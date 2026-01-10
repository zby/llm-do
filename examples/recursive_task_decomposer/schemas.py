from pydantic import BaseModel, Field


class PlannerInput(BaseModel):
    """Input schema for recursive task planning."""

    task: str = Field(..., min_length=1, description="Goal to plan")
    context: str = Field("", description="Constraints, resources, or deadlines")
    remaining_depth: int = Field(0, ge=0, description="Remaining recursion depth")
