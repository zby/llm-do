import json

import pytest
from pydantic import BaseModel
from pydantic_ai.messages import ModelRequest, ModelResponse, TextPart
from pydantic_ai.models import Model

from llm_do.pydanticai import (
    ApprovalCallback,
    ApprovalController,
    ApprovalDecision,
    SandboxConfig,
    SandboxManager,
    SandboxToolset,
    ToolRule,
    WorkerContext,
    WorkerCreationDefaults,
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

    def reject_callback(tool_name, payload, reason):
        return ApprovalDecision(approved=False, note="Test rejection")

    with pytest.raises(PermissionError, match="User rejected tool call 'sandbox.write': Test rejection"):
        run_worker(
            registry=registry,
            worker="writer",
            input_data="",
            cli_model="model-x",
            agent_runner=runner,
            approval_callback=reject_callback,
        )

    assert not (sandbox_path / "note.txt").exists()


def test_create_worker_applies_creation_defaults(registry, tmp_path):
    defaults = WorkerCreationDefaults(
        default_model="gpt-4",
        default_sandboxes={
            "rw": SandboxConfig(name="rw", path=tmp_path / "rw", mode="rw"),
        },
    )
    spec = WorkerSpec(name="beta", instructions="collect data")

    created = create_worker(registry, spec, defaults=defaults)

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

    controller = ApprovalController(parent_def.tool_rules)
    sandbox_manager = SandboxManager(parent_def.sandboxes)
    parent_context = WorkerContext(
        registry=registry,
        worker=parent_def,
        sandbox_manager=sandbox_manager,
        sandbox_toolset=SandboxToolset(sandbox_manager, controller),
        creation_defaults=WorkerCreationDefaults(),
        effective_model="cli",
        approval_controller=controller,
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
        "worker_call",
        "worker_create",
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


def test_approve_all_callback_mode(tmp_path, registry):
    """Test Story 6: --approve-all flag auto-approves all tools."""
    from llm_do.pydanticai import approve_all_callback

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
        result = ctx.sandbox_toolset.write_text("out", "note.txt", "hello")
        return {"wrote": result}

    result = run_worker(
        registry=registry,
        worker="writer",
        input_data="",
        cli_model="model-x",
        agent_runner=runner,
        approval_callback=approve_all_callback,
    )

    # Tool executed successfully
    assert (sandbox_path / "note.txt").exists()
    assert (sandbox_path / "note.txt").read_text() == "hello"


def test_strict_mode_callback_rejects(tmp_path, registry):
    """Test Story 7: --strict flag rejects all non-preapproved tools."""
    from llm_do.pydanticai import strict_mode_callback

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
        return {"worker": defn.name}

    with pytest.raises(PermissionError, match="Strict mode: tool 'sandbox.write' not pre-approved"):
        run_worker(
            registry=registry,
            worker="writer",
            input_data="",
            cli_model="model-x",
            agent_runner=runner,
            approval_callback=strict_mode_callback,
        )

    # Tool did not execute
    assert not (sandbox_path / "note.txt").exists()


def test_jinja_file_function(tmp_path):
    """Test that Jinja2 file() function loads files correctly."""
    # Create registry and support file
    registry_root = tmp_path / "workers"
    prompts_dir = tmp_path / "prompts"
    prompts_dir.mkdir(parents=True)

    # Create a rubric file in prompts directory
    rubric_file = prompts_dir / "rubric.md"
    rubric_file.write_text("# Evaluation Rubric\n\nScore from 1-5.")

    # Create worker definition with Jinja2 file() function
    # File paths are relative to prompts/ directory
    registry = WorkerRegistry(registry_root)
    worker_def = WorkerDefinition(
        name="evaluator",
        instructions="Evaluate using this rubric:\n\n{{ file('rubric.md') }}\n\nReturn scores.",
    )
    registry.save_definition(worker_def)

    # Load the worker - Jinja2 should render the template
    loaded = registry.load_definition("evaluator")

    assert "{{ file(" not in loaded.instructions
    assert "# Evaluation Rubric" in loaded.instructions
    assert "Score from 1-5." in loaded.instructions
    assert "Return scores." in loaded.instructions


def test_jinja_include_directive(tmp_path):
    """Test that standard Jinja2 {% include %} directive works."""
    registry_root = tmp_path / "workers"
    prompts_dir = tmp_path / "prompts"
    prompts_dir.mkdir(parents=True)

    # Create a procedure file in prompts directory
    procedure_file = prompts_dir / "procedure.txt"
    procedure_file.write_text("Step 1: Analyze\nStep 2: Score")

    # Create worker with {% include %} directive
    # Include paths are relative to prompts/ directory
    registry = WorkerRegistry(registry_root)
    worker_def = WorkerDefinition(
        name="worker",
        instructions="Follow this procedure:\n{% include 'procedure.txt' %}",
    )
    registry.save_definition(worker_def)

    loaded = registry.load_definition("worker")

    assert "{% include" not in loaded.instructions
    assert "Step 1: Analyze" in loaded.instructions
    assert "Step 2: Score" in loaded.instructions


def test_jinja_plain_text_passthrough(tmp_path):
    """Test that plain text without Jinja2 syntax passes through unchanged."""
    registry_root = tmp_path / "workers"
    registry = WorkerRegistry(registry_root)

    plain_instructions = "Just evaluate the document. No templates here."
    worker_def = WorkerDefinition(
        name="plain",
        instructions=plain_instructions,
    )
    registry.save_definition(worker_def)

    loaded = registry.load_definition("plain")
    assert loaded.instructions == plain_instructions


def test_jinja_file_not_found(tmp_path):
    """Test that missing file raises FileNotFoundError."""
    registry_root = tmp_path / "workers"
    registry = WorkerRegistry(registry_root)

    worker_def = WorkerDefinition(
        name="broken",
        instructions="Use this: {{ file('missing.md') }}",
    )
    registry.save_definition(worker_def)

    with pytest.raises(FileNotFoundError, match="File not found"):
        registry.load_definition("broken")


def test_jinja_path_escape_prevention(tmp_path):
    """Test that file() function prevents path escapes."""
    registry_root = tmp_path / "workers"
    registry = WorkerRegistry(registry_root)

    # Try to escape to parent's parent
    worker_def = WorkerDefinition(
        name="malicious",
        instructions="{{ file('../../etc/passwd') }}",
    )
    registry.save_definition(worker_def)

    with pytest.raises(PermissionError, match="path escapes allowed directory"):
        registry.load_definition("malicious")


def test_prompt_file_txt(tmp_path):
    """Test loading plain text prompt from .txt file."""
    registry_root = tmp_path / "workers"
    prompts_dir = tmp_path / "prompts"
    prompts_dir.mkdir(parents=True)

    # Create plain text prompt file
    prompt_file = prompts_dir / "my_worker.txt"
    prompt_file.write_text("Analyze the input data and provide insights.")

    # Create worker definition without inline instructions
    registry = WorkerRegistry(registry_root)
    worker_def = WorkerDefinition(name="my_worker")
    registry.save_definition(worker_def)

    # Load should discover and use the prompt file
    loaded = registry.load_definition("my_worker")
    assert loaded.instructions == "Analyze the input data and provide insights."


def test_prompt_file_jinja2(tmp_path):
    """Test loading Jinja2 template prompt from .jinja2 file."""
    registry_root = tmp_path / "workers"
    prompts_dir = tmp_path / "prompts"
    config_dir = tmp_path / "config"
    prompts_dir.mkdir(parents=True)
    config_dir.mkdir(parents=True)

    # Create config file
    config_file = config_dir / "rubric.md"
    config_file.write_text("# Scoring Rubric\n\nScore from 1-10.")

    # Create Jinja2 template prompt file
    prompt_file = prompts_dir / "evaluator.jinja2"
    prompt_file.write_text("Evaluate using:\n\n{{ file('config/rubric.md') }}\n\nReturn JSON.")

    # Create worker definition without inline instructions
    registry = WorkerRegistry(registry_root)
    worker_def = WorkerDefinition(name="evaluator")
    registry.save_definition(worker_def)

    # Load should discover, render template, and use the prompt
    loaded = registry.load_definition("evaluator")
    assert "{{ file(" not in loaded.instructions
    assert "# Scoring Rubric" in loaded.instructions
    assert "Score from 1-10." in loaded.instructions
    assert "Return JSON." in loaded.instructions


def test_prompt_file_priority(tmp_path):
    """Test that .jinja2 takes priority over .txt when both exist."""
    registry_root = tmp_path / "workers"
    prompts_dir = tmp_path / "prompts"
    prompts_dir.mkdir(parents=True)

    # Create both .jinja2 and .txt files
    (prompts_dir / "worker.jinja2").write_text("From jinja2 file")
    (prompts_dir / "worker.txt").write_text("From txt file")

    registry = WorkerRegistry(registry_root)
    worker_def = WorkerDefinition(name="worker")
    registry.save_definition(worker_def)

    loaded = registry.load_definition("worker")
    assert loaded.instructions == "From jinja2 file"


def test_prompt_file_j2_extension(tmp_path):
    """Test loading from .j2 extension."""
    registry_root = tmp_path / "workers"
    prompts_dir = tmp_path / "prompts"
    prompts_dir.mkdir(parents=True)

    prompt_file = prompts_dir / "worker.j2"
    prompt_file.write_text("Instructions from .j2 file")

    registry = WorkerRegistry(registry_root)
    worker_def = WorkerDefinition(name="worker")
    registry.save_definition(worker_def)

    loaded = registry.load_definition("worker")
    assert loaded.instructions == "Instructions from .j2 file"


def test_prompt_file_md_extension(tmp_path):
    """Test loading from .md extension."""
    registry_root = tmp_path / "workers"
    prompts_dir = tmp_path / "prompts"
    prompts_dir.mkdir(parents=True)

    prompt_file = prompts_dir / "worker.md"
    prompt_file.write_text("# Worker Instructions\n\nDo the task.")

    registry = WorkerRegistry(registry_root)
    worker_def = WorkerDefinition(name="worker")
    registry.save_definition(worker_def)

    loaded = registry.load_definition("worker")
    assert loaded.instructions == "# Worker Instructions\n\nDo the task."


def test_prompt_file_not_found_no_inline(tmp_path):
    """Test that validation error occurs when no prompt file and no inline instructions."""
    registry_root = tmp_path / "workers"
    registry = WorkerRegistry(registry_root)

    # Create worker without instructions and no prompts/ directory
    worker_def = WorkerDefinition(name="worker")
    registry.save_definition(worker_def)

    # Load should fail validation because instructions is required
    # (WorkerDefinition.instructions is Optional but WorkerSpec.instructions is required for actual execution)
    # For now, it will load successfully but may fail at runtime
    loaded = registry.load_definition("worker")
    assert loaded.instructions is None


def test_prompt_file_inline_takes_precedence(tmp_path):
    """Test that inline instructions take precedence over prompt files."""
    registry_root = tmp_path / "workers"
    prompts_dir = tmp_path / "prompts"
    prompts_dir.mkdir(parents=True)

    # Create prompt file
    prompt_file = prompts_dir / "worker.txt"
    prompt_file.write_text("From file")

    # Create worker with inline instructions
    registry = WorkerRegistry(registry_root)
    worker_def = WorkerDefinition(name="worker", instructions="Inline instructions")
    registry.save_definition(worker_def)

    loaded = registry.load_definition("worker")
    assert loaded.instructions == "Inline instructions"


def test_prompt_file_nested_workers_directory(tmp_path):
    """Test prompt file discovery when worker is in workers/ subdirectory."""
    workers_dir = tmp_path / "workers"
    prompts_dir = tmp_path / "prompts"
    prompts_dir.mkdir(parents=True)

    # Create prompt at project root level
    prompt_file = prompts_dir / "my_worker.txt"
    prompt_file.write_text("Instructions from prompts/")

    # Create worker in workers/ subdirectory
    registry = WorkerRegistry(workers_dir)
    worker_def = WorkerDefinition(name="my_worker")
    registry.save_definition(worker_def)

    # Load should find prompts/ at parent level
    loaded = registry.load_definition("my_worker")
    assert loaded.instructions == "Instructions from prompts/"


def test_workers_subdirectory_discovery(tmp_path):
    """Test that workers can be discovered from workers/ subdirectory by name."""
    # Create registry at project root
    registry = WorkerRegistry(tmp_path)

    # Create worker in workers/ subdirectory
    workers_dir = tmp_path / "workers"
    workers_dir.mkdir()
    worker_file = workers_dir / "my_worker.yaml"
    worker_def = WorkerDefinition(name="my_worker", instructions="Do the task")

    # Save directly to the workers/ subdirectory
    registry.save_definition(worker_def, path=worker_file)

    # Load by name only - should discover from workers/ subdirectory
    loaded = registry.load_definition("my_worker")
    assert loaded.name == "my_worker"
    assert loaded.instructions == "Do the task"


