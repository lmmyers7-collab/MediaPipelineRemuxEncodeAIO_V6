from __future__ import annotations

from datetime import datetime, timedelta, timezone, UTC
import json
import logging
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path
from types import SimpleNamespace

from mediapipeline.tools.paths import find_repo_root
from unittest.mock import patch

sys.path.insert(0, str(find_repo_root(Path(__file__)) / "src"))

from mediapipeline.desktop.application import MediaPipelineApplicationFacade
from mediapipeline.core.kernel.contracts import QueueAcceptedRunRow
from mediapipeline.core.processes.rerun_control import (
    _recovery_enrollment_can_be_superseded,
    _recovery_row_selectors,
    _rerun_recovery_key,
)
from mediapipeline.core.processes.rerun_facade import _spawn_stop_exit_verified
from mediapipeline.core.processes.rerun_results import rerun_results_payload
from mediapipeline.core.processes.rerun_lifecycle import transition_rerun_enrollment
from mediapipeline.core.processes.spawn_runner import (
    _ensure_process_ownership_finalization_context,
    _finalize_process_ownership_after_tree_proof,
    _mark_launch_cleanup_reconciliation_required,
)
from mediapipeline.core.status.run_monitor import RunMonitorStore
from tests.python.desktop.application_facade_test_support import (
    DummyProc,
    DummyWorkflowFacadeService,
    _resolved,
    write_test_media_file as _media_file,
)
from tests.python.desktop.application_facade_network_test_support import _sha256


def _retry_exhausted_continue_case(
    root: Path,
    *,
    service: DummyWorkflowFacadeService | None = None,
) -> tuple[MediaPipelineApplicationFacade, DummyWorkflowFacadeService, object, str, Path]:
    movie = _media_file(root, "Exactly Once Retry")
    source_stat = movie.stat()
    source_mtime = datetime.fromtimestamp(source_stat.st_mtime, UTC).isoformat()
    source_content_sha256 = _sha256(movie)
    csv_path = root / "rerun.csv"
    csv_path.write_text(
        "enabled,source_path,source_size,source_mtime_utc,source_identity_v2,source_content_sha256,source_content_sha256_algorithm\n"
        f"true,{movie},{source_stat.st_size},{source_mtime},exactly-once-source-v2,{source_content_sha256},sha256-full-file\n",
        encoding="utf-8",
    )
    selected_service = service or DummyWorkflowFacadeService(root)
    facade = MediaPipelineApplicationFacade(selected_service, app_version="v5-test")
    resolved = _resolved(root)
    resolved.local_base = root / "LocalBase"
    resolved.state_root = resolved.local_base / "State"
    manifest_root = resolved.local_base / "RerunManifests"
    manifest_root.mkdir(parents=True)
    manifest_path = manifest_root / "source-exactly-once.json"
    manifest_path.write_text(
        json.dumps(
            {
                "batch_id": "source-exactly-once",
                "status": "completed_with_failures",
                "csv_path": str(csv_path),
                "rows": [
                    {
                        "row_index": 0,
                        "status": "retry_exhausted",
                        "source_path": str(movie),
                        "source_size": source_stat.st_size,
                        "source_mtime_utc": source_mtime,
                        "source_identity_v2": "exactly-once-source-v2",
                        "source_content_sha256": source_content_sha256,
                        "source_content_sha256_algorithm": "sha256-full-file",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    manifest_key = rerun_results_payload(resolved)["manifests"][0]["manifest_key"]
    return facade, selected_service, resolved, manifest_key, manifest_path


class ApplicationFacadeProcessLaunchTests(unittest.TestCase):
    def test_pipeline_process_finalization_records_correlated_terminal_phase(self) -> None:
        class TerminalEvidenceService:
            def __init__(self) -> None:
                self.logger = logging.getLogger("terminal-evidence-test")
                self.registered: set[int] = set()
                self.records: list[dict[str, object]] = []

            def update_active_job_record(self, proc: object, **_kwargs: object) -> None:
                self.registered.add(id(proc))

            def _active_spawned_process_is_registered(self, proc: object) -> bool:
                return id(proc) in self.registered

            def _unregister_active_spawned_process(self, proc: object) -> bool:
                self.registered.discard(id(proc))
                return True

            def record_process_terminal_command_evidence(self, **evidence: object) -> None:
                self.records.append(dict(evidence))

        service = TerminalEvidenceService()
        proc = SimpleNamespace(pid=4321)
        service.registered.add(id(proc))
        _ensure_process_ownership_finalization_context(
            service,  # type: ignore[arg-type]
            proc,
            "pipeline",
            resolved=None,
            metadata={"command_id": "command-4321", "mode": "once"},
        )

        finalized = _finalize_process_ownership_after_tree_proof(proc, 0)

        self.assertTrue(finalized)
        self.assertEqual(
            service.records,
            [
                {
                    "command_id": "command-4321",
                    "phase": "completed",
                    "return_code": 0,
                    "pid": 4321,
                    "mode": "once",
                }
            ],
        )
        self.assertFalse(service._active_spawned_process_is_registered(proc))

    def test_pipeline_start_uses_existing_service_launch_path(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            service = DummyWorkflowFacadeService(root)
            facade = MediaPipelineApplicationFacade(service, app_version="v5-test")
            resolved = _resolved(root)
            resolved.source_movies = root / "Movies"
            resolved.source_movies.mkdir(parents=True)
            sample = resolved.source_movies / "sample.mkv"
            sample.write_bytes(b"media")

            result = facade.start_pipeline_process(
                resolved,
                {
                    "mode": "validate",
                    "sleep_seconds": 5,
                    "show_config": True,
                    "show_console": False,
                    "single_file": str(sample),
                },
            ).to_mapping()
            rejected = facade.start_pipeline_process(resolved, {"mode": "once", "extra_args": "-Danger"}).to_mapping()
            rejected_with_client_allow = facade.start_pipeline_process(
                resolved,
                {"mode": "once", "extra_args": "-Danger", "allow_extra_args": True},
            ).to_mapping()

        self.assertTrue(result["ok"])
        self.assertEqual(result["schema_version"], "desktop_command_result.v1")
        self.assertEqual(result["command"], "pipeline.start")
        self.assertEqual(result["data"]["mode"], "validate")
        self.assertEqual(result["data"]["pid"], 24680)
        self.assertEqual(service.started_pipeline["mode"], "validate")
        self.assertEqual(service.started_pipeline["sleep_seconds"], 5)
        self.assertEqual(service.started_pipeline["single_file"], str(sample))
        self.assertTrue(result["data"]["single_file_validation"]["ok"])
        self.assertEqual(result["data"]["single_file_validation"]["normalized_path"], str(sample))
        self.assertFalse(rejected["ok"])
        self.assertIn("Extra pipeline arguments", rejected["message"])
        self.assertFalse(rejected_with_client_allow["ok"])
        self.assertIn("Extra pipeline arguments", rejected_with_client_allow["message"])

    def test_backend_queue_run_once_returns_and_threads_stable_run_identity(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            service = DummyWorkflowFacadeService(root)
            facade = MediaPipelineApplicationFacade(service, app_version="v5-test")
            resolved = _resolved(root)
            resolved.state_root = root / "State"
            accepted_fingerprint = "accepted-plan-fingerprint-123"
            accepted_row = QueueAcceptedRunRow.from_mapping(
                {
                    "source_identity": "source-identity-1",
                    "source_identity_algorithm": "path_size_mtime_sha256.v1",
                    "source_path": str(root / "Movies" / "Django.Unchained.2012.1080p.BluRay.x264.YIFY.mkv"),
                    "display_name": "Django Unchained (2012).mkv",
                    "planned_display_name": "Django Unchained (2012).mkv",
                    "planned_display_name_source": "plex_destination_plan.v1",
                    "parent_context": str(root / "Movies"),
                    "run_queue_index": 1,
                    "run_queue_total": 1,
                    "route": "remux",
                    "route_reason_code": "copy_compatible",
                    "route_reason": "Already compatible",
                }
            )

            with patch.object(
                facade,
                "_normal_queue_scope_preflight_check",
                return_value={
                    "status": "ready",
                    "queue_plan_fingerprint": accepted_fingerprint,
                    "_accepted_run_rows": (accepted_row,),
                },
            ):
                result = facade.start_pipeline_process(
                    resolved,
                    {"mode": "once", "single_file": "", "_command_id": "command-123"},
                ).to_mapping()
            seeded = RunMonitorStore(resolved.state_root).read(result["data"]["run_id"])

        self.assertTrue(result["ok"])
        self.assertRegex(result["data"]["run_id"], r"^[0-9a-f]{32}$")
        self.assertEqual(result["data"]["accepted_queue_fingerprint"], accepted_fingerprint)
        self.assertEqual(result["data"]["run_monitor"]["schema_version"], "desktop_run_monitor_launch.v1")
        self.assertEqual(result["data"]["run_monitor"]["run_id"], result["data"]["run_id"])
        self.assertEqual(result["data"]["run_monitor"]["route"], "/api/run-monitor")
        self.assertEqual(result["data"]["run_monitor"]["acceptance_state"], "backend_accepted")
        self.assertEqual(
            result["data"]["run_monitor"]["expected_queue"]["fingerprint"],
            accepted_fingerprint,
        )
        self.assertEqual(service.started_pipeline["run_id"], result["data"]["run_id"])
        self.assertIsNotNone(seeded)
        assert seeded is not None
        self.assertEqual(seeded.run.lifecycle_state, "starting")
        self.assertEqual(seeded.run.command_id, "command-123")
        self.assertEqual([item.source_path for item in seeded.items], [accepted_row.source_path])
        self.assertEqual([item.display_name for item in seeded.items], ["Django Unchained (2012).mkv"])
        self.assertEqual(
            service.started_pipeline["expected_queue_plan_fingerprint"],
            accepted_fingerprint,
        )

    def test_backend_queue_seed_terminalizes_only_when_launch_cleanup_is_proven(self) -> None:
        accepted_row = QueueAcceptedRunRow.from_mapping(
            {
                "source_identity": "source-identity-1",
                "source_identity_algorithm": "path_size_mtime_sha256.v1",
                "source_path": r"C:\Media\Movie.mkv",
                "display_name": "Movie.mkv",
                "planned_display_name": "Movie.mkv",
                "planned_display_name_source": "plex_destination_plan.v1",
                "parent_context": r"C:\Media",
                "run_queue_index": 1,
                "run_queue_total": 1,
                "route": "remux",
                "route_reason_code": "copy_compatible",
                "route_reason": "Already compatible",
            }
        )

        for cleanup_verified, expected_state in ((True, "failed"), (False, "starting")):
            with self.subTest(cleanup_verified=cleanup_verified), tempfile.TemporaryDirectory() as raw_root:
                root = Path(raw_root)

                class FailingService(DummyWorkflowFacadeService):
                    def start_pipeline(
                        self,
                        *args: object,
                        _cleanup_verified: bool = cleanup_verified,
                        **kwargs: object,
                    ) -> DummyProc:  # type: ignore[override]
                        error = RuntimeError("synthetic post-Popen ownership failure")
                        error._mediapipeline_process_started = True  # type: ignore[attr-defined]
                        error._mediapipeline_cleanup_verified = _cleanup_verified  # type: ignore[attr-defined]
                        raise error

                service = FailingService(root)
                facade = MediaPipelineApplicationFacade(service, app_version="v5-test")
                resolved = _resolved(root)
                resolved.state_root = root / "State"
                run_id = "a" * 31 + ("1" if cleanup_verified else "2")
                with patch.object(
                    facade,
                    "_normal_queue_scope_preflight_check",
                    return_value={
                        "status": "ready",
                        "queue_plan_fingerprint": "accepted-plan",
                        "_accepted_run_rows": (accepted_row,),
                    },
                ):
                    result = facade.start_pipeline_process(
                        resolved,
                        {
                            "mode": "once",
                            "single_file": "",
                            "_command_id": "command-123",
                            "_run_id": run_id,
                        },
                    ).to_mapping()
                record = RunMonitorStore(resolved.state_root).read(run_id)

                self.assertFalse(result["ok"])
                self.assertIsNotNone(record)
                assert record is not None
                self.assertEqual(record.run.lifecycle_state, expected_state)
                if not cleanup_verified:
                    self.assertEqual(record.run.outcome.state, "pending")

    def test_queue_refresh_after_launch_acceptance_cannot_replace_seeded_membership(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            snapshot_path = root / "State" / "Progress" / "queue_snapshot.json"
            snapshot_path.parent.mkdir(parents=True)

            class RefreshingService(DummyWorkflowFacadeService):
                def start_pipeline(self, *args: object, **kwargs: object) -> DummyProc:  # type: ignore[override]
                    snapshot_path.write_text(
                        json.dumps(
                            {
                                "schema_version": "queue_plan_snapshot.v1",
                                "queue_plan_fingerprint": "replacement-plan",
                                "accepted_run_rows": [
                                    {
                                        "source_identity": "replacement-source",
                                        "source_path": r"C:\Media\Replacement.mkv",
                                    }
                                ],
                            }
                        ),
                        encoding="utf-8",
                    )
                    return super().start_pipeline(*args, **kwargs)

            service = RefreshingService(root)
            facade = MediaPipelineApplicationFacade(service, app_version="v5-test")
            resolved = _resolved(root)
            resolved.state_root = root / "State"
            resolved.queue_snapshot_path = snapshot_path
            accepted_row = QueueAcceptedRunRow.from_mapping(
                {
                    "source_identity": "accepted-source",
                    "source_identity_algorithm": "path_size_mtime_sha256.v1",
                    "source_path": r"C:\Media\Accepted.mkv",
                    "display_name": "Accepted.mkv",
                    "planned_display_name": "Accepted.mkv",
                    "planned_display_name_source": "plex_destination_plan.v1",
                    "parent_context": r"C:\Media",
                    "run_queue_index": 1,
                    "run_queue_total": 1,
                    "route": "remux",
                    "route_reason_code": "copy_compatible",
                    "route_reason": "Already compatible",
                }
            )
            with patch.object(
                facade,
                "_normal_queue_scope_preflight_check",
                return_value={
                    "status": "ready",
                    "queue_plan_fingerprint": "accepted-plan",
                    "_accepted_run_rows": (accepted_row,),
                },
            ):
                result = facade.start_pipeline_process(
                    resolved,
                    {"mode": "once", "_command_id": "command-race"},
                ).to_mapping()
            record = RunMonitorStore(resolved.state_root).read(result["data"]["run_id"])
            refreshed = json.loads(snapshot_path.read_text(encoding="utf-8"))

        self.assertTrue(result["ok"])
        self.assertEqual(refreshed["queue_plan_fingerprint"], "replacement-plan")
        self.assertIsNotNone(record)
        assert record is not None
        self.assertEqual(record.run.accepted_queue.fingerprint, "accepted-plan")
        self.assertEqual([item.source_identity.value for item in record.items], ["accepted-source"])
        self.assertEqual([item.source_path for item in record.items], [accepted_row.source_path])

    def test_pipeline_start_rejects_single_file_outside_configured_sources_or_invalid_media(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            service = DummyWorkflowFacadeService(root)
            facade = MediaPipelineApplicationFacade(service, app_version="v5-test")
            resolved = _resolved(root)
            resolved.source_movies = root / "Movies"
            resolved.source_movies.mkdir(parents=True)
            outside = root / "Downloads" / "sample.mkv"
            outside.parent.mkdir(parents=True)
            outside.write_bytes(b"media")
            directory = resolved.source_movies / "Folder"
            directory.mkdir()
            unsupported = resolved.source_movies / "notes.txt"
            unsupported.write_text("not media", encoding="utf-8")

            outside_result = facade.start_pipeline_process(
                resolved,
                {
                    "mode": "validate",
                    "single_file": str(outside),
                },
            ).to_mapping()
            missing_result = facade.start_pipeline_process(
                resolved,
                {"mode": "validate", "single_file": str(resolved.source_movies / "missing.mkv")},
            ).to_mapping()
            relative_result = facade.start_pipeline_process(
                resolved,
                {"mode": "validate", "single_file": "relative.mkv"},
            ).to_mapping()
            directory_result = facade.start_pipeline_process(
                resolved,
                {"mode": "validate", "single_file": str(directory)},
            ).to_mapping()
            unsupported_result = facade.start_pipeline_process(
                resolved,
                {"mode": "validate", "single_file": str(unsupported)},
            ).to_mapping()
            preflight = facade.get_launch_preflight(
                resolved,
                {"target": "pipeline", "mode": "validate", "single_file": str(outside)},
            )

        for result in (outside_result, missing_result, relative_result, directory_result, unsupported_result):
            with self.subTest(message=result["message"]):
                self.assertFalse(result["ok"])
                self.assertEqual(result["severity"], "error")
                self.assertEqual(result["data"]["schema_version"], "desktop_pipeline_single_file_launch_block.v1")
                self.assertFalse(result["data"]["validation"]["ok"])
                self.assertFalse(result["data"]["start_route_allowed"])
        self.assertFalse(outside_result["data"]["validation"]["under_source_root"])
        self.assertIn("outside", outside_result["data"]["validation"]["message"])
        self.assertIn("does not exist", missing_result["message"])
        self.assertIn("absolute path", relative_result["message"])
        self.assertIn("not a file", directory_result["message"])
        self.assertIn("unsupported media suffix", unsupported_result["message"])
        self.assertEqual(preflight["status"], "blocked")
        self.assertFalse(preflight["can_request_start"])
        preflight_rows = {row["key"]: row for row in preflight["checks"]}
        self.assertEqual(preflight_rows["single_file_scope"]["status"], "blocked")
        self.assertFalse(preflight_rows["single_file_scope"]["detail"][0]["under_source_root"])
        self.assertFalse(hasattr(service, "started_pipeline"))

    def test_pipeline_start_blocks_unverified_active_config(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            service = DummyWorkflowFacadeService(root)
            facade = MediaPipelineApplicationFacade(service, app_version="v5-test")
            resolved = _resolved(root)
            resolved.config_identity = {
                "schema_version": "desktop_config_identity.v1",
                "blocks_operations": True,
                "operator_status": "Config requires recovery",
                "reasons": ["Config key count 4 is below the operator threshold 80."],
            }

            result = facade.start_pipeline_process(resolved, {"mode": "validate"}).to_mapping()
            audit = facade.start_audit_process(resolved, {"library_root": str(root / "Outsource")}).to_mapping()
            rerun_csv = root / "rerun.csv"
            rerun_source = _media_file(root, "Movie")
            rerun_csv.write_text(f"enabled,source_path\ntrue,{rerun_source}\n", encoding="utf-8")
            rerun = facade.start_rerun_csv_process(resolved, {"csv_path": str(rerun_csv)}).to_mapping()
            preflight = facade.get_launch_preflight(resolved, {"target": "pipeline", "mode": "validate"})
            audit_preflight = facade.get_launch_preflight(resolved, {"target": "audit", "library_root": str(root / "Outsource")})
            rerun_preflight = facade.get_launch_preflight(resolved, {"target": "rerun", "csv_path": str(rerun_csv)})

        self.assertFalse(result["ok"])
        self.assertEqual(result["command"], "pipeline.start")
        self.assertEqual(result["severity"], "error")
        self.assertIn("not a verified operator config", result["message"])
        self.assertFalse(result["data"]["can_execute"])
        self.assertFalse(audit["ok"])
        self.assertFalse(rerun["ok"])
        self.assertIn("not a verified operator config", audit["message"])
        self.assertIn("not a verified operator config", rerun["message"])
        self.assertFalse(hasattr(service, "started_pipeline"))
        self.assertFalse(hasattr(service, "started_audit"))
        self.assertFalse(hasattr(service, "started_rerun"))
        self.assertEqual(preflight["status"], "blocked")
        self.assertFalse(preflight["can_request_start"])
        self.assertTrue(any(row["key"] == "config_identity" and row["status"] == "blocked" for row in preflight["checks"]))
        self.assertEqual(audit_preflight["status"], "blocked")
        self.assertEqual(rerun_preflight["status"], "blocked")

    def test_pipeline_start_respects_schedule_gate_before_web_launch_ui(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            service = DummyWorkflowFacadeService(root)
            service.save_app_state({"schedule_enabled": True, "schedule_grid": service.default_schedule_grid()})
            facade = MediaPipelineApplicationFacade(service, app_version="v5-test")
            resolved = _resolved(root)
            resolved.source_movies = root / "Movies"
            resolved.source_movies.mkdir()
            sample = resolved.source_movies / "sample.mkv"
            sample.write_bytes(b"media")

            blocked = facade.start_pipeline_process(resolved, {"mode": "continuous"}).to_mapping()
            run_once = facade.start_pipeline_process(
                resolved,
                {"mode": "continuous", "schedule_override": "run_once", "single_file": str(sample)},
            ).to_mapping()
            ignored = facade.start_pipeline_process(
                resolved,
                {"mode": "continuous", "schedule_override": "ignore"},
            ).to_mapping()

        self.assertFalse(blocked["ok"])
        self.assertIn("outside the allowed schedule", blocked["message"])
        self.assertEqual(blocked["refresh_hint"], "schedule")
        self.assertTrue(run_once["ok"])
        self.assertEqual(run_once["data"]["requested_mode"], "continuous")
        self.assertEqual(run_once["data"]["mode"], "once")
        self.assertEqual(run_once["data"]["schedule"]["override"], "run_once")
        self.assertTrue(ignored["ok"])
        self.assertEqual(ignored["data"]["mode"], "continuous")

    def test_pipeline_start_allows_scheduled_continuous_with_backend_watcher_available(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            service = DummyWorkflowFacadeService(root)
            grid = {day: [True] * 48 for day in service.default_schedule_grid()}
            service.save_app_state({"schedule_enabled": True, "schedule_grid": grid})
            facade = MediaPipelineApplicationFacade(service, app_version="v5-test")
            resolved = _resolved(root)
            resolved.source_movies = root / "Movies"
            resolved.source_movies.mkdir()
            sample = resolved.source_movies / "sample.mkv"
            sample.write_bytes(b"media")

            continuous = facade.start_pipeline_process(resolved, {"mode": "continuous"}).to_mapping()
            once = facade.start_pipeline_process(
                resolved,
                {"mode": "once", "single_file": str(sample)},
            ).to_mapping()

        self.assertTrue(continuous["ok"])
        self.assertEqual(continuous["data"]["mode"], "continuous")
        self.assertIn("no stop boundary", " ".join(continuous["data"]["launch_prep"]))
        self.assertTrue(once["ok"])
        self.assertEqual(once["data"]["mode"], "once")

    def test_audit_start_uses_existing_service_launch_path(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            service = DummyWorkflowFacadeService(root)
            facade = MediaPipelineApplicationFacade(service, app_version="v5-test")
            resolved = _resolved(root)
            resolved.config_data = {"NetworkRole": "standalone", "Outsource": str(root / "Outsource")}

            result = facade.start_audit_process(resolved, {"include_sidecars": True}).to_mapping()

        self.assertTrue(result["ok"])
        self.assertEqual(result["schema_version"], "desktop_command_result.v1")
        self.assertEqual(result["command"], "audit.start")
        self.assertEqual(result["data"]["pid"], 24681)
        self.assertTrue(service.started_audit["include_sidecars"])
        self.assertEqual(service.started_audit["library_root"], str(root / "Outsource"))

    def test_audit_start_can_run_while_pipeline_is_active_but_rejects_duplicate_audit(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            service = DummyWorkflowFacadeService(root)

            def related_processes(_resolved: object, *, job_kinds: set[str] | None = None) -> list[DummyProc]:
                if job_kinds is not None and "pipeline" not in job_kinds:
                    return []
                return [DummyProc(25001)]

            service.find_related_pipeline_processes = related_processes  # type: ignore[method-assign]
            facade = MediaPipelineApplicationFacade(service, app_version="v5-test")
            resolved = _resolved(root)
            resolved.config_data = {"NetworkRole": "standalone", "Outsource": str(root / "Outsource")}

            audit = facade.start_audit_process(resolved, {"include_sidecars": True}).to_mapping()
            audit_preflight = facade.get_launch_preflight(resolved, {"target": "audit", "include_sidecars": True})
            pipeline_preflight = facade.get_launch_preflight(resolved, {"target": "pipeline", "mode": "validate"})

            service_with_audit = DummyWorkflowFacadeService(root)
            service_with_audit.find_related_pipeline_processes = lambda _resolved, *, job_kinds=None: [DummyProc(25002)] if job_kinds is None or "audit" in job_kinds else []  # type: ignore[method-assign]
            facade_with_audit = MediaPipelineApplicationFacade(service_with_audit, app_version="v5-test")
            resolved_with_audit = _resolved(root)
            resolved_with_audit.config_data = {"NetworkRole": "standalone", "Outsource": str(root / "Outsource")}

            duplicate_audit = facade_with_audit.start_audit_process(resolved_with_audit, {}).to_mapping()

        self.assertTrue(audit["ok"])
        self.assertEqual(audit["command"], "audit.start")
        self.assertEqual(audit["data"]["pid"], 24681)
        self.assertEqual(service.started_audit["library_root"], str(root / "Outsource"))
        self.assertTrue(audit_preflight["can_request_start"])
        self.assertTrue(any(row["key"] == "active_work" and row["status"] == "ready" for row in audit_preflight["checks"]))
        self.assertFalse(pipeline_preflight["can_request_start"])
        self.assertTrue(any(row["key"] == "active_work" and row["status"] == "blocked" for row in pipeline_preflight["checks"]))
        self.assertFalse(duplicate_audit["ok"])
        self.assertIn("still running from this bundle", duplicate_audit["message"])
        self.assertFalse(hasattr(service_with_audit, "started_audit"))

    def test_audit_stop_requires_confirmation_and_marks_progress_stopped(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            service = DummyWorkflowFacadeService(root)
            facade = MediaPipelineApplicationFacade(service, app_version="v5-test")
            resolved = _resolved(root)
            resolved.audit_reports_path = root / "AuditReports"
            resolved.audit_reports_path.mkdir(parents=True)
            progress_path = resolved.audit_reports_path / "audit_progress.json"
            progress_path.write_text(
                json.dumps(
                    {
                        "status": "scanning",
                        "completed": False,
                        "failed": False,
                        "processed_files": 2371,
                        "total_files": 2973,
                        "percent_complete": 79.8,
                        "last_update": "2026-06-24T05:21:51Z",
                        "current_operation": "Scanning 2372 / 2973",
                    }
                ),
                encoding="utf-8",
            )
            calls: list[tuple[str, set[str] | None]] = []

            def kill_active_spawned_processes(*, job_kinds: set[str] | None = None) -> list[str]:
                calls.append(("active", job_kinds))
                return ["Force-killed audit process tree (PID 24681)."]

            def kill_related_pipeline_processes(
                _resolved: object,
                *,
                job_kinds: set[str] | None = None,
            ) -> list[str]:
                calls.append(("related", job_kinds))
                return ["Force-killed related MediaPipeline audit process tree (PID 25002)."]

            service.kill_active_spawned_processes = kill_active_spawned_processes  # type: ignore[method-assign]
            service.kill_related_pipeline_processes = kill_related_pipeline_processes  # type: ignore[method-assign]

            missing_confirm = facade.stop_audit_process(resolved, {}).to_mapping()
            stopped = facade.stop_audit_process(
                resolved,
                {"confirm_stop": True, "reason": "operator requested stop"},
            ).to_mapping()
            progress = json.loads(progress_path.read_text(encoding="utf-8"))

        self.assertFalse(missing_confirm["ok"])
        self.assertEqual(missing_confirm["command"], "audit.stop")
        self.assertIn("confirm_stop=true", missing_confirm["message"])
        self.assertTrue(stopped["ok"])
        self.assertEqual(stopped["command"], "audit.stop")
        self.assertEqual(stopped["data"]["requested_scope"], "audit")
        self.assertEqual(stopped["data"]["job_kinds"], ["audit"])
        self.assertEqual(stopped["data"]["stopped_process_tree_count"], 2)
        self.assertEqual(calls, [("active", {"audit"}), ("related", {"audit"})])
        self.assertEqual(progress["status"], "stopped")
        self.assertFalse(progress["completed"])
        self.assertFalse(progress["failed"])
        self.assertEqual(progress["processed_files"], 2371)
        self.assertEqual(progress["total_files"], 2973)
        self.assertTrue(progress["stop_requested"])
        self.assertEqual(progress["stop_reason"], "operator requested stop")
        self.assertIn("Stopped by operator", progress["current_operation"])

    def test_rerun_start_uses_existing_service_launch_path(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            csv_path = root / "rerun.csv"
            movie = _media_file(root, "Movie")
            csv_path.write_text(f"enabled,source_path\ntrue,{movie}\n", encoding="utf-8")
            service = DummyWorkflowFacadeService(root)
            facade = MediaPipelineApplicationFacade(service, app_version="v5-test")
            resolved = _resolved(root)

            missing_confirm = facade.start_rerun_csv_process(resolved, {"csv_path": str(csv_path)}).to_mapping()
            result = facade.start_rerun_csv_process(
                resolved,
                {"csv_path": str(csv_path), "confirm_replace_final": True},
            ).to_mapping()
            default_started = dict(service.started_rerun)
            pending_publish = facade.start_rerun_csv_process(
                resolved,
                {"csv_path": str(csv_path), "destination_mode": "pending_publish", "collision_policy": "suffix"},
            ).to_mapping()
            pending_started = dict(service.started_rerun)
            stale_original = facade.start_rerun_csv_process(
                resolved,
                {"csv_path": str(csv_path), "original_mode": "delete"},
            ).to_mapping()
            stale_started = dict(service.started_rerun)
            conflicting_plan = facade.start_rerun_csv_process(
                resolved,
                {"csv_path": str(csv_path), "dry_run": True, "plan_only": True, "confirm_replace_final": True},
            ).to_mapping()
            missing = facade.start_rerun_csv_process(resolved, {}).to_mapping()

        self.assertTrue(result["ok"])
        self.assertEqual(result["schema_version"], "desktop_command_result.v1")
        self.assertEqual(result["command"], "rerun.start")
        self.assertFalse(missing_confirm["ok"])
        self.assertIn("confirm_replace_final=true", missing_confirm["message"])
        self.assertEqual(result["data"]["pid"], 24682)
        self.assertFalse(result["data"]["dry_run"])
        self.assertFalse(result["data"]["plan_only"])
        self.assertEqual(default_started["return_mode"], "replace_original")
        self.assertEqual(default_started["execution_mode"], "one_at_a_time")
        self.assertEqual(default_started["destination_mode"], "auto_replace_clean_else_pending_review")
        self.assertEqual(default_started["collision_policy"], "replace_final")
        self.assertTrue(default_started["confirm_replace_final"])
        self.assertEqual(result["data"]["execution_mode"], "one_at_a_time")
        self.assertEqual(result["data"]["destination_mode"], "auto_replace_clean_else_pending_review")
        self.assertEqual(result["data"]["collision_policy"], "replace_final")
        self.assertTrue(result["data"]["confirm_replace_final"])
        self.assertTrue(pending_publish["ok"])
        self.assertEqual(pending_publish["data"]["return_mode"], "pending_publish")
        self.assertEqual(pending_publish["data"]["destination_mode"], "pending_publish")
        self.assertEqual(pending_started["return_mode"], "pending_publish")
        self.assertEqual(pending_started["destination_mode"], "pending_publish")
        self.assertFalse(pending_publish["data"]["confirm_source_overwrite"])
        self.assertFalse(pending_started["confirm_source_overwrite"])
        self.assertTrue(stale_original["ok"])
        self.assertEqual(stale_original["data"]["original_policy"], "keep")
        self.assertEqual(stale_started["original_policy"], "keep")
        self.assertFalse(stale_started["confirm_original_policy"])
        self.assertFalse(stale_started["confirm_delete_original"])
        self.assertFalse(conflicting_plan["ok"])
        self.assertIn("either dry_run or plan_only", conflicting_plan["message"])
        self.assertFalse(missing["ok"])
        self.assertIn("csv_path", missing["message"])

    def test_rerun_start_durably_enrolls_batch_before_spawn_with_one_correlation_chain(self) -> None:
        class EnrollmentProbeService(DummyWorkflowFacadeService):
            def start_rerun_csv(self, resolved: object, csv_path: Path, **kwargs: object) -> DummyProc:  # type: ignore[override]
                enrollment_path = Path(str(kwargs["enrollment_path"]))
                self.enrollment_existed_before_spawn = enrollment_path.exists()
                self.enrollment_before_spawn = json.loads(enrollment_path.read_text(encoding="utf-8"))
                self.started_rerun = {"resolved": resolved, "csv_path": csv_path, **kwargs}
                proc = DummyProc(24682)
                self.started_rerun_proc = proc
                return proc

        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            local_base = root / "LocalBase"
            movie = _media_file(root, "Movie")
            csv_path = root / "rerun.csv"
            csv_path.write_text(f"enabled,source_path,source_size\ntrue,{movie},{movie.stat().st_size}\n", encoding="utf-8")
            service = EnrollmentProbeService(root)
            facade = MediaPipelineApplicationFacade(service, app_version="v5-test")
            resolved = _resolved(root)
            resolved.local_base = local_base
            resolved.state_root = local_base / "State"

            result = facade.start_rerun_csv_process(
                resolved,
                {
                    "_command_id": "command-rerun-123",
                    "csv_path": str(csv_path),
                    "confirm_replace_final": True,
                },
            ).to_mapping()

            enrollment_path = Path(str(result["data"]["enrollment_path"]))
            enrollment = json.loads(enrollment_path.read_text(encoding="utf-8"))
            manifest_path = Path(str(result["data"]["manifest_path"]))

        self.assertTrue(result["ok"])
        self.assertTrue(service.enrollment_existed_before_spawn)
        self.assertTrue(result["data"]["durably_enrolled"])
        self.assertFalse(result["data"]["inserted_into_normal_queue"])
        self.assertEqual(result["data"]["queue_source"], "csv_rerun")
        self.assertEqual(result["data"]["lifecycle_state"], "process_spawned")
        self.assertNotIn("Started", result["message"])
        self.assertEqual(result["data"]["command_id"], "command-rerun-123")
        self.assertEqual(enrollment["command_id"], "command-rerun-123")
        self.assertEqual(enrollment["launch_id"], result["data"]["launch_id"])
        self.assertEqual(enrollment["batch_id"], result["data"]["batch_id"])
        self.assertEqual(enrollment["manifest_path"], str(manifest_path))
        self.assertEqual(enrollment_path, Path(str(service.started_rerun["enrollment_path"])))
        self.assertEqual(manifest_path, Path(str(service.started_rerun["manifest_path"])))
        self.assertEqual(service.started_rerun["command_id"], "command-rerun-123")
        self.assertEqual(service.started_rerun["launch_id"], enrollment["launch_id"])
        self.assertEqual(service.started_rerun["batch_id"], enrollment["batch_id"])
        self.assertEqual(service.enrollment_before_spawn["status"], "accepted")
        self.assertEqual(enrollment["status"], "process_spawned")
        self.assertEqual(len(enrollment["rows"]), 1)
        self.assertEqual(enrollment["rows"][0]["status"], "process_spawned")
        self.assertEqual(enrollment["rows"][0]["source_path"], str(movie))

    def test_continue_retry_exhausted_uses_hardened_start_and_new_correlation_chain(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            movie = _media_file(root, "Retry Exhausted")
            source_stat = movie.stat()
            source_mtime = datetime.fromtimestamp(source_stat.st_mtime, UTC).isoformat()
            source_content_sha256 = _sha256(movie)
            csv_path = root / "rerun.csv"
            csv_path.write_text(
                "enabled,source_path,source_size,source_mtime_utc,source_identity_v2,source_content_sha256,source_content_sha256_algorithm\n"
                f"true,{movie},{source_stat.st_size},{source_mtime},stable-source-v2,{source_content_sha256},sha256-full-file\n",
                encoding="utf-8",
            )
            service = DummyWorkflowFacadeService(root)
            facade = MediaPipelineApplicationFacade(service, app_version="v5-test")
            resolved = _resolved(root)
            resolved.local_base = root / "LocalBase"
            resolved.state_root = resolved.local_base / "State"
            manifest_root = resolved.local_base / "RerunManifests"
            manifest_root.mkdir(parents=True)
            source_batch_id = "rerun-source-completed-with-failures"
            manifest_path = manifest_root / f"{source_batch_id}.json"
            manifest_path.write_text(
                json.dumps(
                    {
                        "batch_id": source_batch_id,
                        "status": "completed_with_failures",
                        "csv_path": str(csv_path),
                        "execution_mode": "one_at_a_time",
                        "destination_mode": "pending_publish",
                        "collision_policy": "suffix",
                        "rows": [
                            {
                                "row_index": 0,
                                "status": "retry_exhausted",
                                "source_path": str(movie),
                                "source_size": source_stat.st_size,
                                "source_mtime_utc": source_mtime,
                                "source_identity_v2": "stable-source-v2",
                                "source_content_sha256": source_content_sha256,
                                "source_content_sha256_algorithm": "sha256-full-file",
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            manifest_key = rerun_results_payload(resolved)["manifests"][0]["manifest_key"]

            result = facade.continue_rerun_pending_rows(
                resolved,
                {
                    "_command_id": "command-retry-exhausted-123",
                    "manifest_key": manifest_key,
                    "request_id": "retry-request-123",
                    "confirm_continue": True,
                },
            ).to_mapping()
            launch = result["data"]["launch"]
            launch_data = launch["data"]
            enrollment = json.loads(Path(launch_data["enrollment_path"]).read_text(encoding="utf-8"))

        self.assertTrue(result["ok"])
        self.assertIn("Accepted", result["message"])
        self.assertIn("durably enrolled", result["message"])
        self.assertNotIn("Started", result["message"])
        self.assertTrue(result["data"]["launches_work"])
        self.assertTrue(result["data"]["durably_enrolled"])
        self.assertEqual(result["data"]["recovery_scope"], "retry_exhausted")
        self.assertEqual(result["data"]["command_id"], "command-retry-exhausted-123")
        self.assertEqual(result["data"]["batch_id"], launch_data["batch_id"])
        self.assertEqual(launch_data["command_id"], "command-retry-exhausted-123")
        self.assertNotEqual(launch_data["batch_id"], source_batch_id)
        self.assertEqual(enrollment["command_id"], "command-retry-exhausted-123")
        self.assertEqual(enrollment["batch_id"], launch_data["batch_id"])
        self.assertEqual(enrollment["launch_id"], launch_data["launch_id"])
        self.assertEqual(enrollment["recovery_request_id"], "retry-request-123")
        self.assertEqual(enrollment["recovery_source_batch_id"], source_batch_id)
        self.assertEqual(enrollment["recovery_source_manifest_path"], str(manifest_path))
        self.assertEqual(enrollment["recovery_source_manifest_key"], manifest_key)
        self.assertEqual(enrollment["recovery_scope"], "retry_exhausted")
        self.assertEqual(enrollment["recovery_row_selectors"][0]["row_index"], 0)
        self.assertEqual(
            enrollment["recovery_row_selectors"][0]["source_content_sha256"],
            source_content_sha256,
        )
        self.assertTrue(enrollment["recovery_key"])
        self.assertEqual(enrollment["rows"][0]["source_identity_v2"], "stable-source-v2")
        self.assertEqual(enrollment["rows"][0]["source_content_sha256"], source_content_sha256)

    def test_continue_retry_is_restart_durable_and_exactly_once_across_sequential_requests(self) -> None:
        class CountingService(DummyWorkflowFacadeService):
            def __init__(self, root: Path) -> None:
                super().__init__(root)
                self.rerun_start_count = 0

            def start_rerun_csv(self, resolved: object, csv_path: Path, **kwargs: object) -> DummyProc:  # type: ignore[override]
                self.rerun_start_count += 1
                return super().start_rerun_csv(resolved, csv_path, **kwargs)  # type: ignore[arg-type]

        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            counting_service = CountingService(root)
            facade, service, resolved, manifest_key, _manifest_path = _retry_exhausted_continue_case(
                root,
                service=counting_service,
            )
            request = {
                "_command_id": "command-exactly-once-first",
                "manifest_key": manifest_key,
                "request_id": "recovery-request-stable",
                "confirm_continue": True,
            }

            first = facade.continue_rerun_pending_rows(resolved, request).to_mapping()  # type: ignore[arg-type]
            service.started_rerun_proc.complete()
            same_request = facade.continue_rerun_pending_rows(
                resolved,  # type: ignore[arg-type]
                {**request, "_command_id": "command-exactly-once-replay"},
            ).to_mapping()
            different_request = facade.continue_rerun_pending_rows(
                resolved,  # type: ignore[arg-type]
                {**request, "_command_id": "command-exactly-once-other", "request_id": "recovery-request-other"},
            ).to_mapping()

        self.assertTrue(first["ok"])
        self.assertTrue(first["data"]["launches_work"])
        self.assertTrue(same_request["ok"])
        self.assertTrue(same_request["data"]["idempotent_replay"])
        self.assertFalse(same_request["data"]["launches_work"])
        self.assertEqual(same_request["data"]["batch_id"], first["data"]["batch_id"])
        self.assertFalse(different_request["ok"])
        self.assertTrue(different_request["data"]["already_enrolled"])
        self.assertEqual(different_request["data"]["batch_id"], first["data"]["batch_id"])
        self.assertIn("rerun_recovery_already_enrolled", different_request["errors"])
        self.assertEqual(counting_service.rerun_start_count, 1)

    def test_continue_retry_rejects_copied_v2_manifest_after_valid_original_launch(self) -> None:
        class CountingService(DummyWorkflowFacadeService):
            def __init__(self, root: Path) -> None:
                super().__init__(root)
                self.rerun_start_count = 0

            def start_rerun_csv(self, resolved: object, csv_path: Path, **kwargs: object) -> DummyProc:  # type: ignore[override]
                self.rerun_start_count += 1
                return super().start_rerun_csv(resolved, csv_path, **kwargs)  # type: ignore[arg-type]

        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            service = CountingService(root)
            facade, _service, resolved, manifest_key, manifest_path = _retry_exhausted_continue_case(
                root,
                service=service,
            )
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest.update(
                {
                    "schema_version": "rerun_batch_manifest.v2",
                    "command_id": "source-command-v2",
                    "launch_id": "source-launch-v2",
                    "manifest_path": str(manifest_path),
                }
            )
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

            first = facade.continue_rerun_pending_rows(
                resolved,  # type: ignore[arg-type]
                {
                    "_command_id": "copied-v2-first-command",
                    "manifest_key": manifest_key,
                    "request_id": "copied-v2-first-request",
                    "confirm_continue": True,
                },
            ).to_mapping()
            service.started_rerun_proc.complete()
            copied_path = manifest_path.with_name("copied-v2-manifest.json")
            copied_path.write_text(manifest_path.read_text(encoding="utf-8"), encoding="utf-8")
            manifest_path.unlink()
            copied_projection = next(
                item
                for item in rerun_results_payload(resolved)["manifests"]
                if item["manifest_path"] == str(copied_path)
            )

            copied = facade.continue_rerun_pending_rows(
                resolved,  # type: ignore[arg-type]
                {
                    "_command_id": "copied-v2-second-command",
                    "manifest_key": copied_projection["manifest_key"],
                    "request_id": "copied-v2-second-request",
                    "confirm_continue": True,
                },
            ).to_mapping()

        self.assertTrue(first["ok"])
        self.assertFalse(copied["ok"])
        self.assertIn("rerun_manifest_path_mismatch", copied["errors"])
        self.assertEqual(service.rerun_start_count, 1)

    def test_continue_retry_copied_v1_manifest_reuses_logical_exactly_once_namespace(self) -> None:
        class CountingService(DummyWorkflowFacadeService):
            def __init__(self, root: Path) -> None:
                super().__init__(root)
                self.rerun_start_count = 0

            def start_rerun_csv(self, resolved: object, csv_path: Path, **kwargs: object) -> DummyProc:  # type: ignore[override]
                self.rerun_start_count += 1
                return super().start_rerun_csv(resolved, csv_path, **kwargs)  # type: ignore[arg-type]

        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            service = CountingService(root)
            facade, _service, resolved, manifest_key, manifest_path = _retry_exhausted_continue_case(
                root,
                service=service,
            )
            first = facade.continue_rerun_pending_rows(
                resolved,  # type: ignore[arg-type]
                {
                    "_command_id": "copied-v1-first-command",
                    "manifest_key": manifest_key,
                    "request_id": "copied-v1-first-request",
                    "confirm_continue": True,
                },
            ).to_mapping()
            service.started_rerun_proc.complete()
            copied_path = manifest_path.with_name("copied-v1-manifest.json")
            copied_path.write_text(manifest_path.read_text(encoding="utf-8"), encoding="utf-8")
            copied_projection = next(
                item
                for item in rerun_results_payload(resolved)["manifests"]
                if item["manifest_path"] == str(copied_path)
            )

            copied = facade.continue_rerun_pending_rows(
                resolved,  # type: ignore[arg-type]
                {
                    "_command_id": "copied-v1-second-command",
                    "manifest_key": copied_projection["manifest_key"],
                    "request_id": "copied-v1-second-request",
                    "confirm_continue": True,
                },
            ).to_mapping()

        self.assertTrue(first["ok"])
        self.assertFalse(copied["ok"])
        self.assertIn("rerun_recovery_already_enrolled", copied["errors"])
        self.assertEqual(copied["data"]["recovery_root_key"], first["data"]["recovery_root_key"])
        self.assertEqual(service.rerun_start_count, 1)

    def test_continue_retry_copied_v1_windows_equivalent_path_cannot_split_namespace(self) -> None:
        class CountingService(DummyWorkflowFacadeService):
            def __init__(self, root: Path) -> None:
                super().__init__(root)
                self.rerun_start_count = 0

            def start_rerun_csv(self, resolved: object, csv_path: Path, **kwargs: object) -> DummyProc:  # type: ignore[override]
                self.rerun_start_count += 1
                return super().start_rerun_csv(resolved, csv_path, **kwargs)  # type: ignore[arg-type]

        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            service = CountingService(root)
            facade, _service, resolved, manifest_key, manifest_path = _retry_exhausted_continue_case(
                root,
                service=service,
            )
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            source_path = Path(str(manifest["rows"][0]["source_path"]))
            equivalent_parent = str(source_path.parent).upper().replace("\\", "/")
            equivalent_source_path = f"{equivalent_parent}/./{source_path.name.swapcase()}"
            equivalent_manifest = json.loads(json.dumps(manifest))
            equivalent_manifest["rows"][0]["source_path"] = equivalent_source_path

            original_selectors = _recovery_row_selectors(manifest["rows"])
            equivalent_selectors = _recovery_row_selectors(equivalent_manifest["rows"])
            distinct_manifest = json.loads(json.dumps(manifest))
            distinct_manifest["rows"][0]["source_path"] = str(source_path.with_name("Different.mkv"))
            distinct_selectors = _recovery_row_selectors(distinct_manifest["rows"])

            first = facade.continue_rerun_pending_rows(
                resolved,  # type: ignore[arg-type]
                {
                    "_command_id": "equivalent-v1-first-command",
                    "manifest_key": manifest_key,
                    "request_id": "equivalent-v1-first-request",
                    "confirm_continue": True,
                },
            ).to_mapping()
            service.started_rerun_proc.complete()
            copied_path = manifest_path.with_name("copied-equivalent-v1-manifest.json")
            copied_path.write_text(json.dumps(equivalent_manifest), encoding="utf-8")
            copied_projection = next(
                item
                for item in rerun_results_payload(resolved)["manifests"]
                if item["manifest_path"] == str(copied_path)
            )
            copied = facade.continue_rerun_pending_rows(
                resolved,  # type: ignore[arg-type]
                {
                    "_command_id": "equivalent-v1-second-command",
                    "manifest_key": copied_projection["manifest_key"],
                    "request_id": "equivalent-v1-second-request",
                    "confirm_continue": True,
                },
            ).to_mapping()

        self.assertEqual(equivalent_selectors, original_selectors)
        self.assertNotEqual(distinct_selectors, original_selectors)
        self.assertTrue(first["ok"])
        self.assertFalse(copied["ok"])
        self.assertIn("rerun_recovery_already_enrolled", copied["errors"])
        self.assertEqual(copied["data"]["recovery_root_key"], first["data"]["recovery_root_key"])
        self.assertEqual(service.rerun_start_count, 1)

    def test_continue_retry_row_reordering_keeps_same_exactly_once_namespace(self) -> None:
        class CountingService(DummyWorkflowFacadeService):
            def __init__(self, root: Path) -> None:
                super().__init__(root)
                self.rerun_start_count = 0

            def start_rerun_csv(self, resolved: object, csv_path: Path, **kwargs: object) -> DummyProc:  # type: ignore[override]
                self.rerun_start_count += 1
                return super().start_rerun_csv(resolved, csv_path, **kwargs)  # type: ignore[arg-type]

        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            service = CountingService(root)
            facade = MediaPipelineApplicationFacade(service, app_version="v5-test")
            resolved = _resolved(root)
            resolved.local_base = root / "LocalBase"
            resolved.state_root = resolved.local_base / "State"
            sources = [_media_file(root, "Reorder A"), _media_file(root, "Reorder B")]
            csv_path = root / "rerun-reordered.csv"
            csv_rows: list[str] = []
            manifest_rows: list[dict[str, object]] = []
            for row_index, source in enumerate(sources):
                source_stat = source.stat()
                source_mtime = datetime.fromtimestamp(source_stat.st_mtime, UTC).isoformat()
                source_hash = _sha256(source)
                source_identity = f"reordered-source-{row_index}-v2"
                csv_rows.append(
                    f"true,{source},{source_stat.st_size},{source_mtime},{source_identity},{source_hash},sha256-full-file"
                )
                manifest_rows.append(
                    {
                        "row_index": row_index,
                        "status": "retry_exhausted",
                        "source_path": str(source),
                        "source_size": source_stat.st_size,
                        "source_mtime_utc": source_mtime,
                        "source_identity_v2": source_identity,
                        "source_content_sha256": source_hash,
                        "source_content_sha256_algorithm": "sha256-full-file",
                    }
                )
            csv_path.write_text(
                "enabled,source_path,source_size,source_mtime_utc,source_identity_v2,source_content_sha256,source_content_sha256_algorithm\n"
                + "\n".join(csv_rows)
                + "\n",
                encoding="utf-8",
            )
            manifest_root = resolved.local_base / "RerunManifests"
            manifest_root.mkdir(parents=True)
            manifest_path = manifest_root / "reordered-v2.json"
            manifest = {
                "schema_version": "rerun_batch_manifest.v2",
                "batch_id": "reordered-v2",
                "command_id": "reordered-source-command",
                "launch_id": "reordered-source-launch",
                "manifest_path": str(manifest_path),
                "status": "completed_with_failures",
                "csv_path": str(csv_path),
                "rows": list(reversed(manifest_rows)),
            }
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            manifest_key = rerun_results_payload(resolved)["manifests"][0]["manifest_key"]

            first = facade.continue_rerun_pending_rows(
                resolved,
                {
                    "_command_id": "reordered-first-command",
                    "manifest_key": manifest_key,
                    "request_id": "reordered-first-request",
                    "confirm_continue": True,
                },
            ).to_mapping()
            service.started_rerun_proc.complete()
            first_enrollment_path = Path(first["data"]["enrollment_path"])
            first_enrollment = json.loads(first_enrollment_path.read_text(encoding="utf-8"))
            legacy_ordered_selectors = _recovery_row_selectors(
                list(reversed(manifest_rows)),
                canonical_order=False,
            )
            legacy_root_key = _rerun_recovery_key(
                manifest_key=manifest_key,
                recovery_scope="retry_exhausted",
                row_selectors=legacy_ordered_selectors,
            )
            first_enrollment.update(
                {
                    "recovery_key": legacy_root_key,
                    "recovery_root_key": legacy_root_key,
                    "recovery_row_selectors": legacy_ordered_selectors,
                }
            )
            first_enrollment_path.write_text(json.dumps(first_enrollment), encoding="utf-8")
            manifest["rows"] = manifest_rows
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            second = facade.continue_rerun_pending_rows(
                resolved,
                {
                    "_command_id": "reordered-second-command",
                    "manifest_key": manifest_key,
                    "request_id": "reordered-second-request",
                    "confirm_continue": True,
                },
            ).to_mapping()

        self.assertTrue(first["ok"])
        self.assertFalse(second["ok"])
        self.assertIn("rerun_recovery_already_enrolled", second["errors"])
        self.assertEqual(service.rerun_start_count, 1)

    def test_continue_retry_supersedes_only_exit_verified_failed_before_manifest_generation(self) -> None:
        class CountingService(DummyWorkflowFacadeService):
            def __init__(self, root: Path) -> None:
                super().__init__(root)
                self.rerun_start_count = 0

            def start_rerun_csv(self, resolved: object, csv_path: Path, **kwargs: object) -> DummyProc:  # type: ignore[override]
                self.rerun_start_count += 1
                return super().start_rerun_csv(resolved, csv_path, **kwargs)  # type: ignore[arg-type]

        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            counting_service = CountingService(root)
            facade, service, resolved, manifest_key, _manifest_path = _retry_exhausted_continue_case(
                root,
                service=counting_service,
            )
            first_request = {
                "_command_id": "command-recovery-generation-one",
                "manifest_key": manifest_key,
                "request_id": "recovery-request-generation-one",
                "confirm_continue": True,
            }
            first = facade.continue_rerun_pending_rows(resolved, first_request).to_mapping()  # type: ignore[arg-type]
            service.started_rerun_proc.complete()
            first_enrollment_path = Path(first["data"]["enrollment_path"])
            transition_rerun_enrollment(
                first_enrollment_path,
                "failed_before_manifest",
                expected_states={"process_spawned"},
                reason_code="rerun_process_exit_nonzero",
                reason="Child exited before creating an execution manifest.",
                extra_fields={"process_exit_verified": True, "duplicate_launch_blocked": False},
            )
            same_request = facade.continue_rerun_pending_rows(
                resolved,  # type: ignore[arg-type]
                {**first_request, "_command_id": "command-recovery-generation-one-replay"},
            ).to_mapping()
            second = facade.continue_rerun_pending_rows(
                resolved,  # type: ignore[arg-type]
                {
                    **first_request,
                    "_command_id": "command-recovery-generation-two",
                    "request_id": "recovery-request-generation-two",
                },
            ).to_mapping()

            self.assertTrue(first["ok"])
            self.assertTrue(same_request["ok"])
            self.assertTrue(same_request["data"]["idempotent_replay"])
            self.assertFalse(same_request["data"]["launches_work"])
            self.assertEqual(same_request["data"]["batch_id"], first["data"]["batch_id"])
            self.assertTrue(second["ok"])

            second_enrollment_path = Path(second["data"]["enrollment_path"])
            second_enrollment = json.loads(second_enrollment_path.read_text(encoding="utf-8"))
            self.assertNotEqual(second["data"]["batch_id"], first["data"]["batch_id"])
            self.assertNotEqual(second_enrollment_path, first_enrollment_path)
            self.assertEqual(second["data"]["recovery_generation"], 2)
            self.assertEqual(
                second["data"]["recovery_supersedes_enrollment_path"],
                str(first_enrollment_path),
            )
            self.assertNotEqual(second["data"]["recovery_key"], first["data"]["recovery_key"])
            self.assertEqual(second_enrollment["recovery_key"], second["data"]["recovery_key"])
            self.assertEqual(
                second_enrollment["recovery_root_key"],
                second["data"]["recovery_root_key"],
            )
            self.assertEqual(second_enrollment["recovery_generation"], 2)
            self.assertEqual(
                second_enrollment["recovery_supersedes_enrollment_path"],
                str(first_enrollment_path),
            )
            self.assertEqual(
                second_enrollment["recovery_supersedes_recovery_key"],
                first["data"]["recovery_key"],
            )
            self.assertEqual(
                second_enrollment["recovery_supersedes_batch_id"],
                first["data"]["batch_id"],
            )

            live_duplicate = facade.continue_rerun_pending_rows(
                resolved,  # type: ignore[arg-type]
                {
                    **first_request,
                    "_command_id": "command-recovery-generation-three-live",
                    "request_id": "recovery-request-generation-three-live",
                },
            ).to_mapping()
            self.assertFalse(live_duplicate["ok"])
            self.assertIn("rerun_recovery_already_enrolled", live_duplicate["errors"])
            self.assertEqual(counting_service.rerun_start_count, 2)

            service.started_rerun_proc.complete()
            transition_rerun_enrollment(
                second_enrollment_path,
                "completed",
                expected_states={"process_spawned"},
            )
            completed_duplicate = facade.continue_rerun_pending_rows(
                resolved,  # type: ignore[arg-type]
                {
                    **first_request,
                    "_command_id": "command-recovery-generation-three-completed",
                    "request_id": "recovery-request-generation-three-completed",
                },
            ).to_mapping()

        self.assertFalse(completed_duplicate["ok"])
        self.assertIn("rerun_recovery_already_enrolled", completed_duplicate["errors"])
        self.assertEqual(counting_service.rerun_start_count, 2)

    def test_continue_retry_does_not_supersede_stale_failed_before_manifest_with_execution_evidence(self) -> None:
        class CountingService(DummyWorkflowFacadeService):
            def __init__(self, root: Path) -> None:
                super().__init__(root)
                self.rerun_start_count = 0

            def start_rerun_csv(self, resolved: object, csv_path: Path, **kwargs: object) -> DummyProc:  # type: ignore[override]
                self.rerun_start_count += 1
                return super().start_rerun_csv(resolved, csv_path, **kwargs)  # type: ignore[arg-type]

        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            counting_service = CountingService(root)
            facade, service, resolved, manifest_key, _manifest_path = _retry_exhausted_continue_case(
                root,
                service=counting_service,
            )
            first_request = {
                "_command_id": "command-stale-pre-manifest-one",
                "manifest_key": manifest_key,
                "request_id": "recovery-request-stale-pre-manifest-one",
                "confirm_continue": True,
            }
            first = facade.continue_rerun_pending_rows(resolved, first_request).to_mapping()  # type: ignore[arg-type]
            service.started_rerun_proc.complete()
            enrollment_path = Path(first["data"]["enrollment_path"])
            execution_manifest_path = Path(first["data"]["manifest_path"])
            execution_manifest_path.parent.mkdir(parents=True, exist_ok=True)
            execution_manifest_path.write_text(
                json.dumps(
                    {
                        "schema_version": "rerun_batch_manifest.v2",
                        "command_id": first["data"]["command_id"],
                        "launch_id": first["data"]["launch_id"],
                        "batch_id": first["data"]["batch_id"],
                        "enrollment_path": str(enrollment_path),
                        "manifest_path": str(execution_manifest_path),
                        "status": "failed",
                        "lifecycle_state": "terminal",
                        "rows": [],
                    }
                ),
                encoding="utf-8",
            )
            transition_rerun_enrollment(
                enrollment_path,
                "failed_before_manifest",
                expected_states={"process_spawned"},
                reason_code="stale_pre_manifest_label",
                reason="The enrollment label is stale even though execution evidence exists.",
                extra_fields={"process_exit_verified": True, "duplicate_launch_blocked": False},
            )

            second = facade.continue_rerun_pending_rows(
                resolved,  # type: ignore[arg-type]
                {
                    **first_request,
                    "_command_id": "command-stale-pre-manifest-two",
                    "request_id": "recovery-request-stale-pre-manifest-two",
                },
            ).to_mapping()

        self.assertFalse(second["ok"])
        self.assertIn("rerun_recovery_already_enrolled", second["errors"])
        self.assertEqual(counting_service.rerun_start_count, 1)

    def test_recovery_supersession_requires_explicit_exit_and_duplicate_guard_booleans(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            absent_manifest = Path(raw_root) / "absent-manifest.json"
            valid = {
                "lifecycle_state": "failed_before_manifest",
                "process_exit_verified": True,
                "duplicate_launch_blocked": False,
                "manifest_path": str(absent_manifest),
            }
            cases: list[tuple[str, dict[str, object]]] = [
                ("missing_process_exit_verified", {"process_exit_verified": None}),
                ("null_process_exit_verified", {"process_exit_verified": None}),
                ("string_process_exit_verified", {"process_exit_verified": "true"}),
                ("missing_duplicate_launch_blocked", {"duplicate_launch_blocked": None}),
                ("null_duplicate_launch_blocked", {"duplicate_launch_blocked": None}),
                ("string_duplicate_launch_blocked", {"duplicate_launch_blocked": "false"}),
            ]
            for case, replacement in cases:
                with self.subTest(case=case):
                    enrollment = dict(valid)
                    field = next(iter(replacement))
                    if case.startswith("missing_"):
                        enrollment.pop(field)
                    else:
                        enrollment.update(replacement)
                    self.assertFalse(_recovery_enrollment_can_be_superseded(enrollment))

            self.assertTrue(_recovery_enrollment_can_be_superseded(valid))

    def test_recovery_supersession_allows_only_filenotfound_manifest_stat(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            absent_manifest = root / "absent-manifest.json"
            enrollment = {
                "lifecycle_state": "failed_before_manifest",
                "process_exit_verified": True,
                "duplicate_launch_blocked": False,
                "manifest_path": str(absent_manifest),
            }
            self.assertTrue(_recovery_enrollment_can_be_superseded(enrollment))

            existing_file = root / "existing-manifest.json"
            existing_file.write_text("{}", encoding="utf-8")
            self.assertFalse(
                _recovery_enrollment_can_be_superseded(
                    {**enrollment, "manifest_path": str(existing_file)}
                )
            )

            existing_directory = root / "manifest-directory"
            existing_directory.mkdir()
            self.assertFalse(
                _recovery_enrollment_can_be_superseded(
                    {**enrollment, "manifest_path": str(existing_directory)}
                )
            )
            self.assertFalse(
                _recovery_enrollment_can_be_superseded({**enrollment, "manifest_path": ""})
            )
            broken_reparse_path = root / "broken-reparse-manifest.json"
            with (
                patch.object(Path, "lstat", return_value=object()),
                patch.object(Path, "stat", side_effect=FileNotFoundError("reparse target missing")),
            ):
                self.assertFalse(
                    _recovery_enrollment_can_be_superseded(
                        {**enrollment, "manifest_path": str(broken_reparse_path)}
                    )
                )
            with patch.object(Path, "lstat", side_effect=PermissionError("manifest lstat denied")):
                self.assertFalse(_recovery_enrollment_can_be_superseded(enrollment))

    def test_continue_retry_is_exactly_once_for_concurrent_same_request(self) -> None:
        class CountingService(DummyWorkflowFacadeService):
            def __init__(self, root: Path) -> None:
                super().__init__(root)
                self.rerun_start_count = 0
                self.count_lock = threading.Lock()

            def start_rerun_csv(self, resolved: object, csv_path: Path, **kwargs: object) -> DummyProc:  # type: ignore[override]
                with self.count_lock:
                    self.rerun_start_count += 1
                return super().start_rerun_csv(resolved, csv_path, **kwargs)  # type: ignore[arg-type]

        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            counting_service = CountingService(root)
            facade, _service, resolved, manifest_key, _manifest_path = _retry_exhausted_continue_case(
                root,
                service=counting_service,
            )
            barrier = threading.Barrier(3)
            results: list[dict[str, object]] = []
            results_lock = threading.Lock()

            def invoke(command_id: str) -> None:
                barrier.wait()
                result = facade.continue_rerun_pending_rows(
                    resolved,  # type: ignore[arg-type]
                    {
                        "_command_id": command_id,
                        "manifest_key": manifest_key,
                        "request_id": "concurrent-recovery-request",
                        "confirm_continue": True,
                    },
                ).to_mapping()
                with results_lock:
                    results.append(result)

            threads = [
                threading.Thread(target=invoke, args=("concurrent-command-a",)),
                threading.Thread(target=invoke, args=("concurrent-command-b",)),
            ]
            for thread in threads:
                thread.start()
            barrier.wait()
            for thread in threads:
                thread.join(timeout=5)

        self.assertEqual(len(results), 2)
        self.assertEqual(counting_service.rerun_start_count, 1)
        self.assertEqual(sum(result["data"]["launches_work"] is True for result in results), 1)  # type: ignore[index]
        self.assertEqual(sum(result["data"].get("idempotent_replay") is True for result in results), 1)  # type: ignore[union-attr]
        self.assertEqual(len({str(result["data"]["batch_id"]) for result in results}), 1)  # type: ignore[index]

    def test_rerun_start_does_not_report_process_spawned_after_enrollment_already_terminalized(self) -> None:
        class ImmediateExitService(DummyWorkflowFacadeService):
            def start_rerun_csv(self, resolved: object, csv_path: Path, **kwargs: object) -> DummyProc:  # type: ignore[override]
                enrollment_path = Path(str(kwargs["enrollment_path"]))
                transition_rerun_enrollment(
                    enrollment_path,
                    "failed_before_manifest",
                    expected_states={"accepted"},
                    reason_code="rerun_process_exit_nonzero",
                    reason="Child exited before manifest creation.",
                )
                self.enrollment_path = enrollment_path
                return DummyProc(24682)

        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            movie = _media_file(root, "Movie")
            csv_path = root / "rerun.csv"
            csv_path.write_text(f"enabled,source_path\ntrue,{movie}\n", encoding="utf-8")
            service = ImmediateExitService(root)
            facade = MediaPipelineApplicationFacade(service, app_version="v5-test")
            resolved = _resolved(root)
            resolved.local_base = root / "LocalBase"
            resolved.state_root = resolved.local_base / "State"

            result = facade.start_rerun_csv_process(
                resolved,
                {"csv_path": str(csv_path), "confirm_replace_final": True},
            ).to_mapping()
            enrollment = json.loads(service.enrollment_path.read_text(encoding="utf-8"))

        self.assertFalse(result["ok"])
        self.assertNotIn("process spawned", result["message"].casefold())
        self.assertEqual(enrollment["status"], "failed_before_manifest")

    def test_rerun_start_stops_child_when_post_spawn_enrollment_cannot_be_read_or_updated(self) -> None:
        class StopProbeService(DummyWorkflowFacadeService):
            def start_rerun_csv(self, resolved: object, csv_path: Path, **kwargs: object) -> DummyProc:  # type: ignore[override]
                self.enrollment_path = Path(str(kwargs["enrollment_path"]))
                self.proc = DummyProc(24682)
                return self.proc

            def kill_process_tree(self, proc: object, label: str) -> str:  # type: ignore[override]
                self.stopped_proc = proc
                self.stop_label = label
                return "stopped"

        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            movie = _media_file(root, "Movie")
            csv_path = root / "rerun.csv"
            csv_path.write_text(f"enabled,source_path\ntrue,{movie}\n", encoding="utf-8")
            service = StopProbeService(root)
            facade = MediaPipelineApplicationFacade(service, app_version="v5-test")
            resolved = _resolved(root)
            resolved.local_base = root / "LocalBase"
            resolved.state_root = resolved.local_base / "State"

            with (
                patch("mediapipeline.core.processes.rerun_facade.transition_rerun_enrollment", return_value=None),
                patch("mediapipeline.core.processes.rerun_facade.read_rerun_enrollment", return_value=None),
            ):
                result = facade.start_rerun_csv_process(
                    resolved,
                    {"csv_path": str(csv_path), "confirm_replace_final": True},
                ).to_mapping()
            enrollment = json.loads(service.enrollment_path.read_text(encoding="utf-8"))

        self.assertFalse(result["ok"])
        self.assertIs(service.stopped_proc, service.proc)
        self.assertEqual(service.stop_label, "CSV rerun enrollment transition failure")
        self.assertEqual(enrollment["status"], "failed_before_manifest")
        self.assertEqual(enrollment["reason_code"], "rerun_process_spawn_transition_unpersisted")
        self.assertIn("safe child stop", enrollment["reason"])

    def test_rerun_start_stops_child_when_spawn_transition_write_leaves_only_accepted_state(self) -> None:
        class StopProbeService(DummyWorkflowFacadeService):
            def kill_process_tree(self, proc: object, label: str) -> str:  # type: ignore[override]
                self.stopped_proc = proc
                self.stop_label = label
                return "stopped"

        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            movie = _media_file(root, "Movie")
            csv_path = root / "rerun.csv"
            csv_path.write_text(f"enabled,source_path\ntrue,{movie}\n", encoding="utf-8")
            service = StopProbeService(root)
            facade = MediaPipelineApplicationFacade(service, app_version="v5-test")
            resolved = _resolved(root)
            resolved.local_base = root / "LocalBase"
            resolved.state_root = resolved.local_base / "State"

            with patch(
                "mediapipeline.core.processes.rerun_facade.transition_rerun_enrollment",
                side_effect=OSError("state write unavailable"),
            ):
                result = facade.start_rerun_csv_process(
                    resolved,
                    {"csv_path": str(csv_path), "confirm_replace_final": True},
                ).to_mapping()
            enrollment = json.loads(Path(result["data"]["enrollment_path"]).read_text(encoding="utf-8"))

        self.assertFalse(result["ok"])
        self.assertEqual(result["data"]["lifecycle_state"], "failed_before_manifest")
        self.assertNotIn("process spawned", result["message"].casefold())
        self.assertIs(service.stopped_proc, service.started_rerun_proc)
        self.assertEqual(service.stop_label, "CSV rerun enrollment transition failure")
        self.assertEqual(enrollment["status"], "failed_before_manifest")
        self.assertEqual(enrollment["reason_code"], "rerun_process_spawn_transition_unpersisted")

    def test_rerun_start_preserves_nonterminal_ambiguity_when_spawn_transition_and_child_exit_are_unverified(self) -> None:
        class AmbiguousProc(DummyProc):
            def poll(self) -> None:
                return None

        class AmbiguousStopService(DummyWorkflowFacadeService):
            def start_rerun_csv(self, resolved: object, csv_path: Path, **kwargs: object) -> DummyProc:  # type: ignore[override]
                self.enrollment_path = Path(str(kwargs["enrollment_path"]))
                self.proc = AmbiguousProc(24682)
                return self.proc

            def kill_process_tree(self, proc: object, label: str) -> str:  # type: ignore[override]
                self.stopped_proc = proc
                return (
                    "Kill requested, but taskkill timed out and exit could not be verified. "
                    "Fallback attempts completed."
                )

        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            movie = _media_file(root, "Movie")
            csv_path = root / "rerun.csv"
            csv_path.write_text(f"enabled,source_path\ntrue,{movie}\n", encoding="utf-8")
            service = AmbiguousStopService(root)
            facade = MediaPipelineApplicationFacade(service, app_version="v5-test")
            resolved = _resolved(root)
            resolved.local_base = root / "LocalBase"
            resolved.state_root = resolved.local_base / "State"

            with (
                patch("mediapipeline.core.processes.rerun_facade.transition_rerun_enrollment", return_value=None),
                patch("mediapipeline.core.processes.rerun_facade.read_rerun_enrollment", return_value=None),
            ):
                result = facade.start_rerun_csv_process(
                    resolved,
                    {"csv_path": str(csv_path), "confirm_replace_final": True},
                ).to_mapping()
            enrollment = json.loads(service.enrollment_path.read_text(encoding="utf-8"))

        self.assertFalse(result["ok"])
        self.assertIs(service.stopped_proc, service.proc)
        self.assertEqual(enrollment["status"], "spawn_transition_ambiguous")
        self.assertFalse(enrollment["process_exit_verified"])
        self.assertTrue(enrollment["operator_action_required"])
        self.assertEqual(enrollment["pid"], 24682)
        self.assertNotIn(enrollment["status"], {"failed", "failed_before_manifest"})

    def test_spawn_stop_exit_verification_rejects_degraded_tree_evidence_after_root_exit(self) -> None:
        proc = SimpleNamespace(poll=lambda: -9)
        degraded_results = (
            "Kill requested for process tree, but taskkill timed out and descendant exit could not be verified.",
            "taskkill returned a nonzero exit status after the root stopped.",
            "App-owned CSV rerun process already exited.",
            "kill_degraded: root stopped but descendant state is unknown.",
        )

        for stop_result in degraded_results:
            with self.subTest(stop_result=stop_result):
                self.assertFalse(_spawn_stop_exit_verified(proc, stop_result))
        self.assertTrue(_spawn_stop_exit_verified(proc, "Stopped process tree; descendant exit verified."))

    def test_rerun_start_outer_exception_preserves_live_child_as_spawn_transition_ambiguity(self) -> None:
        class LiveProc(DummyProc):
            def poll(self) -> None:
                return None

        class LiveChildService(DummyWorkflowFacadeService):
            def start_rerun_csv(self, resolved: object, csv_path: Path, **kwargs: object) -> DummyProc:  # type: ignore[override]
                self.proc = LiveProc(24683)
                return self.proc

        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            movie = _media_file(root, "Live Outer Exception")
            csv_path = root / "rerun.csv"
            csv_path.write_text(f"enabled,source_path\ntrue,{movie}\n", encoding="utf-8")
            service = LiveChildService(root)
            facade = MediaPipelineApplicationFacade(service, app_version="v5-test")
            resolved = _resolved(root)
            resolved.local_base = root / "LocalBase"
            resolved.state_root = resolved.local_base / "State"

            with patch.object(
                facade,
                "_transfer_process_launch_lease",
                side_effect=RuntimeError("post-spawn lease transfer failed"),
            ):
                result = facade.start_rerun_csv_process(
                    resolved,
                    {"csv_path": str(csv_path), "confirm_replace_final": True},
                ).to_mapping()
            enrollment = json.loads(Path(result["data"]["enrollment_path"]).read_text(encoding="utf-8"))

        self.assertFalse(result["ok"])
        self.assertEqual(enrollment["status"], "spawn_transition_ambiguous")
        self.assertFalse(enrollment["process_exit_verified"])
        self.assertTrue(enrollment["duplicate_launch_blocked"])
        self.assertEqual(enrollment["pid"], service.proc.pid)

    def test_rerun_start_outer_exception_uses_nonconsuming_spawn_cleanup_marker(self) -> None:
        class MarkerAmbiguousService(DummyWorkflowFacadeService):
            def __init__(self, root: Path) -> None:
                super().__init__(root)
                self._pending_lifecycle_lease_lock = threading.Lock()
                self._pending_lifecycle_lease = None

            def start_rerun_csv(self, resolved: object, csv_path: Path, **kwargs: object) -> DummyProc:  # type: ignore[override]
                lease = self._consume_pending_lifecycle_lease()
                if lease is None:
                    raise AssertionError("expected facade lifecycle lease")
                _mark_launch_cleanup_reconciliation_required(lease)
                raise RuntimeError("spawn cleanup could not verify descendant exit")

        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            movie = _media_file(root, "Marked Outer Exception")
            csv_path = root / "rerun.csv"
            csv_path.write_text(f"enabled,source_path\ntrue,{movie}\n", encoding="utf-8")
            service = MarkerAmbiguousService(root)
            facade = MediaPipelineApplicationFacade(service, app_version="v5-test")
            resolved = _resolved(root)
            resolved.local_base = root / "LocalBase"
            resolved.state_root = resolved.local_base / "State"

            result = facade.start_rerun_csv_process(
                resolved,
                {"csv_path": str(csv_path), "confirm_replace_final": True},
            ).to_mapping()
            enrollment = json.loads(Path(result["data"]["enrollment_path"]).read_text(encoding="utf-8"))

        self.assertFalse(result["ok"])
        self.assertEqual(enrollment["status"], "spawn_transition_ambiguous")
        self.assertFalse(enrollment["process_exit_verified"])
        self.assertTrue(enrollment["duplicate_launch_blocked"])

    def test_rerun_start_outer_exception_marker_vetoes_exited_root_process_proof(self) -> None:
        class ExitedProc(DummyProc):
            def poll(self) -> int:
                return -9

        class MarkedExitedRootService(DummyWorkflowFacadeService):
            def __init__(self, root: Path) -> None:
                super().__init__(root)
                self._pending_lifecycle_lease_lock = threading.Lock()
                self._pending_lifecycle_lease = None

            def start_rerun_csv(self, resolved: object, csv_path: Path, **kwargs: object) -> DummyProc:  # type: ignore[override]
                lease = self._consume_pending_lifecycle_lease()
                if lease is None:
                    raise AssertionError("expected facade lifecycle lease")
                _mark_launch_cleanup_reconciliation_required(lease)
                self.proc = ExitedProc(24684)
                return self.proc

        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            movie = _media_file(root, "Marked Exited Root")
            csv_path = root / "rerun.csv"
            csv_path.write_text(f"enabled,source_path\ntrue,{movie}\n", encoding="utf-8")
            service = MarkedExitedRootService(root)
            facade = MediaPipelineApplicationFacade(service, app_version="v5-test")
            resolved = _resolved(root)
            resolved.local_base = root / "LocalBase"
            resolved.state_root = resolved.local_base / "State"

            with patch.object(
                facade,
                "_transfer_process_launch_lease",
                side_effect=RuntimeError("post-spawn lease transfer failed"),
            ):
                result = facade.start_rerun_csv_process(
                    resolved,
                    {"csv_path": str(csv_path), "confirm_replace_final": True},
                ).to_mapping()
            enrollment = json.loads(Path(result["data"]["enrollment_path"]).read_text(encoding="utf-8"))

        self.assertFalse(result["ok"])
        self.assertEqual(enrollment["status"], "spawn_transition_ambiguous")
        self.assertFalse(enrollment["process_exit_verified"])
        self.assertTrue(enrollment["duplicate_launch_blocked"])
        self.assertEqual(enrollment["pid"], service.proc.pid)

    def test_rerun_start_outer_exception_process_tree_marker_vetoes_exited_root_process_proof(self) -> None:
        class ExitedProc(DummyProc):
            def poll(self) -> int:
                return -9

        class MarkedExitedRootService(DummyWorkflowFacadeService):
            def start_rerun_csv(self, resolved: object, csv_path: Path, **kwargs: object) -> DummyProc:  # type: ignore[override]
                self.proc = ExitedProc(24685)
                return self.proc

        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            movie = _media_file(root, "Process Tree Marked Exited Root")
            csv_path = root / "rerun.csv"
            csv_path.write_text(f"enabled,source_path\ntrue,{movie}\n", encoding="utf-8")
            service = MarkedExitedRootService(root)
            facade = MediaPipelineApplicationFacade(service, app_version="v5-test")
            resolved = _resolved(root)
            resolved.local_base = root / "LocalBase"
            resolved.state_root = resolved.local_base / "State"

            with (
                patch.object(
                    facade,
                    "_transfer_process_launch_lease",
                    side_effect=RuntimeError("post-spawn lease transfer failed"),
                ),
                patch(
                    "mediapipeline.core.processes.rerun_facade._process_tree_cleanup_reconciliation_required",
                    return_value=True,
                    create=True,
                ),
            ):
                result = facade.start_rerun_csv_process(
                    resolved,
                    {"csv_path": str(csv_path), "confirm_replace_final": True},
                ).to_mapping()
            enrollment = json.loads(Path(result["data"]["enrollment_path"]).read_text(encoding="utf-8"))

        self.assertFalse(result["ok"])
        self.assertEqual(enrollment["status"], "spawn_transition_ambiguous")
        self.assertFalse(enrollment["process_exit_verified"])
        self.assertTrue(enrollment["duplicate_launch_blocked"])
        self.assertEqual(enrollment["pid"], service.proc.pid)

    def test_rerun_start_degraded_stop_veto_survives_ambiguity_persistence_failure(self) -> None:
        class ExitedProc(DummyProc):
            def poll(self) -> int:
                return -9

        class DegradedStopService(DummyWorkflowFacadeService):
            def start_rerun_csv(self, resolved: object, csv_path: Path, **kwargs: object) -> DummyProc:  # type: ignore[override]
                self.enrollment_path = Path(str(kwargs["enrollment_path"]))
                self.proc = ExitedProc(24686)
                return self.proc

            def kill_process_tree(self, proc: object, label: str) -> str:  # type: ignore[override]
                self.stopped_proc = proc
                return (
                    "Kill requested for CSV rerun process tree; taskkill reported a nonzero exit status. "
                    "The root process exited, but descendant state is unknown."
                )

        real_transition = transition_rerun_enrollment

        def transition_with_unpersisted_spawn(
            path: Path | None,
            state: str,
            **kwargs: object,
        ) -> dict[str, object] | None:
            if state == "process_spawned":
                return None
            return real_transition(path, state, **kwargs)

        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            movie = _media_file(root, "Degraded Stop Persistence Failure")
            csv_path = root / "rerun.csv"
            csv_path.write_text(f"enabled,source_path\ntrue,{movie}\n", encoding="utf-8")
            service = DegradedStopService(root)
            facade = MediaPipelineApplicationFacade(service, app_version="v5-test")
            resolved = _resolved(root)
            resolved.local_base = root / "LocalBase"
            resolved.state_root = resolved.local_base / "State"

            with (
                patch(
                    "mediapipeline.core.processes.rerun_facade.transition_rerun_enrollment",
                    side_effect=transition_with_unpersisted_spawn,
                ),
                patch(
                    "mediapipeline.core.processes.rerun_facade.record_rerun_spawn_transition_ambiguity",
                    side_effect=OSError("ambiguity state unavailable"),
                ),
                patch(
                    "mediapipeline.core.processes.rerun_facade.read_rerun_enrollment",
                    return_value=None,
                ),
            ):
                result = facade.start_rerun_csv_process(
                    resolved,
                    {"csv_path": str(csv_path), "confirm_replace_final": True},
                ).to_mapping()
            enrollment = json.loads(service.enrollment_path.read_text(encoding="utf-8"))

        self.assertFalse(result["ok"])
        self.assertIs(service.stopped_proc, service.proc)
        self.assertNotIn(enrollment["status"], {"failed", "failed_before_manifest"})
        self.assertIn(enrollment["status"], {"accepted", "spawn_transition_ambiguous"})
        self.assertIn("reconcil", f"{result['message']} {' '.join(result['errors'])}".casefold())

    def test_rerun_start_outer_exception_before_lease_activation_records_verified_failure(self) -> None:
        class BeforeChildFailureService(DummyWorkflowFacadeService):
            def start_rerun_csv(self, resolved: object, csv_path: Path, **kwargs: object) -> DummyProc:  # type: ignore[override]
                raise RuntimeError("spawn failed before a child was created")

        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            movie = _media_file(root, "No Child Outer Exception")
            csv_path = root / "rerun.csv"
            csv_path.write_text(f"enabled,source_path\ntrue,{movie}\n", encoding="utf-8")
            service = BeforeChildFailureService(root)
            facade = MediaPipelineApplicationFacade(service, app_version="v5-test")
            resolved = _resolved(root)
            resolved.local_base = root / "LocalBase"
            resolved.state_root = resolved.local_base / "State"

            result = facade.start_rerun_csv_process(
                resolved,
                {"csv_path": str(csv_path), "confirm_replace_final": True},
            ).to_mapping()
            enrollment = json.loads(Path(result["data"]["enrollment_path"]).read_text(encoding="utf-8"))

        self.assertFalse(result["ok"])
        self.assertEqual(enrollment["status"], "failed_before_manifest")
        self.assertTrue(enrollment["process_exit_verified"])
        self.assertFalse(enrollment["duplicate_launch_blocked"])

    def test_rerun_start_blocks_relative_source_rows_before_spawn(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            csv_path = root / "rerun-relative.csv"
            csv_path.write_text("enabled,source_path\ntrue,relative-source.mkv\n", encoding="utf-8")
            service = DummyWorkflowFacadeService(root)
            facade = MediaPipelineApplicationFacade(service, app_version="v5-test")
            resolved = _resolved(root)

            result = facade.start_rerun_csv_process(
                resolved,
                {"csv_path": str(csv_path), "confirm_replace_final": True},
            ).to_mapping()

        self.assertFalse(result["ok"])
        self.assertEqual(result["command"], "rerun.start")
        self.assertEqual(result["data"]["counts"]["relative_source_rows"], 1)
        self.assertIn("relative source_path", "\n".join(result["errors"]))
        self.assertFalse(hasattr(service, "started_rerun"))

    def test_rerun_start_blocks_duplicate_source_rows_before_spawn(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            source = _media_file(root, "Duplicate")
            csv_path = root / "rerun-duplicates.csv"
            csv_path.write_text(
                f"enabled,source_path\ntrue,{source}\ntrue,{source}\n",
                encoding="utf-8",
            )
            service = DummyWorkflowFacadeService(root)
            facade = MediaPipelineApplicationFacade(service, app_version="v5-test")
            resolved = _resolved(root)

            result = facade.start_rerun_csv_process(
                resolved,
                {"csv_path": str(csv_path), "confirm_replace_final": True},
            ).to_mapping()

        self.assertFalse(result["ok"])
        self.assertEqual(result["command"], "rerun.start")
        self.assertEqual(result["data"]["status"], "blocked")
        self.assertEqual(result["data"]["counts"]["duplicate_source_rows"], 2)
        self.assertIn("duplicate source_path", "\n".join(result["errors"]))
        self.assertFalse(hasattr(service, "started_rerun"))

    def test_rerun_start_blocks_duplicate_planned_output_rows_before_spawn(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            correct = root / "Media" / "Hellboy II The Golden Army (2008)" / "Hellboy II The Golden Army (2008).mkv"
            duplicate = root / "Outsource" / "Hellboy II The Golden Army (2008)" / "Hellboy II The Golden Army (2008).mkv"
            for path in (correct, duplicate):
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(b"media")
            csv_path = root / "rerun-duplicate-output.csv"
            csv_path.write_text(
                "enabled,source_path,media_kind\n"
                f"true,{correct},Movie\n"
                f"true,{duplicate},Movie\n",
                encoding="utf-8",
            )
            service = DummyWorkflowFacadeService(root)
            facade = MediaPipelineApplicationFacade(service, app_version="v5-test")
            resolved = _resolved(root)

            result = facade.start_rerun_csv_process(
                resolved,
                {"csv_path": str(csv_path), "confirm_replace_final": True},
            ).to_mapping()

        self.assertFalse(result["ok"])
        self.assertEqual(result["command"], "rerun.start")
        self.assertEqual(result["data"]["status"], "blocked")
        self.assertEqual(result["data"]["counts"]["duplicate_planned_output_rows"], 2)
        self.assertIn("duplicate planned output path", "\n".join(result["errors"]))
        self.assertFalse(hasattr(service, "started_rerun"))

    def test_rerun_plan_launches_backend_plan_and_start_materializes_scoped_csv(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            csv_path = root / "rerun.csv"
            movie = _media_file(root, "Movie")
            skip = _media_file(root, "Skip")
            csv_path.write_text(
                "enabled,source_path,primary_issue_code,effective_bucket\n"
                f"true,{movie},audio-default-policy-mismatch,movie\n"
                f"false,{skip},subtitle-missing-text,movie\n",
                encoding="utf-8",
            )
            service = DummyWorkflowFacadeService(root)
            facade = MediaPipelineApplicationFacade(service, app_version="v5-test")
            resolved = _resolved(root)
            resolved.state_root = root / "State"

            plan = facade.start_rerun_csv_process(
                resolved,
                {"csv_path": str(csv_path), "plan_only": True, "confirm_replace_final": True},
            ).to_mapping()
            scoped_dir = root / "State" / "Rerun" / "ScopedCsv"
            self.assertTrue(plan["ok"])
            self.assertEqual(plan["data"]["pid"], 24682)
            self.assertTrue(plan["data"]["plan_only"])
            self.assertEqual(service.started_rerun["plan_only"], True)
            self.assertEqual(service.started_rerun["return_mode"], "replace_original")
            service.started_rerun_proc.complete()

            result = facade.start_rerun_csv_process(
                resolved,
                {"csv_path": str(csv_path), "dry_run": True, "confirm_replace_final": True},
            ).to_mapping()

            self.assertTrue(result["ok"])
            scoped_csv = Path(str(result["data"]["scoped_csv_path"]))
            self.assertNotEqual(scoped_csv, csv_path)
            self.assertEqual(scoped_csv.parent, scoped_dir)
            self.assertEqual(Path(service.started_rerun["csv_path"]), scoped_csv)
            self.assertEqual(result["data"]["source_csv_path"], str(csv_path))
            scoped_text = scoped_csv.read_text(encoding="utf-8")
            self.assertIn("Movie.mkv", scoped_text)
            self.assertNotIn("Skip.mkv", scoped_text)

    def test_process_launch_commands_share_backend_launch_lock(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            csv_path = root / "rerun.csv"
            movie = _media_file(root, "Movie")
            csv_path.write_text(f"enabled,source_path\ntrue,{movie}\n", encoding="utf-8")
            service = DummyWorkflowFacadeService(root)
            facade = MediaPipelineApplicationFacade(service, app_version="v5-test")
            resolved = _resolved(root)
            resolved.config_data = {"NetworkRole": "standalone", "Outsource": str(root / "Outsource")}

            self.assertTrue(facade._process_launch_lock.acquire(blocking=False))  # type: ignore[attr-defined]
            try:
                pipeline = facade.start_pipeline_process(resolved, {"mode": "validate"}).to_mapping()
                audit = facade.start_audit_process(resolved, {}).to_mapping()
                rerun = facade.start_rerun_csv_process(
                    resolved,
                    {"csv_path": str(csv_path), "confirm_replace_final": True},
                ).to_mapping()
            finally:
                facade._process_launch_lock.release()  # type: ignore[attr-defined]

        self.assertFalse(pipeline["ok"])
        self.assertFalse(audit["ok"])
        self.assertFalse(rerun["ok"])
        self.assertIn("another process launch command is already in progress", pipeline["message"])
        self.assertIn("another process launch command is already in progress", audit["message"])
        self.assertIn("another process launch command is already in progress", rerun["message"])
        self.assertFalse(hasattr(service, "started_pipeline"))
        self.assertFalse(hasattr(service, "started_audit"))
        self.assertFalse(hasattr(service, "started_rerun"))

    def test_pipeline_start_rejects_duplicate_launch_when_first_process_is_still_running(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            service = DummyWorkflowFacadeService(root)
            start_calls: list[dict[str, object]] = []

            def fake_start_pipeline(**kwargs: object) -> DummyProc:
                start_calls.append(dict(kwargs))
                return DummyProc(25000 + len(start_calls))

            service.start_pipeline = fake_start_pipeline  # type: ignore[method-assign]
            facade = MediaPipelineApplicationFacade(service, app_version="v5-test")
            resolved = _resolved(root)

            first = facade.start_pipeline_process(resolved, {"mode": "validate"}).to_mapping()
            service.find_related_pipeline_processes = lambda _resolved: [DummyProc(first["data"]["pid"])]  # type: ignore[method-assign]
            second = facade.start_pipeline_process(resolved, {"mode": "validate"}).to_mapping()

        self.assertTrue(first["ok"])
        self.assertEqual(first["data"]["pid"], 25001)
        self.assertFalse(second["ok"])
        self.assertEqual(second["command"], "pipeline.start")
        self.assertEqual(second["severity"], "warning")
        self.assertIn("still running from this bundle", second["message"])
        self.assertEqual(len(start_calls), 1)

    def test_pipeline_start_stale_guard_cleanup_does_not_ignore_live_related_process(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            service = DummyWorkflowFacadeService(root)
            cleanup_calls: list[object] = []
            service.cleanup_stale_launch_guards = lambda resolved_arg: cleanup_calls.append(resolved_arg)  # type: ignore[method-assign]
            service.find_related_pipeline_processes = lambda _resolved_arg, *, job_kinds=None: [DummyProc(24681)]  # type: ignore[method-assign]
            facade = MediaPipelineApplicationFacade(service, app_version="v5-test")
            resolved = _resolved(root)

            blocked = facade.start_pipeline_process(resolved, {"mode": "validate"}).to_mapping()

        self.assertEqual(cleanup_calls, [resolved])
        self.assertFalse(blocked["ok"])
        self.assertEqual(blocked["severity"], "warning")
        self.assertIn("PID(s) 24681", blocked["message"])
        self.assertFalse(hasattr(service, "started_pipeline"))

    def test_pipeline_start_stop_requested_progress_blocks_from_fresh_progress(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            service = DummyWorkflowFacadeService(root)
            service.find_related_pipeline_processes = lambda _resolved_arg, *, job_kinds=None: []  # type: ignore[method-assign]
            service.read_progress = lambda _resolved_arg: {"CurrentStage": "encode", "StopRequested": True}  # type: ignore[method-assign]
            service.is_progress_stale = lambda _progress: False  # type: ignore[method-assign]
            facade = MediaPipelineApplicationFacade(service, app_version="v5-test")
            resolved = _resolved(root)

            blocked = facade.start_pipeline_process(resolved, {"mode": "validate"}).to_mapping()

        self.assertFalse(blocked["ok"])
        self.assertEqual(blocked["severity"], "warning")
        self.assertIn("fresh pipeline progress indicates active work", blocked["message"])
        self.assertFalse(hasattr(service, "started_pipeline"))

    def test_pipeline_start_blocks_autonomy_health_before_spawn(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            service = DummyWorkflowFacadeService(root)
            facade = MediaPipelineApplicationFacade(service, app_version="v5-test")
            resolved = _resolved(root)
            resolved.pending_push_path = root / "State" / "PendingServerPush"
            resolved.pending_push_path.mkdir(parents=True)
            manifest = resolved.pending_push_path / "movie.manifest.json"
            parked_at = (datetime.now() - timedelta(days=4)).astimezone().isoformat()
            manifest.write_text(
                json.dumps(
                    {
                        "parked_at": parked_at,
                        "retry_count": 3,
                        "local_file": str(resolved.pending_push_path / "movie.mkv"),
                        "server_out": str(root / "Out" / "movie.mkv"),
                        "manifest_state": "parked",
                    }
                ),
                encoding="utf-8",
            )

            blocked = facade.start_pipeline_process(resolved, {"mode": "validate"}).to_mapping()
            preflight = facade.get_launch_preflight(resolved, {"target": "pipeline", "mode": "validate"})

        self.assertFalse(blocked["ok"])
        self.assertEqual(blocked["command"], "pipeline.start")
        self.assertEqual(blocked["severity"], "error")
        self.assertEqual(blocked["refresh_hint"], "diagnostics")
        self.assertEqual(blocked["data"]["schema_version"], "desktop_pipeline_autonomy_launch_block.v1")
        self.assertFalse(blocked["data"]["start_route_allowed"])
        self.assertEqual(blocked["data"]["autonomy_health"]["overall_status"], "blocked")
        self.assertFalse(hasattr(service, "started_pipeline"))
        self.assertEqual(preflight["status"], "blocked")
        rows = {row["key"]: row for row in preflight["checks"]}
        self.assertEqual(rows["autonomy_health"]["status"], "blocked")
        self.assertIn("can_start_new_work=no", rows["autonomy_health"]["evidence"])
        self.assertIn("blocker=", rows["autonomy_health"]["evidence"])
        self.assertIn("reason=", rows["autonomy_health"]["evidence"])
        self.assertTrue(rows["autonomy_health"]["recovery_actions"])
        self.assertEqual(rows["autonomy_health"]["recovery_actions"][0]["route"], "/api/pending-publish/recovery-plan")
        readiness_rows = {row["key"]: row for row in preflight["operator_readiness"]["non_ready_checks"]}
        self.assertEqual(readiness_rows["autonomy_health"]["recovery_actions"][0]["kind"], "pending_publish_recovery_plan")

    def test_pending_drain_mode_bypasses_autonomy_new_work_block(self) -> None:
        blocked_autonomy = {
            "overall_status": "blocked",
            "launch_gate": {
                "can_start_new_work": False,
                "safe_next_action": "Publish parked outputs before starting more queue work.",
            },
            "blockers": [
                {
                    "code": "autonomy_pending_bytes_over_budget",
                    "message": "Pending publish parked bytes exceed the blocked budget.",
                    "next_action": "Publish the parked outputs before starting more queue work.",
                    "recovery_action": {
                        "kind": "drain_pending_pushes",
                        "label": "Drain parked outputs",
                        "route": "/api/pipeline/start",
                        "request": {"mode": "drain_pending_pushes"},
                    },
                }
            ],
            "review_items": [],
        }
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            service = DummyWorkflowFacadeService(root)
            facade = MediaPipelineApplicationFacade(service, app_version="v5-test")
            facade._autonomy_health_for_resolved = lambda _resolved_arg, **_kwargs: blocked_autonomy  # type: ignore[method-assign]
            resolved = _resolved(root)

            normal = facade.start_pipeline_process(resolved, {"mode": "validate"}).to_mapping()
            drain_preflight = facade.get_launch_preflight(resolved, {"target": "pipeline", "mode": "drain_pending_pushes"})
            drain = facade.start_pipeline_process(resolved, {"mode": "drain_pending_pushes"}).to_mapping()

        self.assertFalse(normal["ok"])
        self.assertEqual(normal["data"]["schema_version"], "desktop_pipeline_autonomy_launch_block.v1")
        self.assertTrue(drain["ok"])
        self.assertEqual(drain["data"]["mode"], "drain_pending_pushes")
        self.assertEqual(service.started_pipeline["mode"], "drain_pending_pushes")
        self.assertNotEqual(drain_preflight["status"], "blocked")
        self.assertTrue(drain_preflight["can_request_start"])
        rows = {row["key"]: row for row in drain_preflight["checks"]}
        self.assertEqual(rows["autonomy_health"]["status"], "review")
        self.assertIn("can_start_new_work=no", rows["autonomy_health"]["evidence"])
        self.assertIn("can_attempt_pending_drain=yes", rows["autonomy_health"]["evidence"])
        self.assertIn("recovery work", rows["autonomy_health"]["action"])

    def test_pipeline_start_blocked_by_active_work_does_not_cancel_existing_schedule_watcher(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            service = DummyWorkflowFacadeService(root)
            facade = MediaPipelineApplicationFacade(service, app_version="v5-test")
            resolved = _resolved(root)
            watcher = facade._schedule_stop_watcher  # type: ignore[attr-defined]
            watcher.arm(
                service=service,
                resolved=resolved,
                proc=DummyProc(24681),
                deadline=datetime.now() + timedelta(seconds=30),
            )
            service.find_related_pipeline_processes = lambda _resolved_arg: [DummyProc(24681)]  # type: ignore[method-assign]

            blocked = facade.start_pipeline_process(resolved, {"mode": "validate"}).to_mapping()
            state = watcher.state()
            watcher.cancel("test cleanup")

        self.assertFalse(blocked["ok"])
        self.assertEqual(state.status, "armed")
        self.assertEqual(state.pid, 24681)
