/* Default no-op/read-only adapters used until Pending Publish child factories are composed. */
(function () {
  function createPendingPublishDefaultAdapters() {
const pendingDiagnosticsFallbackLines = function () { return []; };
  const pendingDiagnosticsFallbackRender = function () {};
  let pendingSelectedOpenTargetLines = pendingDiagnosticsFallbackLines;
  let pendingDiagnosticsActionsForRow = function () { return []; };
  let pendingDiagnosticsGuidanceLines = pendingDiagnosticsFallbackLines;
  let renderPendingDiagnosticsLinks = pendingDiagnosticsFallbackRender;
  let requestPendingDiagnosticsAction = async function () {};
  let isPendingOpenCommand = function (entry) { return String(entry?.command || "").toLowerCase() === "pending_publish.open"; };
  let pendingOpenHistoryLine = function (entry) { return String(entry?.message || entry?.command || "pending_publish.open"); };
  let renderPendingOpenHistory = pendingDiagnosticsFallbackRender;
  let requestPendingPublishOpen = async function () {};

const pendingRecoveryFallbackRows = function () { return []; };
  const pendingRecoveryFallbackLines = function () { return []; };
  const pendingRecoveryFallbackRender = function () {};

let rejectPendingRecoveryPlanWhileBusy = function () { return false; };
  let requestPendingRecoveryPlan = async function () {};
  let renderPendingRecoveryPlanResult = pendingRecoveryFallbackRender;
  let pendingRecoveryPlanResultLines = pendingRecoveryFallbackLines;
  let pendingRecoveryPlanRowKey = function (row, index = 0) { return String(row?.row_key || row?.manifest_path || row?.local_file || row?.server_out || row?.source_path || `plan-row-${index}`).trim(); };
  let pendingRecoveryPlanRowStatus = function () { return "warning"; };
  let pendingRecoveryPlanEvidenceText = function () { return "No explicit evidence fields reported."; };
  let pendingRecoveryPlanActionText = function (row) { return row?.safe_next_action || row?.planned_action || "Review pending publish diagnostics before drain."; };
  let pendingRecoveryPlanRowDetailLines = pendingRecoveryFallbackLines;
  let renderPendingRecoveryPlanRows = pendingRecoveryFallbackRender;
  let selectPendingRecoveryPlanRow = pendingRecoveryFallbackRender;
  let renderPendingRecoveryPlanRowDetail = pendingRecoveryFallbackRender;
  let renderPendingRecoveryPlanHistory = pendingRecoveryFallbackRender;
  let isPendingRecoveryPlanCommand = function (entry) { return String(entry?.command || "").toLowerCase() === "pending_publish.recovery_plan_dry_run"; };
  let pendingRecoveryPlanHistoryLine = function (entry) { return String(entry?.message || entry?.command || "pending_publish.recovery_plan_dry_run"); };
  let pendingRecoveryPlanResultData = function (result) { return result?.data && typeof result.data === "object" ? result.data : {}; };
  let pendingRecoveryPlanRowLabel = function (row) { return pendingRecoveryPlanRowKey(row); };
  let initPendingRepairManifestEvents = function () {};
  let isPendingRepairManifestCommand = function () { return false; };
  let pendingRepairDryRunIsSafeForSelection = function () { return false; };
  let pendingRepairManifestApplyRequest = function () { return null; };
  let pendingRepairManifestDryRunRequest = function () { return null; };
  let pendingRepairManifestHistoryLine = function (entry) { return String(entry?.message || entry?.command || "pending_publish.repair_manifest"); };
  let pendingRepairManifestResultLines = pendingRecoveryFallbackLines;
  let renderPendingRepairManifestControls = pendingRecoveryFallbackRender;
  let renderPendingRepairManifestHistory = pendingRecoveryFallbackRender;
  let requestPendingRepairManifestApply = async function () {};
  let requestPendingRepairManifestDryRun = async function () {};
  let setPendingRepairManifestBusy = function () {};
  let isPendingRepairOrphanCommand = function (entry) { return String(entry?.command || entry?.raw?.command || "").toLowerCase() === "pending_publish.reconcile_orphan_payloads"; };
  let pendingOrphanDryRunIsSafeForSelection = function () { return false; };
  let pendingRepairOrphanApplyRequest = function () { return null; };
  let pendingRepairOrphanDryRunRequest = function () { return null; };
  let renderPendingRepairOrphanControls = pendingRecoveryFallbackRender;
  let renderPendingRepairOrphanHistory = pendingRecoveryFallbackRender;
  let requestPendingRepairOrphanApply = async function () {};
  let requestPendingRepairOrphanDryRun = async function () {};
  let setPendingRepairOrphanBusy = function () {};

const pendingDrainFallbackRows = function () { return []; };
  const pendingDrainFallbackLines = function () { return []; };
  const pendingDrainFallbackScope = function () {
    return {
      active: false,
      filterText: "",
      statusFilter: "all",
      statusLabel: "all",
      investigationFilter: "all",
      investigationLabel: "all signals",
      totalCount: 0,
      visibleCount: 0,
      hiddenCount: 0,
      hiddenBlockedCount: 0,
      hiddenReviewCount: 0,
    };
  };
  const pendingDrainFallbackRender = function () {};
  let pendingCurrentFilterScope = pendingDrainFallbackScope;
  let pendingCurrentFilterScopeEvidence = function () { return "filters=inactive; visible=0/0; hidden=0; hidden blocked=0; hidden review=0; text=none; status=all; view=all signals"; };
  let pendingCurrentFilterScopeAction = function () { return "No display filter is active; visible table scope matches loaded Pending Publish rows."; };
  let pendingBackendDrainScopeRows = pendingDrainFallbackRows;
  let pendingBackendDrainScopeStatus = function () { return "Not evaluated"; };
  let pendingBackendDrainScopeSummaryLines = pendingDrainFallbackLines;
  let renderPendingBackendDrainScopePreview = pendingDrainFallbackRender;
  let pendingEvidenceClass = function () { return "review"; };
  let pendingEvidenceRows = pendingDrainFallbackRows;
  let pendingEvidenceStatus = function () { return "Not loaded"; };
  let pendingEvidenceText = function () { return "no explicit evidence fields reported"; };
  let pendingEvidenceAction = function () { return "Select a row and inspect backend-selected targets before drain."; };
  let pendingDrainEvidenceLines = pendingDrainFallbackLines;
  let renderPendingDrainEvidence = pendingDrainFallbackRender;
  let pendingDrainSearchText = function () { return ""; };
  let isPendingDrainCommand = function () { return false; };
  let pendingDrainHistoryLine = function (entry) { return String(entry?.message || entry?.command || "pending publish drain"); };
  let renderPendingDrainHistory = pendingDrainFallbackRender;
  let pendingDrainEventsFromSnapshot = pendingDrainFallbackRows;
  let pendingDrainEventStatus = function () { return "unknown"; };
  let pendingDrainEventRoute = function () { return "unknown"; };
  let pendingDrainEventLeaf = function () { return "(unknown output)"; };
  let pendingDrainEventCounts = function () { return "none"; };
  let pendingDrainEventsStatus = function () { return "No snapshot"; };
  let pendingDrainEventsLines = pendingDrainFallbackLines;
  let renderPendingDrainEvents = pendingDrainFallbackRender;
  let pendingDrainSummaryPayload = function () { return {}; };
  let pendingDrainSummaryItems = pendingDrainFallbackRows;
  let pendingDrainSummaryStatus = function () { return "No summary"; };
  let pendingDrainSummaryLeaf = function () { return "(unknown output)"; };
  let pendingDrainSummaryLines = pendingDrainFallbackLines;
  let renderPendingDrainSummary = pendingDrainFallbackRender;
  let pendingDrainLatestCommand = function () { return null; };
  let pendingDrainCommandData = function () { return {}; };
  let pendingDrainCommandRequest = function () { return {}; };
  let pendingDrainCommandResultText = function () { return "no recent drain command"; };
  let pendingDrainCommandIssueLevel = function () { return "none"; };
  let pendingDrainSummaryIssueLevel = function () { return "none"; };
  let pendingDrainCorrelationStatus = function () { return "No drain evidence"; };
  let pendingDrainCorrelationLines = pendingDrainFallbackLines;
  let renderPendingDrainCorrelation = pendingDrainFallbackRender;

const pendingConfidenceFallbackRows = function () { return []; };
  const pendingConfidenceFallbackLines = function () { return []; };
  const pendingConfidenceFallbackRender = function () {};
  let pendingDrainConfidenceRows = pendingConfidenceFallbackRows;
  let pendingDrainConfidenceStatus = function () { return "Not evaluated"; };
  let pendingDrainConfidenceSummaryLines = pendingConfidenceFallbackLines;
  let renderPendingDrainActionConfidence = pendingConfidenceFallbackRender;
  let pendingDrainDecisionRows = pendingConfidenceFallbackRows;
  let pendingDrainDecisionStatus = function () { return "Not evaluated"; };
  let pendingDrainDecisionStatusState = function () { return "unknown"; };
  let pendingDrainDecisionSummaryLines = pendingConfidenceFallbackLines;
  let pendingDrainDecisionDetailLines = pendingConfidenceFallbackLines;
  let pendingDrainDecisionPostureStatus = function () { return "unknown"; };
  let renderPendingDrainDecisionChecklist = pendingConfidenceFallbackRender;
  let pendingPostDrainTrustRows = pendingConfidenceFallbackRows;
  let pendingPostDrainTrustStatus = function () { return "Not evaluated"; };
  let pendingPostDrainTrustSummaryLines = pendingConfidenceFallbackLines;
  let pendingPostDrainTrustDetailLines = pendingConfidenceFallbackLines;
  let pendingPostDrainTrustPostureStatus = function () { return "unknown"; };
  let renderPendingPostDrainTrust = pendingConfidenceFallbackRender;
  let pendingDrainGuardState = function () {
    return {
      allowed: false,
      review_required: false,
      decision_status: "Not evaluated",
      message: "Pending drain guard is not loaded.",
      confirm_message: "Pending drain guard is not loaded.",
    };
  };
  let pendingDrainGuardLines = function (state) { return [state?.message || "Pending drain guard is not loaded."]; };
  let renderPendingDrainGuard = function () { return pendingDrainGuardState(); };
    return {
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
    };
  }
  window.__pendingPublishDefaultAdaptersModule = { createPendingPublishDefaultAdapters };
})();
