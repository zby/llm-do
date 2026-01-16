"""Simple filesystem toolset for llm-do workers."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Optional, cast

from pydantic import BaseModel, Field
from pydantic_ai.tools import ToolDefinition
from pydantic_ai.toolsets import AbstractToolset, ToolsetTool
from pydantic_ai.toolsets.abstract import SchemaValidatorProt
from pydantic_ai_blocking_approval import (
    ApprovalConfig,
    ApprovalResult,
    needs_approval_from_config,
)

from .validators import DictValidator

DEFAULT_MAX_READ_CHARS = 20_000


class ReadResult(BaseModel):
    content: str = Field(description="The file content read")
    truncated: bool = Field(description="True if more content exists")
    total_chars: int = Field(description="Total file size in characters")
    offset: int = Field(description="Starting character position")
    chars_read: int = Field(description="Characters returned")


class ReadFileArgs(BaseModel):
    path: str = Field(description="Path to the file to read")
    max_chars: int = Field(default=DEFAULT_MAX_READ_CHARS, description="Maximum characters to read")
    offset: int = Field(default=0, description="Character position to start reading from")


class WriteFileArgs(BaseModel):
    path: str = Field(description="Path to the file to write")
    content: str = Field(description="Content to write to the file")


class ListFilesArgs(BaseModel):
    path: str = Field(default=".", description="Directory to search in")
    pattern: str = Field(default="**/*", description="Glob pattern to match")


class FileSystemToolset(AbstractToolset[Any]):
    """Simple file I/O toolset: read_file, write_file, list_files."""

    def __init__(self, config: dict, id: Optional[str] = None, max_retries: int = 1):
        self._config = config
        self._base_path: Path | None = Path(config["base_path"]).expanduser().resolve() if "base_path" in config else None
        self._read_approval = config.get("read_approval", False)
        self._write_approval = config.get("write_approval", True)
        self._toolset_id = id
        self._max_retries = max_retries

    @property
    def id(self) -> str | None:
        return self._toolset_id

    @property
    def config(self) -> dict:
        return self._config

    def _resolve_path(self, path: str) -> Path:
        """Resolve a path (relative to base_path/CWD or absolute)."""
        p = Path(path).expanduser()
        if p.is_absolute():
            return p.resolve()
        return (self._base_path / p).resolve() if self._base_path else p.resolve()

    def needs_approval(
        self,
        name: str,
        tool_args: dict[str, Any],
        ctx: Any,
        config: ApprovalConfig | None = None,
    ) -> ApprovalResult:
        base = needs_approval_from_config(name, config)
        if base.is_blocked or base.is_pre_approved:
            return base

        approval_required = {
            "read_file": self._read_approval,
            "list_files": self._read_approval,
            "write_file": self._write_approval,
        }.get(name)
        if approval_required is None:
            return ApprovalResult.needs_approval()
        return ApprovalResult.needs_approval() if approval_required else ApprovalResult.pre_approved()

    def get_approval_description(
        self, name: str, tool_args: dict[str, Any], ctx: Any
    ) -> str:
        path = tool_args.get("path", "")
        if name == "write_file":
            return f"Write {len(tool_args.get('content', ''))} chars to {path}"
        if name == "read_file":
            return f"Read from {path}"
        if name == "list_files":
            return f"List files matching {tool_args.get('pattern', '**/*')} in {tool_args.get('path', '.')}"
        return f"{name}({path})"

    def read_file(self, path: str, max_chars: int = DEFAULT_MAX_READ_CHARS, offset: int = 0) -> ReadResult:
        """Read text file with optional seeking support."""
        resolved = self._resolve_path(path)
        if not resolved.exists():
            raise FileNotFoundError(f"File not found: {path}")
        if not resolved.is_file():
            raise IsADirectoryError(f"Not a file: {path}")

        # For small files (< 1MB), just read the whole thing
        if resolved.stat().st_size < 1024 * 1024:
            text = resolved.read_text(encoding="utf-8")
            total_chars = len(text)
            text = text[offset:] if offset > 0 else text
            truncated = len(text) > max_chars
            return ReadResult(content=text[:max_chars], truncated=truncated, total_chars=total_chars, offset=offset, chars_read=min(len(text), max_chars))

        # For larger files, use streaming approach
        with open(resolved, "r", encoding="utf-8") as f:
            if offset > 0:
                skipped = 0
                while skipped < offset:
                    chunk = f.read(min(8192, offset - skipped))
                    if not chunk:
                        return ReadResult(content="", truncated=False, total_chars=skipped, offset=offset, chars_read=0)
                    skipped += len(chunk)

            text = f.read(max_chars + 1)
            truncated = len(text) > max_chars
            if truncated:
                text = text[:max_chars]
            remaining = sum(len(chunk) for chunk in iter(lambda: f.read(65536), ""))
            total_chars = offset + len(text) + remaining + (1 if truncated else 0)

        return ReadResult(content=text, truncated=truncated, total_chars=total_chars, offset=offset, chars_read=len(text))

    def write_file(self, path: str, content: str) -> str:
        """Write text file."""
        resolved = self._resolve_path(path)
        resolved.parent.mkdir(parents=True, exist_ok=True)
        resolved.write_text(content, encoding="utf-8")
        return f"Written {len(content)} characters to {path}"

    def list_files(self, path: str = ".", pattern: str = "**/*") -> list[str]:
        """List files matching pattern in a directory."""
        base = self._resolve_path(path)
        results = []
        for match in base.glob(pattern):
            if match.is_file():
                try:
                    results.append(str(match.relative_to(base)))
                except ValueError:
                    results.append(str(match))
        return sorted(results)

    def _make_tool(self, name: str, desc: str, args_cls: type[BaseModel]) -> ToolsetTool[Any]:
        return ToolsetTool(
            toolset=self,
            tool_def=ToolDefinition(name=name, description=desc, parameters_json_schema=args_cls.model_json_schema()),
            max_retries=self._max_retries,
            args_validator=cast(SchemaValidatorProt, DictValidator(args_cls)),
        )

    async def get_tools(self, ctx: Any) -> dict[str, ToolsetTool[Any]]:
        return {
            "read_file": self._make_tool("read_file", "Read a text file. Do not use on binary files - pass them as attachments instead.", ReadFileArgs),
            "write_file": self._make_tool("write_file", "Write a text file.", WriteFileArgs),
            "list_files": self._make_tool("list_files", "List files in a directory matching a glob pattern.", ListFilesArgs),
        }

    async def call_tool(
        self, name: str, tool_args: dict[str, Any], ctx: Any, tool: ToolsetTool[Any]
    ) -> Any:
        if name == "read_file":
            return self.read_file(tool_args["path"], tool_args.get("max_chars", DEFAULT_MAX_READ_CHARS), tool_args.get("offset", 0))
        if name == "write_file":
            return self.write_file(tool_args["path"], tool_args["content"])
        if name == "list_files":
            return self.list_files(tool_args.get("path", "."), tool_args.get("pattern", "**/*"))
        raise ValueError(f"Unknown tool: {name}")


class ReadOnlyFileSystemToolset(FileSystemToolset):
    """Read-only filesystem toolset (read/list only)."""

    def needs_approval(
        self,
        name: str,
        tool_args: dict[str, Any],
        ctx: Any,
        config: ApprovalConfig | None = None,
    ) -> ApprovalResult:
        if name == "write_file":
            return ApprovalResult.blocked("write_file is disabled for read-only filesystem")
        return super().needs_approval(name, tool_args, ctx, config)

    async def get_tools(self, ctx: Any) -> dict[str, ToolsetTool[Any]]:
        tools = await super().get_tools(ctx)
        tools.pop("write_file", None)
        return tools

    async def call_tool(
        self,
        name: str,
        tool_args: dict[str, Any],
        ctx: Any,
        tool: ToolsetTool[Any],
    ) -> Any:
        if name == "write_file":
            raise PermissionError("write_file is disabled for read-only filesystem")
        return await super().call_tool(name, tool_args, ctx, tool)
