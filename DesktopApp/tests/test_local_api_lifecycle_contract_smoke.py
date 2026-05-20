from __future__ import annotations

import json
import sys
import tempfile
import threading
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from mediapipeline_desktop_app.api import LocalApiServer
from mediapipeline_desktop_app.application import MediaPipelineApplicationFacade

try:  # unittest discovery can import tests as top-level modules or package modules.
    from .test_application_facade import DummyProc, DummyWorkflowFacadeService
    from .test_webview_real_media_smoke import _write_fixture_state
except ImportError:  # pragma: no cover - fallback for direct test execution
    from test_application_facade import DummyProc, DummyWorkflowFacadeService
    from test_webview_real_media_smoke import _write_fixture_state


def _json_request(
    url: str,
    *,
    method: str = "GET",
    token: str | None = None,
    payload: dict[str, object] | None = None,
) -> tuple[int, dict[str, object]]:
    headers: dict[str, str] = {}
    body: bytes | None = None
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if payload is not None:
        headers["Content-Type"] = "application/json"
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = Request(url, data=body, headers=headers, method=method)
    try:
        with urlopen(request, timeout=5) as response:  # noqa: S310 - localhost test server
            return response.status, json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        return exc.code, json.loads(exc.read().decode("utf-8"))


def _service_with_idle_fixture(root: Path) -> tuple[object, DummyWorkflowFacadeService]:
    resolved, _source, _output = _write_fixture_state(root)
    service = DummyWorkflowFacadeService(root)
    snapshot = service.build_snapshot(resolved, str(root))
    if snapshot.progress is None:
        snapshot.progress = {}
    snapshot.progress["Status"] = "Completed"
    snapshot.progress["CurrentStage"] = "completed"
    service.snapshot = snapshot
    service.find_related_pipeline_processes = lambda _resolved: []  # type: ignore[method-assign]
    service.read_progress = lambda _resolved: {}  # type: ignore[method-assign]
    service.is_progress_stale = lambda _progress: True  # type: ignore[method-assign]
    service.read_audit_progress = lambda _resolved: {}  # type: ignore[method-assign]
    service.is_audit_progress_stale = lambda _progress: True  # type: ignore[method-assign]
    return resolved, service


class LocalApiLifecycleContractSmokeTests(unittest.TestCase):
    def test_close_readiness_and_shutdown_contract_when_backend_is_safe(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            resolved, service = _service_with_idle_fixture(root)
            facade = MediaPipelineApplicationFacade(service, app_version="v5-lifecycle-smoke")
            shutdown_event = threading.Event()
            server = LocalApiServer(
                facade,
                token="lifecycle-safe-token",
                resolved_provider=lambda: resolved,
                audit_root_provider=lambda: str(root),
                shutdown_request=shutdown_event.set,
            )
            try:
                server.start()
                close_status, close_payload = _json_request(
                    f"{server.url}/api/backend/close-readiness",
                    token=server.token,
                )
                denied_status, denied = _json_request(
                    f"{server.url}/api/backend/shutdown",
                    method="POST",
                    payload={"reason": "lifecycle-contract-smoke"},
                )
                shutdown_status, shutdown = _json_request(
                    f"{server.url}/api/backend/shutdown",
                    method="POST",
                    token=server.token,
                    payload={"reason": "lifecycle-contract-smoke"},
                )
            finally:
                server.stop()

        self.assertEqual(close_status, 200)
        self.assertEqual(close_payload["schema_version"], "desktop_close_readiness.v1")
        self.assertTrue(close_payload["safe_to_close"])
        self.assertFalse(close_payload["active_work"])
        self.assertEqual(close_payload["state"], "completed")
        self.assertEqual(close_payload["continuous_watcher"]["status"], "idle")
        self.assertEqual(close_payload["continuous_watcher"]["generation"], 0)
        self.assertEqual(denied_status, 401)
        self.assertEqual(denied["error"], "unauthorized")
        self.assertEqual(shutdown_status, 200)
        self.assertEqual(shutdown["schema_version"], "desktop_command_result.v1")
        self.assertEqual(shutdown["command"], "backend.shutdown")
        self.assertTrue(shutdown["ok"])
        self.assertEqual(shutdown["severity"], "info")
        self.assertEqual(shutdown["message"], "Backend shutdown requested.")
        self.assertIsNone(shutdown["warnings"])
        self.assertTrue(shutdown_event.wait(1.0))

    def test_close_readiness_and_shutdown_contract_blocks_when_watcher_is_armed(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            resolved, service = _service_with_idle_fixture(root)
            facade = MediaPipelineApplicationFacade(service, app_version="v5-lifecycle-smoke")
            deadline = (datetime.now() + timedelta(minutes=7)).replace(microsecond=0)
            facade._schedule_stop_watcher.arm(  # type: ignore[attr-defined]
                service=service,
                resolved=resolved,
                proc=DummyProc(43210),
                deadline=deadline,
            )
            shutdown_event = threading.Event()
            server = LocalApiServer(
                facade,
                token="lifecycle-blocked-token",
                resolved_provider=lambda: resolved,
                audit_root_provider=lambda: str(root),
                shutdown_request=shutdown_event.set,
            )
            try:
                server.start()
                close_status, close_payload = _json_request(
                    f"{server.url}/api/backend/close-readiness",
                    token=server.token,
                )
                shutdown_status, shutdown = _json_request(
                    f"{server.url}/api/backend/shutdown",
                    method="POST",
                    token=server.token,
                    payload={"reason": "lifecycle-contract-smoke"},
                )
            finally:
                server.stop()

        self.assertEqual(close_status, 200)
        self.assertEqual(close_payload["schema_version"], "desktop_close_readiness.v1")
        self.assertFalse(close_payload["safe_to_close"])
        self.assertTrue(close_payload["active_work"])
        self.assertEqual(close_payload["state"], "completed")
        self.assertIn("schedule-stop watcher is armed", close_payload["reason"])
        self.assertIn("PID 43210", close_payload["reason"])
        watcher = close_payload["continuous_watcher"]
        self.assertEqual(watcher["status"], "armed")
        self.assertEqual(watcher["pid"], 43210)
        self.assertEqual(watcher["deadline"], deadline.isoformat())
        self.assertFalse(watcher["stop_requested"])
        self.assertGreater(watcher["generation"], 0)

        self.assertEqual(shutdown_status, 200)
        self.assertEqual(shutdown["schema_version"], "desktop_command_result.v1")
        self.assertEqual(shutdown["command"], "backend.shutdown")
        self.assertFalse(shutdown["ok"])
        self.assertEqual(shutdown["severity"], "error")
        self.assertEqual(shutdown["message"], "Backend shutdown blocked because active work may still be running.")
        self.assertIn("schedule-stop watcher is armed", shutdown["errors"][0])
        self.assertEqual(shutdown["data"]["safe_to_close"], False)
        self.assertEqual(shutdown["data"]["state"], "completed")
        self.assertEqual(shutdown["data"]["reason"], close_payload["reason"])
        self.assertEqual(shutdown["data"]["continuous_watcher"]["status"], "armed")
        self.assertEqual(shutdown["data"]["continuous_watcher"]["pid"], 43210)
        self.assertEqual(shutdown["data"]["continuous_watcher"]["deadline"], deadline.isoformat())
        self.assertEqual(shutdown["data"]["continuous_watcher"]["generation"], watcher["generation"])
        self.assertFalse(shutdown_event.wait(0.2))


if __name__ == "__main__":
    unittest.main()
