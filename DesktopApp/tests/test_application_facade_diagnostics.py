from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from mediapipeline_desktop_app.application import MediaPipelineApplicationFacade
from mediapipeline_desktop_app.models import ResolvedPaths
from DesktopApp.tests.test_application_facade import DummyFacadeService, _resolved


class ApplicationFacadeDiagnosticsTests(unittest.TestCase):
    def test_facade_opens_only_allowlisted_diagnostics_locations(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            service = DummyFacadeService(root)
            facade = MediaPipelineApplicationFacade(service, app_version="v5-test")
            resolved = _resolved(root)
            run_logs = root / "RunLogs"
            run_logs.mkdir()
            cluster_log = root / "cluster.log"
            cluster_log.write_text("coordinator started\n", encoding="utf-8")
            latest_failure = root / "failures.txt"
            latest_failure.write_text("latest failure report", encoding="utf-8")
            latest_audit = root / "audit_summary_latest.csv"
            latest_audit.write_text("Path,Issue\n", encoding="utf-8")

            opened = facade.open_diagnostics_location(resolved, {"target": "run_logs"})
            opened_cluster_log = facade.open_diagnostics_location(resolved, {"target": "cluster_log"})
            opened_failure = facade.open_diagnostics_location(resolved, {"target": "latest_failure_report"})
            opened_audit = facade.open_diagnostics_location(resolved, {"target": "latest_audit_csv"})
            rejected = facade.open_diagnostics_location(resolved, {"target": str(root / "secret.txt")})
            missing = facade.open_diagnostics_location(resolved, {"target": "pending_publish"})

        self.assertTrue(opened.ok)
        self.assertEqual(opened.command, "diagnostics.open")
        self.assertEqual(opened.data["target"], "run_logs")
        self.assertTrue(opened_cluster_log.ok)
        self.assertEqual(opened_cluster_log.data["target"], "cluster_log")
        self.assertTrue(opened_failure.ok)
        self.assertEqual(opened_failure.data["target"], "latest_failure_report")
        self.assertTrue(opened_audit.ok)
        self.assertEqual(opened_audit.data["target"], "latest_audit_csv")
        self.assertEqual(service.opened_paths, [run_logs, cluster_log, latest_failure, latest_audit])
        self.assertFalse(rejected.ok)
        self.assertIn("not allowed", rejected.message)
        self.assertFalse(missing.ok)
        self.assertIn("No path is configured", missing.message)

    def test_facade_reads_only_allowlisted_diagnostics_tail(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            service = DummyFacadeService(root)
            facade = MediaPipelineApplicationFacade(service, app_version="v5-test")
            resolved = _resolved(root)
            assert resolved.active_jobs_path is not None
            resolved.active_jobs_path.mkdir(parents=True)
            cluster_log = root / "cluster.log"
            cluster_log.write_text("first line\n" + ("x" * 3000) + "\nlast line\n", encoding="utf-8")

            read_tail = facade.read_diagnostics_tail(resolved, {"target": "cluster_log", "max_bytes": 128})
            rejected = facade.read_diagnostics_tail(resolved, {"target": str(root / "secret.txt"), "max_bytes": 128})
            folder = facade.read_diagnostics_tail(resolved, {"target": "active_jobs", "max_bytes": 128})
            missing = facade.read_diagnostics_tail(resolved, {"target": "last_stderr_log", "max_bytes": 128})

        self.assertEqual(read_tail["schema_version"], "desktop_diagnostics_tail.v1")
        self.assertTrue(read_tail["ok"])
        self.assertEqual(read_tail["target"], "cluster_log")
        self.assertEqual(read_tail["max_bytes"], 1024)
        self.assertTrue(read_tail["truncated"])
        self.assertIn("last line", read_tail["text"])
        self.assertNotIn("first line", read_tail["text"])
        self.assertEqual(read_tail["evidence"]["evidence_authority"], "backend")
        self.assertEqual(read_tail["evidence"]["operator_status"], "review")
        self.assertTrue(read_tail["evidence"]["truncated"])
        self.assertFalse(rejected["ok"])
        self.assertIn("not allowed", "\n".join(rejected["errors"]))
        self.assertEqual(rejected["evidence"]["operator_status"], "blocked")
        self.assertFalse(folder["ok"])
        self.assertIn("non-regular file", "\n".join(folder["warnings"]))
        self.assertFalse(missing["ok"])
        self.assertIn("No path is configured", "\n".join(missing["warnings"]))

    def test_facade_summarizes_diagnostics_state_artifacts_read_only(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            service = DummyFacadeService(root)
            facade = MediaPipelineApplicationFacade(service, app_version="v5-test")
            resolved = _resolved(root)
            resolved.state_root = root / "State"
            resolved.queue_snapshot_path = root / "State" / "Progress" / "queue_snapshot.json"
            resolved.completed_manifest_path = root / "State" / "Completed" / "completed_jobs.jsonl"
            resolved.pending_push_path = root / "State" / "PendingPublish"
            resolved.failed_reports_path = root / "State" / "Failures" / "Reports"
            resolved.failed_markers_path = root / "State" / "Failures" / "Markers"
            for path in (
                resolved.state_root,
                resolved.queue_snapshot_path.parent,
                resolved.completed_manifest_path.parent,
                resolved.pending_push_path,
                resolved.failed_reports_path,
                resolved.failed_markers_path,
            ):
                assert path is not None
                path.mkdir(parents=True, exist_ok=True)
            resolved.queue_snapshot_path.write_text(json.dumps({"items": [{"Path": "Movie.mkv"}], "version": 1}), encoding="utf-8")
            resolved.completed_manifest_path.write_text(
                '{"schema_version":"completed_job.v1","output_path":"Movie.mkv"}\nnot json\n',
                encoding="utf-8",
            )
            (resolved.pending_push_path / "pending.json").write_text("{}", encoding="utf-8")
            (root / "failures.json").write_text(json.dumps([{"Reason": "bad encode"}]), encoding="utf-8")
            (root / "RunLogs").mkdir()
            (root / "RunLogs" / "run.stderr.log").write_text("WARNING retry\nERROR failed\n", encoding="utf-8")

            payload = facade.read_diagnostics_state_summary(resolved)

        self.assertEqual(payload["schema_version"], "desktop_diagnostics_state_summary.v1")
        self.assertIn("Read-only backend summary", payload["guardrail"])
        rows = {row["target"]: row for row in payload["targets"]}
        self.assertEqual(rows["queue_snapshot"]["status"], "ok")
        self.assertEqual(rows["queue_snapshot"]["operator_status"], "ready")
        self.assertEqual(rows["queue_snapshot"]["operator_status_state"], "ready")
        self.assertIn("Queue Snapshot explains", rows["queue_snapshot"]["operator_guidance"])
        self.assertEqual(rows["queue_snapshot"]["recommended_open_target"], "queue_snapshot")
        self.assertEqual(rows["queue_snapshot"]["recommended_tail_target"], "queue_snapshot")
        self.assertEqual(rows["queue_snapshot"]["recovery_stage"], "queue_launch_readiness")
        self.assertIn("runnable work", rows["queue_snapshot"]["unsafe_if_ignored"])
        self.assertIn("Top keys: items, version", "\n".join(rows["queue_snapshot"]["facts"]))
        self.assertEqual(rows["completed_manifest"]["status"], "warning")
        self.assertEqual(rows["completed_manifest"]["operator_status"], "review")
        self.assertEqual(rows["completed_manifest"]["operator_status_state"], "warning")
        self.assertEqual(rows["completed_manifest"]["recovery_stage"], "completed_output_proof")
        self.assertEqual(rows["completed_manifest"]["recommended_tail_target"], "completed_manifest")
        self.assertIn("JSONL invalid records: 1", "\n".join(rows["completed_manifest"]["facts"]))
        self.assertEqual(rows["pending_publish"]["status"], "ok")
        self.assertEqual(rows["pending_publish"]["recovery_stage"], "pending_publish_validation")
        self.assertIn("rerun files already waiting", rows["pending_publish"]["unsafe_if_ignored"])
        self.assertIn("parked outputs", rows["pending_publish"]["operator_guidance"])
        self.assertTrue(rows["pending_publish"]["recent_entries"])
        self.assertEqual(rows["last_stderr_log"]["status"], "missing")
        self.assertEqual(rows["last_stderr_log"]["operator_status"], "review")
        self.assertEqual(rows["last_stderr_log"]["operator_status_state"], "warning")
        self.assertEqual(rows["last_stderr_log"]["recommended_open_target"], "")
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["operator_status"], "review")
        self.assertEqual(payload["operator_status_state"], "warning")
        self.assertGreaterEqual(payload["operator_counts"]["review"], 1)
        self.assertGreaterEqual(payload["operator_status_state_counts"]["warning"], 1)
        self.assertIn("Backend state posture: review", "\n".join(payload["operator_summary"]))
        self.assertIn("Read order starts with", "\n".join(payload["operator_summary"]))
        self.assertEqual(payload["triage"][0]["target"], "completed_manifest")
        self.assertEqual(payload["triage"][0]["read_first_target"], "completed_manifest")
        self.assertIn("owning page", payload["triage"][0]["safe_next_action"])
        self.assertEqual(payload["counts"]["warning"], 1)
        self.assertGreaterEqual(payload["counts"]["missing"], 1)

    def test_facade_diagnostics_state_summary_surfaces_blocked_bdpgs_ocr_paths(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            service = DummyFacadeService(root)
            facade = MediaPipelineApplicationFacade(service, app_version="v5-test")
            resolved = _resolved(root)
            resolved.config_data = {
                "ConvertBdpgsToSrt": True,
                "BdpgsOcrToolPath": "Tools/PgsToSrt/missing-pgs-to-srt.dll",
                "BdpgsOcrTessdataPath": "Tools/PgsToSrt/missing-tessdata",
                "AllowSystemTools": False,
            }

            payload = facade.read_diagnostics_state_summary(resolved)

        self.assertEqual(payload["schema_version"], "desktop_diagnostics_state_summary.v1")
        self.assertFalse(payload["ok"])
        self.assertEqual(payload["operator_status"], "blocked")
        self.assertEqual(payload["settings_tool_path_evidence"]["schema_version"], "settings_tool_path_evidence.v1")
        self.assertEqual(len(payload["settings_tool_path_issues"]), 1)
        issue = payload["settings_tool_path_issues"][0]
        self.assertEqual(issue["target"], "settings_bdpgs_ocr_paths")
        self.assertEqual(issue["kind"], "settings")
        self.assertEqual(issue["status"], "error")
        self.assertEqual(issue["operator_status"], "blocked")
        self.assertEqual(issue["operator_status_state"], "blocked")
        self.assertEqual(issue["recovery_stage"], "settings_subtitle_ocr_readiness")
        self.assertIn("Settings > Subtitles", issue["operator_guidance"])
        self.assertIn("PGS subtitle conversion", issue["unsafe_if_ignored"])
        self.assertIn("BdpgsOcrToolPath", "\n".join(issue["facts"]))
        rows = {row["target"]: row for row in payload["targets"]}
        self.assertEqual(rows["settings_bdpgs_ocr_paths"]["operator_status"], "blocked")
        self.assertEqual(rows["settings_bdpgs_ocr_paths"]["operator_status_state"], "blocked")
        self.assertEqual(payload["triage"][0]["target"], "settings_bdpgs_ocr_paths")
        self.assertIn("Review the artifact detail", payload["triage"][0]["safe_next_action"])

    def test_diagnostics_path_lookup_failures_are_logged(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            service = DummyFacadeService(root)

            def fail_latest_report(_resolved: ResolvedPaths) -> Path | None:
                raise RuntimeError("report index locked")

            service.latest_failure_report = fail_latest_report  # type: ignore[method-assign]
            facade = MediaPipelineApplicationFacade(service, app_version="v5-test")
            resolved = _resolved(root)

            with self.assertLogs("test_application_facade", level="WARNING") as logs:
                result = facade.open_diagnostics_location(resolved, {"target": "latest_failure_report"})

        self.assertFalse(result.ok)
        self.assertIn("No path is configured for latest failure report", result.message)
        self.assertIn("Diagnostics path lookup failed for latest_failure_report", "\n".join(logs.output))
        self.assertIn("report index locked", "\n".join(logs.output))
