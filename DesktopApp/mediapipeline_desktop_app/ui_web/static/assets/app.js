const bootstrap = window.MEDIA_PIPELINE_BOOTSTRAP || {};

let lastSnapshot = null;
let lastCloseReadiness = null;
let lastSchedule = null;
let refreshInFlight = false;
let refreshQueued = false;
let lastRefreshStartedAt = null;
let lastRefreshCompletedAt = null;
let lastRefreshDurationMs = null;
let backendShutdownInFlight = false;
let lastStartupProgress = bootstrap.startupProgress || null;
let lastTauriBackendLifecycleEvent = null;

function renderBrandVersion(snapshot = {}) {
  setText("app-version", bootstrap.appVersion || snapshot.app_version || "V6");
}

function topbarPathLeaf(value) {
  const text = formatProgressValue(value || "").trim();
  if (!text) return "";
  return text.split(/[\\/]/).filter(Boolean).pop() || text;
}

function topbarCleanCurrentName(progress = {}) {
  return formatProgressValue(
    progress.CurrentFileDisplay
      || progress.CurrentDisplayName
      || progress.CleanDisplayName
      || progress.CleanedName
      || "",
  ).trim();
}

function topbarOriginalCurrentName(progress = {}) {
  const candidates = [
    progress.CurrentFilePath,
    progress.CurrentFile,
    progress.InputFile,
    progress.SourceFile,
    progress.SourcePath,
    progress.InputPath,
    progress.OutputPath,
  ];
  for (const candidate of candidates) {
    const leaf = topbarPathLeaf(candidate);
    if (leaf) return leaf;
  }
  return "";
}

function topbarStageContext(progress = {}) {
  const stage = formatProgressValue(progress.CurrentStage || progress.Status || "").trim();
  const percent = homeAtAGlancePercent(progress.CurrentStagePercent);
  const route = formatProgressValue(progress.CurrentRoute || progress.Route || "").trim();
  return [
    stage,
    percent,
    route ? `Route ${route}` : "",
  ].filter(Boolean).join(" · ");
}

function renderTopbarActivity(snapshot = {}) {
  const node = byId("activity");
  if (!node) return;
  const payload = snapshot && typeof snapshot === "object" ? snapshot : {};
  const progress = payload.progress && typeof payload.progress === "object" ? payload.progress : {};
  const activity = formatProgressValue(payload.activity || "No active work reported.").trim();
  const cleanName = topbarCleanCurrentName(progress);
  const originalName = topbarOriginalCurrentName(progress);
  const stageContext = topbarStageContext(progress);
  const primaryText = cleanName
    ? [cleanName, stageContext].filter(Boolean).join(" | ")
    : activity || "No active work reported.";
  const shouldShowOriginal = Boolean(originalName && (!cleanName || originalName !== cleanName));

  const primary = document.createElement("span");
  primary.className = "activity-primary";
  primary.textContent = primaryText;
  primary.title = primaryText;
  const original = document.createElement("span");
  original.className = "activity-original";
  original.textContent = shouldShowOriginal ? `Original: ${originalName}` : "";
  if (shouldShowOriginal) original.title = originalName;
  node.replaceChildren(primary, original);
  node.title = [primaryText, shouldShowOriginal ? `Original: ${originalName}` : ""].filter(Boolean).join("\n");
}

function renderSnapshot(snapshot) {
  lastSnapshot = snapshot || {};
  const state = snapshot.pipeline_state || "idle";
  renderBrandVersion(snapshot);
  renderTopbarActivity(snapshot);
  setText("pipeline-state", state);
  setText("status-summary", snapshot.status_summary || "No status summary.");
  const pill = byId("state-pill");
  if (pill) {
    pill.textContent = state;
    pill.dataset.state = state;
  }
  const counts = snapshot.counts || {};
  // queue-count is driven by renderHomeQueueSnapshot which runs later in the
  // same poll cycle and uses the real queue snapshot data (runnable/total rows).
  // Do not set it here — the snapshot counts reflect only the active run's
  // batch position (CurrentQueueIndex/Total), which is 0/0 when idle and
  // would mask the actual queue size the operator needs to see.
  setText("processed-count", String(counts.processed || 0));
  setText("failed-count", String(counts.failed || 0));
  setText("home-failed-count", String(counts.failed || 0));
  if (typeof renderProgressBars === "function") {
    renderProgressBars(Array.isArray(snapshot.progress_bars) ? snapshot.progress_bars : [], snapshot);
  }
  renderProgressDetails(snapshot.progress || {});
  if (typeof renderProgressEvidence === "function") {
    renderProgressEvidence({ snapshot: lastSnapshot, closeReadiness: lastCloseReadiness, diagnostics: null });
  }
  window.mediaPipelineProgressView?.renderDiagnosticsProgress?.(lastSnapshot);
  const recentEvents = Array.isArray(snapshot.recent_events) ? snapshot.recent_events : [];
  renderPipelineEvents(recentEvents);
  renderSparkline(recentEvents);
  window.mediaPipelineReportsView?.renderReports?.(lastSnapshot, getLastSettings());
  if (typeof renderLaunchAuditProgress === "function") renderLaunchAuditProgress(lastSnapshot);
  renderControlReadiness(lastSnapshot, lastCloseReadiness);
  if (typeof renderLaunchReadiness === "function") {
    renderLaunchReadiness({ snapshot: lastSnapshot, closeReadiness: lastCloseReadiness, schedule: lastSchedule, settings: getLastSettings() });
  }
  renderBackendLifecycle(lastCloseReadiness, lastSnapshot);
}

function renderCloseReadiness(closeReadiness) {
  lastCloseReadiness = closeReadiness || null;
  const node = byId("close-readiness");
  if (!closeReadiness) {
    if (node) {
      node.textContent = "Close: unknown";
      node.dataset.state = "unknown";
      node.title = "Close readiness has not loaded yet.";
    }
    setTextState("diagnostics-close-status", "Unknown", "empty");
    setText("diagnostics-close-readiness", "Close readiness has not loaded yet.");
    renderControlReadiness(lastSnapshot, lastCloseReadiness);
    if (typeof renderLaunchReadiness === "function") {
      renderLaunchReadiness({ snapshot: lastSnapshot, closeReadiness: lastCloseReadiness, schedule: lastSchedule, settings: getLastSettings() });
    }
    renderBackendLifecycle(lastCloseReadiness, lastSnapshot);
    return;
  }
  const safe = Boolean(closeReadiness.safe_to_close);
  const state = closeReadiness.state || "unknown";
  if (node) {
    node.textContent = safe ? "Close: safe" : "Close: active work";
    node.dataset.state = safe ? "safe" : "blocked";
    node.title = closeReadiness.reason || `Current pipeline state: ${state}`;
  }
  setTextState("diagnostics-close-status", safe ? "Safe" : "Blocked", safe ? "ok" : "blocked");
  setText("diagnostics-close-readiness", formatCloseReadiness(closeReadiness));
  renderControlReadiness(lastSnapshot, lastCloseReadiness);
  if (typeof renderLaunchReadiness === "function") {
    renderLaunchReadiness({ snapshot: lastSnapshot, closeReadiness: lastCloseReadiness, schedule: lastSchedule, settings: getLastSettings() });
  }
  renderBackendLifecycle(lastCloseReadiness, lastSnapshot);
}

function formatCloseReadiness(closeReadiness) {
  if (!closeReadiness) return "Close readiness has not loaded yet.";
  const warnings = Array.isArray(closeReadiness.warnings) ? closeReadiness.warnings : [];
  const watcher = closeReadinessWatcherData(closeReadiness);
  const lines = [
    `Safe to close: ${closeReadiness.safe_to_close ? "yes" : "no"}`,
    `State: ${closeReadiness.state || "unknown"}`,
    `Active work: ${closeReadiness.active_work ? "yes" : "no"}`,
    `Reason: ${closeReadiness.reason || "No reason reported."}`,
    `Continuous watcher: ${closeReadinessWatcherSummary(closeReadiness)}`,
  ];
  if (Object.keys(watcher).length) {
    lines.push(
      `Watcher generation: ${Number(watcher.generation || 0) > 0 ? watcher.generation : "none"}`,
      `Watcher stop requested: ${watcher.stop_requested ? "yes" : "no"}`,
      `Watcher message: ${watcher.message || "(not reported)"}`,
      `Watcher error: ${watcher.error || "none"}`
    );
  }
  if (warnings.length) {
    lines.push("", "Warnings:");
    warnings.forEach((warning) => lines.push(`- ${warning}`));
  }
  return lines.join("\n");
}

function closeReadinessWatcherData(closeReadiness = lastCloseReadiness) {
  return closeReadiness?.continuous_watcher && typeof closeReadiness.continuous_watcher === "object"
    ? closeReadiness.continuous_watcher
    : {};
}

function closeReadinessWatcherSummary(closeReadiness = lastCloseReadiness) {
  const watcher = closeReadinessWatcherData(closeReadiness);
  const status = String(watcher.status || "unknown");
  const pid = Number(watcher.pid || 0) > 0 ? ` for PID ${watcher.pid}` : "";
  const deadline = watcher.deadline ? ` until ${typeof scheduleDisplayValue === "function" ? scheduleDisplayValue(watcher.deadline) : watcher.deadline}` : "";
  return `${status}${pid}${deadline}`;
}

function closeReadinessWatcherIsArmed(closeReadiness = lastCloseReadiness) {
  return String(closeReadinessWatcherData(closeReadiness).status || "").toLowerCase() === "armed";
}

function backendLifecycleState(closeReadiness = lastCloseReadiness) {
  if (!closeReadiness) {
    return {
      label: "Waiting",
      state: "unknown",
      canShutdown: false,
      reason: "Close-readiness has not loaded yet.",
    };
  }
  if (closeReadiness.safe_to_close === true) {
    return {
      label: "Safe to request",
      state: "ready",
      canShutdown: true,
      reason: closeReadiness.reason || "Close-readiness reports that no active work is blocking backend shutdown.",
    };
  }
  if (closeReadinessWatcherIsArmed(closeReadiness)) {
    return {
      label: "Watcher armed",
      state: "blocked",
      canShutdown: false,
      reason: closeReadiness.reason || "Backend schedule-stop watcher is armed; keep the local backend running or use backend-owned stop controls first.",
    };
  }
  return {
    label: "Blocked",
    state: "blocked",
    canShutdown: false,
    reason: closeReadiness.reason || "Active work, stale runtime state, or unverifiable close-readiness is blocking shutdown.",
  };
}

function startupProgressLines(progress = lastStartupProgress) {
  const payload = progress && typeof progress === "object" ? progress : null;
  if (!payload || !Array.isArray(payload.steps)) {
    return ["Startup progress: not reported by backend bootstrap."];
  }
  const steps = payload.steps;
  const status = payload.status || "unknown";
  const completed = Number(payload.completed_steps || 0);
  const total = Number(payload.total_steps || steps.length || 0);
  const percent = Number(payload.percent);
  const summary = `Startup progress: ${status}; ${completed} / ${total} step${total === 1 ? "" : "s"}${Number.isFinite(percent) ? `; ${percent.toFixed(1)}%` : ""}`;
  const recent = steps.slice(-5).map((step) => {
    const detail = step.detail ? ` - ${step.detail}` : "";
    return `- ${step.label || step.id || "startup step"}: ${step.status || "unknown"}${detail}`;
  });
  return [summary, ...recent];
}

function normalizeTauriBackendLifecycleEvent(payload) {
  const source = payload && typeof payload === "object" && payload.payload && typeof payload.payload === "object"
    ? payload.payload
    : payload && typeof payload === "object"
      ? payload
      : {};
  return {
    schema_version: source.schema_version || "unknown",
    status: String(source.status || "unknown"),
    detail: String(source.detail || "No lifecycle detail was reported."),
    consecutive_failures: Number(source.consecutive_failures || 0),
    emitted_at_unix_seconds: Number(source.emitted_at_unix_seconds || 0),
  };
}

function tauriBackendLifecycleStatusLabel(status) {
  if (status === "backend_exited") return "Backend exited";
  if (status === "backend_health_failed") return "Backend health failed";
  if (status === "monitor_error") return "Lifecycle monitor error";
  return "Backend lifecycle warning";
}

function tauriBackendLifecycleLines(event = lastTauriBackendLifecycleEvent) {
  if (!event) return [];
  return [
    "",
    "Tauri lifecycle monitor:",
    `Status: ${tauriBackendLifecycleStatusLabel(event.status)} (${event.status})`,
    `Detail: ${event.detail}`,
    `Consecutive health failures: ${event.consecutive_failures}`,
    `Schema: ${event.schema_version}`,
    "Recovery: refresh once, then inspect Diagnostics run logs, close-readiness, ActiveJobs, and backend stderr before launching, draining, saving settings, renaming, publishing, or closing the shell.",
  ];
}

function renderTauriBackendLifecycleAlert(event = lastTauriBackendLifecycleEvent) {
  const topbar = document.querySelector(".topbar");
  if (!topbar || !event) return;
  let node = document.querySelector(".tauri-lifecycle-alert");
  if (!node) {
    node = document.createElement("div");
    node.className = "tauri-lifecycle-alert";
    node.setAttribute("role", "alert");
    topbar.insertAdjacentElement("afterend", node);
  }
  node.dataset.state = event.status === "backend_health_failed" ? "warning" : "blocked";
  const title = document.createElement("strong");
  title.textContent = tauriBackendLifecycleStatusLabel(event.status);
  const detail = document.createElement("span");
  detail.textContent = event.detail;
  const hint = document.createElement("span");
  hint.textContent = "Open Diagnostics before starting, draining, saving, renaming, publishing, or closing.";
  node.replaceChildren(title, detail, hint);
}

function handleTauriBackendLifecycleEvent(event) {
  lastTauriBackendLifecycleEvent = normalizeTauriBackendLifecycleEvent(event?.detail);
  renderTauriBackendLifecycleAlert(lastTauriBackendLifecycleEvent);
  renderBackendLifecycle(lastCloseReadiness, lastSnapshot);
}

function renderBackendLifecycle(closeReadiness = lastCloseReadiness, snapshot = lastSnapshot) {
  const lifecycle = backendLifecycleState(closeReadiness);
  const status = byId("backend-lifecycle-status");
  if (status) {
    status.textContent = backendShutdownInFlight ? "Requesting" : lifecycle.label;
    status.dataset.state = backendShutdownInFlight ? "changed" : lifecycle.state;
  }
  const warnings = Array.isArray(closeReadiness?.warnings) ? closeReadiness.warnings : [];
  const watcher = closeReadinessWatcherData(closeReadiness);
  const lines = [
    "Backend lifecycle handoff:",
    `Request status: ${backendShutdownInFlight ? "shutdown command in progress" : lifecycle.label}`,
    `Close-readiness: ${closeReadiness ? (closeReadiness.safe_to_close ? "safe" : "blocked") : "not loaded"}`,
    `Pipeline state: ${snapshot?.pipeline_state || closeReadiness?.state || "unknown"}`,
    `Reason: ${lifecycle.reason}`,
    `Continuous watcher: ${closeReadinessWatcherSummary(closeReadiness)}`,
    `Watcher generation: ${Number(watcher.generation || 0) > 0 ? watcher.generation : "none"}`,
    `Watcher stop requested: ${watcher.stop_requested ? "yes" : "no"}`,
    `Warnings: ${warnings.length ? warnings.slice(0, 5).join(" | ") : "none"}`,
    "",
    ...startupProgressLines(),
    ...tauriBackendLifecycleLines(),
    "",
    "Guardrail: WebView exposes backend shutdown only when the loaded close-readiness payload reports safe.",
    "Backend authority: /api/backend/shutdown remains token-protected and performs the actual lifecycle request.",
    "Scope: this does not launch, pause, stop media, drain pending publish, rename files, save settings, delete files, or touch source/output/scratch media.",
  ];
  if (!lifecycle.canShutdown) {
    lines.push("Next step: inspect Close Readiness, ActiveJobs, Progress, Run Logs, and Last Stderr before closing or retrying lifecycle actions.");
    if (closeReadinessWatcherIsArmed(closeReadiness)) {
      lines.push("Watcher note: keep the backend alive until the schedule boundary requests Stop, or use backend-owned Stop After Current before shutting down.");
    }
  } else {
    lines.push("Next step: use this only when you are done with the WebView/local backend session. Closing the Tauri window also owns backend shutdown.");
  }
  setText("backend-lifecycle-summary", lines.join("\n"));
  const button = byId("backend-shutdown-button");
  if (button) {
    button.disabled = backendShutdownInFlight || !lifecycle.canShutdown;
    button.title = lifecycle.canShutdown
      ? "Request backend-owned graceful shutdown. This is enabled only because close-readiness reports safe."
      : "Disabled until close-readiness reports safe.";
  }
  if (typeof getCommandHistory === "function") renderBackendLifecycleHistory(getCommandHistory());
}

function backendLifecycleCommandEntries(history) {
  const entries = Array.isArray(history) ? history : [];
  return entries.filter((entry) => {
    const raw = entry?.raw && typeof entry.raw === "object" ? entry.raw : {};
    return String(entry?.command || raw.command || "").trim().toLowerCase() === "backend.shutdown";
  });
}

function backendLifecycleCommandLine(entry) {
  const raw = entry?.raw && typeof entry.raw === "object" ? entry.raw : {};
  const data = raw.data && typeof raw.data === "object" ? raw.data : {};
  const request = raw.request && typeof raw.request === "object"
    ? raw.request
    : raw.submitted_request && typeof raw.submitted_request === "object"
      ? raw.submitted_request
      : {};
  const result = entry?.result || (entry?.ok ? "ok" : entry?.severity || "unknown");
  const bits = [];
  if (data.safe_to_close !== undefined) bits.push(`safe_to_close=${data.safe_to_close ? "yes" : "no"}`);
  if (data.state) bits.push(`state=${data.state}`);
  if (data.reason) bits.push(`close_reason=${data.reason}`);
  if (data.continuous_watcher && typeof data.continuous_watcher === "object" && data.continuous_watcher.status) {
    const watcherBits = [`watcher=${data.continuous_watcher.status}`];
    if (data.continuous_watcher.pid) watcherBits.push(`pid=${data.continuous_watcher.pid}`);
    if (data.continuous_watcher.deadline) watcherBits.push(`deadline=${data.continuous_watcher.deadline}`);
    bits.push(watcherBits.join(" "));
  }
  if (request.reason) bits.push(`reason=${request.reason}`);
  const message = String(entry?.message || raw.message || "").trim();
  if (typeof commandHistoryCompactEvidenceLine === "function") {
    return commandHistoryCompactEvidenceLine(entry, {
      label: "backend.shutdown",
      detail: bits.length ? ` (${bits.join("; ")})` : "",
    });
  }
  return `${entry?.at || ""} backend.shutdown [${result}] ${message}${bits.length ? ` (${bits.join("; ")})` : ""}`.trim();
}

function renderBackendLifecycleHistory(history = []) {
  const entries = backendLifecycleCommandEntries(history).slice(0, 5);
  if (!entries.length) {
    setText("backend-lifecycle-history", "No backend shutdown command history loaded. Safe WebView shutdown requests will appear here after the backend responds.");
    return;
  }
  setText("backend-lifecycle-history", [
    `Last ${entries.length} backend lifecycle command${entries.length === 1 ? "" : "s"}:`,
    ...entries.map(backendLifecycleCommandLine),
    "Lifecycle command history is evidence only; close-readiness remains the authority before any new shutdown attempt.",
  ].join("\n"));
}

function backendShutdownStatusMessage(result) {
  const displayMessage = window.mediaPipelineCommandHistory?.commandResultDisplayMessage;
  if (typeof displayMessage === "function") {
    return displayMessage(result);
  }
  return result?.message || "Backend shutdown command finished.";
}

function appendBackendShutdownResult(result) {
  if (typeof appendCommandResult === "function") appendCommandResult(result);
  setText("backend-shutdown-status", backendShutdownStatusMessage(result));
  if (typeof getCommandHistory === "function") renderBackendLifecycleHistory(getCommandHistory());
}

function rejectBackendShutdown(message) {
  const result = {
    schema_version: "desktop_command_result.v1",
    command: "backend.shutdown",
    ok: false,
    severity: "warning",
    message,
    refresh_hint: "shutdown",
    warnings: [message],
  };
  appendBackendShutdownResult(result);
  renderBackendLifecycle(lastCloseReadiness, lastSnapshot);
}

async function requestBackendShutdown() {
  if (backendShutdownInFlight) {
    rejectBackendShutdown("Another backend shutdown command is already in progress.");
    return;
  }
  const lifecycle = backendLifecycleState(lastCloseReadiness);
  if (!lifecycle.canShutdown) {
    rejectBackendShutdown(`Backend shutdown is disabled in WebView until close-readiness reports safe. Current reason: ${lifecycle.reason}`);
    return;
  }
  const confirmed = typeof window.confirm === "function"
    ? window.confirm("Close the local WebView backend now? Use this only after work is idle and close-readiness reports safe.")
    : true;
  if (!confirmed) {
    setText("backend-shutdown-status", "Backend shutdown request cancelled.");
    return;
  }
  backendShutdownInFlight = true;
  renderBackendLifecycle(lastCloseReadiness, lastSnapshot);
  setText("backend-shutdown-status", "Requesting backend shutdown...");
  try {
    const result = await apiPost("/api/backend/shutdown", { reason: "webview-safe-close-request" }, { timeoutMs: 10000 });
    appendBackendShutdownResult(result);
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    appendBackendShutdownResult({
      schema_version: "desktop_command_result.v1",
      command: "backend.shutdown",
      ok: false,
      severity: "error",
      message: `Backend shutdown request failed: ${message}`,
      refresh_hint: "shutdown",
      errors: [message],
    });
  } finally {
    backendShutdownInFlight = false;
    renderBackendLifecycle(lastCloseReadiness, lastSnapshot);
  }
}

function closeReadinessRequiresWarning() {
  if (lastCloseReadiness && lastCloseReadiness.safe_to_close === false) return true;
  const state = String(lastSnapshot?.pipeline_state || "").toLowerCase();
  return Boolean(state && !["idle", "completed", "failed"].includes(state));
}

function closeReadinessWarningMessage() {
  return lastCloseReadiness?.reason || "Active MediaPipeline work may still be running. Close anyway?";
}

function refreshTimeLabel(value) {
  if (!value) return "never";
  try {
    return value.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });
  } catch {
    return String(value);
  }
}

function renderRefreshInProgress() {
  const node = byId("refresh-health");
  if (node) {
    node.textContent = "Refresh: updating";
    node.dataset.state = "updating";
    node.title = `Refresh started ${refreshTimeLabel(lastRefreshStartedAt)}. Previous completed refresh: ${refreshTimeLabel(lastRefreshCompletedAt)}.`;
  }
  const button = byId("refresh-button");
  if (button) {
    button.disabled = true;
    button.textContent = "Refreshing...";
    button.title = "Refreshing backend health, queue, completed, pending publish, diagnostics, settings, network, schedule, and contract state.";
  }
}

function renderRefreshHealth(failures) {
  const node = byId("refresh-health");
  const button = byId("refresh-button");
  if (button) {
    button.disabled = false;
    button.textContent = "Refresh";
  }
  if (!node) return;
  const items = Array.isArray(failures) ? failures : [];
  const timing = `Last refresh: ${refreshTimeLabel(lastRefreshCompletedAt)}${Number.isFinite(lastRefreshDurationMs) ? ` (${lastRefreshDurationMs} ms)` : ""}.`;
  if (!items.length) {
    node.textContent = "Refresh: ok";
    node.dataset.state = "ok";
    node.title = `All backend reads completed. ${timing}`;
    if (button) button.title = `Refresh all WebView read-only state. ${timing}`;
    return;
  }
  node.textContent = `Refresh: ${items.length} issue${items.length === 1 ? "" : "s"}`;
  node.dataset.state = items.some((item) => item.required) ? "failed" : "warning";
  node.title = [...items.map((item) => `${item.name}: ${item.message}`), timing].join("\n");
  if (button) button.title = `Refresh all WebView read-only state. Last result had ${items.length} issue${items.length === 1 ? "" : "s"}.`;
}

function refreshFailure(name, result, required = false) {
  if (result.status === "fulfilled") return null;
  const reason = result.reason;
  return {
    name,
    required,
    message: reason instanceof Error ? reason.message : String(reason),
  };
}

function homeReadinessNextStep({ snapshot, closeReadiness, failures }) {
  const items = Array.isArray(failures) ? failures : [];
  const requiredFailure = items.find((item) => item.required);
  if (requiredFailure) {
    return `Refresh the page or open Diagnostics; required backend read failed: ${requiredFailure.name}.`;
  }
  if (!snapshot) {
    return "Refresh the page or open Diagnostics; no backend snapshot is available.";
  }
  if (!closeReadiness) {
    return "Close-readiness has not loaded yet. Wait for the next refresh before closing the app.";
  }
  if (closeReadiness.safe_to_close === false) {
    return "Do not close unless intentionally interrupting active work. Check Home progress, ActiveJobs, and Run Logs.";
  }
  const optionalFailures = items.filter((item) => !item.required);
  if (optionalFailures.length) {
    return "Core snapshot is available, but one or more supporting panels failed. Use Diagnostics for the failed read(s).";
  }
  const state = String(snapshot.pipeline_state || "").toLowerCase();
  if (["processing", "running", "active", "publishing"].includes(state)) {
    return "Pipeline appears active. Monitor progress and avoid closing until close-readiness reports safe.";
  }
  return "Ready for normal operation.";
}

function renderHomeReadiness({ snapshot = null, closeReadiness = null, failures = [] } = {}) {
  const items = Array.isArray(failures) ? failures : [];
  const requiredFailures = items.filter((item) => item.required);
  const optionalFailures = items.filter((item) => !item.required);
  const safe = closeReadiness ? Boolean(closeReadiness.safe_to_close) : null;
  const state = snapshot?.pipeline_state || closeReadiness?.state || "unknown";
  const status = requiredFailures.length
    ? "Backend issue"
    : safe === false
      ? "Active work"
      : optionalFailures.length
        ? "Limited"
        : safe === true
          ? "Ready"
          : "Checking";
  setTextState("home-readiness-status", status, status === "Ready" ? "ok" : status === "Checking" ? "loading" : status === "Backend issue" ? "blocked" : "warning");
  const lines = [
    `Backend snapshot: ${snapshot ? "ok" : "unavailable"}`,
    `Refresh health: ${items.length ? `${items.length} issue${items.length === 1 ? "" : "s"}` : "ok"}`,
    `Close readiness: ${safe === null ? "unknown" : safe ? "safe" : "active work"}`,
    `Pipeline state: ${state}`,
  ];
  if (closeReadiness?.reason) lines.push(`Close reason: ${closeReadiness.reason}`);
  if (requiredFailures.length) {
    lines.push("", "Required read failure(s):");
    requiredFailures.forEach((item) => lines.push(`- ${item.name}: ${item.message}`));
  }
  if (optionalFailures.length) {
    lines.push("", "Supporting read issue(s):");
    optionalFailures.forEach((item) => lines.push(`- ${item.name}: ${item.message}`));
  }
  const warnings = Array.isArray(closeReadiness?.warnings) ? closeReadiness.warnings : [];
  if (warnings.length) {
    lines.push("", "Close-readiness warning(s):");
    warnings.slice(0, 5).forEach((warning) => lines.push(`- ${warning}`));
  }
  lines.push("", `Next step: ${homeReadinessNextStep({ snapshot, closeReadiness, failures: items })}`);
  setText("home-readiness-summary", lines.join("\n"));
}

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

function externalDependencyRows(context = {}) {
  const payload = context || {};
  const settings = payload.settings || {};
  const stateSummary = payload.stateSummary || payload.diagnosticsStateSummary || {};
  const maintenance = payload.maintenance
    || (typeof getLastMaintenance === "function" ? getLastMaintenance() : {});
  const rows = [];
  const bdpgs = settings?.tool_path_evidence?.bdpgs_ocr;
  if (bdpgs && typeof bdpgs === "object") {
    const status = dependencyStatusLabel(bdpgs.operator_status || (bdpgs.enabled ? "unknown" : "ready"));
    const attention = Boolean(bdpgs.enabled) && status !== "ready";
    rows.push({
      area: "Settings BDPGS OCR paths",
      status: attention ? status : "ready",
      evidence: `enabled=${bdpgs.enabled ? "yes" : "no"}; blocked=${bdpgs.blocked_count || 0}; review=${bdpgs.review_count || 0}`,
      nextStep: attention
        ? "Open Settings > Subtitles and fix saved OCR tool/tessdata path evidence or disable OCR intentionally before rerunning PGS subtitle conversion."
        : "Saved BDPGS OCR path evidence is not blocking in the loaded Settings payload.",
    });
  } else {
    rows.push({
      area: "Settings BDPGS OCR paths",
      status: "unknown",
      evidence: "settings tool-path evidence not loaded",
      nextStep: "Refresh Settings before diagnosing OCR path failures.",
    });
  }

  const settingsIssues = Array.isArray(stateSummary?.settings_tool_path_issues)
    ? stateSummary.settings_tool_path_issues
    : [];
  if (settingsIssues.length) {
    const blocked = settingsIssues.filter((item) => dependencyStatusLabel(item?.operator_status || item?.status) === "blocked").length;
    rows.push({
      area: "Diagnostics settings handoff",
      status: blocked ? "blocked" : "review",
      evidence: `settings dependency issue rows=${settingsIssues.length}; blocked=${blocked}`,
      nextStep: "Use Diagnostics State Artifact Summary read order, then return to Settings > Subtitles before rerun or manual-review decisions.",
    });
  }

  if (typeof settingsRawActionPlanRows === "function") {
    const rawActionRows = settingsRawActionPlanRows();
    if (rawActionRows.length) {
      const rawStatus = typeof settingsRawActionPlanStatus === "function"
        ? settingsRawActionPlanStatus(rawActionRows)
        : "Review";
      const blockedRows = rawActionRows.filter((row) => String(row.posture || "").toLowerCase().includes("blocked"));
      const highRows = rawActionRows.filter((row) => String(row.posture || "").toLowerCase().includes("high"));
      const reviewRows = rawActionRows.filter((row) => String(row.posture || "").toLowerCase().includes("review") || String(row.posture || "").toLowerCase().includes("exclusion"));
      const schemaRow = rawActionRows.find((row) => row.key === "schema-drift");
      const ocrRow = rawActionRows.find((row) => row.key === "bdpgs-ocr-paths");
      rows.push({
        area: "Settings raw-key action plan",
        status: blockedRows.length ? "blocked" : highRows.length ? "review" : "ready",
        evidence: `status=${rawStatus}; rows=${rawActionRows.length}; blocked=${blockedRows.length}; high=${highRows.length}; review/exclusion=${reviewRows.length}; schema=${schemaRow?.posture || "unknown"}; OCR=${ocrRow?.posture || "unknown"}`,
        nextStep: blockedRows.length
          ? "Open Settings > Raw-Key Action Plan before save, launch, rerun, or OCR decisions; schema drift and blocked raw keys need backend Preview Patch evidence."
          : highRows.length
            ? "Open Settings > Raw-Key Action Plan and verify OCR path evidence or advanced settings before unattended processing."
            : "Raw-key action plan has no blocking/high-review row in the loaded Settings workspace; subtitle keyword builder coverage and auth-token exclusions remain read-only guidance.",
      });
    } else {
      rows.push({
        area: "Settings raw-key action plan",
        status: "review",
        evidence: "raw-key action-plan rows not loaded",
        nextStep: "Open Settings and refresh the workspace before diagnosing schema drift, OCR path keys, or network auth-token boundaries.",
      });
    }
  }

  const toolchain = maintenance?.toolchain_evidence;
  if (toolchain && typeof toolchain === "object" && toolchain.schema_version) {
    const status = dependencyStatusLabel(toolchain.operator_status);
    const rowsList = Array.isArray(toolchain.rows) ? toolchain.rows : [];
    const blockedNames = rowsList
      .filter((row) => row?.required && dependencyStatusLabel(row?.operator_status || row?.status) !== "ready")
      .map((row) => row.name || row.tool_kind || "tool")
      .slice(0, 5);
    const reviewNames = rowsList
      .filter((row) => row?.optional && dependencyStatusLabel(row?.operator_status || row?.status) !== "ready")
      .map((row) => row.name || row.tool_kind || "tool")
      .slice(0, 5);
    rows.push({
      area: "Maintenance toolchain",
      status,
      evidence: `tools=${toolchain.tool_count || rowsList.length || 0}; required missing=${toolchain.required_missing_count || 0}; optional review=${toolchain.optional_review_count || 0}${blockedNames.length ? `; blocking=${blockedNames.join(", ")}` : ""}${reviewNames.length ? `; optional=${reviewNames.join(", ")}` : ""}`,
      nextStep: status === "blocked"
        ? "Open Maintenance, fix required toolchain rows, rerun Environment Health, then return to Queue/Launch/Diagnostics."
        : status === "review"
          ? "Open Maintenance and decide whether optional toolchain warnings are acceptable for this run."
          : "Maintenance toolchain evidence is ready in the loaded health payload.",
    });
  } else {
    rows.push({
      area: "Maintenance toolchain",
      status: "review",
      evidence: "maintenance health/toolchain evidence not loaded in this WebView session",
      nextStep: "Open Maintenance and run Environment Health before trusting long unattended processing or packaging/backfill dry runs.",
    });
  }
  return rows.sort((left, right) => dependencyStatusRank(left.status) - dependencyStatusRank(right.status));
}

function externalDependencyOverallStatus(context = {}) {
  const rows = externalDependencyRows(context);
  if (!rows.length) return "unknown";
  if (rows.some((row) => dependencyStatusLabel(row.status) === "blocked")) return "blocked";
  if (rows.some((row) => dependencyStatusLabel(row.status) === "review")) return "review";
  return "ready";
}

function externalDependencySummaryLines(context = {}) {
  const rows = externalDependencyRows(context);
  const status = externalDependencyOverallStatus(context);
  const counts = rows.reduce((acc, row) => {
    const key = dependencyStatusLabel(row.status);
    acc[key] = (acc[key] || 0) + 1;
    return acc;
  }, {});
  const first = rows.find((row) => dependencyStatusLabel(row.status) !== "ready") || rows[0];
  const lines = [
    "External dependency digest:",
    `Status: ${status}; rows=${rows.length}; blocked=${counts.blocked || 0}; review=${counts.review || 0}; ready=${counts.ready || 0}.`,
    "Scope: saved Settings OCR evidence, Settings raw-key action plan, Diagnostics settings handoff, and already-loaded Maintenance toolchain evidence.",
  ];
  rows.slice(0, 6).forEach((row) => {
    lines.push(`- ${row.area}: ${row.status}; ${row.evidence}`);
  });
  if (rows.length > 6) lines.push(`- ${rows.length - 6} more dependency row(s).`);
  lines.push("", `Next step: ${first ? `${first.area}: ${first.nextStep}` : "Refresh Settings, Diagnostics, and Maintenance evidence."}`);
  lines.push("Real-media boundary: dependency readiness does not prove route correctness, subtitle/audio output, output size, sidecars, or pending-publish completion for a real media file.");
  lines.push("Mutation guardrail: this digest is read-only and cannot install tools, edit PATH, stage or save settings, edit secrets, run OCR, launch FFmpeg, drain publish, repair manifests, or mutate files.");
  return lines;
}

function externalDependencyEvidenceText(context = {}) {
  const rows = externalDependencyRows(context);
  if (!rows.length) return "external dependency evidence not loaded";
  return rows
    .slice(0, 4)
    .map((row) => `${row.area}=${row.status}`)
    .join("; ");
}

function renderExternalDependencyDigest(context = {}) {
  const status = externalDependencyOverallStatus(context);
  setTextState("home-external-dependencies-status", status === "blocked" ? "Blocked" : status === "review" ? "Review" : status === "ready" ? "Ready" : "Unknown");
  setText("home-external-dependencies-summary", externalDependencySummaryLines(context).join("\n"));
}

function dailyDriverDiagnosticsCounts(diagnostics) {
  const view = window.mediaPipelineCrossPageContextView || {};
  if (typeof view.crossPageDiagnosticsCounts === "function") return view.crossPageDiagnosticsCounts(diagnostics || {});
  return {};
}

function dailyDriverCommandIssues() {
  const history = typeof getCommandHistory === "function" ? getCommandHistory() : [];
  if (!Array.isArray(history)) return [];
  return history.filter((entry) => {
    const level = typeof commandHistoryIssueLevel === "function" ? commandHistoryIssueLevel(entry) : (entry?.ok ? "ok" : (entry?.severity || "error"));
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
    `required failures=${requiredFailures.length}; supporting failures=${optionalFailures.length}; completed=${refreshTimeLabel(lastRefreshCompletedAt)}${Number.isFinite(lastRefreshDurationMs) ? `; duration=${lastRefreshDurationMs}ms` : ""}`,
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
    `rows=${Array.isArray(queue.rows) ? queue.rows.length : 0}; runnable=${dailyDriverCount(queue.runnable_count || (Array.isArray(queue.rows) ? queue.rows.length : 0))}; stale=${queue.snapshot_file_freshness_status || "unknown"}; blocked=${dailyDriverCount(queue.blocked_row_count)}; invalid=${dailyDriverCount(queue.invalid_row_count)}`,
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
  rows.push(dailyDriverRow(
    "Network visibility",
    role && role !== "standalone" ? "review" : "ready",
    `role=${role}; persisted worker rows=${workerRows}`,
    role && role !== "standalone"
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
    `Refresh evidence: completed ${refreshTimeLabel(lastRefreshCompletedAt)}${Number.isFinite(lastRefreshDurationMs) ? ` in ${lastRefreshDurationMs} ms` : ""}.`,
    "Real-media boundary: WebView readiness is not proof by itself. Daily-driver confidence still requires a known sample run whose Queue, Completed, Diagnostics, and Pending Publish evidence agree.",
  ];
  lines.push("", `Next operator action: ${firstAction ? `${firstAction.area}: ${firstAction.nextStep}` : "No checklist blocker is visible; refresh once before long unattended operation."}`);
  lines.push("Mutation guardrail: this checklist is read-only and does not launch, repair, drain, save, rename, delete, publish, or touch media files.");
  return lines;
}

function homeAtAGlanceStatusState(label) {
  const normalized = String(label || "").toLowerCase();
  if (normalized === "blocked") return "blocked";
  if (normalized === "review") return "warning";
  if (normalized === "active") return "changed";
  if (normalized === "idle" || normalized === "ready") return "ok";
  return "loading";
}

function homeAtAGlancePercent(value) {
  const number = Number(value);
  if (!Number.isFinite(number)) return "";
  const bounded = Math.max(0, Math.min(100, number));
  return `${bounded.toFixed(bounded % 1 ? 1 : 0)}%`;
}

function homeAtAGlanceShortValue(value, maxChars = 64) {
  const text = formatProgressValue(value || "");
  if (!text) return "";
  if (typeof shortenPath === "function") return shortenPath(text, maxChars);
  return text.length > maxChars ? `...${text.slice(-(maxChars - 3))}` : text;
}

function homeAtAGlanceCurrentFile(progress = {}) {
  return progress.CurrentFileDisplay
    || progress.CurrentFile
    || progress.CurrentFilePath
    || progress.SourceFile
    || progress.SourcePath
    || progress.InputPath
    || progress.OutputPath
    || "";
}

function homeAtAGlanceQueuePosition(progress = {}) {
  const index = progress.CurrentQueueIndex;
  const total = progress.CurrentQueueTotal;
  if ((index === undefined || index === null || index === "") && (total === undefined || total === null || total === "")) return "";
  return `${formatProgressValue(index || 0)} / ${formatProgressValue(total || 0)}`;
}

function homeAtAGlanceQueueTitle(item = {}) {
  return item.lookup_title
    || item.display_name
    || item.title
    || item.source_file_name
    || item.source_file
    || item.source_path
    || item.path
    || item.input_path
    || item.file
    || "";
}

function homeAtAGlanceQueueMeta(item = {}) {
  return [
    item.route_name || item.route || item.mode || "",
    item.status || item.operator_status || item.decision || "",
    item.queue_position || (item.queue_index || item.queue_total ? `${item.queue_index || "?"}/${item.queue_total || "?"}` : ""),
  ].filter(Boolean).map(formatProgressValue).join(" · ");
}

function homeAtAGlanceProgressNumber(value) {
  const number = Number(value);
  if (!Number.isFinite(number)) return null;
  return Math.max(0, Math.min(100, number));
}

function homeAtAGlancePushStatus(value) {
  const state = String(value || "").toLowerCase();
  if (state.includes("fail") || state.includes("error") || state.includes("blocked")) return "blocked";
  if (state.includes("complete") || state.includes("deferred") || state.includes("published")) return "complete";
  if (state.includes("copy") || state.includes("push") || state.includes("reveal")) return "active";
  return state ? "unknown" : "";
}

function homeAtAGlanceBarStatusLabel(bar) {
  const status = String(bar?.status || "unknown").trim();
  const mode = String(bar?.mode || "determinate").trim();
  const percent = bar?.percent;
  if (mode === "indeterminate") return status === "active" ? `${status} · running` : status;
  const value = Number(percent);
  if (!Number.isFinite(value)) return status;
  const bounded = Math.max(0, Math.min(100, value));
  return `${status} · ${bounded.toFixed(bounded % 1 ? 1 : 0)}%`;
}

function homeAtAGlancePerFilePushBar(snapshot = null, progress = {}) {
  const bars = Array.isArray(snapshot?.progress_bars) ? snapshot.progress_bars.filter(Boolean) : [];
  const backendBar = bars.find((bar) => String(bar?.id || "").toLowerCase() === "publish_copy");
  if (backendBar) {
    return {
      ...backendBar,
      id: "home_push_file",
      label: "Push file",
    };
  }
  const pushState = progress.PushState || progress.push_state || "";
  const status = homeAtAGlancePushStatus(pushState);
  if (!status || status === "complete") return null;
  const copyPercent = homeAtAGlanceProgressNumber(progress.CopyPercent ?? progress.copy_percent);
  const copied = progress.CopyBytesCopied ?? progress.copy_bytes_copied ?? "";
  const total = progress.CopyTotalBytes ?? progress.copy_total_bytes ?? "";
  const file = homeAtAGlanceShortValue(homeAtAGlanceCurrentFile(progress), 88);
  const detail = [
    pushState ? `Push ${formatProgressValue(pushState)}` : "",
    copied !== "" && total !== "" ? `${formatProgressValue(copied)} / ${formatProgressValue(total)} bytes` : "",
    file ? `File ${file}` : "",
  ].filter(Boolean).join(" · ");
  return {
    id: "home_push_file",
    label: "Push file",
    mode: copyPercent === null ? "indeterminate" : "determinate",
    percent: copyPercent === null ? 0 : copyPercent,
    status,
    detail: detail || "Per-file push is active.",
    source: "pipeline_progress.json",
    updated_at: progress.CopyUpdatedAt || progress.LastUpdate || progress.UpdatedAt || "",
    stale: false,
  };
}

function homeAtAGlanceUpcomingRows(queue = {}, progress = {}) {
  const rows = Array.isArray(queue.rows) ? queue.rows.filter(Boolean) : [];
  if (!rows.length) return [];
  const currentIndex = Number(progress.CurrentQueueIndex);
  const startIndex = Number.isFinite(currentIndex) && currentIndex > 0 && currentIndex < rows.length
    ? Math.floor(currentIndex)
    : 0;
  return rows.slice(startIndex, startIndex + 4);
}

function homeAtAGlanceModel(context = {}) {
  const snapshot = context.snapshot || null;
  const closeReadiness = context.closeReadiness || null;
  const diagnostics = context.diagnostics || {};
  const queue = context.queue || {};
  const progress = snapshot?.progress && typeof snapshot.progress === "object" ? snapshot.progress : {};
  const activeJobs = Array.isArray(diagnostics?.active_jobs) ? diagnostics.active_jobs.filter(Boolean) : [];
  const pipelineState = snapshot?.pipeline_state || closeReadiness?.state || "unknown";
  const stateActive = ["processing", "running", "active", "publishing", "audit"].includes(String(pipelineState || "").toLowerCase());
  const active = activeJobs.length > 0 || closeReadiness?.safe_to_close === false || stateActive;
  const stage = progress.CurrentStage || progress.Status || "";
  const percent = homeAtAGlancePercent(progress.CurrentStagePercent);
  const percentNumber = Number(progress.CurrentStagePercent);
  const rawFile = homeAtAGlanceCurrentFile(progress);
  const file = homeAtAGlanceShortValue(rawFile, 88);
  const queuePosition = homeAtAGlanceQueuePosition(progress);
  const route = progress.CurrentRoute || progress.Route || "";
  const detail = [
    stage ? `Stage ${formatProgressValue(stage)}` : "",
    percent ? percent : "",
    route ? `Route ${formatProgressValue(route)}` : "",
    queuePosition ? `Queue ${queuePosition}` : "",
    activeJobs.length ? `${activeJobs.length} ActiveJobs` : "",
  ].filter(Boolean).join(" · ");
  const status = !snapshot && !closeReadiness
    ? "Checking"
    : active
      ? "Active"
      : Object.keys(progress).length
        ? "Idle"
        : "Ready";
  return {
    active,
    status,
    pipelineState,
    file,
    rawFile,
    stage,
    percent,
    percentNumber,
    route,
    queuePosition,
    pushBar: homeAtAGlancePerFilePushBar(snapshot, progress),
    detail: detail || `Pipeline ${pipelineState}; close ${closeReadiness ? (closeReadiness.safe_to_close ? "safe" : "active work") : "unknown"}.`,
    currentText: file ? `${stage ? formatProgressValue(stage) : "Processing"}: ${file}` : active ? "Backend work is active." : "No active item.",
    upcoming: homeAtAGlanceUpcomingRows(queue, progress),
  };
}

function homeAtAGlanceProgressBar(model) {
  const bars = [];
  if (!model.active && !Number.isFinite(model.percentNumber)) return model.pushBar ? [model.pushBar] : [];
  const percent = Number.isFinite(model.percentNumber) ? model.percentNumber : 0;
  bars.push({
    id: "home_current_item",
    label: "Current item",
    mode: Number.isFinite(model.percentNumber) ? "determinate" : "indeterminate",
    percent,
    status: model.active ? "active" : percent >= 100 ? "complete" : "unknown",
    detail: model.detail || "No progress detail reported.",
    source: "snapshot progress",
  });
  if (model.pushBar) bars.push(model.pushBar);
  return bars;
}

function homeAtAGlanceSummaryText(model) {
  const upcoming = model.upcoming
    .map((item) => homeAtAGlanceShortValue(homeAtAGlanceQueueTitle(item), 48))
    .filter(Boolean)
    .slice(0, 3);
  return [
    model.active ? "Processing now." : "No active processing item is reported.",
    model.file ? `Current: ${model.file}.` : "",
    model.percent ? `Progress: ${model.percent}.` : "",
    model.pushBar ? `Push: ${homeAtAGlanceBarStatusLabel(model.pushBar)}.` : "",
    upcoming.length ? `Up next: ${upcoming.join(" | ")}.` : "Up next: no queue items loaded.",
  ].filter(Boolean).join(" ");
}

function renderHomeAtAGlanceQueue(items = []) {
  const list = byId("home-at-a-glance-up-next");
  if (!list) return;
  list.replaceChildren();
  const rows = Array.isArray(items) ? items : [];
  if (!rows.length) {
    const empty = document.createElement("li");
    empty.textContent = "No queue items loaded.";
    list.appendChild(empty);
    return;
  }
  rows.forEach((item) => {
    const li = document.createElement("li");
    const title = document.createElement("span");
    title.className = "home-up-next-title";
    const rawTitle = homeAtAGlanceQueueTitle(item);
    title.textContent = homeAtAGlanceShortValue(rawTitle, 70) || "Untitled queue item";
    if (rawTitle) title.title = rawTitle;
    const meta = document.createElement("span");
    meta.className = "home-up-next-meta";
    meta.textContent = homeAtAGlanceQueueMeta(item) || "queued";
    li.append(title, meta);
    list.appendChild(li);
  });
}

function renderHomeAtAGlance(context = {}) {
  const model = homeAtAGlanceModel(context);
  setTextState("home-at-a-glance-status", model.status, homeAtAGlanceStatusState(model.status));
  setText("home-at-a-glance-current", model.currentText);
  setText("home-at-a-glance-detail", model.detail);
  setText("home-at-a-glance-summary", homeAtAGlanceSummaryText(model));
  if (typeof renderProgressBarsInto === "function") {
    renderProgressBarsInto("home-at-a-glance-progress-bars", homeAtAGlanceProgressBar(model), context.snapshot || {}, "No active progress loaded.");
  }
  renderHomeAtAGlanceQueue(model.upcoming);
}

function renderDailyDriverReadiness(context = {}) {
  const rows = dailyDriverRows(context);
  setTextState("daily-driver-status", dailyDriverOverallStatus(rows));
  setText("daily-driver-summary", dailyDriverSummaryLines(rows).join("\n"));
  setText("daily-driver-legend", "Daily-driver checklist rows are read-only and do not launch, repair, drain, save, rename, or mutate files.");
  const tbody = byId("daily-driver-rows");
  if (!tbody) return;
  if (!rows.length) {
    clearRows(tbody, 4, "No daily-driver readiness rows loaded.");
    return;
  }
  tbody.replaceChildren();
  rows.forEach((item) => {
    const row = document.createElement("tr");
    row.dataset.status = dailyDriverStatusClass(item.status);
    appendCells(row, [item.area, item.status, item.evidence, item.nextStep]);
    tbody.appendChild(row);
  });
}

function pipelineControlReadinessStatus(snapshot, closeReadiness) {
  if (!snapshot) return "No snapshot";
  if (closeReadiness?.safe_to_close === false || closeReadiness?.active_work) return "Active controls";
  const state = String(snapshot.pipeline_state || closeReadiness?.state || "").toLowerCase();
  if (["processing", "running", "active", "publishing", "audit"].includes(state)) return "Active controls";
  if (["idle", "completed", "failed"].includes(state)) return "Idle";
  return "Review state";
}

function pipelineControlReadinessLines(snapshot, closeReadiness) {
  if (!snapshot) {
    return [
      "Snapshot: unavailable",
      "Control guidance: wait for snapshot refresh before sending pipeline controls.",
      "Mutation guardrail: control buttons send backend-owned control flags through /api/pipeline/control.",
    ];
  }
  const state = snapshot.pipeline_state || closeReadiness?.state || "unknown";
  const progress = snapshot.progress && typeof snapshot.progress === "object" ? snapshot.progress : {};
  const active = closeReadiness?.safe_to_close === false || closeReadiness?.active_work === true;
  const lines = [
    `Pipeline state: ${state}`,
    `Active work: ${active ? "yes" : "no"}`,
    `Close readiness: ${closeReadiness ? (closeReadiness.safe_to_close ? "safe" : "active/blocked") : "unknown"}`,
    progress.CurrentStage ? `Current stage: ${progress.CurrentStage}` : "",
    progress.Status ? `Progress status: ${progress.Status}` : "",
  ].filter(Boolean);
  if (closeReadiness?.reason) lines.push(`Close reason: ${closeReadiness.reason}`);
  lines.push("");
  if (active) {
    lines.push("Pause / Resume: meaningful while backend work is active.");
    lines.push("Rescan: request only when the running pipeline should refresh queue state.");
    lines.push("Stop After Current: request when current work should finish but no new item should start.");
  } else {
    lines.push("Pause / Resume: normally unnecessary while no active work is reported.");
    lines.push("Rescan: normally unnecessary while idle; refresh Queue or launch a fresh preview instead.");
    lines.push("Stop After Current: normally unnecessary while close-readiness reports safe.");
  }
  lines.push("Mutation guardrail: control buttons send backend-owned control flags through /api/pipeline/control and backend locks remain the source of truth.");
  return lines;
}

function renderControlReadiness(snapshot = lastSnapshot, closeReadiness = lastCloseReadiness) {
  setTextState("control-readiness-status", pipelineControlReadinessStatus(snapshot, closeReadiness));
  setTextState("home-control-readiness-status", pipelineControlReadinessStatus(snapshot, closeReadiness));
  setText("control-readiness", pipelineControlReadinessLines(snapshot, closeReadiness).join("\n"));
  window.mediaPipelineLaunchView?.updateLaunchCommandButtonStates?.(snapshot, closeReadiness);
}

function recordLocalUiDiagnostic(command, message, severity = "warning") {
  const result = {
    schema_version: "desktop_command_result.v1",
    command,
    ok: severity !== "error",
    severity,
    message,
    local: true,
    refresh_hint: "diagnostics",
  };
  if (typeof appendCommandResult === "function") appendCommandResult(result);
  return result;
}

function renderTelemetrySafely(telemetry) {
  const renderTelemetryFn = window.mediaPipelineTelemetryView?.renderTelemetry;
  if (typeof renderTelemetryFn !== "function") return null;
  try {
    renderTelemetryFn(telemetry);
    return null;
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    setTextState("telemetry-readiness-status", "Render warning", "warning");
    setText("telemetry-readiness-summary", [
      "Telemetry payload loaded, but the WebView renderer failed.",
      `Root cause: ${message}`,
      "Next step: open Diagnostics and inspect browser/runtime logs before trusting telemetry graphs.",
    ].join("\n"));
    recordLocalUiDiagnostic("telemetry.render", `Telemetry rendering failed: ${message}`, "warning");
    return {
      name: "telemetry render",
      required: false,
      message,
    };
  }
}

function visiblePagePanel() {
  return document.querySelector(".page.is-visible[data-page-panel]");
}

function panelVisibilityEmptyState(page) {
  let node = page.querySelector(':scope > [data-page-empty-state="panel-visibility"]');
  if (node) return node;

  node = document.createElement("section");
  node.className = "page-panel-empty-window";
  node.dataset.pageEmptyState = "panel-visibility";
  node.setAttribute("role", "status");
  node.setAttribute("aria-live", "polite");
  node.setAttribute("aria-hidden", "true");

  const title = document.createElement("strong");
  title.textContent = "No boxes are visible on this tab.";
  const detail = document.createElement("p");
  detail.className = "page-panel-empty-detail";
  detail.textContent = "Boxes may be hidden by Advanced, Evidence, or Customize settings.";

  const actions = document.createElement("div");
  actions.className = "inline-actions page-panel-empty-actions";
  const showEvidence = document.createElement("button");
  showEvidence.type = "button";
  showEvidence.className = "secondary-button";
  showEvidence.textContent = "Show Evidence";
  showEvidence.addEventListener("click", () => {
    if (document.body.classList.contains("evidence-hidden")) {
      byId("evidence-toggle")?.click();
    } else {
      updatePagePanelEmptyStates();
    }
  });
  const showAdvanced = document.createElement("button");
  showAdvanced.type = "button";
  showAdvanced.className = "secondary-button";
  showAdvanced.textContent = "Show Advanced";
  showAdvanced.addEventListener("click", () => {
    if (!document.body.classList.contains("advanced-mode")) {
      byId("advanced-toggle")?.click();
    } else {
      updatePagePanelEmptyStates();
    }
  });
  const customize = document.createElement("button");
  customize.type = "button";
  customize.className = "secondary-button";
  customize.textContent = "Customize";
  customize.addEventListener("click", () => {
    if (!document.body.classList.contains("layout-customize-mode")) {
      byId("customize-layout-btn")?.click();
    } else {
      updatePagePanelEmptyStates();
    }
  });
  actions.append(showEvidence, showAdvanced, customize);
  node.append(title, detail, actions);
  page.appendChild(node);
  return node;
}

function panelIsCurrentlyVisible(panel) {
  return Boolean(panel.offsetWidth || panel.offsetHeight || panel.getClientRects().length);
}

function panelHiddenByAdvancedGate(panel) {
  if (document.body.classList.contains("advanced-mode")) return false;
  return panel.hasAttribute("data-panel-advanced") || panel.hasAttribute("data-advanced") || Boolean(panel.closest("[data-advanced]"));
}

function panelHiddenByEvidenceGate(panel) {
  if (!document.body.classList.contains("evidence-hidden")) return false;
  if (panel.dataset.evidenceToggleExempt === "true") return false;
  return panel.dataset.panelType === "evidence";
}

function pagePanelHiddenReasonLines(page, panels) {
  const reasons = [];
  if (panels.some(panelHiddenByAdvancedGate)) reasons.push("Advanced is off.");
  if (panels.some(panelHiddenByEvidenceGate)) reasons.push("Evidence is hidden.");
  if (panels.some((panel) => panel.hasAttribute("data-panel-hidden"))) reasons.push("Customize has hidden panel(s).");
  if (!reasons.length) reasons.push("A display filter is hiding this tab's panels.");
  return `Boxes may be hidden by ${reasons.join(" ")} Use the controls above to restore them.`;
}

function updatePagePanelEmptyState(page) {
  if (!page) return;
  const empty = panelVisibilityEmptyState(page);
  const panels = Array.from(page.querySelectorAll(".panel")).filter((panel) => !panel.closest("[data-page-empty-state]"));
  const hasVisiblePanel = panels.some(panelIsCurrentlyVisible);
  const shouldShow = page.classList.contains("is-visible") && panels.length > 0 && !hasVisiblePanel;
  empty.classList.toggle("is-visible", shouldShow);
  empty.setAttribute("aria-hidden", String(!shouldShow));
  if (shouldShow) {
    const detail = empty.querySelector(".page-panel-empty-detail");
    if (detail) detail.textContent = pagePanelHiddenReasonLines(page, panels);
  }
}

function updatePagePanelEmptyStates() {
  document.querySelectorAll(".page[data-page-panel]").forEach(updatePagePanelEmptyState);
}

function showPage(page) {
  const normalized = String(page || "").trim();
  if (!normalized) return;
  const buttons = Array.from(document.querySelectorAll(".nav-button"));
  const panels = Array.from(document.querySelectorAll("[data-page-panel]"));
  buttons.forEach((item) => item.classList.toggle("is-active", item.dataset.page === normalized));
  panels.forEach((panel) => panel.classList.toggle("is-visible", panel.dataset.pagePanel === normalized));
  updatePagePanelEmptyStates();
  if (normalized === "maintenance" && typeof hasMaintenanceLoaded === "function" && !hasMaintenanceLoaded()) {
    refreshMaintenance();
  }
}

function applyDefaultActionTooltips() {
  const tooltips = [
    ["#pipeline-start-button", "Start is disabled while active work is reported. Backend start routes re-check queue, schedule, settings, and process locks at submission time."],
    ["#home-refresh-button", "Refreshes dashboard state from backend snapshots without starting or mutating media work."],
    ["#audit-start-button", "Starts backend audit mode. Use only after the library root and active-work state look correct."],
    ["#rerun-start-button", "Starts backend CSV rerun with copy / keep / park policy. Review the CSV path and preflight before starting."],
    ["#pending-drain-button", "Requests backend pending-publish drain. Drain safety remains backend-owned and requires parked payload evidence."],
    ['[data-control-action="pause"]', "Pause or resume the active backend pipeline. Disabled while no active work is reported."],
    ['[data-control-action="rescan"]', "Request a backend queue rescan flag for the running pipeline. Disabled while no active work is reported."],
    ['[data-control-action="stop"]', "Request graceful Stop After Current. The current file may finish; no new item should start."],
    ['[data-control-action="kill"]', "Emergency force stop. Requires confirmation and asks the backend to terminate the active process tree."],
    ["#backend-shutdown-button", "Request backend shutdown only when close-readiness reports safe."],
    ["#maintenance-refresh-button", "Runs backend maintenance probes. Tool checks can take several seconds on portable bundles."],
    ["#release-dry-run-button", "Plans a deployment package without writing files. Review dry-run evidence before creating a deployment."],
    ["#release-build-button", "Creates a deployment package through the backend release builder after confirmation."],
    ["#backfill-dry-run-button", "Dry-run completed-manifest backfill. No manifest writes should occur during dry-run."],
    ["#diagnostics-tail-refresh-button", "Reads a bounded backend-allowlisted log tail. It cannot open arbitrary paths."],
    ["#sample-validation-append-button", "Appends backend-authored sample validation evidence only after preview/review. It does not accept output or publish media."],
    ["#sample-validation-preview-button", "Previews the sample validation record before any append."],
    ["#rename-apply-selected-button", "Submits selected rename rows to the backend transaction. Blocked rows cannot be applied."],
    ["#rename-preview-button", "Builds a backend rename preview. It does not rename files."],
    ["#rename-preview-top-button", "Builds a backend rename preview. It does not rename files."],
    ["#rename-use-selected-queue-button", "Copies the selected Queue source path into Rename paths. It does not rename files."],
    ["#rename-use-loaded-queue-button", "Copies loaded Queue source paths into Rename paths. It does not rename files."],
    ["#rename-browse-files-button", "Opens the Windows file browser and stages selected paths. It does not preview or rename files."],
    ["#rename-browse-folder-button", "Opens the Windows folder browser and stages the selected folder path. It does not preview or rename files."],
    ["#rename-add-path-button", "Adds the typed source path to Rename paths. It does not inspect or rename files."],
    ["#rename-clear-paths-button", "Clears staged Rename paths and preview rows. It does not touch source files."],
    ["#settings-network-apply-button", "Stages standalone/coordinator/worker settings into the shared Settings patch JSON. It does not start or stop workers."],
    ["#settings-network-reset-button", "Reloads the Workers tab mode controls from current saved backend settings."],
    ["#network-settings-preview-button", "Previews staged Worker Mode Settings through the backend settings route. It does not save the PSD1."],
    ["#network-settings-save-button", "Saves staged Worker Mode Settings through backend validation and config backup. It does not start or stop workers."],
    ["#settings-save-patch-button", "Saves staged settings through backend validation. Raw WebView fields never write directly to the PSD1."],
    ["#settings-preview-patch-button", "Previews staged settings changes without saving."],
  ];
  tooltips.forEach(([selector, title]) => {
    document.querySelectorAll(selector).forEach((node) => {
      if (!node.title) node.title = title;
    });
  });
}

async function refreshAll() {
  if (refreshInFlight) {
    refreshQueued = true;
    return;
  }
  refreshInFlight = true;
  try {
    await refreshAllNow();
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    renderTopbarActivity({ activity: `Refresh failed: ${message}` });
    renderRefreshHealth([{
      name: "refresh/render",
      required: true,
      message,
    }]);
  } finally {
    refreshInFlight = false;
    if (refreshQueued) {
      refreshQueued = false;
      window.setTimeout(refreshAll, 0);
    }
  }
}

async function refreshAllNow() {
  lastRefreshStartedAt = new Date();
  const refreshStartedMs = Date.now();
  renderRefreshInProgress();
  const failureSourceMarkers = Boolean(byId("failure-source-markers")?.checked);
  const failureQuery = `/api/failures?limit=100${failureSourceMarkers ? "&source=markers" : ""}`;
  const auditPriorityOnly = Boolean(byId("audit-preview-priority-only")?.checked);
  const auditQuery = `/api/audit-results?limit=100${auditPriorityOnly ? "&priority_only=true" : ""}`;
  const requests = [
    ["health", apiGet("/api/health"), false],
    ["snapshot", apiGet("/api/snapshot"), true],
    ["close readiness", apiGet("/api/backend/close-readiness"), false],
    ["telemetry", apiGet("/api/telemetry"), false],
    ["diagnostics", apiGet("/api/diagnostics"), false],
    ["diagnostics state summary", apiGet("/api/diagnostics/state-summary"), false],
    ["commands", apiGet("/api/commands?limit=20"), false],
    ["queue", apiGet("/api/queue"), false],
    ["completed", apiGet("/api/completed"), false],
    ["failures", apiGet(failureQuery), false],
    ["audit results", apiGet(auditQuery), false],
    ["pending publish", apiGet("/api/pending-publish"), false],
    ["schedule", apiGet("/api/schedule"), false],
    ["settings", apiGet("/api/settings/workspace"), false],
    ["network workers", apiGet("/api/network/workers"), false],
    ["sample validation", apiGet("/api/sample-validation?limit=10"), false],
    ["contract", apiGet("/api/contract"), false],
  ];
  const results = await Promise.allSettled(requests.map(([, request]) => request));
  const values = {};
  const failures = [];
  results.forEach((result, index) => {
    const [name, , required] = requests[index];
    const failure = refreshFailure(name, result, Boolean(required));
    if (failure) {
      failures.push(failure);
      return;
    }
    values[name] = result.value;
  });
  if (values.snapshot) {
    renderSnapshot(values.snapshot);
  } else {
    const snapshotFailure = failures.find((item) => item.name === "snapshot");
    const message = snapshotFailure?.message || "snapshot unavailable";
    renderTopbarActivity({ activity: `Backend snapshot read failed: ${message}` });
    const pill = byId("state-pill");
    if (pill) {
      pill.textContent = "error";
      pill.dataset.state = "failed";
    }
  }
  if (values.health?.startup_progress) {
    lastStartupProgress = values.health.startup_progress;
  }
  if (values["close readiness"]) renderCloseReadiness(values["close readiness"]);
  const telemetryRenderFailure = values.telemetry ? renderTelemetrySafely(values.telemetry) : null;
  if (telemetryRenderFailure) failures.push(telemetryRenderFailure);
  if (values.diagnostics) renderDiagnostics(values.diagnostics);
  const renderDiagnosticsStateSummaryFn = window.mediaPipelineDiagnosticsStateSummaryView?.renderDiagnosticsStateSummary;
  if (values["diagnostics state summary"] && typeof renderDiagnosticsStateSummaryFn === "function") {
    renderDiagnosticsStateSummaryFn(values["diagnostics state summary"]);
  }
  if (values.commands) window.mediaPipelineCommandHistory?.renderCommandHistoryPayload?.(values.commands);
  if (values.queue) renderQueue(values.queue);
  renderHomeQueueSnapshot(values.queue || {});
  if (values.completed) renderCompleted(values.completed);
  renderHomeRecentCompleted(values.completed || {});
  if (values.failures) window.mediaPipelineReportsView?.renderFailurePreview?.(values.failures);
  if (values["audit results"]) window.mediaPipelineReportsView?.renderAuditPreview?.(values["audit results"]);
  if (values["pending publish"]) renderPendingPublish(values["pending publish"], values.snapshot || lastSnapshot);
  renderHomePendingCount(values["pending publish"] || {});
  if (values.schedule) {
    lastSchedule = values.schedule;
    renderSchedule(values.schedule);
  }
  if (values.settings) {
    renderSettings(values.settings);
    window.mediaPipelineReportsView?.renderReports?.(lastSnapshot, getLastSettings());
    window.mediaPipelineLaunchView?.renderAllLaunchPreflights?.();
  }
  if (values.contract) window.mediaPipelineContractView?.renderContract?.(values.contract);
  const renderNetworkViewFn = window.mediaPipelineNetworkView?.renderNetworkView;
  if (typeof renderNetworkViewFn === "function") {
    renderNetworkViewFn({
      settings: values.settings || getLastSettings(),
      contract: values.contract || {},
      closeReadiness: values["close readiness"] || lastCloseReadiness,
      snapshot: values.snapshot || lastSnapshot,
      networkWorkers: values["network workers"] || null,
      bootstrap,
    });
  }
  renderBackendLifecycle(values["close readiness"] || lastCloseReadiness, values.snapshot || lastSnapshot);
  renderHomeReadiness({
    snapshot: values.snapshot || lastSnapshot,
    closeReadiness: values["close readiness"] || lastCloseReadiness,
    failures,
  });
  const dependencyContext = {
    settings: values.settings || getLastSettings(),
    stateSummary: values["diagnostics state summary"] || {},
    maintenance: typeof getLastMaintenance === "function" ? getLastMaintenance() : {},
  };
  renderExternalDependencyDigest(dependencyContext);
  if (typeof renderLaunchReadiness === "function") {
    renderLaunchReadiness({
      snapshot: values.snapshot || lastSnapshot,
      closeReadiness: values["close readiness"] || lastCloseReadiness,
      schedule: values.schedule || lastSchedule,
      settings: values.settings || getLastSettings(),
      failures,
    });
  }
  if (typeof renderHomeActiveWork === "function") {
    renderHomeActiveWork({
      snapshot: values.snapshot || lastSnapshot,
      diagnostics: values.diagnostics || null,
      closeReadiness: values["close readiness"] || lastCloseReadiness,
    });
  }
  if (typeof renderProgressEvidence === "function") {
    renderProgressEvidence({
      snapshot: values.snapshot || lastSnapshot,
      closeReadiness: values["close readiness"] || lastCloseReadiness,
      diagnostics: values.diagnostics || null,
    });
  }
  if (typeof renderCrossPageContext === "function") {
    const crossPageContext = {
      snapshot: values.snapshot || lastSnapshot,
      closeReadiness: values["close readiness"] || lastCloseReadiness,
      queue: values.queue || {},
      completed: values.completed || {},
      pending: values["pending publish"] || {},
      diagnostics: values.diagnostics || {},
      settings: values.settings || getLastSettings(),
      sampleValidation: values["sample validation"] || {},
      failures,
    };
    renderCrossPageContext(crossPageContext);
    window.mediaPipelineLaunchView?.renderLaunchRealMediaProofHandoff?.(crossPageContext);
  }
  if (typeof renderDiagnosticsInvestigationTrail === "function") {
    const diagnosticsContext = {
      snapshot: values.snapshot || lastSnapshot,
      closeReadiness: values["close readiness"] || lastCloseReadiness,
      diagnostics: values.diagnostics || {},
      stateSummary: values["diagnostics state summary"] || {},
      commands: values.commands || {},
      queue: values.queue || {},
      completed: values.completed || {},
      pending: values["pending publish"] || {},
      settings: values.settings || getLastSettings(),
      sampleValidation: values["sample validation"] || {},
      maintenance: typeof getLastMaintenance === "function" ? getLastMaintenance() : {},
      failures,
    };
    const renderDiagnosticsFirstResponseFn = window.mediaPipelineDiagnosticsView?.renderDiagnosticsFirstResponse;
    if (typeof renderDiagnosticsFirstResponseFn === "function") {
      renderDiagnosticsFirstResponseFn(diagnosticsContext);
    }
    renderDiagnosticsInvestigationTrail(diagnosticsContext);
  }
  const renderDiagnosticsOwnerHandoffFn = window.mediaPipelineDiagnosticsView?.renderDiagnosticsOwnerHandoff;
  if (typeof renderDiagnosticsOwnerHandoffFn === "function") {
    renderDiagnosticsOwnerHandoffFn({
      queue: values.queue || {},
      completed: values.completed || {},
      pending: values["pending publish"] || {},
      sampleValidation: values["sample validation"] || {},
      settings: values.settings || getLastSettings(),
    });
  }
  lastRefreshCompletedAt = new Date();
  lastRefreshDurationMs = Date.now() - refreshStartedMs;
  renderRefreshHealth(failures);
  const dashboardContext = {
    snapshot: values.snapshot || lastSnapshot,
    closeReadiness: values["close readiness"] || lastCloseReadiness,
    schedule: values.schedule || lastSchedule,
    settings: values.settings || getLastSettings(),
    stateSummary: values["diagnostics state summary"] || {},
    maintenance: typeof getLastMaintenance === "function" ? getLastMaintenance() : {},
    queue: values.queue || {},
    completed: values.completed || {},
    pending: values["pending publish"] || {},
    diagnostics: values.diagnostics || {},
    networkWorkers: values["network workers"] || {},
    failuresPayload: values.failures || {},
    auditResults: values["audit results"] || {},
    failures,
  };
  renderHomeAtAGlance(dashboardContext);
  renderDailyDriverReadiness(dashboardContext);
}

window.externalDependencyRows = externalDependencyRows;
window.externalDependencyOverallStatus = externalDependencyOverallStatus;
window.externalDependencySummaryLines = externalDependencySummaryLines;
window.externalDependencyEvidenceText = externalDependencyEvidenceText;
window.renderExternalDependencyDigest = renderExternalDependencyDigest;

// ── HOME PAGE FUNCTIONS — Stage 12 ──────────────────────────────────────────

function renderHomePendingCount(pending) {
  pending = pending && typeof pending === "object" ? pending : {};
  setText("home-pending-count", String(pending.count || 0));
}

function renderHomeNetworkRole(settings) {
  settings = settings && typeof settings === "object" ? settings : {};
  const role = String(settings?.config?.NetworkRole || "").trim().toLowerCase() || "standalone";
  setText("home-network-role", role);
}

function renderHomeQueueSnapshot(queue) {
  queue = queue && typeof queue === "object" ? queue : {};
  const rows = Array.isArray(queue.rows) ? queue.rows : [];
  const runnable = queue.runnable_count !== undefined ? queue.runnable_count : rows.length;
  const blocked = queue.blocked_row_count || 0;
  const priority = queue.priority_count || rows.filter((r) => r?.is_priority).length || 0;
  const encodeRows = rows.filter((r) => String(r?.route_name || "").toLowerCase().includes("encode")).length;
  const remuxRows = rows.filter((r) => String(r?.route_name || "").toLowerCase().includes("remux")).length;
  // Drive the dashboard "Queue" metric tile from the real snapshot data so
  // it shows the actual queue size (runnable / total rows) rather than the
  // active run's batch position (CurrentQueueIndex/Total), which was always
  // 0/0 when the pipeline was idle.
  setText("queue-count", `${runnable} / ${rows.length}`);
  const lines = [
    `Rows: ${rows.length} | Runnable: ${runnable} | Blocked: ${blocked}`,
    priority ? `Priority: ${priority}` : "",
    encodeRows || remuxRows ? `Route mix: ${encodeRows} encode / ${remuxRows} remux` : "",
    queue.error ? `Error: ${queue.error}` : "",
    ...(Array.isArray(queue.warnings) ? queue.warnings.slice(0, 2) : []),
  ].filter(Boolean);
  const statusEl = byId("home-queue-snapshot-status");
  if (statusEl) statusEl.textContent = rows.length ? `${rows.length} items` : "Empty";
  const pre = byId("home-queue-snapshot");
  if (pre) pre.textContent = lines.join("\n") || "No queue data loaded.";
}

function renderHomeRecentCompleted(completed) {
  completed = completed && typeof completed === "object" ? completed : {};
  const rows = Array.isArray(completed.rows) ? completed.rows : [];
  const tbody = byId("home-recent-completed-tbody");
  if (!tbody) return;
  const statusEl = byId("home-recent-completed-status");
  if (statusEl) statusEl.textContent = rows.length ? `${completed.count || rows.length} total` : "No data";
  tbody.textContent = "";
  const recent = rows.slice(0, 5);
  if (!recent.length) {
    const tr = document.createElement("tr");
    if (typeof appendCells === "function") appendCells(tr, ["No completed files loaded.", "", ""]);
    tbody.appendChild(tr);
    return;
  }
  recent.forEach((row) => {
    const title = String(row.lookup_title || row.output_file || row.output_path || "—");
    const shortTitle = title.length > 48 ? "…" + title.slice(-47) : title;
    const route = String(row.route_name || row.mode || "—");
    const finished = String(row.completed_at || row.manifest_recorded_at || "—");
    const tr = document.createElement("tr");
    if (typeof appendCells === "function") appendCells(tr, [shortTitle, route, finished]);
    const firstCell = tr.cells[0];
    if (firstCell) firstCell.title = title;
    tbody.appendChild(tr);
  });
}

// ── SETTINGS TAB NAV — Stage 13 ─────────────────────────────────────────────

function initSettingsTabNav() {
  const STORAGE_KEY = "mediapipeline-settings-tab";
  const page = document.querySelector('[data-page-panel="settings"]');
  if (!page) return;
  const btns = Array.from(page.querySelectorAll(".settings-tab-btn[data-settings-tab]"));
  const panes = Array.from(page.querySelectorAll(".settings-tab-pane[data-settings-tab]"));
  if (!btns.length || !panes.length) return;

  function activateTab(tabId) {
    btns.forEach((b) => {
      const active = b.dataset.settingsTab === tabId;
      b.setAttribute("aria-selected", String(active));
    });
    panes.forEach((p) => {
      p.classList.toggle("is-active", p.dataset.settingsTab === tabId);
    });
    try { localStorage.setItem(STORAGE_KEY, tabId); } catch (_) {}
    updatePagePanelEmptyStates();
  }

  btns.forEach((btn) => {
    btn.addEventListener("click", () => activateTab(btn.dataset.settingsTab));
  });

  let stored = "status";
  try { stored = localStorage.getItem(STORAGE_KEY) || "status"; } catch (_) {}
  // Validate stored value is a real tab, fall back to status
  if (!btns.some((b) => b.dataset.settingsTab === stored)) stored = "status";
  activateTab(stored);
}

// ── DIAGNOSTICS TAB NAV — Stage 14 ───────────────────────────────────────────

function initDiagnosticsTabNav() {
  const STORAGE_KEY = "mediapipeline-diag-tab";
  const page = document.querySelector('[data-page-panel="diagnostics"]');
  if (!page) return;
  const btns = Array.from(page.querySelectorAll(".settings-tab-btn[data-diag-tab]"));
  const panes = Array.from(page.querySelectorAll(".settings-tab-pane[data-diag-tab]"));
  if (!btns.length || !panes.length) return;

  function activateTab(tabId) {
    btns.forEach((b) => {
      const active = b.dataset.diagTab === tabId;
      b.setAttribute("aria-selected", String(active));
    });
    panes.forEach((p) => {
      p.classList.toggle("is-active", p.dataset.diagTab === tabId);
    });
    try { localStorage.setItem(STORAGE_KEY, tabId); } catch (_) {}
    updatePagePanelEmptyStates();
  }

  btns.forEach((btn) => {
    btn.addEventListener("click", () => activateTab(btn.dataset.diagTab));
  });

  let stored = "logs";
  try { stored = localStorage.getItem(STORAGE_KEY) || "logs"; } catch (_) {}
  // Validate stored value is a real tab, fall back to logs.
  if (!btns.some((b) => b.dataset.diagTab === stored)) stored = "logs";
  activateTab(stored);
}

// ── COMPLETED TAB NAV — Stage 15 ─────────────────────────────────────────────

function initCompletedTabNav() {
  const STORAGE_KEY = "mediapipeline-completed-tab";
  const page = document.querySelector('[data-page-panel="completed"]');
  if (!page) return;
  const btns = Array.from(page.querySelectorAll(".settings-tab-btn[data-completed-tab]"));
  const panes = Array.from(page.querySelectorAll(".settings-tab-pane[data-completed-tab]"));
  if (!btns.length || !panes.length) return;

  function activateTab(tabId) {
    btns.forEach((b) => {
      const active = b.dataset.completedTab === tabId;
      b.setAttribute("aria-selected", String(active));
    });
    panes.forEach((p) => {
      p.classList.toggle("is-active", p.dataset.completedTab === tabId);
    });
    try { localStorage.setItem(STORAGE_KEY, tabId); } catch (_) {}
    updatePagePanelEmptyStates();
  }

  btns.forEach((btn) => {
    btn.addEventListener("click", () => activateTab(btn.dataset.completedTab));
  });

  let stored = "overview";
  try { stored = localStorage.getItem(STORAGE_KEY) || "overview"; } catch (_) {}
  // Validate stored value is a real tab, fall back to overview
  if (!btns.some((b) => b.dataset.completedTab === stored)) stored = "overview";
  activateTab(stored);
}

function initNavigation() {
  const buttons = Array.from(document.querySelectorAll(".nav-button"));
  buttons.forEach((button) => {
    button.addEventListener("click", () => {
      showPage(button.dataset.page);
    });
  });
  document.querySelectorAll("[data-cross-page-target]").forEach((button) => {
    button.addEventListener("click", () => showPage(button.dataset.crossPageTarget));
  });
  // S15: topbar health badges → click navigates to Diagnostics
  const refreshHealthBadge = byId("refresh-health");
  if (refreshHealthBadge) refreshHealthBadge.addEventListener("click", () => showPage("diagnostics"));
  const closeReadinessBadge = byId("close-readiness");
  if (closeReadinessBadge) closeReadinessBadge.addEventListener("click", () => showPage("diagnostics"));
}

function initAdvancedToggle() {
  const STORAGE_KEY = "mediapipeline-advanced-mode";
  const btn = byId("advanced-toggle");
  if (!btn) return;

  function applyAdvancedMode(on) {
    document.body.classList.toggle("advanced-mode", on);
    btn.setAttribute("aria-pressed", String(on));
    btn.dataset.state = on ? "on" : "off";
    try { localStorage.setItem(STORAGE_KEY, on ? "1" : "0"); } catch (_) {}
    updatePagePanelEmptyStates();
  }

  // Restore persisted preference — operators who turn this on stay in advanced
  // mode across reloads without having to toggle it every session.
  let stored = false;
  try { stored = localStorage.getItem(STORAGE_KEY) === "1"; } catch (_) {}
  applyAdvancedMode(stored);

  btn.addEventListener("click", () => {
    applyAdvancedMode(!document.body.classList.contains("advanced-mode"));
  });
}

function initEvidenceToggle() {
  const STORAGE_KEY = "mediapipeline-evidence-hidden";
  const btn = byId("evidence-toggle");
  if (!btn) return;

  function applyEvidenceHidden(hidden) {
    document.body.classList.toggle("evidence-hidden", hidden);
    btn.setAttribute("aria-pressed", String(hidden));
    btn.dataset.state = hidden ? "on" : "off";
    btn.textContent = hidden ? "Show Evidence" : "Hide Evidence";
    btn.title = hidden
      ? "Show read-only evidence panels again."
      : "Hide panels marked as read-only evidence. Interactive controls remain visible.";
    try { localStorage.setItem(STORAGE_KEY, hidden ? "1" : "0"); } catch (_) {}
    updatePagePanelEmptyStates();
  }

  let stored = false;
  try { stored = localStorage.getItem(STORAGE_KEY) === "1"; } catch (_) {}
  applyEvidenceHidden(stored);

  btn.addEventListener("click", () => {
    applyEvidenceHidden(!document.body.classList.contains("evidence-hidden"));
  });
}

// ── PIPELINE SPARKLINE — S45 ─────────────────────────────────────────────────
// Renders the last 20 pipeline events as coloured 8×8 px squares inside
// #pipeline-sparkline. Oldest event is on the left, newest on the right.
// event_type/type strings are classified into 5 visual categories:
//   success  — completed / done / accepted / ok / published / passed
//   active   — processing / encoding / remuxing / copying / auditing / running
//   failed   — failed / error / failure / blocked / rejected
//   warning  — paused / stopped / skipped / stale / warning / unknown
//   skip     — skip / idle / heartbeat / ping (structural noise, shown grey)

function sparkKind(event) {
  const t = String(event.event_type || event.type || event.Status || event.status || event || "").toLowerCase();
  if (/complet|done|accept|success|ok\b|publish|pass/.test(t))       return "success";
  if (/process|encod|remux|copy|audit|running|active|launch/.test(t)) return "active";
  if (/fail|error|block|reject/.test(t))                             return "failed";
  if (/pause|stop|skip|stale|warn|unknown/.test(t))                  return "warning";
  return "skip";
}

function renderSparkline(events) {
  const el = byId("pipeline-sparkline");
  if (!el) return;
  const items = Array.isArray(events) ? events.slice(-20) : [];
  if (!items.length) { el.replaceChildren(); return; }
  el.replaceChildren();
  items.forEach((ev) => {
    const sq = document.createElement("span");
    sq.className = "spark";
    sq.dataset.kind = sparkKind(ev);
    sq.title = String(ev.event_type || ev.type || "event");
    el.appendChild(sq);
  });
}

// ── LAUNCH EVIDENCE COLLAPSE — S3 ────────────────────────────────────────────
// The "Settings Check" evidence panel on the Launch page can be collapsed so
// the operator sees only the heading status and the Start Pipeline section,
// without scrolling past all the evidence sub-panels.
//
// The #launch-evidence-body div (see index.html) gets .is-collapsed toggled.
// State persists to localStorage so operators who prefer collapsed stay collapsed.

function initLaunchEvidenceToggle() {
  const STORAGE_KEY = "mediapipeline-launch-evidence-expanded";
  const body = byId("launch-evidence-body");
  const btn  = byId("launch-evidence-toggle");
  if (!body || !btn) return;

  function applyCollapsed(collapsed) {
    body.classList.toggle("is-collapsed", collapsed);
    btn.textContent = collapsed ? "Expand" : "Collapse";
    btn.setAttribute("aria-expanded", String(!collapsed));
    try { localStorage.setItem(STORAGE_KEY, collapsed ? "0" : "1"); } catch (_) {}
  }

  // Restore persisted preference (default: expanded)
  let stored = true;
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (raw !== null) stored = raw === "1";
  } catch (_) {}
  applyCollapsed(!stored);

  btn.addEventListener("click", () => applyCollapsed(!body.classList.contains("is-collapsed")));
}

// ── KEYBOARD SHORTCUTS — S46 ─────────────────────────────────────────────────
// Global keyboard shortcuts that activate only when focus is NOT in a text
// field, select, textarea, or contenteditable element.
//
//   R          Refresh all panels
//   A          Toggle Advanced mode
//   T          Toggle Light / Dark theme
//   1–9        Navigate to page (Home, Queue, Completed, Pending, Launch,
//              Reports, Diagnostics, Settings, Maintenance)
//   ?          Show / hide this shortcut reference overlay

function initKeyboardShortcuts() {
  const PAGE_KEYS = {
    "1": "home",
    "2": "queue",
    "3": "completed",
    "4": "pending",
    "5": "launch",
    "6": "reports",
    "7": "diagnostics",
    "8": "settings",
    "9": "maintenance",
  };

  const HELP_TEXT = [
    "Keyboard shortcuts",
    "──────────────────",
    "  R  Refresh",
    "  A  Toggle Advanced mode",
    "  T  Toggle Light / Dark theme",
    "  1  Home",
    "  2  Queue",
    "  3  Completed",
    "  4  Pending Publish",
    "  5  Launch",
    "  6  Reports",
    "  7  Diagnostics",
    "  8  Settings",
    "  9  Maintenance",
    "  ?  Show / hide this overlay",
  ].join("\n");

  let helpEl = null;

  function toggleHelp() {
    if (helpEl) {
      helpEl.remove();
      helpEl = null;
      return;
    }
    helpEl = document.createElement("div");
    helpEl.className = "keyboard-shortcut-help";
    helpEl.setAttribute("role", "dialog");
    helpEl.setAttribute("aria-label", "Keyboard shortcuts");
    helpEl.textContent = HELP_TEXT;
    document.body.appendChild(helpEl);
    // Auto-dismiss after 6 s so it never blocks the operator permanently
    window.setTimeout(() => {
      if (helpEl) {
        helpEl.remove();
        helpEl = null;
      }
    }, 6000);
  }

  document.addEventListener("keydown", (e) => {
    // Never fire shortcuts while typing
    const tag = e.target ? String(e.target.tagName || "").toUpperCase() : "";
    if (["INPUT", "TEXTAREA", "SELECT"].includes(tag) || e.target.isContentEditable) return;
    // Never intercept modifier combos (browser / OS commands)
    if (e.ctrlKey || e.altKey || e.metaKey) return;

    switch (e.key) {
      case "r":
      case "R":
        e.preventDefault();
        refreshAll();
        break;
      case "a":
      case "A": {
        const advBtn = byId("advanced-toggle");
        if (advBtn) { e.preventDefault(); advBtn.click(); }
        break;
      }
      case "t":
      case "T": {
        const themeBtn = byId("theme-toggle");
        if (themeBtn) { e.preventDefault(); themeBtn.click(); }
        break;
      }
      case "?":
        e.preventDefault();
        toggleHelp();
        break;
      default:
        if (PAGE_KEYS[e.key]) {
          e.preventDefault();
          showPage(PAGE_KEYS[e.key]);
        }
    }
  });
}

// ── S5: COLLAPSIBLE SUMMARIES ─────────────────────────────────────────────────
// For every prose-block <pre> whose immediately-next sibling is a .table-wrap,
// inject a "Show summary / Hide summary" tertiary toggle button before the pre.
// Summary defaults to collapsed so the table is the primary view of each panel.
// Per-summary expand state is persisted to localStorage:
//   key: mediapipeline-summary-<pre id>   value: "1" = expanded, "0" = collapsed
// Elements with no id get no persistence (state resets on reload — acceptable).
// The element stays in the DOM when hidden (pre.hidden = true) so test assertions
// can still read content via #id even when the summary is collapsed.

function initCollapsibleSummaries() {
  document.querySelectorAll("pre.prose-block").forEach((pre) => {
    const next = pre.nextElementSibling;
    if (!next || !next.classList.contains("table-wrap")) return;

    const id = pre.id || "";
    const STORAGE_KEY = id ? `mediapipeline-summary-${id}` : null;

    // Default: collapsed (table first). Restore to expanded only if stored as "1".
    let isExpanded = false;
    if (STORAGE_KEY) {
      try {
        const raw = localStorage.getItem(STORAGE_KEY);
        if (raw === "1") isExpanded = true;
      } catch (_) {}
    }

    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "tertiary-button summary-toggle";
    if (id) btn.setAttribute("aria-controls", id);

    function applyState(expanded) {
      isExpanded = expanded;
      pre.hidden = !expanded;
      btn.textContent = expanded ? "Hide summary" : "Show summary";
      btn.setAttribute("aria-expanded", String(expanded));
      if (STORAGE_KEY) {
        try { localStorage.setItem(STORAGE_KEY, expanded ? "1" : "0"); } catch (_) {}
      }
    }

    btn.addEventListener("click", () => applyState(!isExpanded));
    pre.parentNode.insertBefore(btn, pre);
    applyState(isExpanded);
  });
}

// ── THEME TOGGLE — Stage 15 ───────────────────────────────────────────────────
// Adds/removes body.light-mode class. Persists choice to localStorage.
// On first load (no stored preference) falls back to system prefers-color-scheme.

function initThemeToggle() {
  const STORAGE_KEY = "mediapipeline-theme";
  const btn = byId("theme-toggle");
  if (!btn) return;

  function applyTheme(light) {
    document.body.classList.toggle("light-mode", light);
    btn.textContent = light ? "Dark" : "Light";
    try { localStorage.setItem(STORAGE_KEY, light ? "light" : "dark"); } catch (_) {}
  }

  // Determine initial theme: stored pref → system pref → dark default
  let stored = null;
  try { stored = localStorage.getItem(STORAGE_KEY); } catch (_) {}
  const preferLight = stored
    ? stored === "light"
    : (typeof window.matchMedia === "function" && window.matchMedia("(prefers-color-scheme: light)").matches);
  applyTheme(preferLight);

  btn.addEventListener("click", () => {
    applyTheme(!document.body.classList.contains("light-mode"));
  });
}

window.getLastSnapshot = () => lastSnapshot;

// ── LAYOUT MANAGER — S50 ─────────────────────────────────────────────────────
// Allows per-tab panel reordering (drag-and-drop), per-panel hidden toggle,
// and per-panel Advanced-gate toggle. All state is persisted to localStorage.
//
// Panel identity: derived from the panel's <h2>/<h3> heading text + layout
// container slug so no HTML changes are needed to assign stable keys.
//
// On init the manager flattens div[data-advanced] group wrappers inside each
// managed container into direct panel siblings, recording each panel's original
// advanced status as data-advanced-default. Individual panels that already
// carry data-advanced directly are also promoted to data-panel-advanced.
// After flattening, all visibility is controlled by:
//   [data-panel-advanced]  → hidden unless body.advanced-mode
//   [data-panel-hidden]    → always hidden (operator-set)
//
// Tab panes and sub-section bodies are also normalized into layout containers
// so Settings, Diagnostics, Completed, Launch, Reports, and similar grouped
// boxes can receive their own handles without moving authority into the UI.

const LAYOUT_STORAGE_KEY = "mediapipeline-layout-v1";
const _layoutDragHintTimers = new WeakMap();

function _layoutSlug(text) {
  return String(text || "")
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "");
}

function _panelKey(containerKey, panel) {
  const h = panel.querySelector(".panel-heading h2, .panel-heading h3");
  const label = h ? h.textContent.trim() : "";
  return `${containerKey}::${_layoutSlug(label || "panel")}`;
}

function _layoutPageIdFor(container) {
  const page = container?.classList?.contains("page")
    ? container
    : container?.closest?.(".page[data-page-panel]");
  return page?.dataset?.pagePanel || "page";
}

function _layoutContainerKey(container) {
  if (!container) return "page";
  const pageId = _layoutPageIdFor(container);
  if (container.classList?.contains("page")) return pageId;
  const tabPairs = [
    ["settingsTab", "settings"],
    ["diagTab", "diagnostics"],
    ["completedTab", "completed"],
  ];
  for (const [datasetKey, label] of tabPairs) {
    if (container.dataset?.[datasetKey]) {
      return `${pageId}::${label}-${_layoutSlug(container.dataset[datasetKey])}`;
    }
  }
  if (container.id) return `${pageId}::${_layoutSlug(container.id)}`;
  const parentPanel = container.closest?.("section.panel[data-panel-key]");
  if (parentPanel?.dataset?.panelKey) return `${parentPanel.dataset.panelKey}::subsections`;
  return `${pageId}::container-${_layoutSlug(container.className || "subsections")}`;
}

function _loadLayout() {
  try { return JSON.parse(localStorage.getItem(LAYOUT_STORAGE_KEY) || "{}"); } catch (_) { return {}; }
}

function _saveLayout(state) {
  try { localStorage.setItem(LAYOUT_STORAGE_KEY, JSON.stringify(state)); } catch (_) {}
}

function _updateCustomizeBar(panel) {
  const bar = panel.querySelector(".panel-customize-bar");
  if (!bar) return;
  const btnAdv = bar.querySelector(".pcb-btn-advanced");
  const btnHid = bar.querySelector(".pcb-btn-hidden");
  const isAdv = panel.hasAttribute("data-panel-advanced");
  const isHid = panel.hasAttribute("data-panel-hidden");
  if (btnAdv) {
    btnAdv.setAttribute("aria-pressed", String(isAdv));
    btnAdv.dataset.state = isAdv ? "on" : "off";
    btnAdv.title = isAdv
      ? "Panel is behind the Advanced gate — click to make always visible"
      : "Click to move panel behind the Advanced gate";
  }
  if (btnHid) {
    btnHid.setAttribute("aria-pressed", String(isHid));
    btnHid.dataset.state = isHid ? "on" : "off";
    btnHid.title = isHid
      ? "Panel is hidden — click to restore visibility"
      : "Click to hide this panel";
  }
}

function _injectCustomizeBar(panel, title) {
  if (panel.querySelector(".panel-customize-bar")) return;
  const bar = document.createElement("div");
  bar.className = "panel-customize-bar";
  bar.setAttribute("aria-hidden", "true");

  const handle = document.createElement("span");
  handle.className = "pcb-drag-handle";
  handle.textContent = "⠿";
  handle.title = "Drag to reorder";

  const nameEl = document.createElement("span");
  nameEl.className = "pcb-panel-name";
  nameEl.textContent = title || "Panel";

  const actions = document.createElement("div");
  actions.className = "pcb-actions";

  const btnAdv = document.createElement("button");
  btnAdv.type = "button";
  btnAdv.className = "pcb-btn-advanced";
  btnAdv.textContent = "Advanced";
  btnAdv.setAttribute("aria-pressed", "false");

  const btnHid = document.createElement("button");
  btnHid.type = "button";
  btnHid.className = "pcb-btn-hidden";
  btnHid.textContent = "Hidden";
  btnHid.setAttribute("aria-pressed", "false");

  actions.appendChild(btnAdv);
  actions.appendChild(btnHid);
  bar.appendChild(handle);
  bar.appendChild(nameEl);
  bar.appendChild(actions);

  // Insert bar as the very first child of the panel so it sits above all content.
  panel.insertBefore(bar, panel.firstChild);

  _updateCustomizeBar(panel);
}

function _showLayoutDragHint(panel) {
  const bar = panel.querySelector(".panel-customize-bar");
  if (!bar) return;
  let hint = bar.querySelector(".layout-drag-hint");
  if (!hint) {
    hint = document.createElement("span");
    hint.className = "layout-drag-hint";
    bar.appendChild(hint);
  }
  hint.textContent = "Still gated. Click Advanced to make this panel always visible.";
  panel.classList.add("panel-drag-hint-active");
  const oldTimer = _layoutDragHintTimers.get(panel);
  if (oldTimer) clearTimeout(oldTimer);
  const timer = setTimeout(() => {
    panel.classList.remove("panel-drag-hint-active");
    const currentHint = bar.querySelector(".layout-drag-hint");
    if (currentHint) currentHint.remove();
    _layoutDragHintTimers.delete(panel);
  }, 3500);
  _layoutDragHintTimers.set(panel, timer);
}

// ── DnD state ────────────────────────────────────────────────────────────────
let _dndSrc = null;
let _dndContainer = null;

function _onDragStart(e) {
  // Only allow drag to start from the handle element.
  const handle = this.querySelector(".pcb-drag-handle");
  if (!handle || !handle.contains(e.target)) {
    e.preventDefault();
    return;
  }
  _dndSrc = this;
  _dndContainer = this.parentElement;
  if (this.hasAttribute("data-panel-advanced")) _showLayoutDragHint(this);
  this.classList.add("panel-dragging");
  e.dataTransfer.effectAllowed = "move";
  e.dataTransfer.setData("text/plain", this.dataset.panelKey || "");
}

function _onDragOver(e) {
  if (!_dndSrc || _dndSrc === this) return;
  if (this.parentElement !== _dndContainer) return;
  e.preventDefault();
  e.dataTransfer.dropEffect = "move";
  const rect = this.getBoundingClientRect();
  const above = e.clientY < rect.top + rect.height / 2;
  this.classList.toggle("panel-drop-above", above);
  this.classList.toggle("panel-drop-below", !above);
}

function _onDragLeave() {
  this.classList.remove("panel-drop-above", "panel-drop-below");
}

function _onDrop(e) {
  if (!_dndSrc || _dndSrc === this) return;
  if (this.parentElement !== _dndContainer) return;
  e.preventDefault();
  this.classList.remove("panel-drop-above", "panel-drop-below");
  const rect = this.getBoundingClientRect();
  const above = e.clientY < rect.top + rect.height / 2;
  if (above) {
    this.parentNode.insertBefore(_dndSrc, this);
  } else {
    this.parentNode.insertBefore(_dndSrc, this.nextSibling);
  }
  _savePanelOrder(_dndContainer);
}

function _onDragEnd() {
  this.classList.remove("panel-dragging");
  document.querySelectorAll(".panel-drop-above, .panel-drop-below").forEach((el) => {
    el.classList.remove("panel-drop-above", "panel-drop-below");
  });
  _dndSrc = null;
  _dndContainer = null;
}

function _savePanelOrder(container) {
  if (!container) return;
  const containerKey = _layoutContainerKey(container);
  const panels = Array.from(container.querySelectorAll(":scope > section.panel[data-panel-key]"));
  const state = _loadLayout();
  state[`__order__${containerKey}`] = panels.map((p) => p.dataset.panelKey || "");
  _saveLayout(state);
}

// ── Per-panel toggle handlers ─────────────────────────────────────────────────
function _togglePanelAdvanced(panel) {
  const key = panel.dataset.panelKey;
  const wasAdv = panel.hasAttribute("data-panel-advanced");
  const state = _loadLayout();
  if (!state[key]) state[key] = {};
  state[key].advanced = !wasAdv;
  _saveLayout(state);
  panel.toggleAttribute("data-panel-advanced", !wasAdv);
  if (wasAdv) {
    panel.classList.remove("panel-drag-hint-active");
    const hint = panel.querySelector(".layout-drag-hint");
    if (hint) hint.remove();
  }
  _updateCustomizeBar(panel);
  updatePagePanelEmptyStates();
}

function _togglePanelHidden(panel) {
  const key = panel.dataset.panelKey;
  const wasHid = panel.hasAttribute("data-panel-hidden");
  const state = _loadLayout();
  if (!state[key]) state[key] = {};
  state[key].hidden = !wasHid;
  _saveLayout(state);
  panel.toggleAttribute("data-panel-hidden", !wasHid);
  _updateCustomizeBar(panel);
  updatePagePanelEmptyStates();
}

// ── Init helpers ──────────────────────────────────────────────────────────────
function _layoutNodeHasContent(node) {
  if (!node) return false;
  if (node.nodeType === 3) return Boolean(String(node.textContent || "").trim());
  if (node.nodeType === 1) return true;
  return false;
}

function _layoutPanelTitleFromHeading(heading, fallback = "Panel") {
  const h = heading?.querySelector?.("h2, h3");
  return (h?.textContent || fallback).trim() || fallback;
}

function _layoutPaneTitle(container) {
  const page = container.closest?.(".page[data-page-panel]");
  const pairs = [
    ["settingsTab", "settingsTab"],
    ["diagTab", "diagTab"],
    ["completedTab", "completedTab"],
  ];
  for (const [paneKey, buttonKey] of pairs) {
    const tab = container.dataset?.[paneKey];
    if (!tab || !page) continue;
    const button = page.querySelector(`.settings-tab-btn[data-${buttonKey.replace(/[A-Z]/g, (m) => `-${m.toLowerCase()}`)}="${tab}"]`);
    const label = button?.textContent?.trim();
    if (label) return label;
  }
  return "Summary";
}

function _layoutMakeHeading(title, statusId = "") {
  const heading = document.createElement("div");
  heading.className = "panel-heading";
  const h = document.createElement("h2");
  h.textContent = title || "Summary";
  heading.appendChild(h);
  if (statusId) {
    const status = document.createElement("strong");
    status.id = statusId;
    heading.appendChild(status);
  }
  return heading;
}

function _layoutInferPanelType(nodes) {
  return nodes.some((node) => (
    node.nodeType === 1
    && (
      node.matches?.("button, input, select, textarea")
      || node.querySelector?.("button, input, select, textarea")
    )
  )) ? "interactive" : "evidence";
}

function _copyPanelContextAttributes(source, target) {
  if (!source || !target) return;
  ["launch-tab-panel", "reports-tab-panel"].forEach((className) => {
    if (source.classList?.contains(className)) target.classList.add(className);
  });
  [
    "launchTabPanel",
    "reportsTabPanel",
    "evidenceToggleExempt",
  ].forEach((key) => {
    if (source.dataset?.[key] !== undefined) target.dataset[key] = source.dataset[key];
  });
}

function _createLayoutGeneratedPanel(nodes, options = {}) {
  const panel = document.createElement("section");
  panel.className = "panel";
  panel.dataset.layoutGeneratedPanel = "true";
  panel.dataset.panelType = options.panelType || _layoutInferPanelType(nodes);
  if (options.advanced) panel.setAttribute("data-advanced", "");
  if (options.sourcePanel) _copyPanelContextAttributes(options.sourcePanel, panel);
  if (options.syntheticHeading) panel.appendChild(_layoutMakeHeading(options.title || "Summary"));
  nodes.forEach((node) => panel.appendChild(node));
  return panel;
}

function _extractLooseGroups(nodes, defaultTitle, advanced = false) {
  const groups = [];
  let current = null;
  nodes.forEach((node) => {
    if (!_layoutNodeHasContent(node)) return;
    if (node.nodeType === 1 && node.matches("div[data-advanced]")) {
      const advancedGroups = _extractLooseGroups(Array.from(node.childNodes), defaultTitle, true);
      groups.push(...advancedGroups);
      node.remove();
      current = null;
      return;
    }
    if (node.nodeType === 1 && node.matches(".panel-heading.panel-subheading")) {
      current = {
        title: _layoutPanelTitleFromHeading(node, defaultTitle),
        nodes: [node],
        advanced,
        syntheticHeading: false,
      };
      groups.push(current);
      return;
    }
    if (!current) {
      current = {
        title: defaultTitle,
        nodes: [],
        advanced,
        syntheticHeading: true,
      };
      groups.push(current);
    }
    current.nodes.push(node);
  });
  return groups.filter((group) => group.nodes.some(_layoutNodeHasContent));
}

function _splitLooseContentIntoPanels(container) {
  if (!container || container.dataset.layoutLoosePanelsReady === "true") return;
  if (container.classList?.contains("page")) return;
  if (container.querySelector(":scope > section.panel")) return;
  const nodes = Array.from(container.childNodes);
  if (!nodes.some(_layoutNodeHasContent)) return;
  const hasPanelishHeading = nodes.some((node) => (
    node.nodeType === 1
    && (
      node.matches(".panel-heading.panel-subheading")
      || (node.matches("div[data-advanced]") && node.querySelector(":scope > .panel-heading.panel-subheading"))
    )
  ));
  const isKnownTabPane = container.matches?.(".settings-tab-pane[data-settings-tab], .settings-tab-pane[data-diag-tab], .settings-tab-pane[data-completed-tab]");
  if (!hasPanelishHeading && !isKnownTabPane) return;
  const defaultTitle = _layoutPaneTitle(container);
  const groups = _extractLooseGroups(nodes, defaultTitle, false);
  groups.forEach((group) => {
    container.appendChild(_createLayoutGeneratedPanel(group.nodes, {
      title: group.title,
      advanced: group.advanced,
      syntheticHeading: group.syntheticHeading,
    }));
  });
  container.dataset.layoutLoosePanelsReady = "true";
}

function _splitDirectPanelSubsections(container) {
  if (!container) return;
  Array.from(container.querySelectorAll(":scope > section.panel")).forEach((panel) => {
    if (panel.dataset.layoutSubsectionsReady === "true" || panel.dataset.layoutGeneratedPanel === "true") return;
    const directNodes = Array.from(panel.childNodes);
    const groups = [];
    let current = null;
    directNodes.forEach((node) => {
      if (!_layoutNodeHasContent(node)) return;
      if (node.nodeType === 1 && node.matches("div[data-advanced]")) {
        const advancedGroups = _extractLooseGroups(Array.from(node.childNodes), "Advanced", true);
        groups.push(...advancedGroups);
        node.remove();
        current = null;
        return;
      }
      if (node.nodeType === 1 && node.matches(".panel-heading.panel-subheading")) {
        current = {
          title: _layoutPanelTitleFromHeading(node, "Detail"),
          nodes: [node],
          advanced: false,
          syntheticHeading: false,
        };
        groups.push(current);
        return;
      }
      if (current) current.nodes.push(node);
    });
    if (!groups.length) {
      panel.dataset.layoutSubsectionsReady = "true";
      return;
    }
    let insertAfter = panel;
    groups.forEach((group) => {
      const generated = _createLayoutGeneratedPanel(group.nodes, {
        title: group.title,
        advanced: group.advanced,
        syntheticHeading: group.syntheticHeading,
        sourcePanel: panel,
      });
      insertAfter.parentNode.insertBefore(generated, insertAfter.nextSibling);
      insertAfter = generated;
    });
    panel.dataset.layoutSubsectionsReady = "true";
  });
}

function _flattenAdvancedWrappers(container) {
  Array.from(container.querySelectorAll(":scope > div[data-advanced]")).forEach((wrapper) => {
    Array.from(wrapper.querySelectorAll(":scope > section.panel")).forEach((p) => {
      p.dataset.advancedDefault = "true";
      wrapper.parentNode.insertBefore(p, wrapper);
    });
    if (wrapper.children.length === 0) wrapper.remove();
  });
  Array.from(container.querySelectorAll(":scope > section.panel[data-advanced]")).forEach((p) => {
    p.dataset.advancedDefault = "true";
    p.removeAttribute("data-advanced");
  });
}

function _applyStoredPanelState(panel, panelState) {
  const defaultAdv = panel.dataset.advancedDefault === "true";
  const isAdv = panelState.advanced !== undefined ? Boolean(panelState.advanced) : defaultAdv;
  panel.toggleAttribute("data-panel-advanced", isAdv);
  panel.toggleAttribute("data-panel-hidden", Boolean(panelState.hidden));
}

function _panelKeys(panels) {
  return panels.map((p) => p.dataset.panelKey || "").filter(Boolean);
}

function _storedOrderMatchesCurrentPanels(storedOrder, currentKeys) {
  if (!Array.isArray(storedOrder) || storedOrder.length === 0) return true;
  const storedKeys = storedOrder.filter(Boolean);
  if (storedKeys.length !== currentKeys.length) return false;
  const currentSet = new Set(currentKeys);
  const storedSet = new Set(storedKeys);
  return storedSet.size === currentSet.size && storedKeys.every((key) => currentSet.has(key));
}

function _applyStoredOrder(container, allPanels, state) {
  const containerKey = _layoutContainerKey(container);
  const storedOrder = state[`__order__${containerKey}`];
  if (!Array.isArray(storedOrder) || storedOrder.length === 0) return;
  const currentKeys = _panelKeys(allPanels);
  if (!_storedOrderMatchesCurrentPanels(storedOrder, currentKeys)) {
    // A page schema changed: keep hidden/advanced panel state, but reset order so
    // newly added panels appear at their authored default position instead of
    // being appended below every stored panel.
    state[`__order__${containerKey}`] = currentKeys;
    _saveLayout(state);
    container.dataset.layoutOrderStatus = "schema-reset";
    const page = container.closest?.(".page[data-page-panel]");
    if (page) page.dataset.layoutOrderStatus = "schema-reset";
    return;
  }
  const panelMap = new Map(allPanels.map((p) => [p.dataset.panelKey, p]));
  const known = storedOrder.filter((k) => panelMap.has(k));
  const extra = allPanels
    .map((p) => p.dataset.panelKey)
    .filter((k) => !known.includes(k));
  [...known, ...extra].forEach((k) => {
    const p = panelMap.get(k);
    if (p) container.appendChild(p);
  });
}

function _initLayoutContainer(container, state) {
  const containerKey = _layoutContainerKey(container);

  _splitLooseContentIntoPanels(container);
  _flattenAdvancedWrappers(container);
  _splitDirectPanelSubsections(container);
  _flattenAdvancedWrappers(container);

  // Dedup map: if two panels on the same page share an identical h2 (key
  // collision), the second gets a "-2" suffix, the third "-3", and so on.
  // This prevents silent localStorage corruption without requiring any HTML changes.
  const _keySeen = new Map();

  const panels = Array.from(container.querySelectorAll(":scope > section.panel"));
  panels.forEach((panel) => {
    let key = _panelKey(containerKey, panel);
    const seen = (_keySeen.get(key) || 0) + 1;
    _keySeen.set(key, seen);
    if (seen > 1) key = `${key}-${seen}`;
    panel.dataset.panelKey = key;
    const h = panel.querySelector(".panel-heading h2, .panel-heading h3");
    const title = h ? h.textContent.trim() : key.split("::")[1] || "Panel";
    _applyStoredPanelState(panel, state[key] || {});
    _injectCustomizeBar(panel, title);

    // Wire per-panel button clicks inside the bar.
    const bar = panel.querySelector(".panel-customize-bar");
    if (bar) {
      const btnAdv = bar.querySelector(".pcb-btn-advanced");
      if (btnAdv) btnAdv.addEventListener("click", () => _togglePanelAdvanced(panel));
      const btnHid = bar.querySelector(".pcb-btn-hidden");
      if (btnHid) btnHid.addEventListener("click", () => _togglePanelHidden(panel));
    }

    // DnD listeners — active only when draggable attr is set.
    panel.addEventListener("dragstart", _onDragStart);
    panel.addEventListener("dragover", _onDragOver);
    panel.addEventListener("dragleave", _onDragLeave);
    panel.addEventListener("drop", _onDrop);
    panel.addEventListener("dragend", _onDragEnd);
  });

  _applyStoredOrder(container, panels, state);
}

function _layoutManagedContainers(page) {
  const containers = [];
  const seen = new Set();
  function add(container) {
    if (!container || seen.has(container)) return;
    seen.add(container);
    containers.push(container);
  }
  add(page);
  page.querySelectorAll(
    ".settings-tab-pane[data-settings-tab], .settings-tab-pane[data-diag-tab], .settings-tab-pane[data-completed-tab]"
  ).forEach(add);
  page.querySelectorAll("section.panel > div").forEach((node) => {
    if (node.querySelector(":scope > .panel-heading.panel-subheading")) add(node);
  });
  return containers;
}

function _initPageLayout(page, state) {
  _layoutManagedContainers(page).forEach((container) => _initLayoutContainer(container, state));
}

// ── Main entry point ──────────────────────────────────────────────────────────
function initLayoutManager() {
  const state = _loadLayout();
  document.querySelectorAll(".page[data-page-panel]").forEach((page) => {
    _initPageLayout(page, state);
  });

  // ── Customize toggle ──
  const customizeBtn = byId("customize-layout-btn");
  const resetBtn = byId("reset-layout-btn");

  function enterCustomize() {
    document.body.classList.add("layout-customize-mode");
    if (customizeBtn) {
      customizeBtn.setAttribute("aria-pressed", "true");
      customizeBtn.dataset.state = "on";
      customizeBtn.textContent = "Done";
    }
    // Enable draggable on all managed panels, including subtab and subsection boxes.
    document.querySelectorAll("section.panel[data-panel-key]").forEach((p) => {
      p.setAttribute("draggable", "true");
    });
    updatePagePanelEmptyStates();
  }

  function exitCustomize() {
    document.body.classList.remove("layout-customize-mode");
    if (customizeBtn) {
      customizeBtn.setAttribute("aria-pressed", "false");
      customizeBtn.dataset.state = "off";
      customizeBtn.textContent = "Customize";
    }
    document.querySelectorAll("section.panel[data-panel-key]").forEach((p) => {
      p.removeAttribute("draggable");
      p.classList.remove("panel-dragging", "panel-drop-above", "panel-drop-below");
    });
    updatePagePanelEmptyStates();
  }

  if (customizeBtn) {
    customizeBtn.addEventListener("click", () => {
      const active = document.body.classList.contains("layout-customize-mode");
      if (active) exitCustomize(); else enterCustomize();
    });
  }

  // ── Reset button — two-step inline confirm (no window.confirm) ──
  // First click: arms the button (label → "Confirm Reset?", pulsing border).
  // Auto-disarms after 3 s if not confirmed.
  // Second click within 3 s: executes the reset.
  // Before reloading, checks closeReadinessRequiresWarning() to catch
  // unsaved Rename / Settings / Launch changes; if active, shows an inline
  // warning note and requires a third click to proceed anyway.
  if (resetBtn) {
    let _resetArmed = false;
    let _resetTimer = null;
    let _resetForced = false;

    function _disarmReset() {
      _resetArmed = false;
      _resetForced = false;
      clearTimeout(_resetTimer);
      _resetTimer = null;
      resetBtn.textContent = "Reset Layout";
      resetBtn.dataset.state = "idle";
      const warn = byId("layout-reset-warning");
      if (warn) warn.remove();
    }

    resetBtn.addEventListener("click", () => {
      if (!_resetArmed) {
        // First click — arm
        _resetArmed = true;
        resetBtn.textContent = "Confirm Reset?";
        resetBtn.dataset.state = "armed";
        _resetTimer = setTimeout(_disarmReset, 3000);
        return;
      }

      // Second+ click — check for unsaved page state
      const hasUnsaved = typeof closeReadinessRequiresWarning === "function"
        && closeReadinessRequiresWarning();

      if (hasUnsaved && !_resetForced) {
        // Show an inline note in the topbar asking them to confirm once more
        _resetForced = true;
        resetBtn.textContent = "Reset Anyway?";
        resetBtn.dataset.state = "forced";
        // Inject a small warning note below the topbar if not already there
        if (!byId("layout-reset-warning")) {
          const note = document.createElement("div");
          note.id = "layout-reset-warning";
          note.className = "layout-reset-warning-note";
          note.textContent = "⚠ You have unsaved changes. Click “Reset Anyway?” once more to discard them and reload.";
          const topbar = document.querySelector(".topbar");
          if (topbar) topbar.insertAdjacentElement("afterend", note);
        }
        // Still auto-disarm after 3 more seconds
        clearTimeout(_resetTimer);
        _resetTimer = setTimeout(_disarmReset, 3000);
        return;
      }

      // Confirmed — execute reset
      _disarmReset();
      try { localStorage.removeItem(LAYOUT_STORAGE_KEY); } catch (_) {}
      exitCustomize();
      location.reload();
    });
  }
}

document.addEventListener("DOMContentLoaded", () => {
  renderBrandVersion();
  initNavigation();
  initLayoutManager();
  initAdvancedToggle();
  initEvidenceToggle();
  initThemeToggle();
  initLaunchEvidenceToggle();
  initKeyboardShortcuts();
  initCollapsibleSummaries();
  initSettingsTabNav();
  initDiagnosticsTabNav();
  initCompletedTabNav();
  applyDefaultActionTooltips();
  window.addEventListener("mediapipeline:backend-lifecycle", handleTauriBackendLifecycleEvent);
  window.addEventListener("beforeunload", (event) => {
    if (!closeReadinessRequiresWarning()) return;
    const message = closeReadinessWarningMessage();
    event.preventDefault();
    event.returnValue = message;
    return message;
  });
  const refreshButton = byId("refresh-button");
  if (refreshButton) refreshButton.addEventListener("click", refreshAll);
  const homeRefreshButton = byId("home-refresh-button");
  if (homeRefreshButton) homeRefreshButton.addEventListener("click", refreshAll);
  const backendShutdownButton = byId("backend-shutdown-button");
  if (backendShutdownButton) backendShutdownButton.addEventListener("click", requestBackendShutdown);
  const renamePreviewButton = byId("rename-preview-button");
  if (renamePreviewButton) renamePreviewButton.addEventListener("click", refreshRenamePreview);
  const renamePreviewTopButton = byId("rename-preview-top-button");
  if (renamePreviewTopButton) renamePreviewTopButton.addEventListener("click", refreshRenamePreview);
  const renameUseSelectedQueueButton = byId("rename-use-selected-queue-button");
  if (renameUseSelectedQueueButton) renameUseSelectedQueueButton.addEventListener("click", () => window.mediaPipelineRenameView?.useSelectedQueueRowForRename?.());
  const renameUseLoadedQueueButton = byId("rename-use-loaded-queue-button");
  if (renameUseLoadedQueueButton) renameUseLoadedQueueButton.addEventListener("click", () => window.mediaPipelineRenameView?.useLoadedQueueRowsForRename?.());
  const renameBrowseFilesButton = byId("rename-browse-files-button");
  if (renameBrowseFilesButton) renameBrowseFilesButton.addEventListener("click", () => window.mediaPipelineRenameView?.browseRenamePaths?.("files"));
  const renameBrowseFolderButton = byId("rename-browse-folder-button");
  if (renameBrowseFolderButton) renameBrowseFolderButton.addEventListener("click", () => window.mediaPipelineRenameView?.browseRenamePaths?.("folder"));
  const renameAddPathButton = byId("rename-add-path-button");
  if (renameAddPathButton) renameAddPathButton.addEventListener("click", () => window.mediaPipelineRenameView?.addRenamePathFromInput?.());
  const renameClearPathsButton = byId("rename-clear-paths-button");
  if (renameClearPathsButton) renameClearPathsButton.addEventListener("click", () => window.mediaPipelineRenameView?.clearRenamePaths?.());
  const renameAddPathInput = byId("rename-add-path-input");
  if (renameAddPathInput) {
    renameAddPathInput.addEventListener("input", () => window.mediaPipelineRenameView?.syncRenameCommandButtons?.());
    renameAddPathInput.addEventListener("keydown", (event) => {
      if (event.key !== "Enter") return;
      event.preventDefault();
      window.mediaPipelineRenameView?.addRenamePathFromInput?.();
    });
  }
  const renamePaths = byId("rename-paths");
  if (renamePaths) renamePaths.addEventListener("input", () => {
    window.mediaPipelineRenameView?.renderRenameFileSourceSummary?.();
    window.mediaPipelineRenameView?.syncRenameCommandButtons?.();
  });
  window.mediaPipelineRenameView?.renderRenameFileSourceSummary?.();
  const renameSaveOverrideButton = byId("rename-save-override-button");
  if (renameSaveOverrideButton) renameSaveOverrideButton.addEventListener("click", applyRenameSelectedOverride);
  const renameClearOverrideButton = byId("rename-clear-override-button");
  if (renameClearOverrideButton) renameClearOverrideButton.addEventListener("click", clearRenameSelectedOverride);
  const renameApplySelectedButton = byId("rename-apply-selected-button");
  if (renameApplySelectedButton) renameApplySelectedButton.addEventListener("click", () => window.mediaPipelineRenameView?.applySelectedRename?.());
  const renameCheckApplicableButton = byId("rename-check-applicable-button");
  if (renameCheckApplicableButton) renameCheckApplicableButton.addEventListener("click", checkApplicableRenameRows);
  const renameClearChecksButton = byId("rename-clear-checks-button");
  if (renameClearChecksButton) renameClearChecksButton.addEventListener("click", clearCheckedRenameRows);
  const renameMoveCheckedUpButton = byId("rename-move-checked-up-button");
  if (renameMoveCheckedUpButton) renameMoveCheckedUpButton.addEventListener("click", () => moveCheckedRenamePaths(-1));
  const renameMoveCheckedDownButton = byId("rename-move-checked-down-button");
  if (renameMoveCheckedDownButton) renameMoveCheckedDownButton.addEventListener("click", () => moveCheckedRenamePaths(1));
  const renameNaturalSortButton = byId("rename-natural-sort-button");
  if (renameNaturalSortButton) renameNaturalSortButton.addEventListener("click", naturalSortRenamePaths);
  const renameBulkScope = byId("rename-bulk-scope");
  if (renameBulkScope) renameBulkScope.addEventListener("change", () => {
    renderRenameBulkEditor();
    syncRenameCommandButtons();
  });
  const renameBulkStageButton = byId("rename-bulk-stage-button");
  if (renameBulkStageButton) renameBulkStageButton.addEventListener("click", stageRenameBulkEdit);
  const renameBulkUsePipelineButton = byId("rename-bulk-use-pipeline-button");
  if (renameBulkUsePipelineButton) renameBulkUsePipelineButton.addEventListener("click", usePipelineNamesForRenameScope);
  const renameBulkForceButton = byId("rename-bulk-force-button");
  if (renameBulkForceButton) renameBulkForceButton.addEventListener("click", () => setRenameBulkForce(true));
  const renameBulkClearForceButton = byId("rename-bulk-clear-force-button");
  if (renameBulkClearForceButton) renameBulkClearForceButton.addEventListener("click", () => setRenameBulkForce(false));
  const renameBulkClearButton = byId("rename-bulk-clear-button");
  if (renameBulkClearButton) renameBulkClearButton.addEventListener("click", clearRenameBulkOverrides);
  window.mediaPipelineRenameView?.initRenameCleaningFilterEditorEvents?.();
  initSettingsViewEvents();
  initLaunchViewEvents();
  if (typeof initReportsViewEvents === "function") initReportsViewEvents();
  if (typeof initScheduleViewEvents === "function") initScheduleViewEvents();
  initDiagnosticsViewEvents();
  initNetworkViewEvents();
  initContractViewEvents();
  if (typeof initMaintenanceViewEvents === "function") initMaintenanceViewEvents();
  if (typeof initSampleValidationViewEvents === "function") initSampleValidationViewEvents();
  const pipelineStartButton = byId("pipeline-start-button");
  if (pipelineStartButton) pipelineStartButton.addEventListener("click", startPipelineFromForm);
  const auditStartButton = byId("audit-start-button");
  if (auditStartButton) auditStartButton.addEventListener("click", startAuditFromForm);
  const rerunStartButton = byId("rerun-start-button");
  if (rerunStartButton) rerunStartButton.addEventListener("click", startRerunFromForm);
  const pendingDrainButton = byId("pending-drain-button");
  if (pendingDrainButton) pendingDrainButton.addEventListener("click", () => window.mediaPipelineLaunchView?.startPendingPublishDrain?.());
  const pendingRecoveryPlanSelectedButton = byId("pending-recovery-plan-selected-button");
  if (pendingRecoveryPlanSelectedButton) pendingRecoveryPlanSelectedButton.addEventListener("click", () => requestPendingRecoveryPlan("selected"));
  const pendingRecoveryPlanAllButton = byId("pending-recovery-plan-all-button");
  if (pendingRecoveryPlanAllButton) pendingRecoveryPlanAllButton.addEventListener("click", () => requestPendingRecoveryPlan("all"));
  const maintenanceRefreshButton = byId("maintenance-refresh-button");
  if (maintenanceRefreshButton) maintenanceRefreshButton.addEventListener("click", refreshMaintenance);
  const releaseDryRunButton = byId("release-dry-run-button");
  if (releaseDryRunButton) releaseDryRunButton.addEventListener("click", runReleaseDryRun);
  const releaseBuildButton = byId("release-build-button");
  if (releaseBuildButton) releaseBuildButton.addEventListener("click", () => window.mediaPipelineMaintenanceView?.runReleaseBuild?.());
  const backfillDryRunButton = byId("backfill-dry-run-button");
  if (backfillDryRunButton) backfillDryRunButton.addEventListener("click", runBackfillDryRun);
  const queueFilter = byId("queue-filter");
  if (queueFilter) queueFilter.addEventListener("input", () => window.mediaPipelineQueueView?.renderQueueRows?.());
  const queueStatusFilter = byId("queue-status-filter");
  if (queueStatusFilter) queueStatusFilter.addEventListener("change", () => window.mediaPipelineQueueView?.renderQueueRows?.());
  const queueInvestigationFilter = byId("queue-investigation-filter");
  if (queueInvestigationFilter) queueInvestigationFilter.addEventListener("change", () => window.mediaPipelineQueueView?.renderQueueRows?.());
  const queueClearFiltersButton = byId("queue-clear-filters-button");
  if (queueClearFiltersButton) queueClearFiltersButton.addEventListener("click", resetQueueFilters);
  const completedFilter = byId("completed-filter");
  if (completedFilter) completedFilter.addEventListener("input", () => window.mediaPipelineCompletedView?.renderCompletedRows?.());
  const completedStatusFilter = byId("completed-status-filter");
  if (completedStatusFilter) completedStatusFilter.addEventListener("change", () => window.mediaPipelineCompletedView?.renderCompletedRows?.());
  const completedInvestigationFilter = byId("completed-investigation-filter");
  if (completedInvestigationFilter) completedInvestigationFilter.addEventListener("change", () => window.mediaPipelineCompletedView?.renderCompletedRows?.());
  const completedClearFiltersButton = byId("completed-clear-filters-button");
  if (completedClearFiltersButton) completedClearFiltersButton.addEventListener("click", resetCompletedFilters);
  const publishReconciliationRefreshButton = byId("publish-reconciliation-refresh-button");
  if (publishReconciliationRefreshButton) publishReconciliationRefreshButton.addEventListener("click", () => window.mediaPipelineCompletedView?.requestPublishReconciliation?.());
  const pendingFilter = byId("pending-filter");
  if (pendingFilter) pendingFilter.addEventListener("input", () => window.mediaPipelinePendingPublishView?.renderPendingRows?.());
  const pendingStatusFilter = byId("pending-status-filter");
  if (pendingStatusFilter) pendingStatusFilter.addEventListener("change", () => window.mediaPipelinePendingPublishView?.renderPendingRows?.());
  const pendingInvestigationFilter = byId("pending-investigation-filter");
  if (pendingInvestigationFilter) pendingInvestigationFilter.addEventListener("change", () => window.mediaPipelinePendingPublishView?.renderPendingRows?.());
  const pendingClearFiltersButton = byId("pending-clear-filters-button");
  if (pendingClearFiltersButton) pendingClearFiltersButton.addEventListener("click", () => window.mediaPipelinePendingPublishView?.resetPendingFilters?.());
  const failureFilter = byId("failure-filter");
  if (failureFilter) failureFilter.addEventListener("input", renderFailureRows);
  const failureSourceMarkers = byId("failure-source-markers");
  if (failureSourceMarkers) failureSourceMarkers.addEventListener("change", refreshAll);
  const auditPreviewFilter = byId("audit-preview-filter");
  if (auditPreviewFilter) auditPreviewFilter.addEventListener("input", renderAuditRows);
  const auditPreviewPriorityOnly = byId("audit-preview-priority-only");
  if (auditPreviewPriorityOnly) auditPreviewPriorityOnly.addEventListener("change", refreshAll);
  document.querySelectorAll("[data-control-action]").forEach((button) => {
    button.addEventListener("click", () => requestPipelineControl(button.dataset.controlAction || ""));
  });
  document.querySelectorAll("[data-open-diagnostics]").forEach((button) => {
    button.addEventListener("click", () => requestDiagnosticsOpen(button.dataset.openDiagnostics || ""));
  });
  document.querySelectorAll("[data-open-pending]").forEach((button) => {
    button.addEventListener("click", () => requestPendingPublishOpen(button.dataset.openPending || ""));
  });
    document.querySelectorAll("[data-open-completed]").forEach((button) => {
      button.addEventListener("click", () => requestCompletedOpen(button.dataset.openCompleted || ""));
    });
    document.querySelectorAll("[data-open-queue]").forEach((button) => {
      button.addEventListener("click", () => requestQueueOpen(button.dataset.openQueue || ""));
    });
    document.querySelectorAll("[data-open-queue-excluded]").forEach((button) => {
      button.addEventListener("click", () => requestQueueOpen(button.dataset.openQueueExcluded || "", "excluded"));
    });
  updatePagePanelEmptyStates();
  refreshAll();
  window.setInterval(refreshAll, 4000);
});
