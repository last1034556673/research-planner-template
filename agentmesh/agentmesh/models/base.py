"""Abstract base class for model backends."""

from __future__ import annotations

from abc import ABC, abstractmethod


class ModelBackend(ABC):
    """Interface every model backend must implement.

    The contract is intentionally tiny: take a system prompt and a
    conversation, return the assistant's response as a string.
    """

    @abstractmethod
    async def generate(
        self,
        system: str,
        messages: list[dict[str, str]],
    ) -> str:
        """Generate a response.

        Args:
            system: System prompt for the model.
            messages: Conversation history as [{"role": "user"|"assistant", "content": "..."}].

        Returns:
            The assistant's response text.
        """
        ...
