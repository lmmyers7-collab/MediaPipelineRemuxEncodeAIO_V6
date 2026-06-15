(function () {
  function createQualityDetailSettingsBuilder(deps) {
    const {
      byId,
      formatSettingsChoiceLabel,
      qualityDetailSettingsBuilderFields,
      qualityDetailSettingsBuilderState,
      readSettingsBuilderFloat,
      readSettingsBuilderNumber,
      refreshSettingsSelectChoices,
      renderSettingsActiveMediaPolicyHandoff,
      setSettingsBuilderControl,
      setText,
      settingsBuilderConfigValue,
      settingsBuilderInputValue,
      settingsFieldDefinition,
      settingsSpecificImpactHints,
      writeSettingsPatchJson,
    } = deps;

    function setQualityBuilderControl(id, key, kind, fallback) {
      const element = byId(id);
      if (!element) return;
      const value = settingsBuilderConfigValue(key, fallback);
      if (kind === "bool") {
        element.checked = value === true || String(value).toLowerCase() === "true";
        return;
      }
      setSettingsBuilderControl(id, value);
    }

    function syncQualityDetailSettingsBuilderFromConfig() {
      refreshSettingsSelectChoices(qualityDetailSettingsBuilderFields);
      setQualityBuilderControl("settings-builder-quality-enable", "EnableQualityVerification", "bool", false);
      setQualityBuilderControl("settings-builder-quality-metric", "QualityMetric", "select", "vmaf");
      setQualityBuilderControl("settings-builder-quality-sample-mode", "QualitySampleMode", "select", "sampled");
      setQualityBuilderControl("settings-builder-quality-sample-seconds", "QualitySampleSeconds", "number_positive", 10);
      setQualityBuilderControl("settings-builder-quality-sample-count", "QualitySampleCount", "number_positive", 3);
      setQualityBuilderControl("settings-builder-quality-warn-threshold", "QualityWarnThreshold", "number_float_nonnegative", 90);
      setQualityBuilderControl("settings-builder-quality-fail-threshold", "QualityFailThreshold", "number_float_nonnegative", 75);
      setQualityBuilderControl("settings-builder-quality-fail-action", "QualityFailAction", "select", "warn_only");
      setQualityBuilderControl("settings-builder-quality-timeout", "QualityVerifyTimeoutSeconds", "number_positive", 1800);
      qualityDetailSettingsBuilderState.initialized = true;
      qualityDetailSettingsBuilderState.dirty = false;
      setText("settings-quality-builder-status", "Loaded current values");
      renderQualityDetailSettingsBuilderGuidance();
      renderSettingsActiveMediaPolicyHandoff();
    }

    function markQualityDetailSettingsBuilderDirty() {
      qualityDetailSettingsBuilderState.initialized = true;
      qualityDetailSettingsBuilderState.dirty = true;
      setText("settings-quality-builder-status", "Editing quality verification values");
      renderQualityDetailSettingsBuilderGuidance();
      renderSettingsActiveMediaPolicyHandoff();
    }

    function readQualityBuilderValue(id, kind, label) {
      const element = byId(id);
      if (!element) return kind === "bool" ? false : "";
      if (kind === "bool") return element.checked === true;
      if (kind === "number_positive") {
        const value = readSettingsBuilderNumber(id, label);
        if (value < 1) throw new Error(`${label} must be one or higher.`);
        return value;
      }
      if (kind === "number_float_nonnegative") {
        const value = readSettingsBuilderFloat(id, label);
        if (value < 0) throw new Error(`${label} must be zero or higher.`);
        return value;
      }
      return settingsBuilderInputValue(id);
    }

    function collectQualityDetailSettingsBuilderPatch() {
      const patch = {};
      qualityDetailSettingsBuilderFields.forEach(([key, id, kind]) => {
        const field = settingsFieldDefinition(key);
        patch[key] = readQualityBuilderValue(id, kind, field?.label || key);
      });
      return patch;
    }

    function applyQualityDetailSettingsBuilderToPatch() {
      let patch;
      try {
        patch = collectQualityDetailSettingsBuilderPatch();
      } catch (error) {
        const message = error instanceof Error ? error.message : String(error);
        setText("settings-quality-builder-status", "Invalid quality verification value");
        setText("settings-patch-status", "Builder invalid");
        setText("settings-patch-detail", message);
        return false;
      }
      writeSettingsPatchJson(patch, "Quality verification builder merged metric, sampling, threshold, action, and timeout keys into Changes JSON. Preview or Save still uses backend validation.");
      qualityDetailSettingsBuilderState.initialized = true;
      qualityDetailSettingsBuilderState.dirty = true;
      setText("settings-quality-builder-status", `${Object.keys(patch).length} quality verification patch keys ready`);
      renderQualityDetailSettingsBuilderGuidance();
      renderSettingsActiveMediaPolicyHandoff();
      return true;
    }

    function qualityBuilderValueText(id, kind) {
      if (kind === "bool") return byId(id)?.checked ? "enabled" : "disabled";
      if (kind === "select") return formatSettingsChoiceLabel(settingsBuilderInputValue(id) || "");
      return settingsBuilderInputValue(id) || "(not set)";
    }

    function renderQualityDetailSettingsBuilderGuidance() {
      const enabled = byId("settings-builder-quality-enable")?.checked === true;
      const metric = settingsBuilderInputValue("settings-builder-quality-metric") || "vmaf";
      const sampleMode = settingsBuilderInputValue("settings-builder-quality-sample-mode") || "sampled";
      const warnThreshold = Number(settingsBuilderInputValue("settings-builder-quality-warn-threshold") || 0);
      const failThreshold = Number(settingsBuilderInputValue("settings-builder-quality-fail-threshold") || 0);
      const timeoutSeconds = Number(settingsBuilderInputValue("settings-builder-quality-timeout") || 0);
      const lines = [
        "Guardrail: quality verification runs after lossy encodes only. Remux/direct-copy paths do not run this check.",
        enabled
          ? "Mode: objective quality verification is enabled for future lossy encodes."
          : "Mode: objective quality verification is disabled; existing output validation still applies.",
      ];
      qualityDetailSettingsBuilderFields.forEach(([key, id, kind]) => {
        const field = settingsFieldDefinition(key);
        const label = field?.label || key;
        const valueText = qualityBuilderValueText(id, kind);
        lines.push(`${label}: ${valueText}`);
        const choiceHelp = field?.choice_help && settingsBuilderInputValue(id) ? field.choice_help[settingsBuilderInputValue(id)] : "";
        if (choiceHelp) {
          lines.push(`  ${choiceHelp}`);
        } else if (field?.help) {
          lines.push(`  ${field.help}`);
        }
        const hint = settingsSpecificImpactHints[key];
        if (hint) lines.push(`  ${hint}`);
      });
      if (enabled && metric === "vmaf" && sampleMode === "full") {
        lines.push("", "Review: full-file VMAF can be expensive on long movies; sampled mode is the safer default for routine runs.");
      }
      if (enabled && warnThreshold > 0 && failThreshold > 0 && failThreshold > warnThreshold) {
        lines.push("", "Review: fail threshold is higher than warn threshold. For higher-is-better metrics, fail is usually lower than warn.");
      }
      if (enabled && timeoutSeconds > 0 && timeoutSeconds < 300) {
        lines.push("", "Review: short quality-verification timeouts can produce fail-open error evidence on large or slow samples.");
      }
      if (byId("settings-builder-quality-fail-action")?.value === "block_review") {
        lines.push("", "Warning: block_review rejects below-floor encodes before publish and routes the source for operator review.");
      }
      lines.push("", "Operator action: merge, Preview Patch, review backend risk summary, then save only when the thresholds match the selected metric.");
      setText("settings-quality-guidance", lines.join("\n") || "No quality verification guidance loaded.");
    }

    return {
      syncQualityDetailSettingsBuilderFromConfig,
      markQualityDetailSettingsBuilderDirty,
      collectQualityDetailSettingsBuilderPatch,
      applyQualityDetailSettingsBuilderToPatch,
      renderQualityDetailSettingsBuilderGuidance,
    };
  }

  window.__settingsViewQualityBuilderModule = {
    createQualityDetailSettingsBuilder,
  };
})();
