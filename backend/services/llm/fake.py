from pydantic import BaseModel

from services.llm.base import LLMError, LLMProvider, ResponseT


class FakeLLMProvider(LLMProvider):
    """Returns canned responses so no test touches a real API.

    Deliberately not registered as a selectable production provider: a fake that can
    be chosen by accident would serve invented job data as if it were extracted, which
    is far worse than the honest 503 the real dependency raises until Phase 4.
    """

    name = "fake"
    available_models = ["fake-1"]

    def __init__(self, responses: list[BaseModel] | None = None) -> None:
        self._responses = list(responses or [])
        self.prompts: list[str] = []

    def generate_structured(
        self, prompt: str, response_model: type[ResponseT]
    ) -> ResponseT:
        self.prompts.append(prompt)
        if not self._responses:
            raise LLMError("FakeLLMProvider has no queued responses left")
        response = self._responses.pop(0)
        if not isinstance(response, response_model):
            raise LLMError(
                f"queued a {type(response).__name__}, but {response_model.__name__} "
                "was requested"
            )
        return response
