from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

from mediapipeline.tools.paths import find_repo_root
from unittest.mock import patch

sys.path.insert(0, str(find_repo_root(Path(__file__)) / "src"))

from mediapipeline.desktop.application import MediaPipelineApplicationFacade
from mediapipeline.desktop.models import ResolvedPaths
from tests.python.desktop.application_facade_test_support import DummyFacadeService, DummyWorkflowFacadeService, _resolved


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
        self.assertEqual(payload["autonomy_health"]["schema_version"], "desktop_autonomy_health.v1")
        self.assertIn(payload["autonomy_health"]["overall_status"], {"ready", "review", "blocked"})
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

    def test_facade_diagnostics_state_summary_caps_large_directory_recent_entries(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            service = DummyFacadeService(root)
            facade = MediaPipelineApplicationFacade(service, app_version="v5-test")
            resolved = _resolved(root)
            resolved.pending_push_path = root / "State" / "PendingPublish"
            resolved.pending_push_path.mkdir(parents=True)
            base_time = 1_700_000_000
            for index in range(8):
                path = resolved.pending_push_path / f"old-{index:03d}.json"
                path.write_text("{}", encoding="utf-8")
                os.utime(path, (base_time + index, base_time + index))
            newest = resolved.pending_push_path / "zz-newest.json"
            newest.write_text("{}", encoding="utf-8")
            os.utime(newest, (base_time + 100, base_time + 100))

            with (
                patch("mediapipeline.core.diagnostics.state_summary.DIAGNOSTICS_STATE_SUMMARY_DIR_SCAN_LIMIT", 5),
                patch("mediapipeline.core.diagnostics.state_summary.DIAGNOSTICS_STATE_SUMMARY_RECENT_LIMIT", 3),
            ):
                payload = facade.read_diagnostics_state_summary(resolved)

        rows = {row["target"]: row for row in payload["targets"]}
        pending_entries = rows["pending_publish"]["recent_entries"]
        self.assertEqual(len(pending_entries), 3)
        self.assertIn("scan stopped after 5 entries", "\n".join(rows["pending_publish"]["warnings"]))
        self.assertIn("Files scanned: 5", "\n".join(rows["pending_publish"]["facts"]))

    def test_facade_diagnostics_state_summary_uses_bounded_pending_publish_scan(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            service = DummyWorkflowFacadeService(root)
            calls: list[dict[str, object]] = []
            original_scan = service.scan_pending_publish

            def wrapped_scan(resolved: ResolvedPaths, **kwargs: object) -> dict[str, object]:
                calls.append(dict(kwargs))
                return original_scan(resolved, **kwargs)

            service.scan_pending_publish = wrapped_scan  # type: ignore[method-assign]
            facade = MediaPipelineApplicationFacade(service, app_version="v5-test")
            resolved = _resolved(root)
            resolved.pending_push_path = root / "State" / "PendingPublish"
            resolved.pending_push_path.mkdir(parents=True)
            for index in range(10):
                (resolved.pending_push_path / f"movie-{index:04d}.mkv.manifest.json").write_text("{}", encoding="utf-8")

            payload = facade.read_diagnostics_state_summary(resolved)

        self.assertEqual(payload["schema_version"], "desktop_diagnostics_state_summary.v1")
        self.assertTrue(calls)
        self.assertEqual(calls[-1]["manifest_limit"], 500)
        self.assertFalse(calls[-1]["include_orphan_rows"])

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
        self.assertIn("Settings > Media Output", issue["operator_guidance"])
        self.assertIn("PGS subtitle conversion", issue["unsafe_if_ignored"])
        self.assertIn("BdpgsOcrToolPath", "\n".join(issue["facts"]))
        rows = {row["target"]: row for row in payload["targets"]}
        self.assertEqual(rows["settings_bdpgs_ocr_paths"]["operator_status"], "blocked")
        self.assertEqual(rows["settings_bdpgs_ocr_paths"]["operator_status_state"], "blocked")
        self.assertEqual(payload["triage"][0]["target"], "settings_bdpgs_ocr_paths")
        self.assertIn("Review the artifact detail", payload["triage"][0]["safe_next_action"])

    def test_facade_diagnostics_state_summary_surfaces_configured_path_health(self) -> None:
        health = {
            "schema_version": "desktop_configured_path_health.v1",
            "read_only": True,
            "operator_status": "blocked",
            "rows": [
                {
                    "key": "source_movies",
                    "label": "SourceMovies root",
                    "role": "source",
                    "path": r"\\LAYNE-SERVER\Video\Movies",
                    "configured_key": "SourceMovies",
                    "is_unc": True,
                    "server": "LAYNE-SERVER",
                    "share": "Video",
                    "status": "blocked",
                    "operator_status": "blocked",
                    "health_code": "path_missing_or_unreachable",
                    "exists": False,
                    "path_kind": "missing",
                    "can_list": False,
                    "elapsed_ms": 1500,
                    "probe_attempts": [
                        {
                            "attempt": 1,
                            "timeout_seconds": 5.0,
                            "timed_out": False,
                            "elapsed_ms": 1500,
                            "status_hint": "missing",
                        }
                    ],
                    "phase_timings_ms": {"dns": 5, "tcp_445": 1495},
                    "server_probe": {"dns_status": "blocked", "tcp_445_status": "blocked"},
                    "path_probe": {"exists": False, "path_kind": "missing", "can_list": False},
                    "storage_status": "not_checked",
                    "storage_probe": {"status": "not_checked", "capacity_source": "not_checked"},
                    "capacity_source": "not_checked",
                    "capacity_path": "",
                    "capacity_error": "",
                    "last_successful_capacity": {"free_space_gb": 109.2, "evidence_only": True},
                    "message": "SourceMovies root does not exist or is not reachable from this Windows session.",
                    "safe_next_action": "Log back into Windows/server share, then refresh path health.",
                }
            ],
        }
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            service = DummyFacadeService(root)
            facade = MediaPipelineApplicationFacade(service, app_version="v5-test")
            resolved = _resolved(root)
            resolved.config_data = {"SourceMovies": r"\\LAYNE-SERVER\Video\Movies"}

            with patch("mediapipeline.core.diagnostics.facade.configured_path_health", return_value=health):
                payload = facade.read_diagnostics_state_summary(resolved)

        self.assertEqual(payload["path_health"]["schema_version"], "desktop_configured_path_health.v1")
        self.assertEqual(len(payload["path_health_issues"]), 1)
        issue = payload["path_health_issues"][0]
        self.assertEqual(issue["target"], "configured_path_health_source_movies")
        self.assertEqual(issue["kind"], "path_health")
        self.assertEqual(issue["status"], "error")
        self.assertEqual(issue["operator_status"], "blocked")
        self.assertEqual(issue["recovery_stage"], "configured_server_folder_health")
        self.assertIn("server/share", issue["operator_guidance"].casefold())
        self.assertIn("scan, copy, remux", issue["unsafe_if_ignored"])
        facts = "\n".join(issue["facts"])
        self.assertIn("SMB TCP 445: blocked", facts)
        self.assertIn("Health code: path_missing_or_unreachable", facts)
        self.assertIn("Probe attempts: 1", facts)
        self.assertIn("Phase timings: dns=5ms, tcp_445=1495ms", facts)
        self.assertIn("Capacity source: not_checked", facts)
        self.assertIn("Last successful capacity: 109.2 GB; evidence-only=yes", facts)
        self.assertEqual(payload["triage"][0]["target"], "configured_path_health_source_movies")

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
