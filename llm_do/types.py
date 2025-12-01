"""Type definitions and data models for llm-do workers.

This module contains all the data models and type definitions used throughout
the llm-do system, including worker definitions, contexts, and results.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from typing import Any, Callable, Dict, List, Literal, Optional, Sequence, Type, Union

from pydantic import BaseModel, ConfigDict, Field, model_validator
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
        description="File sandbox configuration (read_file, write_file, etc.)"
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

    # Legacy fields for backward compatibility - these are migrated to toolsets
    sandbox_legacy: Optional[SandboxConfig] = Field(default=None, alias="sandbox", exclude=True)
    shell_rules_legacy: List["ShellRule"] = Field(default_factory=list, alias="shell_rules", exclude=True)
    shell_default_legacy: Optional["ShellDefault"] = Field(default=None, alias="shell_default", exclude=True)
    allow_workers_legacy: List[str] = Field(default_factory=list, alias="allow_workers", exclude=True)
    custom_tools_legacy: List[str] = Field(default_factory=list, alias="custom_tools", exclude=True)

    # Attachment policy (applies to worker_call delegation)
    attachment_policy: AttachmentPolicy = Field(default_factory=AttachmentPolicy)

    # Server-side tools (executed by LLM provider, not local toolsets)
    server_side_tools: List[ServerSideToolConfig] = Field(
        default_factory=list,
        description="Server-side tools executed by the LLM provider (web_search, code_execution, etc.)"
    )

    locked: bool = False

    model_config = ConfigDict(arbitrary_types_allowed=True, populate_by_name=True)

    @model_validator(mode="after")
    def migrate_legacy_fields_to_toolsets(self) -> "WorkerDefinition":
        """Migrate legacy top-level fields to the new toolsets structure."""
        # If toolsets is already set, use it
        if object.__getattribute__(self, "toolsets") is not None:
            return self

        # Access legacy fields directly (bypass property overrides)
        model_fields = object.__getattribute__(self, "__dict__")

        sandbox_val = model_fields.get("sandbox_legacy")
        shell_rules_val = model_fields.get("shell_rules_legacy", [])
        shell_default_val = model_fields.get("shell_default_legacy")
        allow_workers_val = model_fields.get("allow_workers_legacy", [])
        custom_tools_val = model_fields.get("custom_tools_legacy", [])

        # Check if any legacy fields are set
        has_legacy = any([
            sandbox_val is not None,
            len(shell_rules_val) > 0,
            shell_default_val is not None,
            len(allow_workers_val) > 0,
            len(custom_tools_val) > 0,
        ])

        if not has_legacy:
            return self

        # Migrate legacy fields to new toolsets structure
        toolsets_dict: Dict[str, Any] = {}

        if sandbox_val is not None:
            toolsets_dict["sandbox"] = sandbox_val

        if shell_rules_val or shell_default_val:
            toolsets_dict["shell"] = ShellToolsetConfig(
                rules=shell_rules_val,
                default=shell_default_val,
            )

        if allow_workers_val:
            toolsets_dict["delegation"] = DelegationToolsetConfig(
                allow_workers=allow_workers_val
            )

        if custom_tools_val:
            # Convert list of tool names to dict with default config
            toolsets_dict["custom"] = {
                name: CustomToolConfig() for name in custom_tools_val
            }

        if toolsets_dict:
            object.__setattr__(self, "toolsets", ToolsetsConfig(**toolsets_dict))

        return self

    @property
    def sandbox(self) -> Optional[SandboxConfig]:
        """Get sandbox config from toolsets."""
        if self.toolsets:
            return self.toolsets.sandbox
        return None

    @property
    def shell_rules(self) -> List[ShellRule]:
        """Get shell rules from toolsets."""
        if self.toolsets and self.toolsets.shell:
            return self.toolsets.shell.rules
        return []

    @property
    def shell_default(self) -> Optional[ShellDefault]:
        """Get shell default from toolsets."""
        if self.toolsets and self.toolsets.shell:
            return self.toolsets.shell.default
        return None

    @property
    def allow_workers(self) -> List[str]:
        """Get allow_workers from toolsets."""
        if self.toolsets and self.toolsets.delegation:
            return self.toolsets.delegation.allow_workers
        return []

    @property
    def custom_tools(self) -> Dict[str, CustomToolConfig]:
        """Get custom tools config from toolsets."""
        if self.toolsets and self.toolsets.custom:
            return self.toolsets.custom
        return {}


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

    # Legacy fields for backward compatibility
    default_sandbox_legacy: Optional[SandboxConfig] = Field(default=None, alias="default_sandbox", exclude=True)
    default_allow_workers_legacy: List[str] = Field(default_factory=list, alias="default_allow_workers", exclude=True)
    default_custom_tools_legacy: List[str] = Field(default_factory=list, alias="default_custom_tools", exclude=True)

    model_config = ConfigDict(arbitrary_types_allowed=True, populate_by_name=True)

    @model_validator(mode="after")
    def migrate_legacy_defaults_to_toolsets(self) -> "WorkerCreationDefaults":
        """Migrate legacy default fields to the new toolsets structure."""
        if self.default_toolsets is not None:
            return self

        model_fields = object.__getattribute__(self, "__dict__")
        sandbox_val = model_fields.get("default_sandbox_legacy")
        allow_workers_val = model_fields.get("default_allow_workers_legacy", [])
        custom_tools_val = model_fields.get("default_custom_tools_legacy", [])

        has_legacy = any([
            sandbox_val is not None,
            len(allow_workers_val) > 0,
            len(custom_tools_val) > 0,
        ])

        if not has_legacy:
            return self

        toolsets_dict: Dict[str, Any] = {}

        if sandbox_val is not None:
            toolsets_dict["sandbox"] = sandbox_val

        if allow_workers_val:
            toolsets_dict["delegation"] = DelegationToolsetConfig(
                allow_workers=allow_workers_val
            )

        if custom_tools_val:
            toolsets_dict["custom"] = {
                name: CustomToolConfig() for name in custom_tools_val
            }

        if toolsets_dict:
            object.__setattr__(self, "default_toolsets", ToolsetsConfig(**toolsets_dict))

        return self

    @property
    def default_sandbox(self) -> Optional[SandboxConfig]:
        """Get default sandbox from toolsets."""
        if self.default_toolsets:
            return self.default_toolsets.sandbox
        return None

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
