"""Regression tests for the 2026-06-13 Network Worker/Coordinator review fixes.

Covers the integration seams the older suite stubbed over:

* D1 - the desktop facade actually exposes the four lifecycle providers.
* D2 - the coordinator re-scans the source queue instead of draining only the
       start-time snapshot.
* D3 - claim metadata reads the real ``QueueRecord`` fields (``is_priority`` /
       ``size_gb``) with back-compat fallback to the legacy names.
* D4 - the lifecycle worker-URL precondition requires a port (parity with the
       dispatcher-level ``validate_coordinator_url``).
* D5 - a stop whose provider ran but whose journal write failed commits the
       stopped state instead of leaving a phantom ``running``.
"""
from __future__ import annotations

import json
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from types import SimpleNamespace

from mediapipeline.tools.paths import find_repo_root
from unittest.mock import patch

sys.path.insert(0, str(find_repo_root(Path(__file__)) / "src"))

from mediapipeline.desktop.application import MediaPipelineApplicationFacade
from mediapipeline.desktop.application.network_lifecycle_provider import _NetworkRuntimeApp
from mediapipeline.desktop.network.coordinator_url import validate_coordinator_url
from mediapipeline.desktop.network.coordinator_queue import (
    _coerce_record_estimated_size_gb,
    _coerce_record_priority,
)
from mediapipeline.desktop.network.worker import WorkerDispatcher
from tests.python.desktop.application_facade_test_support import DummyWorkflowFacadeService, _resolved


class _FakeCoordinatorDispatcher:
    """Minimal stand-in so the real provider wiring runs without binding HTTP."""

    def __init__(self, app: object) -> None:
        self.app = app
        self.shutdown_called = False

    def shutdown(self) -> None:
        self.shutdown_called = True


class QueueRecordFieldCoercionTests(unittest.TestCase):
    def test_priority_prefers_real_model_field_with_legacy_fallback(self) -> None:
        # Real QueueRecord field name.
        self.assertTrue(_coerce_record_priority(SimpleNamespace(is_priority=True)))
        self.assertFalse(_coerce_record_priority(SimpleNamespace(is_priority=False)))
        # Legacy/synthetic field name still honoured when is_priority is absent.
        self.assertTrue(_coerce_record_priority(SimpleNamespace(priority=True)))
        # Real field wins when both are present.
        self.assertTrue(
            _coerce_record_priority(SimpleNamespace(is_priority=True, priority=False))
        )
        # No attribute at all -> not priority.
        self.assertFalse(_coerce_record_priority(SimpleNamespace()))

    def test_size_prefers_real_model_field_with_legacy_fallback(self) -> None:
        # Real QueueRecord field name.
        self.assertEqual(
            _coerce_record_estimated_size_gb(SimpleNamespace(size_gb=2.5), "x"), 2.5
        )
        # Legacy/synthetic field name still honoured when size_gb is absent.
        self.assertEqual(
            _coerce_record_estimated_size_gb(SimpleNamespace(estimated_size_gb=1.5), "x"),
            1.5,
        )
        # Real field wins when both are present.
        self.assertEqual(
            _coerce_record_estimated_size_gb(
                SimpleNamespace(size_gb=3.0, estimated_size_gb=9.0), "x"
            ),
            3.0,
        )
        # Non-finite/garbage coerces to 0.0 rather than raising.
        self.assertEqual(
            _coerce_record_estimated_size_gb(SimpleNamespace(size_gb="nope"), "x"), 0.0
        )
        self.assertEqual(_coerce_record_estimated_size_gb(SimpleNamespace(), "x"), 0.0)


class LifecycleProviderPresenceTests(unittest.TestCase):
    def test_facade_exposes_all_four_lifecycle_providers(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            facade = MediaPipelineApplicationFacade(
                DummyWorkflowFacadeService(Path(raw_root)), app_version="v5-test"
            )
        for name in (
            "start_network_coordinator",
            "stop_network_coordinator",
            "start_network_worker",
            "stop_network_worker",
        ):
            self.assertTrue(callable(getattr(facade, name, None)), name)

    def test_worker_provider_attaches_runtime_before_polling_starts(self) -> None:
        class RaceCheckingWorkerDispatcher:
            instances: list["RaceCheckingWorkerDispatcher"] = []

            def __init__(self, app: object, *, start_polling: bool = True) -> None:
                self.app = app
                self.start_polling_requested = start_polling
                self.status_callback_attached = False
                self.polling_started = False
                RaceCheckingWorkerDispatcher.instances.append(self)
                if start_polling:
                    self.start_polling()

            def set_status_callback(self, _callback: object) -> None:
                self.status_callback_attached = True

            def start_polling(self) -> None:
                facade = self.app.facade
                runtime = facade._network_dispatcher_runtime
                self.polling_started = True
                self.runtime_attached_when_polling_started = (
                    self.app.dispatcher is self
                    and runtime.get("worker", {}).get("app") is self.app
                    and runtime.get("worker", {}).get("dispatcher") is self
                )

            def shutdown(self, **_kwargs: object) -> None:
                return None

        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            service = DummyWorkflowFacadeService(root)
            facade = MediaPipelineApplicationFacade(service, app_version="v5-test")
            resolved = _resolved(root)
            resolved.config_data = {
                "NetworkRole": "worker",
                "WorkerCoordinatorUrl": "http://coordinator.test:7830",
                "WorkerAuthToken": "worker-token",
            }

            with patch(
                "mediapipeline.desktop.application.network_lifecycle_provider.WorkerDispatcher",
                RaceCheckingWorkerDispatcher,
            ):
                started = facade.request_network_lifecycle(
                    resolved,
                    role="worker",
                    action="start",
                    dry_run=False,
                    request={"confirm_start": True},
                    journal_recorder=lambda _payload, _request: None,
                ).to_mapping()

        self.assertTrue(started["ok"])
        dispatcher = RaceCheckingWorkerDispatcher.instances[0]
        self.assertFalse(dispatcher.start_polling_requested)
        self.assertTrue(dispatcher.status_callback_attached)
        self.assertTrue(dispatcher.polling_started)
        self.assertTrue(dispatcher.runtime_attached_when_polling_started)


class WorkerUrlPreconditionParityTests(unittest.TestCase):
    def test_missing_port_blocks_in_precondition_like_the_dispatcher(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            facade = MediaPipelineApplicationFacade(
                DummyWorkflowFacadeService(root), app_version="v5-test"
            )
            resolved = _resolved(root)
            resolved.config_data = {
                "NetworkRole": "worker",
                "WorkerCoordinatorUrl": "http://coordinator.test",
                "WorkerAuthToken": "worker-token",
            }
            dry_run = facade.request_network_lifecycle(
                resolved, role="worker", action="start", dry_run=True, request={}
            ).to_mapping()
        preconditions = {row["key"]: row for row in dry_run["data"]["precondition_results"]}
        self.assertEqual(preconditions["coordinator_url_present"]["status"], "blocked")
        self.assertIn(
            "must include the coordinator TCP port",
            preconditions["coordinator_url_present"]["evidence"],
        )

    def test_worker_url_precondition_matches_runtime_validator(self) -> None:
        cases = [
            ("http://coordinator.test:7830", True),
            ("http://192.168.1.10:7830", True),
            ("http://0.0.0.0:7830", False),
            ("file:///tmp/coordinator", False),
            ("coordinator.test:7830", False),
            ("http://coordinator.test", False),
            ("http://coordinator.test:7830/path", False),
            ("http://coordinator.test:7830?token=secret", False),
            ("http://coordinator.test:7830#secret", False),
            ("http://user:pass@coordinator.test:7830", False),
        ]
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            facade = MediaPipelineApplicationFacade(
                DummyWorkflowFacadeService(root), app_version="v5-test"
            )
            for url, should_pass in cases:
                with self.subTest(url=url):
                    resolved = _resolved(root)
                    resolved.config_data = {
                        "NetworkRole": "worker",
                        "WorkerCoordinatorUrl": url,
                        "WorkerAuthToken": "worker-token",
                    }
                    dry_run = facade.request_network_lifecycle(
                        resolved, role="worker", action="start", dry_run=True, request={}
                    ).to_mapping()
                    preconditions = {row["key"]: row for row in dry_run["data"]["precondition_results"]}
                    status = preconditions["coordinator_url_present"]["status"]
                    try:
                        validate_coordinator_url(url)
                        runtime_accepts = True
                    except ValueError:
                        runtime_accepts = False
                    self.assertEqual(runtime_accepts, should_pass)
                    self.assertEqual(status == "pass", should_pass)
                    self.assertNotIn("secret", preconditions["coordinator_url_present"]["evidence"])

    def test_provider_unavailable_precondition_instructs_restart(self) -> None:
        class FacadeWithoutProviders(MediaPipelineApplicationFacade):
            start_network_coordinator = None

        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            facade = FacadeWithoutProviders(
                DummyWorkflowFacadeService(root), app_version="v5-test"
            )
            resolved = _resolved(root)
            resolved.config_data = {
                "NetworkRole": "coordinator",
                "CoordinatorPort": 7830,
                "CoordinatorBindAddress": "127.0.0.1",
                "CoordinatorHeartbeatTimeoutMins": 5,
            }
            dry_run = facade.request_network_lifecycle(
                resolved, role="coordinator", action="start", dry_run=True, request={}
            ).to_mapping()
        preconditions = {row["key"]: row for row in dry_run["data"]["precondition_results"]}
        self.assertEqual(preconditions["lifecycle_provider_available"]["status"], "blocked")
        self.assertIn("Restart the app/API", preconditions["lifecycle_provider_available"]["action"])


class CoordinatorQueueRefreshTests(unittest.TestCase):
    def test_running_coordinator_picks_up_newly_added_queue_records(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            service = DummyWorkflowFacadeService(root)
            preview = {
                "records": [SimpleNamespace(source_path=root / "first.mkv", is_priority=False, size_gb=1.0)]
            }
            service.build_queue_preview = (  # type: ignore[attr-defined]
                lambda _resolved, force_refresh=False: list(preview["records"])
            )
            facade = MediaPipelineApplicationFacade(service, app_version="v5-test")
            resolved = _resolved(root)
            resolved.config_data = {
                "NetworkRole": "coordinator",
                "CoordinatorPort": 7830,
                "CoordinatorBindAddress": "127.0.0.1",
                "CoordinatorHeartbeatTimeoutMins": 5,
            }
            try:
                with patch(
                    "mediapipeline.desktop.application.network_lifecycle_provider.CoordinatorDispatcher",
                    _FakeCoordinatorDispatcher,
                ):
                    started = facade.request_network_lifecycle(
                        resolved,
                        role="coordinator",
                        action="start",
                        dry_run=False,
                        request={"confirm_start": True},
                        journal_recorder=lambda _payload, _request: None,
                    ).to_mapping()
                    self.assertTrue(started["ok"])
                    entry = facade._network_dispatcher_runtime["coordinator"]
                    app = entry["app"]
                    # Start-time snapshot.
                    self.assertEqual(
                        [str(r.source_path) for r in app.queue_records],
                        [str(root / "first.mkv")],
                    )
                    # A refresh thread is wired so new media is distributed.
                    self.assertIn("queue_refresh_thread", entry)
                    self.assertIn("queue_refresh_stop", entry)
                    # New media appears, then a refresh tick publishes it.
                    preview["records"].append(
                        SimpleNamespace(source_path=root / "second.mkv", is_priority=True, size_gb=2.0)
                    )
                    self.assertTrue(facade._refresh_coordinator_queue_records(entry, resolved))
                    self.assertEqual(
                        [str(r.source_path) for r in app.queue_records],
                        [str(root / "first.mkv"), str(root / "second.mkv")],
                    )
                    stopped = facade.request_network_lifecycle(
                        resolved,
                        role="coordinator",
                        action="stop",
                        dry_run=False,
                        request={"confirm_stop": True},
                        journal_recorder=lambda _payload, _request: None,
                    ).to_mapping()
                    self.assertTrue(stopped["ok"])
                    self.assertNotIn("coordinator", facade._network_dispatcher_runtime)
            finally:
                facade.stop_network_coordinator(resolved=resolved, request={}, command_id="cleanup")


class RunningWorkerSettingsHotApplyTests(unittest.TestCase):
    def test_worker_dispatcher_hot_apply_methods_update_runtime_descriptor_and_wake_poll(self) -> None:
        worker = WorkerDispatcher.__new__(WorkerDispatcher)
        worker._base_url = "http://old-coordinator.test:7830"
        worker._auth_token = "old-token"
        worker._source_path_map = []
        worker._active_job_lock = threading.Lock()
        worker._wakeup = threading.Event()

        path_map = json.dumps({r"C:\Media": r"\\SERVER\Media"})
        worker.update_source_path_map(path_map)
        worker.update_auth_token("new-token")
        worker.update_coordinator_url("http://new-coordinator.test:7830")

        descriptor = worker.runtime_descriptor()
        self.assertEqual(descriptor["coordinator_url"], "http://new-coordinator.test:7830")
        self.assertEqual(descriptor["path_map_entries"], 1)
        self.assertEqual(worker._apply_path_map(r"C:\Media\Movie.mkv"), r"\\SERVER\Media\Movie.mkv")
        self.assertTrue(worker._wakeup.is_set())
        self.assertNotIn("new-token", json.dumps(descriptor))

    def test_settings_save_patch_hot_applies_running_worker_settings(self) -> None:
        class Dispatcher:
            def __init__(self) -> None:
                self.urls: list[str] = []
                self.tokens: list[str] = []
                self.path_maps: list[str] = []

            def update_coordinator_url(self, value: str) -> None:
                self.urls.append(value)

            def update_auth_token(self, value: str) -> None:
                self.tokens.append(value)

            def update_source_path_map(self, value: str) -> None:
                self.path_maps.append(value)

        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            config_path = root / "config.psd1"
            config_path.write_text("@{ NetworkRole = 'worker' }\n", encoding="utf-8")
            service = DummyWorkflowFacadeService(root)
            facade = MediaPipelineApplicationFacade(service, app_version="v5-test")
            resolved = _resolved(root)
            resolved.config_path = config_path
            resolved.config_data = {
                "NetworkRole": "worker",
                "WorkerCoordinatorUrl": "http://old-coordinator.test:7830",
                "WorkerAuthToken": "old-token",
                "WorkerSourcePathMap": "",
            }
            running_resolved = _resolved(root)
            running_resolved.config_data = dict(resolved.config_data)
            dispatcher = Dispatcher()
            facade._network_dispatcher_runtime = {
                "worker": {
                    "app": SimpleNamespace(resolved=running_resolved),
                    "dispatcher": dispatcher,
                }
            }
            path_map = json.dumps({r"C:\Media": r"\\SERVER\Media"})
            request = {
                "changes": {
                    "WorkerCoordinatorUrl": "http://new-coordinator.test:7830",
                    "WorkerAuthToken": "new-token",
                    "WorkerSourcePathMap": path_map,
                },
            }

            result = facade.save_settings_patch(
                resolved,
                {**facade.settings_patch_request_with_review_confirmation(resolved, request), "confirm_save": True},
            )

        self.assertTrue(result.ok)
        self.assertEqual(dispatcher.urls, ["http://new-coordinator.test:7830"])
        self.assertEqual(dispatcher.tokens, ["new-token"])
        self.assertEqual(dispatcher.path_maps, [path_map])
        hot_apply = result.data["network_worker_hot_apply"]
        self.assertEqual(
            [(item["key"], item["status"]) for item in hot_apply],
            [
                ("WorkerCoordinatorUrl", "applied"),
                ("WorkerAuthToken", "applied"),
                ("WorkerSourcePathMap", "applied"),
            ],
        )
        self.assertEqual(running_resolved.config_data["WorkerCoordinatorUrl"], "http://new-coordinator.test:7830")
        self.assertNotIn("new-token", json.dumps(hot_apply))


class StopJournalFailureCommitsStoppedTests(unittest.TestCase):
    def test_worker_process_watcher_start_failure_aborts_and_reports_failed_done(self) -> None:
        class BadWatcherThread:
            def __init__(self, *_args, **_kwargs) -> None:
                return None

            def start(self) -> None:
                raise RuntimeError("thread denied")

        class Dispatcher:
            def __init__(self) -> None:
                self.done_reports: list[dict[str, object]] = []

            def mark_done(self, job: object, **kwargs: object) -> None:
                self.done_reports.append({"job_id": getattr(job, "job_id", ""), **kwargs})

            def release(self, _job: object) -> None:
                raise AssertionError("watcher failure must not clean-release a launched process")

        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            service = DummyWorkflowFacadeService(root)
            killed: list[tuple[object, str]] = []
            service.kill_process_tree = lambda proc, reason: killed.append((proc, reason))  # type: ignore[attr-defined]
            facade = MediaPipelineApplicationFacade(service, app_version="v5-test")
            app = _NetworkRuntimeApp(facade, _resolved(root), role="worker")
            dispatcher = Dispatcher()
            job = SimpleNamespace(job_id="job-1", record=SimpleNamespace(source_path=r"C:\Media\movie.mkv"))
            proc = SimpleNamespace()

            with (
                patch("mediapipeline.desktop.application.network_lifecycle_provider.threading.Thread", BadWatcherThread),
                self.assertLogs("mediapipeline.desktop.application.network_lifecycle_provider", level="ERROR") as logs,
            ):
                app._watch_claimed_process(dispatcher, job, proc)

        self.assertEqual(killed, [(proc, "network worker process watcher failed to start")])
        self.assertEqual(len(dispatcher.done_reports), 1)
        self.assertFalse(dispatcher.done_reports[0]["success"])
        self.assertEqual(dispatcher.done_reports[0]["completion_status"], "failed")
        self.assertIsNone(app._active_job)
        self.assertIsNone(app._active_proc)
        self.assertIn("Network worker process watcher failed for job job-1", "\n".join(logs.output))

    def test_worker_stop_does_not_release_claim_when_process_still_running(self) -> None:
        class Proc:
            def __init__(self) -> None:
                self.terminated = False

            def poll(self) -> None:
                return None

            def terminate(self) -> None:
                self.terminated = True

        class Dispatcher:
            def __init__(self) -> None:
                self.shutdown_calls: list[dict[str, bool]] = []

            def shutdown(self, *, release_active_job: bool = True, preserve_active_job: bool = False) -> None:
                self.shutdown_calls.append(
                    {
                        "release_active_job": release_active_job,
                        "preserve_active_job": preserve_active_job,
                    }
                )

        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            service = DummyWorkflowFacadeService(root)
            killed: list[tuple[object, str]] = []
            service.kill_process_tree = lambda proc, reason: killed.append((proc, reason))  # type: ignore[attr-defined]
            facade = MediaPipelineApplicationFacade(service, app_version="v5-test")
            resolved = _resolved(root)
            app = _NetworkRuntimeApp(facade, resolved, role="worker")
            app._active_job = SimpleNamespace(job_id="job-1")
            proc = Proc()
            app._active_proc = proc
            dispatcher = Dispatcher()
            facade._network_dispatcher_runtime = {
                "worker": {"app": app, "dispatcher": dispatcher}
            }

            facade.stop_network_worker(resolved=resolved, request={}, command_id="cmd-1")

        self.assertEqual(
            dispatcher.shutdown_calls,
            [{"release_active_job": False, "preserve_active_job": True}],
        )
        self.assertEqual(killed, [])
        self.assertFalse(proc.terminated)
        self.assertIn("worker", facade._network_dispatcher_runtime)
        self.assertTrue(facade._network_dispatcher_runtime["worker"]["stop_requested"])

    def test_coordinator_stop_preserves_active_local_worker_process(self) -> None:
        class Proc:
            def __init__(self) -> None:
                self.terminated = False

            def poll(self) -> None:
                return None

            def terminate(self) -> None:
                self.terminated = True

        class Dispatcher:
            def __init__(self) -> None:
                self.shutdown_called = False
                self.begin_drain_called = False

            def shutdown(self) -> None:
                self.shutdown_called = True

            def begin_drain(self) -> None:
                self.begin_drain_called = True

        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            service = DummyWorkflowFacadeService(root)
            killed: list[tuple[object, str]] = []
            service.kill_process_tree = lambda proc, reason: killed.append((proc, reason))  # type: ignore[attr-defined]
            facade = MediaPipelineApplicationFacade(service, app_version="v5-test")
            resolved = _resolved(root)
            app = _NetworkRuntimeApp(facade, resolved, role="coordinator")
            app._active_job = SimpleNamespace(job_id="job-1")
            proc = Proc()
            app._active_proc = proc
            dispatcher = Dispatcher()
            stop_event = threading.Event()
            facade._network_dispatcher_runtime = {
                "coordinator": {
                    "app": app,
                    "dispatcher": dispatcher,
                    "local_worker_stop": stop_event,
                }
            }

            facade.stop_network_coordinator(resolved=resolved, request={}, command_id="cmd-1")

        self.assertTrue(stop_event.is_set())
        self.assertTrue(dispatcher.begin_drain_called)
        self.assertFalse(dispatcher.shutdown_called)
        self.assertEqual(killed, [])
        self.assertFalse(proc.terminated)
        self.assertIn("coordinator", facade._network_dispatcher_runtime)
        self.assertTrue(facade._network_dispatcher_runtime["coordinator"]["stop_requested"])

    def test_stop_dry_run_reports_active_in_memory_worker_job(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            service = DummyWorkflowFacadeService(root)
            facade = MediaPipelineApplicationFacade(service, app_version="v5-test")
            resolved = _resolved(root)
            resolved.config_data = {
                "NetworkRole": "worker",
                "WorkerCoordinatorUrl": "http://coordinator.test:7830",
                "WorkerAuthToken": "worker-token",
            }
            app = _NetworkRuntimeApp(facade, resolved, role="worker")
            app._active_job = SimpleNamespace(
                job_id="job-1",
                worker_id="worker-1",
                record=SimpleNamespace(source_path=root / "Movie.mkv"),
            )
            app._active_proc = SimpleNamespace(poll=lambda: None)
            facade._network_dispatcher_runtime = {"worker": {"app": app, "dispatcher": SimpleNamespace()}}

            dry_run = facade.request_network_lifecycle(
                resolved,
                role="worker",
                action="stop",
                dry_run=True,
                request={},
            ).to_mapping()

        self.assertTrue(dry_run["ok"])
        active_work = dry_run["data"]["active_work"]
        self.assertEqual(active_work["active_job_count"], 1)
        self.assertTrue(active_work["active_process_running"])
        self.assertEqual(active_work["active_jobs"][0]["job_id"], "job-1")
        preconditions = {row["key"]: row for row in dry_run["data"]["precondition_results"]}
        self.assertEqual(preconditions["active_network_work"]["status"], "review")
        self.assertIn("ordinary stop preserves active process", preconditions["active_network_work"]["evidence"])

    def test_stop_dry_run_reports_active_coordinator_local_worker_job(self) -> None:
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
                "CoordinatorAlsoEncodeLocally": True,
            }
            app = _NetworkRuntimeApp(facade, resolved, role="coordinator")
            app._active_job = SimpleNamespace(
                job_id="job-local",
                worker_id="coordinator",
                record=SimpleNamespace(source_path=root / "Local.mkv"),
            )
            facade._network_dispatcher_runtime = {
                "coordinator": {"app": app, "dispatcher": SimpleNamespace()}
            }

            dry_run = facade.request_network_lifecycle(
                resolved,
                role="coordinator",
                action="stop",
                dry_run=True,
                request={},
            ).to_mapping()

        active_work = dry_run["data"]["active_work"]
        self.assertEqual(active_work["active_job_count"], 1)
        self.assertEqual(active_work["active_jobs"][0]["job_id"], "job-local")
        preconditions = {row["key"]: row for row in dry_run["data"]["precondition_results"]}
        self.assertEqual(preconditions["active_network_work"]["status"], "review")

    def test_start_dry_run_blocks_when_preserved_active_worker_job_exists(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            service = DummyWorkflowFacadeService(root)
            facade = MediaPipelineApplicationFacade(service, app_version="v5-test")
            resolved = _resolved(root)
            resolved.config_data = {
                "NetworkRole": "worker",
                "WorkerCoordinatorUrl": "http://coordinator.test:7830",
                "WorkerAuthToken": "worker-token",
            }
            app = _NetworkRuntimeApp(facade, resolved, role="worker")
            app._active_job = SimpleNamespace(
                job_id="job-1",
                worker_id="worker-1",
                record=SimpleNamespace(source_path=root / "Movie.mkv"),
            )
            facade._network_dispatcher_runtime = {"worker": {"app": app, "dispatcher": SimpleNamespace()}}

            dry_run = facade.request_network_lifecycle(
                resolved,
                role="worker",
                action="start",
                dry_run=True,
                request={},
            ).to_mapping()

        self.assertTrue(dry_run["ok"])
        self.assertFalse(dry_run["data"]["safe_to_apply"])
        preconditions = {row["key"]: row for row in dry_run["data"]["precondition_results"]}
        self.assertEqual(preconditions["active_network_work"]["status"], "blocked")

    def test_confirmed_worker_stop_reports_active_work_preserved_instead_of_stopped(self) -> None:
        class Dispatcher:
            def __init__(self) -> None:
                self.shutdown_calls: list[dict[str, bool]] = []

            def shutdown(self, *, release_active_job: bool = True, preserve_active_job: bool = False) -> None:
                self.shutdown_calls.append(
                    {
                        "release_active_job": release_active_job,
                        "preserve_active_job": preserve_active_job,
                    }
                )

        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            service = DummyWorkflowFacadeService(root)
            facade = MediaPipelineApplicationFacade(service, app_version="v5-test")
            resolved = _resolved(root)
            resolved.config_data = {
                "NetworkRole": "worker",
                "WorkerCoordinatorUrl": "http://coordinator.test:7830",
                "WorkerAuthToken": "worker-token",
            }
            app = _NetworkRuntimeApp(facade, resolved, role="worker")
            app._active_job = SimpleNamespace(
                job_id="job-1",
                worker_id="worker-1",
                record=SimpleNamespace(source_path=root / "Movie.mkv"),
            )
            app._active_proc = SimpleNamespace(poll=lambda: None)
            dispatcher = Dispatcher()
            facade._network_dispatcher_runtime = {"worker": {"app": app, "dispatcher": dispatcher}}
            journal: list[dict[str, object]] = []

            result = facade.request_network_lifecycle(
                resolved,
                role="worker",
                action="stop",
                dry_run=False,
                request={"confirm_stop": True},
                journal_recorder=lambda payload, _request: journal.append(payload),
            ).to_mapping()

        self.assertTrue(result["ok"])
        self.assertEqual(result["severity"], "warning")
        self.assertIn("active work is preserved", result["message"])
        self.assertEqual(result["data"]["state_after"]["status"], "active_work_preserved")
        self.assertTrue(result["data"]["active_work_preserved"])
        self.assertEqual(result["data"]["post_action_active_work"]["active_job_count"], 1)
        self.assertEqual(result["data"]["state_after"]["active_work"]["active_jobs"][0]["job_id"], "job-1")
        self.assertEqual(facade._network_lifecycle_state_for("worker")["status"], "active_work_preserved")
        self.assertEqual(
            dispatcher.shutdown_calls,
            [{"release_active_job": False, "preserve_active_job": True}],
        )
        self.assertTrue(journal)

    def test_stop_when_already_stopped_is_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            service = DummyWorkflowFacadeService(root)
            service.stop_network_worker = lambda **kwargs: None  # type: ignore[attr-defined]
            facade = MediaPipelineApplicationFacade(service, app_version="v5-test")
            resolved = _resolved(root)
            resolved.config_data = {
                "NetworkRole": "worker",
                "WorkerCoordinatorUrl": "http://coordinator.test:7830",
                "WorkerAuthToken": "worker-token",
            }
            result = facade.request_network_lifecycle(
                resolved,
                role="worker",
                action="stop",
                dry_run=False,
                request={"confirm_stop": True},
                journal_recorder=lambda _payload, _request: None,
            ).to_mapping()

        self.assertTrue(result["ok"])
        self.assertEqual(result["data"]["state_after"]["status"], "stopped")
        preconditions = {row["key"]: row for row in result["data"]["precondition_results"]}
        self.assertEqual(preconditions["duplicate_stop_guard"]["status"], "pass")

    def test_stop_journal_failure_commits_stopped_state(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            service = DummyWorkflowFacadeService(root)
            service.start_network_coordinator = lambda **kwargs: None  # type: ignore[attr-defined]
            service.stop_network_coordinator = lambda **kwargs: None  # type: ignore[attr-defined]
            facade = MediaPipelineApplicationFacade(service, app_version="v5-test")
            resolved = _resolved(root)
            resolved.config_data = {
                "NetworkRole": "coordinator",
                "CoordinatorPort": 7830,
                "CoordinatorBindAddress": "127.0.0.1",
                "CoordinatorHeartbeatTimeoutMins": 5,
            }
            good_journal: list[object] = []
            facade.request_network_lifecycle(
                resolved,
                role="coordinator",
                action="start",
                dry_run=False,
                request={"confirm_start": True},
                journal_recorder=lambda payload, _request: good_journal.append(payload),
            )
            self.assertEqual(facade._network_lifecycle_state_for("coordinator")["status"], "running")

            def failing_journal(_payload: dict, _request: dict | None) -> None:
                raise RuntimeError("journal path unavailable")

            stop_result = facade.request_network_lifecycle(
                resolved,
                role="coordinator",
                action="stop",
                dry_run=False,
                request={"confirm_stop": True},
                journal_recorder=failing_journal,
            ).to_mapping()

        self.assertFalse(stop_result["ok"])
        self.assertEqual(
            stop_result["data"]["cleanup_result"],
            "command_journal_failed_stop_state_committed",
        )
        # The dispatcher was torn down, so the committed state must be stopped,
        # not a phantom running that would block a later start.
        self.assertEqual(facade._network_lifecycle_state_for("coordinator")["status"], "stopped")

    def test_coordinator_stop_dry_run_reports_remote_active_claims(self) -> None:
        class Dispatcher:
            def active_claims_snapshot(self) -> list[dict[str, object]]:
                return [
                    {
                        "job_id": "job-remote",
                        "worker_id": "worker-1",
                        "worker_name": "Worker 1",
                        "source_path": r"C:\Media\Remote.mkv",
                        "last_heartbeat": "2026-06-15T12:00:00+00:00",
                        "heartbeat_age_seconds": 9,
                    }
                ]

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
            facade._network_dispatcher_runtime = {
                "coordinator": {"app": _NetworkRuntimeApp(facade, resolved, role="coordinator"), "dispatcher": Dispatcher()}
            }

            dry_run = facade.request_network_lifecycle(
                resolved,
                role="coordinator",
                action="stop",
                dry_run=True,
                request={},
            ).to_mapping()

        active_work = dry_run["data"]["active_work"]
        self.assertEqual(active_work["local_active_job_count"], 0)
        self.assertEqual(active_work["remote_active_claim_count"], 1)
        self.assertEqual(active_work["active_job_count"], 1)
        self.assertEqual(active_work["remote_active_claims"][0]["job_id"], "job-remote")
        self.assertEqual(active_work["remote_active_claims"][0]["source"], "coordinator_registry")
        preconditions = {row["key"]: row for row in dry_run["data"]["precondition_results"]}
        self.assertEqual(preconditions["active_network_work"]["status"], "review")
        self.assertIn("remote_active_claims=1", preconditions["active_network_work"]["evidence"])

    def test_coordinator_start_dry_run_blocks_with_preserved_remote_claims(self) -> None:
        class Dispatcher:
            def active_claims_snapshot(self) -> list[dict[str, object]]:
                return [{"job_id": "job-remote", "worker_id": "worker-1", "source_path": r"C:\Media\Remote.mkv"}]

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
            facade._network_dispatcher_runtime = {
                "coordinator": {"app": _NetworkRuntimeApp(facade, resolved, role="coordinator"), "dispatcher": Dispatcher()}
            }

            dry_run = facade.request_network_lifecycle(
                resolved,
                role="coordinator",
                action="start",
                dry_run=True,
                request={},
            ).to_mapping()

        self.assertFalse(dry_run["data"]["safe_to_apply"])
        preconditions = {row["key"]: row for row in dry_run["data"]["precondition_results"]}
        self.assertEqual(preconditions["active_network_work"]["status"], "blocked")
        self.assertIn("remote_active_claims=1", preconditions["active_network_work"]["evidence"])

    def test_confirmed_coordinator_stop_with_remote_claim_enters_drain_without_http_shutdown(self) -> None:
        class Dispatcher:
            def __init__(self) -> None:
                self.claims = [{"job_id": "job-remote", "worker_id": "worker-1", "source_path": r"C:\Media\Remote.mkv"}]
                self.begin_drain_called = False
                self.shutdown_called = False

            def active_claims_snapshot(self) -> list[dict[str, object]]:
                return list(self.claims)

            def begin_drain(self) -> None:
                self.begin_drain_called = True

            def shutdown(self) -> None:
                self.shutdown_called = True

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
            dispatcher = Dispatcher()
            facade._network_dispatcher_runtime = {
                "coordinator": {"app": _NetworkRuntimeApp(facade, resolved, role="coordinator"), "dispatcher": dispatcher}
            }
            journal: list[dict[str, object]] = []

            result = facade.request_network_lifecycle(
                resolved,
                role="coordinator",
                action="stop",
                dry_run=False,
                request={"confirm_stop": True},
                journal_recorder=lambda payload, _request: journal.append(payload),
            ).to_mapping()
            drain_stop = facade._network_dispatcher_runtime["coordinator"].get("drain_monitor_stop")
            if isinstance(drain_stop, threading.Event):
                drain_stop.set()

        self.assertTrue(result["ok"])
        self.assertEqual(result["severity"], "warning")
        self.assertEqual(result["data"]["state_after"]["status"], "active_work_preserved")
        self.assertEqual(result["data"]["post_action_active_work"]["remote_active_claim_count"], 1)
        self.assertEqual(facade._network_lifecycle_state_for("coordinator")["status"], "active_work_preserved")
        self.assertTrue(journal)
        self.assertTrue(dispatcher.begin_drain_called)
        self.assertFalse(dispatcher.shutdown_called)
        self.assertIn("coordinator", facade._network_dispatcher_runtime)
        self.assertTrue(facade._network_dispatcher_runtime["coordinator"]["stop_requested"])

    def test_coordinator_drain_finalizes_shutdown_after_registry_idle(self) -> None:
        class Dispatcher:
            def __init__(self) -> None:
                self.claims = [{"job_id": "job-remote", "worker_id": "worker-1", "source_path": r"C:\Media\Remote.mkv"}]
                self.begin_drain_called = False
                self.shutdown_called = False

            def active_claims_snapshot(self) -> list[dict[str, object]]:
                return list(self.claims)

            def begin_drain(self) -> None:
                self.begin_drain_called = True

            def shutdown(self) -> None:
                self.shutdown_called = True

        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            service = DummyWorkflowFacadeService(root)
            facade = MediaPipelineApplicationFacade(service, app_version="v5-test")
            resolved = _resolved(root)
            dispatcher = Dispatcher()
            entry = {"app": _NetworkRuntimeApp(facade, resolved, role="coordinator"), "dispatcher": dispatcher}
            facade._network_dispatcher_runtime = {"coordinator": entry}

            facade.stop_network_coordinator(resolved=resolved, request={}, command_id="cmd-1")
            dispatcher.claims.clear()
            finalized = facade._finalize_coordinator_drain_if_idle(entry)

        self.assertTrue(finalized)
        self.assertTrue(dispatcher.begin_drain_called)
        self.assertTrue(dispatcher.shutdown_called)
        self.assertNotIn("coordinator", facade._network_dispatcher_runtime)

    def test_worker_start_polling_failure_cleans_runtime_entry(self) -> None:
        class FailingWorkerDispatcher:
            instances: list["FailingWorkerDispatcher"] = []

            def __init__(self, app: object, *, start_polling: bool = True) -> None:
                self.app = app
                self.shutdown_calls: list[dict[str, object]] = []
                FailingWorkerDispatcher.instances.append(self)

            def set_status_callback(self, _callback: object) -> None:
                return None

            def start_polling(self) -> None:
                raise RuntimeError("poll startup failed")

            def shutdown(self, **kwargs: object) -> None:
                self.shutdown_calls.append(dict(kwargs))

        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            service = DummyWorkflowFacadeService(root)
            facade = MediaPipelineApplicationFacade(service, app_version="v5-test")
            resolved = _resolved(root)
            resolved.config_data = {
                "NetworkRole": "worker",
                "WorkerCoordinatorUrl": "http://coordinator.test:7830",
                "WorkerAuthToken": "worker-token",
            }

            with patch(
                "mediapipeline.desktop.application.network_lifecycle_provider.WorkerDispatcher",
                FailingWorkerDispatcher,
            ):
                with self.assertRaisesRegex(RuntimeError, "poll startup failed"):
                    facade.start_network_worker(resolved=resolved, request={}, command_id="cmd-1")

        dispatcher = FailingWorkerDispatcher.instances[0]
        self.assertEqual(dispatcher.shutdown_calls, [{"release_active_job": False, "preserve_active_job": True}])
        self.assertNotIn("worker", facade._network_dispatcher_runtime)

    def test_coordinator_start_loop_failure_shuts_down_partial_dispatcher(self) -> None:
        class Dispatcher:
            instances: list["Dispatcher"] = []

            def __init__(self, app: object) -> None:
                self.app = app
                self.shutdown_called = False
                Dispatcher.instances.append(self)

            def shutdown(self) -> None:
                self.shutdown_called = True

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

            with (
                patch("mediapipeline.desktop.application.network_lifecycle_provider.CoordinatorDispatcher", Dispatcher),
                patch.object(
                    MediaPipelineApplicationFacade,
                    "_start_coordinator_queue_refresh_loop",
                    side_effect=RuntimeError("queue refresh loop failed"),
                ),
            ):
                with self.assertRaisesRegex(RuntimeError, "queue refresh loop failed"):
                    facade.start_network_coordinator(resolved=resolved, request={}, command_id="cmd-1")

        self.assertTrue(Dispatcher.instances[0].shutdown_called)
        self.assertNotIn("coordinator", facade._network_dispatcher_runtime)


if __name__ == "__main__":  # pragma: no cover - convenience runner
    unittest.main()
