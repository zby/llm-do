---
description: Review of type surface with simplification recommendations
---

# Type Catalog Review

## Context
Review of the current type surface (dataclasses, protocols, Pydantic models, type aliases, enums, exceptions)
with an eye toward design quality and opportunities to simplify.

## Findings
### Design observations
- Runtime/manifest renamed its config model to `ManifestRuntimeConfig`, so the old `RuntimeConfig` naming collision is resolved.
- Unused types: `ShellRule` and `ShellDefault` are declared in `llm_do/toolsets/shell/types.py` but never referenced by shell toolset config parsing or validation; config is still raw dicts.
- Unused types: `OAuthModelOverrides` and `resolve_oauth_overrides` have no call sites in runtime/CLI; they are dead surface unless OAuth integration is planned.
- Approval mode is defined in three places: `runtime/manifest.py` (`ApprovalMode`), `ui/runner.py` (`ApprovalMode`), and `RunApprovalPolicy.mode` (inline Literal). This is a drift risk.
- Parallel approval-override shapes exist: `WorkerApprovalOverride` (Pydantic) vs `WorkerApprovalConfig` (dataclass), with normalization via `_normalize_worker_approval_overrides`. This adds adapter logic and multiple "truths" for the same concept.
- Runtime and UI event hierarchies (`llm_do/runtime/events.py` vs `llm_do/ui/events.py`) mirror each other; the adapter keeps them in sync, but any field change requires updating both types and `ui/adapter.py`.

### Simplification recommendations
- Decide on `ShellRule`/`ShellDefault`: either parse/validate shell config into these models (e.g., in `ShellToolset` init or config loader) or remove the unused models/exports to shrink the type surface.
- Decide on OAuth overrides: integrate `resolve_oauth_overrides` into model selection (e.g., in `select_model` or runtime build step) or remove the type + helper until the feature is ready.
- Centralize approval-mode typing: define a single `ApprovalMode` alias (likely in `runtime/approval.py` or `runtime/contracts.py`) and import it into the manifest/UI, or rename with explicit scope (`ManifestApprovalMode` vs `UiApprovalMode`).
- Consolidate approval-override shapes: convert manifest overrides to `WorkerApprovalConfig` at load time, or replace the runtime dataclass with the Pydantic model to avoid dual shapes.
- If event duplication becomes churn, consider a shared event base + UI mixin to reduce duplication; otherwise keep but treat `ui/adapter.py` as the required sync point.

### Type catalog
- llm_do/models.py: ModelError, ModelCompatibilityError, NoModelError, InvalidCompatibleModelsError, ModelConfigError (exceptions)
- llm_do/oauth/__init__.py: OAuthModelOverrides (dataclass)
- llm_do/oauth/storage.py: OAuthCredentials (dataclass); OAuthStorageBackend (Protocol); OAuthProvider (TypeAlias)
- llm_do/runtime/approval.py: ApprovalCallback (TypeAlias); RunApprovalPolicy, WorkerApprovalPolicy (dataclasses)
- llm_do/runtime/args.py: PromptContent, PromptMessages (type aliases); WorkerArgs (BaseModel)
- llm_do/runtime/call.py: CallConfig, CallFrame, CallScope (dataclasses)
- llm_do/runtime/contracts.py: ModelType, EventCallback, MessageLogCallback (TypeAlias); WorkerRuntimeProtocol (Protocol); EntrySpec, AgentSpec (dataclasses)
- llm_do/runtime/events.py: RuntimeEvent, InitialRequestEvent, StatusEvent, UserMessageEvent, TextResponseEvent, ToolCallEvent, ToolResultEvent, DeferredToolEvent, CompletionEvent, ErrorEvent (dataclasses)
- llm_do/runtime/manifest.py: ApprovalMode (TypeAlias); WorkerApprovalOverride, ManifestRuntimeConfig, EntryConfig, ProjectManifest (BaseModel)
- llm_do/runtime/registry.py: AgentRegistry, WorkerSpec (dataclasses)
- llm_do/runtime/runtime.py: WorkerApprovalConfig, RuntimeConfig (dataclasses)
- llm_do/runtime/worker_file.py: WorkerDefinition (dataclass)
- llm_do/toolsets/agent.py: _DefaultAgentToolSchema (BaseModel); AgentToolset (dataclass)
- llm_do/toolsets/filesystem.py: ReadResult, ReadFileArgs, WriteFileArgs, ListFilesArgs (BaseModel)
- llm_do/runtime/tooling.py: ToolDef, ToolsetDef (TypeAlias)
- llm_do/toolsets/shell/execution.py: ShellError, ShellBlockedError (exceptions)
- llm_do/toolsets/shell/types.py: ShellResult, ShellRule, ShellDefault (BaseModel)
- llm_do/toolsets/shell/toolset.py: ShellArgs (BaseModel)
- llm_do/ui/controllers/approval_workflow.py: PendingApproval (dataclass)
- llm_do/ui/controllers/exit_confirmation.py: ExitDecision (Enum); ExitConfirmationController (dataclass)
- llm_do/ui/controllers/input_history.py: HistoryNavigation, InputHistoryController (dataclasses)
- llm_do/ui/controllers/worker_runner.py: RunTurnFn (TypeAlias); WorkerRunner (dataclass)
- llm_do/ui/events.py: UIEvent, InitialRequestEvent, StatusEvent, UserMessageEvent, TextResponseEvent, ToolCallEvent, ToolResultEvent, DeferredToolEvent, CompletionEvent, ErrorEvent, ApprovalRequestEvent (dataclasses)
- llm_do/ui/runner.py: UiMode, ApprovalMode, UiEventSink, RuntimeEventSink, EntryFactory, RuntimeFactory (TypeAlias); RunUiResult (dataclass)

## Open Questions
- Should shell config be formally validated with `ShellRule`/`ShellDefault`, or are these types better removed until needed?
- Is OAuth override flow intended to be wired into runtime/CLI soon, or should `OAuthModelOverrides` be removed for now?
- Where should `ApprovalMode` live to avoid drift (runtime/approval, runtime/contracts), and should UI/manifest import it?
- Do we want to keep two approval-override shapes (`WorkerApprovalOverride` vs `WorkerApprovalConfig`), or collapse to one?
- Is the UI/runtime event duplication worth keeping for decoupling, or should we introduce a shared base to reduce churn?
