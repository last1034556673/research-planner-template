from __future__ import annotations

import argparse
import datetime as dt
import json
import shutil
import subprocess
import sys
from pathlib import Path
from zoneinfo import ZoneInfo

from .config import integration_settings, load_configs
from .workspace import build_paths, ensure_workspace_dirs, repo_root


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Research planner template CLI.")
    parser.add_argument("--workspace", help="Workspace directory. Defaults to ./workspace", default=None)
    subparsers = parser.add_subparsers(dest="command", required=True)

    init_parser = subparsers.add_parser("init", help="Initialize a local workspace from blank or demo template.")
    init_parser.add_argument("--mode", choices=("blank", "demo"), required=True)
    init_parser.add_argument("--force", action="store_true", help="Replace an existing workspace.")

    ingest_parser = subparsers.add_parser("ingest-report", help="Parse a saved daily report and refresh outputs.")
    ingest_parser.add_argument("--input", required=True, help="Path to a saved daily report.")

    subparsers.add_parser("prepare-report", help="Create today's report from the template.")
    subparsers.add_parser("refresh", help="Refresh the main dashboard HTML.")

    summary_parser = subparsers.add_parser("summary", help="Generate a history summary HTML.")
    summary_parser.add_argument("--period", choices=("month", "quarter", "year"), required=True)
    summary_parser.add_argument("--target", help="Target period like 2026-03, 2026-Q1 or 2026.")

    subparsers.add_parser("doctor", help="Check workspace configuration and optional integrations.")
    return parser.parse_args()


def copy_template(source: Path, target: Path, force: bool) -> None:
    if target.exists():
        if not force:
            raise SystemExit(f"Workspace already exists: {target}")
        shutil.rmtree(target)
    shutil.copytree(source, target)


def run_module(module: str, args: list[str]) -> None:
    subprocess.run([sys.executable, "-m", module, *args], check=True)


def today_iso(tz_name: str) -> str:
    return dt.datetime.now(dt.timezone.utc).astimezone(ZoneInfo(tz_name)).date().isoformat()


def prepare_report(paths, project_config: dict[str, str]) -> Path:
    ensure_workspace_dirs(paths)
    today = dt.datetime.now(dt.timezone.utc).astimezone(ZoneInfo(project_config["timezone"])).date().isoformat()
    target = paths.daily_reports_dir / f"{today}.md"
    if not target.exists():
        text = paths.report_template.read_text(encoding="utf-8")
        text = text.replace("Date: YYYY-MM-DD", f"Date: {today}", 1)
        text = text.replace("日期：YYYY-MM-DD", f"日期：{today}", 1)
        target.write_text(text, encoding="utf-8")
    print(target)
    return target


def refresh_dashboard(paths, configs: dict[str, dict]) -> Path:
    ensure_workspace_dirs(paths)
    integrations = integration_settings(paths, configs)
    project = configs["project"]
    today = dt.datetime.now(dt.timezone.utc).astimezone(ZoneInfo(project["timezone"])).date()
    start = today - dt.timedelta(days=7)
    args = [
        "--calendar",
        integrations["primary_calendar_name"],
        "--calendar-provider",
        integrations["calendar_provider"],
        "--events-file",
        str(integrations["event_source_path"]),
        "--calendar-script",
        str(integrations["calendar_script"]),
        "--details-file",
        str(paths.plan_details),
        "--status-file",
        str(paths.status_log),
        "--project-name",
        project["project_name"],
        "--time-zone",
        project["timezone"],
        "--sync-deadline",
        project["sync_deadline"],
        "--days",
        str(project["dashboard_window_days"]),
        "--start-date",
        start.isoformat(),
        "--include-past",
        "--output",
        str(paths.dashboard_output),
        "--streams-json",
        json.dumps(configs["workstreams"].get("streams", []), ensure_ascii=False),
    ]
    run_module("planner.dashboard", args)
    return paths.dashboard_output


def ingest_report(paths, configs: dict[str, dict], input_path: Path) -> None:
    integrations = integration_settings(paths, configs)
    project = configs["project"]
    args = [
        "--input",
        str(input_path),
        "--calendar",
        integrations["primary_calendar_name"],
        "--calendar-provider",
        integrations["calendar_provider"],
        "--events-file",
        str(integrations["event_source_path"]),
        "--calendar-script",
        str(integrations["calendar_script"]),
        "--status-file",
        str(paths.status_log),
        "--history-dir",
        str(paths.history_dir),
        "--time-zone",
        project["timezone"],
        "--sync-deadline",
        project["sync_deadline"],
        "--write-status-log",
        "--write-history",
    ]
    run_module("planner.report_parser", args)
    refresh_dashboard(paths, configs)


def generate_summary(paths, configs: dict[str, dict], period: str, target: str | None) -> Path:
    project = configs["project"]
    args = [
        "--period",
        period,
        "--history-dir",
        str(paths.history_dir),
        "--time-zone",
        project["timezone"],
    ]
    if target:
        args.extend(["--target", target])
    output_path = paths.history_summaries_dir / f"{target or period}.html"
    args.extend(["--output", str(output_path)])
    run_module("planner.history_summary", args)
    return output_path


def doctor(paths, configs: dict[str, dict]) -> None:
    integrations = integration_settings(paths, configs)
    report = {
        "workspace": str(paths.root),
        "project_name": configs["project"]["project_name"],
        "timezone": configs["project"]["timezone"],
        "calendar_provider": integrations["calendar_provider"],
        "primary_calendar_name": integrations["primary_calendar_name"],
        "plan_details_exists": paths.plan_details.exists(),
        "status_log_exists": paths.status_log.exists(),
        "report_template_exists": paths.report_template.exists(),
        "events_file_exists": integrations["event_source_path"].exists(),
        "macos_script_exists": integrations["calendar_script"].exists(),
    }
    print(json.dumps(report, indent=2, ensure_ascii=False))


def main() -> int:
    args = parse_args()
    paths = build_paths(args.workspace)
    configs = load_configs(paths) if paths.root.exists() else None

    if args.command == "init":
        source = repo_root() / ("templates/blank_workspace" if args.mode == "blank" else "examples/wetlab_demo/workspace_seed")
        copy_template(source, paths.root, args.force)
        print(paths.root)
        return 0

    if configs is None:
        raise SystemExit(f"Workspace not found: {paths.root}. Run `python -m planner.cli init --mode blank` first.")

    if args.command == "prepare-report":
        prepare_report(paths, configs["project"])
        return 0

    if args.command == "refresh":
        print(refresh_dashboard(paths, configs))
        return 0

    if args.command == "ingest-report":
        ingest_report(paths, configs, Path(args.input).expanduser().resolve())
        return 0

    if args.command == "summary":
        print(generate_summary(paths, configs, args.period, args.target))
        return 0

    if args.command == "doctor":
        doctor(paths, configs)
        return 0

    raise SystemExit(f"Unknown command: {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())
