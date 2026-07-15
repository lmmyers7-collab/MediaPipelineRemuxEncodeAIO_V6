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
from mediapipeline.desktop.application import CommandResult, MediaPipelineApplicationFacade
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


class LocalApiProcessCommandTests(LocalApiHttpTestMixin, unittest.TestCase):
    def test_network_rerun_retry_http_route_is_strict_and_dispatches_exact_request(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            facade = MediaPipelineApplicationFacade(DummyWorkflowFacadeService(root), app_version="v6-test")
            resolved = _resolved(root)
            dispatched: list[dict[str, object]] = []

            def request_retry(_resolved_paths: ResolvedPaths, request: dict[str, object]) -> CommandResult:
                dispatched.append(dict(request))
                return CommandResult(
                    command="rerun.network.retry",
                    ok=True,
                    message="Network CSV rerun row reopened.",
                    data={"batch_id": request["batch_id"], "row_key": request["row_key"]},
                )

            facade.request_network_rerun_retry = request_retry  # type: ignore[method-assign]
            server = LocalApiServer(
                facade,
                token="test-token",
                resolved_provider=lambda: resolved,
                command_journal_path=root / "RunLogs" / "local_api_command_history.json",
            )
            request = {
                "batch_id": "batch-1",
                "row_key": "row-1",
                "request_id": "request-1",
                "reason": "operator_requested_retry_after_source_restore",
                "confirm_retry": True,
            }
            try:
                server.start()
                invalid_status, invalid = self._post_json(
                    f"{server.url}/api/rerun/network/retry",
                    {**request, "confirm_retry": "true"},
                    token="test-token",
                )
                status, payload = self._post_json(
                    f"{server.url}/api/rerun/network/retry",
                    request,
                    token="test-token",
                )
            finally:
                server.stop()

        self.assertEqual(invalid_status, 400)
        self.assertEqual(invalid["path"], "/api/rerun/network/retry")
        self.assertIn("confirm_retry", invalid["error"])
        self.assertEqual(status, 200)
        self.assertEqual(payload["command"], "rerun.network.retry")
        self.assertTrue(payload["data"]["strict_command_journal_recorded"])
        self.assertRegex(payload["data"]["command_id"], r"^[0-9a-f]{32}$")
        self.assertEqual(len(dispatched), 1)
        self.assertEqual(
            {key: dispatched[0][key] for key in request},
            request,
        )

    def test_local_api_process_commands_require_token_before_side_effects(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            service = DummyWorkflowFacadeService(root)
            facade = MediaPipelineApplicationFacade(service, app_version="v6-test")
            resolved = _resolved(root)
            server = LocalApiServer(
                facade,
                token="test-token",
                resolved_provider=lambda: resolved,
                audit_root_provider=lambda: str(root),
            )
            try:
                server.start()
                no_token_status, no_token = self._post_json(
                    f"{server.url}/api/pipeline/start",
                    {"mode": "validate", "sleep_seconds": 3},
                )
                wrong_token_status, wrong_token = self._post_json(
                    f"{server.url}/api/pipeline/start",
                    {"mode": "validate", "sleep_seconds": 3},
                    token="wrong-token",
                )
                side_effect_before_auth = hasattr(service, "started_pipeline")
                ok_status, ok = self._post_json(
                    f"{server.url}/api/pipeline/start",
                    {"mode": "validate", "sleep_seconds": 3},
                    token="test-token",
                )
            finally:
                server.stop()

        self.assertEqual(no_token_status, 401)
        self.assertEqual(no_token["error"], "unauthorized")
        self.assertEqual(wrong_token_status, 401)
        self.assertEqual(wrong_token["error"], "unauthorized")
        self.assertFalse(side_effect_before_auth)
        self.assertEqual(ok_status, 200)
        self.assertEqual(ok["command"], "pipeline.start")
        self.assertTrue(hasattr(service, "started_pipeline"))
        self.assertEqual(service.started_pipeline["mode"], "validate")

    def test_local_api_rejects_invalid_command_payload_before_side_effects(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            service = DummyWorkflowFacadeService(root)
            facade = MediaPipelineApplicationFacade(service, app_version="v6-test")
            resolved = _resolved(root)
            server = LocalApiServer(
                facade,
                token="test-token",
                resolved_provider=lambda: resolved,
                audit_root_provider=lambda: str(root),
            )
            try:
                server.start()
                status, payload = self._post_json(
                    f"{server.url}/api/pipeline/start",
                    {"mode": "validate", "extra_args": "-NoDeleteSource", "token": "secret-value"},
                    token="test-token",
                )
                commands_status, commands = self._get_json(f"{server.url}/api/commands?limit=5", token="test-token")
            finally:
                server.stop()

        self.assertEqual(status, 400)
        self.assertEqual(payload["path"], "/api/pipeline/start")
        self.assertIn("extra_args", payload["error"])
        self.assertIn("Extra inputs are not permitted", payload["error"])
        self.assertFalse(hasattr(service, "started_pipeline"))
        self.assertEqual(commands_status, 200)
        self.assertEqual(commands["schema_version"], "desktop_command_history.v1")
        self.assertEqual(commands["count"], 1)
        entry = commands["entries"][0]
        self.assertEqual(entry["command"], "local_api.validation_failed")
        self.assertFalse(entry["ok"])
        self.assertEqual(entry["severity"], "error")
        self.assertEqual(entry["data"]["path"], "/api/pipeline/start")
        self.assertEqual(entry["request"]["token"], "<redacted>")
        self.assertEqual(entry["request"]["extra_args"], "-NoDeleteSource")

    def test_local_api_route_exception_is_recorded_in_command_journal(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            service = DummyWorkflowFacadeService(root)
            facade = MediaPipelineApplicationFacade(service, app_version="v6-test")
            resolved = _resolved(root)

            def fail_start(_resolved_paths: ResolvedPaths, _request: dict) -> object:
                raise RuntimeError("backend exploded with sensitive diagnostic detail")

            facade.start_pipeline_process = fail_start  # type: ignore[method-assign]
            server = LocalApiServer(
                facade,
                token="test-token",
                resolved_provider=lambda: resolved,
                command_journal_path=root / "RunLogs" / "local_api_command_history.json",
            )
            try:
                server.start()
                status, payload = self._post_json(
                    f"{server.url}/api/pipeline/start",
                    {"mode": "validate", "sleep_seconds": 1},
                    token="test-token",
                )
                commands_status, commands = self._get_json(f"{server.url}/api/commands?limit=5", token="test-token")
            finally:
                server.stop()

        self.assertEqual(status, 500)
        self.assertEqual(payload["error"], "internal route error")
        self.assertEqual(payload["path"], "/api/pipeline/start")
        self.assertRegex(payload["error_id"], r"^[0-9a-f]{12}$")
        self.assertEqual(commands_status, 200)
        self.assertEqual(commands["schema_version"], "desktop_command_history.v1")
        self.assertEqual(commands["count"], 2)
        entry = commands["entries"][0]
        self.assertEqual(entry["command"], "local_api.route_exception")
        self.assertFalse(entry["ok"])
        self.assertEqual(entry["severity"], "error")
        self.assertEqual(entry["refresh_hint"], "diagnostics")
        self.assertEqual(entry["errors"], ["Internal route error."])
        self.assertEqual(entry["data"]["path"], "/api/pipeline/start")
        self.assertEqual(entry["data"]["status"], 500)
        self.assertEqual(entry["data"]["error_id"], payload["error_id"])
        self.assertEqual(entry["request"]["mode"], "validate")
        self.assertEqual(entry["request"]["sleep_seconds"], 1)
        self.assertNotIn("backend exploded", json.dumps(entry, sort_keys=True))
        accepted = commands["entries"][1]
        self.assertEqual(accepted["command"], "pipeline.start")
        self.assertEqual(accepted["data"]["evidence_phase"], "accepted")
        self.assertTrue(accepted["ok"])
        persistence = commands["journal_persistence"]
        self.assertFalse(persistence["degraded"])
        self.assertEqual(persistence["json"]["status"], "ok")

    def test_local_api_scheduled_continuous_start_arms_backend_stop_watcher(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            service = DummyWorkflowFacadeService(root)
            service.save_app_state({"schedule_enabled": True, "schedule_grid": service.default_schedule_grid()})
            deadline = (datetime.now() + timedelta(seconds=60)).replace(microsecond=0).isoformat()
            service.evaluate_schedule = lambda _enabled, _grid: {  # type: ignore[method-assign]
                "enabled": True,
                "allowed_now": True,
                "status_text": f"Schedule: Allowed now until {deadline}",
                "current_window_end": deadline,
                "next_allowed_start": datetime.now().replace(microsecond=0).isoformat(),
                "next_allowed_end": deadline,
                "next_transition": deadline,
            }
            service.find_related_pipeline_processes = lambda _resolved_arg: []  # type: ignore[method-assign]
            service.read_progress = lambda _resolved_arg: {}  # type: ignore[method-assign]
            service.is_progress_stale = lambda _progress: True  # type: ignore[method-assign]
            service.read_audit_progress = lambda _resolved_arg: {}  # type: ignore[method-assign]
            service.is_audit_progress_stale = lambda _progress: True  # type: ignore[method-assign]
            facade = MediaPipelineApplicationFacade(service, app_version="v6-test")
            resolved = _resolved(root)
            service.snapshot = Snapshot(
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
            server = LocalApiServer(
                facade,
                token="test-token",
                resolved_provider=lambda: resolved,
                audit_root_provider=lambda: str(root),
            )
            try:
                server.start()
                status, payload = self._post_json(
                    f"{server.url}/api/pipeline/start",
                    {"mode": "continuous", "sleep_seconds": 3},
                    token="test-token",
                )
                armed_state = facade._schedule_stop_watcher.state()  # type: ignore[attr-defined]
                schedule_status, schedule_payload = self._get_json(f"{server.url}/api/schedule", token="test-token")
                close_status, close_payload = self._get_json(f"{server.url}/api/backend/close-readiness", token="test-token")
            finally:
                server.stop()
            stopped_state = facade._schedule_stop_watcher.state()  # type: ignore[attr-defined]

        self.assertEqual(status, 200)
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["data"]["mode"], "continuous")
        self.assertEqual(service.started_pipeline["mode"], "continuous")
        self.assertEqual(armed_state.status, "armed")
        self.assertEqual(armed_state.pid, 24680)
        self.assertEqual(armed_state.deadline, deadline)
        self.assertGreater(armed_state.generation, 0)
        self.assertEqual(schedule_status, 200)
        self.assertEqual(schedule_payload["continuous_watcher"]["status"], "armed")
        self.assertEqual(schedule_payload["continuous_watcher"]["pid"], 24680)
        self.assertEqual(schedule_payload["continuous_watcher"]["generation"], armed_state.generation)
        self.assertEqual(close_status, 200)
        self.assertFalse(close_payload["safe_to_close"])
        self.assertTrue(close_payload["active_work"])
        self.assertIn("schedule-stop watcher is armed", close_payload["reason"])
        self.assertEqual(close_payload["continuous_watcher"]["status"], "armed")
        self.assertEqual(close_payload["continuous_watcher"]["pid"], 24680)
        self.assertEqual(close_payload["continuous_watcher"]["generation"], armed_state.generation)
        self.assertEqual(stopped_state.status, "canceled")


if __name__ == "__main__":
    unittest.main()
