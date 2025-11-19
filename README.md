# llm-do

**Template-driven agentic workflows for the `llm` CLI, with progressive
hardening.**

`llm-do` is a **template-first plugin** for [llm](https://llm.datasette.io).
Instead of shipping a bespoke CLI, it contributes a set of reusable toolboxes
and ready-to-run templates that let you orchestrate complex workflows using
nothing more than `llm -t <template> "task"`.

The philosophy:

1. **Templates are executable specs.**
   Everything starts as an `llm` template (`.yaml`) that captures prompts,
   schemas, allowed tools, and guardrails.
2. **Domain logic grows from prompts into Python helpers.**
   Keep workflow rules in templates while exploring, then migrate fragile pieces
   (parsing, validation, formatting) into repeatable Python toolboxes over time.
3. **Context stays small thanks to sub-calls.**
   Large workflows use the bundled `TemplateCall` tool to spin up **sub-LLM
   calls** with tightly scoped inputs (e.g. "evaluate exactly this PDF with this
   procedure"), so each call stays grounded.

There is **no backwards compatibility layer** with the previous `llm do`
command. The package now consists of:

```
llm_do/
  __init__.py
  plugin.py            # registers toolboxes with llm
  tools_files.py       # sandboxed filesystem helper
  tools_template_call.py
  templates/           # shipped templates (generic orchestrator, etc.)
examples/
  pitchdeck_eval/      # end-to-end demo built on templates + sub-calls
```

Use it the same way you would run any `llm` template:

```bash
llm -t llm_do/templates/generic-orchestrator.yaml "task description"
```

Pass template parameters with `-p` as usual (see below).

---

## Installation

```bash
llm install llm-do
```

The plugin depends on `llm>=0.26` and `PyYAML`. Install any model providers you
need via `llm install ...` and make sure their API keys are configured.

---

## Bundled toolboxes

### `Files`

```
Files("ro:pipeline")   # read-only sandbox rooted at ./pipeline
Files("out:evaluations")
```

* Methods:
  * `Files_list(pattern="**/*")`
  * `Files_read_text(path, max_chars=200_000)`
  * `Files_write_text(path, content)` (read-only sandboxes refuse writes)
* Paths are resolved inside the sandbox root. Any attempt to escape the sandbox
  raises an error.
* `out:` sandboxes are created on demand; `ro:` sandboxes must already exist.

### `TemplateCall`

```
TemplateCall(
  allow_templates=["pkg:*", "./templates/**/*.yaml"],
  lock_template="pkg:pitchdeck-single.yaml",
  allowed_suffixes=[".pdf", ".txt"],
  max_attachments=1,
  max_bytes=15_000_000,
)
```

* `run(template, input="", attachments=None, fragments=None, params=None,
  expect_json=False)` executes another template with a constrained context.
* Attachments are validated against count/size/suffix limits before being
  transformed into `llm.Attachment` objects.
* Templates can be loaded from the filesystem or from the package via `pkg:`
  (`pkg:pitchdeck-single.yaml`).
* Inline Python functions defined inside templates are ignored by default; pass
  `ignore_functions=False` if you need them and trust the source.
* When `expect_json=True`, responses are parsed and re-dumped so callers always
  get normalized JSON text back.

---

## Shipped templates

### `llm_do/templates/generic-orchestrator.yaml`

A domain-agnostic bootstrapper:

1. Takes a natural-language task plus optional `sub_template` parameter.
2. Figures out the unit of work ("each PDF in pipeline", "each Markdown in
   notes", etc.) by inspecting directories via `Files`.
3. Generates a dedicated sub-template if one is not provided and saves it under
   `templates/generated/<slug>.yaml`.
4. Executes that sub-template for each unit using `TemplateCall`, passing along
   attachments and procedure fragments.
5. Writes normalized outputs (usually Markdown) back through `Files`.

Run it with:

```bash
llm -t llm_do/templates/generic-orchestrator.yaml \
  -p max_units=5 \
  "evaluate every PDF in pipeline/ and write summaries to evaluations/"
```

The template prints which sub-template it used/created and how many units were
processed so you can iterate quickly.

### `llm_do/templates/pitchdeck-single.yaml`

A reference sub-template that evaluates a single pitch deck. It expects:

* one PDF attachment (`deck.pdf`),
* optional fragments containing the evaluation procedure,
* JSON output with fields like `deck_id`, `file_slug`, `summary`, `scores`,
  `verdict`, and `red_flags`.

It is primarily used by the example orchestrator but you can run it directly if
you want to experiment with different prompts or schemas.

---

## Pitch deck evaluation example

`examples/pitchdeck_eval/` demonstrates the "one sub-call per file" pattern.
Directory layout:

```
examples/pitchdeck_eval/
  PROCEDURE.md                 # evaluation rubric shared with every call
  pipeline/                    # drop PDF pitch decks here
  evaluations/                 # outputs land here
  templates/
    pitchdeck-single.yaml      # copy of the single-call template
    pitchdeck-orchestrator.yaml
```

`templates/pitchdeck-orchestrator.yaml` is run directly with `llm -t` and does
all orchestration:

1. Uses `Files("ro:pipeline")` to list incoming PDFs.
2. Calls `TemplateCall_run` once per file while locking it to the packaged
   `pkg:pitchdeck-single.yaml` template.
3. Converts the returned JSON into Markdown via inline helper functions.
4. Saves results using `Files("out:evaluations")`.

Because each PDF is processed in isolation, the context stays tight and it's
straightforward to add more guardrails (limit file size, restrict attachment
suffixes, cap unit count, etc.).

Try it out:

```bash
cd examples/pitchdeck_eval
llm -t templates/pitchdeck-orchestrator.yaml \
  "evaluate every pitch deck in pipeline/ using the procedure"
```

Populate `pipeline/` with a few PDFs first (use your own data). The template
reports which files were processed and where the Markdown reports were saved.

---

## Progressive hardening path

1. **Exploration**
   * Start with `generic-orchestrator` and no `sub_template` parameter. Let it
     infer the per-unit template and create a scaffold for you.
2. **Template specialization**
   * Copy the generated template into a named file (for example
     `templates/pitchdeck-single.yaml`). Refine the system prompt, add schema
     fields, tighten instructions.
3. **Locking**
   * Update your orchestrator templates (or rerun `generic-orchestrator` with
     `-p sub_template=templates/pitchdeck-single.yaml`) so every future run uses
     the vetted template.
4. **Move fragile logic to Python**
   * When pieces of logic feel brittle (slug generation, markdown rendering,
     scoring math), migrate them from template `functions:` blocks into Python
     helpers inside your project. Expose those helpers via dedicated toolboxes
     so multiple templates can reuse them.

Rinse and repeat—templates stay expressive, but critical behaviors end up in
version-controlled Python.

---

## Development

* Run tests with `pytest`.
* Templates live under `llm_do/templates/` and `examples/*/templates/`.
* Keep prompts in YAML and move logic to Python only when repeated issues make
  that worthwhile.

PRs that add new domain templates, helper toolboxes, or documentation about the
progressive-hardening workflow are welcome.
