# Quickstart

## 1. Install

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

## 2. Create a workspace

Blank workspace:

```bash
python -m planner.cli init --mode blank
```

Demo workspace:

```bash
python -m planner.cli init --mode demo --workspace ./workspace_demo
```

## 3. Prepare today's report

```bash
python -m planner.cli prepare-report
```

This creates `workspace/daily_reports/YYYY-MM-DD.md` from the fixed template.

## 4. Refresh the dashboard

```bash
python -m planner.cli refresh
```

Output:

- `workspace/outputs/future_experiment_schedule.html`

## 5. Ingest a completed report

```bash
python -m planner.cli ingest-report --input workspace/daily_reports/YYYY-MM-DD.md
```

This updates:

- `workspace/data/status_log.json`
- `workspace/history/daily/*.json`
- `workspace/history/events.jsonl`
- `workspace/outputs/future_experiment_schedule.html`

## 6. Generate summaries

```bash
python -m planner.cli summary --period month --target 2026-03
python -m planner.cli summary --period quarter --target 2026-Q1
python -m planner.cli summary --period year --target 2026
```

## 7. Verify setup

```bash
python -m planner.cli doctor
```
