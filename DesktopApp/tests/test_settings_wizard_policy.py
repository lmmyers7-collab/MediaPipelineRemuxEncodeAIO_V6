from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "DesktopApp"))

from app.config.settings_wizard import (  # noqa: E402
    validate_ffmpeg_tools,
    validate_wizard_paths,
    validate_wizard_payload,
    validate_worker_settings,
    wizard_changes,
)
from mediapipeline_desktop_app.models import ResolvedPaths  # noqa: E402


def _resolved(root: Path) -> ResolvedPaths:
    return ResolvedPaths(
        app_root=root / "DesktopApp",
        workspace_root=root,
        pipeline_path=root / "Pipeline" / "MediaPipeline.ps1",
        config_path=root / "Pipeline" / "MediaPipeline_config.psd1",
        audit_script_path=root / "Pipeline" / "Audit-MediaLibrary.ps1",
        rerun_script_path=root / "Pipeline" / "Invoke-RerunCsv.ps1",
        powershell_host="pwsh.exe",
        local_base=root / "LocalBase",
        state_root=root / "State",
        source_movies=root / "SourceMovies",
        source_tv=root / "SourceTV",
        pending_push_path=root / "PendingServerPush",
        queue_snapshot_path=root / "State" / "Queue" / "snapshot.json",
        active_jobs_path=root / "State" / "ActiveJobs",
        failed_reports_path=root / "State" / "Failed" / "Reports",
        failed_markers_path=root / "State" / "Failed" / "Markers",
        audit_reports_path=root / "AuditReports",
        completed_manifest_path=root / "State" / "Completed" / "completed_jobs.jsonl",
    )


class SettingsWizardPolicyTests(unittest.TestCase):
    def test_validate_wizard_paths_reports_malformed_library_rows(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            source = root / "Movies"
            source.mkdir()
            result = validate_wizard_paths(
                {
                    "libraries": [
                        "not-a-library-object",
                        {"name": "Movies", "source_path": str(source), "output_path": str(root / "Output")},
                    ],
                    "output": {"root": str(root / "Output")},
                    "scratch": {"path": str(root / "Scratch")},
                }
            )

        self.assertFalse(result["ok"])
        self.assertIn("Wizard library row 1 must be a JSON object.", result["errors"])
        self.assertTrue(any(row["label"] == "Library Movies" for row in result["rows"]))

    def test_validate_wizard_payload_reports_malformed_worker_settings(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            result = validate_wizard_payload(
                {
                    "libraries": [],
                    "output": {"root": str(root / "Output")},
                    "scratch": {"path": str(root / "Scratch")},
                    "workers": ["not-a-worker-object"],
                }
            )

        self.assertFalse(result["ok"])
        self.assertIn("Wizard workers must be a JSON object.", result["errors"])
        self.assertFalse(result["worker_validation"]["ok"])

    def test_validate_wizard_payload_reports_non_object_payload(self) -> None:
        result = validate_wizard_payload(["not-a-wizard-object"])

        self.assertFalse(result["ok"])
        self.assertIn("Settings Wizard payload must be a JSON object.", result["errors"])
        self.assertFalse(result["path_validation"]["ok"])

    def test_validate_worker_settings_reports_non_object_payload(self) -> None:
        result = validate_worker_settings(["not-a-worker-object"])

        self.assertFalse(result["ok"])
        self.assertEqual(result["errors"], ["Wizard workers must be a JSON object."])
        self.assertEqual(result["max_parallel_encodes"], 1)
        self.assertEqual(result["parallel_encode_mode"], "single")

    def test_wizard_changes_ignores_non_array_libraries_without_crashing(self) -> None:
        changes = wizard_changes(
            {
                "libraries": 42,
                "output": {"root": r"C:\Processed"},
                "scratch": {"path": r"C:\Scratch"},
            }
        )

        self.assertEqual(changes["Outsource"], r"C:\Processed")
        self.assertEqual(changes["LocalBase"], r"C:\Scratch")
        self.assertNotIn("SourceMovies", changes)
        self.assertNotIn("SourceTV", changes)

    def test_validate_ffmpeg_tools_reports_missing_or_non_file_paths(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            result = validate_ffmpeg_tools(
                _resolved(root),
                {
                    "wizard": {
                        "tools": {
                            "ffmpeg_path": str(root / "missing-ffmpeg.exe"),
                            "ffprobe_path": str(root),
                        }
                    }
                },
            )

        self.assertFalse(result["ok"])
        self.assertIn("FFmpeg: tool path not found", result["errors"])
        self.assertIn("ffprobe: tool path is not a file", result["errors"])
        self.assertFalse(result["blocks_unrelated_settings_save"])

    def test_validate_ffmpeg_tools_accepts_file_paths(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            ffmpeg = root / "ffmpeg.exe"
            ffprobe = root / "ffprobe.exe"
            ffmpeg.write_text("fake", encoding="utf-8")
            ffprobe.write_text("fake", encoding="utf-8")
            result = validate_ffmpeg_tools(
                _resolved(root),
                {"wizard": {"tools": {"ffmpeg_path": str(ffmpeg), "ffprobe_path": str(ffprobe)}}},
            )

        self.assertTrue(result["ok"])
        self.assertEqual(result["errors"], [])
        self.assertTrue(result["ffmpeg"]["ok"])
        self.assertTrue(result["ffprobe"]["ok"])


if __name__ == "__main__":
    unittest.main()
