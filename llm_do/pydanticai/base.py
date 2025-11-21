"""Foundational PydanticAI-style runtime for llm-do.

This module implements the initial slice described in
``docs/pydanticai_base_plan.md``. It provides:

- Worker artifacts (definition/spec/profile) with YAML/JSON persistence via
  ``WorkerRegistry``.
- Runtime orchestration through ``run_worker`` using a pluggable agent runner
  (LLM integration can be layered on later).
- Sandbox-aware filesystem helpers with optional approval gating.
- Simple worker delegation and creation hooks that honor allowlists and locks.

The design favors testability and deterministic enforcement so that a future
host can swap in real PydanticAI agents and approval UIs without changing the
core interfaces.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Mapping, Optional, Sequence, Type, Union

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator
from pydantic_ai import Agent
from pydantic_ai.models import Model as PydanticAIModel
from pydantic_ai.tools import RunContext


# ---------------------------------------------------------------------------
# Worker artifact models
# ---------------------------------------------------------------------------


class AttachmentPolicy(BaseModel):
    """Constraints for inbound attachments."""

    max_attachments: int = 4
    max_total_bytes: int = 10_000_000
    allowed_suffixes: List[str] = Field(default_factory=list)
    denied_suffixes: List[str] = Field(default_factory=list)

    @field_validator("max_attachments")
    @classmethod
    def _positive_max_attachments(cls, value: int) -> int:
        if value < 0:
            raise ValueError("max_attachments must be non-negative")
        return value

    @field_validator("max_total_bytes")
    @classmethod
    def _positive_max_total_bytes(cls, value: int) -> int:
        if value <= 0:
            raise ValueError("max_total_bytes must be positive")
        return value

    @field_validator("allowed_suffixes", "denied_suffixes")
    @classmethod
    def _lower_suffixes(cls, value: List[str]) -> List[str]:
        return [suffix.lower() for suffix in value]

    def validate_paths(self, attachments: Sequence[Path]) -> None:
        if len(attachments) > self.max_attachments:
            raise ValueError("Too many attachments provided")
        total = 0
        for path in attachments:
            suffix = path.suffix.lower()
            if self.allowed_suffixes and suffix not in self.allowed_suffixes:
                raise ValueError(f"Attachment suffix '{suffix}' not allowed")
            if self.denied_suffixes and suffix in self.denied_suffixes:
                raise ValueError(f"Attachment suffix '{suffix}' is denied")
            size = path.stat().st_size
            total += size
            if total > self.max_total_bytes:
                raise ValueError("Attachments exceed max_total_bytes")


class ToolRule(BaseModel):
    """Policy applied to a tool call."""

    name: str
    allowed: bool = True
    approval_required: bool = False
    description: Optional[str] = None


class SandboxConfig(BaseModel):
    """Configuration for a sandbox root."""

    name: str
    path: Path
    mode: str = Field(default="ro", description="ro or rw")
    allowed_suffixes: List[str] = Field(default_factory=list)
    max_bytes: int = 2_000_000

    model_config = ConfigDict(arbitrary_types_allowed=True)

    @field_validator("mode")
    @classmethod
    def _normalize_mode(cls, value: str) -> str:
        normalized = value.lower()
        if normalized not in {"ro", "rw"}:
            raise ValueError("Sandbox mode must be 'ro' or 'rw'")
        return normalized

    @field_validator("allowed_suffixes")
    @classmethod
    def _lower_suffixes(cls, value: List[str]) -> List[str]:
        return [suffix.lower() for suffix in value]


class WorkerDefinition(BaseModel):
    """Persisted worker artifact."""

    name: str
    description: Optional[str] = None
    instructions: str
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


class WorkerCreationProfile(BaseModel):
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


ApprovalCallback = Callable[[str, Mapping[str, Any], Optional[str]], ApprovalDecision]


def _auto_approve_callback(
    tool_name: str, payload: Mapping[str, Any], reason: Optional[str]
) -> ApprovalDecision:
    """Default callback that auto-approves all requests (for tests/non-interactive)."""
    return ApprovalDecision(approved=True)


def _strict_mode_callback(
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


# Public aliases for CLI use
approve_all_callback = _auto_approve_callback
strict_mode_callback = _strict_mode_callback


class WorkerRunResult(BaseModel):
    """Structured result from a worker execution."""

    output: Any


# ---------------------------------------------------------------------------
# Registry helpers
# ---------------------------------------------------------------------------


OutputSchemaResolver = Callable[[WorkerDefinition], Optional[Type[BaseModel]]]


def _default_resolver(definition: WorkerDefinition) -> Optional[Type[BaseModel]]:
    return None


ModelLike = Union[str, PydanticAIModel]


class WorkerRegistry:
    """File-backed registry for worker artifacts."""

    def __init__(
        self,
        root: Path,
        *,
        output_schema_resolver: OutputSchemaResolver = _default_resolver,
    ):
        self.root = Path(root).expanduser().resolve()
        self.output_schema_resolver = output_schema_resolver
        self.root.mkdir(parents=True, exist_ok=True)

    # paths -----------------------------------------------------------------
    def _definition_path(self, name: str) -> Path:
        base = Path(name)
        if base.suffix:
            return base if base.is_absolute() else (self.root / base)
        return self.root / f"{name}.yaml"

    def _load_raw(self, path: Path) -> Dict[str, Any]:
        suffix = path.suffix.lower()
        if suffix not in {".yaml", ".yml"}:
            raise ValueError(
                f"Worker definition must be .yaml or .yml, got: {suffix}"
            )
        content = path.read_text(encoding="utf-8")
        return yaml.safe_load(content) or {}

    def load_definition(self, name: str) -> WorkerDefinition:
        path = self._definition_path(name)
        if not path.exists():
            raise FileNotFoundError(f"Worker definition not found: {name}")
        data = self._load_raw(path)
        try:
            return WorkerDefinition.model_validate(data)
        except ValidationError as exc:
            raise ValueError(f"Invalid worker definition at {path}: {exc}") from exc

    def save_definition(
        self,
        definition: WorkerDefinition,
        *,
        force: bool = False,
        path: Optional[Path] = None,
    ) -> Path:
        target = path or self._definition_path(definition.name)
        if target.exists() and definition.locked and not force:
            raise PermissionError("Cannot overwrite locked worker without force=True")
        if target.exists() and not force:
            existing = self.load_definition(str(target))
            if existing.locked:
                raise PermissionError(
                    "Existing worker is locked; pass force=True to overwrite"
                )
        serialized = yaml.safe_dump(
            definition.model_dump(exclude_none=True, mode="json")
        )
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(serialized, encoding="utf-8")
        return target

    def resolve_output_schema(self, definition: WorkerDefinition) -> Optional[Type[BaseModel]]:
        return self.output_schema_resolver(definition)


# ---------------------------------------------------------------------------
# Sandbox + tools
# ---------------------------------------------------------------------------


@dataclass
class SandboxRoot:
    name: str
    path: Path
    read_only: bool
    allowed_suffixes: List[str]
    max_bytes: int

    def resolve(self, relative: str) -> Path:
        relative = relative.lstrip("/")
        candidate = (self.path / relative).resolve()
        try:
            candidate.relative_to(self.path)
        except ValueError as exc:
            raise PermissionError("Path escapes sandbox root") from exc
        return candidate


class SandboxManager:
    """Manage sandboxed filesystem access for a worker."""

    def __init__(self, sandboxes: Mapping[str, SandboxConfig]):
        self.sandboxes: Dict[str, SandboxRoot] = {}
        for name, cfg in sandboxes.items():
            root = Path(cfg.path).expanduser().resolve()
            root.mkdir(parents=True, exist_ok=True)
            self.sandboxes[name] = SandboxRoot(
                name=name,
                path=root,
                read_only=cfg.mode == "ro",
                allowed_suffixes=list(cfg.allowed_suffixes),
                max_bytes=cfg.max_bytes,
            )

    def _sandbox_for(self, sandbox: str) -> SandboxRoot:
        if sandbox not in self.sandboxes:
            raise KeyError(f"Unknown sandbox '{sandbox}'")
        return self.sandboxes[sandbox]

    def list_files(self, sandbox: str, pattern: str = "**/*") -> List[str]:
        root = self._sandbox_for(sandbox)
        matches: List[str] = []
        for path in root.path.glob(pattern):
            try:
                rel = path.relative_to(root.path)
            except ValueError:
                continue
            matches.append(str(rel))
        return sorted(matches)

    def read_text(self, sandbox: str, path: str, *, max_chars: int = 200_000) -> str:
        root = self._sandbox_for(sandbox)
        target = root.resolve(path)
        if not target.exists() or not target.is_file():
            raise FileNotFoundError(path)
        text = target.read_text(encoding="utf-8")
        if len(text) > max_chars:
            raise ValueError("File exceeds max_chars")
        return text

    def write_text(self, sandbox: str, path: str, content: str) -> str:
        root = self._sandbox_for(sandbox)
        if root.read_only:
            raise PermissionError("Sandbox is read-only")
        target = root.resolve(path)
        suffix = target.suffix.lower()
        if root.allowed_suffixes and suffix not in root.allowed_suffixes:
            raise PermissionError(f"Suffix '{suffix}' not allowed in sandbox '{sandbox}'")
        if len(content.encode("utf-8")) > root.max_bytes:
            raise ValueError("Content exceeds sandbox max_bytes")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        rel = target.relative_to(root.path)
        return f"wrote {len(content)} chars to {sandbox}:{rel}"


class ApprovalController:
    """Apply tool rules with blocking approval prompts."""

    def __init__(
        self,
        tool_rules: Mapping[str, ToolRule],
        *,
        approval_callback: ApprovalCallback = _auto_approve_callback,
    ):
        self.tool_rules = tool_rules
        self.approval_callback = approval_callback
        self.session_approvals: set[tuple[str, frozenset]] = set()

    def _make_approval_key(self, tool_name: str, payload: Mapping[str, Any]) -> tuple[str, frozenset]:
        """Create a hashable key for session approval tracking."""
        try:
            items = frozenset(payload.items())
        except TypeError:
            # If payload has unhashable values, use repr as fallback
            items = frozenset((k, repr(v)) for k, v in payload.items())
        return (tool_name, items)

    def maybe_run(
        self,
        tool_name: str,
        payload: Mapping[str, Any],
        func: Callable[[], Any],
    ) -> Any:
        rule = self.tool_rules.get(tool_name)
        if rule:
            if not rule.allowed:
                raise PermissionError(f"Tool '{tool_name}' is disallowed")
            if rule.approval_required:
                # Check session approvals
                key = self._make_approval_key(tool_name, payload)
                if key in self.session_approvals:
                    return func()

                # Block and wait for approval
                decision = self.approval_callback(tool_name, payload, rule.description)
                if not decision.approved:
                    note = f": {decision.note}" if decision.note else ""
                    raise PermissionError(f"User rejected tool call '{tool_name}'{note}")

                # Track session approval if requested
                if decision.approve_for_session:
                    self.session_approvals.add(key)

        return func()


class SandboxToolset:
    """Filesystem helpers exposed to agents."""

    def __init__(self, manager: SandboxManager, approvals: ApprovalController):
        self.manager = manager
        self.approvals = approvals

    def list(self, sandbox: str, pattern: str = "**/*") -> List[str]:
        return self.manager.list_files(sandbox, pattern)

    def read_text(self, sandbox: str, path: str, *, max_chars: int = 200_000) -> str:
        return self.manager.read_text(sandbox, path, max_chars=max_chars)

    def write_text(self, sandbox: str, path: str, content: str) -> Optional[str]:
        return self.approvals.maybe_run(
            "sandbox.write",
            {"sandbox": sandbox, "path": path},
            lambda: self.manager.write_text(sandbox, path, content),
        )


# ---------------------------------------------------------------------------
# Runtime context and operations
# ---------------------------------------------------------------------------


@dataclass
class WorkerContext:
    registry: WorkerRegistry
    worker: WorkerDefinition
    sandbox_manager: SandboxManager
    sandbox_toolset: SandboxToolset
    creation_profile: WorkerCreationProfile
    effective_model: Optional[ModelLike]
    approval_controller: ApprovalController
    attachments: List[Path] = field(default_factory=list)


AgentRunner = Callable[[WorkerDefinition, Any, WorkerContext, Optional[Type[BaseModel]]], Any]


def _format_user_prompt(user_input: Any) -> str:
    """Serialize user input into a prompt string for the agent."""

    if isinstance(user_input, str):
        return user_input
    return json.dumps(user_input, indent=2, sort_keys=True)


def _register_worker_tools(agent: Agent) -> None:
    """Expose built-in llm-do helpers as PydanticAI tools."""

    @agent.tool(name="sandbox_list", description="List files within a sandbox using a glob pattern")
    def sandbox_list(
        ctx: RunContext[WorkerContext],
        sandbox: str,
        pattern: str = "**/*",
    ) -> List[str]:
        return ctx.deps.sandbox_toolset.list(sandbox, pattern)

    @agent.tool(name="sandbox_read_text", description="Read UTF-8 text from a sandboxed file")
    def sandbox_read_text(
        ctx: RunContext[WorkerContext],
        sandbox: str,
        path: str,
        *,
        max_chars: int = 200_000,
    ) -> str:
        return ctx.deps.sandbox_toolset.read_text(sandbox, path, max_chars=max_chars)

    @agent.tool(name="sandbox_write_text", description="Write UTF-8 text to a sandboxed file")
    def sandbox_write_text(
        ctx: RunContext[WorkerContext],
        sandbox: str,
        path: str,
        content: str,
    ) -> Optional[str]:
        return ctx.deps.sandbox_toolset.write_text(sandbox, path, content)

    @agent.tool(name="worker_call", description="Delegate to another registered worker")
    def worker_call_tool(
        ctx: RunContext[WorkerContext],
        worker: str,
        input_data: Any = None,
        attachments: Optional[List[str]] = None,
    ) -> Any:
        return _worker_call_tool(
            ctx.deps,
            worker=worker,
            input_data=input_data,
            attachments=attachments,
        )

    @agent.tool(name="worker_create", description="Persist a new worker definition using the active profile")
    def worker_create_tool(
        ctx: RunContext[WorkerContext],
        name: str,
        instructions: str,
        description: Optional[str] = None,
        model: Optional[str] = None,
        output_schema_ref: Optional[str] = None,
        force: bool = False,
    ) -> Dict[str, Any]:
        return _worker_create_tool(
            ctx.deps,
            name=name,
            instructions=instructions,
            description=description,
            model=model,
            output_schema_ref=output_schema_ref,
            force=force,
        )


def _worker_call_tool(
    ctx: WorkerContext,
    *,
    worker: str,
    input_data: Any = None,
    attachments: Optional[List[str]] = None,
) -> Any:
    def _invoke() -> Any:
        resolved = [Path(path).expanduser().resolve() for path in attachments or []]
        result = call_worker(
            registry=ctx.registry,
            worker=worker,
            input_data=input_data,
            caller_context=ctx,
            attachments=resolved or None,
        )
        return result.output

    return ctx.approval_controller.maybe_run(
        "worker.call",
        {"worker": worker},
        _invoke,
    )


def _worker_create_tool(
    ctx: WorkerContext,
    *,
    name: str,
    instructions: str,
    description: Optional[str] = None,
    model: Optional[str] = None,
    output_schema_ref: Optional[str] = None,
    force: bool = False,
) -> Dict[str, Any]:
    spec = WorkerSpec(
        name=name,
        instructions=instructions,
        description=description,
        model=model,
        output_schema_ref=output_schema_ref,
    )

    def _invoke() -> Dict[str, Any]:
        created = create_worker(
            registry=ctx.registry,
            spec=spec,
            profile=ctx.creation_profile,
            force=force,
        )
        return created.model_dump(mode="json")

    return ctx.approval_controller.maybe_run(
        "worker.create",
        {"worker": name},
        _invoke,
    )


def _default_agent_runner(
    definition: WorkerDefinition,
    user_input: Any,
    context: WorkerContext,
    output_model: Optional[Type[BaseModel]],
) -> Any:
    """Execute a worker via a PydanticAI agent using the worker context."""

    if context.effective_model is None:
        raise ValueError(
            f"No model configured for worker '{definition.name}'. "
            "Set worker.model, pass --model, or provide a custom agent_runner."
        )

    agent_kwargs: Dict[str, Any] = dict(
        model=context.effective_model,
        instructions=definition.instructions,
        name=definition.name,
        deps_type=WorkerContext,
    )
    if output_model is not None:
        agent_kwargs["output_type"] = output_model

    agent = Agent(**agent_kwargs)
    _register_worker_tools(agent)

    prompt = _format_user_prompt(user_input)
    run_result = agent.run_sync(prompt, deps=context)
    return run_result.output


# worker delegation ---------------------------------------------------------

def call_worker(
    registry: WorkerRegistry,
    worker: str,
    input_data: Any,
    *,
    caller_context: WorkerContext,
    attachments: Optional[List[Path]] = None,
    agent_runner: AgentRunner = _default_agent_runner,
) -> WorkerRunResult:
    allowed = caller_context.worker.allow_workers
    if allowed and worker not in allowed:
        raise PermissionError(f"Delegation to '{worker}' is not allowed")
    return run_worker(
        registry=registry,
        worker=worker,
        input_data=input_data,
        caller_effective_model=caller_context.effective_model,
        attachments=attachments,
        creation_profile=caller_context.creation_profile,
        agent_runner=agent_runner,
    )


# worker creation -----------------------------------------------------------

def create_worker(
    registry: WorkerRegistry,
    spec: WorkerSpec,
    *,
    profile: WorkerCreationProfile,
    force: bool = False,
) -> WorkerDefinition:
    definition = profile.expand_spec(spec)
    registry.save_definition(definition, force=force)
    return definition


# run_worker ----------------------------------------------------------------

def run_worker(
    *,
    registry: WorkerRegistry,
    worker: str,
    input_data: Any,
    attachments: Optional[List[Path]] = None,
    caller_effective_model: Optional[ModelLike] = None,
    cli_model: Optional[ModelLike] = None,
    creation_profile: Optional[WorkerCreationProfile] = None,
    agent_runner: AgentRunner = _default_agent_runner,
    approval_callback: ApprovalCallback = _auto_approve_callback,
) -> WorkerRunResult:
    definition = registry.load_definition(worker)

    profile = creation_profile or WorkerCreationProfile()
    sandbox_manager = SandboxManager(definition.sandboxes or profile.default_sandboxes)

    attachment_policy = definition.attachment_policy
    attachment_list = [Path(path).expanduser().resolve() for path in attachments or []]
    attachment_policy.validate_paths(attachment_list)

    effective_model = definition.model or caller_effective_model or cli_model

    approvals = ApprovalController(definition.tool_rules, approval_callback=approval_callback)
    sandbox_tools = SandboxToolset(sandbox_manager, approvals)

    context = WorkerContext(
        registry=registry,
        worker=definition,
        sandbox_manager=sandbox_manager,
        sandbox_toolset=sandbox_tools,
        creation_profile=profile,
        effective_model=effective_model,
        attachments=attachment_list,
        approval_controller=approvals,
    )

    output_model = registry.resolve_output_schema(definition)

    # Real agent integration would expose toolsets to the model here. The base
    # implementation simply forwards to the agent runner with the constructed
    # context.
    raw_output = agent_runner(definition, input_data, context, output_model)

    if output_model is not None:
        output = output_model.model_validate(raw_output)
    else:
        output = raw_output

    return WorkerRunResult(output=output)


__all__: Iterable[str] = [
    "AgentRunner",
    "ApprovalCallback",
    "ApprovalController",
    "ApprovalDecision",
    "approve_all_callback",
    "strict_mode_callback",
    "AttachmentPolicy",
    "ToolRule",
    "SandboxConfig",
    "WorkerDefinition",
    "WorkerSpec",
    "WorkerCreationProfile",
    "WorkerRegistry",
    "WorkerRunResult",
    "run_worker",
    "call_worker",
    "create_worker",
    "SandboxManager",
    "SandboxToolset",
    "WorkerContext",
]
