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

from .sandbox import AttachmentPolicy, SandboxConfig, SandboxManager, SandboxToolset


# ---------------------------------------------------------------------------
# Worker artifact models
# ---------------------------------------------------------------------------


class ToolRule(BaseModel):
    """Policy applied to a tool call."""

    name: str
    allowed: bool = True
    approval_required: bool = False
    description: Optional[str] = None


class WorkerDefinition(BaseModel):
    """Persisted worker artifact."""

    name: str
    description: Optional[str] = None
    instructions: Optional[str] = None  # Optional: can load from prompts/{name}.{txt,jinja2,j2,md}
    model: Optional[str] = None
    output_schema_ref: Optional[str] = None
    sandboxes: Dict[str, SandboxConfig] = Field(default_factory=dict)
    attachment_policy: AttachmentPolicy = Field(default_factory=AttachmentPolicy)
    allow_workers: List[str] = Field(default_factory=list)
    tool_rules: Dict[str, ToolRule] = Field(default_factory=dict)
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
    default_sandboxes: Dict[str, SandboxConfig] = Field(default_factory=dict)
    default_attachment_policy: AttachmentPolicy = Field(
        default_factory=AttachmentPolicy
    )
    default_allow_workers: List[str] = Field(default_factory=list)
    default_tool_rules: Dict[str, ToolRule] = Field(default_factory=dict)

    model_config = ConfigDict(arbitrary_types_allowed=True)

    def expand_spec(self, spec: WorkerSpec) -> WorkerDefinition:
        """Apply defaults to a ``WorkerSpec`` to create a full definition."""

        sandboxes = {name: cfg.model_copy() for name, cfg in self.default_sandboxes.items()}
        attachment_policy = self.default_attachment_policy.model_copy()
        allow_workers = list(self.default_allow_workers)
        tool_rules = {name: rule.model_copy() for name, rule in self.default_tool_rules.items()}
        return WorkerDefinition(
            name=spec.name,
            description=spec.description,
            instructions=spec.instructions,
            model=spec.model or self.default_model,
            output_schema_ref=spec.output_schema_ref,
            sandboxes=sandboxes,
            attachment_policy=attachment_policy,
            allow_workers=allow_workers,
            tool_rules=tool_rules,
            locked=False,
        )


class ApprovalDecision(BaseModel):
    """Decision from an approval prompt."""

    approved: bool
    approve_for_session: bool = False
    note: Optional[str] = None


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
class AttachmentPayload:
    """Attachment path plus a display-friendly label."""

    path: Path
    display_name: str


AttachmentInput = Union[str, Path, AttachmentPayload]


@dataclass
class WorkerContext:
    """Runtime context passed to worker execution.

    This contains all the dependencies and state needed during worker execution,
    including registry, sandboxes, approvals, and callbacks.
    """
    registry: Any  # WorkerRegistry - avoid circular import
    worker: WorkerDefinition
    sandbox_manager: SandboxManager
    sandbox_toolset: SandboxToolset
    creation_defaults: WorkerCreationDefaults
    effective_model: Optional[ModelLike]
    approval_controller: Any  # ApprovalController - defined in runtime.py
    attachments: List[AttachmentPayload] = field(default_factory=list)
    message_callback: Optional[MessageCallback] = None
    custom_tools_path: Optional[Path] = None  # Path to tools.py if worker has custom tools

    def validate_attachments(
        self, attachment_specs: Optional[Sequence[Union[str, Path]]]
    ) -> tuple[List[Path], List[Dict[str, Any]]]:
        """Resolve attachment specs to sandboxed files and enforce policy limits."""

        if not attachment_specs:
            return ([], [])

        resolved: List[Path] = []
        metadata: List[Dict[str, Any]] = []
        for spec in attachment_specs:
            path, info = self._resolve_attachment_spec(spec)
            resolved.append(path)
            metadata.append(info)

        # Reuse the caller's attachment policy to keep delegation within limits
        self.worker.attachment_policy.validate_paths(resolved)
        return (resolved, metadata)

    def _resolve_attachment_spec(
        self, spec: Union[str, Path]
    ) -> tuple[Path, Dict[str, Any]]:
        value = str(spec).strip()
        if not value:
            raise ValueError("Attachment path cannot be empty")

        normalized = value.replace("\\", "/")
        if normalized.startswith("/") or normalized.startswith("~"):
            raise PermissionError("Attachments must reference a sandbox, not an absolute path")

        # Support "sandbox:path" style by converting to sandbox/relative.
        if ":" in normalized:
            prefix, suffix = normalized.split(":", 1)
            if prefix in self.sandbox_manager.sandboxes:
                normalized = f"{prefix}/{suffix.lstrip('/')}"

        path = PurePosixPath(normalized)
        parts = path.parts
        if not parts:
            raise ValueError("Attachment path must include a sandbox and file name")

        sandbox_name = parts[0]
        if sandbox_name in {".", ".."}:
            raise PermissionError("Attachments must reference a sandbox name")

        if sandbox_name not in self.sandbox_manager.sandboxes:
            raise KeyError(f"Unknown sandbox '{sandbox_name}' for attachment '{value}'")

        relative_parts = parts[1:]
        if not relative_parts:
            raise ValueError("Attachment path must include a file inside the sandbox")

        relative_path = PurePosixPath(*relative_parts).as_posix()
        sandbox_root = self.sandbox_manager.sandboxes[sandbox_name]
        target = sandbox_root.resolve(relative_path)
        if not target.exists():
            raise FileNotFoundError(f"Attachment not found: {value}")
        if not target.is_file():
            raise IsADirectoryError(f"Attachment must be a file: {value}")

        suffix = target.suffix.lower()
        attachment_suffixes = getattr(sandbox_root, "attachment_suffixes", [])
        if attachment_suffixes and suffix not in attachment_suffixes:
            raise PermissionError(
                f"Attachments from sandbox '{sandbox_name}' must use suffixes:"
                f" {', '.join(sorted(attachment_suffixes))}"
            )

        size = target.stat().st_size
        info = {"sandbox": sandbox_name, "path": relative_path, "bytes": size}
        return (target, info)


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
