from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from mediapipeline_desktop_app.network import local_ip


class LocalIpPolicyTests(unittest.TestCase):
    def test_primary_local_ip_prefers_home_lan_over_vpn_ordering(self) -> None:
        candidates = ["10.20.30.40", "172.20.1.2", "192.168.1.50"]
        self.assertEqual(local_ip.get_primary_local_ip(candidates), "192.168.1.50")

    def test_get_all_local_ips_filters_loopback_linklocal_and_invalid_values(self) -> None:
        with patch.object(local_ip.socket, "gethostname", return_value="host"), patch.object(
            local_ip.socket,
            "gethostbyname_ex",
            return_value=("host", [], ["127.0.0.1", "169.254.1.2", "192.168.1.20", "not-an-ip"]),
        ), self.assertLogs("mediapipeline_desktop_app.network.local_ip", level="DEBUG") as logs:
            result = local_ip.get_all_local_ips()

        self.assertEqual(result, ["192.168.1.20"])
        self.assertIn("Ignoring invalid local IPv4 candidate", "\n".join(logs.output))

    def test_get_all_local_ips_logs_hostname_lookup_failure(self) -> None:
        with (
            patch.object(local_ip.socket, "gethostname", return_value="host"),
            patch.object(local_ip.socket, "gethostbyname_ex", side_effect=OSError("dns unavailable")),
            self.assertLogs("mediapipeline_desktop_app.network.local_ip", level="WARNING") as logs,
        ):
            self.assertEqual(local_ip.get_all_local_ips(), [])

        self.assertIn("Local IPv4 hostname lookup failed: dns unavailable", "\n".join(logs.output))

    def test_primary_local_ip_falls_back_when_udp_detection_fails(self) -> None:
        class FailingSocket:
            def __enter__(self) -> "FailingSocket":
                return self

            def __exit__(self, *_args: object) -> None:
                return None

            def settimeout(self, _timeout: float) -> None:
                return None

            def connect(self, _target: tuple[str, int]) -> None:
                raise OSError("route unavailable")

        with (
            patch.object(local_ip.socket, "socket", return_value=FailingSocket()),
            self.assertLogs("mediapipeline_desktop_app.network.local_ip", level="WARNING") as logs,
        ):
            self.assertEqual(
                local_ip.get_primary_local_ip(["203.0.113.10"], empty_fallback=""),
                "203.0.113.10",
            )
            self.assertEqual(local_ip.get_primary_local_ip([], empty_fallback=""), "")

        self.assertIn("UDP route local IPv4 detection failed", "\n".join(logs.output))


if __name__ == "__main__":
    unittest.main()
