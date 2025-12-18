import json
from typing import Any

import pytest
from pydantic import BaseModel
from pydantic_ai.messages import BinaryContent, ModelRequest, ModelResponse, TextPart
from pydantic_ai.models import Model

from llm_do import (
    ApprovalController,
    ApprovalDecision,
    WorkerContext,
    WorkerCreationDefaults,
    WorkerDefinition,
    WorkerRegistry,
    WorkerSpec,
    call_worker,
    create_worker,
    run_worker,
)
from pydantic_ai_blocking_approval import ApprovalRequest


class EchoPayload(BaseModel):
    worker: str
    input: object
    model: str | None


class RecordingModel(Model):
    def __init__(self):
        super().__init__()
        self.tool_names: list[str] = []
        self.last_prompt: str | None = None
        self.last_instructions: str | None = None

    @property
    def model_name(self) -> str:
        return "recording"

    @property
    def system(self) -> str:
        return "test"

    async def request(self, messages, model_settings, model_request_parameters):
        self.tool_names = [tool.name for tool in model_request_parameters.function_tools]
        prompt = None
        instructions = None
        for message in reversed(messages):
            if isinstance(message, ModelRequest):
                instructions = message.instructions
                parts: list[str] = []
                for part in message.parts:
                    content = getattr(part, "content", None)
                    if content is None:
                        continue
                    if isinstance(content, str):
                        parts.append(content)
                    else:
                        parts.append(str(content))
                prompt = "\n\n".join(parts)
                break
        self.last_prompt = prompt or ""
        self.last_instructions = instructions
        payload = json.dumps({"prompt": self.last_prompt, "instructions": self.last_instructions})
        return ModelResponse(parts=[TextPart(content=payload)], model_name=self.model_name)


@pytest.fixture
def resolver():
    def _resolve(definition: WorkerDefinition):
        if definition.output_schema_ref == "EchoPayload":
            return EchoPayload
        return None

    return _resolve


def _project_root(tmp_path):
    root = tmp_path / "project"
    root.mkdir(parents=True, exist_ok=True)
    return root


@pytest.fixture
def registry(tmp_path, resolver):
    root = _project_root(tmp_path)
    # Use test-specific generated dir (not global /tmp/llm-do/generated)
    generated_dir = tmp_path / "generated"
    generated_dir.mkdir()
    return WorkerRegistry(root, output_schema_resolver=resolver, generated_dir=generated_dir)


def test_registry_respects_locked_flag(registry):
    definition = WorkerDefinition(name="alpha", instructions="do things", locked=True)
    registry.save_definition(definition)

    updated = definition.model_copy(update={"instructions": "new"})
    with pytest.raises(PermissionError):
        registry.save_definition(updated)

    registry.save_definition(updated, force=True)


def test_run_worker_applies_model_inheritance(registry):
    definition = WorkerDefinition(
        name="alpha",
        instructions="",
        output_schema_ref="EchoPayload",
    )
    registry.save_definition(definition)

    result = run_worker(
        registry=registry,
        worker="alpha",
        input_data={"task": "demo"},
        cli_model="cli-model",
        agent_runner=lambda d, i, ctx, model: {
            "worker": d.name,
            "input": i,
            "model": ctx.effective_model,
        },
    )

    assert result.output.model == "cli-model"
    assert result.output.worker == "alpha"


def test_run_worker_message_callback_invoked(registry):
    definition = WorkerDefinition(name="alpha", instructions="")
    registry.save_definition(definition)

    seen: list[Any] = []

    def callback(events):
        seen.extend(events)

    def runner(defn, input_data, ctx, output_model):
        assert ctx.message_callback is callback
        ctx.message_callback([{"worker": defn.name, "event": "chunk"}])
        return ("done", [])

    run_worker(
        registry=registry,
        worker="alpha",
        input_data="hi",
        cli_model="mock",
        agent_runner=runner,
        message_callback=callback,
    )

    assert seen == [{"worker": "alpha", "event": "chunk"}]




def test_create_worker_applies_creation_defaults(registry, tmp_path):
    defaults = WorkerCreationDefaults(
        default_model="gpt-4",
    )
    spec = WorkerSpec(name="beta", instructions="collect data")

    created = create_worker(registry, spec, defaults=defaults)

    assert created.model == "gpt-4"
    loaded = registry.load_definition("beta")
    # Generated workers are directories: {name}/worker.worker
    generated_path = registry.generated_dir / "beta" / "worker.worker"
    assert generated_path.exists()


def test_create_worker_writes_definition_to_generated_dir(registry):
    defaults = WorkerCreationDefaults()
    spec = WorkerSpec(name="gamma", instructions="demo")

    create_worker(registry, spec, defaults=defaults)

    # Generated workers are directories: {name}/worker.worker
    generated_path = registry.generated_dir / "gamma" / "worker.worker"
    assert generated_path.exists()
    definition = registry.load_definition("gamma")
    assert definition.instructions == "demo"


def test_registry_prefers_project_workers_over_generated(tmp_path, resolver):
    """Project workers take precedence over generated workers (when registered)."""
    root = _project_root(tmp_path)
    generated_dir = tmp_path / "generated"
    generated_dir.mkdir()
    registry = WorkerRegistry(root, output_schema_resolver=resolver, generated_dir=generated_dir)

    # Create generated worker (directory form) and register it
    (generated_dir / "foo").mkdir()
    (generated_dir / "foo" / "worker.worker").write_text(
        "---\nname: foo\n---\ngenerated",
        encoding="utf-8",
    )
    registry.register_generated("foo")

    # Create project worker (higher priority)
    project_dir = root / "workers"
    project_dir.mkdir(exist_ok=True)
    (project_dir / "foo.worker").write_text(
        "---\nname: foo\n---\nproject",
        encoding="utf-8",
    )

    definition = registry.load_definition("foo")
    assert definition.instructions == "project"


def test_registry_loads_generated_worker_when_registered(tmp_path, resolver):
    """Generated workers are only findable when registered in session."""
    root = _project_root(tmp_path)
    generated_dir = tmp_path / "generated"
    generated_dir.mkdir()
    registry = WorkerRegistry(root, output_schema_resolver=resolver, generated_dir=generated_dir)

    # Create generated worker (directory form)
    (generated_dir / "foo").mkdir()
    (generated_dir / "foo" / "worker.worker").write_text(
        "---\nname: foo\n---\ngenerated",
        encoding="utf-8",
    )

    # Not registered - should not be findable
    with pytest.raises(FileNotFoundError):
        registry.load_definition("foo")

    # Register it - now findable
    registry.register_generated("foo")
    definition = registry.load_definition("foo")
    assert definition.instructions == "generated"


def test_registry_loads_built_in_worker_when_not_found_locally(tmp_path, resolver):
    root = _project_root(tmp_path)
    generated_dir = tmp_path / "generated"
    generated_dir.mkdir()
    registry = WorkerRegistry(root, output_schema_resolver=resolver, generated_dir=generated_dir)

    definition = registry.load_definition("worker_bootstrapper")
    assert definition.name == "worker_bootstrapper"
    assert "worker_call" in (definition.instructions or "")


def test_generated_worker_resolves_prompts_from_own_directory(tmp_path, resolver):
    """Generated workers are self-contained - prompts are in worker's directory."""
    root = _project_root(tmp_path)
    generated_dir = tmp_path / "generated"
    generated_dir.mkdir()
    registry = WorkerRegistry(root, output_schema_resolver=resolver, generated_dir=generated_dir)

    # Create generated worker directory with embedded instructions
    worker_dir = generated_dir / "foo"
    worker_dir.mkdir()
    (worker_dir / "worker.worker").write_text("---\nname: foo\n---\nWorker-specific prompt", encoding="utf-8")
    registry.register_generated("foo")

    definition = registry.load_definition("foo")
    assert definition.instructions == "Worker-specific prompt"


def test_call_worker_respects_allowlist(registry):
    parent_def = WorkerDefinition(
        name="parent",
        instructions="",
        toolsets={"delegation": {"allow_workers": ["child"]}},
    )
    # Child has its own model - no inheritance from parent
    child_def = WorkerDefinition(name="child", instructions="", model="child:model")
    registry.save_definition(parent_def)
    registry.save_definition(child_def)

    def simple_runner(defn, input_data, ctx, output_model):
        return {"worker": defn.name, "input": input_data, "model": ctx.effective_model}

    controller = ApprovalController(mode="approve_all")
    parent_context = WorkerContext(
        # Core
        worker=parent_def,
        effective_model="parent:model",
        approval_controller=controller,
        # Delegation
        registry=registry,
        creation_defaults=WorkerCreationDefaults(),
    )

    result = call_worker(
        registry=registry,
        worker="child",
        input_data={"from": "parent"},
        caller_context=parent_context,
        agent_runner=simple_runner,
    )

    assert result.output["worker"] == "child"
    # Child resolves its own model - no inheritance from parent
    assert result.output["model"] == "child:model"


def test_call_worker_supports_wildcard_allowlist(registry):
    parent_def = WorkerDefinition(
        name="parent",
        instructions="",
        toolsets={"delegation": {"allow_workers": ["*"]}},
    )
    child_def = WorkerDefinition(name="child", instructions="")
    registry.save_definition(parent_def)
    registry.save_definition(child_def)

    def simple_runner(defn, input_data, ctx, output_model):
        return {"worker": defn.name, "input": input_data}

    controller = ApprovalController(mode="approve_all")
    parent_context = WorkerContext(
        # Core
        worker=parent_def,
        effective_model="cli",
        approval_controller=controller,
        # Delegation
        registry=registry,
        creation_defaults=WorkerCreationDefaults(),
    )

    result = call_worker(
        registry=registry,
        worker="child",
        input_data={"note": "ok"},
        caller_context=parent_context,
        agent_runner=simple_runner,
    )

    assert result.output["worker"] == "child"


def test_call_worker_propagates_message_callback(registry):
    parent_def = WorkerDefinition(
        name="parent",
        instructions="",
        toolsets={"delegation": {"allow_workers": ["child"]}},
    )
    child_def = WorkerDefinition(name="child", instructions="")
    registry.save_definition(parent_def)
    registry.save_definition(child_def)

    events: list[Any] = []

    def callback(payload):
        events.extend(payload)

    def runner(defn, input_data, ctx, output_model):
        assert ctx.message_callback is callback
        ctx.message_callback([{"worker": defn.name, "event": "child-event"}])
        return ("done", [])

    controller = ApprovalController(mode="approve_all")
    parent_context = WorkerContext(
        # Core
        worker=parent_def,
        effective_model="cli",
        approval_controller=controller,
        # Delegation
        registry=registry,
        creation_defaults=WorkerCreationDefaults(),
        # Callbacks
        message_callback=callback,
    )

    call_worker(
        registry=registry,
        worker="child",
        input_data={"from": "parent"},
        caller_context=parent_context,
        agent_runner=runner,
    )

    assert events == [{"worker": "child", "event": "child-event"}]


def test_default_agent_runner_uses_pydantic_ai(registry):
    definition = WorkerDefinition(
        name="pydantic-worker",
        instructions="Summarize input",
        toolsets={
            "filesystem": {},
            "shell": {"default": {"allowed": True, "approval_required": True}},
            "delegation": {"allow_workers": ["*"]},
        },
    )
    registry.save_definition(definition)

    model = RecordingModel()
    result = run_worker(
        registry=registry,
        worker="pydantic-worker",
        input_data={"task": "demo"},
        cli_model=model,
    )

    payload = json.loads(result.output)
    assert json.loads(payload["prompt"]) == {"task": "demo"}
    assert payload["instructions"] == definition.instructions
    # Verify our toolsets were loaded (don't test exact tool names from dependencies)
    tool_names = set(model.tool_names)
    assert "shell" in tool_names, "shell toolset should be loaded"
    assert "worker_call" in tool_names, "delegation toolset should be loaded"
    assert "worker_create" in tool_names, "delegation toolset should be loaded"
    assert "read_file" in tool_names, "filesystem toolset should be loaded"


def test_default_runner_emits_request_preview(tmp_path, registry):
    definition = WorkerDefinition(name="preview-worker", instructions="State input")
    registry.save_definition(definition)

    attachment = tmp_path / "doc.txt"
    attachment.write_text("hi", encoding="utf-8")

    events: list[Any] = []

    def callback(payload):
        events.extend(payload)

    model = RecordingModel()
    run_worker(
        registry=registry,
        worker="preview-worker",
        input_data="Hello",
        cli_model=model,
        attachments=[str(attachment)],
        message_callback=callback,
    )

    preview_events = [event for event in events if "initial_request" in event]
    assert preview_events, "expected initial request event"
    preview = preview_events[0]["initial_request"]
    assert preview["user_input"] == "Hello"
    assert preview["attachments"] == [str(attachment)]


def test_run_worker_without_model_errors(registry):
    definition = WorkerDefinition(name="no-model", instructions="")
    registry.save_definition(definition)

    with pytest.raises(ValueError, match="No model configured"):
        run_worker(
            registry=registry,
            worker="no-model",
            input_data="hello",
        )






# ---------------------------------------------------------------------------
# Template rendering and prompt file discovery tests
# ---------------------------------------------------------------------------
# NOTE: These tests have been moved to tests/test_prompts.py as part of
# refactoring the prompts module (load_prompt_file, render_jinja_template)
# out of base.py. See test_prompts.py for all Jinja2 and prompt file tests.
# ---------------------------------------------------------------------------


def test_workers_subdirectory_discovery(tmp_path):
    """Test that workers can be discovered from workers/ subdirectory by name."""
    project_root = _project_root(tmp_path)
    registry = WorkerRegistry(project_root)

    # Create worker in workers/ subdirectory
    workers_dir = project_root / "workers"
    workers_dir.mkdir()
    worker_file = workers_dir / "my_worker.worker"
    worker_def = WorkerDefinition(name="my_worker", instructions="Do the task")

    # Save directly to the workers/ subdirectory
    registry.save_definition(worker_def, path=worker_file)

    # Load by name only - should discover from workers/ subdirectory
    loaded = registry.load_definition("my_worker")
    assert loaded.name == "my_worker"
    assert loaded.instructions == "Do the task"
