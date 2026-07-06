(function () {
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
  const PENDING_FILTER_FIELDS = [
    "state",
    "row_key",
    "local_file",
    "server_out",
    "source_path",
    "manifest_path",
    "error",
    "issue_summary",
    "primary_concern",
    "safe_next_action",
    "route",
    "publish_mode",
    "diagnostic_status",
    "diagnostic_severity",
    "drain_recommendation",
    "operator_guidance",
    "operator_trust_state",
  ];

  function clampTableScrollOffset(value, maxValue) {
    const numeric = Number(value);
    const maximum = Math.max(0, Number(maxValue) || 0);
    return Math.min(Math.max(0, Number.isFinite(numeric) ? numeric : 0), maximum);
  }

  function tableScrollSnapshot(tbody) {
    const target = tbody?.closest?.(".table-wrap") || null;
    if (!target) return null;
    return {
      target,
      top: target.scrollTop,
      left: target.scrollLeft,
    };
  }

  function restoreTableScrollSnapshot(snapshot) {
    const target = snapshot?.target;
    if (!target || target.isConnected === false) return;
    target.scrollTop = clampTableScrollOffset(snapshot.top, target.scrollHeight - target.clientHeight);
    target.scrollLeft = clampTableScrollOffset(snapshot.left, target.scrollWidth - target.clientWidth);
  }

  function deferTableScrollRestore(snapshot) {
    if (!snapshot) return;
    const schedule = typeof window.requestAnimationFrame === "function"
      ? window.requestAnimationFrame.bind(window)
      : (fn) => window.setTimeout(fn, 0);
    restoreTableScrollSnapshot(snapshot);
    schedule(() => {
      restoreTableScrollSnapshot(snapshot);
      schedule(() => restoreTableScrollSnapshot(snapshot));
      window.setTimeout(() => restoreTableScrollSnapshot(snapshot), 0);
    });
  }

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

  function renderPendingPublish(pending, snapshot = {}) {
    const rows = Array.isArray(pending.rows) ? pending.rows : [];
    lastPendingRows = rows;
    lastPendingPayload = pending || {};
    lastPendingSnapshot = snapshot || {};
    if (selectedPendingRowKey && !rows.some((row) => pendingRowKey(row) === selectedPendingRowKey)) {
      selectedPendingRowKey = "";
    }
    clearStalePendingRecoveryPlan(pending || {}, rows);
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
    renderPendingDrainProgress(snapshot || {});
    renderPendingInventoryProgress(pending);
    renderPendingFileInventory(pending);
    renderPendingPublishReadiness(pending, rows);
    renderPendingRiskBreakdown(pending, rows);
    renderPendingValidation(pending, rows);
    renderPendingWorkflow(pending, rows);
    renderPendingReviewBoard(pending, rows);
    renderPendingDrainEvidence(pending, rows);
    if (typeof getCommandHistory === "function") renderPendingDrainHistory(getCommandHistory());
    if (typeof getCommandHistory === "function") renderPendingOpenHistory(getCommandHistory());
    if (typeof getCommandHistory === "function") renderPendingRecoveryPlanHistory(getCommandHistory());
    if (typeof getCommandHistory === "function") renderPendingRepairManifestHistory(getCommandHistory());
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
    renderPendingRepairManifestControls();
    renderPendingRepairOrphanControls();
    const completedView = window.mediaPipelineCompletedView || {};
    if (
      typeof completedView.renderCompletedPendingProof === "function"
      && typeof completedView.getLastCompletedPayload === "function"
      && typeof completedView.getLastCompletedRows === "function"
    ) {
      const completedPayload = completedView.getLastCompletedPayload();
      const completedRows = completedView.getLastCompletedRows();
      completedView.renderCompletedPendingProof(completedPayload, completedRows, lastPendingPayload);
      if (typeof completedView.renderCompletedRealMediaProof === "function" && typeof completedView.getLastCompletedPendingProofRows === "function") {
        const completedPendingProofRows = completedView.getLastCompletedPendingProofRows();
        completedView.renderCompletedRealMediaProof(
          completedPayload,
          completedRows,
          completedPendingProofRows,
          lastPendingPayload,
        );
        if (typeof completedView.renderCompletedPilotEvidencePacket === "function") {
          completedView.renderCompletedPilotEvidencePacket(
            completedPayload,
            completedRows,
            completedPendingProofRows,
            lastPendingPayload,
          );
        }
      }
    }
  }

  function renderPendingDrainProgress(snapshot = {}) {
    const bars = Array.isArray(snapshot?.progress_bars)
      ? snapshot.progress_bars.filter((bar) => ["pending_drain", "publish_copy", "publish_output"].includes(String(bar?.id || "")))
      : [];
    window.mediaPipelineProgressView?.renderProgressBarsInto?.(
      "pending-drain-progress-bars",
      bars,
      snapshot,
      "No active pending-publish drain progress loaded.",
      { compact: "pendingDrain" },
    );
  }

  function getLastPendingPublishPayload() {
    return lastPendingPayload;
  }

  function getLastPendingPublishRows() {
    return lastPendingRows.slice();
  }

  function pendingRecoverySignatureValue(value) {
    return String(value ?? "").replace(/[\\/]+/g, "/").trim().toLowerCase();
  }

  function pendingRecoveryPlanSignature(pending = lastPendingPayload, rows = lastPendingRows) {
    const payload = pending && typeof pending === "object" ? pending : {};
    const rowList = Array.isArray(rows) ? rows : [];
    const rowParts = rowList.map((row, index) => [
      pendingRecoverySignatureValue(pendingRowKey(row) || `row-${index}`),
      pendingRecoverySignatureValue(row?.manifest_path),
      pendingRecoverySignatureValue(row?.local_file),
      pendingRecoverySignatureValue(row?.server_out),
      pendingRecoverySignatureValue(row?.source_path),
      pendingRecoverySignatureValue(row?.state),
      pendingRecoverySignatureValue(row?.diagnostic_status),
      pendingRecoverySignatureValue(row?.diagnostic_severity),
      pendingRecoverySignatureValue(row?.drain_recommendation),
      pendingRecoverySignatureValue(row?.operator_trust_state),
    ].join("::")).sort();
    return [
      pendingRecoverySignatureValue(payload.pending_root),
      String(payload.count || rowList.length || 0),
      String(payload.ready_count || 0),
      String(payload.issue_count || 0),
      String(payload.health_count || 0),
      String(payload.missing_local_count || 0),
      rowParts.join("||"),
    ].join("|");
  }

  function clearStalePendingRecoveryPlan(pending, rows) {
    const currentSignature = pendingRecoveryPlanSignature(pending, rows);
    const hasPlanRows = Array.isArray(lastPendingRecoveryPlanRows) && lastPendingRecoveryPlanRows.length > 0;
    const hasRecoveryState = hasPlanRows || Boolean(lastPendingRecoveryPlanSignature || selectedPendingRecoveryPlanKey);
    if (!hasRecoveryState || (hasPlanRows && lastPendingRecoveryPlanSignature === currentSignature)) {
      return currentSignature;
    }
    lastPendingRecoveryPlanRows = [];
    lastPendingRecoveryPlanSignature = "";
    selectedPendingRecoveryPlanKey = "";
    setText("pending-recovery-plan-status", "Recovery dry-run cleared because Pending Publish evidence changed. Build a fresh dry-run before drain review.");
    renderPendingRecoveryPlanRows([]);
    return currentSignature;
  }

  function pendingFileInventoryPayload(pending) {
    const inventory = pending?.file_inventory;
    return inventory && typeof inventory === "object" ? inventory : {};
  }

  function pendingFileInventoryRows(pending) {
    const rows = pendingFileInventoryPayload(pending).rows;
    return Array.isArray(rows) ? rows.filter(Boolean) : [];
  }

  function pendingFileInventoryStatus(pending) {
    const inventory = pendingFileInventoryPayload(pending);
    const rows = pendingFileInventoryRows(pending);
    if (inventory.error) return "Unavailable";
    if (inventory.exists === false) return "No pending root";
    if (!Number(inventory.total_count || rows.length || 0)) return "No parked files";
    if (inventory.truncated) return `${rows.length} shown / ${inventory.total_count} files`;
    if (Number(inventory.orphan_payload_count || 0) > 0) return "Review files";
    return "Inventory loaded";
  }

  function pendingFileInventorySummaryLines(pending) {
    const inventory = pendingFileInventoryPayload(pending);
    const summary = Array.isArray(inventory.summary_lines) ? inventory.summary_lines.filter(Boolean) : [];
    if (summary.length) return summary;
    if (inventory.error) {
      return [
        "Pending parked file inventory:",
        `Status: unavailable`,
        `Error: ${inventory.error}`,
        "Safe action: open Diagnostics > Pending Publish and Run Logs before drain, cleanup, rerun, or manual move.",
      ];
    }
    return [
      "Pending parked file inventory:",
      `Pending root: ${inventory.pending_root || pending?.pending_root || "not reported"}`,
      `Files scanned: ${inventory.total_count || 0}`,
      `Rows shown: ${inventory.shown_count || pendingFileInventoryRows(pending).length || 0}`,
      `Manifest files: ${inventory.manifest_count || 0}`,
      `Payload-like files: ${inventory.payload_like_count || 0}`,
      `Referenced payload files: ${inventory.referenced_payload_count || 0}`,
      `Unreferenced payload files: ${inventory.orphan_payload_count || 0}`,
      `Total size: ${inventory.total_size_text || "0 B"}`,
      "Evidence boundary: directory listing only; file bytes were not read and no files were changed.",
    ];
  }

  function pendingFileInventoryRowStatus(item) {
    const role = String(item?.role || "").toLowerCase();
    const status = String(item?.status || "").toLowerCase();
    if (role === "scan_error" || status === "error") return "failed";
    if (role === "orphan_payload" || status === "unreferenced") return "warning";
    if (role === "manifest") return "changed";
    return "match";
  }

  function renderPendingFileInventory(pending) {
    setText("pending-file-inventory-status", pendingFileInventoryStatus(pending || {}));
    setText("pending-file-inventory-summary", pendingFileInventorySummaryLines(pending || {}).join("\n"));
    const tbody = byId("pending-file-inventory-rows");
    if (!tbody) return;
    const rows = pendingFileInventoryRows(pending || {});
    const scrollSnapshot = tableScrollSnapshot(tbody);
    if (!rows.length) {
      clearRows(tbody, 6, "No parked files were reported by the backend pending directory scan.");
      updateTableStatusLegend("pending-file-inventory-legend", tbody, "Parked file inventory rows");
      deferTableScrollRestore(scrollSnapshot);
      return;
    }
    tbody.replaceChildren();
    rows.slice(0, 250).forEach((item) => {
      const row = document.createElement("tr");
      row.dataset.status = pendingFileInventoryRowStatus(item);
      const pathRaw = item.path || item.name || "";
      const pathDisplay = typeof shortenPath === "function" ? shortenPath(pathRaw, 56) : pathRaw;
      appendCells(row, [
        item.kind || "unknown",
        item.role || item.status || "unknown",
        item.size_text || "",
        item.modified_at || "",
        pathDisplay,
        item.evidence || "",
      ], [null, null, "num", null, "path-cell", null]);
      const cells = row.querySelectorAll("td");
      if (typeof setCellStatusChip === "function") setCellStatusChip(cells[0], item.kind || "unknown", row.dataset.status);
      if (cells[4] && pathRaw) cells[4].title = pathRaw;
      tbody.appendChild(row);
    });
    updateTableStatusLegend("pending-file-inventory-legend", tbody, "Parked file inventory rows");
    deferTableScrollRestore(scrollSnapshot);
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

  function capturePendingSelectionScroll() {
    return window.mediaPipelineDom?.captureScrollablePositions?.() || null;
  }

  function restorePendingSelectionScroll(snapshot) {
    if (snapshot) window.mediaPipelineDom?.restoreScrollablePositions?.(snapshot);
  }

  function selectPendingRow(item) {
    const scrollSnapshot = capturePendingSelectionScroll();
    selectedPendingRowKey = pendingRowKey(item);
    renderPendingDetail(item || null);
    renderPendingReviewDigest(lastPendingPayload, lastPendingRows);
    renderPendingDrainEvidence(lastPendingPayload, lastPendingRows);
    renderPendingBackendDrainScopePreview(lastPendingPayload, lastPendingRows, lastPendingSnapshot, typeof getCommandHistory === "function" ? getCommandHistory() : []);
    renderPendingDrainDecisionChecklist(lastPendingPayload, lastPendingRows, lastPendingSnapshot, typeof getCommandHistory === "function" ? getCommandHistory() : []);
    renderPendingRows();
    renderPendingRepairManifestControls();
    renderPendingRepairOrphanControls();
    restorePendingSelectionScroll(scrollSnapshot);
  }

  function pendingDrainOverviewState(status) {
    const normalized = String(status || "").toLowerCase();
    if (normalized.includes("do not") || normalized.includes("blocked")) return "blocked";
    if (normalized.includes("incomplete") || normalized.includes("not evaluated")) return "validation-needed";
    if (normalized.includes("review")) return "warning";
    if (normalized.includes("ready")) return "ok";
    return "unknown";
  }

  function pendingRowPresentationStatus(item) {
    const tableStatus = pendingTableRowStatus(item);
    const evidenceClass = pendingEvidenceClass(item);
    const severity = String(item?.diagnostic_severity || "").toLowerCase();
    const recommendation = String(item?.drain_recommendation || "").toLowerCase();
    if (["completed", "skipped", "running", "publishing", "queued"].includes(tableStatus)) return tableStatus;
    if (tableStatus === "failed" || severity === "error" || item?.error) return "failed";
    if (
      tableStatus === "blocked"
      || recommendation === "do_not_drain"
      || ["do-not-drain", "diagnostic-error", "manifest-invalid", "missing-payload"].includes(evidenceClass)
    ) {
      return "blocked";
    }
    if (["missing-sidecar", "orphan-payload"].includes(evidenceClass)) return "validation-needed";
    if (tableStatus === "warning" || evidenceClass === "review" || item?.ready_to_drain === false) return "warning";
    if (["ready", "match"].includes(tableStatus) || item?.ready_to_drain === true || evidenceClass === "ready-evidence") return "ready";
    return tableStatus || "unknown";
  }

  function pendingRowPresentationLabel(item) {
    const status = pendingRowPresentationStatus(item);
    if (status === "completed") return "Drained";
    if (["running", "publishing", "queued"].includes(status)) return "Draining";
    if (status === "skipped") return "Skipped";
    if (status === "failed") return "Failed";
    if (status === "blocked") return "Blocked";
    if (status === "validation-needed") return "Evidence missing";
    if (status === "warning") return "Needs review";
    if (["ready", "match"].includes(status)) return "Ready";
    if (status === "unavailable") return "Unavailable";
    if (status === "empty") return "No row";
    return "Unknown";
  }

  function pendingRowReasonText(item) {
    const candidates = [
      item?.issue_summary,
      item?.primary_concern,
      item?.error,
      item?.operator_guidance,
      item?.safe_next_action,
      item?.drain_recommendation,
      item?.diagnostic_status,
    ];
    const reason = candidates.map((value) => String(value || "").trim()).find(Boolean);
    if (reason) return reason;
    if (item?.ready_to_drain === true) return "No focused blocker in the loaded backend scan.";
    return "";
  }

  function pendingRowUpdatedText(item) {
    return String(
      item?.updated_at
      || item?.modified_at
      || item?.last_seen_at
      || item?.parked_at_display
      || item?.parked_at
      || item?.age_text
      || ""
    );
  }

  function pendingPathDisplay(path, limit = 44) {
    const value = String(path || "");
    return typeof shortenPath === "function" ? shortenPath(value, limit) : value;
  }

  function pendingDrainSummaryCounts(payload) {
    const summary = pendingDrainSummaryPayload(payload || {});
    const items = pendingDrainSummaryItems(summary);
    const counts = {
      drained: Number(summary.succeeded_count || 0) + Number(summary.already_published_count || 0),
      failed: Number(summary.error_count || 0),
      skipped: Number(summary.skipped_count || 0),
    };
    if (!items.length) return counts;
    const itemCounts = items.reduce((acc, item) => {
      const status = String(item?.status || item?.result || "").trim().toLowerCase();
      if (["succeeded", "success", "already_published", "published", "completed"].includes(status)) acc.drained += 1;
      else if (["skipped", "deferred"].includes(status)) acc.skipped += 1;
      else if (status || item?.error) acc.failed += 1;
      return acc;
    }, { drained: 0, failed: 0, skipped: 0 });
    return {
      drained: counts.drained || itemCounts.drained,
      failed: counts.failed || itemCounts.failed,
      skipped: counts.skipped || itemCounts.skipped,
    };
  }

  function pendingActionCenterTriage(rows, payload = lastPendingPayload) {
    const rowList = Array.isArray(rows) ? rows : [];
    const counts = rowList.reduce((acc, row) => {
      const status = pendingRowPresentationStatus(row);
      if (status === "completed") {
        acc.drained += 1;
      } else if (status === "skipped") {
        acc.skipped += 1;
      } else if (["running", "publishing", "queued"].includes(status)) {
        acc.draining += 1;
      } else if (status === "failed") {
        acc.failed += 1;
      } else if (status === "blocked") {
        acc.blocked += 1;
      } else if (status === "validation-needed") {
        acc.evidence += 1;
      } else if (["warning", "unknown", "unavailable", "empty"].includes(status)) {
        acc.review += 1;
      } else {
        acc.ready += 1;
      }
      return acc;
    }, { ready: 0, review: 0, evidence: 0, blocked: 0, failed: 0, drained: 0, skipped: 0, draining: 0 });
    const summaryCounts = pendingDrainSummaryCounts(payload || {});
    counts.drained += summaryCounts.drained;
    counts.failed += summaryCounts.failed;
    counts.skipped += summaryCounts.skipped;
    return counts;
  }

  function pendingActionCenterOutcome(payload, rowList, decisionStatus, validationStatus, guard, triage) {
    const rows = Array.isArray(rowList) ? rowList : [];
    const counts = triage || pendingActionCenterTriage(rows, payload);
    const normalizedDecision = String(decisionStatus || "").toLowerCase();
    const warnings = Array.isArray(payload?.warnings) ? payload.warnings.filter(Boolean) : [];
    if (payload?.error) {
      return {
        action: "Open Diagnostics first",
        reason: `Pending Publish scan is unavailable: ${payload.error}`,
        detail: "Do not drain until backend state, Run Logs, and Last Stderr explain the scan failure.",
        state: "blocked",
      };
    }
    if (payload?.exists === false) {
      return {
        action: "No drain needed",
        reason: "No pending-publish folder exists yet.",
        detail: "Check Completed and Run Logs before reprocessing if an expected output is missing.",
        state: "empty",
      };
    }
    if (!rows.length) {
      if (counts.drained) {
        return {
          action: `Review ${counts.drained} drained file${counts.drained === 1 ? "" : "s"}`,
          reason: "No current parked rows are loaded; the latest drain summary has completed evidence.",
          detail: "Compare Last Drain and Completed proof before assuming final placement for a specific title.",
          state: "empty",
        };
      }
      return {
        action: "No parked outputs",
        reason: "Pending Publish has no parked rows loaded.",
        detail: "An empty pending view is not proof of publish; compare Completed and drain-summary evidence when an output is missing.",
        state: "empty",
      };
    }
    if (counts.failed) {
      return {
        action: `Investigate ${counts.failed} failed file${counts.failed === 1 ? "" : "s"}`,
        reason: `${counts.failed} failed drain or row error signal${counts.failed === 1 ? "" : "s"} loaded.`,
        detail: "Open the failed row, Last Drain, Run Logs, and Last Stderr before another drain attempt.",
        state: "blocked",
      };
    }
    if (counts.blocked || normalizedDecision.includes("do not")) {
      return {
        action: "Resolve blockers before drain",
        reason: counts.blocked
          ? `${counts.blocked} blocked row${counts.blocked === 1 ? "" : "s"} or do-not-drain checkpoint found.`
          : "A do-not-drain checkpoint is active in the drain decision checklist.",
        detail: "Show blockers, select the highest-risk row, and inspect backend-selected diagnostics in Advanced before another drain attempt.",
        state: "blocked",
      };
    }
    if (counts.evidence || normalizedDecision.includes("incomplete") || normalizedDecision.includes("not evaluated")) {
      return {
        action: "Review evidence gaps",
        reason: counts.evidence
          ? `${counts.evidence} row${counts.evidence === 1 ? "" : "s"} have payload, sidecar, or parked-output evidence gaps.`
          : "Drain evidence is incomplete or has not been evaluated.",
        detail: "Show evidence gaps, then use Advanced recovery or diagnostics only when the row evidence explains a concrete problem.",
        state: "validation-needed",
      };
    }
    if (counts.review || validationStatus === "Review" || warnings.length || guard?.review_required) {
      return {
        action: "Review before drain",
        reason: counts.review
          ? `${counts.review} row${counts.review === 1 ? "" : "s"} or checklist signal require read-first review.`
          : "The drain guard requires explicit read-first review before submission.",
        detail: "Use the review filter and selected-row detail first; open Advanced diagnostics only when a row needs deeper evidence.",
        state: "warning",
      };
    }
    return {
      action: `Drain ${rows.length} parked file${rows.length === 1 ? "" : "s"}`,
      reason: `${counts.ready} row${counts.ready === 1 ? " has" : "s have"} no focused blocker in the loaded backend scan.`,
      detail: "Submit the backend-owned drain when the current parked rows show no local blockers; the backend still validates the full parked scope.",
      state: "ok",
    };
  }

  function setPendingActionCount(id, count, state, label) {
    const node = byId(id);
    if (!node) return;
    node.textContent = String(count || 0);
    const button = node.closest("button");
    if (button) {
      button.dataset.state = state || "empty";
      button.title = `${label}: ${count || 0}`;
      button.setAttribute("aria-label", `Show ${label.toLowerCase()}: ${count || 0}`);
    }
  }

  function renderPendingActionCenter(pending = lastPendingPayload, rows = lastPendingRows, snapshot = lastPendingSnapshot, entries, overview = {}) {
    const payload = pending && typeof pending === "object" ? pending : {};
    const rowList = Array.isArray(rows) ? rows : [];
    const entryList = Array.isArray(entries) ? entries : (typeof getCommandHistory === "function" ? getCommandHistory() : []);
    const decisionStatus = overview.decisionStatus || pendingDrainDecisionStatus(payload, rowList, snapshot || {}, entryList);
    const validationStatus = overview.validationStatus || pendingValidationStatus(payload, rowList);
    const filterScope = overview.filterScope || pendingCurrentFilterScope(rowList);
    const guard = overview.guard || pendingDrainGuardState(payload, rowList, snapshot || {}, entryList);
    const triage = pendingActionCenterTriage(rowList, payload);
    const outcome = pendingActionCenterOutcome(payload, rowList, decisionStatus, validationStatus, guard, triage);
    const state = pendingDrainOverviewState(decisionStatus) === "unknown" ? outcome.state : pendingDrainOverviewState(decisionStatus);

    setText("pending-action-status", decisionStatus || "Not loaded");
    const statusNode = byId("pending-action-status");
    if (statusNode) statusNode.dataset.state = state;
    setText("pending-action-subtitle", `Rows loaded: ${rowList.length}; visible after filters: ${filterScope.visibleCount ?? rowList.length}/${filterScope.totalCount ?? rowList.length}; backend drain scope is not narrowed by display filters.`);
    setText("pending-action-primary", outcome.action);
    setText("pending-action-reason", outcome.reason);
    setPendingActionCount("pending-action-ready-count", triage.ready, triage.ready ? "ok" : "empty", "Ready to drain rows");
    setPendingActionCount("pending-action-review-count", triage.review, triage.review ? "warning" : "empty", "Rows needing review");
    setPendingActionCount("pending-action-evidence-count", triage.evidence, triage.evidence ? "validation-needed" : "empty", "Rows with missing evidence");
    setPendingActionCount("pending-action-blocked-count", triage.blocked, triage.blocked ? "blocked" : "empty", "Blocked rows");
    setPendingActionCount("pending-action-failed-count", triage.failed, triage.failed ? "blocked" : "empty", "Failed rows");
    setPendingActionCount("pending-action-drained-count", triage.drained, triage.drained ? "completed" : "empty", "Drained rows in latest summary");

    const drainButton = byId("pending-action-drain-button");
    if (drainButton) {
      const drainLabel = rowList.length
        ? `Drain ${rowList.length} parked file${rowList.length === 1 ? "" : "s"}`
        : "Drain Parked Outputs";
      drainButton.disabled = !guard?.allowed;
      drainButton.textContent = guard?.allowed
        ? guard.review_required && rowList.length ? `Drain after review (${rowList.length})` : drainLabel
        : "Drain Blocked";
      drainButton.title = guard?.allowed ? guard.confirm_message || outcome.detail : guard?.message || outcome.detail;
      drainButton.dataset.state = guard?.allowed ? guard.review_required ? "warning" : "ok" : "blocked";
    }

    setText("pending-action-detail", [
      "Pending Publish action center:",
      `Next action: ${outcome.action}`,
      `Why: ${outcome.reason}`,
      `Drain decision: ${decisionStatus || "not loaded"}; checklist: ${validationStatus || "not loaded"}; backend button guard: ${guard?.allowed ? guard.review_required ? "review confirmation required" : "allowed" : "blocked"}.`,
      `Triage filters: ready=${triage.ready}; review=${triage.review}; evidence missing=${triage.evidence}; blocked=${triage.blocked}; failed=${triage.failed}; drained summary=${triage.drained}.`,
      `Visible table scope: ${filterScope.visibleCount ?? rowList.length}/${filterScope.totalCount ?? rowList.length}; hidden blocked/review=${filterScope.hiddenBlockedCount || 0}/${filterScope.hiddenReviewCount || 0}.`,
      outcome.detail,
      "Boundary: this action center can only update local filters, refresh backend evidence, or submit the backend-owned drain command.",
    ].join("\n"));
  }

  function renderPendingDrainOverview(pending = lastPendingPayload, rows = lastPendingRows, snapshot = lastPendingSnapshot, entries) {
    const payload = pending && typeof pending === "object" ? pending : {};
    const rowList = Array.isArray(rows) ? rows : [];
    const entryList = Array.isArray(entries) ? entries : (typeof getCommandHistory === "function" ? getCommandHistory() : []);
    const decisionStatus = pendingDrainDecisionStatus(payload, rowList, snapshot || {}, entryList);
    const validationStatus = pendingValidationStatus(payload, rowList);
    const filterScope = pendingCurrentFilterScope(rowList);
    const guard = pendingDrainGuardState(payload, rowList, snapshot || {}, entryList);
    const chips = byId("pending-drain-decision-chips");
    if (chips && window.mediaPipelineDom?.makeStatusChip) {
      chips.replaceChildren(
        window.mediaPipelineDom.makeStatusChip("Blocked", decisionStatus === "Do not drain" ? "blocked" : "normal"),
        window.mediaPipelineDom.makeStatusChip("Review", decisionStatus === "Review first" ? "warning" : "normal"),
        window.mediaPipelineDom.makeStatusChip("Need evidence", decisionStatus === "Evidence incomplete" || decisionStatus === "Not evaluated" ? "validation-needed" : "normal"),
        window.mediaPipelineDom.makeStatusChip("Ready", decisionStatus === "Ready-looking" ? "ok" : "normal"),
      );
    }
    setText("pending-drain-overview", [
      "Pending Publish drain decision:",
      `Operator outcome: ${decisionStatus}.`,
      `Publish checklist: ${validationStatus}.`,
      `Rows loaded: ${rowList.length}; visible table scope: ${filterScope.visibleCount ?? rowList.length}/${filterScope.totalCount ?? rowList.length}; hidden blocked=${filterScope.hiddenBlockedCount || 0}; hidden review=${filterScope.hiddenReviewCount || 0}.`,
      `Button guard: ${guard.allowed ? (guard.review_required ? "review confirmation required" : "allowed by local evidence") : "blocked by local evidence"}.`,
      "Command boundary: Drain Parked Outputs remains the backend-owned validation and movement path; this overview cannot move, publish, repair, delete, rewrite, or mark outputs complete.",
    ].join("\n"));
    const overviewNode = byId("pending-drain-overview");
    if (overviewNode) overviewNode.dataset.state = pendingDrainOverviewState(decisionStatus);
    renderPendingActionCenter(payload, rowList, snapshot || {}, entryList, { decisionStatus, validationStatus, filterScope, guard });
  }

  function applyPendingActionFilter(kind) {
    const normalized = String(kind || "all").trim().toLowerCase();
    const filter = byId("pending-filter");
    const status = byId("pending-status-filter");
    const investigation = byId("pending-investigation-filter");
    if (filter) filter.value = "";
    if (status) status.value = "all";
    if (investigation) investigation.value = "all";
    if (normalized === "ready") {
      if (status) status.value = "ready";
      if (investigation) investigation.value = "ready_to_drain";
    } else if (normalized === "review") {
      if (status) status.value = "warning";
    } else if (normalized === "evidence") {
      if (investigation) investigation.value = "evidence_missing";
    } else if (normalized === "blocked") {
      if (status) status.value = "blocked";
      if (investigation) investigation.value = "do_not_drain";
    } else if (normalized === "failed") {
      if (status) status.value = "failed";
      if (investigation) investigation.value = "failed";
    } else if (normalized === "drained") {
      if (status) status.value = "completed";
      if (investigation) investigation.value = "drained";
    } else if (normalized === "payloads") {
      if (filter) filter.value = "payload";
    }
    renderPendingRows();
    const labels = {
      ready: "Showing ready-looking pending rows. Backend drain scope is unchanged.",
      review: "Showing pending rows that need review. Backend drain scope is unchanged.",
      evidence: "Showing pending rows with missing payload, sidecar, or manifest evidence. Backend drain scope is unchanged.",
      blocked: "Showing do-not-drain or blocked pending rows. Backend drain scope is unchanged.",
      failed: "Showing failed pending rows and failed latest-summary entries when present. Backend drain scope is unchanged.",
      drained: "Showing rows with drained/completed evidence when present. Current pending rows remain the backend source of truth.",
      payloads: "Showing rows matching payload evidence. Backend drain scope is unchanged.",
    };
    setText("pending-action-feedback", labels[normalized] || "Pending Publish filters cleared. Backend drain scope is unchanged.");
  }

  function triggerPendingActionDrain() {
    const drainButton = byId("pending-drain-button");
    if (!drainButton) {
      setText("pending-action-feedback", "The backend drain button is not available on this page.");
      return;
    }
    if (drainButton.disabled) {
      setText("pending-action-feedback", "Drain is currently busy or unavailable. Wait for the active command to finish, then refresh evidence.");
      return;
    }
    setText("pending-action-feedback", "Opening the existing backend-owned Drain Parked Outputs confirmation.");
    drainButton.click();
  }

  function focusPendingQuickLinkTarget(selector) {
    const target = selector ? document.querySelector(selector) : null;
    if (!target) return false;
    target.scrollIntoView?.({ block: "center", inline: "nearest" });
    if (!target.matches?.("a[href], button, input, select, textarea, summary, [tabindex]")) {
      target.setAttribute("tabindex", "-1");
    }
    target.focus?.({ preventScroll: true });
    return true;
  }

  function setPendingTextFilter(text) {
    const filter = byId("pending-filter");
    const status = byId("pending-status-filter");
    const investigation = byId("pending-investigation-filter");
    if (filter) filter.value = text || "";
    if (status) status.value = "all";
    if (investigation) investigation.value = "all";
    renderPendingRows();
    setText("pending-action-feedback", `Showing Pending Publish rows matching "${text}". Backend drain scope is unchanged.`);
  }

  function activateQuickLink(action) {
    const normalized = String(action || "").trim().toLowerCase();
    if (normalized === "manifests") {
      setPendingTextFilter("manifest");
      return focusPendingQuickLinkTarget("#pending-rows");
    }
    if (normalized === "payloads") {
      setPendingTextFilter("payload");
      return focusPendingQuickLinkTarget("#pending-rows");
    }
    if (normalized === "review" || normalized === "health") {
      applyPendingActionFilter("review");
      return focusPendingQuickLinkTarget("#pending-rows");
    }
    if (normalized === "summary" || normalized === "size") {
      return focusPendingQuickLinkTarget("#pending-summary");
    }
    if (normalized === "action") {
      return focusPendingQuickLinkTarget(".pending-action-center");
    }
    return true;
  }

  function triggerPendingActionRefresh() {
    const refreshButton = document.querySelector('[data-page-refresh-button="pending"]');
    if (refreshButton && typeof refreshButton.click === "function") {
      setText("pending-action-feedback", "Refreshing backend Pending Publish evidence.");
      refreshButton.click();
      return;
    }
    if (typeof window.refreshAllNow === "function") {
      setText("pending-action-feedback", "Refreshing backend evidence from the app refresh command.");
      window.refreshAllNow();
      return;
    }
    setText("pending-action-feedback", "Refresh command is not available yet.");
  }

  function initPendingActionCenterEvents() {
    if (pendingActionCenterEventsInitialized) return;
    if (typeof document === "undefined" || typeof document.querySelectorAll !== "function") return;
    document.querySelectorAll("[data-pending-action-filter]").forEach((button) => {
      button.addEventListener("click", () => applyPendingActionFilter(button.dataset.pendingActionFilter || "all"));
    });
    const drainButton = byId("pending-action-drain-button");
    if (drainButton) drainButton.addEventListener("click", triggerPendingActionDrain);
    const refreshButton = byId("pending-action-refresh-button");
    if (refreshButton) refreshButton.addEventListener("click", triggerPendingActionRefresh);
    const blockersButton = byId("pending-action-blockers-button");
    if (blockersButton) blockersButton.addEventListener("click", () => applyPendingActionFilter("blocked"));
    pendingActionCenterEventsInitialized = true;
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

  function renderPendingRows() {
    const filterText = byId("pending-filter")?.value || "";
    const statusFilter = byId("pending-status-filter")?.value || "all";
    const investigationFilter = byId("pending-investigation-filter")?.value || "all";
    const textRows = filterRows(lastPendingRows, filterText, PENDING_FILTER_FIELDS);
    const statusRows = typeof filterRowsByStatus === "function" ? filterRowsByStatus(textRows, statusFilter, pendingRowPresentationStatus) : textRows;
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
        statusOf: pendingRowPresentationStatus,
        limit: 250,
        decisionName: "publish/drain",
        guardrail: PENDING_READ_ONLY_BOUNDARY,
      }).join("\n"));
    }
    const tbody = byId("pending-rows");
    const scrollSnapshot = tableScrollSnapshot(tbody);
    if (!rows.length) {
      clearRows(tbody, 7, lastPendingRows.length ? "No pending publish rows match the filter." : lastPendingEmptyMessage);
      updateTableStatusLegend("pending-table-legend", tbody, "Pending publish rows");
      if (selectedPendingRowKey) renderPendingDetail(getSelectedPendingRow());
      renderPendingDrainActionConfidence(lastPendingPayload, lastPendingRows, lastPendingSnapshot, typeof getCommandHistory === "function" ? getCommandHistory() : []);
      renderPendingBackendDrainScopePreview(lastPendingPayload, lastPendingRows, lastPendingSnapshot, typeof getCommandHistory === "function" ? getCommandHistory() : []);
      renderPendingDrainDecisionChecklist(lastPendingPayload, lastPendingRows, lastPendingSnapshot, typeof getCommandHistory === "function" ? getCommandHistory() : []);
      renderPendingDrainOverview(lastPendingPayload, lastPendingRows, lastPendingSnapshot, typeof getCommandHistory === "function" ? getCommandHistory() : []);
      renderPendingDrainGuard(lastPendingPayload, lastPendingRows, lastPendingSnapshot, typeof getCommandHistory === "function" ? getCommandHistory() : []);
      renderPendingRepairManifestControls();
      renderPendingRepairOrphanControls();
      deferTableScrollRestore(scrollSnapshot);
      return;
    }
    tbody.replaceChildren();
    rows.slice(0, renderLimit).forEach((item) => {
      const row = document.createElement("tr");
      const key = pendingRowKey(item);
      row.dataset.rowKey = key;
      row.dataset.status = pendingRowPresentationStatus(item);
      const localFileDisplay = pendingPathDisplay(item.local_file || item.source_path || "", 42);
      const manifestDisplay = pendingPathDisplay(item.manifest_path || item.row_key || "", 34);
      const serverOutDisplay = pendingPathDisplay(item.server_out || "", 42);
      const statusText = pendingRowPresentationLabel(item);
      appendCells(row, [
        statusText,
        localFileDisplay,
        manifestDisplay,
        serverOutDisplay,
        item.size_text || "",
        pendingRowUpdatedText(item),
        pendingRowReasonText(item),
      ], [null, "path-cell", "path-cell", "path-cell", "num", null, null]);
      const pendingCells = row.querySelectorAll("td");
      const stateCell = pendingCells[0] || row.children?.[0];
      if (typeof setCellStatusChip === "function") setCellStatusChip(stateCell, statusText, row.dataset.status);
      if (pendingCells[1] && (item.local_file || item.source_path)) pendingCells[1].title = item.local_file || item.source_path;
      if (pendingCells[2] && item.manifest_path) pendingCells[2].title = item.manifest_path;
      if (pendingCells[3] && item.server_out) pendingCells[3].title = item.server_out;
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
    renderPendingDrainOverview(lastPendingPayload, lastPendingRows, lastPendingSnapshot, typeof getCommandHistory === "function" ? getCommandHistory() : []);
    renderPendingDrainGuard(lastPendingPayload, lastPendingRows, lastPendingSnapshot, typeof getCommandHistory === "function" ? getCommandHistory() : []);
    renderPendingRepairManifestControls();
    renderPendingRepairOrphanControls();
    deferTableScrollRestore(scrollSnapshot);
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
