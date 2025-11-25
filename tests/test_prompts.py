"""Tests for prompt file loading and Jinja2 template rendering.

These tests were migrated from test_pydanticai_base.py to test the
prompts module in isolation. Tests use WorkerRegistry as the integration
point since that's the primary consumer of the prompts module.
"""
import pytest

from llm_do import WorkerDefinition, WorkerRegistry


def _project_root(tmp_path):
    """Helper to create a project root directory."""
    root = tmp_path / "project"
    root.mkdir(parents=True, exist_ok=True)
    return root


# ---------------------------------------------------------------------------
# Jinja2 template rendering tests
# ---------------------------------------------------------------------------


def test_jinja_file_function(tmp_path):
    """Test that Jinja2 file() function loads files correctly."""
    # Create registry and support file
    project_root = _project_root(tmp_path)
    prompts_dir = project_root / "prompts"
    prompts_dir.mkdir(parents=True)

    # Create a rubric file in prompts directory
    rubric_file = prompts_dir / "rubric.md"
    rubric_file.write_text("# Evaluation Rubric\n\nScore from 1-5.")

    # Create worker definition using a prompt file
    # File paths are relative to prompts/ directory
    (prompts_dir / "evaluator.jinja2").write_text(
        "Evaluate using this rubric:\n\n{{ file('rubric.md') }}\n\nReturn scores."
    )
    
    registry = WorkerRegistry(project_root)
    worker_def = WorkerDefinition(name="evaluator")
    registry.save_definition(worker_def)

    # Load the worker - Jinja2 should render the template
    loaded = registry.load_definition("evaluator")

    assert "{{ file(" not in loaded.instructions
    assert "# Evaluation Rubric" in loaded.instructions
    assert "Score from 1-5." in loaded.instructions
    assert "Return scores." in loaded.instructions


def test_jinja_include_directive(tmp_path):
    """Test that standard Jinja2 {% include %} directive works."""
    project_root = _project_root(tmp_path)
    prompts_dir = project_root / "prompts"
    prompts_dir.mkdir(parents=True)

    # Create a procedure file in prompts directory
    procedure_file = prompts_dir / "procedure.txt"
    procedure_file.write_text("Step 1: Analyze\nStep 2: Score")

    # Create worker with {% include %} directive in a file
    # Include paths are relative to prompts/ directory
    (prompts_dir / "worker.jinja2").write_text(
        "Follow this procedure:\n{% include 'procedure.txt' %}"
    )

    registry = WorkerRegistry(project_root)
    worker_def = WorkerDefinition(name="worker")
    registry.save_definition(worker_def)

    loaded = registry.load_definition("worker")

    assert "{% include" not in loaded.instructions
    assert "Step 1: Analyze" in loaded.instructions
    assert "Step 2: Score" in loaded.instructions


def test_jinja_plain_text_passthrough(tmp_path):
    """Test that plain text without Jinja2 syntax passes through unchanged."""
    registry = WorkerRegistry(_project_root(tmp_path))

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
    project_root = _project_root(tmp_path)
    prompts_dir = project_root / "prompts"
    prompts_dir.mkdir(parents=True)

    (prompts_dir / "broken.jinja2").write_text("Use this: {{ file('missing.md') }}")

    registry = WorkerRegistry(project_root)
    worker_def = WorkerDefinition(name="broken")
    registry.save_definition(worker_def)

    with pytest.raises(FileNotFoundError, match="File not found"):
        registry.load_definition("broken")


def test_jinja_path_escape_prevention(tmp_path):
    """Test that file() function prevents path escapes."""
    project_root = _project_root(tmp_path)
    prompts_dir = project_root / "prompts"
    prompts_dir.mkdir(parents=True)

    # Try to escape to parent's parent
    (prompts_dir / "malicious.jinja2").write_text("{{ file('../../etc/passwd') }}")

    registry = WorkerRegistry(project_root)
    worker_def = WorkerDefinition(name="malicious")
    registry.save_definition(worker_def)

    with pytest.raises(PermissionError, match="path escapes allowed directory"):
        registry.load_definition("malicious")


def test_inline_jinja_rendering(tmp_path):
    """Test that inline instructions with Jinja2 syntax are rendered."""
    project_root = _project_root(tmp_path)
    prompts_dir = project_root / "prompts"
    prompts_dir.mkdir(parents=True)

    # Create a support file
    support_file = prompts_dir / "guidelines.txt"
    support_file.write_text("Be thorough and accurate.")

    # Create worker with inline Jinja2 instructions
    registry = WorkerRegistry(project_root)
    worker_def = WorkerDefinition(
        name="reviewer",
        instructions="Review the submission.\n\nGuidelines: {{ file('guidelines.txt') }}",
    )
    registry.save_definition(worker_def)

    # Load should NOT render the inline template (raw instructions are now always raw)
    loaded = registry.load_definition("reviewer")
    assert "{{ file('guidelines.txt') }}" in loaded.instructions
    assert "Be thorough and accurate." not in loaded.instructions
    assert "Review the submission." in loaded.instructions


# ---------------------------------------------------------------------------
# Prompt file discovery tests
# ---------------------------------------------------------------------------


def test_prompt_file_txt(tmp_path):
    """Test loading plain text prompt from .txt file."""
    project_root = _project_root(tmp_path)
    prompts_dir = project_root / "prompts"
    prompts_dir.mkdir(parents=True)

    # Create plain text prompt file
    prompt_file = prompts_dir / "my_worker.txt"
    prompt_file.write_text("Analyze the input data and provide insights.")

    # Create worker definition without inline instructions
    registry = WorkerRegistry(project_root)
    worker_def = WorkerDefinition(name="my_worker")
    registry.save_definition(worker_def)

    # Load should discover and use the prompt file
    loaded = registry.load_definition("my_worker")
    assert loaded.instructions == "Analyze the input data and provide insights."


def test_prompt_file_jinja2(tmp_path):
    """Test loading Jinja2 template prompt from .jinja2 file."""
    project_root = _project_root(tmp_path)
    prompts_dir = project_root / "prompts"
    config_dir = prompts_dir / "config"
    prompts_dir.mkdir(parents=True)
    config_dir.mkdir(parents=True)

    # Create config file
    config_file = config_dir / "rubric.md"
    config_file.write_text("# Scoring Rubric\n\nScore from 1-10.")

    # Create Jinja2 template prompt file
    prompt_file = prompts_dir / "evaluator.jinja2"
    prompt_file.write_text("Evaluate using:\n\n{{ file('config/rubric.md') }}\n\nReturn JSON.")

    # Create worker definition without inline instructions
    registry = WorkerRegistry(project_root)
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
    project_root = _project_root(tmp_path)
    prompts_dir = project_root / "prompts"
    prompts_dir.mkdir(parents=True)

    # Create both .jinja2 and .txt files
    (prompts_dir / "worker.jinja2").write_text("From jinja2 file")
    (prompts_dir / "worker.txt").write_text("From txt file")

    registry = WorkerRegistry(project_root)
    worker_def = WorkerDefinition(name="worker")
    registry.save_definition(worker_def)

    loaded = registry.load_definition("worker")
    assert loaded.instructions == "From jinja2 file"


def test_prompt_file_j2_extension(tmp_path):
    """Test loading from .j2 extension."""
    project_root = _project_root(tmp_path)
    prompts_dir = project_root / "prompts"
    prompts_dir.mkdir(parents=True)

    prompt_file = prompts_dir / "worker.j2"
    prompt_file.write_text("Instructions from .j2 file")

    registry = WorkerRegistry(project_root)
    worker_def = WorkerDefinition(name="worker")
    registry.save_definition(worker_def)

    loaded = registry.load_definition("worker")
    assert loaded.instructions == "Instructions from .j2 file"


def test_prompt_file_md_extension(tmp_path):
    """Test loading from .md extension."""
    project_root = _project_root(tmp_path)
    prompts_dir = project_root / "prompts"
    prompts_dir.mkdir(parents=True)

    prompt_file = prompts_dir / "worker.md"
    prompt_file.write_text("# Worker Instructions\n\nDo the task.")

    registry = WorkerRegistry(project_root)
    worker_def = WorkerDefinition(name="worker")
    registry.save_definition(worker_def)

    loaded = registry.load_definition("worker")
    assert loaded.instructions == "# Worker Instructions\n\nDo the task."



def test_prompt_file_inline_takes_precedence(tmp_path):
    """Test that inline instructions take precedence over prompt files."""
    project_root = _project_root(tmp_path)
    prompts_dir = project_root / "prompts"
    prompts_dir.mkdir(parents=True)

    # Create prompt file
    prompt_file = prompts_dir / "worker.txt"
    prompt_file.write_text("From file")

    # Create worker with inline instructions
    registry = WorkerRegistry(project_root)
    worker_def = WorkerDefinition(name="worker", instructions="Inline instructions")
    registry.save_definition(worker_def)

    loaded = registry.load_definition("worker")
    assert loaded.instructions == "Inline instructions"


def test_prompt_file_nested_workers_directory(tmp_path):
    """Test prompt file discovery when worker is in workers/ subdirectory."""
    project_root = _project_root(tmp_path)
    prompts_dir = project_root / "prompts"
    prompts_dir.mkdir(parents=True)

    # Create prompt at project root level
    prompt_file = prompts_dir / "my_worker.txt"
    prompt_file.write_text("Instructions from prompts/")

    # Create worker in workers/ subdirectory
    registry = WorkerRegistry(project_root)
    worker_def = WorkerDefinition(name="my_worker")
    registry.save_definition(worker_def)

    # Load should find prompts/ at parent level
    loaded = registry.load_definition("my_worker")
    assert loaded.instructions == "Instructions from prompts/"


# ---------------------------------------------------------------------------
# resolve_worker_instructions unit tests
# ---------------------------------------------------------------------------


def test_resolve_worker_instructions_missing_prompts_dir(tmp_path):
    """Test that None is returned if prompts_dir does not exist."""
    from llm_do.prompts import resolve_worker_instructions

    result = resolve_worker_instructions(
        raw_instructions=None,
        worker_name="worker",
        prompts_dir=tmp_path / "missing",
    )
    assert result is None


def test_resolve_worker_instructions_missing_file(tmp_path):
    """Test that None is returned if prompt file is missing."""
    from llm_do.prompts import resolve_worker_instructions

    prompts_dir = tmp_path / "prompts"
    prompts_dir.mkdir()

    result = resolve_worker_instructions(
        raw_instructions=None,
        worker_name="worker",
        prompts_dir=prompts_dir,
    )
    assert result is None


def test_resolve_worker_instructions_inline_plain(tmp_path):
    """Test that plain inline instructions are returned as-is."""
    from llm_do.prompts import resolve_worker_instructions

    result = resolve_worker_instructions(
        raw_instructions="Just do it",
        worker_name="worker",
        prompts_dir=tmp_path / "prompts",
    )
    assert result == "Just do it"


def test_resolve_worker_instructions_inline_jinja_is_raw(tmp_path):
    """Test that inline instructions with Jinja syntax are NOT rendered."""
    from llm_do.prompts import resolve_worker_instructions

    prompts_dir = tmp_path / "prompts"
    prompts_dir.mkdir()
    (prompts_dir / "data.txt").write_text("123")

    raw = "Data: {{ file('data.txt') }}"
    result = resolve_worker_instructions(
        raw_instructions=raw,
        worker_name="worker",
        prompts_dir=prompts_dir,
    )
    assert result == raw
