from __future__ import annotations

import unittest
from pathlib import Path

from planner.validate import validate_workspace_files
from planner.workspace import build_paths


class ValidateWorkspaceTests(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
