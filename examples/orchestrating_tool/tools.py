"""Orchestrating tool example.

This demonstrates a TOOL that orchestrates multiple AGENTS internally.
The outer LLM just calls `deep_research(question)` - it doesn't need to know
that this tool internally:
1. Calls query_expander agent to generate search queries
2. Calls searcher agent for each query (in parallel)
3. Calls synthesizer agent to combine all findings

This pattern is useful when:
- You want to encapsulate complex multi-agent workflows
- The orchestration logic is deterministic (not LLM-decided)
- You want reusability across different entry agents
"""

import asyncio
import json

from pydantic_ai.tools import RunContext
from pydantic_ai.toolsets import FunctionToolset

from llm_do.runtime import CallContext
from llm_do.toolsets.approval import set_toolset_approval_config


def build_research_tools(_ctx: RunContext[CallContext]):
    """Build the research toolset with an orchestrating tool."""
    tools = FunctionToolset()

    @tools.tool
    async def deep_research(
        ctx: RunContext[CallContext],
        question: str,
    ) -> str:
        """Perform deep research on a question using multiple specialized agents.

        This tool orchestrates a multi-agent pipeline:
        1. Expands the question into multiple search queries
        2. Searches for each query in parallel
        3. Synthesizes all findings into a comprehensive answer

        Args:
            question: The research question to investigate

        Returns:
            A comprehensive answer synthesized from multiple sources
        """
        runtime = ctx.deps

        # Step 1: Expand the question into multiple queries
        queries_json = await runtime.call_agent(
            "query_expander",
            {"input": question},
        )

        # Parse the queries (agent returns JSON array)
        try:
            queries = json.loads(queries_json)
            if not isinstance(queries, list):
                queries = [question]  # Fallback
        except json.JSONDecodeError:
            queries = [question]  # Fallback to original question

        # Step 2: Search for each query in parallel
        search_tasks = [
            runtime.call_agent(
                "searcher",
                {"input": f"Search for: {query}"},
            )
            for query in queries
        ]
        findings = await asyncio.gather(*search_tasks)

        # Step 3: Synthesize all findings
        synthesis_input = {
            "input": f"""Original question: {question}

Research findings from {len(queries)} queries:

"""
            + "\n\n".join(
                f"Query: {q}\nFindings: {f}" for q, f in zip(queries, findings)
            )
        }

        answer = await runtime.call_agent("synthesizer", synthesis_input)
        return answer

    set_toolset_approval_config(
        tools,
        {"deep_research": {"pre_approved": True}},
    )

    return tools


TOOLSETS = {"research_tools": build_research_tools}
