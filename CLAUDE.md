# CLAUDE.md

Use this repository as a self-contained local-first planning system for wet-lab and experiment-heavy research work.

## Recommended reading order

1. [`README.md`](README.md) — project overview and quick start
2. [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) — data flow, package layout, workspace model
3. [`docs/PLANNER_WORKFLOW.md`](docs/PLANNER_WORKFLOW.md) — operational rules, daily report contract, status system
4. [`docs/PRIVACY_BOUNDARY.md`](docs/PRIVACY_BOUNDARY.md) — what is tracked vs untracked

## Repository structure

```
research-planner-template/
├── planner/                  # Core Python package (13 modules, ~4,750 LOC)
│   ├── cli.py                #   CLI entrypoint and command routing
│   ├── config.py             #   YAML config loading and merging
│   ├── workspace.py          #   WorkspacePaths dataclass, directory creation
│   ├── dashboard.py          #   15-day HTML dashboard renderer
│   ├── report_parser.py      #   Fixed daily report parser, status inference
│   ├── history.py            #   Archive daily reports → JSON + events.jsonl
│   ├── history_summary.py    #   Month/quarter/year HTML summaries
│   ├── replan.py             #   Schedule change suggestions and application
│   ├── calendar_io.py        #   Load events from file / macOS / ICS
│   ├── validate.py           #   Config and data validation against schemas
│   ├── planner_data.py       #   Data normalization, task/event ID matching
│   └── demo_assets.py        #   Demo sample output generation
├── schemas/                  # JSON Schema definitions (7 schemas)
├── templates/
│   ├── blank_workspace/      #   Starter workspace template (config + data + report template)
│   ├── local_claude_setup/   #   CLAUDE.local.md overlay template
│   └── local_codex_skill/    #   Codex skill template (SKILL.md + agents/openai.yaml)
├── examples/
│   └── wetlab_demo/          #   Anonymized wet-lab demo with synthetic data
│       ├── workspace_seed/   #     Tracked demo workspace (config, data, reports, history)
│       └── sample_outputs/   #     Pre-generated HTML dashboards and summaries
├── integrations/
│   └── macos/                #   Optional macOS Calendar integration (Swift + AppleScript)
├── docs/                     # Documentation (8 guides)
├── tests/                    # Unit tests (cli, replan, report_parser, validate)
├── pyproject.toml            # Python 3.10+, PyYAML>=6.0, entry point: research-planner
├── AGENTS.md                 # Instructions for Codex and other LLM agents
└── .gitignore                # Excludes workspace/, outputs, reports, history
```

## CLI commands

All commands accept `--workspace <path>` (defaults to `workspace/`).

```bash
research-planner init --mode blank|demo [--force] [--guided] [--no-input]
research-planner prepare-report
research-planner ingest-report --input <path> [--replan off|suggest|apply]
research-planner replan --input <path> [--apply] [--output <path>]
research-planner refresh
research-planner summary --period month|quarter|year --target <value>
research-planner doctor [--json]
research-planner refresh-demo-assets [--skip-screenshots]
```

## Daily update loop

1. `research-planner prepare-report` — scaffold today's report
2. User fills the report (fixed four-part format below)
3. `research-planner ingest-report --input <path>` — parse and archive
4. `research-planner refresh` — regenerate dashboard
5. `research-planner summary --period <p> --target <v>` — only when requested

## Fixed daily report contract

The planner expects a four-section report (see `templates/blank_workspace/daily_report_template.md`):

1. **Experiment Execution** — completed / not completed / reasons
2. **Key Status** — cells / animals / instruments & reagents
3. **Data Analysis and Writing**
4. **Tomorrow Must Do**

Free-form text is fallback only. Preserve this format.

## Data flow

```
Daily Report (.md) → report_parser → status_log.json + history/daily/YYYY-MM-DD.json
                                                        ↓
                                              history/events.jsonl → history_summary (HTML)
                                                        ↓
Calendar Events (file/macOS/ICS) + plan_details.json → dashboard (HTML)
```

## Workspace model

**Tracked** (safe to read and reference):
- `templates/blank_workspace/` — starter config and data
- `examples/wetlab_demo/workspace_seed/` — synthetic demo data

**Untracked** (real user state, never commit):
- `workspace/` or any user-specified workspace path
- Generated dashboards, reports, history, and outputs

### Workspace layout

```
workspace/
├── config/          # project.yaml, constraints.yaml, integrations.yaml, workstreams.yaml
├── data/            # plan_details.json, status_log.json, calendar_events.json
├── daily_reports/   # YYYY-MM-DD.md
├── history/
│   ├── daily/       # YYYY-MM-DD.json snapshots
│   ├── events.jsonl # Event-level archive
│   └── summaries/   # YYYY-MM.html, YYYY-Q#.html, YYYY.html
└── outputs/
    ├── future_experiment_schedule.html
    └── replan_suggestions/
```

## Status system

Precedence: explicit user feedback > explicit moved/incomplete > automatic inference.

Statuses: `Completed`, `Partially Done`, `Incomplete`, `Moved`, `Pending Sync`, `Unsynced`, `Conditional`, `Planned`.

Timing: after a planned task ends and before the next-day sync deadline → `Pending Sync`; after deadline → `Unsynced`. Deadline is set in `config/project.yaml` (default `09:30` in `Asia/Shanghai`).

## Summary density rules

Do not reuse the day-level dashboard for long-period history. Use period-specific density:

- **month** = weekly overview + daily review
- **quarter** = weekly roadmap + weekly review
- **year** = monthly milestones + monthly review

## Key conventions and rules

- Keep real user state in `workspace/` or another untracked path. Never commit it.
- Do not hardcode absolute home-directory paths.
- Do not assume macOS calendar access exists — prefer file-based event input unless the user explicitly enables macOS integration.
- Preserve the fixed daily report format intact.
- Keep the main dashboard short-window only (15 days). Long-period views go in summaries.
- Preserve conditional tasks as conditional until the triggering condition is explicitly satisfied.
- Update downstream tasks only when the report changes a real dependency (sample readiness, animal/instrument availability, hard timepoints, blocked days, meeting constraints).
- Do not place personal names, private calendar names, real experiment identifiers, or real home-directory paths into tracked files.
- If asked to create a local Claude Code overlay, use [`docs/MAKE_LOCAL_CLAUDE_CODE_SETUP.md`](docs/MAKE_LOCAL_CLAUDE_CODE_SETUP.md).
- If asked to create a local Codex skill, use [`docs/MAKE_LOCAL_CODEX_SKILL.md`](docs/MAKE_LOCAL_CODEX_SKILL.md).

## Development

- **Python**: ≥ 3.10
- **Dependencies**: `PyYAML>=6.0` (core), `pytest>=8.0` (dev), `icalendar>=5.0` (optional ICS)
- **Install**: `pip install -e .` or `pip install -e ".[dev]"`
- **Tests**: `pytest tests/`
- **Schemas**: all data structures are validated against JSON Schemas in `schemas/`
- **Version**: 1.1.0 (set in `pyproject.toml` and `planner/__init__.py`)
