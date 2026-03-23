"""Memory subsystem for agents.

- LocalMemory: per-agent scratchpad
- SharedMemory: mesh-wide key-value store accessible by all agents
"""

from agentmesh.memory.local import LocalMemory
from agentmesh.memory.shared import SharedMemory

__all__ = ["LocalMemory", "SharedMemory"]
