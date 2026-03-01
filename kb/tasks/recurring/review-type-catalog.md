# Review: Type Catalog

Periodic review of the type surface (dataclasses, protocols, Pydantic models, enums, exceptions) to identify simplification opportunities and maintain design quality.

## Scope

Review all custom types in `llm_do/` - dataclasses, protocols, Pydantic models, TypeAliases, enums, and exception classes.

## Checklist

- [x] Catalog all types: list every dataclass, protocol, Pydantic model, TypeAlias, enum, and exception
- [x] Identify unused types: types declared but never referenced elsewhere
- [x] Identify wrapper bloat: wrapper types that add little behavior over what they wrap
- [x] Check type drift: types that don't match their runtime usage (e.g., `str | Model` but always cast at runtime)
- [x] Check layering: excessive wrapper chains that obscure type checks and debugging
- [x] Check duplication: similar types that could be consolidated
- [x] Check naming: types with unclear or inconsistent naming conventions
- [x] Identify simplification opportunities: types that could be removed, merged, or inlined

## Output

Update `docs/notes/type-catalog-review.md` with:
- Current type catalog (organized by module)
- Design observations and issues found
- Simplification recommendations
- Open questions for follow-up

