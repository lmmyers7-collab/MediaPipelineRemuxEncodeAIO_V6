from __future__ import annotations

import contextlib
import csv
from datetime import datetime, timedelta
import io
import json
import logging
import os
import re
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path

from mediapipeline.tools.paths import find_repo_root
from urllib.parse import quote
from unittest.mock import patch

sys.path.insert(0, str(find_repo_root(Path(__file__)) / "src"))

from mediapipeline.desktop.api import LocalApiServer
from mediapipeline.core.api.commands_process import LocalApiProcessCommandPayloadMixin
from mediapipeline.desktop.api.handler import build_local_api_handler_class
from mediapipeline.desktop.application import MediaPipelineApplicationFacade
from mediapipeline.desktop.local_api_main import BOOTSTRAP_SCHEMA_VERSION, bootstrap_payload, build_backend, main as local_api_main
from mediapipeline.desktop.models import ResolvedPaths, Snapshot
from tests.python.desktop.application_facade_test_support import (
    COMMAND_HISTORY_ASSET_ORDER,
    DummyFacadeService,
    DummyProc,
    DummyWorkflowFacadeService,
    LocalApiHttpTestMixin,
    served_webview_static_contract_bundle,
    assert_namespace_export as _assert_namespace_export,
    _render_static_index_html,
    _resolved,
)


class LocalApiLifecycleTests(LocalApiHttpTestMixin, unittest.TestCase):
    def test_local_api_close_readiness_is_unsafe_when_workspace_is_unresolved(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            service = DummyFacadeService(root)
            facade = MediaPipelineApplicationFacade(service, app_version="v6-test")
            server = LocalApiServer(facade, token="test-token")
            try:
                server.start()
                status, payload = self._get_json(f"{server.url}/api/backend/close-readiness", token="test-token")
            finally:
                server.stop()

        self.assertEqual(status, 200)
        self.assertEqual(payload["schema_version"], "desktop_close_readiness.v1")
        self.assertFalse(payload["safe_to_close"])
        self.assertTrue(payload["active_work"])
        self.assertEqual(payload["state"], "unknown")
        self.assertIn("resolved paths are unavailable", payload["reason"])
        self.assertTrue(payload["warnings"])

    def test_local_api_shutdown_blocks_when_workspace_is_unresolved(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            service = DummyFacadeService(root)
            facade = MediaPipelineApplicationFacade(service, app_version="v6-test")
            shutdown_event = threading.Event()
            server = LocalApiServer(facade, token="test-token", shutdown_request=shutdown_event.set)
            try:
                server.start()
                status, payload = self._post_json(
                    f"{server.url}/api/backend/shutdown",
                    {"reason": "test"},
                    token="test-token",
                )
            finally:
                server.stop()

        self.assertEqual(status, 503)
        self.assertEqual(payload["schema_version"], "desktop_command_result.v1")
        self.assertEqual(payload["command"], "backend.shutdown")
        self.assertFalse(payload["ok"])
        self.assertEqual(payload["severity"], "error")
        self.assertEqual(payload["data"]["evidence_phase"], "rejected")
        self.assertEqual(payload["data"]["journal_durability"], "strict")
        self.assertFalse(shutdown_event.wait(0.2))

    def test_local_api_shutdown_ignores_active_jobs_when_close_readiness_is_safe(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            service = DummyWorkflowFacadeService(root)
            resolved = _resolved(root)
            idle_snapshot = Snapshot(
                resolved=resolved,
                current_activity="Ready.",
                status_summary="Idle",
                log_tail="",
                progress={"ProgressVersion": 2, "Status": "Completed", "CurrentStage": "completed"},
                audit_progress=None,
                latest_failure_report=None,
                latest_failure_json=None,
                latest_audit_csv=None,
                latest_priority_csv=None,
            )
            service.snapshot = idle_snapshot
            active_jobs = resolved.active_jobs_path
            active_jobs.mkdir(parents=True, exist_ok=True)
            (active_jobs / "launching.json").write_text(
                json.dumps(
                    {
                        "schema_version": "desktop_active_job.v1",
                        "launch_id": "launching",
                        "job_kind": "pipeline",
                        "mode": "continuous",
                        "status": "launching",
                        "pid": None,
                        "app_pid": 1234,
                        "command_line": "pwsh -File MediaPipeline.ps1",
                        "args": ["pwsh", "-File", "MediaPipeline.ps1"],
                        "cwd": str(root),
                        "stdout_log": "",
                        "stderr_log": "",
                        "show_console": False,
                        "metadata": {},
                        "launched_at": "2026-05-08T21:00:00-04:00",
                        "last_update": "2026-05-08T21:00:01-04:00",
                        "return_code": None,
                    }
                ),
                encoding="utf-8",
            )
            facade = MediaPipelineApplicationFacade(service, app_version="v6-test")
            shutdown_event = threading.Event()
            server = LocalApiServer(
                facade,
                token="test-token",
                resolved_provider=lambda: resolved,
                snapshot_provider=lambda: idle_snapshot,
                audit_root_provider=lambda: str(root),
                shutdown_request=shutdown_event.set,
            )
            try:
                server.start()
                readiness_status, readiness = self._get_json(f"{server.url}/api/backend/close-readiness", token="test-token")
                denied_status, denied = self._post_json(f"{server.url}/api/backend/shutdown", {"reason": "test"})
                shutdown_status, shutdown = self._post_json(
                    f"{server.url}/api/backend/shutdown",
                    {"reason": "test"},
                    token="test-token",
                )
            finally:
                server.stop()

        self.assertEqual(readiness_status, 200)
        self.assertTrue(readiness["safe_to_close"])
        self.assertEqual(readiness["reason"], "No active pipeline, audit, or CSV rerun work was detected.")
        self.assertEqual(denied_status, 401)
        self.assertEqual(denied["error"], "unauthorized")
        self.assertEqual(shutdown_status, 200)
        self.assertEqual(shutdown["command"], "backend.shutdown")
        self.assertTrue(shutdown["ok"])
        self.assertEqual(shutdown["severity"], "info")
        self.assertEqual(shutdown["message"], "Backend shutdown requested.")
        self.assertEqual(shutdown["data"]["evidence_phase"], "completed")
        self.assertEqual(shutdown["data"]["journal_durability"], "strict")
        self.assertTrue(shutdown["data"]["command_id"])
        self.assertTrue(shutdown_event.wait(0.5))

    def test_local_api_shutdown_blocks_when_schedule_stop_watcher_is_armed(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            service = DummyWorkflowFacadeService(root)
            resolved = _resolved(root)
            service.find_related_pipeline_processes = lambda _resolved_arg: []  # type: ignore[method-assign]
            service.read_progress = lambda _resolved_arg: {}  # type: ignore[method-assign]
            service.is_progress_stale = lambda _progress: True  # type: ignore[method-assign]
            service.read_audit_progress = lambda _resolved_arg: {}  # type: ignore[method-assign]
            service.is_audit_progress_stale = lambda _progress: True  # type: ignore[method-assign]
            idle_snapshot = Snapshot(
                resolved=resolved,
                current_activity="Ready.",
                status_summary="Idle",
                log_tail="",
                progress={"ProgressVersion": 2, "Status": "Completed", "CurrentStage": "completed"},
                audit_progress=None,
                latest_failure_report=None,
                latest_failure_json=None,
                latest_audit_csv=None,
                latest_priority_csv=None,
            )
            facade = MediaPipelineApplicationFacade(service, app_version="v6-test")
            deadline = (datetime.now() + timedelta(seconds=30)).replace(microsecond=0)
            facade._schedule_stop_watcher.arm(  # type: ignore[attr-defined]
                service=service,
                resolved=resolved,
                proc=DummyProc(7777),
                deadline=deadline,
            )
            shutdown_event = threading.Event()
            server = LocalApiServer(
                facade,
                token="test-token",
                resolved_provider=lambda: resolved,
                snapshot_provider=lambda: idle_snapshot,
                audit_root_provider=lambda: str(root),
                shutdown_request=shutdown_event.set,
            )
            try:
                server.start()
                readiness_status, readiness = self._get_json(f"{server.url}/api/backend/close-readiness", token="test-token")
                shutdown_status, shutdown = self._post_json(
                    f"{server.url}/api/backend/shutdown",
                    {"reason": "test"},
                    token="test-token",
                )
            finally:
                server.stop()

        self.assertEqual(readiness_status, 200)
        self.assertFalse(readiness["safe_to_close"])
        self.assertEqual(readiness["state"], "completed")
        self.assertIn("schedule-stop watcher is armed", readiness["reason"])
        self.assertIn("PID 7777", readiness["reason"])
        self.assertEqual(readiness["continuous_watcher"]["status"], "armed")
        self.assertEqual(readiness["continuous_watcher"]["pid"], 7777)
        self.assertGreater(readiness["continuous_watcher"]["generation"], 0)
        self.assertEqual(shutdown_status, 200)
        self.assertEqual(shutdown["command"], "backend.shutdown")
        self.assertFalse(shutdown["ok"])
        self.assertEqual(shutdown["severity"], "error")
        self.assertEqual(shutdown["message"], "Backend shutdown blocked because active work may still be running.")
        self.assertFalse(shutdown["data"]["safe_to_close"])
        self.assertEqual(shutdown["data"]["state"], "completed")
        self.assertEqual(shutdown["data"]["reason"], readiness["reason"])
        self.assertEqual(shutdown["data"]["continuous_watcher"]["status"], "armed")
        self.assertEqual(shutdown["data"]["continuous_watcher"]["pid"], 7777)
        self.assertEqual(
            shutdown["data"]["continuous_watcher"]["generation"],
            readiness["continuous_watcher"]["generation"],
        )
        self.assertIn("schedule-stop watcher is armed", shutdown["errors"][0])
        self.assertFalse(shutdown_event.wait(0.2))

    def test_local_api_shutdown_force_cleanup_invokes_backend_owned_process_cleanup(self) -> None:
        shutdown_event = threading.Event()
        logger_name = "test.local_api.force_shutdown_cleanup"
        cleanup_calls: list[str] = []
        readiness_calls = 0
        resolved = object()

        class Readiness:
            def __init__(self, *, safe_to_close: bool) -> None:
                self.safe_to_close = safe_to_close

            def to_mapping(self) -> dict[str, object]:
                return {
                    "schema_version": "desktop_close_readiness.v1",
                    "safe_to_close": self.safe_to_close,
                    "state": "idle" if self.safe_to_close else "processing",
                    "active_work": not self.safe_to_close,
                    "reason": "No active work remains." if self.safe_to_close else "Active pipeline process is running.",
                    "continuous_watcher": {},
                }

        class CleanupService:
            def kill_active_spawned_processes(self) -> list[str]:
                cleanup_calls.append("tracked")
                return ["Force-killed tracked pipeline process tree (PID 1234)."]

            def kill_related_pipeline_processes(self, value: object) -> list[str]:
                self.related_resolved = value
                cleanup_calls.append("related")
                return []

        class CleanupFacade:
            service = CleanupService()

            def get_close_readiness(self, _resolved: object, _snapshot: object) -> Readiness:
                nonlocal readiness_calls
                readiness_calls += 1
                return Readiness(safe_to_close=readiness_calls > 1)

        class Harness(LocalApiProcessCommandPayloadMixin):
            shutdown_request = shutdown_event.set
            facade = CleanupFacade()
            logger = logging.getLogger(logger_name)

            def _resolved(self) -> object:
                return resolved

            def _snapshot(self) -> None:
                return None

        payload = Harness()._backend_shutdown_payload({"force_active_work_shutdown": True})

        self.assertEqual(cleanup_calls, ["tracked", "related"])
        self.assertEqual(readiness_calls, 2)
        self.assertTrue(shutdown_event.wait(1.0))
        self.assertEqual(payload["command"], "backend.shutdown")
        self.assertEqual(payload["severity"], "warning")
        self.assertEqual(payload["message"], "Backend shutdown requested with forced active-work cleanup.")
        self.assertTrue(payload["data"]["forced_active_work_shutdown"])
        self.assertTrue(payload["data"]["cleanup_verified"])
        self.assertTrue(payload["data"]["post_cleanup_readiness"]["safe_to_close"])
        self.assertEqual(payload["data"]["cleanup_messages"], ["Force-killed tracked pipeline process tree (PID 1234)."])
        self.assertIn("Active pipeline process is running.", payload["warnings"][0])
        self.assertIn("Force-killed tracked pipeline", payload["warnings"][1])

    def test_local_api_shutdown_force_cleanup_exception_keeps_backend_available(self) -> None:
        shutdown_event = threading.Event()
        cleanup_calls: list[str] = []
        resolved = object()

        class Readiness:
            def to_mapping(self) -> dict[str, object]:
                return {
                    "schema_version": "desktop_close_readiness.v1",
                    "safe_to_close": False,
                    "state": "processing",
                    "active_work": True,
                    "reason": "Active pipeline process is running.",
                    "continuous_watcher": {},
                }

        class CleanupService:
            def kill_active_spawned_processes(self) -> list[str]:
                cleanup_calls.append("tracked")
                raise RuntimeError("tracked cleanup exploded")

            def kill_related_pipeline_processes(self, _resolved: object) -> list[str]:
                cleanup_calls.append("related")
                raise RuntimeError("descendant cleanup refused termination")

        class CleanupFacade:
            service = CleanupService()

            def get_close_readiness(self, _resolved: object, _snapshot: object) -> Readiness:
                return Readiness()

        class Harness(LocalApiProcessCommandPayloadMixin):
            shutdown_request = shutdown_event.set
            facade = CleanupFacade()
            logger = logging.getLogger("test.local_api.force_shutdown_cleanup_exception")

            def _resolved(self) -> object:
                return resolved

            def _snapshot(self) -> None:
                return None

        with self.assertLogs("test.local_api.force_shutdown_cleanup_exception", level="ERROR"):
            payload = Harness()._backend_shutdown_payload({"force_active_work_shutdown": True})

        self.assertEqual(cleanup_calls, ["tracked", "related"])
        self.assertFalse(shutdown_event.is_set())
        self.assertFalse(payload["ok"])
        self.assertEqual(payload["severity"], "error")
        self.assertEqual(payload["refresh_hint"], "close-readiness")
        self.assertTrue(payload["data"]["active_work"])
        self.assertTrue(payload["data"]["cleanup_uncertain"])
        self.assertIn("tracked cleanup exploded", "\n".join(payload["errors"]))
        self.assertIn("descendant cleanup refused termination", "\n".join(payload["errors"]))

    def test_local_api_shutdown_cleanup_failure_journal_preserves_uncertainty(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            resolved = _resolved(root)
            service = DummyWorkflowFacadeService(root)
            facade = MediaPipelineApplicationFacade(service, app_version="v6-test")
            shutdown_event = threading.Event()
            snapshot = Snapshot(
                resolved=resolved,
                current_activity="Processing.",
                status_summary="Active",
                log_tail="",
                progress={"ProgressVersion": 2, "Status": "Processing", "CurrentStage": "encode"},
                audit_progress=None,
                latest_failure_report=None,
                latest_failure_json=None,
                latest_audit_csv=None,
                latest_priority_csv=None,
            )

            class Readiness:
                def to_mapping(self) -> dict[str, object]:
                    return {
                        "schema_version": "desktop_close_readiness.v1",
                        "safe_to_close": False,
                        "state": "processing",
                        "active_work": True,
                        "reason": "Active pipeline process is running.",
                        "continuous_watcher": {},
                    }

            facade.get_close_readiness = lambda _resolved, _snapshot: Readiness()  # type: ignore[method-assign]

            def fail_tracked_cleanup() -> list[str]:
                raise RuntimeError("tracked process exit unverified")

            service.kill_active_spawned_processes = fail_tracked_cleanup  # type: ignore[method-assign]
            service.kill_related_pipeline_processes = lambda _resolved: []  # type: ignore[method-assign]
            server = LocalApiServer(
                facade,
                token="test-token",
                resolved_provider=lambda: resolved,
                snapshot_provider=lambda: snapshot,
                shutdown_request=shutdown_event.set,
                command_journal_path=root / "RunLogs" / "local_api_command_history.json",
            )
            try:
                server.start()
                status, payload = self._post_json(
                    f"{server.url}/api/backend/shutdown",
                    {"reason": "adversarial-test", "force_active_work_shutdown": True},
                    token="test-token",
                )
                journal = server.command_journal.to_mapping(limit=5)
            finally:
                server.stop()

        self.assertEqual(status, 200)
        self.assertFalse(payload["ok"])
        self.assertFalse(shutdown_event.is_set())
        self.assertTrue(payload["data"]["cleanup_uncertain"])
        entries = [entry for entry in journal["entries"] if entry["command"] == "backend.shutdown"]
        self.assertGreaterEqual(len(entries), 2)
        entry = next(item for item in entries if item["data"].get("cleanup_uncertain") is True)
        self.assertEqual(entry["command"], "backend.shutdown")
        self.assertFalse(entry["ok"])
        self.assertNotEqual(entry["data"].get("evidence_phase"), "completed")
        self.assertEqual(entry["data"]["journal_durability"], "strict")
        self.assertTrue(entry["data"]["cleanup_uncertain"])
        self.assertTrue(entry["data"]["reconciliation_required"])
        self.assertFalse(any(item["data"].get("evidence_phase") == "completed" for item in entries))

    def test_local_api_shutdown_force_cleanup_false_result_is_not_verified_exit(self) -> None:
        shutdown_event = threading.Event()
        resolved = object()

        class Readiness:
            def to_mapping(self) -> dict[str, object]:
                return {
                    "schema_version": "desktop_close_readiness.v1",
                    "safe_to_close": False,
                    "state": "processing",
                    "active_work": True,
                    "reason": "Active pipeline process is running.",
                    "continuous_watcher": {},
                }

        class CleanupService:
            def kill_active_spawned_processes(self) -> bool:
                return False

            def kill_related_pipeline_processes(self, _resolved: object) -> list[str]:
                return []

        class CleanupFacade:
            service = CleanupService()

            def get_close_readiness(self, _resolved: object, _snapshot: object) -> Readiness:
                return Readiness()

        class Harness(LocalApiProcessCommandPayloadMixin):
            shutdown_request = shutdown_event.set
            facade = CleanupFacade()
            logger = logging.getLogger("test.local_api.force_shutdown_cleanup_false")

            def _resolved(self) -> object:
                return resolved

            def _snapshot(self) -> None:
                return None

        payload = Harness()._backend_shutdown_payload({"force_active_work_shutdown": True})

        self.assertFalse(shutdown_event.is_set())
        self.assertFalse(payload["ok"])
        self.assertTrue(payload["data"]["cleanup_uncertain"])
        self.assertIn("reported failure", "\n".join(payload["errors"]))

    def test_local_api_shutdown_force_cleanup_requires_safe_post_cleanup_readiness(self) -> None:
        shutdown_event = threading.Event()
        resolved = object()
        readiness_calls = 0

        class Readiness:
            def to_mapping(self) -> dict[str, object]:
                return {
                    "schema_version": "desktop_close_readiness.v1",
                    "safe_to_close": False,
                    "state": "recovering",
                    "active_work": True,
                    "reason": "Descendant exit remains unverified.",
                    "continuous_watcher": {},
                }

        class CleanupService:
            def kill_active_spawned_processes(self) -> list[str]:
                return ["Tracked root exited; descendant reconciliation remains required."]

            def kill_related_pipeline_processes(self, _resolved: object) -> list[str]:
                return []

        class CleanupFacade:
            service = CleanupService()

            def get_close_readiness(self, _resolved: object, _snapshot: object) -> Readiness:
                nonlocal readiness_calls
                readiness_calls += 1
                return Readiness()

        class Harness(LocalApiProcessCommandPayloadMixin):
            shutdown_request = shutdown_event.set
            facade = CleanupFacade()
            logger = logging.getLogger("test.local_api.force_shutdown_post_cleanup")

            def _resolved(self) -> object:
                return resolved

            def _snapshot(self) -> None:
                return None

        payload = Harness()._backend_shutdown_payload({"force_active_work_shutdown": True})

        self.assertEqual(readiness_calls, 2)
        self.assertFalse(shutdown_event.is_set())
        self.assertFalse(payload["ok"])
        self.assertTrue(payload["data"]["cleanup_uncertain"])
        self.assertEqual(payload["data"]["post_cleanup_readiness"]["state"], "recovering")
        self.assertIn("Descendant exit remains unverified", "\n".join(payload["errors"]))

    def test_local_api_shutdown_force_cleanup_ignores_non_boolean_truthy_values(self) -> None:
        shutdown_event = threading.Event()
        cleanup_calls: list[str] = []
        resolved = object()

        class Readiness:
            def to_mapping(self) -> dict[str, object]:
                return {
                    "schema_version": "desktop_close_readiness.v1",
                    "safe_to_close": False,
                    "state": "processing",
                    "active_work": True,
                    "reason": "Active pipeline process is running.",
                    "continuous_watcher": {},
                }

        class CleanupService:
            def kill_active_spawned_processes(self) -> list[str]:
                cleanup_calls.append("tracked")
                return ["Force-killed tracked pipeline process tree (PID 1234)."]

            def kill_related_pipeline_processes(self, _resolved: object) -> list[str]:
                cleanup_calls.append("related")
                return []

        class CleanupFacade:
            service = CleanupService()

            def get_close_readiness(self, _resolved: object, _snapshot: object) -> Readiness:
                return Readiness()

        class Harness(LocalApiProcessCommandPayloadMixin):
            shutdown_request = shutdown_event.set
            facade = CleanupFacade()
            logger = logging.getLogger("test.local_api.force_shutdown_type_guard")

            def _resolved(self) -> object:
                return resolved

            def _snapshot(self) -> None:
                return None

        payload = Harness()._backend_shutdown_payload({"force_active_work_shutdown": "true"})

        self.assertEqual(cleanup_calls, [])
        self.assertFalse(payload["ok"])
        self.assertEqual(payload["severity"], "error")
        self.assertEqual(payload["message"], "Backend shutdown blocked because active work may still be running.")
        self.assertFalse(shutdown_event.wait(0.2))

    def test_local_api_shutdown_logs_close_readiness_exceptions(self) -> None:
        shutdown_event = threading.Event()
        logger_name = "test.local_api.shutdown"

        class RaisingFacade:
            def get_close_readiness(self, _resolved: object, _snapshot: object) -> object:
                raise RuntimeError("progress unreadable")

        class Harness(LocalApiProcessCommandPayloadMixin):
            shutdown_request = shutdown_event.set
            facade = RaisingFacade()
            logger = logging.getLogger(logger_name)

            def _resolved(self) -> object:
                return object()

            def _snapshot(self) -> None:
                return None

        with self.assertLogs(logger_name, level="ERROR") as logs:
            payload = Harness()._backend_shutdown_payload({})

        self.assertEqual(payload["schema_version"], "desktop_command_result.v1")
        self.assertEqual(payload["command"], "backend.shutdown")
        self.assertFalse(payload["ok"])
        self.assertEqual(payload["severity"], "error")
        self.assertEqual(payload["message"], "Backend shutdown blocked because active work may still be running.")
        self.assertFalse(payload["data"]["safe_to_close"])
        self.assertEqual(payload["data"]["state"], "unknown")
        self.assertIn("Close readiness could not be verified", payload["errors"][0])
        self.assertIn("local API close-readiness verification failed", "\n".join(logs.output))
        self.assertFalse(shutdown_event.wait(0.2))

    def test_local_api_shutdown_logs_callback_failures_after_response(self) -> None:
        callback_event = threading.Event()
        log_event = threading.Event()
        records: list[logging.LogRecord] = []
        logger_name = "test.local_api.shutdown_callback"
        logger = logging.getLogger(logger_name)

        class EventHandler(logging.Handler):
            def emit(self, record: logging.LogRecord) -> None:
                records.append(record)
                log_event.set()

        class Harness(LocalApiProcessCommandPayloadMixin):
            facade = object()
            logger = logging.getLogger(logger_name)

            def shutdown_request(self) -> None:
                callback_event.set()
                raise RuntimeError("shutdown callback broke")

        handler = EventHandler(level=logging.ERROR)
        old_level = logger.level
        logger.addHandler(handler)
        logger.setLevel(logging.ERROR)
        try:
            Harness()._request_backend_shutdown_after_response()
            self.assertTrue(callback_event.wait(1.0))
            self.assertTrue(log_event.wait(1.0))
        finally:
            logger.removeHandler(handler)
            logger.setLevel(old_level)

        combined = "\n".join(record.getMessage() for record in records)
        self.assertIn("local API backend shutdown callback failed", combined)
        self.assertTrue(any(record.exc_info for record in records))

    def test_local_api_shutdown_logs_timer_start_failures(self) -> None:
        logger_name = "test.local_api.shutdown_timer"

        class BrokenTimer:
            daemon = False

            def __init__(self, *_args, **_kwargs) -> None:
                pass

            def start(self) -> None:
                raise RuntimeError("timer unavailable")

        class Harness(LocalApiProcessCommandPayloadMixin):
            facade = object()
            logger = logging.getLogger(logger_name)
            shutdown_request = lambda self: None

        with (
            patch("mediapipeline.core.api.commands_process.threading.Timer", BrokenTimer),
            self.assertLogs(logger_name, level="ERROR") as logs,
        ):
            Harness()._request_backend_shutdown_after_response()

        self.assertIn("local API backend shutdown timer start failed", "\n".join(logs.output))


if __name__ == "__main__":
    unittest.main()
