#!/usr/bin/env python3
"""Suggest or apply schedule changes from a daily report."""

from __future__ import annotations

import argparse
import datetime as dt
import json
from collections import defaultdict, deque
from copy import deepcopy
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from .calendar_io import load_event_records
from .config import integration_settings, load_configs
from .planner_data import (
    build_task_index,
    compact_match_text,
    descriptor_matches_event_record,
    normalize_calendar_events,
    normalize_calendar_provider,
    normalize_plan_details,
    normalize_status_log,
    task_title,
)
from .report_parser import collect_events, detect_report_date, infer_status_candidates, load_text, parse_daily_report
from .workspace import build_paths


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Suggest or apply planner schedule changes from a daily report.")
    parser.add_argument("--input", required=True, help="Path to the saved daily report.")
    parser.add_argument("--workspace-root", required=True, help="Workspace root directory.")
    parser.add_argument("--calendar-provider", choices=("none", "file", "macos", "ics"), help="Override calendar provider.")
    parser.add_argument("--events-file", help="Override calendar event source file.")
    parser.add_argument("--calendar-script", help="Override calendar export script.")
    parser.add_argument("--apply", action="store_true", help="Apply the suggestions to plan details and file calendar events.")
    parser.add_argument("--output", help="Optional path for the suggestion JSON.")
    return parser.parse_args()


def load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return deepcopy(default)
    return json.loads(path.read_text(encoding="utf-8"))


def parse_clock(value: str, default: dt.time) -> dt.time:
    try:
        hours_text, minutes_text = value.split(":", 1)
        return dt.time(int(hours_text), int(minutes_text))
    except Exception:
        return default


def weekday_code(value: dt.date) -> str:
    return ["MO", "TU", "WE", "TH", "FR", "SA", "SU"][value.weekday()]


def is_allowed_workday(day: dt.date, constraints: dict[str, Any]) -> bool:
    if day.isoformat() in set(constraints.get("blocked_days", [])):
        return False
    weekend_rules = constraints.get("weekend_rules", {}) or {}
    if day.weekday() == 5 and not weekend_rules.get("saturday_lab_allowed", True):
        return False
    if day.weekday() == 6 and not weekend_rules.get("sunday_lab_allowed", True):
        return False
    return True


def interval_for(day: dt.date, start_text: str, end_text: str, tz: ZoneInfo) -> tuple[dt.datetime, dt.datetime]:
    start_time = parse_clock(start_text, dt.time(8, 0))
    end_time = parse_clock(end_text, dt.time(18, 0))
    return (
        dt.datetime.combine(day, start_time, tzinfo=tz),
        dt.datetime.combine(day, end_time, tzinfo=tz),
    )


def busy_intervals_for_day(
    day: dt.date,
    events: list[dict[str, Any]],
    constraints: dict[str, Any],
    tz: ZoneInfo,
    *,
    skip_event_ids: set[str] | None = None,
) -> list[tuple[dt.datetime, dt.datetime]]:
    skip_event_ids = skip_event_ids or set()
    intervals: list[tuple[dt.datetime, dt.datetime]] = []
    for event in events:
        event_id = event.get("event_id")
        if event_id and event_id in skip_event_ids:
            continue
        start = dt.datetime.fromisoformat(event["start"]).astimezone(tz)
        end = dt.datetime.fromisoformat(event["end"]).astimezone(tz)
        if start.date() == day:
            intervals.append((start, end))

    for meeting in constraints.get("meetings", []) or []:
        if not isinstance(meeting, dict):
            continue
        if meeting.get("day") == weekday_code(day) and meeting.get("start") and meeting.get("end"):
            intervals.append(interval_for(day, meeting["start"], meeting["end"], tz))

    for blocked in constraints.get("blocked_windows", []) or []:
        if not isinstance(blocked, dict):
            continue
        day_match = blocked.get("date") == day.isoformat() or blocked.get("day") == weekday_code(day)
        if day_match and blocked.get("start") and blocked.get("end"):
            intervals.append(interval_for(day, blocked["start"], blocked["end"], tz))

    return sorted(intervals, key=lambda item: item[0])


def find_slot(
    *,
    start_day: dt.date,
    preferred_start: dt.time,
    duration_minutes: int,
    constraints: dict[str, Any],
    events: list[dict[str, Any]],
    tz: ZoneInfo,
    skip_event_ids: set[str] | None = None,
) -> tuple[dt.datetime, dt.datetime, list[str]]:
    warnings: list[str] = []
    workday_start = parse_clock(constraints.get("workday_start", "08:00"), dt.time(8, 0))
    workday_end = parse_clock(constraints.get("workday_end", "18:00"), dt.time(18, 0))
    duration = dt.timedelta(minutes=max(duration_minutes, 30))
    candidate_day = start_day

    for _ in range(30):
        if not is_allowed_workday(candidate_day, constraints):
            warnings.append(f"{candidate_day.isoformat()} is blocked by weekend or blocked-day rules.")
            candidate_day += dt.timedelta(days=1)
            continue

        window_start = dt.datetime.combine(candidate_day, max(preferred_start, workday_start), tzinfo=tz)
        window_end = dt.datetime.combine(candidate_day, workday_end, tzinfo=tz)
        busy = busy_intervals_for_day(candidate_day, events, constraints, tz, skip_event_ids=skip_event_ids)
        probe = window_start
        while probe + duration <= window_end:
            conflict = next((interval for interval in busy if probe < interval[1] and probe + duration > interval[0]), None)
            if conflict is None:
                return probe, probe + duration, warnings
            probe = max(conflict[1], probe + dt.timedelta(minutes=30))

        candidate_day += dt.timedelta(days=1)

    raise RuntimeError("Unable to find a valid slot within the next 30 days.")


def event_for_task(task_id: str, events: list[dict[str, Any]], title: str) -> dict[str, Any] | None:
    ranked: list[tuple[int, dict[str, Any]]] = []
    for event in events:
        score, _ = descriptor_matches_event_record({"task_id": task_id, "aliases": [title], "title": title}, event)
        if score > 0:
            ranked.append((score, event))
    ranked.sort(key=lambda item: (item[0], item[1].get("start", "")), reverse=True)
    return ranked[0][1] if ranked else None


def reverse_dependencies(plan_index: dict[str, dict[str, Any]]) -> dict[str, list[str]]:
    graph: dict[str, list[str]] = defaultdict(list)
    for task_id, descriptor in plan_index.items():
        for dependency in descriptor.get("depends_on", []) or []:
            graph[dependency].append(task_id)
    return graph


def score_descriptor_match(text: str, descriptor: dict[str, Any]) -> int:
    left_raw = (text or "").strip().lower()
    left = compact_match_text(text)
    title_raw = task_title(descriptor).strip().lower()
    aliases_raw = {(item or "").strip().lower() for item in descriptor.get("aliases", []) if item}
    aliases_raw.add(title_raw)
    aliases = {compact_match_text(item) for item in aliases_raw if item}
    if not left_raw:
        return -1
    if left in aliases or left_raw in aliases_raw:
        return 100
    if any(left in alias or alias in left for alias in aliases if alias):
        return 75
    if any(left_raw in alias or alias in left_raw for alias in aliases_raw if alias):
        return 70
    left_tokens = set(filter(None, re_split_tokens(left_raw)))
    right_tokens = set()
    for alias in aliases_raw:
        right_tokens.update(filter(None, re_split_tokens(alias)))
    overlap = len(left_tokens & right_tokens)
    return overlap * 12


def re_split_tokens(value: str) -> list[str]:
    import re

    return re.findall(r"[\u4e00-\u9fffA-Za-z0-9]+", value)


def fallback_candidates_from_payload(
    payload: dict[str, Any],
    plan_index: dict[str, dict[str, Any]],
    report_date: dt.date,
) -> list[dict[str, Any]]:
    fallback: list[dict[str, Any]] = []
    reasons = "；".join(payload.get("execution", {}).get("reasons", [])).strip()
    for item in payload.get("execution", {}).get("incomplete", []):
        ranked = []
        for descriptor in plan_index.values():
            source_date = task_source_date(descriptor)
            if source_date > report_date:
                continue
            score = score_descriptor_match(item, descriptor)
            if score >= 24:
                ranked.append((score, descriptor))
        ranked.sort(key=lambda pair: (pair[0], pair[1].get("source_date", "")), reverse=True)
        if not ranked:
            continue
        descriptor = ranked[0][1]
        fallback.append(
            {
                "date": descriptor.get("source_date", report_date.isoformat()),
                "title_match": descriptor.get("title_match") or task_title(descriptor),
                "task_id": descriptor["task_id"],
                "aliases": descriptor.get("aliases", []),
                "status": "incomplete",
                "note": "；".join(part for part in [item, reasons] if part),
            }
        )
    return fallback


def seed_candidate_map(plan: dict[str, Any], status_log: dict[str, Any]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    plan_index = build_task_index(plan)
    for entry in status_log.get("statuses", []):
        if entry.get("status") not in {"moved", "incomplete"}:
            continue
        if entry.get("resolution_state") == "resolved":
            continue
        task_id = entry.get("task_id")
        if task_id and task_id in plan_index:
            result[task_id] = entry
            continue
        title_match = entry.get("title_match")
        for descriptor in plan_index.values():
            if title_match and title_match == descriptor.get("title_match"):
                result[descriptor["task_id"]] = entry
                break
    return result


def task_source_date(descriptor: dict[str, Any]) -> dt.date:
    raw = descriptor.get("source_date") or descriptor.get("date")
    return dt.date.fromisoformat(raw)


def apply_suggestion_to_plan(plan: dict[str, Any], changes: list[dict[str, Any]]) -> dict[str, Any]:
    updated = normalize_plan_details(plan)
    changes_by_task = {change["task_id"]: change for change in changes}

    for experiment in updated.get("experiments", []):
        for step in experiment.get("steps", []):
            change = changes_by_task.get(step.get("task_id"))
            if change:
                step["date"] = change["suggested_date"]

    for day in updated.get("days", []):
        moved_tasks: list[dict[str, Any]] = []
        keep_tasks: list[dict[str, Any]] = []
        for task in day.get("tasks", []):
            change = changes_by_task.get(task.get("task_id"))
            if change and change["current_date"] != change["suggested_date"]:
                moved_tasks.append(task)
            else:
                keep_tasks.append(task)
        day["tasks"] = keep_tasks
        for task in moved_tasks:
            target_day = next((item for item in updated["days"] if item.get("date") == changes_by_task[task["task_id"]]["suggested_date"]), None)
            if target_day is None:
                target_day = {"date": changes_by_task[task["task_id"]]["suggested_date"], "focus": "", "notes": [], "tasks": []}
                updated["days"].append(target_day)
            target_day.setdefault("tasks", []).append(task)

    updated["days"] = sorted(updated.get("days", []), key=lambda item: item.get("date", ""))
    updated["schema_version"] = max(int(updated.get("schema_version", 1)), 2)
    return updated


def apply_suggestion_to_events(events: list[dict[str, Any]], changes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    changes_by_task = {change["task_id"]: change for change in changes}
    updated: list[dict[str, Any]] = []
    for event in events:
        item = dict(event)
        change = changes_by_task.get(item.get("task_id"))
        if change:
            item["start"] = change["suggested_start"]
            item["end"] = change["suggested_end"]
        updated.append(item)
    return updated


def build_replan(
    *,
    plan: dict[str, Any],
    status_log: dict[str, Any],
    constraints: dict[str, Any],
    calendar_events: list[dict[str, Any]],
    candidates: list[dict[str, Any]],
    report_date: dt.date,
    tz: ZoneInfo,
    apply: bool,
    plan_path: Path,
    calendar_events_path: Path,
    provider: str,
) -> dict[str, Any]:
    plan = normalize_plan_details(plan)
    status_log = normalize_status_log(status_log)
    calendar_events = normalize_calendar_events(calendar_events, plan)
    plan_index = build_task_index(plan)
    by_dependency = reverse_dependencies(plan_index)

    root_candidates = seed_candidate_map(plan, status_log)
    for candidate in candidates:
        if candidate.get("status") not in {"moved", "incomplete"}:
            continue
        task_id = candidate.get("task_id")
        if not task_id:
            for descriptor in plan_index.values():
                exact = candidate.get("title_match")
                aliases = {compact_match_text(item) for item in candidate.get("aliases", [])}
                if exact and exact == descriptor.get("title_match"):
                    task_id = descriptor["task_id"]
                    break
                if aliases and aliases & {compact_match_text(item) for item in descriptor.get("aliases", [])}:
                    task_id = descriptor["task_id"]
                    break
        if task_id:
            candidate["task_id"] = task_id
            root_candidates[task_id] = candidate

    changes: list[dict[str, Any]] = []
    blocked: list[dict[str, Any]] = []
    warnings: list[str] = []
    planned_updates: dict[str, dict[str, Any]] = {}
    queue = deque(root_candidates.keys())

    while queue:
        task_id = queue.popleft()
        if task_id in planned_updates:
            continue
        descriptor = plan_index.get(task_id)
        if not descriptor:
            warnings.append(f"Unable to find task metadata for {task_id}.")
            continue
        source_date = task_source_date(descriptor)
        status_entry = root_candidates.get(task_id, {})
        reason = status_entry.get("note") or "Reported as incomplete and needs rescheduling."

        if descriptor.get("hard_timepoint"):
            blocked.append(
                {
                    "task_id": task_id,
                    "title": task_title(descriptor),
                    "current_date": source_date.isoformat(),
                    "reason": "This task is marked as a hard timepoint and was not moved automatically.",
                }
            )
            continue

        reference_event = event_for_task(task_id, calendar_events, task_title(descriptor))
        preferred_start = dt.time(9, 0)
        duration_minutes = 60
        skip_event_ids: set[str] = set()
        if reference_event:
            start_dt = dt.datetime.fromisoformat(reference_event["start"]).astimezone(tz)
            end_dt = dt.datetime.fromisoformat(reference_event["end"]).astimezone(tz)
            preferred_start = start_dt.time().replace(second=0, microsecond=0)
            duration_minutes = max(int((end_dt - start_dt).total_seconds() // 60), 30)
            if reference_event.get("event_id"):
                skip_event_ids.add(reference_event["event_id"])

        requested_day = source_date + dt.timedelta(days=1)
        if status_entry.get("requested_day"):
            requested_day = dt.date.fromisoformat(status_entry["requested_day"])

        suggested_start, suggested_end, slot_warnings = find_slot(
            start_day=requested_day,
            preferred_start=preferred_start,
            duration_minutes=duration_minutes,
            constraints=constraints,
            events=calendar_events,
            tz=tz,
            skip_event_ids=skip_event_ids,
        )
        warnings.extend(slot_warnings)

        dependent_ids = by_dependency.get(task_id, [])
        change = {
            "task_id": task_id,
            "title": task_title(descriptor),
            "current_date": source_date.isoformat(),
            "suggested_date": suggested_start.date().isoformat(),
            "suggested_start": suggested_start.isoformat(),
            "suggested_end": suggested_end.isoformat(),
            "reason": reason,
            "depends_on": descriptor.get("depends_on", []),
            "follow_on_tasks": dependent_ids,
            "apply_targets": ["plan_details"] + (["calendar_events"] if provider == "file" else []),
        }
        planned_updates[task_id] = change
        changes.append(change)

        for dependent_id in dependent_ids:
            if dependent_id in planned_updates:
                continue
            dependent = plan_index.get(dependent_id)
            if not dependent:
                continue
            dependency_note = f"Dependency {task_title(descriptor)} moved to {suggested_start.date().isoformat()}."
            dependent_source_date = task_source_date(dependent)
            offset_days = (dependent_source_date - source_date).days
            requested_day = suggested_start.date() + dt.timedelta(days=offset_days)
            root_candidates.setdefault(
                dependent_id,
                {
                    "task_id": dependent_id,
                    "status": "moved",
                    "note": dependency_note,
                    "requested_day": requested_day.isoformat(),
                },
            )
            if dependent.get("hard_timepoint"):
                blocked.append(
                    {
                        "task_id": dependent_id,
                        "title": task_title(dependent),
                        "current_date": task_source_date(dependent).isoformat(),
                        "reason": f"{dependency_note} Follow-on task is a hard timepoint and needs manual review.",
                    }
                )
                continue
            queue.append(dependent_id)

    suggestion = {
        "report_date": report_date.isoformat(),
        "changes": changes,
        "blocked": blocked,
        "warnings": sorted(set(warnings)),
    }

    if apply and changes:
        updated_plan = apply_suggestion_to_plan(plan, changes)
        plan_path.write_text(json.dumps(updated_plan, ensure_ascii=False, indent=2), encoding="utf-8")
        if provider == "file" and calendar_events_path.exists():
            updated_events = apply_suggestion_to_events(calendar_events, changes)
            calendar_events_path.write_text(json.dumps(updated_events, ensure_ascii=False, indent=2), encoding="utf-8")

    return suggestion


def main() -> int:
    args = parse_args()
    workspace_root = Path(args.workspace_root).expanduser().resolve()
    paths = build_paths(workspace_root)
    configs = load_configs(paths)
    integrations = integration_settings(paths, configs)
    provider = normalize_calendar_provider(args.calendar_provider or integrations["calendar_provider"])
    events_file = Path(args.events_file).expanduser().resolve() if args.events_file else integrations["event_source_path"]
    calendar_script = Path(args.calendar_script).expanduser().resolve() if args.calendar_script else integrations["calendar_script"]

    raw_report = load_text(Path(args.input).expanduser().resolve())
    report_date_text = detect_report_date(raw_report) or dt.datetime.now(dt.timezone.utc).astimezone(ZoneInfo(configs["project"]["timezone"])).date().isoformat()
    report_date = dt.date.fromisoformat(report_date_text)
    payload = parse_daily_report(raw_report, report_date_text)
    tz = ZoneInfo(configs["project"]["timezone"])

    primary_events = collect_events(
        report_date=report_date,
        tz=tz,
        calendar=integrations["primary_calendar_name"],
        provider=provider,
        events_file=events_file,
        calendar_script=calendar_script,
    )
    plan = load_json(paths.plan_details, {"streams": [], "experiments": [], "days": []})
    plan_index = build_task_index(normalize_plan_details(plan))
    candidates = infer_status_candidates(payload, primary_events)
    known_task_ids = {candidate.get("task_id") for candidate in candidates if candidate.get("task_id")}
    for candidate in fallback_candidates_from_payload(payload, plan_index, report_date):
        if candidate.get("task_id") not in known_task_ids:
            candidates.append(candidate)
    status_log = load_json(paths.status_log, {"statuses": []})
    calendar_events = load_event_records(
        start=dt.datetime.combine(report_date - dt.timedelta(days=14), dt.time.min, tzinfo=tz),
        end=dt.datetime.combine(report_date + dt.timedelta(days=30), dt.time.min, tzinfo=tz),
        tz_name=tz.key,
        provider=provider,
        events_file=events_file,
        calendar_script=calendar_script,
    )
    suggestion = build_replan(
        plan=plan,
        status_log=status_log,
        constraints=configs["constraints"],
        calendar_events=calendar_events,
        candidates=candidates,
        report_date=report_date,
        tz=tz,
        apply=args.apply,
        plan_path=paths.plan_details,
        calendar_events_path=events_file,
        provider=provider,
    )

    output_path = Path(args.output).expanduser().resolve() if args.output else paths.replan_suggestions_dir / f"{report_date.isoformat()}.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(suggestion, ensure_ascii=False, indent=2), encoding="utf-8")
    print(output_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
