from __future__ import annotations

import datetime as dt
import unittest
from unittest.mock import patch
from zoneinfo import ZoneInfo

from planner.report_parser import (
    best_event_match,
    collect_events,
    detect_report_date,
    empty_payload,
    infer_status_candidates,
    load_status_log,
    merge_status_candidates,
    parse_daily_report,
    split_inline_items,
)


class SplitInlineItemsTests(unittest.TestCase):
    def test_empty_string(self) -> None:
        self.assertEqual(split_inline_items(""), [])

    def test_blank_bullet(self) -> None:
        self.assertEqual(split_inline_items("-"), [])
        self.assertEqual(split_inline_items(" - "), [])

    def test_single_item(self) -> None:
        self.assertEqual(split_inline_items("check samples"), ["check samples"])

    def test_semicolon_separated(self) -> None:
        result = split_inline_items("item A; item B；item C")
        self.assertEqual(result, ["item A", "item B", "item C"])

    def test_strips_leading_dash(self) -> None:
        result = split_inline_items("- something")
        self.assertEqual(result, ["something"])


class DetectReportDateTests(unittest.TestCase):
    def test_english_format(self) -> None:
        text = "Date: 2026-03-15\n\nSome content"
        self.assertEqual(detect_report_date(text), "2026-03-15")

    def test_chinese_format(self) -> None:
        text = "日期：2026-04-01\n\nSome content"
        self.assertEqual(detect_report_date(text), "2026-04-01")

    def test_no_date(self) -> None:
        text = "No date line here\nJust content"
        self.assertIsNone(detect_report_date(text))

    def test_invalid_date_format_not_matched(self) -> None:
        text = "Date: March 15 2026\n"
        self.assertIsNone(detect_report_date(text))

    def test_date_must_be_on_own_line(self) -> None:
        text = "prefix Date: 2026-03-15\n"
        self.assertIsNone(detect_report_date(text))


class EmptyPayloadTests(unittest.TestCase):
    def test_structure(self) -> None:
        payload = empty_payload("2026-03-15")
        self.assertEqual(payload["date"], "2026-03-15")
        self.assertIn("execution", payload)
        self.assertIn("completed", payload["execution"])
        self.assertIn("incomplete", payload["execution"])
        self.assertIn("reasons", payload["execution"])
        self.assertEqual(payload["analysis"], [])
        self.assertEqual(payload["tomorrow"], [])


class ParseDailyReportTests(unittest.TestCase):
    def test_full_english_report(self) -> None:
        text = """Date: 2026-03-15

Experiment Execution:
- Completed:
  - Finished RNA extraction
  - Ran qPCR
- Not completed:
  - Cell passaging
- Reasons:
  - Equipment malfunction

Key Status:
- Cells / samples:
  - 80% confluence
- Animals:
  - Cohort A healthy
- Instruments / reagents:
  - Centrifuge repaired

Analysis & Writing:
- Updated figure 3
- Drafted methods section

Tomorrow Must-Do:
- Cell passaging
- Data analysis
"""
        payload = parse_daily_report(text, "2026-03-15")
        self.assertEqual(payload["date"], "2026-03-15")
        self.assertEqual(payload["execution"]["completed"], ["Finished RNA extraction", "Ran qPCR"])
        self.assertEqual(payload["execution"]["incomplete"], ["Cell passaging"])
        self.assertEqual(payload["execution"]["reasons"], ["Equipment malfunction"])
        self.assertEqual(payload["status"]["cells"], ["80% confluence"])
        self.assertEqual(payload["status"]["animals"], ["Cohort A healthy"])
        self.assertEqual(payload["status"]["instruments"], ["Centrifuge repaired"])
        self.assertEqual(payload["analysis"], ["Updated figure 3", "Drafted methods section"])
        self.assertEqual(payload["tomorrow"], ["Cell passaging", "Data analysis"])

    def test_chinese_report(self) -> None:
        text = """日期：2026-03-16

实验执行：
- 完成了：
  - RNA提取
- 没完成：
  - 细胞传代
- 原因：
  - 设备故障

关键状态：
- 细胞/样本：
  - 80%汇合度
- 动物：
  - 正常
- 仪器/试剂：
  - 已修复

数据分析与写作：
- 更新图表

明天必须做：
- 传代
"""
        payload = parse_daily_report(text, "2026-03-16")
        self.assertEqual(payload["execution"]["completed"], ["RNA提取"])
        self.assertEqual(payload["execution"]["incomplete"], ["细胞传代"])
        self.assertEqual(payload["execution"]["reasons"], ["设备故障"])
        self.assertEqual(payload["status"]["cells"], ["80%汇合度"])
        self.assertEqual(payload["analysis"], ["更新图表"])
        self.assertEqual(payload["tomorrow"], ["传代"])

    def test_ignores_blank_analysis_and_tomorrow_items(self) -> None:
        text = """Date: 2026-03-16

Analysis & Writing:
-

Tomorrow Must-Do:
-
"""
        payload = parse_daily_report(text, "2026-03-16")
        self.assertEqual(payload["analysis"], [])
        self.assertEqual(payload["tomorrow"], [])

    def test_inline_completed_items(self) -> None:
        text = """Date: 2026-03-17

Experiment Execution:
- Completed: task A; task B
- Not completed:
- Reasons:
"""
        payload = parse_daily_report(text, "2026-03-17")
        self.assertEqual(payload["execution"]["completed"], ["task A", "task B"])

    def test_empty_report(self) -> None:
        text = "Date: 2026-03-17\n"
        payload = parse_daily_report(text, "2026-03-17")
        self.assertEqual(payload["execution"]["completed"], [])
        self.assertEqual(payload["execution"]["incomplete"], [])


class InferStatusCandidatesTests(unittest.TestCase):
    def _make_event(self, title: str, date: str = "2026-03-15", task_id: str | None = None) -> dict:
        tz = ZoneInfo("Asia/Shanghai")
        start = dt.datetime.combine(dt.date.fromisoformat(date), dt.time(9, 0), tzinfo=tz)
        end = start + dt.timedelta(hours=2)
        return {
            "title": title,
            "short_title": title,
            "calendar": "Research",
            "start": start,
            "end": end,
            "task_id": task_id,
            "aliases": [title],
        }

    def test_completed_item_matched(self) -> None:
        payload = empty_payload("2026-03-15")
        payload["execution"]["completed"] = ["RNA extraction"]
        events = [self._make_event("RNA extraction")]
        candidates = infer_status_candidates(payload, events)
        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0]["status"], "completed")
        self.assertEqual(candidates[0]["title_match"], "RNA extraction")

    def test_incomplete_item_basic(self) -> None:
        payload = empty_payload("2026-03-15")
        payload["execution"]["incomplete"] = ["Cell passaging"]
        events = [self._make_event("Cell passaging")]
        candidates = infer_status_candidates(payload, events)
        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0]["status"], "incomplete")

    def test_incomplete_with_move_hint_becomes_moved(self) -> None:
        payload = empty_payload("2026-03-15")
        payload["execution"]["incomplete"] = ["Cell passaging reschedule to Monday"]
        payload["execution"]["reasons"] = []
        events = [self._make_event("Cell passaging")]
        candidates = infer_status_candidates(payload, events)
        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0]["status"], "moved")

    def test_incomplete_with_move_hint_in_reasons(self) -> None:
        payload = empty_payload("2026-03-15")
        payload["execution"]["incomplete"] = ["Cell passaging"]
        payload["execution"]["reasons"] = ["delay to next week"]
        events = [self._make_event("Cell passaging")]
        candidates = infer_status_candidates(payload, events)
        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0]["status"], "moved")

    def test_future_event_excluded(self) -> None:
        payload = empty_payload("2026-03-15")
        payload["execution"]["completed"] = ["Future task"]
        events = [self._make_event("Future task", date="2026-03-16")]
        candidates = infer_status_candidates(payload, events)
        self.assertEqual(len(candidates), 0)

    def test_no_matching_event(self) -> None:
        payload = empty_payload("2026-03-15")
        payload["execution"]["completed"] = ["Completely unrelated task name"]
        events = [self._make_event("RNA extraction")]
        candidates = infer_status_candidates(payload, events)
        self.assertEqual(len(candidates), 0)


class MergeStatusCandidatesTests(unittest.TestCase):
    def test_append_new_candidate(self) -> None:
        status_log = {"statuses": []}
        candidates = [{"date": "2026-03-15", "title_match": "Task A", "status": "completed"}]
        result = merge_status_candidates(status_log, candidates)
        self.assertEqual(len(result["statuses"]), 1)
        self.assertEqual(result["statuses"][0]["title_match"], "Task A")

    def test_update_existing_by_title(self) -> None:
        status_log = {"statuses": [{"date": "2026-03-15", "title_match": "Task A", "status": "incomplete"}]}
        candidates = [{"date": "2026-03-15", "title_match": "Task A", "status": "completed", "note": "done"}]
        result = merge_status_candidates(status_log, candidates)
        self.assertEqual(len(result["statuses"]), 1)
        self.assertEqual(result["statuses"][0]["status"], "completed")
        self.assertEqual(result["statuses"][0]["note"], "done")

    def test_update_existing_by_task_id(self) -> None:
        status_log = {"statuses": [{"date": "2026-03-15", "task_id": "task-abc", "status": "incomplete"}]}
        candidates = [{"date": "2026-03-15", "task_id": "task-abc", "status": "moved"}]
        result = merge_status_candidates(status_log, candidates)
        self.assertEqual(len(result["statuses"]), 1)
        self.assertEqual(result["statuses"][0]["status"], "moved")

    def test_sorted_by_date_and_title(self) -> None:
        status_log = {"statuses": []}
        candidates = [
            {"date": "2026-03-16", "title_match": "B", "status": "completed"},
            {"date": "2026-03-15", "title_match": "A", "status": "completed"},
        ]
        result = merge_status_candidates(status_log, candidates)
        self.assertEqual(result["statuses"][0]["date"], "2026-03-15")
        self.assertEqual(result["statuses"][1]["date"], "2026-03-16")


class BestEventMatchTests(unittest.TestCase):
    def _make_event(self, title: str) -> dict:
        tz = ZoneInfo("Asia/Shanghai")
        start = dt.datetime(2026, 3, 15, 9, 0, tzinfo=tz)
        return {"title": title, "start": start, "end": start + dt.timedelta(hours=1)}

    def test_exact_match(self) -> None:
        events = [self._make_event("RNA extraction"), self._make_event("Cell culture")]
        result = best_event_match("RNA extraction", events, dt.date(2026, 3, 15))
        self.assertIsNotNone(result)
        self.assertEqual(result["title"], "RNA extraction")

    def test_no_match_returns_none(self) -> None:
        events = [self._make_event("RNA extraction")]
        result = best_event_match("Completely different topic", events, dt.date(2026, 3, 15))
        self.assertIsNone(result)

    def test_empty_events_returns_none(self) -> None:
        result = best_event_match("anything", [], dt.date(2026, 3, 15))
        self.assertIsNone(result)


class LoadStatusLogTests(unittest.TestCase):
    def test_nonexistent_file(self) -> None:
        from pathlib import Path
        result = load_status_log(Path("/tmp/nonexistent_status_log_test_12345.json"))
        self.assertIn("statuses", result)
        self.assertEqual(result["statuses"], [])


if __name__ == "__main__":
    unittest.main()
