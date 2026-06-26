from __future__ import annotations

import sys
import unittest
from pathlib import Path

from tests.css_import_resolver import resolve_css_imports


REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "src"))
sys.path.insert(0, str(REPO_ROOT))

STATIC_ROOT = REPO_ROOT / "apps" / "desktop" / "webview" / "static"
ASSETS_ROOT = STATIC_ROOT / "assets"


def read_static(path: str) -> str:
    return (STATIC_ROOT / path).read_text(encoding="utf-8")


def read_css(path: str) -> str:
    return resolve_css_imports(STATIC_ROOT / path, ASSETS_ROOT)


class WebViewDropdownRemediationStaticTests(unittest.TestCase):
    def test_settings_wizard_policy_selects_have_visible_choice_groups(self) -> None:
        js = read_static("assets/settingsWizard.js")
        css = read_css("assets/styles.components.css")
        self.assertIn("wizardChoiceGroupConfigs", js)
        for select_id in [
            "wizard-mode",
            "wizard-output-container",
            "wizard-publish-mode",
            "wizard-existing-policy",
            "wizard-video-strategy",
            "wizard-audio-policy",
            "wizard-subtitle-policy",
        ]:
            self.assertIn(select_id, js)
        self.assertIn("initWizardChoiceGroups", js)
        self.assertIn("syncWizardChoiceGroup", js)
        self.assertIn(".enhanced-choice-group", css)
        self.assertIn(".enhanced-choice-card:has(input:focus-visible)", css)

    def test_queue_strategy_selector_has_visible_radio_cards(self) -> None:
        js = read_static("assets/queueView.js")
        partial = read_static("partials/page-queue.html")
        css = read_css("assets/styles.queue.css")
        self.assertIn("enhanceQueueStrategySelector", js)
        self.assertIn("data-queue-strategy-choice-grid", js)
        self.assertIn("syncQueueStrategyChoiceGroup", js)
        self.assertIn('id="queue-strategy-select"', partial)
        self.assertIn(".queue-strategy-select", css)
        self.assertIn(".queue-strategy-choice-grid", css)

    def test_diagnostics_tail_targets_are_grouped_and_synchronized(self) -> None:
        js = read_static("assets/diagnosticsTailView.js")
        self.assertIn("diagnosticsTailTargetGroups", js)
        for label in ["Logs", "State and manifests", "Failures and audit", "Validation"]:
            self.assertIn(label, js)
        self.assertIn("initDiagnosticsTailTargetChoices", js)
        self.assertIn("syncDiagnosticsTailTargetChoices", js)
        self.assertIn("setDiagnosticsTailTarget", js)

    def test_dynamic_empty_selects_are_disabled_with_explanations(self) -> None:
        libraries_js = read_static("assets/librariesRouteMap.js")
        diagnostics_js = read_static("assets/diagnosticsView.js")
        self.assertIn("No library profiles loaded", libraries_js)
        self.assertIn("No comparable profiles loaded", libraries_js)
        self.assertIn("No loaded rows to trace", libraries_js)
        self.assertIn("No Tdarr Matrix runs loaded", diagnostics_js)
        self.assertIn("compareRefresh.disabled = tdarrMatrixConsoleState.runs.length < 2", diagnostics_js)

    def test_file_override_route_and_track_disabled_reasons_are_visible(self) -> None:
        partial = read_static("partials/page-queue.html")
        drawer_js = read_static("assets/queue/fileOverrides.drawer.js")
        form_js = read_static("assets/queue/fileOverrides.drawer.form.js")
        tracks_js = read_static("assets/queue/fileOverrides.drawer.tracks.js")
        queue_css = read_css("assets/styles.queue.css")
        self.assertIn("fo-route-override-toggle", partial)
        self.assertIn("fo-route-override-controls", partial)
        self.assertIn("toggleRouteOverrideDisclosure", form_js)
        self.assertIn("syncRouteOverrideDisclosure", form_js)
        self.assertIn("routeOverrideToggle", drawer_js)
        self.assertIn("fo-track-action-reason", tracks_js)
        self.assertIn("aria-describedby", tracks_js)
        self.assertIn("setTrackActionDisabledReason", form_js)
        self.assertIn(".fo-track-action-reason", queue_css)

    def test_file_override_glob_patterns_escape_before_regex_creation(self) -> None:
        tracks_js = read_static("assets/queue/fileOverrides.drawer.tracks.js")
        escape_index = tracks_js.index(r'rawPattern.replace(/[.+^${}()|[\]\\]/g, "\\$&")')
        wildcard_index = tracks_js.index(r'.replace(/\*/g, ".*")', escape_index)
        question_index = tracks_js.index(r'.replace(/\?/g, ".")', wildcard_index)
        regex_index = tracks_js.index("new RegExp(`^${escaped}$`)", question_index)

        self.assertLess(escape_index, wildcard_index)
        self.assertLess(wildcard_index, question_index)
        self.assertLess(question_index, regex_index)


if __name__ == "__main__":
    unittest.main()
