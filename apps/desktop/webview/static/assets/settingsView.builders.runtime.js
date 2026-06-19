(function () {
  function createRuntimeSettingsBuilder(deps) {
    const {
      byId,
      readSettingsBuilderNumber,
      refreshSettingsSelectChoices,
      runtimeSettingsBuilderFields,
      runtimeSettingsBuilderState,
      setSettingsBuilderControl,
      setText,
      settingsBuilderConfigValue,
      settingsBuilderInputValue,
      settingsFieldDefinition,
      settingsSpecificImpactHints,
      writeSettingsPatchJson,
    } = deps;

    function setRuntimeBuilderControl(id, key, kind, fallback) {
      const element = byId(id);
      if (!element) return;
      const value = settingsBuilderConfigValue(key, fallback);
      if (kind === "bool") {
        element.checked = value === true || String(value).toLowerCase() === "true";
        return;
      }
      setSettingsBuilderControl(id, value);
    }

    function syncRuntimeSettingsBuilderFromConfig() {
      refreshSettingsSelectChoices(runtimeSettingsBuilderFields);
      setRuntimeBuilderControl("settings-runtime-debug-mode", "DebugMode", "bool", false);
      setRuntimeBuilderControl("settings-runtime-console-log", "ConsoleLogLevel", "select", "");
      setRuntimeBuilderControl("settings-runtime-file-log", "FileLogLevel", "select", "");
      setRuntimeBuilderControl("settings-runtime-log-retention", "LogRetentionDays", "number", 7);
      setRuntimeBuilderControl("settings-runtime-ffmpeg-encode-timeout", "FFmpegEncodeTimeoutSeconds", "number_positive", 21600);
      setRuntimeBuilderControl("settings-runtime-ffmpeg-remux-timeout", "FFmpegRemuxTimeoutSeconds", "number_positive", 7200);
      setRuntimeBuilderControl("settings-runtime-cpu-encode-timeout", "FFmpegCpuEncodeTimeoutSeconds", "number_positive", 43200);
      setRuntimeBuilderControl("settings-runtime-mkvmerge-timeout", "MkvmergeRemuxTimeoutSeconds", "number_positive", 7200);
      setRuntimeBuilderControl("settings-runtime-robocopy-timeout", "RobocopyTimeoutSeconds", "number_positive", 14400);
      setRuntimeBuilderControl("settings-runtime-source-scan-interval", "SourceScanIntervalSeconds", "number_positive", 300);
      setRuntimeBuilderControl("settings-runtime-source-scan-timeout", "SourceScanTimeoutSeconds", "number_positive", 1800);
      setRuntimeBuilderControl("settings-runtime-index-scan-timeout", "IndexScanTimeoutSeconds", "number_positive", 1800);
      setRuntimeBuilderControl("settings-runtime-cleanup-scan-timeout", "CleanupScanTimeoutSeconds", "number_positive", 300);
      setRuntimeBuilderControl("settings-runtime-transient-retry-limit", "TransientFailureRetryLimit", "number", 3);
      setRuntimeBuilderControl("settings-runtime-allow-system-tools", "AllowSystemTools", "bool", false);
      runtimeSettingsBuilderState.initialized = true;
      runtimeSettingsBuilderState.dirty = false;
      setText("settings-runtime-builder-status", "Loaded current values");
      renderRuntimeSettingsBuilderGuidance();
    }

    function markRuntimeSettingsBuilderDirty() {
      runtimeSettingsBuilderState.initialized = true;
      runtimeSettingsBuilderState.dirty = true;
      setText("settings-runtime-builder-status", "Editing runtime values");
      renderRuntimeSettingsBuilderGuidance();
    }

    function readRuntimeBuilderValue(id, kind, label) {
      const element = byId(id);
      if (!element) return kind === "bool" ? false : "";
      if (kind === "bool") return element.checked === true;
      if (kind === "number_positive") {
        const value = readSettingsBuilderNumber(id, label);
        if (value < 1) throw new Error(`${label} must be one or higher.`);
        return value;
      }
      if (kind === "number") return readSettingsBuilderNumber(id, label);
      return settingsBuilderInputValue(id);
    }

    function collectRuntimeSettingsBuilderPatch() {
      const patch = {};
      runtimeSettingsBuilderFields.forEach(([key, id, kind]) => {
        const field = settingsFieldDefinition(key);
        patch[key] = readRuntimeBuilderValue(id, kind, field?.label || key);
      });
      return patch;
    }

    function applyRuntimeSettingsBuilderToPatch() {
      let patch;
      try {
        patch = collectRuntimeSettingsBuilderPatch();
      } catch (error) {
        const message = error instanceof Error ? error.message : String(error);
        setText("settings-runtime-builder-status", "Invalid runtime value");
        setText("settings-patch-status", "Builder invalid");
        setText("settings-patch-detail", message);
        return false;
      }
      writeSettingsPatchJson(patch, "Runtime builder prepared scan, timeout, retry, logging, and tool-fallback keys for Save Settings. Backend Save still validates before writing.");
      runtimeSettingsBuilderState.initialized = true;
      runtimeSettingsBuilderState.dirty = true;
      setText("settings-runtime-builder-status", `${Object.keys(patch).length} runtime change keys ready`);
      renderRuntimeSettingsBuilderGuidance();
      return true;
    }

    function renderRuntimeSettingsBuilderGuidance() {
      const lines = [
        "Guardrail: these values affect long-running process ceilings, scan cadence, retry escalation, and diagnostic log volume.",
      ];
      runtimeSettingsBuilderFields.forEach(([key, id, kind]) => {
        const field = settingsFieldDefinition(key);
        const label = field?.label || key;
        const valueText = kind === "bool"
          ? (byId(id)?.checked ? "enabled" : "disabled")
          : (settingsBuilderInputValue(id) || "(not set)");
        lines.push(`${label}: ${valueText}`);
        if (field?.help) lines.push(`  ${field.help}`);
        const hint = settingsSpecificImpactHints[key];
        if (hint) lines.push(`  ${hint}`);
        if (key === "AllowSystemTools" && byId(id)?.checked) {
          lines.push("  Warning: release validation should normally use bundled tools, not PATH fallback.");
        }
        if (key === "DebugMode" && byId(id)?.checked) {
          lines.push("  Warning: debug mode can generate noisy logs during unattended runs.");
        }
        if (key === "LogRetentionDays" && Number(settingsBuilderInputValue(id)) === 0) {
          lines.push("  Warning: zero-day retention can remove forensic logs quickly after failures.");
        }
      });
      setText("settings-runtime-guidance", lines.join("\n") || "No runtime guidance loaded.");
    }

    return {
      syncRuntimeSettingsBuilderFromConfig,
      markRuntimeSettingsBuilderDirty,
      collectRuntimeSettingsBuilderPatch,
      applyRuntimeSettingsBuilderToPatch,
      renderRuntimeSettingsBuilderGuidance,
    };
  }

  window.__settingsViewRuntimeBuilderModule = {
    createRuntimeSettingsBuilder,
  };
})();
