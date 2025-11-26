# Style and Conventions
- Formatting: black, 4 spaces; follow snake_case for functions/vars and PascalCase for classes. Keep code clear and delete dead code when possible.
- Workers: keep each worker focused on single unit of work; compose via worker_call/worker_create. Declare sandboxes explicitly with minimal access; document tools in worker instructions; rely on WorkerCreationDefaults for shared defaults instead of duplicating YAML.
- Approvals/safety: approval rules default to auto-approve—lock down tool_rules for sensitive workers. Avoid forgetting sandboxes to prevent runtime KeyError.
- Testing mindset: tests prefer PydanticAI TestModel/custom agent_runner (see tests/README). No backward compatibility promises—breaking changes OK when improving design.
- Python execution: use `.venv/bin/python` rather than global Python; prefer editing/creating workers in `workers/*.yaml` then run with `llm-do`.
- Comments: keep concise, only where non-obvious; follow project guidance and black formatting.