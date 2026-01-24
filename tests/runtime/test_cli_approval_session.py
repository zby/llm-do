from __future__ import annotations

from typing import Any, cast

import pytest
from pydantic import TypeAdapter
from pydantic_ai.models.test import TestModel
from pydantic_ai.tools import RunContext, ToolDefinition
from pydantic_ai.toolsets import AbstractToolset, ToolsetTool
from pydantic_ai_blocking_approval import (
    ApprovalDecision,
    ApprovalRequest,
    ApprovalResult,
)
from pydantic_core import SchemaValidator

from llm_do.runtime import AgentSpec, EntrySpec, RunApprovalPolicy, Runtime, ToolsetSpec


class _ProbeToolset(AbstractToolset[Any]):
    @property
    def id(self) -> str | None:
        return "probe"

    def needs_approval(
        self,
        name: str,
        tool_args: dict[str, Any],
        ctx: Any,
        config: Any = None,
    ) -> ApprovalResult:
        return ApprovalResult.needs_approval()

    def get_approval_description(
        self,
        name: str,
        tool_args: dict[str, Any],
        ctx: Any,
    ) -> str:
        return "probe tool"

    async def get_tools(self, run_ctx: RunContext[Any]) -> dict[str, ToolsetTool[Any]]:
        schema = {"type": "object", "additionalProperties": True}
        tool_def = ToolDefinition(
            name="probe",
            description="probe tool",
            parameters_json_schema=schema,
        )
        return {
            "probe": ToolsetTool(
                toolset=self,
                tool_def=tool_def,
                max_retries=0,
                args_validator=cast(SchemaValidator, TypeAdapter(dict[str, Any]).validator),
            )
        }

    async def call_tool(
        self,
        name: str,
        tool_args: dict[str, Any],
        run_ctx: RunContext[Any],
        tool: ToolsetTool[Any],
    ) -> Any:
        return "ok"


@pytest.mark.anyio
async def test_tui_session_approval_cache_persists_across_runs() -> None:
    calls: list[ApprovalRequest] = []

    def approval_callback(request: ApprovalRequest) -> ApprovalDecision:
        calls.append(request)
        return ApprovalDecision(approved=True, remember="session")

    probe_spec = ToolsetSpec(factory=lambda _ctx: _ProbeToolset())
    agent_spec = AgentSpec(
        name="main",
        instructions="Test agent",
        model=TestModel(call_tools=["probe"], custom_output_text="done"),
        toolset_specs=[probe_spec],
    )

    async def main(input_data, runtime) -> str:
        return await runtime.call_agent(agent_spec, input_data)

    entry_spec = EntrySpec(name="entry", main=main)

    runtime = Runtime(
        run_approval_policy=RunApprovalPolicy(
            mode="prompt",
            approval_callback=approval_callback,
        )
    )
    runtime.register_agents({agent_spec.name: agent_spec})
    await runtime.run_entry(entry_spec, {"input": "First turn"})
    await runtime.run_entry(entry_spec, {"input": "Second turn"})

    assert len(calls) == 1
