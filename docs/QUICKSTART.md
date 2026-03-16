# Quickstart

## 1. Install

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

For local development and tests:

```bash
pip install -e '.[dev]'
python -m pytest
```

## 2. Create a workspace

Blank workspace:

```bash
research-planner init --mode blank
```

Demo workspace:

```bash
research-planner --workspace ./workspace_demo init --mode demo
```

`--workspace` works both before and after the subcommand.

## 3. Prepare today's report

```bash
research-planner prepare-report
```

This creates `workspace/daily_reports/YYYY-MM-DD.md` from the fixed template.

## 4. Refresh the dashboard

```bash
research-planner refresh
```

Output:

- `workspace/outputs/future_experiment_schedule.html`

## 5. Ingest a completed report

```bash
research-planner ingest-report --input workspace/daily_reports/YYYY-MM-DD.md
research-planner replan --input workspace/daily_reports/YYYY-MM-DD.md
```

This updates:

- `workspace/data/status_log.json`
- `workspace/history/daily/*.json`
- `workspace/history/events.jsonl`
- `workspace/outputs/future_experiment_schedule.html`

## 6. Generate summaries

```bash
research-planner summary --period month --target 2026-03
research-planner summary --period quarter --target 2026-Q1
research-planner summary --period year --target 2026
```

## 7. Verify setup

```bash
research-planner doctor
research-planner doctor --json
```
