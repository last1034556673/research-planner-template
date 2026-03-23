"""Tests for HTML rendering output validity in dashboard and history_summary."""

from __future__ import annotations

import datetime as dt
import unittest
from zoneinfo import ZoneInfo

from planner.dashboard import (
    collect_status_counts,
    render_conditional_panel,
    render_experiment_timelines,
    render_gantt,
    render_html,
    render_today_plan,
    STATUS_META,
)
from planner.history_summary import (
    compute_stats,
    month_week_buckets,
    normalize_record,
    quarter_week_buckets,
    reason_counts,
    render_bucket_overview,
    render_daily_review,
    render_group_review,
    render_html as render_summary_html,
    year_month_buckets,
)


TZ = ZoneInfo("Asia/Shanghai")


def _make_event(title: str, date: str = "2026-03-15", start_hour: int = 9, end_hour: int = 10, **extra) -> dict:
    start = dt.datetime(int(date[:4]), int(date[5:7]), int(date[8:10]), start_hour, 0, tzinfo=TZ)
    end = dt.datetime(int(date[:4]), int(date[5:7]), int(date[8:10]), end_hour, 0, tzinfo=TZ)
    event = {
        "id": f"Research|{start.isoformat()}|{title}",
        "calendar": "Research",
        "event_id": None,
        "task_id": None,
        "title": title,
        "short_title": title,
        "start": start,
        "end": end,
        "is_all_day": False,
        "stream": "general",
        "display_streams": ["general"],
        "conditional": False,
        "aliases": [title],
        "status_key": "planned",
        "status_label": "Planned",
        "status_class": "status-planned",
        "status_note": "",
        "blocking_reason": "",
        "next_check_time": "",
        "trigger_condition": "",
        "condition_state": "",
    }
    event.update(extra)
    return event


def _make_record(title: str, date: str = "2026-03-15", status: str = "completed", stream: str = "cell") -> dict:
    record = {
        "event_date": date,
        "title": title,
        "status": status,
        "stream": stream,
        "status_note": "",
        "planned_start": f"{date}T09:00:00+08:00",
    }
    return normalize_record(record)


class RenderGanttTests(unittest.TestCase):
    def test_produces_valid_html_structure(self) -> None:
        events = [_make_event("Task A"), _make_event("Task B", date="2026-03-16")]
        streams = [{"id": "general", "label": "General"}]
        days = [dt.date(2026, 3, 15), dt.date(2026, 3, 16)]
        html = render_gantt(events, streams, days)
        self.assertIn("Window Overview", html)
        self.assertIn("section", html)
        self.assertIn("gantt-row", html)

    def test_empty_events_shows_empty_cells(self) -> None:
        streams = [{"id": "general", "label": "General"}]
        days = [dt.date(2026, 3, 15)]
        html = render_gantt([], streams, days)
        self.assertIn("cell-empty", html)
        self.assertIn("0 blocks", html)


class RenderTodayPlanTests(unittest.TestCase):
    def test_renders_tasks(self) -> None:
        context = {
            "plan_day": {"focus": "Test focus", "notes": ["Note 1"]},
            "primary_events": [_make_event("Task")],
            "external_events": [],
            "tasks": [
                {
                    "title": "Task A",
                    "stream": "cell",
                    "stream_label": "Cell Expansion",
                    "time": "09:00-10:00",
                    "status": "planned",
                    "deliverable": "Result X",
                    "notes": [],
                    "condition": "",
                    "status_note": "",
                    "blocking_reason": "",
                    "trigger_condition": "",
                    "next_check_time": "",
                    "date": "2026-03-15",
                    "history_link": "#",
                },
            ],
        }
        html = render_today_plan(context, dt.date(2026, 3, 15))
        self.assertIn("Today Plan", html)
        self.assertIn("Task A", html)
        self.assertIn("Test focus", html)

    def test_no_tasks_shows_empty_state(self) -> None:
        context = {
            "plan_day": None,
            "primary_events": [],
            "external_events": [],
            "tasks": [],
        }
        html = render_today_plan(context, dt.date(2026, 3, 15))
        self.assertIn("empty-state", html)


class RenderConditionalPanelTests(unittest.TestCase):
    def test_no_items_shows_empty(self) -> None:
        html = render_conditional_panel([])
        self.assertIn("No unresolved conditional tasks", html)

    def test_with_items_renders_cards(self) -> None:
        items = [{
            "experiment": "Exp 1",
            "title": "If ready: proceed",
            "window": "03/15 Mon 09:00-10:00",
            "window_date": "2026-03-15",
            "stream_id": "cell",
            "stream_label": "Cell Expansion",
            "trigger_condition": "Confluence > 80%",
            "condition_state": "Pending",
            "blocking_reason": "Needs check",
            "next_check_time": "03/15 09:00",
        }]
        html = render_conditional_panel(items)
        self.assertIn("If ready: proceed", html)
        self.assertIn("Confluence", html)


class RenderExperimentTimelinesTests(unittest.TestCase):
    def test_no_experiments_shows_empty(self) -> None:
        html = render_experiment_timelines({"experiments": []}, [], {})
        self.assertIn("No experiment timelines defined", html)

    def test_with_experiment(self) -> None:
        plan = {
            "experiments": [{
                "id": "exp1",
                "title": "GFP Reporter",
                "stream": "cell",
                "goal": "Expand cells",
                "steps": [
                    {"title": "Seed cells", "date": "2026-03-15"},
                ],
            }],
        }
        events = [_make_event("Seed cells")]
        stream_map = {"cell": {"id": "cell", "label": "Cell Expansion"}}
        html = render_experiment_timelines(plan, events, stream_map)
        self.assertIn("GFP Reporter", html)
        self.assertIn("Seed cells", html)


class RenderFullDashboardTests(unittest.TestCase):
    def test_produces_complete_html_document(self) -> None:
        events = [_make_event("Task A"), _make_event("Task B", date="2026-03-16")]
        days = [dt.date(2026, 3, 15), dt.date(2026, 3, 16)]
        streams = [{"id": "general", "label": "General"}]
        today_context = {
            "plan_day": None,
            "primary_events": events[:1],
            "external_events": [],
            "tasks": [],
        }
        html = render_html(
            project_name="Test Project",
            days=days,
            streams=streams,
            primary_events=events,
            external_events=[],
            plan={"experiments": [], "days": []},
            today_context=today_context,
            conditional_items=[],
        )
        self.assertIn("<!DOCTYPE html>", html)
        self.assertIn("Test Project", html)
        self.assertIn("<style>", html)
        self.assertIn("</style>", html)
        self.assertIn("<script>", html)
        self.assertIn("</html>", html)
        # Check CSS was loaded from external file
        self.assertIn("--bg:", html)
        self.assertIn("gantt-grid", html)

    def test_escapes_html_in_project_name(self) -> None:
        events = [_make_event("Task")]
        today_context = {
            "plan_day": None,
            "primary_events": events,
            "external_events": [],
            "tasks": [],
        }
        html = render_html(
            project_name='<script>alert("xss")</script>',
            days=[dt.date(2026, 3, 15)],
            streams=[{"id": "general", "label": "General"}],
            primary_events=events,
            external_events=[],
            plan={"experiments": [], "days": []},
            today_context=today_context,
            conditional_items=[],
        )
        self.assertNotIn('<script>alert("xss")</script>', html)
        self.assertIn("&lt;script&gt;", html)


class RenderSummaryHtmlTests(unittest.TestCase):
    def test_month_summary_complete_html(self) -> None:
        records = [
            _make_record("Task A", "2026-03-15", "completed"),
            _make_record("Task B", "2026-03-16", "moved"),
        ]
        html = render_summary_html("month", "2026-03", records, "Asia/Shanghai", dt.date(2026, 3, 1), dt.date(2026, 3, 31))
        self.assertIn("<!DOCTYPE html>", html)
        self.assertIn("2026-03", html)
        self.assertIn("History Summary", html)
        self.assertIn("<style>", html)
        self.assertIn("--bg:", html)
        self.assertIn("</html>", html)

    def test_quarter_summary(self) -> None:
        records = [_make_record("Task", "2026-02-15")]
        html = render_summary_html("quarter", "2026 Q1", records, "Asia/Shanghai", dt.date(2026, 1, 1), dt.date(2026, 3, 31))
        self.assertIn("Quarter", html)
        self.assertIn("Weekly Roadmap", html)

    def test_year_summary(self) -> None:
        records = [_make_record("Task", "2026-06-15")]
        html = render_summary_html("year", "2026", records, "Asia/Shanghai", dt.date(2026, 1, 1), dt.date(2026, 12, 31))
        self.assertIn("Year", html)
        self.assertIn("Monthly Milestones", html)

    def test_empty_records(self) -> None:
        html = render_summary_html("month", "2026-03", [], "Asia/Shanghai", dt.date(2026, 3, 1), dt.date(2026, 3, 31))
        self.assertIn("<!DOCTYPE html>", html)
        self.assertIn("empty-state", html)


class RenderBucketOverviewTests(unittest.TestCase):
    def test_with_data(self) -> None:
        records = [_make_record("Cell passage", "2026-03-15", "completed", "cell")]
        buckets = month_week_buckets(dt.date(2026, 3, 1), dt.date(2026, 3, 31))
        html = render_bucket_overview(records, buckets, "Weekly Overview", "Test subtitle")
        self.assertIn("Weekly Overview", html)
        self.assertIn("Cell Expansion", html)

    def test_empty_records(self) -> None:
        buckets = month_week_buckets(dt.date(2026, 3, 1), dt.date(2026, 3, 31))
        html = render_bucket_overview([], buckets, "Title", "Subtitle")
        self.assertIn("empty-state", html)


class RenderDailyReviewTests(unittest.TestCase):
    def test_renders_day_cards(self) -> None:
        records = [_make_record("Cell passage", "2026-03-15")]
        html = render_daily_review(records, dt.date(2026, 3, 15), dt.date(2026, 3, 16))
        self.assertIn("Daily Review", html)
        self.assertIn("Mar 15", html)
        self.assertIn("Cell passage", html)


class RenderGroupReviewTests(unittest.TestCase):
    def test_renders_week_cards(self) -> None:
        records = [_make_record("Task", "2026-01-05")]
        buckets = quarter_week_buckets(dt.date(2026, 1, 1), dt.date(2026, 3, 31))
        html = render_group_review(records, buckets, "Weekly Review", "Test")
        self.assertIn("Weekly Review", html)


if __name__ == "__main__":
    unittest.main()
