"""Example of worker-local tools registered at runtime."""
from __future__ import annotations

from pydantic_ai.tools import RunContext

from llm_do.pydanticai import WorkerContext


def register_tools(agent, ctx: WorkerContext, default_tone: str = "concise") -> None:
    """Register small utility tools for the local_tools worker.

    Tools live next to the worker YAML so they can evolve with the prompt.
    The loader calls this function with the active ``WorkerContext`` so tools
    can reuse sandboxes, approval policies, or other shared state.
    """

    @agent.tool(
        name="local_summarize",
        description="Summarize text into a short note with an optional tone override",
    )
    def local_summarize(
        run_ctx: RunContext[WorkerContext],
        text: str,
        tone: str | None = None,
    ) -> str:
        """Summarize inline text without leaving the worker sandbox."""

        chosen_tone = tone or default_tone
        note = text.strip()
        if len(note) > 280:
            note = f"{note[:260].rstrip()}…"
        return f"[{chosen_tone} summary] {note}"

    @agent.tool(
        name="local_todo",
        description="Append a TODO line to the scratch sandbox for later follow-up",
    )
    def local_todo(
        run_ctx: RunContext[WorkerContext],
        title: str,
        sandbox: str = "scratch",
    ) -> str:
        target = run_ctx.deps.sandbox_manager._sandbox_for(sandbox)
        todo_path = target.path / "todo.txt"
        todo_path.parent.mkdir(parents=True, exist_ok=True)

        existing = todo_path.read_text(encoding="utf-8") if todo_path.exists() else ""
        todo_path.write_text(f"{existing}- {title}\n", encoding="utf-8")
        return f"added todo to {sandbox}:{todo_path.name}"
