"""Anthropic (Claude) model backend."""

from __future__ import annotations

import os
from agentmesh.models.base import ModelBackend


class AnthropicBackend(ModelBackend):
    """Backend for Anthropic Claude models.

    Requires the `anthropic` package and ANTHROPIC_API_KEY env var.

    Args:
        model: Model ID, e.g. "claude-sonnet-4-20250514", "claude-opus-4-20250514".
        api_key: API key. Defaults to ANTHROPIC_API_KEY env var.
        max_tokens: Max tokens for each response.
        temperature: Sampling temperature.
    """

    def __init__(
        self,
        model: str = "claude-sonnet-4-20250514",
        api_key: str | None = None,
        max_tokens: int = 4096,
        temperature: float = 0.7,
    ) -> None:
        self.model = model
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY", "")
        self.max_tokens = max_tokens
        self.temperature = temperature
        self._client = None

    def _get_client(self):
        if self._client is None:
            try:
                import anthropic
            except ImportError:
                raise ImportError(
                    "Install the anthropic package: pip install anthropic"
                )
            self._client = anthropic.AsyncAnthropic(api_key=self.api_key)
        return self._client

    async def generate(
        self,
        system: str,
        messages: list[dict[str, str]],
    ) -> str:
        client = self._get_client()
        response = await client.messages.create(
            model=self.model,
            max_tokens=self.max_tokens,
            temperature=self.temperature,
            system=system,
            messages=messages,
        )
        return response.content[0].text
