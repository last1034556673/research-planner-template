from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class WorkspacePaths:
    repo_root: Path
    root: Path
    config_dir: Path
    data_dir: Path
    daily_reports_dir: Path
    history_dir: Path
    history_daily_dir: Path
    history_summaries_dir: Path
    outputs_dir: Path
    replan_suggestions_dir: Path
    project_config: Path
    constraints_config: Path
    integrations_config: Path
    workstreams_config: Path
    report_template: Path
    plan_details: Path
    status_log: Path
    calendar_events: Path
    dashboard_output: Path


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def build_paths(workspace_root: Path | str | None = None) -> WorkspacePaths:
    root_path = Path(workspace_root).expanduser().resolve() if workspace_root else repo_root() / "workspace"
    config_dir = root_path / "config"
    data_dir = root_path / "data"
    history_dir = root_path / "history"
    outputs_dir = root_path / "outputs"
    replan_suggestions_dir = outputs_dir / "replan_suggestions"
    return WorkspacePaths(
        repo_root=repo_root(),
        root=root_path,
        config_dir=config_dir,
        data_dir=data_dir,
        daily_reports_dir=root_path / "daily_reports",
        history_dir=history_dir,
        history_daily_dir=history_dir / "daily",
        history_summaries_dir=history_dir / "summaries",
        outputs_dir=outputs_dir,
        replan_suggestions_dir=replan_suggestions_dir,
        project_config=config_dir / "project.yaml",
        constraints_config=config_dir / "constraints.yaml",
        integrations_config=config_dir / "integrations.yaml",
        workstreams_config=config_dir / "workstreams.yaml",
        report_template=root_path / "daily_report_template.md",
        plan_details=data_dir / "plan_details.json",
        status_log=data_dir / "status_log.json",
        calendar_events=data_dir / "calendar_events.json",
        dashboard_output=outputs_dir / "future_experiment_schedule.html",
    )


def ensure_workspace_dirs(paths: WorkspacePaths) -> None:
    for path in (
        paths.root,
        paths.config_dir,
        paths.data_dir,
        paths.daily_reports_dir,
        paths.history_dir,
        paths.history_daily_dir,
        paths.history_summaries_dir,
        paths.outputs_dir,
        paths.replan_suggestions_dir,
    ):
        path.mkdir(parents=True, exist_ok=True)
