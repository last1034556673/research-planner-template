"""Tests for memory subsystems."""

import pytest
from agentmesh.memory.local import LocalMemory
from agentmesh.memory.shared import SharedMemory


def test_local_memory_add_get():
    mem = LocalMemory()
    mem.add("facts", "sky is blue")
    mem.add("facts", "water is wet")
    assert mem.get("facts") == ["sky is blue", "water is wet"]


def test_local_memory_last():
    mem = LocalMemory()
    mem.add("x", 1)
    mem.add("x", 2)
    assert mem.last("x") == 2
    assert mem.last("nonexistent") is None


def test_local_memory_clear():
    mem = LocalMemory()
    mem.add("a", 1)
    mem.add("b", 2)
    mem.clear("a")
    assert mem.get("a") == []
    assert mem.get("b") == [2]
    mem.clear()
    assert mem.keys() == []


@pytest.mark.asyncio
async def test_shared_memory_set_get():
    mem = SharedMemory()
    await mem.set("key", "value")
    assert await mem.get("key") == "value"
    assert await mem.get("missing", "default") == "default"


@pytest.mark.asyncio
async def test_shared_memory_update():
    mem = SharedMemory()
    await mem.update({"a": 1, "b": 2})
    assert await mem.get("a") == 1
    assert await mem.get("b") == 2


@pytest.mark.asyncio
async def test_shared_memory_delete():
    mem = SharedMemory()
    await mem.set("x", 42)
    await mem.delete("x")
    assert await mem.get("x") is None


@pytest.mark.asyncio
async def test_shared_memory_snapshot():
    mem = SharedMemory()
    await mem.update({"a": 1, "b": 2})
    snap = await mem.snapshot()
    assert snap == {"a": 1, "b": 2}
