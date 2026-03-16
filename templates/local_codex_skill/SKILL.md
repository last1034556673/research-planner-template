---
name: "research-planner"
description: "Operate a cloned research-planner-template workspace when the user explicitly asks to prepare or ingest daily reports, update planner state, refresh the dashboard, inspect task status, or generate month, quarter, or year summaries. Use only for local research-planning operations, not for general scientific advice."
---

# Research Planner

This is a local Codex skill template for a cloned `research-planner-template` repository.

## Before using

Replace these placeholders in your local copy:

- `<REPO_ROOT>`
- `<WORKSPACE_PATH>`

Keep the filled-in copy local. Do not commit it back to the public repository.

## Read first

- `<REPO_ROOT>/README.md`
- `<REPO_ROOT>/docs/PLANNER_WORKFLOW.md`
- `<REPO_ROOT>/docs/ARCHITECTURE.md`
- `<REPO_ROOT>/docs/PRIVACY_BOUNDARY.md`

## Use when

- the user explicitly asks to update the planner
- the user wants to prepare or ingest a daily report
- the user wants to refresh the dashboard
- the user wants to inspect blocked or conditional tasks
- the user wants to generate month, quarter, or year summaries

## Do not use when

- the user is asking for general scientific explanation
- the user is discussing literature only
- the task is unrelated to the local planner workspace

## Core rules

- Keep real planner state in `<WORKSPACE_PATH>` or `<REPO_ROOT>/workspace`.
- Prefer `research-planner`.
- Preserve the fixed daily report contract.
- Keep the main dashboard short-window.
- Keep conditional tasks visible until their trigger is explicitly satisfied.
- Generate long-period summaries only when requested.
- Ask the minimum follow-up question only when a hard dependency is unclear.

## Useful commands

Prepare today's report:

```bash
research-planner --workspace "<WORKSPACE_PATH>" prepare-report
```

Ingest a saved report:

```bash
research-planner --workspace "<WORKSPACE_PATH>" ingest-report --input "<REPORT_PATH>"
```

Refresh the dashboard:

```bash
research-planner --workspace "<WORKSPACE_PATH>" refresh
```

Generate a summary:

```bash
research-planner --workspace "<WORKSPACE_PATH>" summary --period month --target 2026-03
```
