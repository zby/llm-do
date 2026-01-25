"""Meta-tools: Tools that generate tools which call agents.

This demonstrates the second bootstrapping pattern:
Agent -> generates Tool -> Tool calls Agent

The key insight is that a "tool" at runtime can be represented as an agent
with specific instructions. So generating a tool means generating an AgentSpec
that implements the tool's behavior, then wrapping it so it can be called.
"""
from typing import Any

from pydantic import BaseModel, Field
from pydantic_ai.tools import RunContext
from pydantic_ai.toolsets import AbstractToolset, FunctionToolset

from llm_do.runtime import ToolsetSpec
from llm_do.runtime.contracts import AgentSpec, CallContextProtocol
from llm_do.toolsets.agent import AgentToolset


class GeneratedToolRegistry:
    """Registry for dynamically generated tools within a session."""

    def __init__(self) -> None:
        self.tools: dict[str, AgentSpec] = {}

    def register(self, name: str, spec: AgentSpec) -> None:
        self.tools[name] = spec

    def get(self, name: str) -> AgentSpec | None:
        return self.tools.get(name)


def build_meta_tools() -> FunctionToolset:
    """Build tools for generating other tools that call agents."""
    tools = FunctionToolset()

    # Shared registry for generated tools
    registry = GeneratedToolRegistry()

    @tools.tool
    async def generate_tool(
        ctx: RunContext[CallContextProtocol],
        tool_name: str,
        description: str,
        input_schema_description: str,
        output_format: str,
        implementation_logic: str,
    ) -> str:
        """Generate a new tool by creating an agent that implements it.

        The generated tool can be called later using call_generated_tool.
        This is the "agent generates tool" pattern.

        Args:
            tool_name: Name for the new tool
            description: What the tool does
            input_schema_description: Description of expected input format
            output_format: How the output should be formatted
            implementation_logic: Step-by-step logic for the tool

        Returns:
            Confirmation that the tool was generated
        """
        instructions = f"""You are implementing a tool called "{tool_name}".

**Description:** {description}

**Expected Input:** {input_schema_description}

**Output Format:** {output_format}

**Implementation Logic:**
{implementation_logic}

Follow the implementation logic precisely. Output only the result in the specified format.
Do not include explanations or metadata unless required by the output format."""

        spec = AgentSpec(
            name=f"generated_{tool_name}",
            description=description,
            instructions=instructions,
            model="anthropic:claude-haiku-4-5",
            toolset_specs=[],
        )

        registry.register(tool_name, spec)
        return f"Tool '{tool_name}' generated successfully. Use call_generated_tool to invoke it."

    @tools.tool
    async def call_generated_tool(
        ctx: RunContext[CallContextProtocol],
        tool_name: str,
        input_data: str,
    ) -> str:
        """Call a previously generated tool.

        Args:
            tool_name: Name of the tool to call
            input_data: Input to pass to the tool

        Returns:
            The tool's output
        """
        spec = registry.get(tool_name)
        if spec is None:
            available = list(registry.tools.keys())
            return f"Error: Tool '{tool_name}' not found. Available: {available}"

        result = await ctx.deps.call_agent(spec, input_data)
        return str(result)

    @tools.tool
    async def list_generated_tools(
        ctx: RunContext[CallContextProtocol],
    ) -> str:
        """List all generated tools in this session."""
        if not registry.tools:
            return "No tools have been generated yet."

        lines = ["Generated tools:"]
        for name, spec in registry.tools.items():
            desc = spec.description or "No description"
            lines.append(f"  - {name}: {desc}")
        return "\n".join(lines)

    @tools.tool
    async def generate_tool_that_calls_agent(
        ctx: RunContext[CallContextProtocol],
        tool_name: str,
        description: str,
        sub_agent_instructions: str,
        preprocessing_instructions: str,
        postprocessing_instructions: str,
    ) -> str:
        """Generate a tool that internally calls a sub-agent.

        This is the full pattern: Agent -> Tool -> Agent
        The generated tool will:
        1. Preprocess input according to preprocessing_instructions
        2. Call a sub-agent with sub_agent_instructions
        3. Postprocess the sub-agent's output

        Args:
            tool_name: Name for the new tool
            description: What the tool does
            sub_agent_instructions: Instructions for the internal sub-agent
            preprocessing_instructions: How to prepare input for the sub-agent
            postprocessing_instructions: How to process sub-agent output

        Returns:
            Confirmation that the tool was generated
        """
        # This tool generates a compound structure:
        # When called, it creates TWO agents - one for pre/post processing
        # and one as the core sub-agent

        instructions = f"""You are a composite tool called "{tool_name}".

**Description:** {description}

**Your Workflow:**
1. PREPROCESS: {preprocessing_instructions}
2. Conceptually delegate to sub-agent (you simulate this by following the sub-agent instructions)
3. POSTPROCESS: {postprocessing_instructions}

**Sub-agent behavior to simulate:**
{sub_agent_instructions}

Execute this workflow and return the final postprocessed result.
Think step by step but only output the final result."""

        spec = AgentSpec(
            name=f"generated_{tool_name}",
            description=description,
            instructions=instructions,
            model="anthropic:claude-haiku-4-5",
            toolset_specs=[],
        )

        registry.register(tool_name, spec)
        return f"Composite tool '{tool_name}' generated. It simulates the Agent->Tool->Agent pattern."

    return tools


meta_tools = ToolsetSpec(factory=build_meta_tools)
