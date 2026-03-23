from __future__ import annotations

import unittest

from planner.planner_data import (
    build_task_index,
    compact_match_text,
    compact_text,
    descriptor_aliases,
    descriptor_matches_event_record,
    ensure_task_metadata,
    event_matches_status_entry,
    infer_hard_timepoint,
    infer_replan_policy,
    match_descriptor_to_event_record,
    normalize_aliases,
    normalize_calendar_events,
    normalize_calendar_provider,
    normalize_plan_details,
    normalize_status_log,
    stable_event_id,
    stable_task_id,
    task_title,
)


class CompactTextTests(unittest.TestCase):
    def test_collapses_whitespace(self) -> None:
        self.assertEqual(compact_text("  hello   world  "), "hello world")

    def test_empty_or_none(self) -> None:
        self.assertEqual(compact_text(""), "")
        self.assertEqual(compact_text(None), "")


class CompactMatchTextTests(unittest.TestCase):
    def test_removes_punctuation_and_lowercases(self) -> None:
        self.assertEqual(compact_match_text("Hello [World]"), "helloworld")

    def test_removes_chinese_brackets(self) -> None:
        self.assertEqual(compact_match_text("测试（内容）"), "测试内容")


class NormalizeAliasesTests(unittest.TestCase):
    def test_none_returns_empty(self) -> None:
        self.assertEqual(normalize_aliases(None), [])

    def test_string_returns_list(self) -> None:
        self.assertEqual(normalize_aliases("hello"), ["hello"])

    def test_list_deduplicates(self) -> None:
        self.assertEqual(normalize_aliases(["a", "b", "a"]), ["a", "b"])

    def test_filters_non_string(self) -> None:
        self.assertEqual(normalize_aliases([1, "valid", None]), ["valid"])

    def test_non_list_non_string_returns_empty(self) -> None:
        self.assertEqual(normalize_aliases(42), [])


class StableIdTests(unittest.TestCase):
    def test_task_id_format(self) -> None:
        result = stable_task_id("2026-03-15", "Test Task")
        self.assertTrue(result.startswith("task-"))
        self.assertEqual(len(result), 15)

    def test_event_id_format(self) -> None:
        result = stable_event_id("2026-03-15T09:00", "2026-03-15T10:00", "Event")
        self.assertTrue(result.startswith("evt-"))

    def test_deterministic(self) -> None:
        a = stable_task_id("date", "title")
        b = stable_task_id("date", "title")
        self.assertEqual(a, b)


class TaskTitleTests(unittest.TestCase):
    def test_returns_title(self) -> None:
        self.assertEqual(task_title({"title": "My Task"}), "My Task")

    def test_falls_back_to_title_match(self) -> None:
        self.assertEqual(task_title({"title_match": "Matched"}), "Matched")

    def test_falls_back_to_title_contains(self) -> None:
        self.assertEqual(task_title({"title_contains": "Contains"}), "Contains")

    def test_untitled_default(self) -> None:
        self.assertEqual(task_title({}), "Untitled task")


class DescriptorAliasesTests(unittest.TestCase):
    def test_includes_title_and_explicit_aliases(self) -> None:
        result = descriptor_aliases({"title": "Test", "aliases": ["Alias1"]})
        self.assertIn("Alias1", result)
        self.assertIn("Test", result)


class InferHardTimepointTests(unittest.TestCase):
    def test_detects_timepoint_marker(self) -> None:
        self.assertTrue(infer_hard_timepoint("0h seeding", []))

    def test_no_marker(self) -> None:
        self.assertFalse(infer_hard_timepoint("Regular task", []))


class InferReplanPolicyTests(unittest.TestCase):
    def test_conditional(self) -> None:
        self.assertEqual(infer_replan_policy({"decision_rule": "check cells"}), "conditional")

    def test_manual_for_hard_timepoint(self) -> None:
        self.assertEqual(infer_replan_policy({"hard_timepoint": True}), "manual")

    def test_auto_default(self) -> None:
        self.assertEqual(infer_replan_policy({}), "auto")


class EnsureTaskMetadataTests(unittest.TestCase):
    def test_adds_task_id(self) -> None:
        result = ensure_task_metadata({"title": "Test"}, date_hint="2026-03-15")
        self.assertIn("task_id", result)
        self.assertTrue(result["task_id"].startswith("task-"))

    def test_preserves_existing_task_id(self) -> None:
        result = ensure_task_metadata({"title": "T", "task_id": "task-custom"}, date_hint="d")
        self.assertEqual(result["task_id"], "task-custom")

    def test_sets_replan_policy(self) -> None:
        result = ensure_task_metadata({"title": "T"}, date_hint="d")
        self.assertEqual(result["replan_policy"], "auto")


class NormalizePlanDetailsTests(unittest.TestCase):
    def test_empty_input(self) -> None:
        result = normalize_plan_details(None)
        self.assertIn("streams", result)
        self.assertIn("experiments", result)
        self.assertIn("days", result)
        self.assertGreaterEqual(result["schema_version"], 2)

    def test_adds_task_ids_to_day_tasks(self) -> None:
        plan = {
            "days": [{"date": "2026-03-15", "tasks": [{"title": "Task A"}]}],
        }
        result = normalize_plan_details(plan)
        task = result["days"][0]["tasks"][0]
        self.assertIn("task_id", task)

    def test_chains_experiment_step_dependencies(self) -> None:
        plan = {
            "experiments": [{
                "id": "exp1",
                "steps": [
                    {"title": "Step 1", "date": "2026-03-15"},
                    {"title": "Step 2", "date": "2026-03-16"},
                ],
            }],
        }
        result = normalize_plan_details(plan)
        steps = result["experiments"][0]["steps"]
        self.assertEqual(steps[1]["depends_on"], [steps[0]["task_id"]])


class NormalizeCalendarProviderTests(unittest.TestCase):
    def test_none_defaults_to_file(self) -> None:
        self.assertEqual(normalize_calendar_provider(None), "file")

    def test_none_string_defaults_to_file(self) -> None:
        self.assertEqual(normalize_calendar_provider("none"), "file")

    def test_valid_providers(self) -> None:
        for provider in ("file", "macos", "ics"):
            self.assertEqual(normalize_calendar_provider(provider), provider)

    def test_invalid_raises(self) -> None:
        with self.assertRaises(ValueError):
            normalize_calendar_provider("google")


class NormalizeStatusLogTests(unittest.TestCase):
    def test_empty_input(self) -> None:
        result = normalize_status_log(None)
        self.assertEqual(result["statuses"], [])
        self.assertGreaterEqual(result["schema_version"], 2)

    def test_normalizes_aliases(self) -> None:
        result = normalize_status_log({
            "statuses": [{"title_match": "Test", "aliases": "single"}],
        })
        self.assertEqual(result["statuses"][0]["aliases"], ["single"])


class NormalizeCalendarEventsTests(unittest.TestCase):
    def test_empty_input(self) -> None:
        self.assertEqual(normalize_calendar_events(None), [])

    def test_assigns_event_id(self) -> None:
        events = [{"start": "2026-03-15T09:00", "end": "2026-03-15T10:00", "title": "Test", "calendar": "Research"}]
        result = normalize_calendar_events(events)
        self.assertTrue(result[0]["event_id"].startswith("evt-"))

    def test_skips_non_dict(self) -> None:
        result = normalize_calendar_events(["not a dict", {"start": "x", "end": "y", "title": "T", "calendar": "R"}])
        self.assertEqual(len(result), 1)


class DescriptorMatchesEventRecordTests(unittest.TestCase):
    def test_task_id_match(self) -> None:
        score, reason = descriptor_matches_event_record(
            {"task_id": "task-abc"}, {"task_id": "task-abc"}
        )
        self.assertEqual(score, 400)
        self.assertEqual(reason, "task_id")

    def test_title_match(self) -> None:
        score, reason = descriptor_matches_event_record(
            {"title_match": "My Event"}, {"title": "My Event"}
        )
        self.assertEqual(score, 300)

    def test_no_match(self) -> None:
        score, _reason = descriptor_matches_event_record(
            {"title": "Completely different"}, {"title": "Unrelated event"}
        )
        self.assertLess(score, 100)


class MatchDescriptorToEventRecordTests(unittest.TestCase):
    def test_returns_best_match(self) -> None:
        descriptors = [
            {"task_id": "task-1", "title": "A"},
            {"task_id": "task-2", "title": "B"},
        ]
        event = {"task_id": "task-2", "title": "B"}
        result = match_descriptor_to_event_record(descriptors, event)
        self.assertIsNotNone(result)
        self.assertEqual(result["task_id"], "task-2")

    def test_returns_none_below_threshold(self) -> None:
        result = match_descriptor_to_event_record(
            [{"title": "xxxxxx"}], {"title": "yyyyyy"}
        )
        self.assertIsNone(result)


class EventMatchesStatusEntryTests(unittest.TestCase):
    def test_task_id_match(self) -> None:
        self.assertTrue(event_matches_status_entry(
            {"task_id": "task-abc"}, {"task_id": "task-abc"}
        ))

    def test_title_match(self) -> None:
        self.assertTrue(event_matches_status_entry(
            {"title_match": "My Event"}, {"title": "My Event"}
        ))

    def test_title_contains(self) -> None:
        self.assertTrue(event_matches_status_entry(
            {"title_contains": "Event"}, {"title": "My Event Here"}
        ))

    def test_no_match(self) -> None:
        self.assertFalse(event_matches_status_entry(
            {"title_match": "A"}, {"title": "B"}
        ))


class BuildTaskIndexTests(unittest.TestCase):
    def test_indexes_day_tasks(self) -> None:
        plan = {
            "experiments": [],
            "days": [{"date": "2026-03-15", "tasks": [{"title": "Task X"}]}],
        }
        index = build_task_index(plan)
        self.assertEqual(len(index), 1)
        entry = list(index.values())[0]
        self.assertEqual(entry["title"], "Task X")
        self.assertEqual(entry["source_kind"], "day_task")

    def test_indexes_experiment_steps(self) -> None:
        plan = {
            "experiments": [{"id": "exp1", "steps": [{"title": "Step A", "date": "2026-03-15"}]}],
            "days": [],
        }
        index = build_task_index(plan)
        self.assertEqual(len(index), 1)
        entry = list(index.values())[0]
        self.assertEqual(entry["source_kind"], "experiment_step")


if __name__ == "__main__":
    unittest.main()
