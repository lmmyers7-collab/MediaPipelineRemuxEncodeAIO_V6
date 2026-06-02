(function () {
  let lastPendingRows = [];
  let lastPendingPayload = {};
  let lastPendingSnapshot = {};
  let selectedPendingRowKey = "";
  let lastPendingRecoveryPlanRows = [];
  let selectedPendingRecoveryPlanKey = "";
  let selectedPendingDrainDecisionKey = "";
  let selectedPendingPostDrainTrustKey = "";
  let lastPendingEmptyMessage = "No pending publish rows available.";
  let pendingOpenInFlight = false;
  let pendingRecoveryPlanInFlight = false;
  const PENDING_FILTER_FIELDS = ["state", "local_file", "server_out", "source_path", "error", "issue_summary", "route", "publish_mode", "diagnostic_status", "diagnostic_severity", "drain_recommendation", "operator_guidance"];

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
  let setPendingRecoveryPlanBusy = function (isBusy) {
    pendingRecoveryPlanInFlight = Boolean(isBusy);
    ["pending-recovery-plan-selected-button", "pending-recovery-plan-all-button"].forEach((id) => {
      const button = byId(id);
      if (button) button.disabled = pendingRecoveryPlanInFlight;
    });
  };
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

  function renderPendingPublish(pending, snapshot = {}) {
    const rows = Array.isArray(pending.rows) ? pending.rows : [];
    lastPendingRows = rows;
    lastPendingPayload = pending || {};
    lastPendingSnapshot = snapshot || {};
    if (selectedPendingRowKey && !rows.some((row) => pendingRowKey(row) === selectedPendingRowKey)) {
      selectedPendingRowKey = "";
    }
    lastPendingEmptyMessage = pendingEmptyStateMessage(pending, rows);
    setText("pending-count", String(pending.count || 0));
    setText("pending-payload-count", String(pending.payload_count || 0));
    setText("pending-size", pending.total_size_text || "0 B");
    setText("pending-health-count", String(pending.health_count || 0));
    const freshnessLines = window.mediaPipelineDom?.payloadFreshnessLines
      ? window.mediaPipelineDom.payloadFreshnessLines({
        payload: pending,
        label: "Pending Publish",
        rowCount: pending.count || rows.length || 0,
        sourceLine: pending.pending_root ? `Pending root: ${pending.pending_root}` : "",
        artifactLine: pending.exists ? "Pending scan: backend returned current parked-output inventory." : "Pending scan: pending root does not exist.",
        readError: pending.error || "",
        refreshAction: "Use Refresh Pending or topbar Refresh. This re-reads parked-output evidence only and does not publish, repair, delete, or move files.",
      })
      : [];
    const summary = [
      ...freshnessLines,
      freshnessLines.length ? "" : (pending.pending_root ? `Pending root: ${pending.pending_root}` : ""),
      freshnessLines.length ? "" : (pending.exists ? "" : "Pending root does not exist."),
      `Manifests: ${pending.count || rows.length || 0}`,
      `Payloads: ${pending.payload_count || 0}`,
      `Health rows: ${pending.health_count || 0}`,
      `Ready/review: ${pending.ready_count || 0} / ${pending.issue_count || 0}`,
      pending.operator_trust_state_counts ? `Backend trust states: ${pendingFormatCounts(pending.operator_trust_state_counts)}` : "",
      pending.available_open_target_counts ? `Backend open targets: ${pendingFormatCounts(pending.available_open_target_counts)}` : "",
      pending.missing_local_count ? `${pending.missing_local_count} payload reference(s) missing.` : "",
      ...(pending.warnings || []),
      !rows.length ? pendingEmptyStateMessage(pending, rows) : "",
    ].filter(Boolean);
    setText("pending-summary", summary.join("\n") || pending.error || "No pending publish health issues.");
    renderPendingInventoryProgress(pending);
    renderPendingPublishReadiness(pending, rows);
    renderPendingRiskBreakdown(pending, rows);
    renderPendingValidation(pending, rows);
    renderPendingWorkflow(pending, rows);
    renderPendingReviewBoard(pending, rows);
    renderPendingDrainEvidence(pending, rows);
    if (typeof getCommandHistory === "function") renderPendingDrainHistory(getCommandHistory());
    if (typeof getCommandHistory === "function") renderPendingOpenHistory(getCommandHistory());
    if (typeof getCommandHistory === "function") renderPendingRecoveryPlanHistory(getCommandHistory());
    renderPendingDrainEvents(snapshot || {});
    renderPendingDrainSummary(pending || {});
    renderPendingDrainCorrelation(pending || {}, rows, snapshot || {}, typeof getCommandHistory === "function" ? getCommandHistory() : []);
    renderPendingPostDrainTrust(pending || {}, rows, snapshot || {}, typeof getCommandHistory === "function" ? getCommandHistory() : []);
    renderPendingDrainActionConfidence(pending || {}, rows, snapshot || {}, typeof getCommandHistory === "function" ? getCommandHistory() : []);
    renderPendingBackendDrainScopePreview(pending || {}, rows, snapshot || {}, typeof getCommandHistory === "function" ? getCommandHistory() : []);
    renderPendingDrainDecisionChecklist(pending || {}, rows, snapshot || {}, typeof getCommandHistory === "function" ? getCommandHistory() : []);
    renderPendingDrainGuard(pending || {}, rows, snapshot || {}, typeof getCommandHistory === "function" ? getCommandHistory() : []);
    renderPendingDetail(getSelectedPendingRow());
    renderPendingRows();
    if (
      typeof window.renderCompletedPendingProof === "function"
      && typeof window.getLastCompletedPayload === "function"
      && typeof window.getLastCompletedRows === "function"
    ) {
      window.renderCompletedPendingProof(window.getLastCompletedPayload(), window.getLastCompletedRows(), lastPendingPayload);
      if (typeof window.renderCompletedRealMediaProof === "function" && typeof window.getLastCompletedPendingProofRows === "function") {
        window.renderCompletedRealMediaProof(
          window.getLastCompletedPayload(),
          window.getLastCompletedRows(),
          window.getLastCompletedPendingProofRows(),
          lastPendingPayload,
        );
        if (typeof window.renderCompletedPilotEvidencePacket === "function") {
          window.renderCompletedPilotEvidencePacket(
            window.getLastCompletedPayload(),
            window.getLastCompletedRows(),
            window.getLastCompletedPendingProofRows(),
            lastPendingPayload,
          );
        }
      }
    }
  }

  function getLastPendingPublishPayload() {
    return lastPendingPayload;
  }

  function getLastPendingPublishRows() {
    return lastPendingRows.slice();
  }

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
      renderProgressBarsInto: (...args) => window.renderProgressBarsInto?.(...args),
      selectPendingRow: (...args) => selectPendingRow(...args),
      setText: typeof setText === "function" ? setText : window.setText,
      shortenPath: window.shortenPath,
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

  function pendingListText(value) {
    return Array.isArray(value) && value.length ? value.join(", ") : "none";
  }

  function pendingRowKey(item) {
    if (item?.row_key) return String(item.row_key).toLocaleLowerCase();
    return [
      item?.manifest_path || "",
      item?.local_file || "",
      item?.server_out || "",
      item?.state || "",
    ].join("\u001f").toLocaleLowerCase();
  }

  function getSelectedPendingRow() {
    if (!selectedPendingRowKey) return null;
    return lastPendingRows.find((row) => pendingRowKey(row) === selectedPendingRowKey) || null;
  }

  function selectPendingRow(item) {
    selectedPendingRowKey = pendingRowKey(item);
    renderPendingDetail(item || null);
    renderPendingReviewDigest(lastPendingPayload, lastPendingRows);
    renderPendingDrainEvidence(lastPendingPayload, lastPendingRows);
    renderPendingBackendDrainScopePreview(lastPendingPayload, lastPendingRows, lastPendingSnapshot, typeof getCommandHistory === "function" ? getCommandHistory() : []);
    renderPendingDrainDecisionChecklist(lastPendingPayload, lastPendingRows, lastPendingSnapshot, typeof getCommandHistory === "function" ? getCommandHistory() : []);
    renderPendingRows();
  }

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
      diagnosticsBridgeHandoffLines: window.diagnosticsBridgeHandoffLines,
      diagnosticsBridgeRowTrustLines: window.diagnosticsBridgeRowTrustLines,
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

  function renderPendingRows() {
    const filterText = byId("pending-filter")?.value || "";
    const statusFilter = byId("pending-status-filter")?.value || "all";
    const investigationFilter = byId("pending-investigation-filter")?.value || "all";
    const textRows = filterRows(lastPendingRows, filterText, PENDING_FILTER_FIELDS);
    const statusRows = typeof filterRowsByStatus === "function" ? filterRowsByStatus(textRows, statusFilter, pendingTableRowStatus) : textRows;
    const rows = typeof filterRowsByInvestigation === "function" ? filterRowsByInvestigation(statusRows, investigationFilter, pendingMatchesInvestigationFilter) : statusRows;
    const renderLimit = 250;
    const renderedCount = Math.min(rows.length, renderLimit);
    setText(
      "pending-status",
      rows.length > renderLimit
        ? `${renderedCount} shown / ${rows.length} filtered / ${lastPendingRows.length} rows`
        : `${rows.length} / ${lastPendingRows.length} row${lastPendingRows.length === 1 ? "" : "s"}`
    );
    if (typeof filterResultSummaryLines === "function") {
      setText("pending-filter-summary", filterResultSummaryLines({
        label: "Pending publish filter",
        allRows: lastPendingRows,
        visibleRows: rows,
        filterText,
        statusFilter,
        investigationFilter,
        investigationLabel: pendingInvestigationFilterLabel(investigationFilter),
        statusOf: pendingTableRowStatus,
        limit: 250,
        decisionName: "publish/drain",
        guardrail: "Mutation guardrail: filtering Pending Publish rows does not change drain scope, recovery plans, manifests, payloads, or publish commands.",
      }).join("\n"));
    }
    const tbody = byId("pending-rows");
    if (!rows.length) {
      clearRows(tbody, 6, lastPendingRows.length ? "No pending publish rows match the filter." : lastPendingEmptyMessage);
      updateTableStatusLegend("pending-table-legend", tbody, "Pending publish rows");
      if (selectedPendingRowKey) renderPendingDetail(getSelectedPendingRow());
      renderPendingDrainActionConfidence(lastPendingPayload, lastPendingRows, lastPendingSnapshot, typeof getCommandHistory === "function" ? getCommandHistory() : []);
      renderPendingBackendDrainScopePreview(lastPendingPayload, lastPendingRows, lastPendingSnapshot, typeof getCommandHistory === "function" ? getCommandHistory() : []);
      renderPendingDrainDecisionChecklist(lastPendingPayload, lastPendingRows, lastPendingSnapshot, typeof getCommandHistory === "function" ? getCommandHistory() : []);
      renderPendingDrainGuard(lastPendingPayload, lastPendingRows, lastPendingSnapshot, typeof getCommandHistory === "function" ? getCommandHistory() : []);
      return;
    }
    tbody.replaceChildren();
    rows.slice(0, renderLimit).forEach((item) => {
      const row = document.createElement("tr");
      const key = pendingRowKey(item);
      row.dataset.rowKey = key;
      row.dataset.status = pendingTableRowStatus(item);
      const localFileDisplay = typeof shortenPath === "function" ? shortenPath(item.local_file || "", 40) : item.local_file || "";
      const serverOutDisplay = typeof shortenPath === "function" ? shortenPath(item.server_out || "", 40) : item.server_out || "";
      const stateText = item.state || "unknown";
      appendCells(row, [
        stateText,
        item.size_text || "",
        item.age_text || item.parked_at_display || "",
        localFileDisplay,
        serverOutDisplay,
        item.issue_summary || item.error || item.diagnostic_status || "",
      ], [null, "num", "num", "path-cell", "path-cell", null]);
      // Set title tooltip so full path is accessible on hover
      const pendingCells = row.querySelectorAll("td");
      const stateCell = pendingCells[0] || row.children?.[0];
      if (typeof setCellStatusChip === "function") setCellStatusChip(stateCell, stateText, row.dataset.status);
      if (pendingCells[3] && item.local_file) pendingCells[3].title = item.local_file;
      if (pendingCells[4] && item.server_out) pendingCells[4].title = item.server_out;
      makeRowSelectable(row, () => selectPendingRow(item), {
        selected: Boolean(key && key === selectedPendingRowKey),
        label: `Pending publish row ${item.local_file || item.server_out || item.manifest_path || ""}`,
      });
      tbody.appendChild(row);
    });
    updateTableStatusLegend("pending-table-legend", tbody, "Pending publish rows");
    if (selectedPendingRowKey) renderPendingDetail(getSelectedPendingRow());
    renderPendingDrainActionConfidence(lastPendingPayload, lastPendingRows, lastPendingSnapshot, typeof getCommandHistory === "function" ? getCommandHistory() : []);
    renderPendingBackendDrainScopePreview(lastPendingPayload, lastPendingRows, lastPendingSnapshot, typeof getCommandHistory === "function" ? getCommandHistory() : []);
    renderPendingDrainDecisionChecklist(lastPendingPayload, lastPendingRows, lastPendingSnapshot, typeof getCommandHistory === "function" ? getCommandHistory() : []);
    renderPendingDrainGuard(lastPendingPayload, lastPendingRows, lastPendingSnapshot, typeof getCommandHistory === "function" ? getCommandHistory() : []);
  }

  function resetPendingFilters() {
    const filter = byId("pending-filter");
    const status = byId("pending-status-filter");
    const investigation = byId("pending-investigation-filter");
    if (filter) filter.value = "";
    if (status) status.value = "all";
    if (investigation) investigation.value = "all";
    renderPendingRows();
    setText("pending-open-status", "Pending Publish display filters cleared. Backend drain scope, recovery plans, manifests, and payloads are unchanged.");
  }

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
      appendDiagnosticsBridgeButton: typeof appendDiagnosticsBridgeButton === "function" ? appendDiagnosticsBridgeButton : window.appendDiagnosticsBridgeButton,
      appendDiagnosticsBridgeGroupedButtons: typeof appendDiagnosticsBridgeGroupedButtons === "function" ? appendDiagnosticsBridgeGroupedButtons : window.appendDiagnosticsBridgeGroupedButtons,
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
      getSelectedPendingRow: (...args) => getSelectedPendingRow(...args),
      makeRowSelectable: typeof makeRowSelectable === "function" ? makeRowSelectable : window.makeRowSelectable,
      pendingFormatCounts: (...args) => pendingFormatCounts(...args),
      pendingRowKey: (...args) => pendingRowKey(...args),
      renderPendingBackendDrainScopePreview: (...args) => renderPendingBackendDrainScopePreview(...args),
      renderPendingDrainActionConfidence: (...args) => renderPendingDrainActionConfidence(...args),
      renderPendingDrainDecisionChecklist: (...args) => renderPendingDrainDecisionChecklist(...args),
      renderPendingDrainGuard: (...args) => renderPendingDrainGuard(...args),
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

  /**
   * Public namespace for the Pending Publish page module.
   * Prefer this namespace from new code; flat window.* exports are transitional compatibility aliases when present.
   */
  window.mediaPipelinePendingPublishView = {
    renderPendingPublish,
    renderPendingInventoryProgress,
    pendingInventoryProgressBars,
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
    pendingPostDrainTrustRows,
    pendingPostDrainTrustStatus,
    pendingPostDrainTrustSummaryLines,
    pendingPostDrainTrustDetailLines,
    pendingPostDrainTrustPostureStatus,
    renderPendingPostDrainTrust,
    pendingDrainGuardState,
    pendingDrainGuardLines,
    renderPendingDrainGuard,
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
  };
  window.renderPendingPublish = renderPendingPublish;
  window.renderPendingDetail = renderPendingDetail;
  window.getLastPendingPublishPayload = getLastPendingPublishPayload;
  window.renderPendingDrainEvidence = renderPendingDrainEvidence;
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
