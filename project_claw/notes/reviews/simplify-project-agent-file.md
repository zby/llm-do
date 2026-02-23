# Simplify: project/agent_file.py

## Context
Review of `.agent` frontmatter parsing and `AgentDefinition` construction.

## 2026-02-09 Review
- Class and functional APIs overlap (`AgentFileParser` vs `load_*`/`parse_*` helpers); one style can be removed.
- `_parse_tools()` and `_parse_toolsets()` duplicate list+dedupe validation; a generic string-list parser helper would cut duplication.
- `_parse_server_side_tools()` and `_parse_compatible_models()` only validate top-level container type. If schema guarantees are desired, validate item types here.

## Open Questions
- Are custom parser instances needed, or can this module be fully functional API?
