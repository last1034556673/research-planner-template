from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from planner.workspace import build_paths, ensure_workspace_dirs, repo_root, WorkspacePaths
from planner.history import (
    display_path,
    ensure_history_dirs,
    entry_matches_event,
    infer_reason_category,
    load_jsonl,
    record_key,
    serialize_event,
    status_entries_for_date,
    to_iso,
    upsert_history_records,
    write_jsonl,
)


class RepoRootTests(unittest.TestCase):
    def test_returns_project_root(self) -> None:
        root = repo_root()
        self.assertTrue((root / "planner").is_dir())
        self.assertTrue((root / "tests").is_dir())


class BuildPathsTests(unittest.TestCase):
    def test_default_workspace(self) -> None:
        paths = build_paths()
        self.assertTrue(str(paths.root).endswith("workspace"))

    def test_custom_workspace(self) -> None:
        paths = build_paths("/tmp/custom_ws")
        self.assertEqual(paths.root, Path("/tmp/custom_ws"))
        self.assertEqual(paths.config_dir, Path("/tmp/custom_ws/config"))
        self.assertEqual(paths.data_dir, Path("/tmp/custom_ws/data"))

    def test_frozen_dataclass(self) -> None:
        paths = build_paths("/tmp/test_ws")
        with self.assertRaises(AttributeError):
            paths.root = Path("/other")

    def test_all_expected_fields(self) -> None:
        paths = build_paths("/tmp/test_ws")
        expected = [
            "repo_root", "root", "config_dir", "data_dir",
            "daily_reports_dir", "history_dir", "history_daily_dir",
            "history_summaries_dir", "outputs_dir", "replan_suggestions_dir",
            "project_config", "constraints_config", "integrations_config",
            "workstreams_config", "report_template", "plan_details",
            "status_log", "calendar_events", "dashboard_output",
        ]
        for field in expected:
            self.assertTrue(hasattr(paths, field), f"Missing field: {field}")


class EnsureWorkspaceDirsTests(unittest.TestCase):
    def test_creates_all_directories(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            paths = build_paths(tmp)
            ensure_workspace_dirs(paths)
            self.assertTrue(paths.config_dir.is_dir())
            self.assertTrue(paths.data_dir.is_dir())
            self.assertTrue(paths.daily_reports_dir.is_dir())
            self.assertTrue(paths.history_dir.is_dir())
            self.assertTrue(paths.outputs_dir.is_dir())
            self.assertTrue(paths.replan_suggestions_dir.is_dir())


class ToIsoTests(unittest.TestCase):
    def test_none(self) -> None:
        self.assertIsNone(to_iso(None))

    def test_datetime(self) -> None:
        import datetime as dt
        val = dt.datetime(2026, 3, 15, 9, 0)
        self.assertEqual(to_iso(val), "2026-03-15T09:00:00")


class DisplayPathTests(unittest.TestCase):
    def test_none_path(self) -> None:
        self.assertIsNone(display_path(None, None))

    def test_relative_to_base(self) -> None:
        result = display_path(Path("/home/user/ws/data/file.json"), Path("/home/user/ws"))
        self.assertEqual(result, "data/file.json")

    def test_absolute_fallback(self) -> None:
        result = display_path(Path("/other/path.json"), Path("/home/user"))
        self.assertEqual(result, "/other/path.json")


class InferReasonCategoryTests(unittest.TestCase):
    def test_cell_keywords(self) -> None:
        self.assertEqual(infer_reason_category("Cell confluence too low"), "Cell / sample state")

    def test_instrument_keywords(self) -> None:
        self.assertEqual(infer_reason_category("DLS machine booked"), "Instrument / reagent")

    def test_time_keywords(self) -> None:
        self.assertEqual(infer_reason_category("Weekend conflict"), "Time conflict / non-lab day")

    def test_animal_keywords(self) -> None:
        self.assertEqual(infer_reason_category("Mouse cohort not ready"), "Animals / materials")

    def test_plan_keywords(self) -> None:
        self.assertEqual(infer_reason_category("Reschedule to next week"), "Plan change")

    def test_unspecified(self) -> None:
        self.assertEqual(infer_reason_category("Unknown reason"), "Unspecified")

    def test_uses_status_note(self) -> None:
        self.assertEqual(infer_reason_category("Task", "cell density insufficient"), "Cell / sample state")


class EntryMatchesEventTests(unittest.TestCase):
    def test_exact_title(self) -> None:
        self.assertTrue(entry_matches_event({"title_match": "Event A"}, {"title": "Event A"}))

    def test_contains(self) -> None:
        self.assertTrue(entry_matches_event({"title_contains": "passage"}, {"title": "Cell passage"}))

    def test_no_match(self) -> None:
        self.assertFalse(entry_matches_event({"title_match": "X"}, {"title": "Y"}))


class StatusEntriesForDateTests(unittest.TestCase):
    def test_filters_by_date(self) -> None:
        log = {
            "statuses": [
                {"date": "2026-03-15", "title_match": "A"},
                {"date": "2026-03-16", "title_match": "B"},
                {"date": "2026-03-15", "title_match": "C"},
            ]
        }
        result = status_entries_for_date(log, "2026-03-15")
        self.assertEqual(len(result), 2)


class RecordKeyTests(unittest.TestCase):
    def test_format(self) -> None:
        record = {
            "event_date": "2026-03-15",
            "source": "calendar",
            "title": "Task",
            "planned_start": "2026-03-15T09:00:00",
            "planned_end": "2026-03-15T10:00:00",
        }
        key = record_key(record)
        self.assertIn("2026-03-15", key)
        self.assertIn("Task", key)


class JsonlTests(unittest.TestCase):
    def test_load_and_write_jsonl(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "test.jsonl"
            records = [{"a": 1}, {"b": 2}]
            write_jsonl(path, records)
            loaded = load_jsonl(path)
            self.assertEqual(len(loaded), 2)
            self.assertEqual(loaded[0]["a"], 1)

    def test_load_missing_file(self) -> None:
        self.assertEqual(load_jsonl(Path("/nonexistent/file.jsonl")), [])


class EnsureHistoryDirsTests(unittest.TestCase):
    def test_creates_dirs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            history_dir = Path(tmp) / "history"
            paths = ensure_history_dirs(history_dir)
            self.assertTrue(paths["daily"].is_dir())
            self.assertTrue(paths["summaries"].is_dir())
            self.assertTrue(str(paths["events"]).endswith("events.jsonl"))


class SerializeEventTests(unittest.TestCase):
    def test_serializes_fields(self) -> None:
        import datetime as dt
        event = {
            "id": "test-id",
            "calendar": "Research",
            "title": "Test",
            "short_title": "Test",
            "start": dt.datetime(2026, 3, 15, 9, 0),
            "end": dt.datetime(2026, 3, 15, 10, 0),
            "stream": "cell",
            "display_streams": ["cell"],
            "conditional": False,
            "status_key": "completed",
            "status_label": "Completed",
            "status_note": "Done",
        }
        result = serialize_event(event)
        self.assertEqual(result["title"], "Test")
        self.assertEqual(result["start"], "2026-03-15T09:00:00")


class UpsertHistoryRecordsTests(unittest.TestCase):
    def test_merges_records(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "events.jsonl"
            initial = [
                {"event_date": "2026-03-15", "source": "calendar", "title": "A", "planned_start": "09:00", "planned_end": "10:00"},
            ]
            write_jsonl(path, initial)
            new = [
                {"event_date": "2026-03-15", "source": "calendar", "title": "B", "planned_start": "11:00", "planned_end": "12:00"},
            ]
            total = upsert_history_records(path, new)
            self.assertEqual(total, 2)

    def test_upsert_deduplicates(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "events.jsonl"
            record = {"event_date": "2026-03-15", "source": "calendar", "title": "A", "planned_start": "09:00", "planned_end": "10:00", "status": "planned"}
            write_jsonl(path, [record])
            updated = dict(record)
            updated["status"] = "completed"
            total = upsert_history_records(path, [updated])
            self.assertEqual(total, 1)
            loaded = load_jsonl(path)
            self.assertEqual(loaded[0]["status"], "completed")


if __name__ == "__main__":
    unittest.main()
