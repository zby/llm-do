# Simplify: toolsets/validators.py

## Context
Review of schema validator wrapper used by toolsets.

## Findings
- `DictValidator` is a thin wrapper around `TypeAdapter.validator` with
  repeated `validate_*` methods that only convert a BaseModel to dict. Consider
  a small helper that returns a dict for `BaseModel` and use `TypeAdapter`
  directly at call sites to reduce indirection.
- If returning dicts is required, consider implementing `__call__` and using a
  single validation path rather than multiple nearly-identical methods.
