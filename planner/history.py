#!/usr/bin/env python3
"""History archive helpers for the public research planner template."""

from __future__ import annotations

import datetime as dt
import json
from pathlib import Path
import re
from typing import Any
from zoneinfo import ZoneInfo

from .calendar_io import load_event_records
from .dashboard import (
    DEFAULT_IGNORE,
    DEFAULT_STREAMS,
    annotate_event_status,
    categorize,
    is_conditional,
    parse_event,
    visible_primary,
)


DEFAULT_HISTORY_DIR = "history"
DAILY_HISTORY_DIRNAME = "daily"
SUMMARY_DIRNAME = "summaries"
EVENTS_FILENAME = "events.jsonl"

STREAM_LABELS = {item["id"]: item["label"] for item in DEFAULT_STREAMS}
REASON_CATEGORIES = (
    "Cell / sample state",
    "Instrument / reagent",
    "Time conflict / non-lab day",
    "Animals / materials",
    "Plan change",
    "Unspecified",
)

_CELL_KEYWORDS = (
    "cell",
    "sample",
    "confluence",
    "density",
    "passage",
    "growth",
    "recovery",
    "状态",
    "细胞",
    "传代",
)
_INSTRUMENT_KEYWORDS = (
    "instrument",
    "reagent",
    "booking",
    "machine",
    "dls",
    "zeta",
    "flow",
    "cytometry",
    "microscope",
    "试剂",
    "仪器",
)
_TIME_KEYWORDS = (
    "meeting",
    "weekend",
    "saturday",
    "sunday",
    "conflict",
    "no-lab",
    "busy",
    "周末",
    "会议",
    "组会",
)
_ANIMAL_MATERIAL_KEYWORDS = (
    "animal",
    "mouse",
    "cohort",
    "material",
    "particle",
    "mouse room",
    "动物",
    "小鼠",
    "材料",
)
_PLAN_KEYWORDS = (
    "reschedule",
    "move",
    "delay",
    "switch",
    "change",
    "adjust",
    "顺延",
    "改到",
    "改成",
    "调整",
)


def ensure_history_dirs(history_dir: Path) -> dict[str, Path]:
    daily_dir = history_dir / DAILY_HISTORY_DIRNAME
    summary_dir = history_dir / SUMMARY_DIRNAME
    daily_dir.mkdir(parents=True, exist_ok=True)
    summary_dir.mkdir(parents=True, exist_ok=True)
    return {
        "root": history_dir,
        "daily": daily_dir,
        "summaries": summary_dir,
        "events": history_dir / EVENTS_FILENAME,
    }


def to_iso(value: dt.datetime | None) -> str | None:
    return value.isoformat() if value else None


def display_path(path: Path | None, base: Path | None) -> str | None:
    if path is None:
        return None
    if base is not None:
        try:
            return str(path.relative_to(base))
        except ValueError:
            pass
    return str(path)


def serialize_event(event: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": event.get("id"),
        "calendar": event.get("calendar"),
        "title": event.get("title"),
        "short_title": event.get("short_title"),
        "start": to_iso(event.get("start")),
        "end": to_iso(event.get("end")),
        "stream": event.get("stream"),
        "display_streams": event.get("display_streams", []),
        "conditional": bool(event.get("conditional")),
        "status_key": event.get("status_key"),
        "status_label": event.get("status_label"),
        "status_note": event.get("status_note", ""),
    }


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    records = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        records.append(json.loads(line))
    return records


def write_jsonl(path: Path, records: list[dict[str, Any]]) -> None:
    lines = [json.dumps(record, ensure_ascii=False, sort_keys=True) for record in records]
    text = "\n".join(lines)
    if text:
        text += "\n"
    path.write_text(text, encoding="utf-8")


def status_entries_for_date(status_log: dict[str, Any], date_text: str) -> list[dict[str, Any]]:
    return [entry for entry in status_log.get("statuses", []) if entry.get("date") == date_text]


def entry_matches_event(entry: dict[str, Any], event: dict[str, Any]) -> bool:
    exact = entry.get("title_match")
    contains = entry.get("title_contains")
    if exact:
        return event["title"] == exact
    if contains:
        return contains in event["title"]
    return False


def infer_reason_category(title: str, status_note: str = "", extra_text: str = "") -> str:
    text = " ".join(part for part in (title, status_note, extra_text) if part).lower()
    if any(keyword in text for keyword in _CELL_KEYWORDS):
        return "Cell / sample state"
    if any(keyword in text for keyword in _INSTRUMENT_KEYWORDS):
        return "Instrument / reagent"
    if any(keyword in text for keyword in _TIME_KEYWORDS):
        return "Time conflict / non-lab day"
    if any(keyword in text for keyword in _ANIMAL_MATERIAL_KEYWORDS):
        return "Animals / materials"
    if any(keyword in text for keyword in _PLAN_KEYWORDS):
        return "Plan change"
    return "Unspecified"


def record_key(record: dict[str, Any]) -> str:
    return "|".join(
        [
            record.get("event_date", ""),
            record.get("source", ""),
            record.get("title", ""),
            record.get("planned_start") or "",
            record.get("planned_end") or "",
        ]
    )


def collect_primary_events_for_day(
    *,
    day: dt.date,
    tz: ZoneInfo,
    calendar: str,
    status_log: dict[str, Any],
    provider: str,
    events_file: Path | None,
    calendar_script: Path | None,
    now: dt.datetime | None = None,
) -> list[dict[str, Any]]:
    start = dt.datetime.combine(day, dt.time.min, tzinfo=tz)
    end = dt.datetime.combine(day + dt.timedelta(days=1), dt.time.min, tzinfo=tz)
    raw_events = load_event_records(
        start=start,
        end=end,
        tz_name=tz.key,
        provider=provider,
        events_file=events_file,
        calendar_script=calendar_script,
    )
    events = [parse_event(record, tz) for record in raw_events]
    events = [
        annotate_event_status(event, status_log.get("statuses", []), now or dt.datetime.now(tz))
        for event in events
        if event["calendar"] == calendar and event["calendar"] not in DEFAULT_IGNORE and visible_primary(event)
    ]
    events.sort(key=lambda item: (item["start"], item["end"], item["title"]))
    return events


def make_calendar_record(event: dict[str, Any], report_date: dt.date, extra_reason_text: str = "") -> dict[str, Any]:
    stream = event.get("stream", categorize(event["title"]))
    return {
        "report_date": report_date.isoformat(),
        "event_date": event["start"].date().isoformat(),
        "title": event["title"],
        "stream": stream,
        "stream_label": STREAM_LABELS.get(stream, stream),
        "planned_start": to_iso(event["start"]),
        "planned_end": to_iso(event["end"]),
        "status": event.get("status_key", "planned"),
        "status_note": event.get("status_note", ""),
        "is_conditional": bool(event.get("conditional")),
        "reason_category": infer_reason_category(event["title"], event.get("status_note", ""), extra_reason_text),
        "source": "calendar",
    }


def make_status_only_record(entry: dict[str, Any], report_date: dt.date, extra_reason_text: str = "") -> dict[str, Any]:
    title = entry.get("title_match") or entry.get("title_contains") or "Untitled status record"
    stream = categorize(title)
    return {
        "report_date": report_date.isoformat(),
        "event_date": entry.get("date", report_date.isoformat()),
        "title": title,
        "stream": stream,
        "stream_label": STREAM_LABELS.get(stream, stream),
        "planned_start": None,
        "planned_end": None,
        "status": entry.get("status", "planned"),
        "status_note": entry.get("note", ""),
        "is_conditional": bool(entry.get("trigger_condition")) or is_conditional(title),
        "reason_category": infer_reason_category(title, entry.get("note", ""), extra_reason_text),
        "source": "status_log_only",
    }


def build_records_for_date(
    *,
    event_date: dt.date,
    report_date: dt.date,
    events: list[dict[str, Any]],
    status_log: dict[str, Any],
    extra_reason_text: str = "",
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    date_text = event_date.isoformat()
    entries = status_entries_for_date(status_log, date_text)
    records = [make_calendar_record(event, report_date, extra_reason_text=extra_reason_text) for event in events]
    for entry in entries:
        if any(entry_matches_event(entry, event) for event in events):
            continue
        records.append(make_status_only_record(entry, report_date, extra_reason_text=extra_reason_text))
    return records, entries


def summarize_records(records: list[dict[str, Any]]) -> dict[str, Any]:
    counts = {"completed": 0, "partial": 0, "moved": 0, "conditional": 0, "unsynced": 0}
    reason_counts = {label: 0 for label in REASON_CATEGORIES}
    for record in records:
        status = record.get("status")
        if status in counts:
            counts[status] += 1
        elif status in {"pending_sync", "unsynced"}:
            counts["unsynced"] += 1
        if status in {"moved", "incomplete"}:
            reason = record.get("reason_category", "Unspecified")
            reason_counts[reason] = reason_counts.get(reason, 0) + 1
    completed_titles = [record["title"] for record in records if record.get("status") in {"completed", "partial"}]
    moved_titles = [record["title"] for record in records if record.get("status") == "moved"]
    return {
        "counts": counts,
        "reason_counts": reason_counts,
        "completed_highlights": completed_titles[:5],
        "moved_highlights": moved_titles[:5],
    }


def upsert_history_records(events_path: Path, records: list[dict[str, Any]]) -> int:
    existing = load_jsonl(events_path)
    by_key = {record_key(record): record for record in existing}
    for record in records:
        by_key[record_key(record)] = record
    merged = sorted(
        by_key.values(),
        key=lambda item: (
            item.get("event_date") or "",
            item.get("planned_start") or "",
            item.get("stream") or "",
            item.get("title") or "",
        ),
    )
    write_jsonl(events_path, merged)
    return len(merged)


def archive_report_history(
    *,
    report_date: dt.date,
    payload: dict[str, Any],
    status_log: dict[str, Any],
    history_dir: Path,
    calendar: str,
    tz: ZoneInfo,
    provider: str,
    events_file: Path | None,
    calendar_script: Path | None,
    source_report: Path | None = None,
) -> dict[str, Any]:
    paths = ensure_history_dirs(history_dir)
    extra_reason_text = "；".join(payload.get("execution", {}).get("reasons", []))
    affected_dates = {report_date}
    for candidate in payload.get("status_candidates", []):
        date_text = candidate.get("date")
        if not date_text:
            continue
        try:
            affected_dates.add(dt.date.fromisoformat(date_text))
        except ValueError:
            continue

    all_records: list[dict[str, Any]] = []
    daily_snapshot_records: list[dict[str, Any]] = []
    daily_events: list[dict[str, Any]] = []
    daily_status_entries: list[dict[str, Any]] = []

    for day in sorted(affected_dates):
        events = collect_primary_events_for_day(
            day=day,
            tz=tz,
            calendar=calendar,
            status_log=status_log,
            provider=provider,
            events_file=events_file,
            calendar_script=calendar_script,
        )
        records, status_entries = build_records_for_date(
            event_date=day,
            report_date=report_date,
            events=events,
            status_log=status_log,
            extra_reason_text=extra_reason_text,
        )
        all_records.extend(records)
        if day == report_date:
            daily_snapshot_records = records
            daily_events = events
            daily_status_entries = status_entries

    daily_summary = summarize_records(daily_snapshot_records)
    daily_archive = {
        "version": 1,
        "generated_at": dt.datetime.now(tz).isoformat(),
        "report_date": report_date.isoformat(),
        "source_report": display_path(source_report, history_dir.parent),
        "affected_dates": [day.isoformat() for day in sorted(affected_dates)],
        "report_payload": payload,
        "status_updates": daily_status_entries,
        "calendar_snapshot": {
            "calendar": calendar,
            "events": [serialize_event(event) for event in daily_events],
        },
        "plan_summary": daily_summary,
        "event_records": daily_snapshot_records,
    }

    daily_path = paths["daily"] / f"{report_date.isoformat()}.json"
    daily_path.write_text(json.dumps(daily_archive, ensure_ascii=False, indent=2), encoding="utf-8")
    total_records = upsert_history_records(paths["events"], all_records)
    return {
        "daily_path": str(daily_path),
        "events_path": str(paths["events"]),
        "affected_dates": [day.isoformat() for day in sorted(affected_dates)],
        "daily_record_count": len(daily_snapshot_records),
        "history_record_count": total_records,
    }
