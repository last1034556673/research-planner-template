"""Simplest possible AgentMesh example.

Two agents collaborate to answer a question. The Researcher finds
information and the Writer crafts the final response. They communicate
autonomously — no predefined workflow.

Usage:
    # With real APIs:
    export ANTHROPIC_API_KEY=sk-...
    python examples/simple/hello_mesh.py

    # Without APIs (uses mock backend):
    python examples/simple/hello_mesh.py --mock
"""

import asyncio
import sys

from agentmesh import Mesh
from agentmesh.models import AnthropicBackend, MockBackend


def build_mock_mesh() -> Mesh:
    """Build a mesh with mock backends for demo purposes."""
    mesh = Mesh()

    researcher_responses = [
        '```action\n{"action": "send", "to": "writer", "content": "Here are the key facts about quantum computing: 1) Uses qubits that can be 0, 1, or both simultaneously (superposition). 2) Quantum entanglement allows qubits to be correlated. 3) Current leaders: IBM (1000+ qubits), Google (quantum supremacy claim). 4) Main applications: cryptography, drug discovery, optimization. 5) Still in early stages — error correction is the main challenge."}\n```',
        '```action\n{"action": "answer", "content": "Research delivered to writer."}\n```',
    ]

    writer_responses = [
        '```action\n{"action": "answer", "content": "# Quantum Computing in 2025\\n\\nQuantum computing harnesses the strange properties of quantum mechanics to process information in fundamentally new ways.\\n\\n**How it works:** Unlike classical bits (0 or 1), quantum bits (qubits) can exist in superposition — both states at once. When qubits become entangled, measuring one instantly affects the other, enabling massive parallel computation.\\n\\n**Where we are:** IBM has crossed 1,000 qubits, and Google claimed quantum supremacy. But error correction remains the central challenge before practical, large-scale applications become reality.\\n\\n**Why it matters:** Quantum computers could revolutionize cryptography, accelerate drug discovery, and solve optimization problems that would take classical computers billions of years."}\n```',
    ]

    mesh.add(
        "researcher",
        role="You are a research specialist. Find relevant facts and data, then send them to the writer.",
        model=MockBackend(researcher_responses),
        capabilities=["research", "fact-finding", "data analysis"],
    )

    mesh.add(
        "writer",
        role="You are a skilled writer. Take research from peers and craft a clear, engaging response.",
        model=MockBackend(writer_responses),
        capabilities=["writing", "summarization", "editing"],
    )

    return mesh


def build_real_mesh() -> Mesh:
    """Build a mesh with real Anthropic backends."""
    mesh = Mesh()

    mesh.add(
        "researcher",
        role="You are a research specialist. Find relevant facts and data, then send your findings to the writer agent.",
        model=AnthropicBackend(model="claude-sonnet-4-20250514"),
        capabilities=["research", "fact-finding", "data analysis"],
    )

    mesh.add(
        "writer",
        role="You are a skilled writer. Wait for research from the researcher agent, then craft a clear, engaging response. Output your final text as an answer action.",
        model=AnthropicBackend(model="claude-sonnet-4-20250514"),
        capabilities=["writing", "summarization", "editing"],
    )

    return mesh


async def main():
    use_mock = "--mock" in sys.argv

    if use_mock:
        print("Running with mock backends (no API calls)\n")
        mesh = build_mock_mesh()
    else:
        print("Running with Anthropic backends\n")
        mesh = build_real_mesh()

    task = "Explain quantum computing to a smart 15 year old. Keep it under 200 words."

    print(f"Task: {task}\n")
    print("Agents:", mesh.agents)
    print("---\n")

    results = await mesh.run(task, entry_agent="researcher")

    print("=== Results ===\n")
    for agent_name, answer in results.items():
        print(f"[{agent_name}]")
        print(answer)
        print()

    print("=== Message Log ===\n")
    mesh.print_log()


if __name__ == "__main__":
    asyncio.run(main())
