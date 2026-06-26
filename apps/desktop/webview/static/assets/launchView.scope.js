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
      showPage = null,
      activateLaunchTab = null,
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
      "Queue tab display state",
      queueScope ? (queueScope.active ? "review" : "ready") : "unknown",
      queueScope
        ? `filters=${queueScope.active ? "active" : "inactive"}; visible=${queueScope.visibleRows}/${queueScope.totalRows}; hidden blocked=${queueScope.hiddenBlocked}; hidden review=${queueScope.hiddenReview}.`
        : "Queue tab display state is unavailable.",
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
      "Queue-to-Launch Handoff",
      queueDecisionNonReady.some((row) => launchScopeStatusValue(row.posture) === "blocked") ? "blocked" : queueDecisionNonReady.length ? "review" : queueDecisionRows.length ? "ready" : "unknown",
      queueDecisionRows.length
        ? `${queueDecisionRows.length} queue-to-Launch handoff checkpoint(s); non-ready=${queueDecisionNonReady.length}.`
        : "Queue-to-Launch handoff rows are unavailable.",
      queueDecisionNonReady.length
        ? "Open Queue-to-Launch Handoff rows and Diagnostics cross-links before starting."
        : "Queue-to-Launch handoff is ready-looking; backend start still re-checks at submission time.",
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

  function launchStartDecisionAdvisoryPosture(posture) {
    return String(posture || "").toLowerCase() === "blocked" ? "review" : posture;
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
    const pipelineBackendPreflight = launchBackendPreflightPayloadForTarget("pipeline");
    const pipelineBackendPayloads = pipelineBackendPreflight ? [pipelineBackendPreflight] : [];
    const pipelineBackendRows = launchBackendPreflightRows(pipelineBackendPayloads);
    const pipelineBackendNonReady = pipelineBackendRows.filter((row) => String(row.posture || "").toLowerCase() !== "ready");
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

    const backendStatus = launchBackendPreflightOverallStatus(pipelineBackendPayloads);
    add(
      "backend-preflight",
      "Backend preflight",
      launchStartDecisionPostureFromStatus(backendStatus),
      `status=${backendStatus}; target=pipeline; checks=${pipelineBackendRows.length}; non-ready=${pipelineBackendNonReady.length}; other targets=${Math.max(backendPayloads.length - pipelineBackendPayloads.length, 0)}; fetch failures=${getLastLaunchBackendPreflightRefreshInfo().fetch_failure_count || 0}.`,
      pipelineBackendPayloads.length
        ? pipelineBackendNonReady.length
          ? "Select Pipeline Backend Launch Preflight non-ready rows before submitting a pipeline start."
          : "Cached Pipeline backend preflight is ready-looking; the start route still re-checks state."
        : "Refresh Pipeline Backend Preflight before trusting a pipeline start decision.",
      launchBackendPreflightSummaryLines(pipelineBackendPayloads),
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
      "Queue-to-Launch handoff",
      launchStartDecisionPostureFromStatus(queueStatus),
      `status=${queueStatus}; loaded rows=${queueRows.length}; decision rows=${queueDecisionRows.length}; non-ready=${queueNonReady.length}.`,
      queueNonReady.length
        ? "Inspect Queue-to-Launch Handoff rows and Diagnostics cross-links before pressing Start."
        : "Queue-to-Launch handoff is ready-looking; backend Launch still owns actual processing scope.",
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
      launchStartDecisionAdvisoryPosture(launchStartDecisionPostureFromStatus(scopeStatus)),
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
      launchStartDecisionAdvisoryPosture(launchStartDecisionPostureFromStatus(proofStatus)),
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

  function launchCompactGateState(posture) {
    const normalized = String(posture || "").trim().toLowerCase();
    if (normalized === "blocked" || normalized === "failed" || normalized === "error" || normalized === "will fail" || normalized === "forced") return "blocked";
    if (normalized === "running" || normalized === "active" || normalized === "active work") return "running";
    if (normalized === "ready" || normalized === "ok" || normalized === "match" || normalized === "normal" || normalized === "all clear") return "ready";
    if (
      normalized === "unknown"
      || normalized === "neutral"
      || normalized === "not loaded"
      || normalized === "needs evidence"
      || normalized === "evidence incomplete"
      || normalized === "no history"
      || normalized === "no command history"
      || normalized === "loading"
      || normalized === "stale"
      || normalized === "stale evidence"
    ) return "unknown";
    return "warning";
  }

  function launchCompactGateValue(status) {
    const normalized = String(status || "").toLowerCase();
    if (normalized === "ready") return "OK";
    if (normalized === "blocked") return "Will Fail";
    if (normalized === "running") return "Active";
    if (normalized === "unknown") return "Needs Evidence";
    return "At Risk";
  }

  function launchCompactGateDefaultNote(status) {
    const normalized = String(status || "").toLowerCase();
    if (normalized === "ready") return "Clear";
    if (normalized === "blocked") return "Blocked";
    if (normalized === "running") return "Active";
    if (normalized === "unknown") return "Not loaded";
    return "At Risk";
  }

  function launchCompactGateRow(key, label, status, note, summary, detail = [], target = {}) {
    const stateValue = launchCompactGateState(status);
    const safeTarget = target && typeof target === "object" ? target : {};
    return {
      key,
      label,
      status: stateValue,
      value: launchCompactGateValue(stateValue),
      note: note || launchCompactGateDefaultNote(stateValue),
      summary,
      detail: Array.isArray(detail) ? detail.filter(Boolean) : [],
      target: safeTarget,
      required: safeTarget.required !== false,
    };
  }

  function launchCompactGateRequiredRows(rows = []) {
    return (Array.isArray(rows) ? rows : []).filter((row) => row?.required !== false);
  }

  function launchCompactGateHeaderState(status) {
    return launchCompactGateState(status);
  }

  function launchCompactGateActionLabel(row) {
    const target = row?.target || {};
    return target.label || "Select this gate to open and highlight its owner evidence.";
  }

  function launchCompactGateActivateTargetTab(pageId, tabId) {
    if (!tabId) return;
    if (pageId === "launch" && typeof activateLaunchTab === "function") {
      activateLaunchTab(tabId, { persist: false });
      return;
    }
    const page = Array.from(document.querySelectorAll("[data-page-panel]"))
      .find((node) => node.dataset?.pagePanel === pageId);
    if (!page) return;
    const tabDatasetKey = pageId === "diagnostics" ? "diagTab" : "";
    if (!tabDatasetKey) return;
    if (pageId === "diagnostics") {
      const buttons = Array.from(page.querySelectorAll(".settings-tab-btn[data-diag-tab]"));
      const panels = Array.from(page.querySelectorAll(".settings-tab-pane[data-diag-tab]"));
      if (!buttons.length || !panels.length) return;
      const selected = buttons.some((button) => button.dataset.diagTab === tabId) ? tabId : "triage";
      buttons.forEach((button) => {
        const active = button.dataset.diagTab === selected;
        button.setAttribute("aria-selected", String(active));
      });
      panels.forEach((panel) => {
        panel.classList.toggle("is-active", panel.dataset.diagTab === selected);
      });
      try { localStorage.setItem("mediapipeline-diag-tab", selected); } catch (_) {}
      if (typeof window.mediaPipelineAppLifecycle?.syncTabAccessibility === "function") window.mediaPipelineAppLifecycle.syncTabAccessibility();
      if (typeof updatePagePanelEmptyStates === "function") updatePagePanelEmptyStates();
      return;
    }
    const button = Array.from(page.querySelectorAll(".settings-tab-btn"))
      .find((node) => node.dataset?.[tabDatasetKey] === tabId);
    if (button && typeof button.click === "function") button.click();
  }

  function launchCompactGateQueryTarget(target = {}) {
    const selectors = [
      target.rowSelector,
      target.selector,
      target.fallbackSelector,
      target.focusSelector,
    ].filter(Boolean);
    for (const selector of selectors) {
      const node = document.querySelector(selector);
      if (node) return node;
    }
    if (target.focusId) return byId(target.focusId);
    return null;
  }

  function launchCompactGateRevealTarget(node) {
    if (!node) return;
    const advancedGate = node.closest("[data-advanced]") || node.closest("[data-panel-advanced]");
    if (advancedGate && !document.body.classList.contains("advanced-mode")) {
      advancedGate.classList.add("is-attention-reveal");
    }
    const evidenceGate = node.closest("[data-panel-type='evidence']");
    if (evidenceGate && document.body.classList.contains("evidence-hidden")) {
      evidenceGate.classList.add("is-attention-reveal");
    }
    const launchEvidenceBody = node.closest("#launch-evidence-body");
    if (launchEvidenceBody?.classList?.contains("is-collapsed")) {
      launchEvidenceBody.classList.add("is-attention-reveal");
    }
  }

  function launchCompactGateHighlightTarget(node) {
    if (!node || typeof node.classList === "undefined") return;
    launchCompactGateRevealTarget(node);
    document.querySelectorAll(".is-attention-target").forEach((item) => item.classList.remove("is-attention-target"));
    node.classList.add("is-attention-target");
    if (typeof node.scrollIntoView === "function") {
      try {
        node.scrollIntoView({ block: "center", inline: "nearest", behavior: "smooth" });
      } catch (_) {
        node.scrollIntoView(false);
      }
    }
    const hadTabIndex = node.hasAttribute("tabindex");
    if (!hadTabIndex) node.setAttribute("tabindex", "-1");
    if (typeof node.focus === "function") {
      try {
        node.focus({ preventScroll: true });
      } catch (_) {
        node.focus();
      }
    }
    window.setTimeout(() => {
      node.classList.remove("is-attention-target");
      document.querySelectorAll(".is-attention-reveal").forEach((item) => item.classList.remove("is-attention-reveal"));
      if (!hadTabIndex && node.getAttribute("tabindex") === "-1") node.removeAttribute("tabindex");
    }, 2400);
  }

  function launchCompactGateOpenTarget(row) {
    const target = row?.target || {};
    const showPageFn = typeof showPage === "function" ? showPage : window.showPage;
    if (target.page && typeof showPageFn === "function") showPageFn(target.page);
    launchCompactGateActivateTargetTab(target.page || "", target.tab || "");
    let node = launchCompactGateQueryTarget(target);
    launchCompactGateRevealTarget(node);
    if (node?.matches?.("tr[data-selectable-row='true']")) {
      node.click();
      node = launchCompactGateQueryTarget(target) || node;
      launchCompactGateRevealTarget(node);
    }
    if (node) {
      launchCompactGateHighlightTarget(node);
      setText("pipeline-compact-gate-detail", `${row.label}: ${row.value}. ${row.summary} ${launchCompactGateActionLabel(row)} Backend start remains authoritative.`);
    } else {
      setText("pipeline-compact-gate-detail", `${row?.label || "Gate"}: ${row?.value || "Needs Evidence"}. Target evidence is not rendered yet. Refresh and retry this gate. Backend start remains authoritative.`);
    }
  }

  function launchCompactGateNonReadyCount(rows = []) {
    return (Array.isArray(rows) ? rows : []).filter((row) => {
      const posture = String(row?.posture || row?.status || row?.launchState || "").toLowerCase();
      return posture && !["ready", "ok", "match", "same as saved", "launch-active"].includes(posture);
    }).length;
  }

  function launchCompactGateSettingsRows(rows = []) {
    const owned = new Set(["saved-settings", "staged-settings", "risk-handoff"]);
    return (Array.isArray(rows) ? rows : []).filter((row) => owned.has(row?.key));
  }

  function launchCompactGateSettingsPosture(settingsRows = [], policyRows = []) {
    const settingsPostures = (Array.isArray(settingsRows) ? settingsRows : []).map((row) => {
      const posture = row?.key === "staged-settings"
        ? launchStartDecisionAdvisoryPosture(row?.posture)
        : row?.posture;
      return String(posture || "unknown");
    });
    const policyPostures = (Array.isArray(policyRows) ? policyRows : []).map((row) => {
      const launchState = String(row?.launchState || "");
      const posture = launchStartDecisionPostureFromStatus(launchState);
      return launchState.toLowerCase().includes("blocked") ? launchStartDecisionAdvisoryPosture(posture) : posture;
    });
    return launchStartDecisionWorstPosture([...settingsPostures, ...policyPostures]);
  }

  function launchCompactGateBackendActiveWorkBlock(row) {
    const tokens = [
      row?.checkKey,
      row?.key,
      row?.check,
    ].map((item) => String(item || "").trim().toLowerCase()).filter(Boolean);
    return tokens.some((token) => (
      token === "active_work"
      || token.endsWith(":active_work")
      || token === "process_launch_lock"
      || token.endsWith(":process_launch_lock")
      || token.includes("active work")
      || token.includes("launch lock")
    ));
  }

  function launchCompactGateBackendActiveWorkOnly(rows = []) {
    const blockedRows = (Array.isArray(rows) ? rows : []).filter((row) => launchCompactGateState(row?.posture) === "blocked");
    return blockedRows.length > 0 && blockedRows.every(launchCompactGateBackendActiveWorkBlock);
  }

  function launchCompactGateQueueBlockedOnlyByActiveWork(queueRows = [], backendRows = []) {
    const blockedRows = (Array.isArray(queueRows) ? queueRows : []).filter((row) => {
      const posture = typeof queueLaunchDecisionPostureStatus === "function"
        ? queueLaunchDecisionPostureStatus(row?.posture)
        : String(row?.posture || "").toLowerCase();
      return launchCompactGateState(posture) === "blocked";
    });
    if (!blockedRows.length || !launchCompactGateBackendActiveWorkOnly(backendRows)) return false;
    return blockedRows.every((row) => String(row?.key || "").toLowerCase() === "backend-launch-preflight");
  }

  function launchCompactGateRows(request = collectPipelineStartRequest(), payload = launchSettingsIntentPayload()) {
    const context = launchSettingsIntentPayload(payload);
    const history = typeof getCommandHistory === "function" ? getCommandHistory() : [];
    const queueRows = typeof getLastQueueRows === "function" ? getLastQueueRows() : [];
    const queuePayload = typeof getLastQueuePayload === "function" ? getLastQueuePayload() : null;
    const pipelineBackendPreflight = launchBackendPreflightPayloadForTarget("pipeline");
    const pipelineBackendPayloads = pipelineBackendPreflight ? [pipelineBackendPreflight] : [];
    const backendRows = launchBackendPreflightRows(pipelineBackendPayloads);
    const backendFetchFailures = getLastLaunchBackendPreflightRefreshInfo().fetch_failure_count || 0;

    const rows = [];
    if (!pipelineBackendPreflight) {
      rows.push(launchCompactGateRow(
        "backend",
        "Backend",
        "unknown",
        "Refresh",
        "Refresh Backend Preflight before submitting normal start modes.",
        ["No cached Pipeline backend preflight is loaded for the current form state."],
        {
          page: "diagnostics",
          tab: "readiness",
          selector: "#launch-backend-preflight-refresh-button",
          fallbackSelector: "#launch-backend-preflight-summary",
          label: "Opened Diagnostics > Readiness > Backend Preflight. Refresh the backend preflight checks.",
        },
      ));
    } else {
      const backendStatus = launchBackendPreflightOverallStatus(pipelineBackendPayloads);
      const backendActiveWorkOnly = launchCompactGateBackendActiveWorkOnly(backendRows);
      const backendBlocked = !backendActiveWorkOnly && (pipelineBackendPreflight?.can_request_start === false
        || String(pipelineBackendPreflight?.status || "").toLowerCase() === "blocked"
        || backendRows.some((row) => launchCompactGateState(row?.posture) === "blocked"));
      const backendReviewRows = backendRows.filter((row) => launchCompactGateState(row?.posture) === "warning");
      const backendUnknownRows = backendRows.filter((row) => launchCompactGateState(row?.posture) === "unknown");
      const backendGateStatus = backendActiveWorkOnly && !backendReviewRows.length && !backendUnknownRows.length
        ? "running"
        : backendBlocked
        ? "blocked"
        : (backendReviewRows.length ? "warning" : launchStartDecisionPostureFromStatus(backendStatus));
      const backendGateState = launchCompactGateState(backendGateStatus);
      rows.push(launchCompactGateRow(
        "backend",
        "Backend",
        backendGateStatus,
        backendGateState === "running"
          ? "Active"
          : backendBlocked
          ? "Blocked"
          : (backendGateState === "warning" ? `At Risk ${backendReviewRows.length || 1}` : (backendGateState === "unknown" ? "Needs Evidence" : `${backendRows.length || 0} checks`)),
        backendGateState === "running"
          ? "Backend preflight is blocking duplicate starts because active work is already running; this is expected during normal processing."
          : backendBlocked
          ? "Backend preflight would reject normal Start Pipeline now; backend start remains authoritative."
          : (backendGateState === "warning"
            ? "Backend preflight has review checks that may affect launch; backend start remains authoritative."
            : (backendGateState === "unknown" || backendUnknownRows.length
              ? "Backend preflight evidence is incomplete; refresh before trusting the cached posture."
              : "Backend preflight is ready-looking; backend start still re-checks state at submission time.")),
        launchBackendPreflightSummaryLines(pipelineBackendPayloads),
        {
          page: "diagnostics",
          tab: "readiness",
          rowSelector: "#launch-backend-preflight-rows tr[data-selectable-row='true']:not([data-status='match'])",
          fallbackSelector: "#launch-backend-preflight-summary",
          label: "Opened Diagnostics > Readiness > Backend Preflight and selected the first non-ready check.",
        },
      ));
    }

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
    const queueNonReadyStates = queueNonReady.map((row) => {
      const posture = typeof queueLaunchDecisionPostureStatus === "function"
        ? queueLaunchDecisionPostureStatus(row.posture)
        : row.posture;
      return launchCompactGateState(posture);
    });
    const queueBlocked = queueNonReadyStates.includes("blocked");
    const queueAtRisk = queueNonReadyStates.includes("warning");
    const queueNeedsEvidence = !queueRows.length || queueNonReadyStates.includes("unknown");
    const queueActiveWorkOnly = queueBlocked
      && !queueAtRisk
      && !queueNeedsEvidence
      && launchCompactGateQueueBlockedOnlyByActiveWork(queueNonReady, backendRows);
    const queueGateStatus = !queueRows.length
      ? "unknown"
      : (queueActiveWorkOnly ? "running" : (queueBlocked ? "blocked" : (queueAtRisk ? "warning" : (queueNeedsEvidence ? "unknown" : launchStartDecisionPostureFromStatus(queueStatus)))));
    const queueGateState = launchCompactGateState(queueGateStatus);
    const queueIssueCount = queueNonReady.length || 1;
    rows.push(launchCompactGateRow(
      "queue",
      "Queue",
      queueGateStatus,
      queueRows.length
        ? (queueGateState === "running" ? "Active" : (queueGateState === "blocked" ? "Blocked" : (queueGateState === "warning" ? `At Risk ${queueIssueCount}` : (queueGateState === "unknown" ? "Needs Evidence" : `Queue ${queueRows.length}`))))
        : "Not loaded",
      queueRows.length
        ? (queueGateState === "running"
          ? "Queue launch handoff is paused by active backend work; no queue-specific compact blocker is indicated."
          : (queueGateState === "blocked"
          ? `Queue has ${queueIssueCount} launch handoff item(s) that would block this launch scope.`
          : (queueGateState === "warning"
            ? `Queue has ${queueIssueCount} launch handoff item(s) likely to affect this start.`
            : (queueGateState === "unknown"
              ? "Queue handoff evidence is incomplete; refresh before trusting visible launch scope."
              : "Queue handoff is ready-looking; backend owns actual launch scope."))))
        : "Queue evidence is not loaded in this view. Use Refresh to update backend evidence before trusting visible launch scope.",
      typeof queueLaunchDecisionSummaryLines === "function" ? queueLaunchDecisionSummaryLines(queuePayload, queueRows, history) : [],
      {
        page: "queue",
        rowSelector: "#queue-launch-decision-rows tr[data-selectable-row='true']:not([data-status='match'])",
        fallbackSelector: "#queue-launch-decision-summary",
        label: "Opened Queue > Queue-to-Launch handoff and selected the first non-ready row.",
      },
    ));

    const settingsIntentRows = launchSettingsIntentRows(request, context);
    const compactSettingsRows = launchCompactGateSettingsRows(settingsIntentRows);
    const policyRows = launchPolicyBoundaryRows();
    const settingsPosture = launchCompactGateSettingsPosture(compactSettingsRows, policyRows);
    const settingsNonReady = launchCompactGateNonReadyCount(compactSettingsRows) + launchCompactGateNonReadyCount(policyRows);
    const settingsLoaded = Boolean(launchSettingsWorkspace()?.schema_version);
    const settingsGateState = settingsLoaded ? launchCompactGateState(settingsPosture) : "unknown";
    rows.push(launchCompactGateRow(
      "settings",
      "Settings",
      settingsGateState,
      settingsLoaded
        ? (settingsGateState === "blocked" ? "Blocked" : (settingsGateState === "unknown" ? "Needs Evidence" : (settingsGateState === "warning" ? `At Risk ${settingsNonReady || 1}` : "Saved")))
        : "Not loaded",
      settingsLoaded
        ? (settingsGateState === "blocked"
          ? "Saved settings or policy posture would block this start path."
          : (settingsGateState === "warning"
            ? "Saved settings or policy posture has review evidence likely to affect unattended starts."
            : (settingsGateState === "unknown"
              ? "Saved settings or policy posture evidence is incomplete; refresh before trusting settings posture."
              : "Saved settings and policy posture are ready-looking; backend start remains authoritative.")))
        : "Saved settings evidence is not loaded in this view. Use Refresh before trusting settings posture.",
      [
        ...launchSettingsIntentSummaryLines(compactSettingsRows),
        ...launchPolicyBoundarySummaryLines(policyRows),
      ],
      {
        page: "diagnostics",
        tab: "readiness",
        rowSelector: "#launch-settings-risk-rows tr[data-selectable-row='true'][data-status='blocked'], #launch-settings-risk-rows tr[data-selectable-row='true'][data-status='warning'], #launch-settings-intent-rows tr[data-selectable-row='true']:not([data-status='match']), #launch-policy-boundary-rows tr[data-selectable-row='true']:not([data-status='match'])",
        fallbackSelector: "#launch-settings-risk-summary",
        label: "Opened Diagnostics > Readiness > Settings Check and selected the first non-ready settings row.",
      },
    ));

    const timingStatus = typeof launchTimingStatus === "function" ? launchTimingStatus(context, request) : "Unknown";
    const timingPosture = String(timingStatus || "").toLowerCase().includes("active work")
      ? "running"
      : launchStartDecisionPostureFromStatus(timingStatus);
    const timingState = launchCompactGateState(timingPosture);
    rows.push(launchCompactGateRow(
      "schedule",
      "Schedule",
      timingPosture,
      request?.schedule_override
        ? "Override"
        : (timingState === "running" ? "Active" : (timingState === "ready" ? "Window" : (timingState === "blocked" ? "Blocked" : (timingState === "unknown" ? "Not loaded" : "At Risk")))),
      `Schedule status is ${timingStatus}; override=${request?.schedule_override || "none"}.`,
      typeof launchTimingTrustLines === "function" ? launchTimingTrustLines(context, request) : [],
      {
        page: "diagnostics",
        tab: "readiness",
        selector: "#launch-timing",
        fallbackSelector: "#pipeline-start-schedule-override",
        label: "Opened Diagnostics > Readiness > Schedule Alignment. Use the schedule evidence, wait for the window, or choose an intentional override.",
      },
    ));

    const closeReadiness = context.closeReadiness || null;
    const snapshot = context.snapshot || null;
    const snapshotState = String(snapshot?.pipeline_state || snapshot?.state || snapshot?.status || "").toLowerCase();
    const active = Boolean(closeReadiness?.active_work || closeReadiness?.pipeline_active || closeReadiness?.safe_to_close === false)
      || ["active", "running", "processing", "paused", "stopping"].some((term) => snapshotState.includes(term));
    rows.push(launchCompactGateRow(
      "active",
      "Active",
      active ? "running" : (closeReadiness || snapshot ? "ready" : "unknown"),
      active ? "Active" : (closeReadiness || snapshot ? "Idle" : "Not loaded"),
      active
        ? "Active backend work is in progress; Start controls remain disabled to prevent duplicate pipeline starts."
        : (closeReadiness || snapshot ? "No active backend work is visible in the latest loaded state." : "Backend state evidence is not loaded in this view. Use Refresh before starting work."),
      typeof launchReadinessLines === "function"
        ? launchReadinessLines({ snapshot, closeReadiness, schedule: context.schedule || {}, settings: launchSettingsWorkspace(), backendPreflight: pipelineBackendPreflight })
        : [],
      {
        page: "launch",
        tab: "pipeline",
        selector: active ? "#launch-live-run-strip" : "#pipeline-controller-stage-summary",
        fallbackSelector: "#launch-readiness",
        label: active ? "Opened Launch > Pipeline Processor > Live Run for the active backend work." : "Opened Launch > Pipeline Processor state evidence.",
      },
    ));

    const commandRows = typeof launchCommandReviewRows === "function" ? launchCommandReviewRows(history) : [];
    const commandStatus = typeof launchCommandReviewStatus === "function" ? launchCommandReviewStatus(history) : "No command history";
    const latestLaunch = commandRows[0] || history.find((entry) => isLaunchCommand(entry)) || null;
    const commandPosture = launchStartDecisionAdvisoryPosture(launchStartDecisionPostureFromStatus(commandStatus));
    rows.push(launchCompactGateRow(
      "last",
      "Last",
      latestLaunch ? commandPosture : "unknown",
      latestLaunch ? (commandPosture === "ready" ? "Last OK" : "Last issue") : "No history",
      latestLaunch
        ? "Recent launch history is visible; compare it with the current backend preflight before retrying."
        : "No recent launch result is loaded; the next backend response will create command evidence.",
      typeof launchCommandReviewSummaryLines === "function" ? launchCommandReviewSummaryLines(history) : [],
      {
        page: "launch",
        tab: "history",
        rowSelector: "#launch-command-review-rows tr[data-selectable-row='true']:not([data-status='match'])",
        fallbackSelector: latestLaunch ? "#launch-history" : "#launch-latest-command-evidence",
        label: latestLaunch ? "Opened Launch > History and selected the first command-review issue." : "Opened Launch command history; no prior launch command issue is available.",
        required: false,
      },
    ));

    if (backendFetchFailures) {
      const backend = rows.find((row) => row.key === "backend");
      if (backend && backend.status === "ready") {
        backend.status = "unknown";
        backend.value = launchCompactGateValue("unknown");
      }
      if (backend) {
        backend.note = `Fetch ${backendFetchFailures}`;
        backend.summary = `Backend preflight refresh reported ${backendFetchFailures} fetch failure(s); refresh before trusting the cached posture.`;
      }
    }
    return rows;
  }

  function launchCompactGateOverallStatus(rows = launchCompactGateRows()) {
    const source = launchCompactGateRequiredRows(rows);
    if (!source.length) return "Needs Evidence";
    if (source.some((row) => row.status === "blocked")) return "Will Fail";
    if (source.some((row) => row.status === "running")) return "Active";
    if (source.some((row) => row.status === "warning")) return "At Risk";
    if (source.some((row) => row.status === "unknown")) return "Needs Evidence";
    return "All Clear";
  }

  function selectedLaunchCompactGateRow(rows = []) {
    const source = Array.isArray(rows) ? rows : [];
    return source.find((row) => row.key === state.selectedLaunchCompactGateKey)
      || source.find((row) => row.status === "blocked")
      || source.find((row) => row.status === "running")
      || source.find((row) => row.status === "warning")
      || source.find((row) => row.required !== false && row.status === "unknown")
      || source[0]
      || null;
  }

  function selectLaunchCompactGate(row) {
    state.selectedLaunchCompactGateKey = row?.key || "";
    renderLaunchCompactGate();
  }

  function renderLaunchCompactGate(request = collectPipelineStartRequest(), payload = launchSettingsIntentPayload()) {
    const rows = launchCompactGateRows(request, payload);
    if (state.selectedLaunchCompactGateKey && !rows.some((row) => row.key === state.selectedLaunchCompactGateKey)) {
      state.selectedLaunchCompactGateKey = "";
    }
    const selected = selectedLaunchCompactGateRow(rows);
    const overall = launchCompactGateOverallStatus(rows);
    setText("pipeline-compact-gate-status", overall);
    const statusNode = byId("pipeline-compact-gate-status");
    if (statusNode) statusNode.dataset.state = launchCompactGateHeaderState(overall);
    rows.forEach((item) => {
      const button = byId(`pipeline-gate-${item.key}`);
      if (!button) return;
      const selectedState = item.key === selected?.key;
      button.dataset.status = item.status;
      button.classList.toggle("is-active", selectedState);
      button.setAttribute("aria-pressed", selectedState ? "true" : "false");
      button.setAttribute("aria-label", `${item.label} gate: ${item.value}. ${item.summary}`);
      button.title = item.summary;
      const label = button.querySelector(".pipeline-gate-label");
      const value = button.querySelector(".pipeline-gate-value");
      const note = button.querySelector(".pipeline-gate-note");
      if (label) label.textContent = item.label;
      if (value) value.textContent = item.value;
      if (note) note.textContent = item.note;
      button.onclick = () => {
        selectLaunchCompactGate(item);
        launchCompactGateOpenTarget(item);
      };
    });
    const detail = selected
      ? `${selected.label}: ${selected.value}. ${selected.summary} ${launchCompactGateActionLabel(selected)} Backend start remains authoritative.`
      : "Compact gate not evaluated. Refresh Backend Preflight before submitting normal start modes.";
    setText("pipeline-compact-gate-detail", detail);
    return rows;
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
      launchCompactGateRows,
      launchCompactGateOverallStatus,
      renderLaunchCompactGate,
    };
  }

  window.__launchViewScopeModule = {
    createLaunchScopeModule,
  };
})();
