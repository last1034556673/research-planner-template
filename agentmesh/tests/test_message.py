"""Tests for the message bus."""

import asyncio
import pytest
from agentmesh.message import Message, MessageBus, MessageKind


@pytest.fixture
def bus():
    return MessageBus()


def test_message_creation():
    msg = Message(sender="a", receiver="b", kind=MessageKind.REQUEST, content="hello")
    assert msg.sender == "a"
    assert msg.receiver == "b"
    assert msg.content == "hello"
    assert msg.id  # auto-generated


def test_message_reply():
    msg = Message(sender="a", receiver="b", kind=MessageKind.REQUEST, content="hello")
    reply = msg.reply("world")
    assert reply.sender == "b"
    assert reply.receiver == "a"
    assert reply.kind == MessageKind.RESPONSE
    assert reply.reply_to == msg.id


@pytest.mark.asyncio
async def test_bus_direct_message(bus):
    q = bus.register("agent_b")
    msg = Message(sender="agent_a", receiver="agent_b", kind="request", content="hi")
    await bus.send(msg)
    received = await asyncio.wait_for(q.get(), timeout=1.0)
    assert received.content == "hi"
    assert received.sender == "agent_a"


@pytest.mark.asyncio
async def test_bus_broadcast(bus):
    q_a = bus.register("a")
    q_b = bus.register("b")
    q_c = bus.register("c")

    msg = Message(sender="a", receiver=None, kind="broadcast", content="hey all")
    await bus.send(msg)

    # a should NOT receive its own broadcast
    assert q_a.empty()
    # b and c should
    b_msg = await asyncio.wait_for(q_b.get(), timeout=1.0)
    c_msg = await asyncio.wait_for(q_c.get(), timeout=1.0)
    assert b_msg.content == "hey all"
    assert c_msg.content == "hey all"


@pytest.mark.asyncio
async def test_bus_log(bus):
    bus.register("a")
    bus.register("b")
    msg = Message(sender="a", receiver="b", kind="request", content="logged")
    await bus.send(msg)
    assert len(bus.log) == 1
    assert bus.log[0].content == "logged"


@pytest.mark.asyncio
async def test_bus_listener(bus):
    listener = bus.listen()
    bus.register("a")
    bus.register("b")
    msg = Message(sender="a", receiver="b", kind="request", content="observed")
    await bus.send(msg)
    observed = await asyncio.wait_for(listener.get(), timeout=1.0)
    assert observed.content == "observed"


def test_bus_agents(bus):
    bus.register("x")
    bus.register("y")
    assert set(bus.agents) == {"x", "y"}


def test_bus_unregister(bus):
    bus.register("x")
    bus.unregister("x")
    assert "x" not in bus.agents
