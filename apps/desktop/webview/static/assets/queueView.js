(function () {
  const formatters = window.mediaPipelineFormatters || {};
  const shortenPath = typeof formatters.shortenPath === "function" ? formatters.shortenPath : null;
  let lastQueueRows = [];
  let lastQueueExcludedRows = [];
  let lastQueueHiddenSidecarRows = [];
  let lastQueuePayload = {};
  let lastQueueEmptyMessage = "No queue rows available.";
  let queueScanInFlight = false;
  let queueScanLoading = false;
  let queueScanPollTimer = null;
  let queueActiveStrategy = "Standard";
  let queueManualDragKey = "";
  let queuePriorityCommandInFlight = false;
  let queuePriorityCommandSeq = 0;
  let queueManualOrderLoadedKeys = [];
  let queueManualOrderDraftDirty = false;
  let queueTablePageStart = 0;
  let queueTableFilterSignature = "";
  const QUEUE_RENDER_LIMIT = 250;
  const displayedQueueFileOverrideMarkers = new Map();
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
      updateQueueSelectionVisuals: () => updateQueueSelectionVisuals(),
      setText: typeof setText === "function" ? setText : window.setText,
    })
    : {};
  const {
    getLastQueuePayload = function () { return lastQueuePayload || {}; },
    getLastQueueRows = function () { return lastQueueRows.slice(); },
    getSelectedQueueExcludedRow = function () { return null; },
    getSelectedQueueExcludedRowKey = _queueEmptyString,
    getSelectedQueuePriorityRowKeys = _queueEmptyArray,
    getSelectedQueuePriorityRows = _queueEmptyArray,
    getSelectedQueueRow = function () { return null; },
    getSelectedQueueRowKey = _queueEmptyString,
    queueExcludedRowKey = _queueEmptyString,
    queueRowKey = _queueEmptyString,
    selectQueueExcludedRow = _queueNoop,
    selectQueueRow = _queueNoop,
    setRenderedQueueRows = _queueNoop,
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
      shortenPath,
      wireManualOrderRow: (row, item) => wireQueueManualOrderRow(row, item),
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

  function queueVisibleFilterScope(rows) {
    const rowList = Array.isArray(rows) ? rows : [];
    const scope = typeof queueCurrentFilterScope === "function" ? queueCurrentFilterScope(rowList) : null;
    if (scope && typeof scope === "object") {
      return {
        active: Boolean(scope.active),
        totalRows: Number(scope.totalRows || 0),
        visibleRows: Number(scope.visibleRows || 0),
        hiddenRows: Number(scope.hiddenRows || 0),
        hiddenBlocked: Number(scope.hiddenBlocked || 0),
        hiddenWarning: Number(scope.hiddenWarning || 0),
        hiddenReview: Number(scope.hiddenReview || 0),
        renderLimit: Number(scope.renderLimit || 250),
      };
    }
    return {
      active: false,
      totalRows: rowList.length,
      visibleRows: rowList.length,
      hiddenRows: 0,
      hiddenBlocked: 0,
      hiddenWarning: 0,
      hiddenReview: 0,
      renderLimit: 250,
    };
  }

  function queueDecisionOutcome(queue, rows, entries) {
    const rowList = Array.isArray(rows) ? rows : [];
    const scope = queueVisibleFilterScope(rowList);
    const rawStatus = typeof queueLaunchDecisionStatus === "function"
      ? queueLaunchDecisionStatus(queue || {}, rowList, Array.isArray(entries) ? entries : [])
      : "Read evidence";
    if (String(rawStatus || "").toLowerCase() === "ready-looking") {
      return scope.hiddenBlocked || scope.hiddenReview ? "Review first" : "Queue evidence OK";
    }
    if (String(rawStatus || "").toLowerCase() === "evidence incomplete" || String(rawStatus || "").toLowerCase() === "not evaluated") {
      return "Read evidence";
    }
    return rawStatus || "Read evidence";
  }

  function queueDecisionStatusState(status) {
    const normalized = String(status || "").trim().toLowerCase();
    if (normalized === "queue evidence ok") return "ready";
    return typeof queueLaunchDecisionStatusState === "function"
      ? queueLaunchDecisionStatusState(status)
      : normalized === "do not launch"
        ? "blocked"
        : normalized === "review first"
          ? "warning"
          : normalized === "read evidence"
            ? "changed"
            : "unknown";
  }

  function queueDecisionFirstAction(status, queue, rows, scope) {
    const payload = queue || {};
    const rowList = Array.isArray(rows) ? rows : [];
    if (String(status || "").toLowerCase() === "do not launch") {
      return "First action: stay in Queue and Diagnostics until blocked evidence is explained.";
    }
    if (scope.hiddenBlocked || scope.hiddenReview) {
      return "First action: clear display filters or inspect hidden blocked/review rows before using Launch.";
    }
    if (Number(payload.excluded_row_count || 0) > 0 || Number(payload.completed_excluded_count || 0) > 0) {
      return "First action: review backend-excluded source files and completed exclusions before assuming files were missed.";
    }
    if (!rowList.length) {
      return "First action: explain the empty backend queue evidence before opening Launch.";
    }
    if (String(status || "").toLowerCase() === "queue evidence ok") {
      return "First action: open Launch for backend preflight, scope controls, schedule checks, and final authorization.";
    }
    return "First action: read the Queue-to-Launch handoff and diagnostics evidence before opening Launch.";
  }

  function queueDecisionSummaryLines(queue, rows, entries) {
    const payload = queue || {};
    const rowList = Array.isArray(rows) ? rows : [];
    const history = Array.isArray(entries) ? entries : [];
    const scope = queueVisibleFilterScope(rowList);
    const outcome = queueDecisionOutcome(payload, rowList, history);
    const selectedCount = typeof getSelectedQueuePriorityRowKeys === "function" ? getSelectedQueuePriorityRowKeys().length : 0;
    return [
      "Queue decision header:",
      `Decision state: ${outcome}.`,
      `Loaded rows: ${rowList.length}.`,
      `Visible rows after display filters: ${scope.visibleRows}/${scope.totalRows}.`,
      `Selected for Queue actions: ${selectedCount}.`,
      `Hidden blocked/review rows: ${scope.hiddenBlocked}/${scope.hiddenReview}.`,
      `Backend-excluded source rows: ${payload.excluded_row_count || 0}${payload.excluded_rows_truncated ? " (truncated)" : ""}.`,
      `Collision posture: ${payload.completed_collision_status || "unknown"} (${payload.completed_collision_severity || "unknown"}).`,
      "Backend launch scope is owned by Launch; Queue filters, selected rows, and rendered row caps are not submitted as processing scope.",
      queueDecisionFirstAction(outcome, payload, rowList, scope),
    ];
  }

  function renderQueueDecisionHeader(queue = lastQueuePayload, rows = lastQueueRows, entries) {
    const payload = queue || {};
    const rowList = Array.isArray(rows) ? rows : [];
    const history = Array.isArray(entries) ? entries : [];
    const outcome = queueDecisionOutcome(payload, rowList, history);
    setText("queue-decision-status", outcome);
    const statusNode = byId("queue-decision-status");
    if (statusNode) statusNode.dataset.state = queueDecisionStatusState(outcome);
    setText("queue-decision-summary", queueDecisionSummaryLines(payload, rowList, history).join("\n"));
  }

  function queueAttentionStatus(queue, rows) {
    const payload = queue || {};
    const rowList = Array.isArray(rows) ? rows : [];
    const scope = queueVisibleFilterScope(rowList);
    const reviewRows = typeof queueReviewRows === "function" ? queueReviewRows(payload, rowList) : [];
    const collisionSeverity = String(payload.completed_collision_severity || "").toLowerCase();
    if (payload.error) return "Diagnostics first";
    if (queueSnapshotIsStale(payload)) return "Refresh first";
    if (scope.hiddenBlocked || scope.hiddenReview) return "Hidden review rows";
    if (Array.isArray(reviewRows) && reviewRows.length) return `${reviewRows.length} flagged`;
    if (Number(payload.blocked_row_count || 0) > 0 || Number(payload.invalid_row_count || 0) > 0) return "Review rows";
    if (collisionSeverity && collisionSeverity !== "ok" && collisionSeverity !== "none") return "Collision review";
    if (Number(payload.excluded_row_count || 0) > 0) return "Check exclusions";
    if (!rowList.length) return "Explain empty";
    return "No immediate blocker";
  }

  function queueAttentionSummaryLines(queue, rows) {
    const payload = queue || {};
    const rowList = Array.isArray(rows) ? rows : [];
    const scope = queueVisibleFilterScope(rowList);
    const reviewRows = typeof queueReviewRows === "function" ? queueReviewRows(payload, rowList) : [];
    const flaggedCount = Array.isArray(reviewRows) ? reviewRows.length : 0;
    const lines = [
      "Attention required:",
      `Readiness: ${typeof queueReadinessStatus === "function" ? queueReadinessStatus(payload, rowList) : "unknown"}.`,
      `Flagged items: ${flaggedCount}; blocked rows: ${payload.blocked_row_count || 0}; invalid rows: ${payload.invalid_row_count || 0}.`,
      `Hidden blocked/review rows behind display filters: ${scope.hiddenBlocked}/${scope.hiddenReview}.`,
      `Collision risk: ${payload.completed_collision_status || "unknown"} (${payload.completed_collision_severity || "unknown"}).`,
      `Backend-excluded source rows: ${payload.excluded_row_count || 0}${payload.excluded_rows_truncated ? " (truncated)" : ""}.`,
    ];
    if (payload.error) {
      lines.push(`First action: open Diagnostics before Launch because Queue payload is unavailable: ${payload.error}`);
    } else if (scope.hiddenBlocked || scope.hiddenReview) {
      lines.push("First action: clear display filters or use the review views; the visible table can look safer than the backend queue evidence.");
    } else if (flaggedCount) {
      lines.push("First action: inspect flagged rows, collision risk, and selected-row diagnostics before opening Launch.");
    } else if (Number(payload.excluded_row_count || 0) > 0) {
      lines.push("First action: review Backend-Excluded Source Files so completed/history exclusions are understood before rerun decisions.");
    } else if (!rowList.length) {
      lines.push("First action: verify source roots, exclusions, and recent history before treating an empty Queue as safe.");
    } else {
      lines.push("First action: continue to Queue-to-Launch Handoff, then use Launch for backend authorization.");
    }
    lines.push("Boundary: attention evidence is read-only; Queue does not start work or submit display state as processing scope.");
    return lines;
  }

  function renderQueueAttentionSummary(queue = lastQueuePayload, rows = lastQueueRows) {
    const payload = queue || {};
    const rowList = Array.isArray(rows) ? rows : [];
    const status = queueAttentionStatus(payload, rowList);
    setText("queue-attention-status", status);
    const statusNode = byId("queue-attention-status");
    if (statusNode) {
      const normalized = String(status || "").toLowerCase();
      statusNode.dataset.state = normalized.includes("first") || normalized.includes("review") || normalized.includes("flagged") || normalized.includes("collision") || normalized.includes("exclusion") || normalized.includes("empty")
        ? "warning"
        : normalized.includes("blocker")
          ? "ready"
          : "changed";
    }
    setText("queue-attention-summary", queueAttentionSummaryLines(payload, rowList).join("\n"));
  }

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

  function queueSourceInventorySizeGb(row) {
    const sizeGb = Number(row?.size_gb);
    if (Number.isFinite(sizeGb) && sizeGb > 0) return sizeGb;
    const sizeBytes = Number(row?.size_bytes);
    return Number.isFinite(sizeBytes) && sizeBytes > 0 ? sizeBytes / (1024 ** 3) : 0;
  }

  function queueFormatSizeGb(sizeGb) {
    const value = Number(sizeGb);
    if (!Number.isFinite(value) || value <= 0) return "0 GB";
    if (value >= 10) return `${value.toFixed(1)} GB`;
    return `${value.toFixed(3)} GB`;
  }

  function queueFirstPositiveNumber(values) {
    const match = values.map((value) => Number(value)).find((value) => Number.isFinite(value) && value > 0);
    return match || 0;
  }

  function queueFirstCountEntry(counts) {
    if (!counts || typeof counts !== "object") return null;
    return Object.entries(counts)
      .map(([label, count]) => ({ label: String(label || "unknown"), count: Number(count || 0) }))
      .filter((entry) => entry.count > 0)
      .sort((a, b) => b.count - a.count || a.label.localeCompare(b.label))[0] || null;
  }

  function queueFormatTopCounts(counts, limit = 3) {
    if (!counts || typeof counts !== "object") return "No counts loaded";
    const entries = Object.entries(counts)
      .map(([label, count]) => ({ label: String(label || "unknown"), count: Number(count || 0) }))
      .filter((entry) => entry.count > 0)
      .sort((a, b) => b.count - a.count || a.label.localeCompare(b.label))
      .slice(0, limit);
    return entries.length ? entries.map((entry) => `${entry.label} ${entry.count}`).join("; ") : "No counts loaded";
  }

  function queueCountBy(rows, keyFn) {
    return (Array.isArray(rows) ? rows : []).reduce((counts, row) => {
      const key = String(keyFn(row) || "unknown").trim() || "unknown";
      counts[key] = Number(counts[key] || 0) + 1;
      return counts;
    }, {});
  }

  function queueRowReadinessCounts(rows) {
    return (Array.isArray(rows) ? rows : []).reduce((counts, row) => {
      const status = String(queueDisplayRowStatus(row) || "").toLowerCase();
      if (status.includes("blocked") || status.includes("failed") || status.includes("error")) {
        counts.blocked += 1;
      } else if (
        status.includes("warning")
        || status.includes("review")
        || status.includes("validation")
        || status.includes("unknown")
        || status.includes("parked")
        || status.includes("paused")
        || status.includes("retry")
      ) {
        counts.warning += 1;
      } else {
        counts.ready += 1;
      }
      return counts;
    }, { ready: 0, warning: 0, blocked: 0 });
  }

  function queueScanStatusTone(status) {
    const text = String(status?.status || "").toLowerCase();
    const errors = Array.isArray(status?.errors) ? status.errors : [];
    const warnings = Array.isArray(status?.warnings) ? status.warnings : [];
    if (errors.length || text.includes("fail") || text.includes("error")) return "danger";
    if (warnings.length || text.includes("warning")) return "warning";
    if (Boolean(status?.running) || text.includes("running") || text.includes("scan")) return "info";
    if (text.includes("complete") || text.includes("success") || text === "ok") return "success";
    return "muted";
  }

  function queueSourceInventoryLargestRow(rows) {
    return (Array.isArray(rows) ? rows : []).reduce((largest, row) => {
      const sizeGb = queueSourceInventorySizeGb(row);
      return sizeGb > largest.sizeGb ? { row, sizeGb } : largest;
    }, { row: null, sizeGb: 0 });
  }

  function queueSourceInventoryTileModel(queue = lastQueuePayload) {
    const payload = queue && typeof queue === "object" ? queue : {};
    const inventory = queueSourceInventory(payload);
    const inventoryRows = Array.isArray(inventory.rows) ? inventory.rows : [];
    const queueRows = Array.isArray(lastQueueRows) ? lastQueueRows : [];
    const filteredRows = typeof queueFilteredRowsForCurrentDisplay === "function" ? queueFilteredRowsForCurrentDisplay() : queueRows;
    const status = queueScanStatus(payload);
    const candidateCount = queueFirstPositiveNumber([inventory.row_count, inventory.available_row_count, inventoryRows.length, status.inventory_count]);
    const curatedCount = queueFirstPositiveNumber([status.curated_row_count, queueRows.length]);
    const totalSizeGb = inventoryRows.reduce((total, row) => total + queueSourceInventorySizeGb(row), 0);
    const readiness = queueRowReadinessCounts(queueRows);
    const topBlocker = queueFirstCountEntry(payload.blocked_reason_counts) || queueFirstCountEntry(payload.blocked_reason_code_counts);
    const routeCounts = payload.route_counts && typeof payload.route_counts === "object"
      ? payload.route_counts
      : queueCountBy(queueRows, (row) => row.route_name || row.route || row.route_decision || "unknown");
    const sourceRootCounts = payload.source_root_counts && typeof payload.source_root_counts === "object"
      ? payload.source_root_counts
      : inventory.source_root_counts;
    const sourceRootTotal = sourceRootCounts && typeof sourceRootCounts === "object" ? Object.keys(sourceRootCounts).length : 0;
    const largest = queueSourceInventoryLargestRow(inventoryRows);
    const largestName = largest.row?.relative_path || largest.row?.display_name || largest.row?.source_path || "No preview item loaded";
    const visibleCount = Array.isArray(filteredRows) ? filteredRows.length : queueRows.length;
    return [
      {
        label: "Scan Freshness",
        value: status.status || "Not scanned",
        detail: status.updated_at_utc ? `Updated ${status.updated_at_utc}` : (status.message || "No backend scan status loaded."),
        tone: queueScanStatusTone(status),
      },
      {
        label: "Queue Size",
        value: `${curatedCount} row${curatedCount === 1 ? "" : "s"}`,
        detail: `${candidateCount} inventory candidate${candidateCount === 1 ? "" : "s"}; preview size ${queueFormatSizeGb(totalSizeGb)}.`,
        tone: curatedCount ? "info" : "muted",
      },
      {
        label: "Launch Readiness",
        value: `Ready ${readiness.ready}`,
        detail: `Blocked ${readiness.blocked}; Warning ${readiness.warning}.`,
        tone: readiness.blocked ? "danger" : (readiness.warning ? "warning" : (queueRows.length ? "success" : "muted")),
      },
      {
        label: "Top Blocker",
        value: topBlocker ? topBlocker.label : "No blockers",
        detail: topBlocker ? `${topBlocker.count} row${topBlocker.count === 1 ? "" : "s"} affected.` : "No blocked reason count in the loaded queue.",
        tone: topBlocker ? "danger" : "success",
      },
      {
        label: "Work Mix",
        value: queueFormatTopCounts(routeCounts, 2),
        detail: "Highest route counts in the curated queue.",
        tone: queueRows.length ? "info" : "muted",
      },
      {
        label: "Largest Preview",
        value: largest.sizeGb ? queueFormatSizeGb(largest.sizeGb) : "No size",
        detail: largestName,
        tone: largest.sizeGb ? "warning" : "muted",
      },
      {
        label: "Filter Impact",
        value: `${visibleCount} of ${queueRows.length}`,
        detail: "Visible rows only; backend Launch scope is unchanged.",
        tone: visibleCount === queueRows.length ? "success" : "warning",
      },
      {
        label: "Source Roots",
        value: sourceRootTotal ? `${sourceRootTotal} root${sourceRootTotal === 1 ? "" : "s"}` : "Not reported",
        detail: sourceRootTotal ? queueFormatTopCounts(sourceRootCounts, 2) : "Refresh source inventory to load root evidence.",
        tone: sourceRootTotal ? "info" : "muted",
      },
    ];
  }

  function appendQueueSourceTile(board, tile) {
    const card = document.createElement("section");
    card.className = "queue-source-tile";
    card.dataset.tone = tile.tone || "muted";
    const label = document.createElement("span");
    label.className = "queue-source-tile-label";
    label.textContent = tile.label || "";
    const value = document.createElement("strong");
    value.className = "queue-source-tile-value";
    value.textContent = tile.value || "";
    const detail = document.createElement("span");
    detail.className = "queue-source-tile-detail";
    detail.textContent = tile.detail || "";
    card.append(label, value, detail);
    board.appendChild(card);
  }

  function renderQueueSourceInventoryMessage(lines, tone = "info") {
    const root = byId("queue-source-inventory");
    if (!root) return;
    root.replaceChildren();
    const card = document.createElement("section");
    card.className = "queue-source-tile queue-source-message-tile";
    card.dataset.tone = tone;
    const value = document.createElement("strong");
    value.className = "queue-source-tile-value";
    value.textContent = lines[0] || "Queue source inventory";
    const detail = document.createElement("span");
    detail.className = "queue-source-tile-detail";
    detail.textContent = lines.slice(1).join(" ");
    card.append(value, detail);
    root.appendChild(card);
  }

  function renderQueueScanArtifacts(queue = lastQueuePayload) {
    const root = byId("queue-source-inventory");
    if (root) {
      const lines = queueSourceInventoryLines(queue);
      const board = document.createElement("div");
      board.className = "queue-source-tile-board";
      queueSourceInventoryTileModel(queue).forEach((tile) => appendQueueSourceTile(board, tile));

      const details = document.createElement("details");
      details.className = "queue-source-detail-disclosure";
      const summary = document.createElement("summary");
      summary.textContent = "Source inventory details";
      const body = document.createElement("pre");
      body.className = "prose-block";
      body.textContent = lines.join("\n");
      details.append(summary, body);

      root.replaceChildren(board, details);
    }
    window.mediaPipelineAppRefresh?.setQueueRefreshButtonBusy?.(queueScanIsRunning(queue));
  }

  function queueTableWrap() {
    const tbody = byId("queue-rows");
    return tbody?.closest?.(".queue-table-wrap") || null;
  }

  function queueTableElement() {
    const tbody = byId("queue-rows");
    return tbody?.closest?.("table") || null;
  }

  function setQueueLoadingScreenVisible(isVisible) {
    queueScanLoading = Boolean(isVisible);
    const wrap = queueTableWrap();
    const screen = byId("queue-loading-screen");
    if (wrap) {
      wrap.classList.toggle("is-queue-loading", queueScanLoading);
      wrap.dataset.queueLoading = queueScanLoading ? "true" : "false";
      if (queueScanLoading) {
        wrap.setAttribute("aria-busy", "true");
      } else {
        wrap.removeAttribute("aria-busy");
      }
    }
    if (screen) screen.hidden = !queueScanLoading;
  }

  function renderQueueLoadingTable() {
    const rowCount = Array.isArray(lastQueueRows) ? lastQueueRows.length : 0;
    const snapshotText = rowCount
      ? `Showing previous backend snapshot (${rowCount} row${rowCount === 1 ? "" : "s"}) until the refreshed dry-run snapshot arrives.`
      : "No previous queue snapshot is loaded yet.";
    const scanLines = queueScanStatusLines(lastQueuePayload).filter((line) => line && !/^Queue source scan: not requested/i.test(line));
    const scanText = scanLines.length ? ` ${scanLines.slice(0, 3).join(" ")}` : "";
    setText("queue-status", `Refreshing queue... ${snapshotText}`);
    setText("queue-table-legend", `Queue refresh in progress. ${snapshotText} Backend Launch scope is unchanged.`);
    setText("queue-loading-status", `Scanning configured source roots for a fresh queue preview.${scanText} ${snapshotText} No media mutation has been submitted.`);
    updateQueueManualOrderControls();
  }

  function renderQueueScanLoadingState() {
    setQueueLoadingScreenVisible(true);
    renderQueueLoadingTable();
    renderQueueRows();
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
      .map((row) => queueRowWithOverrideMarker(row, overrideTargetKeys))
      .map(queueRowWithDisplayedFileOverrideMarker);
    const displayQueue = queueDisplayPayloadForVisibleRows(queue, rows, hiddenSidecars, rawRows);
    const excludedRows = Array.isArray(queue.excluded_rows) ? queue.excluded_rows : [];
    queueTablePageStart = 0;
    queueTableFilterSignature = "";
    lastQueuePayload = displayQueue;
    lastQueueRows = rows;
    resetQueueManualOrderLoadedKeys(rows);
    lastQueueHiddenSidecarRows = hiddenSidecars;
    lastQueueExcludedRows = excludedRows;
    syncSelectedQueueRows(rows, excludedRows);
    lastQueueEmptyMessage = queueEmptyStateMessage(displayQueue, rows);
    renderQueueScanArtifacts(displayQueue);
    scheduleQueueScanPoll();
    setQueueLoadingScreenVisible(queueScanIsRunning(displayQueue));
    const commandHistory = typeof getCommandHistory === "function" ? getCommandHistory() : [];
    renderQueueDecisionHeader(displayQueue, rows, commandHistory);
    renderQueueAttentionSummary(displayQueue, rows);
    renderQueueProgress(displayQueue);
    renderQueueSummary(displayQueue, rows);
    renderQueueReadiness(displayQueue, rows);
    renderQueueBreakdown(displayQueue, rows);
    renderQueueRuntime(displayQueue, rows);
    renderQueueValidation(displayQueue, rows);
    renderQueueWorkflow(displayQueue, rows);
    renderQueueBackendLaunchScopePreview(displayQueue, rows, commandHistory);
    renderQueueLaunchDecisionChecklist(displayQueue, rows, commandHistory);
    renderQueueReviewBoard(displayQueue, rows);
    renderQueueCollision(displayQueue, rows);
    renderQueueExcluded(displayQueue);
    renderQueueExcludedDetail(getSelectedQueueExcludedRow());
    if (typeof getCommandHistory === "function") renderQueueOpenHistory(commandHistory);
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

  function queueCompactPathText(value, maxChars) {
    const raw = String(value || "");
    const max = Math.max(16, Number(maxChars) || 64);
    if (!raw || raw.length <= max) return raw;
    const endCount = Math.max(8, Math.floor((max - 3) * 0.62));
    const startCount = Math.max(4, max - endCount - 3);
    return `${raw.slice(0, startCount)}...${raw.slice(-endCount)}`;
  }

  function queueExcludedSourceDisplay(sourcePath) {
    const raw = String(sourcePath || "");
    if (!raw) return "";
    const sep = raw.includes("\\") ? "\\" : "/";
    const parts = raw.split(/[\\/]+/).filter(Boolean);
    const filename = parts[parts.length - 1] || raw;
    const parent = parts.length > 1 ? parts[parts.length - 2] : "";
    let root = "";
    if (raw.startsWith("\\\\")) {
      root = parts.length >= 2 ? `\\\\${parts[0]}${sep}${parts[1]}` : "\\\\";
    } else if (/^[A-Za-z]:$/.test(parts[0] || "")) {
      root = parts[0];
    } else if (parts.length > 2 && !raw.startsWith("/")) {
      root = parts[0];
    }
    const prefix = root ? `${root}${sep}...${sep}` : `...${sep}`;
    const parentPrefix = parent && parent !== filename ? `${parent}${sep}` : "";
    const filenameBudget = Math.max(12, 64 - prefix.length - parentPrefix.length);
    const compactFilename = queueCompactPathText(filename, filenameBudget);
    return `${prefix}${parentPrefix}${compactFilename}`;
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
      const sourcePath = item.source_path || "";
      appendCells(row, [
        item.source_order || "",
        item.media_type || item.media_kind || "",
        item.reason_code || "excluded",
        item.display_name || item.relative_path || "",
        queueExcludedSourceDisplay(sourcePath),
      ], [null, null, null, null, "path-cell"]);
      const cells = row.querySelectorAll("td");
      if (cells[4] && sourcePath) cells[4].title = sourcePath;
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

  function queueClampScrollOffset(value, maxValue) {
    const numeric = Number(value);
    const maximum = Math.max(0, Number(maxValue) || 0);
    return Math.min(Math.max(0, Number.isFinite(numeric) ? numeric : 0), maximum);
  }

  function queueTableScrollSnapshot(tbody) {
    const target = tbody?.closest?.(".queue-table-wrap") || tbody?.closest?.(".table-wrap") || null;
    if (!target) return null;
    return {
      target,
      top: target.scrollTop,
      left: target.scrollLeft,
    };
  }

  function restoreQueueTableScroll(snapshot) {
    const target = snapshot?.target;
    if (!target) return;
    target.scrollTop = queueClampScrollOffset(snapshot.top, target.scrollHeight - target.clientHeight);
    target.scrollLeft = queueClampScrollOffset(snapshot.left, target.scrollWidth - target.clientWidth);
  }

  function updateQueueSelectionVisuals() {
    const tbody = byId("queue-rows");
    const selectedKeys = new Set(getSelectedQueuePriorityRowKeys());
    if (tbody && typeof tbody.querySelectorAll === "function") {
      tbody.querySelectorAll('tr[data-selectable-row="true"]').forEach((row) => {
        const key = String(row.dataset.rowKey || "");
        const selected = Boolean(key && selectedKeys.has(key));
        row.classList.toggle("is-selected", selected);
        row.setAttribute("aria-selected", selected ? "true" : "false");
        if (selected) row.dataset.prioritySelected = "true";
        else delete row.dataset.prioritySelected;
      });
    }
    updateQueueTableLegend(tbody);
    updateQueueManualOrderControls();
  }

  function updateQueueTableLegend(tbody) {
    updateTableStatusLegend("queue-table-legend", tbody, "Queue rows");
    const legend = byId("queue-table-legend");
    if (!legend) return;
    const selectedKeys = getSelectedQueuePriorityRowKeys();
    const visibleSelectedCount = tbody && typeof tbody.querySelectorAll === "function"
      ? tbody.querySelectorAll('tr[data-priority-selected="true"]').length
      : selectedKeys.length;
    legend.textContent = `${legend.textContent} Selected for Queue actions: ${selectedKeys.length} total, ${visibleSelectedCount} visible. Backend Launch scope is unchanged. Ctrl/Cmd-click or Space toggles rows; Shift-click selects a visible range.`;
  }

  function queueDisplayFilterSignature(filterText, statusFilter, investigationFilter) {
    return [
      String(filterText || ""),
      String(statusFilter || "all"),
      String(investigationFilter || "all"),
      String(lastQueueRows.length),
    ].join("\u001f");
  }

  function queueClampPageStart(rowCount) {
    const count = Math.max(0, Number(rowCount) || 0);
    if (count <= QUEUE_RENDER_LIMIT) return 0;
    const maxStart = Math.floor((count - 1) / QUEUE_RENDER_LIMIT) * QUEUE_RENDER_LIMIT;
    return Math.min(Math.max(0, queueTablePageStart), maxStart);
  }

  function updateQueuePaginationControls(rowCount, pageStart, renderedCount) {
    const container = byId("queue-table-pagination");
    const status = byId("queue-table-page-status");
    const previous = byId("queue-page-prev-btn");
    const next = byId("queue-page-next-btn");
    const total = Math.max(0, Number(rowCount) || 0);
    const hasPages = total > QUEUE_RENDER_LIMIT;
    if (container) {
      container.hidden = !hasPages;
      container.setAttribute("aria-hidden", hasPages ? "false" : "true");
    }
    if (status) {
      if (hasPages) {
        const first = pageStart + 1;
        const last = pageStart + renderedCount;
        const page = Math.floor(pageStart / QUEUE_RENDER_LIMIT) + 1;
        const pages = Math.ceil(total / QUEUE_RENDER_LIMIT);
        status.textContent = `Rows ${first}-${last} of ${total}. Page ${page} of ${pages}. Display paging does not change backend Launch scope.`;
      } else {
        status.textContent = `Rows ${total ? `1-${total}` : "0"} of ${total}.`;
      }
    }
    if (previous) previous.disabled = !hasPages || pageStart <= 0;
    if (next) next.disabled = !hasPages || pageStart + QUEUE_RENDER_LIMIT >= total;
  }

  function moveQueueTablePage(delta) {
    const rows = queueFilteredRowsForCurrentDisplay();
    const nextStart = queueClampScrollOffset(queueTablePageStart + (delta * QUEUE_RENDER_LIMIT), Math.max(0, rows.length - 1));
    const normalized = Math.floor(nextStart / QUEUE_RENDER_LIMIT) * QUEUE_RENDER_LIMIT;
    queueTablePageStart = normalized;
    renderQueueRows({ preservePage: true });
  }

  function queueFilteredRowsForCurrentDisplay() {
    const filterText = byId("queue-filter")?.value || "";
    const statusFilter = byId("queue-status-filter")?.value || "all";
    const investigationFilter = byId("queue-investigation-filter")?.value || "all";
    const textRows = filterRows(lastQueueRows, filterText, QUEUE_FILTER_FIELDS);
    const statusRows = typeof filterRowsByStatus === "function" ? filterRowsByStatus(textRows, statusFilter, queueDisplayRowStatus) : textRows;
    return typeof filterRowsByInvestigation === "function" ? filterRowsByInvestigation(statusRows, investigationFilter, queueMatchesInvestigationFilter) : statusRows;
  }

  function setQueueFilterSummary(lines) {
    const summary = byId("queue-filter-summary");
    const text = Array.isArray(lines) ? lines.join("\n") : String(lines || "");
    setText("queue-filter-summary", text || "Queue filter inactive. No rows loaded.");
    if (!summary) return;
    summary.hidden = true;
    summary.setAttribute("aria-hidden", "true");
    const normalized = text.toLowerCase();
    summary.dataset.tone = normalized.includes("hidden review rows")
      || normalized.includes("display cap")
      || normalized.includes("blocked/warning")
      ? "warning"
      : "info";
  }

  function renderQueueRows(options = {}) {
    const filterText = byId("queue-filter")?.value || "";
    const statusFilter = byId("queue-status-filter")?.value || "all";
    const investigationFilter = byId("queue-investigation-filter")?.value || "all";
    const rows = queueFilteredRowsForCurrentDisplay();
    const filterSignature = queueDisplayFilterSignature(filterText, statusFilter, investigationFilter);
    if (!options.preservePage && filterSignature !== queueTableFilterSignature) {
      queueTablePageStart = 0;
    }
    queueTableFilterSignature = filterSignature;
    queueTablePageStart = queueClampPageStart(rows.length);
    const renderLimit = QUEUE_RENDER_LIMIT;
    const visibleRows = rows.slice(queueTablePageStart, queueTablePageStart + renderLimit);
    const renderedCount = visibleRows.length;
    setText(
      "queue-status",
      rows.length > renderLimit
        ? (
          queueTablePageStart > 0
            ? `${queueTablePageStart + 1}-${queueTablePageStart + renderedCount} shown / ${rows.length} filtered / ${lastQueueRows.length} rows`
            : `${renderedCount} shown / ${rows.length} filtered / ${lastQueueRows.length} rows`
        )
        : `${rows.length} / ${lastQueueRows.length} row${lastQueueRows.length === 1 ? "" : "s"}`
    );
    const buildFilterSummary = typeof filterResultSummaryLines === "function"
      ? filterResultSummaryLines
      : window.mediaPipelineDom?.filterResultSummaryLines;
    if (typeof buildFilterSummary === "function") {
      const summaryLines = buildFilterSummary({
        label: "Queue display filter",
        allRows: lastQueueRows,
        visibleRows: rows,
        filterText,
        statusFilter,
        investigationFilter,
        investigationLabel: queueInvestigationFilterLabel(investigationFilter),
        statusOf: queueDisplayRowStatus,
        limit: renderLimit,
        decisionName: "launch",
        guardrail: "Mutation guardrail: display filtering the Queue table does not change backend launch scope, queue state, source files, or processing commands.",
      });
      if (rows.length > renderLimit) {
        const first = queueTablePageStart + 1;
        const last = queueTablePageStart + renderedCount;
        summaryLines.push(`Display page: showing filtered rows ${first}-${last} of ${rows.length}. Use Previous/Next to inspect more rows; display pages are not backend Launch scope.`);
      }
      setQueueFilterSummary(summaryLines);
    }
    const tbody = byId("queue-rows");
    const scrollSnapshot = queueTableScrollSnapshot(tbody);
    if (!rows.length) {
      setRenderedQueueRows([]);
      clearRows(tbody, 9, lastQueueRows.length ? "No queue rows match the filter." : lastQueueEmptyMessage);
      updateQueuePaginationControls(rows.length, 0, 0);
      updateQueueTableLegend(tbody);
      updateQueueManualOrderControls();
      if (queueScanLoading) renderQueueLoadingTable();
      if (getSelectedQueueRowKey()) renderQueueDetail(getSelectedQueueRow());
      const commandHistory = typeof getCommandHistory === "function" ? getCommandHistory() : [];
      renderQueueBackendLaunchScopePreview(lastQueuePayload, lastQueueRows, commandHistory);
      renderQueueLaunchDecisionChecklist(lastQueuePayload, lastQueueRows, commandHistory);
      renderQueueDecisionHeader(lastQueuePayload, lastQueueRows, commandHistory);
      renderQueueAttentionSummary(lastQueuePayload, lastQueueRows);
      restoreQueueTableScroll(scrollSnapshot);
      return;
    }
    tbody.replaceChildren();
    setRenderedQueueRows(visibleRows);
    renderQueueTableRows({
      rows: visibleRows,
      tbody,
      manualOrderEnabled: queueManualOrderIsEnabled(),
      selectedQueuePriorityRowKeys: getSelectedQueuePriorityRowKeys(),
      selectedQueueRowKey: getSelectedQueueRowKey(),
      wireManualOrderRow: wireQueueManualOrderRow,
    });
    updateQueuePaginationControls(rows.length, queueTablePageStart, renderedCount);
    updateQueueTableLegend(tbody);
    updateQueueManualOrderControls();
    if (getSelectedQueueRowKey()) renderQueueDetail(getSelectedQueueRow());
    const commandHistory = typeof getCommandHistory === "function" ? getCommandHistory() : [];
    renderQueueBackendLaunchScopePreview(lastQueuePayload, lastQueueRows, commandHistory);
    renderQueueLaunchDecisionChecklist(lastQueuePayload, lastQueueRows, commandHistory);
    renderQueueDecisionHeader(lastQueuePayload, lastQueueRows, commandHistory);
    renderQueueAttentionSummary(lastQueuePayload, lastQueueRows);
    if (queueScanLoading) renderQueueLoadingTable();
    restoreQueueTableScroll(scrollSnapshot);
  }

  function resetQueueFilters() {
    const filter = byId("queue-filter");
    const status = byId("queue-status-filter");
    const investigation = byId("queue-investigation-filter");
    if (filter) filter.value = "";
    if (status) status.value = "all";
    if (investigation) investigation.value = "all";
    queueTablePageStart = 0;
    queueTableFilterSignature = "";
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
    renderQueueSourceInventoryMessage([
      "Queue source scan requested.",
      "Waiting for backend source inventory and queue curation status.",
      "Mutation guardrail: this command does not process, rename, move, delete, publish, drain, or mutate source media.",
    ], "info");
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
        setQueueFilterSummary("Queue source scan started, but refresh wiring is not loaded.");
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
      setQueueLoadingScreenVisible(false);
      renderQueueRows();
      setText("queue-open-status", result.message);
      renderQueueSourceInventoryMessage([
        result.message,
        "Safe next step: inspect Diagnostics and backend command history before trying again.",
      ], "danger");
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
    setQueueFilterSummary,
    renderQueueScanLoadingState,
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
    getSelectedQueuePriorityRowKeys,
    getSelectedQueuePriorityRows,
    getLastQueuePayload,
    getLastQueueRows,
    queueRowKey,
    queuePriorityItemsForSelected,
    applyDisplayedQueueFileOverrideMarker,
    sendSelectedQueuePriority,
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
  window.getSelectedQueuePriorityRows = getSelectedQueuePriorityRows;
  window.getSelectedQueuePriorityRowKeys = getSelectedQueuePriorityRowKeys;
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

  function queuePriorityPathKey(value) {
    return String(value || "").trim().replace(/[\\/]+/g, "\\").toLowerCase();
  }

  function queuePriorityNormalizedLevel(level) {
    const normalized = String(level || "normal").trim().toLowerCase();
    return ["high", "low", "hold"].includes(normalized) ? normalized : "normal";
  }

  function queuePriorityRowMatchesPath(row, targetKey) {
    if (!targetKey) return false;
    return [row?.source_path, row?.relative_path].some((value) => queuePriorityPathKey(value) === targetKey);
  }

  function queueDisplayedFileOverrideMarkerForRow(row) {
    const keys = [row?.source_path, row?.relative_path]
      .map(queuePriorityPathKey)
      .filter(Boolean);
    for (const key of keys) {
      if (displayedQueueFileOverrideMarkers.has(key)) return displayedQueueFileOverrideMarkers.get(key);
    }
    return null;
  }

  function queueRowWithDisplayedFileOverrideMarker(row) {
    const markerValue = queueDisplayedFileOverrideMarkerForRow(row);
    if (markerValue === null) return row;
    const next = { ...row, __queue_has_override: markerValue, has_file_override: markerValue };
    if (!markerValue) {
      next.has_override = false;
      next.file_override = null;
      next.file_override_path = "";
    }
    return next;
  }

  function queuePriorityRowHasVisibleMarker(row) {
    const manifestLevel = queuePriorityNormalizedLevel(row?.manifest_priority_level);
    return Boolean(row?.is_priority) || manifestLevel === "high" || manifestLevel === "low" || manifestLevel === "hold";
  }

  function queuePriorityRowPath(row) {
    return row ? (row.source_path || row.relative_path || "") : "";
  }

  function queuePriorityItemsForSelected(level, reason) {
    const normalizedLevel = queuePriorityNormalizedLevel(level);
    const seen = new Set();
    return getSelectedQueuePriorityRows()
      .map((row) => ({
        path: queuePriorityRowPath(row),
        level: normalizedLevel,
        reason: reason || "",
      }))
      .filter((item) => {
        const pathKey = queuePriorityPathKey(item.path);
        if (!pathKey || seen.has(pathKey)) return false;
        seen.add(pathKey);
        return true;
      });
  }

  function refreshDisplayedQueuePriorityRows() {
    const previousPayload = lastQueuePayload && typeof lastQueuePayload === "object" ? lastQueuePayload : {};
    const refreshMeta = previousPayload.__mediaPipelineRefreshMeta;
    lastQueuePayload = {
      ...previousPayload,
      rows: lastQueueRows,
      priority_visible_count: lastQueueRows.filter(queuePriorityRowHasVisibleMarker).length,
    };
    if (refreshMeta) {
      try {
        Object.defineProperty(lastQueuePayload, "__mediaPipelineRefreshMeta", {
          value: refreshMeta,
          enumerable: false,
          configurable: true,
        });
      } catch (_) {}
    }
    syncSelectedQueueRows(lastQueueRows, lastQueueExcludedRows);
    renderQueueSummary(lastQueuePayload, lastQueueRows);
    renderQueueBreakdown(lastQueuePayload, lastQueueRows);
    renderQueueRows();
  }

  function applyDisplayedQueuePriorityUpdates(items) {
    const updates = Array.isArray(items) ? items : [];
    const levelsByPath = new Map();
    updates.forEach((item) => {
      const pathKey = queuePriorityPathKey(item?.path);
      if (pathKey) levelsByPath.set(pathKey, queuePriorityNormalizedLevel(item?.level));
    });
    if (!levelsByPath.size) return false;

    let changed = false;
    lastQueueRows = lastQueueRows.map((row) => {
      let nextLevel = null;
      levelsByPath.forEach((level, pathKey) => {
        if (nextLevel === null && queuePriorityRowMatchesPath(row, pathKey)) nextLevel = level;
      });
      if (nextLevel === null) return row;
      changed = true;
      return { ...row, manifest_priority_level: nextLevel };
    });
    if (!changed) return false;
    refreshDisplayedQueuePriorityRows();
    return true;
  }

  function clearDisplayedQueuePriorityManifest() {
    let changed = false;
    lastQueueRows = lastQueueRows.map((row) => {
      if (queuePriorityNormalizedLevel(row?.manifest_priority_level) === "normal") return row;
      changed = true;
      return { ...row, manifest_priority_level: "normal" };
    });
    if (!changed) return false;
    refreshDisplayedQueuePriorityRows();
    return true;
  }

  function applyDisplayedQueueFileOverrideMarker(path, hasOverride) {
    const targetKey = queuePriorityPathKey(path);
    if (!targetKey) return false;
    const markerValue = Boolean(hasOverride);
    displayedQueueFileOverrideMarkers.set(targetKey, markerValue);
    let changed = false;
    lastQueueRows = lastQueueRows.map((row) => {
      if (!queuePriorityRowMatchesPath(row, targetKey)) return row;
      const currentValue = Boolean(
        row?.__queue_has_override
          || row?.has_override
          || row?.has_file_override
          || row?.file_override
          || row?.file_override_path
      );
      if (
        currentValue === markerValue
        && Boolean(row?.__queue_has_override) === markerValue
        && Boolean(row?.has_file_override) === markerValue
      ) {
        return row;
      }
      changed = true;
      const next = { ...row, __queue_has_override: markerValue, has_file_override: markerValue };
      if (!markerValue) {
        next.has_override = false;
        next.file_override = null;
        next.file_override_path = "";
      }
      return next;
    });
    if (!changed) return false;
    refreshDisplayedQueuePriorityRows();
    return true;
  }

  function queuePriorityControlIds() {
    return [
      "queue-priority-promote-btn",
      "queue-priority-normal-btn",
      "queue-priority-low-btn",
      "queue-priority-hold-btn",
      "queue-priority-promote-movies-btn",
      "queue-priority-promote-tv-btn",
      "queue-priority-clear-all-btn",
    ];
  }

  function updateQueuePriorityControls() {
    const disabled = Boolean(queuePriorityCommandInFlight || queueScanLoading);
    queuePriorityControlIds().forEach((id) => {
      const button = byId(id);
      if (button) button.disabled = disabled;
    });
    updateQueueManualOrderControls();
  }

  function beginQueuePriorityCommand(message = "") {
    queuePriorityCommandInFlight = true;
    const seq = queuePriorityCommandSeq + 1;
    queuePriorityCommandSeq = seq;
    if (message) setText("queue-priority-status", message);
    updateQueuePriorityControls();
    return seq;
  }

  function isCurrentQueuePriorityCommand(seq) {
    return seq === queuePriorityCommandSeq;
  }

  function endQueuePriorityCommand(seq) {
    if (isCurrentQueuePriorityCommand(seq)) queuePriorityCommandInFlight = false;
    updateQueuePriorityControls();
  }

  // Rows shown during a dry-run scan come from the previous snapshot; block
  // queue-state requests until the refreshed snapshot arrives so stale row
  // identities are never submitted to the backend.
  function queuePriorityActionsPausedForScan() {
    if (!queueScanLoading) return false;
    setText("queue-priority-status", "Priority actions are paused while the backend builds a fresh queue preview. The table shows the previous snapshot; retry after the refresh completes.");
    return true;
  }

  async function sendQueuePriority(path, level, reason) {
    if (queuePriorityActionsPausedForScan()) return;
    if (queuePriorityCommandInFlight) {
      setText("queue-priority-status", "Queue priority command already in progress.");
      return;
    }
    if (!path) {
      setText("queue-priority-status", "No row selected — select a queue row first.");
      return;
    }
    const seq = beginQueuePriorityCommand("Sending...");
    try {
      const result = await apiPost("/api/queue/priority", { path, level, reason });
      const msg = result && result.message ? result.message : `Priority set to '${level}'.`;
      if (isCurrentQueuePriorityCommand(seq)) setText("queue-priority-status", msg);
      if (typeof appendCommandResult === "function") appendCommandResult({ command: "queue.priority", ok: Boolean(result && result.ok), severity: result && result.ok ? "ok" : "error", message: msg });
      if (result && result.ok) applyDisplayedQueuePriorityUpdates([{ path, level }]);
      if (result && result.ok && typeof refreshAll === "function") await refreshAll();
    } catch (err) {
      if (isCurrentQueuePriorityCommand(seq)) setText("queue-priority-status", `Priority request failed: ${err}`);
    } finally {
      endQueuePriorityCommand(seq);
    }
  }

  async function sendQueuePriorityBulk(items, description) {
    if (queuePriorityActionsPausedForScan()) return;
    if (queuePriorityCommandInFlight) {
      setText("queue-priority-status", "Queue priority command already in progress.");
      return;
    }
    if (!items || !items.length) {
      setText("queue-priority-status", "No rows to update.");
      return;
    }
    const seq = beginQueuePriorityCommand(`Updating ${items.length} row(s)...`);
    try {
      const result = await apiPost("/api/queue/priority", { items });
      const msg = result && result.message ? result.message : description || "Bulk priority updated.";
      if (isCurrentQueuePriorityCommand(seq)) setText("queue-priority-status", msg);
      if (typeof appendCommandResult === "function") appendCommandResult({ command: "queue.priority", ok: Boolean(result && result.ok), severity: result && result.ok ? "ok" : "error", message: msg });
      if (result && result.ok) applyDisplayedQueuePriorityUpdates(items);
      if (result && result.ok && typeof refreshAll === "function") await refreshAll();
    } catch (err) {
      if (isCurrentQueuePriorityCommand(seq)) setText("queue-priority-status", `Bulk priority request failed: ${err}`);
    } finally {
      endQueuePriorityCommand(seq);
    }
  }

  function confirmLoadedQueuePriorityBulk(kindLabel, items) {
    if (!items || !items.length) return true;
    if (typeof window.confirm !== "function") return true;
    const filteredCount = queueFilteredRowsForCurrentDisplay()
      .filter((row) => String(row.media_type || "").toLowerCase() === String(kindLabel || "").toLowerCase())
      .length;
    return window.confirm([
      `Promote ${items.length} loaded ${kindLabel} row(s) to High priority?`,
      "",
      `Loaded queue rows: ${lastQueueRows.length}.`,
      `Current display-filter matches for ${kindLabel}: ${filteredCount}.`,
      "This loaded-row action ignores display filters and the table render cap for the selected media kind.",
      "Backend Launch scope remains unchanged and is still decided by Launch routes.",
      "This sends a queue-state request only; it does not touch source, scratch, output, or rename files.",
    ].join("\n"));
  }

  async function sendSelectedQueuePriority(level, reason) {
    const items = queuePriorityItemsForSelected(level, reason);
    if (!items.length) {
      setText("queue-priority-status", "No priority rows selected — select one or more queue rows first.");
      return;
    }
    if (items.length === 1) {
      await sendQueuePriority(items[0].path, items[0].level, items[0].reason);
      return;
    }
    await sendQueuePriorityBulk(items, `Priority set to '${queuePriorityNormalizedLevel(level)}' for ${items.length} selected row(s).`);
  }

  function confirmClearQueuePriorityManifest() {
    if (typeof window.confirm !== "function") return false;
    return window.confirm([
      "Clear the entire queue priority manifest?",
      "",
      "This resets every backend priority override to Normal, including rows hidden by display filters or render caps.",
      "Backend Launch scope remains unchanged and is still decided by Launch routes.",
      "This sends a queue-state request only; it does not touch source, scratch, output, or rename files.",
    ].join("\n"));
  }

  async function clearQueuePriorityManifest() {
    if (queuePriorityCommandInFlight) {
      setText("queue-priority-status", "Queue priority command already in progress.");
      return;
    }
    if (!confirmClearQueuePriorityManifest()) {
      setText("queue-priority-status", "Priority manifest clear cancelled before any backend request.");
      return;
    }
    const seq = beginQueuePriorityCommand("Clearing entire priority manifest...");
    try {
      const result = await apiPost("/api/queue/priority", { clear_all: true });
      const msg = result && result.message ? result.message : "All priority manifest entries cleared.";
      if (isCurrentQueuePriorityCommand(seq)) setText("queue-priority-status", msg);
      if (typeof appendCommandResult === "function") appendCommandResult({ command: "queue.priority", ok: Boolean(result && result.ok), severity: result && result.ok ? "ok" : "error", message: msg });
      if (result && result.ok) clearDisplayedQueuePriorityManifest();
      if (result && result.ok && typeof refreshAll === "function") await refreshAll();
    } catch (err) {
      if (isCurrentQueuePriorityCommand(seq)) setText("queue-priority-status", `Priority manifest clear failed: ${err}`);
    } finally {
      endQueuePriorityCommand(seq);
    }
  }

  function queueManualOrderStatus(message) {
    setText("queue-manual-order-status", message);
  }

  function queueManualOrderKeyOrder(rows) {
    return (Array.isArray(rows) ? rows : [])
      .map(queueRowKey)
      .filter(Boolean);
  }

  function resetQueueManualOrderLoadedKeys(rows = lastQueueRows) {
    queueManualOrderLoadedKeys = queueManualOrderKeyOrder(rows);
    queueManualOrderDraftDirty = false;
  }

  function queueManualOrderCurrentKeySignature() {
    return queueManualOrderKeyOrder(lastQueueRows).join("\u001f");
  }

  function queueManualOrderLoadedKeySignature() {
    return queueManualOrderLoadedKeys.join("\u001f");
  }

  function syncQueueManualOrderDraftDirty() {
    queueManualOrderDraftDirty = Boolean(
      queueManualOrderLoadedKeys.length
      && queueManualOrderCurrentKeySignature() !== queueManualOrderLoadedKeySignature()
    );
    return queueManualOrderDraftDirty;
  }

  function queueManualOrderSelectValue() {
    const select = byId("queue-strategy-select");
    return select ? String(select.value || "") : queueActiveStrategy;
  }

  function queueManualOrderIsEnabled() {
    return queueManualOrderSelectValue() === "ManualOrder";
  }

  function queueManualOrderRowPhase(row) {
    const level = queuePriorityNormalizedLevel(row?.manifest_priority_level);
    const isTv = String(row?.media_type || row?.media_kind || "").trim().toLowerCase() === "tv" || Boolean(row?.is_tv);
    if (level === "hold") return "hold";
    if (level === "low") return "low";
    if (level === "high" || (Boolean(row?.is_priority) && level === "normal")) return isTv ? "priority-tv" : "priority-movie";
    return isTv ? "tv" : "movie";
  }

  function queueManualOrderPhaseLabel(phase) {
    const labels = {
      "priority-movie": "priority movies",
      "priority-tv": "priority TV",
      movie: "normal movies",
      tv: "normal TV",
      low: "low priority",
      hold: "held rows",
    };
    return labels[phase] || "this backend phase";
  }

  function queueManualOrderItemPath(row) {
    return queuePriorityRowPath(row);
  }

  function queueManualOrderPositionItems() {
    return lastQueueRows
      .map((row, index) => {
        const path = queueManualOrderItemPath(row);
        if (!path) return null;
        return {
          path,
          level: queuePriorityNormalizedLevel(row?.manifest_priority_level),
          position: index + 1,
        };
      })
      .filter(Boolean);
  }

  function queueManualOrderSelectedContext() {
    const selectedRows = getSelectedQueuePriorityRows().filter((row) => queueManualOrderItemPath(row));
    if (!selectedRows.length) {
      return { ok: false, message: "Select one or more queue rows before moving manual order." };
    }
    const phase = queueManualOrderRowPhase(selectedRows[0]);
    if (phase === "hold") {
      return { ok: false, message: "Held rows are excluded from backend processing and cannot be manually ordered." };
    }
    const eligibleRows = selectedRows.filter((row) => queueManualOrderRowPhase(row) === phase);
    const selectedKeys = new Set(eligibleRows.map(queueRowKey).filter(Boolean));
    if (!selectedKeys.size) {
      return { ok: false, message: "The selected row does not have a stable queue key for manual ordering." };
    }
    const phaseRows = lastQueueRows.filter((row) => queueManualOrderRowPhase(row) === phase && queueManualOrderItemPath(row));
    return {
      ok: true,
      phase,
      phaseRows,
      selectedKeys,
      ignoredCount: selectedRows.length - eligibleRows.length,
    };
  }

  function queueManualOrderSameKeys(left, right) {
    if (left.length !== right.length) return false;
    return left.every((row, index) => queueRowKey(row) === queueRowKey(right[index]));
  }

  function queueManualOrderMoveRows(rows, selectedKeys, mode, targetKey = "") {
    const next = rows.slice();
    const isSelected = (row) => selectedKeys.has(queueRowKey(row));
    if (mode === "top") {
      return next.filter(isSelected).concat(next.filter((row) => !isSelected(row)));
    }
    if (mode === "bottom") {
      return next.filter((row) => !isSelected(row)).concat(next.filter(isSelected));
    }
    if (mode === "up") {
      for (let index = 1; index < next.length; index += 1) {
        if (isSelected(next[index]) && !isSelected(next[index - 1])) {
          const previous = next[index - 1];
          next[index - 1] = next[index];
          next[index] = previous;
        }
      }
      return next;
    }
    if (mode === "down") {
      for (let index = next.length - 2; index >= 0; index -= 1) {
        if (isSelected(next[index]) && !isSelected(next[index + 1])) {
          const following = next[index + 1];
          next[index + 1] = next[index];
          next[index] = following;
        }
      }
      return next;
    }
    if (mode === "drop") {
      if (!targetKey || selectedKeys.has(targetKey)) return next;
      const selectedRows = next.filter(isSelected);
      const remaining = next.filter((row) => !isSelected(row));
      const targetIndex = remaining.findIndex((row) => queueRowKey(row) === targetKey);
      if (targetIndex < 0) return next;
      remaining.splice(targetIndex, 0, ...selectedRows);
      return remaining;
    }
    return next;
  }

  function queueManualOrderApplyPhaseRows(phase, phaseRows) {
    let phaseIndex = 0;
    lastQueueRows = lastQueueRows.map((row) => {
      if (queueManualOrderRowPhase(row) !== phase || !queueManualOrderItemPath(row)) return row;
      const replacement = phaseRows[phaseIndex];
      phaseIndex += 1;
      return replacement || row;
    });
    refreshDisplayedQueuePriorityRows();
    syncQueueManualOrderDraftDirty();
  }

  async function saveQueueManualOrderPositions(message) {
    if (queueScanLoading) {
      queueManualOrderStatus("Manual order is paused while the backend builds a fresh queue preview. Retry after the refreshed snapshot arrives.");
      return false;
    }
    if (queuePriorityCommandInFlight) {
      queueManualOrderStatus("A queue priority/order command is already in progress.");
      return false;
    }
    const items = queueManualOrderPositionItems();
    if (!items.length) {
      queueManualOrderStatus("No queue rows are available to save manual order positions.");
      return false;
    }
    if (!syncQueueManualOrderDraftDirty()) {
      queueManualOrderStatus("No staged manual-order changes to save.");
      updateQueueManualOrderControls();
      return false;
    }
    const seq = beginQueuePriorityCommand();
    queueManualOrderStatus(`Saving loaded backend manual positions for ${items.length} row(s)...`);
    let finalStatusMessage = "";
    try {
      const result = await apiPost("/api/queue/priority", { items });
      const ok = Boolean(result && result.ok);
      const resultMessage = result && result.message ? result.message : message || "Manual order positions saved.";
      finalStatusMessage = ok
        ? `${message || resultMessage} ManualOrder takes effect on the next backend queue build.`
        : `Manual order save failed: ${resultMessage}`;
      if (isCurrentQueuePriorityCommand(seq)) {
        queueManualOrderStatus(finalStatusMessage);
      }
      if (typeof appendCommandResult === "function") {
        appendCommandResult({
          command: "queue.priority",
          ok,
          severity: ok ? "ok" : "error",
          message: ok ? (message || resultMessage) : resultMessage,
        });
      }
      if (ok) resetQueueManualOrderLoadedKeys(lastQueueRows);
      return ok;
    } catch (err) {
      finalStatusMessage = `Manual order save failed: ${err}`;
      if (isCurrentQueuePriorityCommand(seq)) queueManualOrderStatus(finalStatusMessage);
      return false;
    } finally {
      endQueuePriorityCommand(seq);
      updateQueueManualOrderControls();
      if (finalStatusMessage) queueManualOrderStatus(finalStatusMessage);
    }
  }

  async function moveQueueManualOrder(mode, targetKey = "") {
    if (queueScanLoading) {
      queueManualOrderStatus("Manual order is paused while the backend builds a fresh queue preview. Retry after the refreshed snapshot arrives.");
      updateQueueManualOrderControls();
      return;
    }
    if (!queueManualOrderIsEnabled()) {
      queueManualOrderStatus("Choose Manual Order in the strategy selector to enable drag/drop and arrow moves.");
      updateQueueManualOrderControls();
      return;
    }
    const context = queueManualOrderSelectedContext();
    if (!context.ok) {
      queueManualOrderStatus(context.message);
      updateQueueManualOrderControls();
      return;
    }
    const nextPhaseRows = queueManualOrderMoveRows(context.phaseRows, context.selectedKeys, mode, targetKey);
    if (queueManualOrderSameKeys(context.phaseRows, nextPhaseRows)) {
      queueManualOrderStatus(`Selected row(s) are already at that edge within ${queueManualOrderPhaseLabel(context.phase)}.`);
      updateQueueManualOrderControls();
      return;
    }
    queueManualOrderApplyPhaseRows(context.phase, nextPhaseRows);
    const ignored = context.ignoredCount > 0 ? ` ${context.ignoredCount} selected row(s) in other backend phases stayed put.` : "";
    queueManualOrderStatus(`Staged manual order for ${queueManualOrderPhaseLabel(context.phase)}.${ignored} Use Save Loaded Backend Order to write backend positions, or Discard Loaded Order Changes to restore the loaded order.`);
    renderQueueRows({ preservePage: true });
    updateQueueManualOrderControls();
  }

  async function saveCurrentQueueManualOrder() {
    if (!queueManualOrderIsEnabled()) {
      queueManualOrderStatus("Choose Manual Order in the strategy selector before saving manual positions.");
      updateQueueManualOrderControls();
      return;
    }
    await saveQueueManualOrderPositions("Saved loaded backend queue order to the backend manifest. Display filters and render caps did not define the saved scope.");
    updateQueueManualOrderControls();
  }

  function discardQueueManualOrderDraft() {
    if (!queueManualOrderIsEnabled()) {
      queueManualOrderStatus("Choose Manual Order in the strategy selector before discarding staged positions.");
      updateQueueManualOrderControls();
      return;
    }
    if (!syncQueueManualOrderDraftDirty()) {
      queueManualOrderStatus("No staged manual-order changes to discard.");
      updateQueueManualOrderControls();
      return;
    }
    restoreQueueManualOrderLoadedOrder();
    queueManualOrderStatus("Discarded staged manual-order changes. Loaded backend order restored locally; no backend request was sent.");
    renderQueueRows({ preservePage: true });
    updateQueueManualOrderControls();
  }

  function restoreQueueManualOrderLoadedOrder() {
    const currentRowsByKey = new Map(lastQueueRows.map((row) => [queueRowKey(row), row]));
    const restored = [];
    queueManualOrderLoadedKeys.forEach((key) => {
      const row = currentRowsByKey.get(key);
      if (!row) return;
      restored.push(row);
      currentRowsByKey.delete(key);
    });
    lastQueueRows = restored.concat(Array.from(currentRowsByKey.values()));
    queueManualOrderDraftDirty = false;
    refreshDisplayedQueuePriorityRows();
  }

  function wireQueueManualOrderRow(row, item) {
    if (!row) return;
    const key = queueRowKey(item);
    const enabled = queueManualOrderIsEnabled() && queueManualOrderRowPhase(item) !== "hold";
    row.draggable = enabled;
    row.classList.toggle("queue-manual-order-row", enabled);
    if (enabled) {
      row.dataset.manualOrderDraggable = "true";
      row.title = row.title ? `${row.title} Manual order: drag to move within this backend phase.` : "Manual order: drag to move within this backend phase.";
    } else {
      delete row.dataset.manualOrderDraggable;
    }
    row.addEventListener("keydown", (event) => {
      if (!event.altKey || (event.key !== "ArrowUp" && event.key !== "ArrowDown")) return;
      event.preventDefault();
      event.stopImmediatePropagation();
      if (key && !getSelectedQueuePriorityRowKeys().includes(key)) selectQueueRow(item);
      void moveQueueManualOrder(event.key === "ArrowUp" ? "up" : "down");
    }, true);
    row.addEventListener("dragstart", (event) => {
      if (!queueManualOrderIsEnabled() || !enabled || !key) {
        event.preventDefault();
        return;
      }
      if (!getSelectedQueuePriorityRowKeys().includes(key)) selectQueueRow(item);
      queueManualDragKey = key;
      row.classList.add("is-manual-dragging");
      if (event.dataTransfer) {
        event.dataTransfer.effectAllowed = "move";
        event.dataTransfer.setData("text/plain", key);
      }
    });
    row.addEventListener("dragover", (event) => {
      if (!queueManualDragKey || !enabled) return;
      event.preventDefault();
      row.classList.add("is-manual-drop-target");
      if (event.dataTransfer) event.dataTransfer.dropEffect = "move";
    });
    row.addEventListener("dragleave", () => {
      row.classList.remove("is-manual-drop-target");
    });
    row.addEventListener("drop", (event) => {
      if (!queueManualDragKey || !enabled) return;
      event.preventDefault();
      row.classList.remove("is-manual-drop-target");
      void moveQueueManualOrder("drop", key);
    });
    row.addEventListener("dragend", () => {
      queueManualDragKey = "";
      row.classList.remove("is-manual-dragging", "is-manual-drop-target");
    });
  }

  function updateQueueManualOrderControls() {
    syncQueueManualOrderDraftDirty();
    const enabled = queueManualOrderIsEnabled();
    const hasRows = lastQueueRows.length > 0 && !queueScanLoading;
    const hasSelection = getSelectedQueuePriorityRows().length > 0;
    [
      "queue-manual-save-order-btn",
      "queue-manual-discard-order-btn",
      "queue-manual-move-top-btn",
      "queue-manual-move-up-btn",
      "queue-manual-move-down-btn",
      "queue-manual-move-bottom-btn",
    ].forEach((id) => {
      const button = byId(id);
      if (!button) return;
      const needsSelection = !["queue-manual-save-order-btn", "queue-manual-discard-order-btn"].includes(id);
      const needsDraft = id === "queue-manual-save-order-btn" || id === "queue-manual-discard-order-btn";
      button.disabled = queuePriorityCommandInFlight || !enabled || !hasRows || (needsSelection && !hasSelection) || (needsDraft && !queueManualOrderDraftDirty);
    });
    const status = byId("queue-manual-order-status");
    if (!status) return;
    const currentStatus = String(status.textContent || "");
    const preserveResultStatus = /^(Saved loaded backend queue order|Manual order save failed|Discarded staged manual-order changes)/.test(currentStatus);
    if (!enabled) {
      status.textContent = "Manual order controls are available when the strategy selector is Manual Order. Move controls stage loaded backend rows locally; Save Loaded Backend Order writes the staged positions. Display filters and render caps do not define Launch scope.";
    } else if (queueScanLoading) {
      status.textContent = "Manual order is paused while the backend builds a fresh queue preview.";
    } else if (!hasRows) {
      status.textContent = "Manual order is active, but no queue rows are loaded.";
    } else if (queuePriorityCommandInFlight) {
      status.textContent = "Manual order is paused while a backend queue priority/order request is in progress.";
    } else if (queueManualOrderDraftDirty) {
      status.textContent = "Manual order has staged local changes. Save Loaded Backend Order writes backend positions; Discard restores the loaded order. Launch scope is unchanged.";
    } else if (!hasSelection) {
      if (preserveResultStatus) return;
      status.textContent = "Manual order is active. Select a row, use arrow buttons or Alt+Up/Alt+Down, or drag within its backend phase to stage local order changes.";
    }
  }

  function initQueueManualOrderToolbar() {
    const wire = (id, handler) => {
      const btn = byId(id);
      if (btn) btn.addEventListener("click", handler);
    };
    wire("queue-manual-save-order-btn", () => saveCurrentQueueManualOrder());
    wire("queue-manual-discard-order-btn", () => discardQueueManualOrderDraft());
    wire("queue-manual-move-top-btn", () => moveQueueManualOrder("top"));
    wire("queue-manual-move-up-btn", () => moveQueueManualOrder("up"));
    wire("queue-manual-move-down-btn", () => moveQueueManualOrder("down"));
    wire("queue-manual-move-bottom-btn", () => moveQueueManualOrder("bottom"));
    wire("queue-page-prev-btn", () => moveQueueTablePage(-1));
    wire("queue-page-next-btn", () => moveQueueTablePage(1));
    const select = byId("queue-strategy-select");
    if (select) {
      select.addEventListener("change", () => {
        if (!queueManualOrderIsEnabled() && queueManualOrderDraftDirty) {
          restoreQueueManualOrderLoadedOrder();
          queueManualOrderStatus("Discarded staged manual-order changes because Manual Order is no longer selected. No backend request was sent.");
        }
        updateQueueManualOrderControls();
        renderQueueRows();
      });
    }
    updateQueueManualOrderControls();
  }

  function initQueuePriorityToolbar() {
    const wire = (id, handler) => {
      const btn = byId(id);
      if (btn) btn.addEventListener("click", handler);
    };

    wire("queue-priority-promote-btn", () => sendSelectedQueuePriority("high", "Operator promoted via toolbar"));
    wire("queue-priority-normal-btn",  () => sendSelectedQueuePriority("normal", ""));
    wire("queue-priority-low-btn",     () => sendSelectedQueuePriority("low", "Operator demoted via toolbar"));
    wire("queue-priority-hold-btn",    () => sendSelectedQueuePriority("hold", "Operator hold via toolbar"));
    const refreshBtn = typeof document.querySelector === "function" ? document.querySelector("[data-queue-refresh-button]") : null;
    if (refreshBtn) refreshBtn.addEventListener("click", () => requestQueueScan());

    wire("queue-priority-promote-movies-btn", () => {
      const items = lastQueueRows
        .filter((r) => String(r.media_type || "").toLowerCase() === "movie")
        .map((r) => ({ path: r.source_path || r.relative_path || "", level: "high", reason: "Bulk promote all movies" }))
        .filter((i) => i.path);
      if (!confirmLoadedQueuePriorityBulk("movie", items)) {
        setText("queue-priority-status", "Loaded-row movie priority update cancelled before any backend request.");
        return;
      }
      sendQueuePriorityBulk(items, `Promoted ${items.length} loaded Movie row(s) to High.`);
    });

    wire("queue-priority-promote-tv-btn", () => {
      const items = lastQueueRows
        .filter((r) => String(r.media_type || "").toLowerCase() === "tv")
        .map((r) => ({ path: r.source_path || r.relative_path || "", level: "high", reason: "Bulk promote all TV" }))
        .filter((i) => i.path);
      if (!confirmLoadedQueuePriorityBulk("tv", items)) {
        setText("queue-priority-status", "Loaded-row TV priority update cancelled before any backend request.");
        return;
      }
      sendQueuePriorityBulk(items, `Promoted ${items.length} loaded TV row(s) to High.`);
    });

    wire("queue-priority-clear-all-btn", clearQueuePriorityManifest);
    updateQueuePriorityControls();
  }

  // Wire toolbar on DOMContentLoaded (or immediately if already loaded)
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initQueuePriorityToolbar);
    document.addEventListener("DOMContentLoaded", initQueueManualOrderToolbar);
  } else {
    initQueuePriorityToolbar();
    initQueueManualOrderToolbar();
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

  const QUEUE_STRATEGY_DESCRIPTIONS = {
    Standard: "Priority, then Movies, then TV using the normal backend ordering.",
    FreshestFirst: "Put the newest detected work ahead of older rows.",
    ShowComplete: "Group TV work so a show can finish together.",
    RoundRobin: "Alternate across media groups to avoid one bucket dominating.",
    DeadlineAware: "Prefer work with deadline evidence from backend state.",
    SmallFirst: "Run smaller files first when a quick pass is useful.",
    LargeFirst: "Run larger files first when long jobs should start earlier.",
    ManualOrder: "Use the operator-saved order for loaded backend rows.",
  };

  function splitQueueStrategyOptionText(option) {
    const text = String(option?.textContent || option?.value || "").trim();
    const parts = text.split(/\s+[—-]\s+/);
    return {
      title: parts[0] || text,
      detail: parts.slice(1).join(" - ") || QUEUE_STRATEGY_DESCRIPTIONS[option?.value] || "",
    };
  }

  function syncQueueStrategyChoiceGroup() {
    const select = byId("queue-strategy-select");
    const group = document.querySelector("[data-queue-strategy-choice-grid]");
    if (!select || !group) return;
    group.querySelectorAll("input[type='radio']").forEach((radio) => {
      const selected = String(radio.value || "") === String(select.value || "");
      radio.checked = selected;
      radio.closest(".enhanced-choice-card")?.classList.toggle("is-selected", selected);
    });
  }

  function enhanceQueueStrategySelector() {
    const select = byId("queue-strategy-select");
    if (!select || document.querySelector("[data-queue-strategy-choice-grid]")) {
      syncQueueStrategyChoiceGroup();
      return;
    }
    const label = document.querySelector('label[for="queue-strategy-select"]');
    const grid = document.createElement("div");
    grid.className = "enhanced-choice-grid queue-strategy-choice-grid";
    grid.dataset.queueStrategyChoiceGrid = "true";
    grid.setAttribute("role", "radiogroup");
    grid.setAttribute("aria-label", "Queue order strategy");

    Array.from(select.options || []).forEach((option) => {
      const value = String(option.value || "");
      const optionText = splitQueueStrategyOptionText(option);
      const optionId = `queue-strategy-choice-${value.replace(/[^a-z0-9_-]+/gi, "-")}`;
      const card = document.createElement("label");
      card.className = "enhanced-choice-card queue-strategy-choice";
      card.htmlFor = optionId;

      const radio = document.createElement("input");
      radio.type = "radio";
      radio.id = optionId;
      radio.name = "queue-strategy-choice";
      radio.value = value;
      radio.checked = value === String(select.value || "");
      radio.addEventListener("change", () => {
        if (!radio.checked) return;
        select.value = value;
        select.dispatchEvent(new Event("input", { bubbles: true }));
        select.dispatchEvent(new Event("change", { bubbles: true }));
        syncQueueStrategyChoiceGroup();
      });

      const title = document.createElement("span");
      title.className = "enhanced-choice-card-title";
      title.textContent = optionText.title;

      const detail = document.createElement("span");
      detail.className = "enhanced-choice-card-detail";
      detail.textContent = optionText.detail;
      card.append(radio, title, detail);
      grid.appendChild(card);
    });

    if (label) label.classList.add("enhanced-choice-source-label");
    select.classList.add("enhanced-choice-source");
    select.addEventListener("input", syncQueueStrategyChoiceGroup);
    select.addEventListener("change", syncQueueStrategyChoiceGroup);
    select.insertAdjacentElement("afterend", grid);
    syncQueueStrategyChoiceGroup();
  }

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
        queueActiveStrategy = strategy;
        sel.value = strategy;
        syncQueueStrategyChoiceGroup();
      }
      // Show source hint if strategy came from UI override vs default
      const source = data && data.source ? String(data.source) : "default";
      const statusEl = document.getElementById("queue-strategy-status");
      if (statusEl) {
        statusEl.textContent = source === "state_file"
          ? `Active strategy: ${strategy} (saved).`
          : `Active strategy: ${strategy} (config default).`;
      }
      if (lastQueueRows.length) renderQueueRows();
      else updateQueueManualOrderControls();
    } catch (_) {
      // Silently ignore — API may not be up yet
      updateQueueManualOrderControls();
    }
  }

  // Revert the selector (and its radio-card mirror) to the last strategy the
  // backend confirmed, so a failed apply does not leave the UI showing an
  // unapplied strategy as if it were active.
  function resetQueueStrategySelectorToActive() {
    const sel = document.getElementById("queue-strategy-select");
    if (!sel) return;
    if (QUEUE_STRATEGIES.includes(queueActiveStrategy)) sel.value = queueActiveStrategy;
    syncQueueStrategyChoiceGroup();
    updateQueueManualOrderControls();
    if (lastQueueRows.length) renderQueueRows();
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
        updateQueueManualOrderControls();
      } else {
        const msg = (payload && payload.message) ? payload.message : "Unknown error.";
        if (status) status.textContent = `Error: ${msg} Selector reset to active strategy "${queueActiveStrategy}".`;
        if (payload) appendCommandResult(payload);
        resetQueueStrategySelectorToActive();
      }
    } catch (err) {
      if (status) status.textContent = `Error: ${err.message || err} Selector reset to active strategy "${queueActiveStrategy}".`;
      resetQueueStrategySelectorToActive();
    }
  }

  function initQueueStrategySelector() {
    enhanceQueueStrategySelector();
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
