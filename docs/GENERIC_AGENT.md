# Generic Agent Guide

This repo can be used with any local LLM workflow that can read files and run shell commands.

## Minimal instructions to give the model

1. Read `README.md` and `docs/ARCHITECTURE.md`.
2. Read `docs/PLANNER_WORKFLOW.md`.
3. Treat this repo as a local-first planner.
4. Prefer the CLI in `research-planner`.
5. Keep user state in a local workspace, not in tracked example data.
6. When asked to update progress:
   - parse the daily report
   - update the status log
   - refresh the dashboard
   - regenerate summaries only when requested

## Fixed daily report format

Use the template in:

- [`templates/blank_workspace/daily_report_template.md`](../templates/blank_workspace/daily_report_template.md)

## Suggested command flow

```bash
research-planner init --mode blank
research-planner prepare-report
research-planner ingest-report --input workspace/daily_reports/YYYY-MM-DD.md
research-planner replan --input workspace/daily_reports/YYYY-MM-DD.md
research-planner refresh
research-planner summary --period month --target 2026-03
```

## Optional local setup generation

- Codex local skill:
  - [`docs/MAKE_LOCAL_CODEX_SKILL.md`](./MAKE_LOCAL_CODEX_SKILL.md)
- Claude Code local setup:
  - [`docs/MAKE_LOCAL_CLAUDE_CODE_SETUP.md`](./MAKE_LOCAL_CLAUDE_CODE_SETUP.md)
