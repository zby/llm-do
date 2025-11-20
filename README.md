# llm-do

A plugin for [llm](https://llm.datasette.io) that adds orchestration tools for building multi-step LLM workflows.

## Background

This project started as a collection of prompts I ran in Claude Code to automate repetitive tasks—evaluating pitch decks, processing batches of documents, that sort of thing. It worked, but I quickly hit two limitations:

1. **Control over LLM execution.** I needed finer control over how the LLM was invoked—which model, what attachments, structured outputs, guardrails around file access.

2. **IDE dependency.** Tying useful automation to a particular IDE felt wrong. I wanted something portable that could run in CI, on a server, or from any terminal.

After several false starts trying to build a standalone tool, I realized Simon Willison's [llm](https://llm.datasette.io) library already solved most of the hard parts: model abstraction, template management, tool integration. So I pivoted to building a plugin that extends `llm` with orchestration primitives.

## Design Approach: Evolving Hybrid Systems

The plugin is designed around a specific workflow for developing hybrid LLM/deterministic systems:

1. **Start with templates as executable specs**
   - Begin with `llm` templates (`.yaml` files) that capture prompts, schemas, allowed tools, and guardrails
   - Templates are the primary interface—keep everything flexible and easy to iterate

2. **Migrate domain logic from prompts to Python**
   - During exploration, keep workflow rules in templates where they're easy to modify
   - As patterns stabilize and fragility emerges (parsing, validation, formatting, scoring math), move those pieces into tested Python toolboxes
   - This progression lets you start fast and harden incrementally

3. **Reduce context via decomposed sub-calls**
   - Large workflows with bloated prompts tend to drift and fail unpredictably
   - Instead, decompose into focused sub-LLM calls with tightly scoped inputs
   - Example: "evaluate exactly this PDF with this procedure" keeps each call grounded and reproducible

This approach treats template-based workflows as a starting point, not an end state. You prototype quickly with flexible templates, identify what's brittle, and gradually extract that logic into version-controlled, testable Python. Over time you end up with hybrid systems that balance LLM flexibility with deterministic reliability.

## What It Does

`llm-do` adds two main toolboxes to `llm` templates:

### Files

Sandboxed file operations for templates. You specify a directory prefix and access mode:

```python
Files("ro:pipeline")      # read-only access to ./pipeline
Files("out:evaluations")  # writable access to ./evaluations
```

Methods:
- `Files_list(pattern="**/*")` — glob within the sandbox
- `Files_read_text(path, max_chars=200_000)` — read with size limits
- `Files_write_text(path, content)` — write (blocked in `ro:` mode)

All paths are resolved inside the sandbox root. Attempts to escape (via `..` or absolute paths) raise errors immediately.

### TemplateCall / `llm_worker_call`

Lets one template invoke another with controlled inputs. Example configuration:

```python
TemplateCall(
  allow_templates=["pkg:*", "./templates/**/*.yaml"],
  lock_template="templates/pitchdeck-single.yaml",
  allowed_suffixes=[".pdf", ".txt"],
  max_attachments=1,
  max_bytes=15_000_000,
)
```

The `run` method mirrors how you'd use `llm -t <template>` from the command line:

```python
run(
  template,
  input="",
  attachments=[],
  fragments=[],
  params={},
  expect_json=False,
)
```

The public tool LLMs see is called `llm_worker_call`, which maps its parameters onto `TemplateCall.run`:

- `worker_name` → `template`
- `extra_context` → `fragments`
- `attachments`, `params`, and `expect_json` pass through unchanged

Think of `llm_worker_call` as "delegate this subtask to a separate LLM worker with its own context and attachments," backed by the safety checks above.

This enforces allowlists, file size/type restrictions, and attachment limits. It also supports template locking (force all calls to use a specific vetted template) and structured outputs via `expect_json=True`. Only set `expect_json=True` if the target template defines `schema_object`; otherwise TemplateCall will error.

Model selection is simple: TemplateCall uses the target template's `model` when present, otherwise it falls back to the global default model configured in `llm`. There is no per-toolbox default model parameter.

## Why TemplateCall?

The simplest case where you need a second LLM call is the two-step pattern: **choose what to do**, then **do it**. For example:

1. Look at a directory of PDFs and decide which ones need evaluation
2. For each chosen PDF, run a separate LLM call with that file attached and a detailed rubric

You could hard-code this in Python, but that makes iteration slow. A better approach is to keep the workflow logic in templates (easy to tweak) while adding a primitive that lets templates call other templates safely.

That's what TemplateCall does. It makes the template language recursively closed—a template can invoke another template (or even itself indirectly) with the same guardrails. This turns common orchestration patterns into reusable building blocks instead of one-off scripts. Programmers tend to like clean recursion, and it makes workflows easier to audit and reproduce.

See [`docs/templatecall.md`](docs/templatecall.md) for more detail on the design.

## Example: Pitch Deck Evaluation

The `examples/pitchdeck_eval` directory demonstrates the two-step pattern. Directory structure:

```
examples/pitchdeck_eval/
  PROCEDURE.md                 # shared evaluation rubric
  pipeline/                    # drop PDFs here
  evaluations/                 # Markdown outputs written here
  templates/
    pitchdeck-orchestrator.yaml
    pitchdeck-single.yaml
```

The orchestrator template:
1. Lists PDFs in `pipeline/` using `Files("ro:pipeline")`
2. Decides which files to process (could be all of them, or just a subset based on task description)
3. For each file, calls `pitchdeck-single.yaml` via `llm_worker_call`, passing the PDF as an attachment and `PROCEDURE.md` as a fragment
4. Writes the resulting Markdown evaluations to `evaluations/` using `Files("out:evaluations")`

Run it like this:

```bash
cd examples/pitchdeck_eval
llm -t templates/pitchdeck-orchestrator.yaml \
  "evaluate every pitch deck in pipeline/ using the procedure"
```

Each PDF gets processed in its own isolated LLM call, which keeps context tight and makes guardrails straightforward (file size limits, attachment restrictions, etc.).

## Progressive Hardening

The idea is to start with flexible templates and gradually move critical logic into Python as patterns stabilize:

1. **Exploration:** Use the worker bootstrapper to infer templates and scaffold workflows
2. **Specialization:** Copy the generated template, refine prompts, add schema constraints
3. **Locking:** Pin the orchestrator to a specific vetted sub-template via `lock_template`
4. **Hardening:** When brittle logic emerges (scoring math, slug generation, markdown formatting), migrate it from inline template functions to tested Python toolboxes

This keeps iteration fast while ensuring production workflows have solid foundations.

## Package Structure

```
llm_do/
  __init__.py
  plugin.py                   # registers toolboxes with llm
  tools_files.py              # Files toolbox implementation
  tools_template_call.py      # TemplateCall toolbox implementation
  templates/
    worker-bootstrapper.yaml  # bootstraps worker templates and calls them via llm_worker_call
examples/
  pitchdeck_eval/             # working pitch deck evaluation demo
```

This is a clean break from any prior `llm do` experiments—no backwards compatibility.

## Installation

Not yet published to PyPI. For now, install in development mode:

```bash
pip install -e .
```

Dependencies are minimal: `llm>=0.26` and `PyYAML`. You'll install model providers separately via `llm install ...` and configure API keys as usual.

## Current Status

The core toolboxes, pitch deck example, and worker bootstrapper are implemented and working. Test coverage is basic but growing.

This is an active experiment. The template format and toolbox APIs may change as usage patterns emerge.

## Contributing

PRs welcome for new templates, toolboxes, or workflow examples. If you're building something similar or have ideas for orchestration primitives, please open an issue.

## Acknowledgements

This plugin builds on [Simon Willison's llm library](https://llm.datasette.io/), which provides the foundation for model abstraction, template management, and tool integration. Without `llm`, this project would have required building all that infrastructure from scratch.
