"""Per-agent local memory — a simple append-only scratchpad."""

from __future__ import annotations

from typing import Any


class LocalMemory:
    """Agent-private memory store.

    Think of it as the agent's personal notebook. Other agents cannot
    access it directly — they must ask via messages.
    """

    def __init__(self) -> None:
        self._store: dict[str, list[Any]] = {}

    def add(self, key: str, value: Any) -> None:
        """Append a value under a key."""
        self._store.setdefault(key, []).append(value)

    def get(self, key: str) -> list[Any]:
        """Get all values under a key."""
        return self._store.get(key, [])

    def last(self, key: str) -> Any | None:
        """Get the most recent value under a key."""
        items = self._store.get(key, [])
        return items[-1] if items else None

    def clear(self, key: str | None = None) -> None:
        """Clear a specific key or everything."""
        if key is None:
            self._store.clear()
        else:
            self._store.pop(key, None)

    def keys(self) -> list[str]:
        return list(self._store.keys())

    def __repr__(self) -> str:
        counts = {k: len(v) for k, v in self._store.items()}
        return f"LocalMemory({counts})"
