from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml

from .planner_data import normalize_calendar_provider, normalize_plan_details, normalize_status_log


def issue(path: str, level: str, message: str) -> dict[str, str]:
    return {"path": path, "level": level, "message": message}


def load_yaml_file(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def load_json_file(path: Path) -> Any:
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def validate_project_config(payload: dict[str, Any]) -> list[dict[str, str]]:
    issues: list[dict[str, str]] = []
    required = {
        "project_name": str,
        "timezone": str,
        "locale": str,
        "primary_language": str,
        "dashboard_window_days": int,
        "sync_deadline": str,
    }
    for key, expected in required.items():
        if key not in payload:
            issues.append(issue(f"project.{key}", "error", "Missing required field."))
        elif not isinstance(payload[key], expected):
            issues.append(issue(f"project.{key}", "error", f"Expected {expected.__name__}."))
    return issues


def validate_constraints_config(payload: dict[str, Any]) -> list[dict[str, str]]:
    issues: list[dict[str, str]] = []
    for key in ("meetings", "blocked_days", "blocked_windows"):
        if key not in payload:
            issues.append(issue(f"constraints.{key}", "error", "Missing required field."))
        elif not isinstance(payload[key], list):
            issues.append(issue(f"constraints.{key}", "error", "Expected a list."))
    for key in ("workday_start", "workday_end"):
        if key not in payload:
            issues.append(issue(f"constraints.{key}", "warning", "Missing workday bound; default will be used."))
        elif not isinstance(payload[key], str):
            issues.append(issue(f"constraints.{key}", "error", "Expected a string in HH:MM format."))
    return issues


def validate_integrations_config(payload: dict[str, Any]) -> list[dict[str, str]]:
    issues: list[dict[str, str]] = []
    for key in ("calendar_provider", "primary_calendar_name", "auto_open_outputs", "event_source_file"):
        if key not in payload:
            issues.append(issue(f"integrations.{key}", "error", "Missing required field."))
    provider = payload.get("calendar_provider")
    try:
        normalize_calendar_provider(provider)
    except ValueError as exc:
        issues.append(issue("integrations.calendar_provider", "error", str(exc)))
    return issues


def validate_workstreams_config(payload: dict[str, Any]) -> list[dict[str, str]]:
    issues: list[dict[str, str]] = []
    streams = payload.get("streams")
    if not isinstance(streams, list):
        return [issue("workstreams.streams", "error", "Expected a list of streams.")]
    for index, stream in enumerate(streams):
        if not isinstance(stream, dict):
            issues.append(issue(f"workstreams.streams[{index}]", "error", "Expected an object."))
            continue
        for key in ("id", "label"):
            if key not in stream:
                issues.append(issue(f"workstreams.streams[{index}].{key}", "error", "Missing required field."))
    return issues


def validate_plan_details(payload: dict[str, Any]) -> list[dict[str, str]]:
    issues: list[dict[str, str]] = []
    normalized = normalize_plan_details(payload)
    if normalized.get("schema_version", 0) < 2:
        issues.append(issue("plan_details.schema_version", "warning", "Older schema version; it will be upgraded in memory."))
    if not isinstance(normalized.get("streams"), list):
        issues.append(issue("plan_details.streams", "error", "Expected a list."))
    if not isinstance(normalized.get("experiments"), list):
        issues.append(issue("plan_details.experiments", "error", "Expected a list."))
    if not isinstance(normalized.get("days"), list):
        issues.append(issue("plan_details.days", "error", "Expected a list."))
    return issues


def validate_status_log(payload: dict[str, Any]) -> list[dict[str, str]]:
    issues: list[dict[str, str]] = []
    normalized = normalize_status_log(payload)
    if not isinstance(normalized.get("statuses"), list):
        issues.append(issue("status_log.statuses", "error", "Expected a list."))
    return issues


def validate_calendar_events(payload: Any) -> list[dict[str, str]]:
    issues: list[dict[str, str]] = []
    if not isinstance(payload, list):
        return [issue("calendar_events", "error", "Expected a list of events.")]
    for index, event in enumerate(payload):
        if not isinstance(event, dict):
            issues.append(issue(f"calendar_events[{index}]", "error", "Expected an object."))
            continue
        for key in ("calendar", "title", "start", "end"):
            if key not in event:
                issues.append(issue(f"calendar_events[{index}].{key}", "error", "Missing required field."))
    return issues


def validate_workspace_files(paths) -> dict[str, list[dict[str, str]]]:
    return {
        "project": validate_project_config(load_yaml_file(paths.project_config)),
        "constraints": validate_constraints_config(load_yaml_file(paths.constraints_config)),
        "integrations": validate_integrations_config(load_yaml_file(paths.integrations_config)),
        "workstreams": validate_workstreams_config(load_yaml_file(paths.workstreams_config)),
        "plan_details": validate_plan_details(load_json_file(paths.plan_details) or {}),
        "status_log": validate_status_log(load_json_file(paths.status_log) or {}),
        "calendar_events": validate_calendar_events(load_json_file(paths.calendar_events) or []),
    }

