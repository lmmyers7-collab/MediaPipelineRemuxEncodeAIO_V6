from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

from mediapipeline.tools.paths import find_repo_root
from unittest.mock import patch

sys.path.insert(0, str(find_repo_root(Path(__file__)) / "src"))

from mediapipeline.desktop.network import mdns
from mediapipeline.desktop.api import LocalApiServer
from mediapipeline.desktop.application.facade import MediaPipelineApplicationFacade
from mediapipeline.desktop.models import ResolvedPaths
from tests.python.desktop.application_facade_test_support import DummyFacadeService


def _resolved(root: Path, config: dict[str, object]) -> ResolvedPaths:
    return ResolvedPaths(
        app_root=root,
        workspace_root=root,
        pipeline_path=root / "pipeline.ps1",
        config_path=root / "config.psd1",
        audit_script_path=root / "audit.ps1",
        rerun_script_path=root / "rerun.ps1",
        powershell_host=str(root / "pwsh.exe"),
        local_base=root / "LocalBase",
        state_root=root / "LocalBase" / "State",
        app_state_path=root / "LocalBase" / "State" / "App" / "desktop_app_state.json",
        config_data=config,
    )


def _post_json(url: str, payload: dict, token: str) -> tuple[int, dict]:
    import json
    from urllib.error import HTTPError
    from urllib.request import Request, urlopen

    request = Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urlopen(request, timeout=5) as response:  # noqa: S310 - localhost test server
            return response.status, json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        return exc.code, json.loads(exc.read().decode("utf-8"))


def _get_json(url: str, token: str) -> tuple[int, dict]:
    import json
    from urllib.error import HTTPError
    from urllib.request import Request, urlopen

    request = Request(url, headers={"Authorization": f"Bearer {token}"})
    try:
        with urlopen(request, timeout=5) as response:  # noqa: S310 - localhost test server
            return response.status, json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        return exc.code, json.loads(exc.read().decode("utf-8"))


class MdnsDiagnosticsTests(unittest.TestCase):
    def test_optional_zeroconf_symbols_remain_patchable_without_dependency(self) -> None:
        for symbol_name in ("ServiceBrowser", "ServiceInfo", "ServiceStateChange", "Zeroconf"):
            self.assertTrue(hasattr(mdns, symbol_name), symbol_name)

    def test_async_discovery_thread_start_failure_is_logged(self) -> None:
        class BadThread:
            def __init__(self, *_args: object, **_kwargs: object) -> None:
                return None

            def start(self) -> None:
                raise RuntimeError("thread denied")

        callbacks: list[list[str]] = []

        with (
            patch("mediapipeline.desktop.network.mdns.threading.Thread", BadThread),
            self.assertLogs("mediapipeline.desktop.network.mdns", level="WARNING") as logs,
        ):
            with self.assertRaisesRegex(RuntimeError, "Could not start mDNS discovery thread"):
                mdns.discover_coordinators_async(callbacks.append, timeout_secs=0.0)

        self.assertEqual(callbacks, [])
        self.assertIn("mDNS async discovery thread failed to start: thread denied", "\n".join(logs.output))

    def test_async_discovery_callback_failure_is_logged(self) -> None:
        def fail_callback(_urls: list[str]) -> None:
            raise RuntimeError("callback failed")

        with self.assertLogs("mediapipeline.desktop.network.mdns", level="ERROR") as logs:
            mdns._invoke_discovery_callback(fail_callback, ["http://127.0.0.1:7830"])

        self.assertIn("mDNS async discovery callback failed.", "\n".join(logs.output))
        self.assertIn("callback failed", "\n".join(logs.output))

    def test_advertiser_stop_logs_cleanup_failures(self) -> None:
        class FailingZeroconf:
            def unregister_service(self, _info: object) -> None:
                raise RuntimeError("unregister failed")

            def close(self) -> None:
                raise RuntimeError("close failed")

        advertiser = mdns.CoordinatorAdvertiser.__new__(mdns.CoordinatorAdvertiser)
        advertiser._zc = FailingZeroconf()
        advertiser._info = object()

        with self.assertLogs("mediapipeline.desktop.network.mdns", level="WARNING") as logs:
            advertiser.stop()

        output = "\n".join(logs.output)
        self.assertIn("failed to unregister coordinator service", output)
        self.assertIn("unregister failed", output)
        self.assertIn("failed to close Zeroconf instance", output)
        self.assertIn("close failed", output)
        self.assertIsNone(advertiser._zc)
        self.assertIsNone(advertiser._info)

    def test_advertiser_start_registration_failure_clears_partial_state(self) -> None:
        class FakeServiceInfo:
            def __init__(self, *_args: object, **_kwargs: object) -> None:
                return None

        class FailingRegisterZeroconf:
            def __init__(self) -> None:
                self.closed = False

            def register_service(self, _info: object) -> None:
                raise RuntimeError("register denied")

            def close(self) -> None:
                self.closed = True

        zc = FailingRegisterZeroconf()
        advertiser = mdns.CoordinatorAdvertiser.__new__(mdns.CoordinatorAdvertiser)
        advertiser._port = 7830
        advertiser._zc = None
        advertiser._info = None

        with (
            patch("mediapipeline.desktop.network.mdns._get_local_ip", return_value="127.0.0.1"),
            patch("mediapipeline.desktop.network.mdns.ServiceInfo", FakeServiceInfo),
            patch("mediapipeline.desktop.network.mdns.Zeroconf", return_value=zc),
            self.assertLogs("mediapipeline.desktop.network.mdns", level="ERROR") as logs,
        ):
            self.assertFalse(advertiser.start())

        self.assertTrue(zc.closed)
        self.assertIsNone(advertiser._zc)
        self.assertIsNone(advertiser._info)
        output = "\n".join(logs.output)
        self.assertIn("mDNS: failed to register coordinator service.", output)
        self.assertIn("register denied", output)

    def test_advertiser_start_skips_loopback_bind_address(self) -> None:
        advertiser = mdns.CoordinatorAdvertiser.__new__(mdns.CoordinatorAdvertiser)
        advertiser._port = 7830
        advertiser._bind_address = "127.0.0.1"
        advertiser._zc = None
        advertiser._info = None
        advertiser.skipped = False
        advertiser.skip_reason = ""

        with (
            patch("mediapipeline.desktop.network.mdns.ServiceInfo", side_effect=AssertionError("loopback should not advertise")),
            patch("mediapipeline.desktop.network.mdns.Zeroconf", side_effect=AssertionError("loopback should not open zeroconf")),
            self.assertLogs("mediapipeline.desktop.network.mdns", level="INFO") as logs,
        ):
            self.assertFalse(advertiser.start())

        self.assertTrue(advertiser.skipped)
        self.assertIn("127.0.0.1", advertiser.skip_reason)
        self.assertIn("not advertised via mDNS", "\n".join(logs.output))

    def test_advertiser_start_uses_specific_lan_bind_address(self) -> None:
        captured: list[dict[str, object]] = []

        class FakeServiceInfo:
            def __init__(self, **kwargs: object) -> None:
                captured.append(kwargs)

        class FakeZeroconf:
            def register_service(self, _info: object) -> None:
                return None

        advertiser = mdns.CoordinatorAdvertiser.__new__(mdns.CoordinatorAdvertiser)
        advertiser._port = 7830
        advertiser._bind_address = "192.168.1.25"
        advertiser._zc = None
        advertiser._info = None
        advertiser.skipped = False
        advertiser.skip_reason = ""

        with (
            patch("mediapipeline.desktop.network.mdns._get_local_ip", side_effect=AssertionError("specific bind should be advertised directly")),
            patch("mediapipeline.desktop.network.mdns.ServiceInfo", FakeServiceInfo),
            patch("mediapipeline.desktop.network.mdns.Zeroconf", FakeZeroconf),
        ):
            self.assertTrue(advertiser.start())

        self.assertEqual(mdns.socket.inet_ntoa(captured[0]["addresses"][0]), "192.168.1.25")

    def test_advertiser_start_uses_primary_ip_for_wildcard_bind_address(self) -> None:
        captured: list[dict[str, object]] = []

        class FakeServiceInfo:
            def __init__(self, **kwargs: object) -> None:
                captured.append(kwargs)

        class FakeZeroconf:
            def register_service(self, _info: object) -> None:
                return None

        advertiser = mdns.CoordinatorAdvertiser.__new__(mdns.CoordinatorAdvertiser)
        advertiser._port = 7830
        advertiser._bind_address = "0.0.0.0"
        advertiser._zc = None
        advertiser._info = None
        advertiser.skipped = False
        advertiser.skip_reason = ""

        with (
            patch("mediapipeline.desktop.network.mdns._get_local_ip", return_value="192.168.1.50"),
            patch("mediapipeline.desktop.network.mdns.ServiceInfo", FakeServiceInfo),
            patch("mediapipeline.desktop.network.mdns.Zeroconf", FakeZeroconf),
        ):
            self.assertTrue(advertiser.start())

        self.assertEqual(mdns.socket.inet_ntoa(captured[0]["addresses"][0]), "192.168.1.50")

    def test_discovery_logs_zeroconf_close_failure(self) -> None:
        class FailingCloseZeroconf:
            def close(self) -> None:
                raise RuntimeError("discovery close failed")

        class FakeBrowser:
            def __init__(self, *_args: object, **_kwargs: object) -> None:
                pass

        old_available = mdns._ZEROCONF_AVAILABLE
        old_zeroconf = mdns.Zeroconf
        old_browser = mdns.ServiceBrowser
        try:
            mdns._ZEROCONF_AVAILABLE = True
            mdns.Zeroconf = FailingCloseZeroconf  # type: ignore[assignment]
            mdns.ServiceBrowser = FakeBrowser  # type: ignore[assignment]
            with self.assertLogs("mediapipeline.desktop.network.mdns", level="WARNING") as logs:
                urls = mdns.discover_coordinators(timeout_secs=0.0)
        finally:
            mdns._ZEROCONF_AVAILABLE = old_available
            mdns.Zeroconf = old_zeroconf  # type: ignore[assignment]
            mdns.ServiceBrowser = old_browser  # type: ignore[assignment]

        self.assertEqual(urls, [])
        output = "\n".join(logs.output)
        self.assertIn("mDNS discovery: failed to close Zeroconf instance", output)
        self.assertIn("discovery close failed", output)

    def test_discovery_logs_service_resolution_failure(self) -> None:
        added_state = object()

        class FakeServiceStateChange:
            Added = added_state

        class FailingResolveZeroconf:
            def get_service_info(self, _service_type: str, _name: str, timeout: int = 0) -> object:
                raise RuntimeError(f"resolve failed after {timeout}ms")

            def close(self) -> None:
                return None

        class FakeBrowser:
            def __init__(self, zc: object, service_type: str, handlers: list[object]) -> None:
                handlers[0](zc, service_type, "Broken Coordinator._mediapipeline._tcp.local.", added_state)  # type: ignore[index,operator]

        old_available = mdns._ZEROCONF_AVAILABLE
        old_zeroconf = mdns.Zeroconf
        old_browser = mdns.ServiceBrowser
        old_state_change = mdns.ServiceStateChange
        try:
            mdns._ZEROCONF_AVAILABLE = True
            mdns.Zeroconf = FailingResolveZeroconf  # type: ignore[assignment]
            mdns.ServiceBrowser = FakeBrowser  # type: ignore[assignment]
            mdns.ServiceStateChange = FakeServiceStateChange  # type: ignore[assignment]
            with self.assertLogs("mediapipeline.desktop.network.mdns", level="WARNING") as logs:
                urls = mdns.discover_coordinators(timeout_secs=0.0)
        finally:
            mdns._ZEROCONF_AVAILABLE = old_available
            mdns.Zeroconf = old_zeroconf  # type: ignore[assignment]
            mdns.ServiceBrowser = old_browser  # type: ignore[assignment]
            mdns.ServiceStateChange = old_state_change  # type: ignore[assignment]

        self.assertEqual(urls, [])
        output = "\n".join(logs.output)
        self.assertIn("mDNS discovery: error resolving Broken Coordinator._mediapipeline._tcp.local.", output)
        self.assertIn("continuing scan", output)
        self.assertIn("resolve failed after 2000ms", output)


class NetworkCoordinatorDiscoveryCommandTests(unittest.TestCase):
    def test_worker_discovery_command_returns_selectable_mdns_urls_without_media_touch(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            facade = MediaPipelineApplicationFacade(DummyFacadeService(root), app_version="v6-test")
            resolved = _resolved(root, {"NetworkRole": "worker"})

            with patch(
                "mediapipeline.core.network.facade.discover_coordinators",
                return_value=["http://coordinator.test:7830", "http://coordinator.test:7830", "bad-url"],
            ) as discover:
                result = facade.request_network_worker_discover_coordinators(
                    resolved,
                    {"timeout_seconds": 0.25},
                ).to_mapping()

        discover.assert_called_once_with(timeout_secs=0.25)
        self.assertTrue(result["ok"])
        self.assertEqual(result["command"], "network.worker.discover_coordinators")
        self.assertEqual(result["data"]["schema_version"], "desktop_network_coordinator_discovery.v1")
        self.assertTrue(result["data"]["suppress_command_journal"])
        self.assertEqual(result["data"]["effect"], "none")
        self.assertEqual(result["data"]["count"], 1)
        self.assertEqual(
            result["data"]["coordinators"],
            [
                {
                    "url": "http://coordinator.test:7830",
                    "host": "coordinator.test",
                    "port": 7830,
                    "source": "mdns",
                    "selectable": True,
                }
            ],
        )
        self.assertIn("source_media", result["data"]["would_not_touch"])
        self.assertIn("bad-url", "\n".join(result.get("warnings", [])))

    def test_worker_discovery_command_reports_missing_zeroconf_without_crashing(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            facade = MediaPipelineApplicationFacade(DummyFacadeService(root), app_version="v6-test")
            resolved = _resolved(root, {"NetworkRole": "worker"})

            with patch(
                "mediapipeline.core.network.facade.discover_coordinators",
                side_effect=mdns.ZeroconfUnavailable("zeroconf not installed"),
            ):
                result = facade.request_network_worker_discover_coordinators(resolved, {}).to_mapping()

        self.assertFalse(result["ok"])
        self.assertEqual(result["severity"], "warning")
        self.assertEqual(result["data"]["coordinators"], [])
        self.assertFalse(result["data"]["zeroconf_available"])
        self.assertIn("zeroconf not installed", "\n".join(result["warnings"]))

    def test_local_api_worker_discovery_route_is_unjournaled(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            resolved = _resolved(root, {"NetworkRole": "worker"})
            facade = MediaPipelineApplicationFacade(DummyFacadeService(root), app_version="v6-test")
            server = LocalApiServer(
                facade,
                token="network-discovery-token",
                resolved_provider=lambda: resolved,
                audit_root_provider=lambda: str(root),
            )
            try:
                server.start()
                with patch(
                    "mediapipeline.core.network.facade.discover_coordinators",
                    return_value=["http://coordinator.test:7830"],
                ):
                    status, payload = _post_json(
                        f"{server.url}/api/network/worker/discover-coordinators",
                        {"timeout_seconds": 0.1},
                        token=server.token,
                    )
                commands_status, commands = _get_json(f"{server.url}/api/commands?limit=5", token=server.token)
            finally:
                server.stop()

        self.assertEqual(status, 200)
        self.assertTrue(payload["ok"])
        self.assertTrue(payload["data"]["suppress_command_journal"])
        self.assertEqual(payload["data"]["coordinators"][0]["url"], "http://coordinator.test:7830")
        self.assertEqual(commands_status, 200)
        self.assertEqual(commands["entries"], [])


if __name__ == "__main__":
    unittest.main()
