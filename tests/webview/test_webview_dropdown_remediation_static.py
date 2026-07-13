from __future__ import annotations

import shutil
import subprocess
import sys
import textwrap
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
        js = "\n".join(
            read_static(path)
            for path in (
                "assets/queue/strategy.js",
                "assets/queue/controls.js",
                "assets/queueView.js",
            )
        )
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
        diagnostics_js = "\n".join(
            (
                read_static("assets/diagnostics/matrixConsole.js"),
                read_static("assets/diagnosticsView.js"),
            )
        )
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

    def test_file_override_glob_patterns_use_bounded_literal_wildcard_matching(self) -> None:
        tracks_js = read_static("assets/queue/fileOverrides.drawer.tracks.js")
        self.assertIn('glob[globIndex] === "?"', tracks_js)
        self.assertIn('glob[globIndex] === "*"', tracks_js)
        self.assertIn("starIndex >= 0", tracks_js)
        self.assertIn("MAX_TRACK_TITLE_GLOB_LENGTH = 256", tracks_js)
        self.assertIn("MAX_TRACK_TITLE_VALUE_LENGTH = 1024", tracks_js)
        self.assertNotIn("new RegExp(`^${escaped}$`)", tracks_js)

        node = shutil.which("node")
        if not node:
            raise unittest.SkipTest("Node.js is required for the file-override wildcard behavior check.")
        script = textwrap.dedent(
            r"""
            const fs = require("fs");
            const vm = require("vm");
            const source = fs.readFileSync(
              "apps/desktop/webview/static/assets/queue/fileOverrides.drawer.tracks.js",
              "utf8",
            );
            const context = { window: {}, console };
            context.window = context;
            vm.createContext(context);
            vm.runInContext(source, context);
            const isPlainObject = (value) => Boolean(value) && typeof value === "object" && !Array.isArray(value);
            const selectorStreamIndex = (rule) => {
              const value = Number(rule?.streamIndex ?? rule?.stream_index);
              return Number.isFinite(value) ? value : null;
            };
            const module = context.__queueFileOverridesDrawerTracksModule.createFileOverridesDrawerTracksModule({
              documentRef: {},
              state: {},
              DRAWER_FIELD_PATHS: [],
              TRACK_ACTION_FIELD_PATHS: [],
              SOURCE_INFO_BASIS_LABELS: {},
              byId() { return null; },
              isPlainObject,
              hasOwnValue(value, key) { return Object.prototype.hasOwnProperty.call(value, key); },
              emptyExactSelectorState() { return {}; },
              selectorStreamIndex,
              isExactTrackSelector(value) { return selectorStreamIndex(value) !== null; },
              currentFileOverridePathLooksFileLike() { return true; },
              setStatus() {},
              form: {
                fileOverrideEffectiveSourceLabel() { return ""; },
                syncSubFilterFields() {},
              },
            });
            const track = {
              index: 4,
              language: "ENG",
              codec: "AAC",
              title: "Director + Cast [Final]",
              channels: 6,
            };
            const cases = [
              [{ streamIndex: 4, title: "director*final]", language: "eng", codec: "aac", channels: 6 }, true],
              [{ streamIndex: 4, title: "Director + Cast [Final]" }, true],
              [{ streamIndex: 4, title: "Director + Cast [Final?" }, true],
              [{ streamIndex: 4, title: "Director + Cast [Final??" }, false],
              [{ streamIndex: 4, title: "Director .+ Cast *" }, false],
            ];
            for (const [selector, expected] of cases) {
              const actual = module.exactSelectorMatchesTrack(selector, track, "audio");
              if (actual !== expected) {
                throw new Error(JSON.stringify({ selector, expected, actual }));
              }
            }
            if (module.exactSelectorMatchesTrack({ streamIndex: 4, title: "x".repeat(257) }, track, "audio")) {
              throw new Error("Oversized title glob did not fail closed.");
            }
            const oversizedTrack = { ...track, title: "x".repeat(1025) };
            if (module.exactSelectorMatchesTrack({ streamIndex: 4, title: "*" }, oversizedTrack, "audio")) {
              throw new Error("Oversized probed title did not fail closed.");
            }
            """
        )
        result = subprocess.run(
            [node, "-e", script],
            cwd=REPO_ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr or result.stdout)


if __name__ == "__main__":
    unittest.main()
