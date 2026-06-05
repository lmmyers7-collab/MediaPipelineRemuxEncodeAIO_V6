(function () {
  function createNetworkSettingsBuilder(deps) {
    const {
      byId,
      formatSettingsChoiceLabel,
      networkSettingsBuilderFields,
      networkSettingsBuilderState,
      readSettingsBuilderNumber,
      refreshSettingsSelectChoices,
      setSettingsBuilderControl,
      setText,
      settingsBuilderConfigValue,
      settingsBuilderInputValue,
      settingsFieldDefinition,
      writeSettingsPatchJson,
    } = deps;

    function setNetworkBuilderControl(id, key, kind, fallback) {
      const element = byId(id);
      if (!element) return;
      const value = settingsBuilderConfigValue(key, fallback);
      if (kind === "bool") {
        element.checked = value === true || String(value).toLowerCase() === "true";
        return;
      }
      if (kind === "json_text" && value && typeof value === "object") {
        element.value = JSON.stringify(value, null, 2);
        return;
      }
      setSettingsBuilderControl(id, value);
    }

    function syncNetworkSettingsBuilderFromConfig() {
      refreshSettingsSelectChoices(networkSettingsBuilderFields);
      setNetworkBuilderControl("settings-network-role", "NetworkRole", "select", "standalone");
      setNetworkBuilderControl("settings-network-coordinator-port", "CoordinatorPort", "port", 7830);
      setNetworkBuilderControl("settings-network-bind-address", "CoordinatorBindAddress", "text", "0.0.0.0");
      setNetworkBuilderControl("settings-network-coordinator-local-encode", "CoordinatorAlsoEncodeLocally", "bool", false);
      setNetworkBuilderControl("settings-network-heartbeat-timeout", "CoordinatorHeartbeatTimeoutMins", "number_positive", 5);
      setNetworkBuilderControl("settings-network-worker-url", "WorkerCoordinatorUrl", "text", "");
      setNetworkBuilderControl("settings-network-worker-name", "WorkerName", "text", "");
      setNetworkBuilderControl("settings-network-worker-poll", "WorkerPollIntervalSecs", "number_positive", 10);
      setNetworkBuilderControl("settings-network-path-map", "WorkerSourcePathMap", "json_text", "");
      setNetworkBuilderControl("settings-network-worker-overrides", "WorkerConfigOverrides", "json_text", "");
      networkSettingsBuilderState.initialized = true;
      networkSettingsBuilderState.dirty = false;
      setText("settings-network-builder-status", "Loaded current values");
      renderNetworkSettingsBuilderGuidance();
      window.mediaPipelineNetworkView?.renderNetworkSettingsPatchHandoff?.("Worker mode controls loaded from saved backend settings.");
    }

    function markNetworkSettingsBuilderDirty() {
      networkSettingsBuilderState.initialized = true;
      networkSettingsBuilderState.dirty = true;
      setText("settings-network-builder-status", "Editing network values");
      renderNetworkSettingsBuilderGuidance();
      window.mediaPipelineNetworkView?.renderNetworkSettingsPatchHandoff?.("Worker mode settings changed locally. Stage, preview, and save before relying on them.");
    }

    function readNetworkJsonText(id, label) {
      const value = settingsBuilderInputValue(id);
      if (!value) return "";
      try {
        const parsed = JSON.parse(value);
        if (!parsed || Array.isArray(parsed) || typeof parsed !== "object") {
          throw new Error(`${label} must be a JSON object.`);
        }
      } catch (error) {
        const message = error instanceof Error ? error.message : String(error);
        throw new Error(`${label} must be valid JSON object text: ${message}`);
      }
      return value;
    }

    function readNetworkBuilderValue(id, kind, label) {
      const element = byId(id);
      if (!element) return kind === "bool" ? false : "";
      if (kind === "bool") return element.checked === true;
      if (kind === "port") {
        const port = readSettingsBuilderNumber(id, label);
        if (port < 1 || port > 65535) throw new Error(`${label} must be between 1 and 65535.`);
        return port;
      }
      if (kind === "number_positive") {
        const value = readSettingsBuilderNumber(id, label);
        if (value < 1) throw new Error(`${label} must be one or higher.`);
        return value;
      }
      if (kind === "json_text") return readNetworkJsonText(id, label);
      return settingsBuilderInputValue(id);
    }

    function collectNetworkSettingsBuilderPatch() {
      const patch = {};
      networkSettingsBuilderFields.forEach(([key, id, kind]) => {
        const field = settingsFieldDefinition(key);
        patch[key] = readNetworkBuilderValue(id, kind, field?.label || key);
      });
      return patch;
    }

    function applyNetworkSettingsBuilderToPatch() {
      let patch;
      try {
        patch = collectNetworkSettingsBuilderPatch();
      } catch (error) {
        const message = error instanceof Error ? error.message : String(error);
        setText("settings-network-builder-status", "Invalid network value");
        setText("settings-patch-status", "Builder invalid");
        setText("settings-patch-detail", message);
        return;
      }
      writeSettingsPatchJson(patch, "Workers tab merged role, coordinator, worker, and path-map keys into Changes JSON. Preview or Save still uses backend validation.");
      networkSettingsBuilderState.initialized = true;
      networkSettingsBuilderState.dirty = true;
      setText("settings-network-builder-status", `${Object.keys(patch).length} network patch keys ready`);
      renderNetworkSettingsBuilderGuidance();
      window.mediaPipelineNetworkView?.renderNetworkSettingsPatchHandoff?.("Worker mode settings staged into the shared Settings patch JSON.");
    }

    function renderNetworkSettingsBuilderGuidance() {
      const role = settingsBuilderInputValue("settings-network-role") || "standalone";
      const lines = [
        `Role: ${formatSettingsChoiceLabel(role)}`,
        "Location: these controls live on the Workers tab because they affect coordinator, standalone, and worker behavior.",
        "Lifecycle guardrail: this builder only stages config values. Start/stop coordinator and worker runtime remains backend-owned during the transition.",
        "Auth-token guardrail: CoordinatorAuthToken and WorkerAuthToken are intentionally excluded from this builder to avoid accidental token churn.",
      ];
      networkSettingsBuilderFields.forEach(([key, id, kind]) => {
        const field = settingsFieldDefinition(key);
        const label = field?.label || key;
        let valueText = "";
        if (kind === "bool") {
          valueText = byId(id)?.checked ? "enabled" : "disabled";
        } else {
          valueText = settingsBuilderInputValue(id) || "(not set)";
        }
        lines.push(`${label}: ${valueText}`);
        if (field?.help) lines.push(`  ${field.help}`);
        if (key === "WorkerSourcePathMap" && valueText !== "(not set)") {
          lines.push("  Validate path rewrites on the worker before running unattended network claims.");
        }
        if (key === "WorkerConfigOverrides" && valueText !== "(not set)") {
          lines.push("  Keep overrides limited to worker-specific encode tuning; global policy should stay in normal settings.");
        }
      });
      setText("settings-network-guidance", lines.join("\n") || "No network guidance loaded.");
    }

    return {
      syncNetworkSettingsBuilderFromConfig,
      markNetworkSettingsBuilderDirty,
      collectNetworkSettingsBuilderPatch,
      applyNetworkSettingsBuilderToPatch,
      renderNetworkSettingsBuilderGuidance,
    };
  }

  window.__settingsViewNetworkBuilderModule = {
    createNetworkSettingsBuilder,
  };
})();
