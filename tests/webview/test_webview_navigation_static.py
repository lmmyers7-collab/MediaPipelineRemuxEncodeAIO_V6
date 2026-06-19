"""
Static navigation structure tests for the WebView single-page shell.

Parses the Local API rendered index template — no browser, no Node.js, no subprocess.
Verifies nav button structure, page panel presence, initial active state,
and cross-page navigation target validity.

Does not test JavaScript execution, CSS rendering, or runtime page switching.
"""
from __future__ import annotations

import pathlib
import re
import sys
import unittest
from html.parser import HTMLParser
from pathlib import Path

from mediapipeline.tools.paths import find_repo_root

sys.path.insert(0, str(find_repo_root(Path(__file__)) / "src"))

from mediapipeline.desktop.api.static_files import render_index


_STATIC_ROOT = find_repo_root(Path(__file__)) / "apps" / "desktop" / "webview" / "static"
_INDEX_HTML = _STATIC_ROOT / "index.html"

_EXPECTED_NAV_PAGES = [
    "home",
    "launch",
    "live",
    "metrics",
    "queue",
    "completed",
    "pending",
    "rename",
    "reports",
    "network",
    "libraries",
    "schedule",
    "settings",
    "diagnostics",
    "maintenance",
]

_EXPECTED_PAGE_PANELS = _EXPECTED_NAV_PAGES

_EXPECTED_NAV_LABELS = {
    "home": "Home",
    "launch": "Launch",
    "live": "Telemetry",
    "metrics": "Metrics",
    "queue": "Queue",
    "completed": "Completed Output",
    "pending": "Pending Publish",
    "rename": "Rename",
    "reports": "Reports",
    "network": "Network Workers",
    "libraries": "Libraries",
    "schedule": "Schedule",
    "settings": "Settings",
    "diagnostics": "Diagnostics",
    "maintenance": "Maintenance",
}

_INITIAL_ACTIVE_PAGE = "home"
_VOID_TAGS = {
    "area",
    "base",
    "br",
    "col",
    "embed",
    "hr",
    "img",
    "input",
    "link",
    "meta",
    "param",
    "source",
    "track",
    "wbr",
}


class _NavParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.nav_buttons: list[dict] = []
        self.page_panels: list[dict] = []
        self.cross_page_targets: list[str] = []
        self._in_nav = False
        self._current_button: dict | None = None
        self._current_text: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr_dict = dict(attrs)
        if tag == "nav" and "nav" in (attr_dict.get("class") or "").split():
            self._in_nav = True
        if tag == "button":
            classes = (attr_dict.get("class") or "").split()
            data_page = attr_dict.get("data-page")
            cross_target = attr_dict.get("data-cross-page-target")
            if "nav-button" in classes and data_page:
                self._current_button = {
                    "page": data_page,
                    "classes": classes,
                    "label": "",
                }
                self._current_text = []
            if cross_target:
                self.cross_page_targets.append(cross_target)
        if tag == "section":
            data_panel = attr_dict.get("data-page-panel")
            if data_panel:
                classes = (attr_dict.get("class") or "").split()
                self.page_panels.append({"panel": data_panel, "classes": classes})

    def handle_endtag(self, tag: str) -> None:
        if tag == "nav":
            self._in_nav = False
        if tag == "button" and self._current_button is not None:
            self._current_button["label"] = "".join(self._current_text).strip()
            self.nav_buttons.append(self._current_button)
            self._current_button = None
            self._current_text = []

    def handle_data(self, data: str) -> None:
        if self._current_button is not None:
            self._current_text.append(data)


def _parse_index() -> _NavParser:
    parser = _NavParser()
    response = render_index(
        _STATIC_ROOT,
        {"token": "nav-test-token", "appVersion": "v5-test", "shellSurface": "webview"},
    )
    if response.status != 200:
        raise AssertionError(f"index render failed with status {response.status}: {response.body!r}")
    parser.feed(response.body.decode("utf-8"))
    return parser


class _PanelLayoutParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.stack: list[tuple[str, list[str], dict[str, str | None]]] = []
        self.panel_headings_by_page: dict[str, list[str]] = {}
        self._panel_stack: list[dict[str, object]] = []
        self._heading_panel: dict[str, object] | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr_dict = dict(attrs)
        classes = (attr_dict.get("class") or "").split()
        if tag not in _VOID_TAGS:
            self.stack.append((tag, classes, attr_dict))
        if tag == "section" and "panel" in classes:
            parent = self.stack[-2] if len(self.stack) >= 2 else None
            page_id = parent[2].get("data-page-panel") if parent and parent[0] == "section" else None
            direct = bool(page_id and "page" in parent[1])
            panel = {"direct": direct, "page": page_id, "heading": ""}
            self._panel_stack.append(panel)
            if direct and isinstance(page_id, str):
                self.panel_headings_by_page.setdefault(page_id, []).append("")
        if tag in {"h2", "h3"} and self._panel_stack:
            panel = self._panel_stack[-1]
            if not panel.get("heading"):
                self._heading_panel = panel

    def handle_endtag(self, tag: str) -> None:
        if tag in {"h2", "h3"}:
            self._heading_panel = None
        if tag == "section" and self.stack:
            while self.stack:
                item = self.stack.pop()
                if item[0] == "section":
                    if "panel" in item[1] and self._panel_stack:
                        self._panel_stack.pop()
                    break
        elif tag not in _VOID_TAGS and self.stack:
            while self.stack:
                item = self.stack.pop()
                if item[0] == tag:
                    break

    def handle_data(self, data: str) -> None:
        if self._heading_panel is None:
            return
        text = data.strip()
        if not text:
            return
        self._heading_panel["heading"] = f"{self._heading_panel.get('heading', '')}{text}"
        if self._heading_panel.get("direct"):
            page_id = self._heading_panel.get("page")
            if isinstance(page_id, str) and self.panel_headings_by_page.get(page_id):
                self.panel_headings_by_page[page_id][-1] = str(self._heading_panel["heading"])


def _parse_panel_layout() -> _PanelLayoutParser:
    parser = _PanelLayoutParser()
    response = render_index(
        _STATIC_ROOT,
        {"token": "panel-layout-test-token", "appVersion": "v5-test", "shellSurface": "webview"},
    )
    if response.status != 200:
        raise AssertionError(f"index render failed with status {response.status}: {response.body!r}")
    parser.feed(response.body.decode("utf-8"))
    return parser


class WebViewNavigationStaticTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.parsed = _parse_index()

    def test_index_html_exists(self) -> None:
        self.assertTrue(_INDEX_HTML.exists(), f"index.html not found at {_INDEX_HTML}")

    def test_all_expected_nav_pages_have_buttons(self) -> None:
        button_pages = [b["page"] for b in self.parsed.nav_buttons]
        for page in _EXPECTED_NAV_PAGES:
            self.assertIn(page, button_pages, f"Nav button for page '{page}' missing from index.html")

    def test_nav_button_count_matches_expected(self) -> None:
        button_pages = [b["page"] for b in self.parsed.nav_buttons]
        self.assertEqual(
            len(button_pages),
            len(_EXPECTED_NAV_PAGES),
            f"Expected {len(_EXPECTED_NAV_PAGES)} nav buttons, found {len(button_pages)}: {button_pages}",
        )

    def test_no_duplicate_nav_button_pages(self) -> None:
        pages = [b["page"] for b in self.parsed.nav_buttons]
        seen: set[str] = set()
        for page in pages:
            self.assertNotIn(page, seen, f"Duplicate nav button for page '{page}'")
            seen.add(page)

    def test_nav_button_labels_match_expected(self) -> None:
        label_map = {b["page"]: b["label"] for b in self.parsed.nav_buttons}
        for page, expected_label in _EXPECTED_NAV_LABELS.items():
            self.assertEqual(
                label_map.get(page),
                expected_label,
                f"Nav button for '{page}' has label {label_map.get(page)!r}, expected {expected_label!r}",
            )

    def test_all_expected_nav_pages_have_panels(self) -> None:
        panel_pages = [p["panel"] for p in self.parsed.page_panels]
        for page in _EXPECTED_PAGE_PANELS:
            self.assertIn(page, panel_pages, f"Page panel for '{page}' missing from index.html")

    def test_no_duplicate_page_panels(self) -> None:
        panels = [p["panel"] for p in self.parsed.page_panels]
        seen: set[str] = set()
        for panel in panels:
            self.assertNotIn(panel, seen, f"Duplicate page panel for '{panel}'")
            seen.add(panel)

    def test_nav_button_pages_and_panels_match(self) -> None:
        button_pages = set(b["page"] for b in self.parsed.nav_buttons)
        panel_pages = set(p["panel"] for p in self.parsed.page_panels)
        self.assertEqual(
            button_pages,
            panel_pages,
            f"Nav button pages and page panels differ.\n"
            f"  Buttons only: {button_pages - panel_pages}\n"
            f"  Panels without primary nav:  {panel_pages - button_pages}",
        )

    def test_initial_active_nav_button_is_home(self) -> None:
        active_buttons = [b["page"] for b in self.parsed.nav_buttons if "is-active" in b["classes"]]
        self.assertEqual(
            active_buttons,
            [_INITIAL_ACTIVE_PAGE],
            f"Expected exactly one initially active nav button ('home'), got: {active_buttons}",
        )

    def test_initial_active_nav_button_has_aria_current(self) -> None:
        response = render_index(
            _STATIC_ROOT,
            {"token": "nav-aria-current-test-token", "appVersion": "v5-test", "shellSurface": "webview"},
        )
        self.assertEqual(response.status, 200)
        html = response.body.decode("utf-8")
        self.assertIn('data-page="home" aria-current="page"', html)
        self.assertEqual(html.count('aria-current="page"'), 1)

    def test_initial_visible_page_panel_is_home(self) -> None:
        visible_panels = [p["panel"] for p in self.parsed.page_panels if "is-visible" in p["classes"]]
        self.assertEqual(
            visible_panels,
            [_INITIAL_ACTIVE_PAGE],
            f"Expected exactly one initially visible page panel ('home'), got: {visible_panels}",
        )

    def test_cross_page_targets_are_valid_page_names(self) -> None:
        valid_pages = set(_EXPECTED_PAGE_PANELS)
        for target in self.parsed.cross_page_targets:
            self.assertIn(
                target,
                valid_pages,
                f"data-cross-page-target='{target}' is not a known nav page",
            )

    def test_nav_element_is_present(self) -> None:
        self.assertGreater(
            len(self.parsed.nav_buttons),
            0,
            "No nav buttons found — nav element may be missing or malformed in index.html",
        )

    def test_page_identity_and_diagnostics_subview_labels_are_canonical(self) -> None:
        response = render_index(
            _STATIC_ROOT,
            {"token": "page-identity-test-token", "appVersion": "v5-test", "shellSurface": "webview"},
        )
        self.assertEqual(response.status, 200)
        html = response.body.decode("utf-8")
        for label in [
            "Home",
            "Launch",
            "Telemetry",
            "Queue",
            "Completed Output",
            "Pending Publish",
            "Rename",
            "Reports",
            "Network Workers",
            "Libraries",
            "Schedule",
            "Settings",
            "Diagnostics",
            "Maintenance",
        ]:
            self.assertIn(f'<h1 class="visually-hidden">{label}</h1>', html)
        self.assertIn("Commands Evidence", html)
        self.assertIn("API Contract Evidence", html)

    def test_completed_selected_output_context_follows_history_table(self) -> None:
        response = render_index(
            _STATIC_ROOT,
            {"token": "completed-selected-output-order-test-token", "appVersion": "v5-test", "shellSurface": "webview"},
        )
        self.assertEqual(response.status, 200)
        html = response.body.decode("utf-8")
        history_legend_index = html.index('id="completed-history-table-legend"')
        selected_context_index = html.index('id="completed-active-output-context"')
        self.assertGreater(selected_context_index, history_legend_index)

    def test_completed_selected_output_context_is_inside_history_panel(self) -> None:
        response = render_index(
            _STATIC_ROOT,
            {"token": "completed-selected-output-tab-test-token", "appVersion": "v5-test", "shellSurface": "webview"},
        )
        self.assertEqual(response.status, 200)
        html = response.body.decode("utf-8")
        history_heading_index = html.index('id="completed-history-summary-heading"')
        history_legend_index = html.index('id="completed-history-table-legend"')
        selected_context_index = html.index('id="completed-active-output-context"')
        next_history_panel_index = html.index("<h2>Output History</h2>")
        self.assertLess(history_heading_index, history_legend_index)
        self.assertLess(history_legend_index, selected_context_index)
        self.assertLess(selected_context_index, next_history_panel_index)

    def test_operational_summary_blocks_are_movable_page_panels(self) -> None:
        layout = _parse_panel_layout().panel_headings_by_page
        expected_by_page = {
            "queue": [
                "Queue Decision",
                "Source Scan And Display Filters",
                "Attention Required",
                "Queue Rows",
                "Selected Row Detail (not launch scope)",
                "Selected Row Diagnostics Links",
                "Backend Launch Scope Boundary",
                "Queue-to-Launch Handoff",
                "Readiness",
                "Queue Summary",
                "Run History",
                "Queue Readiness Checklist",
                "Flagged Items",
                "Collision Risk",
                "Backend-Excluded Source Files",
            ],
            "pending": [
                "Pending Publish Guard Evidence",
                "Pending Publish Drain",
                "Drain Status",
                "Risk Summary",
                "Pending Publish Checklist",
                "Flagged Items",
                "Recovery Preview",
                "Pending Rows",
                "Selected Item",
                "Diagnostics Links",
            ],
            "completed": [
                "Output Trust Decision",
                "Current Output Status",
                "Output Files",
                "Final Library Promotion",
                "Why This Output Looks Different",
                "Completed History Summary",
                "Output History",
                "Integrity Check",
                "Route Summary",
                "Run History",
                "Manifest Check",
                "Output Checklist",
                "Diagnostics Links",
                "Evidence Groups",
                "File And Size Proof",
                "Media And Route Proof",
                "Acceptance Readiness",
                "Acceptance And Evidence Packet",
                "Publish And Pending Proof",
                "Publish Reconciliation",
                "Route Agreement",
            ],
            "maintenance": [
                "Health Progress",
                "Readiness",
                "Tool Status",
                "Health Checks",
                "Check Detail",
            ],
        }
        for page, headings in expected_by_page.items():
            actual = layout.get(page, [])
            for heading in headings:
                self.assertIn(
                    heading,
                    actual,
                    f"Expected '{heading}' to be a direct movable panel on page '{page}'. Found: {actual}",
                )

    def test_dashboard_quick_controls_are_present(self) -> None:
        response = render_index(
            _STATIC_ROOT,
            {"token": "dashboard-controls-test-token", "appVersion": "v5-test", "shellSurface": "webview"},
        )
        self.assertEqual(response.status, 200)
        html = response.body.decode("utf-8")
        for fragment in [
            "Quick Controls",
            "home-quick-controls-panel",
            "home-quick-control-row",
            "home-control-readiness-status",
            "home-refresh-button",
            "home-control-message",
            "Open Completed Output",
            "Open Pending Publish",
            'data-cross-page-target="launch"',
            'data-cross-page-target="completed" data-home-promotion-entry',
            'data-cross-page-target="queue"',
            'data-cross-page-target="pending"',
        ]:
            self.assertIn(fragment, html)
        quick_match = re.search(
            r'<section class="panel home-quick-controls-panel"[^>]*>(.*?)</section>',
            html,
            re.S,
        )
        self.assertIsNotNone(quick_match)
        quick_html = quick_match.group(1)
        self.assertIn('id="home-control-readiness-status" class="visually-hidden"', quick_html)
        self.assertIn('id="home-control-message" class="note visually-hidden"', quick_html)
        self.assertIn('id="home-promotion-entry-message" class="note visually-hidden"', quick_html)
        for removed_fragment in [
            'data-cross-page-target="diagnostics"',
            'data-open-diagnostics="run_logs"',
            'data-open-diagnostics="active_jobs"',
            ">Diagnostics<",
            ">Run Logs<",
            ">Active Jobs<",
        ]:
            self.assertNotIn(removed_fragment, quick_html)
        home_match = re.search(
            r'<section class="page is-visible" data-page-panel="home">(.*?)<section class="page" data-page-panel="live">',
            html,
            re.S,
        )
        self.assertIsNotNone(home_match)
        self.assertNotIn('data-control-action="', home_match.group(1))


if __name__ == "__main__":
    unittest.main()
