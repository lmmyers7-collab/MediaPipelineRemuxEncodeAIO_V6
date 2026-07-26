from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

from mediapipeline.tools.paths import find_repo_root

sys.path.insert(0, str(find_repo_root(Path(__file__)) / "src"))

from mediapipeline.desktop.api import LocalApiServer
from mediapipeline.desktop.application import MediaPipelineApplicationFacade

try:  # unittest discovery can import tests as top-level modules or package modules.
    from .test_application_facade import DummyWorkflowFacadeService
    from .test_webview_browser_settings_control_census_smoke import _static_control_descriptors
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
    from test_webview_browser_settings_control_census_smoke import _static_control_descriptors
    from test_webview_real_media_smoke import _write_fixture_state
    from webview_browser_smoke_support import (
        assert_media_no_mutation,
        browser_cdp_runner_prelude,
        capture_media_no_mutation_snapshot,
        find_browser,
        free_port,
        run_node_browser_smoke,
    )


_EXPECTED_SURFACES = ("settings", "libraries", "schedule")


def _browser_generated_control_census_runner_source() -> str:
    return browser_cdp_runner_prelude() + textwrap.dedent(
        r"""
        async function browserGeneratedControlCensus(data) {
          const authoredDescriptors = Array.isArray(data.authoredDescriptors) ? data.authoredDescriptors : [];
          const nativeTags = new Set(["button", "input", "select", "summary", "textarea"]);
          const interactiveRoles = new Set([
            "button", "checkbox", "gridcell", "link", "menuitem", "menuitemcheckbox",
            "menuitemradio", "option", "radio", "row", "switch", "tab", "treeitem",
          ]);
          const panelFor = (surface) => document.querySelector('[data-page-panel="' + surface + '"]');

          function exactInteractive(node) {
            const tag = String(node?.tagName || "").toLowerCase();
            if (nativeTags.has(tag)) return true;
            if (tag === "a" && node.hasAttribute("href")) return true;
            if (interactiveRoles.has(String(node.getAttribute?.("role") || "").trim().toLowerCase())) return true;
            const raw = String(node.getAttribute?.("tabindex") || "").trim();
            return raw !== "" && Number.isInteger(Number(raw)) && Number(raw) >= 0;
          }

          function resolveAuthored(descriptor) {
            const panel = panelFor(descriptor.surface);
            const locator = descriptor.locator || {};
            if (!panel) return null;
            if (locator.kind === "id") {
              const node = document.getElementById(String(locator.value || ""));
              return node && panel.contains(node) ? node : null;
            }
            if (locator.kind === "attribute") {
              const name = String(locator.name || "");
              const value = String(locator.value || "");
              return Array.from(panel.querySelectorAll("[" + name + "]"))
                .filter((node) => node.getAttribute(name) === value)[Number(locator.occurrence || 0)] || null;
            }
            if (locator.kind === "tag") {
              return panel.querySelectorAll(String(locator.value || ""))[Number(locator.occurrence || 0)] || null;
            }
            return null;
          }

          const authoredNodes = new Set(authoredDescriptors.map(resolveAuthored).filter(Boolean));
          if (authoredNodes.size !== authoredDescriptors.length) {
            throw new Error("authored control resolution mismatch: " + authoredNodes.size + "/" + authoredDescriptors.length);
          }

          function controlFamily(node, surface) {
            if (node.closest("section.panel[data-panel-key] .panel-customize-bar")) {
              if (node.matches(".pcb-btn-move-up")) return "layout-panel-move-up";
              if (node.matches(".pcb-btn-move-down")) return "layout-panel-move-down";
              if (node.matches(".pcb-btn-advanced")) return "layout-panel-advanced-toggle";
              if (node.matches(".pcb-btn-hidden")) return "layout-panel-hidden-toggle";
            }
            if (node.matches(".table-sort-button")) return "table-column-sort";
            if (node.matches(".table-column-resizer")) return "table-column-resize";
            if (node.matches(".table-column-menu > summary")) return "table-column-menu";
            if (node.matches('.table-column-menu input[type="checkbox"]')) return "table-column-visibility";
            if (node.matches(".diagnostic-callout details > summary")) return "diagnostic-why-disclosure";
            if (node.matches(".summary-toggle[aria-controls]")) return "generated-summary-toggle";
            if (node.matches('[data-selectable-row="true"][tabindex]')) return "generated-selectable-row";
            if (node.closest('[data-page-empty-state="panel-visibility"]')) return "page-empty-state-recovery";
            if (surface === "schedule") {
              if (node.matches('[id*="-block-"]')) return "schedule-time-block";
              if (node.matches('[id$="-clear-day"]')) return "schedule-day-clear";
              if (node.matches('[id$="-allow-day"]')) return "schedule-day-allow-all";
              if (node.matches('[id$="-copy-day"]')) return "schedule-day-copy";
              if (node.matches('[id$="-paste-day"]')) return "schedule-day-paste";
              if (node.matches('[id$="-windows"]')) return "schedule-hidden-window-state";
            }
            if (node.matches("[data-settings-advanced-toggle]")) return "settings-advanced-toggle";
            if (node.matches('[type="radio"][id*="-choice-"]')) return "settings-wizard-enhanced-choice";
            if (node.closest(".settings-wizard-library-row")) {
              if (node.matches("[data-path-picker-target]")) return "settings-wizard-library-path-picker";
              if (node.matches("[data-library-remove]")) return "settings-wizard-library-remove";
              return "settings-wizard-library-field";
            }
            if (surface === "libraries") {
              if (node.matches("[data-library-profile-nav]")) return "libraries-profile-navigation";
              if (node.matches("[data-library-summary-row]")) return "libraries-summary-tile";
              if (node.matches("[data-library-summary-inspect] > summary")) return "libraries-summary-inspect";
              if (node.matches("[data-path-picker-target]")) return "libraries-path-picker";
              if (node.matches("[data-library-override-section] > summary")) return "libraries-override-section";
              if (node.matches("[data-library-advanced-disclosure] > summary")) return "libraries-advanced-disclosure";
              if (node.matches("[data-library-route-boundary-input]")) return "libraries-route-boundary-input";
              if (node.matches("[data-library-route-boundary-reset]")) return "libraries-route-boundary-reset";
              if (node.matches("[data-library-compatibility-select]")) return "libraries-compatibility-select";
              if (node.matches("[data-library-use-default-override]")) return "libraries-override-reset";
              if (node.matches("[data-library-use-default]")) return "libraries-path-reset";
              if (node.matches("[data-library-override-control]")) return "libraries-override-control";
              if (node.matches("[data-library-field]")) return "libraries-profile-field";
            }
            return "unclassified-family";
          }

          function stableId(node, surface, family) {
            if (node.id) return surface + "#" + node.id;
            const panel = node.closest("section.panel[data-panel-key]");
            if (panel && family.startsWith("layout-panel-")) {
              return surface + ":panel:" + String(panel.dataset.panelKey || "missing") + ":" + family.replace("layout-panel-", "");
            }
            const table = node.closest("table");
            const toolbar = node.closest("[data-table-toolbar-for]");
            if (family.startsWith("table-column-")) {
              const tableId = String(table?.id || toolbar?.dataset.tableToolbarFor || "missing");
              const header = node.closest("th");
              const column = String(header?.dataset.tableColumnIndex || node.getAttribute("aria-label") || "menu");
              return surface + ":table:" + tableId + ":" + family.replace("table-column-", "") + ":" + column;
            }
            if (family === "diagnostic-why-disclosure") {
              const root = node.closest(".diagnostic-callout");
              const owner = root?.id || root?.closest("[id]")?.id || "missing";
              return surface + ":diagnostic:" + owner + ":why";
            }
            if (family === "generated-summary-toggle") {
              return surface + ":summary-toggle:" + String(node.getAttribute("aria-controls") || "missing");
            }
            if (family === "generated-selectable-row") {
              const tbody = node.closest("tbody");
              const rowKey = String(node.cells?.[0]?.textContent || node.getAttribute("aria-label") || "missing").trim().replace(/\s+/g, " ");
              return surface + ":selectable-row:" + String(tbody?.id || "missing") + ":" + rowKey;
            }
            if (family === "page-empty-state-recovery") {
              return surface + ":page-empty-recovery:" + String(node.textContent || "missing").trim().toLowerCase().replace(/\s+/g, "-");
            }
            if (family === "settings-advanced-toggle") {
              return "settings:advanced-toggle:" + String(node.closest('[data-settings-tab]')?.dataset.settingsTab || "missing");
            }
            const wizardRow = node.closest(".settings-wizard-library-row");
            if (wizardRow) {
              const libraryId = String(wizardRow.dataset.libraryId || ("row-" + wizardRow.dataset.libraryIndex));
              const semantic = node.getAttribute("data-library-field")
                || node.getAttribute("data-path-picker-target")
                || (node.hasAttribute("data-library-remove") ? "remove" : "missing");
              return "settings:wizard-library:" + libraryId + ":" + semantic;
            }
            if (node.matches("[data-library-profile-nav]")) {
              return "libraries:profile-nav:" + node.getAttribute("data-library-profile-nav");
            }
            if (node.matches("[data-library-summary-row]")) {
              return "libraries:summary-tile:" + node.getAttribute("data-library-summary-row");
            }
            if (node.matches("[data-library-summary-inspect] > summary")) {
              return "libraries:summary-inspect:" + String(node.closest("[data-library-summary-row]")?.getAttribute("data-library-summary-row") || "missing");
            }
            const card = node.closest("[data-library-id]");
            if (card) {
              const libraryId = String(card.getAttribute("data-library-id") || "missing");
              let semantic = "";
              if (node.matches("[data-path-picker-target]")) semantic = "path-picker:" + node.getAttribute("data-path-picker-target");
              else if (node.matches("[data-library-field]")) semantic = "field:" + node.getAttribute("data-library-field");
              else if (node.matches("[data-library-use-default]")) semantic = "path-reset:" + node.getAttribute("data-library-use-default");
              else if (node.matches("[data-library-override-control]")) semantic = "override:" + node.getAttribute("data-library-override-key");
              else if (node.matches("[data-library-use-default-override]")) semantic = "override-reset:" + node.getAttribute("data-library-override-key");
              else if (node.matches("[data-library-route-boundary-input]")) semantic = "route-boundary:" + node.getAttribute("data-library-route-boundary-input");
              else if (node.matches("[data-library-route-boundary-reset]")) semantic = "route-boundary-reset:" + node.getAttribute("data-library-route-boundary-reset");
              else if (node.matches("[data-library-compatibility-select]")) semantic = "compatibility:" + String(node.closest("[data-library-compatibility-preset]")?.getAttribute("data-library-compatibility-preset") || "missing");
              else if (node.matches("[data-library-override-section] > summary")) semantic = "override-section:" + String(node.parentElement?.getAttribute("data-library-override-section") || "missing");
              else if (node.matches("[data-library-advanced-disclosure] > summary")) {
                const group = node.closest("[data-library-override-section]")?.getAttribute("data-library-override-section") || "missing";
                semantic = "advanced-disclosure:" + group;
              }
              if (semantic) return "libraries:" + libraryId + ":" + semantic;
            }
            const all = Array.from(panelFor(surface).querySelectorAll("*")).filter(exactInteractive).filter((candidate) => !authoredNodes.has(candidate));
            return surface + ":unresolved:" + family + ":" + String(all.indexOf(node));
          }

          function knownGeneratedControl(node) {
            return controlFamily(node, String(node.closest("[data-page-panel]")?.getAttribute("data-page-panel") || "")) !== "unclassified-family";
          }

          const descriptors = [];
          const descriptorById = new Map();
          const nodeById = new Map();
          function registerCurrentControls() {
            for (const surface of ["settings", "libraries", "schedule"]) {
              const panel = panelFor(surface);
              if (!panel) throw new Error("missing surface " + surface);
              Array.from(panel.querySelectorAll("*"))
                .filter(exactInteractive)
                .filter((node) => !authoredNodes.has(node) || knownGeneratedControl(node))
                .forEach((node) => {
                  const family = controlFamily(node, surface);
                  if (family === "unclassified-family" && String(node.tagName || "").toLowerCase() === "summary") return;
                  const id = stableId(node, surface, family);
                  nodeById.set(id, node);
                  if (descriptorById.has(id)) return;
                  const descriptor = {
                    stable_id: id,
                    family,
                    surface,
                    tag: String(node.tagName || "").toLowerCase(),
                    type: String(node.type || "").toLowerCase(),
                    disabled_initially: Boolean(node.disabled),
                    read_only_initially: Boolean(node.readOnly),
                    hidden_initially: Boolean(node.hidden || node.type === "hidden"),
                    label: String(node.getAttribute("aria-label") || node.title || node.textContent || "").trim().replace(/\s+/g, " ").slice(0, 160),
                  };
                  descriptors.push(descriptor);
                  descriptorById.set(id, descriptor);
                });
            }
          }
          registerCurrentControls();
          if (descriptors.some((item) => item.family === "unclassified-family")) {
            throw new Error("unclassified generated controls: " + JSON.stringify(descriptors.filter((item) => item.family === "unclassified-family")));
          }

          const classifications = {};
          const finiteValues = {};
          const eventEvidence = {};
          const requests = [];
          const originalFetch = window.fetch.bind(window);
          const originalConfirm = window.confirm;
          const originalAlert = window.alert;
          const originalStorage = {};
          for (let index = 0; index < localStorage.length; index += 1) {
            const key = localStorage.key(index);
            if (key !== null) originalStorage[key] = localStorage.getItem(key);
          }
          const originalFormState = new Map();
          const originalEnhancedChoiceValues = new Map();
          document.querySelectorAll("[data-enhanced-choice-for]").forEach((group) => {
            const selectId = String(group.getAttribute("data-enhanced-choice-for") || "");
            const select = document.getElementById(selectId);
            if (selectId && select) originalEnhancedChoiceValues.set(selectId, String(select.value || ""));
          });
          descriptors.forEach((descriptor) => {
            const node = nodeById.get(descriptor.stable_id);
            if (node instanceof HTMLInputElement || node instanceof HTMLSelectElement || node instanceof HTMLTextAreaElement) {
              originalFormState.set(descriptor.stable_id, { checked: Boolean(node.checked), value: String(node.value || "") });
            }
          });

          window.fetch = async (input, init) => {
            const method = String(init?.method || "GET").toUpperCase();
            if (method !== "GET" && method !== "HEAD") {
              const request = { method, url: String(input || ""), blocked: true };
              requests.push(request);
              return new Response(JSON.stringify({ ok: false, message: "Generated control census blocked a non-read request." }), {
                status: 409,
                headers: { "Content-Type": "application/json" },
              });
            }
            return originalFetch(input, init);
          };
          window.confirm = () => true;
          window.alert = () => {};

          function record(stableId, status, reason, extra = {}) {
            if (classifications[stableId]) throw new Error("duplicate generated-control classification: " + stableId);
            classifications[stableId] = Object.assign({ status, reason }, extra);
          }
          function observe(node, stableId, names) {
            const counts = {};
            names.forEach((name) => {
              counts[name] = 0;
              node.addEventListener(name, () => { counts[name] += 1; });
            });
            eventEvidence[stableId] = counts;
            return counts;
          }
          function itemsForFamily(family) {
            return descriptors.filter((item) => item.family === family);
          }
          function nodeFor(descriptor) {
            let node = nodeById.get(descriptor.stable_id);
            if (node && !node.isConnected) {
              registerCurrentControls();
              node = nodeById.get(descriptor.stable_id);
            }
            if (!node) throw new Error("missing generated node for " + descriptor.stable_id);
            return node;
          }
          function revealNode(node, surface) {
            if (typeof window.showPage === "function") window.showPage(surface);
            const settingsPane = node.closest('.settings-tab-pane[data-settings-tab]');
            if (settingsPane) {
              const tab = settingsPane.getAttribute("data-settings-tab");
              document.querySelector('.settings-section-nav-btn[data-settings-tab="' + tab + '"]')?.click();
            }
            const wizardStep = node.closest("[data-wizard-step]");
            if (wizardStep) {
              document.querySelector('[data-wizard-step-button="' + wizardStep.getAttribute("data-wizard-step") + '"]')?.click();
            }
            const libraryPane = node.closest("[data-library-profile-pane]");
            if (libraryPane) {
              document.querySelector('[data-library-profile-nav="' + libraryPane.getAttribute("data-library-profile-pane") + '"]')?.click();
            }
            let ancestor = node.parentElement?.closest("details");
            while (ancestor) {
              ancestor.open = true;
              ancestor = ancestor.parentElement?.closest("details");
            }
          }
          function clickAndCount(descriptor, node, reason, times = 1) {
            revealNode(node, descriptor.surface);
            const counts = observe(node, descriptor.stable_id, ["click"]);
            for (let index = 0; index < times; index += 1) node.click();
            if (counts.click < times) throw new Error("click activation did not fire for " + descriptor.stable_id);
            record(descriptor.stable_id, "activated", reason, { activation_count: counts.click });
          }
          function dispatchFormEvents(node) {
            node.dispatchEvent(new Event("input", { bubbles: true }));
            node.dispatchEvent(new Event("change", { bubbles: true }));
          }
          function alternateValue(node) {
            const original = String(node.value || "");
            if (node.type === "number" || node.type === "range") {
              const min = node.getAttribute("min");
              const max = node.getAttribute("max");
              if (min !== null && min !== original) return min;
              if (max !== null && max !== original) return max;
              return original === "1" ? "2" : "1";
            }
            return original === "generated-census-value" ? "generated-census-value-2" : "generated-census-value";
          }
          function activateFormControl(descriptor) {
            const node = nodeFor(descriptor);
            revealNode(node, descriptor.surface);
            if (node.type === "hidden") {
              record(descriptor.stable_id, "skipped", "hidden_non_operator_state");
              return;
            }
            if (node.disabled) {
              record(descriptor.stable_id, "blocked", "disabled_in_current_supported_state");
              return;
            }
            if (node.readOnly) {
              record(descriptor.stable_id, "blocked", "readonly_in_current_supported_state");
              return;
            }
            const counts = observe(node, descriptor.stable_id, ["click", "input", "change"]);
            if (node instanceof HTMLSelectElement) {
              const original = String(node.value || "");
              const values = Array.from(node.options).filter((option) => !option.disabled).map((option) => String(option.value));
              if (!values.length) {
                record(descriptor.stable_id, "blocked", "no_enabled_finite_values");
                return;
              }
              const observedNodes = new WeakSet([node]);
              const bindReplacement = (current) => {
                if (observedNodes.has(current)) return;
                observedNodes.add(current);
                ["click", "input", "change"].forEach((name) => current.addEventListener(name, () => { counts[name] += 1; }));
              };
              values.forEach((value) => {
                const current = nodeFor(descriptor);
                bindReplacement(current);
                current.value = value;
                dispatchFormEvents(current);
              });
              const restored = nodeFor(descriptor);
              bindReplacement(restored);
              restored.value = original;
              dispatchFormEvents(restored);
              finiteValues[descriptor.stable_id] = values;
              if (counts.input < values.length || counts.change < values.length) throw new Error("select events missing for " + descriptor.stable_id);
              record(descriptor.stable_id, "activated", "all_enabled_select_values_activated", { value_count: values.length });
              return;
            }
            if (node.type === "checkbox") {
              const original = Boolean(node.checked);
              const observed = [];
              const observedNodes = new WeakSet([node]);
              const bindReplacement = (current) => {
                if (observedNodes.has(current)) return;
                observedNodes.add(current);
                ["click", "input", "change"].forEach((name) => current.addEventListener(name, () => { counts[name] += 1; }));
              };
              let current = node;
              current.click(); observed.push(Boolean(current.checked));
              current = nodeFor(descriptor);
              bindReplacement(current);
              current.click(); observed.push(Boolean(current.checked));
              current = nodeFor(descriptor);
              bindReplacement(current);
              if (current.checked !== original) current.click();
              if (nodeFor(descriptor).checked !== original) throw new Error("checkbox restoration failed for " + descriptor.stable_id);
              finiteValues[descriptor.stable_id] = Array.from(new Set([original, ...observed])).sort();
              if (finiteValues[descriptor.stable_id].length !== 2 || counts.click < 2 || counts.change < 2) {
                throw new Error("checkbox finite activation failed for " + descriptor.stable_id + ": " + JSON.stringify({ original, observed, finite: finiteValues[descriptor.stable_id], counts, connected: node.isConnected }));
              }
              record(descriptor.stable_id, "activated", "both_checkbox_values_activated", { value_count: 2 });
              return;
            }
            if (node.type === "radio") {
              node.click();
              finiteValues[descriptor.stable_id] = [String(node.value || "on")];
              if (counts.click < 1) throw new Error("radio activation failed for " + descriptor.stable_id);
              record(descriptor.stable_id, "activated", "radio_option_activated", { value_count: 1 });
              return;
            }
            const original = String(node.value || "");
            const candidate = alternateValue(node);
            node.value = candidate;
            dispatchFormEvents(node);
            node.value = original;
            dispatchFormEvents(node);
            finiteValues[descriptor.stable_id] = [candidate, original];
            if (counts.input < 2 || counts.change < 2) throw new Error("editable control events missing for " + descriptor.stable_id);
            record(descriptor.stable_id, "activated", node.type === "number" || node.type === "range" ? "numeric_boundary_value_activated" : "editable_value_activated");
          }
          function activateDisclosure(descriptor) {
            const node = nodeFor(descriptor);
            revealNode(node, descriptor.surface);
            const details = node.closest("details");
            if (!details) throw new Error("generated disclosure lacks details owner: " + descriptor.stable_id);
            const original = Boolean(details.open);
            const counts = observe(node, descriptor.stable_id, ["click"]);
            node.click();
            const first = Boolean(details.open);
            node.click();
            const second = Boolean(details.open);
            if (first === original || second !== original || counts.click < 2) throw new Error("disclosure activation failed for " + descriptor.stable_id);
            record(descriptor.stable_id, "activated", "disclosure_open_close_activated", { activation_count: 2 });
          }
          function activateSelectable(descriptor) {
            const node = nodeFor(descriptor);
            revealNode(node, descriptor.surface);
            const counts = observe(node, descriptor.stable_id, ["click", "keydown"]);
            node.click();
            node.dispatchEvent(new KeyboardEvent("keydown", { key: "Enter", bubbles: true, cancelable: true }));
            node.dispatchEvent(new KeyboardEvent("keydown", { key: " ", bubbles: true, cancelable: true }));
            if (counts.click < 1 || counts.keydown < 2) throw new Error("selectable activation failed for " + descriptor.stable_id);
            record(descriptor.stable_id, "activated", "click_enter_space_activated", { activation_count: 3 });
          }

          try {
            itemsForFamily("page-empty-state-recovery").forEach((descriptor) => {
              record(descriptor.stable_id, "blocked", "hidden_recovery_control_precondition_not_present");
            });
            ["settings-wizard-library-path-picker", "libraries-path-picker"].forEach((family) => {
              itemsForFamily(family).forEach((descriptor) => record(descriptor.stable_id, "skipped", "native_or_backend_path_picker_not_invoked"));
            });

            const customizeButton = document.getElementById("customize-layout-btn");
            const customizeWasOpen = document.body.classList.contains("layout-editor-open");
            if (!customizeWasOpen) customizeButton?.click();
            const panelGroups = new Map();
            descriptors.filter((item) => item.family === "layout-panel-move-up" || item.family === "layout-panel-move-down").forEach((descriptor) => {
              const panel = nodeFor(descriptor).closest("section.panel[data-panel-key]");
              if (!panelGroups.has(panel)) panelGroups.set(panel, {});
              panelGroups.get(panel)[descriptor.family.endsWith("move-up") ? "up" : "down"] = descriptor;
            });
            panelGroups.forEach((pair, panel) => {
              const siblings = Array.from(panel.parentElement?.querySelectorAll(":scope > section.panel[data-panel-key]") || []);
              if (siblings.length <= 1) {
                record(pair.up.stable_id, "blocked", "single_panel_container_has_no_move_target");
                record(pair.down.stable_id, "blocked", "single_panel_container_has_no_move_target");
                return;
              }
              const originalIndex = siblings.indexOf(panel);
              const first = originalIndex > 0 ? pair.up : pair.down;
              const second = originalIndex > 0 ? pair.down : pair.up;
              const firstNode = nodeFor(first);
              const secondNode = nodeFor(second);
              const firstCounts = observe(firstNode, first.stable_id, ["click"]);
              firstNode.click();
              if (firstCounts.click < 1) throw new Error("panel move activation failed for " + first.stable_id);
              const secondCounts = observe(secondNode, second.stable_id, ["click"]);
              secondNode.click();
              if (secondCounts.click < 1) throw new Error("panel move restoration failed for " + second.stable_id);
              const restored = Array.from(panel.parentElement?.querySelectorAll(":scope > section.panel[data-panel-key]") || []).indexOf(panel);
              if (restored !== originalIndex) throw new Error("panel order restoration failed for " + panel.dataset.panelKey);
              record(first.stable_id, "activated", "panel_step_move_and_restore_activated");
              record(second.stable_id, "activated", "panel_step_move_and_restore_activated");
            });
            ["layout-panel-advanced-toggle", "layout-panel-hidden-toggle"].forEach((family) => {
              itemsForFamily(family).forEach((descriptor) => {
                const node = nodeFor(descriptor);
                const panel = node.closest("section.panel[data-panel-key]");
                const attribute = family.endsWith("advanced-toggle") ? "data-panel-advanced" : "data-panel-hidden";
                const original = panel.hasAttribute(attribute);
                clickAndCount(descriptor, node, "panel_state_toggle_round_trip_activated", 2);
                if (panel.hasAttribute(attribute) !== original) throw new Error("panel state restoration failed for " + descriptor.stable_id);
              });
            });

            ["diagnostic-why-disclosure", "table-column-menu", "libraries-summary-inspect", "libraries-override-section", "libraries-advanced-disclosure"].forEach((family) => {
              itemsForFamily(family).forEach(activateDisclosure);
            });
            itemsForFamily("generated-summary-toggle").forEach((descriptor) => clickAndCount(descriptor, nodeFor(descriptor), "summary_expand_collapse_activated", 2));
            itemsForFamily("generated-selectable-row").forEach(activateSelectable);
            itemsForFamily("libraries-summary-tile").forEach(activateSelectable);

            itemsForFamily("table-column-visibility").forEach(activateFormControl);
            itemsForFamily("table-column-sort").forEach((descriptor) => clickAndCount(descriptor, nodeFor(descriptor), "ascending_and_descending_sort_activated", 2));
            itemsForFamily("table-column-resize").forEach((descriptor) => {
              const node = nodeFor(descriptor);
              revealNode(node, descriptor.surface);
              const counts = observe(node, descriptor.stable_id, ["keydown"]);
              node.dispatchEvent(new KeyboardEvent("keydown", { key: "ArrowRight", bubbles: true, cancelable: true }));
              node.dispatchEvent(new KeyboardEvent("keydown", { key: "ArrowLeft", bubbles: true, cancelable: true }));
              if (counts.keydown < 2) throw new Error("table resize keyboard activation failed for " + descriptor.stable_id);
              record(descriptor.stable_id, "activated", "keyboard_resize_right_left_activated", { activation_count: 2 });
            });

            const advancedToggleOriginal = new Map();
            itemsForFamily("settings-advanced-toggle").forEach((descriptor) => {
              const node = nodeFor(descriptor);
              revealNode(node, descriptor.surface);
              const expanded = node.getAttribute("aria-expanded") === "true";
              advancedToggleOriginal.set(descriptor.stable_id, expanded);
              const counts = observe(node, descriptor.stable_id, ["click"]);
              node.click();
              if (expanded) node.click();
              if (counts.click < 1) throw new Error("advanced toggle activation failed for " + descriptor.stable_id);
              record(descriptor.stable_id, "activated", "advanced_controls_reveal_activated", { activation_count: counts.click });
            });

            [
              "settings-wizard-library-field", "settings-wizard-enhanced-choice",
              "libraries-profile-field", "libraries-override-control",
              "libraries-compatibility-select", "libraries-route-boundary-input",
            ].forEach((family) => itemsForFamily(family).forEach(activateFormControl));
            itemsForFamily("settings-wizard-library-remove").forEach((descriptor) => {
              const node = nodeFor(descriptor);
              if (node.disabled) record(descriptor.stable_id, "blocked", "protected_default_library_cannot_be_removed");
              else clickAndCount(descriptor, node, "wizard_library_remove_activated");
            });
            ["libraries-override-reset", "libraries-path-reset"].forEach((family) => {
              itemsForFamily(family).forEach((descriptor) => {
                const node = nodeFor(descriptor);
                if (node.disabled || node.hidden) record(descriptor.stable_id, "blocked", "inherited_value_has_no_reset_action");
                else clickAndCount(descriptor, node, "local_inherited_reset_activated");
              });
            });
            ["libraries-profile-navigation", "libraries-route-boundary-reset"].forEach((family) => {
              itemsForFamily(family).forEach((descriptor) => clickAndCount(descriptor, nodeFor(descriptor), "local_library_action_activated"));
            });

            itemsForFamily("schedule-hidden-window-state").forEach((descriptor) => record(descriptor.stable_id, "skipped", "hidden_non_operator_state"));
            itemsForFamily("schedule-time-block").forEach((descriptor) => clickAndCount(descriptor, nodeFor(descriptor), "schedule_half_hour_block_activated"));
            const scheduleActionFamilies = ["schedule-day-clear", "schedule-day-allow-all", "schedule-day-copy", "schedule-day-paste"];
            const scheduleDays = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"];
            scheduleDays.forEach((day) => {
              scheduleActionFamilies.forEach((family) => {
                const descriptor = itemsForFamily(family).find((item) => item.stable_id.includes("schedule-editor-" + day + "-"));
                if (!descriptor) throw new Error("missing " + family + " for " + day);
                const node = nodeFor(descriptor);
                if (family === "schedule-day-paste" && node.disabled) throw new Error("Paste Day remained disabled after Copy Day for " + day);
                clickAndCount(descriptor, node, "schedule_day_local_action_activated");
              });
            });
            document.getElementById("schedule-editor-load-current-button")?.click();

            registerCurrentControls();
            descriptors.filter((descriptor) => !classifications[descriptor.stable_id]).forEach((descriptor) => {
              if (descriptor.family === "generated-selectable-row" || descriptor.family === "libraries-summary-tile") {
                activateSelectable(descriptor);
                return;
              }
              if (["diagnostic-why-disclosure", "table-column-menu", "libraries-summary-inspect"].includes(descriptor.family)) {
                activateDisclosure(descriptor);
                return;
              }
              throw new Error("post-activation generated control lacked a strategy: " + JSON.stringify(descriptor));
            });

            advancedToggleOriginal.forEach((expanded, stableId) => {
              const node = nodeById.get(stableId);
              if (node && (node.getAttribute("aria-expanded") === "true") !== expanded) node.click();
            });
            originalFormState.forEach((state, stableId) => {
              const node = nodeById.get(stableId);
              if (!node || !node.isConnected || node.disabled || node.readOnly || node.type === "hidden") return;
              if (node.type === "checkbox" || node.type === "radio") node.checked = state.checked;
              else node.value = state.value;
              dispatchFormEvents(node);
            });
            originalEnhancedChoiceValues.forEach((value, selectId) => {
              const select = document.getElementById(selectId);
              if (!select) return;
              select.value = value;
              dispatchFormEvents(select);
            });
            if (!customizeWasOpen && document.body.classList.contains("layout-editor-open")) customizeButton?.click();
          } finally {
            window.fetch = originalFetch;
            window.confirm = originalConfirm;
            window.alert = originalAlert;
            Object.keys(localStorage).forEach((key) => localStorage.removeItem(key));
            Object.entries(originalStorage).forEach(([key, value]) => localStorage.setItem(key, value));
          }

          const discoveredIds = descriptors.map((item) => item.stable_id);
          const omittedIds = discoveredIds.filter((stableId) => !classifications[stableId]);
          const failedIds = discoveredIds.filter((stableId) => classifications[stableId]?.status === "failed");
          const unclassifiedIds = discoveredIds.filter((stableId) => classifications[stableId]?.status === "unclassified");
          if (omittedIds.length) throw new Error("generated census omitted controls: " + JSON.stringify(omittedIds));
          if (failedIds.length || unclassifiedIds.length) throw new Error("generated census invalid outcomes: " + JSON.stringify({ failedIds, unclassifiedIds }));
          const surfaceCounts = Object.fromEntries(["settings", "libraries", "schedule"].map((surface) => [surface, descriptors.filter((item) => item.surface === surface).length]));
          const statusCounts = Object.fromEntries(["activated", "blocked", "skipped", "failed", "unclassified"].map((status) => [status, discoveredIds.filter((id) => classifications[id]?.status === status).length]));
          const familyNames = Array.from(new Set(descriptors.map((item) => item.family))).sort();
          const generatedFamilies = familyNames.map((family) => {
            const familyIds = descriptors.filter((item) => item.family === family).map((item) => item.stable_id);
            return {
              family,
              instance_count: familyIds.length,
              outcomes: Object.fromEntries(["activated", "blocked", "skipped"].map((status) => [status, familyIds.filter((id) => classifications[id]?.status === status).length])),
            };
          });
          const blockerReasons = Array.from(new Set(discoveredIds
            .filter((id) => classifications[id]?.status === "blocked" || classifications[id]?.status === "skipped")
            .map((id) => classifications[id]?.reason)))
            .sort();
          const blockers = blockerReasons.map((reason) => ({
            reason,
            instance_ids: discoveredIds.filter((id) => classifications[id]?.reason === reason),
          }));
          const prohibitedRequests = requests.filter((request) => !request.url.endsWith("/api/ui-preferences"));
          if (prohibitedRequests.length) throw new Error("generated census attempted prohibited non-read requests: " + JSON.stringify(prohibitedRequests));
          return {
            schema_version: "webview-generated-control-census.v1",
            scope: ["settings", "libraries", "schedule"],
            exact_interactive_predicate: {
              native_tags: Array.from(nativeTags),
              roles: Array.from(interactiveRoles),
              includes_href_anchor: true,
              includes_nonnegative_tabindex: true,
            },
            discovered_count: descriptors.length,
            surface_counts: surfaceCounts,
            status_counts: statusCounts,
            discovered_ids: discoveredIds,
            descriptors,
            classifications,
            generated_families: generatedFamilies,
            blockers,
            finite_values: finiteValues,
            event_evidence: eventEvidence,
            requests,
            prohibited_requests: prohibitedRequests,
          };
        }

        async function main() {
          const userDataDir = fs.mkdtempSync(`${payload.tmpRoot.replace(/\\/g, "/")}/chrome-profile-`);
          const browser = launchBrowser([
            "--headless=new", "--disable-gpu", "--disable-background-networking", "--disable-default-apps",
            "--disable-extensions", "--disable-sync", "--metrics-recording-only", "--no-first-run",
            "--no-default-browser-check", `--remote-debugging-port=${payload.port}`,
            `--user-data-dir=${userDataDir}`, payload.url,
          ]);
          let client = null;
          try {
            const wsUrl = await waitForPageWebSocket(payload.port, payload.url);
            client = createCdpClient(wsUrl);
            await client.send("Runtime.enable");
            await client.send("Log.enable");
            await client.send("Page.enable");
            const deadline = Date.now() + 30000;
            let ready = false;
            while (Date.now() < deadline) {
              const probe = await client.send("Runtime.evaluate", {
                expression: `Boolean(
                  document.querySelectorAll("#schedule-editor-rows .schedule-block-button").length === 336
                  && document.querySelectorAll("#settings-wizard-library-list .settings-wizard-library-row").length === 2
                  && document.querySelectorAll("[data-enhanced-choice-for] input[type=radio]").length >= 19
                )`,
                returnByValue: true,
              });
              if (probe.result?.value === true) { ready = true; break; }
              await sleep(150);
            }
            if (!ready) {
              const diagnostic = await client.send("Runtime.evaluate", {
                expression: `({
                  blocks: document.querySelectorAll("#schedule-editor-rows .schedule-block-button").length,
                  wizardRows: document.querySelectorAll("#settings-wizard-library-list .settings-wizard-library-row").length,
                  radios: document.querySelectorAll("[data-enhanced-choice-for] input[type=radio]").length,
                  libraryCards: document.querySelectorAll("#settings-library-profile-list .settings-library-card").length,
                })`,
                returnByValue: true,
              });
              throw new Error("generated Settings/Libraries/Schedule controls did not become ready: " + JSON.stringify(diagnostic.result?.value || {}));
            }
            await sleep(500);
            const evaluation = await client.send("Runtime.evaluate", {
              expression: `(${browserGeneratedControlCensus.toString()})(${JSON.stringify({ authoredDescriptors: payload.authoredDescriptors })})`,
              awaitPromise: true,
              returnByValue: true,
            });
            if (evaluation.exceptionDetails) {
              const details = evaluation.exceptionDetails;
              throw new Error(details.exception?.description || details.exception?.value || details.text || "generated census failed");
            }
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


def _run_generated_control_census(
    *, browser_path: str, url: str, authored_descriptors: list[dict[str, object]]
) -> dict[str, object]:
    node = shutil.which("node")
    if not node:
        raise unittest.SkipTest("Node.js is required for the generated control census.")
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as raw_tmp:
        tmp = Path(raw_tmp)
        payload_path = tmp / "generated-control-census-payload.json"
        runner_path = tmp / "generated-control-census-runner.cjs"
        payload_path.write_text(
            json.dumps(
                {
                    "browserPath": browser_path,
                    "port": free_port(),
                    "tmpRoot": str(tmp),
                    "url": url,
                    "authoredDescriptors": authored_descriptors,
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        runner_path.write_text(_browser_generated_control_census_runner_source(), encoding="utf-8")
        return run_node_browser_smoke(
            "Browser-backed generated Settings/Libraries/Schedule control census",
            node=node,
            runner_path=runner_path,
            payload_path=payload_path,
            timeout_seconds=120,
        )


class WebViewBrowserSettingsGeneratedControlCensus(unittest.TestCase):
    def test_generated_controls_are_fully_classified_and_safe_instances_activate(self) -> None:
        browser_path = find_browser()
        if not browser_path:
            raise unittest.SkipTest("Chrome or Edge is required for the generated control census.")

        repo_root = find_repo_root(Path(__file__))
        authored_descriptors = _static_control_descriptors(repo_root)
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
            facade = MediaPipelineApplicationFacade(service, app_version="v6-generated-control-census")
            server = LocalApiServer(
                facade,
                token="browser-generated-control-census-token",
                resolved_provider=lambda: resolved,
                resolved_reload=lambda: resolved,
                audit_root_provider=lambda: str(root),
            )
            try:
                server.start()
                result = _run_generated_control_census(
                    browser_path=browser_path,
                    url=f"{server.url}/",
                    authored_descriptors=authored_descriptors,
                )
            finally:
                server.stop()
            assert_media_no_mutation(self, media_snapshot)
            media_snapshot_after = capture_media_no_mutation_snapshot(root, register_runner_finalizer=False)

        census = result["result"]
        census["source_output_snapshot_proof"] = {
            "before": media_snapshot,
            "after": media_snapshot_after,
            "unchanged": media_snapshot == media_snapshot_after,
            "file_count": len(media_snapshot) - 1,
        }
        descriptors = census["descriptors"]
        evidence_path = os.environ.get("MEDIAPIPELINE_WEBVIEW_GENERATED_CONTROL_EVIDENCE", "").strip()
        if evidence_path:
            Path(evidence_path).write_text(json.dumps(census, indent=2) + "\n", encoding="utf-8")
        if os.environ.get("MEDIAPIPELINE_EMIT_CONTROL_CENSUS_JSON", "").strip() == "1":
            print("CONTROL_CENSUS_JSON=" + json.dumps(census, ensure_ascii=False, separators=(",", ":")))

        self.assertEqual(census["discovered_count"], 1145)
        self.assertEqual(census["surface_counts"], {"settings": 339, "libraries": 385, "schedule": 421})
        self.assertEqual(census["status_counts"]["activated"], 953)
        self.assertEqual(census["status_counts"]["blocked"], 173)
        self.assertEqual(census["status_counts"]["skipped"], 19)
        self.assertEqual(census["status_counts"]["failed"], 0)
        self.assertEqual(census["status_counts"]["unclassified"], 0)
        self.assertEqual(
            census["status_counts"]["activated"]
            + census["status_counts"]["blocked"]
            + census["status_counts"]["skipped"],
            census["discovered_count"],
        )
        self.assertEqual(census["prohibited_requests"], [])
        self.assertTrue(census["source_output_snapshot_proof"]["unchanged"])
        self.assertGreater(census["source_output_snapshot_proof"]["file_count"], 0)
        self.assertFalse([item for item in descriptors if item["family"] == "unclassified-family"])
        family_counts = {item["family"]: item["instance_count"] for item in census["generated_families"]}
        self.assertEqual(family_counts["schedule-time-block"], 336)
        self.assertEqual(family_counts["schedule-day-clear"], 7)
        self.assertEqual(family_counts["schedule-day-allow-all"], 7)
        self.assertEqual(family_counts["schedule-day-copy"], 7)
        self.assertEqual(family_counts["schedule-day-paste"], 7)
        self.assertEqual(family_counts["schedule-hidden-window-state"], 7)
        self.assertEqual(family_counts["settings-wizard-enhanced-choice"], 19)
        self.assertEqual(family_counts["settings-wizard-library-field"], 20)
        self.assertEqual(family_counts["settings-wizard-library-path-picker"], 6)
        self.assertEqual(family_counts["settings-wizard-library-remove"], 2)
        self.assertEqual(family_counts["libraries-override-control"], 154)
        self.assertEqual(family_counts["libraries-override-reset"], 154)


if __name__ == "__main__":
    unittest.main()
