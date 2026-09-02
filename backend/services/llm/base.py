from abc import ABC, abstractmethod
from typing import TypeVar

from pydantic import BaseModel

ResponseT = TypeVar("ResponseT", bound=BaseModel)


class LLMProvider(ABC):
    """The interface every provider implements.

    Adding a provider means writing a class and registering it — no calling code
    changes. Phase 3 ships this ABC and a fake; Phase 4 adds the Anthropic
    implementation, prompts and guardrails on top of exactly this signature.
    """

    name: str
    available_models: list[str]

    @abstractmethod
    def generate_structured(
        self, prompt: str, response_model: type[ResponseT]
    ) -> ResponseT:
        """Return an instance of `response_model`, validated."""


class LLMError(RuntimeError):
    """A provider failed to produce a usable structured response."""
