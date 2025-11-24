"""Foundational PydanticAI-based runtime for llm-do.

This module provides:

- Worker artifacts (definition/spec/defaults) with YAML/JSON persistence via
  ``WorkerRegistry``.
- Runtime orchestration through ``run_worker`` using PydanticAI agents.
- Sandbox-aware filesystem helpers with optional approval gating.
- Worker delegation and creation tools that honor allowlists and locks.

The design favors testability and deterministic enforcement through pluggable
agent runners and approval callbacks.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from time import perf_counter
from typing import Any, Callable, Dict, Iterable, List, Mapping, Optional, Sequence, Type, Union

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError
from pydantic_ai import Agent
from pydantic_ai.messages import BinaryContent, UserContent
from pydantic_ai.models import Model as PydanticAIModel
from pydantic_ai.tools import RunContext

from . import prompts
from .sandbox import (
    AttachmentPolicy,
    SandboxConfig,
    SandboxManager,
    SandboxToolset,
)


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
    messages: List[Any] = Field(default_factory=list)  # PydanticAI messages from agent run


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
    def _get_search_paths(self, name: str) -> List[Path]:
        base = Path(name)
        if base.suffix:
            return [base if base.is_absolute() else (self.root / base)]

        candidates = [
            self.root / "workers" / f"{name}.yaml",
            self.root / "workers" / "generated" / f"{name}.yaml",
        ]
        
        # Add built-in path
        builtin_path = Path(__file__).parent / "workers" / f"{name}.yaml"
        candidates.append(builtin_path)
        
        return candidates

    def _definition_path(self, name: str) -> Path:
        # Legacy helper: return the first existing path, or the default user path
        paths = self._get_search_paths(name)
        for path in paths:
            if path.exists():
                return path
        return paths[0]  # Default to workers/{name}.yaml

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
            # _definition_path returns the first candidate if none exist,
            # but we want to be sure we checked all of them in the error message
            raise FileNotFoundError(f"Worker definition not found: {name}")
        data = self._load_raw(path)

        # Determine project root: workers stored under project/workers/** should inherit
        # the project root directory so prompts/ resolves correctly.
        project_root = path.parent
        resolved_path = path.resolve()
        user_workers_dir = (self.root / "workers").resolve()
        if resolved_path.is_relative_to(user_workers_dir):
            project_root = user_workers_dir.parent

        prompts_dir = project_root / "prompts"
        worker_name = data.get("name", name)

        resolved_instructions = prompts.resolve_worker_instructions(
            raw_instructions=data.get("instructions"),
            worker_name=worker_name,
            prompts_dir=prompts_dir,
        )

        if resolved_instructions is not None:
            data["instructions"] = resolved_instructions

        # Inject sandbox names from dictionary keys
        if "sandboxes" in data and isinstance(data["sandboxes"], dict):
            for sandbox_name, sandbox_config in data["sandboxes"].items():
                if isinstance(sandbox_config, dict) and "name" not in sandbox_config:
                    sandbox_config["name"] = sandbox_name

        # Inject tool rule names from dictionary keys
        if "tool_rules" in data and isinstance(data["tool_rules"], dict):
            for rule_name, rule_config in data["tool_rules"].items():
                if isinstance(rule_config, dict) and "name" not in rule_config:
                    rule_config["name"] = rule_name

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


# ---------------------------------------------------------------------------
# Runtime context and operations
# ---------------------------------------------------------------------------


MessageCallback = Callable[[List[Any]], None]


@dataclass
class AttachmentPayload:
    """Attachment path plus a display-friendly label."""

    path: Path
    display_name: str


AttachmentInput = Union[str, Path, AttachmentPayload]


@dataclass
class WorkerContext:
    registry: WorkerRegistry
    worker: WorkerDefinition
    sandbox_manager: SandboxManager
    sandbox_toolset: SandboxToolset
    creation_defaults: WorkerCreationDefaults
    effective_model: Optional[ModelLike]
    approval_controller: ApprovalController
    attachments: List[AttachmentPayload] = field(default_factory=list)
    message_callback: Optional[MessageCallback] = None

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


def _prepare_agent_execution(
    definition: WorkerDefinition,
    user_input: Any,
    context: WorkerContext,
    output_model: Optional[Type[BaseModel]],
) -> AgentExecutionContext:
    """Prepare everything needed for agent execution (sync or async).

    This extracts all the setup logic that's common between sync and async
    agent runners, including:
    - Building the prompt with attachments
    - Setting up streaming callbacks
    - Preparing agent kwargs
    - Initializing status tracking

    Args:
        definition: Worker definition with instructions and configuration
        user_input: Input data for the worker
        context: Worker execution context with tools and dependencies
        output_model: Optional Pydantic model for structured output

    Returns:
        AgentExecutionContext with all prepared state for agent execution
    """
    import sys

    if context.effective_model is None:
        raise ValueError(
            f"No model configured for worker '{definition.name}'. "
            "Set worker.model, pass --model, or provide a custom agent_runner."
        )

    # Build user prompt with attachments
    prompt_text = _format_user_prompt(user_input)
    attachment_labels = [item.display_name for item in context.attachments]

    if context.attachments:
        # Create a list of UserContent with text + file attachments
        print(f"DEBUG: Processing {len(context.attachments)} attachments", file=sys.stderr)
        sys.stderr.flush()
        user_content: List[Union[str, BinaryContent]] = [prompt_text]
        for i, attachment in enumerate(context.attachments):
            print(f"DEBUG:   Attachment {i}: path={attachment.path}, exists={attachment.path.exists()}, size={attachment.path.stat().st_size if attachment.path.exists() else 'N/A'}", file=sys.stderr)
            sys.stderr.flush()
            print(f"DEBUG:   Calling BinaryContent.from_path...", file=sys.stderr)
            sys.stderr.flush()
            binary_content = BinaryContent.from_path(attachment.path)
            print(f"DEBUG:   Created BinaryContent with media_type={binary_content.media_type}", file=sys.stderr)
            sys.stderr.flush()
            user_content.append(binary_content)
        print(f"DEBUG: All attachments processed, prompt list has {len(user_content)} items", file=sys.stderr)
        sys.stderr.flush()
        prompt = user_content
    else:
        # Just text, no attachments
        prompt = prompt_text

    # Setup callbacks and status tracking
    event_handler = None
    model_label: Optional[str] = None
    started_at: Optional[float] = None
    emit_status: Optional[Callable[[str, Optional[float]], None]] = None

    if context.message_callback:
        preview = {
            "instructions": definition.instructions or "",
            "user_input": prompt_text,
            "attachments": attachment_labels,
        }
        context.message_callback(
            [{"worker": definition.name, "initial_request": preview}]
        )

        def _emit_model_status(state: str, *, duration: Optional[float] = None) -> None:
            if not context.message_callback:
                return
            status: Dict[str, Any] = {
                "phase": "model_request",
                "state": state,
            }
            if model_label:
                status["model"] = model_label
            if duration is not None:
                status["duration_sec"] = duration
            context.message_callback(
                [{"worker": definition.name, "status": status}]
            )

        if _model_supports_streaming(context.effective_model):
            # Note: The stream handler must be thread-safe since it will be called
            # from within the agent's event loop
            async def _stream_handler(
                run_ctx: RunContext[WorkerContext], event_stream
            ) -> None:  # pragma: no cover - exercised indirectly via integration tests
                async for event in event_stream:
                    # Call message_callback in a thread-safe way
                    try:
                        context.message_callback(
                            [{"worker": definition.name, "event": event}]
                        )
                    except Exception as e:
                        # Log but don't crash on callback errors
                        print(f"DEBUG: Error in stream handler callback: {e}", file=sys.stderr)
                        sys.stderr.flush()

            event_handler = _stream_handler

        if isinstance(context.effective_model, str):
            model_label = context.effective_model
        elif context.effective_model is not None:
            model_label = (
                getattr(context.effective_model, "model_name", None)
                or context.effective_model.__class__.__name__
            )

        from time import perf_counter
        started_at = perf_counter()
        emit_status = _emit_model_status
        emit_status("start")

    # Prepare agent kwargs
    agent_kwargs: Dict[str, Any] = dict(
        model=context.effective_model,
        instructions=definition.instructions,
        name=definition.name,
        deps_type=WorkerContext,
    )
    if output_model is not None:
        agent_kwargs["output_type"] = output_model

    return AgentExecutionContext(
        prompt=prompt,
        agent_kwargs=agent_kwargs,
        event_handler=event_handler,
        model_label=model_label,
        started_at=started_at,
        emit_status=emit_status,
    )


AgentRunner = Callable[[WorkerDefinition, Any, WorkerContext, Optional[Type[BaseModel]]], Any]
"""Type alias for the execution strategy used by ``run_worker``.

This interface allows swapping the underlying agent execution logic (e.g., for
unit testing or using a different agent framework) while keeping the
``run_worker`` orchestration logic (sandboxing, approvals, context) intact.
"""


def _model_supports_streaming(model: ModelLike) -> bool:
    """Return True if the configured model supports streaming callbacks."""

    if isinstance(model, str):
        # Assume vendor-provided identifiers support streaming
        return True

    # When the caller passes a Model subclass, only opt into streaming if the
    # subclass overrides request_stream. Comparing attribute identity avoids
    # invoking the method (which could raise NotImplementedError).
    base_stream = getattr(PydanticAIModel, "request_stream", None)
    model_stream = getattr(type(model), "request_stream", None)
    if base_stream is None or model_stream is None:
        return False
    return model_stream is not base_stream


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

    @agent.tool(name="sandbox_read_text", description="Read UTF-8 text from a sandboxed file. Do not use this on binary files (PDFs, images, etc) - pass them as attachments instead.")
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
    async def worker_call_tool(
        ctx: RunContext[WorkerContext],
        worker: str,
        input_data: Any = None,
        attachments: Optional[List[str]] = None,
    ) -> Any:
        import sys
        print(f"DEBUG: worker_call_tool called for worker={worker}", file=sys.stderr)
        sys.stderr.flush()

        result = await _worker_call_tool_async(
            ctx.deps,
            worker=worker,
            input_data=input_data,
            attachments=attachments,
        )

        print(f"DEBUG: worker_call_tool completed for worker={worker}", file=sys.stderr)
        sys.stderr.flush()
        return result

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


async def _worker_call_tool_async(
    ctx: WorkerContext,
    *,
    worker: str,
    input_data: Any = None,
    attachments: Optional[List[str]] = None,
) -> Any:
    """Async version of worker call tool - calls call_worker_async to avoid hangs."""
    resolved_attachments: List[Path]
    attachment_metadata: List[Dict[str, Any]]
    if attachments:
        resolved_attachments, attachment_metadata = ctx.validate_attachments(attachments)
    else:
        resolved_attachments, attachment_metadata = ([], [])

    attachment_payloads: Optional[List[AttachmentPayload]] = None
    if resolved_attachments:
        attachment_payloads = [
            AttachmentPayload(
                path=path,
                display_name=f"{meta['sandbox']}/{meta['path']}",
            )
            for path, meta in zip(resolved_attachments, attachment_metadata)
        ]

    async def _invoke() -> Any:
        result = await call_worker_async(
            registry=ctx.registry,
            worker=worker,
            input_data=input_data,
            caller_context=ctx,
            attachments=attachment_payloads,
        )
        return result.output

    payload: Dict[str, Any] = {"worker": worker}
    if attachment_metadata:
        payload["attachments"] = attachment_metadata

    # Note: maybe_run is sync, but we need to await _invoke
    # For now, call maybe_run with an async wrapper
    import asyncio

    def _sync_wrapper() -> Any:
        return asyncio.create_task(_invoke())

    # Actually, we need to handle approval synchronously but execution asynchronously
    # Check approval first
    rule = ctx.approval_controller.tool_rules.get("worker.call")
    if rule:
        if not rule.allowed:
            raise PermissionError(f"Tool 'worker.call' is disallowed")
        if rule.approval_required:
            # Check session approvals
            key = ctx.approval_controller._make_approval_key("worker.call", payload)
            if key not in ctx.approval_controller.session_approvals:
                # Block and wait for approval
                decision = ctx.approval_controller.approval_callback("worker.call", payload, rule.description)
                if not decision.approved:
                    note = f": {decision.note}" if decision.note else ""
                    raise PermissionError(f"User rejected tool call 'worker.call'{note}")
                # Track session approval if requested
                if decision.approve_for_session:
                    ctx.approval_controller.session_approvals.add(key)

    # Now execute async
    return await _invoke()


def _worker_call_tool(
    ctx: WorkerContext,
    *,
    worker: str,
    input_data: Any = None,
    attachments: Optional[List[str]] = None,
) -> Any:
    """Sync version of worker call tool - kept for backward compatibility."""
    resolved_attachments: List[Path]
    attachment_metadata: List[Dict[str, Any]]
    if attachments:
        resolved_attachments, attachment_metadata = ctx.validate_attachments(attachments)
    else:
        resolved_attachments, attachment_metadata = ([], [])

    attachment_payloads: Optional[List[AttachmentPayload]] = None
    if resolved_attachments:
        attachment_payloads = [
            AttachmentPayload(
                path=path,
                display_name=f"{meta['sandbox']}/{meta['path']}",
            )
            for path, meta in zip(resolved_attachments, attachment_metadata)
        ]

    def _invoke() -> Any:
        result = call_worker(
            registry=ctx.registry,
            worker=worker,
            input_data=input_data,
            caller_context=ctx,
            attachments=attachment_payloads,
        )
        return result.output

    payload: Dict[str, Any] = {"worker": worker}
    if attachment_metadata:
        payload["attachments"] = attachment_metadata

    return ctx.approval_controller.maybe_run(
        "worker.call",
        payload,
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
            defaults=ctx.creation_defaults,
            force=force,
        )
        return created.model_dump(mode="json")

    return ctx.approval_controller.maybe_run(
        "worker.create",
        {"worker": name},
        _invoke,
    )


async def _default_agent_runner_async(
    definition: WorkerDefinition,
    user_input: Any,
    context: WorkerContext,
    output_model: Optional[Type[BaseModel]],
) -> tuple[Any, List[Any]]:
    """Async version of the default agent runner.

    This is the core async implementation that directly awaits agent.run().
    The sync version wraps this with asyncio.run().

    Args:
        definition: Worker definition with instructions and configuration
        user_input: Input data for the worker
        context: Worker execution context with tools and dependencies
        output_model: Optional Pydantic model for structured output

    Returns:
        Tuple of (output, messages) where messages is the list of all messages
        exchanged with the LLM during execution.
    """
    import sys

    # Prepare execution context (prompt, callbacks, agent kwargs)
    exec_ctx = _prepare_agent_execution(definition, user_input, context, output_model)

    # Debug logging
    print(f"DEBUG: About to call agent.run with prompt type: {type(exec_ctx.prompt)}", file=sys.stderr)
    if isinstance(exec_ctx.prompt, list):
        print(f"DEBUG: Prompt has {len(exec_ctx.prompt)} items", file=sys.stderr)
        for i, item in enumerate(exec_ctx.prompt):
            print(f"DEBUG:   Item {i}: {type(item).__name__}", file=sys.stderr)
    sys.stderr.flush()

    # Create Agent
    print(f"DEBUG: Creating Agent in async runner...", file=sys.stderr)
    sys.stderr.flush()

    agent = Agent(**exec_ctx.agent_kwargs)
    _register_worker_tools(agent)

    print(f"DEBUG: Agent created, calling agent.run()...", file=sys.stderr)
    sys.stderr.flush()

    # Run the agent asynchronously
    run_result = await agent.run(
        exec_ctx.prompt,
        deps=context,
        event_stream_handler=exec_ctx.event_handler,
    )

    print(f"DEBUG: agent.run() completed successfully", file=sys.stderr)
    sys.stderr.flush()

    if exec_ctx.emit_status is not None and exec_ctx.started_at is not None:
        from time import perf_counter
        exec_ctx.emit_status("end", duration=round(perf_counter() - exec_ctx.started_at, 2))

    # Extract all messages from the result
    messages = run_result.all_messages() if hasattr(run_result, 'all_messages') else []

    return (run_result.output, messages)


def _default_agent_runner(
    definition: WorkerDefinition,
    user_input: Any,
    context: WorkerContext,
    output_model: Optional[Type[BaseModel]],
) -> tuple[Any, List[Any]]:
    """Synchronous wrapper around the async agent runner.

    This provides backward compatibility for synchronous code that calls
    run_worker(). It simply wraps the async implementation with asyncio.run().

    Args:
        definition: Worker definition with instructions and configuration
        user_input: Input data for the worker
        context: Worker execution context with tools and dependencies
        output_model: Optional Pydantic model for structured output

    Returns:
        Tuple of (output, messages) where messages is the list of all messages
        exchanged with the LLM during execution.
    """
    import asyncio
    import sys

    print(f"DEBUG: Sync runner wrapping async runner with asyncio.run()", file=sys.stderr)
    sys.stderr.flush()

    # Simply wrap the async version with asyncio.run()
    return asyncio.run(
        _default_agent_runner_async(definition, user_input, context, output_model)
    )


# worker delegation ---------------------------------------------------------

def call_worker(
    registry: WorkerRegistry,
    worker: str,
    input_data: Any,
    *,
    caller_context: WorkerContext,
    attachments: Optional[Sequence[AttachmentInput]] = None,
    agent_runner: AgentRunner = _default_agent_runner,
    ) -> WorkerRunResult:
    allowed = caller_context.worker.allow_workers
    if allowed:
        allowed_set = set(allowed)
        if "*" not in allowed_set and worker not in allowed_set:
            raise PermissionError(f"Delegation to '{worker}' is not allowed")
    return run_worker(
        registry=registry,
        worker=worker,
        input_data=input_data,
        caller_effective_model=caller_context.effective_model,
        attachments=attachments,
        creation_defaults=caller_context.creation_defaults,
        agent_runner=agent_runner,
        message_callback=caller_context.message_callback,
    )


async def call_worker_async(
    registry: WorkerRegistry,
    worker: str,
    input_data: Any,
    *,
    caller_context: WorkerContext,
    attachments: Optional[Sequence[AttachmentInput]] = None,
    agent_runner: Optional[Callable] = None,
    ) -> WorkerRunResult:
    """Async version of call_worker for delegating to another worker.

    This is the key function that enables nested worker calls without hanging.
    By awaiting run_worker_async(), we stay within the same async context
    instead of creating conflicting event loops.

    Args:
        registry: Source for worker definitions.
        worker: Name of the worker to delegate to.
        input_data: Input payload for the delegated worker.
        caller_context: Context from the calling worker (for allowlist checks).
        attachments: Optional files to pass to the delegated worker.
        agent_runner: Optional async agent runner (defaults to async PydanticAI).

    Returns:
        WorkerRunResult from the delegated worker.
    """
    allowed = caller_context.worker.allow_workers
    if allowed:
        allowed_set = set(allowed)
        if "*" not in allowed_set and worker not in allowed_set:
            raise PermissionError(f"Delegation to '{worker}' is not allowed")
    return await run_worker_async(
        registry=registry,
        worker=worker,
        input_data=input_data,
        caller_effective_model=caller_context.effective_model,
        attachments=attachments,
        creation_defaults=caller_context.creation_defaults,
        agent_runner=agent_runner,
        message_callback=caller_context.message_callback,
        approval_callback=caller_context.approval_controller.approval_callback,
    )


# worker creation -----------------------------------------------------------

def create_worker(
    registry: WorkerRegistry,
    spec: WorkerSpec,
    *,
    defaults: WorkerCreationDefaults,
    force: bool = False,
) -> WorkerDefinition:
    definition = defaults.expand_spec(spec)
    
    # Default to workers/generated/ for new workers
    path = registry.root / "workers" / "generated" / f"{spec.name}.yaml"
    
    registry.save_definition(definition, force=force, path=path)
    return definition


# run_worker ----------------------------------------------------------------

async def run_worker_async(
    *,
    registry: WorkerRegistry,
    worker: str,
    input_data: Any,
    attachments: Optional[Sequence[AttachmentInput]] = None,
    caller_effective_model: Optional[ModelLike] = None,
    cli_model: Optional[ModelLike] = None,
    creation_defaults: Optional[WorkerCreationDefaults] = None,
    agent_runner: Optional[Callable] = None,
    approval_callback: ApprovalCallback = _auto_approve_callback,
    message_callback: Optional[MessageCallback] = None,
) -> WorkerRunResult:
    """Execute a worker by name (async version).

    This is the async entry point for running workers. It handles:
    1. Loading the worker definition.
    2. Setting up the runtime environment (sandboxes, tools, approvals).
    3. Creating the execution context.
    4. Awaiting the async agent runner.

    Args:
        registry: Source for worker definitions.
        worker: Name of the worker to run.
        input_data: Input payload for the worker.
        attachments: Optional files to expose to the worker.
        caller_effective_model: Inherited model from parent (used if worker has no model).
        cli_model: Fallback model from CLI (used if neither worker nor parent has a model).
        creation_defaults: Defaults for any new workers created during this run.
        agent_runner: Optional async strategy for executing the agent (defaults to async PydanticAI).
        approval_callback: Callback for tool approval requests.
        message_callback: Callback for streaming events and progress updates.

    Returns:
        WorkerRunResult containing the final output and message history.
    """
    definition = registry.load_definition(worker)

    defaults = creation_defaults or WorkerCreationDefaults()
    sandbox_manager = SandboxManager(definition.sandboxes or defaults.default_sandboxes)

    attachment_policy = definition.attachment_policy

    attachment_payloads: List[AttachmentPayload] = []
    if attachments:
        for item in attachments:
            if isinstance(item, AttachmentPayload):
                attachment_payloads.append(item)
                continue

            display_name = str(item)
            path = Path(item).expanduser().resolve()
            attachment_payloads.append(
                AttachmentPayload(path=path, display_name=display_name)
            )

    attachment_policy.validate_paths([payload.path for payload in attachment_payloads])

    effective_model = definition.model or caller_effective_model or cli_model

    approvals = ApprovalController(definition.tool_rules, approval_callback=approval_callback)
    sandbox_tools = SandboxToolset(sandbox_manager, approvals)

    context = WorkerContext(
        registry=registry,
        worker=definition,
        sandbox_manager=sandbox_manager,
        sandbox_toolset=sandbox_tools,
        creation_defaults=defaults,
        effective_model=effective_model,
        attachments=attachment_payloads,
        approval_controller=approvals,
        message_callback=message_callback,
    )

    output_model = registry.resolve_output_schema(definition)

    # Use the provided agent_runner or default to the async version
    if agent_runner is None:
        result = await _default_agent_runner_async(definition, input_data, context, output_model)
    else:
        # Support both sync and async agent runners
        import inspect
        if inspect.iscoroutinefunction(agent_runner):
            result = await agent_runner(definition, input_data, context, output_model)
        else:
            result = agent_runner(definition, input_data, context, output_model)

    # Handle both old-style (output only) and new-style (output, messages) returns
    if isinstance(result, tuple) and len(result) == 2:
        raw_output, messages = result
    else:
        raw_output = result
        messages = []

    if output_model is not None:
        output = output_model.model_validate(raw_output)
    else:
        output = raw_output

    return WorkerRunResult(output=output, messages=messages)


def run_worker(
    *,
    registry: WorkerRegistry,
    worker: str,
    input_data: Any,
    attachments: Optional[Sequence[AttachmentInput]] = None,
    caller_effective_model: Optional[ModelLike] = None,
    cli_model: Optional[ModelLike] = None,
    creation_defaults: Optional[WorkerCreationDefaults] = None,
    agent_runner: AgentRunner = _default_agent_runner,
    approval_callback: ApprovalCallback = _auto_approve_callback,
    message_callback: Optional[MessageCallback] = None,
) -> WorkerRunResult:
    """Execute a worker by name.

    This is the primary entry point for running workers. It handles:
    1. Loading the worker definition.
    2. Setting up the runtime environment (sandboxes, tools, approvals).
    3. Creating the execution context.
    4. Delegating the actual agent loop to the provided ``agent_runner``.

    Args:
        registry: Source for worker definitions.
        worker: Name of the worker to run.
        input_data: Input payload for the worker.
        attachments: Optional files to expose to the worker.
        caller_effective_model: Inherited model from parent (used if worker has no model).
        cli_model: Fallback model from CLI (used if neither worker nor parent has a model).
        creation_defaults: Defaults for any new workers created during this run.
        agent_runner: Strategy for executing the agent (defaults to PydanticAI).
        approval_callback: Callback for tool approval requests.
        message_callback: Callback for streaming events and progress updates.

    Returns:
        WorkerRunResult containing the final output and message history.
    """
    definition = registry.load_definition(worker)

    defaults = creation_defaults or WorkerCreationDefaults()
    sandbox_manager = SandboxManager(definition.sandboxes or defaults.default_sandboxes)

    attachment_policy = definition.attachment_policy

    attachment_payloads: List[AttachmentPayload] = []
    if attachments:
        for item in attachments:
            if isinstance(item, AttachmentPayload):
                attachment_payloads.append(item)
                continue

            display_name = str(item)
            path = Path(item).expanduser().resolve()
            attachment_payloads.append(
                AttachmentPayload(path=path, display_name=display_name)
            )

    attachment_policy.validate_paths([payload.path for payload in attachment_payloads])

    effective_model = definition.model or caller_effective_model or cli_model

    approvals = ApprovalController(definition.tool_rules, approval_callback=approval_callback)
    sandbox_tools = SandboxToolset(sandbox_manager, approvals)

    context = WorkerContext(
        registry=registry,
        worker=definition,
        sandbox_manager=sandbox_manager,
        sandbox_toolset=sandbox_tools,
        creation_defaults=defaults,
        effective_model=effective_model,
        attachments=attachment_payloads,
        approval_controller=approvals,
        message_callback=message_callback,
    )

    output_model = registry.resolve_output_schema(definition)

    # Real agent integration would expose toolsets to the model here. The base
    # implementation simply forwards to the agent runner with the constructed
    # context.
    result = agent_runner(definition, input_data, context, output_model)

    # Handle both old-style (output only) and new-style (output, messages) returns
    if isinstance(result, tuple) and len(result) == 2:
        raw_output, messages = result
    else:
        raw_output = result
        messages = []

    if output_model is not None:
        output = output_model.model_validate(raw_output)
    else:
        output = raw_output

    return WorkerRunResult(output=output, messages=messages)


__all__: Iterable[str] = [
    "AgentRunner",
    "AttachmentPayload",
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
    "WorkerCreationDefaults",
    "WorkerRegistry",
    "WorkerRunResult",
    "run_worker",
    "run_worker_async",
    "call_worker",
    "call_worker_async",
    "create_worker",
    "SandboxManager",
    "SandboxToolset",
    "WorkerContext",
]
