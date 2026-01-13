# Find and Remove Useless Features

Periodic audit for features that add complexity without clear value.

## Previous Runs

- **2026-01-13**: Initial audit - see `docs/notes/reviews/useless-features-audit.md`
- **2026-01-13**: Follow-up audit - see `docs/notes/reviews/useless-features-audit-2026-01-13.md` (confirmed `schema_out` and `cache_key_fn` still need removal)

## What Makes a Feature "Useless"

1. **Low/No Usage**: Optional parameters that are rarely or never used in real configs
2. **Over-engineering**: Abstractions or patterns added "just in case"
3. **Dead Code**: Code paths that can never be reached
4. **Redundant Options**: Parameters that duplicate functionality
5. **Half-Implemented**: Features partially built but never finished
6. **Configuration Explosion**: Options that don't compose well or create confusion

## Checklist

### Core Classes

- [ ] **Worker class** - Check all optional fields for usage
- [ ] **Runtime class** - Check configuration options
- [ ] **EntryFunction** - Optional parameters and their usage
- [ ] **ToolsetSpec** - Configuration options

### Dead Code

- [ ] Functions/methods with no callers
- [ ] Conditionals that always evaluate the same way
- [ ] Parameters with default values that are never overridden

### Test Coverage Patterns

- [ ] Features tested but never used in examples/real configs
- [ ] Tests for edge cases that can't happen in practice

### Configuration/Registry

- [ ] `RunApprovalPolicy` - all options used?
- [ ] Toolset approval config - necessary complexity?

### Recent Additions

- [ ] Were they driven by real need or speculation?
- [ ] Are they being used?

## Output

Save new reviews as `docs/notes/reviews/useless-features-audit-YYYY-MM-DD.md`

## Notes

- Focus on features that add complexity without clear benefit
- Don't remove things just because they're unused - some are intentionally available
- Consider whether the feature might be needed in the near future
- Removing unused code improves maintainability and reduces cognitive load
