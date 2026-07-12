(function () {
  function createSettingsViewLifecycleModule(deps = {}) {
    const {
      apiPost,
      appendCommandResult,
      byId,
      handleSettingsAdvancedToggleClick,
      initSettingsRenameLogCaseEvents,
      markFileSafetySettingsBuilderDirty,
      refreshAll,
      rejectSettingsCommandWhileBusy,
      renderSettingsActiveMediaPolicyHandoff,
      renderSettingsPatchSummary,
      resetSettingsBuilderSyncState,
      setSettingsCommandBusy,
      setText,
      settingsBuilderConfigValue,
      settingsFieldDefinition,
      settingsPatchReviewFunction,
      state,
    } = deps;

  async function reloadSettingsFromDisk() {
    if (rejectSettingsCommandWhileBusy("settings.reload", "settings-status", "")) return;
    setSettingsCommandBusy(true);
    setText("settings-status", "Reloading...");
    try {
      const result = await apiPost("/api/settings/reload", {});
      appendCommandResult(result);
      state.lastSettingsReloadEvidence = {
        command: "settings.reload",
        result,
        captured_at: new Date().toISOString(),
      };
      setText("settings-status", result.message || "Settings reload completed.");
      renderSettingsPatchSummary();
      if (result.ok) {
        resetSettingsBuilderSyncState({ includeFinalLibraryPromotion: true });
        await refreshAll();
      }
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      appendCommandResult({
        command: "settings.reload",
        ok: false,
        severity: "error",
        message,
      });
      state.lastSettingsReloadEvidence = {
        command: "settings.reload",
        result: {
          command: "settings.reload",
          ok: false,
          severity: "error",
          message,
        },
        captured_at: new Date().toISOString(),
      };
      setText("settings-status", `Reload failed: ${message}`);
      renderSettingsPatchSummary();
    } finally {
      setSettingsCommandBusy(false);
    }
  }

    function getLastSettings() {
      return state.lastSettings || {};
    }

    function settingsBrowsePathDetailLines(result, fieldLabel) {
      const data = result?.data && typeof result.data === "object" ? result.data : {};
      const validation = data.validation && typeof data.validation === "object" ? data.validation : {};
      const lines = [
        result?.message || `Settings folder browse returned for ${fieldLabel}.`,
        validation.message ? `Validation: ${validation.message}` : "Validation: no selected-folder evidence returned.",
        `Writes config: ${data.writes_config === true ? "yes" : "no"}`,
        `Save candidate only: ${data.stages_only === true ? "yes" : "no"}`,
        "Next step: Save Settings. Launch uses saved backend settings only.",
        "Mutation guardrail: this route only opens a backend-owned Windows folder picker and prepares one allowlisted Settings field. It cannot save settings, launch work, rewrite queue state, publish, rename, delete, or touch media files.",
      ];
      if (data.selected_path) lines.splice(1, 0, `Selected path: ${data.selected_path}`);
      return lines;
    }

    async function browseSettingsPath(settingKey, inputId) {
      if (rejectSettingsCommandWhileBusy("settings.browse_path", "settings-file-safety-builder-status", "settings-file-safety-guidance")) return;
      const input = byId(inputId);
      const field = settingsFieldDefinition(settingKey);
      const fieldLabel = field?.label || settingKey;
      const initialPath = input?.value || settingsBuilderConfigValue(settingKey, "");
      setSettingsCommandBusy(true);
      setText("settings-file-safety-builder-status", `Opening ${fieldLabel} folder browser...`);
      setText(
        "settings-file-safety-guidance",
        [
          `Opening backend-owned Windows folder browser for ${fieldLabel}.`,
          "No Settings file will be saved by this action.",
          "Use Save Settings to review and write the prepared File Safety change.",
        ].join("\n")
      );
      try {
        const result = await apiPost(
          "/api/settings/browse-path",
          { setting_key: settingKey, selection_mode: "folder", initial_path: initialPath },
          { timeoutMs: 15 * 60 * 1000 }
        );
        appendCommandResult(result);
        const data = result?.data && typeof result.data === "object" ? result.data : {};
        const validation = data.validation && typeof data.validation === "object" ? data.validation : {};
        const selectedPath = String(data.selected_path || "");
        if (result.ok && !data.canceled && selectedPath && validation.status_state === "ready" && input) {
          input.value = selectedPath;
          markFileSafetySettingsBuilderDirty();
          setText("settings-file-safety-builder-status", `${fieldLabel} path ready`);
        } else if (data.canceled) {
          setText("settings-file-safety-builder-status", "Folder browse canceled");
        } else {
          setText("settings-file-safety-builder-status", result.ok ? "Folder browse needs review" : "Folder browse failed");
        }
        setText("settings-file-safety-guidance", settingsBrowsePathDetailLines(result, fieldLabel).join("\n"));
        renderSettingsActiveMediaPolicyHandoff();
      } catch (error) {
        const message = error instanceof Error ? error.message : String(error);
        const result = {
          command: "settings.browse_path",
          ok: false,
          severity: "error",
          message,
        };
        appendCommandResult(result);
        setText("settings-file-safety-builder-status", "Folder browse failed");
        setText("settings-file-safety-guidance", settingsBrowsePathDetailLines(result, fieldLabel).join("\n"));
      } finally {
        setSettingsCommandBusy(false);
      }
    }

    function initSettingsViewEvents() {
      const fn = settingsPatchReviewFunction("initSettingsViewEvents");
      if (fn) fn();
      initSettingsRenameLogCaseEvents();
      if (!state.settingsAdvancedToggleEventsBound) {
        document.addEventListener("click", handleSettingsAdvancedToggleClick);
        state.settingsAdvancedToggleEventsBound = true;
      }
    }


    return {
      browseSettingsPath,
      getLastSettings,
      initSettingsViewEvents,
      reloadSettingsFromDisk,
      settingsBrowsePathDetailLines,
    };
  }

  window.__settingsViewLifecycleModule = { createSettingsViewLifecycleModule };
})();
