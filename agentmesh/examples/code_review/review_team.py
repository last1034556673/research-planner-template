"""Multi-agent code review team.

Three agents with different expertise review code collaboratively:
- Architect: evaluates design and structure
- Security: checks for vulnerabilities
- Reviewer: synthesizes feedback into a final review

The agents communicate freely — the Architect and Security agent
send their findings to the Reviewer, who produces the final output.

Usage:
    python examples/code_review/review_team.py --mock
    # or with real API:
    export ANTHROPIC_API_KEY=sk-...
    python examples/code_review/review_team.py
"""

import asyncio
import sys

from agentmesh import Mesh
from agentmesh.models import AnthropicBackend, MockBackend

SAMPLE_CODE = '''\
def process_user_input(request):
    username = request.params["username"]
    query = f"SELECT * FROM users WHERE name = '{username}'"
    db.execute(query)
    token = hashlib.md5(username.encode()).hexdigest()
    return {"user": username, "token": token, "query": query}
'''


def build_mock_mesh() -> Mesh:
    mesh = Mesh()

    architect_responses = [
        '```action\n{"action": "send", "to": "reviewer", "content": "Architecture issues found:\\n1. Function does too many things (query + auth + response). Violates SRP.\\n2. Raw SQL construction — should use an ORM or query builder.\\n3. Return value leaks implementation details (includes raw query).\\nRecommend: split into separate auth, query, and response functions."}\n```',
        '```action\n{"action": "answer", "content": "Architectural review sent to reviewer."}\n```',
    ]

    security_responses = [
        '```action\n{"action": "send", "to": "reviewer", "content": "CRITICAL security issues:\\n1. SQL INJECTION: f-string query construction allows arbitrary SQL. Use parameterized queries.\\n2. WEAK HASHING: MD5 is broken for auth tokens. Use secrets.token_urlsafe() or JWT.\\n3. DATA LEAK: returning the raw SQL query to the client exposes database schema.\\nSeverity: HIGH — this code should not be deployed."}\n```',
        '```action\n{"action": "answer", "content": "Security review sent to reviewer."}\n```',
    ]

    reviewer_responses = [
        '```action\n{"action": "answer", "content": "# Code Review Summary\\n\\n## Critical Issues\\n\\n**SQL Injection (CRITICAL):** The username is interpolated directly into the SQL query. An attacker could input `\\' OR 1=1 --` to dump the entire users table. Fix: use parameterized queries (`db.execute(\\"SELECT * FROM users WHERE name = ?\\", (username,))`)\\n\\n**Insecure Token Generation (HIGH):** MD5 is cryptographically broken. Use `secrets.token_urlsafe(32)` for session tokens or a proper JWT library.\\n\\n**Information Disclosure (MEDIUM):** The raw SQL query is returned in the response, exposing database schema to clients.\\n\\n## Design Issues\\n\\n- Function violates Single Responsibility Principle — split into `authenticate()`, `fetch_user()`, and response formatting.\\n- No input validation on the username parameter.\\n\\n## Verdict: REJECT — requires fixes before merge."}\n```',
    ]

    mesh.add("architect", role="Review code architecture and design patterns.", model=MockBackend(architect_responses), capabilities=["architecture", "design patterns", "code structure"])
    mesh.add("security", role="Find security vulnerabilities in code.", model=MockBackend(security_responses), capabilities=["security", "vulnerability analysis", "OWASP"])
    mesh.add("reviewer", role="Synthesize feedback from architect and security into a final code review. Wait for their input before writing your review.", model=MockBackend(reviewer_responses), capabilities=["code review", "synthesis", "writing"])

    return mesh


def build_real_mesh() -> Mesh:
    mesh = Mesh()
    sonnet = AnthropicBackend(model="claude-sonnet-4-20250514")

    mesh.add("architect", role="Review code for architecture and design pattern issues. Send your findings to the reviewer agent.", model=sonnet, capabilities=["architecture", "design patterns"])
    mesh.add("security", role="Find security vulnerabilities in code. Send your findings to the reviewer agent.", model=sonnet, capabilities=["security", "vulnerability analysis", "OWASP"])
    mesh.add("reviewer", role="Synthesize feedback from the architect and security agents into a single, actionable code review. Wait for both agents to send you their findings before writing your final review.", model=AnthropicBackend(model="claude-sonnet-4-20250514"), capabilities=["code review", "synthesis"])

    return mesh


async def main():
    use_mock = "--mock" in sys.argv
    mesh = build_mock_mesh() if use_mock else build_real_mesh()

    task = f"Review this Python code:\n\n```python\n{SAMPLE_CODE}```"

    print(f"Task: Review code\nAgents: {mesh.agents}\n---\n")
    results = await mesh.run(task)

    print("=== Final Review ===\n")
    if "reviewer" in results:
        print(results["reviewer"])
    else:
        for name, answer in results.items():
            print(f"[{name}] {answer}\n")

    print("\n=== Message Log ===\n")
    mesh.print_log()


if __name__ == "__main__":
    asyncio.run(main())
