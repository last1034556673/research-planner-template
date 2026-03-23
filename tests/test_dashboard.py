from __future__ import annotations

import datetime as dt
import unittest
from zoneinfo import ZoneInfo

from planner.dashboard import (
    annotate_event_status,
    bucket_events_by_day,
    clip_text,
    collect_status_counts,
    format_event_window,
    match_descriptor_to_event,
    match_status_entry,
    merged_streams,
    normalize_streams,
    parse_sync_deadline,
    render_reason_details,
    render_status_badge,
    visible_primary,
    weekday_label,
    DEFAULT_SYNC_DEADLINE,
    STATUS_META,
)
from planner.planner_data import (
    best_event_match,
    categorize,
    compact_title,
    is_conditional,
    normalize_match_text,
    parse_event,
    score_event_match,
)


TZ = ZoneInfo("Asia/Shanghai")


def _make_event(title: str, start_hour: int = 9, end_hour: int = 10, date: str = "2026-03-15", calendar: str = "Research", **extra) -> dict:
    start = dt.datetime(int(date[:4]), int(date[5:7]), int(date[8:10]), start_hour, 0, tzinfo=TZ)
    end = dt.datetime(int(date[:4]), int(date[5:7]), int(date[8:10]), end_hour, 0, tzinfo=TZ)
    event = {
        "id": f"{calendar}|{start.isoformat()}|{title}",
        "calendar": calendar,
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
    }
    event.update(extra)
    return event


class ParseSyncDeadlineTests(unittest.TestCase):
    def test_parse_valid(self) -> None:
        self.assertEqual(parse_sync_deadline("09:30"), dt.time(9, 30))
        self.assertEqual(parse_sync_deadline("14:00"), dt.time(14, 0))

    def test_default_sync_deadline(self) -> None:
        self.assertEqual(DEFAULT_SYNC_DEADLINE, dt.time(9, 30))


class CategorizeTests(unittest.TestCase):
    def test_mouse_keyword(self) -> None:
        self.assertEqual(categorize("Mouse cohort treatment"), "mouse")

    def test_cell_keyword(self) -> None:
        self.assertEqual(categorize("Cell culture passage"), "cell")

    def test_flow_keyword(self) -> None:
        self.assertEqual(categorize("Flow cytometry analysis"), "flow")

    def test_general_fallback(self) -> None:
        self.assertEqual(categorize("Weekly team meeting"), "general")

    def test_chinese_keyword(self) -> None:
        self.assertEqual(categorize("细胞传代"), "cell")


class IsConditionalTests(unittest.TestCase):
    def test_conditional_markers(self) -> None:
        self.assertTrue(is_conditional("If confluence > 80%: proceed"))
        self.assertTrue(is_conditional("When cells are ready"))
        self.assertTrue(is_conditional("After confirmation of results"))

    def test_not_conditional(self) -> None:
        self.assertFalse(is_conditional("Regular cell passage"))


class CompactTitleTests(unittest.TestCase):
    def test_removes_trailing_brackets(self) -> None:
        self.assertEqual(compact_title("Task name [Research]"), "Task name")

    def test_removes_leading_punctuation(self) -> None:
        self.assertEqual(compact_title("- Task name"), "Task name")


class ClipTextTests(unittest.TestCase):
    def test_short_text_unchanged(self) -> None:
        self.assertEqual(clip_text("hello", 10), "hello")

    def test_long_text_clipped(self) -> None:
        result = clip_text("a very long title that exceeds limit", 20)
        self.assertEqual(len(result), 20)
        self.assertTrue(result.endswith("…"))


class WeekdayLabelTests(unittest.TestCase):
    def test_monday(self) -> None:
        self.assertEqual(weekday_label(dt.date(2026, 3, 16)), "Mon")

    def test_sunday(self) -> None:
        self.assertEqual(weekday_label(dt.date(2026, 3, 22)), "Sun")

    def test_datetime_input(self) -> None:
        self.assertEqual(weekday_label(dt.datetime(2026, 3, 16, 10, 0, tzinfo=TZ)), "Mon")


class ParseEventTests(unittest.TestCase):
    def test_basic_parsing(self) -> None:
        record = {
            "calendar": "Research",
            "title": "Cell passage",
            "start": "2026-03-15T09:00:00+08:00",
            "end": "2026-03-15T10:00:00+08:00",
            "isAllDay": False,
        }
        result = parse_event(record, TZ)
        self.assertEqual(result["title"], "Cell passage")
        self.assertEqual(result["calendar"], "Research")
        self.assertIsInstance(result["start"], dt.datetime)
        self.assertEqual(result["stream"], "cell")

    def test_conditional_detection(self) -> None:
        record = {
            "calendar": "Research",
            "title": "If cells ready: expand",
            "start": "2026-03-15T09:00:00+08:00",
            "end": "2026-03-15T10:00:00+08:00",
        }
        result = parse_event(record, TZ)
        self.assertTrue(result["conditional"])


class VisiblePrimaryTests(unittest.TestCase):
    def test_visible(self) -> None:
        self.assertTrue(visible_primary(_make_event("Cell passage")))

    def test_hidden_lunch(self) -> None:
        self.assertFalse(visible_primary(_make_event("Lunch Break")))

    def test_hidden_focus_block(self) -> None:
        self.assertFalse(visible_primary(_make_event("Focus Block")))


class ScoreEventMatchTests(unittest.TestCase):
    def test_exact_match(self) -> None:
        event = _make_event("Cell passage")
        self.assertEqual(score_event_match("Cell passage", event), 100)

    def test_substring_match(self) -> None:
        event = _make_event("Cell passage and expansion")
        self.assertEqual(score_event_match("Cell passage", event), 80)

    def test_no_match(self) -> None:
        event = _make_event("Completely unrelated")
        self.assertLessEqual(score_event_match("Something else entirely different", event), 20)


class BestEventMatchTests(unittest.TestCase):
    def test_finds_best(self) -> None:
        events = [_make_event("Mouse treatment"), _make_event("Cell passage")]
        result = best_event_match("Cell passage", events)
        self.assertIsNotNone(result)
        self.assertEqual(result["title"], "Cell passage")

    def test_returns_none_for_no_match(self) -> None:
        events = [_make_event("Mouse treatment")]
        result = best_event_match("Completely different task", events)
        self.assertIsNone(result)


class MatchStatusEntryTests(unittest.TestCase):
    def test_finds_matching_entry(self) -> None:
        event = _make_event("Cell passage", task_id="task-abc")
        entries = [{"task_id": "task-abc", "status": "completed"}]
        result = match_status_entry(event, entries)
        self.assertIsNotNone(result)
        self.assertEqual(result["status"], "completed")

    def test_returns_none_when_no_match(self) -> None:
        event = _make_event("Cell passage", task_id="task-abc")
        entries = [{"task_id": "task-xyz", "status": "completed"}]
        result = match_status_entry(event, entries)
        self.assertIsNone(result)


class AnnotateEventStatusTests(unittest.TestCase):
    def test_planned_for_future_event(self) -> None:
        now = dt.datetime(2026, 3, 15, 8, 0, tzinfo=TZ)
        event = _make_event("Future task", start_hour=14, end_hour=15)
        result = annotate_event_status(event, [], now)
        self.assertEqual(result["status_key"], "planned")

    def test_conditional_for_conditional_event(self) -> None:
        now = dt.datetime(2026, 3, 15, 8, 0, tzinfo=TZ)
        event = _make_event("If cells ready: expand", start_hour=14, end_hour=15, conditional=True)
        result = annotate_event_status(event, [], now)
        self.assertEqual(result["status_key"], "conditional")

    def test_pending_sync_for_recent_past(self) -> None:
        now = dt.datetime(2026, 3, 16, 8, 0, tzinfo=TZ)
        event = _make_event("Past task", start_hour=14, end_hour=15)
        result = annotate_event_status(event, [], now)
        self.assertEqual(result["status_key"], "pending_sync")

    def test_unsynced_for_old_past(self) -> None:
        now = dt.datetime(2026, 3, 16, 12, 0, tzinfo=TZ)
        event = _make_event("Past task", start_hour=14, end_hour=15)
        result = annotate_event_status(event, [], now)
        self.assertEqual(result["status_key"], "unsynced")

    def test_custom_sync_deadline(self) -> None:
        now = dt.datetime(2026, 3, 16, 8, 0, tzinfo=TZ)
        event = _make_event("Past task", start_hour=14, end_hour=15)
        result = annotate_event_status(event, [], now, sync_deadline=dt.time(7, 0))
        self.assertEqual(result["status_key"], "unsynced")

    def test_status_from_entry(self) -> None:
        now = dt.datetime(2026, 3, 15, 8, 0, tzinfo=TZ)
        event = _make_event("Cell passage", task_id="task-abc")
        entries = [{"task_id": "task-abc", "status": "completed", "note": "Done"}]
        result = annotate_event_status(event, entries, now)
        self.assertEqual(result["status_key"], "completed")
        self.assertEqual(result["status_note"], "Done")


class FormatEventWindowTests(unittest.TestCase):
    def test_same_day(self) -> None:
        start = dt.datetime(2026, 3, 15, 9, 0, tzinfo=TZ)
        end = dt.datetime(2026, 3, 15, 10, 0, tzinfo=TZ)
        result = format_event_window(start, end)
        self.assertIn("09:00-10:00", result)

    def test_cross_day(self) -> None:
        start = dt.datetime(2026, 3, 15, 23, 0, tzinfo=TZ)
        end = dt.datetime(2026, 3, 16, 1, 0, tzinfo=TZ)
        result = format_event_window(start, end)
        self.assertIn("->", result)


class RenderStatusBadgeTests(unittest.TestCase):
    def test_renders_html(self) -> None:
        result = render_status_badge("completed")
        self.assertIn("status-completed", result)
        self.assertIn("Completed", result)

    def test_custom_label(self) -> None:
        result = render_status_badge("planned", label="Custom")
        self.assertIn("Custom", result)


class RenderReasonDetailsTests(unittest.TestCase):
    def test_empty_returns_empty(self) -> None:
        self.assertEqual(render_reason_details(), "")

    def test_with_fields(self) -> None:
        result = render_reason_details(status_note="Note", blocking_reason="Blocked")
        self.assertIn("Status note", result)
        self.assertIn("Blocking reason", result)


class NormalizeStreamsTests(unittest.TestCase):
    def test_list_input(self) -> None:
        result = normalize_streams(["cell", "rna"], "cell")
        self.assertEqual(result, ["cell", "rna"])

    def test_string_input(self) -> None:
        result = normalize_streams("cell", "cell")
        self.assertEqual(result, ["cell"])

    def test_adds_default(self) -> None:
        result = normalize_streams(["rna"], "cell")
        self.assertIn("cell", result)


class MergedStreamsTests(unittest.TestCase):
    def test_default_streams_present(self) -> None:
        result = merged_streams({"streams": []})
        ids = [item["id"] for item in result]
        self.assertIn("rna", ids)
        self.assertIn("cell", ids)

    def test_extra_streams_appended(self) -> None:
        result = merged_streams({"streams": []}, [{"id": "custom", "label": "Custom"}])
        ids = [item["id"] for item in result]
        self.assertIn("custom", ids)


class CollectStatusCountsTests(unittest.TestCase):
    def test_counts(self) -> None:
        events = [
            _make_event("A", status_key="completed"),
            _make_event("B", status_key="completed"),
            _make_event("C", status_key="planned"),
        ]
        counts = collect_status_counts(events)
        self.assertEqual(counts["completed"], 2)
        self.assertEqual(counts["planned"], 1)


class BucketEventsByDayTests(unittest.TestCase):
    def test_groups_by_date(self) -> None:
        events = [
            _make_event("A", date="2026-03-15"),
            _make_event("B", date="2026-03-15"),
            _make_event("C", date="2026-03-16"),
        ]
        grouped = bucket_events_by_day(events)
        self.assertEqual(len(grouped["2026-03-15"]), 2)
        self.assertEqual(len(grouped["2026-03-16"]), 1)


class MatchDescriptorToEventTests(unittest.TestCase):
    def test_exact_title_match(self) -> None:
        events = [_make_event("Cell passage"), _make_event("Mouse treatment")]
        descriptor = {"title_match": "Cell passage"}
        result = match_descriptor_to_event(descriptor, events)
        self.assertIsNotNone(result)
        self.assertEqual(result["title"], "Cell passage")

    def test_contains_match(self) -> None:
        events = [_make_event("Cell passage and expansion")]
        descriptor = {"title_contains": "passage"}
        result = match_descriptor_to_event(descriptor, events)
        self.assertIsNotNone(result)

    def test_no_match(self) -> None:
        events = [_make_event("Cell passage")]
        descriptor = {"title_match": "Not found"}
        result = match_descriptor_to_event(descriptor, events)
        self.assertIsNone(result)


class NormalizeMatchTextTests(unittest.TestCase):
    def test_lowercases_and_strips(self) -> None:
        result = normalize_match_text("Hello World [Tag]")
        self.assertEqual(result, "helloworld")


if __name__ == "__main__":
    unittest.main()
