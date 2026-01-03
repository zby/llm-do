# Toolsets and Approval UX Improvements

## Prerequisites
- [x] None.

## Goal
Toolset approvals are consistent and tool execution stays isolated and well-specified.

## Tasks
- [x] Move shell metacharacter blocking into `needs_approval` for consistent UX.
- [x] Namespace custom tool modules using a stable path hash to avoid collisions.
- [x] Improve JSON schema generation for `Optional`/`Union` type hints.
- [x] Avoid full-file loads in `read_file` when `max_chars` is set.

## Current State
Completed.

## Notes
- Origin: toolsets/approvals review notes.

## Implementation Summary

1. **Shell metacharacter blocking**: Moved `check_metacharacters()` call from
   `execute_shell()` to `ShellToolset.needs_approval()`. Commands with shell
   metacharacters now get a consistent "blocked" UX through the approval layer
   instead of runtime errors.

2. **Custom tool module namespacing**: Module names now include an 8-character
   MD5 hash of the full tools.py path (e.g., `analyzer_tools_a1b2c3d4`). This
   prevents collisions when multiple workers with the same name exist in
   different directories.

3. **Pydantic schema generation**: Replaced custom `_python_type_to_json_schema`
   with Pydantic's `create_model` + `model_json_schema()`. This properly handles
   `Optional`, `Union`, `List`, `Dict`, and other complex types with correct
   `anyOf` schemas.

4. **Efficient read_file**: For files > 1MB, uses streaming approach with
   character-by-character seeking for offset support. Avoids loading entire
   large files into memory when only a portion is needed.
