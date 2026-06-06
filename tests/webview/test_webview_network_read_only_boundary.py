from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path

from mediapipeline.tools.paths import find_repo_root

sys.path.insert(0, str(find_repo_root(Path(__file__)) / "src"))

from mediapipeline.desktop.api.contract import LOCAL_API_ROUTE_CONTRACT
from mediapipeline.desktop.api.static_files import render_index

REPO_ROOT = find_repo_root(Path(__file__))
STATIC_ROOT = REPO_ROOT / "apps" / "desktop" / "webview" / "static"
INDEX_HTML = STATIC_ROOT / "index.html"
NETWORK_JS = STATIC_ROOT / "assets" / "networkView.js"


def _network_page_html() -> str:
    response = render_index(
        STATIC_ROOT,
        {"token": "network-test-token", "appVersion": "v6-test", "shellSurface": "webview"},
    )
    if response.status != 200:
        raise AssertionError(f"index render failed with status {response.status}: {response.body!r}")
    html = response.body.decode("utf-8")
    start = html.index('<section class="page" data-page-panel="network">')
    end = html.index('<section class="page" data-page-panel="maintenance">', start)
    return html[start:end]


def _button_labels_and_attrs(html: str) -> list[tuple[str, str]]:
    rows: list[tuple[str, str]] = []
    for match in re.finditer(r"<button\b(?P<attrs>[^>]*)>(?P<label>.*?)</button>", html, flags=re.DOTALL | re.IGNORECASE):
        label = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", match.group("label"))).strip()
        rows.append((label, match.group("attrs")))
    return rows


def _h2_texts(html: str) -> list[str]:
    rows: list[str] = []
    for match in re.finditer(r"<h2\b[^>]*>(?P<label>.*?)</h2>", html, flags=re.DOTALL | re.IGNORECASE):
        label = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", match.group("label"))).strip()
        rows.append(label)
    return rows


class WebViewNetworkReadOnlyBoundaryTests(unittest.TestCase):
    def test_workers_page_uses_evidence_first_panel_order(self) -> None:
        headings = _h2_texts(_network_page_html())

        self.assertEqual(
            headings,
            [
                "Mode Summary",
                "Readiness + Lifecycle Boundary",
                "Persisted Worker State",
                "Saved Worker Mode Settings Medium Impact",
                "Network Config",
                "Open History",
                "Lifecycle Handoff",
                "Evidence Checklist",
                "State Files",
                "API Contract",
            ],
        )

    def test_workers_page_distinguishes_saved_and_persisted_state_labels(self) -> None:
        network_html = _network_page_html()

        for expected in (
            "Saved Role",
            "Mode Model",
            "Lifecycle Boundary",
            "Workers Route Summary",
            "Persisted Worker State",
            "Last Reported Worker Progress",
            "Saved Worker Mode Settings",
            "Staged Patch: none",
        ):
            self.assertIn(expected, network_html)

    def test_workers_api_contract_detail_is_advanced_only(self) -> None:
        network_html = _network_page_html()
        first_advanced = network_html.index("data-advanced")

        self.assertLess(network_html.index("Workers Route Summary"), first_advanced)
        self.assertGreater(network_html.index("<h2>API Contract</h2>"), first_advanced)
        self.assertRegex(
            network_html,
            r'<section class="panel" data-advanced data-panel-type="evidence">\s*'
            r'<div class="panel-heading">\s*<h2>API Contract</h2>',
        )

    def test_workers_page_buttons_are_diagnostics_or_settings_only(self) -> None:
        buttons = _button_labels_and_attrs(_network_page_html())

        self.assertEqual(
            [label for label, _attrs in buttons],
            [
                "Open Run Logs",
                "Open Cluster Log",
                "Open Active Jobs",
                "Open Config",
                "Open State Folder",
                "Stage Worker Settings",
                "Reset From Current",
                "Preview Settings Patch",
                "Save Worker Settings",
            ],
        )
        for _label, attrs in buttons[:5]:
            self.assertIn("data-open-diagnostics=", attrs)
            self.assertNotIn("id=", attrs)
        allowed_setting_ids = {
            'id="settings-network-apply-button"',
            'id="settings-network-reset-button"',
            'id="network-settings-preview-button"',
            'id="network-settings-save-button"',
        }
        for _label, attrs in buttons[5:]:
            self.assertTrue(any(item in attrs for item in allowed_setting_ids), attrs)
            self.assertNotIn("data-open-diagnostics=", attrs)

    def test_workers_page_has_no_lifecycle_or_mutation_control_attributes(self) -> None:
        network_html = _network_page_html()
        forbidden = re.compile(
            r"(?:id|data-[\w-]+)=\"[^\"]*"
            r"(?:start|stop|promote|demote|reclaim|release|abort|retry|delete|drain|publish|rename)"
            r"[^\"]*\"",
            flags=re.IGNORECASE,
        )

        self.assertEqual(forbidden.findall(network_html), [])

    def test_network_view_js_does_not_own_command_routes(self) -> None:
        source = NETWORK_JS.read_text(encoding="utf-8")

        self.assertNotRegex(source, r"\bapiPost\s*\(")
        self.assertNotRegex(source, r"\bfetch\s*\(")
        self.assertNotRegex(source, r"/api/network/(?!workers\b)")
        self.assertIn("Lifecycle controls remain backend-owned", source)
        self.assertIn("network_lifecycle_contracts", source)
        self.assertIn("design_only_no_lifecycle_routes", source)
        self.assertIn("Mutation guardrail", source)

    def test_network_view_js_does_not_render_auth_token_settings(self) -> None:
        source = NETWORK_JS.read_text(encoding="utf-8")

        self.assertNotIn("CoordinatorAuthToken", source)
        self.assertNotIn("WorkerAuthToken", source)
        self.assertNotIn("Coordinator auth token:", source)
        self.assertNotIn("Worker auth token:", source)
        self.assertIn("backend-owned secret, not displayed by WebView", source)

    def test_local_api_network_routes_are_read_only(self) -> None:
        network_routes = [
            (str(route["method"]).upper(), str(route["path"]), str(route.get("effect", "")))
            for route in LOCAL_API_ROUTE_CONTRACT
            if str(route["path"]).startswith("/api/network")
        ]

        self.assertEqual(network_routes, [("GET", "/api/network/workers", "none")])


if __name__ == "__main__":
    unittest.main()
