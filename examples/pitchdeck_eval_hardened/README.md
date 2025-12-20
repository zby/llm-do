# Pitch Deck Evaluation (Hardened)

This example demonstrates **progressive hardening** - extracting deterministic
logic from LLM instructions into Python tools.

## What Changed from `pitchdeck_eval`

The original `pitchdeck_eval` example has the LLM:
1. Call `list_files("input", "*.pdf")` to find PDFs
2. Generate slugs from filenames (lowercase, hyphenated)
3. Construct output paths

**Problem**: Slug generation is purely mechanical. The LLM might:
- Generate inconsistent slugs across runs
- Make mistakes with edge cases (unicode, special chars)
- Waste tokens on deterministic work

**Solution**: Extract to a Python tool:

```python
def list_pitchdecks(path: str = "input") -> list[dict]:
    """Returns [{file, slug, output_path}, ...]"""
    for pdf in Path(path).glob("*.pdf"):
        slug = slugify(pdf.stem)  # deterministic, tested
        yield {"file": str(pdf), "slug": slug, "output_path": f"evaluations/{slug}.md"}
```

Now the worker instructions are simpler:
```
1. Call list_pitchdecks() to get all decks with metadata
2. For each item: evaluate and write to item.output_path
```

## The Hardening Pattern

```
Neural (flexible)                    Symbolic (deterministic)
─────────────────────────────────────────────────────────────
LLM generates slugs        →        Python slugify library
LLM constructs paths       →        Pre-computed in tool
LLM decides file order     →        sorted() in Python
```

Benefits:
- **Consistency**: Same input always produces same slug
- **Testability**: Python function can be unit tested
- **Efficiency**: Less tokens spent on mechanical work
- **Reliability**: Edge cases handled by battle-tested library

## Prerequisites

```bash
pip install -e .              # llm-do from repo root (includes python-slugify)
export ANTHROPIC_API_KEY=...
```

## Run

```bash
cd examples/pitchdeck_eval_hardened
llm-do --model anthropic:claude-haiku-4-5 --approve-all
```

## Files

```
pitchdeck_eval_hardened/
├── main.worker           # Orchestrator (uses list_pitchdecks tool)
├── pitch_evaluator.worker # Evaluator (unchanged from original)
├── PROCEDURE.md          # Evaluation rubric
├── tools.py              # Custom tool: list_pitchdecks()
├── requirements.txt      # python-slugify>=8.0
├── input/                # Drop PDFs here
└── evaluations/          # Reports written here
```

## Next Hardening Steps

This example shows one hardening step. Further progression could include:

1. **Structured output schema** - Pydantic model for evaluation results
2. **Score computation in Python** - LLM provides qualitative scores, Python computes weighted totals
3. **Full Python orchestration** - Python script calls workers, LLM only does analysis
