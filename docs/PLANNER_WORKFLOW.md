# Planner Workflow

This document is the shared operational core for local agent setups built on top of this repository.

Use it when you want an AI assistant to:

- prepare or ingest a daily report
- update planner state
- refresh the short-window dashboard
- regenerate month, quarter, or year summaries
- create a local Codex skill or Claude Code overlay for this repo

## Source of truth

Read these first:

- [`README.md`](../README.md)
- [`docs/ARCHITECTURE.md`](./ARCHITECTURE.md)
- [`docs/PRIVACY_BOUNDARY.md`](./PRIVACY_BOUNDARY.md)

Then read the local workspace state as needed:

- `workspace/data/plan_details.json`
- `workspace/data/status_log.json`
- `workspace/history/daily/*.json`
- `workspace/history/events.jsonl`

## Fixed daily report contract

The planner expects a fixed four-part daily report:

1. `Experiment Execution`
   - completed
   - not completed
   - reason
2. `Key Status`
   - cells
   - animals
   - instruments / reagents
3. `Data Analysis and Writing`
4. `Tomorrow Must Do`

Use the template in:

- [`templates/blank_workspace/daily_report_template.md`](../templates/blank_workspace/daily_report_template.md)

Free-form text is fallback only.

## Default update loop

1. Prepare today's report:
   - `python -m planner.cli prepare-report`
2. Fill the report.
3. Ingest it:
   - `python -m planner.cli ingest-report --input <report>`
4. Refresh the dashboard:
   - `python -m planner.cli refresh`
5. Generate summaries only when requested:
   - `python -m planner.cli summary --period month|quarter|year --target <value>`

## Status rules

Status precedence:

1. explicit user feedback
2. explicit moved / incomplete records
3. automatic inference

Default human-facing status set:

- `Completed`
- `Partially Done`
- `Incomplete`
- `Moved`
- `Pending Sync`
- `Unsynced`
- `Conditional`
- `Planned`

Timing rule:

- after a planned task ends and before the next-day sync deadline: `Pending Sync`
- after the next-day sync deadline: `Unsynced`

The deadline comes from `config/project.yaml`. The starter templates use `09:30` in `Asia/Shanghai`.

## Replanning rules

- Keep the main dashboard short-window only.
- Preserve conditional tasks as conditional until the triggering condition is explicitly satisfied.
- Update downstream tasks only when the report changes a real dependency:
  - sample or culture readiness
  - animal availability
  - instrument availability
  - hard timepoint assays
  - blocked lab days
  - recurring meeting constraints
- Ask the minimum follow-up question only when the missing detail would materially change a hard dependency.

## Summary rules

Do not reuse the day-level real-time dashboard for long-period history.

Use period-specific density:

- month = weekly overview + daily review
- quarter = weekly roadmap + weekly review
- year = monthly milestones + monthly review

## Privacy rules for local agent setup

- Keep real planner state in a local workspace, not in tracked demo files.
- Do not commit generated local history, dashboards, or daily reports.
- Do not place personal names, private calendar names, real experiment identifiers, or another user's home-directory path into tracked files.
- If generating a local skill or local agent config, keep private paths in the local generated copy only, never in the public repo template.

