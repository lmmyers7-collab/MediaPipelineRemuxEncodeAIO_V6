from __future__ import annotations

import json
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
    from .test_webview_real_media_smoke import _write_fixture_state
    from .webview_browser_smoke_support import (
        assert_media_no_mutation,
        browser_cdp_runner_prelude,
        capture_media_no_mutation_snapshot,
        find_browser as _find_browser,
        free_port as _free_port,
        run_node_browser_smoke,
    )
except ImportError:  # pragma: no cover - fallback for direct test execution
    from test_application_facade import DummyWorkflowFacadeService
    from test_webview_real_media_smoke import _write_fixture_state
    from webview_browser_smoke_support import (
        assert_media_no_mutation,
        browser_cdp_runner_prelude,
        capture_media_no_mutation_snapshot,
        find_browser as _find_browser,
        free_port as _free_port,
        run_node_browser_smoke,
    )


def _browser_layout_manager_runner_source() -> str:
    return browser_cdp_runner_prelude() + textwrap.dedent(
        r"""
        function layoutManagerScript() {
          return `
          (async () => {
            localStorage.removeItem("mediapipeline-layout-v1");
            function text(node) { return node ? String(node.textContent || "").trim() : ""; }
            function headingText(panel) {
              return text(panel.querySelector(".panel-heading h2, .panel-heading h3")).replace(/\\s+/g, " ");
            }
            function click(id) {
              const node = document.getElementById(id);
              if (!node) throw new Error("missing button " + id);
              node.click();
            }
            function openDrawer() {
              if (!document.body.classList.contains("layout-editor-open")) click("customize-layout-btn");
              if (!document.body.classList.contains("layout-editor-open")) throw new Error("layout editor drawer did not activate");
              const drawer = document.getElementById("layout-editor-drawer");
              if (!drawer) throw new Error("missing layout editor drawer");
              if (drawer.getAttribute("aria-hidden") !== "false") throw new Error("layout editor drawer is still aria-hidden");
              if (drawer.hidden) throw new Error("layout editor drawer remained hidden after open");
              if (drawer.inert) throw new Error("layout editor drawer remained inert after open");
              if (document.body.classList.contains("layout-customize-mode")) throw new Error("legacy inline customize mode should not activate");
            }
            function closeDrawerAndRequireInert() {
              const drawer = document.getElementById("layout-editor-drawer");
              if (!drawer) throw new Error("missing layout editor drawer");
              click("layout-editor-done");
              if (document.body.classList.contains("layout-editor-open")) throw new Error("layout editor drawer did not close");
              if (drawer.getAttribute("aria-hidden") !== "true") throw new Error("closed layout editor drawer should be aria-hidden");
              if (!drawer.hidden) throw new Error("closed layout editor drawer should be hidden");
              if (!drawer.inert) throw new Error("closed layout editor drawer should be inert");
              const done = document.getElementById("layout-editor-done");
              done.focus();
              if (document.activeElement === done) throw new Error("closed layout editor drawer accepted focus");
            }
            function assertEmptyStateCustomizeOpenOnly() {
              window.showPage("completed");
              openDrawer();
              const page = document.querySelector('[data-page-panel="completed"]');
              if (!page) throw new Error("missing completed page for empty-state customize check");
              const panels = Array.from(page.querySelectorAll("section.panel[data-panel-key]"))
                .filter((panel) => !panel.closest("[data-page-empty-state]"));
              panels.forEach((panel) => panel.setAttribute("data-panel-hidden", ""));
              window.updatePagePanelEmptyStates();
              const empty = page.querySelector('[data-page-empty-state="panel-visibility"]');
              if (!empty || !empty.classList.contains("is-visible")) throw new Error("completed empty-state did not become visible");
              const customize = Array.from(empty.querySelectorAll("button")).find((button) => text(button) === "Customize");
              if (!customize) throw new Error("missing empty-state Customize button");
              customize.click();
              if (!document.body.classList.contains("layout-editor-open")) throw new Error("empty-state Customize closed an already-open drawer");
              const drawer = document.getElementById("layout-editor-drawer");
              if (drawer.getAttribute("aria-hidden") !== "false" || drawer.hidden || drawer.inert) throw new Error("empty-state Customize left drawer inaccessible");
              panels.forEach((panel) => panel.removeAttribute("data-panel-hidden"));
              window.updatePagePanelEmptyStates();
              closeDrawerAndRequireInert();
            }
            function drawerRows() {
              return Array.from(document.querySelectorAll("#layout-editor-tree .layout-editor-panel-row[data-layout-editor-panel-key]"));
            }
            function drawerRowText(row) {
              return text(row.querySelector(".layout-editor-panel-name")).replace(/\\s+/g, " ");
            }
            function panelForDrawerRow(row) {
              return document.querySelector('section.panel[data-panel-key="' + row.dataset.layoutEditorPanelKey + '"]');
            }
            function sharedPreferenceSnapshot() {
              const snapshot = {};
              for (let index = 0; index < localStorage.length; index += 1) {
                const key = localStorage.key(index);
                if (/^mediapipeline[-.][A-Za-z0-9_.:-]{1,160}$/.test(String(key || ""))) {
                  snapshot[key] = String(localStorage.getItem(key));
                }
              }
              return snapshot;
            }
            function storedLayoutState() {
              return JSON.parse(localStorage.getItem("mediapipeline-layout-v1") || "{}");
            }
            async function restoreUiPreferencesLikeTauriRefresh() {
              if (typeof restoreSharedUiPreferences !== "function") throw new Error("restoreSharedUiPreferences is not global");
              await restoreSharedUiPreferences({ applyRuntime: true, seedWebview: false });
            }
            async function withStaleUiPreferences(stalePreferences, action) {
              const originalApiGet = window.apiGet;
              const originalApiPost = window.apiPost;
              let postedPreferences = null;
              window.apiGet = async function apiGetWithStaleUiPreferences(path, options) {
                if (path === "/api/ui-preferences") return { storage: stalePreferences };
                return originalApiGet(path, options);
              };
              window.apiPost = async function apiPostCapturingUiPreferences(path, payload, options) {
                if (path === "/api/ui-preferences") {
                  postedPreferences = payload?.storage || {};
                  return { ok: true, storage: postedPreferences };
                }
                return originalApiPost(path, payload, options);
              };
              try {
                await action(() => postedPreferences);
              } finally {
                window.apiGet = originalApiGet;
                window.apiPost = originalApiPost;
              }
            }
            async function requireStaleRemoteRefreshDoesNotRevertSharedPreference() {
              const key = "mediapipeline-launch-tab";
              const stalePreferences = sharedPreferenceSnapshot();
              stalePreferences[key] = "pipeline";
              await withStaleUiPreferences(stalePreferences, async (postedPreferences) => {
                localStorage.setItem(key, "history");
                await restoreUiPreferencesLikeTauriRefresh();
                if (localStorage.getItem(key) !== "history") {
                  throw new Error("stale remote UI preferences reverted a pending shared preference write");
                }
                if ((postedPreferences() || {})[key] !== "history") {
                  throw new Error("pending shared preference write was not flushed before remote refresh");
                }
              });
            }
            async function requireStaleRemoteRefreshDoesNotRevertLayoutToggle(panel) {
              const panelKey = panel.dataset.panelKey || "";
              if (!panelKey) throw new Error("missing panel key for stale-refresh regression");
              const staleLayout = storedLayoutState();
              staleLayout[panelKey] = { ...(staleLayout[panelKey] || {}), advanced: false };
              const stalePreferences = sharedPreferenceSnapshot();
              stalePreferences["mediapipeline-layout-v1"] = JSON.stringify(staleLayout);
              await withStaleUiPreferences(stalePreferences, async (postedPreferences) => {
                requireDrawerPanel("queue", "Queue Summary").querySelectorAll(".layout-editor-toggle-button")[1].click();
                if (!panel.hasAttribute("data-panel-advanced")) throw new Error("drawer Advanced toggle did not gate Queue Summary");
                await restoreUiPreferencesLikeTauriRefresh();
                if (!panel.hasAttribute("data-panel-advanced")) {
                  throw new Error("stale remote UI preferences reverted a pending layout editor Advanced click");
                }
                const savedLayout = JSON.parse((postedPreferences() || {})["mediapipeline-layout-v1"] || "{}");
                if (savedLayout[panelKey]?.advanced !== true) {
                  throw new Error("pending layout editor Advanced click was not flushed before remote refresh");
                }
              });
            }
            function layoutContainerOrderKeyForPanel(panel) {
              const panelKey = panel?.dataset?.panelKey || "";
              const parts = panelKey.split("::");
              if (parts.length < 2) throw new Error("cannot infer layout container key from " + panelKey);
              parts.pop();
              return "__order__" + parts.join("::");
            }
            async function requireStaleRemoteRefreshDoesNotRevertFlushedLayoutMove() {
              window.showPage("completed");
              openDrawer();
              const overviewPane = document.querySelector('[data-page-panel="completed"] .settings-tab-pane[data-completed-tab="overview"]');
              if (!overviewPane) throw new Error("missing Completed Overview pane for layout move regression");
              const panels = Array.from(overviewPane.querySelectorAll(":scope > section.panel[data-panel-key]"));
              const byHeading = Object.fromEntries(panels.map((panel) => [headingText(panel), panel]));
              const currentPanel = byHeading["Current Output Status"];
              const whyPanel = byHeading["Why This Output Looks Different"];
              const finalPanel = byHeading["Final Library Promotion"];
              if (!currentPanel || !whyPanel || !finalPanel) {
                throw new Error("missing Completed panels for layout move regression: " + panels.map(headingText).join(" | "));
              }
              const orderKey = layoutContainerOrderKeyForPanel(currentPanel);
              const authoredOrder = panels.map((panel) => panel.dataset.panelKey || "");
              const staleOrder = authoredOrder.filter((key) => key && key !== whyPanel.dataset.panelKey);
              const finalIndex = staleOrder.indexOf(finalPanel.dataset.panelKey || "");
              if (finalIndex < 0) throw new Error("cannot place stale Completed order after Final Library Promotion");
              staleOrder.splice(finalIndex + 1, 0, whyPanel.dataset.panelKey || "");
              const staleLayout = storedLayoutState();
              staleLayout[orderKey] = staleOrder;
              const stalePreferences = sharedPreferenceSnapshot();
              stalePreferences["mediapipeline-layout-v1"] = JSON.stringify(staleLayout);
              await withStaleUiPreferences(stalePreferences, async (postedPreferences) => {
                localStorage.setItem("mediapipeline-layout-v1", JSON.stringify(staleLayout));
                window.mediaPipelineAppLayoutManager.applyStoredLayoutPreferences();
                openDrawer();
                let staleHeadings = panelOrderIn(overviewPane);
                if (staleHeadings.indexOf("Why This Output Looks Different") <= staleHeadings.indexOf("Final Library Promotion")) {
                  throw new Error("stale Completed layout setup did not place Why after Final Library Promotion: " + staleHeadings.join(" | "));
                }
                let guard = 0;
                while (
                  panelOrderIn(overviewPane).indexOf("Why This Output Looks Different")
                    > panelOrderIn(overviewPane).indexOf("Current Output Status") + 1
                ) {
                  requireDrawerPanel("completed", "Why This Output Looks Different").querySelectorAll(".layout-editor-move-button")[0].click();
                  guard += 1;
                  if (guard > 10) throw new Error("could not move Why This Output Looks Different below Current Output Status");
                }
                const movedHeadings = panelOrderIn(overviewPane);
                if (movedHeadings[movedHeadings.indexOf("Current Output Status") + 1] !== "Why This Output Looks Different") {
                  throw new Error("Completed layout move did not place Why after Current Output Status: " + movedHeadings.join(" | "));
                }
                const currentKey = currentPanel.dataset.panelKey || "";
                const whyKey = whyPanel.dataset.panelKey || "";
                let lastPostedOrder = "";
                let flushed = false;
                for (let attempt = 0; attempt < 25; attempt += 1) {
                  const savedLayout = JSON.parse((postedPreferences() || {})["mediapipeline-layout-v1"] || "{}");
                  const savedOrderEntry = Object.entries(savedLayout).find(([, value]) => (
                    Array.isArray(value) && value.includes(currentKey) && value.includes(whyKey)
                  ));
                  const savedOrder = savedOrderEntry ? savedOrderEntry[1] : [];
                  lastPostedOrder = savedOrder.join(" | ");
                  if (savedOrder[savedOrder.indexOf(currentKey) + 1] === whyKey) {
                    flushed = true;
                    break;
                  }
                  await new Promise((resolve) => setTimeout(resolve, 100));
                }
                if (!flushed) {
                  throw new Error("flushed Completed layout preference did not keep Why after Current Output Status: " + lastPostedOrder);
                }
                await restoreUiPreferencesLikeTauriRefresh();
                const afterRefreshHeadings = panelOrderIn(overviewPane);
                if (afterRefreshHeadings[afterRefreshHeadings.indexOf("Current Output Status") + 1] !== "Why This Output Looks Different") {
                  throw new Error("stale remote UI preferences reverted a flushed layout move: " + afterRefreshHeadings.join(" | "));
                }
              });
            }
            function drawerRowByHeading(heading) {
              return drawerRows().find((row) => drawerRowText(row) === heading);
            }
            function drawerGroupLabels() {
              return Array.from(document.querySelectorAll("#layout-editor-tree .layout-editor-group-summary"))
                .map((summary) => text(summary.querySelector("span")).replace(/\\s+/g, " "))
                .filter(Boolean);
            }
            function requireDrawerGroups(page, labels) {
              window.showPage(page);
              openDrawer();
              const found = drawerGroupLabels();
              labels.forEach((label) => {
                if (!found.includes(label)) {
                  throw new Error("missing layout drawer group " + page + " / " + label + "\\nFound: " + found.join(" | "));
                }
              });
              const genericSummaryCount = found.filter((label) => label === "Summary").length;
              if (genericSummaryCount > 1) {
                throw new Error("layout drawer has duplicate generic Summary groups for " + page + ": " + found.join(" | "));
              }
            }
            function requireDrawerHeadings(page, expected, omitted) {
              window.showPage(page);
              openDrawer();
              const found = drawerRows().map(drawerRowText);
              const missing = expected.filter((heading) => !found.includes(heading));
              const extras = found.filter((heading) => !expected.includes(heading));
              const unexpected = omitted.filter((heading) => found.includes(heading));
              if (missing.length || extras.length || unexpected.length) {
                throw new Error(
                  "layout drawer headings mismatch for " + page
                  + "\\nMissing: " + missing.join(" | ")
                  + "\\nExtras: " + extras.join(" | ")
                  + "\\nUnexpected omitted: " + unexpected.join(" | ")
                  + "\\nFound: " + found.join(" | ")
                );
              }
            }
            function requireManagedPanel(page, heading) {
              if (page === "queue") {
                const tabId = heading === "CSV Rerun" ? "rerun" : "main";
                if (window.mediaPipelineQueueView?.activateQueueTab) {
                  window.mediaPipelineQueueView.activateQueueTab(tabId);
                } else {
                  const tab = document.querySelector('[data-queue-tab="' + tabId + '"]');
                  if (tab && tab.getAttribute("aria-selected") !== "true") tab.click();
                }
              }
              const root = document.querySelector('[data-page-panel="' + page + '"]');
              if (!root) throw new Error("missing page " + page);
              const panels = Array.from(root.querySelectorAll("section.panel[data-panel-key]"));
              const panel = panels.find((candidate) => headingText(candidate) === heading);
              if (!panel) {
                throw new Error("missing managed panel " + page + " / " + heading + "\\nFound: " + panels.map(headingText).join(" | "));
              }
              if (!panel.querySelector(".panel-customize-bar")) throw new Error("missing customize bar for " + page + " / " + heading);
              if (panel.getAttribute("draggable") === "true") throw new Error("real page panel should not be draggable while drawer is open: " + page + " / " + heading);
              if (!panel.querySelector(".pcb-btn-move-up")) throw new Error("missing move-up button for " + page + " / " + heading);
              if (!panel.querySelector(".pcb-btn-move-down")) throw new Error("missing move-down button for " + page + " / " + heading);
              return panel;
            }
            function requireDrawerPanel(page, heading) {
              window.showPage(page);
              openDrawer();
              const row = drawerRowByHeading(heading);
              if (!row) {
                throw new Error("missing drawer row " + page + " / " + heading + "\\nFound: " + drawerRows().map(drawerRowText).join(" | "));
              }
              if (row.getAttribute("draggable") !== "true") throw new Error("drawer row is not draggable: " + page + " / " + heading);
              if (!row.querySelector(".layout-editor-panel-grip")) throw new Error("missing drawer drag handle: " + page + " / " + heading);
              if (!row.querySelector(".layout-editor-move-button")) throw new Error("missing drawer move controls: " + page + " / " + heading);
              return row;
            }
            function panelOrder(page) {
              if (page === "queue") {
                return Array.from(document.querySelectorAll('[data-page-panel="queue"] .settings-tab-pane[data-queue-tab-panel="main"] > section.panel[data-panel-key]')).map((panel) => headingText(panel));
              }
              return Array.from(document.querySelectorAll('[data-page-panel="' + page + '"] > section.panel[data-panel-key]')).map((panel) => headingText(panel));
            }
            function panelOrderIn(container) {
              return Array.from(container.querySelectorAll(":scope > section.panel[data-panel-key]")).map((panel) => headingText(panel));
            }
            function dragDrawerRow(sourceRow, targetRow) {
              const grip = sourceRow.querySelector(".layout-editor-panel-grip");
              const sourceRect = sourceRow.getBoundingClientRect();
              const targetRect = targetRow.getBoundingClientRect();
              const pointerId = 17;
              const startX = sourceRect.left + sourceRect.width / 2;
              const startY = sourceRect.top + sourceRect.height / 2;
              const targetX = targetRect.left + targetRect.width / 2;
              const targetY = targetRect.top + 1;
              grip.dispatchEvent(new PointerEvent("pointerdown", {
                bubbles: true,
                cancelable: true,
                pointerId,
                pointerType: "mouse",
                button: 0,
                buttons: 1,
                clientX: startX,
                clientY: startY,
              }));
              if (!sourceRow.classList.contains("is-drag-holding")) throw new Error("drawer source row did not enter held drag state");
              targetRow.dispatchEvent(new PointerEvent("pointermove", {
                bubbles: true,
                cancelable: true,
                pointerId,
                pointerType: "mouse",
                buttons: 1,
                clientX: targetX,
                clientY: targetY,
              }));
              if (!sourceRow.classList.contains("is-dragging")) throw new Error("drawer source row did not enter active drag state");
              if (!targetRow.classList.contains("is-drop-target")) throw new Error("drawer drop target did not highlight");
              targetRow.dispatchEvent(new PointerEvent("pointerup", {
                bubbles: true,
                cancelable: true,
                pointerId,
                pointerType: "mouse",
                button: 0,
                buttons: 0,
                clientX: targetX,
                clientY: targetY,
              }));
              if (document.querySelector(".layout-editor-panel-row.is-drag-holding, .layout-editor-panel-row.is-dragging, .layout-editor-panel-row.is-drop-target")) {
                throw new Error("drawer pointer drag state did not clear after drop");
              }
            }
            openDrawer();
            closeDrawerAndRequireInert();
            openDrawer();
            assertEmptyStateCustomizeOpenOnly();
            await requireStaleRemoteRefreshDoesNotRevertSharedPreference();
            await requireStaleRemoteRefreshDoesNotRevertFlushedLayoutMove();
            const required = {
              queue: ["CSV Rerun", "Queue Decision", "Attention Required", "Queue Rows", "Backend Launch Scope Boundary", "Queue-to-Launch Handoff", "Queue Readiness Checklist"],
              completed: ["Overview", "Output Trust Decision", "Current Output Status", "Completed History Summary", "File And Size Proof", "Publish And Pending Proof", "Integrity Check", "Diagnostics Links"],
              settings: ["Current Changes", "Active Policy", "Save Status", "Launch Impact", "Save Result"],
              diagnostics: ["Recovery Steps", "Read Order", "Impact Summary", "Related Evidence", "Contract Review"],
              launch: ["Pipeline Processor", "Start Evidence", "Start Decision Summary", "Command History", "Command Review"],
              reports: ["Report Triage", "Failure Resolution Center", "Audit Entries"],
            };
            const keys = {};
            for (const [page, headings] of Object.entries(required)) {
              window.showPage(page);
              openDrawer();
              keys[page] = headings.map((heading) => {
                const panel = requireManagedPanel(page, heading);
                const row = requireDrawerPanel(page, heading);
                return {
                  panelKey: panel.dataset.panelKey || "",
                  drawerKey: row.dataset.layoutEditorPanelKey || "",
                };
              });
            }
            window.showPage("completed");
            openDrawer();
            const completedPanes = Array.from(document.querySelectorAll('[data-page-panel="completed"] .settings-tab-pane[data-completed-tab]'));
            const completedPaneKeys = completedPanes.map((pane) => pane.dataset.completedTab).sort().join("|");
            if (completedPaneKeys !== "evidence|history|overview") throw new Error("Completed tab panes were not merged to one container per tab: " + completedPaneKeys);
            if (document.querySelector('[data-page-panel="completed"] section.panel.settings-tab-pane')) throw new Error("Completed tab panes should be containers, not draggable panels");
            requireDrawerGroups("launch", ["Pipeline Processor", "History"]);
            requireDrawerGroups("queue", ["CSV Rerun", "Main Queue"]);
            requireDrawerGroups("reports", ["Failures", "Audit", "Locations"]);
            requireDrawerHeadings(
              "pending",
              [
                "Pending Publish Guard Evidence",
                "Drain Status",
                "Risk Summary",
                "Pending Publish Checklist",
                "Flagged Items",
                "Recovery Preview",
                "Manifest Repair",
                "Diagnostics Links",
              ],
              [
                "Pending Publish Operations",
                "Live Run",
                "File Inventory",
                "Drain Progress",
                "Selected Item",
                "Pending Refresh",
                "Parked Files",
                "Next Step",
                "Drain Evidence",
                "Drain Confidence",
                "Drain Scope",
                "Drain Checklist",
                "Drain Comparison",
                "Post-Drain Review",
                "Recent Events",
                "Last Drain",
              ],
            );
            const keyedExcludedPendingPanels = Array.from(document.querySelectorAll('[data-page-panel="pending"] > section.panel[data-layout-editor-exclude][data-panel-key]'));
            if (keyedExcludedPendingPanels.length) {
              throw new Error("Pending Publish excluded panels still received layout keys: " + keyedExcludedPendingPanels.map(headingText).join(" | "));
            }
            const pendingPanels = Array.from(document.querySelectorAll('[data-page-panel="pending"] > section.panel'));
            [
              "Drain Evidence",
              "Drain Confidence",
              "Drain Scope",
              "Drain Comparison",
              "Post-Drain Review",
              "Last Drain",
            ].forEach((heading) => {
              const panel = pendingPanels.find((candidate) => headingText(candidate) === heading);
              if (!panel) throw new Error("missing excluded advanced Pending Publish panel: " + heading);
              if (!panel.hasAttribute("data-advanced")) throw new Error("excluded Pending Publish advanced panel lost data-advanced gate: " + heading);
            });
            const nestedCompletedPanels = Array.from(document.querySelectorAll('[data-page-panel="completed"] section.panel[data-panel-key] section.panel[data-panel-key]'));
            if (nestedCompletedPanels.length) throw new Error("Completed layout still has nested managed panels: " + nestedCompletedPanels.map(headingText).join(" | "));
            const overviewPane = document.querySelector('[data-page-panel="completed"] .settings-tab-pane[data-completed-tab="overview"]');
            const overviewHeadings = panelOrderIn(overviewPane);
            ["Overview", "Final Library Promotion", "Why This Output Looks Different", "Current Output Status"].forEach((heading) => {
              if (!overviewHeadings.includes(heading)) throw new Error("Completed Overview missing movable sibling panel " + heading + "; found " + overviewHeadings.join(" | "));
            });
            const completedOverviewPanel = Array.from(overviewPane.querySelectorAll(":scope > section.panel[data-panel-key]")).find((panel) => headingText(panel) === "Overview");
            if (!completedOverviewPanel || !text(completedOverviewPanel).includes("Output Files")) {
              throw new Error("Completed Overview generated panel lost Output Files content");
            }
            window.showPage("queue");
            openDrawer();
            const beforeQueueOrder = panelOrder("queue");
            let queueSummaryRow = requireDrawerPanel("queue", "Queue Summary");
            queueSummaryRow.querySelectorAll(".layout-editor-move-button")[0].click();
            const afterQueueOrder = panelOrder("queue");
            if (beforeQueueOrder.join("|") === afterQueueOrder.join("|")) throw new Error("drawer move-up button did not reorder Queue Summary");
            const queueSummary = requireManagedPanel("queue", "Queue Summary");
            if (!queueSummary.classList.contains("panel-layout-moved")) throw new Error("move-up button did not show moved-panel animation state");
            const beforeDragOrder = panelOrder("queue");
            dragDrawerRow(requireDrawerPanel("queue", "Queue Readiness Checklist"), requireDrawerPanel("queue", "Run History"));
            const afterDragOrder = panelOrder("queue");
            if (beforeDragOrder.join("|") === afterDragOrder.join("|")) throw new Error("drawer drag/drop did not reorder panels");
            queueSummaryRow = requireDrawerPanel("queue", "Queue Summary");
            const queueSummaryPanel = panelForDrawerRow(queueSummaryRow);
            queueSummaryRow.querySelectorAll(".layout-editor-toggle-button")[0].click();
            if (!queueSummaryPanel.hasAttribute("data-panel-hidden")) throw new Error("drawer Hidden toggle did not hide Queue Summary");
            if (!text(document.getElementById("layout-editor-status")).includes("hidden")) throw new Error("drawer status did not explain hidden panel");
            requireDrawerPanel("queue", "Queue Summary").querySelectorAll(".layout-editor-toggle-button")[0].click();
            if (queueSummaryPanel.hasAttribute("data-panel-hidden")) throw new Error("drawer Hidden toggle did not restore Queue Summary");
            await requireStaleRemoteRefreshDoesNotRevertLayoutToggle(queueSummaryPanel);
            requireDrawerPanel("queue", "Queue Summary").querySelectorAll(".layout-editor-toggle-button")[1].click();
            if (queueSummaryPanel.hasAttribute("data-panel-advanced")) throw new Error("drawer Advanced toggle did not restore Queue Summary");
            const excludedRow = requireDrawerPanel("queue", "Backend-Excluded Source Files");
            const excludedPanel = panelForDrawerRow(excludedRow);
            const excludedPanelKey = excludedPanel.dataset.panelKey || "";
            if (excludedPanel.dataset.panelType !== "interactive") throw new Error("Backend-Excluded Source Files should start as interactive");
            const excludedToggleButtons = excludedRow.querySelectorAll(".layout-editor-toggle-button");
            if (excludedToggleButtons.length < 3) throw new Error("missing drawer Evidence toggle for Backend-Excluded Source Files");
            if (text(excludedToggleButtons[2]) !== "Evidence") throw new Error("third drawer toggle should be Evidence");
            excludedToggleButtons[2].click();
            if (excludedPanel.dataset.panelType !== "evidence") throw new Error("drawer Evidence toggle did not mark Backend-Excluded Source Files as evidence");
            if (storedLayoutState()[excludedPanelKey]?.panelType !== "evidence") throw new Error("drawer Evidence toggle did not persist panelType evidence");
            if (!text(document.getElementById("layout-editor-status")).includes("marked as evidence")) throw new Error("drawer status did not explain evidence panel type");
            const evidenceButtonActive = requireDrawerPanel("queue", "Backend-Excluded Source Files").querySelectorAll(".layout-editor-toggle-button")[2];
            if (!evidenceButtonActive.classList.contains("is-active")) throw new Error("Evidence toggle did not render active after marking evidence");
            window.applyEvidenceHiddenPreference(true);
            if (getComputedStyle(excludedPanel).display !== "none") throw new Error("custom evidence panel did not follow Hide Evidence");
            window.applyEvidenceHiddenPreference(false);
            requireDrawerPanel("queue", "Backend-Excluded Source Files").querySelectorAll(".layout-editor-toggle-button")[2].click();
            if (excludedPanel.dataset.panelType !== "interactive") throw new Error("drawer Evidence toggle did not restore authored panel type");
            if (storedLayoutState()[excludedPanelKey]?.panelType === "evidence") throw new Error("restored panel type should clear persisted evidence override");
            window.showPage("completed");
            openDrawer();
            const sizeEvidenceRow = requireDrawerPanel("completed", "File And Size Proof");
            sizeEvidenceRow.click();
            const evidenceSelected = document.querySelector('[data-page-panel="completed"] .settings-tab-btn[data-completed-tab="evidence"]').getAttribute("aria-selected") === "true";
            if (!evidenceSelected) throw new Error("selecting File And Size Proof did not switch to Completed Evidence");
            const sizeEvidencePanel = panelForDrawerRow(sizeEvidenceRow);
            if (!sizeEvidencePanel.classList.contains("layout-panel-preview")) throw new Error("selected drawer row did not highlight visible panel");
            window.showPage("completed");
            openDrawer();
            const overviewPaneForReset = document.querySelector('[data-page-panel="completed"] .settings-tab-pane[data-completed-tab="overview"]');
            const beforeOverviewResetOrder = panelOrderIn(overviewPaneForReset);
            const completedDetailRow = requireDrawerPanel("completed", "Why This Output Looks Different");
            completedDetailRow.click();
            completedDetailRow.querySelectorAll(".layout-editor-move-button")[1].click();
            const movedOverviewOrder = panelOrderIn(overviewPaneForReset);
            if (beforeOverviewResetOrder.join("|") === movedOverviewOrder.join("|")) throw new Error("drawer move did not change Completed Overview order before reset");
            click("layout-editor-reset-subtab");
            const afterOverviewResetOrder = panelOrderIn(overviewPaneForReset);
            if (beforeOverviewResetOrder.join("|") !== afterOverviewResetOrder.join("|")) throw new Error("Reset Current Subtab did not restore Completed Overview order");
            window.showPage("settings");
            openDrawer();
            const inactiveSettingsPanesHidden = Array.from(document.querySelectorAll('[data-page-panel="settings"] .settings-tab-pane'))
              .filter((pane) => !pane.classList.contains("is-active"))
              .every((pane) => getComputedStyle(pane).display === "none");
            if (!inactiveSettingsPanesHidden) throw new Error("inactive Settings subtab panes should remain hidden while drawer is open");
            const generatedCount = document.querySelectorAll("section.panel[data-layout-generated-panel='true'][data-panel-key]").length;
            if (generatedCount < 20) throw new Error("expected generated subsection panels, found " + generatedCount);
            return { generatedCount, keys, beforeQueueOrder, afterQueueOrder };
          })();
          `;
        }

        async function main() {
          const browser = launchBrowser([
            `--remote-debugging-port=${payload.port}`,
            "--headless=new",
            "--disable-gpu",
            "--no-first-run",
            "--no-default-browser-check",
            "--disable-extensions",
            "--disable-popup-blocking",
            "--disable-background-networking",
            "--user-data-dir=" + payload.tmpRoot + "/browser-profile",
            payload.url,
          ]);
          let client = null;
          try {
            const wsUrl = await waitForPageWebSocket(payload.port, payload.url);
            client = createCdpClient(wsUrl);
            await client.send("Runtime.enable");
            await client.send("Log.enable");
            const deadline = Date.now() + 20000;
            let appReady = false;
            while (Date.now() < deadline) {
              const ready = await client.send("Runtime.evaluate", {
                expression: `Boolean(document.readyState !== "loading" && document.getElementById("customize-layout-btn") && typeof window.showPage === "function" && document.querySelector("section.panel[data-panel-key] .panel-customize-bar"))`,
                returnByValue: true,
              });
              if (ready.result?.value === true) {
                appReady = true;
                break;
              }
              await sleep(150);
            }
            if (!appReady) throw new Error("Timed out waiting for layout manager initialization");
            const startupErrorEvents = client.consoleEvents.filter((entry) => entry.startsWith("error:") || entry.startsWith("warning:"));
            if (client.exceptions.length || startupErrorEvents.length) {
              throw new Error(`Browser startup console/exception noise: ${client.exceptions.concat(startupErrorEvents).join("; ")}`);
            }
            const result = await client.send("Runtime.evaluate", {
              expression: layoutManagerScript(),
              awaitPromise: true,
              returnByValue: true,
            });
            if (result.exceptionDetails) {
              const details = result.exceptionDetails;
              throw new Error(details.exception?.description || details.exception?.value || details.text || "browser evaluation failed");
            }
            await sleep(500);
            const errorEvents = client.consoleEvents.filter((entry) => entry.startsWith("error:") || entry.startsWith("warning:"));
            if (client.exceptions.length || errorEvents.length) {
              throw new Error(`Browser console/exception noise: ${client.exceptions.concat(errorEvents).join("; ")}`);
            }
            console.log(JSON.stringify({ ok: true, result: result.result?.value || {} }));
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


def _run_browser_layout_manager_smoke(*, browser_path: str, url: str) -> dict[str, object]:
    node = shutil.which("node")
    if not node:
        raise unittest.SkipTest("Node.js is required for the browser-backed WebView layout-manager smoke.")
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as raw_tmp:
        tmp = Path(raw_tmp)
        port = _free_port()
        payload_path = tmp / "browser-layout-manager-payload.json"
        runner_path = tmp / "browser-layout-manager-runner.cjs"
        payload_path.write_text(
            json.dumps(
                {
                    "browserPath": browser_path,
                    "port": port,
                    "tmpRoot": str(tmp),
                    "url": url,
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        runner_path.write_text(_browser_layout_manager_runner_source(), encoding="utf-8")
        return run_node_browser_smoke(
            "Browser-backed WebView layout-manager smoke",
            node=node,
            runner_path=runner_path,
            payload_path=payload_path,
            timeout_seconds=60,
        )


class WebViewBrowserLayoutManagerSmoke(unittest.TestCase):
    def test_layout_editor_drawer_manages_tab_and_subsection_boxes(self) -> None:
        browser_path = _find_browser()
        if not browser_path:
            raise unittest.SkipTest("Chrome or Edge is required for the browser-backed WebView layout-manager smoke.")

        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            resolved, _source, _output = _write_fixture_state(root)
            media_snapshot = capture_media_no_mutation_snapshot(root)
            service = DummyWorkflowFacadeService(root)
            facade = MediaPipelineApplicationFacade(service, app_version="v5-test")
            server = LocalApiServer(
                facade,
                token="browser-layout-manager-token",
                resolved_provider=lambda: resolved,
                audit_root_provider=lambda: str(root),
            )
            try:
                server.start()
                result = _run_browser_layout_manager_smoke(browser_path=browser_path, url=f"{server.url}/")
            finally:
                server.stop()
            assert_media_no_mutation(self, media_snapshot)

        browser_result = result["result"]
        self.assertGreaterEqual(browser_result["generatedCount"], 20)
        self.assertIn("settings", browser_result["keys"])
        self.assertIn("completed", browser_result["keys"])


if __name__ == "__main__":
    unittest.main()
