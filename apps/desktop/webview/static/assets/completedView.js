/* global refreshAll, refreshCurrentOutputStatus */
(function () {
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

  function normalizeCompletedSizeColumnMode(value) {
    return String(value || "size").trim().toLowerCase() === "bitrate" ? "bitrate" : "size";
  }

  function loadCompletedSizeColumnMode() {
    try {
      return normalizeCompletedSizeColumnMode(window.localStorage?.getItem(COMPLETED_SIZE_COLUMN_MODE_STORAGE_KEY));
    } catch (_error) {
      return "size";
    }
  }

  let completedSizeColumnMode = loadCompletedSizeColumnMode();

  function syncCompletedSizeColumnModeControls() {
    const mode = normalizeCompletedSizeColumnMode(completedSizeColumnMode);
    const label = mode === "bitrate" ? "Bitrate" : "Size";
    document.querySelectorAll("[data-completed-size-column-mode]").forEach((button) => {
      const active = normalizeCompletedSizeColumnMode(button.dataset.completedSizeColumnMode) === mode;
      button.classList.toggle("is-active", active);
      button.setAttribute("aria-pressed", active ? "true" : "false");
    });
    document.querySelectorAll("[data-completed-size-column-label]").forEach((node) => {
      node.textContent = label;
    });
  }

  function setCompletedSizeColumnMode(mode) {
    completedSizeColumnMode = normalizeCompletedSizeColumnMode(mode);
    try {
      window.localStorage?.setItem(COMPLETED_SIZE_COLUMN_MODE_STORAGE_KEY, completedSizeColumnMode);
    } catch (_error) {
      // Local storage is optional; the table still updates for this session.
    }
    syncCompletedSizeColumnModeControls();
    renderCompletedRows();
  }

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
    set completedSizeColumnMode(value) { completedSizeColumnMode = normalizeCompletedSizeColumnMode(value); },
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
      completedOutputPlacement: (...args) => completedOutputPlacement(...args),
      completedRiskStatusLine: (...args) => completedRiskStatusLine(...args),
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

  function completedTrustDecisionState(status) {
    const normalized = String(status || "").toLowerCase();
    if (normalized.includes("trust")) return "ok";
    if (normalized.includes("investigate")) return "blocked";
    if (normalized.includes("incomplete")) return "validation-needed";
    if (normalized.includes("review")) return "warning";
    return "unknown";
  }

  function completedTrustDecisionRowIdentity(row) {
    return String(row?.row_key || row?.output_path || row?.source_path || row?.output_file || "").trim().toLowerCase();
  }

  function completedTrustDecisionHiddenReviewCount(currentRows, visibleRows) {
    const visible = new Set((Array.isArray(visibleRows) ? visibleRows : []).map(completedTrustDecisionRowIdentity).filter(Boolean));
    return (Array.isArray(currentRows) ? currentRows : []).filter((row) => {
      const identity = completedTrustDecisionRowIdentity(row);
      if (identity && visible.has(identity)) return false;
      const status = String(completedDisplayRowStatus(row) || "").toLowerCase();
      const reasons = completedReviewRowReasons(row);
      return ["blocked", "warning", "failed", "validation-needed"].includes(status)
        || (Array.isArray(reasons) && reasons.length);
    }).length;
  }

  function completedPublishReconciliationPayloadLoaded(payload = lastPublishReconciliationPayload) {
    const data = payload && typeof payload === "object" ? payload : {};
    const status = String(data.status || "").trim().toLowerCase();
    if (data.stale) return false;
    if (["not_loaded", "loading", "error", "stale"].includes(status)) return false;
    return Boolean(status) || Array.isArray(data.rows);
  }

  function completedPublishReconciliationStateLabel(payload = lastPublishReconciliationPayload) {
    const data = payload && typeof payload === "object" ? payload : {};
    if (data.stale) return "stale";
    const status = String(data.status || "").trim();
    if (status === "not_loaded") return "not loaded";
    return status || (Array.isArray(data.rows) ? "loaded" : "not loaded");
  }

  function completedTrustDecisionReconciliationLoaded() {
    return completedPublishReconciliationPayloadLoaded(lastPublishReconciliationPayload);
  }

  function renderCompletedTrustDecision({
    payload = lastCompletedPayload,
    allRows = lastCompletedRows,
    currentRows = completedCurrentRows(allRows),
    visibleRows = currentRows,
    proofRows = lastCompletedPendingProofRows,
  } = {}) {
    const rowList = Array.isArray(allRows) ? allRows : [];
    const currentList = Array.isArray(currentRows) ? currentRows : [];
    const visibleList = Array.isArray(visibleRows) ? visibleRows : [];
    const proofList = Array.isArray(proofRows) ? proofRows : [];
    const missingRows = completedMissingRows(rowList);
    const missingList = Array.isArray(missingRows) ? missingRows : [];
    const placementCounts = completedPlacementCounts(rowList, proofList) || {};
    const currentReview = completedReviewRows(payload || {}, currentList);
    const currentReviewCount = Array.isArray(currentReview) ? currentReview.length : 0;
    const hiddenReviewCount = completedTrustDecisionHiddenReviewCount(currentList, visibleList);
    const reconciliationLoaded = completedTrustDecisionReconciliationLoaded();
    const pendingProofLoaded = Boolean(proofList.length || Object.keys(lastCompletedPendingPayload || {}).length);
    const missingNoProof = Number(placementCounts.missing_no_proof || 0);
    const movedUnknown = Number(placementCounts.moved_offline_unknown || 0);
    const pendingProofMissing = Number(placementCounts.missing_pending_proof || 0);
    const drainProofMissing = Number(placementCounts.missing_drain_proof || 0);
    const incompleteReasons = [];
    if (!rowList.length) incompleteReasons.push("no completed history rows loaded");
    if (!pendingProofLoaded) incompleteReasons.push("pending/drain proof not loaded");
    if (!reconciliationLoaded) incompleteReasons.push(`publish reconciliation ${completedPublishReconciliationStateLabel(lastPublishReconciliationPayload)}`);
    let status = "Trust ready";
    if (payload?.error || missingNoProof || movedUnknown) {
      status = "Investigate";
    } else if (currentReviewCount || hiddenReviewCount || pendingProofMissing || drainProofMissing || !reconciliationLoaded) {
      status = "Review first";
    } else if (incompleteReasons.length) {
      status = "Evidence incomplete";
    }
    const statusNode = byId("completed-trust-decision-status");
    setText("completed-trust-decision-status", status);
    if (statusNode) statusNode.dataset.state = completedTrustDecisionState(status);
    const chipContainer = byId("completed-trust-decision-chips");
    if (chipContainer && window.mediaPipelineDom?.makeStatusChip) {
      chipContainer.replaceChildren(
        window.mediaPipelineDom.makeStatusChip(`Trust ready${status === "Trust ready" ? "" : ` ${Math.max(currentList.length - currentReviewCount, 0)}`}`, status === "Trust ready" ? "ok" : "normal"),
        window.mediaPipelineDom.makeStatusChip(`Review first ${currentReviewCount + hiddenReviewCount + pendingProofMissing + drainProofMissing}`, status === "Review first" ? "warning" : "normal"),
        window.mediaPipelineDom.makeStatusChip(`Investigate ${missingNoProof + movedUnknown + (payload?.error ? 1 : 0)}`, status === "Investigate" ? "blocked" : "normal"),
        window.mediaPipelineDom.makeStatusChip(`Evidence incomplete ${incompleteReasons.length}`, status === "Evidence incomplete" ? "validation-needed" : "normal"),
      );
    }
    const lines = [
      "Output trust decision:",
      `Operator outcome: ${status}.`,
      `Current outputs present: ${currentList.length}; visible after filters: ${visibleList.length}.`,
      `Current rows needing review: ${currentReviewCount}; hidden review rows: ${hiddenReviewCount}.`,
      `Historical missing outputs: ${missingList.length}.`,
      `Placement evidence: Current=${placementCounts.current || 0}; Missing: pending proof=${pendingProofMissing}; Missing: drain proof=${drainProofMissing}; Missing: no proof=${missingNoProof}; Moved/offline unknown=${movedUnknown}.`,
      `Pending/drain proof: ${pendingProofLoaded ? "loaded or locally derived" : "not loaded"}.`,
      `Backend publish reconciliation: ${completedPublishReconciliationStateLabel(lastPublishReconciliationPayload)}.`,
    ];
    if (incompleteReasons.length) lines.push(`Evidence gaps: ${incompleteReasons.join("; ")}.`);
    if (status === "Investigate") {
      lines.push("First action: inspect missing/no-proof outputs in Completed History, Pending Publish, Diagnostics, Run Logs, and Last Stderr before rerun, cleanup, deletion, or manual movement.");
    } else if (status === "Review first") {
      lines.push("First action: read review rows and refresh backend reconciliation before trusting, rerunning, draining, or promoting output.");
    } else if (status === "Evidence incomplete") {
      lines.push("First action: load Completed, Pending Publish, and backend reconciliation evidence before making a trust decision.");
    } else {
      lines.push("First action: output appears trust-ready in the loaded evidence; acceptance remains an operator judgment and backend state remains authoritative.");
    }
    lines.push("Mutation guardrail: this summary is read-only and cannot accept outputs, rerun jobs, drain pending publish, promote files, delete files, rewrite manifests, or touch media.");
    setText("completed-trust-decision-summary", lines.join("\n"));
  }

  function completedActiveOutputTitle(item) {
    if (!item) return "No completed row selected";
    return item.output_file || item.lookup_title || item.output_path || item.source_path || "(unnamed completed row)";
  }

  function completedActiveOutputPathsLine(item) {
    if (!item) return "Select a row to keep its output context visible across Completed subtabs.";
    return [
      item.output_path ? `Output: ${item.output_path}` : "Output: not reported",
      item.source_path ? `Source: ${item.source_path}` : "Source: not reported",
    ].join(" | ");
  }

  function completedRowIsRenderedInTable(rowKey, tableSelector) {
    if (!rowKey) return false;
    return Array.from(document.querySelectorAll(`${tableSelector} tr[data-row-key]`)).some((row) => String(row.dataset.rowKey || "") === rowKey);
  }

  function completedActiveOutputVisibility(item) {
    if (!item) return { label: "not evaluated", hidden: false };
    const lines = typeof completedFilterVisibilityLines === "function" ? completedFilterVisibilityLines(item) : [];
    const visibilityLine = lines.find((line) => /^Selected row visible in table:/.test(String(line || ""))) || "";
    const hiddenLine = lines.find((line) => /^Hidden by current filters:/.test(String(line || ""))) || "";
    const activeLine = lines.find((line) => /^Active filters:/.test(String(line || ""))) || "";
    const rowKey = String(item.row_key || "");
    const inCurrentTable = completedRowIsRenderedInTable(rowKey, "#completed-rows");
    const inHistoryTable = completedRowIsRenderedInTable(rowKey, "#completed-history-rows");
    if (inCurrentTable || inHistoryTable) {
      if (hiddenLine) {
        const renderedLabel = inCurrentTable ? "visible in rendered current table" : "visible in rendered history table";
        return { label: activeLine ? `${renderedLabel}. ${hiddenLine} ${activeLine}` : `${renderedLabel}. ${hiddenLine}`, hidden: true };
      }
      return { label: activeLine ? `${visibilityLine || "Selected row visible in table: yes"} ${activeLine}` : "visible in rendered table", hidden: false };
    }
    if (hiddenLine) {
      return { label: activeLine ? `${hiddenLine} ${activeLine}` : hiddenLine, hidden: true };
    }
    if (String(visibilityLine).toLowerCase().includes("yes")) {
      return {
        label: "visible after filters but outside the first rendered rows; Show Selected pins it into the displayed table window",
        hidden: true,
      };
    }
    return {
      label: hiddenLine || visibilityLine || "not visible in the rendered table",
      hidden: true,
    };
  }

  function renderCompletedActiveOutputContext(item = getSelectedCompletedRow()) {
    const context = byId("completed-active-output-context");
    if (!context) return;
    const selected = item || null;
    const state = selected && typeof completedSelectedAtAGlanceState === "function"
      ? completedSelectedAtAGlanceState(selected)
      : "unknown";
    const placement = selected && typeof completedOutputPlacement === "function"
      ? completedOutputPlacement(selected, lastCompletedPendingProofRows)
      : { label: "not checked", state: "unknown" };
    const visibility = completedActiveOutputVisibility(selected);
    context.dataset.state = state || "unknown";
    setText("completed-active-output-title", completedActiveOutputTitle(selected));
    setText("completed-active-output-paths", completedActiveOutputPathsLine(selected));
    setText("completed-active-output-trust", selected && typeof completedSelectedAtAGlanceStatus === "function"
      ? `${completedSelectedAtAGlanceStatus(selected)} / ${selected.operator_trust_state || selected.output_health || "local proof"}`
      : "not selected");
    setText("completed-active-output-placement", placement.label || "not checked");
    setText("completed-active-output-visibility", visibility.label || "not evaluated");
    const button = byId("completed-show-selected-button");
    if (button) {
      button.disabled = !selected;
      button.title = selected
        ? "Clear Completed display filters and pin the selected row into the rendered table window without backend mutation."
        : "Select a completed row first.";
    }
  }

  function showSelectedCompletedRow() {
    const item = getSelectedCompletedRow();
    if (!item) {
      setText("completed-open-status", "Select a completed row before using Show Selected.");
      renderCompletedActiveOutputContext(null);
      return;
    }
    ["completed-filter", "completed-history-filter"].forEach((id) => {
      const node = byId(id);
      if (node) node.value = "";
    });
    ["completed-status-filter", "completed-library-filter", "completed-investigation-filter", "completed-history-status-filter", "completed-history-investigation-filter"].forEach((id) => {
      const node = byId(id);
      if (node) node.value = "all";
    });
    selectedCompletedRowKey = item.row_key || selectedCompletedRowKey;
    renderCompletedRows();
    renderCompletedDetail(item);
    const rowKey = String(item.row_key || "");
    const renderedRow = Array.from(document.querySelectorAll("#completed-rows tr[data-row-key], #completed-history-rows tr[data-row-key]"))
      .find((row) => String(row.dataset.rowKey || "") === rowKey);
    if (renderedRow && typeof renderedRow.focus === "function") {
      renderedRow.focus({ preventScroll: true });
    }
    setText("completed-open-status", "Selected completed row shown locally. Filters were cleared; backend manifest, promotion, rerun, cleanup, and reconcile scopes are unchanged.");
    renderCompletedActiveOutputContext(item);
  }

  function completedEvidencePacketAvailable() {
    const text = completedEvidencePacketText();
    return Boolean(text && text !== "No copyable pilot evidence packet loaded.");
  }

  function renderCompletedEvidenceCopyState(message = "") {
    const available = completedEvidencePacketAvailable();
    const button = byId("completed-copy-evidence-button");
    const status = byId("completed-copy-evidence-status");
    if (button) {
      button.disabled = !available;
      button.title = available
        ? "Copy the rendered evidence packet text. This does not append evidence or mutate media."
        : "No copyable evidence packet is available for the selected output.";
    }
    if (status) {
      status.dataset.state = available ? "ready" : "blocked";
      if (message) {
        status.textContent = message;
      } else if (!available) {
        status.textContent = "No evidence packet text is available to copy.";
      } else if (!String(status.textContent || "").trim() || String(status.textContent || "").includes("No evidence packet")) {
        status.textContent = "Evidence packet text is ready to copy. Copy does not append evidence, publish, drain, rerun, rename, or touch media.";
      }
    }
  }

  function markPublishReconciliationStale(reason = "Completed output status was refreshed after the last backend reconciliation snapshot.") {
    const previous = lastPublishReconciliationPayload && typeof lastPublishReconciliationPayload === "object"
      ? lastPublishReconciliationPayload
      : {};
    const hadPrevious = Boolean(previous.status || Array.isArray(previous.rows));
    lastPublishReconciliationPayload = hadPrevious
      ? {
        ...previous,
        status: "stale",
        stale: true,
        stale_reason: reason,
        summary_lines: [
          `Backend publish reconciliation is stale: ${reason}`,
          "Use Refresh Backend Reconciliation for a current backend-owned Completed/Pending/drain-summary proof snapshot.",
        ],
      }
      : {
        status: "not_loaded",
        stale: false,
        rows: [],
        summary_lines: [
          "Backend publish reconciliation has not been loaded for this Completed snapshot.",
          "Use Refresh Backend Reconciliation for a backend-owned Completed/Pending/drain-summary proof snapshot.",
        ],
      };
    selectedPublishReconciliationKey = "";
    renderPublishReconciliation(lastPublishReconciliationPayload);
    renderCompletedTrustDecision();
    renderCompletedReconciliationHint(lastCompletedPayload, lastCompletedRows);
  }

  function renderCompleted(completed = {}) {
    const payload = completed && typeof completed === "object" ? completed : {};
    let rows = Array.isArray(payload.rows) ? payload.rows : [];
    if (payload.final_library_promotion && typeof payload.final_library_promotion === "object") {
      lastFinalLibraryPromotionStatus = payload.final_library_promotion;
      const mergedRows = mergeFinalLibraryPromotionRows(rows, payload.final_library_promotion);
      rows = Array.isArray(mergedRows) ? mergedRows : rows;
    }
    const currentRowsResult = completedCurrentRows(rows);
    const currentRows = Array.isArray(currentRowsResult) ? currentRowsResult : [];
    const metricCountsResult = completedMetricCounts(rows);
    const metricCounts = metricCountsResult && typeof metricCountsResult === "object"
      ? metricCountsResult
      : { current: rows.length, encoded: 0, remuxed: 0, missing: 0 };
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
    renderCompletedRepairControls();
    if (typeof getCommandHistory === "function") renderCompletedRepairHistory(getCommandHistory());
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
    renderCompletedEvidenceCopyState();
    renderPublishReconciliation(lastPublishReconciliationPayload);
    renderCompletedDetail(getSelectedCompletedRow());
    renderCompletedActiveOutputContext(getSelectedCompletedRow());
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
      renderCompletedEvidenceCopyState("No evidence packet text is available to copy.");
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
      renderCompletedEvidenceCopyState("Copied evidence packet. This did not append evidence, save settings, publish, drain, rerun, rename, or touch media.");
      return true;
    } catch (error) {
      const message = error?.message || String(error);
      renderCompletedEvidenceCopyState(`Copy failed: ${message}. Select the packet text manually if needed.`);
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
  };
  initCompletedRepairEvents();
  window.renderCompleted = renderCompleted;
  window.renderCompletedPendingProof = renderCompletedPendingProof;
  window.renderCompletedRealMediaProof = renderCompletedRealMediaProof;
  window.selectCompletedRow = selectCompletedRow;
  window.getLastCompletedRows = getLastCompletedRows;
})();
