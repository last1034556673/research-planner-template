"""End-to-end integration tests exercising the full CLI workflow."""

from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
DEMO_SEED = REPO_ROOT / "examples" / "wetlab_demo" / "workspace_seed"
BLANK_TEMPLATE = REPO_ROOT / "templates" / "blank_workspace"


def run_cli(*args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["python3", "-m", "planner.cli", *args],
        cwd=REPO_ROOT,
        check=check,
        text=True,
        capture_output=True,
    )


class InitBlankWorkflowTests(unittest.TestCase):
    """Test: init blank → prepare-report → refresh → doctor."""

    def setUp(self) -> None:
        self.temp_dir = Path(tempfile.mkdtemp(prefix="research-planner-e2e-blank-"))
        self.workspace = self.temp_dir / "workspace"

    def tearDown(self) -> None:
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_init_blank_creates_workspace(self) -> None:
        run_cli("--workspace", str(self.workspace), "init", "--mode", "blank", "--no-input")
        self.assertTrue(self.workspace.exists())
        self.assertTrue((self.workspace / "config" / "project.yaml").exists())
        self.assertTrue((self.workspace / "data" / "plan_details.json").exists())

    def test_blank_workspace_passes_doctor(self) -> None:
        run_cli("--workspace", str(self.workspace), "init", "--mode", "blank", "--no-input")
        result = run_cli("--workspace", str(self.workspace), "doctor", "--json")
        report = json.loads(result.stdout)
        self.assertTrue(report["ok"])
        self.assertEqual(report["summary"]["errors"], 0)

    def test_prepare_report_creates_markdown(self) -> None:
        run_cli("--workspace", str(self.workspace), "init", "--mode", "blank", "--no-input")
        result = run_cli("--workspace", str(self.workspace), "prepare-report")
        report_path = Path(result.stdout.strip().splitlines()[-1])
        self.assertTrue(report_path.exists())
        content = report_path.read_text(encoding="utf-8")
        self.assertIn("Experiment Execution", content)

    def test_refresh_produces_html(self) -> None:
        run_cli("--workspace", str(self.workspace), "init", "--mode", "blank", "--no-input")
        result = run_cli("--workspace", str(self.workspace), "refresh")
        html_path = Path(result.stdout.strip().splitlines()[-1])
        self.assertTrue(html_path.exists())
        content = html_path.read_text(encoding="utf-8")
        self.assertIn("<!DOCTYPE html>", content)
        self.assertIn("<style>", content)


class InitDemoWorkflowTests(unittest.TestCase):
    """Test: init demo → ingest-report → refresh → summary → replan."""

    def setUp(self) -> None:
        self.temp_dir = Path(tempfile.mkdtemp(prefix="research-planner-e2e-demo-"))
        self.workspace = self.temp_dir / "workspace"

    def tearDown(self) -> None:
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_init_demo_creates_workspace_with_data(self) -> None:
        run_cli("--workspace", str(self.workspace), "init", "--mode", "demo", "--no-input")
        self.assertTrue((self.workspace / "data" / "calendar_events.json").exists())
        self.assertTrue((self.workspace / "data" / "plan_details.json").exists())
        events = json.loads((self.workspace / "data" / "calendar_events.json").read_text())
        self.assertGreater(len(events), 0)

    def test_full_ingest_refresh_summary_pipeline(self) -> None:
        run_cli("--workspace", str(self.workspace), "init", "--mode", "demo", "--no-input")
        report = self.workspace / "daily_reports" / "2026-03-15.md"
        self.assertTrue(report.exists(), f"Demo report missing: {report}")

        # Ingest the demo report
        run_cli("--workspace", str(self.workspace), "ingest-report", "--input", str(report))

        # Verify dashboard was generated
        dashboard = self.workspace / "outputs" / "future_experiment_schedule.html"
        self.assertTrue(dashboard.exists())
        html = dashboard.read_text(encoding="utf-8")
        self.assertIn("<!DOCTYPE html>", html)
        self.assertIn("Planner", html)

        # Verify status log was updated
        status_log = json.loads((self.workspace / "data" / "status_log.json").read_text())
        self.assertIn("statuses", status_log)

        # Verify history was archived
        self.assertTrue((self.workspace / "history" / "daily").exists())

        # Generate month summary
        result = run_cli("--workspace", str(self.workspace), "summary", "--period", "month", "--target", "2026-03")
        summary_path = Path(result.stdout.strip().splitlines()[-1])
        self.assertTrue(summary_path.exists())
        summary_html = summary_path.read_text(encoding="utf-8")
        self.assertIn("<!DOCTYPE html>", summary_html)
        self.assertIn("History Summary", summary_html)

    def test_replan_suggest_and_apply(self) -> None:
        run_cli("--workspace", str(self.workspace), "init", "--mode", "demo", "--no-input")
        report = self.workspace / "daily_reports" / "2026-03-15.md"

        # Suggest mode
        run_cli("--workspace", str(self.workspace), "replan", "--input", str(report))
        suggestion_path = self.workspace / "outputs" / "replan_suggestions" / "2026-03-15.json"
        self.assertTrue(suggestion_path.exists())
        suggestion = json.loads(suggestion_path.read_text())
        self.assertEqual(suggestion["report_date"], "2026-03-15")

        # Apply mode - copy fresh workspace since suggest already ran
        workspace2 = self.temp_dir / "workspace2"
        shutil.copytree(DEMO_SEED, workspace2)
        run_cli("--workspace", str(workspace2), "replan", "--input", str(workspace2 / "daily_reports" / "2026-03-15.md"), "--apply")
        plan = json.loads((workspace2 / "data" / "plan_details.json").read_text())
        self.assertIn("experiments", plan)

    def test_summary_all_periods(self) -> None:
        run_cli("--workspace", str(self.workspace), "init", "--mode", "demo", "--no-input")
        # Ingest first to populate history
        report = self.workspace / "daily_reports" / "2026-03-15.md"
        run_cli("--workspace", str(self.workspace), "ingest-report", "--input", str(report))

        for period, target in [("month", "2026-03"), ("quarter", "2026-Q1"), ("year", "2026")]:
            result = run_cli("--workspace", str(self.workspace), "summary", "--period", period, "--target", target)
            path = Path(result.stdout.strip().splitlines()[-1])
            self.assertTrue(path.exists(), f"Missing {period} summary: {path}")


class InitForceOverwriteTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = Path(tempfile.mkdtemp(prefix="research-planner-e2e-force-"))
        self.workspace = self.temp_dir / "workspace"

    def tearDown(self) -> None:
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_init_without_force_fails_on_existing(self) -> None:
        run_cli("--workspace", str(self.workspace), "init", "--mode", "blank", "--no-input")
        result = run_cli("--workspace", str(self.workspace), "init", "--mode", "blank", "--no-input", check=False)
        self.assertNotEqual(result.returncode, 0)

    def test_init_with_force_overwrites(self) -> None:
        run_cli("--workspace", str(self.workspace), "init", "--mode", "blank", "--no-input")
        marker = self.workspace / "custom_marker.txt"
        marker.write_text("test")
        run_cli("--workspace", str(self.workspace), "init", "--mode", "blank", "--no-input", "--force")
        self.assertFalse(marker.exists())


class DoctorNonexistentWorkspaceTests(unittest.TestCase):
    def test_reports_errors_for_missing_workspace(self) -> None:
        result = run_cli("--workspace", "/tmp/nonexistent-ws-12345", "doctor", "--json", check=False)
        report = json.loads(result.stdout)
        self.assertFalse(report["ok"])
        self.assertGreater(report["summary"]["errors"], 0)


if __name__ == "__main__":
    unittest.main()
