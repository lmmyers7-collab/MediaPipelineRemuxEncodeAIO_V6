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
      openFileSettingsDrawer: typeof openFileSettingsDrawer === "function" ? openFileSettingsDrawer : window.openFileSettingsDrawer,
      queueRowKey,
      queueTableRowStatus,
      selectQueueRow,
      shortenPath: typeof shortenPath === "function" ? shortenPath : window.shortenPath,
    })
    : {};
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

  // Currently-open source path
  let foCurrentPath = "";

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

  /** Populate a lang-list input from an array of rule objects */
  function rulesToLangInput(rules) {
    if (!Array.isArray(rules) || !rules.length) return "";
    return rules.map((r) => r.language || "").filter(Boolean).join(", ");
  }

  function byId(id) { return document.getElementById(id); }
  function setStatus(msg) {
    const el = byId("fo-drawer-status");
    if (el) el.textContent = msg;
  }

  // ---------------------------------------------------------------------------
  // Drawer open / close
  // ---------------------------------------------------------------------------

  function openFileSettingsDrawer(item) {
    const path = item.source_path || "";
    foCurrentPath = path;

    const titleEl = byId("fo-drawer-title");
    const pathEl  = byId("fo-drawer-path");
    const name    = item.display_name || item.relative_path || path || "Unknown";
    if (titleEl) titleEl.textContent = "File Settings — " + (name.length > 40 ? "…" + name.slice(-40) : name);
    if (pathEl) pathEl.textContent = path;

    clearDrawerForm();
    setStatus("Loading current override…");
    loadFileOverrideForPath(path);

    const overlay = byId("fo-overlay");
    const drawer  = byId("fo-drawer");
    if (overlay) { overlay.hidden = false; overlay.removeAttribute("aria-hidden"); }
    if (drawer)  { drawer.hidden  = false; }

    // Focus the close button for a11y
    const closeBtn = byId("fo-drawer-close");
    if (closeBtn) setTimeout(() => closeBtn.focus(), 50);
  }

  function closeFileSettingsDrawer() {
    const overlay = byId("fo-overlay");
    const drawer  = byId("fo-drawer");
    if (overlay) { overlay.hidden = true; overlay.setAttribute("aria-hidden", "true"); }
    if (drawer)  { drawer.hidden  = true; }
    foCurrentPath = "";
  }

  // ---------------------------------------------------------------------------
  // Form helpers
  // ---------------------------------------------------------------------------

  function clearDrawerForm() {
    const ids = ["fo-audio-keep-langs","fo-audio-drop-langs","fo-sub-keep-langs","fo-sub-drop-langs"];
    ids.forEach((id) => { const el = byId(id); if (el) el.value = ""; });
    const maxCh = byId("fo-audio-max-channels");
    if (maxCh) maxCh.value = "";
    const stripAll = byId("fo-sub-strip-all");
    if (stripAll) stripAll.checked = false;
    syncSubFilterFields();
  }

  function syncSubFilterFields() {
    const stripAll = byId("fo-sub-strip-all");
    const fields   = byId("fo-sub-filter-fields");
    if (!fields) return;
    if (stripAll && stripAll.checked) {
      fields.style.opacity = "0.4";
      fields.style.pointerEvents = "none";
    } else {
      fields.style.opacity = "";
      fields.style.pointerEvents = "";
    }
  }

  function populateDrawerForm(entry) {
    // entry = { audio: {...}, subtitles: {...} } or null
    const audio = (entry && entry.audio)     || {};
    const subs  = (entry && entry.subtitles) || {};

    const keepLangs = byId("fo-audio-keep-langs");
    const dropLangs = byId("fo-audio-drop-langs");
    const maxCh     = byId("fo-audio-max-channels");
    if (keepLangs) keepLangs.value = rulesToLangInput(audio.keepTracks);
    if (dropLangs) dropLangs.value = rulesToLangInput(audio.dropTracks);
    if (maxCh) {
      const v = audio.maxChannels != null ? String(audio.maxChannels) : "";
      maxCh.value = ["2","6","8"].includes(v) ? v : "";
    }

    const stripAll   = byId("fo-sub-strip-all");
    const subKeep    = byId("fo-sub-keep-langs");
    const subDrop    = byId("fo-sub-drop-langs");
    if (stripAll) stripAll.checked = Boolean(subs.stripAll);
    if (subKeep) subKeep.value = rulesToLangInput(subs.keepTracks);
    if (subDrop) subDrop.value = rulesToLangInput(subs.dropTracks);
    syncSubFilterFields();
  }

  function buildOverridePayload() {
    const keepLangList = parseLangList(byId("fo-audio-keep-langs")?.value);
    const dropLangList = parseLangList(byId("fo-audio-drop-langs")?.value);
    const maxChVal     = byId("fo-audio-max-channels")?.value || "";
    const stripAll     = Boolean(byId("fo-sub-strip-all")?.checked);
    const subKeepList  = parseLangList(byId("fo-sub-keep-langs")?.value);
    const subDropList  = parseLangList(byId("fo-sub-drop-langs")?.value);

    const audio = {};
    if (keepLangList.length) audio.keepTracks = langCodesToRules(keepLangList);
    if (dropLangList.length) audio.dropTracks = langCodesToRules(dropLangList);
    if (maxChVal) audio.maxChannels = parseInt(maxChVal, 10);

    const subtitles = {};
    if (stripAll) subtitles.stripAll = true;
    if (!stripAll && subKeepList.length) subtitles.keepTracks = langCodesToRules(subKeepList);
    if (!stripAll && subDropList.length) subtitles.dropTracks = langCodesToRules(subDropList);

    const hasAudio    = Object.keys(audio).length > 0;
    const hasSubs     = Object.keys(subtitles).length > 0;
    if (!hasAudio && !hasSubs) return null;  // nothing set

    const payload = { path: foCurrentPath };
    if (hasAudio)  payload.audio     = audio;
    if (hasSubs)   payload.subtitles = subtitles;
    return payload;
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
        clearDrawerForm();
        setStatus("No override set for this file.");
      }
    } catch (err) {
      setStatus("Error loading override: " + (err.message || err));
    }
  }

  async function saveFileOverrideForPath() {
    if (!foCurrentPath) { setStatus("No file selected."); return; }
    const payload = buildOverridePayload();
    if (!payload) { setStatus("No overrides specified — nothing to save."); return; }

    setStatus("Saving…");
    try {
      const result = await apiPost("/api/queue/file-overrides", payload);
      if (result && result.ok) {
        setStatus("Override saved. Takes effect on next pipeline round.");
        if (typeof appendCommandResult === "function") appendCommandResult(result);
      } else {
        const msg = (result && result.message) ? result.message : "Unknown error.";
        setStatus("Error: " + msg);
      }
    } catch (err) {
      setStatus("Error saving override: " + (err.message || err));
    }
  }

  async function clearFileOverrideForPath() {
    if (!foCurrentPath) { setStatus("No file selected."); return; }
    setStatus("Clearing…");
    try {
      const result = await apiPost("/api/queue/file-overrides", { path: foCurrentPath, clear: true });
      if (result && result.ok) {
        clearDrawerForm();
        setStatus("Override cleared.");
        if (typeof appendCommandResult === "function") appendCommandResult(result);
      } else {
        const msg = (result && result.message) ? result.message : "Unknown error.";
        setStatus("Error: " + msg);
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
    const stripAll = byId("fo-sub-strip-all");

    if (overlay)  overlay.addEventListener("click", closeFileSettingsDrawer);
    if (closeBtn) closeBtn.addEventListener("click", closeFileSettingsDrawer);
    if (saveBtn)  saveBtn.addEventListener("click",  saveFileOverrideForPath);
    if (clearBtn) clearBtn.addEventListener("click", clearFileOverrideForPath);
    if (stripAll) stripAll.addEventListener("change", syncSubFilterFields);

    // Close on Escape
    document.addEventListener("keydown", (e) => {
      if (e.key === "Escape") {
        const drawer = byId("fo-drawer");
        if (drawer && !drawer.hidden) closeFileSettingsDrawer();
      }
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initFileSettingsDrawer);
  } else {
    initFileSettingsDrawer();
  }

})();
