import json

import pytest
from pydantic import BaseModel
from pydantic_ai.messages import ModelRequest, ModelResponse, TextPart
from pydantic_ai.models import Model

from llm_do.pydanticai import (
    ApprovalController,
    SandboxConfig,
    SandboxManager,
    SandboxToolset,
    ToolRule,
    WorkerContext,
    WorkerCreationProfile,
    WorkerDefinition,
    WorkerRegistry,
    WorkerSpec,
    call_worker,
    create_worker,
    run_worker,
)


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
                        parts.append(json.dumps(content))
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


@pytest.fixture
def registry(tmp_path, resolver):
    root = tmp_path / "workers"
    return WorkerRegistry(root, output_schema_resolver=resolver)


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


def test_sandbox_write_requires_approval(tmp_path, registry):
    sandbox_path = tmp_path / "out"
    sandbox_cfg = SandboxConfig(
        name="out",
        path=sandbox_path,
        mode="rw",
        allowed_suffixes=[".txt"],
    )
    rule = ToolRule(name="sandbox.write", approval_required=True)

    definition = WorkerDefinition(
        name="writer",
        instructions="",
        sandboxes={"out": sandbox_cfg},
        tool_rules={"sandbox.write": rule},
    )
    registry.save_definition(definition)

    def runner(defn, input_data, ctx, output_model):
        ctx.sandbox_toolset.write_text("out", "note.txt", "hello")
        return {"worker": defn.name, "input": input_data, "model": ctx.effective_model}

    result = run_worker(
        registry=registry,
        worker="writer",
        input_data="",
        cli_model="model-x",
        agent_runner=runner,
    )

    assert result.deferred_requests
    assert result.deferred_requests[0].tool_name == "sandbox.write"
    assert not (sandbox_path / "note.txt").exists()


def test_create_worker_applies_profile_defaults(registry, tmp_path):
    profile = WorkerCreationProfile(
        default_model="gpt-4",
        default_sandboxes={
            "rw": SandboxConfig(name="rw", path=tmp_path / "rw", mode="rw"),
        },
    )
    spec = WorkerSpec(name="beta", instructions="collect data")

    created = create_worker(registry, spec, profile=profile)

    assert created.model == "gpt-4"
    assert "rw" in created.sandboxes
    loaded = registry.load_definition("beta")
    assert loaded.sandboxes["rw"].path == (tmp_path / "rw").resolve()


def test_call_worker_respects_allowlist(registry):
    parent_def = WorkerDefinition(
        name="parent",
        instructions="",
        allow_workers=["child"],
    )
    child_def = WorkerDefinition(name="child", instructions="")
    registry.save_definition(parent_def)
    registry.save_definition(child_def)

    def simple_runner(defn, input_data, ctx, output_model):
        return {"worker": defn.name, "input": input_data, "model": ctx.effective_model}

    parent_context = WorkerContext(
        registry=registry,
        worker=parent_def,
        sandbox_manager=SandboxManager(parent_def.sandboxes),
        sandbox_toolset=SandboxToolset(
            SandboxManager(parent_def.sandboxes),
            ApprovalController(parent_def.tool_rules, requests=[]),
        ),
        creation_profile=WorkerCreationProfile(),
        effective_model="cli",
    )

    result = call_worker(
        registry=registry,
        worker="child",
        input_data={"from": "parent"},
        caller_context=parent_context,
        agent_runner=simple_runner,
    )

    assert result.output["worker"] == "child"
    assert result.output["model"] == "cli"


def test_default_agent_runner_uses_pydantic_ai(registry):
    definition = WorkerDefinition(name="pydantic-worker", instructions="Summarize input")
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
    assert model.tool_names == [
        "sandbox_list",
        "sandbox_read_text",
        "sandbox_write_text",
    ]


def test_run_worker_without_model_errors(registry):
    definition = WorkerDefinition(name="no-model", instructions="")
    registry.save_definition(definition)

    with pytest.raises(ValueError, match="No model configured"):
        run_worker(
            registry=registry,
            worker="no-model",
            input_data="hello",
        )
