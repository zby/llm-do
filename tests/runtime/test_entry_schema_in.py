import pytest

from llm_do.runtime import PromptSpec, Runtime, WorkerArgs, entry


class CustomInput(WorkerArgs):
    input: str
    tag: str

    def prompt_spec(self) -> PromptSpec:
        return PromptSpec(text=f"{self.input}:{self.tag}")


@pytest.mark.anyio
async def test_entry_schema_in_normalizes_input() -> None:
    @entry(schema_in=CustomInput)
    async def echo(args: WorkerArgs, runtime_ctx) -> str:
        assert isinstance(args, CustomInput)
        return args.tag

    runtime = Runtime()
    result, ctx = await runtime.run_entry(
        echo,
        {"input": "hi", "tag": "t1"},
    )

    assert result == "t1"
    assert ctx.frame.prompt == "hi:t1"
