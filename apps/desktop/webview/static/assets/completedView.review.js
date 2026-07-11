(function () {
  function createCompletedReviewModule(deps = {}) {
    const {
      appendCells,
      byId,
      clearRows,
      completedAcceptanceProofRowsForItem,
      completedDiagnosticsActionsForRow,
      completedFilterFields = [],
      completedLibraryFilterLabel,
      completedLibraryMatchesFilter,
      completedFormatCounts,
      completedFreshnessLine = () => "",
      completedManifestIsAged,
      completedPendingProofIsExactPathSignal,
      completedProofCompletedOutputPath,
      completedProofCompletedSourcePath,
      completedProofRowLabel,
      completedProofRowMissingOutput,
      diagnosticsBridgeRowTrustLines,
      filterRows,
      makeRowSelectable,
      renderCompletedDetail,
      renderCompletedFinalTrust,
      renderCompletedOutputAcceptance,
      renderCompletedPendingProof,
      renderCompletedPilotEvidencePacket,
      renderCompletedRealMediaProof,
      renderCompletedRows,
      selectCompletedRow,
      setText,
      state,
      tableStatusMatchesFilter,
      tableStatusFilterLabel,
      updateTableStatusLegend,
    } = deps;
    const COMPLETED_READ_ONLY_BOUNDARY = "Mutation guardrail: read-only evidence; backend routes own output and manifest changes.";

    const completedReviewNoop = function () {};
    let completedReviewRowReasons = completedReviewNoop;

    const reviewIntegrityModule = window.__completedViewReviewIntegrityModule || {};
    delete window.__completedViewReviewIntegrityModule;
    const reviewIntegrity = typeof reviewIntegrityModule.createCompletedReviewIntegrityModule === "function"
      ? reviewIntegrityModule.createCompletedReviewIntegrityModule({
        completedFreshnessLine,
        completedFormatCounts,
        completedManifestIsAged,
      })
      : {};
    const {
      completedRowHasIntegrityIssue = completedReviewNoop,
      completedIntegrityStatus = completedReviewNoop,
      completedIntegrityLines = completedReviewNoop,
    } = reviewIntegrity;

    const reviewWorkflowOverviewModule = window.__completedReviewWorkflowOverviewModule;
    if (!reviewWorkflowOverviewModule?.createCompletedReviewWorkflowOverviewModule) throw new Error("Missing completed review workflow overview module");
    delete window.__completedReviewWorkflowOverviewModule;
    const {
      completedProofStripState, completedProofStripChip, renderCompletedProofStrip, renderCompletedIntegrity,
      completedWorkflowStatus, completedWorkflowLines, renderCompletedWorkflow,
    } = reviewWorkflowOverviewModule.createCompletedReviewWorkflowOverviewModule({
      byId, completedIntegrityLines, completedIntegrityStatus, completedManifestIsAged, completedRowHasIntegrityIssue,
      completedValidationStatus: (...args) => completedValidationStatus(...args), setText,
    });
    const reviewSizeReviewModule = window.__completedViewReviewSizeReviewModule || {};
    delete window.__completedViewReviewSizeReviewModule;
    const reviewSizeReview = typeof reviewSizeReviewModule.createCompletedReviewSizeReviewModule === "function"
      ? reviewSizeReviewModule.createCompletedReviewSizeReviewModule({
        completedRowHasIntegrityIssue,
        completedReviewRowReasons: (...args) => completedReviewRowReasons(...args),
      })
      : {};
    const {
      completedSizeDeltaPercent = () => Number.NaN,
      completedHasSmallHealthySizeDelta = completedReviewNoop,
      completedSizeReviewRows = () => [],
      completedSizeReviewStatus = completedReviewNoop,
      completedSizeReviewAction = completedReviewNoop,
      completedSizeReviewLines = () => [],
    } = reviewSizeReview;

    const reviewHealthSignalsModule = window.__completedViewReviewHealthSignalsModule || {};
    delete window.__completedViewReviewHealthSignalsModule;
    const reviewHealthSignals = typeof reviewHealthSignalsModule.createCompletedReviewHealthSignalsModule === "function"
      ? reviewHealthSignalsModule.createCompletedReviewHealthSignalsModule({
        completedRowHasIntegrityIssue,
        completedSizeDeltaPercent,
      })
      : {};
    const {
      completedRowHasBasicHealthyEvidence = completedReviewNoop,
      completedRowHasSmallHealthySizeGrowth = completedReviewNoop,
      completedRowLooksHealthy = completedReviewNoop,
      completedRuntimeAlreadyProcessedIsBenign = completedReviewNoop,
      completedReviewFlagIsBenign = completedReviewNoop,
      completedPrimaryConcernIsBenign = completedReviewNoop,
      completedRowHasBenignAlreadyProcessedOutcome = completedReviewNoop,
    } = reviewHealthSignals;

    const reviewRowsModule = window.__completedViewReviewRowsModule || {};
    delete window.__completedViewReviewRowsModule;
    const reviewRows = typeof reviewRowsModule.createCompletedReviewRowsModule === "function"
      ? reviewRowsModule.createCompletedReviewRowsModule({
        completedFormatCounts,
        completedManifestIsAged,
        completedWorkflowStatus,
        completedHasSmallHealthySizeDelta,
        completedPrimaryConcernIsBenign,
        completedReviewFlagIsBenign,
        completedRowHasIntegrityIssue,
        completedRowHasSmallHealthySizeGrowth,
        completedRowLooksHealthy,
        completedRowHasBenignAlreadyProcessedOutcome,
      })
      : {};
    completedReviewRowReasons = reviewRows.completedReviewRowReasons || completedReviewNoop;
    const {
      completedReviewRows = () => [],
      completedReviewStatus = completedReviewNoop,
      completedReviewBoardLines = () => [],
      completedReviewDigestStatus = completedReviewNoop,
      completedReviewDigestAction = completedReviewNoop,
      completedTableRowStatus = completedReviewNoop,
    } = reviewRows;

    const reviewInvestigationFiltersModule = window.__completedViewReviewInvestigationFiltersModule || {};
    delete window.__completedViewReviewInvestigationFiltersModule;
    const reviewInvestigationFilters = typeof reviewInvestigationFiltersModule.createCompletedReviewInvestigationFiltersModule === "function"
      ? reviewInvestigationFiltersModule.createCompletedReviewInvestigationFiltersModule({
        byId,
        completedFilterFields,
        completedLibraryFilterLabel,
        completedLibraryMatchesFilter,
        completedSizeDeltaPercent,
        completedTableRowStatus,
        filterRows,
        tableStatusMatchesFilter,
        tableStatusFilterLabel,
      })
      : {};
    const {
      completedInvestigationFilterLabel = completedReviewNoop,
      completedMatchesInvestigationFilter = completedReviewNoop,
      completedFocusedInvestigationLabels = () => [],
      completedFilterVisibilityLines = () => [],
      completedSelectedQuickSignalLines = () => [],
      completedInvestigationSignalLines = () => [],
    } = reviewInvestigationFilters;

    function captureCompletedReviewSelectionScroll() {
      return window.mediaPipelineDom?.captureScrollablePositions?.() || null;
    }

    function restoreCompletedReviewSelectionScroll(snapshot) {
      if (snapshot) window.mediaPipelineDom?.restoreScrollablePositions?.(snapshot);
    }

    const reviewTablePanelsModule = window.__completedReviewTablePanelsModule;
    if (!reviewTablePanelsModule?.createCompletedReviewTablePanelsModule) throw new Error("Missing completed review table panels module");
    delete window.__completedReviewTablePanelsModule;
    const {
      renderCompletedReviewDigest, renderCompletedReviewBoard, renderCompletedSizeReview,
      completedBreakdownStatus, completedBreakdownLines, renderCompletedBreakdown,
      completedRuntimeStatus, completedRuntimeLines, renderCompletedRuntime,
      completedConsistencyStatus, completedConsistencyLines, renderCompletedConsistency,
    } = reviewTablePanelsModule.createCompletedReviewTablePanelsModule({
      ...deps, completedHasSmallHealthySizeDelta, completedReviewBoardLines, completedReviewDigestAction,
      completedReviewDigestStatus, completedReviewRows, completedReviewStatus, completedSizeDeltaPercent,
      completedSizeReviewAction, completedSizeReviewLines, completedSizeReviewRows, completedSizeReviewStatus, renderCompletedProofStrip,
    });
    const reviewMetricsValidationModule = window.__completedReviewMetricsValidationModule;
    if (!reviewMetricsValidationModule?.createCompletedReviewMetricsValidationModule) throw new Error("Missing completed review metrics and validation module");
    delete window.__completedReviewMetricsValidationModule;
    const {
      completedSizeEvidencePostureStatus, completedSizeEvidenceRows, completedSizeEvidenceStatus,
      completedSizeEvidenceSummaryLines, completedSizeEvidenceDetailLines, selectedCompletedSizeEvidenceRow,
      selectCompletedSizeEvidenceRow, renderCompletedSizeEvidence, completedValidationStatePayload,
      completedValidationStatusLabel, completedValidationProofLabel, completedValidationStatus,
      completedValidationChecklistLines, renderCompletedValidation, completedRowReviewChecklistLines,
    } = reviewMetricsValidationModule.createCompletedReviewMetricsValidationModule({
      ...deps, captureSelectionScroll: captureCompletedReviewSelectionScroll, restoreSelectionScroll: restoreCompletedReviewSelectionScroll,
      completedHasSmallHealthySizeDelta, completedSizeDeltaPercent, completedSizeReviewRows,
      renderCompletedProofStrip, renderCompletedReviewDigest,
    });
    const reviewSelectedAtAGlanceModule = window.__completedReviewSelectedAtAGlanceModule;
    if (!reviewSelectedAtAGlanceModule?.createCompletedReviewSelectedAtAGlanceModule) throw new Error("Missing completed selected-row presentation module");
    delete window.__completedReviewSelectedAtAGlanceModule;
    const {
      completedSelectedAtAGlanceState, completedSelectedOutputUnavailable, completedSelectedAtAGlanceStatus,
      completedSelectedVisibilitySummary, completedSelectedLabel, completedSelectedConcern,
      completedSelectedSafeAction, completedSelectedTrustStatus, completedSelectedRouteLabel,
      completedSelectedSizeLabel, completedSelectedFormatBytes, completedSelectedSizeText,
      completedSelectedRuntimeLabel, completedSelectedPolicyLabel, completedSelectedSignalLine,
      completedSelectedRouteEvidenceLines, completedSelectedDecisionRows, completedSelectedSizeDetailLines,
      completedSelectedRouteDetailLines, completedSelectedTriggerDetailLines, completedSelectedSizePolicyDetailLines,
      completedSelectedRuntimeDetailLines, completedSelectedAudioSubtitleDetailLines, completedSelectedSignalDetailLines,
      completedSelectedSizeDeltaPercent, completedSelectedPositiveGrowth, completedSelectedRouteLooksEncode,
      completedSelectedSizePolicyLabel, completedSelectedDiagnosisLine, completedSelectedWhyItMatters,
      completedSelectedEvidenceGaps, completedSelectedNextChecks, completedSelectedSignalTone,
      completedSelectedKeySignals, completedSelectedNode, completedSelectedSignalItem,
      completedSelectedActiveSignal, selectCompletedSignal, completedSelectedSignalDetailPanel,
      completedSelectedListBlock, completedSelectedPaths, completedSelectedSummaryNodes,
      completedSelectedAtAGlanceLines, renderCompletedSelectedAtAGlance,
    } = reviewSelectedAtAGlanceModule.createCompletedReviewSelectedAtAGlanceModule({
      ...deps, backendRowStatusState: window.backendRowStatusState,
      captureSelectionScroll: captureCompletedReviewSelectionScroll, restoreSelectionScroll: restoreCompletedReviewSelectionScroll,
      completedPrimaryConcernIsBenign, completedReviewFlagIsBenign, completedRowHasBenignAlreadyProcessedOutcome,
      completedRowLooksHealthy, completedValidationProofLabel, completedValidationStatusLabel, completedFilterVisibilityLines,
    });
    const reviewSelectedEvidenceModule = window.__completedReviewSelectedEvidenceModule;
    if (!reviewSelectedEvidenceModule?.createCompletedReviewSelectedEvidenceModule) throw new Error("Missing completed selected-row diagnostics module");
    delete window.__completedReviewSelectedEvidenceModule;
    const {
      completedRowIssueDigestLines, completedRowCombinedReviewPlanLines, completedRealMediaTraceLines,
      completedRowTrustSummaryLines, completedSampleValidationComparisonLines,
    } = reviewSelectedEvidenceModule.createCompletedReviewSelectedEvidenceModule({
      ...deps, completedReviewFlagIsBenign, completedRowLooksHealthy,
    });
    return {
      completedIntegrityStatus,
      completedIntegrityLines,
      renderCompletedIntegrity,
      completedWorkflowStatus,
      completedWorkflowLines,
      renderCompletedWorkflow,
      completedReviewRowReasons,
      completedReviewRows,
      completedReviewStatus,
      completedReviewBoardLines,
      completedReviewDigestStatus,
      completedReviewDigestAction,
      completedTableRowStatus,
      completedInvestigationFilterLabel,
      completedMatchesInvestigationFilter,
      completedFocusedInvestigationLabels,
      completedFilterVisibilityLines,
      completedSelectedQuickSignalLines,
      completedInvestigationSignalLines,
      renderCompletedReviewDigest,
      renderCompletedReviewBoard,
      completedSizeReviewRows,
      completedSizeReviewStatus,
      completedSizeReviewAction,
      completedSizeReviewLines,
      renderCompletedSizeReview,
      completedSizeEvidencePostureStatus,
      completedSizeEvidenceRows,
      completedSizeEvidenceStatus,
      completedSizeEvidenceSummaryLines,
      completedSizeEvidenceDetailLines,
      renderCompletedSizeEvidence,
      completedBreakdownStatus,
      completedBreakdownLines,
      renderCompletedBreakdown,
      completedRuntimeStatus,
      completedRuntimeLines,
      renderCompletedRuntime,
      completedConsistencyStatus,
      completedConsistencyLines,
      renderCompletedConsistency,
      completedValidationStatus,
      completedValidationChecklistLines,
      renderCompletedValidation,
      completedRowReviewChecklistLines,
      completedSelectedAtAGlanceState,
      completedSelectedAtAGlanceStatus,
      completedSelectedAtAGlanceLines,
      completedSelectedKeySignals,
      completedSelectedSignalDetailLines,
      renderCompletedSelectedAtAGlance,
      completedRowIssueDigestLines,
      completedRowCombinedReviewPlanLines,
      completedRealMediaTraceLines,
      completedRowTrustSummaryLines,
      completedSampleValidationComparisonLines,
    };
  }

  window.__completedViewReviewModule = {
    createCompletedReviewModule,
  };
})();
