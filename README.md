# llm-do

Package prompts with configuration to create executable workers.

A worker is a **promptogram**: **prompt + config + tools**. Promptograms are self-contained, versioned units you run from the CLI or call from other workers.

## Why llm-do?

**Tight context.** Each worker does one thing well. No bloated multi-purpose prompts that try to handle everything.

**Composability.** Workers call other workers like functions. Build complex workflows from simple, focused building blocks.

**Guardrails by construction.** Security is enforced in code—sandboxes prevent path traversal, attachment policies prevent resource exhaustion, tool approvals gate dangerous operations. Not suggestions the LLM might ignore.

**Progressive hardening.** Programming with specs (prompts) is powerful for bootstrapping. But as systems grow and compose many parts, stochasticity becomes a liability—especially in key areas. So you progressively harden: replace workers or extract operations to tested Python code.

## Quick Start

```bash
# Install
pip install -e .

# Set your API key (choose one)
export ANTHROPIC_API_KEY="sk-ant-..."
# or
export OPENAI_API_KEY="sk-..."

# Set a default model (cheap and fast)
export MODEL=anthropic:claude-3-5-haiku-20241022  # or openai:gpt-4o-mini

# Run a simple worker
cd examples/greeter
llm-do greeter "Tell me a joke" --model $MODEL
```

Model names follow [PydanticAI conventions](https://ai.pydantic.dev/models/) (e.g., `anthropic:claude-sonnet-4-20250514`, `openai:gpt-4o`).

---

Workers can do much more than simple chat: access files, call other workers, require approvals. Here's a real example that analyzes PDF pitch decks:

```yaml
# workers/pitch_evaluator.worker
---
name: pitch_evaluator
description: Analyze a PDF pitch deck and return a markdown evaluation report.
attachment_policy:
  max_attachments: 1
  max_total_bytes: 10000000  # 10MB
  allowed_suffixes:
    - .pdf
---

You are a pitch deck evaluation specialist. You will receive a pitch deck PDF
as an attachment and must analyze it according to the evaluation rubric below.

Evaluation rubric:
{{ file('PROCEDURE.md') }}

...
```

Run it:
```bash
cd examples/pitchdeck_eval

llm-do pitch_evaluator --attachments input/deck.pdf --model $MODEL

# Or override configuration at runtime
llm-do pitch_evaluator --attachments input/deck.pdf \
  --set model=anthropic:claude-sonnet-4 \
  --set attachment_policy.max_total_bytes=20000000
```

**Note:** This example requires a model with native PDF reading (e.g., Anthropic Claude models). Not all models support PDF attachments.

## More Examples

Check the `examples/` directory for additional patterns:
- **[`greeter/`](examples/greeter/)** — Minimal conversational worker (shown above)
- **[`pitchdeck_eval/`](examples/pitchdeck_eval/)** — Multi-worker orchestration with PDF analysis (shown above)
- **[`approvals_demo/`](examples/approvals_demo/)** — A demo for tool approval system
- **[`calculator/`](examples/calculator/)** — Custom tools example with mathematical functions
- **[`web_searcher/`](examples/web_searcher/)** — Server-side tools with web search
- **`bootstrapping_pitchdeck_eval/`** — Autonomous worker creation workflow

## Key Features

- **Sandboxed file access**: Workers can only read/write within declared directories, with suffix filters and size limits
- **Worker delegation**: Workers call other workers like functions, with built-in allowlists and validation
- **Custom tools**: Add Python functions as tools in `workers/name/tools.py` for domain-specific operations
- **Server-side tools**: Enable provider-executed capabilities like web search and code execution (maps to PydanticAI's `builtin_tools`)
- **Tool approval system**: Configure which operations run automatically vs. require human review
- **Autonomous worker creation**: Let workers draft new worker definitions (requires approval)
- **Jinja2 templating**: Include files and compose prompts with `{{ file() }}` and `{% include %}`
- **Model flexibility**: Specify models per-worker or override at runtime with `--model`
- **Runtime configuration**: Override any worker config field with `--set` without editing YAML files

## How It Works

**Workers** are `.worker` files with [YAML front matter](https://python-frontmatter.readthedocs.io/) + instructions:
- `name`: Worker identifier
- `description`: What the worker does
- `model`: Which LLM to use (optional, can override with `--model`)
- `sandbox`: File access configuration (paths, permissions, file filters)
- `tool_rules`: Which tools require approval
- `allow_workers`: Which workers can be delegated to
- **Body** (after `---`): System prompt / instructions with optional Jinja2 templating

See [`docs/notes/archive/worker_format_migration.md`](docs/notes/archive/worker_format_migration.md) for complete field documentation.

**Sandbox** limits file access:
```yaml
sandbox:
  paths:
    input:
      root: ./input
      mode: ro
      suffixes: [.pdf, .txt]
    output:
      root: ./output
      mode: rw
```

**Worker delegation** lets workers call other workers via the `worker_call` tool:
```yaml
# In your worker's instructions, tell the LLM about delegation:
allow_workers:
  - pitch_evaluator

# The LLM can then use the worker_call tool:
# worker_call(worker="pitch_evaluator", input_data={...}, attachments=["input/deck.pdf"])
```

The orchestrator worker delegates work, the evaluator worker processes it—clean separation of concerns.

**Custom tools** extend workers with Python code:
```python
# workers/calculator/tools.py
def calculate_fibonacci(n: int) -> int:
    """Calculate the nth Fibonacci number."""
    if n <= 1:
        return n
    a, b = 0, 1
    for _ in range(2, n + 1):
        a, b = b, a + b
    return b
```

Functions in `tools.py` are automatically registered as [tools](https://ai.pydantic.dev/api/tools/) the LLM can call. Workers also have access to [toolsets](https://ai.pydantic.dev/api/toolsets/) for file operations (when a sandbox is configured). See [`examples/calculator/`](examples/calculator/) for a complete example.

**Server-side tools** enable provider-executed capabilities (web search, code execution) without local tool overhead:
```yaml
# workers/researcher.worker
---
name: researcher
server_side_tools:
  - tool_type: web_search
    max_uses: 5
---
You are a research assistant with web search capability...
```

These map to PydanticAI's [`builtin_tools`](https://ai.pydantic.dev/builtin-tools/). Available types: `web_search`, `code_execution`, `image_generation`, `url_context`. Provider support varies—see PydanticAI docs for compatibility. See [`examples/web_searcher/`](examples/web_searcher/) for a complete example.

See [`docs/worker_delegation.md`](docs/worker_delegation.md) for detailed design.

## Architecture

llm-do uses a clean, modular architecture with dependency injection to eliminate circular dependencies and maintain clear separation of concerns.

### Core Modules

- **`runtime.py`** (540 lines) — Main orchestration: worker delegation, creation, and execution lifecycle
- **`protocols.py`** (97 lines) — Interface definitions for dependency injection (`WorkerDelegator`, `WorkerCreator`)
- **`tools.py`** (282 lines) — Tool registration (sandbox ops, worker delegation, custom tools)
- **`execution.py`** (278 lines) — Agent runners and execution context preparation
- **`approval.py`** (76 lines) — Approval enforcement and session tracking
- **`types.py`** — Type definitions and data models
- **`registry.py`** — Worker definition loading and persistence
- **`sandbox.py`** — Sandboxed filesystem operations with security enforcement

### Key Design Patterns

**Protocol-Based Dependency Injection**: Tools depend on abstract protocols rather than concrete implementations, enabling recursive worker calls without circular imports:

```python
# tools.py depends on protocols (interfaces)
from .protocols import WorkerDelegator, WorkerCreator

def register_worker_tools(agent, context, delegator: WorkerDelegator, creator: WorkerCreator):
    # Tools use injected implementations
    @agent.tool(name="worker_call")
    async def worker_call_tool(...):
        return await delegator.call_async(...)

# runtime.py provides concrete implementations
class RuntimeDelegator:
    async def call_async(self, worker, input_data, attachments):
        # Actual worker delegation logic with approval enforcement
        ...
```

This architecture achieves clean separation of concerns, with `runtime.py` reduced to 540 lines while maintaining all functionality and zero circular dependencies.

## Documentation

- **[`docs/cli.md`](docs/cli.md)** — CLI reference and configuration overrides
- **[`docs/concept.md`](docs/concept.md)** — Design philosophy and motivation
- **[`docs/architecture.md`](docs/architecture.md)** — Internal architecture (runtime, sandbox, approval)
- **[`docs/worker_delegation.md`](docs/worker_delegation.md)** — Worker-to-worker delegation
- **[`examples/pitchdeck_eval/README.md`](examples/pitchdeck_eval/README.md)** — Multi-worker example walkthrough
- **[`AGENTS.md`](AGENTS.md)** — Development guide (for AI agents and humans)

## Design Philosophy

1. **Prompts are executables** — Workers are self-contained units you run from CLI or invoke from other workers
2. **Workers are artifacts** — Version controlled, auditable, refinable YAML files on disk
3. **Explicit over implicit** — Tool access and sandboxes declared in worker definitions
4. **Progressive hardening** — Start with flexible prompts, extract deterministic logic to Python tools later
5. **Composability** — Worker delegation feels like function calls

## Current Status

🧪 **Experimental** — Built on PydanticAI. Architecture is functional but APIs may change.

✅ **Working:**
- Worker definitions with YAML persistence
- Sandboxed file access with escape prevention
- Tool approval system
- Worker-to-worker delegation
- CLI with approval modes
- Comprehensive test coverage

🚧 **In Progress:**
- Output schema resolution
- Project scaffolding builder

## Caveats

**Security reality**: Sandboxes, attachment policies, and approval prompts reduce risk but aren't guarantees. Prompt injection and malicious inputs can trick LLMs into misusing granted tools. Treat approvals and sandboxes as mitigations that buy review time, not proof the system is locked down. Assume every worker handles untrusted data.

**Experimental status**: APIs may change. Not production-ready.

## Contributing

PRs welcome! See [`AGENTS.md`](AGENTS.md) for development guidance.

Quick points:
- Run `.venv/bin/pytest` before committing
- Follow `black` formatting, snake_case/PascalCase
- No backwards compatibility promise — breaking changes are fine if they improve design

## Acknowledgements

Built on [PydanticAI](https://ai.pydantic.dev/) for agent runtime and structured outputs.
