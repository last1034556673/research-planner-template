"""Mesh-wide shared memory — a thread-safe key-value store."""

from __future__ import annotations

import asyncio
from typing import Any


class SharedMemory:
    """Shared memory accessible by all agents in a mesh.

    Use this for facts, intermediate results, or coordination state
    that multiple agents need. Protected by an asyncio lock.
    """

    def __init__(self) -> None:
        self._store: dict[str, Any] = {}
        self._lock = asyncio.Lock()

    async def set(self, key: str, value: Any) -> None:
        """Set a value."""
        async with self._lock:
            self._store[key] = value

    async def get(self, key: str, default: Any = None) -> Any:
        """Get a value."""
        async with self._lock:
            return self._store.get(key, default)

    async def update(self, data: dict[str, Any]) -> None:
        """Merge multiple key-value pairs."""
        async with self._lock:
            self._store.update(data)

    async def delete(self, key: str) -> None:
        """Delete a key."""
        async with self._lock:
            self._store.pop(key, None)

    async def keys(self) -> list[str]:
        async with self._lock:
            return list(self._store.keys())

    async def snapshot(self) -> dict[str, Any]:
        """Return a shallow copy of the entire store."""
        async with self._lock:
            return dict(self._store)

    def __repr__(self) -> str:
        return f"SharedMemory(keys={list(self._store.keys())})"
