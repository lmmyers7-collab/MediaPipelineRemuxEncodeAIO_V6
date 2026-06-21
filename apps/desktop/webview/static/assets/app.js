const bootstrap = window.MEDIA_PIPELINE_BOOTSTRAP || {};
const AUTOMATIC_REFRESH_INTERVAL_MS = 15000;
const AUTOMATIC_OPTIONAL_GET_TIMEOUT_MS = 12000;

let lastSnapshot = null;
let lastCloseReadiness = null;
let lastSchedule = null;
let refreshInFlight = false;
let refreshQueued = false;
let refreshQueuedOptions = null;
let lastRefreshStartedAt = null;
let lastRefreshCompletedAt = null;
let lastRefreshDurationMs = null;
void [lastRefreshStartedAt, lastRefreshCompletedAt, lastRefreshDurationMs];
let backendShutdownInFlight = false;
let lastStartupProgress = bootstrap.startupProgress || null;
let lastTauriBackendLifecycleEvent = null;

function renderBrandVersion(snapshot = {}) {
  return window.mediaPipelineAppTopbar?.renderBrandVersion?.(snapshot, bootstrap);
}

function renderHomePipelineState(value) {
  return window.mediaPipelineAppTopbar?.renderHomePipelineState?.(value);
}






function topbarStageContext(progress = {}) {
  return window.mediaPipelineAppTopbar?.topbarStageContext?.(progress) || "";
}

function renderTopbarActivity(snapshot = {}) {
  return window.mediaPipelineAppTopbar?.renderTopbarActivity?.(snapshot);
}

function renderTopbarEventTicker(snapshot = {}) {
  return window.mediaPipelineAppTopbar?.renderTopbarEventTicker?.(snapshot);
}

function setTopbarPendingLaunch(payload = {}) {
  return window.mediaPipelineAppTopbar?.setTopbarPendingLaunch?.(payload);
}

function formatCloseReadiness(closeReadiness) {
  return window.mediaPipelineAppCloseReadiness?.formatCloseReadiness?.(closeReadiness) || "Close readiness has not loaded yet.";
}

function closeReadinessWatcherData(closeReadiness = lastCloseReadiness) {
  return window.mediaPipelineAppCloseReadiness?.closeReadinessWatcherData?.(closeReadiness) || {};
}

function closeReadinessWatcherSummary(closeReadiness = lastCloseReadiness) {
  return window.mediaPipelineAppCloseReadiness?.closeReadinessWatcherSummary?.(closeReadiness) || "unknown";
}

function closeReadinessWatcherIsArmed(closeReadiness = lastCloseReadiness) {
  return Boolean(window.mediaPipelineAppCloseReadiness?.closeReadinessWatcherIsArmed?.(closeReadiness));
}
void [
  topbarStageContext,
  renderTopbarEventTicker,
  setTopbarPendingLaunch,
  closeReadinessWatcherData,
  closeReadinessWatcherSummary,
  closeReadinessWatcherIsArmed,
];
void ["window.mediaPipelineLaunchView?.updateLaunchCommandButtonStates", "progressWorkerPayload?.(snapshot, diagnostics)", "tauri-lifecycle-alert", "Open Diagnostics before starting, draining, saving, renaming, publishing, or closing.", "Recovery: refresh once, then inspect Diagnostics run logs"];

function backendLifecycleState(closeReadiness = lastCloseReadiness) {
  return window.mediaPipelineAppCloseReadiness?.backendLifecycleState?.(closeReadiness) || { label: "Waiting", state: "unknown", canShutdown: false, reason: "Close-readiness has not loaded yet." };
}

function startupProgressLines(progress = lastStartupProgress) {
  return window.mediaPipelineAppTauriLifecycle?.startupProgressLines?.(progress) || ["Startup progress: not reported by backend bootstrap."];
}

function normalizeTauriBackendLifecycleEvent(payload) {
  return window.mediaPipelineAppTauriLifecycle?.normalizeTauriBackendLifecycleEvent?.(payload) || { schema_version: "unknown", status: "unknown", detail: "No lifecycle detail was reported.", consecutive_failures: 0, emitted_at_unix_seconds: 0 };
}

function tauriBackendLifecycleLines(event = lastTauriBackendLifecycleEvent) {
  return window.mediaPipelineAppTauriLifecycle?.tauriBackendLifecycleLines?.(event) || [];
}

function renderTauriBackendLifecycleAlert(event = lastTauriBackendLifecycleEvent) {
  return window.mediaPipelineAppTauriLifecycle?.renderTauriBackendLifecycleAlert?.(event);
}

function renderLaunchReadinessPanel(payload) {
  window.mediaPipelineLaunchReadinessView?.renderLaunchReadiness?.(payload);
}

function renderSnapshot(snapshot) {
  lastSnapshot = snapshot || {};
  const state = snapshot.pipeline_state || "idle";
  renderBrandVersion(snapshot);
  renderTopbarActivity(snapshot);
  renderTopbarEventTicker(snapshot);
  renderHomePipelineState(state);
  setText("status-summary", snapshot.status_summary || "No status summary.");
  const pill = byId("state-pill");
  if (pill) {
    const phaseLabel = snapshot?.current_work?.phase_label || state;
    pill.textContent = phaseLabel;
    pill.dataset.state = state;
  }
  const counts = snapshot.counts || {};
  const queueIndex = Math.max(0, Math.trunc(Number(counts.queue_index) || 0));
  const queueTotal = Math.max(0, Math.trunc(Number(counts.queue_total) || 0));
  setText("queue-count", `${queueIndex} / ${queueTotal}`);
  setText("processed-count", String(counts.processed || 0));
  renderDashboardIssueMetric(snapshot, dashboardCount(counts.failed));
  if (typeof renderProgressBars === "function") {
    renderProgressBars(Array.isArray(snapshot.progress_bars) ? snapshot.progress_bars : [], snapshot);
  }
  renderProgressDetails(snapshot.progress || {});
  if (typeof renderProgressEvidence === "function") {
    renderProgressEvidence({ snapshot: lastSnapshot, closeReadiness: lastCloseReadiness, diagnostics: null });
  }
  window.mediaPipelineProgressView?.renderDiagnosticsProgress?.(lastSnapshot);
  window.mediaPipelineProgressView?.renderLiveRunStrip?.({
    snapshot: lastSnapshot,
    diagnostics: null,
    closeReadiness: lastCloseReadiness,
  });
  const recentEvents = Array.isArray(snapshot.recent_events) ? snapshot.recent_events : [];
  window.mediaPipelineProgressView?.renderPipelineEvents?.(recentEvents);
  renderSparkline(recentEvents);
  window.mediaPipelineReportsView?.renderReports?.(lastSnapshot, getLastSettings());
  renderControlReadiness(lastSnapshot, lastCloseReadiness);
  renderLaunchReadinessPanel({ snapshot: lastSnapshot, closeReadiness: lastCloseReadiness, schedule: lastSchedule, settings: getLastSettings() });
  renderBackendLifecycle(lastCloseReadiness, lastSnapshot);
}

function dashboardText(value) {
  return String(value || "").trim().toLowerCase();
}

function dashboardCount(value) {
  const number = Number(value);
  return Number.isFinite(number) ? Math.max(0, Math.trunc(number)) : 0;
}

function dashboardBoolean(value) {
  if (typeof value === "boolean") return value;
  const text = dashboardText(value);
  if (["1", "true", "yes", "y"].includes(text)) return true;
  if (["0", "false", "no", "n"].includes(text)) return false;
  return false;
}

function dashboardEventData(event) {
  return event?.data && typeof event.data === "object" ? event.data : {};
}

function dashboardEventIsStopRequested(event) {
  const data = dashboardEventData(event);
  const status = dashboardText(data.completion_status || event?.status || "");
  const errorCode = dashboardText(data.error_code || data.ErrorCode || "");
  const reason = dashboardText(data.reason || data.suggested_action || "");
  return status === "stopped" && (errorCode === "stop_requested" || (reason.includes("stop") && reason.includes("operator")));
}

function dashboardEventIsFailure(event) {
  const data = dashboardEventData(event);
  const status = dashboardText(data.completion_status || event?.status || data.classification || "");
  const errorCode = dashboardText(data.error_code || data.ErrorCode || "");
  return ["failed", "failure", "error", "blocked"].includes(status)
    || String(event?.event_type || "").toLowerCase() === "failure_recorded"
    || Boolean(errorCode && errorCode !== "stop_requested");
}

function dashboardProgressHasStopRequested(progress = {}) {
  const payload = progress && typeof progress === "object" ? progress : {};
  if (dashboardBoolean(payload.StopRequested) || dashboardBoolean(payload.stop_requested)) return true;
  const errorCode = dashboardText(payload.ErrorCode || payload.error_code || "");
  const reason = dashboardText(payload.Reason || payload.reason || "");
  if (errorCode === "stop_requested") return true;
  if (reason.includes("stop") && reason.includes("operator")) return true;
  const text = dashboardText([
    payload.CurrentStage,
    payload.Status,
    payload.status,
    payload.CurrentStatus,
  ].filter(Boolean).join(" "));
  return /\bstopped\b/.test(text) && (errorCode === "stop_requested" || (reason.includes("stop") && reason.includes("operator")));
}

function dashboardLatestStopRequestedOutcome(snapshot = {}) {
  const events = Array.isArray(snapshot?.recent_events) ? snapshot.recent_events : [];
  for (let index = events.length - 1; index >= 0; index -= 1) {
    const event = events[index];
    if (dashboardEventIsStopRequested(event)) return true;
    if (dashboardEventIsFailure(event)) return false;
  }
  return dashboardProgressHasStopRequested(snapshot?.progress || {});
}

function renderDashboardIssueMetric(snapshot = {}, failedCount = 0) {
  const stoppedByRequest = failedCount > 0 && dashboardLatestStopRequestedOutcome(snapshot);
  const visibleFailedCount = stoppedByRequest ? Math.max(0, failedCount - 1) : failedCount;
  const label = "Failed";
  const title = stoppedByRequest
    ? visibleFailedCount
      ? "Stop After Current is shown in progress; this remaining count still needs Diagnostics or run-log review."
      : "Stop After Current is shown in progress; this marker is not counted as a failed media output."
    : visibleFailedCount
      ? "Failed items need Diagnostics or run-log review."
      : "No failed items reported.";
  setText("failed-count", String(visibleFailedCount));
  setText("home-failed-count", String(visibleFailedCount));
  setText("failed-label", label);
  setText("home-failed-label", label);
  ["failed-count", "home-failed-count", "failed-label", "home-failed-label"].forEach((id) => {
    const node = byId(id);
    if (node) {
      node.title = title;
      node.dataset.state = visibleFailedCount ? "blocked" : "ok";
    }
  });
}

function dashboardHasOwn(source, key) {
  return Boolean(source && typeof source === "object" && Object.prototype.hasOwnProperty.call(source, key));
}

function dashboardPipelineStateAllowsEmptyScan(snapshot = lastSnapshot) {
  const state = dashboardText(snapshot?.pipeline_state || "");
  return !state || ["idle", "complete", "completed", "sleeping"].includes(state);
}

function dashboardQueueScanStatus(queue = {}) {
  const status = queue?.queue_scan_status;
  return status && typeof status === "object" ? status : {};
}

function dashboardQueueProgress(queue = {}) {
  const progress = queue?.queue_progress;
  return progress && typeof progress === "object" ? progress : {};
}

function dashboardQueueScanRunning(queue = {}) {
  const status = dashboardQueueScanStatus(queue);
  return Boolean(status.running) || dashboardText(status.status) === "running";
}

function dashboardQueueStale(queue = {}) {
  const progress = dashboardQueueProgress(queue);
  return Boolean(progress.stale)
    || dashboardText(queue.snapshot_file_freshness_status) === "stale"
    || dashboardText(queue.produced_freshness_status) === "stale";
}

function dashboardQueueBlockingWarnings(queue = {}) {
  const warnings = Array.isArray(queue.warnings) ? queue.warnings : [];
  return warnings.some((warning) => dashboardText(warning) !== "queue snapshot contains no runnable rows.");
}

function dashboardQueueRunnableCount(queue = {}) {
  if (dashboardHasOwn(queue, "runnable_count")) return dashboardCount(queue.runnable_count);
  if (Array.isArray(queue.rows)) return queue.rows.length;
  return null;
}

function dashboardQueueHasFreshEmptyProof(queue = {}) {
  const status = dashboardQueueScanStatus(queue);
  const scanStatus = dashboardText(status.status);
  if (scanStatus === "completed" && dashboardHasOwn(status, "curated_row_count")) {
    return dashboardCount(status.curated_row_count) === 0;
  }

  const runnableCount = dashboardQueueRunnableCount(queue);
  if (runnableCount !== 0) return false;

  const progress = dashboardQueueProgress(queue);
  const progressStatus = dashboardText(progress.status);
  const hasFreshnessEvidence = Boolean(queue.snapshot_file_freshness_status || queue.produced_freshness_status);
  return progressStatus === "complete" || hasFreshnessEvidence;
}

function renderHomePipelineQueueOutcome(snapshot = lastSnapshot, queue = {}) {
  if (!dashboardPipelineStateAllowsEmptyScan(snapshot)) return false;
  if (!queue || typeof queue !== "object" || !queue.schema_version || queue.error) return false;
  if (dashboardQueueScanRunning(queue) || dashboardQueueStale(queue) || dashboardQueueBlockingWarnings(queue)) return false;
  if (!dashboardQueueHasFreshEmptyProof(queue)) return false;
  renderHomePipelineState("no_new_sources");
  return true;
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
    renderLaunchReadinessPanel({ snapshot: lastSnapshot, closeReadiness: lastCloseReadiness, schedule: lastSchedule, settings: getLastSettings() });
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
  renderLaunchReadinessPanel({ snapshot: lastSnapshot, closeReadiness: lastCloseReadiness, schedule: lastSchedule, settings: getLastSettings() });
  renderBackendLifecycle(lastCloseReadiness, lastSnapshot);
}











function handleTauriBackendLifecycleEvent(event) {
  lastTauriBackendLifecycleEvent = normalizeTauriBackendLifecycleEvent(event?.detail);
  renderTauriBackendLifecycleAlert(lastTauriBackendLifecycleEvent);
  renderBackendLifecycle(lastCloseReadiness, lastSnapshot);
}

function renderBackendLifecycle(closeReadiness = lastCloseReadiness, snapshot = lastSnapshot) {
  return window.mediaPipelineAppLifecycle?.renderBackendLifecycle?.(closeReadiness, snapshot);
}

function backendLifecycleCommandEntries(history) {
  return window.mediaPipelineAppLifecycle?.backendLifecycleCommandEntries?.(history) || [];
}

function backendLifecycleCommandLine(entry) {
  const line = window.mediaPipelineAppLifecycle?.backendLifecycleCommandLine?.(entry);
  if (line) return line;
  if (typeof window.commandHistoryCompactEvidenceLine === "function") {
    return window.commandHistoryCompactEvidenceLine(entry, { label: "backend.shutdown" });
  }
  return "";
}

function renderBackendLifecycleHistory(history = []) {
  return window.mediaPipelineAppLifecycle?.renderBackendLifecycleHistory?.(history);
}

const _backendLifecycleSliceCompatibility = [
  startupProgressLines,
  tauriBackendLifecycleLines,
  backendLifecycleCommandEntries,
  backendLifecycleCommandLine,
];

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
    // Backend authority: the Local API owns the lifecycle request; WebView only submits the guarded command.
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
  return Boolean(window.mediaPipelineAppCloseReadiness?.closeReadinessRequiresWarning?.(lastCloseReadiness, lastSnapshot));
}

function closeReadinessWarningMessage() {
  return window.mediaPipelineAppCloseReadiness?.closeReadinessWarningMessage?.(lastCloseReadiness) || "Active MediaPipeline work may still be running. Close anyway?";
}

function rowOpenActionGroup(scope) {
  return window.mediaPipelineAppRowOpenActions?.rowOpenActionGroup?.(scope) || null;
}

function initBackendRowOpenActions() {
  return window.mediaPipelineAppRowOpenActions?.initBackendRowOpenActions?.();
}

function refreshTimeLabel(value) {
  return window.mediaPipelineAppRefresh?.refreshTimeLabel?.(value) || "never";
}

function renderRefreshInProgress() {
  return window.mediaPipelineAppRefresh?.renderRefreshInProgress?.();
}

function renderRefreshHealth(failures) {
  return window.mediaPipelineAppRefresh?.renderRefreshHealth?.(failures);
}

function attachRefreshMetadata(name, payload) {
  return window.mediaPipelineAppRefresh?.attachRefreshMetadata?.(name, payload) || payload;
}

function initPageRefreshButtons() {
  return window.mediaPipelineAppRefresh?.initPageRefreshButtons?.();
}

function refreshFailure(name, result, required = false) {
  return window.mediaPipelineAppRefresh?.refreshFailure?.(name, result, required) || null;
}

function renderHomeReadiness(context = {}) {
  return window.mediaPipelineAppHomeReadiness?.renderHomeReadiness?.(context);
}

function dailyDriverRows(context = {}) {
  return window.mediaPipelineAppHomeReadiness?.dailyDriverRows?.(context) || [];
}

function dailyDriverStatusClass(status) {
  return window.mediaPipelineAppHomeReadiness?.dailyDriverStatusClass?.(status) || "match";
}

function dailyDriverSummaryLines(rows = []) {
  return window.mediaPipelineAppHomeReadiness?.dailyDriverSummaryLines?.(rows) || [];
}

function dependencyStatusLabel(status) {
  return window.mediaPipelineAppHomeReadiness?.dependencyStatusLabel?.(status) || "review";
}

function homeProgressPercent(value) {
  return window.mediaPipelineAppHomeReadiness?.homeProgressPercent?.(value) || "";
}
void [homeProgressPercent];

function renderHomePendingCount(pending) {
  return window.mediaPipelineAppHomeReadiness?.renderHomePendingCount?.(pending);
}

function renderHomeNetworkRole(settings) {
  return window.mediaPipelineAppHomeReadiness?.renderHomeNetworkRole?.(settings);
}

function renderHomeStorageHealth(context = {}) {
  return window.mediaPipelineAppHomeReadiness?.renderHomeStorageHealth?.(context);
}

function renderHomeQueueSnapshot(queue) {
  return window.mediaPipelineAppHomeReadiness?.renderHomeQueueSnapshot?.(queue);
}

function renderHomeRecentCompleted(completed) {
  return window.mediaPipelineAppHomeReadiness?.renderHomeRecentCompleted?.(completed);
}

function renderHomePromotionEntry(status = {}) {
  return window.mediaPipelineAppHomeReadiness?.renderHomePromotionEntry?.(status);
}

function externalDependencyRows(context = {}) {
  return window.mediaPipelineAppHomeReadiness?.externalDependencyRows?.(context) || [];
}

function externalDependencyOverallStatus(context = {}) {
  return window.mediaPipelineAppHomeReadiness?.externalDependencyOverallStatus?.(context) || "unknown";
}

function externalDependencySummaryLines(context = {}) {
  return window.mediaPipelineAppHomeReadiness?.externalDependencySummaryLines?.(context) || [];
}

function externalDependencyEvidenceText(context = {}) {
  return window.mediaPipelineAppHomeReadiness?.externalDependencyEvidenceText?.(context) || "external dependency evidence not loaded";
}

function renderExternalDependencyDigest(context = {}) {
  return window.mediaPipelineAppHomeReadiness?.renderExternalDependencyDigest?.(context);
}




















function renderHomeNextQueue(context = {}) {
  return window.mediaPipelineAppHomeReadiness?.renderHomeNextQueue?.(context);
}

function renderDailyDriverReadiness(context = {}) {
  return window.mediaPipelineAppHomeReadiness?.renderDailyDriverReadiness?.(context);
}

void [dailyDriverRows, dailyDriverStatusClass, dailyDriverSummaryLines, dependencyStatusLabel];
void [renderHomeNetworkRole];




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

function renderTelemetrySafely(telemetry, options = {}) {
  const renderTelemetryFn = window.mediaPipelineTelemetryView?.renderTelemetry;
  if (typeof renderTelemetryFn !== "function") return null;
  try {
    renderTelemetryFn(telemetry, options);
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












function renderControlReadiness(snapshot, closeReadiness) {
  return window.mediaPipelineAppLifecycle?.renderControlReadiness?.(snapshot, closeReadiness);
}

function updatePagePanelEmptyStates() {
  return window.mediaPipelineAppLifecycle?.updatePagePanelEmptyStates?.();
}

function showPage(page) {
  return window.mediaPipelineAppLifecycle?.showPage?.(page);
}
window.showPage = showPage;

function applyDefaultActionTooltips(root = document) {
  return window.mediaPipelineAppLifecycle?.applyDefaultActionTooltips?.(root);
}

void [showPage, refreshTimeLabel, "[data-settings-path-key]"];

function normalizeRefreshOptions(options = {}) {
  return {
    automatic: Boolean(options && options.automatic === true),
    queueRefresh: Boolean(options && options.queueRefresh === true),
  };
}

function mergeRefreshOptions(existing, next) {
  const current = normalizeRefreshOptions(existing || {});
  const incoming = normalizeRefreshOptions(next || {});
  return {
    automatic: current.automatic && incoming.automatic,
    queueRefresh: current.queueRefresh || incoming.queueRefresh,
  };
}

function refreshGet(path, refreshOptions = {}, options = {}) {
  const requestOptions = {};
  const timeoutMs = Number(options.timeoutMs);
  if (Number.isFinite(timeoutMs) && timeoutMs > 0) {
    requestOptions.timeoutMs = timeoutMs;
  } else if (normalizeRefreshOptions(refreshOptions).automatic && options.required !== true) {
    requestOptions.timeoutMs = AUTOMATIC_OPTIONAL_GET_TIMEOUT_MS;
  }
  return apiGet(path, requestOptions);
}

async function refreshAll(options = {}) {
  const refreshOptions = normalizeRefreshOptions(options);
  if (refreshInFlight) {
    if (refreshOptions.automatic) return;
    refreshQueued = true;
    refreshQueuedOptions = mergeRefreshOptions(refreshQueuedOptions, refreshOptions);
    return;
  }
  refreshInFlight = true;
  try {
    await refreshAllNow(refreshOptions);
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    renderTopbarActivity({ activity: `Refresh failed: ${message}` });
    renderRefreshHealth([{
      name: "refresh/render",
      required: true,
      message,
    }], refreshOptions);
  } finally {
    refreshInFlight = false;
    if (refreshQueued) {
      const queuedOptions = normalizeRefreshOptions(refreshQueuedOptions || {});
      refreshQueued = false;
      refreshQueuedOptions = null;
      window.setTimeout(() => refreshAll(queuedOptions), 0);
    }
  }
}

async function refreshCurrentOutputStatus() {
  return window.mediaPipelineAppRefresh?.refreshCurrentOutputStatus?.();
}

async function refreshAllNow(options = {}) {
  const refreshOptions = normalizeRefreshOptions(options);
  lastRefreshStartedAt = new Date();
  const refreshStartedMs = Date.now();
  renderRefreshInProgress(refreshOptions);
  const failureSourceMarkers = Boolean(byId("failure-source-markers")?.checked);
  const failureQuery = `/api/failures?limit=100${failureSourceMarkers ? "&source=markers" : ""}`;
  const auditPriorityOnly = Boolean(byId("audit-preview-priority-only")?.checked);
  const auditQuery = `/api/audit-results?limit=100${auditPriorityOnly ? "&priority_only=true" : ""}`;
  const requests = [
    ["health", refreshGet("/api/health", refreshOptions), false],
    ["snapshot", refreshGet("/api/snapshot", refreshOptions, { required: true }), true],
    ["close readiness", refreshGet("/api/backend/close-readiness", refreshOptions), false],
    ["telemetry", refreshGet("/api/telemetry", refreshOptions), false],
    ["diagnostics", refreshGet("/api/diagnostics", refreshOptions), false],
    ["diagnostics state summary", refreshGet("/api/diagnostics/state-summary", refreshOptions), false],
    ["commands", refreshGet("/api/commands?limit=20", refreshOptions), false],
    ["metrics", refreshGet("/api/metrics", refreshOptions), false],
    ["queue", refreshGet("/api/queue", refreshOptions), false],
    ["completed", refreshGet("/api/completed?limit=100", refreshOptions), false],
    ["failures", refreshGet(failureQuery, refreshOptions), false],
    ["audit results", refreshGet(auditQuery, refreshOptions), false],
    ["audit controls", refreshGet("/api/audit-controls", refreshOptions), false],
    ["pending publish", refreshGet("/api/pending-publish", refreshOptions), false],
    ["schedule", refreshGet("/api/schedule", refreshOptions), false],
    ["watch folders", refreshGet("/api/watch-folders/status", refreshOptions), false],
    ["settings", refreshGet("/api/settings/workspace", refreshOptions), false],
    ["libraries route map", refreshGet("/api/libraries/route-map", refreshOptions), false],
    ["network workers", refreshGet("/api/network/workers", refreshOptions), false],
    ["sample validation", refreshGet("/api/sample-validation?limit=10", refreshOptions), false],
    ["contract", refreshGet("/api/contract", refreshOptions), false],
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
    values[name] = attachRefreshMetadata(name, result.value);
  });
  const pendingPublishFailure = failures.find((item) => item.name === "pending publish");
  const pendingPublishPayload = values["pending publish"] || (pendingPublishFailure ? {
    schema_version: "desktop_pending_publish_preview.v1",
    count: 0,
    rows: [],
    error: pendingPublishFailure.message || "Pending Publish proof read failed.",
    warnings: [pendingPublishFailure.message || "Pending Publish proof read failed."],
    operator_status: "blocked",
    file_inventory: {
      status: "blocked",
      error: pendingPublishFailure.message || "Pending Publish proof read failed.",
    },
    recovery_summary: {
      status: "blocked",
      safe_next_action: "Open Diagnostics and Pending Publish after refresh succeeds before trusting final-placement evidence.",
    },
  } : {});
  const scrollSnapshot = window.mediaPipelineDom?.captureScrollablePositions?.();
  try {
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
  const telemetryOptions = {
    snapshot: values.snapshot || lastSnapshot,
    refreshIntervalMs: AUTOMATIC_REFRESH_INTERVAL_MS,
  };
  const telemetryFailure = failures.find((item) => item.name === "telemetry");
  const telemetryRenderFailure = values.telemetry
    ? renderTelemetrySafely(values.telemetry, telemetryOptions)
    : renderTelemetrySafely(null, {
      ...telemetryOptions,
      unavailableReason: telemetryFailure?.message || "telemetry route returned no payload",
    });
  if (telemetryRenderFailure) failures.push(telemetryRenderFailure);
  if (values.diagnostics) renderDiagnostics(values.diagnostics);
  const renderDiagnosticsStateSummaryFn = window.mediaPipelineDiagnosticsStateSummaryView?.renderDiagnosticsStateSummary;
  if (values["diagnostics state summary"] && typeof renderDiagnosticsStateSummaryFn === "function") {
    renderDiagnosticsStateSummaryFn(values["diagnostics state summary"]);
  }
  if (values.commands) window.mediaPipelineCommandHistory?.renderCommandHistoryPayload?.(values.commands);
  if (values.metrics) window.mediaPipelineMetricsView?.renderMetrics?.(values.metrics);
  if (values.queue) renderQueue(values.queue);
  renderHomeQueueSnapshot(values.queue || {});
  renderHomePipelineQueueOutcome(values.snapshot || lastSnapshot, values.queue || {});
  if (values.completed) renderCompleted(values.completed);
  // Reuse the final-library promotion status attached to the completed payload:
  // the completed read already computes it via the same builder
  // (annotate_final_library_promotion_rows -> get_final_library_promotion_status),
  // so the broad refresh no longer issues a second 500-row completed load via
  // /api/final-library-promotion/status. Full status loads on demand from the
  // Current Output Status action. (backend-load-performance Packet 4.)
  const finalLibraryPromotion = values.completed?.final_library_promotion;
  if (finalLibraryPromotion) window.mediaPipelineCompletedView?.renderFinalLibraryPromotion?.(finalLibraryPromotion);
  renderHomePromotionEntry(finalLibraryPromotion || {});
  renderHomeRecentCompleted(values.completed || {});
  if (values.failures) window.mediaPipelineReportsView?.renderFailurePreview?.(values.failures);
  if (values["audit results"]) {
    window.mediaPipelineReportsView?.renderAuditPreview?.(values["audit results"]);
  }
  if (values["audit controls"]) {
    window.mediaPipelineReportsView?.renderAuditControls?.(values["audit controls"]);
  }
  if (values["pending publish"] || pendingPublishFailure) renderPendingPublish(pendingPublishPayload, values.snapshot || lastSnapshot);
  renderHomePendingCount(pendingPublishPayload);
  if (values.schedule) {
    lastSchedule = values.schedule;
    renderSchedule(values.schedule);
  }
  const watchFoldersFailure = failures.find((item) => item.name === "watch folders");
  if (values["watch folders"] || watchFoldersFailure) {
    window.mediaPipelineScheduleView?.renderWatchFolderStatus?.(values["watch folders"] || {
      schema_version: "desktop_watch_folders.v1",
      status: "error",
      reason: watchFoldersFailure?.message || "Watch-folder status read failed.",
      last_error: watchFoldersFailure?.message || "Watch-folder status read failed.",
    });
  }
  if (values.settings) {
    renderSettings(values.settings);
    window.mediaPipelineSettingsLibraries?.renderSettingsLibraries?.(values.settings, refreshOptions);
    window.mediaPipelineReportsView?.renderReports?.(lastSnapshot, getLastSettings());
    window.mediaPipelineLaunchView?.renderAllLaunchPreflights?.();
  }
  if (values["libraries route map"]) {
    window.mediaPipelineLibraryRouteMap?.renderRouteMap?.(values["libraries route map"], {
      queue: values.queue || {},
      completed: values.completed || {},
      sampleValidation: values["sample validation"] || {},
    });
  }
  if (values.contract) window.mediaPipelineContractView?.renderContract?.(values.contract);
  const renderNetworkViewFn = window.mediaPipelineNetworkView?.renderNetworkView;
  if (typeof renderNetworkViewFn === "function") {
    renderNetworkViewFn({
      settings: values.settings || getLastSettings(),
      contract: values.contract || {},
      closeReadiness: values["close readiness"] || lastCloseReadiness,
      snapshot: values.snapshot || lastSnapshot,
      queue: values.queue || {},
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
    maintenance: window.mediaPipelineMaintenanceView?.getLastMaintenance?.() || {},
  };
  renderExternalDependencyDigest(dependencyContext);
  renderLaunchReadinessPanel({
    snapshot: values.snapshot || lastSnapshot,
    closeReadiness: values["close readiness"] || lastCloseReadiness,
    schedule: values.schedule || lastSchedule,
    settings: values.settings || getLastSettings(),
    failures,
  });
  window.mediaPipelineProgressView?.renderHomeActiveWork?.({
    snapshot: values.snapshot || lastSnapshot,
    diagnostics: values.diagnostics || null,
    closeReadiness: values["close readiness"] || lastCloseReadiness,
  });
  window.mediaPipelineProgressView?.renderLiveRunStrip?.({
    snapshot: values.snapshot || lastSnapshot,
    diagnostics: values.diagnostics || null,
    closeReadiness: values["close readiness"] || lastCloseReadiness,
  });
  if (typeof renderProgressEvidence === "function") {
    renderProgressEvidence({
      snapshot: values.snapshot || lastSnapshot,
      closeReadiness: values["close readiness"] || lastCloseReadiness,
      diagnostics: values.diagnostics || null,
    });
  }
  window.mediaPipelineProgressView?.renderDiagnosticsProgress?.(values.snapshot || lastSnapshot, values.diagnostics || null);
  if (typeof renderCrossPageContext === "function") {
    const crossPageContext = {
      snapshot: values.snapshot || lastSnapshot,
      closeReadiness: values["close readiness"] || lastCloseReadiness,
      queue: values.queue || {},
      completed: values.completed || {},
      pending: pendingPublishPayload,
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
      pending: pendingPublishPayload,
      settings: values.settings || getLastSettings(),
      sampleValidation: values["sample validation"] || {},
      maintenance: window.mediaPipelineMaintenanceView?.getLastMaintenance?.() || {},
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
      pending: pendingPublishPayload,
      sampleValidation: values["sample validation"] || {},
      settings: values.settings || getLastSettings(),
    });
  }
  const renderDiagnosticsRefreshFailuresFn = window.mediaPipelineDiagnosticsView?.renderDiagnosticsRefreshFailures;
  if (typeof renderDiagnosticsRefreshFailuresFn === "function") {
    renderDiagnosticsRefreshFailuresFn(failures);
  }
  lastRefreshCompletedAt = new Date();
  lastRefreshDurationMs = Date.now() - refreshStartedMs;
  renderRefreshHealth(failures, refreshOptions);
  const dashboardContext = {
    snapshot: values.snapshot || lastSnapshot,
    closeReadiness: values["close readiness"] || lastCloseReadiness,
    schedule: values.schedule || lastSchedule,
    settings: values.settings || getLastSettings(),
    stateSummary: values["diagnostics state summary"] || {},
    maintenance: window.mediaPipelineMaintenanceView?.getLastMaintenance?.() || {},
    queue: values.queue || {},
    completed: values.completed || {},
    pending: pendingPublishPayload,
    diagnostics: values.diagnostics || {},
    networkWorkers: values["network workers"] || {},
    failuresPayload: values.failures || {},
    auditResults: values["audit results"] || {},
    failures,
  };
  renderHomeNextQueue(dashboardContext);
  renderHomeStorageHealth(dashboardContext);
  renderDailyDriverReadiness(dashboardContext);
  window.mediaPipelineDom?.applyProseBoxDispositions?.(document);
  } finally {
    window.mediaPipelineDom?.restoreScrollablePositions?.(scrollSnapshot);
  }
}

window.refreshAll = refreshAll;
window.refreshAllNow = refreshAllNow;
window.setTopbarPendingLaunch = setTopbarPendingLaunch;
window.externalDependencyRows = externalDependencyRows;
window.externalDependencyOverallStatus = externalDependencyOverallStatus;
window.externalDependencySummaryLines = externalDependencySummaryLines;
window.externalDependencyEvidenceText = externalDependencyEvidenceText;
window.renderExternalDependencyDigest = renderExternalDependencyDigest;

// ── HOME PAGE FUNCTIONS — Stage 12 ──────────────────────────────────────────





// ── SETTINGS TAB NAV — Stage 13 ─────────────────────────────────────────────


// ── DIAGNOSTICS TAB NAV — Stage 14 ───────────────────────────────────────────


// ── COMPLETED TAB NAV — Stage 15 ─────────────────────────────────────────────


// Browser and Tauri WebView2 do not share localStorage, even when both load the
// same localhost URL. Sync only app-owned UI keys through the local backend so
// layout/theme/tab customization follows the operator between surfaces.
function initSettingsTabNav() {
  return window.mediaPipelineAppLifecycle?.initSettingsTabNav?.();
}

function initDiagnosticsTabNav() {
  return window.mediaPipelineAppLifecycle?.initDiagnosticsTabNav?.();
}

function initCompletedTabNav() {
  return window.mediaPipelineAppLifecycle?.initCompletedTabNav?.();
}

function initNavigation() {
  return window.mediaPipelineAppLifecycle?.initNavigation?.();
}

function renderSparkline(events = []) {
  return window.mediaPipelineAppLifecycle?.renderSparkline?.(events);
}

function initLaunchEvidenceToggle() {
  return window.mediaPipelineAppLifecycle?.initLaunchEvidenceToggle?.();
}

function initCollapsibleSummaries() {
  return window.mediaPipelineAppLifecycle?.initCollapsibleSummaries?.();
}

function initThemeToggle() {
  return window.mediaPipelineAppLifecycle?.initThemeToggle?.();
}

function applyThemePreference(isLight) {
  return window.mediaPipelineAppLifecycle?.applyThemePreference?.(isLight);
}

const UI_PREFERENCES_ROUTE = "/api/ui-preferences";
const UI_PREFERENCE_KEY_RE = /^mediapipeline[-.][A-Za-z0-9_.:-]{1,160}$/;
const ADVANCED_MODE_STORAGE_KEY = "mediapipeline-advanced-mode";
const EVIDENCE_HIDDEN_STORAGE_KEY = "mediapipeline-evidence-hidden";
const THEME_STORAGE_KEY = "mediapipeline-theme";
void [applyThemePreference, THEME_STORAGE_KEY];
let uiPreferenceSyncInstalled = false;
let uiPreferenceSyncTimer = null;
let uiPreferenceRemoteRefreshTimer = null;
let uiPreferenceSyncInFlight = false;
let uiPreferenceSyncPending = false;
let uiPreferenceApplyingRemote = false;
let uiPreferenceLocalDirty = false;
let uiPreferenceLastSerialized = "";

function isSharedUiPreferenceKey(key) {
  return UI_PREFERENCE_KEY_RE.test(String(key || ""));
}

function collectSharedUiPreferences() {
  const storage = {};
  try {
    for (let index = 0; index < localStorage.length; index += 1) {
      const key = localStorage.key(index);
      if (!isSharedUiPreferenceKey(key)) continue;
      const value = localStorage.getItem(key);
      if (value !== null) storage[key] = String(value);
    }
  } catch (_) {}
  return Object.fromEntries(Object.entries(storage).sort(([a], [b]) => a.localeCompare(b)));
}

function currentUiPreferenceSurface() {
  const bootstrap = window.MEDIA_PIPELINE_BOOTSTRAP || {};
  return String(bootstrap.shellSurface || bootstrap.shell_surface || "webview").toLowerCase();
}

function readBooleanUiPreference(key) {
  try { return localStorage.getItem(key) === "1"; } catch (_) { return false; }
}

function sharedUiPreferencePayload() {
  return {
    storage: collectSharedUiPreferences(),
    source_surface: currentUiPreferenceSurface(),
  };
}

async function persistSharedUiPreferencesNow() {
  if (uiPreferenceApplyingRemote) return;
  if (uiPreferenceSyncInFlight) {
    uiPreferenceSyncPending = true;
    uiPreferenceLocalDirty = true;
    return;
  }
  if (uiPreferenceSyncTimer) {
    window.clearTimeout(uiPreferenceSyncTimer);
    uiPreferenceSyncTimer = null;
  }
  const payload = sharedUiPreferencePayload();
  const serialized = JSON.stringify(payload.storage);
  if (serialized === uiPreferenceLastSerialized) {
    uiPreferenceLocalDirty = false;
    return;
  }
  uiPreferenceSyncInFlight = true;
  try {
    const result = await apiPost("/api/ui-preferences", payload, { timeoutMs: 5000 });
    if (result && result.ok === false) {
      throw new Error(result.message || "UI preference sync failed.");
    }
    uiPreferenceLastSerialized = serialized;
    uiPreferenceLocalDirty = false;
  } catch (_) {
    // UI preference sync must never block the operator surface.
  } finally {
    uiPreferenceSyncInFlight = false;
    if (uiPreferenceSyncPending) {
      uiPreferenceSyncPending = false;
      scheduleSharedUiPreferenceSync();
    }
  }
}

function applySharedUiPreferenceStorage(remoteStorage) {
  const local = collectSharedUiPreferences();
  const remoteEntries = Object.entries(remoteStorage || {}).filter(([key]) => isSharedUiPreferenceKey(key));
  const remote = Object.fromEntries(remoteEntries);
  let changed = false;
  Object.keys(local).forEach((key) => {
    if (!Object.prototype.hasOwnProperty.call(remote, key)) {
      try { localStorage.removeItem(key); changed = true; } catch (_) {}
    }
  });
  remoteEntries.forEach(([key, value]) => {
    const text = String(value);
    let current = null;
    try { current = localStorage.getItem(key); } catch (_) {}
    if (current !== text) {
      try { localStorage.setItem(key, text); changed = true; } catch (_) {}
    }
  });
  return changed;
}

function hasPendingSharedUiPreferenceWrite() {
  return Boolean(uiPreferenceLocalDirty || uiPreferenceSyncTimer || uiPreferenceSyncPending);
}

function scheduleSharedUiPreferenceSync() {
  if (!uiPreferenceSyncInstalled || uiPreferenceApplyingRemote) return;
  uiPreferenceLocalDirty = true;
  if (uiPreferenceSyncTimer) window.clearTimeout(uiPreferenceSyncTimer);
  uiPreferenceSyncTimer = window.setTimeout(() => {
    uiPreferenceSyncTimer = null;
    persistSharedUiPreferencesNow();
  }, 400);
}

async function restoreSharedUiPreferences(options = {}) {
  const applyRuntime = options.applyRuntime === true;
  const seedWebview = options.seedWebview !== false;
  let remote = {};
  try {
    const payload = await apiGet(UI_PREFERENCES_ROUTE, { timeoutMs: 5000 });
    if (payload && typeof payload.storage === "object" && payload.storage !== null) {
      remote = payload.storage;
    }
  } catch (_) {
    return;
  }

  const local = collectSharedUiPreferences();
  const localSerialized = JSON.stringify(local);
  const surface = currentUiPreferenceSurface();
  const remoteEntries = Object.entries(remote).filter(([key]) => isSharedUiPreferenceKey(key));
  const remoteStorage = Object.fromEntries(remoteEntries);
  if (surface !== "tauri" && seedWebview && Object.keys(local).length && JSON.stringify(remoteStorage) !== localSerialized) {
    await persistSharedUiPreferencesNow();
    return;
  }
  if (uiPreferenceSyncInstalled && hasPendingSharedUiPreferenceWrite() && JSON.stringify(remoteStorage) !== localSerialized) {
    await persistSharedUiPreferencesNow();
    return;
  }
  if (remoteEntries.length) {
    uiPreferenceApplyingRemote = true;
    try {
      const changed = applySharedUiPreferenceStorage(remoteStorage);
      if (changed && applyRuntime) applySharedUiPreferenceRuntimeState();
    } finally {
      uiPreferenceApplyingRemote = false;
    }
    uiPreferenceLastSerialized = JSON.stringify(collectSharedUiPreferences());
    uiPreferenceLocalDirty = false;
    return;
  }

  if (surface !== "tauri" && Object.keys(local).length) {
    await persistSharedUiPreferencesNow();
  }
}

function startSharedUiPreferenceRemoteRefresh() {
  if (currentUiPreferenceSurface() !== "tauri" || uiPreferenceRemoteRefreshTimer) return;
  const refresh = () => {
    if (uiPreferenceSyncInFlight || uiPreferenceApplyingRemote) return;
    restoreSharedUiPreferences({ applyRuntime: true, seedWebview: false });
  };
  window.addEventListener("focus", refresh);
  document.addEventListener("visibilitychange", () => {
    if (document.visibilityState === "visible") refresh();
  });
  uiPreferenceRemoteRefreshTimer = window.setInterval(refresh, 3000);
}

function installSharedUiPreferenceStorageSync() {
  if (uiPreferenceSyncInstalled) return;
  uiPreferenceSyncInstalled = true;
  const originalSetItem = Storage.prototype.setItem;
  const originalRemoveItem = Storage.prototype.removeItem;
  Storage.prototype.setItem = function setItemWithUiPreferenceSync(key, value) {
    const result = originalSetItem.call(this, key, value);
    if (this === window.localStorage && isSharedUiPreferenceKey(key)) {
      scheduleSharedUiPreferenceSync();
    }
    return result;
  };
  Storage.prototype.removeItem = function removeItemWithUiPreferenceSync(key) {
    const result = originalRemoveItem.call(this, key);
    if (this === window.localStorage && isSharedUiPreferenceKey(key)) {
      scheduleSharedUiPreferenceSync();
    }
    return result;
  };
}

function initAdvancedToggle() {
  const btn = byId("advanced-toggle");
  if (!btn) return;

  // Restore persisted preference — operators who turn this on stay in advanced
  // mode across reloads without having to toggle it every session.
  applyAdvancedModePreference(readBooleanUiPreference(ADVANCED_MODE_STORAGE_KEY));

  btn.addEventListener("click", () => {
    applyAdvancedModePreference(!document.body.classList.contains("advanced-mode"));
  });
}

function initEvidenceToggle() {
  const btn = byId("evidence-toggle");
  if (!btn) return;

  applyEvidenceHiddenPreference(readBooleanUiPreference(EVIDENCE_HIDDEN_STORAGE_KEY));

  btn.addEventListener("click", () => {
    applyEvidenceHiddenPreference(!document.body.classList.contains("evidence-hidden"));
  });
}

function syncDiagnosticAdvancedCallouts(on) {
  document.querySelectorAll(".diagnostic-callout-advanced[data-advanced]").forEach((node) => {
    node.hidden = !on;
    node.style.display = on ? "" : "none";
  });
}

function applyAdvancedModePreference(on) {
  const btn = byId("advanced-toggle");
  document.body.classList.toggle("advanced-mode", on);
  if (btn) {
    btn.setAttribute("aria-pressed", String(on));
    btn.dataset.state = on ? "on" : "off";
  }
  syncDiagnosticAdvancedCallouts(on);
  try { localStorage.setItem(ADVANCED_MODE_STORAGE_KEY, on ? "1" : "0"); } catch (_) {}
  updatePagePanelEmptyStates();
}

function applyEvidenceHiddenPreference(hidden) {
  const btn = byId("evidence-toggle");
  document.body.classList.toggle("evidence-hidden", hidden);
  if (btn) {
    btn.setAttribute("aria-pressed", String(hidden));
    btn.dataset.state = hidden ? "on" : "off";
    btn.textContent = hidden ? "Show Evidence" : "Hide Evidence";
    btn.title = hidden
      ? "Show read-only evidence panels again."
      : "Hide panels marked as read-only evidence. Interactive controls remain visible.";
  }
  try { localStorage.setItem(EVIDENCE_HIDDEN_STORAGE_KEY, hidden ? "1" : "0"); } catch (_) {}
  updatePagePanelEmptyStates();
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



// ── LAUNCH EVIDENCE COLLAPSE — S3 ────────────────────────────────────────────
// The "Settings Check" evidence panel on the Launch page can be collapsed so
// the operator sees only the heading status and the Start Pipeline section,
// without scrolling past all the evidence sub-panels.
//
// The #launch-evidence-body div (see index.html) gets .is-collapsed toggled.
// State persists to localStorage so operators who prefer collapsed stay collapsed.


// ── S5: COLLAPSIBLE SUMMARIES ─────────────────────────────────────────────────
// For every prose-block <pre> whose immediately-next sibling is a .table-wrap,
// inject a "Show summary / Hide summary" tertiary toggle button before the pre.
// Summary defaults to collapsed so the table is the primary view of each panel.
// Per-summary expand state is persisted to localStorage:
//   key: mediapipeline-summary-<pre id>   value: "1" = expanded, "0" = collapsed
// Elements with no id get no persistence (state resets on reload — acceptable).
// The element stays in the DOM when hidden (pre.hidden = true) so test assertions
// can still read content via #id even when the summary is collapsed.


// ── THEME TOGGLE — Stage 15 ───────────────────────────────────────────────────
// Adds/removes body.light-mode class. Persists choice to localStorage.
// On first load (no stored preference) defaults to dark mode.

// Keyboard shortcut implementation lives in app/lifecycle.js; these wrappers preserve
// the tested app.js public contract and read-only safety language.
function activeKeyboardPage() {
  return window.mediaPipelineAppLifecycle?.activeKeyboardPage?.() || "home";
}

function activeKeyboardPanel() {
  return window.mediaPipelineAppLifecycle?.activeKeyboardPanel?.() || null;
}

function shortcutTypingTarget(target) {
  return Boolean(window.mediaPipelineAppLifecycle?.shortcutTypingTarget?.(target));
}

function shortcutElementVisible(node) {
  return Boolean(window.mediaPipelineAppLifecycle?.shortcutElementVisible?.(node));
}

function focusActivePageSearch() {
  return Boolean(window.mediaPipelineAppLifecycle?.focusActivePageSearch?.());
}

function dispatchShortcutInputChange(node) {
  return window.mediaPipelineAppLifecycle?.dispatchShortcutInputChange?.(node);
}

function clearActivePageFilters() {
  return Boolean(window.mediaPipelineAppLifecycle?.clearActivePageFilters?.());
}

function activePageSelectableRows() {
  return window.mediaPipelineAppLifecycle?.activePageSelectableRows?.() || [];
}

function moveActivePageSelection(delta) {
  return Boolean(window.mediaPipelineAppLifecycle?.moveActivePageSelection?.(delta));
}

function focusActivePageDetail() {
  return Boolean(window.mediaPipelineAppLifecycle?.focusActivePageDetail?.());
}

function keyboardShortcutRegistry(toggleHelp) {
  return window.mediaPipelineAppLifecycle?.keyboardShortcutRegistry?.(toggleHelp) || [];
}

function keyboardShortcutHelpText(registry) {
  return window.mediaPipelineAppLifecycle?.keyboardShortcutHelpText?.(registry) || "";
}

function initKeyboardShortcuts() {
  return window.mediaPipelineAppLifecycle?.initKeyboardShortcuts?.();
}

void [
  activeKeyboardPage,
  activeKeyboardPanel,
  shortcutTypingTarget,
  shortcutElementVisible,
  focusActivePageSearch,
  dispatchShortcutInputChange,
  clearActivePageFilters,
  activePageSelectableRows,
  moveActivePageSelection,
  focusActivePageDetail,
  keyboardShortcutRegistry,
  keyboardShortcutHelpText,
  "Read-only shortcuts. They navigate, refresh, filter, focus, or select rows",
  'key: "/"',
  'key: "c"',
  'key: "j"',
  'key: "k"',
  'key: "d"',
];

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


















// ── DnD state ────────────────────────────────────────────────────────────────







































// ── Per-panel toggle handlers ─────────────────────────────────────────────────


// ── Init helpers ──────────────────────────────────────────────────────────────


















function _layoutRenderDrawer(options = {}) {
  return window.mediaPipelineAppLayoutManager?._layoutRenderDrawer?.(options);
}

function _movePanelByStep(panel, delta) {
  return window.mediaPipelineAppLayoutManager?._movePanelByStep?.(panel, delta);
}

function applyStoredLayoutPreferences() {
  return window.mediaPipelineAppLayoutManager?.applyStoredLayoutPreferences?.();
}

function applySharedUiPreferenceRuntimeState() {
  return window.mediaPipelineAppLayoutManager?.applySharedUiPreferenceRuntimeState?.();
}

void [
  _layoutRenderDrawer,
  _movePanelByStep,
  applyStoredLayoutPreferences,
  applySharedUiPreferenceRuntimeState,
  "pcb-btn-move-up",
  "pcb-btn-move-down",
];

// ── Main entry point ──────────────────────────────────────────────────────────
function initLayoutManager() {
  return window.mediaPipelineAppLayoutManager?.initLayoutManager?.();
}

document.addEventListener("DOMContentLoaded", async () => {
  renderBrandVersion();
  initKeyboardShortcuts();
  await restoreSharedUiPreferences();
  installSharedUiPreferenceStorageSync();
  initNavigation();
  initLayoutManager();
  initAdvancedToggle();
  initEvidenceToggle();
  initThemeToggle();
  initLaunchEvidenceToggle();
  initCollapsibleSummaries();
  window.mediaPipelineDom?.enhanceDataTables?.();
  initPageRefreshButtons();
  initSettingsTabNav();
  initDiagnosticsTabNav();
  initCompletedTabNav();
  startSharedUiPreferenceRemoteRefresh();
  if (typeof applyDiagnosticCallouts === "function") applyDiagnosticCallouts(document);
  window.mediaPipelineDom?.applyProseBoxDispositions?.(document);
  applyDefaultActionTooltips();
  window.addEventListener("mediapipeline:backend-lifecycle", handleTauriBackendLifecycleEvent);
  window.mediaPipelineTauriLifecycleBridge?.replayLatestBackendLifecycleEvent?.();
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
  const renameUsesStandaloneWorkbench = Boolean(byId("rename-apply-button"));
  const renameView = window.mediaPipelineRenameView || {};
  const renamePreviewButton = byId("rename-preview-button");
  if (renamePreviewButton && !renameUsesStandaloneWorkbench) renamePreviewButton.addEventListener("click", () => renameView.refreshRenamePreview?.());
  const renamePreviewTopButton = byId("rename-preview-top-button");
  if (renamePreviewTopButton) renamePreviewTopButton.addEventListener("click", () => renameView.refreshRenamePreview?.());
  const renameUseSelectedQueueButton = byId("rename-use-selected-queue-button");
  if (renameUseSelectedQueueButton) renameUseSelectedQueueButton.addEventListener("click", () => renameView.useSelectedQueueRowForRename?.());
  const renameUseLoadedQueueButton = byId("rename-use-loaded-queue-button");
  if (renameUseLoadedQueueButton) renameUseLoadedQueueButton.addEventListener("click", () => renameView.useLoadedQueueRowsForRename?.());
  const renameBrowseFilesButton = byId("rename-browse-files-button");
  if (renameBrowseFilesButton && !renameUsesStandaloneWorkbench) renameBrowseFilesButton.addEventListener("click", () => renameView.browseRenamePaths?.("files"));
  const renameBrowseFolderButton = byId("rename-browse-folder-button");
  if (renameBrowseFolderButton && !renameUsesStandaloneWorkbench) renameBrowseFolderButton.addEventListener("click", () => renameView.browseRenamePaths?.("folder"));
  const renameAddPathButton = byId("rename-add-path-button");
  if (renameAddPathButton) renameAddPathButton.addEventListener("click", () => renameView.addRenamePathFromInput?.());
  const renameClearPathsButton = byId("rename-clear-paths-button");
  if (renameClearPathsButton && !renameUsesStandaloneWorkbench) renameClearPathsButton.addEventListener("click", () => renameView.clearRenamePaths?.());
  const renameAddPathInput = byId("rename-add-path-input");
  if (renameAddPathInput) {
    renameAddPathInput.addEventListener("input", () => renameView.syncRenameCommandButtons?.());
    renameAddPathInput.addEventListener("keydown", (event) => {
      if (event.key !== "Enter") return;
      event.preventDefault();
      renameView.addRenamePathFromInput?.();
    });
  }
  const renamePaths = byId("rename-paths");
  if (renamePaths) renamePaths.addEventListener("input", () => {
    renameView.renderRenameFileSourceSummary?.();
    renameView.syncRenameCommandButtons?.();
  });
  renameView.renderRenameFileSourceSummary?.();
  const renameSaveOverrideButton = byId("rename-save-override-button");
  if (renameSaveOverrideButton) renameSaveOverrideButton.addEventListener("click", () => renameView.applyRenameSelectedOverride?.());
  const renameClearOverrideButton = byId("rename-clear-override-button");
  if (renameClearOverrideButton) renameClearOverrideButton.addEventListener("click", () => renameView.clearRenameSelectedOverride?.());
  const renameApplySelectedButton = byId("rename-apply-selected-button");
  if (renameApplySelectedButton && !renameUsesStandaloneWorkbench) renameApplySelectedButton.addEventListener("click", () => renameView.applySelectedRename?.());
  const renameCheckApplicableButton = byId("rename-check-applicable-button");
  if (renameCheckApplicableButton) renameCheckApplicableButton.addEventListener("click", () => renameView.checkApplicableRenameRows?.());
  const renameClearChecksButton = byId("rename-clear-checks-button");
  if (renameClearChecksButton) renameClearChecksButton.addEventListener("click", () => renameView.clearCheckedRenameRows?.());
  const renameMoveCheckedUpButton = byId("rename-move-checked-up-button");
  if (renameMoveCheckedUpButton) renameMoveCheckedUpButton.addEventListener("click", () => renameView.moveCheckedRenamePaths?.(-1));
  const renameMoveCheckedDownButton = byId("rename-move-checked-down-button");
  if (renameMoveCheckedDownButton) renameMoveCheckedDownButton.addEventListener("click", () => renameView.moveCheckedRenamePaths?.(1));
  const renameNaturalSortButton = byId("rename-natural-sort-button");
  if (renameNaturalSortButton) renameNaturalSortButton.addEventListener("click", () => renameView.naturalSortRenamePaths?.());
  const renameBulkScope = byId("rename-bulk-scope");
  if (renameBulkScope) renameBulkScope.addEventListener("change", () => {
    renameView.renderRenameBulkEditor?.();
    renameView.syncRenameCommandButtons?.();
  });
  const renameBulkStageButton = byId("rename-bulk-stage-button");
  if (renameBulkStageButton) renameBulkStageButton.addEventListener("click", () => renameView.stageRenameBulkEdit?.());
  const renameBulkUsePipelineButton = byId("rename-bulk-use-pipeline-button");
  if (renameBulkUsePipelineButton) renameBulkUsePipelineButton.addEventListener("click", () => renameView.usePipelineNamesForRenameScope?.());
  const renameBulkForceButton = byId("rename-bulk-force-button");
  if (renameBulkForceButton) renameBulkForceButton.addEventListener("click", () => renameView.setRenameBulkForce?.(true));
  const renameBulkClearForceButton = byId("rename-bulk-clear-force-button");
  if (renameBulkClearForceButton) renameBulkClearForceButton.addEventListener("click", () => renameView.setRenameBulkForce?.(false));
  const renameBulkClearButton = byId("rename-bulk-clear-button");
  if (renameBulkClearButton) renameBulkClearButton.addEventListener("click", () => renameView.clearRenameBulkOverrides?.());
  renameView.initRenameCleaningFilterEditorEvents?.();
  // Standalone Rename workbench wiring: 3-step workflow, confirm + result dialogs,
  // mode-based field visibility, drop zone, modern folder picker via folder_files mode.
  renameView.renameInitWorkbenchEvents?.();
  initSettingsViewEvents();
  window.mediaPipelineSettingsLibraries?.initSettingsLibrariesEvents?.({ refreshAll });
  window.mediaPipelineLibraryRouteMap?.initLibraryRouteMapEvents?.({ refreshAll });
  window.mediaPipelineSettingsWizard?.initSettingsWizardEvents?.({
    refreshAll,
    setSettingsCommandBusy: window.mediaPipelineSettingsView?.setSettingsCommandBusy,
    rejectSettingsCommandWhileBusy: window.mediaPipelineSettingsView?.rejectSettingsCommandWhileBusy,
  });
  initLaunchViewEvents();
  window.mediaPipelineMetricsView?.initMetricsViewEvents?.();
  window.mediaPipelineReportsView?.initReportsViewEvents?.();
  window.mediaPipelineScheduleView?.initScheduleViewEvents?.();
  initDiagnosticsViewEvents();
  window.mediaPipelineNetworkView?.initNetworkViewEvents?.();
  window.mediaPipelineContractView?.initContractViewEvents?.();
  const maintenanceView = window.mediaPipelineMaintenanceView || {};
  maintenanceView.initMaintenanceViewEvents?.();
  if (typeof initSampleValidationViewEvents === "function") initSampleValidationViewEvents();
  const pipelineStartButton = byId("pipeline-start-button");
  if (pipelineStartButton) pipelineStartButton.addEventListener("click", startPipelineFromForm);
  const rerunDryRunButton = byId("rerun-dry-run-button");
  if (rerunDryRunButton) rerunDryRunButton.addEventListener("click", () => startRerunFromForm({ dry_run: true }));
  const rerunStartButton = byId("rerun-start-button");
  if (rerunStartButton) rerunStartButton.addEventListener("click", () => startRerunFromForm({ dry_run: false }));
  const pendingDrainButton = byId("pending-drain-button");
  if (pendingDrainButton) pendingDrainButton.addEventListener("click", () => window.mediaPipelineLaunchView?.startPendingPublishDrain?.());
  const pendingRecoveryPlanSelectedButton = byId("pending-recovery-plan-selected-button");
  if (pendingRecoveryPlanSelectedButton) pendingRecoveryPlanSelectedButton.addEventListener("click", () => requestPendingRecoveryPlan("selected"));
  const pendingRecoveryPlanAllButton = byId("pending-recovery-plan-all-button");
  if (pendingRecoveryPlanAllButton) pendingRecoveryPlanAllButton.addEventListener("click", () => requestPendingRecoveryPlan("all"));
  const maintenanceRefreshButton = byId("maintenance-refresh-button");
  if (maintenanceRefreshButton) maintenanceRefreshButton.addEventListener("click", () => maintenanceView.refreshMaintenance?.());
  const releaseDryRunButton = byId("release-dry-run-button");
  if (releaseDryRunButton) releaseDryRunButton.addEventListener("click", () => maintenanceView.runReleaseDryRun?.());
  const releaseBuildButton = byId("release-build-button");
  if (releaseBuildButton) releaseBuildButton.addEventListener("click", () => maintenanceView.runReleaseBuild?.());
  const backfillDryRunButton = byId("backfill-dry-run-button");
  if (backfillDryRunButton) backfillDryRunButton.addEventListener("click", () => maintenanceView.runBackfillDryRun?.());
  const dependencyAtlasButton = byId("dependency-atlas-button");
  if (dependencyAtlasButton) dependencyAtlasButton.addEventListener("click", () => maintenanceView.runDependencyAtlas?.());
  const dependencyAtlasOpenFolderButton = byId("dependency-atlas-open-folder-button");
  if (dependencyAtlasOpenFolderButton) dependencyAtlasOpenFolderButton.addEventListener("click", () => maintenanceView.openDependencyAtlasFolder?.());
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
  const completedLibraryFilter = byId("completed-library-filter");
  if (completedLibraryFilter) completedLibraryFilter.addEventListener("change", () => window.mediaPipelineCompletedView?.renderCompletedRows?.());
  const completedInvestigationFilter = byId("completed-investigation-filter");
  if (completedInvestigationFilter) completedInvestigationFilter.addEventListener("change", () => window.mediaPipelineCompletedView?.renderCompletedRows?.());
  const completedClearFiltersButton = byId("completed-clear-filters-button");
  if (completedClearFiltersButton) completedClearFiltersButton.addEventListener("click", resetCompletedFilters);
  const completedShowSelectedButton = byId("completed-show-selected-button");
  if (completedShowSelectedButton) completedShowSelectedButton.addEventListener("click", () => window.mediaPipelineCompletedView?.showSelectedCompletedRow?.());
  const completedRefreshCurrentOutputButton = byId("completed-refresh-current-output-button");
  if (completedRefreshCurrentOutputButton) completedRefreshCurrentOutputButton.addEventListener("click", refreshCurrentOutputStatus);
  const completedHistoryFilter = byId("completed-history-filter");
  if (completedHistoryFilter) completedHistoryFilter.addEventListener("input", () => window.mediaPipelineCompletedView?.renderCompletedRows?.());
  const completedHistoryStatusFilter = byId("completed-history-status-filter");
  if (completedHistoryStatusFilter) completedHistoryStatusFilter.addEventListener("change", () => window.mediaPipelineCompletedView?.renderCompletedRows?.());
  const completedHistoryInvestigationFilter = byId("completed-history-investigation-filter");
  if (completedHistoryInvestigationFilter) completedHistoryInvestigationFilter.addEventListener("change", () => window.mediaPipelineCompletedView?.renderCompletedRows?.());
  const completedHistoryClearFiltersButton = byId("completed-history-clear-filters-button");
  if (completedHistoryClearFiltersButton) completedHistoryClearFiltersButton.addEventListener("click", () => window.mediaPipelineCompletedView?.resetCompletedHistoryFilters?.());
  document.querySelectorAll("[data-completed-size-column-mode]").forEach((button) => {
    button.addEventListener("click", () => {
      window.mediaPipelineCompletedView?.setCompletedSizeColumnMode?.(button.dataset.completedSizeColumnMode || "size");
    });
  });
  const publishReconciliationRefreshButton = byId("publish-reconciliation-refresh-button");
  if (publishReconciliationRefreshButton) publishReconciliationRefreshButton.addEventListener("click", () => window.mediaPipelineCompletedView?.requestPublishReconciliation?.());
  const completedCopyEvidenceButton = byId("completed-copy-evidence-button");
  if (completedCopyEvidenceButton) completedCopyEvidenceButton.addEventListener("click", () => window.mediaPipelineCompletedView?.copyCompletedEvidencePacket?.());
  const finalLibraryPromoteButton = byId("final-library-promote-button");
  if (finalLibraryPromoteButton) finalLibraryPromoteButton.addEventListener("click", () => window.mediaPipelineCompletedView?.requestFinalLibraryPromotion?.());
  document.querySelectorAll("[data-completed-promote-selected]").forEach((button) => {
    button.addEventListener("click", () => window.mediaPipelineCompletedView?.requestSelectedFinalLibraryPromotion?.());
  });
  const finalLibraryPauseButton = byId("final-library-pause-button");
  if (finalLibraryPauseButton) finalLibraryPauseButton.addEventListener("click", () => window.mediaPipelineCompletedView?.requestFinalLibraryPromotionPause?.());
  const finalLibraryResumeButton = byId("final-library-resume-button");
  if (finalLibraryResumeButton) finalLibraryResumeButton.addEventListener("click", () => window.mediaPipelineCompletedView?.requestFinalLibraryPromotionResume?.());
  const pendingFilter = byId("pending-filter");
  if (pendingFilter) pendingFilter.addEventListener("input", () => window.mediaPipelinePendingPublishView?.renderPendingRows?.());
  const pendingStatusFilter = byId("pending-status-filter");
  if (pendingStatusFilter) pendingStatusFilter.addEventListener("change", () => window.mediaPipelinePendingPublishView?.renderPendingRows?.());
  const pendingInvestigationFilter = byId("pending-investigation-filter");
  if (pendingInvestigationFilter) pendingInvestigationFilter.addEventListener("change", () => window.mediaPipelinePendingPublishView?.renderPendingRows?.());
  const pendingClearFiltersButton = byId("pending-clear-filters-button");
  if (pendingClearFiltersButton) pendingClearFiltersButton.addEventListener("click", () => window.mediaPipelinePendingPublishView?.resetPendingFilters?.());
  const failureFilter = byId("failure-filter");
  if (failureFilter) failureFilter.addEventListener("input", () => window.mediaPipelineReportsView?.renderFailureRows?.());
  const failureSourceMarkers = byId("failure-source-markers");
  if (failureSourceMarkers) failureSourceMarkers.addEventListener("change", refreshAll);
  const auditPreviewFilter = byId("audit-preview-filter");
  if (auditPreviewFilter) auditPreviewFilter.addEventListener("input", () => window.mediaPipelineReportsView?.renderAuditRows?.());
  const auditPreviewPriorityOnly = byId("audit-preview-priority-only");
  if (auditPreviewPriorityOnly) auditPreviewPriorityOnly.addEventListener("change", refreshAll);
  document.querySelectorAll("[data-control-action]").forEach((button) => {
    button.addEventListener("click", () => requestPipelineControl(button.dataset.controlAction || ""));
  });
  document.querySelectorAll("[data-open-diagnostics]").forEach((button) => {
    button.addEventListener("click", () => requestDiagnosticsOpen(button.dataset.openDiagnostics || "", button));
  });
  initBackendRowOpenActions();
  updatePagePanelEmptyStates();
  refreshAll({ automatic: true });
  window.setInterval(() => refreshAll({ automatic: true }), AUTOMATIC_REFRESH_INTERVAL_MS);
});
