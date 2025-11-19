# TemplateCall Motivation & Pattern

Great call—adding a short, opinionated "why" makes the TemplateCall idea click
faster for readers. The llm-do repo uses TemplateCall to separate planning from
execution: list and triage work with an outer template, then lock a vetted
sub-template for the risky, attachment-heavy calls.

## Motivation: Why TemplateCall?

TemplateCall exists to solve two recurring problems in template-driven workflows
with the `llm` CLI:

1. **Two-step actions (choose → then act).** Many useful automations take
   exactly two LLM calls:
   - **Call 1 (selection):** Look at a directory, triage, and decide what to
     process (which files, which units of work, which sub-template).
   - **Call 2 (execution):** For each chosen unit, run a dedicated,
     parameterized template with attachments and tight guardrails.

   `TemplateCall.run(...)` formalizes that second call. It enforces a template
   allowlist/lock (`allow_templates`, `lock_template`), file suffix and size
   caps, attachment count limits, and optional structured outputs
   (`expect_json=True`). That cleanly separates planning from doing, improves
   auditability ("which template ran on which files with which params?"), and
   makes the riskiest part—passing files—safe by construction.

2. **Building high-signal context incrementally.** Big prompts bloat, drift, and
   get brittle. A better pattern is to assemble context in small, verified
   pieces—summaries, extracted sections, or reusable procedure fragments—then
   feed those into a final sub-call. TemplateCall lets an outer template pass
   both attachments (e.g., one PDF) and fragments (e.g., `PROCEDURE.md`, rubric
   snippets, or prior extracts) into a focused sub-template. This keeps each
   call's context tight, explicit, and reproducible, aligning with the repo's
   "progressive hardening" arc where fragile behaviors migrate into tested
   Python toolboxes over time.

## Benefits at a Glance

- **Safety & control:** allowlisted templates, suffix filters, byte/attachment
  caps, and disabled inline Python by default.
- **Reproducibility:** sub-calls are small, well-scoped, and loggable—easy to
  re-run or diff.
- **Cost & quality:** less prompt sprawl; one sub-call per unit (e.g., per file)
  yields more consistent outputs.
- **Composability:** the same orchestrator can lock to a vetted sub-template via
  `lock_template` or select one dynamically, then pass per-unit params and
  fragments.

## Recursive Closure: Templates Calling Templates

TemplateCall introduces true recursion into the llm template model: a template
can safely call another template (or even itself indirectly) while remaining
inside the same guardrails. That closes the language over its own execution
primitive—`TemplateCall.run(...)`—so any workflow that can be expressed in two
LLM calls can be encoded entirely in templates without shelling out to bespoke
Python. This theoretical closure matters in practice: orchestration patterns
like "choose files → process files" or "triage → escalate" become reusable
building blocks rather than bespoke glue scripts, and they inherit the same
auditing, logging, and allowlist guarantees as single-call templates.

## Core Design (Recap)

```python
TemplateCall(
  allow_templates=["pkg:*", "./templates/**/*.yaml"],
  lock_template="pkg:pitchdeck-single.yaml",
  allowed_suffixes=[".pdf", ".txt"],
  max_attachments=1,
  max_bytes=15_000_000,
).run(
  template,
  input="",
  attachments=[],
  fragments=[],
  params={},
  expect_json=False,
)
```

This mirrors how users already work with llm templates (`llm -t ...`), just made
safer and more automatable inside another template.

## The "Choose Files → Process Files" Recipe (Illustrative)

Pseudo-YAML showing the two-call pattern; exact template syntax may evolve.

```yaml
# generic-orchestrator.yaml (excerpt, pseudo-YAML)
system: |
  You are an orchestrator. First decide what to process, then call the locked
  sub-template per file.

tools:
  - Files_list
  - TemplateCall_run

params:
  k: 5  # maximum number of files to process

steps:
  - name: list_candidates
    call: Files_list
    args: { pattern: "pipeline/**/*.pdf" }

  - name: choose_files
    prompt: |
      Here are candidate PDFs:
      {{ steps.list_candidates.output }}

      Choose up to {{ params.k }} files that best match the task: "{{ task }}".
      Return a JSON array of relative paths.
    expect_json: true

  - name: process_each
    for: file in {{ steps.choose_files.output }}
    call: TemplateCall_run
    args:
      template: "pkg:pitchdeck-single.yaml"  # or locked via config
      attachments:
        - { path: "{{ file }}" }            # validated by suffix/size/attachment limits
      fragments:
        - { path: "PROCEDURE.md" }          # shared rubric
      expect_json: true
```

This is exactly the one-sub-call-per-file pattern planned for the
`examples/pitchdeck_eval` demo: the orchestrator lists PDFs, picks which to
process, then invokes the locked single-deck template with that PDF plus the
procedure fragment; results are written to `evaluations/`.

## When to Reach for TemplateCall

- You need LLM-mediated selection (triage, ranking, bucketing) followed by
  guarded execution.
- You want to pre-bake context—extract key sections first, then use them in a
  final decision call.
- You're hardening a workflow: keep choices in templates, move brittle pieces
  into Python tools, and lock sub-templates as they stabilize.

For a runnable scenario, see `examples/pitchdeck_eval`, which stitches together a
pitchdeck orchestrator with the locked `pkg:pitchdeck-single.yaml` template.
