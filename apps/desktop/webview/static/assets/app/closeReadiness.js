(function () {
  function unavailableCloseReadiness(reason) {
    const message = String(reason || "Close-readiness is unavailable.");
    return {
      schema_version: "desktop_close_readiness.v1",
      safe_to_close: false,
      active_work: true,
      state: "unavailable",
      operator_status: "unavailable",
      reason: message,
      continuous_watcher: { status: "unavailable" },
      warnings: [message],
      evidence_authority: "frontend-fail-closed-sentinel",
    };
  }

  function normalizeCloseReadiness(payload, unavailableReason = "Close-readiness payload is invalid.") {
    if (!payload || typeof payload !== "object" || Array.isArray(payload)) {
      return unavailableCloseReadiness(unavailableReason);
    }
    const watcher = payload.continuous_watcher;
    const validText = (value) => typeof value === "string" && Boolean(value.trim());
    const validWarnings = Array.isArray(payload.warnings)
      && payload.warnings.every((warning) => typeof warning === "string");
    const validWatcher = watcher && typeof watcher === "object" && !Array.isArray(watcher);
    const validSafeState = ["idle", "completed", "failed", "stale", "stopped"].includes(
      String(payload.state || "").trim().toLowerCase(),
    );
    const watcherStatus = validWatcher ? String(watcher.status || "").trim().toLowerCase() : "";
    const watcherBlocksClose = ["armed", "error"].includes(watcherStatus);
    if (
      payload.schema_version !== "desktop_close_readiness.v1"
      || typeof payload.safe_to_close !== "boolean"
      || typeof payload.active_work !== "boolean"
      || !validText(payload.state)
      || !validText(payload.reason)
      || !validWarnings
      || !validWatcher
      || payload.safe_to_close === payload.active_work
      || (payload.safe_to_close && (!validSafeState || watcherBlocksClose))
    ) {
      return unavailableCloseReadiness(unavailableReason);
    }
    return { ...payload };
  }

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
    unavailableCloseReadiness,
    normalizeCloseReadiness,
    formatCloseReadiness,
    closeReadinessWatcherData,
    closeReadinessWatcherSummary,
    closeReadinessWatcherIsArmed,
    backendLifecycleState,
    closeReadinessRequiresWarning,
    closeReadinessWarningMessage,
  };
})();
