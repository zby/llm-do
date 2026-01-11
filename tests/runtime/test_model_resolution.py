from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

import pytest
from pydantic import BaseModel, TypeAdapter
from pydantic_ai.models.test import TestModel
from pydantic_ai.tools import RunContext, ToolDefinition
from pydantic_ai.toolsets import AbstractToolset, ToolsetTool

from llm_do.models import ModelConfigError, validate_model_compatibility
from llm_do.runtime import WorkerInput, WorkerRuntime
from llm_do.runtime.approval import RunApprovalPolicy
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


@pytest.mark.anyio
async def test_child_context_uses_parent_model() -> None:
    """Child context inherits model from parent when not overridden."""
    toolset = CaptureToolset()
    ctx = build_runtime_context(
        toolsets=[toolset],
        model="parent-model",
    )

    # Spawn child without model override - should inherit parent's model
    child = ctx.spawn_child(active_toolsets=[toolset])
    assert child.model == "parent-model"

    # Tool call should see the inherited model
    await child.call("capture", {"value": 1})
    assert toolset.seen_model == "parent-model"


@pytest.mark.anyio
async def test_child_context_overrides_parent_model() -> None:
    """Child context can override parent's model."""
    toolset = CaptureToolset()
    ctx = build_runtime_context(
        toolsets=[toolset],
        model="parent-model",
    )

    # Spawn child with model override
    child = ctx.spawn_child(active_toolsets=[toolset], model="child-model")
    assert child.model == "child-model"

    # Tool call should see the overridden model
    await child.call("capture", {"value": 1})
    assert toolset.seen_model == "child-model"


# --- compatible_models tests ---
@pytest.mark.anyio
async def test_worker_compatible_models_allows_matching_model() -> None:
    """Worker runs successfully when inherited model is in compatible_models."""
    worker = Worker(
        name="strict",
        instructions="Be strict.",
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
    result = await worker.call(WorkerInput(input="hi"), run_ctx)
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
        await worker.call(WorkerInput(input="hi"), run_ctx)


@pytest.mark.anyio
async def test_worker_model_and_compatible_models_raises() -> None:
    """Worker with model and compatible_models set is invalid."""
    worker = Worker(
        name="strict",
        instructions="Be strict.",
        model="test",
        compatible_models=["test"],
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

    with pytest.raises(ModelConfigError, match="cannot have both"):
        await worker.call(WorkerInput(input="hi"), run_ctx)


@pytest.mark.anyio
async def test_worker_no_compatible_models_allows_any() -> None:
    """Worker allows any model when compatible_models is None."""
    worker = Worker(
        name="flexible",
        instructions="Be flexible.",
        compatible_models=None,  # No restriction
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

    # Should not raise
    result = await worker.call(WorkerInput(input="hi"), run_ctx)
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
    result = await worker.call(WorkerInput(input="hi"), run_ctx)
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
    result = await worker.call(WorkerInput(input="hi"), run_ctx)
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
        await worker.call(WorkerInput(input="hi"), run_ctx)


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
        await worker.call(WorkerInput(input="hi"), run_ctx)


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
        await worker.call(WorkerInput(input="hi"), run_ctx)


# --- Model object tests (TestModel) with compatible_models ---
# These tests verify that Model objects (not strings) work correctly with
# compatible_models by extracting model_name for validation.
@pytest.mark.anyio
async def test_model_object_validated_against_compatible_models() -> None:
    """Model object's full model string is validated against compatible_models patterns."""
    worker = Worker(
        name="test-only",
        instructions="Test model only.",
        compatible_models=["test:test"],  # Should match TestModel's full string
    )
    ctx = build_runtime_context(
        toolsets=[],
        model=TestModel(custom_output_text="Hello!"),  # produces "test:test"
        run_approval_policy=RunApprovalPolicy(mode="approve_all"),
    )
    run_ctx = RunContext(
        deps=ctx,
        model=None,
        usage=None,
        prompt="test",
    )

    # Should not raise - TestModel.model_name = "test" matches pattern
    result = await worker.call(WorkerInput(input="hi"), run_ctx)
    assert result is not None


@pytest.mark.anyio
async def test_model_object_rejected_by_incompatible_pattern() -> None:
    """Model object is rejected when full model string doesn't match compatible_models."""
    worker = Worker(
        name="anthropic-only",
        instructions="Anthropic models only.",
        compatible_models=["anthropic:*"],
    )
    ctx = build_runtime_context(
        toolsets=[],
        model=TestModel(),  # produces "test:test", not "anthropic:*"
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
        await worker.call(WorkerInput(input="hi"), run_ctx)


@pytest.mark.anyio
async def test_model_object_with_provider_wildcard() -> None:
    """Model object passes validation when compatible_models has provider wildcard."""
    worker = Worker(
        name="test-provider",
        instructions="Test provider models allowed.",
        compatible_models=["test:*"],  # Provider wildcard matches "test:test"
    )
    ctx = build_runtime_context(
        toolsets=[],
        model=TestModel(custom_output_text="OK"),  # produces "test:test"
        run_approval_policy=RunApprovalPolicy(mode="approve_all"),
    )
    run_ctx = RunContext(
        deps=ctx,
        model=None,
        usage=None,
        prompt="test",
    )

    # Should not raise - 'test:*' matches "test:test"
    result = await worker.call(WorkerInput(input="hi"), run_ctx)
    assert result is not None


@pytest.mark.anyio
async def test_model_object_with_global_wildcard() -> None:
    """Model object passes validation when compatible_models has global wildcard."""
    worker = Worker(
        name="any-model",
        instructions="Any model allowed.",
        compatible_models=["*"],  # Global wildcard accepts any model
    )
    ctx = build_runtime_context(
        toolsets=[],
        model=TestModel(custom_output_text="OK"),  # produces "test:test"
        run_approval_policy=RunApprovalPolicy(mode="approve_all"),
    )
    run_ctx = RunContext(
        deps=ctx,
        model=None,
        usage=None,
        prompt="test",
    )

    # Should not raise - '*' matches any model_name including "test"
    result = await worker.call(WorkerInput(input="hi"), run_ctx)
    assert result is not None
