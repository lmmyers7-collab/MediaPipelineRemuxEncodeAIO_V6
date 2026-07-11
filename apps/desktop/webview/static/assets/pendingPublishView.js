(function () {
  const pendingTableSupportModule = window.__pendingPublishTableSupportModule || {};
  delete window.__pendingPublishTableSupportModule;
  const { PENDING_FILTER_FIELDS, clampTableScrollOffset, tableScrollSnapshot, restoreTableScrollSnapshot, deferTableScrollRestore } =
    pendingTableSupportModule.createPendingPublishTableSupportModule();

  const pendingDefaultAdaptersModule = window.__pendingPublishDefaultAdaptersModule || {};
  delete window.__pendingPublishDefaultAdaptersModule;
  let {
    pendingDiagnosticsFallbackLines, pendingDiagnosticsFallbackRender, pendingSelectedOpenTargetLines, pendingDiagnosticsActionsForRow,
    pendingDiagnosticsGuidanceLines, renderPendingDiagnosticsLinks, requestPendingDiagnosticsAction, isPendingOpenCommand,
    pendingOpenHistoryLine, renderPendingOpenHistory, requestPendingPublishOpen, pendingRecoveryFallbackRows,
    pendingRecoveryFallbackLines, pendingRecoveryFallbackRender, rejectPendingRecoveryPlanWhileBusy, requestPendingRecoveryPlan,
    renderPendingRecoveryPlanResult, pendingRecoveryPlanResultLines, pendingRecoveryPlanRowKey, pendingRecoveryPlanRowStatus,
    pendingRecoveryPlanEvidenceText, pendingRecoveryPlanActionText, pendingRecoveryPlanRowDetailLines, renderPendingRecoveryPlanRows,
    selectPendingRecoveryPlanRow, renderPendingRecoveryPlanRowDetail, renderPendingRecoveryPlanHistory, isPendingRecoveryPlanCommand,
    pendingRecoveryPlanHistoryLine, pendingRecoveryPlanResultData, pendingRecoveryPlanRowLabel, initPendingRepairManifestEvents,
    isPendingRepairManifestCommand, pendingRepairDryRunIsSafeForSelection, pendingRepairManifestApplyRequest, pendingRepairManifestDryRunRequest,
    pendingRepairManifestHistoryLine, pendingRepairManifestResultLines, renderPendingRepairManifestControls, renderPendingRepairManifestHistory,
    requestPendingRepairManifestApply, requestPendingRepairManifestDryRun, setPendingRepairManifestBusy, isPendingRepairOrphanCommand,
    pendingOrphanDryRunIsSafeForSelection, pendingRepairOrphanApplyRequest, pendingRepairOrphanDryRunRequest, renderPendingRepairOrphanControls,
    renderPendingRepairOrphanHistory, requestPendingRepairOrphanApply, requestPendingRepairOrphanDryRun, setPendingRepairOrphanBusy,
    pendingDrainFallbackRows, pendingDrainFallbackLines, pendingDrainFallbackScope, pendingDrainFallbackRender,
    pendingCurrentFilterScope, pendingCurrentFilterScopeEvidence, pendingCurrentFilterScopeAction, pendingBackendDrainScopeRows,
    pendingBackendDrainScopeStatus, pendingBackendDrainScopeSummaryLines, renderPendingBackendDrainScopePreview, pendingEvidenceClass,
    pendingEvidenceRows, pendingEvidenceStatus, pendingEvidenceText, pendingEvidenceAction,
    pendingDrainEvidenceLines, renderPendingDrainEvidence, pendingDrainSearchText, isPendingDrainCommand,
    pendingDrainHistoryLine, renderPendingDrainHistory, pendingDrainEventsFromSnapshot, pendingDrainEventStatus,
    pendingDrainEventRoute, pendingDrainEventLeaf, pendingDrainEventCounts, pendingDrainEventsStatus,
    pendingDrainEventsLines, renderPendingDrainEvents, pendingDrainSummaryPayload, pendingDrainSummaryItems,
    pendingDrainSummaryStatus, pendingDrainSummaryLeaf, pendingDrainSummaryLines, renderPendingDrainSummary,
    pendingDrainLatestCommand, pendingDrainCommandData, pendingDrainCommandRequest, pendingDrainCommandResultText,
    pendingDrainCommandIssueLevel, pendingDrainSummaryIssueLevel, pendingDrainCorrelationStatus, pendingDrainCorrelationLines,
    renderPendingDrainCorrelation, pendingConfidenceFallbackRows, pendingConfidenceFallbackLines, pendingConfidenceFallbackRender,
    pendingDrainConfidenceRows, pendingDrainConfidenceStatus, pendingDrainConfidenceSummaryLines, renderPendingDrainActionConfidence,
    pendingDrainDecisionRows, pendingDrainDecisionStatus, pendingDrainDecisionStatusState, pendingDrainDecisionSummaryLines,
    pendingDrainDecisionDetailLines, pendingDrainDecisionPostureStatus, renderPendingDrainDecisionChecklist, pendingPostDrainTrustRows,
    pendingPostDrainTrustStatus, pendingPostDrainTrustSummaryLines, pendingPostDrainTrustDetailLines, pendingPostDrainTrustPostureStatus,
    renderPendingPostDrainTrust, pendingDrainGuardState, pendingDrainGuardLines, renderPendingDrainGuard,
  } = pendingDefaultAdaptersModule.createPendingPublishDefaultAdapters();

  const formatters = window.mediaPipelineFormatters || {};
  const shortenPath = typeof formatters.shortenPath === "function" ? formatters.shortenPath : null;
  const PENDING_READ_ONLY_BOUNDARY = "Mutation guardrail: read-only evidence; backend routes own pending-publish changes.";
  let lastPendingRows = [];
  let lastPendingPayload = {};
  let lastPendingSnapshot = {};
  let selectedPendingRowKey = "";
  let lastPendingRecoveryPlanRows = [];
  let lastPendingRecoveryPlanSignature = "";
  let selectedPendingRecoveryPlanKey = "";
  let selectedPendingDrainDecisionKey = "";
  let selectedPendingPostDrainTrustKey = "";
  let lastPendingEmptyMessage = "No pending publish rows available.";
  let pendingOpenInFlight = false;
  let pendingRecoveryPlanInFlight = false;
  let pendingActionCenterEventsInitialized = false;
  function diagnosticsBridgeApi() {
    return window.mediaPipelineDiagnosticsBridge || {};
  }

  let setPendingOpenBusy = function (isBusy) {
    pendingOpenInFlight = Boolean(isBusy);
    document.querySelectorAll("[data-open-pending]").forEach((button) => {
      button.disabled = pendingOpenInFlight;
    });
  };

  let rejectPendingOpenWhileBusy = function () {
    if (!pendingOpenInFlight) return false;
    const result = {
      command: "pending_publish.open",
      ok: false,
      severity: "warning",
      message: "Another pending publish open command is already in progress.",
    };
    appendCommandResult(result);
    setText("pending-open-status", result.message);
    return true;
  };

  let setPendingRecoveryPlanBusy = function (isBusy) {
    pendingRecoveryPlanInFlight = Boolean(isBusy);
    ["pending-recovery-plan-selected-button", "pending-recovery-plan-all-button"].forEach((id) => {
      const button = byId(id);
      if (button) button.disabled = pendingRecoveryPlanInFlight;
    });
  };
  let pendingInventoryProgressBars = function () { return []; };
  let renderPendingInventoryProgress = function () {};
  let pendingEmptyStateMessage = function () { return "No pending publish rows available."; };
  let pendingRowHasHealthIssue = function () { return false; };
  let pendingPublishReadinessStatus = function () { return "Not evaluated"; };
  let pendingPublishReadinessLines = function () { return []; };
  let renderPendingPublishReadiness = function () {};
  let pendingWorkflowStatus = function () { return "Not evaluated"; };
  let pendingWorkflowLines = function () { return []; };
  let renderPendingWorkflow = function () {};
  let pendingReviewRowReasons = function () { return []; };
  let pendingReviewRows = function () { return []; };
  let pendingReviewStatus = function () { return "Not evaluated"; };
  let pendingReviewBoardLines = function () { return []; };
  let pendingReviewDigestStatus = function () { return "warning"; };
  let pendingReviewDigestAction = function () { return "Select this row and inspect Pending detail before drain."; };
  let renderPendingReviewDigest = function () {};
  let renderPendingReviewBoard = function () {};
  let pendingFormatCounts = function () { return "none"; };
  let pendingRecoverySummaryPayload = function () { return {}; };
  let pendingRecoverySummaryLines = function () { return []; };
  let pendingRiskStatus = function () { return "Not evaluated"; };
  let pendingRiskLines = function () { return []; };
  let renderPendingRiskBreakdown = function () {};
  let pendingValidationStatus = function () { return "Not evaluated"; };
  let pendingValidationChecklistLines = function () { return []; };
  let renderPendingValidation = function () {};

  const pendingSummaryModule = window.__pendingPublishSummaryModule || {};
  const pendingSummary = typeof pendingSummaryModule.createPendingPublishSummaryModule === "function"
    ? pendingSummaryModule.createPendingPublishSummaryModule({
      appendCells: typeof appendCells === "function" ? appendCells : window.appendCells,
      byId: typeof byId === "function" ? byId : window.byId,
      clearRows: typeof clearRows === "function" ? clearRows : window.clearRows,
      getSelectedPendingRowKey: () => selectedPendingRowKey,
      makeRowSelectable: typeof makeRowSelectable === "function" ? makeRowSelectable : window.makeRowSelectable,
      pendingDrainSummaryStatus: (...args) => pendingDrainSummaryStatus(...args),
      pendingRowKey: (...args) => pendingRowKey(...args),
      renderProgressBarsInto: (...args) => window.mediaPipelineProgressView?.renderProgressBarsInto?.(...args),
      selectPendingRow: (...args) => selectPendingRow(...args),
      setText: typeof setText === "function" ? setText : window.setText,
      shortenPath,
      updateTableStatusLegend: typeof updateTableStatusLegend === "function" ? updateTableStatusLegend : window.updateTableStatusLegend,
    })
    : {};
  pendingInventoryProgressBars = typeof pendingSummary.pendingInventoryProgressBars === "function" ? pendingSummary.pendingInventoryProgressBars : pendingInventoryProgressBars;
  renderPendingInventoryProgress = typeof pendingSummary.renderPendingInventoryProgress === "function" ? pendingSummary.renderPendingInventoryProgress : renderPendingInventoryProgress;
  pendingEmptyStateMessage = typeof pendingSummary.pendingEmptyStateMessage === "function" ? pendingSummary.pendingEmptyStateMessage : pendingEmptyStateMessage;
  pendingRowHasHealthIssue = typeof pendingSummary.pendingRowHasHealthIssue === "function" ? pendingSummary.pendingRowHasHealthIssue : pendingRowHasHealthIssue;
  pendingPublishReadinessStatus = typeof pendingSummary.pendingPublishReadinessStatus === "function" ? pendingSummary.pendingPublishReadinessStatus : pendingPublishReadinessStatus;
  pendingPublishReadinessLines = typeof pendingSummary.pendingPublishReadinessLines === "function" ? pendingSummary.pendingPublishReadinessLines : pendingPublishReadinessLines;
  renderPendingPublishReadiness = typeof pendingSummary.renderPendingPublishReadiness === "function" ? pendingSummary.renderPendingPublishReadiness : renderPendingPublishReadiness;
  pendingWorkflowStatus = typeof pendingSummary.pendingWorkflowStatus === "function" ? pendingSummary.pendingWorkflowStatus : pendingWorkflowStatus;
  pendingWorkflowLines = typeof pendingSummary.pendingWorkflowLines === "function" ? pendingSummary.pendingWorkflowLines : pendingWorkflowLines;
  renderPendingWorkflow = typeof pendingSummary.renderPendingWorkflow === "function" ? pendingSummary.renderPendingWorkflow : renderPendingWorkflow;
  pendingReviewRowReasons = typeof pendingSummary.pendingReviewRowReasons === "function" ? pendingSummary.pendingReviewRowReasons : pendingReviewRowReasons;
  pendingReviewRows = typeof pendingSummary.pendingReviewRows === "function" ? pendingSummary.pendingReviewRows : pendingReviewRows;
  pendingReviewStatus = typeof pendingSummary.pendingReviewStatus === "function" ? pendingSummary.pendingReviewStatus : pendingReviewStatus;
  pendingReviewBoardLines = typeof pendingSummary.pendingReviewBoardLines === "function" ? pendingSummary.pendingReviewBoardLines : pendingReviewBoardLines;
  pendingReviewDigestStatus = typeof pendingSummary.pendingReviewDigestStatus === "function" ? pendingSummary.pendingReviewDigestStatus : pendingReviewDigestStatus;
  pendingReviewDigestAction = typeof pendingSummary.pendingReviewDigestAction === "function" ? pendingSummary.pendingReviewDigestAction : pendingReviewDigestAction;
  renderPendingReviewDigest = typeof pendingSummary.renderPendingReviewDigest === "function" ? pendingSummary.renderPendingReviewDigest : renderPendingReviewDigest;
  renderPendingReviewBoard = typeof pendingSummary.renderPendingReviewBoard === "function" ? pendingSummary.renderPendingReviewBoard : renderPendingReviewBoard;
  pendingFormatCounts = typeof pendingSummary.pendingFormatCounts === "function" ? pendingSummary.pendingFormatCounts : pendingFormatCounts;
  pendingRecoverySummaryPayload = typeof pendingSummary.pendingRecoverySummaryPayload === "function" ? pendingSummary.pendingRecoverySummaryPayload : pendingRecoverySummaryPayload;
  pendingRecoverySummaryLines = typeof pendingSummary.pendingRecoverySummaryLines === "function" ? pendingSummary.pendingRecoverySummaryLines : pendingRecoverySummaryLines;
  pendingRiskStatus = typeof pendingSummary.pendingRiskStatus === "function" ? pendingSummary.pendingRiskStatus : pendingRiskStatus;
  pendingRiskLines = typeof pendingSummary.pendingRiskLines === "function" ? pendingSummary.pendingRiskLines : pendingRiskLines;
  renderPendingRiskBreakdown = typeof pendingSummary.renderPendingRiskBreakdown === "function" ? pendingSummary.renderPendingRiskBreakdown : renderPendingRiskBreakdown;
  pendingValidationStatus = typeof pendingSummary.pendingValidationStatus === "function" ? pendingSummary.pendingValidationStatus : pendingValidationStatus;
  pendingValidationChecklistLines = typeof pendingSummary.pendingValidationChecklistLines === "function" ? pendingSummary.pendingValidationChecklistLines : pendingValidationChecklistLines;
  renderPendingValidation = typeof pendingSummary.renderPendingValidation === "function" ? pendingSummary.renderPendingValidation : renderPendingValidation;

  let pendingTableRowStatus = function () { return "match"; };
  let pendingInvestigationFilterLabel = function (value) { return String(value || "all").replace(/_/g, " "); };
  let pendingMatchesInvestigationFilter = function () { return true; };
  let pendingFocusedInvestigationLabels = function () { return []; };
  let pendingFilterVisibilityLines = function () { return []; };
  let pendingSelectedQuickSignalLines = function () { return []; };
  let pendingInvestigationSignalLines = function () { return []; };

  const pendingFiltersModule = window.__pendingPublishFiltersModule || {};
  const pendingFilters = typeof pendingFiltersModule.createPendingPublishFiltersModule === "function"
    ? pendingFiltersModule.createPendingPublishFiltersModule({
      backendRowStatusState: window.backendRowStatusState,
      byId: typeof byId === "function" ? byId : window.byId,
      filterRows: typeof filterRows === "function" ? filterRows : window.filterRows,
      pendingFilterFields: PENDING_FILTER_FIELDS,
      pendingReviewRowReasons: (...args) => pendingReviewRowReasons(...args),
      tableStatusFilterLabel: window.tableStatusFilterLabel,
      tableStatusMatchesFilter: window.tableStatusMatchesFilter,
    })
    : {};
  pendingTableRowStatus = typeof pendingFilters.pendingTableRowStatus === "function" ? pendingFilters.pendingTableRowStatus : pendingTableRowStatus;
  pendingInvestigationFilterLabel = typeof pendingFilters.pendingInvestigationFilterLabel === "function" ? pendingFilters.pendingInvestigationFilterLabel : pendingInvestigationFilterLabel;
  pendingMatchesInvestigationFilter = typeof pendingFilters.pendingMatchesInvestigationFilter === "function" ? pendingFilters.pendingMatchesInvestigationFilter : pendingMatchesInvestigationFilter;
  pendingFocusedInvestigationLabels = typeof pendingFilters.pendingFocusedInvestigationLabels === "function" ? pendingFilters.pendingFocusedInvestigationLabels : pendingFocusedInvestigationLabels;
  pendingFilterVisibilityLines = typeof pendingFilters.pendingFilterVisibilityLines === "function" ? pendingFilters.pendingFilterVisibilityLines : pendingFilterVisibilityLines;
  pendingSelectedQuickSignalLines = typeof pendingFilters.pendingSelectedQuickSignalLines === "function" ? pendingFilters.pendingSelectedQuickSignalLines : pendingSelectedQuickSignalLines;
  pendingInvestigationSignalLines = typeof pendingFilters.pendingInvestigationSignalLines === "function" ? pendingFilters.pendingInvestigationSignalLines : pendingInvestigationSignalLines;

  let pendingRowReviewChecklistLines = function () { return []; };
  let pendingSelectedAtAGlanceState = function () { return "unknown"; };
  let pendingSelectedAtAGlanceStatus = function () { return "No row selected"; };
  let pendingSelectedAtAGlanceLines = function () { return []; };
  let renderPendingSelectedAtAGlance = function () {};
  let pendingRowIssueDigestLines = function () { return []; };
  let pendingRealMediaTraceLines = function () { return []; };
  let pendingSelectedCompletedCorrelationRows = function () { return []; };
  let pendingSelectedCompletedCorrelationLines = function () { return []; };
  let pendingSampleValidationHandoffLines = function () { return []; };
  let pendingSampleValidationComparisonLines = function () { return []; };
  let pendingRowTrustSummaryLines = function () { return []; };
  let renderPendingDetail = function () {};

  const pendingDetailsModule = window.__pendingPublishDetailsModule || {};
  const pendingDetails = typeof pendingDetailsModule.createPendingPublishDetailsModule === "function"
    ? pendingDetailsModule.createPendingPublishDetailsModule({
      byId: typeof byId === "function" ? byId : window.byId,
      backendRowStatusState: window.backendRowStatusState,
      diagnosticsBridgeHandoffLines: diagnosticsBridgeApi().diagnosticsBridgeHandoffLines,
      diagnosticsBridgeRowTrustLines: diagnosticsBridgeApi().diagnosticsBridgeRowTrustLines,
      pendingDiagnosticsActionsForRow: (...args) => pendingDiagnosticsActionsForRow(...args),
      pendingFilterVisibilityLines: (...args) => pendingFilterVisibilityLines(...args),
      pendingInvestigationSignalLines: (...args) => pendingInvestigationSignalLines(...args),
      pendingListText: (...args) => pendingListText(...args),
      pendingRowKey: (...args) => pendingRowKey(...args),
      pendingSelectedOpenTargetLines: (...args) => pendingSelectedOpenTargetLines(...args),
      pendingSelectedQuickSignalLines: (...args) => pendingSelectedQuickSignalLines(...args),
      renderPendingDiagnosticsLinks: (...args) => renderPendingDiagnosticsLinks(...args),
      setText: typeof setText === "function" ? setText : window.setText,
    })
    : {};
  pendingRowReviewChecklistLines = typeof pendingDetails.pendingRowReviewChecklistLines === "function" ? pendingDetails.pendingRowReviewChecklistLines : pendingRowReviewChecklistLines;
  pendingSelectedAtAGlanceState = typeof pendingDetails.pendingSelectedAtAGlanceState === "function" ? pendingDetails.pendingSelectedAtAGlanceState : pendingSelectedAtAGlanceState;
  pendingSelectedAtAGlanceStatus = typeof pendingDetails.pendingSelectedAtAGlanceStatus === "function" ? pendingDetails.pendingSelectedAtAGlanceStatus : pendingSelectedAtAGlanceStatus;
  pendingSelectedAtAGlanceLines = typeof pendingDetails.pendingSelectedAtAGlanceLines === "function" ? pendingDetails.pendingSelectedAtAGlanceLines : pendingSelectedAtAGlanceLines;
  renderPendingSelectedAtAGlance = typeof pendingDetails.renderPendingSelectedAtAGlance === "function" ? pendingDetails.renderPendingSelectedAtAGlance : renderPendingSelectedAtAGlance;
  pendingRowIssueDigestLines = typeof pendingDetails.pendingRowIssueDigestLines === "function" ? pendingDetails.pendingRowIssueDigestLines : pendingRowIssueDigestLines;
  pendingRealMediaTraceLines = typeof pendingDetails.pendingRealMediaTraceLines === "function" ? pendingDetails.pendingRealMediaTraceLines : pendingRealMediaTraceLines;
  pendingSelectedCompletedCorrelationRows = typeof pendingDetails.pendingSelectedCompletedCorrelationRows === "function" ? pendingDetails.pendingSelectedCompletedCorrelationRows : pendingSelectedCompletedCorrelationRows;
  pendingSelectedCompletedCorrelationLines = typeof pendingDetails.pendingSelectedCompletedCorrelationLines === "function" ? pendingDetails.pendingSelectedCompletedCorrelationLines : pendingSelectedCompletedCorrelationLines;
  pendingSampleValidationHandoffLines = typeof pendingDetails.pendingSampleValidationHandoffLines === "function" ? pendingDetails.pendingSampleValidationHandoffLines : pendingSampleValidationHandoffLines;
  pendingSampleValidationComparisonLines = typeof pendingDetails.pendingSampleValidationComparisonLines === "function" ? pendingDetails.pendingSampleValidationComparisonLines : pendingSampleValidationComparisonLines;
  pendingRowTrustSummaryLines = typeof pendingDetails.pendingRowTrustSummaryLines === "function" ? pendingDetails.pendingRowTrustSummaryLines : pendingRowTrustSummaryLines;
  renderPendingDetail = typeof pendingDetails.renderPendingDetail === "function" ? pendingDetails.renderPendingDetail : renderPendingDetail;

  const pendingActionCenterModule = window.__pendingPublishActionCenterModule || {};
  delete window.__pendingPublishActionCenterModule;
  const pendingActionCenter = typeof pendingActionCenterModule.createPendingPublishActionCenterModule === "function"
    ? pendingActionCenterModule.createPendingPublishActionCenterModule({
      byId,
      clearRows: typeof clearRows === "function" ? clearRows : window.clearRows,
      appendCells: typeof appendCells === "function" ? appendCells : window.appendCells,
      setCellStatusChip: typeof setCellStatusChip === "function" ? setCellStatusChip : window.setCellStatusChip,
      makeRowSelectable: typeof makeRowSelectable === "function" ? makeRowSelectable : window.makeRowSelectable,
      updateTableStatusLegend: typeof updateTableStatusLegend === "function" ? updateTableStatusLegend : window.updateTableStatusLegend,
      filterRows: typeof filterRows === "function" ? filterRows : window.filterRows,
      filterRowsByStatus: typeof filterRowsByStatus === "function" ? filterRowsByStatus : window.filterRowsByStatus,
      filterRowsByInvestigation: typeof filterRowsByInvestigation === "function" ? filterRowsByInvestigation : window.filterRowsByInvestigation,
      filterResultSummaryLines: typeof filterResultSummaryLines === "function" ? filterResultSummaryLines : window.filterResultSummaryLines,
      tableScrollSnapshot,
      deferTableScrollRestore,
      pendingFilterFields: PENDING_FILTER_FIELDS,
      readOnlyBoundary: PENDING_READ_ONLY_BOUNDARY,
      getLastPendingEmptyMessage: () => lastPendingEmptyMessage,
      setText,
      shortenPath: typeof shortenPath === "function" ? shortenPath : (value) => String(value || ""),
      getLastPendingPayload: () => lastPendingPayload,
      getLastPendingRows: () => lastPendingRows,
      getLastPendingSnapshot: () => lastPendingSnapshot,
      getSelectedPendingRowKey: () => selectedPendingRowKey,
      setSelectedPendingRowKey: (value) => { selectedPendingRowKey = value || ""; },
      pendingTableRowStatus: (...args) => pendingTableRowStatus(...args),
      pendingEvidenceClass: (...args) => pendingEvidenceClass(...args),
      pendingDrainSummaryPayload: (...args) => pendingDrainSummaryPayload(...args),
      pendingDrainSummaryItems: (...args) => pendingDrainSummaryItems(...args),
      pendingDrainDecisionStatus: (...args) => pendingDrainDecisionStatus(...args),
      pendingValidationStatus: (...args) => pendingValidationStatus(...args),
      pendingCurrentFilterScope: (...args) => pendingCurrentFilterScope(...args),
      pendingDrainGuardState: (...args) => pendingDrainGuardState(...args),
      pendingInvestigationFilterLabel: (...args) => pendingInvestigationFilterLabel(...args),
      pendingMatchesInvestigationFilter: (...args) => pendingMatchesInvestigationFilter(...args),
      renderPendingDetail: (...args) => renderPendingDetail(...args),
      renderPendingReviewDigest: (...args) => renderPendingReviewDigest(...args),
      renderPendingDrainEvidence: (...args) => renderPendingDrainEvidence(...args),
      renderPendingBackendDrainScopePreview: (...args) => renderPendingBackendDrainScopePreview(...args),
      renderPendingDrainDecisionChecklist: (...args) => renderPendingDrainDecisionChecklist(...args),
      renderPendingDrainActionConfidence: (...args) => renderPendingDrainActionConfidence(...args),
      renderPendingDrainGuard: (...args) => renderPendingDrainGuard(...args),
      renderPendingRepairManifestControls: (...args) => renderPendingRepairManifestControls(...args),
      renderPendingRepairOrphanControls: (...args) => renderPendingRepairOrphanControls(...args),
      getCommandHistory: () => typeof getCommandHistory === "function" ? getCommandHistory() : [],
    })
    : {};
  const {
    pendingListText = (value) => Array.isArray(value) && value.length ? value.join(", ") : "none",
    pendingRowKey = (item) => String(item?.row_key || item?.manifest_path || "").toLowerCase(),
    getSelectedPendingRow = () => null,
    capturePendingSelectionScroll = () => null,
    restorePendingSelectionScroll = () => {},
    selectPendingRow = () => {},
    pendingDrainOverviewState = () => "unknown",
    pendingRowPresentationStatus = () => "unknown",
    pendingRowPresentationLabel = () => "Unknown",
    pendingRowReasonText = () => "",
    pendingRowUpdatedText = () => "",
    pendingPathDisplay = (value) => String(value || ""),
    pendingDrainSummaryCounts = () => ({ drained: 0, failed: 0, skipped: 0 }),
    pendingActionCenterTriage = () => ({ ready: 0, review: 0, evidence: 0, blocked: 0, failed: 0, drained: 0, skipped: 0, draining: 0 }),
    pendingActionCenterOutcome = () => ({ action: "Review Pending Publish", reason: "Evidence not loaded.", detail: "Refresh Pending Publish.", state: "unknown" }),
    setPendingActionCount = () => {},
    renderPendingActionCenter = () => {},
    renderPendingDrainOverview = () => {},
    applyPendingActionFilter = () => {},
    triggerPendingActionDrain = () => {},
    focusPendingQuickLinkTarget = () => false,
    setPendingTextFilter = () => {},
    activateQuickLink = () => false,
    triggerPendingActionRefresh = () => {},
    initPendingActionCenterEvents = () => {},
    renderPendingRows = () => {},
    resetPendingFilters = () => {},
  } = pendingActionCenter;
  const pendingDiagnosticsState = {
    get pendingOpenInFlight() {
      return pendingOpenInFlight;
    },
    set pendingOpenInFlight(value) {
      pendingOpenInFlight = Boolean(value);
    },
  };

  const pendingDiagnosticsModule = window.__pendingPublishDiagnosticsModule || {};
  delete window.__pendingPublishDiagnosticsModule;
  const pendingDiagnostics = typeof pendingDiagnosticsModule.createPendingPublishDiagnosticsModule === "function"
    ? pendingDiagnosticsModule.createPendingPublishDiagnosticsModule({
      apiPost: typeof apiPost === "function" ? apiPost : window.apiPost,
      appendCommandResult: typeof appendCommandResult === "function" ? appendCommandResult : window.appendCommandResult,
      appendDiagnosticsBridgeGroupedButtons: diagnosticsBridgeApi().appendDiagnosticsBridgeGroupedButtons,
      byId: typeof byId === "function" ? byId : window.byId,
      commandHistoryCompactEvidenceLine: typeof window.commandHistoryCompactEvidenceLine === "function" ? window.commandHistoryCompactEvidenceLine : (typeof commandHistoryCompactEvidenceLine === "function" ? commandHistoryCompactEvidenceLine : null),
      getSelectedPendingRow: (...args) => getSelectedPendingRow(...args),
      pendingListText: (...args) => pendingListText(...args),
      pendingRowKey: (...args) => pendingRowKey(...args),
      requestDiagnosticsOpen: typeof requestDiagnosticsOpen === "function" ? requestDiagnosticsOpen : window.requestDiagnosticsOpen,
      requestDiagnosticsTail: typeof requestDiagnosticsTail === "function" ? requestDiagnosticsTail : window.requestDiagnosticsTail,
      setText: typeof setText === "function" ? setText : window.setText,
      state: pendingDiagnosticsState,
    })
    : {};
  setPendingOpenBusy = typeof pendingDiagnostics.setPendingOpenBusy === "function" ? pendingDiagnostics.setPendingOpenBusy : setPendingOpenBusy;
  rejectPendingOpenWhileBusy = typeof pendingDiagnostics.rejectPendingOpenWhileBusy === "function" ? pendingDiagnostics.rejectPendingOpenWhileBusy : rejectPendingOpenWhileBusy;
  pendingSelectedOpenTargetLines = typeof pendingDiagnostics.pendingSelectedOpenTargetLines === "function" ? pendingDiagnostics.pendingSelectedOpenTargetLines : pendingSelectedOpenTargetLines;
  pendingDiagnosticsActionsForRow = typeof pendingDiagnostics.pendingDiagnosticsActionsForRow === "function" ? pendingDiagnostics.pendingDiagnosticsActionsForRow : pendingDiagnosticsActionsForRow;
  pendingDiagnosticsGuidanceLines = typeof pendingDiagnostics.pendingDiagnosticsGuidanceLines === "function" ? pendingDiagnostics.pendingDiagnosticsGuidanceLines : pendingDiagnosticsGuidanceLines;
  renderPendingDiagnosticsLinks = typeof pendingDiagnostics.renderPendingDiagnosticsLinks === "function" ? pendingDiagnostics.renderPendingDiagnosticsLinks : renderPendingDiagnosticsLinks;
  requestPendingDiagnosticsAction = typeof pendingDiagnostics.requestPendingDiagnosticsAction === "function" ? pendingDiagnostics.requestPendingDiagnosticsAction : requestPendingDiagnosticsAction;
  isPendingOpenCommand = typeof pendingDiagnostics.isPendingOpenCommand === "function" ? pendingDiagnostics.isPendingOpenCommand : isPendingOpenCommand;
  pendingOpenHistoryLine = typeof pendingDiagnostics.pendingOpenHistoryLine === "function" ? pendingDiagnostics.pendingOpenHistoryLine : pendingOpenHistoryLine;
  renderPendingOpenHistory = typeof pendingDiagnostics.renderPendingOpenHistory === "function" ? pendingDiagnostics.renderPendingOpenHistory : renderPendingOpenHistory;
  requestPendingPublishOpen = typeof pendingDiagnostics.requestPendingPublishOpen === "function" ? pendingDiagnostics.requestPendingPublishOpen : requestPendingPublishOpen;

  const pendingDrainModule = window.__pendingPublishDrainModule || {};
  delete window.__pendingPublishDrainModule;
  const pendingDrain = typeof pendingDrainModule.createPendingPublishDrainModule === "function"
    ? pendingDrainModule.createPendingPublishDrainModule({
      appendCells: typeof appendCells === "function" ? appendCells : window.appendCells,
      byId: typeof byId === "function" ? byId : window.byId,
      clearRows: typeof clearRows === "function" ? clearRows : window.clearRows,
      commandHistoryCompactEvidenceLine: typeof window.commandHistoryCompactEvidenceLine === "function" ? window.commandHistoryCompactEvidenceLine : (typeof commandHistoryCompactEvidenceLine === "function" ? commandHistoryCompactEvidenceLine : null),
      renderCompactCommandHistoryBlock: window.mediaPipelineCommandHistory?.renderCompactCommandHistoryBlock || null,
      filterRows: typeof filterRows === "function" ? filterRows : window.filterRows,
      filterRowsByInvestigation: typeof filterRowsByInvestigation === "function" ? filterRowsByInvestigation : window.filterRowsByInvestigation,
      filterRowsByStatus: typeof filterRowsByStatus === "function" ? filterRowsByStatus : window.filterRowsByStatus,
      getLastPendingPayload: () => lastPendingPayload || {},
      getLastPendingRecoveryPlanRows: () => Array.isArray(lastPendingRecoveryPlanRows) ? lastPendingRecoveryPlanRows : [],
      getLastPendingRecoveryPlanSignature: () => lastPendingRecoveryPlanSignature || "",
      getCurrentPendingRecoveryPlanSignature: (pending, rows) => pendingRecoveryPlanSignature(pending || lastPendingPayload, Array.isArray(rows) ? rows : lastPendingRows),
      getLastPendingRows: () => Array.isArray(lastPendingRows) ? lastPendingRows : [],
      getLastPendingSnapshot: () => lastPendingSnapshot || {},
      getSelectedPendingRow: (...args) => getSelectedPendingRow(...args),
      getSelectedPendingRowKey: () => selectedPendingRowKey || "",
      makeRowSelectable: typeof makeRowSelectable === "function" ? makeRowSelectable : window.makeRowSelectable,
      pendingDrainDecisionStatusState: (...args) => pendingDrainDecisionStatusState(...args),
      pendingFilterFields: PENDING_FILTER_FIELDS,
      pendingFormatCounts: (...args) => pendingFormatCounts(...args),
      pendingInvestigationFilterLabel: (...args) => pendingInvestigationFilterLabel(...args),
      pendingMatchesInvestigationFilter: (...args) => pendingMatchesInvestigationFilter(...args),
      pendingRecoveryPlanRowStatus: (...args) => pendingRecoveryPlanRowStatus(...args),
      pendingRowHasHealthIssue: (...args) => pendingRowHasHealthIssue(...args),
      pendingRowKey: (...args) => pendingRowKey(...args),
      pendingTableRowStatus: (...args) => pendingTableRowStatus(...args),
      renderPendingDrainActionConfidence: (...args) => renderPendingDrainActionConfidence(...args),
      renderPendingDrainDecisionChecklist: (...args) => renderPendingDrainDecisionChecklist(...args),
      renderPendingDrainGuard: (...args) => renderPendingDrainGuard(...args),
      renderPendingPostDrainTrust: (...args) => renderPendingPostDrainTrust(...args),
      selectPendingRow: (...args) => selectPendingRow(...args),
      setText: typeof setText === "function" ? setText : window.setText,
      tableStatusFilterLabel: typeof tableStatusFilterLabel === "function" ? tableStatusFilterLabel : window.tableStatusFilterLabel,
      updateTableStatusLegend: typeof updateTableStatusLegend === "function" ? updateTableStatusLegend : window.updateTableStatusLegend,
    })
    : {};
  const pendingDrainFn = function (name, fallback) {
    return typeof pendingDrain[name] === "function" ? pendingDrain[name] : fallback;
  };
  pendingCurrentFilterScope = pendingDrainFn("pendingCurrentFilterScope", pendingCurrentFilterScope);
  pendingCurrentFilterScopeEvidence = pendingDrainFn("pendingCurrentFilterScopeEvidence", pendingCurrentFilterScopeEvidence);
  pendingCurrentFilterScopeAction = pendingDrainFn("pendingCurrentFilterScopeAction", pendingCurrentFilterScopeAction);
  pendingBackendDrainScopeRows = pendingDrainFn("pendingBackendDrainScopeRows", pendingBackendDrainScopeRows);
  pendingBackendDrainScopeStatus = pendingDrainFn("pendingBackendDrainScopeStatus", pendingBackendDrainScopeStatus);
  pendingBackendDrainScopeSummaryLines = pendingDrainFn("pendingBackendDrainScopeSummaryLines", pendingBackendDrainScopeSummaryLines);
  renderPendingBackendDrainScopePreview = pendingDrainFn("renderPendingBackendDrainScopePreview", renderPendingBackendDrainScopePreview);
  pendingEvidenceClass = pendingDrainFn("pendingEvidenceClass", pendingEvidenceClass);
  pendingEvidenceRows = pendingDrainFn("pendingEvidenceRows", pendingEvidenceRows);
  pendingEvidenceStatus = pendingDrainFn("pendingEvidenceStatus", pendingEvidenceStatus);
  pendingEvidenceText = pendingDrainFn("pendingEvidenceText", pendingEvidenceText);
  pendingEvidenceAction = pendingDrainFn("pendingEvidenceAction", pendingEvidenceAction);
  pendingDrainEvidenceLines = pendingDrainFn("pendingDrainEvidenceLines", pendingDrainEvidenceLines);
  renderPendingDrainEvidence = pendingDrainFn("renderPendingDrainEvidence", renderPendingDrainEvidence);
  pendingDrainSearchText = pendingDrainFn("pendingDrainSearchText", pendingDrainSearchText);
  isPendingDrainCommand = pendingDrainFn("isPendingDrainCommand", isPendingDrainCommand);
  pendingDrainHistoryLine = pendingDrainFn("pendingDrainHistoryLine", pendingDrainHistoryLine);
  renderPendingDrainHistory = pendingDrainFn("renderPendingDrainHistory", renderPendingDrainHistory);
  pendingDrainEventsFromSnapshot = pendingDrainFn("pendingDrainEventsFromSnapshot", pendingDrainEventsFromSnapshot);
  pendingDrainEventStatus = pendingDrainFn("pendingDrainEventStatus", pendingDrainEventStatus);
  pendingDrainEventRoute = pendingDrainFn("pendingDrainEventRoute", pendingDrainEventRoute);
  pendingDrainEventLeaf = pendingDrainFn("pendingDrainEventLeaf", pendingDrainEventLeaf);
  pendingDrainEventCounts = pendingDrainFn("pendingDrainEventCounts", pendingDrainEventCounts);
  pendingDrainEventsStatus = pendingDrainFn("pendingDrainEventsStatus", pendingDrainEventsStatus);
  pendingDrainEventsLines = pendingDrainFn("pendingDrainEventsLines", pendingDrainEventsLines);
  renderPendingDrainEvents = pendingDrainFn("renderPendingDrainEvents", renderPendingDrainEvents);
  pendingDrainSummaryPayload = pendingDrainFn("pendingDrainSummaryPayload", pendingDrainSummaryPayload);
  pendingDrainSummaryItems = pendingDrainFn("pendingDrainSummaryItems", pendingDrainSummaryItems);
  pendingDrainSummaryStatus = pendingDrainFn("pendingDrainSummaryStatus", pendingDrainSummaryStatus);
  pendingDrainSummaryLeaf = pendingDrainFn("pendingDrainSummaryLeaf", pendingDrainSummaryLeaf);
  pendingDrainSummaryLines = pendingDrainFn("pendingDrainSummaryLines", pendingDrainSummaryLines);
  renderPendingDrainSummary = pendingDrainFn("renderPendingDrainSummary", renderPendingDrainSummary);
  pendingDrainLatestCommand = pendingDrainFn("pendingDrainLatestCommand", pendingDrainLatestCommand);
  pendingDrainCommandData = pendingDrainFn("pendingDrainCommandData", pendingDrainCommandData);
  pendingDrainCommandRequest = pendingDrainFn("pendingDrainCommandRequest", pendingDrainCommandRequest);
  pendingDrainCommandResultText = pendingDrainFn("pendingDrainCommandResultText", pendingDrainCommandResultText);
  pendingDrainCommandIssueLevel = pendingDrainFn("pendingDrainCommandIssueLevel", pendingDrainCommandIssueLevel);
  pendingDrainSummaryIssueLevel = pendingDrainFn("pendingDrainSummaryIssueLevel", pendingDrainSummaryIssueLevel);
  pendingDrainCorrelationStatus = pendingDrainFn("pendingDrainCorrelationStatus", pendingDrainCorrelationStatus);
  pendingDrainCorrelationLines = pendingDrainFn("pendingDrainCorrelationLines", pendingDrainCorrelationLines);
  renderPendingDrainCorrelation = pendingDrainFn("renderPendingDrainCorrelation", renderPendingDrainCorrelation);

  const pendingRecoveryState = {
    get lastPendingRecoveryPlanRows() {
      return lastPendingRecoveryPlanRows;
    },
    set lastPendingRecoveryPlanRows(value) {
      lastPendingRecoveryPlanRows = Array.isArray(value) ? value : [];
    },
    get lastPendingRecoveryPlanSignature() {
      return lastPendingRecoveryPlanSignature;
    },
    set lastPendingRecoveryPlanSignature(value) {
      lastPendingRecoveryPlanSignature = value || "";
    },
    get selectedPendingRecoveryPlanKey() {
      return selectedPendingRecoveryPlanKey;
    },
    set selectedPendingRecoveryPlanKey(value) {
      selectedPendingRecoveryPlanKey = value || "";
    },
    get pendingRecoveryPlanInFlight() {
      return pendingRecoveryPlanInFlight;
    },
    set pendingRecoveryPlanInFlight(value) {
      pendingRecoveryPlanInFlight = Boolean(value);
    },
  };

  const pendingRenderingModule = window.__pendingPublishRenderingModule || {};
  delete window.__pendingPublishRenderingModule;
  const pendingRendering = typeof pendingRenderingModule.createPendingPublishRenderingModule === "function"
    ? pendingRenderingModule.createPendingPublishRenderingModule({
      byId,
      setText,
      clearRows: typeof clearRows === "function" ? clearRows : window.clearRows,
      appendCells: typeof appendCells === "function" ? appendCells : window.appendCells,
      setCellStatusChip: typeof setCellStatusChip === "function" ? setCellStatusChip : window.setCellStatusChip,
      updateTableStatusLegend: typeof updateTableStatusLegend === "function" ? updateTableStatusLegend : window.updateTableStatusLegend,
      shortenPath: typeof shortenPath === "function" ? shortenPath : (value) => String(value || ""),
      tableScrollSnapshot, deferTableScrollRestore, pendingRowKey, getSelectedPendingRow,
      setLastPendingRows: (value) => { lastPendingRows = value; },
      setLastPendingPayload: (value) => { lastPendingPayload = value; },
      setLastPendingSnapshot: (value) => { lastPendingSnapshot = value; },
      setLastPendingEmptyMessage: (value) => { lastPendingEmptyMessage = value; },
      getLastPendingRows: () => lastPendingRows,
      getLastPendingPayload: () => lastPendingPayload,
      getSelectedPendingRowKey: () => selectedPendingRowKey,
      setSelectedPendingRowKey: (value) => { selectedPendingRowKey = value || ""; },
      getLastRecoveryPlanRows: () => lastPendingRecoveryPlanRows,
      setLastRecoveryPlanRows: (value) => { lastPendingRecoveryPlanRows = value; },
      getLastRecoveryPlanSignature: () => lastPendingRecoveryPlanSignature,
      setLastRecoveryPlanSignature: (value) => { lastPendingRecoveryPlanSignature = value || ""; },
      getSelectedRecoveryPlanKey: () => selectedPendingRecoveryPlanKey,
      setSelectedRecoveryPlanKey: (value) => { selectedPendingRecoveryPlanKey = value || ""; },
      pendingEmptyStateMessage: (...args) => pendingEmptyStateMessage(...args), pendingFormatCounts: (...args) => pendingFormatCounts(...args),
      renderPendingDrainProgress: (...args) => renderPendingDrainProgress(...args), renderPendingInventoryProgress: (...args) => renderPendingInventoryProgress(...args),
      renderPendingPublishReadiness: (...args) => renderPendingPublishReadiness(...args), renderPendingRiskBreakdown: (...args) => renderPendingRiskBreakdown(...args),
      renderPendingValidation: (...args) => renderPendingValidation(...args), renderPendingWorkflow: (...args) => renderPendingWorkflow(...args),
      renderPendingReviewBoard: (...args) => renderPendingReviewBoard(...args), renderPendingDrainEvidence: (...args) => renderPendingDrainEvidence(...args),
      renderPendingDrainHistory: (...args) => renderPendingDrainHistory(...args), renderPendingOpenHistory: (...args) => renderPendingOpenHistory(...args),
      renderPendingRecoveryPlanHistory: (...args) => renderPendingRecoveryPlanHistory(...args), renderPendingRepairManifestHistory: (...args) => renderPendingRepairManifestHistory(...args),
      renderPendingDrainEvents: (...args) => renderPendingDrainEvents(...args), renderPendingDrainSummary: (...args) => renderPendingDrainSummary(...args),
      renderPendingDrainCorrelation: (...args) => renderPendingDrainCorrelation(...args), renderPendingPostDrainTrust: (...args) => renderPendingPostDrainTrust(...args),
      renderPendingDrainActionConfidence: (...args) => renderPendingDrainActionConfidence(...args), renderPendingBackendDrainScopePreview: (...args) => renderPendingBackendDrainScopePreview(...args),
      renderPendingDrainDecisionChecklist: (...args) => renderPendingDrainDecisionChecklist(...args), renderPendingDrainGuard: (...args) => renderPendingDrainGuard(...args),
      renderPendingDetail: (...args) => renderPendingDetail(...args), renderPendingRows: (...args) => renderPendingRows(...args),
      renderPendingRepairManifestControls: (...args) => renderPendingRepairManifestControls(...args), renderPendingRepairOrphanControls: (...args) => renderPendingRepairOrphanControls(...args),
      renderPendingRecoveryPlanRows: (...args) => renderPendingRecoveryPlanRows(...args), getCommandHistory: () => typeof getCommandHistory === "function" ? getCommandHistory() : [],
    }) : {};
  const { renderPendingPublish, renderPendingDrainProgress, getLastPendingPublishPayload, getLastPendingPublishRows,
    pendingRecoverySignatureValue, pendingRecoveryPlanSignature, clearStalePendingRecoveryPlan,
    pendingFileInventoryPayload, pendingFileInventoryRows, pendingFileInventoryStatus, pendingFileInventorySummaryLines,
    pendingFileInventoryRowStatus, renderPendingFileInventory } = pendingRendering;
  const pendingRecoveryModule = window.__pendingPublishRecoveryModule || {};
  delete window.__pendingPublishRecoveryModule;
  const pendingRecovery = typeof pendingRecoveryModule.createPendingPublishRecoveryModule === "function"
    ? pendingRecoveryModule.createPendingPublishRecoveryModule({
      apiPost: typeof apiPost === "function" ? apiPost : window.apiPost,
      appendCells: typeof appendCells === "function" ? appendCells : window.appendCells,
      appendCommandResult: typeof appendCommandResult === "function" ? appendCommandResult : window.appendCommandResult,
      byId: typeof byId === "function" ? byId : window.byId,
      clearRows: typeof clearRows === "function" ? clearRows : window.clearRows,
      commandHistoryCompactEvidenceLine: typeof window.commandHistoryCompactEvidenceLine === "function" ? window.commandHistoryCompactEvidenceLine : (typeof commandHistoryCompactEvidenceLine === "function" ? commandHistoryCompactEvidenceLine : null),
      renderCompactCommandHistoryBlock: window.mediaPipelineCommandHistory?.renderCompactCommandHistoryBlock || null,
      getCommandHistory: typeof window.getCommandHistory === "function" ? () => window.getCommandHistory() : (typeof getCommandHistory === "function" ? () => getCommandHistory() : () => []),
      getLastPendingPayload: () => lastPendingPayload || {},
      getLastPendingRows: () => Array.isArray(lastPendingRows) ? lastPendingRows : [],
      getLastPendingSnapshot: () => lastPendingSnapshot || {},
      getCurrentPendingRecoveryPlanSignature: (pending, rows) => pendingRecoveryPlanSignature(pending || lastPendingPayload, Array.isArray(rows) ? rows : lastPendingRows),
      getSelectedPendingRow: (...args) => getSelectedPendingRow(...args),
      makeRowSelectable: typeof makeRowSelectable === "function" ? makeRowSelectable : window.makeRowSelectable,
      pendingFormatCounts: (...args) => pendingFormatCounts(...args),
      pendingRowKey: (...args) => pendingRowKey(...args),
      renderPendingBackendDrainScopePreview: (...args) => renderPendingBackendDrainScopePreview(...args),
      renderPendingDrainActionConfidence: (...args) => renderPendingDrainActionConfidence(...args),
      renderPendingDrainDecisionChecklist: (...args) => renderPendingDrainDecisionChecklist(...args),
      renderPendingDrainGuard: (...args) => renderPendingDrainGuard(...args),
      renderPendingDrainOverview: (...args) => renderPendingDrainOverview(...args),
      setText: typeof setText === "function" ? setText : window.setText,
      state: pendingRecoveryState,
      updateTableStatusLegend: typeof updateTableStatusLegend === "function" ? updateTableStatusLegend : window.updateTableStatusLegend,
    })
    : {};
  setPendingRecoveryPlanBusy = typeof pendingRecovery.setPendingRecoveryPlanBusy === "function" ? pendingRecovery.setPendingRecoveryPlanBusy : setPendingRecoveryPlanBusy;
  rejectPendingRecoveryPlanWhileBusy = typeof pendingRecovery.rejectPendingRecoveryPlanWhileBusy === "function" ? pendingRecovery.rejectPendingRecoveryPlanWhileBusy : rejectPendingRecoveryPlanWhileBusy;
  requestPendingRecoveryPlan = typeof pendingRecovery.requestPendingRecoveryPlan === "function" ? pendingRecovery.requestPendingRecoveryPlan : requestPendingRecoveryPlan;
  renderPendingRecoveryPlanResult = typeof pendingRecovery.renderPendingRecoveryPlanResult === "function" ? pendingRecovery.renderPendingRecoveryPlanResult : renderPendingRecoveryPlanResult;
  pendingRecoveryPlanResultLines = typeof pendingRecovery.pendingRecoveryPlanResultLines === "function" ? pendingRecovery.pendingRecoveryPlanResultLines : pendingRecoveryPlanResultLines;
  pendingRecoveryPlanRowKey = typeof pendingRecovery.pendingRecoveryPlanRowKey === "function" ? pendingRecovery.pendingRecoveryPlanRowKey : pendingRecoveryPlanRowKey;
  pendingRecoveryPlanRowStatus = typeof pendingRecovery.pendingRecoveryPlanRowStatus === "function" ? pendingRecovery.pendingRecoveryPlanRowStatus : pendingRecoveryPlanRowStatus;
  pendingRecoveryPlanEvidenceText = typeof pendingRecovery.pendingRecoveryPlanEvidenceText === "function" ? pendingRecovery.pendingRecoveryPlanEvidenceText : pendingRecoveryPlanEvidenceText;
  pendingRecoveryPlanActionText = typeof pendingRecovery.pendingRecoveryPlanActionText === "function" ? pendingRecovery.pendingRecoveryPlanActionText : pendingRecoveryPlanActionText;
  pendingRecoveryPlanRowDetailLines = typeof pendingRecovery.pendingRecoveryPlanRowDetailLines === "function" ? pendingRecovery.pendingRecoveryPlanRowDetailLines : pendingRecoveryPlanRowDetailLines;
  renderPendingRecoveryPlanRows = typeof pendingRecovery.renderPendingRecoveryPlanRows === "function" ? pendingRecovery.renderPendingRecoveryPlanRows : renderPendingRecoveryPlanRows;
  selectPendingRecoveryPlanRow = typeof pendingRecovery.selectPendingRecoveryPlanRow === "function" ? pendingRecovery.selectPendingRecoveryPlanRow : selectPendingRecoveryPlanRow;
  renderPendingRecoveryPlanRowDetail = typeof pendingRecovery.renderPendingRecoveryPlanRowDetail === "function" ? pendingRecovery.renderPendingRecoveryPlanRowDetail : renderPendingRecoveryPlanRowDetail;
  renderPendingRecoveryPlanHistory = typeof pendingRecovery.renderPendingRecoveryPlanHistory === "function" ? pendingRecovery.renderPendingRecoveryPlanHistory : renderPendingRecoveryPlanHistory;
  isPendingRecoveryPlanCommand = typeof pendingRecovery.isPendingRecoveryPlanCommand === "function" ? pendingRecovery.isPendingRecoveryPlanCommand : isPendingRecoveryPlanCommand;
  pendingRecoveryPlanHistoryLine = typeof pendingRecovery.pendingRecoveryPlanHistoryLine === "function" ? pendingRecovery.pendingRecoveryPlanHistoryLine : pendingRecoveryPlanHistoryLine;
  pendingRecoveryPlanResultData = typeof pendingRecovery.pendingRecoveryPlanResultData === "function" ? pendingRecovery.pendingRecoveryPlanResultData : pendingRecoveryPlanResultData;
  pendingRecoveryPlanRowLabel = typeof pendingRecovery.pendingRecoveryPlanRowLabel === "function" ? pendingRecovery.pendingRecoveryPlanRowLabel : pendingRecoveryPlanRowLabel;

  const pendingRepairModule = window.__pendingPublishRepairModule || {};
  delete window.__pendingPublishRepairModule;
  const pendingRepair = typeof pendingRepairModule.createPendingPublishRepairModule === "function"
    ? pendingRepairModule.createPendingPublishRepairModule({
      apiPost: typeof apiPost === "function" ? apiPost : window.apiPost,
      appendCommandResult: typeof appendCommandResult === "function" ? appendCommandResult : window.appendCommandResult,
      byId: typeof byId === "function" ? byId : window.byId,
      commandHistoryCompactEvidenceLine: typeof window.commandHistoryCompactEvidenceLine === "function" ? window.commandHistoryCompactEvidenceLine : (typeof commandHistoryCompactEvidenceLine === "function" ? commandHistoryCompactEvidenceLine : null),
      renderCompactCommandHistoryBlock: window.mediaPipelineCommandHistory?.renderCompactCommandHistoryBlock || null,
      getCommandHistory: typeof window.getCommandHistory === "function" ? () => window.getCommandHistory() : (typeof getCommandHistory === "function" ? () => getCommandHistory() : () => []),
      getSelectedPendingRow: (...args) => getSelectedPendingRow(...args),
      pendingRowKey: (...args) => pendingRowKey(...args),
      setText: typeof setText === "function" ? setText : window.setText,
    })
    : {};
  initPendingRepairManifestEvents = typeof pendingRepair.initPendingRepairManifestEvents === "function" ? pendingRepair.initPendingRepairManifestEvents : initPendingRepairManifestEvents;
  isPendingRepairManifestCommand = typeof pendingRepair.isPendingRepairManifestCommand === "function" ? pendingRepair.isPendingRepairManifestCommand : isPendingRepairManifestCommand;
  pendingRepairDryRunIsSafeForSelection = typeof pendingRepair.pendingRepairDryRunIsSafeForSelection === "function" ? pendingRepair.pendingRepairDryRunIsSafeForSelection : pendingRepairDryRunIsSafeForSelection;
  pendingRepairManifestApplyRequest = typeof pendingRepair.pendingRepairManifestApplyRequest === "function" ? pendingRepair.pendingRepairManifestApplyRequest : pendingRepairManifestApplyRequest;
  pendingRepairManifestDryRunRequest = typeof pendingRepair.pendingRepairManifestDryRunRequest === "function" ? pendingRepair.pendingRepairManifestDryRunRequest : pendingRepairManifestDryRunRequest;
  pendingRepairManifestHistoryLine = typeof pendingRepair.pendingRepairManifestHistoryLine === "function" ? pendingRepair.pendingRepairManifestHistoryLine : pendingRepairManifestHistoryLine;
  pendingRepairManifestResultLines = typeof pendingRepair.pendingRepairManifestResultLines === "function" ? pendingRepair.pendingRepairManifestResultLines : pendingRepairManifestResultLines;
  renderPendingRepairManifestControls = typeof pendingRepair.renderPendingRepairManifestControls === "function" ? pendingRepair.renderPendingRepairManifestControls : renderPendingRepairManifestControls;
  renderPendingRepairManifestHistory = typeof pendingRepair.renderPendingRepairManifestHistory === "function" ? pendingRepair.renderPendingRepairManifestHistory : renderPendingRepairManifestHistory;
  requestPendingRepairManifestApply = typeof pendingRepair.requestPendingRepairManifestApply === "function" ? pendingRepair.requestPendingRepairManifestApply : requestPendingRepairManifestApply;
  requestPendingRepairManifestDryRun = typeof pendingRepair.requestPendingRepairManifestDryRun === "function" ? pendingRepair.requestPendingRepairManifestDryRun : requestPendingRepairManifestDryRun;
  setPendingRepairManifestBusy = typeof pendingRepair.setPendingRepairManifestBusy === "function" ? pendingRepair.setPendingRepairManifestBusy : setPendingRepairManifestBusy;
  isPendingRepairOrphanCommand = typeof pendingRepair.isPendingRepairOrphanCommand === "function" ? pendingRepair.isPendingRepairOrphanCommand : isPendingRepairOrphanCommand;
  pendingOrphanDryRunIsSafeForSelection = typeof pendingRepair.pendingOrphanDryRunIsSafeForSelection === "function" ? pendingRepair.pendingOrphanDryRunIsSafeForSelection : pendingOrphanDryRunIsSafeForSelection;
  pendingRepairOrphanApplyRequest = typeof pendingRepair.pendingRepairOrphanApplyRequest === "function" ? pendingRepair.pendingRepairOrphanApplyRequest : pendingRepairOrphanApplyRequest;
  pendingRepairOrphanDryRunRequest = typeof pendingRepair.pendingRepairOrphanDryRunRequest === "function" ? pendingRepair.pendingRepairOrphanDryRunRequest : pendingRepairOrphanDryRunRequest;
  renderPendingRepairOrphanControls = typeof pendingRepair.renderPendingRepairOrphanControls === "function" ? pendingRepair.renderPendingRepairOrphanControls : renderPendingRepairOrphanControls;
  renderPendingRepairOrphanHistory = typeof pendingRepair.renderPendingRepairOrphanHistory === "function" ? pendingRepair.renderPendingRepairOrphanHistory : renderPendingRepairOrphanHistory;
  requestPendingRepairOrphanApply = typeof pendingRepair.requestPendingRepairOrphanApply === "function" ? pendingRepair.requestPendingRepairOrphanApply : requestPendingRepairOrphanApply;
  requestPendingRepairOrphanDryRun = typeof pendingRepair.requestPendingRepairOrphanDryRun === "function" ? pendingRepair.requestPendingRepairOrphanDryRun : requestPendingRepairOrphanDryRun;
  setPendingRepairOrphanBusy = typeof pendingRepair.setPendingRepairOrphanBusy === "function" ? pendingRepair.setPendingRepairOrphanBusy : setPendingRepairOrphanBusy;

  const pendingConfidenceState = {
    get selectedPendingDrainDecisionKey() {
      return selectedPendingDrainDecisionKey;
    },
    set selectedPendingDrainDecisionKey(value) {
      selectedPendingDrainDecisionKey = value || "";
    },
    get selectedPendingPostDrainTrustKey() {
      return selectedPendingPostDrainTrustKey;
    },
    set selectedPendingPostDrainTrustKey(value) {
      selectedPendingPostDrainTrustKey = value || "";
    },
  };

  const pendingConfidenceModule = window.__pendingPublishConfidenceModule || {};
  delete window.__pendingPublishConfidenceModule;
  const pendingConfidence = typeof pendingConfidenceModule.createPendingPublishConfidenceModule === "function"
    ? pendingConfidenceModule.createPendingPublishConfidenceModule({
      appendCells: typeof appendCells === "function" ? appendCells : window.appendCells,
      byId: typeof byId === "function" ? byId : window.byId,
      clearRows: typeof clearRows === "function" ? clearRows : window.clearRows,
      getCommandHistory: typeof window.getCommandHistory === "function" ? () => window.getCommandHistory() : (typeof getCommandHistory === "function" ? () => getCommandHistory() : () => []),
      getLastPendingPayload: () => lastPendingPayload || {},
      getLastPendingRecoveryPlanRows: () => Array.isArray(lastPendingRecoveryPlanRows) ? lastPendingRecoveryPlanRows : [],
      getLastPendingRecoveryPlanSignature: () => lastPendingRecoveryPlanSignature || "",
      getCurrentPendingRecoveryPlanSignature: (pending, rows) => pendingRecoveryPlanSignature(pending || lastPendingPayload, Array.isArray(rows) ? rows : lastPendingRows),
      getLastPendingRows: () => Array.isArray(lastPendingRows) ? lastPendingRows : [],
      getLastPendingSnapshot: () => lastPendingSnapshot || {},
      getSelectedPendingRow: (...args) => getSelectedPendingRow(...args),
      makeRowSelectable: typeof makeRowSelectable === "function" ? makeRowSelectable : window.makeRowSelectable,
      pendingCurrentFilterScope: (...args) => pendingCurrentFilterScope(...args),
      pendingCurrentFilterScopeAction: (...args) => pendingCurrentFilterScopeAction(...args),
      pendingCurrentFilterScopeEvidence: (...args) => pendingCurrentFilterScopeEvidence(...args),
      pendingDrainCommandIssueLevel: (...args) => pendingDrainCommandIssueLevel(...args),
      pendingDrainCommandResultText: (...args) => pendingDrainCommandResultText(...args),
      pendingDrainEventCounts: (...args) => pendingDrainEventCounts(...args),
      pendingDrainEventLeaf: (...args) => pendingDrainEventLeaf(...args),
      pendingDrainEventRoute: (...args) => pendingDrainEventRoute(...args),
      pendingDrainEventStatus: (...args) => pendingDrainEventStatus(...args),
      pendingDrainEventsFromSnapshot: (...args) => pendingDrainEventsFromSnapshot(...args),
      pendingDrainHistoryLine: (...args) => pendingDrainHistoryLine(...args),
      pendingDrainLatestCommand: (...args) => pendingDrainLatestCommand(...args),
      pendingDrainSummaryIssueLevel: (...args) => pendingDrainSummaryIssueLevel(...args),
      pendingDrainSummaryItems: (...args) => pendingDrainSummaryItems(...args),
      pendingDrainSummaryLeaf: (...args) => pendingDrainSummaryLeaf(...args),
      pendingDrainSummaryPayload: (...args) => pendingDrainSummaryPayload(...args),
      pendingDrainSummaryStatus: (...args) => pendingDrainSummaryStatus(...args),
      pendingEvidenceClass: (...args) => pendingEvidenceClass(...args),
      pendingEvidenceRows: (...args) => pendingEvidenceRows(...args),
      pendingEvidenceStatus: (...args) => pendingEvidenceStatus(...args),
      pendingEvidenceText: (...args) => pendingEvidenceText(...args),
      pendingFormatCounts: (...args) => pendingFormatCounts(...args),
      pendingRecoveryPlanRowStatus: (...args) => pendingRecoveryPlanRowStatus(...args),
      pendingRowHasHealthIssue: (...args) => pendingRowHasHealthIssue(...args),
      pendingRowKey: (...args) => pendingRowKey(...args),
      pendingSampleValidationHandoffLines: (...args) => pendingSampleValidationHandoffLines(...args),
      pendingValidationStatus: (...args) => pendingValidationStatus(...args),
      renderPendingDetail: (...args) => renderPendingDetail(...args),
      renderPendingDrainEvidence: (...args) => renderPendingDrainEvidence(...args),
      renderPendingReviewDigest: (...args) => renderPendingReviewDigest(...args),
      renderPendingRows: (...args) => renderPendingRows(...args),
      setSelectedPendingRowKey: (value) => {
        selectedPendingRowKey = value || "";
      },
      setText: typeof setText === "function" ? setText : window.setText,
      state: pendingConfidenceState,
      updateTableStatusLegend: typeof updateTableStatusLegend === "function" ? updateTableStatusLegend : window.updateTableStatusLegend,
    })
    : {};
  pendingDrainConfidenceRows = typeof pendingConfidence.pendingDrainConfidenceRows === "function" ? pendingConfidence.pendingDrainConfidenceRows : pendingDrainConfidenceRows;
  pendingDrainConfidenceStatus = typeof pendingConfidence.pendingDrainConfidenceStatus === "function" ? pendingConfidence.pendingDrainConfidenceStatus : pendingDrainConfidenceStatus;
  pendingDrainConfidenceSummaryLines = typeof pendingConfidence.pendingDrainConfidenceSummaryLines === "function" ? pendingConfidence.pendingDrainConfidenceSummaryLines : pendingDrainConfidenceSummaryLines;
  renderPendingDrainActionConfidence = typeof pendingConfidence.renderPendingDrainActionConfidence === "function" ? pendingConfidence.renderPendingDrainActionConfidence : renderPendingDrainActionConfidence;
  pendingDrainDecisionRows = typeof pendingConfidence.pendingDrainDecisionRows === "function" ? pendingConfidence.pendingDrainDecisionRows : pendingDrainDecisionRows;
  pendingDrainDecisionStatus = typeof pendingConfidence.pendingDrainDecisionStatus === "function" ? pendingConfidence.pendingDrainDecisionStatus : pendingDrainDecisionStatus;
  pendingDrainDecisionStatusState = typeof pendingConfidence.pendingDrainDecisionStatusState === "function" ? pendingConfidence.pendingDrainDecisionStatusState : pendingDrainDecisionStatusState;
  pendingDrainDecisionSummaryLines = typeof pendingConfidence.pendingDrainDecisionSummaryLines === "function" ? pendingConfidence.pendingDrainDecisionSummaryLines : pendingDrainDecisionSummaryLines;
  pendingDrainDecisionDetailLines = typeof pendingConfidence.pendingDrainDecisionDetailLines === "function" ? pendingConfidence.pendingDrainDecisionDetailLines : pendingDrainDecisionDetailLines;
  pendingDrainDecisionPostureStatus = typeof pendingConfidence.pendingDrainDecisionPostureStatus === "function" ? pendingConfidence.pendingDrainDecisionPostureStatus : pendingDrainDecisionPostureStatus;
  renderPendingDrainDecisionChecklist = typeof pendingConfidence.renderPendingDrainDecisionChecklist === "function" ? pendingConfidence.renderPendingDrainDecisionChecklist : renderPendingDrainDecisionChecklist;
  pendingPostDrainTrustRows = typeof pendingConfidence.pendingPostDrainTrustRows === "function" ? pendingConfidence.pendingPostDrainTrustRows : pendingPostDrainTrustRows;
  pendingPostDrainTrustStatus = typeof pendingConfidence.pendingPostDrainTrustStatus === "function" ? pendingConfidence.pendingPostDrainTrustStatus : pendingPostDrainTrustStatus;
  pendingPostDrainTrustSummaryLines = typeof pendingConfidence.pendingPostDrainTrustSummaryLines === "function" ? pendingConfidence.pendingPostDrainTrustSummaryLines : pendingPostDrainTrustSummaryLines;
  pendingPostDrainTrustDetailLines = typeof pendingConfidence.pendingPostDrainTrustDetailLines === "function" ? pendingConfidence.pendingPostDrainTrustDetailLines : pendingPostDrainTrustDetailLines;
  pendingPostDrainTrustPostureStatus = typeof pendingConfidence.pendingPostDrainTrustPostureStatus === "function" ? pendingConfidence.pendingPostDrainTrustPostureStatus : pendingPostDrainTrustPostureStatus;
  renderPendingPostDrainTrust = typeof pendingConfidence.renderPendingPostDrainTrust === "function" ? pendingConfidence.renderPendingPostDrainTrust : renderPendingPostDrainTrust;
  pendingDrainGuardState = typeof pendingConfidence.pendingDrainGuardState === "function" ? pendingConfidence.pendingDrainGuardState : pendingDrainGuardState;
  pendingDrainGuardLines = typeof pendingConfidence.pendingDrainGuardLines === "function" ? pendingConfidence.pendingDrainGuardLines : pendingDrainGuardLines;
  renderPendingDrainGuard = typeof pendingConfidence.renderPendingDrainGuard === "function" ? pendingConfidence.renderPendingDrainGuard : renderPendingDrainGuard;

  initPendingActionCenterEvents();
  initPendingRepairManifestEvents();

  /**
   * Public namespace for the Pending Publish page module.
   * Prefer this namespace from new code; flat window.* exports are transitional compatibility aliases when present.
   */
  window.mediaPipelinePendingPublishView = {
    renderPendingPublish,
    renderPendingInventoryProgress,
    pendingInventoryProgressBars,
    renderPendingFileInventory,
    pendingFileInventoryPayload,
    pendingFileInventoryRows,
    pendingFileInventoryStatus,
    pendingFileInventorySummaryLines,
    renderPendingRows,
    resetPendingFilters,
    renderPendingDetail,
    getLastPendingPublishPayload,
    getLastPendingPublishRows,
    renderPendingPublishReadiness,
    renderPendingRiskBreakdown,
    renderPendingValidation,
    renderPendingWorkflow,
    renderPendingReviewBoard,
    renderPendingDrainEvidence,
    renderPendingDrainEvents,
    renderPendingDrainSummary,
    renderPendingDrainCorrelation,
    renderPendingDrainActionConfidence,
    renderPendingBackendDrainScopePreview,
    pendingBackendDrainScopeRows,
    pendingBackendDrainScopeStatus,
    pendingBackendDrainScopeSummaryLines,
    renderPendingDrainDecisionChecklist,
    pendingPublishReadinessStatus,
    pendingPublishReadinessLines,
    pendingRiskStatus,
    pendingRiskLines,
    pendingValidationStatus,
    pendingValidationChecklistLines,
    pendingWorkflowStatus,
    pendingWorkflowLines,
    pendingReviewStatus,
    pendingReviewBoardLines,
    pendingReviewRows,
    renderPendingReviewDigest,
    pendingReviewDigestStatus,
    pendingReviewDigestAction,
    pendingEvidenceClass,
    pendingEvidenceRows,
    pendingEvidenceStatus,
    pendingDrainEvidenceLines,
    pendingEvidenceAction,
    pendingRowReviewChecklistLines,
    pendingRowIssueDigestLines,
    pendingSelectedQuickSignalLines,
    pendingSelectedAtAGlanceState,
    pendingSelectedAtAGlanceStatus,
    pendingSelectedAtAGlanceLines,
    renderPendingSelectedAtAGlance,
    pendingFilterVisibilityLines,
    pendingCurrentFilterScope,
    pendingCurrentFilterScopeEvidence,
    pendingCurrentFilterScopeAction,
    pendingFocusedInvestigationLabels,
    pendingInvestigationSignalLines,
    pendingRealMediaTraceLines,
    pendingSelectedCompletedCorrelationRows,
    pendingSelectedCompletedCorrelationLines,
    pendingSampleValidationHandoffLines,
    pendingSampleValidationComparisonLines,
    pendingRowTrustSummaryLines,
    pendingDrainEventsStatus,
    pendingDrainEventsLines,
    pendingDrainEventsFromSnapshot,
    pendingDrainSummaryStatus,
    pendingDrainSummaryLines,
    pendingDrainSummaryPayload,
    pendingDrainLatestCommand,
    pendingDrainCommandIssueLevel,
    pendingDrainSummaryIssueLevel,
    pendingDrainCorrelationStatus,
    pendingDrainCorrelationLines,
    pendingDrainConfidenceRows,
    pendingDrainConfidenceStatus,
    pendingDrainConfidenceSummaryLines,
    pendingDrainDecisionRows,
    pendingDrainDecisionStatus,
    pendingDrainDecisionStatusState,
    pendingDrainDecisionSummaryLines,
    pendingDrainDecisionDetailLines,
    pendingDrainDecisionPostureStatus,
    renderPendingDrainProgress,
    pendingPostDrainTrustRows,
    pendingPostDrainTrustStatus,
    pendingPostDrainTrustSummaryLines,
    pendingPostDrainTrustDetailLines,
    pendingPostDrainTrustPostureStatus,
    renderPendingPostDrainTrust,
    pendingDrainGuardState,
    pendingDrainGuardLines,
    renderPendingDrainGuard,
    pendingActionCenterTriage,
    pendingActionCenterOutcome,
    renderPendingActionCenter,
    applyPendingActionFilter,
    activateQuickLink,
    initPendingActionCenterEvents,
    pendingDrainOverviewState,
    renderPendingDrainOverview,
    pendingRecoverySummaryPayload,
    pendingRecoverySummaryLines,
    pendingFormatCounts,
    pendingListText,
    pendingSelectedOpenTargetLines,
    pendingEmptyStateMessage,
    pendingDiagnosticsActionsForRow,
    pendingDiagnosticsGuidanceLines,
    renderPendingDiagnosticsLinks,
    requestPendingDiagnosticsAction,
    selectPendingRow,
    getSelectedPendingRow,
    pendingRowKey,
    setPendingOpenBusy,
    rejectPendingOpenWhileBusy,
    requestPendingPublishOpen,
    renderPendingDrainHistory,
    isPendingDrainCommand,
    pendingDrainHistoryLine,
    pendingDrainSearchText,
    renderPendingOpenHistory,
    isPendingOpenCommand,
    pendingOpenHistoryLine,
    setPendingRecoveryPlanBusy,
    rejectPendingRecoveryPlanWhileBusy,
    requestPendingRecoveryPlan,
    renderPendingRecoveryPlanResult,
    pendingRecoveryPlanResultLines,
    pendingRecoveryPlanRowKey,
    pendingRecoveryPlanRowStatus,
    pendingRecoveryPlanEvidenceText,
    pendingRecoveryPlanActionText,
    pendingRecoveryPlanRowDetailLines,
    renderPendingRecoveryPlanRows,
    selectPendingRecoveryPlanRow,
    renderPendingRecoveryPlanRowDetail,
    renderPendingRecoveryPlanHistory,
    isPendingRecoveryPlanCommand,
    pendingRecoveryPlanHistoryLine,
    initPendingRepairManifestEvents,
    isPendingRepairManifestCommand,
    pendingRepairDryRunIsSafeForSelection,
    pendingRepairManifestApplyRequest,
    pendingRepairManifestDryRunRequest,
    pendingRepairManifestHistoryLine,
    pendingRepairManifestResultLines,
    renderPendingRepairManifestControls,
    renderPendingRepairManifestHistory,
    requestPendingRepairManifestApply,
    requestPendingRepairManifestDryRun,
    setPendingRepairManifestBusy,
    isPendingRepairOrphanCommand,
    pendingOrphanDryRunIsSafeForSelection,
    pendingRepairOrphanApplyRequest,
    pendingRepairOrphanDryRunRequest,
    renderPendingRepairOrphanControls,
    renderPendingRepairOrphanHistory,
    requestPendingRepairOrphanApply,
    requestPendingRepairOrphanDryRun,
    setPendingRepairOrphanBusy,
  };
  window.renderPendingPublish = renderPendingPublish;
  window.renderPendingFileInventory = renderPendingFileInventory;
  window.renderPendingDetail = renderPendingDetail;
  window.getLastPendingPublishPayload = getLastPendingPublishPayload;
  window.renderPendingDrainEvidence = renderPendingDrainEvidence;
  window.renderPendingDrainProgress = renderPendingDrainProgress;
  window.renderPendingDrainEvents = renderPendingDrainEvents;
  window.renderPendingDrainSummary = renderPendingDrainSummary;
  window.renderPendingDrainCorrelation = renderPendingDrainCorrelation;
  window.renderPendingDrainActionConfidence = renderPendingDrainActionConfidence;
  window.renderPendingBackendDrainScopePreview = renderPendingBackendDrainScopePreview;
  window.pendingBackendDrainScopeRows = pendingBackendDrainScopeRows;
  window.pendingBackendDrainScopeStatus = pendingBackendDrainScopeStatus;
  window.pendingBackendDrainScopeSummaryLines = pendingBackendDrainScopeSummaryLines;
  window.renderPendingDrainDecisionChecklist = renderPendingDrainDecisionChecklist;
  window.pendingValidationStatus = pendingValidationStatus;
  window.pendingReviewRows = pendingReviewRows;
  window.renderPendingReviewDigest = renderPendingReviewDigest;
  window.pendingEvidenceClass = pendingEvidenceClass;
  window.pendingEvidenceRows = pendingEvidenceRows;
  window.pendingEvidenceStatus = pendingEvidenceStatus;
  window.pendingDrainEvidenceLines = pendingDrainEvidenceLines;
  window.pendingEvidenceAction = pendingEvidenceAction;
  window.pendingCurrentFilterScope = pendingCurrentFilterScope;
  window.pendingCurrentFilterScopeEvidence = pendingCurrentFilterScopeEvidence;
  window.pendingCurrentFilterScopeAction = pendingCurrentFilterScopeAction;
  window.pendingSampleValidationHandoffLines = pendingSampleValidationHandoffLines;
  window.pendingDrainEventsStatus = pendingDrainEventsStatus;
  window.pendingDrainEventsLines = pendingDrainEventsLines;
  window.pendingDrainEventsFromSnapshot = pendingDrainEventsFromSnapshot;
  window.pendingDrainSummaryStatus = pendingDrainSummaryStatus;
  window.pendingDrainSummaryLines = pendingDrainSummaryLines;
  window.pendingDrainSummaryPayload = pendingDrainSummaryPayload;
  window.pendingDrainLatestCommand = pendingDrainLatestCommand;
  window.pendingDrainCommandIssueLevel = pendingDrainCommandIssueLevel;
  window.pendingDrainSummaryIssueLevel = pendingDrainSummaryIssueLevel;
  window.pendingDrainCorrelationStatus = pendingDrainCorrelationStatus;
  window.pendingDrainCorrelationLines = pendingDrainCorrelationLines;
  window.pendingDrainConfidenceRows = pendingDrainConfidenceRows;
  window.pendingDrainConfidenceStatus = pendingDrainConfidenceStatus;
  window.pendingDrainConfidenceSummaryLines = pendingDrainConfidenceSummaryLines;
  window.pendingDrainDecisionRows = pendingDrainDecisionRows;
  window.pendingDrainDecisionStatus = pendingDrainDecisionStatus;
  window.pendingDrainDecisionStatusState = pendingDrainDecisionStatusState;
  window.pendingDrainDecisionSummaryLines = pendingDrainDecisionSummaryLines;
  window.pendingDrainDecisionDetailLines = pendingDrainDecisionDetailLines;
  window.pendingDrainDecisionPostureStatus = pendingDrainDecisionPostureStatus;
  window.pendingPostDrainTrustRows = pendingPostDrainTrustRows;
  window.pendingPostDrainTrustStatus = pendingPostDrainTrustStatus;
  window.pendingPostDrainTrustSummaryLines = pendingPostDrainTrustSummaryLines;
  window.pendingPostDrainTrustDetailLines = pendingPostDrainTrustDetailLines;
  window.pendingPostDrainTrustPostureStatus = pendingPostDrainTrustPostureStatus;
  window.pendingDrainGuardState = pendingDrainGuardState;
  window.pendingDrainGuardLines = pendingDrainGuardLines;
  window.renderPendingDrainGuard = renderPendingDrainGuard;
  window.pendingDrainOverviewState = pendingDrainOverviewState;
  window.renderPendingDrainOverview = renderPendingDrainOverview;
  window.pendingFormatCounts = pendingFormatCounts;
  window.pendingListText = pendingListText;
  window.pendingSelectedOpenTargetLines = pendingSelectedOpenTargetLines;
  window.pendingDiagnosticsActionsForRow = pendingDiagnosticsActionsForRow;
  window.pendingDiagnosticsGuidanceLines = pendingDiagnosticsGuidanceLines;
  window.renderPendingDiagnosticsLinks = renderPendingDiagnosticsLinks;
  window.requestPendingDiagnosticsAction = requestPendingDiagnosticsAction;
  window.selectPendingRow = selectPendingRow;
  window.getSelectedPendingRow = getSelectedPendingRow;
  window.pendingRowKey = pendingRowKey;
  window.setPendingOpenBusy = setPendingOpenBusy;
  window.rejectPendingOpenWhileBusy = rejectPendingOpenWhileBusy;
  window.requestPendingPublishOpen = requestPendingPublishOpen;
  window.renderPendingDrainHistory = renderPendingDrainHistory;
  window.isPendingDrainCommand = isPendingDrainCommand;
  window.pendingDrainHistoryLine = pendingDrainHistoryLine;
  window.pendingDrainSearchText = pendingDrainSearchText;
  window.renderPendingOpenHistory = renderPendingOpenHistory;
  window.isPendingOpenCommand = isPendingOpenCommand;
  window.pendingOpenHistoryLine = pendingOpenHistoryLine;
  window.setPendingRecoveryPlanBusy = setPendingRecoveryPlanBusy;
  window.rejectPendingRecoveryPlanWhileBusy = rejectPendingRecoveryPlanWhileBusy;
  window.requestPendingRecoveryPlan = requestPendingRecoveryPlan;
  window.pendingRecoveryPlanResultLines = pendingRecoveryPlanResultLines;
  window.pendingRecoveryPlanRowKey = pendingRecoveryPlanRowKey;
  window.pendingRecoveryPlanRowStatus = pendingRecoveryPlanRowStatus;
  window.pendingRecoveryPlanEvidenceText = pendingRecoveryPlanEvidenceText;
  window.pendingRecoveryPlanActionText = pendingRecoveryPlanActionText;
  window.pendingRecoveryPlanRowDetailLines = pendingRecoveryPlanRowDetailLines;
  window.renderPendingRecoveryPlanRows = renderPendingRecoveryPlanRows;
  window.selectPendingRecoveryPlanRow = selectPendingRecoveryPlanRow;
  window.renderPendingRecoveryPlanRowDetail = renderPendingRecoveryPlanRowDetail;
  window.renderPendingRecoveryPlanHistory = renderPendingRecoveryPlanHistory;
  window.isPendingRecoveryPlanCommand = isPendingRecoveryPlanCommand;
  window.pendingRecoveryPlanHistoryLine = pendingRecoveryPlanHistoryLine;
})();
