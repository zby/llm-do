from pydantic_ai.models.openai import OpenAIChatModel

from llm_do import register_model_factory
from llm_do.providers import OpenAICompatibleProvider


class LocalOllamaProvider(OpenAICompatibleProvider):
    def __init__(self) -> None:
        super().__init__(
            base_url="http://127.0.0.1:11434/v1",
            name="ollama-local",
        )


def build_ollama_model(model_name: str) -> OpenAIChatModel:
    return OpenAIChatModel(model_name, provider=LocalOllamaProvider())


register_model_factory("ollama-local", build_ollama_model)
