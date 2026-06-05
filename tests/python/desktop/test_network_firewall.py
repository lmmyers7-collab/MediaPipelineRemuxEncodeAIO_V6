from __future__ import annotations

import sys
import unittest
from pathlib import Path

from mediapipeline.tools.paths import find_repo_root
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(find_repo_root(Path(__file__)) / "src"))

from mediapipeline.desktop.network.firewall import (
    add_firewall_rule,
    build_add_firewall_rule_command,
    check_firewall_port,
    parse_matching_firewall_rule_names,
)


class NetworkFirewallTests(unittest.TestCase):
    def test_firewall_rule_parser_matches_local_port_blocks(self) -> None:
        output = "\n".join(
            [
                "Rule Name: MediaPipeline Coordinator",
                "Protocol: TCP",
                "LocalPort: 7830",
                "Rule Name: Other Rule",
                "Protocol: TCP",
                "LocalPort: 9000",
            ]
        )

        self.assertEqual(parse_matching_firewall_rule_names(output, 7830), ["MediaPipeline Coordinator"])

    def test_firewall_add_rule_command_keeps_arguments_separate(self) -> None:
        command = build_add_firewall_rule_command(7830, netsh_path=r"C:\Windows\System32\netsh.exe")

        self.assertEqual(command[0], r"C:\Windows\System32\netsh.exe")
        self.assertIn("advfirewall", command)
        self.assertIn("firewall", command)
        self.assertIn("add", command)
        self.assertIn("rule", command)
        self.assertIn("name=MediaPipeline Coordinator (port 7830)", command)
        self.assertIn("localport=7830", command)

    def test_firewall_check_uses_bounded_subprocess_and_reports_match(self) -> None:
        output = "Rule Name: MediaPipeline Coordinator\nProtocol: TCP\nLocalPort: 7830\n"

        with patch(
            "mediapipeline.desktop.network.firewall.subprocess.run",
            return_value=SimpleNamespace(stdout=output, stderr="", returncode=0),
        ) as run:
            result = check_firewall_port(7830)

        self.assertEqual(result.status, "ok")
        self.assertIn("Inbound rule", result.message)
        self.assertFalse(run.call_args.kwargs.get("shell", False))
        self.assertTrue(run.call_args.kwargs["capture_output"])
        self.assertEqual(run.call_args.kwargs["timeout"], 15)

    def test_firewall_check_reports_netsh_nonzero_exit_as_warning(self) -> None:
        with patch(
            "mediapipeline.desktop.network.firewall.subprocess.run",
            return_value=SimpleNamespace(stdout="", stderr="access denied", returncode=1),
        ) as run:
            result = check_firewall_port(7830)

        self.assertEqual(result.status, "warning")
        self.assertIn("Firewall check failed (exit 1)", result.message)
        self.assertIn("show rule", result.message)
        self.assertIn("name=all", result.message)
        self.assertIn("netsh output:", result.message)
        self.assertIn("access denied", result.message)
        self.assertNotIn("No inbound rule", result.message)
        self.assertFalse(run.call_args.kwargs.get("shell", False))
        self.assertEqual(run.call_args.kwargs["timeout"], 15)

    def test_firewall_add_rule_reports_admin_failure_with_manual_command(self) -> None:
        with patch(
            "mediapipeline.desktop.network.firewall.subprocess.run",
            return_value=SimpleNamespace(stdout="", stderr="access denied", returncode=1),
        ) as run:
            result = add_firewall_rule(7830)

        self.assertEqual(result.status, "warning")
        self.assertIn("run as administrator", result.message)
        self.assertIn("localport=7830", result.message)
        self.assertFalse(run.call_args.kwargs.get("shell", False))
        self.assertEqual(run.call_args.kwargs["timeout"], 15)

    def test_firewall_add_rule_nonzero_exit_includes_netsh_output(self) -> None:
        with patch(
            "mediapipeline.desktop.network.firewall.subprocess.run",
            return_value=SimpleNamespace(stdout="rule exists", stderr="access denied", returncode=1),
        ):
            result = add_firewall_rule(7830)

        self.assertEqual(result.status, "warning")
        self.assertIn("Could not add rule (exit 1)", result.message)
        self.assertIn("netsh output:", result.message)
        self.assertIn("access denied", result.message)
        self.assertIn("rule exists", result.message)
