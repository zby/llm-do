from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

import pytest
from pydantic import BaseModel, TypeAdapter
from pydantic_ai.models.test import TestModel
from pydantic_ai.tools import RunContext, ToolDefinition
from pydantic_ai.toolsets import AbstractToolset, ToolsetTool

from llm_do.models import validate_model_compatibility
from llm_do.runtime import WorkerRuntime
from llm_do.runtime.approval import RunApprovalPolicy
from llm_do.runtime.call import CallFrame
from llm_do.runtime.shared import RuntimeConfig
from llm_do.runtime.worker import Worker
from tests.runtime.helpers import build_runtime_context


class CaptureArgs(BaseModel):
    value: int


class CaptureToolset(AbstractToolset[Any]):
    def __init__(self) -> None:
        self.seen_model: Optional[str] = None

    @property
    def id(self) -> str | None:
        return "capture"

    async def get_tools(self, run_ctx: RunContext[Any]) -> dict[str, ToolsetTool[Any]]:
        tool_def = ToolDefinition(
            name="capture",
            description="Capture run context model.",
            parameters_json_schema=CaptureArgs.model_json_schema(),
        )
        return {
            "capture": ToolsetTool(
                toolset=self,
                tool_def=tool_def,
                max_retries=0,
                args_validator=TypeAdapter(CaptureArgs).validator,
            )
        }

    async def call_tool(
        self,
        name: str,
        tool_args: dict[str, Any],
        run_ctx: RunContext[Any],
        tool: ToolsetTool[Any],
    ) -> Any:
        self.seen_model = run_ctx.model
        return run_ctx.model


@dataclass
class DummyEntry:
    """Mock entry that creates a child context with its toolsets, like Worker does."""

    name: str
    toolsets: list[AbstractToolset[Any]]
    model: Optional[str] = None

    async def call(
        self,
        input_data: Any,
        config: RuntimeConfig,
        state: CallFrame,
        run_ctx: RunContext[WorkerRuntime],
    ) -> Any:
        # Like Worker.call(), fork state and create a child context with our toolsets
        resolved_model = self.model if self.model is not None else state.model
        child_runtime = run_ctx.deps.spawn_child(toolsets=self.toolsets, model=resolved_model)
        return await child_runtime.call("capture", {"value": 1})


@pytest.mark.anyio
async def test_worker_uses_context_model_for_tool_calls() -> None:
    """Entry without model uses context's model for tool calls."""
    toolset = CaptureToolset()
    entry = DummyEntry(name="child", toolsets=[toolset])
    # In production, ctx.model is already resolved via Runtime entry setup.
    ctx = build_runtime_context(toolsets=[], model="resolved-model")

    await ctx._execute(entry, {"input": "hi"})

    assert toolset.seen_model == "resolved-model"


@pytest.mark.anyio
async def test_worker_model_overrides_context_model_for_tool_calls() -> None:
    """Entry with explicit model overrides context's model."""
    toolset = CaptureToolset()
    entry = DummyEntry(name="child", toolsets=[toolset], model="worker-model")
    ctx = build_runtime_context(toolsets=[], model="context-model")

    await ctx._execute(entry, {"input": "hi"})

    assert toolset.seen_model == "worker-model"


# --- compatible_models tests ---
@pytest.mark.anyio
async def test_worker_compatible_models_allows_matching_model() -> None:
    """Worker runs successfully when model is in compatible_models."""
    worker = Worker(
        name="strict",
        instructions="Be strict.",
        model="test",  # Use "test" string - PydanticAI converts to TestModel
        compatible_models=["test", "other-model"],
    )
    ctx = build_runtime_context(
        toolsets=[],
        model="test",
        run_approval_policy=RunApprovalPolicy(mode="approve_all"),
    )
    run_ctx = RunContext(
        deps=ctx,
        model=None,
        usage=None,
        prompt="test",
    )

    # Should not raise - "test" is in compatible_models
    result = await worker.call({"input": "hi"}, ctx.config, ctx.frame, run_ctx)
    assert result is not None


@pytest.mark.anyio
async def test_worker_incompatible_model_raises() -> None:
    """Worker raises ValueError when model is not in compatible_models."""
    worker = Worker(
        name="strict",
        instructions="Be strict.",
        compatible_models=["model-a", "model-b"],
    )
    ctx = build_runtime_context(
        toolsets=[],
        model="incompatible-model",
        run_approval_policy=RunApprovalPolicy(mode="approve_all"),
    )
    run_ctx = RunContext(
        deps=ctx,
        model=None,
        usage=None,
        prompt="test",
    )

    with pytest.raises(ValueError, match="not compatible with worker"):
        await worker.call({"input": "hi"}, ctx.config, ctx.frame, run_ctx)


@pytest.mark.anyio
async def test_worker_no_compatible_models_allows_any() -> None:
    """Worker allows any model when compatible_models is None."""
    worker = Worker(
        name="flexible",
        instructions="Be flexible.",
        model="test",  # Use "test" string - PydanticAI converts to TestModel
        compatible_models=None,  # No restriction
    )
    ctx = build_runtime_context(
        toolsets=[],
        model="any-model",
        run_approval_policy=RunApprovalPolicy(mode="approve_all"),
    )
    run_ctx = RunContext(
        deps=ctx,
        model=None,
        usage=None,
        prompt="test",
    )

    # Should not raise
    result = await worker.call({"input": "hi"}, ctx.config, ctx.frame, run_ctx)
    assert result is not None


# --- Pattern matching tests for compatible_models ---
# These tests verify that wildcard patterns in compatible_models work correctly.
# Workers without model set inherit from context, so we test pattern matching
# against the context's model.


@pytest.mark.anyio
async def test_worker_wildcard_star_allows_any_model() -> None:
    """Worker with compatible_models=['*'] allows any model."""
    worker = Worker(
        name="any-model-worker",
        instructions="Accept any model.",
        model="test",  # Worker's own model (matches '*')
        compatible_models=["*"],
    )
    ctx = build_runtime_context(
        toolsets=[],
        model="test",
        run_approval_policy=RunApprovalPolicy(mode="approve_all"),
    )
    run_ctx = RunContext(
        deps=ctx,
        model=None,
        usage=None,
        prompt="test",
    )

    # Should not raise - '*' matches "test"
    result = await worker.call({"input": "hi"}, ctx.config, ctx.frame, run_ctx)
    assert result is not None


@pytest.mark.anyio
async def test_worker_wildcard_star_allows_inherited_model() -> None:
    """Worker without model inherits from context; '*' pattern allows any."""
    worker = Worker(
        name="any-model-worker",
        instructions="Accept any model.",
        # No model set - will inherit from context
        compatible_models=["*"],
    )
    ctx = build_runtime_context(
        toolsets=[],
        model="test",  # This model will be inherited and validated
        run_approval_policy=RunApprovalPolicy(mode="approve_all"),
    )
    run_ctx = RunContext(
        deps=ctx,
        model=None,
        usage=None,
        prompt="test",
    )

    # Should not raise - '*' matches inherited "test" model
    result = await worker.call({"input": "hi"}, ctx.config, ctx.frame, run_ctx)
    assert result is not None


@pytest.mark.anyio
async def test_worker_provider_wildcard_allows_matching_provider() -> None:
    """Worker with compatible_models=['anthropic:*'] allows anthropic models."""
    result = validate_model_compatibility(
        "anthropic:claude-sonnet-4",
        ["anthropic:*"],
        worker_name="anthropic-only",
    )
    assert result.valid is True


@pytest.mark.anyio
async def test_worker_provider_wildcard_rejects_other_provider() -> None:
    """Worker with compatible_models=['anthropic:*'] rejects non-anthropic models."""
    worker = Worker(
        name="anthropic-only",
        instructions="Anthropic models only.",
        compatible_models=["anthropic:*"],
    )
    ctx = build_runtime_context(
        toolsets=[],
        model="openai:gpt-4",  # Inherited model doesn't match pattern
        run_approval_policy=RunApprovalPolicy(mode="approve_all"),
    )
    run_ctx = RunContext(
        deps=ctx,
        model=None,
        usage=None,
        prompt="test",
    )

    with pytest.raises(ValueError, match="not compatible with worker"):
        await worker.call({"input": "hi"}, ctx.config, ctx.frame, run_ctx)


@pytest.mark.anyio
async def test_worker_model_family_wildcard_rejects_non_matching() -> None:
    """Worker with compatible_models=['anthropic:claude-*'] rejects non-claude models."""
    worker = Worker(
        name="claude-only",
        instructions="Claude models only.",
        compatible_models=["anthropic:claude-*"],
    )
    ctx = build_runtime_context(
        toolsets=[],
        model="anthropic:other-model",  # Doesn't match claude-*
        run_approval_policy=RunApprovalPolicy(mode="approve_all"),
    )
    run_ctx = RunContext(
        deps=ctx,
        model=None,
        usage=None,
        prompt="test",
    )

    with pytest.raises(ValueError, match="not compatible with worker"):
        await worker.call({"input": "hi"}, ctx.config, ctx.frame, run_ctx)


@pytest.mark.anyio
async def test_worker_multiple_patterns_rejects_non_matching() -> None:
    """Worker rejects model that doesn't match any pattern."""
    worker = Worker(
        name="multi-provider",
        instructions="Multiple providers allowed.",
        compatible_models=["anthropic:*", "openai:*"],
    )
    ctx = build_runtime_context(
        toolsets=[],
        model="google:gemini-pro",  # Doesn't match any pattern
        run_approval_policy=RunApprovalPolicy(mode="approve_all"),
    )
    run_ctx = RunContext(
        deps=ctx,
        model=None,
        usage=None,
        prompt="test",
    )

    with pytest.raises(ValueError, match="not compatible with worker"):
        await worker.call({"input": "hi"}, ctx.config, ctx.frame, run_ctx)


# --- Model object tests (TestModel) with compatible_models ---
# These tests verify that Model objects (not strings) work correctly with
# compatible_models by extracting model_name for validation.
@pytest.mark.anyio
async def test_model_object_validated_against_compatible_models() -> None:
    """Model object's full model string is validated against compatible_models patterns."""
    worker = Worker(
        name="test-only",
        instructions="Test model only.",
        model=TestModel(custom_output_text="Hello!"),  # produces "test:test"
        compatible_models=["test:test"],  # Should match TestModel's full string
    )
    ctx = build_runtime_context(
        toolsets=[],
        model="test",
        run_approval_policy=RunApprovalPolicy(mode="approve_all"),
    )
    run_ctx = RunContext(
        deps=ctx,
        model=None,
        usage=None,
        prompt="test",
    )

    # Should not raise - TestModel.model_name = "test" matches pattern
    result = await worker.call({"input": "hi"}, ctx.config, ctx.frame, run_ctx)
    assert result is not None


@pytest.mark.anyio
async def test_model_object_rejected_by_incompatible_pattern() -> None:
    """Model object is rejected when full model string doesn't match compatible_models."""
    worker = Worker(
        name="anthropic-only",
        instructions="Anthropic models only.",
        model=TestModel(),  # produces "test:test", not "anthropic:*"
        compatible_models=["anthropic:*"],
    )
    ctx = build_runtime_context(
        toolsets=[],
        model="test",
        run_approval_policy=RunApprovalPolicy(mode="approve_all"),
    )
    run_ctx = RunContext(
        deps=ctx,
        model=None,
        usage=None,
        prompt="test",
    )

    # Should raise - TestModel.model_name = "test" doesn't match "anthropic:*"
    with pytest.raises(ValueError, match="not compatible with worker"):
        await worker.call({"input": "hi"}, ctx.config, ctx.frame, run_ctx)


@pytest.mark.anyio
async def test_model_object_with_provider_wildcard() -> None:
    """Model object passes validation when compatible_models has provider wildcard."""
    worker = Worker(
        name="test-provider",
        instructions="Test provider models allowed.",
        model=TestModel(custom_output_text="OK"),  # produces "test:test"
        compatible_models=["test:*"],  # Provider wildcard matches "test:test"
    )
    ctx = build_runtime_context(
        toolsets=[],
        model="test",
        run_approval_policy=RunApprovalPolicy(mode="approve_all"),
    )
    run_ctx = RunContext(
        deps=ctx,
        model=None,
        usage=None,
        prompt="test",
    )

    # Should not raise - 'test:*' matches "test:test"
    result = await worker.call({"input": "hi"}, ctx.config, ctx.frame, run_ctx)
    assert result is not None


@pytest.mark.anyio
async def test_model_object_with_global_wildcard() -> None:
    """Model object passes validation when compatible_models has global wildcard."""
    worker = Worker(
        name="any-model",
        instructions="Any model allowed.",
        model=TestModel(custom_output_text="OK"),  # produces "test:test"
        compatible_models=["*"],  # Global wildcard accepts any model
    )
    ctx = build_runtime_context(
        toolsets=[],
        model="test",
        run_approval_policy=RunApprovalPolicy(mode="approve_all"),
    )
    run_ctx = RunContext(
        deps=ctx,
        model=None,
        usage=None,
        prompt="test",
    )

    # Should not raise - '*' matches any model_name including "test"
    result = await worker.call({"input": "hi"}, ctx.config, ctx.frame, run_ctx)
    assert result is not None
