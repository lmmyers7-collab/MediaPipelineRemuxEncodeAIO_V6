// Network settings-patch handoff controls; backend Settings owns persistence.
(function () {
  "use strict";

  function createNetworkSettingsHandoffModule(deps = {}) {
    const { byId = () => null, setText = () => {}, windowRef = window } = deps;

  function networkSettingsPatchStatusText() {
    const raw = byId("settings-patch-status")?.textContent || "none";
    const text = String(raw || "none").trim();
    if (!text || text.toLowerCase() === "no patch") return "Staged Patch: none";
    return text.toLowerCase().startsWith("staged patch:") ? text : `Staged Patch: ${text}`;
  }

  function renderNetworkSettingsPatchHandoff(message = "") {
    const patchStatus = networkSettingsPatchStatusText();
    const patchText = byId("settings-patch-json")?.value || "{}";
    let patchKeys = [];
    try {
      const patch = JSON.parse(patchText);
      if (patch && typeof patch === "object" && !Array.isArray(patch)) {
        patchKeys = Object.keys(patch);
      }
    } catch (_error) {
      patchKeys = ["invalid JSON"];
    }
    setText("network-settings-control-status", patchStatus);
    setText("network-settings-patch-handoff", [
      message,
      `Saved settings patch status: ${patchStatus}`,
      `Staged keys: ${patchKeys.length ? patchKeys.join(", ") : "none"}`,
      "Preview Settings Patch calls the backend settings preview route and does not write the PSD1.",
      "Save Distributed Settings calls the backend settings save route, asks for confirmation, and creates the normal config backup before writing.",
      "Runtime boundary: settings controls only stage, preview, and save config. Start/Stop must use the backend Network Lifecycle controls.",
    ].filter(Boolean).join("\n"));
  }

  async function previewNetworkSettingsPatch() {
    const preview = windowRef.mediaPipelineSettingsView?.previewSettingsPatch;
    if (typeof preview !== "function") {
      setText("network-settings-control-status", "Settings unavailable");
      renderNetworkSettingsPatchHandoff("Settings preview controls are not loaded.");
      return;
    }
    setText("network-settings-control-status", "Previewing...");
    renderNetworkSettingsPatchHandoff("Previewing staged Saved Distributed Mode Settings through backend validation.");
    await preview();
    renderNetworkSettingsPatchHandoff("Saved Distributed Mode Settings preview command finished.");
  }

  async function saveNetworkSettingsPatch() {
    const save = windowRef.mediaPipelineSettingsView?.saveSettingsPatch;
    if (typeof save !== "function") {
      setText("network-settings-control-status", "Settings unavailable");
      renderNetworkSettingsPatchHandoff("Settings save controls are not loaded.");
      return;
    }
    setText("network-settings-control-status", "Saving...");
    renderNetworkSettingsPatchHandoff("Saving staged Saved Distributed Mode Settings through the backend settings route.");
    await save();
    renderNetworkSettingsPatchHandoff("Saved Distributed Mode Settings save command finished.");
  }
    return {
      networkSettingsPatchStatusText,
      renderNetworkSettingsPatchHandoff,
      previewNetworkSettingsPatch,
      saveNetworkSettingsPatch,
    };
  }

  window.__networkSettingsHandoffModule = { createNetworkSettingsHandoffModule };
})();
