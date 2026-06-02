from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from mediapipeline_desktop_app.api.static_files import render_index

DESKTOP_APP_ROOT = Path(__file__).resolve().parents[1]
STATIC_ROOT = DESKTOP_APP_ROOT / "mediapipeline_desktop_app" / "ui_web" / "static"
ASSETS_ROOT = STATIC_ROOT / "assets"
CSS_PATH = ASSETS_ROOT / "styles.css"
CSS_PATHS = sorted(ASSETS_ROOT.glob("styles*.css"))
DOM_HELPERS_PATH = ASSETS_ROOT / "domHelpers.js"
COMPLETED_VIEW_PATH = ASSETS_ROOT / "completedView.js"
PENDING_VIEW_PATH = ASSETS_ROOT / "pendingPublishView.js"
COMPLETED_TABLE_PATH = ASSETS_ROOT / "completed" / "table.js"
APP_LIFECYCLE_PATH = ASSETS_ROOT / "app" / "lifecycle.js"
APP_LAYOUT_MANAGER_PATH = ASSETS_ROOT / "app" / "layoutManager.js"
LAUNCH_VIEW_PATH = ASSETS_ROOT / "launchView.js"
LAUNCH_PARTIAL_PATH = STATIC_ROOT / "partials" / "page-launch.html"
REPORTS_VIEW_PATH = ASSETS_ROOT / "reportsView.js"
COMPLETED_PARTIAL_PATH = STATIC_ROOT / "partials" / "page-completed.html"
RENAME_PARTIAL_PATH = STATIC_ROOT / "partials" / "page-rename.html"


def _rendered_index_html() -> str:
    response = render_index(STATIC_ROOT, {"token": "test-token", "appVersion": "v5-test"})
    assert response.status == 200
    return response.body.decode("utf-8")


class WebViewCssDesignTokenTests(unittest.TestCase):
    def _css_lines(self) -> list[tuple[str, int, str]]:
        rows: list[tuple[str, int, str]] = []
        for path in CSS_PATHS:
            rows.extend(
                (path.name, line_number, line)
                for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1)
            )
        return rows

    def test_no_raw_colors_outside_custom_property_tokens(self) -> None:
        raw_color = re.compile(r"#[0-9a-fA-F]{3,8}\b|rgba\s*\(|hsla\s*\(")
        raw_hsl = re.compile(r"hsl\s*\(")
        violations: list[str] = []

        for file_name, line_number, line in self._css_lines():
            stripped = line.strip()
            if raw_color.search(line):
                violations.append(f"{file_name}:{line_number}: {line}")
                continue
            if raw_hsl.search(line) and not stripped.startswith("--"):
                violations.append(f"{file_name}:{line_number}: {line}")

        self.assertEqual(violations, [])

    def test_no_raw_font_spacing_or_opacity_de_emphasis(self) -> None:
        font_size = re.compile(r"font-size\s*:")
        spacing = re.compile(r"\b(?:margin|padding|gap)\s*:")
        opacity = re.compile(r"\bopacity\s*:")
        violations: list[str] = []

        for file_name, line_number, line in self._css_lines():
            stripped = line.strip()
            if font_size.search(line) and not stripped.startswith("--text-"):
                if "var(--text-" not in line and "font-size: inherit" not in line:
                    violations.append(f"{file_name}:{line_number}: {line}")
            if spacing.search(line):
                if "var(--space-" not in line and not re.search(r":\s*0(?:[;\s]|$)", line) and "auto" not in line:
                    violations.append(f"{file_name}:{line_number}: {line}")
            if opacity.search(line):
                violations.append(f"{file_name}:{line_number}: {line}")

        self.assertEqual(violations, [])

    def test_css_custom_property_references_are_declared_or_have_fallbacks(self) -> None:
        declaration = re.compile(r"--([A-Za-z0-9_-]+)\s*:")
        reference = re.compile(r"var\(\s*--([A-Za-z0-9_-]+)\s*(?P<suffix>[,)])")
        declared: set[str] = set()
        violations: list[str] = []

        for file_name, _line_number, line in self._css_lines():
            stripped = line.strip()
            if not stripped.startswith("--"):
                continue
            match = declaration.match(stripped)
            if match:
                declared.add(match.group(1))

        for file_name, line_number, line in self._css_lines():
            for match in reference.finditer(line):
                token = match.group(1)
                has_fallback = match.group("suffix") == ","
                if token not in declared and not has_fallback:
                    violations.append(f"{file_name}:{line_number}: --{token}")

        self.assertEqual(violations, [])

    def test_styles_parent_imports_split_assets_first(self) -> None:
        css = CSS_PATH.read_text(encoding="utf-8")
        tokens = (ASSETS_ROOT / "styles.tokens.css").read_text(encoding="utf-8")
        theme = (ASSETS_ROOT / "styles.theme.css").read_text(encoding="utf-8")
        layout = (ASSETS_ROOT / "styles.layout.css").read_text(encoding="utf-8")
        components = (ASSETS_ROOT / "styles.components.css").read_text(encoding="utf-8")
        pages = (ASSETS_ROOT / "styles.pages.css").read_text(encoding="utf-8")
        controls = (ASSETS_ROOT / "styles.controls.css").read_text(encoding="utf-8")
        layout_manager = (ASSETS_ROOT / "styles.layout-manager.css").read_text(encoding="utf-8")
        queue = (ASSETS_ROOT / "styles.queue.css").read_text(encoding="utf-8")
        rename = (ASSETS_ROOT / "styles.rename.css").read_text(encoding="utf-8")
        lines = css.splitlines()

        self.assertEqual(
            lines[:9],
            [
                '@import url("./styles.tokens.css");',
                '@import url("./styles.theme.css");',
                '@import url("./styles.layout.css");',
                '@import url("./styles.components.css");',
                '@import url("./styles.pages.css");',
                '@import url("./styles.controls.css");',
                '@import url("./styles.layout-manager.css");',
                '@import url("./styles.queue.css");',
                '@import url("./styles.rename.css");',
            ],
        )
        self.assertNotIn(":root {", css)
        self.assertNotIn(".app-shell {", css)
        self.assertNotIn(".metric-grid {", css)
        self.assertNotIn(".workflow-table {", css)
        self.assertNotIn(".home-at-a-glance-panel {", css)
        self.assertNotIn(".settings-tab-bar {", css)
        self.assertNotIn(".primary-button {", css)
        self.assertNotIn(".status-chip {", css)
        self.assertNotIn("#customize-layout-btn {", css)
        self.assertNotIn(".panel-customize-bar {", css)
        self.assertNotIn(".layout-editor-drawer {", css)
        self.assertNotIn(".priority-badge {", css)
        self.assertNotIn(".queue-strategy-select {", css)
        self.assertNotIn(".fo-drawer {", css)
        self.assertNotIn(".rename-workbench", css)
        self.assertNotIn("body.light-mode .nav-button.is-active", css)
        self.assertIn(":root {", tokens)
        self.assertIn("body.light-mode {", tokens)
        self.assertIn("body.light-mode .nav-button.is-active", theme)
        self.assertIn(".app-shell {", layout)
        self.assertIn(".page.is-visible {", layout)
        self.assertIn(".metric-grid {", components)
        self.assertIn(".workflow-table {", components)
        self.assertIn(".home-at-a-glance-panel {", pages)
        self.assertIn(".settings-tab-bar {", pages)
        self.assertIn(".primary-button {", controls)
        self.assertIn(".status-chip {", controls)
        self.assertIn(".route-chip {", controls)
        self.assertIn("#customize-layout-btn {", layout_manager)
        self.assertIn(".panel-customize-bar {", layout_manager)
        self.assertIn(".layout-editor-drawer {", layout_manager)
        self.assertIn(".layout-editor-panel-row {", layout_manager)
        self.assertIn(".layout-panel-preview {", layout_manager)
        self.assertIn(".layout-drag-hint {", layout_manager)
        self.assertIn(".priority-badge {", queue)
        self.assertIn(".queue-strategy-select {", queue)
        self.assertIn(".fo-drawer {", queue)
        self.assertIn(".rename-workbench", rename)

    def test_workflow_tables_use_content_weighted_layout_classes(self) -> None:
        html = _rendered_index_html()
        components = (ASSETS_ROOT / "styles.components.css").read_text(encoding="utf-8")

        for table_class in [
            "workflow-table queue-table",
            "workflow-table completed-table",
            "workflow-table pending-table",
        ]:
            self.assertIn(f'class="{table_class}"', html)

        self.assertIn(".workflow-table {", components)
        for selector in [".queue-table", ".completed-table", ".pending-table"]:
            self.assertIn(selector, components)

    def test_status_chip_helper_and_owner_tables_are_wired(self) -> None:
        helpers = DOM_HELPERS_PATH.read_text(encoding="utf-8")
        controls = (ASSETS_ROOT / "styles.controls.css").read_text(encoding="utf-8")
        completed = COMPLETED_TABLE_PATH.read_text(encoding="utf-8")
        pending = PENDING_VIEW_PATH.read_text(encoding="utf-8")

        self.assertIn("function makeStatusChip", helpers)
        self.assertIn("function setCellStatusChip", helpers)
        self.assertRegex(helpers, r"window\.mediaPipelineDom\s*=\s*\{[\s\S]*\bmakeStatusChip,")
        self.assertRegex(helpers, r"window\.mediaPipelineDom\s*=\s*\{[\s\S]*\bsetCellStatusChip,")
        self.assertIn(".status-chip", controls)
        self.assertIn("setCellStatusChip(healthCell", completed)
        self.assertIn("setCellStatusChip(stateCell", pending)

    def test_design_system_cleanup_tokens_and_action_hierarchy_are_wired(self) -> None:
        tokens = (ASSETS_ROOT / "styles.tokens.css").read_text(encoding="utf-8")
        layout = (ASSETS_ROOT / "styles.layout.css").read_text(encoding="utf-8")
        components = (ASSETS_ROOT / "styles.components.css").read_text(encoding="utf-8")
        controls = (ASSETS_ROOT / "styles.controls.css").read_text(encoding="utf-8")
        launch_js = LAUNCH_VIEW_PATH.read_text(encoding="utf-8")
        launch_html = LAUNCH_PARTIAL_PATH.read_text(encoding="utf-8")

        for token in ["--radius-xs:", "--radius-sm:", "--radius-pill:", "--amber-900:"]:
            self.assertIn(token, tokens)

        declared_radius_tokens = set(re.findall(r"--(radius-[\w-]+):", tokens))
        used_radius_tokens = set(
            re.findall(
                r"var\(--(radius-[\w-]+)\)",
                "\n".join(path.read_text(encoding="utf-8") for path in CSS_PATHS),
            )
        )
        self.assertTrue(used_radius_tokens)
        self.assertEqual(used_radius_tokens - declared_radius_tokens, set())

        self.assertRegex(layout, r"\.danger-button\s*\{[^}]*background: var\(--grey-800\);")
        self.assertRegex(layout, r"\.emergency-button\s*\{[^}]*background: var\(--red-900\);")
        self.assertIn(".status-chip::before", controls)
        self.assertIn("background: currentColor;", controls)
        self.assertIn("padding: var(--space-3) var(--space-4);", components)
        self.assertIn('id="audit-start-button" class="primary-button"', launch_html)
        self.assertIn('id="rerun-start-button" class="primary-button"', launch_html)
        self.assertIn("This does not start a new run or touch media", launch_js)
        self.assertIn("source media should not be touched", launch_js)

    def test_theme_toggle_uses_dark_as_unstored_default(self) -> None:
        app_js = APP_LIFECYCLE_PATH.read_text(encoding="utf-8")

        self.assertIn("localStorage.getItem(THEME_STORAGE_KEY)", app_js)
        self.assertIn("const preferLight = stored === \"light\";", app_js)
        self.assertNotIn("prefers-color-scheme: light", app_js)

    def test_panel_and_tab_consistency_contract_is_wired(self) -> None:
        html = _rendered_index_html()
        pages = (ASSETS_ROOT / "styles.pages.css").read_text(encoding="utf-8")
        components = (ASSETS_ROOT / "styles.components.css").read_text(encoding="utf-8")
        rename_css = (ASSETS_ROOT / "styles.rename.css").read_text(encoding="utf-8")
        app_js = APP_LAYOUT_MANAGER_PATH.read_text(encoding="utf-8")
        launch_js = LAUNCH_VIEW_PATH.read_text(encoding="utf-8")
        reports_js = REPORTS_VIEW_PATH.read_text(encoding="utf-8")
        completed_html = COMPLETED_PARTIAL_PATH.read_text(encoding="utf-8")
        rename_html = RENAME_PARTIAL_PATH.read_text(encoding="utf-8")

        for selector in [
            ".settings-tab-btn:hover",
            ".settings-tab-btn:focus-visible",
            ".settings-tab-btn[aria-selected=\"true\"]",
            ".settings-tab-btn:disabled",
            ".settings-tab-btn[aria-disabled=\"true\"]",
            ".settings-tab-btn[aria-busy=\"true\"]",
            ".settings-tab-pane.is-active",
        ]:
            self.assertIn(selector, pages)

        self.assertIn('id="layout-editor-drawer"', html)
        self.assertIn('id="layout-editor-tree"', html)
        self.assertNotIn(".layout-customize-mode .settings-tab-pane", pages)
        self.assertNotIn("is-launch-tab-hidden", pages + launch_js + html)
        self.assertNotIn("is-reports-tab-hidden", pages + reports_js + html)
        self.assertIn('panel.classList.toggle("is-active"', launch_js)
        self.assertIn('panel.classList.toggle("is-active"', reports_js)
        self.assertIn(".settings-tab-pane[data-launch-tab-panel]", app_js)
        self.assertIn(".settings-tab-pane[data-reports-tab-panel]", app_js)

        self.assertIn('class="settings-tab-bar completed-tab-bar"', html)
        self.assertIn('class="panel settings-tab-pane is-active output-overview-section output-overview-section-current" data-completed-tab="overview"', completed_html)
        self.assertIn('class="panel settings-tab-pane is-active" data-completed-tab="overview"', completed_html)
        self.assertIn('class="panel settings-tab-pane" data-completed-tab="advanced"', completed_html)
        self.assertIn('class="panel settings-tab-pane" data-completed-tab="history"', completed_html)
        self.assertIn("function _normalizeLayoutTabPaneContainers(page)", app_js)
        self.assertIn('page.querySelectorAll("section.panel.settings-tab-pane")', app_js)
        self.assertIn('className !== "panel"', app_js)
        self.assertIn('while (pane.firstChild) existing.appendChild(pane.firstChild);', app_js)
        self.assertIn('data-completed-tab="overview"', completed_html)
        self.assertIn("output-overview-kicker", completed_html)
        self.assertLess(
            completed_html.index('<h2 id="completed-current-output-heading">Current Output Status</h2>'),
            completed_html.index("<h2>Output Files</h2>"),
        )
        self.assertNotRegex(
            completed_html,
            r"<section class=\"panel settings-tab-pane is-active\" data-completed-tab=\"overview\"[\s\S]*?<div class=\"settings-tab-bar",
        )

        self.assertRegex(pages, r"\.settings-library-card\s*\{[^}]*border-radius: var\(--radius-sm\);")
        self.assertRegex(pages, r"\.settings-wizard-library-row\s*\{[^}]*border-radius: var\(--radius-sm\);")
        self.assertIn(".table-toolbar {", components)
        self.assertIn('class="table-toolbar queue-priority-toolbar"', html)
        self.assertIn('class="table-toolbar queue-strategy-toolbar"', html)
        self.assertIn(".rename-workbench > h1.visually-hidden", rename_css)
        self.assertIn('<h1 class="visually-hidden">Rename Files</h1>', rename_html)

    def test_webview_shell_has_narrow_viewport_layout(self) -> None:
        layout = (ASSETS_ROOT / "styles.layout.css").read_text(encoding="utf-8")
        components = (ASSETS_ROOT / "styles.components.css").read_text(encoding="utf-8")
        pages = (ASSETS_ROOT / "styles.pages.css").read_text(encoding="utf-8")

        body_match = re.search(r"body\s*\{(?P<body>.*?)\}", layout, re.S)
        self.assertIsNotNone(body_match)
        self.assertNotIn("min-width: 1120px", body_match.group("body"))
        self.assertIn("@media (max-width: 900px)", layout)
        self.assertIn("@media (max-width: 900px)", components)
        self.assertIn("@media (max-width: 900px)", pages)
        self.assertRegex(layout, r"@media \(max-width: 900px\)[\s\S]*\.app-shell\s*\{[\s\S]*grid-template-columns: minmax\(0, 1fr\);")
        self.assertRegex(layout, r"@media \(max-width: 900px\)[\s\S]*\.sidebar\s*\{[\s\S]*border-bottom: 1px solid var\(--grey-600\);")
        self.assertRegex(layout, r"@media \(max-width: 900px\)[\s\S]*\.nav\s*\{[\s\S]*overflow-x: auto;")
        self.assertRegex(layout, r"@media \(max-width: 900px\)[\s\S]*\.workspace\s*\{[\s\S]*min-width: 0;")
        self.assertRegex(layout, r"@media \(max-width: 900px\)[\s\S]*\.topbar\s*\{[\s\S]*flex-direction: column;")
        self.assertIn(".table-wrap,\n  .prose-block,\n  .log-block,\n  .status-block", components)
        self.assertIn("max-width: 100%;", components)
        self.assertIn(".home-up-next-list li", pages)


if __name__ == "__main__":
    unittest.main()
