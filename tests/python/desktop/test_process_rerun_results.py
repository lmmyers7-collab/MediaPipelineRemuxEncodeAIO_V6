from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from mediapipeline.tools.paths import find_repo_root

REPO_ROOT = find_repo_root(Path(__file__))
sys.path.insert(0, str(REPO_ROOT / "src"))

from mediapipeline.core.kernel.contracts.pending_publish import PendingPushManifest  # noqa: E402
from mediapipeline.core.paths.contracts import ResolvedPaths  # noqa: E402
from mediapipeline.core.processes.rerun_results import (  # noqa: E402
    rerun_promote_dry_run,
    rerun_promote_to_pending_publish,
    rerun_results_payload,
)
from mediapipeline.core.processes.rerun_rules import AUDIO_LANGUAGE_REMEDIATION  # noqa: E402
from mediapipeline.core.processes.rerun_control import (  # noqa: E402
    build_rerun_continue_pending_request,
    request_rerun_stop_after_current,
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
            manifest_root = resolved.local_base / "RerunManifests"
            manifest_root.mkdir(parents=True)
            (manifest_root / "rerun_stopped.json").write_text(
                json.dumps(
                    {
                        "batch_id": "rerun-stopped",
                        "status": "stopped_after_current",
                        "current_chunk": 2,
                        "remaining_pending_count": 1,
                        "stop_request_id": "rerun-stop-1",
                        "stopped_at": "2026-07-03T12:05:00-04:00",
                        "rows": [
                            {"status": "review_workspace", "source_path": str(root / "done.mkv")},
                            {"status": "pending", "source_path": str(root / "pending.mkv")},
                            {"status": "failed", "source_path": str(root / "failed.mkv")},
                        ],
                    }
                ),
                encoding="utf-8",
            )

            manifest = rerun_results_payload(resolved)["manifests"][0]

            self.assertEqual(manifest["status"], "stopped_after_current")
            self.assertEqual(manifest["current_chunk"], 2)
            self.assertEqual(manifest["remaining_pending_count"], 1)
            self.assertTrue(manifest["can_continue_pending"])
            self.assertEqual(manifest["row_status_counts"]["pending"], 1)
            self.assertEqual(manifest["stop_request_id"], "rerun-stop-1")

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
                            {"status": "failed", "source_path": str(root / "failed.mkv"), "reason": "nested pipeline failed"},
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
        self.assertEqual(by_name["pending.mkv"]["queue_status_label"], "Stopped")
        self.assertEqual(by_name["active.mkv"]["queue_status_label"], "Active")
        self.assertEqual(by_name["blocked.mkv"]["queue_status_label"], "Blocked")
        self.assertEqual(by_name["warning.mkv"]["queue_status_label"], "Warning")
        self.assertEqual(by_name["failed.mkv"]["queue_status_label"], "Failed")
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
                        "source_path,audit_issue_codes",
                        f"{duplicate},duplicate-failed",
                        f"{duplicate},duplicate-pending",
                        f"{pending},pending-issue",
                        f"{failed},failed-issue",
                        f"{parked},pending-publish-issue",
                        f"{complete},complete-issue",
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
                            {"row_index": 1, "status": "pending", "source_path": str(duplicate)},
                            {"row_index": 2, "status": "pending", "source_path": str(pending)},
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
                {"manifest_key": manifest_key, "confirm_continue": True},
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
                {"manifest_key": manifest_key, "confirm_continue": True},
            )
            self.assertIsNotNone(error)
            self.assertIn("rerun_manifest_not_stopped_after_current", error.errors)

            manifest_path.write_text(
                json.dumps({"batch_id": "rerun", "status": "stopped_after_current", "csv_path": str(root / "missing.csv"), "rows": [{"status": "failed", "source_path": "C:/one.mkv"}]}),
                encoding="utf-8",
            )
            error, _continue_request, _scoped_info = build_rerun_continue_pending_request(
                resolved,
                {"manifest_key": manifest_key, "confirm_continue": True},
            )
            self.assertIsNotNone(error)
            self.assertIn("no_pending_rerun_rows", error.warnings)

            manifest_path.write_text(
                json.dumps({"batch_id": "rerun", "status": "stopped_after_current", "csv_path": str(root / "missing.csv"), "rows": [{"status": "pending", "source_path": "C:/one.mkv"}]}),
                encoding="utf-8",
            )
            error, _continue_request, _scoped_info = build_rerun_continue_pending_request(
                resolved,
                {"manifest_key": manifest_key, "confirm_continue": True},
            )
            self.assertIsNotNone(error)
            self.assertIn("rerun_source_csv_missing", error.errors)

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
