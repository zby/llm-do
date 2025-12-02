"""Type definitions and data models for llm-do workers.

This module contains all the data models and type definitions used throughout
the llm-do system, including worker definitions, contexts, and results.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from typing import Any, Callable, Dict, List, Literal, Optional, Sequence, Type, Union

from pydantic import BaseModel, ConfigDict, Field
from pydantic_ai.messages import BinaryContent
from pydantic_ai.models import Model as PydanticAIModel
from pydantic_ai.toolsets import AbstractToolset

from pydantic_ai_blocking_approval import ApprovalDecision

from .sandbox import AttachmentInput, AttachmentPayload, AttachmentPolicy
from .worker_sandbox import AttachmentValidator, SandboxConfig



# ---------------------------------------------------------------------------
# Worker artifact models
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Toolset configuration types
# ---------------------------------------------------------------------------


class CustomToolConfig(BaseModel):
    """Configuration for a single custom tool."""

    approval_required: bool = Field(
        default=True,
        description="Whether this tool requires user approval (secure by default)"
    )
    allowed: bool = Field(
        default=True,
        description="Whether this tool is allowed at all"
    )


class ShellToolsetConfig(BaseModel):
    """Configuration for the shell toolset."""

    rules: List["ShellRule"] = Field(
        default_factory=list,
        description="Pattern-based rules for shell command approval"
    )
    default: Optional["ShellDefault"] = Field(
        default=None,
        description="Default behavior for commands not matching any rule"
    )


class DelegationToolsetConfig(BaseModel):
    """Configuration for the delegation toolset."""

    allow_workers: List[str] = Field(
        default_factory=list,
        description="List of workers that can be delegated to. Use ['*'] for all."
    )


class ToolsetsConfig(BaseModel):
    """Configuration for all toolsets.

    Each key corresponds to a toolset type. Toolsets are only enabled
    if their config is present and non-null.
    """

    sandbox: Optional["SandboxConfig"] = Field(
        default=None,
        description="Sandbox policy (paths, modes, network)"
    )
    file_tools: bool = Field(
        default=True,
        description="Enable FileSystemToolset (read_file, write_file, etc.)"
    )
    shell: Optional[ShellToolsetConfig] = Field(
        default=None,
        description="Shell command execution configuration"
    )
    delegation: Optional[DelegationToolsetConfig] = Field(
        default=None,
        description="Worker delegation configuration"
    )
    custom: Optional[Dict[str, CustomToolConfig]] = Field(
        default=None,
        description="Custom tools from tools.py. Keys are function names."
    )


# ---------------------------------------------------------------------------
# Shell tool types (used within ShellToolsetConfig)
# ---------------------------------------------------------------------------


class ShellResult(BaseModel):
    """Result from a shell command execution."""

    stdout: str
    stderr: str
    exit_code: int
    truncated: bool = False  # True if output exceeded limit


class ShellRule(BaseModel):
    """Pattern-based rule for shell command approval.

    Rules are matched in order. First match wins.
    """

    pattern: str = Field(description="Command prefix to match (e.g., 'git status')")
    sandbox_paths: List[str] = Field(
        default_factory=list,
        description="Sandboxes for path argument validation. Empty means no path validation."
    )
    approval_required: bool = Field(
        default=True,
        description="Whether this command requires user approval"
    )
    allowed: bool = Field(
        default=True,
        description="Whether this command is allowed at all"
    )


class ShellDefault(BaseModel):
    """Default behavior for shell commands that don't match any rule."""

    allowed: bool = Field(
        default=True,
        description="Whether unmatched commands are allowed"
    )
    approval_required: bool = Field(
        default=True,
        description="Whether unmatched commands require approval"
    )


# ---------------------------------------------------------------------------
# Server-side tools (provider-executed)
# ---------------------------------------------------------------------------


class ServerSideToolConfig(BaseModel):
    """Configuration for a server-side tool executed by the LLM provider.

    These tools run on the provider's infrastructure (Anthropic, OpenAI, etc.),
    not locally. Examples: web search, code execution, image generation.

    Provider support varies - check pydantic-ai docs for compatibility.
    """

    tool_type: Literal["web_search", "code_execution", "image_generation", "url_context"] = Field(
        description="Type of server-side tool"
    )
    max_uses: Optional[int] = Field(
        default=None,
        description="Maximum number of times the tool can be used (web_search only, Anthropic)"
    )
    blocked_domains: Optional[List[str]] = Field(
        default=None,
        description="Domains to block (web_search only, mutually exclusive with allowed_domains for Anthropic)"
    )
    allowed_domains: Optional[List[str]] = Field(
        default=None,
        description="Only allow these domains (web_search only, mutually exclusive with blocked_domains for Anthropic)"
    )


class WorkerDefinition(BaseModel):
    """Persisted worker artifact."""

    name: str
    description: Optional[str] = None
    instructions: Optional[str] = None  # Acts as the worker's system prompt. Optional: can load from prompts/{name}.{txt,jinja2,j2,md}
    model: Optional[str] = None
    output_schema_ref: Optional[str] = None

    # Unified toolsets configuration (new format)
    toolsets: Optional[ToolsetsConfig] = Field(
        default=None,
        description="Configuration for all toolsets (sandbox, shell, delegation, custom)"
    )

    # Attachment policy (applies to worker_call delegation)
    attachment_policy: AttachmentPolicy = Field(default_factory=AttachmentPolicy)

    # Server-side tools (executed by LLM provider, not local toolsets)
    server_side_tools: List[ServerSideToolConfig] = Field(
        default_factory=list,
        description="Server-side tools executed by the LLM provider (web_search, code_execution, etc.)"
    )

    locked: bool = False

    model_config = ConfigDict(arbitrary_types_allowed=True)


class WorkerSpec(BaseModel):
    """Minimal LLM-facing worker description."""

    name: str
    instructions: str
    description: Optional[str] = None
    output_schema_ref: Optional[str] = None
    model: Optional[str] = None


class WorkerCreationDefaults(BaseModel):
    """Host-configured defaults used when persisting workers."""

    default_model: Optional[str] = None
    default_toolsets: Optional[ToolsetsConfig] = Field(
        default=None,
        description="Default toolsets configuration"
    )
    default_attachment_policy: AttachmentPolicy = Field(
        default_factory=AttachmentPolicy
    )

    model_config = ConfigDict(arbitrary_types_allowed=True)

    def expand_spec(self, spec: WorkerSpec) -> WorkerDefinition:
        """Apply defaults to a ``WorkerSpec`` to create a full definition."""

        attachment_policy = self.default_attachment_policy.model_copy()
        toolsets = self.default_toolsets.model_copy() if self.default_toolsets else None
        return WorkerDefinition(
            name=spec.name,
            description=spec.description,
            instructions=spec.instructions,
            model=spec.model or self.default_model,
            output_schema_ref=spec.output_schema_ref,
            toolsets=toolsets,
            attachment_policy=attachment_policy,
            locked=False,
        )


class WorkerRunResult(BaseModel):
    """Structured result from a worker execution."""

    output: Any
    messages: List[Any] = Field(default_factory=list)  # PydanticAI messages from agent run


# ---------------------------------------------------------------------------
# Type aliases and callbacks
# ---------------------------------------------------------------------------


OutputSchemaResolver = Callable[[WorkerDefinition], Optional[Type[BaseModel]]]

ModelLike = Union[str, PydanticAIModel]

MessageCallback = Callable[[List[Any]], None]


# ---------------------------------------------------------------------------
# Runtime context and data structures
# ---------------------------------------------------------------------------




@dataclass
class WorkerContext:
    """Runtime context passed to worker execution.

    This contains all the dependencies and state needed during worker execution,
    including registry, sandboxes, approvals, and callbacks.
    """
    registry: Any  # WorkerRegistry - avoid circular import
    worker: WorkerDefinition
    attachment_validator: Optional[AttachmentValidator]
    creation_defaults: WorkerCreationDefaults
    effective_model: Optional[ModelLike]
    approval_controller: Any  # ApprovalController - defined in tool_approval.py
    sandbox: Optional[AbstractToolset] = None  # None if worker doesn't use file I/O
    attachments: List[AttachmentPayload] = field(default_factory=list)
    message_callback: Optional[MessageCallback] = None
    custom_tools_path: Optional[Path] = None  # Path to tools.py if worker has custom tools

    def validate_attachments(
        self, attachment_specs: Optional[Sequence[AttachmentInput]]
    ) -> tuple[List[Path], List[Dict[str, Any]]]:
        """Resolve attachment specs to sandboxed files and enforce policy limits."""
        if self.attachment_validator is None:
            raise RuntimeError("Worker has no sandbox configured - cannot validate attachments for delegation")
        return self.attachment_validator.validate_attachments(
            attachment_specs, self.worker.attachment_policy
        )


@dataclass
class AgentExecutionContext:
    """Prepared context for agent execution (shared by sync and async runners)."""
    prompt: Union[str, List[Union[str, BinaryContent]]]
    agent_kwargs: Dict[str, Any]
    event_handler: Optional[Callable]
    model_label: Optional[str]
    started_at: Optional[float]
    emit_status: Optional[Callable[[str, Optional[float]], None]]


# ---------------------------------------------------------------------------
# Agent runner type
# ---------------------------------------------------------------------------


AgentRunner = Callable[[WorkerDefinition, Any, WorkerContext, Optional[Type[BaseModel]]], Any]
"""Type alias for the execution strategy used by ``run_worker``.

This interface allows swapping the underlying agent execution logic (e.g., for
unit testing or using a different agent framework) while keeping the
``run_worker`` orchestration logic (sandboxing, approvals, context) intact.
"""
