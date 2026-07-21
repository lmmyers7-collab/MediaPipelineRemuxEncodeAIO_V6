// Queue source-scan request and refresh handoff. Loaded before queueView.js.
(function () {
  function createQueueScanModule(deps = {}) {
    const getScanInFlight = typeof deps.getScanInFlight === "function" ? deps.getScanInFlight : () => false;
    const setScanInFlight = typeof deps.setScanInFlight === "function" ? deps.setScanInFlight : () => {};
    const apiPost = typeof deps.apiPost === "function" ? deps.apiPost : async () => ({});
    const appendCommandResult = typeof deps.appendCommandResult === "function" ? deps.appendCommandResult : () => {};
    const setText = typeof deps.setText === "function" ? deps.setText : () => {};
    const refreshAll = typeof deps.refreshAll === "function" ? deps.refreshAll : null;
    const renderQueueSourceInventoryMessage = typeof deps.renderQueueSourceInventoryMessage === "function" ? deps.renderQueueSourceInventoryMessage : () => {};
    const setQueueFilterSummary = typeof deps.setQueueFilterSummary === "function" ? deps.setQueueFilterSummary : () => {};
    const scheduleQueueScanPoll = typeof deps.scheduleQueueScanPoll === "function" ? deps.scheduleQueueScanPoll : () => {};
    const setQueueLoadingScreenVisible = typeof deps.setQueueLoadingScreenVisible === "function" ? deps.setQueueLoadingScreenVisible : () => {};
    const renderQueueRows = typeof deps.renderQueueRows === "function" ? deps.renderQueueRows : () => {};
    const queueScanIsRunning = typeof deps.queueScanIsRunning === "function" ? deps.queueScanIsRunning : () => false;

  async function requestQueueScan() {
    if (getScanInFlight()) {
      const result = {
        command: "queue.scan",
        ok: false,
        severity: "warning",
        message: "A Queue source scan request is already being submitted.",
      };
      if (typeof appendCommandResult === "function") appendCommandResult(result);
      setText("queue-open-status", result.message);
      return result;
    }
    setScanInFlight(true);
    window.mediaPipelineAppRefresh?.renderQueueRefreshInProgress?.();
    renderQueueSourceInventoryMessage([
      "Queue source scan requested.",
      "Waiting for backend source inventory and queue curation status.",
      "This command is plan-only; backend routes own processing and media mutation.",
    ], "info");
    try {
      const result = await apiPost("/api/queue/scan", {
        mode: "inventory_then_curate",
        force: true,
        scope: "all",
        reason: "operator_requested_queue_scan",
      }, { timeoutMs: 10000 });
      if (typeof appendCommandResult === "function") appendCommandResult(result);
      setText("queue-open-status", result.message || "Queue source scan command accepted.");
      if (typeof refreshAll === "function") {
        await refreshAll({ queueRefresh: true });
      } else {
        setQueueFilterSummary("Queue source scan started, but refresh wiring is not loaded.");
      }
      scheduleQueueScanPoll();
      return result;
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      const result = {
        command: "queue.scan",
        ok: false,
        severity: "error",
        message: `Queue source scan request failed: ${message}`,
        errors: [message],
      };
      if (typeof appendCommandResult === "function") appendCommandResult(result);
      setQueueLoadingScreenVisible(false);
      renderQueueRows();
      setText("queue-open-status", result.message);
      renderQueueSourceInventoryMessage([
        result.message,
        "Safe next step: inspect Diagnostics and backend command history before trying again.",
      ], "danger");
      return result;
    } finally {
      setScanInFlight(false);
      window.mediaPipelineAppRefresh?.setQueueRefreshButtonBusy?.(queueScanIsRunning());
    }
  }

    return { requestQueueScan };
  }
  window.__queueScanModule = { createQueueScanModule };
})();
