# AGENTS.md

This repository is a local-first research planning template. Use the repo itself as the source of truth; do not assume hidden local setup.

## Default workflow

1. Read [`README.md`](README.md) and [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).
2. Read [`docs/PLANNER_WORKFLOW.md`](docs/PLANNER_WORKFLOW.md) before changing planner state or generating a local skill.
3. Work inside a local workspace, not inside the tracked demo unless the user explicitly wants the demo.
4. Prefer the Python CLI:
   - `python -m planner.cli init --mode blank|demo`
   - `python -m planner.cli prepare-report`
   - `python -m planner.cli ingest-report --input <path>`
   - `python -m planner.cli refresh`
   - `python -m planner.cli summary --period month|quarter|year --target <value>`
   - `python -m planner.cli doctor`
5. Treat `workspace/` as private local state.

## Rules

- Do not commit or overwrite real user history unless explicitly asked.
- Prefer file-based event input unless the user explicitly enables macOS integration.
- Keep the fixed daily report format intact.
- If a task changes long-window summaries, keep the main dashboard lightweight.

## Key files

- Core package: [`planner/`](planner/)
- Blank starter: [`templates/blank_workspace/`](templates/blank_workspace/)
- Demo seed: [`examples/wetlab_demo/workspace_seed/`](examples/wetlab_demo/workspace_seed/)
- Shared workflow rules: [`docs/PLANNER_WORKFLOW.md`](docs/PLANNER_WORKFLOW.md)
- Local Codex skill guide: [`docs/MAKE_LOCAL_CODEX_SKILL.md`](docs/MAKE_LOCAL_CODEX_SKILL.md)
- Privacy rules: [`docs/PRIVACY_BOUNDARY.md`](docs/PRIVACY_BOUNDARY.md)
