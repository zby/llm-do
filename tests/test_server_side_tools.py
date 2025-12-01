"""Tests for server-side tools (provider-executed tools like web search)."""
import pytest
from pydantic_ai.builtin_tools import (
    CodeExecutionTool,
    ImageGenerationTool,
    UrlContextTool,
    WebSearchTool,
)

from llm_do import ServerSideToolConfig, WorkerDefinition
from llm_do.execution import build_server_side_tools


class TestBuildServerSideTools:
    """Tests for build_server_side_tools function."""

    def test_web_search_basic(self):
        """Test basic web_search tool conversion."""
        configs = [ServerSideToolConfig(tool_type="web_search")]
        tools = build_server_side_tools(configs)

        assert len(tools) == 1
        assert isinstance(tools[0], WebSearchTool)

    def test_web_search_with_options(self):
        """Test web_search tool with all options."""
        configs = [
            ServerSideToolConfig(
                tool_type="web_search",
                max_uses=5,
                blocked_domains=["spam.com", "ads.com"],
            )
        ]
        tools = build_server_side_tools(configs)

        assert len(tools) == 1
        tool = tools[0]
        assert isinstance(tool, WebSearchTool)
        assert tool.max_uses == 5
        assert tool.blocked_domains == ["spam.com", "ads.com"]

    def test_web_search_allowed_domains(self):
        """Test web_search with allowed_domains (mutually exclusive with blocked)."""
        configs = [
            ServerSideToolConfig(
                tool_type="web_search",
                allowed_domains=["trusted.com"],
            )
        ]
        tools = build_server_side_tools(configs)

        tool = tools[0]
        assert tool.allowed_domains == ["trusted.com"]
        assert tool.blocked_domains is None

    def test_url_context_basic(self):
        """Test url_context tool conversion."""
        configs = [ServerSideToolConfig(tool_type="url_context")]
        tools = build_server_side_tools(configs)

        assert len(tools) == 1
        assert isinstance(tools[0], UrlContextTool)

    def test_code_execution(self):
        """Test code_execution tool conversion."""
        configs = [ServerSideToolConfig(tool_type="code_execution")]
        tools = build_server_side_tools(configs)

        assert len(tools) == 1
        assert isinstance(tools[0], CodeExecutionTool)

    def test_image_generation(self):
        """Test image_generation tool conversion."""
        configs = [ServerSideToolConfig(tool_type="image_generation")]
        tools = build_server_side_tools(configs)

        assert len(tools) == 1
        assert isinstance(tools[0], ImageGenerationTool)

    def test_multiple_tools(self):
        """Test multiple server-side tools at once."""
        configs = [
            ServerSideToolConfig(tool_type="web_search", max_uses=3),
            ServerSideToolConfig(tool_type="code_execution"),
            ServerSideToolConfig(tool_type="url_context"),
        ]
        tools = build_server_side_tools(configs)

        assert len(tools) == 3
        assert isinstance(tools[0], WebSearchTool)
        assert isinstance(tools[1], CodeExecutionTool)
        assert isinstance(tools[2], UrlContextTool)

    def test_empty_config(self):
        """Test empty config list returns empty tools list."""
        tools = build_server_side_tools([])
        assert tools == []


class TestWorkerDefinitionServerSideTools:
    """Tests for server_side_tools in WorkerDefinition."""

    def test_default_empty(self):
        """Test that server_side_tools defaults to empty list."""
        definition = WorkerDefinition(name="test", instructions="do stuff")
        assert definition.server_side_tools == []

    def test_with_server_side_tools(self):
        """Test WorkerDefinition with server_side_tools configured."""
        definition = WorkerDefinition(
            name="researcher",
            instructions="Research the topic",
            server_side_tools=[
                ServerSideToolConfig(tool_type="web_search", max_uses=5),
                ServerSideToolConfig(tool_type="url_context"),
            ],
        )

        assert len(definition.server_side_tools) == 2
        assert definition.server_side_tools[0].tool_type == "web_search"
        assert definition.server_side_tools[0].max_uses == 5
        assert definition.server_side_tools[1].tool_type == "url_context"

    def test_serialization_round_trip(self):
        """Test that server_side_tools survive serialization."""
        definition = WorkerDefinition(
            name="test",
            instructions="test",
            server_side_tools=[
                ServerSideToolConfig(
                    tool_type="web_search",
                    blocked_domains=["bad.com"],
                ),
            ],
        )

        # Serialize and deserialize
        data = definition.model_dump()
        restored = WorkerDefinition.model_validate(data)

        assert len(restored.server_side_tools) == 1
        assert restored.server_side_tools[0].tool_type == "web_search"
        assert restored.server_side_tools[0].blocked_domains == ["bad.com"]
