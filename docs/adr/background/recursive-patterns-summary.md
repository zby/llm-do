---
description: Summary of recursive worker patterns for context-limited tasks
---

# Recursive Worker Patterns (Summary)

> For the full catalog of 15 problem types with detailed examples, see [recursive-problem-patterns.md](recursive-problem-patterns.md).

## Why Recursion?

LLMs have context limits—both hard (token limits) and soft (quality degrades with length). Recursion addresses this:

1. Break work into chunks that fit comfortably in context
2. Each recursive call gets fresh context (messages are locals)
3. Parent sees only results, not full child conversations
4. Enables arbitrarily deep processing within context bounds

## Representative Example: Document Summarization

**Problem**: Summarize a 500-page document that exceeds context limits.

**Pattern**: Map-reduce tree—chunk, summarize each, recursively summarize summaries.

```yaml
# summarizer.worker
---
name: summarizer
description: Recursively summarize text of any length
model: anthropic:claude-haiku-4-5
toolsets:
  - summarizer  # Self-reference for recursion
---
You are a document summarizer.

Given TEXT:
1. If TEXT is short enough (under 2000 words), summarize directly
2. If TEXT is too long:
   a. Split into 3-5 chunks
   b. Call summarizer(input=chunk) for each
   c. Combine summaries; if still too long, recurse again
```

**Execution**:
```
summarizer("500 page document")
  ├── summarizer(chunk_1) → summary_1
  ├── summarizer(chunk_2) → summary_2
  ├── summarizer(chunk_3) → summary_3
  └── summarizer(combined) → final
```

## Other Problem Types

The [full catalog](recursive-problem-patterns.md) covers:

| Pattern | Example Problems |
|---------|------------------|
| Hierarchical reduction | Summarization, code analysis |
| Decomposition | Task planning, proof construction |
| Tree exploration | Game AI, research questions |
| Reference following | Knowledge graphs, contract analysis |
| Multi-level generation | Creative writing, test generation |

## Implementation Patterns

**A. Self-Recursive**: Worker includes itself in toolsets.
```yaml
toolsets:
  - self_name
```

**B. Twin Workers**: Two identical workers calling each other (works without policy changes).
```yaml
# analyzer_a.agent calls analyzer_b
# analyzer_b.agent calls analyzer_a
```

**C. Typed Recursion**: Different workers for hierarchy levels.
```yaml
document_analyzer → section_analyzer → paragraph_analyzer
```

**D. Depth-Controlled**: Explicit depth parameter, decrement on each call.
```python
class RecursiveInput(BaseModel):
    data: str
    depth: int = 3
```

## Key Insight: Messages Are Locals

Each worker call gets fresh context containing only:
- Worker instructions
- Input to this call
- Tool calls/results from this execution

Parent never sees child's full conversation—only the final result. This prevents context accumulation and enables arbitrary depth within token budgets.
