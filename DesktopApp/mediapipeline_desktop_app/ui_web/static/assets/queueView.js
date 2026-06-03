(function () {
  let lastQueueRows = [];
  let lastQueueExcludedRows = [];
  let lastQueueHiddenSidecarRows = [];
  let lastQueuePayload = {};
  let lastQueueEmptyMessage = "No queue rows available.";
  let queueScanInFlight = false;
  let queueScanPollTimer = null;
  const QUEUE_HIDDEN_SIDECAR_EXTENSIONS = new Set([".srt", ".ass", ".ssa", ".vtt", ".sub", ".idx", ".sup"]);
  const QUEUE_FILTER_FIELDS = ["media_type", "display_name", "relative_path", "source_path", "route_name", "route_reason", "route_reason_code", "route_decision_summary", "route_evidence_lines", "phase", "priority_reasons", "blocked_reason", "error", "operator_status", "operator_guidance", "review_flags", "runtime_outcome_status", "runtime_outcome_error_code", "runtime_outcome_reason", "runtime_outcome_event_type"];
  const QUEUE_PRIORITY_ROUTE = "/api/queue/priority";
  const QUEUE_STRATEGY_ROUTE = "/api/queue/strategy";
  const QUEUE_FILE_OVERRIDES_ROUTE = "/api/queue/file-overrides";

  // ---------------------------------------------------------------------------
  // Consume split Queue children: summary, review, detail, launch.
  // Children use temporary stash globals that are deleted immediately here.
  // ---------------------------------------------------------------------------

  const __queueSummaryMod = window.__queueSummaryModule || {};
  delete window.__queueSummaryModule;
  const _queueSummary = typeof __queueSummaryMod.createQueueSummaryModule === "function"
    ? __queueSummaryMod.createQueueSummaryModule({
      setText: typeof setText === "function" ? setText : window.setText,
      queueHiddenSidecarExtensions: QUEUE_HIDDEN_SIDECAR_EXTENSIONS,
      queueValidationStatus,
    })
    : {};
  const _queueNoop = function () {};
  const _queueEmptyArray = function () { return []; };
  const _queueEmptyObject = function () { return {}; };
  const _queueEmptyString = function () { return ""; };
  const _queueFalse = function () { return false; };
  const _queueIdentity = function (row) { return row; };
  const _queueEmptySet = function () { return new Set(); };

  const __queueSelectionMod = window.__queueSelectionModule || {};
  delete window.__queueSelectionModule;
  const _queueSelection = typeof __queueSelectionMod.createQueueSelectionModule === "function"
    ? __queueSelectionMod.createQueueSelectionModule({
      getCommandHistory: () => typeof getCommandHistory === "function" ? getCommandHistory() : [],
      getLastQueueExcludedRows: () => lastQueueExcludedRows,
      getLastQueuePayload: () => lastQueuePayload,
      getLastQueueRows: () => lastQueueRows,
      renderQueueBackendLaunchScopePreview: (payload, rows, history) => renderQueueBackendLaunchScopePreview(payload, rows, history),
      renderQueueDetail: (row) => renderQueueDetail(row),
      renderQueueExcluded: (payload) => renderQueueExcluded(payload),
      renderQueueExcludedDetail: (row) => renderQueueExcludedDetail(row),
      renderQueueLaunchDecisionChecklist: (payload, rows, history) => renderQueueLaunchDecisionChecklist(payload, rows, history),
      renderQueueReviewDigest: (payload, rows) => renderQueueReviewDigest(payload, rows),
      renderQueueRows: () => renderQueueRows(),
      setText: typeof setText === "function" ? setText : window.setText,
    })
    : {};
  const {
    getLastQueuePayload = function () { return lastQueuePayload || {}; },
    getLastQueueRows = function () { return lastQueueRows.slice(); },
    getSelectedQueueExcludedRow = function () { return null; },
    getSelectedQueueExcludedRowKey = _queueEmptyString,
    getSelectedQueueRow = function () { return null; },
    getSelectedQueueRowKey = _queueEmptyString,
    queueExcludedRowKey = _queueEmptyString,
    queueRowKey = _queueEmptyString,
    selectQueueExcludedRow = _queueNoop,
    selectQueueRow = _queueNoop,
    syncSelectedQueueRows = _queueNoop,
  } = _queueSelection;
  const {
    queuePathExtension = _queueNoop,
    queueRowExtension = _queueNoop,
    queueIsHiddenSidecarBlockedRow = _queueNoop,
    queueIncrementCount = _queueNoop,
    queueCountRowsBy = _queueNoop,
    queueCountRowsByExtension = _queueNoop,
    queueIsMovieRow = _queueNoop,
    queueIsTvRow = _queueNoop,
    queueBlockedRows = _queueNoop,
    queueVisibleRunnableCount = _queueNoop,
    queueDisplayPayloadForVisibleRows = _queueNoop,
    queueDisplayProgressForVisibleRows = _queueNoop,
    queueHiddenSidecarLine = _queueNoop,
    queueEmptyStateMessage = _queueNoop,
    queueProgressPayload = _queueNoop,
    queueProgressBars = _queueNoop,
    queueProgressStatus = _queueNoop,
    queueProgressSummaryLines = _queueNoop,
    renderQueueProgress = _queueNoop,
    queueFreshnessLine = _queueNoop,
    queueSnapshotIsStale = _queueNoop,
    renderQueueSummary = _queueNoop,
    queueCounts = _queueNoop,
    queueReadinessStatus = _queueNoop,
    queueReadinessLines = _queueNoop,
    renderQueueReadiness = _queueNoop,
    queueWorkflowStatus = _queueNoop,
    queueWorkflowLines = _queueNoop,
    renderQueueWorkflow = _queueNoop,
    queueFormatCounts = _queueNoop,
  } = _queueSummary;

  function queuePayloadNumber(payload, key, fallback = 0) {
    if (payload && Object.prototype.hasOwnProperty.call(payload, key)) {
      const value = Number(payload[key]);
      return Number.isFinite(value) ? Math.max(0, value) : 0;
    }
    const fallbackValue = Number(fallback);
    return Number.isFinite(fallbackValue) ? Math.max(0, fallbackValue) : 0;
  }


  function queuePayloadRunnableCount(payload, rows) {
    const rowList = Array.isArray(rows) ? rows : [];
    return queuePayloadNumber(payload, "runnable_count", rowList.length);
  }


  const __queueReviewMod = window.__queueReviewModule || {};
  delete window.__queueReviewModule;
  const _queueReview = typeof __queueReviewMod.createQueueReviewModule === "function"
    ? __queueReviewMod.createQueueReviewModule({
      appendCells: typeof appendCells === "function" ? appendCells : window.appendCells,
      byId: typeof byId === "function" ? byId : window.byId,
      clearRows: typeof clearRows === "function" ? clearRows : window.clearRows,
      getSelectedQueueRowKey,
      makeRowSelectable: typeof makeRowSelectable === "function" ? makeRowSelectable : window.makeRowSelectable,
      queueFilterFields: QUEUE_FILTER_FIELDS,
      queueFormatCounts,
      queueHiddenSidecarLine,
      queueRowKey,
      queueSnapshotIsStale,
      queueWorkflowStatus,
      selectQueueRow,
      setText: typeof setText === "function" ? setText : window.setText,
      updateTableStatusLegend: typeof updateTableStatusLegend === "function" ? updateTableStatusLegend : window.updateTableStatusLegend,
    })
    : {};
  const {
    queueReviewRowReasons = _queueNoop,
    queueReviewRows = _queueNoop,
    queueReviewStatus = _queueNoop,
    queueReviewBoardLines = _queueNoop,
    queueReviewDigestStatus = _queueNoop,
    queueReviewDigestAction = _queueNoop,
    queueTableRowStatus = _queueNoop,
    queueInvestigationFilterLabel = _queueNoop,
    queueMatchesInvestigationFilter = _queueNoop,
    queueFocusedInvestigationLabels = _queueNoop,
    queueFilterVisibilityLines = _queueNoop,
    queueSelectedQuickSignalLines = _queueNoop,
    queueSelectedAtAGlanceState = _queueNoop,
    queueSelectedAtAGlanceStatus = _queueNoop,
    queueSelectedVisibilitySummary = _queueNoop,
    queueSelectedAtAGlanceLines = _queueNoop,
    renderQueueSelectedAtAGlance = _queueNoop,
    queueInvestigationSignalLines = _queueNoop,
    renderQueueReviewDigest = _queueNoop,
    renderQueueReviewBoard = _queueNoop,
    queueListText = _queueNoop,
  } = _queueReview;

  const __queueOpenActionsMod = window.__queueOpenActionsModule || {};
  delete window.__queueOpenActionsModule;
  const _queueOpenActions = typeof __queueOpenActionsMod.createQueueOpenActionsModule === "function"
    ? __queueOpenActionsMod.createQueueOpenActionsModule({
      apiPost: typeof apiPost === "function" ? apiPost : window.apiPost,
      appendCommandResult: typeof appendCommandResult === "function" ? appendCommandResult : window.appendCommandResult,
      documentRef: document,
      getSelectedQueueExcludedRow,
      getSelectedQueueRow,
      queueExcludedRowKey,
      queueListText,
      queueRowKey,
      setText: typeof setText === "function" ? setText : window.setText,
    })
    : {};
  const {
    queueSelectedOpenTargetLines = _queueEmptyArray,
    rejectQueueOpenWhileBusy = _queueNoop,
    requestQueueOpen = _queueNoop,
    setQueueOpenBusy = _queueNoop,
  } = _queueOpenActions;

  const __queueTableMod = window.__queueTableModule || {};
  delete window.__queueTableModule;
  const _queueTable = typeof __queueTableMod.createQueueTableModule === "function"
    ? __queueTableMod.createQueueTableModule({
      appendCells: typeof appendCells === "function" ? appendCells : window.appendCells,
      makeRowSelectable: typeof makeRowSelectable === "function" ? makeRowSelectable : window.makeRowSelectable,
      queueRowKey,
      queueTableRowStatus,
      selectQueueRow,
      shortenPath: typeof shortenPath === "function" ? shortenPath : window.shortenPath,
    })
    : {};
  window.__queueSetFileDrawer = typeof _queueTable.setOpenFileSettingsDrawer === "function"
    ? _queueTable.setOpenFileSettingsDrawer.bind(_queueTable)
    : null;
  const {
    queueIsOverrideArtifactRow = _queueFalse,
    queueOverrideTargetKeys = _queueEmptySet,
    queueRowWithOverrideMarker = _queueIdentity,
    queueDisplayRowStatus = queueTableRowStatus,
    renderQueueTableRows = _queueNoop,
  } = _queueTable;

  const __queueDetailMod = window.__queueDetailModule || {};
  delete window.__queueDetailModule;
  const _queueDetail = typeof __queueDetailMod.createQueueDetailModule === "function"
    ? __queueDetailMod.createQueueDetailModule({
      appendDiagnosticsBridgeButton: window.appendDiagnosticsBridgeButton,
      appendDiagnosticsBridgeGroupedButtons: window.appendDiagnosticsBridgeGroupedButtons,
      byId: typeof byId === "function" ? byId : window.byId,
      commandHistoryCompactEvidenceLine: window.commandHistoryCompactEvidenceLine,
      diagnosticsBridgeHandoffLines: window.diagnosticsBridgeHandoffLines,
      diagnosticsBridgeRowTrustLines: window.diagnosticsBridgeRowTrustLines,
      queueInvestigationSignalLines,
      queueListText,
      queueRowKey,
      queueSelectedAtAGlanceLines,
      queueSelectedOpenTargetLines,
      queueSelectedQuickSignalLines,
      renderQueueSelectedAtAGlance,
      requestQueueDiagnosticsAction,
      setText: typeof setText === "function" ? setText : window.setText,
    })
    : {};
  const {
    queueRowReviewChecklistLines = _queueEmptyArray,
    queueRowIssueDigestLines = _queueEmptyArray,
    queueRowCombinedReviewPlanLines = _queueEmptyArray,
    queueRealMediaTraceLines = _queueEmptyArray,
    queueRowTrustSummaryLines = _queueEmptyArray,
    queueDiagnosticsActionsForRow = _queueEmptyArray,
    queueAddDiagnosticsAction = _queueNoop,
    queueDiagnosticsGuidanceLines = _queueEmptyArray,
    queueDiagnosticsActionStatusText = _queueEmptyString,
    renderQueueDiagnosticsLinks = _queueNoop,
    queueRouteReasoningLines = _queueEmptyArray,
    renderQueueDetail = _queueNoop,
    renderQueueExcludedDetail = _queueNoop,
    isQueueOpenCommand = _queueNoop,
    queueOpenHistoryLine = _queueEmptyString,
    renderQueueOpenHistory = _queueNoop,
  } = _queueDetail;

  const __queueLaunchMod = window.__queueLaunchModule || {};
  delete window.__queueLaunchModule;
  const _queueLaunch = typeof __queueLaunchMod.createQueueLaunchModule === "function"
    ? __queueLaunchMod.createQueueLaunchModule({
      appendCells: typeof appendCells === "function" ? appendCells : window.appendCells,
      byId: typeof byId === "function" ? byId : window.byId,
      clearRows: typeof clearRows === "function" ? clearRows : window.clearRows,
      getCommandHistory: typeof getCommandHistory === "function" ? getCommandHistory : window.getCommandHistory,
      getLastQueuePayload,
      getLastQueueRows,
      getSelectedQueueRow,
      makeRowSelectable: typeof makeRowSelectable === "function" ? makeRowSelectable : window.makeRowSelectable,
      queueCounts,
      queueCollisionLines,
      queueFilterFields: QUEUE_FILTER_FIELDS,
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
      queueRowKey,
      queueRuntimeLines,
      queueSnapshotIsStale,
      queueTableRowStatus,
      renderQueueDetail,
      renderQueueReviewDigest,
      renderQueueRows,
      selectQueueRow,
      setText: typeof setText === "function" ? setText : window.setText,
      updateTableStatusLegend: typeof updateTableStatusLegend === "function" ? updateTableStatusLegend : window.updateTableStatusLegend,
    })
    : {};
  const {
    queueLaunchDecisionPostureStatus = _queueNoop,
    isQueueLaunchCommand = _queueNoop,
    queueLaunchDecisionLatestCommand = _queueNoop,
    queueLaunchCommandIssueLevel = _queueNoop,
    queueLaunchDecisionAdd = _queueNoop,
    queueLaunchBackendPreflightPayload = _queueNoop,
    queueLaunchBackendPreflightRows = _queueNoop,
    queueLaunchBackendPreflightCheckpoint = _queueNoop,
    queueLaunchDecisionSelectedRowSummary = _queueNoop,
    queueCurrentFilterScope = _queueNoop,
    queueFilterScopePosture = _queueNoop,
    queueFilterScopeEvidence = _queueNoop,
    queueFilterScopeAction = _queueNoop,
    queueFilterScopeDetailLines = _queueNoop,
    queueBackendLaunchScopeRows = _queueNoop,
    queueBackendLaunchScopeStatus = _queueNoop,
    queueBackendLaunchScopeSummaryLines = _queueNoop,
    renderQueueBackendLaunchScopePreview = _queueNoop,
    queueLaunchDecisionRows = _queueNoop,
    queueLaunchDecisionStatus = _queueNoop,
    queueLaunchDecisionStatusState = _queueNoop,
    queueLaunchDecisionSummaryLines = _queueNoop,
    queueLaunchDecisionDetailLines = _queueNoop,
    selectedQueueLaunchDecisionRow = _queueNoop,
    selectQueueLaunchDecisionRow = _queueNoop,
    renderQueueLaunchDecisionChecklist = _queueNoop,
  } = _queueLaunch;

  function queueScanStatus(queue = lastQueuePayload) {
    const payload = queue && typeof queue === "object" ? queue : {};
    const status = payload.queue_scan_status;
    return status && typeof status === "object" ? status : {};
  }

  function queueScanIsRunning(queue = lastQueuePayload) {
    const status = queueScanStatus(queue);
    return Boolean(status.running) || String(status.status || "").toLowerCase() === "running";
  }

  function queueSourceInventory(queue = lastQueuePayload) {
    const payload = queue && typeof queue === "object" ? queue : {};
    const inventory = payload.source_inventory;
    return inventory && typeof inventory === "object" ? inventory : {};
  }

  function queueScanStatusLines(queue = lastQueuePayload) {
    const status = queueScanStatus(queue);
    if (!status.schema_version && !status.status) {
      return ["Queue source scan: not requested in this session."];
    }
    const lines = [
      `Queue source scan: ${status.status || "unknown"}${status.phase ? ` (${status.phase})` : ""}.`,
      status.message || "Latest scan status loaded from backend state.",
    ];
    if (status.scan_id) lines.push(`Scan id: ${status.scan_id}`);
    if (status.inventory_count || status.curated_row_count) {
      lines.push(`Inventory candidates: ${status.inventory_count || 0}; curated queue rows: ${status.curated_row_count || 0}.`);
    }
    if (status.updated_at_utc) lines.push(`Updated: ${status.updated_at_utc}`);
    if (status.inventory_path) lines.push(`Inventory artifact: ${status.inventory_path}`);
    if (status.queue_snapshot_path) lines.push(`Queue snapshot: ${status.queue_snapshot_path}`);
    const warnings = Array.isArray(status.warnings) ? status.warnings : [];
    const errors = Array.isArray(status.errors) ? status.errors : [];
    warnings.slice(0, 3).forEach((warning) => lines.push(`Warning: ${warning}`));
    errors.slice(0, 3).forEach((error) => lines.push(`Error: ${error}`));
    return lines;
  }

  function queueSourceInventoryLines(queue = lastQueuePayload) {
    const inventory = queueSourceInventory(queue);
    const rows = Array.isArray(inventory.rows) ? inventory.rows : [];
    const lines = [
      ...queueScanStatusLines(queue),
      "",
      `Fast source inventory: ${inventory.row_count || inventory.available_row_count || rows.length || 0} candidate file(s).`,
      "Inventory candidates are not launchable queue rows. Wait for backend curation before Launch decisions.",
    ];
    const summary = Array.isArray(inventory.summary_lines) ? inventory.summary_lines : [];
    summary.slice(0, 4).forEach((line) => lines.push(String(line)));
    if (inventory.preview_truncated) {
      lines.push(`Preview truncated: showing ${rows.length} of ${inventory.available_row_count || inventory.row_count || rows.length} inventory rows.`);
    }
    if (rows.length) {
      lines.push("", "Newest inventory candidates:");
      rows.slice(0, 12).forEach((row) => {
        const kind = String(row.media_kind || "media").toUpperCase();
        const name = row.relative_path || row.display_name || row.source_path || "";
        const size = Number(row.size_gb);
        const sizeText = Number.isFinite(size) && size > 0 ? `${size.toFixed(3)} GB` : `${row.size_bytes || 0} bytes`;
        lines.push(`- [${kind}] ${name} (${sizeText})`);
      });
    }
    return lines;
  }

  function renderQueueScanArtifacts(queue = lastQueuePayload) {
    setText("queue-source-inventory", queueSourceInventoryLines(queue).join("\n"));
    window.mediaPipelineAppRefresh?.setQueueRefreshButtonBusy?.(queueScanIsRunning(queue));
  }

  function scheduleQueueScanPoll() {
    if (queueScanPollTimer) {
      window.clearTimeout(queueScanPollTimer);
      queueScanPollTimer = null;
    }
    if (!queueScanIsRunning()) return;
    queueScanPollTimer = window.setTimeout(async () => {
      queueScanPollTimer = null;
      if (typeof refreshAll === "function") {
        await refreshAll({ queueRefresh: true });
      }
      if (queueScanIsRunning()) scheduleQueueScanPoll();
    }, 1500);
  }

  function renderQueue(queue) {
    queue = queue && typeof queue === "object" ? queue : {};
    const rawRows = Array.isArray(queue.rows) ? queue.rows : [];
    const overrideArtifactRows = rawRows.filter(queueIsOverrideArtifactRow);
    const overrideTargetKeys = queueOverrideTargetKeys(overrideArtifactRows);
    const hiddenSidecars = rawRows.filter((row) => queueIsHiddenSidecarBlockedRow(row) && !queueIsOverrideArtifactRow(row));
    const rows = rawRows
      .filter((row) => !queueIsHiddenSidecarBlockedRow(row) && !queueIsOverrideArtifactRow(row))
      .map((row) => queueRowWithOverrideMarker(row, overrideTargetKeys));
    const displayQueue = queueDisplayPayloadForVisibleRows(queue, rows, hiddenSidecars, rawRows);
    const excludedRows = Array.isArray(queue.excluded_rows) ? queue.excluded_rows : [];
    lastQueuePayload = displayQueue;
    lastQueueRows = rows;
    lastQueueHiddenSidecarRows = hiddenSidecars;
    lastQueueExcludedRows = excludedRows;
    syncSelectedQueueRows(rows, excludedRows);
    lastQueueEmptyMessage = queueEmptyStateMessage(displayQueue, rows);
    renderQueueScanArtifacts(displayQueue);
    scheduleQueueScanPoll();
    renderQueueProgress(displayQueue);
    renderQueueSummary(displayQueue, rows);
    renderQueueReadiness(displayQueue, rows);
    renderQueueBreakdown(displayQueue, rows);
    renderQueueRuntime(displayQueue, rows);
    renderQueueValidation(displayQueue, rows);
    renderQueueWorkflow(displayQueue, rows);
    renderQueueBackendLaunchScopePreview(displayQueue, rows, typeof getCommandHistory === "function" ? getCommandHistory() : []);
    renderQueueLaunchDecisionChecklist(displayQueue, rows, typeof getCommandHistory === "function" ? getCommandHistory() : []);
    renderQueueReviewBoard(displayQueue, rows);
    renderQueueCollision(displayQueue, rows);
    renderQueueExcluded(displayQueue);
    renderQueueExcludedDetail(getSelectedQueueExcludedRow());
    if (typeof getCommandHistory === "function") renderQueueOpenHistory(getCommandHistory());
    renderQueueDetail(getSelectedQueueRow());
    renderQueueRows();
  }

  function queueBreakdownStatus(queue, rows) {
    const rowList = Array.isArray(rows) ? rows : [];
    if (queue?.error) return "Unavailable";
    if (!rowList.length) return "No rows";
    if (Number(queue?.invalid_row_count || 0) > 0 || rowList.some((row) => String(row?.status || "").toLowerCase() === "invalid")) return "Snapshot review";
    if (Number(queue?.priority_visible_count || 0) > 0) return "Priority visible";
    return "Loaded";
  }

  function queueBreakdownLines(queue, rows) {
    const payload = queue || {};
    const rowList = Array.isArray(rows) ? rows : [];
    const lines = [
      `Rows loaded: ${rowList.length}`,
      queueHiddenSidecarLine(payload),
      queueFreshnessLine("Snapshot file age", payload.snapshot_file_age_text, payload.snapshot_file_freshness_status, payload.snapshot_file_mtime_utc),
      queueFreshnessLine("Produced age", payload.produced_age_text, payload.produced_freshness_status),
      `Runnable rows: ${queuePayloadRunnableCount(payload, rowList)}`,
      `Visible size: ${payload.total_visible_size_text || "0.00 GB"}`,
      `Invalid snapshot rows: ${payload.invalid_row_count || 0}`,
      `Visible priority rows: ${payload.priority_visible_count || 0}`,
      `Snapshot priority count: ${payload.priority_count || 0}`,
      `Routes: ${queueFormatCounts(payload.route_counts)}`,
      `Route reasons: ${queueFormatCounts(payload.route_reason_counts)}`,
      `Operator statuses: ${queueFormatCounts(payload.operator_status_counts)}`,
      `Operator severities: ${queueFormatCounts(payload.operator_severity_counts)}`,
      `Phases: ${queueFormatCounts(payload.phase_counts)}`,
      `Media types: ${queueFormatCounts(payload.media_type_counts)}`,
      `Seasons: ${queueFormatCounts(payload.season_counts)}`,
      `Priority reasons: ${queueFormatCounts(payload.priority_reason_counts)}`,
      `Source roots: ${queueFormatCounts(payload.source_root_counts)}`,
      `Visible blocked reason codes: ${queueFormatCounts(payload.blocked_reason_code_counts)}`,
      `Visible blocked reasons: ${queueFormatCounts(payload.blocked_reason_counts)}`,
      `Runtime deferred checks: ${queueFormatCounts(payload.runtime_check_code_counts)}`,
      `Runtime outcomes: ${queueFormatCounts(payload.runtime_outcome_status_counts)}`,
      `Runtime outcome errors: ${queueFormatCounts(payload.runtime_outcome_error_code_counts)}`,
      `Runtime outcome freshness: ${queueFormatCounts(payload.runtime_outcome_freshness_counts)}`,
      `Excluded reasons: ${queueFormatCounts(payload.excluded_reason_counts)}`,
      `Excluded media types: ${queueFormatCounts(payload.excluded_media_type_counts)}`,
    ];
    if (payload.invalid_row_count) {
      lines.push("", "Operator note: invalid snapshot rows are ignored by processing until the backend can parse them. Refresh the queue preview before launching unattended work.");
    } else {
      lines.push("", "Operator note: this is a read-only snapshot breakdown. Launch and queue mutation remain backend-owned.");
    }
    return lines;
  }

  function renderQueueBreakdown(queue, rows) {
    const rowList = Array.isArray(rows) ? rows : [];
    setText("queue-breakdown-status", queueBreakdownStatus(queue || {}, rowList));
    setText("queue-breakdown", queueBreakdownLines(queue || {}, rowList).join("\n"));
  }

  function queueRuntimeStatus(queue, rows) {
    const payload = queue || {};
    const rowList = Array.isArray(rows) ? rows : [];
    if (payload.error) return "Unavailable";
    if (!payload.runtime_outcome_source) return "No event source";
    if (payload.runtime_outcome_warning) return "History warning";
    if (!Number(payload.runtime_outcome_event_count || 0)) return "No recent events";
    if (!Number(payload.runtime_outcome_match_count || 0)) return rowList.length ? "No row matches" : "No rows";
    const freshness = payload.runtime_outcome_freshness_counts || {};
    if (Number(freshness.stale || 0) > 0) return "Stale matches";
    const statuses = payload.runtime_outcome_status_counts || {};
    const failed = Object.entries(statuses).some(([key, count]) => {
      const text = String(key || "").toLowerCase();
      return Number(count || 0) > 0 && (text.includes("fail") || text === "skipped" || text === "stopped");
    });
    return failed ? "Review history" : "Matched";
  }

  function queueRuntimeLines(queue, rows) {
    const payload = queue || {};
    const rowList = Array.isArray(rows) ? rows : [];
    const lines = [
      `Pipeline event source: ${payload.runtime_outcome_source || "(not configured)"}`,
      `Recent events read: ${payload.runtime_outcome_event_count || 0}`,
      `Visible queue rows: ${rowList.length}`,
      `Rows with exact source-path runtime history: ${payload.runtime_outcome_match_count || 0}`,
      `Outcome statuses: ${queueFormatCounts(payload.runtime_outcome_status_counts)}`,
      `Outcome event types: ${queueFormatCounts(payload.runtime_outcome_event_type_counts)}`,
      `Outcome error codes: ${queueFormatCounts(payload.runtime_outcome_error_code_counts)}`,
      `Outcome freshness: ${queueFormatCounts(payload.runtime_outcome_freshness_counts)}`,
    ];
    if (payload.runtime_outcome_warning) {
      lines.push("", `Warning: ${payload.runtime_outcome_warning}`);
    }
    const stale = Number((payload.runtime_outcome_freshness_counts || {}).stale || 0);
    if (stale > 0) {
      lines.push("", "Stale history is shown only as context. Refresh Queue and inspect recent run logs before acting on old outcomes.");
    }
    if (!Number(payload.runtime_outcome_event_count || 0)) {
      lines.push("", "No recent pipeline completion/failure events were available in the bounded event tail.");
    } else if (!Number(payload.runtime_outcome_match_count || 0)) {
      lines.push("", "No visible row matched recent runtime history. Matching is exact source-path identity only to avoid misleading fuzzy correlations.");
    } else {
      lines.push("", "Select a queue row to inspect the matching runtime status, error code, reason, publish state, and output path.");
    }
    lines.push("Mutation guardrail: runtime history is read-only context; rerun, completed reconciliation, and queue mutation remain backend-owned.");
    return lines;
  }

  function renderQueueRuntime(queue, rows) {
    const rowList = Array.isArray(rows) ? rows : [];
    setText("queue-runtime-status", queueRuntimeStatus(queue || {}, rowList));
    setText("queue-runtime", queueRuntimeLines(queue || {}, rowList).join("\n"));
  }

  function queueValidationStatus(queue, rows) {
    const payload = queue || {};
    const rowList = Array.isArray(rows) ? rows : [];
    if (payload.error) return "Unavailable";
    if (queueSnapshotIsStale(payload)) return "Refresh first";
    if (Number(payload.invalid_row_count || 0) > 0 || Number(payload.blocked_row_count || 0) > 0) return "Review rows";
    if (payload.runtime_outcome_warning) return "History warning";
    if (Number((payload.runtime_outcome_freshness_counts || {}).stale || 0) > 0) return "Stale history";
    if (!rowList.length && Number(payload.excluded_row_count || 0) > 0) return "Filtered";
    if (!rowList.length) return "Empty";
    return "Trustworthy";
  }

  function queueValidationChecklistLines(queue, rows) {
    const payload = queue || {};
    const rowList = Array.isArray(rows) ? rows : [];
    const warnings = Array.isArray(payload.warnings) ? payload.warnings.filter(Boolean) : [];
    if (payload.error) {
      return [
        "Validation state: queue payload is unavailable.",
        `Error: ${payload.error}`,
        "Operator action: open Diagnostics > Queue Snapshot, Run Logs, and Last Stderr before launching or reprocessing.",
        "Mutation guardrail: this checklist is read-only and does not reconcile completed state.",
      ];
    }
    const staleSnapshot = queueSnapshotIsStale(payload);
    const runtimeFreshness = payload.runtime_outcome_freshness_counts || {};
    const runtimeErrors = payload.runtime_outcome_error_code_counts || {};
    const lines = [
      "Real-media validation checklist:",
      `Queue snapshot fresh enough: ${staleSnapshot ? "no - refresh before launch" : "yes"}`,
      `Runnable rows visible: ${rowList.length}`,
      queueHiddenSidecarLine(payload),
      `Excluded source rows: ${payload.excluded_row_count || 0}${payload.excluded_rows_truncated ? " (truncated)" : ""}`,
      `Completed/blocked exclusions: ${payload.completed_excluded_count || 0}`,
      `Visible blocked rows: ${payload.blocked_row_count || 0}`,
      `Invalid snapshot rows: ${payload.invalid_row_count || 0}`,
      `Runtime checks deferred: ${payload.runtime_check_deferred_count || 0}`,
      `Runtime history matched rows: ${payload.runtime_outcome_match_count || 0}`,
      `Runtime freshness: ${queueFormatCounts(runtimeFreshness)}`,
      `Runtime error codes: ${queueFormatCounts(runtimeErrors)}`,
      `Warnings: ${warnings.length}`,
    ];
    lines.push("");
    if (staleSnapshot) {
      lines.push("Operator action: refresh queue preview before launch. Stale snapshots are common after files move, complete, or are still being copied.");
    } else if (Number(payload.invalid_row_count || 0) > 0 || Number(payload.blocked_row_count || 0) > 0) {
      lines.push("Operator action: filter for blocked/invalid rows, select them, and inspect route evidence before launching a broad batch.");
    } else if (!rowList.length && Number(payload.excluded_row_count || 0) > 0) {
      lines.push("Operator action: inspect Excluded Source Rows. Empty queue with exclusions usually means completed history, failure markers, or processed-state filtering is active.");
    } else if (payload.runtime_outcome_warning || Number(runtimeFreshness.stale || 0) > 0) {
      lines.push("Operator action: treat runtime history as context only. Open Run Logs before trusting stale or warning outcome data.");
    } else if (!rowList.length) {
      lines.push("Operator action: verify source roots, file extensions, completed exclusions, and source stability before assuming media was missed.");
    } else if (warnings.length) {
      lines.push("Operator action: review warning text and selected-row guidance before Launch.");
    } else {
      lines.push("Operator action: queue preview is internally consistent. Launch remains schedule-gated and backend-owned.");
    }
    lines.push("Mutation guardrail: this checklist does not launch, remove completed markers, rewrite queue snapshots, or mutate source/output files.");
    return lines;
  }

  function renderQueueValidation(queue, rows) {
    const rowList = Array.isArray(rows) ? rows : [];
    setText("queue-validation-status", queueValidationStatus(queue || {}, rowList));
    setText("queue-validation", queueValidationChecklistLines(queue || {}, rowList).join("\n"));
  }

  function queueCollisionStatus(queue, rows) {
    const payload = queue || {};
    if (payload.error) return "Unavailable";
    return payload.completed_collision_status || (Array.isArray(rows) && rows.length ? "Loaded" : "No rows");
  }

  function queueCollisionLines(queue, rows) {
    const payload = queue || {};
    const lines = Array.isArray(payload.completed_collision_lines) ? [...payload.completed_collision_lines] : [];
    if (!lines.length) {
      const rowList = Array.isArray(rows) ? rows : [];
      lines.push(
        `Source candidates: ${payload.source_count_total || 0}`,
        `Runnable rows: ${queuePayloadRunnableCount(payload, rowList)}`,
        `Completed/blocked exclusions: ${payload.completed_excluded_count || 0}`,
        "Row-level excluded-file detail: unavailable in the current queue snapshot contract."
      );
    }
    const flags = Array.isArray(payload.completed_collision_flags) ? payload.completed_collision_flags.join(", ") : "";
    return [
      `Status: ${payload.completed_collision_status || "unknown"}`,
      `Severity: ${payload.completed_collision_severity || "unknown"}`,
      payload.completed_collision_guidance ? `Next step: ${payload.completed_collision_guidance}` : "",
      flags ? `Risk flags: ${flags}` : "",
      "",
      ...lines,
    ].filter((line) => line !== "");
  }

  function renderQueueCollision(queue, rows) {
    const rowList = Array.isArray(rows) ? rows : [];
    setText("queue-collision-status", queueCollisionStatus(queue || {}, rowList));
    setText("queue-collision", queueCollisionLines(queue || {}, rowList).join("\n"));
  }

  function queueExcludedStatus(queue) {
    const payload = queue || {};
    if (payload.error) return "Unavailable";
    if (!payload.completed_collision_row_level_available) return "Unavailable";
    const total = Number(payload.excluded_row_count || 0);
    if (!total) return "No excluded rows";
    return payload.excluded_rows_truncated ? "Truncated detail" : "Loaded";
  }

  function queueExcludedSummaryLines(queue) {
    const payload = queue || {};
    const rows = Array.isArray(payload.excluded_rows) ? payload.excluded_rows : [];
    if (!payload.completed_collision_row_level_available) {
      return [
        "Row-level excluded source detail is not available in this queue snapshot.",
        "Next step: refresh Queue after the updated backend has emitted a new snapshot.",
        "Mutation guardrail: this panel is read-only and never reconciles completed state from the frontend.",
      ];
    }
    const lines = [
      `Excluded rows reported: ${payload.excluded_row_count || rows.length || 0}`,
      `Rows shown: ${rows.length}`,
      `Snapshot row limit: ${payload.excluded_row_limit || "not reported"}`,
      `Truncated: ${payload.excluded_rows_truncated ? "yes" : "no"}`,
      `Reasons: ${queueFormatCounts(payload.excluded_reason_counts)}`,
      `Media types: ${queueFormatCounts(payload.excluded_media_type_counts)}`,
    ];
    if (!rows.length) {
      lines.push("", "No excluded source rows were reported. If runnable rows are missing, inspect source filters, schedule state, and recent run logs.");
    } else {
      lines.push("", "These rows were filtered before the runnable queue. Already-processed rows usually mean completed history, sidecar state, or pending-publish state matched the source.");
    }
    if (payload.excluded_rows_truncated) {
      lines.push("Refresh after narrowing the source folder if you need exact detail beyond the bounded snapshot limit.");
    }
    lines.push("Mutation guardrail: completed reconciliation, rerun, and queue mutation remain backend-owned.");
    return lines;
  }

  function renderQueueExcluded(queue) {
    const payload = queue || {};
    const rows = Array.isArray(payload.excluded_rows) ? payload.excluded_rows : [];
    setText("queue-excluded-status", queueExcludedStatus(payload));
    setText("queue-excluded-summary", queueExcludedSummaryLines(payload).join("\n"));
    const tbody = byId("queue-excluded-rows");
    if (!rows.length) {
      clearRows(tbody, 5, payload.completed_collision_row_level_available ? "No excluded source rows reported." : "Excluded row detail is unavailable until a fresh queue snapshot is emitted.");
      updateTableStatusLegend("queue-excluded-table-legend", tbody, "Excluded rows");
      return;
    }
    tbody.replaceChildren();
    rows.slice(0, 100).forEach((item) => {
      const row = document.createElement("tr");
      const key = queueExcludedRowKey(item);
      row.dataset.rowKey = key;
      appendCells(row, [
        item.source_order || "",
        item.media_type || item.media_kind || "",
        item.reason_code || "excluded",
        item.display_name || item.relative_path || "",
        item.source_path || "",
      ]);
      makeRowSelectable(row, () => selectQueueExcludedRow(item), {
        selected: Boolean(key && key === getSelectedQueueExcludedRowKey()),
        label: `Excluded source ${item.display_name || item.relative_path || item.source_path || ""}`,
      });
      tbody.appendChild(row);
    });
    updateTableStatusLegend("queue-excluded-table-legend", tbody, "Excluded rows");
  }

  async function requestQueueDiagnosticsAction(action) {
    const target = String(action?.target || "").trim();
    if (!target) return;
    if (action.kind === "tail") {
      if (typeof requestDiagnosticsTail === "function") {
        await requestDiagnosticsTail(target);
        setText("queue-diagnostics-status", `Read requested: ${target}`);
      } else {
        setText("queue-diagnostics-status", "Diagnostics tail reader is not loaded.");
      }
      return;
    }
    if (typeof requestDiagnosticsOpen === "function") {
      await requestDiagnosticsOpen(target);
      setText("queue-diagnostics-status", `Open requested: ${target}`);
    } else {
      setText("queue-diagnostics-status", "Diagnostics open command is not loaded.");
    }
  }

  function renderQueueRows() {
    const filterText = byId("queue-filter")?.value || "";
    const statusFilter = byId("queue-status-filter")?.value || "all";
    const investigationFilter = byId("queue-investigation-filter")?.value || "all";
    const textRows = filterRows(lastQueueRows, filterText, QUEUE_FILTER_FIELDS);
    const statusRows = typeof filterRowsByStatus === "function" ? filterRowsByStatus(textRows, statusFilter, queueDisplayRowStatus) : textRows;
    const rows = typeof filterRowsByInvestigation === "function" ? filterRowsByInvestigation(statusRows, investigationFilter, queueMatchesInvestigationFilter) : statusRows;
    const renderLimit = 250;
    const renderedCount = Math.min(rows.length, renderLimit);
    setText(
      "queue-status",
      rows.length > renderLimit
        ? `${renderedCount} shown / ${rows.length} filtered / ${lastQueueRows.length} rows`
        : `${rows.length} / ${lastQueueRows.length} row${lastQueueRows.length === 1 ? "" : "s"}`
    );
    const buildFilterSummary = typeof filterResultSummaryLines === "function"
      ? filterResultSummaryLines
      : window.mediaPipelineDom?.filterResultSummaryLines;
    if (typeof buildFilterSummary === "function") {
      setText("queue-filter-summary", buildFilterSummary({
        label: "Queue filter",
        allRows: lastQueueRows,
        visibleRows: rows,
        filterText,
        statusFilter,
        investigationFilter,
        investigationLabel: queueInvestigationFilterLabel(investigationFilter),
        statusOf: queueDisplayRowStatus,
        limit: 250,
        decisionName: "launch",
        guardrail: "Mutation guardrail: filtering the Queue table does not change backend launch scope, queue state, source files, or processing commands.",
      }).join("\n"));
    }
    const tbody = byId("queue-rows");
    if (!rows.length) {
      clearRows(tbody, 9, lastQueueRows.length ? "No queue rows match the filter." : lastQueueEmptyMessage);
      updateTableStatusLegend("queue-table-legend", tbody, "Queue rows");
      if (getSelectedQueueRowKey()) renderQueueDetail(getSelectedQueueRow());
      renderQueueBackendLaunchScopePreview(lastQueuePayload, lastQueueRows, typeof getCommandHistory === "function" ? getCommandHistory() : []);
      renderQueueLaunchDecisionChecklist(lastQueuePayload, lastQueueRows, typeof getCommandHistory === "function" ? getCommandHistory() : []);
      return;
    }
    tbody.replaceChildren();
    renderQueueTableRows({
      rows: rows.slice(0, renderLimit),
      tbody,
      selectedQueueRowKey: getSelectedQueueRowKey(),
    });
    updateTableStatusLegend("queue-table-legend", tbody, "Queue rows");
    if (getSelectedQueueRowKey()) renderQueueDetail(getSelectedQueueRow());
    renderQueueBackendLaunchScopePreview(lastQueuePayload, lastQueueRows, typeof getCommandHistory === "function" ? getCommandHistory() : []);
    renderQueueLaunchDecisionChecklist(lastQueuePayload, lastQueueRows, typeof getCommandHistory === "function" ? getCommandHistory() : []);
  }

  function resetQueueFilters() {
    const filter = byId("queue-filter");
    const status = byId("queue-status-filter");
    const investigation = byId("queue-investigation-filter");
    if (filter) filter.value = "";
    if (status) status.value = "all";
    if (investigation) investigation.value = "all";
    renderQueueRows();
    setText("queue-open-status", "Queue display filters cleared. Backend launch scope is unchanged.");
  }

  async function requestQueueScan() {
    if (queueScanInFlight) {
      const result = {
        command: "queue.scan",
        ok: false,
        severity: "warning",
        message: "A Queue source scan request is already being submitted.",
      };
      if (typeof appendCommandResult === "function") appendCommandResult(result);
      setText("queue-open-status", result.message);
      return;
    }
    queueScanInFlight = true;
    window.mediaPipelineAppRefresh?.renderQueueRefreshInProgress?.();
    setText("queue-source-inventory", [
      "Queue source scan requested.",
      "Waiting for backend source inventory and queue curation status.",
      "Mutation guardrail: this command does not process, rename, move, delete, publish, drain, or mutate source media.",
    ].join("\n"));
    try {
      const result = await apiPost("/api/queue/scan", {
        mode: "inventory_then_curate",
        force: true,
        scope: "all",
        reason: "operator_requested_queue_scan",
      }, { timeoutMs: 10000 });
      if (typeof appendCommandResult === "function") appendCommandResult(result);
      setText("queue-open-status", result.message || "Queue source scan command accepted.");
      if (typeof refreshAll === "function") {
        await refreshAll({ queueRefresh: true });
      } else {
        setText("queue-filter-summary", "Queue source scan started, but refresh wiring is not loaded.");
      }
      scheduleQueueScanPoll();
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      const result = {
        command: "queue.scan",
        ok: false,
        severity: "error",
        message: `Queue source scan request failed: ${message}`,
        errors: [message],
      };
      if (typeof appendCommandResult === "function") appendCommandResult(result);
      setText("queue-open-status", result.message);
      setText("queue-source-inventory", [
        result.message,
        "Safe next step: inspect Diagnostics and backend command history before trying again.",
      ].join("\n"));
    } finally {
      queueScanInFlight = false;
      window.mediaPipelineAppRefresh?.setQueueRefreshButtonBusy?.(queueScanIsRunning());
    }
  }

  /**
   * Public namespace for the Queue page module.
   * Prefer this namespace from new code; flat window.* exports are transitional compatibility aliases when present.
   */
  window.mediaPipelineQueueView = {
    renderQueue,
    renderQueueRows,
    resetQueueFilters,
    renderQueueDetail,
    renderQueueProgress,
    queueProgressPayload,
    queueProgressBars,
    queueProgressStatus,
    queueProgressSummaryLines,
    renderQueueSummary,
    renderQueueReadiness,
    renderQueueBreakdown,
    renderQueueRuntime,
    renderQueueValidation,
    renderQueueWorkflow,
    renderQueueBackendLaunchScopePreview,
    queueBackendLaunchScopeRows,
    queueBackendLaunchScopeStatus,
    queueBackendLaunchScopeSummaryLines,
    renderQueueLaunchDecisionChecklist,
    renderQueueReviewBoard,
    renderQueueCollision,
    renderQueueExcluded,
    renderQueueExcludedDetail,
    queueReadinessStatus,
    queueReadinessLines,
    queueBreakdownStatus,
    queueBreakdownLines,
    queueRuntimeStatus,
    queueRuntimeLines,
    queueValidationStatus,
    queueValidationChecklistLines,
    queueWorkflowStatus,
    queueWorkflowLines,
    queueLaunchDecisionRows,
    queueLaunchDecisionStatus,
    queueLaunchDecisionStatusState,
    queueLaunchDecisionSummaryLines,
    queueLaunchDecisionDetailLines,
    queueLaunchDecisionPostureStatus,
    queueLaunchDecisionLatestCommand,
    queueCurrentFilterScope,
    queueFilterScopePosture,
    queueFilterScopeEvidence,
    queueFilterScopeAction,
    queueFilterScopeDetailLines,
    queueLaunchBackendPreflightPayload,
    queueLaunchBackendPreflightCheckpoint,
    isQueueLaunchCommand,
    queueReviewStatus,
    queueReviewBoardLines,
    queueReviewRows,
    renderQueueReviewDigest,
    queueReviewDigestStatus,
    queueReviewDigestAction,
    queueListText,
    queueSelectedOpenTargetLines,
    queueRowReviewChecklistLines,
    queueRowIssueDigestLines,
    queueSelectedQuickSignalLines,
    queueSelectedAtAGlanceState,
    queueSelectedAtAGlanceStatus,
    queueSelectedAtAGlanceLines,
    renderQueueSelectedAtAGlance,
    queueFilterVisibilityLines,
    queueFocusedInvestigationLabels,
    queueInvestigationSignalLines,
    queueRealMediaTraceLines,
    queueRowTrustSummaryLines,
    queueDiagnosticsActionsForRow,
    queueDiagnosticsGuidanceLines,
    renderQueueDiagnosticsLinks,
    requestQueueDiagnosticsAction,
    queueCollisionStatus,
    queueCollisionLines,
    queueExcludedStatus,
    queueExcludedSummaryLines,
    queueExcludedRowKey,
    selectQueueExcludedRow,
    getSelectedQueueExcludedRow,
    queueFormatCounts,
    queueFreshnessLine,
    queueSnapshotIsStale,
    queueEmptyStateMessage,
    selectQueueRow,
    getSelectedQueueRow,
    getLastQueuePayload,
    getLastQueueRows,
    queueRowKey,
    setQueueOpenBusy,
    rejectQueueOpenWhileBusy,
    requestQueueOpen,
    requestQueueScan,
    queueScanIsRunning,
    queueScanStatusLines,
    queueSourceInventoryLines,
    renderQueueScanArtifacts,
    isQueueOpenCommand,
    queueOpenHistoryLine,
    renderQueueOpenHistory,
  };
  window.renderQueue = renderQueue;
  window.resetQueueFilters = resetQueueFilters;
  window.renderQueueDetail = renderQueueDetail;
  window.renderQueueProgress = renderQueueProgress;
  window.queueProgressPayload = queueProgressPayload;
  window.queueProgressBars = queueProgressBars;
  window.queueProgressStatus = queueProgressStatus;
  window.queueProgressSummaryLines = queueProgressSummaryLines;
  window.renderQueueSummary = renderQueueSummary;
  window.renderQueueReadiness = renderQueueReadiness;
  window.renderQueueWorkflow = renderQueueWorkflow;
  window.renderQueueBackendLaunchScopePreview = renderQueueBackendLaunchScopePreview;
  window.queueBackendLaunchScopeRows = queueBackendLaunchScopeRows;
  window.queueBackendLaunchScopeStatus = queueBackendLaunchScopeStatus;
  window.queueBackendLaunchScopeSummaryLines = queueBackendLaunchScopeSummaryLines;
  window.renderQueueLaunchDecisionChecklist = renderQueueLaunchDecisionChecklist;
  window.renderQueueReviewBoard = renderQueueReviewBoard;
  window.renderQueueExcludedDetail = renderQueueExcludedDetail;
  window.queueReadinessStatus = queueReadinessStatus;
  window.queueReadinessLines = queueReadinessLines;
  window.queueRuntimeLines = queueRuntimeLines;
  window.queueValidationStatus = queueValidationStatus;
  window.queueWorkflowStatus = queueWorkflowStatus;
  window.queueWorkflowLines = queueWorkflowLines;
  window.queueLaunchDecisionRows = queueLaunchDecisionRows;
  window.queueLaunchDecisionStatus = queueLaunchDecisionStatus;
  window.queueLaunchDecisionStatusState = queueLaunchDecisionStatusState;
  window.queueLaunchDecisionSummaryLines = queueLaunchDecisionSummaryLines;
  window.queueLaunchDecisionDetailLines = queueLaunchDecisionDetailLines;
  window.queueLaunchDecisionPostureStatus = queueLaunchDecisionPostureStatus;
  window.queueLaunchDecisionLatestCommand = queueLaunchDecisionLatestCommand;
  window.queueCurrentFilterScope = queueCurrentFilterScope;
  window.queueFilterScopePosture = queueFilterScopePosture;
  window.queueFilterScopeEvidence = queueFilterScopeEvidence;
  window.queueFilterScopeAction = queueFilterScopeAction;
  window.queueFilterScopeDetailLines = queueFilterScopeDetailLines;
  window.queueLaunchBackendPreflightPayload = queueLaunchBackendPreflightPayload;
  window.queueLaunchBackendPreflightCheckpoint = queueLaunchBackendPreflightCheckpoint;
  window.isQueueLaunchCommand = isQueueLaunchCommand;
  window.queueReviewStatus = queueReviewStatus;
  window.queueReviewBoardLines = queueReviewBoardLines;
  window.queueReviewRows = queueReviewRows;
  window.renderQueueReviewDigest = renderQueueReviewDigest;
  window.queueReviewDigestStatus = queueReviewDigestStatus;
  window.queueReviewDigestAction = queueReviewDigestAction;
  window.queueListText = queueListText;
  window.queueSelectedOpenTargetLines = queueSelectedOpenTargetLines;
  window.queueRowReviewChecklistLines = queueRowReviewChecklistLines;
  window.queueRowIssueDigestLines = queueRowIssueDigestLines;
  window.queueSelectedQuickSignalLines = queueSelectedQuickSignalLines;
  window.queueSelectedAtAGlanceState = queueSelectedAtAGlanceState;
  window.queueSelectedAtAGlanceStatus = queueSelectedAtAGlanceStatus;
  window.queueSelectedAtAGlanceLines = queueSelectedAtAGlanceLines;
  window.renderQueueSelectedAtAGlance = renderQueueSelectedAtAGlance;
  window.queueFilterVisibilityLines = queueFilterVisibilityLines;
  window.queueFocusedInvestigationLabels = queueFocusedInvestigationLabels;
  window.queueInvestigationSignalLines = queueInvestigationSignalLines;
  window.queueRealMediaTraceLines = queueRealMediaTraceLines;
  window.queueRowTrustSummaryLines = queueRowTrustSummaryLines;
  window.queueDiagnosticsActionsForRow = queueDiagnosticsActionsForRow;
  window.queueDiagnosticsGuidanceLines = queueDiagnosticsGuidanceLines;
  window.renderQueueDiagnosticsLinks = renderQueueDiagnosticsLinks;
  window.requestQueueDiagnosticsAction = requestQueueDiagnosticsAction;
  window.queueCollisionLines = queueCollisionLines;
  window.queueFormatCounts = queueFormatCounts;
  window.queueFreshnessLine = queueFreshnessLine;
  window.queueSnapshotIsStale = queueSnapshotIsStale;
  window.selectQueueRow = selectQueueRow;
  window.getSelectedQueueRow = getSelectedQueueRow;
  window.getLastQueuePayload = getLastQueuePayload;
  window.getLastQueueRows = getLastQueueRows;
  window.queueRowKey = queueRowKey;
  window.requestQueueOpen = requestQueueOpen;
  window.requestQueueScan = requestQueueScan;
  window.queueScanIsRunning = queueScanIsRunning;
  window.queueScanStatusLines = queueScanStatusLines;
  window.queueSourceInventoryLines = queueSourceInventoryLines;
  window.renderQueueScanArtifacts = renderQueueScanArtifacts;
  window.isQueueOpenCommand = isQueueOpenCommand;
  window.queueOpenHistoryLine = queueOpenHistoryLine;
  window.renderQueueOpenHistory = renderQueueOpenHistory;

  // ===========================================================================
  // S60 — Queue Priority Toolbar
  // ===========================================================================

  function queuePriorityBadgeLabel(level) {
    const labels = { high: "⬆ HIGH", low: "⬇ LOW", hold: "⏸ HOLD", fs: "★ FS" };
    return labels[level] || "";
  }

  async function sendQueuePriority(path, level, reason) {
    if (!path) {
      setText("queue-priority-status", "No row selected — select a queue row first.");
      return;
    }
    setText("queue-priority-status", "Sending…");
    try {
      const result = await apiPost("/api/queue/priority", { path, level, reason });
      const msg = result && result.message ? result.message : `Priority set to '${level}'.`;
      setText("queue-priority-status", msg);
      if (typeof appendCommandResult === "function") appendCommandResult({ command: "queue.priority", ok: Boolean(result && result.ok), severity: result && result.ok ? "ok" : "error", message: msg });
      if (result && result.ok && typeof refreshAll === "function") await refreshAll();
    } catch (err) {
      setText("queue-priority-status", `Priority request failed: ${err}`);
    }
  }

  async function sendQueuePriorityBulk(items, description) {
    if (!items || !items.length) {
      setText("queue-priority-status", "No rows to update.");
      return;
    }
    setText("queue-priority-status", `Updating ${items.length} row(s)…`);
    try {
      const result = await apiPost("/api/queue/priority", { items });
      const msg = result && result.message ? result.message : description || "Bulk priority updated.";
      setText("queue-priority-status", msg);
      if (typeof appendCommandResult === "function") appendCommandResult({ command: "queue.priority", ok: Boolean(result && result.ok), severity: result && result.ok ? "ok" : "error", message: msg });
      if (result && result.ok && typeof refreshAll === "function") await refreshAll();
    } catch (err) {
      setText("queue-priority-status", `Bulk priority request failed: ${err}`);
    }
  }

  async function clearQueuePriorityManifest() {
    setText("queue-priority-status", "Clearing entire priority manifest...");
    try {
      const result = await apiPost("/api/queue/priority", { clear_all: true });
      const msg = result && result.message ? result.message : "All priority manifest entries cleared.";
      setText("queue-priority-status", msg);
      if (typeof appendCommandResult === "function") appendCommandResult({ command: "queue.priority", ok: Boolean(result && result.ok), severity: result && result.ok ? "ok" : "error", message: msg });
      if (result && result.ok && typeof refreshAll === "function") await refreshAll();
    } catch (err) {
      setText("queue-priority-status", `Priority manifest clear failed: ${err}`);
    }
  }

  function initQueuePriorityToolbar() {
    function getPath() {
      const row = getSelectedQueueRow();
      return row ? (row.source_path || row.relative_path || "") : "";
    }

    const wire = (id, handler) => {
      const btn = byId(id);
      if (btn) btn.addEventListener("click", handler);
    };

    wire("queue-priority-promote-btn", () => sendQueuePriority(getPath(), "high", "Operator promoted via toolbar"));
    wire("queue-priority-normal-btn",  () => sendQueuePriority(getPath(), "normal", ""));
    wire("queue-priority-low-btn",     () => sendQueuePriority(getPath(), "low", "Operator demoted via toolbar"));
    wire("queue-priority-hold-btn",    () => sendQueuePriority(getPath(), "hold", "Operator hold via toolbar"));
    const refreshBtn = typeof document.querySelector === "function" ? document.querySelector("[data-queue-refresh-button]") : null;
    if (refreshBtn) refreshBtn.addEventListener("click", () => requestQueueScan());

    wire("queue-priority-promote-movies-btn", () => {
      const items = lastQueueRows
        .filter((r) => String(r.media_type || "").toLowerCase() === "movie")
        .map((r) => ({ path: r.source_path || r.relative_path || "", level: "high", reason: "Bulk promote all movies" }))
        .filter((i) => i.path);
      sendQueuePriorityBulk(items, `Promoted ${items.length} Movie row(s) to High.`);
    });

    wire("queue-priority-promote-tv-btn", () => {
      const items = lastQueueRows
        .filter((r) => String(r.media_type || "").toLowerCase() === "tv")
        .map((r) => ({ path: r.source_path || r.relative_path || "", level: "high", reason: "Bulk promote all TV" }))
        .filter((i) => i.path);
      sendQueuePriorityBulk(items, `Promoted ${items.length} TV row(s) to High.`);
    });

    wire("queue-priority-clear-all-btn", clearQueuePriorityManifest);
  }

  // Wire toolbar on DOMContentLoaded (or immediately if already loaded)
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initQueuePriorityToolbar);
  } else {
    initQueuePriorityToolbar();
  }


  // ===========================================================================
  // S70 — Queue Ordering Strategy Selector
  // ===========================================================================

  // Strategy names must match VALID_STRATEGIES in app/queue/strategy.py
  // and $script:ValidQueueStrategies in QueuePlan.ps1.
  const QUEUE_STRATEGIES = [
    "Standard",
    "FreshestFirst",
    "ShowComplete",
    "RoundRobin",
    "DeadlineAware",
    "SmallFirst",
    "LargeFirst",
    "ManualOrder",
  ];

  /**
   * Fetch the currently active strategy from the API and update the
   * <select> to reflect it.  Called on queue page show and after a
   * successful strategy change.
   */
  async function loadQueueStrategy() {
    const sel = document.getElementById("queue-strategy-select");
    if (!sel) return;
    try {
      const data = await apiGet(QUEUE_STRATEGY_ROUTE);
      const strategy = data && data.strategy ? String(data.strategy) : "Standard";
      if (QUEUE_STRATEGIES.includes(strategy)) {
        sel.value = strategy;
      }
      // Show source hint if strategy came from UI override vs default
      const source = data && data.source ? String(data.source) : "default";
      const statusEl = document.getElementById("queue-strategy-status");
      if (statusEl) {
        statusEl.textContent = source === "state_file"
          ? `Active strategy: ${strategy} (saved).`
          : `Active strategy: ${strategy} (config default).`;
      }
    } catch (_) {
      // Silently ignore — API may not be up yet
    }
  }

  /**
   * POST the selected strategy to the API and update the status line.
   * Also refreshes the queue snapshot so the sorted order is visible.
   */
  async function applyQueueStrategy() {
    const sel    = document.getElementById("queue-strategy-select");
    const status = document.getElementById("queue-strategy-status");
    if (!sel) return;

    const strategy = sel.value;
    if (!QUEUE_STRATEGIES.includes(strategy)) {
      if (status) status.textContent = `Unknown strategy: ${strategy}`;
      return;
    }

    if (status) status.textContent = "Saving strategy…";
    try {
      const payload = await apiPost("/api/queue/strategy", { strategy });
      if (payload && payload.ok) {
        if (status) {
          status.textContent = `Strategy set to "${strategy}". Takes effect on next queue build.`;
        }
        appendCommandResult(payload);
        // Reload the strategy display to confirm round-trip
        await loadQueueStrategy();
      } else {
        const msg = (payload && payload.message) ? payload.message : "Unknown error.";
        if (status) status.textContent = `Error: ${msg}`;
        if (payload) appendCommandResult(payload);
      }
    } catch (err) {
      if (status) status.textContent = `Error: ${err.message || err}`;
    }
  }

  function initQueueStrategySelector() {
    const applyBtn = document.getElementById("queue-strategy-apply-btn");
    if (applyBtn) {
      applyBtn.addEventListener("click", applyQueueStrategy);
    }
    // Populate the select with options that match VALID_STRATEGIES
    // (they are already hard-coded in index.html, so we just load current value)
    loadQueueStrategy();
  }

  // Wire on DOMContentLoaded
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initQueueStrategySelector);
  } else {
    initQueueStrategySelector();
  }

  // Reload strategy when the queue panel becomes visible.
  // showPage() in app.js toggles the "is-visible" class on [data-page-panel]
  // elements; we use a MutationObserver to catch that transition.
  (function wireQueuePanelVisibilityObserver() {
    const panel = document.querySelector('[data-page-panel="queue"]');
    if (!panel || typeof MutationObserver === "undefined") return;
    let wasVisible = panel.classList.contains("is-visible");
    new MutationObserver(function () {
      const isNowVisible = panel.classList.contains("is-visible");
      if (isNowVisible && !wasVisible) {
        loadQueueStrategy();
      }
      wasVisible = isNowVisible;
    }).observe(panel, { attributes: true, attributeFilter: ["class"] });
  })();

})();
