from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path

from mediapipeline.tools.paths import find_repo_root

sys.path.insert(0, str(find_repo_root(Path(__file__)) / "src"))

from mediapipeline.desktop.api.static_files import render_index
from tests.css_import_resolver import local_css_import_paths, resolve_css_imports

REPO_ROOT = find_repo_root(Path(__file__))
STATIC_ROOT = REPO_ROOT / "apps" / "desktop" / "webview" / "static"
ASSETS_ROOT = STATIC_ROOT / "assets"
CSS_PATH = ASSETS_ROOT / "styles.css"
CSS_PATHS = sorted(path for path in ASSETS_ROOT.rglob("*.css") if path.is_file())
COMPONENTS_CSS_PATH = ASSETS_ROOT / "styles.components.css"
PAGES_CSS_PATH = ASSETS_ROOT / "styles.pages.css"
QUEUE_CSS_PATH = ASSETS_ROOT / "styles.queue.css"
DOM_HELPERS_PATH = ASSETS_ROOT / "domHelpers.js"
COMPLETED_VIEW_PATH = ASSETS_ROOT / "completedView.js"
PENDING_VIEW_PATH = ASSETS_ROOT / "pendingPublishView.js"
COMPLETED_TABLE_PATH = ASSETS_ROOT / "completed" / "table.js"
APP_LIFECYCLE_PATH = ASSETS_ROOT / "app" / "lifecycle.js"
APP_LAYOUT_MANAGER_PATH = ASSETS_ROOT / "app" / "layoutManager.js"
LAUNCH_VIEW_PATH = ASSETS_ROOT / "launchView.js"
LAUNCH_COMMAND_BUTTONS_PATH = ASSETS_ROOT / "launch" / "commandButtons.js"
LAUNCH_PARTIAL_PATH = STATIC_ROOT / "partials" / "page-launch.html"
REPORTS_VIEW_PATH = ASSETS_ROOT / "reportsView.js"
REPORTS_SHELL_PATH = ASSETS_ROOT / "reports" / "shell.js"
COMPLETED_PARTIAL_PATH = STATIC_ROOT / "partials" / "page-completed.html"
PENDING_PARTIAL_PATH = STATIC_ROOT / "partials" / "page-pending.html"
QUEUE_PARTIAL_PATH = STATIC_ROOT / "partials" / "page-queue.html"
TELEMETRY_PARTIAL_PATH = STATIC_ROOT / "partials" / "page-telemetry.html"
RENAME_PARTIAL_PATH = STATIC_ROOT / "partials" / "page-rename.html"


def _read_dom_helpers_bundle() -> str:
    return "\n".join(
        (ASSETS_ROOT / name).read_text(encoding="utf-8")
        for name in [
            "dom/query.js",
            "dom/text.js",
            "dom/status.js",
            "dom/filtering.js",
            "dom/table.js",
            "domHelpers.js",
        ]
    )


def _rendered_index_html() -> str:
    response = render_index(STATIC_ROOT, {"token": "test-token", "appVersion": "v5-test"})
    assert response.status == 200
    return response.body.decode("utf-8")


def _read_components_css() -> str:
    return resolve_css_imports(COMPONENTS_CSS_PATH, ASSETS_ROOT)


def _read_pages_css() -> str:
    return resolve_css_imports(PAGES_CSS_PATH, ASSETS_ROOT)


def _read_queue_css() -> str:
    return resolve_css_imports(QUEUE_CSS_PATH, ASSETS_ROOT)


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
        raw_state_palette = re.compile(r"var\(--(?:red|green|amber|blue|purple)-\d+\)")
        violations: list[str] = []

        for file_name, line_number, line in self._css_lines():
            stripped = line.strip()
            if raw_color.search(line):
                violations.append(f"{file_name}:{line_number}: {line}")
                continue
            if raw_hsl.search(line) and not stripped.startswith("--"):
                violations.append(f"{file_name}:{line_number}: {line}")
            if file_name != "styles.tokens.css" and raw_state_palette.search(line):
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
                if "var(--opacity-" not in line:
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
        components = _read_components_css()
        pages = _read_pages_css()
        controls = (ASSETS_ROOT / "styles.controls.css").read_text(encoding="utf-8")
        layout_manager = (ASSETS_ROOT / "styles.layout-manager.css").read_text(encoding="utf-8")
        queue = _read_queue_css()
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
        self.assertNotIn(".home-next-queue-panel {", css)
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
        self.assertIn(".home-next-queue-panel {", pages)
        self.assertIn(".settings-tab-bar {", pages)
        self.assertIn(".primary-button {", controls)
        self.assertIn(".status-chip {", controls)
        self.assertIn(".route-chip {", controls)
        self.assertIn("#customize-layout-btn {", layout_manager)
        self.assertIn(".panel-customize-bar {", layout_manager)
        self.assertIn(".layout-editor-drawer {", layout_manager)
        self.assertIn(".layout-editor-panel-row {", layout_manager)
        self.assertIn(".layout-editor-panel-row.is-drag-holding", layout_manager)
        self.assertIn("touch-action: none;", layout_manager)
        self.assertIn("@keyframes layout-editor-row-grab-jiggle", layout_manager)
        self.assertIn("@media (prefers-reduced-motion: reduce)", layout_manager)
        self.assertIn(".layout-panel-preview {", layout_manager)
        self.assertIn(".layout-drag-hint {", layout_manager)
        self.assertIn(".priority-badge {", queue)
        self.assertIn(".queue-strategy-select {", queue)
        self.assertIn(".fo-drawer {", queue)
        self.assertIn(".rename-workbench", rename)

    def test_component_css_local_imports_resolve_under_assets_root(self) -> None:
        for imported_path in local_css_import_paths(COMPONENTS_CSS_PATH, ASSETS_ROOT):
            self.assertTrue(imported_path.is_file(), imported_path)
            imported_path.relative_to(ASSETS_ROOT.resolve())
        self.assertTrue(_read_components_css())

    def test_pages_css_local_imports_resolve_under_assets_root(self) -> None:
        for imported_path in local_css_import_paths(PAGES_CSS_PATH, ASSETS_ROOT):
            self.assertTrue(imported_path.is_file(), imported_path)
            imported_path.relative_to(ASSETS_ROOT.resolve())
        self.assertTrue(_read_pages_css())

    def test_queue_css_local_imports_resolve_under_assets_root(self) -> None:
        for imported_path in local_css_import_paths(QUEUE_CSS_PATH, ASSETS_ROOT):
            self.assertTrue(imported_path.is_file(), imported_path)
            imported_path.relative_to(ASSETS_ROOT.resolve())
        self.assertTrue(_read_queue_css())

    def test_workflow_tables_use_content_weighted_layout_classes(self) -> None:
        html = _rendered_index_html()
        components = _read_components_css()

        for table_class in [
            "workflow-table queue-table",
            "workflow-table completed-table",
            "workflow-table pending-table",
        ]:
            self.assertIn(f'class="{table_class}"', html)

        self.assertIn(".workflow-table {", components)
        for selector in [".queue-table", ".completed-table", ".pending-table"]:
            self.assertIn(selector, components)

    def test_shared_data_table_controls_are_wired(self) -> None:
        helpers = _read_dom_helpers_bundle()
        app_js = (ASSETS_ROOT / "app.js").read_text(encoding="utf-8")
        components = _read_components_css()

        self.assertIn("function enhanceDataTables", helpers)
        self.assertIn("enhanceDataTables,", helpers)
        self.assertIn("window.mediaPipelineDom?.enhanceDataTables?.();", app_js)
        for selector in [
            ".data-table-wrap",
            ".table-ui-toolbar",
            ".table-column-menu",
            ".table-sort-button",
            ".table-column-resizer",
            ".data-table th[data-sticky-column]",
            ".data-table.has-many-rows tbody tr:nth-child(even):not(.is-selected):not([data-status]) td",
        ]:
            self.assertIn(selector, components)

    def test_status_chip_helper_and_owner_tables_are_wired(self) -> None:
        helpers = _read_dom_helpers_bundle()
        controls = (ASSETS_ROOT / "styles.controls.css").read_text(encoding="utf-8")
        completed = COMPLETED_TABLE_PATH.read_text(encoding="utf-8")
        pending = PENDING_VIEW_PATH.read_text(encoding="utf-8")

        self.assertIn("function makeStatusChip", helpers)
        self.assertIn("function setCellStatusChip", helpers)
        self.assertIn('if (["parked", "park", "pending_publish", "pending publish"].includes(raw)) return "parked";', helpers)
        self.assertIn('if (["health-check", "health_check", "health check"].includes(raw)) return "health-check";', helpers)
        self.assertIn('if (["unavailable", "not_available", "not available"].includes(raw)) return "unavailable";', helpers)
        self.assertIn('if (["unknown"].includes(raw)) return "unknown";', helpers)
        self.assertIn('if (["queue_pending", "queue pending"].includes(raw)) return "queued";', helpers)
        self.assertIn('if (["drain_pending", "drain pending"].includes(raw)) return "queued";', helpers)
        self.assertIn('if (["pending"].includes(raw)) return "unknown";', helpers)
        self.assertIn('do_not_drain: "blocked"', helpers)
        self.assertNotIn('do_not_drain: "failed"', helpers)
        self.assertNotIn("span.tabIndex = 0", helpers)
        self.assertIn("Visual tone:", helpers)
        self.assertNotIn("Color meaning:", helpers)
        self.assertRegex(helpers, r"window\.mediaPipelineDom\s*=\s*\{[\s\S]*\bmakeStatusChip,")
        self.assertRegex(helpers, r"window\.mediaPipelineDom\s*=\s*\{[\s\S]*\bsetCellStatusChip,")
        self.assertIn(".status-chip", controls)
        self.assertIn("setCellStatusChip(promotionCell", completed)
        self.assertIn("setCellStatusChip(stateCell", pending)

    def test_semantic_color_roles_are_wired(self) -> None:
        tokens = (ASSETS_ROOT / "styles.tokens.css").read_text(encoding="utf-8")
        controls = (ASSETS_ROOT / "styles.controls.css").read_text(encoding="utf-8")
        components = _read_components_css()
        pages = _read_pages_css()
        queue = _read_queue_css()
        theme = (ASSETS_ROOT / "styles.theme.css").read_text(encoding="utf-8")

        for token in (
            "--semantic-success-bg:",
            "--semantic-warning-bg:",
            "--semantic-danger-bg:",
            "--semantic-info-bg:",
            "--semantic-pending-bg:",
            "--semantic-disabled-bg:",
            "--semantic-selected-bg:",
            "--semantic-backend-evidence-bg:",
            "--semantic-frontend-advisory-bg:",
            "--semantic-evidence-panel-bg:",
            "--semantic-interactive-panel-border:",
        ):
            self.assertIn(token, tokens)

        self.assertIn("--semantic-backend-evidence-bg: hsl(265, 15%, 14%);", tokens)
        self.assertIn("--semantic-backend-evidence-bg: var(--purple-100);", tokens)
        self.assertIn("--evidence-bg: var(--semantic-evidence-panel-bg);", tokens)
        self.assertNotIn("--evidence-bg: var(--blue-100);", tokens)
        self.assertIn("keep backend evidence purple in both themes", theme)

        self.assertRegex(controls, r'\.status-chip\[data-status="unknown"\]\s*\{[^}]*var\(--semantic-warning-bg\)')
        self.assertRegex(controls, r'\.status-chip\[data-status="queued"\]\s*\{[^}]*var\(--semantic-pending-bg\)')
        self.assertRegex(controls, r'\.status-chip\[data-status="empty"\],\s*\n\.status-chip\[data-status="unavailable"\]\s*\{[^}]*var\(--semantic-disabled-bg\)')
        self.assertRegex(controls, r'\.route-chip\[data-route="encode"\].*var\(--semantic-info-bg\)')
        self.assertRegex(controls, r'\.route-chip\[data-route="remux-fallback"\]\s*\{[^}]*linear-gradient\(90deg, var\(--semantic-info-bg\) 0 50%, var\(--semantic-success-bg\) 50% 100%\)')
        self.assertRegex(controls, r'\.route-chip\[data-route="review"\].*var\(--semantic-warning-bg\)')
        self.assertRegex(controls, r'tr\[data-status="empty"\] td,\s*\ntr\[data-status="unavailable"\] td \{ background: var\(--semantic-disabled-bg\); \}')
        self.assertIn('[data-page-panel="schedule"] tr[data-status="review"] td  { background: var(--row-warning-bg); }', controls)

        self.assertRegex(components, r'\.panel\[data-panel-type="evidence"\]\s*\{[^}]*var\(--evidence-bg\)[^}]*var\(--semantic-evidence-panel-border\)')
        self.assertRegex(components, r'\.completed-selected-status-chip\[data-state="warning"\]\s*\{[^}]*var\(--semantic-warning-border\)[^}]*var\(--semantic-warning-text\)')
        self.assertNotRegex(components, r'\.completed-selected-status-chip\[data-state="warning"\]\s*\{[^}]*blue')
        self.assertRegex(components, r'tr\.is-selected td\s*\{[^}]*var\(--semantic-selected-bg\)')
        self.assertIn("body.light-mode tr.is-selected td { background: var(--semantic-selected-bg); }", theme)

        self.assertRegex(pages, r'\.rename-preview-output\[data-state="changed"\]\s*\{[^}]*var\(--semantic-info-border\)[^}]*var\(--semantic-info-text\)')
        self.assertRegex(pages, r'\.settings-wizard-steps strong\[data-state="not-started"\]\s*\{[^}]*var\(--semantic-disabled-text\)')

        rename = (ASSETS_ROOT / "styles.rename.css").read_text(encoding="utf-8")
        self.assertIn("--rename-stage-accent: var(--semantic-info-accent);", rename)
        self.assertIn("--rename-stage-accent: var(--semantic-warning-accent);", rename)
        self.assertIn("--rename-stage-accent: var(--semantic-danger-accent);", rename)
        self.assertIn("--rename-stage-accent: var(--semantic-success-accent);", rename)

        self.assertRegex(queue, r'\.fo-route-encode-advisory\[data-tone="warning"\]\s*\{[^}]*var\(--semantic-frontend-advisory-bg\)')
        self.assertRegex(queue, r'\.fo-drawer-status\[data-tone="working"\]\s*\{[^}]*var\(--semantic-pending-bg\)')
        self.assertIn("box-shadow: inset 3px 0 0 var(--semantic-pending-accent);", queue)
        self.assertIn("outline: 2px solid var(--semantic-focus-outline);", queue)
        self.assertRegex(queue, r'\.fo-series-modal\s*\{[^}]*background: var\(--semantic-overlay-bg\);')

    def test_topbar_and_evidence_tools_accessibility_contract(self) -> None:
        html = _rendered_index_html()
        layout = (ASSETS_ROOT / "styles.layout.css").read_text(encoding="utf-8")
        components = _read_components_css()

        for token in (
            '<button type="button" id="refresh-health"',
            '<button type="button" id="close-readiness"',
            'aria-label="Open Diagnostics for refresh health"',
            'aria-label="Open Diagnostics for close readiness"',
            'aria-label="Current output status rows"',
            'aria-label="Completed history rows"',
            'aria-label="Final library promotion rows"',
            'aria-label="Acceptance and evidence packet rows"',
            'aria-label="Queue rows"',
            'aria-label="Queue backend launch scope boundary rows"',
            'aria-label="Pending publish rows"',
            'aria-label="Pending publish backend drain scope rows"',
            'aria-label="GPU telemetry detail rows"',
            'role="tablist" aria-label="Completed output sections"',
            'role="img" aria-label="CPU usage over the last eight minutes"',
            'role="img" aria-label="Video encoder usage over the last eight minutes"',
            'role="img" aria-label="RAM usage over the last eight minutes"',
            'aria-describedby="cpu-chart-meta cpu-utility-note"',
            'data-panel-subtype="evidence-tools"',
        ):
            self.assertIn(token, html)
        self.assertIn('id="pipeline-sparkline" class="pipeline-sparkline" aria-hidden="true"', html)
        self.assertNotIn('aria-label="Recent pipeline event history"', html)
        self.assertNotIn('title="Last 20 pipeline events"', html)
        self.assertNotIn('<span id="refresh-health"', html)
        self.assertNotIn('<span id="close-readiness"', html)
        self.assertIn(".close-readiness:focus-visible", layout)
        self.assertIn(".refresh-health:focus-visible", layout)
        self.assertIn('.panel[data-panel-subtype="evidence-tools"]', components)
        self.assertIn('content: "evidence tools"', components)

    def test_design_system_cleanup_tokens_and_action_hierarchy_are_wired(self) -> None:
        tokens = (ASSETS_ROOT / "styles.tokens.css").read_text(encoding="utf-8")
        layout = (ASSETS_ROOT / "styles.layout.css").read_text(encoding="utf-8")
        components = _read_components_css()
        controls = (ASSETS_ROOT / "styles.controls.css").read_text(encoding="utf-8")
        launch_js = LAUNCH_VIEW_PATH.read_text(encoding="utf-8")
        launch_command_buttons_js = LAUNCH_COMMAND_BUTTONS_PATH.read_text(encoding="utf-8")
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
        self.assertRegex(layout, r"\.emergency-button\s*\{[^}]*background: var\(--semantic-danger-bg\);")
        self.assertIn(".status-chip::before", controls)
        self.assertIn("background: currentColor;", controls)
        self.assertIn("padding: var(--space-3) var(--space-4);", components)
        self.assertNotIn('id="audit-start-button" class="primary-button"', launch_html)
        self.assertIn('id="rerun-start-button" class="primary-button"', launch_html)
        self.assertIn("This does not start a new run or touch media", launch_command_buttons_js)
        self.assertIn("source media should not be touched", launch_command_buttons_js)

    def test_theme_toggle_uses_dark_as_unstored_default(self) -> None:
        app_js = APP_LIFECYCLE_PATH.read_text(encoding="utf-8")

        self.assertIn("localStorage.getItem(THEME_STORAGE_KEY)", app_js)
        self.assertIn("const preferLight = stored === \"light\";", app_js)
        self.assertNotIn("prefers-color-scheme: light", app_js)

    def test_panel_and_tab_consistency_contract_is_wired(self) -> None:
        html = _rendered_index_html()
        pages = _read_pages_css()
        components = _read_components_css()
        rename_css = (ASSETS_ROOT / "styles.rename.css").read_text(encoding="utf-8")
        app_js = APP_LAYOUT_MANAGER_PATH.read_text(encoding="utf-8")
        lifecycle_js = APP_LIFECYCLE_PATH.read_text(encoding="utf-8")
        launch_js = LAUNCH_VIEW_PATH.read_text(encoding="utf-8")
        reports_js = REPORTS_VIEW_PATH.read_text(encoding="utf-8")
        reports_shell_js = REPORTS_SHELL_PATH.read_text(encoding="utf-8")
        completed_html = COMPLETED_PARTIAL_PATH.read_text(encoding="utf-8")
        rename_html = RENAME_PARTIAL_PATH.read_text(encoding="utf-8")

        for selector in [
            ".settings-tab-btn:hover",
            ".settings-tab-btn:focus-visible",
            ".settings-tab-btn[aria-selected=\"true\"]",
            ".settings-section-nav-btn[aria-current=\"location\"]",
            ".profile-nav-btn[aria-current=\"location\"]",
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
        self.assertIn('panel.classList.toggle("is-active"', reports_shell_js)
        self.assertIn(".settings-tab-pane[data-launch-tab-panel]", app_js)
        self.assertIn(".settings-tab-pane[data-reports-tab-panel]", app_js)

        self.assertIn('class="settings-tab-bar completed-tab-bar"', html)
        self.assertIn('role="tablist" aria-label="Completed output sections"', completed_html)
        self.assertIn('role="tab" data-completed-tab="overview" aria-selected="true">Overview</button>', completed_html)
        self.assertIn('role="tab" data-completed-tab="evidence" aria-selected="false">Evidence</button>', completed_html)
        self.assertNotIn('data-output-page-target="pending"', completed_html)
        self.assertIn('class="panel settings-tab-pane is-active output-overview-section output-overview-section-current" data-completed-tab="overview"', completed_html)
        self.assertIn('class="panel settings-tab-pane is-active" data-completed-tab="overview"', completed_html)
        self.assertIn('class="panel settings-tab-pane" data-completed-tab="evidence"', completed_html)
        self.assertIn('class="panel settings-tab-pane" data-completed-tab="history"', completed_html)
        self.assertIn("function _normalizeLayoutTabPaneContainers(page)", app_js)
        self.assertIn('page.querySelectorAll("section.panel.settings-tab-pane")', app_js)
        self.assertIn('className !== "panel"', app_js)
        self.assertIn('while (pane.firstChild) existing.appendChild(pane.firstChild);', app_js)
        self.assertIn("function syncTabAccessibility()", lifecycle_js)
        self.assertIn('button.setAttribute("aria-controls", panelIds.join(" "))', lifecycle_js)
        self.assertIn('panel.setAttribute("role", "tabpanel")', lifecycle_js)
        self.assertIn('panel.setAttribute("aria-labelledby", buttonId)', lifecycle_js)
        self.assertIn('if (event.key === "ArrowRight" || event.key === "ArrowDown")', lifecycle_js)
        self.assertIn('if (event.key === "Home") nextIndex = 0;', lifecycle_js)
        self.assertNotIn('function syncOutputSectionButtons(activePage, completedTab)', lifecycle_js)
        self.assertNotIn('document.querySelectorAll("[data-output-page-target]")', lifecycle_js)
        self.assertIn('data-completed-tab="overview"', completed_html)
        self.assertIn("output-overview-kicker", completed_html)
        self.assertIn('id="completed-current-at-a-glance"', completed_html)
        self.assertIn('id="completed-current-filter-line"', completed_html)
        self.assertIn('id="completed-current-details"', completed_html)
        self.assertIn("<h2>Why This Output Looks Different</h2>", completed_html)
        self.assertRegex(completed_html, r'<section class="panel settings-tab-pane is-active" data-completed-tab="overview" data-panel-type="interactive">\s*<div class="panel-heading">\s*<h2>Why This Output Looks Different</h2>')
        self.assertLess(
            completed_html.index("<h2>Output Files</h2>"),
            completed_html.index('<h2 id="completed-current-output-heading">Current Output Status</h2>'),
        )
        self.assertNotRegex(
            completed_html,
            r"<section class=\"panel settings-tab-pane is-active\" data-completed-tab=\"overview\"[\s\S]*?<div class=\"settings-tab-bar",
        )

        self.assertIn(".completed-current-at-a-glance {", components)
        self.assertIn(".completed-current-metric-value {", components)
        self.assertRegex(components, r"\.completed-current-metric-value\s*\{[^}]*font-variant-numeric: tabular-nums;")
        self.assertRegex(pages, r"\.settings-library-card\s*\{[^}]*border-radius: var\(--radius-sm\);")
        self.assertRegex(pages, r"\.settings-wizard-library-row\s*\{[^}]*border-radius: var\(--radius-sm\);")
        self.assertRegex(pages, r"\.settings-wizard-readiness-strip\s*\{[^}]*border-radius: var\(--radius-sm\);")
        self.assertRegex(pages, r"\.settings-wizard-result-row\s*\{[^}]*border-radius: var\(--radius-sm\);")
        self.assertIn(".table-toolbar {", components)
        self.assertIn('class="table-toolbar queue-priority-toolbar"', html)
        self.assertIn('class="table-toolbar queue-strategy-toolbar"', html)
        self.assertIn(".rename-workbench > h1.visually-hidden", rename_css)
        self.assertIn('<h1 class="visually-hidden">Rename</h1>', rename_html)

    def test_rename_workbench_keeps_mode_stage_left_aligned_at_wide_width(self) -> None:
        rename_css = (ASSETS_ROOT / "styles.rename.css").read_text(encoding="utf-8")

        workbench_grid_match = re.search(
            r"\.rename-workbench-grid\s*\{(?P<body>[^}]*)\}",
            rename_css,
            re.S,
        )
        self.assertIsNotNone(workbench_grid_match)
        self.assertIn("grid-template-columns: minmax(0, 1fr);", workbench_grid_match.group("body"))
        self.assertNotIn("minmax(300px, 0.9fr) minmax(420px, 1.1fr)", rename_css)

    def test_webview_shell_has_narrow_viewport_layout(self) -> None:
        layout = (ASSETS_ROOT / "styles.layout.css").read_text(encoding="utf-8")
        components = _read_components_css()
        pages = _read_pages_css()

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
        self.assertIn(".home-next-queue-list li", pages)
        self.assertRegex(components, r"\.telemetry-grid\s*\{[^}]*grid-template-columns: repeat\(3, minmax\(280px, 1fr\)\);")
        self.assertRegex(components, r"@media \(max-width: 900px\)[\s\S]*\.telemetry-grid\s*\{[\s\S]*grid-template-columns: repeat\(2, minmax\(0, 1fr\)\);")
        self.assertRegex(components, r"@media \(max-width: 520px\)[\s\S]*\.telemetry-grid,[\s\S]*grid-template-columns: minmax\(0, 1fr\);")


if __name__ == "__main__":
    unittest.main()
