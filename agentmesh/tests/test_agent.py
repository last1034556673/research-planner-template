"""Tests for the Agent class."""

import asyncio
import pytest
from agentmesh.agent import Agent, AgentConfig, _parse_actions
from agentmesh.message import MessageBus
from agentmesh.models.mock import MockBackend


def test_parse_actions_single():
    text = 'Some thinking...\n```action\n{"action": "answer", "content": "done"}\n```'
    actions = _parse_actions(text)
    assert len(actions) == 1
    assert actions[0]["action"] == "answer"
    assert actions[0]["content"] == "done"


def test_parse_actions_multiple():
    text = '''Let me help.
```action
{"action": "send", "to": "bob", "content": "hi"}
```
And also:
```action
{"action": "answer", "content": "finished"}
```'''
    actions = _parse_actions(text)
    assert len(actions) == 2
    assert actions[0]["action"] == "send"
    assert actions[1]["action"] == "answer"


def test_parse_actions_no_actions():
    text = "Just a regular response with no actions."
    actions = _parse_actions(text)
    assert len(actions) == 0


def test_parse_actions_malformed_json():
    text = '```action\n{not valid json}\n```'
    actions = _parse_actions(text)
    assert len(actions) == 0


@pytest.mark.asyncio
async def test_agent_direct_answer():
    """Agent produces an answer action on the first turn."""
    mock = MockBackend([
        '```action\n{"action": "answer", "content": "The answer is 42."}\n```'
    ])
    config = AgentConfig(name="test", role="test agent", model=mock)
    agent = Agent(config)
    bus = MessageBus()
    agent.attach(bus, "(no peers)")

    result = await agent.run("What is the meaning of life?")
    assert result == "The answer is 42."
    assert mock.call_count == 1


@pytest.mark.asyncio
async def test_agent_sends_then_answers():
    """Agent sends a message to a peer, then answers."""
    mock = MockBackend([
        '```action\n{"action": "send", "to": "peer", "content": "help me"}\n```',
        '```action\n{"action": "answer", "content": "got it"}\n```',
    ])
    config = AgentConfig(name="test", role="test agent", model=mock)
    agent = Agent(config)
    bus = MessageBus()
    bus.register("peer")  # register a dummy peer
    agent.attach(bus, "- peer (helper): [general]")

    result = await agent.run("do something")
    assert result == "got it"
    assert mock.call_count == 2

    # Verify the message was sent on the bus
    assert len(bus.log) == 1
    assert bus.log[0].receiver == "peer"


@pytest.mark.asyncio
async def test_agent_no_action_returns_raw():
    """If the model doesn't use action blocks, the raw text becomes the answer."""
    mock = MockBackend(["Just a plain text response."])
    config = AgentConfig(name="test", role="test agent", model=mock)
    agent = Agent(config)
    bus = MessageBus()
    agent.attach(bus, "(no peers)")

    result = await agent.run("hello")
    assert result == "Just a plain text response."


@pytest.mark.asyncio
async def test_agent_max_turns():
    """Agent respects max_turns limit."""
    # Always sends, never answers — should hit the turn limit
    mock = MockBackend(lambda s, m: '```action\n{"action": "send", "to": "nobody", "content": "looping"}\n```')
    config = AgentConfig(name="test", role="test agent", model=mock, max_turns=3)
    agent = Agent(config)
    bus = MessageBus()
    agent.attach(bus, "(no peers)")

    result = await agent.run("go")
    assert mock.call_count <= 3


@pytest.mark.asyncio
async def test_agent_stop():
    """Agent can be stopped externally during execution."""
    call_count = 0

    def stop_after_two(s, m):
        nonlocal call_count
        call_count += 1
        if call_count >= 2:
            agent.stop()
        return '```action\n{"action": "send", "to": "x", "content": "..."}\n```'

    mock = MockBackend(stop_after_two)
    config = AgentConfig(name="test", role="test", model=mock, max_turns=100)
    agent = Agent(config)
    bus = MessageBus()
    agent.attach(bus, "")

    result = await agent.run("go")
    # Should have stopped after ~2-3 calls, not 100
    assert mock.call_count <= 3
