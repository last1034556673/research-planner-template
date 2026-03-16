# CLAUDE.md

Use this repository as a self-contained local planning system.

## Recommended order

1. Read [`README.md`](README.md).
2. Read [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).
3. Read [`docs/PLANNER_WORKFLOW.md`](docs/PLANNER_WORKFLOW.md).
4. Operate through `python -m planner.cli`.

## Expectations

- Keep real user state in `workspace/` or another untracked local workspace.
- Do not hardcode absolute home-directory paths.
- Do not assume macOS calendar access exists.
- Preserve the fixed daily report contract.
- If asked to create a local Claude Code overlay, use [`docs/MAKE_LOCAL_CLAUDE_CODE_SETUP.md`](docs/MAKE_LOCAL_CLAUDE_CODE_SETUP.md).
- If asked to create a local Codex skill from this repo, use [`docs/MAKE_LOCAL_CODEX_SKILL.md`](docs/MAKE_LOCAL_CODEX_SKILL.md).
- When generating long-period summaries, use the existing period-specific density:
  - month = weekly overview + daily review
  - quarter = weekly roadmap + weekly review
  - year = monthly milestones + monthly review
