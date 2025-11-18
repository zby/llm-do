# llm-do

**Spec-driven agentic workflows for the `llm` CLI.**
Write workflows as natural-language specs, run them as tool-using agents, then progressively harden recurring patterns into tested code.

> In current LLM terminology: `llm-do` runs **single-agent, spec-guided agentic workflows**.
> The workflow skeleton lives in Markdown specs; the LLM implements an **agentic loop** over tools (bash, files, custom Python) inside those rails.

---

## What is this?

`llm-do` is a plugin for [llm](https://llm.datasette.io) that lets you:

1. **Describe workflows as specs** – write `SPEC.md` files in natural language.
2. **Run them with `llm do`** – call workflows using natural language commands.
3. **Let the LLM act as an agent** – it reads the spec and drives tool calls (bash, file IO, custom toolbox methods) in an **agentic loop**.
4. **Progressively harden** – when a pattern stabilizes, move it from spec to tested Python functions.

The key idea:

> **During exploration, the spec *is* the program.
> As patterns stabilize, you migrate them into deterministic, tested code.**

This gives you agent-like flexibility early, and classic "workflow + library" reliability later.

---

## Where `llm-do` fits in the LLM buzzword zoo

- **LLM workflow**
  Your directories (`examples/pitchdeck_eval/`, etc.) are *workflows*: a spec + config + toolbox that describe *what* should happen.

- **Agent / agentic loop**
  Each `llm do "…"` run spins up a **single agent** (your configured model) that:
  - reads the spec,
  - plans steps,
  - calls tools (`run_bash`, `read_file`, `write_file`, custom methods),
  - loops until the task is done.
  That plan → act → observe → re-plan cycle is the **agentic loop**.

- **Agentic workflow**
  Overall, `llm-do` gives you **agentic workflows**:
  - you define the high-level workflow in Markdown + TOML,
  - the LLM has local autonomy inside that frame to decide *how* to use tools to satisfy the spec.

If you want: think of `llm-do` as *"make my `llm` prompts into repeatable, agentic workflows that I can gradually refactor into a normal Python library."*

---

## Installation

```bash
llm install llm-do
```

Requirements:

```bash
pip install llm
llm install llm-anthropic
llm keys set anthropic
```

(Any `llm`-compatible provider with tools/functions support should work; Anthropic is the default in the examples.)

---

## Quick Start

1. **Create a `SPEC.md` describing your workflow:**

   ```markdown
   # My Workflow Specification

   You have access to tools: `run_bash`, `read_file`, `write_file`.

   ## Task: Process Documents

   When user says "process documents":

   1. Find all PDF files with `run_bash("find docs/ -name '*.pdf'")`
   2. For each PDF:
      - Read it (PDFs supported natively by the model)
      - Extract key information
      - Save a summary to `summaries/[filename].md` using `write_file`
   3. Report what was processed
   ```

2. **Run tasks with natural language:**

   ```bash
   llm do "process documents"
   llm do "process documents from yesterday"
   llm do "process the urgent document"
   ```

Under the hood, `llm-do`:

* loads `SPEC.md` as part of the system prompt,
* exposes a toolbox of tools,
* lets the model decide which tools to call and in what order, in a loop, until the task is complete.

---

## Usage

Basic usage (spec discovered via config):

```bash
llm do "your task description"
```

Explicit spec file:

```bash
llm do "your task" --spec path/to/SPEC.md
```

Working directory:

```bash
llm do "your task" -d /path/to/project
```

Model selection:

```bash
llm do "your task" -m claude-3-5-sonnet
```

Quiet mode:

```bash
llm do "your task" -q
```

Custom toolbox:

```bash
llm do "process files" --toolbox myproject.tools.MyToolbox
```

Tool approval (manually approve each tool call):

```bash
llm do "your task" --ta
llm do "your task" --tools-approve
```

`llm-do` follows `llm`'s normal model-selection rules: it uses your default model unless you override it with `-m` / `--model` or a named alias.

> **Note:** `llm-do` requires an explicit spec path one way or another:
> either via `--spec` or via `[workflow].spec` in `llm-do.toml` in the working directory.

---

## Workflow configuration (`llm-do.toml`)

Workflows carry their configuration in `llm-do.toml` in the working directory.
This is also how `llm-do` discovers the spec when `--spec` is omitted.

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

* `workflow.spec` – default spec path when `--spec` is omitted
* `model.required_attachment_types` – capability checks (PDF, audio, etc.)
* `model.allowed_models` – constrain to vetted model IDs / aliases
* `prompt.template` – reuse a standard `llm` template
* `prompt.params` – parameters passed into the template along with `spec`, `spec_path`, `task`, and `working_dir`

This lets you ship directories like `examples/pitchdeck_eval/` that:

* enforce "must be PDF-capable",
* reuse a richer prompt template,
* and still keep `llm do "…"` one-liner simple for users.

---

## Tools and toolboxes

### Base toolbox

The default toolbox exposes:

* `run_bash(command)` – run shell commands
* `read_file(path)` – read text files
* `write_file(path, content)` – write files

These are the primitive tools your agentic loop uses to interact with the environment.

### Custom toolboxes (progressive hardening in code)

Extend `BaseToolbox` to add domain-specific, hardened logic:

```python
# myproject/tools.py
from llm_do import BaseToolbox
import re

class MyToolbox(BaseToolbox):
    def normalize_filename(self, filename: str) -> str:
        """Remove spaces and special chars from filename."""
        name = filename.replace(".pdf", "")
        return re.sub(r"[^a-zA-Z0-9-]", "", name.replace(" ", ""))

    def get_metadata(self, path: str) -> dict:
        """Extract file metadata."""
        # Your hardened logic here
        ...
```

Use it with:

```bash
llm do "process files" --toolbox myproject.tools.MyToolbox
```

Now the spec can say "normalize filenames" and the agent calls your hardened function instead of reinventing it every run.

---

## Progressive Hardening (from agentic spec → deterministic code)

Typical evolution:

**Week 1 – Pure spec-driven (maximally agentic)**

* You write in `SPEC.md`:

  > When processing files:
  >
  > * Normalize filenames (remove spaces, special characters)
  > * …

* The LLM figures out how to do that via `run_bash` etc., but may be inconsistent.

**Week 2 – Extract pattern into a hard tool**

* You add a `normalize_filename()` implementation in your toolbox
* Add unit tests for edge cases
* Update the spec to say "call `normalize_filename`" rather than describing the logic

**Week 3+ – Keep migrating**

* Anything that repeats and matters for correctness moves into code.
* Specs focus on *orchestration and intent*, not low-level string wrangling.

Over time you end up with:

* **Specs**: human-friendly workflow definitions ("evaluate all new pitchdecks in this folder")
* **Toolbox**: deterministic, tested library functions
* **Agentic loop**: glues them together at runtime and handles the fuzzy bits ("what counts as *new*?" "where is the urgent deck?").

---

## How it works (conceptual flow)

```text
User: llm do "process documents from yesterday"
    ↓
llm-do plugin:
  - Loads SPEC.md as a system / context prompt
  - Applies llm-do.toml constraints (model allowlist, capabilities)
  - Provides a toolbox to the model
    ↓
LLM (agent):
  - Reads the workflow spec
  - Interprets "from yesterday" → e.g. -mtime -1
  - Calls run_bash("find docs/ -name '*.pdf' -mtime -1")
  - Reads PDFs (if model supports it)
  - Calls write_file() to save results
    ↓
Result: Task executed according to the spec and tools
```

---

## Examples

See [`examples/pitchdeck_eval/`](examples/pitchdeck_eval/) for a full example:

* AI-assisted pitchdeck evaluation workflow
* Custom toolbox with hardened helpers
* Rich `SPEC.md` with multiple workflows
* Shows progressive hardening from spec → code

---

## Development philosophy

### Spec-driven, agentic development

1. **Write specs** – edit `SPEC.md` to describe the workflow you want.
2. **Run them** – `llm do "your command"`.
3. **Observe** – inspect what tools were called, in what order.
4. **Iterate** – update the spec to tighten behavior or add branches.
5. **Harden** – when something stabilizes and matters, move it into code + tests.
6. **Repeat** – specs stay flexible; the toolbox becomes your stable API.

### When to harden

**Harden into code when:**

* ✅ The pattern repeats
* ✅ Correctness / safety really matters
* ✅ You want unit tests and observability
* ✅ Performance or latency is important

**Keep in spec when:**

* ❌ You're still exploring
* ❌ It's rare or low-stakes
* ❌ You want stylistic variation or experimentation

---

## Features

* 🧠 **Agentic workflows** – single-agent, tool-using loops guided by Markdown specs
* 📄 **Spec-driven design** – workflows live in plain `SPEC.md` files
* 🧰 **Tool-based architecture** – bash + file IO + your own Python tools
* 🔒 **Progressive hardening** – from "prompt as program" to tested functions
* 🔍 **Transparent execution** – see what tools run with what arguments
* 🧩 **Built on `llm`** – reuse your existing models, keys, templates, and aliases

---

## Contributing

Contributions welcome! Interesting areas:

* More example workflows (data pipelines, codegen, personal automations)
* Extra base tools and safer defaults
* Testing utilities / harnesses for specs + toolboxes
* Documentation and patterns for larger agentic workflows

---

## License

Apache-2.0

Built on [llm](https://llm.datasette.io) by Simon Willison.

---

**Write specs. Run them as agents. Harden what works.**
