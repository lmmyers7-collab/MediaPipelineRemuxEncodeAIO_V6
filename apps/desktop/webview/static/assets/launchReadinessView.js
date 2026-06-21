(function () {
  const domHelpers = window.mediaPipelineDom || {};
  const scheduleView = window.mediaPipelineScheduleView || {};
  const scheduleCurrentLaunchSelection = typeof scheduleView.scheduleCurrentLaunchSelection === "function" ? scheduleView.scheduleCurrentLaunchSelection : null;
  const scheduleDisplayValue = typeof scheduleView.scheduleDisplayValue === "function" ? scheduleView.scheduleDisplayValue : null;
  const scheduleOverrideLabel = typeof scheduleView.scheduleOverrideLabel === "function" ? scheduleView.scheduleOverrideLabel : null;
  const schedulePipelineModeLabel = typeof scheduleView.schedulePipelineModeLabel === "function" ? scheduleView.schedulePipelineModeLabel : null;
  const scheduleTimingTrustLines = typeof scheduleView.scheduleTimingTrustLines === "function" ? scheduleView.scheduleTimingTrustLines : null;
  const scheduleTimingTrustStatus = typeof scheduleView.scheduleTimingTrustStatus === "function" ? scheduleView.scheduleTimingTrustStatus : null;
  const scheduleWatcherSummary = typeof scheduleView.scheduleWatcherSummary === "function" ? scheduleView.scheduleWatcherSummary : null;
  const byIdLocal = typeof byId === "function"
    ? byId
    : (typeof domHelpers.byId === "function" ? domHelpers.byId : (id) => document.getElementById(id));
  let lastLaunchReadinessPayload = {};

  function launchReadinessSettingsStatus(settings = null) {
    if (!settings || typeof settings !== "object" || !settings.schema_version) return "Not loaded";
    try {
      if (typeof settingsOperatorTrustStatus === "function") return settingsOperatorTrustStatus(settings);
    } catch {
      // Fall through to the local summary so Launch remains usable if Settings fails to initialize.
    }
    const errors = Array.isArray(settings.errors) ? settings.errors : [];
    if (errors.length) return "Invalid";
    const risk = settings.risk_summary || {};
    const highest = String(risk.highest_severity || "none").toLowerCase();
    if (highest === "critical") return "Critical risk";
    if (highest === "high") return "High risk";
    if (Number(risk.total_count || 0) > 0) return "Review";
    const warnings = Array.isArray(settings.warnings) ? settings.warnings : [];
    if (warnings.length) return "Review";
    return "Ready";
  }

  function launchReadinessSettingsNeedsReview(status) {
    const normalized = String(status || "").toLowerCase();
    return normalized.includes("invalid")
      || normalized.includes("critical")
      || normalized.includes("high")
      || normalized.includes("review")
      || normalized.includes("not loaded");
  }

  function launchReadinessSettingsBlocks(status) {
    const normalized = String(status || "").toLowerCase();
    return normalized.includes("invalid") || normalized.includes("critical");
  }

  function launchReadinessScheduleWatcherSummary(schedule = null) {
    if (typeof scheduleWatcherSummary === "function") return scheduleWatcherSummary(schedule || {});
    const watcher = schedule?.continuous_watcher && typeof schedule.continuous_watcher === "object"
      ? schedule.continuous_watcher
      : {};
    const status = String(watcher.status || "unknown");
    const deadlineValue = watcher.deadline || "";
    const deadline = deadlineValue
      ? ` until ${typeof scheduleDisplayValue === "function" ? scheduleDisplayValue(deadlineValue) : deadlineValue}`
      : "";
    const pid = Number(watcher.pid || 0) > 0 ? ` for PID ${watcher.pid}` : "";
    return `${status}${pid}${deadline}`;
  }

  function launchReadinessBackendReadiness(payload = {}) {
    const source = payload && typeof payload === "object" ? payload : {};
    const candidates = [
      source.backendReadiness,
      source.launchReadiness,
      source.operator_readiness,
      source.backend_readiness,
      source.backendPreflight?.operator_readiness,
      source.backendPreflightPayload?.operator_readiness,
    ];
    if (Array.isArray(source.backendPreflight)) {
      const pipeline = source.backendPreflight.find((item) => String(item?.target || "").toLowerCase() === "pipeline");
      candidates.push(pipeline?.operator_readiness);
    }
    if (Array.isArray(source.backendPreflightPayloads)) {
      const pipeline = source.backendPreflightPayloads.find((item) => String(item?.target || "").toLowerCase() === "pipeline");
      candidates.push(pipeline?.operator_readiness);
    }
    try {
      const pipelinePayload = window.mediaPipelineLaunchView?.launchBackendPreflightPayloadForTarget?.("pipeline");
      candidates.push(pipelinePayload?.operator_readiness);
    } catch (_) {}
    return candidates.find((item) => item && typeof item === "object" && item.evidence_authority === "backend") || null;
  }

  function launchReadinessBackendStatus(readiness = null) {
    const status = String(readiness?.display_status || readiness?.operator_status || "").trim();
    if (!status) return "";
    if (status.toLowerCase() === "ready") return "Ready";
    if (status.toLowerCase() === "blocked") return "Blocked";
    return status;
  }

  function launchReadinessBackendLines(readiness = null) {
    const source = readiness && typeof readiness === "object" ? readiness : {};
    const lines = Array.isArray(source.summary_lines)
      ? source.summary_lines.map((item) => String(item || "")).filter(Boolean)
      : [];
    if (lines.length) return lines;
    return [
      "Launch readiness (backend-authored):",
      `Status: ${launchReadinessBackendStatus(source) || "unknown"}`,
      `Target: ${source.target || "pipeline"}; start route: ${source.start_route || "(not reported)"}`,
      `Can request start: ${source.can_request_start ? "yes" : "no"}`,
      source.final_authority || "Backend start routes remain authoritative.",
      "Backend launch locking and gating remain the source of truth.",
    ];
  }

  function launchReadinessActionLabel(action = {}) {
    const explicit = String(action.label || action.title || "").trim();
    if (explicit) return explicit;
    const kind = String(action.kind || "").toLowerCase();
    if (kind === "archive_state_journals") return "Archive Event Journal";
    if (kind === "drain_pending_pushes") return "Drain Parked Outputs";
    if (kind === "pending_publish_recovery_plan") return "Open Pending Publish";
    return "Review Action";
  }

  function launchReadinessRecoveryActions(payload = lastLaunchReadinessPayload) {
    const readiness = launchReadinessBackendReadiness(payload);
    if (!readiness) return [];
    const actions = [];
    const pushAction = (action) => {
      if (!action || typeof action !== "object") return;
      actions.push(action);
    };
    pushAction(readiness.recovery_action);
    (Array.isArray(readiness.non_ready_checks) ? readiness.non_ready_checks : []).forEach((check) => {
      pushAction(check?.recovery_action);
      (Array.isArray(check?.recovery_actions) ? check.recovery_actions : []).forEach(pushAction);
    });
    const seen = new Set();
    return actions.filter((action) => {
      const key = [
        String(action.kind || ""),
        String(action.route || ""),
        JSON.stringify(action.request || {}),
      ].join("\u0000");
      if (seen.has(key)) return false;
      seen.add(key);
      return true;
    });
  }

  function renderLaunchReadinessRecoveryActions(payload = lastLaunchReadinessPayload) {
    const container = byIdLocal("launch-readiness-actions");
    if (!container) return;
    const status = byIdLocal("launch-readiness-action-status");
    const actions = launchReadinessRecoveryActions(payload);
    container.replaceChildren();
    container.hidden = actions.length === 0;
    if (status && !actions.length) status.textContent = "No backend recovery action is advertised.";
    actions.forEach((action) => {
      const button = document.createElement("button");
      button.type = "button";
      button.className = "secondary-button";
      button.dataset.launchRecoveryAction = String(action.kind || "");
      button.dataset.launchRecoveryRoute = String(action.route || "");
      try {
        button.dataset.launchRecoveryRequest = JSON.stringify(action.request || {});
      } catch (_) {
        button.dataset.launchRecoveryRequest = "{}";
      }
      if (action.requires_confirmation !== undefined) {
        button.dataset.requiresConfirmation = action.requires_confirmation ? "true" : "false";
      }
      button.textContent = launchReadinessActionLabel(action);
      const description = String(action.description || action.safe_next_action || action.evidence_path || "").trim();
      if (description) button.title = description;
      container.appendChild(button);
    });
    if (status && actions.length) {
      status.textContent = "Backend recovery actions are shown only when the backend preflight payload advertises them.";
    }
  }

  function launchReadinessStatus(payload = {}) {
    const backendReadiness = launchReadinessBackendReadiness(payload);
    if (backendReadiness) return launchReadinessBackendStatus(backendReadiness) || "Backend preflight";
    const { snapshot = null, closeReadiness = null, schedule = null, failures = [], settings = null } = payload || {};
    const items = Array.isArray(failures) ? failures : [];
    if (items.some((item) => item.required)) return "Backend issue";
    if (!snapshot) return "No snapshot";
    if (closeReadiness?.safe_to_close === false || closeReadiness?.active_work === true) return "Active work";
    const state = String(snapshot.pipeline_state || closeReadiness?.state || "").toLowerCase();
    if (["processing", "running", "active", "publishing", "audit"].includes(state)) return "Active work";
    const settingsStatus = launchReadinessSettingsStatus(settings);
    if (launchReadinessSettingsBlocks(settingsStatus)) return "Settings issue";
    const evaluation = schedule?.evaluation || {};
    if (schedule?.enabled && evaluation.allowed_now === false) return "Outside schedule";
    if (launchReadinessSettingsNeedsReview(settingsStatus)) return "Settings review";
    if ((schedule?.warnings || []).length || items.length) return "Review";
    if (closeReadiness?.safe_to_close === true || ["idle", "completed", "failed"].includes(state)) return "Ready";
    return "Checking";
  }

  function launchReadinessStatusState(status) {
    const normalized = String(status || "").toLowerCase();
    if (normalized.includes("blocked") || normalized.includes("issue") || normalized.includes("outside schedule") || normalized.includes("critical") || normalized.includes("invalid")) return "blocked";
    if (normalized.includes("active") || normalized.includes("running")) return "running";
    if (normalized.includes("ready") || normalized.includes("not watched") || normalized.includes("schedule off")) return "ready";
    if (normalized.includes("review") || normalized.includes("stale") || normalized.includes("bypassed") || normalized.includes("override")) return "warning";
    return "unknown";
  }

  function launchReadinessLines(payload = {}) {
    const backendReadiness = launchReadinessBackendReadiness(payload);
    if (backendReadiness) return launchReadinessBackendLines(backendReadiness);
    const { snapshot = null, closeReadiness = null, schedule = null, failures = [], settings = null } = payload || {};
    const items = Array.isArray(failures) ? failures : [];
    const state = snapshot?.pipeline_state || closeReadiness?.state || "unknown";
    const evaluation = schedule?.evaluation || {};
    const scheduleEnabled = Boolean(schedule?.enabled);
    const scheduleAllowed = evaluation.allowed_now !== false;
    const settingsStatus = launchReadinessSettingsStatus(settings);
    const lines = [
      "Launch readiness (frontend advisory fallback):",
      "Evidence authority: frontend advisory only until backend preflight payload is loaded.",
      `Backend snapshot: ${snapshot ? "ok" : "unavailable"}`,
      `Pipeline state: ${state}`,
      `Close readiness: ${closeReadiness ? (closeReadiness.safe_to_close ? "safe" : "active/blocked") : "unknown"}`,
      `Active work: ${closeReadiness?.active_work ? "yes" : closeReadiness?.safe_to_close === false ? "yes" : "no"}`,
      `Saved settings: ${settingsStatus}`,
    ];
    if (closeReadiness?.reason) lines.push(`Close reason: ${closeReadiness.reason}`);
    if (snapshot?.activity) lines.push(`Activity: ${snapshot.activity}`);
    lines.push(
      `Schedule: ${scheduleEnabled ? (scheduleAllowed ? "inside allowed window" : "outside allowed window") : "off or unavailable"}`,
      `Next allowed start: ${typeof scheduleDisplayValue === "function" ? scheduleDisplayValue(evaluation.next_allowed_start) : (evaluation.next_allowed_start || "None")}`,
      `Relevant window end: ${typeof scheduleDisplayValue === "function" ? scheduleDisplayValue(evaluation.current_window_end || evaluation.next_allowed_end) : (evaluation.current_window_end || evaluation.next_allowed_end || "None")}`,
      `Backend continuous watcher: ${launchReadinessScheduleWatcherSummary(schedule)}`
    );
    const warnings = Array.isArray(schedule?.warnings) ? schedule.warnings : [];
    if (warnings.length) {
      lines.push("", "Schedule warning(s):");
      warnings.slice(0, 5).forEach((warning) => lines.push(`- ${warning}`));
    }
    if (items.length) {
      lines.push("", "Refresh issue(s):");
      items.slice(0, 6).forEach((item) => lines.push(`- ${item.name}: ${item.message}`));
    }
    lines.push("", "Launch guidance:");
    if (closeReadiness?.safe_to_close === false || closeReadiness?.active_work === true) {
      lines.push("- Active work is reported. Wait for completion or use backend-owned controls before starting more work.");
    } else {
      lines.push("- No active work block is reported by close-readiness.");
    }
    if (launchReadinessSettingsBlocks(settingsStatus)) {
      lines.push("- Saved settings are invalid or critical-risk. Use Settings > Validate / Reload before starting media work.");
    } else if (String(settingsStatus).toLowerCase() === "not loaded") {
      lines.push("- Saved settings have not loaded; refresh before launch if the config was edited.");
    } else if (launchReadinessSettingsNeedsReview(settingsStatus)) {
      lines.push("- Saved settings need review. Avoid long unattended runs until risk items are understood.");
    } else {
      lines.push("- Saved settings trust panel reports Ready; backend validation still owns acceptance/rejection.");
    }
    if (scheduleEnabled && !scheduleAllowed) {
      lines.push("- Run Once and Continuous are schedule-blocked unless a deliberate override is selected.");
      lines.push("- Validate and Publish Parked are not schedule-watched modes.");
    } else if (scheduleEnabled) {
      lines.push("- Run Once can launch in the current schedule window.");
      lines.push("- Continuous from WebView relies on backend start to arm the schedule-stop watcher when the loaded schedule reports a stop boundary.");
      lines.push("- Refresh Backend Preflight and inspect the Continuous schedule-stop watcher row before any continuous run.");
    } else {
      lines.push("- Schedule enforcement is off or unavailable; backend validation still owns acceptance/rejection.");
    }
    lines.push("- Backend launch locking and gating remain the source of truth.");
    lines.push("- Refresh Backend Preflight to replace this advisory fallback with backend-authored launch readiness.");
    return lines;
  }

  function launchTimingCurrentRequest() {
    if (typeof scheduleCurrentLaunchSelection === "function") return scheduleCurrentLaunchSelection();
    return {
      mode: byIdLocal("pipeline-start-mode")?.value || "validate",
      schedule_override: byIdLocal("pipeline-start-schedule-override")?.value || "",
    };
  }

  function launchTimingStatus(payload = lastLaunchReadinessPayload, request = launchTimingCurrentRequest()) {
    const closeReadiness = payload?.closeReadiness || null;
    if (closeReadiness?.safe_to_close === false || closeReadiness?.active_work === true) return "Active work";
    const settingsStatus = launchReadinessSettingsStatus(payload?.settings || null);
    if (launchReadinessSettingsBlocks(settingsStatus)) return "Settings issue";
    if (typeof scheduleTimingTrustStatus === "function") return scheduleTimingTrustStatus(payload?.schedule || {}, request);
    const schedule = payload?.schedule || {};
    const mode = String(request?.mode || "validate");
    const override = String(request?.schedule_override || "");
    if (mode === "validate" || mode === "drain_pending_pushes") return "Not watched";
    if (!schedule.enabled) return "Schedule off";
    if (override === "ignore") return "Bypassed";
    if (override === "run_once") return "One-shot override";
    return schedule.evaluation?.allowed_now === false ? "Blocked" : "Ready";
  }

  function launchTimingTrustLines(payload = lastLaunchReadinessPayload, request = launchTimingCurrentRequest()) {
    const schedule = payload?.schedule || {};
    const closeReadiness = payload?.closeReadiness || null;
    const snapshot = payload?.snapshot || null;
    const settingsStatus = launchReadinessSettingsStatus(payload?.settings || null);
    const mode = String(request?.mode || "validate");
    const override = String(request?.schedule_override || "");
    const lines = [
      "Launch timing trust:",
      `Selected mode: ${typeof schedulePipelineModeLabel === "function" ? schedulePipelineModeLabel(mode) : mode}`,
      `Selected override: ${typeof scheduleOverrideLabel === "function" ? scheduleOverrideLabel(override) : (override || "None")}`,
      `Pipeline state: ${snapshot?.pipeline_state || closeReadiness?.state || "unknown"}`,
      `Close readiness: ${closeReadiness ? (closeReadiness.safe_to_close ? "safe" : "active/blocked") : "unknown"}`,
      `Saved settings: ${settingsStatus}`,
    ];
    if (closeReadiness?.reason) lines.push(`Close reason: ${closeReadiness.reason}`);
    lines.push("");
    if (closeReadiness?.safe_to_close === false || closeReadiness?.active_work === true) {
      lines.push("Timing decision: active work is already reported. Do not start another media run unless intentionally controlling the current run.");
    } else {
      lines.push("Timing decision: no active-work block is reported; schedule/mode checks are the next gate.");
    }
    if (launchReadinessSettingsBlocks(settingsStatus)) {
      lines.push("Settings decision: launch should remain blocked until Settings validation/risk is clean.");
    } else if (launchReadinessSettingsNeedsReview(settingsStatus)) {
      lines.push("Settings decision: timing may be acceptable, but unattended starts should wait until settings risks are understood.");
    } else {
      lines.push("Settings decision: saved settings do not add a timing block; backend validation still has final authority.");
    }
    lines.push("");
    if (typeof scheduleTimingTrustLines === "function") {
      lines.push(...scheduleTimingTrustLines(schedule, request));
    } else {
      const evaluation = schedule.evaluation || {};
      lines.push(
        `Schedule enforcement: ${schedule.enabled ? "on" : "off"}`,
        `Allowed now: ${evaluation.allowed_now === false ? "no" : "yes"}`,
        "Backend launch gating remains the source of truth."
      );
    }
    lines.push("", "Mutation guardrail: this Launch timing panel is read-only; it does not bypass backend launch locks, schedule gates, or settings validation.");
    return lines;
  }

  function renderLaunchTimingTrust(payload = lastLaunchReadinessPayload, request = launchTimingCurrentRequest()) {
    const status = launchTimingStatus(payload || {}, request);
    setText("launch-timing-status", status);
    const statusNode = byIdLocal("launch-timing-status");
    if (statusNode) statusNode.dataset.state = launchReadinessStatusState(status);
    setText("launch-timing", launchTimingTrustLines(payload || {}, request).join("\n"));
  }

  function renderLaunchReadiness(payload = {}) {
    lastLaunchReadinessPayload = payload || {};
    const status = launchReadinessStatus(payload);
    setText("launch-readiness-status", status);
    const statusNode = byIdLocal("launch-readiness-status");
    if (statusNode) statusNode.dataset.state = launchReadinessStatusState(status);
    setText("launch-readiness", launchReadinessLines(payload).join("\n"));
    renderLaunchReadinessRecoveryActions(lastLaunchReadinessPayload);
    renderLaunchTimingTrust(lastLaunchReadinessPayload);
    if (typeof renderLaunchSettingsIntentChecklist === "function") {
      renderLaunchSettingsIntentChecklist(undefined, lastLaunchReadinessPayload);
    }
  }

  function getLastLaunchReadinessPayload() {
    return lastLaunchReadinessPayload || {};
  }

  /**
   * Public namespace for the launch readiness module.
   * Prefer this namespace from new code; flat window.* exports are transitional compatibility aliases when present.
   */
  window.mediaPipelineLaunchReadinessView = {
    launchReadinessSettingsStatus,
    launchReadinessSettingsNeedsReview,
    launchReadinessSettingsBlocks,
    launchReadinessScheduleWatcherSummary,
    launchReadinessBackendReadiness,
    launchReadinessBackendStatus,
    launchReadinessBackendLines,
    launchReadinessRecoveryActions,
    renderLaunchReadinessRecoveryActions,
    launchReadinessStatus,
    launchReadinessStatusState,
    launchReadinessLines,
    launchTimingCurrentRequest,
    launchTimingStatus,
    launchTimingTrustLines,
    renderLaunchTimingTrust,
    renderLaunchReadiness,
    getLastLaunchReadinessPayload,
  };
})();
