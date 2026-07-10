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
      warnings: [message],
      evidence_authority: "frontend-fail-closed-sentinel",
    };
  }

  function normalizeCloseReadiness(payload, unavailableReason = "Close-readiness payload is invalid.") {
    if (!payload || typeof payload !== "object" || Array.isArray(payload)) {
      return unavailableCloseReadiness(unavailableReason);
    }
    if (typeof payload.safe_to_close !== "boolean") {
      return unavailableCloseReadiness(unavailableReason);
    }
    if (Object.prototype.hasOwnProperty.call(payload, "active_work") && typeof payload.active_work !== "boolean") {
      return unavailableCloseReadiness(unavailableReason);
    }
    return {
      ...payload,
      active_work: typeof payload.active_work === "boolean" ? payload.active_work : !payload.safe_to_close,
    };
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
