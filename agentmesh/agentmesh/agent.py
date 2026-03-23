"""Agent — the fundamental unit in the mesh.

An Agent has:
- An identity (name + role description)
- A model backend (any LLM)
- Capabilities it advertises to peers
- Tools it can use
- Autonomy to decide who to talk to and when to stop

The design philosophy: tell the agent *what* it is, not *how* to behave.
The model's reasoning handles the rest.
"""

from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Awaitable

from agentmesh.message import Message, MessageBus, MessageKind
from agentmesh.models.base import ModelBackend
from agentmesh.memory.local import LocalMemory
from agentmesh.tools.base import Tool

logger = logging.getLogger("agentmesh")


@dataclass
class AgentConfig:
    """Static agent configuration."""

    name: str
    role: str  # Free-form role description — this IS the prompt
    capabilities: list[str] = field(default_factory=list)
    model: ModelBackend | None = None
    tools: list[Tool] = field(default_factory=list)
    max_turns: int = 20  # Safety cap on autonomous message loops
    system_prompt_extra: str = ""


# The routing prompt injected into every agent's system message.
# It teaches the agent HOW to communicate without restricting WHAT it thinks.
_ROUTING_PROMPT = """\
You are part of an agent mesh. You can communicate with other agents by \
outputting JSON action blocks.

Available agents and their capabilities:
{peer_directory}

Actions you can take (output as JSON inside ```action fences):

1. Send a message to a specific agent:
```action
{{"action": "send", "to": "<agent_name>", "content": "<your message>"}}
```

2. Broadcast to all agents:
```action
{{"action": "broadcast", "content": "<your message>"}}
```

3. Declare your final answer (stops your turn):
```action
{{"action": "answer", "content": "<final answer>"}}
```

4. Use a tool:
```action
{{"action": "tool", "name": "<tool_name>", "args": {{...}}}}
```

You may output multiple actions in one response. Think step by step about \
who can help, then act. If you can answer directly, just answer. \
Do not ask for permission — act autonomously.

Incoming messages from other agents will appear as user messages prefixed \
with [from:<agent_name>].
"""


class Agent:
    """A mesh-connected autonomous agent."""

    def __init__(self, config: AgentConfig) -> None:
        self.config = config
        self.name = config.name
        self.memory = LocalMemory()
        self._bus: MessageBus | None = None
        self._inbox: asyncio.Queue[Message] | None = None
        self._conversation: list[dict[str, str]] = []
        self._running = False
        self._result: str | None = None
        self._tools_map: dict[str, Tool] = {t.name: t for t in config.tools}
        self._peer_directory: str = ""

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def attach(self, bus: MessageBus, peer_directory: str) -> None:
        """Attach to a message bus. Called by the Mesh."""
        self._bus = bus
        self._inbox = bus.register(self.name)
        self._peer_directory = peer_directory

    def detach(self) -> None:
        if self._bus:
            self._bus.unregister(self.name)
            self._bus = None
            self._inbox = None

    # ------------------------------------------------------------------
    # System prompt
    # ------------------------------------------------------------------

    def _build_system(self) -> str:
        parts = [
            f"Your name is {self.name}.",
            f"Your role: {self.config.role}",
        ]
        if self.config.capabilities:
            parts.append(f"Your capabilities: {', '.join(self.config.capabilities)}")
        if self.config.system_prompt_extra:
            parts.append(self.config.system_prompt_extra)

        tool_descriptions = ""
        if self._tools_map:
            tool_lines = []
            for t in self._tools_map.values():
                tool_lines.append(f"- {t.name}: {t.description}")
            tool_descriptions = "\nAvailable tools:\n" + "\n".join(tool_lines)

        parts.append(
            _ROUTING_PROMPT.format(peer_directory=self._peer_directory)
            + tool_descriptions
        )
        return "\n\n".join(parts)

    # ------------------------------------------------------------------
    # Core loop
    # ------------------------------------------------------------------

    async def run(self, task: str | None = None) -> str:
        """Run the agent's autonomous loop.

        If *task* is given, it becomes the first user message.
        The agent then processes incoming messages and acts until it
        produces an answer or hits the turn limit.
        """
        self._running = True
        self._result = None
        self._conversation = []
        model = self.config.model
        if model is None:
            raise RuntimeError(f"Agent {self.name} has no model backend")

        system = self._build_system()

        if task:
            self._conversation.append({"role": "user", "content": task})

        for turn in range(self.config.max_turns):
            if not self._running:
                break

            # Drain inbox — add any new messages from peers
            if self._inbox:
                while not self._inbox.empty():
                    msg = self._inbox.get_nowait()
                    self._conversation.append({
                        "role": "user",
                        "content": f"[from:{msg.sender}] {msg.content}",
                    })

            if not self._conversation:
                # Nothing to do yet, wait briefly for messages
                try:
                    msg = await asyncio.wait_for(self._inbox.get(), timeout=2.0)
                    self._conversation.append({
                        "role": "user",
                        "content": f"[from:{msg.sender}] {msg.content}",
                    })
                except (asyncio.TimeoutError, AttributeError):
                    continue

            # Call the model
            response = await model.generate(system, self._conversation)
            self._conversation.append({"role": "assistant", "content": response})
            self.memory.add("conversation", {"role": "assistant", "content": response})

            # Parse and execute actions
            actions = _parse_actions(response)
            if not actions:
                # No structured action — treat the whole response as the answer
                self._result = response
                break

            for action in actions:
                await self._execute_action(action)
                if not self._running:
                    break

        self._running = False
        return self._result or "(no answer produced)"

    async def _execute_action(self, action: dict[str, Any]) -> None:
        """Execute a single parsed action."""
        kind = action.get("action", "")

        if kind == "send" and self._bus:
            msg = Message(
                sender=self.name,
                receiver=action.get("to", ""),
                kind=MessageKind.REQUEST,
                content=action.get("content", ""),
            )
            await self._bus.send(msg)

        elif kind == "broadcast" and self._bus:
            msg = Message(
                sender=self.name,
                receiver=None,
                kind=MessageKind.BROADCAST,
                content=action.get("content", ""),
            )
            await self._bus.send(msg)

        elif kind == "answer":
            self._result = action.get("content", "")
            self._running = False

        elif kind == "tool":
            tool_name = action.get("name", "")
            tool = self._tools_map.get(tool_name)
            if tool:
                args = action.get("args", {})
                result = await tool.execute(**args)
                self._conversation.append({
                    "role": "user",
                    "content": f"[tool:{tool_name} result] {result}",
                })
            else:
                self._conversation.append({
                    "role": "user",
                    "content": f"[error] Unknown tool: {tool_name}",
                })

    def stop(self) -> None:
        """Signal the agent to stop after the current turn."""
        self._running = False


def _parse_actions(text: str) -> list[dict[str, Any]]:
    """Extract action blocks from model output.

    Looks for ```action ... ``` fenced blocks containing JSON.
    """
    actions = []
    parts = text.split("```action")
    for part in parts[1:]:  # skip everything before the first fence
        end = part.find("```")
        if end == -1:
            json_str = part.strip()
        else:
            json_str = part[:end].strip()
        try:
            parsed = json.loads(json_str)
            actions.append(parsed)
        except json.JSONDecodeError:
            continue
    return actions
