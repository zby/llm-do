# Update Documentation

## Goal

Update all documentation to reflect current architecture after workers-as-tools and remove-workshop changes.

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

- [ ] Complete task 60 (remove-workshop) first

## Files to Update

### Core Docs

| File | Issues |
|------|--------|
| `docs/concept.md` | Workshop-centric, `worker_call` references |
| `docs/architecture.md` | Old module structure, `delegation_toolset.py` reference |
| `docs/worker_delegation.md` | `worker_call` tool signature, old API |
| `docs/cli.md` | May reference workshop invocation |
| `docs/bootstrapping.md` | May reference old patterns |

### Specific Changes Needed

#### concept.md
- Remove workshop-as-program metaphor
- Update to tool_path model
- Update worker-to-worker delegation to show direct tool calls
- Replace `allow_workers` examples with delegation tool map (`toolsets.delegation.<worker>: {}`)

#### architecture.md
- Update module structure (remove `workshop.py`, `delegation_toolset.py`)
- Add `agent_toolset.py` description
- Update delegation config examples to tool map (no `allow_workers`)
- Remove sandbox two-layer diagram (sandbox removed)
- Update execution flow diagram

#### worker_delegation.md
- Update `worker_call` docs: optional and configured like any other tool
- Show direct worker invocation with `_agent_` prefix: `_agent_summarizer(input="...")`
- Document dynamic schema: `attachments` parameter added when worker's `attachment_policy.max_attachments > 0`
- Update WorkerDefinition examples to use delegation tool map (`toolsets.delegation.<worker>: {}`)
- Explain security model:
  - Static workers → `_agent_*` tools (controlled by delegation tool config)
  - Dynamic routing → `worker_call` (only when configured)
- Simplify - much of this becomes "workers are just tools"

#### attachment_policy
- Document that `attachment_policy.max_attachments > 0` adds `attachments` param to tool schema
- Explain schema description reflects `allowed_suffixes` and `max_attachments`
- Show example worker definition with attachment policy

#### cli.md
- Update override examples to use `toolsets.delegation.<worker>={}`

### Notes to Archive

These can be moved to `docs/notes/archive/`:
- `docs/notes/workers-as-tools.md` (design note, implementation complete)

## Tasks

- [ ] Wait for task 60 (remove-workshop) to complete
- [ ] Update `docs/concept.md`
- [ ] Update `docs/architecture.md`
- [ ] Update `docs/worker_delegation.md`
- [ ] Review and update `docs/cli.md`
- [ ] Review and update `docs/bootstrapping.md`
- [ ] Archive obsolete design notes
- [ ] Update README.md if needed

## References

- Current AgentToolset: `llm_do/agent_toolset.py`
- Remove workshop task: `docs/tasks/active/60-remove-workshop.md`
- Completed workers-as-tools: `docs/tasks/completed/workers-as-tools.md`
