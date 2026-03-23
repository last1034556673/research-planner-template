from __future__ import annotations

import datetime as dt
import json
import tempfile
import unittest
from pathlib import Path

from planner.calendar_io import (
    load_event_records,
    load_event_records_from_file,
)


class LoadEventRecordsFromFileTests(unittest.TestCase):
    def test_missing_file_returns_empty(self) -> None:
        result = load_event_records_from_file(
            start=dt.datetime(2026, 3, 1, tzinfo=dt.timezone.utc),
            end=dt.datetime(2026, 3, 31, tzinfo=dt.timezone.utc),
            events_file=Path("/nonexistent/path.json"),
        )
        self.assertEqual(result, [])

    def test_none_file_returns_empty(self) -> None:
        result = load_event_records_from_file(
            start=dt.datetime(2026, 3, 1, tzinfo=dt.timezone.utc),
            end=dt.datetime(2026, 3, 31, tzinfo=dt.timezone.utc),
            events_file=None,
        )
        self.assertEqual(result, [])

    def test_filters_by_date_range(self) -> None:
        events = [
            {"calendar": "R", "title": "Before", "start": "2026-02-28T09:00:00+08:00", "end": "2026-02-28T10:00:00+08:00"},
            {"calendar": "R", "title": "In range", "start": "2026-03-15T09:00:00+08:00", "end": "2026-03-15T10:00:00+08:00"},
            {"calendar": "R", "title": "After", "start": "2026-04-01T09:00:00+08:00", "end": "2026-04-01T10:00:00+08:00"},
        ]
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(events, f)
            f.flush()
            result = load_event_records_from_file(
                start=dt.datetime(2026, 3, 1, tzinfo=dt.timezone.utc),
                end=dt.datetime(2026, 3, 31, tzinfo=dt.timezone.utc),
                events_file=Path(f.name),
            )
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["title"], "In range")

    def test_skips_invalid_records(self) -> None:
        events = [
            {"calendar": "R", "title": "Valid", "start": "2026-03-15T09:00:00+08:00", "end": "2026-03-15T10:00:00+08:00"},
            {"calendar": "R", "title": "No end"},
            {"calendar": "R", "title": "Bad date", "start": "not-a-date", "end": "not-a-date"},
        ]
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(events, f)
            f.flush()
            result = load_event_records_from_file(
                start=dt.datetime(2026, 3, 1, tzinfo=dt.timezone.utc),
                end=dt.datetime(2026, 3, 31, tzinfo=dt.timezone.utc),
                events_file=Path(f.name),
            )
        self.assertEqual(len(result), 1)


class LoadEventRecordsTests(unittest.TestCase):
    def test_file_provider(self) -> None:
        result = load_event_records(
            start=dt.datetime(2026, 3, 1, tzinfo=dt.timezone.utc),
            end=dt.datetime(2026, 3, 31, tzinfo=dt.timezone.utc),
            tz_name="Asia/Shanghai",
            provider="file",
            events_file=None,
        )
        self.assertEqual(result, [])

    def test_invalid_provider_raises(self) -> None:
        with self.assertRaises(ValueError):
            load_event_records(
                start=dt.datetime(2026, 3, 1, tzinfo=dt.timezone.utc),
                end=dt.datetime(2026, 3, 31, tzinfo=dt.timezone.utc),
                tz_name="Asia/Shanghai",
                provider="google",
            )

    def test_macos_missing_script(self) -> None:
        result = load_event_records(
            start=dt.datetime(2026, 3, 1, tzinfo=dt.timezone.utc),
            end=dt.datetime(2026, 3, 31, tzinfo=dt.timezone.utc),
            tz_name="Asia/Shanghai",
            provider="macos",
            calendar_script=Path("/nonexistent/script.swift"),
        )
        self.assertEqual(result, [])


if __name__ == "__main__":
    unittest.main()
