# Update Documentation

## Goal

Update all documentation to reflect current architecture after workers-as-tools and remove-workshop changes.

## Status: ✅ COMPLETED

All documentation updated on 2025-12-19.

## Background

Documentation is out of date:
- Still references `worker_call` tool (now workers are direct tools via `AgentToolset`)
- Still describes workshop concept (being removed in task 60)
- References `DelegationToolset` (renamed to `AgentToolset`)
- Module structure descriptions are stale
- Delegation config still uses `allow_workers` (now tool map keyed by worker/tool name)

Recent changes (commit b1297d5) added:
- `_agent_*` prefix for worker tools (e.g., `_agent_summarizer`)
- `worker_call` optional and configured like any other tool
- Dynamic `attachments` parameter in tool schema based on `attachment_policy`
- Delegation config now lists tools directly under `toolsets.delegation` (no allowlist)

## Prerequisite

- [x] Complete task 60 (remove-workshop) first

## Tasks

- [x] Wait for task 60 (remove-workshop) to complete
- [x] Update `docs/concept.md` - removed workshop metaphor, updated to workers-as-tools model
- [x] Update `docs/architecture.md` - updated module structure, delegation config examples
- [x] Update `docs/worker_delegation.md` - simplified to workers-as-tools pattern
- [x] Review and update `docs/cli.md` - removed workshop references, updated examples
- [x] Review and update `docs/bootstrapping.md` - updated to `_agent_*` tool pattern
- [x] Archive obsolete design notes - moved `workers-as-tools.md` to `docs/notes/archive/`
- [x] Update README.md - removed workshop references, updated structure examples

## Summary of Changes

### docs/concept.md
- Removed "Workshops are workshops" metaphor
- Updated programming analogy table (removed Workshop/main.worker)
- Added "Project Structure" section with flat directory examples
- Updated delegation section to use `_agent_*` tools
- Simplified design principles

### docs/architecture.md
- Updated module structure (workshop.py now describes worker resolution)
- Updated agent_toolset.py description
- Updated delegation config to show tool map syntax
- Updated approval configuration summary table

### docs/worker_delegation.md
- Removed `worker_call` tool from API signatures (emphasized `_agent_*` pattern)
- Updated worker definition example to use tool map
- Updated attachment resolution and approval rules

### docs/cli.md
- Removed workshop-centric language
- Removed `--entry` flag documentation
- Updated model precedence (removed workshop.yaml)
- Renamed "Workshop Initialization" to "Project Initialization"
- Updated all examples to use flat structure

### docs/bootstrapping.md
- Updated diagram to show `_agent_*` tool calls
- Updated directory structure (generated/ instead of workers/generated/)

### README.md
- Updated programming analogy table
- Changed quick start to use flat structure
- Updated project structure examples
- Changed "Running Workshops" to "Running Workers"

### Archived
- `docs/notes/workers-as-tools.md` → `docs/notes/archive/workers-as-tools.md`

## References

- Current AgentToolset: `llm_do/agent_toolset.py`
- Remove workshop task: `tasks/completed/60-remove-workshop.md`
- Completed workers-as-tools: `tasks/completed/workers-as-tools.md`
