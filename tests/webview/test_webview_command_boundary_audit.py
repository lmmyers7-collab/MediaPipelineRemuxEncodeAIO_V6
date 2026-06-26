from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path

from mediapipeline.tools.paths import find_repo_root

sys.path.insert(0, str(find_repo_root(Path(__file__)) / "src"))

from mediapipeline.desktop.api.contract import LOCAL_API_ROUTE_CONTRACT


REPO_ROOT = find_repo_root(Path(__file__))
AUDIT_SCRIPT = REPO_ROOT / "ops" / "scripts" / "dev" / "check-webview-command-boundary.mjs"
AUDIT_REPORT = REPO_ROOT / "docs" / "generated" / "WEBVIEW_COMMAND_BOUNDARY_AUDIT.json"


def _load_report() -> dict[str, object]:
    return json.loads(AUDIT_REPORT.read_text(encoding="utf-8"))


def _contract_routes() -> set[tuple[str, str]]:
    return {
        (str(route.get("method", "")).upper(), str(route["path"]))
        for route in LOCAL_API_ROUTE_CONTRACT
    }


class WebViewCommandBoundaryAuditTests(unittest.TestCase):
    def test_generated_audit_is_current_and_clean(self) -> None:
        try:
            result = subprocess.run(
                ["node", str(AUDIT_SCRIPT), "--check"],
                cwd=REPO_ROOT,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=120,
                check=False,
            )
        except FileNotFoundError:
            self.skipTest("Node.js is required for the WebView command-boundary audit")

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

        report = _load_report()
        self.assertEqual(report["schema_version"], "webview_command_boundary_audit.v1")
        self.assertTrue(report["ok"], report["violations"])
        self.assertEqual(report["violations"], [])

    def test_every_action_like_control_is_classified(self) -> None:
        report = _load_report()
        summary = report["summary"]
        controls = report["controls"]

        self.assertGreaterEqual(len(controls), 400)
        self.assertEqual(summary["unclassified_high_risk_controls"], 0)

        invalid = []
        for control in controls:
            classification = str(control["classification"])
            if classification.startswith(("backend-", "local-")):
                continue
            if classification == "disabled-future-network-control":
                continue
            invalid.append(
                f"{control.get('page')}:{control.get('tag')}#{control.get('id')}: {classification}"
            )
        self.assertEqual(invalid, [])

    def test_route_usages_match_local_api_contract_and_owners(self) -> None:
        report = _load_report()
        contract_routes = _contract_routes()
        missing = []
        owner_mismatches = []

        for usage in report["route_usages"]:
            route_key = (str(usage["method"]), str(usage["normalized_route"]))
            if route_key not in contract_routes:
                missing.append(f"{usage['file']}:{usage['line']} -> {route_key}")
            if not usage["owner_ok"]:
                owner_mismatches.append(
                    f"{usage['file']}:{usage['line']} -> {usage['normalized_route']}"
                )

        self.assertEqual(missing, [])
        self.assertEqual(owner_mismatches, [])

    def test_high_risk_route_usages_are_backend_owned_effects(self) -> None:
        report = _load_report()
        high_risk = [
            usage
            for usage in report["route_usages"]
            if usage.get("high_risk_effect")
        ]

        self.assertGreaterEqual(len(high_risk), 40)
        self.assertTrue(all(usage["contract_found"] for usage in high_risk))
        self.assertTrue(all(usage["owner_ok"] for usage in high_risk))
        self.assertTrue(all(usage["contract_effect"] for usage in high_risk))

        effects = {str(usage["contract_effect"]) for usage in high_risk}
        self.assertIn("config-write", effects)
        self.assertIn("filesystem-mutation", effects)
        self.assertIn("process-launch", effects)
        self.assertIn("queue-state-write", effects)

    def test_dynamic_api_post_dispatch_is_only_network_lifecycle(self) -> None:
        report = _load_report()
        dynamic_posts = report["dynamic_api_posts"]

        self.assertEqual(len(dynamic_posts), 1)
        dynamic_post = dynamic_posts[0]
        self.assertIn(
            dynamic_post["file"],
            {
                "apps/desktop/webview/static/assets/networkView.js",
                "apps/desktop/webview/static/assets/network/lifecycle.commands.js",
                "apps/desktop/webview/static/assets/network/setup.commands.js",
            },
        )
        self.assertTrue(dynamic_post["allowed"])
        self.assertEqual(
            dynamic_post["reason"],
            "contract-driven Network lifecycle dispatch",
        )
