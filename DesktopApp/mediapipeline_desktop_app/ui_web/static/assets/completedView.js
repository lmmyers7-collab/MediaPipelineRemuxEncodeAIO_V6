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
  let finalLibraryPromotionCommandInFlight = false;
  let lastCompletedEmptyMessage = "No completed jobs available.";
  let completedOpenInFlight = false;
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

  function setCompletedOpenBusy(isBusy) {
    completedOpenInFlight = Boolean(isBusy);
    document.querySelectorAll("[data-open-completed]").forEach((button) => {
      button.disabled = completedOpenInFlight;
    });
  }

  function rejectCompletedOpenWhileBusy() {
    if (!completedOpenInFlight) return false;
    const result = {
      command: "completed.open",
      ok: false,
      severity: "warning",
      message: "Another completed open command is already in progress.",
    };
    if (typeof appendCommandResult === "function") appendCommandResult(result);
    setText("completed-open-status", result.message);
    return true;
  }

  function completedCurrentOutputIdentity(item) {
    const candidates = [
      item?.output_path,
      item?.manifest_output_path,
      item?.final_library_source_path,
    ];
    for (const candidate of candidates) {
      const text = String(candidate || "").trim();
      if (text) return text.replace(/\\/g, "/").replace(/\/+/g, "/").toLowerCase();
    }
    return "";
  }

  function completedCurrentRows(rows = lastCompletedRows) {
    const seen = new Set();
    const currentRows = [];
    (Array.isArray(rows) ? rows : []).forEach((row) => {
      if (row?.output_exists === false) return;
      const identity = completedCurrentOutputIdentity(row);
      if (identity) {
        if (seen.has(identity)) return;
        seen.add(identity);
      }
      currentRows.push(row);
    });
    return currentRows;
  }

  function completedMissingRows(rows = lastCompletedRows) {
    return (Array.isArray(rows) ? rows : []).filter((row) => row?.output_exists === false && !row?.promoted_cleaned);
  }

  function completedMetricCounts(rows = lastCompletedRows) {
    const currentRows = completedCurrentRows(rows);
    return {
      current: currentRows.length,
      encoded: currentRows.filter((row) => String(row?.route || "").startsWith("encode")).length,
      remuxed: currentRows.filter((row) => String(row?.route || "") === "remux").length,
      missing: completedMissingRows(rows).length,
    };
  }

  function finalLibraryPromotionItemsByKey(status = lastFinalLibraryPromotionStatus) {
    const payload = status && typeof status === "object" ? status : {};
    const items = Array.isArray(payload.items) ? payload.items : Array.isArray(payload.item_rows) ? payload.item_rows : [];
    const byKey = {};
    items.forEach((item) => {
      if (item?.row_key) byKey[item.row_key] = item;
    });
    return byKey;
  }

  function mergeFinalLibraryPromotionRows(rows, status = lastFinalLibraryPromotionStatus) {
    const byKey = finalLibraryPromotionItemsByKey(status);
    return (Array.isArray(rows) ? rows : []).map((row) => {
      const item = byKey[row?.row_key || ""];
      return item ? { ...row, ...item } : row;
    });
  }

  function finalLibraryPromotionStatusText(item = {}) {
    if (item.promoted_cleaned) return "✓ Promoted + cleaned";
    if (item.promoted) return "✓ Promoted";
    if (item.promoting) return "Promoting";
    if (item.paused) return "Paused";
    if (item.promotion_failed) return "Failed";
    if (item.ready_for_promotion) return "✓ Ready";
    if (item.no_destination_rule) return "No Destination Rule";
    if (item.destination_offline) return "Destination Offline";
    return item.final_library_promotion_status_label || "";
  }

  function finalLibraryPromotionChipState(item = {}) {
    if (item.promoted || item.promoted_cleaned) return "success";
    if (item.ready_for_promotion || item.promoting) return "ready";
    if (item.paused || item.destination_offline || item.no_destination_rule) return "warning";
    if (item.promotion_failed) return "error";
    return "unknown";
  }

  function finalLibraryPromotionActionState(item = {}) {
    const enabled = Boolean(lastFinalLibraryPromotionStatus?.enabled);
    if (!item) return { available: false, reason: "Select a completed output first." };
    if (finalLibraryPromotionCommandInFlight) return { available: false, reason: "A promotion command is already in progress." };
    if (!enabled) return { available: false, reason: "Final Library Promotion is disabled in Settings." };
    if (finalLibraryPromotionRunActive(lastFinalLibraryPromotionStatus)) return { available: false, reason: "A final-library promotion run is already active." };
    if (item.promoted || item.promoted_cleaned) return { available: false, reason: "This output has already been promoted." };
    if (item.output_exists === false) return { available: false, reason: "The reviewed output is not present at the promotion source location." };
    if (item.no_destination_rule) return { available: false, reason: "No final-library destination rule is configured for this output." };
    if (item.destination_offline) return { available: false, reason: "The configured final-library destination is offline." };
    if (!item.final_library_destination_path) return { available: false, reason: "No final-library destination path is configured for this output." };
    if (!item.ready_for_promotion) return { available: false, reason: "This output is not currently marked ready for final-library promotion." };
    if (!item.row_key) return { available: false, reason: "This completed output has no backend row key." };
    return { available: true, reason: "Promote this reviewed file to its final destination." };
  }

  function finalLibraryPromotionConfirmMessage(rowCount) {
    const count = Number(rowCount || 0);
    if (count === 1) {
      return "Promote this file to its final destination?\n\nThis means you have reviewed it and are ready for it to be delivered.";
    }
    return "Promote these files to their final destination?\n\nThis means you have reviewed them and are ready for them to be delivered.";
  }

  function shouldConfirmFinalLibraryPromotion(rowCount) {
    if (typeof window.confirm !== "function") return true;
    return window.confirm(finalLibraryPromotionConfirmMessage(rowCount));
  }

  function createCompletedPromotionButton(item = {}) {
    const action = finalLibraryPromotionActionState(item);
    if (!action.available) return null;
    const button = document.createElement("button");
    button.type = "button";
    button.className = "secondary-button completed-row-promotion-button";
    button.textContent = "Promote";
    button.title = "Promote this reviewed file to its final destination after confirmation.";
    button.dataset.completedPromoteRowKey = item.row_key || "";
    button.addEventListener("click", (event) => {
      event.preventDefault();
      event.stopPropagation();
      selectCompletedRow(item);
      requestSelectedFinalLibraryPromotion(item);
    });
    return button;
  }

  function appendCompletedPromotionCellAction(cell, item = {}) {
    if (!cell) return;
    const button = createCompletedPromotionButton(item);
    if (!button) return;
    cell.classList.add("completed-promotion-cell");
    cell.appendChild(button);
  }

  function renderCompletedPromotionActions(item = getSelectedCompletedRow()) {
    const action = finalLibraryPromotionActionState(item);
    document.querySelectorAll("[data-completed-promote-selected]").forEach((button) => {
      button.disabled = !action.available;
      button.setAttribute("aria-disabled", String(!action.available));
      button.textContent = "Promote Selected File";
      button.title = action.reason;
    });
  }

  function finalLibraryPromotionActiveRun(status = lastFinalLibraryPromotionStatus) {
    const active = status?.active_run && typeof status.active_run === "object" ? status.active_run : {};
    return active?.run_id ? active : {};
  }

  function finalLibraryPromotionRunActive(status = lastFinalLibraryPromotionStatus) {
    const active = finalLibraryPromotionActiveRun(status);
    const state = String(active.status || "").toLowerCase();
    return Boolean(active.run_id && ["running", "pausing", "paused"].includes(state));
  }

  function renderFinalLibraryPromotion(status = {}) {
    const payload = status && typeof status === "object" ? status : {};
    lastFinalLibraryPromotionStatus = payload;
    if (lastCompletedRows.length) {
      lastCompletedRows = mergeFinalLibraryPromotionRows(lastCompletedRows, payload);
    }
    const counts = payload.counts && typeof payload.counts === "object" ? payload.counts : {};
    const active = finalLibraryPromotionActiveRun(payload);
    const activeStatus = String(active.status || "").toLowerCase();
    const enabled = Boolean(payload.enabled);
    const eligible = Number(counts.eligible || 0);
    const warnings = Array.isArray(payload.warnings) ? payload.warnings.filter(Boolean) : [];
    const statusText = active.run_id
      ? `${active.status || "active"} / ${Number(active.completed_count || 0)} of ${Number(active.eligible_count || eligible || 0)}`
      : enabled
        ? `${eligible} ready`
        : "Disabled";
    setText("final-library-promotion-status", statusText);
    setText("final-library-promotion-summary", [
      `Enabled: ${enabled ? "yes" : "no"}`,
      `Verification: ${payload.verification_mode || "cautious"}`,
      `Cleanup after verified: ${payload.cleanup_after_verified ? "yes" : "no"}`,
      `Overwrite existing: ${payload.overwrite_existing ? "yes - destructive" : "no"}`,
      `Rows: ${Number(counts.total || 0)} total; ${eligible} ready; ${Number(counts.no_destination_rule || 0)} no rule; ${Number(counts.destination_offline || 0)} offline; ${Number(counts.promoted || 0)} promoted; ${Number(counts.promoted_cleaned || 0)} promoted + cleaned`,
      active.run_id ? `Active run: ${active.run_id}; status=${active.status || ""}; pause=${active.pause_state || ""}; consecutive failures=${Number(active.consecutive_failures || 0)}` : "Active run: none",
      active.stop_reason ? `Stop reason: ${active.stop_reason}` : "",
      payload.publish_root ? `Publish root: ${payload.publish_root}` : "",
      payload.evidence_root ? `Evidence: ${payload.evidence_root}` : "",
      ...warnings,
    ].filter(Boolean).join("\n"));

    const promoteButton = byId("final-library-promote-button");
    const pauseButton = byId("final-library-pause-button");
    const resumeButton = byId("final-library-resume-button");
    if (promoteButton) {
      promoteButton.disabled = finalLibraryPromotionCommandInFlight || !enabled || finalLibraryPromotionRunActive(payload) || eligible <= 0;
      promoteButton.title = promoteButton.disabled
        ? (enabled ? "No eligible reviewed files are ready for final-library promotion, or a promotion run is active." : "Final Library Promotion is disabled in Settings.")
        : `Promote ${eligible} reviewed file${eligible === 1 ? "" : "s"} to final-library destinations after confirmation.`;
    }
    if (pauseButton) pauseButton.disabled = finalLibraryPromotionCommandInFlight || !(active.run_id && ["running", "pausing"].includes(activeStatus));
    if (resumeButton) resumeButton.disabled = finalLibraryPromotionCommandInFlight || !(active.run_id && activeStatus === "paused");

    const tbody = byId("final-library-promotion-rows");
    const items = Array.isArray(payload.items) ? payload.items : Array.isArray(payload.item_rows) ? payload.item_rows : [];
    if (!items.length) {
      clearRows(tbody, 3, "No final library promotion rows loaded.");
    } else {
      tbody.replaceChildren();
      items.slice(0, 40).forEach((item) => {
        const tr = document.createElement("tr");
        appendCells(tr, [
          finalLibraryPromotionStatusText(item),
          item.lookup_title || item.output_file || "",
          item.final_library_destination_path || "",
        ]);
        const statusCell = tr.querySelector("td");
        if (typeof setCellStatusChip === "function") {
          setCellStatusChip(statusCell, finalLibraryPromotionStatusText(item), finalLibraryPromotionChipState(item));
        }
        tbody.appendChild(tr);
      });
    }
    renderCompletedPromotionActions(getSelectedCompletedRow());
    window.mediaPipelineAppHome?.renderHomePromotionEntry?.(payload);
    renderCompletedRows();
  }

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
  const {
    renderCompletedRows = completedReviewNoop,
    renderCompletedHistoryRows = completedReviewNoop,
  } = completedTable;

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

  function completedInventoryProgressBars(completed) {
    const payload = completed && typeof completed === "object" ? completed : {};
    const progress = payload.inventory_progress && typeof payload.inventory_progress === "object" ? payload.inventory_progress : {};
    if (Array.isArray(progress.progress_bars)) return progress.progress_bars.filter(Boolean);
    if (Array.isArray(payload.progress_bars)) return payload.progress_bars.filter(Boolean);
    return [];
  }

  function renderCompletedInventoryProgress(completed) {
    if (typeof renderProgressBarsInto !== "function") return;
    const payload = completed && typeof completed === "object" ? completed : {};
    const progress = payload.inventory_progress && typeof payload.inventory_progress === "object" ? payload.inventory_progress : {};
    renderProgressBarsInto("completed-inventory-progress-bars", completedInventoryProgressBars(payload), progress, "No completed inventory progress loaded.");
  }

  function completedEmptyStateMessage(completed, rows) {
    const rowList = Array.isArray(rows) ? rows : [];
    if (completed?.error) {
      return `Completed history unavailable: ${completed.error}. Open Diagnostics > Completed Manifest and Run Logs.`;
    }
    const warnings = Array.isArray(completed?.warnings) ? completed.warnings.filter(Boolean) : [];
    if (warnings.length && !rowList.length) {
      return `No completed history rows. Warning: ${warnings[0]}`;
    }
    if (!completed?.manifest_exists && !completed?.source && !completed?.manifest_path) {
      return "No completed history rows. This is normal before the first successful job; otherwise open Diagnostics > Completed Manifest.";
    }
    if (!rowList.length) {
      return "No completed history rows. Check Run Logs and Completed Manifest before reprocessing anything that appears missing.";
    }
    return "No completed jobs available.";
  }

  function completedFreshnessLine(label, ageText, status, timestamp) {
    const parts = [];
    if (ageText) parts.push(ageText);
    if (status) parts.push(status);
    if (timestamp) parts.push(timestamp);
    return `${label}: ${parts.join(" / ") || "not reported"}`;
  }

  function completedManifestIsAged(completed) {
    const status = String(completed?.manifest_freshness_status || "").trim().toLowerCase();
    return Boolean(status && ["aged", "old", "stale"].some((token) => status.includes(token)));
  }

  function completedFormatCounts(value) {
    const entries = value && typeof value === "object" ? Object.entries(value) : [];
    if (!entries.length) return "none";
    return entries.map(([key, count]) => `${key || "unknown"}=${count}`).join(", ");
  }

  function completedListText(value) {
    if (Array.isArray(value)) return value.filter(Boolean).join(", ") || "none";
    return value ? String(value) : "none";
  }

  function completedSelectedOpenTargetLines(item) {
    if (!item) return ["Backend selected open targets: none.", "Open boundary: Completed buttons send only row_key and target."];
    const targets = Array.isArray(item.available_open_targets)
      ? item.available_open_targets.filter(Boolean)
      : item.available_open_targets && typeof item.available_open_targets === "object"
      ? Object.entries(item.available_open_targets)
        .filter(([, enabled]) => enabled !== false)
        .map(([key]) => key)
      : [];
    return [
      `Backend selected open targets: ${targets.length ? targets.join(", ") : "none reported"}.`,
      "Open boundary: Completed buttons send only row_key and target.",
      "The WebView never sends arbitrary filesystem paths for Completed opens.",
    ];
  }

  function getSelectedCompletedRow() {
    return lastCompletedRows.find((row) => row?.row_key && row.row_key === selectedCompletedRowKey) || lastCompletedRows[0] || null;
  }

  function getLastCompletedPayload() {
    return lastCompletedPayload;
  }

  function getLastCompletedRows() {
    return lastCompletedRows.slice();
  }

  function getLastCompletedPendingProofRows() {
    return lastCompletedPendingProofRows.slice();
  }

  function selectCompletedRow(item) {
    if (item?.row_key) selectedCompletedRowKey = item.row_key;
    renderCompletedRows();
    renderCompletedDetail(item || getSelectedCompletedRow());
  }

  function renderCompletedDetail(item) {
    renderCompletedSelectedAtAGlance(item || null);
    const detailDrawer = window.mediaPipelineDom?.selectedRowDetailDrawerLines;
    const guardrail = "Mutation guardrail: selected-row detail is read-only and cannot accept outputs, repair manifests, rerun jobs, reconcile sidecars, publish, or delete files.";
    if (!item) {
      const bodyLines = completedRowReviewChecklistLines(null);
      const detailLines = typeof detailDrawer === "function"
        ? detailDrawer({
          title: "Completed selected-row detail",
          summaryLines: completedSelectedAtAGlanceLines(null),
          bodyLines,
          guardrail,
        })
        : bodyLines;
      setText("completed-detail", detailLines.join("\n"));
      setText("completed-open-status", "Select a completed row to open a backend-selected location.");
      renderCompletedDiagnosticsLinks(null);
      renderCompletedPromotionActions(null);
      return;
    }
    const audioPreview = Array.isArray(item.audio_decision_preview) ? item.audio_decision_preview : [];
    const subtitlePreview = Array.isArray(item.subtitle_decision_preview) ? item.subtitle_decision_preview : [];
    const reviewFlags = Array.isArray(item.review_flags) ? item.review_flags.join(", ") : "";
    const routeEvidence = Array.isArray(item.route_evidence_lines) ? item.route_evidence_lines : [];
    const proofSummary = Array.isArray(item.proof_summary) ? item.proof_summary : [];
    const diagnosticTargets = Array.isArray(item.recommended_diagnostics_targets) ? item.recommended_diagnostics_targets.join(", ") : "";
    const handoffLines = typeof diagnosticsBridgeHandoffLines === "function"
      ? diagnosticsBridgeHandoffLines("Completed selected row", completedDiagnosticsActionsForRow(item), {
        evidence: [
          item.output_health || item.output_exists === false ? `output=${item.output_health || "missing"}` : "",
          item.consistency_status ? `consistency=${item.consistency_status}` : "",
          item.size_delta_label ? `size=${item.size_delta_label}` : "",
          item.runtime_outcome_status || item.runtime_outcome_reason ? `runtime=${[item.runtime_outcome_status, item.runtime_outcome_error_code, item.runtime_outcome_reason].filter(Boolean).join(" - ")}` : "",
        ],
        safeAction: "compare Completed Manifest, output/sidecar state, Pending Publish, Run Logs, and Last Stderr before rerun or cleanup.",
      })
      : [];
    const detail = [
      ...completedSelectedQuickSignalLines(item),
      "",
      ...completedRowReviewChecklistLines(item),
      "",
      ...completedRowIssueDigestLines(item),
      "",
      ...completedRowCombinedReviewPlanLines(item),
      "",
      ...completedInvestigationSignalLines(item),
      "",
      ...completedRealMediaTraceLines(item),
      "",
      ...completedRowTrustSummaryLines(item),
      "",
      ...completedSampleValidationComparisonLines(item),
      "",
      ...handoffLines,
      "",
      ...completedSelectedOpenTargetLines(item),
      "",
      item.row_key ? `Row key: ${item.row_key}` : "",
      `Completed: ${item.completed_at || ""}`,
      item.operator_trust_state ? `Backend trust state: ${item.operator_trust_state}` : "",
      item.primary_concern ? `Primary concern: ${item.primary_concern}` : "",
      item.safe_next_action ? `Safe next action: ${item.safe_next_action}` : "",
      item.unsafe_if_ignored ? `Unsafe if ignored: ${item.unsafe_if_ignored}` : "",
      proofSummary.length ? "Backend proof summary:" : "",
      ...proofSummary.map((line) => `  ${line}`),
      diagnosticTargets ? `Recommended diagnostics targets: ${diagnosticTargets}` : "",
      item.operator_status ? `Operator status: ${item.operator_status}` : "",
      item.operator_guidance ? `Next step: ${item.operator_guidance}` : "",
      reviewFlags ? `Review flags: ${reviewFlags}` : "",
      item.consistency_status ? `Consistency: ${item.consistency_status}` : "",
      item.consistency_guidance ? `Consistency next step: ${item.consistency_guidance}` : "",
      Array.isArray(item.consistency_issues) && item.consistency_issues.length ? `Consistency issues: ${item.consistency_issues.join(", ")}` : "",
      item.validation_status_state ? `Validation state: ${item.validation_status_state}` : "",
      item.validation_failure_reason ? `Validation proof gap: ${item.validation_failure_reason}` : "",
      item.validation_probe_ok === true ? "Probe proof: passed" : item.validation_probe_ok === false ? "Probe proof: failed" : "Probe proof: not reported",
      item.validation_hash_ok === true ? "Hash proof: passed" : item.validation_hash_ok === false ? "Hash proof: failed" : "Hash proof: not reported",
      item.validation_playback_required === true ? "Playback required: yes" : item.validation_playback_required === false ? "Playback required: no" : "Playback required: not reported",
      Array.isArray(item.validation_unavailable_reasons) && item.validation_unavailable_reasons.length ? `Validation unavailable proof: ${item.validation_unavailable_reasons.join(", ")}` : "",
      item.validation_safe_next_action ? `Validation next step: ${item.validation_safe_next_action}` : "",
      item.expected_sidecar_path ? `Expected sidecar: ${item.expected_sidecar_path}` : "",
      item.sidecar_exists === false ? "Sidecar: missing" : item.sidecar_exists === true ? "Sidecar: present" : "",
      item.route_decision_summary ? `Route decision: ${item.route_decision_summary}` : "",
      routeEvidence.length ? "Route evidence:" : "",
      ...routeEvidence.map((line) => `  ${line}`),
      item.runtime_outcome_status ? `Last runtime outcome: ${item.runtime_outcome_status}` : "",
      item.runtime_outcome_event_type ? `Runtime event type: ${item.runtime_outcome_event_type}` : "",
      item.runtime_outcome_at ? `Runtime event at: ${item.runtime_outcome_at}` : "",
      item.runtime_outcome_age_text || item.runtime_outcome_freshness_status ? `Runtime history age: ${item.runtime_outcome_age_text || "unknown"} (${item.runtime_outcome_freshness_status || "unknown"})` : "",
      item.runtime_outcome_stage || item.runtime_outcome_route ? `Runtime stage/route: ${item.runtime_outcome_stage || "unknown"} / ${item.runtime_outcome_route || "unknown"}` : "",
      item.runtime_outcome_error_code ? `Runtime error code: ${item.runtime_outcome_error_code}` : "",
      item.runtime_outcome_reason ? `Runtime reason: ${item.runtime_outcome_reason}` : "",
      item.runtime_outcome_publish_state || item.runtime_outcome_publish_mode ? `Runtime publish: ${item.runtime_outcome_publish_state || "unknown"} / ${item.runtime_outcome_publish_mode || "unknown"}` : "",
      item.runtime_outcome_output_path ? `Runtime output: ${item.runtime_outcome_output_path}` : "",
      item.runtime_outcome_match ? `Runtime match: ${item.runtime_outcome_match}` : "",
      `Route: ${item.route_label || item.route || ""}`,
      item.route_reason || item.route_reason_code ? `Route reason: ${[item.route_reason_code, item.route_reason].filter(Boolean).join(" - ")}` : "",
      `Publish: ${item.publish || ""}`,
      item.final_library_promotion_status_label ? `Final library promotion: ${item.final_library_promotion_status_label}` : "",
      item.final_library_rule_label ? `Final library rule: ${item.final_library_rule_label}` : "",
      item.final_library_destination_path ? `Final library destination: ${item.final_library_destination_path}` : "",
      item.last_promotion_run_id ? `Last promotion run: ${item.last_promotion_run_id}` : "",
      item.last_promotion_completed_at ? `Last promotion completed: ${item.last_promotion_completed_at}` : "",
      item.promotion_error ? `Promotion error: ${item.promotion_error}` : "",
      `Media: ${item.media_type || ""}`,
      `Title: ${item.lookup_title || item.output_file || ""}`,
      `Output: ${item.output_path || ""}`,
      `Source: ${item.source_path || ""}`,
      `Sidecar: ${item.sidecar_path || ""}`,
      `Size: ${item.size_reduction_text || item.output_size_text || ""}`,
      `Output growth: ${item.size_delta_label || "unknown"}`,
      item.size_growth_over_5 ? "Size review: output is more than 5% larger than source." : "",
      `Encoder: ${item.encoder || item.encoder_kind || ""}`,
      `Audio decisions: ${item.audio_decision_count || 0}`,
      ...audioPreview.map((line) => `  ${line}`),
      `Subtitle decisions: ${item.subtitle_decision_count || 0}`,
      ...subtitlePreview.map((line) => `  ${line}`),
      `Health: ${item.output_health || (item.output_exists === false ? "missing output" : "ok")}`,
    ].filter((line) => line !== "");
    const detailLines = typeof detailDrawer === "function"
      ? detailDrawer({
        title: "Completed selected-row detail",
        summaryLines: completedSelectedAtAGlanceLines(item),
        bodyLines: detail,
        guardrail,
      })
      : detail;
    setText("completed-detail", detailLines.join("\n"));
    setText("completed-open-status", "Selected completed row. Open commands use backend-selected paths from the manifest.");
    renderCompletedPromotionActions(item);
    renderCompletedDiagnosticsLinks(item);
  }

  function currentFinalLibraryPromotionRunId() {
    return String(finalLibraryPromotionActiveRun(lastFinalLibraryPromotionStatus).run_id || "");
  }

  function setFinalLibraryPromotionCommandBusy(isBusy) {
    finalLibraryPromotionCommandInFlight = Boolean(isBusy);
    renderFinalLibraryPromotion(lastFinalLibraryPromotionStatus);
  }

  async function requestFinalLibraryPromotion(rowKeys = []) {
    if (finalLibraryPromotionCommandInFlight) return;
    const selectedRowKeys = (Array.isArray(rowKeys) ? rowKeys : [rowKeys])
      .map((value) => String(value || "").trim())
      .filter(Boolean);
    if (!shouldConfirmFinalLibraryPromotion(selectedRowKeys.length || Number(lastFinalLibraryPromotionStatus?.counts?.eligible || 0))) return;
    setFinalLibraryPromotionCommandBusy(true);
    setText("final-library-promotion-status", "Starting");
    try {
      const request = { confirm_promote: true };
      if (selectedRowKeys.length) request.row_keys = selectedRowKeys;
      const result = await apiPost("/api/final-library-promotion/promote-queue", request);
      appendCommandResult(result);
      setText("final-library-promotion-status", result.ok ? "Started" : "Start failed");
      if (result?.data && typeof result.data === "object") {
        renderFinalLibraryPromotion({ ...lastFinalLibraryPromotionStatus, active_run: result.data });
      }
      if (result?.ok) {
        if (typeof refreshCurrentOutputStatus === "function") {
          await refreshCurrentOutputStatus();
        } else if (typeof refreshAll === "function") {
          await refreshAll();
        }
      }
    } catch (error) {
      const message = error?.message || String(error);
      appendCommandResult({
        command: "final_library.promote_queue",
        ok: false,
        message,
        severity: "error",
      });
      setText("final-library-promotion-status", `Start failed: ${message}`);
    } finally {
      setFinalLibraryPromotionCommandBusy(false);
    }
  }

  async function requestSelectedFinalLibraryPromotion(item = getSelectedCompletedRow()) {
    const row = item || getSelectedCompletedRow();
    const action = finalLibraryPromotionActionState(row);
    if (!action.available) {
      setText("completed-open-status", action.reason);
      renderCompletedPromotionActions(row || null);
      return;
    }
    setText("completed-open-status", "Promotion request will be sent after confirmation. The backend owns destination selection and file movement.");
    await requestFinalLibraryPromotion([row.row_key]);
  }

  async function requestFinalLibraryPromotionPause() {
    if (finalLibraryPromotionCommandInFlight) return;
    const runId = currentFinalLibraryPromotionRunId();
    if (!runId) {
      setText("final-library-promotion-status", "No active promotion run to pause.");
      return;
    }
    setFinalLibraryPromotionCommandBusy(true);
    try {
      const result = await apiPost("/api/final-library-promotion/pause", { run_id: runId });
      appendCommandResult(result);
      if (result?.data && typeof result.data === "object") {
        renderFinalLibraryPromotion({ ...lastFinalLibraryPromotionStatus, active_run: result.data });
      }
    } catch (error) {
      const message = error?.message || String(error);
      appendCommandResult({
        command: "final_library.pause",
        ok: false,
        message,
        severity: "error",
      });
      setText("final-library-promotion-status", `Pause failed: ${message}`);
    } finally {
      setFinalLibraryPromotionCommandBusy(false);
    }
  }

  async function requestFinalLibraryPromotionResume() {
    if (finalLibraryPromotionCommandInFlight) return;
    const runId = currentFinalLibraryPromotionRunId();
    if (!runId) {
      setText("final-library-promotion-status", "No paused promotion run to resume.");
      return;
    }
    setFinalLibraryPromotionCommandBusy(true);
    try {
      const result = await apiPost("/api/final-library-promotion/resume", { run_id: runId });
      appendCommandResult(result);
      if (result?.data && typeof result.data === "object") {
        renderFinalLibraryPromotion({ ...lastFinalLibraryPromotionStatus, active_run: result.data });
      }
    } catch (error) {
      const message = error?.message || String(error);
      appendCommandResult({
        command: "final_library.resume",
        ok: false,
        message,
        severity: "error",
      });
      setText("final-library-promotion-status", `Resume failed: ${message}`);
    } finally {
      setFinalLibraryPromotionCommandBusy(false);
    }
  }

  async function requestCompletedOpen(target) {
    if (rejectCompletedOpenWhileBusy()) return;
    const row = getSelectedCompletedRow();
    if (!row?.row_key) {
      setText("completed-open-status", "Select a completed row first.");
      return;
    }
    setCompletedOpenBusy(true);
    setText("completed-open-status", "Opening...");
    try {
      const result = await apiPost("/api/completed/open", { row_key: row.row_key, target });
      setText("completed-open-status", result.message || "Open request sent.");
      appendCommandResult(result);
    } catch (error) {
      const message = error?.message || String(error);
      setText("completed-open-status", `Open failed: ${message}`);
      appendCommandResult({
        command: "completed.open",
        ok: false,
        message,
        severity: "error",
      });
    } finally {
      setCompletedOpenBusy(false);
    }
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

  function isCompletedOpenCommand(entry) {
    return String(entry?.command || "").toLowerCase() === "completed.open";
  }

  function completedOpenHistoryLine(entry) {
    const raw = entry?.raw && typeof entry.raw === "object" ? entry.raw : {};
    const data = raw.data && typeof raw.data === "object" ? raw.data : {};
    const request = raw.request && typeof raw.request === "object" ? raw.request : {};
    const bits = [];
    if (data.target || request.target) bits.push(`target=${data.target || request.target}`);
    if (data.row_key || request.row_key) bits.push(`row=${data.row_key || request.row_key}`);
    const openedPath = data.path || data.opened_path || "";
    if (openedPath) bits.push(`opened=${openedPath}`);
    if (typeof commandHistoryCompactEvidenceLine === "function") {
      return commandHistoryCompactEvidenceLine(entry, {
        label: "completed.open",
        detail: bits.length ? ` (${bits.join("; ")})` : "",
      });
    }
    const status = entry?.result || (entry?.ok ? "ok" : entry?.severity || "unknown");
    const local = entry?.local ? "local" : "journal";
    return `${entry?.at || ""} completed.open [${status}; ${local}] ${entry?.message || ""}${bits.length ? ` (${bits.join("; ")})` : ""}`.trim();
  }

  function renderCompletedOpenHistory(history = []) {
    const entries = Array.isArray(history) ? history.filter(isCompletedOpenCommand).slice(0, 5) : [];
    if (!Array.isArray(history) || !history.length) {
      setText("completed-open-history", "No completed open command history loaded. Open a selected row location to see backend results here after refresh.");
      return;
    }
    if (!entries.length) {
      setText("completed-open-history", "No completed open commands found in recent command history.");
      return;
    }
    setText("completed-open-history", [
      `Last ${entries.length} completed open command${entries.length === 1 ? "" : "s"}:`,
      ...entries.map(completedOpenHistoryLine),
      "Backend manifest row keys and target allowlists remain the source of truth.",
    ].join("\n"));
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
