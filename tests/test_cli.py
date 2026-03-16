from __future__ import annotations

import unittest

from planner.cli import normalize_cli_argv


class NormalizeCliArgvTests(unittest.TestCase):
    def test_workspace_after_subcommand_is_moved_forward(self) -> None:
        argv = ["init", "--mode", "demo", "--workspace", "./workspace_demo"]
        self.assertEqual(
            normalize_cli_argv(argv),
            ["--workspace", "./workspace_demo", "init", "--mode", "demo"],
        )

    def test_workspace_before_subcommand_is_preserved(self) -> None:
        argv = ["--workspace", "./workspace_demo", "refresh"]
        self.assertEqual(normalize_cli_argv(argv), argv)

    def test_workspace_equals_form_is_supported(self) -> None:
        argv = ["summary", "--period", "month", "--workspace=./workspace_demo"]
        self.assertEqual(
            normalize_cli_argv(argv),
            ["--workspace=./workspace_demo", "summary", "--period", "month"],
        )


if __name__ == "__main__":
    unittest.main()
