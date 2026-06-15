from __future__ import annotations

import sys
import unittest
from pathlib import Path

from mediapipeline.tools.paths import find_repo_root

sys.path.insert(0, str(find_repo_root(Path(__file__)) / "src"))

from mediapipeline.desktop.api.contract import LOCAL_API_ROUTE_CONTRACT  # noqa: E402
from mediapipeline.desktop.api.read_payloads_status import LocalApiStatusReadPayloadMixin  # noqa: E402
from mediapipeline.desktop.api.routes_read import GET_ROUTE_HANDLERS  # noqa: E402
from mediapipeline.desktop.api.server import LocalApiServer  # noqa: E402


class _PayloadHarness(LocalApiStatusReadPayloadMixin):
    def __init__(self, facade: object) -> None:
        self.facade = facade


class _FacadeWithWatchState:
    app_version = "test"

    def __init__(self, state: dict[str, object] | None = None, *, fail: bool = False) -> None:
        self.state = state or {}
        self.fail = fail
        self.cancel_reasons: list[str] = []
        self.stop_reasons: list[str] = []

    def get_watch_folder_state(self) -> dict[str, object]:
        if self.fail:
            raise RuntimeError("state failed")
        return dict(self.state)

    def _cancel_pipeline_schedule_stop_watcher(self, reason: str) -> None:
        self.cancel_reasons.append(reason)

    def _stop_watch_folder_manager(self, reason: str) -> None:
        self.stop_reasons.append(reason)


class WatchFolderRouteTests(unittest.TestCase):
    def test_read_route_dispatches_to_watch_folder_payload(self) -> None:
        spec = GET_ROUTE_HANDLERS["/api/watch-folders/status"]

        self.assertEqual(spec.method_name, "_watch_folders_status_payload")
        self.assertFalse(spec.needs_query)

    def test_route_contract_documents_read_only_watch_status(self) -> None:
        route = next(
            item
            for item in LOCAL_API_ROUTE_CONTRACT
            if item["method"] == "GET" and item["path"] == "/api/watch-folders/status"
        )

        self.assertTrue(route["auth_required"])
        self.assertEqual(route["effect"], "none")
        self.assertEqual(route["response_schema"], "desktop_watch_folders.v1")
        self.assertIn("Read", route["purpose"])

    def test_payload_reads_facade_watch_state(self) -> None:
        expected = {
            "schema_version": "desktop_watch_folders.v1",
            "enabled": True,
            "running": True,
            "status": "running",
            "roots": [{"path": "C:/Media", "reachable": True, "last_error": ""}],
        }
        payload = _PayloadHarness(_FacadeWithWatchState(expected))._watch_folders_status_payload()

        self.assertEqual(payload, expected)

    def test_payload_falls_back_when_facade_state_fails(self) -> None:
        payload = _PayloadHarness(_FacadeWithWatchState(fail=True))._watch_folders_status_payload()

        self.assertEqual(payload["schema_version"], "desktop_watch_folders.v1")
        self.assertEqual(payload["status"], "error")
        self.assertEqual(payload["reason"], "Watch-folder state could not be read.")
        self.assertEqual(payload["last_error"], "state failed")

    def test_local_api_stop_stops_watch_folder_manager(self) -> None:
        facade = _FacadeWithWatchState()
        server = LocalApiServer(facade, token="test-token")

        server.stop()

        self.assertEqual(facade.cancel_reasons, ["local API server stopping"])
        self.assertEqual(facade.stop_reasons, ["local API server stopping"])


if __name__ == "__main__":
    unittest.main()
