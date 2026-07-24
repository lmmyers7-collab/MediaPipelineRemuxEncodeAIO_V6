from __future__ import annotations

import json
import os
import tempfile
import threading
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from mediapipeline.desktop.application import MediaPipelineApplicationFacade
from mediapipeline.desktop.application.network_lifecycle_provider import (
    _NetworkRuntimeApp,
    _network_done_kwargs_from_result,
    _read_network_worker_result,
)
from tests.python.desktop.application_facade_test_support import (
    DummyProc,
    DummyWorkflowFacadeService,
    _resolved,
)


class ApplicationFacadeNetworkLifecycleTests(unittest.TestCase):
    @staticmethod
    def _write_csv_rerun_worker_result(root: Path) -> tuple[Path, SimpleNamespace, SimpleNamespace]:
        result_path = root / "NetworkWorkerResults" / "job-1" / "run-1.worker_result.json"
        result_path.parent.mkdir(parents=True)
        result_path.write_text(
            json.dumps(
                {
                    "SchemaVersion": "local_worker_result.v1",
                    "Success": True,
                    "Status": "processed",
                    "Reason": "",
                    "ErrorCode": "",
                    "WorkerRunId": "run-1",
                    "WorkerClaimId": "job-1",
                    "QueueTerminal": True,
                    "Retryable": False,
                    "ElapsedSeconds": 12,
                    "OutputSizeBytes": 456,
                    "OutputPath": str(root / "Handoff" / "Movie.mkv"),
                    "PublishState": "handoff_ready",
                    "PublishMode": "network_handoff",
                    "Route": "encode",
                },
                separators=(",", ":"),
            )
            + "\n",
            encoding="utf-8",
        )
        proc = SimpleNamespace(
            _network_worker_result_path=str(result_path),
            _network_worker_run_id="run-1",
            _network_worker_claim_id="job-1",
        )
        job = SimpleNamespace(
            job_id="job-1",
            claim_metadata={
                "job_kind": "csv_rerun_row",
                "rerun_batch_id": "batch-1",
                "rerun_row_key": "row-1",
                "rerun_row_index": 1,
                "planned_output_path": str(root / "Handoff" / "Movie.mkv"),
                "coordinator_source_path": str(root / "Coordinator" / "Movie.mkv"),
                "worker_source_path": str(root / "Worker" / "Movie.mkv"),
                "output_handoff": {"mode": "copy"},
                "source_identity": {"library_id": "movies", "relative_path": "Movie.mkv"},
                "handoff_probe": {"status": "ready"},
            },
        )
        return result_path, proc, job

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
        self.assertEqual(
            dispatcher.done[0]["worker_result_artifact"]["WorkerClaimId"],
            "job-1",
        )
        self.assertEqual(
            dispatcher.done[0]["worker_result_artifact"]["SchemaVersion"],
            "local_worker_result.v1",
        )
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

    def test_csv_rerun_result_partial_temp_write_preserves_success_and_original_bytes(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            result_path, proc, job = self._write_csv_rerun_worker_result(root)
            original_bytes = result_path.read_bytes()
            real_fdopen = os.fdopen

            class PartialWriter:
                def __init__(self, handle: object) -> None:
                    self.handle = handle

                def __enter__(self) -> PartialWriter:
                    return self

                def __exit__(self, *_args: object) -> None:
                    self.handle.close()  # type: ignore[attr-defined]

                def write(self, text: str) -> None:
                    self.handle.write(text[:1])  # type: ignore[attr-defined]
                    self.handle.flush()  # type: ignore[attr-defined]
                    raise OSError("injected partial enrichment write")

                def flush(self) -> None:
                    self.handle.flush()  # type: ignore[attr-defined]

                def fileno(self) -> int:
                    return int(self.handle.fileno())  # type: ignore[attr-defined]

            def partial_fdopen(fd: int, *args: object, **kwargs: object) -> PartialWriter:
                return PartialWriter(real_fdopen(fd, *args, **kwargs))

            with (
                patch("mediapipeline.desktop.network.worker_state.os.fdopen", partial_fdopen),
                self.assertLogs("mediapipeline.desktop.application.network_lifecycle_provider", level="WARNING"),
            ):
                done = _network_done_kwargs_from_result(proc, job, return_code=0, wait_error="", elapsed_seconds=12.0)

            preserved_bytes = result_path.read_bytes()
            leftovers = list(result_path.parent.glob(f".{result_path.name}.*.tmp"))

        self.assertEqual(preserved_bytes, original_bytes)
        self.assertTrue(done["success"])
        self.assertFalse(done["retry_on_failure"])
        self.assertEqual(done["completion_status"], "processed")
        self.assertEqual(done["worker_result_artifact"]["RerunBatchId"], "batch-1")
        enrichment = done["worker_result_artifact"]["CoordinatorMetadataPersistence"]
        self.assertEqual(enrichment["status"], "failed")
        self.assertTrue(enrichment["artifact_preserved"])
        self.assertIn("partial enrichment write", enrichment["error"])
        self.assertEqual(leftovers, [])

    def test_csv_rerun_result_replace_failure_preserves_original_and_reports_separately(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            result_path, proc, job = self._write_csv_rerun_worker_result(root)
            original_bytes = result_path.read_bytes()

            with patch(
                "mediapipeline.desktop.network.worker_state.os.replace",
                side_effect=OSError("injected atomic replace failure"),
            ):
                result, result_error, enrichment = _read_network_worker_result(proc, job)

            preserved_bytes = result_path.read_bytes()
            leftovers = list(result_path.parent.glob(f".{result_path.name}.*.tmp"))

        self.assertEqual(result_error, "")
        self.assertIsNotNone(result)
        self.assertEqual(result["RerunRowKey"], "row-1")  # type: ignore[index]
        self.assertEqual(enrichment["status"], "failed")
        self.assertTrue(enrichment["artifact_preserved"])
        self.assertIn("atomic replace failure", enrichment["error"])
        self.assertEqual(preserved_bytes, original_bytes)
        self.assertEqual(leftovers, [])

    def test_csv_rerun_result_restart_ignores_interrupted_enrichment_temp(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            result_path, proc, job = self._write_csv_rerun_worker_result(root)
            orphan = result_path.parent / f".{result_path.name}.interrupted.tmp"
            orphan.write_text("{", encoding="utf-8")

            result, result_error, enrichment = _read_network_worker_result(proc, job)
            persisted = json.loads(result_path.read_text(encoding="utf-8"))
            orphan_still_non_authoritative = orphan.read_text(encoding="utf-8")

        self.assertEqual(result_error, "")
        self.assertIsNotNone(result)
        self.assertTrue(result["Success"])  # type: ignore[index]
        self.assertEqual(result["RerunBatchId"], "batch-1")  # type: ignore[index]
        self.assertEqual(enrichment["status"], "persisted")
        self.assertEqual(persisted["RerunBatchId"], "batch-1")
        self.assertEqual(orphan_still_non_authoritative, "{")

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


if __name__ == "__main__":
    unittest.main()
