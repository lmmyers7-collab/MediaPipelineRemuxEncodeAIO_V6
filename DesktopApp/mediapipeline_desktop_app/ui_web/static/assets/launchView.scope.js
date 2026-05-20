(function () {
  function createLaunchScopeModule(deps = {}) {
    const {
      appendCells = function () {},
      byId = function () { return null; },
      clearRows = function () {},
      collectPipelineStartRequest = function () { return {}; },
      commandHistoryIssueLevel = null,
      getCommandHistory = function () { return []; },
      getLastLaunchBackendPreflightPayloads = function () { return []; },
      getLastLaunchBackendPreflightRefreshInfo = function () { return {}; },
      getLastQueuePayload = function () { return null; },
      getLastQueueRows = function () { return []; },
      getLaunchRealMediaContext = function () { return {}; },
      isLaunchCommand = function () { return false; },
      launchBackendPreflightOverallStatus = function () { return "Unknown"; },
      launchBackendPreflightPayloadForTarget = function () { return null; },
      launchBackendPreflightRows = function () { return []; },
      launchBackendPreflightStatusState = function (status) { return status; },
      launchBackendPreflightSummaryLines = function () { return []; },
      launchCommandReviewRows = null,
      launchCommandReviewStatus = null,
      launchCommandReviewSummaryLines = null,
      launchPolicyBoundaryRows = function () { return []; },
      launchPolicyBoundaryStatus = function () { return "Unknown"; },
      launchPolicyBoundarySummaryLines = function () { return []; },
      launchReadinessLines = null,
      launchReadinessStatus = null,
      launchRealMediaProofRows = function () { return []; },
      launchRealMediaProofStatus = function () { return "Unknown"; },
      launchRealMediaProofSummaryLines = function () { return []; },
      launchRealMediaSample = function () { return null; },
      launchSampleExecutionRows = function () { return []; },
      launchSampleExecutionStatus = function () { return "Unknown"; },
      launchSampleExecutionSummaryLines = function () { return []; },
      launchSampleSetCoverageEvidence = function () { return {}; },
      launchSettingsIntentCommandLine = function () { return ""; },
      launchSettingsIntentLatestCommand = function () { return null; },
      launchSettingsIntentPayload = function (payload) { return payload && typeof payload === "object" ? payload : {}; },
      launchSettingsIntentRows = function () { return []; },
      launchSettingsIntentStatus = function () { return "Unknown"; },
      launchSettingsIntentSummaryLines = function () { return []; },
      launchSettingsWorkspace = function () { return {}; },
      launchTimingStatus = null,
      launchTimingTrustLines = null,
      makeRowSelectable = null,
      pipelineModeLabel = function (mode) { return mode || "Pipeline"; },
      queueCurrentFilterScope = null,
      queueFilterScopeDetailLines = null,
      queueLaunchDecisionPostureStatus = null,
      queueLaunchDecisionRows = null,
      queueLaunchDecisionStatus = null,
      queueLaunchDecisionSummaryLines = null,
      scheduleDisplayValue = null,
      scheduleWatcherSummary = null,
      setText = function () {},
      state = {},
      updateTableStatusLegend = function () {},
    } = deps;

  function launchScopeStatusValue(posture) {
    const normalized = String(posture || "").toLowerCase();
    if (normalized === "blocked") return "blocked";
    if (normalized === "high review" || normalized === "review") return "warning";
    if (normalized === "read-first") return "changed";
    if (normalized === "unknown") return "unknown";
    return "match";
  }

  function launchScopeRank(posture) {
    const normalized = String(posture || "").toLowerCase();
    if (normalized === "blocked") return 0;
    if (normalized === "high review") return 1;
    if (normalized === "review") return 2;
    if (normalized === "read-first") return 3;
    if (normalized === "unknown") return 4;
    return 5;
  }

  function launchScopeLatestLaunchCommand() {
    return launchSettingsIntentLatestCommand(isLaunchCommand);
  }

  function launchScopeCommandPosture(entry) {
    if (!entry) return "unknown";
    if (typeof commandHistoryIssueLevel === "function") {
      const level = commandHistoryIssueLevel(entry);
      if (["error", "blocked"].includes(level)) return "review";
      if (level === "warning") return "review";
      if (level === "info") return "read-first";
      return "ready";
    }
    if (entry.ok === false) return "review";
    if (String(entry.severity || "").toLowerCase() === "warning") return "review";
    return "ready";
  }

  function launchScopeBackendPreflightPosture(payload) {
    if (!payload) return "unknown";
    const status = String(payload.status || "unknown").toLowerCase();
    if (status === "blocked") return "blocked";
    if (status === "high review") return "high review";
    if (status === "review") return "review";
    if (status === "unknown") return "unknown";
    return "ready";
  }

  function launchScopeQueuePosture(rows) {
    const queueRows = Array.isArray(rows) ? rows : [];
    if (!queueRows.length) return "unknown";
    const blocked = queueRows.filter((row) => String(row?.operator_status || row?.status || "").toLowerCase().includes("blocked") || row?.blocked_reason || row?.blocked_reason_code);
    if (blocked.length) return "blocked";
    const review = queueRows.filter((row) => String(row?.operator_trust_state || row?.operator_status || row?.status || "").toLowerCase().includes("review") || String(row?.operator_trust_state || "").toLowerCase().includes("warning"));
    return review.length ? "review" : "ready";
  }

  function launchScopeReconciliationRows(request = collectPipelineStartRequest(), payload = launchSettingsIntentPayload()) {
    const context = launchSettingsIntentPayload(payload);
    const schedule = context.schedule || {};
    const closeReadiness = context.closeReadiness || null;
    const snapshot = context.snapshot || null;
    const queueRows = typeof getLastQueueRows === "function" ? getLastQueueRows() : [];
    const queuePayload = typeof getLastQueuePayload === "function" ? getLastQueuePayload() : null;
    const queueScope = typeof queueCurrentFilterScope === "function" ? queueCurrentFilterScope(queueRows) : null;
    const queueDecisionRows = typeof queueLaunchDecisionRows === "function" ? queueLaunchDecisionRows(queuePayload, queueRows, typeof getCommandHistory === "function" ? getCommandHistory() : []) : [];
    const queueDecisionNonReady = queueDecisionRows.filter((row) => {
      const status = typeof queueLaunchDecisionPostureStatus === "function"
        ? queueLaunchDecisionPostureStatus(row.posture)
        : String(row.posture || "").toLowerCase();
      return !["ready", "normal", "match"].includes(status);
    });
    const backendPreflight = launchBackendPreflightPayloadForTarget("pipeline");
    const backendRows = backendPreflight ? launchBackendPreflightRows([backendPreflight]) : [];
    const backendNonReady = backendRows.filter((row) => String(row.posture || "").toLowerCase() !== "ready");
    const latestLaunch = launchScopeLatestLaunchCommand();
    const mode = String(request?.mode || "validate");
    const override = String(request?.schedule_override || "");
    const evaluation = schedule.evaluation || {};
    const watchedMode = mode === "once" || mode === "continuous";
    const outsideWindow = Boolean(schedule.enabled && evaluation.allowed_now === false && watchedMode && !override);
    const rows = [];
    const add = (key, signal, posture, evidence, action, detail = []) => rows.push({
      key,
      signal,
      posture,
      evidence,
      action,
      detail: Array.isArray(detail) ? detail.filter(Boolean) : [],
    });

    add(
      "backend-authority",
      "Backend authority",
      "ready",
      "Launch, audit, CSV rerun, pipeline control, and pending-drain commands remain backend-owned.",
      "Use this table as reconciliation only; submit starts only through backend-owned Launch buttons.",
      [
        "This panel never changes queue scope, filters, saved settings, schedule state, command history, or media files.",
        "Backend start routes still re-check locks, active work, schedule gates, and service availability.",
      ],
    );

    add(
      "selected-intent",
      "Selected Launch intent",
      mode === "continuous" && override === "ignore" ? "high review" : mode === "continuous" ? "review" : "ready",
      `mode=${pipelineModeLabel(mode)}; schedule override=${override || "none"}; sleep=${request?.sleep_seconds || 30}s.`,
      mode === "continuous"
        ? "Continuous is unattended-sensitive; confirm schedule stop behavior, close-readiness, and backend preflight first."
        : "Confirm the selected mode matches the current operator intent.",
      [
        `Show config: ${request?.show_config ? "yes" : "no"}`,
        `Show console: ${request?.show_console ? "yes" : "no"}`,
        `Single file: ${request?.single_file ? "operator-provided backend request" : "not requested"}`,
        override === "ignore" ? "Ignore Schedule bypasses schedule-window protection for this launch request." : "No full schedule bypass is selected.",
      ],
    );

    add(
      "queue-payload",
      "Queue payload",
      launchScopeQueuePosture(queueRows),
      queueRows.length
        ? `loaded rows=${queueRows.length}; queue status=${queuePayload?.status || queuePayload?.operator_status || "loaded"}.`
        : "No queue rows are loaded in the current WebView session.",
      queueRows.length
        ? "Compare queue rows, route reasons, and blocked/review evidence before launching."
        : "Refresh Queue or inspect Diagnostics > Queue Snapshot before starting queued work.",
      queueRows.slice(0, 5).map((row) => `${row.display_name || row.source_path || "row"}: ${row.operator_status || row.status || row.route_name || "unknown"}`),
    );

    add(
      "queue-display-scope",
      "Queue display filter scope",
      queueScope ? (queueScope.active ? "review" : "ready") : "unknown",
      queueScope
        ? `filters=${queueScope.active ? "active" : "inactive"}; visible=${queueScope.visibleRows}/${queueScope.totalRows}; hidden blocked=${queueScope.hiddenBlocked}; hidden review=${queueScope.hiddenReview}.`
        : "Queue display filter scope is unavailable.",
      queueScope?.active
        ? "Do not treat the visible Queue subset as launch scope; clear filters or inspect hidden rows before starting."
        : "No visible Queue filter is narrowing the table; backend Launch still owns actual processing scope.",
      queueScope && typeof queueFilterScopeDetailLines === "function"
        ? queueFilterScopeDetailLines(queueScope)
        : [
          "Launch requests do not include Queue text filters, status filters, investigation filters, selected rows, or visible-row subsets.",
          "Backend Launch uses its own saved config, queue state, schedule gates, and process locks.",
        ],
    );

    add(
      "queue-launch-decision",
      "Queue Launch Decision",
      queueDecisionNonReady.some((row) => launchScopeStatusValue(row.posture) === "blocked") ? "blocked" : queueDecisionNonReady.length ? "review" : queueDecisionRows.length ? "ready" : "unknown",
      queueDecisionRows.length
        ? `${queueDecisionRows.length} queue launch checkpoint(s); non-ready=${queueDecisionNonReady.length}.`
        : "Queue launch decision rows are unavailable.",
      queueDecisionNonReady.length
        ? "Open Queue Launch Decision rows and Diagnostics cross-links before starting."
        : "Queue launch decision is ready-looking; backend start still re-checks at submission time.",
      queueDecisionNonReady.slice(0, 6).map((row) => `${row.checkpoint || row.key}: ${row.posture}; ${row.action}`),
    );

    add(
      "backend-preflight",
      "Backend Launch Preflight",
      launchScopeBackendPreflightPosture(backendPreflight),
      backendPreflight
        ? `status=${backendPreflight.status || "unknown"}; checks=${backendRows.length}; non-ready=${backendNonReady.length}.`
        : "No cached Pipeline backend preflight payload is loaded.",
      backendPreflight
        ? backendNonReady.length
          ? "Select Backend Launch Preflight rows before submitting a start."
          : "Cached backend preflight is ready-looking; start route still re-checks state at submission time."
        : "Refresh Backend Preflight before relying on Launch scope reconciliation.",
      backendNonReady.slice(0, 6).map((row) => `${row.check}: ${row.posture}; ${row.action}`),
    );

    add(
      "close-readiness",
      "Close-readiness / active work",
      closeReadiness?.safe_to_close === false || closeReadiness?.active_work === true ? "blocked" : closeReadiness ? "ready" : "unknown",
      `snapshot=${snapshot ? (snapshot.pipeline_state || "loaded") : "missing"}; close=${closeReadiness ? (closeReadiness.safe_to_close ? "safe" : "active/blocked") : "unknown"}.`,
      closeReadiness?.safe_to_close === false || closeReadiness?.active_work === true
        ? "Wait for active work to finish or use backend-owned controls intentionally before starting more work."
        : closeReadiness
          ? "Close-readiness does not report an active-work block."
          : "Refresh before launch if close-readiness has not loaded.",
      [
        `Close reason: ${closeReadiness?.reason || "none reported"}`,
        `Activity: ${snapshot?.activity || "none reported"}`,
      ],
    );

    add(
      "schedule-scope",
      "Schedule / override scope",
      outsideWindow ? "blocked" : (schedule.enabled && watchedMode && override ? "review" : schedule.enabled ? "ready" : "unknown"),
      `schedule=${schedule.enabled ? "enabled" : "off/unavailable"}; allowed_now=${evaluation.allowed_now === false ? "no" : "yes/unknown"}; override=${override || "none"}.`,
      outsideWindow
        ? "Wait for the allowed window or choose an explicit one-shot override."
        : override
          ? "Override is intentional-looking; confirm the operator reason before submitting."
          : "No schedule-window block is visible for the selected mode.",
      [
        `Next allowed start: ${typeof scheduleDisplayValue === "function" ? scheduleDisplayValue(evaluation.next_allowed_start) : (evaluation.next_allowed_start || "None")}`,
        `Window end: ${typeof scheduleDisplayValue === "function" ? scheduleDisplayValue(evaluation.current_window_end || evaluation.next_allowed_end) : (evaluation.current_window_end || evaluation.next_allowed_end || "None")}`,
        `Continuous watcher: ${typeof scheduleWatcherSummary === "function" ? scheduleWatcherSummary(schedule) : "unknown"}`,
      ],
    );

    add(
      "recent-launch-command",
      "Recent Launch command",
      launchScopeCommandPosture(latestLaunch),
      latestLaunch
        ? `${latestLaunch.command || "launch"} at ${latestLaunch.at || "unknown time"}; issue=${typeof commandHistoryIssueLevel === "function" ? commandHistoryIssueLevel(latestLaunch) : (latestLaunch.ok ? "ok" : latestLaunch.severity || "unknown")}.`
        : "No recent pipeline/audit/CSV rerun launch command is visible.",
      latestLaunch
        ? "Compare recent launch result with current preflight, Queue, and Diagnostics before retrying."
        : "First launch attempts will create command-history evidence after backend response.",
      [launchSettingsIntentCommandLine(latestLaunch)],
    );

    add(
      "decision-boundary",
      "Decision boundary",
      "ready",
      "This panel reconciles already-loaded evidence; it is not a start button and not a backend reservation.",
      "Submit only after Launch, Queue, Schedule, Settings, Diagnostics, and command history agree enough for the selected risk level.",
      [
        "No filesystem mutation, queue rewrite, settings save, schedule save, publish drain, rename, or media processing happens here.",
        "A real start can still be rejected if runtime state changes after this read-only reconciliation.",
      ],
    );

    return rows.sort((left, right) => launchScopeRank(left.posture) - launchScopeRank(right.posture));
  }

  function launchScopeReconciliationStatus(rows = launchScopeReconciliationRows()) {
    if (!rows.length) return "Not evaluated";
    if (rows.some((row) => row.posture === "blocked")) return "Blocked";
    if (rows.some((row) => row.posture === "high review")) return "High review";
    if (rows.some((row) => row.posture === "review")) return "Review";
    if (rows.some((row) => row.posture === "read-first")) return "Read evidence";
    if (rows.some((row) => row.posture === "unknown")) return "Evidence incomplete";
    return "Ready-looking";
  }

  function launchScopeReconciliationSummaryLines(rows = launchScopeReconciliationRows()) {
    const counts = rows.reduce((acc, row) => {
      const key = row.posture || "unknown";
      acc[key] = (acc[key] || 0) + 1;
      return acc;
    }, {});
    const nonReady = rows.filter((row) => row.posture !== "ready");
    const lines = [
      "Launch scope reconciliation:",
      `Signals: ${rows.length}; ready=${counts.ready || 0}; review=${counts.review || 0}; high review=${counts["high review"] || 0}; blocked=${counts.blocked || 0}; read-first=${counts["read-first"] || 0}; unknown=${counts.unknown || 0}.`,
      "Decision rule: the visible Queue table, selected Launch mode, cached backend preflight, Schedule posture, close-readiness, and recent command evidence must agree before starting queued work.",
    ];
    if (nonReady.length) {
      lines.push("First action: select blocked/review/read-first rows below and reconcile the evidence before using backend-owned start buttons.");
      nonReady.slice(0, 8).forEach((row) => lines.push(`- ${row.signal}: ${row.posture}; ${row.action}`));
      if (nonReady.length > 8) lines.push(`- ${nonReady.length - 8} more scope signal(s) need review.`);
    } else {
      lines.push("First action: no local scope mismatch is visible; backend start routes still re-check and may reject at submission time.");
    }
    lines.push("Mutation guardrail: this reconciliation is read-only and cannot launch, save settings, rewrite queue state, drain, publish, rename, delete, or touch media files.");
    return lines;
  }

  function selectedLaunchScopeReconciliationRow(rows) {
    const source = Array.isArray(rows) ? rows : [];
    return source.find((row) => row.key === state.selectedLaunchScopeReconciliationKey) || source.find((row) => row.posture !== "ready") || source[0] || null;
  }

  function launchScopeReconciliationDetailLines(row) {
    if (!row) {
      return [
        "Launch scope reconciliation:",
        "No scope signal is selected.",
        "Mutation guardrail: this detail panel is read-only.",
      ];
    }
    const lines = [
      "Launch scope reconciliation:",
      `Signal: ${row.signal || "unknown"}`,
      `Posture: ${row.posture || "unknown"}`,
      `Evidence: ${row.evidence || ""}`,
      `Safe next step: ${row.action || ""}`,
    ];
    if (row.detail.length) {
      lines.push("", "Detail:");
      row.detail.forEach((item) => lines.push(`- ${typeof item === "object" ? JSON.stringify(item) : String(item)}`));
    }
    lines.push("", "Guardrail: backend start routes remain authoritative and re-check runtime state at submission time.");
    return lines;
  }

  function selectLaunchScopeReconciliationRow(row) {
    state.selectedLaunchScopeReconciliationKey = row?.key || "";
    renderLaunchScopeReconciliation();
  }

  function renderLaunchScopeReconciliation(request = collectPipelineStartRequest(), payload = launchSettingsIntentPayload()) {
    const rows = launchScopeReconciliationRows(request, payload);
    if (state.selectedLaunchScopeReconciliationKey && !rows.some((row) => row.key === state.selectedLaunchScopeReconciliationKey)) {
      state.selectedLaunchScopeReconciliationKey = "";
    }
    const selected = selectedLaunchScopeReconciliationRow(rows);
    const status = launchScopeReconciliationStatus(rows);
    setText("launch-scope-reconciliation-status", status);
    const statusNode = byId("launch-scope-reconciliation-status");
    if (statusNode) statusNode.dataset.state = launchBackendPreflightStatusState(status === "Ready-looking" ? "Ready" : status);
    setText("launch-scope-reconciliation-summary", launchScopeReconciliationSummaryLines(rows).join("\n"));
    setText("launch-scope-reconciliation-detail", launchScopeReconciliationDetailLines(selected).join("\n"));
    const tbody = byId("launch-scope-reconciliation-rows");
    if (!tbody) return;
    if (!rows.length) {
      clearRows(tbody, 4, "No launch scope reconciliation rows loaded.");
      updateTableStatusLegend("launch-scope-reconciliation-legend", tbody, "Launch scope reconciliation rows");
      return;
    }
    tbody.replaceChildren();
    rows.forEach((item) => {
      const row = document.createElement("tr");
      row.dataset.status = launchScopeStatusValue(item.posture);
      appendCells(row, [item.signal, item.posture, item.evidence, item.action]);
      if (typeof makeRowSelectable === "function") {
        makeRowSelectable(row, () => selectLaunchScopeReconciliationRow(item), {
          selected: item.key === selected?.key,
          label: `Launch scope ${item.signal} ${item.posture}`,
        });
      }
      tbody.appendChild(row);
    });
    updateTableStatusLegend("launch-scope-reconciliation-legend", tbody, "Launch scope reconciliation rows");
  }

  function launchStartDecisionPostureFromStatus(status) {
    const normalized = String(status || "").toLowerCase();
    if (!normalized) return "unknown";
    if (
      normalized.includes("blocked")
      || normalized.includes("active work")
      || normalized.includes("backend issue")
      || normalized.includes("settings issue")
      || normalized.includes("outside schedule")
      || normalized.includes("do not launch")
      || normalized.includes("blocked proof")
      || normalized.includes("blocked checklist")
    ) {
      return "blocked";
    }
    if (
      normalized.includes("not loaded")
      || normalized.includes("no snapshot")
      || normalized.includes("checking")
      || normalized.includes("evidence incomplete")
      || normalized.includes("unknown")
      || normalized.includes("no command history")
      || normalized.includes("no launch commands")
      || normalized.includes("no checklist")
    ) {
      return "unknown";
    }
    if (
      normalized.includes("high review")
      || normalized.includes("review")
      || normalized.includes("needs")
      || normalized.includes("read evidence")
      || normalized.includes("issue")
      || normalized.includes("warning")
      || normalized.includes("preview required")
    ) {
      return "review";
    }
    return "ready";
  }

  function launchStartDecisionWorstPosture(postures = []) {
    const values = Array.isArray(postures) ? postures.map((item) => String(item || "").toLowerCase()) : [];
    if (values.includes("blocked")) return "blocked";
    if (values.includes("review")) return "review";
    if (values.includes("unknown")) return "unknown";
    return "ready";
  }

  function launchStartDecisionRank(posture) {
    const normalized = String(posture || "").toLowerCase();
    if (normalized === "blocked") return 0;
    if (normalized === "review") return 1;
    if (normalized === "unknown") return 2;
    return 3;
  }

  function launchStartDecisionRowStatus(posture) {
    const normalized = String(posture || "").toLowerCase();
    if (normalized === "blocked") return "blocked";
    if (normalized === "review") return "warning";
    if (normalized === "unknown") return "unknown";
    return "match";
  }

  function launchStartDecisionRows(request = collectPipelineStartRequest(), payload = launchSettingsIntentPayload()) {
    const context = launchSettingsIntentPayload(payload);
    const snapshot = context.snapshot || null;
    const closeReadiness = context.closeReadiness || null;
    const schedule = context.schedule || {};
    const history = typeof getCommandHistory === "function" ? getCommandHistory() : [];
    const queueRows = typeof getLastQueueRows === "function" ? getLastQueueRows() : [];
    const queuePayload = typeof getLastQueuePayload === "function" ? getLastQueuePayload() : null;
    const backendPayloads = getLastLaunchBackendPreflightPayloads();
    const backendRows = launchBackendPreflightRows(backendPayloads);
    const backendNonReady = backendRows.filter((row) => String(row.posture || "").toLowerCase() !== "ready");
    const settingsIntentRows = launchSettingsIntentRows(request, context);
    const policyRows = launchPolicyBoundaryRows();
    const scopeRows = launchScopeReconciliationRows(request, context);
    const realMediaRows = launchRealMediaProofRows(getLaunchRealMediaContext());
    const sampleRows = launchSampleExecutionRows(getLaunchRealMediaContext());
    const commandRows = typeof launchCommandReviewRows === "function" ? launchCommandReviewRows(history) : [];
    const rows = [];
    const add = (key, signal, posture, evidence, action, detail = []) => rows.push({
      key,
      signal,
      posture,
      evidence,
      action,
      detail: Array.isArray(detail) ? detail.filter(Boolean) : [],
    });

    const pipelineBackendPreflight = launchBackendPreflightPayloadForTarget("pipeline");
    const readinessPayload = {
      snapshot,
      closeReadiness,
      schedule,
      settings: launchSettingsWorkspace(),
      backendPreflight: pipelineBackendPreflight,
      backendReadiness: pipelineBackendPreflight?.operator_readiness || null,
    };
    const readinessStatus = typeof launchReadinessStatus === "function"
      ? launchReadinessStatus(readinessPayload)
      : "Unknown";
    add(
      "launch-readiness",
      "Launch readiness",
      launchStartDecisionPostureFromStatus(readinessStatus),
      `status=${readinessStatus}; snapshot=${snapshot ? "loaded" : "missing"}; close=${closeReadiness ? (closeReadiness.safe_to_close ? "safe" : "active/blocked") : "unknown"}.`,
      launchStartDecisionPostureFromStatus(readinessStatus) === "blocked"
        ? "Resolve the Launch Readiness blocker before pressing Start."
        : "Use this as the top-level readiness posture; backend start still re-checks.",
      typeof launchReadinessLines === "function"
        ? launchReadinessLines(readinessPayload)
        : [],
    );

    const timingStatus = typeof launchTimingStatus === "function" ? launchTimingStatus(context, request) : "Unknown";
    add(
      "timing-schedule",
      "Timing / schedule",
      launchStartDecisionPostureFromStatus(timingStatus),
      `status=${timingStatus}; mode=${pipelineModeLabel(request?.mode)}; override=${request?.schedule_override || "none"}.`,
      launchStartDecisionPostureFromStatus(timingStatus) === "blocked"
        ? "Wait for the allowed window, change mode, or choose an intentional one-shot override."
        : "Confirm the selected mode and schedule override match the operator intent.",
      typeof launchTimingTrustLines === "function" ? launchTimingTrustLines(context, request) : [],
    );

    const backendStatus = launchBackendPreflightOverallStatus(backendPayloads);
    add(
      "backend-preflight",
      "Backend preflight",
      launchStartDecisionPostureFromStatus(backendStatus),
      `status=${backendStatus}; targets=${backendPayloads.length}; checks=${backendRows.length}; non-ready=${backendNonReady.length}; fetch failures=${getLastLaunchBackendPreflightRefreshInfo().fetch_failure_count || 0}.`,
      backendPayloads.length
        ? backendNonReady.length
          ? "Select Backend Launch Preflight non-ready rows before submitting a start."
          : "Cached backend preflight is ready-looking; the start route still re-checks state."
        : "Refresh Backend Preflight before trusting a start decision.",
      launchBackendPreflightSummaryLines(backendPayloads),
    );

    const queueStatus = typeof queueLaunchDecisionStatus === "function"
      ? queueLaunchDecisionStatus(queuePayload, queueRows, history)
      : (queueRows.length ? "Ready" : "Evidence incomplete");
    const queueDecisionRows = typeof queueLaunchDecisionRows === "function" ? queueLaunchDecisionRows(queuePayload, queueRows, history) : [];
    const queueNonReady = queueDecisionRows.filter((row) => {
      const posture = typeof queueLaunchDecisionPostureStatus === "function"
        ? queueLaunchDecisionPostureStatus(row.posture)
        : String(row.posture || "").toLowerCase();
      return !["ready", "normal", "match"].includes(posture);
    });
    add(
      "queue-decision",
      "Queue launch decision",
      launchStartDecisionPostureFromStatus(queueStatus),
      `status=${queueStatus}; loaded rows=${queueRows.length}; decision rows=${queueDecisionRows.length}; non-ready=${queueNonReady.length}.`,
      queueNonReady.length
        ? "Inspect Queue Launch Decision rows and Diagnostics cross-links before pressing Start."
        : "Queue decision is ready-looking; backend Launch still owns actual processing scope.",
      typeof queueLaunchDecisionSummaryLines === "function" ? queueLaunchDecisionSummaryLines(queuePayload, queueRows, history) : [],
    );

    const settingsIntentStatus = launchSettingsIntentStatus(settingsIntentRows);
    const policyStatus = launchPolicyBoundaryStatus(policyRows);
    add(
      "settings-policy",
      "Settings / policy",
      launchStartDecisionWorstPosture([
        launchStartDecisionPostureFromStatus(settingsIntentStatus),
        launchStartDecisionPostureFromStatus(policyStatus),
      ]),
      `intent=${settingsIntentStatus}; active policy=${policyStatus}; settings loaded=${launchSettingsWorkspace()?.schema_version ? "yes" : "no"}.`,
      settingsIntentRows.some((row) => row.posture !== "ready") || policyRows.some((row) => !["ready", "launch-active", "same as saved"].includes(row.launchState))
        ? "Resolve staged/saved settings evidence before unattended starts; Launch uses saved backend settings only."
        : "No local settings/policy blocker is visible.",
      [
        ...launchSettingsIntentSummaryLines(settingsIntentRows),
        "",
        ...launchPolicyBoundarySummaryLines(policyRows),
      ],
    );

    const scopeStatus = launchScopeReconciliationStatus(scopeRows);
    add(
      "scope-reconciliation",
      "Scope reconciliation",
      launchStartDecisionPostureFromStatus(scopeStatus),
      `status=${scopeStatus}; scope signals=${scopeRows.length}.`,
      scopeRows.some((row) => row.posture !== "ready")
        ? "Read scope mismatches before treating visible rows, filters, commands, and backend preflight as aligned."
        : "No local scope mismatch is visible.",
      launchScopeReconciliationSummaryLines(scopeRows),
    );

    const proofStatus = launchRealMediaProofStatus(realMediaRows);
    add(
      "real-media-proof",
      "Real-media proof",
      launchStartDecisionPostureFromStatus(proofStatus),
      `status=${proofStatus}; proof rows=${realMediaRows.length}; sample=${launchRealMediaSample(getLaunchRealMediaContext())?.label || "none selected"}.`,
      proofStatus === "Evidence loaded"
        ? "Loaded sample proof has no local proof blocker."
        : "Use a small known sample and complete proof rows before treating WebView as daily-driver ready.",
      launchRealMediaProofSummaryLines(getLaunchRealMediaContext(), realMediaRows),
    );

    const categoryCoverage = launchSampleSetCoverageEvidence(getLaunchRealMediaContext());
    add(
      "pilot-category-coverage",
      "Pilot category coverage",
      categoryCoverage.posture === "match" ? "ready" : categoryCoverage.posture === "blocked" ? "blocked" : categoryCoverage.posture === "unknown" ? "unknown" : "review",
      categoryCoverage.evidence,
      categoryCoverage.nextCheck,
      categoryCoverage.detail,
    );

    const sampleStatus = launchSampleExecutionStatus(sampleRows);
    add(
      "sample-execution",
      "Sample execution checklist",
      launchStartDecisionPostureFromStatus(sampleStatus),
      `status=${sampleStatus}; checklist rows=${sampleRows.length}; required=${sampleRows.filter((row) => row.required).length}.`,
      sampleStatus === "Checklist visible"
        ? "Sample execution checklist is visible; complete post-run proof after a real run."
        : "Review required sample checklist rows before a real-media pilot.",
      launchSampleExecutionSummaryLines(getLaunchRealMediaContext(), sampleRows),
    );

    const commandStatus = typeof launchCommandReviewStatus === "function" ? launchCommandReviewStatus(history) : "No command history";
    const latestLaunch = commandRows[0] || null;
    add(
      "recent-command",
      "Recent command evidence",
      launchStartDecisionPostureFromStatus(commandStatus),
      `status=${commandStatus}; launch commands=${commandRows.length}; latest=${latestLaunch?.latestCommand || "none"}.`,
      latestLaunch
        ? "Compare recent command result with current preflight and Diagnostics before retrying."
        : "No recent Launch command is visible; the next start response will create command evidence.",
      typeof launchCommandReviewSummaryLines === "function" ? launchCommandReviewSummaryLines(history) : [],
    );

    add(
      "mutation-boundary",
      "Start boundary",
      "ready",
      "This summary is read-only and never reserves locks, starts processes, changes queue scope, saves settings, drains, publishes, renames, deletes, or touches media.",
      "Only backend-owned Start controls can submit a launch request, and backend routes remain final authority.",
      [
        "The summary rolls up visible evidence so the operator can decide whether pressing Start is sensible.",
        "Runtime state can change after this render; backend start routes still accept or reject at submission time.",
      ],
    );

    return rows.sort((left, right) => launchStartDecisionRank(left.posture) - launchStartDecisionRank(right.posture));
  }

  function launchStartDecisionStatus(rows = launchStartDecisionRows()) {
    if (!rows.length) return "Not evaluated";
    if (rows.some((row) => row.posture === "blocked")) return "Blocked";
    if (rows.some((row) => row.posture === "review")) return "Review before start";
    if (rows.some((row) => row.posture === "unknown")) return "Evidence incomplete";
    return "Ready to submit";
  }

  function launchStartDecisionSummaryLines(rows = launchStartDecisionRows()) {
    const counts = rows.reduce((acc, row) => {
      const key = row.posture || "unknown";
      acc[key] = (acc[key] || 0) + 1;
      return acc;
    }, {});
    const nonReady = rows.filter((row) => row.posture !== "ready");
    const lines = [
      "Launch start decision summary:",
      `Signals: ${rows.length}; ready=${counts.ready || 0}; review=${counts.review || 0}; blocked=${counts.blocked || 0}; unknown=${counts.unknown || 0}.`,
      "Decision rule: treat Start as sensible only when Launch readiness, backend preflight, Queue, Settings, schedule/close-readiness, real-media proof, sample checklist, and recent command evidence agree.",
    ];
    if (nonReady.length) {
      lines.push("First action: select the highest-severity row below and reconcile it before using backend-owned Start controls.");
      nonReady.slice(0, 8).forEach((row) => lines.push(`- ${row.signal}: ${row.posture}; ${row.action}`));
      if (nonReady.length > 8) lines.push(`- ${nonReady.length - 8} more start decision signal(s) need review.`);
    } else {
      lines.push("First action: no local blockers are visible; backend start routes still re-check locks, schedule, settings, and runtime state.");
    }
    lines.push("Mutation guardrail: this summary is read-only and cannot launch, save, drain, publish, rename, rewrite queue state, or touch media files.");
    return lines;
  }

  function selectedLaunchStartDecisionRow(rows = []) {
    const source = Array.isArray(rows) ? rows : [];
    return source.find((row) => row.key === state.selectedLaunchStartDecisionKey)
      || source.find((row) => row.posture !== "ready")
      || source[0]
      || null;
  }

  function launchStartDecisionDetailLines(row) {
    if (!row) {
      return [
        "Launch start decision summary:",
        "No start decision signal is selected.",
        "Mutation guardrail: this detail panel is read-only.",
      ];
    }
    const lines = [
      "Launch start decision summary:",
      `Signal: ${row.signal || "unknown"}`,
      `Posture: ${row.posture || "unknown"}`,
      `Evidence: ${row.evidence || ""}`,
      `Operator action: ${row.action || ""}`,
    ];
    const detail = Array.isArray(row.detail) ? row.detail : [];
    if (detail.length) {
      lines.push("", "Detail:");
      detail.forEach((item) => lines.push(`- ${typeof item === "object" ? JSON.stringify(item) : String(item)}`));
    }
    lines.push("", "Guardrail: backend-owned start routes remain the only path that can launch work and they re-check runtime state at submission time.");
    return lines;
  }

  function selectLaunchStartDecisionRow(row) {
    state.selectedLaunchStartDecisionKey = row?.key || "";
    renderLaunchStartDecisionSummary();
  }

  function renderLaunchStartDecisionSummary(request = collectPipelineStartRequest(), payload = launchSettingsIntentPayload()) {
    const rows = launchStartDecisionRows(request, payload);
    if (state.selectedLaunchStartDecisionKey && !rows.some((row) => row.key === state.selectedLaunchStartDecisionKey)) {
      state.selectedLaunchStartDecisionKey = "";
    }
    const selected = selectedLaunchStartDecisionRow(rows);
    const status = launchStartDecisionStatus(rows);
    setText("launch-start-decision-status", status);
    const statusNode = byId("launch-start-decision-status");
    if (statusNode) {
      const stateStatus = status === "Ready to submit" ? "Ready" : status === "Review before start" ? "Review" : status;
      statusNode.dataset.state = launchBackendPreflightStatusState(stateStatus);
    }
    setText("launch-start-decision-summary", launchStartDecisionSummaryLines(rows).join("\n"));
    setText("launch-start-decision-detail", launchStartDecisionDetailLines(selected).join("\n"));
    const tbody = byId("launch-start-decision-rows");
    if (!tbody) return;
    if (!rows.length) {
      clearRows(tbody, 4, "No launch start decision rows loaded.");
      updateTableStatusLegend("launch-start-decision-legend", tbody, "Launch start decision rows");
      return;
    }
    tbody.replaceChildren();
    rows.forEach((item) => {
      const row = document.createElement("tr");
      row.dataset.status = launchStartDecisionRowStatus(item.posture);
      appendCells(row, [item.signal, item.posture, item.evidence, item.action]);
      if (typeof makeRowSelectable === "function") {
        makeRowSelectable(row, () => selectLaunchStartDecisionRow(item), {
          selected: item.key === selected?.key,
          label: `Launch start decision ${item.signal} ${item.posture}`,
        });
      }
      tbody.appendChild(row);
    });
    updateTableStatusLegend("launch-start-decision-legend", tbody, "Launch start decision rows");
  }

    return {
      launchScopeStatusValue,
      launchScopeRank,
      launchScopeLatestLaunchCommand,
      launchScopeCommandPosture,
      launchScopeBackendPreflightPosture,
      launchScopeQueuePosture,
      launchScopeReconciliationRows,
      launchScopeReconciliationStatus,
      launchScopeReconciliationSummaryLines,
      launchScopeReconciliationDetailLines,
      renderLaunchScopeReconciliation,
      launchStartDecisionPostureFromStatus,
      launchStartDecisionWorstPosture,
      launchStartDecisionRank,
      launchStartDecisionRowStatus,
      launchStartDecisionRows,
      launchStartDecisionStatus,
      launchStartDecisionSummaryLines,
      launchStartDecisionDetailLines,
      renderLaunchStartDecisionSummary,
    };
  }

  window.__launchViewScopeModule = {
    createLaunchScopeModule,
  };
})();
