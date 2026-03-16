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


def normalize_cli_argv(argv: list[str]) -> list[str]:
    workspace_args: list[str] = []
    remaining: list[str] = []
    index = 0
    while index < len(argv):
        token = argv[index]
        if token == "--workspace":
            workspace_args.append(token)
            if index + 1 >= len(argv):
                raise SystemExit("Missing value after --workspace.")
            workspace_args.append(argv[index + 1])
            index += 2
            continue
        if token.startswith("--workspace="):
            workspace_args.append(token)
            index += 1
            continue
        remaining.append(token)
        index += 1

    if not workspace_args:
        return argv

    insert_at = 0
    while insert_at < len(remaining) and remaining[insert_at].startswith("-"):
        insert_at += 1
    return remaining[:insert_at] + workspace_args + remaining[insert_at:]


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Research planner template CLI.",
        epilog="Global options such as --workspace may appear before or after the subcommand.",
    )
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
    return parser.parse_args(normalize_cli_argv(list(sys.argv[1:] if argv is None else argv)))


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


def template_sources() -> dict[str, Path]:
    root = repo_root()
    return {
        "blank": root / "templates" / "blank_workspace",
        "demo": root / "examples" / "wetlab_demo" / "workspace_seed",
    }


def _doctor_line(level: str, title: str, detail: str, fix: str | None = None) -> str:
    lines = [f"[{level}] {title}", f"      {detail}"]
    if fix:
        lines.append(f"      Next: {fix}")
    return "\n".join(lines)


def doctor(paths) -> int:
    configs = load_configs(paths)
    integrations = integration_settings(paths, configs)
    sources = template_sources()
    errors = 0
    warnings = 0
    lines = [
        f"Workspace: {paths.root}",
        f"Project name: {configs['project']['project_name']}",
        f"Time zone: {configs['project']['timezone']}",
        f"Calendar provider: {integrations['calendar_provider']}",
        f"Primary calendar: {integrations['primary_calendar_name']}",
        "",
    ]

    for label, source in sources.items():
        if source.exists():
            lines.append(_doctor_line("OK", f"{label.capitalize()} source is available", str(source)))
        else:
            errors += 1
            lines.append(
                _doctor_line(
                    "ERROR",
                    f"{label.capitalize()} source is missing",
                    f"The repo is missing {source}. `{label}` init will fail.",
                    "Restore the tracked template files in this repository before using init.",
                )
            )

    if not paths.root.exists():
        errors += 1
        lines.append(
            _doctor_line(
                "ERROR",
                "Workspace root is missing",
                "The selected workspace has not been initialized yet.",
                "Run `python -m planner.cli init --mode blank` or `python -m planner.cli --workspace ./workspace_demo init --mode demo`.",
            )
        )
        warnings += 1
        lines.append(
            _doctor_line(
                "WARN",
                "Detailed workspace checks were skipped",
                "The workspace does not exist yet, so file-level checks would all fail for the same reason.",
                "Initialize the workspace first, then run `python -m planner.cli doctor` again for a full check.",
            )
        )
    else:
        lines.append(_doctor_line("OK", "Workspace root exists", str(paths.root)))
        required_files = [
            ("Project config", paths.project_config, "Copy the file from templates/blank_workspace/config/project.yaml or initialize a new workspace."),
            ("Constraints config", paths.constraints_config, "Copy the file from templates/blank_workspace/config/constraints.yaml or initialize a new workspace."),
            ("Integrations config", paths.integrations_config, "Copy the file from templates/blank_workspace/config/integrations.yaml or initialize a new workspace."),
            ("Workstreams config", paths.workstreams_config, "Copy the file from templates/blank_workspace/config/workstreams.yaml or initialize a new workspace."),
            ("Daily report template", paths.report_template, "Copy the file from templates/blank_workspace/daily_report_template.md or initialize a new workspace."),
            ("Plan details", paths.plan_details, "Restore data/plan_details.json from a starter template or recreate it before refreshing the dashboard."),
            ("Status log", paths.status_log, "Restore data/status_log.json from a starter template or recreate it before ingesting reports."),
        ]
        for label, path, fix in required_files:
            if path.exists():
                lines.append(_doctor_line("OK", label, str(path)))
            else:
                errors += 1
                lines.append(_doctor_line("ERROR", label, f"Missing required file: {path}", fix))

        if paths.daily_reports_dir.exists():
            lines.append(_doctor_line("OK", "Daily reports directory", str(paths.daily_reports_dir)))
        else:
            warnings += 1
            lines.append(
                _doctor_line(
                    "WARN",
                    "Daily reports directory is missing",
                    f"{paths.daily_reports_dir} does not exist yet.",
                    "Run `python -m planner.cli prepare-report` to recreate it automatically.",
                )
            )

        if paths.history_dir.exists():
            lines.append(_doctor_line("OK", "History directory", str(paths.history_dir)))
        else:
            warnings += 1
            lines.append(
                _doctor_line(
                    "WARN",
                    "History directory is missing",
                    f"{paths.history_dir} does not exist yet.",
                    "Run `python -m planner.cli ingest-report --input <report>` to recreate it automatically.",
                )
            )

        if paths.outputs_dir.exists():
            lines.append(_doctor_line("OK", "Outputs directory", str(paths.outputs_dir)))
        else:
            warnings += 1
            lines.append(
                _doctor_line(
                    "WARN",
                    "Outputs directory is missing",
                    f"{paths.outputs_dir} does not exist yet.",
                    "Run `python -m planner.cli refresh` to recreate it automatically.",
                )
            )

        if integrations["calendar_provider"] == "none":
            if integrations["event_source_path"].exists():
                lines.append(_doctor_line("OK", "File-based calendar source", str(integrations["event_source_path"])))
            else:
                warnings += 1
                lines.append(
                    _doctor_line(
                        "WARN",
                        "File-based calendar source is missing",
                        f"Planner events will load as an empty list without {integrations['event_source_path']}.",
                        "Create the JSON file with `[]` or restore data/calendar_events.json from a starter template.",
                    )
                )
        else:
            if integrations["calendar_script"].exists():
                lines.append(_doctor_line("OK", "macOS calendar export script", str(integrations["calendar_script"])))
            else:
                errors += 1
                lines.append(
                    _doctor_line(
                        "ERROR",
                        "macOS calendar export script is missing",
                        f"Expected {integrations['calendar_script']} for macOS calendar sync.",
                        "Restore integrations/macos/export_events.swift from the repository.",
                    )
                )
            warnings += 1
            lines.append(
                _doctor_line(
                    "WARN",
                    "macOS calendar access still needs user permission",
                    "Even with the script present, EventKit export can fail if Calendar access is denied.",
                    "Grant calendar permission to the terminal or app that runs the planner.",
                )
            )

    summary = f"Summary: {errors} error(s), {warnings} warning(s)"
    print("\n".join([summary, ""] + lines))
    return 1 if errors else 0


def main() -> int:
    args = parse_args()
    paths = build_paths(args.workspace)

    if args.command == "init":
        source = template_sources()["blank" if args.mode == "blank" else "demo"]
        if not source.exists():
            raise SystemExit(f"Missing init source: {source}")
        copy_template(source, paths.root, args.force)
        print(paths.root)
        return 0

    if args.command == "doctor":
        return doctor(paths)

    configs = load_configs(paths) if paths.root.exists() else None

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

    raise SystemExit(f"Unknown command: {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())
