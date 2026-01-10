from pydantic import Field

from llm_do.runtime import PromptSpec, WorkerArgs


class PlannerInput(WorkerArgs):
    """Input schema for recursive task planning."""

    task: str = Field(..., min_length=1, description="Goal to plan")
    context: str = Field("", description="Constraints, resources, or deadlines")
    remaining_depth: int = Field(0, ge=0, description="Remaining recursion depth")

    def prompt_spec(self) -> PromptSpec:
        return PromptSpec(
            text=(
                "Plan the task below.\n"
                f"Task: {self.task}\n"
                f"Context: {self.context}\n"
                f"Remaining depth: {self.remaining_depth}"
            )
        )
