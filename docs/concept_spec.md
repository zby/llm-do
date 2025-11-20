# llm-do: Concept and Design

## Core Idea

Build multi-step LLM workflows using **workers** (agents) that can:
1. Access files through sandboxed directories
2. Call other workers with controlled inputs
3. Start as flexible YAML and harden into tested Python over time

A **worker** = prompt template + configuration + tools, packaged as an executable unit.

## How the Pieces Connect

### The llm Library Foundation

The `llm` library provides:
- **Templates** (`.yaml` files): system/prompt text with parameter substitution
- **Tool registration**: plugins expose Python functions/classes as tools
- **Model abstraction**: consistent interface across providers
- **Command-line interface**: `llm -t template.yaml "prompt text"`

### What llm-do Adds

The concept of **workers as executables**:
- A worker bundles template + model + tools + schemas into one runnable unit
- Workers can invoke other workers recursively
- Workers can autonomously create new workers (with user approval)
- Three core capabilities enable orchestration:
  1. **Files**: Sandboxed file access per-directory
  2. **TemplateCall**: Safe worker-to-worker delegation
  3. **CreateWorker**: Autonomous worker creation with approval flow

### The Recursive Call Problem (Why Rewrite?)

In the current `llm` library architecture:
- Templates and tools live in separate worlds
- Inside a tool call, you don't have normal access to template loading/parsing machinery
- To call another template from a tool, you have to manually reconstruct all the template resolution logic

`TemplateCall` works around this by re-implementing template loading inside a tool, but it's awkward.

**A better architecture** would treat workers as first-class executables that can naturally invoke other workers, because the template loading machinery would be part of the worker runtime.

## Worker Anatomy

A complete worker definition bundles everything together:

```yaml
# workers/orchestrator.yaml
system: |
  You coordinate multi-file evaluations.
  List files, call workers for each, write results.

prompt: |
  {{ prompt }}

model: claude-3-5-sonnet-20241022

tools:
  # Sandboxed file access
  - Files:
      config: "ro:pipeline"
      alias: "pipeline_ro"

  - Files:
      config: "out:evaluations"
      alias: "evals_out"

  # Worker delegation tool
  - TemplateCall:
      allow_templates: ["pkg:*"]
      lock_template: "workers/evaluator.yaml"
      allowed_suffixes: [".pdf", ".txt"]
      max_attachments: 1
      max_bytes: 15000000

schema_object: null  # or structured output schema
```

**Run the worker:**
```bash
llm -t workers/orchestrator.yaml "evaluate all PDFs"
```

The worker is self-contained: prompt template, model choice, tool configuration, and security constraints all in one file.

This is the *executable unit*—you can run it from the command line, but more importantly, other workers can call it via the worker delegation tool.

## Files Toolbox

Provides sandboxed directory access:

```yaml
- Files:
    config: "ro:./data"      # read-only
    alias: "data"
```

Exposes:
- `Files_data_list(pattern="**/*")` — glob within sandbox
- `Files_data_read_text(path, max_chars=200_000)` — read with size cap
- `Files_data_write_text(path, content)` — write (blocked in ro: mode)

**Security:**
- All paths resolved inside sandbox root
- Escaping via `..` or absolute paths raises errors
- Read-only mode blocks writes
- Configurable read size limits

## Worker Delegation (TemplateCall / llm_worker_call)

Lets workers call other workers:

```yaml
- TemplateCall:
    allow_templates: ["pkg:*", "./workers/**/*.yaml"]
    lock_template: "workers/single-eval.yaml"  # optional: force this worker
    allowed_suffixes: [".pdf", ".txt"]
    max_attachments: 1
    max_bytes: 15000000
```

**LLM-facing tool signature:**
```python
llm_worker_call(
    worker_name: str,           # which worker to invoke
    input: str,                 # main prompt text
    attachments: list = [],     # files to attach
    extra_context: list = [],   # text fragments (rubrics, procedures)
    params: dict = {},          # worker parameters
    expect_json: bool = False   # parse structured output
)
```

**What happens on invocation:**
1. Load the target worker definition (prompt template + config)
2. Validate all inputs against configured constraints
3. Execute the worker with its own model and tools
4. Return result (text or parsed JSON)

**Validation before execution:**
- Worker must match allowlist (or locked worker overrides)
- Attachments checked: count, size, file extensions
- If `expect_json=True`, worker must define `schema_object`

**Model selection:**
- Uses target worker's `model:` field if present
- Falls back to `llm.get_default_model()` otherwise
- Does NOT inherit from parent command's `-m` flag

**Security:**
- Inline `functions:` blocks in workers are ignored
- Only registered Python toolboxes are callable
- All validation happens before LLM sees inputs

**The architectural challenge:**
In the current llm library, this tool has to re-implement all the worker loading logic because tools don't have access to the template machinery. A better architecture would make workers first-class executables that can naturally invoke each other.

## The Two-Step Pattern

Most common use case: **choose, then act**

Example workflow:
1. **Orchestrator worker**: Lists files, decides which to process
2. **Evaluator worker**: Processes one file with focused context
3. **Orchestrator again**: Collects results, writes outputs

```yaml
# Step 1: Orchestrator lists and chooses
tools:
  - Files_pipeline_ro_list  # see what's available
  - llm_worker_call         # delegate to another worker

# Step 2: For each chosen file, orchestrator calls:
llm_worker_call(
    worker_name="workers/evaluate-one.yaml",
    attachments=[{"path": "pipeline/deck1.pdf"}],
    extra_context=[{"path": "PROCEDURE.md"}],
    expect_json=True
)

# Step 3: Evaluator worker runs in isolation, returns structured result
# Orchestrator writes formatted output via Files_evals_out_write_text
```

**Benefits:**
- Each worker invocation has tight, focused context
- File access and attachment restrictions enforced by code
- Evaluator worker doesn't know about file selection—just evaluation
- Refine evaluator worker without touching orchestrator
- Each worker is independently testable and runnable

## Workers Creating Workers

A key capability: **workers can autonomously create new workers** when they determine a subtask needs specialized handling.

```yaml
# Any worker can have the worker creation tool
tools:
  - CreateWorker:
      output_dir: "workers"
      require_approval: true  # user must approve before worker is saved
```

**Flow (autonomous with approval):**
1. User gives a task: "Evaluate all pitch decks in this directory"
2. Worker decides: "I need a specialized evaluator worker for the PDF processing subtask"
3. Worker calls `create_worker(...)` with:
   - Worker name and description
   - Prompt template
   - Schema definition
   - Tool configuration (restricted by default)
4. **System prompts user for approval**: shows the proposed YAML
5. User approves → worker saved to `workers/pitchdeck-evaluator.yaml`
6. Worker can now call the newly created worker via `llm_worker_call`
7. Saved YAML is the starting point for progressive hardening

**Security defaults:**
- Created workers start with minimal tool access
- No file write permissions by default
- Worker delegation restricted to specific allowlists
- User approval required before worker is saved/used
- Programmer explicitly grants additional capabilities during refinement

**Why this matters:**
- Workers autonomously decompose tasks—no manual scaffolding needed
- Human-in-the-loop approval ensures safety and quality
- The saved YAML is the artifact—version controlled, auditable, refinable
- Natural workflow: LLM identifies need → generates worker → user approves → system uses it
- Progressive hardening begins from the approved file

This meta-capability (workers creating workers with approval) makes the system self-scaffolding while keeping humans in control.

## Progressive Hardening

Start flexible, harden incrementally:

1. **Autonomous creation**: Worker autonomously creates specialized sub-worker, user approves
2. **Testing**: Re-run tasks using the created worker, observe results, iterate on the YAML
3. **Specialization**: Add schemas, refine prompts, tune models
4. **Locking**: Pin to vetted workers via `lock_template`
5. **Migration**: Move brittle logic from prompts to Python toolboxes

Example progression:
- **Day 1**: Orchestrator autonomously creates `evaluator.yaml`, user approves
- **Week 1**: Test runs reveal scoring inconsistencies, user edits YAML
- **Week 2**: Add structured output schema, refine prompt
- **Week 3**: Scoring math extracted to Python toolbox with tests
- **Week 4**: Worker just calls `compute_score(dimensions)`, math is stable

Workers stay as the orchestration layer; Python handles deterministic logic.

## Design Principles

1. **Workers as executables**
   A worker is a self-contained unit you can run from CLI or invoke from another worker
   Keeps iteration fast—edit YAML, re-run

2. **Workers as artifacts**
   Workers can create other workers by writing YAML files
   The saved file is the starting point for progressive hardening
   Version controlled, auditable, refinable by programmers

3. **Security by construction**
   Sandbox escapes, file size bombs, and arbitrary code execution are prevented by toolbox design, not LLM instructions
   Created workers start with minimal permissions—programmer explicitly grants more

4. **Explicit over implicit**
   Model selection, tool configuration, and worker allowlists are declared in YAML, not inherited or guessed

5. **Recursive composability**
   Workers can call workers—workflows become building blocks
   The architecture should make this natural, not a hack

6. **No backwards compatibility**
   This is a clean break; prioritize good design over legacy constraints

## Implementation Notes (Current llm-based System)

- **Plugin registration**: `llm_do.plugin.register_tools()` exposes Files and TemplateCall to llm
- **Worker resolution**: Supports `pkg:worker-name` (bundled) and filesystem paths
- **Debugging**: Set `LLM_DO_DEBUG=1` for verbose stderr logging
- **Tool naming**: Each Files instance prefixes tools with its alias to avoid collisions
- **Attachment handling**: Converted to `llm.Attachment` objects before model invocation
- **The awkward part**: TemplateCall re-implements template loading because tools don't have access to llm's template machinery

## What a Better Architecture Would Look Like

A rewrite on a different base (PydanticAI, custom runtime, etc.) should:

1. **Make workers first-class**
   - Worker = template + config + tools as a loadable, executable unit
   - Workers have a standard invocation interface: `worker.run(input, attachments, params, ...)`
   - Tools can access the worker registry naturally—no special hacks

2. **Provide worker-to-worker delegation primitives**
   - A tool like `call_worker(name, input, ...)` should be built-in, not bolted on
   - Worker loading, validation, and execution is part of the core runtime
   - Recursive calls are natural because workers are just executables

3. **Support autonomous worker creation with approval flow**
   - Workers can propose new worker definitions when they identify the need
   - System prompts user for approval before saving/using the worker
   - User can review, edit, or reject the proposed YAML
   - Template generation helpers for common patterns
   - Created workers start with safe defaults (minimal permissions)
   - Approved YAML is immediately runnable and refinable

4. **Keep the same security model**
   - Sandboxed file access with escape prevention
   - Attachment validation (size, count, suffix)
   - Worker allowlists and locks
   - No inline code execution
   - Explicit permission grants for created workers

The goal: make recursive worker calls feel like function calls, not template loading gymnastics. And make autonomous worker creation with approval a natural part of the workflow—workers propose specialized sub-workers when needed, users approve, system uses them.

## Example: Pitch Deck Evaluation

See `examples/pitchdeck_eval/`:

```
pipeline/           # drop PDFs here
evaluations/        # outputs written here
PROCEDURE.md        # shared rubric
templates/          # worker definitions
  pitchdeck-orchestrator.yaml
  pitchdeck-single.yaml
```

**Run the orchestrator worker:**
```bash
cd examples/pitchdeck_eval
llm -t templates/pitchdeck-orchestrator.yaml \
  "evaluate every pitch deck using the procedure"
```

**Flow:**
1. Orchestrator worker lists `pipeline/*.pdf`
2. For each PDF:
   - Calls locked evaluator worker
   - Passes PDF + PROCEDURE.md
   - Gets back structured JSON
   - Converts to Markdown
   - Writes to `evaluations/<slug>.md`

Each PDF processed in isolated worker invocation = tight context, reproducible results.

The evaluator worker (`pitchdeck-single.yaml`) is independently runnable:
```bash
llm -t templates/pitchdeck-single.yaml \
  -a deck.pdf \
  --system-fragment PROCEDURE.md \
  "evaluate this deck"
```

## Why Not Just Script It?

You could hard-code this in Python. But:
- **Autonomous decomposition**: Workers identify when they need specialized sub-workers and create them—no manual scaffolding
- **Human-in-the-loop**: User approves generated workers before they're used—safety + quality control
- **Iteration speed**: Edit approved YAML → re-run, vs. code → test → deploy
- **Auditability**: Workflow logic lives in workers where it's easy to inspect and test
- **Flexibility**: Adding edge cases (skip files, retry failures) is easier in worker prompts
- **Composability**: Recursive worker calls make complex workflows into building blocks
- **Progressive refinement**: Start with approved generated YAML, harden incrementally

Workers are the right level of abstraction for orchestration. Python handles the deterministic plumbing. And workers can autonomously scaffold specialized sub-workers when needed.

## Future Directions

Not priorities, but possible:
- Streaming support for long-running worker invocations
- Built-in retry logic with backoff
- Token usage tracking per worker call
- Worker composition/inheritance (import worker definitions)
- Parallel worker execution (run multiple workers concurrently)

Better to keep it simple now and see what usage patterns emerge.

## Summary

**Core concept**: Workers are prompt templates + config + tools, packaged as executable units.

**Key insight**: In the current llm library, making workers call other workers is awkward because tools don't have natural access to the template loading machinery. A better architecture would treat workers as first-class executables with built-in delegation primitives.

**Meta-capability**: Workers can autonomously create specialized sub-workers when they identify the need. User approves the generated YAML before it's saved/used. This enables autonomous task decomposition with human-in-the-loop control, and the saved YAML becomes the starting point for progressive hardening.

**What to preserve in a rewrite**:
- Workers as self-contained YAML definitions
- Autonomous worker creation with user approval
- Sandboxed file access with escape prevention
- Worker delegation with allowlists/locks and attachment validation
- Progressive hardening: autonomous creation → approval → test → refine → migrate to Python
- Security by construction: created workers start with minimal permissions, user must approve

**What would improve**:
- Worker invocation becomes a natural primitive, not a hack
- Tools can call `invoke_worker(name, ...)` without re-implementing template loading
- The worker registry is part of the core runtime, accessible to all tools
- Worker creation with approval flow feels integrated, not bolted on
- Clear approval UX: show proposed YAML, allow edits before saving
