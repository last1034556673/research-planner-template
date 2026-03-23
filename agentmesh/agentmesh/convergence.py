"""Convergence strategies — lightweight guardrails, not rigid workflows.

The mesh needs *some* way to know when agents are done, without
micromanaging their conversation. These strategies observe the message
flow and decide when to stop.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from agentmesh.message import Message


class ConvergenceStrategy(ABC):
    """Base class for convergence detection."""

    @abstractmethod
    def should_stop(self, messages: list[Message]) -> bool:
        """Return True if the mesh should stop."""
        ...


class TokenBudgetStrategy(ConvergenceStrategy):
    """Stop after a maximum number of messages.

    Simple but effective. Prevents runaway conversations.
    """

    def __init__(self, max_messages: int = 50) -> None:
        self.max_messages = max_messages

    def should_stop(self, messages: list[Message]) -> bool:
        return len(messages) >= self.max_messages


class QuietStrategy(ConvergenceStrategy):
    """Stop when no new messages have been sent for N seconds.

    Good for open-ended collaboration where you want agents to
    naturally wind down.
    """

    def __init__(self, quiet_seconds: float = 10.0) -> None:
        self.quiet_seconds = quiet_seconds

    def should_stop(self, messages: list[Message]) -> bool:
        if not messages:
            return False
        import time
        last = messages[-1].timestamp
        return (time.time() - last) > self.quiet_seconds


class ConsensusStrategy(ConvergenceStrategy):
    """Stop when all agents have sent an 'answer' action.

    The most principled approach — the mesh waits until every agent
    has declared its conclusion.
    """

    def __init__(self, agent_names: list[str]) -> None:
        self.agent_names = set(agent_names)

    def should_stop(self, messages: list[Message]) -> bool:
        answered = set()
        for msg in messages:
            if msg.kind == "result" or msg.kind == "answer":
                answered.add(msg.sender)
        return self.agent_names.issubset(answered)
