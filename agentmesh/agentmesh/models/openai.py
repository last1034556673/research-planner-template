"""OpenAI model backend."""

from __future__ import annotations

import os
from agentmesh.models.base import ModelBackend


class OpenAIBackend(ModelBackend):
    """Backend for OpenAI models (GPT-4o, o1, o3, etc.).

    Requires the `openai` package and OPENAI_API_KEY env var.

    Args:
        model: Model ID, e.g. "gpt-4o", "o3-mini".
        api_key: API key. Defaults to OPENAI_API_KEY env var.
        base_url: Custom API base URL (for Azure, proxies, etc.).
        max_tokens: Max tokens for each response.
        temperature: Sampling temperature.
    """

    def __init__(
        self,
        model: str = "gpt-4o",
        api_key: str | None = None,
        base_url: str | None = None,
        max_tokens: int = 4096,
        temperature: float = 0.7,
    ) -> None:
        self.model = model
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY", "")
        self.base_url = base_url
        self.max_tokens = max_tokens
        self.temperature = temperature
        self._client = None

    def _get_client(self):
        if self._client is None:
            try:
                import openai
            except ImportError:
                raise ImportError(
                    "Install the openai package: pip install openai"
                )
            kwargs = {"api_key": self.api_key}
            if self.base_url:
                kwargs["base_url"] = self.base_url
            self._client = openai.AsyncOpenAI(**kwargs)
        return self._client

    async def generate(
        self,
        system: str,
        messages: list[dict[str, str]],
    ) -> str:
        client = self._get_client()
        full_messages = [{"role": "system", "content": system}] + messages
        response = await client.chat.completions.create(
            model=self.model,
            messages=full_messages,
            max_tokens=self.max_tokens,
            temperature=self.temperature,
        )
        return response.choices[0].message.content or ""
