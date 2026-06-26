(function () {
  const FALLBACK_MESSAGE = "Native log window is unavailable in this browser surface. Showing Diagnostics > Logs instead.";

  function byId(id) {
    return document.getElementById(id);
  }

  function setButtonBusy(button, busy) {
    if (!button) return;
    button.disabled = Boolean(busy);
    button.dataset.state = busy ? "loading" : "";
  }

  function setLaunchStatus(message, state) {
    const status = byId("pipeline-launch-status");
    if (!status) return;
    status.textContent = message;
    status.dataset.state = state || "unknown";
  }

  function openBrowserLogWindow() {
    if (typeof window.open !== "function") return null;
    return window.open(
      "/assets/pipelineLogWindow.html?surface=pipeline-log",
      "mediapipeline-pipeline-log",
      "popup,width=980,height=680"
    );
  }

  function showDiagnosticsLogsFallback() {
    if (typeof window.showPage === "function") window.showPage("diagnostics");
    const diagnosticsLogsTab = document.querySelector('[data-page-panel="diagnostics"] .settings-tab-btn[data-diag-tab="logs"]');
    if (diagnosticsLogsTab) diagnosticsLogsTab.click();
    const pipelineLogStatus = byId("diagnostics-pipeline-log-status");
    if (pipelineLogStatus) {
      pipelineLogStatus.textContent = "Native window unavailable";
      pipelineLogStatus.dataset.state = "warning";
    }
    setLaunchStatus("Diagnostics log view opened", "warning");
  }

  async function openPipelineLogWindow(sourceButton) {
    setButtonBusy(sourceButton, true);
    try {
      const logWindow = openBrowserLogWindow();
      if (!logWindow) {
        showDiagnosticsLogsFallback();
        return { opened: false, fallback: true };
      }
      if (typeof logWindow.focus === "function") logWindow.focus();
      setLaunchStatus("Pipeline Log window opened", "ok");
      return { opened: true, fallback: false };
    } catch (error) {
      const message = error && error.message ? error.message : String(error || "Unable to open Pipeline Log window.");
      if (sourceButton) sourceButton.title = message;
      setLaunchStatus("Pipeline Log window failed", "blocked");
      showDiagnosticsLogsFallback();
      return { opened: false, fallback: true, error: message };
    } finally {
      setButtonBusy(sourceButton, false);
    }
  }

  function bindOpenButton(id) {
    const button = byId(id);
    if (!button || button.dataset.pipelineLogWindowBound === "true") return;
    button.dataset.pipelineLogWindowBound = "true";
    button.addEventListener("click", () => openPipelineLogWindow(button));
  }

  function initPipelineLogWindowBridgeEvents() {
    bindOpenButton("launch-open-pipeline-log-window-button");
  }

  /**
   * Public namespace for the Pipeline Log window bridge module.
   * Prefer this namespace from new code; flat window.* exports are intentionally not added for this bridge.
   */
  window.mediaPipelinePipelineLogWindowBridge = {
    initPipelineLogWindowBridgeEvents,
    openPipelineLogWindow,
    openBrowserLogWindow,
    showDiagnosticsLogsFallback,
    fallbackMessage: FALLBACK_MESSAGE,
  };
})();
