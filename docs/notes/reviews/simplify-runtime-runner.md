# Simplify Runtime Runner

## Context
Simplification review of `llm_do/runtime/runner.py` and local runtime imports
(`approval.py`, `contracts.py`, `deps.py`, `shared.py`) to remove redundant
indirection and unused flexibility.

## Findings
- **Module-level runner wrapper duplicates `Runtime.run_invocable`**
  - Pattern: redundant parameters / duplicated derived values.
  - Current code:
    ```python
    async def run_invocable(...):
        runtime = Runtime(
            cli_model=model,
            run_approval_policy=approval_policy,
            on_event=on_event,
            verbosity=verbosity,
        )
        return await runtime.run_invocable(
            invocable,
            prompt,
            message_history=list(message_history) if message_history else None,
        )
    ```
  - Simplified version:
    ```python
    # Prefer direct usage; remove runtime/runner.py.
    result, ctx = await Runtime(
        cli_model=model,
        run_approval_policy=approval_policy,
        on_event=on_event,
        verbosity=verbosity,
    ).run_invocable(invocable, prompt, message_history=message_history)
    ```
  - Judgment call: keep a module-level helper only if external callers rely on
    `runtime.run_invocable` as a function instead of constructing `Runtime`.
  - Inconsistency prevention: yes - avoids the wrapper drifting from
    `Runtime.run_invocable` (e.g., different `message_history` handling).

- **Drop unused `WorkerRuntime.from_entry` and the alternate constructor path**
  - Pattern: unused flexibility.
  - Current code:
    ```python
    @classmethod
    def from_entry(...):
        runtime = Runtime(...)
        frame = runtime._build_entry_frame(...)
        return cls(runtime=runtime, frame=frame)

    def __init__(..., runtime: Runtime | None = None, frame: CallFrame | None = None, ...):
        if runtime is not None or frame is not None:
            ...
        else:
            if toolsets is None or model is None:
                raise TypeError(...)
            self.runtime = Runtime(...)
            ...
    ```
  - Simplified version:
    ```python
    def __init__(self, runtime: Runtime, frame: CallFrame) -> None:
        self.runtime = runtime
        self.frame = frame
        self.tools = ToolsProxy(self)
    ```
  - Judgment call: if third-party callers construct `WorkerRuntime` directly,
    provide an explicit factory (e.g., `Runtime.build_worker(...)`) instead of
    keeping two implicit init modes.
  - Inconsistency prevention: yes - removes the partially-initialized pathway
    where some args are silently ignored depending on which branch is taken.

- **Collapse prompt duplication between `Runtime.run_invocable` and `WorkerRuntime.run`**
  - Pattern: duplicated derived values / over-specified interface.
  - Current code:
    ```python
    # Runtime.run_invocable
    ctx = WorkerRuntime(runtime=self, frame=frame)
    input_data: dict[str, str] = {"input": prompt}
    result = await ctx.run(invocable, input_data)

    # WorkerRuntime.run
    if isinstance(input_data, dict) and "input" in input_data:
        self.prompt = str(input_data["input"])
    elif isinstance(input_data, str):
        self.prompt = input_data
    return await self._execute(entry, input_data)
    ```
  - Simplified version:
    ```python
    # Runtime.run_invocable
    ctx = WorkerRuntime(runtime=self, frame=frame)
    ctx.prompt = prompt
    result = await ctx._execute(invocable, {"input": prompt})
    ```
    or
    ```python
    async def run(self, entry: Invocable, prompt: str, input_data: Any | None = None) -> Any:
        self.prompt = prompt
        return await self._execute(entry, input_data if input_data is not None else {"input": prompt})
    ```
  - Judgment call: decide whether `WorkerRuntime.run` should accept only
    `input_data` (status quo) or a dedicated `prompt` parameter to make the
    API unambiguous.
  - Inconsistency prevention: yes - removes the possibility for `prompt` and
    `input_data["input"]` to diverge if a future caller passes both.

- **Store resolved approval settings instead of the full policy**
  - Pattern: redundant parameters / over-specified interface.
  - Current code:
    ```python
    @dataclass(frozen=True, slots=True)
    class RuntimeConfig:
        cli_model: ModelType | None
        run_approval_policy: RunApprovalPolicy
        max_depth: int = 5
        ...

    self._approval_callback = resolve_approval_callback(policy)

    return_permission_errors=run_ctx.deps.run_approval_policy.return_permission_errors
    ```
  - Simplified version:
    ```python
    @dataclass(frozen=True, slots=True)
    class RuntimeConfig:
        cli_model: ModelType | None
        approval_callback: ApprovalCallback
        return_permission_errors: bool = False
        max_depth: int = 5
        ...
    ```
  - Judgment call: keep `RunApprovalPolicy` if you need to surface approval
    mode/caching details later; otherwise store only the resolved callback +
    `return_permission_errors`.
  - Inconsistency prevention: marginal - avoids having both a policy and a
    derived callback if one changes without the other (even though policy is
    frozen today).

- **Avoid double `get_tools()` pass in `WorkerRuntime.call`**
  - Pattern: duplicated derived values.
  - Current code:
    ```python
    for toolset in self.toolsets:
        tools = await toolset.get_tools(run_ctx)
        if name in tools:
            tool = tools[name]
            ...
            return result

    available: list[str] = []
    for toolset in self.toolsets:
        tools = await toolset.get_tools(run_ctx)
        available.extend(tools.keys())
    raise KeyError(...)
    ```
  - Simplified version:
    ```python
    tools_by_name: dict[str, tuple[AbstractToolset[Any], Any]] = {}
    for toolset in self.toolsets:
        for tool_name, tool in (await toolset.get_tools(run_ctx)).items():
            tools_by_name.setdefault(tool_name, (toolset, tool))

    if name not in tools_by_name:
        raise KeyError(f"Tool '{name}' not found. Available: {list(tools_by_name)}")
    toolset, tool = tools_by_name[name]
    ```
  - Judgment call: if toolsets intentionally change their tool list between
    calls, this collapses it to a single snapshot (which is likely the desired
    behavior anyway).
  - Inconsistency prevention: yes - avoids the "not found" error listing a
    different tool set than the lookup pass.

## Open Questions
- Do we want to keep a module-level `run_invocable` helper for external callers,
  or standardize on `Runtime(...).run_invocable(...)`?
- Is `WorkerRuntime` intended to be constructed outside `Runtime`? If so, should
  that be a single explicit factory instead of two implicit init modes?
- Should runtime expose the original `RunApprovalPolicy`, or only the resolved
  `approval_callback` + `return_permission_errors`?

## Conclusion
Runtime runner has several small simplifications available: remove the thin
wrapper module, collapse the unused `WorkerRuntime` constructor path, and
eliminate duplicated prompt handling. The approval policy surface and tool
lookup loop are the next candidates if the goal is to shrink interface area and
prevent future drift.
