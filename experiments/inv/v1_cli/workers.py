"""v1_cli: Python-defined workers, run via llm-do CLI.

Run with:
    cd experiments/inv/v1_cli
    llm-do workers.py --entry main --approve-all "Go"
"""

from pathlib import Path

from llm_do.runtime import ToolsetSpec
from llm_do.runtime.worker import Worker
from llm_do.toolsets.filesystem import FileSystemToolset

HERE = Path(__file__).parent


def load_instructions(name: str) -> str:
    """Load instructions from the instructions/ directory."""
    return (HERE / "instructions" / f"{name}.md").read_text()


# Instantiate builtin toolsets
# NOTE: base_path must be configured separately on FileSystemToolset and on
# workers that receive attachments. This duplication is not ideal - a cleaner
# solution would unify path resolution at the runtime level.
filesystem_spec = ToolsetSpec(
    factory=lambda _ctx: FileSystemToolset(config={"base_path": str(HERE)})
)

# Define workers - order matters for references
pitch_evaluator = Worker(
    name="pitch_evaluator",
    model="anthropic:claude-haiku-4-5",
    instructions=load_instructions("pitch_evaluator"),
    base_path=HERE,  # For resolving attachment paths
)

main = Worker(
    name="main",
    model="anthropic:claude-haiku-4-5",
    instructions=load_instructions("main"),
    toolset_specs=[filesystem_spec, pitch_evaluator.as_toolset_spec()],
)
