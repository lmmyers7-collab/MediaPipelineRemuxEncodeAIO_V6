from __future__ import annotations

import sys
import tempfile
import threading
import unittest
from pathlib import Path

from mediapipeline.tools.paths import find_repo_root
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(find_repo_root(Path(__file__)) / "src"))

from mediapipeline.desktop.network.coordinator import CoordinatorDispatcher, _CoordServer


class NetworkCoordinatorStartupTests(unittest.TestCase):
    def test_coordinator_http_request_threads_are_not_daemonized(self) -> None:
        self.assertFalse(_CoordServer.daemon_threads)
        self.assertTrue(getattr(_CoordServer, "block_on_close", True))

    def test_coordinator_bind_address_default_and_validation(self) -> None:
        dispatcher = CoordinatorDispatcher.__new__(CoordinatorDispatcher)
        dispatcher._app = SimpleNamespace(resolved=SimpleNamespace(config_data={}))
        self.assertEqual(CoordinatorDispatcher._coord_bind_address(dispatcher), "0.0.0.0")

        dispatcher._app = SimpleNamespace(
            resolved=SimpleNamespace(config_data={"CoordinatorBindAddress": "127.0.0.1"})
        )
        self.assertEqual(CoordinatorDispatcher._coord_bind_address(dispatcher), "127.0.0.1")

        dispatcher._app = SimpleNamespace(
            resolved=SimpleNamespace(config_data={"CoordinatorBindAddress": "http://0.0.0.0"})
        )
        self.assertEqual(CoordinatorDispatcher._coord_bind_address(dispatcher), "0.0.0.0")

    def test_coordinator_http_bind_failure_raises_instead_of_marking_started(self) -> None:
        dispatcher = CoordinatorDispatcher.__new__(CoordinatorDispatcher)
        dispatcher._http_server = None
        dispatcher._coord_port = lambda: 7830
        dispatcher._coord_bind_address = lambda: "127.0.0.1"

        with patch(
            "mediapipeline.desktop.network.coordinator_lifecycle._CoordServer",
            side_effect=OSError("address already in use"),
        ):
            with self.assertLogs("mediapipeline.desktop.network.coordinator", level="ERROR") as logs:
                with self.assertRaisesRegex(RuntimeError, "Could not start coordinator HTTP server"):
                    CoordinatorDispatcher._start_http_server(dispatcher)

        self.assertIsNone(dispatcher._http_server)
        self.assertIn("workers will not be able to connect", "\n".join(logs.output))

    def test_coordinator_http_thread_start_failure_closes_server(self) -> None:
        class FakeServer:
            def __init__(self) -> None:
                self.dispatcher: object | None = None
                self.closed = False

            def serve_forever(self) -> None:
                return None

            def server_close(self) -> None:
                self.closed = True

        class BadThread:
            def __init__(self, *_args, **_kwargs) -> None:
                return None

            def start(self) -> None:
                raise RuntimeError("thread denied")

        server = FakeServer()
        dispatcher = CoordinatorDispatcher.__new__(CoordinatorDispatcher)
        dispatcher._http_server = None
        dispatcher._coord_port = lambda: 7830
        dispatcher._coord_bind_address = lambda: "127.0.0.1"

        with (
            patch("mediapipeline.desktop.network.coordinator_lifecycle._CoordServer", return_value=server),
            patch("mediapipeline.desktop.network.coordinator_lifecycle.threading.Thread", BadThread),
            self.assertLogs("mediapipeline.desktop.network.coordinator", level="ERROR") as logs,
        ):
            with self.assertRaisesRegex(RuntimeError, "Could not start coordinator HTTP server"):
                CoordinatorDispatcher._start_http_server(dispatcher)

        self.assertIsNone(dispatcher._http_server)
        self.assertIs(server.dispatcher, dispatcher)
        self.assertTrue(server.closed)
        self.assertIn("thread denied", "\n".join(logs.output))

    def test_coordinator_reaper_thread_start_failure_is_logged(self) -> None:
        class BadThread:
            def __init__(self, *_args, **_kwargs) -> None:
                return None

            def start(self) -> None:
                raise RuntimeError("reaper thread denied")

        dispatcher = CoordinatorDispatcher.__new__(CoordinatorDispatcher)
        dispatcher._reaper_stop = threading.Event()
        dispatcher._reaper_thread = object()  # type: ignore[assignment]

        with (
            patch("mediapipeline.desktop.network.coordinator_lifecycle.threading.Thread", BadThread),
            self.assertLogs("mediapipeline.desktop.network.coordinator", level="ERROR") as logs,
        ):
            with self.assertRaisesRegex(RuntimeError, "Could not start coordinator stale-job reaper thread"):
                CoordinatorDispatcher._start_reaper(dispatcher)

        self.assertIsNone(dispatcher._reaper_thread)
        self.assertIn("Could not start coordinator stale-job reaper thread: reaper thread denied", "\n".join(logs.output))

    def test_coordinator_mdns_start_failure_logs_manual_url_fallback(self) -> None:
        dispatcher = CoordinatorDispatcher.__new__(CoordinatorDispatcher)
        dispatcher._mdns = object()
        dispatcher._coord_port = lambda: 7830
        dispatcher._coord_bind_address = lambda: "127.0.0.1"

        with (
            patch(
                "mediapipeline.desktop.network.mdns.CoordinatorAdvertiser",
                side_effect=RuntimeError("zeroconf missing"),
            ),
            self.assertLogs("mediapipeline.desktop.network.coordinator", level="WARNING") as logs,
        ):
            CoordinatorDispatcher._start_mdns(dispatcher)

        self.assertIsNone(dispatcher._mdns)
        text = "\n".join(logs.output)
        self.assertIn("Coordinator mDNS advertisement unavailable", text)
        self.assertIn("workers can enter the coordinator URL manually", text)
        self.assertIn("zeroconf missing", text)

    def test_coordinator_mdns_registration_failure_does_not_mark_advertiser_active(self) -> None:
        class RegistrationFailedAdvertiser:
            def __init__(self, port: int, bind_address: str = "0.0.0.0") -> None:
                self.port = port
                self.bind_address = bind_address

            def start(self) -> bool:
                return False

        dispatcher = CoordinatorDispatcher.__new__(CoordinatorDispatcher)
        dispatcher._mdns = object()
        dispatcher._coord_port = lambda: 7830
        dispatcher._coord_bind_address = lambda: "192.168.1.25"

        with (
            patch("mediapipeline.desktop.network.mdns.CoordinatorAdvertiser", RegistrationFailedAdvertiser),
            self.assertLogs("mediapipeline.desktop.network.coordinator", level="WARNING") as logs,
        ):
            CoordinatorDispatcher._start_mdns(dispatcher)

        self.assertIsNone(dispatcher._mdns)
        self.assertIn(
            "Coordinator mDNS advertisement unavailable; workers can enter the coordinator URL manually.",
            "\n".join(logs.output),
        )

    def test_coordinator_constructor_cleans_up_http_when_reaper_start_fails(self) -> None:
        class FakeServer:
            def __init__(self) -> None:
                self.shutdown_called = False
                self.close_called = False

            def shutdown(self) -> None:
                self.shutdown_called = True

            def server_close(self) -> None:
                self.close_called = True

        with tempfile.TemporaryDirectory() as td:
            server = FakeServer()
            holder: dict[str, CoordinatorDispatcher] = {}
            app = SimpleNamespace(
                service=SimpleNamespace(app_state_path=Path(td) / "app_state.json"),
                resolved=SimpleNamespace(config_data={}),
                queue_records=[],
            )

            def fake_start_http(dispatcher: CoordinatorDispatcher) -> None:
                holder["dispatcher"] = dispatcher
                dispatcher._http_server = server  # type: ignore[assignment]

            def fail_reaper(_dispatcher: CoordinatorDispatcher) -> None:
                raise RuntimeError("reaper denied")

            with (
                patch.object(CoordinatorDispatcher, "_load_or_generate_token", return_value="token"),
                patch.object(CoordinatorDispatcher, "_start_http_server", fake_start_http),
                patch.object(CoordinatorDispatcher, "_start_reaper", fail_reaper),
                self.assertLogs("mediapipeline.desktop.network.coordinator", level="ERROR") as logs,
            ):
                with self.assertRaisesRegex(RuntimeError, "reaper denied"):
                    CoordinatorDispatcher(app)

            dispatcher = holder["dispatcher"]
            self.assertFalse(dispatcher._accepting_claims)
            self.assertIsNone(dispatcher._http_server)
            self.assertTrue(server.shutdown_called)
            self.assertTrue(server.close_called)
            self.assertIn(
                "Coordinator startup failed after HTTP server start; cleaning up partial coordinator.",
                "\n".join(logs.output),
            )

    def test_coordinator_constructor_refuses_start_when_inflight_restore_fails(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            state_dir = Path(td)
            (state_dir / "coordinator_inflight.json").write_text("{not-json", encoding="utf-8")
            app = SimpleNamespace(
                service=SimpleNamespace(app_state_path=state_dir / "app_state.json"),
                resolved=SimpleNamespace(config_data={"CoordinatorBindAddress": "127.0.0.1"}),
                queue_records=[],
            )

            with (
                patch.object(CoordinatorDispatcher, "_load_or_generate_token", return_value="token"),
                patch.object(CoordinatorDispatcher, "_start_http_server") as start_http,
                self.assertLogs("mediapipeline.desktop.network.coordinator", level="ERROR") as logs,
            ):
                with self.assertRaisesRegex(RuntimeError, "in-flight state restore failed"):
                    CoordinatorDispatcher(app)

            start_http.assert_not_called()
            self.assertIn("refusing to start coordinator", "\n".join(logs.output))

    def test_coordinator_startup_cluster_log_failure_does_not_abort_startup(self) -> None:
        calls: list[str] = []

        def fake_start_http(dispatcher: CoordinatorDispatcher) -> None:
            calls.append("http")
            dispatcher._http_server = object()  # type: ignore[assignment]

        def fake_start_reaper(_dispatcher: CoordinatorDispatcher) -> None:
            calls.append("reaper")

        def fake_start_mdns(_dispatcher: CoordinatorDispatcher) -> None:
            calls.append("mdns")

        with tempfile.TemporaryDirectory() as td:
            app = SimpleNamespace(
                service=SimpleNamespace(app_state_path=Path(td) / "app_state.json"),
                resolved=SimpleNamespace(config_data={"CoordinatorBindAddress": "127.0.0.1"}),
                queue_records=[],
            )

            with (
                patch.object(CoordinatorDispatcher, "_load_or_generate_token", return_value="token"),
                patch.object(CoordinatorDispatcher, "_start_http_server", fake_start_http),
                patch.object(CoordinatorDispatcher, "_start_reaper", fake_start_reaper),
                patch.object(CoordinatorDispatcher, "_start_mdns", fake_start_mdns),
                patch.object(
                    CoordinatorDispatcher,
                    "log_cluster_event",
                    side_effect=RuntimeError("cluster blocked"),
                ),
                self.assertLogs("mediapipeline.desktop.network.coordinator", level="WARNING") as logs,
            ):
                dispatcher = CoordinatorDispatcher(app)

        self.assertEqual(calls, ["http", "reaper", "mdns"])
        self.assertTrue(dispatcher._accepting_claims)
        self.assertIsNotNone(dispatcher._http_server)
        self.assertIn("Failed to emit coordinator-started cluster event", "\n".join(logs.output))
        self.assertIn("cluster blocked", "\n".join(logs.output))


if __name__ == "__main__":
    unittest.main()
