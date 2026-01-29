from pydantic import Field
from pydantic_ai import BinaryContent

from llm_do.runtime import AgentArgs, PromptContent


class PlannerInput(AgentArgs):
    """Input schema for recursive task planning."""

    task: str = Field(..., min_length=1, description="Goal to plan")
    context: str = Field("", description="Constraints, resources, or deadlines")
    remaining_depth: int = Field(0, ge=0, description="Remaining recursion depth")

    def prompt_messages(self) -> list[PromptContent]:
        return [
            "Plan the task below.\n"
            f"Task: {self.task}\n"
            f"Context: {self.context}\n"
            f"Remaining depth: {self.remaining_depth}"
        ]

    def input_parts(self, model_name: str | None = None) -> list[object]:
        parts: list[object] = [
            "Input fields are attached as plain text files. Read them exactly.",
        ]
        parts.extend(_as_text_file_parts("task.txt", self.task))
        parts.extend(_as_text_file_parts("context.txt", self.context))
        parts.extend(_as_text_file_parts("remaining_depth.txt", str(self.remaining_depth)))
        return parts


def _as_text_file(name: str, text: str) -> BinaryContent:
    return BinaryContent(
        data=text.encode("utf-8"),
        media_type="text/plain",
        identifier=name,
    )


def _as_text_file_parts(name: str, text: str) -> list[object]:
    return [f"{name}:", _as_text_file(name, text)]
