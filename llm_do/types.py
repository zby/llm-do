"""Type definitions and data models for llm-do workers.

This module contains all the data models and type definitions used throughout
the llm-do system, including worker definitions, contexts, and results.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Literal, Optional, Protocol, Type, Union, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field
from pydantic_ai.messages import BinaryContent
from pydantic_ai.models import Model as PydanticAIModel

from pydantic_ai_blocking_approval import ApprovalController, ApprovalDecision

from .attachments import AttachmentInput, AttachmentPayload, AttachmentPolicy



# ---------------------------------------------------------------------------
# Worker artifact models
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Toolset configuration types
# ---------------------------------------------------------------------------


class CustomToolConfig(BaseModel):
    """Configuration for a single custom tool.

    Presence in config means the tool is allowed (whitelist model).
    Tools not in config are not exposed to the LLM.
    """

    pre_approved: bool = Field(
        default=False,
        description="If True, skip approval for this tool. Secure by default (requires approval)."
    )


class ShellToolsetConfig(BaseModel):
    """Configuration for the shell toolset."""

    rules: List["ShellRule"] = Field(
        default_factory=list,
        description="Pattern-based rules for shell command approval"
    )
    default: Optional["ShellDefault"] = Field(
        default=None,
        description="Default behavior for commands not matching any rule"
    )


class DelegationToolsetConfig(BaseModel):
    """Configuration for the delegation toolset.

    Keys are tool names to expose (worker names, worker_call, worker_create).
    Values are tool-specific config (currently unused).
    """
    model_config = ConfigDict(extra="allow")


# ToolsetsConfig removed - replaced by Dict[str, Any] with class paths as keys.
# The typed config classes above (ShellToolsetConfig, DelegationToolsetConfig, etc.)
# are kept as documentation of expected config structure for built-in toolsets.


# ---------------------------------------------------------------------------
# Shell tool types (imported from shell subpackage)
# ---------------------------------------------------------------------------

from .shell.types import ShellDefault, ShellResult, ShellRule


# ---------------------------------------------------------------------------
# Server-side tools (provider-executed)
# ---------------------------------------------------------------------------


class ServerSideToolConfig(BaseModel):
    """Configuration for a server-side tool executed by the LLM provider.

    These tools run on the provider's infrastructure (Anthropic, OpenAI, etc.),
    not locally. Examples: web search, code execution, image generation.

    Provider support varies - check pydantic-ai docs for compatibility.
    """

    tool_type: Literal["web_search", "web_fetch", "code_execution", "image_generation"] = Field(
        description="Type of server-side tool."
    )
    max_uses: Optional[int] = Field(
        default=None,
        description="Maximum number of times the tool can be used (web_search only, Anthropic)"
    )
    blocked_domains: Optional[List[str]] = Field(
        default=None,
        description="Domains to block (web_search only, mutually exclusive with allowed_domains for Anthropic)"
    )
    allowed_domains: Optional[List[str]] = Field(
        default=None,
        description="Only allow these domains (web_search only, mutually exclusive with blocked_domains for Anthropic)"
    )


class WorkerDefinition(BaseModel):
    """Persisted worker artifact."""

    name: str
    description: Optional[str] = None
    instructions: Optional[str] = None  # Acts as the worker's system prompt. Optional: can load from prompts/{name}.{txt,jinja2,j2,md}
    model: Optional[str] = None
    compatible_models: Optional[List[str]] = Field(
        default=None,
        description="Model compatibility patterns. Supports wildcards: '*' (any), 'anthropic:*' (provider), "
                    "'anthropic:claude-haiku-*' (family). None/unset means any model. Empty list is invalid."
    )
    output_schema_ref: Optional[str] = None

    # Toolsets configuration (class paths -> config dicts)
    # Example: {"shell": {"rules": [...]}, "delegation": {"summarizer": {}, "worker_call": {}}}
    # Supports aliases (shell, delegation, filesystem) or full class paths
    toolsets: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Toolsets to load. Keys are class paths or aliases, values are config dicts."
    )

    # Attachment policy (applies to inbound attachments)
    attachment_policy: AttachmentPolicy = Field(default_factory=AttachmentPolicy)

    # Server-side tools (executed by LLM provider, not local toolsets)
    server_side_tools: List[ServerSideToolConfig] = Field(
        default_factory=list,
        description="Server-side tools executed by the LLM provider (web_search, code_execution, etc.)"
    )

    locked: bool = False

    model_config = ConfigDict(arbitrary_types_allowed=True)


class WorkerSpec(BaseModel):
    """Minimal LLM-facing worker description."""

    name: str
    instructions: str
    description: Optional[str] = None
    output_schema_ref: Optional[str] = None
    model: Optional[str] = None


class WorkerCreationDefaults(BaseModel):
    """Host-configured defaults used when persisting workers."""

    default_model: Optional[str] = None
    default_toolsets: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Default toolsets configuration (class paths -> config dicts)"
    )
    default_attachment_policy: AttachmentPolicy = Field(
        default_factory=AttachmentPolicy
    )

    model_config = ConfigDict(arbitrary_types_allowed=True)

    def expand_spec(self, spec: WorkerSpec) -> WorkerDefinition:
        """Apply defaults to a ``WorkerSpec`` to create a full definition."""

        attachment_policy = self.default_attachment_policy.model_copy()
        toolsets = dict(self.default_toolsets) if self.default_toolsets else None
        return WorkerDefinition(
            name=spec.name,
            description=spec.description,
            instructions=spec.instructions,
            model=spec.model or self.default_model,
            output_schema_ref=spec.output_schema_ref,
            toolsets=toolsets,
            attachment_policy=attachment_policy,
            locked=False,
        )


class WorkerRunResult(BaseModel):
    """Structured result from a worker execution."""

    output: Any
    messages: List[Any] = Field(default_factory=list)  # PydanticAI messages from agent run


# ---------------------------------------------------------------------------
# Type aliases and callbacks
# ---------------------------------------------------------------------------


OutputSchemaResolver = Callable[[WorkerDefinition], Optional[Type[BaseModel]]]

ModelLike = Union[str, PydanticAIModel]

MessageCallback = Callable[[List[Any]], None]


# ---------------------------------------------------------------------------
# Runtime context and data structures
# ---------------------------------------------------------------------------


@runtime_checkable
class ToolContext(Protocol):
    """Interface for tools needing nested agent calls.

    This Protocol defines the minimal interface that tools can depend on
    when they need to make nested worker/agent calls. WorkerContext implements
    this protocol.

    The spectrum of tools:
    - Pure tools: No LLM, just computation (read_file, calculate)
    - Hybrid tools: Call LLM when needed (smart_refactor)
    - Agent tools: Full LLM agent loop (code_reviewer)

    Tools that need nested calls declare dependency on ToolContext via
    PydanticAI's RunContext[ToolContext] mechanism.
    """

    @property
    def depth(self) -> int:
        """Current nesting depth (0 = top-level worker)."""
        ...

    @property
    def approval_controller(self) -> Any:  # ApprovalController
        """Controller for tool approval decisions."""
        ...

    @property
    def cost_tracker(self) -> Optional[Any]:
        """Cost tracking across nested calls (future enhancement)."""
        ...

    async def call_worker(self, worker: str, input_data: Any) -> Any:
        """Delegate to another worker.

        Args:
            worker: Name of the worker to call.
            input_data: Input payload for the worker.

        Returns:
            The worker's output (unwrapped from WorkerRunResult).

        Raises:
            RecursionError: If max depth exceeded.
        """
        ...



@dataclass
class WorkerContext:
    """Runtime context passed to worker execution.

    This contains all the dependencies and state needed during worker execution,
    grouped by concern:
    - Core: worker definition, model, approval handling
    - Delegation: registry access, worker creation (when delegation toolset enabled)
    - I/O: attachments for file operations
    - Callbacks: streaming and custom tools
    """

    # Core - always needed
    worker: WorkerDefinition
    effective_model: Optional[ModelLike]
    approval_controller: ApprovalController

    # Nesting control (implements ToolContext protocol)
    depth: int = 0  # Current nesting depth (0 = top-level worker)
    cost_tracker: Optional[Any] = None  # Future enhancement: track costs across nested calls

    # Delegation - populated when delegation toolset is enabled
    registry: Any = None  # WorkerRegistry - avoid circular import
    creation_defaults: Optional[WorkerCreationDefaults] = None

    # I/O - attachments for file operations
    attachments: List[AttachmentPayload] = field(default_factory=list)

    # Callbacks and extensions
    message_callback: Optional[MessageCallback] = None
    custom_tools_path: Optional[Path] = None  # Path to tools.py if worker has custom tools

    async def call_worker(self, worker: str, input_data: Any) -> Any:
        """Delegate to another worker (implements ToolContext protocol).

        This is the primary method for tools to make nested worker calls.
        Depth checking and increment are handled by call_worker_async.

        Args:
            worker: Name of the worker to delegate to.
            input_data: Input payload for the worker.

        Returns:
            The worker's output (unwrapped from WorkerRunResult).

        Raises:
            RecursionError: If max worker depth would be exceeded.
        """
        # Late import to avoid circular dependency (runtime imports types)
        from .runtime import call_worker_async

        result = await call_worker_async(
            registry=self.registry,
            worker=worker,
            input_data=input_data,
            caller_context=self,
        )
        return result.output


@dataclass
class AgentExecutionContext:
    """Prepared context for agent execution (shared by sync and async runners)."""
    prompt: Union[str, List[Union[str, BinaryContent]]]
    agent_kwargs: Dict[str, Any]
    event_handler: Optional[Callable]
    model_label: Optional[str]
    started_at: Optional[float]
    emit_status: Optional[Callable[[str, Optional[float]], None]]


# ---------------------------------------------------------------------------
# Agent runner type
# ---------------------------------------------------------------------------


AgentRunner = Callable[[WorkerDefinition, Any, WorkerContext, Optional[Type[BaseModel]]], Any]
"""Type alias for the execution strategy used by ``run_worker_async``.

This interface allows swapping the underlying agent execution logic (e.g., for
unit testing or using a different agent framework) while keeping the
``run_worker_async`` orchestration logic (approvals, context) intact.
"""
