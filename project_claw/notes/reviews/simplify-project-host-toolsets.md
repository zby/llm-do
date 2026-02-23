# Simplify: project/host_toolsets.py

## Context
Review of host-layer wiring helpers that feed `build_registry`.

## 2026-02-09 Review
- `build_host_toolsets()` and `build_agent_toolset_factory()` are thin wrappers over single calls; module can be collapsed into one `build_registry_host_wiring()` helper.
- `RegistryHostWiring` TypedDict is useful but currently only wraps two fields; consider directly reusing `(extra_toolsets, agent_toolset_factory)` tuple if API churn is acceptable.

## Open Questions
- Is this module meant as a stable extension seam for alternate hosts, or just an internal convenience layer?
