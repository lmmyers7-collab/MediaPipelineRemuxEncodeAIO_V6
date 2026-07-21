from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
import textwrap
import unittest
from collections import Counter
from html.parser import HTMLParser
from pathlib import Path

from mediapipeline.tools.paths import find_repo_root
from tests.webview.static_markup_support import settings_markup

sys.path.insert(0, str(find_repo_root(Path(__file__)) / "src"))

from mediapipeline.desktop.api import LocalApiServer
from mediapipeline.desktop.application import MediaPipelineApplicationFacade

try:  # unittest discovery can import tests as top-level modules or package modules.
    from .test_application_facade import DummyWorkflowFacadeService
    from .test_webview_real_media_smoke import _write_fixture_state
    from .webview_browser_smoke_support import (
        assert_media_no_mutation,
        browser_cdp_runner_prelude,
        capture_media_no_mutation_snapshot,
        find_browser,
        free_port,
        run_node_browser_smoke,
    )
except ImportError:  # pragma: no cover - fallback for direct test execution
    from test_application_facade import DummyWorkflowFacadeService
    from test_webview_real_media_smoke import _write_fixture_state
    from webview_browser_smoke_support import (
        assert_media_no_mutation,
        browser_cdp_runner_prelude,
        capture_media_no_mutation_snapshot,
        find_browser,
        free_port,
        run_node_browser_smoke,
    )


_INTERACTIVE_NATIVE_TAGS = {"button", "input", "select", "summary", "textarea"}
_INTERACTIVE_ROLES = {
    "button",
    "checkbox",
    "gridcell",
    "link",
    "menuitem",
    "menuitemcheckbox",
    "menuitemradio",
    "option",
    "radio",
    "row",
    "switch",
    "tab",
    "treeitem",
}
_STABLE_DATA_ATTRIBUTES = (
    "data-settings-tab",
    "data-wizard-step-button",
    "data-rename-movie-filter",
    "data-rename-tv-filter",
    "data-cross-page-target",
    "data-quick-link-focus",
)
_SURFACE_EXPECTED_COUNTS = {"settings": 325, "libraries": 17, "schedule": 10}


class _StaticInteractiveParser(HTMLParser):
    def __init__(self, surface: str) -> None:
        super().__init__(convert_charrefs=True)
        self.surface = surface
        self.controls: list[dict[str, object]] = []
        self._tag_counts: Counter[str] = Counter()
        self._identity_counts: Counter[str] = Counter()

    @staticmethod
    def _is_interactive(tag: str, attrs: dict[str, str]) -> bool:
        if tag in _INTERACTIVE_NATIVE_TAGS:
            return True
        if tag == "a" and "href" in attrs:
            return True
        if attrs.get("role", "").strip().casefold() in _INTERACTIVE_ROLES:
            return True
        raw_tabindex = attrs.get("tabindex", "").strip()
        try:
            return bool(raw_tabindex) and int(raw_tabindex) >= 0
        except ValueError:
            return False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        normalized_tag = tag.casefold()
        normalized_attrs = {key.casefold(): "" if value is None else value for key, value in attrs}
        if not self._is_interactive(normalized_tag, normalized_attrs):
            return

        tag_ordinal = self._tag_counts[normalized_tag]
        self._tag_counts[normalized_tag] += 1
        element_id = normalized_attrs.get("id", "").strip()
        locator: dict[str, object]
        if element_id:
            identity_base = f"{self.surface}#{element_id}"
            locator = {"kind": "id", "value": element_id}
        else:
            attribute_name = next(
                (name for name in _STABLE_DATA_ATTRIBUTES if normalized_attrs.get(name, "").strip()),
                "",
            )
            if attribute_name:
                attribute_value = normalized_attrs[attribute_name].strip()
                identity_base = f'{self.surface}[{attribute_name}="{attribute_value}"]'
                locator = {
                    "kind": "attribute",
                    "name": attribute_name,
                    "value": attribute_value,
                    "occurrence": self._identity_counts[identity_base],
                }
            elif normalized_attrs.get("aria-label", "").strip():
                label = normalized_attrs["aria-label"].strip()
                identity_base = f'{self.surface}[aria-label="{label}"]'
                locator = {
                    "kind": "attribute",
                    "name": "aria-label",
                    "value": label,
                    "occurrence": self._identity_counts[identity_base],
                }
            else:
                class_name = ".".join(normalized_attrs.get("class", "").split())
                identity_base = f"{self.surface}:{normalized_tag}"
                if class_name:
                    identity_base += f".{class_name}"
                locator = {"kind": "tag", "value": normalized_tag, "occurrence": tag_ordinal}

        identity_occurrence = self._identity_counts[identity_base]
        self._identity_counts[identity_base] += 1
        stable_id = identity_base if identity_occurrence == 0 else f"{identity_base}@{identity_occurrence + 1}"
        self.controls.append(
            {
                "stable_id": stable_id,
                "surface": self.surface,
                "tag": normalized_tag,
                "type": normalized_attrs.get("type", "").casefold(),
                "role": normalized_attrs.get("role", "").casefold(),
                "id": element_id,
                "locator": locator,
            }
        )


def _static_control_descriptors(repo_root: Path) -> list[dict[str, object]]:
    descriptors: list[dict[str, object]] = []
    static_root = repo_root / "apps" / "desktop" / "webview" / "static"
    for surface, expected_count in _SURFACE_EXPECTED_COUNTS.items():
        source = static_root / "partials" / f"page-{surface}.html"
        parser = _StaticInteractiveParser(surface)
        parser.feed(settings_markup(static_root) if surface == "settings" else source.read_text(encoding="utf-8"))
        parser.close()
        if len(parser.controls) != expected_count:
            raise AssertionError(
                f"{surface} static interactive-control denominator changed: "
                f"expected {expected_count}, found {len(parser.controls)}"
            )
        descriptors.extend(parser.controls)
    stable_ids = [str(item["stable_id"]) for item in descriptors]
    if len(stable_ids) != len(set(stable_ids)):
        duplicates = sorted(name for name, count in Counter(stable_ids).items() if count > 1)
        raise AssertionError(f"Static control stable IDs are not unique: {duplicates}")
    return descriptors


def _browser_settings_control_census_runner_source() -> str:
    return browser_cdp_runner_prelude() + textwrap.dedent(
        r"""
        async function browserSettingsControlCensus(data) {
          const descriptors = Array.isArray(data.descriptors) ? data.descriptors : [];
          const expectedSurfaceCounts = { settings: 325, libraries: 17, schedule: 10 };
          const classifications = {};
          const finiteValues = {};
          const blockedFiniteValues = {};
          const eventEvidence = {};
          const unexpectedPostRequests = [];
          const originalFetch = window.fetch.bind(window);
          const originalConfirm = window.confirm;
          const originalAlert = window.alert;

          const localButtonIds = new Set([
            "settings-wizard-add-library-button",
            "settings-wizard-copy-diagnostics-button",
            "settings-wizard-back-button",
            "settings-deployment-start-button",
            "settings-deployment-repair-button",
            "settings-deployment-launch-button",
            "settings-open-wizard-button",
            "settings-builder-apply-button",
            "settings-builder-reset-button",
            "settings-summarize-patch-button",
            "settings-video-apply-button",
            "settings-video-reset-button",
            "settings-quality-apply-button",
            "settings-quality-reset-button",
            "settings-file-safety-apply-button",
            "settings-file-safety-reset-button",
            "settings-pending-apply-button",
            "settings-pending-reset-button",
            "settings-subtitle-apply-button",
            "settings-subtitle-reset-button",
            "settings-audio-apply-button",
            "settings-audio-reset-button",
            "settings-rename-workbench-stage-suggestions-button",
            "settings-rename-cleaning-filters-reset-button",
            "settings-queue-apply-button",
            "settings-queue-reset-button",
            "settings-runtime-apply-button",
            "settings-runtime-reset-button",
            "settings-library-add-button",
            "settings-library-delete-button",
            "settings-library-defaults-button",
            "settings-library-reset-button",
            "settings-library-build-patch-button",
            "settings-library-watch-stage-button",
            "schedule-editor-load-current-button",
            "schedule-editor-clear-button",
            "schedule-editor-allow-all-button",
          ]);
          const backendCommandButtonIds = new Set([
            "settings-save-header-save-button",
            "settings-save-header-reload-button",
            "settings-wizard-validate-paths-button",
            "settings-wizard-detect-tools-button",
            "settings-wizard-probe-hardware-button",
            "settings-wizard-validate-workers-button",
            "settings-wizard-preview-button",
            "settings-wizard-next-button",
            "settings-preset-library-load",
            "settings-preset-library-validate",
            "settings-preset-library-compare",
            "settings-preset-library-import-preview",
            "settings-preset-library-export",
            "settings-preset-library-apply-preview",
            "settings-deployment-verify-button",
            "settings-validate-button",
            "settings-reload-button",
            "settings-save-patch-button",
            "settings-rename-workbench-test-button",
            "settings-rename-workbench-retest-button",
            "settings-library-scan-sources-button",
            "settings-library-preview-button",
            "settings-library-watch-preview-button",
            "schedule-editor-preview-button",
          ]);
          const backendMutationButtonIds = new Set([
            "settings-wizard-save-button",
            "settings-preset-library-save",
            "settings-preset-library-apply",
            "settings-rename-workbench-save-filters-button",
            "settings-rename-workbench-save-case-button",
            "settings-library-save-button",
            "settings-library-watch-save-button",
            "schedule-editor-save-button",
          ]);

          function record(stableId, status, reason, extra) {
            if (classifications[stableId]) {
              throw new Error("duplicate classification for " + stableId);
            }
            classifications[stableId] = Object.assign({ status, reason }, extra || {});
          }
          function panelFor(surface) {
            return document.querySelector('[data-page-panel="' + surface + '"]');
          }
          function resolveControl(descriptor) {
            const panel = panelFor(descriptor.surface);
            if (!panel) return null;
            const locator = descriptor.locator || {};
            let node = null;
            if (locator.kind === "id") {
              node = document.getElementById(String(locator.value || ""));
            } else if (locator.kind === "attribute") {
              const name = String(locator.name || "");
              const value = String(locator.value || "");
              const matches = Array.from(panel.querySelectorAll("[" + name + "]"))
                .filter((candidate) => candidate.getAttribute(name) === value);
              node = matches[Number(locator.occurrence || 0)] || null;
            } else if (locator.kind === "tag") {
              node = panel.querySelectorAll(String(locator.value || ""))[Number(locator.occurrence || 0)] || null;
            }
            return node && panel.contains(node) ? node : null;
          }
          function observe(node, stableId, eventNames) {
            const observed = [];
            eventNames.forEach((eventName) => {
              node.addEventListener(eventName, (event) => {
                observed.push({ type: event.type, key: event.key || "" });
              });
            });
            eventEvidence[stableId] = observed;
            return observed;
          }
          function dispatchFormEvents(node) {
            node.dispatchEvent(new Event("input", { bubbles: true }));
            node.dispatchEvent(new Event("change", { bubbles: true }));
          }
          function enabledOptionValues(node) {
            return Array.from(node.options || []).filter((option) => !option.disabled).map((option) => String(option.value));
          }
          function disabledOptionValues(node) {
            return Array.from(node.options || []).filter((option) => option.disabled).map((option) => String(option.value));
          }
          function alternateTextValue(node, stableId) {
            const original = String(node.value || "");
            if (stableId.endsWith("#settings-patch-json")) return original + " ";
            if (node.type === "number" || node.type === "range") {
              const min = node.getAttribute("min");
              const max = node.getAttribute("max");
              if (min !== null && String(min) !== original) return String(min);
              if (max !== null && String(max) !== original) return String(max);
              return original === "1" ? "2" : "1";
            }
            return original === "census-local-value" ? "census-local-value-2" : "census-local-value";
          }
          function closeOpenDialogs() {
            document.querySelectorAll("dialog[open]").forEach((dialog) => {
              try { dialog.close(); } catch (_error) { dialog.removeAttribute("open"); }
            });
          }
          function isLocalButton(node) {
            if (node.hasAttribute("data-settings-tab")) return true;
            if (node.hasAttribute("data-wizard-step-button")) return true;
            if (node.hasAttribute("data-cross-page-target")) return true;
            return localButtonIds.has(String(node.id || ""));
          }
          function buttonPostcondition(node) {
            if (node.hasAttribute("data-settings-tab")) {
              return node.getAttribute("aria-current") === "location";
            }
            if (node.hasAttribute("data-wizard-step-button")) {
              return node.getAttribute("aria-current") === "step";
            }
            if (node.hasAttribute("data-cross-page-target")) {
              const target = node.getAttribute("data-cross-page-target");
              return panelFor(target)?.classList.contains("is-visible") === true;
            }
            return true;
          }

          const nodes = new Map();
          descriptors.forEach((descriptor) => {
            const node = resolveControl(descriptor);
            if (node) nodes.set(descriptor.stable_id, node);
            else record(descriptor.stable_id, "failed", "missing_runtime_control");
          });

          const resolvedSurfaceCounts = { settings: 0, libraries: 0, schedule: 0 };
          descriptors.forEach((descriptor) => {
            if (nodes.has(descriptor.stable_id)) resolvedSurfaceCounts[descriptor.surface] += 1;
          });
          Object.entries(expectedSurfaceCounts).forEach(([surface, expected]) => {
            if (resolvedSurfaceCounts[surface] !== expected) {
              throw new Error(surface + " runtime resolution mismatch: expected " + expected + ", found " + resolvedSurfaceCounts[surface]);
            }
          });

          window.fetch = async (input, init) => {
            const method = String((init && init.method) || "GET").toUpperCase();
            if (method !== "GET" && method !== "HEAD") {
              unexpectedPostRequests.push({ method, url: String(input || "") });
              return new Response(JSON.stringify({ ok: false, message: "Control census blocked a non-read request." }), {
                status: 409,
                headers: { "Content-Type": "application/json" },
              });
            }
            return originalFetch(input, init);
          };
          window.confirm = () => true;
          window.alert = () => {};

          try {
            for (const descriptor of descriptors) {
              const stableId = descriptor.stable_id;
              if (classifications[stableId]) continue;
              const node = nodes.get(stableId);
              if (!node) continue;
              if (typeof window.showPage === "function" && !panelFor(descriptor.surface)?.classList.contains("is-visible")) {
                window.showPage(descriptor.surface);
                await new Promise((resolve) => setTimeout(resolve, 25));
              }

              if (descriptor.tag === "input" || descriptor.tag === "select" || descriptor.tag === "textarea") {
                const inputType = String(node.type || descriptor.type || "").toLowerCase();
                if (inputType === "hidden") {
                  record(stableId, "skipped", "hidden_non_operator_state");
                  continue;
                }
                if (node.disabled) {
                  record(stableId, "blocked", "disabled_in_current_supported_state");
                  continue;
                }
                if (node.readOnly) {
                  record(stableId, "blocked", "readonly_in_current_supported_state");
                  continue;
                }
                const observed = observe(node, stableId, ["click", "input", "change"]);
                if (descriptor.tag === "select") {
                  const original = String(node.value || "");
                  const values = enabledOptionValues(node);
                  const disabledValues = disabledOptionValues(node);
                  if (!values.length) {
                    record(stableId, "blocked", "no_enabled_finite_values", { blocked_values: disabledValues });
                    continue;
                  }
                  for (const value of values) {
                    node.value = value;
                    dispatchFormEvents(node);
                  }
                  node.value = original;
                  dispatchFormEvents(node);
                  finiteValues[stableId] = values;
                  if (disabledValues.length) blockedFiniteValues[stableId] = disabledValues;
                  if (!observed.some((entry) => entry.type === "input") || !observed.some((entry) => entry.type === "change")) {
                    throw new Error("select did not emit input/change events: " + stableId);
                  }
                  record(stableId, "activated", "all_enabled_select_values_dispatched", { value_count: values.length });
                  continue;
                }
                if (inputType === "checkbox") {
                  const original = Boolean(node.checked);
                  const observedValues = [];
                  for (const desired of [false, true]) {
                    node.checked = desired;
                    dispatchFormEvents(node);
                    observedValues.push(desired);
                  }
                  node.checked = original;
                  dispatchFormEvents(node);
                  finiteValues[stableId] = Array.from(new Set(observedValues)).sort();
                  if (finiteValues[stableId].length !== 2) {
                    throw new Error("checkbox did not reach both finite values: " + stableId);
                  }
                  if (!observed.some((entry) => entry.type === "change")) {
                    throw new Error("checkbox did not emit a change event: " + stableId);
                  }
                  record(stableId, "activated", "both_checkbox_values_activated", { value_count: 2 });
                  continue;
                }
                if (inputType === "radio") {
                  node.click();
                  finiteValues[stableId] = [String(node.value || "on")];
                  if (!observed.some((entry) => entry.type === "click")) {
                    throw new Error("radio did not emit a click event: " + stableId);
                  }
                  record(stableId, "activated", "radio_value_activated", { value_count: 1 });
                  continue;
                }
                const original = String(node.value || "");
                node.value = alternateTextValue(node, stableId);
                dispatchFormEvents(node);
                node.value = original;
                dispatchFormEvents(node);
                if (!observed.some((entry) => entry.type === "input") || !observed.some((entry) => entry.type === "change")) {
                  throw new Error("form control did not emit input/change events: " + stableId);
                }
                record(stableId, "activated", inputType === "range" ? "range_bounds_dispatched" : "editable_value_dispatched");
                continue;
              }

              if (descriptor.tag === "summary") {
                const details = node.closest("details");
                if (!details) {
                  record(stableId, "failed", "summary_missing_details_owner");
                  continue;
                }
                const observed = observe(node, stableId, ["click"]);
                const original = details.open;
                node.click();
                await new Promise((resolve) => setTimeout(resolve, 0));
                const first = details.open;
                node.click();
                await new Promise((resolve) => setTimeout(resolve, 0));
                const second = details.open;
                if (first === original || second !== original || !observed.some((entry) => entry.type === "click")) {
                  throw new Error("summary disclosure did not toggle open/closed: " + stableId);
                }
                record(stableId, "activated", "disclosure_open_close_activated");
                continue;
              }

              const isCustomQuickLink = node.hasAttribute("data-ui-quick-link")
                && (descriptor.role === "button" || Number(node.getAttribute("tabindex")) >= 0);
              if (isCustomQuickLink) {
                const observed = observe(node, stableId, ["click", "keydown"]);
                for (const mode of ["click", "Enter", " "]) {
                  node.focus();
                  const handled = mode === "click"
                    ? !node.dispatchEvent(new MouseEvent("click", { bubbles: true, cancelable: true }))
                    : !node.dispatchEvent(new KeyboardEvent("keydown", { key: mode, bubbles: true, cancelable: true }));
                  await new Promise((resolve) => setTimeout(resolve, 10));
                  if (!handled) {
                    throw new Error("custom quick link did not consume " + mode + " activation: " + stableId);
                  }
                }
                const keys = observed.filter((entry) => entry.type === "keydown").map((entry) => entry.key);
                if (!observed.some((entry) => entry.type === "click") || !keys.includes("Enter") || !keys.includes(" ")) {
                  throw new Error("custom quick link lacked click/Enter/Space event evidence: " + stableId);
                }
                record(stableId, "activated", "custom_click_enter_space_activated");
                continue;
              }

              if (descriptor.tag === "button") {
                const id = String(node.id || "");
                if (node.hasAttribute("data-path-picker-target") || id.includes("path-picker") || id.endsWith("-browse")) {
                  record(stableId, "skipped", "native_or_backend_path_picker_not_invoked");
                  continue;
                }
                if (backendMutationButtonIds.has(id)) {
                  if (node.disabled) record(stableId, "blocked", "backend_mutation_not_ready_and_not_invoked");
                  else record(stableId, "skipped", "backend_mutation_not_invoked");
                  continue;
                }
                if (backendCommandButtonIds.has(id)) {
                  record(stableId, "skipped", "backend_command_not_required_for_local_control_census");
                  continue;
                }
                if (!isLocalButton(node)) {
                  record(stableId, "unclassified", "button_missing_explicit_effect_classification");
                  continue;
                }
                if (node.disabled) {
                  record(stableId, "blocked", "local_control_disabled_in_current_supported_state");
                  continue;
                }
                if (id === "settings-wizard-next-button") {
                  document.querySelector('[data-wizard-step-button="0"]')?.click();
                }
                const observed = observe(node, stableId, ["click"]);
                node.click();
                await new Promise((resolve) => setTimeout(resolve, 0));
                if (!observed.some((entry) => entry.type === "click")) {
                  throw new Error("button did not emit click event: " + stableId);
                }
                if (!buttonPostcondition(node)) {
                  throw new Error("button final-state postcondition failed: " + stableId);
                }
                closeOpenDialogs();
                record(stableId, "activated", "local_button_click_activated");
                continue;
              }

              record(stableId, "unclassified", "interactive_kind_missing_activation_strategy");
            }
          } finally {
            window.fetch = originalFetch;
            window.confirm = originalConfirm;
            window.alert = originalAlert;
            closeOpenDialogs();
          }

          const allIds = descriptors.map((descriptor) => descriptor.stable_id);
          const idsForStatus = (status) => allIds.filter((stableId) => classifications[stableId]?.status === status);
          const activatedIds = idsForStatus("activated");
          const skippedIds = idsForStatus("skipped");
          const blockedIds = idsForStatus("blocked");
          const failedIds = idsForStatus("failed");
          const unclassifiedIds = idsForStatus("unclassified");
          const classifiedIds = new Set(Object.keys(classifications));
          const omittedIds = allIds.filter((stableId) => !classifiedIds.has(stableId));
          if (omittedIds.length) throw new Error("census omitted controls: " + JSON.stringify(omittedIds));
          if (unclassifiedIds.length) throw new Error("census has unclassified controls: " + JSON.stringify(unclassifiedIds));
          if (failedIds.length) throw new Error("census has failed controls: " + JSON.stringify(failedIds));
          const reversiblePreferenceRequests = unexpectedPostRequests.filter((request) => request.url.endsWith("/api/ui-preferences"));
          const prohibitedPostRequests = unexpectedPostRequests.filter((request) => !request.url.endsWith("/api/ui-preferences"));
          if (prohibitedPostRequests.length) {
            throw new Error("local census attempted non-read backend requests: " + JSON.stringify(prohibitedPostRequests));
          }

          return {
            discovered_count: allIds.length,
            surface_counts: resolvedSurfaceCounts,
            activated_count: activatedIds.length,
            skipped_count: skippedIds.length,
            blocked_count: blockedIds.length,
            failed_count: failedIds.length,
            unclassified_count: unclassifiedIds.length,
            discovered_ids: allIds,
            activated_ids: activatedIds,
            skipped_ids: skippedIds,
            blocked_ids: blockedIds,
            failed_ids: failedIds,
            unclassified_ids: unclassifiedIds,
            classifications: classifications,
            finite_values: finiteValues,
            blocked_finite_values: blockedFiniteValues,
            event_evidence: eventEvidence,
            unexpected_post_requests: prohibitedPostRequests,
            blocked_reversible_preference_requests: reversiblePreferenceRequests,
          };
        }

        async function main() {
          const userDataDir = fs.mkdtempSync(`${payload.tmpRoot.replace(/\\/g, "/")}/chrome-profile-`);
          const browser = launchBrowser([
            "--headless=new",
            "--disable-gpu",
            "--disable-background-networking",
            "--disable-default-apps",
            "--disable-extensions",
            "--disable-sync",
            "--metrics-recording-only",
            "--no-first-run",
            "--no-default-browser-check",
            `--remote-debugging-port=${payload.port}`,
            `--user-data-dir=${userDataDir}`,
            payload.url,
          ]);
          let client = null;
          try {
            const wsUrl = await waitForPageWebSocket(payload.port, payload.url);
            client = createCdpClient(wsUrl);
            await client.send("Runtime.enable");
            await client.send("Log.enable");
            await client.send("Page.enable");
            const readyExpression = `Boolean(
              document.getElementById("settings-patch-json")
              && document.getElementById("settings-library-profile-list")
              && document.getElementById("schedule-editor-rows")
              && typeof window.showPage === "function"
              && typeof window.mediaPipelineSettingsView?.renderSettings === "function"
              && typeof window.mediaPipelineSettingsLibraries?.initSettingsLibrariesEvents === "function"
              && typeof window.mediaPipelineScheduleView?.scheduleEditorRequest === "function"
            )`;
            const deadline = Date.now() + 30000;
            let ready = false;
            while (Date.now() < deadline) {
              const probe = await client.send("Runtime.evaluate", { expression: readyExpression, returnByValue: true });
              if (probe.result?.value === true) {
                ready = true;
                break;
              }
              await sleep(150);
            }
            if (!ready) {
              const diagnostic = await client.send("Runtime.evaluate", {
                expression: `({
                  readyState: document.readyState,
                  patch: Boolean(document.getElementById("settings-patch-json")),
                  libraryList: Boolean(document.getElementById("settings-library-profile-list")),
                  scheduleRows: Boolean(document.getElementById("schedule-editor-rows")),
                  showPage: typeof window.showPage,
                  settingsView: typeof window.mediaPipelineSettingsView?.renderSettings,
                  librariesView: typeof window.mediaPipelineSettingsLibraries?.initSettingsLibrariesEvents,
                  scheduleView: typeof window.mediaPipelineScheduleView?.scheduleEditorRequest,
                })`,
                returnByValue: true,
              });
              throw new Error("Settings/Libraries/Schedule controls did not become ready: " + JSON.stringify(diagnostic.result?.value || {}));
            }
            await sleep(750);
            const expression = `(${browserSettingsControlCensus.toString()})(${JSON.stringify({
              descriptors: payload.descriptors,
            })})`;
            const evaluation = await client.send("Runtime.evaluate", {
              expression,
              awaitPromise: true,
              returnByValue: true,
            });
            if (evaluation.exceptionDetails) {
              const details = evaluation.exceptionDetails;
              throw new Error(details.exception?.description || details.exception?.value || details.text || "browser census failed");
            }
            await sleep(300);
            const errorEvents = client.consoleEvents.filter((entry) => entry.startsWith("error:") || entry.startsWith("warning:"));
            if (client.exceptions.length || errorEvents.length) {
              throw new Error(`Browser console/exception noise: ${client.exceptions.concat(errorEvents).join("; ")}`);
            }
            console.log(JSON.stringify({ ok: true, result: evaluation.result?.value || {} }));
          } finally {
            if (client) client.close();
            await terminateBrowser(browser);
          }
        }

        main().catch((error) => {
          console.error(error.stack || error.message || String(error));
          process.exit(1);
        });
        """
    )


def _run_browser_settings_control_census(
    *, browser_path: str, url: str, descriptors: list[dict[str, object]]
) -> dict[str, object]:
    node = shutil.which("node")
    if not node:
        raise unittest.SkipTest("Node.js is required for the browser-backed Settings control census.")
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as raw_tmp:
        tmp = Path(raw_tmp)
        payload_path = tmp / "browser-settings-control-census-payload.json"
        runner_path = tmp / "browser-settings-control-census-runner.cjs"
        payload_path.write_text(
            json.dumps(
                {
                    "browserPath": browser_path,
                    "port": free_port(),
                    "tmpRoot": str(tmp),
                    "url": url,
                    "descriptors": descriptors,
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        runner_path.write_text(_browser_settings_control_census_runner_source(), encoding="utf-8")
        return run_node_browser_smoke(
            "Browser-backed Settings/Libraries/Schedule static control census",
            node=node,
            runner_path=runner_path,
            payload_path=payload_path,
            timeout_seconds=120,
        )


class WebViewBrowserSettingsControlCensusSmoke(unittest.TestCase):
    def test_static_controls_are_fully_classified_and_safe_local_controls_activate(self) -> None:
        browser_path = find_browser()
        if not browser_path:
            raise unittest.SkipTest("Chrome or Edge is required for the browser-backed Settings control census.")

        repo_root = find_repo_root(Path(__file__))
        descriptors = _static_control_descriptors(repo_root)
        self.assertEqual(len(descriptors), 352)

        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            resolved, _source, _output = _write_fixture_state(root)
            resolved.config_data.update(
                {
                    "SourceMovies": str(root / "Movies"),
                    "SourceTV": str(root / "TV"),
                    "Outsource": str(root / "Outsource"),
                    "LocalBase": str(root),
                }
            )
            service = DummyWorkflowFacadeService(root)
            resolved.config_path.write_text(service.serialize_psd1_document(resolved.config_data), encoding="utf-8")
            media_snapshot = capture_media_no_mutation_snapshot(root)
            facade = MediaPipelineApplicationFacade(service, app_version="v6-settings-control-census")
            server = LocalApiServer(
                facade,
                token="browser-settings-control-census-token",
                resolved_provider=lambda: resolved,
                resolved_reload=lambda: resolved,
                audit_root_provider=lambda: str(root),
            )
            try:
                server.start()
                result = _run_browser_settings_control_census(
                    browser_path=browser_path,
                    url=f"{server.url}/",
                    descriptors=descriptors,
                )
            finally:
                server.stop()
            assert_media_no_mutation(self, media_snapshot)

        census = result["result"]
        evidence_path = os.environ.get("MEDIAPIPELINE_WEBVIEW_TOUCHPOINT_EVIDENCE", "").strip()
        if evidence_path:
            Path(evidence_path).write_text(
                json.dumps(
                    {
                        "schema_version": "webview-touchpoint-evidence.v1",
                        "scope": ["settings", "libraries", "schedule"],
                        "source_denominators": _SURFACE_EXPECTED_COUNTS,
                        "descriptors": descriptors,
                        "browser_result": census,
                    },
                    indent=2,
                    ensure_ascii=False,
                )
                + "\n",
                encoding="utf-8",
            )
        self.assertEqual(census["discovered_count"], 352)
        self.assertEqual(census["surface_counts"], _SURFACE_EXPECTED_COUNTS)
        self.assertEqual(census["failed_count"], 0, census["failed_ids"])
        self.assertEqual(census["unclassified_count"], 0, census["unclassified_ids"])
        self.assertEqual(census["unexpected_post_requests"], [])
        self.assertEqual(
            census["activated_count"] + census["skipped_count"] + census["blocked_count"],
            census["discovered_count"],
        )
        self.assertEqual(census["discovered_ids"], [item["stable_id"] for item in descriptors])

        static_select_ids = {
            str(item["stable_id"]) for item in descriptors if item["tag"] == "select"
        }
        static_checkbox_ids = {
            str(item["stable_id"])
            for item in descriptors
            if item["tag"] == "input" and item["type"] == "checkbox"
        }
        activated_or_blocked = set(census["activated_ids"]) | set(census["blocked_ids"])
        self.assertTrue(static_select_ids <= activated_or_blocked)
        self.assertTrue(static_checkbox_ids <= activated_or_blocked)
        for stable_id in static_select_ids & set(census["activated_ids"]):
            self.assertGreaterEqual(len(census["finite_values"][stable_id]), 1)
        for stable_id in static_checkbox_ids & set(census["activated_ids"]):
            self.assertEqual(census["finite_values"][stable_id], [False, True])


if __name__ == "__main__":
    unittest.main()
