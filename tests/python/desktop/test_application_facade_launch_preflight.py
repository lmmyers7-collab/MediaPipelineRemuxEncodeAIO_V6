from __future__ import annotations

from datetime import datetime, timedelta, UTC
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from mediapipeline.core.kernel.contracts import accepted_run_rows_fingerprint
from mediapipeline.core.kernel.runtime.subprocess_runner import CapturedCommandResult
from mediapipeline.core.paths.queue_input_fingerprint import queue_input_fingerprint
from mediapipeline.core.processes.path_evidence import LAUNCH_PATH_HEALTH_TIMEOUT_SECONDS
from mediapipeline.core.processes.preflight_facade import LAUNCH_PREFLIGHT_PATH_HEALTH_TIMEOUT_SECONDS
from mediapipeline.desktop.application import MediaPipelineApplicationFacade
from mediapipeline.desktop.models import ResolvedPaths
from tests.python.desktop.application_facade_test_support import (
    DummyWorkflowFacadeService,
    _resolved,
    fresh_generated_at as _fresh_generated_at,
    write_test_media_file as _media_file,
)


def _launch_preflight_facade(
    root: Path,
) -> tuple[DummyWorkflowFacadeService, MediaPipelineApplicationFacade, ResolvedPaths]:
    """Build the disposable service/facade/path trio shared by preflight tests."""
    service = DummyWorkflowFacadeService(root)
    return service, MediaPipelineApplicationFacade(service, app_version="v5-test"), _resolved(root)


class ApplicationFacadeLaunchPreflightTests(unittest.TestCase):
    def test_launch_preflight_is_read_only_and_matches_launch_guards(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            csv_path = root / "rerun.csv"
            movie = _media_file(root, "Movie")
            csv_path.write_text(f"enabled,source_path\ntrue,{movie}\n", encoding="utf-8")
            (root / "Outsource").mkdir()
            service, facade, resolved = _launch_preflight_facade(root)
            resolved.source_movies = root / "Movies"
            resolved.source_movies.mkdir(parents=True)
            sample = resolved.source_movies / "sample.mkv"
            sample.write_bytes(b"media")
            resolved.config_data = {
                "NetworkRole": "standalone",
                "Outsource": str(root / "Outsource"),
                "SourceMovies": str(resolved.source_movies),
            }

            pipeline = facade.get_launch_preflight(
                resolved,
                {
                    "target": "pipeline",
                    "mode": "validate",
                    "sleep_seconds": 3,
                    "single_file": str(sample),
                },
            )
            invalid_mode = facade.get_launch_preflight(resolved, {"target": "pipeline", "mode": "bad"})
            audit = facade.get_launch_preflight(resolved, {"target": "audit", "include_sidecars": True})
            rerun = facade.get_launch_preflight(
                resolved,
                {"target": "rerun", "csv_path": str(csv_path), "confirm_replace_final": True},
            )
            blocked_rerun = facade.get_launch_preflight(
                resolved,
                {"target": "rerun", "csv_path": str(csv_path), "destination_mode": "publish_replace_final"},
            )
            has_started_side_effects = any(
                hasattr(service, attr)
                for attr in ("started_pipeline", "started_audit", "started_rerun")
            )

        self.assertEqual(pipeline["schema_version"], "desktop_launch_preflight.v1")
        self.assertEqual(pipeline["target"], "pipeline")
        self.assertEqual(pipeline["request"]["single_file"], str(sample))
        self.assertTrue(pipeline["can_request_start"])
        self.assertEqual(pipeline["start_route"], "/api/pipeline/start")
        self.assertEqual(pipeline["operator_readiness"]["schema_version"], "desktop_launch_readiness.v1")
        self.assertEqual(pipeline["operator_readiness"]["evidence_authority"], "backend")
        self.assertEqual(pipeline["operator_readiness"]["source_route"], "/api/launch/preflight")
        self.assertEqual(pipeline["operator_readiness"]["display_status"], "Review")
        self.assertIn("Launch readiness (backend-authored):", pipeline["operator_readiness"]["summary_lines"])
        self.assertTrue(any("Backend launch locking and gating remain the source of truth." in line for line in pipeline["operator_readiness"]["summary_lines"]))
        self.assertTrue(any(row["key"] == "runtime_prep_boundary" and row["status"] == "ready" for row in pipeline["checks"]))
        self.assertTrue(any(row["key"] == "encoder_capability_report" for row in pipeline["checks"]))
        self.assertTrue(any(row["key"] == "single_file_scope" and row["status"] == "ready" for row in pipeline["checks"]))
        self.assertTrue(pipeline["request"]["single_file_validation"]["ok"])
        self.assertEqual(pipeline["request"]["single_file_validation"]["normalized_path"], str(sample))
        self.assertFalse(has_started_side_effects)
        self.assertEqual(invalid_mode["status"], "blocked")
        self.assertFalse(invalid_mode["can_request_start"])
        self.assertEqual(invalid_mode["operator_readiness"]["display_status"], "Blocked")
        self.assertGreaterEqual(invalid_mode["operator_readiness"]["non_ready_count"], 1)
        self.assertTrue(any(row["key"] == "mode" and row["status"] == "blocked" for row in invalid_mode["checks"]))
        self.assertEqual(audit["target"], "audit")
        self.assertEqual(audit["start_route"], "/api/audit/start")
        self.assertEqual(audit["request"]["library_root"], str(root / "Outsource"))
        self.assertTrue(any(row["key"] == "runtime_prep_boundary" and row["status"] == "ready" for row in audit["checks"]))
        self.assertEqual(rerun["target"], "rerun")
        self.assertEqual(rerun["start_route"], "/api/rerun/start")
        self.assertEqual(rerun["request"]["execution_mode"], "one_at_a_time")
        self.assertEqual(rerun["request"]["destination_mode"], "auto_replace_clean_else_pending_review")
        self.assertEqual(rerun["request"]["collision_policy"], "replace_final")
        self.assertTrue(rerun["request"]["confirm_replace_final"])
        self.assertNotIn("original_policy", rerun["request"])
        self.assertTrue(any(row["key"] == "csv_rerun_rows" and row["status"] == "ready" for row in rerun["checks"]))
        self.assertEqual(blocked_rerun["status"], "blocked")
        self.assertTrue(any(row["key"] == "lifecycle_policy" and row["status"] == "blocked" for row in blocked_rerun["checks"]))
        self.assertTrue(any(row["key"] == "csv_rerun_rows" and row["status"] == "blocked" for row in blocked_rerun["checks"]))

    def test_run_once_preflight_requires_current_backend_queue_plan(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            service = DummyWorkflowFacadeService(root)
            fixed_now = datetime(2026, 7, 20, 12, 0, 0, tzinfo=UTC)
            service.queue_snapshot_freshness_wall_now = lambda: fixed_now  # type: ignore[method-assign]
            service.queue_snapshot_freshness_monotonic_now = lambda: 100.0  # type: ignore[method-assign]
            facade = MediaPipelineApplicationFacade(service, app_version="v5-test")
            resolved = _resolved(root)
            resolved.source_movies = root / "Movies"
            resolved.source_tv = root / "TV"
            resolved.source_movies.mkdir(parents=True)
            resolved.source_tv.mkdir(parents=True)
            (root / "Outsource").mkdir()
            resolved.config_data = {
                "NetworkRole": "standalone",
                "SourceMovies": str(resolved.source_movies),
                "SourceTV": str(resolved.source_tv),
                "Outsource": str(root / "Outsource"),
                "QueueLaunchSnapshotFreshnessSeconds": 60,
            }
            resolved.config_path.write_text("@{ NetworkRole = 'standalone' }", encoding="utf-8")
            snapshot_path = root / "State" / "Progress" / "queue_snapshot.json"
            snapshot_path.parent.mkdir(parents=True)
            resolved.state_root = root / "State"
            resolved.queue_snapshot_path = snapshot_path

            def write_snapshot(
                *,
                runnable_count: int,
                config_path: Path | None = None,
                produced_at: str | None = None,
                mtime_age_seconds: int = 0,
                include_accepted_run_rows: bool = True,
            ) -> None:
                request_id = "queue-preview-test"
                input_fingerprint = queue_input_fingerprint(resolved)
                rows = []
                if runnable_count:
                    rows.append(
                        {
                            "global_order": 1,
                            "phase": "movie",
                            "media_kind": "movie",
                            "queue_index": 1,
                            "queue_total": 1,
                            "is_priority": False,
                            "source_path": str(resolved.source_movies / "Movie.mkv"),
                            "root_path": str(resolved.source_movies),
                            "relative_path": "Movie.mkv",
                            "display_name": "Movie.mkv",
                            "size_gb": 1.0,
                            "route": "remux",
                            "route_reason_code": "copy_compatible",
                            "route_reason": "already compatible",
                            "blocked_reason": "",
                        }
                    )
                accepted_run_rows = []
                if runnable_count and include_accepted_run_rows:
                    accepted_run_rows.append(
                        {
                            "source_identity": "source-identity-1",
                            "source_identity_algorithm": "path_size_mtime_sha256.v1",
                            "source_path": str(resolved.source_movies / "Movie.mkv"),
                            "display_name": "Movie.mkv",
                            "planned_display_name": "Movie.mkv",
                            "planned_display_name_source": "plex_destination_plan.v1",
                            "parent_context": str(resolved.source_movies),
                            "run_queue_index": 1,
                            "run_queue_total": runnable_count,
                            "route": "remux",
                            "route_reason_code": "copy_compatible",
                            "route_reason": "already compatible",
                        }
                    )
                snapshot_path.write_text(
                    json.dumps(
                        {
                            "schema_version": "queue_plan_snapshot.v1",
                            "produced_at": produced_at or fixed_now.isoformat(),
                            "config_path": str(config_path or resolved.config_path),
                            "local_base": str(resolved.local_base),
                            "source_movies": str(resolved.source_movies),
                            "source_tv": str(resolved.source_tv),
                            "outsource": str(root / "Outsource"),
                            "movie_count_total": runnable_count,
                            "tv_count_total": 0,
                            "priority_count": 0,
                            "runnable_count": runnable_count,
                            "queue_snapshot_origin": "dry_run",
                            "desktop_queue_preview_request_id": request_id,
                            "queue_input_fingerprint_schema": input_fingerprint["schema_version"],
                            "queue_input_fingerprint": input_fingerprint["fingerprint"],
                            "queue_input_components": input_fingerprint["components"],
                            "queue_plan_fingerprint_schema": "queue_plan_fingerprint.v1",
                            "queue_plan_fingerprint": f"test-plan-{runnable_count}",
                            "accepted_run_rows_fingerprint_schema": "accepted_run_rows_fingerprint.v1",
                            "accepted_run_rows_fingerprint": accepted_run_rows_fingerprint(accepted_run_rows),
                            "pending_publish_index_health": {"status": "ready"},
                            "pending_publish_backpressure": {"blocked": False},
                            "accepted_run_rows": accepted_run_rows,
                            "rows": rows,
                        }
                    ),
                    encoding="utf-8",
                )
                if mtime_age_seconds:
                    timestamp = fixed_now.timestamp() - mtime_age_seconds
                    os.utime(snapshot_path, (timestamp, timestamp))
                else:
                    timestamp = fixed_now.timestamp()
                    os.utime(snapshot_path, (timestamp, timestamp))
                (snapshot_path.parent / "queue_scan_status.json").write_text(
                    json.dumps(
                        {
                            "schema_version": "desktop_queue_scan_status.v1",
                            "scan_id": "scan-test",
                            "status": "completed",
                            "phase": "complete",
                            "mode": "inventory_then_curate",
                            "queue_preview_request_id": request_id,
                        }
                    ),
                    encoding="utf-8",
                )

            def queue_scope(payload: dict[str, object]) -> dict[str, object]:
                return next(
                    check
                    for check in payload["checks"]  # type: ignore[index]
                    if check["key"] == "normal_queue_scope"
                )

            write_snapshot(runnable_count=0)
            fresh_empty = facade.get_launch_preflight(resolved, {"target": "pipeline", "mode": "once"})

            write_snapshot(runnable_count=1, mtime_age_seconds=61)
            old_file_age_ready = facade.get_launch_preflight(
                resolved,
                {"target": "pipeline", "mode": "once"},
            )

            write_snapshot(
                runnable_count=1,
                produced_at=(fixed_now - timedelta(seconds=120)).isoformat(),
            )
            old_produced_age_ready = facade.get_launch_preflight(
                resolved,
                {"target": "pipeline", "mode": "once"},
            )

            write_snapshot(
                runnable_count=1,
                produced_at=(fixed_now + timedelta(seconds=30)).isoformat(),
            )
            future_produced_age_ready = facade.get_launch_preflight(
                resolved,
                {"target": "pipeline", "mode": "once"},
            )

            resolved.config_data["QueueLaunchSnapshotFreshnessSeconds"] = 120
            write_snapshot(
                runnable_count=1,
                produced_at=(fixed_now - timedelta(seconds=90)).isoformat(),
                mtime_age_seconds=90,
            )
            configured_age_ready = facade.get_launch_preflight(
                resolved,
                {"target": "pipeline", "mode": "once"},
            )
            resolved.config_data["QueueLaunchSnapshotFreshnessSeconds"] = 60

            write_snapshot(runnable_count=0, config_path=root / "other.psd1")
            mismatched_empty = facade.get_launch_preflight(resolved, {"target": "pipeline", "mode": "once"})

            write_snapshot(runnable_count=1)
            resolved.config_path.write_text("@{ NetworkRole = 'worker' }", encoding="utf-8")
            changed_inputs = facade.get_launch_preflight(resolved, {"target": "pipeline", "mode": "once"})
            resolved.config_path.write_text("@{ NetworkRole = 'standalone' }", encoding="utf-8")
            write_snapshot(runnable_count=1, include_accepted_run_rows=False)
            legacy_missing_accepted_rows = facade.get_launch_preflight(
                resolved,
                {"target": "pipeline", "mode": "once"},
            )
            write_snapshot(runnable_count=1)
            fresh_ready = facade.get_launch_preflight(resolved, {"target": "pipeline", "mode": "once"})
            tampered_snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
            tampered_snapshot["accepted_run_rows"][0]["planned_display_name"] = "Tampered Raw Release.mkv"
            snapshot_path.write_text(json.dumps(tampered_snapshot), encoding="utf-8")
            os.utime(snapshot_path, (fixed_now.timestamp(), fixed_now.timestamp()))
            tampered_accepted_name = facade.get_launch_preflight(
                resolved,
                {"target": "pipeline", "mode": "once"},
            )
            write_snapshot(runnable_count=1)
            service.queue_source_scan_active_block_message = lambda _action: "Queue scan is running."  # type: ignore[method-assign]
            scanning = facade.get_launch_preflight(resolved, {"target": "pipeline", "mode": "once"})
            service.queue_source_scan_active_block_message = lambda _action: ""  # type: ignore[method-assign]
            validate = facade.get_launch_preflight(resolved, {"target": "pipeline", "mode": "validate"})
            single_file = resolved.source_movies / "Single.mkv"
            single_file.write_bytes(b"media")
            scoped_once = facade.get_launch_preflight(
                resolved,
                {"target": "pipeline", "mode": "once", "single_file": str(single_file)},
            )

        expected = (
            (fresh_empty, "blocked", "no_runnable_work"),
            (old_file_age_ready, "ready", "queue_plan_fingerprint=test-plan-1"),
            (old_produced_age_ready, "ready", "preview_age=older_than_preference"),
            (future_produced_age_ready, "ready", "preview_age=clock_skewed"),
            (configured_age_ready, "ready", "preview_age_limit_seconds=120"),
            (mismatched_empty, "blocked", "queue_snapshot_scope_mismatch"),
            (changed_inputs, "blocked", "queue_snapshot_inputs_not_current"),
            (legacy_missing_accepted_rows, "blocked", "queue_snapshot_accepted_rows_missing"),
            (fresh_ready, "ready", "queue_plan_fingerprint=test-plan-1"),
            (tampered_accepted_name, "blocked", "queue_snapshot_accepted_fingerprint_mismatch"),
            (scanning, "blocked", "queue_scan_running"),
        )
        for payload, expected_status, expected_detail in expected:
            with self.subTest(expected_detail=expected_detail):
                self.assertEqual(queue_scope(payload)["status"], expected_status)
                self.assertIn(expected_detail, queue_scope(payload)["detail"])
        self.assertIn("preview_handoff_grace_seconds=1", queue_scope(old_file_age_ready)["detail"])
        for payload in (
            old_file_age_ready,
            old_produced_age_ready,
            future_produced_age_ready,
            configured_age_ready,
        ):
            self.assertTrue(payload["can_request_start"])
            self.assertFalse(
                any(
                    "queue_snapshot" in str(item) and "stale" in str(item)
                    for item in queue_scope(payload)["detail"]
                )
            )
        self.assertFalse(any(check["key"] == "normal_queue_scope" for check in validate["checks"]))
        self.assertFalse(any(check["key"] == "normal_queue_scope" for check in scoped_once["checks"]))

    def test_rerun_launch_preflight_mirrors_csv_preview_blockers_without_writes(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            csv_path = root / "rerun.csv"
            invalid_extension = _media_file(root, "Notes", suffix=".txt")
            missing = root / "Media" / "Missing.mkv"
            csv_path.write_text(
                "enabled,source_path\n"
                "true,relative/movie.mkv\n"
                f"true,{missing}\n"
                f"true,{invalid_extension}\n",
                encoding="utf-8",
            )
            service, facade, resolved = _launch_preflight_facade(root)
            resolved.state_root = root / "State"

            preflight = facade.get_launch_preflight(resolved, {"target": "rerun", "csv_path": str(csv_path)})

        checks = {row["key"]: row for row in preflight["checks"]}
        self.assertEqual(preflight["status"], "blocked")
        self.assertFalse(preflight["can_request_start"])
        self.assertEqual(checks["csv_rerun_rows"]["status"], "blocked")
        self.assertIn("relative=1", checks["csv_rerun_rows"]["evidence"])
        self.assertIn("missing_files=1", checks["csv_rerun_rows"]["evidence"])
        self.assertIn("invalid_extensions=1", checks["csv_rerun_rows"]["evidence"])
        self.assertFalse(hasattr(service, "started_rerun"))
        self.assertFalse((root / "State" / "Rerun" / "ScopedCsv").exists())

    def test_launch_preflight_surfaces_configured_path_health_warning(self) -> None:
        health = {
            "schema_version": "desktop_configured_path_health.v1",
            "read_only": True,
            "operator_status": "blocked",
            "operator_summary": "1 configured root(s) are not reachable or listable.",
            "rows": [
                {
                    "key": "source_movies",
                    "label": "SourceMovies root",
                    "status": "blocked",
                    "message": "SourceMovies root does not exist or is not reachable from this Windows session.",
                    "safe_next_action": "Log back into Windows/server share, then refresh path health.",
                }
            ],
            "summary_lines": [
                "Configured path health: blocked.",
                "SourceMovies root: blocked; SourceMovies root does not exist or is not reachable from this Windows session.",
            ],
        }
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            service, facade, resolved = _launch_preflight_facade(root)
            resolved.config_data = {"NetworkRole": "standalone", "SourceMovies": r"\\LAYNE-SERVER\Video\Movies"}

            with patch("mediapipeline.core.processes.preflight_facade.configured_path_health", return_value=health):
                preflight = facade.get_launch_preflight(resolved, {"target": "pipeline", "mode": "validate"})

        self.assertEqual(preflight["status"], "blocked")
        self.assertFalse(preflight["can_request_start"])
        rows = {row["key"]: row for row in preflight["checks"]}
        self.assertEqual(rows["configured_path_health"]["status"], "high review")
        self.assertIn("not reachable", "\n".join(str(item) for item in rows["configured_path_health"]["detail"]))
        self.assertIn("Configured server/folder health", rows["configured_path_health"]["label"])
        self.assertEqual(rows["autonomy_health"]["status"], "blocked")
        self.assertIn("can_start_new_work=no", rows["autonomy_health"]["evidence"])

    def test_launch_preflight_uses_network_tolerant_path_health_timeout(self) -> None:
        health = {
            "schema_version": "desktop_configured_path_health.v1",
            "read_only": True,
            "operator_status": "ready",
            "operator_summary": "Configured media/storage roots are reachable and listable.",
            "rows": [
                {
                    "key": "source_movies",
                    "label": "SourceMovies root",
                    "role": "source",
                    "status": "ready",
                    "storage_status": "not_checked",
                    "message": "SourceMovies root exists and the backend can list the root.",
                }
            ],
            "summary_lines": ["Configured path health: ready."],
        }
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            service, facade, resolved = _launch_preflight_facade(root)
            resolved.config_data = {"NetworkRole": "standalone", "SourceMovies": r"\\LAYNE-SERVER\Video\Movies"}

            with patch("mediapipeline.core.processes.preflight_facade.configured_path_health", return_value=health) as path_health:
                preflight = facade.get_launch_preflight(resolved, {"target": "pipeline", "mode": "validate"})

        self.assertTrue(preflight["can_request_start"])
        path_health.assert_called_once()
        self.assertEqual(LAUNCH_PREFLIGHT_PATH_HEALTH_TIMEOUT_SECONDS, LAUNCH_PATH_HEALTH_TIMEOUT_SECONDS)
        self.assertEqual(path_health.call_args.kwargs["timeout_seconds"], LAUNCH_PREFLIGHT_PATH_HEALTH_TIMEOUT_SECONDS)

    def test_pipeline_start_uses_launch_path_health_before_autonomy_gate(self) -> None:
        health = {
            "schema_version": "desktop_configured_path_health.v1",
            "read_only": True,
            "operator_status": "ready",
            "operator_summary": "Configured media/storage roots are reachable and listable.",
            "rows": [],
            "summary_lines": ["Configured path health: ready."],
        }
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            service, facade, resolved = _launch_preflight_facade(root)

            with patch.object(facade, "_launch_path_health_for_resolved", return_value=health) as path_health:
                result = facade.start_pipeline_process(resolved, {"mode": "validate"}).to_mapping()

        self.assertTrue(result["ok"])
        path_health.assert_called_once_with(resolved)

    def test_launch_preflight_surfaces_missing_encoder_capability_report_without_blocking_start(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            service, facade, resolved = _launch_preflight_facade(root)
            resolved.state_root = root / "State"
            resolved.pipeline_path.write_text("pipeline", encoding="utf-8")
            resolved.config_path.write_text("@{}", encoding="utf-8")
            Path(resolved.powershell_host).write_text("pwsh", encoding="utf-8")
            resolved.config_data = {"NetworkRole": "standalone"}

            preflight = facade.get_launch_preflight(resolved, {"target": "pipeline", "mode": "validate"})

        rows = {row["key"]: row for row in preflight["checks"]}
        report = rows["encoder_capability_report"]
        self.assertTrue(preflight["can_request_start"])
        self.assertEqual(report["status"], "review")
        self.assertIn("exists=no", report["evidence"])
        self.assertIn("refresh=skipped", report["evidence"])
        self.assertIn("read_only=yes", report["evidence"])
        self.assertEqual(report["detail"][0]["schema_version"], "settings_encoder_capability_report.v1")
        self.assertTrue(report["detail"][0]["read_only"])
        self.assertEqual(report["detail"][0]["operator_status_state"], "missing")
        self.assertEqual(report["detail"][0]["source"], "-DumpEncoderCapabilitiesPath")
        self.assertTrue(report["detail"][0]["refresh_needed"])
        self.assertEqual(report["detail"][0]["auto_refresh"]["reason"], "missing")
        self.assertFalse(report["detail"][0]["auto_refresh"]["attempted"])
        self.assertFalse(report["detail"][0]["auto_refresh"]["requested"])
        self.assertEqual(report["detail"][0]["auto_refresh"]["skipped_reason"], "refresh not requested")

    def test_launch_preflight_skips_stale_encoder_capability_refresh_by_default(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            report_path = root / "State" / "Progress" / "encoder_capabilities.json"
            report_path.parent.mkdir(parents=True)
            report_path.write_text(
                json.dumps(
                    {
                        "schema": "mediapipeline.encoder_capabilities.v2",
                        "generated_at": "2000-01-01T00:00:00Z",
                        "video_codec": "hevc_nvenc",
                        "encoder_backend": "auto",
                        "selection": {"resolved": True, "reason": "old", "family": "hevc"},
                        "encoders": [
                            {
                                "encoder_name": "hevc_nvenc",
                                "family": "hevc",
                                "backend": "nvenc",
                                "roles": ["primary"],
                                "descriptor_flags_active": True,
                                "available": True,
                                "runtime_ok": True,
                                "runtime_probe_skipped": False,
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            service, facade, resolved = _launch_preflight_facade(root)
            resolved.state_root = root / "State"
            resolved.config_data = {"NetworkRole": "standalone"}

            with patch("mediapipeline.core.processes.preflight_facade.run_capture") as run_capture:
                preflight = facade.get_launch_preflight(resolved, {"target": "pipeline", "mode": "validate"})

        rows = {row["key"]: row for row in preflight["checks"]}
        report = rows["encoder_capability_report"]
        run_capture.assert_not_called()
        self.assertTrue(preflight["can_request_start"])
        self.assertEqual(report["status"], "review")
        self.assertIn("refresh=skipped", report["evidence"])
        self.assertTrue(report["detail"][0]["refresh_needed"])
        self.assertTrue(report["detail"][0]["stale"])
        self.assertFalse(report["detail"][0]["auto_refresh"]["attempted"])
        self.assertFalse(report["detail"][0]["auto_refresh"]["requested"])
        self.assertEqual(report["detail"][0]["auto_refresh"]["reason"], "stale")
        self.assertEqual(report["detail"][0]["auto_refresh"]["skipped_reason"], "refresh not requested")

    def test_launch_preflight_ignores_encoder_capability_refresh_request(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            report_path = root / "State" / "Progress" / "encoder_capabilities.json"
            report_path.parent.mkdir(parents=True)
            report_path.write_text(
                json.dumps(
                    {
                        "schema": "mediapipeline.encoder_capabilities.v1",
                        "generated_at": "2000-01-01T00:00:00Z",
                        "video_codec": "hevc_nvenc",
                        "encoder_backend": "auto",
                        "selection": {"resolved": True, "reason": "old", "family": "hevc"},
                        "encoders": [
                            {
                                "encoder_name": "hevc_nvenc",
                                "family": "hevc",
                                "backend": "nvenc",
                                "roles": ["primary"],
                                "descriptor_flags_active": True,
                                "available": True,
                                "runtime_ok": True,
                                "runtime_probe_skipped": False,
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            service, facade, resolved = _launch_preflight_facade(root)
            resolved.state_root = root / "State"
            resolved.pipeline_path.write_text("pipeline", encoding="utf-8")
            resolved.config_path.write_text("@{}", encoding="utf-8")
            Path(resolved.powershell_host).write_text("pwsh", encoding="utf-8")
            resolved.config_data = {"NetworkRole": "standalone"}
            with patch("mediapipeline.core.processes.preflight_facade.run_capture") as run_capture:
                preflight = facade.get_launch_preflight(
                    resolved,
                    {
                        "target": "pipeline",
                        "mode": "validate",
                        "refresh_encoder_capability_report": True,
                    },
                )

        rows = {row["key"]: row for row in preflight["checks"]}
        report = rows["encoder_capability_report"]
        run_capture.assert_not_called()
        self.assertEqual(report["status"], "review")
        self.assertIn("refresh=skipped", report["evidence"])
        self.assertTrue(report["detail"][0]["refresh_needed"])
        self.assertTrue(report["detail"][0]["stale"])
        self.assertFalse(report["detail"][0]["auto_refresh"]["attempted"])
        self.assertFalse(report["detail"][0]["auto_refresh"]["requested"])
        self.assertEqual(report["detail"][0]["auto_refresh"]["reason"], "stale")
        self.assertEqual(report["detail"][0]["auto_refresh"]["skipped_reason"], "refresh not requested")

    def test_encoder_capability_refresh_is_explicit_backend_command(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            report_path = root / "State" / "Progress" / "encoder_capabilities.json"
            report_path.parent.mkdir(parents=True)
            report_path.write_text(
                json.dumps(
                    {
                        "schema": "mediapipeline.encoder_capabilities.v1",
                        "generated_at": "2000-01-01T00:00:00Z",
                        "video_codec": "hevc_nvenc",
                        "encoder_backend": "auto",
                        "selection": {"resolved": True, "reason": "old", "family": "hevc"},
                        "encoders": [],
                    }
                ),
                encoding="utf-8",
            )
            service, facade, resolved = _launch_preflight_facade(root)
            resolved.state_root = root / "State"
            resolved.pipeline_path.write_text("pipeline", encoding="utf-8")
            resolved.config_path.write_text("@{}", encoding="utf-8")
            Path(resolved.powershell_host).write_text("pwsh", encoding="utf-8")

            def fake_run_capture(args: list[str], **kwargs: object) -> CapturedCommandResult:
                target = Path(args[args.index("-DumpEncoderCapabilitiesPath") + 1])
                target.write_text(
                    json.dumps(
                        {
                            "schema": "mediapipeline.encoder_capabilities.v1",
                            "generated_at": _fresh_generated_at(),
                            "video_codec": "hevc_nvenc",
                            "encoder_backend": "auto",
                            "selection": {"resolved": True, "reason": "refreshed", "family": "hevc"},
                            "encoders": [],
                        }
                    ),
                    encoding="utf-8",
                )
                return CapturedCommandResult(args=args, returncode=0, stdout="dumped", stderr="")

            with patch("mediapipeline.core.processes.preflight_facade.run_capture", side_effect=fake_run_capture):
                result = facade.refresh_encoder_capability_report(resolved, {})

        self.assertTrue(result.ok)
        self.assertEqual(result.command, "diagnostics.encoder_capabilities.refresh")
        self.assertTrue(result.data["encoder_capability_report"]["exists"])
        self.assertFalse(result.data["encoder_capability_report"]["refresh_needed"])

    def test_launch_preflight_surfaces_existing_encoder_capability_report_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            report_path = root / "State" / "Progress" / "encoder_capabilities.json"
            report_path.parent.mkdir(parents=True)
            report_path.write_text(
                json.dumps(
                    {
                        "schema": "mediapipeline.encoder_capabilities.v2",
                        "generated_at": _fresh_generated_at(),
                        "video_codec": "h264_nvenc",
                        "encoder_backend": "auto",
                        "selection": {"resolved": True, "reason": "auto", "family": "h264"},
                        "evidence": {
                            "freshness": {"ttl_seconds": 900, "posture": "availability_and_runtime_probe_only"},
                            "resolved_config": {"fingerprint": "fixture"},
                            "ffmpeg": {"path": "C:/tools/ffmpeg.exe"},
                            "host": {"certification_state": "not_certified"},
                            "selected_descriptor_chain": {"primary": {"encoder": "h264_nvenc"}, "cpu_fallback": {"encoder": "libx264"}},
                            "activation_state": {"selected_resolved": True}, "list_probe_state": "completed", "runtime_probe_state": "completed",
                            "invalidation_state": {"invalidated": False}, "metadata_proof_state": "not_collected", "playback_proof_state": "not_collected",
                        },
                        "encoders": [
                            {
                                "encoder_name": "h264_nvenc",
                                "probe_encoder_name": "h264_nvenc",
                                "family": "h264",
                                "backend": "nvenc",
                                "roles": ["primary"],
                                "descriptor_flags_active": True,
                                "activation": [
                                    {
                                        "role": "primary",
                                        "active": True,
                                        "descriptor_encoder": "h264_nvenc",
                                        "active_descriptor_encoder": "h264_nvenc",
                                        "reason": "descriptor-owned flags are active for primary attempt",
                                    }
                                ],
                                "available": True,
                                "probed": True,
                                "runtime_probe_skipped": False,
                                "encoder_list_match": True,
                                "runtime_ok": True,
                                "backend_invalidated": False,
                                "reason": "available",
                                "probed_at": "2026-06-21T12:30:01Z",
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            service, facade, resolved = _launch_preflight_facade(root)
            resolved.state_root = root / "State"
            resolved.config_data = {"NetworkRole": "standalone"}

            preflight = facade.get_launch_preflight(resolved, {"target": "pipeline", "mode": "validate"})

        rows = {row["key"]: row for row in preflight["checks"]}
        report = rows["encoder_capability_report"]
        self.assertTrue(preflight["can_request_start"])
        self.assertEqual(report["status"], "ready")
        self.assertIn("VideoCodec=h264_nvenc", report["evidence"])
        self.assertIn("available_count=1", report["evidence"])
        self.assertIn("active_count=1", report["evidence"])
        self.assertIn("inactive_available_count=0", report["evidence"])
        self.assertEqual(report["detail"][0]["operator_status_state"], "ready")
        self.assertEqual(report["detail"][0]["available_encoders"], ["h264_nvenc"])
        self.assertEqual(report["detail"][0]["active_encoders"], ["h264_nvenc"])
        self.assertEqual(report["detail"][0]["available_inactive_encoders"], [])
        self.assertEqual(report["detail"][0]["backend_counts"]["nvenc"], {"available": 1, "unavailable": 0, "total": 1})
        self.assertEqual(
            report["detail"][0]["encoding_capability_facts"]["supported_video_codecs"],
            ["h264"],
        )
        self.assertEqual(
            report["detail"][0]["encoding_capability_facts"]["supported_encoder_backends"],
            ["copy", "nvenc"],
        )

    def test_launch_preflight_surfaces_available_but_inactive_encoder_capability_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            report_path = root / "State" / "Progress" / "encoder_capabilities.json"
            report_path.parent.mkdir(parents=True)
            report_path.write_text(
                json.dumps(
                    {
                        "schema": "mediapipeline.encoder_capabilities.v1",
                        "generated_at": _fresh_generated_at(),
                        "video_codec": "av1_nvenc",
                        "encoder_backend": "auto",
                        "selection": {"resolved": True, "reason": "resolved primary descriptor 'av1/nvenc'", "family": "av1"},
                        "encoders": [
                            {
                                "encoder_name": "av1_nvenc",
                                "probe_encoder_name": "av1_nvenc",
                                "family": "av1",
                                "backend": "nvenc",
                                "roles": ["primary"],
                                "descriptor_flags_active": False,
                                "activation": [
                                    {
                                        "role": "primary",
                                        "active": False,
                                        "descriptor_encoder": "av1_nvenc",
                                        "active_descriptor_encoder": "",
                                        "reason": "descriptor flags are not active for primary attempt",
                                    }
                                ],
                                "available": True,
                                "probed": True,
                                "encoder_list_match": True,
                                "runtime_ok": True,
                                "reason": "encoder 'av1_nvenc' probe succeeded",
                            },
                            {
                                "encoder_name": "libaom-av1",
                                "probe_encoder_name": "libaom-av1",
                                "family": "av1",
                                "backend": "cpu",
                                "roles": ["cpu_fallback"],
                                "descriptor_flags_active": True,
                                "activation": [
                                    {
                                        "role": "cpu_fallback",
                                        "active": True,
                                        "descriptor_encoder": "libaom-av1",
                                        "active_descriptor_encoder": "libaom-av1",
                                        "reason": "descriptor-owned flags are active for cpu_fallback attempt",
                                    }
                                ],
                                "available": True,
                                "probed": True,
                                "encoder_list_match": True,
                                "runtime_ok": True,
                                "reason": "encoder 'libaom-av1' probe succeeded",
                            },
                        ],
                    }
                ),
                encoding="utf-8",
            )
            service, facade, resolved = _launch_preflight_facade(root)
            resolved.state_root = root / "State"
            resolved.config_data = {"NetworkRole": "standalone"}

            preflight = facade.get_launch_preflight(resolved, {"target": "pipeline", "mode": "validate"})

        rows = {row["key"]: row for row in preflight["checks"]}
        report = rows["encoder_capability_report"]
        self.assertTrue(preflight["can_request_start"])
        self.assertEqual(report["status"], "review")
        self.assertIn("available_count=2", report["evidence"])
        self.assertIn("active_count=1", report["evidence"])
        self.assertIn("inactive_available_count=1", report["evidence"])
        self.assertEqual(report["detail"][0]["operator_status_state"], "warning")
        self.assertEqual(report["detail"][0]["available_encoders"], ["av1_nvenc", "libaom-av1"])
        self.assertEqual(report["detail"][0]["active_encoders"], ["libaom-av1"])
        self.assertEqual(report["detail"][0]["available_inactive_encoders"], ["av1_nvenc"])
        self.assertEqual(
            report["detail"][0]["encoding_capability_facts"]["supported_encoder_backends"],
            ["copy", "cpu", "libaom"],
        )

    def test_launch_preflight_surfaces_hardware_runtime_proof_gaps(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            report_path = root / "State" / "Progress" / "encoder_capabilities.json"
            report_path.parent.mkdir(parents=True)
            report_path.write_text(
                json.dumps(
                    {
                        "schema": "mediapipeline.encoder_capabilities.v1",
                        "generated_at": _fresh_generated_at(),
                        "video_codec": "hevc_nvenc",
                        "encoder_backend": "auto",
                        "selection": {"resolved": True, "reason": "resolved primary descriptor 'hevc/nvenc'", "family": "hevc"},
                        "encoders": [
                            {
                                "encoder_name": "hevc_nvenc",
                                "probe_encoder_name": "hevc_nvenc",
                                "family": "hevc",
                                "backend": "nvenc",
                                "roles": ["primary"],
                                "descriptor_flags_active": True,
                                "activation": [
                                    {
                                        "role": "primary",
                                        "active": True,
                                        "descriptor_encoder": "hevc_nvenc",
                                        "active_descriptor_encoder": "hevc_nvenc",
                                        "reason": "descriptor-owned flags are active for primary attempt",
                                    }
                                ],
                                "available": False,
                                "probed": False,
                                "runtime_probe_skipped": True,
                                "encoder_list_match": True,
                                "runtime_ok": False,
                                "reason": "runtime probe skipped for hardware descriptor",
                            },
                            {
                                "encoder_name": "libx265",
                                "probe_encoder_name": "libx265",
                                "family": "hevc",
                                "backend": "cpu",
                                "roles": ["cpu_fallback"],
                                "descriptor_flags_active": True,
                                "activation": [
                                    {
                                        "role": "cpu_fallback",
                                        "active": True,
                                        "descriptor_encoder": "libx265",
                                        "active_descriptor_encoder": "libx265",
                                        "reason": "descriptor-owned flags are active for cpu_fallback attempt",
                                    }
                                ],
                                "available": True,
                                "probed": True,
                                "runtime_probe_skipped": False,
                                "encoder_list_match": True,
                                "runtime_ok": True,
                                "reason": "encoder 'libx265' probe succeeded",
                            },
                        ],
                    }
                ),
                encoding="utf-8",
            )
            service, facade, resolved = _launch_preflight_facade(root)
            resolved.state_root = root / "State"
            resolved.config_data = {"NetworkRole": "standalone"}

            preflight = facade.get_launch_preflight(resolved, {"target": "pipeline", "mode": "validate"})

        rows = {row["key"]: row for row in preflight["checks"]}
        report = rows["encoder_capability_report"]
        self.assertTrue(preflight["can_request_start"])
        self.assertEqual(report["status"], "review")
        self.assertIn("hardware_runtime_skipped_count=1", report["evidence"])
        self.assertIn("active_hardware_unverified_count=1", report["evidence"])
        self.assertEqual(report["detail"][0]["hardware_runtime_verified_encoders"], [])
        self.assertEqual(report["detail"][0]["hardware_runtime_skipped_encoders"], ["hevc_nvenc"])
        self.assertEqual(report["detail"][0]["active_hardware_runtime_unverified_encoders"], ["hevc_nvenc"])
        self.assertIn("Active hardware descriptor rows lack runtime proof", "\n".join(report["detail"][0]["errors"]))
        self.assertEqual(
            report["detail"][0]["encoding_capability_facts"]["supported_encoder_backends"],
            ["copy", "cpu", "x265"],
        )

    def test_audit_preflight_skips_unc_library_root_exists_check(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            service, facade, resolved = _launch_preflight_facade(root)
            resolved.config_data = {
                "NetworkRole": "standalone",
                "Outsource": r"\\LAYNE-SERVER\Users\Layne\Videos\outsource\Movies",
            }

            original_exists = Path.exists

            def fail_only_for_unc(path: Path) -> bool:
                if str(path).startswith(r"\\LAYNE-SERVER"):
                    raise AssertionError("UNC existence check should not run")
                return original_exists(path)

            with patch.object(Path, "exists", fail_only_for_unc):
                audit = facade.get_launch_preflight(resolved, {"target": "audit"})

        self.assertEqual(audit["target"], "audit")
        self.assertNotEqual(audit["status"], "blocked")
        self.assertTrue(audit["can_request_start"])
        library_rows = [row for row in audit["checks"] if row["key"] == "library_root"]
        self.assertEqual(len(library_rows), 1)
        self.assertEqual(library_rows[0]["status"], "review")
        self.assertIn("network path not checked", library_rows[0]["evidence"])

    def test_launch_preflight_reports_schedule_and_lock_blocks_without_launching(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            service = DummyWorkflowFacadeService(root)
            service.save_app_state({"schedule_enabled": True, "schedule_grid": service.default_schedule_grid()})
            facade = MediaPipelineApplicationFacade(service, app_version="v5-test")
            resolved = _resolved(root)

            schedule_blocked = facade.get_launch_preflight(resolved, {"target": "pipeline", "mode": "continuous"})
            self.assertTrue(facade._process_launch_lock.acquire(blocking=False))  # type: ignore[attr-defined]
            try:
                lock_blocked = facade.get_launch_preflight(resolved, {"target": "pipeline", "mode": "validate"})
            finally:
                facade._process_launch_lock.release()  # type: ignore[attr-defined]

        self.assertEqual(schedule_blocked["status"], "blocked")
        self.assertFalse(schedule_blocked["can_request_start"])
        self.assertTrue(any(row["key"] == "schedule_gate" and row["status"] == "blocked" for row in schedule_blocked["checks"]))
        self.assertTrue(any("outside the allowed schedule" in " ".join(str(item) for item in row["detail"]) for row in schedule_blocked["checks"] if row["key"] == "schedule_gate"))
        self.assertEqual(lock_blocked["status"], "blocked")
        self.assertFalse(lock_blocked["can_request_start"])
        self.assertTrue(any(row["key"] == "process_launch_lock" and row["status"] == "blocked" for row in lock_blocked["checks"]))
        self.assertFalse(hasattr(service, "started_pipeline"))

    def test_launch_preflight_reports_continuous_schedule_stop_watcher_boundary(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            service = DummyWorkflowFacadeService(root)
            service.save_app_state({"schedule_enabled": True, "schedule_grid": service.default_schedule_grid()})
            service.evaluate_schedule = lambda _enabled, _grid: {  # type: ignore[method-assign]
                "enabled": True,
                "allowed_now": True,
                "status_text": "Schedule: Allowed now until Thursday 11:30 PM",
                "current_window_end": "2026-05-14T23:30:00",
                "next_allowed_start": "2026-05-14T22:00:00",
                "next_allowed_end": "2026-05-14T23:30:00",
                "next_transition": "2026-05-14T23:30:00",
            }
            facade = MediaPipelineApplicationFacade(service, app_version="v5-test")
            resolved = _resolved(root)

            preflight = facade.get_launch_preflight(resolved, {"target": "pipeline", "mode": "continuous"})
            ignored = facade.get_launch_preflight(
                resolved,
                {"target": "pipeline", "mode": "continuous", "schedule_override": "ignore"},
            )

        watcher_rows = [row for row in preflight["checks"] if row["key"] == "continuous_schedule_stop_watcher"]
        ignored_watcher = [row for row in ignored["checks"] if row["key"] == "continuous_schedule_stop_watcher"]
        self.assertNotEqual(preflight["status"], "blocked")
        self.assertTrue(preflight["can_request_start"])
        self.assertEqual(len(watcher_rows), 1)
        self.assertEqual(watcher_rows[0]["status"], "ready")
        self.assertIn("backend watcher available", watcher_rows[0]["evidence"])
        self.assertIn("2026-05-14T23:30:00", watcher_rows[0]["evidence"])
        self.assertEqual(ignored["status"], "high review")
        self.assertTrue(ignored["can_request_start"])
        self.assertEqual(ignored_watcher[0]["status"], "high review")
        self.assertIn("Ignore Schedule", ignored_watcher[0]["action"])
