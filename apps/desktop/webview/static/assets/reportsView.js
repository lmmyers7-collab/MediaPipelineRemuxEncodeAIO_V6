(function () {
  const commandHistoryView = window.mediaPipelineCommandHistory || {};
  const reportsStateModule = window.__reportsViewStateModule || {};
  delete window.__reportsViewStateModule;
  if (typeof reportsStateModule.createReportsState !== "function") {
    throw new Error("reports/state.js must load before reportsView.js");
  }
  const reportsState = reportsStateModule.createReportsState();
  const REPORTS_TAB_STORAGE_KEY = "mediapipeline-reports-tab";
  const REPORTS_ROW_RENDER_LIMIT = 250;
  const reportsInvestigationModule = window.__reportsViewInvestigationModule || {};
  delete window.__reportsViewInvestigationModule;
  if (typeof reportsInvestigationModule.createReportsInvestigationModule !== "function") {
    throw new Error("reports/investigation.js must load before reportsView.js");
  }
  const {
    getSelectedFailureGroup,
    selectedFailureGroupMarkerPaths,
    setReportChipPressed,
    getSelectedFailureRow,
    getSelectedFailureRows,
    failureMarkerModeActive,
    setFailureMarkerSourceMode,
    reportNumber,
    reportPreviewLoaded,
    reportCountBy,
    reportFormatCounts,
    reportSortedCountEntries,
    reportHumanLabel,
    reportCompactCountPairs,
    focusReportsQuickLinkTarget,
    setFailureQuickFilter,
    setAuditQuickFilter,
    activateQuickLink,
  } = reportsInvestigationModule.createReportsInvestigationModule({
    state: reportsState,
    byId,
    failureResolutionGroupKey: (...args) => failureResolutionGroupKey(...args),
    normalizeFailureMarkerPaths: (...args) => normalizeFailureMarkerPaths(...args),
    failureRowsForGroup: (...args) => failureRowsForGroup(...args),
    failureClearMarkerPathsForRow: (...args) => failureClearMarkerPathsForRow(...args),
    failureRowKey: (...args) => failureRowKey(...args),
    renderFailureResolutionGroups: (...args) => renderFailureResolutionGroups(...args),
    renderFailureRows: (...args) => renderFailureRows(...args),
    updateFailureClearConfirmState: (...args) => updateFailureClearConfirmState(...args),
    updateFailureLifecycleConfirmState: (...args) => updateFailureLifecycleConfirmState(...args),
    renderAuditRows: (...args) => renderAuditRows(...args),
    activateReportsTab: (...args) => activateReportsTab(...args),
  });
  let reportsAuditCommands = null;
  let reportsTriage = null;
  const reportsSharedModule = window.__reportsViewSharedModule || {};
  delete window.__reportsViewSharedModule;
  if (typeof reportsSharedModule.createReportsSharedModule !== "function") {
    throw new Error("reports/shared.js must load before reportsView.js");
  }
  const {
    hiddenSelectedCount,
    reportRenderedRows,
    reportRenderedRowsNote,
    reportTableStatusText,
    rowKeySet,
  } = reportsSharedModule.createReportsSharedModule({
    rowRenderLimit: REPORTS_ROW_RENDER_LIMIT,
  });
  const reportsShellModule = window.__reportsViewShellModule || {};
  delete window.__reportsViewShellModule;
  if (typeof reportsShellModule.createReportsShellModule !== "function") {
    throw new Error("reports/shell.js must load before reportsView.js");
  }
  const {
    activateReportsTab,
    appendReportOwnerNavigationButton,
    collectReportWarnings,
    initReportsTabNav,
    isReportOpenCommand,
    renderKeyPathRows,
    renderReportDiagnosticsActions,
    renderReportOpenHistory,
    renderReportWarnings,
    reportAddDiagnosticsAction,
    reportCompactPath,
    reportCountLabel,
    reportLabel,
    reportLatestState,
    reportOpenHistoryLine,
    reportOpenTarget,
    reportOpenTargetValues,
    reportOwnerFromText,
    reportOwnerPage,
  } = reportsShellModule.createReportsShellModule({
    appendCells,
    byId,
    clearRows,
    commandHistoryCompactEvidenceLine: typeof commandHistoryCompactEvidenceLine === "function" ? commandHistoryCompactEvidenceLine : null,
    commandHistoryView,
    diagnosticsBridgeApi,
    reportAuditJsonDetail,
    reportsTabIds,
    requestDiagnosticsOpen: typeof requestDiagnosticsOpen === "function" ? requestDiagnosticsOpen : null,
    requestDiagnosticsTail: typeof requestDiagnosticsTail === "function" ? requestDiagnosticsTail : null,
    setText,
    state: reportsState,
    tabStorageKey: REPORTS_TAB_STORAGE_KEY,
    updatePagePanelEmptyStates: typeof updatePagePanelEmptyStates === "function" ? updatePagePanelEmptyStates : null,
  });
  const reportsFailureModelModule = window.__reportsViewFailureModelModule || {};
  delete window.__reportsViewFailureModelModule;
  if (typeof reportsFailureModelModule.createReportsFailureModelModule !== "function") {
    throw new Error("reports/failureModel.js must load before reportsView.js");
  }
  const {
    failureActionOwner,
    failureClassificationText,
    failureClearError,
    failureClearMarkerPath,
    failureClearMarkerPathsForRow,
    failureClearUnavailableReason,
    failureCountsForRows,
    failureDiagnosticsActionsForGroup,
    failureDiagnosticsActionsForRow,
    failureDisplayValue,
    failureEmptyStateMessage,
    failureEvidenceDetails,
    failureEvidenceProofLines,
    failureEvidenceStreamLine,
    failureFileText,
    failureGroupJournalKey,
    failureGroupLifecycleState,
    failureGroupMatchesChip,
    failureGroupSearchText,
    failureMarkerPath,
    failureMatchesChip,
    failurePlainSummaryText,
    failureReasonText,
    failureRecordedText,
    failureResolutionFallbackGroups,
    failureResolutionGroupForRow,
    failureResolutionGroupKey,
    failureResolutionGroupsFromPayload,
    failureResolutionPrimaryAction,
    failureResolutionSummaryPayload,
    failureRetryDetailLines,
    failureRetryPreviewSummaryLine,
    failureRetryRows,
    failureRetryStateForRow,
    failureRetryStateFromRow,
    failureRetryStatePayload,
    failureRetrySummaryText,
    failureReviewBoardLines,
    failureReviewBoardTiles,
    failureReviewNextStep,
    failureReviewStatus,
    failureRootCauseLabel,
    failureRootCauseTone,
    failureRowKey,
    failureRowSearchText,
    failureRowsForGroup,
    failureSeverity,
    failureStageText,
    failureStatusLabel,
    failureSuggestedActionText,
    failureTableEvidenceText,
    failureTriage,
    normalizeFailureMarkerPaths,
  } = reportsFailureModelModule.createReportsFailureModelModule({
    failureMarkerModeActive,
    reportAddDiagnosticsAction,
    reportCountLabel,
    reportCompactCountPairs,
    reportCountBy,
    reportFormatCounts,
    reportHumanLabel,
    reportNumber,
    reportOwnerPage,
    reportPreviewLoaded,
    reportSortedCountEntries,
    selectedFailureGroupMarkerPaths,
    state: reportsState,
  });
  const failureClearButtonIds = [
    "failure-clear-confirm-button",
    "failure-primary-action-button",
  ];
  const failureArchiveButtonIds = [
    "failure-archive-confirm-button",
  ];
  const failureArtifactCleanupButtonIds = [
    "failure-artifact-cleanup-confirm-button",
  ];
  const failureLifecycleButtonIds = [
    "failure-lifecycle-ack-button",
    "failure-lifecycle-start-button",
    "failure-lifecycle-resolve-confirm-button",
    "failure-lifecycle-reopen-confirm-button",
  ];
  const FAILURE_LIFECYCLE_BACKEND_REASONS = {
    mark_resolved: "Operator marked failure resolved from Reports.",
    reopen: "Operator reopened failure from Reports.",
    waive_step: "Operator waived failure lifecycle step from Reports.",
  };
  const reportsFailureCommandsModule = window.__reportsViewFailureCommandsModule || {};
  delete window.__reportsViewFailureCommandsModule;
  if (typeof reportsFailureCommandsModule.createReportsFailureCommandsModule !== "function") {
    throw new Error("reports/failureCommands.js must load before reportsView.js");
  }
  const {
    configureFailurePrimaryAction,
    failureTransition,
    renderFailureArtifactCleanupResult,
    renderFailureArchiveResult,
    renderFailureClearResult,
    requestFailureArtifactCleanup,
    requestFailureEvidenceOpen,
    requestFailureEvidenceArchive,
    requestFailureLifecycleTransition,
    requestFailureMarkerClear,
    requestFailureRowClear,
    runFailurePrimaryAction,
    setFailureLifecycleButton,
    updateFailureArtifactCleanupConfirmState,
    updateFailureArchiveConfirmState,
    updateFailureClearConfirmState,
    updateFailureLifecycleConfirmState,
  } = reportsFailureCommandsModule.createReportsFailureCommandsModule({
    apiPost: (...args) => {
      const post = typeof window.apiPost === "function" ? window.apiPost : typeof apiPost === "function" ? apiPost : null;
      if (typeof post !== "function") throw new Error("apiPost is unavailable");
      return post(...args);
    },
    appendCommandResult: (...args) => {
      const append = typeof window.appendCommandResult === "function"
        ? window.appendCommandResult
        : typeof appendCommandResult === "function"
          ? appendCommandResult
          : null;
      if (typeof append === "function") return append(...args);
      return undefined;
    },
    byId,
    failureArchiveButtonIds,
    failureArtifactCleanupButtonIds,
    failureClearButtonIds,
    failureClearMarkerPathsForRow,
    failureClearUnavailableReason,
    failureCountsForRows,
    failureGroupJournalKey,
    failureLifecycleBackendReasons: FAILURE_LIFECYCLE_BACKEND_REASONS,
    failureLifecycleButtonIds,
    failureMarkerModeActive,
    failureResolutionFallbackGroups,
    failureResolutionGroupKey,
    failureResolutionGroupsFromPayload,
    failureResolutionPrimaryAction,
    failureRowKey,
    failureRowsForGroup,
    getSelectedFailureGroup,
    getSelectedFailureRow,
    getSelectedFailureRows,
    hiddenSelectedFailureCount: (...args) => hiddenSelectedFailureCount(...args),
    normalizeFailureMarkerPaths,
    refreshAll: (...args) => {
      const refresh = typeof window.refreshAll === "function" ? window.refreshAll : typeof refreshAll === "function" ? refreshAll : null;
      if (typeof refresh === "function") return refresh(...args);
      return undefined;
    },
    renderFailureDetail: (...args) => renderFailureDetail(...args),
    renderFailurePreview: (...args) => renderFailurePreview(...args),
    renderFailureRows: (...args) => renderFailureRows(...args),
    reportNumber,
    reportOwnerPage,
    reportRenderedRowsNote,
    rowRenderLimit: REPORTS_ROW_RENDER_LIMIT,
    selectedFailureGroupMarkerPaths,
    setButtonsBusy,
    setFailureMarkerSourceMode,
    setText,
    state: reportsState,
    visibleFailureRows: (...args) => visibleFailureRows(...args),
  });

  const reportsFailureViewModule = window.__reportsViewFailureViewModule || {};
  delete window.__reportsViewFailureViewModule;
  if (typeof reportsFailureViewModule.createReportsFailureViewModule !== "function") {
    throw new Error("reports/failureView.js must load before reportsView.js");
  }
  const {
    ensureSelectedFailureGroupVisible,
    eventTargetAcceptsText,
    handleReportsFailureKeyboard,
    hiddenSelectedFailureCount,
    moveFailureGroupSelection,
    renderFailureDetail,
    renderFailureLifecycleControls,
    renderFailureLifecyclePanels,
    renderFailurePlaybook,
    renderFailureArtifactSummary,
    renderFailurePreview,
    renderFailureResolutionDetail,
    renderFailureResolutionGroups,
    renderFailureResolutionSummary,
    renderFailureReviewBoard,
    renderFailureRows,
    renderFailureTimeline,
    renderFailureVerification,
    reportsFailuresTabActive,
    selectVisibleFailureArtifacts,
    selectFailureGroup,
    selectFailureRow,
    toggleFailureRowSelection,
    visibleFailureGroups,
    visibleFailureRows,
  } = reportsFailureViewModule.createReportsFailureViewModule({
    appendCells,
    appendReportOwnerNavigationButton,
    byId,
    clearRows,
    configureFailurePrimaryAction,
    ensureSelectedFailureGroupVisible: null,
    failureActionOwner,
    failureClassificationText,
    failureCountsForRows,
    failureDiagnosticsActionsForGroup,
    failureDiagnosticsActionsForRow,
    failureEmptyStateMessage,
    failureEvidenceProofLines,
    failureFileText,
    failureGroupLifecycleState,
    failureGroupMatchesChip,
    failureGroupSearchText,
    failureMarkerModeActive,
    failureMatchesChip,
    failurePlainSummaryText,
    failureReasonText,
    failureRecordedText,
    failureResolutionGroupForRow,
    failureResolutionGroupKey,
    failureResolutionGroupsFromPayload,
    failureResolutionPrimaryAction,
    failureResolutionSummaryPayload,
    failureRetryDetailLines,
    failureRetryPreviewSummaryLine,
    failureReviewBoardLines,
    failureReviewBoardTiles,
    failureReviewStatus,
    failureReviewTileNode,
    failureRowKey,
    failureRowsForGroup,
    failureSeverity,
    failureStageText,
    failureStatusLabel,
    failureSuggestedActionText,
    failureTableEvidenceText,
    failureTransition,
    filterRows: typeof filterRows === "function" ? filterRows : window.filterRows,
    getSelectedFailureGroup,
    getSelectedFailureRow,
    hiddenSelectedCount,
    makeRowSelectable,
    normalizeFailureMarkerPaths,
    renderReportDiagnosticsActions,
    renderReportTriage: (...args) => renderReportTriage(...args),
    reportCompactPath,
    reportNumber,
    reportRenderedRows,
    reportRenderedRowsNote,
    reportTableStatusText,
    requestFailureEvidenceOpen,
    rowKeySet,
    runFailurePrimaryAction,
    setCellStatusChip: typeof setCellStatusChip === "function" ? setCellStatusChip : window.setCellStatusChip,
    setFailureLifecycleButton,
    setReportChipPressed,
    setText,
    setTextState,
    state: reportsState,
    updateFailureArtifactCleanupConfirmState,
    updateFailureClearConfirmState,
    updateFailureLifecycleConfirmState,
    updateTableStatusLegend,
  });

  function diagnosticsBridgeApi() {
    return window.mediaPipelineDiagnosticsBridge || {};
  }
  const reportAuditCommandButtonIds = {
    sourceEdit: ["report-audit-add-source-button"],
    sourceScan: ["report-audit-scan-selected-button", "report-audit-scan-all-button"],
    start: ["report-audit-start-button"],
    stop: ["report-audit-stop-button"],
    policy: ["report-audit-score-policy-save-button", "report-audit-score-policy-reset-button"],
    triage: ["report-audit-ignore-selected-button", "report-audit-export-rerun-csv-button"],
  };
  const reportAuditScoreFieldIds = {
    redownload_bucket: "report-audit-score-redownload-bucket",
    high_issue: "report-audit-score-high-issue",
    rerun_bucket: "report-audit-score-rerun-bucket",
    medium_issue: "report-audit-score-medium-issue",
    review_bucket: "report-audit-score-review-bucket",
    fallback_issue: "report-audit-score-fallback-issue",
    redownload_bonus: "report-audit-score-redownload-bonus",
    rerun_bonus: "report-audit-score-rerun-bonus",
  };
  const reportAuditScoreGroupDefaultKeys = { high: "high_issue", medium: "medium_issue" };
  const reportsAuditModelModule = window.__reportsViewAuditModelModule || {};
  delete window.__reportsViewAuditModelModule;
  if (typeof reportsAuditModelModule.createReportsAuditModelModule !== "function") {
    throw new Error("reports/auditModel.js must load before reportsView.js");
  }
  const {
    auditActionOwner,
    auditDiagnosticsActionsForRow,
    auditEmptyStateMessage,
    auditMatchesChip,
    auditReviewBoardLines,
    auditReviewStatus,
    auditRowKey,
    auditRowSearchText,
  } = reportsAuditModelModule.createReportsAuditModelModule({
    reportAddDiagnosticsAction,
    reportCountBy,
    reportFormatCounts,
    reportNumber,
    reportPreviewLoaded,
    state: reportsState,
  });
  const reportsAuditViewModule = window.__reportsViewAuditViewModule || {};
  delete window.__reportsViewAuditViewModule;
  if (typeof reportsAuditViewModule.createReportsAuditViewModule !== "function") {
    throw new Error("reports/auditView.js must load before reportsView.js");
  }
  const {
    auditScoreThresholdValue,
    clearAuditSelection,
    getSelectedAuditRow,
    hiddenAuditSelectionMessage,
    hiddenSelectedAuditCount,
    renderAuditControls,
    renderAuditDetail,
    renderAuditPreview,
    renderAuditReviewBoard,
    renderAuditRows,
    runAuditSelectionAction,
    selectedAuditRowKeysList,
    selectAuditRow,
    selectAuditRowsAtOrAboveScore,
    selectVisibleAuditRows,
    toggleAuditRowSelection,
    updateAuditSelectionControls,
    visibleAuditRows,
  } = reportsAuditViewModule.createReportsAuditViewModule({
    appendCells,
    appendReportOwnerNavigationButton,
    auditActionOwner,
    auditDiagnosticsActionsForRow,
    auditEmptyStateMessage,
    auditMatchesChip,
    auditReviewBoardLines,
    auditReviewStatus,
    auditRowKey,
    byId,
    clearRows,
    diagnosticsBridgeApi,
    filterRows: typeof filterRows === "function" ? filterRows : window.filterRows,
    hiddenSelectedCount,
    makeRowSelectable,
    renderReportDiagnosticsActions,
    renderReportTriage: (...args) => renderReportTriage(...args),
    reportAuditScoreFieldIds,
    reportAuditScoreGroupDefaultKeys,
    reportRenderedRows,
    reportTableStatusText,
    rowKeySet,
    setReportChipPressed,
    setText,
    state: reportsState,
    updateTableStatusLegend,
  });

  const reportsAuditCommandsModule = window.__reportsViewAuditCommandsModule || {};
  delete window.__reportsViewAuditCommandsModule;
  if (typeof reportsAuditCommandsModule.createReportsAuditCommandsModule !== "function") {
    throw new Error("reports/auditCommands.js must load before reportsView.js");
  }
  reportsAuditCommands = reportsAuditCommandsModule.createReportsAuditCommandsModule({
    apiPost: (...args) => {
      const post = typeof window.apiPost === "function" ? window.apiPost : typeof apiPost === "function" ? apiPost : null;
      if (typeof post !== "function") throw new Error("apiPost is unavailable");
      return post(...args);
    },
    appendCommandResult: (...args) => {
      const append = typeof window.appendCommandResult === "function"
        ? window.appendCommandResult
        : typeof appendCommandResult === "function"
          ? appendCommandResult
          : null;
      if (typeof append === "function") return append(...args);
      return undefined;
    },
    byId,
    hiddenAuditSelectionMessage,
    hiddenSelectedAuditCount,
    jsonDetailText: (...args) => {
      const formatter = typeof window.jsonDetailText === "function" ? window.jsonDetailText : typeof jsonDetailText === "function" ? jsonDetailText : null;
      if (typeof formatter === "function") return formatter(...args);
      return "";
    },
    refreshAll: (...args) => {
      const refresh = typeof window.refreshAll === "function" ? window.refreshAll : typeof refreshAll === "function" ? refreshAll : null;
      if (typeof refresh === "function") return refresh(...args);
      return undefined;
    },
    renderAuditProgressInto: (...args) => window.mediaPipelineProgressView?.renderAuditProgressInto?.(...args),
    reportAuditCommandButtonIds,
    reportAuditScoreFieldIds,
    reportNumber,
    selectedAuditRowKeysList,
    setButtonsBusy,
    setText,
    state: reportsState,
  });

  const reportsTriageModule = window.__reportsViewTriageModule || {};
  delete window.__reportsViewTriageModule;
  if (typeof reportsTriageModule.createReportsTriageModule !== "function") {
    throw new Error("reports/triage.js must load before reportsView.js");
  }
  reportsTriage = reportsTriageModule.createReportsTriageModule({
    auditReviewStatus,
    collectReportWarnings,
    failureReviewStatus,
    renderAuditReviewBoard,
    renderFailureReviewBoard,
    renderReportWarnings,
    reportAuditReviewCount,
    reportFailureReviewCount,
    reportLatestState,
    reportNumber,
    reportPreviewLoaded,
    setText,
    state: reportsState,
  });


  function reportsTabIds() {
    return ["failures", "audit", "files"];
  }

  function setButtonsBusy(ids, busy, activeId = "") {
    ids.forEach((id) => {
      const button = byId(id);
      if (!button) return;
      button.disabled = Boolean(busy);
      button.setAttribute("aria-busy", String(Boolean(busy && (!activeId || activeId === id))));
    });
  }

  function reportAuditCommandApi() {
    if (!reportsAuditCommands) throw new Error("reports/auditCommands.js must initialize before audit command use");
    return reportsAuditCommands;
  }

  function reportAuditJsonDetail(label, value, intro) {
    return reportAuditCommandApi().reportAuditJsonDetail(label, value, intro);
  }

  function renderReportAuditSources(payload, message = "") {
    return reportAuditCommandApi().renderReportAuditSources(payload, message);
  }

  function addReportAuditSourceFromForm() {
    return reportAuditCommandApi().addReportAuditSourceFromForm();
  }

  function scanReportAuditSources(sourceIds = null) {
    return reportAuditCommandApi().scanReportAuditSources(sourceIds);
  }

  function selectAllReportAuditSources() {
    return reportAuditCommandApi().selectAllReportAuditSources();
  }

  function clearReportAuditSourceSelection() {
    return reportAuditCommandApi().clearReportAuditSourceSelection();
  }

  function renderReportAuditProgressPanel(snapshot = reportsState.lastReportSnapshot) {
    return reportAuditCommandApi().renderReportAuditProgressPanel(snapshot);
  }

  function renderReportAuditRunningState(snapshot = reportsState.lastReportSnapshot) {
    return reportAuditCommandApi().renderReportAuditRunningState(snapshot);
  }

  function reportAuditReviewCount() {
    return reportAuditCommandApi().reportAuditReviewCount();
  }

  function reportFailureReviewCount() {
    return reportNumber(reportsState.lastFailurePreviewPayload?.operator_required_count)
      + reportNumber(reportsState.lastFailurePreviewPayload?.permanent_count);
  }

  function collectReportAuditStartRequest() {
    return reportAuditCommandApi().collectReportAuditStartRequest();
  }

  function renderReportAuditLaunchPreflight(request = collectReportAuditStartRequest()) {
    return reportAuditCommandApi().renderReportAuditLaunchPreflight(request);
  }

  async function startReportAuditFromForm() {
    return reportAuditCommandApi().startReportAuditFromForm();
  }

  async function stopReportAuditFromForm() {
    return reportAuditCommandApi().stopReportAuditFromForm();
  }

  async function saveReportAuditScorePolicy(reset = false) {
    return reportAuditCommandApi().saveReportAuditScorePolicy(reset);
  }

  async function ignoreSelectedAuditRows() {
    return reportAuditCommandApi().ignoreSelectedAuditRows();
  }

  async function exportAuditRerunCsv() {
    return reportAuditCommandApi().exportAuditRerunCsv();
  }

  function reportsTriageApi() {
    if (!reportsTriage) throw new Error("reports/triage.js must initialize before Reports triage use");
    return reportsTriage;
  }

  function reportTriageActionOwner() {
    return reportsTriageApi().reportTriageActionOwner();
  }

  function reportTriageBandNextAction() {
    return reportsTriageApi().reportTriageBandNextAction();
  }

  function renderReportTriageBand() {
    return reportsTriageApi().renderReportTriageBand();
  }


  function renderReports(snapshot, settings) {
    const snapshotPayload = snapshot || {};
    const settingsPayload = settings || {};
    reportsState.lastReportSnapshot = snapshotPayload;
    reportsState.lastReportSettings = settingsPayload;
    const latestPaths = snapshotPayload.latest_paths || {};
    const workspacePaths = settingsPayload.paths || {};
    const auditRootInput = byId("report-audit-start-library-root");
    if (auditRootInput && !auditRootInput.value && workspacePaths.outsource) {
      auditRootInput.value = workspacePaths.outsource;
    }
    renderReportAuditSources(reportsState.lastReportAuditSources);
    renderReportAuditLaunchPreflight();
    setText("report-failure-json-state", latestPaths.latest_failure_json ? "Present" : "Missing");
    setText("report-audit-csv-state", latestPaths.latest_audit_csv ? "Present" : "Missing");
    setText("report-priority-csv-state", latestPaths.latest_priority_csv ? "Present" : "Missing");
    renderReportAuditProgressPanel(snapshotPayload);
    const latestRows = ["latest_failure_report", "latest_failure_json", "latest_audit_csv", "latest_priority_csv"].map((key) => ({
      key,
      label: reportLabel(key),
      path: latestPaths[key] || "",
    }));
    renderKeyPathRows("report-path-rows", "report-path-status", latestRows, "No latest reports loaded.");
    const rootRows = ["failed_reports", "failed_markers", "audit_reports", "completed_manifest", "pending_push", "queue_snapshot", "active_jobs"].map((key) => ({
      key,
      label: reportLabel(key),
      path: workspacePaths[key] || "",
    }));
    renderKeyPathRows("report-root-rows", "report-root-status", rootRows, "No report roots loaded.");
    renderReportWarnings();
    renderReportTriage();
    if (typeof getCommandHistory === "function") renderReportOpenHistory(getCommandHistory());
    renderReportAuditRunningState(snapshotPayload);
  }
  function failureReviewTileNode(tile) {
    const section = document.createElement("section");
    section.className = `review-tile${tile.wide ? " review-tile-wide" : ""}`;
    section.dataset.tone = tile.tone || "muted";
    const label = document.createElement("span");
    label.className = "review-tile-label";
    label.textContent = tile.label || "";
    const value = document.createElement("strong");
    value.className = "review-tile-value";
    value.textContent = tile.value || "";
    const detail = document.createElement("span");
    detail.className = "review-tile-detail";
    detail.textContent = tile.detail || "";
    section.replaceChildren(label, value, detail);
    return section;
  }
  function reportTriageStatus() {
    return reportsTriageApi().reportTriageStatus();
  }

  function reportTriageNextStep() {
    return reportsTriageApi().reportTriageNextStep();
  }

  function reportTriageLines() {
    return reportsTriageApi().reportTriageLines();
  }

  function renderReportTriage() {
    return reportsTriageApi().renderReportTriage();
  }

  function reportInvestigationStatus() {
    return reportsTriageApi().reportInvestigationStatus();
  }

  function reportInvestigationChecklistLines() {
    return reportsTriageApi().reportInvestigationChecklistLines();
  }

  function renderReportInvestigation() {
    return reportsTriageApi().renderReportInvestigation();
  }

  function initReportsViewEvents() {
    initReportsTabNav();
    if (reportsState.reportsViewEventsInitialized) return;
    reportsState.reportsViewEventsInitialized = true;
    document.addEventListener("keydown", handleReportsFailureKeyboard);
    document.querySelectorAll("[data-failure-filter-chip]").forEach((button) => {
      button.addEventListener("click", () => {
        reportsState.activeFailureFilterChip = button.dataset.failureFilterChip || "all";
        reportsState.lastFailureClearPreview = null;
        reportsState.lastFailureLifecyclePreview = null;
        setReportChipPressed("[data-failure-filter-chip]", reportsState.activeFailureFilterChip);
        renderFailureResolutionGroups();
        renderFailureRows();
        updateFailureClearConfirmState();
        updateFailureLifecycleConfirmState();
      });
    });
    document.querySelectorAll("[data-audit-filter-chip]").forEach((button) => {
      button.addEventListener("click", () => {
        reportsState.activeAuditFilterChip = button.dataset.auditFilterChip || "all";
        setReportChipPressed("[data-audit-filter-chip]", reportsState.activeAuditFilterChip);
        renderAuditRows();
      });
    });
    document.querySelectorAll("[data-audit-selection-action]").forEach((button) => {
      button.onclick = () => runAuditSelectionAction(button.dataset.auditSelectionAction || "");
    });
    const auditScoreThresholdInput = document.querySelector("[data-audit-score-threshold-input]");
    if (auditScoreThresholdInput) auditScoreThresholdInput.addEventListener("keydown", (event) => {
      if (event.key !== "Enter") return;
      event.preventDefault();
      selectAuditRowsAtOrAboveScore();
    });
    const failureFilter = byId("failure-filter");
    if (failureFilter) failureFilter.addEventListener("input", () => {
      reportsState.lastFailureClearPreview = null;
      reportsState.lastFailureLifecyclePreview = null;
      renderFailureResolutionGroups();
      renderFailureRows();
      updateFailureClearConfirmState();
      updateFailureLifecycleConfirmState();
    });
    const clearScope = byId("failure-clear-scope");
    if (clearScope) clearScope.addEventListener("change", () => {
      reportsState.lastFailureClearPreview = null;
      updateFailureClearConfirmState();
    });
    const clearConfirmButton = byId("failure-clear-confirm-button");
    if (clearConfirmButton) clearConfirmButton.addEventListener("click", () => requestFailureMarkerClear(byId("failure-clear-scope")?.value || "selected_files", false));
    const lifecycleAckButton = byId("failure-lifecycle-ack-button");
    if (lifecycleAckButton) lifecycleAckButton.addEventListener("click", () => requestFailureLifecycleTransition("acknowledge", false));
    const lifecycleStartButton = byId("failure-lifecycle-start-button");
    if (lifecycleStartButton) lifecycleStartButton.addEventListener("click", () => requestFailureLifecycleTransition("start_work", false));
    const lifecycleResolveConfirmButton = byId("failure-lifecycle-resolve-confirm-button");
    if (lifecycleResolveConfirmButton) lifecycleResolveConfirmButton.addEventListener("click", () => requestFailureLifecycleTransition("mark_resolved", false));
    const lifecycleReopenConfirmButton = byId("failure-lifecycle-reopen-confirm-button");
    if (lifecycleReopenConfirmButton) lifecycleReopenConfirmButton.addEventListener("click", () => requestFailureLifecycleTransition("reopen", false));
    const archiveConfirmButton = byId("failure-archive-confirm-button");
    if (archiveConfirmButton) archiveConfirmButton.addEventListener("click", () => requestFailureEvidenceArchive(false));
    const artifactSelectAll = byId("failure-artifact-select-all");
    if (artifactSelectAll) artifactSelectAll.addEventListener("change", () => selectVisibleFailureArtifacts(artifactSelectAll.checked));
    const artifactCleanupConfirmButton = byId("failure-artifact-cleanup-confirm-button");
    if (artifactCleanupConfirmButton) artifactCleanupConfirmButton.addEventListener("click", () => requestFailureArtifactCleanup(false));
    ["failure-archive-include-markers", "failure-archive-include-reports"].forEach((id) => {
      const element = byId(id);
      if (!element) return;
      element.addEventListener("input", () => {
        reportsState.lastFailureArchivePreview = null;
        updateFailureArchiveConfirmState();
      });
      element.addEventListener("change", () => {
        reportsState.lastFailureArchivePreview = null;
        updateFailureArchiveConfirmState();
      });
    });
    const archiveReason = byId("failure-archive-reason");
    if (archiveReason) {
      archiveReason.addEventListener("input", () => updateFailureArchiveConfirmState());
      archiveReason.addEventListener("change", () => updateFailureArchiveConfirmState());
    }
    updateFailureArchiveConfirmState();
    const saveAuditScorePolicyButton = byId("report-audit-score-policy-save-button");
    if (saveAuditScorePolicyButton) saveAuditScorePolicyButton.addEventListener("click", () => saveReportAuditScorePolicy(false));
    const resetAuditScorePolicyButton = byId("report-audit-score-policy-reset-button");
    if (resetAuditScorePolicyButton) resetAuditScorePolicyButton.addEventListener("click", () => saveReportAuditScorePolicy(true));
    const addAuditSourceButton = byId("report-audit-add-source-button");
    if (addAuditSourceButton) addAuditSourceButton.addEventListener("click", () => addReportAuditSourceFromForm());
    const scanSelectedAuditSourcesButton = byId("report-audit-scan-selected-button");
    if (scanSelectedAuditSourcesButton) scanSelectedAuditSourcesButton.addEventListener("click", () => scanReportAuditSources());
    const scanAllAuditSourcesButton = byId("report-audit-scan-all-button");
    if (scanAllAuditSourcesButton) scanAllAuditSourcesButton.addEventListener("click", () => scanReportAuditSources([]));
    const selectAllAuditSourcesButton = byId("report-audit-select-all-sources-button");
    if (selectAllAuditSourcesButton) selectAllAuditSourcesButton.addEventListener("click", () => selectAllReportAuditSources());
    const clearAuditSourceSelectionButton = byId("report-audit-clear-source-selection-button");
    if (clearAuditSourceSelectionButton) clearAuditSourceSelectionButton.addEventListener("click", () => clearReportAuditSourceSelection());
    const startAuditButton = byId("report-audit-start-button");
    if (startAuditButton) startAuditButton.addEventListener("click", () => startReportAuditFromForm());
    const stopAuditButton = byId("report-audit-stop-button");
    if (stopAuditButton) stopAuditButton.addEventListener("click", () => stopReportAuditFromForm());
    [
      "report-audit-start-library-root",
      "report-audit-start-include-sidecars",
      "report-audit-start-show-console",
    ].forEach((id) => {
      const element = byId(id);
      if (!element) return;
      element.addEventListener("input", () => {
        renderReportAuditLaunchPreflight();
      });
      element.addEventListener("change", () => {
        renderReportAuditLaunchPreflight();
      });
    });
    const ignoreAuditRowsButton = byId("report-audit-ignore-selected-button");
    if (ignoreAuditRowsButton) ignoreAuditRowsButton.addEventListener("click", () => ignoreSelectedAuditRows());
    const exportAuditRowsButton = byId("report-audit-export-rerun-csv-button");
    if (exportAuditRowsButton) exportAuditRowsButton.addEventListener("click", () => exportAuditRerunCsv());
  }

  function reportsComponentCommandSelectors(component) {
    const selectorsByComponent = {
      failures: ["#failure-primary-action-button", "#failure-clear-confirm-button", "#failure-archive-confirm-button", "#failure-lifecycle-ack-button", "#failure-lifecycle-start-button", "#failure-lifecycle-resolve-confirm-button", "#failure-lifecycle-reopen-confirm-button"],
      artifacts: ["#failure-artifact-cleanup-confirm-button"],
      audit: ["#report-audit-ignore-selected-button", "#report-audit-export-rerun-csv-button"],
      controls: ["#report-audit-start-button", "#report-audit-stop-button"],
      sources: ["#report-audit-scan-selected-button", "#report-audit-scan-all-button", "#report-audit-start-button"],
    };
    return selectorsByComponent[component] || [];
  }

  function markReportsComponentFresh(component, payload = {}) {
    const timestamp = String(payload.generated_at || payload._refresh?.completed_at || new Date().toISOString());
    reportsState.componentFreshAt[component] = timestamp;
    reportsComponentCommandSelectors(component).forEach((selector) => {
      const button = document.querySelector(selector);
      if (!button || button.dataset.reportsUnavailableDisabled !== "true") return;
      button.disabled = false;
      delete button.dataset.reportsUnavailableDisabled;
    });
    const page = document.querySelector('[data-page-panel="reports"]');
    if (page) page.dataset.availability = "available";
    if (component === "failures") renderFailureReviewBoard();
    if (component === "audit") renderAuditReviewBoard();
  }

  function renderReportsUnavailable(component, reason = "Reports evidence is unavailable.") {
    const lastFresh = String(reportsState.componentFreshAt[component] || "");
    const historical = lastFresh
      ? ` Historical rows remain visible from ${lastFresh}; they are not current evidence.`
      : " No current evidence is available.";
    const message = `${reason}${historical}`;
    const statusIdsByComponent = {
      failures: ["failure-status", "failure-resolution-group-status", "failure-resolution-detail-status", "failure-clear-status", "failure-archive-status", "failure-review-status", "report-triage-band-status"],
      artifacts: ["failure-artifact-storage-status", "failure-artifact-cleanup-status"],
      audit: ["audit-preview-status", "audit-review-status", "report-audit-export-status"],
      controls: ["report-audit-launch-status", "report-progress-status"],
      sources: ["report-audit-source-status", "report-audit-source-selection-status"],
    };
    (statusIdsByComponent[component] || ["report-triage-band-status"]).forEach((id) => setText(id, "Unavailable — historical only"));
    if (component === "failures") {
      reportsState.selectedFailureRowKey = "";
      reportsState.selectedFailureRowKeys.clear();
      reportsState.selectedFailureGroupKey = "";
      setText("failure-summary", message);
    } else if (component === "audit") {
      reportsState.selectedAuditRowKey = "";
      reportsState.selectedAuditRowKeys.clear();
      setText("audit-summary", message);
    }
    reportsComponentCommandSelectors(component).forEach((selector) => {
      const button = document.querySelector(selector);
      if (!button) return;
      if (!button.disabled) button.dataset.reportsUnavailableDisabled = "true";
      button.disabled = true;
    });
    const page = document.querySelector('[data-page-panel="reports"]');
    if (page) {
      page.dataset.availability = "unavailable";
      page.dataset.unavailableComponent = component;
    }
  }

  /**
   * Public namespace for the Reports page module.
   * Prefer this namespace from new code; flat window.* exports are transitional compatibility aliases when present.
   */
  window.mediaPipelineReportsView = {
    renderReports,
    markReportsComponentFresh,
    renderReportsUnavailable,
    renderReportTriage,
    renderReportInvestigation,
    activateQuickLink,
    reportInvestigationStatus,
    reportInvestigationChecklistLines,
    initReportsViewEvents,
    reportTriageStatus,
    reportTriageLines,
    renderFailurePreview,
    renderFailureResolutionGroups,
    renderFailureRows,
    renderFailureDetail,
    renderFailureArtifactSummary,
    renderFailureReviewBoard,
    failureRetryStatePayload,
    failureRetryRows,
    failureRetryStateForRow,
    failureRetryPreviewSummaryLine,
    requestFailureMarkerClear,
    renderFailureClearResult,
    requestFailureArtifactCleanup,
    renderFailureArtifactCleanupResult,
    requestFailureEvidenceArchive,
    renderFailureArchiveResult,
    failureReviewStatus,
    failureReviewBoardLines,
    failureReviewBoardTiles,
    failureDiagnosticsActionsForRow,
    failureEmptyStateMessage,
    selectFailureRow,
    getSelectedFailureRow,
    failureRowKey,
    renderAuditPreview,
    renderAuditControls,
    renderReportAuditSources,
    renderAuditRows,
    selectVisibleAuditRows,
    selectAuditRowsAtOrAboveScore,
    clearAuditSelection,
    renderAuditDetail,
    renderAuditReviewBoard,
    collectReportAuditStartRequest,
    renderReportAuditLaunchPreflight,
    startReportAuditFromForm,
    stopReportAuditFromForm,
    saveReportAuditScorePolicy,
    ignoreSelectedAuditRows,
    exportAuditRerunCsv,
    selectedAuditRowKeysList,
    auditReviewStatus,
    auditReviewBoardLines,
    auditDiagnosticsActionsForRow,
    auditEmptyStateMessage,
    selectAuditRow,
    toggleAuditRowSelection,
    getSelectedAuditRow,
    auditRowKey,
    renderKeyPathRows,
    reportLabel,
    reportOpenTarget,
    reportOpenTargetValues,
    isReportOpenCommand,
    reportOpenHistoryLine,
    renderReportOpenHistory,
    renderReportDiagnosticsActions,
    activateReportsTab,
    initReportsTabNav,
  };
})();
