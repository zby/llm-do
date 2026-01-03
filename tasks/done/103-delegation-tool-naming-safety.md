# Delegation Tool Naming Safety

## Prerequisites
- [x] None.

## Goal
Worker tool naming is collision-free and worker_create is robust in integrations.

## Tasks
- [x] Reserve known provider tool names (web_search, web_fetch, etc.) in delegation collision checks.
- [x] Consider introducing a prefixed worker tool namespace to eliminate collisions.
- [x] Ensure `creation_defaults` is always set or safely defaulted in worker_create.

## Current State
Completed.

## Notes
- Origin: delegation/composition review notes.

## Implementation Summary

1. **Server-side tool collision detection**:
   - Added `_SERVER_SIDE_TOOL_NAMES` constant with known provider tool types
     (`web_search`, `web_fetch`, `code_execution`, `image_generation`)
   - Updated `_collect_reserved_tool_names()` to check `worker.server_side_tools`
   - Worker names that collide with enabled server-side tools now fail fast
     with a clear error message

2. **Worker tool namespace decision**:
   - Kept current flat naming (worker name = tool name) for simplicity
   - Collision detection is comprehensive enough with reserved names,
     filesystem tools, shell tools, custom tools, and server-side tools

3. **creation_defaults safety**:
   - WorkerContext already has proper safeguards:
     - `default_factory=WorkerCreationDefaults` on the field
     - `__post_init__` guard that sets `WorkerCreationDefaults()` if None
   - Added tests to verify this behavior:
     - `test_worker_context_creation_defaults_never_none`
     - `test_worker_context_creation_defaults_explicit_none_becomes_default`
     - `test_worker_create_without_explicit_defaults`
   - Added tests for server-side tool collision:
     - `test_delegation_toolset_blocks_server_side_tool_collision`
     - `test_delegation_toolset_allows_worker_when_no_server_side_collision`
