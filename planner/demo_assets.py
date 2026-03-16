#!/usr/bin/env python3
"""Refresh tracked demo HTML outputs and optional screenshots."""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Refresh demo sample outputs from the tracked workspace seed.")
    parser.add_argument("--workspace-root", required=True, help="Demo workspace root.")
    parser.add_argument("--skip-screenshots", action="store_true", help="Skip PNG screenshot refresh.")
    return parser.parse_args()


def run_cli(*args: str) -> None:
    subprocess.run([sys.executable, "-m", "planner.cli", *args], check=True)


def maybe_refresh_screenshot(html_path: Path, png_path: Path) -> str:
    try:
        from playwright.sync_api import sync_playwright  # type: ignore
    except Exception:
        return "Skipped screenshot refresh: Playwright is not available."

    png_path.parent.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page(viewport={"width": 1720, "height": 1280}, device_scale_factor=2)
        page.goto(html_path.resolve().as_uri(), wait_until="networkidle")
        page.screenshot(path=str(png_path), full_page=True)
        browser.close()
    return f"Refreshed screenshot: {png_path}"


def main() -> int:
    args = parse_args()
    workspace_root = Path(args.workspace_root).expanduser().resolve()
    repo_root = workspace_root.parent.parent.parent
    sample_output_dir = repo_root / "examples" / "wetlab_demo" / "sample_outputs"
    sample_history_dir = repo_root / "examples" / "wetlab_demo" / "history" / "summaries"
    screenshots_dir = repo_root / "assets" / "screenshots"
    sample_output_dir.mkdir(parents=True, exist_ok=True)
    sample_history_dir.mkdir(parents=True, exist_ok=True)
    screenshots_dir.mkdir(parents=True, exist_ok=True)

    run_cli("--workspace", str(workspace_root), "refresh")
    run_cli("--workspace", str(workspace_root), "summary", "--period", "month", "--target", "2026-03")
    run_cli("--workspace", str(workspace_root), "summary", "--period", "quarter", "--target", "2026-Q1")
    run_cli("--workspace", str(workspace_root), "summary", "--period", "year", "--target", "2026")

    tracked = {
        workspace_root / "outputs" / "future_experiment_schedule.html": sample_output_dir / "dashboard.html",
        workspace_root / "history" / "summaries" / "2026-03.html": sample_output_dir / "history-month.html",
        workspace_root / "history" / "summaries" / "2026-Q1.html": sample_output_dir / "history-quarter.html",
        workspace_root / "history" / "summaries" / "2026.html": sample_output_dir / "history-year.html",
    }
    for source, target in tracked.items():
        shutil.copy2(source, target)
        print(target)

    for source_name in ("2026-03.html", "2026-Q1.html", "2026.html"):
        source = workspace_root / "history" / "summaries" / source_name
        target = sample_history_dir / source_name
        shutil.copy2(source, target)
        print(target)

    if not args.skip_screenshots:
        print(maybe_refresh_screenshot(sample_output_dir / "dashboard.html", screenshots_dir / "dashboard.png"))
        print(maybe_refresh_screenshot(sample_output_dir / "history-month.html", screenshots_dir / "history-month.png"))
    else:
        print("Skipped screenshot refresh by request.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
