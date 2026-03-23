"""Base tool interface and decorator.

Tools give agents the ability to interact with the outside world —
run code, search the web, read files, call APIs, etc.
"""

from __future__ import annotations

import asyncio
import functools
import inspect
from dataclasses import dataclass, field
from typing import Any, Callable, Awaitable


@dataclass
class Tool:
    """A tool an agent can use.

    Args:
        name: Short identifier (e.g. "web_search", "run_python").
        description: What the tool does — shown to the model.
        fn: The async callable that implements the tool.
        parameters: Optional JSON Schema describing the arguments.
    """

    name: str
    description: str
    fn: Callable[..., Awaitable[str]]
    parameters: dict[str, Any] = field(default_factory=dict)

    async def execute(self, **kwargs: Any) -> str:
        """Run the tool and return a string result."""
        result = self.fn(**kwargs)
        if inspect.isawaitable(result):
            result = await result
        return str(result)


def tool(
    name: str | None = None,
    description: str = "",
) -> Callable:
    """Decorator to create a Tool from an async function.

    Usage:
        @tool(description="Search the web")
        async def web_search(query: str) -> str:
            ...
    """

    def decorator(fn: Callable) -> Tool:
        tool_name = name or fn.__name__

        # Ensure the function is async
        if not asyncio.iscoroutinefunction(fn):
            @functools.wraps(fn)
            async def async_fn(**kwargs):
                return fn(**kwargs)
            actual_fn = async_fn
        else:
            actual_fn = fn

        return Tool(
            name=tool_name,
            description=description or fn.__doc__ or "",
            fn=actual_fn,
        )

    return decorator
