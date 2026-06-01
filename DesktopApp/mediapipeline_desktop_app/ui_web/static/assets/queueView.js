(function () {
  let lastQueueRows = [];
  let lastQueueExcludedRows = [];
  let lastQueueHiddenSidecarRows = [];
  let lastQueuePayload = {};
  let selectedQueueRowKey = "";
  let selectedQueueExcludedRowKey = "";
  let lastQueueEmptyMessage = "No queue rows available.";
  let queueOpenInFlight = false;
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

  const __queueReviewMod = window.__queueReviewModule || {};
  delete window.__queueReviewModule;
  const _queueReview = typeof __queueReviewMod.createQueueReviewModule === "function"
    ? __queueReviewMod.createQueueReviewModule({
      appendCells: typeof appendCells === "function" ? appendCells : window.appendCells,
      byId: typeof byId === "function" ? byId : window.byId,
      clearRows: typeof clearRows === "function" ? clearRows : window.clearRows,
      getSelectedQueueRowKey: () => selectedQueueRowKey,
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

  function setQueueOpenBusy(isBusy) {
    queueOpenInFlight = Boolean(isBusy);
    document.querySelectorAll("[data-open-queue], [data-open-queue-excluded]").forEach((button) => {
      button.disabled = queueOpenInFlight;
    });
  }

  function rejectQueueOpenWhileBusy() {
    if (!queueOpenInFlight) return false;
    const result = {
      command: "queue.open",
      ok: false,
      severity: "warning",
      message: "Another queue open command is already in progress.",
    };
    appendCommandResult(result);
    setText("queue-open-status", result.message);
    return true;
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
    if (selectedQueueRowKey && !rows.some((row) => queueRowKey(row) === selectedQueueRowKey)) {
      selectedQueueRowKey = "";
    }
    if (selectedQueueExcludedRowKey && !excludedRows.some((row) => queueExcludedRowKey(row) === selectedQueueExcludedRowKey)) {
      selectedQueueExcludedRowKey = "";
    }
    lastQueueEmptyMessage = queueEmptyStateMessage(displayQueue, rows);
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

  function queueSelectedOpenTargetLines(item) {
    if (!item) {
      return [
        "Backend selected open targets:",
        "Select a queue row to see which backend target keys are available for source inspection.",
      ];
    }
    return [
      "Backend selected open targets:",
      `Available open targets: ${queueListText(item.available_open_targets)}`,
      `Row key: ${item.row_key || queueRowKey(item) || ""}`,
      "Open boundary: Queue buttons send only row_key, row_scope, and target. The backend resolves source paths from the loaded queue snapshot.",
      "Mutation guardrail: opening a target does not launch, copy, rename, reorder, drop, rewrite, or mutate source/output files.",
    ];
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
      `Runnable rows: ${payload.runnable_count || rowList.length || 0}`,
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
        `Runnable rows: ${payload.runnable_count || rowList.length || 0}`,
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
        selected: Boolean(key && key === selectedQueueExcludedRowKey),
        label: `Excluded source ${item.display_name || item.relative_path || item.source_path || ""}`,
      });
      tbody.appendChild(row);
    });
    updateTableStatusLegend("queue-excluded-table-legend", tbody, "Excluded rows");
  }

  function queueRowKey(item) {
    if (item?.row_key) return String(item.row_key).toLocaleLowerCase();
    return [
      item?.source_path || "",
      item?.global_order || "",
      item?.queue_index || "",
      item?.route_name || "",
    ].join("\u001f").toLocaleLowerCase();
  }

  function getSelectedQueueRow() {
    if (!selectedQueueRowKey) return null;
    return lastQueueRows.find((row) => queueRowKey(row) === selectedQueueRowKey) || null;
  }

  function getLastQueuePayload() {
    return lastQueuePayload || {};
  }

  function getLastQueueRows() {
    return lastQueueRows.slice();
  }

  function queueExcludedRowKey(item) {
    if (item?.row_key) return String(item.row_key).toLocaleLowerCase();
    return [
      item?.source_path || "",
      item?.source_order || "",
      item?.reason_code || "",
    ].join("\u001f").toLocaleLowerCase();
  }

  function getSelectedQueueExcludedRow() {
    if (!selectedQueueExcludedRowKey) return null;
    return lastQueueExcludedRows.find((row) => queueExcludedRowKey(row) === selectedQueueExcludedRowKey) || null;
  }

  function selectQueueRow(item) {
    selectedQueueRowKey = queueRowKey(item);
    renderQueueDetail(item || null);
    setText("queue-open-status", "Selected queue row. Open commands use backend-selected paths from the queue snapshot.");
    renderQueueReviewDigest(lastQueuePayload, lastQueueRows);
    renderQueueBackendLaunchScopePreview(lastQueuePayload, lastQueueRows, typeof getCommandHistory === "function" ? getCommandHistory() : []);
    renderQueueLaunchDecisionChecklist(lastQueuePayload, lastQueueRows, typeof getCommandHistory === "function" ? getCommandHistory() : []);
    renderQueueRows();
  }

  function selectQueueExcludedRow(item) {
    selectedQueueExcludedRowKey = queueExcludedRowKey(item);
    renderQueueExcludedDetail(item || null);
    setText("queue-excluded-open-status", "Selected excluded source row. Open commands use backend-selected paths from the queue snapshot.");
    renderQueueExcluded(lastQueuePayload);
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
      if (selectedQueueRowKey) renderQueueDetail(getSelectedQueueRow());
      renderQueueBackendLaunchScopePreview(lastQueuePayload, lastQueueRows, typeof getCommandHistory === "function" ? getCommandHistory() : []);
      renderQueueLaunchDecisionChecklist(lastQueuePayload, lastQueueRows, typeof getCommandHistory === "function" ? getCommandHistory() : []);
      return;
    }
    tbody.replaceChildren();
    renderQueueTableRows({
      rows: rows.slice(0, renderLimit),
      tbody,
      selectedQueueRowKey,
    });
    updateTableStatusLegend("queue-table-legend", tbody, "Queue rows");
    if (selectedQueueRowKey) renderQueueDetail(getSelectedQueueRow());
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

  async function requestQueueOpen(target, rowScope = "runnable") {
    if (rejectQueueOpenWhileBusy()) return;
    const isExcluded = String(rowScope || "").toLowerCase() === "excluded";
    const row = isExcluded ? getSelectedQueueExcludedRow() : getSelectedQueueRow();
    const statusTarget = isExcluded ? "queue-excluded-open-status" : "queue-open-status";
    if (!row) {
      const result = {
        command: "queue.open",
        ok: false,
        severity: "warning",
        message: isExcluded ? "Select an excluded source row first." : "Select a queue row first.",
      };
      appendCommandResult(result);
      setText(statusTarget, result.message);
      return;
    }
    setQueueOpenBusy(true);
    setText(statusTarget, "Opening...");
    try {
      const result = await apiPost("/api/queue/open", {
        row_key: row.row_key || (isExcluded ? queueExcludedRowKey(row) : queueRowKey(row)),
        row_scope: isExcluded ? "excluded" : "runnable",
        target,
      });
      appendCommandResult(result);
      setText(statusTarget, result.message || "Open request sent.");
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      appendCommandResult({
        command: "queue.open",
        ok: false,
        severity: "error",
        message,
      });
      setText(statusTarget, `Open failed: ${message}`);
    } finally {
      setQueueOpenBusy(false);
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
    } catch (err) {
      setText("queue-priority-status", `Bulk priority request failed: ${err}`);
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
    if (refreshBtn) refreshBtn.addEventListener("click", () => (typeof refreshAll === "function" ? refreshAll() : setText("queue-filter-summary", "Refresh is unavailable until app refresh wiring is loaded.")));

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

    wire("queue-priority-clear-all-btn", () => {
      const items = lastQueueRows
        .map((r) => ({ path: r.source_path || r.relative_path || "", level: "normal", reason: "" }))
        .filter((i) => i.path);
      sendQueuePriorityBulk(items, `Cleared priority manifest for ${items.length} row(s).`);
    });
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

/* =============================================================================
   S80 — Per-File Settings Drawer  (Phase 3)
   Manages the slide-in drawer for per-file audio/subtitle overrides.
   API: GET/POST /api/queue/file-overrides
   ============================================================================= */
(function initFileSettingsDrawerModule() {
  const FILE_OVERRIDES_ROUTE = "/api/queue/file-overrides";
  const FILE_OVERRIDES_EFFECTIVE_ROUTE = "/api/queue/file-overrides/effective";
  const FILE_OVERRIDES_TRACKS_ROUTE = "/api/queue/file-overrides/tracks";
  const FILE_OVERRIDES_ROUTE_PREVIEW_ROUTE = "/api/queue/file-overrides/route-preview";
  const FILE_OVERRIDES_FOLDER_PREVIEW_ROUTE = "/api/queue/file-overrides/folder-preview";
  const FILE_OVERRIDES_FOLDER_RULE_ROUTE = "/api/queue/file-overrides/folder-rule";

  // Currently-open source path
  let foCurrentPath = "";
  let foCurrentItem = null;
  let fileSettingsDrawerTrigger = null;
  let foLastEffectivePayload = null;
  let foRoutePreviewTimer = null;
  let foExactTrackOverrideEntry = null;
  let foExactTrackWarnings = [];
  let foUnmatchedExactSelectors = emptyExactSelectorState();
  let foLastFolderPreviewPayload = null;
  let foLastFolderPreviewRequest = null;
  let foFolderRules = [];

  const DRAWER_FIELD_HINT_IDS = {
    audioKeepLanguages: "fo-audio-keep-langs-inherited",
    audioDropLanguages: "fo-audio-drop-langs-inherited",
    audioMaxChannels: "fo-audio-max-channels-inherited",
    audioPreferDefaultLanguage: "fo-audio-prefer-default-language-inherited",
    subtitleKeepLanguages: "fo-sub-keep-langs-inherited",
    subtitleDropLanguages: "fo-sub-drop-langs-inherited",
    subtitleStripAll: "fo-sub-strip-all-inherited",
    routeProfile: "fo-route-profile-inherited",
    videoContainer: "fo-video-container-inherited",
    videoCodec: "fo-video-codec-inherited",
    videoEncodePreset: "fo-video-encode-preset-inherited",
    videoEncodeLadder: "fo-video-encode-ladder-inherited",
    routingRouteThresholdMode: "fo-route-threshold-mode-inherited",
  };
  const DRAWER_FIELD_PATHS = {
    audioKeepLanguages: "audio.keepTracks",
    audioDropLanguages: "audio.dropTracks",
    audioMaxChannels: "audio.maxChannels",
    audioPreferDefaultLanguage: "audio.preferDefaultLanguage",
    subtitleKeepLanguages: "subtitles.keepTracks",
    subtitleDropLanguages: "subtitles.dropTracks",
    subtitleStripAll: "subtitles.stripAll",
    routeProfile: "routing.profile",
    routingRouteThresholdMode: "routing.routeThresholdMode",
    videoCodec: "video.codec",
    videoContainer: "video.container",
    videoEncodePreset: "video.encodePreset",
    videoEncodeLadder: "video.encodeLadder",
  };
  const DRAWER_FIELD_CONFIG = {
    audioKeepLanguages: { settingKey: "PreferredDefaultAudioLanguages", groups: ["audio", "effective_audio"] },
    audioDropLanguages: {},
    audioMaxChannels: { settingKey: "AudioMaxChannels", groups: ["audio", "effective_audio"], unit: "channels" },
    audioPreferDefaultLanguage: { settingKey: "PreferredDefaultAudioLanguages", groups: ["audio", "effective_audio"], scalarLanguage: true },
    subtitleKeepLanguages: { settingKey: "SubKeepLanguages", groups: ["subtitles", "effective_subtitles"] },
    subtitleDropLanguages: {},
    subtitleStripAll: {},
    routeProfile: { settingKey: "RoutingProfile", groups: ["editor", "effective_editor"] },
    routingRouteThresholdMode: { settingKey: "RouteThresholdMode", groups: ["editor", "effective_editor"] },
    videoCodec: { settingKey: "VideoCodec", groups: ["video", "effective_video"] },
    videoContainer: { settingKey: "OutputContainer", groups: ["video", "effective_video"] },
    videoEncodePreset: { settingKey: "EncodeTuningPreset", groups: ["video", "effective_video"] },
    videoEncodeLadder: { settingKey: "EncodeLadder", groups: ["video", "effective_video"] },
  };
  const ROUTE_FIELD_CONFIG = {
    routeProfile: { controlId: "fo-route-profile", section: "routing", payloadKey: "profile" },
    routingRouteThresholdMode: { controlId: "fo-route-threshold-mode", section: "routing", payloadKey: "routeThresholdMode" },
    videoCodec: { controlId: "fo-video-codec", section: "video", payloadKey: "codec" },
    videoContainer: { controlId: "fo-video-container", section: "video", payloadKey: "container" },
    videoEncodePreset: { controlId: "fo-video-encode-preset", section: "video", payloadKey: "encodePreset" },
    videoEncodeLadder: { controlId: "fo-video-encode-ladder", section: "video", payloadKey: "encodeLadder" },
  };
  const ROUTE_FIELD_KEYS = Object.keys(ROUTE_FIELD_CONFIG);
  const ROUTE_FORCE_VALUES = new Set(["auto", "encode", "remux", "transcode"]);
  const TRACK_ACTION_FIELD_PATHS = {
    audio: { keep: "audio.keepTracks", drop: "audio.dropTracks" },
    subtitle: { keep: "subtitles.keepTracks", drop: "subtitles.dropTracks" },
  };
  const FOLDER_RULE_FILE_SUFFIXES = new Set([".mkv", ".mp4", ".m4v", ".mov", ".avi", ".ts", ".m2ts", ".webm"]);
  const DRAWER_FOCUSABLE_SELECTOR = [
    "a[href]",
    "button",
    "input",
    "select",
    "textarea",
    "[tabindex]:not([tabindex=\"-1\"])",
  ].join(",");

  // ---------------------------------------------------------------------------
  // Helpers
  // ---------------------------------------------------------------------------

  /** Split "eng, jpn , " into ["eng","jpn"] */
  function parseLangList(text) {
    return (text || "")
      .split(",")
      .map((s) => s.trim().toLowerCase())
      .filter(Boolean);
  }

  /** Build a keepTracks/dropTracks rule array from a list of lang codes */
  function langCodesToRules(langs) {
    return langs.map((lang) => ({ language: lang }));
  }

  function selectorStreamIndex(rule) {
    if (!isPlainObject(rule)) return null;
    const raw = rule.streamIndex ?? rule.stream_index ?? rule.trackIndex ?? rule.track_index ?? rule.index;
    const value = Number(raw);
    return Number.isInteger(value) && value >= 0 ? value : null;
  }

  function isExactTrackSelector(rule) {
    return selectorStreamIndex(rule) !== null;
  }

  /** Populate a lang-list input from an array of rule objects */
  function rulesToLangInput(rules) {
    if (!Array.isArray(rules) || !rules.length) return "";
    return rules
      .filter((rule) => !isExactTrackSelector(rule))
      .map((r) => r.language || "")
      .filter(Boolean)
      .join(", ");
  }

  function byId(id) { return document.getElementById(id); }
  function setStatus(msg) {
    const el = byId("fo-drawer-status");
    if (el) el.textContent = msg;
  }

  function isPlainObject(value) {
    return value && typeof value === "object" && !Array.isArray(value);
  }

  function emptyExactSelectorState() {
    return {
      audioKeep: [],
      audioDrop: [],
      subtitleKeep: [],
      subtitleDrop: [],
    };
  }

  function hasOwnValue(source, key) {
    return isPlainObject(source) && Object.prototype.hasOwnProperty.call(source, key);
  }

  function backendErrorMessage(result, fallback = "Unknown error.") {
    const message = String(result?.message || fallback).trim();
    const errors = Array.isArray(result?.errors)
      ? result.errors.map((error) => String(error || "").trim()).filter(Boolean)
      : [];
    if (!errors.length) return message;
    return `${message} ${errors.join(" ")}`;
  }

  function currentFileOverridePathLooksFileLike() {
    const path = String(foCurrentPath || "").trim();
    if (!path || /[\\/]$/.test(path)) return false;
    const leaf = path.split(/[\\/]/).pop() || "";
    return /\.[A-Za-z0-9]{1,12}$/.test(leaf);
  }

  function drawerChoiceLabel(value, explicitLabel = "") {
    const label = String(explicitLabel || "").trim();
    if (label) return label;
    const text = String(value || "").trim();
    const metadataLabels = window.mediaPipelineSettingsMetadata?.settingsChoiceLabels || {};
    if (metadataLabels[text]) return metadataLabels[text];
    return text.replace(/[_-]/g, " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
  }

  function normalizeRouteChoiceOptions(field) {
    const rawChoices = Array.isArray(field?.choices) ? field.choices : [];
    return rawChoices
      .map((choice) => {
        if (isPlainObject(choice)) {
          const value = String(choice.value || "").trim();
          if (!value) return null;
          return { value, label: drawerChoiceLabel(value, choice.label) };
        }
        const value = String(choice || "").trim();
        return value ? { value, label: drawerChoiceLabel(value) } : null;
      })
      .filter(Boolean);
  }

  function populateRouteSelectOptions(select, choices) {
    if (!select) return;
    const current = select.value;
    select.replaceChildren();
    const inherit = document.createElement("option");
    inherit.value = "";
    inherit.textContent = "Inherit";
    select.appendChild(inherit);
    choices.forEach((choice) => {
      const option = document.createElement("option");
      option.value = choice.value;
      option.textContent = choice.label;
      select.appendChild(option);
    });
    const values = choices.map((choice) => choice.value);
    select.value = values.includes(current) ? current : "";
  }

  function firstSettingValue(source, key, groups = []) {
    const candidates = [source];
    groups.forEach((group) => {
      if (isPlainObject(source?.[group])) candidates.push(source[group]);
    });
    for (const candidate of candidates) {
      if (hasOwnValue(candidate, key)) return { found: true, value: candidate[key] };
    }
    return { found: false, value: "" };
  }

  function normalizeLibraryDefaultValue(value, options = {}) {
    if (Array.isArray(value)) {
      const values = value
        .map((item) => isPlainObject(item) ? (item.language || item.value || item.id || "") : item)
        .map((item) => String(item || "").trim())
        .filter(Boolean);
      return options.firstValue ? (values[0] || "") : values.join(", ");
    }
    if (typeof value === "boolean") return value ? "enabled" : "disabled";
    if (value === null || value === undefined) return "";
    return String(value).trim();
  }

  function drawerLibrarySourceLabel(item, sourceName) {
    const libraryName = String(item?.library_name || item?.library_id || "").trim();
    const profileName = String(item?.profile_name || item?.profile || "").trim();
    const parts = [];
    parts.push(libraryName ? `Library ${libraryName}` : "Library");
    if (profileName) parts.push(`profile ${profileName}`);
    if (sourceName === "library_settings_overrides") parts.push("reported overrides");
    return parts.join(" / ");
  }

  function drawerLibrarySettingsSource(item) {
    const effective = isPlainObject(item?.library_effective_settings) ? item.library_effective_settings : {};
    if (Object.keys(effective).length) {
      return { source: effective, sourceName: "library_effective_settings" };
    }
    const overrides = isPlainObject(item?.library_settings_overrides) ? item.library_settings_overrides : {};
    if (Object.keys(overrides).length) {
      return { source: overrides, sourceName: "library_settings_overrides" };
    }
    return { source: {}, sourceName: "" };
  }

  function getDrawerLibraryDefaults(item) {
    const { source, sourceName } = drawerLibrarySettingsSource(item);
    const hasSource = Object.keys(source).length > 0;
    const defaults = {
      available: hasSource,
      sourceLabel: hasSource ? drawerLibrarySourceLabel(item, sourceName) : "Library",
      sourceName,
      fields: {},
    };
    Object.keys(DRAWER_FIELD_CONFIG).forEach((fieldKey) => {
      const config = DRAWER_FIELD_CONFIG[fieldKey] || {};
      if (!hasSource || !config.settingKey) {
        defaults.fields[fieldKey] = { available: false, value: "", unit: config.unit || "" };
        return;
      }
      const found = firstSettingValue(source, config.settingKey, config.groups || []);
      defaults.fields[fieldKey] = {
        available: found.found,
        value: found.found ? normalizeLibraryDefaultValue(found.value, { firstValue: Boolean(config.scalarLanguage) }) : "",
        unit: config.unit || "",
        settingKey: config.settingKey,
      };
    });
    return defaults;
  }

  function formatInheritedValue(inheritedValue) {
    const raw = String(inheritedValue?.value || "").trim();
    if (!raw) return "not set";
    if (inheritedValue?.unit === "channels") return `${raw} channels`;
    return raw;
  }

  function fileOverrideEffectiveSourceLabel(source) {
    if (source === "file_override") return "file override";
    if (source === "folder_override") return "folder override";
    if (source === "library") return "Library";
    if (source === "global_default") return "Global";
    if (source === "unavailable") return "unavailable";
    return "";
  }

  function setInheritedHint(fieldKey, inheritedValue, defaultsAvailable) {
    const el = byId(DRAWER_FIELD_HINT_IDS[fieldKey]);
    if (!el) return;
    el.textContent = "";
    delete el.dataset.available;
    if (!defaultsAvailable) return;
    const effectiveSourceLabel = fileOverrideEffectiveSourceLabel(inheritedValue?.effectiveSource || "");
    const effectiveValue = String(inheritedValue?.effectiveValue || "").trim();
    const inheritedSourceLabel = fileOverrideEffectiveSourceLabel(inheritedValue?.source || "");
    const inheritedPrefix = inheritedSourceLabel === "Global" ? "Global default" : "Library default";
    if (inheritedValue?.effectiveAvailable && effectiveSourceLabel && effectiveValue) {
      const inheritedText = inheritedValue?.available ? formatInheritedValue(inheritedValue) : "unavailable";
      el.textContent = `Effective: ${formatInheritedValue({ value: effectiveValue, unit: inheritedValue?.unit || "" })} (${effectiveSourceLabel}). ${inheritedPrefix}: ${inheritedText}`;
      el.dataset.available = "true";
      return;
    }
    if (inheritedValue?.available) {
      el.textContent = `${inheritedPrefix}: ${formatInheritedValue(inheritedValue)}`;
      el.dataset.available = "true";
    } else {
      el.textContent = "Library default: unavailable";
      el.dataset.available = "false";
    }
  }

  function renderDrawerInheritedDefaults(defaults) {
    const status = byId("fo-inherited-settings-status");
    const available = Boolean(defaults?.available);
    Object.keys(DRAWER_FIELD_HINT_IDS).forEach((fieldKey) => {
      setInheritedHint(fieldKey, defaults?.fields?.[fieldKey], available);
    });
    if (!status) return;
    status.dataset.available = available ? "true" : "false";
    if (!available) {
      status.textContent = "Library defaults unavailable for this queue row.";
      return;
    }
    const fieldValues = Object.values(defaults.fields || {}).filter((field) => field?.available);
    if (fieldValues.length) {
      status.textContent = `Inherited defaults shown from ${defaults.sourceLabel}. Unavailable field hints were not reported on the queue row.`;
    } else {
      status.textContent = `Library defaults unavailable for these drawer fields; the row only reported ${defaults.sourceLabel}.`;
    }
  }

  function drawerEffectiveSourceLabel(payload, item) {
    const library = isPlainObject(payload?.library) ? payload.library : {};
    const name = String(library.name || library.id || "").trim();
    if (library.available) return name ? `Library ${name}` : "Library";
    const inherited = isPlainObject(payload?.inherited) ? Object.values(payload.inherited) : [];
    if (inherited.some((field) => field?.source === "global_default")) return "Global defaults";
    return drawerLibrarySourceLabel(item, "");
  }

  function effectiveInheritedHintValue(fieldKey, field) {
    if (!field?.available) return "";
    const value = field.value;
    if (Array.isArray(value)) return value.map((item) => String(item || "").trim()).filter(Boolean).join(", ");
    if (value === null || value === undefined) return "";
    if (typeof value === "boolean") return value ? "enabled" : "disabled";
    return String(value).trim();
  }

  function drawerDefaultsFromEffectivePayload(payload, item) {
    const inherited = isPlainObject(payload?.inherited) ? payload.inherited : {};
    const expanded = {
      ...(isPlainObject(payload?.expanded_effective_fields) ? payload.expanded_effective_fields : {}),
      ...(isPlainObject(payload?.route_video_effective_fields) ? payload.route_video_effective_fields : {}),
    };
    const fields = {};
    Object.keys(DRAWER_FIELD_CONFIG).forEach((fieldKey) => {
      const expandedField = isPlainObject(expanded[fieldKey]) ? expanded[fieldKey] : {};
      const expandedInherited = isPlainObject(expanded[fieldKey]?.inherited) ? expanded[fieldKey].inherited : {};
      const expandedEffective = isPlainObject(expandedField.effective) ? expandedField.effective : {};
      const field = isPlainObject(inherited[fieldKey]) ? inherited[fieldKey] : expandedInherited;
      fields[fieldKey] = {
        available: Boolean(field.available),
        value: effectiveInheritedHintValue(fieldKey, field),
        source: String(field.source || ""),
        unit: DRAWER_FIELD_CONFIG[fieldKey]?.unit || "",
        settingKey: field.source_key || DRAWER_FIELD_CONFIG[fieldKey]?.settingKey || "",
        effectiveAvailable: Boolean(expandedEffective.available),
        effectiveValue: effectiveInheritedHintValue(fieldKey, expandedEffective),
        effectiveSource: String(expandedEffective.source || ""),
      };
    });
    const hasAvailableField = Object.values(fields).some((field) => field?.available);
    return {
      available: hasAvailableField || Boolean(payload?.library?.available),
      sourceLabel: drawerEffectiveSourceLabel(payload, item),
      sourceName: "file_overrides_effective",
      fields,
    };
  }

  function routeControlElement(fieldKey) {
    const id = ROUTE_FIELD_CONFIG[fieldKey]?.controlId;
    return id ? byId(id) : null;
  }

  function clearRoutePreviewStatus() {
    const status = byId("fo-route-preview-status");
    if (status) {
      status.hidden = true;
      status.textContent = "";
      delete status.dataset.risk;
      status.replaceChildren();
    }
    const confirmation = byId("fo-route-risk-confirmation");
    const checkbox = byId("fo-route-risk-confirm");
    if (checkbox) checkbox.checked = false;
    if (confirmation) confirmation.hidden = true;
  }

  function clearProcessingRouteControls() {
    if (foRoutePreviewTimer) {
      clearTimeout(foRoutePreviewTimer);
      foRoutePreviewTimer = null;
    }
    ROUTE_FIELD_KEYS.forEach((fieldKey) => {
      const field = document.querySelector(`[data-fo-field="${fieldKey}"]`);
      const control = routeControlElement(fieldKey);
      if (control) control.value = "";
      if (field) field.hidden = true;
    });
    const section = byId("fo-processing-route-section");
    if (section) section.hidden = true;
    clearRoutePreviewStatus();
  }

  function renderProcessingRouteControls(payload) {
    const routeFields = isPlainObject(payload?.route_video_effective_fields)
      ? payload.route_video_effective_fields
      : {};
    let supportedCount = 0;
    ROUTE_FIELD_KEYS.forEach((fieldKey) => {
      const field = document.querySelector(`[data-fo-field="${fieldKey}"]`);
      const control = routeControlElement(fieldKey);
      const metadata = isPlainObject(routeFields[fieldKey]) ? routeFields[fieldKey] : {};
      const choices = normalizeRouteChoiceOptions(metadata);
      const supported = choices.length > 0;
      if (control && supported) populateRouteSelectOptions(control, choices);
      if (field) field.hidden = !supported;
      if (supported) supportedCount += 1;
    });
    const section = byId("fo-processing-route-section");
    if (section) section.hidden = supportedCount === 0;
    if (!supportedCount) clearRoutePreviewStatus();
  }

  function applyFileOverrideEffectivePayload(payload, item) {
    if (!payload || payload.ok === false) return false;
    foLastEffectivePayload = payload;
    foExactTrackOverrideEntry = payload.file_override_scope === "file" && isPlainObject(payload.file_override)
      ? payload.file_override
      : null;
    renderProcessingRouteControls(payload);
    renderDrawerInheritedDefaults(drawerDefaultsFromEffectivePayload(payload, item));
    if (isPlainObject(payload.file_override)) {
      populateDrawerForm(payload.file_override);
    } else {
      clearDrawerForm({ resetRouteControls: false, resetTrackMetadata: false });
    }
    renderDrawerTrackMetadata(payload);
    renderDrawerUseInheritedButtons(payload);
    renderRoutePreviewFromEffectivePayload(payload);
    return true;
  }

  function clearDrawerUseInheritedButtons() {
    document.querySelectorAll("[data-fo-use-inherited]").forEach((button) => {
      button.hidden = true;
      button.disabled = true;
    });
  }

  function setDrawerUseInheritedAvailable(fieldKey, isAvailable) {
    const button = document.querySelector(`[data-fo-use-inherited="${fieldKey}"]`);
    if (!button) return;
    button.hidden = !isAvailable;
    button.disabled = !isAvailable;
  }

  function renderDrawerUseInheritedButtons(payload) {
    clearDrawerUseInheritedButtons();
    if (!payload || payload.file_override_scope !== "file" || !isPlainObject(payload.file_override)) return;
    const sources = isPlainObject(payload.sources) ? payload.sources : {};
    const state = drawerOverrideState(payload.file_override);
    Object.keys(DRAWER_FIELD_PATHS).forEach((fieldKey) => {
      const fieldPath = DRAWER_FIELD_PATHS[fieldKey];
      const isExactFileOverride = sources[fieldPath] === "file_override";
      setDrawerUseInheritedAvailable(fieldKey, Boolean(state[fieldKey] && isExactFileOverride));
    });
  }

  function clearDrawerOverrideMarkers() {
    document.querySelectorAll("[data-fo-field]").forEach((field) => {
      delete field.dataset.overridden;
      field.querySelectorAll("[data-fo-overridden-badge]").forEach((badge) => {
        badge.hidden = true;
      });
    });
  }

  function setDrawerFieldOverridden(fieldKey, isOverridden) {
    const field = document.querySelector(`[data-fo-field="${fieldKey}"]`);
    if (!field) return;
    if (isOverridden) field.dataset.overridden = "true";
    else delete field.dataset.overridden;
    field.querySelectorAll("[data-fo-overridden-badge]").forEach((badge) => {
      badge.hidden = !isOverridden;
    });
  }

  function ruleListHasValues(rules) {
    return Array.isArray(rules) && rules.some((rule) => {
      if (isPlainObject(rule)) {
        return ["streamIndex", "stream_index", "trackIndex", "track_index", "index", "language", "value", "codec", "channels", "forced", "title"]
          .some((key) => hasOwnValue(rule, key) && String(rule[key] ?? "").trim() !== "");
      }
      return String(rule || "").trim();
    });
  }

  function drawerOverrideState(entry) {
    const audio = isPlainObject(entry?.audio) ? entry.audio : {};
    const subs = isPlainObject(entry?.subtitles) ? entry.subtitles : {};
    const routing = isPlainObject(entry?.routing) ? entry.routing : {};
    const video = isPlainObject(entry?.video) ? entry.video : {};
    return {
      audioKeepLanguages: ruleListHasValues(audio.keepTracks),
      audioDropLanguages: ruleListHasValues(audio.dropTracks),
      audioMaxChannels: hasOwnValue(audio, "maxChannels") && audio.maxChannels !== null && audio.maxChannels !== "",
      audioPreferDefaultLanguage: hasOwnValue(audio, "preferDefaultLanguage") && String(audio.preferDefaultLanguage || "").trim() !== "",
      subtitleKeepLanguages: ruleListHasValues(subs.keepTracks),
      subtitleDropLanguages: ruleListHasValues(subs.dropTracks),
      subtitleStripAll: hasOwnValue(subs, "stripAll"),
      routeProfile: hasOwnValue(routing, "profile") && String(routing.profile || "").trim() !== "",
      routingRouteThresholdMode: hasOwnValue(routing, "routeThresholdMode") && String(routing.routeThresholdMode || "").trim() !== "",
      videoCodec: hasOwnValue(video, "codec") && String(video.codec || "").trim() !== "",
      videoContainer: hasOwnValue(video, "container") && String(video.container || "").trim() !== "",
      videoEncodePreset: hasOwnValue(video, "encodePreset") && String(video.encodePreset || "").trim() !== "",
      videoEncodeLadder: hasOwnValue(video, "encodeLadder") && String(video.encodeLadder || "").trim() !== "",
    };
  }

  function renderDrawerOverrideMarkers(entry) {
    clearDrawerOverrideMarkers();
    const state = drawerOverrideState(entry);
    Object.keys(state).forEach((fieldKey) => setDrawerFieldOverridden(fieldKey, state[fieldKey]));
  }

  function isHTMLElement(value) {
    if (!value || typeof value !== "object") return false;
    if (typeof HTMLElement === "function") return value instanceof HTMLElement;
    return value.nodeType === 1;
  }

  function fileSettingsTriggerFromOptions(options) {
    if (isHTMLElement(options?.trigger)) return options.trigger;
    return isHTMLElement(document.activeElement) ? document.activeElement : null;
  }

  function isFileSettingsDrawerOpen() {
    const drawer = byId("fo-drawer");
    return Boolean(drawer && !drawer.hidden);
  }

  function fileSettingsElementIsHidden(element) {
    if (!element || element.hidden) return true;
    if (typeof element.closest === "function" && element.closest("[hidden]")) return true;
    if (typeof window.getComputedStyle === "function") {
      const style = window.getComputedStyle(element);
      if (style.display === "none" || style.visibility === "hidden") return true;
    }
    return false;
  }

  function getFileSettingsDrawerFocusableElements() {
    const drawer = byId("fo-drawer");
    if (!drawer || drawer.hidden || typeof drawer.querySelectorAll !== "function") return [];
    return Array.from(drawer.querySelectorAll(DRAWER_FOCUSABLE_SELECTOR)).filter((element) => {
      if (!isHTMLElement(element)) return false;
      if (element.disabled) return false;
      if (element.getAttribute("aria-hidden") === "true") return false;
      return !fileSettingsElementIsHidden(element);
    });
  }

  function focusInitialFileSettingsDrawerControl() {
    const drawer = byId("fo-drawer");
    if (!drawer || drawer.hidden) return;
    const focusable = getFileSettingsDrawerFocusableElements();
    const target = focusable[0] || drawer;
    if (target && typeof target.focus === "function") target.focus();
  }

  function restoreFileSettingsDrawerFocus() {
    const trigger = fileSettingsDrawerTrigger;
    fileSettingsDrawerTrigger = null;
    if (
      trigger &&
      trigger.isConnected &&
      typeof trigger.focus === "function" &&
      !trigger.disabled
    ) {
      trigger.focus();
    }
  }

  function handleFileSettingsDrawerKeydown(event) {
    if (!isFileSettingsDrawerOpen()) return;
    if (event.key === "Escape") {
      closeFileSettingsDrawer();
      return;
    }
    if (event.key !== "Tab") return;
    const drawer = byId("fo-drawer");
    const focusable = getFileSettingsDrawerFocusableElements();
    if (!focusable.length) {
      event.preventDefault();
      if (drawer && typeof drawer.focus === "function") drawer.focus();
      return;
    }
    const first = focusable[0];
    const last = focusable[focusable.length - 1];
    const active = document.activeElement;
    if (event.shiftKey && active === first) {
      event.preventDefault();
      last.focus();
    } else if (!event.shiftKey && active === last) {
      event.preventDefault();
      first.focus();
    }
  }

  try {
    if (typeof window.__queueSetFileDrawer === "function") {
      window.__queueSetFileDrawer(openFileSettingsDrawer);
    }
  } finally {
    delete window.__queueSetFileDrawer;
  }

  // ---------------------------------------------------------------------------
  // Drawer open / close
  // ---------------------------------------------------------------------------

  function openFileSettingsDrawer(item, options = {}) {
    const queueItem = item || {};
    fileSettingsDrawerTrigger = fileSettingsTriggerFromOptions(options);
    const path = queueItem.source_path || "";
    foCurrentPath = path;
    foCurrentItem = queueItem;
    foLastEffectivePayload = null;

    const titleEl = byId("fo-drawer-title");
    const pathEl  = byId("fo-drawer-path");
    const name    = queueItem.display_name || queueItem.relative_path || path || "Unknown";
    if (titleEl) titleEl.textContent = "File Settings — " + (name.length > 40 ? "…" + name.slice(-40) : name);
    if (pathEl) pathEl.textContent = path;

    clearDrawerForm();
    clearFolderRulePreviewPanel();
    clearFolderRuleManagementPanel();
    renderDrawerInheritedDefaults(getDrawerLibraryDefaults(queueItem));
    setStatus("Loading current override…");
    loadFileOverrideForPath(path);
    loadFileOverrideEffectiveForPath(path, queueItem);

    const overlay = byId("fo-overlay");
    const drawer  = byId("fo-drawer");
    if (overlay) { overlay.hidden = false; overlay.removeAttribute("aria-hidden"); }
    if (drawer)  { drawer.hidden  = false; }

    setTimeout(focusInitialFileSettingsDrawerControl, 50);
  }

  function closeFileSettingsDrawer() {
    const overlay = byId("fo-overlay");
    const drawer  = byId("fo-drawer");
    if (overlay) { overlay.hidden = true; overlay.setAttribute("aria-hidden", "true"); }
    if (drawer)  { drawer.hidden  = true; }
    clearDrawerOverrideMarkers();
    clearDrawerUseInheritedButtons();
    clearDrawerTrackMetadata();
    clearProcessingRouteControls();
    clearFolderRulePreviewPanel();
    clearFolderRuleManagementPanel();
    foLastEffectivePayload = null;
    foExactTrackOverrideEntry = null;
    foExactTrackWarnings = [];
    foUnmatchedExactSelectors = emptyExactSelectorState();
    foCurrentPath = "";
    foCurrentItem = null;
    restoreFileSettingsDrawerFocus();
  }

  // ---------------------------------------------------------------------------
  // Form helpers
  // ---------------------------------------------------------------------------

  function clearDrawerForm(options = {}) {
    const resetRouteControls = options.resetRouteControls !== false;
    const resetTrackMetadata = options.resetTrackMetadata !== false;
    const ids = [
      "fo-audio-keep-langs",
      "fo-audio-drop-langs",
      "fo-audio-prefer-default-language",
      "fo-sub-keep-langs",
      "fo-sub-drop-langs",
    ];
    ids.forEach((id) => { const el = byId(id); if (el) el.value = ""; });
    const maxCh = byId("fo-audio-max-channels");
    if (maxCh) maxCh.value = "";
    const stripAll = byId("fo-sub-strip-all");
    if (stripAll) stripAll.checked = false;
    ROUTE_FIELD_KEYS.forEach((fieldKey) => {
      const control = routeControlElement(fieldKey);
      if (control) control.value = "";
    });
    clearDrawerOverrideMarkers();
    clearDrawerUseInheritedButtons();
    foExactTrackOverrideEntry = null;
    resetExactTrackControls();
    foUnmatchedExactSelectors = emptyExactSelectorState();
    foExactTrackWarnings = [];
    if (resetTrackMetadata) clearDrawerTrackMetadata();
    if (resetRouteControls) clearProcessingRouteControls();
    else clearRoutePreviewStatus();
    syncSubFilterFields();
  }

  function syncSubFilterFields() {
    const stripAll = byId("fo-sub-strip-all");
    const fields   = byId("fo-sub-filter-fields");
    const stripAllChecked = Boolean(stripAll && stripAll.checked);
    if (!fields) return;
    if (stripAllChecked) {
      fields.style.opacity = "0.4";
      fields.style.pointerEvents = "none";
    } else {
      fields.style.opacity = "";
      fields.style.pointerEvents = "";
    }
    document.querySelectorAll('[data-fo-track-action][data-fo-track-kind="subtitle"]').forEach((control) => {
      const hasIndex = control.dataset.foTrackIndexAvailable !== "false";
      control.disabled = stripAllChecked || !hasIndex;
      if (stripAllChecked) control.value = "";
    });
  }

  function populateDrawerForm(entry) {
    // entry = { audio: {...}, subtitles: {...} } or null
    const audio = (entry && entry.audio)     || {};
    const subs  = (entry && entry.subtitles) || {};
    const routing = (entry && entry.routing) || {};
    const video = (entry && entry.video) || {};

    const keepLangs = byId("fo-audio-keep-langs");
    const dropLangs = byId("fo-audio-drop-langs");
    const maxCh     = byId("fo-audio-max-channels");
    const preferDefaultLanguage = byId("fo-audio-prefer-default-language");
    if (keepLangs) keepLangs.value = rulesToLangInput(audio.keepTracks);
    if (dropLangs) dropLangs.value = rulesToLangInput(audio.dropTracks);
    if (maxCh) {
      const v = audio.maxChannels != null ? String(audio.maxChannels) : "";
      maxCh.value = ["2","6","8"].includes(v) ? v : "";
    }
    if (preferDefaultLanguage) {
      preferDefaultLanguage.value = String(audio.preferDefaultLanguage || "").trim();
    }

    const stripAll   = byId("fo-sub-strip-all");
    const subKeep    = byId("fo-sub-keep-langs");
    const subDrop    = byId("fo-sub-drop-langs");
    if (stripAll) stripAll.checked = Boolean(subs.stripAll);
    if (subKeep) subKeep.value = rulesToLangInput(subs.keepTracks);
    if (subDrop) subDrop.value = rulesToLangInput(subs.dropTracks);
    const routeProfile = byId("fo-route-profile");
    const routeThresholdMode = byId("fo-route-threshold-mode");
    const videoCodec = byId("fo-video-codec");
    const videoContainer = byId("fo-video-container");
    const videoEncodePreset = byId("fo-video-encode-preset");
    const videoEncodeLadder = byId("fo-video-encode-ladder");
    if (routeProfile) routeProfile.value = String(routing.profile || "");
    if (routeThresholdMode) routeThresholdMode.value = String(routing.routeThresholdMode || "");
    if (videoCodec) videoCodec.value = String(video.codec || "");
    if (videoContainer) videoContainer.value = String(video.container || "");
    if (videoEncodePreset) videoEncodePreset.value = String(video.encodePreset || "");
    if (videoEncodeLadder) videoEncodeLadder.value = String(video.encodeLadder || "");
    renderDrawerOverrideMarkers(entry);
    syncSubFilterFields();
  }

  function buildOverridePayload() {
    const keepLangList = parseLangList(byId("fo-audio-keep-langs")?.value);
    const dropLangList = parseLangList(byId("fo-audio-drop-langs")?.value);
    const maxChVal     = byId("fo-audio-max-channels")?.value || "";
    const preferDefaultLanguage = String(byId("fo-audio-prefer-default-language")?.value || "").trim().toLowerCase();
    const stripAll     = Boolean(byId("fo-sub-strip-all")?.checked);
    const subKeepList  = parseLangList(byId("fo-sub-keep-langs")?.value);
    const subDropList  = parseLangList(byId("fo-sub-drop-langs")?.value);
    const routeProfile = String(byId("fo-route-profile")?.value || "").trim();
    const routeThresholdMode = String(byId("fo-route-threshold-mode")?.value || "").trim();
    const videoCodec = String(byId("fo-video-codec")?.value || "").trim();
    const videoContainer = String(byId("fo-video-container")?.value || "").trim();
    const videoEncodePreset = String(byId("fo-video-encode-preset")?.value || "").trim();
    const videoEncodeLadder = String(byId("fo-video-encode-ladder")?.value || "").trim();
    const exactTrackSelectors = collectExactTrackSelectorsFromControls();

    const audio = {};
    appendSelectorRules(audio, "keepTracks", langCodesToRules(keepLangList));
    appendSelectorRules(audio, "keepTracks", exactTrackSelectors.audioKeep);
    appendSelectorRules(audio, "dropTracks", langCodesToRules(dropLangList));
    appendSelectorRules(audio, "dropTracks", exactTrackSelectors.audioDrop);
    if (maxChVal) audio.maxChannels = parseInt(maxChVal, 10);
    if (preferDefaultLanguage) audio.preferDefaultLanguage = preferDefaultLanguage;

    const subtitles = {};
    if (stripAll) subtitles.stripAll = true;
    if (!stripAll) {
      appendSelectorRules(subtitles, "keepTracks", langCodesToRules(subKeepList));
      appendSelectorRules(subtitles, "keepTracks", exactTrackSelectors.subtitleKeep);
      appendSelectorRules(subtitles, "dropTracks", langCodesToRules(subDropList));
      appendSelectorRules(subtitles, "dropTracks", exactTrackSelectors.subtitleDrop);
    }

    const routing = {};
    if (routeProfile) routing.profile = routeProfile;
    if (routeThresholdMode) routing.routeThresholdMode = routeThresholdMode;

    const video = {};
    if (videoCodec) video.codec = videoCodec;
    if (videoContainer) video.container = videoContainer;
    if (videoEncodePreset) video.encodePreset = videoEncodePreset;
    if (videoEncodeLadder) video.encodeLadder = videoEncodeLadder;

    const hasAudio    = Object.keys(audio).length > 0;
    const hasSubs     = Object.keys(subtitles).length > 0;
    const hasRouting  = Object.keys(routing).length > 0;
    const hasVideo    = Object.keys(video).length > 0;
    if (!hasAudio && !hasSubs && !hasRouting && !hasVideo) return null;  // nothing set

    const payload = { path: foCurrentPath };
    if (hasAudio)  payload.audio     = audio;
    if (hasSubs)   payload.subtitles = subtitles;
    if (hasRouting) payload.routing  = routing;
    if (hasVideo)   payload.video    = video;
    return payload;
  }

  function payloadHasRouteVideoOverride(payload) {
    return Boolean(payload && (isPlainObject(payload.routing) || isPlainObject(payload.video)));
  }

  function routePreviewProposalFromPayload(payload) {
    const proposed = {};
    const routing = isPlainObject(payload?.routing) ? payload.routing : {};
    const video = isPlainObject(payload?.video) ? payload.video : {};
    const proposedRouting = {};
    const profile = String(routing.profile || "").trim();
    if (profile) {
      if (ROUTE_FORCE_VALUES.has(profile.toLowerCase())) proposedRouting.forceRoute = profile;
      else proposedRouting.routingProfile = profile;
    }
    if (routing.routeThresholdMode) proposedRouting.routeThresholdMode = routing.routeThresholdMode;
    if (Object.keys(proposedRouting).length) proposed.routing = proposedRouting;

    const proposedVideo = {};
    if (video.codec) proposedVideo.codec = video.codec;
    if (video.container) proposedVideo.container = video.container;
    if (video.encodePreset) proposedVideo.encodePreset = video.encodePreset;
    if (video.encodeLadder) proposedVideo.encodeLadder = video.encodeLadder;
    if (Object.keys(proposedVideo).length) proposed.video = proposedVideo;
    return proposed;
  }

  function routePreviewWarningMessages(result) {
    const warnings = [];
    if (Array.isArray(result?.warnings)) {
      result.warnings.forEach((warning) => {
        const message = String(isPlainObject(warning) ? warning.message : warning || "").trim();
        if (message) warnings.push(message);
      });
    }
    if (Array.isArray(result?.route_video_processing?.warnings)) {
      result.route_video_processing.warnings.forEach((warning) => {
        const message = String(warning || "").trim();
        if (message) warnings.push(message);
      });
    }
    return Array.from(new Set(warnings));
  }

  function renderRoutePreviewPayload(result) {
    const status = byId("fo-route-preview-status");
    const confirmation = byId("fo-route-risk-confirmation");
    const checkbox = byId("fo-route-risk-confirm");
    if (!status) return;
    status.replaceChildren();
    status.hidden = false;
    delete status.dataset.risk;

    const impact = isPlainObject(result?.impact) ? result.impact : {};
    const risk = String(impact.estimated_risk || "").trim();
    if (risk) status.dataset.risk = risk;
    const current = isPlainObject(result?.current) ? result.current : {};
    const proposed = isPlainObject(result?.proposed) ? result.proposed : {};
    const processing = isPlainObject(result?.route_video_processing) ? result.route_video_processing : {};

    const summary = document.createElement("p");
    summary.className = "fo-route-preview-summary";
    const currentRoute = String(current.route || "").trim();
    const proposedRoute = String(proposed.route || processing.route || "").trim();
    if (currentRoute || proposedRoute) {
      summary.textContent = `Route preview: ${currentRoute || "current route"} -> ${proposedRoute || "inherited route"}.`;
    } else if (result?.ok === false) {
      summary.textContent = backendErrorMessage(result, "Route preview failed.");
    } else {
      summary.textContent = "Route preview available for selected processing overrides.";
    }
    status.appendChild(summary);

    const warnings = routePreviewWarningMessages(result);
    if (warnings.length) {
      const list = document.createElement("ul");
      list.className = "fo-route-preview-list";
      warnings.forEach((message) => {
        const item = document.createElement("li");
        item.textContent = message;
        list.appendChild(item);
      });
      status.appendChild(list);
    }

    const requiresConfirmation = Boolean(impact.requires_confirmation);
    if (confirmation) confirmation.hidden = !requiresConfirmation;
    if (!requiresConfirmation && checkbox) checkbox.checked = false;
  }

  function renderRoutePreviewFromEffectivePayload(payload) {
    const entry = isPlainObject(payload?.file_override) ? payload.file_override : {};
    if (!entry.routing && !entry.video) {
      clearRoutePreviewStatus();
      return;
    }
    const processing = isPlainObject(payload?.route_video_processing) ? payload.route_video_processing : {};
    const warnings = Array.isArray(processing.warnings) ? processing.warnings : [];
    if (!warnings.length) {
      clearRoutePreviewStatus();
      return;
    }
    renderRoutePreviewPayload({
      ok: true,
      proposed: { route: processing.route || "" },
      route_video_processing: processing,
      impact: {
        estimated_risk: processing.will_force_transcode ? "high" : "medium",
        requires_confirmation: false,
      },
      warnings,
    });
  }

  function trackActionBucket(kind, action) {
    if (kind === "audio" && action === "keep") return "audioKeep";
    if (kind === "audio" && action === "drop") return "audioDrop";
    if (kind === "subtitle" && action === "keep") return "subtitleKeep";
    if (kind === "subtitle" && action === "drop") return "subtitleDrop";
    return "";
  }

  function exactSelectorRules(entry, kind, action) {
    const sectionKey = kind === "audio" ? "audio" : "subtitles";
    const fieldKey = action === "keep" ? "keepTracks" : "dropTracks";
    const section = isPlainObject(entry?.[sectionKey]) ? entry[sectionKey] : {};
    const rules = Array.isArray(section[fieldKey]) ? section[fieldKey] : [];
    return rules.filter((rule) => isPlainObject(rule) && isExactTrackSelector(rule));
  }

  function normalizedTrackLanguage(value) {
    const text = String(value ?? "").trim().toLowerCase();
    return text || "und";
  }

  function normalizedTrackCodec(value) {
    return String(value ?? "").trim().toLowerCase();
  }

  function trackTitleValue(value) {
    return String(value ?? "").trim();
  }

  function globPatternMatches(value, pattern) {
    const text = String(value || "").toLowerCase();
    const rawPattern = String(pattern || "").toLowerCase();
    if (!rawPattern) return true;
    const escaped = rawPattern.replace(/[.+^${}()|[\]\\]/g, "\\$&").replace(/\*/g, ".*").replace(/\?/g, ".");
    return new RegExp(`^${escaped}$`).test(text);
  }

  function exactSelectorMatchesTrack(selector, track, kind) {
    if (!isPlainObject(selector) || !isPlainObject(track)) return false;
    const selectorIndex = selectorStreamIndex(selector);
    if (selectorIndex === null || selectorIndex !== trackStreamIndex(track)) return false;
    if (hasOwnValue(selector, "language") && normalizedTrackLanguage(selector.language) !== normalizedTrackLanguage(track.language)) return false;
    if (hasOwnValue(selector, "codec") && normalizedTrackCodec(selector.codec) !== normalizedTrackCodec(track.codec)) return false;
    if (hasOwnValue(selector, "title") && !globPatternMatches(trackTitleValue(track.title), selector.title)) return false;
    if (kind === "audio" && hasOwnValue(selector, "channels")) {
      const selectorChannels = Number(selector.channels);
      const trackChannels = Number(track.channels);
      if (!Number.isFinite(selectorChannels) || !Number.isFinite(trackChannels) || selectorChannels !== trackChannels) return false;
    }
    if (kind === "subtitle" && hasOwnValue(selector, "forced") && Boolean(selector.forced) !== Boolean(track.forced)) return false;
    return true;
  }

  function exactSelectorForTrack(track, kind) {
    const streamIndex = trackStreamIndex(track);
    if (streamIndex === null) return null;
    const selector = { streamIndex };
    const language = normalizedTrackLanguage(track.language);
    if (language) selector.language = language;
    const codec = normalizedTrackCodec(track.codec);
    if (codec) selector.codec = codec;
    const title = trackTitleValue(track.title);
    if (title) selector.title = title;
    if (kind === "audio") {
      const channels = Number(track.channels);
      if (Number.isInteger(channels) && channels > 0) selector.channels = channels;
    } else if (typeof track.forced === "boolean") {
      selector.forced = Boolean(track.forced);
    }
    return selector;
  }

  function trackExactActionForTrack(track, kind) {
    const entry = foExactTrackOverrideEntry;
    if (!isPlainObject(entry)) return "";
    const keepRules = exactSelectorRules(entry, kind, "keep");
    const dropRules = exactSelectorRules(entry, kind, "drop");
    const matchesKeep = keepRules.some((rule) => exactSelectorMatchesTrack(rule, track, kind));
    const matchesDrop = dropRules.some((rule) => exactSelectorMatchesTrack(rule, track, kind));
    if (matchesDrop) return "drop";
    if (matchesKeep) return "keep";
    return "";
  }

  function computeExactTrackWarningsForMetadata(metadata) {
    const entry = foExactTrackOverrideEntry;
    foUnmatchedExactSelectors = emptyExactSelectorState();
    if (!isPlainObject(entry)) return [];
    const available = Boolean(metadata?.available || metadata?.probe_available);
    if (!available) {
      return ["Saved exact-track override cannot be displayed because track metadata is unavailable."];
    }
    const warnings = [];
    const groups = [
      { kind: "audio", action: "keep", tracks: Array.isArray(metadata.audio_tracks) ? metadata.audio_tracks : [] },
      { kind: "audio", action: "drop", tracks: Array.isArray(metadata.audio_tracks) ? metadata.audio_tracks : [] },
      { kind: "subtitle", action: "keep", tracks: Array.isArray(metadata.subtitle_tracks) ? metadata.subtitle_tracks : [] },
      { kind: "subtitle", action: "drop", tracks: Array.isArray(metadata.subtitle_tracks) ? metadata.subtitle_tracks : [] },
    ];
    groups.forEach(({ kind, action, tracks }) => {
      exactSelectorRules(entry, kind, action).forEach((selector) => {
        const streamIndex = selectorStreamIndex(selector);
        const matched = tracks.some((track) => isPlainObject(track) && exactSelectorMatchesTrack(selector, track, kind));
        if (matched) return;
        const bucket = trackActionBucket(kind, action);
        if (bucket) foUnmatchedExactSelectors[bucket].push(selector);
        warnings.push(
          `Saved exact-track override no longer matches detected track metadata: ${TRACK_ACTION_FIELD_PATHS[kind][action]} stream ${streamIndex ?? "?"}.`
        );
      });
    });
    const seen = new Set();
    groups.forEach(({ kind, tracks }) => {
      tracks.forEach((track) => {
        if (!isPlainObject(track)) return;
        const streamIndex = trackStreamIndex(track);
        if (streamIndex === null) return;
        const key = `${kind}:${streamIndex}`;
        if (seen.has(key)) return;
        seen.add(key);
        const matchesKeep = exactSelectorRules(entry, kind, "keep").some((rule) => exactSelectorMatchesTrack(rule, track, kind));
        const matchesDrop = exactSelectorRules(entry, kind, "drop").some((rule) => exactSelectorMatchesTrack(rule, track, kind));
        if (matchesKeep && matchesDrop) {
          warnings.push(`Stream ${streamIndex} is saved as both Keep and Drop; Drop wins during processing.`);
        }
      });
    });
    return Array.from(new Set(warnings));
  }

  function resetExactTrackControls() {
    document.querySelectorAll("[data-fo-track-action]").forEach((control) => {
      control.value = "";
    });
  }

  function resetExactTrackActionsForField(fieldKey) {
    const targetPath = DRAWER_FIELD_PATHS[fieldKey];
    if (!targetPath) return;
    document.querySelectorAll("[data-fo-track-action]").forEach((control) => {
      const kind = control.dataset.foTrackKind || "";
      const action = control.dataset.foTrackActionKind || "";
      if (TRACK_ACTION_FIELD_PATHS[kind]?.[action] === targetPath) control.value = "";
    });
    const bucket = trackActionBucket(
      targetPath.startsWith("audio.") ? "audio" : "subtitle",
      targetPath.endsWith(".keepTracks") ? "keep" : "drop",
    );
    if (bucket) foUnmatchedExactSelectors[bucket] = [];
    foExactTrackWarnings = foExactTrackWarnings.filter((message) => !String(message || "").includes(targetPath));
  }

  function collectExactTrackSelectorsFromControls() {
    const selectors = emptyExactSelectorState();
    if (!currentFileOverridePathLooksFileLike()) return selectors;
    document.querySelectorAll("[data-fo-track-action]").forEach((control) => {
      if (control.disabled) return;
      const action = String(control.value || "");
      if (action !== "keep" && action !== "drop") return;
      const kind = control.dataset.foTrackKind || "";
      const trackData = control.dataset.foTrackJson || "";
      let track = null;
      try { track = JSON.parse(trackData); } catch (_err) { track = null; }
      const selector = exactSelectorForTrack(track, kind);
      const bucket = trackActionBucket(kind, action);
      if (bucket && selector) selectors[bucket].push(selector);
    });
    Object.keys(foUnmatchedExactSelectors).forEach((bucket) => {
      selectors[bucket].push(...foUnmatchedExactSelectors[bucket]);
    });
    return selectors;
  }

  function appendSelectorRules(target, key, rules) {
    if (!rules.length) return;
    target[key] = Array.isArray(target[key]) ? target[key].concat(rules) : rules.slice();
  }

  function validateExactTrackSelectionsBeforeSave() {
    const selectedExactControl = Array.from(document.querySelectorAll("[data-fo-track-action]"))
      .some((control) => ["keep", "drop"].includes(String(control.value || "")));
    if (selectedExactControl && !currentFileOverridePathLooksFileLike()) {
      setStatus("Exact stream selectors can only be saved for a file path, not a folder or library scope.");
      return false;
    }
    if (foExactTrackWarnings.some((message) => message.includes("Saved exact-track override"))) {
      setStatus("Saved exact-track override cannot be safely resaved. Use inherited for the affected field before saving.");
      return false;
    }
    const selected = new Map();
    let conflict = "";
    document.querySelectorAll("[data-fo-track-action]").forEach((control) => {
      const action = String(control.value || "");
      if (action !== "keep" && action !== "drop") return;
      const kind = control.dataset.foTrackKind || "";
      const streamIndex = Number(control.dataset.foTrackStreamIndex);
      if (!kind || !Number.isInteger(streamIndex)) return;
      const key = `${kind}:${streamIndex}`;
      const previous = selected.get(key);
      if (previous && previous !== action) conflict = `${kind} stream ${streamIndex}`;
      selected.set(key, action);
    });
    if (conflict) {
      setStatus(`Choose either Keep or Drop for ${conflict}, not both.`);
      return false;
    }
    return true;
  }

  function trackTextValue(value, fallback = "Not reported") {
    const text = String(value ?? "").trim();
    return text || fallback;
  }

  function trackStreamIndex(track) {
    const raw = track?.stream_index ?? track?.index;
    const value = Number(raw);
    return Number.isFinite(value) ? value : null;
  }

  function setTrackText(id, text) {
    const el = byId(id);
    if (el) el.textContent = text;
  }

  function clearElementChildren(id) {
    const el = byId(id);
    if (el) el.replaceChildren();
  }

  function clearDrawerTrackMetadata(message = "Track metadata unavailable for this file.") {
    ["fo-audio-track-list", "fo-subtitle-track-list", "fo-track-warning-list"].forEach(clearElementChildren);
    setTrackText("fo-audio-track-count", "Unavailable");
    setTrackText("fo-subtitle-track-count", "Unavailable");
    setTrackText("fo-audio-track-status", message);
    setTrackText("fo-subtitle-track-status", message);
    foExactTrackWarnings = [];
    foUnmatchedExactSelectors = emptyExactSelectorState();
  }

  function createTrackBadge(label, tone = "") {
    const badge = document.createElement("span");
    badge.className = "fo-track-badge";
    badge.textContent = label;
    if (tone) badge.dataset.tone = tone;
    return badge;
  }

  function appendTrackDetail(container, label, value) {
    const detail = document.createElement("span");
    detail.className = "fo-track-detail";
    detail.textContent = `${label}: ${trackTextValue(value)}`;
    container.appendChild(detail);
  }

  function trackSelectionMarkerLabel(marker) {
    if (!isPlainObject(marker)) return "";
    const sourceLabel = fileOverrideEffectiveSourceLabel(marker.source || "") || String(marker.source || "").trim();
    const field = String(marker.field || "").trim();
    if (sourceLabel && field) return `${sourceLabel} ${field}`;
    return sourceLabel || field;
  }

  function trackPreviewState(preview, streamIndex) {
    if (!isPlainObject(preview) || streamIndex === null) return null;
    const kept = Array.isArray(preview.kept_stream_indexes) ? preview.kept_stream_indexes.map(Number) : [];
    const dropped = Array.isArray(preview.dropped_stream_indexes) ? preview.dropped_stream_indexes.map(Number) : [];
    const indexKey = String(streamIndex);
    if (dropped.includes(streamIndex)) {
      return {
        label: "Dropped",
        tone: "warning",
        marker: isPlainObject(preview.dropped_stream_sources) ? preview.dropped_stream_sources[indexKey] : null,
      };
    }
    if (kept.includes(streamIndex)) {
      return {
        label: "Kept",
        tone: "",
        marker: isPlainObject(preview.kept_stream_sources) ? preview.kept_stream_sources[indexKey] : null,
      };
    }
    return null;
  }

  function appendTrackFlags(container, track, kind, previewState) {
    if (previewState) {
      const markerLabel = trackSelectionMarkerLabel(previewState.marker);
      const label = markerLabel ? `${previewState.label} by ${markerLabel}` : previewState.label;
      container.appendChild(createTrackBadge(label, previewState.tone));
    }
    if (track.default) container.appendChild(createTrackBadge("Default"));
    if (track.forced) container.appendChild(createTrackBadge("Forced", "warning"));
    if (kind === "audio" && track.commentary) container.appendChild(createTrackBadge("Commentary", "warning"));
    if (track.hearing_impaired) container.appendChild(createTrackBadge("SDH"));
    if (kind === "subtitle" && track.image_based) container.appendChild(createTrackBadge("Image subtitle", "warning"));
    if (kind === "subtitle" && track.text_based) container.appendChild(createTrackBadge("Text subtitle"));
  }

  function createTrackActionControl(track, kind) {
    const streamIndex = trackStreamIndex(track);
    const wrapper = document.createElement("label");
    wrapper.className = "fo-track-action";
    const label = document.createElement("span");
    label.textContent = "File override";
    wrapper.appendChild(label);

    const select = document.createElement("select");
    select.className = "fo-track-action-select";
    select.dataset.foTrackAction = "true";
    select.dataset.foTrackKind = kind;
    select.dataset.foTrackStreamIndex = streamIndex === null ? "" : String(streamIndex);
    select.dataset.foTrackIndexAvailable = streamIndex === null ? "false" : "true";
    select.dataset.foTrackJson = JSON.stringify(track);
    select.setAttribute("aria-label", `Override action for ${kind === "audio" ? "audio" : "subtitle"} stream ${streamIndex ?? "unknown"}`);
    [
      ["", "Inherit"],
      ["keep", kind === "audio" ? "Keep this audio track" : "Keep this subtitle track"],
      ["drop", kind === "audio" ? "Drop this audio track" : "Drop this subtitle track"],
    ].forEach(([value, text]) => {
      const option = document.createElement("option");
      option.value = value;
      option.textContent = text;
      select.appendChild(option);
    });
    select.value = trackExactActionForTrack(track, kind);
    if (streamIndex === null) {
      select.disabled = true;
      select.title = "Track stream index unavailable; exact-track override cannot be saved for this row.";
    }
    wrapper.appendChild(select);
    return wrapper;
  }

  function createTrackRow(track, kind, preview) {
    const row = document.createElement("div");
    row.className = "fo-track-row";
    row.dataset.trackKind = kind;

    const streamIndex = trackStreamIndex(track);
    const previewState = trackPreviewState(preview, streamIndex);

    const summary = document.createElement("div");
    summary.className = "fo-track-summary";
    const title = document.createElement("strong");
    title.textContent = streamIndex === null ? "Stream ?" : `Stream ${streamIndex}`;
    summary.appendChild(title);
    const display = document.createElement("span");
    display.textContent = trackTextValue(track.display, `${trackTextValue(track.language, "und")} track`);
    summary.appendChild(display);
    row.appendChild(summary);

    const details = document.createElement("div");
    details.className = "fo-track-details";
    appendTrackDetail(details, "Language", trackTextValue(track.language, "und"));
    appendTrackDetail(details, "Title", track.title);
    appendTrackDetail(details, "Codec", track.codec);
    if (kind === "audio") {
      appendTrackDetail(details, "Channels", track.channels);
      appendTrackDetail(details, "Layout", track.channel_layout);
    }
    row.appendChild(details);

    const badges = document.createElement("div");
    badges.className = "fo-track-badges";
    appendTrackFlags(badges, track, kind, previewState);
    row.appendChild(badges);
    row.appendChild(createTrackActionControl(track, kind));
    return row;
  }

  function renderTrackGroup({ kind, tracks, preview, listId, countId, statusId }) {
    const list = byId(listId);
    if (list) list.replaceChildren();
    const count = tracks.length;
    setTrackText(countId, `${count} ${count === 1 ? "track" : "tracks"}`);
    if (!count) {
      setTrackText(statusId, kind === "audio" ? "No detected audio tracks were reported." : "No detected subtitle tracks were reported.");
      return;
    }
    setTrackText(statusId, "");
    if (!list) return;
    tracks.forEach((track) => {
      if (isPlainObject(track)) list.appendChild(createTrackRow(track, kind, preview));
    });
  }

  function trackWarningMessage(warning) {
    if (!isPlainObject(warning)) return String(warning || "").trim();
    const message = String(warning.message || "").trim();
    const field = String(warning.field || "").trim();
    if (!message) return "";
    return field ? `${field}: ${message}` : message;
  }

  function collectTrackWarnings(metadata, preview) {
    const warnings = [];
    const addWarning = (warning) => {
      const message = trackWarningMessage(warning);
      if (message) warnings.push(message);
    };
    (Array.isArray(metadata?.warnings) ? metadata.warnings : []).forEach(addWarning);
    (Array.isArray(preview?.audio?.warnings) ? preview.audio.warnings : []).forEach(addWarning);
    (Array.isArray(preview?.subtitles?.warnings) ? preview.subtitles.warnings : []).forEach(addWarning);
    (Array.isArray(metadata?.audio_tracks) ? metadata.audio_tracks : []).forEach((track) => {
      const index = trackStreamIndex(track);
      if (track?.commentary) warnings.push(`Audio stream ${index ?? "?"} appears to be commentary.`);
    });
    (Array.isArray(metadata?.subtitle_tracks) ? metadata.subtitle_tracks : []).forEach((track) => {
      const index = trackStreamIndex(track);
      if (track?.forced) warnings.push(`Subtitle stream ${index ?? "?"} is marked forced.`);
      if (track?.image_based) warnings.push(`Subtitle stream ${index ?? "?"} is image-based and may require OCR or burn-in review.`);
    });
    foExactTrackWarnings.forEach((message) => {
      const text = String(message || "").trim();
      if (text) warnings.push(text);
    });
    return Array.from(new Set(warnings));
  }

  function renderTrackWarnings(metadata, preview) {
    const list = byId("fo-track-warning-list");
    if (!list) return;
    list.replaceChildren();
    const warnings = collectTrackWarnings(metadata, preview);
    if (!warnings.length) return;
    const heading = document.createElement("p");
    heading.className = "fo-track-warning-heading";
    heading.textContent = "Track warnings";
    list.appendChild(heading);
    const warningList = document.createElement("ul");
    warnings.forEach((message) => {
      const item = document.createElement("li");
      item.className = "fo-track-warning";
      item.textContent = message;
      warningList.appendChild(item);
    });
    list.appendChild(warningList);
  }

  function renderDrawerTrackMetadata(payload) {
    const metadata = isPlainObject(payload?.track_metadata) ? payload.track_metadata : {};
    const preview = isPlainObject(payload?.track_selection_preview) ? payload.track_selection_preview : {};
    const available = Boolean(metadata.available || metadata.probe_available);
    foExactTrackWarnings = computeExactTrackWarningsForMetadata(metadata);
    if (!available) {
      const message = trackWarningMessage((Array.isArray(metadata.warnings) ? metadata.warnings : [])[0])
        || "Track metadata unavailable for this file.";
      clearDrawerTrackMetadata(message);
      foExactTrackWarnings = computeExactTrackWarningsForMetadata(metadata);
      renderTrackWarnings(metadata, preview);
      return;
    }
    const audioTracks = Array.isArray(metadata.audio_tracks) ? metadata.audio_tracks : [];
    const subtitleTracks = Array.isArray(metadata.subtitle_tracks) ? metadata.subtitle_tracks : [];
    renderTrackGroup({
      kind: "audio",
      tracks: audioTracks,
      preview: isPlainObject(preview.audio) ? preview.audio : {},
      listId: "fo-audio-track-list",
      countId: "fo-audio-track-count",
      statusId: "fo-audio-track-status",
    });
    renderTrackGroup({
      kind: "subtitle",
      tracks: subtitleTracks,
      preview: isPlainObject(preview.subtitles) ? preview.subtitles : {},
      listId: "fo-subtitle-track-list",
      countId: "fo-subtitle-track-count",
      statusId: "fo-subtitle-track-status",
    });
    renderTrackWarnings(metadata, preview);
    syncSubFilterFields();
  }

  function trackMetadataFromTracksPayload(payload) {
    const available = Boolean(payload?.probe_available);
    return {
      available,
      probe_available: available,
      probe_source: String(payload?.probe_source || (available ? "tracks_endpoint" : "unavailable")),
      audio_tracks: available && Array.isArray(payload?.audio_tracks) ? payload.audio_tracks : [],
      subtitle_tracks: available && Array.isArray(payload?.subtitle_tracks) ? payload.subtitle_tracks : [],
      warnings: Array.isArray(payload?.warnings) ? payload.warnings : [],
    };
  }

  function normalizedFolderPreviewPath(value) {
    return String(value || "").trim().replace(/\\/g, "/").replace(/\/+$/, "").toLowerCase();
  }

  function folderPreviewParentPath(value) {
    const text = String(value || "").trim().replace(/[\\/]+$/, "");
    if (!text) return "";
    const slash = Math.max(text.lastIndexOf("\\"), text.lastIndexOf("/"));
    if (slash < 0) return "";
    if (slash === 0) return text.slice(0, 1);
    if (slash === 2 && /^[A-Za-z]:/.test(text)) return text.slice(0, 3);
    return text.slice(0, slash);
  }

  function folderPreviewLeaf(value) {
    const text = String(value || "").trim().replace(/[\\/]+$/, "");
    if (!text) return "";
    return text.split(/[\\/]/).filter(Boolean).pop() || text;
  }

  function folderPreviewScopeLabel(folderPath, payload) {
    const scope = isPlainObject(payload?.scope) ? payload.scope : {};
    if (scope.is_library_root) return "Library root";
    const folderKey = normalizedFolderPreviewPath(folderPath);
    const sourceRootKey = normalizedFolderPreviewPath(foCurrentItem?.library_source_root || foCurrentItem?.source_root || "");
    if (sourceRootKey && folderKey === sourceRootKey) return "Library root";

    const leaf = folderPreviewLeaf(folderPath).toLowerCase();
    const seasonFolder = String(foCurrentItem?.season_folder || "").trim().toLowerCase();
    if ((seasonFolder && leaf === seasonFolder) || /^s\d{1,2}$/.test(leaf) || /^season\s+\d{1,2}$/.test(leaf)) {
      return "Season folder";
    }

    const showFolder = String(foCurrentItem?.show_folder || "").trim().toLowerCase();
    if (showFolder && leaf === showFolder) {
      return "Show folder";
    }

    const relativeParent = folderPreviewParentPath(foCurrentItem?.relative_path || "");
    const relativeParentLeaf = folderPreviewLeaf(relativeParent).toLowerCase();
    const relativeGrandparent = folderPreviewParentPath(relativeParent);
    const mediaType = String(foCurrentItem?.media_type || foCurrentItem?.type || "").toLowerCase();
    if (relativeParentLeaf && leaf === relativeParentLeaf && !relativeGrandparent && mediaType.includes("tv")) {
      return "Show folder";
    }
    return "File folder";
  }

  function folderPreviewLibraryRootPath(payload) {
    const scope = isPlainObject(payload?.scope) ? payload.scope : {};
    return String(scope.library_source_path || foCurrentItem?.library_source_root || foCurrentItem?.source_root || "").trim();
  }

  function folderPreviewPathSegments(path) {
    return normalizedFolderPreviewPath(path).split("/").filter(Boolean);
  }

  function folderPreviewSegmentsUnderLibraryRoot(folderPath, payload) {
    const rootKey = normalizedFolderPreviewPath(folderPreviewLibraryRootPath(payload));
    const folderKey = normalizedFolderPreviewPath(folderPath);
    if (!rootKey || !folderKey || folderKey === rootKey) return [];
    if (!folderKey.startsWith(rootKey + "/")) return [];
    const rootSegments = folderPreviewPathSegments(rootKey);
    const folderSegments = folderPreviewPathSegments(folderKey);
    return folderSegments.slice(rootSegments.length);
  }

  function folderPreviewIsNarrowShowOrSeasonScope(folderPath, payload) {
    const label = folderPreviewScopeLabel(folderPath, payload);
    return label === "Season folder" || label === "Show folder";
  }

  function folderPreviewIsLibraryRoot(folderPath, payload) {
    const scope = isPlainObject(payload?.scope) ? payload.scope : {};
    if (scope.is_library_root) return true;
    const folderKey = normalizedFolderPreviewPath(folderPath);
    const sourceRootKey = normalizedFolderPreviewPath(folderPreviewLibraryRootPath(payload));
    return Boolean(sourceRootKey && folderKey === sourceRootKey);
  }

  function folderPreviewIsNearLibraryRoot(folderPath, payload) {
    if (folderPreviewIsLibraryRoot(folderPath, payload)) return true;
    const segments = folderPreviewSegmentsUnderLibraryRoot(folderPath, payload);
    return Boolean(segments.length === 1 && !folderPreviewIsNarrowShowOrSeasonScope(folderPath, payload));
  }

  function folderPreviewLooksBroadLibraryPolicy(folderPath, payload) {
    if (folderPreviewIsLibraryRoot(folderPath, payload)) return true;
    if (!folderPreviewIsNearLibraryRoot(folderPath, payload)) return false;
    const impact = isPlainObject(payload?.impact) ? payload.impact : {};
    const knownCount = Number(impact.known_file_count || 0);
    const previewedCount = Number(impact.previewed_file_count || 0);
    return Boolean(knownCount > 1 || previewedCount > 1 || impact.partial);
  }

  function folderPreviewLibraryRootSaveApproved(payload) {
    return payload?.allow_library_root_folder_rule === true;
  }

  function folderPreviewSaveBlockedByLibraryRoot(folderPath, payload) {
    return folderPreviewIsLibraryRoot(folderPath, payload) && !folderPreviewLibraryRootSaveApproved(payload);
  }

  function folderPreviewLibraryHandoffMessage(folderPath, payload) {
    if (!folderPreviewLooksBroadLibraryPolicy(folderPath, payload)) return "";
    return "This looks like a broad library-level policy. Use Library settings for stable defaults.";
  }

  function setFolderPreviewLibraryHandoff(folderPath, payload) {
    const message = folderPreviewLibraryHandoffMessage(folderPath, payload);
    setTrackText("fo-folder-preview-library-note", message);
    const button = byId("fo-folder-preview-library-settings");
    if (button) button.hidden = !message;
    return message;
  }

  function folderPreviewAddScopeCandidate(candidates, seen, label, path) {
    const cleanPath = String(path || "").trim().replace(/[\\/]+$/, "");
    const key = normalizedFolderPreviewPath(cleanPath);
    if (!cleanPath || !key || seen.has(key)) return;
    const sourceRootKey = normalizedFolderPreviewPath(foCurrentItem?.library_source_root || foCurrentItem?.source_root || "");
    if (sourceRootKey && key === sourceRootKey) return;
    seen.add(key);
    candidates.push({ label: label || "Folder", path: cleanPath });
  }

  function folderPreviewScopeCandidates() {
    const candidates = [];
    const seen = new Set();
    const fileFolder = folderPreviewParentPath(foCurrentPath);
    folderPreviewAddScopeCandidate(candidates, seen, folderPreviewScopeLabel(fileFolder, {}), fileFolder);

    const parent = folderPreviewParentPath(fileFolder);
    if (parent) {
      const currentLabel = folderPreviewScopeLabel(fileFolder, {});
      folderPreviewAddScopeCandidate(
        candidates,
        seen,
        currentLabel === "Season folder" ? "Show folder" : "Parent folder",
        parent,
      );
    }
    return candidates;
  }

  function renderFolderPreviewScopeOptions() {
    const select = byId("fo-folder-preview-scope-select");
    const candidates = folderPreviewScopeCandidates();
    if (!select) return candidates[0]?.path || "";

    const previous = String(select.value || "").trim();
    select.replaceChildren();
    candidates.forEach((candidate) => {
      const option = document.createElement("option");
      option.value = candidate.path;
      option.textContent = `${candidate.label}: ${candidate.path}`;
      select.appendChild(option);
    });
    if (previous && candidates.some((candidate) => candidate.path === previous)) {
      select.value = previous;
    }
    select.disabled = candidates.length <= 1;
    return String(select.value || candidates[0]?.path || "").trim();
  }

  function selectedFolderPreviewPath() {
    const selected = String(byId("fo-folder-preview-scope-select")?.value || "").trim();
    return selected || renderFolderPreviewScopeOptions() || folderPreviewParentPath(foCurrentPath);
  }

  function folderPreviewSelectorFromTrack(track, kind) {
    const exact = exactSelectorForTrack(track, kind);
    if (!exact) return null;
    const selector = {};
    ["language", "codec", "title"].forEach((key) => {
      const value = String(exact[key] || "").trim();
      if (value) selector[key] = value;
    });
    if (kind === "audio" && hasOwnValue(exact, "channels")) selector.channels = exact.channels;
    if (kind === "subtitle" && hasOwnValue(exact, "forced")) selector.forced = Boolean(exact.forced);
    return Object.keys(selector).length ? selector : null;
  }

  function folderPreviewAppendRules(section, key, rules) {
    const cleanRules = (Array.isArray(rules) ? rules : []).filter((rule) => isPlainObject(rule) && Object.keys(rule).length);
    if (!cleanRules.length) return;
    section[key] = Array.isArray(section[key]) ? section[key].concat(cleanRules) : cleanRules.slice();
  }

  function buildFolderPreviewProposal() {
    const audio = {};
    const subtitles = {};
    const stripAll = Boolean(byId("fo-sub-strip-all")?.checked);
    folderPreviewAppendRules(audio, "keepTracks", langCodesToRules(parseLangList(byId("fo-audio-keep-langs")?.value)));
    folderPreviewAppendRules(audio, "dropTracks", langCodesToRules(parseLangList(byId("fo-audio-drop-langs")?.value)));
    if (!stripAll) {
      folderPreviewAppendRules(subtitles, "keepTracks", langCodesToRules(parseLangList(byId("fo-sub-keep-langs")?.value)));
      folderPreviewAppendRules(subtitles, "dropTracks", langCodesToRules(parseLangList(byId("fo-sub-drop-langs")?.value)));
    }

    document.querySelectorAll("[data-fo-track-action]").forEach((control) => {
      if (control.disabled) return;
      const action = String(control.value || "");
      if (action !== "keep" && action !== "drop") return;
      const kind = control.dataset.foTrackKind || "";
      if (stripAll && kind === "subtitle") return;
      let track = null;
      try { track = JSON.parse(control.dataset.foTrackJson || ""); } catch (_err) { track = null; }
      const selector = folderPreviewSelectorFromTrack(track, kind);
      if (!selector) return;
      if (kind === "audio") folderPreviewAppendRules(audio, action === "keep" ? "keepTracks" : "dropTracks", [selector]);
      if (kind === "subtitle") folderPreviewAppendRules(subtitles, action === "keep" ? "keepTracks" : "dropTracks", [selector]);
    });

    const proposed = {};
    if (Object.keys(audio).length) proposed.audio = audio;
    if (Object.keys(subtitles).length) proposed.subtitles = subtitles;
    return proposed;
  }

  function folderPreviewWarningText(warning) {
    if (!isPlainObject(warning)) return String(warning || "").trim();
    const field = String(warning.field || "").trim();
    const message = String(warning.message || "").trim();
    if (!message) return "";
    return field ? `${field}: ${message}` : message;
  }

  function folderPreviewSelectorText(selector) {
    if (!isPlainObject(selector)) return "";
    const parts = [];
    ["language", "codec", "title", "channels", "forced"].forEach((key) => {
      if (!hasOwnValue(selector, key)) return;
      const value = selector[key];
      if (value === null || value === undefined || String(value).trim() === "") return;
      parts.push(`${key}=${value}`);
    });
    return parts.join(", ");
  }

  function appendFolderPreviewListItems(list, items, formatter) {
    if (!list) return;
    const values = (Array.isArray(items) ? items : []).map(formatter).filter(Boolean);
    if (!values.length) {
      const item = document.createElement("li");
      item.className = "fo-folder-preview-empty";
      item.textContent = "None reported.";
      list.appendChild(item);
      return;
    }
    values.forEach((value) => {
      const item = document.createElement("li");
      item.textContent = value;
      list.appendChild(item);
    });
  }

  function renderFolderPreviewSelectors(proposed) {
    const list = byId("fo-folder-preview-selectors");
    if (!list) return;
    list.replaceChildren();
    const rows = [];
    [
      ["audio.keepTracks", proposed?.audio?.keepTracks],
      ["audio.dropTracks", proposed?.audio?.dropTracks],
      ["subtitles.keepTracks", proposed?.subtitles?.keepTracks],
      ["subtitles.dropTracks", proposed?.subtitles?.dropTracks],
    ].forEach(([field, rules]) => {
      (Array.isArray(rules) ? rules : []).forEach((rule) => {
        const text = folderPreviewSelectorText(rule);
        if (text) rows.push(`${field}: ${text}`);
      });
    });
    if (!rows.length) {
      const item = document.createElement("li");
      item.className = "fo-folder-preview-empty";
      item.textContent = "No language or signature selectors are set; preview will show folder coverage only.";
      list.appendChild(item);
      return;
    }
    rows.forEach((row) => {
      const item = document.createElement("li");
      item.textContent = row;
      list.appendChild(item);
    });
  }

  function folderPreviewProposalHasRules(proposed) {
    return Boolean(
      isPlainObject(proposed)
        && (
          Object.keys(isPlainObject(proposed.audio) ? proposed.audio : {}).length
          || Object.keys(isPlainObject(proposed.subtitles) ? proposed.subtitles : {}).length
        ),
    );
  }

  function setFolderPreviewConfirmationsChecked(checked) {
    [
      "fo-folder-confirm-future-files",
      "fo-folder-confirm-file-overrides",
      "fo-folder-confirm-no-stream-index",
    ].forEach((id) => {
      const input = byId(id);
      if (input) input.checked = Boolean(checked);
    });
  }

  function folderPreviewConfirmationsSatisfied() {
    return [
      "fo-folder-confirm-future-files",
      "fo-folder-confirm-file-overrides",
      "fo-folder-confirm-no-stream-index",
    ].every((id) => Boolean(byId(id)?.checked));
  }

  function setFolderPreviewSaveDisabled(disabled) {
    const saveButton = byId("fo-folder-preview-save");
    if (saveButton) saveButton.disabled = Boolean(disabled);
  }

  function folderPreviewSaveCanSubmit() {
    const payload = foLastFolderPreviewPayload;
    const request = foLastFolderPreviewRequest;
    return Boolean(
      payload
        && payload.ok !== false
        && payload.can_save_folder_rule !== false
        && request
        && request.folderPath
        && folderPreviewProposalHasRules(request.proposedOverride)
        && !folderPreviewSaveBlockedByLibraryRoot(request.folderPath, payload)
        && folderPreviewConfirmationsSatisfied(),
    );
  }

  function syncFolderPreviewSaveState() {
    setFolderPreviewSaveDisabled(!folderPreviewSaveCanSubmit());
  }

  function resetFolderPreviewResult(message = "") {
    foLastFolderPreviewPayload = null;
    foLastFolderPreviewRequest = null;
    setFolderPreviewSaveDisabled(true);
    if (message) setTrackText("fo-folder-preview-status", message);
  }

  function invalidateFolderPreviewAfterRuleChange() {
    const panel = byId("fo-folder-preview-panel");
    if (!panel || panel.hidden || (!foLastFolderPreviewPayload && !foLastFolderPreviewRequest)) return;
    resetFolderPreviewResult("Folder selectors changed. Run preview again before saving.");
  }

  function handleFolderPreviewScopeChange() {
    const folderPath = selectedFolderPreviewPath();
    resetFolderPreviewResult("Folder scope changed. Run preview before saving.");
    setFolderPreviewConfirmationsChecked(false);
    setTrackText("fo-folder-preview-path", folderPath || "Folder unavailable");
    setTrackText("fo-folder-preview-scope", folderPath ? `Appears to be: ${folderPreviewScopeLabel(folderPath, {})}.` : "");
    setTrackText("fo-folder-preview-counts", "");
    setTrackText("fo-folder-preview-library-note", "");
    const libraryButton = byId("fo-folder-preview-library-settings");
    if (libraryButton) libraryButton.hidden = true;
    renderFolderPreviewSelectors(buildFolderPreviewProposal());
    ["fo-folder-preview-conflicts", "fo-folder-preview-warnings", "fo-folder-preview-samples"].forEach(clearElementChildren);
  }

  function clearFolderRulePreviewPanel() {
    const panel = byId("fo-folder-preview-panel");
    if (panel) panel.hidden = true;
    foLastFolderPreviewPayload = null;
    foLastFolderPreviewRequest = null;
    setFolderPreviewConfirmationsChecked(false);
    setFolderPreviewSaveDisabled(true);
    [
      "fo-folder-preview-path",
      "fo-folder-preview-scope",
      "fo-folder-preview-counts",
      "fo-folder-preview-status",
      "fo-folder-preview-library-note",
    ].forEach((id) => {
      const el = byId(id);
      if (el) el.textContent = "";
    });
    ["fo-folder-preview-selectors", "fo-folder-preview-conflicts", "fo-folder-preview-warnings", "fo-folder-preview-samples"].forEach(clearElementChildren);
    const scopeSelect = byId("fo-folder-preview-scope-select");
    if (scopeSelect) scopeSelect.replaceChildren();
    const libraryButton = byId("fo-folder-preview-library-settings");
    if (libraryButton) libraryButton.hidden = true;
  }

  function renderFolderPreviewPayload(payload, folderPath, proposedOverride) {
    const panel = byId("fo-folder-preview-panel");
    if (panel) panel.hidden = false;
    const impact = isPlainObject(payload?.impact) ? payload.impact : {};
    const knownCount = Number(impact.known_file_count || 0);
    const previewedCount = Number(impact.previewed_file_count || 0);
    const partial = Boolean(impact.partial);
    const blockedByLibraryRoot = folderPreviewSaveBlockedByLibraryRoot(folderPath, payload);
    const canSavePreview = payload?.can_save_folder_rule !== false && !blockedByLibraryRoot;
    const hasRules = folderPreviewProposalHasRules(proposedOverride);
    const handoffMessage = folderPreviewLibraryHandoffMessage(folderPath, payload);
    setTrackText("fo-folder-preview-path", folderPath || "Folder unavailable");
    setTrackText("fo-folder-preview-scope", `Appears to be: ${folderPreviewScopeLabel(folderPath, payload)}.`);
    setTrackText("fo-folder-preview-counts", `Known files: ${knownCount}. Previewed samples: ${previewedCount}. Partial preview: ${partial ? "yes" : "no"}.`);
    setTrackText(
      "fo-folder-preview-status",
      !hasRules
        ? "Preview succeeded, but no language or signature selectors are set. Add selectors and preview again before saving."
        : canSavePreview
        ? "Preview succeeded. Confirm the folder-rule acknowledgements before saving. Future files under this folder may be affected."
        : blockedByLibraryRoot
        ? `${handoffMessage} Folder-rule save is blocked for library-root scope.`
        : "Preview succeeded, but this folder scope cannot be saved here.",
    );
    setFolderPreviewLibraryHandoff(folderPath, payload);
    renderFolderPreviewSelectors(proposedOverride);

    const conflicts = byId("fo-folder-preview-conflicts");
    if (conflicts) {
      conflicts.replaceChildren();
      appendFolderPreviewListItems(conflicts, payload?.conflicts, (conflict) => {
        if (!isPlainObject(conflict)) return "";
        const path = String(conflict.path || "").trim();
        const reason = String(conflict.reason || "").replace(/_/g, " ").trim();
        return [path, reason || "override conflict"].filter(Boolean).join(" — ");
      });
    }

    const warnings = byId("fo-folder-preview-warnings");
    if (warnings) {
      warnings.replaceChildren();
      const aggregateWarnings = Array.isArray(payload?.warnings) ? payload.warnings : [];
      const sampleWarnings = [];
      (Array.isArray(payload?.sample_rows) ? payload.sample_rows : []).forEach((sample) => {
        (Array.isArray(sample?.warnings) ? sample.warnings : []).forEach((warning) => sampleWarnings.push(warning));
      });
      appendFolderPreviewListItems(warnings, aggregateWarnings.concat(sampleWarnings), folderPreviewWarningText);
    }

    const samples = byId("fo-folder-preview-samples");
    if (samples) {
      samples.replaceChildren();
      appendFolderPreviewListItems(samples, payload?.sample_rows, (sample) => {
        if (!isPlainObject(sample)) return "";
        const path = String(sample.path || "").trim();
        const audioCount = Number(sample.audio_track_count || 0);
        const subtitleCount = Number(sample.subtitle_track_count || 0);
        const audioMatches = Array.isArray(sample.matched_audio_tracks) ? sample.matched_audio_tracks.length : 0;
        const subtitleMatches = Array.isArray(sample.matched_subtitle_tracks) ? sample.matched_subtitle_tracks.length : 0;
        return `${path || "Sample row"} — audio ${audioCount}, subtitles ${subtitleCount}, matched audio ${audioMatches}, matched subtitles ${subtitleMatches}`;
      });
    }
    syncFolderPreviewSaveState();
  }

  async function openFolderRulePreviewPanel() {
    if (!foCurrentPath) {
      setStatus("No file selected for folder preview.");
      return;
    }
    const panel = byId("fo-folder-preview-panel");
    if (panel) panel.hidden = false;
    renderFolderPreviewScopeOptions();
    const folderPath = selectedFolderPreviewPath();
    if (!folderPath) {
      setStatus("Cannot derive a folder path from this file.");
      return;
    }
    resetFolderPreviewResult("");
    setFolderPreviewConfirmationsChecked(false);
    const proposedOverride = buildFolderPreviewProposal();
    setTrackText("fo-folder-preview-path", folderPath);
    setTrackText("fo-folder-preview-scope", "Checking folder scope...");
    setTrackText("fo-folder-preview-counts", "");
    setTrackText("fo-folder-preview-status", "Loading folder impact preview...");
    renderFolderPreviewSelectors(proposedOverride);
    ["fo-folder-preview-conflicts", "fo-folder-preview-warnings", "fo-folder-preview-samples"].forEach(clearElementChildren);

    try {
      const result = await apiPost("/api/queue/file-overrides/folder-preview", {
        folder_path: folderPath,
        proposed_override: proposedOverride,
        options: {
          sample_limit: 25,
          use_cached_track_metadata_only: true,
        },
      });
      if (!result || result.ok === false) {
        setTrackText("fo-folder-preview-status", "Folder preview failed: " + backendErrorMessage(result, "Folder preview failed."));
        return;
      }
      foLastFolderPreviewPayload = result;
      foLastFolderPreviewRequest = { folderPath, proposedOverride };
      renderFolderPreviewPayload(result, folderPath, proposedOverride);
    } catch (err) {
      setTrackText("fo-folder-preview-status", "Folder preview failed: " + (err.message || err));
    }
  }

  async function saveFolderRuleForPreview() {
    if (!foLastFolderPreviewPayload || !foLastFolderPreviewRequest) {
      setTrackText("fo-folder-preview-status", "Run a successful folder preview before saving.");
      syncFolderPreviewSaveState();
      return;
    }
    if (!folderPreviewProposalHasRules(foLastFolderPreviewRequest.proposedOverride)) {
      setTrackText("fo-folder-preview-status", "Add at least one language or signature selector before saving a folder rule.");
      syncFolderPreviewSaveState();
      return;
    }
    if (!folderPreviewConfirmationsSatisfied()) {
      setTrackText("fo-folder-preview-status", "Confirm all folder-rule acknowledgements before saving.");
      syncFolderPreviewSaveState();
      return;
    }
    if (!folderPreviewSaveCanSubmit()) {
      setTrackText("fo-folder-preview-status", "This folder preview cannot be saved.");
      syncFolderPreviewSaveState();
      return;
    }

    setFolderPreviewSaveDisabled(true);
    setTrackText("fo-folder-preview-status", "Saving folder rule...");
    try {
      const result = await apiPost("/api/queue/file-overrides/folder-rule", {
        folder_path: foLastFolderPreviewRequest.folderPath,
        override: foLastFolderPreviewRequest.proposedOverride,
        confirmation: {
          acknowledged_future_files: true,
          acknowledged_file_overrides_win: true,
        },
      });
      if (!result || result.ok === false) {
        setTrackText("fo-folder-preview-status", "Folder rule save failed: " + backendErrorMessage(result, "Folder rule save failed."));
        syncFolderPreviewSaveState();
        return;
      }
      await loadFileOverrideEffectiveForPath(foCurrentPath, foCurrentItem);
      setTrackText("fo-folder-preview-status", "Folder rule saved. Effective settings and queue state refreshed when available.");
      setStatus("Folder rule saved. Takes effect on next pipeline round.");
      if (typeof appendCommandResult === "function") appendCommandResult(result);
      if (typeof refreshAll === "function") await refreshAll();
      if (!byId("fo-folder-rules-panel")?.hidden) await loadFolderRulesForDrawer();
      foLastFolderPreviewPayload = null;
      foLastFolderPreviewRequest = null;
      setFolderPreviewConfirmationsChecked(false);
      setFolderPreviewSaveDisabled(true);
    } catch (err) {
      setTrackText("fo-folder-preview-status", "Folder rule save failed: " + (err.message || err));
      syncFolderPreviewSaveState();
    }
  }

  async function loadRoutePreviewForPayload(payload) {
    const proposed = routePreviewProposalFromPayload(payload);
    if (!foCurrentPath || !Object.keys(proposed).length) {
      clearRoutePreviewStatus();
      return { ok: true, impact: { requires_confirmation: false }, warnings: [] };
    }
    const status = byId("fo-route-preview-status");
    if (status) {
      status.hidden = false;
      status.textContent = "Checking route impact...";
      delete status.dataset.risk;
    }
    const result = await apiPost("/api/queue/file-overrides/route-preview", {
      path: foCurrentPath,
      proposed_override: proposed,
    });
    renderRoutePreviewPayload(result);
    return result;
  }

  function folderRulePathLooksFile(path) {
    const text = String(path || "").trim();
    if (!text || /[\\/]$/.test(text)) return false;
    const leaf = folderPreviewLeaf(text).toLowerCase();
    return Array.from(FOLDER_RULE_FILE_SUFFIXES).some((suffix) => leaf.endsWith(suffix));
  }

  function folderRuleEntriesFromManifestPayload(payload) {
    const entries = isPlainObject(payload?.entries) ? payload.entries : {};
    return Object.entries(entries)
      .filter(([path, entry]) => String(path || "").trim() && isPlainObject(entry) && !folderRulePathLooksFile(path))
      .map(([path, entry]) => ({ path, entry }))
      .sort((left, right) => left.path.localeCompare(right.path));
  }

  function folderRuleOverrideForPreview(entry) {
    const proposed = {};
    if (isPlainObject(entry?.audio)) proposed.audio = entry.audio;
    if (isPlainObject(entry?.subtitles)) proposed.subtitles = entry.subtitles;
    return proposed;
  }

  function folderRuleSelectorSummary(rule) {
    if (typeof rule === "string") {
      const language = rule.trim();
      return language ? `language=${language}` : "";
    }
    return folderPreviewSelectorText(rule);
  }

  function folderRuleSummary(entry) {
    const rows = [];
    [
      ["audio.keepTracks", entry?.audio?.keepTracks],
      ["audio.dropTracks", entry?.audio?.dropTracks],
      ["subtitles.keepTracks", entry?.subtitles?.keepTracks],
      ["subtitles.dropTracks", entry?.subtitles?.dropTracks],
    ].forEach(([field, rules]) => {
      (Array.isArray(rules) ? rules : []).forEach((rule) => {
        const text = folderRuleSelectorSummary(rule);
        if (text) rows.push(`${field}: ${text}`);
      });
    });
    if (hasOwnValue(entry?.subtitles, "stripAll")) {
      rows.push(`subtitles.stripAll=${Boolean(entry.subtitles.stripAll)}`);
    }
    if (rows.length) return rows.join("; ");
    if (isPlainObject(entry?.routing) || isPlainObject(entry?.video)) {
      return "Contains processing settings; use Library settings for broad stable defaults.";
    }
    return "No folder-safe audio/subtitle selectors in this entry.";
  }

  function folderRuleNode(index) {
    return document.querySelector(`[data-fo-folder-rule-index="${index}"]`);
  }

  function folderRuleConflictText(conflict) {
    if (!isPlainObject(conflict)) return String(conflict || "").trim();
    const path = String(conflict.path || "").trim();
    const reason = String(conflict.reason || "override conflict").replace(/_/g, " ").trim();
    return [path, reason].filter(Boolean).join(" — ");
  }

  function renderFolderRuleConflicts(list, conflicts) {
    if (!list) return;
    list.replaceChildren();
    appendFolderPreviewListItems(list, conflicts, folderRuleConflictText);
  }

  function clearFolderRuleManagementPanel() {
    const panel = byId("fo-folder-rules-panel");
    if (panel) panel.hidden = true;
    foFolderRules = [];
    clearElementChildren("fo-folder-rules-list");
    setTrackText("fo-folder-rules-status", "");
  }

  function renderFolderRules(rules) {
    const panel = byId("fo-folder-rules-panel");
    const list = byId("fo-folder-rules-list");
    if (panel) panel.hidden = false;
    foFolderRules = Array.isArray(rules) ? rules : [];
    if (!list) return;
    list.replaceChildren();

    if (!foFolderRules.length) {
      const empty = document.createElement("li");
      empty.className = "fo-folder-rule-item";
      empty.textContent = "No folder-prefix rules are saved.";
      list.appendChild(empty);
      return;
    }

    foFolderRules.forEach((rule, index) => {
      const item = document.createElement("li");
      item.className = "fo-folder-rule-item";
      item.dataset.foFolderRuleIndex = String(index);

      const path = document.createElement("p");
      path.className = "fo-folder-rule-path";
      path.textContent = rule.path;
      item.appendChild(path);

      const summary = document.createElement("p");
      summary.className = "fo-folder-rule-summary";
      summary.textContent = folderRuleSummary(rule.entry);
      item.appendChild(summary);

      const meta = document.createElement("p");
      meta.className = "fo-folder-rule-meta";
      meta.dataset.foFolderRuleMeta = "";
      meta.textContent = "Affected count not previewed yet.";
      item.appendChild(meta);

      const libraryNote = document.createElement("p");
      libraryNote.className = "fo-folder-rule-library-note";
      libraryNote.dataset.foFolderRuleLibraryNote = "";
      item.appendChild(libraryNote);

      const conflicts = document.createElement("ul");
      conflicts.className = "fo-folder-rule-conflicts";
      conflicts.dataset.foFolderRuleConflicts = "";
      renderFolderRuleConflicts(conflicts, []);
      item.appendChild(conflicts);

      const actions = document.createElement("div");
      actions.className = "fo-folder-rule-actions";
      const preview = document.createElement("button");
      preview.type = "button";
      preview.className = "secondary-button";
      preview.dataset.foFolderRulePreview = String(index);
      preview.textContent = "Re-preview";
      const clear = document.createElement("button");
      clear.type = "button";
      clear.className = "secondary-button";
      clear.dataset.foFolderRuleClear = String(index);
      clear.textContent = "Clear folder rule";
      actions.append(preview, clear);
      item.appendChild(actions);

      list.appendChild(item);
    });
  }

  function renderFolderRulePreviewResult(rule, index, payload) {
    const item = folderRuleNode(index);
    if (!item) return;
    const meta = item.querySelector("[data-fo-folder-rule-meta]");
    const libraryNote = item.querySelector("[data-fo-folder-rule-library-note]");
    const conflicts = item.querySelector("[data-fo-folder-rule-conflicts]");
    const impact = isPlainObject(payload?.impact) ? payload.impact : {};
    const knownCount = Number(impact.known_file_count || 0);
    const previewedCount = Number(impact.previewed_file_count || 0);
    const partial = Boolean(impact.partial);
    if (meta) {
      meta.textContent = `Known files: ${knownCount}. Previewed samples: ${previewedCount}. Partial preview: ${partial ? "yes" : "no"}.`;
    }
    if (libraryNote) {
      libraryNote.textContent = folderPreviewLibraryHandoffMessage(rule.path, payload);
    }
    renderFolderRuleConflicts(conflicts, payload?.conflicts);
  }

  async function previewFolderRuleForManagement(rule, index, options = {}) {
    if (!rule || !rule.path) return;
    const item = folderRuleNode(index);
    const meta = item?.querySelector?.("[data-fo-folder-rule-meta]");
    if (meta) meta.textContent = "Loading cached preview...";
    if (!options.silent) setTrackText("fo-folder-rules-status", "Loading folder rule preview...");

    try {
      const result = await apiPost("/api/queue/file-overrides/folder-preview", {
        folder_path: rule.path,
        proposed_override: folderRuleOverrideForPreview(rule.entry),
        options: {
          sample_limit: 25,
          use_cached_track_metadata_only: true,
        },
      });
      if (!result || result.ok === false) {
        const message = "Folder rule preview failed: " + backendErrorMessage(result, "Folder rule preview failed.");
        if (meta) meta.textContent = message;
        if (!options.silent) setTrackText("fo-folder-rules-status", message);
        return;
      }
      renderFolderRulePreviewResult(rule, index, result);
      if (!options.silent) setTrackText("fo-folder-rules-status", "Folder rule preview refreshed.");
    } catch (err) {
      const message = "Folder rule preview failed: " + (err.message || err);
      if (meta) meta.textContent = message;
      if (!options.silent) setTrackText("fo-folder-rules-status", message);
    }
  }

  async function loadFolderRulesForDrawer() {
    const panel = byId("fo-folder-rules-panel");
    if (panel) panel.hidden = false;
    setTrackText("fo-folder-rules-status", "Loading folder rules...");
    try {
      const result = await apiGet(FILE_OVERRIDES_ROUTE);
      const rules = folderRuleEntriesFromManifestPayload(result);
      renderFolderRules(rules);
      setTrackText(
        "fo-folder-rules-status",
        rules.length
          ? `${rules.length} folder rule(s) loaded. Re-preview uses cached track metadata only. File-level overrides remain when a folder rule is cleared.`
          : "No folder-prefix rules are saved.",
      );
      await Promise.allSettled(rules.map((rule, index) => previewFolderRuleForManagement(rule, index, { silent: true })));
    } catch (err) {
      renderFolderRules([]);
      setTrackText("fo-folder-rules-status", "Error loading folder rules: " + (err.message || err));
    }
  }

  async function clearFolderRuleFromManagement(rule, index) {
    if (!rule || !rule.path) return;
    const confirmed = typeof window.confirm !== "function"
      || window.confirm(`Clear folder rule for ${rule.path}? File-level overrides remain.`);
    if (!confirmed) return;

    const item = folderRuleNode(index);
    const meta = item?.querySelector?.("[data-fo-folder-rule-meta]");
    if (meta) meta.textContent = "Clearing folder rule...";
    setTrackText("fo-folder-rules-status", "Clearing folder rule...");
    try {
      const result = await apiPost("/api/queue/file-overrides/folder-rule", {
        folder_path: rule.path,
        clear: true,
      });
      if (!result || result.ok === false) {
        setTrackText("fo-folder-rules-status", "Folder rule clear failed: " + backendErrorMessage(result, "Folder rule clear failed."));
        return;
      }
      if (typeof appendCommandResult === "function") appendCommandResult(result);
      if (foCurrentPath) await loadFileOverrideEffectiveForPath(foCurrentPath, foCurrentItem);
      if (typeof refreshAll === "function") await refreshAll();
      await loadFolderRulesForDrawer();
      setStatus("Folder rule cleared. File-level overrides remain.");
      setTrackText("fo-folder-rules-status", "Folder rule cleared. File-level overrides remain.");
    } catch (err) {
      setTrackText("fo-folder-rules-status", "Folder rule clear failed: " + (err.message || err));
    }
  }

  function handleFolderRuleManagementClick(event) {
    const previewButton = event.target?.closest?.("[data-fo-folder-rule-preview]");
    if (previewButton) {
      const index = Number(previewButton.dataset.foFolderRulePreview);
      const rule = foFolderRules[index];
      if (rule) previewFolderRuleForManagement(rule, index);
      return;
    }
    const clearButton = event.target?.closest?.("[data-fo-folder-rule-clear]");
    if (clearButton) {
      const index = Number(clearButton.dataset.foFolderRuleClear);
      const rule = foFolderRules[index];
      if (rule) clearFolderRuleFromManagement(rule, index);
    }
  }

  function openLibrarySettingsFromFolderHandoff() {
    closeFileSettingsDrawer();
    if (typeof window.showPage === "function") {
      window.showPage("libraries");
    } else {
      setStatus("Open the Libraries page to change broad stable defaults.");
    }
  }

  async function ensureRoutePreviewAllowsSave(payload) {
    if (!payloadHasRouteVideoOverride(payload)) return true;
    let result;
    try {
      result = await loadRoutePreviewForPayload(payload);
    } catch (err) {
      setStatus("Error previewing route impact: " + (err.message || err));
      return false;
    }
    if (!result || result.ok === false) {
      setStatus("Error: " + backendErrorMessage(result, "Route preview failed."));
      return false;
    }
    if (result?.impact?.requires_confirmation && !byId("fo-route-risk-confirm")?.checked) {
      setStatus("Confirm the route impact before saving this processing override.");
      return false;
    }
    return true;
  }

  async function refreshRoutePreviewFromCurrentForm() {
    if (!foCurrentPath) return;
    const payload = buildOverridePayload();
    if (!payloadHasRouteVideoOverride(payload)) {
      clearRoutePreviewStatus();
      return;
    }
    try {
      await loadRoutePreviewForPayload(payload);
    } catch (err) {
      const status = byId("fo-route-preview-status");
      if (status) {
        status.hidden = false;
        status.textContent = "Route preview failed: " + (err.message || err);
        status.dataset.risk = "high";
      }
    }
  }

  function scheduleRoutePreviewFromCurrentForm() {
    const checkbox = byId("fo-route-risk-confirm");
    if (checkbox) checkbox.checked = false;
    if (foRoutePreviewTimer) clearTimeout(foRoutePreviewTimer);
    foRoutePreviewTimer = setTimeout(() => {
      foRoutePreviewTimer = null;
      refreshRoutePreviewFromCurrentForm();
    }, 250);
  }

  // ---------------------------------------------------------------------------
  // API calls
  // ---------------------------------------------------------------------------

  async function loadFileOverrideForPath(path) {
    if (!path) { setStatus("No source path — cannot load override."); return; }
    try {
      const url  = FILE_OVERRIDES_ROUTE + "?path=" + encodeURIComponent(path);
      const data = await apiGet(url);
      if (data && data.entry) {
        populateDrawerForm(data.entry);
        setStatus("Override loaded.");
      } else {
        clearDrawerForm({
          resetRouteControls: !foLastEffectivePayload,
          resetTrackMetadata: !foLastEffectivePayload,
        });
        setStatus("No override set for this file.");
      }
    } catch (err) {
      setStatus("Error loading override: " + (err.message || err));
    }
  }

  async function loadFileOverrideEffectiveForPath(path, item) {
    if (!path) return false;
    try {
      const url = FILE_OVERRIDES_EFFECTIVE_ROUTE + "?path=" + encodeURIComponent(path);
      const data = await apiGet(url);
      const applied = applyFileOverrideEffectivePayload(data, item);
      if (applied && !isPlainObject(data?.track_metadata)) await loadFileOverrideTracksForPath(path);
      return applied;
    } catch (_err) {
      await loadFileOverrideTracksForPath(path);
      return false;
    }
  }

  async function loadFileOverrideTracksForPath(path) {
    if (!path) return false;
    try {
      const url = FILE_OVERRIDES_TRACKS_ROUTE + "?path=" + encodeURIComponent(path);
      const data = await apiGet(url);
      renderDrawerTrackMetadata({
        track_metadata: trackMetadataFromTracksPayload(data),
        track_selection_preview: {},
      });
      return true;
    } catch (_err) {
      return false;
    }
  }

  async function saveFileOverrideForPath() {
    if (!foCurrentPath) { setStatus("No file selected."); return; }
    const payload = buildOverridePayload();
    if (!payload) { setStatus("No overrides specified — nothing to save."); return; }
    if (!validateExactTrackSelectionsBeforeSave()) return;
    const hasRouteVideoOverride = payloadHasRouteVideoOverride(payload);

    if (!(await ensureRoutePreviewAllowsSave(payload))) return;

    setStatus("Saving…");
    try {
      const result = await apiPost("/api/queue/file-overrides", payload);
      if (result && result.ok) {
        populateDrawerForm({
          audio: payload.audio || {},
          subtitles: payload.subtitles || {},
          routing: payload.routing || {},
          video: payload.video || {},
        });
        await loadFileOverrideEffectiveForPath(foCurrentPath, foCurrentItem);
        if (hasRouteVideoOverride) await loadRoutePreviewForPayload(payload);
        setStatus("Override saved. Takes effect on next pipeline round.");
        if (typeof appendCommandResult === "function") appendCommandResult(result);
        if (typeof refreshAll === "function") await refreshAll();
      } else {
        setStatus("Error: " + backendErrorMessage(result));
      }
    } catch (err) {
      setStatus("Error saving override: " + (err.message || err));
    }
  }

  async function clearFileOverrideField(fieldKey) {
    const fieldPath = DRAWER_FIELD_PATHS[fieldKey];
    if (!foCurrentPath) { setStatus("No file selected."); return; }
    if (!fieldPath) { setStatus("Cannot clear this override field."); return; }

    const button = document.querySelector(`[data-fo-use-inherited="${fieldKey}"]`);
    if (button) button.disabled = true;
    setStatus("Clearing field override…");
    try {
      const result = await apiPost("/api/queue/file-overrides", {
        path: foCurrentPath,
        clear_fields: [fieldPath],
      });
      if (result && result.ok) {
        resetExactTrackActionsForField(fieldKey);
        const reloaded = await loadFileOverrideEffectiveForPath(foCurrentPath, foCurrentItem);
        if (ROUTE_FIELD_KEYS.includes(fieldKey)) await refreshRoutePreviewFromCurrentForm();
        setStatus(reloaded ? "Override field cleared. Inherited value will be used." : "Override field cleared, but effective settings could not be reloaded.");
        if (typeof appendCommandResult === "function") appendCommandResult(result);
        if (typeof refreshAll === "function") await refreshAll();
      } else {
        if (button) button.disabled = false;
        setStatus("Error: " + backendErrorMessage(result));
      }
    } catch (err) {
      if (button) button.disabled = false;
      setStatus("Error clearing override field: " + (err.message || err));
    }
  }

  async function clearFileOverrideForPath() {
    if (!foCurrentPath) { setStatus("No file selected."); return; }
    setStatus("Clearing…");
    try {
      const result = await apiPost("/api/queue/file-overrides", { path: foCurrentPath, clear: true });
      if (result && result.ok) {
        clearDrawerForm();
        await loadFileOverrideEffectiveForPath(foCurrentPath, foCurrentItem);
        setStatus("Override cleared.");
        if (typeof appendCommandResult === "function") appendCommandResult(result);
        if (typeof refreshAll === "function") await refreshAll();
      } else {
        setStatus("Error: " + backendErrorMessage(result));
      }
    } catch (err) {
      setStatus("Error clearing override: " + (err.message || err));
    }
  }

  // ---------------------------------------------------------------------------
  // Wiring
  // ---------------------------------------------------------------------------

  function initFileSettingsDrawer() {
    const overlay  = byId("fo-overlay");
    const closeBtn = byId("fo-drawer-close");
    const saveBtn  = byId("fo-drawer-save");
    const clearBtn = byId("fo-drawer-clear");
    const folderPreviewBtn = byId("fo-folder-preview-open");
    const folderPreviewSaveBtn = byId("fo-folder-preview-save");
    const folderPreviewScopeSelect = byId("fo-folder-preview-scope-select");
    const folderPreviewLibraryBtn = byId("fo-folder-preview-library-settings");
    const folderRulesBtn = byId("fo-folder-rules-open");
    const folderRulesRefreshBtn = byId("fo-folder-rules-refresh");
    const folderRulesLibraryBtn = byId("fo-folder-rules-library-settings");
    const folderRulesList = byId("fo-folder-rules-list");
    const stripAll = byId("fo-sub-strip-all");

    if (overlay)  overlay.addEventListener("click", closeFileSettingsDrawer);
    if (closeBtn) closeBtn.addEventListener("click", closeFileSettingsDrawer);
    if (saveBtn)  saveBtn.addEventListener("click",  saveFileOverrideForPath);
    if (clearBtn) clearBtn.addEventListener("click", clearFileOverrideForPath);
    if (folderPreviewBtn) folderPreviewBtn.addEventListener("click", openFolderRulePreviewPanel);
    if (folderPreviewSaveBtn) folderPreviewSaveBtn.addEventListener("click", saveFolderRuleForPreview);
    if (folderPreviewScopeSelect) folderPreviewScopeSelect.addEventListener("change", handleFolderPreviewScopeChange);
    if (folderPreviewLibraryBtn) folderPreviewLibraryBtn.addEventListener("click", openLibrarySettingsFromFolderHandoff);
    if (folderRulesBtn) folderRulesBtn.addEventListener("click", loadFolderRulesForDrawer);
    if (folderRulesRefreshBtn) folderRulesRefreshBtn.addEventListener("click", loadFolderRulesForDrawer);
    if (folderRulesLibraryBtn) folderRulesLibraryBtn.addEventListener("click", openLibrarySettingsFromFolderHandoff);
    if (folderRulesList) folderRulesList.addEventListener("click", handleFolderRuleManagementClick);
    if (stripAll) stripAll.addEventListener("change", syncSubFilterFields);
    [
      "fo-folder-confirm-future-files",
      "fo-folder-confirm-file-overrides",
      "fo-folder-confirm-no-stream-index",
    ].forEach((id) => {
      const checkbox = byId(id);
      if (checkbox) checkbox.addEventListener("change", syncFolderPreviewSaveState);
    });
    [
      "fo-audio-keep-langs",
      "fo-audio-drop-langs",
      "fo-sub-keep-langs",
      "fo-sub-drop-langs",
      "fo-sub-strip-all",
    ].forEach((id) => {
      const control = byId(id);
      if (control) {
        control.addEventListener("change", invalidateFolderPreviewAfterRuleChange);
        control.addEventListener("input", invalidateFolderPreviewAfterRuleChange);
      }
    });
    document.querySelectorAll("[data-fo-use-inherited]").forEach((button) => {
      button.addEventListener("click", () => clearFileOverrideField(button.dataset.foUseInherited || ""));
    });
    document.querySelectorAll("[data-fo-route-control]").forEach((control) => {
      control.addEventListener("change", scheduleRoutePreviewFromCurrentForm);
    });
    document.addEventListener("change", (event) => {
      if (event.target?.matches?.("[data-fo-track-action]")) invalidateFolderPreviewAfterRuleChange();
    });

    document.addEventListener("keydown", handleFileSettingsDrawerKeydown);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initFileSettingsDrawer);
  } else {
    initFileSettingsDrawer();
  }

})();
