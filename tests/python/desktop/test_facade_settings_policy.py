from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

from mediapipeline.tools.paths import find_repo_root

sys.path.insert(0, str(find_repo_root(Path(__file__)) / "src"))

from mediapipeline.core.config.settings_policy import (
    settings_bdpgs_ocr_path_evidence,
    settings_config_path_value,
    settings_tool_path_evidence,
    settings_validation_exception_result,
    settings_validation_missing_values_result,
    settings_validation_result,
    settings_validation_unavailable_result,
    settings_vobsub_ocr_path_evidence,
    settings_workspace_paths,
)
from mediapipeline.desktop.models import ResolvedPaths


def _resolved(root: Path) -> ResolvedPaths:
    return ResolvedPaths(
        app_root=root / "DesktopApp",
        workspace_root=root,
        pipeline_path=root / "ops" / "pipeline" / "entrypoints" / "MediaPipeline.ps1",
        config_path=root / "ops" / "pipeline" / "config" / "MediaPipeline_config.psd1",
        audit_script_path=root / "ops" / "pipeline" / "entrypoints" / "Audit-MediaLibrary.ps1",
        rerun_script_path=root / "ops" / "pipeline" / "entrypoints" / "Invoke-RerunCsv.ps1",
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


class SettingsFacadePolicyTests(unittest.TestCase):
    def test_settings_workspace_paths_include_resolved_and_outsource_paths(self) -> None:
        root = Path("C:/MediaPipeline")
        paths = settings_workspace_paths(_resolved(root), {"Outsource": " C:/Plex/Movies "})

        self.assertEqual(paths["app_root"], str(root / "DesktopApp"))
        self.assertEqual(paths["workspace_root"], str(root))
        self.assertEqual(paths["outsource"], str(Path("C:/Plex/Movies")))
        self.assertEqual(paths["completed_manifest"], str(root / "State" / "Completed" / "completed_jobs.jsonl"))

    def test_settings_config_path_value_ignores_empty_values(self) -> None:
        self.assertEqual(settings_config_path_value({"Outsource": "C:/Out"}, "Outsource"), Path("C:/Out"))
        self.assertIsNone(settings_config_path_value({"Outsource": " "}, "Outsource"))
        self.assertIsNone(settings_config_path_value({}, "Outsource"))

    def test_settings_validation_result_shapes_pass_warning_and_error_states(self) -> None:
        passed = settings_validation_result({"A": 1}, [], [])
        warning = settings_validation_result({"A": 1, "B": 2}, [], ["be careful"])
        failed = settings_validation_result({"A": 1}, ["bad"], ["warn"])

        self.assertTrue(passed.ok)
        self.assertEqual(passed.severity, "info")
        self.assertEqual(passed.data["key_count"], 1)
        self.assertTrue(warning.ok)
        self.assertEqual(warning.message, "Settings validation passed with 1 warning(s).")
        self.assertFalse(failed.ok)
        self.assertEqual(failed.message, "Settings validation failed with 1 error(s).")
        self.assertEqual(failed.errors, ["bad"])

    def test_settings_validation_error_results_are_stable(self) -> None:
        self.assertEqual(settings_validation_missing_values_result().errors, ["Missing values object."])
        self.assertEqual(
            settings_validation_unavailable_result().errors,
            ["Settings validation service is not available."],
        )
        self.assertIn("offline", settings_validation_exception_result(RuntimeError("offline")).message)

    def test_bdpgs_ocr_path_evidence_reports_ready_relative_bundle_paths(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            tool = root / "ops" / "pipeline" / "tools" / "PgsToSrt" / "PgsToSrt.exe"
            tessdata = root / "ops" / "pipeline" / "tools" / "PgsToSrt" / "tessdata"
            tool.parent.mkdir(parents=True)
            tool.write_text("fake", encoding="utf-8")
            tessdata.mkdir()

            evidence = settings_bdpgs_ocr_path_evidence(
                _resolved(root),
                {
                    "ConvertBdpgsToSrt": True,
                    "AllowSystemTools": False,
                    "BdpgsOcrToolPath": r"Tools\PgsToSrt\PgsToSrt.exe",
                    "BdpgsOcrTessdataPath": r"Tools\PgsToSrt\tessdata",
                },
            )

        self.assertEqual(evidence["schema_version"], "settings_bdpgs_ocr_path_evidence.v1")
        self.assertEqual(evidence["operator_status"], "Ready")
        self.assertEqual(evidence["blocked_count"], 0)
        rows = {row["key"]: row for row in evidence["rows"]}
        self.assertEqual(rows["BdpgsOcrToolPath"]["status"], "ready")
        self.assertEqual(rows["BdpgsOcrToolPath"]["path_type"], "file")
        self.assertEqual(Path(rows["BdpgsOcrToolPath"]["resolved"]).resolve(), tool.resolve())
        self.assertEqual(rows["BdpgsOcrTessdataPath"]["status"], "ready")
        self.assertEqual(rows["BdpgsOcrTessdataPath"]["path_type"], "directory")

    def test_bdpgs_ocr_path_evidence_is_inactive_until_enabled(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            evidence = settings_bdpgs_ocr_path_evidence(
                _resolved(root),
                {
                    "AllowSystemTools": False,
                    "BdpgsOcrToolPath": "",
                    "BdpgsOcrTessdataPath": "",
                },
            )

        self.assertEqual(evidence["schema_version"], "settings_bdpgs_ocr_path_evidence.v1")
        self.assertEqual(evidence["operator_status"], "Inactive")
        rows = {row["key"]: row for row in evidence["rows"]}
        self.assertEqual(rows["BdpgsOcrToolPath"]["status"], "inactive")
        self.assertEqual(rows["BdpgsOcrTessdataPath"]["status"], "inactive")

    def test_vobsub_ocr_path_evidence_reports_ready_promoted_bundle_paths(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            tool = root / "ops" / "pipeline" / "tools" / "SubtitleEditLegacy" / "SubtitleEdit.exe"
            tesseract = root / "ops" / "pipeline" / "tools" / "SubtitleEditLegacy" / "Tesseract302" / "tesseract.exe"
            tool.parent.mkdir(parents=True)
            tesseract.parent.mkdir(parents=True)
            tool.write_text("fake", encoding="utf-8")
            tesseract.write_text("fake", encoding="utf-8")

            evidence = settings_vobsub_ocr_path_evidence(
                _resolved(root),
                {
                    "ConvertVobSubToSrt": True,
                    "AllowSystemTools": False,
                    "VobSubOcrToolPath": r"Tools\SubtitleEditLegacy\SubtitleEdit.exe",
                },
            )

        self.assertEqual(evidence["operator_status"], "Ready")
        rows = {row["key"]: row for row in evidence["rows"]}
        self.assertEqual(rows["VobSubOcrToolPath"]["status"], "ready")
        self.assertEqual(Path(rows["VobSubOcrToolPath"]["resolved"]).resolve(), tool.resolve())
        self.assertEqual(rows["tesseract"]["status"], "ready")
        self.assertEqual(Path(rows["tesseract"]["resolved"]).resolve(), tesseract.resolve())

    def test_bdpgs_ocr_path_evidence_blocks_missing_tool_when_ocr_enabled(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            evidence = settings_tool_path_evidence(
                _resolved(root),
                {
                    "ConvertBdpgsToSrt": True,
                    "AllowSystemTools": False,
                    "BdpgsOcrToolPath": r"Tools\PgsToSrt\missing.exe",
                    "BdpgsOcrTessdataPath": "",
                },
            )

        bdpgs = evidence["bdpgs_ocr"]
        vobsub = evidence["vobsub_ocr"]
        self.assertEqual(evidence["schema_version"], "settings_tool_path_evidence.v1")
        self.assertEqual(bdpgs["operator_status"], "Blocked")
        self.assertEqual(vobsub["operator_status"], "Inactive")
        rows = {row["key"]: row for row in bdpgs["rows"]}
        self.assertEqual(rows["BdpgsOcrToolPath"]["status"], "blocked")
        self.assertEqual(rows["BdpgsOcrToolPath"]["path_type"], "missing")
        self.assertEqual(rows["BdpgsOcrTessdataPath"]["status"], "ready")
        self.assertIn("Mutation guardrail", "\n".join(bdpgs["summary_lines"]))

    def test_vobsub_ocr_path_evidence_is_inactive_until_enabled(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            evidence = settings_vobsub_ocr_path_evidence(
                _resolved(root),
                {
                    "ConvertVobSubToSrt": False,
                    "AllowSystemTools": False,
                    "VobSubOcrToolPath": "",
                },
            )

        self.assertEqual(evidence["schema_version"], "settings_vobsub_ocr_path_evidence.v1")
        self.assertEqual(evidence["operator_status"], "Inactive")
        rows = {row["key"]: row for row in evidence["rows"]}
        self.assertEqual(rows["VobSubOcrToolPath"]["status"], "inactive")
        self.assertIn(rows["tesseract"]["status"], {"inactive", "ready"})

    def test_vobsub_ocr_path_evidence_blocks_missing_tool_when_enabled(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            evidence = settings_vobsub_ocr_path_evidence(
                _resolved(root),
                {
                    "ConvertVobSubToSrt": True,
                    "AllowSystemTools": False,
                    "VobSubOcrToolPath": r"Tools\SubtitleEdit\missing.exe",
                },
            )

        self.assertEqual(evidence["operator_status"], "Blocked")
        rows = {row["key"]: row for row in evidence["rows"]}
        self.assertEqual(rows["VobSubOcrToolPath"]["status"], "blocked")
        self.assertIn(rows["tesseract"]["status"], {"blocked", "ready"})
        self.assertIn("Tesseract", "\n".join(evidence["summary_lines"]))


if __name__ == "__main__":
    unittest.main()
