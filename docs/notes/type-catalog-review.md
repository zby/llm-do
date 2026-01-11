# Type Catalog Review

## Context
Review of the current type surface (dataclasses, protocols, Pydantic models, type aliases, enums, exceptions)
with an eye toward design quality and avoiding wrapper types that add little behavior.

## Findings
### Design observations
- Model typing drift: `ModelType` permits `str | Model`, but `RunContext` still casts to a concrete `Model` when calling tools; the type system cannot represent "resolved" vs "unresolved" (`llm_do/runtime/contracts.py`, `llm_do/runtime/deps.py`).
- Wrapper layering: toolsets can be wrapped via `ToolsetRef` resolution -> `WorkerToolset` -> `ApprovalToolset` -> `ApprovalDeniedResultToolset`, which adds indirection and complicates debugging (`llm_do/runtime/worker.py`, `llm_do/runtime/approval.py`, `llm_do/toolsets/loader.py`).
- Unused types: `ShellRule`/`ShellDefault` are defined but never referenced; `OAuthModelOverrides` + `resolve_oauth_overrides` are not wired into runtime or CLI (`llm_do/toolsets/shell/types.py`, `llm_do/oauth/__init__.py`).
- Naming collision: `RuntimeConfig` is defined in both `llm_do/runtime/manifest.py` (Pydantic model) and `llm_do/runtime/shared.py` (dataclass), which invites mis-imports and conceptual confusion.

### Simplification recommendations
- Resolve models to concrete `Model` objects before building `RunContext` (or split into `ModelRef` vs `ResolvedModel`) so runtime types stop relying on casts.
- Either wire `ShellRule`/`ShellDefault` into shell config parsing/validation or remove them.
- Either integrate OAuth overrides into runtime model selection or remove the unused type and helper.
- Rename one of the `RuntimeConfig` types (e.g., `ManifestRuntimeConfig` vs `RuntimeConfig`) to make boundaries explicit.
- Consider a helper for toolset wrapper introspection or a slimmer wrapper chain to reduce indirection.

### Type catalog
```
llm_do/models.py: ModelCompatibilityError, NoModelError, InvalidCompatibleModelsError, ModelConfigError, ModelValidationResult
llm_do/oauth/__init__.py: OAuthModelOverrides
llm_do/oauth/storage.py: OAuthProvider, OAuthCredentials, OAuthStorageBackend
llm_do/runtime/approval.py: ApprovalCallback, RunApprovalPolicy, WorkerApprovalPolicy
llm_do/runtime/args.py: PromptSpec, WorkerArgs, WorkerInput
llm_do/runtime/call.py: CallConfig, CallFrame
llm_do/runtime/contracts.py: ModelType, EventCallback, MessageLogCallback, WorkerRuntimeProtocol, Entry
llm_do/runtime/manifest.py: ApprovalMode, RuntimeConfig, EntryConfig, ProjectManifest
llm_do/runtime/registry.py: EntryRegistry, WorkerSpec
llm_do/runtime/shared.py: RuntimeConfig
llm_do/runtime/worker.py: ToolsetRef, WorkerToolset, EntryFunction, Worker
llm_do/runtime/worker_file.py: WorkerDefinition
llm_do/toolsets/filesystem.py: ReadResult
llm_do/toolsets/loader.py: ToolsetBuildContext
llm_do/toolsets/shell/execution.py: ShellError, ShellBlockedError
llm_do/toolsets/shell/types.py: ShellResult, ShellRule, ShellDefault
llm_do/ui/controllers/approval_workflow.py: PendingApproval
llm_do/ui/controllers/exit_confirmation.py: ExitDecision, ExitConfirmationController
llm_do/ui/controllers/input_history.py: HistoryNavigation, InputHistoryController
llm_do/ui/controllers/worker_runner.py: RunTurnFn, WorkerRunner
llm_do/ui/events.py: UIEvent, InitialRequestEvent, StatusEvent, UserMessageEvent, TextResponseEvent, ToolCallEvent, ToolResultEvent, DeferredToolEvent, CompletionEvent, ErrorEvent, ApprovalRequestEvent
```

## Open Questions
- Should model resolution happen earlier so runtime types can assume a concrete `Model` in `RunContext`?
- Are `ShellRule`/`ShellDefault` intended for enforcement, or should they be removed for now?
- Is the OAuth override flow intended to be wired into runtime/CLI soon, or should it be dropped?
- Should the manifest/runtime `RuntimeConfig` types be renamed to clarify ownership?
- Do we want a dedicated helper or a slimmer wrapper chain for toolset wrapping?
