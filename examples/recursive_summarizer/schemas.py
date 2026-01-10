from pydantic import BaseModel, Field


class SummarizerInput(BaseModel):
    """Input schema for recursive summarizer ranges."""

    path: str = Field(..., description="Path to the file (relative to worker directory)")
    start: int = Field(..., ge=0, description="Inclusive start offset (characters)")
    end: int = Field(..., gt=0, description="Exclusive end offset (characters)")
