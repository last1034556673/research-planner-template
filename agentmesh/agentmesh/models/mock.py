"""Mock backend for testing without API calls."""

from __future__ import annotations

from typing import Callable
from agentmesh.models.base import ModelBackend


class MockBackend(ModelBackend):
    """A mock model that returns scripted responses.

    Useful for testing, demos, and development without burning tokens.

    Args:
        responses: Either a list of responses (consumed in order) or a
                   callable that takes (system, messages) and returns a string.
    """

    def __init__(
        self,
        responses: list[str] | Callable | None = None,
    ) -> None:
        if callable(responses):
            self._fn = responses
            self._queue: list[str] = []
        else:
            self._fn = None
            self._queue = list(responses or ["(mock response)"])
        self.call_count = 0
        self.history: list[tuple[str, list[dict[str, str]]]] = []

    async def generate(
        self,
        system: str,
        messages: list[dict[str, str]],
    ) -> str:
        self.call_count += 1
        self.history.append((system, messages))

        if self._fn:
            return self._fn(system, messages)

        if self._queue:
            return self._queue.pop(0)
        return "(mock: no more responses)"
