# Make a Local Claude Code Setup

Use this guide when you want Claude Code to generate a local planner setup for a cloned copy of this repository.

Claude Code does not require a Codex-style `SKILL.md`, so the preferred local target is a small local overlay file such as:

- `CLAUDE.local.md` in the cloned repo

If the user also wants a Codex-compatible skill, Claude Code can generate that too by following:

- [`docs/MAKE_LOCAL_CODEX_SKILL.md`](./MAKE_LOCAL_CODEX_SKILL.md)

## What Claude Code should read first

- [`README.md`](../README.md)
- [`docs/PLANNER_WORKFLOW.md`](./PLANNER_WORKFLOW.md)
- [`docs/ARCHITECTURE.md`](./ARCHITECTURE.md)
- [`docs/PRIVACY_BOUNDARY.md`](./PRIVACY_BOUNDARY.md)

## Preferred local target

Start from:

- [`templates/local_claude_setup/CLAUDE.local.md`](../templates/local_claude_setup/CLAUDE.local.md)

Replace:

- `<REPO_ROOT>`
- `<WORKSPACE_PATH>`

## What the local Claude Code setup should do

- operate this repo as a local-first planner
- use `python -m planner.cli` as the main interface
- keep real user state in a local workspace
- keep the fixed daily report format intact
- respect period-specific summary density

## Privacy rule

The generated local setup may include the current user's own local repo path, but it must not copy another person's path, name, calendar label, or private research records from the public repo history.

## Suggested prompt

```text
Read README.md, docs/PLANNER_WORKFLOW.md, docs/ARCHITECTURE.md, and docs/PRIVACY_BOUNDARY.md. Then create a local CLAUDE.local.md for this cloned repo by adapting templates/local_claude_setup/CLAUDE.local.md, replacing <REPO_ROOT> and <WORKSPACE_PATH>, and keeping the file local to this clone.
```

