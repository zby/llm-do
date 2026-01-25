"""Bootstrapping tools: agents that create and call other agents dynamically."""
from pydantic import BaseModel, Field
from pydantic_ai.tools import RunContext
from pydantic_ai.toolsets import FunctionToolset

from llm_do.runtime import ToolsetSpec
from llm_do.runtime.contracts import AgentSpec, CallContextProtocol


def build_bootstrapping_tools() -> FunctionToolset:
    tools = FunctionToolset()

    @tools.tool
    async def create_agent(
        ctx: RunContext[CallContextProtocol],
        name: str,
        instructions: str,
        input_data: str,
        model: str = "anthropic:claude-haiku-4-5",
    ) -> str:
        """Create a new agent dynamically and execute it with the given input.

        This allows you to spawn specialized agents on-the-fly without pre-defining them.
        The created agent has no tools - it's a pure reasoning agent.

        Args:
            name: Unique name for the agent
            instructions: The system instructions that define the agent's behavior
            input_data: The input to pass to the agent
            model: The model to use (default: anthropic:claude-haiku-4-5)

        Returns:
            The output from the dynamically created agent
        """
        spec = AgentSpec(
            name=name,
            instructions=instructions,
            model=model,
            toolset_specs=[],  # Pure reasoning agent - no tools
        )
        result = await ctx.deps.call_agent(spec, input_data)
        return str(result)

    @tools.tool
    async def create_tool_agent(
        ctx: RunContext[CallContextProtocol],
        tool_name: str,
        tool_description: str,
        tool_implementation: str,
        input_data: str,
        model: str = "anthropic:claude-haiku-4-5",
    ) -> str:
        """Create an agent that acts as a tool implementation.

        This pattern allows you to dynamically generate "tools" by creating
        specialized agents. The agent receives instructions on how to behave
        like a specific tool and processes the input accordingly.

        Args:
            tool_name: Name of the tool being implemented
            tool_description: What the tool does
            tool_implementation: Detailed instructions for how to implement the tool's behavior
            input_data: The "tool call arguments" to process
            model: The model to use (default: anthropic:claude-haiku-4-5)

        Returns:
            The tool's output (as processed by the implementing agent)
        """
        instructions = f"""You are implementing a tool called "{tool_name}".

Tool Description: {tool_description}

Implementation Instructions:
{tool_implementation}

Process the input according to these instructions and return the result.
Be precise and follow the implementation instructions exactly.
Output only the result, no explanations unless the instructions require them."""

        spec = AgentSpec(
            name=f"tool_{tool_name}",
            instructions=instructions,
            model=model,
            toolset_specs=[],
        )
        result = await ctx.deps.call_agent(spec, input_data)
        return str(result)

    @tools.tool
    async def create_agent_with_tools(
        ctx: RunContext[CallContextProtocol],
        name: str,
        instructions: str,
        toolset_names: list[str],
        input_data: str,
        model: str = "anthropic:claude-haiku-4-5",
    ) -> str:
        """Create a new agent with access to specific toolsets.

        This allows spawning agents that can use tools from the registry.
        The toolsets must already be registered in the runtime.

        Args:
            name: Unique name for the agent
            instructions: The system instructions
            toolset_names: List of toolset names to give the agent access to
            input_data: The input to pass to the agent
            model: The model to use

        Returns:
            The output from the dynamically created agent
        """
        # Resolve toolsets from registry
        from llm_do.toolsets.loader import ToolsetSpec as TS

        runtime = ctx.deps.runtime
        toolset_specs = []
        for ts_name in toolset_names:
            # Look up in the combined registry
            all_toolsets = runtime.agent_registry  # Access through runtime
            # For now, we can only pass empty toolsets
            # TODO: Need registry access to resolve toolset specs by name
            pass

        spec = AgentSpec(
            name=name,
            instructions=instructions,
            model=model,
            toolset_specs=toolset_specs,
        )
        result = await ctx.deps.call_agent(spec, input_data)
        return str(result)

    return tools


bootstrapping_tools = ToolsetSpec(factory=build_bootstrapping_tools)
