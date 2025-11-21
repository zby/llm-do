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

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Mapping, Optional, Sequence, Type

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator


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
    kind: Optional[str] = Field(
        default=None, description="Optional category (e.g., evaluator, orchestrator)."
    )


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


class DeferredToolRequest(BaseModel):
    """Represents a tool call that requires approval."""

    tool_name: str
    payload: Mapping[str, Any]
    reason: Optional[str] = None


class WorkerRunResult(BaseModel):
    """Structured result from a worker execution."""

    output: Any
    deferred_requests: List[DeferredToolRequest] = Field(default_factory=list)
    usage: Dict[str, Any] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Registry helpers
# ---------------------------------------------------------------------------


OutputSchemaResolver = Callable[[WorkerDefinition], Optional[Type[BaseModel]]]


def _default_resolver(definition: WorkerDefinition) -> Optional[Type[BaseModel]]:
    return None


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
        content = path.read_text(encoding="utf-8")
        if path.suffix.lower() in {".yaml", ".yml"}:
            return yaml.safe_load(content) or {}
        return yaml.safe_load(content) if path.suffix.lower() == ".json" else {}

    def load_definition(self, name: str) -> WorkerDefinition:
        path = self._definition_path(name)
        if not path.exists():
            # try JSON fallback
            alt = path.with_suffix(".json")
            if alt.exists():
                path = alt
            else:
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
    """Apply tool rules and record deferred requests."""

    def __init__(self, tool_rules: Mapping[str, ToolRule], *, requests: List[DeferredToolRequest]):
        self.tool_rules = tool_rules
        self.requests = requests

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
                self.requests.append(
                    DeferredToolRequest(
                        tool_name=tool_name,
                        payload=dict(payload),
                        reason=rule.description,
                    )
                )
                return None
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
    effective_model: Optional[str]
    attachments: List[Path] = field(default_factory=list)
    caller_effective_model: Optional[str] = None


AgentRunner = Callable[[WorkerDefinition, Any, WorkerContext, Optional[Type[BaseModel]]], Any]


def _default_agent_runner(
    definition: WorkerDefinition,
    user_input: Any,
    context: WorkerContext,
    output_model: Optional[Type[BaseModel]],
) -> Any:
    """A placeholder agent runner for tests and bootstrapping.

    The runner simply echoes back the requested input and worker name. Real
    integrations should replace this with a PydanticAI Agent invocation.
    """

    payload = {
        "worker": definition.name,
        "input": user_input,
        "model": context.effective_model,
    }
    if output_model:
        return output_model.model_validate(payload)
    return payload


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
    caller_effective_model: Optional[str] = None,
    cli_model: Optional[str] = None,
    creation_profile: Optional[WorkerCreationProfile] = None,
    agent_runner: AgentRunner = _default_agent_runner,
) -> WorkerRunResult:
    definition = registry.load_definition(worker)

    profile = creation_profile or WorkerCreationProfile()
    sandbox_manager = SandboxManager(definition.sandboxes or profile.default_sandboxes)

    attachment_policy = definition.attachment_policy
    attachment_list = [Path(path).expanduser().resolve() for path in attachments or []]
    attachment_policy.validate_paths(attachment_list)

    effective_model = definition.model or caller_effective_model or cli_model

    deferred: List[DeferredToolRequest] = []
    approvals = ApprovalController(definition.tool_rules, requests=deferred)
    sandbox_tools = SandboxToolset(sandbox_manager, approvals)

    context = WorkerContext(
        registry=registry,
        worker=definition,
        sandbox_manager=sandbox_manager,
        sandbox_toolset=sandbox_tools,
        creation_profile=profile,
        effective_model=effective_model,
        attachments=attachment_list,
        caller_effective_model=caller_effective_model,
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

    return WorkerRunResult(output=output, deferred_requests=deferred, usage={})


__all__: Iterable[str] = [
    "AgentRunner",
    "ApprovalController",
    "AttachmentPolicy",
    "ToolRule",
    "SandboxConfig",
    "WorkerDefinition",
    "WorkerSpec",
    "WorkerCreationProfile",
    "WorkerRegistry",
    "WorkerRunResult",
    "DeferredToolRequest",
    "run_worker",
    "call_worker",
    "create_worker",
    "SandboxManager",
    "SandboxToolset",
    "WorkerContext",
]
