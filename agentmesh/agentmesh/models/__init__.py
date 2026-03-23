"""Model backends for AgentMesh.

Each backend wraps a different LLM provider behind the same async interface.
Mix and match — use Opus for your lead agent, Haiku for workers, and a local
model for anything touching sensitive data.
"""

from agentmesh.models.base import ModelBackend
from agentmesh.models.anthropic import AnthropicBackend
from agentmesh.models.openai import OpenAIBackend
from agentmesh.models.ollama import OllamaBackend
from agentmesh.models.mock import MockBackend

__all__ = [
    "ModelBackend",
    "AnthropicBackend",
    "OpenAIBackend",
    "OllamaBackend",
    "MockBackend",
]
