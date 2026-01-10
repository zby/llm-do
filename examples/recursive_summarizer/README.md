# Recursive Summarizer Example

Demonstrates self-recursive worker pattern for hierarchical document summarization.

## Key Features

- **Self-recursion**: Worker lists itself in `toolsets` to enable recursive calls
- **Context cap**: Uses 1000-character limit per call to force chunking
- **Semantic splitting**: Respects document structure (paragraphs, sentence boundaries)
- **Offset recursion**: Main worker computes file length; recursive worker advances start/end offsets

## Running

```bash
# From project root
llm-do examples/recursive_summarizer/main.worker examples/recursive_summarizer/summarizer.worker --entry main "sample_input.txt"

# Or with max-depth control (recommended for the sample input)
llm-do examples/recursive_summarizer/main.worker examples/recursive_summarizer/summarizer.worker --entry main --max-depth 10 "sample_input.txt"
```

## Expected Behavior

With the ~700 word sample document (5 chapters + conclusion):
1. `main` reads the file length and calls `summarizer` with start=0/end=total
2. `summarizer` reads a 1000-character window and chooses a split
3. It recurses on HEAD and TAIL ranges with advancing offsets
4. Summaries are merged into a final 1-3 sentence summary

## Sample Document Structure

| Section | Approx Words |
|---------|--------------|
| Chapter 1: Early Days | ~120 |
| Chapter 2: PC Revolution | ~90 |
| Chapter 3: Internet | ~150 |
| Chapter 4: Mobile/Cloud | ~150 |
| Chapter 5: AI Age | ~150 |
| Conclusion | ~100 |

## Recursion Depth

The 1000-character cap forces multiple recursion levels. Real use cases would use higher limits.

## Non-Tail Recursion Alternative

For a non-tail-recursive example, see **Pattern 2: Task Decomposition / Planning**
in `docs/notes/recursive-problem-patterns.md`, or the `examples/recursive_task_decomposer/` example.
