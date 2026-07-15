from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
import textwrap
import unittest
from collections import Counter
from pathlib import Path

from mediapipeline.tools.paths import find_repo_root

REPO_ROOT = find_repo_root(Path(__file__))
sys.path.insert(0, str(REPO_ROOT / "src"))

from mediapipeline.desktop.api import LocalApiServer
from mediapipeline.desktop.application import MediaPipelineApplicationFacade
from mediapipeline.core.diagnostics.tdarr_matrix_console import tdarr_matrix_runs_root

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


_SURFACE_EXPECTED_COUNTS = {
    "app-shell": 32,
    "home": 49,
    "metrics": 17,
    "diagnostics": 75,
    "maintenance": 30,
    "settings-save-dialog": 3,
}
_TARGET_SURFACES = frozenset(_SURFACE_EXPECTED_COUNTS)
_SPECIAL_BLOCK_REASONS = {
    "webview.static.pipeline-log-window-button": "external_window_not_opened_by_hermetic_census",
    "webview.static.settings-save-review-confirm-button": "strict_settings_save_requires_staged_patch_and_confirmation_harness",
    "webview.static.maintenance-support-create": "support_bundle_creation_is_not_a_local_display_action",
    "webview.static.diagnostics-recovery-preview-button": "lifecycle_command_not_executed_by_control_census",
    "webview.static.diagnostics-recovery-reconcile-button": "lifecycle_mutation_not_executed_by_control_census",
    "webview.static.launch-encoder-capability-refresh-button": "encoder_capability_refresh_is_a_backend_command_not_a_local_navigation",
    "webview.static.sample-validation-strip-preview-button": "sample_validation_preview_is_a_backend_command_not_a_local_navigation",
}


def _seed_tdarr_compare_runs(root: Path) -> None:
    runs_root = tdarr_matrix_runs_root(root)
    for ordinal, run_id in enumerate(("run-root-census-left", "run-root-census-right"), start=1):
        run_root = runs_root / run_id
        audit_root = run_root / "manifests" / "audit"
        audit_root.mkdir(parents=True, exist_ok=True)
        (run_root / ".tdarr-matrix-audit-run.json").write_text(
            json.dumps(
                {
                    "schema_version": "tdarr_matrix_audit.v1",
                    "run_root": str(run_root),
                }
            ),
            encoding="utf-8",
        )
        (run_root / "manifests" / "materialized_library.csv").write_text(
            "case_id,view,diagnostic_bucket,generated_path\n",
            encoding="utf-8",
        )
        (audit_root / "tdarr_matrix_audit_report.json").write_text(
            json.dumps(
                {
                    "schema_version": "tdarr_matrix_audit.v1",
                    "generated_at_utc": f"2026-07-13T0{ordinal}:00:00+00:00",
                    "mode": "run-samples",
                    "findings": [],
                }
            ),
            encoding="utf-8",
        )


def _block_reason(record: dict[str, object]) -> str:
    touchpoint_id = str(record["touchpoint_id"])
    if touchpoint_id in _SPECIAL_BLOCK_REASONS:
        return _SPECIAL_BLOCK_REASONS[touchpoint_id]

    classification = dict(record.get("classification") or {})
    if classification.get("status") == "destructive":
        return "destructive_verified_matrix_delete_not_armed_or_executed"

    action = dict(record.get("action") or {})
    if action.get("kind") != "api_command":
        return ""

    route = str(action.get("route") or "")
    label = str(record.get("label") or "").casefold()
    if route in {"/api/backend/shutdown", "/api/pipeline/control"}:
        return "process_lifecycle_command_not_executed_by_control_census"
    if route.endswith("/open") or route.endswith("/open-folder"):
        return "external_shell_open_not_executed_by_control_census"
    if (
        "proof pack" in label
        or "smoke pack" in label
        or "proof gate" in label
        or route.endswith("/rerun")
    ):
        return "diagnostics_proof_or_rerun_effect_requires_isolated_full_effect_harness"
    return "backend_command_effect_requires_route_specific_isolated_harness"


def _root_control_descriptors() -> list[dict[str, object]]:
    ledger_path = REPO_ROOT / "docs" / "generated" / "WEBVIEW_TOUCHPOINT_LEDGER.json"
    ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
    if ledger.get("schema_version") != "webview_touchpoint_ledger.v1":
        raise AssertionError("Unexpected WebView touchpoint ledger schema.")

    records = [
        record
        for record in ledger.get("records", [])
        if str(dict(record.get("surface") or {}).get("page") or "") in _TARGET_SURFACES
    ]
    surface_counts = Counter(
        str(dict(record.get("surface") or {}).get("page") or "") for record in records
    )
    if dict(surface_counts) != _SURFACE_EXPECTED_COUNTS:
        raise AssertionError(
            f"Root control ledger denominator changed: {dict(surface_counts)} != {_SURFACE_EXPECTED_COUNTS}"
        )
    if len(records) != 206:
        raise AssertionError(f"Root control ledger denominator changed: {len(records)} != 206")

    selector_occurrences: Counter[tuple[str, str]] = Counter()
    descriptors: list[dict[str, object]] = []
    for record in records:
        surface = str(dict(record.get("surface") or {}).get("page") or "")
        locator = dict(record.get("locator") or {})
        selector = str(locator.get("selector") or "")
        if not selector:
            raise AssertionError(f"Touchpoint has no CSS selector: {record.get('touchpoint_id')}")
        selector_key = (surface, selector)
        occurrence = selector_occurrences[selector_key]
        selector_occurrences[selector_key] += 1
        classification = dict(record.get("classification") or {})
        if classification.get("status") not in {
            "safe",
            "safe_reversible",
            "destructive",
            "unreachable",
        }:
            raise AssertionError(f"Unclassified ledger touchpoint: {record.get('touchpoint_id')}")
        descriptors.append(
            {
                "touchpoint_id": str(record["touchpoint_id"]),
                "surface": surface,
                "label": str(record.get("label") or ""),
                "selector": selector,
                "selector_occurrence": occurrence,
                "tag": str(locator.get("tag") or "").casefold(),
                "role": str(locator.get("role") or "").casefold(),
                "ledger_classification": classification,
                "action": dict(record.get("action") or {}),
                "block_reason": _block_reason(record),
                "source": list(record.get("source") or []),
            }
        )

    touchpoint_ids = [str(item["touchpoint_id"]) for item in descriptors]
    if len(touchpoint_ids) != len(set(touchpoint_ids)):
        raise AssertionError("Root control touchpoint IDs are not unique.")
    return descriptors


def _browser_root_control_census_runner_source() -> str:
    return browser_cdp_runner_prelude() + textwrap.dedent(
        r"""
        function normalizedText(value) {
          return String(value || "").replace(/\s+/g, " ").trim();
        }

        async function browserRootControlCensus(data) {
          function normalizedText(value) {
            return String(value || "").replace(/\s+/g, " ").trim();
          }
          const descriptors = Array.isArray(data.descriptors) ? data.descriptors : [];
          const expectedSurfaceCounts = {
            "app-shell": 32,
            home: 49,
            metrics: 17,
            diagnostics: 75,
            maintenance: 30,
            "settings-save-dialog": 3,
          };
          const classifications = {};
          const eventEvidence = {};
          const finiteValues = {};
          const disabledFiniteValues = {};
          const runtimeTypes = {};
          const generatedClassifications = {};
          const generatedEventEvidence = {};
          const generatedFiniteValues = {};
          const generatedDisabledFiniteValues = {};
          let generatedDescriptors = [];
          let generatedRawDescriptors = [];
          let generatedInventoryCounts = {};
          const generatedNodeRegistry = new Map();
          let generatedActivationMode = false;
          const interceptedRequests = [];
          const interceptedWindowOpens = [];
          const originalFetch = window.fetch.bind(window);
          const originalConfirm = window.confirm;
          const originalAlert = window.alert;
          const originalOpen = window.open;
          let activeTouchpoint = "bootstrap";

          function record(touchpointId, status, reason, extra) {
            if (classifications[touchpointId]) {
              throw new Error("duplicate classification for " + touchpointId);
            }
            classifications[touchpointId] = Object.assign({ status, reason }, extra || {});
          }
          function recordGenerated(touchpointId, status, reason, extra) {
            if (generatedClassifications[touchpointId]) {
              throw new Error("duplicate generated classification for " + touchpointId);
            }
            generatedClassifications[touchpointId] = Object.assign({ status, reason }, extra || {});
          }
          function surfaceScope(surface) {
            if (surface === "settings-save-dialog") {
              return document.getElementById("settings-save-review-dialog");
            }
            if (surface === "app-shell") return document;
            return document.querySelector('[data-page-panel="' + surface + '"]');
          }
          function surfaceMatches(surface, selector) {
            const scope = surfaceScope(surface);
            if (!scope) return [];
            const matches = Array.from(scope.querySelectorAll(selector));
            if (surface !== "app-shell") return matches;
            return matches.filter((node) => {
              if (node.closest("[data-page-panel]")) return false;
              if (node.closest("#settings-save-review-dialog")) return false;
              return true;
            });
          }
          function resolveControl(descriptor) {
            if (descriptor.touchpoint_id === "webview.static.diagnostics.button-button-read-last-stderr") {
              return surfaceScope("diagnostics")?.querySelector('[data-read-diagnostics-tail="last_stderr_log"]') || null;
            }
            const matches = surfaceMatches(descriptor.surface, descriptor.selector);
            if (matches.length > 1 && descriptor.label) {
              const expectedLabel = normalizedText(descriptor.label);
              const labelMatches = matches.filter((node) => {
                const actualLabel = normalizedText(
                  node.getAttribute("aria-label")
                  || node.getAttribute("title")
                  || node.textContent
                  || node.value
                  || ""
                );
                return actualLabel === expectedLabel;
              });
              if (labelMatches.length === 1) return labelMatches[0];
              const expectedTokens = new Set(expectedLabel.toLowerCase().split(/[^a-z0-9]+/).filter((token) => token.length > 2));
              const scored = matches.map((node) => {
                const actual = normalizedText(node.getAttribute("aria-label") || node.getAttribute("title") || node.textContent || node.value || "").toLowerCase();
                const actualTokens = new Set(actual.split(/[^a-z0-9]+/).filter((token) => token.length > 2));
                const score = Array.from(expectedTokens).filter((token) => actualTokens.has(token)).length;
                return { node, score };
              }).sort((left, right) => right.score - left.score);
              if (scored[0]?.score > 0 && scored[0].score > (scored[1]?.score || 0)) return scored[0].node;
            }
            return matches[Number(descriptor.selector_occurrence || 0)] || null;
          }
          function observe(node, touchpointId, names) {
            const observed = [];
            names.forEach((name) => {
              node.addEventListener(name, (event) => {
                observed.push({
                  type: event.type,
                  key: event.key || "",
                  value: "value" in node ? String(node.value ?? "") : "",
                  checked: "checked" in node ? Boolean(node.checked) : null,
                });
              });
            });
            eventEvidence[touchpointId] = observed;
            return observed;
          }
          function dispatchFormEvents(node) {
            node.dispatchEvent(new Event("input", { bubbles: true }));
            node.dispatchEvent(new Event("change", { bubbles: true }));
          }
          function alternateValue(node) {
            const current = String(node.value || "");
            if (node.type === "number" || node.type === "range") {
              const min = node.getAttribute("min");
              const max = node.getAttribute("max");
              if (min !== null && min !== current) return min;
              if (max !== null && max !== current) return max;
              return current === "1" ? "2" : "1";
            }
            return current === "root-control-census" ? "root-control-census-2" : "root-control-census";
          }
          function openSettingsDialog() {
            const dialog = document.getElementById("settings-save-review-dialog");
            if (!dialog || dialog.open) return dialog;
            try { dialog.showModal(); } catch (_error) { dialog.setAttribute("open", ""); }
            return dialog;
          }
          function prepareControlState(descriptor) {
            const id = String(descriptor.touchpoint_id || "");
            if (descriptor.surface === "settings-save-dialog") openSettingsDialog();
            if (id.includes("layout-editor-") || id === "webview.static.reset-layout-btn") {
              if (!document.body.classList.contains("layout-editor-open")) {
                document.getElementById("customize-layout-btn")?.click();
              }
            }
            if (id.startsWith("webview.static.floating-pipeline-log-")) {
              const panel = document.getElementById("floating-pipeline-log-panel");
              if (panel) panel.hidden = false;
            }
          }
          async function showSurface(surface) {
            if (surface === "app-shell" || surface === "settings-save-dialog") return;
            const panel = document.querySelector('[data-page-panel="' + surface + '"]');
            if (panel?.classList.contains("is-visible")) return;
            if (generatedActivationMode && panel) {
              document.querySelectorAll("[data-page-panel]").forEach((candidate) => {
                const selected = candidate === panel;
                candidate.classList.toggle("is-visible", selected);
                candidate.hidden = !selected;
                candidate.setAttribute("aria-hidden", selected ? "false" : "true");
              });
              document.querySelectorAll("[data-page]").forEach((candidate) => {
                const selected = candidate.getAttribute("data-page") === surface;
                candidate.classList.toggle("is-active", selected);
                if (selected) candidate.setAttribute("aria-current", "page");
                else candidate.removeAttribute("aria-current");
              });
              return;
            }
            if (typeof window.showPage === "function") {
              window.showPage(surface);
              await new Promise((resolve) => setTimeout(resolve, 60));
            }
          }
          async function waitForEnabled(descriptor, node) {
            const deadline = Date.now() + 1200;
            let current = node;
            const waitingForState = () => {
              if (!current) return false;
              if (current.disabled) return true;
              if (String(current.tagName || "").toLowerCase() !== "select") return false;
              return !Array.from(current.options || []).some((option) => !option.disabled);
            };
            while (waitingForState() && Date.now() < deadline) {
              await new Promise((resolve) => setTimeout(resolve, 40));
              current = resolveControl(descriptor);
            }
            return current;
          }
          function dispatchCustomKeyboard(node) {
            node.focus({ preventScroll: true });
            const enter = new KeyboardEvent("keydown", {
              key: "Enter",
              code: "Enter",
              bubbles: true,
              cancelable: true,
            });
            node.dispatchEvent(enter);
            const space = new KeyboardEvent("keydown", {
              key: " ",
              code: "Space",
              bubbles: true,
              cancelable: true,
            });
            node.dispatchEvent(space);
          }
          function assertNavigationPostcondition(node, descriptor) {
            const targetPage = node.getAttribute("data-page")
              || node.getAttribute("data-quick-link-page")
              || node.getAttribute("data-cross-page-target");
            if (targetPage) {
              const panel = document.querySelector('[data-page-panel="' + targetPage + '"]');
              if (!panel || !panel.classList.contains("is-visible")) {
                throw new Error(descriptor.touchpoint_id + " did not display target page " + targetPage);
              }
            }
            if (node.hasAttribute("data-diag-tab") && node.getAttribute("aria-selected") !== "true") {
              throw new Error(descriptor.touchpoint_id + " did not select its Diagnostics tab");
            }
            if (node.hasAttribute("data-metrics-tab") && node.getAttribute("aria-selected") !== "true") {
              throw new Error(descriptor.touchpoint_id + " did not select its Metrics tab");
            }
          }
          const interactiveRoles = new Set([
            "button", "link", "checkbox", "radio", "switch", "tab", "menuitem",
            "menuitemcheckbox", "menuitemradio", "option", "treeitem", "gridcell", "row",
          ]);
          function isInteractive(node) {
            const tag = String(node?.tagName || "").toLowerCase();
            if (["button", "input", "select", "textarea", "summary"].includes(tag)) return true;
            if (tag === "a" && node.hasAttribute("href")) return true;
            if (interactiveRoles.has(String(node.getAttribute("role") || "").toLowerCase())) return true;
            const rawTabindex = node.getAttribute("tabindex");
            if (rawTabindex === null || rawTabindex === "") return false;
            const parsed = Number(rawTabindex);
            return Number.isInteger(parsed) && parsed >= 0;
          }
          function fnv1a(value) {
            let hash = 0x811c9dc5;
            for (let index = 0; index < value.length; index += 1) {
              hash ^= value.charCodeAt(index);
              hash = Math.imul(hash, 0x01000193);
            }
            return (hash >>> 0).toString(16).padStart(8, "0");
          }
          function slug(value) {
            return normalizedText(value).toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "").slice(0, 72) || "control";
          }
          function generatedSemantic(node, surface) {
            const attributes = {};
            Array.from(node.attributes || []).forEach((attribute) => {
              const name = String(attribute.name || "").toLowerCase();
              if (name === "id" || name === "role" || name === "tabindex" || name === "type" || name.startsWith("data-")) {
                attributes[name] = String(attribute.value || "");
              }
            });
            const label = normalizedText(
              node.getAttribute("aria-label")
              || node.getAttribute("title")
              || node.textContent
              || node.getAttribute("name")
              || node.value
              || "control"
            ).slice(0, 180);
            const contextNode = node.closest("tr, [data-row-id], [data-item-id], [data-job-id], [data-path], [data-column-key], .table-card");
            const context = normalizedText(
              contextNode?.getAttribute("data-row-id")
              || contextNode?.getAttribute("data-item-id")
              || contextNode?.getAttribute("data-job-id")
              || contextNode?.getAttribute("data-path")
              || contextNode?.getAttribute("data-column-key")
              || contextNode?.textContent
              || ""
            ).slice(0, 180);
            const tableId = String(node.closest("table")?.id || node.closest("[data-table-id]")?.getAttribute("data-table-id") || "");
            const panelNode = node.closest("[data-panel-key], section, [data-page-panel]");
            const panelKey = String(
              panelNode?.getAttribute("data-panel-key")
              || panelNode?.id
              || panelNode?.getAttribute("data-page-panel")
              || ""
            );
            const panelHeading = normalizedText(
              panelNode?.querySelector(".panel-heading h2, .panel-heading h3, h2, h3")?.textContent || ""
            ).slice(0, 120);
            const ownerId = String(
              node.parentElement?.id
              || node.closest("[id]")?.id
              || ""
            );
            const ancestorTrail = [];
            let ancestor = node.parentElement;
            for (let depth = 0; ancestor && depth < 7; depth += 1, ancestor = ancestor.parentElement) {
              const data = {};
              Array.from(ancestor.attributes || []).forEach((attribute) => {
                if (attribute.name.startsWith("data-") || attribute.name === "id" || attribute.name === "role") {
                  data[attribute.name] = String(attribute.value || "");
                }
              });
              ancestorTrail.push({
                tag: String(ancestor.tagName || "").toLowerCase(),
                class_name: String(ancestor.className || ""),
                data,
              });
            }
            const adjacent = {
              previous: normalizedText(node.previousElementSibling?.textContent || "").slice(0, 100),
              next: normalizedText(node.nextElementSibling?.textContent || "").slice(0, 100),
            };
            const signature = JSON.stringify({
              surface,
              tag: String(node.tagName || "").toLowerCase(),
              attributes,
              label,
              context,
              table_id: tableId,
              panel_key: panelKey,
              panel_heading: panelHeading,
              owner_id: ownerId,
              ancestor_trail: ancestorTrail,
              adjacent,
            });
            const semantic = attributes.id || attributes["data-touchpoint-id"] || attributes["data-action"]
              || attributes["data-column-key"] || label || String(node.tagName || "control");
            return {
              touchpoint_id: "webview.runtime." + surface + "." + slug(semantic) + "-" + fnv1a(signature),
              surface,
              tag: String(node.tagName || "").toLowerCase(),
              role: String(node.getAttribute("role") || "").toLowerCase(),
              label,
              attributes,
              context,
              table_id: tableId,
              panel_key: panelKey,
              panel_heading: panelHeading,
              owner_id: ownerId,
              ancestor_trail: ancestorTrail,
              adjacent,
              signature,
            };
          }
          function authoredNodeSet() {
            const nodes = new Set();
            const owners = new Map();
            descriptors.forEach((descriptor) => {
              const node = resolveControl(descriptor);
              if (node) {
                nodes.add(node);
                const ids = owners.get(node) || [];
                ids.push(descriptor.touchpoint_id);
                owners.set(node, ids);
              }
            });
            if (nodes.size !== descriptors.length) {
              const duplicates = Array.from(owners.values()).filter((ids) => ids.length > 1);
              throw new Error("authored controls did not resolve to 206 unique runtime nodes; found " + nodes.size + "; duplicates=" + JSON.stringify(duplicates));
            }
            return nodes;
          }
          function generatedSurfaceNodes(surface, authoredNodes) {
            const scope = surfaceScope(surface);
            if (!scope) return [];
            let nodes = Array.from(scope.querySelectorAll("*"));
            if (surface === "app-shell") {
              nodes = nodes.filter((node) => !node.closest("[data-page-panel]") && !node.closest("#settings-save-review-dialog"));
            }
            return nodes.filter((node) => isInteractive(node) && !authoredNodes.has(node));
          }
          function sharedGeneratedFamily(descriptor) {
            const label = String(descriptor.label || "");
            const attributes = descriptor.attributes || {};
            if (/^Move .+ up$/.test(label)) return "panel-move-up";
            if (/^Move .+ down$/.test(label)) return "panel-move-down";
            if (label.includes("Advanced gate") || label.includes("always visible")) return "panel-advanced-gate";
            if (label === "Click to hide this panel") return "panel-hide";
            if (label === "Columns") return "table-columns-menu";
            if (Object.prototype.hasOwnProperty.call(attributes, "data-sort-direction")) return "table-sort";
            if (/^Resize .+ column$/.test(label)) return "table-resize";
            if (
              descriptor.tag === "input"
              && attributes.type === "checkbox"
              && /^(Show|Hide) .+ column in /.test(label)
            ) return "table-column-visibility";
            if (/^(Show|Hide) summary$/.test(label) || label === "Why?") return "disclosure";
            return "";
          }
          function pageOwnedGeneratedKey(descriptor) {
            const stableAttributes = {};
            Object.entries(descriptor.attributes || {}).forEach(([name, value]) => {
              if (["data-state", "data-status", "data-current", "data-sort-direction"].includes(name)) return;
              stableAttributes[name] = value;
            });
            const labelStem = normalizedText(descriptor.label || "")
              .replace(/\b\d+\b/g, "#")
              .replace(/:\s.*$/, "")
              .replace(/\s+-\s+.*$/, "");
            return JSON.stringify({
              surface: descriptor.surface,
              tag: descriptor.tag,
              role: descriptor.role,
              owner_id: descriptor.owner_id,
              panel_key: descriptor.panel_key,
              attributes: stableAttributes,
              label_stem: labelStem,
            });
          }
          function collectGeneratedInventory() {
            const authoredNodes = authoredNodeSet();
            const raw = [];
            for (const surface of Object.keys(expectedSurfaceCounts)) {
              generatedSurfaceNodes(surface, authoredNodes).forEach((node) => {
                const descriptor = generatedSemantic(node, surface);
                raw.push(descriptor);
                generatedNodeRegistry.set(descriptor.touchpoint_id, node);
              });
            }
            const ids = raw.map((item) => item.touchpoint_id);
            const duplicates = ids.filter((id, index) => ids.indexOf(id) !== index);
            if (duplicates.length) {
              throw new Error("generated semantic IDs collided: " + JSON.stringify(Array.from(new Set(duplicates))));
            }
            const pageOwnedFamilies = new Map();
            const rowFamilies = new Map();
            const sharedFamilies = new Map();
            raw.forEach((descriptor) => {
              const sharedFamily = sharedGeneratedFamily(descriptor);
              if (sharedFamily) {
                const current = sharedFamilies.get(sharedFamily) || {
                  touchpoint_id: "webview.runtime.shared." + sharedFamily,
                  origin: "shared_generated_family",
                  family: sharedFamily,
                  surface: "shared",
                  surfaces: [],
                  tag: descriptor.tag,
                  role: descriptor.role,
                  label: sharedFamily,
                  attributes: {},
                  instance_count: 0,
                  raw_instance_ids: [],
                };
                current.instance_count += 1;
                current.raw_instance_ids.push(descriptor.touchpoint_id);
                if (!current.surfaces.includes(descriptor.surface)) current.surfaces.push(descriptor.surface);
                sharedFamilies.set(sharedFamily, current);
                return;
              }
              if (descriptor.tag === "tr" && descriptor.attributes["data-selectable-row"] === "true") {
                const owner = descriptor.owner_id || descriptor.panel_key || descriptor.panel_heading || "rows";
                const key = descriptor.surface + "|" + owner;
                const current = rowFamilies.get(key) || {
                  touchpoint_id: "webview.runtime." + descriptor.surface + ".row-family." + slug(owner) + "-" + fnv1a(key),
                  origin: "page_owned_row_family",
                  family: "selectable-row",
                  surface: descriptor.surface,
                  owner_id: owner,
                  tag: "tr",
                  role: "row",
                  label: owner + " selectable rows",
                  attributes: { "data-selectable-row": "true" },
                  instance_count: 0,
                  raw_instance_ids: [],
                };
                current.instance_count += 1;
                current.raw_instance_ids.push(descriptor.touchpoint_id);
                rowFamilies.set(key, current);
                return;
              }
              const stableKey = pageOwnedGeneratedKey(descriptor);
              const current = pageOwnedFamilies.get(stableKey) || Object.assign({}, descriptor, {
                touchpoint_id: "webview.runtime." + descriptor.surface + ".control-family." + slug(descriptor.label) + "-" + fnv1a(stableKey),
                origin: "page_owned_control_family",
                stable_key: stableKey,
                instance_count: 0,
                raw_instance_ids: [],
              });
              current.instance_count += 1;
              current.raw_instance_ids.push(descriptor.touchpoint_id);
              pageOwnedFamilies.set(stableKey, current);
            });
            const audit = [
              ...Array.from(pageOwnedFamilies.values()).sort((left, right) => {
                const leftCsv = String(left.label || "").startsWith("CSV rerun complete") ? 0 : 1;
                const rightCsv = String(right.label || "").startsWith("CSV rerun complete") ? 0 : 1;
                return leftCsv - rightCsv;
              }),
              ...Array.from(rowFamilies.values()),
              ...Array.from(sharedFamilies.values()),
            ];
            return {
              raw,
              audit,
              counts: {
                raw_instances: raw.length,
                page_owned_records: pageOwnedFamilies.size + rowFamilies.size,
                page_owned_instances: Array.from(pageOwnedFamilies.values()).reduce((total, item) => total + item.instance_count, 0)
                  + Array.from(rowFamilies.values()).reduce((total, item) => total + item.instance_count, 0),
                row_families: rowFamilies.size,
                shared_families: sharedFamilies.size,
                shared_instances: Array.from(sharedFamilies.values()).reduce((total, item) => total + item.instance_count, 0),
              },
            };
          }
          function currentRawGenerated() {
            const authoredNodes = authoredNodeSet();
            const entries = [];
            for (const surface of Object.keys(expectedSurfaceCounts)) {
              generatedSurfaceNodes(surface, authoredNodes).forEach((node) => {
                entries.push({ node, descriptor: generatedSemantic(node, surface) });
              });
            }
            return entries;
          }
          function resolveGeneratedInstances(descriptor) {
            if (descriptor.origin === "page_owned_control_family") {
              const connected = descriptor.raw_instance_ids
                .map((id) => generatedNodeRegistry.get(id))
                .filter((node) => node?.isConnected)
                .map((node) => ({ node, descriptor: generatedSemantic(node, descriptor.surface) }));
              if (connected.length === descriptor.instance_count) return connected;
            }
            const entries = currentRawGenerated();
            if (descriptor.origin === "shared_generated_family") {
              return entries.filter((entry) => sharedGeneratedFamily(entry.descriptor) === descriptor.family);
            }
            if (descriptor.origin === "page_owned_row_family") {
              return entries.filter((entry) => {
                const item = entry.descriptor;
                const owner = item.owner_id || item.panel_key || item.panel_heading || "rows";
                return item.surface === descriptor.surface
                  && item.tag === "tr"
                  && item.attributes["data-selectable-row"] === "true"
                  && owner === descriptor.owner_id;
              });
            }
            if (descriptor.origin === "page_owned_control_family") {
              return entries.filter((entry) => pageOwnedGeneratedKey(entry.descriptor) === descriptor.stable_key);
            }
            return [];
          }
          async function expandAndLoadGeneratedSurfaces() {
            const advancedToggle = document.getElementById("advanced-toggle");
            if (advancedToggle && advancedToggle.getAttribute("aria-expanded") !== "true") advancedToggle.click();
            for (const surface of ["home", "metrics", "diagnostics", "maintenance"]) {
              if (typeof window.showPage === "function") window.showPage(surface);
              await new Promise((resolve) => setTimeout(resolve, 180));
              const surfaceScopeNode = surfaceScope(surface);
              const refreshCandidates = [
                document.getElementById("refresh-button"),
                document.getElementById(surface + "-refresh-button"),
                surfaceScopeNode?.querySelector("[data-page-refresh-button]"),
              ].filter(Boolean);
              const refreshDeadline = Date.now() + 2500;
              while (
                refreshCandidates.some((button) => button.disabled || button.getAttribute("aria-busy") === "true")
                && Date.now() < refreshDeadline
              ) {
                await new Promise((resolve) => setTimeout(resolve, 50));
              }
              await new Promise((resolve) => setTimeout(resolve, 100));
              if (surface === "home") {
                const completionRendered = window.mediaPipelineAppHome?.renderHomeCsvRerunCompletion?.({
                  snapshot: {
                    csv_rerun_summary: {
                      schema_version: "desktop_csv_rerun_completion.v1",
                      evidence_authority: "backend_manifest",
                      terminal: true,
                      display_label: "CSV rerun complete",
                      display_state: "ok",
                      csv_name: "root-control-census.csv",
                      detail: "root-control-census.csv · 1 processed · 1 completed",
                    },
                  },
                });
                if (!completionRendered) throw new Error("Home CSV completion control did not render for expanded census state");
              }
              const scope = surfaceScope(surface);
              if (!scope) continue;
              const tabs = Array.from(scope.querySelectorAll("[data-metrics-tab], [data-diag-tab]"));
              for (const tab of tabs) {
                if (!tab.disabled) tab.click();
                await new Promise((resolve) => setTimeout(resolve, 55));
              }
              scope.querySelectorAll("details").forEach((details) => {
                details.open = true;
                details.dispatchEvent(new Event("toggle"));
              });
              await new Promise((resolve) => setTimeout(resolve, 100));
            }
            const homePanel = surfaceScope("home");
            document.querySelectorAll("[data-page-panel]").forEach((candidate) => {
              const selected = candidate === homePanel;
              candidate.classList.toggle("is-visible", selected);
              candidate.hidden = !selected;
              candidate.setAttribute("aria-hidden", selected ? "false" : "true");
            });
            const finalCompletionRendered = window.mediaPipelineAppHome?.renderHomeCsvRerunCompletion?.({
              snapshot: {
                csv_rerun_summary: {
                  schema_version: "desktop_csv_rerun_completion.v1",
                  evidence_authority: "backend_manifest",
                  terminal: true,
                  display_label: "CSV rerun complete",
                  display_state: "ok",
                  csv_name: "root-control-census.csv",
                  detail: "root-control-census.csv · 1 processed · 1 completed",
                },
              },
            });
            if (!finalCompletionRendered) throw new Error("Home CSV completion control did not remain reachable for expanded census state");
          }
          function generatedPreflightBlockReason(node, descriptor) {
            const attributes = descriptor.attributes || {};
            const label = String(descriptor.label || "").casefold ? String(descriptor.label || "").casefold() : String(descriptor.label || "").toLowerCase();
            const attributeNames = Object.keys(attributes);
            if (descriptor.role === "option" && label.startsWith("csv rerun complete")) return "";
            if (descriptor.tag === "a") {
              const href = String(node.getAttribute("href") || "");
              if (href && !href.startsWith("#") && !href.startsWith("javascript:")) return "external_link_not_opened_by_hermetic_census";
            }
            if (attributeNames.some((name) => name.startsWith("data-open-") || name === "data-control-action")) {
              return "generated_external_or_process_action_not_executed";
            }
            if (attributeNames.some((name) => name.includes("drain") || name.includes("delete") || name.includes("rerun"))) {
              return "generated_high_risk_effect_not_executed";
            }
            if (/\b(drain|delete|permanent|shutdown|force stop|rerun|proof pack|smoke pack|strict proof)\b/.test(label)) {
              return "generated_high_risk_effect_not_executed";
            }
            return "";
          }
          async function activateGeneratedControls(generatedDescriptors) {
            for (const descriptor of generatedDescriptors) {
              const touchpointId = descriptor.touchpoint_id;
              activeTouchpoint = touchpointId;
              if (descriptor.surface !== "shared") await showSurface(descriptor.surface);
              let entries = resolveGeneratedInstances(descriptor);
              if (!entries.length) {
                recordGenerated(touchpointId, "failed", "generated_control_family_not_resolved");
                continue;
              }
              if (descriptor.origin === "page_owned_row_family" && entries.length !== descriptor.instance_count) {
                recordGenerated(touchpointId, "failed", "generated_family_instance_count_changed", {
                  expected_instance_count: descriptor.instance_count,
                  resolved_instance_count: entries.length,
                });
                continue;
              }
              if (descriptor.origin === "page_owned_row_family") {
                const familyEvidence = [];
                let activatedInstances = 0;
                let disabledInstances = 0;
                for (const entry of entries) {
                  const row = entry.node;
                  if (row.getAttribute("aria-disabled") === "true") {
                    disabledInstances += 1;
                    continue;
                  }
                  const observed = [];
                  ["click", "keydown"].forEach((name) => row.addEventListener(name, (event) => observed.push({ type: event.type, key: event.key || "" })));
                  dispatchCustomKeyboard(row);
                  row.click();
                  const keys = observed.filter((item) => item.type === "keydown").map((item) => item.key);
                  if (!observed.some((item) => item.type === "click") || !keys.includes("Enter") || !keys.includes(" ")) {
                    recordGenerated(touchpointId, "failed", "generated_row_family_keyboard_or_click_event_missing", {
                      activated_instance_count: activatedInstances,
                    });
                    activatedInstances = -1;
                    break;
                  }
                  activatedInstances += 1;
                  familyEvidence.push({
                    raw_instance_id: entry.descriptor.touchpoint_id,
                    events: observed,
                  });
                }
                generatedEventEvidence[touchpointId] = familyEvidence;
                if (activatedInstances < 0) continue;
                if (!activatedInstances) {
                  recordGenerated(touchpointId, "blocked", "all_generated_row_family_instances_disabled", {
                    disabled_instance_count: disabledInstances,
                  });
                } else {
                  recordGenerated(touchpointId, "activated", "all_enabled_generated_row_instances_received_click_enter_and_space", {
                    activated_instance_count: activatedInstances,
                    disabled_instance_count: disabledInstances,
                    instance_count: descriptor.instance_count,
                  });
                }
                continue;
              }
              let node = entries.find((entry) => !entry.node.disabled && entry.node.getAttribute("aria-disabled") !== "true")?.node || entries[0].node;
              const preflightBlock = generatedPreflightBlockReason(node, descriptor);
              if (preflightBlock) {
                recordGenerated(touchpointId, "blocked", preflightBlock, {
                  instance_count: descriptor.instance_count,
                });
                continue;
              }
              const deadline = Date.now() + 900;
              while (node.disabled && Date.now() < deadline) {
                await new Promise((resolve) => setTimeout(resolve, 35));
                entries = resolveGeneratedInstances(descriptor);
                node = entries.find((entry) => !entry.node.disabled)?.node || node;
              }
              if (node.disabled) {
                recordGenerated(touchpointId, "blocked", "generated_control_disabled_in_disposable_fixture_state");
                continue;
              }
              if (node.readOnly) {
                recordGenerated(touchpointId, "blocked", "generated_control_readonly_in_disposable_fixture_state");
                continue;
              }

              const tag = descriptor.tag;
              const inputType = String(node.type || "").toLowerCase();
              if (tag === "select") {
                const observed = [];
                ["input", "change"].forEach((name) => node.addEventListener(name, (event) => observed.push({ type: event.type })));
                generatedEventEvidence[touchpointId] = observed;
                const original = String(node.value || "");
                const enabled = Array.from(node.options || []).filter((option) => !option.disabled).map((option) => String(option.value));
                const disabled = Array.from(node.options || []).filter((option) => option.disabled).map((option) => String(option.value));
                if (!enabled.length) {
                  recordGenerated(touchpointId, "blocked", "generated_select_has_no_enabled_values", { disabled_values: disabled });
                  continue;
                }
                enabled.forEach((value) => {
                  node.value = value;
                  dispatchFormEvents(node);
                });
                node.value = original;
                dispatchFormEvents(node);
                generatedFiniteValues[touchpointId] = enabled;
                if (disabled.length) generatedDisabledFiniteValues[touchpointId] = disabled;
                recordGenerated(touchpointId, "activated", "all_enabled_generated_select_values_dispatched", {
                  value_count: enabled.length,
                  instance_count: descriptor.instance_count,
                  coverage: descriptor.instance_count > 1 ? "representative-per-family" : "all-record-instances",
                });
                continue;
              }
              if (tag === "input" || tag === "textarea") {
                if (inputType === "hidden") {
                  recordGenerated(touchpointId, "skipped", "generated_hidden_non_operator_state");
                  continue;
                }
                if (inputType === "file") {
                  recordGenerated(touchpointId, "blocked", "generated_file_picker_not_opened");
                  continue;
                }
                const observed = [];
                ["click", "input", "change"].forEach((name) => node.addEventListener(name, (event) => observed.push({ type: event.type })));
                generatedEventEvidence[touchpointId] = observed;
                if (inputType === "checkbox" || inputType === "radio") {
                  const original = Boolean(node.checked);
                  for (const desired of [false, true]) {
                    node.checked = desired;
                    dispatchFormEvents(node);
                  }
                  node.checked = original;
                  dispatchFormEvents(node);
                  generatedFiniteValues[touchpointId] = [false, true];
                  recordGenerated(touchpointId, "activated", "both_generated_boolean_values_dispatched", {
                    value_count: 2,
                    instance_count: descriptor.instance_count,
                    coverage: descriptor.instance_count > 1 ? "representative-per-family" : "all-record-instances",
                  });
                  continue;
                }
                const original = String(node.value || "");
                const alternate = alternateValue(node);
                node.value = alternate;
                dispatchFormEvents(node);
                node.value = original;
                dispatchFormEvents(node);
                recordGenerated(touchpointId, "activated", "generated_representative_edit_and_restore_dispatched", {
                  finite_domain: false,
                  instance_count: descriptor.instance_count,
                });
                continue;
              }
              if (tag === "summary") {
                const details = node.closest("details");
                if (!details) {
                  recordGenerated(touchpointId, "failed", "generated_summary_has_no_details_owner");
                  continue;
                }
                const original = Boolean(details.open);
                node.click();
                node.click();
                if (Boolean(details.open) !== original) {
                  recordGenerated(touchpointId, "failed", "generated_summary_did_not_restore_state");
                  continue;
                }
                generatedFiniteValues[touchpointId] = [false, true];
                recordGenerated(touchpointId, "activated", "generated_disclosure_open_and_closed", {
                  value_count: 2,
                  instance_count: descriptor.instance_count,
                  coverage: descriptor.instance_count > 1 ? "representative-per-family" : "all-record-instances",
                });
                continue;
              }

              const observed = [];
              ["click", "keydown"].forEach((name) => node.addEventListener(name, (event) => observed.push({ type: event.type, key: event.key || "" })));
              generatedEventEvidence[touchpointId] = observed;
              const customKeyboard = tag !== "button" || Boolean(descriptor.role) || node.hasAttribute("tabindex");
              const requestOffset = interceptedRequests.length;
              const windowOffset = interceptedWindowOpens.length;
              if (customKeyboard) dispatchCustomKeyboard(node);
              node.click();
              if (
                descriptor.origin === "shared_generated_family"
                && ["panel-advanced-gate", "panel-hide"].includes(descriptor.family)
              ) node.click();
              await new Promise((resolve) => setTimeout(resolve, 35));
              if (String(descriptor.label || "").startsWith("CSV rerun complete")) {
                const currentCompletion = document.querySelector("#home-next-queue-list [role='option']");
                const completionDetail = document.getElementById("home-next-queue-detail")?.textContent || "";
                if (
                  currentCompletion?.getAttribute("aria-selected") !== "true"
                  || !currentCompletion?.classList.contains("is-selected")
                  || !completionDetail.includes("root-control-census.csv")
                ) {
                  recordGenerated(touchpointId, "failed", "home_csv_completion_click_or_keyboard_selection_did_not_persist");
                  continue;
                }
              }
              const effectRequests = interceptedRequests.slice(requestOffset).filter((request) => !request.url.endsWith("/api/ui-preferences"));
              const externalOpens = interceptedWindowOpens.slice(windowOffset);
              if (effectRequests.length || externalOpens.length) {
                recordGenerated(touchpointId, "blocked", "generated_backend_or_external_effect_intercepted_before_execution", {
                  physical_event_observed: true,
                  intercepted_requests: effectRequests,
                  intercepted_window_opens: externalOpens,
                });
                continue;
              }
              if (!observed.some((item) => item.type === "click")) {
                recordGenerated(touchpointId, "failed", "generated_click_event_not_observed");
                continue;
              }
              if (customKeyboard) {
                const keys = observed.filter((item) => item.type === "keydown").map((item) => item.key);
                if (!keys.includes("Enter") || !keys.includes(" ")) {
                  recordGenerated(touchpointId, "failed", "generated_custom_control_missing_enter_or_space_event");
                  continue;
                }
              }
              recordGenerated(touchpointId, "activated", customKeyboard
                ? "generated_click_enter_and_space_activation_observed"
                : "generated_click_activation_observed", {
                instance_count: descriptor.instance_count,
                coverage: descriptor.instance_count > 1 ? "representative-per-family" : "all-record-instances",
              });
            }
          }

          window.fetch = async (input, init) => {
            const method = String((init && init.method) || "GET").toUpperCase();
            if (method === "GET" || method === "HEAD") return originalFetch(input, init);
            const request = { touchpoint_id: activeTouchpoint, method, url: String(input || "") };
            interceptedRequests.push(request);
            return new Response(JSON.stringify({
              ok: false,
              accepted: false,
              intercepted: true,
              message: "Hermetic root-control census intercepted the non-read request.",
            }), {
              status: 409,
              headers: { "Content-Type": "application/json" },
            });
          };
          window.open = (...args) => {
            interceptedWindowOpens.push({ touchpoint_id: activeTouchpoint, args: args.map(String) });
            return null;
          };
          window.confirm = () => true;
          window.alert = () => {};

          try {
            const initialSurfaceCounts = {};
            for (const surface of Object.keys(expectedSurfaceCounts)) {
              initialSurfaceCounts[surface] = descriptors
                .filter((item) => item.surface === surface && resolveControl(item))
                .length;
            }
            for (const [surface, expected] of Object.entries(expectedSurfaceCounts)) {
              if (initialSurfaceCounts[surface] !== expected) {
                throw new Error(surface + " runtime resolution mismatch: expected " + expected + ", found " + initialSurfaceCounts[surface]);
              }
            }

            await expandAndLoadGeneratedSurfaces();
            const generatedInventory = collectGeneratedInventory();
            generatedDescriptors = generatedInventory.audit;
            generatedRawDescriptors = generatedInventory.raw;
            generatedInventoryCounts = generatedInventory.counts;
            generatedActivationMode = true;
            await activateGeneratedControls(generatedDescriptors);
            generatedActivationMode = false;

            for (const descriptor of descriptors) {
              const touchpointId = String(descriptor.touchpoint_id || "");
              activeTouchpoint = touchpointId;
              await showSurface(descriptor.surface);
              prepareControlState(descriptor);
              let node = resolveControl(descriptor);
              if (!node) {
                record(touchpointId, "failed", "missing_runtime_control");
                continue;
              }

              if (descriptor.ledger_classification?.status === "destructive") {
                record(touchpointId, "skipped", descriptor.block_reason, {
                  ledger_status: descriptor.ledger_classification.status,
                });
                continue;
              }
              if (descriptor.block_reason) {
                record(touchpointId, "blocked", descriptor.block_reason, {
                  route: descriptor.action?.route || null,
                  action_kind: descriptor.action?.kind || null,
                });
                continue;
              }
              node = await waitForEnabled(descriptor, node);
              if (node.disabled) {
                record(touchpointId, "blocked", "disabled_in_current_disposable_fixture_state");
                continue;
              }
              if (node.readOnly) {
                record(touchpointId, "blocked", "readonly_in_current_disposable_fixture_state");
                continue;
              }

              const tag = String(node.tagName || descriptor.tag || "").toLowerCase();
              if (tag === "select") {
                const observed = observe(node, touchpointId, ["input", "change"]);
                const original = String(node.value || "");
                const enabled = Array.from(node.options || [])
                  .filter((option) => !option.disabled)
                  .map((option) => String(option.value));
                const disabled = Array.from(node.options || [])
                  .filter((option) => option.disabled)
                  .map((option) => String(option.value));
                if (!enabled.length) {
                  record(touchpointId, "blocked", "no_enabled_finite_values", { disabled_values: disabled });
                  continue;
                }
                for (const value of enabled) {
                  node.value = value;
                  dispatchFormEvents(node);
                }
                node.value = original;
                dispatchFormEvents(node);
                finiteValues[touchpointId] = enabled;
                if (disabled.length) disabledFiniteValues[touchpointId] = disabled;
                if (!observed.some((item) => item.type === "input") || !observed.some((item) => item.type === "change")) {
                  throw new Error(touchpointId + " did not emit input and change across its finite values");
                }
                record(touchpointId, "activated", "all_enabled_select_values_dispatched", { value_count: enabled.length });
                continue;
              }

              if (tag === "input" || tag === "textarea") {
                const inputType = String(node.type || "").toLowerCase();
                runtimeTypes[touchpointId] = inputType || tag;
                if (inputType === "hidden") {
                  record(touchpointId, "skipped", "hidden_non_operator_state");
                  continue;
                }
                if (inputType === "file") {
                  record(touchpointId, "blocked", "file_picker_not_opened_by_hermetic_census");
                  continue;
                }
                const observed = observe(node, touchpointId, ["click", "input", "change"]);
                if (inputType === "checkbox") {
                  const original = Boolean(node.checked);
                  for (const desired of [false, true]) {
                    node.checked = desired;
                    dispatchFormEvents(node);
                  }
                  node.checked = original;
                  dispatchFormEvents(node);
                  finiteValues[touchpointId] = [false, true];
                  if (!observed.some((item) => item.type === "input") || !observed.some((item) => item.type === "change")) {
                    throw new Error(touchpointId + " did not emit checkbox input and change events");
                  }
                  record(touchpointId, "activated", "both_checkbox_values_dispatched", { value_count: 2 });
                  continue;
                }
                const original = String(node.value || "");
                const alternate = alternateValue(node);
                node.value = alternate;
                dispatchFormEvents(node);
                node.value = original;
                dispatchFormEvents(node);
                if (!observed.some((item) => item.type === "input") || !observed.some((item) => item.type === "change")) {
                  throw new Error(touchpointId + " did not emit representative input and change events");
                }
                record(touchpointId, "activated", "representative_edit_and_restore_dispatched", {
                  finite_domain: false,
                  representative_value: alternate,
                });
                continue;
              }

              if (tag === "summary") {
                const details = node.closest("details");
                if (!details) throw new Error(touchpointId + " summary has no details owner");
                const observed = observe(node, touchpointId, ["click", "keydown"]);
                const original = Boolean(details.open);
                node.click();
                if (Boolean(details.open) === original) throw new Error(touchpointId + " did not toggle its details owner");
                node.click();
                if (Boolean(details.open) !== original) throw new Error(touchpointId + " did not restore its details owner");
                finiteValues[touchpointId] = [false, true];
                if (!observed.some((item) => item.type === "click")) throw new Error(touchpointId + " did not emit click");
                record(touchpointId, "activated", "details_disclosure_open_and_closed", { value_count: 2 });
                continue;
              }

              const observed = observe(node, touchpointId, ["click", "keydown"]);
              const customKeyboard = tag !== "button" || Boolean(descriptor.role) || node.hasAttribute("tabindex");
              if (customKeyboard) dispatchCustomKeyboard(node);
              node.click();
              if (touchpointId === "webview.static.layout-editor-reset-all" && node.dataset.state === "armed") {
                node.click();
              }
              await new Promise((resolve) => setTimeout(resolve, 35));
              if (!observed.some((item) => item.type === "click")) {
                throw new Error(touchpointId + " did not emit click");
              }
              if (customKeyboard) {
                const keys = observed.filter((item) => item.type === "keydown").map((item) => item.key);
                if (!keys.includes("Enter") || !keys.includes(" ")) {
                  throw new Error(touchpointId + " did not receive Enter and Space keyboard activation");
                }
              }
              assertNavigationPostcondition(node, descriptor);
              if (descriptor.surface === "settings-save-dialog") {
                const dialog = document.getElementById("settings-save-review-dialog");
                if (dialog?.open) throw new Error(touchpointId + " did not close the settings review dialog");
              }
              record(touchpointId, "activated", customKeyboard
                ? "click_enter_and_space_activation_observed"
                : "click_activation_observed");
            }
          } finally {
            activeTouchpoint = "teardown";
            window.fetch = originalFetch;
            window.open = originalOpen;
            window.confirm = originalConfirm;
            window.alert = originalAlert;
          }

          const allIds = descriptors.map((item) => String(item.touchpoint_id || ""));
          const activatedIds = allIds.filter((id) => classifications[id]?.status === "activated");
          const skippedIds = allIds.filter((id) => classifications[id]?.status === "skipped");
          const blockedIds = allIds.filter((id) => classifications[id]?.status === "blocked");
          const failedIds = allIds.filter((id) => classifications[id]?.status === "failed");
          const unclassifiedIds = allIds.filter((id) => !classifications[id]);
          const prohibitedRequests = interceptedRequests.filter((request) => {
            return request.url.endsWith("/api/ui-preferences") === false;
          });
          const localControlsWithProhibitedRequests = prohibitedRequests.filter((request) => {
            return classifications[request.touchpoint_id]?.status === "activated";
          });
          const generatedIds = generatedDescriptors.map((item) => item.touchpoint_id);
          const generatedActivatedIds = generatedIds.filter((id) => generatedClassifications[id]?.status === "activated");
          const generatedSkippedIds = generatedIds.filter((id) => generatedClassifications[id]?.status === "skipped");
          const generatedBlockedIds = generatedIds.filter((id) => generatedClassifications[id]?.status === "blocked");
          const generatedFailedIds = generatedIds.filter((id) => generatedClassifications[id]?.status === "failed");
          const generatedUnclassifiedIds = generatedIds.filter((id) => !generatedClassifications[id]);
          const generatedSurfaceCounts = {};
          generatedDescriptors.forEach((item) => {
            generatedSurfaceCounts[item.surface] = (generatedSurfaceCounts[item.surface] || 0) + 1;
          });

          return {
            discovered_count: allIds.length,
            surface_counts: expectedSurfaceCounts,
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
            classifications,
            finite_values: finiteValues,
            disabled_finite_values: disabledFiniteValues,
            runtime_types: runtimeTypes,
            event_evidence: eventEvidence,
            intercepted_requests: interceptedRequests,
            intercepted_window_opens: interceptedWindowOpens,
            local_controls_with_prohibited_requests: localControlsWithProhibitedRequests,
            generated: {
              discovered_count: generatedIds.length,
              raw_instance_count: generatedRawDescriptors.length,
              raw_instance_ids: generatedRawDescriptors.map((item) => item.touchpoint_id),
              inventory_counts: generatedInventoryCounts,
              surface_counts: generatedSurfaceCounts,
              activated_count: generatedActivatedIds.length,
              skipped_count: generatedSkippedIds.length,
              blocked_count: generatedBlockedIds.length,
              failed_count: generatedFailedIds.length,
              unclassified_count: generatedUnclassifiedIds.length,
              descriptors: generatedDescriptors,
              discovered_ids: generatedIds,
              activated_ids: generatedActivatedIds,
              skipped_ids: generatedSkippedIds,
              blocked_ids: generatedBlockedIds,
              failed_ids: generatedFailedIds,
              unclassified_ids: generatedUnclassifiedIds,
              classifications: generatedClassifications,
              finite_values: generatedFiniteValues,
              disabled_finite_values: generatedDisabledFiniteValues,
              event_evidence: generatedEventEvidence,
            },
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
              document.readyState !== "loading"
              && document.getElementById("advanced-toggle")
              && document.getElementById("sample-validation-preview-button")
              && document.getElementById("metrics-source-label")
              && document.getElementById("api-contract-filter")
              && document.getElementById("maintenance-change-ledger-search")
              && document.getElementById("settings-save-review-dialog")
              && typeof window.showPage === "function"
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
            if (!ready) throw new Error("Root census controls did not become ready");
            await sleep(600);
            const expression = `(${browserRootControlCensus.toString()})(${JSON.stringify({ descriptors: payload.descriptors })})`;
            const evaluation = await client.send("Runtime.evaluate", {
              expression,
              awaitPromise: true,
              returnByValue: true,
            });
            if (evaluation.exceptionDetails) {
              const details = evaluation.exceptionDetails;
              throw new Error(details.exception?.description || details.exception?.value || details.text || "browser census failed");
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


def _run_browser_root_control_census(
    *, browser_path: str, url: str, descriptors: list[dict[str, object]]
) -> dict[str, object]:
    node = shutil.which("node")
    if not node:
        raise unittest.SkipTest("Node.js is required for the browser-backed root control census.")
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as raw_tmp:
        tmp = Path(raw_tmp)
        payload_path = tmp / "browser-root-control-census-payload.json"
        runner_path = tmp / "browser-root-control-census-runner.cjs"
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
        runner_path.write_text(_browser_root_control_census_runner_source(), encoding="utf-8")
        return run_node_browser_smoke(
            "Browser-backed root surface control census",
            node=node,
            runner_path=runner_path,
            payload_path=payload_path,
            timeout_seconds=150,
        )


class WebViewBrowserRootControlCensus(unittest.TestCase):
    def test_root_surface_controls_have_zero_unclassified_and_safe_local_controls_activate(self) -> None:
        browser_path = find_browser()
        if not browser_path:
            raise unittest.SkipTest("Chrome or Edge is required for the browser-backed root control census.")

        descriptors = _root_control_descriptors()
        self.assertEqual(len(descriptors), 206)

        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            resolved, _source, _output = _write_fixture_state(root)
            _seed_tdarr_compare_runs(root)
            resolved.config_data.update(
                {
                    "SourceMovies": str(root / "Movies"),
                    "SourceTV": str(root / "TV"),
                    "Outsource": str(root / "Outsource"),
                    "LocalBase": str(root),
                }
            )
            service = DummyWorkflowFacadeService(root)
            resolved.config_path.write_text(
                service.serialize_psd1_document(resolved.config_data), encoding="utf-8"
            )
            media_snapshot = capture_media_no_mutation_snapshot(root)
            facade = MediaPipelineApplicationFacade(service, app_version="v6-root-control-census")
            server = LocalApiServer(
                facade,
                token="browser-root-control-census-token",
                resolved_provider=lambda: resolved,
                resolved_reload=lambda: resolved,
                audit_root_provider=lambda: str(root),
            )
            try:
                server.start()
                result = _run_browser_root_control_census(
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
                        "scope": list(_SURFACE_EXPECTED_COUNTS),
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

        self.assertEqual(census["discovered_count"], 206)
        self.assertEqual(census["surface_counts"], _SURFACE_EXPECTED_COUNTS)
        self.assertEqual(census["activated_count"], 153)
        self.assertEqual(census["blocked_count"], 51)
        self.assertEqual(census["skipped_count"], 2)
        self.assertEqual(census["failed_count"], 0, census["failed_ids"])
        self.assertEqual(census["unclassified_count"], 0, census["unclassified_ids"])
        self.assertEqual(census["local_controls_with_prohibited_requests"], [])
        self.assertEqual(census["intercepted_window_opens"], [])
        self.assertEqual(
            census["activated_count"] + census["skipped_count"] + census["blocked_count"],
            census["discovered_count"],
        )
        self.assertEqual(census["discovered_ids"], [item["touchpoint_id"] for item in descriptors])
        for stable_id in census["blocked_ids"] + census["skipped_ids"]:
            self.assertTrue(census["classifications"][stable_id]["reason"])

        generated = census["generated"]
        self.assertEqual(generated["discovered_count"], 87)
        self.assertEqual(generated["raw_instance_count"], 1129)
        self.assertEqual(generated["activated_count"], 80)
        self.assertEqual(generated["blocked_count"], 7)
        self.assertEqual(generated["skipped_count"], 0)
        self.assertEqual(
            generated["surface_counts"],
            {"home": 27, "metrics": 4, "diagnostics": 43, "maintenance": 4, "shared": 9},
        )
        self.assertEqual(
            generated["inventory_counts"],
            {
                "raw_instances": 1129,
                "page_owned_records": 78,
                "page_owned_instances": 233,
                "row_families": 19,
                "shared_families": 9,
                "shared_instances": 896,
            },
        )
        self.assertEqual(generated["failed_count"], 0, generated["failed_ids"])
        self.assertEqual(generated["unclassified_count"], 0, generated["unclassified_ids"])
        self.assertEqual(
            generated["activated_count"] + generated["skipped_count"] + generated["blocked_count"],
            generated["discovered_count"],
        )
        self.assertEqual(
            generated["discovered_ids"],
            [item["touchpoint_id"] for item in generated["descriptors"]],
        )
        self.assertEqual(len(generated["discovered_ids"]), len(set(generated["discovered_ids"])))
        self.assertEqual(len(generated["raw_instance_ids"]), len(set(generated["raw_instance_ids"])))
        self.assertEqual(
            sum(int(item["instance_count"]) for item in generated["descriptors"]),
            generated["raw_instance_count"],
        )
        for stable_id in generated["blocked_ids"]:
            self.assertTrue(generated["classifications"][stable_id]["reason"])

        shared_descriptors = [
            item for item in generated["descriptors"] if item["origin"] == "shared_generated_family"
        ]
        self.assertEqual(len(shared_descriptors), 9)
        for descriptor in shared_descriptors:
            stable_id = descriptor["touchpoint_id"]
            self.assertIn(stable_id, generated["activated_ids"])
            self.assertEqual(
                generated["classifications"][stable_id]["coverage"],
                "representative-per-family",
            )

        row_descriptors = [
            item for item in generated["descriptors"] if item["origin"] == "page_owned_row_family"
        ]
        self.assertEqual(len(row_descriptors), 19)
        for descriptor in row_descriptors:
            stable_id = descriptor["touchpoint_id"]
            self.assertIn(stable_id, generated["activated_ids"])
            classification = generated["classifications"][stable_id]
            self.assertEqual(
                classification["activated_instance_count"]
                + classification["disabled_instance_count"],
                descriptor["instance_count"],
            )
            for instance_evidence in generated["event_evidence"][stable_id]:
                keys = {
                    event["key"]
                    for event in instance_evidence["events"]
                    if event["type"] == "keydown"
                }
                self.assertEqual(keys, {"Enter", " "}, instance_evidence["raw_instance_id"])

        csv_completion = [
            item
            for item in generated["descriptors"]
            if str(item["label"]).startswith("CSV rerun complete")
        ]
        self.assertEqual(len(csv_completion), 1)
        csv_completion_id = csv_completion[0]["touchpoint_id"]
        self.assertIn(csv_completion_id, generated["activated_ids"])
        csv_keys = {
            event["key"]
            for event in generated["event_evidence"][csv_completion_id]
            if event["type"] == "keydown"
        }
        self.assertEqual(csv_keys, {"Enter", " "})

        finite_select_ids = {
            str(item["touchpoint_id"])
            for item in descriptors
            if item["tag"] == "select" and not item["block_reason"]
        }
        finite_checkbox_ids = {
            stable_id
            for stable_id, runtime_type in census["runtime_types"].items()
            if runtime_type == "checkbox"
        }
        activated_or_blocked = set(census["activated_ids"]) | set(census["blocked_ids"])
        self.assertTrue(finite_select_ids <= activated_or_blocked)
        for stable_id in finite_select_ids & set(census["activated_ids"]):
            self.assertGreaterEqual(len(census["finite_values"][stable_id]), 1)
        for stable_id in finite_checkbox_ids & set(census["activated_ids"]):
            self.assertEqual(census["finite_values"][stable_id], [False, True])
        self.assertEqual(len(census["finite_values"]), 39)
        self.assertEqual(len(generated["finite_values"]), 16)

        for descriptor in descriptors:
            stable_id = str(descriptor["touchpoint_id"])
            if stable_id not in census["activated_ids"]:
                continue
            is_custom_keyboard = bool(descriptor["role"]) or descriptor["tag"] in {"section", "span"}
            if not is_custom_keyboard:
                continue
            keys = {
                event["key"]
                for event in census["event_evidence"][stable_id]
                if event["type"] == "keydown"
            }
            self.assertEqual(keys, {"Enter", " "}, stable_id)

        for descriptor in generated["descriptors"]:
            stable_id = descriptor["touchpoint_id"]
            if descriptor["tag"] == "select" and stable_id in generated["activated_ids"]:
                self.assertGreaterEqual(len(generated["finite_values"][stable_id]), 1)
            if (
                descriptor["tag"] == "input"
                and descriptor["attributes"].get("type") in {"checkbox", "radio"}
                and stable_id in generated["activated_ids"]
            ):
                self.assertEqual(generated["finite_values"][stable_id], [False, True])


if __name__ == "__main__":
    unittest.main()
