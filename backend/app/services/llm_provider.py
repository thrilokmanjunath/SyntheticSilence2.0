from abc import ABC, abstractmethod
from typing import Any, Type, TypeVar

T = TypeVar("T")


class LLMProviderError(RuntimeError):
    """The LLM call failed or returned something unusable. Never contains credentials."""


class LLMProvider(ABC):
    @abstractmethod
    async def generate_structured_output(self, prompt: str, schema_class: Type[T]) -> T:
        """
        Generates structured output matching the provided Pydantic schema class.
        This abstracts away the specific provider (e.g., OpenRouter, Gemini).
        """
        pass
