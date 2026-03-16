#!/usr/bin/env python3
"""Generate the short-window research planning dashboard."""

from __future__ import annotations

import argparse
from collections import defaultdict
import datetime as dt
import html
import json
from pathlib import Path
import re
from typing import Any
from zoneinfo import ZoneInfo

from .calendar_io import load_event_records
from .planner_data import event_matches_status_entry, normalize_calendar_events, normalize_plan_details, normalize_status_log


DEFAULT_OUTPUT = "future_experiment_schedule.html"
DEFAULT_PRIMARY_CALENDAR = "Research"
DEFAULT_DETAILS_FILE = "plan_details.json"
DEFAULT_STATUS_FILE = "status_log.json"
DEFAULT_IGNORE = {"Birthdays", "Holidays", "China Holidays", "Chinese Holidays"}
DISPLAY_EXCLUDE_KEYWORDS = ("Lunch Break", "午餐", "break", "Focus Block")
WEEKDAY_LABELS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
SYNC_DEADLINE = dt.time(9, 30)

DEFAULT_STREAMS = [
    {"id": "rna", "label": "Analysis / Slides"},
    {"id": "cell", "label": "Cell Expansion"},
    {"id": "spheroid", "label": "3D Models"},
    {"id": "flow", "label": "Assays / Flow"},
    {"id": "material", "label": "Material Characterization"},
    {"id": "robot", "label": "Motion Tests"},
    {"id": "mouse", "label": "Animal Work"},
    {"id": "prep", "label": "Preparation / Follow-up"},
    {"id": "general", "label": "General"},
]

STATUS_META = {
    "completed": {"label": "Completed", "class": "status-completed"},
    "partial": {"label": "Partially Done", "class": "status-partial"},
    "moved": {"label": "Moved", "class": "status-moved"},
    "incomplete": {"label": "Incomplete", "class": "status-incomplete"},
    "pending_sync": {"label": "Pending Sync", "class": "status-pending-sync"},
    "unsynced": {"label": "Unsynced", "class": "status-unsynced"},
    "conditional": {"label": "Conditional", "class": "status-conditional"},
    "planned": {"label": "Planned", "class": "status-planned"},
}

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


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate an HTML dashboard for the active planning window.")
    parser.add_argument("--project-name", default="Research Planner", help="Project title shown in the header.")
    parser.add_argument("--calendar", default=DEFAULT_PRIMARY_CALENDAR, help="Primary calendar label.")
    parser.add_argument(
        "--calendar-provider",
        default="file",
        choices=("none", "file", "macos", "ics"),
        help="Calendar source provider.",
    )
    parser.add_argument("--events-file", help="JSON event source when using the file-based provider.")
    parser.add_argument("--calendar-script", help="Swift EventKit exporter when using the macOS provider.")
    parser.add_argument("--details-file", default=DEFAULT_DETAILS_FILE, help="Plan details JSON path.")
    parser.add_argument("--status-file", default=DEFAULT_STATUS_FILE, help="Status log JSON path.")
    parser.add_argument("--days", type=int, default=15, help="Number of days to render from start-date.")
    parser.add_argument("--start-date", default=dt.date.today().isoformat(), help="Render window start date.")
    parser.add_argument("--time-zone", default="Asia/Shanghai", help="IANA time zone.")
    parser.add_argument("--sync-deadline", default="09:30", help="Next-day sync deadline in HH:MM.")
    parser.add_argument("--output", default=DEFAULT_OUTPUT, help="HTML output path.")
    parser.add_argument("--include-past", action="store_true", help="Keep already-ended events in the rendered window.")
    parser.add_argument("--streams-json", help="Optional JSON array of stream descriptors.")
    return parser.parse_args()


def set_sync_deadline(value: str) -> None:
    global SYNC_DEADLINE
    hours_text, minutes_text = value.split(":", 1)
    SYNC_DEADLINE = dt.time(int(hours_text), int(minutes_text))


def load_plan_details(path: Path) -> dict[str, Any]:
    if not path.exists():
        return normalize_plan_details({"streams": DEFAULT_STREAMS, "experiments": [], "days": []})
    return normalize_plan_details(json.loads(path.read_text(encoding="utf-8")))


def load_status_log(path: Path) -> dict[str, Any]:
    if not path.exists():
        return normalize_status_log({"statuses": []})
    return normalize_status_log(json.loads(path.read_text(encoding="utf-8")))


def merged_streams(plan: dict[str, Any], extra_streams: list[dict[str, Any]] | None = None) -> list[dict[str, str]]:
    by_id = {item["id"]: {"id": item["id"], "label": item["label"]} for item in DEFAULT_STREAMS}
    for source in (plan.get("streams", []), extra_streams or []):
        for item in source:
            stream_id = item.get("id")
            label = item.get("label") or item.get("label_en")
            if stream_id and label:
                by_id[stream_id] = {"id": stream_id, "label": label}
    ordered = []
    for item in DEFAULT_STREAMS:
        if item["id"] in by_id:
            ordered.append(by_id.pop(item["id"]))
    ordered.extend(sorted(by_id.values(), key=lambda entry: entry["label"].lower()))
    return ordered


def categorize(title: str) -> str:
    title_lower = title.lower()
    for stream_id, keywords in GENERIC_CATEGORIZATION:
        if any(keyword in title_lower or keyword in title for keyword in keywords):
            return stream_id
    return "general"


def is_conditional(title: str) -> bool:
    markers = ("if ", "when ", "once ", "after confirmation", "if confluence", "若", "待确认", "条件")
    title_lower = title.lower()
    return any(marker in title_lower or marker in title for marker in markers)


def compact_title(title: str) -> str:
    title = re.sub(r"\s*\[[^\]]+\]\s*$", "", title).strip()
    title = re.sub(r"^[^\w\u4e00-\u9fff]+", "", title).strip()
    return title


def clip_text(text: str, limit: int = 40) -> str:
    if len(text) <= limit:
        return text
    return text[: limit - 1] + "…"


def weekday_label(value: dt.date | dt.datetime) -> str:
    date_value = value.date() if isinstance(value, dt.datetime) else value
    return WEEKDAY_LABELS[date_value.weekday()]


def parse_event(record: dict[str, Any], tz: ZoneInfo) -> dict[str, Any]:
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


def visible_primary(event: dict[str, Any]) -> bool:
    title_lower = event["title"].lower()
    return not any(keyword.lower() in title_lower for keyword in DISPLAY_EXCLUDE_KEYWORDS)


def normalize_match_text(text: str) -> str:
    text = compact_title(text)
    return re.sub(r"[\s\[\]（）()【】:：,，.。+＋/_-]+", "", text).lower()


def score_event_match(text: str, event: dict[str, Any]) -> int:
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


def best_event_match(text: str, events: list[dict[str, Any]]) -> dict[str, Any] | None:
    ranked = sorted(events, key=lambda item: (score_event_match(text, item), item["start"]), reverse=True)
    if not ranked:
        return None
    return ranked[0] if score_event_match(text, ranked[0]) >= 60 else None


def match_status_entry(event: dict[str, Any], entries: list[dict[str, Any]]) -> dict[str, Any] | None:
    for entry in entries:
        if event_matches_status_entry(entry, event):
            return entry
    return None


def annotate_event_status(event: dict[str, Any], status_entries: list[dict[str, Any]], now: dt.datetime) -> dict[str, Any]:
    entry = match_status_entry(event, status_entries)
    note = ""
    status_key = None
    blocking_reason = ""
    next_check_time = ""
    trigger_condition = ""
    condition_state = ""
    if entry:
        status_key = entry.get("status")
        note = entry.get("note", "")
        blocking_reason = entry.get("blocking_reason", "")
        next_check_time = entry.get("next_check_time", "")
        trigger_condition = entry.get("trigger_condition", "")
        condition_state = entry.get("condition_state", "")

    if not status_key:
        if event["end"] < now:
            sync_deadline = dt.datetime.combine(
                event["start"].date() + dt.timedelta(days=1),
                SYNC_DEADLINE,
                tzinfo=event["start"].tzinfo,
            )
            status_key = "pending_sync" if now < sync_deadline else "unsynced"
        elif event["conditional"]:
            status_key = "conditional"
        else:
            status_key = "planned"

    meta = STATUS_META.get(status_key, STATUS_META["planned"])
    clone = dict(event)
    clone["status_key"] = status_key
    clone["status_label"] = meta["label"]
    clone["status_class"] = meta["class"]
    clone["status_note"] = note
    clone["blocking_reason"] = blocking_reason
    clone["next_check_time"] = next_check_time
    clone["trigger_condition"] = trigger_condition
    clone["condition_state"] = condition_state
    return clone


def format_event_window(start: dt.datetime, end: dt.datetime) -> str:
    if start.date() == end.date():
        return f"{start:%m/%d} {weekday_label(start)} {start:%H:%M}-{end:%H:%M}"
    return f"{start:%m/%d %H:%M} -> {end:%m/%d %H:%M}"


def render_status_badge(status_key: str, label: str | None = None) -> str:
    meta = STATUS_META.get(status_key, STATUS_META["planned"])
    text = label or meta["label"]
    return f"<span class=\"status-badge {meta['class']}\">{html.escape(text)}</span>"


def match_descriptor_to_event(descriptor: dict[str, Any], events: list[dict[str, Any]]) -> dict[str, Any] | None:
    exact = descriptor.get("title_match")
    contains = descriptor.get("title_contains")
    title = descriptor.get("title")
    if exact:
        for event in events:
            if event["title"] == exact:
                return event
    if contains:
        for event in events:
            if contains in event["title"]:
                return event
    if title:
        return best_event_match(title, events)
    return None


def normalize_streams(raw_streams: Any, default_stream: str) -> list[str]:
    streams: list[str] = []
    if isinstance(raw_streams, list):
        for item in raw_streams:
            if isinstance(item, str) and item and item not in streams:
                streams.append(item)
    elif isinstance(raw_streams, str) and raw_streams:
        streams.append(raw_streams)
    if default_stream not in streams:
        streams.insert(0, default_stream)
    return streams


def enrich_events_with_plan_links(
    events: list[dict[str, Any]],
    plan: dict[str, Any],
    stream_map: dict[str, dict[str, str]],
) -> None:
    for experiment in plan.get("experiments", []):
        default_stream = experiment.get("stream", "general")
        for step in experiment.get("steps", []):
            match = match_descriptor_to_event(step, events)
            if not match:
                continue
            linked = normalize_streams(step.get("streams") or step.get("linked_streams"), default_stream)
            match["display_streams"] = list(dict.fromkeys(match.get("display_streams", []) + linked))
            match.setdefault("linked_experiments", []).append(experiment.get("title") or experiment.get("id", "Experiment"))
            if step.get("decision_rule") and not match.get("trigger_condition"):
                match["trigger_condition"] = step["decision_rule"]

    for day in plan.get("days", []):
        for task in day.get("tasks", []):
            match = match_descriptor_to_event(task, events)
            if not match:
                continue
            default_stream = task.get("stream") or match.get("stream", "general")
            linked = normalize_streams(task.get("streams") or task.get("linked_streams"), default_stream)
            match["display_streams"] = list(dict.fromkeys(match.get("display_streams", []) + linked))
            if task.get("condition") and not match.get("trigger_condition"):
                match["trigger_condition"] = task["condition"]

    for event in events:
        clean = [stream_id for stream_id in event.get("display_streams", []) if stream_id in stream_map]
        event["display_streams"] = clean or [event.get("stream", "general")]


def collect_window_events(
    *,
    calendar: str,
    provider: str,
    events_file: Path | None,
    calendar_script: Path | None,
    tz: ZoneInfo,
    window_start: dt.datetime,
    window_end: dt.datetime,
    status_entries: list[dict[str, Any]],
    include_past: bool,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dt.datetime]:
    now = dt.datetime.now(dt.timezone.utc).astimezone(tz)
    raw_records = load_event_records(
        start=window_start,
        end=window_end,
        tz_name=tz.key,
        provider=provider,
        events_file=events_file,
        calendar_script=calendar_script,
    )
    raw_records = normalize_calendar_events(raw_records)
    parsed = [parse_event(record, tz) for record in raw_records]
    primary = []
    external = []
    for event in parsed:
        if event["calendar"] in DEFAULT_IGNORE:
            continue
        if not include_past and event["end"] < now:
            continue
        event = annotate_event_status(event, status_entries, now)
        if event["calendar"] == calendar:
            primary.append(event)
        else:
            external.append(event)
    primary.sort(key=lambda item: (item["start"], item["end"], item["title"]))
    external.sort(key=lambda item: (item["start"], item["end"], item["title"]))
    return primary, external, now


def bucket_events_by_day(events: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for event in events:
        grouped[event["start"].date().isoformat()].append(event)
    for day_events in grouped.values():
        day_events.sort(key=lambda item: (item["start"], item["end"], item["title"]))
    return grouped


def collect_today_context(
    *,
    today: dt.date,
    primary_by_day: dict[str, list[dict[str, Any]]],
    external_by_day: dict[str, list[dict[str, Any]]],
    plan: dict[str, Any],
    stream_map: dict[str, dict[str, str]],
) -> dict[str, Any]:
    today_key = today.isoformat()
    plan_day = next((day for day in plan.get("days", []) if day.get("date") == today_key), None)
    primary_events = primary_by_day.get(today_key, [])
    external_events = external_by_day.get(today_key, [])
    tasks = []
    if plan_day:
        for task in plan_day.get("tasks", []):
            matched_event = match_descriptor_to_event(task, primary_events)
            title = matched_event["title"] if matched_event else task.get("title") or task.get("title_match") or task.get("title_contains") or "Planned task"
            stream_id = task.get("stream") or (matched_event["stream"] if matched_event else "general")
            status = matched_event["status_key"] if matched_event else ("conditional" if task.get("condition") else "planned")
            time_text = f"{matched_event['start']:%H:%M}-{matched_event['end']:%H:%M}" if matched_event else task.get("time", "Time TBD")
            tasks.append(
                {
                    "title": title,
                    "stream": stream_id,
                    "stream_label": stream_map.get(stream_id, {"label": "General"})["label"],
                    "time": time_text,
                    "status": status,
                    "deliverable": task.get("deliverable", ""),
                    "notes": task.get("notes", []),
                    "condition": task.get("condition", ""),
                    "status_note": matched_event.get("status_note", "") if matched_event else "",
                    "blocking_reason": matched_event.get("blocking_reason", "") if matched_event else "",
                    "trigger_condition": matched_event.get("trigger_condition", "") if matched_event else task.get("condition", ""),
                    "next_check_time": matched_event.get("next_check_time", "") if matched_event else "",
                    "date": today_key,
                    "history_link": f"../history/summaries/{today:%Y-%m}.html#day-{today_key}",
                }
            )
    else:
        for event in primary_events:
            tasks.append(
                {
                    "title": event["title"],
                    "stream": event["stream"],
                    "stream_label": stream_map.get(event["stream"], {"label": "General"})["label"],
                    "time": f"{event['start']:%H:%M}-{event['end']:%H:%M}",
                    "status": event["status_key"],
                    "deliverable": "",
                    "notes": [event["status_note"]] if event.get("status_note") else [],
                    "condition": event.get("trigger_condition", ""),
                    "status_note": event.get("status_note", ""),
                    "blocking_reason": event.get("blocking_reason", ""),
                    "trigger_condition": event.get("trigger_condition", ""),
                    "next_check_time": event.get("next_check_time", ""),
                    "date": today_key,
                    "history_link": f"../history/summaries/{today:%Y-%m}.html#day-{today_key}",
                }
            )
    return {
        "plan_day": plan_day,
        "primary_events": primary_events,
        "external_events": external_events,
        "tasks": tasks,
    }


def collect_conditional_items(
    plan: dict[str, Any],
    events: list[dict[str, Any]],
    stream_map: dict[str, dict[str, str]],
) -> list[dict[str, Any]]:
    items = []
    for experiment in plan.get("experiments", []):
        default_stream = experiment.get("stream", "general")
        for step in experiment.get("steps", []):
            matched = match_descriptor_to_event(step, events)
            is_flagged = bool(step.get("decision_rule")) or bool(step.get("condition"))
            if matched and (matched.get("status_key") == "conditional" or matched.get("trigger_condition")):
                is_flagged = True
            if not is_flagged:
                continue
            stream_id = step.get("stream") or default_stream
            items.append(
                {
                    "experiment": experiment.get("title", "Experiment"),
                    "title": matched["title"] if matched else step.get("title") or step.get("title_contains") or step.get("title_match") or "Conditional step",
                    "window": format_event_window(matched["start"], matched["end"]) if matched else step.get("date", "TBD"),
                    "window_date": matched["start"].date().isoformat() if matched else step.get("date", ""),
                    "stream_id": stream_id,
                    "stream_label": stream_map.get(stream_id, {"label": "General"})["label"],
                    "trigger_condition": matched.get("trigger_condition") if matched else step.get("decision_rule") or step.get("condition") or "Pending confirmation",
                    "condition_state": matched.get("condition_state") if matched and matched.get("condition_state") else ("Pending confirmation" if matched else "Pending confirmation"),
                    "blocking_reason": matched.get("blocking_reason") if matched and matched.get("blocking_reason") else ("Needs the day-of result before deciding." if matched else "Waiting for a future check or user update."),
                    "next_check_time": matched.get("next_check_time") if matched and matched.get("next_check_time") else (matched["start"].strftime("%m/%d %H:%M") if matched else step.get("date", "TBD")),
                }
            )
    items.sort(key=lambda item: (item["window"], item["title"]))
    return items


def collect_status_counts(events: list[dict[str, Any]]) -> dict[str, int]:
    counts = {key: 0 for key in STATUS_META}
    for event in events:
        counts[event.get("status_key", "planned")] += 1
    return counts


def render_reason_details(
    *,
    status_note: str = "",
    blocking_reason: str = "",
    trigger_condition: str = "",
    next_check_time: str = "",
) -> str:
    items = []
    if status_note:
        items.append(f"<p><strong>Status note:</strong> {html.escape(status_note)}</p>")
    if blocking_reason:
        items.append(f"<p><strong>Blocking reason:</strong> {html.escape(blocking_reason)}</p>")
    if trigger_condition:
        items.append(f"<p><strong>Trigger condition:</strong> {html.escape(trigger_condition)}</p>")
    if next_check_time:
        items.append(f"<p><strong>Next check:</strong> {html.escape(next_check_time)}</p>")
    if not items:
        return ""
    return (
        "<details class=\"reason-details\">"
        "<summary>Why this status?</summary>"
        f"{''.join(items)}"
        "</details>"
    )


def render_gantt(primary_events: list[dict[str, Any]], streams: list[dict[str, str]], days: list[dt.date]) -> str:
    stream_map = {item["id"]: item["label"] for item in streams}
    grouped: dict[str, dict[str, list[dict[str, Any]]]] = defaultdict(lambda: defaultdict(list))
    for event in primary_events:
        if not visible_primary(event):
            continue
        for stream_id in event.get("display_streams", [event["stream"]]):
            grouped[stream_id][event["start"].date().isoformat()].append(event)

    date_headers = "".join(
        "<div class=\"calendar-cell calendar-head\">"
        f"<span>{day:%m/%d}</span><small>{weekday_label(day)}</small>"
        "</div>"
        for day in days
    )
    rows = []
    for stream in streams:
        week_cells = []
        stream_count = 0
        for day in days:
            key = day.isoformat()
            cell_items = grouped.get(stream["id"], {}).get(key, [])
            stream_count += len(cell_items)
            cards = []
            for event in cell_items:
                cards.append(
                    "<article class=\"gantt-card filter-item "
                    f"{event['status_class']} {'gantt-conditional' if event['status_key'] == 'conditional' else ''}\" "
                    f"data-stream=\"{html.escape(stream['id'])}\" "
                    f"data-status=\"{html.escape(event['status_key'])}\" "
                    f"data-title=\"{html.escape((event['title'] + ' ' + event.get('status_note', '')).lower())}\" "
                    f"data-date=\"{event['start'].date().isoformat()}\">"
                    f"<div class=\"gantt-time\">{event['start']:%H:%M}-{event['end']:%H:%M}</div>"
                    f"<div class=\"gantt-title\">{html.escape(clip_text(event['short_title'], 42))}</div>"
                    f"<div class=\"gantt-state\">{html.escape(event['status_label'])}</div>"
                    f"{render_reason_details(status_note=event.get('status_note', ''), blocking_reason=event.get('blocking_reason', ''), trigger_condition=event.get('trigger_condition', ''), next_check_time=event.get('next_check_time', ''))}"
                    "</article>"
                )
            cell_html = "".join(cards) if cards else "<div class=\"cell-empty\"></div>"
            week_cells.append(f"<div class=\"calendar-cell\" data-date=\"{key}\">{cell_html}</div>")
        rows.append(
            f"<div class=\"gantt-row filter-row\" data-stream=\"{html.escape(stream['id'])}\" data-count=\"{stream_count}\">"
            f"<div class=\"gantt-stream\"><strong>{html.escape(stream['label'])}</strong><small>{sum(len(v) for v in grouped.get(stream['id'], {}).values())} blocks</small></div>"
            f"<div class=\"gantt-grid\">{''.join(week_cells)}</div>"
            "</div>"
        )

    rows_html = "".join(rows) if rows else "<div class=\"empty-state\">No primary events in the current window.</div>"
    return (
        "<section class=\"panel\" data-panel=\"window-overview\">"
        "<div class=\"panel-head\"><div><h2>Window Overview</h2><p>Past week, today, and the upcoming week in one grid.</p></div><button class=\"panel-toggle\" type=\"button\">Collapse</button></div>"
        "<div class=\"panel-body\"><div class=\"gantt-shell\">"
        "<div class=\"gantt-row gantt-row-head\">"
        "<div class=\"gantt-stream gantt-stream-head\">Workstream</div>"
        f"<div class=\"gantt-grid gantt-grid-head\">{date_headers}</div>"
        "</div>"
        f"{rows_html}"
        "</div></div>"
        "</section>"
    )


def render_today_plan(today_context: dict[str, Any], today: dt.date) -> str:
    plan_day = today_context["plan_day"]
    tasks = today_context["tasks"]
    external_events = today_context["external_events"]
    focus = plan_day.get("focus", "No explicit focus set.") if plan_day else "No explicit focus set."
    notes = plan_day.get("notes", []) if plan_day else []
    task_cards = []
    for task in tasks:
        notes_html = "".join(f"<li>{html.escape(note)}</li>" for note in task.get("notes", []) if note)
        notes_block = f"<ul>{notes_html}</ul>" if notes_html else ""
        condition = (
            f"<p class=\"task-condition\"><strong>Condition:</strong> {html.escape(task['condition'])}</p>"
            if task.get("condition")
            else ""
        )
        deliverable = (
            f"<p class=\"task-deliverable\"><strong>Deliverable:</strong> {html.escape(task['deliverable'])}</p>"
            if task.get("deliverable")
            else ""
        )
        task_cards.append(
            "<article class=\"today-task filter-item\" "
            f"data-stream=\"{html.escape(task['stream'])}\" "
            f"data-status=\"{html.escape(task['status'])}\" "
            f"data-title=\"{html.escape((task['title'] + ' ' + task.get('status_note', '') + ' ' + task.get('blocking_reason', '')).lower())}\" "
            f"data-date=\"{task.get('date', today.isoformat())}\">"
            f"<div class=\"today-task-top\"><span class=\"task-time\">{html.escape(task['time'])}</span>{render_status_badge(task['status'])}</div>"
            f"<h3>{html.escape(task['title'])}</h3>"
            f"<p class=\"task-stream\">{html.escape(task['stream_label'])}</p>"
            f"{deliverable}{condition}"
            f"{notes_block}"
            f"{render_reason_details(status_note=task.get('status_note', ''), blocking_reason=task.get('blocking_reason', ''), trigger_condition=task.get('trigger_condition', ''), next_check_time=task.get('next_check_time', ''))}"
            f"<p class=\"history-link\"><a href=\"{html.escape(task.get('history_link', '#'))}\">Open matching history day</a></p>"
            "</article>"
        )
    chip_parts = []
    for event in external_events:
        label = f"{event['start']:%H:%M}-{event['end']:%H:%M} {event['title']}"
        chip_parts.append(f"<span class=\"external-chip\">{html.escape(label)}</span>")
    chips = "".join(chip_parts)
    note_html = "".join(f"<li>{html.escape(note)}</li>" for note in notes if note)
    notes_block = f"<ul class=\"focus-notes\">{note_html}</ul>" if note_html else ""
    task_grid_html = "".join(task_cards) if task_cards else "<div class=\"empty-state\">No tasks were mapped for today.</div>"
    external_html = chips or "<span class=\"muted\">No competing calendar blocks.</span>"
    return (
        "<section class=\"panel today-panel\" data-panel=\"today-plan\">"
        f"<div class=\"panel-head\"><div><h2>Today Plan</h2><p>{today:%A, %B %d, %Y}</p></div><button class=\"panel-toggle\" type=\"button\">Collapse</button></div>"
        "<div class=\"panel-body\"><div class=\"today-meta\">"
        f"<div><span class=\"kicker\">Focus</span><strong>{html.escape(focus)}</strong></div>"
        f"<div><span class=\"kicker\">External commitments</span><div class=\"external-chip-wrap\">{external_html}</div></div>"
        "</div>"
        f"{notes_block}"
        f"<div class=\"today-task-grid\">{task_grid_html}</div></div>"
        "</section>"
    )


def render_conditional_panel(items: list[dict[str, Any]]) -> str:
    if not items:
        return (
            "<section class=\"panel\" data-panel=\"conditional-review\">"
            "<div class=\"panel-head\"><div><h2>Conditional Task Review</h2><p>Only unresolved or confirmation-dependent tasks appear here.</p></div><button class=\"panel-toggle\" type=\"button\">Collapse</button></div>"
            "<div class=\"panel-body\"><div class=\"empty-state\">No unresolved conditional tasks in the current window.</div></div>"
            "</section>"
        )
    cards = []
    for item in items:
        cards.append(
            "<article class=\"condition-card filter-item\" "
            f"data-stream=\"{html.escape(item.get('stream_id', 'general'))}\" "
            f"data-status=\"conditional\" "
            f"data-title=\"{html.escape((item['title'] + ' ' + item['blocking_reason']).lower())}\" "
            f"data-date=\"{html.escape(item.get('window_date', ''))}\">"
            f"<div class=\"condition-meta\"><span>{html.escape(item['stream_label'])}</span><span>{html.escape(item['window'])}</span></div>"
            f"<h3>{html.escape(item['title'])}</h3>"
            f"<p class=\"condition-exp\">{html.escape(item['experiment'])}</p>"
            f"<p><strong>Trigger:</strong> {html.escape(item['trigger_condition'])}</p>"
            f"<p><strong>State:</strong> {html.escape(item['condition_state'])}</p>"
            f"<p><strong>Blocker:</strong> {html.escape(item['blocking_reason'])}</p>"
            f"<p><strong>Next check:</strong> {html.escape(item['next_check_time'])}</p>"
            "</article>"
        )
    return (
        "<section class=\"panel\" data-panel=\"conditional-review\">"
        "<div class=\"panel-head\"><div><h2>Conditional Task Review</h2><p>Tasks that still need a decision, result, or prerequisite check.</p></div><button class=\"panel-toggle\" type=\"button\">Collapse</button></div>"
        f"<div class=\"panel-body\"><div class=\"condition-grid\">{''.join(cards)}</div></div>"
        "</section>"
    )


def render_experiment_timelines(plan: dict[str, Any], events: list[dict[str, Any]], stream_map: dict[str, dict[str, str]]) -> str:
    if not plan.get("experiments"):
        return (
            "<section class=\"panel\" data-panel=\"experiment-timelines\">"
            "<div class=\"panel-head\"><div><h2>Experiment Timelines</h2><p>Multi-step plans appear here once you define them in plan_details.json.</p></div><button class=\"panel-toggle\" type=\"button\">Collapse</button></div>"
            "<div class=\"panel-body\"><div class=\"empty-state\">No experiment timelines defined yet.</div></div>"
            "</section>"
        )
    blocks = []
    for experiment in plan.get("experiments", []):
        stream_label = stream_map.get(experiment.get("stream", "general"), {"label": "General"})["label"]
        steps_html = []
        for step in experiment.get("steps", []):
            matched = match_descriptor_to_event(step, events)
            status_key = matched["status_key"] if matched else ("conditional" if step.get("decision_rule") else "planned")
            window = format_event_window(matched["start"], matched["end"]) if matched else step.get("date", "TBD")
            notes = step.get("notes", [])
            notes_html = "".join(f"<li>{html.escape(note)}</li>" for note in notes if note)
            decision = step.get("decision_rule") or step.get("condition")
            decision_html = f"<p class=\"timeline-rule\"><strong>Decision rule:</strong> {html.escape(decision)}</p>" if decision else ""
            notes_block = f"<ul>{notes_html}</ul>" if notes_html else ""
            steps_html.append(
                "<article class=\"timeline-step filter-item\" "
                f"data-stream=\"{html.escape(experiment.get('stream', 'general'))}\" "
                f"data-status=\"{html.escape(status_key)}\" "
                f"data-title=\"{html.escape(((step.get('title') or step.get('title_match') or step.get('title_contains') or 'step') + ' ' + ' '.join(notes)).lower())}\" "
                f"data-date=\"{html.escape(step.get('date', ''))}\">"
                f"<div class=\"timeline-step-top\"><span>{html.escape(window)}</span>{render_status_badge(status_key)}</div>"
                f"<h4>{html.escape(step.get('title') or step.get('title_match') or step.get('title_contains') or 'Step')}</h4>"
                f"{decision_html}"
                f"{notes_block}"
                f"{render_reason_details(status_note=matched.get('status_note', '') if matched else '', blocking_reason=matched.get('blocking_reason', '') if matched else '', trigger_condition=matched.get('trigger_condition', '') if matched else decision or '', next_check_time=matched.get('next_check_time', '') if matched else '')}"
                "</article>"
            )
        blocks.append(
            "<article class=\"experiment-card filter-item\" "
            f"data-stream=\"{html.escape(experiment.get('stream', 'general'))}\" "
            f"data-status=\"planned\" "
            f"data-title=\"{html.escape((experiment.get('title', '') + ' ' + experiment.get('goal', '')).lower())}\">"
            f"<div class=\"experiment-head\"><span class=\"stream-pill\">{html.escape(stream_label)}</span><h3>{html.escape(experiment.get('title', experiment.get('id', 'Experiment')))}</h3></div>"
            f"<p class=\"experiment-goal\">{html.escape(experiment.get('goal', ''))}</p>"
            f"<div class=\"timeline-list\">{''.join(steps_html)}</div>"
            "</article>"
        )
    return (
        "<section class=\"panel\" data-panel=\"experiment-timelines\">"
        "<div class=\"panel-head\"><div><h2>Experiment Timelines</h2><p>Cross-day workflows, decision points, and follow-up windows.</p></div><button class=\"panel-toggle\" type=\"button\">Collapse</button></div>"
        f"<div class=\"panel-body\"><div class=\"experiment-grid\">{''.join(blocks)}</div></div>"
        "</section>"
    )


def render_html(
    *,
    project_name: str,
    days: list[dt.date],
    streams: list[dict[str, str]],
    primary_events: list[dict[str, Any]],
    external_events: list[dict[str, Any]],
    plan: dict[str, Any],
    today_context: dict[str, Any],
    conditional_items: list[dict[str, Any]],
) -> str:
    stream_map = {item["id"]: item for item in streams}
    counts = collect_status_counts(primary_events)
    stream_options = "".join(
        f"<option value=\"{html.escape(item['id'])}\">{html.escape(item['label'])}</option>"
        for item in streams
    )
    status_options = "".join(
        f"<option value=\"{html.escape(key)}\">{html.escape(meta['label'])}</option>"
        for key, meta in STATUS_META.items()
    )
    legend = "".join(
        f"<span class=\"legend-chip\"><i class=\"legend-dot {meta['class']}\"></i>{html.escape(meta['label'])}</span>"
        for meta in STATUS_META.values()
    )
    hero_range = f"{days[0]:%b %d} - {days[-1]:%b %d, %Y}"
    today = today_context["primary_events"][0]["start"].date() if today_context["primary_events"] else dt.datetime.now().date()
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{html.escape(project_name)} Planner</title>
  <style>
    :root {{
      --bg: #f4efe8;
      --paper: #fffdfa;
      --ink: #2d241f;
      --muted: #766960;
      --line: #e8ddd0;
      --shadow: 0 18px 45px rgba(86, 58, 37, 0.08);
      --radius: 28px;
      --rna: #c95e49;
      --cell: #1b8a83;
      --spheroid: #6469d8;
      --flow: #ee934d;
      --material: #2d6fab;
      --robot: #2e9b7d;
      --mouse: #9c4e44;
      --prep: #967321;
      --general: #67727e;
      --done: #17664f;
      --partial: #845b19;
      --moved: #8a6d61;
      --incomplete: #9e3f39;
      --pending: #7a5d2a;
      --unsynced: #8a4c4c;
      --conditional: #5a55b8;
      --planned: #5f6d7a;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      background:
        radial-gradient(circle at top left, rgba(242, 186, 138, 0.26), transparent 32%),
        linear-gradient(180deg, #f8f4ee 0%, var(--bg) 100%);
      color: var(--ink);
      font-family: "Avenir Next", "Segoe UI", sans-serif;
    }}
    .shell {{ max-width: 1580px; margin: 0 auto; padding: 28px; }}
    .hero {{
      background: linear-gradient(135deg, rgba(255,255,255,0.96), rgba(255,247,239,0.92));
      border: 1px solid rgba(146, 106, 77, 0.12);
      box-shadow: var(--shadow);
      border-radius: 34px;
      padding: 28px 30px;
      display: grid;
      gap: 22px;
    }}
    .hero h1 {{ margin: 0; font-size: 44px; line-height: 1.05; }}
    .hero p {{ margin: 0; color: var(--muted); }}
    .hero-top {{
      display: flex;
      justify-content: space-between;
      gap: 20px;
      align-items: flex-start;
      flex-wrap: wrap;
    }}
    .hero-stats {{
      display: grid;
      grid-template-columns: repeat(4, minmax(150px, 1fr));
      gap: 14px;
      width: 100%;
    }}
    .stat-card {{
      background: var(--paper);
      border: 1px solid var(--line);
      border-radius: 22px;
      padding: 16px 18px;
    }}
    .stat-card span {{
      display: block;
      font-size: 12px;
      letter-spacing: 0.12em;
      text-transform: uppercase;
      color: var(--muted);
      margin-bottom: 8px;
    }}
    .stat-card strong {{ font-size: 28px; }}
    .legend-bar {{
      display: flex;
      flex-wrap: wrap;
      gap: 10px 12px;
      align-items: center;
    }}
    .legend-chip {{
      display: inline-flex;
      align-items: center;
      gap: 8px;
      background: rgba(255,255,255,0.72);
      border: 1px solid var(--line);
      border-radius: 999px;
      padding: 8px 12px;
      color: var(--muted);
      font-size: 13px;
    }}
    .legend-dot {{
      display: inline-block;
      width: 10px;
      height: 10px;
      border-radius: 999px;
    }}
    .panel {{
      margin-top: 22px;
      background: rgba(255,253,250,0.95);
      border: 1px solid rgba(146, 106, 77, 0.12);
      box-shadow: var(--shadow);
      border-radius: var(--radius);
      padding: 24px;
    }}
    .panel-head {{
      display: flex;
      justify-content: space-between;
      gap: 16px;
      align-items: end;
      flex-wrap: wrap;
      margin-bottom: 18px;
    }}
    .panel-head h2 {{ margin: 0; font-size: 30px; }}
    .panel-head p {{ margin: 0; color: var(--muted); }}
    .panel-toggle {{
      border: 1px solid var(--line);
      background: #f8f1e9;
      border-radius: 999px;
      color: var(--ink);
      padding: 8px 14px;
      font: inherit;
      cursor: pointer;
    }}
    .panel.collapsed .panel-body {{ display: none; }}
    .controls-panel {{
      margin-top: 22px;
      display: grid;
      gap: 14px;
      grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
      align-items: end;
    }}
    .control {{
      display: grid;
      gap: 8px;
    }}
    .control label {{
      color: var(--muted);
      font-size: 12px;
      letter-spacing: 0.1em;
      text-transform: uppercase;
    }}
    .control input, .control select {{
      width: 100%;
      padding: 11px 12px;
      border-radius: 14px;
      border: 1px solid var(--line);
      background: rgba(255,255,255,0.92);
      font: inherit;
      color: var(--ink);
    }}
    .toggle-row {{
      display: flex;
      gap: 14px;
      flex-wrap: wrap;
      align-items: center;
      padding-bottom: 4px;
    }}
    .toggle-row label {{
      display: inline-flex;
      align-items: center;
      gap: 8px;
      color: var(--muted);
      font-size: 14px;
      letter-spacing: normal;
      text-transform: none;
    }}
    .gantt-shell {{
      overflow-x: auto;
      border-top: 1px solid var(--line);
      padding-top: 14px;
    }}
    .gantt-row {{
      display: grid;
      grid-template-columns: 280px minmax(900px, 1fr);
      gap: 14px;
      align-items: start;
      margin-bottom: 12px;
    }}
    .gantt-row-head {{
      position: sticky;
      top: 0;
      background: rgba(255, 253, 250, 0.92);
      z-index: 2;
      padding-bottom: 8px;
    }}
    .gantt-stream {{
      padding: 14px 12px;
      border-radius: 18px;
      background: rgba(250, 243, 235, 0.95);
      border: 1px solid var(--line);
      min-height: 100%;
    }}
    .gantt-stream strong {{
      display: block;
      font-size: 15px;
      margin-bottom: 6px;
    }}
    .gantt-stream small {{
      color: var(--muted);
      font-size: 13px;
    }}
    .gantt-stream-head {{
      font-size: 13px;
      letter-spacing: 0.12em;
      text-transform: uppercase;
      color: var(--muted);
    }}
    .gantt-grid {{
      display: grid;
      grid-template-columns: repeat({len(days)}, minmax(120px, 1fr));
      gap: 10px;
    }}
    .calendar-cell {{
      min-height: 112px;
      border-radius: 18px;
      padding: 10px;
      background: linear-gradient(180deg, rgba(255,255,255,0.95), rgba(250,244,238,0.9));
      border: 1px solid var(--line);
      display: flex;
      flex-direction: column;
      gap: 8px;
    }}
    .calendar-head {{
      min-height: auto;
      background: #f7f0e8;
      justify-content: center;
      align-items: start;
      font-weight: 700;
    }}
    .calendar-head small {{
      color: var(--muted);
      font-weight: 500;
    }}
    .cell-empty {{
      flex: 1;
      border: 1px dashed rgba(145, 120, 103, 0.25);
      border-radius: 14px;
      min-height: 42px;
      background: rgba(255,255,255,0.5);
    }}
    .gantt-card {{
      color: white;
      border-radius: 16px;
      padding: 10px 12px;
      box-shadow: 0 12px 22px rgba(51, 34, 22, 0.12);
      border: 1px solid rgba(255,255,255,0.12);
      background: var(--general);
    }}
    .filter-hidden {{ display: none !important; }}
    .gantt-card.status-moved,
    .legend-dot.status-moved {{ background: var(--moved); }}
    .gantt-card.status-completed,
    .legend-dot.status-completed {{ background: var(--done); }}
    .gantt-card.status-partial,
    .legend-dot.status-partial {{ background: var(--partial); }}
    .gantt-card.status-incomplete,
    .legend-dot.status-incomplete {{ background: var(--incomplete); }}
    .gantt-card.status-pending-sync,
    .legend-dot.status-pending-sync {{ background: var(--pending); }}
    .gantt-card.status-unsynced,
    .legend-dot.status-unsynced {{ background: var(--unsynced); }}
    .gantt-card.status-conditional,
    .legend-dot.status-conditional {{ background: var(--conditional); }}
    .gantt-card.status-planned,
    .legend-dot.status-planned {{ background: var(--planned); }}
    .gantt-conditional {{
      outline: 2px dashed rgba(255,255,255,0.7);
      outline-offset: -6px;
    }}
    .gantt-time {{
      font-size: 12px;
      opacity: 0.9;
      margin-bottom: 6px;
    }}
    .gantt-title {{
      font-size: 15px;
      font-weight: 700;
      line-height: 1.2;
    }}
    .gantt-state {{
      margin-top: 8px;
      font-size: 12px;
      opacity: 0.95;
    }}
    .today-meta {{
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 16px;
      margin-bottom: 16px;
    }}
    .kicker {{
      display: block;
      color: var(--muted);
      font-size: 12px;
      letter-spacing: 0.12em;
      text-transform: uppercase;
      margin-bottom: 6px;
    }}
    .external-chip-wrap {{
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
    }}
    .external-chip {{
      display: inline-flex;
      align-items: center;
      padding: 7px 10px;
      border-radius: 999px;
      background: #f3ebdf;
      border: 1px solid var(--line);
      color: var(--muted);
      font-size: 13px;
    }}
    .focus-notes {{
      margin: 0 0 18px;
      color: var(--muted);
      padding-left: 18px;
    }}
    .today-task-grid, .condition-grid, .experiment-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
      gap: 14px;
    }}
    .today-task, .condition-card, .experiment-card {{
      background: linear-gradient(180deg, rgba(255,255,255,0.96), rgba(249,243,237,0.9));
      border: 1px solid var(--line);
      border-radius: 22px;
      padding: 18px;
    }}
    .today-task-top, .timeline-step-top, .condition-meta {{
      display: flex;
      justify-content: space-between;
      gap: 10px;
      align-items: center;
      flex-wrap: wrap;
      margin-bottom: 10px;
    }}
    .task-time, .condition-meta, .timeline-step-top {{
      color: var(--muted);
      font-size: 13px;
    }}
    .today-task h3, .condition-card h3, .experiment-card h3 {{
      margin: 0 0 8px;
      font-size: 22px;
      line-height: 1.15;
    }}
    .task-stream, .condition-exp, .experiment-goal {{
      margin: 0 0 12px;
      color: var(--muted);
    }}
    .task-deliverable, .task-condition, .timeline-rule, .condition-card p {{
      margin: 8px 0;
    }}
    .status-badge {{
      display: inline-flex;
      align-items: center;
      padding: 7px 10px;
      border-radius: 999px;
      font-size: 12px;
      font-weight: 700;
      color: white;
      letter-spacing: 0.03em;
      text-transform: uppercase;
    }}
    .status-completed {{ background: var(--done); }}
    .status-partial {{ background: var(--partial); }}
    .status-moved {{ background: var(--moved); }}
    .status-incomplete {{ background: var(--incomplete); }}
    .status-pending-sync {{ background: var(--pending); }}
    .status-unsynced {{ background: var(--unsynced); }}
    .status-conditional {{ background: var(--conditional); }}
    .status-planned {{ background: var(--planned); }}
    .stream-pill {{
      display: inline-flex;
      padding: 6px 10px;
      border-radius: 999px;
      background: #f4ebdf;
      border: 1px solid var(--line);
      color: var(--muted);
      font-size: 12px;
      font-weight: 700;
      letter-spacing: 0.05em;
      text-transform: uppercase;
    }}
    .experiment-head {{
      display: flex;
      flex-direction: column;
      gap: 10px;
      margin-bottom: 10px;
    }}
    .timeline-list {{
      display: grid;
      gap: 10px;
    }}
    .timeline-step {{
      border: 1px solid var(--line);
      border-radius: 18px;
      padding: 14px;
      background: rgba(255,255,255,0.7);
    }}
    .timeline-step h4 {{
      margin: 0;
      font-size: 18px;
    }}
    .reason-details {{
      margin-top: 10px;
      border-top: 1px dashed rgba(145, 120, 103, 0.35);
      padding-top: 10px;
      color: var(--muted);
    }}
    .reason-details summary {{
      cursor: pointer;
      color: var(--ink);
      font-weight: 600;
      margin-bottom: 8px;
    }}
    .reason-details p {{ margin: 8px 0; }}
    .history-link {{
      margin: 12px 0 0;
      font-size: 13px;
    }}
    .history-link a {{
      color: var(--mouse);
      text-decoration: none;
      font-weight: 600;
    }}
    .empty-state {{
      padding: 22px;
      border-radius: 18px;
      border: 1px dashed rgba(135, 104, 82, 0.35);
      color: var(--muted);
      background: rgba(255,255,255,0.62);
    }}
    .muted {{ color: var(--muted); }}
    @media (max-width: 1080px) {{
      .hero-stats, .today-meta {{ grid-template-columns: 1fr 1fr; }}
      .gantt-row {{ grid-template-columns: 220px minmax(780px, 1fr); }}
    }}
    @media (max-width: 720px) {{
      .shell {{ padding: 16px; }}
      .hero h1 {{ font-size: 34px; }}
      .hero-stats, .today-meta {{ grid-template-columns: 1fr; }}
      .panel {{ padding: 18px; }}
      .gantt-row {{ grid-template-columns: 180px minmax(720px, 1fr); }}
    }}
  </style>
</head>
<body>
  <div class="shell">
    <section class="hero">
      <div class="hero-top">
        <div>
          <p class="kicker">Research Planner Template</p>
          <h1>{html.escape(project_name)}</h1>
          <p>{html.escape(hero_range)}. Short window for execution, review, and rolling replanning.</p>
        </div>
        <div class="legend-bar">{legend}</div>
      </div>
      <div class="hero-stats">
        <article class="stat-card"><span>Completed / Partial</span><strong>{counts['completed'] + counts['partial']}</strong></article>
        <article class="stat-card"><span>Moved / Incomplete</span><strong>{counts['moved'] + counts['incomplete']}</strong></article>
        <article class="stat-card"><span>Conditional</span><strong>{counts['conditional']}</strong></article>
        <article class="stat-card"><span>Pending Sync</span><strong>{counts['pending_sync'] + counts['unsynced']}</strong></article>
      </div>
    </section>
    <section class="panel controls-panel">
      <div class="control">
        <label for="stream-filter">Stream</label>
        <select id="stream-filter">
          <option value="">All streams</option>
          {stream_options}
        </select>
      </div>
      <div class="control">
        <label for="status-filter">Status</label>
        <select id="status-filter">
          <option value="">All statuses</option>
          {status_options}
        </select>
      </div>
      <div class="control">
        <label for="search-filter">Search</label>
        <input id="search-filter" type="search" placeholder="Title, blocker, note">
      </div>
      <div class="control toggle-row">
        <label><input id="hide-empty-streams" type="checkbox"> Hide empty streams</label>
        <label><input id="today-only" type="checkbox"> Today only</label>
      </div>
    </section>
    {render_gantt(primary_events, streams, days)}
    {render_today_plan(today_context, today)}
    {render_conditional_panel(conditional_items)}
    {render_experiment_timelines(plan, primary_events, stream_map)}
  </div>
  <script>
    const todayIso = "{today.isoformat()}";
    const streamFilter = document.getElementById("stream-filter");
    const statusFilter = document.getElementById("status-filter");
    const searchFilter = document.getElementById("search-filter");
    const hideEmptyStreams = document.getElementById("hide-empty-streams");
    const todayOnly = document.getElementById("today-only");

    function elementMatches(el) {{
      const stream = streamFilter.value.trim();
      const status = statusFilter.value.trim();
      const query = searchFilter.value.trim().toLowerCase();
      const onlyToday = todayOnly.checked;
      const elStream = (el.dataset.stream || "").trim();
      const elStatus = (el.dataset.status || "").trim();
      const elTitle = (el.dataset.title || "").toLowerCase();
      const elDate = (el.dataset.date || "").trim();
      if (stream && elStream !== stream) return false;
      if (status && elStatus !== status) return false;
      if (query && !elTitle.includes(query)) return false;
      if (onlyToday && elDate && elDate !== todayIso) return false;
      return true;
    }}

    function applyFilters() {{
      document.querySelectorAll(".filter-item").forEach((el) => {{
        el.classList.toggle("filter-hidden", !elementMatches(el));
      }});
      document.querySelectorAll(".filter-row").forEach((row) => {{
        const rowStream = row.dataset.stream || "";
        const streamMismatch = streamFilter.value && rowStream !== streamFilter.value;
        const empty = hideEmptyStreams.checked && row.dataset.count === "0";
        row.classList.toggle("filter-hidden", streamMismatch || empty);
      }});
      document.querySelectorAll(".calendar-cell").forEach((cell) => {{
        const cellDate = cell.dataset.date || "";
        cell.classList.toggle("filter-hidden", todayOnly.checked && cellDate && cellDate !== todayIso);
      }});
    }}

    [streamFilter, statusFilter, searchFilter, hideEmptyStreams, todayOnly].forEach((el) => {{
      el.addEventListener("input", applyFilters);
      el.addEventListener("change", applyFilters);
    }});
    document.querySelectorAll(".panel-toggle").forEach((button) => {{
      button.addEventListener("click", () => {{
        const panel = button.closest(".panel");
        if (panel) panel.classList.toggle("collapsed");
      }});
    }});
    applyFilters();
  </script>
</body>
</html>"""


def main() -> int:
    args = parse_args()
    set_sync_deadline(args.sync_deadline)
    tz = ZoneInfo(args.time_zone)
    start_date = dt.date.fromisoformat(args.start_date)
    days = [start_date + dt.timedelta(days=offset) for offset in range(args.days)]
    window_start = dt.datetime.combine(days[0], dt.time.min, tzinfo=tz)
    window_end = dt.datetime.combine(days[-1] + dt.timedelta(days=1), dt.time.min, tzinfo=tz)

    plan = load_plan_details(Path(args.details_file).expanduser().resolve())
    status_log = load_status_log(Path(args.status_file).expanduser().resolve())
    extra_streams = json.loads(args.streams_json) if args.streams_json else []
    streams = merged_streams(plan, extra_streams)
    stream_map = {item["id"]: item for item in streams}

    primary_events, external_events, now = collect_window_events(
        calendar=args.calendar,
        provider=args.calendar_provider,
        events_file=Path(args.events_file).expanduser().resolve() if args.events_file else None,
        calendar_script=Path(args.calendar_script).expanduser().resolve() if args.calendar_script else None,
        tz=tz,
        window_start=window_start,
        window_end=window_end,
        status_entries=status_log.get("statuses", []),
        include_past=args.include_past,
    )
    enrich_events_with_plan_links(primary_events, plan, stream_map)

    today = now.date()
    primary_by_day = bucket_events_by_day(primary_events)
    external_by_day = bucket_events_by_day(external_events)
    today_context = collect_today_context(
        today=today,
        primary_by_day=primary_by_day,
        external_by_day=external_by_day,
        plan=plan,
        stream_map=stream_map,
    )
    conditional_items = collect_conditional_items(plan, primary_events, stream_map)

    html_text = render_html(
        project_name=args.project_name,
        days=days,
        streams=streams,
        primary_events=primary_events,
        external_events=external_events,
        plan=plan,
        today_context=today_context,
        conditional_items=conditional_items,
    )
    output_path = Path(args.output).expanduser().resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html_text, encoding="utf-8")
    print(output_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
