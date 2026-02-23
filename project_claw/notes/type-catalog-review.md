---
description: Current review of llm_do type surface with simplification candidates (2026-01-29)
---

# Type Catalog Review

## Context
Run date: 2026-01-29. Reviewed dataclasses, protocols, Pydantic models, TypeAliases, enums, and exception classes in llm_do/.

## Type Catalog (by module)

### llm_do/models.py
- TypeAlias: ModelInput = str | Model
- Exceptions: ModelError, ModelCompatibilityError, NoModelError, InvalidCompatibleModelsError, ModelConfigError

### llm_do/runtime/contracts.py
- TypeAliases: ModelType, EventCallback, MessageLogCallback
- Protocol: CallContextProtocol
- Dataclasses: FunctionEntry, AgentSpec, AgentEntry

### llm_do/runtime/events.py
- Dataclasses: UserMessageEvent, RuntimeEvent

### llm_do/runtime/call.py
- Dataclasses: CallConfig, CallFrame, CallScope

### llm_do/runtime/registry.py
- Dataclasses: AgentRegistry, AgentFileSpec

### llm_do/runtime/runtime.py
- Dataclasses: AgentApprovalConfig, RuntimeConfig

### llm_do/runtime/agent_file.py
- Dataclass: AgentDefinition

### llm_do/runtime/approval.py
- TypeAlias (implicit): ApprovalCallback
- Dataclasses: RunApprovalPolicy, AgentApprovalPolicy

### llm_do/runtime/manifest.py
- TypeAlias: ApprovalMode = Literal["prompt", "approve_all", "reject_all"]
- Pydantic models: AgentApprovalOverride, ManifestRuntimeConfig, EntryConfig, ProjectManifest

### llm_do/runtime/args.py
- Pydantic model: AgentArgs
- TypeAliases (implicit): PromptContent, PromptMessages

### llm_do/runtime/tooling.py
- TypeAliases: ToolDef, ToolsetDef

### llm_do/toolsets/agent.py
- Pydantic model: _DefaultAgentToolSchema
- Dataclass: AgentToolset

### llm_do/toolsets/dynamic_agents.py
- Pydantic models: AgentCreateArgs, AgentCallArgs
- Dataclass: DynamicAgentsToolset

### llm_do/toolsets/filesystem.py
- Pydantic models: ReadResult, ReadFileArgs, WriteFileArgs, ListFilesArgs

### llm_do/toolsets/shell/types.py
- Pydantic models: ShellResult, ShellRule, ShellDefault

### llm_do/toolsets/shell/toolset.py
- Pydantic model: ShellArgs

### llm_do/toolsets/shell/execution.py
- Exceptions: ShellError, ShellBlockedError

### llm_do/oauth/storage.py
- TypeAlias: OAuthProvider = Literal["anthropic"]
- Protocol: OAuthStorageBackend
- Dataclass: OAuthCredentials

### llm_do/oauth/__init__.py
- Dataclass: OAuthModelOverrides

### llm_do/ui/events.py
- Dataclasses: UIEvent, InitialRequestEvent, StatusEvent, UserMessageEvent, TextResponseEvent, ToolCallEvent, ToolResultEvent, DeferredToolEvent, CompletionEvent, ErrorEvent, ApprovalRequestEvent

### llm_do/ui/runner.py
- TypeAliases (implicit): UiMode, ApprovalMode, UiEventSink, RuntimeEventSink, EntryFactory, RuntimeFactory
- Dataclass: RunUiResult

### llm_do/ui/controllers/approval_workflow.py
- Dataclass: PendingApproval

### llm_do/ui/controllers/agent_runner.py
- TypeAlias (implicit): RunTurnFn
- Dataclass: AgentRunner

### llm_do/ui/controllers/exit_confirmation.py
- Enum: ExitDecision
- Dataclass: ExitConfirmationController

### llm_do/ui/controllers/input_history.py
- Dataclasses: HistoryNavigation, InputHistoryController

## Design Observations
- Unused UI events: InitialRequestEvent, StatusEvent, and DeferredToolEvent are exported but have no emitters or call sites outside llm_do/ui/events.py and llm_do/ui/__init__.py.
- ShellRule and ShellDefault are defined and exported, but shell config is still raw dicts; no validation uses those models.
- OAuthModelOverrides and resolve_oauth_overrides have no call sites in runtime/CLI; the type exists without a feature path.
- ApprovalMode is defined in multiple places (runtime/manifest.py, ui/runner.py, and RunApprovalPolicy.mode literal), which is a drift risk.
- Approval override shapes are duplicated: AgentApprovalOverride (Pydantic) vs AgentApprovalConfig (dataclass), with normalization glue to bridge them.
- Naming collisions remain: runtime.events.UserMessageEvent vs ui.events.UserMessageEvent; also ApprovalCallback is defined locally while pydantic_ai_blocking_approval exports a similarly named type.
- The toolset wrapper has been removed; toolsets now use ToolsetDef (callables or instances) via TOOLSETS registry.
- `llm_do/toolsets/loader.py` has been removed; `runtime/tooling.py` is the canonical tool/toolset type surface.

## Simplification Recommendations

### 1) Prune or wire the unused UI event types
- What: Remove InitialRequestEvent/StatusEvent/DeferredToolEvent or add emitters in ui/adapter.py + ui/runner.py to justify their presence.
- Why: These types are dead surface today and increase cognitive load when scanning event hierarchies.
- Trade-offs: Removing breaks external integrations that might import them; wiring adds implementation work but preserves intent.
- Priority: Must-have (either remove or implement) to keep UI event surface honest.

### 2) Decide on ShellRule/ShellDefault ownership
- What: Either parse shell toolset config into ShellRule/ShellDefault in ShellToolset.__init__ (or a loader) or delete the models/exports.
- Why: Current config is untyped dicts, so the models provide no safety and can drift.
- Trade-offs: Validation adds code and migration; removing drops a potential documentation aid.
- Priority: Must-have, because config correctness is security-adjacent.

### 3) Wire OAuth overrides or remove them
- What: Integrate resolve_oauth_overrides into model selection/runtime setup, or remove OAuthModelOverrides and the helper until needed.
- Why: Unused types create false affordances and complicate the type catalog.
- Trade-offs: Wiring adds runtime complexity and testing; removal could delay OAuth functionality.
- Priority: Should-have.

### 4) Centralize approval mode typing
- What: Define a single ApprovalMode alias (e.g., in runtime/approval.py or runtime/contracts.py) and import it everywhere.
- Why: Multiple Literals make it easy to drift and harder to refactor.
- Trade-offs: Minimal refactor across manifest/UI files.
- Priority: Should-have.

### 5) Drop worker_* backcompat types and aliases (Done)
- What: Removed WorkerApprovalConfig/WorkerApprovalOverride/WorkerApprovalPolicy/WorkerArgs/WorkerRunner and deprecated worker_* parameters/fields across runtime/UI/manifest.
- Why: Project policy says no backcompat; keeping these doubled the naming surface and logic branches.
- Trade-offs: Breaking change for any external consumers relying on worker naming, but project constraints allow it.
- Priority: Completed in this review cycle.

### 6) Collapse approval override shapes
- What: Choose either AgentApprovalOverride (Pydantic) or AgentApprovalConfig (dataclass) as the single runtime shape.
- Why: Duplicate shapes require normalization glue and increase type drift risk.
- Trade-offs: Using Pydantic everywhere adds dependency weight; using dataclass everywhere requires manifest conversion at load time.
- Priority: Should-have.

### 7) Remove toolset wrapper (Done)
- What: Replaced the wrapper dataclass with raw ToolsetDef (ToolsetFunc/AbstractToolset).
- Why: The wrapper added a class solely to carry a single factory.
- Trade-offs: Removing reduces type count but loses a convenient place to hang future attributes.
- Priority: Completed.

## Open Questions
- Should the UI ever emit InitialRequestEvent/StatusEvent/DeferredToolEvent, or should they be removed entirely?
- Is shell config validation a near-term goal, or should ShellRule/ShellDefault be dropped until it is?
- Is OAuth override wiring planned for the runtime (and if so, where should it live)?
- Where should ApprovalMode live so both manifest and UI share it without duplication?
- Should runtime and UI event naming be disambiguated to avoid UserMessageEvent collisions?
