# Review: Toolsets

Periodic review of toolset implementations for bugs, inconsistencies, and improvements.

## Scope

- `llm_do/toolsets/filesystem.py` - Filesystem toolset
- `llm_do/toolsets/loader.py` - Toolset loading and class-path resolution
- `llm_do/toolsets/builtins.py` - Built-in toolset registry
- `llm_do/toolsets/approval.py` - Toolset approval logic
- `llm_do/toolsets/validators.py` - Argument validators
- `llm_do/toolsets/shell/` - Shell toolset and execution helpers

## Checklist

- [ ] Toolset APIs are consistent
- [ ] Approval logic (`needs_approval()`) is correct
- [ ] Error handling is appropriate
- [ ] Security boundaries are respected
- [ ] No code duplication across toolsets

## Output

Record findings in `docs/notes/reviews/review-toolsets.md`.

