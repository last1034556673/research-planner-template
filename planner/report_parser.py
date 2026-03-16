#!/usr/bin/env python3
"""Parse a daily report and update status/history files."""

from __future__ import annotations

import argparse
import datetime as dt
import json
from pathlib import Path
import re
from typing import Any
from zoneinfo import ZoneInfo

from .calendar_io import load_event_records
from .dashboard import DEFAULT_IGNORE, compact_title, parse_event, score_event_match
from .history import DEFAULT_HISTORY_DIR, archive_report_history


DEFAULT_CALENDAR = "Research"
DEFAULT_STATUS_FILE = "status_log.json"
DEFAULT_TIME_ZONE = "Asia/Shanghai"
DEFAULT_TEMPLATE = """Date: YYYY-MM-DD

Experiment Execution:
- Completed:
- Not completed:
- Reasons:

Key Status:
- Cells / samples:
- Animals:
- Instruments / reagents:

Analysis & Writing:
- 

Tomorrow Must-Do:
- 
"""

SECTION_ALIASES = {
    "实验执行": "execution",
    "Experiment Execution": "execution",
    "关键状态": "status",
    "Key Status": "status",
    "数据分析与写作": "analysis",
    "Analysis & Writing": "analysis",
    "明天必须做": "tomorrow",
    "Tomorrow Must-Do": "tomorrow",
}

FIELD_ALIASES = {
    "完成了": "completed",
    "Completed": "completed",
    "没完成": "incomplete",
    "Not completed": "incomplete",
    "原因": "reasons",
    "Reasons": "reasons",
    "细胞": "cells",
    "Cells / samples": "cells",
    "细胞/样本": "cells",
    "动物": "animals",
    "Animals": "animals",
    "仪器/试剂": "instruments",
    "Instruments / reagents": "instruments",
}

MOVE_HINTS = (
    "reschedule",
    "move",
    "delay",
    "push",
    "weekend",
    "monday",
    "tomorrow",
    "next",
    "顺延",
    "改到",
    "延期",
    "延后",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Parse the fixed-format daily report.")
    parser.add_argument("--input", help="Path to a markdown/text daily report.")
    parser.add_argument("--date", help="Optional report date in YYYY-MM-DD. Falls back to the report body or today.")
    parser.add_argument("--calendar", default=DEFAULT_CALENDAR, help="Primary calendar name.")
    parser.add_argument(
        "--calendar-provider",
        default="none",
        choices=("none", "macos"),
        help="Calendar source provider.",
    )
    parser.add_argument("--events-file", help="JSON event source when using the file-based provider.")
    parser.add_argument("--calendar-script", help="Swift EventKit exporter when using the macOS provider.")
    parser.add_argument("--status-file", default=DEFAULT_STATUS_FILE, help="Path to status log JSON.")
    parser.add_argument("--history-dir", default=DEFAULT_HISTORY_DIR, help="History archive directory.")
    parser.add_argument("--time-zone", default=DEFAULT_TIME_ZONE, help="IANA time zone name.")
    parser.add_argument("--sync-deadline", default="09:30", help="Reserved for caller compatibility.")
    parser.add_argument("--output", help="Optional output JSON path.")
    parser.add_argument("--write-status-log", action="store_true", help="Merge inferred statuses into the status log.")
    parser.add_argument("--write-history", action="store_true", help="Write the parsed report into the history archive.")
    parser.add_argument("--print-template", action="store_true", help="Print the fixed daily report template and exit.")
    return parser.parse_args()


def load_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def default_template() -> str:
    return DEFAULT_TEMPLATE


def display_path(path: Path, base: Path | None) -> str:
    if base is not None:
        try:
            return str(path.relative_to(base))
        except ValueError:
            pass
    return str(path)


def empty_payload(report_date: str) -> dict[str, Any]:
    return {
        "date": report_date,
        "execution": {"completed": [], "incomplete": [], "reasons": []},
        "status": {"cells": [], "animals": [], "instruments": []},
        "analysis": [],
        "tomorrow": [],
    }


def split_inline_items(text: str) -> list[str]:
    value = text.strip()
    if not value:
        return []
    parts = [item.strip(" -") for item in re.split(r"[；;]\s*", value) if item.strip()]
    return parts or [value]


def parse_daily_report(text: str, report_date: str) -> dict[str, Any]:
    payload = empty_payload(report_date)
    current_section: str | None = None
    current_field: str | None = None
    section_pattern = "|".join(re.escape(item) for item in SECTION_ALIASES)
    field_pattern = "|".join(re.escape(item) for item in FIELD_ALIASES)

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith("Date") or line.startswith("日期"):
            continue

        section_match = re.match(rf"^({section_pattern})\s*[：:]\s*$", line)
        if section_match:
            current_section = SECTION_ALIASES[section_match.group(1)]
            current_field = None
            continue

        field_match = re.match(rf"^[-*]?\s*({field_pattern})\s*[：:]\s*(.*)$", line)
        if field_match and current_section in {"execution", "status"}:
            current_field = FIELD_ALIASES[field_match.group(1)]
            inline_items = split_inline_items(field_match.group(2))
            if current_section == "execution":
                payload["execution"][current_field].extend(inline_items)
            else:
                payload["status"][current_field].extend(inline_items)
            continue

        bullet_match = re.match(r"^[-*]\s+(.*)$", line)
        bullet_text = bullet_match.group(1).strip() if bullet_match else line

        if current_section == "execution" and current_field:
            payload["execution"][current_field].extend(split_inline_items(bullet_text))
        elif current_section == "status" and current_field:
            payload["status"][current_field].extend(split_inline_items(bullet_text))
        elif current_section == "analysis":
            payload["analysis"].extend(split_inline_items(bullet_text))
        elif current_section == "tomorrow":
            payload["tomorrow"].extend(split_inline_items(bullet_text))

    return payload


def detect_report_date(text: str) -> str | None:
    for raw_line in text.splitlines():
        line = raw_line.strip()
        match = re.match(r"^(Date|日期)\s*[：:]\s*(\d{4}-\d{2}-\d{2})\s*$", line)
        if match:
            return match.group(2)
    return None


def normalize_match_text(text: str) -> str:
    text = compact_title(text)
    return re.sub(r"[\s\[\]（）()【】:：,，.。+＋/_-]+", "", text).lower()


def collect_events(
    *,
    report_date: dt.date,
    tz: ZoneInfo,
    calendar: str,
    provider: str,
    events_file: Path | None,
    calendar_script: Path | None,
) -> list[dict[str, Any]]:
    start = dt.datetime.combine(report_date - dt.timedelta(days=2), dt.time.min, tzinfo=tz)
    end = dt.datetime.combine(report_date + dt.timedelta(days=3), dt.time.min, tzinfo=tz)
    raw_events = load_event_records(
        start=start,
        end=end,
        tz_name=tz.key,
        provider=provider,
        events_file=events_file,
        calendar_script=calendar_script,
    )
    events = [parse_event(record, tz) for record in raw_events]
    return [event for event in events if event["calendar"] == calendar and event["calendar"] not in DEFAULT_IGNORE]


def best_event_match(text: str, events: list[dict[str, Any]], report_date: dt.date) -> dict[str, Any] | None:
    ranked = sorted(
        events,
        key=lambda item: (score_event_match(text, item), -abs((item["start"].date() - report_date).days)),
        reverse=True,
    )
    if not ranked:
        return None
    return ranked[0] if score_event_match(text, ranked[0]) >= 60 else None


def infer_status_candidates(payload: dict[str, Any], events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    report_date = dt.date.fromisoformat(payload["date"])
    reasons = "；".join(payload["execution"]["reasons"]).strip()
    candidates: list[dict[str, Any]] = []

    for item in payload["execution"]["completed"]:
        matched = best_event_match(item, events, report_date)
        if not matched:
            continue
        candidates.append(
            {
                "date": matched["start"].date().isoformat(),
                "title_match": matched["title"],
                "status": "completed",
                "note": item,
            }
        )

    for item in payload["execution"]["incomplete"]:
        matched = best_event_match(item, events, report_date)
        if not matched:
            continue
        status = "moved" if any(hint in (item + " " + reasons).lower() or hint in item or hint in reasons for hint in MOVE_HINTS) else "incomplete"
        note_parts = [item]
        if reasons:
            note_parts.append(reasons)
        candidates.append(
            {
                "date": matched["start"].date().isoformat(),
                "title_match": matched["title"],
                "status": status,
                "note": "；".join(part for part in note_parts if part),
            }
        )
    return candidates


def load_status_log(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"statuses": []}
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload.setdefault("statuses", [])
    return payload


def merge_status_candidates(status_log: dict[str, Any], candidates: list[dict[str, Any]]) -> dict[str, Any]:
    statuses = status_log.setdefault("statuses", [])
    for candidate in candidates:
        matched_index = None
        for idx, entry in enumerate(statuses):
            same_date = entry.get("date") == candidate.get("date")
            same_title = entry.get("title_match") == candidate.get("title_match")
            if same_date and same_title:
                matched_index = idx
                break
        if matched_index is None:
            statuses.append(candidate)
        else:
            merged = dict(statuses[matched_index])
            merged.update(candidate)
            statuses[matched_index] = merged
    statuses.sort(key=lambda item: (item.get("date", ""), item.get("title_match") or item.get("title_contains") or ""))
    return status_log


def main() -> int:
    args = parse_args()
    if args.print_template:
        print(default_template())
        return 0

    if not args.input:
        raise SystemExit("Missing --input. Use --print-template to view the fixed report template.")

    input_path = Path(args.input).expanduser().resolve()
    status_path = Path(args.status_file).expanduser().resolve()
    history_dir = Path(args.history_dir).expanduser().resolve()
    output_path = Path(args.output).expanduser().resolve() if args.output else None
    tz = ZoneInfo(args.time_zone)
    events_file = Path(args.events_file).expanduser().resolve() if args.events_file else None
    calendar_script = Path(args.calendar_script).expanduser().resolve() if args.calendar_script else None
    raw_text = load_text(input_path)
    report_date_text = args.date or detect_report_date(raw_text) or dt.date.today().isoformat()
    report_date = dt.date.fromisoformat(report_date_text)
    workspace_base = history_dir.parent if history_dir.name == "history" else input_path.parent

    payload = parse_daily_report(raw_text, report_date.isoformat())
    events = collect_events(
        report_date=report_date,
        tz=tz,
        calendar=args.calendar,
        provider=args.calendar_provider,
        events_file=events_file,
        calendar_script=calendar_script,
    )
    payload["status_candidates"] = infer_status_candidates(payload, events)
    status_log = load_status_log(status_path)
    effective_status_log = merge_status_candidates(
        json.loads(json.dumps(status_log, ensure_ascii=False)),
        payload["status_candidates"],
    )

    if args.write_status_log:
        status_path.parent.mkdir(parents=True, exist_ok=True)
        status_path.write_text(json.dumps(effective_status_log, ensure_ascii=False, indent=2), encoding="utf-8")
        payload["status_log_updated"] = display_path(status_path, workspace_base)

    if args.write_history:
        archive_info = archive_report_history(
            report_date=report_date,
            payload=payload,
            status_log=effective_status_log,
            history_dir=history_dir,
            calendar=args.calendar,
            tz=tz,
            provider=args.calendar_provider,
            events_file=events_file,
            calendar_script=calendar_script,
            source_report=input_path,
        )
        payload["history_archive_updated"] = archive_info

    output_text = json.dumps(payload, ensure_ascii=False, indent=2)
    if output_path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(output_text, encoding="utf-8")
        print(output_path)
    else:
        print(output_text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
