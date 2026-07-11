(function () {
  function createNetworkEventsModule(deps = {}) {
    const { byId, renderNetworkWorkerRows, syncNetworkWorkerViewPresetButtons, previewNetworkSettingsPatch, saveNetworkSettingsPatch, runNetworkLifecycleCommand, runNetworkWorkerTestConnection, openNetworkDrawer, createNetworkJoinBlob, copyNetworkJoinBlob, importNetworkJoinBlob, discoverNetworkCoordinators, stageDiscoveredCoordinatorUrl, renderNetworkJoinControls, settingsConfig, getLastNetworkLifecyclePayload, getLastNetworkWorkersPayload, getNetworkViewEventsInitialized, setNetworkViewEventsInitialized, getNetworkWorkerSearchText, setNetworkWorkerSearchText, getNetworkWorkerStatusFilter, setNetworkWorkerStatusFilter, getNetworkWorkerViewPreset, setNetworkWorkerViewPreset } = deps;
      function initNetworkViewEvents() {
      if (getNetworkViewEventsInitialized()) return;
      setNetworkViewEventsInitialized(true);
        const workerFilter = byId("network-worker-filter");
        if (workerFilter) {
          workerFilter.addEventListener("input", () => {
          setNetworkWorkerSearchText(workerFilter.value || "");
          renderNetworkWorkerRows(getLastNetworkWorkersPayload());
          });
        }
        const statusFilter = byId("network-worker-status-filter");
        if (statusFilter) {
          statusFilter.addEventListener("change", () => {
          setNetworkWorkerStatusFilter(statusFilter.value || "");
          renderNetworkWorkerRows(getLastNetworkWorkersPayload());
          });
        }
        document.querySelectorAll("[data-network-worker-view]").forEach((button) => {
          button.addEventListener("click", () => {
          setNetworkWorkerViewPreset(button.dataset.networkWorkerView || "");
          syncNetworkWorkerViewPresetButtons();
          renderNetworkWorkerRows(getLastNetworkWorkersPayload());
          });
        });
        const openQueueRerunButton = byId("network-open-queue-rerun-button");
        if (openQueueRerunButton) {
          openQueueRerunButton.addEventListener("click", () => {
            if (typeof window.showPage === "function") window.showPage("queue");
            document.querySelector('[data-queue-tab="rerun"]')?.click();
          });
        }
        const previewSettingsButton = byId("network-settings-preview-button");
        if (previewSettingsButton) previewSettingsButton.addEventListener("click", previewNetworkSettingsPatch);
        const saveSettingsButton = byId("network-settings-save-button");
        if (saveSettingsButton) saveSettingsButton.addEventListener("click", saveNetworkSettingsPatch);
        document.querySelectorAll("[data-network-lifecycle-role]").forEach((button) => {
          button.addEventListener("click", () => runNetworkLifecycleCommand(button));
        });
        document.querySelectorAll("[data-network-test-connection]").forEach((button) => {
          button.addEventListener("click", () => runNetworkWorkerTestConnection());
        });
        document.querySelectorAll("[data-network-open-drawer]").forEach((button) => {
          button.addEventListener("click", () => openNetworkDrawer(button.dataset.networkOpenDrawer || ""));
        });
        const createJoinButton = byId("network-coordinator-join-create");
        if (createJoinButton) createJoinButton.addEventListener("click", () => createNetworkJoinBlob());
        const copyJoinButton = byId("network-coordinator-join-copy");
        if (copyJoinButton) copyJoinButton.addEventListener("click", () => copyNetworkJoinBlob());
        const importJoinButton = byId("network-worker-join-import");
        if (importJoinButton) importJoinButton.addEventListener("click", () => importNetworkJoinBlob());
        const discoverButton = byId("network-worker-discover");
        if (discoverButton) discoverButton.addEventListener("click", () => discoverNetworkCoordinators());
        const discoveryList = byId("network-worker-discovery-list");
        if (discoveryList) {
          discoveryList.addEventListener("click", (event) => {
            const button = event.target?.closest?.("[data-network-discovery-url]");
            if (!button) return;
            stageDiscoveredCoordinatorUrl(button.dataset.networkDiscoveryUrl || "");
          });
        }
        const workerJoinBlob = byId("network-worker-join-blob");
        if (workerJoinBlob) {
          workerJoinBlob.addEventListener("input", () => {
          const payload = getLastNetworkLifecyclePayload();
          renderNetworkJoinControls(payload, settingsConfig(payload.settings || {}));
          });
        }
      }

    return { initNetworkViewEvents };
  }

  window.__networkEventsModule = { createNetworkEventsModule };
})();
