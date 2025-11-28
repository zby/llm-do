"""File sandbox implementation with LLM-friendly errors.

This module provides a standalone, reusable filesystem sandbox for PydanticAI:
- FileSandboxConfig and PathConfig for configuration
- FileSandboxError classes with LLM-friendly messages
- FileSandboxImpl implementation as a PydanticAI AbstractToolset
- Built-in approval checking support (optional)

This module is designed to be fully self-contained and can be extracted
as a standalone PydanticAI package. It has no dependencies beyond
pydantic and pydantic-ai.

Usage (standalone):
    from filesystem_sandbox import FileSandboxImpl, FileSandboxConfig, PathConfig

    config = FileSandboxConfig(paths={
        "data": PathConfig(root="./data", mode="rw"),
    })
    sandbox = FileSandboxImpl(config)
    agent = Agent(..., toolsets=[sandbox])

Usage (with approval):
    from filesystem_sandbox import FileSandboxImpl, ApprovalToolsetWrapper

    sandbox = FileSandboxImpl(config)
    approved_sandbox = ApprovalToolsetWrapper(sandbox, controller)
    agent = Agent(..., toolsets=[approved_sandbox])
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, Literal, Mapping, Optional

from pydantic import BaseModel, Field, TypeAdapter
from pydantic_ai.toolsets import AbstractToolset, ToolsetTool
from pydantic_ai.tools import RunContext, ToolDefinition


# ---------------------------------------------------------------------------
# Approval Types (self-contained for standalone use)
# ---------------------------------------------------------------------------


class ApprovalContext(BaseModel):
    """Context passed to check_approval.

    This is the input to the approval check - it contains the tool name
    and arguments that the LLM is trying to execute.
    """

    tool_name: str
    args: dict[str, Any]
    metadata: dict[str, Any] = Field(default_factory=dict)


class ApprovalRequest(BaseModel):
    """Returned by check_approval when approval is needed.

    The payload is used for "approve for session" matching - identical
    payloads will be auto-approved after the first approval.
    """

    tool_name: str
    description: str
    payload: dict[str, Any]


class ApprovalDecision(BaseModel):
    """Result of an approval request."""

    approved: bool
    scope: Literal["once", "session"] = "once"
    note: Optional[str] = None


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------


class PathConfig(BaseModel):
    """Configuration for a single path in the sandbox."""

    root: str = Field(description="Root directory path")
    mode: Literal["ro", "rw"] = Field(
        default="ro", description="Access mode: 'ro' (read-only) or 'rw' (read-write)"
    )
    suffixes: Optional[list[str]] = Field(
        default=None,
        description="Allowed file suffixes (e.g., ['.md', '.txt']). None means all allowed.",
    )
    max_file_bytes: Optional[int] = Field(
        default=None, description="Maximum file size in bytes. None means no limit."
    )
    # Approval settings
    write_approval: bool = Field(
        default=True,
        description="Whether writes to this path require approval",
    )
    read_approval: bool = Field(
        default=False,
        description="Whether reads from this path require approval",
    )


class FileSandboxConfig(BaseModel):
    """Configuration for a file sandbox."""

    paths: dict[str, PathConfig] = Field(
        default_factory=dict,
        description="Named paths with their configurations",
    )


# ---------------------------------------------------------------------------
# LLM-Friendly Errors
# ---------------------------------------------------------------------------


class FileSandboxError(Exception):
    """Base class for sandbox errors with LLM-friendly messages.

    All sandbox errors include guidance on what IS allowed,
    helping the LLM correct its behavior.
    """

    pass


class PathNotInSandboxError(FileSandboxError):
    """Raised when a path is outside all sandbox boundaries."""

    def __init__(self, path: str, readable_roots: list[str]):
        self.path = path
        self.readable_roots = readable_roots
        roots_str = ", ".join(readable_roots) if readable_roots else "none"
        self.message = (
            f"Cannot access '{path}': path is outside sandbox.\n"
            f"Readable paths: {roots_str}"
        )
        super().__init__(self.message)


class PathNotWritableError(FileSandboxError):
    """Raised when trying to write to a read-only path."""

    def __init__(self, path: str, writable_roots: list[str]):
        self.path = path
        self.writable_roots = writable_roots
        roots_str = ", ".join(writable_roots) if writable_roots else "none"
        self.message = (
            f"Cannot write to '{path}': path is read-only.\n"
            f"Writable paths: {roots_str}"
        )
        super().__init__(self.message)


class SuffixNotAllowedError(FileSandboxError):
    """Raised when file suffix is not in the allowed list."""

    def __init__(self, path: str, suffix: str, allowed: list[str]):
        self.path = path
        self.suffix = suffix
        self.allowed = allowed
        allowed_str = ", ".join(allowed) if allowed else "any"
        self.message = (
            f"Cannot access '{path}': suffix '{suffix}' not allowed.\n"
            f"Allowed suffixes: {allowed_str}"
        )
        super().__init__(self.message)


class FileTooLargeError(FileSandboxError):
    """Raised when file exceeds size limit."""

    def __init__(self, path: str, size: int, limit: int):
        self.path = path
        self.size = size
        self.limit = limit
        self.message = (
            f"Cannot read '{path}': file too large ({size:,} bytes).\n"
            f"Maximum allowed: {limit:,} bytes"
        )
        super().__init__(self.message)


# ---------------------------------------------------------------------------
# Read Result
# ---------------------------------------------------------------------------


DEFAULT_MAX_READ_CHARS = 20_000
"""Default maximum characters to read from a file."""


class ReadResult(BaseModel):
    """Result of reading a file from the sandbox."""

    content: str = Field(description="The file content read")
    truncated: bool = Field(description="True if more content exists after this chunk")
    total_chars: int = Field(description="Total file size in characters")
    offset: int = Field(description="Starting character position used")
    chars_read: int = Field(description="Number of characters actually returned")


# ---------------------------------------------------------------------------
# Implementation
# ---------------------------------------------------------------------------


class FileSandboxImpl(AbstractToolset[Any]):
    """File sandbox implementation as a PydanticAI AbstractToolset.

    Implements both the FileSandbox protocol and AbstractToolset interface.
    Provides read_file, write_file, and list_files tools.
    """

    def __init__(
        self,
        config: FileSandboxConfig,
        base_path: Optional[Path] = None,
        id: Optional[str] = None,
        max_retries: int = 1,
    ):
        """Initialize the file sandbox toolset.

        Args:
            config: Sandbox configuration
            base_path: Base path for resolving relative roots (defaults to cwd)
            id: Optional toolset ID for durable execution
            max_retries: Maximum number of retries for tool calls (default: 1)
        """
        self.config = config
        self._base_path = base_path or Path.cwd()
        self._toolset_id = id
        self._max_retries = max_retries
        self._paths: dict[str, tuple[Path, PathConfig]] = {}
        self._setup_paths()

    def _setup_paths(self) -> None:
        """Resolve and validate configured paths."""
        for name, path_config in self.config.paths.items():
            root = Path(path_config.root)
            if not root.is_absolute():
                root = (self._base_path / root).resolve()
            else:
                root = root.resolve()
            # Create directory if it doesn't exist
            root.mkdir(parents=True, exist_ok=True)
            self._paths[name] = (root, path_config)

    @property
    def readable_roots(self) -> list[str]:
        """List of readable path roots (for error messages)."""
        return [name for name in self._paths.keys()]

    @property
    def writable_roots(self) -> list[str]:
        """List of writable path roots (for error messages)."""
        return [
            name
            for name, (_, config) in self._paths.items()
            if config.mode == "rw"
        ]

    def _find_path_for(self, path: str) -> tuple[str, Path, PathConfig]:
        """Find which sandbox path contains the given path.

        Args:
            path: Path to look up (can be "sandbox_name/relative" or absolute)

        Returns:
            Tuple of (sandbox_name, resolved_path, path_config)

        Raises:
            PathNotInSandboxError: If path is not in any sandbox
        """
        # Handle "sandbox_name/relative/path" format
        if "/" in path and not path.startswith("/"):
            parts = path.split("/", 1)
            sandbox_name = parts[0]
            if sandbox_name in self._paths:
                root, config = self._paths[sandbox_name]
                relative = parts[1] if len(parts) > 1 else ""
                resolved = self._resolve_within(root, relative)
                return (sandbox_name, resolved, config)

        # Handle "sandbox_name:relative/path" format
        if ":" in path:
            parts = path.split(":", 1)
            sandbox_name = parts[0]
            if sandbox_name in self._paths:
                root, config = self._paths[sandbox_name]
                relative = parts[1].lstrip("/") if len(parts) > 1 else ""
                resolved = self._resolve_within(root, relative)
                return (sandbox_name, resolved, config)

        # Try to find path in any sandbox
        check_path = Path(path)
        if check_path.is_absolute():
            check_path = check_path.resolve()
            for name, (root, config) in self._paths.items():
                try:
                    check_path.relative_to(root)
                    return (name, check_path, config)
                except ValueError:
                    continue

        raise PathNotInSandboxError(path, self.readable_roots)

    def _resolve_within(self, root: Path, relative: str) -> Path:
        """Resolve a relative path within a root, preventing escapes.

        Args:
            root: The sandbox root directory
            relative: Relative path within the sandbox

        Returns:
            Resolved absolute path

        Raises:
            PathNotInSandboxError: If resolved path escapes the root
        """
        relative = relative.lstrip("/")
        candidate = (root / relative).resolve()
        try:
            candidate.relative_to(root)
        except ValueError:
            raise PathNotInSandboxError(
                relative, self.readable_roots
            )
        return candidate

    def can_read(self, path: str) -> bool:
        """Check if path is readable within sandbox boundaries."""
        try:
            self._find_path_for(path)
            return True
        except FileSandboxError:
            return False

    def can_write(self, path: str) -> bool:
        """Check if path is writable within sandbox boundaries."""
        try:
            _, _, config = self._find_path_for(path)
            return config.mode == "rw"
        except FileSandboxError:
            return False

    def resolve(self, path: str) -> Path:
        """Resolve path within sandbox.

        Args:
            path: Relative or absolute path to resolve

        Returns:
            Resolved absolute Path

        Raises:
            PathNotInSandboxError: If path is outside sandbox boundaries
        """
        _, resolved, _ = self._find_path_for(path)
        return resolved

    def _check_suffix(self, path: Path, config: PathConfig) -> None:
        """Check if file suffix is allowed.

        Raises:
            SuffixNotAllowedError: If suffix is not in allowed list
        """
        if config.suffixes is not None:
            suffix = path.suffix.lower()
            allowed = [s.lower() for s in config.suffixes]
            if suffix not in allowed:
                raise SuffixNotAllowedError(str(path), suffix, config.suffixes)

    def _check_size(self, path: Path, config: PathConfig) -> None:
        """Check if file size is within limit.

        Raises:
            FileTooLargeError: If file exceeds size limit
        """
        if config.max_file_bytes is not None and path.exists():
            size = path.stat().st_size
            if size > config.max_file_bytes:
                raise FileTooLargeError(str(path), size, config.max_file_bytes)

    # ---------------------------------------------------------------------------
    # Approval Interface (ApprovalAware protocol)
    # ---------------------------------------------------------------------------

    def check_approval(self, ctx: ApprovalContext) -> Optional[ApprovalRequest]:
        """Check if the tool call requires approval.

        This is the single entry point for all tools in this toolset.
        It dispatches based on ctx.tool_name.

        Args:
            ctx: Approval context with tool_name and args

        Returns:
            ApprovalRequest if approval is needed, None otherwise

        Raises:
            PermissionError: If operation is blocked entirely (path not in sandbox, etc.)
        """
        if ctx.tool_name == "write_file":
            return self._check_write_approval(ctx)
        elif ctx.tool_name == "read_file":
            return self._check_read_approval(ctx)
        # list_files doesn't require approval
        return None

    def _check_write_approval(self, ctx: ApprovalContext) -> Optional[ApprovalRequest]:
        """Check if a write operation requires approval.

        Note: Path validation here is intentionally duplicated in write().
        This provides defense in depth - early rejection here gives better error
        messages, while write() remains safe as a standalone method.
        """
        path = ctx.args.get("path", "")

        try:
            sandbox_name, resolved, config = self._find_path_for(path)
        except PathNotInSandboxError:
            # Re-raise as PermissionError for blocked operations
            raise PermissionError(f"Path not in any sandbox: {path}")

        if config.mode != "rw":
            raise PermissionError(f"Path is read-only: {path}")

        if config.write_approval:
            return ApprovalRequest(
                tool_name=ctx.tool_name,
                description=f"Write to {sandbox_name}:{path}",
                payload={"sandbox": sandbox_name, "path": path},
                # Note: presentation (diff) is generated lazily by the controller
            )

        return None  # Pre-approved by config

    def _check_read_approval(self, ctx: ApprovalContext) -> Optional[ApprovalRequest]:
        """Check if a read operation requires approval.

        Note: Path validation here is intentionally duplicated in read().
        This provides defense in depth - early rejection here gives better error
        messages, while read() remains safe as a standalone method.
        """
        path = ctx.args.get("path", "")

        try:
            sandbox_name, resolved, config = self._find_path_for(path)
        except PathNotInSandboxError:
            raise PermissionError(f"Path not in any sandbox: {path}")

        if config.read_approval:
            return ApprovalRequest(
                tool_name=ctx.tool_name,
                description=f"Read from {sandbox_name}:{path}",
                payload={"sandbox": sandbox_name, "path": path},
            )

        return None  # Pre-approved by config

    # ---------------------------------------------------------------------------
    # File Operations
    # ---------------------------------------------------------------------------

    def read(self, path: str, max_chars: int = DEFAULT_MAX_READ_CHARS, offset: int = 0) -> ReadResult:
        """Read text file from sandbox.

        Args:
            path: Path to file (relative to sandbox)
            max_chars: Maximum characters to read
            offset: Character position to start reading from (default: 0)

        Returns:
            ReadResult with content, truncation info, and metadata

        Raises:
            PathNotInSandboxError: If path outside sandbox
            SuffixNotAllowedError: If suffix not allowed
            FileTooLargeError: If file too large
            FileNotFoundError: If file doesn't exist
        """
        name, resolved, config = self._find_path_for(path)

        if not resolved.exists():
            raise FileNotFoundError(f"File not found: {path}")

        if not resolved.is_file():
            raise IsADirectoryError(f"Not a file: {path}")

        self._check_suffix(resolved, config)
        self._check_size(resolved, config)

        text = resolved.read_text(encoding="utf-8")
        total_chars = len(text)

        # Apply offset
        if offset > 0:
            text = text[offset:]

        # Apply max_chars limit
        truncated = len(text) > max_chars
        if truncated:
            text = text[:max_chars]

        return ReadResult(
            content=text,
            truncated=truncated,
            total_chars=total_chars,
            offset=offset,
            chars_read=len(text),
        )

    def write(self, path: str, content: str) -> str:
        """Write text file to sandbox.

        Args:
            path: Path to file (relative to sandbox)
            content: Content to write

        Returns:
            Confirmation message

        Raises:
            PathNotInSandboxError: If path outside sandbox
            PathNotWritableError: If path is read-only
            SuffixNotAllowedError: If suffix not allowed
        """
        name, resolved, config = self._find_path_for(path)

        if config.mode != "rw":
            raise PathNotWritableError(path, self.writable_roots)

        self._check_suffix(resolved, config)

        # Check content size against limit
        if config.max_file_bytes is not None:
            content_bytes = len(content.encode("utf-8"))
            if content_bytes > config.max_file_bytes:
                raise FileTooLargeError(path, content_bytes, config.max_file_bytes)

        # Create parent directories if needed
        resolved.parent.mkdir(parents=True, exist_ok=True)

        resolved.write_text(content, encoding="utf-8")
        return f"Written {len(content)} characters to {name}/{resolved.relative_to(self._paths[name][0])}"

    def list_files(self, path: str = ".", pattern: str = "**/*") -> list[str]:
        """List files matching pattern within sandbox.

        Args:
            path: Base path to search from (sandbox name or sandbox_name/subdir)
            pattern: Glob pattern to match

        Returns:
            List of matching file paths (as sandbox_name/relative format)
        """
        # If path is "." or empty, list all sandboxes
        if path in (".", ""):
            results = []
            for name, (root, _) in self._paths.items():
                for match in root.glob(pattern):
                    if match.is_file():
                        try:
                            rel = match.relative_to(root)
                            results.append(f"{name}/{rel}")
                        except ValueError:
                            continue
            return sorted(results)

        # Otherwise, find the specific path
        try:
            name, resolved, _ = self._find_path_for(path)
        except PathNotInSandboxError:
            # Path might be just a sandbox name
            if path in self._paths:
                name = path
                resolved, _ = self._paths[name]
            else:
                raise

        root, _ = self._paths[name]
        results = []
        for match in resolved.glob(pattern):
            if match.is_file():
                try:
                    rel = match.relative_to(root)
                    results.append(f"{name}/{rel}")
                except ValueError:
                    continue
        return sorted(results)

    # ---------------------------------------------------------------------------
    # AbstractToolset Implementation
    # ---------------------------------------------------------------------------

    @property
    def id(self) -> str | None:
        """Unique identifier for this toolset."""
        return self._toolset_id

    async def get_tools(self, ctx: RunContext[Any]) -> dict[str, ToolsetTool[Any]]:
        """Return the tools provided by this toolset."""
        tools = {}

        # Define tool schemas
        read_file_schema = {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Path format: 'sandbox_name/relative/path'",
                },
                "max_chars": {
                    "type": "integer",
                    "default": DEFAULT_MAX_READ_CHARS,
                    "description": f"Maximum characters to read (default {DEFAULT_MAX_READ_CHARS:,})",
                },
                "offset": {
                    "type": "integer",
                    "default": 0,
                    "description": "Character position to start reading from (default 0)",
                },
            },
            "required": ["path"],
        }

        write_file_schema = {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Path format: 'sandbox_name/relative/path'",
                },
                "content": {
                    "type": "string",
                    "description": "Content to write to the file",
                },
            },
            "required": ["path", "content"],
        }

        list_files_schema = {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "default": ".",
                    "description": "Path format: 'sandbox_name' or 'sandbox_name/subdir' (default: '.')",
                },
                "pattern": {
                    "type": "string",
                    "default": "**/*",
                    "description": "Glob pattern to match (default: '**/*')",
                },
            },
        }

        # Create ToolsetTool instances
        tools["read_file"] = ToolsetTool(
            toolset=self,
            tool_def=ToolDefinition(
                name="read_file",
                description=(
                    "Read a text file from the sandbox. "
                    "Path format: 'sandbox_name/relative/path'. "
                    "Do not use this on binary files (PDFs, images, etc) - "
                    "pass them as attachments instead."
                ),
                parameters_json_schema=read_file_schema,
            ),
            max_retries=self._max_retries,
            args_validator=TypeAdapter(dict[str, Any]).validator,
        )

        tools["write_file"] = ToolsetTool(
            toolset=self,
            tool_def=ToolDefinition(
                name="write_file",
                description=(
                    "Write a text file to the sandbox. "
                    "Path format: 'sandbox_name/relative/path'."
                ),
                parameters_json_schema=write_file_schema,
            ),
            max_retries=self._max_retries,
            args_validator=TypeAdapter(dict[str, Any]).validator,
        )

        tools["list_files"] = ToolsetTool(
            toolset=self,
            tool_def=ToolDefinition(
                name="list_files",
                description=(
                    "List files in the sandbox matching a glob pattern. "
                    "Path format: 'sandbox_name' or 'sandbox_name/subdir'. "
                    "Use '.' to list all sandboxes."
                ),
                parameters_json_schema=list_files_schema,
            ),
            max_retries=self._max_retries,
            args_validator=TypeAdapter(dict[str, Any]).validator,
        )

        return tools

    async def call_tool(
        self,
        name: str,
        tool_args: dict[str, Any],
        ctx: RunContext[Any],
        tool: ToolsetTool[Any],
    ) -> Any:
        """Call a tool with the given arguments.

        Note: Approval checking is handled by the runtime via check_approval().
        This method just executes the operation.
        """
        if name == "read_file":
            path = tool_args["path"]
            max_chars = tool_args.get("max_chars", DEFAULT_MAX_READ_CHARS)
            offset = tool_args.get("offset", 0)
            return self.read(path, max_chars=max_chars, offset=offset)

        elif name == "write_file":
            path = tool_args["path"]
            content = tool_args["content"]
            return self.write(path, content)

        elif name == "list_files":
            path = tool_args.get("path", ".")
            pattern = tool_args.get("pattern", "**/*")
            return self.list_files(path, pattern)

        else:
            raise ValueError(f"Unknown tool: {name}")


# ---------------------------------------------------------------------------
# Approval Controller (self-contained for standalone use)
# ---------------------------------------------------------------------------


class ApprovalController:
    """Manages approval requests, session memory, and user prompts.

    This is a self-contained approval controller for standalone use.
    It handles:
    - Runtime mode interpretation (interactive, approve_all, strict)
    - Session approval caching (don't prompt twice for same operation)
    - User prompt dispatch via callback

    Usage:
        # Auto-approve everything (for tests)
        controller = ApprovalController(mode="approve_all")

        # Reject everything (for CI/production)
        controller = ApprovalController(mode="strict")

        # Interactive mode with custom callback
        def my_callback(request: ApprovalRequest) -> ApprovalDecision:
            # Show UI, get user input
            return ApprovalDecision(approved=True, scope="session")

        controller = ApprovalController(mode="interactive", approval_callback=my_callback)
    """

    def __init__(
        self,
        mode: Literal["interactive", "approve_all", "strict"] = "interactive",
        approval_callback: Optional[Callable[[ApprovalRequest], ApprovalDecision]] = None,
    ):
        self.mode = mode
        self._approval_callback = approval_callback
        self._session_approvals: set[tuple[str, frozenset]] = set()

    def _make_key(self, request: ApprovalRequest) -> tuple[str, frozenset]:
        """Create hashable key for session matching."""

        def freeze(obj: Any) -> Any:
            if isinstance(obj, dict):
                return frozenset((k, freeze(v)) for k, v in sorted(obj.items()))
            elif isinstance(obj, (list, tuple)):
                return tuple(freeze(x) for x in obj)
            return obj

        return (request.tool_name, freeze(request.payload))

    def is_session_approved(self, request: ApprovalRequest) -> bool:
        """Check if this request is already approved for the session."""
        return self._make_key(request) in self._session_approvals

    def add_session_approval(self, request: ApprovalRequest) -> None:
        """Add a request to the session approval cache."""
        self._session_approvals.add(self._make_key(request))

    async def request_approval(self, request: ApprovalRequest) -> ApprovalDecision:
        """Request approval for a tool call.

        This handles mode interpretation, session caching, and user prompts.
        """
        if self.mode == "approve_all":
            return ApprovalDecision(approved=True)
        if self.mode == "strict":
            return ApprovalDecision(
                approved=False, note=f"Strict mode: {request.tool_name} requires approval"
            )

        if self.is_session_approved(request):
            return ApprovalDecision(approved=True, scope="session")

        if self._approval_callback is None:
            raise NotImplementedError(
                "No approval_callback provided for interactive mode"
            )

        decision = self._approval_callback(request)

        if decision.approved and decision.scope == "session":
            self.add_session_approval(request)

        return decision


# ---------------------------------------------------------------------------
# Approval Toolset Wrapper (self-contained for standalone use)
# ---------------------------------------------------------------------------


class ApprovalToolsetWrapper(AbstractToolset):
    """Wraps a toolset with approval checking.

    This intercepts tool calls and checks if they need approval before
    executing. It works with any toolset that implements `check_approval()`.

    Usage:
        sandbox = FileSandboxImpl(config)
        controller = ApprovalController(mode="interactive", approval_callback=...)
        approved_sandbox = ApprovalToolsetWrapper(sandbox, controller)
        agent = Agent(..., toolsets=[approved_sandbox])
    """

    def __init__(
        self,
        inner: AbstractToolset,
        controller: ApprovalController,
    ):
        self._inner = inner
        self._controller = controller

    @property
    def id(self) -> Optional[str]:
        return getattr(self._inner, "id", None)

    @property
    def label(self) -> str:
        return getattr(self._inner, "label", self.__class__.__name__)

    @property
    def tool_name_conflict_hint(self) -> str:
        return getattr(
            self._inner,
            "tool_name_conflict_hint",
            "Rename the tool or use a PrefixedToolset.",
        )

    async def __aenter__(self) -> "ApprovalToolsetWrapper":
        if hasattr(self._inner, "__aenter__"):
            await self._inner.__aenter__()
        return self

    async def __aexit__(self, *args: Any) -> Optional[bool]:
        if hasattr(self._inner, "__aexit__"):
            return await self._inner.__aexit__(*args)
        return None

    async def get_tools(self, ctx: Any) -> dict:
        return await self._inner.get_tools(ctx)

    async def call_tool(
        self,
        name: str,
        tool_args: dict[str, Any],
        ctx: Any,
        tool: Any,
    ) -> Any:
        """Call tool with approval checking."""
        if hasattr(self._inner, "check_approval"):
            approval_ctx = ApprovalContext(
                tool_name=name,
                args=tool_args,
                metadata={"toolset_id": self.id},
            )

            try:
                approval_request = self._inner.check_approval(approval_ctx)
            except PermissionError:
                raise

            if approval_request is not None:
                decision = await self._controller.request_approval(approval_request)

                if not decision.approved:
                    note = f": {decision.note}" if decision.note else ""
                    raise PermissionError(f"Approval denied for {name}{note}")

        return await self._inner.call_tool(name, tool_args, ctx, tool)
