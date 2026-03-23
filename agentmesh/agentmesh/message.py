"""Message protocol and bus for inter-agent communication.

Messages are the only coupling between agents. The protocol is intentionally
minimal: a sender, a receiver (or broadcast), a kind, and a payload. Agents
decide what to send and who to send it to — the bus just delivers.
"""

from __future__ import annotations

import asyncio
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class MessageKind(str, Enum):
    """Built-in message kinds. Agents may use custom strings too."""

    REQUEST = "request"          # Ask another agent to do something
    RESPONSE = "response"        # Reply to a request
    BROADCAST = "broadcast"      # Announce to all agents
    DELEGATE = "delegate"        # Hand off a sub-task
    RESULT = "result"            # Final result of a delegation
    DISCOVER = "discover"        # Capability discovery query
    ADVERTISE = "advertise"      # Capability advertisement
    SIGNAL = "signal"            # Control signal (e.g. stop, pause)


@dataclass
class Message:
    """A single message between agents."""

    sender: str
    receiver: str | None  # None = broadcast
    kind: str | MessageKind
    content: str
    payload: dict[str, Any] = field(default_factory=dict)
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    reply_to: str | None = None  # id of message being replied to
    timestamp: float = field(default_factory=time.time)

    def reply(self, content: str, **payload: Any) -> Message:
        """Create a reply to this message."""
        return Message(
            sender=self.receiver or "",
            receiver=self.sender,
            kind=MessageKind.RESPONSE,
            content=content,
            payload=payload,
            reply_to=self.id,
        )


class MessageBus:
    """Async message bus that routes messages between agents.

    Agents subscribe by name. Broadcasts go to everyone except the sender.
    The bus keeps a full log for observability.
    """

    def __init__(self) -> None:
        self._queues: dict[str, asyncio.Queue[Message]] = {}
        self._log: list[Message] = []
        self._listeners: list[asyncio.Queue[Message]] = []

    def register(self, agent_name: str) -> asyncio.Queue[Message]:
        """Register an agent and return its inbox queue."""
        if agent_name in self._queues:
            return self._queues[agent_name]
        q: asyncio.Queue[Message] = asyncio.Queue()
        self._queues[agent_name] = q
        return q

    def unregister(self, agent_name: str) -> None:
        """Remove an agent from the bus."""
        self._queues.pop(agent_name, None)

    async def send(self, message: Message) -> None:
        """Route a message to its destination(s)."""
        self._log.append(message)
        # notify global listeners (for observability)
        for lq in self._listeners:
            await lq.put(message)

        if message.receiver is None:
            # broadcast to all except sender
            for name, q in self._queues.items():
                if name != message.sender:
                    await q.put(message)
        else:
            q = self._queues.get(message.receiver)
            if q is not None:
                await q.put(message)

    def listen(self) -> asyncio.Queue[Message]:
        """Get a queue that receives copies of ALL messages (for logging/UI)."""
        q: asyncio.Queue[Message] = asyncio.Queue()
        self._listeners.append(q)
        return q

    @property
    def log(self) -> list[Message]:
        return list(self._log)

    @property
    def agents(self) -> list[str]:
        return list(self._queues.keys())
