from __future__ import annotations

from datetime import datetime, timedelta, timezone, UTC
import hashlib
import json
import os
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
from mediapipeline.desktop.application.network_lifecycle_provider import _NetworkRuntimeApp
from mediapipeline.desktop.network.registry import InFlightRegistry
from mediapipeline.desktop.network.rerun_claims import (
    claim_next_network_rerun_row,
    update_network_rerun_row_done,
    update_network_rerun_row_released,
)
from mediapipeline.core.kernel.runtime.subprocess_runner import CapturedCommandResult
from mediapipeline.core.processes.path_evidence import LAUNCH_PATH_HEALTH_TIMEOUT_SECONDS
from mediapipeline.core.processes.preflight_facade import LAUNCH_PREFLIGHT_PATH_HEALTH_TIMEOUT_SECONDS
from mediapipeline.core.processes.rerun_control import (
    _recovery_enrollment_can_be_superseded,
    _recovery_row_selectors,
    _rerun_recovery_key,
)
from mediapipeline.core.processes.rerun_facade import _spawn_stop_exit_verified
from mediapipeline.core.processes.rerun_results import rerun_results_payload
from mediapipeline.core.processes.rerun_lifecycle import transition_rerun_enrollment
from mediapipeline.core.processes.spawn_runner import _mark_launch_cleanup_reconciliation_required
from tests.python.desktop.application_facade_test_support import DummyProc, DummyWorkflowFacadeService, _resolved


def _fresh_generated_at() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def _media_file(root: Path, name: str, *, suffix: str = ".mkv") -> Path:
    path = root / "Media" / f"{name}{suffix}"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"media")
    return path


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


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_network_worker_result_artifact(
    root: Path,
    *,
    job_id: str,
    output_path: Path,
    batch_id: str,
    row_key: str,
) -> Path:
    path = root / "LocalBase" / "State" / "NetworkWorkerResults" / job_id / "worker_result.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "SchemaVersion": "local_worker_result.v1",
                "JobKind": "csv_rerun_row",
                "RerunBatchId": batch_id,
                "RerunRowKey": row_key,
                "WorkerClaimId": job_id,
                "WorkerRunId": "phase8-run",
                "Success": True,
                "Status": "processed",
                "OutputPath": str(output_path),
                "OutputSizeBytes": output_path.stat().st_size,
                "PublishState": "published",
                "PublishMode": "handoff",
                "Route": "network_lifecycle_single_file",
            }
        ),
        encoding="utf-8",
    )
    return path


class ApplicationFacadeProcessLaunchTests(unittest.TestCase):
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

    def test_pipeline_start_refuses_network_modes(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            service = DummyWorkflowFacadeService(root)
            facade = MediaPipelineApplicationFacade(service, app_version="v5-test")

            coordinator = _resolved(root)
            coordinator.config_data = {
                "NetworkRole": "coordinator",
                "CoordinatorAlsoEncodeLocally": False,
            }
            coordinator_result = facade.start_pipeline_process(coordinator, {"mode": "once"}).to_mapping()
            coordinator_preflight = facade.get_launch_preflight(coordinator, {"target": "pipeline", "mode": "once"})

            local_worker = _resolved(root)
            local_worker.config_data = {
                "NetworkRole": "coordinator",
                "CoordinatorAlsoEncodeLocally": True,
            }
            local_worker_result = facade.start_pipeline_process(local_worker, {"mode": "once"}).to_mapping()

            worker = _resolved(root)
            worker.config_data = {"NetworkRole": "worker"}
            worker_result = facade.start_pipeline_process(worker, {"mode": "once"}).to_mapping()
            worker_preflight = facade.get_launch_preflight(worker, {"target": "pipeline", "mode": "once"})

            invalid = _resolved(root)
            invalid.config_data = {"NetworkRole": "coordinator-only"}
            invalid_result = facade.start_pipeline_process(invalid, {"mode": "once"}).to_mapping()
            invalid_preflight = facade.get_launch_preflight(invalid, {"target": "pipeline", "mode": "once"})

            string_local_flag = _resolved(root)
            string_local_flag.config_data = {
                "NetworkRole": "coordinator",
                "CoordinatorAlsoEncodeLocally": "False",
            }
            string_local_result = facade.start_pipeline_process(string_local_flag, {"mode": "once"}).to_mapping()
            string_local_preflight = facade.get_launch_preflight(string_local_flag, {"target": "pipeline", "mode": "once"})

            missing_role = _resolved(root)
            missing_role.config_data = {}
            missing_role_result = facade.start_pipeline_process(missing_role, {"mode": "once"}).to_mapping()
            missing_role_preflight = facade.get_launch_preflight(missing_role, {"target": "pipeline", "mode": "once"})

            null_role = _resolved(root)
            null_role.config_data = {"NetworkRole": None}
            null_role_result = facade.start_pipeline_process(null_role, {"mode": "once"}).to_mapping()

            empty_role = _resolved(root)
            empty_role.config_data = {"NetworkRole": ""}
            empty_role_result = facade.start_pipeline_process(empty_role, {"mode": "once"}).to_mapping()

        self.assertFalse(coordinator_result["ok"])
        self.assertEqual(coordinator_result["refresh_hint"], "network")
        self.assertEqual(coordinator_result["data"]["network_mode_label"], "Coordinator only")
        self.assertIn("Normal Launch is disabled", coordinator_result["message"])
        self.assertEqual(coordinator_preflight["status"], "blocked")
        self.assertFalse(coordinator_preflight["can_request_start"])
        self.assertTrue(
            any(
                row["key"] == "network_role"
                and row["status"] == "blocked"
                and "Coordinator only" in row["evidence"]
                for row in coordinator_preflight["checks"]
            )
        )
        self.assertFalse(local_worker_result["ok"])
        self.assertEqual(local_worker_result["data"]["network_mode_label"], "Coordinator + local worker")
        self.assertFalse(worker_result["ok"])
        self.assertEqual(worker_result["data"]["network_mode_label"], "Worker only")
        self.assertEqual(worker_preflight["status"], "blocked")
        self.assertTrue(any(row["key"] == "network_role" and row["status"] == "blocked" for row in worker_preflight["checks"]))
        self.assertFalse(invalid_result["ok"])
        self.assertFalse(invalid_result["data"]["network_role_valid"])
        self.assertEqual(invalid_result["data"]["network_mode_label"], "Invalid NetworkRole (coordinator-only)")
        self.assertEqual(invalid_preflight["status"], "blocked")
        self.assertTrue(
            any(
                row["key"] == "network_role"
                and row["status"] == "blocked"
                and "valid=no" in row["evidence"]
                for row in invalid_preflight["checks"]
            )
        )
        self.assertFalse(string_local_result["ok"])
        self.assertEqual(string_local_result["data"]["network_mode_label"], "Coordinator only")
        self.assertTrue(
            any(
                row["key"] == "network_role"
                and row["status"] == "blocked"
                and "Coordinator only" in row["evidence"]
                for row in string_local_preflight["checks"]
            )
        )
        self.assertFalse(missing_role_result["ok"])
        self.assertEqual(missing_role_result["data"]["network_mode_label"], "Invalid NetworkRole (empty)")
        self.assertFalse(missing_role_result["data"]["network_role_valid"])
        self.assertEqual(missing_role_preflight["status"], "blocked")
        self.assertFalse(null_role_result["ok"])
        self.assertFalse(empty_role_result["ok"])
        self.assertFalse(hasattr(service, "started_pipeline"))

    def test_network_lifecycle_dry_run_reports_no_touch_and_requires_journal_before_provider(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            service = DummyWorkflowFacadeService(root)
            facade = MediaPipelineApplicationFacade(service, app_version="v5-test")
            resolved = _resolved(root)
            resolved.config_data = {
                "NetworkRole": "coordinator",
                "CoordinatorPort": 7830,
                "CoordinatorBindAddress": "127.0.0.1",
                "CoordinatorHeartbeatTimeoutMins": 5,
            }

            dry_run = facade.request_network_lifecycle(
                resolved,
                role="coordinator",
                action="start",
                dry_run=True,
                request={},
            ).to_mapping()
            confirmed = facade.request_network_lifecycle(
                resolved,
                role="coordinator",
                action="start",
                dry_run=False,
                request={"confirm_start": True},
            ).to_mapping()

        self.assertTrue(dry_run["ok"])
        self.assertEqual(dry_run["command"], "network.coordinator.start")
        self.assertEqual(dry_run["data"]["schema_version"], "desktop_network_lifecycle_dry_run.v1")
        self.assertTrue(dry_run["data"]["dry_run_only"])
        self.assertEqual(dry_run["data"]["effect"], "none")
        self.assertTrue(dry_run["data"]["safe_to_apply"])
        self.assertIn("source_media", dry_run["data"]["would_not_touch"])
        self.assertNotIn("would_write_state", dry_run["data"])
        self.assertEqual(dry_run["data"]["dry_run_writes"], [])
        self.assertTrue(dry_run["data"]["suppress_command_journal"])
        self.assertEqual(dry_run["data"]["lifecycle_state_source"], "session_memory_only")
        self.assertIn("command_journal_entry", dry_run["data"]["confirmed_route_would_write"])
        self.assertTrue(dry_run["data"]["provider_available"])
        preconditions = {row["key"]: row for row in dry_run["data"]["precondition_results"]}
        self.assertEqual(preconditions["NetworkRole_is_coordinator"]["status"], "pass")
        self.assertEqual(preconditions["lifecycle_provider_available"]["status"], "pass")
        self.assertFalse(confirmed["ok"])
        self.assertEqual(confirmed["data"]["cleanup_result"], "not_started_command_journal_unavailable")
        self.assertFalse(hasattr(service, "started_pipeline"))

    def test_worker_lifecycle_invalid_coordinator_url_blocks_before_provider(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            service = DummyWorkflowFacadeService(root)
            facade = MediaPipelineApplicationFacade(service, app_version="v5-test")
            resolved = _resolved(root)
            resolved.config_data = {
                "NetworkRole": "worker",
                "WorkerCoordinatorUrl": "http://0.0.0.0:7830",
                "WorkerAuthToken": "worker-token",
            }

            dry_run = facade.request_network_lifecycle(
                resolved,
                role="worker",
                action="start",
                dry_run=True,
                request={},
            ).to_mapping()
            confirmed = facade.request_network_lifecycle(
                resolved,
                role="worker",
                action="start",
                dry_run=False,
                request={"confirm_start": True},
                journal_recorder=lambda _payload, _request: None,
            ).to_mapping()
            bad_port = _resolved(root)
            bad_port.config_data = {
                "NetworkRole": "worker",
                "WorkerCoordinatorUrl": "http://coordinator.test:99999",
                "WorkerAuthToken": "worker-token",
            }
            bad_port_dry_run = facade.request_network_lifecycle(
                bad_port,
                role="worker",
                action="start",
                dry_run=True,
                request={},
            ).to_mapping()

        self.assertFalse(dry_run["data"]["safe_to_apply"])
        preconditions = {row["key"]: row for row in dry_run["data"]["precondition_results"]}
        self.assertEqual(preconditions["lifecycle_provider_available"]["status"], "pass")
        self.assertEqual(preconditions["coordinator_url_present"]["status"], "blocked")
        self.assertIn("not a bind-all listen address", preconditions["coordinator_url_present"]["evidence"])
        self.assertFalse(confirmed["ok"])
        self.assertEqual(confirmed["data"]["cleanup_result"], "not_started_preconditions_blocked")
        self.assertNotIn("worker", getattr(facade, "_network_dispatcher_runtime", {}))
        bad_port_preconditions = {row["key"]: row for row in bad_port_dry_run["data"]["precondition_results"]}
        self.assertEqual(bad_port_preconditions["coordinator_url_present"]["status"], "blocked")
        self.assertIn("port must be in 1..65535", bad_port_preconditions["coordinator_url_present"]["evidence"])

    def test_coordinator_lifecycle_provider_starts_and_stops_dispatcher_without_pipeline_launch(self) -> None:
        class FakeCoordinatorDispatcher:
            instances: list[FakeCoordinatorDispatcher] = []

            def __init__(self, app: object) -> None:
                self.app = app
                self.shutdown_called = False
                FakeCoordinatorDispatcher.instances.append(self)

            def shutdown(self) -> None:
                self.shutdown_called = True

        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            service = DummyWorkflowFacadeService(root)
            service.build_queue_preview = lambda _resolved, force_refresh=False: [  # type: ignore[assignment]
                SimpleNamespace(source_path=root / "Movie.mkv", priority=False, estimated_size_gb=1.0)
            ]
            facade = MediaPipelineApplicationFacade(service, app_version="v5-test")
            resolved = _resolved(root)
            resolved.config_data = {
                "NetworkRole": "coordinator",
                "CoordinatorPort": 7830,
                "CoordinatorBindAddress": "127.0.0.1",
                "CoordinatorHeartbeatTimeoutMins": 5,
            }
            journaled: list[dict[str, object]] = []

            with patch(
                "mediapipeline.desktop.application.network_lifecycle_provider.CoordinatorDispatcher",
                FakeCoordinatorDispatcher,
            ):
                started = facade.request_network_lifecycle(
                    resolved,
                    role="coordinator",
                    action="start",
                    dry_run=False,
                    request={"confirm_start": True},
                    journal_recorder=lambda payload, _request: journaled.append(payload),
                ).to_mapping()
                stopped = facade.request_network_lifecycle(
                    resolved,
                    role="coordinator",
                    action="stop",
                    dry_run=False,
                    request={"confirm_stop": True},
                    journal_recorder=lambda payload, _request: journaled.append(payload),
                ).to_mapping()

        self.assertTrue(started["ok"])
        self.assertTrue(stopped["ok"])
        self.assertEqual(len(FakeCoordinatorDispatcher.instances), 1)
        self.assertEqual(len(FakeCoordinatorDispatcher.instances[0].app.queue_records), 1)
        self.assertTrue(FakeCoordinatorDispatcher.instances[0].shutdown_called)
        self.assertEqual(len(journaled), 2)
        self.assertFalse(hasattr(service, "started_pipeline"))

    def test_worker_provider_claimed_job_starts_backend_single_file_and_reports_done(self) -> None:
        class ProcWithWait(DummyProc):
            def wait(self) -> int:
                return 0

        class WorkerService(DummyWorkflowFacadeService):
            def start_pipeline(self, *args: object, **kwargs: object) -> ProcWithWait:  # type: ignore[override]
                super().start_pipeline(*args, **kwargs)  # type: ignore[arg-type]
                extra_argv = [str(item) for item in (kwargs.get("extra_argv") or [])]
                result_path = Path(extra_argv[extra_argv.index("-WorkerResultPath") + 1])
                result_path.parent.mkdir(parents=True, exist_ok=True)
                run_id = extra_argv[extra_argv.index("-WorkerRunId") + 1]
                claim_id = extra_argv[extra_argv.index("-WorkerClaimId") + 1]
                result_path.write_text(
                    json.dumps(
                        {
                            "SchemaVersion": "local_worker_result.v1",
                            "Success": True,
                            "Status": "processed",
                            "Reason": "ok",
                            "ErrorCode": "",
                            "SourcePath": str(root / "Claimed.mkv"),
                            "SourceName": "Claimed.mkv",
                            "Route": "encode",
                            "PublishState": "published",
                            "PublishMode": "direct",
                            "OutputPath": str(root / "Out" / "Claimed.mkv"),
                            "OutputSizeBytes": 123,
                            "QueueTerminal": False,
                            "Retryable": True,
                            "WorkerSlotId": 0,
                            "WorkerRunId": run_id,
                            "WorkerClaimId": claim_id,
                        }
                    ),
                    encoding="utf-8",
                )
                return ProcWithWait()

        class FakeWorkerDispatcher:
            instances: list[FakeWorkerDispatcher] = []

            def __init__(self, app: object) -> None:
                self.app = app
                self.done: list[dict[str, object]] = []
                self.shutdown_called = False
                FakeWorkerDispatcher.instances.append(self)

            def set_status_callback(self, _callback: object) -> None:
                return None

            def mark_done(self, _job: object, **kwargs: object) -> None:
                self.done.append(dict(kwargs))

            def shutdown(self) -> None:
                self.shutdown_called = True

        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            service = WorkerService(root)
            facade = MediaPipelineApplicationFacade(service, app_version="v5-test")
            resolved = _resolved(root)
            resolved.config_data = {
                "NetworkRole": "worker",
                "WorkerCoordinatorUrl": "http://coordinator.test:7830",
                "WorkerAuthToken": "worker-token",
            }

            with patch(
                "mediapipeline.desktop.application.network_lifecycle_provider.WorkerDispatcher",
                FakeWorkerDispatcher,
            ):
                started = facade.request_network_lifecycle(
                    resolved,
                    role="worker",
                    action="start",
                    dry_run=False,
                    request={"confirm_start": True},
                    journal_recorder=lambda _payload, _request: None,
                ).to_mapping()
                dispatcher = FakeWorkerDispatcher.instances[0]
                job = SimpleNamespace(
                    job_id="job-1",
                    record=SimpleNamespace(source_path=root / "Claimed.mkv"),
                )
                dispatcher.app._worker_start_single_file(job)
                deadline = time.time() + 2.0
                while not dispatcher.done and time.time() < deadline:
                    time.sleep(0.01)
                stopped = facade.request_network_lifecycle(
                    resolved,
                    role="worker",
                    action="stop",
                    dry_run=False,
                    request={"confirm_stop": True},
                    journal_recorder=lambda _payload, _request: None,
                ).to_mapping()

        self.assertTrue(started["ok"])
        self.assertTrue(stopped["ok"])
        self.assertEqual(service.started_pipeline["single_file"], str(root / "Claimed.mkv"))
        self.assertEqual(service.started_pipeline["mode"], "once")
        self.assertIn("-WorkerResultPath", service.started_pipeline["extra_argv"])
        self.assertTrue(dispatcher.done)
        self.assertTrue(dispatcher.done[0]["success"])
        self.assertEqual(dispatcher.done[0]["completion_status"], "processed")
        self.assertEqual(dispatcher.done[0]["publish_state"], "published")
        self.assertEqual(dispatcher.done[0]["publish_mode"], "direct")
        self.assertEqual(dispatcher.done[0]["output_path"], str(root / "Out" / "Claimed.mkv"))
        self.assertEqual(dispatcher.done[0]["output_size_bytes"], 123)
        self.assertEqual(dispatcher.done[0]["route"], "encode")
        self.assertFalse(dispatcher.done[0]["queue_terminal"])
        self.assertTrue(dispatcher.done[0]["retry_on_failure"])
        self.assertTrue(dispatcher.shutdown_called)

    def test_worker_provider_result_artifact_failure_paths_and_field_propagation(self) -> None:
        class ProcWithWait(DummyProc):
            def __init__(self, return_code: int = 0) -> None:
                super().__init__()
                self._return_code = return_code

            def wait(self) -> int:
                return self._return_code

        class Dispatcher:
            def __init__(self) -> None:
                self.done: list[dict[str, object]] = []

            def mark_done(self, _job: object, **kwargs: object) -> None:
                self.done.append(dict(kwargs))

        cases: list[tuple[str, object, dict[str, object]]] = [
            (
                "pending_publish",
                {
                    "Success": True,
                    "Status": "pending_publish",
                    "Reason": "",
                    "ErrorCode": "",
                    "Route": "encode",
                    "PublishState": "parked",
                    "PublishMode": "pending_publish",
                    "OutputPath": "D:/Pending/Movie.mkv",
                    "OutputSizeBytes": 456,
                    "QueueTerminal": False,
                    "Retryable": True,
                },
                {
                    "success": True,
                    "completion_status": "pending_publish",
                    "publish_state": "parked",
                    "publish_mode": "pending_publish",
                    "output_path": "D:/Pending/Movie.mkv",
                    "output_size_bytes": 456,
                    "retry_on_failure": True,
                },
            ),
            (
                "failure_terminal",
                {
                    "Success": False,
                    "Status": "failed",
                    "Reason": "ffmpeg failed",
                    "ErrorCode": "ENCODE_ERROR",
                    "Route": "encode",
                    "PublishState": "",
                    "PublishMode": "",
                    "OutputPath": "",
                    "OutputSizeBytes": 0,
                    "QueueTerminal": True,
                    "Retryable": False,
                },
                {
                    "success": False,
                    "completion_status": "failed",
                    "reason_code": "ENCODE_ERROR",
                    "reason": "ffmpeg failed",
                    "queue_terminal": True,
                    "retry_on_failure": False,
                },
            ),
            ("missing", None, {"success": False, "completion_status": "failed_result_missing"}),
            ("unreadable", "{not json", {"success": False, "completion_status": "failed_result_invalid"}),
            (
                "wrong_claim",
                {"Success": True, "Status": "processed", "WorkerClaimId": "other-claim"},
                {"success": False, "completion_status": "failed_result_invalid"},
            ),
            (
                "wrong_run",
                {"Success": True, "Status": "processed", "WorkerRunId": "other-run"},
                {"success": False, "completion_status": "failed_result_invalid"},
            ),
            (
                "string_output_size",
                {"Success": True, "Status": "processed", "OutputSizeBytes": "456"},
                {"success": False, "completion_status": "failed_result_invalid"},
            ),
            (
                "float_output_size",
                {"Success": True, "Status": "processed", "OutputSizeBytes": 4.5},
                {"success": False, "completion_status": "failed_result_invalid"},
            ),
            (
                "negative_output_size",
                {"Success": True, "Status": "processed", "OutputSizeBytes": -1},
                {"success": False, "completion_status": "failed_result_invalid"},
            ),
            (
                "string_elapsed_seconds",
                {"Success": True, "Status": "processed", "ElapsedSeconds": "12"},
                {"success": False, "completion_status": "failed_result_invalid"},
            ),
        ]

        for name, result_payload, expected in cases:
            with self.subTest(name=name), tempfile.TemporaryDirectory() as raw_root:
                root = Path(raw_root)

                def make_worker_service(case_result_payload: object, case_root: Path) -> type[DummyWorkflowFacadeService]:
                    class WorkerService(DummyWorkflowFacadeService):
                        def start_pipeline(self, *args: object, **kwargs: object) -> ProcWithWait:  # type: ignore[override]
                            super().start_pipeline(*args, **kwargs)  # type: ignore[arg-type]
                            extra_argv = [str(item) for item in (kwargs.get("extra_argv") or [])]
                            result_path = Path(extra_argv[extra_argv.index("-WorkerResultPath") + 1])
                            result_path.parent.mkdir(parents=True, exist_ok=True)
                            run_id = extra_argv[extra_argv.index("-WorkerRunId") + 1]
                            claim_id = extra_argv[extra_argv.index("-WorkerClaimId") + 1]
                            if isinstance(case_result_payload, str):
                                result_path.write_text(case_result_payload, encoding="utf-8")
                            elif isinstance(case_result_payload, dict):
                                payload = {
                                    "SchemaVersion": "local_worker_result.v1",
                                    "SourcePath": str(case_root / "Claimed.mkv"),
                                    "SourceName": "Claimed.mkv",
                                    "WorkerSlotId": 0,
                                    "WorkerRunId": run_id,
                                    "WorkerClaimId": claim_id,
                                    "QueueTerminal": False,
                                    "Retryable": True,
                                    "OutputSizeBytes": 0,
                                    **case_result_payload,
                                }
                                result_path.write_text(json.dumps(payload), encoding="utf-8")
                            return ProcWithWait()

                    return WorkerService

                service = make_worker_service(result_payload, root)(root)
                facade = MediaPipelineApplicationFacade(service, app_version="v5-test")
                resolved = _resolved(root)
                app = _NetworkRuntimeApp(facade, resolved, role="worker")
                dispatcher = Dispatcher()
                app.dispatcher = dispatcher
                job = SimpleNamespace(
                    job_id="job-1",
                    record=SimpleNamespace(source_path=root / "Claimed.mkv"),
                )
                app._worker_start_single_file(job)
                deadline = time.time() + 2.0
                while not dispatcher.done and time.time() < deadline:
                    time.sleep(0.01)

                self.assertTrue(dispatcher.done)
                done = dispatcher.done[0]
                for key, value in expected.items():
                    self.assertEqual(done.get(key), value, key)

    def test_network_lifecycle_provider_signature_mismatch_fails_closed_without_retry(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            service = DummyWorkflowFacadeService(root)
            calls: list[object] = []

            def provider(_resolved: object, _request: object) -> None:
                calls.append((_resolved, _request))

            service.start_network_coordinator = provider  # type: ignore[attr-defined]
            facade = MediaPipelineApplicationFacade(service, app_version="v5-test")
            resolved = _resolved(root)
            resolved.config_data = {
                "NetworkRole": "coordinator",
                "CoordinatorPort": 7830,
                "CoordinatorBindAddress": "127.0.0.1",
                "CoordinatorHeartbeatTimeoutMins": 5,
            }

            result = facade.request_network_lifecycle(
                resolved,
                role="coordinator",
                action="start",
                dry_run=False,
                request={"confirm_start": True},
                journal_recorder=lambda _payload, _request: None,
            ).to_mapping()

        self.assertFalse(result["ok"])
        self.assertEqual(result["data"]["cleanup_result"], "provider_exception")
        self.assertIn("unexpected keyword", "\n".join(result["errors"]))
        self.assertEqual(calls, [])
        self.assertEqual(facade._network_lifecycle_state_for("coordinator")["status"], "stopped")

    def test_network_lifecycle_journal_failure_does_not_commit_state(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            service = DummyWorkflowFacadeService(root)
            provider_calls: list[dict[str, object]] = []

            def provider(**kwargs: object) -> None:
                provider_calls.append(dict(kwargs))

            def failing_journal(_payload: dict[str, object], _request: dict[str, object] | None) -> None:
                raise RuntimeError("journal path unavailable")

            service.start_network_coordinator = provider  # type: ignore[attr-defined]
            facade = MediaPipelineApplicationFacade(service, app_version="v5-test")
            resolved = _resolved(root)
            resolved.config_data = {
                "NetworkRole": "coordinator",
                "CoordinatorPort": 7830,
                "CoordinatorBindAddress": "127.0.0.1",
                "CoordinatorHeartbeatTimeoutMins": 5,
            }

            result = facade.request_network_lifecycle(
                resolved,
                role="coordinator",
                action="start",
                dry_run=False,
                request={"confirm_start": True},
                journal_recorder=failing_journal,
            ).to_mapping()

        self.assertFalse(result["ok"])
        self.assertEqual(result["data"]["cleanup_result"], "command_journal_failed_provider_cleanup_ok")
        self.assertEqual(len(provider_calls), 1)
        self.assertEqual(facade._network_lifecycle_state_for("coordinator")["status"], "stopped")

    def test_network_lifecycle_success_requires_strict_journal_before_state_commit_and_blocks_duplicates(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            service = DummyWorkflowFacadeService(root)
            start_calls: list[dict[str, object]] = []
            stop_calls: list[dict[str, object]] = []
            journaled: list[tuple[dict[str, object], dict[str, object] | None]] = []

            service.start_network_coordinator = lambda **kwargs: start_calls.append(dict(kwargs))  # type: ignore[attr-defined]
            service.stop_network_coordinator = lambda **kwargs: stop_calls.append(dict(kwargs))  # type: ignore[attr-defined]
            facade = MediaPipelineApplicationFacade(service, app_version="v5-test")
            resolved = _resolved(root)
            resolved.config_data = {
                "NetworkRole": "coordinator",
                "CoordinatorPort": 7830,
                "CoordinatorBindAddress": "127.0.0.1",
                "CoordinatorHeartbeatTimeoutMins": 5,
            }

            def journal_recorder(payload: dict[str, object], request: dict[str, object] | None) -> None:
                journaled.append((payload, request))

            first_start = facade.request_network_lifecycle(
                resolved,
                role="coordinator",
                action="start",
                dry_run=False,
                request={"confirm_start": True, "reason": "start"},
                journal_recorder=journal_recorder,
            ).to_mapping()
            duplicate_start = facade.request_network_lifecycle(
                resolved,
                role="coordinator",
                action="start",
                dry_run=False,
                request={"confirm_start": True},
                journal_recorder=journal_recorder,
            ).to_mapping()
            first_stop = facade.request_network_lifecycle(
                resolved,
                role="coordinator",
                action="stop",
                dry_run=False,
                request={"confirm_stop": True, "reason": "stop"},
                journal_recorder=journal_recorder,
            ).to_mapping()
            duplicate_stop = facade.request_network_lifecycle(
                resolved,
                role="coordinator",
                action="stop",
                dry_run=False,
                request={"confirm_stop": True},
                journal_recorder=journal_recorder,
            ).to_mapping()

        self.assertTrue(first_start["ok"])
        self.assertTrue(first_start["data"]["strict_command_journal_recorded"])
        self.assertEqual(first_start["data"]["state_before"]["status"], "stopped")
        self.assertEqual(first_start["data"]["state_after"]["status"], "running")
        self.assertEqual(first_start["data"]["cleanup_result"], "ok")
        self.assertFalse(duplicate_start["ok"])
        self.assertEqual(duplicate_start["data"]["cleanup_result"], "not_started_preconditions_blocked")
        self.assertIn("duplicate_start_guard", duplicate_start["errors"])
        self.assertTrue(first_stop["ok"])
        self.assertEqual(first_stop["data"]["state_before"]["status"], "running")
        self.assertEqual(first_stop["data"]["state_after"]["status"], "stopped")
        self.assertTrue(duplicate_stop["ok"])
        self.assertEqual(duplicate_stop["data"]["state_before"]["status"], "stopped")
        self.assertEqual(duplicate_stop["data"]["state_after"]["status"], "stopped")
        self.assertEqual(len(start_calls), 1)
        self.assertEqual(len(stop_calls), 2)
        self.assertEqual(len(journaled), 3)
        journal_payload = journaled[0][0]
        self.assertIn("command_id", journal_payload["data"])
        self.assertIn("state_before", journal_payload["data"])
        self.assertIn("state_after", journal_payload["data"])
        self.assertEqual(journal_payload["data"]["cleanup_result"], "ok")
        self.assertIn("redacted_config_evidence", journal_payload["data"])

    def test_network_lifecycle_concurrent_start_requests_are_serialized(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            service = DummyWorkflowFacadeService(root)
            provider_calls: list[dict[str, object]] = []
            journaled: list[dict[str, object]] = []

            def provider(**kwargs: object) -> None:
                time.sleep(0.05)
                provider_calls.append(dict(kwargs))

            service.start_network_coordinator = provider  # type: ignore[attr-defined]
            facade = MediaPipelineApplicationFacade(service, app_version="v5-test")
            resolved = _resolved(root)
            resolved.config_data = {
                "NetworkRole": "coordinator",
                "CoordinatorPort": 7830,
                "CoordinatorBindAddress": "127.0.0.1",
                "CoordinatorHeartbeatTimeoutMins": 5,
            }
            results: list[dict[str, object]] = []

            def run_start() -> None:
                result = facade.request_network_lifecycle(
                    resolved,
                    role="coordinator",
                    action="start",
                    dry_run=False,
                    request={"confirm_start": True},
                    journal_recorder=lambda payload, _request: journaled.append(payload),
                ).to_mapping()
                results.append(result)

            threads = [threading.Thread(target=run_start) for _ in range(2)]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join()

        self.assertEqual(sum(1 for result in results if result["ok"]), 1)
        self.assertEqual(sum(1 for result in results if not result["ok"]), 1)
        self.assertEqual(len(provider_calls), 1)
        self.assertEqual(len(journaled), 1)

    def test_worker_lifecycle_pending_done_read_failure_blocks_and_redacts_config(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            service = DummyWorkflowFacadeService(root)
            facade = MediaPipelineApplicationFacade(service, app_version="v5-test")
            resolved = _resolved(root)
            resolved.config_data = {
                "NetworkRole": "worker",
                "WorkerCoordinatorUrl": "http://user:pass@example.test:7830/claim?token=secret#frag",
                "WorkerName": "worker-a",
                "WorkerAuthToken": "token-secret",
            }

            def fail_worker_state(_resolved_paths: object) -> object:
                raise RuntimeError("worker state unreadable")

            facade.get_network_workers = fail_worker_state  # type: ignore[method-assign]
            dry_run = facade.request_network_lifecycle(
                resolved,
                role="worker",
                action="start",
                dry_run=True,
                request={},
            ).to_mapping()

        preconditions = {row["key"]: row for row in dry_run["data"]["precondition_results"]}
        self.assertEqual(preconditions["pending_done_reports_delivered"]["status"], "blocked")
        self.assertIn("pending_done_report=unknown", preconditions["pending_done_reports_delivered"]["evidence"])
        self.assertTrue(dry_run["data"]["active_work"]["state_read_failed"])
        redacted = dry_run["data"]["redacted_config_evidence"]
        self.assertEqual(redacted["WorkerCoordinatorUrl"], "http://example.test:7830/claim")
        self.assertEqual(redacted["WorkerAuthToken"], "present_redacted")
        self.assertNotIn("secret", str(redacted))

    def test_pipeline_start_respects_schedule_gate_before_web_launch_ui(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            service = DummyWorkflowFacadeService(root)
            service.save_app_state({"schedule_enabled": True, "schedule_grid": service.default_schedule_grid()})
            facade = MediaPipelineApplicationFacade(service, app_version="v5-test")
            resolved = _resolved(root)

            blocked = facade.start_pipeline_process(resolved, {"mode": "continuous"}).to_mapping()
            run_once = facade.start_pipeline_process(
                resolved,
                {"mode": "continuous", "schedule_override": "run_once"},
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

            continuous = facade.start_pipeline_process(resolved, {"mode": "continuous"}).to_mapping()
            once = facade.start_pipeline_process(resolved, {"mode": "once"}).to_mapping()

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

    def test_network_rerun_start_dry_run_reports_state_files_without_writing(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            service = DummyWorkflowFacadeService(root)
            facade = MediaPipelineApplicationFacade(service, app_version="v5-test")
            resolved = _resolved(root)
            resolved.local_base = root / "LocalBase"
            resolved.state_root = resolved.local_base / "State"
            source_root = root / "ProfileSource"
            profile_out = root / "ProfileOut"
            handoff_root = root / "NetworkRerunHandoff"
            handoff_root.mkdir()
            movie = source_root / "Movie.mkv"
            movie.parent.mkdir(parents=True)
            movie.write_bytes(b"media")
            csv_path = root / "rerun.csv"
            csv_path.write_text(
                f"enabled,source_path,audit_issue_codes,plex_planned_path\ntrue,{movie},AUDIO,{profile_out / 'Movie.mkv'}\n",
                encoding="utf-8",
            )
            resolved.config_data = {
                "NetworkRole": "coordinator",
                "CoordinatorPort": 7830,
                "CoordinatorBindAddress": "127.0.0.1",
                "CoordinatorHeartbeatTimeoutMins": 5,
                "Outsource": str(root / "Outsource"),
                "NetworkRerunHandoffRoot": str(handoff_root),
                "LibraryProfiles": [
                    {
                        "id": "profile",
                        "enabled": True,
                        "source_path": str(source_root),
                        "output_path": str(profile_out),
                    }
                ],
            }
            facade._network_lifecycle_state_commit("coordinator", {"role": "coordinator", "status": "running"})

            result = facade.dry_run_network_rerun_csv_start(
                resolved,
                {"csv_path": str(csv_path), "confirm_replace_final": True, "reason": "operator review"},
            ).to_mapping()

        data = result["data"]
        self.assertTrue(result["ok"])
        self.assertTrue(data["safe_to_apply"])
        self.assertTrue(data["dry_run_only"])
        self.assertEqual(data["effect"], "none")
        self.assertEqual(data["dry_run_writes"], [])
        self.assertFalse(data["touches_media"])
        self.assertFalse(data["writes_queue"])
        self.assertFalse(data["writes_network_state"])
        self.assertFalse(data["launches_work"])
        self.assertEqual(data["preview"]["counts"]["claimable_rows"], 1)
        self.assertEqual(data["preview"]["counts"]["start_ready_rows"], 1)
        self.assertEqual(data["output_handoff"]["status"], "ready")
        self.assertEqual(data["state_files_would_write"][0]["schema_version"], "desktop_rerun_network_batch.v1")
        self.assertIn("command_journal_entry", data["confirmed_route_would_write"])
        self.assertFalse((root / "LocalBase" / "State" / "Rerun" / "Network").exists())
        preconditions = {row["key"]: row for row in data["precondition_results"]}
        self.assertEqual(preconditions["NetworkRole_is_coordinator"]["status"], "pass")
        self.assertEqual(preconditions["coordinator_lifecycle_running"]["status"], "pass")
        self.assertEqual(preconditions["backend_close_readiness_safe"]["status"], "pass")
        self.assertEqual(preconditions["network_preview_has_claimable_rows"]["status"], "pass")
        self.assertEqual(preconditions["network_rerun_handoff_ready"]["status"], "pass")
        self.assertEqual(preconditions["network_rerun_handoff_remote_worker_compatible"]["status"], "review")
        self.assertEqual(preconditions["worker_availability_evidence"]["status"], "review")
        self.assertTrue(data["dry_run_fingerprint"])
        self.assertEqual(preconditions["network_batch_state_path_available"]["status"], "pass")

    def test_network_rerun_start_dry_run_blocks_without_coordinator_role_or_lifecycle(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            service = DummyWorkflowFacadeService(root)
            facade = MediaPipelineApplicationFacade(service, app_version="v5-test")
            resolved = _resolved(root)
            resolved.local_base = root / "LocalBase"
            resolved.state_root = resolved.local_base / "State"
            movie = _media_file(root, "Movie")
            csv_path = root / "rerun.csv"
            csv_path.write_text(f"enabled,source_path,audit_issue_codes\ntrue,{movie},AUDIO\n", encoding="utf-8")
            resolved.config_data = {"NetworkRole": "standalone", "Outsource": str(root / "Outsource")}

            result = facade.dry_run_network_rerun_csv_start(
                resolved,
                {"csv_path": str(csv_path), "confirm_replace_final": True, "minimum_worker_count": 1},
            ).to_mapping()

        data = result["data"]
        self.assertFalse(data["safe_to_apply"])
        preconditions = {row["key"]: row for row in data["precondition_results"]}
        self.assertEqual(preconditions["NetworkRole_is_coordinator"]["status"], "blocked")
        self.assertEqual(preconditions["coordinator_lifecycle_running"]["status"], "blocked")
        self.assertEqual(preconditions["worker_availability_evidence"]["status"], "blocked")
        self.assertEqual(data["dry_run_writes"], [])
        self.assertFalse(data["writes_network_state"])

    def test_network_rerun_start_dry_run_blocks_missing_handoff_root(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            service = DummyWorkflowFacadeService(root)
            facade = MediaPipelineApplicationFacade(service, app_version="v5-test")
            resolved = _resolved(root)
            resolved.local_base = root / "LocalBase"
            resolved.state_root = resolved.local_base / "State"
            movie = _media_file(root, "Movie")
            csv_path = root / "rerun.csv"
            csv_path.write_text(f"enabled,source_path,audit_issue_codes\ntrue,{movie},AUDIO\n", encoding="utf-8")
            resolved.config_data = {
                "NetworkRole": "coordinator",
                "Outsource": str(root / "Outsource"),
            }
            facade._network_lifecycle_state_commit("coordinator", {"role": "coordinator", "status": "running"})

            result = facade.dry_run_network_rerun_csv_start(
                resolved,
                {"csv_path": str(csv_path), "confirm_replace_final": True},
            ).to_mapping()

        data = result["data"]
        self.assertFalse(data["safe_to_apply"])
        preconditions = {row["key"]: row for row in data["precondition_results"]}
        self.assertEqual(preconditions["network_rerun_handoff_ready"]["status"], "blocked")
        self.assertIn("start_ready_rows=0", preconditions["network_rerun_handoff_ready"]["evidence"])
        self.assertEqual(data["output_handoff"]["status"], "not_configured")
        self.assertIn("network_rerun_handoff_not_ready", data["preview"]["start_blockers"])
        self.assertFalse((root / "LocalBase" / "State" / "Rerun" / "Network").exists())

    def test_network_rerun_start_writes_claim_enabled_batch_state_and_strict_journal(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            service = DummyWorkflowFacadeService(root)
            facade = MediaPipelineApplicationFacade(service, app_version="v5-test")
            resolved = _resolved(root)
            resolved.local_base = root / "LocalBase"
            resolved.state_root = resolved.local_base / "State"
            source_root = root / "ProfileSource"
            profile_out = root / "ProfileOut"
            handoff_root = root / "NetworkRerunHandoff"
            handoff_root.mkdir()
            movie = source_root / "Movie.mkv"
            movie.parent.mkdir(parents=True)
            movie.write_bytes(b"media")
            csv_path = root / "rerun.csv"
            csv_path.write_text(
                f"enabled,source_path,audit_issue_codes,plex_planned_path\ntrue,{movie},AUDIO,{profile_out / 'Movie.mkv'}\n",
                encoding="utf-8",
            )
            resolved.config_data = {
                "NetworkRole": "coordinator",
                "CoordinatorPort": 7830,
                "CoordinatorBindAddress": "127.0.0.1",
                "CoordinatorHeartbeatTimeoutMins": 5,
                "Outsource": str(root / "Outsource"),
                "NetworkRerunHandoffRoot": str(handoff_root),
                "LibraryProfiles": [
                    {
                        "id": "profile",
                        "enabled": True,
                        "source_path": str(source_root),
                        "output_path": str(profile_out),
                    }
                ],
            }
            facade._network_lifecycle_state_commit("coordinator", {"role": "coordinator", "status": "running"})
            request = {"csv_path": str(csv_path), "confirm_replace_final": True, "reason": "operator review"}
            dry_run = facade.dry_run_network_rerun_csv_start(resolved, request).to_mapping()
            journal: list[dict[str, object]] = []

            result = facade.start_network_rerun_csv_batch(
                resolved,
                {**request, "dry_run_fingerprint": dry_run["data"]["dry_run_fingerprint"], "confirm_start": True},
                journal_recorder=lambda payload, request_body: journal.append({"payload": payload, "request": request_body}),
            ).to_mapping()

            state_path = Path(result["data"]["state_file"]["path"])
            state = json.loads(state_path.read_text(encoding="utf-8"))

        self.assertTrue(result["ok"])
        self.assertEqual(result["command"], "rerun.network.start")
        self.assertTrue(result["data"]["strict_command_journal_recorded"])
        self.assertTrue(result["data"]["state_written"])
        self.assertTrue(result["data"]["writes_network_state"])
        self.assertFalse(result["data"]["touches_media"])
        self.assertFalse(result["data"]["writes_queue"])
        self.assertFalse(result["data"]["launches_work"])
        self.assertEqual(len(journal), 1)
        self.assertEqual(journal[0]["payload"]["command"], "rerun.network.start")
        self.assertEqual(state["schema_version"], "desktop_rerun_network_batch.v1")
        self.assertEqual(state["status"], "active")
        self.assertTrue(state["claim_provider_enabled"])
        self.assertTrue(state["worker_execution_enabled"])
        self.assertTrue(state["rows_claimable"])
        self.assertEqual(state["phase"], "phase_4b_csv_row_claim_execution")
        self.assertEqual(state["output_handoff"]["status"], "ready")
        self.assertEqual(state["handoff_probe"]["status"], "pass")
        self.assertEqual(state["row_count"], 1)
        self.assertTrue(state["rows"][0]["claimable"])
        self.assertEqual(state["rows"][0]["status"], "pending_claim")
        self.assertEqual(state["rows"][0]["claim_status"], "pending_claim")
        self.assertTrue(state["rows"][0]["planned_output_path"].endswith(state["rows"][0]["row_key"]))
        self.assertEqual(state["rows"][0]["output_handoff"]["batch_id"], state["batch_id"])

    def test_network_rerun_phase8_start_claim_done_destination_and_read_model(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            service = DummyWorkflowFacadeService(root)
            facade = MediaPipelineApplicationFacade(service, app_version="v5-test")
            resolved = _resolved(root)
            resolved.local_base = root / "LocalBase"
            resolved.state_root = resolved.local_base / "State"
            source_root = root / "ProfileSource"
            profile_out = root / "ProfileOut"
            outsource = root / "Outsource"
            handoff_root = root / "NetworkRerunHandoff"
            handoff_root.mkdir()
            movie = source_root / "Phase8.Movie.2026.mkv"
            movie.parent.mkdir(parents=True)
            movie.write_bytes(b"phase8-source-media")
            source_hash_before = _sha256(movie)
            final_output = profile_out / "Phase8 Movie (2026).mkv"
            csv_path = root / "phase8-rerun.csv"
            csv_path.write_text(
                "enabled,source_path,audit_issue_codes,plex_planned_path,"
                "source_identity_v2,source_identity_v2_algorithm,"
                "source_content_sha256,source_content_sha256_algorithm\n"
                f"true,{movie},AUDIO,{final_output},{source_hash_before},sha256,"
                f"{source_hash_before},sha256-full-file\n",
                encoding="utf-8",
            )
            resolved.config_data = {
                "NetworkRole": "coordinator",
                "CoordinatorPort": 7830,
                "CoordinatorBindAddress": "127.0.0.1",
                "CoordinatorHeartbeatTimeoutMins": 5,
                "Outsource": str(outsource),
                "NetworkRerunHandoffRoot": str(handoff_root),
                "LibraryProfiles": [
                    {
                        "id": "profile",
                        "enabled": True,
                        "source_path": str(source_root),
                        "output_path": str(profile_out),
                    }
                ],
            }
            facade._network_lifecycle_state_commit("coordinator", {"role": "coordinator", "status": "running"})
            request = {
                "csv_path": str(csv_path),
                "destination_mode": "pending_publish",
                "collision_policy": "suffix",
                "reason": "phase8 end-to-end validation",
            }
            dry_run = facade.dry_run_network_rerun_csv_start(resolved, request).to_mapping()
            journal: list[dict[str, object]] = []

            start = facade.start_network_rerun_csv_batch(
                resolved,
                {**request, "dry_run_fingerprint": dry_run["data"]["dry_run_fingerprint"], "confirm_start": True},
                journal_recorder=lambda payload, request_body: journal.append({"payload": payload, "request": request_body}),
            ).to_mapping()

            state_path = Path(start["data"]["state_file"]["path"])
            app = SimpleNamespace(resolved=resolved, product_version="v5-test")
            registry = InFlightRegistry()
            first_lease = claim_next_network_rerun_row(
                app=app,
                registry=registry,
                worker_id="worker-phase8-a",
                worker_name="Phase 8 Worker A",
                accessible_library_ids=["profile"],
                encode_config_for_row=lambda record: {"record_source": str(record.source_path)},
                allow_local_handoff=True,
                job_id="phase8-release",
            )
            assert first_lease is not None
            duplicate = claim_next_network_rerun_row(
                app=app,
                registry=registry,
                worker_id="worker-phase8-b",
                worker_name="Phase 8 Worker B",
                accessible_library_ids=["profile"],
                encode_config_for_row=lambda _record: {},
                allow_local_handoff=True,
                job_id="phase8-duplicate",
            )
            released = registry.unclaim(first_lease.response.job_id, "worker-phase8-a")
            assert released is not None
            update_network_rerun_row_released(app=app, job=released, worker_id="worker-phase8-a", reason="phase8 restart")
            with registry._lock:
                registry._recent_completions.clear()
            second_lease = claim_next_network_rerun_row(
                app=app,
                registry=registry,
                worker_id="worker-phase8-b",
                worker_name="Phase 8 Worker B",
                accessible_library_ids=["profile"],
                encode_config_for_row=lambda record: {"record_source": str(record.source_path)},
                allow_local_handoff=True,
                job_id="phase8-complete",
            )
            assert second_lease is not None
            output_path = Path(second_lease.response.planned_output_path) / "Phase8 Movie (2026).mkv"
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_bytes(b"phase8-worker-output")
            artifact_path = _write_network_worker_result_artifact(
                root,
                job_id=second_lease.response.job_id,
                output_path=output_path,
                batch_id=str(second_lease.response.rerun_batch_id),
                row_key=str(second_lease.response.rerun_row_key),
            )
            completed = registry.complete(second_lease.response.job_id, "worker-phase8-b", success=True)
            assert completed is not None
            update_network_rerun_row_done(
                app=app,
                job=completed,
                request=SimpleNamespace(
                    job_id=second_lease.response.job_id,
                    worker_id="worker-phase8-b",
                    success=True,
                    output_path=str(output_path),
                    output_size_bytes=output_path.stat().st_size,
                    completion_status="processed",
                    publish_state="published",
                    publish_mode="handoff",
                    route="network_lifecycle_single_file",
                    reason_code="",
                    reason="",
                    error_message="",
                    queue_terminal=False,
                    retry_on_failure=True,
                    worker_result_artifact_path=str(artifact_path),
                ),
            )

            state = json.loads(state_path.read_text(encoding="utf-8"))
            row = state["rows"][0]
            results = rerun_results_payload(resolved, service=service, limit=24)
            network_rows = [item for item in results["rows"] if item.get("queue_source") == "network_csv_rerun"]
            terminal_claim = claim_next_network_rerun_row(
                app=app,
                registry=registry,
                worker_id="worker-phase8-c",
                worker_name="Phase 8 Worker C",
                accessible_library_ids=["profile"],
                encode_config_for_row=lambda _record: {},
                allow_local_handoff=True,
                job_id="phase8-after-terminal",
            )
            source_hash_after = _sha256(movie)
            output_exists_after = output_path.exists()
            final_output_exists_after = final_output.exists()
            pending_manifest_exists = Path(row["pending_publish_manifest_path"]).is_file()
            pending_payload_path = Path(row["pending_publish_payload_path"])
            pending_payload_exists = pending_payload_path.is_file()
            pending_payload_bytes = pending_payload_path.read_bytes() if pending_payload_exists else b""

        self.assertTrue(dry_run["ok"])
        self.assertTrue(dry_run["data"]["safe_to_apply"])
        self.assertTrue(start["ok"])
        self.assertEqual(len(journal), 1)
        self.assertEqual(journal[0]["payload"]["command"], "rerun.network.start")
        self.assertEqual(first_lease.response.job_kind, "csv_rerun_row")
        self.assertEqual(
            first_lease.response.source_identity["source_content_sha256"],
            source_hash_before,
        )
        self.assertIsNone(duplicate)
        self.assertEqual(second_lease.response.job_kind, "csv_rerun_row")
        self.assertEqual(row["status"], "pending_publish")
        self.assertFalse(row["claimable"])
        self.assertEqual(row["destination_policy_result"]["status"], "pending_publish")
        self.assertTrue(row["destination_policy_result"]["ok"])
        self.assertTrue(row["destination_policy_applied"])
        self.assertEqual(row["reducer_result"]["classification"], "success")
        self.assertEqual(source_hash_after, source_hash_before)
        self.assertFalse(output_exists_after)
        self.assertFalse(final_output_exists_after)
        self.assertTrue(pending_manifest_exists)
        self.assertTrue(pending_payload_exists)
        self.assertEqual(pending_payload_bytes, b"phase8-worker-output")
        self.assertEqual(len(network_rows), 1)
        self.assertEqual(network_rows[0]["queue_status"], "pending_publish")
        self.assertTrue(network_rows[0]["destination_state"]["destination_policy_applied"])
        self.assertEqual(network_rows[0]["destination_state"]["destination_policy_status"], "pending_publish")
        self.assertTrue(results["queue_state"]["contains_network_csv_rerun"])
        self.assertIsNone(terminal_claim)

    def test_network_rerun_start_rejects_stale_dry_run_fingerprint_without_writing_state(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            service = DummyWorkflowFacadeService(root)
            facade = MediaPipelineApplicationFacade(service, app_version="v5-test")
            resolved = _resolved(root)
            resolved.local_base = root / "LocalBase"
            resolved.state_root = resolved.local_base / "State"
            movie = _media_file(root, "Movie")
            csv_path = root / "rerun.csv"
            csv_path.write_text(f"enabled,source_path,audit_issue_codes\ntrue,{movie},AUDIO\n", encoding="utf-8")
            handoff_root = root / "NetworkRerunHandoff"
            handoff_root.mkdir()
            resolved.config_data = {
                "NetworkRole": "coordinator",
                "Outsource": str(root / "Outsource"),
                "NetworkRerunHandoffRoot": str(handoff_root),
            }
            facade._network_lifecycle_state_commit("coordinator", {"role": "coordinator", "status": "running"})

            result = facade.start_network_rerun_csv_batch(
                resolved,
                {
                    "csv_path": str(csv_path),
                    "confirm_replace_final": True,
                    "dry_run_fingerprint": "stale",
                    "confirm_start": True,
                },
                journal_recorder=lambda _payload, _request: None,
            ).to_mapping()

        self.assertFalse(result["ok"])
        self.assertIn("dry_run_fingerprint_mismatch", result["errors"])
        self.assertFalse((root / "LocalBase" / "State" / "Rerun" / "Network").exists())

    def test_network_rerun_start_cleans_batch_state_when_strict_journal_fails(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            service = DummyWorkflowFacadeService(root)
            facade = MediaPipelineApplicationFacade(service, app_version="v5-test")
            resolved = _resolved(root)
            resolved.local_base = root / "LocalBase"
            resolved.state_root = resolved.local_base / "State"
            movie = _media_file(root, "Movie")
            csv_path = root / "rerun.csv"
            csv_path.write_text(f"enabled,source_path,audit_issue_codes\ntrue,{movie},AUDIO\n", encoding="utf-8")
            handoff_root = root / "NetworkRerunHandoff"
            handoff_root.mkdir()
            resolved.config_data = {
                "NetworkRole": "coordinator",
                "Outsource": str(root / "Outsource"),
                "NetworkRerunHandoffRoot": str(handoff_root),
            }
            facade._network_lifecycle_state_commit("coordinator", {"role": "coordinator", "status": "running"})
            request = {"csv_path": str(csv_path), "confirm_replace_final": True}
            dry_run = facade.dry_run_network_rerun_csv_start(resolved, request).to_mapping()

            def failing_journal(_payload: dict[str, object], _request: dict[str, object] | None) -> None:
                raise RuntimeError("journal unavailable")

            result = facade.start_network_rerun_csv_batch(
                resolved,
                {**request, "dry_run_fingerprint": dry_run["data"]["dry_run_fingerprint"], "confirm_start": True},
                journal_recorder=failing_journal,
            ).to_mapping()
            state_path = Path(result["data"]["state_file"]["path"])

        self.assertFalse(result["ok"])
        self.assertIn("command_journal_write_failed", result["errors"][0])
        self.assertIn("state_cleanup_ok", result["data"]["cleanup_result"])
        self.assertFalse(state_path.exists())
        self.assertFalse(result["data"]["writes_network_state"])

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

    def test_launch_preflight_is_read_only_and_matches_launch_guards(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            csv_path = root / "rerun.csv"
            movie = _media_file(root, "Movie")
            csv_path.write_text(f"enabled,source_path\ntrue,{movie}\n", encoding="utf-8")
            (root / "Outsource").mkdir()
            service = DummyWorkflowFacadeService(root)
            facade = MediaPipelineApplicationFacade(service, app_version="v5-test")
            resolved = _resolved(root)
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

    def test_run_once_preflight_blocks_only_authoritative_fresh_empty_normal_queue(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            service = DummyWorkflowFacadeService(root)
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
            }
            snapshot_path = root / "State" / "Progress" / "queue_snapshot.json"
            snapshot_path.parent.mkdir(parents=True)
            resolved.queue_snapshot_path = snapshot_path

            def write_snapshot(*, runnable_count: int, config_path: Path | None = None) -> None:
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
                snapshot_path.write_text(
                    json.dumps(
                        {
                            "schema_version": "queue_plan_snapshot.v1",
                            "produced_at": _fresh_generated_at(),
                            "config_path": str(config_path or resolved.config_path),
                            "local_base": str(resolved.local_base),
                            "source_movies": str(resolved.source_movies),
                            "source_tv": str(resolved.source_tv),
                            "outsource": str(root / "Outsource"),
                            "movie_count_total": runnable_count,
                            "tv_count_total": 0,
                            "priority_count": 0,
                            "runnable_count": runnable_count,
                            "rows": rows,
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

            os.utime(snapshot_path, (time.time() - 61, time.time() - 61))
            stale_empty = facade.get_launch_preflight(resolved, {"target": "pipeline", "mode": "once"})

            write_snapshot(runnable_count=0, config_path=root / "other.psd1")
            mismatched_empty = facade.get_launch_preflight(resolved, {"target": "pipeline", "mode": "once"})

            write_snapshot(runnable_count=1)
            fresh_ready = facade.get_launch_preflight(resolved, {"target": "pipeline", "mode": "once"})
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

        self.assertEqual(queue_scope(fresh_empty)["status"], "blocked")
        self.assertIn("no_runnable_work", queue_scope(fresh_empty)["detail"])
        self.assertFalse(fresh_empty["can_request_start"])
        self.assertEqual(queue_scope(stale_empty)["status"], "review")
        self.assertTrue(stale_empty["can_request_start"])
        self.assertEqual(queue_scope(mismatched_empty)["status"], "review")
        self.assertTrue(mismatched_empty["can_request_start"])
        self.assertEqual(queue_scope(fresh_ready)["status"], "ready")
        self.assertTrue(fresh_ready["can_request_start"])
        self.assertEqual(queue_scope(scanning)["status"], "review")
        self.assertIn("queue_scan_running", queue_scope(scanning)["detail"])
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
            service = DummyWorkflowFacadeService(root)
            facade = MediaPipelineApplicationFacade(service, app_version="v5-test")
            resolved = _resolved(root)
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
            service = DummyWorkflowFacadeService(root)
            facade = MediaPipelineApplicationFacade(service, app_version="v5-test")
            resolved = _resolved(root)
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
            service = DummyWorkflowFacadeService(root)
            facade = MediaPipelineApplicationFacade(service, app_version="v5-test")
            resolved = _resolved(root)
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
            service = DummyWorkflowFacadeService(root)
            facade = MediaPipelineApplicationFacade(service, app_version="v5-test")
            resolved = _resolved(root)

            with patch.object(facade, "_launch_path_health_for_resolved", return_value=health) as path_health:
                result = facade.start_pipeline_process(resolved, {"mode": "validate"}).to_mapping()

        self.assertTrue(result["ok"])
        path_health.assert_called_once_with(resolved)

    def test_launch_preflight_surfaces_missing_encoder_capability_report_without_blocking_start(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            service = DummyWorkflowFacadeService(root)
            facade = MediaPipelineApplicationFacade(service, app_version="v5-test")
            resolved = _resolved(root)
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
            service = DummyWorkflowFacadeService(root)
            facade = MediaPipelineApplicationFacade(service, app_version="v5-test")
            resolved = _resolved(root)
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
            service = DummyWorkflowFacadeService(root)
            facade = MediaPipelineApplicationFacade(service, app_version="v5-test")
            resolved = _resolved(root)
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
            service = DummyWorkflowFacadeService(root)
            facade = MediaPipelineApplicationFacade(service, app_version="v5-test")
            resolved = _resolved(root)
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
            service = DummyWorkflowFacadeService(root)
            facade = MediaPipelineApplicationFacade(service, app_version="v5-test")
            resolved = _resolved(root)
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
            service = DummyWorkflowFacadeService(root)
            facade = MediaPipelineApplicationFacade(service, app_version="v5-test")
            resolved = _resolved(root)
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
            service = DummyWorkflowFacadeService(root)
            facade = MediaPipelineApplicationFacade(service, app_version="v5-test")
            resolved = _resolved(root)
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
            service = DummyWorkflowFacadeService(root)
            facade = MediaPipelineApplicationFacade(service, app_version="v5-test")
            resolved = _resolved(root)
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
