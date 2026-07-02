from __future__ import annotations

from datetime import datetime, timedelta, timezone, UTC
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from mediapipeline.tools.paths import find_repo_root
import sys

sys.path.insert(0, str(find_repo_root(Path(__file__)) / "src"))

from mediapipeline.core.diagnostics.autonomy_health import (
    AUTONOMY_SCAN_LIMIT,
    autonomy_health_payload,
    load_autonomy_growth_history,
    record_autonomy_growth_snapshot,
)
from mediapipeline.core.processes.path_evidence import LAUNCH_PATH_HEALTH_TIMEOUT_SECONDS
from mediapipeline.core.storage.db import open_state_db
from mediapipeline.desktop.models import ResolvedPaths
from mediapipeline.tools.autonomy_health_gate import (
    AUTONOMY_HEALTH_GATE_PATH_HEALTH_TIMEOUT_SECONDS,
    build_health_from_payload,
)


def _resolved(root: Path) -> ResolvedPaths:
    state = root / "State"
    return ResolvedPaths(
        app_root=root,
        workspace_root=root,
        pipeline_path=root / "pipeline.ps1",
        config_path=root / "config.psd1",
        audit_script_path=root / "audit.ps1",
        rerun_script_path=root / "rerun.ps1",
        powershell_host="pwsh",
        local_base=root / "LocalBase",
        state_root=state,
        active_jobs_path=state / "ActiveJobs",
        failed_reports_path=state / "Failures" / "Reports",
        failed_markers_path=state / "Failures" / "Markers",
        pending_push_path=state / "PendingServerPush",
        completed_manifest_path=state / "Completed" / "completed_jobs.jsonl",
        queue_snapshot_path=state / "Progress" / "queue_snapshot.json",
        progress_file=state / "Progress" / "pipeline_progress.json",
        event_file=state / "Progress" / "pipeline_events.jsonl",
        log_file=root / "LocalBase" / "pipeline_debug.log",
        config_data={"NetworkRole": "standalone"},
    )


class AutonomyHealthPayloadTests(unittest.TestCase):
    def test_clean_state_returns_ready(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            resolved = _resolved(root)
            for path in (
                resolved.state_root,
                resolved.active_jobs_path,
                resolved.failed_reports_path,
                resolved.failed_markers_path,
                resolved.pending_push_path,
                resolved.completed_manifest_path.parent,
                resolved.queue_snapshot_path.parent,
                resolved.log_file.parent,
            ):
                assert path is not None
                path.mkdir(parents=True, exist_ok=True)
            resolved.completed_manifest_path.write_text("", encoding="utf-8")
            resolved.queue_snapshot_path.write_text(json.dumps({"runnable_count": 0}), encoding="utf-8")

            payload = autonomy_health_payload(
                resolved,
                pending_publish={"rows": [], "count": 0, "total_bytes": 0, "health_count": 0},
                path_health={"operator_status": "ready", "rows": []},
            )

        self.assertEqual(payload["schema_version"], "desktop_autonomy_health.v1")
        self.assertEqual(payload["overall_status"], "ready")
        self.assertTrue(payload["launch_gate"]["can_start_new_work"])
        self.assertEqual(payload["blocked_count"], 0)
        self.assertEqual(payload["external_alert"]["schema_version"], "desktop_autonomy_alert.v1")
        self.assertEqual(payload["external_alert"]["alert_level"], "none")
        self.assertFalse(payload["external_alert"]["operator_attention_required"])
        self.assertFalse(payload["external_alert"]["would_send_notifications"])
        self.assertFalse(payload["external_alert"]["would_write_files"])
        projection = payload["growth_projection"]
        self.assertEqual(projection["schema_version"], "desktop_autonomy_growth_projection.v1")
        self.assertEqual(projection["effect"], "none")
        self.assertTrue(projection["read_only"])
        self.assertEqual(projection["operator_status"], "ready")
        self.assertEqual(projection["confidence"], "current_evidence_only")
        self.assertFalse(projection["historical_samples_available"])
        self.assertFalse(projection["would_write_snapshots"])
        self.assertFalse(projection["would_delete_or_cleanup"])
        self.assertIsNone(projection["projected_7_day_growth_bytes"])
        self.assertIsNone(projection["projected_30_day_growth_bytes"])
        self.assertIsNone(projection["days_to_budget_exhaustion"])
        self.assertEqual(payload["runtime_reliability"]["schema_version"], "desktop_runtime_reliability_counters.v1")
        self.assertIn("runtime_health", payload["categories"])

    def test_runtime_reliability_counters_surface_long_run_health(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            resolved = _resolved(root)
            resolved.config_data = {
                "NetworkRole": "standalone",
                "DeferredPublish": True,
                "PendingPublishDeferredBlockThreshold": 1,
                "LocalWorkerHeartbeatGraceSeconds": 10,
                "CoordinatorHeartbeatTimeoutMins": 5,
                "PipelineDebugLogMaxBytes": 10,
                "StateDbCompletedJobsMaxRows": 250000,
            }
            resolved.pause_flag = resolved.state_root / "Pipeline" / "pipeline_pause.flag"
            assert resolved.progress_file is not None
            assert resolved.active_jobs_path is not None
            assert resolved.pending_push_path is not None
            now = datetime(2026, 6, 18, 12, 0, tzinfo=UTC)
            started = now - timedelta(minutes=10)
            pause_created = now - timedelta(hours=7)
            for path in (
                resolved.progress_file.parent,
                resolved.active_jobs_path,
                resolved.pending_push_path,
                resolved.pause_flag.parent,
                resolved.log_file.parent,
                resolved.state_root / "Workers" / "slot-1",
                resolved.state_root / "App" / "pending_done_reports",
                resolved.state_root / "App" / "pending_done_reports_review",
            ):
                path.mkdir(parents=True, exist_ok=True)
            resolved.pause_flag.write_text("pause", encoding="utf-8")
            resolved.progress_file.write_text(
                json.dumps(
                    {
                        "CurrentFile": "Movie.mkv",
                        "CurrentFilePath": str(root / "Movie.mkv"),
                        "CurrentStage": "encode",
                        "Status": "Encoding",
                        "CurrentItemStartedAt": started.isoformat(),
                        "RoundFailureCount": 2,
                        "UnexpectedQueueEntryFailures": 1,
                        "UnexpectedRoundFailures": 1,
                        "ConsecutiveUnexpectedRoundFailures": 12,
                        "ConsecutiveRoundFailureBlockLimit": 12,
                        "ConsecutiveRoundFailureProbeBackoffSeconds": 900,
                        "ContinuousRoundFailuresBlocked": True,
                        "LastUnexpectedRoundFailureAt": (now - timedelta(minutes=5)).isoformat(),
                        "PauseFlagReviewSeconds": 1800,
                        "PauseFlagBlockSeconds": 21600,
                        "ControlRequests": {
                            "Pause": {
                                "Requested": True,
                                "CreatedAt": pause_created.isoformat(),
                            }
                        },
                        "NativeNoProgressAbortCount": 1,
                        "ProgressPersistenceHealthy": False,
                        "ProgressWriteFailures": 3,
                        "HeartbeatFailureStartedAt": (now - timedelta(seconds=90)).isoformat(),
                    }
                ),
                encoding="utf-8",
            )
            (resolved.active_jobs_path / "bad.json").write_text("{not-json", encoding="utf-8")
            (resolved.pending_push_path / "movie.manifest.json").write_text("{}", encoding="utf-8")
            heartbeat = resolved.state_root / "Workers" / "slot-1" / "worker_heartbeat.json"
            heartbeat.write_text(
                json.dumps({"schema_version": "local_worker_heartbeat.v1", "updated_at": started.isoformat()}),
                encoding="utf-8",
            )
            os.utime(heartbeat, (started.timestamp(), started.timestamp()))
            app_state = resolved.state_root / "App"
            (app_state / "worker_state.json").write_text(
                json.dumps({"pending_done_report": {"job_id": "legacy-job"}}),
                encoding="utf-8",
            )
            (app_state / "pending_done_reports" / "queued.json").write_text("{}", encoding="utf-8")
            (app_state / "pending_done_reports_review" / "review.json").write_text("{}", encoding="utf-8")
            pending_done_mtime = (now - timedelta(hours=2)).timestamp()
            os.utime(app_state / "worker_state.json", (pending_done_mtime, pending_done_mtime))
            os.utime(app_state / "pending_done_reports" / "queued.json", (pending_done_mtime, pending_done_mtime))
            os.utime(app_state / "pending_done_reports_review" / "review.json", (pending_done_mtime, pending_done_mtime))
            (app_state / "coordinator_inflight.json").write_text(
                json.dumps(
                    {
                        "reclaimed_source_quarantine": [
                            {
                                "source_path": str(root / "Movie.mkv"),
                                "reclaimed_at": (now - timedelta(hours=1)).isoformat(),
                                "expires_at": (now + timedelta(hours=1)).isoformat(),
                            }
                        ],
                        "late_terminal_reports": [{"job_id": "late-1"}],
                        "failure_ledger": [{"job_id": "fail-1"}, {"job_id": "fail-2"}],
                    }
                ),
                encoding="utf-8",
            )
            resolved.log_file.write_text("0123456789ABCDEF", encoding="utf-8")
            db = open_state_db(resolved.state_root)
            db.record_completed_job({"job_id": "job-1", "output_path": "out.mkv", "sidecar_path": "out.pipeline.json"})
            marker_path = resolved.state_root / "state_db_maintenance.json"
            marker_path.write_text(
                json.dumps(
                    {
                        "schema_version": "state_db_maintenance_marker.v1",
                        "checked_at": now.isoformat(),
                        "ok": False,
                        "error": "database is locked",
                    }
                ),
                encoding="utf-8",
            )

            payload = autonomy_health_payload(
                resolved,
                pending_publish={"rows": [{"row_key": "movie"}], "count": 1, "total_bytes": 123, "health_count": 1},
                path_health={"operator_status": "ready", "rows": []},
                now=now,
            )

        counters = payload["runtime_reliability"]
        self.assertEqual(counters["current_file"]["age_seconds"], 600)
        self.assertEqual(counters["round_failures"]["round_failure_count"], 2)
        self.assertEqual(counters["round_failures"]["unexpected_queue_entry_failures"], 1)
        self.assertEqual(counters["round_failures"]["unexpected_round_failures"], 1)
        self.assertTrue(counters["continuous_round_state"]["blocked"])
        self.assertEqual(counters["continuous_round_state"]["consecutive_unexpected_round_failures"], 12)
        self.assertTrue(counters["control_flags"]["pause_flag_present"])
        self.assertGreaterEqual(counters["control_flags"]["pause_age_seconds"], 21600)
        self.assertEqual(counters["native_processes"]["native_no_progress_abort_count"], 1)
        self.assertEqual(counters["pending_publish"]["backlog_count"], 1)
        self.assertTrue(counters["pending_publish_backpressure"]["blocked"])
        self.assertEqual(counters["pending_publish_backpressure"]["block_reason"], "deferred_backlog_threshold")
        self.assertEqual(counters["worker_pending_reports"]["pending_report_count"], 3)
        self.assertGreaterEqual(counters["worker_pending_reports"]["oldest_pending_report_age_seconds"], 7200)
        self.assertEqual(counters["worker_heartbeat_failure"]["age_seconds"], 90)
        self.assertEqual(counters["worker_heartbeat_failure"]["abort_threshold_seconds"], 240)
        self.assertFalse(counters["worker_heartbeat_failure"]["abort_due"])
        self.assertEqual(counters["active_jobs"]["total_count"], 1)
        self.assertEqual(counters["active_jobs"]["blocking_count"], 0)
        self.assertEqual(counters["active_jobs"]["warning_count"], 1)
        self.assertEqual(counters["active_jobs"]["ambiguous_count"], 1)
        self.assertFalse(counters["active_jobs"]["ambiguous_read_first"])
        self.assertEqual(counters["worker_slots"]["active_child_count"], 1)
        self.assertEqual(counters["worker_slots"]["stale_heartbeat_count"], 1)
        self.assertGreater(counters["sqlite_mirror"]["db_size_bytes"], 0)
        self.assertEqual(counters["sqlite_mirror"]["completed_jobs_count"], 1)
        self.assertEqual(counters["sqlite_mirror"]["completed_jobs_max_rows"], 250000)
        self.assertEqual(counters["coordinator_state"]["reclaimed_source_quarantine_count"], 1)
        self.assertEqual(counters["coordinator_state"]["late_terminal_report_count"], 1)
        self.assertEqual(counters["coordinator_state"]["failure_ledger_count"], 2)
        self.assertEqual(counters["coordinator_state"]["failure_ledger_max_entries"], 5000)
        self.assertEqual(counters["debug_log"]["rotation_state"], "rotation_due_or_pending")
        self.assertEqual(counters["debug_log"]["max_bytes"], 10)
        self.assertEqual(counters["state_db"]["last_maintenance"]["error"], "database is locked")
        self.assertFalse(counters["progress_persistence"]["healthy"])
        self.assertEqual(counters["progress_persistence"]["write_failures"], 3)
        runtime_category = payload["categories"]["runtime_health"]
        self.assertEqual(runtime_category["status"], "blocked")
        self.assertEqual(runtime_category["metrics"]["pending_publish_backlog_count"], 1)
        self.assertEqual(runtime_category["metrics"]["coordinator_reclaimed_source_quarantine_count"], 1)
        self.assertEqual(runtime_category["metrics"]["coordinator_failure_ledger_count"], 2)
        self.assertEqual(runtime_category["metrics"]["debug_log_rotation_state"], "rotation_due_or_pending")
        self.assertEqual(runtime_category["metrics"]["sqlite_completed_jobs_count"], 1)
        blocker_codes = {item["code"] for item in payload["blockers"]}
        review_codes = {item["code"] for item in payload["review_items"]}
        self.assertIn("autonomy_round_failures_blocked", blocker_codes)
        self.assertIn("autonomy_pause_flag_stale", blocker_codes)
        self.assertIn("autonomy_pending_backlog_blocked", blocker_codes)
        self.assertIn("autonomy_worker_slot_stale", blocker_codes)
        self.assertIn("autonomy_progress_persistence_unhealthy", blocker_codes)
        self.assertIn("autonomy_state_db_maintenance_overdue", review_codes)

    def test_retry_exhausted_pending_publish_blocks(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            resolved = _resolved(root)
            assert resolved.pending_push_path is not None
            resolved.pending_push_path.mkdir(parents=True)
            manifest = resolved.pending_push_path / "movie.manifest.json"
            parked_at = (datetime.now(UTC) - timedelta(days=4)).isoformat()
            manifest.write_text(
                json.dumps(
                    {
                        "schema_version": "pending_push_manifest.v1",
                        "parked_at": parked_at,
                        "retry_count": 3,
                        "local_file": str(resolved.pending_push_path / "movie.mkv"),
                        "server_out": str(root / "Out" / "movie.mkv"),
                        "manifest_state": "parked",
                    }
                ),
                encoding="utf-8",
            )

            payload = autonomy_health_payload(
                resolved,
                pending_publish={
                    "rows": [
                        {
                            "manifest_path": str(manifest),
                            "parked_at": parked_at,
                            "output_size": 10,
                            "error": "",
                        }
                    ],
                    "count": 1,
                    "total_bytes": 10,
                    "health_count": 0,
                },
                path_health={"operator_status": "ready", "rows": []},
            )

        self.assertEqual(payload["overall_status"], "blocked")
        self.assertFalse(payload["launch_gate"]["can_start_new_work"])
        codes = {item["code"] for item in payload["blockers"]}
        self.assertIn("autonomy_pending_retry_exhausted", codes)
        self.assertIn("autonomy_pending_oldest_blocked", codes)
        retry_blocker = next(item for item in payload["blockers"] if item["code"] == "autonomy_pending_retry_exhausted")
        self.assertEqual(retry_blocker["recovery_action"]["kind"], "pending_publish_recovery_plan")
        self.assertEqual(retry_blocker["recovery_action"]["route"], "/api/pending-publish/recovery-plan")
        alert = payload["external_alert"]
        self.assertEqual(alert["alert_level"], "critical")
        self.assertTrue(alert["operator_attention_required"])
        self.assertIn("autonomy_pending_retry_exhausted", alert["blocker_codes"])
        self.assertNotIn(str(root), alert["dedupe_key"])
        self.assertEqual(alert["recommended_poll_interval_seconds"], 300)

    def test_untrusted_pending_manifest_blocker_has_specific_recovery_guidance(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            resolved = _resolved(root)
            assert resolved.pending_push_path is not None
            resolved.pending_push_path.mkdir(parents=True)
            manifest = resolved.pending_push_path / "movie.manifest.json"
            manifest.write_text(
                json.dumps(
                    {
                        "schema_version": "pending_push_manifest.v1",
                        "pipeline_version": "",
                        "local_file": str(resolved.pending_push_path / "movie.mkv"),
                        "server_out": str(root / "Out" / "movie.mkv"),
                    }
                ),
                encoding="utf-8",
            )
            row_error = (
                "Current pending manifest contract invalid: "
                "pipeline_version is required and cannot be blank."
            )

            payload = autonomy_health_payload(
                resolved,
                pending_publish={
                    "rows": [
                        {
                            "row_key": "pending-row-1",
                            "manifest_path": str(manifest),
                            "state": "invalid_contract",
                            "diagnostic_status": "invalid_manifest",
                            "local_file": str(resolved.pending_push_path / "movie.mkv"),
                            "server_out": str(root / "Out" / "movie.mkv"),
                            "error": row_error,
                        }
                    ],
                    "count": 1,
                    "total_bytes": 10,
                    "health_count": 1,
                },
                path_health={"operator_status": "ready", "rows": []},
            )

        self.assertEqual(payload["overall_status"], "blocked")
        blocker = next(item for item in payload["blockers"] if item["code"] == "autonomy_pending_manifest_untrusted")
        self.assertIn("Pending Publish manifest is not trusted", blocker["message"])
        self.assertIn("pipeline_version is required and cannot be blank", blocker["message"])
        self.assertIn(f"manifest={manifest}", blocker["message"])
        self.assertIn("row_key=pending-row-1", blocker["message"])
        self.assertEqual(blocker["row_key"], "pending-row-1")
        self.assertEqual(blocker["diagnostic_status"], "invalid_manifest")
        self.assertIn("Repair Manifest dry-run", blocker["next_action"])
        self.assertIn("STATE_FILE_SCHEMA_REFERENCE.md", blocker["next_action"])
        self.assertEqual(blocker["recovery_action"]["kind"], "pending_publish_recovery_plan")
        self.assertEqual(blocker["recovery_action"]["route"], "/api/pending-publish/recovery-plan")
        self.assertEqual(blocker["recovery_action"]["request"], {"scope": "selected", "row_key": "pending-row-1"})
        self.assertIn("Pending Publish manifest is not trusted", payload["launch_gate"]["blocked_reason"])

    def test_old_pending_publish_review_exports_warning_alert_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            resolved = _resolved(root)
            assert resolved.pending_push_path is not None
            resolved.pending_push_path.mkdir(parents=True)
            parked_at = (datetime.now(UTC) - timedelta(hours=25)).isoformat()
            manifest = resolved.pending_push_path / "movie.manifest.json"
            manifest.write_text(
                json.dumps(
                    {
                        "schema_version": "pending_push_manifest.v1",
                        "parked_at": parked_at,
                        "retry_count": 0,
                        "local_file": str(resolved.pending_push_path / "movie.mkv"),
                        "server_out": str(root / "Out" / "movie.mkv"),
                        "manifest_state": "parked",
                    }
                ),
                encoding="utf-8",
            )

            payload = autonomy_health_payload(
                resolved,
                pending_publish={
                    "rows": [
                        {
                            "manifest_path": str(manifest),
                            "parked_at": parked_at,
                            "output_size": 10,
                            "error": "",
                        }
                    ],
                    "count": 1,
                    "total_bytes": 10,
                    "health_count": 0,
                },
                path_health={"operator_status": "ready", "rows": []},
            )

        alert = payload["external_alert"]
        self.assertEqual(payload["overall_status"], "review")
        self.assertEqual(alert["alert_level"], "warning")
        self.assertTrue(alert["operator_attention_required"])
        self.assertEqual(alert["blocker_codes"], [])
        self.assertIn("autonomy_pending_oldest_review", alert["review_codes"])
        self.assertEqual(alert["recommended_poll_interval_seconds"], 900)

    def test_old_pending_publish_block_exports_drain_recovery_action(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            resolved = _resolved(root)
            assert resolved.pending_push_path is not None
            resolved.pending_push_path.mkdir(parents=True)
            parked_at = (datetime.now(UTC) - timedelta(days=4)).isoformat()
            manifest = resolved.pending_push_path / "movie.manifest.json"
            manifest.write_text(
                json.dumps(
                    {
                        "schema_version": "pending_push_manifest.v1",
                        "parked_at": parked_at,
                        "retry_count": 0,
                        "local_file": str(resolved.pending_push_path / "movie.mkv"),
                        "server_out": str(root / "Out" / "movie.mkv"),
                        "manifest_state": "parked",
                    }
                ),
                encoding="utf-8",
            )

            payload = autonomy_health_payload(
                resolved,
                pending_publish={
                    "rows": [
                        {
                            "manifest_path": str(manifest),
                            "parked_at": parked_at,
                            "output_size": 10,
                            "error": "",
                        }
                    ],
                    "count": 1,
                    "total_bytes": 10,
                    "health_count": 0,
                },
                path_health={"operator_status": "ready", "rows": []},
            )

        action = payload["launch_gate"]["recovery_action"]
        self.assertEqual(payload["overall_status"], "blocked")
        self.assertEqual(action["kind"], "drain_pending_pushes")
        self.assertEqual(action["route"], "/api/pipeline/start")
        self.assertEqual(action["request"]["mode"], "drain_pending_pushes")
        self.assertTrue(action["requires_confirmation"])

    def test_stale_active_job_is_passive_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            resolved = _resolved(root)
            assert resolved.active_jobs_path is not None
            resolved.active_jobs_path.mkdir(parents=True)
            old = (datetime.now(UTC) - timedelta(hours=2)).isoformat()
            (resolved.active_jobs_path / "pipeline.json").write_text(
                json.dumps(
                    {
                        "schema_version": "active_job.v1",
                        "job_kind": "pipeline",
                        "mode": "continuous",
                        "status": "active",
                        "pid": 43210,
                        "launched_at": old,
                        "last_update": old,
                    }
                ),
                encoding="utf-8",
            )

            payload = autonomy_health_payload(
                resolved,
                pending_publish={"rows": [], "count": 0, "total_bytes": 0, "health_count": 0},
                path_health={"operator_status": "ready", "rows": []},
            )

        workers = payload["categories"]["workers"]
        record = workers["metrics"]["active_liveness_watchdog"]["records"][0]
        self.assertEqual(payload["overall_status"], "review")
        self.assertTrue(payload["launch_gate"]["can_start_new_work"])
        self.assertEqual(workers["status"], "review")
        self.assertEqual(workers["metrics"]["active_count"], 1)
        self.assertEqual(workers["metrics"]["stale_count"], 1)
        self.assertEqual(workers["metrics"]["active_read_first_count"], 0)
        self.assertFalse(workers["metrics"]["ambiguous_read_first"])
        self.assertEqual(record["status"], "passive_stale")
        self.assertTrue(record["blocking_disabled"])
        self.assertEqual(workers["metrics"]["active_liveness_watchdog"]["record_total_count"], 1)
        self.assertFalse(workers["metrics"]["active_liveness_watchdog"]["records_truncated"])
        self.assertIn("autonomy_active_jobs_passive_stale", {item["code"] for item in payload["review_items"]})

    def test_active_job_records_are_passive_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            resolved = _resolved(root)
            assert resolved.active_jobs_path is not None
            resolved.active_jobs_path.mkdir(parents=True)
            launched = datetime.now(UTC).isoformat()
            (resolved.active_jobs_path / "pipeline.json").write_text(
                json.dumps(
                    {
                        "schema_version": "active_job.v1",
                        "job_kind": "pipeline",
                        "mode": "once",
                        "status": "active",
                        "pid": 43210,
                        "launched_at": launched,
                        "last_update": launched,
                    }
                ),
                encoding="utf-8",
            )

            payload = autonomy_health_payload(
                resolved,
                pending_publish={"rows": [], "count": 0, "total_bytes": 0, "health_count": 0},
                path_health={"operator_status": "ready", "rows": []},
            )

        workers = payload["categories"]["workers"]
        active_jobs = payload["runtime_reliability"]["active_jobs"]
        record = workers["metrics"]["active_liveness_watchdog"]["records"][0]
        self.assertEqual(payload["overall_status"], "ready")
        self.assertEqual(workers["metrics"]["active_count"], 1)
        self.assertEqual(workers["metrics"]["active_jobs_ignored_count"], 0)
        self.assertEqual(active_jobs["total_count"], 1)
        self.assertEqual(active_jobs["ignored_count"], 0)
        self.assertFalse(active_jobs["ambiguous_read_first"])
        self.assertEqual(record["status"], "passive_active")
        self.assertTrue(record["blocking_disabled"])
        self.assertEqual(workers["metrics"]["active_liveness_watchdog"]["record_total_count"], 1)
        self.assertFalse(workers["metrics"]["active_liveness_watchdog"]["records_truncated"])

    def test_malformed_active_job_record_is_review_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            resolved = _resolved(root)
            assert resolved.active_jobs_path is not None
            resolved.active_jobs_path.mkdir(parents=True)
            (resolved.active_jobs_path / "broken.json").write_text("{not-json", encoding="utf-8")

            payload = autonomy_health_payload(
                resolved,
                pending_publish={"rows": [], "count": 0, "total_bytes": 0, "health_count": 0},
                path_health={"operator_status": "ready", "rows": []},
            )

        workers = payload["categories"]["workers"]
        watchdog = workers["metrics"]["active_liveness_watchdog"]
        self.assertEqual(payload["overall_status"], "review")
        self.assertTrue(payload["launch_gate"]["can_start_new_work"])
        self.assertEqual(workers["status"], "review")
        self.assertEqual(workers["metrics"]["malformed_count"], 1)
        self.assertEqual(watchdog["record_total_count"], 1)
        self.assertEqual(watchdog["records"][0]["status"], "passive_malformed")
        self.assertIn("autonomy_active_jobs_malformed", {item["code"] for item in payload["review_items"]})

    def test_multiple_active_job_records_do_not_block(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            resolved = _resolved(root)
            assert resolved.active_jobs_path is not None
            resolved.active_jobs_path.mkdir(parents=True)
            launched = datetime.now(UTC).isoformat()
            for file_name, pid in (("current.json", 43210), ("previous.json", 43211)):
                (resolved.active_jobs_path / file_name).write_text(
                    json.dumps(
                        {
                            "schema_version": "active_job.v1",
                            "job_kind": "pipeline",
                            "mode": "once",
                            "status": "active",
                            "pid": pid,
                            "launched_at": launched,
                            "last_update": launched,
                        }
                    ),
                    encoding="utf-8",
                )

            payload = autonomy_health_payload(
                resolved,
                pending_publish={"rows": [], "count": 0, "total_bytes": 0, "health_count": 0},
                path_health={"operator_status": "ready", "rows": []},
            )

        workers = payload["categories"]["workers"]
        active_jobs = payload["runtime_reliability"]["active_jobs"]
        self.assertEqual(payload["overall_status"], "ready")
        self.assertEqual(workers["metrics"]["active_count"], 2)
        self.assertEqual(workers["metrics"]["active_jobs_ignored_count"], 0)
        self.assertEqual(active_jobs["total_count"], 2)
        self.assertEqual(active_jobs["ignored_count"], 0)
        self.assertFalse(active_jobs["ambiguous_read_first"])
        self.assertEqual(workers["metrics"]["active_liveness_watchdog"]["record_count"], 2)
        self.assertEqual(workers["metrics"]["active_liveness_watchdog"]["record_total_count"], 2)
        self.assertFalse(workers["metrics"]["active_liveness_watchdog"]["records_truncated"])

    def test_fresh_progress_evidence_keeps_active_job_passive(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            resolved = _resolved(root)
            assert resolved.active_jobs_path is not None
            assert resolved.progress_file is not None
            resolved.active_jobs_path.mkdir(parents=True)
            resolved.progress_file.parent.mkdir(parents=True)
            now = datetime(2026, 6, 18, 12, 0, tzinfo=UTC)
            old = (now - timedelta(hours=2)).isoformat()
            fresh = (now - timedelta(minutes=5)).isoformat()
            (resolved.active_jobs_path / "pipeline.json").write_text(
                json.dumps(
                    {
                        "schema_version": "active_job.v1",
                        "job_kind": "pipeline",
                        "mode": "continuous",
                        "status": "active",
                        "pid": 43210,
                        "launched_at": old,
                        "last_update": old,
                    }
                ),
                encoding="utf-8",
            )
            resolved.progress_file.write_text(
                json.dumps({"Status": "Processing", "LastUpdate": fresh}),
                encoding="utf-8",
            )

            payload = autonomy_health_payload(
                resolved,
                pending_publish={"rows": [], "count": 0, "total_bytes": 0, "health_count": 0},
                path_health={"operator_status": "ready", "rows": []},
                now=now,
            )

        workers = payload["categories"]["workers"]
        self.assertEqual(payload["overall_status"], "ready")
        self.assertTrue(payload["launch_gate"]["can_start_new_work"])
        self.assertFalse(workers["metrics"]["ambiguous_read_first"])
        self.assertEqual(workers["metrics"]["active_liveness_watchdog"]["schema_version"], "desktop_active_liveness_watchdog.v1")
        self.assertEqual(workers["metrics"]["active_liveness_watchdog"]["records"][0]["latest_evidence_source"], "progress_file")
        self.assertEqual(workers["metrics"]["active_liveness_watchdog"]["records"][0]["status"], "passive_active")
        self.assertFalse(workers["metrics"]["active_liveness_watchdog"]["would_kill_active_processes"])

    def test_configured_native_timeout_is_passive_active_job_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            resolved = _resolved(root)
            resolved.config_data = {"FFmpegRemuxTimeoutSeconds": 300}
            assert resolved.active_jobs_path is not None
            resolved.active_jobs_path.mkdir(parents=True)
            now = datetime(2026, 6, 18, 12, 0, tzinfo=UTC)
            stale = (now - timedelta(minutes=25)).isoformat()
            (resolved.active_jobs_path / "remux.json").write_text(
                json.dumps(
                    {
                        "schema_version": "active_job.v1",
                        "job_kind": "pipeline",
                        "mode": "remux",
                        "status": "active",
                        "pid": 43210,
                        "launched_at": stale,
                        "last_update": stale,
                    }
                ),
                encoding="utf-8",
            )

            payload = autonomy_health_payload(
                resolved,
                pending_publish={"rows": [], "count": 0, "total_bytes": 0, "health_count": 0},
                path_health={"operator_status": "ready", "rows": []},
                now=now,
            )

        workers = payload["categories"]["workers"]
        self.assertEqual(payload["overall_status"], "review")
        self.assertTrue(payload["launch_gate"]["can_start_new_work"])
        self.assertEqual(workers["status"], "review")
        self.assertEqual(workers["metrics"]["active_liveness_watchdog"]["records"][0]["native_timeout_seconds"], 300)
        self.assertEqual(workers["metrics"]["active_liveness_watchdog"]["records"][0]["block_after_seconds"], 1200)
        self.assertEqual(workers["metrics"]["active_liveness_watchdog"]["records"][0]["status"], "passive_stale")

    def test_missing_native_timeout_is_passive_active_job_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            resolved = _resolved(root)
            assert resolved.active_jobs_path is not None
            resolved.active_jobs_path.mkdir(parents=True)
            now = datetime(2026, 6, 18, 12, 0, tzinfo=UTC)
            stale = (now - timedelta(minutes=31)).isoformat()
            (resolved.active_jobs_path / "unknown.json").write_text(
                json.dumps(
                    {
                        "schema_version": "active_job.v1",
                        "job_kind": "pipeline",
                        "mode": "custom",
                        "status": "active",
                        "pid": 43210,
                        "launched_at": stale,
                        "last_update": stale,
                    }
                ),
                encoding="utf-8",
            )

            payload = autonomy_health_payload(
                resolved,
                pending_publish={"rows": [], "count": 0, "total_bytes": 0, "health_count": 0},
                path_health={"operator_status": "ready", "rows": []},
                now=now,
            )

        workers = payload["categories"]["workers"]
        self.assertEqual(payload["overall_status"], "review")
        self.assertTrue(payload["launch_gate"]["can_start_new_work"])
        self.assertEqual(workers["status"], "review")
        self.assertEqual(workers["metrics"]["active_liveness_watchdog"]["records"][0]["native_timeout_source"], "")
        self.assertEqual(workers["metrics"]["active_liveness_watchdog"]["records"][0]["block_after_seconds"], 1800)
        self.assertEqual(workers["metrics"]["active_liveness_watchdog"]["records"][0]["status"], "passive_stale")

    def test_malformed_progress_keeps_stale_active_job_passive(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            resolved = _resolved(root)
            assert resolved.active_jobs_path is not None
            assert resolved.progress_file is not None
            resolved.active_jobs_path.mkdir(parents=True)
            resolved.progress_file.parent.mkdir(parents=True)
            now = datetime(2026, 6, 18, 12, 0, tzinfo=UTC)
            stale = (now - timedelta(minutes=31)).isoformat()
            (resolved.active_jobs_path / "pipeline.json").write_text(
                json.dumps(
                    {
                        "schema_version": "active_job.v1",
                        "job_kind": "pipeline",
                        "mode": "custom",
                        "status": "active",
                        "pid": 43210,
                        "launched_at": stale,
                        "last_update": stale,
                    }
                ),
                encoding="utf-8",
            )
            resolved.progress_file.write_text("{not-json", encoding="utf-8")

            payload = autonomy_health_payload(
                resolved,
                pending_publish={"rows": [], "count": 0, "total_bytes": 0, "health_count": 0},
                path_health={"operator_status": "ready", "rows": []},
                now=now,
            )

        workers = payload["categories"]["workers"]
        record = workers["metrics"]["active_liveness_watchdog"]["records"][0]
        self.assertEqual(payload["overall_status"], "review")
        self.assertTrue(payload["launch_gate"]["can_start_new_work"])
        self.assertEqual(workers["status"], "review")
        self.assertEqual(record["latest_evidence_source"], "active_job")
        self.assertEqual(record["status"], "passive_stale")

    def test_low_configured_storage_free_space_blocks(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            resolved = _resolved(root)
            payload = autonomy_health_payload(
                resolved,
                pending_publish={"rows": [], "count": 0, "total_bytes": 0, "health_count": 0},
                path_health={
                    "operator_status": "ready",
                    "rows": [
                        {
                            "key": "local_base",
                            "label": "LocalBase scratch/state root",
                            "role": "scratch",
                            "path": str(root / "LocalBase"),
                            "status": "ready",
                            "storage_status": "low",
                            "free_space_gb": 50,
                            "reserve_gb": 100,
                        }
                    ],
                },
            )

        self.assertEqual(payload["overall_status"], "blocked")
        self.assertIn("autonomy_storage_free_space_low", {item["code"] for item in payload["blockers"]})
        self.assertNotIn("autonomy_configured_path_blocked", {item["code"] for item in payload["blockers"]})

    def test_disk_state_reports_autonomy_scan_truncation_as_lower_bound(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            resolved = _resolved(root)
            scan_root = resolved.state_root / "ManyFiles"
            scan_root.mkdir(parents=True)
            for index in range(AUTONOMY_SCAN_LIMIT + 1):
                (scan_root / f"state-{index}.json").write_text("x", encoding="utf-8")

            payload = autonomy_health_payload(
                resolved,
                pending_publish={"rows": [], "count": 0, "total_bytes": 0, "health_count": 0},
                path_health={"operator_status": "ready", "rows": []},
            )

        disk_state = payload["categories"]["disk_state"]
        metrics = disk_state["metrics"]
        self.assertEqual(payload["overall_status"], "review")
        self.assertTrue(metrics["state_root_scan_truncated"])
        self.assertTrue(metrics["state_root_size_lower_bound"])
        self.assertEqual(metrics["state_root_scanned_file_count"], AUTONOMY_SCAN_LIMIT)
        self.assertIn("autonomy_scan_truncated", {item["code"] for item in payload["review_items"]})
        self.assertTrue(payload["growth_projection"]["current_budget"]["state_root_scan_truncated"])

    def test_blocked_path_health_does_not_report_false_low_space(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            resolved = _resolved(root)
            payload = autonomy_health_payload(
                resolved,
                pending_publish={"rows": [], "count": 0, "total_bytes": 0, "health_count": 0},
                path_health={
                    "operator_status": "blocked",
                    "operator_summary": "1 configured root did not respond.",
                    "rows": [
                        {
                            "key": "outsource",
                            "label": "Outsource output root",
                            "role": "output",
                            "path": r"\\LAYNE-SERVER\Users\Layne\Videos\outsource\Movies",
                            "status": "blocked",
                            "operator_status": "blocked",
                            "storage_status": "blocked",
                            "free_space_gb": None,
                            "reserve_gb": 50,
                            "message": "Outsource output root did not respond within the bounded path health timeout.",
                            "safe_next_action": "Reconnect the server share before starting the pipeline.",
                        }
                    ],
                },
            )

        blocker_codes = {item["code"] for item in payload["blockers"]}
        self.assertEqual(payload["overall_status"], "blocked")
        self.assertIn("autonomy_configured_path_blocked", blocker_codes)
        self.assertNotIn("autonomy_storage_free_space_low", blocker_codes)
        self.assertIn("did not respond", payload["launch_gate"]["blocked_reason"])

    def test_cli_gate_uses_network_tolerant_path_health_timeout(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            paths_payload = {
                "app_root": str(root),
                "workspace_root": str(root),
                "pipeline_path": str(root / "pipeline.ps1"),
                "config_path": str(root / "config.psd1"),
                "local_base": str(root / "LocalBase"),
                "state_root": str(root / "State"),
                "pending_push_path": str(root / "State" / "PendingServerPush"),
                "source_movies": r"\\LAYNE-SERVER\Video\Movies",
                "source_tv": str(root / "TV"),
                "config_data": {
                    "SourceMovies": r"\\LAYNE-SERVER\Video\Movies",
                    "SourceTV": str(root / "TV"),
                    "Outsource": r"\\LAYNE-SERVER\Video\Outsource",
                    "LocalBase": str(root / "LocalBase"),
                },
            }
            path_health_payload = {
                "schema_version": "desktop_configured_path_health.v1",
                "operator_status": "ready",
                "rows": [],
            }

            with (
                patch(
                    "mediapipeline.tools.autonomy_health_gate.configured_path_health",
                    return_value=path_health_payload,
                ) as path_health,
                patch(
                    "mediapipeline.tools.autonomy_health_gate._PendingScanner.scan_pending_publish",
                    return_value={"rows": [], "count": 0, "total_bytes": 0, "health_count": 0},
                ),
            ):
                payload = build_health_from_payload(paths_payload)

        self.assertEqual(payload["overall_status"], "ready")
        path_health.assert_called_once()
        self.assertEqual(AUTONOMY_HEALTH_GATE_PATH_HEALTH_TIMEOUT_SECONDS, LAUNCH_PATH_HEALTH_TIMEOUT_SECONDS)
        self.assertEqual(
            path_health.call_args.kwargs["timeout_seconds"],
            AUTONOMY_HEALTH_GATE_PATH_HEALTH_TIMEOUT_SECONDS,
        )

    def test_oversized_state_journal_blocks(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            resolved = _resolved(root)
            assert resolved.event_file is not None
            resolved.event_file.parent.mkdir(parents=True)
            resolved.event_file.write_text("1234567890", encoding="utf-8")

            with patch("mediapipeline.core.diagnostics.autonomy_health.STATE_FILE_BLOCK_BYTES", 5):
                payload = autonomy_health_payload(
                    resolved,
                    pending_publish={"rows": [], "count": 0, "total_bytes": 0, "health_count": 0},
                    path_health={"operator_status": "ready", "rows": []},
                )

        self.assertEqual(payload["overall_status"], "blocked")
        journal_blocker = next(item for item in payload["blockers"] if item["code"] == "autonomy_journal_file_blocked_size")
        self.assertEqual(journal_blocker["recovery_action"]["kind"], "archive_state_journals")
        self.assertEqual(journal_blocker["recovery_action"]["route"], "/api/maintenance/archive-state-journals")
        self.assertFalse(journal_blocker["recovery_action"]["mutates_media"])
        self.assertEqual(payload["launch_gate"]["recovery_action"]["kind"], "archive_state_journals")
        self.assertEqual(payload["growth_projection"]["operator_status"], "blocked")
        self.assertIn("autonomy_journal_file_blocked_size", payload["growth_projection"]["current_blocker_codes"])

    def test_growth_projection_summarizes_pending_journals_and_storage_budget(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            resolved = _resolved(root)
            assert resolved.event_file is not None
            assert resolved.queue_snapshot_path is not None
            resolved.event_file.parent.mkdir(parents=True)
            resolved.event_file.write_text("event-data", encoding="utf-8")
            resolved.queue_snapshot_path.write_text(json.dumps({"runnable_count": 0}), encoding="utf-8")

            payload = autonomy_health_payload(
                resolved,
                pending_publish={"rows": [], "count": 0, "total_bytes": 42, "health_count": 0},
                path_health={
                    "operator_status": "ready",
                    "rows": [
                        {
                            "key": "local_base",
                            "label": "LocalBase scratch/state root",
                            "role": "scratch",
                            "path": str(root / "LocalBase"),
                            "status": "ready",
                            "storage_status": "ready",
                            "free_space_gb": 150,
                            "reserve_gb": 100,
                        },
                        {
                            "key": "output",
                            "label": "Final output",
                            "role": "output",
                            "path": str(root / "Out"),
                            "status": "ready",
                            "storage_status": "ready",
                            "free_space_gb": 250,
                        },
                    ],
                },
            )

        projection = payload["growth_projection"]
        current_budget = projection["current_budget"]
        self.assertEqual(current_budget["pending_publish_bytes"], 42)
        self.assertEqual(current_budget["storage_row_count"], 2)
        self.assertGreaterEqual(current_budget["journal_file_bytes"], len("event-data"))
        self.assertGreaterEqual(current_budget["observed_bytes"], current_budget["pending_publish_bytes"])
        self.assertEqual(
            current_budget["observed_bytes"],
            current_budget["observed_filesystem_bytes_unique"] + current_budget["pending_publish_bytes"],
        )
        self.assertGreaterEqual(
            current_budget["observed_bytes_legacy_may_overlap"],
            current_budget["observed_filesystem_bytes_unique"],
        )
        self.assertFalse(current_budget["current_only_may_overlap_scanned_roots"])
        self.assertEqual(current_budget["minimum_free_bytes"], 150 * 1024**3)
        self.assertIn("process_count", current_budget)
        self.assertIn("pending_publish_oldest_age_seconds", current_budget)
        self.assertIn("pending_done_oldest_age_seconds", current_budget)
        self.assertIn("state_db_wal_size_bytes", current_budget)
        self.assertIn("log_size_bytes", current_budget)
        self.assertIn("failure_ledger_size", current_budget)
        self.assertIn("reclaimed_source_quarantine_count", current_budget)
        self.assertEqual(projection["storage_roots"][0]["role"], "scratch")
        self.assertEqual(projection["storage_roots"][0]["threshold_bytes"], 100 * 1024**3)
        self.assertEqual(projection["storage_roots"][1]["threshold_bytes"], 100 * 1024**3)

    def test_growth_projection_uses_snapshot_history_for_rate_estimate(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            resolved = _resolved(root)
            now = datetime(2026, 6, 18, 12, 0, tzinfo=UTC)
            mib = 1024**2

            payload = autonomy_health_payload(
                resolved,
                pending_publish={"rows": [], "count": 0, "total_bytes": 300 * mib, "health_count": 0},
                path_health={
                    "operator_status": "ready",
                    "rows": [
                        {
                            "key": "local_base",
                            "label": "LocalBase scratch/state root",
                            "role": "scratch",
                            "path": str(root / "LocalBase"),
                            "status": "ready",
                            "storage_status": "ready",
                            "free_space_gb": 10,
                        }
                    ],
                },
                now=now,
                growth_history={
                    "snapshots": [
                        {
                            "schema_version": "desktop_autonomy_growth_snapshot.v1",
                            "recorded_at_utc": (now - timedelta(days=2)).isoformat().replace("+00:00", "Z"),
                            "current_budget": {
                                "observed_bytes": 100 * mib,
                                "minimum_free_bytes": 10 * 1024**3,
                            },
                        }
                    ]
                },
            )

        projection = payload["growth_projection"]
        self.assertTrue(projection["historical_samples_available"])
        self.assertEqual(projection["confidence"], "historical_projection")
        self.assertEqual(projection["history_sample_count"], 1)
        self.assertEqual(projection["trend_window_seconds"], 2 * 24 * 60 * 60)
        self.assertEqual(projection["growth_rate_bytes_per_day"], 100 * mib)
        self.assertEqual(projection["projected_7_day_growth_bytes"], 700 * mib)
        self.assertEqual(projection["projected_30_day_growth_bytes"], 3000 * mib)
        self.assertGreater(projection["days_to_budget_exhaustion"], 90)

    def test_record_growth_snapshot_bounds_history_under_state_root(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            resolved = _resolved(root)
            now = datetime(2026, 6, 18, 12, 0, tzinfo=UTC)
            payload = autonomy_health_payload(
                resolved,
                pending_publish={"rows": [], "count": 0, "total_bytes": 10, "health_count": 0},
                path_health={"operator_status": "ready", "rows": []},
                now=now,
            )

            first = record_autonomy_growth_snapshot(
                resolved,
                payload,
                now=now - timedelta(hours=2),
                max_snapshots=2,
            )
            second = record_autonomy_growth_snapshot(
                resolved,
                payload,
                now=now - timedelta(hours=1),
                max_snapshots=2,
            )
            third = record_autonomy_growth_snapshot(
                resolved,
                payload,
                now=now,
                max_snapshots=2,
            )
            history = load_autonomy_growth_history(resolved)

        self.assertTrue(first["wrote_snapshot"])
        self.assertTrue(second["wrote_snapshot"])
        self.assertTrue(third["wrote_snapshot"])
        self.assertEqual(third["schema_version"], "desktop_autonomy_growth_snapshot_write.v1")
        self.assertEqual(third["retained_snapshot_count"], 2)
        self.assertFalse(third["media_mutation_performed"])
        self.assertFalse(third["cleanup_performed"])
        snapshot_path = Path(third["snapshot_path"])
        self.assertEqual(snapshot_path.parent, resolved.state_root / "Diagnostics")
        self.assertEqual(Path(third["lock_path"]), snapshot_path.with_name(f"{snapshot_path.name}.lock"))
        self.assertEqual(history["schema_version"], "desktop_autonomy_growth_history.v1")
        self.assertEqual(history["snapshot_count"], 2)
        self.assertEqual(history["invalid_line_count"], 0)
        self.assertEqual(len(history["snapshots"]), 2)
        self.assertEqual(history["snapshots"][0]["recorded_at_utc"], second["snapshot"]["recorded_at_utc"])
        self.assertEqual(history["snapshots"][1]["recorded_at_utc"], third["snapshot"]["recorded_at_utc"])

    def test_record_growth_snapshot_reports_lock_contention_without_writing(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            resolved = _resolved(root)
            now = datetime(2026, 6, 18, 12, 0, tzinfo=UTC)
            payload = autonomy_health_payload(
                resolved,
                pending_publish={"rows": [], "count": 0, "total_bytes": 10, "health_count": 0},
                path_health={"operator_status": "ready", "rows": []},
                now=now,
            )
            snapshot_path = resolved.state_root / "Diagnostics" / "autonomy_growth_snapshots.jsonl"
            lock_path = snapshot_path.with_name(f"{snapshot_path.name}.lock")
            lock_path.parent.mkdir(parents=True)
            lock_path.write_text("held", encoding="utf-8")

            with patch("mediapipeline.core.diagnostics.autonomy_health.AUTONOMY_GROWTH_SNAPSHOT_LOCK_TIMEOUT_SECONDS", 0.0):
                result = record_autonomy_growth_snapshot(resolved, payload, now=now, max_snapshots=2)

        self.assertFalse(result["wrote_snapshot"])
        self.assertEqual(Path(result["lock_path"]), lock_path)
        self.assertIn("snapshot lock unavailable", result["error"])
        self.assertFalse(snapshot_path.exists())

    def test_old_operator_required_failure_blocks(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            resolved = _resolved(root)
            assert resolved.failed_markers_path is not None
            resolved.failed_markers_path.mkdir(parents=True)
            old = (datetime.now(UTC) - timedelta(days=4)).isoformat()
            report = resolved.failed_markers_path / "failure.json"
            report.write_text(
                json.dumps(
                    {
                        "classification": "operator_required",
                        "stage": "subtitle-ocr",
                        "reason": "OCR tool missing",
                        "recorded_at": old,
                    }
                ),
                encoding="utf-8",
            )

            payload = autonomy_health_payload(
                resolved,
                pending_publish={"rows": [], "count": 0, "total_bytes": 0, "health_count": 0},
                path_health={"operator_status": "ready", "rows": []},
            )

        self.assertEqual(payload["overall_status"], "blocked")
        self.assertIn("autonomy_failure_operator_required_old", {item["code"] for item in payload["blockers"]})
        self.assertEqual(payload["categories"]["subtitles_ocr"]["status"], "review")

    def test_historical_round_failure_reports_do_not_create_active_failure_review(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            resolved = _resolved(root)
            assert resolved.failed_reports_path is not None
            assert resolved.failed_markers_path is not None
            resolved.failed_reports_path.mkdir(parents=True)
            resolved.failed_markers_path.mkdir(parents=True)
            (resolved.failed_reports_path / "round_failures_20260616_120000.json").write_text(
                json.dumps(
                    {
                        "schema_version": "round_failures.v1",
                        "failures": [
                            {
                                "classification": "operator_required",
                                "stage": "subtitle-ocr",
                                "reason": "historical report row",
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )

            payload = autonomy_health_payload(
                resolved,
                pending_publish={"rows": [], "count": 0, "total_bytes": 0, "health_count": 0},
                path_health={"operator_status": "ready", "rows": []},
            )

        failures = payload["categories"]["failures"]
        self.assertEqual(payload["overall_status"], "ready")
        self.assertEqual(failures["status"], "ready")
        self.assertEqual(failures["metrics"]["artifact_count"], 0)
        self.assertEqual(payload["review_count"], 0)

    def test_source_media_failure_paths_do_not_count_as_infrastructure(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            resolved = _resolved(root)
            assert resolved.failed_markers_path is not None
            resolved.failed_markers_path.mkdir(parents=True)
            for idx in range(3):
                (resolved.failed_markers_path / f"source_media_{idx}.json").write_text(
                    json.dumps(
                        {
                            "schema_version": "failure_record.v1",
                            "category": "probe",
                            "operation": "encode",
                            "source_path": rf"\\server\share\Show\S03E{idx + 1:02d}.mkv",
                            "source_full_path": rf"\\server\share\Show\S03E{idx + 1:02d}.mkv",
                            "classification": "permanent",
                            "error_code": "SOURCE_MEDIA_STREAM_UNSUPPORTED",
                            "reason": "FFmpeg NVENC encode failed: invalid argument.",
                            "artifact_path": str(root / "State" / "Failures" / "Artifacts" / f"{idx}.mkv"),
                            "reproduction_path": str(root / "State" / "Failures" / "Reports" / f"{idx}.cmd.txt"),
                            "repro_path": str(root / "State" / "Failures" / "Reports" / f"{idx}.cmd.txt"),
                        }
                    ),
                    encoding="utf-8",
                )

            payload = autonomy_health_payload(
                resolved,
                pending_publish={"rows": [], "count": 0, "total_bytes": 0, "health_count": 0},
                path_health={"operator_status": "ready", "rows": []},
            )

        failures = payload["categories"]["failures"]
        self.assertEqual(failures["status"], "review")
        self.assertEqual(failures["metrics"]["artifact_count"], 3)
        self.assertEqual(failures["metrics"]["infrastructure_count"], 0)
        self.assertTrue(payload["launch_gate"]["can_start_new_work"])
        self.assertNotIn("autonomy_failure_infrastructure_repeated", {item["code"] for item in payload["blockers"]})

    def test_repeated_network_failure_values_still_block(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            resolved = _resolved(root)
            assert resolved.failed_markers_path is not None
            resolved.failed_markers_path.mkdir(parents=True)
            for idx in range(3):
                (resolved.failed_markers_path / f"network_{idx}.json").write_text(
                    json.dumps(
                        {
                            "schema_version": "failure_record.v1",
                            "operation": "publish",
                            "classification": "retryable",
                            "error_code": "NETWORK_SHARE_PATH_UNAVAILABLE",
                            "reason": "Robocopy publish failed because the network share path is not reachable.",
                            "source_path": rf"\\server\share\Show\S03E{idx + 1:02d}.mkv",
                        }
                    ),
                    encoding="utf-8",
                )

            payload = autonomy_health_payload(
                resolved,
                pending_publish={"rows": [], "count": 0, "total_bytes": 0, "health_count": 0},
                path_health={"operator_status": "ready", "rows": []},
            )

        failures = payload["categories"]["failures"]
        self.assertEqual(payload["overall_status"], "blocked")
        self.assertEqual(failures["metrics"]["infrastructure_count"], 3)
        self.assertIn("autonomy_failure_infrastructure_repeated", {item["code"] for item in payload["blockers"]})


if __name__ == "__main__":
    unittest.main()
