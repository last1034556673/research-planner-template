from __future__ import annotations

import argparse
import datetime as dt
import json
import shutil
import subprocess
import sys
from pathlib import Path
from zoneinfo import ZoneInfo

import yaml

from .config import integration_settings, load_configs
from .planner_data import normalize_calendar_provider
from .validate import validate_workspace_files
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
    init_parser.add_argument("--guided", action="store_true", help="Prompt for project settings after creating the workspace.")
    init_parser.add_argument("--no-input", action="store_true", help="Skip prompts and use template defaults.")
    init_parser.add_argument("--project-name")
    init_parser.add_argument("--timezone")
    init_parser.add_argument("--locale")
    init_parser.add_argument("--primary-language")
    init_parser.add_argument("--calendar-provider", choices=("file", "none", "macos", "ics"))
    init_parser.add_argument("--primary-calendar-name")

    ingest_parser = subparsers.add_parser("ingest-report", help="Parse a saved daily report and refresh outputs.")
    ingest_parser.add_argument("--input", required=True, help="Path to a saved daily report.")
    ingest_parser.add_argument("--replan", choices=("off", "suggest", "apply"), default="off")

    replan_parser = subparsers.add_parser("replan", help="Suggest or apply schedule changes from a daily report.")
    replan_parser.add_argument("--input", required=True, help="Path to a saved daily report.")
    replan_parser.add_argument("--apply", action="store_true", help="Apply suggested changes to plan details and file-based calendar events.")
    replan_parser.add_argument("--output", help="Optional path for the suggestion JSON.")

    subparsers.add_parser("prepare-report", help="Create today's report from the template.")
    subparsers.add_parser("refresh", help="Refresh the main dashboard HTML.")

    summary_parser = subparsers.add_parser("summary", help="Generate a history summary HTML.")
    summary_parser.add_argument("--period", choices=("month", "quarter", "year"), required=True)
    summary_parser.add_argument("--target", help="Target period like 2026-03, 2026-Q1 or 2026.")

    doctor_parser = subparsers.add_parser("doctor", help="Check workspace configuration and optional integrations.")
    doctor_parser.add_argument("--json", action="store_true", help="Print machine-readable diagnostics.")

    refresh_demo = subparsers.add_parser("refresh-demo-assets", help="Regenerate demo sample outputs and optional screenshots.")
    refresh_demo.add_argument("--skip-screenshots", action="store_true", help="Only refresh HTML outputs.")
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


def prompt_value(label: str, default: str) -> str:
    response = input(f"{label} [{default}]: ").strip()
    return response or default


def should_prompt_for_init(mode: str, guided: bool, no_input: bool) -> bool:
    if no_input:
        return False
    if guided:
        return True
    return mode == "blank" and sys.stdin.isatty()


def update_yaml(path: Path, updates: dict[str, str]) -> None:
    payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    payload.update({key: value for key, value in updates.items() if value is not None})
    path.write_text(yaml.safe_dump(payload, sort_keys=False, allow_unicode=True), encoding="utf-8")


def configure_initialized_workspace(paths, args: argparse.Namespace) -> None:
    guided = should_prompt_for_init(args.mode, args.guided, args.no_input)
    project = yaml.safe_load(paths.project_config.read_text(encoding="utf-8")) or {}
    integrations = yaml.safe_load(paths.integrations_config.read_text(encoding="utf-8")) or {}

    project_name = args.project_name or project.get("project_name", "My Research Planner")
    timezone = args.timezone or project.get("timezone", "Asia/Shanghai")
    locale = args.locale or project.get("locale", "en_US")
    primary_language = args.primary_language or project.get("primary_language", "en")
    calendar_provider = normalize_calendar_provider(args.calendar_provider or integrations.get("calendar_provider", "file"))
    primary_calendar_name = args.primary_calendar_name or integrations.get("primary_calendar_name", "Research")

    if guided:
        project_name = prompt_value("Project name", project_name)
        timezone = prompt_value("Timezone", timezone)
        locale = prompt_value("Locale", locale)
        primary_language = prompt_value("Primary language", primary_language)
        calendar_provider = normalize_calendar_provider(prompt_value("Calendar provider (file/macos/ics)", calendar_provider))
        primary_calendar_name = prompt_value("Primary calendar name", primary_calendar_name)

    update_yaml(
        paths.project_config,
        {
            "project_name": project_name,
            "timezone": timezone,
            "locale": locale,
            "primary_language": primary_language,
        },
    )
    update_yaml(
        paths.integrations_config,
        {
            "calendar_provider": calendar_provider,
            "primary_calendar_name": primary_calendar_name,
        },
    )


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


def ingest_report(paths, configs: dict[str, dict], input_path: Path, replan_mode: str = "off") -> None:
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
    if replan_mode != "off":
        replan_args = [
            "--input",
            str(input_path),
            "--workspace-root",
            str(paths.root),
            "--calendar-provider",
            integrations["calendar_provider"],
            "--events-file",
            str(integrations["event_source_path"]),
        ]
        if replan_mode == "apply":
            replan_args.append("--apply")
        run_module("planner.replan", replan_args)
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


def doctor_report(paths) -> dict[str, object]:
    configs = load_configs(paths)
    integrations = integration_settings(paths, configs)
    sources = template_sources()
    errors = 0
    warnings = 0
    checks: list[dict[str, str]] = []
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
            checks.append({"level": "ok", "title": f"{label.capitalize()} source is available", "detail": str(source), "fix": ""})
            lines.append(_doctor_line("OK", f"{label.capitalize()} source is available", str(source)))
        else:
            errors += 1
            checks.append(
                {
                    "level": "error",
                    "title": f"{label.capitalize()} source is missing",
                    "detail": f"The repo is missing {source}. `{label}` init will fail.",
                    "fix": "Restore the tracked template files in this repository before using init.",
                }
            )
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
        checks.append(
            {
                "level": "error",
                "title": "Workspace root is missing",
                "detail": "The selected workspace has not been initialized yet.",
                "fix": "Run `research-planner init --mode blank` or `research-planner --workspace ./workspace_demo init --mode demo`.",
            }
        )
        lines.append(
            _doctor_line(
                "ERROR",
                "Workspace root is missing",
                "The selected workspace has not been initialized yet.",
                "Run `research-planner init --mode blank` or `research-planner --workspace ./workspace_demo init --mode demo`.",
            )
        )
        warnings += 1
        checks.append(
            {
                "level": "warning",
                "title": "Detailed workspace checks were skipped",
                "detail": "The workspace does not exist yet, so file-level checks would all fail for the same reason.",
                "fix": "Initialize the workspace first, then run `research-planner doctor` again for a full check.",
            }
        )
        lines.append(
            _doctor_line(
                "WARN",
                "Detailed workspace checks were skipped",
                "The workspace does not exist yet, so file-level checks would all fail for the same reason.",
                "Initialize the workspace first, then run `research-planner doctor` again for a full check.",
            )
        )
    else:
        checks.append({"level": "ok", "title": "Workspace root exists", "detail": str(paths.root), "fix": ""})
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
                checks.append({"level": "ok", "title": label, "detail": str(path), "fix": ""})
                lines.append(_doctor_line("OK", label, str(path)))
            else:
                errors += 1
                checks.append({"level": "error", "title": label, "detail": f"Missing required file: {path}", "fix": fix})
                lines.append(_doctor_line("ERROR", label, f"Missing required file: {path}", fix))

        if paths.daily_reports_dir.exists():
            checks.append({"level": "ok", "title": "Daily reports directory", "detail": str(paths.daily_reports_dir), "fix": ""})
            lines.append(_doctor_line("OK", "Daily reports directory", str(paths.daily_reports_dir)))
        else:
            warnings += 1
            checks.append(
                {
                    "level": "warning",
                    "title": "Daily reports directory is missing",
                    "detail": f"{paths.daily_reports_dir} does not exist yet.",
                    "fix": "Run `research-planner prepare-report` to recreate it automatically.",
                }
            )
            lines.append(
                _doctor_line(
                    "WARN",
                    "Daily reports directory is missing",
                    f"{paths.daily_reports_dir} does not exist yet.",
                    "Run `research-planner prepare-report` to recreate it automatically.",
                )
            )

        if paths.history_dir.exists():
            checks.append({"level": "ok", "title": "History directory", "detail": str(paths.history_dir), "fix": ""})
            lines.append(_doctor_line("OK", "History directory", str(paths.history_dir)))
        else:
            warnings += 1
            checks.append(
                {
                    "level": "warning",
                    "title": "History directory is missing",
                    "detail": f"{paths.history_dir} does not exist yet.",
                    "fix": "Run `research-planner ingest-report --input <report>` to recreate it automatically.",
                }
            )
            lines.append(
                _doctor_line(
                    "WARN",
                    "History directory is missing",
                    f"{paths.history_dir} does not exist yet.",
                    "Run `research-planner ingest-report --input <report>` to recreate it automatically.",
                )
            )

        if paths.outputs_dir.exists():
            checks.append({"level": "ok", "title": "Outputs directory", "detail": str(paths.outputs_dir), "fix": ""})
            lines.append(_doctor_line("OK", "Outputs directory", str(paths.outputs_dir)))
        else:
            warnings += 1
            checks.append(
                {
                    "level": "warning",
                    "title": "Outputs directory is missing",
                    "detail": f"{paths.outputs_dir} does not exist yet.",
                    "fix": "Run `research-planner refresh` to recreate it automatically.",
                }
            )
            lines.append(
                _doctor_line(
                    "WARN",
                    "Outputs directory is missing",
                    f"{paths.outputs_dir} does not exist yet.",
                    "Run `research-planner refresh` to recreate it automatically.",
                )
            )

        if integrations["calendar_provider"] in {"file", "ics"}:
            if integrations["event_source_path"].exists():
                checks.append({"level": "ok", "title": "File-based calendar source", "detail": str(integrations["event_source_path"]), "fix": ""})
                lines.append(_doctor_line("OK", "File-based calendar source", str(integrations["event_source_path"])))
            else:
                warnings += 1
                checks.append(
                    {
                        "level": "warning",
                        "title": "File-based calendar source is missing",
                        "detail": f"Planner events will load as an empty list without {integrations['event_source_path']}.",
                        "fix": "Create the JSON/ICS file or restore data/calendar_events.json from a starter template.",
                    }
                )
                lines.append(
                    _doctor_line(
                        "WARN",
                        "File-based calendar source is missing",
                        f"Planner events will load as an empty list without {integrations['event_source_path']}.",
                        "Create the JSON/ICS file or restore data/calendar_events.json from a starter template.",
                    )
                )
        else:
            if integrations["calendar_script"].exists():
                checks.append({"level": "ok", "title": "macOS calendar export script", "detail": str(integrations["calendar_script"]), "fix": ""})
                lines.append(_doctor_line("OK", "macOS calendar export script", str(integrations["calendar_script"])))
            else:
                errors += 1
                checks.append(
                    {
                        "level": "error",
                        "title": "macOS calendar export script is missing",
                        "detail": f"Expected {integrations['calendar_script']} for macOS calendar sync.",
                        "fix": "Restore integrations/macos/export_events.swift from the repository.",
                    }
                )
                lines.append(
                    _doctor_line(
                        "ERROR",
                        "macOS calendar export script is missing",
                        f"Expected {integrations['calendar_script']} for macOS calendar sync.",
                        "Restore integrations/macos/export_events.swift from the repository.",
                    )
                )
            warnings += 1
            checks.append(
                {
                    "level": "warning",
                    "title": "macOS calendar access still needs user permission",
                    "detail": "Even with the script present, EventKit export can fail if Calendar access is denied.",
                    "fix": "Grant calendar permission to the terminal or app that runs the planner.",
                }
            )
            lines.append(
                _doctor_line(
                    "WARN",
                    "macOS calendar access still needs user permission",
                    "Even with the script present, EventKit export can fail if Calendar access is denied.",
                    "Grant calendar permission to the terminal or app that runs the planner.",
                )
            )

    validation = validate_workspace_files(paths) if paths.root.exists() else {}
    for name, issues in validation.items():
        for item in issues:
            if item["level"] == "error":
                errors += 1
            elif item["level"] == "warning":
                warnings += 1

    summary = f"Summary: {errors} error(s), {warnings} warning(s)"
    return {
        "summary_text": summary,
        "text": "\n".join([summary, ""] + lines),
        "summary": {"errors": errors, "warnings": warnings},
        "workspace": str(paths.root),
        "project_name": configs["project"]["project_name"],
        "calendar_provider": integrations["calendar_provider"],
        "checks": checks,
        "validation": validation,
        "ok": errors == 0,
    }


def doctor(paths, json_mode: bool = False) -> int:
    report = doctor_report(paths)
    if json_mode:
        print(json.dumps(report, indent=2, ensure_ascii=False))
    else:
        print(report["text"])
    return 1 if report["summary"]["errors"] else 0


def refresh_demo_assets(paths, *, skip_screenshots: bool = False) -> int:
    args = [
        "--workspace-root",
        str(paths.root),
    ]
    if skip_screenshots:
        args.append("--skip-screenshots")
    run_module("planner.demo_assets", args)
    return 0


def main() -> int:
    args = parse_args()
    paths = build_paths(args.workspace)

    if args.command == "init":
        source = template_sources()["blank" if args.mode == "blank" else "demo"]
        if not source.exists():
            raise SystemExit(f"Missing init source: {source}")
        copy_template(source, paths.root, args.force)
        configure_initialized_workspace(paths, args)
        print(paths.root)
        return 0

    if args.command == "doctor":
        return doctor(paths, json_mode=args.json)

    if args.command == "refresh-demo-assets":
        return refresh_demo_assets(paths, skip_screenshots=args.skip_screenshots)

    configs = load_configs(paths) if paths.root.exists() else None

    if configs is None:
        raise SystemExit(f"Workspace not found: {paths.root}. Run `research-planner init --mode blank` first.")

    if args.command == "prepare-report":
        prepare_report(paths, configs["project"])
        return 0

    if args.command == "refresh":
        print(refresh_dashboard(paths, configs))
        return 0

    if args.command == "ingest-report":
        ingest_report(paths, configs, Path(args.input).expanduser().resolve(), replan_mode=args.replan)
        return 0

    if args.command == "replan":
        integrations = integration_settings(paths, configs)
        run_args = [
            "--input",
            str(Path(args.input).expanduser().resolve()),
            "--workspace-root",
            str(paths.root),
            "--calendar-provider",
            integrations["calendar_provider"],
            "--events-file",
            str(integrations["event_source_path"]),
        ]
        if args.apply:
            run_args.append("--apply")
        if args.output:
            run_args.extend(["--output", str(Path(args.output).expanduser().resolve())])
        run_module("planner.replan", run_args)
        if args.apply:
            refresh_dashboard(paths, configs)
        return 0

    if args.command == "summary":
        print(generate_summary(paths, configs, args.period, args.target))
        return 0

    raise SystemExit(f"Unknown command: {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())
