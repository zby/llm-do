# Type Catalog Review

## Context
Review of the current type surface (dataclasses, protocols, Pydantic models, enums, exceptions)
with an eye toward design quality and avoiding wrapper types that add little behavior.

## Findings
### Design observations
- Model typing drift: `ModelType` is `str`, but runtime casts it to a concrete PydanticAI `Model` when building `RunContext`, so the static type doesn’t match runtime behavior (`llm_do/runtime/contracts.py`, `llm_do/runtime/context.py`).
- Wrapper layering: toolsets can be wrapped by `ToolInvocable` → `ToolsetRef` → `ApprovalDeniedResultToolset`/`ApprovalToolset`, which adds indirection and can obscure type checks and debugging (`llm_do/runtime/worker.py`, `llm_do/toolsets/loader.py`, `llm_do/runtime/approval.py`).
- Mutable default: `WorkerInput.attachments` uses a mutable default list; consider `Field(default_factory=list)` to avoid shared state (`llm_do/runtime/worker.py`).
- Unused/loosely wired types: `ShellRule`/`ShellDefault` are defined but config matching uses raw dicts; either parse configs into these models or remove them (`llm_do/toolsets/shell/types.py`, `llm_do/toolsets/shell/execution.py`).
- `OAuthModelOverrides` is declared but not referenced elsewhere; wire it into the runtime or remove to keep the type surface tight (`llm_do/oauth/__init__.py`).

### Type catalog
```
llm_do/models.py: ModelCompatibilityError, NoModelError, InvalidCompatibleModelsError, ModelConfigError, ModelValidationResult
llm_do/runtime/contracts.py: ModelType, EventCallback, WorkerRuntimeProtocol, Invocable
llm_do/runtime/approval.py: ApprovalCallback, RunApprovalPolicy, WorkerApprovalPolicy, ApprovalDeniedResultToolset
llm_do/runtime/context.py: _UnsetType, ToolsProxy, UsageCollector, RuntimeConfig, CallFrame, WorkerRuntime
llm_do/runtime/worker.py: WorkerInput, _DictValidator, ToolInvocable, Worker
llm_do/runtime/worker_file.py: WorkerDefinition, WorkerFileParser
llm_do/ui/events.py: UIEvent, InitialRequestEvent, StatusEvent, UserMessageEvent, TextResponseEvent, ToolCallEvent, ToolResultEvent, DeferredToolEvent, CompletionEvent, ErrorEvent, ApprovalRequestEvent
llm_do/ui/display.py: DisplayBackend, RichDisplayBackend, HeadlessDisplayBackend, JsonDisplayBackend, TextualDisplayBackend
llm_do/ui/controllers/worker_runner.py: RunTurnFn, WorkerRunner
llm_do/ui/controllers/approval_workflow.py: PendingApproval, ApprovalWorkflowController
llm_do/ui/controllers/exit_confirmation.py: ExitDecision, ExitConfirmationController
llm_do/ui/controllers/input_history.py: HistoryNavigation, InputHistoryController
llm_do/ui/app.py: LlmDoApp
llm_do/ui/widgets/messages.py: BaseMessage, AssistantMessage, UserMessage, ToolCallMessage, ToolResultMessage, StatusMessage, TurnSeparator, ErrorMessage, ApprovalPanel, MessageContainer
llm_do/toolsets/filesystem.py: ReadResult, FileSystemToolset
llm_do/toolsets/loader.py: ToolsetRef, ToolsetBuildContext
llm_do/toolsets/shell/types.py: ShellResult, ShellRule, ShellDefault
llm_do/toolsets/shell/execution.py: ShellError, ShellBlockedError
llm_do/toolsets/shell/toolset.py: ShellToolset
llm_do/oauth/storage.py: OAuthProvider, OAuthCredentials, OAuthStorageBackend, FileSystemStorage, OAuthStorage
llm_do/oauth/__init__.py: OAuthModelOverrides
```

## Open Questions
- Should `ModelType` include concrete PydanticAI model objects (OAuth-wrapped), or should conversion happen earlier to keep it string-only?
- Do we want to reduce wrapper layers around toolsets (e.g., a binding struct or explicit unwrap helper), or keep current indirection?
- Are `ShellRule`/`ShellDefault` meant to be enforced/validated, or can they be removed?
- Is `OAuthModelOverrides` intended to be wired into the CLI/runtime soon, or should it be removed for now?
