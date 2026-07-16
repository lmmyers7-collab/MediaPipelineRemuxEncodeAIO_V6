from __future__ import annotations

import csv
import json
import sys
import tempfile
import unittest
from datetime import UTC, datetime
from pathlib import Path
from unittest import mock

from mediapipeline.tools.paths import find_repo_root

REPO_ROOT = find_repo_root(Path(__file__))
sys.path.insert(0, str(REPO_ROOT / "src"))

from mediapipeline.core.kernel.contracts.pending_publish import PendingPushManifest  # noqa: E402
from mediapipeline.core.paths.contracts import ResolvedPaths  # noqa: E402
from mediapipeline.core.processes.rerun_results import (  # noqa: E402
    _destination_summary,
    rerun_promote_dry_run,
    rerun_promote_to_pending_publish,
    rerun_results_payload,
)
from mediapipeline.core.processes.rerun_rules import AUDIO_LANGUAGE_REMEDIATION  # noqa: E402
from mediapipeline.core.processes.rerun_control import (  # noqa: E402
    build_rerun_continue_pending_request,
    request_rerun_stop_after_current,
    rerun_waiting_restart_posture,
)
from mediapipeline.core.processes.rerun_results_queue_projection import (  # noqa: E402
    _current_rerun_summary,
    _exact_live_rerun_activity,
    _network_lifecycle_counts,
    _network_output_probe,
)
from mediapipeline.core.processes.rerun_results_destination_policy import (  # noqa: E402
    _network_output_hash_evidence,
)
from mediapipeline.core.publish.pending_manifest import pending_manifest_row  # noqa: E402


def _resolved(root: Path) -> ResolvedPaths:
    local_base = root / "LocalBase"
    state_root = local_base / "State"
    return ResolvedPaths(
        app_root=root,
        workspace_root=root,
        pipeline_path=root / "ops" / "pipeline" / "entrypoints" / "MediaPipeline.ps1",
        config_path=root / "config.psd1",
        audit_script_path=root / "audit.ps1",
        rerun_script_path=root / "rerun.ps1",
        powershell_host="pwsh",
        local_base=local_base,
        state_root=state_root,
        pending_push_path=state_root / "PendingServerPush",
        audit_reports_path=local_base / "AuditReports",
        config_data={"Outsource": str(root / "Outsource")},
    )


def _write_active_job(resolved: ResolvedPaths, *, launch_id: str, job_kind: str = "rerun_csv", csv_path: str = "") -> Path:
    active_jobs = resolved.state_root / "ActiveJobs"
    active_jobs.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": "desktop_active_job.v1",
        "launch_id": launch_id,
        "job_kind": job_kind,
        "mode": "run",
        "status": "active",
        "pid": 43210,
        "app_pid": 12345,
        "command_line": "pwsh -File Invoke-RerunCsv.ps1",
        "args": ["pwsh", "-File", "Invoke-RerunCsv.ps1"],
        "cwd": str(resolved.workspace_root),
        "stdout_log": "",
        "stderr_log": "",
        "show_console": False,
        "metadata": {"csv_path": csv_path} if csv_path else {},
        "launched_at": "2026-07-03T12:00:00-04:00",
        "last_update": "2026-07-03T12:00:01-04:00",
        "completed_at": "",
        "return_code": None,
    }
    path = active_jobs / f"{launch_id}.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


class RerunResultsTests(unittest.TestCase):
    def test_exact_live_rerun_activity_requires_identity_matched_process_and_paths(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            resolved = _resolved(root)
            launch_id = "launch-current"
            batch_id = "batch-current"
            command_id = "command-current"
            manifest_path = resolved.local_base / "RerunManifests" / f"{batch_id}.json"
            enrollment_path = resolved.state_root / "Rerun" / "Local" / f"{batch_id}.json"
            active_job_path = _write_active_job(resolved, launch_id=launch_id)
            active_job = json.loads(active_job_path.read_text(encoding="utf-8"))
            active_job["metadata"] = {
                "batch_id": batch_id,
                "command_id": command_id,
                "manifest_path": str(manifest_path),
                "enrollment_path": str(enrollment_path),
            }
            active_job_path.write_text(json.dumps(active_job), encoding="utf-8")
            payload = {
                "launch_id": launch_id,
                "batch_id": batch_id,
                "command_id": command_id,
                "manifest_path": str(manifest_path),
                "enrollment_path": str(enrollment_path),
            }

            with mock.patch(
                "mediapipeline.core.processes.rerun_results_queue_projection.active_job_pid_matches_record",
                return_value=True,
            ) as pid_matches:
                self.assertTrue(_exact_live_rerun_activity(resolved, payload))
                self.assertFalse(
                    _exact_live_rerun_activity(
                        resolved,
                        {**payload, "manifest_path": str(root / "copied.json")},
                    )
                )

        pid_matches.assert_called_once()

    def test_current_rerun_summary_ignores_terminal_only_history(self) -> None:
        current = _current_rerun_summary(
            [
                {
                    "manifest_key": "terminal",
                    "batch_id": "terminal-batch",
                    "status": "stopped_after_current",
                    "rows": [{"status": "completed", "is_terminal": True}],
                    "available_actions": [],
                }
            ],
            queue_source="csv_rerun",
        )

        self.assertEqual(current["selection_reason"], "none")
        self.assertEqual(current["activity_state"], "none")
        self.assertEqual(current["rows"], [])

        network_current = _current_rerun_summary(
            [
                {
                    "manifest_key": "network-terminal",
                    "batch_id": "network-terminal-batch",
                    "status": "completed",
                    "batch_terminal": True,
                    "rows": [{"queue_status": "completed", "is_terminal": True}],
                    "available_actions": [],
                }
            ],
            queue_source="network_csv_rerun",
            network=True,
        )

        self.assertEqual(network_current["selection_reason"], "none")
        self.assertEqual(network_current["rows"], [])

    def test_current_rerun_summary_prioritizes_live_then_actionable_then_review(self) -> None:
        manifests = [
            {
                "manifest_key": "review",
                "batch_id": "review-batch",
                "status": "running",
                "rows": [{"status": "pending", "is_terminal": False}],
                "available_actions": [],
            },
            {
                "manifest_key": "actionable",
                "batch_id": "actionable-batch",
                "status": "stopped_after_current",
                "rows": [{"status": "pending", "is_terminal": False}],
                "available_actions": [{"action": "continue_pending", "route": "/api/rerun/continue"}],
            },
            {
                "manifest_key": "live",
                "batch_id": "live-batch",
                "status": "running",
                "runtime_active": True,
                "rows": [{"status": "running", "is_terminal": False}],
                "available_actions": [],
            },
        ]

        current = _current_rerun_summary(manifests, queue_source="csv_rerun")

        self.assertEqual(current["manifest_key"], "live")
        self.assertEqual(current["selection_reason"], "exact_live_process")
        self.assertEqual(current["activity_state"], "active")

    def test_network_destination_hash_marks_bounded_probe_timeout_stale(self) -> None:
        with mock.patch(
            "mediapipeline.core.processes.rerun_results_destination_policy.run_source_probe",
            side_effect=TimeoutError("UNC probe timed out"),
        ) as probe:
            evidence = _network_output_hash_evidence(Path(r"\\server\handoff\Movie.mkv"))

        self.assertEqual(evidence["probe_status"], "access_failed")
        self.assertTrue(evidence["stale"])
        self.assertFalse(evidence["exists"])
        probe.assert_called_once()

    def test_network_output_projection_marks_bounded_probe_timeout_stale(self) -> None:
        with mock.patch(
            "mediapipeline.core.processes.rerun_results_queue_projection.run_source_probe",
            side_effect=TimeoutError("UNC probe timed out"),
        ) as probe:
            evidence = _network_output_probe(r"\\server\handoff\Movie.mkv")

        self.assertEqual(evidence["status"], "access_failed")
        self.assertTrue(evidence["stale"])
        self.assertFalse(evidence["is_file"])
        probe.assert_called_once()

    def test_destination_summary_never_resolves_destination_paths(self) -> None:
        rows = [
            {
                "queue_status": "failed",
                "destination_path": r"\\offline-server\library\Movie\Movie.mkv",
            }
        ]

        with mock.patch(
            "mediapipeline.core.processes.rerun_results._path_key",
            side_effect=AssertionError("display-only destination summary must not resolve filesystem paths"),
        ):
            summary = _destination_summary(rows)

        self.assertEqual(summary["distinct_final_destination_count"], 1)

    def test_rerun_control_requires_exactly_one_active_rerun_and_writes_marker_only(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            resolved = _resolved(root)
            csv_path = root / "rerun.csv"
            csv_path.write_text("source_path\n", encoding="utf-8")
            manifest_root = resolved.local_base / "RerunManifests"
            manifest_root.mkdir(parents=True)
            manifest_path = manifest_root / "rerun_active.json"
            manifest_path.write_text(
                json.dumps(
                    {
                        "batch_id": "rerun-active",
                        "status": "chunk_1_complete",
                        "csv_path": str(csv_path),
                        "rows": [{"status": "pending", "source_path": str(root / "Movie.mkv")}],
                    }
                ),
                encoding="utf-8",
            )
            _write_active_job(resolved, launch_id="rerun-active", csv_path=str(csv_path))

            result = request_rerun_stop_after_current(
                resolved,
                {"action": "stop_after_current", "confirm_stop": True},
            )

            self.assertTrue(result.ok, result.message)
            marker_path = Path(result.data["marker_path"])
            self.assertTrue(marker_path.is_file())
            marker = json.loads(marker_path.read_text(encoding="utf-8"))
            self.assertEqual(marker["action"], "stop_after_current")
            self.assertEqual(marker["batch_id"], "rerun-active")
            self.assertEqual(marker["manifest_path"], str(manifest_path))
            persisted_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            self.assertEqual(persisted_manifest["status"], "chunk_1_complete")

    def test_rerun_control_pause_alias_writes_stop_marker_with_pause_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            resolved = _resolved(root)
            csv_path = root / "rerun.csv"
            csv_path.write_text("source_path\n", encoding="utf-8")
            manifest_root = resolved.local_base / "RerunManifests"
            manifest_root.mkdir(parents=True)
            manifest_path = manifest_root / "rerun_active.json"
            manifest_path.write_text(
                json.dumps(
                    {
                        "batch_id": "rerun-active",
                        "status": "chunk_1_complete",
                        "csv_path": str(csv_path),
                        "rows": [{"status": "pending", "source_path": str(root / "Movie.mkv")}],
                    }
                ),
                encoding="utf-8",
            )
            _write_active_job(resolved, launch_id="rerun-active", csv_path=str(csv_path))

            result = request_rerun_stop_after_current(
                resolved,
                {"action": "pause", "confirm_pause": True},
            )

            self.assertTrue(result.ok, result.message)
            self.assertEqual(result.command, "rerun.control.pause")
            self.assertEqual(result.data["action"], "pause")
            self.assertEqual(result.data["marker_action"], "stop_after_current")
            marker_path = Path(result.data["marker_path"])
            marker = json.loads(marker_path.read_text(encoding="utf-8"))
            self.assertEqual(marker["action"], "stop_after_current")
            self.assertEqual(marker["requested_action"], "pause")
            self.assertEqual(marker["batch_id"], "rerun-active")
            self.assertEqual(marker["manifest_path"], str(manifest_path))

    def test_rerun_control_rejects_no_active_non_rerun_and_ambiguous_reruns(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            resolved = _resolved(root)
            missing = request_rerun_stop_after_current(resolved, {"action": "stop_after_current", "confirm_stop": True})
            self.assertFalse(missing.ok)
            self.assertEqual(missing.severity, "warning")

            _write_active_job(resolved, launch_id="pipeline-active", job_kind="pipeline")
            non_rerun = request_rerun_stop_after_current(resolved, {"action": "stop_after_current", "confirm_stop": True})
            self.assertFalse(non_rerun.ok)
            self.assertIn("active_work_is_not_rerun_csv", non_rerun.errors)

            _write_active_job(resolved, launch_id="rerun-one", csv_path=str(root / "one.csv"))
            _write_active_job(resolved, launch_id="rerun-two", csv_path=str(root / "two.csv"))
            ambiguous = request_rerun_stop_after_current(resolved, {"action": "stop_after_current", "confirm_stop": True})
            self.assertFalse(ambiguous.ok)
            self.assertIn("ambiguous_active_rerun_csv_jobs", ambiguous.errors)

    def test_rerun_results_reports_stop_counts_and_continue_eligibility(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            resolved = _resolved(root)
            pending_source = root / "pending.mkv"
            pending_source.write_bytes(b"pending-media")
            csv_path = root / "rerun.csv"
            csv_path.write_text(
                f"source_path,source_identity_v2,source_content_sha256,source_content_sha256_algorithm\n"
                f"{pending_source},pending-v2,{'a' * 64},sha256-full-file\n",
                encoding="utf-8",
            )
            manifest_root = resolved.local_base / "RerunManifests"
            manifest_root.mkdir(parents=True)
            (manifest_root / "rerun_stopped.json").write_text(
                json.dumps(
                    {
                        "batch_id": "rerun-stopped",
                        "status": "stopped_after_current",
                        "csv_path": str(csv_path),
                        "current_chunk": 2,
                        "remaining_pending_count": 1,
                        "stop_request_id": "rerun-stop-1",
                        "stopped_at": "2026-07-03T12:05:00-04:00",
                        "rows": [
                            {"status": "review_workspace", "source_path": str(root / "done.mkv")},
                            {
                                "row_index": 0,
                                "status": "pending",
                                "source_path": str(pending_source),
                                "source_identity_v2": "pending-v2",
                                "source_content_sha256": "a" * 64,
                                "source_content_sha256_algorithm": "sha256-full-file",
                            },
                            {"status": "failed", "source_path": str(root / "failed.mkv")},
                        ],
                    }
                ),
                encoding="utf-8",
            )

            payload = rerun_results_payload(resolved)
            manifest = payload["manifests"][0]

            self.assertEqual(manifest["status"], "stopped_after_current")
            self.assertEqual(manifest["current_chunk"], 2)
            self.assertEqual(manifest["remaining_pending_count"], 1)
            self.assertTrue(manifest["can_continue_pending"])
            self.assertEqual(manifest["row_status_counts"]["pending"], 1)
            self.assertEqual(manifest["stop_request_id"], "rerun-stop-1")
            action = next(item for item in manifest["available_actions"] if item["action"] == "continue_pending")
            self.assertTrue(action["request_id_required"])
            self.assertFalse(action["requires_confirmation"])
            current = payload["queue_state"]["current_local"]
            self.assertEqual(current["manifest_key"], manifest["manifest_key"])
            self.assertEqual(current["batch_id"], "rerun-stopped")
            self.assertEqual(current["selection_reason"], "recovery_actionable")
            self.assertEqual(current["activity_state"], "recoverable")
            self.assertEqual(current["row_count"], 3)
            self.assertEqual(current["remaining_pending_count"], 1)
            self.assertEqual(current["queue_status_counts"], manifest["queue_status_counts"])
            self.assertEqual(current["available_actions"], manifest["available_actions"])
            self.assertEqual(payload["queue_state"]["current_network"]["selection_reason"], "none")

    def test_rerun_results_exposes_first_class_queue_state_rows(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            resolved = _resolved(root)
            manifest_root = resolved.local_base / "RerunManifests"
            manifest_root.mkdir(parents=True)
            output = root / "review-output.mkv"
            output.write_bytes(b"media")
            final_output = root / "Final" / "Movie.mkv"
            pending_final_output = root / "Final" / "Pending Movie.mkv"
            pending_manifest = root / "Pending" / "Movie.manifest.json"
            (manifest_root / "rerun_state.json").write_text(
                json.dumps(
                    {
                        "batch_id": "rerun-state",
                        "status": "stopped_after_current",
                        "created_at": "2026-07-03T12:00:00Z",
                        "destination_mode": "auto_replace_clean_else_pending_review",
                        "collision_policy": "replace_final",
                        "rows": [
                            {"status": "pending", "source_path": str(root / "pending.mkv")},
                            {"status": "running", "source_path": str(root / "active.mkv")},
                            {"status": "invalid", "source_path": str(root / "blocked.mkv"), "reason": "source file not found"},
                            {"status": "warning", "source_path": str(root / "warning.mkv"), "warning_reason": "audit warning"},
                            {
                                "status": "failed",
                                "source_path": str(root / "failed.mkv"),
                                "failure_code": "RERUN_OUTPUT_MISSING",
                                "operator_message": "The rerun did not create the expected output. Source media was not changed.",
                                "reason": "RERUN_OUTPUT_MISSING: The rerun did not create the expected output. Source media was not changed.",
                            },
                            {"status": "stopped", "source_path": str(root / "stopped.mkv")},
                            {"status": "completed", "source_path": str(root / "completed.mkv"), "verified_output_path": str(output), "final_output_path": str(final_output), "final_output_source": "csv_completed_output", "final_output_source_field": "plex_planned_path", "audit_issue_codes": "audio-policy"},
                            {"status": "review_workspace", "source_path": str(root / "review.mkv"), "verified_output_path": str(output), "reason": "operator review"},
                            {"status": "pending_publish", "source_path": str(root / "pending-publish.mkv"), "server_out": str(pending_final_output), "final_output_source": "csv_completed_output", "final_output_source_field": "plex_planned_path", "pending_publish_manifest_path": str(pending_manifest), "auto_destination_decision": "pending_publish_review"},
                            {"status": "published_replace_final", "source_path": str(root / "returned.mkv"), "published_path": str(final_output), "final_output_source": "csv_completed_output", "final_output_source_field": "plex_planned_path", "replaced_final_hold_path": str(root / "Hold" / "Movie.mkv"), "completed_manifest_append": "appended"},
                            {"status": "skipped", "source_path": str(root / "skipped.mkv")},
                        ],
                    }
                ),
                encoding="utf-8",
            )

            payload = rerun_results_payload(resolved)

        self.assertEqual(payload["queue_state"]["schema_version"], "desktop_rerun_queue_state.v1")
        manifest = payload["manifests"][0]
        destination_summary = manifest["destination_summary"]
        self.assertEqual(destination_summary["distinct_final_destination_count"], 2)
        self.assertEqual(destination_summary["counts"]["csv_completed_output_rows"], 3)
        self.assertEqual(destination_summary["counts"]["pending_publish"], 1)
        self.assertEqual(destination_summary["counts"]["replaced_returned"], 1)
        self.assertIn("from CSV completed data", destination_summary["detail"])
        self.assertFalse(payload["queue_state"]["uses_pipeline_start"])
        by_name = {Path(str(row["source_path"])).name: row for row in payload["queue_state"]["rows"]}
        self.assertEqual(by_name["pending.mkv"]["queue_status_label"], "Blocked")
        self.assertEqual(by_name["pending.mkv"]["operator_status_state"], "review")
        self.assertEqual(
            by_name["pending.mkv"]["recovery_blocked_reason_code"],
            "row_index_missing",
        )
        self.assertEqual(by_name["active.mkv"]["queue_status_label"], "Active")
        self.assertEqual(by_name["blocked.mkv"]["queue_status_label"], "Blocked")
        self.assertEqual(by_name["warning.mkv"]["queue_status_label"], "Warning")
        self.assertEqual(by_name["failed.mkv"]["queue_status_label"], "Failed")
        self.assertEqual(by_name["failed.mkv"]["failure_code"], "RERUN_OUTPUT_MISSING")
        self.assertEqual(
            by_name["failed.mkv"]["operator_guidance"],
            "The rerun did not create the expected output. Source media was not changed.",
        )
        self.assertEqual(by_name["failed.mkv"]["attempt_evidence"]["failure_code"], "RERUN_OUTPUT_MISSING")
        self.assertEqual(by_name["stopped.mkv"]["queue_status_label"], "Stopped")
        self.assertEqual(by_name["completed.mkv"]["queue_status_label"], "Completed")
        self.assertIn("audio-policy", by_name["completed.mkv"]["audit_issue_code_list"])
        self.assertEqual(by_name["completed.mkv"]["rerun_rule_id"], AUDIO_LANGUAGE_REMEDIATION)
        self.assertEqual(by_name["completed.mkv"]["rerun_rule_destination_behavior"], "auto_replace_clean_else_pending_review")
        self.assertTrue(by_name["completed.mkv"]["rerun_rule_replacement_eligible"])
        self.assertEqual(by_name["completed.mkv"]["rule_decision"]["schema_version"], "desktop_rerun_rule_decision.v1")
        self.assertEqual(by_name["completed.mkv"]["destination_state"]["rerun_rule_id"], AUDIO_LANGUAGE_REMEDIATION)
        self.assertEqual(by_name["completed.mkv"]["final_output_source"], "csv_completed_output")
        self.assertEqual(by_name["completed.mkv"]["final_output_source_field"], "plex_planned_path")
        self.assertEqual(by_name["completed.mkv"]["attempt_evidence"]["rule_decision"]["rule_id"], AUDIO_LANGUAGE_REMEDIATION)
        self.assertIn("promote_to_pending_publish", {action["action"] for action in by_name["completed.mkv"]["available_actions"]})
        self.assertEqual(by_name["review.mkv"]["queue_status_label"], "Awaiting Review")
        self.assertEqual(by_name["pending-publish.mkv"]["queue_status_label"], "Pending Publish")
        self.assertEqual(by_name["returned.mkv"]["queue_status_label"], "Replaced / Returned")
        self.assertEqual(by_name["returned.mkv"]["destination_path"], str(final_output))
        self.assertEqual(by_name["returned.mkv"]["completed_manifest_append"], "appended")
        self.assertEqual(by_name["skipped.mkv"]["queue_status_label"], "Skipped")
        self.assertEqual(payload["counts"]["queue_status_counts"]["stopped"], 2)
        self.assertEqual(payload["counts"]["queue_status_counts"]["replaced_returned"], 1)

    def test_rerun_results_projects_correlation_recovery_timeline_and_required_counts(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            resolved = _resolved(root)
            manifest_root = resolved.local_base / "RerunManifests"
            manifest_root.mkdir(parents=True)
            manifest_path = manifest_root / "batch-recovery.json"
            manifest_path.write_text(
                json.dumps(
                    {
                        "schema_version": "rerun_batch_manifest.v2",
                        "batch_id": "batch-recovery",
                        "command_id": "command-recovery",
                        "launch_id": "launch-recovery",
                        "manifest_path": str(manifest_path),
                        "status": "retry_scheduled",
                        "created_at": "2026-07-13T20:00:00Z",
                        "started_at": "2026-07-13T20:00:01Z",
                        "last_transition_at": "2026-07-13T20:00:10Z",
                        "current_phase": "waiting_for_source",
                        "current_row_index": 0,
                        "rows": [
                            {
                                "row_index": 0,
                                "source_path": str(root / "Offline" / "Movie.mkv"),
                                "status": "retry_scheduled",
                                "reason_code": "source_location_unavailable",
                                "reason": "Configured source root is temporarily unavailable.",
                                "attempt_count": 2,
                                "max_attempts": 5,
                                "first_failure_at": "2026-07-13T20:00:02Z",
                                "last_failure_at": "2026-07-13T20:00:10Z",
                                "last_transition_at": "2026-07-13T20:00:10Z",
                                "next_retry_at": "2026-07-13T20:00:25Z",
                                "last_error": "The configured root could not be reached.",
                                "automatic_next_action": "Retry source availability at the scheduled time.",
                                "operator_action_required": False,
                                "available_operator_action": "Wait or request Retry now.",
                                "timeline": [
                                    {"state": "accepted", "at": "2026-07-13T20:00:00Z", "reason_code": "request_accepted"},
                                    {"state": "retry_scheduled", "at": "2026-07-13T20:00:10Z", "reason_code": "source_location_unavailable"},
                                ],
                            },
                            {
                                "row_index": 1,
                                "source_path": str(root / "Ready" / "Other.mkv"),
                                "status": "processing",
                                "last_transition_at": "2026-07-13T20:00:08Z",
                                "automatic_next_action": "Continue processing from verified scratch.",
                                "operator_action_required": False,
                            },
                            {
                                "row_index": 2,
                                "source_path": str(root / "Offline" / "Exhausted.mkv"),
                                "status": "retry_exhausted",
                                "reason_code": "source_location_unavailable",
                                "reason": "Source retry limit was exhausted.",
                                "attempt_count": 5,
                                "max_attempts": 5,
                                "first_failure_at": "2026-07-13T19:00:00Z",
                                "last_failure_at": "2026-07-13T20:00:09Z",
                                "last_transition_at": "2026-07-13T20:00:09Z",
                                "next_retry_at": "",
                                "last_error": "Source root remains offline.",
                                "automatic_next_action": "Wait for an operator retry request.",
                                "operator_action_required": True,
                                "available_operator_action": "Retry after restoring the source root.",
                            },
                        ],
                    }
                ),
                encoding="utf-8",
            )

            payload = rerun_results_payload(resolved)

        manifest = payload["manifests"][0]
        self.assertEqual(manifest["command_id"], "command-recovery")
        self.assertEqual(manifest["launch_id"], "launch-recovery")
        self.assertEqual(manifest["batch_id"], "batch-recovery")
        self.assertEqual(manifest["current_phase"], "waiting_for_source")
        self.assertEqual(manifest["current_row_index"], 0)
        self.assertEqual(manifest["lifecycle_counts"]["total"], 3)
        self.assertEqual(manifest["lifecycle_counts"]["waiting"], 1)
        self.assertEqual(manifest["lifecycle_counts"]["retrying"], 1)
        self.assertEqual(manifest["lifecycle_counts"]["active"], 1)
        self.assertEqual(manifest["lifecycle_counts"]["failed"], 1)

        by_name = {Path(str(row["source_path"])).name: row for row in payload["queue_state"]["rows"]}
        waiting = by_name["Movie.mkv"]
        self.assertEqual(waiting["lifecycle_state"], "retry_scheduled")
        self.assertEqual(waiting["queue_status"], "retrying")
        self.assertEqual(waiting["queue_status_label"], "Retry Scheduled")
        self.assertFalse(waiting["is_terminal"])
        self.assertEqual(waiting["reason_code"], "source_location_unavailable")
        self.assertEqual(waiting["attempt_count"], 2)
        self.assertEqual(waiting["next_retry_at"], "2026-07-13T20:00:25Z")
        self.assertFalse(waiting["operator_action_required"])
        self.assertEqual(waiting["timeline"][-1]["state"], "retry_scheduled")
        self.assertIn("manifest", waiting["evidence_links"])
        self.assertIn("active_jobs", waiting["evidence_links"])
        exhausted = by_name["Exhausted.mkv"]
        self.assertEqual(exhausted["lifecycle_state"], "retry_exhausted")
        self.assertEqual(exhausted["queue_status"], "failed")
        self.assertEqual(exhausted["queue_status_label"], "Retry Exhausted")
        self.assertTrue(exhausted["is_terminal"])
        self.assertTrue(exhausted["operator_action_required"])
        self.assertIn("retry", {action["action"] for action in exhausted["available_actions"]})
        self.assertEqual(payload["counts"]["lifecycle_counts"]["total"], 3)
        self.assertEqual(payload["counts"]["lifecycle_counts"]["waiting"], 1)
        self.assertEqual(payload["counts"]["lifecycle_counts"]["retrying"], 1)

    def test_rerun_results_exposes_network_reducer_rows_read_only(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            resolved = _resolved(root)
            source = root / "Source" / "Movie.mkv"
            output = root / "NetworkRerunHandoff" / "batch-1" / "row-1" / "Movie.mkv"
            source.parent.mkdir(parents=True)
            output.parent.mkdir(parents=True)
            source.write_bytes(b"source")
            output.write_bytes(b"handoff-output")
            network_root = resolved.state_root / "Rerun" / "Network"
            network_root.mkdir(parents=True)
            (network_root / "batch-1.json").write_text(
                json.dumps(
                    {
                        "schema_version": "desktop_rerun_network_batch.v1",
                        "batch_id": "batch-1",
                        "status": "active",
                        "phase": "phase_5_coordinator_result_reducer",
                        "claim_provider_enabled": True,
                        "worker_execution_enabled": True,
                        "rows_claimable": False,
                        "created_at_utc": "2026-07-06T00:00:00Z",
                        "updated_at_utc": "2026-07-06T00:01:00Z",
                        "rows": [
                            {
                                "schema_version": "desktop_rerun_network_batch_row.v1",
                                "row_key": "row-1",
                                "row_index": 0,
                                "status": "worker_completed_pending_reduction",
                                "claim_status": "done_reported",
                                "claimable": False,
                                "source_path": str(source),
                                "planned_output_path": str(output.parent),
                                "verified_output_path": str(output),
                                "worker_result": {
                                    "schema_version": "desktop_rerun_network_worker_result_snapshot.v1",
                                    "job_id": "job-1",
                                    "worker_id": "worker-1",
                                    "success": True,
                                    "output_path": str(output),
                                    "pending_reduction": True,
                                },
                                "reducer_result": {
                                    "schema_version": "desktop_rerun_network_result_reduction.v1",
                                    "classification": "success",
                                    "accepted": True,
                                    "pending_destination_policy": True,
                                    "output_artifact": {
                                        "path": str(output),
                                        "exists": True,
                                        "under_planned_handoff": True,
                                    },
                                },
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )

            payload = rerun_results_payload(resolved)

        self.assertTrue(payload["queue_state"]["contains_network_csv_rerun"])
        self.assertEqual(payload["counts"]["network_manifest_count"], 1)
        self.assertEqual(payload["counts"]["network_row_count"], 1)
        network_rows = [row for row in payload["queue_state"]["rows"] if row["queue_source"] == "network_csv_rerun"]
        self.assertEqual(len(network_rows), 1)
        row = network_rows[0]
        self.assertEqual(row["queue_kind"], "network_csv_rerun_row")
        self.assertEqual(row["queue_status"], "pending_reduction")
        self.assertEqual(row["queue_status_label"], "Pending Reduction")
        self.assertEqual(row["network_reducer_result"]["classification"], "success")
        self.assertTrue(row["destination_state"]["pending_destination_policy"])
        self.assertFalse(row["can_promote_to_pending_publish"])
        self.assertTrue(row["can_open_output"])

    def test_rerun_results_projects_network_retry_timeline_actions_and_network_only_counts(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            resolved = _resolved(root)
            source = root / "Source" / "Movie.mkv"
            source.parent.mkdir(parents=True)
            source.write_bytes(b"source")
            network_root = resolved.state_root / "Rerun" / "Network"
            network_root.mkdir(parents=True)
            (network_root / "batch-retry.json").write_text(
                json.dumps(
                    {
                        "schema_version": "desktop_rerun_network_batch.v1",
                        "batch_id": "batch-retry",
                        "status": "retry_exhausted",
                        "phase": "phase_5_coordinator_result_reducer",
                        "terminal_at_utc": "2026-07-13T20:00:30Z",
                        "retry_exhausted_row_count": 1,
                        "terminal_row_count": 1,
                        "rows": [
                            {
                                "schema_version": "desktop_rerun_network_batch_row.v1",
                                "row_key": "row-retry",
                                "row_index": 0,
                                "status": "retry_exhausted",
                                "claim_status": "retry_exhausted",
                                "claimable": False,
                                "terminal": True,
                                "source_path": str(source),
                                "planned_output_path": str(root / "Handoff" / "row-retry"),
                                "attempt_count": 3,
                                "retry_count": 3,
                                "retry_limit": 3,
                                "retry_after_seconds": 0,
                                "next_retry_at_utc": "",
                                "manual_recovery_required": True,
                                "manual_recovery_available": True,
                                "operator_action_required": True,
                                "reason_code": "SOURCE_UNAVAILABLE",
                                "last_error": "Source remained unavailable.",
                                "next_action": "Wait for an operator retry request.",
                                "operator_action": "Request one explicit manual retry after restoring the source.",
                                "what": "Automatic Network CSV rerun retry stopped.",
                                "why": "The configured retry limit was exhausted.",
                                "when": "2026-07-13T20:00:30Z",
                                "timeline": [
                                    {
                                        "state": "retry_exhausted",
                                        "at_utc": "2026-07-13T20:00:30Z",
                                        "reason_code": "SOURCE_UNAVAILABLE",
                                        "what": "Automatic Network CSV rerun retry stopped.",
                                        "why": "The configured retry limit was exhausted.",
                                        "next": "Wait for an operator retry request.",
                                    }
                                ],
                                "first_failure": {
                                    "at_utc": "2026-07-13T20:00:00Z",
                                    "reason_code": "SOURCE_UNAVAILABLE",
                                    "reason": "Source unavailable.",
                                },
                                "last_failure": {
                                    "at_utc": "2026-07-13T20:00:30Z",
                                    "reason_code": "SOURCE_UNAVAILABLE",
                                    "reason": "Source remained unavailable.",
                                },
                                "source_replay_evidence": {
                                    "matches": True,
                                    "mismatches": [],
                                },
                                "reducer_result": {
                                    "schema_version": "desktop_rerun_network_result_reduction.v1",
                                    "classification": "failed_retryable",
                                    "accepted": False,
                                    "retryable": False,
                                    "retry_state": "retry_exhausted",
                                    "reason_code": "SOURCE_UNAVAILABLE",
                                },
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )

            payload = rerun_results_payload(resolved)

        row = next(row for row in payload["rows"] if row["queue_source"] == "network_csv_rerun")
        self.assertEqual(row["queue_status"], "failed")
        self.assertEqual(row["queue_status_label"], "Retry Exhausted")
        self.assertTrue(row["is_terminal"])
        self.assertEqual(row["attempt_count"], 3)
        self.assertEqual(row["retry_count"], 3)
        self.assertEqual(row["retry_limit"], 3)
        self.assertEqual(row["reason_code"], "SOURCE_UNAVAILABLE")
        self.assertEqual(row["last_error"], "Source remained unavailable.")
        self.assertEqual(row["timeline"][-1]["state"], "retry_exhausted")
        self.assertEqual(row["lifecycle_evidence"]["what"], "Automatic Network CSV rerun retry stopped.")
        self.assertEqual(row["lifecycle_evidence"]["next"], "Wait for an operator retry request.")
        retry_action = next(action for action in row["available_actions"] if action["action"] == "retry")
        self.assertEqual(retry_action["route"], "/api/rerun/network/retry")
        self.assertEqual(retry_action["confirmation_field"], "confirm_retry")
        self.assertTrue(retry_action["request"]["confirm_retry"])
        self.assertEqual(
            retry_action["request"]["reason"],
            "operator_requested_retry_after_source_restore",
        )
        self.assertFalse(retry_action["requires_confirmation"])
        self.assertTrue(retry_action["request_id_required"])
        self.assertTrue(retry_action["reason_required"])
        self.assertEqual(payload["counts"]["network_queue_status_counts"], {"failed": 1})
        self.assertEqual(payload["counts"]["network_lifecycle_counts"]["retry_exhausted"], 1)
        self.assertEqual(payload["counts"]["network_retry_exhausted_count"], 1)
        self.assertEqual(payload["queue_state"]["network_status_counts"], {"failed": 1})

    def test_network_lifecycle_counts_use_standard_operator_categories_for_mixed_states(self) -> None:
        rows = [
            {"status": "pending_claim", "is_terminal": False},
            {"status": "blocked", "is_terminal": True},
            {"status": "retry_scheduled", "is_terminal": False},
            {"status": "staged", "is_terminal": False},
            {"status": "claimed", "is_terminal": False},
            {"status": "complete", "is_terminal": True},
            {"status": "retry_exhausted", "is_terminal": True},
            {"status": "review_required", "is_terminal": True},
            {"status": "pending_publish", "is_terminal": True},
        ]

        counts = _network_lifecycle_counts(rows)

        self.assertEqual(
            {key: counts[key] for key in (
                "total",
                "executable",
                "blocked",
                "waiting",
                "retrying",
                "staged",
                "active",
                "completed",
                "failed",
                "review",
                "pending_publish",
            )},
            {
                "total": 9,
                "executable": 1,
                "blocked": 1,
                "waiting": 1,
                "retrying": 1,
                "staged": 1,
                "active": 1,
                "completed": 1,
                "failed": 1,
                "review": 1,
                "pending_publish": 1,
            },
        )

    def test_rerun_results_exposes_network_destination_policy_results(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            resolved = _resolved(root)
            source = root / "Source" / "Movie.mkv"
            source.parent.mkdir(parents=True)
            source.write_bytes(b"source")
            pending_payload = resolved.pending_push_path / "Movie.mkv"
            pending_manifest = resolved.pending_push_path / "Movie.mkv.manifest.json"
            final_output = root / "Outsource" / "Movie.mkv"
            resolved.pending_push_path.mkdir(parents=True)
            pending_payload.write_bytes(b"handoff-output")
            pending_manifest.write_text(json.dumps({"server_out": str(final_output)}), encoding="utf-8")
            network_root = resolved.state_root / "Rerun" / "Network"
            network_root.mkdir(parents=True)
            (network_root / "batch-1.json").write_text(
                json.dumps(
                    {
                        "schema_version": "desktop_rerun_network_batch.v1",
                        "batch_id": "batch-1",
                        "status": "active",
                        "phase": "phase_6_destination_policy_integration",
                        "destination_mode": "pending_publish",
                        "collision_policy": "suffix",
                        "rows": [
                            {
                                "schema_version": "desktop_rerun_network_batch_row.v1",
                                "row_key": "row-1",
                                "row_index": 0,
                                "status": "pending_publish",
                                "source_path": str(source),
                                "planned_output_path": str(root / "NetworkRerunHandoff" / "batch-1" / "row-1"),
                                "verified_output_path": str(root / "NetworkRerunHandoff" / "batch-1" / "row-1" / "Movie.mkv"),
                                "final_output_path": str(final_output),
                                "pending_publish_manifest_path": str(pending_manifest),
                                "pending_publish_payload_path": str(pending_payload),
                                "server_out": str(final_output),
                                "destination_policy_applied": True,
                                "reducer_result": {
                                    "schema_version": "desktop_rerun_network_result_reduction.v1",
                                    "classification": "success",
                                    "accepted": True,
                                    "pending_destination_policy": False,
                                    "destination_policy_applied": True,
                                },
                                "destination_policy_result": {
                                    "schema_version": "desktop_rerun_network_destination_policy_result.v1",
                                    "phase": "phase_6_destination_policy_integration",
                                    "action": "pending_publish",
                                    "status": "pending_publish",
                                    "ok": True,
                                    "terminal": True,
                                    "pending_publish_manifest_path": str(pending_manifest),
                                    "pending_publish_payload_path": str(pending_payload),
                                    "server_out": str(final_output),
                                },
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )

            payload = rerun_results_payload(resolved)

        network_rows = [row for row in payload["queue_state"]["rows"] if row["queue_source"] == "network_csv_rerun"]
        self.assertEqual(len(network_rows), 1)
        row = network_rows[0]
        self.assertEqual(row["queue_status"], "pending_publish")
        self.assertEqual(row["pending_publish_manifest_path"], str(pending_manifest))
        self.assertEqual(row["pending_publish_payload_path"], str(pending_payload))
        self.assertEqual(row["network_destination_policy_result"]["status"], "pending_publish")
        self.assertFalse(row["destination_state"]["pending_destination_policy"])
        self.assertTrue(row["destination_state"]["destination_policy_applied"])
        self.assertTrue(row["destination_state"]["destination_policy_terminal"])
        self.assertEqual(row["destination_state"]["destination_policy_action"], "pending_publish")

    def test_continue_pending_rows_materializes_only_pending_source_rows(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            resolved = _resolved(root)
            source_dir = root / "Source"
            source_dir.mkdir()
            duplicate = source_dir / "Duplicate.mkv"
            pending = source_dir / "Pending.mkv"
            failed = source_dir / "Failed.mkv"
            parked = source_dir / "Parked.mkv"
            complete = source_dir / "Complete.mkv"
            for item in (duplicate, pending, failed, parked, complete):
                item.write_bytes(b"media")
            csv_path = root / "rerun.csv"
            csv_path.write_text(
                "\n".join(
                    [
                        "source_path,audit_issue_codes,source_identity_v2,source_content_sha256,source_content_sha256_algorithm",
                        f"{duplicate},duplicate-failed,duplicate-failed-v2,{'1' * 64},sha256-full-file",
                        f"{duplicate},duplicate-pending,duplicate-pending-v2,{'2' * 64},sha256-full-file",
                        f"{pending},pending-issue,pending-v2,{'3' * 64},sha256-full-file",
                        f"{failed},failed-issue,failed-v2,{'4' * 64},sha256-full-file",
                        f"{parked},pending-publish-issue,parked-v2,{'5' * 64},sha256-full-file",
                        f"{complete},complete-issue,complete-v2,{'6' * 64},sha256-full-file",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            manifest_root = resolved.local_base / "RerunManifests"
            manifest_root.mkdir(parents=True)
            manifest_path = manifest_root / "rerun_stopped.json"
            manifest_path.write_text(
                json.dumps(
                    {
                        "batch_id": "rerun-stopped",
                        "status": "stopped_after_current",
                        "csv_path": str(csv_path),
                        "execution_mode": "windowed",
                        "destination_mode": "pending_publish",
                        "collision_policy": "suffix",
                        "window_size": 2,
                        "rows": [
                            {"row_index": 0, "status": "failed", "source_path": str(duplicate)},
                            {
                                "row_index": 1,
                                "status": "pending",
                                "source_path": str(duplicate),
                                "source_identity_v2": "duplicate-pending-v2",
                                "source_content_sha256": "2" * 64,
                                "source_content_sha256_algorithm": "sha256-full-file",
                            },
                            {
                                "row_index": 2,
                                "status": "pending",
                                "source_path": str(pending),
                                "source_identity_v2": "pending-v2",
                                "source_content_sha256": "3" * 64,
                                "source_content_sha256_algorithm": "sha256-full-file",
                            },
                            {"row_index": 3, "status": "failed", "source_path": str(failed)},
                            {"row_index": 4, "status": "pending_publish", "source_path": str(parked)},
                            {"row_index": 5, "status": "review_workspace", "source_path": str(complete)},
                        ],
                    }
                ),
                encoding="utf-8",
            )
            manifest_key = rerun_results_payload(resolved)["manifests"][0]["manifest_key"]

            error, continue_request, scoped_info = build_rerun_continue_pending_request(
                resolved,
                {"manifest_key": manifest_key, "request_id": "continue-pending-1", "confirm_continue": True},
            )

            self.assertIsNone(error)
            self.assertIsNotNone(continue_request)
            self.assertIsNotNone(scoped_info)
            self.assertEqual(continue_request["execution_mode"], "windowed")
            self.assertEqual(continue_request["destination_mode"], "pending_publish")
            self.assertEqual(continue_request["window_size"], 2)
            scoped_csv = Path(scoped_info["scoped_csv_path"])
            lines = scoped_csv.read_text(encoding="utf-8").splitlines()
            scoped_text = scoped_csv.read_text(encoding="utf-8")
            self.assertEqual(len(lines), 3)
            self.assertIn("duplicate-pending", scoped_text)
            self.assertNotIn("duplicate-failed", scoped_text)
            self.assertIn(str(pending), scoped_text)
            self.assertIn("2" * 64, scoped_text)
            self.assertIn("3" * 64, scoped_text)
            self.assertNotIn(str(failed), scoped_text)
            self.assertNotIn(str(parked), scoped_text)
            self.assertNotIn(str(complete), scoped_text)

    def test_continue_pending_rows_rejects_non_stopped_no_pending_and_missing_csv(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            resolved = _resolved(root)
            manifest_root = resolved.local_base / "RerunManifests"
            manifest_root.mkdir(parents=True)
            manifest_path = manifest_root / "rerun_manifest.json"
            manifest_path.write_text(
                json.dumps({"batch_id": "rerun", "status": "complete", "rows": [{"status": "pending", "source_path": "C:/one.mkv"}]}),
                encoding="utf-8",
            )
            manifest_key = rerun_results_payload(resolved)["manifests"][0]["manifest_key"]
            error, _continue_request, _scoped_info = build_rerun_continue_pending_request(
                resolved,
                {"manifest_key": manifest_key, "request_id": "continue-invalid-status", "confirm_continue": True},
            )
            self.assertIsNotNone(error)
            self.assertIn("rerun_manifest_not_stopped_after_current", error.errors)

            manifest_path.write_text(
                json.dumps({"batch_id": "rerun", "status": "stopped_after_current", "csv_path": str(root / "missing.csv"), "rows": [{"status": "failed", "source_path": "C:/one.mkv"}]}),
                encoding="utf-8",
            )
            error, _continue_request, _scoped_info = build_rerun_continue_pending_request(
                resolved,
                {"manifest_key": manifest_key, "request_id": "continue-no-pending", "confirm_continue": True},
            )
            self.assertIsNotNone(error)
            self.assertIn("no_pending_rerun_rows", error.warnings)

            manifest_path.write_text(
                json.dumps({"batch_id": "rerun", "status": "stopped_after_current", "csv_path": str(root / "missing.csv"), "rows": [{"status": "pending", "source_path": "C:/one.mkv"}]}),
                encoding="utf-8",
            )
            error, _continue_request, _scoped_info = build_rerun_continue_pending_request(
                resolved,
                {"manifest_key": manifest_key, "request_id": "continue-missing-csv", "confirm_continue": True},
            )
            self.assertIsNotNone(error)
            self.assertIn("rerun_source_csv_missing", error.errors)

    def test_continue_retry_exhausted_materializes_identity_preserving_recovery_csv(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            resolved = _resolved(root)
            source_dir = root / "Source"
            source_dir.mkdir(parents=True)
            exhausted = source_dir / "Exhausted.mkv"
            staged = source_dir / "Staged.mkv"
            processing = source_dir / "Processing.mkv"
            completed = source_dir / "Completed.mkv"
            unrecoverable = source_dir / "Unrecoverable.mkv"
            for item in (exhausted, staged, processing, completed, unrecoverable):
                item.write_bytes(b"media")
            csv_path = root / "rerun.csv"
            csv_path.write_text(
                "enabled,source_path,source_size,source_mtime_utc,source_identity_v2,source_content_sha256,source_content_sha256_algorithm\n"
                f"true,{exhausted},1,2026-01-01T00:00:00Z,old-exhausted,{'a' * 64},sha256-full-file\n"
                f"true,{staged},2,2026-01-02T00:00:00Z,old-staged,{'b' * 64},sha256-full-file\n"
                f"true,{processing},3,2026-01-03T00:00:00Z,old-processing,{'c' * 64},sha256-full-file\n"
                f"true,{completed},4,2026-01-04T00:00:00Z,old-completed,{'d' * 64},sha256-full-file\n"
                f"false,{unrecoverable},5,2026-01-05T00:00:00Z,old-unrecoverable,{'e' * 64},sha256-full-file\n",
                encoding="utf-8",
            )
            manifest_root = resolved.local_base / "RerunManifests"
            manifest_root.mkdir(parents=True)
            manifest_path = manifest_root / "rerun_completed_with_failures.json"
            manifest_path.write_text(
                json.dumps(
                    {
                        "batch_id": "rerun-completed-with-failures",
                        "status": "completed_with_failures",
                        "csv_path": str(csv_path),
                        "execution_mode": "one_at_a_time",
                        "destination_mode": "pending_publish",
                        "collision_policy": "suffix",
                        "rows": [
                            {
                                "row_index": 0,
                                "status": "retry_exhausted",
                                "source_path": str(exhausted),
                                "source_size": 101,
                                "source_mtime_utc": "2026-07-13T12:00:00Z",
                                "source_identity_v2": "stable-exhausted-v2",
                                "source_identity_v2_algorithm": "sample-v2",
                                "source_content_sha256": "a" * 64,
                                "source_content_sha256_algorithm": "sha256-full-file",
                            },
                            {"row_index": 1, "status": "staged", "source_path": str(staged)},
                            {"row_index": 2, "status": "processing", "source_path": str(processing)},
                            {"row_index": 3, "status": "completed", "source_path": str(completed)},
                            {
                                "row_index": 4,
                                "status": "retry_exhausted",
                                "source_path": str(unrecoverable),
                                "source_size": 105,
                                "source_mtime_utc": "2026-07-13T12:05:00Z",
                                "source_identity_v2": "stable-unrecoverable-v2",
                                "source_content_sha256": "e" * 64,
                                "source_content_sha256_algorithm": "sha256-full-file",
                            },
                        ],
                    }
                ),
                encoding="utf-8",
            )
            manifest = rerun_results_payload(resolved)["manifests"][0]
            exhausted_projection = manifest["rows"][0]
            unrecoverable_projection = manifest["rows"][4]
            retry_actions = [
                action for action in exhausted_projection["available_actions"] if action["action"] == "retry"
            ]
            self.assertEqual(retry_actions[0]["route"], "/api/rerun/continue")
            self.assertEqual(retry_actions[0]["label"], "Retry Exhausted Rows (1)")
            self.assertEqual(retry_actions[0]["scope"], "batch_retry_exhausted")
            self.assertEqual(
                retry_actions[0]["request"],
                {"manifest_key": manifest["manifest_key"], "confirm_continue": True},
            )
            self.assertTrue(retry_actions[0]["request_id_required"])
            self.assertFalse(retry_actions[0]["requires_confirmation"])
            blocked_retry = next(
                action for action in unrecoverable_projection["available_actions"] if action["action"] == "retry"
            )
            self.assertEqual(blocked_retry["route"], "")
            self.assertEqual(blocked_retry["availability"], "blocked")
            self.assertEqual(unrecoverable_projection["queue_status"], "blocked")
            self.assertEqual(unrecoverable_projection["operator_status_state"], "review")
            self.assertTrue(unrecoverable_projection["recovery_blocked_reason"])

            error, continue_request, scoped_info = build_rerun_continue_pending_request(
                resolved,
                {
                    "manifest_key": manifest["manifest_key"],
                    "request_id": "retry-exhausted-1",
                    "confirm_continue": True,
                },
            )
            self.assertIsNone(error)
            self.assertIsNotNone(continue_request)
            self.assertIsNotNone(scoped_info)
            self.assertEqual(scoped_info["recovery_scope"], "retry_exhausted")
            self.assertEqual(scoped_info["row_count"], 1)
            self.assertEqual(scoped_info["retry_exhausted_total_count"], 2)
            self.assertEqual(scoped_info["retry_exhausted_unrecoverable_count"], 1)
            self.assertEqual(manifest["retry_exhausted_count"], 2)
            self.assertEqual(manifest["recoverable_retry_exhausted_count"], 1)
            self.assertEqual(manifest["unrecoverable_retry_exhausted_count"], 1)
            self.assertEqual(manifest["retry_exhausted_action_label"], "Retry Exhausted Rows (1)")
            scoped_csv = Path(scoped_info["scoped_csv_path"])
            with scoped_csv.open("r", encoding="utf-8-sig", newline="") as handle:
                scoped_rows = list(csv.DictReader(handle))

        self.assertEqual(len(scoped_rows), 1)
        self.assertEqual(scoped_rows[0]["source_path"], str(exhausted))
        self.assertEqual(scoped_rows[0]["source_size"], "101")
        self.assertEqual(scoped_rows[0]["source_mtime_utc"], "2026-07-13T12:00:00Z")
        self.assertEqual(scoped_rows[0]["source_identity_v2"], "stable-exhausted-v2")
        self.assertEqual(scoped_rows[0]["source_content_sha256"], "a" * 64)
        self.assertEqual(scoped_rows[0]["source_content_sha256_algorithm"], "sha256-full-file")
        self.assertEqual(scoped_rows[0]["source_identity_v2_algorithm"], "sample-v2")
        scoped_text = "\n".join(",".join(row.values()) for row in scoped_rows)
        self.assertNotIn(str(staged), scoped_text)
        self.assertNotIn(str(processing), scoped_text)
        self.assertNotIn(str(completed), scoped_text)
        self.assertNotIn(str(unrecoverable), scoped_text)

    def test_continue_retry_exhausted_requires_durable_source_identity_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            resolved = _resolved(root)
            source = root / "Source" / "Exhausted.mkv"
            source.parent.mkdir(parents=True)
            source.write_bytes(b"media")
            csv_path = root / "rerun.csv"
            csv_path.write_text(
                f"enabled,source_path,source_identity_v2\ntrue,{source},legacy-sample-v2\n",
                encoding="utf-8",
            )
            manifest_root = resolved.local_base / "RerunManifests"
            manifest_root.mkdir(parents=True)
            manifest_path = manifest_root / "rerun_missing_identity.json"
            manifest_path.write_text(
                json.dumps(
                    {
                        "batch_id": "rerun-missing-identity",
                        "status": "completed_with_failures",
                        "csv_path": str(csv_path),
                        "rows": [
                            {
                                "row_index": 0,
                                "status": "retry_exhausted",
                                "source_path": str(source),
                                "source_identity_v2": "legacy-sample-v2",
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            manifest = rerun_results_payload(resolved)["manifests"][0]
            retry_action = next(
                action for action in manifest["rows"][0]["available_actions"] if action["action"] == "retry"
            )
            error, continue_request, scoped_info = build_rerun_continue_pending_request(
                resolved,
                {
                    "manifest_key": manifest["manifest_key"],
                    "request_id": "retry-missing-identity",
                    "confirm_continue": True,
                },
            )

        self.assertFalse(manifest["can_retry_exhausted"])
        self.assertEqual(retry_action["route"], "")
        self.assertIsNotNone(error)
        self.assertIn("strong", error.message.casefold())
        self.assertEqual(manifest["rows"][0]["recovery_blocked_reason_code"], "source_content_sha256_missing")
        self.assertIsNone(continue_request)
        self.assertIsNone(scoped_info)

    def test_continue_retry_exhausted_requires_full_file_sha256_algorithm(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            resolved = _resolved(root)
            source = root / "Source" / "Exhausted.mkv"
            source.parent.mkdir(parents=True)
            source.write_bytes(b"media")
            csv_path = root / "rerun.csv"
            csv_path.write_text(
                "enabled,source_path,source_identity_v2,source_content_sha256,source_content_sha256_algorithm\n"
                f"true,{source},sample-v2,{'a' * 64},sha256-sample-v2\n",
                encoding="utf-8",
            )
            manifest_root = resolved.local_base / "RerunManifests"
            manifest_root.mkdir(parents=True)
            (manifest_root / "rerun_invalid_hash_algorithm.json").write_text(
                json.dumps(
                    {
                        "batch_id": "rerun-invalid-hash-algorithm",
                        "status": "completed_with_failures",
                        "csv_path": str(csv_path),
                        "rows": [
                            {
                                "row_index": 0,
                                "status": "retry_exhausted",
                                "source_path": str(source),
                                "source_identity_v2": "sample-v2",
                                "source_content_sha256": "a" * 64,
                                "source_content_sha256_algorithm": "sha256-sample-v2",
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )

            manifest = rerun_results_payload(resolved)["manifests"][0]
            error, continue_request, scoped_info = build_rerun_continue_pending_request(
                resolved,
                {
                    "manifest_key": manifest["manifest_key"],
                    "request_id": "retry-invalid-hash-algorithm",
                    "confirm_continue": True,
                },
            )

        self.assertFalse(manifest["can_retry_exhausted"])
        self.assertEqual(
            manifest["rows"][0]["recovery_blocked_reason_code"],
            "source_content_sha256_algorithm_invalid",
        )
        self.assertIsNotNone(error)
        self.assertIsNone(continue_request)
        self.assertIsNone(scoped_info)

    def test_results_exposes_complete_local_correlation_evidence_without_frontend_inference(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            resolved = _resolved(root)
            batch_id = "rerun-correlation"
            command_id = "command-correlation"
            launch_id = "launch-correlation"
            source = root / "Source" / "Correlation.mkv"
            source.parent.mkdir(parents=True)
            source.write_bytes(b"media")
            manifest_root = resolved.local_base / "RerunManifests"
            enrollment_root = resolved.state_root / "Rerun" / "Local"
            active_jobs = resolved.state_root / "ActiveJobs"
            manifest_root.mkdir(parents=True)
            enrollment_root.mkdir(parents=True)
            active_jobs.mkdir(parents=True)
            manifest_path = manifest_root / f"{batch_id}.json"
            enrollment_path = enrollment_root / f"{batch_id}.json"
            active_job_path = active_jobs / f"{launch_id}.json"
            stdout_log = root / "rerun.stdout.log"
            stderr_log = root / "rerun.stderr.log"
            enrollment_path.write_text(
                json.dumps(
                    {
                        "batch_id": batch_id,
                        "command_id": command_id,
                        "launch_id": launch_id,
                        "manifest_path": str(manifest_path),
                        "enrollment_path": str(enrollment_path),
                        "status": "process_spawned",
                        "rows": [{"row_index": 0, "status": "process_spawned", "source_path": str(source)}],
                    }
                ),
                encoding="utf-8",
            )
            manifest_path.write_text(
                json.dumps(
                    {
                        "batch_id": batch_id,
                        "command_id": command_id,
                        "launch_id": launch_id,
                        "status": "processing",
                        "rows": [{"row_index": 0, "status": "processing", "source_path": str(source)}],
                    }
                ),
                encoding="utf-8",
            )
            active_job_path.write_text(
                json.dumps(
                    {
                        "schema_version": "desktop_active_job.v1",
                        "launch_id": launch_id,
                        "job_kind": "rerun_csv",
                        "mode": "rerun_csv",
                        "status": "active",
                        "pid": 24682,
                        "stdout_log": str(stdout_log),
                        "stderr_log": str(stderr_log),
                        "metadata": {
                            "batch_id": batch_id,
                            "command_id": command_id,
                            "enrollment_path": str(enrollment_path),
                            "manifest_path": str(manifest_path),
                        },
                    }
                ),
                encoding="utf-8",
            )
            resolved.active_jobs_path = active_jobs

            payload = rerun_results_payload(resolved)

        manifest = payload["manifests"][0]
        row = manifest["rows"][0]
        for item in (manifest, row):
            self.assertEqual(item["command_id"], command_id)
            self.assertEqual(item["launch_id"], launch_id)
            self.assertEqual(item["batch_id"], batch_id)
            self.assertEqual(item["manifest_path"], str(manifest_path))
            self.assertEqual(item["enrollment_path"], str(enrollment_path))
            self.assertEqual(item["active_jobs_key"], launch_id)
            self.assertEqual(item["active_jobs_path"], str(active_job_path))
            self.assertEqual(item["stdout_log"], str(stdout_log))
            self.assertEqual(item["stderr_log"], str(stderr_log))
            self.assertEqual(item["command_evidence_key"], command_id)
        self.assertEqual(row["evidence_links"]["active_jobs"]["path"], str(active_job_path))
        self.assertEqual(row["evidence_links"]["command_journal"]["key"], command_id)

    def test_results_projects_spawn_transition_ambiguity_as_blocked_active_work(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            resolved = _resolved(root)
            enrollment_root = resolved.state_root / "Rerun" / "Local"
            enrollment_root.mkdir(parents=True)
            source = root / "Source" / "Ambiguous.mkv"
            enrollment_path = enrollment_root / "rerun-ambiguous.json"
            enrollment_path.write_text(
                json.dumps(
                    {
                        "batch_id": "rerun-ambiguous",
                        "command_id": "command-ambiguous",
                        "launch_id": "launch-ambiguous",
                        "enrollment_path": str(enrollment_path),
                        "manifest_path": str(
                            resolved.local_base / "RerunManifests" / "rerun-ambiguous.json"
                        ),
                        "status": "spawn_transition_ambiguous",
                        "lifecycle_state": "spawn_transition_ambiguous",
                        "reason": "Spawn proof and child exit could not be verified.",
                        "operator_action_required": True,
                        "rows": [
                            {
                                "row_index": 0,
                                "status": "spawn_transition_ambiguous",
                                "lifecycle_state": "spawn_transition_ambiguous",
                                "source_path": str(source),
                                "reason": "Spawn proof and child exit could not be verified.",
                                "operator_action_required": True,
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )

            payload = rerun_results_payload(resolved)

        manifest = payload["manifests"][0]
        row = manifest["rows"][0]
        self.assertEqual(row["queue_status"], "blocked")
        self.assertEqual(row["queue_status_label"], "Child Exit Unverified")
        self.assertEqual(row["operator_status_state"], "blocked")
        self.assertFalse(row["is_terminal"])
        self.assertEqual(manifest["lifecycle_counts"]["blocked"], 1)
        self.assertEqual(manifest["lifecycle_counts"]["active"], 1)
        self.assertEqual(payload["queue_state"]["queue_status_counts"]["blocked"], 1)

    def test_results_rejects_execution_manifest_with_degraded_enrollment_correlation(self) -> None:
        for defect in ("missing_launch_id", "mismatched_command_id", "missing_enrollment_path"):
            with self.subTest(defect=defect), tempfile.TemporaryDirectory() as raw_root:
                root = Path(raw_root)
                resolved = _resolved(root)
                batch_id = "rerun-correlation-degraded"
                command_id = "command-correlation"
                launch_id = "launch-correlation"
                enrollment_root = resolved.state_root / "Rerun" / "Local"
                manifest_root = resolved.local_base / "RerunManifests"
                enrollment_root.mkdir(parents=True)
                manifest_root.mkdir(parents=True)
                enrollment_path = enrollment_root / f"{batch_id}.json"
                manifest_path = manifest_root / f"{batch_id}.json"
                enrollment_path.write_text(
                    json.dumps(
                        {
                            "batch_id": batch_id,
                            "command_id": command_id,
                            "launch_id": launch_id,
                            "enrollment_path": str(enrollment_path),
                            "manifest_path": str(manifest_path),
                            "status": "process_spawned",
                            "lifecycle_state": "process_spawned",
                            "rows": [
                                {
                                    "row_index": 0,
                                    "status": "process_spawned",
                                    "source_path": str(root / "Source" / "Movie.mkv"),
                                }
                            ],
                        }
                    ),
                    encoding="utf-8",
                )
                manifest = {
                    "batch_id": batch_id,
                    "command_id": command_id,
                    "launch_id": launch_id,
                    "enrollment_path": str(enrollment_path),
                    "status": "completed",
                    "rows": [{"row_index": 0, "status": "completed"}],
                }
                if defect == "missing_launch_id":
                    manifest.pop("launch_id")
                elif defect == "mismatched_command_id":
                    manifest["command_id"] = "different-command"
                else:
                    manifest.pop("enrollment_path")
                manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

                payload = rerun_results_payload(resolved)

            projected = payload["manifests"][0]
            self.assertEqual(projected["evidence_authority"], "backend_enrollment_manifest_correlation_degraded")
            self.assertEqual(projected["manifest_correlation_status"], "degraded")
            self.assertTrue(projected["manifest_correlation_warnings"])
            self.assertFalse(projected["manifest_available"])
            self.assertTrue(projected["execution_manifest_available"])
            self.assertEqual(projected["execution_manifest_status"], "completed")
            self.assertEqual(projected["status"], "process_spawned")
            self.assertEqual(projected["command_id"], command_id)
            self.assertEqual(projected["launch_id"], launch_id)
            self.assertEqual(projected["rows"][0]["lifecycle_state"], "process_spawned")

    def test_results_degrades_copied_v2_manifest_and_withholds_recovery_actions(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            resolved = _resolved(root)
            source = root / "Source" / "Copied.mkv"
            source.parent.mkdir(parents=True)
            source.write_bytes(b"media")
            source_stat = source.stat()
            source_mtime = datetime.fromtimestamp(source_stat.st_mtime, UTC).isoformat()
            csv_path = root / "rerun.csv"
            csv_path.write_text(
                "enabled,source_path,source_size,source_mtime_utc,source_identity_v2,source_content_sha256,source_content_sha256_algorithm\n"
                f"true,{source},{source_stat.st_size},{source_mtime},copied-v2,{'a' * 64},sha256-full-file\n",
                encoding="utf-8",
            )
            manifest_root = resolved.local_base / "RerunManifests"
            manifest_root.mkdir(parents=True)
            declared_path = manifest_root / "original-v2.json"
            copied_path = manifest_root / "copied-v2.json"
            copied_path.write_text(
                json.dumps(
                    {
                        "schema_version": "rerun_batch_manifest.v2",
                        "batch_id": "copied-v2",
                        "command_id": "copied-command",
                        "launch_id": "copied-launch",
                        "manifest_path": str(declared_path),
                        "status": "completed_with_failures",
                        "csv_path": str(csv_path),
                        "rows": [
                            {
                                "row_index": 0,
                                "status": "retry_exhausted",
                                "source_path": str(source),
                                "source_size": source_stat.st_size,
                                "source_mtime_utc": source_mtime,
                                "source_identity_v2": "copied-v2",
                                "source_content_sha256": "a" * 64,
                                "source_content_sha256_algorithm": "sha256-full-file",
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )

            projected = rerun_results_payload(resolved)["manifests"][0]

        self.assertEqual(projected["manifest_path"], str(copied_path))
        self.assertEqual(projected["manifest_correlation_status"], "degraded")
        self.assertFalse(projected["manifest_available"])
        self.assertFalse(projected["can_retry_exhausted"])
        self.assertFalse(any(action["action"] == "retry" for action in projected["available_actions"]))
        self.assertTrue(projected["manifest_correlation_warnings"])

    def test_results_degrades_rewritten_copied_v2_manifest_against_enrollment_path(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            resolved = _resolved(root)
            source = root / "Source" / "Anchored.mkv"
            source.parent.mkdir(parents=True)
            source.write_bytes(b"media")
            source_stat = source.stat()
            source_mtime = datetime.fromtimestamp(source_stat.st_mtime, UTC).isoformat()
            csv_path = root / "rerun.csv"
            csv_path.write_text(
                "enabled,source_path,source_size,source_mtime_utc,source_identity_v2,source_content_sha256,source_content_sha256_algorithm\n"
                f"true,{source},{source_stat.st_size},{source_mtime},anchored-v2,{'b' * 64},sha256-full-file\n",
                encoding="utf-8",
            )
            batch_id = "anchored-v2"
            command_id = "anchored-command"
            launch_id = "anchored-launch"
            manifest_root = resolved.local_base / "RerunManifests"
            manifest_root.mkdir(parents=True)
            original_path = manifest_root / f"{batch_id}-writer-original.json"
            copied_path = manifest_root / f"{batch_id}.json"
            enrollment_path = resolved.state_root / "Rerun" / "Local" / f"{batch_id}.json"
            enrollment_path.parent.mkdir(parents=True)
            enrollment_path.write_text(
                json.dumps(
                    {
                        "schema_version": "desktop_rerun_local_enrollment.v1",
                        "batch_id": batch_id,
                        "command_id": command_id,
                        "launch_id": launch_id,
                        "enrollment_path": str(enrollment_path),
                        "manifest_path": str(original_path),
                        "status": "completed_with_failures",
                        "lifecycle_state": "completed_with_failures",
                        "rows": [],
                    }
                ),
                encoding="utf-8",
            )
            manifest = {
                "schema_version": "rerun_batch_manifest.v2",
                "batch_id": batch_id,
                "command_id": command_id,
                "launch_id": launch_id,
                "enrollment_path": str(enrollment_path),
                "manifest_path": str(original_path),
                "status": "completed_with_failures",
                "csv_path": str(csv_path),
                "rows": [
                    {
                        "row_index": 0,
                        "status": "retry_exhausted",
                        "source_path": str(source),
                        "source_size": source_stat.st_size,
                        "source_mtime_utc": source_mtime,
                        "source_identity_v2": "anchored-v2",
                        "source_content_sha256": "b" * 64,
                        "source_content_sha256_algorithm": "sha256-full-file",
                    }
                ],
            }
            original_path.write_text(json.dumps(manifest), encoding="utf-8")
            copied_manifest = {**manifest, "manifest_path": str(copied_path)}
            copied_path.write_text(json.dumps(copied_manifest), encoding="utf-8")

            copied_projection = next(
                item
                for item in rerun_results_payload(resolved)["manifests"]
                if item["manifest_path"] == str(copied_path)
            )
            error, _request, _info = build_rerun_continue_pending_request(
                resolved,
                {
                    "manifest_key": copied_projection["manifest_key"],
                    "request_id": "rewritten-copy-request",
                    "confirm_continue": True,
                },
            )

        self.assertEqual(copied_projection["manifest_correlation_status"], "degraded")
        self.assertFalse(copied_projection["manifest_available"])
        self.assertFalse(copied_projection["can_retry_exhausted"])
        self.assertFalse(any(action["action"] == "retry" for action in copied_projection["available_actions"]))
        self.assertIsNotNone(error)
        self.assertIn("rerun_manifest_path_mismatch", error.errors)

    def test_waiting_manifest_restart_proves_active_child_or_offers_safe_identity_retry(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            resolved = _resolved(root)
            source = root / "Source" / "Waiting.mkv"
            source.parent.mkdir(parents=True)
            source.write_bytes(b"media")
            source_stat = source.stat()
            source_mtime = datetime.fromtimestamp(source_stat.st_mtime, UTC).isoformat()
            csv_path = root / "rerun.csv"
            csv_path.write_text(
                "enabled,source_path,source_size,source_mtime_utc,source_identity_v2,source_content_sha256,source_content_sha256_algorithm\n"
                f"true,{source},{source_stat.st_size},{source_mtime},waiting-source-v2,{'f' * 64},sha256-full-file\n",
                encoding="utf-8",
            )
            manifest_root = resolved.local_base / "RerunManifests"
            manifest_root.mkdir(parents=True)
            manifest_path = manifest_root / "rerun_waiting.json"
            manifest_path.write_text(
                json.dumps(
                    {
                        "batch_id": "rerun-waiting",
                        "command_id": "command-waiting",
                        "launch_id": "launch-waiting",
                        "status": "retry_scheduled",
                        "started_at": "2026-07-13T12:00:00Z",
                        "csv_path": str(csv_path),
                        "rows": [
                            {
                                "row_index": 0,
                                "status": "retry_scheduled",
                                "lifecycle_state": "retry_scheduled",
                                "source_path": str(source),
                                "source_size": source_stat.st_size,
                                "source_mtime_utc": source_mtime,
                                "source_identity_v2": "waiting-source-v2",
                                "source_content_sha256": "f" * 64,
                                "source_content_sha256_algorithm": "sha256-full-file",
                                "automatic_next_action": "Retry at the scheduled time.",
                                "available_operator_action": "Wait or request Retry now.",
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            active_jobs = resolved.local_base / "State" / "ActiveJobs"
            active_jobs.mkdir(parents=True)
            active_job_path = active_jobs / "launch-waiting.json"
            active_job = {
                "schema_version": "desktop_active_job.v1",
                "launch_id": "launch-waiting",
                "job_kind": "rerun_csv",
                "mode": "rerun_csv",
                "status": "active",
                "pid": 24682,
                "app_pid": 13579,
                "command_line": "pwsh -File Invoke-RerunCsv.ps1",
                "args": [],
                "cwd": str(root),
                "stdout_log": str(root / "rerun.stdout.log"),
                "stderr_log": str(root / "rerun.stderr.log"),
                "show_console": False,
                "metadata": {"batch_id": "rerun-waiting", "command_id": "command-waiting"},
                "launched_at": "2026-07-13T12:00:00Z",
                "last_update": "2026-07-13T12:01:00Z",
                "completed_at": "",
                "return_code": None,
            }
            active_job_path.write_text(json.dumps(active_job), encoding="utf-8")
            resolved.active_jobs_path = active_jobs

            active_payload = rerun_results_payload(resolved)
            active_manifest = active_payload["manifests"][0]
            active_retry = next(
                action
                for action in active_manifest["rows"][0]["available_actions"]
                if action["action"] == "retry"
            )
            active_error, _request, _info = build_rerun_continue_pending_request(
                resolved,
                {
                    "manifest_key": active_manifest["manifest_key"],
                    "request_id": "retry-waiting-active",
                    "confirm_continue": True,
                },
            )
            self.assertEqual(active_manifest["started_at"], "2026-07-13T12:00:00Z")
            self.assertEqual(active_manifest["waiting_restart_evidence"]["state"], "child_active")
            self.assertFalse(active_manifest["can_retry_waiting_after_restart"])
            self.assertEqual(active_retry["route"], "")
            self.assertTrue(active_manifest["rows"][0]["lifecycle_evidence"]["next"])
            self.assertIsNotNone(active_error)
            self.assertIn("rerun_waiting_child_still_active", active_error.warnings)

            active_job.update(
                {
                    "status": "orphaned",
                    "last_update": "2026-07-13T12:02:00Z",
                    "completed_at": "2026-07-13T12:02:00Z",
                    "return_code": None,
                    "reconcile_reason": "pid 24682 is no longer running",
                }
            )
            active_job_path.write_text(json.dumps(active_job), encoding="utf-8")
            restarted_resolved = _resolved(root)
            restarted_resolved.active_jobs_path = active_jobs
            recovered_payload = rerun_results_payload(restarted_resolved)
            recovered_manifest = recovered_payload["manifests"][0]
            recovered_retry = next(
                action
                for action in recovered_manifest["rows"][0]["available_actions"]
                if action["action"] == "retry"
            )
            error, continue_request, scoped_info = build_rerun_continue_pending_request(
                restarted_resolved,
                {
                    "manifest_key": recovered_manifest["manifest_key"],
                    "request_id": "retry-waiting-restarted",
                    "confirm_continue": True,
                },
            )
            if scoped_info is not None:
                with Path(scoped_info["scoped_csv_path"]).open(
                    "r", encoding="utf-8-sig", newline=""
                ) as handle:
                    scoped_rows = list(csv.DictReader(handle))
            else:
                scoped_rows = []

        self.assertEqual(recovered_manifest["waiting_restart_evidence"]["state"], "child_exit_proven")
        self.assertTrue(recovered_manifest["can_retry_waiting_after_restart"])
        self.assertEqual(recovered_retry["route"], "/api/rerun/continue")
        self.assertEqual(recovered_retry["label"], "Retry Waiting Rows (1)")
        self.assertTrue(recovered_retry["request_id_required"])
        self.assertFalse(recovered_retry["requires_confirmation"])
        self.assertIsNone(error)
        self.assertIsNotNone(continue_request)
        self.assertEqual(scoped_info["recovery_scope"], "waiting_restart")
        self.assertEqual(scoped_info["row_count"], 1)
        self.assertEqual(scoped_rows[0]["source_content_sha256"], "f" * 64)
        self.assertEqual(scoped_rows[0]["source_content_sha256_algorithm"], "sha256-full-file")

    def test_waiting_manifest_restart_rejects_partial_or_mismatched_active_job_correlation(self) -> None:
        cases = (
            "exact_v2_correlation",
            "csv_path_only",
            "batch_id_only",
            "launch_id_with_mismatched_batch_id",
            "launch_id_with_mismatched_command_id",
            "launch_id_with_mismatched_manifest_path",
            "launch_id_with_mismatched_enrollment_path",
            "launch_id_with_missing_batch_id",
            "launch_id_with_missing_command_id",
            "launch_id_with_missing_manifest_path",
            "launch_id_with_missing_enrollment_path",
        )
        for case in cases:
            with self.subTest(case=case), tempfile.TemporaryDirectory() as raw_root:
                root = Path(raw_root)
                resolved = _resolved(root)
                source = root / "Source" / "Waiting.mkv"
                source.parent.mkdir(parents=True)
                source.write_bytes(b"media")
                source_stat = source.stat()
                source_mtime = datetime.fromtimestamp(source_stat.st_mtime, UTC).isoformat()
                source_sha256 = "f" * 64
                csv_path = root / "rerun.csv"
                csv_path.write_text(
                    "enabled,source_path,source_size,source_mtime_utc,source_identity_v2,source_content_sha256,source_content_sha256_algorithm\n"
                    f"true,{source},{source_stat.st_size},{source_mtime},waiting-source-v2,{source_sha256},sha256-full-file\n",
                    encoding="utf-8",
                )
                batch_id = "rerun-waiting-exact"
                command_id = "command-waiting-exact"
                launch_id = "launch-waiting-exact"
                manifest_path = resolved.local_base / "RerunManifests" / f"{batch_id}.json"
                enrollment_path = resolved.state_root / "Rerun" / "Local" / f"{batch_id}.json"
                manifest = {
                    "schema_version": "rerun_batch_manifest.v2",
                    "batch_id": batch_id,
                    "command_id": command_id,
                    "launch_id": launch_id,
                    "manifest_path": str(manifest_path),
                    "enrollment_path": str(enrollment_path),
                    "status": "retry_scheduled",
                    "csv_path": str(csv_path),
                    "rows": [
                        {
                            "row_index": 0,
                            "status": "retry_scheduled",
                            "lifecycle_state": "retry_scheduled",
                            "source_path": str(source),
                            "source_size": source_stat.st_size,
                            "source_mtime_utc": source_mtime,
                            "source_identity_v2": "waiting-source-v2",
                            "source_content_sha256": source_sha256,
                            "source_content_sha256_algorithm": "sha256-full-file",
                        }
                    ],
                }
                active_jobs = resolved.state_root / "ActiveJobs"
                active_jobs.mkdir(parents=True)
                record_launch_id = launch_id
                metadata = {
                    "batch_id": batch_id,
                    "command_id": command_id,
                    "csv_path": str(csv_path),
                    "manifest_path": str(manifest_path),
                    "enrollment_path": str(enrollment_path),
                }
                if case == "csv_path_only":
                    record_launch_id = "other-launch"
                    metadata = {"csv_path": str(csv_path)}
                elif case == "batch_id_only":
                    record_launch_id = "other-launch"
                    metadata = {"batch_id": batch_id}
                elif case == "launch_id_with_mismatched_batch_id":
                    metadata["batch_id"] = "other-batch"
                elif case == "launch_id_with_mismatched_command_id":
                    metadata["command_id"] = "other-command"
                elif case == "launch_id_with_mismatched_manifest_path":
                    metadata["manifest_path"] = str(root / "other-manifest.json")
                elif case == "launch_id_with_mismatched_enrollment_path":
                    metadata["enrollment_path"] = str(root / "other-enrollment.json")
                elif case == "launch_id_with_missing_batch_id":
                    metadata.pop("batch_id")
                elif case == "launch_id_with_missing_command_id":
                    metadata.pop("command_id")
                elif case == "launch_id_with_missing_manifest_path":
                    metadata.pop("manifest_path")
                elif case == "launch_id_with_missing_enrollment_path":
                    metadata.pop("enrollment_path")
                active_job_path = active_jobs / f"{record_launch_id}.json"
                active_job_path.write_text(
                    json.dumps(
                        {
                            "schema_version": "desktop_active_job.v1",
                            "launch_id": record_launch_id,
                            "job_kind": "rerun_csv",
                            "mode": "rerun_csv",
                            "status": "orphaned",
                            "pid": 24682,
                            "metadata": metadata,
                            "completed_at": "2026-07-13T12:02:00Z",
                            "return_code": None,
                        }
                    ),
                    encoding="utf-8",
                )
                resolved.active_jobs_path = active_jobs

                posture = rerun_waiting_restart_posture(resolved, manifest)

            if case == "exact_v2_correlation":
                self.assertEqual(posture["state"], "child_exit_proven")
                self.assertTrue(posture["manual_retry_available"])
                self.assertEqual(posture["active_job"]["launch_id"], launch_id)
            else:
                self.assertEqual(posture["state"], "child_exit_unproven")
                self.assertFalse(posture["manual_retry_available"])
                self.assertEqual(posture["active_job"], {})

    def test_promote_to_pending_publish_writes_current_manifest_contract(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            resolved = _resolved(root)
            source = root / "Source" / "Movie.mkv"
            review_output = root / "Review" / "Movie.mkv"
            final_output = root / "Outsource" / "Movie.mkv"
            source.parent.mkdir(parents=True)
            review_output.parent.mkdir(parents=True)
            source.write_bytes(b"source-media")
            review_output.write_bytes(b"verified-output")
            review_sidecar = review_output.with_name("Movie.pipeline.json")
            review_srt = review_output.with_name("Movie.eng.srt")
            review_srt.write_text("1\n00:00:00,000 --> 00:00:01,000\nHello\n", encoding="utf-8")
            review_sidecar.write_text(
                json.dumps(
                    {
                        "schema_version": "pipeline_sidecar.v1",
                        "pipeline_version": "1.0",
                        "route": "remux",
                        "output_file": review_output.name,
                        "output_path": str(review_output),
                        "publish_state": "published",
                        "publish_transaction_id": "nested-rerun",
                        "source_identity_v2": "rerun-test-source",
                        "output_size": review_output.stat().st_size,
                        "tx3g_srt_tracks": [
                            {
                                "path": str(review_srt),
                                "file_name": review_srt.name,
                                "status": "written",
                                "language": "eng",
                                "cue_count": 1,
                            }
                        ],
                        "tx3g_srt_failures": [],
                        "bdpgs_srt_failures": [],
                        "vobsub_srt_failures": [],
                        "converted_srt_sidecar_candidates": [{"selected": True, "srt_path": str(review_srt)}],
                        "subtitle_output_reduction": [],
                        "tx3g_embedded_srt_tracks": [],
                        "bdpgs_embedded_srt_tracks": [],
                        "vobsub_embedded_srt_tracks": [],
                        "tx3g_srt_conversion_enabled": True,
                        "tx3g_external_srt_sidecars_enabled": True,
                        "drop_tx3g_after_conversion": False,
                        "bdpgs_srt_conversion_enabled": False,
                        "drop_bdpgs_after_conversion": False,
                        "vobsub_srt_conversion_enabled": False,
                        "drop_vobsub_after_conversion": False,
                        "route_plan": {"decision": "remux"},
                    }
                ),
                encoding="utf-8",
            )

            manifest_root = resolved.local_base / "RerunManifests"
            manifest_root.mkdir(parents=True)
            (manifest_root / "rerun_batch.json").write_text(
                json.dumps(
                    {
                        "batch_id": "rerun-test",
                        "status": "complete",
                        "rows": [
                            {
                                "status": "complete",
                                "source_path": str(source),
                                "verified_output_path": str(review_output),
                                "final_output_path": str(final_output),
                                "source_size": source.stat().st_size,
                                "source_mtime_utc": "2026-07-02T04:00:00Z",
                                "source_identity_v2": "rerun-test-source",
                                "source_identity_v2_algorithm": "rerun_results_test",
                                "media_kind": "movie",
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )

            row = rerun_results_payload(resolved)["rows"][0]
            dry_run = rerun_promote_dry_run(
                resolved,
                {"row_key": row["row_key"]},
            )
            fingerprint = dry_run.data["dry_run_fingerprint"]
            result = rerun_promote_to_pending_publish(
                resolved,
                {"row_key": row["row_key"], "dry_run_fingerprint": fingerprint, "confirm_promote": True},
                product_version="2026.06.04.001",
            )

            self.assertTrue(result.ok, result.message)
            self.assertFalse(review_output.exists())
            self.assertTrue(source.exists())
            payload_path = Path(result.data["pending_publish_payload_path"])
            manifest_path = Path(result.data["pending_publish_manifest_path"])
            self.assertEqual(payload_path.read_bytes(), b"verified-output")
            payload = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest = PendingPushManifest.from_mapping(payload)
            row = pending_manifest_row(manifest_path)

            self.assertEqual(manifest.pipeline_version, "1.0")
            self.assertEqual(manifest.product_version, "2026.06.04.001")
            self.assertTrue(manifest.publish_transaction_id.startswith("rerun-promote-"))
            self.assertEqual(manifest.manifest_state, "parked")
            self.assertEqual(len(manifest.sidecar_files), 1)
            self.assertEqual(Path(manifest.sidecar_files[0]["local_file"]).read_text(encoding="utf-8"), review_srt.read_text(encoding="utf-8"))
            self.assertEqual(manifest.sidecar_files[0]["server_out"], str(final_output.with_name("Movie.eng.srt")))
            self.assertEqual(manifest.tx3g_srt_tracks[0]["status"], "pending")
            self.assertEqual(manifest.tx3g_srt_tracks[0]["path"], str(final_output.with_name("Movie.eng.srt")))
            self.assertEqual(payload["converted_srt_sidecar_candidates"][0]["selected"], True)
            self.assertEqual(payload["route_plan"]["decision"], "remux")
            self.assertEqual(manifest.vobsub_srt_failures, [])
            self.assertEqual(row["state"], "parked")
            self.assertEqual(row["error"], "")

    def test_promote_rejects_outside_root_server_out_before_sidecar_copy(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            resolved = _resolved(root)
            source = root / "Source" / "Movie.mkv"
            review_output = root / "Review" / "Movie.mkv"
            outside_final = root / "OutsideFinal" / "Movie.mkv"
            source.parent.mkdir(parents=True)
            review_output.parent.mkdir(parents=True)
            source.write_bytes(b"source-media")
            review_output.write_bytes(b"verified-output")
            review_srt = review_output.with_name("Movie.eng.srt")
            review_srt.write_text("1\n00:00:00,000 --> 00:00:01,000\nHello\n", encoding="utf-8")
            review_output.with_name("Movie.pipeline.json").write_text(
                json.dumps(
                    {
                        "schema_version": "pipeline_sidecar.v1",
                        "pipeline_version": "1.0",
                        "output_size": review_output.stat().st_size,
                        "tx3g_srt_tracks": [{"path": str(review_srt), "file_name": review_srt.name, "status": "written"}],
                        "tx3g_srt_failures": [],
                        "bdpgs_srt_failures": [],
                        "vobsub_srt_failures": [],
                        "converted_srt_sidecar_candidates": [],
                        "subtitle_output_reduction": [],
                        "tx3g_embedded_srt_tracks": [],
                        "bdpgs_embedded_srt_tracks": [],
                        "vobsub_embedded_srt_tracks": [],
                    }
                ),
                encoding="utf-8",
            )

            manifest_root = resolved.local_base / "RerunManifests"
            manifest_root.mkdir(parents=True)
            (manifest_root / "rerun_batch.json").write_text(
                json.dumps(
                    {
                        "batch_id": "rerun-test",
                        "status": "complete",
                        "rows": [
                            {
                                "status": "complete",
                                "source_path": str(source),
                                "verified_output_path": str(review_output),
                                "server_out": str(outside_final),
                                "final_output_source": "csv_completed_output",
                                "final_output_source_field": "server_out",
                                "source_size": source.stat().st_size,
                                "source_identity_v2": "rerun-test-source",
                                "media_kind": "movie",
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )

            row = rerun_results_payload(resolved)["rows"][0]
            dry_run = rerun_promote_dry_run(resolved, {"row_key": row["row_key"]})
            result = rerun_promote_to_pending_publish(
                resolved,
                {"row_key": row["row_key"], "dry_run_fingerprint": "stale", "confirm_promote": True},
            )

            self.assertFalse(dry_run.ok)
            self.assertIn("rerun_final_output_outside_configured_root", dry_run.errors)
            self.assertIn("server_out", dry_run.message)
            self.assertFalse(result.ok)
            self.assertIn("rerun_final_output_outside_configured_root", result.errors)
            self.assertTrue(review_output.exists())
            self.assertTrue(review_srt.exists())
            self.assertFalse(any(resolved.pending_push_path.glob("*.sidecar*.srt")))
            self.assertFalse(any(resolved.pending_push_path.glob("*.manifest.json")))

    def test_promote_writes_pending_move_manifest_before_media_move(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            resolved = _resolved(root)
            source = root / "Source" / "Movie.mkv"
            review_output = root / "Review" / "Movie.mkv"
            final_output = root / "Outsource" / "Movie.mkv"
            source.parent.mkdir(parents=True)
            review_output.parent.mkdir(parents=True)
            source.write_bytes(b"source-media")
            review_output.write_bytes(b"verified-output")

            manifest_root = resolved.local_base / "RerunManifests"
            manifest_root.mkdir(parents=True)
            (manifest_root / "rerun_batch.json").write_text(
                json.dumps(
                    {
                        "batch_id": "rerun-test",
                        "status": "complete",
                        "rows": [
                            {
                                "status": "complete",
                                "source_path": str(source),
                                "verified_output_path": str(review_output),
                                "final_output_path": str(final_output),
                                "source_size": source.stat().st_size,
                                "source_identity_v2": "rerun-test-source",
                                "media_kind": "movie",
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )

            row = rerun_results_payload(resolved)["rows"][0]
            dry_run = rerun_promote_dry_run(resolved, {"row_key": row["row_key"]})
            with mock.patch("mediapipeline.core.processes.rerun_results.shutil.move", side_effect=OSError("move blocked")):
                result = rerun_promote_to_pending_publish(
                    resolved,
                    {
                        "row_key": row["row_key"],
                        "dry_run_fingerprint": dry_run.data["dry_run_fingerprint"],
                        "confirm_promote": True,
                    },
                )

            self.assertFalse(result.ok)
            self.assertTrue(review_output.exists())
            manifest_path = Path(result.data["pending_publish_manifest_path"])
            self.assertTrue(manifest_path.exists())
            payload = json.loads(manifest_path.read_text(encoding="utf-8"))
            self.assertEqual(payload["manifest_state"], "pending_move")

    def test_promote_suffixes_existing_pending_server_destination(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            resolved = _resolved(root)
            source = root / "Source" / "Movie.mkv"
            review_output = root / "Review" / "Movie.mkv"
            final_output = root / "Outsource" / "Movie.mkv"
            pending_root = resolved.pending_push_path
            source.parent.mkdir(parents=True)
            review_output.parent.mkdir(parents=True)
            pending_root.mkdir(parents=True)
            source.write_bytes(b"source-media")
            review_output.write_bytes(b"verified-output")
            review_srt = review_output.with_name("Movie.eng.srt")
            review_srt.write_text("1\n00:00:00,000 --> 00:00:01,000\nHello\n", encoding="utf-8")
            review_output.with_name("Movie.pipeline.json").write_text(
                json.dumps(
                    {
                        "schema_version": "pipeline_sidecar.v1",
                        "pipeline_version": "1.0",
                        "route": "remux",
                        "source_identity_v2": "rerun-test-source",
                        "output_size": review_output.stat().st_size,
                        "tx3g_srt_tracks": [{"path": str(review_srt), "file_name": review_srt.name, "status": "written"}],
                        "tx3g_srt_failures": [],
                        "bdpgs_srt_failures": [],
                        "vobsub_srt_failures": [],
                        "converted_srt_sidecar_candidates": [],
                        "subtitle_output_reduction": [],
                        "tx3g_embedded_srt_tracks": [],
                        "bdpgs_embedded_srt_tracks": [],
                        "vobsub_embedded_srt_tracks": [],
                    }
                ),
                encoding="utf-8",
            )
            (pending_root / "existing.manifest.json").write_text(
                json.dumps({"server_out": str(final_output), "local_file": str(pending_root / "existing.mkv")}),
                encoding="utf-8",
            )

            manifest_root = resolved.local_base / "RerunManifests"
            manifest_root.mkdir(parents=True)
            (manifest_root / "rerun_batch.json").write_text(
                json.dumps(
                    {
                        "batch_id": "rerun-test",
                        "status": "complete",
                        "rows": [
                            {
                                "status": "complete",
                                "source_path": str(source),
                                "verified_output_path": str(review_output),
                                "final_output_path": str(final_output),
                                "source_size": source.stat().st_size,
                                "source_identity_v2": "rerun-test-source",
                                "media_kind": "movie",
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )

            row = rerun_results_payload(resolved)["rows"][0]
            dry_run = rerun_promote_dry_run(resolved, {"row_key": row["row_key"]})
            self.assertTrue(dry_run.ok, dry_run.message)
            self.assertNotEqual(dry_run.data["server_out"], str(final_output))
            self.assertIn(".rerun-", Path(dry_run.data["server_out"]).name)

            result = rerun_promote_to_pending_publish(
                resolved,
                {"row_key": row["row_key"], "dry_run_fingerprint": dry_run.data["dry_run_fingerprint"], "confirm_promote": True},
            )

            self.assertTrue(result.ok, result.message)
            payload = json.loads(Path(result.data["pending_publish_manifest_path"]).read_text(encoding="utf-8"))
            self.assertEqual(payload["server_out"], dry_run.data["server_out"])
            self.assertEqual(result.data["requested_server_out"], str(final_output))
            self.assertIn(".rerun-", Path(payload["sidecar_files"][0]["server_out"]).name)
            server_outs = [
                json.loads(path.read_text(encoding="utf-8")).get("server_out")
                for path in pending_root.glob("*.manifest.json")
            ]
            self.assertEqual(len(server_outs), len(set(server_outs)))


if __name__ == "__main__":
    unittest.main()
