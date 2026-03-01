# Simplify: project/input_model_refs.py

## Context
Review of `input_model_ref` parsing/resolution for `.agent` definitions.

## 2026-02-09 Review
- `_split_input_model_ref()` supports two syntaxes (`module.Class` and `path.py:Class`), which increases parse branches and error handling.
- Module loading has path/import split with shared failure semantics; a single ref-type abstraction could simplify control flow.
- This module already composes `path_refs` helpers cleanly; further simplification is mostly syntax surface reduction.

## Open Questions
- Can syntax be narrowed to one canonical form to reduce parser complexity?
