# Testing Patterns in llm-do

This guide documents the testing strategies and patterns used in llm-do. The codebase uses PydanticAI's dependency injection system to enable comprehensive testing without API calls.

## Quick Reference

| Pattern | Use Case | Example |
|---------|----------|---------|
| **TestModel** | Test worker definitions, tools, schemas | `Worker(model=test_model)` + `Runtime.run_entry(...)` |
| **Custom agent_runner** | Test orchestration logic | `run_worker_async(agent_runner=custom_runner, ...)` |
| **Real model (integration)** | Verify critical end-to-end flows | Keep minimal |

### Example Integration Tests

`tests/test_examples.py` exercises the example projects end-to-end (copying
directories, writing files, etc.). They now run as part of the normal
suite, so expect a bit more filesystem churn.

To focus on these tests only, use the marker:

```bash
pytest -m examples
```

## Using PydanticAI's TestModel

### When to Use

Use `TestModel` when you need to test the **full agent behavior** including:
- Worker definitions load correctly
- Tools are registered and callable
- Structured output schemas validate
- Tool calling behavior works end-to-end

### How It Works

`TestModel` is a fake LLM from PydanticAI that:
- Returns deterministic outputs without API calls
- Exercises the full agent execution flow
- Can be configured to return specific text or pseudo-random responses

### Configuration Options

```python
from pydantic_ai.models.test import TestModel

# Default: returns empty string
model = TestModel()

# Custom response text
model = TestModel(custom_result_text="I analyzed the data")

# Deterministic pseudo-random (useful for reproducible tests)
model = TestModel(seed=42)
```

### Example

```python
def test_worker_executes_with_tools(test_model):
    """Test that worker loads and tools are available."""
    worker = Worker(
        name="my_worker",
        instructions="Process this",
        model=test_model,  # Uses TestModel from conftest.py fixture
        toolset_specs=[...],
    )
    runtime = Runtime()
    result, _ctx = asyncio.run(runtime.run_entry(
        worker,
        "process this",
    ))
    # Verifies:
    # - Worker definition loaded
    # - Tools registered correctly
    # - Output schema validated
    # - No API calls made
```

### Available Fixture

The `test_model` fixture is available in all tests via `tests/conftest.py`:

```python
def test_something(test_model):
    # test_model is a TestModel(seed=42)
    worker = Worker(name="my_worker", instructions="...", model=test_model)
    result, _ctx = asyncio.run(Runtime().run_entry(worker, "..."))
```

## Using Custom agent_runner

### When to Use

Use custom `agent_runner` when you need to test **orchestration logic** without agent execution:
- Model selection (worker.model or `LLM_DO_MODEL` fallback)
- Approval flow behavior
- Context assembly (attachments, tools)
- Delegation allowlists
- Error handling

### How It Works

The `agent_runner` parameter in `run_worker_async()` allows you to replace the entire agent execution with a custom function that returns predetermined outputs.

### Example

```python
def test_model_resolution_prefers_worker_model(monkeypatch):
    """Test that worker.model takes precedence over LLM_DO_MODEL."""

    # Create custom runner that records what model was used
    used_model = None

    def custom_runner(definition, user_input, context, output_model):
        nonlocal used_model
        used_model = context.effective_model
        return ({"status": "ok"}, [])  # (output, messages)

    monkeypatch.setenv("LLM_DO_MODEL", "model-b")
    result = asyncio.run(run_worker_async(
        worker="my_worker",  # worker.model = "model-a"
        agent_runner=custom_runner,
    ))

    assert used_model == "model-a"  # Worker model takes precedence
```

### Custom Runner Signature

```python
def agent_runner(
    definition: WorkerDefinition,
    user_input: Any,
    context: WorkerContext,
    output_model: Optional[Type[BaseModel]]
) -> tuple[Any, List[Any]]:
    """
    Args:
        definition: Worker definition with instructions and config
        user_input: Input data passed to the worker
        context: WorkerContext with tools, etc.
        output_model: Optional Pydantic model for structured output

    Returns:
        Tuple of (output, messages) where:
        - output: The result to return (can be dict, object, etc.)
        - messages: List of message objects from agent execution
    """
    return (output, messages)
```

### When to Inline vs Extract Helper

- **Inline**: Most tests should inline custom runners for clarity
- **Helper function**: Only extract if 3+ tests use identical pattern

Don't create premature abstractions. The runner is simple enough to inline.

## When to Use Each Pattern

### Use TestModel When

✅ Testing that a worker definition loads correctly
✅ Verifying tools are registered and available
✅ Checking structured output schema validation
✅ Testing tool calling behavior end-to-end

### Use Custom agent_runner When

✅ Testing model inheritance logic
✅ Testing approval callback behavior
✅ Testing context assembly (attachments, tools)
✅ Testing delegation and allowlists
✅ You need precise control over the output

### Use Real Models (Integration Tests) When

✅ Testing critical end-to-end workflows
⚠️ Keep these minimal (slow, flaky, costs money)

## Tradeoffs

| Aspect | TestModel | Custom agent_runner | Real Model |
|--------|-----------|---------------------|------------|
| **Speed** | Fast | Fastest | Slow |
| **Exercises tools** | ✅ Yes | ❌ No | ✅ Yes |
| **Control over output** | ⚠️ Generic | ✅ Full control | ⚠️ Non-deterministic |
| **Tests orchestration** | ⚠️ Partial | ✅ Full | ✅ Full |
| **API calls** | ❌ No | ❌ No | ✅ Yes (costs $) |

**Choose based on what behavior you're testing:**

- Testing **agent behavior** (tools, schemas)? → Use `TestModel`
- Testing **framework behavior** (model inheritance, approvals)? → Use custom `agent_runner`
- Testing **real-world integration**? → Use real model sparingly

## Test Organization

### File Structure

```
tests/
├── conftest.py              # Shared fixtures (test_model, etc.)
├── README.md                # This file
├── test_prompts.py          # Prompt loading and Jinja2 rendering
├── test_pydanticai_base.py  # Core runtime and orchestration
├── test_pydanticai_cli.py   # CLI interface
├── test_pydanticai_integration.py  # Integration tests with real models
└── test_worker_delegation.py       # Worker delegation and creation
```

### Naming Conventions

- `test_*.py` - Test modules
- `test_*` - Test functions
- Use descriptive names that explain **what** is being tested

### Fixtures

Shared fixtures live in `conftest.py`:
- `test_model` - PydanticAI TestModel with seed=42

## Examples from the Codebase

### Example 1: Testing Worker Definition Loading

From `test_prompts.py`:

```python
def test_prompt_file_jinja2(tmp_path):
    """Test loading Jinja2 template prompt from .jinja2 file."""
    project_root = _project_root(tmp_path)
    prompts_dir = project_root / "prompts"
    prompts_dir.mkdir(parents=True)

    # Create template file
    prompt_file = prompts_dir / "evaluator.jinja2"
    prompt_file.write_text("Evaluate using:\n\n{{ file('rubric.md') }}")

    # Load worker - should render template
    registry = WorkerRegistry(project_root)
    worker_def = WorkerDefinition(name="evaluator")
    registry.save_definition(worker_def)
    loaded = registry.load_definition("evaluator")

    assert "{{ file(" not in loaded.instructions  # Template rendered
```

### Example 2: Testing Orchestration with Custom Runner

From `test_pydanticai_base.py`:

```python
def test_run_worker_async_applies_model_inheritance(monkeypatch):
    """Test that worker.model takes precedence over LLM_DO_MODEL."""

    def custom_runner(definition, user_input, context, output_model):
        # Return the effective model so we can verify it
        return (context.effective_model, [])

    monkeypatch.setenv("LLM_DO_MODEL", "env-model")
    result = asyncio.run(run_worker_async(
        worker="my_worker",      # has model="worker-model"
        agent_runner=custom_runner,
    ))

    assert result.output == "worker-model"  # Worker model takes precedence
```

### Example 3: Testing Approval Flow

From `test_pydanticai_base.py`:

```python
def test_strict_mode_rejects():
    """Test that strict mode rejects unapproved tools."""
    from llm_do import ApprovalController

    def runner(definition, user_input, context, output_model):
        return ("should not reach here", [])

    with pytest.raises(PermissionError, match="Strict mode"):
        asyncio.run(run_worker_async(
            worker="writer",
            agent_runner=runner,
            approval_controller=ApprovalController(mode="strict"),  # Rejects all
        ))
```

## Best Practices

1. **Prefer TestModel for agent tests** - It exercises the real code path
2. **Inline custom runners** - Only extract if used 3+ times
3. **Keep integration tests minimal** - They're slow and flaky
4. **Use tmp_path for file tests** - Pytest provides this fixture
5. **Test behavior, not implementation** - Focus on observable outcomes
6. **Use descriptive test names** - Explain the scenario being tested

## Common Pitfalls

❌ **Don't use real models in unit tests**
```python
# BAD: Slow, costs money, non-deterministic
def test_worker(monkeypatch):
    monkeypatch.setenv("LLM_DO_MODEL", "openai:gpt-4")
    result = asyncio.run(run_worker_async(...))
```

✅ **Use TestModel or custom runner**
```python
# GOOD: Fast, free, deterministic
def test_worker(test_model):
    worker = Worker(name="my_worker", instructions="...", model=test_model)
    result, _ctx = asyncio.run(Runtime().run_entry(worker, "..."))
```

❌ **Don't create premature abstractions**
```python
# BAD: Only used once
def make_simple_runner(output):
    def runner(definition, user_input, context, output_model):
        return (output, [])
    return runner
```

✅ **Inline until needed 3+ times**
```python
# GOOD: Clear and simple
def test_something():
    def runner(definition, user_input, context, output_model):
        return ({"status": "ok"}, [])
    result = asyncio.run(run_worker_async(agent_runner=runner, ...))
```

## Further Reading

- PydanticAI TestModel docs: https://ai.pydantic.dev/testing/
- Pytest fixtures: https://docs.pytest.org/en/stable/fixture.html
- See existing tests for more examples
