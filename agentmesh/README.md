# AgentMesh

**Minimal-constraint multi-model AI agent framework.**

Agents communicate autonomously — you define *who they are*, they figure out *who to talk to*.

```python
from agentmesh import Mesh
from agentmesh.models import AnthropicBackend, OpenAIBackend, OllamaBackend

mesh = Mesh()

# Mix models freely — use the right model for each role
mesh.add("researcher",
    role="Find facts and send them to the writer.",
    model=AnthropicBackend(model="claude-sonnet-4-20250514"),
    capabilities=["research", "analysis"])

mesh.add("writer",
    role="Craft clear responses from research findings.",
    model=OpenAIBackend(model="gpt-4o"),
    capabilities=["writing", "editing"])

mesh.add("fact_checker",
    role="Verify claims. Flag anything incorrect.",
    model=OllamaBackend(model="llama3.1"),  # local, no API key
    capabilities=["verification"])

# One line to run — agents handle the rest
results = mesh.run_sync("Explain CRISPR gene editing in 200 words")
```

## Why AgentMesh?

| | AgentMesh | CrewAI | AutoGen | LangGraph |
|---|---|---|---|---|
| **Define workflows?** | No — agents route autonomously | Yes (sequential/hierarchical) | Yes (conversation patterns) | Yes (graph required) |
| **Multi-model?** | Native (mix any backend) | Partial | Partial | Via LangChain |
| **Agent communication** | Peer-to-peer mesh | Task delegation | Conversation threads | Graph edges |
| **Lines to hello world** | ~10 | ~20 | ~30 | ~40 |
| **Core dependency** | None | Several | Several | LangChain |

### Design philosophy

> Tell agents *what they are*, not *how to behave*. The model's reasoning handles the rest.

Most frameworks make you define explicit workflows, pipelines, or conversation graphs. AgentMesh doesn't. Agents discover each other's capabilities and communicate through a message bus. They decide autonomously who to talk to, when to delegate, and when to stop.

**Minimal constraints = smarter agents.** Rigid orchestration makes agents dumber by replacing their reasoning with your scripting. AgentMesh gives agents just enough structure (message protocol + capability directory) and gets out of the way.

## Install

```bash
pip install agentmesh                    # core (no model backends)
pip install agentmesh[anthropic]         # + Claude
pip install agentmesh[openai]            # + GPT
pip install agentmesh[ollama]            # + local models
pip install agentmesh[all]               # everything
pip install agentmesh[dev]               # + pytest
```

Or from source:
```bash
git clone https://github.com/YOUR_USERNAME/agentmesh.git
cd agentmesh
pip install -e ".[all,dev]"
```

## Quick start

### 1. Two agents, one task

```python
import asyncio
from agentmesh import Mesh
from agentmesh.models import AnthropicBackend

mesh = Mesh()

mesh.add("analyst",
    role="Analyze the topic deeply. Send key insights to the writer.",
    model=AnthropicBackend(),
    capabilities=["analysis", "reasoning"])

mesh.add("writer",
    role="Wait for the analyst's input, then write a clear summary.",
    model=AnthropicBackend(),
    capabilities=["writing"])

results = asyncio.run(mesh.run(
    "What are the implications of quantum computing for cryptography?",
    entry_agent="analyst",  # analyst starts, writer waits
))

print(results["writer"])
```

### 2. Give agents tools

```python
from agentmesh.tools import tool

@tool(description="Search the web for information")
async def web_search(query: str = "") -> str:
    # Your search implementation
    return f"Results for: {query}"

@tool(description="Run Python code and return output")
async def run_python(code: str = "") -> str:
    # Your sandbox implementation
    return f"Output: ..."

mesh.add("researcher",
    role="Research topics using web search.",
    model=AnthropicBackend(),
    tools=[web_search],
    capabilities=["research", "web search"])

mesh.add("coder",
    role="Write and test Python code.",
    model=AnthropicBackend(),
    tools=[run_python],
    capabilities=["coding", "testing"])
```

### 3. Use different models for different agents

```python
from agentmesh.models import AnthropicBackend, OpenAIBackend, OllamaBackend

# Strong model for complex reasoning
lead = AnthropicBackend(model="claude-opus-4-20250514")

# Fast model for simple tasks
worker = AnthropicBackend(model="claude-haiku-4-5-20251001")

# Local model for sensitive data (never leaves your machine)
private = OllamaBackend(model="llama3.1")

# OpenAI for variety
gpt = OpenAIBackend(model="gpt-4o")
```

### 4. Run without API keys (mock mode)

```python
from agentmesh.models import MockBackend

# Scripted responses for testing
mock = MockBackend([
    '```action\n{"action": "answer", "content": "Mock response"}\n```'
])

mesh.add("test_agent", role="Testing", model=mock)
```

## How it works

### Architecture

```
┌──────────────────────────────────────────┐
│                  Mesh                     │
│                                           │
│  ┌─────────┐  ┌─────────┐  ┌─────────┐  │
│  │ Agent A  │  │ Agent B  │  │ Agent C  │  │
│  │ (Claude) │  │ (GPT-4o) │  │ (Llama)  │  │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  │
│       │              │              │        │
│  ─────┴──────────────┴──────────────┴─────  │
│              Message Bus                     │
└──────────────────────────────────────────┘
```

1. **You create agents** with a name, role, model, and capabilities
2. **The mesh builds a peer directory** — each agent knows who else exists and what they can do
3. **You submit a task** — it goes to the entry agent (or all agents)
4. **Agents communicate freely** via the message bus — sending targeted messages, broadcasts, or delegations
5. **Each agent decides** who to talk to based on the peer directory and the conversation
6. **Agents declare answers** when they're done — the mesh collects all results

### Message protocol

Agents communicate through action blocks in their responses:

```python
# Send to a specific agent
{"action": "send", "to": "agent_name", "content": "..."}

# Broadcast to all agents
{"action": "broadcast", "content": "..."}

# Use a tool
{"action": "tool", "name": "tool_name", "args": {...}}

# Declare final answer (stops this agent)
{"action": "answer", "content": "..."}
```

### Convergence

How does the mesh know when to stop?

- **Per-agent**: Each agent has a `max_turns` limit (default 20)
- **Global timeout**: The mesh has a 5-minute timeout
- **Strategies** (pluggable):
  - `TokenBudgetStrategy` — stop after N total messages
  - `QuietStrategy` — stop when no messages for N seconds
  - `ConsensusStrategy` — stop when all agents have answered

## Examples

```bash
# Simple two-agent collaboration (mock, no API key needed)
python examples/simple/hello_mesh.py --mock

# Multi-agent code review team
python examples/code_review/review_team.py --mock

# Research team with different model roles
python examples/research/research_team.py --mock
```

## Testing

```bash
pip install -e ".[dev]"
pytest tests/ -v
```

## Project structure

```
agentmesh/
├── agentmesh/
│   ├── __init__.py          # Package entry point
│   ├── agent.py             # Agent class with autonomous loop
│   ├── mesh.py              # Mesh orchestrator
│   ├── message.py           # Message protocol and bus
│   ├── convergence.py       # Convergence strategies
│   ├── models/
│   │   ├── base.py          # ModelBackend interface
│   │   ├── anthropic.py     # Claude backend
│   │   ├── openai.py        # GPT backend
│   │   ├── ollama.py        # Local model backend
│   │   └── mock.py          # Testing backend
│   ├── memory/
│   │   ├── local.py         # Per-agent scratchpad
│   │   └── shared.py        # Mesh-wide shared state
│   └── tools/
│       └── base.py          # Tool interface and @tool decorator
├── examples/
│   ├── simple/              # Minimal hello world
│   ├── code_review/         # Multi-agent code review
│   └── research/            # Multi-model research team
├── tests/                   # Full test suite
├── pyproject.toml
└── README.md
```

## Roadmap

- [ ] Streaming support (real-time agent output)
- [ ] Web UI for observing agent conversations
- [ ] Persistent shared memory (SQLite/Redis)
- [ ] Agent hot-swap (add/remove agents mid-run)
- [ ] Sub-mesh spawning (agents creating child meshes)
- [ ] MCP tool server integration

## Contributing

PRs welcome. The core principle: **keep it minimal**. If a feature adds constraints that make agents dumber, it doesn't belong here.

## License

MIT
