from pydantic import Field

from llm_do.runtime import PromptContent, WorkerArgs


class SummarizerInput(WorkerArgs):
    """Input schema for recursive summarizer ranges."""

    path: str = Field(..., description="Path to the file (relative to worker directory)")
    start: int = Field(..., ge=0, description="Inclusive start offset (characters)")
    end: int = Field(..., gt=0, description="Exclusive end offset (characters)")

    def prompt_messages(self) -> list[PromptContent]:
        return [
            "Summarize the file segment below.\n"
            f"Path: {self.path}\n"
            f"Start: {self.start}\n"
            f"End: {self.end}"
        ]
