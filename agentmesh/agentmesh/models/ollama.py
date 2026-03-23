"""Ollama (local model) backend."""

from __future__ import annotations

import json
from agentmesh.models.base import ModelBackend


class OllamaBackend(ModelBackend):
    """Backend for local models via Ollama.

    No API key needed — just a running Ollama server.

    Args:
        model: Model name, e.g. "llama3.1", "qwen2.5", "deepseek-r1".
        base_url: Ollama API URL. Defaults to http://localhost:11434.
        temperature: Sampling temperature.
    """

    def __init__(
        self,
        model: str = "llama3.1",
        base_url: str = "http://localhost:11434",
        temperature: float = 0.7,
    ) -> None:
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.temperature = temperature

    async def generate(
        self,
        system: str,
        messages: list[dict[str, str]],
    ) -> str:
        try:
            import aiohttp
        except ImportError:
            raise ImportError(
                "Install aiohttp for Ollama support: pip install aiohttp"
            )

        full_messages = [{"role": "system", "content": system}] + messages
        payload = {
            "model": self.model,
            "messages": full_messages,
            "stream": False,
            "options": {"temperature": self.temperature},
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{self.base_url}/api/chat",
                json=payload,
            ) as resp:
                resp.raise_for_status()
                data = await resp.json()
                return data["message"]["content"]
