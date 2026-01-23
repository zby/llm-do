"""Agent loading: builds PydanticAI Agents from worker definitions."""

from __future__ import annotations

import inspect
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any, Iterable, Mapping, Sequence

from pydantic_ai import Agent, RunContext

from pydantic_ai.builtin_tools import (
    CodeExecutionTool,
    ImageGenerationTool,
    WebFetchTool,
    WebSearchTool,
)

from ..models import select_model
from ..toolsets.builtins import build_builtin_toolsets
from ..toolsets.loader import (
    ToolsetBuildContext,
    ToolsetSpec,
    resolve_toolset_specs,
)
from .args import PromptSpec, WorkerArgs, WorkerInput
from .schema_refs import resolve_schema_ref
from .worker_file import WorkerDefinition, load_worker_file

# Registry of server-side tool factories
_BUILTIN_TOOL_FACTORIES: dict[str, Any] = {
    "web_search": lambda cfg: WebSearchTool(
        max_uses=cfg.get("max_uses"),
        blocked_domains=cfg.get("blocked_domains"),
        allowed_domains=cfg.get("allowed_domains"),
    ),
    "web_fetch": lambda cfg: WebFetchTool(),
    "code_execution": lambda cfg: CodeExecutionTool(),
    "image_generation": lambda cfg: ImageGenerationTool(),
}


def _build_builtin_tools(configs: list[dict[str, Any]]) -> list[Any]:
    """Convert server-side tool configs to PydanticAI builtin tool instances."""
    tools: list[Any] = []
    for config in configs:
        tool_type = config.get("tool_type")
        if not tool_type:
            raise ValueError("server_side_tools entry must have 'tool_type'")
        factory = _BUILTIN_TOOL_FACTORIES.get(tool_type)
        if not factory:
            raise ValueError(
                f"Unknown tool_type: {tool_type}. "
                f"Supported: {', '.join(_BUILTIN_TOOL_FACTORIES.keys())}"
            )
        tools.append(factory(config))
    return tools

if TYPE_CHECKING:
    from .agent_runtime import AgentRuntime


@dataclass
class AgentBundle:
    """Bundle of loaded agents and their configurations."""

    agents: dict[str, Agent[Any, Any]]
    definitions: dict[str, WorkerDefinition]
    entry_name: str | None
    toolset_specs: dict[str, list[ToolsetSpec]]
    toolset_registry: dict[str, ToolsetSpec]
    schemas: dict[str, type[WorkerArgs]] = field(default_factory=dict)


def load_agents(
    worker_files: Sequence[str | Path],
    *,
    model_override: str | None = None,
    python_files: Sequence[str | Path] | None = None,
    project_root: Path | None = None,
    cwd: Path | None = None,
) -> AgentBundle:
    """Load worker files and build PydanticAI Agents.

    Args:
        worker_files: Paths to .worker files
        model_override: Override model for all agents
        python_files: Paths to Python files with custom toolsets
        project_root: Project root for toolset context
        cwd: Current working directory for toolset context

    Returns:
        AgentBundle with all loaded agents and configuration
    """
    definitions, worker_paths = _load_definitions(worker_files)
    toolset_registry = _build_toolset_registry(
        python_files=python_files,
        project_root=project_root,
        cwd=cwd,
    )
    schemas = _resolve_schemas(definitions, worker_paths=worker_paths)
    agents, toolset_specs = _build_agents(
        definitions,
        worker_names=set(definitions.keys()),
        toolset_registry=toolset_registry,
        schemas=schemas,
        model_override=model_override,
    )
    entry_name = _find_entry(definitions)

    return AgentBundle(
        agents=agents,
        definitions=definitions,
        entry_name=entry_name,
        toolset_specs=toolset_specs,
        toolset_registry=dict(toolset_registry),
        schemas=schemas,
    )


def _load_definitions(
    worker_files: Sequence[str | Path],
) -> tuple[dict[str, WorkerDefinition], dict[str, Path]]:
    """Load worker definitions from files."""
    definitions: dict[str, WorkerDefinition] = {}
    worker_paths: dict[str, Path] = {}
    for path in worker_files:
        resolved = Path(path).resolve()
        definition = load_worker_file(resolved)
        if definition.name in definitions:
            raise ValueError(f"Duplicate worker name: {definition.name}")
        definitions[definition.name] = definition
        worker_paths[definition.name] = resolved
    return definitions, worker_paths


def _build_agents(
    definitions: dict[str, WorkerDefinition],
    *,
    worker_names: set[str],
    toolset_registry: Mapping[str, ToolsetSpec],
    schemas: dict[str, type[WorkerArgs]],
    model_override: str | None,
) -> tuple[dict[str, Agent[Any, Any]], dict[str, list[ToolsetSpec]]]:
    """Build PydanticAI Agents from worker definitions."""
    from .agent_runtime import AgentRuntime

    agents: dict[str, Agent[Any, Any]] = {}
    toolset_specs: dict[str, list[ToolsetSpec]] = {}

    for name, definition in definitions.items():
        model_name = model_override or definition.model
        model = select_model(
            worker_model=model_name,
            compatible_models=definition.compatible_models,
            worker_name=name,
        )
        if model is None:
            raise ValueError(
                f"Worker '{name}' has no model. "
                "Provide model_override or set model in frontmatter."
            )

        specs, delegate_names = _resolve_toolsets(
            definition,
            worker_names,
            toolset_registry=toolset_registry,
        )
        builtin_tools = _build_builtin_tools(definition.server_side_tools)

        agent: Agent[AgentRuntime, str] = Agent(
            model=model,
            deps_type=AgentRuntime,
            instructions=definition.instructions,
            output_type=str,
            toolsets=[],
            builtin_tools=builtin_tools,
            end_strategy="exhaustive",
        )

        # Add delegation tools for each delegate
        for delegate_name in delegate_names:
            delegate_def = definitions[delegate_name]
            delegate_schema = schemas.get(delegate_name)
            delegate_model = model_override or delegate_def.model
            _add_delegate_tool(
                agent,
                delegate_name,
                delegate_def,
                delegate_schema,
                delegate_model,
            )

        agents[name] = agent
        toolset_specs[name] = specs

    return agents, toolset_specs


def _resolve_toolsets(
    definition: WorkerDefinition,
    worker_names: set[str],
    *,
    toolset_registry: Mapping[str, ToolsetSpec],
) -> tuple[list[ToolsetSpec], list[str]]:
    """Resolve toolset names to specs and identify delegate names."""
    delegate_names: list[str] = []
    toolset_names: list[str] = []

    for toolset_name in definition.toolsets:
        if toolset_name in worker_names:
            delegate_names.append(toolset_name)
        elif toolset_name in toolset_registry:
            toolset_names.append(toolset_name)
        else:
            raise ValueError(
                f"Unknown toolset '{toolset_name}' in worker '{definition.name}'. "
                f"Available: {sorted(toolset_registry.keys())}"
            )

    if not toolset_names:
        return [], delegate_names

    context = ToolsetBuildContext(
        worker_name=definition.name,
        available_toolsets=toolset_registry,
    )
    specs = resolve_toolset_specs(toolset_names, context)
    return specs, delegate_names


def _add_delegate_tool(
    agent: Agent[Any, Any],
    target_name: str,
    target_definition: WorkerDefinition,
    schema_in: type[WorkerArgs] | None,
    target_model: str | None,
) -> None:
    """Add a delegation tool to an agent."""
    from .agent_runtime import AgentRuntime

    description = target_definition.description or f"Delegate to {target_name}"

    if schema_in is not None:
        # Typed delegation with WorkerArgs schema
        async def typed_delegate(
            ctx: RunContext[AgentRuntime],
            args: Any,
        ) -> Any:
            if not isinstance(args, WorkerArgs):
                raise TypeError(
                    f"Expected WorkerArgs input for {target_name}, got {type(args)}"
                )
            prompt = _build_prompt_from_args(ctx, args, model_name=target_model)
            return await ctx.deps.call_agent(target_name, prompt, ctx=ctx)

        typed_delegate.__annotations__["args"] = schema_in
        agent.tool(name=target_name, description=description)(typed_delegate)
        return

    # Default delegation with input/attachments
    @agent.tool(name=target_name, description=description)
    async def delegate(
        ctx: RunContext[AgentRuntime],
        input: str,
        attachments: list[str] | None = None,
    ) -> Any:
        prompt = _build_prompt(ctx, input, attachments)
        return await ctx.deps.call_agent(target_name, prompt, ctx=ctx)


def _build_prompt(
    ctx: RunContext["AgentRuntime"],
    input_text: str,
    attachments: Iterable[str] | None,
) -> str | list[Any]:
    """Build a prompt from input text and attachments."""
    parts: list[Any] = []
    if input_text:
        parts.append(input_text)
    if attachments:
        for path in attachments:
            try:
                content = ctx.deps.load_binary(path)
            except Exception:
                parts.append(f"[Missing attachment: {path}]")
                continue
            parts.append(f"File {content.identifier} (source {path})")
            parts.append(content)

    if not parts:
        return input_text
    if len(parts) == 1 and isinstance(parts[0], str):
        return parts[0]
    return parts


def _build_prompt_from_args(
    ctx: RunContext["AgentRuntime"],
    args: WorkerArgs,
    *,
    model_name: str | None,
) -> str | list[Any]:
    """Build a prompt from WorkerArgs."""
    # Check for custom input_parts method
    renderer = getattr(args, "input_parts", None)
    if callable(renderer):
        parts = _call_input_parts(renderer, model_name)
        return _normalize_prompt_parts(parts)

    # Use default prompt_spec
    spec = args.prompt_spec()
    text = spec.text if spec.text.strip() else "(no input)"
    parts: list[Any] = [text]
    for path in spec.attachments:
        try:
            content = ctx.deps.load_binary(path)
        except Exception:
            parts.append(f"[Missing attachment: {path}]")
            continue
        parts.append(f"File {content.identifier} (source {path})")
        parts.append(content)
    return _normalize_prompt_parts(parts)


def _call_input_parts(renderer: Any, model_name: str | None) -> Any:
    """Call input_parts method with appropriate arguments."""
    signature = inspect.signature(renderer)
    if len(signature.parameters) == 0:
        return renderer()
    return renderer(model_name)


def _normalize_prompt_parts(parts: Any) -> str | list[Any]:
    """Normalize prompt parts to string or list."""
    if isinstance(parts, str):
        return parts
    if isinstance(parts, tuple):
        parts = list(parts)
    if isinstance(parts, list):
        if len(parts) == 1 and isinstance(parts[0], str):
            return parts[0]
        return parts
    return [parts]


def _build_toolset_registry(
    *,
    python_files: Sequence[str | Path] | None,
    project_root: Path | None,
    cwd: Path | None,
) -> dict[str, ToolsetSpec]:
    """Build the toolset registry from builtins and Python files."""
    from .discovery import load_toolsets_from_files

    cwd_path = (cwd or Path.cwd()).resolve()
    project_path = (project_root or cwd_path).resolve()
    registry: dict[str, ToolsetSpec] = {}
    registry.update(build_builtin_toolsets(cwd_path, project_path))
    if python_files:
        for name, toolset in load_toolsets_from_files(list(python_files)).items():
            if name in registry:
                raise ValueError(f"Duplicate toolset name: {name}")
            registry[name] = toolset
    return registry


def _resolve_schemas(
    definitions: Mapping[str, WorkerDefinition],
    *,
    worker_paths: Mapping[str, Path],
) -> dict[str, type[WorkerArgs]]:
    """Resolve schema references to WorkerArgs classes."""
    schemas: dict[str, type[WorkerArgs]] = {}
    for name, definition in definitions.items():
        if not definition.schema_in_ref:
            continue
        worker_path = worker_paths.get(name)
        base_path = worker_path.parent if worker_path is not None else None
        resolved = resolve_schema_ref(
            definition.schema_in_ref,
            base_path=base_path,
        )
        if not issubclass(resolved, WorkerArgs):
            raise TypeError(
                f"schema_in_ref for {name!r} must resolve to WorkerArgs subclass"
            )
        schemas[name] = resolved
    return schemas


def _find_entry(definitions: dict[str, WorkerDefinition]) -> str | None:
    """Find the entry point worker."""
    entries = [name for name, definition in definitions.items() if definition.entry]
    if not entries:
        return None
    if len(entries) > 1:
        raise ValueError(f"Multiple entry workers found: {sorted(entries)}")
    return entries[0]


def build_prompt_for_input(
    runtime: "AgentRuntime",
    input_data: Any,
    *,
    schema_in: type[WorkerArgs] | None = None,
) -> str | list[Any]:
    """Build a prompt from input data.

    Args:
        runtime: AgentRuntime for loading attachments
        input_data: Raw input data (dict or WorkerArgs)
        schema_in: Optional schema class for validation

    Returns:
        Prompt as string or list of parts
    """
    from .args import ensure_worker_args

    args = ensure_worker_args(schema_in, input_data)
    spec = args.prompt_spec()
    text = spec._normalized_text()

    if not spec.attachments:
        return text

    parts: list[Any] = [text]
    for path in spec.attachments:
        try:
            content = runtime.load_binary(path)
        except Exception:
            parts.append(f"[Missing attachment: {path}]")
            continue
        parts.append(f"File {content.identifier} (source {path})")
        parts.append(content)

    return parts
