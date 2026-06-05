from __future__ import annotations

import sys
import unittest
from pathlib import Path

from mediapipeline.tools.paths import find_repo_root

sys.path.insert(0, str(find_repo_root(Path(__file__)) / "src"))

from mediapipeline.desktop.api.static_files import render_index


REPO_ROOT = find_repo_root(Path(__file__))
STATIC_ROOT = REPO_ROOT / "apps" / "desktop" / "webview" / "static"
ASSETS_ROOT = STATIC_ROOT / "assets"


def _render_html() -> str:
    response = render_index(
        STATIC_ROOT,
        {"token": "ledger-static-token", "appVersion": "v5-test", "shellSurface": "webview"},
    )
    if response.status != 200:
        raise AssertionError(f"index render failed with status {response.status}: {response.body!r}")
    return response.body.decode("utf-8")


class WebViewMaintenanceChangeLedgerStaticTests(unittest.TestCase):
    def test_maintenance_page_contains_read_only_change_ledger_panels(self) -> None:
        html = _render_html()

        self.assertIn("Change Ledger Summary", html)
        self.assertIn("Selected Change Detail", html)
        self.assertIn("Changelog Hygiene", html)
        self.assertIn('id="maintenance-change-ledger-refresh-button"', html)
        self.assertIn('id="maintenance-change-ledger-status-filter"', html)
        self.assertIn('id="maintenance-change-ledger-rows"', html)
        self.assertIn('id="maintenance-change-ledger-detail"', html)
        self.assertIn('id="maintenance-change-ledger-hygiene"', html)

    def test_maintenance_view_uses_read_only_get_route_and_namespace_exports(self) -> None:
        source = (ASSETS_ROOT / "maintenanceView.js").read_text(encoding="utf-8")

        self.assertIn('apiGet("/api/maintenance/change-ledger")', source)
        self.assertNotIn('apiPost("/api/maintenance/change-ledger"', source)
        self.assertIn("function renderChangeLedger", source)
        self.assertIn("function renderChangeLedgerRows", source)
        self.assertIn("function renderChangeLedgerDetail", source)
        self.assertIn("function renderChangeLedgerHygiene", source)
        self.assertIn("function refreshChangeLedger", source)
        self.assertIn("window.mediaPipelineMaintenanceView", source)
        self.assertIn("renderChangeLedger,", source)
        self.assertIn("refreshChangeLedger,", source)
        self.assertIn("changeLedgerCoverage,", source)
        self.assertIn("changeLedgerUnrecordedPaths,", source)
        self.assertIn("Coverage review", source)
        self.assertIn("Unrecorded changed files:", source)
        self.assertIn("coverage.uncovered_paths", source)
        self.assertIn("this panel never writes packets", source)
        self.assertIn("Root CHANGELOG.md remains the canonical human changelog.", source)

    def test_maintenance_view_treats_running_process_guard_as_active_not_blocked(self) -> None:
        source = (ASSETS_ROOT / "maintenanceView.js").read_text(encoding="utf-8")

        self.assertIn('item.status === "running" ? "running" : "blocked"', source)
        self.assertIn('item?.status !== "running"', source)
        self.assertIn('if (readiness === "Active") return "Active";', source)
        self.assertIn("Active process guard rows:", source)


if __name__ == "__main__":
    unittest.main()
