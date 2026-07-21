/* Read-only API refresh coordination, payload shaping, and cross-page rendering handoffs. */
function normalizeRefreshOptions(options = {}) {
  return {
    automatic: Boolean(options && options.automatic === true),
    queueRefresh: Boolean(options && options.queueRefresh === true),
    initialCritical: Boolean(options && options.initialCritical === true),
    page: String(options?.page || "").trim().toLowerCase(),
  };
}

function mergeRefreshOptions(existing, next) {
  const current = normalizeRefreshOptions(existing || {});
  const incoming = normalizeRefreshOptions(next || {});
  return {
    automatic: current.automatic && incoming.automatic,
    queueRefresh: current.queueRefresh || incoming.queueRefresh,
    initialCritical: current.initialCritical && incoming.initialCritical,
    page: incoming.page || current.page,
  };
}

const CORE_REFRESH_REQUESTS = new Set(["health", "snapshot", "close readiness", "telemetry"]);
const PAGE_REFRESH_REQUESTS = {
  home: new Set(["diagnostics", "last stdout tail", "diagnostics state summary", "commands", "rerun results", "queue", "completed", "pending publish", "schedule", "watch folders", "settings", "libraries summary", "network workers", "sample validation", "recovery status"]),
  launch: new Set(["commands", "rerun results", "queue", "schedule", "watch folders", "settings", "network workers"]),
  metrics: new Set(["metrics"]),
  queue: new Set(["queue", "commands", "rerun results"]),
  completed: new Set(["completed", "pending publish"]),
  pending: new Set(["pending publish", "completed"]),
  rename: new Set([]),
  reports: new Set(["failures", "failure artifacts", "audit results", "audit controls", "audit sources"]),
  network: new Set(["network workers", "settings", "rerun results"]),
  libraries: new Set(["libraries summary", "libraries route map", "settings"]),
  schedule: new Set(["schedule", "watch folders", "settings"]),
  settings: new Set(["settings", "preset library"]),
  diagnostics: new Set(["diagnostics", "last stdout tail", "diagnostics state summary", "commands", "recovery status"]),
  maintenance: new Set(["productization"]),
};

function activeRefreshPage(options = {}) {
  const requested = String(options?.page || "").trim().toLowerCase();
  if (requested) return requested;
  return String(document.querySelector("[data-page-panel].is-visible")?.dataset?.pagePanel || "home").trim().toLowerCase() || "home";
}

function refreshRequestIncluded(name, page, options = {}) {
  if (options.initialCritical) return CORE_REFRESH_REQUESTS.has(name);
  return CORE_REFRESH_REQUESTS.has(name) || Boolean(PAGE_REFRESH_REQUESTS[page]?.has(name));
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

async function refreshLiveRunTail(refreshOptions = {}) {
  try {
    const stdoutTail = await refreshGet(
      "/api/diagnostics/tail?target=last_stdout_log&max_bytes=65536",
      refreshOptions,
      { timeoutMs: 5000 }
    );
    lastStdoutTail = attachRefreshMetadata("last stdout tail", stdoutTail);
    const liveRunContext = {
      snapshot: lastSnapshot,
      diagnostics: lastDiagnostics,
      closeReadiness: lastCloseReadiness,
      stdoutTail: lastStdoutTail,
    };
    renderLiveWorkHomeSummary(liveRunContext);
  } catch (_error) {
    // The full refresh path owns route error reporting; this fast path keeps Home responsive.
  }
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
  const refreshPage = activeRefreshPage(refreshOptions);
  lastRefreshStartedAt = new Date();
  const refreshStartedMs = Date.now();
  const refreshStartScrollSnapshot = window.mediaPipelineDom?.captureScrollablePositions?.();
  renderRefreshInProgress(refreshOptions);
  const runMonitorRequest = refreshPage === "home"
    ? window.mediaPipelineRunMonitor?.refresh?.({ automatic: true })
    : null;
  void refreshLiveRunTail(refreshOptions);
  window.mediaPipelineDom?.restoreScrollablePositions?.(refreshStartScrollSnapshot);
  const failureSourceMarkers = Boolean(byId("failure-source-markers")?.checked);
  const failureQuery = `/api/failures?limit=100${failureSourceMarkers ? "&source=markers" : ""}`;
  const auditPriorityOnly = Boolean(byId("audit-preview-priority-only")?.checked);
  const auditQuery = `/api/audit-results?limit=100${auditPriorityOnly ? "&priority_only=true" : ""}`;
  const requestDefinitions = [
    ["health", "/api/health", false], ["snapshot", "/api/snapshot", true], ["close readiness", "/api/backend/close-readiness", false], ["telemetry", "/api/telemetry", false],
    ["diagnostics", "/api/diagnostics", false], ["last stdout tail", "/api/diagnostics/tail?target=last_stdout_log&max_bytes=65536", false], ["diagnostics state summary", "/api/diagnostics/state-summary", false], ["commands", "/api/commands?limit=20", false], ["rerun results", "/api/rerun/results?limit=24", false], ["metrics", "/api/metrics", false], ["queue", "/api/queue", false], ["completed", "/api/completed?limit=500", false], ["failures", failureQuery, false], ["failure artifacts", "/api/failures/artifacts", false], ["audit results", auditQuery, false], ["audit controls", "/api/audit-controls", false], ["audit sources", "/api/audit-sources", false], ["pending publish", "/api/pending-publish", false], ["schedule", "/api/schedule", false], ["watch folders", "/api/watch-folders/status", false], ["settings", "/api/settings/workspace", false], ["preset library", "/api/settings/preset-library", false], ["libraries summary", "/api/libraries/summary", false], ["libraries route map", "/api/libraries/route-map", false], ["network workers", "/api/network/workers", false], ["sample validation", "/api/sample-validation?limit=10", false], ["recovery status", "/api/backend/recovery-status", false], ["productization", "/api/maintenance/productization", false],
  ];
  const requests = requestDefinitions
    .filter(([name]) => refreshRequestIncluded(name, refreshPage, refreshOptions))
    .map(([name, path, required]) => [name, refreshGet(path, refreshOptions, { required }), required]);
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
  if (Object.prototype.hasOwnProperty.call(values, "diagnostics")) {
    lastDiagnostics = values.diagnostics;
  }
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
  const snapshotFailure = failures.find((item) => item.name === "snapshot");
  const closeReadinessFailure = failures.find((item) => item.name === "close readiness");
  if (snapshotFailure || closeReadinessFailure) {
    const policyFailure = closeReadinessFailure || snapshotFailure;
    renderCloseReadinessUnavailable(
      `Current close policy is unavailable because ${policyFailure.name} failed: ${policyFailure.message}`,
    );
  } else if (values["close readiness"]) {
    renderCloseReadiness(values["close readiness"]);
  } else {
    renderCloseReadinessUnavailable("Current close-readiness response was missing.");
  }
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
  if (values.diagnostics) {
    renderDiagnostics(values.diagnostics);
    window.mediaPipelineFloatingPipelineLog?.renderFloatingPipelineLog?.(values.diagnostics);
  }
  const renderDiagnosticsStateSummaryFn = window.mediaPipelineDiagnosticsStateSummaryView?.renderDiagnosticsStateSummary;
  if (values["diagnostics state summary"] && typeof renderDiagnosticsStateSummaryFn === "function") {
    renderDiagnosticsStateSummaryFn(values["diagnostics state summary"]);
  }
  if (values.commands) window.mediaPipelineCommandHistory?.renderCommandHistoryPayload?.(values.commands);
  if (values["rerun results"]) window.mediaPipelineQueueView?.renderRerunResults?.(values["rerun results"]);
  const metricsFailure = failures.find((item) => item.name === "metrics");
  if (values.metrics) {
    window.mediaPipelineMetricsView?.renderMetrics?.(values.metrics);
  } else {
    window.mediaPipelineMetricsView?.renderMetricsUnavailable?.(
      metricsFailure?.message || "Metrics route returned no current payload.",
    );
  }
  if (values.queue) {
    lastQueue = values.queue;
    window.mediaPipelineQueueView?.renderQueue?.(values.queue);
    window.mediaPipelineProvenanceView?.renderQueueProvenance?.(window.mediaPipelineQueueView?.getSelectedQueueRow?.());
  }
  const latestQueue = values.queue || lastQueue || {};
  renderHomeQueueSnapshot(latestQueue);
  renderHomePipelineQueueOutcome(values.snapshot || lastSnapshot, latestQueue);
  if (values.completed) {
    window.mediaPipelineCompletedView?.renderCompleted?.(values.completed);
    window.mediaPipelineProvenanceView?.renderCompletedProvenance?.(window.mediaPipelineCompletedView?.getSelectedCompletedRow?.());
  }
  window.mediaPipelineRunMonitor?.reapplyTerminalHandoff?.("completed");
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
  const reportsView = window.mediaPipelineReportsView;
  const failureReadFailure = failures.find((item) => item.name === "failures");
  if (values.failures && values.failures.availability !== "unavailable" && !values.failures.error) {
    reportsView?.renderFailurePreview?.(values.failures);
    reportsView?.markReportsComponentFresh?.("failures", values.failures);
  } else {
    reportsView?.renderReportsUnavailable?.(
      "failures",
      values.failures?.error || failureReadFailure?.message || "Failure evidence read returned no current payload.",
    );
  }
  if (values["failure artifacts"]) {
    window.mediaPipelineReportsView?.renderFailureArtifactSummary?.(values["failure artifacts"]);
    window.mediaPipelineOperatorToast?.showFailureArtifactWarning?.(values["failure artifacts"]);
    reportsView?.markReportsComponentFresh?.("artifacts", values["failure artifacts"]);
  } else {
    reportsView?.renderReportsUnavailable?.(
      "artifacts",
      failures.find((item) => item.name === "failure artifacts")?.message || "Failure artifact evidence is unavailable.",
    );
  }
  if (values["audit results"] && !values["audit results"].error) {
    window.mediaPipelineReportsView?.renderAuditPreview?.(values["audit results"]);
    reportsView?.markReportsComponentFresh?.("audit", values["audit results"]);
  } else {
    reportsView?.renderReportsUnavailable?.(
      "audit",
      values["audit results"]?.error || failures.find((item) => item.name === "audit results")?.message || "Audit results are unavailable.",
    );
  }
  if (values["audit controls"]) {
    window.mediaPipelineReportsView?.renderAuditControls?.(values["audit controls"]);
    reportsView?.markReportsComponentFresh?.("controls", values["audit controls"]);
  } else {
    reportsView?.renderReportsUnavailable?.(
      "controls",
      failures.find((item) => item.name === "audit controls")?.message || "Audit controls are unavailable.",
    );
  }
  if (values["audit sources"]) {
    window.mediaPipelineReportsView?.renderReportAuditSources?.(values["audit sources"]);
    reportsView?.markReportsComponentFresh?.("sources", values["audit sources"]);
  } else {
    reportsView?.renderReportsUnavailable?.(
      "sources",
      failures.find((item) => item.name === "audit sources")?.message || "Audit sources are unavailable.",
    );
  }
  window.mediaPipelineRunMonitor?.reapplyTerminalHandoff?.("reports");
  if (values["pending publish"] || pendingPublishFailure) renderPendingPublish(pendingPublishPayload, values.snapshot || lastSnapshot);
  window.mediaPipelineRunMonitor?.reapplyTerminalHandoff?.("pending");
  renderHomePendingCount(pendingPublishPayload);
  if (values.schedule) {
    lastSchedule = values.schedule;
    window.mediaPipelineScheduleView?.renderSchedule?.(values.schedule);
  }
  lastStdoutTail = values["last stdout tail"] || lastStdoutTail;
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
    window.mediaPipelineSettingsView.renderSettings(values.settings);
    window.mediaPipelinePresetLibraryView?.renderLibrary?.(values["preset library"]?.data || values["preset library"] || {});
    window.mediaPipelineSettingsLibraries?.renderSettingsLibraries?.(values.settings, refreshOptions);
    window.mediaPipelineReportsView?.renderReports?.(lastSnapshot, window.mediaPipelineSettingsView.getLastSettings());
    window.mediaPipelineLaunchView?.renderAllLaunchPreflights?.();
  }
  if (values["recovery status"]) window.mediaPipelineRecoverySupportView?.renderRecoveryStatus?.(values["recovery status"]);
  if (values.productization) window.mediaPipelineRecoverySupportView?.renderProductization?.(values.productization?.data || values.productization);
  if (values["libraries summary"]) {
    window.mediaPipelineSettingsLibraries?.renderLibrarySummary?.(values["libraries summary"]);
  }
  if (values["libraries route map"]) {
    window.mediaPipelineLibraryRouteMap?.renderRouteMap?.(values["libraries route map"], {
      queue: latestQueue,
      completed: values.completed || {},
      sampleValidation: values["sample validation"] || {},
    });
  }
  if (values.contract) window.mediaPipelineContractView?.renderContract?.(values.contract);
  const renderNetworkViewFn = window.mediaPipelineNetworkView?.renderNetworkView;
  if (typeof renderNetworkViewFn === "function") {
    renderNetworkViewFn({
      settings: values.settings || window.mediaPipelineSettingsView.getLastSettings(),
      contract: values.contract || {},
      closeReadiness: values["close readiness"] || lastCloseReadiness,
      snapshot: values.snapshot || lastSnapshot,
      queue: latestQueue,
      networkWorkers: values["network workers"] || null,
      rerunResults: values["rerun results"] || {},
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
    settings: values.settings || window.mediaPipelineSettingsView.getLastSettings(),
    stateSummary: values["diagnostics state summary"] || {},
    maintenance: window.mediaPipelineMaintenanceView?.getLastMaintenance?.() || {},
  };
  renderExternalDependencyDigest(dependencyContext);
  renderLaunchReadinessPanel({
    snapshot: values.snapshot || lastSnapshot,
    closeReadiness: values["close readiness"] || lastCloseReadiness,
    schedule: values.schedule || lastSchedule,
    settings: values.settings || window.mediaPipelineSettingsView.getLastSettings(),
    failures,
  });
  const liveRunContext = {
    snapshot: values.snapshot || lastSnapshot,
    diagnostics: lastDiagnostics,
    closeReadiness: values["close readiness"] || lastCloseReadiness,
    stdoutTail: values["last stdout tail"] || lastStdoutTail,
  };
  renderLiveWorkHomeSummary(liveRunContext);
  const launchPanel = document.querySelector('[data-page-panel="launch"]');
  const launchVisible = Boolean(launchPanel && !launchPanel.hidden && launchPanel.getAttribute("aria-hidden") !== "true");
  const launchAlertVisible = Boolean(document.querySelector(".launch-preflight-startup-alert"));
  const launchView = window.mediaPipelineLaunchView || {};
  if (
    typeof launchView.refreshLaunchBackendPreflight === "function"
    && (!refreshOptions.automatic || launchVisible || launchAlertVisible)
  ) {
    try {
      await launchView.refreshLaunchBackendPreflight();
    } catch (error) {
      failures.push({
        name: "launch backend preflight",
        required: false,
        message: error instanceof Error ? error.message : String(error),
      });
    }
  }
  launchView.renderLaunchCompactGate?.();
  launchView.updateLaunchCommandButtonStates?.(
    values.snapshot || lastSnapshot,
    values["close readiness"] || lastCloseReadiness
  );
  window.mediaPipelineProgressView?.renderProgressEvidence?.({
    snapshot: values.snapshot || lastSnapshot,
    closeReadiness: values["close readiness"] || lastCloseReadiness,
    diagnostics: lastDiagnostics,
  });
  window.mediaPipelineProgressView?.renderDiagnosticsProgress?.(values.snapshot || lastSnapshot, lastDiagnostics);
  if (typeof renderCrossPageContext === "function") {
    const crossPageContext = {
      snapshot: values.snapshot || lastSnapshot,
      closeReadiness: values["close readiness"] || lastCloseReadiness,
      queue: latestQueue,
      completed: values.completed || {},
      pending: pendingPublishPayload,
      diagnostics: lastDiagnostics || {},
      settings: values.settings || window.mediaPipelineSettingsView.getLastSettings(),
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
      diagnostics: lastDiagnostics || {},
      stateSummary: values["diagnostics state summary"] || {},
      commands: values.commands || {},
      queue: latestQueue,
      completed: values.completed || {},
      pending: pendingPublishPayload,
      settings: values.settings || window.mediaPipelineSettingsView.getLastSettings(),
      sampleValidation: values["sample validation"] || {},
      maintenance: window.mediaPipelineMaintenanceView?.getLastMaintenance?.() || {},
      failures,
    };
    const renderDiagnosticsFirstResponseFn = window.mediaPipelineDiagnosticsView?.renderDiagnosticsFirstResponse;
    if (typeof renderDiagnosticsFirstResponseFn === "function") {
      renderDiagnosticsFirstResponseFn(diagnosticsContext);
    }
    renderDiagnosticsInvestigationTrail(diagnosticsContext);
    window.mediaPipelineProvenanceView?.renderDiagnosticsProvenance?.(diagnosticsContext);
  }
  const renderDiagnosticsOwnerHandoffFn = window.mediaPipelineDiagnosticsView?.renderDiagnosticsOwnerHandoff;
  if (typeof renderDiagnosticsOwnerHandoffFn === "function") {
    renderDiagnosticsOwnerHandoffFn({
      queue: latestQueue,
      completed: values.completed || {},
      pending: pendingPublishPayload,
      sampleValidation: values["sample validation"] || {},
      settings: values.settings || window.mediaPipelineSettingsView.getLastSettings(),
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
    settings: values.settings || window.mediaPipelineSettingsView.getLastSettings(),
    stateSummary: values["diagnostics state summary"] || {},
    maintenance: window.mediaPipelineMaintenanceView?.getLastMaintenance?.() || {},
    queue: latestQueue,
    completed: values.completed || {},
    pending: pendingPublishPayload,
    diagnostics: lastDiagnostics || {},
    networkWorkers: values["network workers"] || {},
    failuresPayload: values.failures || {},
    failureArtifacts: values["failure artifacts"] || {},
    auditResults: values["audit results"] || {},
    stdoutTail: values["last stdout tail"] || lastStdoutTail,
    failures,
  };
  renderHomeStorageHealth(dashboardContext);
  renderDailyDriverReadiness(dashboardContext);
  if (runMonitorRequest && typeof runMonitorRequest.then === "function") await runMonitorRequest;
  window.mediaPipelineDom?.applyProseBoxDispositions?.(document);
  } finally {
    window.mediaPipelineDom?.restoreScrollablePositions?.(scrollSnapshot);
  }
}
