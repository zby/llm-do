from pydantic import Field

from llm_do.runtime import AgentArgs, PromptContent


class DatasetInput(AgentArgs):
    """Input schema for the analyze_dataset agent."""

    path: str = Field(..., description="Path to the CSV file")

    def prompt_messages(self) -> list[PromptContent]:
        return [f"Analyze the dataset at: {self.path}"]
