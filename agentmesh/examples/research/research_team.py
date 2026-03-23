"""Multi-agent research team using different model backends.

Demonstrates the key differentiator: mixing models within one mesh.
- Analyst: uses a strong model (Claude Opus) for deep reasoning
- Searcher: uses a fast model (GPT-4o-mini) for breadth
- Synthesizer: uses a local model (Ollama) for privacy

In mock mode, all agents use MockBackend.

Usage:
    python examples/research/research_team.py --mock
"""

import asyncio
import sys

from agentmesh import Mesh
from agentmesh.models import MockBackend


def build_mock_mesh() -> Mesh:
    mesh = Mesh()

    analyst_responses = [
        '```action\n{"action": "send", "to": "synthesizer", "content": "Deep analysis: The AI agent framework space is evolving from rigid pipelines (LangChain) toward more autonomous, message-passing architectures. Key trends: 1) Multi-model support becoming essential — no single model excels at everything. 2) Tool use is table stakes. 3) The gap is in autonomous inter-agent communication without predefined workflows. Most frameworks still require explicit orchestration graphs."}\n```',
        '```action\n{"action": "answer", "content": "Analysis complete, sent to synthesizer."}\n```',
    ]

    searcher_responses = [
        '```action\n{"action": "send", "to": "synthesizer", "content": "Market scan results:\\n- CrewAI: 25k stars, role-based agents, sequential/hierarchical processes\\n- AutoGen: 40k stars, conversation-driven, heavy config\\n- LangGraph: graph-based workflows, tight LangChain coupling\\n- OpenAI Swarm: experimental, function-based handoffs\\n- Camel: role-playing agents, academic focus\\n- MetaGPT: SOP-based, software engineering focus\\nGap: None of these support true autonomous peer-to-peer communication with multi-model backends."}\n```',
        '```action\n{"action": "answer", "content": "Search complete, sent to synthesizer."}\n```',
    ]

    synthesizer_responses = [
        '```action\n{"action": "answer", "content": "# Research Synthesis: AI Agent Framework Landscape\\n\\n## Key Finding\\nThere is a clear gap in the market for a framework that combines:\\n1. **Autonomous inter-agent communication** (no predefined workflows)\\n2. **Multi-model support** (mix Claude, GPT, local models in one system)\\n3. **Minimal constraints** (agents decide routing, not the framework)\\n\\n## Competitive Landscape\\n| Framework | Stars | Approach | Multi-model | Autonomous Routing |\\n|-----------|-------|----------|-------------|-------------------|\\n| AutoGen | 40k | Conversations | Partial | No |\\n| CrewAI | 25k | Roles + Tasks | Partial | No |\\n| LangGraph | 15k | Graph workflows | Via LangChain | No |\\n| Swarm | 12k | Function handoffs | OpenAI only | Partial |\\n\\n## Recommendation\\nPosition AgentMesh in the \\"autonomous mesh\\" niche. Key differentiators: zero-workflow setup, native multi-model, peer-to-peer by default."}\n```',
    ]

    mesh.add("analyst", role="Deep analytical reasoning about trends and implications. Send insights to the synthesizer.", model=MockBackend(analyst_responses), capabilities=["analysis", "reasoning", "trends"])
    mesh.add("searcher", role="Fast, broad information gathering. Send findings to the synthesizer.", model=MockBackend(searcher_responses), capabilities=["search", "market research", "data collection"])
    mesh.add("synthesizer", role="Wait for input from analyst and searcher, then combine into a structured research report. Output as your final answer.", model=MockBackend(synthesizer_responses), capabilities=["synthesis", "writing", "reporting"])

    return mesh


async def main():
    mesh = build_mock_mesh()

    task = "Research the current landscape of AI agent frameworks. What's the gap in the market?"

    print(f"Task: {task}\nAgents: {mesh.agents}\n---\n")
    results = await mesh.run(task)

    print("=== Research Report ===\n")
    if "synthesizer" in results:
        print(results["synthesizer"])

    print("\n=== Message Log ===\n")
    mesh.print_log()


if __name__ == "__main__":
    asyncio.run(main())
