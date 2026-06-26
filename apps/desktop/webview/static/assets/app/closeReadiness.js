(function () {
  function formatCloseReadiness(closeReadiness) {
    return window.mediaPipelineAppLifecycle?.formatCloseReadiness?.(closeReadiness) || "Close readiness has not loaded yet.";
  }

  function closeReadinessWatcherData(closeReadiness) {
    return window.mediaPipelineAppLifecycle?.closeReadinessWatcherData?.(closeReadiness) || {};
  }

  function closeReadinessWatcherSummary(closeReadiness) {
    return window.mediaPipelineAppLifecycle?.closeReadinessWatcherSummary?.(closeReadiness) || "unknown";
  }

  function closeReadinessWatcherIsArmed(closeReadiness) {
    return Boolean(window.mediaPipelineAppLifecycle?.closeReadinessWatcherIsArmed?.(closeReadiness));
  }

  function backendLifecycleState(closeReadiness) {
    return window.mediaPipelineAppLifecycle?.backendLifecycleState?.(closeReadiness) || {
      label: "Waiting",
      state: "unknown",
      canShutdown: false,
      reason: "Close-readiness has not loaded yet.",
    };
  }

  function closeReadinessRequiresWarning(closeReadiness, snapshot) {
    if (closeReadiness && closeReadiness.safe_to_close === false) return true;
  const state = String(snapshot?.pipeline_state || "").toLowerCase();
  return Boolean(state && !["idle", "completed", "failed", "stale"].includes(state));
}

  function closeReadinessWarningMessage(closeReadiness) {
    return closeReadiness?.reason || "Active MediaPipeline work may still be running. Close anyway?";
  }

  window.mediaPipelineAppCloseReadiness = {
    formatCloseReadiness,
    closeReadinessWatcherData,
    closeReadinessWatcherSummary,
    closeReadinessWatcherIsArmed,
    backendLifecycleState,
    closeReadinessRequiresWarning,
    closeReadinessWarningMessage,
  };
})();
