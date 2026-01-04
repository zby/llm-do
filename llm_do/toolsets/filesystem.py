"""Simple filesystem toolset for llm-do workers.

This module provides basic file operations without sandbox validation.
Security is provided by the Docker container boundary.

Security model: llm-do is designed to run inside a Docker container.
The container provides the security boundary. Running on bare metal
is at user's own risk.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Optional, cast

from pydantic import BaseModel, Field, TypeAdapter
from pydantic_ai.tools import ToolDefinition
from pydantic_ai.toolsets import AbstractToolset, ToolsetTool
from pydantic_ai.toolsets.abstract import SchemaValidatorProt
from pydantic_ai_blocking_approval import (
    ApprovalConfig,
    ApprovalResult,
    needs_approval_from_config,
)

DEFAULT_MAX_READ_CHARS = 20_000
"""Default maximum characters to read from a file."""


class ReadResult(BaseModel):
    """Result of reading a file."""

    content: str = Field(description="The file content read")
    truncated: bool = Field(description="True if more content exists after this chunk")
    total_chars: int = Field(description="Total file size in characters")
    offset: int = Field(description="Starting character position used")
    chars_read: int = Field(description="Number of characters actually returned")


class FileSystemToolset(AbstractToolset[Any]):
    """Simple file I/O toolset for PydanticAI agents.

    Provides read_file, write_file, and list_files tools.
    Works with normal filesystem paths (relative to CWD or absolute).
    No sandbox validation - security is provided by Docker container.

    Example:
        toolset = FileSystemToolset(config={})
        agent = Agent(..., toolsets=[toolset])
    """

    def __init__(
        self,
        config: dict,
        id: Optional[str] = None,
        max_retries: int = 1,
    ):
        """Initialize the file system toolset.

        Args:
            config: Configuration dict. Supports:
                - read_approval: Whether reads require approval (default: False)
                - write_approval: Whether writes require approval (default: True)
            id: Optional toolset ID for durable execution
            max_retries: Maximum number of retries for tool calls (default: 1)
        """
        self._config = config
        self._read_approval = config.get("read_approval", False)
        self._write_approval = config.get("write_approval", True)
        self._toolset_id = id
        self._max_retries = max_retries

    @property
    def id(self) -> str | None:
        """Unique identifier for this toolset."""
        return self._toolset_id

    @property
    def config(self) -> dict:
        """Return the toolset configuration."""
        return self._config

    def _resolve_path(self, path: str) -> Path:
        """Resolve a path (relative to CWD or absolute).

        Args:
            path: Path string (can be relative or absolute)

        Returns:
            Resolved absolute Path
        """
        return Path(path).expanduser().resolve()

    def needs_approval(
        self,
        name: str,
        tool_args: dict[str, Any],
        ctx: Any,
        config: ApprovalConfig | None = None,
    ) -> ApprovalResult:
        """Check if the tool call requires approval.

        Args:
            name: Tool name being called
            tool_args: Arguments passed to the tool
            ctx: PydanticAI run context
            config: Per-tool approval config from ApprovalToolset

        Returns:
            ApprovalResult with status: pre_approved or needs_approval
        """
        base = needs_approval_from_config(name, config)
        if base.is_blocked:
            return base
        if base.is_pre_approved:
            return base

        if name == "read_file":
            if self._read_approval:
                return ApprovalResult.needs_approval()
            return ApprovalResult.pre_approved()

        elif name == "write_file":
            if self._write_approval:
                return ApprovalResult.needs_approval()
            return ApprovalResult.pre_approved()

        elif name == "list_files":
            if self._read_approval:
                return ApprovalResult.needs_approval()
            return ApprovalResult.pre_approved()

        # Unknown tool - require approval
        return ApprovalResult.needs_approval()

    def get_approval_description(
        self, name: str, tool_args: dict[str, Any], ctx: Any
    ) -> str:
        """Return human-readable description for approval prompt.

        Args:
            name: Tool name being called
            tool_args: Arguments passed to the tool
            ctx: PydanticAI run context

        Returns:
            Description string to show user
        """
        path = tool_args.get("path", "")

        if name == "write_file":
            content = tool_args.get("content", "")
            char_count = len(content)
            return f"Write {char_count} chars to {path}"

        elif name == "read_file":
            return f"Read from {path}"

        elif name == "list_files":
            search_path = tool_args.get("path", ".")
            pattern = tool_args.get("pattern", "**/*")
            return f"List files matching {pattern} in {search_path}"

        return f"{name}({path})"

    def read_file(
        self, path: str, max_chars: int = DEFAULT_MAX_READ_CHARS, offset: int = 0
    ) -> ReadResult:
        """Read text file efficiently with seeking support.

        For large files, avoids loading the entire file into memory by:
        - Using file seeking when offset is specified
        - Reading only the required bytes (with buffer for UTF-8)

        Args:
            path: Path to file
            max_chars: Maximum characters to read
            offset: Character position to start reading from

        Returns:
            ReadResult with content, truncation info, and metadata

        Raises:
            FileNotFoundError: If file doesn't exist
            IsADirectoryError: If path is a directory
        """
        resolved = self._resolve_path(path)

        if not resolved.exists():
            raise FileNotFoundError(f"File not found: {path}")

        if not resolved.is_file():
            raise IsADirectoryError(f"Not a file: {path}")

        file_size = resolved.stat().st_size

        # For small files (< 1MB), just read the whole thing
        # This is simpler and handles edge cases better
        if file_size < 1024 * 1024:
            text = resolved.read_text(encoding="utf-8")
            total_chars = len(text)

            if offset > 0:
                text = text[offset:]

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

        # For larger files, use streaming approach
        with open(resolved, "r", encoding="utf-8") as f:
            # Skip offset characters if needed
            if offset > 0:
                # Read and discard offset characters
                skipped = 0
                while skipped < offset:
                    chunk = f.read(min(8192, offset - skipped))
                    if not chunk:
                        # Reached EOF before offset
                        return ReadResult(
                            content="",
                            truncated=False,
                            total_chars=skipped,
                            offset=offset,
                            chars_read=0,
                        )
                    skipped += len(chunk)

            # Read the content we need (plus one extra to check truncation)
            text = f.read(max_chars + 1)
            truncated = len(text) > max_chars
            if truncated:
                text = text[:max_chars]

            # Estimate total chars by reading rest of file in chunks
            # (needed for total_chars metadata)
            remaining = 0
            while True:
                chunk = f.read(65536)
                if not chunk:
                    break
                remaining += len(chunk)

            total_chars = offset + len(text) + remaining + (1 if truncated else 0)

        return ReadResult(
            content=text,
            truncated=truncated,
            total_chars=total_chars,
            offset=offset,
            chars_read=len(text),
        )

    def write_file(self, path: str, content: str) -> str:
        """Write text file.

        Args:
            path: Path to file
            content: Content to write

        Returns:
            Confirmation message
        """
        resolved = self._resolve_path(path)

        # Create parent directories if needed
        resolved.parent.mkdir(parents=True, exist_ok=True)

        resolved.write_text(content, encoding="utf-8")

        return f"Written {len(content)} characters to {path}"

    def list_files(self, path: str = ".", pattern: str = "**/*") -> list[str]:
        """List files matching pattern in a directory.

        Args:
            path: Directory to search in (default: current directory)
            pattern: Glob pattern to match (default: all files)

        Returns:
            List of matching file paths (relative to search path)
        """
        base = self._resolve_path(path)
        results = []
        for match in base.glob(pattern):
            if match.is_file():
                try:
                    rel = match.relative_to(base)
                    results.append(str(rel))
                except ValueError:
                    results.append(str(match))
        return sorted(results)

    async def get_tools(self, ctx: Any) -> dict[str, ToolsetTool[Any]]:
        """Return the tools provided by this toolset."""
        tools = {}

        # Define tool schemas
        read_file_schema = {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Path to the file to read",
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
                    "description": "Path to the file to write",
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
                    "description": "Directory to search in (default: current directory)",
                },
                "pattern": {
                    "type": "string",
                    "default": "**/*",
                    "description": "Glob pattern to match (default: all files)",
                },
            },
        }

        # Create ToolsetTool instances
        tools["read_file"] = ToolsetTool(
            toolset=self,
            tool_def=ToolDefinition(
                name="read_file",
                description=(
                    "Read a text file. "
                    "Do not use this on binary files (PDFs, images, etc) - "
                    "pass them as attachments instead."
                ),
                parameters_json_schema=read_file_schema,
            ),
            max_retries=self._max_retries,
            args_validator=cast(SchemaValidatorProt, TypeAdapter(dict[str, Any]).validator),
        )

        tools["write_file"] = ToolsetTool(
            toolset=self,
            tool_def=ToolDefinition(
                name="write_file",
                description="Write a text file.",
                parameters_json_schema=write_file_schema,
            ),
            max_retries=self._max_retries,
            args_validator=cast(SchemaValidatorProt, TypeAdapter(dict[str, Any]).validator),
        )

        tools["list_files"] = ToolsetTool(
            toolset=self,
            tool_def=ToolDefinition(
                name="list_files",
                description="List files in a directory matching a glob pattern.",
                parameters_json_schema=list_files_schema,
            ),
            max_retries=self._max_retries,
            args_validator=cast(SchemaValidatorProt, TypeAdapter(dict[str, Any]).validator),
        )

        return tools

    async def call_tool(
        self,
        name: str,
        tool_args: dict[str, Any],
        ctx: Any,
        tool: ToolsetTool[Any],
    ) -> Any:
        """Call a tool with the given arguments."""
        if name == "read_file":
            path = tool_args["path"]
            max_chars = tool_args.get("max_chars", DEFAULT_MAX_READ_CHARS)
            offset = tool_args.get("offset", 0)
            return self.read_file(path, max_chars=max_chars, offset=offset)

        elif name == "write_file":
            path = tool_args["path"]
            content = tool_args["content"]
            return self.write_file(path, content)

        elif name == "list_files":
            path = tool_args.get("path", ".")
            pattern = tool_args.get("pattern", "**/*")
            return self.list_files(path, pattern)

        else:
            raise ValueError(f"Unknown tool: {name}")
