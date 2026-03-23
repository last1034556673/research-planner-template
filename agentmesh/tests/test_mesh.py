"""Tests for the Mesh orchestrator."""

import pytest
from agentmesh import Mesh
from agentmesh.models.mock import MockBackend


@pytest.mark.asyncio
async def test_mesh_two_agents():
    """Two agents collaborate: one sends to the other, the other answers."""
    mesh = Mesh()

    mesh.add(
        "sender",
        role="Send your task to the receiver agent.",
        model=MockBackend([
            '```action\n{"action": "send", "to": "receiver", "content": "Please handle this task."}\n```',
            '```action\n{"action": "answer", "content": "Delegated to receiver."}\n```',
        ]),
        capabilities=["delegation"],
    )

    mesh.add(
        "receiver",
        role="Wait for messages and produce an answer.",
        model=MockBackend([
            '```action\n{"action": "answer", "content": "Task completed successfully."}\n```',
        ]),
        capabilities=["execution"],
    )

    results = await mesh.run("Do something useful.", entry_agent="sender")
    assert "sender" in results
    assert "receiver" in results
    assert "Delegated" in results["sender"]
    assert "completed" in results["receiver"]


@pytest.mark.asyncio
async def test_mesh_broadcast_task():
    """All agents receive the task when no entry_agent is specified."""
    mesh = Mesh()

    mesh.add("a", role="Answer directly.", model=MockBackend([
        '```action\n{"action": "answer", "content": "A done"}\n```',
    ]))
    mesh.add("b", role="Answer directly.", model=MockBackend([
        '```action\n{"action": "answer", "content": "B done"}\n```',
    ]))

    results = await mesh.run("Hello everyone")
    assert results["a"] == "A done"
    assert results["b"] == "B done"


def test_mesh_agents_list():
    mesh = Mesh()
    mesh.add("x", role="test", model=MockBackend())
    mesh.add("y", role="test", model=MockBackend())
    assert set(mesh.agents) == {"x", "y"}


def test_mesh_remove():
    mesh = Mesh()
    mesh.add("x", role="test", model=MockBackend())
    mesh.remove("x")
    assert "x" not in mesh.agents


def test_mesh_run_sync():
    mesh = Mesh()
    mesh.add("a", role="Answer.", model=MockBackend([
        '```action\n{"action": "answer", "content": "sync works"}\n```',
    ]))
    results = mesh.run_sync("test")
    assert results["a"] == "sync works"


@pytest.mark.asyncio
async def test_mesh_message_log():
    mesh = Mesh()
    mesh.add("sender", role="Send a message.", model=MockBackend([
        '```action\n{"action": "send", "to": "receiver", "content": "hello"}\n```',
        '```action\n{"action": "answer", "content": "done"}\n```',
    ]))
    mesh.add("receiver", role="Answer.", model=MockBackend([
        '```action\n{"action": "answer", "content": "got it"}\n```',
    ]))

    await mesh.run("go", entry_agent="sender")
    assert len(mesh.message_log) >= 1
    assert mesh.message_log[0].sender == "sender"
