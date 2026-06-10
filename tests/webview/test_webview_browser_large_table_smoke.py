from __future__ import annotations

import json
import shutil
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path


def _find_repo_root(start: Path) -> Path:
    for candidate in (start.resolve(), *start.resolve().parents):
        if (candidate / "AGENTS.md").exists() and (candidate / "src" / "mediapipeline").exists():
            return candidate
    raise RuntimeError(f"Could not locate repository root from {start}")


REPO_ROOT = _find_repo_root(Path(__file__))
sys.path.insert(0, str(REPO_ROOT / "src"))

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


def _browser_large_table_runner_source() -> str:
    return browser_cdp_runner_prelude() + textwrap.dedent(
        r"""
        function largeTableScript() {
          return `
          (async () => {
            const posts = [];
            const priorityPosts = [];
            const priorityConfirmMessages = [];
            window.confirm = (message) => {
              priorityConfirmMessages.push(String(message || ""));
              return true;
            };
            window.apiPost = async (path, body) => {
              const route = String(path || "");
              posts.push(route);
              if (route === "/api/queue/priority") {
                priorityPosts.push({ url: route, body: body || {} });
                return { command: "queue.priority", ok: true, data: { count: (body?.items || []).length } };
              }
              return { ok: false, message: "large-table smoke blocks mutation posts", request: body || {} };
            };
            function byId(id) { return document.getElementById(id); }
            function text(id) { const node = byId(id); return node ? node.textContent || "" : ""; }
            function setValue(id, value) {
              const node = byId(id);
              if (!node) throw new Error("missing input " + id);
              node.value = value;
              node.dispatchEvent(new Event("input", { bubbles: true }));
              node.dispatchEvent(new Event("change", { bubbles: true }));
            }
            function pressShortcut(key) {
              const event = new KeyboardEvent("keydown", { key, bubbles: true, cancelable: true });
              document.dispatchEvent(event);
              return event.defaultPrevented;
            }
            function requireActivePage(page) {
              const active = document.querySelector("[data-page-panel].is-visible")?.dataset.pagePanel || "";
              if (active !== page) throw new Error("expected active page " + page + ", got " + active);
            }
            function requireActiveElement(id) {
              const active = document.activeElement?.id || "";
              if (active !== id) throw new Error("expected active element " + id + ", got " + active);
            }
            function requireText(id, fragments) {
              const actual = text(id);
              for (const fragment of fragments) {
                if (!actual.includes(fragment)) throw new Error(id + " missing " + fragment + "\\nActual:\\n" + actual);
              }
            }
            function requireFunction(name) {
              if (typeof window[name] !== "function") throw new Error("missing global function " + name);
            }
            function requireRenderedRows(selector, expected) {
              const count = document.querySelectorAll(selector).length;
              if (count !== expected) throw new Error(selector + " expected " + expected + " rendered rows, got " + count);
            }
            function visibleRenderedRows(selector) {
              return Array.from(document.querySelectorAll(selector)).filter((row) => !row.hidden).length;
            }
            function enhancedTableState(tbodyId) {
              window.mediaPipelineDom?.enhanceDataTables?.();
              const tbody = byId(tbodyId);
              if (!tbody) throw new Error("missing table body " + tbodyId);
              const table = tbody.closest("table");
              if (!table) throw new Error("missing table for " + tbodyId);
              const toolbar = document.querySelector('[data-table-toolbar-for="' + table.id + '"]');
              if (!toolbar) throw new Error("missing shared table toolbar for " + tbodyId);
              const filter = toolbar.querySelector(".table-ui-filter");
              const density = toolbar.querySelector(".table-density-control");
              const columns = toolbar.querySelector(".table-column-menu");
              const filterToggle = toolbar.querySelector(".table-column-filter-toggle");
              if (!table.classList.contains("is-enhanced-table")) throw new Error(tbodyId + " was not enhanced");
              if (!filter || !density || !columns || !filterToggle) throw new Error(tbodyId + " missing shared table controls");
              if (!table.querySelector("th[data-sticky-column]")) throw new Error(tbodyId + " missing sticky identifier columns");
              if (!table.querySelector(".table-sort-button")) throw new Error(tbodyId + " missing sortable headers");
              return { tbody, table, toolbar, filter, density, columns, filterToggle };
            }
            function requireSharedTableFilter(tbodyId, selector, needle, expectedVisible) {
              const state = enhancedTableState(tbodyId);
              state.filter.value = needle;
              state.filter.dispatchEvent(new Event("input", { bubbles: true }));
              const visible = visibleRenderedRows(selector);
              if (visible !== expectedVisible) {
                throw new Error(tbodyId + " shared filter expected " + expectedVisible + " visible rows, got " + visible);
              }
              if (!state.toolbar.textContent.includes(String(expectedVisible) + " shown")) {
                throw new Error(tbodyId + " toolbar summary did not report filtered rows: " + state.toolbar.textContent);
              }
              state.filter.value = "";
              state.filter.dispatchEvent(new Event("input", { bubbles: true }));
            }
            function click(selector, label) {
              const node = document.querySelector(selector);
              if (!node) throw new Error("missing " + label + " selector " + selector);
              node.click();
            }
            function clickRowContaining(selector, fragment) {
              const rows = Array.from(document.querySelectorAll(selector));
              const row = rows.find((candidate) => (candidate.textContent || "").includes(fragment));
              if (!row) throw new Error(selector + " missing row containing " + fragment);
              row.click();
            }
            function requireQueueScrollPreservedOnSelection(fragment) {
              const wrap = document.querySelector('[data-page-panel="queue"] .queue-table-wrap');
              if (!wrap) throw new Error("missing queue table scroll wrapper");
              wrap.scrollTop = wrap.scrollHeight;
              const before = wrap.scrollTop;
              if (before <= 0) throw new Error("queue table did not become scrollable");
              clickRowContaining("#queue-rows tr[data-row-key]", fragment);
              const after = wrap.scrollTop;
              if (after < Math.max(1, before - 3)) {
                throw new Error("queue table scroll reset after row selection: before=" + before + " after=" + after);
              }
            }
            function requireCompletedScrollPreservedOnSelection(fragment) {
              const row = Array.from(document.querySelectorAll("#completed-rows tr[data-row-key]"))
                .find((candidate) => (candidate.textContent || "").includes(fragment));
              if (!row) throw new Error("completed table missing row containing " + fragment);
              const wrap = row.closest(".table-wrap");
              if (!wrap) throw new Error("missing completed table scroll wrapper");
              wrap.style.height = "220px";
              wrap.style.maxHeight = "220px";
              wrap.style.overflow = "auto";
              wrap.scrollTop = wrap.scrollHeight;
              const before = wrap.scrollTop;
              if (before <= 0) throw new Error("completed table did not become scrollable");
              row.click();
              const after = wrap.scrollTop;
              if (after < Math.max(1, before - 3)) {
                throw new Error("completed table scroll reset after row selection: before=" + before + " after=" + after);
              }
            }
            function requirePendingScrollPreservedOnSelection(fragment) {
              const row = Array.from(document.querySelectorAll("#pending-rows tr[data-row-key]"))
                .find((candidate) => (candidate.textContent || "").includes(fragment));
              if (!row) throw new Error("pending table missing row containing " + fragment);
              const wrap = row.closest(".table-wrap");
              if (!wrap) throw new Error("missing pending table scroll wrapper");
              wrap.style.height = "220px";
              wrap.style.maxHeight = "220px";
              wrap.style.overflow = "auto";
              wrap.scrollTop = wrap.scrollHeight;
              const before = wrap.scrollTop;
              if (before <= 0) throw new Error("pending table did not become scrollable");
              row.click();
              const after = wrap.scrollTop;
              if (after < Math.max(1, before - 3)) {
                throw new Error("pending table scroll reset after row selection: before=" + before + " after=" + after);
              }
            }
            function pad(index) { return String(index + 1).padStart(3, "0"); }
            [
              "renderQueue", "renderQueueRows", "selectQueueRow",
              "renderCompleted", "renderCompletedRows", "selectCompletedRow", "renderCompletedInventoryProgress", "completedInventoryProgressBars",
              "renderPendingPublish", "renderPendingRows", "selectPendingRow", "renderPendingInventoryProgress", "pendingInventoryProgressBars"
            ].forEach(requireFunction);

            const queueRows = Array.from({ length: 260 }, (_value, index) => {
              const label = "Large Queue " + pad(index);
              const blocked = index === 259;
              return {
                row_key: "queue-large-" + pad(index),
                global_order: index + 1,
                queue_index: index + 1,
                queue_total: 260,
                media_type: index % 3 === 0 ? "movie" : index % 3 === 1 ? "tv" : "episode",
                display_name: label,
                relative_path: "Large/" + label + ".mkv",
                source_path: "C:/Source/Large/" + label + ".mkv",
                source_root: "C:/Source",
                route_name: index % 2 ? "encode" : "remux",
                route_reason: "large smoke route proof",
                route_decision_summary: index % 2 ? "encode route" : "remux route",
                operator_status: blocked ? "blocked by source parse" : "ready for launch",
                operator_trust_state: blocked ? "blocked" : "ready",
                operator_guidance: blocked ? "Review TV parse before launch." : "Ready after launch preflight agrees.",
                blocked_reason_code: blocked ? "tv_parse_unreliable" : "",
                blocked_reason: blocked ? "Episode/season parse was ambiguous." : "",
                review_flags: blocked ? ["blocked:tv_parse_unreliable"] : [],
                recommended_diagnostics_targets: ["queue_snapshot", "last_stderr"],
                proof_summary: ["large payload queue row", "render cap smoke"],
              };
            });
            const queuePayload = {
              ok: true,
              count: 260,
              rows: queueRows,
              source_roots: ["C:/Source"],
              snapshot_exists: true,
              produced_at: "2026-05-14T00:00:00Z",
              queue_progress: {
                schema_version: "desktop_queue_source_scan_progress.v1",
                status: "complete",
                summary_lines: [
                  "Queue source scan progress:",
                  "Source candidates: 260",
                  "Progress mode: indeterminate until backend scanner telemetry emits a reliable candidate numerator and denominator."
                ],
                progress_bars: [{
                  id: "queue_source_scan",
                  label: "Queue source scan",
                  mode: "indeterminate",
                  status: "complete",
                  detail: "Source candidates: 260 | runnable 260",
                  source: "queue_snapshot.json",
                  updated_at: "2026-05-14T00:00:00Z",
                  stale: false
                }]
              }
            };
            window.renderQueue(queuePayload);
            requireText("queue-status", ["250 shown / 260 filtered / 260 rows"]);
            requireText("queue-progress-status", ["Complete"]);
            requireText("queue-progress-summary", ["Queue source scan progress:", "Source candidates: 260", "indeterminate until backend scanner telemetry"]);
            requireText("queue-progress-bars", ["Queue source scan", "complete", "Source candidates: 260"]);
            requireText("queue-filter-summary", ["Display cap: only the first 250 filtered rows are rendered", "filtering the Queue table does not change backend launch scope"]);
            requireText("queue-table-legend", ["Queue rows: 250 selectable rows"]);
            requireRenderedRows("#queue-rows tr[data-row-key]", 250);
            requireSharedTableFilter("queue-rows", "#queue-rows tr[data-row-key]", "Large Queue 240", 1);
            if (!pressShortcut("2")) throw new Error("Queue page shortcut should be handled before scroll preservation check");
            requireActivePage("queue");
            requireQueueScrollPreservedOnSelection("Large Queue 240");
            requireText("queue-detail", ["Queue selected-row detail:", "Large Queue 240", "Mutation guardrail"]);
            setValue("queue-filter", "Large Queue 001");
            window.mediaPipelineQueueView.renderQueueRows();
            requireText("queue-status", ["1 / 260 rows"]);
            requireText("queue-filter-summary", ["Hidden review rows: 1", "blocked/warning rows are currently hidden"]);
            requireText("queue-backend-scope-summary", [
              "Backend launch scope boundary:",
              "visible after filters: 1/260",
              "hidden blocked/review rows: 1/1",
              "Queue filters, row selection, and rendered table caps are not submitted as processing scope.",
            ]);
            requireText("queue-decision-summary", [
              "Queue decision header:",
              "Visible rows after display filters: 1/260",
              "Hidden blocked/review rows: 1/1",
              "Backend launch scope is owned by Launch",
            ]);
            requireText("queue-backend-scope-rows", [
              "Display filter vs launch scope",
              "Selecting a row cannot make Launch process only that row.",
            ]);
            requireText("queue-launch-decision-summary", [
              "Daily-use handoff: Queue evidence decides whether it is sensible to open Launch",
              "Operator outcome:",
              "Scope boundary: Queue filters, selected rows, review boards",
              "display filter scope",
              "Blocked/review/read-first/unknown",
            ]);
            clickRowContaining("#queue-launch-decision-rows tr", "Display filter / backend launch scope");
            requireText("queue-launch-decision-detail", ["visible WebView table subset", "hidden blocked rows: 1", "hidden review rows: 1", "Queue filters never launch"]);
            if (!pressShortcut("2")) throw new Error("Queue page shortcut should be handled");
            requireActivePage("queue");
            if (!pressShortcut("/")) throw new Error("Queue search shortcut should be handled");
            requireActiveElement("queue-filter");
            document.activeElement.blur();
            setValue("queue-filter", "Large Queue 001");
            if (!pressShortcut("j")) throw new Error("Queue next-row shortcut should be handled");
            requireText("queue-detail", ["Queue selected-row detail:", "Large Queue 001", "Mutation guardrail"]);
            if (!pressShortcut("d")) throw new Error("Queue detail shortcut should be handled");
            requireActiveElement("queue-detail");
            if (!pressShortcut("c")) throw new Error("Queue clear-filter shortcut should be handled");
            requireText("queue-status", ["250 shown / 260 filtered / 260 rows"]);

            const loadedMovieRows = queueRows.filter((row) => String(row.media_type || "").toLowerCase() === "movie");
            const loadedTvRows = queueRows.filter((row) => String(row.media_type || "").toLowerCase() === "tv");
            setValue("queue-filter", "Large Queue 001");
            window.mediaPipelineQueueView.renderQueueRows();
            requireText("queue-priority-promote-movies-btn", ["All Loaded Movies"]);
            requireText("queue-priority-promote-tv-btn", ["All Loaded TV"]);
            requireText("queue-priority-status", [
              "Selected-row priority actions apply only to checked rows.",
              "All Loaded Movies and All Loaded TV apply to loaded queue rows regardless of display filters or render cap.",
              "They do not define Launch scope.",
            ]);
            const originalRefreshAll = window.refreshAll;
            window.refreshAll = async () => {};
            click("#queue-priority-promote-movies-btn", "all loaded movie priority");
            click("#queue-priority-promote-tv-btn", "all loaded TV priority");
            await new Promise((resolve) => setTimeout(resolve, 150));
            window.refreshAll = originalRefreshAll;
            if (priorityConfirmMessages.length !== 2) {
              throw new Error("expected movie and TV loaded-row confirmations: " + JSON.stringify(priorityConfirmMessages));
            }
            for (const fragment of [
              "Loaded queue rows: 260.",
              "This loaded-row action ignores display filters and the table render cap",
              "Backend Launch scope remains unchanged",
              "does not touch source, scratch, output, or rename files",
            ]) {
              if (!priorityConfirmMessages.join("\\n").includes(fragment)) {
                throw new Error("loaded-row confirmation missing " + fragment + "\\nActual:\\n" + priorityConfirmMessages.join("\\n---\\n"));
              }
            }
            if (!priorityConfirmMessages[0].includes("Current display-filter matches for movie: 1.")) {
              throw new Error("movie confirmation did not disclose filtered movie count: " + priorityConfirmMessages[0]);
            }
            if (!priorityConfirmMessages[1].includes("Current display-filter matches for tv: 0.")) {
              throw new Error("TV confirmation did not disclose filtered TV count: " + priorityConfirmMessages[1]);
            }
            if (priorityPosts.length !== 2) {
              throw new Error("expected two queue priority posts: " + JSON.stringify(priorityPosts));
            }
            if ((priorityPosts[0].body?.items || []).length !== loadedMovieRows.length) {
              throw new Error("movie bulk post did not include all loaded movie rows: " + JSON.stringify(priorityPosts[0]));
            }
            if ((priorityPosts[1].body?.items || []).length !== loadedTvRows.length) {
              throw new Error("TV bulk post did not include all loaded TV rows: " + JSON.stringify(priorityPosts[1]));
            }
            requireText("queue-priority-status", ["Promoted " + loadedTvRows.length + " loaded TV row(s) to High."]);
            window.renderQueue(queuePayload);
            setValue("queue-filter", "");
            window.mediaPipelineQueueView.renderQueueRows();

            const completedRows = Array.from({ length: 260 }, (_value, index) => {
              const label = "Large Completed " + pad(index);
              const blocked = index === 259;
              return {
                row_key: "completed-large-" + pad(index),
                completed_at: "2026-05-14T00:00:00Z",
                lookup_title: label,
                output_file: label + ".mkv",
                output_path: "C:/Output/Large/" + label + ".mkv",
                source_path: "C:/Source/Large/" + label + ".mkv",
                sidecar_path: "C:/Output/Large/" + label + ".pipeline.json",
                route: index % 2 ? "encode" : "remux",
                route_label: index % 2 ? "Encode" : "Remux",
                library_id: index % 2 ? "tv-library" : "movie-library",
                library_name: index % 2 ? "TV Library" : "Movie Library",
                library_designation: index % 2 ? "tv" : "movie",
                publish: "completed",
                media_type: index % 3 === 0 ? "movie" : index % 3 === 1 ? "tv" : "episode",
                output_exists: !blocked,
                output_health: blocked ? "missing output" : "ok",
                sidecar_exists: !blocked,
                consistency_status: blocked ? "broken" : "ok",
                consistency_issues: blocked ? ["missing_output", "missing_sidecar"] : [],
                size_growth_over_5: blocked,
                size_delta_label: blocked ? "+110%" : "-5%",
                audio_decision_count: blocked ? 2 : 1,
                subtitle_decision_count: blocked ? 5 : 2,
                operator_status: blocked ? "completed proof conflict" : "completed proof ready",
                operator_trust_state: blocked ? "broken-output" : "ready",
                operator_guidance: blocked ? "Inspect Completed Manifest and Pending Publish before rerun." : "Compare output proof if needed.",
                recommended_diagnostics_targets: ["completed_manifest", "pending_publish", "last_stderr"],
                proof_summary: ["large payload completed row", "render cap smoke"],
              };
            });
            window.renderCompleted({
              ok: true,
              count: 260,
              encode_count: 130,
              remux_count: 130,
              missing_output_count: 1,
              rows: completedRows,
              manifest_exists: true,
              manifest_path: "C:/State/completed.json",
              inventory_progress: {
                schema_version: "desktop_completed_inventory_progress.v1",
                status: "complete",
                rows_scanned: 260,
                rows_loaded: 260,
                source: "C:/State/completed.json",
                detail: "Completed inventory loaded 260 row(s).",
                updated_at: "2026-05-17T12:00:00",
                progress_bars: [{
                  id: "completed_inventory",
                  label: "Completed inventory",
                  mode: "determinate",
                  percent: 100,
                  status: "complete",
                  detail: "Completed inventory loaded 260 row(s).",
                  source: "C:/State/completed.json",
                  updated_at: "2026-05-17T12:00:00",
                  stale: false,
                }],
              },
            });
            requireText("completed-count", ["259"]);
            requireText("completed-encode-count", ["129"]);
            requireText("completed-remux-count", ["130"]);
            requireText("completed-missing-count", ["1"]);
            requireText("completed-status", ["1 missing from expected destination / 250 shown / 259 filtered / 259 rows"]);
            requireText("completed-current-summary", ["Current outputs present at expected destination: 259", "Current encoded/remuxed: 129 / 130", "Completed history rows not currently present: 1"]);
            requireText("completed-reconciliation-hint", ["Backend publish reconciliation: not loaded.", "Advanced -> Refresh Backend Reconciliation"]);
            requireText("completed-inventory-progress-bars", ["Completed inventory", "100%", "Completed inventory loaded 260 row(s)."]);
            requireText("completed-filter-summary", ["Display cap: only the first 250 filtered rows are rendered", "filtering Current Output Status does not mark outputs accepted"]);
            requireText("completed-table-legend", ["Current output rows: 250 selectable rows"]);
            requireRenderedRows("#completed-rows tr[data-row-key]", 250);
            requireRenderedRows("#completed-history-rows tr[data-row-key]", 250);
            requireSharedTableFilter("completed-rows", "#completed-rows tr[data-row-key]", "Large Completed 240", 1);
            const completedLibrarySelect = byId("completed-library-filter");
            const tvLibraryOption = Array.from(completedLibrarySelect.options).find((option) => option.textContent === "TV Library");
            if (!tvLibraryOption) {
              throw new Error("Completed library filter should include TV Library.");
            }
            setValue("completed-library-filter", tvLibraryOption.value);
            requireText("completed-status", ["1 missing from expected destination / 129 / 259 rows"]);
            requireText("completed-filter-summary", ["library=TV Library", "showing 129 of 259 rows"]);
            requireRenderedRows("#completed-rows tr[data-row-key]", 129);
            setValue("completed-library-filter", "all");
            if (!pressShortcut("3")) throw new Error("Completed Output shortcut should be handled before scroll preservation check");
            requireActivePage("completed");
            requireCompletedScrollPreservedOnSelection("Large Completed 240");
            requireText("completed-detail", ["Completed selected-row detail:", "Large Completed 240", "Mutation guardrail"]);
            setValue("completed-history-filter", "Large Completed 260");
            window.mediaPipelineCompletedView.renderCompletedRows();
            requireText("completed-history-status", ["1 / 260 rows"]);
            requireText("completed-history-filter-summary", ["Completed history filter", "Hidden review rows: 0"]);
            requireRenderedRows("#completed-history-rows tr[data-row-key]", 1);
            setValue("completed-filter", "Large Completed 001");
            window.mediaPipelineCompletedView.renderCompletedRows();
            requireText("completed-status", ["1 missing from expected destination / 1 / 259 rows"]);
            requireText("completed-filter-summary", ["Hidden review rows: 0", "not hiding blocked/warning rows"]);
            requireText("completed-output-acceptance-summary", [
              "Daily-use handoff: Completed evidence supports an operator trust decision",
              "Operator outcome:",
              "Scope boundary: Current Output filters, Completed History filters",
              "display filter scope",
              "Blocked checkpoints",
              "Review checkpoints",
            ]);
            clickRowContaining("#completed-output-acceptance-rows tr", "Display filter / backend action scope");
            requireText("completed-output-acceptance-detail", ["Current Output display filter / backend action scope", "hidden blocked rows: 0", "hidden review rows: 0", "Current Output filters never accept outputs"]);
            window.selectCompletedRow(completedRows[259]);
            requireText("completed-selected-summary", [
              "Large Completed 260.mkv",
              "Output unavailable",
              "Trust state: output unavailable",
              "Primary concern",
              "completed row points to a missing output",
              "Recommended next check",
              "Inspect Completed Manifest and Pending Publish before rerun.",
              "Route",
              "Encode",
              "Size change",
              "+110%",
              "Audio tracks",
              "2",
              "Subtitle tracks",
              "5",
              "Current table visibility",
              "Selected row visible in table: no",
              "Policy / route reason",
              "Paths",
              "Authority: this summary is read-only",
            ]);
            requireText("completed-detail", ["Large Completed 260", "Selected row visible in table: no", "not present in Current Output Status table", "text filter=\\"Large Completed 001\\"", "Mutation guardrail"]);
            if (!pressShortcut("3")) throw new Error("Completed Output shortcut should be handled");
            requireActivePage("completed");
            if (!pressShortcut("/")) throw new Error("Output search shortcut should be handled");
            requireActiveElement("completed-filter");
            document.activeElement.blur();
            setValue("completed-filter", "Large Completed 001");
            if (!pressShortcut("j")) throw new Error("Output next-row shortcut should be handled");
            requireText("completed-detail", ["Completed selected-row detail:", "Large Completed 001", "Mutation guardrail"]);
            if (!pressShortcut("d")) throw new Error("Output detail shortcut should be handled");
            requireActiveElement("completed-detail");
            if (!pressShortcut("c")) throw new Error("Output clear-filter shortcut should be handled");
            requireText("completed-status", ["1 missing from expected destination / 250 shown / 259 filtered / 259 rows"]);

            const pendingRows = Array.from({ length: 260 }, (_value, index) => {
              const label = "Large Pending " + pad(index);
              const blocked = index === 259;
              return {
                row_key: "pending-large-" + pad(index),
                state: blocked ? "unreadable_manifest" : "ready",
                local_file: "C:/Scratch/Pending/" + label + ".mkv",
                server_out: "C:/Output/Pending/" + label + ".mkv",
                source_path: "C:/Source/Large/" + label + ".mkv",
                manifest_path: "C:/Pending/" + label + ".pipeline.json",
                size_text: "1.0 GB",
                age_text: "fresh",
                output_size: 1073741824,
                diagnostic_status: blocked ? "unreadable_manifest" : "ready",
                diagnostic_severity: blocked ? "error" : "ok",
                drain_recommendation: blocked ? "do_not_drain" : "ready_to_drain",
                ready_to_drain: !blocked,
                local_exists: !blocked,
                missing_sidecar_count: blocked ? 2 : 0,
                operator_trust_state: blocked ? "do-not-drain" : "ready",
                operator_guidance: blocked ? "Do not drain; inspect manifest and logs first." : "Ready after drain guard agrees.",
                recovery_class: blocked ? "manifest_repair" : "ready",
                recovery_action: blocked ? "Repair manifest before drain." : "",
                issue_summary: blocked ? "Unreadable manifest and missing payload." : "",
                recommended_open_targets: ["manifest", "pending_root"],
                available_open_targets: ["manifest", "pending_root"],
                recommended_diagnostics_targets: ["pending_publish", "last_stderr"],
                proof_summary: ["large payload pending row", "render cap smoke"],
              };
            });
            window.renderPendingPublish({
              ok: true,
              count: 260,
              rows: pendingRows,
              exists: true,
              pending_root: "C:/Pending",
              inventory_progress: {
                schema_version: "desktop_pending_publish_inventory_progress.v1",
                status: "complete",
                rows_scanned: 260,
                rows_loaded: 260,
                source: "C:/Pending",
                detail: "Pending publish inventory scanned 260 row(s) and loaded 260 row(s).",
                updated_at: "2026-05-17T12:00:00",
                progress_bars: [{
                  id: "pending_inventory",
                  label: "Pending inventory",
                  mode: "determinate",
                  percent: 100,
                  status: "complete",
                  detail: "Pending publish inventory scanned 260 row(s) and loaded 260 row(s).",
                  source: "C:/Pending",
                  updated_at: "2026-05-17T12:00:00",
                  stale: false,
                }],
              },
            }, {});
            requireText("pending-status", ["250 shown / 260 filtered / 260 rows"]);
            requireText("pending-inventory-progress-bars", ["Pending inventory", "100%", "Pending publish inventory scanned 260 row(s)"]);
            requireText("pending-filter-summary", ["Display cap: only the first 250 filtered rows are rendered", "filtering Pending Publish rows does not change drain scope"]);
            requireText("pending-table-legend", ["Pending publish rows: 250 selectable rows"]);
            requireRenderedRows("#pending-rows tr[data-row-key]", 250);
            requireSharedTableFilter("pending-rows", "#pending-rows tr[data-row-key]", "Large Pending 240", 1);
            if (!pressShortcut("4")) throw new Error("Pending Publish shortcut should be handled before scroll preservation check");
            requireActivePage("pending");
            requirePendingScrollPreservedOnSelection("Large Pending 240");
            requireText("pending-detail", ["Large Pending 240", "Mutation guardrail"]);
            setValue("pending-filter", "Large Pending 001");
            window.mediaPipelinePendingPublishView.renderPendingRows();
            requireText("pending-status", ["1 / 260 rows"]);
            requireText("pending-filter-summary", ["Hidden review rows: 1", "blocked/warning rows are currently hidden"]);
            requireText("pending-backend-scope-summary", [
              "Backend drain scope preview:",
              "visible after filters: 1/260",
              "hidden blocked/review rows: 1/1",
              "Pending filters, selected row keys, and rendered table caps are not submitted as publish scope.",
            ]);
            requireText("pending-backend-scope-rows", [
              "Display filter vs drain scope",
              "Selecting a row cannot make Drain Parked Outputs drain only that row.",
            ]);
            requireText("pending-drain-decision-summary", [
              "Daily-use handoff: Pending Publish evidence decides whether it is sensible to press Drain Parked Outputs",
              "Operator outcome:",
              "Scope boundary: Pending filters, selected rows, recovery dry-runs",
              "Blocked/review/read-first/unknown",
            ]);
            window.selectPendingRow(pendingRows[259]);
            requireText("pending-selected-summary", ["Selected Pending Publish row: C:/Scratch/Pending/Large Pending 260.mkv", "at-a-glance=Do not drain", "Filter visibility: Selected row visible in table: no", "Authority: this summary is read-only"]);
            requireText("pending-detail", ["Large Pending 260", "Selected row visible in table: no", "Hidden by current filters: text filter=\\"Large Pending 001\\"", "Mutation guardrail"]);
            if (!pressShortcut("4")) throw new Error("Pending Publish shortcut should be handled");
            requireActivePage("pending");
            if (!pressShortcut("/")) throw new Error("Publish search shortcut should be handled");
            requireActiveElement("pending-filter");
            document.activeElement.blur();
            setValue("pending-filter", "Large Pending 001");
            if (!pressShortcut("j")) throw new Error("Publish next-row shortcut should be handled");
            requireText("pending-detail", ["Large Pending 001", "Mutation guardrail"]);
            if (!pressShortcut("d")) throw new Error("Publish detail shortcut should be handled");
            requireActiveElement("pending-detail");
            if (!pressShortcut("c")) throw new Error("Publish clear-filter shortcut should be handled");
            requireText("pending-status", ["250 shown / 260 filtered / 260 rows"]);

            const forbidden = ["/api/pipeline/start", "/api/rerun/start", "/api/completed/open", "/api/queue/open", "/api/pending-publish/open", "/api/pending-publish/recovery-plan", "/api/rename/apply", "/api/settings/save-patch"];
            const forbiddenPosts = posts.filter((path) => forbidden.some((blocked) => path.includes(blocked)));
            if (forbiddenPosts.length) throw new Error("large-table smoke posted mutation routes: " + JSON.stringify(forbiddenPosts));
            return {
              ok: true,
              queueStatus: text("queue-status"),
              completedStatus: text("completed-status"),
              pendingStatus: text("pending-status"),
              posts,
              priorityPosts,
              priorityConfirmMessages,
            };
          })()
          `;
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
            const deadline = Date.now() + 20000;
            while (Date.now() < deadline) {
              const ready = await client.send("Runtime.evaluate", {
                expression: `Boolean(document.readyState === "complete" && document.getElementById("queue-rows") && document.getElementById("completed-rows") && document.getElementById("pending-rows") && typeof window.renderProgressBarsInto === "function" && typeof window.refreshAllNow === "function" && typeof window.renderQueue === "function" && typeof window.renderCompleted === "function" && typeof window.renderPendingPublish === "function")`,
                returnByValue: true,
              });
              if (ready.result?.value === true) break;
              await sleep(150);
            }
            const ready = await client.send("Runtime.evaluate", {
              expression: `Boolean(document.readyState === "complete" && document.getElementById("queue-rows") && document.getElementById("completed-rows") && document.getElementById("pending-rows") && typeof window.renderProgressBarsInto === "function" && typeof window.refreshAllNow === "function" && typeof window.renderQueue === "function" && typeof window.renderCompleted === "function" && typeof window.renderPendingPublish === "function")`,
              returnByValue: true,
            });
            if (ready.result?.value !== true) {
              throw new Error("WebView daily table globals or DOM nodes did not become ready.");
            }
            const result = await client.send("Runtime.evaluate", {
              expression: largeTableScript(),
              awaitPromise: true,
              returnByValue: true,
            });
            if (result.exceptionDetails) {
              const detail = result.exceptionDetails.exception?.description
                || result.exceptionDetails.exception?.value
                || result.exceptionDetails.text
                || "browser evaluation failed";
              throw new Error(detail);
            }
            await sleep(750);
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


def _run_browser_large_table_smoke(*, browser_path: str, url: str) -> dict[str, object]:
    node = shutil.which("node")
    if not node:
        raise unittest.SkipTest("Node.js is required for the browser-backed WebView large-table smoke.")
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as raw_tmp:
        tmp = Path(raw_tmp)
        port = _free_port()
        payload_path = tmp / "browser-large-table-payload.json"
        runner_path = tmp / "browser-large-table-runner.cjs"
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
        runner_path.write_text(_browser_large_table_runner_source(), encoding="utf-8")
        return run_node_browser_smoke(
            "Browser-backed WebView large daily-table smoke",
            node=node,
            runner_path=runner_path,
            payload_path=payload_path,
            timeout_seconds=45,
        )


class WebViewBrowserLargeTableSmoke(unittest.TestCase):
    def test_real_browser_discloses_large_daily_table_caps_without_mutation_posts(self) -> None:
        browser_path = _find_browser()
        if not browser_path:
            raise unittest.SkipTest("Chrome or Edge is required for the browser-backed WebView large-table smoke.")

        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            resolved, _source, _output = _write_fixture_state(root)
            media_snapshot = capture_media_no_mutation_snapshot(root)
            service = DummyWorkflowFacadeService(root)
            facade = MediaPipelineApplicationFacade(service, app_version="v5-test")
            server = LocalApiServer(
                facade,
                token="browser-large-table-smoke-token",
                resolved_provider=lambda: resolved,
                audit_root_provider=lambda: str(root),
            )
            try:
                server.start()
                result = _run_browser_large_table_smoke(
                    browser_path=browser_path,
                    url=f"{server.url}/",
                )
            finally:
                server.stop()
            assert_media_no_mutation(self, media_snapshot)

        self.assertTrue(result["ok"])
        browser_result = result["result"]
        self.assertEqual(browser_result["queueStatus"], "250 shown / 260 filtered / 260 rows")
        self.assertEqual(browser_result["completedStatus"], "1 missing from expected destination / 250 shown / 259 filtered / 259 rows")
        self.assertEqual(browser_result["pendingStatus"], "250 shown / 260 filtered / 260 rows")
        command_posts = [path for path in browser_result["posts"] if path != "/api/ui-preferences"]
        self.assertEqual(command_posts, ["/api/queue/priority", "/api/queue/priority"])
        self.assertEqual(len(browser_result["priorityPosts"]), 2)
        self.assertEqual(len(browser_result["priorityPosts"][0]["body"]["items"]), 87)
        self.assertEqual(len(browser_result["priorityPosts"][1]["body"]["items"]), 87)
        self.assertIn("Backend Launch scope remains unchanged", "\n".join(browser_result["priorityConfirmMessages"]))


if __name__ == "__main__":
    unittest.main()




