# Simplify: runtime/agent_file.py

## Context
Review of `.agent` parsing helpers in `llm_do/runtime/agent_file.py`.

## Findings
- Parsing helpers are duplicated: `load_agent_file_parts()` and
  `AgentFileParser.load()` both read + parse file content, and convenience
  functions wrap the default parser. Pick the functional API or the class API
  and drop the other to shrink surface area.
- `_extract_frontmatter_and_instructions()` and `build_agent_definition()`
  already encapsulate the parse pipeline, so `AgentFileParser` adds little
  unless custom parser instances are required. If custom parsers are not used,
  delete the class and keep module-level functions.
- `server_side_tools` parsing only validates that the value is a list. If the
  config must be dicts with `tool_type`, validate here or else treat the field
  as opaque and rename to reflect that it is pass-through.

## Open Questions
- Are custom parser instances used anywhere, or can we commit to a simple
  functional API?
