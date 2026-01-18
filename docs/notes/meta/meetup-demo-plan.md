# llm-do 5-Minute Meetup Demo Plan

## Core Message

Show how llm-do lets you start flexible with LLMs, then progressively harden with code—same call sites, increasing reliability.

## Demo Structure (5 minutes)

### 1. Hook (30 sec)

"What if you could prototype with LLMs, then swap in deterministic code as patterns emerge—without rewriting your orchestration?"

### 2. Live Demo: Pitch Deck Evaluator (3 min)

The `examples/pitchdeck_eval*` examples show the exact same task with 3 implementations:

| Version | What LLM Does | What's Demo-Worthy |
|---------|--------------|-------------------|
| `pitchdeck_eval/` | Everything (file listing, analysis, reporting) | "Works, but 3 API calls, slow" |
| `pitchdeck_eval_stabilized/` | Analysis + reporting only | "File listing is now Python—faster, cheaper" |
| `pitchdeck_eval_code_entry/` | Only analysis | "Python orchestrates everything, LLM just reasons" |

Run each one live:

```bash
llm-do examples/pitchdeck_eval/project.json
llm-do examples/pitchdeck_eval_stabilized/project.json
llm-do examples/pitchdeck_eval_code_entry/project.json
```

Show the decreasing token usage and latency with each version.

### 3. Key Takeaway (1 min)

- "Same result, same call sites, but 10x cheaper and faster"
- "You don't rewrite—you extract stable patterns to Python"
- "LLM stays where reasoning matters, code handles the mechanical"

### 4. Architecture Slide (30 sec)

One slide showing: Workers (YAML+prompt) + Tools (Python) = Unified function space

## Why This Demo Works

1. **Tangible progression** — Audiences see the same task done 3 ways
2. **Real metrics** — Show actual token counts/latency differences
3. **Low risk** — These examples are tested and work reliably
4. **Memorable concept** — "Extend with LLMs, stabilize with code"

## Backup/Alternative: File Organizer

If you want something more interactive, `examples/file_organizer/` is also good—it shows semantic decisions (LLM picks categories) combined with deterministic cleanup (Python sanitizes filenames). You could demo it organizing a messy folder live.
