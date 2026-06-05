// queueView.review.js
// Split child of queueView.js. Loaded before queueView.js; the parent
// consumes this temporary stash global and deletes it immediately.

(function () {
  "use strict";

  function createQueueReviewModule({
    appendCells,
    byId,
    clearRows,
    getSelectedQueueRowKey,
    makeRowSelectable,
    queueFilterFields,
    queueFormatCounts,
    queueHiddenSidecarLine,
    queueRowKey,
    queueSnapshotIsStale,
    queueWorkflowStatus,
    selectQueueRow,
    setText,
    updateTableStatusLegend,
  }) {
    appendCells = typeof appendCells === "function" ? appendCells : function () {};
    byId = typeof byId === "function" ? byId : function (id) { return document.getElementById(id); };
    clearRows = typeof clearRows === "function" ? clearRows : function () { return null; };
    getSelectedQueueRowKey = typeof getSelectedQueueRowKey === "function" ? getSelectedQueueRowKey : function () { return ""; };
    makeRowSelectable = typeof makeRowSelectable === "function" ? makeRowSelectable : function () {};
    queueFormatCounts = typeof queueFormatCounts === "function" ? queueFormatCounts : function () { return "none"; };
    queueHiddenSidecarLine = typeof queueHiddenSidecarLine === "function" ? queueHiddenSidecarLine : function () { return ""; };
    queueRowKey = typeof queueRowKey === "function" ? queueRowKey : function () { return ""; };
    queueSnapshotIsStale = typeof queueSnapshotIsStale === "function" ? queueSnapshotIsStale : function () { return false; };
    queueWorkflowStatus = typeof queueWorkflowStatus === "function" ? queueWorkflowStatus : function () { return "unknown"; };
    selectQueueRow = typeof selectQueueRow === "function" ? selectQueueRow : function () {};
    setText = typeof setText === "function" ? setText : function () {};
    updateTableStatusLegend = typeof updateTableStatusLegend === "function" ? updateTableStatusLegend : function () {};
    const QUEUE_FILTER_FIELDS = Array.isArray(queueFilterFields) ? queueFilterFields : [];

    function queueReviewRowReasons(row) {
      const reasons = [];
      const severity = String(row?.operator_severity || "").toLowerCase();
      const status = String(row?.status || "").toLowerCase();
      const runtimeStatus = String(row?.runtime_outcome_status || "").toLowerCase();
      const runtimeFreshness = String(row?.runtime_outcome_freshness_status || "").toLowerCase();
      const reviewFlags = Array.isArray(row?.review_flags) ? row.review_flags.filter(Boolean) : [];
      if (severity === "error") reasons.push("backend error severity");
      if (severity === "warning") reasons.push("backend warning severity");
      if (status === "invalid") reasons.push("invalid queue row");
      if (row?.blocked_reason || row?.blocked_reason_code) reasons.push(`blocked: ${row.blocked_reason_code || row.blocked_reason}`);
      if (row?.runtime_checks_deferred) reasons.push("runtime checks deferred");
      if (runtimeFreshness === "fresh" && ["failed", "error", "skipped", "stopped"].some((value) => runtimeStatus.includes(value))) {
        reasons.push(`fresh runtime outcome: ${row.runtime_outcome_status}`);
      }
      if (reviewFlags.length) reasons.push(`review flags: ${reviewFlags.join(", ")}`);
      if (String(row?.operator_trust_state || "").toLowerCase().includes("review")) reasons.push(`trust state: ${row.operator_trust_state}`);
      if (row?.primary_concern) reasons.push(`primary concern: ${row.primary_concern}`);
      return reasons.filter(Boolean);
    }


    function queueReviewRows(queue, rows) {
      const rowList = Array.isArray(rows) ? rows : [];
      return rowList
        .map((row, index) => ({ row, index, reasons: queueReviewRowReasons(row) }))
        .filter((entry) => entry.reasons.length)
        .sort((a, b) => {
          const severityRank = (entry) => String(entry.row?.operator_severity || "").toLowerCase() === "error" ? 0
            : String(entry.row?.operator_severity || "").toLowerCase() === "warning" ? 1
              : entry.row?.blocked_reason || entry.row?.blocked_reason_code ? 2
                : 3;
          return severityRank(a) - severityRank(b) || a.index - b.index;
        });
    }


    function queueReviewStatus(queue, rows) {
      const payload = queue || {};
      const rowList = Array.isArray(rows) ? rows : [];
      if (payload.error) return "Diagnostics first";
      if (queueSnapshotIsStale(payload)) return "Refresh queue";
      const reviewRows = queueReviewRows(payload, rowList);
      if (reviewRows.length) return `${reviewRows.length} row${reviewRows.length === 1 ? "" : "s"} need review`;
      if (!rowList.length) return "No runnable rows";
      return "No flagged rows";
    }


    function queueReviewBoardLines(queue, rows) {
      const payload = queue || {};
      const rowList = Array.isArray(rows) ? rows : [];
      const reviewRows = queueReviewRows(payload, rowList);
      const lines = [
        "Operator review board: Queue",
        `Page status: ${queueWorkflowStatus(payload, rowList)}`,
        `Rows loaded: ${rowList.length}`,
        queueHiddenSidecarLine(payload),
        `Flagged rows: ${reviewRows.length}`,
        `Backend trust states: ${queueFormatCounts(payload.operator_trust_state_counts)}`,
        `Operator severities: ${queueFormatCounts(payload.operator_severity_counts)}`,
        `Runtime freshness: ${queueFormatCounts(payload.runtime_outcome_freshness_counts)}`,
      ];
      lines.push("");
      if (payload.error) {
        lines.push("First action: open Diagnostics > Queue Snapshot, Run Logs, and Last Stderr. Do not launch from an unavailable queue view.");
      } else if (queueSnapshotIsStale(payload)) {
        lines.push("First action: refresh Queue from Launch before acting; stale queue rows can hide completed outputs or half-copied sources.");
      } else if (reviewRows.length) {
        lines.push("First rows to inspect:");
        reviewRows.slice(0, 6).forEach(({ row, reasons }, index) => {
          const label = row.display_name || row.relative_path || row.source_path || `row ${index + 1}`;
          const action = row.safe_next_action || row.operator_guidance || "select the row and use Queue Diagnostics Cross-Links before launch.";
          lines.push(`- ${label}: ${reasons.slice(0, 3).join("; ")}. Safe action: ${action}`);
        });
        if (reviewRows.length > 6) lines.push(`- ${reviewRows.length - 6} more flagged row(s) not shown.`);
      } else if (!rowList.length) {
        lines.push("First action: check Source settings, Completed exclusions, schedule state, and Run Logs before assuming files were missed.");
      } else {
        lines.push("First action: no rows are locally flagged. Select any high-priority row and verify route evidence before Launch.");
      }
      lines.push("Mutation guardrail: this board is read-only; launch, queue mutation, rerun, and file actions remain backend-owned.");
      return lines;
    }


    function queueReviewDigestStatus(entry) {
      const row = entry?.row || {};
      const severity = String(row.operator_severity || "").toLowerCase();
      if (severity === "error" || row.blocked_reason || row.blocked_reason_code || row.error) return "blocked";
      if (severity === "warning" || row.is_priority || entry?.reasons?.length) return "warning";
      return "ready";
    }


    function queueReviewDigestAction(row) {
      return row?.safe_next_action
        || row?.operator_guidance
        || "Select this row, read Queue detail and Diagnostics Cross-Links, then use Launch only after page-level readiness agrees.";
    }


    function queueTableRowStatus(item) {
      const backendState = typeof backendRowStatusState === "function" ? backendRowStatusState(item) : "";
      if (backendState) return backendState;
      const severity = String(item?.operator_severity || "").toLowerCase();
      if (severity === "error" || item?.blocked_reason || item?.blocked_reason_code || item?.error) return "blocked";
      if (severity === "warning" || item?.is_priority || queueReviewRowReasons(item).length) return "warning";
      return "ready";
    }


    function queueInvestigationFilterLabel(value) {
      const normalized = String(value || "all").trim().toLowerCase();
      const labels = {
        all: "all signals",
        launch_blockers: "launch blockers",
        runtime_failed: "runtime failed",
        deferred_checks: "deferred checks",
        priority: "priority rows",
        encode: "encode routes",
        remux: "remux routes",
        tv_parse: "TV parse review",
      };
      return labels[normalized] || normalized.replace(/_/g, " ");
    }


    function queueMatchesInvestigationFilter(item, filter) {
      const normalized = String(filter || "all").trim().toLowerCase();
      const route = String(item?.route_name || item?.route || item?.route_label || "").toLowerCase();
      const runtime = String(item?.runtime_outcome_status || "").toLowerCase();
      const runtimeError = String(item?.runtime_outcome_error_code || item?.runtime_outcome_reason || "").toLowerCase();
      const blocker = String(item?.blocked_reason_code || item?.blocked_reason || item?.error || "").toLowerCase();
      const reviewFlags = Array.isArray(item?.review_flags) ? item.review_flags.join(" ").toLowerCase() : "";
      if (!normalized || normalized === "all") return true;
      if (normalized === "launch_blockers") return queueTableRowStatus(item) === "blocked";
      if (normalized === "runtime_failed") return ["failed", "error", "skipped", "stopped"].some((value) => runtime.includes(value) || runtimeError.includes(value));
      if (normalized === "deferred_checks") return Boolean(item?.runtime_checks_deferred || Number(item?.runtime_check_deferred_count || 0) > 0);
      if (normalized === "priority") return Boolean(item?.is_priority);
      if (normalized === "encode") return route.includes("encode");
      if (normalized === "remux") return route.includes("remux");
      if (normalized === "tv_parse") return blocker.includes("tv_parse") || reviewFlags.includes("tv_parse") || blocker.includes("season") || blocker.includes("episode");
      return true;
    }


    function queueFocusedInvestigationLabels(item) {
      const filters = ["launch_blockers", "runtime_failed", "deferred_checks", "priority", "encode", "remux", "tv_parse"];
      return filters.filter((filter) => queueMatchesInvestigationFilter(item, filter)).map(queueInvestigationFilterLabel);
    }


    function queueFilterVisibilityLines(item) {
      if (!item) return [];
      const filterText = byId("queue-filter")?.value || "";
      const statusFilter = byId("queue-status-filter")?.value || "all";
      const investigationFilter = byId("queue-investigation-filter")?.value || "all";
      const textMatches = typeof filterRows === "function" ? filterRows([item], filterText, QUEUE_FILTER_FIELDS).length > 0 : true;
      const status = queueTableRowStatus(item);
      const statusMatches = typeof tableStatusMatchesFilter === "function" ? tableStatusMatchesFilter(status, statusFilter) : true;
      const normalizedInvestigation = String(investigationFilter || "all").trim().toLowerCase();
      const investigationMatches = !normalizedInvestigation || normalizedInvestigation === "all" || queueMatchesInvestigationFilter(item, normalizedInvestigation);
      const activeFilters = Boolean(String(filterText || "").trim()) || String(statusFilter || "all").toLowerCase() !== "all" || normalizedInvestigation !== "all";
      const reasons = [];
      if (!textMatches) reasons.push(`text filter="${String(filterText || "").trim()}"`);
      if (!statusMatches) reasons.push(`status filter=${typeof tableStatusFilterLabel === "function" ? tableStatusFilterLabel(statusFilter) : statusFilter}`);
      if (!investigationMatches) reasons.push(`investigation view=${queueInvestigationFilterLabel(investigationFilter)}`);
      const lines = [
        "Current filter visibility:",
        `Selected row visible in table: ${textMatches && statusMatches && investigationMatches ? "yes" : "no"}`,
        `Active filters: ${activeFilters ? `text=${String(filterText || "").trim() || "none"}; status=${typeof tableStatusFilterLabel === "function" ? tableStatusFilterLabel(statusFilter) : statusFilter}; view=${queueInvestigationFilterLabel(investigationFilter)}` : "none"}`,
      ];
      if (reasons.length) {
        lines.push(`Hidden by current filters: ${reasons.join("; ")}.`);
        lines.push("Operator note: selected-row detail remains visible for review, but the table is currently hiding this row.");
      } else if (activeFilters) {
        lines.push("Operator note: this selected row is still visible under the active display filters.");
      } else {
        lines.push("Operator note: no Queue display filter is hiding this selected row.");
      }
      return lines;
    }


    function queueSelectedQuickSignalLines(item) {
      if (!item) {
        return [
          "Selected row quick signal:",
          "Select a queue row to see status, focused investigation views, and current-filter visibility.",
        ];
      }
      const focusedViews = queueFocusedInvestigationLabels(item);
      const primaryConcern = item.primary_concern
        || [item.blocked_reason_code, item.blocked_reason, item.error].filter(Boolean).join(" - ")
        || item.operator_guidance
        || item.route_decision_summary
        || "no focused blocker reported";
      return [
        "Selected row quick signal:",
        `Table status: ${queueTableRowStatus(item)}`,
        `Focused views: ${focusedViews.length ? focusedViews.join(", ") : "none beyond all signals"}`,
        `Primary concern: ${primaryConcern}`,
        ...queueFilterVisibilityLines(item),
      ];
    }


    function queueSelectedAtAGlanceState(item) {
      if (!item) return "unknown";
      const backendState = typeof backendRowStatusState === "function" ? backendRowStatusState(item) : "";
      if (["blocked", "failed"].includes(backendState)) return "blocked";
      if (["warning", "running", "completed", "skipped", "parked", "publishing", "health-check"].includes(backendState)) return "warning";
      if (["ready", "match"].includes(backendState)) return "ready";
      const runtimeStatus = String(item.runtime_outcome_status || "").toLowerCase();
      const runtimeFreshness = String(item.runtime_outcome_freshness_status || "").toLowerCase();
      const reviewFlags = Array.isArray(item.review_flags) ? item.review_flags.filter(Boolean) : [];
      const blocked = Boolean(item.blocked_reason || item.blocked_reason_code || String(item.status || "").toLowerCase().includes("blocked") || item.error);
      const recentRuntimeIssue = runtimeFreshness === "fresh" && ["failed", "error", "skipped"].some((value) => runtimeStatus.includes(value));
      if (blocked) return "blocked";
      if (recentRuntimeIssue || reviewFlags.length || String(item.operator_severity || "").toLowerCase() === "warning") return "warning";
      if (item.runtime_checks_deferred) return "changed";
      return "ready";
    }


    function queueSelectedAtAGlanceStatus(item) {
      const state = queueSelectedAtAGlanceState(item);
      if (state === "blocked") return "Blocked";
      if (state === "warning") return "Review";
      if (state === "changed") return "Launch-check needed";
      if (state === "ready") return "Ready-looking";
      return "No selection";
    }


    function queueSelectedVisibilitySummary(item) {
      const lines = queueFilterVisibilityLines(item);
      return lines
        .filter((line) => /^Selected row visible|^Active filters|^Hidden by current filters/.test(String(line || "")))
        .join(" ");
    }


    function queueSelectedAtAGlanceLines(item) {
      const sharedSummary = window.mediaPipelineDom?.selectedRowAtAGlanceLines;
      const authority = "Authority: this summary is read-only. It cannot launch, reorder, drop, rewrite queue entries, or touch source files.";
      if (!item) {
        return typeof sharedSummary === "function"
          ? sharedSummary({
            title: "Selected Queue row",
            item: null,
            emptyNextStep: "Next step: select a queue row to review route, source, diagnostics, and Launch readiness evidence.",
            authority: "Authority: this summary is read-only. Backend Launch remains the only path that can start processing.",
          })
          : [
            "Selected Queue row: none",
            "Next step: select a queue row to review route, source, diagnostics, and Launch readiness evidence.",
            "Authority: this summary is read-only. Backend Launch remains the only path that can start processing.",
          ];
      }
      const concern = item.primary_concern
        || [item.blocked_reason_code, item.blocked_reason, item.error].filter(Boolean).join(" - ")
        || item.operator_guidance
        || "no primary concern reported";
      const safeAction = item.safe_next_action
        || item.operator_guidance
        || (queueSelectedAtAGlanceState(item) === "ready"
          ? "Use Launch only after page-level readiness, schedule, and backend preflight agree."
          : "Read Queue Snapshot, Last Stderr, Run Logs, and owning-page evidence before starting.");
      if (typeof sharedSummary === "function") {
        return sharedSummary({
          title: "Selected Queue row",
          item,
          label: item.display_name || item.relative_path || item.source_path || "(unnamed row)",
          trustStatus: item.operator_trust_state || item.operator_status || queueTableRowStatus(item),
          atAGlanceStatus: queueSelectedAtAGlanceStatus(item),
          proofLabel: "Route/source proof",
          proof: `${item.route_decision_summary || item.route_name || "route not reported"}; source=${item.source_path || "not reported"}`,
          primaryConcern: concern,
          safeNextStep: safeAction,
          filterVisibility: queueSelectedVisibilitySummary(item) || "not evaluated",
          authority,
        });
      }
      return [
        `Selected Queue row: ${item.display_name || item.relative_path || item.source_path || "(unnamed row)"}`,
        `Trust/status: ${item.operator_trust_state || item.operator_status || queueTableRowStatus(item)}; at-a-glance=${queueSelectedAtAGlanceStatus(item)}`,
        `Route/source proof: ${item.route_decision_summary || item.route_name || "route not reported"}; source=${item.source_path || "not reported"}`,
        `Primary concern: ${concern}`,
        `Safe next step: ${safeAction}`,
        `Filter visibility: ${queueSelectedVisibilitySummary(item) || "not evaluated"}`,
        authority,
      ];
    }


    function renderQueueSelectedAtAGlance(item) {
      const status = queueSelectedAtAGlanceStatus(item);
      setText("queue-selected-status", status);
      const statusNode = byId("queue-selected-status");
      if (statusNode) statusNode.dataset.state = queueSelectedAtAGlanceState(item);
      setText("queue-selected-summary", queueSelectedAtAGlanceLines(item).join("\n"));
    }


    function queueInvestigationSignalLines(item) {
      if (!item) {
        return [
          "Investigation view matches:",
          "- Select a queue row to see which Queue investigation views would include it.",
        ];
      }
      const route = String(item.route_name || item.route || item.route_label || "").trim();
      const runtimeProof = [item.runtime_outcome_status, item.runtime_outcome_error_code, item.runtime_outcome_reason]
        .filter(Boolean)
        .join(" - ");
      const blockerProof = [item.blocked_reason_code, item.blocked_reason, item.error].filter(Boolean).join(" - ");
      const reviewFlags = Array.isArray(item.review_flags) ? item.review_flags.filter(Boolean) : [];
      const signals = [];
      if (queueMatchesInvestigationFilter(item, "launch_blockers")) {
        signals.push(`- launch blockers: ${blockerProof || item.operator_status || queueTableRowStatus(item)}`);
      }
      if (queueMatchesInvestigationFilter(item, "runtime_failed")) {
        signals.push(`- runtime failed: ${runtimeProof || "runtime status/error indicates failure"}`);
      }
      if (queueMatchesInvestigationFilter(item, "deferred_checks")) {
        signals.push("- deferred checks: source stability or output-path checks are deferred until backend launch.");
      }
      if (queueMatchesInvestigationFilter(item, "priority")) {
        const priorityReasons = Array.isArray(item.priority_reasons) ? item.priority_reasons.filter(Boolean).join("; ") : "";
        signals.push(`- priority rows: ${priorityReasons || "row is marked priority"}`);
      }
      if (queueMatchesInvestigationFilter(item, "encode")) {
        signals.push(`- encode routes: ${route || item.route_decision_summary || "route includes encode"}`);
      }
      if (queueMatchesInvestigationFilter(item, "remux")) {
        signals.push(`- remux routes: ${route || item.route_decision_summary || "route includes remux"}`);
      }
      if (queueMatchesInvestigationFilter(item, "tv_parse")) {
        signals.push(`- TV parse review: ${blockerProof || reviewFlags.join(", ") || "season/episode evidence requires review"}`);
      }
      if (!signals.length) {
        signals.push("- none beyond all signals: this row is not currently included by a focused Queue investigation view.");
      }
      signals.push("Operator note: investigation views are display filters only and do not alter backend launch scope.");
      return ["Investigation view matches:", ...signals];
    }


    function renderQueueReviewDigest(queue, rows) {
      const tbody = byId("queue-review-rows");
      if (!tbody) return;
      const payload = queue || {};
      const rowList = Array.isArray(rows) ? rows : [];
      const reviewRows = queueReviewRows(payload, rowList).slice(0, 12);
      if (!reviewRows.length) {
        clearRows(
          tbody,
          5,
          payload.error
            ? "Queue preview is unavailable. Use Diagnostics > Queue Snapshot, Run Logs, and Last Stderr before launch."
            : rowList.length
              ? "No queue rows are flagged by the loaded backend payload. Select rows in the main table to inspect route evidence before Launch."
              : "No queue rows loaded. Check Source settings, Completed exclusions, and Diagnostics before assuming files were missed.",
        );
        updateTableStatusLegend("queue-review-legend", tbody, "Queue review rows");
        return;
      }
      tbody.replaceChildren();
      reviewRows.forEach((entry) => {
        const item = entry.row || {};
        const row = document.createElement("tr");
        const key = queueRowKey(item);
        row.dataset.rowKey = key;
        row.dataset.status = queueReviewDigestStatus(entry);
        appendCells(row, [
          item.global_order || item.queue_index || entry.index + 1,
          item.operator_trust_state || item.operator_status || item.status || row.dataset.status,
          item.display_name || item.relative_path || item.source_path || "",
          entry.reasons.slice(0, 3).join("; "),
          queueReviewDigestAction(item),
        ]);
        makeRowSelectable(row, () => selectQueueRow(item), {
          selected: Boolean(key && key === getSelectedQueueRowKey()),
          label: `Queue review row ${item.display_name || item.relative_path || item.source_path || ""}`,
        });
        tbody.appendChild(row);
      });
      updateTableStatusLegend("queue-review-legend", tbody, "Queue review rows");
    }


    function renderQueueReviewBoard(queue, rows) {
      const rowList = Array.isArray(rows) ? rows : [];
      setText("queue-review-status", queueReviewStatus(queue || {}, rowList));
      setText("queue-review-board", queueReviewBoardLines(queue || {}, rowList).join("\n"));
      renderQueueReviewDigest(queue || {}, rowList);
    }


    function queueListText(value) {
      return Array.isArray(value) && value.length ? value.join(", ") : "none";
    }

    return {
      queueReviewRowReasons,
      queueReviewRows,
      queueReviewStatus,
      queueReviewBoardLines,
      queueReviewDigestStatus,
      queueReviewDigestAction,
      queueTableRowStatus,
      queueInvestigationFilterLabel,
      queueMatchesInvestigationFilter,
      queueFocusedInvestigationLabels,
      queueFilterVisibilityLines,
      queueSelectedQuickSignalLines,
      queueSelectedAtAGlanceState,
      queueSelectedAtAGlanceStatus,
      queueSelectedVisibilitySummary,
      queueSelectedAtAGlanceLines,
      renderQueueSelectedAtAGlance,
      queueInvestigationSignalLines,
      renderQueueReviewDigest,
      renderQueueReviewBoard,
      queueListText,
    };
  }

  window.__queueReviewModule = { createQueueReviewModule };
})();
