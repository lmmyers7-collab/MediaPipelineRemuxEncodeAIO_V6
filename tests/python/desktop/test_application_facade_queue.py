from __future__ import annotations

import json
import os
import sys
import tempfile
import time
import unittest
from pathlib import Path

from mediapipeline.tools.paths import find_repo_root
from unittest.mock import patch

sys.path.insert(0, str(find_repo_root(Path(__file__)) / "src"))

from mediapipeline.desktop.application import MediaPipelineApplicationFacade
from mediapipeline.core.queue.source_inventory import (
    queue_scan_status_payload,
    queue_scan_status_path,
    queue_source_inventory_path,
    write_json_artifact,
)
from mediapipeline.core.queue.policy_parts.operator_guidance import queue_row_operator_guidance
from mediapipeline.core.queue.priority_manifest import set_manifest_entry
from mediapipeline.core.queue.facade import _read_latest_rerun_manifest
from tests.python.desktop.application_facade_test_support import DummyWorkflowFacadeService, _resolved


class ApplicationFacadeQueueTests(unittest.TestCase):
    def test_queue_guidance_treats_stop_requested_runtime_as_actionable_hold(self) -> None:
        row = {
            "status": "queued",
            "source_path": r"C:\Media\Movie.mkv",
            "route_name": "remux",
            "route_reason": "already compatible",
            "runtime_outcome_status": "stopped",
            "runtime_outcome_success": False,
            "runtime_outcome_freshness_status": "fresh",
            "runtime_outcome_error_code": "STOP_REQUESTED",
            "runtime_outcome_reason": "Processing stopped by operator",
        }

        guidance = queue_row_operator_guidance(row)

        self.assertEqual(guidance["operator_status"], "Check publish state")
        self.assertEqual(guidance["operator_status_state"], "warning")
        self.assertEqual(guidance["operator_trust_state"], "review-before-launch")
        self.assertIn("Stop After Current", guidance["operator_guidance"])
        self.assertIn("Completed and Pending Publish", guidance["operator_guidance"])
        self.assertIn("runtime_outcome:stopped", guidance["review_flags"])
        self.assertNotEqual(guidance["primary_concern"], "fresh runtime failure")

    def test_queue_guidance_treats_stop_requested_pending_publish_as_waiting_for_push(self) -> None:
        row = {
            "status": "queued",
            "source_path": r"C:\Media\Movie.mkv",
            "route_name": "remux",
            "route_reason": "already compatible",
            "runtime_outcome_status": "stopped",
            "runtime_outcome_success": False,
            "runtime_outcome_freshness_status": "fresh",
            "runtime_outcome_error_code": "STOP_REQUESTED",
            "runtime_outcome_reason": "Processing stopped by operator",
            "runtime_outcome_publish_state": "parked",
            "runtime_outcome_publish_mode": "deferred",
        }

        guidance = queue_row_operator_guidance(row)

        self.assertEqual(guidance["operator_status"], "Waiting for push")
        self.assertEqual(guidance["operator_status_state"], "warning")
        self.assertEqual(guidance["operator_trust_state"], "pending-publish")
        self.assertIn("Drain Pending Publish", guidance["operator_guidance"])

    def test_queue_preview_includes_scan_status_and_source_inventory_without_snapshot(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            resolved = _resolved(root)
            resolved.state_root = root / "State"
            resolved.queue_snapshot_path = resolved.state_root / "Progress" / "queue_snapshot.json"
            status_path = queue_scan_status_path(resolved)
            inventory_path = queue_source_inventory_path(resolved)
            assert status_path is not None
            assert inventory_path is not None
            write_json_artifact(
                status_path,
                queue_scan_status_payload(
                    scan_id="scan-1",
                    status="running",
                    phase="inventory",
                    mode="inventory_then_curate",
                    message="Building fast source inventory.",
                    status_path=status_path,
                    inventory_path=inventory_path,
                    queue_snapshot_path=resolved.queue_snapshot_path,
                    inventory_count=2,
                ),
            )
            write_json_artifact(
                inventory_path,
                {
                    "schema_version": "desktop_queue_source_inventory.v1",
                    "scan_id": "scan-1",
                    "status": "inventory_complete",
                    "curation_state": "uncurated",
                    "launchable": False,
                    "row_count": 1,
                    "rows": [
                        {
                            "candidate_key": "candidate-1",
                            "source_path": str(root / "TV" / "Show" / "Show - S01E01.mkv"),
                            "relative_path": "Show\\Show - S01E01.mkv",
                            "media_kind": "tv",
                            "curation_state": "uncurated",
                            "launchable": False,
                        }
                    ],
                    "summary_lines": ["Source inventory candidates: 1."],
                    "warnings": [],
                },
            )
            facade = MediaPipelineApplicationFacade(DummyWorkflowFacadeService(root))

            preview = facade.get_queue_preview(resolved).to_mapping()

        self.assertEqual(preview["schema_version"], "desktop_queue_preview.v1")
        self.assertEqual(preview["queue_scan_status"]["schema_version"], "desktop_queue_scan_status.v1")
        self.assertEqual(preview["queue_scan_status"]["status"], "running")
        self.assertEqual(preview["queue_scan_status"]["phase"], "inventory")
        self.assertEqual(preview["source_inventory"]["schema_version"], "desktop_queue_source_inventory.v1")
        self.assertEqual(preview["source_inventory"]["row_count"], 1)
        self.assertFalse(preview["source_inventory"]["launchable"])
        self.assertEqual(preview["source_inventory"]["rows"][0]["curation_state"], "uncurated")
        self.assertIn("No queue snapshot is available yet.", "\n".join(preview["warnings"]))

    def test_queue_preview_does_not_fall_back_to_active_csv_rerun_manifest_rows(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            local_base = root / "Local"
            manifest_root = local_base / "RerunManifests"
            manifest_root.mkdir(parents=True)
            manifest_path = manifest_root / "rerun_20260630_010000_abcd1234.json"
            manifest_path.write_text(
                json.dumps(
                    {
                        "batch_id": "rerun_20260630_010000_abcd1234",
                        "created_at": "2026-06-30T01:00:00",
                        "csv_path": str(local_base / "AuditReports" / "audit_rerun.csv"),
                        "config_path": str(root / "config.psd1"),
                        "pipeline_local_base": str(local_base),
                        "output_root": str(local_base / "RerunParked"),
                        "status": "staged",
                        "dry_run": False,
                        "plan_only": False,
                        "rows": [
                            {
                                "source_path": r"\\server\share\Movies\Paprika(2006)\Paprika(2006).mkv",
                                "media_kind": "Movie",
                                "stage_mode": "copy",
                                "original_mode": "keep",
                                "return_mode": "park",
                                "stage_path": str(root / "Local_RerunWorkspace" / "RerunQueue" / "rerun_20260630_010000_abcd1234" / "Movies" / "Paprika (2006)" / "Paprika (2006).mkv"),
                                "planned_output_path": str(root / "Local_RerunWorkspace" / "RerunParked" / "rerun_20260630_010000_abcd1234" / "Output" / "Paprika (2006)" / "Paprika (2006).mkv"),
                                "status": "staged",
                                "audit_issue_codes": "image-only-subtitles",
                                "queue_item": {
                                    "queue_source": "csv_rerun",
                                    "queue_phase": "csv_rerun",
                                    "media_kind": "movie",
                                    "source_path": r"\\server\share\Movies\Paprika(2006)\Paprika(2006).mkv",
                                    "metadata": {
                                        "stage_path": str(root / "Local_RerunWorkspace" / "RerunQueue" / "rerun_20260630_010000_abcd1234" / "Movies" / "Paprika (2006)" / "Paprika (2006).mkv"),
                                        "planned_output_path": str(root / "Local_RerunWorkspace" / "RerunParked" / "rerun_20260630_010000_abcd1234" / "Output" / "Paprika (2006)" / "Paprika (2006).mkv"),
                                        "status": "pending",
                                    },
                                },
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            resolved = _resolved(root)
            resolved.local_base = local_base
            resolved.queue_snapshot_path = root / "State" / "Progress" / "missing_queue_snapshot.json"
            assert resolved.active_jobs_path is not None
            resolved.active_jobs_path.mkdir(parents=True)
            (resolved.active_jobs_path / "rerun.json").write_text(
                json.dumps(
                    {
                        "schema_version": "desktop_active_job.v1",
                        "launch_id": "rerun-1",
                        "job_kind": "rerun_csv",
                        "mode": "rerun_csv",
                        "status": "completed",
                        "pid": 1234,
                        "app_pid": 5678,
                        "command_line": "pwsh -File Invoke-RerunCsv.ps1",
                        "args": [],
                        "cwd": str(root),
                        "stdout_log": str(root / "rerun.stdout.log"),
                        "stderr_log": str(root / "rerun.stderr.log"),
                        "show_console": False,
                        "metadata": {},
                        "launched_at": "2026-06-30T01:00:00",
                        "last_update": "2026-06-30T01:01:00",
                        "completed_at": "2026-07-13T20:02:01Z",
                        "return_code": 0,
                    }
                ),
                encoding="utf-8",
            )
            facade = MediaPipelineApplicationFacade(DummyWorkflowFacadeService(root))

            preview = facade.get_queue_preview(resolved).to_mapping()

        self.assertEqual(preview["source"], str(resolved.queue_snapshot_path))
        self.assertEqual(preview["rows"], [])
        self.assertEqual(preview["normal_queue_visible_count"], 0)
        self.assertEqual(preview["dedicated_rerun_visible_count"], 0)
        self.assertEqual(preview["queue_sources"], ["normal_queue"])
        self.assertEqual(preview["rerun_correlation"], {})
        self.assertIn("No queue snapshot is available", "\n".join(preview["warnings"]))

    def test_queue_preview_does_not_revive_terminal_rerun_history_without_active_job(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            local_base = root / "LocalBase"
            manifest_root = local_base / "RerunManifests"
            manifest_root.mkdir(parents=True)
            (manifest_root / "completed-batch.json").write_text(
                json.dumps(
                    {
                        "batch_id": "completed-batch",
                        "status": "completed",
                        "rows": [{"source_path": str(root / "Movie.mkv"), "status": "completed"}],
                    }
                ),
                encoding="utf-8",
            )
            resolved = _resolved(root)
            resolved.local_base = local_base
            resolved.state_root = local_base / "State"
            resolved.queue_snapshot_path = local_base / "State" / "Progress" / "missing.json"
            facade = MediaPipelineApplicationFacade(DummyWorkflowFacadeService(root))

            preview = facade.get_queue_preview(resolved).to_mapping()

        self.assertEqual(preview["rows"], [])
        self.assertEqual(preview["source"], str(resolved.queue_snapshot_path))
        self.assertIn("No queue snapshot is available", "\n".join(preview["warnings"]))

    def test_queue_preview_keeps_waiting_rerun_enrollment_out_of_normal_queue(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            local_base = root / "LocalBase"
            state_root = local_base / "State"
            enrollment_root = state_root / "Rerun" / "Local"
            enrollment_root.mkdir(parents=True)
            expected_manifest = local_base / "RerunManifests" / "batch-waiting.json"
            source = root / "Offline" / "Movie.mkv"
            (enrollment_root / "batch-waiting.json").write_text(
                json.dumps(
                    {
                        "batch_id": "batch-waiting",
                        "command_id": "command-waiting",
                        "launch_id": "launch-waiting",
                        "status": "waiting_for_source",
                        "lifecycle_state": "waiting_for_source",
                        "manifest_path": str(expected_manifest),
                        "reason": "Configured source root is temporarily unavailable.",
                        "rows": [
                            {
                                "source_path": str(source),
                                "status": "waiting_for_source",
                                "reason": "Configured source root is temporarily unavailable.",
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            resolved = _resolved(root)
            resolved.local_base = local_base
            resolved.state_root = state_root
            resolved.queue_snapshot_path = state_root / "Progress" / "missing.json"
            facade = MediaPipelineApplicationFacade(DummyWorkflowFacadeService(root))

            preview = facade.get_queue_preview(resolved).to_mapping()

        self.assertEqual(preview["source"], str(resolved.queue_snapshot_path))
        self.assertEqual(preview["rows"], [])
        self.assertEqual(preview["queue_sources"], ["normal_queue"])
        self.assertEqual(preview["dedicated_rerun_visible_count"], 0)

    def test_queue_preview_keeps_active_csv_rerun_rows_out_of_normal_queue(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            local_base = root / "LocalBase"
            normal_source = root / "TV" / "Show" / "Show - S01E01.mkv"
            normal_source.parent.mkdir(parents=True)
            normal_source.write_bytes(b"normal")
            rerun_source = root / "Movies" / "Movie.mkv"
            rerun_source.parent.mkdir(parents=True)
            rerun_source.write_bytes(b"rerun")

            snapshot_path = local_base / "State" / "Progress" / "queue_snapshot.json"
            snapshot_path.parent.mkdir(parents=True)
            snapshot_path.write_text(
                json.dumps(
                    {
                        "schema_version": "queue_plan_snapshot.v1",
                        "produced_at": "2026-07-13T20:00:00Z",
                        "config_path": str(root / "config.psd1"),
                        "local_base": str(local_base),
                        "source_movies": str(root / "Movies"),
                        "source_tv": str(root / "TV"),
                        "outsource": str(root / "Outsource"),
                        "movie_count_total": 0,
                        "tv_count_total": 1,
                        "priority_count": 0,
                        "runnable_count": 1,
                        "rows": [
                            {
                                "global_order": 1,
                                "phase": "tv",
                                "media_kind": "tv",
                                "queue_index": 1,
                                "queue_total": 1,
                                "is_priority": False,
                                "source_path": str(normal_source),
                                "root_path": str(root / "TV"),
                                "relative_path": "Show\\Show - S01E01.mkv",
                                "display_name": normal_source.name,
                                "size_gb": 1.0,
                                "route": "remux",
                                "route_reason_code": "copy_compatible",
                                "route_reason": "already compatible",
                                "blocked_reason": "",
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )

            manifest_root = local_base / "RerunManifests"
            manifest_root.mkdir(parents=True)
            terminal_sources = [root / "History" / f"Terminal-{index}.mkv" for index in range(4)]
            terminal_manifest = manifest_root / "batch-terminal-history.json"
            terminal_manifest.write_text(
                json.dumps(
                    {
                        "batch_id": "batch-terminal-history",
                        "lifecycle_state": "terminal",
                        "status": "completed_with_failures",
                        "rows": [
                            {"source_path": str(terminal_sources[0]), "lifecycle_state": "terminal", "status": "published_replace_final"},
                            {"source_path": str(terminal_sources[1]), "lifecycle_state": "terminal", "status": "review_workspace"},
                            {"source_path": str(terminal_sources[2]), "lifecycle_state": "terminal", "status": "pending_publish"},
                            {"source_path": str(terminal_sources[3]), "lifecycle_state": "terminal", "status": "failed"},
                        ],
                    }
                ),
                encoding="utf-8",
            )
            enrollment_root = local_base / "State" / "Rerun" / "Local"
            enrollment_root.mkdir(parents=True)
            expected_manifest = manifest_root / "batch-visible.json"
            (enrollment_root / "batch-visible.json").write_text(
                json.dumps(
                    {
                        "batch_id": "batch-visible",
                        "command_id": "command-visible",
                        "launch_id": "launch-visible",
                        "created_at": "2026-07-13T20:01:00Z",
                        "status": "retry_scheduled",
                        "lifecycle_state": "retry_scheduled",
                        "manifest_path": str(expected_manifest),
                        "rows": [
                            {
                                "row_index": 0,
                                "source_path": str(rerun_source),
                                "media_kind": "movie",
                                "status": "retry_scheduled",
                                "lifecycle_state": "retry_scheduled",
                                "reason": "Configured source root is temporarily unavailable.",
                                "stage_path": str(local_base.parent / "LocalBase_RerunWorkspace" / "stage" / rerun_source.name),
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            active_jobs = local_base / "State" / "ActiveJobs"
            active_jobs.mkdir(parents=True)
            (active_jobs / "launch-visible.json").write_text(
                json.dumps(
                    {
                        "schema_version": "desktop_active_job.v1",
                        "launch_id": "launch-visible",
                        "job_kind": "rerun_csv",
                        "mode": "rerun_csv",
                        "status": "completed",
                        "pid": 1234,
                        "app_pid": 5678,
                        "command_line": "pwsh -File Invoke-RerunCsv.ps1",
                        "args": [],
                        "cwd": str(root),
                        "stdout_log": str(root / "rerun.stdout.log"),
                        "stderr_log": str(root / "rerun.stderr.log"),
                        "show_console": False,
                        "metadata": {
                            "command_id": "command-visible",
                            "batch_id": "batch-visible",
                            "enrollment_path": str(enrollment_root / "batch-visible.json"),
                            "manifest_path": str(expected_manifest),
                        },
                        "launched_at": "2026-07-13T20:01:00Z",
                        "last_update": "2026-07-13T20:02:00Z",
                        "completed_at": "2026-07-13T20:02:01Z",
                        "return_code": 0,
                    }
                ),
                encoding="utf-8",
            )
            resolved = _resolved(root)
            resolved.local_base = local_base
            resolved.state_root = local_base / "State"
            resolved.active_jobs_path = active_jobs
            resolved.queue_snapshot_path = snapshot_path
            facade = MediaPipelineApplicationFacade(DummyWorkflowFacadeService(root))

            preview = facade.get_queue_preview(resolved).to_mapping()

        sources = [str(row.get("queue_source") or "normal_queue") for row in preview["rows"]]
        self.assertEqual(sources, ["normal_queue"])
        self.assertEqual(preview["shown_row_count"], 1)
        self.assertEqual(preview["normal_queue_visible_count"], 1)
        self.assertEqual(preview["dedicated_rerun_visible_count"], 0)
        self.assertEqual(preview["queue_sources"], ["normal_queue"])
        self.assertEqual(preview["runnable_count"], 1)
        self.assertEqual(preview["rerun_correlation"], {})
        visible_paths = {str(row.get("original_source_path") or row.get("source_path") or "") for row in preview["rows"]}
        self.assertTrue(all(str(path) not in visible_paths for path in terminal_sources))
        self.assertNotIn(str(rerun_source), visible_paths)
        self.assertNotIn("dedicated CSV rerun batch", "\n".join(preview["warnings"]))

    def test_queue_authority_hides_stale_progress_when_newer_enrollment_failed(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            local_base = root / "LocalBase"
            manifest_root = local_base / "RerunManifests"
            enrollment_root = local_base / "State" / "Rerun" / "Local"
            manifest_root.mkdir(parents=True)
            enrollment_root.mkdir(parents=True)
            manifest_path = manifest_root / "batch-stale.json"
            enrollment_path = enrollment_root / "batch-stale.json"
            manifest_payload = {
                "batch_id": "batch-stale",
                "command_id": "command-stale",
                "launch_id": "launch-stale",
                "status": "processing",
                "rows": [{"row_index": 0, "status": "processing", "source_path": str(root / "Movie.mkv")}],
            }
            enrollment_payload = {
                "batch_id": "batch-stale",
                "command_id": "command-stale",
                "launch_id": "launch-stale",
                "status": "failed_before_manifest",
                "lifecycle_state": "failed_before_manifest",
                "manifest_path": str(manifest_path),
                "last_transition_at": "2026-07-14T01:00:00Z",
                "rows": [
                    {
                        "row_index": 0,
                        "status": "failed_before_manifest",
                        "lifecycle_state": "failed_before_manifest",
                        "source_path": str(root / "Movie.mkv"),
                    }
                ],
            }
            manifest_path.write_text(json.dumps(manifest_payload), encoding="utf-8")
            enrollment_path.write_text(json.dumps(enrollment_payload), encoding="utf-8")
            os.utime(manifest_path, (1, 1))
            os.utime(enrollment_path, (2, 2))
            resolved = _resolved(root)
            resolved.local_base = local_base
            resolved.state_root = local_base / "State"

            selected = _read_latest_rerun_manifest(resolved)
            manifest_after = json.loads(manifest_path.read_text(encoding="utf-8"))
            enrollment_after = json.loads(enrollment_path.read_text(encoding="utf-8"))

        self.assertIsNone(selected)
        self.assertEqual(manifest_after, manifest_payload)
        self.assertEqual(enrollment_after, enrollment_payload)

    def test_queue_preview_excludes_csv_rerun_manifest_operator_states(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            local_base = root / "Local"
            manifest_root = local_base / "RerunManifests"
            manifest_root.mkdir(parents=True)
            manifest_path = manifest_root / "rerun_20260702_010000_abcd1234.json"
            manifest_path.write_text(
                json.dumps(
                    {
                        "batch_id": "rerun_20260702_010000_abcd1234",
                        "created_at": "2026-07-02T01:00:00",
                        "csv_path": str(local_base / "AuditReports" / "audit_rerun.csv"),
                        "config_path": str(root / "config.psd1"),
                        "pipeline_local_base": str(local_base),
                        "output_root": str(local_base / "RerunParked"),
                        "rows": [
                            {"source_path": str(root / "a.mkv"), "status": "failed", "reason": "source file not found"},
                            {"source_path": str(root / "b.mkv"), "status": "pending"},
                            {"source_path": str(root / "c.mkv"), "status": "staged"},
                            {"source_path": str(root / "d.mkv"), "status": "complete"},
                            {"source_path": str(root / "e.mkv"), "status": "review_workspace", "reason": "parked output requires review"},
                            {"source_path": str(root / "f.mkv"), "status": "pending_publish", "pending_publish_manifest_path": str(root / "Pending" / "f.manifest.json")},
                            {"source_path": str(root / "g.mkv"), "status": "published_replace_final", "published_path": str(root / "Final" / "g.mkv")},
                            {"source_path": str(root / "h.mkv"), "status": "warning", "reason": "audit warning"},
                            {"source_path": str(root / "i.mkv"), "status": "stopped"},
                            {"source_path": str(root / "j.mkv"), "status": "skipped"},
                            {"source_path": str(root / "k.mkv"), "status": "review", "reason": "manual status review"},
                            {
                                "source_path": str(root / "l.mkv"),
                                "status": "spawn_transition_ambiguous",
                                "reason": "Spawn proof and child exit could not be verified.",
                            },
                        ],
                    }
                ),
                encoding="utf-8",
            )
            resolved = _resolved(root)
            resolved.local_base = local_base
            resolved.queue_snapshot_path = root / "State" / "Progress" / "missing_queue_snapshot.json"
            assert resolved.active_jobs_path is not None
            resolved.active_jobs_path.mkdir(parents=True)
            (resolved.active_jobs_path / "rerun.json").write_text(
                json.dumps(
                    {
                        "schema_version": "desktop_active_job.v1",
                        "launch_id": "rerun-1",
                        "job_kind": "rerun_csv",
                        "mode": "rerun_csv",
                        "status": "active",
                        "pid": 1234,
                        "command_line": "pwsh -File Invoke-RerunCsv.ps1",
                    }
                ),
                encoding="utf-8",
            )
            facade = MediaPipelineApplicationFacade(DummyWorkflowFacadeService(root))

            preview = facade.get_queue_preview(resolved).to_mapping()

        self.assertEqual(preview["rows"], [])
        self.assertEqual(preview["queue_sources"], ["normal_queue"])
        self.assertEqual(preview["normal_queue_visible_count"], 0)
        self.assertEqual(preview["dedicated_rerun_visible_count"], 0)
        self.assertEqual(preview["rerun_correlation"], {})

    def test_queue_preview_reads_existing_snapshot_without_dry_run(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            snapshot_path = root / "State" / "Progress" / "queue_snapshot.json"
            snapshot_path.parent.mkdir(parents=True, exist_ok=True)
            source = root / "TV" / "Show" / "Season 01" / "Show - S01E01.mkv"
            source.parent.mkdir(parents=True, exist_ok=True)
            source.write_bytes(b"media")
            snapshot_path.write_text(
                json.dumps(
                    {
                        "schema_version": "queue_plan_snapshot.v1",
                        "produced_at": "2026-05-07T21:00:00-04:00",
                        "config_path": str(root / "config.psd1"),
                        "local_base": str(root),
                        "source_movies": str(root / "Movies"),
                        "source_tv": str(root / "TV"),
                        "outsource": str(root / "Outsource"),
                        "movie_count_total": 2,
                        "tv_count_total": 1,
                        "priority_count": 1,
                        "runnable_count": 1,
                        "excluded_count": 2,
                        "excluded_row_limit": 500,
                        "excluded_rows_truncated": False,
                        "excluded_rows": [
                            {
                                "source_order": 1,
                                "reason_code": "already_processed",
                                "reason": "Already processed by completed history, sidecar state, or pending-publish index.",
                                "phase": "movie",
                                "media_kind": "movie",
                                "queue_index": 1,
                                "queue_total": 2,
                                "is_priority": True,
                                "priority_reasons": ["file"],
                                "source_path": str(root / "Movies" / "Existing Movie.mkv"),
                                "root_path": str(root / "Movies"),
                                "relative_path": "Existing Movie.mkv",
                                "display_name": "Existing Movie",
                                "size_gb": 2.0,
                                "last_write_utc": "2026-05-07T20:00:00Z",
                            },
                            {
                                "source_order": 2,
                                "reason_code": "already_processed",
                                "reason": "Already processed by completed history, sidecar state, or pending-publish index.",
                                "phase": "movie",
                                "media_kind": "movie",
                                "queue_index": 2,
                                "queue_total": 2,
                                "is_priority": False,
                                "source_path": str(root / "Movies" / "Existing Movie 2.mkv"),
                                "root_path": str(root / "Movies"),
                                "relative_path": "Existing Movie 2.mkv",
                                "display_name": "Existing Movie 2",
                                "size_gb": 3.0,
                                "last_write_utc": "2026-05-07T20:30:00Z",
                            },
                        ],
                        "rows": [
                            {
                                "global_order": 1,
                                "phase": "priority_tv",
                                "manifest_priority_level": "high",
                                "media_kind": "tv",
                                "queue_index": 1,
                                "queue_total": 1,
                                "is_priority": False,
                                "source_path": str(source),
                                "root_path": str(root / "TV"),
                                "relative_path": "Show\\Season 01\\Show - S01E01.mkv",
                                "display_name": "Show - S01E01.mkv",
                                "size_gb": 1.25,
                                "route": "remux",
                                "route_reason_code": "copy_compatible",
                                "route_reason": "already compatible",
                                "route_decision_trace": [{"code": "routing_profile_selected"}, {"code": "copy_compatible"}],
                                "estimated_bitrate_mbps": 12.5,
                                "route_size_threshold_gb": 3,
                                "route_bitrate_threshold_mbps": 18,
                                "route_threshold_mode": "compatibility_advisory",
                                "size_over_threshold": False,
                                "bitrate_over_threshold": False,
                                "blocked_reason": "",
                                "runtime_checks_deferred": True,
                                "runtime_check_codes": ["source_stability", "output_path_capability"],
                                "runtime_check_notes": [
                                    "Source stability is checked by Test-FileStable only when processing starts.",
                                    "Output path capability is checked by Test-OutputPathCapability only when processing starts.",
                                ],
                                "season_number": 1,
                                "episode_number": 1,
                                "last_write_utc": "2026-05-07T21:00:00Z",
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            old_mtime = time.time() - 7200
            os.utime(snapshot_path, (old_mtime, old_mtime))
            resolved = _resolved(root)
            resolved.queue_snapshot_path = snapshot_path
            facade = MediaPipelineApplicationFacade(DummyWorkflowFacadeService(root))

            preview = facade.get_queue_preview(resolved).to_mapping()

        self.assertEqual(preview["schema_version"], "desktop_queue_preview.v1")
        self.assertEqual(preview["produced_at"], "2026-05-07T21:00:00-04:00")
        self.assertEqual(preview["produced_freshness_status"], "stale")
        self.assertGreaterEqual(preview["produced_age_seconds"], 3600)
        self.assertEqual(preview["snapshot_file_freshness_status"], "stale")
        self.assertGreaterEqual(preview["snapshot_file_age_seconds"], 3600)
        self.assertTrue(preview["snapshot_file_mtime_utc"])
        self.assertEqual(preview["config_path"], str(root / "config.psd1"))
        self.assertEqual(preview["source_movies"], str(root / "Movies"))
        self.assertEqual(preview["source_tv"], str(root / "TV"))
        self.assertEqual(preview["source_count_total"], 3)
        self.assertEqual(preview["queue_progress"]["schema_version"], "desktop_queue_source_scan_progress.v1")
        self.assertEqual(preview["queue_progress"]["status"], "warning")
        self.assertTrue(preview["queue_progress"]["stale"])
        self.assertIn("Source candidates: 3", "\n".join(preview["queue_progress"]["summary_lines"]))
        self.assertEqual(preview["progress_bars"][0]["id"], "queue_source_scan")
        self.assertEqual(preview["progress_bars"][0]["mode"], "indeterminate")
        self.assertEqual(preview["priority_count"], 1)
        self.assertEqual(preview["runnable_count"], 1)
        self.assertEqual(preview["completed_excluded_count"], 2)
        self.assertEqual(preview["excluded_row_count"], 2)
        self.assertEqual(preview["excluded_row_limit"], 500)
        self.assertFalse(preview["excluded_rows_truncated"])
        self.assertEqual(preview["excluded_reason_counts"], {"already_processed": 2})
        self.assertEqual(preview["excluded_media_type_counts"], {"Movie": 2})
        self.assertEqual(len(preview["excluded_rows"]), 2)
        self.assertEqual(preview["blocked_row_count"], 0)
        self.assertEqual(preview["blocked_reason_code_counts"], {})
        self.assertEqual(preview["blocked_reason_counts"], {})
        self.assertEqual(preview["runtime_check_deferred_count"], 1)
        self.assertEqual(preview["runtime_check_code_counts"], {"output_path_capability": 1, "source_stability": 1})
        self.assertEqual(preview["excluded_rows"][0]["reason_code"], "already_processed")
        self.assertEqual(preview["excluded_rows"][0]["media_type"], "Movie")
        self.assertEqual(preview["excluded_rows"][0]["source_order"], 1)
        self.assertTrue(preview["excluded_rows"][0]["row_key"])
        self.assertEqual(preview["completed_collision_status"], "Stale exclusions")
        self.assertEqual(preview["completed_collision_severity"], "warning")
        self.assertTrue(preview["completed_collision_row_level_available"])
        self.assertIn("completed_or_blocked_exclusions", preview["completed_collision_flags"])
        self.assertIn("row_level_exclusions_available", preview["completed_collision_flags"])
        self.assertIn("stale_snapshot_file", preview["completed_collision_flags"])
        self.assertIn("Row-level excluded-file detail: available", "\n".join(preview["completed_collision_lines"]))
        self.assertIn("already_processed [Movie]: Existing Movie", "\n".join(preview["completed_collision_lines"]))
        self.assertIn("Mutation guardrail", "\n".join(preview["completed_collision_lines"]))
        self.assertIn("Refresh Queue before launch", preview["completed_collision_guidance"])
        self.assertEqual(preview["route_counts"], {"remux": 1})
        self.assertEqual(preview["route_reason_counts"], {"copy_compatible": 1})
        self.assertEqual(preview["operator_status_counts"], {"Ready": 1})
        self.assertEqual(preview["operator_status_state_counts"], {"warning": 1})
        self.assertEqual(preview["operator_severity_counts"], {"ok": 1})
        self.assertEqual(preview["operator_trust_state_counts"], {"launch-check-needed": 1})
        self.assertEqual(preview["phase_counts"], {"PRIORITY": 1})
        self.assertEqual(preview["media_type_counts"], {"TV": 1})
        self.assertEqual(preview["source_root_counts"], {str(root / "TV"): 1})
        self.assertEqual(preview["season_counts"], {"S01": 1})
        self.assertEqual(preview["priority_visible_count"], 1)
        self.assertEqual(preview["invalid_row_count"], 0)
        self.assertEqual(preview["total_visible_size_gb"], 1.25)
        self.assertEqual(preview["total_visible_size_text"], "1.25 GB")
        self.assertEqual(len(preview["rows"]), 1)
        self.assertEqual(preview["rows"][0]["route_name"], "remux")
        self.assertEqual(preview["rows"][0]["phase"], "PRIORITY")
        self.assertEqual(preview["rows"][0]["manifest_priority_level"], "high")
        self.assertEqual(preview["rows"][0]["route_reason_code"], "copy_compatible")
        self.assertEqual(preview["rows"][0]["operator_status"], "Ready")
        self.assertEqual(preview["rows"][0]["operator_status_state"], "warning")
        self.assertEqual(preview["rows"][0]["operator_severity"], "ok")
        self.assertEqual(preview["rows"][0]["operator_trust_state"], "launch-check-needed")
        self.assertIn("deferred until backend launch", preview["rows"][0]["primary_concern"])
        self.assertIn("final source/output validation", preview["rows"][0]["safe_next_action"])
        self.assertIn("duplicate work", preview["rows"][0]["unsafe_if_ignored"])
        self.assertIn("active_jobs", preview["rows"][0]["recommended_diagnostics_targets"])
        self.assertIn("route=remux (copy_compatible)", preview["rows"][0]["proof_summary"])
        self.assertIn("remux_route", preview["rows"][0]["review_flags"])
        self.assertIn("runtime_checks_deferred", preview["rows"][0]["review_flags"])
        self.assertIn("runtime:source_stability", preview["rows"][0]["review_flags"])
        self.assertIn("snapshot is fresh", preview["rows"][0]["operator_guidance"])
        self.assertEqual(preview["rows"][0]["route_decision_summary"], "remux (copy_compatible)")
        self.assertEqual(preview["rows"][0]["estimated_bitrate_mbps"], 12.5)
        self.assertEqual(preview["rows"][0]["route_size_threshold_gb"], 3.0)
        self.assertEqual(preview["rows"][0]["route_bitrate_threshold_mbps"], 18.0)
        self.assertEqual(preview["rows"][0]["route_threshold_mode"], "compatibility_advisory")
        self.assertIn("Route: remux", preview["rows"][0]["route_evidence_lines"])
        self.assertIn("Reason code: copy_compatible", preview["rows"][0]["route_evidence_lines"])
        self.assertIn("Route threshold mode: compatibility_advisory", preview["rows"][0]["route_evidence_lines"])
        self.assertIn("Size threshold: 3 GB; over threshold: no", preview["rows"][0]["route_evidence_lines"])
        self.assertIn("Bitrate estimate: 12.5 Mbps; threshold: 18 Mbps; over threshold: no", preview["rows"][0]["route_evidence_lines"])
        self.assertIn("Route trace: routing_profile_selected, copy_compatible", preview["rows"][0]["route_evidence_lines"])
        self.assertIn("Runtime checks deferred: source_stability, output_path_capability", preview["rows"][0]["route_evidence_lines"])
        self.assertIn("Runtime note: Source stability is checked by Test-FileStable only when processing starts.", preview["rows"][0]["route_evidence_lines"])
        self.assertIn("TV parse: show=Show; folder=Season 01; S01E01", preview["rows"][0]["route_evidence_lines"])
        self.assertEqual(preview["rows"][0]["queue_position"], "1/1")
        self.assertEqual(preview["rows"][0]["last_write_utc"], "2026-05-07T21:00:00Z")
        self.assertEqual(preview["rows"][0]["queue_index"], 1)
        self.assertTrue(preview["rows"][0]["row_key"])

    def test_queue_preview_overlays_current_manifest_on_stale_snapshot_priority(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            state_root = root / "State"
            snapshot_path = state_root / "Progress" / "queue_snapshot.json"
            snapshot_path.parent.mkdir(parents=True, exist_ok=True)
            source = root / "TV" / "Mob Psycho 100" / "S2" / "[Judas] Mob Psycho 100 - S02E05.mkv"
            source.parent.mkdir(parents=True, exist_ok=True)
            source.write_bytes(b"media")
            snapshot_path.write_text(
                json.dumps(
                    {
                        "schema_version": "queue_plan_snapshot.v1",
                        "produced_at": "2026-06-04T02:00:04+00:00",
                        "config_path": str(root / "config.psd1"),
                        "local_base": str(root),
                        "source_movies": str(root / "Movies"),
                        "source_tv": str(root / "TV"),
                        "outsource": str(root / "Outsource"),
                        "movie_count_total": 0,
                        "tv_count_total": 1,
                        "priority_count": 0,
                        "runnable_count": 1,
                        "rows": [
                            {
                                "global_order": 63,
                                "phase": "low",
                                "manifest_priority_level": "low",
                                "media_kind": "tv",
                                "queue_index": 1,
                                "queue_total": 1,
                                "is_priority": False,
                                "source_path": str(source),
                                "root_path": str(root / "TV"),
                                "relative_path": r"Mob Psycho 100\S2\[Judas] Mob Psycho 100 - S02E05.mkv",
                                "display_name": "[Judas] Mob Psycho 100 - S02E05",
                                "size_gb": 1.25,
                                "route": "remux",
                                "route_reason_code": "copy_compatible",
                                "route_reason": "already compatible",
                                "blocked_reason": "",
                                "last_write_utc": "2026-06-04T02:00:00Z",
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            resolved = _resolved(root)
            resolved.state_root = state_root
            resolved.queue_snapshot_path = snapshot_path
            resolved.priority_manifest_path = state_root / "priority_manifest.json"
            set_manifest_entry(resolved.priority_manifest_path, source, "high", "old value")
            set_manifest_entry(resolved.priority_manifest_path, source, "normal", "clear")
            facade = MediaPipelineApplicationFacade(DummyWorkflowFacadeService(root))

            preview = facade.get_queue_preview(resolved).to_mapping()

        self.assertEqual(preview["priority_count"], 0)
        self.assertEqual(preview["priority_visible_count"], 0)
        self.assertEqual(preview["phase_counts"], {"TV": 1})
        self.assertEqual(preview["rows"][0]["manifest_priority_level"], "normal")
        self.assertEqual(preview["rows"][0]["phase"], "TV")

    def test_queue_preview_explicit_normal_overrides_parent_folder_priority(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            state_root = root / "State"
            snapshot_path = state_root / "Progress" / "queue_snapshot.json"
            snapshot_path.parent.mkdir(parents=True, exist_ok=True)
            show_folder = root / "TV" / "Show"
            source = show_folder / "Season 01" / "Show - S01E01.mkv"
            source.parent.mkdir(parents=True, exist_ok=True)
            source.write_bytes(b"media")
            snapshot_path.write_text(
                json.dumps(
                    {
                        "schema_version": "queue_plan_snapshot.v1",
                        "produced_at": "2026-06-04T02:00:04+00:00",
                        "config_path": str(root / "config.psd1"),
                        "local_base": str(root),
                        "source_movies": str(root / "Movies"),
                        "source_tv": str(root / "TV"),
                        "outsource": str(root / "Outsource"),
                        "movie_count_total": 0,
                        "tv_count_total": 1,
                        "priority_count": 0,
                        "runnable_count": 1,
                        "rows": [
                            {
                                "global_order": 1,
                                "phase": "low",
                                "manifest_priority_level": "low",
                                "media_kind": "tv",
                                "queue_index": 1,
                                "queue_total": 1,
                                "is_priority": False,
                                "source_path": str(source),
                                "root_path": str(root / "TV"),
                                "relative_path": r"Show\Season 01\Show - S01E01.mkv",
                                "display_name": "Show - S01E01",
                                "size_gb": 1.25,
                                "route": "remux",
                                "route_reason_code": "copy_compatible",
                                "route_reason": "already compatible",
                                "blocked_reason": "",
                                "last_write_utc": "2026-06-04T02:00:00Z",
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            resolved = _resolved(root)
            resolved.state_root = state_root
            resolved.queue_snapshot_path = snapshot_path
            resolved.priority_manifest_path = state_root / "priority_manifest.json"
            set_manifest_entry(resolved.priority_manifest_path, show_folder, "low", "folder low")
            set_manifest_entry(resolved.priority_manifest_path, source, "normal", "file normal")
            facade = MediaPipelineApplicationFacade(DummyWorkflowFacadeService(root))

            preview = facade.get_queue_preview(resolved).to_mapping()

        self.assertEqual(preview["priority_visible_count"], 0)
        self.assertEqual(preview["phase_counts"], {"TV": 1})
        self.assertEqual(preview["rows"][0]["manifest_priority_level"], "normal")
        self.assertEqual(preview["rows"][0]["phase"], "TV")

    def test_queue_preview_preserves_filesystem_priority_as_normal_manifest_level(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            state_root = root / "State"
            snapshot_path = state_root / "Progress" / "queue_snapshot.json"
            snapshot_path.parent.mkdir(parents=True, exist_ok=True)
            source = root / "Movies" / "! Movie.mkv"
            source.parent.mkdir(parents=True, exist_ok=True)
            source.write_bytes(b"media")
            snapshot_path.write_text(
                json.dumps(
                    {
                        "schema_version": "queue_plan_snapshot.v1",
                        "produced_at": "2026-06-04T02:00:04+00:00",
                        "config_path": str(root / "config.psd1"),
                        "local_base": str(root),
                        "source_movies": str(root / "Movies"),
                        "source_tv": str(root / "TV"),
                        "outsource": str(root / "Outsource"),
                        "movie_count_total": 1,
                        "tv_count_total": 0,
                        "priority_count": 1,
                        "runnable_count": 1,
                        "rows": [
                            {
                                "global_order": 1,
                                "phase": "priority_movie",
                                "manifest_priority_level": "high",
                                "media_kind": "movie",
                                "queue_index": 1,
                                "queue_total": 1,
                                "is_priority": True,
                                "priority_reasons": ["file"],
                                "source_path": str(source),
                                "root_path": str(root / "Movies"),
                                "relative_path": "! Movie.mkv",
                                "display_name": "Movie",
                                "size_gb": 1.25,
                                "route": "remux",
                                "route_reason_code": "copy_compatible",
                                "route_reason": "already compatible",
                                "blocked_reason": "",
                                "last_write_utc": "2026-06-04T02:00:00Z",
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            resolved = _resolved(root)
            resolved.state_root = state_root
            resolved.queue_snapshot_path = snapshot_path
            resolved.priority_manifest_path = state_root / "priority_manifest.json"
            facade = MediaPipelineApplicationFacade(DummyWorkflowFacadeService(root))

            preview = facade.get_queue_preview(resolved).to_mapping()

        self.assertEqual(preview["priority_count"], 1)
        self.assertEqual(preview["priority_visible_count"], 1)
        self.assertEqual(preview["phase_counts"], {"PRIORITY": 1})
        self.assertEqual(preview["rows"][0]["manifest_priority_level"], "normal")
        self.assertEqual(preview["rows"][0]["phase"], "PRIORITY")
        self.assertTrue(preview["rows"][0]["is_priority"])

    def test_queue_preview_blocks_when_priority_manifest_is_corrupt(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            state_root = root / "State"
            snapshot_path = state_root / "Progress" / "queue_snapshot.json"
            snapshot_path.parent.mkdir(parents=True, exist_ok=True)
            source = root / "Movies" / "Movie.mkv"
            source.parent.mkdir(parents=True, exist_ok=True)
            source.write_bytes(b"media")
            snapshot_path.write_text(
                json.dumps(
                    {
                        "schema_version": "queue_plan_snapshot.v1",
                        "produced_at": "2026-06-18T00:00:00+00:00",
                        "source_movies": str(root / "Movies"),
                        "source_tv": str(root / "TV"),
                        "movie_count_total": 1,
                        "tv_count_total": 0,
                        "priority_count": 0,
                        "runnable_count": 1,
                        "rows": [
                            {
                                "global_order": 1,
                                "phase": "movie",
                                "media_kind": "movie",
                                "source_path": str(source),
                                "root_path": str(root / "Movies"),
                                "relative_path": "Movie.mkv",
                                "display_name": "Movie",
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            resolved = _resolved(root)
            resolved.state_root = state_root
            resolved.queue_snapshot_path = snapshot_path
            resolved.priority_manifest_path = state_root / "priority_manifest.json"
            resolved.priority_manifest_path.write_text("{not-json", encoding="utf-8")
            facade = MediaPipelineApplicationFacade(DummyWorkflowFacadeService(root))

            preview = facade.get_queue_preview(resolved).to_mapping()

        self.assertEqual(preview["queue_progress"]["status"], "blocked")
        self.assertEqual(preview["rows"], [])
        self.assertIn("priority manifest could not be read", "\n".join(preview["warnings"]).lower())

    def test_queue_preview_loads_file_override_manifest_once_for_row_annotations(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            source_one = root / "TV" / "Show" / "Season 01" / "Show - S01E01.mkv"
            source_two = root / "TV" / "Show" / "Season 01" / "Show - S01E02.mkv"
            source_one.parent.mkdir(parents=True, exist_ok=True)
            source_one.write_bytes(b"one")
            source_two.write_bytes(b"two")
            snapshot_path = root / "State" / "Progress" / "queue_snapshot.json"
            snapshot_path.parent.mkdir(parents=True, exist_ok=True)
            rows = []
            for index, source in enumerate([source_one, source_two], start=1):
                rows.append(
                    {
                        "global_order": index,
                        "phase": "tv",
                        "media_kind": "tv",
                        "queue_index": index,
                        "queue_total": 2,
                        "is_priority": False,
                        "source_path": str(source),
                        "root_path": str(root / "TV"),
                        "relative_path": source.name,
                        "display_name": source.name,
                        "size_gb": 1.0,
                        "route": "remux",
                        "route_reason": "already compatible",
                        "blocked_reason": "",
                        "season_number": 1,
                        "episode_number": index,
                        "last_write_utc": "2026-05-07T21:00:00Z",
                    }
                )
            snapshot_path.write_text(
                json.dumps(
                    {
                        "schema_version": "queue_plan_snapshot.v1",
                        "produced_at": "2026-05-07T21:00:00-04:00",
                        "config_path": str(root / "config.psd1"),
                        "local_base": str(root),
                        "source_movies": str(root / "Movies"),
                        "source_tv": str(root / "TV"),
                        "outsource": str(root / "Outsource"),
                        "movie_count_total": 0,
                        "tv_count_total": 2,
                        "priority_count": 0,
                        "runnable_count": 2,
                        "excluded_count": 0,
                        "excluded_row_limit": 500,
                        "excluded_rows_truncated": False,
                        "excluded_rows": [],
                        "rows": rows,
                    }
                ),
                encoding="utf-8",
            )
            resolved = _resolved(root)
            resolved.queue_snapshot_path = snapshot_path
            resolved.file_overrides_path = root / "State" / "file_overrides.json"
            manifest = {
                "version": 1,
                "entries": {str(source_one).replace("\\", "/").lower(): {"audio": {"maxChannels": 6}}},
            }
            facade = MediaPipelineApplicationFacade(DummyWorkflowFacadeService(root))

            with patch("mediapipeline.core.queue.facade.read_file_overrides", return_value=manifest) as read_manifest:
                preview = facade.get_queue_preview(resolved).to_mapping()

        read_manifest.assert_called_once_with(resolved.file_overrides_path)
        self.assertTrue(preview["rows"][0]["has_file_override"])
        self.assertEqual(preview["rows"][0]["file_override_scope"], "file")
        self.assertFalse(preview["rows"][1]["has_file_override"])

    def test_queue_preview_reports_visible_blocked_rows_separately_from_exclusions(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            snapshot_path = root / "State" / "Progress" / "queue_snapshot.json"
            snapshot_path.parent.mkdir(parents=True, exist_ok=True)
            source = root / "TV" / "Show" / "Show Episode One.mkv"
            source.parent.mkdir(parents=True, exist_ok=True)
            source.write_bytes(b"media")
            snapshot_path.write_text(
                json.dumps(
                    {
                        "schema_version": "queue_plan_snapshot.v1",
                        "produced_at": "2026-05-07T21:00:00-04:00",
                        "source_tv": str(root / "TV"),
                        "movie_count_total": 0,
                        "tv_count_total": 1,
                        "priority_count": 0,
                        "runnable_count": 1,
                        "rows": [
                            {
                                "global_order": 1,
                                "phase": "tv",
                                "media_kind": "tv",
                                "queue_index": 1,
                                "queue_total": 1,
                                "is_priority": False,
                                "source_path": str(source),
                                "root_path": str(root / "TV"),
                                "relative_path": "Show\\Show Episode One.mkv",
                                "display_name": "Show Episode One.mkv",
                                "size_gb": 1.0,
                                "route": "",
                                "route_reason_code": "",
                                "route_reason": "",
                                "blocked_reason_code": "tv_parse_unreliable",
                                "blocked_reason": "tv-parse: missing season/episode",
                                "season_number": 0,
                                "episode_number": 0,
                                "last_write_utc": "2026-05-07T21:00:00Z",
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            resolved = _resolved(root)
            resolved.queue_snapshot_path = snapshot_path
            facade = MediaPipelineApplicationFacade(DummyWorkflowFacadeService(root))

            preview = facade.get_queue_preview(resolved).to_mapping()

        self.assertEqual(preview["completed_excluded_count"], 0)
        self.assertEqual(preview["blocked_row_count"], 1)
        self.assertEqual(preview["blocked_reason_code_counts"], {"tv_parse_unreliable": 1})
        self.assertEqual(preview["blocked_reason_counts"], {"tv-parse: missing season/episode": 1})
        self.assertEqual(preview["runtime_check_deferred_count"], 0)
        self.assertEqual(preview["runtime_check_code_counts"], {})
        self.assertEqual(preview["operator_status_counts"], {"Blocked": 1})
        self.assertEqual(preview["operator_status_state_counts"], {"blocked": 1})
        self.assertEqual(preview["operator_severity_counts"], {"warning": 1})
        self.assertEqual(preview["operator_trust_state_counts"], {"blocked": 1})
        self.assertEqual(preview["rows"][0]["operator_status"], "Blocked")
        self.assertEqual(preview["rows"][0]["operator_status_state"], "blocked")
        self.assertEqual(preview["rows"][0]["operator_trust_state"], "blocked")
        self.assertIn("tv_parse_unreliable", preview["rows"][0]["primary_concern"])
        self.assertIn("blocked:tv_parse_unreliable", preview["rows"][0]["review_flags"])
        self.assertIn("Blocked reason code: tv_parse_unreliable", preview["rows"][0]["route_evidence_lines"])
        self.assertIn("Blocked reason: tv-parse: missing season/episode", preview["rows"][0]["route_evidence_lines"])

    def test_queue_preview_correlates_recent_runtime_outcomes_by_exact_source_path(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            snapshot_path = root / "State" / "Progress" / "queue_snapshot.json"
            event_file = root / "State" / "Progress" / "pipeline_events.jsonl"
            snapshot_path.parent.mkdir(parents=True, exist_ok=True)
            source_failed = root / "TV" / "Show" / "Season 01" / "Show - S01E01.mkv"
            source_stale = root / "TV" / "Show" / "Season 01" / "Show - S01E02.mkv"
            source_completed = root / "TV" / "Show" / "Season 01" / "Show - S01E03.mkv"
            source_failed.parent.mkdir(parents=True, exist_ok=True)
            source_failed.write_bytes(b"media")
            source_stale.write_bytes(b"media")
            source_completed.write_bytes(b"media")
            snapshot_path.write_text(
                json.dumps(
                    {
                        "schema_version": "queue_plan_snapshot.v1",
                        "produced_at": "2026-05-07T21:00:00-04:00",
                        "source_tv": str(root / "TV"),
                        "movie_count_total": 0,
                        "tv_count_total": 3,
                        "priority_count": 0,
                        "runnable_count": 3,
                        "rows": [
                            {
                                "global_order": 1,
                                "phase": "tv",
                                "media_kind": "tv",
                                "queue_index": 1,
                                "queue_total": 2,
                                "is_priority": False,
                                "source_path": str(source_failed),
                                "root_path": str(root / "TV"),
                                "relative_path": "Show\\Season 01\\Show - S01E01.mkv",
                                "display_name": "Show - S01E01.mkv",
                                "size_gb": 1.0,
                                "route": "remux",
                                "route_reason_code": "copy_compatible",
                                "route_reason": "already compatible",
                                "blocked_reason": "",
                                "season_number": 1,
                                "episode_number": 1,
                            },
                            {
                                "global_order": 2,
                                "phase": "tv",
                                "media_kind": "tv",
                                "queue_index": 2,
                                "queue_total": 2,
                                "is_priority": False,
                                "source_path": str(source_stale),
                                "root_path": str(root / "TV"),
                                "relative_path": "Show\\Season 01\\Show - S01E02.mkv",
                                "display_name": "Show - S01E02.mkv",
                                "size_gb": 1.0,
                                "route": "remux",
                                "route_reason_code": "copy_compatible",
                                "route_reason": "already compatible",
                                "blocked_reason": "",
                                "season_number": 1,
                                "episode_number": 2,
                            },
                            {
                                "global_order": 3,
                                "phase": "tv",
                                "media_kind": "tv",
                                "queue_index": 3,
                                "queue_total": 3,
                                "is_priority": False,
                                "source_path": str(source_completed),
                                "root_path": str(root / "TV"),
                                "relative_path": "Show\\Season 01\\Show - S01E03.mkv",
                                "display_name": "Show - S01E03.mkv",
                                "size_gb": 1.0,
                                "route": "remux",
                                "route_reason_code": "copy_compatible",
                                "route_reason": "already compatible",
                                "blocked_reason": "",
                                "season_number": 1,
                                "episode_number": 3,
                            },
                        ],
                    }
                ),
                encoding="utf-8",
            )
            events = [
                {
                    "schema_version": "pipeline_event.v1",
                    "event_id": "evt-other",
                    "event_type": "job_completed",
                    "timestamp": "2999-01-01T00:00:00Z",
                    "created_at": "2999-01-01T00:00:00Z",
                    "stage": "completed",
                    "route": "remux",
                    "status": "succeeded",
                    "source_path": str(root / "TV" / "Show" / "Season 01" / "Other.mkv"),
                    "data": {"success": True, "completion_status": "processed"},
                },
                {
                    "schema_version": "pipeline_event.v1",
                    "event_id": "evt-failed",
                    "event_type": "job_completed",
                    "timestamp": "2999-01-01T00:00:00Z",
                    "created_at": "2999-01-01T00:00:00Z",
                    "stage": "skipped",
                    "route": "remux",
                    "status": "failed",
                    "source_path": str(source_failed),
                    "data": {
                        "success": False,
                        "completion_status": "skipped",
                        "queue_terminal": True,
                        "retryable": False,
                        "reason": "Source is still changing.",
                        "error_code": "SOURCE_STILL_WRITING",
                        "route": "remux",
                    },
                },
                {
                    "schema_version": "pipeline_event.v1",
                    "event_id": "evt-stale",
                    "event_type": "job_completed",
                    "timestamp": "2000-01-01T00:00:00Z",
                    "created_at": "2000-01-01T00:00:00Z",
                    "stage": "completed",
                    "route": "remux",
                    "status": "succeeded",
                    "source_path": str(source_stale),
                    "data": {
                        "success": True,
                        "completion_status": "processed",
                        "publish_state": "published",
                        "publish_mode": "direct",
                        "output_path": str(root / "Outsource" / "Show - S01E02.mkv"),
                    },
                },
                {
                    "schema_version": "pipeline_event.v1",
                    "event_id": "evt-completed",
                    "event_type": "job_completed",
                    "timestamp": "2999-01-01T00:00:00Z",
                    "created_at": "2999-01-01T00:00:00Z",
                    "stage": "completed",
                    "route": "remux",
                    "status": "succeeded",
                    "source_path": str(source_completed),
                    "data": {
                        "success": True,
                        "completion_status": "processed",
                        "publish_state": "published",
                        "publish_mode": "direct",
                        "output_path": str(root / "Outsource" / "Show - S01E03.mkv"),
                    },
                },
            ]
            event_file.write_text("\n".join(json.dumps(event) for event in events), encoding="utf-8")
            service = DummyWorkflowFacadeService(root)
            service.read_pipeline_events_tail = lambda _resolved, line_count=300: events  # type: ignore[method-assign]
            facade = MediaPipelineApplicationFacade(service)
            resolved = _resolved(root)
            resolved.queue_snapshot_path = snapshot_path
            resolved.event_file = event_file

            preview = facade.get_queue_preview(resolved).to_mapping()

        self.assertEqual(preview["runtime_outcome_source"], str(event_file))
        self.assertEqual(preview["runtime_outcome_event_count"], 4)
        self.assertEqual(preview["runtime_outcome_match_count"], 3)
        self.assertEqual(preview["runtime_outcome_status_counts"], {"skipped": 1, "succeeded": 2})
        self.assertEqual(preview["runtime_outcome_error_code_counts"], {"SOURCE_STILL_WRITING": 1, "unknown": 2})
        self.assertEqual(preview["runtime_outcome_event_type_counts"], {"job_completed": 3})
        self.assertEqual(preview["runtime_outcome_freshness_counts"], {"fresh": 2, "stale": 1})
        self.assertEqual(preview["operator_status_counts"], {"Ready": 1, "Recent runtime failure": 1, "Recently completed": 1})
        self.assertEqual(preview["operator_status_state_counts"], {"warning": 3})
        self.assertEqual(preview["operator_trust_state_counts"], {"ready-looking": 1, "review-before-launch": 2})
        self.assertEqual(preview["rows"][0]["runtime_outcome_status"], "skipped")
        self.assertEqual(preview["rows"][0]["runtime_outcome_error_code"], "SOURCE_STILL_WRITING")
        self.assertEqual(preview["rows"][0]["operator_status"], "Recent runtime failure")
        self.assertEqual(preview["rows"][0]["operator_status_state"], "warning")
        self.assertEqual(preview["rows"][0]["operator_trust_state"], "review-before-launch")
        self.assertIn("SOURCE_STILL_WRITING", preview["rows"][0]["primary_concern"])
        self.assertIn("runtime_outcome:skipped", preview["rows"][0]["review_flags"])
        self.assertIn("runtime_error:SOURCE_STILL_WRITING", preview["rows"][0]["review_flags"])
        self.assertIn("Last runtime outcome: skipped", "\n".join(preview["rows"][0]["route_evidence_lines"]))
        self.assertIn("Runtime error code: SOURCE_STILL_WRITING", preview["rows"][0]["route_evidence_lines"])
        self.assertEqual(preview["rows"][1]["runtime_outcome_status"], "succeeded")
        self.assertEqual(preview["rows"][1]["runtime_outcome_freshness_status"], "stale")
        self.assertEqual(preview["rows"][1]["operator_status"], "Ready")
        self.assertEqual(preview["rows"][1]["operator_status_state"], "warning")
        self.assertEqual(preview["rows"][1]["operator_trust_state"], "ready-looking")
        self.assertIn("runtime_outcome_stale", preview["rows"][1]["review_flags"])
        self.assertEqual(preview["rows"][2]["runtime_outcome_status"], "succeeded")
        self.assertEqual(preview["rows"][2]["runtime_outcome_freshness_status"], "fresh")
        self.assertEqual(preview["rows"][2]["operator_status"], "Recently completed")
        self.assertEqual(preview["rows"][2]["operator_status_state"], "warning")
        self.assertEqual(preview["rows"][2]["operator_trust_state"], "review-before-launch")
        self.assertIn("runtime_outcome:succeeded", preview["rows"][2]["review_flags"])
        self.assertIn("Last runtime outcome: succeeded", "\n".join(preview["rows"][2]["route_evidence_lines"]))

    def test_queue_open_uses_backend_snapshot_row_key_not_frontend_path(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            source = root / "TV" / "Show" / "Season 01" / "Show - S01E01.mkv"
            source.parent.mkdir(parents=True)
            source.write_bytes(b"media")
            route_less_source = root / "TV" / "Show" / "Season 01" / "Show - S01E12v2.mkv"
            route_less_source.write_bytes(b"media")
            excluded_source = root / "Movies" / "Already There.mkv"
            excluded_source.parent.mkdir(parents=True)
            excluded_source.write_bytes(b"media")
            source_root = root / "TV"
            movie_root = root / "Movies"
            snapshot_path = root / "State" / "Progress" / "queue_snapshot.json"
            snapshot_path.parent.mkdir(parents=True)
            snapshot_path.write_text(
                json.dumps(
                    {
                        "schema_version": "queue_plan_snapshot.v1",
                        "produced_at": "2026-05-07T21:00:00-04:00",
                        "config_path": str(root / "config.psd1"),
                        "local_base": str(root / "Scratch"),
                        "source_movies": str(movie_root),
                        "source_tv": str(source_root),
                        "outsource": str(root / "Outsource"),
                        "movie_count_total": 1,
                        "tv_count_total": 1,
                        "priority_count": 0,
                        "runnable_count": 1,
                        "excluded_count": 1,
                        "excluded_row_limit": 500,
                        "excluded_rows": [
                            {
                                "source_order": 1,
                                "reason_code": "already_processed",
                                "reason": "Already processed by completed history, sidecar state, or pending-publish index.",
                                "phase": "movie",
                                "media_kind": "movie",
                                "queue_index": 1,
                                "queue_total": 1,
                                "is_priority": False,
                                "source_path": str(excluded_source),
                                "root_path": str(movie_root),
                                "relative_path": "Already There.mkv",
                                "display_name": "Already There",
                                "size_gb": 1.0,
                                "last_write_utc": "2026-05-07T20:00:00Z",
                            }
                        ],
                        "rows": [
                            {
                                "global_order": 1,
                                "phase": "tv",
                                "media_kind": "tv",
                                "queue_index": 1,
                                "queue_total": 1,
                                "is_priority": False,
                                "source_path": str(source),
                                "root_path": str(source_root),
                                "relative_path": "Show\\Season 01\\Show - S01E01.mkv",
                                "display_name": "Show - S01E01.mkv",
                                "size_gb": 1.25,
                                "route": "remux",
                                "route_reason_code": "copy_compatible",
                                "route_reason": "already compatible",
                                "blocked_reason": "",
                                "season_number": 1,
                                "episode_number": 1,
                                "last_write_utc": "2026-05-07T21:00:00Z",
                            },
                            {
                                "global_order": 2,
                                "phase": "tv",
                                "media_kind": "tv",
                                "queue_index": 2,
                                "queue_total": 2,
                                "is_priority": False,
                                "source_path": str(route_less_source),
                                "root_path": str(source_root),
                                "relative_path": "Show\\Season 01\\Show - S01E12v2.mkv",
                                "display_name": "Show - S01E12v2.mkv",
                                "size_gb": 1.25,
                                "route": "",
                                "route_reason_code": "tv_parse_unreliable",
                                "route_reason": "TV parse is unreliable.",
                                "blocked_reason": "TV parse is unreliable.",
                                "season_number": 1,
                                "episode_number": 0,
                                "last_write_utc": "2026-05-07T21:00:00Z",
                            },
                        ],
                    }
                ),
                encoding="utf-8",
            )
            service = DummyWorkflowFacadeService(root)
            facade = MediaPipelineApplicationFacade(service)
            resolved = _resolved(root)
            resolved.queue_snapshot_path = snapshot_path

            preview = facade.get_queue_preview(resolved)
            row_key = preview.rows[0]["row_key"]
            route_less_row_key = preview.rows[1]["row_key"]
            excluded_row_key = preview.excluded_rows[0]["row_key"]
            opened = facade.open_queue_location(resolved, {"row_key": row_key, "target": "source_folder"})
            opened_route_less = facade.open_queue_location(resolved, {"row_key": route_less_row_key, "target": "source_file"})
            opened_excluded = facade.open_queue_location(resolved, {"row_key": excluded_row_key, "row_scope": "excluded", "target": "source_root"})
            rejected = facade.open_queue_location(resolved, {"row_key": row_key, "target": str(root / "secret.txt")})
            rejected_scope = facade.open_queue_location(resolved, {"row_key": excluded_row_key, "row_scope": "secret", "target": "source_file"})
            missing = facade.open_queue_location(resolved, {"row_key": "not-a-row", "target": "source_file"})

        self.assertTrue(opened.ok)
        self.assertEqual(opened.command, "queue.open")
        self.assertEqual(opened.data["target"], "source_folder")
        self.assertEqual(opened.data["row_scope"], "runnable")
        self.assertEqual(opened.data["path"], str(source.parent))
        self.assertTrue(route_less_row_key.endswith("\x1f"))
        self.assertTrue(opened_route_less.ok)
        self.assertEqual(opened_route_less.data["target"], "source_file")
        self.assertEqual(opened_route_less.data["path"], str(route_less_source))
        self.assertTrue(opened_excluded.ok)
        self.assertEqual(opened_excluded.data["target"], "source_root")
        self.assertEqual(opened_excluded.data["row_scope"], "excluded")
        self.assertEqual(opened_excluded.data["path"], str(movie_root))
        self.assertEqual(service.opened_paths, [source.parent, route_less_source, movie_root])
        self.assertFalse(rejected.ok)
        self.assertIn("not allowed", rejected.message)
        self.assertFalse(rejected_scope.ok)
        self.assertIn("scope is not allowed", rejected_scope.message)
        self.assertFalse(missing.ok)
        self.assertIn("no longer available", missing.message)
