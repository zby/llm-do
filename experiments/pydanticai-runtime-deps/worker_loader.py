from __future__ import annotations

import inspect
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from pydantic_ai import Agent, RunContext
from runtime import AgentRuntime

from llm_do.runtime.args import Attachment, PromptMessages, WorkerArgs
from llm_do.runtime.discovery import load_toolsets_from_files
from llm_do.runtime.registry import _build_builtin_tools
from llm_do.runtime.schema_refs import resolve_schema_ref
from llm_do.runtime.worker_file import WorkerDefinition, load_worker_file
from llm_do.toolsets.builtins import build_builtin_toolsets
from llm_do.toolsets.loader import (
    ToolsetBuildContext,
    ToolsetSpec,
    resolve_toolset_specs,
)


@dataclass
class WorkerAgentBundle:
    agents: dict[str, Agent[Any, Any]]
    definitions: dict[str, WorkerDefinition]
    entry_name: str | None
    unsupported_toolsets: dict[str, list[str]]
    toolset_specs: dict[str, list[ToolsetSpec]]
    toolset_registry: dict[str, ToolsetSpec]


def load_worker_agents(
    worker_files: Sequence[str | Path],
    *,
    model_override: str | None = None,
    python_files: Sequence[str | Path] | None = None,
    project_root: Path | None = None,
    cwd: Path | None = None,
) -> WorkerAgentBundle:
    definitions, worker_paths = _load_definitions(worker_files)
    toolset_registry = _build_toolset_registry(
        python_files=python_files,
        project_root=project_root,
        cwd=cwd,
    )
    agents, unsupported, toolset_specs = _build_agents(
        definitions,
        worker_paths=worker_paths,
        toolset_registry=toolset_registry,
        model_override=model_override,
    )
    entry_name = _find_entry(definitions)
    return WorkerAgentBundle(
        agents=agents,
        definitions=definitions,
        entry_name=entry_name,
        unsupported_toolsets=unsupported,
        toolset_specs=toolset_specs,
        toolset_registry=dict(toolset_registry),
    )


def _load_definitions(
    worker_files: Sequence[str | Path],
) -> tuple[dict[str, WorkerDefinition], dict[str, Path]]:
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
    worker_paths: Mapping[str, Path],
    toolset_registry: Mapping[str, ToolsetSpec],
    model_override: str | None,
) -> tuple[
    dict[str, Agent[Any, Any]],
    dict[str, list[str]],
    dict[str, list[ToolsetSpec]],
]:
    agents: dict[str, Agent[Any, Any]] = {}
    unsupported: dict[str, list[str]] = {}
    toolset_specs: dict[str, list[ToolsetSpec]] = {}
    worker_names = set(definitions.keys())
    schema_map = _resolve_worker_schemas(definitions, worker_paths=worker_paths)
    for name, definition in definitions.items():
        model_name = model_override or definition.model
        if not model_name:
            raise ValueError(
                f"Worker '{name}' has no model. Provide model_override or set model in frontmatter."
            )
        specs, delegate_names, unsupported_toolsets = _resolve_toolsets(
            definition,
            worker_names,
            toolset_registry=toolset_registry,
        )
        builtin_tools = _build_builtin_tools(definition.server_side_tools)
        agent = Agent(
            model=model_name,
            deps_type=AgentRuntime,
            instructions=definition.instructions,
            output_type=str,
            toolsets=[],
            builtin_tools=builtin_tools,
        )
        agents[name] = agent
        toolset_specs[name] = specs
        for delegate_name in delegate_names:
            _add_delegate_tool(
                agent,
                delegate_name,
                definitions[delegate_name],
                schema_map.get(delegate_name),
                model_override or definitions[delegate_name].model,
            )
        if unsupported_toolsets:
            unsupported[name] = unsupported_toolsets
    return agents, unsupported, toolset_specs


def _resolve_toolsets(
    definition: WorkerDefinition,
    worker_names: set[str],
    *,
    toolset_registry: Mapping[str, ToolsetSpec],
) -> tuple[list[ToolsetSpec], list[str], list[str]]:
    delegate_names: list[str] = []
    unsupported: list[str] = []
    toolset_names: list[str] = []

    for toolset_name in definition.toolsets:
        if toolset_name in worker_names:
            delegate_names.append(toolset_name)
        elif toolset_name in toolset_registry:
            toolset_names.append(toolset_name)
        else:
            unsupported.append(toolset_name)

    if not toolset_names:
        return [], delegate_names, unsupported

    context = ToolsetBuildContext(
        worker_name=definition.name,
        available_toolsets=toolset_registry,
    )
    specs = resolve_toolset_specs(toolset_names, context)
    return specs, delegate_names, unsupported


def _add_delegate_tool(
    agent: Agent[Any, Any],
    target_name: str,
    target_definition: WorkerDefinition,
    schema_in: type[WorkerArgs] | None,
    target_model: str | None,
) -> None:
    description = target_definition.description
    if schema_in is not None:
        async def delegate_with_schema(
            ctx: RunContext[AgentRuntime],
            args: Any,
        ) -> Any:
            if not isinstance(args, WorkerArgs):
                raise TypeError(
                    f"Expected WorkerArgs input for {target_name}, got {type(args)}"
                )
            prompt = _build_prompt_from_worker_args(args, model_name=target_model)
            return await ctx.deps.call_agent(target_name, prompt, ctx=ctx)

        delegate_with_schema.__annotations__["args"] = schema_in
        agent.tool(name=target_name, description=description)(delegate_with_schema)
        return

    @agent.tool(name=target_name, description=description)
    async def delegate_simple(
        ctx: RunContext[AgentRuntime],
        input: str,
        attachments: list[str] | None = None,
    ) -> Any:
        prompt = _build_prompt(input, attachments)
        return await ctx.deps.call_agent(target_name, prompt, ctx=ctx)


def _build_prompt(
    input_text: str,
    attachments: Iterable[str] | None,
) -> PromptMessages:
    """Build a prompt message list from text and attachment paths.

    Uses lazy Attachment objects that will be resolved at render time.
    """
    parts: list[str | Attachment] = []
    if input_text:
        parts.append(input_text)
    if attachments:
        for path in attachments:
            parts.append(Attachment(path))
    if not parts:
        return [input_text] if input_text else []
    return parts


def _build_prompt_from_worker_args(
    args: WorkerArgs,
    *,
    model_name: str | None,
) -> PromptMessages:
    """Build a prompt message list from WorkerArgs.

    Uses the prompt_messages() method which returns lazy Attachment objects.
    """
    renderer = getattr(args, "input_parts", None)
    if callable(renderer):
        parts = _call_input_parts(renderer, model_name)
        return _normalize_prompt_parts(parts)

    # Use prompt_messages() which returns list[str | Attachment]
    return args.prompt_messages()


def _call_input_parts(renderer: Any, model_name: str | None) -> Any:
    signature = inspect.signature(renderer)
    if len(signature.parameters) == 0:
        return renderer()
    return renderer(model_name)


def _normalize_prompt_parts(parts: Any) -> PromptMessages:
    if isinstance(parts, str):
        return [parts]
    if isinstance(parts, tuple):
        parts = list(parts)
    if isinstance(parts, list):
        return parts
    return [parts]


def _build_toolset_registry(
    *,
    python_files: Sequence[str | Path] | None,
    project_root: Path | None,
    cwd: Path | None,
) -> dict[str, ToolsetSpec]:
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


def _resolve_worker_schemas(
    definitions: Mapping[str, WorkerDefinition],
    *,
    worker_paths: Mapping[str, Path],
) -> dict[str, type[WorkerArgs]]:
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
    entries = [name for name, definition in definitions.items() if definition.entry]
    if not entries:
        return None
    if len(entries) > 1:
        raise ValueError(f"Multiple entry workers found: {sorted(entries)}")
    return entries[0]
