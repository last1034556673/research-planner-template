# Make a Local Codex Skill

Use this guide when you want Codex, or another model acting on your behalf, to create a local Codex skill for a cloned copy of this repository.

## Goal

Create a thin local skill that points back to this repo's workflow docs and local workspace.

Recommended local target:

- `$CODEX_HOME/skills/research-planner/SKILL.md`
- `$CODEX_HOME/skills/research-planner/agents/openai.yaml`

## What the model should read first

- [`README.md`](../README.md)
- [`docs/PLANNER_WORKFLOW.md`](./PLANNER_WORKFLOW.md)
- [`docs/ARCHITECTURE.md`](./ARCHITECTURE.md)
- [`docs/PRIVACY_BOUNDARY.md`](./PRIVACY_BOUNDARY.md)

## What the generated local skill should do

- operate a local workspace for this repo
- prefer `python -m planner.cli`
- preserve the fixed daily report contract
- update status and refresh the dashboard
- generate long-period summaries only when requested
- avoid unnecessary questions

## What the generated local skill must not contain

- another person's home-directory path
- personal names from the public demo creator
- real private calendar names from tracked files
- copied real history from a user workspace
- hardcoded assumptions that macOS integrations always exist

## Template

Start from:

- [`templates/local_codex_skill/SKILL.md`](../templates/local_codex_skill/SKILL.md)
- [`templates/local_codex_skill/agents/openai.yaml`](../templates/local_codex_skill/agents/openai.yaml)

Replace the placeholders:

- `<REPO_ROOT>`
- `<WORKSPACE_PATH>`

Keep the generated copy local. Do not commit the filled-in copy back to the public repository.

## Suggested prompt

```text
Read README.md, docs/PLANNER_WORKFLOW.md, docs/ARCHITECTURE.md, and docs/PRIVACY_BOUNDARY.md. Then create a local Codex skill named research-planner for this cloned repo by copying templates/local_codex_skill/, replacing <REPO_ROOT> and <WORKSPACE_PATH>, and keeping the result outside the tracked repository.
```

