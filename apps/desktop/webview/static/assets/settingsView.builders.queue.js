(function () {
  function createQueueSettingsBuilder(deps) {
    const {
      byId,
      formatSettingsListValue,
      parseSettingsListText,
      queueSettingsBuilderFields,
      queueSettingsBuilderState,
      readSettingsBuilderNumber,
      setText,
      settingsBuilderConfigValue,
      settingsBuilderInputValue,
      settingsFieldDefinition,
      settingsSpecificImpactHints,
      writeSettingsPatchJson,
    } = deps;

    function setQueueBuilderControl(id, key, kind, fallback) {
      const element = byId(id);
      if (!element) return;
      const value = settingsBuilderConfigValue(key, fallback);
      if (kind === "bool") {
        element.checked = value === true || String(value).toLowerCase() === "true";
        return;
      }
      if (kind === "list") {
        element.value = formatSettingsListValue(value);
        return;
      }
      element.value = String(value ?? "");
    }

    function syncQueueSettingsBuilderFromConfig() {
      setQueueBuilderControl("settings-queue-priority-markers", "PriorityMarkers", "list", ["!", "[NOW]"]);
      setQueueBuilderControl("settings-queue-processed-index-refresh", "ProcessedIndexRefreshSeconds", "number", 900);
      setQueueBuilderControl("settings-queue-min-pipeline-version", "MinPipelineVersion", "text", "");
      setQueueBuilderControl("settings-queue-reprocess-all", "ReprocessAll", "bool", false);
      queueSettingsBuilderState.initialized = true;
      queueSettingsBuilderState.dirty = false;
      setText("settings-queue-builder-status", "Loaded current values");
      renderQueueSettingsBuilderGuidance();
    }

    function markQueueSettingsBuilderDirty() {
      queueSettingsBuilderState.initialized = true;
      queueSettingsBuilderState.dirty = true;
      setText("settings-queue-builder-status", "Editing queue values");
      renderQueueSettingsBuilderGuidance();
    }

    function readQueueBuilderValue(id, kind, label) {
      const element = byId(id);
      if (!element) return kind === "bool" ? false : "";
      if (kind === "bool") return element.checked === true;
      if (kind === "list") return parseSettingsListText(settingsBuilderInputValue(id));
      if (kind === "number") return readSettingsBuilderNumber(id, label);
      return settingsBuilderInputValue(id);
    }

    function collectQueueSettingsBuilderPatch() {
      const patch = {};
      queueSettingsBuilderFields.forEach(([key, id, kind]) => {
        const field = settingsFieldDefinition(key);
        patch[key] = readQueueBuilderValue(id, kind, field?.label || key);
      });
      return patch;
    }

    function applyQueueSettingsBuilderToPatch() {
      let patch;
      try {
        patch = collectQueueSettingsBuilderPatch();
      } catch (error) {
        const message = error instanceof Error ? error.message : String(error);
        setText("settings-queue-builder-status", "Invalid queue value");
        setText("settings-patch-status", "Builder invalid");
        setText("settings-patch-detail", message);
        return false;
      }
      writeSettingsPatchJson(patch, "Queue builder prepared priority, processed-index refresh, and reprocess keys for Save Settings. Backend Save still validates before writing.");
      queueSettingsBuilderState.initialized = true;
      queueSettingsBuilderState.dirty = true;
      setText("settings-queue-builder-status", `${Object.keys(patch).length} queue change keys ready`);
      renderQueueSettingsBuilderGuidance();
      return true;
    }

    function renderQueueSettingsBuilderGuidance() {
      const lines = [
        "Guardrail: these values affect discovery and reprocess decisions only; queue mutation and processing starts remain backend-owned.",
      ];
      queueSettingsBuilderFields.forEach(([key, id, kind]) => {
        const field = settingsFieldDefinition(key);
        const label = field?.label || key;
        let valueText;
        if (kind === "bool") {
          valueText = byId(id)?.checked ? "enabled" : "disabled";
        } else if (kind === "list") {
          const values = parseSettingsListText(settingsBuilderInputValue(id));
          valueText = values.length ? values.join(", ") : "(none)";
        } else {
          valueText = settingsBuilderInputValue(id) || "(not set)";
        }
        lines.push(`${label}: ${valueText}`);
        if (field?.help) lines.push(`  ${field.help}`);
        const hint = settingsSpecificImpactHints[key];
        if (hint) lines.push(`  ${hint}`);
        if (key === "ReprocessAll" && byId(id)?.checked) {
          lines.push("  Warning: backend risk preview should flag this before saving; use only when you intentionally want completed outputs reconsidered.");
        }
        if (key === "ProcessedIndexRefreshSeconds" && Number(settingsBuilderInputValue(id)) === 0) {
          lines.push("  Warning: zero disables processed-index caching and can increase repeated output-share scans.");
        }
      });
      setText("settings-queue-guidance", lines.join("\n") || "No queue guidance loaded.");
    }

    return {
      syncQueueSettingsBuilderFromConfig,
      markQueueSettingsBuilderDirty,
      collectQueueSettingsBuilderPatch,
      applyQueueSettingsBuilderToPatch,
      renderQueueSettingsBuilderGuidance,
    };
  }

  window.__settingsViewQueueBuilderModule = {
    createQueueSettingsBuilder,
  };
})();
