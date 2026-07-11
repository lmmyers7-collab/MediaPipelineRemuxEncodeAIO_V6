(function () {
  const formatters = window.mediaPipelineFormatters || {};
  const shortenPath = typeof formatters.shortenPath === "function" ? formatters.shortenPath : null;
  const QUEUE_READ_ONLY_BOUNDARY = "Mutation guardrail: read-only evidence; backend routes own queue and launch changes.";
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

  function diagnosticsBridgeApi() {
    return window.mediaPipelineDiagnosticsBridge || {};
  }
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
      queueValidationStatus: (...args) => queueValidationStatus(...args),
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
      queueSnapshotIsStale: (...args) => queueSnapshotIsStale(...args),
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
      appendDiagnosticsBridgeButton: diagnosticsBridgeApi().appendDiagnosticsBridgeButton,
      appendDiagnosticsBridgeGroupedButtons: diagnosticsBridgeApi().appendDiagnosticsBridgeGroupedButtons,
      byId: typeof byId === "function" ? byId : window.byId,
      commandHistoryCompactEvidenceLine: window.commandHistoryCompactEvidenceLine,
      diagnosticsBridgeHandoffLines: diagnosticsBridgeApi().diagnosticsBridgeHandoffLines,
      diagnosticsBridgeRowTrustLines: diagnosticsBridgeApi().diagnosticsBridgeRowTrustLines,
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
      queueCollisionLines: (...args) => queueCollisionLines(...args),
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
      commandHistoryIssueLevel: window.mediaPipelineCommandHistory?.commandHistoryIssueLevel,
      queueRowKey,
      queueRuntimeLines: (...args) => queueRuntimeLines(...args),
      queueSnapshotIsStale: (...args) => queueSnapshotIsStale(...args),
      queueTableRowStatus,
      renderQueueDetail,
      renderQueueReviewDigest,
      renderQueueRows: (...args) => renderQueueRows(...args),
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

  const __queueRerunMod = window.__queueRerunModule || {};
  delete window.__queueRerunModule;
  const _queueRerun = typeof __queueRerunMod.createQueueRerunModule === "function"
    ? __queueRerunMod.createQueueRerunModule({
      byId: typeof byId === "function" ? byId : window.byId,
      setText: typeof setText === "function" ? setText : window.setText,
      apiGet: typeof apiGet === "function" ? apiGet : window.apiGet,
      apiPost: typeof apiPost === "function" ? apiPost : window.apiPost,
    })
    : {};
  const {
    initQueueRerunEvents = _queueNoop,
    refreshQueueRerunControlsForInput = _queueNoop,
    scheduleQueueRerunPreviewRefresh = _queueNoop,
    refreshRerunPreview = _queueNoop,
    selectRerunCsvPathForPreview = _queueNoop,
    refreshRerunResults = _queueNoop,
    inspectSelectedRerunCsv = _queueNoop,
    openSelectedRerunCsv = _queueNoop,
    requestRerunContinue = _queueNoop,
    startRerunFromForm = _queueNoop,
    setQueueRerunBusy = _queueNoop,
    updateQueueRerunButtonState = _queueNoop,
    postRerunPreview = _queueNoop,
    postRerunNetworkPreview = _queueNoop,
    postRerunNetworkStartDryRun = _queueNoop,
    postRerunNetworkStart = _queueNoop,
    postRerunStart = _queueNoop,
    postRerunControlStopAfterCurrent = _queueNoop,
    postRerunContinue = _queueNoop,
    postRerunOpen = _queueNoop,
    postRerunPromoteDryRun = _queueNoop,
    postRerunPromote = _queueNoop,
    getRerunResults = _queueNoop,
    renderRerunResults = _queueNoop,
    renderRerunQueueStateRows = _queueNoop,
    openRerunRowTarget = _queueNoop,
    promoteRerunRowToPending = _queueNoop,
    stopRerunAfterCurrent = _queueNoop,
    checkNetworkRerunStartDryRun = _queueNoop,
  } = _queueRerun;

  const __queueTabsMod = window.__queueTabsModule || {};
  delete window.__queueTabsModule;
  const _queueTabs = typeof __queueTabsMod.createQueueTabsModule === "function"
    ? __queueTabsMod.createQueueTabsModule({ updateQueueRerunButtonState, refreshRerunResults })
    : {};
  const { queueTabIds = _queueEmptyArray, activateQueueTab = _queueNoop, initQueueTabNav = _queueNoop } = _queueTabs;

  const __queueDecisionMod = window.__queueDecisionModule || {};
  delete window.__queueDecisionModule;
  const _queueDecision = typeof __queueDecisionMod.createQueueDecisionModule === "function"
    ? __queueDecisionMod.createQueueDecisionModule({
      byId, setText, queueCurrentFilterScope, queueLaunchDecisionStatus, queueLaunchDecisionSummaryLines,
      queueReviewDigestStatus, queueReviewDigestAction, queueReviewRows, queueListText,
      getLastQueuePayload: () => lastQueuePayload, getLastQueueRows: () => lastQueueRows,
    })
    : {};
  const {
    renderQueueDecisionHeader = _queueNoop,
    renderQueueAttentionSummary = _queueNoop,
  } = _queueDecision;

  function queueSourceTileTitle(tile) {
    const parts = [tile.label, tile.value, tile.meta, tile.detail, tile.fullDetail]
      .concat((Array.isArray(tile.chips) ? tile.chips : []).map((chip) => chip?.title || chip?.label))
      .concat((Array.isArray(tile.meter) ? [queueSourceMeterLabel(tile.meter)] : []))
      .concat((Array.isArray(tile.paths) ? tile.paths.map((path) => `${path.title || path.label} ${path.count}`) : []))
      .filter(Boolean);
    return parts.join(" | ");
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
    hideQueueTableLegend();
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

  const __queueStatusPanelsMod = window.__queueStatusPanelsModule || {};
  delete window.__queueStatusPanelsModule;
  const _queueStatusPanels = typeof __queueStatusPanelsMod.createQueueStatusPanelsModule === "function"
    ? __queueStatusPanelsMod.createQueueStatusPanelsModule({
      appendCells: typeof appendCells === "function" ? appendCells : window.appendCells,
      byId: typeof byId === "function" ? byId : window.byId,
      clearRows: typeof clearRows === "function" ? clearRows : window.clearRows,
      documentRef: document,
      getSelectedQueueExcludedRowKey,
      makeRowSelectable: typeof makeRowSelectable === "function" ? makeRowSelectable : window.makeRowSelectable,
      queueFormatCounts,
      queueExcludedRowKey,
      queueFreshnessLine,
      queueHiddenSidecarLine,
      queueSnapshotIsStale,
      readOnlyBoundary: QUEUE_READ_ONLY_BOUNDARY,
      selectQueueExcludedRow,
      setText: typeof setText === "function" ? setText : window.setText,
      updateTableStatusLegend: typeof updateTableStatusLegend === "function" ? updateTableStatusLegend : window.updateTableStatusLegend,
    })
    : {};
  const {
    queueBreakdownStatus = _queueEmptyString,
    queueBreakdownLines = _queueEmptyArray,
    renderQueueBreakdown = _queueNoop,
    queueRuntimeStatus = _queueEmptyString,
    queueRuntimeLines = _queueEmptyArray,
    renderQueueRuntime = _queueNoop,
    queueValidationStatus = _queueEmptyString,
    queueValidationChecklistLines = _queueEmptyArray,
    renderQueueValidation = _queueNoop,
    queueCollisionStatus = _queueEmptyString,
    queueCollisionLines = _queueEmptyArray,
    renderQueueCollision = _queueNoop,
    queueExcludedStatus = _queueEmptyString,
    queueExcludedSummaryLines = _queueEmptyArray,
    renderQueueExcluded = _queueNoop,
  } = _queueStatusPanels;
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

  const __queueTableViewMod = window.__queueTableViewModule || {};
  delete window.__queueTableViewModule;
  const _queueTableView = typeof __queueTableViewMod.createQueueTableViewModule === "function"
    ? __queueTableViewMod.createQueueTableViewModule({
      state: {
        get rows() { return lastQueueRows; },
        get payload() { return lastQueuePayload; },
        get emptyMessage() { return lastQueueEmptyMessage; },
        get scanLoading() { return queueScanLoading; },
        get pageStart() { return queueTablePageStart; },
        set pageStart(value) { queueTablePageStart = Number(value) || 0; },
        get filterSignature() { return queueTableFilterSignature; },
        set filterSignature(value) { queueTableFilterSignature = String(value || ""); },
      },
      byId: typeof byId === "function" ? byId : window.byId,
      clearRows: typeof clearRows === "function" ? clearRows : window.clearRows,
      filterFields: QUEUE_FILTER_FIELDS,
      filterResultSummaryLines: typeof filterResultSummaryLines === "function" ? filterResultSummaryLines : window.mediaPipelineDom?.filterResultSummaryLines,
      filterRows: typeof filterRows === "function" ? filterRows : window.filterRows,
      filterRowsByInvestigation: typeof filterRowsByInvestigation === "function" ? filterRowsByInvestigation : window.filterRowsByInvestigation,
      filterRowsByStatus: typeof filterRowsByStatus === "function" ? filterRowsByStatus : window.filterRowsByStatus,
      getCommandHistory: typeof getCommandHistory === "function" ? getCommandHistory : window.getCommandHistory,
      getSelectedQueuePriorityRowKeys,
      getSelectedQueueRow,
      getSelectedQueueRowKey,
      queueDisplayRowStatus,
      queueInvestigationFilterLabel,
      queueManualOrderIsEnabled: (...args) => queueManualOrderIsEnabled(...args),
      queueMatchesInvestigationFilter,
      readOnlyBoundary: QUEUE_READ_ONLY_BOUNDARY,
      renderQueueAttentionSummary,
      renderQueueBackendLaunchScopePreview,
      renderQueueDecisionHeader,
      renderQueueDetail,
      renderQueueLaunchDecisionChecklist,
      renderQueueLoadingTable: (...args) => renderQueueLoadingTable(...args),
      renderQueueTableRows,
      renderLimit: QUEUE_RENDER_LIMIT,
      setRenderedQueueRows,
      setText: typeof setText === "function" ? setText : window.setText,
      updateQueueManualOrderControls: (...args) => updateQueueManualOrderControls(...args),
      wireManualOrderRow: (...args) => wireQueueManualOrderRow(...args),
    })
    : {};
  const {
    queueClampScrollOffset = _queueNoop,
    queueTableScrollSnapshot = _queueNoop,
    restoreQueueTableScroll = _queueNoop,
    updateQueueSelectionVisuals = _queueNoop,
    hideQueueTableLegend = _queueNoop,
    updateQueueTableLegend = _queueNoop,
    queueDisplayFilterSignature = _queueEmptyString,
    queueClampPageStart = _queueNoop,
    updateQueuePaginationControls = _queueNoop,
    moveQueueTablePage = _queueNoop,
    queueFilteredRowsForCurrentDisplay = _queueEmptyArray,
    setQueueFilterSummary = _queueNoop,
    renderQueueRows = _queueNoop,
    resetQueueFilters = _queueNoop,
  } = _queueTableView;

  const __queueSourceModelMod = window.__queueSourceModelModule || {};
  delete window.__queueSourceModelModule;
  const _queueSourceModel = typeof __queueSourceModelMod.createQueueSourceModelModule === "function"
    ? __queueSourceModelMod.createQueueSourceModelModule({
      shortenPath,
      queueDisplayRowStatus,
      queueFilteredRowsForCurrentDisplay,
      queuePathExtension,
      getLastQueuePayload: () => lastQueuePayload,
      getLastQueueRows: () => lastQueueRows,
    })
    : {};
  const {
    queueScanStatus = _queueEmptyObject,
    queueScanIsRunning = _queueFalse,
    queueSourceInventory = _queueEmptyObject,
    queueScanStatusLines = _queueEmptyArray,
    queueSourceInventoryLines = _queueEmptyArray,
    queueSourceInventoryTileModel = _queueEmptyArray,
    queueSourceMeterLabel = _queueEmptyString,
  } = _queueSourceModel;

  const __queueSourceRenderMod = window.__queueSourceRenderModule || {};
  delete window.__queueSourceRenderModule;
  const _queueSourceRender = typeof __queueSourceRenderMod.createQueueSourceRenderModule === "function"
    ? __queueSourceRenderMod.createQueueSourceRenderModule({
      byId,
      queueSourceMeterLabel,
      queueSourceTileTitle,
      queueSourceInventoryLines,
      queueSourceInventoryTileModel,
      queueScanIsRunning,
      getLastQueuePayload: () => lastQueuePayload,
    })
    : {};
  const {
    renderQueueSourceInventoryMessage = _queueNoop,
    renderQueueScanArtifacts = _queueNoop,
  } = _queueSourceRender;

  const __queueScanMod = window.__queueScanModule || {};
  delete window.__queueScanModule;
  const _queueScan = typeof __queueScanMod.createQueueScanModule === "function"
    ? __queueScanMod.createQueueScanModule({
      apiPost: typeof apiPost === "function" ? apiPost : window.apiPost,
      appendCommandResult: typeof appendCommandResult === "function" ? appendCommandResult : window.appendCommandResult,
      getScanInFlight: () => queueScanInFlight,
      queueScanIsRunning,
      refreshAll: typeof refreshAll === "function" ? refreshAll : window.refreshAll,
      renderQueueRows: () => renderQueueRows(),
      renderQueueSourceInventoryMessage,
      scheduleQueueScanPoll,
      setQueueFilterSummary,
      setQueueLoadingScreenVisible,
      setScanInFlight: (value) => { queueScanInFlight = Boolean(value); },
      setText: typeof setText === "function" ? setText : window.setText,
    })
    : {};
  const { requestQueueScan = _queueNoop } = _queueScan;
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
    activateQueueTab,
    initQueueTabNav,
    initQueueRerunEvents,
    refreshQueueRerunControlsForInput,
    scheduleQueueRerunPreviewRefresh,
    refreshRerunPreview,
    selectRerunCsvPathForPreview,
    refreshRerunResults,
    inspectSelectedRerunCsv,
    openSelectedRerunCsv,
    requestRerunContinue,
    startRerunFromForm,
    setQueueRerunBusy,
    updateQueueRerunButtonState,
    postRerunPreview,
    postRerunNetworkPreview,
    postRerunNetworkStartDryRun,
    postRerunNetworkStart,
    postRerunStart,
    postRerunControlStopAfterCurrent,
    postRerunContinue,
    postRerunOpen,
    postRerunPromoteDryRun,
    postRerunPromote,
    getRerunResults,
    renderRerunResults,
    renderRerunQueueStateRows,
    openRerunRowTarget,
    promoteRerunRowToPending,
    stopRerunAfterCurrent,
    checkNetworkRerunStartDryRun,
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
  window.isQueueOpenCommand = isQueueOpenCommand;
  window.queueOpenHistoryLine = queueOpenHistoryLine;
  window.renderQueueOpenHistory = renderQueueOpenHistory;
  // Compose priority, manual ordering, and strategy controls after the public
  // page namespace exists. The child owns control-specific lifecycle wiring.
  const __queueControlsMod = window.__queueControlsModule || {};
  delete window.__queueControlsModule;
  const _queueControls = typeof __queueControlsMod.createQueueControlsModule === "function"
    ? __queueControlsMod.createQueueControlsModule({
      appendCommandResult: typeof appendCommandResult === "function" ? appendCommandResult : window.appendCommandResult,
      apiGet: typeof apiGet === "function" ? apiGet : window.apiGet,
      apiPost: typeof apiPost === "function" ? apiPost : window.apiPost,
      byId: typeof byId === "function" ? byId : window.byId,
      documentRef: document,
      filteredRows: () => queueFilteredRowsForCurrentDisplay(),
      getExcludedRows: () => lastQueueExcludedRows,
      getPayload: () => lastQueuePayload,
      getRows: () => lastQueueRows,
      getScanLoading: () => queueScanLoading,
      getSelectedPriorityRows: () => getSelectedQueuePriorityRows(),
      initQueueRerunEvents,
      initQueueTabNav,
      overrideMarkers: displayedQueueFileOverrideMarkers,
      refreshAll: typeof refreshAll === "function" ? refreshAll : window.refreshAll,
      renderBreakdown: (payload, rows) => renderQueueBreakdown(payload, rows),
      renderRows: () => renderQueueRows(),
      renderSummary: (payload, rows) => renderQueueSummary(payload, rows),
      requestQueueScan,
      setPayload: (payload) => { lastQueuePayload = payload; },
      setRows: (rows) => { lastQueueRows = rows; },
      setText: typeof setText === "function" ? setText : window.setText,
      state: {
        get rows() { return lastQueueRows; },
        set rows(value) { lastQueueRows = Array.isArray(value) ? value : []; },
        get loadedKeys() { return queueManualOrderLoadedKeys; },
        set loadedKeys(value) { queueManualOrderLoadedKeys = Array.isArray(value) ? value : []; },
        get draftDirty() { return queueManualOrderDraftDirty; },
        set draftDirty(value) { queueManualOrderDraftDirty = Boolean(value); },
        get dragKey() { return queueManualDragKey; },
        set dragKey(value) { queueManualDragKey = String(value || ""); },
        get activeStrategy() { return queueActiveStrategy; },
        set activeStrategy(value) { queueActiveStrategy = String(value || "Standard"); },
      },
      strategyRoute: QUEUE_STRATEGY_ROUTE,
      syncSelectedRows: (rows, excludedRows) => syncSelectedQueueRows(rows, excludedRows),
      queuePriorityRoute: QUEUE_PRIORITY_ROUTE,
      queueRowKey,
    })
    : {};
  const {
    applyDisplayedFileOverrideMarker: applyDisplayedQueueFileOverrideMarker = _queueNoop,
    priorityItemsForSelected: queuePriorityItemsForSelected = _queueEmptyArray,
    rowWithDisplayedFileOverrideMarker: queueRowWithDisplayedFileOverrideMarker = _queueIdentity,
    queueManualOrderIsEnabled = _queueFalse,
    resetQueueManualOrderLoadedKeys = _queueNoop,
    sendSelectedPriority: sendSelectedQueuePriority = _queueNoop,
    updateManualOrderControls: updateQueueManualOrderControls = _queueNoop,
    wireQueueManualOrderRow = _queueNoop,
  } = _queueControls;
  Object.assign(window.mediaPipelineQueueView, {
    queuePriorityItemsForSelected,
    applyDisplayedQueueFileOverrideMarker,
    sendSelectedQueuePriority,
  });

})();
