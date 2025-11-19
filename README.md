# llm-do

**A plan for template-driven agentic workflows for the `llm` CLI**

## Vision

Build a **template-first plugin** for [llm](https://llm.datasette.io) that lets
users orchestrate complex workflows using nothing more than `llm -t <template>
"task"`. Instead of shipping a bespoke CLI, we'll contribute reusable toolboxes
and ready-to-run templates that demonstrate a "progressive hardening" approach.

## Core Philosophy

1. **Templates as executable specs**
   - Everything starts as an `llm` template (`.yaml`) capturing prompts,
     schemas, allowed tools, and guardrails
   - Templates remain the primary interface

2. **Domain logic migrates from prompts to Python**
   - Keep workflow rules in templates during exploration
   - Move fragile pieces (parsing, validation, formatting) into tested Python
     toolboxes as patterns stabilize

3. **Context reduction via sub-calls**
   - Large workflows decompose into focused sub-LLM calls with tightly scoped
     inputs
   - Example: "evaluate exactly this PDF with this procedure" keeps each call
     grounded

## Planned Structure

This will be a clean break—**no backwards compatibility** with any previous `llm
do` command. Target package layout:

```
llm_do/
  __init__.py
  plugin.py                   # registers toolboxes with llm
  tools_files.py              # sandboxed filesystem operations
  tools_template_call.py      # sub-call orchestration
  templates/
    generic-orchestrator.yaml # domain-agnostic bootstrapper
    pitchdeck-single.yaml     # reference sub-template
examples/
  pitchdeck_eval/             # end-to-end demo
    PROCEDURE.md
    pipeline/
    evaluations/
    templates/
```

## Intended Usage

Users will run templates directly:

```bash
llm -t llm_do/templates/generic-orchestrator.yaml "task description"
```

Template parameters pass through with `-p` as usual.

---

## Installation Plan

Once published:

```bash
llm install llm-do
```

Dependencies will be minimal: `llm>=0.26` and `PyYAML`. Users will install model
providers separately via `llm install ...` and configure API keys as usual.

---

## Toolboxes to Build

### `Files` Toolbox

Will provide sandboxed filesystem operations. Planned interface:

```python
Files("ro:pipeline")      # read-only sandbox at ./pipeline
Files("out:evaluations")  # writable output sandbox
```

**Methods to implement:**
- `Files_list(pattern="**/*")` — glob within sandbox
- `Files_read_text(path, max_chars=200_000)` — read with size limits
- `Files_write_text(path, content)` — write (denied in `ro:` mode)

**Design requirements:**
- All paths resolved inside sandbox root
- Path escape attempts raise errors immediately
- `out:` sandboxes auto-create on first write
- `ro:` sandboxes must exist before instantiation

### `TemplateCall` Toolbox

Will orchestrate sub-LLM calls with tight guardrails. Example configuration:

```python
TemplateCall(
  allow_templates=["pkg:*", "./templates/**/*.yaml"],
  lock_template="pkg:pitchdeck-single.yaml",
  allowed_suffixes=[".pdf", ".txt"],
  max_attachments=1,
  max_bytes=15_000_000,
)
```

**Primary method:**
- `run(template, input="", attachments=None, fragments=None, params=None,
  expect_json=False)`

**Implementation requirements:**
- Validate attachments (count, size, suffix) before passing to `llm`
- Support filesystem templates and package templates via `pkg:` prefix
- Ignore inline Python functions by default (security); add opt-in override
- When `expect_json=True`, parse and normalize JSON responses

---

## Templates to Ship

### `generic-orchestrator.yaml`

A domain-agnostic bootstrapper that will:

1. Accept natural-language task + optional `sub_template` parameter
2. Infer the unit of work ("each PDF in pipeline/", "each Markdown in notes/")
   by inspecting directories with `Files`
3. Generate a dedicated sub-template if needed, save to
   `templates/generated/<slug>.yaml`
4. Execute sub-template for each unit via `TemplateCall` with attachments +
   procedure fragments
5. Write outputs (typically Markdown) back via `Files`

**Target invocation:**

```bash
llm -t llm_do/templates/generic-orchestrator.yaml \
  -p max_units=5 \
  "evaluate every PDF in pipeline/ and write summaries to evaluations/"
```

Should report which sub-template was used/created and unit count.

### `pitchdeck-single.yaml`

Reference sub-template for evaluating one pitch deck. Will expect:

- Single PDF attachment
- Optional procedure fragments
- JSON output schema: `deck_id`, `file_slug`, `summary`, `scores`, `verdict`,
  `red_flags`

Primarily invoked by orchestrators but runnable standalone for experimentation.

---

## Example: Pitch Deck Evaluation

Will demonstrate the "one sub-call per file" pattern. Planned directory layout:

```
examples/pitchdeck_eval/
  PROCEDURE.md                 # evaluation rubric shared with every call
  pipeline/                    # users drop PDF pitch decks here
  evaluations/                 # Markdown outputs land here
  templates/
    pitchdeck-single.yaml      # copy of single-call template
    pitchdeck-orchestrator.yaml
```

**How `pitchdeck-orchestrator.yaml` will work:**

1. Use `Files("ro:pipeline")` to list incoming PDFs
2. Call `TemplateCall_run` once per file, locked to `pkg:pitchdeck-single.yaml`
3. Convert returned JSON to Markdown via inline helper functions
4. Save results with `Files("out:evaluations")`

**Key benefit:** Each PDF processed in isolation keeps context tight and makes
guardrails straightforward (file size limits, suffix restrictions, unit caps).

**Target invocation:**

```bash
cd examples/pitchdeck_eval
llm -t templates/pitchdeck-orchestrator.yaml \
  "evaluate every pitch deck in pipeline/ using the procedure"
```

Users would populate `pipeline/` with PDFs; template reports which files were
processed and output locations.

---

## Progressive Hardening Workflow

The intended user journey:

1. **Exploration phase**
   - Run `generic-orchestrator` without `sub_template` parameter
   - Let it infer the per-unit template and generate a scaffold

2. **Specialization phase**
   - Copy generated template to a named file (e.g.,
     `templates/pitchdeck-single.yaml`)
   - Refine system prompt, add schema fields, tighten instructions

3. **Locking phase**
   - Update orchestrator to use vetted template via `-p
     sub_template=templates/pitchdeck-single.yaml`
   - Or set `lock_template` in TemplateCall configuration

4. **Hardening phase**
   - When logic feels brittle (slug generation, markdown rendering, scoring
     math), migrate from template `functions:` to Python helpers
   - Expose helpers via custom toolboxes for reuse across templates

Over time, templates stay expressive but critical behaviors move into
version-controlled Python code.

---

## Implementation Plan

**Initial milestone:**

- [ ] Core `Files` toolbox with sandbox enforcement
- [ ] Core `TemplateCall` toolbox with attachment validation
- [ ] `generic-orchestrator.yaml` template
- [ ] `pitchdeck-single.yaml` reference template
- [ ] Pitch deck evaluation example
- [ ] Basic test coverage (`pytest`)
- [ ] Plugin registration with `llm`

**Future enhancements:**

- Additional domain templates
- More toolboxes for common patterns
- Progressive hardening documentation and guides

**Development notes:**

- Templates will live under `llm_do/templates/` and `examples/*/templates/`
- Keep prompts in YAML; move to Python only when fragility demands it
- PRs welcome for new templates, toolboxes, or workflow documentation
