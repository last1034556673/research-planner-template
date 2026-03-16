# Generic Agent Guide

This repo can be used with any local LLM workflow that can read files and run shell commands.

## Minimal instructions to give the model

1. Read `README.md` and `docs/ARCHITECTURE.md`.
2. Treat this repo as a local-first planner.
3. Prefer the CLI in `python -m planner.cli`.
4. Keep user state in a local workspace, not in tracked example data.
5. When asked to update progress:
   - parse the daily report
   - update the status log
   - refresh the dashboard
   - regenerate summaries only when requested

## Fixed daily report format

Use the template in:

- [`templates/blank_workspace/daily_report_template.md`](../templates/blank_workspace/daily_report_template.md)

## Suggested command flow

```bash
python -m planner.cli init --mode blank
python -m planner.cli prepare-report
python -m planner.cli ingest-report --input workspace/daily_reports/YYYY-MM-DD.md
python -m planner.cli refresh
python -m planner.cli summary --period month --target 2026-03
```
