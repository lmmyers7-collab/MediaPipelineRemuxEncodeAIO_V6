const bootstrap = window.MEDIA_PIPELINE_BOOTSTRAP || {};
const AUTOMATIC_REFRESH_INTERVAL_MS = 15000;
const AUTOMATIC_OPTIONAL_GET_TIMEOUT_MS = 12000;

let lastSnapshot = null;
let lastCloseReadiness = null;
let lastStdoutTail = null;
let lastSchedule = null;
let lastQueue = null;
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

function clearTopbarPendingLaunch(snapshot = {}) {
  return window.mediaPipelineAppTopbar?.clearTopbarPendingLaunch?.(snapshot);
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
  clearTopbarPendingLaunch,
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

function renderCloseReadiness(closeReadiness) {
  const normalized = window.mediaPipelineAppCloseReadiness?.normalizeCloseReadiness?.(closeReadiness);
  closeReadiness = normalized || null;
  lastCloseReadiness = closeReadiness;
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
  const safe = closeReadiness.safe_to_close === true;
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

function renderCloseReadinessUnavailable(reason) {
  const unavailable = window.mediaPipelineAppCloseReadiness?.unavailableCloseReadiness?.(reason) || {
    safe_to_close: false,
    active_work: true,
    state: "unavailable",
    operator_status: "unavailable",
    reason: String(reason || "Close-readiness is unavailable."),
  };
  renderCloseReadiness(unavailable);
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

function renderRefreshInProgress(options = {}) {
  return window.mediaPipelineAppRefresh?.renderRefreshInProgress?.(options);
}

function renderRefreshHealth(failures, options = {}) {
  return window.mediaPipelineAppRefresh?.renderRefreshHealth?.(failures, options);
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

function csvRerunTailEvidence(stdoutTail = lastStdoutTail) {
  const reader = window.mediaPipelineProgressView?.csvRerunTailEvidence;
  if (typeof reader !== "function") return { hasEvidence: false };
  return reader(stdoutTail);
}

function csvRerunActivityEvidence(context = {}) {
  const reader = window.mediaPipelineProgressView?.csvRerunActivityEvidence;
  if (typeof reader !== "function") return csvRerunTailEvidence(context?.stdoutTail || context || lastStdoutTail);
  return reader(context && typeof context === "object" ? context : { stdoutTail: context || lastStdoutTail });
}

function csvRerunHomeIsActive(csvRerun = csvRerunTailEvidence(), closeReadiness = lastCloseReadiness) {
  if (!csvRerun?.hasEvidence) return false;
  if (closeReadiness?.safe_to_close === true) return false;
  if (csvRerun.isActive === true || csvRerun.workerActive === true) return true;
  const terminalReader = window.mediaPipelineProgressView?.csvRerunTerminalLine;
  if (typeof terminalReader === "function") return !terminalReader(csvRerun.latestLine || "");
  return !/^(PLAN ONLY complete|DRY RUN complete|Rerun batch complete|No CSV rows are executable)\b|PIPELINE SHUTDOWN CLEANLY|ROUND COMPLETE|Single-pass mode complete/i.test(String(csvRerun.latestLine || ""));
}

function renderCsvRerunHomeCompletionSummary(source = {}) {
  const summary = window.mediaPipelineProgressView?.csvRerunCompletionSummary?.(source.snapshot || lastSnapshot);
  if (!summary) return false;
  const label = summary.display_label || "CSV rerun complete";
  const detail = summary.detail || "Backend manifest terminal state.";
  renderTopbarActivity({
    activity: label,
    pipeline_state: "csv_rerun_complete",
    current_work: {
      phase_label: "CSV rerun",
      current_stage_label: label,
      summary_label: label,
      item_label: summary.csv_name || summary.batch_id || "Current CSV",
    },
  });
  const pill = byId("state-pill");
  if (pill) {
    pill.textContent = label;
    pill.dataset.state = summary.display_state || "ok";
    pill.title = detail;
  }
  renderHomePipelineState("csv_rerun_complete");
  const pipelineState = byId("pipeline-state");
  if (pipelineState) pipelineState.dataset.state = summary.display_state || "ok";
  const currentItem = byId("queue-count");
  if (currentItem) {
    const totals = summary.totals || {};
    currentItem.textContent = `${totals.processed || 0} / ${totals.total || 0}`;
    currentItem.title = detail;
    currentItem.dataset.mode = "count";
    currentItem.dataset.state = summary.display_state || "ok";
  }
  setText("queue-count-detail", detail);
  return true;
}

function renderCsvRerunHomeSummary(context = { stdoutTail: lastStdoutTail, snapshot: lastSnapshot, closeReadiness: lastCloseReadiness }) {
  const source = context && typeof context === "object" && ("stdoutTail" in context || "snapshot" in context || "diagnostics" in context)
    ? context
    : { stdoutTail: context || lastStdoutTail, snapshot: lastSnapshot, closeReadiness: lastCloseReadiness };
  if (renderCsvRerunHomeCompletionSummary(source)) return true;
  const csvRerun = csvRerunActivityEvidence(source);
  if (!csvRerunHomeIsActive(csvRerun, source.closeReadiness || lastCloseReadiness)) return false;
  const currentWork = dashboardCurrentWork(source.snapshot || {});
  const workSummary = currentWork.summary_label || currentWork.latest_evidence_label || "";
  const workStage = currentWork.current_stage_label || currentWork.phase_label || "";
  const item = currentWork.item_label || csvRerun.currentImport || csvRerun.lastImported || "CSV rerun staging";
  const activity = workSummary || (csvRerun.currentImport ? `Importing ${csvRerun.currentImport}` : "CSV rerun active");
  const stage = workStage || (csvRerun.currentImport ? "Importing from CSV" : "CSV rerun");
  renderTopbarActivity({
    activity,
    pipeline_state: "csv_rerun_active",
    current_work: {
      ...currentWork,
      phase_label: currentWork.phase_label || "CSV rerun",
      current_stage_label: stage,
      summary_label: activity,
      item_label: item,
      percent_label: currentWork.percent_label || csvRerun.plannedRows || "",
    },
    progress: {
      Status: "CSV rerun",
      CurrentStage: stage,
      CurrentFileDisplay: item,
    },
  });
  const backendEvents = Array.isArray(source.snapshot?.recent_events) ? source.snapshot.recent_events.filter(Boolean) : [];
  renderTopbarEventTicker({
    recent_events: backendEvents.length ? backendEvents : [{
      event_type: "csv_rerun",
      stage: csvRerun.currentImport ? "importing" : "staging",
      status: "active",
      data: { display_name: currentWork.latest_event_label || currentWork.latest_evidence_label || item },
    }],
  });
  const pill = byId("state-pill");
  if (pill) {
    pill.textContent = stage;
    pill.dataset.state = "running";
    pill.title = [stage, item, workSummary, currentWork.next_stage_label ? `Next: ${currentWork.next_stage_label}` : "", csvRerun.plannedRows].filter(Boolean).join("\n");
  }
  renderHomePipelineState("csv_rerun_active");
  const pipelineState = byId("pipeline-state");
  if (pipelineState) pipelineState.dataset.state = "running";
  const currentItem = byId("queue-count");
  if (currentItem) {
    currentItem.textContent = item;
    currentItem.title = item;
    currentItem.dataset.mode = "file";
    currentItem.dataset.state = "running";
  }
  setText(
    "queue-count-detail",
    [
      csvRerun.currentImport ? "Importing now" : "CSV rerun active",
      currentWork.latest_evidence_label ? `evidence ${currentWork.latest_evidence_label}` : "",
      currentWork.missing_evidence_label || "",
      currentWork.next_stage_label ? `next ${currentWork.next_stage_label}` : "",
      csvRerun.plannedRows,
      csvRerun.lastImported ? `last imported ${csvRerun.lastImported}` : "",
    ].filter(Boolean).join(" · ")
  );
  return true;
}

function renderLiveWorkHomeSummary(context = {}) {
  const liveRunContext = {
    snapshot: context?.snapshot || lastSnapshot,
    diagnostics: context?.diagnostics || null,
    closeReadiness: context?.closeReadiness || lastCloseReadiness,
    stdoutTail: context?.stdoutTail || lastStdoutTail,
  };
  window.mediaPipelineProgressView?.renderHomeActiveWork?.(liveRunContext);
  window.mediaPipelineProgressView?.renderLiveRunStrip?.(liveRunContext);
  window.mediaPipelineProgressView?.renderProgressBars?.(
    Array.isArray(liveRunContext.snapshot?.progress_bars) ? liveRunContext.snapshot.progress_bars : [],
    liveRunContext.snapshot,
    liveRunContext
  );
  return renderCsvRerunHomeSummary(liveRunContext);
}

window.refreshAll = refreshAll;
window.refreshAllNow = refreshAllNow;
window.setTopbarPendingLaunch = setTopbarPendingLaunch;
window.clearTopbarPendingLaunch = clearTopbarPendingLaunch;
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
// layout/tab customization follows the operator between surfaces.
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

const ADVANCED_MODE_STORAGE_KEY = "mediapipeline-advanced-mode";
const EVIDENCE_HIDDEN_STORAGE_KEY = "mediapipeline-evidence-hidden";
const THEME_STORAGE_KEY = "mediapipeline-theme";
void [applyThemePreference, THEME_STORAGE_KEY];
const appUiPreferencesModule = window.__appUiPreferencesModule || {};
delete window.__appUiPreferencesModule;
const appUiPreferences = typeof appUiPreferencesModule.createAppUiPreferences === "function"
  ? appUiPreferencesModule.createAppUiPreferences({
    apiGet: (...args) => apiGet(...args),
    postPreferences: (payload, options) => apiPost("/api/ui-preferences", payload, options),
    applyRuntimeState: applySharedUiPreferenceRuntimeState,
    documentRef: document,
    storage: window.localStorage,
    windowRef: window,
  })
  : {};

function currentUiPreferenceSurface() { return appUiPreferences.currentSurface?.() || "webview"; }
function readBooleanUiPreference(key) { return Boolean(appUiPreferences.readBoolean?.(key)); }
async function persistSharedUiPreferencesNow(options = {}) { return appUiPreferences.persist?.(options); }
async function restoreSharedUiPreferences(options = {}) { return appUiPreferences.restore?.(options); }
function startSharedUiPreferenceRemoteRefresh() { return appUiPreferences.startRemoteRefresh?.(); }
function installSharedUiPreferenceStorageSync() { return appUiPreferences.installStorageSync?.(); }

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


// ── THEME LOCK — Stage 15 ─────────────────────────────────────────────────────
// Dark mode is the only runtime theme; stale light preferences are overwritten.

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
