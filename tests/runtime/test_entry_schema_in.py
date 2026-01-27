import pytest

from llm_do.runtime import AgentArgs, FunctionEntry, PromptContent, Runtime


class CustomInput(AgentArgs):
    input: str
    tag: str

    def prompt_messages(self) -> list[PromptContent]:
        return [f"{self.input}:{self.tag}"]


@pytest.mark.anyio
async def test_entry_schema_in_normalizes_input() -> None:
    async def main(args: CustomInput, _runtime) -> str:
        return args.tag

    entry = FunctionEntry(name="echo", main=main, schema_in=CustomInput)

    runtime = Runtime()
    result, ctx = await runtime.run_entry(
        entry,
        {"input": "hi", "tag": "t1"},
    )

    assert result == "t1"
    assert ctx.frame.prompt == "hi:t1"
