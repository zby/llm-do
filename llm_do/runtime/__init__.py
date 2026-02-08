"""Core runtime execution API for llm-do."""
from .approval import (
    AgentApprovalPolicy,
    ApprovalCallback,
    RunApprovalPolicy,
    resolve_approval_callback,
)
from .args import AgentArgs, Attachment, PromptContent, PromptInput, PromptMessages
from .call import CallScope
from .context import CallContext
from .contracts import (
    AgentEntry,
    AgentSpec,
    Entry,
    EventCallback,
    FunctionEntry,
    ModelType,
)
from .runtime import Runtime
from .tooling import ToolDef, ToolsetDef

__all__ = [
    # Runtime
    "Runtime",
    "CallContext",
    "CallScope",
    "Entry",
    "FunctionEntry",
    "AgentEntry",
    "AgentSpec",
    "ModelType",
    "EventCallback",
    "ApprovalCallback",
    "RunApprovalPolicy",
    "AgentApprovalPolicy",
    "resolve_approval_callback",
    "Attachment",
    "PromptContent",
    "PromptMessages",
    "AgentArgs",
    "PromptInput",
    # Tool/toolset defs
    "ToolDef",
    "ToolsetDef",
]
