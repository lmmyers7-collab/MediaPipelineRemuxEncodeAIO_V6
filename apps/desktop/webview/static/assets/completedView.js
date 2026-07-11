/* global refreshAll, refreshCurrentOutputStatus */
  const createCompletedSizeMode = window.__completedSizeModeModule;
  const createCompletedPresentation = window.__completedPresentationModule;
  delete window.__completedSizeModeModule;
  delete window.__completedPresentationModule;
  if (typeof createCompletedSizeMode !== "function" || typeof createCompletedPresentation !== "function") {
    throw new Error("Completed child modules must load before completedView.js");
  }

(function () {
  const COMPLETED_READ_ONLY_BOUNDARY = "Mutation guardrail: read-only evidence; backend routes own output and manifest changes.";
  let lastCompletedRows = [];
  let lastCompletedPayload = {};
  let lastFinalLibraryPromotionStatus = {};
  let lastCompletedPendingPayload = {};
  let lastCompletedPendingProofRows = [];
  let lastPublishReconciliationPayload = {};
  let selectedCompletedRowKey = "";
  let selectedCompletedSignalKey = "";
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
  const COMPLETED_SIZE_COLUMN_MODE_STORAGE_KEY = "mediapipeline.completed.sizeColumnMode";
  let initCompletedRepairEvents = function () {};
  let isCompletedRepairCommand = function () { return false; };
  let repairDryRunIsSafeForSelection = function () { return false; };

  function diagnosticsBridgeApi() {
    return window.mediaPipelineDiagnosticsBridge || {};
  }
  let renderCompletedRepairControls = function () {};
  let renderCompletedRepairHistory = function () {};
  let requestCompletedRepairApply = async function () {};
  let requestCompletedRepairDryRun = async function () {};
  let setCompletedRepairBusy = function () {};

  const completedSizeMode = createCompletedSizeMode({ byId, storageKey: COMPLETED_SIZE_COLUMN_MODE_STORAGE_KEY });
  let completedSizeColumnMode = completedSizeMode.getMode();
  function syncCompletedSizeColumnModeControls() { completedSizeMode.sync(); }
  function setCompletedSizeColumnMode(mode) { completedSizeColumnMode = completedSizeMode.setMode(mode); }

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
    "library_id",
    "library_name",
    "library_designation",
    "library_source_root",
    "library_output_root",
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
    get selectedCompletedSignalKey() { return selectedCompletedSignalKey; },
    set selectedCompletedSignalKey(value) { selectedCompletedSignalKey = value; },
    get lastCompletedEmptyMessage() { return lastCompletedEmptyMessage; },
    set lastCompletedEmptyMessage(value) { lastCompletedEmptyMessage = value; },
    get completedSizeColumnMode() { return completedSizeColumnMode; },
    set completedSizeColumnMode(value) { completedSizeColumnMode = completedSizeMode.setMode(value); },
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
  let completedLibraryFilterLabel = completedReviewNoop;
  let completedLibraryMatchesFilter = completedReviewNoop;
  let syncCompletedLibraryFilterOptions = completedReviewNoop;
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
      renderProgressBarsInto: window.mediaPipelineProgressView?.renderProgressBarsInto,
      state: completedEvidenceState,
    })
    : {};
  const {
    completedCurrentRows = completedReviewNoop,
    completedMissingRows = completedReviewNoop,
    completedOutputPlacement = completedReviewNoop,
    completedPlacementCounts = completedReviewNoop,
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
      commandHistoryCommandText: window.mediaPipelineCommandHistory?.commandHistoryCommandText,
      commandHistoryIssueLevel: window.mediaPipelineCommandHistory?.commandHistoryIssueLevel,
      commandHistoryOwnerPage: window.mediaPipelineCommandHistory?.commandHistoryOwnerPage,
      commandHistorySuggestedAction: window.mediaPipelineCommandHistory?.commandHistorySuggestedAction,
      completedEvidenceState,
      completedFilterFields: COMPLETED_FILTER_FIELDS,
      completedCurrentRows: (...args) => completedCurrentRows(...args),
      completedLibraryFilterLabel: (...args) => completedLibraryFilterLabel(...args),
      completedLibraryMatchesFilter: (...args) => completedLibraryMatchesFilter(...args),
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
      renderCompletedDetail: (...args) => renderCompletedDetail(...args),
      renderCompletedFinalTrust: (...args) => renderCompletedFinalTrust(...args),
      renderCompletedPilotEvidencePacket: (...args) => renderCompletedPilotEvidencePacket(...args),
      renderCompletedRealMediaProof: (...args) => renderCompletedRealMediaProof(...args),
      renderCompletedReviewDigest: (...args) => renderCompletedReviewDigest(...args),
      renderCompletedRows: (...args) => renderCompletedRows(...args),
      renderCompletedSizeEvidence: (...args) => renderCompletedSizeEvidence(...args),
      renderCompletedSizeReview: (...args) => renderCompletedSizeReview(...args),
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
      appendDiagnosticsBridgeButton: diagnosticsBridgeApi().appendDiagnosticsBridgeButton,
      appendDiagnosticsBridgeGroupedButtons: diagnosticsBridgeApi().appendDiagnosticsBridgeGroupedButtons,
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
      completedLibraryFilterLabel: (...args) => completedLibraryFilterLabel(...args),
      completedLibraryMatchesFilter: (...args) => completedLibraryMatchesFilter(...args),
      completedFormatCounts,
      completedFreshnessLine,
      completedManifestIsAged,
      completedPendingProofIsExactPathSignal,
      completedProofCompletedOutputPath,
      completedProofCompletedSourcePath,
      completedProofRowLabel,
      completedProofRowMissingOutput,
      diagnosticsBridgeRowTrustLines: diagnosticsBridgeApi().diagnosticsBridgeRowTrustLines,
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
      diagnosticsBridgeHandoffLines: diagnosticsBridgeApi().diagnosticsBridgeHandoffLines,
      renderCompletedDiagnosticsLinks: (...args) => renderCompletedDiagnosticsLinks(...args),
      renderCompletedActiveOutputContext: (...args) => renderCompletedActiveOutputContext(...args),
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

  const completedRepairModule = window.__completedViewRepairModule || {};
  delete window.__completedViewRepairModule;
  const completedRepair = typeof completedRepairModule.createCompletedRepairModule === "function"
    ? completedRepairModule.createCompletedRepairModule({
      apiPost: typeof apiPost === "function" ? apiPost : window.apiPost,
      appendCommandResult: typeof appendCommandResult === "function" ? appendCommandResult : window.appendCommandResult,
      byId: typeof byId === "function" ? byId : window.byId,
      commandHistoryCompactEvidenceLine: typeof window.commandHistoryCompactEvidenceLine === "function" ? window.commandHistoryCompactEvidenceLine : (typeof commandHistoryCompactEvidenceLine === "function" ? commandHistoryCompactEvidenceLine : null),
      renderCompactCommandHistoryBlock: window.mediaPipelineCommandHistory?.renderCompactCommandHistoryBlock || null,
      getCommandHistory: typeof window.getCommandHistory === "function" ? () => window.getCommandHistory() : (typeof getCommandHistory === "function" ? () => getCommandHistory() : () => []),
      getSelectedCompletedRow: (...args) => getSelectedCompletedRow(...args),
      setText: typeof setText === "function" ? setText : window.setText,
    })
    : {};
  initCompletedRepairEvents = typeof completedRepair.initCompletedRepairEvents === "function" ? completedRepair.initCompletedRepairEvents : initCompletedRepairEvents;
  isCompletedRepairCommand = typeof completedRepair.isCompletedRepairCommand === "function" ? completedRepair.isCompletedRepairCommand : isCompletedRepairCommand;
  repairDryRunIsSafeForSelection = typeof completedRepair.repairDryRunIsSafeForSelection === "function" ? completedRepair.repairDryRunIsSafeForSelection : repairDryRunIsSafeForSelection;
  renderCompletedRepairControls = typeof completedRepair.renderCompletedRepairControls === "function" ? completedRepair.renderCompletedRepairControls : renderCompletedRepairControls;
  renderCompletedRepairHistory = typeof completedRepair.renderCompletedRepairHistory === "function" ? completedRepair.renderCompletedRepairHistory : renderCompletedRepairHistory;
  requestCompletedRepairApply = typeof completedRepair.requestCompletedRepairApply === "function" ? completedRepair.requestCompletedRepairApply : requestCompletedRepairApply;
  requestCompletedRepairDryRun = typeof completedRepair.requestCompletedRepairDryRun === "function" ? completedRepair.requestCompletedRepairDryRun : requestCompletedRepairDryRun;
  setCompletedRepairBusy = typeof completedRepair.setCompletedRepairBusy === "function" ? completedRepair.setCompletedRepairBusy : setCompletedRepairBusy;
  const selectCompletedRowFromSelection = selectCompletedRow;
  selectCompletedRow = (...args) => {
    const result = selectCompletedRowFromSelection(...args);
    renderCompletedRepairControls();
    return result;
  };

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
    completedLibraryFilterLabel: resolvedCompletedLibraryFilterLabel = completedReviewNoop,
    completedLibraryMatchesFilter: resolvedCompletedLibraryMatchesFilter = completedReviewNoop,
    completedRiskStatusLine = completedReviewNoop,
    completedRowsStatusLine = completedReviewNoop,
    renderCompletedReconciliationHint = completedReviewNoop,
    resetCompletedFilters = completedReviewNoop,
    resetCompletedHistoryFilters = completedReviewNoop,
    syncCompletedLibraryFilterOptions: resolvedSyncCompletedLibraryFilterOptions = completedReviewNoop,
  } = completedFilters;
  completedLibraryFilterLabel = resolvedCompletedLibraryFilterLabel;
  completedLibraryMatchesFilter = resolvedCompletedLibraryMatchesFilter;
  syncCompletedLibraryFilterOptions = resolvedSyncCompletedLibraryFilterOptions;

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
      completedLibraryFilterLabel: (...args) => completedLibraryFilterLabel(...args),
      completedMetricCounts: (...args) => completedMetricCounts(...args),
      completedOutputPlacement: (...args) => completedOutputPlacement(...args),
      completedRiskStatusLine: (...args) => completedRiskStatusLine(...args),
      completedReviewRows: (...args) => completedReviewRows(...args),
      completedRowsStatusLine: (...args) => completedRowsStatusLine(...args),
      filterResultSummaryLines: window.filterResultSummaryLines || window.mediaPipelineDom?.filterResultSummaryLines,
      finalLibraryPromotionChipState: (...args) => finalLibraryPromotionChipState(...args),
      finalLibraryPromotionStatusText: (...args) => finalLibraryPromotionStatusText(...args),
      getSelectedCompletedRow: (...args) => getSelectedCompletedRow(...args),
      makeStatusChip: window.mediaPipelineDom?.makeStatusChip,
      makeRowSelectable: typeof makeRowSelectable === "function" ? makeRowSelectable : window.makeRowSelectable,
      renderCompletedTrustDecision: (...args) => renderCompletedTrustDecision(...args),
      renderCompletedDetail: (...args) => renderCompletedDetail(...args),
      renderCompletedActiveOutputContext: (...args) => renderCompletedActiveOutputContext(...args),
      renderCompletedEvidenceCopyState: (...args) => renderCompletedEvidenceCopyState(...args),
      renderCompletedFinalTrust: (...args) => renderCompletedFinalTrust(...args),
      renderCompletedOutputAcceptance: (...args) => renderCompletedOutputAcceptance(...args),
      renderCompletedPilotEvidencePacket: (...args) => renderCompletedPilotEvidencePacket(...args),
      selectCompletedRow: (...args) => selectCompletedRow(...args),
      setCellStatusChip: typeof setCellStatusChip === "function" ? setCellStatusChip : window.setCellStatusChip,
      setText: typeof setText === "function" ? setText : window.setText,
      state: completedEvidenceState,
      syncCompletedLibraryFilterOptions: (...args) => syncCompletedLibraryFilterOptions(...args),
      updateTableStatusLegend: typeof updateTableStatusLegend === "function" ? updateTableStatusLegend : window.updateTableStatusLegend,
    })
    : {};
  ({
    renderCompletedRows = completedReviewNoop,
    renderCompletedHistoryRows = completedReviewNoop,
  } = completedTable);
  const renderCompletedRowsFromTable = renderCompletedRows;
  const renderCompletedHistoryRowsFromTable = renderCompletedHistoryRows;
  renderCompletedRows = (...args) => {
    syncCompletedSizeColumnModeControls();
    return renderCompletedRowsFromTable(...args);
  };
  renderCompletedHistoryRows = (...args) => {
    syncCompletedSizeColumnModeControls();
    return renderCompletedHistoryRowsFromTable(...args);
  };
  syncCompletedSizeColumnModeControls();

  const completedPresentation = createCompletedPresentation({
    byId, setText, completedReviewRowReasons, completedCurrentRows, completedMissingRows, completedPlacementCounts, completedReviewRows,
    completedFilterVisibilityLines, getSelectedCompletedRow, completedSelectedAtAGlanceState, completedOutputPlacement, completedSelectedAtAGlanceStatus,
    renderCompletedRows, renderCompletedDetail, renderPublishReconciliation, renderCompletedReconciliationHint, resetCompletedFilters, completedMetricCounts,
    mergeFinalLibraryPromotionRows, renderCompletedRepairControls, renderCompletedRepairHistory, completedEmptyStateMessage, completedFreshnessLine, completedFormatCounts,
    renderCompletedInventoryProgress, renderCompletedIntegrity, renderCompletedBreakdown, renderCompletedRuntime, renderCompletedConsistency, renderCompletedValidation,
    renderCompletedWorkflow, renderCompletedReviewBoard, renderCompletedReviewDigest, renderCompletedPendingProof, renderCompletedSizeReview, renderCompletedSizeEvidence,
    renderCompletedOutputAcceptance, renderCompletedRouteAgreement, renderCompletedRealMediaProof, renderCompletedFinalTrust, renderCompletedPilotEvidencePacket,
    renderCompletedOpenHistory, COMPLETED_READ_ONLY_BOUNDARY, getCommandHistory: typeof getCommandHistory === "function" ? getCommandHistory : undefined,
    getState: () => ({
      lastCompletedPayload, lastCompletedRows, lastFinalLibraryPromotionStatus, lastCompletedPendingPayload,
      lastCompletedPendingProofRows, lastPublishReconciliationPayload, selectedCompletedRowKey,
      selectedPublishReconciliationKey, lastCompletedEmptyMessage,
    }),
    setState: (key, value) => {
      if (key === "lastCompletedPayload") lastCompletedPayload = value;
      else if (key === "lastCompletedRows") lastCompletedRows = value;
      else if (key === "lastFinalLibraryPromotionStatus") lastFinalLibraryPromotionStatus = value;
      else if (key === "lastCompletedPendingPayload") lastCompletedPendingPayload = value;
      else if (key === "lastCompletedPendingProofRows") lastCompletedPendingProofRows = value;
      else if (key === "lastPublishReconciliationPayload") lastPublishReconciliationPayload = value;
      else if (key === "selectedCompletedRowKey") selectedCompletedRowKey = value;
      else if (key === "selectedPublishReconciliationKey") selectedPublishReconciliationKey = value;
      else if (key === "lastCompletedEmptyMessage") lastCompletedEmptyMessage = value;
    },
  });
  const {
    completedTrustDecisionState, completedTrustDecisionRowIdentity, completedTrustDecisionHiddenReviewCount, completedPublishReconciliationPayloadLoaded,
    completedPublishReconciliationStateLabel, completedTrustDecisionReconciliationLoaded, renderCompletedTrustDecision, completedActiveOutputTitle,
    completedActiveOutputPathsLine, completedActiveOutputVisibility, renderCompletedActiveOutputContext, showSelectedCompletedRow, completedEvidencePacketAvailable,
    renderCompletedEvidenceCopyState, markPublishReconciliationStale, focusCompletedQuickLinkTarget, setCompletedCurrentFilters, activateQuickLink, renderCompleted,
    completedEvidencePacketText, copyCompletedEvidencePacket,
  } = completedPresentation;


  /**
   * Public namespace for the Completed page module.
   * Prefer this namespace from new code; flat window.* exports are transitional compatibility aliases when present.
   */
  window.mediaPipelineCompletedView = {
    renderCompleted,
    renderCompletedInventoryProgress,
    completedInventoryProgressBars,
    completedCurrentRows,
    completedLibraryFilterLabel,
    completedLibraryMatchesFilter,
    completedMissingRows,
    completedOutputPlacement,
    completedPlacementCounts,
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
    setCompletedSizeColumnMode,
    syncCompletedSizeColumnModeControls,
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
    renderCompletedTrustDecision,
    renderCompletedActiveOutputContext,
    showSelectedCompletedRow,
    renderCompletedReconciliationHint,
    markPublishReconciliationStale,
    completedEvidencePacketText,
    completedEvidencePacketAvailable,
    renderCompletedEvidenceCopyState,
    copyCompletedEvidencePacket,
    initCompletedRepairEvents,
    isCompletedRepairCommand,
    repairDryRunIsSafeForSelection,
    renderCompletedRepairControls,
    renderCompletedRepairHistory,
    requestCompletedRepairApply,
    requestCompletedRepairDryRun,
    setCompletedRepairBusy,
    activateQuickLink,
  };
  initCompletedRepairEvents();
})();
