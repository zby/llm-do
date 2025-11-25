# Future Work

Consolidated list of future enhancements. These are optional improvements that can be tackled when needed.

---

## Per-Worker Tool Interface

**Source:** worker_tool_interface.md

Expose registered workers as first-class tools so the LLM can call them directly without using `worker_call`.

### Benefits
- Tool schema is self-descriptive ("call `pitch_evaluator`" looks like any other tool)
- Worker description becomes the tool docstring

### Implementation Steps
1. During agent setup, register tools for each allowed worker
2. Each tool wraps `call_worker` with attachment resolution
3. Keep `worker_call` for backward compat and dynamic workers

### Limitations
- Workers created mid-run via `worker_create` still need `worker_call`
- Tool names must be valid Python identifiers

---

## Other Ideas (From worker.md)

- First-class Python object with methods like `.run()` or `.delegate_to()`
- Schema repository for output schema resolution
- Structured policies instead of string-based tool rule naming
- State diagram for worker creation → locking → promotion
