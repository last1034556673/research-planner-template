"""Mesh — the orchestration layer that connects agents.

The Mesh is deliberately thin. It:
1. Registers agents and builds a peer directory
2. Starts all agents concurrently
3. Collects results
4. Provides observability (message log, live listener)

It does NOT define workflows, pipelines, or turn order.
Agents decide for themselves.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from agentmesh.agent import Agent, AgentConfig
from agentmesh.message import MessageBus, Message
from agentmesh.models.base import ModelBackend
from agentmesh.convergence import ConvergenceStrategy, TokenBudgetStrategy

logger = logging.getLogger("agentmesh")


class Mesh:
    """A mesh of autonomous agents that communicate freely."""

    def __init__(
        self,
        convergence: ConvergenceStrategy | None = None,
    ) -> None:
        self.bus = MessageBus()
        self._agents: dict[str, Agent] = {}
        self._convergence = convergence or TokenBudgetStrategy()

    # ------------------------------------------------------------------
    # Agent registration
    # ------------------------------------------------------------------

    def add(
        self,
        name: str,
        role: str,
        model: ModelBackend,
        *,
        capabilities: list[str] | None = None,
        tools: list | None = None,
        max_turns: int = 20,
        system_prompt_extra: str = "",
    ) -> Agent:
        """Create and register an agent in the mesh."""
        config = AgentConfig(
            name=name,
            role=role,
            capabilities=capabilities or [],
            model=model,
            tools=tools or [],
            max_turns=max_turns,
            system_prompt_extra=system_prompt_extra,
        )
        agent = Agent(config)
        self._agents[name] = agent
        return agent

    def add_agent(self, agent: Agent) -> None:
        """Register a pre-configured Agent."""
        self._agents[agent.name] = agent

    def remove(self, name: str) -> None:
        """Remove an agent from the mesh."""
        agent = self._agents.pop(name, None)
        if agent:
            agent.detach()

    # ------------------------------------------------------------------
    # Peer directory
    # ------------------------------------------------------------------

    def _build_peer_directory(self, exclude: str) -> str:
        """Build a text directory of all agents except *exclude*."""
        lines = []
        for name, agent in self._agents.items():
            if name == exclude:
                continue
            caps = ", ".join(agent.config.capabilities) if agent.config.capabilities else "general"
            lines.append(f"- {name} ({agent.config.role}): [{caps}]")
        return "\n".join(lines) if lines else "(no other agents)"

    # ------------------------------------------------------------------
    # Execution
    # ------------------------------------------------------------------

    async def run(
        self,
        task: str,
        *,
        entry_agent: str | None = None,
    ) -> dict[str, str]:
        """Run the mesh on a task.

        Args:
            task: The task description.
            entry_agent: Name of the agent that receives the task directly.
                         If None, all agents receive it as a broadcast.

        Returns:
            Dict mapping agent name → final answer.
        """
        # Attach all agents to the bus with their peer directories
        for name, agent in self._agents.items():
            directory = self._build_peer_directory(exclude=name)
            agent.attach(self.bus, directory)

        # Build coroutines
        coros: dict[str, asyncio.Task] = {}
        for name, agent in self._agents.items():
            if entry_agent is None or name == entry_agent:
                coros[name] = asyncio.create_task(
                    agent.run(task), name=f"agent:{name}"
                )
            else:
                # Non-entry agents run without an initial task —
                # they wait for messages from peers
                coros[name] = asyncio.create_task(
                    agent.run(None), name=f"agent:{name}"
                )

        # Wait for all agents to finish
        results: dict[str, str] = {}
        done, pending = await asyncio.wait(
            coros.values(),
            timeout=300,  # 5 minute global timeout
        )

        for name, atask in coros.items():
            if atask in done:
                try:
                    results[name] = atask.result()
                except Exception as e:
                    results[name] = f"(error: {e})"
            else:
                self._agents[name].stop()
                atask.cancel()
                results[name] = "(timed out)"

        # Detach all
        for agent in self._agents.values():
            agent.detach()

        return results

    def run_sync(self, task: str, **kwargs: Any) -> dict[str, str]:
        """Synchronous wrapper around run()."""
        return asyncio.run(self.run(task, **kwargs))

    # ------------------------------------------------------------------
    # Observability
    # ------------------------------------------------------------------

    @property
    def agents(self) -> list[str]:
        return list(self._agents.keys())

    @property
    def message_log(self) -> list[Message]:
        return self.bus.log

    def print_log(self) -> None:
        """Print all messages in a human-readable format."""
        for msg in self.bus.log:
            receiver = msg.receiver or "*"
            print(f"[{msg.sender} → {receiver}] ({msg.kind}) {msg.content[:120]}")
