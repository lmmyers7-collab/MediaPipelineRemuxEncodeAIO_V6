from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from mediapipeline_desktop_app.application import MediaPipelineApplicationFacade
from mediapipeline_desktop_app.models import Snapshot
from DesktopApp.tests.test_application_facade import DummyFacadeService, _resolved


class ApplicationFacadeSnapshotTests(unittest.TestCase):
    def test_facade_snapshot_and_diagnostics_do_not_require_tk_root(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            service = DummyFacadeService(root)
            facade = MediaPipelineApplicationFacade(service, app_version="v5-test")
            resolved = _resolved(root)
            assert resolved.active_jobs_path is not None
            resolved.active_jobs_path.mkdir(parents=True, exist_ok=True)
            (resolved.active_jobs_path / "launch.json").write_text(
                json.dumps(
                    {
                        "schema_version": "desktop_active_job.v1",
                        "launch_id": "launch-1",
                        "job_kind": "pipeline",
                        "mode": "once",
                        "status": "active",
                        "pid": 1234,
                        "args": [],
                        "metadata": {},
                        "launched_at": "2026-05-07T21:00:00-04:00",
                    }
                ),
                encoding="utf-8",
            )

            snapshot = facade.get_snapshot(resolved)
            diagnostics = facade.get_diagnostics_for_resolved(resolved)

        self.assertEqual(snapshot.pipeline_state, "processing")
        self.assertEqual(snapshot.counts["queue_total"], 5)
        self.assertEqual(snapshot.latest_paths["latest_failure_json"], str(root / "failures.json"))
        self.assertTrue(any(row["id"] == "current_stage" for row in snapshot.progress_bars))
        run_total = next(row for row in snapshot.progress_bars if row["id"] == "run_total")
        self.assertEqual(run_total["mode"], "determinate")
        self.assertEqual(run_total["percent"], 40.0)
        self.assertEqual(run_total["source"], "pipeline_progress.json")
        self.assertEqual(snapshot.worker_progress["schema_version"], "desktop_worker_progress.v1")
        self.assertEqual(snapshot.worker_progress["rows"][0]["worker_id"], "local")
        self.assertEqual(snapshot.worker_progress["rows"][0]["job_id"], "launch-1")
        self.assertEqual(snapshot.worker_progress["rows"][0]["status_state"], "running")
        self.assertEqual(snapshot.ffmpeg_progress["schema_version"], "desktop_ffmpeg_progress.v1")
        self.assertTrue(snapshot.ffmpeg_progress["read_only"])
        self.assertEqual(snapshot.eta["schema_version"], "desktop_eta.v1")
        self.assertTrue(snapshot.eta["read_only"])
        self.assertIn("pipeline once: active", diagnostics.active_jobs[0])
        self.assertEqual(diagnostics.active_job_rows[0]["launch_id"], "launch-1")
        self.assertEqual(diagnostics.active_job_rows[0]["status"], "active")
        self.assertEqual(diagnostics.active_job_rows[0]["status_state"], "running")
        self.assertEqual(diagnostics.worker_progress["schema_version"], "desktop_worker_progress.v1")
        self.assertEqual(diagnostics.worker_progress["rows"][0]["job_id"], "launch-1")
        self.assertEqual(diagnostics.ffmpeg_progress["schema_version"], "desktop_ffmpeg_progress.v1")
        self.assertTrue(diagnostics.ffmpeg_progress["read_only"])
        self.assertEqual(diagnostics.eta["schema_version"], "desktop_eta.v1")
        self.assertTrue(diagnostics.eta["read_only"])
        self.assertEqual(diagnostics.recent_events, ["job_started"])

    def test_snapshot_progress_bars_include_pipeline_publish_and_audit(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            resolved = _resolved(root)
            service = DummyFacadeService(root)
            service.snapshot = Snapshot(
                resolved=resolved,
                current_activity="Publishing output.",
                status_summary="Status OK",
                log_tail="",
                progress={
                    "ProgressVersion": 2,
                    "LastUpdate": "2026-05-17 12:00:00",
                    "Status": "Processing",
                    "CurrentStage": "push",
                    "CurrentStagePercent": 95,
                    "CurrentQueueIndex": 3,
                    "CurrentQueueTotal": 4,
                    "CurrentRoute": "remux",
                    "CurrentFileDisplay": "Episode.mkv",
                    "PushState": "copied_pending_reveal",
                    "SubtitleProgress": {
                        "schema_version": "pipeline_subtitle_progress.v1",
                        "kind": "ass",
                        "stream_index": 2,
                        "stage": "validate",
                        "status": "ASS subtitle SRT validated",
                        "step_index": 3,
                        "step_total": 4,
                        "steps": ["extract", "convert", "validate", "sidecar_write"],
                        "completed_steps": ["extract", "convert", "validate"],
                        "percent": 75,
                        "detail": "32 cue(s)",
                        "cue_count": 32,
                        "updated_at": "2026-05-17T12:00:05Z",
                    },
                    "TotalProcessed": 2,
                    "Encoded": 0,
                    "Remuxed": 2,
                    "Failed": 0,
                    "Movies": 0,
                    "TVEpisodes": 2,
                },
                audit_progress={
                    "status": "writing-reports",
                    "processed_files": 10,
                    "total_files": 10,
                    "percent_complete": 100,
                    "current_operation": "Writing CSV audit summary.",
                    "report_stage": "write_csv",
                    "report_step_index": 2,
                    "report_step_total": 5,
                    "report_completed_steps": ["classify", "write_json"],
                    "latest_json_path": str(root / "audit_summary.json"),
                    "last_update": "2026-05-17T12:00:00Z",
                },
                latest_failure_report=None,
                latest_failure_json=None,
                latest_audit_csv=None,
                latest_priority_csv=None,
            )
            facade = MediaPipelineApplicationFacade(service, app_version="v5-test")
            snapshot = facade.get_snapshot(resolved)

        bars = {bar["id"]: bar for bar in snapshot.progress_bars}
        self.assertEqual(bars["current_stage"]["percent"], 95.0)
        self.assertEqual(bars["run_total"]["percent"], 75.0)
        self.assertEqual(bars["publish_output"]["status"], "active")
        self.assertEqual(bars["publish_output"]["source"], "pipeline_progress.json")
        self.assertEqual(bars["subtitle_track"]["mode"], "stepped")
        self.assertEqual(bars["subtitle_track"]["percent"], 75.0)
        self.assertEqual(bars["subtitle_track"]["label"], "Subtitle ASS stream 2")
        self.assertIn("validate", bars["subtitle_track"]["detail"])
        self.assertEqual(bars["audit_progress"]["percent"], 100.0)
        self.assertEqual(bars["audit_progress"]["source"], "audit_progress.json")
        self.assertEqual(bars["audit_reports"]["mode"], "stepped")
        self.assertEqual(bars["audit_reports"]["percent"], 40.0)
        self.assertEqual(bars["audit_reports"]["status"], "active")
        self.assertIn("write csv", bars["audit_reports"]["detail"])

    def test_snapshot_progress_bars_include_publish_copy_bytes_and_pending_total(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            resolved = _resolved(root)
            service = DummyFacadeService(root)
            service.snapshot = Snapshot(
                resolved=resolved,
                current_activity="Retrying pending push.",
                status_summary="Status OK",
                log_tail="",
                progress={
                    "ProgressVersion": 2,
                    "LastUpdate": "2026-05-17 12:00:00",
                    "Status": "Processing",
                    "CurrentStage": "retry_pending_push",
                    "CurrentStagePercent": 47,
                    "CurrentQueuePhase": "pending_push",
                    "CurrentQueueIndex": 2,
                    "CurrentQueueTotal": 4,
                    "CurrentRoute": "remux",
                    "CurrentFileDisplay": "Episode.mkv",
                    "PushState": "copying",
                    "CopyBytesCopied": 536870912,
                    "CopyTotalBytes": 1073741824,
                    "CopyPercent": 50,
                    "CopyAttempt": 1,
                    "CopyUpdatedAt": "2026-05-17T12:00:02Z",
                    "TotalProcessed": 2,
                    "Encoded": 0,
                    "Remuxed": 2,
                    "Failed": 0,
                    "Movies": 0,
                    "TVEpisodes": 2,
                },
                audit_progress=None,
                latest_failure_report=None,
                latest_failure_json=None,
                latest_audit_csv=None,
                latest_priority_csv=None,
            )
            facade = MediaPipelineApplicationFacade(service, app_version="v5-test")
            snapshot = facade.get_snapshot(resolved)

        bars = {bar["id"]: bar for bar in snapshot.progress_bars}
        self.assertEqual(bars["run_total"]["label"], "Pending publish total")
        self.assertEqual(bars["run_total"]["percent"], 50.0)
        self.assertEqual(bars["publish_output"]["percent"], 47.0)
        self.assertEqual(bars["publish_copy"]["percent"], 50.0)
        self.assertEqual(bars["publish_copy"]["source"], "pipeline_progress.json")
        self.assertIn("512.0 MB / 1.0 GB", bars["publish_copy"]["detail"])

    def test_telemetry_zero_percent_gpu_is_present_not_missing(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            facade = MediaPipelineApplicationFacade(DummyFacadeService(root))

            telemetry = facade.get_cached_telemetry()
            mapping = telemetry.to_mapping()

        self.assertTrue(mapping["gpu_present"])
        self.assertEqual(mapping["gpu_encoder_percent"], 0.0)
        self.assertEqual(mapping["gpu_rows"][0]["encoder_percent"], 0.0)
        self.assertEqual(mapping["gpu_encoder_usage"]["schema_version"], "desktop_gpu_encoder_usage.v1")
        self.assertTrue(mapping["gpu_encoder_usage"]["read_only"])
        self.assertEqual(mapping["gpu_encoder_usage"]["rows"][0]["utilization_percent"], 0.0)
        self.assertIsNone(mapping["gpu_encoder_usage"]["rows"][0]["encoder_sessions"])
