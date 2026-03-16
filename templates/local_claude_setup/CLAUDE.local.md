# CLAUDE.local.md

This is a local template for using Claude Code with a cloned `research-planner-template` repository.

## Before using

Replace these placeholders in your local copy:

- `<REPO_ROOT>`
- `<WORKSPACE_PATH>`

Keep the filled-in copy local. Do not commit it back to the public repository.

## Read first

1. `<REPO_ROOT>/README.md`
2. `<REPO_ROOT>/docs/PLANNER_WORKFLOW.md`
3. `<REPO_ROOT>/docs/ARCHITECTURE.md`
4. `<REPO_ROOT>/docs/PRIVACY_BOUNDARY.md`

## Operating rules

- Treat this repo as a local-first planner.
- Keep real state in `<WORKSPACE_PATH>` or `<REPO_ROOT>/workspace`.
- Prefer `research-planner`.
- Preserve the fixed daily report contract.
- Refresh summaries only when requested.
- Keep the main dashboard short-window.
- Respect the period-specific summary density:
  - month = weekly overview + daily review
  - quarter = weekly roadmap + weekly review
  - year = monthly milestones + monthly review

## Useful commands

```bash
research-planner --workspace "<WORKSPACE_PATH>" prepare-report
research-planner --workspace "<WORKSPACE_PATH>" ingest-report --input "<REPORT_PATH>"
research-planner --workspace "<WORKSPACE_PATH>" refresh
research-planner --workspace "<WORKSPACE_PATH>" summary --period month --target 2026-03
```
