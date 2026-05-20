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
    const summary = [
      pending.pending_root ? `Pending root: ${pending.pending_root}` : "",
      pending.exists ? "" : "Pending root does not exist.",
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

  function pendingInventoryProgressBars(pending) {
    const payload = pending && typeof pending === "object" ? pending : {};
    const progress = payload.inventory_progress && typeof payload.inventory_progress === "object" ? payload.inventory_progress : {};
    if (Array.isArray(progress.progress_bars)) return progress.progress_bars.filter(Boolean);
    if (Array.isArray(payload.progress_bars)) return payload.progress_bars.filter(Boolean);
    return [];
  }

  function renderPendingInventoryProgress(pending) {
    if (typeof renderProgressBarsInto !== "function") return;
    const payload = pending && typeof pending === "object" ? pending : {};
    const progress = payload.inventory_progress && typeof payload.inventory_progress === "object" ? payload.inventory_progress : {};
    renderProgressBarsInto("pending-inventory-progress-bars", pendingInventoryProgressBars(payload), progress, "No pending inventory progress loaded.");
  }

  function getLastPendingPublishPayload() {
    return lastPendingPayload;
  }

  function getLastPendingPublishRows() {
    return lastPendingRows.slice();
  }

  function pendingEmptyStateMessage(pending, rows) {
    if (pending.error) {
      return `Pending publish unavailable: ${pending.error}. Open Diagnostics > Pending Publish and Run Logs.`;
    }
    const warnings = Array.isArray(pending.warnings) ? pending.warnings.filter(Boolean) : [];
    if (warnings.length) {
      return `Pending publish loaded with warning: ${warnings.join(" | ")}`;
    }
    if (!pending.exists) {
      return "No pending-publish folder exists yet. This is normal until Deferred Publish parks an output.";
    }
    if (!rows.length) {
      return "No parked outputs are waiting to publish. If an output is missing, check completed history and Run Logs before reprocessing.";
    }
    return "No pending publish rows available.";
  }

  function pendingStateCounts(rows) {
    const counts = {};
    rows.forEach((row) => {
      const key = String(row?.state || "unknown").trim() || "unknown";
      counts[key] = (counts[key] || 0) + 1;
    });
    return counts;
  }

  function formatPendingStateCounts(rows) {
    const counts = pendingStateCounts(rows);
    return Object.keys(counts).sort().map((key) => `${key}=${counts[key]}`).join(", ") || "none";
  }

  function pendingRowHasHealthIssue(row) {
    const missingSidecars = Number(row?.missing_sidecar_count || 0);
    const state = String(row?.state || "").toLowerCase();
    return Boolean(
      row?.diagnostic_severity === "error" ||
      row?.drain_recommendation === "do_not_drain" ||
      row?.error ||
      row?.local_exists === false ||
      missingSidecars > 0 ||
      state === "orphan_payload" ||
      state === "invalid_manifest" ||
      state === "unreadable_manifest"
    );
  }

  function pendingPublishReadinessStatus(pending, rows) {
    const rowList = Array.isArray(rows) ? rows : [];
    if (pending?.error) return "Unavailable";
    if (!pending?.exists) return "No pending root";
    if (!rowList.length) return "Empty";
    if (rowList.some(pendingRowHasHealthIssue) || Number(pending?.health_count || 0) > 0 || Number(pending?.missing_local_count || 0) > 0) {
      return "Review before drain";
    }
    const warnings = Array.isArray(pending?.warnings) ? pending.warnings.filter(Boolean) : [];
    if (warnings.length) return "Warnings";
    return "Ready-looking";
  }

  function pendingPublishReadinessLines(pending, rows) {
    const payload = pending || {};
    const rowList = Array.isArray(rows) ? rows : [];
    if (payload.error) {
      return [
        `Status: unavailable`,
        `Error: ${payload.error}`,
        "Safe action: open Diagnostics > Pending Publish and Run Logs before retrying a drain.",
        "Backend drain command remains the source of truth; this summary does not authorize publish.",
      ];
    }
    const issueRows = rowList.filter(pendingRowHasHealthIssue);
    const warnings = Array.isArray(payload.warnings) ? payload.warnings.filter(Boolean) : [];
    const lines = [
      `Pending root: ${payload.pending_root || "not reported"}`,
      `Root exists: ${payload.exists ? "yes" : "no"}`,
      `Parked manifests: ${payload.count || rowList.length || 0}`,
      `Payloads: ${payload.payload_count || 0}`,
      `Health rows: ${payload.health_count || 0}`,
      `Missing payload references: ${payload.missing_local_count || 0}`,
      `Ready rows: ${payload.ready_count || 0}`,
      `Issue rows: ${payload.issue_count || issueRows.length}`,
      `Missing sidecars: ${payload.missing_sidecar_count || 0}`,
      `Rows needing review: ${issueRows.length}`,
      `States: ${formatPendingStateCounts(rowList)}`,
      `Diagnostic statuses: ${pendingFormatCounts(payload.diagnostic_status_counts)}`,
      `Diagnostic severities: ${pendingFormatCounts(payload.diagnostic_severity_counts)}`,
      `Backend trust states: ${pendingFormatCounts(payload.operator_trust_state_counts)}`,
      `Recovery classes: ${pendingFormatCounts(payload.recovery_class_counts)}`,
      `Suggested open targets: ${pendingFormatCounts(payload.recommended_open_target_counts)}`,
      `Available open targets: ${pendingFormatCounts(payload.available_open_target_counts)}`,
    ];
    lines.push("", ...pendingRecoverySummaryLines(payload));
    if (warnings.length) {
      lines.push("", "Warning(s):");
      warnings.slice(0, 5).forEach((warning) => lines.push(`- ${warning}`));
    }
    lines.push("");
    if (!payload.exists) {
      lines.push("Safe action: no drain is needed until Deferred Publish parks outputs.");
    } else if (!rowList.length) {
      lines.push("Safe action: no parked outputs are waiting. Do not reprocess solely because this list is empty; check Completed History and Run Logs first.");
    } else if (issueRows.length || Number(payload.health_count || 0) > 0 || Number(payload.missing_local_count || 0) > 0) {
      lines.push("Safe action: review row issues before publishing. Open the selected manifest/local payload/destination using backend-selected open buttons.");
    } else if (warnings.length) {
      lines.push("Safe action: drain may be possible, but review warnings first.");
    } else {
      lines.push("Safe action: pending rows look ready for Publish Parked Outputs.");
    }
    lines.push("Backend drain command remains the source of truth; this summary does not bypass backend validation or publish checks.");
    return lines;
  }

  function renderPendingPublishReadiness(pending, rows) {
    const rowList = Array.isArray(rows) ? rows : [];
    setText("pending-publish-readiness-status", pendingPublishReadinessStatus(pending || {}, rowList));
    setText("pending-publish-readiness", pendingPublishReadinessLines(pending || {}, rowList).join("\n"));
  }

  function pendingWorkflowStatus(pending, rows) {
    const payload = pending || {};
    const rowList = Array.isArray(rows) ? rows : [];
    const warnings = Array.isArray(payload.warnings) ? payload.warnings.filter(Boolean) : [];
    if (payload.error) return "Diagnostics first";
    if (payload.exists === false) return "No pending root";
    if (!rowList.length) return "No drain";
    if (pendingValidationStatus(payload, rowList) === "Do not drain") return "Do not drain";
    if (Number(payload.issue_count || 0) > 0 || rowList.some(pendingRowHasHealthIssue)) return "Review rows";
    if (warnings.length) return "Review context";
    return "Drain path clear";
  }

  function pendingWorkflowLines(pending, rows) {
    const payload = pending || {};
    const rowList = Array.isArray(rows) ? rows : [];
    const warnings = Array.isArray(payload.warnings) ? payload.warnings.filter(Boolean) : [];
    const issueRows = rowList.filter(pendingRowHasHealthIssue);
    const lines = [
      "Cross-page workflow: Pending Publish",
      `Drain readiness: ${pendingPublishReadinessStatus(payload, rowList)}`,
      `Pending validation: ${pendingValidationStatus(payload, rowList)}`,
      `Rows loaded: ${payload.count || rowList.length || 0}`,
      `Payload rows: ${payload.payload_count || 0}`,
      `Ready rows: ${payload.ready_count || 0}`,
      `Issue rows: ${payload.issue_count || issueRows.length}`,
      `Health rows: ${payload.health_count || 0}`,
      `Missing payload references: ${payload.missing_local_count || 0}`,
    ];
    lines.push("");
    if (payload.error) {
      lines.push("Next step: open Diagnostics > State Artifact Summary, Pending Publish, Run Logs, and Last Stderr before another publish attempt.");
    } else if (payload.exists === false) {
      lines.push("Next step: no pending-publish root exists. Check Completed before rerun and do not assume outputs were lost solely from an empty pending view.");
    } else if (!rowList.length) {
      lines.push("Next step: no parked outputs are waiting. If an expected output is missing, inspect Completed and Run Logs before reprocessing.");
    } else if (pendingValidationStatus(payload, rowList) === "Do not drain") {
      lines.push("Next step: do not drain. Select the issue row, use Pending Diagnostics Cross-Links, and inspect manifest/payload/sidecar/log evidence first.");
    } else if (Number(payload.issue_count || 0) > 0 || issueRows.length || warnings.length) {
      lines.push("Next step: review issue/warning rows and Last Stderr before using Publish Parked Outputs.");
    } else {
      lines.push("Next step: pending publish context is coherent. Publish Parked Outputs remains the backend-owned drain command.");
    }
    lines.push("Owning pages: Pending Publish for parked output safety, Completed for output proof, Queue before rerun, Diagnostics for artifacts/logs.");
    lines.push("Mutation guardrail: this workflow panel is read-only. Publish Parked Outputs remains backend-owned.");
    return lines;
  }

  function renderPendingWorkflow(pending, rows) {
    const rowList = Array.isArray(rows) ? rows : [];
    setText("pending-workflow-status", pendingWorkflowStatus(pending || {}, rowList));
    setText("pending-workflow", pendingWorkflowLines(pending || {}, rowList).join("\n"));
  }

  function pendingReviewRowReasons(row) {
    const reasons = [];
    const severity = String(row?.diagnostic_severity || "").toLowerCase();
    const recommendation = String(row?.drain_recommendation || "").toLowerCase();
    const state = String(row?.state || "").toLowerCase();
    if (severity === "error") reasons.push("diagnostic error");
    if (severity === "warning") reasons.push("diagnostic warning");
    if (recommendation === "do_not_drain") reasons.push("do-not-drain recommendation");
    if (row?.local_exists === false) reasons.push("missing local payload");
    if (Number(row?.missing_sidecar_count || 0) > 0) reasons.push(`missing sidecars: ${row.missing_sidecar_count}`);
    if (["orphan_payload", "invalid_manifest", "unreadable_manifest"].includes(state)) reasons.push(`state: ${row.state}`);
    if (row?.error) reasons.push(`error: ${row.error}`);
    if (row?.issue_summary) reasons.push(`issue: ${row.issue_summary}`);
    if (String(row?.operator_trust_state || "").toLowerCase().includes("review") || String(row?.operator_trust_state || "").toLowerCase().includes("drain")) {
      reasons.push(`trust state: ${row.operator_trust_state}`);
    }
    if (row?.recovery_class && String(row.recovery_class).toLowerCase() !== "ready") reasons.push(`recovery: ${row.recovery_class}`);
    if (row?.primary_concern) reasons.push(`primary concern: ${row.primary_concern}`);
    return reasons.filter(Boolean);
  }

  function pendingReviewRows(pending, rows) {
    const rowList = Array.isArray(rows) ? rows : [];
    return rowList
      .map((row, index) => ({ row, index, reasons: pendingReviewRowReasons(row) }))
      .filter((entry) => entry.reasons.length)
      .sort((a, b) => {
        const rank = (entry) => String(entry.row?.drain_recommendation || "").toLowerCase() === "do_not_drain" ? 0
          : String(entry.row?.diagnostic_severity || "").toLowerCase() === "error" ? 1
            : entry.row?.local_exists === false ? 2
              : String(entry.row?.diagnostic_severity || "").toLowerCase() === "warning" ? 3
                : 4;
        return rank(a) - rank(b) || a.index - b.index;
      });
  }

  function pendingReviewStatus(pending, rows) {
    const payload = pending || {};
    const rowList = Array.isArray(rows) ? rows : [];
    if (payload.error) return "Diagnostics first";
    if (payload.exists === false) return "No pending root";
    const reviewRows = pendingReviewRows(payload, rowList);
    if (reviewRows.length) return `${reviewRows.length} row${reviewRows.length === 1 ? "" : "s"} need review`;
    if (!rowList.length) return "No parked rows";
    return "No flagged rows";
  }

  function pendingReviewBoardLines(pending, rows) {
    const payload = pending || {};
    const rowList = Array.isArray(rows) ? rows : [];
    const reviewRows = pendingReviewRows(payload, rowList);
    const lines = [
      "Operator review board: Pending Publish",
      `Page status: ${pendingWorkflowStatus(payload, rowList)}`,
      `Rows loaded: ${payload.count || rowList.length || 0}`,
      `Flagged rows: ${reviewRows.length}`,
      `Ready / issue rows: ${payload.ready_count || 0} / ${payload.issue_count || reviewRows.length}`,
      `Backend trust states: ${pendingFormatCounts(payload.operator_trust_state_counts)}`,
      `Diagnostic severities: ${pendingFormatCounts(payload.diagnostic_severity_counts)}`,
      `Recovery classes: ${pendingFormatCounts(payload.recovery_class_counts)}`,
    ];
    lines.push("");
    if (payload.error) {
      lines.push("First action: open Diagnostics > Pending Publish, Run Logs, and Last Stderr. Do not drain while the pending view is unavailable.");
    } else if (payload.exists === false) {
      lines.push("First action: no pending-publish root exists. Check Completed before rerun; do not assume a missing output is lost from this empty view alone.");
    } else if (reviewRows.length) {
      lines.push("First rows to inspect before drain:");
      reviewRows.slice(0, 6).forEach(({ row, reasons }, index) => {
        const label = row.local_file || row.manifest_path || row.server_out || `row ${index + 1}`;
        const action = row.safe_next_action || row.operator_guidance || row.recovery_action || "build a selected-row recovery dry-run plan and inspect backend-selected targets before drain.";
        lines.push(`- ${label}: ${reasons.slice(0, 3).join("; ")}. Safe action: ${action}`);
      });
      if (reviewRows.length > 6) lines.push(`- ${reviewRows.length - 6} more flagged row(s) not shown.`);
    } else if (!rowList.length) {
      lines.push("First action: no parked outputs are waiting. If expected outputs are missing, inspect Completed and Run Logs before reprocessing.");
    } else {
      lines.push("First action: no pending rows are locally flagged. Publish Parked Outputs remains the backend-owned validation and drain path.");
    }
    lines.push("Mutation guardrail: this board is read-only; drain, repair, rewrite, move, delete, and publish actions remain backend-owned.");
    return lines;
  }

  function pendingReviewDigestStatus(entry) {
    const row = entry?.row || {};
    const severity = String(row.diagnostic_severity || "").toLowerCase();
    const recommendation = String(row.drain_recommendation || "").toLowerCase();
    if (recommendation === "do_not_drain" || severity === "error" || row.local_exists === false || row.error) return "blocked";
    if (severity === "warning" || entry?.reasons?.length || row.ready_to_drain === false) return "warning";
    return "match";
  }

  function pendingReviewDigestAction(row) {
    return row?.safe_next_action
      || row?.operator_guidance
      || row?.recovery_action
      || "Select this row, inspect Pending detail and Diagnostics Cross-Links, then use backend recovery dry-run before drain if anything is unclear.";
  }

  function pendingTableRowStatus(item) {
    const severity = String(item?.diagnostic_severity || "").toLowerCase();
    const recommendation = String(item?.drain_recommendation || "").toLowerCase();
    if (recommendation === "do_not_drain" || severity === "error" || item?.local_exists === false || item?.error) return "failed";
    if (severity === "warning" || item?.ready_to_drain === false || pendingReviewRowReasons(item).length) return "warning";
    return "match";
  }

  function pendingInvestigationFilterLabel(value) {
    const normalized = String(value || "all").trim().toLowerCase();
    const labels = {
      all: "all signals",
      do_not_drain: "do not drain",
      missing_payload: "missing payload",
      invalid_manifest: "invalid manifest",
      missing_sidecars: "missing sidecars",
      orphan_payload: "orphan payload",
      ready_to_drain: "ready to drain",
    };
    return labels[normalized] || normalized.replace(/_/g, " ");
  }

  function pendingMatchesInvestigationFilter(item, filter) {
    const normalized = String(filter || "all").trim().toLowerCase();
    const state = String(item?.state || item?.diagnostic_status || "").toLowerCase();
    const recommendation = String(item?.drain_recommendation || "").toLowerCase();
    if (!normalized || normalized === "all") return true;
    if (normalized === "do_not_drain") return recommendation === "do_not_drain" || pendingTableRowStatus(item) === "failed";
    if (normalized === "missing_payload") return item?.local_exists === false || Number(item?.missing_local_count || 0) > 0 || state.includes("missing");
    if (normalized === "invalid_manifest") return state.includes("invalid_manifest") || state.includes("unreadable_manifest") || String(item?.error || "").toLowerCase().includes("manifest");
    if (normalized === "missing_sidecars") return Number(item?.missing_sidecar_count || 0) > 0;
    if (normalized === "orphan_payload") return state.includes("orphan_payload");
    if (normalized === "ready_to_drain") return item?.ready_to_drain !== false && recommendation !== "do_not_drain" && pendingTableRowStatus(item) === "match";
    return true;
  }

  function pendingFocusedInvestigationLabels(item) {
    const filters = ["do_not_drain", "missing_payload", "invalid_manifest", "missing_sidecars", "orphan_payload", "ready_to_drain"];
    return filters.filter((filter) => pendingMatchesInvestigationFilter(item, filter)).map(pendingInvestigationFilterLabel);
  }

  function pendingFilterVisibilityLines(item) {
    if (!item) return [];
    const filterText = byId("pending-filter")?.value || "";
    const statusFilter = byId("pending-status-filter")?.value || "all";
    const investigationFilter = byId("pending-investigation-filter")?.value || "all";
    const textMatches = typeof filterRows === "function" ? filterRows([item], filterText, PENDING_FILTER_FIELDS).length > 0 : true;
    const status = pendingTableRowStatus(item);
    const statusMatches = typeof tableStatusMatchesFilter === "function" ? tableStatusMatchesFilter(status, statusFilter) : true;
    const normalizedInvestigation = String(investigationFilter || "all").trim().toLowerCase();
    const investigationMatches = !normalizedInvestigation || normalizedInvestigation === "all" || pendingMatchesInvestigationFilter(item, normalizedInvestigation);
    const activeFilters = Boolean(String(filterText || "").trim()) || String(statusFilter || "all").toLowerCase() !== "all" || normalizedInvestigation !== "all";
    const reasons = [];
    if (!textMatches) reasons.push(`text filter="${String(filterText || "").trim()}"`);
    if (!statusMatches) reasons.push(`status filter=${typeof tableStatusFilterLabel === "function" ? tableStatusFilterLabel(statusFilter) : statusFilter}`);
    if (!investigationMatches) reasons.push(`investigation view=${pendingInvestigationFilterLabel(investigationFilter)}`);
    const lines = [
      "Current filter visibility:",
      `Selected row visible in table: ${textMatches && statusMatches && investigationMatches ? "yes" : "no"}`,
      `Active filters: ${activeFilters ? `text=${String(filterText || "").trim() || "none"}; status=${typeof tableStatusFilterLabel === "function" ? tableStatusFilterLabel(statusFilter) : statusFilter}; view=${pendingInvestigationFilterLabel(investigationFilter)}` : "none"}`,
    ];
    if (reasons.length) {
      lines.push(`Hidden by current filters: ${reasons.join("; ")}.`);
      lines.push("Operator note: selected-row detail remains visible for review, but the table is currently hiding this row.");
    } else if (activeFilters) {
      lines.push("Operator note: this selected row is still visible under the active display filters.");
    } else {
      lines.push("Operator note: no Pending Publish display filter is hiding this selected row.");
    }
    return lines;
  }

  function pendingSelectedQuickSignalLines(item) {
    if (!item) {
      return [
        "Selected pending-row quick signal:",
        "Select a pending publish row to see status, focused investigation views, and current-filter visibility.",
      ];
    }
    const focusedViews = pendingFocusedInvestigationLabels(item);
    const primaryConcern = item.primary_concern
      || item.issue_summary
      || item.error
      || item.operator_guidance
      || item.drain_recommendation
      || "no focused pending-publish blocker reported";
    return [
      "Selected pending-row quick signal:",
      `Table status: ${pendingTableRowStatus(item)}`,
      `Focused views: ${focusedViews.length ? focusedViews.join(", ") : "none beyond all signals"}`,
      `Primary concern: ${primaryConcern}`,
      ...pendingFilterVisibilityLines(item),
    ];
  }

  function pendingInvestigationSignalLines(item) {
    if (!item) {
      return [
        "Investigation view matches:",
        "- Select a pending publish row to see which Pending Publish investigation views would include it.",
      ];
    }
    const state = String(item.state || item.diagnostic_status || "").trim();
    const signals = [];
    if (pendingMatchesInvestigationFilter(item, "do_not_drain")) {
      signals.push(`- do not drain: ${item.drain_recommendation || item.diagnostic_severity || item.error || "backend marked row unsafe to drain"}`);
    }
    if (pendingMatchesInvestigationFilter(item, "missing_payload")) {
      signals.push(`- missing payload: ${item.local_file || item.issue_summary || "local parked payload is missing"}`);
    }
    if (pendingMatchesInvestigationFilter(item, "invalid_manifest")) {
      signals.push(`- invalid manifest: ${item.manifest_path || item.error || state || "manifest is invalid or unreadable"}`);
    }
    if (pendingMatchesInvestigationFilter(item, "missing_sidecars")) {
      signals.push(`- missing sidecars: ${item.missing_sidecar_count || "reported by pending scan"}`);
    }
    if (pendingMatchesInvestigationFilter(item, "orphan_payload")) {
      signals.push(`- orphan payload: ${item.local_file || state || "payload exists without a valid manifest"}`);
    }
    if (pendingMatchesInvestigationFilter(item, "ready_to_drain")) {
      signals.push(`- ready to drain: ${item.drain_recommendation || "row has no focused blocker in the loaded pending scan"}`);
    }
    if (!signals.length) {
      signals.push("- none beyond all signals: this row is not currently included by a focused Pending Publish investigation view.");
    }
    signals.push("Operator note: investigation views are display filters only and do not change backend drain scope.");
    return ["Investigation view matches:", ...signals];
  }

  function renderPendingReviewDigest(pending, rows) {
    const tbody = byId("pending-review-rows");
    if (!tbody) return;
    const payload = pending || {};
    const rowList = Array.isArray(rows) ? rows : [];
    const reviewRows = pendingReviewRows(payload, rowList).slice(0, 12);
    if (!reviewRows.length) {
      clearRows(
        tbody,
        5,
        payload.error
          ? "Pending publish scan is unavailable. Use Diagnostics > Pending Publish, Run Logs, and Last Stderr before drain."
          : payload.exists === false
            ? "No pending-publish root exists. Check Completed and Run Logs before assuming a missing output is lost."
            : rowList.length
              ? "No pending rows are flagged by the loaded backend payload. Publish Parked Outputs remains backend-owned validation."
              : "No parked outputs are waiting. Cross-check Completed before reprocessing expected outputs.",
      );
      updateTableStatusLegend("pending-review-legend", tbody, "Pending publish review rows");
      return;
    }
    tbody.replaceChildren();
    reviewRows.forEach((entry) => {
      const item = entry.row || {};
      const row = document.createElement("tr");
      const key = pendingRowKey(item);
      row.dataset.rowKey = key;
      row.dataset.status = pendingReviewDigestStatus(entry);
      const reviewPathRaw = item.local_file || item.manifest_path || item.server_out || item.source_path || "";
      const reviewPathDisplay = typeof shortenPath === "function" ? shortenPath(reviewPathRaw, 40) : reviewPathRaw;
      appendCells(row, [
        item.recovery_class || item.diagnostic_status || item.state || row.dataset.status,
        item.drain_recommendation || "review",
        reviewPathDisplay,
        entry.reasons.slice(0, 3).join("; "),
        pendingReviewDigestAction(item),
      ], [null, null, "path-cell", null, null]);
      if (reviewPathRaw) {
        const reviewCells = row.querySelectorAll("td");
        if (reviewCells[2]) reviewCells[2].title = reviewPathRaw;
      }
      makeRowSelectable(row, () => selectPendingRow(item), {
        selected: Boolean(key && key === selectedPendingRowKey),
        label: `Pending publish review row ${item.local_file || item.server_out || item.manifest_path || ""}`,
      });
      tbody.appendChild(row);
    });
    updateTableStatusLegend("pending-review-legend", tbody, "Pending publish review rows");
  }

  function renderPendingReviewBoard(pending, rows) {
    const rowList = Array.isArray(rows) ? rows : [];
    setText("pending-review-status", pendingReviewStatus(pending || {}, rowList));
    setText("pending-review-board", pendingReviewBoardLines(pending || {}, rowList).join("\n"));
    renderPendingReviewDigest(pending || {}, rowList);
  }

  function pendingFormatCounts(value) {
    const entries = value && typeof value === "object" ? Object.entries(value) : [];
    if (!entries.length) return "none";
    return entries.map(([key, count]) => `${key || "unknown"}=${count}`).join(", ");
  }

  function pendingRecoverySummaryPayload(pending) {
    const summary = pending?.recovery_summary;
    return summary && typeof summary === "object" ? summary : {};
  }

  function pendingRecoverySummaryLines(pending) {
    const summary = pendingRecoverySummaryPayload(pending);
    if (!Object.keys(summary).length) {
      return [
        "Backend recovery summary:",
        "- Status: not reported",
        "- Primary action: use row diagnostics and backend validation before drain.",
      ];
    }
    const lines = [
      "Backend recovery summary:",
      `- Status: ${summary.status || "unknown"}`,
      `- Blockers/review/ready: ${summary.blocker_count || 0} / ${summary.review_count || 0} / ${summary.ready_count || 0}`,
      `- Recovery classes: ${pendingFormatCounts(summary.class_counts)}`,
      `- Primary action: ${summary.primary_action || "Review pending publish diagnostics before drain."}`,
    ];
    const steps = Array.isArray(summary.next_steps) ? summary.next_steps.filter(Boolean) : [];
    if (steps.length) {
      lines.push("- Next steps:");
      steps.slice(0, 5).forEach((step) => lines.push(`  - ${step}`));
    }
    return lines;
  }

  function pendingRiskStatus(pending, rows) {
    const rowList = Array.isArray(rows) ? rows : [];
    if (pending?.error) return "Unavailable";
    if (!pending?.exists) return "No root";
    if (!rowList.length) return "Empty";
    if (Number(pending?.issue_count || 0) > 0 || Number(pending?.health_count || 0) > 0 || rowList.some(pendingRowHasHealthIssue)) return "Review";
    return "Ready";
  }

  function pendingRiskLines(pending, rows) {
    const payload = pending || {};
    const rowList = Array.isArray(rows) ? rows : [];
    const issues = rowList.filter(pendingRowHasHealthIssue);
    const lines = [
      `Rows loaded: ${payload.count || rowList.length || 0}`,
      `Ready rows: ${payload.ready_count || 0}`,
      `Issue rows: ${payload.issue_count || issues.length}`,
      `States: ${pendingFormatCounts(payload.state_counts)}`,
      `Routes: ${pendingFormatCounts(payload.route_counts)}`,
      `Diagnostic statuses: ${pendingFormatCounts(payload.diagnostic_status_counts)}`,
      `Diagnostic severities: ${pendingFormatCounts(payload.diagnostic_severity_counts)}`,
      `Recovery classes: ${pendingFormatCounts(payload.recovery_class_counts)}`,
      `Suggested open targets: ${pendingFormatCounts(payload.recommended_open_target_counts)}`,
      `Available open targets: ${pendingFormatCounts(payload.available_open_target_counts)}`,
      `Orphan payloads: ${payload.orphan_payload_count || 0}`,
      `Invalid/unreadable manifests: ${payload.invalid_manifest_count || 0}`,
      `Missing payload references: ${payload.missing_local_count || 0}`,
      `Missing sidecars: ${payload.missing_sidecar_count || 0}`,
    ];
    if (issues.length) {
      lines.push("", "First issue rows:");
      issues.slice(0, 5).forEach((row) => {
        lines.push(`- ${row.local_file || row.manifest_path || row.server_out || row.row_key || "(row)"}: ${row.issue_summary || row.error || row.state || "review required"}`);
      });
    }
    lines.push("", ...pendingRecoverySummaryLines(payload));
    lines.push("", "Operator note: drain readiness is advisory. The backend Publish Parked Outputs command still performs authoritative validation.");
    return lines;
  }

  function renderPendingRiskBreakdown(pending, rows) {
    const rowList = Array.isArray(rows) ? rows : [];
    setText("pending-risk-status", pendingRiskStatus(pending || {}, rowList));
    setText("pending-risk", pendingRiskLines(pending || {}, rowList).join("\n"));
  }

  function pendingValidationStatus(pending, rows) {
    const payload = pending || {};
    const rowList = Array.isArray(rows) ? rows : [];
    if (payload.error) return "Unavailable";
    if (payload.exists === false) return "No root";
    if (!rowList.length) return "Empty";
    const doNotDrainRows = rowList.filter((row) => String(row?.drain_recommendation || "").toLowerCase() === "do_not_drain");
    const severeRows = rowList.filter((row) => String(row?.diagnostic_severity || "").toLowerCase() === "error");
    const invalidRows = rowList.filter((row) => ["invalid_manifest", "unreadable_manifest"].includes(String(row?.state || "").toLowerCase()));
    const missingPayloadRows = rowList.filter((row) => row?.local_exists === false);
    const missingSidecarRows = rowList.filter((row) => Number(row?.missing_sidecar_count || 0) > 0);
    if (
      doNotDrainRows.length ||
      severeRows.length ||
      invalidRows.length ||
      missingPayloadRows.length ||
      missingSidecarRows.length ||
      Number(payload.health_count || 0) > 0 ||
      Number(payload.missing_local_count || 0) > 0
    ) {
      return "Do not drain";
    }
    const warnings = Array.isArray(payload.warnings) ? payload.warnings.filter(Boolean) : [];
    if (warnings.length || Number(payload.issue_count || 0) > 0 || rowList.some(pendingRowHasHealthIssue)) return "Review";
    return "Ready";
  }

  function pendingValidationChecklistLines(pending, rows) {
    const payload = pending || {};
    const rowList = Array.isArray(rows) ? rows : [];
    const warnings = Array.isArray(payload.warnings) ? payload.warnings.filter(Boolean) : [];
    const issueRows = rowList.filter(pendingRowHasHealthIssue);
    const doNotDrainRows = rowList.filter((row) => String(row?.drain_recommendation || "").toLowerCase() === "do_not_drain");
    const severeRows = rowList.filter((row) => String(row?.diagnostic_severity || "").toLowerCase() === "error");
    const invalidRows = rowList.filter((row) => ["invalid_manifest", "unreadable_manifest"].includes(String(row?.state || "").toLowerCase()));
    const missingPayloadRows = rowList.filter((row) => row?.local_exists === false);
    const missingSidecarRows = rowList.filter((row) => Number(row?.missing_sidecar_count || 0) > 0);
    const existsText = payload.exists === true ? "yes" : payload.exists === false ? "no" : "unknown";
    if (payload.error) {
      return [
        "Real-media validation checklist:",
        `Status: unavailable`,
        `Error: ${payload.error}`,
        "Operator action: open Diagnostics > Pending Publish and Run Logs before another publish attempt.",
        "Mutation guardrail: this checklist is read-only and cannot drain, repair, delete, rewrite, or publish files.",
      ];
    }
    const lines = [
      "Real-media validation checklist:",
      `Pending root: ${payload.pending_root || "not reported"}`,
      `Pending root exists: ${existsText}`,
      `Parked manifest rows: ${payload.count || rowList.length || 0}`,
      `Payload rows: ${payload.payload_count || 0}`,
      `Ready rows: ${payload.ready_count || 0}`,
      `Issue rows: ${payload.issue_count || issueRows.length}`,
      `Health rows: ${payload.health_count || 0}`,
      `Do-not-drain rows: ${doNotDrainRows.length}`,
      `Diagnostic error rows: ${severeRows.length}`,
      `Invalid/unreadable manifest rows: ${payload.invalid_manifest_count || invalidRows.length}`,
      `Missing payload references: ${payload.missing_local_count || missingPayloadRows.length}`,
      `Missing sidecar rows: ${payload.missing_sidecar_count || missingSidecarRows.length}`,
      `Orphan payloads: ${payload.orphan_payload_count || 0}`,
      `States: ${pendingFormatCounts(payload.state_counts || pendingStateCounts(rowList))}`,
      `Diagnostic statuses: ${pendingFormatCounts(payload.diagnostic_status_counts)}`,
      `Diagnostic severities: ${pendingFormatCounts(payload.diagnostic_severity_counts)}`,
      `Recovery classes: ${pendingFormatCounts(payload.recovery_class_counts)}`,
      `Suggested open targets: ${pendingFormatCounts(payload.recommended_open_target_counts)}`,
      `Available open targets: ${pendingFormatCounts(payload.available_open_target_counts)}`,
      `Last drain summary: ${pendingDrainSummaryStatus(payload)}`,
    ];
    lines.push("", ...pendingRecoverySummaryLines(payload));
    if (warnings.length) {
      lines.push("", "Warning(s):");
      warnings.slice(0, 5).forEach((warning) => lines.push(`- ${warning}`));
    }
    lines.push("");
    if (payload.exists === false) {
      lines.push("Operator action: no pending-publish folder exists yet. This is normal until Deferred Publish parks an output.");
    } else if (!rowList.length) {
      lines.push("Operator action: no parked outputs are waiting. Cross-check Completed History and Run Logs before reprocessing anything.");
    } else if (doNotDrainRows.length || severeRows.length || invalidRows.length || missingPayloadRows.length || missingSidecarRows.length) {
      lines.push("Operator action: do not drain yet. Select issue rows and use backend-selected open/diagnostic actions to inspect manifests, payloads, sidecars, and logs.");
    } else if (warnings.length || Number(payload.issue_count || 0) > 0 || issueRows.length) {
      lines.push("Operator action: review warnings and issue rows before publishing parked outputs.");
    } else {
      lines.push("Operator action: rows appear ready, but Publish Parked Outputs remains the authoritative backend validation path.");
    }
    lines.push("Mutation guardrail: this checklist is read-only and cannot drain, repair, delete, rewrite, or publish files.");
    return lines;
  }

  function renderPendingValidation(pending, rows) {
    const rowList = Array.isArray(rows) ? rows : [];
    setText("pending-validation-status", pendingValidationStatus(pending || {}, rowList));
    setText("pending-validation", pendingValidationChecklistLines(pending || {}, rowList).join("\n"));
  }

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

  function pendingRowReviewChecklistLines(item) {
    if (!item) {
      return [
        "Selected pending-row review checklist:",
        "Select a pending publish row to see drain safety, payload, sidecar, manifest, and diagnostics guidance.",
      ];
    }
    const status = String(item.diagnostic_status || "").toLowerCase();
    const severity = String(item.diagnostic_severity || "").toLowerCase();
    const recommendation = String(item.drain_recommendation || "review").toLowerCase();
    const state = String(item.state || "").toLowerCase();
    const missingSidecars = Number(item.missing_sidecar_count || 0);
    const blockers = [];
    if (recommendation === "do_not_drain") blockers.push("backend marked do_not_drain");
    if (severity === "error") blockers.push("diagnostic severity is error");
    if (item.local_exists === false) blockers.push("local payload missing");
    if (missingSidecars > 0) blockers.push(`${missingSidecars} missing sidecar${missingSidecars === 1 ? "" : "s"}`);
    if (["invalid_manifest", "unreadable_manifest"].includes(state) || ["invalid_manifest", "unreadable_manifest"].includes(status)) blockers.push("manifest unreadable or invalid");
    if (state === "orphan_payload" || status === "orphan_payload") blockers.push("orphan payload");
    if (item.error) blockers.push("row error");
    const backendTrustState = String(item.operator_trust_state || "").trim();
    const lines = [
      "Selected pending-row review checklist:",
      `Row state: ${backendTrustState || (blockers.length ? "do-not-drain" : recommendation === "ready" || item.ready_to_drain ? "ready-looking" : "review")}`,
      `Diagnostic status: ${item.diagnostic_status || "unknown"}`,
      `Diagnostic severity: ${item.diagnostic_severity || "unknown"}`,
      `Drain recommendation: ${item.drain_recommendation || "review"}`,
      `Recovery class: ${item.recovery_class || "manual_review"}`,
      `Health blockers: ${blockers.length ? blockers.join(", ") : "none"}`,
      `Evidence fields: ${pendingListText(item.evidence_fields)}`,
      `Recommended open targets: ${pendingListText(item.recommended_open_targets)}`,
    ];
    if (item.issue_summary) lines.push(`Issue summary: ${item.issue_summary}`);
    if (item.error) lines.push(`Row error: ${item.error}`);
    if (item.operator_guidance) {
      lines.push(`Operator action: ${item.operator_guidance}`);
    }
    if (item.recovery_action) {
      lines.push(`Recovery action: ${item.recovery_action}`);
    } else if (blockers.length) {
      lines.push("Operator action: do not drain this row yet; inspect backend-selected payload/manifest/sidecar targets and logs.");
    } else if (recommendation === "review") {
      lines.push("Operator action: review row targets and diagnostics before publishing parked outputs.");
    } else {
      lines.push("Operator action: row looks ready, but Publish Parked Outputs remains the authoritative backend validation path.");
    }
    lines.push("Mutation guardrail: selected-row detail is read-only and cannot drain, repair, delete, rewrite, or publish files.");
    return lines;
  }

  function pendingSelectedAtAGlanceState(item) {
    if (!item) return "unknown";
    const status = String(item.diagnostic_status || "").toLowerCase();
    const severity = String(item.diagnostic_severity || "").toLowerCase();
    const recommendation = String(item.drain_recommendation || "review").toLowerCase();
    const state = String(item.state || "").toLowerCase();
    const missingSidecars = Number(item.missing_sidecar_count || 0);
    const blocked = recommendation === "do_not_drain"
      || severity === "error"
      || item.local_exists === false
      || ["invalid_manifest", "unreadable_manifest"].includes(state)
      || ["invalid_manifest", "unreadable_manifest"].includes(status)
      || Boolean(item.error);
    if (blocked) return "blocked";
    if (missingSidecars > 0 || state === "orphan_payload" || status === "orphan_payload" || recommendation === "review" || !item.ready_to_drain) return "warning";
    return "ready";
  }

  function pendingSelectedAtAGlanceStatus(item) {
    const state = pendingSelectedAtAGlanceState(item);
    if (state === "blocked") return "Do not drain";
    if (state === "warning") return "Review";
    if (state === "ready") return "Ready-looking";
    return "No selection";
  }

  function pendingSelectedVisibilitySummary(item) {
    const lines = pendingFilterVisibilityLines(item);
    return lines
      .filter((line) => /^Selected row visible|^Active filters|^Hidden by current filters/.test(String(line || "")))
      .join(" ");
  }

  function pendingSelectedAtAGlanceLines(item) {
    if (!item) {
      return [
        "Selected Pending Publish row: none",
        "Next step: select a pending row to review parked payload, manifest, sidecars, Completed correlation, and drain guidance.",
        "Authority: this summary is read-only. Backend Publish Parked Outputs remains the only path that can move parked files.",
      ];
    }
    const concern = item.primary_concern
      || item.issue_summary
      || item.error
      || item.operator_guidance
      || "no primary concern reported";
    const safeAction = item.safe_next_action
      || item.operator_guidance
      || item.recovery_action
      || (pendingSelectedAtAGlanceState(item) === "ready"
        ? "Use only backend-owned Publish Parked Outputs after page-level drain validation agrees."
        : "Inspect pending manifest/payload/sidecars, Completed correlation, Last Stderr, and Run Logs before drain.");
    return [
      `Selected Pending Publish row: ${item.local_file || item.server_out || item.manifest_path || "(unnamed row)"}`,
      `Trust/status: ${item.operator_trust_state || item.diagnostic_status || item.state || "not reported"}; at-a-glance=${pendingSelectedAtAGlanceStatus(item)}`,
      `Drain proof: recommendation=${item.drain_recommendation || "review"}; ready=${item.ready_to_drain ? "yes" : "no"}; recovery=${item.recovery_class || "manual_review"}`,
      `Primary concern: ${concern}`,
      `Safe next step: ${safeAction}`,
      `Filter visibility: ${pendingSelectedVisibilitySummary(item) || "not evaluated"}`,
      "Authority: this summary is read-only. It cannot drain, repair, move, delete, rewrite manifests, publish, or touch media files.",
    ];
  }

  function renderPendingSelectedAtAGlance(item) {
    const status = pendingSelectedAtAGlanceStatus(item);
    setText("pending-selected-status", status);
    const statusNode = byId("pending-selected-status");
    if (statusNode) statusNode.dataset.state = pendingSelectedAtAGlanceState(item);
    setText("pending-selected-summary", pendingSelectedAtAGlanceLines(item).join("\n"));
  }

  function pendingRowIssueDigestLines(item) {
    if (!item) return [];
    const status = String(item.diagnostic_status || "").toLowerCase();
    const severity = String(item.diagnostic_severity || "").toLowerCase();
    const recommendation = String(item.drain_recommendation || "review").toLowerCase();
    const state = String(item.state || "").toLowerCase();
    const missingSidecars = Number(item.missing_sidecar_count || 0);
    const issues = [];
    if (recommendation === "do_not_drain") issues.push("backend marked do_not_drain");
    if (severity === "error") issues.push("diagnostic severity is error");
    if (item.local_exists === false) issues.push("local payload missing");
    if (missingSidecars > 0) issues.push(`${missingSidecars} missing sidecar${missingSidecars === 1 ? "" : "s"}`);
    if (["invalid_manifest", "unreadable_manifest"].includes(state) || ["invalid_manifest", "unreadable_manifest"].includes(status)) issues.push("manifest unreadable or invalid");
    if (state === "orphan_payload" || status === "orphan_payload") issues.push("orphan payload");
    if (item.error) issues.push(`row error: ${item.error}`);
    const level = recommendation === "do_not_drain" || severity === "error" ? "do-not-drain" : issues.length ? "review" : item.ready_to_drain ? "ready-looking" : "review";
    const backendTrustState = String(item.operator_trust_state || "").trim();
    const lines = [
      "Selected pending issue digest:",
      `Issue level: ${backendTrustState || level}`,
      `Recovery class: ${item.recovery_class || "manual_review"}`,
      `Primary issue(s): ${issues.length ? issues.join("; ") : "none reported by pending scan"}`,
      `Evidence fields: ${pendingListText(item.evidence_fields)}`,
      `Proof to inspect: manifest=${item.manifest_path || "not reported"}; payload=${item.local_file || "not reported"}; destination=${item.server_out || "not reported"}`,
      `Drain proof: ${item.drain_recommendation || "review"}; status=${item.diagnostic_status || "unknown"}; severity=${item.diagnostic_severity || "unknown"}`,
    ];
    if (recommendation === "do_not_drain" || severity === "error") {
      lines.push("Safe next action: do not drain; inspect row targets, Pending Publish diagnostics, Last Stderr, and Run Logs first.");
    } else if (issues.length) {
      lines.push("Safe next action: review row targets before Publish Parked Outputs; backend drain validation remains authoritative.");
    } else if (item.ready_to_drain) {
      lines.push("Safe next action: row looks ready, but use only the backend-owned Publish Parked Outputs command to move files.");
    } else {
      lines.push("Safe next action: treat this row as review-needed until backend diagnostics or a refreshed pending scan marks it ready.");
    }
    return lines;
  }

  function pendingRowCombinedReviewPlanLines(item) {
    if (!item) return [];
    const status = String(item.diagnostic_status || "").toLowerCase();
    const severity = String(item.diagnostic_severity || "").toLowerCase();
    const recommendation = String(item.drain_recommendation || "review").toLowerCase();
    const state = String(item.state || "").toLowerCase();
    const missingSidecars = Number(item.missing_sidecar_count || 0);
    const signals = [];
    if (recommendation === "do_not_drain") signals.push("backend do_not_drain");
    if (severity === "error") signals.push("diagnostic error");
    if (item.local_exists === false) signals.push("missing payload");
    if (missingSidecars > 0) signals.push(`${missingSidecars} missing sidecar${missingSidecars === 1 ? "" : "s"}`);
    if (["invalid_manifest", "unreadable_manifest"].includes(state) || ["invalid_manifest", "unreadable_manifest"].includes(status)) signals.push("invalid/unreadable manifest");
    if (state === "orphan_payload" || status === "orphan_payload") signals.push("orphan payload");
    if (item.error) signals.push(`row error ${item.error}`);
    const readFirst = ["Pending manifest"];
    if (item.local_exists === false) readFirst.push("Pending payload path");
    if (missingSidecars > 0) readFirst.push("Sidecar paths");
    if (recommendation === "do_not_drain" || severity === "error" || item.error) readFirst.push("Last Stderr", "Run Logs");
    const crossCheck = ["Completed Manifest correlation", "Durable drain summary"];
    if (item.source_path) crossCheck.push("Queue/source route evidence before rerun");
    if (item.recovery_class) crossCheck.push(`Recovery class ${item.recovery_class}`);
    const lines = [
      "Combined pending-row drain review plan:",
      `Signal count: ${signals.length}`,
      `Signals: ${signals.length ? signals.join("; ") : "none reported by the selected pending row"}`,
      `Read first: ${[...new Set(readFirst)].join(" -> ")}`,
      `Cross-check: ${[...new Set(crossCheck)].join(" -> ")}`,
    ];
    if (recommendation === "do_not_drain" || severity === "error") {
      lines.push("Decision: do not run Publish Parked Outputs for this row until pending artifacts and logs explain the blocker.");
    } else if (signals.length) {
      lines.push("Decision: review the selected artifacts first; backend drain validation remains authoritative.");
    } else if (item.ready_to_drain) {
      lines.push("Decision: row is ready-looking, but only backend-owned Publish Parked Outputs may move files.");
    } else {
      lines.push("Decision: treat this row as review-needed until pending scan and drain decision both report ready.");
    }
    lines.push("Guardrail: this combined plan is read-only and cannot drain, repair, move, delete, rewrite manifests, publish, or touch media files.");
    return lines;
  }

  function pendingRealMediaTraceLines(item) {
    if (!item) return [];
    const proofSummary = Array.isArray(item.proof_summary) ? item.proof_summary.filter(Boolean) : [];
    const evidenceFields = Array.isArray(item.evidence_fields) ? item.evidence_fields.filter(Boolean) : [];
    const sidecars = Array.isArray(item.sidecar_paths) ? item.sidecar_paths.filter(Boolean) : [];
    const lines = [
      "Real-media sample trace: Pending Publish",
      `Trace key: payload=${item.local_file || "not reported"}; destination=${item.server_out || "not reported"}; source=${item.source_path || "not reported"}`,
      `Parking proof: state=${item.state || "unknown"}; manifest=${item.manifest_path || "not reported"}; payload exists=${item.local_exists === false ? "no" : item.local_exists === true ? "yes" : "unknown"}`,
      `Drain proof: recommendation=${item.drain_recommendation || "review"}; diagnostic=${[item.diagnostic_status, item.diagnostic_severity].filter(Boolean).join(" / ") || "unknown"}; ready=${item.ready_to_drain ? "yes" : "no"}`,
      "What this proves: the backend pending-publish scan can see a parked output or parked-output issue and can classify drain safety.",
      "What remains unproven: final publish completion until Publish Parked Outputs succeeds and durable drain summary/recent drain event agrees with Completed output proof.",
    ];
    if (proofSummary.length || evidenceFields.length) {
      lines.push("Pending proof to compare with Completed and logs:");
      proofSummary.slice(0, 5).forEach((line) => lines.push(`  ${line}`));
      if (evidenceFields.length) lines.push(`  evidence fields: ${evidenceFields.join(", ")}`);
    }
    if (sidecars.length) {
      lines.push(`Sidecar payloads: ${sidecars.length}; verify they drain with the media file when subtitle SRT sidecars are expected.`);
    }
    if (item.drain_recommendation === "do_not_drain" || item.ready_to_drain === false || item.local_exists === false) {
      lines.push("Drain boundary: do not drain this row until blockers are explained by pending diagnostics and logs.");
    }
    lines.push("Next evidence stop: run or review backend-owned recovery dry-run, then compare durable drain summary with Completed output proof after Publish Parked Outputs.");
    lines.push("Mutation guardrail: this trace is read-only and cannot drain, repair, delete, rewrite, move, publish, or mutate files.");
    return lines;
  }

  function pendingCompletedCorrelationFirstValue(item, keys) {
    for (const key of keys) {
      const value = item?.[key];
      if (value !== undefined && value !== null && String(value).trim()) return String(value).trim();
    }
    return "";
  }

  function pendingCompletedCorrelationNormalizePath(value) {
    const s = String(value || "").trim().replace(/\//g, "\\");
    const unc = s.startsWith("\\\\") ? "\\\\" : "";
    return (unc + s.slice(unc.length).replace(/\\+/g, "\\")).toLowerCase();
  }

  function pendingCompletedCorrelationLeaf(value) {
    const text = String(value || "").trim();
    if (!text) return "";
    const parts = text.split(/[\\/]/).filter(Boolean);
    return parts.length ? parts[parts.length - 1] : text;
  }

  function pendingCompletedCorrelationPendingDestinationPath(row) {
    return pendingCompletedCorrelationFirstValue(row, ["server_out", "destination_path", "output_path", "target_path", "final_path"]);
  }

  function pendingCompletedCorrelationPendingSourcePath(row) {
    return pendingCompletedCorrelationFirstValue(row, ["source_path", "input_path", "source_file"]);
  }

  function pendingCompletedCorrelationPendingLocalPath(row) {
    return pendingCompletedCorrelationFirstValue(row, ["local_file", "payload_path", "payload_file"]);
  }

  function pendingCompletedCorrelationCompletedOutputPath(row) {
    return pendingCompletedCorrelationFirstValue(row, ["output_path", "server_out", "destination_path", "final_path", "output_file"]);
  }

  function pendingCompletedCorrelationCompletedSourcePath(row) {
    return pendingCompletedCorrelationFirstValue(row, ["source_path", "input_path", "source_file"]);
  }

  function pendingCompletedCorrelationCompletedRowLabel(row) {
    return pendingCompletedCorrelationFirstValue(row, ["lookup_title", "output_file", "title", "route_label"])
      || pendingCompletedCorrelationLeaf(pendingCompletedCorrelationCompletedOutputPath(row))
      || pendingCompletedCorrelationLeaf(pendingCompletedCorrelationCompletedSourcePath(row))
      || "(completed row)";
  }

  function pendingCompletedCorrelationLoadedRows() {
    if (typeof window.getLastCompletedRows === "function") {
      const rows = window.getLastCompletedRows();
      return Array.isArray(rows) ? rows : [];
    }
    return [];
  }

  function pendingSelectedCompletedCorrelationRows(item) {
    const completedRows = pendingCompletedCorrelationLoadedRows();
    const pendingDestination = pendingCompletedCorrelationPendingDestinationPath(item);
    const pendingSource = pendingCompletedCorrelationPendingSourcePath(item);
    const pendingLocal = pendingCompletedCorrelationPendingLocalPath(item);
    const pendingDestinationKey = pendingCompletedCorrelationNormalizePath(pendingDestination);
    const pendingSourceKey = pendingCompletedCorrelationNormalizePath(pendingSource);
    const pendingDestinationLeaf = pendingCompletedCorrelationLeaf(pendingDestination).toLowerCase();
    const pendingLocalLeaf = pendingCompletedCorrelationLeaf(pendingLocal).toLowerCase();
    const exactDestination = [];
    const exactSource = [];
    const sameLeaf = [];
    const addMatch = (collection, completedRow, index, matchType, evidence, outputPath, sourcePath) => {
      collection.push({
        completedRow,
        index,
        matchType,
        evidence,
        outputPath,
        sourcePath,
        label: pendingCompletedCorrelationCompletedRowLabel(completedRow),
        status: completedRow?.operator_trust_state || completedRow?.consistency_status || completedRow?.output_health || completedRow?.status || "unknown",
      });
    };
    completedRows.forEach((completedRow, index) => {
      const outputPath = pendingCompletedCorrelationCompletedOutputPath(completedRow);
      const sourcePath = pendingCompletedCorrelationCompletedSourcePath(completedRow);
      const outputKey = pendingCompletedCorrelationNormalizePath(outputPath);
      const sourceKey = pendingCompletedCorrelationNormalizePath(sourcePath);
      const outputLeaf = pendingCompletedCorrelationLeaf(outputPath).toLowerCase();
      if (pendingDestinationKey && outputKey && pendingDestinationKey === outputKey) {
        addMatch(exactDestination, completedRow, index, "exact-destination", "pending destination equals completed output", outputPath, sourcePath);
      }
      if (pendingSourceKey && sourceKey && pendingSourceKey === sourceKey) {
        addMatch(exactSource, completedRow, index, "exact-source", "pending source equals completed source", outputPath, sourcePath);
      }
      if (
        outputLeaf
        && (outputLeaf === pendingDestinationLeaf || outputLeaf === pendingLocalLeaf)
        && !(pendingDestinationKey && outputKey && pendingDestinationKey === outputKey)
      ) {
        addMatch(sameLeaf, completedRow, index, "same-leaf", "completed output filename matches pending destination or local payload leaf only", outputPath, sourcePath);
      }
    });
    return {
      completedRows,
      pendingDestination,
      pendingSource,
      pendingLocal,
      exactDestination,
      exactSource,
      sameLeaf,
    };
  }

  function pendingCompletedCorrelationMatchLine(match) {
    return `- ${match.label}: ${match.evidence}; status=${match.status}; completed output=${match.outputPath || "unknown"}; completed source=${match.sourcePath || "unknown"}`;
  }

  function pendingSelectedCompletedCorrelationLines(item) {
    if (!item) {
      return [
        "Completed Manifest correlation for selected pending row:",
        "Select a pending row to compare its destination/source against the loaded Completed Manifest rows.",
        "Mutation guardrail: this pending-row correlation is read-only and cannot mark done, drain, rerun, delete, publish, rewrite manifests, or touch media.",
      ];
    }
    const correlation = pendingSelectedCompletedCorrelationRows(item);
    const lines = [
      "Completed Manifest correlation for selected pending row:",
      `Completed rows loaded: ${correlation.completedRows.length}`,
      `Pending destination: ${correlation.pendingDestination || "unknown"}`,
      `Pending source: ${correlation.pendingSource || "unknown"}`,
      `Pending local payload: ${correlation.pendingLocal || "unknown"}`,
      `Exact pending destination -> completed output: ${correlation.exactDestination.length}`,
      `Exact pending source -> completed source: ${correlation.exactSource.length}`,
      `Same-leaf completed output hints: ${correlation.sameLeaf.length}`,
      "Proof order: exact normalized destination/source path matches are stronger than same-leaf filename matches.",
      "Boundary: same-leaf matches are duplicate-title hints only and do not prove publish completion.",
    ];
    if (!correlation.completedRows.length) {
      lines.push("No Completed rows are loaded in this WebView session. Open or refresh Completed before deciding whether this parked output already has completed-history proof.");
    }
    if (correlation.exactDestination.length) {
      lines.push("Exact destination matches:");
      correlation.exactDestination.slice(0, 4).forEach((match) => lines.push(pendingCompletedCorrelationMatchLine(match)));
    }
    if (correlation.exactSource.length) {
      lines.push("Exact source matches:");
      correlation.exactSource.slice(0, 4).forEach((match) => lines.push(pendingCompletedCorrelationMatchLine(match)));
    }
    if (correlation.sameLeaf.length) {
      lines.push("Same-leaf review hints:");
      correlation.sameLeaf.slice(0, 4).forEach((match) => lines.push(pendingCompletedCorrelationMatchLine(match)));
    }
    if (!correlation.exactDestination.length && !correlation.exactSource.length && correlation.completedRows.length) {
      lines.push("No exact Completed proof is loaded for this pending row. Inspect Completed, Pending Publish, Run Logs, Last Stderr, and durable drain summaries before assuming publish success or data loss.");
    }
    lines.push("Mutation guardrail: this pending-row correlation is read-only and cannot mark done, drain, rerun, delete, publish, rewrite manifests, or touch media.");
    return lines;
  }

  function pendingSampleValidationHandoffLines(item) {
    if (!item) return [];
    const recommendation = String(item.drain_recommendation || "review").toLowerCase();
    const state = String(item.state || "").toLowerCase();
    const status = String(item.diagnostic_status || item.state || "").toLowerCase();
    const severity = String(item.diagnostic_severity || "").toLowerCase();
    const blocked = Boolean(
      recommendation === "do_not_drain"
      || item.ready_to_drain === false
      || item.local_exists === false
      || severity === "error"
      || ["invalid_manifest", "unreadable_manifest", "orphan_payload", "missing_payload"].some((token) => status.includes(token) || state.includes(token))
    );
    const suggestedDecision = blocked
      ? "hold_review until pending blockers are explained"
      : "accepted only after Completed output proof and durable drain summary agree";
    const lines = [
      "Sample Validation handoff: Pending Publish",
      "Suggested pilot category: deferred-publish",
      `Suggested evidence decision: ${suggestedDecision}`,
      `Current pending proof: recommendation=${item.drain_recommendation || "review"}; ready=${item.ready_to_drain ? "yes" : "no"}; state=${item.state || "unknown"}; diagnostic=${[item.diagnostic_status, item.diagnostic_severity].filter(Boolean).join(" / ") || "unknown"}`,
      "Record evidence only after comparing Pending Publish row proof, Completed output proof, durable drain summary, Run Logs, and Last Stderr.",
    ];
    if (blocked) {
      lines.push("Do not append accepted sample evidence from this pending row until blockers are resolved or intentionally documented as review evidence.");
    } else {
      lines.push("If this row is part of a real-media pilot, use Home Sample Validation after backend-owned Publish Parked Outputs and post-drain proof are checked.");
    }
    lines.push("Home Sample Validation can write JSONL evidence notes only; it cannot drain, publish, mark complete, accept output, rewrite manifests, or mutate media.");
    return lines;
  }

  function pendingSampleValidationComparisonLines(item) {
    const context = window.mediaPipelineLastCrossPageContext || {};
    const log = context.sampleValidation || {};
    const rows = typeof window.sampleValidationRecordComparisonRowsForPaths === "function"
      ? window.sampleValidationRecordComparisonRowsForPaths(
        log,
        [
          item?.source_path,
          item?.server_out,
          item?.destination_path,
          item?.output_path,
          item?.local_file,
          item?.payload_path,
        ],
        item?.lookup_title || item?.output_file || item?.server_out || item?.local_file || "",
      )
      : [];
    const current = rows.filter((row) => row.current_status === "current").length;
    const stale = rows.filter((row) => row.current_status === "stale").length;
    const review = rows.filter((row) => ["review", "not checked", "unknown"].includes(row.current_status)).length;
    const accepted = rows.filter((row) => row.operator_decision === "accepted").length;
    const lines = [
      "Sample Validation comparison for selected Pending Publish row:",
      `Matching evidence records: ${rows.length}; accepted=${accepted}; current=${current}; stale=${stale}; review/not-checked=${review}.`,
      `Pending source: ${item?.source_path || "unknown"}`,
      `Pending destination: ${item?.server_out || item?.destination_path || item?.output_path || "unknown"}`,
      `Parked payload: ${item?.local_file || item?.payload_path || "unknown"}`,
    ];
    if (!rows.length) {
      lines.push(
        "No matching Sample Validation record is loaded for this pending source/destination/payload.",
        "Next action: keep deferred-publish evidence at hold/review until Completed, Pending Publish, durable drain summary, Diagnostics, playback, and output proof agree."
      );
    } else {
      rows.slice(0, 4).forEach((row) => {
        const gaps = Array.isArray(row.missing_current_evidence) && row.missing_current_evidence.length
          ? ` gaps=${row.missing_current_evidence.join("; ")}`
          : " gaps=none";
        lines.push(`- ${row.created_at || "unknown time"} ${row.operator_decision || "unknown decision"} category=${row.sample_category || "general"} proof=${row.proof_strength || "unknown"} match=${row.match_strength} fields=${(row.match_fields || []).join(",") || "unknown"} current=${row.current_status || "not checked"}${gaps}`);
      });
      lines.push("Next action: if a matching record is not current, preview a fresh deferred-publish evidence note only after post-drain/final-placement proof is coherent.");
    }
    lines.push(
      "Post-run capture: Preview Record includes pending/final-placement proof rows; use category deferred-publish for parked/drained samples.",
      "Mutation guardrail: this comparison is read-only and cannot append Sample Validation records, drain, publish, repair, rewrite manifests/sidecars, move/delete payloads, save settings, rename, or touch media."
    );
    return lines;
  }

  function pendingRowTrustSummaryLines(item) {
    if (!item || typeof diagnosticsBridgeRowTrustLines !== "function") return [];
    const status = String(item.diagnostic_status || "").toLowerCase();
    const severity = String(item.diagnostic_severity || "").toLowerCase();
    const recommendation = String(item.drain_recommendation || "review").toLowerCase();
    const state = String(item.state || "").toLowerCase();
    const missingSidecars = Number(item.missing_sidecar_count || 0);
    const issues = [];
    if (recommendation === "do_not_drain") issues.push("backend marked do_not_drain");
    if (severity === "error") issues.push("diagnostic severity is error");
    if (item.local_exists === false) issues.push("local payload missing");
    if (missingSidecars > 0) issues.push(`${missingSidecars} missing sidecar${missingSidecars === 1 ? "" : "s"}`);
    if (["invalid_manifest", "unreadable_manifest"].includes(state) || ["invalid_manifest", "unreadable_manifest"].includes(status)) issues.push("manifest unreadable or invalid");
    if (state === "orphan_payload" || status === "orphan_payload") issues.push("orphan payload");
    if (item.error) issues.push(`row error: ${item.error}`);
    const backendTrustState = String(item.operator_trust_state || "").trim();
    const trustState = backendTrustState || (recommendation === "do_not_drain" || severity === "error"
      ? "do-not-drain"
      : issues.length
        ? "review-before-drain"
        : item.ready_to_drain
          ? "ready-looking"
          : "review");
    const proofSummary = Array.isArray(item.proof_summary) ? item.proof_summary.filter(Boolean) : [];
    return diagnosticsBridgeRowTrustLines("Pending Publish selected row", pendingDiagnosticsActionsForRow(item), {
      trustState,
      primaryConcern: item.primary_concern || (issues.length ? issues.join("; ") : item.ready_to_drain ? "row has no blocker in the loaded pending scan" : "backend still marks this row for review"),
      evidence: proofSummary.length ? proofSummary : [
        item.diagnostic_status || item.diagnostic_severity ? `diagnostic=${[item.diagnostic_status, item.diagnostic_severity].filter(Boolean).join(" / ")}` : "",
        item.drain_recommendation ? `drain=${item.drain_recommendation}` : "",
        item.recovery_class || item.recovery_action ? `recovery=${[item.recovery_class, item.recovery_action].filter(Boolean).join(" - ")}` : "",
        item.local_file ? `payload=${item.local_file}` : "",
        item.manifest_path ? `manifest=${item.manifest_path}` : "",
        item.server_out ? `destination=${item.server_out}` : "",
      ],
      safeAction: item.safe_next_action || (trustState === "ready-looking" ? "use only backend-owned Publish Parked Outputs after page-level validation agrees." : "inspect pending manifest/payload/sidecar evidence, Last Stderr, and Run Logs before drain."),
      unsafeAction: item.unsafe_if_ignored || "move, delete, drain, repair, or rewrite pending payloads/manifests from this page.",
      owningPages: "Pending Publish owns parked output safety; Completed owns output proof; Queue owns rerun risk; Diagnostics owns artifact/log evidence.",
    });
  }

  function renderPendingDetail(item) {
    renderPendingSelectedAtAGlance(item || null);
    if (!item) {
      setText("pending-detail", pendingRowReviewChecklistLines(null).join("\n"));
      renderPendingDiagnosticsLinks(null);
      return;
    }
    const sidecars = Array.isArray(item.sidecar_paths) ? item.sidecar_paths.join("\n  ") : "";
    const proofSummary = Array.isArray(item.proof_summary) ? item.proof_summary : [];
    const diagnosticTargets = Array.isArray(item.recommended_diagnostics_targets) ? item.recommended_diagnostics_targets.join(", ") : "";
    const handoffLines = typeof diagnosticsBridgeHandoffLines === "function"
      ? diagnosticsBridgeHandoffLines("Pending Publish selected row", pendingDiagnosticsActionsForRow(item), {
        evidence: [
          item.diagnostic_status || item.diagnostic_severity ? `diagnostic=${[item.diagnostic_status, item.diagnostic_severity].filter(Boolean).join(" / ")}` : "",
          item.drain_recommendation ? `drain=${item.drain_recommendation}` : "",
          item.recovery_class || item.recovery_action ? `recovery=${[item.recovery_class, item.recovery_action].filter(Boolean).join(" - ")}` : "",
          item.manifest_path || item.local_file ? `payload=${item.local_file || item.manifest_path}` : "",
        ],
        safeAction: "compare Pending Publish, manifest/payload/sidecar evidence, Last Stderr, and Run Logs before using Publish Parked Outputs.",
      })
      : [];
    const detail = [
      ...pendingSelectedQuickSignalLines(item),
      "",
      ...pendingRowReviewChecklistLines(item),
      "",
      ...pendingRowIssueDigestLines(item),
      "",
      ...pendingRowCombinedReviewPlanLines(item),
      "",
      ...pendingInvestigationSignalLines(item),
      "",
      ...pendingRealMediaTraceLines(item),
      "",
      ...pendingSelectedCompletedCorrelationLines(item),
      "",
      ...pendingSampleValidationHandoffLines(item),
      "",
      ...pendingSampleValidationComparisonLines(item),
      "",
      ...pendingRowTrustSummaryLines(item),
      "",
      ...handoffLines,
      "",
      ...pendingSelectedOpenTargetLines(item),
      "",
      `State: ${item.state || ""}`,
      item.operator_trust_state ? `Backend trust state: ${item.operator_trust_state}` : "",
      item.primary_concern ? `Primary concern: ${item.primary_concern}` : "",
      item.safe_next_action ? `Safe next action: ${item.safe_next_action}` : "",
      item.unsafe_if_ignored ? `Unsafe if ignored: ${item.unsafe_if_ignored}` : "",
      proofSummary.length ? "Backend proof summary:" : "",
      ...proofSummary.map((line) => `  ${line}`),
      diagnosticTargets ? `Recommended diagnostics targets: ${diagnosticTargets}` : "",
      `Row key: ${item.row_key || pendingRowKey(item) || ""}`,
      `Route: ${item.route || ""}`,
      `Publish mode: ${item.publish_mode || ""}`,
      `Diagnostic status: ${item.diagnostic_status || "unknown"}`,
      `Diagnostic severity: ${item.diagnostic_severity || "unknown"}`,
      `Drain recommendation: ${item.drain_recommendation || "review"}`,
      `Operator guidance: ${item.operator_guidance || "Review this pending row before drain."}`,
      `Recovery class: ${item.recovery_class || "manual_review"}`,
      `Recovery action: ${item.recovery_action || "Review this row with Pending Publish diagnostics before drain."}`,
      `Evidence fields: ${pendingListText(item.evidence_fields)}`,
      `Recommended open targets: ${pendingListText(item.recommended_open_targets)}`,
      `Available open targets: ${pendingListText(item.available_open_targets)}`,
      `Size: ${item.size_text || ""} (${item.output_size || 0} bytes)`,
      `Parked: ${item.parked_at || item.parked_at_display || ""}`,
      `Age: ${item.age_text || ""}`,
      `Local payload: ${item.local_file || ""}`,
      `Local exists: ${item.local_exists === false ? "no" : item.local_exists === true ? "yes" : ""}`,
      `Destination: ${item.server_out || ""}`,
      `Source: ${item.source_path || ""}`,
      `Manifest: ${item.manifest_path || ""}`,
      `Schema: ${item.schema_version || ""}`,
      `Sidecars: ${item.sidecar_count || 0}`,
      `Missing sidecars: ${item.missing_sidecar_count || 0}`,
      `Ready to drain: ${item.ready_to_drain ? "yes" : "no"}`,
      item.issue_summary ? `Issue summary: ${item.issue_summary}` : "",
      sidecars ? `Sidecar paths:\n  ${sidecars}` : "",
      item.error ? `Issue: ${item.error}` : "",
    ].filter(Boolean);
    setText("pending-detail", detail.join("\n"));
    renderPendingDiagnosticsLinks(item);
  }

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
