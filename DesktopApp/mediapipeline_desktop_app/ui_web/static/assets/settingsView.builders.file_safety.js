(function () {
  function createFileSafetySettingsBuilder(deps) {
    const {
      byId,
      fileSafetySettingsBuilderFields,
      fileSafetySettingsBuilderState,
      formatSettingsListValue,
      parseSettingsListText,
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

    function setFileSafetyBuilderControl(id, key, kind, fallback) {
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

    function syncFileSafetySettingsBuilderFromConfig() {
      setFileSafetyBuilderControl("settings-file-safety-source-movies", "SourceMovies", "text", "");
      setFileSafetyBuilderControl("settings-file-safety-source-tv", "SourceTV", "text", "");
      setFileSafetyBuilderControl("settings-file-safety-outsource", "Outsource", "text", "");
      setFileSafetyBuilderControl("settings-file-safety-local-base", "LocalBase", "text", "");
      setFileSafetyBuilderControl("settings-file-safety-min-free", "MinFreeSpaceGB", "number", 50);
      setFileSafetyBuilderControl("settings-file-safety-outsource-min-free", "OutsourceMinFreeSpaceGB", "number", 50);
      setFileSafetyBuilderControl("settings-file-safety-stability-wait", "FileStabilityWait", "number", 15);
      setFileSafetyBuilderControl("settings-file-safety-cleanup-age", "CleanupStaleAgeHours", "number", 24);
      setFileSafetyBuilderControl("settings-file-safety-output-size-multiplier", "OutputSizeMultiplier", "number_float", 0.7);
      setFileSafetyBuilderControl("settings-file-safety-valid-extensions", "ValidExtensions", "list", [".mkv", ".mp4", ".avi", ".mov", ".m4v", ".ts", ".m2ts"]);
      setFileSafetyBuilderControl("settings-file-safety-robocopy-flags", "RobocopyFlags", "list", ["/J", "/R:3", "/W:15", "/MT:2", "/NP", "/NDL", "/NFL"]);
      setFileSafetyBuilderControl("settings-file-safety-deferred-publish", "DeferredPublish", "bool", false);
      setFileSafetyBuilderControl("settings-file-safety-aggressive-episode", "AggressiveEpisodeParsing", "bool", true);
      setFileSafetyBuilderControl("settings-file-safety-skip-stability", "SkipStabilityCheck", "bool", false);
      setFileSafetyBuilderControl("settings-file-safety-enable-integrity", "EnableIntegrityCheck", "bool", true);
      setFileSafetyBuilderControl("settings-file-safety-create-tv-subfolder", "CreateTVSubfolder", "bool", true);
      setFileSafetyBuilderControl("settings-file-safety-cleanup-remote", "CleanupRemoteStaging", "bool", false);
      fileSafetySettingsBuilderState.initialized = true;
      fileSafetySettingsBuilderState.dirty = false;
      setText("settings-file-safety-builder-status", "Loaded current values");
      renderFileSafetySettingsBuilderGuidance();
      renderSettingsActiveMediaPolicyHandoff();
    }

    function markFileSafetySettingsBuilderDirty() {
      fileSafetySettingsBuilderState.initialized = true;
      fileSafetySettingsBuilderState.dirty = true;
      setText("settings-file-safety-builder-status", "Editing file-safety values");
      renderFileSafetySettingsBuilderGuidance();
      renderSettingsActiveMediaPolicyHandoff();
    }

    function readFileSafetyBuilderValue(id, kind, label) {
      const element = byId(id);
      if (!element) return kind === "bool" ? false : "";
      if (kind === "bool") return element.checked === true;
      if (kind === "list") return parseSettingsListText(element.value);
      if (kind === "number_float") return readSettingsBuilderFloat(id, label);
      if (kind === "number") return readSettingsBuilderNumber(id, label);
      return String(element.value || "").trim();
    }

    function collectFileSafetySettingsBuilderPatch() {
      const patch = {};
      fileSafetySettingsBuilderFields.forEach(([key, id, kind]) => {
        const field = settingsFieldDefinition(key);
        patch[key] = readFileSafetyBuilderValue(id, kind, field?.label || key);
      });
      return patch;
    }

    function applyFileSafetySettingsBuilderToPatch() {
      let patch;
      try {
        patch = collectFileSafetySettingsBuilderPatch();
      } catch (error) {
        const message = error instanceof Error ? error.message : String(error);
        setText("settings-file-safety-builder-status", "Invalid file-safety value");
        setText("settings-patch-status", "Builder invalid");
        setText("settings-patch-detail", message);
        return;
      }
      writeSettingsPatchJson(patch, "File safety builder merged source/output/scratch, reserve, publish, and cleanup keys into Changes JSON. Preview or Save still uses backend validation.");
      fileSafetySettingsBuilderState.initialized = true;
      fileSafetySettingsBuilderState.dirty = true;
      setText("settings-file-safety-builder-status", `${Object.keys(patch).length} file-safety patch keys ready`);
      renderFileSafetySettingsBuilderGuidance();
      renderSettingsActiveMediaPolicyHandoff();
    }

    function fileSafetyChecked(id) {
      return byId(id)?.checked === true;
    }

    function fileSafetyToggleText(enabled) {
      return enabled ? "enabled" : "disabled";
    }

    function renderTvLibraryFolderEvidence() {
      const aggressiveEnabled = fileSafetyChecked("settings-file-safety-aggressive-episode");
      const foldersEnabled = fileSafetyChecked("settings-file-safety-create-tv-subfolder");
      const aggressiveField = settingsFieldDefinition("AggressiveEpisodeParsing");
      const foldersField = settingsFieldDefinition("CreateTVSubfolder");
      const lines = [
        `Aggressive episode parsing: ${fileSafetyToggleText(aggressiveEnabled)}.`,
        aggressiveEnabled
          ? "Effect: folder season hints and loose anime/import filename patterns can help build SxxEyy when strict parsing fails."
          : "Effect: folder and loose filename fallbacks stay off; strict season/episode evidence must carry TV identity.",
        `TV library folders: ${fileSafetyToggleText(foldersEnabled)}.`,
        foldersEnabled
          ? "Effect: future TV outputs can be planned under Plex-style TV\\Show\\Season NN folders."
          : "Effect: future TV outputs may be flatter and should be reviewed before Plex library scans.",
        "Boundary: this panel only stages existing settings keys into Changes JSON; backend Preview/Save and engine naming/publish behavior remain authoritative.",
      ];
      if (aggressiveField?.help) lines.push(`Metadata: ${aggressiveField.help}`);
      if (foldersField?.help) lines.push(`Metadata: ${foldersField.help}`);
      setText(
        "settings-tv-library-folder-status",
        `Episode parsing ${fileSafetyToggleText(aggressiveEnabled)}; TV folders ${fileSafetyToggleText(foldersEnabled)}`,
      );
      setText("settings-tv-library-folder-evidence", lines.join("\n"));
    }

    function renderFileSafetySettingsBuilderGuidance() {
      const lines = [
        "Guardrail: the pipeline should copy source files to scratch and should not mutate source files during normal processing.",
      ];
      fileSafetySettingsBuilderFields.forEach(([key, id, kind]) => {
        const field = settingsFieldDefinition(key);
        const label = field?.label || key;
        let valueText = "";
        if (kind === "bool") {
          valueText = byId(id)?.checked ? "enabled" : "disabled";
        } else if (kind === "list") {
          valueText = parseSettingsListText(byId(id)?.value || "").join(", ") || "(empty)";
        } else {
          valueText = settingsBuilderInputValue(id) || "(not set)";
        }
        lines.push(`${label}: ${valueText}`);
        if (field?.help) lines.push(`  ${field.help}`);
        const hint = settingsSpecificImpactHints[key];
        if (hint) lines.push(`  ${hint}`);
        if (key === "SkipStabilityCheck" && byId(id)?.checked) {
          lines.push("  Warning: skipping stability checks is risky with torrents, network shares, and half-copied files.");
        }
        if (key === "EnableIntegrityCheck" && !byId(id)?.checked) {
          lines.push("  Warning: corrupt or partially-written sources may pass discovery without probe validation.");
        }
        if (key === "CreateTVSubfolder" && !byId(id)?.checked) {
          lines.push("  Warning: future TV outputs may no longer land in Plex-style show/season folders.");
        }
        if (key === "ValidExtensions") {
          const values = parseSettingsListText(byId(id)?.value || "");
          const broad = values.filter((item) => !String(item).trim().startsWith("."));
          if (broad.length) lines.push("  Warning: every extension should start with a dot before backend preview/save.");
        }
        if (key === "RobocopyFlags") {
          const values = parseSettingsListText(byId(id)?.value || "");
          const highThread = values.find((item) => /^\/MT:(\d+)/i.test(String(item).trim()) && Number(String(item).split(":")[1]) > 8);
          if (highThread) lines.push("  Warning: high robocopy thread counts can saturate same-disk source/output/scratch layouts.");
        }
        if (key === "CleanupRemoteStaging" && byId(id)?.checked) {
          lines.push("  Warning: remote staging cleanup can touch slow or unreliable network paths.");
        }
        if (key === "DeferredPublish" && byId(id)?.checked) {
          lines.push("  Pending publish must be monitored and drained after output validation.");
        }
      });
      setText("settings-file-safety-guidance", lines.join("\n") || "No file-safety guidance loaded.");
      renderTvLibraryFolderEvidence();
    }

    return {
      syncFileSafetySettingsBuilderFromConfig,
      markFileSafetySettingsBuilderDirty,
      collectFileSafetySettingsBuilderPatch,
      applyFileSafetySettingsBuilderToPatch,
      renderFileSafetySettingsBuilderGuidance,
    };
  }

  window.__settingsViewFileSafetyBuilderModule = {
    createFileSafetySettingsBuilder,
  };
})();
