(function () {
  function createSettingsViewImpactModule(deps = {}) {
    const {
      apiPost,
      appendCells,
      appendCommandResult,
      applySettingsFieldMetadataToControls,
      byId,
      clearRows,
      formatConfigValue,
      formatSettingsChoiceLabel,
      formatSettingsListValue,
      getCommandHistory,
      isSettingsCommand,
      jsonDetailText,
      makeRowSelectable,
      parseSettingsListText,
      parseSettingsPatchJson,
      rejectSettingsCommandWhileBusy,
      renderSettingsAdvancedControls,
      renderSettingsEncoderCapabilityReport,
      setSettingsCommandBusy,
      setText,
      settingsBuilderConfigValue,
      settingsBuilderInputValue,
      settingsCommandHistoryLine,
      settingsCurrentPatchSignature,
      settingsFieldDefinition,
      settingsImpactGroups,
      settingsPatchHasUnsavedChanges,
      settingsPatchImpactEntries,
      settingsPatchIsTouched,
      settingsPatchReviewFunction,
      settingsPolicyImpactCall,
      settingsPolicyImpactDo,
      settingsRawConfigValue,
      settingsSpecificImpactHints,
      settingsValuesEqual,
      state,
      updateTableStatusLegend,
    } = deps;

  function settingsPatchReviewCall(name, args, fallback) {
    const fn = state.settingsPatchReview && state.settingsPatchReview[name];
    return typeof fn === "function" ? fn(...args) : fallback;
  }

  function settingsPatchSaveReadinessIssues(entries = []) { return settingsPatchReviewCall("settingsPatchSaveReadinessIssues", [entries], []); }
  function settingsPatchSaveReadinessStatus(issues = []) { return settingsPatchReviewCall("settingsPatchSaveReadinessStatus", [issues], "No changes"); }
  function settingsSaveReviewRows(entries = []) { return settingsPatchReviewCall("settingsSaveReviewRows", [entries], []); }
  function settingsSaveReviewStatus(rows = []) { return settingsPatchReviewCall("settingsSaveReviewStatus", [rows], "No review"); }
  function settingsSaveReviewDetailLines(row) { return settingsPatchReviewCall("settingsSaveReviewDetailLines", [row], []); }
  function renderSettingsSaveReviewFromEntries(entries = []) { settingsPatchReviewCall("renderSettingsSaveReviewFromEntries", [entries]); }
  function renderSettingsPatchSaveReadinessFromEntries(entries = []) { settingsPatchReviewCall("renderSettingsPatchSaveReadinessFromEntries", [entries]); }

  function renderSettingsPatchImpactSummaryForError(message) {
    setText(
      "settings-patch-impact-summary",
      `Local impact unavailable because Changes JSON is invalid.\n${message}\nBackend preview cannot run until this is valid JSON.`
    );
  }

  const settingsPolicyImpactModule = window.__settingsPolicyImpactModule || {};
  delete window.__settingsPolicyImpactModule;
  state.settingsPolicyImpact = typeof settingsPolicyImpactModule.createSettingsPolicyImpactModule === "function"
    ? settingsPolicyImpactModule.createSettingsPolicyImpactModule({
      appendCells,
      byId,
      clearRows,
      getCommandHistory: typeof getCommandHistory === "function" ? getCommandHistory : function () { return []; },
      formatConfigValue,
      formatSettingsChoiceLabel,
      formatSettingsListValue,
      getLastSettings: () => state.lastSettings,
      getLastSettingsValues: () => state.lastSettingsValues,
      getLastSettingsPatchPreviewEvidence: () => state.lastSettingsPatchPreviewEvidence,
      getLastSettingsPatchSaveEvidence: () => state.lastSettingsPatchSaveEvidence,
      getSelectedSettingsEffectivePolicyKey: () => state.selectedSettingsEffectivePolicyKey,
      makeRowSelectable,
      parseSettingsListText,
      parseSettingsPatchJson,
      setSelectedSettingsEffectivePolicyKey: (value) => { state.selectedSettingsEffectivePolicyKey = value || ""; },
      settingsBuilderConfigValue,
      settingsBuilderInputValue,
      settingsFieldDefinition,
      settingsImpactGroups,
      settingsRawConfigValue,
      settingsSpecificImpactHints,
      settingsValuesEqual,
      updateTableStatusLegend,
      isSettingsCommand,
      setText,
      settingsCommandHistoryLine,
      settingsPatchSaveReadinessIssues,
      settingsPatchSaveReadinessStatus,
    })
    : {};

  function settingsLaunchImpactRows(entries = []) { return settingsPolicyImpactCall("settingsLaunchImpactRows", [entries], []); }
  function settingsLaunchImpactStatus(rows = []) { return settingsPolicyImpactCall("settingsLaunchImpactStatus", [rows], "Not evaluated"); }
  function settingsLaunchImpactSummaryLines(rows = [], latest = null, issues = []) { return settingsPolicyImpactCall("settingsLaunchImpactSummaryLines", [rows, latest, issues], []); }
  function renderSettingsLaunchImpactHandoffFromEntries(entries = []) { settingsPolicyImpactDo("renderSettingsLaunchImpactHandoffFromEntries", [entries]); }
  function renderSettingsLaunchImpactHandoffForError(message) { settingsPolicyImpactDo("renderSettingsLaunchImpactHandoffForError", [message]); }
  const settingsBackendResultModule = window.__settingsBackendResultModule || {};
  delete window.__settingsBackendResultModule;
  const settingsBackendResult = typeof settingsBackendResultModule.createSettingsBackendResultModule === "function"
    ? settingsBackendResultModule.createSettingsBackendResultModule({
      appendCells,
      byId,
      clearRows,
      formatConfigValue,
      getLastSettingsPatchPreviewEvidence: () => state.lastSettingsPatchPreviewEvidence,
      getLastSettingsPatchSaveEvidence: () => state.lastSettingsPatchSaveEvidence,
      getLastSettingsReloadEvidence: () => state.lastSettingsReloadEvidence,
      getSelectedSettingsBackendResultKey: () => state.selectedSettingsBackendResultKey,
      jsonDetailText,
      makeRowSelectable,
      parseSettingsPatchJson,
      renderProgressBarsInto: function () {
        if (typeof window.mediaPipelineProgressView?.renderProgressBarsInto === "function") {
          window.mediaPipelineProgressView.renderProgressBarsInto.apply(window.mediaPipelineProgressView, arguments);
        }
      },
      setSelectedSettingsBackendResultKey: (value) => { state.selectedSettingsBackendResultKey = value || ""; },
      setText,
      settingsCommandHistoryLine,
      settingsCurrentPatchSignature,
      settingsPatchImpactEntries,
      updateTableStatusLegend,
    })
    : {};

  /*
   * Static smoke compatibility: settingsView.js remains the settings parent owner
   * while backend-result rendering lives in settings/backendResult.js.
   * Backend media-policy readiness:
   * Save Settings is the only persistence command.
   * Save remains backend-owned.
   * Frontend advisory only; backend Save remains authoritative for source-deletion acceptance and PSD1 writes.
   * Patch JSON changed after the last preview. Save reviews the current values before writing.
   * The last save was for different JSON. Do not treat it as proof for the current patch.
   * Evidence matches current JSON:
   * settings-backend-result-rows
   * settings-backend-result-detail
   */

  function settingsBackendResultCall(name, args, fallback) {
    const fn = settingsBackendResult && settingsBackendResult[name];
    return typeof fn === "function" ? fn(...args) : fallback;
  }

  function settingsCommandProgressBars(result) { return settingsBackendResultCall("settingsCommandProgressBars", [result], []); }
  function renderSettingsSaveProgress(result) { settingsBackendResultCall("renderSettingsSaveProgress", [result]); }
  function settingsProgressDetailLines(result) { return settingsBackendResultCall("settingsProgressDetailLines", [result], []); }
  function settingsBackendResultRowKey(row) { return settingsBackendResultCall("settingsBackendResultRowKey", [row], String(row?.key || row?.signal || "backend-result")); }
  function settingsBackendResultRows(entries = []) { return settingsBackendResultCall("settingsBackendResultRows", [entries], []); }
  function settingsBackendResultDetailLines(row) { return settingsBackendResultCall("settingsBackendResultDetailLines", [row], []); }
  function settingsBackendResultStatus(rows = []) { return settingsBackendResultCall("settingsBackendResultStatus", [rows], "No backend result"); }
  function settingsBackendResultSummaryLines(rows = []) { return settingsBackendResultCall("settingsBackendResultSummaryLines", [rows], []); }
  function renderSettingsBackendResultFromEntries(entries = []) { settingsBackendResultCall("renderSettingsBackendResultFromEntries", [entries]); }
  function renderSettingsBackendResultForError(message) { settingsBackendResultCall("renderSettingsBackendResultForError", [message]); }

  function renderSettingsPatchSummary() {
    const fn = settingsPatchReviewFunction("renderSettingsPatchSummary");
    if (fn) fn();
    syncSaveHeaderStatus();
  }

  function syncSaveHeaderStatus() {
    const patchStatusEl = byId("settings-patch-status");
    const headerPatchEl = byId("settings-save-header-patch-status");
    if (patchStatusEl && headerPatchEl) {
      let headerText = patchStatusEl.textContent || "No changes";
      if (headerText !== "No backend changes") {
        try {
          if (!settingsPatchIsTouched() || !settingsPatchHasUnsavedChanges()) {
            headerText = "No changes";
          }
        } catch (_error) {}
      }
      headerPatchEl.textContent = headerText || "No changes";
    }
    const reloaded = state.lastSettingsPatchSaveEvidence?.result?.data?.reloaded;
    const headerReloadEl = byId("settings-save-header-reload-status");
    if (headerReloadEl) {
      headerReloadEl.textContent = reloaded === true ? "Yes" : reloaded === false ? "No" : "—";
    }
  }

  function renderSettingsBuilderGuidance() {
    const fn = settingsPatchReviewFunction("renderSettingsBuilderGuidance");
    if (fn) fn();
  }

  function settingsProfileSummaryLines(settings) {
    const fn = settingsPatchReviewFunction("settingsProfileSummaryLines");
    return fn ? fn(settings) : "No profiles found.";
  }

  function renderSettings(settings) {
    state.lastSettings = settings || {};
    const config = state.lastSettings.config || {};
    state.lastSettingsValues = { ...config };
    state.lastSettingsFieldDefinitions = Array.isArray(state.lastSettings.field_definitions) ? state.lastSettings.field_definitions : [];
    state.lastSettingsFieldMap = Object.fromEntries(
      state.lastSettingsFieldDefinitions
        .filter((field) => field && field.key)
        .map((field) => [String(field.key), field])
    );
    applySettingsFieldMetadataToControls();
    renderSettingsAdvancedControls();
    const fn = settingsPatchReviewFunction("renderSettings");
    if (fn) fn(state.lastSettings);
    renderSettingsEncoderCapabilityReport(state.lastSettings);
    applySettingsFieldMetadataToControls();
    renderSettingsAdvancedControls();
  }

  async function validateCurrentSettings() {
    if (rejectSettingsCommandWhileBusy("settings.validate", "settings-status", "")) return;
    setSettingsCommandBusy(true);
    try {
      const result = await apiPost("/api/settings/validate", { values: state.lastSettingsValues });
      appendCommandResult(result);
      setText("settings-status", result.message || "Settings validation completed.");
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      appendCommandResult({
        command: "settings.validate",
        ok: false,
        severity: "error",
        message,
      });
      setText("settings-status", `Validation failed: ${message}`);
    } finally {
      setSettingsCommandBusy(false);
    }
  }

  function appendSettingsRiskSummaryLines(lines, riskSummary) {
    const items = Array.isArray(riskSummary?.items) ? riskSummary.items : [];
    if (!items.length) return;
    const counts = riskSummary.counts || {};
    lines.push(
      "",
      "Risk summary:",
      `Highest severity: ${riskSummary.highest_severity || "unknown"}`,
      `Counts: critical ${counts.critical || 0}, high ${counts.high || 0}, medium ${counts.medium || 0}, low ${counts.low || 0}`
    );
    items.forEach((item) => {
      const key = item.key || "(unknown key)";
      const severity = item.severity || "unknown";
      const code = item.code || "risk";
      const message = item.message || "";
      lines.push(`- [${severity}] ${key} (${code}): ${message}`);
    });
  }


    return {
      appendSettingsRiskSummaryLines,
      renderSettings,
      renderSettingsBackendResultForError,
      renderSettingsBackendResultFromEntries,
      renderSettingsBuilderGuidance,
      renderSettingsLaunchImpactHandoffForError,
      renderSettingsLaunchImpactHandoffFromEntries,
      renderSettingsPatchImpactSummaryForError,
      renderSettingsPatchSaveReadinessFromEntries,
      renderSettingsPatchSummary,
      renderSettingsSaveProgress,
      renderSettingsSaveReviewFromEntries,
      settingsBackendResultCall,
      settingsBackendResultDetailLines,
      settingsBackendResultRowKey,
      settingsBackendResultRows,
      settingsBackendResultStatus,
      settingsBackendResultSummaryLines,
      settingsCommandProgressBars,
      settingsLaunchImpactRows,
      settingsLaunchImpactStatus,
      settingsLaunchImpactSummaryLines,
      settingsPatchReviewCall,
      settingsPatchSaveReadinessIssues,
      settingsPatchSaveReadinessStatus,
      settingsProfileSummaryLines,
      settingsProgressDetailLines,
      settingsSaveReviewDetailLines,
      settingsSaveReviewRows,
      settingsSaveReviewStatus,
      syncSaveHeaderStatus,
      validateCurrentSettings,
    };
  }

  window.__settingsViewImpactModule = { createSettingsViewImpactModule };
})();
