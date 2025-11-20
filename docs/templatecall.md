# TemplateCall and llm_worker_call: Design and Motivation

This document explains why `TemplateCall` exists, how it fits into the `llm-do` plugin architecture, and how the public tool `llm_worker_call` exposes it to models.

## Programmer vs LLM Perspective

- **Programmers** work with `TemplateCall` directly in Python/YAML. Their mental model is "call another template in a safe, controlled way" with:
  - template allowlists or locks
  - attachment validation (count, size, suffix)
  - fragment handling for extra context
  - structured outputs via `expect_json` + `schema_object`
  - model fallback and tool security toggles
- **LLMs** only see a generic tool named `llm_worker_call` that means "call a named LLM worker (preconfigured template) with its own context and attachments." The model chooses a `worker_name`, provides `input`, optional `attachments` and `extra_context`, and (optionally) `params`/`expect_json`. The worker's prompt, model, and allowed tools are defined elsewhere; the caller only passes arguments.

## What TemplateCall Does

`TemplateCall` is a toolbox that lets one template invoke another template with controlled inputs. It provides:

- **Template allowlisting:** Only approved templates can be called (via glob patterns or specific locks)
- **Attachment validation:** File count, size, and suffix restrictions enforced before passing to the LLM
- **Fragment support:** Pass text snippets (procedures, rubrics, extracted sections) as additional context
- **Structured outputs:** Optional JSON parsing and normalization via `expect_json=True` (only when the template defines `schema_object`).
- **Model selection:** Use the template's `model` when present; otherwise fall back to the global default model configured in `llm`.
- **Security defaults:** Inline Python functions embedded in templates are ignored.

Example configuration:

```python
TemplateCall(
  allow_templates=["pkg:*", "./templates/**/*.yaml"],
  lock_template="templates/pitchdeck-single.yaml",
  allowed_suffixes=[".pdf", ".txt"],
  max_attachments=1,
  max_bytes=15_000_000,
)
```

Programmer-facing API call:

```python
result = TemplateCall().run(
  template="templates/evaluate-one.yaml",
  input="Evaluate this document",
  attachments=[{"path": "file.pdf"}],
  fragments=[{"path": "PROCEDURE.md"}],
  params={"detail_level": "high"},
  expect_json=True,
)
```

LLM-facing tool surface (wired to the same implementation):

```yaml
# Conceptual view of the tool the LLM sees
- name: llm_worker_call
  description: Call a named LLM worker with its own context and optional file attachments.
  params:
    worker_name: which worker/template to call
    input: main text to process
    attachments: list of files to attach
    extra_context: optional snippets/rubrics
    params: optional template parameters
    expect_json: request structured output when available
```

`llm_worker_call` maps parameters like this: `worker_name` → `template`, `extra_context` → `fragments`, while `attachments`, `params`, and `expect_json` pass through with the same validation rules. (TODO: Consider adding additional tool aliases such as `delegate_task` or `call_subtask` if certain models respond better to alternate names.)

This enforces allowlists, file size/type restrictions, and attachment limits. It also supports template locking (force all calls to use a specific vetted template) and structured outputs via `expect_json=True`. Only set `expect_json=True` if the target template defines `schema_object`; otherwise TemplateCall will error.

### Model selection

TemplateCall resolves the model in two steps:

1. The `model:` field on the target template
2. The global default model returned by `llm.get_default_model()`

There is no per-TemplateCall default model parameter.

### Inline functions are ignored

`TemplateCall` skips inline `functions:` blocks defined inside templates. Register Python tools/toolboxes normally and reference them via `tools:` entries instead of embedding code inside YAML.

## Why Recursion Matters

When a template can call another template, the template language becomes recursively closed. This is useful for a couple of reasons:

1. **Composability:** Common patterns like "choose files → process files" or "triage → escalate" become reusable building blocks instead of bespoke scripts.
2. **Uniformity:** Sub-calls inherit the same auditing, logging, and security guarantees as top-level template invocations.
3. **Programmer ergonomics:** Clean recursion is easier to reason about than ad-hoc orchestration glue. You can build workflows that feel like composing functions.

This isn't just theoretical—it matters in practice. When your orchestrator needs to handle edge cases (retry logic, partial failures, dynamic template selection), having a consistent primitive for "call another template" makes those extensions straightforward.

## The Two-Step Pattern in Practice

Here's a simplified example showing how `TemplateCall` and `llm_worker_call` fit into a pitch deck evaluation workflow:

```yaml
# pitchdeck-orchestrator.yaml (pseudo-YAML, simplified)
system: |
  You orchestrate pitch deck evaluations. First list available PDFs,
  then process each one using the locked evaluation template.

tools:
  - Files_list
  - llm_worker_call

params:
  max_decks: 5

# (Workflow steps would go here in real implementation)
# 1. Call Files_list to get pipeline/*.pdf
# 2. Choose up to max_decks files based on task description
# 3. For each chosen file:
#    - Call llm_worker_call with:
#        worker_name: "templates/pitchdeck-single.yaml" (locked)
#        attachments: [the PDF]
#        extra_context: ["PROCEDURE.md"]
#        expect_json: true
# 4. Write results to evaluations/ via Files_write_text
```

The locked `pitchdeck-single.yaml` template expects exactly one PDF, returns structured JSON, and doesn't need to know anything about directory traversal or file selection. The orchestrator handles selection; the sub-template handles evaluation. Clean separation.

## Benefits

- **Tight context:** Each sub-call is scoped to a single unit of work (one file, one task) rather than batching everything into a single bloated prompt.
- **Guardrails by construction:** File size caps, suffix restrictions, and template locks are enforced in code, not by hoping the LLM respects instructions.
- **Reproducibility:** Sub-calls are explicit, loggable, and re-runnable. You can audit exactly which template processed which files with which parameters.
- **Iteration speed:** Refining the evaluation template doesn't require touching the orchestrator. They evolve independently.

## When to Use TemplateCall

Reach for `TemplateCall` when:

- You need LLM-mediated selection followed by guarded execution
- You want to pre-build context (extract sections, generate summaries) then use those in a final decision call
- You're hardening a workflow: keep choices in templates, migrate brittle logic to Python tools, lock sub-templates as they stabilize

For simpler tasks (single-file operations, no selection step), you probably don't need it. Just use a regular template.

## Comparison to Other Approaches

**Hard-coding in Python:**
Fine for production workflows with stable requirements, but slow to iterate. Every change requires editing code, running tests, redeploying.

**Single mega-template:**
Works for simple cases but doesn't scale. Context bloats, instructions drift, guardrails become suggestions rather than enforced constraints.

**Shell scripts calling `llm` CLI:**
Closer to what `TemplateCall` does, but harder to audit, no built-in attachment validation, and mixing shell logic with template logic gets messy fast.

`TemplateCall` sits in between: flexible enough for iteration, structured enough for safety, and composable enough to build complex workflows without custom code.

## Example Workflow: Pitch Deck Evaluation

The `examples/pitchdeck_eval` directory demonstrates this pattern. The orchestrator:

1. Lists PDFs in `pipeline/` using `Files("ro:pipeline")`
2. Chooses which ones to evaluate (based on the task description)
3. Calls the locked `pitchdeck-single.yaml` template once per PDF via `llm_worker_call`, passing:
   - The PDF as an attachment
   - `PROCEDURE.md` as a fragment (shared evaluation rubric)
   - Parameters like `deck_id` derived from the filename
4. Converts the returned JSON to Markdown
5. Writes the result to `evaluations/` using `Files("out:evaluations")`

Each PDF gets its own isolated LLM call with tightly scoped inputs. If the evaluation template needs refinement, you edit it once and all subsequent runs use the updated version. The orchestrator doesn't change.

Run it like this:

```bash
cd examples/pitchdeck_eval
llm -t templates/pitchdeck-orchestrator.yaml \
  "evaluate every pitch deck in pipeline/ using the procedure"
```

## Implementation Notes

The `TemplateCall` toolbox is implemented in `llm_do/tools_template_call.py`. Key details:

- Template paths support `pkg:` prefix for package-bundled templates and filesystem paths for user templates
- Attachment validation happens before invoking `llm` (fail fast if files are too large or have wrong extensions)
- `expect_json=True` attempts to parse the response as JSON (only allowed when the template defines `schema_object`) and returns a normalized structure
- Model selection follows two steps: (1) the template's explicit `model` value, or (2) the global default model configured in `llm`.
- Inline Python `functions:` blocks in sub-templates are ignored; reference Python toolboxes via `tools:` instead.
- Fragment files are read and passed as text to the template (useful for procedures, rubrics, or context snippets)
- From the LLM's point of view, all of this is exposed as the single `llm_worker_call` tool. The model only decides which `worker_name` to call, what `input` to send, which files to attach, and any extra snippets of context.

There is currently no external code depending on this API, so the naming shifts from `TemplateCall_run` → `llm_call` → `llm_worker_call` are not breaking changes. We're optimizing names now for clarity of mental models (programmer vs LLM, worker vs raw call) before external adoption.

## Future Directions

Possible enhancements:

- **Streaming support:** For long-running sub-calls, stream intermediate results
- **Retry logic:** Built-in retry with exponential backoff for transient failures
- **Cost tracking:** Log token usage per sub-call for budget analysis
- **Template composition:** Allow templates to import/extend other templates (beyond just calling them)

These aren't priorities yet—better to keep the initial design simple and see what usage patterns emerge.

## Summary

`TemplateCall` solves a specific problem: you need a second LLM call, but you want to keep the orchestration logic in templates rather than hard-coding it in Python. It provides a clean, recursive primitive that makes multi-step workflows composable, auditable, and safe.

For the two-step "choose → then act" pattern, it's a natural fit. For more complex workflows (multi-stage pipelines, conditional branching, parallel execution), it's still early days—we'll see what patterns emerge as people use it.
