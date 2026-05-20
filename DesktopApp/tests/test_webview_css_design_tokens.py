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
        lines = css.splitlines()

        self.assertEqual(
            lines[:8],
            [
                '@import url("./styles.tokens.css");',
                '@import url("./styles.theme.css");',
                '@import url("./styles.layout.css");',
                '@import url("./styles.components.css");',
                '@import url("./styles.pages.css");',
                '@import url("./styles.controls.css");',
                '@import url("./styles.layout-manager.css");',
                '@import url("./styles.queue.css");',
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
        self.assertNotIn(".priority-badge {", css)
        self.assertNotIn(".queue-strategy-select {", css)
        self.assertNotIn(".fo-drawer {", css)
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
        self.assertIn(".layout-drag-hint {", layout_manager)
        self.assertIn(".priority-badge {", queue)
        self.assertIn(".queue-strategy-select {", queue)
        self.assertIn(".fo-drawer {", queue)

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
        completed = COMPLETED_VIEW_PATH.read_text(encoding="utf-8")
        pending = PENDING_VIEW_PATH.read_text(encoding="utf-8")

        self.assertIn("function makeStatusChip", helpers)
        self.assertIn("function setCellStatusChip", helpers)
        self.assertRegex(helpers, r"window\.mediaPipelineDom\s*=\s*\{[\s\S]*\bmakeStatusChip,")
        self.assertRegex(helpers, r"window\.mediaPipelineDom\s*=\s*\{[\s\S]*\bsetCellStatusChip,")
        self.assertIn(".status-chip", controls)
        self.assertIn("setCellStatusChip(healthCell", completed)
        self.assertIn("setCellStatusChip(stateCell", pending)


if __name__ == "__main__":
    unittest.main()
