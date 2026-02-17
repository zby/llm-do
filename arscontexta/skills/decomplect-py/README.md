# Decomplect-Py

Architectural code analysis for Python design quality.

## Overview

Asks: *"Is this Python code well-designed?"*

```
/decomplect-py
```

Runs 3 analyzers in parallel to evaluate architectural quality of Python code.

## Analyzers

| Analyzer | Source | Question |
|----------|--------|----------|
| **simplicity-analyzer** | Rich Hickey | Is this truly simple or just easy? |
| **fcis-analyzer** | Gary Bernhardt | Is pure logic separated from I/O? |
| **coupling-analyzer** | Constantine & Yourdon | Are modules well-separated? |

## What It Checks

| Pillar | Source | Focus |
|--------|--------|-------|
| **Simplicity** | Rich Hickey (Simple Made Easy, 2011) | Values over state, decomplected concerns |
| **FCIS** | Gary Bernhardt (Destroy All Software) | Functional core (pure), imperative shell (I/O) |
| **Coupling** | Constantine & Yourdon (1970s) | High cohesion, low coupling |

## Usage

```
/decomplect-py                # All 3 analyzers in parallel
/decomplect-py --sequential   # One at a time
/decomplect-py --simplicity   # Simplicity only
/decomplect-py --fcis         # FCIS only
/decomplect-py --coupling     # Coupling only
```

## Python-Specific Patterns

### Simplicity
- `dataclasses(frozen=True)` and `NamedTuple` for immutability
- Avoid mutable default arguments (`def foo(items=[])`)
- Prefer comprehensions over loops with mutation
- Standalone functions over stateful class methods
- Avoid module-level mutable state

### FCIS
- Detect I/O: `open()`, `requests`, `sqlalchemy`, `print()`, `logging`
- Detect non-determinism: `datetime.now()`, `random`, `uuid.uuid4()`
- Django/Flask views mixing logic with I/O
- Extract pure functions from handler code

### Coupling
- Circular imports (common Python issue)
- Module-level state (`_cache = {}` patterns)
- Large base classes vs small `Protocol`/`ABC`
- Import graphs and dependency direction

## When to Use

- Reviewing Python system design
- Before major refactoring
- Assessing architectural quality
- Checking if code is "Rich Hickey approved"

## Architecture

```
decomplect-py/
├── agents/
│   ├── simplicity-analyzer.md
│   ├── fcis-analyzer.md
│   └── coupling-analyzer.md
├── commands/
│   └── decomplect-py.md
└── reference/
    ├── rich-hickey.md
    ├── fcis.md
    └── coupling.md
```

## See Also

- `/decomplect` - Analysis for TypeScript/Go/Rust
- `/unslopify` - Tactical code cleanup
- [EXAMPLES.md](EXAMPLES.md) - Full Python analysis examples
