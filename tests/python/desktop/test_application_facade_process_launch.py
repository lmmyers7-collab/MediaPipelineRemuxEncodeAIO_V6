from __future__ import annotations

from datetime import datetime, timedelta
import json
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
from tests.python.desktop.test_application_facade import DummyProc, DummyWorkflowFacadeService, _resolved


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
            rerun_csv.write_text("enabled,source_path\ntrue,C:\\Media\\Movie.mkv\n", encoding="utf-8")
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
            instances: list["FakeCoordinatorDispatcher"] = []

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
            instances: list["FakeWorkerDispatcher"] = []

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

                class WorkerService(DummyWorkflowFacadeService):
                    def start_pipeline(self, *args: object, **kwargs: object) -> ProcWithWait:  # type: ignore[override]
                        super().start_pipeline(*args, **kwargs)  # type: ignore[arg-type]
                        extra_argv = [str(item) for item in (kwargs.get("extra_argv") or [])]
                        result_path = Path(extra_argv[extra_argv.index("-WorkerResultPath") + 1])
                        result_path.parent.mkdir(parents=True, exist_ok=True)
                        run_id = extra_argv[extra_argv.index("-WorkerRunId") + 1]
                        claim_id = extra_argv[extra_argv.index("-WorkerClaimId") + 1]
                        if isinstance(result_payload, str):
                            result_path.write_text(result_payload, encoding="utf-8")
                        elif isinstance(result_payload, dict):
                            payload = {
                                "SchemaVersion": "local_worker_result.v1",
                                "SourcePath": str(root / "Claimed.mkv"),
                                "SourceName": "Claimed.mkv",
                                "WorkerSlotId": 0,
                                "WorkerRunId": run_id,
                                "WorkerClaimId": claim_id,
                                "QueueTerminal": False,
                                "Retryable": True,
                                "OutputSizeBytes": 0,
                                **result_payload,
                            }
                            result_path.write_text(json.dumps(payload), encoding="utf-8")
                        return ProcWithWait()

                service = WorkerService(root)
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

            def active_job_messages(_resolved: object, *, job_kinds: set[str] | None = None) -> list[str]:
                if job_kinds is not None and "pipeline" not in job_kinds:
                    return []
                return [
                    "ActiveJobs record pipeline.json reports pipeline continuous as active and PID 25001 is still running."
                ]

            service.find_related_pipeline_processes = related_processes  # type: ignore[method-assign]
            service.active_job_close_block_messages = active_job_messages  # type: ignore[method-assign]
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

    def test_rerun_start_uses_existing_service_launch_path(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            csv_path = root / "rerun.csv"
            csv_path.write_text("enabled,source_path\ntrue,C:\\Media\\Movie.mkv\n", encoding="utf-8")
            service = DummyWorkflowFacadeService(root)
            facade = MediaPipelineApplicationFacade(service, app_version="v5-test")
            resolved = _resolved(root)

            result = facade.start_rerun_csv_process(resolved, {"csv_path": str(csv_path)}).to_mapping()
            rejected = facade.start_rerun_csv_process(
                resolved,
                {"csv_path": str(csv_path), "original_mode": "delete"},
            ).to_mapping()
            missing = facade.start_rerun_csv_process(resolved, {}).to_mapping()

        self.assertTrue(result["ok"])
        self.assertEqual(result["schema_version"], "desktop_command_result.v1")
        self.assertEqual(result["command"], "rerun.start")
        self.assertEqual(result["data"]["pid"], 24682)
        self.assertFalse(result["data"]["dry_run"])
        self.assertEqual(service.started_rerun["return_mode"], "park")
        self.assertFalse(rejected["ok"])
        self.assertIn("copy/keep/park", rejected["message"])
        self.assertFalse(missing["ok"])
        self.assertIn("csv_path", missing["message"])

    def test_process_launch_commands_share_backend_launch_lock(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            csv_path = root / "rerun.csv"
            csv_path.write_text("enabled,source_path\ntrue,C:\\Media\\Movie.mkv\n", encoding="utf-8")
            service = DummyWorkflowFacadeService(root)
            facade = MediaPipelineApplicationFacade(service, app_version="v5-test")
            resolved = _resolved(root)
            resolved.config_data = {"NetworkRole": "standalone", "Outsource": str(root / "Outsource")}

            self.assertTrue(facade._process_launch_lock.acquire(blocking=False))  # type: ignore[attr-defined]
            try:
                pipeline = facade.start_pipeline_process(resolved, {"mode": "validate"}).to_mapping()
                audit = facade.start_audit_process(resolved, {}).to_mapping()
                rerun = facade.start_rerun_csv_process(resolved, {"csv_path": str(csv_path)}).to_mapping()
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

    def test_pipeline_start_stop_requested_progress_still_uses_active_jobs_fallback(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            service = DummyWorkflowFacadeService(root)
            service.find_related_pipeline_processes = lambda _resolved_arg, *, job_kinds=None: []  # type: ignore[method-assign]
            service.active_job_close_block_messages = (  # type: ignore[method-assign]
                lambda _resolved_arg, *, job_kinds=None: [
                    "ActiveJobs record pipeline.json reports pipeline validate as active."
                ]
            )
            service.read_progress = lambda _resolved_arg: {"CurrentStage": "encode", "StopRequested": True}  # type: ignore[method-assign]
            service.is_progress_stale = lambda _progress: False  # type: ignore[method-assign]
            facade = MediaPipelineApplicationFacade(service, app_version="v5-test")
            resolved = _resolved(root)

            blocked = facade.start_pipeline_process(resolved, {"mode": "validate"}).to_mapping()

        self.assertFalse(blocked["ok"])
        self.assertEqual(blocked["severity"], "warning")
        self.assertIn("ActiveJobs still reports active work", blocked["message"])
        self.assertIn("pipeline validate", blocked["message"])
        self.assertFalse(hasattr(service, "started_pipeline"))

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
            csv_path.write_text("enabled,source_path\ntrue,C:\\Media\\Movie.mkv\n", encoding="utf-8")
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
            rerun = facade.get_launch_preflight(resolved, {"target": "rerun", "csv_path": str(csv_path)})
            blocked_rerun = facade.get_launch_preflight(
                resolved,
                {"target": "rerun", "csv_path": str(csv_path), "original_mode": "delete"},
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
        self.assertTrue(any(row["key"] == "runtime_prep_boundary" for row in pipeline["checks"]))
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
        self.assertEqual(rerun["target"], "rerun")
        self.assertEqual(rerun["start_route"], "/api/rerun/start")
        self.assertEqual(rerun["request"]["stage_mode"], "copy")
        self.assertEqual(blocked_rerun["status"], "blocked")
        self.assertTrue(any(row["key"] == "safe_modes" and row["status"] == "blocked" for row in blocked_rerun["checks"]))

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

        self.assertEqual(preflight["status"], "high review")
        self.assertTrue(preflight["can_request_start"])
        rows = {row["key"]: row for row in preflight["checks"]}
        self.assertEqual(rows["configured_path_health"]["status"], "high review")
        self.assertIn("not reachable", "\n".join(str(item) for item in rows["configured_path_health"]["detail"]))
        self.assertIn("Configured server/folder health", rows["configured_path_health"]["label"])

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
