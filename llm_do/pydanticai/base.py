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
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Mapping, Optional, Sequence, Type, Union

import yaml
from jinja2 import Environment, FileSystemLoader, TemplateNotFound, UndefinedError
from pydantic import BaseModel, ConfigDict, Field, ValidationError
from pydantic_ai import Agent
from pydantic_ai.messages import BinaryContent, UserContent
from pydantic_ai.models import Model as PydanticAIModel
from pydantic_ai.tools import RunContext

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


def _load_prompt_file(worker_name: str, prompts_dir: Path) -> tuple[str, bool]:
    """Load prompt by convention from prompts/ directory.

    Looks for prompts/{worker_name}.{txt,jinja2,j2,md} in order.

    Args:
        worker_name: Name of the worker
        prompts_dir: Path to prompts directory

    Returns:
        Tuple of (prompt_content, is_jinja_template)

    Raises:
        FileNotFoundError: If no prompt file found for worker
    """
    # Try extensions in order
    for ext, is_jinja in [
        (".jinja2", True),
        (".j2", True),
        (".txt", False),
        (".md", False),
    ]:
        prompt_file = prompts_dir / f"{worker_name}{ext}"
        if prompt_file.exists():
            content = prompt_file.read_text(encoding="utf-8")
            return (content, is_jinja)

    raise FileNotFoundError(
        f"No prompt file found for worker '{worker_name}' in {prompts_dir}. "
        f"Expected: {worker_name}.{{txt,jinja2,j2,md}}"
    )


def _render_jinja_template(template_str: str, template_root: Path) -> str:
    """Render a Jinja2 template with prompts/ directory as the base.

    Provides a `file(path)` function that loads files relative to template_root.
    Also supports standard {% include %} directive.

    Args:
        template_str: Jinja2 template string
        template_root: Root directory for template file loading (prompts/ directory)

    Returns:
        Rendered template string

    Raises:
        FileNotFoundError: If a referenced file doesn't exist
        PermissionError: If a file path escapes template root directory
        jinja2.TemplateError: If template syntax is invalid
    """

    # Set up Jinja2 environment with prompts/ as base
    env = Environment(
        loader=FileSystemLoader(template_root),
        autoescape=False,  # Don't escape - we want raw text
        keep_trailing_newline=True,
    )

    # Add custom file() function
    def load_file(path_str: str) -> str:
        """Load a file relative to template root."""
        file_path = (template_root / path_str).resolve()

        # Security: ensure resolved path doesn't escape template root
        try:
            file_path.relative_to(template_root)
        except ValueError:
            raise PermissionError(
                f"File path escapes allowed directory: {path_str}"
            )

        if not file_path.exists():
            raise FileNotFoundError(
                f"File not found: {path_str}"
            )

        return file_path.read_text(encoding="utf-8")

    # Make file() available in templates
    env.globals["file"] = load_file

    # Render the template
    try:
        template = env.from_string(template_str)
        return template.render()
    except (TemplateNotFound, UndefinedError) as exc:
        raise ValueError(f"Template error: {exc}") from exc


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

        # Check workers/ subdirectory by convention
        workers_path = self.root / "workers" / f"{name}.yaml"
        return workers_path

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

        # Determine project root: if worker is in workers/ subdirectory, go up one level
        # This allows both flat structure (worker.yaml, prompts/) and nested (workers/, prompts/)
        project_root = path.parent
        if project_root.name == "workers":
            project_root = project_root.parent

        prompts_dir = project_root / "prompts"

        if "instructions" not in data or data["instructions"] is None:
            # No inline instructions - discover from prompts/ directory
            if prompts_dir.exists():
                worker_name = data.get("name", name)
                prompt_content, is_jinja = _load_prompt_file(worker_name, prompts_dir)
                if is_jinja:
                    # Jinja2 root is prompts/ directory
                    data["instructions"] = _render_jinja_template(prompt_content, prompts_dir)
                else:
                    data["instructions"] = prompt_content
            # If no prompts/ directory exists and no inline instructions, let validation handle it
        elif isinstance(data["instructions"], str):
            # Inline instructions exist - check if they contain Jinja2 syntax and render
            # Simple heuristic: if contains {{ or {%, assume it's a template
            instructions_str = data["instructions"]
            if "{{" in instructions_str or "{%" in instructions_str:
                # Jinja2 root is prompts/ directory
                data["instructions"] = _render_jinja_template(instructions_str, prompts_dir)

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
class WorkerContext:
    registry: WorkerRegistry
    worker: WorkerDefinition
    sandbox_manager: SandboxManager
    sandbox_toolset: SandboxToolset
    creation_defaults: WorkerCreationDefaults
    effective_model: Optional[ModelLike]
    approval_controller: ApprovalController
    attachments: List[Path] = field(default_factory=list)
    message_callback: Optional[MessageCallback] = None


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
            defaults=ctx.creation_defaults,
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
) -> tuple[Any, List[Any]]:
    """Execute a worker via a PydanticAI agent using the worker context.

    Args:
        definition: Worker definition with instructions and configuration
        user_input: Input data for the worker
        context: Worker execution context with tools and dependencies (includes message_callback)
        output_model: Optional Pydantic model for structured output

    Returns:
        Tuple of (output, messages) where messages is the list of all messages
        exchanged with the LLM during execution.
    """

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

    # Build user prompt with attachments
    prompt_text = _format_user_prompt(user_input)

    if context.attachments:
        # Create a list of UserContent with text + file attachments
        # UserContent = str | BinaryContent | ImageUrl | AudioUrl | ...
        user_content: List[Union[str, BinaryContent]] = [prompt_text]
        for attachment_path in context.attachments:
            binary_content = BinaryContent.from_path(attachment_path)
            user_content.append(binary_content)
        prompt = user_content
    else:
        # Just text, no attachments
        prompt = prompt_text

    event_handler = None
    if context.message_callback:
        async def _stream_handler(
            run_ctx: RunContext[WorkerContext], event_stream
        ) -> None:  # pragma: no cover - exercised indirectly via integration tests
            async for event in event_stream:
                context.message_callback([{"worker": definition.name, "event": event}])

        event_handler = _stream_handler

    run_result = agent.run_sync(
        prompt,
        deps=context,
        event_stream_handler=event_handler,
    )

    # Extract all messages from the result
    messages = run_result.all_messages() if hasattr(run_result, 'all_messages') else []

    return (run_result.output, messages)


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
        creation_defaults=caller_context.creation_defaults,
        agent_runner=agent_runner,
        message_callback=caller_context.message_callback,
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
    creation_defaults: Optional[WorkerCreationDefaults] = None,
    agent_runner: AgentRunner = _default_agent_runner,
    approval_callback: ApprovalCallback = _auto_approve_callback,
    message_callback: Optional[MessageCallback] = None,
) -> WorkerRunResult:
    definition = registry.load_definition(worker)

    defaults = creation_defaults or WorkerCreationDefaults()
    sandbox_manager = SandboxManager(definition.sandboxes or defaults.default_sandboxes)

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
        creation_defaults=defaults,
        effective_model=effective_model,
        attachments=attachment_list,
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
    "call_worker",
    "create_worker",
    "SandboxManager",
    "SandboxToolset",
    "WorkerContext",
]
