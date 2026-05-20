from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from mediapipeline_desktop_app.application.facade_diagnostics_policy import (
    diagnostics_active_job_rows,
    diagnostics_launch_log_summary,
    diagnostics_summary_lines,
    diagnostics_tail_evidence,
    diagnostics_warnings,
)
from mediapipeline_desktop_app.models import ResolvedPaths, Snapshot


def _resolved() -> ResolvedPaths:
    root = Path("C:/MediaPipeline")
    return ResolvedPaths(
        app_root=root / "DesktopApp",
        workspace_root=root,
        pipeline_path=root / "Pipeline" / "MediaPipeline_chatgpt.ps1",
        config_path=root / "Pipeline" / "MediaPipeline_config.psd1",
        audit_script_path=root / "Pipeline" / "Audit-MediaLibrary_chatgpt.ps1",
        rerun_script_path=root / "Pipeline" / "Invoke-RerunCsv.ps1",
        powershell_host="pwsh.exe",
    )


def _snapshot(last_error: str | None = None) -> Snapshot:
    return Snapshot(
        resolved=_resolved(),
        current_activity="Idle",
        status_summary="Ready",
        log_tail="",
        progress=None,
        audit_progress=None,
        latest_failure_report=None,
        latest_failure_json=None,
        latest_audit_csv=None,
        latest_priority_csv=None,
        last_error=last_error,
    )


class DiagnosticsFacadePolicyTests(unittest.TestCase):
    def test_active_job_rows_are_stringified_and_fail_closed(self) -> None:
        self.assertEqual(diagnostics_active_job_rows(lambda _resolved: ["pipeline", 5], _resolved()), ["pipeline", "5"])
        self.assertEqual(diagnostics_active_job_rows(None, _resolved()), [])

        rows = diagnostics_active_job_rows(lambda _resolved: (_ for _ in ()).throw(ValueError("offline")), _resolved())

        self.assertEqual(rows, ["ActiveJobs summary unavailable: offline"])

    def test_summary_lines_split_service_output_and_report_failures(self) -> None:
        snapshot = _snapshot()

        self.assertEqual(diagnostics_summary_lines("format", lambda _snapshot: "one\n\ntwo", snapshot), ["one", "two"])
        self.assertEqual(diagnostics_summary_lines("format", None, snapshot), [])

        rows = diagnostics_summary_lines("format", lambda _snapshot: (_ for _ in ()).throw(RuntimeError("bad")), snapshot)

        self.assertEqual(rows, ["format unavailable: bad"])

    def test_launch_log_summary_and_snapshot_warnings(self) -> None:
        self.assertEqual(diagnostics_launch_log_summary(lambda: "launch ok"), "launch ok")
        self.assertEqual(diagnostics_launch_log_summary(lambda: None), "")
        self.assertEqual(diagnostics_launch_log_summary(None), "")
        self.assertEqual(diagnostics_launch_log_summary(lambda: (_ for _ in ()).throw(OSError("locked"))), "Launch log summary unavailable: locked")
        self.assertEqual(diagnostics_warnings(_snapshot("last failure")), ["last failure"])
        self.assertEqual(diagnostics_warnings(_snapshot()), [])

    def test_diagnostics_tail_evidence_classifies_operator_status(self) -> None:
        blocked = diagnostics_tail_evidence(
            text="starting ffmpeg\nERROR source locked\nTraceback unavailable\n",
            ok=True,
            exists=True,
            is_file=True,
        )
        self.assertEqual(blocked["evidence_authority"], "backend")
        self.assertEqual(blocked["operator_status"], "blocked")
        self.assertEqual(blocked["error_count"], 2)
        self.assertEqual(blocked["active_count"], 1)
        self.assertIn("ERROR source locked", blocked["issue_lines"])
        self.assertIn("read-only", blocked["guardrail"])

        review = diagnostics_tail_evidence(
            text="worker retry after timeout\n",
            warnings=["Log window was truncated"],
            ok=True,
            exists=True,
            is_file=True,
            truncated=True,
        )
        self.assertEqual(review["operator_status"], "review")
        self.assertGreaterEqual(review["warning_count"], 2)
        self.assertTrue(review["truncated"])

        active = diagnostics_tail_evidence(text="ffmpeg running\n", ok=True, exists=True, is_file=True)
        self.assertEqual(active["operator_status"], "active")
        self.assertIn("Close Readiness", active["safe_next_action"])

        ready = diagnostics_tail_evidence(text="completed normally\n", ok=True, exists=True, is_file=True)
        self.assertEqual(ready["operator_status"], "ready")


if __name__ == "__main__":
    unittest.main()
