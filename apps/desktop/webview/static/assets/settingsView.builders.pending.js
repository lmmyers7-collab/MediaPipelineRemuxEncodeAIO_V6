(function () {
  function createPendingPublishSettingsBuilder(deps) {
    const GIB_BYTES = 1024 * 1024 * 1024;
    const {
      byId,
      formatSettingsListValue,
      parseSettingsListText,
      pendingPublishSettingsBuilderFields,
      pendingPublishSettingsBuilderState,
      readSettingsBuilderFloat,
      readSettingsBuilderNumber,
      renderSettingsActiveMediaPolicyHandoff,
      setText,
      settingsBuilderConfigValue,
      settingsBuilderInputValue,
      settingsFieldDefinition,
      settingsSpecificImpactHints,
      writeSettingsPatchJson,
    } = deps;

    function setPendingPublishBuilderControl(id, key, kind, fallback) {
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
      if (kind === "bytes_gib") {
        const bytes = Number(value ?? fallback ?? 0);
        element.value = Number.isFinite(bytes) && bytes > 0 ? String(Math.round(bytes / GIB_BYTES)) : "";
        return;
      }
      element.value = String(value ?? "");
    }

    function syncPendingPublishSettingsBuilderFromConfig() {
      setPendingPublishBuilderControl("settings-pending-deferred-publish", "DeferredPublish", "bool", false);
      setPendingPublishBuilderControl("settings-pending-cleanup-remote", "CleanupRemoteStaging", "bool", false);
      setPendingPublishBuilderControl("settings-pending-transient-retry-limit", "TransientFailureRetryLimit", "number", 3);
      setPendingPublishBuilderControl("settings-pending-cleanup-age", "CleanupStaleAgeHours", "number", 24);
      setPendingPublishBuilderControl("settings-pending-robocopy-timeout", "RobocopyTimeoutSeconds", "number_positive", 14400);
      setPendingPublishBuilderControl("settings-pending-robocopy-flags", "RobocopyFlags", "list", ["/J", "/R:3", "/W:15", "/MT:2", "/NP", "/NDL", "/NFL"]);
      setPendingPublishBuilderControl("settings-pending-outsource-min-free", "OutsourceMinFreeSpaceGB", "number", 50);
      setPendingPublishBuilderControl("settings-pending-review-budget-gib", "AutonomyPendingTotalReviewBytes", "bytes_gib", 100 * GIB_BYTES);
      setPendingPublishBuilderControl("settings-pending-block-budget-gib", "AutonomyPendingTotalBlockBytes", "bytes_gib", 250 * GIB_BYTES);
      setPendingPublishBuilderControl("settings-pending-output-size-multiplier", "OutputSizeMultiplier", "number_float", 0.7);
      setPendingPublishBuilderControl("settings-pending-enable-integrity", "EnableIntegrityCheck", "bool", true);
      setPendingPublishBuilderControl("settings-pending-skip-stability", "SkipStabilityCheck", "bool", false);
      pendingPublishSettingsBuilderState.initialized = true;
      pendingPublishSettingsBuilderState.dirty = false;
      setText("settings-pending-builder-status", "Loaded current values");
      renderPendingPublishSettingsBuilderGuidance();
      renderSettingsActiveMediaPolicyHandoff();
    }

    function markPendingPublishSettingsBuilderDirty() {
      pendingPublishSettingsBuilderState.initialized = true;
      pendingPublishSettingsBuilderState.dirty = true;
      setText("settings-pending-builder-status", "Editing pending-publish values");
      renderPendingPublishSettingsBuilderGuidance();
      renderSettingsActiveMediaPolicyHandoff();
    }

    function readPendingPublishBuilderValue(id, kind, label) {
      const element = byId(id);
      if (!element) return kind === "bool" ? false : kind === "list" ? [] : "";
      if (kind === "bool") return element.checked === true;
      if (kind === "list") return parseSettingsListText(element.value);
      if (kind === "number_float") return readSettingsBuilderFloat(id, label);
      if (kind === "bytes_gib") {
        const value = readSettingsBuilderNumber(id, label);
        if (value < 1) throw new Error(`${label} must be one GiB or higher.`);
        return Math.round(value * GIB_BYTES);
      }
      if (kind === "number_positive") {
        const value = readSettingsBuilderNumber(id, label);
        if (value < 1) throw new Error(`${label} must be one or higher.`);
        return value;
      }
      if (kind === "number") return readSettingsBuilderNumber(id, label);
      return String(element.value || "").trim();
    }

    function collectPendingPublishSettingsBuilderPatch() {
      const patch = {};
      pendingPublishSettingsBuilderFields.forEach(([key, id, kind]) => {
        const field = settingsFieldDefinition(key);
        patch[key] = readPendingPublishBuilderValue(id, kind, field?.label || key);
      });
      return patch;
    }

    function applyPendingPublishSettingsBuilderToPatch() {
      let patch;
      try {
        patch = collectPendingPublishSettingsBuilderPatch();
      } catch (error) {
        const message = error instanceof Error ? error.message : String(error);
        setText("settings-pending-builder-status", "Invalid pending-publish value");
        setText("settings-patch-status", "Builder invalid");
        setText("settings-patch-detail", message);
        return false;
      }
      writeSettingsPatchJson(patch, "Pending publish builder prepared deferred publish, copy, retry, cleanup, and safety keys for Save Settings. Backend Save still validates before writing.");
      pendingPublishSettingsBuilderState.initialized = true;
      pendingPublishSettingsBuilderState.dirty = true;
      setText("settings-pending-builder-status", `${Object.keys(patch).length} pending-publish change keys ready`);
      renderPendingPublishSettingsBuilderGuidance();
      renderSettingsActiveMediaPolicyHandoff();
      return true;
    }

    function renderPendingPublishSettingsBuilderGuidance() {
      const deferred = byId("settings-pending-deferred-publish")?.checked === true;
      const cleanupRemote = byId("settings-pending-cleanup-remote")?.checked === true;
      const integrity = byId("settings-pending-enable-integrity")?.checked === true;
      const skipStability = byId("settings-pending-skip-stability")?.checked === true;
      const retryLimit = Number(settingsBuilderInputValue("settings-pending-transient-retry-limit") || 0);
      const cleanupAge = Number(settingsBuilderInputValue("settings-pending-cleanup-age") || 0);
      const robocopyTimeout = Number(settingsBuilderInputValue("settings-pending-robocopy-timeout") || 0);
      const outputMultiplier = Number(settingsBuilderInputValue("settings-pending-output-size-multiplier") || 0);
      const lines = [
        "Guardrail: this builder stages existing config keys only; Drain Parked Outputs, copy, cleanup, and retry behavior remain backend-owned.",
        deferred
          ? "Mode: deferred publish is enabled. Completed payloads can park until the pending-publish drain validates and moves them."
          : "Mode: deferred publish is disabled. Processing can publish directly to final output after validation.",
      ];
      pendingPublishSettingsBuilderFields.forEach(([key, id, kind]) => {
        const field = settingsFieldDefinition(key);
        const label = field?.label || key;
        let valueText = "";
        if (kind === "bool") {
          valueText = byId(id)?.checked ? "enabled" : "disabled";
        } else if (kind === "list") {
          valueText = parseSettingsListText(byId(id)?.value || "").join(", ") || "(empty)";
        } else if (kind === "bytes_gib") {
          valueText = `${settingsBuilderInputValue(id) || "(not set)"} GiB`;
        } else {
          valueText = settingsBuilderInputValue(id) || "(not set)";
        }
        lines.push(`${label}: ${valueText}`);
        if (field?.help) lines.push(`  ${field.help}`);
        const hint = settingsSpecificImpactHints[key];
        if (hint) lines.push(`  ${hint}`);
      });
      if (cleanupRemote) {
        lines.push("", "Warning: remote staging cleanup should stay disabled until pending drains are trusted on the target share.");
      }
      if (!integrity) {
        lines.push("", "Warning: disabling integrity checks can let corrupt or partially readable files move through publish/recovery.");
      }
      if (skipStability) {
        lines.push("", "Warning: skipping stability checks is risky when source or pending paths sit on active SMB shares.");
      }
      if (skipStability && !deferred) {
        lines.push("Conflict: direct publish plus skipped stability checks gives the operator less opportunity to catch half-copied inputs.");
      }
      if (retryLimit > 8) {
        lines.push("", "Review: high transient retry limits can hide persistent SMB/auth/disk failures for a long time.");
      }
      if (cleanupAge > 0 && cleanupAge < 6) {
        lines.push("", "Review: very short stale cleanup ages can remove forensic scratch or pending-publish evidence quickly.");
      }
      if (robocopyTimeout > 0 && robocopyTimeout < 300) {
        lines.push("", "Review: short copy timeouts can fail large media files on slow spinning disks or SMB shares.");
      }
      if (outputMultiplier > 0 && outputMultiplier < 0.5) {
        lines.push("", "Review: low disk-estimate multipliers can under-reserve final output or pending-publish space.");
      }
      const flags = parseSettingsListText(byId("settings-pending-robocopy-flags")?.value || "");
      const highThread = flags.find((item) => /^\/MT:(\d+)/i.test(String(item).trim()) && Number(String(item).split(":")[1]) > 8);
      if (highThread) {
        lines.push("", "Warning: high robocopy thread counts can saturate pending-publish drains on shared disks or network links.");
      }
      lines.push("", "Operator action: merge, preview patch, review backend risk summary, then save only when no pipeline or drain is active.");
      setText("settings-pending-guidance", lines.join("\n") || "No pending-publish guidance loaded.");
    }

    return {
      syncPendingPublishSettingsBuilderFromConfig,
      markPendingPublishSettingsBuilderDirty,
      collectPendingPublishSettingsBuilderPatch,
      applyPendingPublishSettingsBuilderToPatch,
      renderPendingPublishSettingsBuilderGuidance,
    };
  }

  window.__settingsViewPendingPublishBuilderModule = {
    createPendingPublishSettingsBuilder,
  };
})();
