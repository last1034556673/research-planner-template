"""Calendar event I/O adapters for file, macOS EventKit, and ICS sources."""

from __future__ import annotations

import datetime as dt
import json
import os
from pathlib import Path
import subprocess
from typing import Any

from .planner_data import normalize_calendar_provider


def load_event_records(
    *,
    start: dt.datetime,
    end: dt.datetime,
    tz_name: str,
    provider: str,
    events_file: Path | None = None,
    calendar_script: Path | None = None,
) -> list[dict[str, Any]]:
    provider = normalize_calendar_provider(provider)
    if provider == "file":
        return load_event_records_from_file(start=start, end=end, events_file=events_file)
    if provider == "macos":
        return load_event_records_from_macos(
            start=start,
            end=end,
            tz_name=tz_name,
            calendar_script=calendar_script,
        )
    if provider == "ics":
        return load_event_records_from_ics(start=start, end=end, events_file=events_file)
    raise ValueError(f"Unsupported calendar provider: {provider}")


def load_event_records_from_file(
    *,
    start: dt.datetime,
    end: dt.datetime,
    events_file: Path | None,
) -> list[dict[str, Any]]:
    if not events_file or not events_file.exists():
        return []
    payload = json.loads(events_file.read_text(encoding="utf-8"))
    records = []
    for item in payload:
        try:
            item_start = dt.datetime.fromisoformat(item["start"])
            item_end = dt.datetime.fromisoformat(item["end"])
        except (KeyError, ValueError):
            continue
        if item_end <= start or item_start >= end:
            continue
        records.append(item)
    return records


def load_event_records_from_macos(
    *,
    start: dt.datetime,
    end: dt.datetime,
    tz_name: str,
    calendar_script: Path | None,
) -> list[dict[str, Any]]:
    if not calendar_script or not calendar_script.exists():
        return []
    env = {
        **os.environ,
        "START_ISO": start.isoformat(),
        "END_ISO": end.isoformat(),
        "TZ_NAME": tz_name,
    }
    try:
        result = subprocess.run(
            ["swift", str(calendar_script)],
            check=True,
            capture_output=True,
            text=True,
            env=env,
        )
    except (OSError, subprocess.CalledProcessError):
        return []
    return json.loads(result.stdout)


def load_event_records_from_ics(
    *,
    start: dt.datetime,
    end: dt.datetime,
    events_file: Path | None,
) -> list[dict[str, Any]]:
    if not events_file or not events_file.exists():
        return []
    try:
        from icalendar import Calendar
    except ImportError:
        return []

    cal = Calendar.from_ical(events_file.read_bytes())
    records: list[dict[str, Any]] = []
    for component in cal.walk():
        if component.name != "VEVENT":
            continue
        dtstart = component.decoded("DTSTART", None)
        dtend = component.decoded("DTEND", None)
        if dtstart is None or dtend is None:
            continue
        if isinstance(dtstart, dt.date) and not isinstance(dtstart, dt.datetime):
            dtstart = dt.datetime.combine(dtstart, dt.time.min, tzinfo=start.tzinfo)
        if isinstance(dtend, dt.date) and not isinstance(dtend, dt.datetime):
            dtend = dt.datetime.combine(dtend, dt.time.min, tzinfo=start.tzinfo)
        if dtend <= start or dtstart >= end:
            continue
        records.append(
            {
                "calendar": str(component.get("CATEGORIES", "Research")),
                "title": str(component.get("SUMMARY", "Untitled Event")),
                "start": dtstart.isoformat(),
                "end": dtend.isoformat(),
                "isAllDay": False,
            }
        )
    return records
