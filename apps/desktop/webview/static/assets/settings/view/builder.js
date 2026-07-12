(function () {
  function createSettingsViewBuilderModule(deps = {}) {
    const {
      apiPost,
      appendCells,
      appendCommandResult,
      applyAudioSettingsBuilderToPatch,
      applyFileSafetySettingsBuilderToPatch,
      applyNetworkSettingsBuilderToPatch,
      applyPendingPublishSettingsBuilderToPatch,
      applyQualityDetailSettingsBuilderToPatch,
      applyQueueSettingsBuilderToPatch,
      applyRuntimeSettingsBuilderToPatch,
      applySubtitleSettingsBuilderToPatch,
      applyVideoDetailSettingsBuilderToPatch,
      audioSettingsBuilderFields,
      audioSettingsBuilderState,
      browseSettingsPath,
      byId,
      clearRows,
      fileSafetySettingsBuilderFields,
      fileSafetySettingsBuilderState,
      finalLibraryPromotionSettingsBuilderFields,
      finalLibraryPromotionSettingsBuilderState,
      formatConfigValue,
      formatSettingsChoiceLabel,
      getCommandHistory,
      isSettingsCommand,
      makeRowSelectable,
      markAudioSettingsBuilderDirty,
      markFileSafetySettingsBuilderDirty,
      markNetworkSettingsBuilderDirty,
      markPendingPublishSettingsBuilderDirty,
      markQualityDetailSettingsBuilderDirty,
      markQueueSettingsBuilderDirty,
      markRuntimeSettingsBuilderDirty,
      markSubtitleSettingsBuilderDirty,
      markVideoDetailSettingsBuilderDirty,
      maybeShowSettingsRuntimeRestartNotice,
      networkSettingsBuilderFields,
      networkSettingsBuilderState,
      pendingPublishSettingsBuilderFields,
      pendingPublishSettingsBuilderState,
      previewSettingsPatch,
      qualityDetailSettingsBuilderFields,
      qualityDetailSettingsBuilderState,
      queueSettingsBuilderFields,
      queueSettingsBuilderState,
      refreshAudioSettingsBuilderChoices,
      refreshSettingsBuilderChoices,
      refreshSettingsSelectChoices,
      rejectSettingsCommandWhileBusy,
      reloadSettingsFromDisk,
      renderAudioSettingsBuilderGuidance,
      renderFileSafetySettingsBuilderGuidance,
      renderNetworkSettingsBuilderGuidance,
      renderPendingPublishSettingsBuilderGuidance,
      renderQualityDetailSettingsBuilderGuidance,
      renderQueueSettingsBuilderGuidance,
      renderRuntimeSettingsBuilderGuidance,
      renderSettingsBackendResultForError,
      renderSettingsBackendResultFromEntries,
      renderSettingsBdpgsOcrPathEvidence,
      renderSettingsLaunchImpactHandoffForError,
      renderSettingsLaunchImpactHandoffFromEntries,
      renderSettingsOperatorTrust,
      renderSettingsOverview,
      renderSettingsPatchImpactSummaryForError,
      renderSettingsPatchSummary,
      renderSettingsRawActionPlan,
      renderSettingsRawTriage,
      renderSettingsRows,
      renderSettingsSafetyLocks,
      renderSettingsVobSubOcrPathEvidence,
      renderSubtitleSettingsBuilderGuidance,
      renderVideoDetailSettingsBuilderGuidance,
      runtimeSettingsBuilderFields,
      runtimeSettingsBuilderState,
      saveSettingsPatch,
      scheduleSettingsPostSaveRefresh,
      setSettingsCommandBusy,
      setSettingsRows,
      setText,
      SETTINGS_PREVIEW_POST_TIMEOUT_MS,
      SETTINGS_SAVE_POST_TIMEOUT_MS,
      settingsBuilderConfigValue,
      settingsBuilderFields,
      settingsCommandHistoryLine,
      settingsFieldAllowedValues,
      settingsFieldDefinition,
      settingsFriendlyPersistedKeyAliases,
      settingsHasBackendFieldDefinitions,
      settingsPatchComplexBackendKeys,
      settingsPostErrorMessage,
      settingsRuntimeRestartConfirmationLine,
      settingsRuntimeRestartNoticeLines,
      settingsValuesEqual,
      state,
      subtitleSettingsBuilderFields,
      subtitleSettingsBuilderState,
      syncAudioSettingsBuilderFromConfig,
      syncFileSafetySettingsBuilderFromConfig,
      syncNetworkSettingsBuilderFromConfig,
      syncPendingPublishSettingsBuilderFromConfig,
      syncQualityDetailSettingsBuilderFromConfig,
      syncQueueSettingsBuilderFromConfig,
      syncRuntimeSettingsBuilderFromConfig,
      syncSubtitleSettingsBuilderFromConfig,
      syncVideoDetailSettingsBuilderFromConfig,
      updateTableStatusLegend,
      validateCurrentSettings,
      videoDetailSettingsBuilderFields,
      videoDetailSettingsBuilderState,
    } = deps;

  function setSettingsBuilderControl(id, value) {
    const fn = settingsPatchReviewFunction("setSettingsBuilderControl");
    if (fn) fn(id, value);
  }

  function syncSettingsBuilderFromConfig() {
    const fn = settingsPatchReviewFunction("syncSettingsBuilderFromConfig");
    if (fn) fn();
  }

  function markSettingsBuilderDirty() {
    const fn = settingsPatchReviewFunction("markSettingsBuilderDirty");
    if (fn) fn();
  }

  function settingsBuilderInputValue(id) {
    const fn = settingsPatchReviewFunction("settingsBuilderInputValue");
    return fn ? fn(id) : "";
  }

  function readSettingsBuilderNumber(id, label) {
    const fn = settingsPatchReviewFunction("readSettingsBuilderNumber");
    if (!fn) throw new Error(`${label} is required.`);
    return fn(id, label);
  }

  function readSettingsBuilderFloat(id, label) {
    const fn = settingsPatchReviewFunction("readSettingsBuilderFloat");
    if (!fn) throw new Error(`${label} is required.`);
    return fn(id, label);
  }

  function settingsRawConfigValue(key) {
    const fn = settingsPatchReviewFunction("settingsRawConfigValue");
    return fn ? fn(key) : undefined;
  }

  function parseSettingsPatchJson() {
    const fn = settingsPatchReviewFunction("parseSettingsPatchJson");
    return fn ? fn() : {};
  }

  function markSettingsPatchTouched() {
    const fn = settingsPatchReviewFunction("markSettingsPatchTouched");
    if (fn) fn();
  }

  function settingsPatchIsTouched() {
    const fn = settingsPatchReviewFunction("settingsPatchIsTouched");
    return fn ? fn() : state.settingsPatchTouched;
  }

  function settingsPatchEffectiveChangedEntries() {
    const fn = settingsPatchReviewFunction("settingsPatchEffectiveChangedEntries");
    return fn ? fn() : [];
  }

  function settingsPatchHasUnsavedChanges() {
    const fn = settingsPatchReviewFunction("settingsPatchHasUnsavedChanges");
    return fn ? fn() : false;
  }

  function writeSettingsPatchJson(patch, detail) {
    const fn = settingsPatchReviewFunction("writeSettingsPatchJson");
    if (fn) fn(patch, detail);
  }

  state.settingsPatchReview = {};

  function settingsPatchReviewFunction(name) {
    const fn = state.settingsPatchReview ? state.settingsPatchReview[name] : null;
    return typeof fn === "function" ? fn : null;
  }

  function setFinalLibraryPromotionStatus(status, detail) {
    const fn = settingsPatchReviewFunction("setFinalLibraryPromotionStatus");
    if (fn) {
      fn(status, detail);
      return;
    }
    setText("settings-final-library-status", status || "Not loaded");
    if (detail !== undefined) setText("settings-final-library-guidance", detail);
  }

  function finalLibraryPromotionBrowseDetailLines(result, label) {
    const fn = settingsPatchReviewFunction("finalLibraryPromotionBrowseDetailLines");
    return fn ? fn(result, label) : [result?.message || `Folder browse returned for ${label}.`];
  }

  function addFinalLibraryPromotionRule() {
    const fn = settingsPatchReviewFunction("addFinalLibraryPromotionRule");
    if (fn) fn();
  }

  function syncFinalLibraryPromotionSettingsBuilderFromConfig() {
    const fn = settingsPatchReviewFunction("syncFinalLibraryPromotionSettingsBuilderFromConfig");
    if (fn) fn();
  }

  function markFinalLibraryPromotionSettingsBuilderDirty() {
    const fn = settingsPatchReviewFunction("markFinalLibraryPromotionSettingsBuilderDirty");
    if (fn) fn();
  }

  function collectFinalLibraryPromotionSettingsPatch() {
    const fn = settingsPatchReviewFunction("collectFinalLibraryPromotionSettingsPatch");
    if (!fn) throw new Error("Final Library Promotion settings module is unavailable.");
    return fn();
  }

  function renderFinalLibraryPromotionSettingsGuidance() {
    const fn = settingsPatchReviewFunction("renderFinalLibraryPromotionSettingsGuidance");
    if (fn) fn();
  }

  function finalLibraryPromotionSettingsResultLines(action, result, changes) {
    const fn = settingsPatchReviewFunction("finalLibraryPromotionSettingsResultLines");
    return fn ? fn(action, result, changes) : [`${action}: ${result?.message || "No backend message returned."}`];
  }

  async function browseFinalLibraryPromotionRulePath(input, settingKey, label) {
    if (rejectSettingsCommandWhileBusy("settings.browse_path", "settings-final-library-status", "settings-final-library-guidance")) return;
    setSettingsCommandBusy(true);
    setFinalLibraryPromotionStatus(`Opening ${label} folder browser...`, [
      `Opening backend-owned Windows folder browser for ${label}.`,
      "No settings will be saved by this action.",
    ].join("\n"));
    try {
      const initialPath = input?.value || "";
      const result = await apiPost(
        "/api/settings/browse-path",
        { setting_key: settingKey, selection_mode: "folder", initial_path: initialPath },
        { timeoutMs: 15 * 60 * 1000 }
      );
      appendCommandResult(result);
      const data = result?.data && typeof result.data === "object" ? result.data : {};
      const selectedPath = String(data.selected_path || "");
      if (result.ok && !data.canceled && selectedPath && input) {
        input.value = selectedPath;
        markFinalLibraryPromotionSettingsBuilderDirty();
        setText("settings-final-library-status", `${label} path staged`);
      } else if (data.canceled) {
        setText("settings-final-library-status", "Folder browse canceled");
      } else {
        setText("settings-final-library-status", result.ok ? "Folder browse needs review" : "Folder browse failed");
      }
      setText("settings-final-library-guidance", finalLibraryPromotionBrowseDetailLines(result, label).join("\n"));
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      const result = {
        command: "settings.browse_path",
        ok: false,
        severity: "error",
        message,
      };
      appendCommandResult(result);
      setFinalLibraryPromotionStatus("Folder browse failed", finalLibraryPromotionBrowseDetailLines(result, label).join("\n"));
    } finally {
      setSettingsCommandBusy(false);
    }
  }

  function settingsSaveReviewModalHost() {
    return document.querySelector("[data-settings-modal-host]") || document.querySelector("main.workspace") || document.body;
  }

  function ensureSettingsSaveReviewDialogGlobal(dialog) {
    const hiddenPage = dialog?.closest?.(".page:not(.is-visible)");
    if (!hiddenPage) return dialog;
    const host = settingsSaveReviewModalHost();
    if (host && typeof host.appendChild === "function") {
      host.appendChild(dialog);
    } else if (document.body && typeof document.body.appendChild === "function") {
      document.body.appendChild(dialog);
    }
    return dialog;
  }

  async function previewFinalLibraryPromotionSettings() {
    if (rejectSettingsCommandWhileBusy("settings.preview_patch", "settings-final-library-status", "settings-final-library-guidance")) return;
    let changes;
    try {
      changes = collectFinalLibraryPromotionSettingsPatch();
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      setFinalLibraryPromotionStatus("Invalid final library settings", message);
      appendCommandResult({
        command: "settings.preview_patch",
        ok: false,
        severity: "error",
        message,
      });
      return;
    }
    setSettingsCommandBusy(true);
    setFinalLibraryPromotionStatus("Previewing...", "Requesting backend preview for Final Library Promotion settings. This will not save the PSD1.");
    try {
      const result = await apiPost("/api/settings/preview-patch", { changes }, { timeoutMs: SETTINGS_PREVIEW_POST_TIMEOUT_MS });
      appendCommandResult(result);
      state.lastSettingsPatchPreviewEvidence = {
        command: "settings.preview_patch",
        result,
        changes: settingsStableJsonValue(changes),
        signature: settingsPatchSignature(changes),
        captured_at: new Date().toISOString(),
      };
      setFinalLibraryPromotionStatus(result.ok ? "Preview ready" : result.severity || "Preview failed", finalLibraryPromotionSettingsResultLines("Backend preview", result, changes).join("\n"));
      renderSettingsPatchSummary();
    } catch (error) {
      const message = settingsPostErrorMessage(error, "preview");
      const result = {
        command: "settings.preview_patch",
        ok: false,
        severity: "error",
        message,
      };
      appendCommandResult(result);
      setFinalLibraryPromotionStatus("Preview failed", finalLibraryPromotionSettingsResultLines("Backend preview", result, changes).join("\n"));
    } finally {
      setSettingsCommandBusy(false);
    }
  }

  async function saveFinalLibraryPromotionSettings() {
    if (rejectSettingsCommandWhileBusy("settings.save_patch", "settings-final-library-status", "settings-final-library-guidance")) return;
    let changes;
    try {
      changes = collectFinalLibraryPromotionSettingsPatch();
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      setFinalLibraryPromotionStatus("Invalid final library settings", message);
      appendCommandResult({
        command: "settings.save_patch",
        ok: false,
        severity: "error",
        message,
      });
      return;
    }
    const confirmation = [
      "Save Final Library Promotion settings to the active backend config?",
      "",
      `Promotion enabled: ${changes.FinalLibraryPromotionEnabled ? "yes" : "no"}`,
      `Rules: ${changes.FinalLibraryPromotionRules.filter((rule) => rule.enabled).length} enabled`,
      `Verification: ${changes.FinalLibraryPromotionVerificationMode}`,
      `Cleanup after verified promotion: ${changes.FinalLibraryPromotionCleanupAfterVerified ? "yes" : "no"}`,
      `Destructive overwrite: ${changes.FinalLibraryPromotionOverwriteExisting ? "yes" : "no"}`,
      "",
      settingsRuntimeRestartConfirmationLine(),
    ];
    if (changes.FinalLibraryPromotionOverwriteExisting) {
      confirmation.push("", "Overwrite warning: existing final files will be deleted before replacement copies when promotion runs.");
    }
    if (changes.FinalLibraryPromotionCleanupAfterVerified) {
      confirmation.push("", "Cleanup warning: verified promoted publish-output files below Outsource can be deleted after promotion.");
    }
    if (!window.confirm(confirmation.join("\n"))) {
      setFinalLibraryPromotionStatus("Save cancelled", "No Final Library Promotion settings were saved.");
      appendCommandResult({
        command: "settings.save_patch",
        ok: false,
        severity: "info",
        message: "Final Library Promotion settings save cancelled by operator.",
      });
      return;
    }
    setSettingsCommandBusy(true);
    setFinalLibraryPromotionStatus("Previewing save...", "Requesting backend preview before saving Final Library Promotion settings.");
    try {
      const previewResult = await apiPost("/api/settings/preview-patch", { changes }, { timeoutMs: SETTINGS_PREVIEW_POST_TIMEOUT_MS });
      appendCommandResult(previewResult);
      const previewData = previewResult.data && typeof previewResult.data === "object" ? previewResult.data : {};
      const reviewConfirmation = previewData.review_confirmation && typeof previewData.review_confirmation === "object"
        ? previewData.review_confirmation
        : null;
      if (!previewResult.ok || (previewResult.errors || []).length) {
        setFinalLibraryPromotionStatus("Preview blocked", finalLibraryPromotionSettingsResultLines("Backend preview", previewResult, changes).join("\n"));
        return;
      }
      if (!reviewConfirmation) {
        setFinalLibraryPromotionStatus("Preview missing confirmation", "Backend preview did not return a review_confirmation contract, so no save command was sent.");
        return;
      }
      setFinalLibraryPromotionStatus("Saving...", "Saving backend-validated Final Library Promotion settings to the active PSD1. A backup will be created first.");
      const result = await apiPost(
        "/api/settings/save-patch",
        { changes, review_confirmation: reviewConfirmation, confirm_save: true },
        { timeoutMs: SETTINGS_SAVE_POST_TIMEOUT_MS }
      );
      appendCommandResult(result);
      state.lastSettingsPatchSaveEvidence = {
        command: "settings.save_patch",
        result,
        changes: settingsStableJsonValue(changes),
        signature: settingsPatchSignature(changes),
        captured_at: new Date().toISOString(),
      };
      const statusLines = finalLibraryPromotionSettingsResultLines("Backend save", result, changes);
      if (result.ok) {
        statusLines.push("", ...settingsRuntimeRestartNoticeLines(result));
        maybeShowSettingsRuntimeRestartNotice(result);
      }
      setFinalLibraryPromotionStatus(result.ok ? "Saved" : result.severity || "Save failed", statusLines.join("\n"));
      renderSettingsPatchSummary();
      if (result.ok) {
        finalLibraryPromotionSettingsBuilderState.dirty = false;
        scheduleSettingsPostSaveRefresh();
      }
    } catch (error) {
      const message = settingsPostErrorMessage(error, "save");
      const result = {
        command: "settings.save_patch",
        ok: false,
        severity: "error",
        message,
      };
      appendCommandResult(result);
      setFinalLibraryPromotionStatus("Save failed", finalLibraryPromotionSettingsResultLines("Backend save", result, changes).join("\n"));
    } finally {
      setSettingsCommandBusy(false);
    }
  }

  function collectSettingsBuilderPatch() {
    const fn = settingsPatchReviewFunction("collectSettingsBuilderPatch");
    return fn ? fn() : {};
  }

  function applySettingsBuilderToPatch() {
    const fn = settingsPatchReviewFunction("applySettingsBuilderToPatch");
    return fn ? fn() : true;
  }

  state.settingsPolicyImpact = {};
  function settingsPolicyImpactFunction(name) {
    return state.settingsPolicyImpact && typeof state.settingsPolicyImpact[name] === "function" ? state.settingsPolicyImpact[name] : null;
  }

  function settingsPolicyImpactCall(name, args, fallback) {
    const fn = settingsPolicyImpactFunction(name);
    return fn ? fn(...args) : fallback;
  }

  function settingsPolicyImpactDo(name, args) {
    const fn = settingsPolicyImpactFunction(name);
    if (fn) fn(...args);
  }

  function settingsMediaPolicyRows() { return settingsPolicyImpactCall("settingsMediaPolicyRows", [], []); }
  function settingsMediaPolicyStatus(rows = settingsMediaPolicyRows()) { return settingsPolicyImpactCall("settingsMediaPolicyStatus", [rows], "No policy"); }
  function settingsActiveMediaPolicyRows() { return settingsPolicyImpactCall("settingsActiveMediaPolicyRows", [], []); }
  function settingsActiveMediaPolicyStatus(rows = settingsActiveMediaPolicyRows()) { return settingsPolicyImpactCall("settingsActiveMediaPolicyStatus", [rows], "No policy"); }
  function settingsActiveMediaPolicySummaryLines(rows = settingsActiveMediaPolicyRows()) { return settingsPolicyImpactCall("settingsActiveMediaPolicySummaryLines", [rows], []); }
  function renderSettingsActiveMediaPolicyHandoff() { settingsPolicyImpactDo("renderSettingsActiveMediaPolicyHandoff", []); }
  function settingsEffectivePolicyRows(entries) { return settingsPolicyImpactCall("settingsEffectivePolicyRows", [entries], []); }
  function settingsEffectivePolicyTrustStatus(rows = settingsEffectivePolicyRows(settingsPatchImpactEntries(parseSettingsPatchJson()))) { return settingsPolicyImpactCall("settingsEffectivePolicyTrustStatus", [rows], "Not evaluated"); }
  function settingsEffectivePolicySummaryLines(rows = settingsEffectivePolicyRows(settingsPatchImpactEntries(parseSettingsPatchJson()))) { return settingsPolicyImpactCall("settingsEffectivePolicySummaryLines", [rows], []); }
  function settingsEffectivePolicyDetailLines(row) { return settingsPolicyImpactCall("settingsEffectivePolicyDetailLines", [row], []); }
  function renderSettingsEffectivePolicyTrustFromEntries(entries) { settingsPolicyImpactDo("renderSettingsEffectivePolicyTrustFromEntries", [entries]); }
  function renderSettingsEffectivePolicyTrustForError(message) { settingsPolicyImpactDo("renderSettingsEffectivePolicyTrustForError", [message]); }
  function settingsMediaPolicySummaryLines(rows = settingsMediaPolicyRows()) { return settingsPolicyImpactCall("settingsMediaPolicySummaryLines", [rows], []); }
  function renderSettingsMediaPolicyCrossCheck() { settingsPolicyImpactDo("renderSettingsMediaPolicyCrossCheck", []); }
  function settingsBackendPolicyImpact(settings = state.lastSettings) { return settingsPolicyImpactCall("settingsBackendPolicyImpact", [settings], { schema_version: "", media_policy_readiness: null, launch_risk_handoff: null }); }
  function settingsBackendMediaPolicyReadiness(settings = state.lastSettings) { return settingsPolicyImpactCall("settingsBackendMediaPolicyReadiness", [settings], { operator_status: "Not loaded", rows: [], counts: {}, summary_lines: [] }); }
  function settingsBackendMediaPolicyStatus(readiness = settingsBackendMediaPolicyReadiness()) { return settingsPolicyImpactCall("settingsBackendMediaPolicyStatus", [readiness], "Not evaluated"); }
  function settingsBackendMediaPolicySummaryLines(readiness = settingsBackendMediaPolicyReadiness()) { return settingsPolicyImpactCall("settingsBackendMediaPolicySummaryLines", [readiness], []); }
  function renderSettingsBackendMediaPolicyReadiness(settings = state.lastSettings) { settingsPolicyImpactDo("renderSettingsBackendMediaPolicyReadiness", [settings]); }
  function settingsImpactGroupForKey(key) { return settingsPolicyImpactCall("settingsImpactGroupForKey", [key], null); }
  function settingsPatchImpactEntries(patch) { return settingsPolicyImpactCall("settingsPatchImpactEntries", [patch], []); }
  function renderSettingsPatchImpactSummaryFromEntries(entries) { settingsPolicyImpactDo("renderSettingsPatchImpactSummaryFromEntries", [entries]); }
  function settingsBoolValue(value) { return settingsPolicyImpactCall("settingsBoolValue", [value], null); }
  function settingsPatchCandidateValue(entries, key) { return settingsPolicyImpactCall("settingsPatchCandidateValue", [entries, key], settingsRawConfigValue(key)); }
  function settingsStableJsonValue(value) { return settingsPolicyImpactCall("settingsStableJsonValue", [value], value); }
  function settingsPatchSignature(changes) { return settingsPolicyImpactCall("settingsPatchSignature", [changes], ""); }
  function settingsPatchRequestExtras() {
    const provider = window.mediaPipelineSettingsLibraries?.libraryProfileResetRequest;
    if (typeof provider !== "function") return {};
    try {
      const libraryProfileResets = provider();
      if (Array.isArray(libraryProfileResets) && libraryProfileResets.length) {
        return { library_profile_resets: libraryProfileResets };
      }
    } catch (_error) {
      return {};
    }
    return {};
  }
  function settingsLibraryProfilePatchStateKind() {
    const provider = window.mediaPipelineSettingsLibraries?.libraryPatchStateKind;
    if (typeof provider !== "function") return "";
    try {
      return String(provider() || "");
    } catch (_error) {
      return "";
    }
  }
  function settingsPatchHasStaleLibraryProfiles(changes) {
    return Boolean(
      changes
      && typeof changes === "object"
      && !Array.isArray(changes)
      && Object.prototype.hasOwnProperty.call(changes, "LibraryProfiles")
      && settingsLibraryProfilePatchStateKind() === "stale"
    );
  }
  function blockStaleLibraryProfilesPatch(command) {
    if (command && typeof appendCommandResult === "function") {
      appendCommandResult({
        command,
        ok: false,
        severity: "warning",
        message: "Stale LibraryProfiles patch blocked before backend settings save.",
      });
    }
    setText("settings-patch-status", "Stale LibraryProfiles blocked");
    setText(
      "settings-patch-detail",
      [
        "Changes JSON contains LibraryProfiles, but the Library Profiles editor says that patch is stale.",
        "Stage Patch from the Library Profiles tab to save the current profile editor state, or Reset From Current to remove the stale LibraryProfiles key before saving unrelated settings.",
        "No backend preview or save command was sent.",
      ].join("\n")
    );
    renderSettingsPatchSummary();
    return true;
  }
  function settingsPatchRequestSignature(changes, extras = {}) {
    if (Array.isArray(extras.library_profile_resets) && extras.library_profile_resets.length) {
      return settingsPatchSignature({ changes, library_profile_resets: extras.library_profile_resets });
    }
    return settingsPatchSignature(changes);
  }
  function settingsCurrentPatchSignature() { return settingsPolicyImpactCall("settingsCurrentPatchSignature", [], ""); }
  function settingsPatchListValue(value) { return settingsPolicyImpactCall("settingsPatchListValue", [value], []); }
  function settingsPolicyDeltaStatus(rows) { return settingsPolicyImpactCall("settingsPolicyDeltaStatus", [rows], "No current change"); }
  function settingsPolicyDeltaRows(entries) { return settingsPolicyImpactCall("settingsPolicyDeltaRows", [entries], []); }
  function settingsPolicyDeltaSummaryLines(rows) { return settingsPolicyImpactCall("settingsPolicyDeltaSummaryLines", [rows], []); }
  function renderSettingsPolicyDeltaFromEntries(entries) { settingsPolicyImpactDo("renderSettingsPolicyDeltaFromEntries", [entries]); }
  function renderSettingsPolicyDeltaForError(message) { settingsPolicyImpactDo("renderSettingsPolicyDeltaForError", [message]); }

  const settingsPatchReviewModule = window.__settingsPatchReviewModule || {};
  delete window.__settingsPatchReviewModule;
  state.settingsPatchReview = typeof settingsPatchReviewModule.createSettingsPatchReviewModule === "function"
    ? settingsPatchReviewModule.createSettingsPatchReviewModule({
      addSettingsEventHandlers: {
        addFinalLibraryPromotionRule,
        applyAudioSettingsBuilderToPatch,
        applyFileSafetySettingsBuilderToPatch,
        applyNetworkSettingsBuilderToPatch,
        applyPendingPublishSettingsBuilderToPatch,
        applyQualityDetailSettingsBuilderToPatch,
        applyQueueSettingsBuilderToPatch,
        applyRuntimeSettingsBuilderToPatch,
        applySettingsBuilderToPatch,
        applySubtitleSettingsBuilderToPatch,
        applyVideoDetailSettingsBuilderToPatch,
        browseSettingsPath,
        markAudioSettingsBuilderDirty,
        markFileSafetySettingsBuilderDirty,
        markFinalLibraryPromotionSettingsBuilderDirty,
        markNetworkSettingsBuilderDirty,
        markPendingPublishSettingsBuilderDirty,
        markQualityDetailSettingsBuilderDirty,
        markQueueSettingsBuilderDirty,
        markRuntimeSettingsBuilderDirty,
        markSettingsBuilderDirty,
        markSettingsPatchTouched,
        markSubtitleSettingsBuilderDirty,
        markVideoDetailSettingsBuilderDirty,
        previewFinalLibraryPromotionSettings,
        previewSettingsPatch,
        renderAudioSettingsBuilderGuidance,
        renderFileSafetySettingsBuilderGuidance,
        renderNetworkSettingsBuilderGuidance,
        renderPendingPublishSettingsBuilderGuidance,
        renderQualityDetailSettingsBuilderGuidance,
        renderQueueSettingsBuilderGuidance,
        renderRuntimeSettingsBuilderGuidance,
        renderSubtitleSettingsBuilderGuidance,
        renderVideoDetailSettingsBuilderGuidance,
        reloadSettingsFromDisk,
        saveFinalLibraryPromotionSettings,
        saveSettingsPatch,
        syncAudioSettingsBuilderFromConfig,
        syncFileSafetySettingsBuilderFromConfig,
        syncFinalLibraryPromotionSettingsBuilderFromConfig,
        syncNetworkSettingsBuilderFromConfig,
        syncPendingPublishSettingsBuilderFromConfig,
        syncQualityDetailSettingsBuilderFromConfig,
        syncQueueSettingsBuilderFromConfig,
        syncRuntimeSettingsBuilderFromConfig,
        syncSettingsBuilderFromConfig,
        syncSubtitleSettingsBuilderFromConfig,
        syncVideoDetailSettingsBuilderFromConfig,
        validateCurrentSettings,
      },
      appendCells,
      audioSettingsBuilderFields,
      audioSettingsBuilderState,
      browseFinalLibraryPromotionRulePath,
      byId,
      clearRows,
      fileSafetySettingsBuilderFields,
      fileSafetySettingsBuilderState,
      finalLibraryPromotionSettingsBuilderState,
      finalLibraryPromotionSettingsBuilderFields,
      formatConfigValue,
      formatSettingsChoiceLabel,
      getCommandHistory: typeof getCommandHistory === "function" ? getCommandHistory : function () { return []; },
      getLastSettings: () => state.lastSettings,
      getLastSettingsValues: () => state.lastSettingsValues,
      getSelectedSettingsSaveReviewKey: () => state.selectedSettingsSaveReviewKey,
      getSettingsBuilderState: () => ({ initialized: state.settingsBuilderInitialized, dirty: state.settingsBuilderDirty }),
      getSettingsPatchTouched: () => state.settingsPatchTouched,
      isSettingsCommand,
      makeRowSelectable,
      parseSettingsPatchJson,
      refreshSettingsBuilderChoices,
      renderSettingsActiveMediaPolicyHandoff,
      renderSettingsBackendResultForError,
      renderSettingsBackendResultFromEntries,
      renderSettingsBackendMediaPolicyReadiness,
      renderSettingsBdpgsOcrPathEvidence,
      renderSettingsVobSubOcrPathEvidence,
      renderSettingsEffectivePolicyTrustForError,
      renderSettingsEffectivePolicyTrustFromEntries,
      renderSettingsLaunchImpactHandoffForError,
      renderSettingsLaunchImpactHandoffFromEntries,
      renderSettingsMediaPolicyCrossCheck,
      renderSettingsOperatorTrust,
      renderSettingsOverview,
      renderSettingsPatchImpactSummaryForError,
      renderSettingsPatchImpactSummaryFromEntries,
      renderSettingsPolicyDeltaForError,
      renderSettingsPolicyDeltaFromEntries,
      renderAllLaunchPreflights: typeof window.renderAllLaunchPreflights === "function" ? window.renderAllLaunchPreflights : function () {},
      renderSettingsRawActionPlan,
      renderSettingsRawTriage,
      renderSettingsRows,
      renderSettingsSafetyLocks,
      refreshAudioSettingsBuilderChoices,
      refreshSettingsSelectChoices,
      runtimeSettingsBuilderFields,
      runtimeSettingsBuilderState,
      setSelectedSettingsSaveReviewKey: (value) => { state.selectedSettingsSaveReviewKey = value || ""; },
      setSettingsBuilderState: (initialized, dirty) => {
        state.settingsBuilderInitialized = Boolean(initialized);
        state.settingsBuilderDirty = Boolean(dirty);
      },
      setSettingsRows,
      setSettingsPatchTouched: (value) => { state.settingsPatchTouched = Boolean(value); },
      setText,
      settingsBoolValue,
      settingsBuilderConfigValue,
      settingsBuilderFields,
      settingsFieldAllowedValues,
      settingsBuilderInputValue,
      settingsCommandHistoryLine,
      settingsFieldDefinition,
      settingsFriendlyPersistedKeyAliases,
      settingsHasBackendFieldDefinitions,
      settingsPatchComplexBackendKeys,
      settingsPatchImpactEntries,
      settingsPatchCandidateValue,
      settingsPatchListValue,
      settingsRawConfigValue,
      settingsValuesEqual,
      networkSettingsBuilderFields,
      networkSettingsBuilderState,
      pendingPublishSettingsBuilderFields,
      pendingPublishSettingsBuilderState,
      qualityDetailSettingsBuilderFields,
      qualityDetailSettingsBuilderState,
      queueSettingsBuilderFields,
      queueSettingsBuilderState,
      subtitleSettingsBuilderFields,
      subtitleSettingsBuilderState,
      videoDetailSettingsBuilderFields,
      videoDetailSettingsBuilderState,
      updateTableStatusLegend,
    })
    : {};


    return {
      addFinalLibraryPromotionRule,
      applySettingsBuilderToPatch,
      blockStaleLibraryProfilesPatch,
      browseFinalLibraryPromotionRulePath,
      collectFinalLibraryPromotionSettingsPatch,
      collectSettingsBuilderPatch,
      ensureSettingsSaveReviewDialogGlobal,
      finalLibraryPromotionBrowseDetailLines,
      finalLibraryPromotionSettingsResultLines,
      markFinalLibraryPromotionSettingsBuilderDirty,
      markSettingsBuilderDirty,
      markSettingsPatchTouched,
      parseSettingsPatchJson,
      previewFinalLibraryPromotionSettings,
      readSettingsBuilderFloat,
      readSettingsBuilderNumber,
      renderFinalLibraryPromotionSettingsGuidance,
      renderSettingsActiveMediaPolicyHandoff,
      renderSettingsBackendMediaPolicyReadiness,
      renderSettingsEffectivePolicyTrustForError,
      renderSettingsEffectivePolicyTrustFromEntries,
      renderSettingsMediaPolicyCrossCheck,
      renderSettingsPatchImpactSummaryFromEntries,
      renderSettingsPolicyDeltaForError,
      renderSettingsPolicyDeltaFromEntries,
      saveFinalLibraryPromotionSettings,
      setFinalLibraryPromotionStatus,
      setSettingsBuilderControl,
      settingsActiveMediaPolicyRows,
      settingsActiveMediaPolicyStatus,
      settingsActiveMediaPolicySummaryLines,
      settingsBackendMediaPolicyReadiness,
      settingsBackendMediaPolicyStatus,
      settingsBackendMediaPolicySummaryLines,
      settingsBackendPolicyImpact,
      settingsBoolValue,
      settingsBuilderInputValue,
      settingsCurrentPatchSignature,
      settingsEffectivePolicyDetailLines,
      settingsEffectivePolicyRows,
      settingsEffectivePolicySummaryLines,
      settingsEffectivePolicyTrustStatus,
      settingsImpactGroupForKey,
      settingsLibraryProfilePatchStateKind,
      settingsMediaPolicyRows,
      settingsMediaPolicyStatus,
      settingsMediaPolicySummaryLines,
      settingsPatchCandidateValue,
      settingsPatchEffectiveChangedEntries,
      settingsPatchHasStaleLibraryProfiles,
      settingsPatchHasUnsavedChanges,
      settingsPatchImpactEntries,
      settingsPatchIsTouched,
      settingsPatchListValue,
      settingsPatchRequestExtras,
      settingsPatchRequestSignature,
      settingsPatchReviewFunction,
      settingsPatchSignature,
      settingsPolicyDeltaRows,
      settingsPolicyDeltaStatus,
      settingsPolicyDeltaSummaryLines,
      settingsPolicyImpactCall,
      settingsPolicyImpactDo,
      settingsPolicyImpactFunction,
      settingsRawConfigValue,
      settingsSaveReviewModalHost,
      settingsStableJsonValue,
      syncFinalLibraryPromotionSettingsBuilderFromConfig,
      syncSettingsBuilderFromConfig,
      writeSettingsPatchJson,
    };
  }

  window.__settingsViewBuilderModule = { createSettingsViewBuilderModule };
})();
