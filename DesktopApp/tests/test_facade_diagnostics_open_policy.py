from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from mediapipeline_desktop_app.application.facade_diagnostics_open_policy import (
    DIAGNOSTICS_OPEN_TARGETS,
    diagnostics_allowed_targets_error,
    diagnostics_open_data,
    diagnostics_open_disallowed_target_result,
    diagnostics_open_exception_result,
    diagnostics_open_failure_message,
    diagnostics_open_missing_message,
    diagnostics_open_missing_result,
    diagnostics_open_missing_warning,
    diagnostics_open_path,
    diagnostics_open_service_unavailable_result,
    diagnostics_open_success_result,
    diagnostics_open_success_message,
    diagnostics_open_target_label,
    normalize_diagnostics_open_target,
    optional_diagnostics_path,
)
from mediapipeline_desktop_app.models import ResolvedPaths


def _resolved(root: Path) -> ResolvedPaths:
    return ResolvedPaths(
        app_root=root / "DesktopApp",
        workspace_root=root,
        pipeline_path=root / "Pipeline" / "MediaPipeline.ps1",
        config_path=root / "Pipeline" / "config.psd1",
        audit_script_path=root / "Pipeline" / "audit.ps1",
        rerun_script_path=root / "Pipeline" / "rerun.ps1",
        powershell_host=str(root / "pwsh.exe"),
        state_root=root / "State",
        active_jobs_path=root / "State" / "ActiveJobs",
        pending_push_path=root / "PendingServerPush",
        failed_reports_path=root / "State" / "Failures" / "Reports",
        failed_markers_path=root / "State" / "Failures" / "Markers",
        audit_reports_path=root / "State" / "Audit",
        queue_snapshot_path=root / "State" / "Progress" / "queue_snapshot.json",
        completed_manifest_path=root / "State" / "Completed" / "completed_jobs.jsonl",
    )


class DiagnosticsOpenPolicyTests(unittest.TestCase):
    def test_target_normalization_and_allowlist_error_are_stable(self) -> None:
        self.assertEqual(normalize_diagnostics_open_target(" Run_Logs "), "run_logs")
        self.assertEqual(normalize_diagnostics_open_target(None), "")
        self.assertEqual(diagnostics_open_target_label("run_logs"), "Run logs folder")
        self.assertIsNone(diagnostics_open_target_label("not_allowed"))
        self.assertIn("run_logs", diagnostics_allowed_targets_error())
        self.assertIn("last_stderr_log", diagnostics_allowed_targets_error())
        self.assertIn("pending_publish", DIAGNOSTICS_OPEN_TARGETS)
        self.assertIn("latest_failure_report", DIAGNOSTICS_OPEN_TARGETS)
        self.assertIn("latest_audit_csv", DIAGNOSTICS_OPEN_TARGETS)
        self.assertIn("failed_markers", DIAGNOSTICS_OPEN_TARGETS)
        self.assertIn("active_jobs", DIAGNOSTICS_OPEN_TARGETS)

    def test_path_selection_uses_resolved_paths_and_launch_logs(self) -> None:
        root = Path("C:/MediaPipeline")
        resolved = _resolved(root)
        stdout = root / "DesktopApp" / "RunLogs" / "run.stdout.log"
        stderr = root / "DesktopApp" / "RunLogs" / "run.stderr.log"
        latest_failure_report = root / "State" / "Failures" / "Reports" / "round_failures.txt"
        latest_failure_json = root / "State" / "Failures" / "Reports" / "round_failures.json"
        latest_audit_csv = root / "State" / "Audit" / "audit_summary.csv"
        latest_priority_csv = root / "State" / "Audit" / "audit_summary.priority.csv"

        self.assertEqual(diagnostics_open_path(resolved, "run_logs"), resolved.app_root / "RunLogs")
        self.assertEqual(diagnostics_open_path(resolved, "config"), resolved.config_path)
        self.assertEqual(diagnostics_open_path(resolved, "config_folder"), resolved.config_path.parent)
        self.assertEqual(diagnostics_open_path(resolved, "workspace"), resolved.workspace_root)
        self.assertEqual(diagnostics_open_path(resolved, "state"), resolved.state_root)
        self.assertEqual(diagnostics_open_path(resolved, "pending_publish"), resolved.pending_push_path)
        self.assertEqual(diagnostics_open_path(resolved, "failed_reports"), resolved.failed_reports_path)
        self.assertEqual(diagnostics_open_path(resolved, "failed_markers"), resolved.failed_markers_path)
        self.assertEqual(diagnostics_open_path(resolved, "audit_reports"), resolved.audit_reports_path)
        self.assertEqual(diagnostics_open_path(resolved, "queue_snapshot"), resolved.queue_snapshot_path)
        self.assertEqual(diagnostics_open_path(resolved, "active_jobs"), resolved.active_jobs_path)
        self.assertEqual(diagnostics_open_path(resolved, "completed_manifest"), resolved.completed_manifest_path)
        self.assertEqual(diagnostics_open_path(resolved, "latest_failure_report", latest_failure_report=latest_failure_report), latest_failure_report)
        self.assertEqual(diagnostics_open_path(resolved, "latest_failure_json", latest_failure_json=latest_failure_json), latest_failure_json)
        self.assertEqual(diagnostics_open_path(resolved, "latest_audit_csv", latest_audit_csv=latest_audit_csv), latest_audit_csv)
        self.assertEqual(diagnostics_open_path(resolved, "latest_priority_csv", latest_priority_csv=latest_priority_csv), latest_priority_csv)
        self.assertEqual(diagnostics_open_path(resolved, "last_stdout_log", last_stdout_log=stdout), stdout)
        self.assertEqual(diagnostics_open_path(resolved, "last_stderr_log", last_stderr_log=stderr), stderr)
        self.assertIsNone(diagnostics_open_path(resolved, "not_allowed"))

    def test_optional_path_and_operator_messages_are_stable(self) -> None:
        path = Path("C:/MediaPipeline/RunLogs/run.stdout.log")
        error = RuntimeError("blocked")

        self.assertEqual(optional_diagnostics_path(path), path)
        self.assertIsNone(optional_diagnostics_path(None))
        self.assertIsNone(optional_diagnostics_path(object()))
        self.assertEqual(diagnostics_open_data("run_logs", path), {"target": "run_logs", "path": str(path)})
        self.assertEqual(diagnostics_open_success_message("run_logs"), "Opened Run logs folder.")
        self.assertEqual(diagnostics_open_missing_message("pending_publish"), "No path is configured for pending publish folder.")
        self.assertEqual(diagnostics_open_missing_warning("pending_publish"), "No path is configured for target 'pending_publish'.")
        self.assertEqual(diagnostics_open_failure_message("run_logs", error), "Could not open Run logs folder: blocked")

    def test_command_result_helpers_preserve_diagnostics_open_contract(self) -> None:
        path = Path("C:/MediaPipeline/RunLogs")

        disallowed = diagnostics_open_disallowed_target_result()
        missing = diagnostics_open_missing_result("pending_publish")
        unavailable = diagnostics_open_service_unavailable_result("run_logs", path)
        failed = diagnostics_open_exception_result("run_logs", path, RuntimeError("blocked"))
        opened = diagnostics_open_success_result("run_logs", path)

        self.assertEqual(disallowed.command, "diagnostics.open")
        self.assertIn("Allowed targets", disallowed.errors[0])
        self.assertEqual(missing.severity, "warning")
        self.assertEqual(missing.warnings, ["No path is configured for target 'pending_publish'."])
        self.assertEqual(unavailable.data, {"target": "run_logs", "path": str(path)})
        self.assertIn("blocked", failed.message)
        self.assertTrue(opened.ok)
        self.assertEqual(opened.message, "Opened Run logs folder.")
        self.assertEqual(opened.refresh_hint, "diagnostics")


if __name__ == "__main__":
    unittest.main()
