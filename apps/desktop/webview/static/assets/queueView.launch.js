// queueView.launch.js
// Split child of queueView.js. Loaded before queueView.js; the parent
// consumes this temporary stash global and deletes it immediately.

(function () {
  "use strict";

  function createQueueLaunchModule({
    appendCells,
    byId,
    clearRows,
    getCommandHistory,
    getLastQueuePayload,
    getLastQueueRows,
    getSelectedQueueRow,
    makeRowSelectable,
    queueCounts,
    queueCollisionLines,
    queueFilterFields,
    queueFormatCounts,
    queueFreshnessLine,
    queueHiddenSidecarLine,
    queueInvestigationFilterLabel,
    queueMatchesInvestigationFilter,
    queueReadinessLines,
    queueReviewBoardLines,
    queueReviewRowReasons,
    queueReviewRows,
    queueRowIssueDigestLines,
    commandHistoryIssueLevel,
    queueRowKey,
    queueRuntimeLines,
    queueSnapshotIsStale,
    queueTableRowStatus,
    renderQueueDetail,
    renderQueueReviewDigest,
    renderQueueRows,
    selectQueueRow,
    setText,
    updateTableStatusLegend,
  }) {
    appendCells = typeof appendCells === "function" ? appendCells : function () {};
    byId = typeof byId === "function" ? byId : function (id) { return document.getElementById(id); };
    clearRows = typeof clearRows === "function" ? clearRows : function () { return null; };
    getCommandHistory = typeof getCommandHistory === "function" ? getCommandHistory : function () { return []; };
    commandHistoryIssueLevel = typeof commandHistoryIssueLevel === "function" ? commandHistoryIssueLevel : null;
    getLastQueuePayload = typeof getLastQueuePayload === "function" ? getLastQueuePayload : function () { return {}; };
    getLastQueueRows = typeof getLastQueueRows === "function" ? getLastQueueRows : function () { return []; };
    getSelectedQueueRow = typeof getSelectedQueueRow === "function" ? getSelectedQueueRow : function () { return null; };
    makeRowSelectable = typeof makeRowSelectable === "function" ? makeRowSelectable : function () {};
    queueCounts = typeof queueCounts === "function" ? queueCounts : function () { return {}; };
    queueCollisionLines = typeof queueCollisionLines === "function" ? queueCollisionLines : function () { return []; };
    queueFormatCounts = typeof queueFormatCounts === "function" ? queueFormatCounts : function () { return "none"; };
    queueFreshnessLine = typeof queueFreshnessLine === "function" ? queueFreshnessLine : function () { return ""; };
    queueHiddenSidecarLine = typeof queueHiddenSidecarLine === "function" ? queueHiddenSidecarLine : function () { return ""; };
    queueInvestigationFilterLabel = typeof queueInvestigationFilterLabel === "function" ? queueInvestigationFilterLabel : function (value) { return String(value || ""); };
    queueMatchesInvestigationFilter = typeof queueMatchesInvestigationFilter === "function" ? queueMatchesInvestigationFilter : function () { return true; };
    queueReadinessLines = typeof queueReadinessLines === "function" ? queueReadinessLines : function () { return []; };
    queueReviewBoardLines = typeof queueReviewBoardLines === "function" ? queueReviewBoardLines : function () { return []; };
    queueReviewRowReasons = typeof queueReviewRowReasons === "function" ? queueReviewRowReasons : function () { return []; };
    queueReviewRows = typeof queueReviewRows === "function" ? queueReviewRows : function () { return []; };
    queueRowIssueDigestLines = typeof queueRowIssueDigestLines === "function" ? queueRowIssueDigestLines : function () { return []; };
    queueRowKey = typeof queueRowKey === "function" ? queueRowKey : function () { return ""; };
    queueRuntimeLines = typeof queueRuntimeLines === "function" ? queueRuntimeLines : function () { return []; };
    queueSnapshotIsStale = typeof queueSnapshotIsStale === "function" ? queueSnapshotIsStale : function () { return false; };
    queueTableRowStatus = typeof queueTableRowStatus === "function" ? queueTableRowStatus : function () { return ""; };
    renderQueueDetail = typeof renderQueueDetail === "function" ? renderQueueDetail : function () {};
    renderQueueReviewDigest = typeof renderQueueReviewDigest === "function" ? renderQueueReviewDigest : function () {};
    renderQueueRows = typeof renderQueueRows === "function" ? renderQueueRows : function () {};
    selectQueueRow = typeof selectQueueRow === "function" ? selectQueueRow : function () {};
    setText = typeof setText === "function" ? setText : function () {};
    updateTableStatusLegend = typeof updateTableStatusLegend === "function" ? updateTableStatusLegend : function () {};
    const QUEUE_FILTER_FIELDS = Array.isArray(queueFilterFields) ? queueFilterFields : [];
    let selectedQueueLaunchDecisionKey = "";

    function launchViewApi() {
      return window.mediaPipelineLaunchView || {};
    }

    function queueLaunchDecisionPostureStatus(posture) {
      const normalized = String(posture || "").toLowerCase();
      if (normalized.includes("block") || normalized.includes("do not")) return "blocked";
      if (normalized.includes("review") || normalized.includes("warning")) return "warning";
      if (normalized.includes("read") || normalized.includes("refresh")) return "changed";
      if (normalized.includes("unknown") || normalized.includes("incomplete")) return "unknown";
      if (normalized.includes("ready")) return "ready";
      return "normal";
    }


    function isQueueLaunchCommand(entry) {
      const command = String(entry?.command || entry?.raw?.command || "").toLowerCase();
      return command === "pipeline.start" || command === "rerun.start" || command === "audit.start";
    }


    function queueLaunchDecisionLatestCommand(entries) {
      const source = Array.isArray(entries) ? entries : [];
      return source.find(isQueueLaunchCommand) || null;
    }


    function queueLaunchCommandIssueLevel(entry) {
      if (!entry) return "none";
      if (typeof commandHistoryIssueLevel === "function") return commandHistoryIssueLevel(entry);
      if (entry.ok === false) return "error";
      return String(entry.severity || entry.result || "").toLowerCase() || "info";
    }


    function queueLaunchDecisionAdd(rowsOut, key, checkpoint, posture, evidence, action, detail = [], row = null) {
      rowsOut.push({
        key,
        checkpoint,
        posture,
        evidence,
        action,
        detail: Array.isArray(detail) ? detail.filter(Boolean) : [],
        row,
      });
    }


    function queueLaunchBackendPreflightPayload() {
      const launchView = launchViewApi();
      if (typeof launchView.launchBackendPreflightPayloadForTarget === "function") {
        return launchView.launchBackendPreflightPayloadForTarget("pipeline");
      }
      if (typeof launchView.getLastLaunchBackendPreflightPayloads === "function") {
        const payloads = launchView.getLastLaunchBackendPreflightPayloads();
        return (Array.isArray(payloads) ? payloads : []).find((payload) => String(payload?.target || "").toLowerCase() === "pipeline") || null;
      }
      return null;
    }


    function queueLaunchBackendPreflightRows(payload) {
      if (!payload) return [];
      const launchView = launchViewApi();
      if (typeof launchView.launchBackendPreflightRows === "function") return launchView.launchBackendPreflightRows([payload]);
      const target = payload?.target || "pipeline";
      return (Array.isArray(payload?.checks) ? payload.checks : []).map((check, index) => ({
        key: `${target}:${check.key || check.label || index}`,
        target,
        check: check.label || check.key || "Check",
        posture: check.status || "unknown",
        evidence: check.evidence || "",
        action: check.action || "",
        detail: Array.isArray(check.detail) ? check.detail : [],
        payload,
      }));
    }


    function queueLaunchBackendPreflightCheckpoint() {
      const payload = queueLaunchBackendPreflightPayload();
      if (!payload) {
        return {
          posture: "Evidence incomplete",
          evidence: "Pipeline backend launch preflight has not been loaded in this WebView session.",
          action: "Open Launch or refresh the Launch page so Queue can display backend-authored start blockers.",
          detail: [
            "Queue can preview source readiness, but backend launch preflight is the closer authority for schedule, settings, process locks, stale active work, and service availability.",
            "This row is read-only and cannot start queued work.",
          ],
        };
      }
      const rows = queueLaunchBackendPreflightRows(payload);
      const launchView = launchViewApi();
      const refreshInfo = typeof launchView.getLastLaunchBackendPreflightRefreshInfo === "function" ? launchView.getLastLaunchBackendPreflightRefreshInfo() : {};
      const status = String(payload.status || "unknown").toLowerCase();
      const nonReadyRows = rows.filter((row) => String(row.posture || "").toLowerCase() !== "ready");
      const blockedRows = rows.filter((row) => queueLaunchDecisionPostureStatus(row.posture) === "blocked");
      const reviewRows = rows.filter((row) => ["warning", "changed"].includes(queueLaunchDecisionPostureStatus(row.posture)));
      let posture = "Ready";
      if (status === "blocked" || blockedRows.length) {
        posture = "Blocked";
      } else if (status === "high review" || status === "review" || reviewRows.length) {
        posture = "Review first";
      } else if (status === "unknown" || payload.can_request_start === false) {
        posture = "Evidence incomplete";
      }
      const request = payload.request || {};
      const detail = [
        `Target: ${payload.target || "pipeline"}`,
        `Start route: ${payload.start_route || "/api/pipeline/start"}`,
        `Final authority: ${payload.final_authority || "Backend start routes re-check state at submission time."}`,
        `Last backend preflight refresh: ${refreshInfo.loaded_at || "unknown"}; requested=${refreshInfo.request_count || 0}; payloads=${refreshInfo.payload_count || 0}; fetch failures=${refreshInfo.fetch_failure_count || 0}.`,
        `Request mode: ${request.mode || "default"}; schedule override: ${request.schedule_override || "none"}.`,
      ];
      nonReadyRows.slice(0, 8).forEach((row) => {
        detail.push(`${row.check}: ${row.posture}; ${row.evidence || "no evidence"}; ${row.action || "review in Launch"}`);
      });
      if (nonReadyRows.length > 8) detail.push(`${nonReadyRows.length - 8} more backend launch preflight check(s) need review.`);
      if (!nonReadyRows.length) detail.push("No backend-authored pipeline preflight blocker is visible in the cached Launch payload.");
      detail.push("Mutation guardrail: Queue only reads the cached backend preflight payload; it cannot reserve locks, clear flags, save settings, or start work.");
      return {
        posture,
        evidence: `Pipeline preflight=${payload.status || "unknown"}; can request start=${payload.can_request_start === true ? "yes" : "no"}; checks=${rows.length}; blocked=${blockedRows.length}; review=${reviewRows.length}; fetch failures=${refreshInfo.fetch_failure_count || 0}.`,
        action: posture === "Blocked"
          ? "Do not launch. Open Launch > Backend Launch Preflight and Diagnostics before retrying."
          : posture === "Review first"
            ? "Review the Launch backend preflight rows for context; start routes still re-check immediately before launch."
            : posture === "Evidence incomplete"
              ? "Refresh Launch backend preflight for current evidence, or open Launch and let backend start re-check."
              : "Backend preflight is currently ready-looking; start routes still re-check immediately before launch.",
        detail,
      };
    }


    function queueLaunchDecisionSelectedRowSummary(row) {
      if (!row) return {
        status: "warning",
        evidence: "No queue row is selected.",
        action: "Optional: select a representative row for concrete route, source, and runtime-history context.",
        detail: [
          "A selected row is not required by backend launch, but it gives the operator a concrete route, source, and runtime-history sample to inspect.",
        ],
      };
      const reviewFlags = Array.isArray(row.review_flags) ? row.review_flags.filter(Boolean) : [];
      const runtimeStatus = String(row.runtime_outcome_status || "").toLowerCase();
      const runtimeFreshness = String(row.runtime_outcome_freshness_status || "").toLowerCase();
      const blocked = Boolean(row.blocked_reason || row.blocked_reason_code || row.error || String(row.status || "").toLowerCase().includes("blocked"));
      const freshIssue = runtimeFreshness === "fresh" && ["failed", "error", "skipped", "stopped"].some((value) => runtimeStatus.includes(value));
      if (blocked) {
        return {
          status: "blocked",
          evidence: [row.blocked_reason_code, row.blocked_reason, row.error].filter(Boolean).join(" - ") || "selected row is blocked",
          action: "Do not launch this row until Queue diagnostics explain the blocker.",
          detail: queueRowIssueDigestLines(row),
        };
      }
      if (freshIssue || reviewFlags.length || String(row.operator_severity || "").toLowerCase() === "warning") {
        return {
          status: "warning",
          evidence: freshIssue ? [row.runtime_outcome_status, row.runtime_outcome_error_code, row.runtime_outcome_reason].filter(Boolean).join(" - ") : reviewFlags.join(", ") || row.operator_status || "selected row needs review",
          action: "Inspect Queue diagnostics, route evidence, and recent logs when this selected row explains queue risk.",
          detail: queueRowIssueDigestLines(row),
        };
      }
      if (row.runtime_checks_deferred) {
        return {
          status: "changed",
          evidence: "Source stability/output-path checks are deferred until backend processing starts.",
          action: "Launch can proceed only with the expectation that backend runtime checks may still stop the row.",
          detail: queueRowIssueDigestLines(row),
        };
      }
      return {
        status: "ready",
        evidence: row.route_decision_summary || row.route_name || row.operator_status || "selected row has no blocker in the loaded snapshot",
        action: "Use Launch only after page-level readiness, schedule, and settings agree.",
        detail: queueRowIssueDigestLines(row),
      };
    }


    function queueCurrentFilterScope(rows = getLastQueueRows()) {
      const allRows = Array.isArray(rows) ? rows : [];
      const filterText = byId("queue-filter")?.value || "";
      const statusFilter = byId("queue-status-filter")?.value || "all";
      const investigationFilter = byId("queue-investigation-filter")?.value || "all";
      const normalizedStatus = String(statusFilter || "all").trim().toLowerCase();
      const normalizedInvestigation = String(investigationFilter || "all").trim().toLowerCase();
      const textRows = typeof filterRows === "function" ? filterRows(allRows, filterText, QUEUE_FILTER_FIELDS) : allRows;
      const statusRows = typeof filterRowsByStatus === "function" ? filterRowsByStatus(textRows, statusFilter, queueTableRowStatus) : textRows;
      const visibleRows = typeof filterRowsByInvestigation === "function" ? filterRowsByInvestigation(statusRows, investigationFilter, queueMatchesInvestigationFilter) : statusRows;
      const visibleSet = new Set(visibleRows);
      const hiddenRows = allRows.filter((row) => !visibleSet.has(row));
      const hiddenBlocked = hiddenRows.filter((row) => queueTableRowStatus(row) === "blocked").length;
      const hiddenWarning = hiddenRows.filter((row) => queueTableRowStatus(row) === "warning").length;
      const hiddenReview = hiddenRows.filter((row) => queueReviewRowReasons(row).length || ["blocked", "warning"].includes(queueTableRowStatus(row))).length;
      const active = Boolean(String(filterText || "").trim())
        || (normalizedStatus && normalizedStatus !== "all")
        || (normalizedInvestigation && normalizedInvestigation !== "all");
      return {
        active,
        filterText: String(filterText || "").trim(),
        statusFilter: normalizedStatus || "all",
        statusLabel: typeof tableStatusFilterLabel === "function" ? tableStatusFilterLabel(statusFilter) : statusFilter,
        investigationFilter: normalizedInvestigation || "all",
        investigationLabel: queueInvestigationFilterLabel(investigationFilter),
        totalRows: allRows.length,
        visibleRows: visibleRows.length,
        hiddenRows: hiddenRows.length,
        hiddenBlocked,
        hiddenWarning,
        hiddenReview,
        renderLimit: 250,
      };
    }


    function queueFilterScopePosture(scope) {
      if (!scope?.active) return "Ready - display unfiltered";
      if (scope.hiddenBlocked || scope.hiddenReview) return "Review first";
      if (scope.visibleRows === 0 && scope.totalRows > 0) return "Read evidence";
      return "Read evidence";
    }


    function queueFilterScopeEvidence(scope) {
      return `Filters=${scope.active ? "active" : "inactive"}; visible=${scope.visibleRows}/${scope.totalRows}; hidden=${scope.hiddenRows}; hidden blocked=${scope.hiddenBlocked}; hidden review=${scope.hiddenReview}.`;
    }


    function queueFilterScopeAction(scope) {
      if (!scope.active) {
        return "No local Queue filter is narrowing the table, but Launch still uses backend-owned queue scope rather than table selection.";
      }
      if (scope.hiddenBlocked || scope.hiddenReview) {
        return "Clear display filters or inspect hidden review rows before Launch; backend start scope is not narrowed to the visible table.";
      }
      return "Treat filters as display-only search. Backend start routes do not receive Queue filter state or visible-row subsets.";
    }


    function queueFilterScopeDetailLines(scope) {
      const lines = [
        "Queue display filter / backend launch scope:",
        `Text filter: ${scope.filterText || "none"}`,
        `Status filter: ${scope.statusLabel || scope.statusFilter || "all"}`,
        `Investigation view: ${scope.investigationLabel || scope.investigationFilter || "all"}`,
        `Visible rows after filters: ${scope.visibleRows} of ${scope.totalRows}`,
        `Hidden rows: ${scope.hiddenRows}; hidden blocked rows: ${scope.hiddenBlocked}; hidden warning rows: ${scope.hiddenWarning}; hidden review rows: ${scope.hiddenReview}`,
        `Render cap: first ${scope.renderLimit} visible rows are rendered when a large filtered set remains.`,
        "Backend launch scope: unchanged. Launch routes use backend queue/schedule/settings checks, not the visible WebView table subset.",
        "Mutation guardrail: Queue filters never launch, skip, reorder, drop, delete, rewrite snapshots, or narrow processing commands.",
      ];
      if (scope.active && (scope.hiddenBlocked || scope.hiddenReview)) {
        lines.push("Operator warning: the current filters hide rows that need review, so the visible table can look safer than the backend launch scope.");
      } else if (scope.active) {
        lines.push("Operator note: the current filters are active for visual search only.");
      } else {
        lines.push("Operator note: no display filter is active.");
      }
      return lines;
    }


    function queueBackendLaunchScopeRows(queue = getLastQueuePayload(), rows = getLastQueueRows(), entries) {
      const payload = queue || {};
      const rowList = Array.isArray(rows) ? rows : [];
      const history = Array.isArray(entries) ? entries : [];
      const counts = queueCounts(payload, rowList);
      const filterScope = queueCurrentFilterScope(rowList);
      const selected = getSelectedQueueRow();
      const backendPreflight = queueLaunchBackendPreflightCheckpoint();
      const latestCommand = queueLaunchDecisionLatestCommand(history);
      const issueLevel = queueLaunchCommandIssueLevel(latestCommand);
      const rowsOut = [
        {
          signal: "Backend start authority",
          evidence: "/api/pipeline/start owns Launch; Queue page is a read-only preview.",
          meaning: "Start scope is decided by saved backend queue/schedule/settings/process checks.",
          boundary: "No WebView queue row, filter, or selected-row key is submitted as launch scope.",
          status: "ready",
        },
        {
          signal: "Loaded queue snapshot",
          evidence: `loaded=${rowList.length}; runnable=${counts.runnable}; source candidates=${counts.sourceCount}; completed exclusions=${counts.completedExcluded}`,
          meaning: rowList.length ? "Backend Launch will re-check current saved state before processing." : "Empty preview needs explanation before unattended launch.",
          boundary: "Preview rows do not rewrite the queue snapshot or force processing order.",
          status: payload.error || (!rowList.length && counts.runnable <= 0) ? "warning" : "ready",
        },
        {
          signal: "Display filter vs launch scope",
          evidence: queueFilterScopeEvidence(filterScope),
          meaning: queueFilterScopeAction(filterScope),
          boundary: "Filters are table search only; backend launch scope remains unchanged.",
          status: filterScope.hiddenBlocked || filterScope.hiddenReview ? "warning" : filterScope.active ? "changed" : "ready",
        },
        {
          signal: "Selected row",
          evidence: selected ? selected.display_name || selected.relative_path || selected.source_path || "selected queue row" : "none selected",
          meaning: selected ? "Selection drives detail/open-target context only." : "No selected-row sample is available for quick inspection.",
          boundary: "Selecting a row cannot make Launch process only that row.",
          status: selected ? "ready" : "changed",
        },
        {
          signal: "Launch preflight cache",
          evidence: backendPreflight.evidence || "no cached backend launch preflight",
          meaning: backendPreflight.action || "Open Launch for authoritative start checks; refresh readiness for current evidence if useful.",
          boundary: "Only backend preflight/start routes can authorize or reject a run.",
          status: queueLaunchDecisionPostureStatus(backendPreflight.posture),
        },
        {
          signal: "Recent backend start command",
          evidence: latestCommand ? `${latestCommand.at || ""} ${latestCommand.command || latestCommand.raw?.command || "pipeline.start"} [${latestCommand.result || latestCommand.severity || (latestCommand.ok ? "ok" : "unknown")}]` : "none loaded",
          meaning: latestCommand
            ? "Use command history as evidence only; current queue/schedule/settings state still decides next launch."
            : "No recent backend start result is available in this WebView session.",
          boundary: "History display cannot retry, start, cancel, or override a command.",
          status: !latestCommand ? "changed" : ["error", "warning"].includes(issueLevel) ? "warning" : "ready",
        },
      ];
      return rowsOut;
    }


    function queueBackendLaunchScopeStatus(queue = getLastQueuePayload(), rows = getLastQueueRows(), entries) {
      const rowsOut = queueBackendLaunchScopeRows(queue, rows, entries);
      if (rowsOut.some((row) => row.status === "blocked")) return "Do not launch";
      if (rowsOut.some((row) => row.status === "warning")) return "Review first";
      if (rowsOut.some((row) => row.status === "changed" || row.status === "unknown")) return "Read evidence";
      return rowsOut.length ? "Ready-looking" : "Not evaluated";
    }


    function queueBackendLaunchScopeSummaryLines(queue = getLastQueuePayload(), rows = getLastQueueRows(), entries) {
      const payload = queue || {};
      const rowList = Array.isArray(rows) ? rows : [];
      const scope = queueCurrentFilterScope(rowList);
      const selected = getSelectedQueueRow();
      const latest = queueLaunchDecisionLatestCommand(Array.isArray(entries) ? entries : []);
      const lines = [
        "Backend launch scope boundary:",
        `Loaded queue rows: ${rowList.length}; visible after filters: ${scope.visibleRows}/${scope.totalRows}; selected row: ${selected ? "detail/open context only" : "none"}.`,
        queueHiddenSidecarLine(payload),
        `Active filters: ${scope.active ? "yes" : "no"}; hidden blocked/review rows: ${scope.hiddenBlocked}/${scope.hiddenReview}.`,
        `Backend start route: /api/pipeline/start; Queue filters, row selection, and rendered table caps are not submitted as processing scope.`,
        `Snapshot freshness: ${payload.snapshot_file_freshness_status || "unknown"}; produced freshness: ${payload.produced_freshness_status || "unknown"}.`,
        `Latest backend start evidence: ${latest ? latest.message || latest.result || latest.command || "loaded" : "none loaded"}.`,
      ];
      if (payload.error) {
        lines.push(`First action: do not launch until Queue error is resolved: ${payload.error}`);
      } else if (scope.hiddenBlocked || scope.hiddenReview) {
        lines.push("First action: clear filters or inspect hidden review rows before Launch; the backend can still see rows hidden by the table.");
      } else if (!rowList.length) {
        lines.push("First action: explain the empty queue with Source settings, Completed exclusions, schedule state, and Diagnostics before launch.");
      } else {
        lines.push("Suggested action: use this scope preview as context; Launch start remains backend-owned and re-checks at submission.");
      }
      lines.push("Mutation guardrail: this preview cannot launch, skip, reorder, drop, rewrite queue snapshots, delete files, or bypass backend validation.");
      return lines;
    }


    function renderQueueBackendLaunchScopePreview(queue = getLastQueuePayload(), rows = getLastQueueRows(), entries) {
      const payload = queue || {};
      const rowList = Array.isArray(rows) ? rows : [];
      const history = Array.isArray(entries) ? entries : [];
      const scopeRows = queueBackendLaunchScopeRows(payload, rowList, history);
      const status = queueBackendLaunchScopeStatus(payload, rowList, history);
      setText("queue-backend-scope-status", status);
      const statusNode = byId("queue-backend-scope-status");
      if (statusNode) statusNode.dataset.state = queueLaunchDecisionStatusState(status);
      setText("queue-backend-scope-summary", queueBackendLaunchScopeSummaryLines(payload, rowList, history).join("\n"));
      const tbody = byId("queue-backend-scope-rows");
      if (!tbody) return;
      if (!scopeRows.length) {
        clearRows(tbody, 4, "No backend launch scope rows loaded.");
        updateTableStatusLegend("queue-backend-scope-legend", tbody, "Backend launch scope rows");
        return;
      }
      tbody.replaceChildren();
      scopeRows.forEach((item) => {
        const row = document.createElement("tr");
        row.dataset.status = item.status === "blocked" ? "blocked" : item.status === "warning" ? "warning" : item.status === "changed" ? "changed" : "match";
        appendCells(row, [item.signal || "", item.evidence || "", item.meaning || "", item.boundary || ""]);
        tbody.appendChild(row);
      });
      updateTableStatusLegend("queue-backend-scope-legend", tbody, "Backend launch scope rows");
    }


    function queueLaunchDecisionRows(queue = getLastQueuePayload(), rows = getLastQueueRows(), entries) {
      const payload = queue || {};
      const rowList = Array.isArray(rows) ? rows : [];
      const history = Array.isArray(entries) ? entries : [];
      const counts = queueCounts(payload, rowList);
      const warnings = Array.isArray(payload.warnings) ? payload.warnings.filter(Boolean) : [];
      const reviewRows = queueReviewRows(payload, rowList);
      const selected = getSelectedQueueRow();
      const selectedSummary = queueLaunchDecisionSelectedRowSummary(selected);
      const latestCommand = queueLaunchDecisionLatestCommand(history);
      const latestIssue = queueLaunchCommandIssueLevel(latestCommand);
      const runtimeFreshness = payload.runtime_outcome_freshness_counts || {};
      const runtimeStatuses = payload.runtime_outcome_status_counts || {};
      const filterScope = queueCurrentFilterScope(rowList);
      const rowsOut = [];

      queueLaunchDecisionAdd(
        rowsOut,
        "backend-authority",
        "Backend launch authority",
        "Ready - backend owned",
        "Pipeline launch, audit, and Queue CSV Rerun start commands are backend routes with locking, schedule checks, and saved-settings validation.",
        "Use the Launch page for start commands; this Queue handoff cannot start, reorder, drop, or mutate work.",
        [
          "Queue is a read-only preview. Frontend launch decisions are advisory only.",
          "Backend launch routes remain authoritative for schedule, close-readiness, settings, process locks, and runtime safety checks.",
        ],
      );

      const backendPreflight = queueLaunchBackendPreflightCheckpoint();
      queueLaunchDecisionAdd(
        rowsOut,
        "backend-launch-preflight",
        "Backend launch preflight",
        backendPreflight.posture,
        backendPreflight.evidence,
        backendPreflight.action,
        backendPreflight.detail,
      );

      queueLaunchDecisionAdd(
        rowsOut,
        "payload",
        "Queue payload",
        payload.error ? "Blocked" : rowList.length ? "Ready" : "Review",
        payload.error ? `Queue unavailable: ${payload.error}` : `${rowList.length} visible row(s), ${counts.runnable} runnable, ${counts.sourceCount} source candidate(s).`,
        payload.error ? "Open Diagnostics > Queue Snapshot, Run Logs, and Last Stderr to explain the queue error." : rowList.length ? "Queue checklist is ready-looking; open Launch for authoritative start checks." : "Do not launch from an empty visible queue until exclusions/source roots are explained.",
        payload.error ? [`Error: ${payload.error}`] : queueReadinessLines(payload, rowList).slice(0, 8),
      );

      queueLaunchDecisionAdd(
        rowsOut,
        "display-filter-scope",
        "Display filter / backend launch scope",
        queueFilterScopePosture(filterScope),
        queueFilterScopeEvidence(filterScope),
        queueFilterScopeAction(filterScope),
        queueFilterScopeDetailLines(filterScope),
      );

      queueLaunchDecisionAdd(
        rowsOut,
        "freshness",
        "Snapshot freshness",
        queueSnapshotIsStale(payload) ? "Refresh first" : "Ready",
        `Snapshot: ${payload.snapshot_file_age_text || "unknown"} (${payload.snapshot_file_freshness_status || "unknown"}); produced: ${payload.produced_age_text || "unknown"} (${payload.produced_freshness_status || "unknown"}).`,
        queueSnapshotIsStale(payload) ? "Refresh queue preview from Launch before processing; stale snapshots can hide moved, completed, or half-copied files." : "Use the loaded queue freshness as current-enough preview evidence.",
        [
          queueFreshnessLine("Snapshot file age", payload.snapshot_file_age_text, payload.snapshot_file_freshness_status, payload.snapshot_file_mtime_utc),
          queueFreshnessLine("Produced age", payload.produced_age_text, payload.produced_freshness_status),
        ],
      );

      queueLaunchDecisionAdd(
        rowsOut,
        "blocked-invalid",
        "Blocked and invalid rows",
        Number(payload.invalid_row_count || 0) || Number(payload.blocked_row_count || 0) || reviewRows.length ? "Review first" : "Ready",
        `Blocked=${payload.blocked_row_count || 0}; invalid=${payload.invalid_row_count || 0}; review rows=${reviewRows.length}.`,
        reviewRows.length ? "Select flagged rows and inspect Queue Diagnostics Cross-Links before a broad unattended launch." : "No blocker rows are visible in the loaded queue payload.",
        queueReviewBoardLines(payload, rowList).slice(0, 10),
      );

      queueLaunchDecisionAdd(
        rowsOut,
        "runtime-context",
        "Runtime and deferred checks",
        payload.runtime_outcome_warning || Number(runtimeFreshness.stale || 0) > 0 ? "Read evidence" : Number(payload.runtime_check_deferred_count || 0) > 0 ? "Review first" : "Ready",
        `Deferred=${payload.runtime_check_deferred_count || 0}; matched=${payload.runtime_outcome_match_count || 0}; freshness=${queueFormatCounts(runtimeFreshness)}; statuses=${queueFormatCounts(runtimeStatuses)}.`,
        payload.runtime_outcome_warning || Number(runtimeFreshness.stale || 0) > 0
          ? "Treat runtime history as context only; Run Logs/Last Stderr can explain stale runtime evidence."
          : Number(payload.runtime_check_deferred_count || 0) > 0
            ? "Expect backend runtime checks to still stop unstable sources or unsafe output paths after launch."
            : "No runtime-history warning is visible in the loaded payload.",
        queueRuntimeLines(payload, rowList).slice(0, 10),
      );

      queueLaunchDecisionAdd(
        rowsOut,
        "completed-exclusions",
        "Completed and excluded proof",
        Number(payload.excluded_row_count || 0) > 0 || Number(payload.completed_excluded_count || 0) > 0 || String(payload.completed_collision_severity || "").toLowerCase() === "warning" ? "Read evidence" : "Ready",
        `Completed/blocked exclusions=${payload.completed_excluded_count || 0}; excluded detail=${payload.excluded_row_count || 0}; collision=${payload.completed_collision_status || "unknown"}.`,
        Number(payload.excluded_row_count || 0) > 0 || Number(payload.completed_excluded_count || 0) > 0
          ? "Review Excluded Source Rows and Completed before assuming files were missed or relaunching a source tree."
          : "No completed/excluded proof issue is visible in the loaded queue payload.",
        queueCollisionLines(payload, rowList).slice(0, 10),
      );

      queueLaunchDecisionAdd(
        rowsOut,
        "selected-row",
        "Selected row sample",
        selectedSummary.status === "blocked" ? "Blocked" : selectedSummary.status === "warning" ? "Review first" : selectedSummary.status === "changed" ? "Read evidence" : "Ready",
        selectedSummary.evidence,
        selectedSummary.action,
        selectedSummary.detail,
        selected,
      );

      queueLaunchDecisionAdd(
        rowsOut,
        "recent-launch-command",
        "Recent launch command",
        !latestCommand ? "Read evidence" : ["error", "warning"].includes(latestIssue) ? "Review first" : "Ready",
        latestCommand ? `${latestCommand.at || ""} ${latestCommand.command || latestCommand.raw?.command || "launch command"}: ${latestCommand.message || latestCommand.result || latestIssue}` : "No recent pipeline/audit/rerun start command in the local command stream.",
        !latestCommand
          ? "Use Queue readiness, Launch readiness, and saved-settings trust as context when opening Launch."
          : ["error", "warning"].includes(latestIssue)
            ? "Inspect the latest launch command result and Diagnostics before trying again."
            : "Recent launch command history has no visible warning/error, but current Queue readiness still decides the next attempt.",
        latestCommand ? [
          `Command: ${latestCommand.command || latestCommand.raw?.command || "unknown"}`,
          `Result: ${latestCommand.result || latestCommand.severity || (latestCommand.ok ? "ok" : "unknown")}`,
          `Message: ${latestCommand.message || ""}`,
        ] : [
          "No recent backend start command is available in the loaded command history.",
        ],
      );

      queueLaunchDecisionAdd(
        rowsOut,
        "diagnostics-order",
        "Diagnostics read order",
        warnings.length || queueSnapshotIsStale(payload) || reviewRows.length ? "Read evidence" : "Ready",
        "Read Queue Snapshot first, then Last Stderr, Run Logs, Active Jobs, Completed, and Pending Publish when row state conflicts with disk state.",
        warnings.length || queueSnapshotIsStale(payload) || reviewRows.length ? "Use backend-allowlisted Diagnostics before Launch." : "Diagnostics are optional unless the Launch page raises a blocker.",
        [
          "Read first: Queue Snapshot and Last Stderr.",
          "Open next: Run Logs and Active Jobs for stale/active runtime state.",
          "Cross-check: Completed for exclusions and Pending Publish for parked outputs.",
        ],
      );

      queueLaunchDecisionAdd(
        rowsOut,
        "decision-boundary",
        "Decision boundary",
        "Ready - backend owned",
        "This checklist is advisory. Backend Launch remains authoritative and may still block the run.",
        "Start only from Launch; do not treat this table as queue mutation, schedule override, or settings validation.",
        [
          "Mutation guardrail: this handoff cannot launch, reorder, drop, rewrite queue snapshots, delete files, clear completed state, override schedule, or bypass backend validation.",
        ],
      );

      return rowsOut;
    }


    function queueLaunchDecisionStatus(queue, rows, entries) {
      const decisionRows = queueLaunchDecisionRows(queue, rows, entries);
      if (decisionRows.some((row) => queueLaunchDecisionPostureStatus(row.posture) === "blocked")) return "Do not launch";
      if (decisionRows.some((row) => queueLaunchDecisionPostureStatus(row.posture) === "warning")) return "Review first";
      if (decisionRows.some((row) => queueLaunchDecisionPostureStatus(row.posture) === "changed")) return "Read evidence";
      if (decisionRows.some((row) => queueLaunchDecisionPostureStatus(row.posture) === "unknown")) return "Evidence incomplete";
      return decisionRows.length ? "Ready-looking" : "Not evaluated";
    }


    function queueLaunchDecisionStatusState(status) {
      const normalized = String(status || "").trim().toLowerCase();
      if (normalized === "do not launch") return "blocked";
      if (normalized === "review first") return "warning";
      if (normalized === "read evidence") return "changed";
      if (normalized === "evidence incomplete" || normalized === "not evaluated") return "unknown";
      if (normalized === "ready-looking") return "ready";
      return "unknown";
    }


    function queueLaunchDecisionSummaryLines(queue, rows, entries) {
      const decisionRows = queueLaunchDecisionRows(queue, rows, entries);
      const blocked = decisionRows.filter((row) => queueLaunchDecisionPostureStatus(row.posture) === "blocked").length;
      const review = decisionRows.filter((row) => queueLaunchDecisionPostureStatus(row.posture) === "warning").length;
      const readFirst = decisionRows.filter((row) => queueLaunchDecisionPostureStatus(row.posture) === "changed").length;
      const unknown = decisionRows.filter((row) => queueLaunchDecisionPostureStatus(row.posture) === "unknown").length;
      const outcome = blocked ? "Do not launch" : review ? "Review first" : readFirst ? "Read evidence" : unknown ? "Evidence incomplete" : decisionRows.length ? "Ready-looking" : "Not evaluated";
      const lines = [
        "Queue-to-Launch handoff:",
        `Daily-use handoff: Queue evidence decides whether it is sensible to open Launch; backend Launch owns final start authorization. Operator outcome: ${outcome}.`,
        `Checkpoints loaded: ${decisionRows.length}`,
        `Blocked/review/read-first/unknown: ${blocked}/${review}/${readFirst}/${unknown}`,
        "Decision context: use backend launch preflight, queue payload, display filter scope, freshness, blocked rows, runtime context, completed exclusions, selected-row proof, command history, and Launch readiness as advisory context; Launch performs authoritative start checks.",
        "Scope boundary: Queue filters, selected rows, review boards, and rendered row caps never narrow backend launch scope or mutate the queue.",
      ];
      if (blocked) {
        lines.push("First action: do not start queued work until blocked evidence is explained in Diagnostics.");
      } else if (review || readFirst || unknown) {
        lines.push("Suggested action: inspect review/read-first checkpoints when they explain a concrete issue; open Launch for authoritative schedule, settings, lock, and process validation.");
      } else {
        lines.push("First action: Queue evidence is ready-looking; open Launch for authoritative schedule, settings, lock, and process validation.");
      }
      lines.push("Mutation guardrail: this handoff cannot launch, reorder, drop, rewrite queue snapshots, delete files, clear completed state, override schedule, or bypass backend validation.");
      return lines;
    }


    function queueLaunchDecisionDetailLines(item) {
      if (!item) {
        return [
          "Queue-to-Launch handoff:",
          "Select a handoff checkpoint for detail.",
          "Mutation guardrail: this detail panel is read-only.",
        ];
      }
      const lines = [
        "Queue-to-Launch handoff:",
        `Checkpoint: ${item.checkpoint || "unknown"}`,
        `Posture: ${item.posture || "read-only"}`,
        `Evidence: ${item.evidence || ""}`,
        `Safe next step: ${item.action || ""}`,
      ];
      (Array.isArray(item.detail) ? item.detail : []).forEach((line) => lines.push(line));
      if (item.row) {
        lines.push("");
        lines.push("Associated queue row:");
        lines.push(`Status: ${item.row.operator_status || item.row.status || "unknown"}`);
        lines.push(`Route: ${item.row.route_decision_summary || item.row.route_name || "unknown"}`);
        lines.push(`Runtime: ${item.row.runtime_outcome_status || "none"}${item.row.runtime_outcome_freshness_status ? ` (${item.row.runtime_outcome_freshness_status})` : ""}`);
        lines.push(`Source: ${item.row.source_path || "unknown"}`);
      }
      lines.push("");
      lines.push("Guardrail: only backend Launch routes can start processing or reject a start attempt.");
      return lines;
    }


    function selectedQueueLaunchDecisionRow(decisionRows) {
      const rows = Array.isArray(decisionRows) ? decisionRows : [];
      return rows.find((row) => row.key === selectedQueueLaunchDecisionKey) || rows[0] || null;
    }


    function selectQueueLaunchDecisionRow(item) {
      selectedQueueLaunchDecisionKey = item?.key || "";
      if (item?.row) {
        selectQueueRow(item.row);
      }
      renderQueueLaunchDecisionChecklist(getLastQueuePayload(), getLastQueueRows(), getCommandHistory());
    }


    function renderQueueLaunchDecisionChecklist(queue = getLastQueuePayload(), rows = getLastQueueRows(), entries) {
      const payload = queue || {};
      const rowList = Array.isArray(rows) ? rows : [];
      const history = Array.isArray(entries) ? entries : [];
      const decisionRows = queueLaunchDecisionRows(payload, rowList, history);
      if (selectedQueueLaunchDecisionKey && !decisionRows.some((row) => row.key === selectedQueueLaunchDecisionKey)) {
        selectedQueueLaunchDecisionKey = "";
      }
      const selected = selectedQueueLaunchDecisionRow(decisionRows);
      const status = queueLaunchDecisionStatus(payload, rowList, history);
      setText("queue-launch-decision-status", status);
      const statusNode = byId("queue-launch-decision-status");
      if (statusNode) statusNode.dataset.state = queueLaunchDecisionStatusState(status);
      setText("queue-launch-decision-summary", queueLaunchDecisionSummaryLines(payload, rowList, history).join("\n"));
      setText("queue-launch-decision-detail", queueLaunchDecisionDetailLines(selected).join("\n"));
      const tbody = byId("queue-launch-decision-rows");
      if (!tbody) return;
      if (!decisionRows.length) {
        clearRows(tbody, 4, "No queue-to-Launch handoff rows loaded.");
        updateTableStatusLegend("queue-launch-decision-legend", tbody, "Queue-to-Launch handoff rows");
        return;
      }
      tbody.replaceChildren();
      decisionRows.forEach((item) => {
        const row = document.createElement("tr");
        row.dataset.status = queueLaunchDecisionPostureStatus(item.posture);
        appendCells(row, [item.checkpoint || "", item.posture || "Read-only", item.evidence || "", item.action || ""]);
        makeRowSelectable(row, () => selectQueueLaunchDecisionRow(item), {
          selected: item.key === selectedQueueLaunchDecisionKey,
          label: `Queue-to-Launch handoff checkpoint ${item.checkpoint || ""}`,
        });
        tbody.appendChild(row);
      });
      updateTableStatusLegend("queue-launch-decision-legend", tbody, "Queue-to-Launch handoff rows");
      if (typeof renderLaunchScopeReconciliation === "function") {
        renderLaunchScopeReconciliation();
      }
    }

    return {
      queueLaunchDecisionPostureStatus,
      isQueueLaunchCommand,
      queueLaunchDecisionLatestCommand,
      queueLaunchCommandIssueLevel,
      queueLaunchDecisionAdd,
      queueLaunchBackendPreflightPayload,
      queueLaunchBackendPreflightRows,
      queueLaunchBackendPreflightCheckpoint,
      queueLaunchDecisionSelectedRowSummary,
      queueCurrentFilterScope,
      queueFilterScopePosture,
      queueFilterScopeEvidence,
      queueFilterScopeAction,
      queueFilterScopeDetailLines,
      queueBackendLaunchScopeRows,
      queueBackendLaunchScopeStatus,
      queueBackendLaunchScopeSummaryLines,
      renderQueueBackendLaunchScopePreview,
      queueLaunchDecisionRows,
      queueLaunchDecisionStatus,
      queueLaunchDecisionStatusState,
      queueLaunchDecisionSummaryLines,
      queueLaunchDecisionDetailLines,
      selectedQueueLaunchDecisionRow,
      selectQueueLaunchDecisionRow,
      renderQueueLaunchDecisionChecklist,
    };
  }

  window.__queueLaunchModule = { createQueueLaunchModule };
})();
