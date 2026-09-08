from abc import ABC, abstractmethod
from typing import TypeVar

from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


class LLMProviderError(Exception):
    """Raised when the LLM call fails outright or never produces valid structured output."""


class LLMProvider(ABC):
    @abstractmethod
    async def generate_structured(
        self, system_prompt: str, user_prompt: str, response_model: type[T]
    ) -> T:
        """Call the model and return output validated against response_model. Never
        returns free text — callers must not need to parse anything themselves."""
