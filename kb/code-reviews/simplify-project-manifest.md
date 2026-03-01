# Simplify: project/manifest.py

## Context
Review of manifest schema validation and path resolution.

## 2026-02-09 Review
- `resolve_manifest_paths()` duplicates agent/python file existence loops; a shared resolver helper would remove mirrored code.
- `validate_file_list()` performs duplicate tracking manually; extracting a generic list validator for both `agent_files` and `python_files` would reduce branch size.
- Validation for non-empty file lists exists here and in registry construction; keeping manifest as single source of truth would remove redundant guards.

## Open Questions
- Should file-existence checks live exclusively in manifest loading, or remain duplicated at registry build boundaries for defense-in-depth?
