from __future__ import annotations

import datetime as dt
import unittest

from planner.history_summary import (
    compact_note,
    compute_stats,
    default_target,
    month_week_buckets,
    normalize_record,
    period_bounds,
    quarter_week_buckets,
    reason_counts,
    render_reason_bars,
    render_stream_stats,
    status_badge,
    year_month_buckets,
)


class DefaultTargetTests(unittest.TestCase):
    def test_month(self) -> None:
        self.assertEqual(default_target("month", dt.date(2026, 3, 15)), "2026-03")

    def test_quarter(self) -> None:
        self.assertEqual(default_target("quarter", dt.date(2026, 3, 15)), "2026-Q1")
        self.assertEqual(default_target("quarter", dt.date(2026, 7, 1)), "2026-Q3")

    def test_year(self) -> None:
        self.assertEqual(default_target("year", dt.date(2026, 3, 15)), "2026")


class PeriodBoundsTests(unittest.TestCase):
    def test_month_bounds(self) -> None:
        start, end, label = period_bounds("month", "2026-03")
        self.assertEqual(start, dt.date(2026, 3, 1))
        self.assertEqual(end, dt.date(2026, 3, 31))
        self.assertEqual(label, "2026-03")

    def test_month_december(self) -> None:
        start, end, _label = period_bounds("month", "2026-12")
        self.assertEqual(start, dt.date(2026, 12, 1))
        self.assertEqual(end, dt.date(2026, 12, 31))

    def test_quarter_bounds(self) -> None:
        start, end, label = period_bounds("quarter", "2026-Q1")
        self.assertEqual(start, dt.date(2026, 1, 1))
        self.assertEqual(end, dt.date(2026, 3, 31))
        self.assertIn("Q1", label)

    def test_quarter_q4(self) -> None:
        start, end, _label = period_bounds("quarter", "2026-Q4")
        self.assertEqual(start, dt.date(2026, 10, 1))
        self.assertEqual(end, dt.date(2026, 12, 31))

    def test_year_bounds(self) -> None:
        start, end, label = period_bounds("year", "2026")
        self.assertEqual(start, dt.date(2026, 1, 1))
        self.assertEqual(end, dt.date(2026, 12, 31))
        self.assertEqual(label, "2026")


class NormalizeRecordTests(unittest.TestCase):
    def test_adds_computed_fields(self) -> None:
        record = {
            "event_date": "2026-03-15",
            "planned_start": "2026-03-15T09:00:00+08:00",
            "title": "Cell passage",
            "status": "completed",
            "stream": "cell",
            "status_note": "",
        }
        result = normalize_record(record)
        self.assertEqual(result["event_day"], dt.date(2026, 3, 15))
        self.assertEqual(result["status_label"], "Completed")
        self.assertEqual(result["status_class"], "status-completed")
        self.assertTrue(result["has_precise_time"])

    def test_default_status(self) -> None:
        record = {"event_date": "2026-03-15", "title": "Task", "stream": "general", "status_note": ""}
        result = normalize_record(record)
        self.assertEqual(result["status_label"], "Planned")


class CompactNoteTests(unittest.TestCase):
    def test_short_text(self) -> None:
        self.assertEqual(compact_note("hello", 10), "hello")

    def test_long_text(self) -> None:
        result = compact_note("a" * 200, 100)
        self.assertEqual(len(result), 100)
        self.assertTrue(result.endswith("…"))

    def test_none(self) -> None:
        self.assertEqual(compact_note(None), "")


class ComputeStatsTests(unittest.TestCase):
    def test_counts_statuses(self) -> None:
        records = [
            {"status": "completed"},
            {"status": "partial"},
            {"status": "moved"},
            {"status": "conditional"},
            {"status": "pending_sync"},
        ]
        stats = compute_stats(records)
        self.assertEqual(stats["completed"], 2)
        self.assertEqual(stats["moved"], 1)
        self.assertEqual(stats["conditional"], 1)
        self.assertEqual(stats["unsynced"], 1)


class ReasonCountsTests(unittest.TestCase):
    def test_counts_moved_reasons(self) -> None:
        records = [
            {"status": "moved", "reason_category": "Cell / sample state"},
            {"status": "moved", "reason_category": "Cell / sample state"},
            {"status": "completed", "reason_category": "Cell / sample state"},
            {"status": "incomplete", "reason_category": "Plan change"},
        ]
        result = reason_counts(records)
        categories = dict(result)
        self.assertEqual(categories["Cell / sample state"], 2)
        self.assertEqual(categories["Plan change"], 1)


class StatusBadgeTests(unittest.TestCase):
    def test_renders_badge(self) -> None:
        record = {"status_class": "status-completed", "status_label": "Completed"}
        result = status_badge(record)
        self.assertIn("status-completed", result)
        self.assertIn("Completed", result)


class RenderReasonBarsTests(unittest.TestCase):
    def test_empty(self) -> None:
        result = render_reason_bars([])
        self.assertIn("empty-state", result)

    def test_with_data(self) -> None:
        result = render_reason_bars([("Cell / sample state", 5), ("Plan change", 2)])
        self.assertIn("Cell / sample state", result)
        self.assertIn("reason-fill", result)


class RenderStreamStatsTests(unittest.TestCase):
    def test_empty(self) -> None:
        result = render_stream_stats([])
        self.assertIn("empty-state", result)

    def test_with_records(self) -> None:
        records = [
            {"stream": "cell", "status": "completed"},
            {"stream": "cell", "status": "moved"},
        ]
        result = render_stream_stats(records)
        self.assertIn("Cell Expansion", result)


class MonthWeekBucketsTests(unittest.TestCase):
    def test_march_2026(self) -> None:
        buckets = month_week_buckets(dt.date(2026, 3, 1), dt.date(2026, 3, 31))
        self.assertGreater(len(buckets), 0)
        self.assertEqual(buckets[0]["start"], dt.date(2026, 3, 1))
        self.assertEqual(buckets[-1]["end"], dt.date(2026, 3, 31))


class QuarterWeekBucketsTests(unittest.TestCase):
    def test_q1_2026(self) -> None:
        buckets = quarter_week_buckets(dt.date(2026, 1, 1), dt.date(2026, 3, 31))
        self.assertGreater(len(buckets), 10)
        self.assertEqual(buckets[0]["start"], dt.date(2026, 1, 1))
        self.assertIn("W01", buckets[0]["label"])


class YearMonthBucketsTests(unittest.TestCase):
    def test_full_year(self) -> None:
        buckets = year_month_buckets(dt.date(2026, 1, 1), dt.date(2026, 12, 31))
        self.assertEqual(len(buckets), 12)
        self.assertEqual(buckets[0]["label"], "Jan")
        self.assertEqual(buckets[-1]["label"], "Dec")


if __name__ == "__main__":
    unittest.main()
