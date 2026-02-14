"""Init module for live tests: registers a provider without streaming support."""

from pydantic_ai.models import Model, infer_model

from llm_do import register_model_factory


class NonStreamingModel(Model):
    def __init__(self, inner: Model) -> None:
        super().__init__()
        self._inner = inner

    @property
    def model_name(self) -> str:
        return self._inner.model_name

    @property
    def system(self) -> str:
        return self._inner.system

    async def request(self, messages, model_settings, model_request_parameters):
        return await self._inner.request(messages, model_settings, model_request_parameters)


def build_nostream(model_name: str) -> Model:
    return NonStreamingModel(infer_model(model_name))


register_model_factory("nostream_live", build_nostream, replace=True)
