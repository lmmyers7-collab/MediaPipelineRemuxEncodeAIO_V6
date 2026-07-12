(function () {
  function createHomeDailyDriverModule(deps = {}) {
    const {
      appendCells, byId, clearRows, commandHistoryView, externalDependencyOverallStatus,
      externalDependencyEvidenceText, getCommandHistory = () => [],
      getLastRefreshCompletedAt = () => null, getLastRefreshDurationMs = () => null,
      refreshTimeLabel = () => "not completed", setHomePanelStatus, setText, settingsOperatorTrustStatus,
    } = deps;
  function dailyDriverCount(value) {
    const number = Number(value || 0);
    return Number.isFinite(number) ? Math.max(0, Math.round(number)) : 0;
  }

  function dailyDriverRow(area, status, evidence, nextStep) {
    return { area, status, evidence, nextStep };
  }

  function dailyDriverStatusRank(status) {
    const normalized = String(status || "").toLowerCase();
    if (normalized === "blocked") return 0;
    if (normalized === "review" || normalized === "unknown") return 1;
    if (normalized === "ready") return 2;
    return 3;
  }

  function dailyDriverOverallStatus(rows) {
    if (!rows.length) return "Not evaluated";
    if (rows.some((row) => row.status === "blocked")) return "Blocked review";
    if (rows.some((row) => row.status === "review" || row.status === "unknown")) return "Review";
    return "Ready";
  }

  function dailyDriverStatusClass(status) {
    const normalized = String(status || "").toLowerCase();
    if (normalized === "blocked") return "blocked";
    if (normalized === "review" || normalized === "unknown") return "warning";
    return "match";
  }

  function dailyDriverSettingsStatus(settings) {
    if (!settings || typeof settings !== "object" || !settings.schema_version) return "unknown";
    let trustStatus = "";
    try {
      trustStatus = typeof settingsOperatorTrustStatus === "function" ? settingsOperatorTrustStatus(settings) : "";
    } catch {
      trustStatus = "";
    }
    const errors = Array.isArray(settings.errors) ? settings.errors : [];
    const highest = String(settings.risk_summary?.highest_severity || "").toLowerCase();
    const normalized = String(trustStatus || "").toLowerCase();
    if (errors.length || highest === "critical" || normalized.includes("critical") || normalized.includes("invalid")) return "blocked";
    if (highest === "high" || dailyDriverCount(settings.risk_summary?.total_count) || (settings.warnings || []).length || normalized.includes("review") || normalized.includes("high")) return "review";
    return "ready";
  }

  function dependencyStatusRank(status) {
    const normalized = String(status || "").toLowerCase();
    if (normalized.includes("block") || normalized.includes("missing") || normalized.includes("error")) return 0;
    if (normalized.includes("review") || normalized.includes("warning") || normalized.includes("unknown") || normalized.includes("not loaded")) return 1;
    if (normalized.includes("ready") || normalized.includes("ok")) return 2;
    return 1;
  }

  function dependencyStatusLabel(status) {
    const rank = dependencyStatusRank(status);
    if (rank === 0) return "blocked";
    if (rank === 1) return "review";
    return "ready";
  }

  function dailyDriverDiagnosticsCounts(diagnostics) {
    const view = window.mediaPipelineCrossPageContextView || {};
    if (typeof view.crossPageDiagnosticsCounts === "function") return view.crossPageDiagnosticsCounts(diagnostics || {});
    return {};
  }

  function dailyDriverCommandIssues() {
    const history = getCommandHistory();
    if (!Array.isArray(history)) return [];
    return history.filter((entry) => {
      const level = typeof commandHistoryView.commandHistoryIssueLevel === "function" ? commandHistoryView.commandHistoryIssueLevel(entry) : (entry?.ok ? "ok" : (entry?.severity || "error"));
      return !["ok", "info", "none"].includes(String(level || "").toLowerCase());
    });
  }

  function dailyDriverRealMediaProofRow({ queue = {}, completed = {}, pending = {}, diagnosticCounts = {} } = {}) {
    const queueRows = Array.isArray(queue.rows) ? queue.rows.length : 0;
    const completedList = Array.isArray(completed.rows) ? completed.rows : [];
    const completedRows = completedList.length;
    const pendingRows = Array.isArray(pending.rows) ? pending.rows.length : 0;
    const missingOutputs = dailyDriverCount(completed.missing_output_count);
    const sizePolicyExceededRows = dailyDriverCount(completed.size_policy_exceeded_count);
    const legacySizeGrowthRows = completedList.filter((row) => row?.size_growth_over_5 && !row?.size_policy_available).length;
    const pendingIssues = dailyDriverCount(pending.issue_count) + dailyDriverCount(pending.health_count);
    const diagnosticsErrors = dailyDriverCount(diagnosticCounts.error);
    const diagnosticsWarnings = dailyDriverCount(diagnosticCounts.warning);
    const blocked = missingOutputs > 0 || pendingIssues > 0 || diagnosticsErrors > 0;
    const sizeNeedsReview = sizePolicyExceededRows > 0 || legacySizeGrowthRows > 0;
    const hasProofSources = completedRows > 0;
    const status = blocked || sizeNeedsReview ? "review" : hasProofSources ? "ready" : "review";
    const evidence = `queue rows=${queueRows}; completed rows=${completedRows}; pending rows=${pendingRows}; missing outputs=${missingOutputs}; size policy exceeded=${sizePolicyExceededRows}; legacy growth >5% without policy=${legacySizeGrowthRows}; pending issues=${pendingIssues}; diagnostics errors=${diagnosticsErrors}; diagnostics warnings=${diagnosticsWarnings}`;
    const nextStep = completedRows <= 0
      ? "Before treating WebView as daily-driver ready, process a small known batch and compare Queue route, subtitle/audio evidence, Completed output proof, Diagnostics logs, and Pending Publish drain state."
      : blocked
        ? "Use the real-media validation playbook before rerun, cleanup, drain, or acceptance; visible output/publish/diagnostics issues still need review."
        : "Loaded proof sources exist; inspect a known completed sample row and verify route, subtitle/audio, sidecar, size-growth, and publish evidence agree.";
    return dailyDriverRow("Real-media sample proof", status, evidence, nextStep);
  }

  function homeNetworkDriftPayload(networkWorkers = {}) {
    const drift = networkWorkers?.running_vs_saved;
    return drift && typeof drift === "object" ? drift : {};
  }

  function homeNetworkDriftFieldsText(drift = {}) {
    const labels = Array.isArray(drift.drift_field_labels) ? drift.drift_field_labels : [];
    const fields = Array.isArray(drift.drift_fields) ? drift.drift_fields : [];
    const values = (labels.length ? labels : fields)
      .map((item) => String(item || "").trim())
      .filter(Boolean);
    return values.length ? values.join(", ") : "none";
  }

  function homeNetworkPolicyDivergencePayload(drift = {}) {
    const payload = drift?.policy_divergence;
    return payload && typeof payload === "object" ? payload : {};
  }

  function homeNetworkPolicyDivergenceFieldsText(drift = {}) {
    const payload = homeNetworkPolicyDivergencePayload(drift);
    const labels = Array.isArray(payload.field_labels) ? payload.field_labels : [];
    const fields = Array.isArray(payload.fields) ? payload.fields : [];
    const values = (labels.length ? labels : fields)
      .map((item) => String(item || "").trim())
      .filter(Boolean);
    return values.length ? values.join(", ") : "none";
  }

  function homeNetworkPolicyDivergenceStatusText(drift = {}) {
    const payload = homeNetworkPolicyDivergencePayload(drift);
    const status = String(payload.status || "not_loaded").trim().toLowerCase();
    if (status === "review") return `review (${homeNetworkPolicyDivergenceFieldsText(drift)})`;
    if (status === "ready") return "ready";
    return status || "not loaded";
  }

  function homeNetworkPolicyDivergenceActive(drift = {}) {
    return String(homeNetworkPolicyDivergencePayload(drift).status || "").trim().toLowerCase() === "review";
  }

  function dailyDriverRows(context = {}) {
    const failures = Array.isArray(context.failures) ? context.failures : [];
    const requiredFailures = failures.filter((item) => item.required);
    const optionalFailures = failures.filter((item) => !item.required);
    const snapshot = context.snapshot || null;
    const closeReadiness = context.closeReadiness || null;
    const settings = context.settings || {};
    const queue = context.queue || {};
    const completed = context.completed || {};
    const pending = context.pending || {};
    const diagnostics = context.diagnostics || {};
    const dependencyStatus = externalDependencyOverallStatus(context);
    const schedule = context.schedule || {};
    const networkWorkers = context.networkWorkers || {};
    const commandIssues = dailyDriverCommandIssues();
    const diagnosticCounts = dailyDriverDiagnosticsCounts(diagnostics);
    const rows = [];

    rows.push(dailyDriverRow(
      "Refresh payloads",
      requiredFailures.length ? "blocked" : optionalFailures.length ? "review" : "ready",
      `required failures=${requiredFailures.length}; supporting failures=${optionalFailures.length}; completed=${refreshTimeLabel(getLastRefreshCompletedAt())}${Number.isFinite(getLastRefreshDurationMs()) ? `; duration=${getLastRefreshDurationMs()}ms` : ""}`,
      requiredFailures.length
        ? "Open Diagnostics and resolve required backend reads before trusting the WebView."
        : optionalFailures.length
          ? "Use Diagnostics for supporting read issues; avoid unattended runs until important panels refresh cleanly."
          : "Core payload refresh is clean.",
    ));

    rows.push(dailyDriverRow(
      "Close / active work",
      !snapshot || !closeReadiness ? "unknown" : closeReadiness.safe_to_close === false || closeReadiness.active_work ? "review" : "ready",
      `snapshot=${snapshot ? "loaded" : "missing"}; close=${closeReadiness ? (closeReadiness.safe_to_close ? "safe" : "active") : "unknown"}; state=${snapshot?.pipeline_state || closeReadiness?.state || "unknown"}`,
      closeReadiness?.safe_to_close === false || closeReadiness?.active_work
        ? "Monitor progress, ActiveJobs, and logs before closing or starting more work."
        : "No active-work block is currently reported.",
    ));

    const settingsStatus = dailyDriverSettingsStatus(settings);
    rows.push(dailyDriverRow(
      "Saved settings",
      settingsStatus,
      settings?.schema_version
        ? `risk=${settings.risk_summary?.highest_severity || "none"}; warnings=${(settings.warnings || []).length}; errors=${(settings.errors || []).length}`
        : "settings workspace not loaded",
      settingsStatus === "blocked"
        ? "Use Settings > Validate / Reload and resolve critical settings before launch."
        : settingsStatus === "review"
          ? "Review Settings trust and staged patch handoff before unattended work."
          : "Saved settings posture is clean in the loaded workspace.",
    ));

    rows.push(dailyDriverRow(
      "External dependencies",
      dependencyStatus === "blocked" ? "blocked" : dependencyStatus === "review" || dependencyStatus === "unknown" ? "review" : "ready",
      externalDependencyEvidenceText(context),
      dependencyStatus === "blocked"
        ? "Resolve blocked Settings OCR or Maintenance toolchain evidence before launch/rerun decisions."
        : dependencyStatus === "review" || dependencyStatus === "unknown"
          ? "Review Settings OCR and Maintenance toolchain evidence before long unattended processing."
          : "No external dependency blocker is visible in loaded Settings/Diagnostics/Maintenance evidence.",
    ));

    rows.push(dailyDriverRow(
      "Queue",
      queue.error ? "review" : String(queue.snapshot_file_freshness_status || "").toLowerCase() === "stale" || dailyDriverCount(queue.invalid_row_count) || dailyDriverCount(queue.blocked_row_count) ? "review" : "ready",
      `rows=${Array.isArray(queue.rows) ? queue.rows.length : 0}; runnable=${dailyDriverCount(Object.prototype.hasOwnProperty.call(queue, "runnable_count") ? queue.runnable_count : (Array.isArray(queue.rows) ? queue.rows.length : 0))}; stale=${queue.snapshot_file_freshness_status || "unknown"}; blocked=${dailyDriverCount(queue.blocked_row_count)}; invalid=${dailyDriverCount(queue.invalid_row_count)}`,
      queue.error
        ? "Open Queue and Diagnostics; queue payload reported an error."
        : String(queue.snapshot_file_freshness_status || "").toLowerCase() === "stale"
          ? "Refresh Queue before Launch because stale snapshots can disagree with current state."
          : "Use Launch only after Queue row guidance and schedule/settings preflight look correct.",
    ));

    rows.push(dailyDriverRow(
      "Completed proof",
      completed.error || dailyDriverCount(completed.missing_output_count) ? "review" : dailyDriverCount(completed.size_policy_exceeded_count) ? "review" : "ready",
      `rows=${Array.isArray(completed.rows) ? completed.rows.length : 0}; missing outputs=${dailyDriverCount(completed.missing_output_count)}; size policy exceeded=${dailyDriverCount(completed.size_policy_exceeded_count)}; within policy=${dailyDriverCount(completed.size_policy_within_limit_count)}`,
      dailyDriverCount(completed.missing_output_count)
        ? "Review Completed Output Proof, Pending Publish, Run Logs, and Last Stderr before rerun or cleanup."
        : dailyDriverCount(completed.size_policy_exceeded_count)
          ? "Review rows that exceeded recorded backend size_policy before treating recent encodes as intentional."
          : "Completed proof has no loaded blocker.",
    ));

    rows.push(dailyDriverRow(
      "Pending Publish",
      pending.error || dailyDriverCount(pending.issue_count) || dailyDriverCount(pending.health_count) ? "review" : "ready",
      `rows=${Array.isArray(pending.rows) ? pending.rows.length : 0}; issues=${dailyDriverCount(pending.issue_count)}; health=${dailyDriverCount(pending.health_count)}; ready=${dailyDriverCount(pending.ready_count)}`,
      dailyDriverCount(pending.issue_count) || dailyDriverCount(pending.health_count)
        ? "Review Pending Publish diagnostics/recovery before draining, rerunning, or cleaning outputs."
        : "Pending Publish has no loaded drain blocker.",
    ));

    rows.push(dailyDriverRealMediaProofRow({ queue, completed, pending, diagnosticCounts }));

    rows.push(dailyDriverRow(
      "Diagnostics",
      dailyDriverCount(diagnosticCounts.error) ? "review" : dailyDriverCount(diagnosticCounts.warning) ? "review" : "ready",
      `errors=${dailyDriverCount(diagnosticCounts.error)}; warnings=${dailyDriverCount(diagnosticCounts.warning)}; info=${dailyDriverCount(diagnosticCounts.info)}`,
      dailyDriverCount(diagnosticCounts.error) || dailyDriverCount(diagnosticCounts.warning)
        ? "Open Diagnostics Investigation Trail and inspect read-first evidence before unattended operation."
        : "No warning/error diagnostics are visible in the loaded payload.",
    ));

    rows.push(dailyDriverRow(
      "Recent commands",
      commandIssues.length ? "review" : "ready",
      `recent command issues=${commandIssues.length}`,
      commandIssues.length
        ? "Inspect Command Results or Diagnostics Command Result Drilldown before repeating actions."
        : "Recent command history has no visible warning/error result.",
    ));

    const scheduleEnabled = Boolean(schedule.enabled);
    const allowedNow = schedule.evaluation?.allowed_now !== false;
    rows.push(dailyDriverRow(
      "Schedule / launch",
      scheduleEnabled && !allowedNow ? "review" : "ready",
      `schedule=${scheduleEnabled ? "enabled" : "off"}; allowed now=${allowedNow ? "yes" : "no"}`,
      scheduleEnabled && !allowedNow
        ? "Use Launch timing trust before outside-window testing; schedule bypass must be deliberate."
        : "Launch timing does not show a schedule-window block in the loaded payload.",
    ));

    const role = String(settings?.config?.NetworkRole || "").trim().toLowerCase() || "standalone";
    const workerRows = Array.isArray(networkWorkers?.rows) ? networkWorkers.rows.length : 0;
    const workerDrift = homeNetworkDriftPayload(networkWorkers);
    const workerDriftStatus = String(workerDrift.status || "not_loaded").toLowerCase();
    const workerDriftActive = workerDriftStatus === "drift";
    const workerDriftFields = homeNetworkDriftFieldsText(workerDrift);
    const workerPolicyReviewActive = homeNetworkPolicyDivergenceActive(workerDrift);
    const workerPolicyStatus = homeNetworkPolicyDivergenceStatusText(workerDrift);
    const workerPolicyFields = homeNetworkPolicyDivergenceFieldsText(workerDrift);
    rows.push(dailyDriverRow(
      "Network visibility",
      workerDriftActive || workerPolicyReviewActive || (role && role !== "standalone") ? "review" : "ready",
      `role=${role}; persisted worker rows=${workerRows}; running_vs_saved=${workerDriftStatus}; drift_fields=${workerDriftFields}; policy_authority=${workerPolicyStatus}`,
      workerDriftActive
        ? `Open Network Workers and restart worker polling so the live dispatcher uses saved settings (${workerDriftFields}).`
        : workerPolicyReviewActive
        ? `Open Network Workers and decide WorkerHonorCoordinatorPolicy plus WorkerEncoderMap before policy-authoritative network claims (${workerPolicyFields}).`
        : role && role !== "standalone"
        ? "Network mode remains read-only in WebView; use backend-owned coordinator/worker lifecycle controls."
        : "Standalone mode is visible; Network page remains read-only.",
    ));

    return rows.sort((left, right) => dailyDriverStatusRank(left.status) - dailyDriverStatusRank(right.status));
  }

  function dailyDriverSummaryLines(rows) {
    const counts = rows.reduce((acc, row) => {
      const key = row.status || "unknown";
      acc[key] = (acc[key] || 0) + 1;
      return acc;
    }, {});
    const firstAction = rows.find((row) => row.status === "blocked" || row.status === "review" || row.status === "unknown");
    const lines = [
      "Daily-driver readiness checklist:",
      `Status: ${dailyDriverOverallStatus(rows)}`,
      `Rows: ${rows.length}; blocked=${counts.blocked || 0}; review=${counts.review || 0}; unknown=${counts.unknown || 0}; ready=${counts.ready || 0}.`,
      `Refresh evidence: completed ${refreshTimeLabel(getLastRefreshCompletedAt())}${Number.isFinite(getLastRefreshDurationMs()) ? ` in ${getLastRefreshDurationMs()} ms` : ""}.`,
      "Real-media boundary: WebView readiness is not proof by itself. Daily-driver confidence still requires a known sample run whose Queue, Completed, Diagnostics, and Pending Publish evidence agree.",
    ];
    lines.push("", `Next operator action: ${firstAction ? `${firstAction.area}: ${firstAction.nextStep}` : "No checklist blocker is visible; refresh once before long unattended operation."}`);
    lines.push("Mutation guardrail: this checklist is read-only and does not launch, repair, drain, save, rename, delete, publish, or touch media files.");
    return lines;
  }

    return {
      dailyDriverCount, dailyDriverRow, dailyDriverStatusRank, dailyDriverOverallStatus,
      dailyDriverStatusClass, dailyDriverSettingsStatus, dependencyStatusRank, dependencyStatusLabel,
      dailyDriverDiagnosticsCounts, dailyDriverCommandIssues, dailyDriverRealMediaProofRow,
      homeNetworkDriftPayload, homeNetworkDriftFieldsText, homeNetworkPolicyDivergencePayload,
      homeNetworkPolicyDivergenceFieldsText, homeNetworkPolicyDivergenceStatusText,
      homeNetworkPolicyDivergenceActive, dailyDriverRows, dailyDriverSummaryLines,    };
  }
  window.__homeDailyDriverModule = { createHomeDailyDriverModule };
})();
