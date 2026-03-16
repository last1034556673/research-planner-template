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


if __name__ == "__main__":
    unittest.main()
