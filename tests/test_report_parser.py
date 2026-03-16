from __future__ import annotations

import unittest

from planner.report_parser import parse_daily_report, split_inline_items


class ReportParserTests(unittest.TestCase):
    def test_split_inline_items_filters_empty_bullets(self) -> None:
        self.assertEqual(split_inline_items("-"), [])
        self.assertEqual(split_inline_items(" - "), [])

    def test_parse_daily_report_ignores_blank_analysis_and_tomorrow_items(self) -> None:
        text = """Date: 2026-03-16

Analysis & Writing:
- 

Tomorrow Must-Do:
- 
"""
        payload = parse_daily_report(text, "2026-03-16")
        self.assertEqual(payload["analysis"], [])
        self.assertEqual(payload["tomorrow"], [])


if __name__ == "__main__":
    unittest.main()
