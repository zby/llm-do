# Simplify: runtime/manifest.py

## Context
Review of manifest models and file path resolution.

## Findings
- `resolve_manifest_paths()` repeats file existence validation for agent_files
  and python_files. A shared helper would reduce duplication.
- `ProjectManifest.validate_has_files()` duplicates a similar check in
  `build_registry()`. If manifest validation is authoritative, drop the
  runtime check to avoid repeated errors.
- `load_manifest()` wraps JSON errors into ValueError, then re-wraps manifest
  validation errors. Consider a single error wrapper to simplify exception
  flow.

## Open Questions
- Should manifest validation be the single source of truth for file existence,
  or do we want runtime checks for extra safety?
