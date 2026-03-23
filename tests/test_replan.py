from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
DEMO_SEED = REPO_ROOT / "examples" / "wetlab_demo" / "workspace_seed"


class ReplanTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = Path(tempfile.mkdtemp(prefix="research-planner-replan-"))
        self.workspace = self.temp_dir / "workspace"
        shutil.copytree(DEMO_SEED, self.workspace)

    def tearDown(self) -> None:
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def run_cli(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["python3", "-m", "planner.cli", "--workspace", str(self.workspace), *args],
            cwd=REPO_ROOT,
            check=True,
            text=True,
            capture_output=True,
        )

    def test_replan_suggest_generates_follow_on_change(self) -> None:
        self.run_cli("replan", "--input", str(self.workspace / "daily_reports" / "2026-03-15.md"))
        payload = json.loads((self.workspace / "outputs" / "replan_suggestions" / "2026-03-15.json").read_text())
        self.assertEqual(payload["report_date"], "2026-03-15")
        self.assertGreaterEqual(len(payload["changes"]), 1)
        first = payload["changes"][0]
        self.assertEqual(first["title"], "Expand GFP reporter culture 5 flasks to 10 flasks")
        self.assertIn("task-976cfa0215", first["follow_on_tasks"])

    def test_replan_apply_updates_plan_and_calendar(self) -> None:
        self.run_cli("replan", "--input", str(self.workspace / "daily_reports" / "2026-03-15.md"), "--apply")
        plan = json.loads((self.workspace / "data" / "plan_details.json").read_text())
        events = json.loads((self.workspace / "data" / "calendar_events.json").read_text())
        updated_step = next(
            step
            for experiment in plan["experiments"]
            for step in experiment["steps"]
            if step.get("title_match") == "If reporter culture is ready: expand to 20 flasks and seed spheroids"
        )
        updated_event = next(event for event in events if event.get("task_id") == "task-976cfa0215")
        self.assertEqual(updated_step["date"], "2026-03-19")
        self.assertTrue(updated_event["start"].startswith("2026-03-19T15:00:00"))


class ReplanUnitTests(unittest.TestCase):
    """Unit tests for replan helper functions (no subprocess)."""

    def test_is_allowed_workday_normal(self) -> None:
        import datetime as dt
        from planner.replan import is_allowed_workday

        monday = dt.date(2026, 3, 16)
        self.assertTrue(is_allowed_workday(monday, {}))

    def test_is_allowed_workday_blocked_day(self) -> None:
        import datetime as dt
        from planner.replan import is_allowed_workday

        day = dt.date(2026, 3, 16)
        self.assertFalse(is_allowed_workday(day, {"blocked_days": ["2026-03-16"]}))

    def test_is_allowed_workday_saturday_blocked(self) -> None:
        import datetime as dt
        from planner.replan import is_allowed_workday

        saturday = dt.date(2026, 3, 21)
        self.assertFalse(is_allowed_workday(saturday, {"weekend_rules": {"saturday_lab_allowed": False}}))

    def test_is_allowed_workday_sunday_blocked(self) -> None:
        import datetime as dt
        from planner.replan import is_allowed_workday

        sunday = dt.date(2026, 3, 22)
        self.assertFalse(is_allowed_workday(sunday, {"weekend_rules": {"sunday_lab_allowed": False}}))

    def test_weekday_code(self) -> None:
        import datetime as dt
        from planner.replan import weekday_code

        self.assertEqual(weekday_code(dt.date(2026, 3, 16)), "MO")
        self.assertEqual(weekday_code(dt.date(2026, 3, 22)), "SU")

    def test_parse_clock_valid(self) -> None:
        import datetime as dt
        from planner.replan import parse_clock

        self.assertEqual(parse_clock("14:30", dt.time(9, 0)), dt.time(14, 30))

    def test_parse_clock_invalid_returns_default(self) -> None:
        import datetime as dt
        from planner.replan import parse_clock

        self.assertEqual(parse_clock("invalid", dt.time(9, 0)), dt.time(9, 0))

    def test_reverse_dependencies(self) -> None:
        from planner.replan import reverse_dependencies

        plan_index = {
            "task-a": {"depends_on": []},
            "task-b": {"depends_on": ["task-a"]},
            "task-c": {"depends_on": ["task-a", "task-b"]},
        }
        graph = reverse_dependencies(plan_index)
        self.assertIn("task-b", graph["task-a"])
        self.assertIn("task-c", graph["task-a"])
        self.assertIn("task-c", graph["task-b"])

    def test_apply_suggestion_to_plan_moves_task(self) -> None:
        from planner.replan import apply_suggestion_to_plan

        plan = {
            "experiments": [],
            "days": [
                {"date": "2026-03-15", "tasks": [{"title": "Task A", "task_id": "task-1"}]},
            ],
        }
        changes = [
            {"task_id": "task-1", "current_date": "2026-03-15", "suggested_date": "2026-03-17"},
        ]
        result = apply_suggestion_to_plan(plan, changes)
        day_15_tasks = next(d for d in result["days"] if d["date"] == "2026-03-15")["tasks"]
        day_17 = next(d for d in result["days"] if d["date"] == "2026-03-17")
        self.assertEqual(len(day_15_tasks), 0)
        self.assertEqual(len(day_17["tasks"]), 1)

    def test_apply_suggestion_to_events(self) -> None:
        from planner.replan import apply_suggestion_to_events

        events = [
            {"task_id": "task-1", "start": "2026-03-15T09:00:00+08:00", "end": "2026-03-15T10:00:00+08:00"},
            {"task_id": "task-2", "start": "2026-03-15T11:00:00+08:00", "end": "2026-03-15T12:00:00+08:00"},
        ]
        changes = [
            {"task_id": "task-1", "suggested_start": "2026-03-17T09:00:00+08:00", "suggested_end": "2026-03-17T10:00:00+08:00"},
        ]
        result = apply_suggestion_to_events(events, changes)
        self.assertEqual(result[0]["start"], "2026-03-17T09:00:00+08:00")
        self.assertEqual(result[1]["start"], "2026-03-15T11:00:00+08:00")

    def test_find_slot_basic(self) -> None:
        import datetime as dt
        from zoneinfo import ZoneInfo
        from planner.replan import find_slot

        tz = ZoneInfo("Asia/Shanghai")
        start, end, warnings = find_slot(
            start_day=dt.date(2026, 3, 16),
            preferred_start=dt.time(9, 0),
            duration_minutes=60,
            constraints={"workday_start": "08:00", "workday_end": "18:00"},
            events=[],
            tz=tz,
        )
        self.assertEqual(start.date(), dt.date(2026, 3, 16))
        self.assertEqual(start.hour, 9)
        self.assertEqual((end - start).total_seconds(), 3600)

    def test_find_slot_skips_blocked_day(self) -> None:
        import datetime as dt
        from zoneinfo import ZoneInfo
        from planner.replan import find_slot

        tz = ZoneInfo("Asia/Shanghai")
        start, end, warnings = find_slot(
            start_day=dt.date(2026, 3, 16),
            preferred_start=dt.time(9, 0),
            duration_minutes=60,
            constraints={
                "workday_start": "08:00",
                "workday_end": "18:00",
                "blocked_days": ["2026-03-16"],
            },
            events=[],
            tz=tz,
        )
        self.assertNotEqual(start.date(), dt.date(2026, 3, 16))
        self.assertGreater(len(warnings), 0)

    def test_find_slot_avoids_busy_interval(self) -> None:
        import datetime as dt
        from zoneinfo import ZoneInfo
        from planner.replan import find_slot

        tz = ZoneInfo("Asia/Shanghai")
        busy_event = {
            "start": "2026-03-16T09:00:00+08:00",
            "end": "2026-03-16T12:00:00+08:00",
            "event_id": "evt-busy",
        }
        start, end, warnings = find_slot(
            start_day=dt.date(2026, 3, 16),
            preferred_start=dt.time(9, 0),
            duration_minutes=60,
            constraints={"workday_start": "08:00", "workday_end": "18:00"},
            events=[busy_event],
            tz=tz,
        )
        self.assertGreaterEqual(start.hour, 12)

    def test_score_descriptor_match_exact(self) -> None:
        from planner.replan import score_descriptor_match

        score = score_descriptor_match("Cell passage", {"title": "Cell passage", "aliases": ["Cell passage"]})
        self.assertGreaterEqual(score, 100)

    def test_score_descriptor_match_no_match(self) -> None:
        from planner.replan import score_descriptor_match

        score = score_descriptor_match("Completely unrelated", {"title": "Mouse treatment", "aliases": []})
        self.assertLess(score, 50)

    def test_seed_candidate_map_filters_resolved(self) -> None:
        from planner.replan import seed_candidate_map
        from planner.planner_data import normalize_plan_details

        plan = normalize_plan_details({
            "days": [{"date": "2026-03-15", "tasks": [{"title": "Task A", "task_id": "task-1"}]}],
        })
        status_log = {
            "statuses": [
                {"task_id": "task-1", "status": "moved", "resolution_state": "resolved"},
            ]
        }
        result = seed_candidate_map(plan, status_log)
        self.assertEqual(len(result), 0)

    def test_build_replan_hard_timepoint_blocked(self) -> None:
        import datetime as dt
        import tempfile
        from zoneinfo import ZoneInfo
        from planner.replan import build_replan

        tz = ZoneInfo("Asia/Shanghai")
        plan = {
            "experiments": [],
            "days": [{"date": "2026-03-15", "tasks": [
                {"title": "Hard task", "task_id": "task-hard", "hard_timepoint": True},
            ]}],
        }
        with tempfile.TemporaryDirectory() as tmp:
            result = build_replan(
                plan=plan,
                status_log={"statuses": [{"task_id": "task-hard", "status": "incomplete"}]},
                constraints={"workday_start": "08:00", "workday_end": "18:00"},
                calendar_events=[],
                candidates=[],
                report_date=dt.date(2026, 3, 15),
                tz=tz,
                apply=False,
                plan_path=Path(tmp) / "plan.json",
                calendar_events_path=Path(tmp) / "events.json",
                provider="file",
            )
        self.assertEqual(len(result["changes"]), 0)
        self.assertGreaterEqual(len(result["blocked"]), 1)
        self.assertIn("hard timepoint", result["blocked"][0]["reason"])

    def test_build_replan_no_candidates(self) -> None:
        import datetime as dt
        import tempfile
        from zoneinfo import ZoneInfo
        from planner.replan import build_replan

        tz = ZoneInfo("Asia/Shanghai")
        with tempfile.TemporaryDirectory() as tmp:
            result = build_replan(
                plan={"experiments": [], "days": []},
                status_log={"statuses": []},
                constraints={},
                calendar_events=[],
                candidates=[],
                report_date=dt.date(2026, 3, 15),
                tz=tz,
                apply=False,
                plan_path=Path(tmp) / "plan.json",
                calendar_events_path=Path(tmp) / "events.json",
                provider="file",
            )
        self.assertEqual(len(result["changes"]), 0)
        self.assertEqual(len(result["blocked"]), 0)


if __name__ == "__main__":
    unittest.main()
