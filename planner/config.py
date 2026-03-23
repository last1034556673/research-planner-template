"""Workspace configuration loading and merging utilities."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from .planner_data import normalize_calendar_provider
from .workspace import WorkspacePaths


DEFAULT_PROJECT = {
    "project_name": "Research Planner",
    "timezone": "Asia/Shanghai",
    "locale": "en_US",
    "primary_language": "en",
    "dashboard_window_days": 15,
    "sync_deadline": "09:30",
}

DEFAULT_CONSTRAINTS = {
    "meetings": [],
    "blocked_days": [],
    "blocked_windows": [],
    "weekend_rules": {},
    "workday_start": "08:00",
    "workday_end": "18:00",
}

DEFAULT_INTEGRATIONS = {
    "calendar_provider": "file",
    "primary_calendar_name": "Research",
    "auto_open_outputs": False,
    "event_source_file": "data/calendar_events.json",
}

DEFAULT_WORKSTREAMS = {
    "streams": [
        {"id": "rna", "label": "Analysis / Slides", "label_en": "Analysis / Slides", "group": "analysis", "color": "#c84f3f"},
        {"id": "cell", "label": "Cell Expansion", "label_en": "Cell Expansion", "group": "wetlab", "color": "#157f78"},
        {"id": "spheroid", "label": "3D Models", "label_en": "3D Models", "group": "wetlab", "color": "#5e60ce"},
        {"id": "flow", "label": "Assays / Flow", "label_en": "Assays / Flow", "group": "wetlab", "color": "#f08f49"},
        {"id": "material", "label": "Material Characterization", "label_en": "Material Characterization", "group": "wetlab", "color": "#2f6cad"},
        {"id": "robot", "label": "Motion Tests", "label_en": "Motion Tests", "group": "wetlab", "color": "#2d936c"},
        {"id": "mouse", "label": "Animal Work", "label_en": "Animal Work", "group": "wetlab", "color": "#98473e"},
        {"id": "prep", "label": "Preparation / Follow-up", "label_en": "Preparation / Follow-up", "group": "planning", "color": "#8f6a1a"},
        {"id": "general", "label": "General", "label_en": "General", "group": "general", "color": "#566573"},
    ]
}


def _load_yaml(path: Path, default: dict[str, Any]) -> dict[str, Any]:
    if not path.exists():
        return dict(default)
    payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    merged = dict(default)
    merged.update(payload)
    return merged


def load_configs(paths: WorkspacePaths) -> dict[str, Any]:
    project = _load_yaml(paths.project_config, DEFAULT_PROJECT)
    constraints = _load_yaml(paths.constraints_config, DEFAULT_CONSTRAINTS)
    integrations = _load_yaml(paths.integrations_config, DEFAULT_INTEGRATIONS)
    workstreams = _load_yaml(paths.workstreams_config, DEFAULT_WORKSTREAMS)
    workstreams.setdefault("streams", [])
    return {
        "project": project,
        "constraints": constraints,
        "integrations": integrations,
        "workstreams": workstreams,
    }


def resolve_workspace_path(paths: WorkspacePaths, configured_path: str | None, fallback: Path) -> Path:
    if not configured_path:
        return fallback
    candidate = Path(configured_path).expanduser()
    if candidate.is_absolute():
        return candidate
    return (paths.root / candidate).resolve()


def integration_settings(paths: WorkspacePaths, configs: dict[str, Any]) -> dict[str, Any]:
    integrations = dict(configs["integrations"])
    integrations["calendar_provider"] = normalize_calendar_provider(integrations.get("calendar_provider"))
    integrations["event_source_path"] = resolve_workspace_path(
        paths,
        integrations.get("event_source_file"),
        paths.calendar_events,
    )
    integrations["calendar_script"] = (
        paths.repo_root / "integrations" / "macos" / "export_events.swift"
    )
    return integrations


def merged_streams_from_config(configs: dict[str, Any]) -> list[dict[str, Any]]:
    streams = []
    for stream in configs["workstreams"].get("streams", []):
        stream_id = stream.get("id")
        label = stream.get("label")
        if not stream_id or not label:
            continue
        streams.append({"id": stream_id, "label": label})
    return streams
