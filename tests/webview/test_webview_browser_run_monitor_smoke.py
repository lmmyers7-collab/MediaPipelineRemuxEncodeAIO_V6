from __future__ import annotations

import json
import shutil
import tempfile
import textwrap
import unittest
from pathlib import Path

from mediapipeline.desktop.api import LocalApiServer
from mediapipeline.desktop.application import MediaPipelineApplicationFacade

try:
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
except ImportError:  # pragma: no cover
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


def _runner_source() -> str:
    return browser_cdp_runner_prelude() + textwrap.dedent(
        r"""
        function smokeScript() {
          return `
          (async () => {
            const monitor = window.mediaPipelineRunMonitor;
            const lifecycle = window.mediaPipelineAppLifecycle;
            const byId = (id) => document.getElementById(id);
            const text = (id) => byId(id)?.textContent || "";
            const visibleText = (id) => byId(id)?.innerText || "";
            const wait = (ms = 0) => new Promise((resolve) => setTimeout(resolve, ms));
            const waitForStable = async (predicate, label, timeoutMs = 3000) => {
              const deadline = Date.now() + timeoutMs;
              let consecutivePasses = 0;
              while (Date.now() < deadline) {
                if (predicate()) {
                  consecutivePasses += 1;
                  if (consecutivePasses >= 3) return;
                } else {
                  consecutivePasses = 0;
                }
                await wait(20);
              }
              throw new Error("Timed out waiting for stable " + label);
            };
            const requireIncludes = (id, fragments) => {
              const actual = text(id);
              for (const fragment of fragments) {
                if (!actual.includes(fragment)) throw new Error(id + " missing " + fragment + "\\nActual:\\n" + actual);
              }
            };
            const requireNotIncludes = (id, fragments) => {
              const actual = text(id);
              for (const fragment of fragments) {
                if (actual.includes(fragment)) throw new Error(id + " unexpectedly included " + fragment + "\\nActual:\\n" + actual);
              }
            };
            const requireVisibleIncludes = (id, fragments) => {
              const actual = visibleText(id);
              for (const fragment of fragments) {
                if (!actual.includes(fragment)) throw new Error(id + " missing visible " + fragment + "\\nActual visible text:\\n" + actual);
              }
            };
            const requireVisibleNotIncludes = (id, fragments) => {
              const actual = visibleText(id);
              for (const fragment of fragments) {
                if (actual.includes(fragment)) throw new Error(id + " unexpectedly displayed " + fragment + "\\nActual visible text:\\n" + actual);
              }
            };
            const renderTerminalDestinationSelection = (tbodyId, statusId, row, label) => {
              const tbody = byId(tbodyId);
              if (!tbody) throw new Error("Missing terminal destination table " + tbodyId);
              const destinationRow = document.createElement("tr");
              destinationRow.dataset.rowKey = row.row_key;
              destinationRow.tabIndex = -1;
              destinationRow.setAttribute("aria-label", label + " exact backend proof");
              const cell = document.createElement("td");
              cell.textContent = label + " · " + row.row_key;
              destinationRow.appendChild(cell);
              tbody.replaceChildren(destinationRow);
              byId(statusId).textContent = label + " selected from exact backend reference";
            };
            const assertNamedButtonTarget = (node, label) => {
              if (!(node instanceof HTMLButtonElement)) throw new Error(label + " must use native button semantics.");
              const name = String(node.getAttribute("aria-label") || node.textContent || "").trim();
              if (!name) throw new Error(label + " has no accessible name.");
              const rect = node.getBoundingClientRect();
              if (rect.width < 24 || rect.height < 24) {
                throw new Error(label + " target is smaller than 24 by 24 CSS pixels: " + rect.width + "x" + rect.height);
              }
              return { label, name, width: rect.width, height: rect.height, disabled: node.disabled };
            };
            const parseColor = (value) => {
              const match = String(value || "").match(/rgba?\\(([^)]+)\\)/i);
              if (!match) return null;
              const parts = match[1].split(/[ ,/]+/).map(Number);
              if (parts.length < 3 || parts.slice(0, 3).some((part) => !Number.isFinite(part))) return null;
              return { rgb: parts.slice(0, 3), alpha: Number.isFinite(parts[3]) ? parts[3] : 1 };
            };
            const relativeLuminance = (rgb) => {
              const channels = rgb.map((channel) => {
                const value = channel / 255;
                return value <= 0.04045 ? value / 12.92 : Math.pow((value + 0.055) / 1.055, 2.4);
              });
              return 0.2126 * channels[0] + 0.7152 * channels[1] + 0.0722 * channels[2];
            };
            const contrastRatio = (left, right) => {
              const l1 = relativeLuminance(left);
              const l2 = relativeLuminance(right);
              return (Math.max(l1, l2) + 0.05) / (Math.min(l1, l2) + 0.05);
            };
            const opaqueBackground = (node) => {
              let current = node;
              while (current) {
                const parsed = parseColor(getComputedStyle(current).backgroundColor);
                if (parsed && parsed.alpha >= 0.99) return parsed.rgb;
                current = current.parentElement;
              }
              return [255, 255, 255];
            };
            const focusIndicatorEvidence = (node) => {
              const style = getComputedStyle(node);
              const outline = parseColor(style.outlineColor);
              if (!outline) throw new Error("Focus outline color was not parseable: " + style.outlineColor);
              return {
                width: style.outlineWidth,
                color: style.outlineColor,
                background: opaqueBackground(node),
                contrast: contrastRatio(outline.rgb, opaqueBackground(node)),
              };
            };
            const textContrastEvidence = (node) => {
              const style = getComputedStyle(node);
              const foreground = parseColor(style.color);
              if (!foreground) throw new Error("Text color was not parseable: " + style.color);
              const background = opaqueBackground(node);
              return {
                color: style.color,
                background,
                contrast: contrastRatio(foreground.rgb, background),
              };
            };
            const requireVisibleTrackCellLabels = (tbodyId, expectedLabels) => {
              const row = byId(tbodyId)?.querySelector("tr");
              const cells = Array.from(row?.querySelectorAll("td") || []);
              const labels = cells.map((cell) => cell.dataset.label || "");
              if (JSON.stringify(labels) !== JSON.stringify(expectedLabels)) {
                throw new Error(tbodyId + " did not expose exact responsive cell labels: " + JSON.stringify(labels));
              }
              const visibleLabels = cells.map((cell) => getComputedStyle(cell, "::before").content.replace(/[\"']/g, ""));
              if (JSON.stringify(visibleLabels) !== JSON.stringify(expectedLabels)) {
                throw new Error(tbodyId + " did not render visible responsive cell labels: " + JSON.stringify(visibleLabels));
              }
            };
            const iso = (offsetSeconds = 0) => new Date(Date.now() + offsetSeconds * 1000).toISOString();
            const evidence = (source = "synthetic_run_monitor", provenance = "backend_confirmed") => ({
              source, provenance, recorded_at: iso(-1),
            });
            const none = () => ({ kind: "none", numerator: null, denominator: null });
            const indeterminate = () => ({ kind: "indeterminate", numerator: null, denominator: null });
            const determinate = (numerator, denominator) => ({ kind: "determinate", numerator, denominator });
            const stageIds = [
              "accepted", "source_discovery", "copy_to_scratch", "probe", "route_decision", "audio",
              "subtitles", "transcode", "mux", "verification", "sidecar_writing", "publish", "final_evidence",
            ];
            const stage = (stageId, state = "not_started", progress = none(), detail = "") => ({
              stage_id: stageId,
              state,
              started_at: state === "active" ? iso(-125) : "",
              updated_at: state === "not_started" ? "" : iso(-1),
              completed_at: ["completed", "skipped", "not_applicable", "blocked", "review", "failed"].includes(state) ? iso(-1) : "",
              detail,
              reason_code: "",
              progress,
              evidence: evidence("engine_stage", "engine_event"),
            });
            const ledger = (activeId = "", options = {}) => {
              const activeIndex = stageIds.indexOf(activeId);
              return stageIds.map((stageId, index) => {
                const override = options[stageId];
                if (override) return stage(stageId, override.state, override.progress || none(), override.detail || "");
                if (activeId && index < activeIndex) return stage(stageId, "completed", none(), "Backend-confirmed complete");
                if (stageId === activeId) return stage(stageId, "active", options.progress || indeterminate(), options.detail || "Backend-confirmed active work");
                return stage(stageId);
              });
            };
            const route = (label, reasonLabel, state, value = "", reason = "") => ({
              label, reason_label: reasonLabel, state, value, reason, reason_code: value ? "fixture_policy" : "", evidence: evidence("route_ledger", value ? "engine_event" : "unknown"),
            });
            const routes = (executed = null, final = null) => ({
              planned_route: route("Planned route", "Planned reason", "available", "remux", "Queue plan says compatible streams"),
              executed_route: executed,
              final_route: final,
            });
            const collection = (kind, state = "awaiting_evidence", tracks = []) => ({
              state,
              policy_final: ["completed", "not_applicable", "failed", "review"].includes(state),
              tracks,
              evidence: evidence(kind + "_ledger", state === "awaiting_evidence" ? "unknown" : "engine_event"),
            });
            const output = (overrides = {}) => ({
              state: "awaiting_evidence",
              scratch_path: "D:\\\\Scratch\\\\Run-42\\\\input.mkv",
              working_output_path: "D:\\\\Scratch\\\\Run-42\\\\output.partial.mkv",
              published_path: "",
              parked_path: "",
              intended_final_path: "Z:\\\\Library\\\\Series\\\\Episode.mkv",
              size_bytes: null,
              verification_state: "not_started",
              sidecars: [],
              evidence: evidence("output_ledger", "engine_event"),
              ...overrides,
            });
            const item = (jobId, position, name, lifecycleState = "queued", options = {}) => ({
              job_id: jobId,
              source_identity: { value: "sha256:" + jobId, algorithm: "sha256" },
              source_path: "E:\\\\Source\\\\" + (options.parent || "Season 01") + "\\\\" + (options.sourceName || name),
              display_name: name,
              accepted_display_name: options.acceptedDisplayName || name,
              display_name_basis: options.displayNameBasis || undefined,
              display_name_evidence: options.displayNameEvidence || undefined,
              parent_context: "E:\\\\Source\\\\" + (options.parent || "Season 01"),
              position,
              total: options.total || 2,
              lifecycle_state: lifecycleState,
              lifecycle_evidence: evidence("item_ledger", lifecycleState === "queued" ? "queue_plan" : "engine_event"),
              updated_at: iso(-1),
              ...routes(options.executedRoute || null, options.finalRoute || null),
              current_stage: options.currentStage || null,
              current_progress: options.currentProgress || null,
              stages: options.stages || ledger(),
              audio: options.audio || collection("audio"),
              subtitles: options.subtitles || collection("subtitle"),
              output: options.output || output(),
              terminal_references: options.terminalReferences || [],
              failure: options.failure || { state: "none", reason_code: "", reason: "", retryable: null, reference: "", evidence: evidence("failure_ledger") },
              recovery: options.recovery || { owner: "pipeline", next_action: "Continue monitoring Current Work.", retryable: null, evidence: evidence("recovery_ledger") },
            });
            const worker = (workerId, jobId, stageId, routeValue = "remux", progress = indeterminate()) => ({
              worker_id: workerId, run_id: "run-42", job_id: jobId, state: "active", stage_id: stageId,
              route: routeValue, progress, updated_at: iso(-1), evidence: evidence("worker_heartbeat", "worker_heartbeat"),
            });
            const counts = (items) => {
              const result = { accepted: items.length, queued: 0, active: 0, completed: 0, failed: 0, skipped: 0, blocked: 0, review: 0, parked: 0, stopped: 0 };
              items.forEach((entry) => { if (Object.hasOwn(result, entry.lifecycle_state)) result[entry.lifecycle_state] += 1; });
              return result;
            };
            const projection = ({ runId = "run-42", runState = "running", freshness = "current", items = [], workers = [], stopState = "not_requested", ended = false, outcome = null, lastKnown = null, reasonCode = "backend_confirmed_current" } = {}) => ({
              schema_version: "desktop_run_monitor.v1",
              run: {
                run_id: runId, command_id: "command-42", mode: "once", scope: "backend_queue", display_mode: "Run Once · Backend Queue",
                accepted_queue: { schema_version: "queue_plan_fingerprint.v1", fingerprint: "fingerprint-" + runId, accepted_count: items.length },
                lifecycle_state: runState, started_at: iso(-600), updated_at: iso(-1), ended_at: ended ? iso(-1) : "",
                stop_after_current: { state: stopState, requested_at: stopState === "not_requested" ? "" : iso(-30), evidence: evidence("control_flag") },
                outcome,
                counts: counts(items),
                evidence: evidence("run_manifest"),
              },
              freshness: { state: freshness, reason_code: reasonCode, detail: "", updated_at: iso(-1), age_seconds: freshness === "stale" ? 120 : 1, backend_state: freshness === "current" ? "confirmed_active" : "confirmed_idle" },
              items,
              current_workers: workers,
              last_known: lastKnown,
              compatibility: { legacy_current_work_used: false },
            });
            const activeItem = (jobId, position, name, stageId, options = {}) => {
              const activeStage = stage(stageId, "active", options.progress || indeterminate(), options.detail || "Backend-confirmed active work");
              return item(jobId, position, name, "active", { ...options, stages: ledger(stageId, { ...options.stageOverrides, progress: options.progress || indeterminate(), detail: options.detail || "Backend-confirmed active work" }), currentStage: activeStage, currentProgress: activeStage.progress });
            };

            if (!monitor || typeof monitor.render !== "function") throw new Error("Run Monitor module was not available.");
            if (!lifecycle || typeof lifecycle.navigateToPage !== "function") throw new Error("Shared focus navigation was not available.");
            if (typeof window.applyAdvancedModePreference === "function") window.applyAdvancedModePreference(false);
            else document.body.classList.remove("advanced-mode");
            const liveMonitorRefresh = monitor.refresh.bind(monitor);
            await monitor.refresh({ automatic: true });
            const homeLiveRegions = Array.from(document.querySelectorAll('[data-page-panel="home"] [aria-live="polite"]'));
            if (homeLiveRegions.length !== 1) {
              throw new Error("Home must expose exactly one polite live region; saw " + homeLiveRegions.map((node) => node.id || node.className || node.tagName).join(", "));
            }

            const liveApiGet = window.apiGet;
            const requestedMonitorRoutes = [];
            let resolveUncorrelatedLatest;
            window.apiGet = async (route, options) => {
              const normalizedRoute = String(route);
              requestedMonitorRoutes.push(normalizedRoute);
              if (normalizedRoute === "/api/run-monitor") {
                return new Promise((resolve) => { resolveUncorrelatedLatest = resolve; });
              }
              if (normalizedRoute.includes("run_id=42424242424242424242424242424242")) {
                return { schema_version: "desktop_run_monitor.v1", run: null, freshness: { state: "unavailable", reason_code: "monitor_not_found", backend_state: "confirmed_idle" }, items: [], current_workers: [], last_known: null };
              }
              return liveApiGet(route, options);
            };
            const uncorrelatedRefresh = monitor.refresh({ automatic: true });
            await wait(0);
            const missingFingerprintAccepted = monitor.acceptLaunchResult({
              ok: true,
              data: {
                run_monitor: {
                  schema_version: "desktop_run_monitor_launch.v1",
                  run_id: "missing-fingerprint-run",
                  route: "/api/run-monitor",
                  acceptance_state: "awaiting_engine_confirmation",
                  expected_queue: { schema_version: "queue_plan_fingerprint.v1", fingerprint: "" },
                },
              },
            }, { navigate: false });
            if (missingFingerprintAccepted) throw new Error("Launch monitor accepted a handoff without the expected Queue fingerprint.");
            const launchAccepted = monitor.acceptLaunchResult({
              ok: true,
              data: {
                mode: "once",
                run_id: "42424242424242424242424242424242",
                accepted_queue_fingerprint: "launch-fingerprint-42",
                run_monitor: {
                  schema_version: "desktop_run_monitor_launch.v1",
                  run_id: "42424242424242424242424242424242",
                  route: "/api/run-monitor",
                  acceptance_state: "backend_accepted",
                  expected_queue: { schema_version: "queue_plan_fingerprint.v1", fingerprint: "launch-fingerprint-42" },
                },
              },
            }, { navigate: false });
            if (!launchAccepted) throw new Error("Backend Queue launch acceptance was not connected to Current Work.");
            requireIncludes("run-monitor-state", ["Starting"]);
            requireIncludes("run-monitor-freshness", ["Unknown"]);
            requireIncludes("run-monitor-authority", ["Backend Accepted", "launch-fingerprint-42", "Backend Launch Response"]);
            requireIncludes("run-monitor-items", ["loading the durable accepted workload", "No file identities"]);
            requireIncludes("run-monitor-counts", ["Backend accepted the workload", "loading durable run-wide file identities"]);
            if (byId("run-monitor-items").querySelector("[data-run-monitor-job-id]")) {
              throw new Error("Launch acceptance fabricated accepted file rows before durable engine evidence existed.");
            }
            resolveUncorrelatedLatest({ schema_version: "desktop_run_monitor.v1", run: null, freshness: { state: "unavailable", reason_code: "state_root_unavailable", backend_state: "unavailable" }, items: [], current_workers: [], last_known: null });
            await uncorrelatedRefresh;
            await wait(30);
            requireIncludes("run-monitor-state", ["Starting"]);
            if (!requestedMonitorRoutes.some((route) => route.includes("run_id=42424242424242424242424242424242"))) {
              throw new Error("Launch acceptance did not follow an uncorrelated in-flight latest request with an exact-run monitor fetch.");
            }
            window.apiGet = liveApiGet;
            monitor.refresh = async () => monitor.getPayload();

            monitor.render({ schema_version: "desktop_run_monitor.v1", run: null, freshness: { state: "unavailable", reason_code: "monitor_not_found", backend_state: "confirmed_idle" }, items: [], current_workers: [], last_known: null });
            requireIncludes("run-monitor-state", ["No run loaded"]);
            requireIncludes("run-monitor-items", ["No accepted Run Once workload"]);

            const queuedA = item("job-a", 1, "Episode 01 — The Extremely Long Distinguishing Filename.mkv", "queued", { parent: "Series Alpha\\\\Season 01" });
            const queuedB = item("job-b", 2, "Episode 01 — The Extremely Long Distinguishing Filename.mkv", "queued", { parent: "Series Beta\\\\Season 01" });
            monitor.render(projection({ runState: "starting", items: [queuedA, queuedB] }));
            requireIncludes("run-monitor-state", ["Starting"]);
            requireIncludes("run-monitor-items", [queuedA.display_name, queuedB.display_name]);
            requireIncludes("run-monitor-items-help", ["saved run predates verified cleaned-name evidence", "refresh Queue"]);

            const contradictoryNameEvidence = item(
              "job-contradictory-name",
              1,
              "Unverified Name.mkv",
              "queued",
              { displayNameEvidence: evidence("plex_destination_plan.v1", "unknown") },
            );
            monitor.render(projection({ runState: "starting", items: [contradictoryNameEvidence] }));
            requireIncludes("run-monitor-items-help", ["saved run predates verified cleaned-name evidence", "refresh Queue"]);

            const terminalReconciledName = item(
              "job-terminal-name",
              1,
              "Django Unchained (2012).mkv",
              "completed",
              {
                sourceName: "Django.Unchained.2012.1080p.BluRay.x264.YIFY.mp4",
                acceptedDisplayName: "Django.Unchained.2012.1080p.BluRay.x264.YIFY.mp4",
                displayNameBasis: "terminal_output",
                displayNameEvidence: evidence("completed_artifact", "terminal"),
              },
            );
            monitor.render(projection({ runState: "completed", items: [terminalReconciledName] }));
            requireIncludes("run-monitor-items", ["Django Unchained (2012).mkv"]);
            requireIncludes("run-monitor-items-help", ["correlated terminal output evidence"]);
            requireIncludes("run-monitor-evidence", [
              "File name authority: Exact job-correlated terminal output evidence",
              "File name evidence: Source: completed_artifact",
            ]);
            if (byId("run-monitor-items").textContent.includes("Django.Unchained.2012.1080p.BluRay.x264.YIFY.mp4")) {
              throw new Error("Terminal-reconciled accepted workload rendered the raw accepted filename.");
            }

            const compactItems = Array.from({ length: 25 }, (_, offset) => {
              const position = offset + 1;
              return item(
                "job-compact-" + position,
                position,
                "Renamed Movie " + String(position).padStart(2, "0") + " (2026).mkv",
                "queued",
                {
                  total: 25,
                  sourceName: "Raw.Release.Movie." + position + ".2160p.WEB-DL.mkv",
                  displayNameEvidence: evidence("plex_destination_plan.v1", "queue_plan"),
                },
              );
            });
            const compactPayload = projection({ runState: "starting", items: compactItems });
            monitor.render(compactPayload);
            requireIncludes("run-monitor-items-help", ["verified backend production naming plan"]);
            const workloadToggle = byId("run-monitor-items-toggle");
            assertNamedButtonTarget(workloadToggle, "Accepted workload disclosure");
            if (workloadToggle.getAttribute("aria-expanded") !== "false" || !workloadToggle.textContent.includes("Show all 25")) {
              throw new Error("Accepted workload did not default to a collapsed 20-file preview.");
            }
            if (byId("run-monitor-items").children.length !== 20 || byId("run-monitor-items").querySelector("button")) {
              throw new Error("Collapsed accepted workload must render exactly 20 noninteractive preview names.");
            }
            requireIncludes("run-monitor-items", ["Renamed Movie 01 (2026).mkv", "Renamed Movie 20 (2026).mkv"]);
            requireNotIncludes("run-monitor-items", ["Raw.Release.Movie", "Renamed Movie 21 (2026).mkv"]);
            const firstCompactPreview = byId("run-monitor-items").firstElementChild;
            const firstCompactLabel = firstCompactPreview?.getAttribute("aria-label") || "";
            if (!firstCompactLabel.startsWith("Renamed Movie 01 (2026).mkv.") || !firstCompactLabel.includes("Raw.Release.Movie.1.2160p.WEB-DL.mkv") || !firstCompactLabel.includes("Selected file detail")) {
              throw new Error("Compact workload accessible identity must lead with the planned rename, retain raw source identity, and announce selection: " + firstCompactLabel);
            }
            workloadToggle.click();
            await wait(30);
            if (workloadToggle.getAttribute("aria-expanded") !== "true" || byId("run-monitor-items").querySelectorAll("button").length !== 25) {
              throw new Error("Expanded accepted workload did not expose all 25 selectable files.");
            }
            const firstCompactButton = byId("run-monitor-items").querySelector('[data-run-monitor-job-id="job-compact-1"]');
            const firstExpandedLabel = firstCompactButton?.getAttribute("aria-label") || "";
            if (!firstExpandedLabel.startsWith("Renamed Movie 01 (2026).mkv.") || !firstExpandedLabel.includes("Raw.Release.Movie.1.2160p.WEB-DL.mkv")) {
              throw new Error("Expanded workload accessible identity must lead with the planned rename and retain raw source identity: " + firstExpandedLabel);
            }
            firstCompactButton.dispatchEvent(new KeyboardEvent("keydown", { key: "End", bubbles: true }));
            await wait(30);
            if (monitor.getSelectedJobId() !== "job-compact-25" || document.activeElement?.dataset?.runMonitorJobId !== "job-compact-25") {
              throw new Error("Expanded workload End key did not select the final accepted file.");
            }
            workloadToggle.focus();
            workloadToggle.click();
            await wait(30);
            if (document.activeElement !== workloadToggle || byId("run-monitor-items").children.length !== 20 || byId("run-monitor-items").querySelector("button")) {
              throw new Error("Folding the workload did not restore a compact preview and disclosure focus.");
            }
            monitor.render(compactPayload);
            if (workloadToggle.getAttribute("aria-expanded") !== "false" || monitor.getSelectedJobId() !== "job-compact-25") {
              throw new Error("Automatic refresh did not retain folded state and exact selected identity.");
            }

            const accessibilityRegressions = [];
            const workerFocusPayload = projection({
              runState: "running",
              items: compactItems,
              workers: [worker("worker-focus", "job-compact-1", "mux", "remux")],
            });
            monitor.render(workerFocusPayload);
            let workerFocusButton = byId("run-monitor-workers").querySelector('[data-run-monitor-worker-id="worker-focus"]');
            workerFocusButton.focus();
            workerFocusButton.click();
            await wait(30);
            if (document.activeElement !== workerFocusButton) {
              accessibilityRegressions.push("folded active-worker activation moved focus away from the worker button");
            }

            workloadToggle.click();
            await wait(30);
            workerFocusButton = byId("run-monitor-workers").querySelector('[data-run-monitor-worker-id="worker-focus"]');
            workerFocusButton.focus();
            workerFocusButton.click();
            await wait(30);
            if (document.activeElement !== workerFocusButton) {
              accessibilityRegressions.push("expanded active-worker activation moved focus away from the worker button");
            }

            const stableFocusedRow = byId("run-monitor-items").querySelector('[data-run-monitor-job-id="job-compact-1"]');
            stableFocusedRow.focus();
            let stableRefreshFocusEvents = 0;
            const stableRefreshFocusListener = (event) => {
              if (event.target?.dataset?.runMonitorJobId === "job-compact-1") stableRefreshFocusEvents += 1;
            };
            document.addEventListener("focusin", stableRefreshFocusListener);
            monitor.render(workerFocusPayload);
            await wait(30);
            document.removeEventListener("focusin", stableRefreshFocusListener);
            const stableFocusedRowAfter = byId("run-monitor-items").querySelector('[data-run-monitor-job-id="job-compact-1"]');
            if (stableFocusedRowAfter !== stableFocusedRow
                || document.activeElement !== stableFocusedRow
                || stableRefreshFocusEvents !== 0) {
              accessibilityRegressions.push(
                "unchanged automatic refresh replaced/refocused the selected workload row: focus events=" + stableRefreshFocusEvents,
              );
            }

            const repeatedItem = item(
              "job-repeat-current",
              1,
              "Repeated Current Work (2026).mkv",
              "queued",
              { displayNameEvidence: evidence("plex_destination_plan.v1", "queue_plan") },
            );
            const repeatQuietPayload = projection({ runState: "running", items: [repeatedItem], workers: [] });
            const repeatActivePayload = projection({
              runState: "running",
              items: [activeItem("job-repeat-current", 1, repeatedItem.display_name, "mux")],
              workers: [worker("worker-repeat-current", "job-repeat-current", "mux", "remux")],
            });
            monitor.render(repeatQuietPayload);
            await wait(30);
            let repeatedAnnouncementWrites = 0;
            const repeatedAnnouncementObserver = new MutationObserver(() => {
              if (text("run-monitor-announcer").includes("Repeated Current Work (2026).mkv")) {
                repeatedAnnouncementWrites += 1;
              }
            });
            repeatedAnnouncementObserver.observe(byId("run-monitor-announcer"), { childList: true, subtree: true });
            monitor.render(repeatActivePayload);
            await wait(40);
            monitor.render(repeatQuietPayload);
            await wait(30);
            monitor.render(repeatActivePayload);
            await wait(40);
            repeatedAnnouncementObserver.disconnect();
            if (repeatedAnnouncementWrites !== 2) {
              accessibilityRegressions.push(
                "active to quiet to same-active transition wrote " + repeatedAnnouncementWrites + " announcements instead of 2",
              );
            }

            monitor.render(workerFocusPayload);
            await wait(30);
            if (accessibilityRegressions.length) {
              throw new Error("Accepted-workload accessibility regressions:\\n" + accessibilityRegressions.join("\\n"));
            }
            const oldRunSelection = byId("run-monitor-items").querySelector('[data-run-monitor-job-id="job-compact-25"]');
            oldRunSelection.focus();
            monitor.render(projection({ runId: "run-43", runState: "starting", items: [queuedA, queuedB] }));
            await waitForStable(
              () => document.activeElement === workloadToggle && workloadToggle.getAttribute("aria-expanded") === "false",
              "new-run compact workload focus fallback",
            );
            monitor.render(projection({ runState: "starting", items: [queuedA, queuedB] }));
            workloadToggle.click();
            await wait(30);

            const scanningA = activeItem("job-a", 1, queuedA.display_name, "source_discovery", { parent: "Series Alpha\\\\Season 01" });
            monitor.render(projection({ runState: "scanning", items: [scanningA, queuedB], workers: [worker("worker-1", "job-a", "source_discovery")] }));
            requireIncludes("run-monitor-state", ["Scanning"]);
            requireIncludes("run-monitor-stage-list", ["Source discovery / scanning", "Active"]);

            const copyingKnown = activeItem("job-a", 1, queuedA.display_name, "copy_to_scratch", { parent: "Series Alpha\\\\Season 01", progress: determinate(50, 100), detail: "Copy bytes confirmed" });
            monitor.render(projection({ items: [copyingKnown, queuedB], workers: [worker("worker-1", "job-a", "copy_to_scratch", "", determinate(50, 100))] }));
            requireIncludes("run-monitor-stage-list", ["Copy to scratch", "50 / 100", "50%"]);
            const copyingUnknown = activeItem("job-a", 1, queuedA.display_name, "copy_to_scratch", { parent: "Series Alpha\\\\Season 01", progress: indeterminate() });
            monitor.render(projection({ items: [copyingUnknown, queuedB], workers: [worker("worker-1", "job-a", "copy_to_scratch", "", indeterminate())] }));
            requireIncludes("run-monitor-stage-list", ["Working · progress is indeterminate"]);

            const probing = activeItem("job-a", 1, queuedA.display_name, "probe", { parent: "Series Alpha\\\\Season 01" });
            monitor.render(projection({ items: [probing, queuedB], workers: [worker("worker-1", "job-a", "probe", "")] }));
            requireIncludes("run-monitor-stage-list", ["Probe", "Active"]);
            const routePending = activeItem("job-a", 1, queuedA.display_name, "route_decision", {
              parent: "Series Alpha\\\\Season 01",
              stageOverrides: { probe: { state: "not_applicable", detail: "Probe not required for this accepted item" } },
              executedRoute: route("Executed route", "Executed reason", "awaiting_evidence"),
            });
            monitor.render(projection({ items: [routePending, queuedB], workers: [worker("worker-1", "job-a", "route_decision", "")] }));
            requireIncludes("run-monitor-stage-list", ["Probe", "Not Applicable", "Route decision"]);
            requireIncludes("run-monitor-routes", ["Planned route", "Planned reason", "Executed route", "Executed reason", "Awaiting backend evidence", "Final route", "Final reason"]);
            requireVisibleIncludes("run-monitor-route-summary", ["Planned Remux", "Executed Awaiting backend evidence", "Final Unknown"]);
            requireVisibleNotIncludes("run-monitor-detail", ["Advanced route evidence", "Source: route_ledger"]);
            lifecycle.renderTopbarActivity({});
            if (byId("activity").querySelector(".activity-route-badge")) {
              throw new Error("Route-undecided current work exposed an inferred top-bar route badge.");
            }

            monitor.render({
              schema_version: "desktop_run_monitor.v1",
              run: { run_id: "run-42", mode: "once", scope: "backend_queue", display_mode: "Run Once · Backend Queue", lifecycle_state: "running", counts: { accepted: 1 }, stop_after_current: { state: "unknown" } },
              freshness: { state: "current", reason_code: "partial_backend_projection", backend_state: "confirmed_active", updated_at: iso(-1), age_seconds: 1 },
              items: [{ job_id: "job-partial", source_identity: { value: "stable-partial", algorithm: "backend" }, source_path: "E:\\Source\\Partial\\Partial Evidence.mkv", display_name: "Partial Evidence.mkv", parent_context: "E:\\Source\\Partial", position: 1, total: 1, lifecycle_state: "active", updated_at: iso(-1) }],
              current_workers: [],
            });
            requireIncludes("run-monitor-items", ["Partial Evidence.mkv", "Active"]);
            requireIncludes("run-monitor-detail-state", ["Active"]);
            requireIncludes("run-monitor-routes", ["Planned route", "Executed route", "Final route", "Unknown"]);
            requireIncludes("run-monitor-stage-list", ["No backend stage ledger loaded"]);
            requireIncludes("run-monitor-audio-body", ["Audio evidence unknown"]);
            requireIncludes("run-monitor-subtitle-body", ["Subtitle evidence unknown"]);
            requireNotIncludes("run-monitor-audio-body", ["pending"]);
            requireNotIncludes("run-monitor-subtitle-body", ["pending"]);
            requireIncludes("run-monitor-output", ["Output state", "Unknown", "Verification"]);
            requireIncludes("run-monitor-output-evidence", ["Exact verified size", "Unknown", "Scratch path", "Output evidence"]);
            requireIncludes("run-monitor-workers", ["No backend-confirmed active workers"]);

            const preRouteFinal = route("Final route", "Final reason", "unknown", "", "Source probe failed before route selection.");
            preRouteFinal.reason_code = "SOURCE_PROBE_FAILED";
            preRouteFinal.evidence = evidence("failure_artifact", "terminal");
            const preRouteFailure = item("job-pre-route-failure", 1, "Pre Route Failure.mkv", "failed", {
              total: 1,
              finalRoute: preRouteFinal,
              failure: { state: "recoverable", reason_code: "SOURCE_PROBE_FAILED", reason: "Source probe failed before route selection.", retryable: true, reference: "failure-pre-route.json", evidence: evidence("failure_artifact", "terminal") },
            });
            monitor.render(projection({ runState: "failed", freshness: "terminal", items: [preRouteFailure], ended: true }));
            requireIncludes("run-monitor-routes", ["Final route", "Unknown", "Final reason", "Source probe failed before route selection.", "SOURCE_PROBE_FAILED", "failure_artifact"]);

            const routeBadgeBackgrounds = {};
            for (const [routeValue, routeReason, stageId, stageLabel] of [["remux", "Runtime remux proof", "mux", "Mux"], ["hardware_encode", "NVENC selected by backend", "transcode", "Encode or remux"], ["cpu_encode_fallback", "Backend confirmed CPU fallback", "transcode", "Encode or remux"]]) {
              const processing = activeItem("job-a", 1, queuedA.display_name, stageId, {
                parent: "Series Alpha\\\\Season 01",
                executedRoute: route("Executed route", "Executed reason", "available", routeValue, routeReason),
                progress: determinate(25, 100),
              });
              monitor.render(projection({ items: [processing, queuedB], workers: [worker("worker-1", "job-a", stageId, routeValue, determinate(25, 100))] }));
              requireIncludes("run-monitor-routes", ["Planned route", "Executed route", routeValue, routeReason]);
              requireIncludes("run-monitor-stage-list", [stageLabel, "Active"]);
              lifecycle.renderTopbarActivity({});
              const routeBadge = byId("activity").querySelector(".activity-route-badge");
              const expectedCategory = routeValue === "remux" ? "remux" : "encode";
              if (!routeBadge || routeBadge.dataset.route !== expectedCategory || routeBadge.textContent.trim() !== expectedCategory.toUpperCase()) {
                throw new Error("Top-bar activity route badge did not reflect backend-confirmed route " + routeValue + ".");
              }
              routeBadgeBackgrounds[expectedCategory] = window.getComputedStyle(routeBadge).backgroundColor;
              if (!routeBadgeBackgrounds[expectedCategory] || routeBadgeBackgrounds[expectedCategory] === "rgba(0, 0, 0, 0)") {
                throw new Error("Top-bar activity route badge did not load its semantic background color.");
              }
            }
            if (routeBadgeBackgrounds.remux === routeBadgeBackgrounds.encode) {
              throw new Error("Remux and encode top-bar activity badges did not load distinct semantic colors.");
            }

            const audioTracks = [
              { track_id: "a0", stream_index: 1, language: "eng", source_codec: "truehd", source_channels: 8, source_layout: "7.1", planned_action: "passthrough", current_action: "copy", state: "active", output_codec: "truehd", output_channels: 8, output_layout: "7.1", is_default: true, reason_code: "profile_passthrough", reason: "Profile permits passthrough", progress: indeterminate(), result: "", started_at: iso(-125), updated_at: iso(-1), completed_at: "", evidence: evidence("audio_policy", "engine_event") },
              { track_id: "a1", stream_index: 2, language: "jpn", source_codec: "dts", source_channels: 6, source_layout: "5.1", planned_action: "transcode and downmix", current_action: "downmix", state: "active", output_codec: "aac", output_channels: 2, output_layout: "stereo", is_default: false, reason_code: "profile_downmix", reason: "Profile requests stereo companion", progress: determinate(1, 2), result: "", started_at: iso(-60), updated_at: iso(-1), completed_at: "", evidence: evidence("audio_policy", "engine_event") },
            ];
            const audioWork = activeItem("job-a", 1, queuedA.display_name, "audio", { parent: "Series Alpha\\\\Season 01", audio: collection("audio", "active", audioTracks) });
            monitor.render(projection({ items: [audioWork, queuedB], workers: [worker("worker-1", "job-a", "audio")] }));
            requireIncludes("run-monitor-audio-body", ["Stream 1", "truehd", "passthrough", "Stream 2", "downmix", "stereo", "Elapsed"]);
            requireVisibleTrackCellLabels("run-monitor-audio-body", ["Track", "Source", "Outcome"]);
            const noAudio = activeItem("job-a", 1, queuedA.display_name, "subtitles", { parent: "Series Alpha\\\\Season 01", audio: collection("audio", "not_applicable", []) });
            monitor.render(projection({ items: [noAudio, queuedB], workers: [worker("worker-1", "job-a", "subtitles")] }));
            requireIncludes("run-monitor-audio-body", ["No audio tracks", "Not applicable"]);
            requireNotIncludes("run-monitor-audio-body", ["pending"]);
            const noSubtitles = activeItem("job-a", 1, queuedA.display_name, "mux", { parent: "Series Alpha\\\\Season 01", subtitles: collection("subtitle", "not_applicable", []) });
            monitor.render(projection({ items: [noSubtitles, queuedB], workers: [worker("worker-1", "job-a", "mux")] }));
            requireIncludes("run-monitor-subtitle-body", ["No subtitle tracks", "Not applicable"]);
            requireNotIncludes("run-monitor-subtitle-body", ["pending"]);

            const subtitleBase = { track_id: "s0", stream_index: 3, source_ordinal: null, language: "jpn", source_codec: "hdmv_pgs_subtitle", source_type: "image", source_kind: "embedded", preserve: true, extract: true, convert: true, ocr: true, write_embedded: false, write_sidecar: true, planned_action: "Preserve and OCR preferred-language SRT", current_action: "OCR", state: "active", output_codec: "srt", output_location: "external_sidecar", output_path: "D:\\\\Scratch\\\\Episode.jpn.srt", parked_path: "", intended_final_path: "Z:\\\\Library\\\\Episode.jpn.srt", reason_code: "preferred_language", reason: "Original image subtitle remains preserved", result: "", started_at: iso(-180), updated_at: iso(-1), completed_at: "", evidence: evidence("subtitle_ocr", "engine_event") };
            const subtitleConversionTrack = { ...subtitleBase, track_id: "s-ass", stream_index: 4, language: "eng", source_codec: "ass", source_type: "text", ocr: false, planned_action: "Preserve and convert ASS to SRT", current_action: "ASS to SRT conversion", step_index: 2, step_total: 4, step_name: "convert", progress_unit: "cues", cue_count: null, progress: determinate(45, 90), output_path: "D:\\\\Scratch\\\\Episode.eng.srt", intended_final_path: "Z:\\\\Library\\\\Episode.eng.srt", evidence: evidence("subtitle_conversion", "engine_event") };
            const subtitleConversion = activeItem("job-a", 1, queuedA.display_name, "subtitles", { parent: "Series Alpha\\\\Season 01", subtitles: collection("subtitle", "active", [subtitleConversionTrack]) });
            monitor.render(projection({ items: [subtitleConversion, queuedB], workers: [worker("worker-1", "job-a", "subtitles", "remux", determinate(45, 90))] }));
            requireIncludes("run-monitor-subtitle-body", ["eng", "ass", "Text", "Preserve original", "Convert", "ASS to SRT conversion", "Step 2 of 4", "45 / 90 cues", "subtitle_conversion"]);
            requireNotIncludes("run-monitor-subtitle-body", ["OCR"]);
            const subtitleDeterminate = activeItem("job-a", 1, queuedA.display_name, "subtitles", { parent: "Series Alpha\\\\Season 01", subtitles: collection("subtitle", "active", [{ ...subtitleBase, step_index: 2, step_total: 4, step_name: "convert_ocr", progress_unit: "pages", cue_count: 17, progress: determinate(37, 120) }]) });
            monitor.render(projection({ items: [subtitleDeterminate, queuedB], workers: [worker("worker-1", "job-a", "subtitles", "remux", determinate(37, 120))] }));
            requireIncludes("run-monitor-subtitle-body", ["jpn", "Preserve original", "OCR", "Step 2 of 4", "Convert Ocr", "37 / 120 pages", "Cues 17", "Elapsed", "external sidecar"]);
            requireVisibleIncludes("run-monitor-subtitle-body", ["jpn", "OCR", "37 / 120 pages", "Cues 17", "External Sidecar"]);
            requireVisibleNotIncludes("run-monitor-subtitle-body", ["Track ID s0", "Started", "Source: subtitle_ocr"]);
            requireVisibleTrackCellLabels("run-monitor-subtitle-body", ["Track", "Source", "Outcome"]);
            const subtitleIndeterminate = activeItem("job-a", 1, queuedA.display_name, "subtitles", { parent: "Series Alpha\\\\Season 01", subtitles: collection("subtitle", "active", [{ ...subtitleBase, step_index: 2, step_total: 4, step_name: "convert_ocr", progress_unit: "pages", cue_count: null, progress: indeterminate() }]) });
            monitor.render(projection({ items: [subtitleIndeterminate, queuedB], workers: [worker("worker-1", "job-a", "subtitles")] }));
            requireIncludes("run-monitor-subtitle-body", ["Step 2 of 4", "Convert Ocr", "Working (pages) · progress is indeterminate", "Elapsed"]);
            requireNotIncludes("run-monitor-subtitle-body", ["pending"]);

            for (const [stageId, expected] of [["mux", "Mux"], ["verification", "Verification"], ["sidecar_writing", "Sidecar writing"]]) {
              const work = activeItem("job-a", 1, queuedA.display_name, stageId, { parent: "Series Alpha\\\\Season 01" });
              monitor.render(projection({ items: [work, queuedB], workers: [worker("worker-1", "job-a", stageId)] }));
              requireIncludes("run-monitor-stage-list", [expected, "Active"]);
            }
            const directPublication = activeItem("job-a", 1, queuedA.display_name, "publish", { parent: "Series Alpha\\\\Season 01", detail: "Backend-confirmed direct publication to verified final destination", output: output({ state: "active", verification_state: "completed", intended_final_path: "Z:\\\\Library\\\\Series Alpha\\\\Episode 01.mkv" }) });
            monitor.render(projection({ items: [directPublication, queuedB], workers: [worker("worker-1", "job-a", "publish")] }));
            requireIncludes("run-monitor-stage-list", ["Direct publish or park", "Active", "direct publication to verified final destination"]);
            requireIncludes("run-monitor-output", ["Output state", "Active", "Verification", "Completed", "Intended destination", "Series Alpha"]);
            if (byId("run-monitor-terminal-links").children.length) throw new Error("Active direct publication exposed terminal Pending/Completed proof before terminal evidence existed.");

            const multiActiveA = activeItem("job-a", 1, queuedA.display_name, "transcode", { parent: "Series Alpha\\\\Season 01", executedRoute: route("Executed route", "Executed reason", "available", "hardware_encode", "Runtime hardware encode proof") });
            const multiActiveB = activeItem("job-b", 2, queuedB.display_name, "mux", { parent: "Series Beta\\\\Season 01", executedRoute: route("Executed route", "Executed reason", "available", "remux", "Runtime remux proof") });
            const multiActivePayload = projection({
              items: [multiActiveA, multiActiveB],
              workers: [worker("worker-multi-a", "job-a", "transcode", "hardware_encode"), worker("worker-multi-b", "job-b", "mux", "remux")],
            });
            monitor.render(multiActivePayload);
            requireIncludes("run-monitor-workers", ["Worker worker-multi-a", "Worker worker-multi-b", "Series Alpha", "Series Beta"]);
            lifecycle.renderTopbarActivity({});
            const mixedRouteBadges = Array.from(byId("activity").querySelectorAll(".activity-route-badge"))
              .map((badge) => badge.dataset.route)
              .sort();
            if (JSON.stringify(mixedRouteBadges) !== JSON.stringify(["encode", "remux"])) {
              throw new Error("Mixed active routes did not expose both top-bar route badges: " + JSON.stringify(mixedRouteBadges));
            }
            const activeFileButtons = Array.from(byId("run-monitor-items").querySelectorAll(".run-monitor-item-button"))
              .filter((button) => button.getAttribute("aria-label")?.includes("Current backend worker item"));
            if (activeFileButtons.length !== 2) throw new Error("Two distinct active jobs did not expose two truthful active-file labels.");
            if (activeFileButtons.some((button) => button.hasAttribute("aria-current"))) {
              throw new Error("Plural active files must not expose multiple singular aria-current values in one workload list.");
            }
            await waitForStable(
              () => text("run-monitor-announcer").includes("Series Beta") && !text("run-monitor-announcer").includes("Series Alpha"),
              "newly active file announcement without repeating the already-active file",
            );
            let focusedWorker = byId("run-monitor-workers").querySelector('[data-run-monitor-worker-id="worker-multi-b"]');
            if (!focusedWorker) throw new Error("Distinct active worker focus target was not rendered.");
            focusedWorker.focus();
            let stableWorkerFocusEvents = 0;
            const stableWorkerFocusListener = (event) => {
              if (event.target?.dataset?.runMonitorWorkerId === "worker-multi-b") stableWorkerFocusEvents += 1;
            };
            document.addEventListener("focusin", stableWorkerFocusListener);
            monitor.render(multiActivePayload);
            await wait(30);
            document.removeEventListener("focusin", stableWorkerFocusListener);
            const focusedWorkerAfter = byId("run-monitor-workers").querySelector('[data-run-monitor-worker-id="worker-multi-b"]');
            if (focusedWorkerAfter !== focusedWorker
                || document.activeElement !== focusedWorker
                || stableWorkerFocusEvents !== 0) {
              throw new Error(
                "unchanged automatic refresh replaced/refocused the active-worker button: focus events=" + stableWorkerFocusEvents,
              );
            }

            const sameWorkerA = activeItem("job-same-worker-a", 1, "Same Worker Alpha (2026).mkv", "mux");
            const sameWorkerB = activeItem("job-same-worker-b", 2, "Same Worker Beta (2026).mkv", "mux");
            const sameWorkerQuiet = projection({ items: [sameWorkerA, sameWorkerB], workers: [] });
            const sameWorkerFileA = projection({
              items: [sameWorkerA, sameWorkerB],
              workers: [worker("worker-reused", "job-same-worker-a", "mux", "remux")],
            });
            const sameWorkerFileB = projection({
              items: [sameWorkerA, sameWorkerB],
              workers: [worker("worker-reused", "job-same-worker-b", "mux", "remux")],
            });
            const replacementWorkerSameFileB = projection({
              items: [sameWorkerA, sameWorkerB],
              workers: [worker("worker-replacement", "job-same-worker-b", "mux", "remux")],
            });
            monitor.render(sameWorkerQuiet);
            await wait(30);
            monitor.render(sameWorkerFileA);
            await wait(40);
            monitor.render(sameWorkerFileB);
            await wait(40);
            const sameWorkerHandoffAnnouncement = text("run-monitor-announcer");
            if (!sameWorkerHandoffAnnouncement.includes("Same Worker Beta (2026).mkv")
                || sameWorkerHandoffAnnouncement.includes("Same Worker Alpha (2026).mkv")) {
              throw new Error("A file handoff on the same worker did not announce the new current file: " + sameWorkerHandoffAnnouncement);
            }
            let replacementWorkerAnnouncementWrites = 0;
            const replacementWorkerObserver = new MutationObserver(() => { replacementWorkerAnnouncementWrites += 1; });
            replacementWorkerObserver.observe(byId("run-monitor-announcer"), { childList: true, subtree: true });
            monitor.render(replacementWorkerSameFileB);
            await wait(40);
            replacementWorkerObserver.disconnect();
            if (replacementWorkerAnnouncementWrites !== 0) {
              throw new Error(
                "A worker-ID replacement for the same active file produced a duplicate current-file announcement: writes="
                  + replacementWorkerAnnouncementWrites,
              );
            }
            monitor.render(multiActivePayload);
            await wait(30);

            const completedA = item("job-a", 1, queuedA.display_name, "completed", {
              parent: "Series Alpha\\\\Season 01",
              executedRoute: route("Executed route", "Executed reason", "available", "hardware_encode", "Runtime hardware encode proof"),
              finalRoute: route("Final route", "Final reason", "available", "hardware_encode", "Verified terminal route"),
              stages: ledger("", Object.fromEntries(stageIds.map((id) => [id, { state: "completed", detail: "Terminally proven" }]))),
              audio: collection("audio", "completed", audioTracks.map((track) => ({ ...track, state: "completed", current_action: "", result: "Written", progress: none(), completed_at: iso(-1) }))),
              subtitles: collection("subtitle", "completed", [{ ...subtitleBase, state: "completed", current_action: "", result: "SRT written; original preserved", progress: none(), completed_at: iso(-1) }]),
              output: output({ state: "published", verification_state: "completed", size_bytes: 987654321, published_path: "Z:\\\\Library\\\\Series Alpha\\\\Episode 01.mkv", sidecars: [{ kind: "subtitle", state: "written", path: "Z:\\\\Library\\\\Series Alpha\\\\Episode 01.jpn.srt", reason: "Preferred-language sidecar", evidence: evidence("sidecar_manifest", "terminal") }] }),
              terminalReferences: [{ kind: "completed", reference: "completed:job-a", path: "State/Completed.json", evidence: evidence("completed_manifest", "terminal") }],
              recovery: { owner: "pipeline", next_action: "No action required.", retryable: false, evidence: evidence("completed_manifest", "terminal") },
            });
            const currentB = activeItem("job-b", 2, queuedB.display_name, "mux", { parent: "Series Beta\\\\Season 01", executedRoute: route("Executed route", "Executed reason", "available", "remux", "Runtime remux proof") });
            monitor.render(projection({ items: [copyingKnown, queuedB], workers: [worker("worker-1", "job-a", "copy_to_scratch")] }));
            monitor.selectJob("job-b", { focusButton: true });
            await wait(30);
            const completedTransitionPayload = projection({ items: [completedA, currentB], workers: [worker("worker-3", "job-b", "mux")] });
            monitor.render(completedTransitionPayload);
            await wait(30);
            if (monitor.getSelectedJobId() !== "job-b" || document.activeElement?.dataset?.runMonitorJobId !== "job-b") {
              throw new Error("Automatic refresh did not preserve exact selected job identity and focus.");
            }
            requireIncludes("run-monitor-workers", ["Worker worker-3"]);
            requireIncludes("run-monitor-items", ["Completed", "Current · Active", "Selected"]);
            requireIncludes("run-monitor-routes", ["Planned route", "Executed route", "Final route"]);
            const newCurrentAnnouncement = text("run-monitor-announcer");
            const announcedLeafCount = newCurrentAnnouncement.split(queuedB.display_name).length - 1;
            if (announcedLeafCount !== 1) {
              throw new Error("One newly current file must produce one current-file announcement; saw " + announcedLeafCount + ": " + newCurrentAnnouncement);
            }
            const staleRawSnapshot = {
              activity: "Encoding Stale Legacy Name.mkv",
              pipeline_state: "processing",
              current_work: { item_label: "Stale Legacy Name.mkv", current_stage_label: "Encoding", route_label: "Route remux", percent_label: "88%" },
              progress: { Status: "Encoding", CurrentStage: "Encoding", CurrentRoute: "remux", CurrentStagePercent: 88, CurrentDisplayName: "Stale Legacy Name.mkv" },
              recent_events: [{ event_id: "uncorrelated-event", event_type: "job_progress", stage: "Encoding", route: "remux", source_path: "E:\\Old\\Stale Legacy Name.mkv", timestamp: iso() }],
            };
            lifecycle.renderTopbarActivity(staleRawSnapshot);
            lifecycle.renderTopbarEventTicker(staleRawSnapshot);
            requireIncludes("activity", [queuedB.display_name, "Run Once · Backend Queue · Running"]);
            requireNotIncludes("activity", ["Stale Legacy Name", "Encoding", "Route remux", "88%"]);
            if (byId("topbar-event-ticker")) throw new Error("The redundant supporting-telemetry row is still visible in the topbar.");
            const targetSizeEvidence = [
              assertNamedButtonTarget(byId("run-monitor-refresh"), "Refresh"),
              assertNamedButtonTarget(byId("run-monitor-stop-after-current"), "Stop After Current"),
              ...Array.from(byId("run-monitor-items").querySelectorAll(".run-monitor-item-button")).map((button, index) => assertNamedButtonTarget(button, "Accepted file " + (index + 1))),
            ];
            const monitorStopButton = byId("run-monitor-stop-after-current");
            if (monitorStopButton.disabled) throw new Error("A fresh active selected run must own an enabled Stop After Current control.");
            window.mediaPipelineLaunchView.updateLaunchCommandButtonStates(
              { pipeline_state: "idle", active_work: [] },
              { state: "ready", active_work: [] },
            );
            if (monitorStopButton.disabled) throw new Error("An unrelated idle snapshot overwrote the fresh selected-run Stop control.");
            monitor.setStopCommandBusy(true);
            if (!monitorStopButton.disabled || monitorStopButton.dataset.commandState !== "running") {
              throw new Error("The Run Monitor owner did not apply shared control-command busy state.");
            }
            monitor.setStopCommandBusy(false);
            if (monitorStopButton.disabled || monitorStopButton.dataset.commandState !== "ready") {
              throw new Error("The Run Monitor owner did not restore exact selected-run Stop availability after busy state.");
            }
            const originalFetch = window.fetch.bind(window);
            const originalConfirm = window.confirm;
            const stopControlRequests = [];
            window.confirm = () => true;
            window.fetch = async (input, init = {}) => {
              const url = String(typeof input === "string" ? input : input?.url || "");
              if (url.includes("/api/pipeline/control")) {
                stopControlRequests.push(JSON.parse(String(init.body || "{}")));
                return new Response(JSON.stringify({
                  schema_version: "desktop_command_result.v1",
                  command: "pipeline.control.stop",
                  ok: true,
                  severity: "info",
                  message: "Stop After Current requested for exact run-42.",
                  data: { run_id: "run-42", semantic_action: "stop_after_current" },
                }), { status: 200, headers: { "Content-Type": "application/json" } });
              }
              return originalFetch(input, init);
            };
            try {
              monitorStopButton.click();
              await waitForStable(
                () => stopControlRequests.length === 1 && monitorStopButton.dataset.commandState === "ready",
                "run-correlated Stop After Current request",
              );
            } finally {
              window.fetch = originalFetch;
              window.confirm = originalConfirm;
            }
            if (JSON.stringify(stopControlRequests[0]) !== JSON.stringify({ action: "stop", expected_run_id: "run-42" })) {
              throw new Error("Current Work Stop did not POST the exact displayed run identity: " + JSON.stringify(stopControlRequests[0]));
            }
            const currentFileButton = byId("run-monitor-items").querySelector('[data-run-monitor-job-id="job-b"]');
            if (currentFileButton?.getAttribute("aria-pressed") !== "true" || !currentFileButton.getAttribute("aria-label")?.includes(currentB.source_path)) {
              throw new Error("Selected file Name/Role/Value did not expose exact full identity and selected state.");
            }
            monitor.selectJob("job-a", { focusButton: true });
            await wait(30);
            requireIncludes("run-monitor-file-outcome", ["Published", "Verification completed", "942 MiB", "Audio 2 tracks", "Subtitles 1 track"]);
            requireIncludes("run-monitor-output", ["Published", "Completed", "942 MiB", "Published destination", "Episode 01.mkv"]);
            requireIncludes("run-monitor-output-evidence", ["987,654,321 bytes", "Intended final destination"]);
            requireVisibleIncludes("run-monitor-detail", ["Published", "942 MiB", "PUBLISHED DESTINATION", "Open Completed Output proof"]);
            requireVisibleNotIncludes("run-monitor-detail", ["Job ID job-a", "EXACT VERIFIED SIZE", "SCRATCH PATH", "Source: completed_manifest", "Full stage evidence"]);
            byId("advanced-toggle").click();
            await waitForStable(() => document.body.classList.contains("advanced-mode"), "Advanced evidence visibility");
            requireVisibleIncludes("run-monitor-detail", ["Job ID job-a", "EXACT VERIFIED SIZE", "987,654,321 bytes", "SCRATCH PATH", "Advanced route evidence", "Full stage evidence", "Source: completed_manifest"]);
            byId("advanced-toggle").click();
            await waitForStable(() => !document.body.classList.contains("advanced-mode"), "normal evidence visibility");
            requireIncludes("run-monitor-sidecars", ["Sidecar results", "Written", "Episode 01.jpn.srt"]);
            requireIncludes("run-monitor-terminal-links", ["Open Completed Output proof"]);
            const completedProofView = window.mediaPipelineCompletedView;
            const completedProofRow = { row_key: "completed:job-a", manifest_path: "State/Completed.json", lookup_title: "Exact completed job A" };
            completedProofView.getLastCompletedRows = () => [completedProofRow];
            completedProofView.selectCompletedRow = (row) => renderTerminalDestinationSelection("completed-rows", "completed-selected-status", row, "Exact completed job A");
            let completedProofLink = byId("run-monitor-terminal-links").querySelector('[data-run-monitor-deep-link="completed"]');
            targetSizeEvidence.push(assertNamedButtonTarget(completedProofLink, "Completed terminal proof"));
            if (!completedProofLink?.getAttribute("aria-label")?.includes("completed:job-a") || !completedProofLink.getAttribute("aria-label").includes("State/Completed.json")) {
              throw new Error("Completed proof link did not expose the exact backend reference and artifact path.");
            }
            const completedProofFocusKey = completedProofLink.dataset.runMonitorTerminalKey;
            if (!completedProofFocusKey) throw new Error("Completed proof link did not expose an exact refresh focus key.");
            completedProofLink.focus();
            monitor.render(completedTransitionPayload);
            await waitForStable(
              () => document.activeElement?.dataset?.runMonitorTerminalKey === completedProofFocusKey,
              "exact terminal-proof focus after automatic refresh",
            );
            completedProofLink = document.activeElement;
            completedProofLink.click();
            await waitForStable(
              () => text("completed-selected-status").includes("Exact completed job A")
                && document.activeElement?.dataset?.rowKey === "completed:job-a"
                && document.activeElement?.dataset?.terminalReferenceMatch === "stable_row_key",
              "Completed exact proof landing",
            );
            requireIncludes("completed-selected-status", ["Exact completed job A", "exact backend reference"]);
            if (getComputedStyle(document.querySelector('[data-page-panel="completed"]')).display === "none") throw new Error("Completed proof destination was not visibly active.");
            if (document.activeElement?.dataset?.rowKey !== "completed:job-a" || document.activeElement?.dataset?.terminalReferenceMatch !== "stable_row_key") {
              throw new Error("Completed proof did not select and focus the exact stable row key.");
            }
            lifecycle.navigateToPage("home", { restoreFocus: false });
            await wait(30);

            const homeKey = new KeyboardEvent("keydown", { key: "End", bubbles: true });
            byId("run-monitor-items").querySelector('[data-run-monitor-job-id="job-a"]').dispatchEvent(homeKey);
            await wait(30);
            if (monitor.getSelectedJobId() !== "job-b" || document.activeElement?.dataset?.runMonitorJobId !== "job-b") {
              throw new Error("End key did not move the roving file selection and focus.");
            }
            const tabStops = Array.from(byId("run-monitor-items").querySelectorAll("button")).filter((button) => button.tabIndex === 0);
            if (tabStops.length !== 1) throw new Error("Accepted workload must expose exactly one roving Tab stop.");

            const attentionItems = [
              item("job-completed", 1, "Completed.mkv", "completed", { total: 7, recovery: { owner: "pipeline", next_action: "Open Completed Output for terminal proof.", retryable: false, evidence: evidence("completed_manifest", "terminal") } }),
              item("job-failed", 2, "Failed.mkv", "failed", { total: 7, failure: { state: "recoverable", reason_code: "tool_exit", reason: "Tool exited", retryable: true, reference: "failure:2", evidence: evidence("failure_report", "terminal") }, recovery: { owner: "operator", next_action: "Open Reports, correct the failure, and retry in a new run.", retryable: true, evidence: evidence("failure_report", "terminal") }, terminalReferences: [{ kind: "failure", reference: "failure:2", path: "Reports/failure-2.json", evidence: evidence("failure_report", "terminal") }] }),
              item("job-skipped", 3, "Skipped.mkv", "skipped", { total: 7, recovery: { owner: "pipeline", next_action: "Review the skip reason; no action is required unless the file should be re-queued.", retryable: false, evidence: evidence("item_ledger", "terminal") } }),
              item("job-blocked", 4, "Blocked.mkv", "blocked", { total: 7, recovery: { owner: "operator", next_action: "Resolve the backend-reported blocker, then start a new run.", retryable: true, evidence: evidence("failure_report", "terminal") } }),
              item("job-review", 5, "Review.mkv", "review", { total: 7, recovery: { owner: "operator", next_action: "Open Reports and resolve the review evidence before retrying.", retryable: true, evidence: evidence("failure_report", "terminal") } }),
              item("job-parked", 6, "Parked.mkv", "parked", { total: 7, output: output({ state: "parked", parked_path: "D:\\\\Pending\\\\Parked.mkv", verification_state: "completed" }), recovery: { owner: "pipeline", next_action: "Open Pending Publish to review or drain the manifest-backed output.", retryable: false, evidence: evidence("pending_manifest", "terminal") }, terminalReferences: [{ kind: "pending_publish", reference: "pending:6", path: "State/Pending/6.json", evidence: evidence("pending_manifest", "terminal") }, { kind: "sidecar", reference: "pending:6", path: "State/Pending/6.json", evidence: evidence("pending_manifest", "terminal") }] }),
              item("job-stopped", 7, "Stopped.mkv", "stopped", { total: 7, failure: { state: "force_stopped", reason_code: "force_stopped_by_operator", reason: "Operator force stop", retryable: true, reference: "", evidence: evidence("force_stop_control", "terminal") }, recovery: { owner: "pipeline", next_action: "Review stop evidence before starting a new run.", retryable: true, evidence: evidence("force_stop_control", "terminal") } }),
            ];
            monitor.render(projection({ runState: "force_stopped", freshness: "terminal", items: attentionItems, ended: true, outcome: { state: "force_stopped", reason_code: "force_stopped_by_operator", reason: "Operator force stop", retryable: true, owner: "operator", next_action: "Review partial output before retrying.", evidence: evidence("force_stop_control", "terminal") }, reasonCode: "terminal_backend_evidence" }));
            await wait(30);
            window.mediaPipelineLaunchView.updateLaunchCommandButtonStates(
              { pipeline_state: "processing", active_work: [{ job_kind: "pipeline", state: "active" }] },
              { state: "blocked", active_work: [{ job_kind: "pipeline", state: "active" }] },
            );
            if (!monitorStopButton.disabled) throw new Error("Unrelated active backend work enabled Stop After Current for a terminal selected run.");
            requireIncludes("run-monitor-items", ["Completed", "Failed", "Skipped", "Blocked", "Review", "Parked", "Stopped"]);
            requireIncludes("run-monitor-outcome", ["Force Stopped", "Owner: operator", "Review partial output"]);
            requireIncludes("run-monitor-announcer", ["Parked.mkv", "is now parked"]);
            const terminalRecoveryExpectations = [
              ["job-completed", "Owner: pipeline", "Open Completed Output for terminal proof."],
              ["job-failed", "Owner: operator", "Open Reports, correct the failure, and retry in a new run."],
              ["job-review", "Owner: operator", "Open Reports and resolve the review evidence before retrying."],
              ["job-blocked", "Owner: operator", "Resolve the backend-reported blocker, then start a new run."],
              ["job-skipped", "Owner: pipeline", "Review the skip reason; no action is required unless the file should be re-queued."],
              ["job-parked", "Owner: pipeline", "Open Pending Publish to review or drain the manifest-backed output."],
              ["job-stopped", "Owner: pipeline", "Review stop evidence before starting a new run."],
            ];
            for (const [jobId, owner, nextAction] of terminalRecoveryExpectations) {
              monitor.selectJob(jobId);
              requireIncludes("run-monitor-recovery", [owner, nextAction]);
            }
            monitor.selectJob("job-failed");
            requireIncludes("run-monitor-recovery", ["Recoverable", "Tool exited", "Retryable: yes", "Owner: operator", "Open Reports, correct the failure, and retry in a new run."]);
            requireIncludes("run-monitor-terminal-links", ["Open Reports proof"]);
            const reportsProofView = window.mediaPipelineReportsView;
            const reportsProofRow = { row_key: "failure:2", source_json: "Reports/failure-2.json", source_path: "E:\\Source\\Failed.mkv", error_code: "tool_exit" };
            reportsProofView.getLastFailureRows = () => [reportsProofRow];
            reportsProofView.selectFailureRow = (row) => renderTerminalDestinationSelection("failure-rows", "failure-resolution-detail-status", row, "Exact failure job 2");
            const reportsProofLink = byId("run-monitor-terminal-links").querySelector('[data-run-monitor-deep-link="reports"]');
            targetSizeEvidence.push(assertNamedButtonTarget(reportsProofLink, "Reports terminal proof"));
            reportsProofLink.click();
            await waitForStable(
              () => text("failure-resolution-detail-status").includes("Exact failure job 2")
                && document.activeElement?.dataset?.rowKey === "failure:2"
                && document.activeElement?.dataset?.terminalReferenceMatch === "stable_row_key",
              "Reports exact proof landing",
            );
            requireIncludes("failure-resolution-detail-status", ["Exact failure job 2", "exact backend reference"]);
            if (getComputedStyle(document.querySelector('[data-page-panel="reports"]')).display === "none") throw new Error("Reports proof destination was not visibly active.");
            if (document.activeElement?.dataset?.rowKey !== "failure:2" || document.activeElement?.dataset?.terminalReferenceMatch !== "stable_row_key") {
              throw new Error("Reports proof did not select and focus the exact stable row key.");
            }
            lifecycle.navigateToPage("home", { restoreFocus: false });
            await wait(30);
            monitor.selectJob("job-parked");
            requireIncludes("run-monitor-output", ["Parked", "Parked destination", "Parked.mkv"]);
            requireIncludes("run-monitor-terminal-links", ["Open Pending Publish proof"]);
            if (byId("run-monitor-terminal-links").querySelector('[data-run-monitor-deep-link="completed"]') || byId("run-monitor-terminal-links").querySelectorAll('[data-run-monitor-deep-link="pending"]').length !== 2) {
              throw new Error("Parked sidecar proof did not remain under Pending Publish authority.");
            }
            const pendingProofView = window.mediaPipelinePendingPublishView;
            const pendingProofRow = { row_key: "pending-row-6", manifest_path: "State/Pending/6.json", local_file: "D:\\Pending\\Parked.mkv" };
            pendingProofView.getLastPendingPublishRows = () => [pendingProofRow];
            pendingProofView.selectPendingRow = (row) => renderTerminalDestinationSelection("pending-rows", "pending-selected-status", row, "Exact pending manifest 6");
            const pendingProofLink = byId("run-monitor-terminal-links").querySelector('[data-run-monitor-deep-link="pending"]');
            targetSizeEvidence.push(assertNamedButtonTarget(pendingProofLink, "Pending terminal proof"));
            pendingProofLink.click();
            await waitForStable(
              () => text("pending-selected-status").includes("Exact pending manifest 6")
                && document.activeElement?.dataset?.rowKey === "pending-row-6"
                && document.activeElement?.dataset?.terminalReferenceMatch === "artifact_path",
              "Pending exact proof landing",
            );
            requireIncludes("pending-selected-status", ["Exact pending manifest 6", "exact backend reference"]);
            if (getComputedStyle(document.querySelector('[data-page-panel="pending"]')).display === "none") throw new Error("Pending proof destination was not visibly active.");
            if (document.activeElement?.dataset?.rowKey !== "pending-row-6" || document.activeElement?.dataset?.terminalReferenceMatch !== "artifact_path") {
              throw new Error("Pending proof did not select and focus the exact manifest artifact path.");
            }
            lifecycle.navigateToPage("home", { restoreFocus: false });
            await wait(30);
            pendingProofView.getLastPendingPublishRows = () => [];
            byId("run-monitor-terminal-links").querySelector('[data-run-monitor-deep-link="pending"]').click();
            await wait(30);
            if (document.activeElement?.tagName !== "H1" || document.activeElement?.textContent.trim() !== "Pending Publish") {
              throw new Error("Unmatched terminal proof did not fall back honestly to the Pending Publish heading.");
            }
            const asynchronouslyLoadedPendingRow = { row_key: "pending-row-async-6", manifest_path: "State/Pending/6.json", local_file: "D:\\Pending\\Parked.mkv" };
            pendingProofView.getLastPendingPublishRows = () => [asynchronouslyLoadedPendingRow];
            byId("pending-rows").appendChild(document.createComment("correlated pending rows loaded"));
            await waitForStable(
              () => document.activeElement?.dataset?.rowKey === "pending-row-async-6"
                && document.activeElement?.dataset?.terminalReferenceMatch === "artifact_path",
              "asynchronously loaded Pending exact proof landing",
            );
            if (document.activeElement?.dataset?.rowKey !== "pending-row-async-6" || document.activeElement?.dataset?.terminalReferenceMatch !== "artifact_path") {
              throw new Error("Asynchronously loaded terminal proof did not re-apply the exact artifact-path handoff.");
            }
            lifecycle.navigateToPage("home", { restoreFocus: false });
            await wait(30);

            for (const [runState, stopState, expected] of [["paused", "not_requested", "Paused"], ["stop_requested", "requested", "Stop Requested"], ["stopping", "stopping", "Stopping"]]) {
              monitor.render(projection({ runState, items: [currentB, queuedA], workers: [worker("worker-2", "job-b", "mux")], stopState }));
              await wait(30);
              requireIncludes("run-monitor-state", [expected]);
              requireIncludes("run-monitor-stop-state", [stopState === "not_requested" ? "Not Requested" : stopState === "requested" ? "Requested" : "Stopping"]);
              if (stopState === "requested") requireIncludes("run-monitor-announcer", ["Stop After Current requested"]);
            }

            const currentPayload = projection({ items: [currentB, queuedA], workers: [worker("worker-2", "job-b", "mux")] });
            monitor.render(currentPayload);
            monitor.selectJob("job-b", { focusButton: true });
            await wait(30);
            const apiGetBeforeTransientFailure = window.apiGet;
            window.apiGet = async (route, options) => {
              if (String(route).startsWith("/api/run-monitor")) throw new Error("synthetic transient monitor read failure");
              return apiGetBeforeTransientFailure(route, options);
            };
            await liveMonitorRefresh({ automatic: true });
            await wait(30);
            if (monitor.getPayload()?.freshness?.state !== "unavailable") throw new Error("Transient read failure did not suppress current freshness.");
            if (monitor.getSelectedJobId() !== "job-b") throw new Error("Transient read failure erased the selected accepted file.");
            if (monitor.getPayload()?.items?.length !== 2) throw new Error("Transient read failure erased the accepted workload.");
            if (document.activeElement?.dataset?.runMonitorJobId !== "job-b") throw new Error("Transient read failure did not restore focus to the selected accepted file.");
            requireIncludes("run-monitor-items", ["Series Alpha", "Series Beta", "Unknown"]);
            requireIncludes("run-monitor-workers", ["suppressed"]);
            requireNotIncludes("run-monitor-workers", ["worker-2"]);
            requireIncludes("run-monitor-counts", ["Accepted 2", "current run-scoped counts unavailable"]);
            if (byId("run-monitor-last-known").hidden) throw new Error("Transient read failure did not retain last-known workload evidence.");
            requireIncludes("run-monitor-last-known-body", ["job-b", "Series Beta", "Mux"]);
            const lastKnownDetails = byId("run-monitor-last-known");
            lastKnownDetails.open = true;
            const focusedHistory = lastKnownDetails.querySelector('[data-last-known-job-id="job-b"]');
            focusedHistory.focus();
            await liveMonitorRefresh({ automatic: true });
            await wait(30);
            if (!lastKnownDetails.open) throw new Error("Automatic unavailable refresh collapsed Last known — not current.");
            if (document.activeElement !== focusedHistory || !focusedHistory.isConnected) throw new Error("Automatic unavailable refresh replaced or unfocused unchanged historical evidence.");

            window.apiGet = async (route, options) => String(route).startsWith("/api/run-monitor")
              ? currentPayload
              : apiGetBeforeTransientFailure(route, options);
            await liveMonitorRefresh({ automatic: true });
            await wait(30);
            window.apiGet = apiGetBeforeTransientFailure;
            if (monitor.getPayload()?.freshness?.state !== "current") throw new Error("Run Monitor did not recover after a transient read failure.");
            if (monitor.getSelectedJobId() !== "job-b") throw new Error("Monitor recovery erased the selected accepted file.");
            if (document.activeElement?.dataset?.runMonitorJobId !== "job-b") throw new Error("Monitor recovery did not land focus on the selected current-work row.");
            requireIncludes("run-monitor-workers", ["worker-2", "Mux"]);

            monitor.render({ schema_version: "desktop_run_monitor.v1", run: null, freshness: { state: "unavailable", reason_code: "monitor_not_found", backend_state: "confirmed_idle" }, items: [], current_workers: [], last_known: null });
            const suppressedCurrentB = item("job-b", 2, queuedB.display_name, "unknown", {
              parent: "Series Beta\\\\Season 01",
              executedRoute: route("Executed route", "Executed reason", "unknown"),
              finalRoute: route("Final route", "Final reason", "unknown"),
              stages: [],
              audio: collection("audio", "unknown"),
              subtitles: collection("subtitle", "unknown"),
              output: output({ state: "unknown", scratch_path: "", working_output_path: "", verification_state: "unknown", sidecars: [] }),
            });
            const stalePayload = projection({
              freshness: "stale",
              reasonCode: "evidence_stale",
              items: [completedA, suppressedCurrentB],
              workers: [],
              lastKnown: { label: "Last known — not current", updated_at: iso(-120), age_seconds: 120, items: [completedA, currentB], current_workers: currentPayload.current_workers },
            });
            monitor.render(stalePayload);
            if (monitor.getSelectedJobId() !== "job-a") throw new Error("Stale raw worker evidence incorrectly auto-selected the historical active file.");
            requireIncludes("run-monitor-freshness", ["Stale"]);
            lifecycle.renderTopbarActivity(staleRawSnapshot);
            requireIncludes("activity", ["Current-work evidence stale", "No file, stage, route, or percent claim"]);
            requireNotIncludes("activity", ["Stale Legacy Name", "Encoding", "remux", "88%"]);
            requireIncludes("run-monitor-workers", ["suppressed"]);
            requireNotIncludes("run-monitor-items", ["Encode or remux", "Current · Active"]);
            requireIncludes("run-monitor-items", [completedA.display_name, suppressedCurrentB.display_name]);
            if (workloadToggle.getAttribute("aria-expanded") === "false") {
              requireNotIncludes("run-monitor-items", ["Completed ·", "Unknown ·"]);
              workloadToggle.click();
              await wait(30);
            }
            requireIncludes("run-monitor-items", [completedA.display_name, "Completed", suppressedCurrentB.display_name, "Unknown"]);
            requireIncludes("run-monitor-detail-state", ["Completed"]);
            requireIncludes("run-monitor-routes", ["Final route", "hardware_encode", "Verified terminal route"]);
            requireIncludes("run-monitor-terminal-links", ["Open Completed Output proof"]);
            monitor.selectJob("job-b", { focusButton: true });
            await wait(30);
            requireIncludes("run-monitor-detail-state", ["Unknown"]);
            requireIncludes("run-monitor-stage-list", ["Current timeline is suppressed"]);
            requireIncludes("run-monitor-routes", ["Route claims are suppressed"]);
            requireNotIncludes("run-monitor-routes", ["Runtime remux proof"]);
            if (byId("run-monitor-last-known").hidden) throw new Error("Stale history disclosure was not available.");
            requireIncludes("run-monitor-last-known-meta", ["historical", "does not populate current file"]);

            monitor.render({ schema_version: "desktop_run_monitor.v1", run: null, freshness: { state: "unavailable", reason_code: "read_failed", detail: "Run monitor read failed", updated_at: iso(-1), age_seconds: 1, backend_state: "unavailable" }, items: [], current_workers: [], last_known: null });
            lifecycle.renderTopbarActivity(staleRawSnapshot);
            requireIncludes("activity", ["Run Once · Backend Queue", "Correlated Monitor Unavailable", "Current-work evidence unavailable", "No file, stage, route, or percent claim"]);
            requireNotIncludes("activity", ["Stale Legacy Name", "Encoding", "remux", "88%"]);
            monitor.clearBackendQueueContext();
            const coldStartBackendQueueSnapshot = {
              ...staleRawSnapshot,
              pipeline_state: "processing",
              progress_health: { available: true, stale_evidence: false },
              progress: { ...staleRawSnapshot.progress, Mode: "once", Scope: "backend_queue", RunId: "cold-start-run" },
            };
            lifecycle.renderTopbarActivity(coldStartBackendQueueSnapshot);
            requireIncludes("activity", ["Run Once · Backend Queue", "Correlated Monitor Unavailable", "No file, stage, route, or percent claim"]);
            requireNotIncludes("activity", ["Stale Legacy Name", "Encoding", "remux", "88%"]);
            lifecycle.renderTopbarActivity({
              ...coldStartBackendQueueSnapshot,
              progress_health: { available: true, stale_evidence: true },
            });
            requireIncludes("activity", ["Run Once · Backend Queue", "Correlated Monitor Unavailable", "No file, stage, route, or percent claim"]);
            requireNotIncludes("activity", ["Stale Legacy Name", "Encoding", "remux", "88%"]);
            monitor.render(stalePayload);

            monitor.render(projection({ freshness: "unknown", reasonCode: "contradictory_backend_idle", items: stalePayload.items, workers: [], lastKnown: stalePayload.last_known }));
            requireIncludes("run-monitor-freshness", ["Unknown"]);
            requireIncludes("run-monitor-authority", ["Contradictory Backend Idle"]);
            requireNotIncludes("run-monitor-workers", ["worker-2"]);
            monitor.selectJob("job-b", { focusButton: true });
            await wait(30);
            requireIncludes("run-monitor-routes", ["Route claims are suppressed"]);
            monitor.selectJob("job-a", { focusButton: true });
            await wait(30);
            if (document.activeElement?.dataset?.runMonitorJobId !== "job-a") throw new Error("Terminal row was not keyboard-focusable after unknown current evidence.");
            requireIncludes("run-monitor-detail-state", ["Completed"]);
            requireIncludes("run-monitor-terminal-links", ["Open Completed Output proof"]);

            const terminalItems = [completedA, item("job-b", 2, queuedB.display_name, "parked", { parent: "Series Beta\\\\Season 01", finalRoute: route("Final route", "Final reason", "available", "remux", "Verified and parked"), output: output({ state: "parked", parked_path: "D:\\\\Pending\\\\Episode.mkv", verification_state: "completed" }) })];
            monitor.render(projection({ runState: "completed", freshness: "terminal", items: terminalItems, ended: true, outcome: { state: "completed", reason_code: "run_complete", reason: "Every accepted item reached terminal evidence.", retryable: false, owner: "pipeline", next_action: "Review Pending Publish for parked output.", evidence: evidence("run_manifest", "terminal") }, reasonCode: "terminal_backend_evidence" }));
            requireIncludes("run-monitor-state", ["Completed"]);
            requireIncludes("run-monitor-outcome", ["Every accepted item", "Review Pending Publish"]);
            if (text("run-monitor-workers-count") !== "0 active") throw new Error("Terminal run retained an active worker count.");

            const continuousSnapshot = {
              pipeline_state: "processing",
              progress_health: { available: true, stale_evidence: false },
              current_work: { current_stage_label: "Continuous discovery", item_label: "Continuous source scanner" },
              progress: { Mode: "continuous", Status: "Processing", CurrentStage: "Scanning", CurrentDisplayName: "Continuous source scanner" },
            };
            lifecycle.renderTopbarActivity(continuousSnapshot);
            requireIncludes("activity", ["Continuous source scanner"]);
            requireNotIncludes("activity", ["Continuous discovery"]);
            requireNotIncludes("activity", ["Run Once · Backend Queue"]);
            const scheduledSnapshotWithoutRunMetadata = {
              pipeline_state: "processing",
              progress_health: { available: true, stale_evidence: false },
              current_work: { current_stage_label: "Scheduled discovery", item_label: "Scheduled source scanner" },
              progress: { Status: "Processing", CurrentStage: "Scanning", CurrentDisplayName: "Scheduled source scanner" },
            };
            lifecycle.renderTopbarActivity(scheduledSnapshotWithoutRunMetadata);
            requireIncludes("activity", ["Scheduled source scanner"]);
            requireNotIncludes("activity", ["Scheduled discovery"]);
            requireNotIncludes("activity", ["Run Once · Backend Queue"]);
            lifecycle.renderTopbarActivity(staleRawSnapshot);
            requireIncludes("activity", ["Run Once · Backend Queue", "Terminal backend evidence"]);
            requireNotIncludes("activity", ["Stale Legacy Name", "Encoding", "remux", "88%"]);

            monitor.render({ schema_version: "desktop_run_monitor.v1", run: null, freshness: { state: "unavailable", reason_code: "monitor_not_found", detail: "", updated_at: iso(), age_seconds: 0, backend_state: "confirmed_idle" }, items: [], current_workers: [], last_known: null });
            requireIncludes("run-monitor-state", ["No run loaded"]);
            requireIncludes("run-monitor-authority", ["Confirmed Idle"]);
            requireNotIncludes("run-monitor-workers", ["worker-"]);

            monitor.render(projection({ items: [completedA, currentB], workers: [worker("worker-2", "job-b", "mux")] }));
            monitor.selectJob("job-b", { focusButton: true });
            await wait(30);
            lifecycle.navigateToPage("queue", { restoreFocus: false });
            await wait(30);
            if (document.activeElement?.tagName !== "H1" || document.activeElement?.textContent.trim() !== "Queue") {
              throw new Error("Queue navigation did not land focus on the destination heading.");
            }
            const routeQuickLink = document.createElement("button");
            routeQuickLink.type = "button";
            routeQuickLink.dataset.uiQuickLink = "";
            routeQuickLink.dataset.quickLinkPage = "home";
            routeQuickLink.dataset.quickLinkFocus = "#run-monitor-detail";
            routeQuickLink.textContent = "Route evidence";
            document.querySelector('[data-page-panel="queue"]')?.appendChild(routeQuickLink);
            routeQuickLink.click();
            await wait(30);
            if (document.activeElement?.id !== "run-monitor-detail") {
              throw new Error("Route quick-link navigation did not focus the selected-file detail target.");
            }
            routeQuickLink.remove();
            lifecycle.navigateToPage("queue", { restoreFocus: false });
            await wait(30);
            lifecycle.navigateToPage("home", { restoreFocus: true });
            await wait(30);
            if (monitor.getSelectedJobId() !== "job-b" || document.activeElement?.id !== "run-monitor-detail") {
              throw new Error("Returning to Current Work did not restore the selected-file detail focus.");
            }

            const focusTarget = byId("run-monitor-items").querySelector('[data-run-monitor-job-id="job-b"]');
            if (!focusTarget) throw new Error("Selected Current Work file was not available for focus contrast validation.");
            focusTarget.focus();
            document.body.classList.remove("light-mode");
            const darkFocus = focusIndicatorEvidence(focusTarget);
            document.body.classList.add("light-mode");
            const lightFocus = focusIndicatorEvidence(focusTarget);
            if (darkFocus.width !== "3px" || lightFocus.width !== "3px") throw new Error("Visible 3px focus indicator was not present in both themes.");
            if (darkFocus.contrast < 3 || lightFocus.contrast < 3) {
              throw new Error("Focus indicator contrast was below 3:1. Dark=" + JSON.stringify(darkFocus) + " Light=" + JSON.stringify(lightFocus));
            }
            const evidenceText = document.querySelector(".run-monitor-route-card small");
            if (!evidenceText) throw new Error("Visible route evidence text was unavailable for AA contrast validation.");
            document.body.classList.remove("light-mode");
            const darkEvidenceText = textContrastEvidence(evidenceText);
            document.body.classList.add("light-mode");
            const lightEvidenceText = textContrastEvidence(evidenceText);
            if (darkEvidenceText.contrast < 4.5 || lightEvidenceText.contrast < 4.5) {
              throw new Error("Essential monitor evidence text contrast was below 4.5:1. Dark=" + JSON.stringify(darkEvidenceText) + " Light=" + JSON.stringify(lightEvidenceText));
            }
            const horizontalOverflow = document.documentElement.scrollWidth - document.documentElement.clientWidth;
            if (horizontalOverflow > 1) {
              const offenders = Array.from(document.querySelectorAll('[data-page-panel="home"] *, .workspace, .app-shell'))
                .filter((node) => { const rect = node.getBoundingClientRect(); return rect.width > 320 || rect.right > 321; })
                .sort((left, right) => right.getBoundingClientRect().right - left.getBoundingClientRect().right)
                .slice(0, 12)
                .map((node) => (node.id || node.className || node.tagName) + ":" + JSON.stringify(node.getBoundingClientRect().toJSON()));
              throw new Error("Current Work caused page-level horizontal overflow at 320 CSS pixels: " + horizontalOverflow + "\\n" + offenders.join("\\n"));
            }

            return {
              ok: true,
              selectedJobId: monitor.getSelectedJobId(),
              freshness: text("run-monitor-freshness"),
              workers: text("run-monitor-workers-count"),
              viewport: document.documentElement.clientWidth,
              horizontalOverflow,
              darkOutline: darkFocus.width,
              lightOutline: lightFocus.width,
              darkFocusContrast: darkFocus.contrast,
              lightFocusContrast: lightFocus.contrast,
              darkEvidenceTextContrast: darkEvidenceText.contrast,
              lightEvidenceTextContrast: lightEvidenceText.contrast,
              targetSizeEvidence,
            };
          })()
          `;
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
            await client.send("Emulation.setDeviceMetricsOverride", { width: 320, height: 900, deviceScaleFactor: 1, mobile: false });
            const deadline = Date.now() + 20000;
            let ready = false;
            while (Date.now() < deadline) {
              const result = await client.send("Runtime.evaluate", {
                expression: `Boolean(document.getElementById("run-monitor-items") && typeof window.mediaPipelineRunMonitor?.render === "function" && typeof window.mediaPipelineAppLifecycle?.navigateToPage === "function")`,
                returnByValue: true,
              });
              if (result.result?.value === true) { ready = true; break; }
              await sleep(150);
            }
            if (!ready) throw new Error("Run Monitor WebView globals or DOM nodes did not become ready.");
            const result = await client.send("Runtime.evaluate", { expression: smokeScript(), awaitPromise: true, returnByValue: true });
            if (result.exceptionDetails) {
              const details = result.exceptionDetails;
              throw new Error(details.exception?.description || details.exception?.value || details.text || "browser evaluation failed");
            }
            await client.send("Emulation.setEmulatedMedia", { features: [{ name: "prefers-reduced-motion", value: "reduce" }] });
            const reducedMotionResult = await client.send("Runtime.evaluate", {
              expression: `(() => {
                const target = document.querySelector(".run-monitor-item-button");
                const style = getComputedStyle(target);
                return { transitionDuration: style.transitionDuration, animationDuration: style.animationDuration, scrollBehavior: style.scrollBehavior };
              })()`,
              returnByValue: true,
            });
            const reducedMotion = reducedMotionResult.result?.value || {};
            const durationSeconds = (value) => String(value || "").split(",").map((part) => parseFloat(part) || 0).reduce((largest, value) => Math.max(largest, value), 0);
            if (durationSeconds(reducedMotion.transitionDuration) > 0.001 || durationSeconds(reducedMotion.animationDuration) > 0.001 || reducedMotion.scrollBehavior !== "auto") {
              throw new Error("Reduced-motion Current Work styles were not applied: " + JSON.stringify(reducedMotion));
            }
            const viewportCases = [
              { label: "desktop", width: 1440 },
              { label: "tablet", width: 768 },
              { label: "mobile", width: 390 },
              { label: "minimum", width: 320 },
              { label: "zoom-200-equivalent", width: 720 },
              { label: "zoom-400-equivalent", width: 360 },
            ];
            const responsive = [];
            for (const theme of ["dark", "light"]) {
              for (const viewportCase of viewportCases) {
                await client.send("Emulation.setDeviceMetricsOverride", { width: viewportCase.width, height: 1000, deviceScaleFactor: 1, mobile: false });
                await sleep(35);
                const layoutResult = await client.send("Runtime.evaluate", {
                  expression: `(() => {
                    document.body.classList.toggle("light-mode", ${JSON.stringify(theme === "light")});
                    const home = document.querySelector('[data-page-panel="home"]');
                    const overflow = document.documentElement.scrollWidth - document.documentElement.clientWidth;
                    const visibleWraps = Array.from(home?.querySelectorAll(".table-wrap") || []).filter((node) => {
                      const rect = node.getBoundingClientRect();
                      return rect.width > 0 && rect.height > 0 && getComputedStyle(node).display !== "none";
                    });
                    const twoAxis = visibleWraps.filter((node) => node.scrollWidth - node.clientWidth > 1 && node.scrollHeight - node.clientHeight > 1)
                      .map((node) => node.id || node.className || node.tagName);
                    return { width: document.documentElement.clientWidth, overflow, twoAxis };
                  })()`,
                  returnByValue: true,
                });
                if (layoutResult.exceptionDetails) throw new Error(layoutResult.exceptionDetails.text || "responsive evaluation failed");
                const layout = layoutResult.result?.value || {};
                if (Number(layout.overflow || 0) > 1) throw new Error(`${theme} ${viewportCase.label} layout overflowed by ${layout.overflow}px at ${viewportCase.width}px.`);
                if (viewportCase.width <= 390 && Array.isArray(layout.twoAxis) && layout.twoAxis.length) {
                  throw new Error(`${theme} ${viewportCase.label} required two-axis table navigation: ${layout.twoAxis.join(", ")}`);
                }
                responsive.push({ theme, label: viewportCase.label, ...layout });
              }
            }
            const errors = client.consoleEvents.filter((entry) => entry.startsWith("error:"));
            if (client.exceptions.length || errors.length) throw new Error(client.exceptions.concat(errors).join("; "));
            console.log(JSON.stringify({ ok: true, result: result.result?.value || {}, responsive, reducedMotion }));
          } finally {
            if (client) client.close();
            await terminateBrowser(browser);
          }
        }
        main().catch((error) => { console.error(error.stack || error.message || String(error)); process.exit(1); });
        """
    )


class WebViewBrowserRunMonitorSmoke(unittest.TestCase):
    def test_backend_queue_run_monitor_states_focus_and_narrow_layout(self) -> None:
        browser_path = find_browser()
        if not browser_path:
            raise unittest.SkipTest("Chrome or Edge is required for the browser-backed Run Monitor smoke.")
        node = shutil.which("node")
        if not node:
            raise unittest.SkipTest("Node.js is required for the browser-backed Run Monitor smoke.")

        with tempfile.TemporaryDirectory() as raw_root, tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as raw_tmp:
            root = Path(raw_root)
            tmp = Path(raw_tmp)
            resolved, _source, _output = _write_fixture_state(root)
            media_snapshot = capture_media_no_mutation_snapshot(root)
            server = LocalApiServer(
                MediaPipelineApplicationFacade(DummyWorkflowFacadeService(root), app_version="v6-test"),
                token="browser-run-monitor-token",
                resolved_provider=lambda: resolved,
                audit_root_provider=lambda: str(root),
            )
            payload_path = tmp / "run-monitor-payload.json"
            runner_path = tmp / "run-monitor-runner.cjs"
            try:
                server.start()
                payload_path.write_text(
                    json.dumps({"browserPath": browser_path, "port": free_port(), "tmpRoot": str(tmp), "url": f"{server.url}/"}),
                    encoding="utf-8",
                )
                runner_path.write_text(_runner_source(), encoding="utf-8")
                result = run_node_browser_smoke(
                    "Browser-backed Run Monitor state/focus smoke",
                    node=node,
                    runner_path=runner_path,
                    payload_path=payload_path,
                    timeout_seconds=60,
                )
            finally:
                server.stop()
            assert_media_no_mutation(self, media_snapshot)

        self.assertTrue(result["ok"])
        self.assertEqual(result["result"]["selectedJobId"], "job-b")
        self.assertGreaterEqual(result["result"]["viewport"], 300)
        self.assertLessEqual(result["result"]["viewport"], 320)
        self.assertLessEqual(result["result"]["horizontalOverflow"], 1)
        self.assertEqual(result["result"]["darkOutline"], "3px")
        self.assertEqual(result["result"]["lightOutline"], "3px")
        self.assertGreaterEqual(result["result"]["darkFocusContrast"], 3.0)
        self.assertGreaterEqual(result["result"]["lightFocusContrast"], 3.0)
        self.assertGreaterEqual(result["result"]["darkEvidenceTextContrast"], 4.5)
        self.assertGreaterEqual(result["result"]["lightEvidenceTextContrast"], 4.5)
        self.assertTrue(all(entry["width"] >= 24 and entry["height"] >= 24 for entry in result["result"]["targetSizeEvidence"]))
        self.assertEqual(result["reducedMotion"]["scrollBehavior"], "auto")
        self.assertEqual(len(result["responsive"]), 12)
        self.assertEqual(
            {(entry["theme"], entry["label"]) for entry in result["responsive"]},
            {
                (theme, label)
                for theme in ("dark", "light")
                for label in ("desktop", "tablet", "mobile", "minimum", "zoom-200-equivalent", "zoom-400-equivalent")
            },
        )
        self.assertTrue(all(entry["overflow"] <= 1 for entry in result["responsive"]))


if __name__ == "__main__":
    unittest.main()
