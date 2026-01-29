from __future__ import annotations

import asyncio
from pydantic_ai import Agent
from pydantic_ai.models.openai import OpenAIChatModel

from llm_do.providers.openai_compatible import OpenAICompatibleProvider


# ---- Script entry point ----

MODEL = "smollm2:135m-instruct-q2_K"   # must match `ollama list` EXACTLY
BASE_URL = "http://127.0.0.1:11434/v1" # Ollama OpenAI-compatible API


async def main() -> None:
    provider = OpenAICompatibleProvider(
        base_url=BASE_URL,
        name="ollama",
    )

    model = OpenAIChatModel(
        MODEL,
        provider=provider,
    )

    agent = Agent(model)

    result = await agent.run("hello")
    print(result)


if __name__ == "__main__":
    asyncio.run(main())
