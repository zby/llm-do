"""Runtime-level OAuth behavior tests for agent execution."""
from __future__ import annotations

import pytest
from pydantic_ai.models.test import TestModel

from llm_do.oauth import OAuthModelOverrides
from llm_do.runtime import AgentSpec, FunctionEntry, Runtime, agent_runner


@pytest.mark.anyio
async def test_auth_auto_uses_oauth_override_model(monkeypatch) -> None:
    base_model = TestModel(custom_output_text="base-model")
    oauth_model = TestModel(custom_output_text="oauth-model")
    agent_spec = AgentSpec(
        name="oauth_agent",
        instructions="Respond with your configured output.",
        model=base_model,
        model_id="anthropic:claude-sonnet-4",
    )

    async def fake_resolve_oauth_overrides(model: str):
        assert model == "anthropic:claude-sonnet-4"
        return OAuthModelOverrides(model=oauth_model, model_settings=None)

    monkeypatch.setattr(
        agent_runner,
        "resolve_oauth_overrides",
        fake_resolve_oauth_overrides,
    )

    async def entry_main(input_data, runtime):
        return await runtime.call_agent(agent_spec, input_data)

    runtime = Runtime(auth_mode="oauth_auto")
    runtime.register_agents({agent_spec.name: agent_spec})
    result, _ctx = await runtime.run_entry(
        FunctionEntry(name="entry", fn=entry_main),
        {"input": "hello"},
    )
    assert result == "oauth-model"


@pytest.mark.anyio
async def test_auth_required_raises_when_oauth_credentials_missing(monkeypatch) -> None:
    agent_spec = AgentSpec(
        name="oauth_agent",
        instructions="Respond with your configured output.",
        model=TestModel(custom_output_text="base-model"),
        model_id="anthropic:claude-sonnet-4",
    )

    async def fake_resolve_oauth_overrides(_model: str):
        return None

    monkeypatch.setattr(
        agent_runner,
        "resolve_oauth_overrides",
        fake_resolve_oauth_overrides,
    )

    async def entry_main(input_data, runtime):
        return await runtime.call_agent(agent_spec, input_data)

    runtime = Runtime(auth_mode="oauth_required")
    runtime.register_agents({agent_spec.name: agent_spec})
    with pytest.raises(RuntimeError, match="no OAuth credentials found"):
        await runtime.run_entry(
            FunctionEntry(name="entry", fn=entry_main),
            {"input": "hello"},
        )
