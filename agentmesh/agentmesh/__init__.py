"""AgentMesh — A minimal-constraint multi-model AI agent framework.

Agents autonomously discover peers, communicate, and collaborate
with no rigid workflow definitions. You define agents; they figure
out who to talk to.
"""

__version__ = "0.1.0"

from agentmesh.message import Message, MessageBus
from agentmesh.agent import Agent
from agentmesh.mesh import Mesh

__all__ = ["Agent", "Mesh", "Message", "MessageBus"]
