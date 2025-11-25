# Dependency Injection Architecture

llm-do uses two complementary dependency injection systems:

## PydanticAI's Built-in DI

We use PydanticAI's standard dependency injection for passing runtime context into tools:

```python
# Define context type
agent = Agent(model=..., deps_type=WorkerContext)

# Inject dependencies when running
result = await agent.run(input_data, deps=context)

# Tools receive context via RunContext
@agent.tool
async def read_file(ctx: RunContext[WorkerContext], path: str, ...):
    # File operations are handled through registered Sandbox toolset
    # Tools like read_file, write_file, list_files are registered automatically
    # based on the worker's sandbox configuration
    ...
```

This follows PydanticAI conventions exactly. See [`tools.py`](../llm_do/tools.py) for examples.

## Custom Protocol-Based DI

Our protocol layer solves a different problem: **enabling recursive worker calls without circular imports**.

**The problem:**
- Tools need to call back into the runtime to delegate to other workers
- `tools.py` can't import `runtime.py` directly (circular dependency)
- Tools are registered before the runtime exists

**The solution:**
```python
# protocols.py - Abstract interfaces
class WorkerDelegator(Protocol):
    async def call_async(self, worker: str, ...) -> Any: ...
    def call_sync(self, worker: str, ...) -> Any: ...

# tools.py - Depends on protocols, not runtime
def register_worker_tools(agent, context, delegator: WorkerDelegator, ...):
    @agent.tool(name="worker_call")
    async def worker_call_tool(...):
        return await delegator.call_async(...)  # Uses injected implementation

# runtime.py - Provides concrete implementation
class RuntimeDelegator:
    async def call_async(self, worker: str, ...) -> Any:
        # Actual delegation logic with approval enforcement
        ...

# Wired together in runtime.py
delegator = RuntimeDelegator(context)
register_worker_tools(agent, context, delegator=delegator, ...)
```

## Why Both?

The two systems are complementary:

- **PydanticAI's DI**: Passes data/state into tools ("how do tools access context?")
- **Protocol-based DI**: Enables callbacks without coupling ("how do tools call runtime operations?")

This architecture achieves:
- ✅ Clean separation of concerns
- ✅ Zero circular dependencies
- ✅ Testability (inject mock implementations)
- ✅ Recursive worker calls (workers calling workers)

See [`protocols.py`](../llm_do/protocols.py), [`tools.py`](../llm_do/tools.py), and [`runtime.py`](../llm_do/runtime.py) for implementation details.
