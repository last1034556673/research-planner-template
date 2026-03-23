"""Core data normalization and matching for plan details, status logs, and calendar events."""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import re
from copy import deepcopy
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo


SCHEMA_VERSION = 2
HARD_TIMEPOINT_MARKERS = ("0h", "24h", "48h", "72h", "96h")

DEFAULT_PRIMARY_CALENDAR = "Research"
DEFAULT_IGNORE = frozenset({"Birthdays", "Holidays", "China Holidays", "Chinese Holidays"})

GENERIC_CATEGORIZATION = (
    ("mouse", ("mouse", "animal", "in vivo", "cohort", "tumor model", "小鼠", "动物")),
    ("cell", ("cell", "culture", "passage", "seed", "confluence", "organoid", "传代", "细胞", "扩增")),
    ("spheroid", ("3d", "spheroid", "organoid", "embed", "matrigel", "肿瘤球", "成球")),
    ("flow", ("flow", "cytometry", "staining", "fitc", "cfse", "uptake", "assay", "流式")),
    ("rna", ("rna", "analysis", "figure", "slides", "ppt", "summary", "results", "plot")),
    ("material", ("dls", "zeta", "characterization", "particle", "material", "sizing", "表征")),
    ("robot", ("motion", "microrobot", "pipeline", "navigation", "tracking", "运动", "机器人")),
    ("prep", ("prepare", "booking", "order", "check", "review", "follow-up", "整理", "订购", "准备")),
)


def compact_text(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip())


def compact_title(text: str) -> str:
    """Strip bracket suffixes and leading non-word characters from event titles."""
    text = re.sub(r"\s*\[[^\]]+\]\s*$", "", text).strip()
    text = re.sub(r"^[^\w\u4e00-\u9fff]+", "", text).strip()
    return text


def compact_match_text(text: str) -> str:
    text = compact_text(text)
    return re.sub(r"[\s\[\]（）()【】:：,，.。+＋/_-]+", "", text).lower()


def normalize_match_text(text: str) -> str:
    """Normalize event title text for fuzzy matching."""
    text = compact_title(text)
    return re.sub(r"[\s\[\]（）()【】:：,，.。+＋/_-]+", "", text).lower()


def score_event_match(text: str, event: dict[str, Any]) -> int:
    """Score how well a text fragment matches an event title (0-100)."""
    left = normalize_match_text(text)
    right = normalize_match_text(event["title"])
    if not left or not right:
        return -1
    if left == right:
        return 100
    if left in right or right in left:
        return 80
    left_tokens = set(re.findall(r"[\u4e00-\u9fffA-Za-z0-9]+", left))
    right_tokens = set(re.findall(r"[\u4e00-\u9fffA-Za-z0-9]+", right))
    return len(left_tokens & right_tokens) * 10


def categorize(title: str) -> str:
    """Classify an event title into a workstream based on keyword matching."""
    title_lower = title.lower()
    for stream_id, keywords in GENERIC_CATEGORIZATION:
        if any(keyword in title_lower or keyword in title for keyword in keywords):
            return stream_id
    return "general"


def is_conditional(title: str) -> bool:
    """Check whether an event title indicates a conditional/gated task."""
    markers = ("if ", "when ", "once ", "after confirmation", "if confluence", "若", "待确认", "条件")
    title_lower = title.lower()
    return any(marker in title_lower or marker in title for marker in markers)


def parse_event(record: dict[str, Any], tz: ZoneInfo) -> dict[str, Any]:
    """Transform a raw calendar event record into a normalized parsed event dict."""
    start = dt.datetime.fromisoformat(record["start"]).astimezone(tz)
    end = dt.datetime.fromisoformat(record["end"]).astimezone(tz)
    title = record["title"]
    return {
        "id": f"{record.get('calendar', '')}|{start.isoformat()}|{title}",
        "calendar": record.get("calendar", DEFAULT_PRIMARY_CALENDAR),
        "event_id": record.get("event_id"),
        "task_id": record.get("task_id"),
        "title": title,
        "short_title": compact_title(title),
        "start": start,
        "end": end,
        "is_all_day": bool(record.get("isAllDay", False)),
        "stream": record.get("stream") or categorize(title),
        "display_streams": list(dict.fromkeys(record.get("display_streams", []) or [record.get("stream") or categorize(title)])),
        "conditional": bool(record.get("conditional")) or is_conditional(title),
        "aliases": list(dict.fromkeys(record.get("aliases", []) or [title])),
    }


def best_event_match(
    text: str,
    events: list[dict[str, Any]],
    reference_date: dt.date | None = None,
) -> dict[str, Any] | None:
    """Find the best-matching event for a text fragment, returning None if below threshold."""
    if not events:
        return None
    if reference_date is not None:
        ranked = sorted(
            events,
            key=lambda item: (score_event_match(text, item), -abs((item["start"].date() - reference_date).days)),
            reverse=True,
        )
    else:
        ranked = sorted(
            events,
            key=lambda item: (score_event_match(text, item), item["start"]),
            reverse=True,
        )
    return ranked[0] if score_event_match(text, ranked[0]) >= 60 else None


def load_status_log(path: Path) -> dict[str, Any]:
    """Load and normalize a status log from a JSON file, returning empty log if missing."""
    if not path.exists():
        return normalize_status_log({"statuses": []})
    return normalize_status_log(json.loads(path.read_text(encoding="utf-8")))


def normalize_aliases(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        value = [value]
    if not isinstance(value, list):
        return []
    normalized: list[str] = []
    for item in value:
        if not isinstance(item, str):
            continue
        text = compact_text(item)
        if text and text not in normalized:
            normalized.append(text)
    return normalized


def stable_task_id(*parts: str) -> str:
    joined = "||".join(compact_match_text(part) for part in parts if part)
    digest = hashlib.sha1(joined.encode("utf-8")).hexdigest()[:10]
    return f"task-{digest}"


def stable_event_id(*parts: str) -> str:
    joined = "||".join(compact_match_text(part) for part in parts if part)
    digest = hashlib.sha1(joined.encode("utf-8")).hexdigest()[:10]
    return f"evt-{digest}"


def task_title(descriptor: dict[str, Any]) -> str:
    return (
        descriptor.get("title")
        or descriptor.get("title_match")
        or descriptor.get("title_contains")
        or "Untitled task"
    )


def descriptor_aliases(descriptor: dict[str, Any]) -> list[str]:
    aliases = normalize_aliases(descriptor.get("aliases"))
    title = descriptor.get("title")
    title_match = descriptor.get("title_match")
    title_contains = descriptor.get("title_contains")
    for item in (title, title_match, title_contains):
        text = compact_text(item or "")
        if text and text not in aliases:
            aliases.append(text)
    return aliases


def infer_hard_timepoint(title: str, aliases: list[str]) -> bool:
    haystack = " ".join([title, *aliases]).lower()
    return any(marker in haystack for marker in HARD_TIMEPOINT_MARKERS)


def infer_replan_policy(descriptor: dict[str, Any]) -> str:
    if descriptor.get("decision_rule") or descriptor.get("condition") or descriptor.get("conditional"):
        return "conditional"
    if descriptor.get("hard_timepoint"):
        return "manual"
    return "auto"


def ensure_task_metadata(descriptor: dict[str, Any], *, date_hint: str) -> dict[str, Any]:
    item = dict(descriptor)
    aliases = descriptor_aliases(item)
    title = task_title(item)
    item["aliases"] = aliases
    item["task_id"] = item.get("task_id") or stable_task_id(date_hint, title, *aliases)
    item["depends_on"] = [dep for dep in normalize_aliases(item.get("depends_on"))]
    item["hard_timepoint"] = bool(item.get("hard_timepoint", infer_hard_timepoint(title, aliases)))
    item["replan_policy"] = item.get("replan_policy") or infer_replan_policy(item)
    return item


def normalize_plan_details(payload: dict[str, Any] | None) -> dict[str, Any]:
    data = deepcopy(payload) if payload else {}
    data.setdefault("streams", [])
    data.setdefault("experiments", [])
    data.setdefault("days", [])
    data["schema_version"] = max(int(data.get("schema_version", 1)), SCHEMA_VERSION)

    for experiment in data["experiments"]:
        experiment.setdefault("steps", [])
        for index, step in enumerate(experiment["steps"]):
            date_hint = step.get("date") or experiment.get("id") or f"step-{index}"
            experiment["steps"][index] = ensure_task_metadata(step, date_hint=date_hint)
        for index, step in enumerate(experiment["steps"]):
            if index == 0 or step.get("depends_on"):
                continue
            previous = experiment["steps"][index - 1]
            step["depends_on"] = [previous["task_id"]]

    for day in data["days"]:
        day.setdefault("tasks", [])
        for index, task in enumerate(day["tasks"]):
            date_hint = day.get("date") or f"day-{index}"
            day["tasks"][index] = ensure_task_metadata(task, date_hint=date_hint)

    return data


def normalize_calendar_provider(provider: str | None) -> str:
    if not provider:
        return "file"
    if provider == "none":
        return "file"
    if provider in {"file", "macos", "ics"}:
        return provider
    raise ValueError(f"Unsupported calendar provider: {provider}")


def normalize_calendar_events(payload: list[dict[str, Any]] | None, plan: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    events = deepcopy(payload) if payload else []
    plan_index = build_task_index(plan or {"experiments": [], "days": []})
    descriptors = list(plan_index.values())
    normalized: list[dict[str, Any]] = []
    for item in events:
        if not isinstance(item, dict):
            continue
        event = dict(item)
        event["aliases"] = normalize_aliases(event.get("aliases"))
        event["event_id"] = event.get("event_id") or stable_event_id(
            str(event.get("start", "")),
            str(event.get("end", "")),
            str(event.get("title", "")),
            str(event.get("calendar", "")),
        )
        if not event.get("task_id"):
            matched = match_descriptor_to_event_record(descriptors, event)
            if matched:
                event["task_id"] = matched["task_id"]
                merged_aliases = [*event["aliases"]]
                for alias in matched.get("aliases", []):
                    if alias not in merged_aliases:
                        merged_aliases.append(alias)
                event["aliases"] = merged_aliases
        normalized.append(event)
    return normalized


def normalize_status_log(payload: dict[str, Any] | None) -> dict[str, Any]:
    data = deepcopy(payload) if payload else {}
    data["schema_version"] = max(int(data.get("schema_version", 1)), SCHEMA_VERSION)
    statuses = data.setdefault("statuses", [])
    normalized_statuses = []
    for entry in statuses:
        if not isinstance(entry, dict):
            continue
        item = dict(entry)
        item["aliases"] = normalize_aliases(item.get("aliases"))
        item["depends_on"] = normalize_aliases(item.get("depends_on"))
        normalized_statuses.append(item)
    data["statuses"] = normalized_statuses
    return data


def build_task_index(plan: dict[str, Any]) -> dict[str, dict[str, Any]]:
    normalized_plan = normalize_plan_details(plan)
    index: dict[str, dict[str, Any]] = {}

    for experiment in normalized_plan.get("experiments", []):
        experiment_id = experiment.get("id", "")
        for step in experiment.get("steps", []):
            entry = {
                **step,
                "source_kind": "experiment_step",
                "source_id": experiment_id,
                "source_date": step.get("date"),
                "stream": step.get("stream") or experiment.get("stream", "general"),
                "title": task_title(step),
            }
            index[entry["task_id"]] = entry

    for day in normalized_plan.get("days", []):
        day_date = day.get("date")
        for task in day.get("tasks", []):
            task_id = task.get("task_id")
            title = task_title(task)
            existing = index.get(task_id)
            merged_depends_on = list(
                dict.fromkeys(
                    [
                        *normalize_aliases((existing or {}).get("depends_on")),
                        *normalize_aliases(task.get("depends_on")),
                    ]
                )
            )
            merged = {
                **(existing or {}),
                **task,
                "task_id": task_id,
                "source_kind": "day_task",
                "source_date": day_date,
                "stream": task.get("stream") or (existing or {}).get("stream", "general"),
                "title": title,
                "depends_on": merged_depends_on,
            }
            aliases = normalize_aliases((existing or {}).get("aliases")) + normalize_aliases(task.get("aliases"))
            merged["aliases"] = list(dict.fromkeys([*aliases, title]))
            index[task_id] = merged
    return index


def descriptor_matches_event_record(descriptor: dict[str, Any], event: dict[str, Any]) -> tuple[int, str]:
    descriptor_task_id = descriptor.get("task_id")
    event_task_id = event.get("task_id")
    if descriptor_task_id and event_task_id and descriptor_task_id == event_task_id:
        return 400, "task_id"

    title_match = descriptor.get("title_match")
    if title_match and title_match == event.get("title"):
        return 300, "title_match"

    descriptor_alias_set = {compact_match_text(item) for item in descriptor.get("aliases", []) if item}
    event_alias_set = {compact_match_text(item) for item in normalize_aliases(event.get("aliases")) if item}
    event_title = compact_match_text(event.get("title", ""))
    if event_title:
        event_alias_set.add(event_title)
    if descriptor_alias_set & event_alias_set:
        return 200, "aliases"

    descriptor_title = compact_match_text(task_title(descriptor))
    if descriptor_title and event_title:
        if descriptor_title == event_title:
            return 150, "fuzzy"
        if descriptor_title in event_title or event_title in descriptor_title:
            return 120, "fuzzy"
        descriptor_tokens = set(re.findall(r"[\u4e00-\u9fffA-Za-z0-9]+", descriptor_title))
        event_tokens = set(re.findall(r"[\u4e00-\u9fffA-Za-z0-9]+", event_title))
        overlap = len(descriptor_tokens & event_tokens)
        if overlap:
            return overlap * 10, "fuzzy"
    return -1, ""


def match_descriptor_to_event_record(descriptors: list[dict[str, Any]], event: dict[str, Any]) -> dict[str, Any] | None:
    ranked = sorted(
        (
            (descriptor_matches_event_record(descriptor, event)[0], descriptor)
            for descriptor in descriptors
        ),
        key=lambda item: item[0],
        reverse=True,
    )
    if not ranked or ranked[0][0] < 100:
        return None
    return ranked[0][1]


def event_matches_status_entry(entry: dict[str, Any], event: dict[str, Any]) -> bool:
    if entry.get("task_id") and event.get("task_id"):
        return entry["task_id"] == event["task_id"]
    if entry.get("date") and event.get("start"):
        event_date = event["start"].date().isoformat() if isinstance(event["start"], dt.datetime) else str(event["start"])[:10]
        if event_date != entry["date"]:
            return False
    if entry.get("title_match"):
        return entry["title_match"] == event.get("title")
    if entry.get("title_contains"):
        return entry["title_contains"] in event.get("title", "")
    entry_aliases = {compact_match_text(item) for item in normalize_aliases(entry.get("aliases"))}
    if entry_aliases:
        event_aliases = {compact_match_text(item) for item in normalize_aliases(event.get("aliases"))}
        event_aliases.add(compact_match_text(event.get("title", "")))
        return bool(entry_aliases & event_aliases)
    return False
