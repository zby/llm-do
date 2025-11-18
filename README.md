# llm-do

**Spec-driven automation with LLM and progressive hardening**

Write workflows as natural language specifications, execute them with LLM + tools, progressively harden proven patterns into tested functions.

## What is this?

`llm-do` is a plugin for [llm](https://llm.datasette.io/) that enables spec-driven automation:

1. **Write specs in natural language** - Define workflows in `SPEC.md` files
2. **Execute with `llm do`** - Run tasks using natural language commands
3. **LLM interprets & executes** - Your configured llm model reads the spec and calls tools (bash, files, custom functions)
4. **Progressive hardening** - Extract proven patterns into tested functions over time

**Key insight**: Specs ARE the program during development. Code is optimization for proven patterns.

## Installation

```bash
llm install llm-do
```

Requires `llm` with Anthropic plugin:

```bash
pip install llm
llm install llm-anthropic
llm keys set anthropic
```

## Quick Start

1. **Create a `SPEC.md` file** describing your workflow:

```markdown
# My Workflow Specification

You have access to tools: `run_bash`, `read_file`, `write_file`.

## Task: Process Documents

When user says "process documents":

1. Find all PDF files with `run_bash("find docs/ -name '*.pdf'")`
2. For each PDF:
   - Read it (PDFs supported natively)
   - Extract key information
   - Save summary to `summaries/[filename].md` using `write_file`
3. Report what was processed
```

2. **Execute tasks with natural language**:

```bash
llm do "process documents"
llm do "process documents from yesterday"
llm do "process the urgent document"
```

The LLM reads your `SPEC.md`, interprets the command, and executes using available tools.

## Usage

```bash
# Basic usage (spec defined via llm-do.toml)
llm do "your task description"

# Specify spec file
llm do "your task" --spec path/to/SPEC.md

# Specify working directory
llm do "your task" -d /path/to/project

# Use different model
llm do "your task" -m claude-opus-4.1

# Quiet mode (less output)
llm do "your task" -q

# Use custom toolbox
llm do "your task" --toolbox myproject.tools.MyToolbox
```

`llm do` follows the same model selection rules as the rest of `llm`: it will use your configured default model unless you override it with `-m/--model` or a named alias.

`llm-do` now requires an explicit spec path. Provide one via `--spec` or define `[workflow].spec` in `llm-do.toml` within the working directory.

## Workflow Configuration

Workflows carry their requirements in an `llm-do.toml` located in the working directory; this file is also how `llm-do` discovers the spec when `--spec` is omitted. Example:

```toml
[workflow]
spec = "SPEC.md"

[model]
required_attachment_types = ["application/pdf"]  # require models with PDF support
allowed_models = ["anthropic/claude-3.5-sonnet"]

[prompt]
template = "pitchdeck-evaluator"

[prompt.params]
spec_title = "Pitchdeck Evaluation Framework"
```

- `workflow.spec` overrides which spec file is loaded when `--spec` is omitted.
- `model.required_attachment_types` forces a capability check (PDF support, audio, etc.).
- `model.allowed_models` constrains the workflow to a vetted list of model IDs or aliases.
- `prompt.template` tells `llm-do` to load a standard llm template; `prompt.params` are passed into it, along with `spec`, `spec_path`, `task`, and `working_dir`.

This allows directories like `examples/pitchdeck_eval/` to require PDF-capable models and reuse richer llm templates without repeating boilerplate in every command.

## Available Tools

### Base Toolbox

The default toolbox provides:

- **`run_bash(command)`** - Execute shell commands
- **`read_file(path)`** - Read text files
- **`write_file(path, content)`** - Write files

### Custom Toolboxes

Extend `BaseToolbox` to add domain-specific tools:

```python
# myproject/tools.py
from llm_do import BaseToolbox
import re

class MyToolbox(BaseToolbox):
    def normalize_filename(self, filename: str) -> str:
        """Remove spaces and special chars from filename."""
        name = filename.replace('.pdf', '')
        return re.sub(r'[^a-zA-Z0-9-]', '', name.replace(' ', ''))

    def get_metadata(self, path: str) -> dict:
        """Extract file metadata."""
        # Your hardened logic here
        pass
```

Use it with:

```bash
llm do "process files" --toolbox myproject.tools.MyToolbox
```

## Progressive Hardening

Start with specs, gradually extract code:

**Week 1**: Pure spec-driven
```markdown
When processing files:
- Normalize filenames (remove spaces, special chars)
- ...
```

LLM figures it out each time (might be inconsistent).

**Week 2**: Extract pattern to hardened tool
```python
def normalize_filename(self, filename: str) -> str:
    """Normalize filename - hardened, tested function."""
    name = filename.replace('.pdf', '')
    return re.sub(r'[^a-zA-Z0-9-]', '', name.replace(' ', ''))
```

Add tests:
```python
def test_normalize():
    assert normalize_filename("File (2024).pdf") == "File2024"
```

**Week 3-4**: Extract more patterns as they stabilize

You get **rapid iteration** (change specs, test immediately) AND **reliable code** (tested functions for critical logic).

## Examples

See [`examples/pitchdeck_eval/`](examples/pitchdeck_eval/) for a complete example:

- AI-powered pitchdeck evaluation system
- Custom toolbox with hardened functions
- Comprehensive `SPEC.md` with multiple workflows
- Shows progressive hardening in action

## Development Philosophy

### Spec-Driven Development

1. **Write specs** - Edit `SPEC.md` to describe what you want
2. **Test immediately** - Run `llm do "your command"`
3. **Observe behavior** - See what LLM does, what tools it calls
4. **Iterate on specs** - Refine workflow based on results
5. **Extract patterns** - When stable, harden into tested functions
6. **Keep iterating** - Natural language stays flexible while core logic becomes deterministic

### When to Harden

Extract patterns into tools when:

✅ Pattern repeats consistently
✅ Correctness is critical
✅ Want unit tests
✅ Performance matters

Don't harden when:

❌ Still experimenting
❌ Rare operation
❌ Want natural variation

## How It Works

```
User: "llm do 'process documents from yesterday'"
    ↓
llm-do plugin:
  - Loads SPEC.md as system prompt
  - Provides toolbox to Claude Sonnet
    ↓
Claude Sonnet:
  - Reads workflow spec
  - Interprets "from yesterday" → -mtime -1
  - Calls: run_bash("find docs/ -name '*.pdf' -mtime -1")
  - Reads PDFs directly (native PDF support)
  - Calls: write_file() to save results
    ↓
Result: Task completed according to spec
```

## Features

- **Natural language commands** - Flexible task descriptions
- **Spec-driven workflows** - Define logic in markdown
- **Tool-based architecture** - Mix bash, files, custom functions
- **Progressive hardening** - Start flexible, extract code gradually
- **Built on llm** - Leverage existing infrastructure
- **Transparent** - See tool calls, understand execution

## Contributing

Contributions welcome! Areas:

- Additional example projects
- Base toolbox improvements
- Testing utilities
- Documentation

## License

Apache-2.0

## Credits

Built on [llm](https://llm.datasette.io/) by Simon Willison.

---

**Write specs. Execute with LLM. Harden what works.**
