from __future__ import annotations

import unittest
from pathlib import Path

from planner.validate import (
    validate_calendar_events,
    validate_constraints_config,
    validate_integrations_config,
    validate_plan_details,
    validate_project_config,
    validate_status_log,
    validate_workspace_files,
    validate_workstreams_config,
)
from planner.workspace import build_paths


class ValidateProjectConfigTests(unittest.TestCase):
    def test_valid_config(self) -> None:
        config = {
            "project_name": "Test",
            "timezone": "UTC",
            "locale": "en_US",
            "primary_language": "en",
            "dashboard_window_days": 15,
            "sync_deadline": "09:30",
        }
        self.assertEqual(validate_project_config(config), [])

    def test_missing_fields(self) -> None:
        issues = validate_project_config({})
        self.assertEqual(len(issues), 6)
        self.assertTrue(all(i["level"] == "error" for i in issues))

    def test_wrong_type(self) -> None:
        config = {
            "project_name": 123,
            "timezone": "UTC",
            "locale": "en_US",
            "primary_language": "en",
            "dashboard_window_days": "fifteen",
            "sync_deadline": "09:30",
        }
        issues = validate_project_config(config)
        error_paths = {i["path"] for i in issues}
        self.assertIn("project.project_name", error_paths)
        self.assertIn("project.dashboard_window_days", error_paths)


class ValidateConstraintsConfigTests(unittest.TestCase):
    def test_valid_config(self) -> None:
        config = {
            "meetings": [],
            "blocked_days": [],
            "blocked_windows": [],
            "workday_start": "08:00",
            "workday_end": "18:00",
        }
        self.assertEqual(validate_constraints_config(config), [])

    def test_missing_lists(self) -> None:
        issues = validate_constraints_config({})
        error_paths = {i["path"] for i in issues if i["level"] == "error"}
        self.assertIn("constraints.meetings", error_paths)
        self.assertIn("constraints.blocked_days", error_paths)

    def test_wrong_type_for_list(self) -> None:
        config = {"meetings": "not a list", "blocked_days": [], "blocked_windows": []}
        issues = validate_constraints_config(config)
        self.assertTrue(any(i["path"] == "constraints.meetings" and i["level"] == "error" for i in issues))

    def test_missing_workday_bounds_are_warnings(self) -> None:
        config = {"meetings": [], "blocked_days": [], "blocked_windows": []}
        issues = validate_constraints_config(config)
        self.assertTrue(all(i["level"] == "warning" for i in issues))


class ValidateIntegrationsConfigTests(unittest.TestCase):
    def test_valid_config(self) -> None:
        config = {
            "calendar_provider": "file",
            "primary_calendar_name": "Research",
            "auto_open_outputs": False,
            "event_source_file": "data/events.json",
        }
        self.assertEqual(validate_integrations_config(config), [])

    def test_invalid_provider(self) -> None:
        config = {
            "calendar_provider": "invalid_provider",
            "primary_calendar_name": "Research",
            "auto_open_outputs": False,
            "event_source_file": "data/events.json",
        }
        issues = validate_integrations_config(config)
        self.assertTrue(any("calendar_provider" in i["path"] for i in issues))

    def test_missing_fields(self) -> None:
        issues = validate_integrations_config({})
        self.assertGreater(len(issues), 0)


class ValidateWorkstreamsConfigTests(unittest.TestCase):
    def test_valid_config(self) -> None:
        config = {"streams": [{"id": "rna", "label": "RNA Analysis"}]}
        self.assertEqual(validate_workstreams_config(config), [])

    def test_not_a_list(self) -> None:
        issues = validate_workstreams_config({"streams": "wrong"})
        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0]["level"], "error")

    def test_missing_stream_keys(self) -> None:
        config = {"streams": [{"id": "rna"}]}
        issues = validate_workstreams_config(config)
        self.assertTrue(any("label" in i["path"] for i in issues))

    def test_non_dict_stream(self) -> None:
        config = {"streams": ["not a dict"]}
        issues = validate_workstreams_config(config)
        self.assertEqual(len(issues), 1)


class ValidatePlanDetailsTests(unittest.TestCase):
    def test_valid_plan(self) -> None:
        plan = {"streams": [], "experiments": [], "days": []}
        issues = validate_plan_details(plan)
        errors = [i for i in issues if i["level"] == "error"]
        self.assertEqual(errors, [])

    def test_empty_plan_normalizes(self) -> None:
        issues = validate_plan_details({})
        errors = [i for i in issues if i["level"] == "error"]
        self.assertEqual(errors, [])


class ValidateStatusLogTests(unittest.TestCase):
    def test_valid_status_log(self) -> None:
        self.assertEqual(validate_status_log({"statuses": []}), [])

    def test_empty_normalizes(self) -> None:
        issues = validate_status_log({})
        errors = [i for i in issues if i["level"] == "error"]
        self.assertEqual(errors, [])


class ValidateCalendarEventsTests(unittest.TestCase):
    def test_valid_events(self) -> None:
        events = [{"calendar": "Research", "title": "Task", "start": "2026-03-15T09:00", "end": "2026-03-15T11:00"}]
        self.assertEqual(validate_calendar_events(events), [])

    def test_not_a_list(self) -> None:
        issues = validate_calendar_events("not a list")
        self.assertEqual(len(issues), 1)

    def test_missing_event_fields(self) -> None:
        events = [{"calendar": "Research"}]
        issues = validate_calendar_events(events)
        missing_fields = {i["path"] for i in issues}
        self.assertIn("calendar_events[0].title", missing_fields)
        self.assertIn("calendar_events[0].start", missing_fields)

    def test_non_dict_event(self) -> None:
        events = ["not a dict"]
        issues = validate_calendar_events(events)
        self.assertEqual(len(issues), 1)


class ValidateWorkspaceFilesTests(unittest.TestCase):
    def test_blank_template_has_no_validation_errors(self) -> None:
        paths = build_paths(str(Path(__file__).resolve().parents[1] / "templates" / "blank_workspace"))
        report = validate_workspace_files(paths)
        errors = [
            item
            for issues in report.values()
            for item in issues
            if item["level"] == "error"
        ]
        self.assertEqual(errors, [])

    def test_demo_workspace_has_no_validation_errors(self) -> None:
        demo_path = Path(__file__).resolve().parents[1] / "examples" / "wetlab_demo" / "workspace_seed"
        if not demo_path.exists():
            self.skipTest("Demo workspace not available")
        paths = build_paths(str(demo_path))
        report = validate_workspace_files(paths)
        errors = [
            item
            for issues in report.values()
            for item in issues
            if item["level"] == "error"
        ]
        self.assertEqual(errors, [])


if __name__ == "__main__":
    unittest.main()
