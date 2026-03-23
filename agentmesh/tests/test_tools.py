"""Tests for the tool system."""

import pytest
from agentmesh.tools.base import Tool, tool


@pytest.mark.asyncio
async def test_tool_execute():
    async def greet(name: str = "world") -> str:
        return f"hello {name}"

    t = Tool(name="greet", description="Say hello", fn=greet)
    result = await t.execute(name="mesh")
    assert result == "hello mesh"


@pytest.mark.asyncio
async def test_tool_decorator():
    @tool(description="Add two numbers")
    async def add(a: int = 0, b: int = 0) -> str:
        return str(a + b)

    assert add.name == "add"
    assert add.description == "Add two numbers"
    result = await add.execute(a=3, b=4)
    assert result == "7"


@pytest.mark.asyncio
async def test_tool_decorator_sync():
    @tool(name="multiply", description="Multiply")
    def mul(a: int = 1, b: int = 1) -> str:
        return str(a * b)

    result = await mul.execute(a=5, b=6)
    assert result == "30"
