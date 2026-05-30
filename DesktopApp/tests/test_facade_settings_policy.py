from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config.settings_policy import (
    settings_bdpgs_ocr_path_evidence,
    settings_config_path_value,
    settings_tool_path_evidence,
    settings_validation_exception_result,
    settings_validation_missing_values_result,
    settings_validation_result,
    settings_validation_unavailable_result,
    settings_workspace_paths,
)
from mediapipeline_desktop_app.models import ResolvedPaths


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
            tool = root / "Pipeline" / "Tools" / "PgsToSrt" / "PgsToSrt.exe"
            tessdata = root / "Pipeline" / "Tools" / "PgsToSrt" / "tessdata"
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
        self.assertTrue(rows["BdpgsOcrToolPath"]["resolved"].endswith(str(Path("Tools") / "PgsToSrt" / "PgsToSrt.exe")))
        self.assertEqual(rows["BdpgsOcrTessdataPath"]["status"], "ready")
        self.assertEqual(rows["BdpgsOcrTessdataPath"]["path_type"], "directory")

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
        self.assertEqual(evidence["schema_version"], "settings_tool_path_evidence.v1")
        self.assertEqual(bdpgs["operator_status"], "Blocked")
        rows = {row["key"]: row for row in bdpgs["rows"]}
        self.assertEqual(rows["BdpgsOcrToolPath"]["status"], "blocked")
        self.assertEqual(rows["BdpgsOcrToolPath"]["path_type"], "missing")
        self.assertEqual(rows["BdpgsOcrTessdataPath"]["status"], "ready")
        self.assertIn("Mutation guardrail", "\n".join(bdpgs["summary_lines"]))


if __name__ == "__main__":
    unittest.main()
