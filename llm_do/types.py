"""Type definitions and data models for llm-do workers.

This module contains all the data models and type definitions used throughout
the llm-do system, including worker definitions, contexts, and results.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from typing import Any, Callable, Dict, List, Mapping, Optional, Sequence, Type, Union

from pydantic import BaseModel, ConfigDict, Field
from pydantic_ai.messages import BinaryContent
from pydantic_ai.models import Model as PydanticAIModel
from pydantic_ai.toolsets import AbstractToolset

from .sandbox import AttachmentInput, AttachmentPayload, AttachmentPolicy
from .tool_approval import ApprovalDecision
from .worker_sandbox import AttachmentValidator, SandboxConfig


# ---------------------------------------------------------------------------
# Worker artifact models
# ---------------------------------------------------------------------------


class ToolRule(BaseModel):
    """Policy applied to a tool call."""

    name: str
    allowed: bool = True
    approval_required: bool = False
    description: Optional[str] = None


# ---------------------------------------------------------------------------
# Shell tool types
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


class WorkerDefinition(BaseModel):
    """Persisted worker artifact."""

    name: str
    description: Optional[str] = None
    instructions: Optional[str] = None  # Acts as the worker's system prompt. Optional: can load from prompts/{name}.{txt,jinja2,j2,md}
    model: Optional[str] = None
    output_schema_ref: Optional[str] = None
    # Unified sandbox config
    sandbox: Optional[SandboxConfig] = Field(
        default=None,
        description="Unified sandbox configuration"
    )
    attachment_policy: AttachmentPolicy = Field(default_factory=AttachmentPolicy)
    allow_workers: List[str] = Field(default_factory=list)
    tool_rules: Dict[str, ToolRule] = Field(default_factory=dict)
    # Shell tool configuration
    shell_rules: List[ShellRule] = Field(
        default_factory=list,
        description="Pattern-based rules for shell command approval"
    )
    shell_default: Optional[ShellDefault] = Field(
        default=None,
        description="Default behavior for shell commands not matching any rule"
    )
    shell_cwd: Optional[str] = Field(
        default=None,
        description="Working directory for shell commands. Can be absolute or relative to registry root. None means registry root."
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
    # Unified sandbox config
    default_sandbox: Optional[SandboxConfig] = Field(
        default=None,
        description="Unified sandbox configuration"
    )
    default_attachment_policy: AttachmentPolicy = Field(
        default_factory=AttachmentPolicy
    )
    default_allow_workers: List[str] = Field(default_factory=list)
    default_tool_rules: Dict[str, ToolRule] = Field(default_factory=dict)

    model_config = ConfigDict(arbitrary_types_allowed=True)

    def expand_spec(self, spec: WorkerSpec) -> WorkerDefinition:
        """Apply defaults to a ``WorkerSpec`` to create a full definition."""

        attachment_policy = self.default_attachment_policy.model_copy()
        allow_workers = list(self.default_allow_workers)
        tool_rules = {name: rule.model_copy() for name, rule in self.default_tool_rules.items()}
        return WorkerDefinition(
            name=spec.name,
            description=spec.description,
            instructions=spec.instructions,
            model=spec.model or self.default_model,
            output_schema_ref=spec.output_schema_ref,
            sandbox=self.default_sandbox.model_copy() if self.default_sandbox else None,
            attachment_policy=attachment_policy,
            allow_workers=allow_workers,
            tool_rules=tool_rules,
            locked=False,
        )


class WorkerRunResult(BaseModel):
    """Structured result from a worker execution."""

    output: Any
    messages: List[Any] = Field(default_factory=list)  # PydanticAI messages from agent run


# ---------------------------------------------------------------------------
# Type aliases and callbacks
# ---------------------------------------------------------------------------


ApprovalCallback = Callable[[str, Mapping[str, Any], Optional[str]], ApprovalDecision]


def approve_all_callback(
    tool_name: str, payload: Mapping[str, Any], reason: Optional[str]
) -> ApprovalDecision:
    """Default callback that auto-approves all requests (for tests/non-interactive)."""
    return ApprovalDecision(approved=True)


def strict_mode_callback(
    tool_name: str, payload: Mapping[str, Any], reason: Optional[str]
) -> ApprovalDecision:
    """Callback that rejects all approval-required tools (strict/production mode).

    Use with --strict flag to ensure only pre-approved tools execute.
    Provides "deny by default" security posture.
    """
    return ApprovalDecision(
        approved=False,
        note=f"Strict mode: tool '{tool_name}' not pre-approved in worker config"
    )


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
    approval_controller: Any  # ApprovalController - defined in approval.py (for tool rules)
    sandbox_approval_controller: Any  # ApprovalController - defined in tool_approval.py (for filesystem)
    sandbox: Optional[AbstractToolset] = None  # None if worker doesn't use file I/O
    attachments: List[AttachmentPayload] = field(default_factory=list)
    message_callback: Optional[MessageCallback] = None
    custom_tools_path: Optional[Path] = None  # Path to tools.py if worker has custom tools
    shell_cwd: Optional[Path] = None  # Working directory for shell commands (overrides worker.shell_cwd)

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
