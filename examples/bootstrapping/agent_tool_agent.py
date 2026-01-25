"""True Agent -> Tool -> Agent pattern implementation.

This demonstrates the full bootstrapping capability where:
1. An outer agent has a tool
2. The tool dynamically creates and calls an inner agent
3. The inner agent processes data and returns to the tool
4. The tool processes the result and returns to the outer agent

This enables meta-programming: agents that generate other agents as tools.
"""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel
from pydantic_ai.tools import RunContext
from pydantic_ai.toolsets import FunctionToolset

from llm_do.runtime import ToolsetSpec
from llm_do.runtime.contracts import AgentSpec, CallContextProtocol


class AgentFactory:
    """Factory for building agents from specifications.

    This encapsulates the pattern of dynamically creating AgentSpecs
    and provides utilities for common agent patterns.
    """

    @staticmethod
    def create_specialist(
        name: str,
        specialty: str,
        task_description: str,
        output_format: str = "plain text",
    ) -> AgentSpec:
        """Create a specialist agent for a specific domain."""
        instructions = f"""You are a specialist in {specialty}.

Your task: {task_description}

Output format: {output_format}

Be precise, accurate, and focused. Output only the result."""

        return AgentSpec(
            name=name,
            description=f"Specialist agent for {specialty}",
            instructions=instructions,
            model="anthropic:claude-haiku-4-5",
            toolset_specs=[],
        )

    @staticmethod
    def create_transformer(
        name: str,
        input_description: str,
        output_description: str,
        transformation_rules: str,
    ) -> AgentSpec:
        """Create a data transformation agent."""
        instructions = f"""You are a data transformer.

Input: {input_description}
Output: {output_description}

Transformation rules:
{transformation_rules}

Apply the transformation rules to the input and output the result.
Do not include explanations unless the output format requires them."""

        return AgentSpec(
            name=name,
            description=f"Transform {input_description} to {output_description}",
            instructions=instructions,
            model="anthropic:claude-haiku-4-5",
            toolset_specs=[],
        )


def build_agent_tool_agent_tools() -> FunctionToolset:
    """Build tools that demonstrate the Agent -> Tool -> Agent pattern."""
    tools = FunctionToolset()

    @tools.tool
    async def analyze_with_specialist(
        ctx: RunContext[CallContextProtocol],
        domain: str,
        analysis_type: str,
        data: str,
    ) -> str:
        """Create a specialist agent and have it analyze data.

        This tool demonstrates Agent -> Tool -> Agent:
        - You (the outer agent) call this tool
        - This tool creates a specialist agent
        - The specialist analyzes the data
        - The result comes back through the tool to you

        Args:
            domain: The domain of expertise (e.g., "financial analysis", "code review")
            analysis_type: What kind of analysis to perform
            data: The data to analyze

        Returns:
            The specialist's analysis
        """
        specialist = AgentFactory.create_specialist(
            name=f"specialist_{domain.replace(' ', '_')}",
            specialty=domain,
            task_description=f"Perform {analysis_type} on the provided data",
            output_format="structured analysis with key findings",
        )

        result = await ctx.deps.call_agent(specialist, data)
        return f"[Specialist Analysis - {domain}]\n{result}"

    @tools.tool
    async def transform_data(
        ctx: RunContext[CallContextProtocol],
        input_format: str,
        output_format: str,
        rules: str,
        data: str,
    ) -> str:
        """Create a transformer agent to convert data.

        Args:
            input_format: Description of the input format
            output_format: Desired output format
            rules: Transformation rules to apply
            data: The data to transform

        Returns:
            The transformed data
        """
        transformer = AgentFactory.create_transformer(
            name="data_transformer",
            input_description=input_format,
            output_description=output_format,
            transformation_rules=rules,
        )

        result = await ctx.deps.call_agent(transformer, data)
        return str(result)

    @tools.tool
    async def chain_agents(
        ctx: RunContext[CallContextProtocol],
        agent_specs: str,
        data: str,
    ) -> str:
        """Chain multiple dynamically created agents together.

        Each agent processes the output of the previous one.

        Args:
            agent_specs: JSON-like description of agents to chain.
                Format: "name1:instructions1 | name2:instructions2 | ..."
                Each agent receives the output of the previous one.
            data: Initial input data

        Returns:
            Final output after all agents have processed
        """
        # Parse the simple spec format
        specs = []
        for part in agent_specs.split("|"):
            part = part.strip()
            if ":" in part:
                name, instructions = part.split(":", 1)
                specs.append((name.strip(), instructions.strip()))

        if not specs:
            return "Error: No valid agent specs provided"

        current_data = data
        chain_log = []

        for i, (name, instructions) in enumerate(specs):
            agent = AgentSpec(
                name=f"chain_{i}_{name}",
                instructions=instructions,
                model="anthropic:claude-haiku-4-5",
                toolset_specs=[],
            )
            result = await ctx.deps.call_agent(agent, current_data)
            current_data = str(result)
            chain_log.append(f"Step {i + 1} ({name}): processed")

        return f"Chain completed:\n" + "\n".join(chain_log) + f"\n\nFinal result:\n{current_data}"

    @tools.tool
    async def create_and_call_pipeline(
        ctx: RunContext[CallContextProtocol],
        task_description: str,
        data: str,
    ) -> str:
        """Meta-tool: Design and execute an agent pipeline for a task.

        This creates a planning agent that designs the pipeline,
        then executes each stage.

        Args:
            task_description: What needs to be accomplished
            data: The data to process

        Returns:
            The pipeline result
        """
        # Step 1: Create a planning agent to design the pipeline
        planner = AgentSpec(
            name="pipeline_planner",
            instructions="""You are a pipeline architect. Given a task description,
design a processing pipeline as a series of 2-3 simple steps.

Output format (exactly):
STEP1: [brief instruction for first agent]
STEP2: [brief instruction for second agent]
STEP3: [brief instruction for third agent, if needed]

Keep instructions concise and focused. Each step should do ONE thing.""",
            model="anthropic:claude-haiku-4-5",
            toolset_specs=[],
        )

        plan = await ctx.deps.call_agent(planner, task_description)
        plan_str = str(plan)

        # Step 2: Parse the plan and execute each step
        steps = []
        for line in plan_str.split("\n"):
            line = line.strip()
            if line.startswith("STEP"):
                if ":" in line:
                    _, instruction = line.split(":", 1)
                    steps.append(instruction.strip())

        if not steps:
            return f"Pipeline planning failed. Plan was:\n{plan_str}"

        # Step 3: Execute each step as a separate agent
        current_data = data
        execution_log = [f"Pipeline plan:\n{plan_str}\n", "Execution:"]

        for i, instruction in enumerate(steps):
            step_agent = AgentSpec(
                name=f"pipeline_step_{i + 1}",
                instructions=instruction,
                model="anthropic:claude-haiku-4-5",
                toolset_specs=[],
            )
            result = await ctx.deps.call_agent(step_agent, current_data)
            current_data = str(result)
            execution_log.append(f"  Step {i + 1} complete")

        execution_log.append(f"\nFinal output:\n{current_data}")
        return "\n".join(execution_log)

    return tools


agent_tool_agent = ToolsetSpec(factory=build_agent_tool_agent_tools)
