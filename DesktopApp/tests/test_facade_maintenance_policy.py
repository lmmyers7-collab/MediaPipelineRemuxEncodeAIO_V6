from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.maintenance.policy import (
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
                ("PowerShell (pwsh)", True, r"C:\Pipeline\PowerShell-7.6.0-win-x64\pwsh.exe"),
                ("ffmpeg", False, "Not found in bundled Tools or system PATH"),
                ("ffprobe", True, r"C:\Pipeline\Tools\ffmpeg\bin\ffprobe.exe"),
                ("nvidia-smi (optional)", False, "Not found - GPU encoder telemetry unavailable"),
            ]
        )

        evidence = maintenance_toolchain_evidence(rows)
        by_name = {row["name"]: row for row in evidence["rows"]}

        self.assertEqual(evidence["schema_version"], "desktop_maintenance_toolchain_evidence.v1")
        self.assertTrue(evidence["read_only"])
        self.assertEqual(evidence["operator_status"], "blocked")
        self.assertEqual(evidence["required_missing_count"], 1)
        self.assertEqual(evidence["optional_review_count"], 1)
        self.assertEqual(by_name["PowerShell (pwsh)"]["source"], "bundled")
        self.assertEqual(by_name["ffmpeg"]["operator_status"], "blocked")
        self.assertIn("media jobs may fail", by_name["ffmpeg"]["failure_scope"])
        self.assertEqual(by_name["nvidia-smi (optional)"]["operator_status"], "review")
        self.assertIn("Optional visibility", by_name["nvidia-smi (optional)"]["failure_scope"])
        self.assertIn("WebView does not resolve arbitrary tools", "\n".join(evidence["summary_lines"]))

        ffprobe = maintenance_toolchain_row(by_name["ffprobe"])
        self.assertEqual(ffprobe["tool_kind"], "ffprobe")
        self.assertIn("Media probing", ffprobe["capability"])


if __name__ == "__main__":
    unittest.main()
