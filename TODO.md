# TODO

## Runtime polish

- [ ] Add a helper that parses the old `Files` shorthand (e.g., `ro:./reports`) into `SandboxConfig` entries so worker authors can keep concise configs.
- [ ] Expose per-sandbox aliases when generating `sandbox_*` tool calls so orchestration instructions can mention `sandbox_write_text("evaluations", …)` without boilerplate.
- [ ] Surface attachment approval/context UX in the CLI (prompts instead of auto-approving everything).

## Docs & guidance

- [ ] Expand AGENTS/README with a short “Worker authoring checklist” now that TemplateCall is gone.
- [ ] Write a migration note for users who previously relied on the `llm` plugin/toolboxes.
