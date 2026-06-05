(function () {
  function startupProgressLines(progress) {
    return window.mediaPipelineAppLifecycle?.startupProgressLines?.(progress) || ["Startup progress: not reported by backend bootstrap."];
  }

  function normalizeTauriBackendLifecycleEvent(payload) {
    return window.mediaPipelineAppLifecycle?.normalizeTauriBackendLifecycleEvent?.(payload) || {
      schema_version: "unknown",
      status: "unknown",
      detail: "No lifecycle detail was reported.",
      consecutive_failures: 0,
      emitted_at_unix_seconds: 0,
    };
  }

  function tauriBackendLifecycleLines(event) {
    return window.mediaPipelineAppLifecycle?.tauriBackendLifecycleLines?.(event) || [];
  }

  function renderTauriBackendLifecycleAlert(event) {
    return window.mediaPipelineAppLifecycle?.renderTauriBackendLifecycleAlert?.(event);
  }

  window.mediaPipelineAppTauriLifecycle = {
    startupProgressLines,
    normalizeTauriBackendLifecycleEvent,
    tauriBackendLifecycleLines,
    renderTauriBackendLifecycleAlert,
  };
})();
