"""v1_cli: Python-defined workers, run via llm-do CLI.

Run with:
    cd experiments/inv/v1_cli
    llm-do workers.py --entry main --approve-all "Go"
"""

from pathlib import Path

from llm_do.ctx_runtime.invocables import WorkerInvocable
from llm_do.filesystem_toolset import FileSystemToolset

HERE = Path(__file__).parent


def load_instructions(name: str) -> str:
    """Load instructions from the instructions/ directory."""
    return (HERE / "instructions" / f"{name}.md").read_text()


# Instantiate builtin toolsets
filesystem = FileSystemToolset(config={})

# Define workers - order matters for references
pitch_evaluator = WorkerInvocable(
    name="pitch_evaluator",
    model="anthropic:claude-haiku-4-5",
    instructions=load_instructions("pitch_evaluator"),
    toolsets=[],
)

main = WorkerInvocable(
    name="main",
    model="anthropic:claude-haiku-4-5",
    instructions=load_instructions("main"),
    toolsets=[filesystem, pitch_evaluator],
)
