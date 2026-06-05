from __future__ import annotations

import sys
import unittest
from pathlib import Path

from mediapipeline.tools.paths import find_repo_root

sys.path.insert(0, str(find_repo_root(Path(__file__)) / "src"))

from mediapipeline.core.maintenance.policy import (
    maintenance_health_progress,
    maintenance_health_row,
    maintenance_health_rows,
    maintenance_toolchain_evidence,
    maintenance_toolchain_row,
    maintenance_workspace_counts,
)


class MaintenanceFacadePolicyTests(unittest.TestCase):
    def test_maintenance_health_row_shapes_required_and_optional_tools(self) -> None:
        required = maintenance_health_row(("PowerShell 7", True, "pwsh.exe"))
        optional = maintenance_health_row(("optional NVIDIA telemetry", False, "nvidia-smi missing"))
        missing = maintenance_health_row(("FFmpeg", False, "ffmpeg missing"))
        active = maintenance_health_row(
            (
                "Process guard",
                False,
                "ActiveJobs record launch.json reports pipeline once as active and PID 123 is still running; Related MediaPipeline process PID(s) still running: 123",
            )
        )

        self.assertEqual(required["status"], "ok")
        self.assertFalse(required["optional"])
        self.assertEqual(required["tool_kind"], "powershell_host")
        self.assertEqual(required["tool_source"], "resolved_host")
        self.assertIn("PowerShell host", required["capability"])
        self.assertEqual(optional["status"], "warning")
        self.assertTrue(optional["optional"])
        self.assertEqual(optional["tool_kind"], "gpu_telemetry")
        self.assertEqual(missing["status"], "missing")
        self.assertEqual(missing["detail"], "ffmpeg missing")
        self.assertEqual(missing["tool_kind"], "ffmpeg")
        self.assertEqual(missing["tool_source"], "missing")
        self.assertIn("Remux/encode", missing["failure_scope"])
        self.assertEqual(active["status"], "running")
        self.assertEqual(active["operator_status"], "active")
        self.assertEqual(active["tool_source"], "backend_evidence")
        self.assertIn("expected while a pipeline run is in progress", active["operator_guidance"])

    def test_maintenance_health_rows_skip_malformed_items(self) -> None:
        rows = maintenance_health_rows(
            [
                ("PowerShell 7", True, "ok"),
                ("too", "short"),
                object(),
                ("Optional OCR helper", False, "not installed"),
            ]
        )

        self.assertEqual([row["name"] for row in rows], ["PowerShell 7", "Optional OCR helper"])

    def test_maintenance_workspace_counts_are_status_based(self) -> None:
        rows = maintenance_health_rows(
            [
                ("PowerShell 7", True, "ok"),
                ("FFmpeg", False, "missing"),
                ("optional NVIDIA telemetry", False, "missing"),
            ]
        )

        self.assertEqual(maintenance_workspace_counts(rows), {"ok_count": 1, "missing_count": 1, "warning_count": 1})
        self.assertIsNone(maintenance_health_row(("too", "short")))

    def test_maintenance_toolchain_evidence_summarizes_required_and_optional_impact(self) -> None:
        rows = maintenance_health_rows(
            [
                ("PowerShell (pwsh)", True, r"C:\ops\pipeline\runtime\PowerShell-7.6.0-win-x64\pwsh.exe"),
                ("Process guard", False, "Related MediaPipeline process PID(s) still running: 123"),
                ("ffmpeg", False, "Not found in bundled Tools or system PATH"),
                ("ffprobe", True, r"C:\ops\pipeline\tools\ffmpeg\bin\ffprobe.exe"),
                ("nvidia-smi (optional)", False, "Not found - GPU encoder telemetry unavailable"),
            ]
        )

        evidence = maintenance_toolchain_evidence(rows)
        by_name = {row["name"]: row for row in evidence["rows"]}

        self.assertEqual(evidence["schema_version"], "desktop_maintenance_toolchain_evidence.v1")
        self.assertTrue(evidence["read_only"])
        self.assertEqual(evidence["operator_status"], "blocked")
        self.assertEqual(evidence["required_missing_count"], 1)
        self.assertEqual(evidence["active_count"], 1)
        self.assertEqual(evidence["optional_review_count"], 1)
        self.assertEqual(by_name["PowerShell (pwsh)"]["source"], "resolved_host")
        self.assertEqual(by_name["Process guard"]["status"], "running")
        self.assertEqual(by_name["Process guard"]["operator_status"], "active")
        self.assertEqual(by_name["Process guard"]["source"], "backend_evidence")
        self.assertEqual(by_name["ffmpeg"]["operator_status"], "blocked")
        self.assertIn("media jobs may fail", by_name["ffmpeg"]["failure_scope"])
        self.assertEqual(by_name["nvidia-smi (optional)"]["operator_status"], "review")
        self.assertIn("Optional visibility", by_name["nvidia-smi (optional)"]["failure_scope"])
        self.assertIn("WebView does not resolve arbitrary tools", "\n".join(evidence["summary_lines"]))

        ffprobe = maintenance_toolchain_row(by_name["ffprobe"])
        self.assertEqual(ffprobe["tool_kind"], "ffprobe")
        self.assertIn("Media probing", ffprobe["capability"])

    def test_subtitle_tool_rows_get_specific_tool_kinds_and_progress(self) -> None:
        rows = maintenance_health_rows(
            [
                ("mkvextract", True, r"C:\ops\pipeline\tools\MKVToolNix\mkvextract.exe"),
                ("PgsToSrt (BDPGS OCR)", False, "BDPGS OCR tool not found."),
                ("PgsToSrt tessdata (BDPGS OCR)", True, r"C:\ops\pipeline\tools\PgsToSrt\tessdata"),
                ("SubtitleEdit.exe (VobSub OCR)", True, r"C:\ops\pipeline\tools\SubtitleEditLegacy\SubtitleEdit.exe"),
                ("Tesseract OCR (VobSub OCR)", True, r"C:\ops\pipeline\tools\SubtitleEditLegacy\Tesseract302\tesseract.exe"),
            ]
        )
        by_name = {row["name"]: row for row in rows}

        self.assertEqual(by_name["mkvextract"]["tool_kind"], "mkvextract")
        self.assertEqual(by_name["PgsToSrt (BDPGS OCR)"]["tool_kind"], "bdpgs_ocr")
        self.assertEqual(by_name["PgsToSrt tessdata (BDPGS OCR)"]["tool_kind"], "bdpgs_tessdata")
        self.assertEqual(by_name["SubtitleEdit.exe (VobSub OCR)"]["tool_kind"], "vobsub_ocr")
        self.assertEqual(by_name["Tesseract OCR (VobSub OCR)"]["tool_kind"], "vobsub_tesseract")

        progress = maintenance_health_progress(None, rows)
        steps = {step["id"]: step for step in progress["steps"]}

        self.assertEqual(steps["mkvextract"]["status"], "complete")
        self.assertEqual(steps["subtitle_bdpgs_ocr"]["status"], "blocked")
        self.assertIn("BDPGS OCR tool not found", steps["subtitle_bdpgs_ocr"]["detail"])
        self.assertEqual(steps["subtitle_vobsub_ocr"]["status"], "complete")

    def test_expanded_health_rows_get_specific_tool_kinds_and_progress(self) -> None:
        rows = maintenance_health_rows(
            [
                ("Config schema", True, r"C:\ops\pipeline\config\MediaPipeline_config.psd1; active config loaded and validated"),
                ("Configured root: SourceMovies", True, r"C:\Media\Movies"),
                ("Library output root: Movies", False, r"Directory not found: C:\Out\Movies"),
                ("Runtime state files", True, "State root readable; parsed 2 existing state artifact(s)."),
                ("SQLite mirror (optional)", True, "not present; JSON state remains authoritative."),
                ("API contract", True, "42 route contract(s) available."),
                ("Process guard", False, "Related MediaPipeline process PID(s) still running: 123"),
                ("Bundle layout", True, "Canonical scripts present."),
            ]
        )
        by_name = {row["name"]: row for row in rows}

        self.assertEqual(by_name["Config schema"]["tool_kind"], "config_schema")
        self.assertEqual(by_name["Configured root: SourceMovies"]["tool_kind"], "configured_root")
        self.assertEqual(by_name["Library output root: Movies"]["tool_kind"], "library_output_root")
        self.assertEqual(by_name["Runtime state files"]["tool_kind"], "runtime_state")
        self.assertEqual(by_name["SQLite mirror (optional)"]["tool_kind"], "sqlite_mirror")
        self.assertEqual(by_name["API contract"]["tool_kind"], "api_contract")
        self.assertEqual(by_name["Process guard"]["tool_kind"], "process_guard")
        self.assertEqual(by_name["Process guard"]["status"], "running")
        self.assertEqual(by_name["Process guard"]["operator_status"], "active")
        self.assertEqual(by_name["Bundle layout"]["tool_kind"], "bundle_layout")
        self.assertEqual(by_name["Library output root: Movies"]["operator_status"], "blocked")
        self.assertIn("Library-specific output", by_name["Library output root: Movies"]["failure_scope"])

        progress = maintenance_health_progress(None, rows)
        steps = {step["id"]: step for step in progress["steps"]}

        self.assertEqual(steps["config_parse"]["status"], "complete")
        self.assertEqual(steps["path_reachability"]["status"], "blocked")
        self.assertEqual(steps["state_directory"]["status"], "complete")
        self.assertEqual(steps["api_contract"]["status"], "complete")
        self.assertEqual(steps["process_guard"]["status"], "active")
        self.assertEqual(steps["bundle_layout"]["status"], "complete")


if __name__ == "__main__":
    unittest.main()
