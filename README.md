# Research Planner Template

Research Planner Template is a local-first planning system for wet-lab and experiment-heavy research work. It combines a short-window execution dashboard, fixed-format daily reports, rolling status logs, and history summaries without requiring any cloud backend.

This public template is cross-platform at the core. macOS calendar sync is optional and isolated under [`integrations/macos`](integrations/macos).

## What It Does

- Maintains a rolling dashboard for the past week, today, and the next week.
- Parses a fixed daily report format and converts it into status updates.
- Archives history snapshots as JSON plus `events.jsonl`.
- Generates period-specific history summaries:
  - Month: weekly overview + daily review
  - Quarter: weekly roadmap + weekly review
  - Year: monthly milestones + monthly review
- Works in file-only mode by default.
- Optionally reads or cleans a macOS Calendar if you enable the macOS integration.

## Usage Tiers

1. Core planner only
   - File-based events, fixed daily reports, dashboard HTML.
2. Planner + history summaries
   - Adds monthly, quarterly, and yearly HTML summaries.
3. Planner + optional macOS calendar integration
   - Adds EventKit export and cleanup helpers on macOS.

## Repository Layout

- [`planner/`](planner/)
  - Reusable Python package and CLI.
- [`templates/blank_workspace/`](templates/blank_workspace/)
  - Blank starter workspace.
- [`examples/wetlab_demo/`](examples/wetlab_demo/)
  - Anonymized wet-lab demo workspace and tracked sample outputs.
- [`integrations/macos/`](integrations/macos/)
  - Optional macOS-only helpers.
- [`docs/`](docs/)
  - Quickstart, architecture, privacy, and model-specific guidance.

## Quick Start

Requirements:

- Python 3.10+
- `PyYAML`

From a fresh clone:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
python -m planner.cli init --mode blank
python -m planner.cli prepare-report
python -m planner.cli refresh
```

The default local workspace is `./workspace`, which is ignored by git.

## Demo Workspace

The anonymized demo lives in [`examples/wetlab_demo/workspace_seed/`](examples/wetlab_demo/workspace_seed/). It already contains:

- synthetic plan details
- synthetic status log
- synthetic calendar events
- sample daily reports
- tracked history snapshots

You can inspect the prebuilt demo outputs here:

- [`dashboard.html`](examples/wetlab_demo/sample_outputs/dashboard.html)
- [`history-month.html`](examples/wetlab_demo/sample_outputs/history-month.html)
- [`history-quarter.html`](examples/wetlab_demo/sample_outputs/history-quarter.html)
- [`history-year.html`](examples/wetlab_demo/sample_outputs/history-year.html)

## Screenshots

- Dashboard
  - ![dashboard screenshot](assets/screenshots/dashboard.png)
- Monthly history
  - ![month summary screenshot](assets/screenshots/history-month.png)

## CLI

```bash
python -m planner.cli init --mode blank|demo
python -m planner.cli prepare-report
python -m planner.cli ingest-report --input <path>
python -m planner.cli refresh
python -m planner.cli summary --period month|quarter|year --target <value>
python -m planner.cli doctor
```

## Agent Support

This repository does not require a Codex skill to work. The repo itself ships instructions for multiple model frontends:

- [`AGENTS.md`](AGENTS.md) for Codex
- [`CLAUDE.md`](CLAUDE.md) for Claude
- [`docs/GENERIC_AGENT.md`](docs/GENERIC_AGENT.md) for MiniMax and other local LLM workflows

## Documentation

- [`docs/QUICKSTART.md`](docs/QUICKSTART.md)
- [`docs/MACOS_OPTIONAL.md`](docs/MACOS_OPTIONAL.md)
- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md)
- [`docs/PRIVACY_BOUNDARY.md`](docs/PRIVACY_BOUNDARY.md)
- [`README.zh-CN.md`](README.zh-CN.md)

## License

MIT. See [`LICENSE`](LICENSE).
