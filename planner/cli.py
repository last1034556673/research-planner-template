"""Command-line interface for the research planner template."""

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


_LEVEL_LABELS = {"ok": "OK", "error": "ERROR", "warning": "WARN"}


def _doctor_line(level: str, title: str, detail: str, fix: str | None = None) -> str:
    tag = _LEVEL_LABELS.get(level, level.upper())
    lines = [f"[{tag}] {title}", f"      {detail}"]
    if fix:
        lines.append(f"      Next: {fix}")
    return "\n".join(lines)


class _DoctorCollector:
    """Accumulates doctor checks, counts, and display lines."""

    def __init__(self) -> None:
        self.errors = 0
        self.warnings = 0
        self.checks: list[dict[str, str]] = []
        self.lines: list[str] = []

    def ok(self, title: str, detail: str) -> None:
        self.checks.append({"level": "ok", "title": title, "detail": detail, "fix": ""})
        self.lines.append(_doctor_line("ok", title, detail))

    def error(self, title: str, detail: str, fix: str) -> None:
        self.errors += 1
        self.checks.append({"level": "error", "title": title, "detail": detail, "fix": fix})
        self.lines.append(_doctor_line("error", title, detail, fix))

    def warning(self, title: str, detail: str, fix: str) -> None:
        self.warnings += 1
        self.checks.append({"level": "warning", "title": title, "detail": detail, "fix": fix})
        self.lines.append(_doctor_line("warning", title, detail, fix))

    def check_path_exists(self, path: Path, label: str, missing_detail: str, fix: str, level: str = "error") -> bool:
        if path.exists():
            self.ok(label, str(path))
            return True
        if level == "error":
            self.error(label, missing_detail, fix)
        else:
            self.warning(label, missing_detail, fix)
        return False


def _check_template_sources(collector: _DoctorCollector) -> None:
    for label, source in template_sources().items():
        collector.check_path_exists(
            source,
            f"{label.capitalize()} source is available",
            f"The repo is missing {source}. `{label}` init will fail.",
            "Restore the tracked template files in this repository before using init.",
        )


def _check_required_files(collector: _DoctorCollector, paths) -> None:
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
        collector.check_path_exists(path, label, f"Missing required file: {path}", fix)


def _check_optional_dirs(collector: _DoctorCollector, paths) -> None:
    optional_dirs = [
        ("Daily reports directory", paths.daily_reports_dir, "Run `research-planner prepare-report` to recreate it automatically."),
        ("History directory", paths.history_dir, "Run `research-planner ingest-report --input <report>` to recreate it automatically."),
        ("Outputs directory", paths.outputs_dir, "Run `research-planner refresh` to recreate it automatically."),
    ]
    for label, path, fix in optional_dirs:
        collector.check_path_exists(
            path,
            label,
            f"{path} does not exist yet.",
            fix,
            level="warning",
        )


def _check_calendar_provider(collector: _DoctorCollector, integrations: dict) -> None:
    if integrations["calendar_provider"] in {"file", "ics"}:
        collector.check_path_exists(
            integrations["event_source_path"],
            "File-based calendar source",
            f"Planner events will load as an empty list without {integrations['event_source_path']}.",
            "Create the JSON/ICS file or restore data/calendar_events.json from a starter template.",
            level="warning",
        )
    else:
        collector.check_path_exists(
            integrations["calendar_script"],
            "macOS calendar export script",
            f"Expected {integrations['calendar_script']} for macOS calendar sync.",
            "Restore integrations/macos/export_events.swift from the repository.",
        )
        collector.warning(
            "macOS calendar access still needs user permission",
            "Even with the script present, EventKit export can fail if Calendar access is denied.",
            "Grant calendar permission to the terminal or app that runs the planner.",
        )


def doctor_report(paths) -> dict[str, object]:
    configs = load_configs(paths)
    integrations = integration_settings(paths, configs)
    collector = _DoctorCollector()
    collector.lines.extend([
        f"Workspace: {paths.root}",
        f"Project name: {configs['project']['project_name']}",
        f"Time zone: {configs['project']['timezone']}",
        f"Calendar provider: {integrations['calendar_provider']}",
        f"Primary calendar: {integrations['primary_calendar_name']}",
        "",
    ])

    _check_template_sources(collector)

    if not paths.root.exists():
        collector.error(
            "Workspace root is missing",
            "The selected workspace has not been initialized yet.",
            "Run `research-planner init --mode blank` or `research-planner --workspace ./workspace_demo init --mode demo`.",
        )
        collector.warning(
            "Detailed workspace checks were skipped",
            "The workspace does not exist yet, so file-level checks would all fail for the same reason.",
            "Initialize the workspace first, then run `research-planner doctor` again for a full check.",
        )
    else:
        collector.ok("Workspace root exists", str(paths.root))
        _check_required_files(collector, paths)
        _check_optional_dirs(collector, paths)
        _check_calendar_provider(collector, integrations)

    validation = validate_workspace_files(paths) if paths.root.exists() else {}
    for issues in validation.values():
        for item in issues:
            if item["level"] == "error":
                collector.errors += 1
            elif item["level"] == "warning":
                collector.warnings += 1

    summary = f"Summary: {collector.errors} error(s), {collector.warnings} warning(s)"
    return {
        "summary_text": summary,
        "text": "\n".join([summary, ""] + collector.lines),
        "summary": {"errors": collector.errors, "warnings": collector.warnings},
        "workspace": str(paths.root),
        "project_name": configs["project"]["project_name"],
        "calendar_provider": integrations["calendar_provider"],
        "checks": collector.checks,
        "validation": validation,
        "ok": collector.errors == 0,
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


def dispatch_standalone(command: str, args: argparse.Namespace, paths) -> int | None:
    """Handle commands that don't require a loaded workspace config."""
    if command == "init":
        source = template_sources()["blank" if args.mode == "blank" else "demo"]
        if not source.exists():
            raise SystemExit(f"Missing init source: {source}")
        copy_template(source, paths.root, args.force)
        configure_initialized_workspace(paths, args)
        print(paths.root)
        return 0
    if command == "doctor":
        return doctor(paths, json_mode=args.json)
    if command == "refresh-demo-assets":
        return refresh_demo_assets(paths, skip_screenshots=args.skip_screenshots)
    return None


def dispatch_workspace(command: str, args: argparse.Namespace, paths, configs: dict[str, dict]) -> int:
    """Handle commands that require a loaded workspace config."""
    if command == "prepare-report":
        prepare_report(paths, configs["project"])
        return 0
    if command == "refresh":
        print(refresh_dashboard(paths, configs))
        return 0
    if command == "ingest-report":
        ingest_report(paths, configs, Path(args.input).expanduser().resolve(), replan_mode=args.replan)
        return 0
    if command == "replan":
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
    if command == "summary":
        print(generate_summary(paths, configs, args.period, args.target))
        return 0
    raise SystemExit(f"Unknown command: {command}")


def main() -> int:
    args = parse_args()
    paths = build_paths(args.workspace)

    result = dispatch_standalone(args.command, args, paths)
    if result is not None:
        return result

    configs = load_configs(paths) if paths.root.exists() else None
    if configs is None:
        raise SystemExit(f"Workspace not found: {paths.root}. Run `research-planner init --mode blank` first.")

    return dispatch_workspace(args.command, args, paths, configs)


if __name__ == "__main__":
    raise SystemExit(main())
