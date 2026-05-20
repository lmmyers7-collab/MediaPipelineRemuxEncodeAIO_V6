from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from mediapipeline_desktop_app.network import mdns


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
            patch("mediapipeline_desktop_app.network.mdns.threading.Thread", BadThread),
            self.assertLogs("mediapipeline_desktop_app.network.mdns", level="WARNING") as logs,
        ):
            with self.assertRaisesRegex(RuntimeError, "Could not start mDNS discovery thread"):
                mdns.discover_coordinators_async(callbacks.append, timeout_secs=0.0)

        self.assertEqual(callbacks, [])
        self.assertIn("mDNS async discovery thread failed to start: thread denied", "\n".join(logs.output))

    def test_async_discovery_callback_failure_is_logged(self) -> None:
        def fail_callback(_urls: list[str]) -> None:
            raise RuntimeError("callback failed")

        with self.assertLogs("mediapipeline_desktop_app.network.mdns", level="ERROR") as logs:
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

        with self.assertLogs("mediapipeline_desktop_app.network.mdns", level="WARNING") as logs:
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
            patch("mediapipeline_desktop_app.network.mdns._get_local_ip", return_value="127.0.0.1"),
            patch("mediapipeline_desktop_app.network.mdns.ServiceInfo", FakeServiceInfo),
            patch("mediapipeline_desktop_app.network.mdns.Zeroconf", return_value=zc),
            self.assertLogs("mediapipeline_desktop_app.network.mdns", level="ERROR") as logs,
        ):
            self.assertFalse(advertiser.start())

        self.assertTrue(zc.closed)
        self.assertIsNone(advertiser._zc)
        self.assertIsNone(advertiser._info)
        output = "\n".join(logs.output)
        self.assertIn("mDNS: failed to register coordinator service.", output)
        self.assertIn("register denied", output)

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
            with self.assertLogs("mediapipeline_desktop_app.network.mdns", level="WARNING") as logs:
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
            with self.assertLogs("mediapipeline_desktop_app.network.mdns", level="WARNING") as logs:
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


if __name__ == "__main__":
    unittest.main()
