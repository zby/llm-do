# Investor Pitch Deck Evaluation Experiments

Experiments exploring different patterns for defining and running llm-do workers.

## Versions

### v1_cli - Python workers via llm-do CLI

Workers defined as Python objects, run via the `llm-do` command.

```bash
cd v1_cli
llm-do workers.py --entry main --approve-all "Go"
```

If `llm-do` is not installed, run via `uv` instead:

```bash
uv run llm-do experiments/inv/v1_cli/workers.py --entry main --approve-all "Go"
```

### v2_direct - Direct Python execution

Workers defined and executed entirely in Python, no CLI needed.
Configuration constants at the top of the script for easy experimentation.

```bash
cd v2_direct
python run.py
```

If the `llm_do` package is not installed, run via `uv` instead:

```bash
uv run -m experiments.inv.v2_direct.run
```

Edit `run.py` to change:
- `MODEL` - which LLM to use
- `APPROVE_ALL` - auto-approve tools or require manual approval
- `VERBOSITY` - 0=quiet, 1=tool calls, 2=streaming
- `PROMPT` - the input to send

## Comparison

| Aspect | v1_cli | v2_direct |
|--------|--------|-----------|
| Execution | `llm-do` CLI | `python run.py` |
| Config | CLI flags | Python constants |
| Dependencies | CLI discovery | Explicit imports |
| Customization | Limited to CLI | Full Python control |
| Debugging | CLI output | Python debugger |

## Structure

Both versions share the same structure:
```
v*/
├── instructions/
│   ├── main.md             # Orchestrator instructions
│   └── pitch_evaluator.md  # Evaluator instructions
├── input/                  # Drop PDFs here (symlinked)
├── evaluations/            # Reports written here
└── workers.py / run.py     # Worker definitions
```
