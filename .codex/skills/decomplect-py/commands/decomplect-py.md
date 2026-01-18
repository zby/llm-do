---
name: decomplect-py
description: Deep architectural analysis for Python code using Rich Hickey's decomplection principles. Evaluates simplicity, functional core/imperative shell, and coupling. Use for design review and architectural assessment.
---

# Decomplect-Py Command

Architectural analysis for Python code focused on Rich Hickey's simplicity philosophy.

## Usage

```
/decomplect-py                # Run all 3 architectural analyzers in parallel
/decomplect-py --sequential   # Run one at a time
/decomplect-py --simplicity   # Run specific analyzer only
```

## What It Analyzes

| Analyzer | Question | Focus |
|----------|----------|-------|
| **simplicity-analyzer** | Is this truly simple or just easy? | Values over state, decomplected concerns |
| **fcis-analyzer** | Is pure logic separated from I/O? | Functional core, imperative shell |
| **coupling-analyzer** | Are modules well-separated? | Cohesion, coupling, dependency direction |

## Execution

Launches 3 agents in parallel:
1. **simplicity-analyzer** - Rich Hickey's decomplection principles for Python
2. **fcis-analyzer** - Functional Core, Imperative Shell pattern in Python
3. **coupling-analyzer** - Module boundaries and dependencies in Python

## Output

```markdown
# Decomplection Analysis (Python)

## Overall Grade: [A-F]

## Summary
[Architectural assessment]

## Pillar Scores

| Pillar | Grade | Key Finding |
|--------|-------|-------------|
| Simplicity | B | Some complected concerns |
| FCIS | C | I/O mixed with logic |
| Coupling | A | Well-separated modules |

## Detailed Findings
[Per-analyzer findings with refactoring suggestions]

## Recommendations
[Priority architectural improvements]
```

## Agent Selection

| Flag | Analyzer |
|------|----------|
| (default) | All 3 in parallel |
| `--sequential` | All 3, one at a time |
| `--simplicity` | Simplicity only |
| `--fcis` | FCIS only |
| `--coupling` | Coupling only |

## When to Use

- Reviewing Python system design
- Before major refactoring
- Assessing architectural quality
- Checking if code is "Rich Hickey approved"

## See Also

- `/decomplect` - Analysis for TypeScript/Go/Rust
- `/unslopify` - Tactical code cleanup
