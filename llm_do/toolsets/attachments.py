"""Attachment reading toolset for multimodal prompts."""
from __future__ import annotations

import mimetypes
from pathlib import Path
from typing import Any, Optional, cast

from pydantic import TypeAdapter
from pydantic_ai.messages import BinaryContent
from pydantic_ai.tools import ToolDefinition
from pydantic_ai.toolsets import AbstractToolset, ToolsetTool
from pydantic_ai.toolsets.abstract import SchemaValidatorProt


class AttachmentToolset(AbstractToolset[Any]):
    """Toolset for loading binary attachments with approval gating."""

    def __init__(
        self,
        id: Optional[str] = None,
        max_retries: int = 1,
    ) -> None:
        self._id = id
        self._max_retries = max_retries

    @property
    def id(self) -> str | None:
        """Unique identifier for this toolset."""
        return self._id

    def get_approval_description(self, name: str, tool_args: dict[str, Any], ctx: Any) -> str:
        path = tool_args.get("path", "")
        return f"Read attachment {path}"

    async def get_tools(self, ctx: Any) -> dict[str, ToolsetTool[Any]]:
        read_schema = {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Path to the attachment file",
                },
            },
            "required": ["path"],
        }

        return {
            "read_attachment": ToolsetTool(
                toolset=self,
                tool_def=ToolDefinition(
                    name="read_attachment",
                    description="Read a binary attachment for multimodal prompts.",
                    parameters_json_schema=read_schema,
                ),
                max_retries=self._max_retries,
                args_validator=cast(SchemaValidatorProt, TypeAdapter(dict[str, Any]).validator),
            )
        }

    async def call_tool(
        self,
        name: str,
        tool_args: dict[str, Any],
        ctx: Any,
        tool: ToolsetTool[Any],
    ) -> Any:
        if name != "read_attachment":
            raise KeyError(f"Tool {name} not found in toolset")
        return self.read_attachment(tool_args["path"])

    def read_attachment(self, path: str) -> BinaryContent:
        """Read attachment data from disk and infer media type."""
        file_path = Path(path).expanduser().resolve()
        if not file_path.exists():
            raise FileNotFoundError(f"Attachment not found: {path}")

        media_type, _ = mimetypes.guess_type(str(file_path))
        if media_type is None:
            media_type = "application/octet-stream"

        data = file_path.read_bytes()
        return BinaryContent(data=data, media_type=media_type)
