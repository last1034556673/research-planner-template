from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import yaml

from planner.config import (
    integration_settings,
    load_configs,
    merged_streams_from_config,
    resolve_workspace_path,
)
from planner.workspace import build_paths


class LoadConfigsTests(unittest.TestCase):
    def test_loads_from_blank_template(self) -> None:
        paths = build_paths(str(Path(__file__).resolve().parents[1] / "templates" / "blank_workspace"))
        configs = load_configs(paths)
        self.assertIn("project", configs)
        self.assertIn("constraints", configs)
        self.assertIn("integrations", configs)
        self.assertIn("workstreams", configs)

    def test_defaults_when_files_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            paths = build_paths(tmp)
            configs = load_configs(paths)
            self.assertEqual(configs["project"]["project_name"], "Research Planner")
            self.assertEqual(configs["project"]["timezone"], "Asia/Shanghai")

    def test_yaml_override(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            paths = build_paths(tmp)
            paths.config_dir.mkdir(parents=True, exist_ok=True)
            paths.project_config.write_text(
                yaml.dump({"project_name": "Custom Project"}),
                encoding="utf-8",
            )
            configs = load_configs(paths)
            self.assertEqual(configs["project"]["project_name"], "Custom Project")


class ResolveWorkspacePathTests(unittest.TestCase):
    def test_none_returns_fallback(self) -> None:
        paths = build_paths("/tmp/test_ws")
        result = resolve_workspace_path(paths, None, Path("/fallback"))
        self.assertEqual(result, Path("/fallback"))

    def test_absolute_path(self) -> None:
        paths = build_paths("/tmp/test_ws")
        result = resolve_workspace_path(paths, "/absolute/path", Path("/fallback"))
        self.assertEqual(result, Path("/absolute/path"))

    def test_relative_path(self) -> None:
        paths = build_paths("/tmp/test_ws")
        result = resolve_workspace_path(paths, "data/events.json", Path("/fallback"))
        self.assertEqual(result, Path("/tmp/test_ws/data/events.json"))


class IntegrationSettingsTests(unittest.TestCase):
    def test_normalizes_provider(self) -> None:
        paths = build_paths("/tmp/test_ws")
        configs = {
            "integrations": {
                "calendar_provider": "none",
                "event_source_file": "data/calendar_events.json",
            }
        }
        result = integration_settings(paths, configs)
        self.assertEqual(result["calendar_provider"], "file")

    def test_resolves_event_source_path(self) -> None:
        paths = build_paths("/tmp/test_ws")
        configs = {
            "integrations": {
                "calendar_provider": "file",
                "event_source_file": "data/custom.json",
            }
        }
        result = integration_settings(paths, configs)
        self.assertEqual(result["event_source_path"], Path("/tmp/test_ws/data/custom.json"))


class MergedStreamsFromConfigTests(unittest.TestCase):
    def test_extracts_id_and_label(self) -> None:
        configs = {
            "workstreams": {
                "streams": [
                    {"id": "cell", "label": "Cell Work", "color": "#000"},
                    {"id": "rna", "label": "RNA Analysis"},
                ]
            }
        }
        result = merged_streams_from_config(configs)
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]["id"], "cell")
        self.assertEqual(result[0]["label"], "Cell Work")

    def test_filters_incomplete_streams(self) -> None:
        configs = {
            "workstreams": {
                "streams": [
                    {"id": "cell"},
                    {"label": "No ID"},
                    {"id": "valid", "label": "Valid"},
                ]
            }
        }
        result = merged_streams_from_config(configs)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["id"], "valid")


if __name__ == "__main__":
    unittest.main()
