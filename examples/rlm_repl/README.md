# RLM-Style REPL Example

Demonstrates a Recursive Language Model pattern inside llm-do:
- The agent only sees the query.
- The full context lives in an external Python REPL.
- The agent can recursively call itself to handle sub-questions.

## Key Features

- **External context**: `context.txt` is loaded by a code entry point, not shown to the agent.
- **REPL tool**: `repl(code)` runs RestrictedPython with `context` preloaded.
- **Self-recursion**: the agent calls `rlm` for sub-queries.
- **Pre-approved tools**: `project.json` uses `approve_all` to mirror the paper's REPL setup.

## Dependencies

This example requires `RestrictedPython`:

```bash
pip install RestrictedPython
```

## Running

```bash
export LLM_DO_MODEL="anthropic:claude-haiku-4-5"
llm-do examples/rlm_repl
```

Override the default query:

```bash
llm-do examples/rlm_repl "What is the objective of Project Nimbus?"
```

Edit `context.txt` to swap in your own corpus.

## Files

- `project.json` - Manifest defining entry point and runtime approvals
- `tools.py` - REPL tool + entry point that loads `context.txt`
- `rlm.agent` - RLM-style agent prompt
- `context.txt` - Sample long-context corpus

## Safety Note

`repl` runs in-process with RestrictedPython. It is not OS isolation; use a container if you need strong isolation.
