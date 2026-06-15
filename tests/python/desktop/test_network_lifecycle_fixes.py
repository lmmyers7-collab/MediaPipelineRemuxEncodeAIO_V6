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
from tests.python.desktop.test_application_facade import DummyWorkflowFacadeService, _resolved


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

            result = facade.save_settings_patch(
                resolved,
                {
                    "changes": {
                        "WorkerCoordinatorUrl": "http://new-coordinator.test:7830",
                        "WorkerAuthToken": "new-token",
                        "WorkerSourcePathMap": path_map,
                    },
                    "confirm_save": True,
                },
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
    def test_worker_stop_does_not_release_claim_when_process_still_running(self) -> None:
        class Dispatcher:
            def __init__(self) -> None:
                self.release_flags: list[bool] = []

            def shutdown(self, *, release_active_job: bool = True) -> None:
                self.release_flags.append(release_active_job)

        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            service = DummyWorkflowFacadeService(root)
            service.kill_process_tree = lambda _proc, _reason: None  # type: ignore[attr-defined]
            facade = MediaPipelineApplicationFacade(service, app_version="v5-test")
            resolved = _resolved(root)
            app = _NetworkRuntimeApp(facade, resolved, role="worker")
            app._active_job = SimpleNamespace(job_id="job-1")
            app._active_proc = SimpleNamespace(poll=lambda: None)
            app.wait_for_active_process_exit = lambda timeout_seconds=10.0: False  # type: ignore[method-assign]
            dispatcher = Dispatcher()
            facade._network_dispatcher_runtime = {
                "worker": {"app": app, "dispatcher": dispatcher}
            }

            facade.stop_network_worker(resolved=resolved, request={}, command_id="cmd-1")

        self.assertEqual(dispatcher.release_flags, [False])

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


if __name__ == "__main__":  # pragma: no cover - convenience runner
    unittest.main()
