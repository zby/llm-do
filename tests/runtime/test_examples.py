"""Smoke tests for representative examples/ patterns."""
import os
from pathlib import Path
from typing import Any

import pytest
from pydantic_ai.messages import ModelMessage, ModelResponse, TextPart
from pydantic_ai.models.function import AgentInfo, FunctionModel

from llm_do.models import ModelCompatibilityError, register_model_factory
from llm_do.project import (
    build_registry,
    build_registry_host_wiring,
    load_agent_file,
    load_manifest,
    load_toolsets_from_files,
    resolve_entry,
    resolve_manifest_paths,
)
from llm_do.runtime import Runtime
from llm_do.toolsets.agent import AgentToolset
from llm_do.toolsets.dynamic_agents import DynamicAgentsToolset
from tests.runtime.helpers import build_runtime_context, materialize_toolset_def

EXAMPLES_DIR = Path(__file__).parent.parent.parent / "examples"
NON_STREAMING_PROVIDER = "testnostream_examples"


def _build_example(example_name: str):
    manifest, manifest_dir = load_manifest(EXAMPLES_DIR / example_name / "project.json")
    agent_paths, python_paths = resolve_manifest_paths(manifest, manifest_dir)
    registry = build_registry(
        [str(path) for path in agent_paths],
        [str(path) for path in python_paths],
        project_root=manifest_dir,
        **build_registry_host_wiring(manifest_dir),
    )
    entry = resolve_entry(
        manifest.entry,
        registry,
        python_files=python_paths,
        base_path=manifest_dir,
    )
    return entry, registry, manifest


def _register_non_streaming_provider() -> None:
    def respond(_messages: list[ModelMessage], _info: AgentInfo) -> ModelResponse:
        return ModelResponse(parts=[TextPart(content="non-streaming smoke response")])

    register_model_factory(
        NON_STREAMING_PROVIDER,
        lambda _model_name: FunctionModel(respond),
        replace=True,
    )


def _default_input(manifest_input: Any | None) -> dict[str, str] | Any:
    if manifest_input is None:
        return {"input": "smoke test input"}
    return manifest_input


@pytest.fixture
def non_streaming_provider_env() -> Any:
    _register_non_streaming_provider()
    previous = os.environ.get("LLM_DO_MODEL")
    os.environ["LLM_DO_MODEL"] = f"{NON_STREAMING_PROVIDER}:smoke"
    try:
        yield
    finally:
        if previous is None:
            os.environ.pop("LLM_DO_MODEL", None)
        else:
            os.environ["LLM_DO_MODEL"] = previous


@pytest.mark.anyio
@pytest.mark.parametrize(
    "manifest_path",
    sorted(EXAMPLES_DIR.glob("*/project.json")),
    ids=lambda path: path.parent.name,
)
async def test_all_examples_run_with_non_streaming_provider(
    manifest_path: Path,
    non_streaming_provider_env: Any,
) -> None:
    manifest, manifest_dir = load_manifest(manifest_path)
    agent_paths, python_paths = resolve_manifest_paths(manifest, manifest_dir)
    try:
        registry = build_registry(
            [str(path) for path in agent_paths],
            [str(path) for path in python_paths],
            project_root=manifest_dir,
            **build_registry_host_wiring(manifest_dir),
        )
        entry = resolve_entry(
            manifest.entry,
            registry,
            python_files=python_paths,
            base_path=manifest_dir,
        )
    except ModelCompatibilityError as exc:
        pytest.skip(f"example enforces model compatibility not matching non-streaming provider: {exc}")
    except ModuleNotFoundError as exc:
        pytest.skip(f"example requires optional dependency unavailable in test environment: {exc}")

    runtime = Runtime()
    runtime.register_registry(registry)

    result, _ctx = await runtime.run_entry(
        entry,
        _default_input(manifest.entry.args),
    )

    assert result is not None


@pytest.mark.anyio
async def test_single_worker_example_builds():
    worker_file = load_agent_file(EXAMPLES_DIR / "calculator" / "main.agent")
    assert "calc_tools" in worker_file.toolsets

    toolsets = load_toolsets_from_files([EXAMPLES_DIR / "calculator" / "tools.py"])
    assert "calc_tools" in toolsets

    entry, registry, _manifest = _build_example("calculator")
    agent = registry.agents[entry.name]
    assert len(agent.toolsets) == 1


@pytest.mark.anyio
async def test_delegation_example_builds():
    """Test pitchdeck_eval: static agent delegation pattern."""
    entry, registry, _manifest = _build_example("pitchdeck_eval")
    agent = registry.agents[entry.name]
    ctx = build_runtime_context(toolsets=[], model="test")
    toolsets = [
        await materialize_toolset_def(toolset_def, ctx)
        for toolset_def in agent.toolsets
    ]
    assert any(isinstance(toolset, AgentToolset) for toolset in toolsets)


@pytest.mark.anyio
async def test_bootstrapping_example_builds():
    """Test bootstrapping: dynamic agent creation pattern."""
    entry, registry, _manifest = _build_example("bootstrapping")
    agent = registry.agents[entry.name]
    ctx = build_runtime_context(toolsets=[], model="test")
    toolsets = [
        await materialize_toolset_def(toolset_def, ctx)
        for toolset_def in agent.toolsets
    ]
    assert any(isinstance(toolset, DynamicAgentsToolset) for toolset in toolsets)


@pytest.mark.anyio
async def test_code_entry_example_builds():
    entry, _registry, _manifest = _build_example("pitchdeck_eval_code_entry")
    assert entry.name


@pytest.mark.anyio
async def test_server_side_tools_example_builds():
    worker_file = load_agent_file(EXAMPLES_DIR / "web_searcher" / "main.agent")
    assert len(worker_file.server_side_tools) == 1
    assert worker_file.server_side_tools[0]["tool_type"] == "web_search"

    entry, registry, _manifest = _build_example("web_searcher")
    agent = registry.agents[entry.name]
    assert len(agent.builtin_tools) == 1


@pytest.mark.anyio
async def test_file_organizer_example_builds():
    """Test file_organizer: stabilizing pattern with semantic/mechanical separation."""
    worker_file = load_agent_file(EXAMPLES_DIR / "file_organizer" / "main.agent")
    assert "file_tools" in worker_file.toolsets
    assert "shell_file_ops" in worker_file.toolsets

    toolsets = load_toolsets_from_files([EXAMPLES_DIR / "file_organizer" / "tools.py"])
    assert "file_tools" in toolsets

    entry, registry, _manifest = _build_example("file_organizer")
    agent = registry.agents[entry.name]
    assert len(agent.toolsets) == 2  # file_tools + shell_file_ops


@pytest.mark.anyio
async def test_recursive_summarizer_example_builds():
    worker_file = load_agent_file(EXAMPLES_DIR / "recursive_summarizer" / "main.agent")
    assert "filesystem_project" in worker_file.toolsets
    assert "summarizer" in worker_file.toolsets

    entry, registry, _manifest = _build_example("recursive_summarizer")
    agent = registry.agents[entry.name]
    ctx = build_runtime_context(toolsets=[], model="test")
    toolsets = [
        await materialize_toolset_def(toolset_def, ctx)
        for toolset_def in agent.toolsets
    ]
    toolset_names = [
        toolset.spec.name for toolset in toolsets if isinstance(toolset, AgentToolset)
    ]
    assert "summarizer" in toolset_names
