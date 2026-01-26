# Agent Skills Standard Unification

## Context

The `.agent` file format is structurally similar to the [Agent Skills](https://agentskills.io/specification) standard (SKILL.md). Both use YAML frontmatter + Markdown instructions. Aligning with the standard could ease adoption.

## Key Differences

| Concept | `.agent` | Agent Skills | Notes |
|---------|-----------|--------------|-------|
| Identifier | `name` (any string) | `name` (kebab-case, required) | Skills enforces naming convention |
| Description | `description` (optional) | `description` (required) | Make required for alignment |
| Model/Runtime | `model`, `compatible_models` | `compatibility` (string) | Different semantics |
| Tools | `toolsets`, `server_side_tools` | `allowed-tools` | Different approach |
| Entry point | `entry: true` | N/A | .worker-specific (multi-agent) |
| Input schema | `schema_in_ref` | N/A | .worker-specific |
| License | N/A | `license` | Skills-specific |
| Metadata | N/A | `metadata` | Skills-specific |

## Proposed Changes

### 1. Move `entry` to manifest

Currently `entry: true` is in individual .agent files. Move to project.json:

```json
{
  "version": 1,
  "entry": {
    "worker": "main",
    "input": { ... }
  },
  "agent_files": ["main.agent", "helper.agent"]
}
```

Rationale: Entry point is project-level config, not agent definition.

### 2. Unify compatibility fields

Current `compatible_models` is machine-readable (glob patterns for runtime validation).
Skills `compatibility` is human-readable (environment requirements string).

**Option A: Structured `compatibility` object (recommended)**
```yaml
---
name: my-worker
description: Process PDFs and extract data
compatibility:
  models: ["anthropic:*", "openai:gpt-4*"]
  environment: "Requires poppler, tesseract"
---
```

**Option B: Single string (exact Skills spec)**
```yaml
compatibility: "Requires anthropic:claude-* or openai:gpt-4*, poppler, tesseract"
```
Parse model patterns from string at load time.

**Option C: Keep both fields**
```yaml
compatibility: "Requires poppler, tesseract"  # Skills-compatible
models: ["anthropic:*"]  # Machine-validated patterns
```

### 3. Additional alignment

- Make `description` required
- Add optional `license` field
- Add optional `metadata` field (free-form key-value)
- Consider adopting kebab-case naming convention for `name`

## References

- [Agent Skills Specification](https://agentskills.io/specification)
- [GitHub - agentskills/agentskills](https://github.com/agentskills/agentskills)
- Industry adoption: Microsoft, OpenAI, Atlassian, Figma, Cursor, GitHub
