/* global refreshAll, refreshCurrentOutputStatus */
(function () {
  let lastCompletedRows = [];
  let lastCompletedPayload = {};
  let lastFinalLibraryPromotionStatus = {};
  let lastCompletedPendingPayload = {};
  let lastCompletedPendingProofRows = [];
  let lastPublishReconciliationPayload = {};
  let selectedCompletedRowKey = "";
  let selectedCompletedPendingProofKey = "";
  let selectedCompletedSizeEvidenceKey = "";
  let selectedCompletedAcceptanceKey = "";
  let selectedCompletedRealMediaProofKey = "";
  let selectedCompletedFinalTrustKey = "";
  let selectedCompletedPilotEvidenceKey = "";
  let selectedCompletedRouteAgreementKey = "";
  let lastCompletedRouteAgreementRows = [];
  let selectedPublishReconciliationKey = "";
  let publishReconciliationInFlight = false;
  let lastCompletedEmptyMessage = "No completed jobs available.";
  const COMPLETED_FILTER_FIELDS = [
    "completed_at",
    "route",
    "route_label",
    "route_reason",
    "route_reason_code",
    "publish",
    "final_library_promotion_status",
    "final_library_promotion_status_label",
    "final_library_destination_path",
    "final_library_rule_label",
    "media_type",
    "lookup_title",
    "output_file",
    "output_path",
    "output_health",
    "encoder",
    "size_delta_label",
    "route_decision_summary",
    "route_evidence_lines",
    "operator_status",
    "operator_guidance",
    "review_flags",
    "consistency_status",
    "consistency_guidance",
    "consistency_issues",
    "validation_status_state",
    "validation_failure_reason",
    "validation_unavailable_reasons",
    "validation_safe_next_action",
    "expected_sidecar_path",
    "runtime_outcome_status",
    "runtime_outcome_error_code",
    "runtime_outcome_reason",
    "runtime_outcome_event_type",
  ];

  const completedEvidenceState = {
    get lastCompletedRows() { return lastCompletedRows; },
    set lastCompletedRows(value) { lastCompletedRows = value; },
    get lastCompletedPayload() { return lastCompletedPayload; },
    set lastCompletedPayload(value) { lastCompletedPayload = value; },
    get lastFinalLibraryPromotionStatus() { return lastFinalLibraryPromotionStatus; },
    set lastFinalLibraryPromotionStatus(value) { lastFinalLibraryPromotionStatus = value; },
    get lastCompletedPendingPayload() { return lastCompletedPendingPayload; },
    set lastCompletedPendingPayload(value) { lastCompletedPendingPayload = value; },
    get lastCompletedPendingProofRows() { return lastCompletedPendingProofRows; },
    set lastCompletedPendingProofRows(value) { lastCompletedPendingProofRows = value; },
    get lastPublishReconciliationPayload() { return lastPublishReconciliationPayload; },
    set lastPublishReconciliationPayload(value) { lastPublishReconciliationPayload = value; },
    get selectedCompletedPendingProofKey() { return selectedCompletedPendingProofKey; },
    set selectedCompletedPendingProofKey(value) { selectedCompletedPendingProofKey = value; },
    get selectedCompletedRowKey() { return selectedCompletedRowKey; },
    set selectedCompletedRowKey(value) { selectedCompletedRowKey = value; },
    get lastCompletedEmptyMessage() { return lastCompletedEmptyMessage; },
    set lastCompletedEmptyMessage(value) { lastCompletedEmptyMessage = value; },
    get selectedCompletedSizeEvidenceKey() { return selectedCompletedSizeEvidenceKey; },
    set selectedCompletedSizeEvidenceKey(value) { selectedCompletedSizeEvidenceKey = value; },
    get selectedCompletedAcceptanceKey() { return selectedCompletedAcceptanceKey; },
    set selectedCompletedAcceptanceKey(value) { selectedCompletedAcceptanceKey = value; },
    get selectedCompletedRealMediaProofKey() { return selectedCompletedRealMediaProofKey; },
    set selectedCompletedRealMediaProofKey(value) { selectedCompletedRealMediaProofKey = value; },
    get selectedCompletedFinalTrustKey() { return selectedCompletedFinalTrustKey; },
    set selectedCompletedFinalTrustKey(value) { selectedCompletedFinalTrustKey = value; },
    get selectedCompletedPilotEvidenceKey() { return selectedCompletedPilotEvidenceKey; },
    set selectedCompletedPilotEvidenceKey(value) { selectedCompletedPilotEvidenceKey = value; },
    get lastCompletedRouteAgreementRows() { return lastCompletedRouteAgreementRows; },
    set lastCompletedRouteAgreementRows(value) { lastCompletedRouteAgreementRows = value; },
    get selectedCompletedRouteAgreementKey() { return selectedCompletedRouteAgreementKey; },
    set selectedCompletedRouteAgreementKey(value) { selectedCompletedRouteAgreementKey = value; },
    get selectedPublishReconciliationKey() { return selectedPublishReconciliationKey; },
    set selectedPublishReconciliationKey(value) { selectedPublishReconciliationKey = value; },
    get publishReconciliationInFlight() { return publishReconciliationInFlight; },
    set publishReconciliationInFlight(value) { publishReconciliationInFlight = Boolean(value); },
  };
  const completedReviewNoop = function () {};
  let completedIntegrityStatus = completedReviewNoop;
  let completedIntegrityLines = completedReviewNoop;
  let renderCompletedIntegrity = completedReviewNoop;
  let completedWorkflowStatus = completedReviewNoop;
  let completedWorkflowLines = completedReviewNoop;
  let renderCompletedWorkflow = completedReviewNoop;
  let completedReviewRowReasons = completedReviewNoop;
  let completedReviewRows = completedReviewNoop;
  let completedReviewStatus = completedReviewNoop;
  let completedReviewBoardLines = completedReviewNoop;
  let completedReviewDigestStatus = completedReviewNoop;
  let completedReviewDigestAction = completedReviewNoop;
  let completedTableRowStatus = completedReviewNoop;
  let completedInvestigationFilterLabel = completedReviewNoop;
  let completedMatchesInvestigationFilter = completedReviewNoop;
  let completedFocusedInvestigationLabels = completedReviewNoop;
  let completedFilterVisibilityLines = completedReviewNoop;
  let completedSelectedQuickSignalLines = completedReviewNoop;
  let completedInvestigationSignalLines = completedReviewNoop;
  let renderCompletedReviewDigest = completedReviewNoop;
  let renderCompletedReviewBoard = completedReviewNoop;
  let completedSizeReviewRows = completedReviewNoop;
  let completedSizeReviewStatus = completedReviewNoop;
  let completedSizeReviewAction = completedReviewNoop;
  let completedSizeReviewLines = completedReviewNoop;
  let renderCompletedSizeReview = completedReviewNoop;
  let completedSizeEvidencePostureStatus = completedReviewNoop;
  let completedSizeEvidenceRows = completedReviewNoop;
  let completedSizeEvidenceStatus = completedReviewNoop;
  let completedSizeEvidenceSummaryLines = completedReviewNoop;
  let completedSizeEvidenceDetailLines = completedReviewNoop;
  let renderCompletedSizeEvidence = completedReviewNoop;
  let completedBreakdownStatus = completedReviewNoop;
  let completedBreakdownLines = completedReviewNoop;
  let renderCompletedBreakdown = completedReviewNoop;
  let completedRuntimeStatus = completedReviewNoop;
  let completedRuntimeLines = completedReviewNoop;
  let renderCompletedRuntime = completedReviewNoop;
  let completedConsistencyStatus = completedReviewNoop;
  let completedConsistencyLines = completedReviewNoop;
  let renderCompletedConsistency = completedReviewNoop;
  let completedValidationStatus = completedReviewNoop;
  let completedValidationChecklistLines = completedReviewNoop;
  let renderCompletedValidation = completedReviewNoop;
  let completedRowReviewChecklistLines = completedReviewNoop;
  let completedSelectedAtAGlanceState = completedReviewNoop;
  let completedSelectedAtAGlanceStatus = completedReviewNoop;
  let completedSelectedAtAGlanceLines = completedReviewNoop;
  let renderCompletedSelectedAtAGlance = completedReviewNoop;
  let completedRowIssueDigestLines = completedReviewNoop;
  let completedRowCombinedReviewPlanLines = completedReviewNoop;
  let completedRealMediaTraceLines = completedReviewNoop;
  let completedRowTrustSummaryLines = completedReviewNoop;
  let completedSampleValidationComparisonLines = completedReviewNoop;
  let appendCompletedPromotionCellAction = completedReviewNoop;
  let currentFinalLibraryPromotionRunId = completedReviewNoop;
  let finalLibraryPromotionActionState = completedReviewNoop;
  let finalLibraryPromotionChipState = completedReviewNoop;
  let finalLibraryPromotionStatusText = completedReviewNoop;
  let mergeFinalLibraryPromotionRows = completedReviewNoop;
  let renderCompletedPromotionActions = completedReviewNoop;
  let renderFinalLibraryPromotion = completedReviewNoop;
  let requestFinalLibraryPromotion = completedReviewNoop;
  let requestFinalLibraryPromotionPause = completedReviewNoop;
  let requestFinalLibraryPromotionResume = completedReviewNoop;
  let requestSelectedFinalLibraryPromotion = completedReviewNoop;
  let completedOpenHistoryLine = completedReviewNoop;
  let completedSelectedOpenTargetLines = completedReviewNoop;
  let isCompletedOpenCommand = completedReviewNoop;
  let rejectCompletedOpenWhileBusy = completedReviewNoop;
  let renderCompletedOpenHistory = completedReviewNoop;
  let requestCompletedOpen = completedReviewNoop;
  let setCompletedOpenBusy = completedReviewNoop;
  let getLastCompletedPayload = completedReviewNoop;
  let getLastCompletedPendingProofRows = completedReviewNoop;
  let getLastCompletedRows = completedReviewNoop;
  let getSelectedCompletedRow = completedReviewNoop;
  let renderCompletedDetail = completedReviewNoop;
  let selectCompletedRow = completedReviewNoop;
  let renderCompletedRows = completedReviewNoop;
  let renderCompletedHistoryRows = completedReviewNoop;
  const completedStatusBoardsModule = window.__completedViewStatusBoardsModule || {};
  delete window.__completedViewStatusBoardsModule;
  const completedStatusBoards = typeof completedStatusBoardsModule.createCompletedStatusBoardsModule === "function"
    ? completedStatusBoardsModule.createCompletedStatusBoardsModule({
      renderProgressBarsInto: window.renderProgressBarsInto,
      state: completedEvidenceState,
    })
    : {};
  const {
    completedCurrentRows = completedReviewNoop,
    completedMissingRows = completedReviewNoop,
    completedMetricCounts = completedReviewNoop,
    completedInventoryProgressBars = completedReviewNoop,
    renderCompletedInventoryProgress = completedReviewNoop,
    completedEmptyStateMessage = completedReviewNoop,
    completedFreshnessLine = completedReviewNoop,
    completedManifestIsAged = completedReviewNoop,
    completedFormatCounts = completedReviewNoop,
    completedListText = completedReviewNoop,
  } = completedStatusBoards;
  const completedProofNoop = function () {};
  let completedRealMediaProofRows = completedProofNoop;
  let completedRealMediaProofStatus = completedProofNoop;
  let completedRealMediaProofSummaryLines = completedProofNoop;
  let completedRealMediaProofDetailLines = completedProofNoop;
  let completedRealMediaProofPostureStatus = completedProofNoop;
  let completedPolicyAlignmentOutputEvidence = completedProofNoop;
  let completedPolicyOutputCategorySignal = completedProofNoop;
  let renderCompletedRealMediaProof = completedProofNoop;
  let completedFinalTrustRows = completedProofNoop;
  let completedFinalTrustStatus = completedProofNoop;
  let completedFinalTrustSummaryLines = completedProofNoop;
  let completedFinalTrustDetailLines = completedProofNoop;
  let completedFinalTrustPostureStatus = completedProofNoop;
  let selectCompletedFinalTrustStep = completedProofNoop;
  let renderCompletedFinalTrust = completedProofNoop;
  let completedPilotEvidencePacketRows = completedProofNoop;
  let completedPilotEvidencePacketStatus = completedProofNoop;
  let completedPilotEvidencePacketSummaryLines = completedProofNoop;
  let completedPilotEvidencePacketDetailLines = completedProofNoop;
  let completedPilotEvidencePacketMarkdownLines = completedProofNoop;
  let completedPilotEvidencePostureStatus = completedProofNoop;
  let renderCompletedPilotEvidencePacket = completedProofNoop;
  const completedEvidenceModule = window.__completedViewEvidenceModule || {};
  delete window.__completedViewEvidenceModule;
  const completedEvidence = typeof completedEvidenceModule.createCompletedEvidenceModule === "function"
    ? completedEvidenceModule.createCompletedEvidenceModule({
      apiGet: typeof apiGet === "function" ? apiGet : window.apiGet,
      appendCells: typeof appendCells === "function" ? appendCells : window.appendCells,
      byId: typeof byId === "function" ? byId : window.byId,
      clearRows: typeof clearRows === "function" ? clearRows : window.clearRows,
      commandHistoryCommandText: window.commandHistoryCommandText,
      commandHistoryIssueLevel: window.commandHistoryIssueLevel,
      commandHistoryOwnerPage: window.commandHistoryOwnerPage,
      commandHistorySuggestedAction: window.commandHistorySuggestedAction,
      completedEvidenceState,
      completedFilterFields: COMPLETED_FILTER_FIELDS,
      completedCurrentRows: (...args) => completedCurrentRows(...args),
      completedInvestigationFilterLabel: (...args) => completedInvestigationFilterLabel(...args),
      completedMatchesInvestigationFilter: (...args) => completedMatchesInvestigationFilter(...args),
      completedReviewRowReasons: (...args) => completedReviewRowReasons(...args),
      completedTableRowStatus: (...args) => completedTableRowStatus(...args),
      filterRows: typeof filterRows === "function" ? filterRows : window.filterRows,
      filterRowsByInvestigation: typeof filterRowsByInvestigation === "function" ? filterRowsByInvestigation : window.filterRowsByInvestigation,
      filterRowsByStatus: typeof filterRowsByStatus === "function" ? filterRowsByStatus : window.filterRowsByStatus,
      getCommandHistory: window.getCommandHistory,
      getSelectedCompletedRow,
      makeRowSelectable: typeof makeRowSelectable === "function" ? makeRowSelectable : window.makeRowSelectable,
      renderCompletedFinalTrust: (...args) => renderCompletedFinalTrust(...args),
      renderCompletedPilotEvidencePacket: (...args) => renderCompletedPilotEvidencePacket(...args),
      renderCompletedRealMediaProof: (...args) => renderCompletedRealMediaProof(...args),
      renderCompletedSizeEvidence: (...args) => renderCompletedSizeEvidence(...args),
      setText: typeof setText === "function" ? setText : window.setText,
      tableStatusFilterLabel: typeof tableStatusFilterLabel === "function" ? tableStatusFilterLabel : window.tableStatusFilterLabel,
      updateTableStatusLegend: typeof updateTableStatusLegend === "function" ? updateTableStatusLegend : window.updateTableStatusLegend,
    })
    : {};
  const completedEvidenceNoop = function () {};
  const {
    completedAcceptancePostureStatus = completedEvidenceNoop,
    completedAcceptanceCommandEntries = completedEvidenceNoop,
    completedAcceptanceIssueLevel = completedEvidenceNoop,
    completedAcceptanceProofRowsForItem = completedEvidenceNoop,
    completedAcceptanceSelectedOrFirst = completedEvidenceNoop,
    completedCurrentFilterScope = completedEvidenceNoop,
    completedFilterScopePosture = completedEvidenceNoop,
    completedFilterScopeEvidence = completedEvidenceNoop,
    completedFilterScopeAction = completedEvidenceNoop,
    completedFilterScopeDetailLines = completedEvidenceNoop,
    completedAcceptanceRows = completedEvidenceNoop,
    completedAcceptanceStatus = completedEvidenceNoop,
    completedAcceptanceSummaryLines = completedEvidenceNoop,
    completedAcceptanceDetailLines = completedEvidenceNoop,
    selectedCompletedAcceptanceRow = completedEvidenceNoop,
    selectCompletedAcceptanceRow = completedEvidenceNoop,
    renderCompletedOutputAcceptance = completedEvidenceNoop,
    completedRouteAgreementRouteToken = completedEvidenceNoop,
    completedRouteAgreementReason = completedEvidenceNoop,
    completedRouteAgreementQueueSourcePath = completedEvidenceNoop,
    completedRouteAgreementQueueRowLabel = completedEvidenceNoop,
    completedRouteAgreementRouteEvidenceCount = completedEvidenceNoop,
    completedRouteAgreementQueueIndexes = completedEvidenceNoop,
    completedRouteAgreementPostureStatus = completedEvidenceNoop,
    completedRouteAgreementRows = completedEvidenceNoop,
    completedRouteAgreementStatus = completedEvidenceNoop,
    completedRouteAgreementSummaryLines = completedEvidenceNoop,
    completedRouteAgreementDetailLines = completedEvidenceNoop,
    selectedCompletedRouteAgreementRow = completedEvidenceNoop,
    selectCompletedRouteAgreementRow = completedEvidenceNoop,
    renderCompletedRouteAgreement = completedEvidenceNoop,
    completedProofRows = completedEvidenceNoop,
    completedProofDrainSummaryPayload = completedEvidenceNoop,
    completedProofDrainSummaryItems = completedEvidenceNoop,
    completedProofNormalizePath = completedEvidenceNoop,
    completedProofPathLooksAbsolute = completedEvidenceNoop,
    completedProofLeaf = completedEvidenceNoop,
    completedProofFirstValue = completedEvidenceNoop,
    completedProofCompletedOutputPath = completedEvidenceNoop,
    completedProofCompletedSourcePath = completedEvidenceNoop,
    completedProofRowMissingOutput = completedEvidenceNoop,
    completedProofPendingDestinationPath = completedEvidenceNoop,
    completedProofPendingSourcePath = completedEvidenceNoop,
    completedProofPendingLocalPath = completedEvidenceNoop,
    completedProofRowKey = completedEvidenceNoop,
    completedProofRowLabel = completedEvidenceNoop,
    completedProofPendingLabel = completedEvidenceNoop,
    completedProofDrainItemLabel = completedEvidenceNoop,
    completedPendingProofSignalLabel = completedEvidenceNoop,
    completedPendingProofIsExactPathSignal = completedEvidenceNoop,
    completedPendingProofIsFinalPlacementReviewSignal = completedEvidenceNoop,
    completedPendingProofDataStatus = completedEvidenceNoop,
    completedPendingProofEvidenceText = completedEvidenceNoop,
    completedPendingProofNextAction = completedEvidenceNoop,
    completedPendingProofRowKey = completedEvidenceNoop,
    completedPendingProofSelectedRow = completedEvidenceNoop,
    completedPendingProofDetailLines = completedEvidenceNoop,
    renderCompletedPendingProofDetail = completedEvidenceNoop,
    selectCompletedPendingProofRow = completedEvidenceNoop,
    completedPendingProofRows = completedEvidenceNoop,
    completedPendingProofStatus = completedEvidenceNoop,
    completedPendingProofSummaryLines = completedEvidenceNoop,
    renderCompletedPendingProof = completedEvidenceNoop,
    publishReconciliationStatusLabel = completedEvidenceNoop,
    publishReconciliationTableStatus = completedEvidenceNoop,
    publishReconciliationRows = completedEvidenceNoop,
    publishReconciliationRowKey = completedEvidenceNoop,
    publishReconciliationSelectedRow = completedEvidenceNoop,
    publishReconciliationDetailLines = completedEvidenceNoop,
    renderPublishReconciliation = completedEvidenceNoop,
    selectPublishReconciliationRow = completedEvidenceNoop,
    setPublishReconciliationBusy = completedEvidenceNoop,
    requestPublishReconciliation = completedEvidenceNoop,
  } = completedEvidence;
  const completedProofModule = window.__completedViewProofModule || {};
  delete window.__completedViewProofModule;
  const completedProof = typeof completedProofModule.createCompletedProofModule === "function"
    ? completedProofModule.createCompletedProofModule({
      appendCells: typeof appendCells === "function" ? appendCells : window.appendCells,
      byId: typeof byId === "function" ? byId : window.byId,
      clearRows: typeof clearRows === "function" ? clearRows : window.clearRows,
      completedAcceptanceCommandEntries,
      completedAcceptanceIssueLevel,
      completedAcceptancePostureStatus,
      completedAcceptanceProofRowsForItem,
      completedAcceptanceRows,
      completedPendingProofIsExactPathSignal,
      completedPendingProofIsFinalPlacementReviewSignal,
      completedProofCompletedOutputPath,
      completedProofCompletedSourcePath,
      completedProofDrainSummaryPayload,
      completedProofRowKey,
      completedProofRowLabel,
      completedProofRowMissingOutput,
      completedSampleValidationComparisonLines: (...args) => completedSampleValidationComparisonLines(...args),
      getSelectedCompletedRow,
      makeRowSelectable: typeof makeRowSelectable === "function" ? makeRowSelectable : window.makeRowSelectable,
      setText: typeof setText === "function" ? setText : window.setText,
      state: completedEvidenceState,
      updateTableStatusLegend: typeof updateTableStatusLegend === "function" ? updateTableStatusLegend : window.updateTableStatusLegend,
    })
    : {};
  ({
    completedRealMediaProofRows = completedProofNoop,
    completedRealMediaProofStatus = completedProofNoop,
    completedRealMediaProofSummaryLines = completedProofNoop,
    completedRealMediaProofDetailLines = completedProofNoop,
    completedRealMediaProofPostureStatus = completedProofNoop,
    completedPolicyAlignmentOutputEvidence = completedProofNoop,
    completedPolicyOutputCategorySignal = completedProofNoop,
    renderCompletedRealMediaProof = completedProofNoop,
    completedFinalTrustRows = completedProofNoop,
    completedFinalTrustStatus = completedProofNoop,
    completedFinalTrustSummaryLines = completedProofNoop,
    completedFinalTrustDetailLines = completedProofNoop,
    completedFinalTrustPostureStatus = completedProofNoop,
    selectCompletedFinalTrustStep = completedProofNoop,
    renderCompletedFinalTrust = completedProofNoop,
    completedPilotEvidencePacketRows = completedProofNoop,
    completedPilotEvidencePacketStatus = completedProofNoop,
    completedPilotEvidencePacketSummaryLines = completedProofNoop,
    completedPilotEvidencePacketDetailLines = completedProofNoop,
    completedPilotEvidencePacketMarkdownLines = completedProofNoop,
    completedPilotEvidencePostureStatus = completedProofNoop,
    renderCompletedPilotEvidencePacket = completedProofNoop,
  } = completedProof);
  const completedDiagnosticsModule = window.__completedViewDiagnosticsModule || {};
  delete window.__completedViewDiagnosticsModule;
  const completedDiagnostics = typeof completedDiagnosticsModule.createCompletedDiagnosticsModule === "function"
    ? completedDiagnosticsModule.createCompletedDiagnosticsModule({
      appendDiagnosticsBridgeButton: window.appendDiagnosticsBridgeButton,
      appendDiagnosticsBridgeGroupedButtons: window.appendDiagnosticsBridgeGroupedButtons,
      byId: typeof byId === "function" ? byId : window.byId,
      requestDiagnosticsOpen: (...args) => {
        const request = typeof window.requestDiagnosticsOpen === "function"
          ? window.requestDiagnosticsOpen
          : (typeof requestDiagnosticsOpen === "function" ? requestDiagnosticsOpen : null);
        if (typeof request !== "function") return Promise.reject(new Error("requestDiagnosticsOpen is not available."));
        return request(...args);
      },
      requestDiagnosticsTail: (...args) => {
        const request = typeof window.requestDiagnosticsTail === "function"
          ? window.requestDiagnosticsTail
          : (typeof requestDiagnosticsTail === "function" ? requestDiagnosticsTail : null);
        if (typeof request !== "function") return Promise.reject(new Error("requestDiagnosticsTail is not available."));
        return request(...args);
      },
      setText: typeof setText === "function" ? setText : window.setText,
    })
    : {};
  const completedDiagnosticsNoop = function () {};
  const {
    completedDiagnosticsActionsForRow = completedDiagnosticsNoop,
    completedDiagnosticsGuidanceLines = completedDiagnosticsNoop,
    renderCompletedDiagnosticsLinks = completedDiagnosticsNoop,
    requestCompletedDiagnosticsAction = completedDiagnosticsNoop,
  } = completedDiagnostics;

  const completedReviewModule = window.__completedViewReviewModule || {};
  delete window.__completedViewReviewModule;
  const completedReview = typeof completedReviewModule.createCompletedReviewModule === "function"
    ? completedReviewModule.createCompletedReviewModule({
      appendCells: typeof appendCells === "function" ? appendCells : window.appendCells,
      byId: typeof byId === "function" ? byId : window.byId,
      clearRows: typeof clearRows === "function" ? clearRows : window.clearRows,
      completedAcceptanceProofRowsForItem,
      completedDiagnosticsActionsForRow: (...args) => completedDiagnosticsActionsForRow(...args),
      completedFilterFields: COMPLETED_FILTER_FIELDS,
      completedFormatCounts,
      completedFreshnessLine,
      completedManifestIsAged,
      completedPendingProofIsExactPathSignal,
      completedProofCompletedOutputPath,
      completedProofCompletedSourcePath,
      completedProofRowLabel,
      completedProofRowMissingOutput,
      diagnosticsBridgeRowTrustLines: typeof diagnosticsBridgeRowTrustLines === "function" ? diagnosticsBridgeRowTrustLines : window.diagnosticsBridgeRowTrustLines,
      filterRows: typeof filterRows === "function" ? filterRows : window.filterRows,
      makeRowSelectable: typeof makeRowSelectable === "function" ? makeRowSelectable : window.makeRowSelectable,
      renderCompletedDetail: (...args) => renderCompletedDetail(...args),
      renderCompletedFinalTrust: (...args) => renderCompletedFinalTrust(...args),
      renderCompletedOutputAcceptance: (...args) => renderCompletedOutputAcceptance(...args),
      renderCompletedPendingProof: (...args) => renderCompletedPendingProof(...args),
      renderCompletedPilotEvidencePacket: (...args) => renderCompletedPilotEvidencePacket(...args),
      renderCompletedRealMediaProof: (...args) => renderCompletedRealMediaProof(...args),
      renderCompletedRows: (...args) => renderCompletedRows(...args),
      selectCompletedRow: (...args) => selectCompletedRow(...args),
      setText: typeof setText === "function" ? setText : window.setText,
      state: completedEvidenceState,
      tableStatusMatchesFilter: typeof tableStatusMatchesFilter === "function" ? tableStatusMatchesFilter : window.tableStatusMatchesFilter,
      tableStatusFilterLabel: typeof tableStatusFilterLabel === "function" ? tableStatusFilterLabel : window.tableStatusFilterLabel,
      updateTableStatusLegend: typeof updateTableStatusLegend === "function" ? updateTableStatusLegend : window.updateTableStatusLegend,
    })
    : {};
  ({
    completedIntegrityStatus = completedReviewNoop,
    completedIntegrityLines = completedReviewNoop,
    renderCompletedIntegrity = completedReviewNoop,
    completedWorkflowStatus = completedReviewNoop,
    completedWorkflowLines = completedReviewNoop,
    renderCompletedWorkflow = completedReviewNoop,
    completedReviewRowReasons = completedReviewNoop,
    completedReviewRows = completedReviewNoop,
    completedReviewStatus = completedReviewNoop,
    completedReviewBoardLines = completedReviewNoop,
    completedReviewDigestStatus = completedReviewNoop,
    completedReviewDigestAction = completedReviewNoop,
    completedTableRowStatus = completedReviewNoop,
    completedInvestigationFilterLabel = completedReviewNoop,
    completedMatchesInvestigationFilter = completedReviewNoop,
    completedFocusedInvestigationLabels = completedReviewNoop,
    completedFilterVisibilityLines = completedReviewNoop,
    completedSelectedQuickSignalLines = completedReviewNoop,
    completedInvestigationSignalLines = completedReviewNoop,
    renderCompletedReviewDigest = completedReviewNoop,
    renderCompletedReviewBoard = completedReviewNoop,
    completedSizeReviewRows = completedReviewNoop,
    completedSizeReviewStatus = completedReviewNoop,
    completedSizeReviewAction = completedReviewNoop,
    completedSizeReviewLines = completedReviewNoop,
    renderCompletedSizeReview = completedReviewNoop,
    completedSizeEvidencePostureStatus = completedReviewNoop,
    completedSizeEvidenceRows = completedReviewNoop,
    completedSizeEvidenceStatus = completedReviewNoop,
    completedSizeEvidenceSummaryLines = completedReviewNoop,
    completedSizeEvidenceDetailLines = completedReviewNoop,
    renderCompletedSizeEvidence = completedReviewNoop,
    completedBreakdownStatus = completedReviewNoop,
    completedBreakdownLines = completedReviewNoop,
    renderCompletedBreakdown = completedReviewNoop,
    completedRuntimeStatus = completedReviewNoop,
    completedRuntimeLines = completedReviewNoop,
    renderCompletedRuntime = completedReviewNoop,
    completedConsistencyStatus = completedReviewNoop,
    completedConsistencyLines = completedReviewNoop,
    renderCompletedConsistency = completedReviewNoop,
    completedValidationStatus = completedReviewNoop,
    completedValidationChecklistLines = completedReviewNoop,
    renderCompletedValidation = completedReviewNoop,
    completedRowReviewChecklistLines = completedReviewNoop,
    completedSelectedAtAGlanceState = completedReviewNoop,
    completedSelectedAtAGlanceStatus = completedReviewNoop,
    completedSelectedAtAGlanceLines = completedReviewNoop,
    renderCompletedSelectedAtAGlance = completedReviewNoop,
    completedRowIssueDigestLines = completedReviewNoop,
    completedRowCombinedReviewPlanLines = completedReviewNoop,
    completedRealMediaTraceLines = completedReviewNoop,
    completedRowTrustSummaryLines = completedReviewNoop,
    completedSampleValidationComparisonLines = completedReviewNoop,
  } = completedReview);

  const completedPromotionCommandsModule = window.__completedViewPromotionCommandsModule || {};
  delete window.__completedViewPromotionCommandsModule;
  const completedPromotionCommands = typeof completedPromotionCommandsModule.createCompletedPromotionCommandsModule === "function"
    ? completedPromotionCommandsModule.createCompletedPromotionCommandsModule({
      apiPost: typeof apiPost === "function" ? apiPost : window.apiPost,
      appendCells: typeof appendCells === "function" ? appendCells : window.appendCells,
      appendCommandResult: typeof appendCommandResult === "function" ? appendCommandResult : window.appendCommandResult,
      byId: typeof byId === "function" ? byId : window.byId,
      clearRows: typeof clearRows === "function" ? clearRows : window.clearRows,
      getSelectedCompletedRow: (...args) => getSelectedCompletedRow(...args),
      refreshAll: typeof refreshAll === "function" ? refreshAll : window.refreshAll,
      refreshCurrentOutputStatus: typeof refreshCurrentOutputStatus === "function" ? refreshCurrentOutputStatus : window.refreshCurrentOutputStatus,
      renderCompletedRows: (...args) => renderCompletedRows(...args),
      selectCompletedRow: (...args) => selectCompletedRow(...args),
      setCellStatusChip: typeof setCellStatusChip === "function" ? setCellStatusChip : window.setCellStatusChip,
      setText: typeof setText === "function" ? setText : window.setText,
      state: completedEvidenceState,
    })
    : {};
  ({
    appendCompletedPromotionCellAction = completedReviewNoop,
    currentFinalLibraryPromotionRunId = completedReviewNoop,
    finalLibraryPromotionActionState = completedReviewNoop,
    finalLibraryPromotionChipState = completedReviewNoop,
    finalLibraryPromotionStatusText = completedReviewNoop,
    mergeFinalLibraryPromotionRows = completedReviewNoop,
    renderCompletedPromotionActions = completedReviewNoop,
    renderFinalLibraryPromotion = completedReviewNoop,
    requestFinalLibraryPromotion = completedReviewNoop,
    requestFinalLibraryPromotionPause = completedReviewNoop,
    requestFinalLibraryPromotionResume = completedReviewNoop,
    requestSelectedFinalLibraryPromotion = completedReviewNoop,
  } = completedPromotionCommands);

  const completedOpenActionsModule = window.__completedViewOpenActionsModule || {};
  delete window.__completedViewOpenActionsModule;
  const completedOpenActions = typeof completedOpenActionsModule.createCompletedOpenActionsModule === "function"
    ? completedOpenActionsModule.createCompletedOpenActionsModule({
      apiPost: typeof apiPost === "function" ? apiPost : window.apiPost,
      appendCommandResult: typeof appendCommandResult === "function" ? appendCommandResult : window.appendCommandResult,
      byId: typeof byId === "function" ? byId : window.byId,
      commandHistoryCompactEvidenceLine: window.commandHistoryCompactEvidenceLine,
      getSelectedCompletedRow: (...args) => getSelectedCompletedRow(...args),
      setText: typeof setText === "function" ? setText : window.setText,
    })
    : {};
  ({
    completedOpenHistoryLine = completedReviewNoop,
    completedSelectedOpenTargetLines = completedReviewNoop,
    isCompletedOpenCommand = completedReviewNoop,
    rejectCompletedOpenWhileBusy = completedReviewNoop,
    renderCompletedOpenHistory = completedReviewNoop,
    requestCompletedOpen = completedReviewNoop,
    setCompletedOpenBusy = completedReviewNoop,
  } = completedOpenActions);

  const completedSelectionModule = window.__completedViewSelectionModule || {};
  delete window.__completedViewSelectionModule;
  const completedSelection = typeof completedSelectionModule.createCompletedSelectionModule === "function"
    ? completedSelectionModule.createCompletedSelectionModule({
      completedDiagnosticsActionsForRow: (...args) => completedDiagnosticsActionsForRow(...args),
      completedInvestigationSignalLines: (...args) => completedInvestigationSignalLines(...args),
      completedRealMediaTraceLines: (...args) => completedRealMediaTraceLines(...args),
      completedRowCombinedReviewPlanLines: (...args) => completedRowCombinedReviewPlanLines(...args),
      completedRowIssueDigestLines: (...args) => completedRowIssueDigestLines(...args),
      completedRowReviewChecklistLines: (...args) => completedRowReviewChecklistLines(...args),
      completedRowTrustSummaryLines: (...args) => completedRowTrustSummaryLines(...args),
      completedSampleValidationComparisonLines: (...args) => completedSampleValidationComparisonLines(...args),
      completedSelectedAtAGlanceLines: (...args) => completedSelectedAtAGlanceLines(...args),
      completedSelectedOpenTargetLines: (...args) => completedSelectedOpenTargetLines(...args),
      completedSelectedQuickSignalLines: (...args) => completedSelectedQuickSignalLines(...args),
      diagnosticsBridgeHandoffLines: window.diagnosticsBridgeHandoffLines,
      renderCompletedDiagnosticsLinks: (...args) => renderCompletedDiagnosticsLinks(...args),
      renderCompletedPromotionActions: (...args) => renderCompletedPromotionActions(...args),
      renderCompletedRows: (...args) => renderCompletedRows(...args),
      renderCompletedSelectedAtAGlance: (...args) => renderCompletedSelectedAtAGlance(...args),
      selectedRowDetailDrawerLines: window.mediaPipelineDom?.selectedRowDetailDrawerLines,
      setText: typeof setText === "function" ? setText : window.setText,
      state: completedEvidenceState,
    })
    : {};
  ({
    getLastCompletedPayload = completedReviewNoop,
    getLastCompletedPendingProofRows = completedReviewNoop,
    getLastCompletedRows = completedReviewNoop,
    getSelectedCompletedRow = completedReviewNoop,
    renderCompletedDetail = completedReviewNoop,
    selectCompletedRow = completedReviewNoop,
  } = completedSelection);

  const completedFiltersModule = window.__completedViewFiltersModule || {};
  delete window.__completedViewFiltersModule;
  const completedFilters = typeof completedFiltersModule.createCompletedFiltersModule === "function"
    ? completedFiltersModule.createCompletedFiltersModule({
      byId: typeof byId === "function" ? byId : window.byId,
      completedCurrentRows: (...args) => completedCurrentRows(...args),
      completedFilterFields: COMPLETED_FILTER_FIELDS,
      completedInvestigationFilterLabel: (...args) => completedInvestigationFilterLabel(...args),
      completedMatchesInvestigationFilter: (...args) => completedMatchesInvestigationFilter(...args),
      completedMissingRows: (...args) => completedMissingRows(...args),
      completedReviewRows: (...args) => completedReviewRows(...args),
      completedReviewRowReasons: (...args) => completedReviewRowReasons(...args),
      completedTableRowStatus: (...args) => completedTableRowStatus(...args),
      filterRows: typeof filterRows === "function" ? filterRows : window.filterRows,
      filterRowsByInvestigation: window.filterRowsByInvestigation,
      filterRowsByStatus: window.filterRowsByStatus,
      renderCompletedRows: (...args) => renderCompletedRows(...args),
      setText: typeof setText === "function" ? setText : window.setText,
      state: completedEvidenceState,
    })
    : {};
  const {
    completedDisplayRowStatus = completedReviewNoop,
    completedFilteredRows = completedReviewNoop,
    completedRiskStatusLine = completedReviewNoop,
    completedRowsStatusLine = completedReviewNoop,
    renderCompletedReconciliationHint = completedReviewNoop,
    resetCompletedFilters = completedReviewNoop,
    resetCompletedHistoryFilters = completedReviewNoop,
  } = completedFilters;

  const completedTableModule = window.__completedViewTableModule || {};
  delete window.__completedViewTableModule;
  const completedTable = typeof completedTableModule.createCompletedTableModule === "function"
    ? completedTableModule.createCompletedTableModule({
      appendCells: typeof appendCells === "function" ? appendCells : window.appendCells,
      appendCompletedPromotionCellAction: (...args) => appendCompletedPromotionCellAction(...args),
      byId: typeof byId === "function" ? byId : window.byId,
      clearRows: typeof clearRows === "function" ? clearRows : window.clearRows,
      completedCurrentRows: (...args) => completedCurrentRows(...args),
      completedDisplayRowStatus: (...args) => completedDisplayRowStatus(...args),
      completedFilteredRows: (...args) => completedFilteredRows(...args),
      completedInvestigationFilterLabel: (...args) => completedInvestigationFilterLabel(...args),
      completedRiskStatusLine: (...args) => completedRiskStatusLine(...args),
      completedRowsStatusLine: (...args) => completedRowsStatusLine(...args),
      filterResultSummaryLines: window.filterResultSummaryLines || window.mediaPipelineDom?.filterResultSummaryLines,
      finalLibraryPromotionChipState: (...args) => finalLibraryPromotionChipState(...args),
      finalLibraryPromotionStatusText: (...args) => finalLibraryPromotionStatusText(...args),
      getSelectedCompletedRow: (...args) => getSelectedCompletedRow(...args),
      makeRowSelectable: typeof makeRowSelectable === "function" ? makeRowSelectable : window.makeRowSelectable,
      renderCompletedDetail: (...args) => renderCompletedDetail(...args),
      renderCompletedFinalTrust: (...args) => renderCompletedFinalTrust(...args),
      renderCompletedOutputAcceptance: (...args) => renderCompletedOutputAcceptance(...args),
      renderCompletedPilotEvidencePacket: (...args) => renderCompletedPilotEvidencePacket(...args),
      selectCompletedRow: (...args) => selectCompletedRow(...args),
      setCellStatusChip: typeof setCellStatusChip === "function" ? setCellStatusChip : window.setCellStatusChip,
      setText: typeof setText === "function" ? setText : window.setText,
      state: completedEvidenceState,
      updateTableStatusLegend: typeof updateTableStatusLegend === "function" ? updateTableStatusLegend : window.updateTableStatusLegend,
    })
    : {};
  ({
    renderCompletedRows = completedReviewNoop,
    renderCompletedHistoryRows = completedReviewNoop,
  } = completedTable);

  function renderCompleted(completed = {}) {
    const payload = completed && typeof completed === "object" ? completed : {};
    let rows = Array.isArray(payload.rows) ? payload.rows : [];
    if (payload.final_library_promotion && typeof payload.final_library_promotion === "object") {
      lastFinalLibraryPromotionStatus = payload.final_library_promotion;
      rows = mergeFinalLibraryPromotionRows(rows, payload.final_library_promotion);
    }
    const currentRows = completedCurrentRows(rows);
    const metricCounts = completedMetricCounts(rows);
    const commandEntries = typeof getCommandHistory === "function" ? getCommandHistory() : [];
    lastCompletedPayload = payload;
    lastCompletedRows = rows;
    lastCompletedEmptyMessage = completedEmptyStateMessage(payload, rows);
    if (selectedCompletedRowKey && !rows.some((row) => row?.row_key === selectedCompletedRowKey)) {
      selectedCompletedRowKey = "";
    }
    if (!selectedCompletedRowKey && rows.length) {
      selectedCompletedRowKey = rows[0]?.row_key || "";
    }
    setText("completed-count", String(metricCounts.current));
    setText("completed-encode-count", String(metricCounts.encoded));
    setText("completed-remux-count", String(metricCounts.remuxed));
    setText("completed-missing-count", String(metricCounts.missing));
    const warnings = Array.isArray(payload.warnings) ? payload.warnings.filter(Boolean) : [];
    const freshnessLines = window.mediaPipelineDom?.payloadFreshnessLines
      ? window.mediaPipelineDom.payloadFreshnessLines({
        payload,
        label: "Output",
        rowCount: payload.count || rows.length || 0,
        sourceLine: payload.source || payload.manifest_path ? `Manifest: ${payload.source || payload.manifest_path}` : "",
        artifactLine: completedFreshnessLine("Manifest age", payload.manifest_age_text, payload.manifest_freshness_status, payload.manifest_mtime_utc),
        readError: payload.manifest_error || payload.error || "",
        refreshAction: "Use Refresh Current Output Status to reread completed history and recheck destination file existence without accepting, deleting, or moving outputs.",
      })
      : [];
    const currentReviewCount = completedReviewRows(payload, currentRows).length;
    const summary = [
      ...freshnessLines,
      freshnessLines.length ? "" : (payload.source || payload.manifest_path ? `Manifest: ${payload.source || payload.manifest_path}` : ""),
      freshnessLines.length ? "" : completedFreshnessLine("Manifest age", payload.manifest_age_text, payload.manifest_freshness_status, payload.manifest_mtime_utc),
      `Completed history rows: ${payload.count || rows.length || 0}`,
      `Current outputs present: ${metricCounts.current}`,
      `Current encode/remux: ${metricCounts.encoded} / ${metricCounts.remuxed}`,
      `Historical outputs missing from expected destination: ${metricCounts.missing}`,
      `Rows needing review: ${completedReviewRows(payload, rows).length}`,
      `Rows over +5% output growth: ${payload.size_growth_over_5_count || 0}`,
      payload.operator_status_counts ? `Operator statuses: ${completedFormatCounts(payload.operator_status_counts)}` : "",
      payload.operator_severity_counts ? `Operator severities: ${completedFormatCounts(payload.operator_severity_counts)}` : "",
      payload.operator_trust_state_counts ? `Backend trust states: ${completedFormatCounts(payload.operator_trust_state_counts)}` : "",
      payload.available_open_target_counts ? `Backend open targets from available_open_target_counts: ${completedFormatCounts(payload.available_open_target_counts)}` : "",
      payload.total_output_size_text ? `Loaded output size: ${payload.total_output_size_text}` : "",
      ...warnings,
      !rows.length ? lastCompletedEmptyMessage : "",
    ].filter(Boolean);
    setText("completed-summary", summary.join("\n") || payload.error || "No completed history issues loaded.");
    setText("completed-current-summary", [
      `Current outputs present at expected destination: ${metricCounts.current}`,
      `Current encoded/remuxed: ${metricCounts.encoded} / ${metricCounts.remuxed}`,
      `Current rows needing review: ${currentReviewCount}`,
      `Completed history rows not currently present: ${metricCounts.missing}`,
      "Current table rule: a row appears here once per expected output path when the completed output is still present at that destination.",
      "Refresh Current Output Status rereads the completed manifest and rechecks output existence; it does not accept, delete, rerun, drain, publish, or move media.",
    ].join("\n"));
    renderCompletedReconciliationHint(payload, rows);
    renderCompletedInventoryProgress(payload);
    renderCompletedIntegrity(payload, rows);
    renderCompletedBreakdown(payload, rows);
    renderCompletedRuntime(payload, rows);
    renderCompletedConsistency(payload, rows);
    renderCompletedValidation(payload, rows);
    renderCompletedWorkflow(payload, rows);
    renderCompletedReviewBoard(payload, rows);
    renderCompletedReviewDigest(payload, rows);
    renderCompletedPendingProof(payload, rows, lastCompletedPendingPayload);
    renderCompletedSizeReview(payload, rows);
    renderCompletedSizeEvidence(payload, rows, lastCompletedPendingProofRows);
    renderCompletedOutputAcceptance(payload, rows, lastCompletedPendingProofRows, commandEntries);
    renderCompletedRouteAgreement(
      payload,
      rows,
      typeof window.getLastQueuePayload === "function" ? window.getLastQueuePayload() : {},
      typeof window.getLastQueueRows === "function" ? window.getLastQueueRows() : []
    );
    renderCompletedRealMediaProof(payload, rows, lastCompletedPendingProofRows, lastCompletedPendingPayload, commandEntries);
    renderCompletedFinalTrust(payload, rows, lastCompletedPendingProofRows, lastCompletedPendingPayload, commandEntries);
    renderCompletedPilotEvidencePacket(payload, rows, lastCompletedPendingProofRows, lastCompletedPendingPayload, commandEntries);
    renderPublishReconciliation(lastPublishReconciliationPayload);
    renderCompletedDetail(getSelectedCompletedRow());
    renderCompletedRows();
    renderCompletedOpenHistory(commandEntries);
  }

  function completedEvidencePacketText() {
    const node = byId("completed-pilot-evidence-markdown");
    return node ? String(node.textContent || "").trim() : "";
  }

  async function copyCompletedEvidencePacket() {
    const text = completedEvidencePacketText();
    if (!text || text === "No copyable pilot evidence packet loaded.") {
      setText("completed-copy-evidence-status", "No evidence packet text is available to copy.");
      return false;
    }
    try {
      if (navigator.clipboard?.writeText) {
        await navigator.clipboard.writeText(text);
      } else {
        const textarea = document.createElement("textarea");
        textarea.value = text;
        textarea.setAttribute("readonly", "readonly");
        textarea.style.position = "fixed";
        textarea.style.left = "-9999px";
        document.body.appendChild(textarea);
        textarea.select();
        const copied = document.execCommand("copy");
        document.body.removeChild(textarea);
        if (!copied) throw new Error("clipboard command returned false");
      }
      setText("completed-copy-evidence-status", "Copied evidence packet. This did not append evidence, save settings, publish, drain, rerun, rename, or touch media.");
      return true;
    } catch (error) {
      const message = error?.message || String(error);
      setText("completed-copy-evidence-status", `Copy failed: ${message}. Select the packet text manually if needed.`);
      return false;
    }
  }

  /**
   * Public namespace for the Completed page module.
   * Prefer this namespace from new code; flat window.* exports are transitional compatibility aliases when present.
   */
  window.mediaPipelineCompletedView = {
    renderCompleted,
    renderCompletedInventoryProgress,
    completedInventoryProgressBars,
    completedCurrentRows,
    completedMissingRows,
    completedMetricCounts,
    finalLibraryPromotionActionState,
    renderCompletedPromotionActions,
    renderFinalLibraryPromotion,
    requestFinalLibraryPromotion,
    requestSelectedFinalLibraryPromotion,
    requestFinalLibraryPromotionPause,
    requestFinalLibraryPromotionResume,
    currentFinalLibraryPromotionRunId,
    renderCompletedRows,
    renderCompletedHistoryRows,
    resetCompletedFilters,
    resetCompletedHistoryFilters,
    renderCompletedDetail,
    renderCompletedIntegrity,
    renderCompletedBreakdown,
    renderCompletedRuntime,
    renderCompletedConsistency,
    renderCompletedValidation,
    renderCompletedWorkflow,
    renderCompletedReviewBoard,
    renderCompletedSizeReview,
    completedIntegrityStatus,
    completedIntegrityLines,
    completedBreakdownStatus,
    completedBreakdownLines,
    completedRuntimeStatus,
    completedRuntimeLines,
    completedConsistencyStatus,
    completedConsistencyLines,
    completedValidationStatus,
    completedValidationChecklistLines,
    completedWorkflowStatus,
    completedWorkflowLines,
    completedReviewStatus,
    completedReviewBoardLines,
    completedTableRowStatus,
    completedReviewRows,
    renderCompletedReviewDigest,
    completedReviewDigestStatus,
    completedReviewDigestAction,
    completedListText,
    completedSelectedOpenTargetLines,
    completedSizeReviewRows,
    completedSizeReviewStatus,
    completedSizeReviewLines,
    completedSizeReviewAction,
    renderCompletedSizeEvidence,
    completedSizeEvidenceRows,
    completedSizeEvidenceStatus,
    completedSizeEvidenceSummaryLines,
    completedSizeEvidenceDetailLines,
    completedSizeEvidencePostureStatus,
    renderCompletedRealMediaProof,
    completedRealMediaProofRows,
    completedRealMediaProofStatus,
    completedRealMediaProofSummaryLines,
    completedRealMediaProofDetailLines,
    completedRealMediaProofPostureStatus,
    completedPolicyAlignmentOutputEvidence,
    completedPolicyOutputCategorySignal,
    renderCompletedFinalTrust,
    completedFinalTrustRows,
    completedFinalTrustStatus,
    completedFinalTrustSummaryLines,
    completedFinalTrustDetailLines,
    completedFinalTrustPostureStatus,
    selectCompletedFinalTrustStep,
    renderCompletedPilotEvidencePacket,
    completedPilotEvidencePacketRows,
    completedPilotEvidencePacketStatus,
    completedPilotEvidencePacketSummaryLines,
    completedPilotEvidencePacketDetailLines,
    completedPilotEvidencePacketMarkdownLines,
    completedPilotEvidencePostureStatus,
    renderCompletedOutputAcceptance,
    completedAcceptanceRows,
    completedAcceptanceStatus,
    completedAcceptanceSummaryLines,
    completedAcceptanceDetailLines,
    completedAcceptancePostureStatus,
    completedCurrentFilterScope,
    completedFilterScopePosture,
    completedFilterScopeEvidence,
    completedFilterScopeAction,
    completedFilterScopeDetailLines,
    renderCompletedRouteAgreement,
    completedRouteAgreementRows,
    completedRouteAgreementStatus,
    completedRouteAgreementSummaryLines,
    completedRouteAgreementDetailLines,
    completedRouteAgreementPostureStatus,
    completedRouteAgreementRouteToken,
    completedRouteAgreementReason,
    renderCompletedPendingProof,
    completedPendingProofRows,
    completedPendingProofStatus,
    completedPendingProofSummaryLines,
    completedPendingProofSignalLabel,
    completedPendingProofIsExactPathSignal,
    completedPendingProofIsFinalPlacementReviewSignal,
    completedPendingProofDataStatus,
    completedPendingProofEvidenceText,
    completedPendingProofNextAction,
    completedPendingProofRowKey,
    completedPendingProofDetailLines,
    renderCompletedPendingProofDetail,
    selectCompletedPendingProofRow,
    renderPublishReconciliation,
    requestPublishReconciliation,
    publishReconciliationRows,
    publishReconciliationDetailLines,
    publishReconciliationRowKey,
    selectPublishReconciliationRow,
    completedProofRowMissingOutput,
    completedRowReviewChecklistLines,
    completedRowIssueDigestLines,
    completedSelectedQuickSignalLines,
    completedSelectedAtAGlanceState,
    completedSelectedAtAGlanceStatus,
    completedSelectedAtAGlanceLines,
    renderCompletedSelectedAtAGlance,
    completedFilterVisibilityLines,
    completedFocusedInvestigationLabels,
    completedInvestigationSignalLines,
    completedRealMediaTraceLines,
    completedRowTrustSummaryLines,
    completedSampleValidationComparisonLines,
    completedDiagnosticsActionsForRow,
    completedDiagnosticsGuidanceLines,
    renderCompletedDiagnosticsLinks,
    requestCompletedDiagnosticsAction,
    completedFormatCounts,
    completedFreshnessLine,
    completedManifestIsAged,
    completedEmptyStateMessage,
    selectCompletedRow,
    getSelectedCompletedRow,
    getLastCompletedPayload,
    getLastCompletedRows,
    getLastCompletedPendingProofRows,
    setCompletedOpenBusy,
    rejectCompletedOpenWhileBusy,
    requestCompletedOpen,
    isCompletedOpenCommand,
    completedOpenHistoryLine,
    renderCompletedOpenHistory,
    completedRiskStatusLine,
    renderCompletedReconciliationHint,
    completedEvidencePacketText,
    copyCompletedEvidencePacket,
  };
  window.renderCompleted = renderCompleted;
  window.resetCompletedFilters = resetCompletedFilters;
  window.resetCompletedHistoryFilters = resetCompletedHistoryFilters;
  window.renderCompletedDetail = renderCompletedDetail;
  window.renderCompletedIntegrity = renderCompletedIntegrity;
  window.renderCompletedBreakdown = renderCompletedBreakdown;
  window.renderCompletedRuntime = renderCompletedRuntime;
  window.renderCompletedConsistency = renderCompletedConsistency;
  window.renderCompletedValidation = renderCompletedValidation;
  window.renderCompletedWorkflow = renderCompletedWorkflow;
  window.renderCompletedReviewBoard = renderCompletedReviewBoard;
  window.renderCompletedSizeReview = renderCompletedSizeReview;
  window.renderCompletedPendingProof = renderCompletedPendingProof;
  window.completedIntegrityStatus = completedIntegrityStatus;
  window.completedIntegrityLines = completedIntegrityLines;
  window.completedBreakdownStatus = completedBreakdownStatus;
  window.completedBreakdownLines = completedBreakdownLines;
  window.completedRuntimeStatus = completedRuntimeStatus;
  window.completedRuntimeLines = completedRuntimeLines;
  window.completedConsistencyStatus = completedConsistencyStatus;
  window.completedConsistencyLines = completedConsistencyLines;
  window.completedValidationStatus = completedValidationStatus;
  window.completedValidationChecklistLines = completedValidationChecklistLines;
  window.completedWorkflowStatus = completedWorkflowStatus;
  window.completedWorkflowLines = completedWorkflowLines;
  window.completedReviewStatus = completedReviewStatus;
  window.completedReviewBoardLines = completedReviewBoardLines;
  window.completedReviewRows = completedReviewRows;
  window.renderCompletedReviewDigest = renderCompletedReviewDigest;
  window.completedReviewDigestStatus = completedReviewDigestStatus;
  window.completedReviewDigestAction = completedReviewDigestAction;
  window.completedSizeReviewRows = completedSizeReviewRows;
  window.completedSizeReviewStatus = completedSizeReviewStatus;
  window.completedSizeReviewLines = completedSizeReviewLines;
  window.completedSizeReviewAction = completedSizeReviewAction;
  window.renderCompletedSizeEvidence = renderCompletedSizeEvidence;
  window.completedSizeEvidenceRows = completedSizeEvidenceRows;
  window.completedSizeEvidenceStatus = completedSizeEvidenceStatus;
  window.completedSizeEvidenceSummaryLines = completedSizeEvidenceSummaryLines;
  window.completedSizeEvidenceDetailLines = completedSizeEvidenceDetailLines;
  window.completedSizeEvidencePostureStatus = completedSizeEvidencePostureStatus;
  window.renderCompletedRealMediaProof = renderCompletedRealMediaProof;
  window.completedRealMediaProofStatus = completedRealMediaProofStatus;
  window.completedRealMediaProofSummaryLines = completedRealMediaProofSummaryLines;
  window.completedRealMediaProofDetailLines = completedRealMediaProofDetailLines;
  window.completedRealMediaProofPostureStatus = completedRealMediaProofPostureStatus;
  window.completedPolicyAlignmentOutputEvidence = completedPolicyAlignmentOutputEvidence;
  window.completedPolicyOutputCategorySignal = completedPolicyOutputCategorySignal;
  window.completedFinalTrustStatus = completedFinalTrustStatus;
  window.completedFinalTrustSummaryLines = completedFinalTrustSummaryLines;
  window.completedFinalTrustDetailLines = completedFinalTrustDetailLines;
  window.completedFinalTrustPostureStatus = completedFinalTrustPostureStatus;
  window.selectCompletedFinalTrustStep = selectCompletedFinalTrustStep;
  window.renderCompletedPilotEvidencePacket = renderCompletedPilotEvidencePacket;
  window.completedPilotEvidencePacketRows = completedPilotEvidencePacketRows;
  window.completedPilotEvidencePacketStatus = completedPilotEvidencePacketStatus;
  window.completedPilotEvidencePacketSummaryLines = completedPilotEvidencePacketSummaryLines;
  window.completedPilotEvidencePacketDetailLines = completedPilotEvidencePacketDetailLines;
  window.completedPilotEvidencePacketMarkdownLines = completedPilotEvidencePacketMarkdownLines;
  window.completedPilotEvidencePostureStatus = completedPilotEvidencePostureStatus;
  window.renderCompletedOutputAcceptance = renderCompletedOutputAcceptance;
  window.completedAcceptanceRows = completedAcceptanceRows;
  window.completedAcceptanceStatus = completedAcceptanceStatus;
  window.completedAcceptanceSummaryLines = completedAcceptanceSummaryLines;
  window.completedAcceptanceDetailLines = completedAcceptanceDetailLines;
  window.completedAcceptancePostureStatus = completedAcceptancePostureStatus;
  window.completedCurrentFilterScope = completedCurrentFilterScope;
  window.completedFilterScopePosture = completedFilterScopePosture;
  window.completedFilterScopeEvidence = completedFilterScopeEvidence;
  window.completedFilterScopeAction = completedFilterScopeAction;
  window.completedFilterScopeDetailLines = completedFilterScopeDetailLines;
  window.renderCompletedRouteAgreement = renderCompletedRouteAgreement;
  window.completedRouteAgreementRows = completedRouteAgreementRows;
  window.completedRouteAgreementStatus = completedRouteAgreementStatus;
  window.completedRouteAgreementSummaryLines = completedRouteAgreementSummaryLines;
  window.completedRouteAgreementDetailLines = completedRouteAgreementDetailLines;
  window.completedRouteAgreementPostureStatus = completedRouteAgreementPostureStatus;
  window.completedRouteAgreementRouteToken = completedRouteAgreementRouteToken;
  window.completedRouteAgreementReason = completedRouteAgreementReason;
  window.completedPendingProofRows = completedPendingProofRows;
  window.completedPendingProofStatus = completedPendingProofStatus;
  window.completedPendingProofSummaryLines = completedPendingProofSummaryLines;
  window.completedPendingProofSignalLabel = completedPendingProofSignalLabel;
  window.completedPendingProofIsExactPathSignal = completedPendingProofIsExactPathSignal;
  window.completedPendingProofIsFinalPlacementReviewSignal = completedPendingProofIsFinalPlacementReviewSignal;
  window.completedPendingProofDataStatus = completedPendingProofDataStatus;
  window.completedPendingProofEvidenceText = completedPendingProofEvidenceText;
  window.completedPendingProofNextAction = completedPendingProofNextAction;
  window.completedPendingProofRowKey = completedPendingProofRowKey;
  window.completedPendingProofDetailLines = completedPendingProofDetailLines;
  window.renderCompletedPendingProofDetail = renderCompletedPendingProofDetail;
  window.selectCompletedPendingProofRow = selectCompletedPendingProofRow;
  window.renderPublishReconciliation = renderPublishReconciliation;
  window.publishReconciliationRows = publishReconciliationRows;
  window.publishReconciliationDetailLines = publishReconciliationDetailLines;
  window.publishReconciliationRowKey = publishReconciliationRowKey;
  window.selectPublishReconciliationRow = selectPublishReconciliationRow;
  window.completedProofRowMissingOutput = completedProofRowMissingOutput;
  window.completedRowReviewChecklistLines = completedRowReviewChecklistLines;
  window.completedRowIssueDigestLines = completedRowIssueDigestLines;
  window.completedSelectedQuickSignalLines = completedSelectedQuickSignalLines;
  window.completedSelectedAtAGlanceState = completedSelectedAtAGlanceState;
  window.completedSelectedAtAGlanceStatus = completedSelectedAtAGlanceStatus;
  window.completedSelectedAtAGlanceLines = completedSelectedAtAGlanceLines;
  window.renderCompletedSelectedAtAGlance = renderCompletedSelectedAtAGlance;
  window.completedFilterVisibilityLines = completedFilterVisibilityLines;
  window.completedFocusedInvestigationLabels = completedFocusedInvestigationLabels;
  window.completedInvestigationSignalLines = completedInvestigationSignalLines;
  window.completedRealMediaTraceLines = completedRealMediaTraceLines;
  window.completedRowTrustSummaryLines = completedRowTrustSummaryLines;
  window.completedSampleValidationComparisonLines = completedSampleValidationComparisonLines;
  window.completedDiagnosticsActionsForRow = completedDiagnosticsActionsForRow;
  window.completedDiagnosticsGuidanceLines = completedDiagnosticsGuidanceLines;
  window.renderCompletedDiagnosticsLinks = renderCompletedDiagnosticsLinks;
  window.requestCompletedDiagnosticsAction = requestCompletedDiagnosticsAction;
  window.completedFormatCounts = completedFormatCounts;
  window.completedFreshnessLine = completedFreshnessLine;
  window.completedManifestIsAged = completedManifestIsAged;
  window.selectCompletedRow = selectCompletedRow;
  window.getSelectedCompletedRow = getSelectedCompletedRow;
  window.getLastCompletedPayload = getLastCompletedPayload;
  window.getLastCompletedRows = getLastCompletedRows;
  window.getLastCompletedPendingProofRows = getLastCompletedPendingProofRows;
  window.requestCompletedOpen = requestCompletedOpen;
  window.renderCompletedOpenHistory = renderCompletedOpenHistory;
  window.copyCompletedEvidencePacket = copyCompletedEvidencePacket;
})();
