(function () {
  function createSettingsViewCommandsModule(deps = {}) {
    const {
      apiPost,
      appendCommandResult,
      appendSettingsRiskSummaryLines,
      blockStaleLibraryProfilesPatch,
      byId,
      clearSettingsPatchCandidate,
      ensureSettingsSaveReviewDialogGlobal,
      flushDirtySettingsBuilders,
      markSettingsPatchTouched,
      maybeShowSettingsRuntimeRestartNotice,
      mergeRenameCleaningFiltersForSave,
      recordSettingsBuilderFlushFailure,
      rejectSettingsCommandWhileBusy,
      renderAllLaunchPreflights,
      renderSettingsPatchSummary,
      renderSettingsSaveReviewDialogRows,
      resetSettingsBuilderSyncState,
      scheduleSettingsPostSaveRefresh,
      setSettingsCommandBusy,
      setText,
      SETTINGS_PREVIEW_POST_TIMEOUT_MS,
      SETTINGS_SAVE_POST_TIMEOUT_MS,
      settingsPatchHasStaleLibraryProfiles,
      settingsPatchLocalValidationHintLines,
      settingsPatchRequestExtras,
      settingsPatchRequestSignature,
      settingsPersistedKeyDisplayList,
      settingsPostErrorMessage,
      settingsResultStatusLabel,
      settingsReviewDigestShort,
      settingsRuntimeRestartConfirmationLine,
      settingsRuntimeRestartNoticeLines,
      settingsSaveActualKeys,
      settingsSavePreviewDetailLines,
      settingsSaveReviewBackendEntries,
      settingsSaveReviewBackendEntryForKey,
      settingsSaveReviewLibraryProfileDetailLines,
      settingsStableJsonValue,
      settingsUniqueKeys,
      state,
    } = deps;

  function openSettingsSaveReviewDialog(options) {
      const dialog = ensureSettingsSaveReviewDialogGlobal(byId("settings-save-review-dialog"));
      if (!dialog || typeof dialog.showModal !== "function") {
        setText("settings-patch-status", "Review unavailable");
        setText("settings-patch-detail", "The Save Settings review dialog could not open, so no backend save command was sent.");
        return Promise.resolve(false);
      }
      const {
        changes,
        keys,
        changedKeys,
        removedKeys,
        libraryProfileResetCount,
        localHintLines,
        renameMerge,
        previewResult,
      } = options;
      const reviewEntries = settingsSaveReviewBackendEntries(previewResult?.data?.review_entries || options.reviewEntries || []);
      const effectiveChangeCount = settingsSaveActualKeys(changedKeys, removedKeys).length;
      setText(
        "settings-save-review-summary",
        `Review ${effectiveChangeCount} backend-confirmed change${effectiveChangeCount === 1 ? "" : "s"} from ${keys.length} submitted key${keys.length === 1 ? "" : "s"} before writing the active PSD1.`
      );
      setText("settings-save-review-dialog-changed", String(effectiveChangeCount));
      setText("settings-save-review-dialog-submitted", String(keys.length));
      setText("settings-save-review-dialog-resets", String(libraryProfileResetCount));
      renderSettingsSaveReviewDialogRows({ changes, changedKeys, removedKeys, libraryProfileResetCount, reviewEntries });
      const detailLines = [
        "Backend preview already filtered out submitted values that are unchanged. Confirming will save only backend-confirmed changes.",
        "Backend save will validate again, write a backup, persist the PSD1, and reload settings after confirmation.",
        settingsRuntimeRestartConfirmationLine(),
      ];
      if (renameMerge?.included) {
        detailLines.push(`Rename filter keys included: ${settingsPersistedKeyDisplayList(renameMerge.keys)}.`);
      }
      if (settingsUniqueKeys(changedKeys).includes("LibraryProfiles")) {
        const libraryProfileEntry = settingsSaveReviewBackendEntryForKey(reviewEntries, "LibraryProfiles");
        detailLines.push(
          "",
          "LibraryProfiles change detail:",
          ...settingsSaveReviewLibraryProfileDetailLines(
            libraryProfileEntry ? libraryProfileEntry.current_value : state.lastSettingsValues?.LibraryProfiles,
            libraryProfileEntry ? libraryProfileEntry.new_value : changes.LibraryProfiles
          )
        );
      }
      if ((previewResult?.warnings || []).length) {
        detailLines.push("", "Backend preview warning(s):", ...(previewResult.warnings || []).map((item) => `- ${item}`));
      }
      if (localHintLines.length) detailLines.push("", ...localHintLines);
      setText("settings-save-review-dialog-detail", detailLines.join("\n"));
      return new Promise((resolve) => {
        const form = dialog.querySelector("form");
        let settled = false;
        const cleanup = () => {
          dialog.removeEventListener("close", onClose);
          form?.removeEventListener("submit", onSubmit);
        };
        const finish = (value) => {
          if (settled) return;
          settled = true;
          cleanup();
          resolve(value);
        };
        const onSubmit = (event) => {
          event.preventDefault();
          const submitter = event.submitter;
          const value = String(submitter?.value || "cancel");
          dialog.returnValue = value;
          dialog.close(value);
        };
        const onClose = () => {
          finish(dialog.returnValue === "confirm");
        };
        dialog.addEventListener("close", onClose);
        form?.addEventListener("submit", onSubmit);
        try {
          dialog.returnValue = "cancel";
          dialog.showModal();
        } catch (error) {
          const message = error instanceof Error ? error.message : String(error);
          setText("settings-patch-status", "Review unavailable");
          setText("settings-patch-detail", `The Save Settings review dialog could not open: ${message}`);
          finish(false);
        }
      });
    }
  
    function settingsRenameLogCaseInput(id) {
      return byId(`settings-rename-log-case-${id}`);
    }
  
    function settingsRenameLogCaseValue(id) {
      return String(settingsRenameLogCaseInput(id)?.value || "").trim();
    }
  
    function settingsRenameLogCaseInteger(id, minValue, label) {
      const raw = settingsRenameLogCaseValue(id);
      if (!raw) return { value: null, error: "" };
      if (!/^\d+$/.test(raw)) return { value: null, error: `${label} must be a whole number.` };
      const value = Number.parseInt(raw, 10);
      if (!Number.isFinite(value) || value < minValue) {
        return { value: null, error: `${label} must be ${minValue} or greater.` };
      }
      return { value, error: "" };
    }
  
    function settingsRenameLogCasePayload() {
      const seasonNumber = settingsRenameLogCaseInteger("season-number", 1, "Season number");
      const expectedSeason = settingsRenameLogCaseInteger("expected-season", 0, "Expected season");
      const expectedShow = settingsRenameLogCaseValue("expected-show");
      const notes = settingsRenameLogCaseValue("notes").replace(/\s+/g, " ");
      const payload = {
        source_folder: settingsRenameLogCaseValue("source-folder"),
        source_file: settingsRenameLogCaseValue("source-file"),
        expected_name: settingsRenameLogCaseValue("expected-name"),
        expected_show: expectedShow,
        status: String(byId("settings-rename-log-case-status-select")?.value || "pending").trim().toLowerCase(),
        confirm_append: true,
      };
      if (seasonNumber.value !== null) payload.season_number = seasonNumber.value;
      if (expectedSeason.value !== null) payload.expected_season = expectedSeason.value;
      if (expectedShow) payload.expected_clean_folder = expectedShow;
      if (notes) payload.notes = notes;
      return { payload, issues: [seasonNumber.error, expectedSeason.error].filter(Boolean) };
    }
  
    function settingsRenameLogCaseRequiredIssues(payload) {
      const issues = [];
      if (!payload.source_folder) issues.push("Source folder is required.");
      if (!payload.source_file) issues.push("Source file is required.");
      if (!payload.expected_name) issues.push("Expected name is required.");
      if (!["active", "pending"].includes(payload.status)) issues.push("Status must be pending or active.");
      return issues;
    }
  
    function syncSettingsRenameLogCaseButton() {
      const button = byId("settings-rename-log-case-submit-button");
      if (button) button.disabled = state.settingsCommandInFlight || state.settingsRenameLogCaseInFlight;
    }
  
    function setSettingsRenameLogCaseBusy(isBusy) {
      state.settingsRenameLogCaseInFlight = Boolean(isBusy);
      syncSettingsRenameLogCaseButton();
    }
  
    async function submitSettingsRenameLogCase() {
      if (state.settingsRenameLogCaseInFlight) return;
      if (state.settingsCommandInFlight) {
        setText("settings-rename-log-case-status", "Busy");
        setText("settings-rename-log-case-message", "Finish the current Settings command before appending a rename filter case.");
        return;
      }
      const renameView = window.mediaPipelineRenameView || {};
      if (typeof renameView.submitRenameBadCasePayload !== "function") {
        setText("settings-rename-log-case-status", "Unavailable");
        setText("settings-rename-log-case-message", "Rename filter case logging is not loaded.");
        return;
      }
      const { payload, issues } = settingsRenameLogCasePayload();
      issues.push(...settingsRenameLogCaseRequiredIssues(payload));
      if (issues.length) {
        setText("settings-rename-log-case-status", "Needs details");
        setText("settings-rename-log-case-message", issues.join(" "));
        return;
      }
      setSettingsRenameLogCaseBusy(true);
      setText("settings-rename-log-case-status", "Appending case...");
      setText("settings-rename-log-case-message", "Appending rename filter case...");
      try {
        const result = await renameView.submitRenameBadCasePayload(payload);
        const message = result?.message || (result?.ok ? "Rename filter case appended." : "Rename filter case was not appended.");
        setText("settings-rename-log-case-status", result?.ok ? "Case appended" : "Append failed");
        setText("settings-rename-log-case-message", message);
      } catch (error) {
        const message = error instanceof Error ? error.message : String(error);
        setText("settings-rename-log-case-status", "Append failed");
        setText("settings-rename-log-case-message", message);
        appendCommandResult({ command: "rename.filter_case.append", ok: false, severity: "error", message });
      } finally {
        setSettingsRenameLogCaseBusy(false);
      }
    }
  
    function initSettingsRenameLogCaseEvents() {
      const form = byId("settings-rename-log-case-form");
      if (form && !state.settingsRenameLogCaseEventsBound) {
        form.addEventListener("submit", (event) => {
          event.preventDefault();
          submitSettingsRenameLogCase();
        });
        state.settingsRenameLogCaseEventsBound = true;
      }
      syncSettingsRenameLogCaseButton();
    }
  
    async function previewSettingsPatch() {
      if (rejectSettingsCommandWhileBusy("settings.preview_patch", "settings-patch-status", "settings-patch-detail")) return;
      const flushResult = flushDirtySettingsBuilders();
      if (!flushResult.ok) {
        recordSettingsBuilderFlushFailure("settings.preview_patch", flushResult);
        return;
      }
      const raw = byId("settings-patch-json")?.value || "{}";
      const rawAtRequest = raw;
      markSettingsPatchTouched();
      if (typeof renderAllLaunchPreflights === "function") renderAllLaunchPreflights();
      let changes;
    try {
      changes = JSON.parse(raw);
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      const result = {
        command: "settings.preview_patch",
        ok: false,
        severity: "error",
        message: `Patch JSON is invalid: ${message}`,
      };
      appendCommandResult(result);
      setText("settings-patch-status", "Invalid JSON");
      setText("settings-patch-detail", result.message);
      return;
    }
    if (!changes || Array.isArray(changes) || typeof changes !== "object") {
      const result = {
        command: "settings.preview_patch",
        ok: false,
        severity: "error",
        message: "Patch JSON must be an object of config keys and values.",
      };
      appendCommandResult(result);
      setText("settings-patch-status", "Invalid patch");
      setText("settings-patch-detail", result.message);
      return;
    }
    if (settingsPatchHasStaleLibraryProfiles(changes)) {
      blockStaleLibraryProfilesPatch("settings.preview_patch");
      return;
    }
    const requestExtras = settingsPatchRequestExtras();
    const requestSignature = settingsPatchRequestSignature(changes, requestExtras);
    const localHintLines = settingsPatchLocalValidationHintLines(changes);
    setSettingsCommandBusy(true);
    setText("settings-patch-status", "Previewing...");
    setText("settings-patch-detail", [
      "Requesting backend patch preview. This will not save the PSD1.",
      ...localHintLines,
    ].join("\n"));
    const requestId = ++state.settingsPatchPreviewRequestId;
    try {
      const result = await apiPost("/api/settings/preview-patch", { changes, ...requestExtras }, { timeoutMs: SETTINGS_PREVIEW_POST_TIMEOUT_MS });
      if (requestId !== state.settingsPatchPreviewRequestId) return;
      if ((byId("settings-patch-json")?.value || "{}") !== rawAtRequest) {
        setText("settings-patch-status", "Preview replaced");
        setText("settings-patch-detail", "Patch JSON changed before the backend preview returned. Save will review the current values before writing.");
        return;
      }
      appendCommandResult(result);
      state.lastSettingsPatchPreviewEvidence = {
        signature: requestSignature,
        command: "settings.preview_patch",
        result,
        captured_at: new Date().toISOString(),
      };
      setText("settings-patch-status", settingsResultStatusLabel(result, "Preview ready", "Preview failed"));
      const data = result.data || {};
      const lines = [
        result.message || "Settings patch preview completed.",
        "",
        `Writes config: ${data.writes_config === true ? "yes" : "no"}`,
        `Active preset: ${byId("settings-handbrake-active-preset")?.textContent || "Saved settings"}`,
        "Preset scope: display/preset adapters only; backend save writes stable persisted keys.",
        `Changed keys: ${settingsPersistedKeyDisplayList(data.changed_keys || []) || "none"}`,
        `Removed keys: ${settingsPersistedKeyDisplayList(data.removed_keys || []) || "none"}`,
        "Preview/save uses persisted keys. Friendly labels are display only and are not saved keys.",
      ];
      if (localHintLines.length) lines.push("", ...localHintLines);
      if ((result.errors || []).length) {
        lines.push("", "Errors:", ...(result.errors || []).map((item) => `- ${item}`));
        lines.push("Backend validation errors are authoritative; this WebView did not save or bypass them.");
      }
      if ((result.warnings || []).length) {
        lines.push("", "Warnings:", ...(result.warnings || []).map((item) => `- ${item}`));
      }
      appendSettingsRiskSummaryLines(lines, data.risk_summary);
      if ((data.redacted_diff_lines || []).length) {
        lines.push("", "Redacted diff:", ...(data.redacted_diff_lines || []));
        if (data.diff_truncated) lines.push("...diff truncated...");
      }
      setText("settings-patch-detail", lines.join("\n"));
      renderSettingsPatchSummary();
    } catch (error) {
      if (requestId !== state.settingsPatchPreviewRequestId) return;
      if ((byId("settings-patch-json")?.value || "{}") !== rawAtRequest) {
        setText("settings-patch-status", "Preview replaced");
        setText("settings-patch-detail", "Patch JSON changed before the backend preview returned. Save will review the current values before writing.");
        return;
      }
      const message = settingsPostErrorMessage(error, "preview");
      const result = {
        command: "settings.preview_patch",
        ok: false,
        severity: "error",
        message,
      };
      appendCommandResult(result);
      state.lastSettingsPatchPreviewEvidence = {
        signature: requestSignature,
        command: "settings.preview_patch",
        result,
        captured_at: new Date().toISOString(),
      };
      setText("settings-patch-status", "Preview failed");
      setText("settings-patch-detail", message);
      renderSettingsPatchSummary();
    } finally {
      if (requestId === state.settingsPatchPreviewRequestId) setSettingsCommandBusy(false);
    }
  }
  
  async function saveSettingsPatch() {
    if (rejectSettingsCommandWhileBusy("settings.save_patch", "settings-patch-status", "settings-patch-detail")) return;
    const flushResult = flushDirtySettingsBuilders();
    if (!flushResult.ok) {
      recordSettingsBuilderFlushFailure("settings.save_patch", flushResult);
      return;
    }
    const raw = byId("settings-patch-json")?.value || "{}";
    markSettingsPatchTouched();
    if (typeof renderAllLaunchPreflights === "function") renderAllLaunchPreflights();
    let changes;
    try {
      changes = JSON.parse(raw);
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      appendCommandResult({
        command: "settings.save_patch",
        ok: false,
        severity: "error",
        message: `Patch JSON is invalid: ${message}`,
      });
      setText("settings-patch-status", "Invalid JSON");
      setText("settings-patch-detail", `Patch JSON is invalid: ${message}`);
      return;
    }
    if (!changes || Array.isArray(changes) || typeof changes !== "object") {
      const message = "Patch JSON must be an object of config keys and values.";
      appendCommandResult({
        command: "settings.save_patch",
        ok: false,
        severity: "error",
        message,
      });
      setText("settings-patch-status", "Invalid patch");
      setText("settings-patch-detail", message);
      return;
    }
    const renameMerge = mergeRenameCleaningFiltersForSave(changes);
    if (renameMerge.error) {
      const message = `Rename filter values could not be prepared for save: ${renameMerge.error}`;
      appendCommandResult({
        command: "settings.save_patch",
        ok: false,
        severity: "error",
        message,
      });
      setText("settings-patch-status", "Rename filters invalid");
      setText("settings-patch-detail", message);
      return;
    }
    changes = renameMerge.changes;
    const requestExtras = settingsPatchRequestExtras();
    const libraryProfileResetCount = Array.isArray(requestExtras.library_profile_resets) ? requestExtras.library_profile_resets.length : 0;
    const hasLibraryProfileResets = libraryProfileResetCount > 0;
    const keys = Object.keys(changes);
    if (settingsPatchHasStaleLibraryProfiles(changes)) {
      blockStaleLibraryProfilesPatch("settings.save_patch");
      return;
    }
    if (!keys.length && !hasLibraryProfileResets) {
      setText("settings-patch-status", "No changes");
      setText("settings-patch-detail", [
        renameMerge.draftSaved ? "Rename filter draft retained in this browser for local recovery." : "",
        "No backend settings change keys were provided, so the PSD1 was not changed.",
      ].filter(Boolean).join("\n"));
      return;
    }
    const signature = settingsPatchRequestSignature(changes, requestExtras);
    const localHintLines = settingsPatchLocalValidationHintLines(changes);
    const rawAtRequest = byId("settings-patch-json")?.value || "{}";
    let previewResult;
    setSettingsCommandBusy(true);
    setText("settings-patch-status", "Previewing save...");
    setText("settings-patch-detail", [
      "Requesting backend save preview. This filters submitted keys down to settings that will actually change.",
      ...localHintLines,
    ].join("\n"));
    try {
      previewResult = await apiPost("/api/settings/preview-patch", { changes, ...requestExtras }, { timeoutMs: SETTINGS_PREVIEW_POST_TIMEOUT_MS });
    } catch (error) {
      const message = settingsPostErrorMessage(error, "preview");
      const result = {
        command: "settings.preview_patch",
        ok: false,
        severity: "error",
        message,
      };
      appendCommandResult(result);
      state.lastSettingsPatchPreviewEvidence = {
        signature,
        command: "settings.preview_patch",
        result,
        captured_at: new Date().toISOString(),
      };
      setText("settings-patch-status", "Preview failed");
      setText("settings-patch-detail", message);
      renderSettingsPatchSummary();
      setSettingsCommandBusy(false);
      return;
    }
    if ((byId("settings-patch-json")?.value || "{}") !== rawAtRequest) {
      setText("settings-patch-status", "Preview replaced");
      setText("settings-patch-detail", "Patch JSON changed before the backend save preview returned. Save again to review the current values before writing.");
      renderSettingsPatchSummary();
      setSettingsCommandBusy(false);
      return;
    }
    appendCommandResult(previewResult);
    state.lastSettingsPatchPreviewEvidence = {
      signature,
      command: "settings.preview_patch",
      result: previewResult,
      captured_at: new Date().toISOString(),
    };
    const previewData = previewResult.data && typeof previewResult.data === "object" ? previewResult.data : {};
    const reviewConfirmation = previewData.review_confirmation && typeof previewData.review_confirmation === "object"
      ? previewData.review_confirmation
      : null;
    const changedKeys = settingsUniqueKeys(previewData.changed_keys || []);
    const removedKeys = settingsUniqueKeys(previewData.removed_keys || []);
    const actualChangeKeys = settingsSaveActualKeys(changedKeys, removedKeys);
    const previewLines = settingsSavePreviewDetailLines(previewResult, localHintLines, { submittedCount: keys.length });
    if (!previewResult.ok || (previewResult.errors || []).length) {
      setText("settings-patch-status", "Preview blocked");
      setText("settings-patch-detail", previewLines.join("\n"));
      renderSettingsPatchSummary();
      setSettingsCommandBusy(false);
      return;
    }
    if (!actualChangeKeys.length) {
      clearSettingsPatchCandidate();
      resetSettingsBuilderSyncState();
      setText("settings-patch-status", "No backend changes");
      setText("settings-patch-detail", [
        renameMerge.draftSaved ? "Rename filter draft retained in this browser for local recovery." : "",
        ...previewLines,
        "",
        "No backend settings differ from the saved config, so no save command was sent.",
        "The stale save candidate was cleared to avoid reviewing unchanged values again.",
      ].filter(Boolean).join("\n"));
      renderSettingsPatchSummary();
      if (typeof renderAllLaunchPreflights === "function") renderAllLaunchPreflights();
      setSettingsCommandBusy(false);
      return;
    }
    if (!reviewConfirmation) {
      setText("settings-patch-status", "Preview missing confirmation");
      setText("settings-patch-detail", [
        ...previewLines,
        "",
        "Backend preview did not return a review_confirmation contract, so no save command was sent.",
      ].join("\n"));
      renderSettingsPatchSummary();
      setSettingsCommandBusy(false);
      return;
    }
    setText("settings-patch-status", (previewResult.warnings || []).length ? "Review warnings" : "Review ready");
    setText("settings-patch-detail", previewLines.join("\n"));
    renderSettingsPatchSummary();
    const confirmed = await openSettingsSaveReviewDialog({
      changes,
      keys,
      changedKeys,
      removedKeys,
      libraryProfileResetCount,
      localHintLines,
      renameMerge,
      previewResult,
    });
    if (!confirmed) {
      state.selectedSettingsBackendResultKey = "save-confirmation-boundary";
      setText("settings-patch-status", "Save cancelled");
      setText("settings-patch-detail", [
        "Save Settings was cancelled before any backend save command was sent.",
        "No config backup was created, no PSD1 file was written, and the current edits remain available.",
        "Launch still uses saved backend settings only; press Save Settings again when ready.",
      ].join("\n"));
      renderSettingsPatchSummary();
      if (typeof renderAllLaunchPreflights === "function") renderAllLaunchPreflights();
      setSettingsCommandBusy(false);
      return;
    }
    const snapshotBefore = {};
    actualChangeKeys.forEach((key) => {
      if (state.lastSettingsValues && Object.prototype.hasOwnProperty.call(state.lastSettingsValues, key)) {
        snapshotBefore[key] = state.lastSettingsValues[key];
      }
    });
    setText("settings-patch-status", "Saving...");
    setText("settings-patch-detail", [
      "Saving backend-validated settings changes to the active PSD1. A backup will be created first.",
      ...localHintLines,
    ].join("\n"));
    try {
      const result = await apiPost(
        "/api/settings/save-patch",
        { changes, ...requestExtras, review_confirmation: reviewConfirmation, confirm_save: true },
        { timeoutMs: SETTINGS_SAVE_POST_TIMEOUT_MS }
      );
      appendCommandResult(result);
      state.lastSettingsPatchSaveEvidence = {
        signature,
        command: "settings.save_patch",
        result,
        changes: settingsStableJsonValue(changes),
        snapshot_before: snapshotBefore,
        captured_at: new Date().toISOString(),
      };
      setText("settings-patch-status", settingsResultStatusLabel(result, "Saved", "Save failed"));
      const data = result.data || {};
      const saveReviewEntries = settingsSaveReviewBackendEntries(data.review_entries || []);
      const lines = [
        result.message || "Settings save completed.",
        "",
        `Writes config: ${data.writes_config === true ? "yes" : "no"}`,
        `Config: ${data.config_path || ""}`,
        `Backup: ${data.backup_path || ""}`,
        `Reloaded: ${data.reloaded === true ? "yes" : data.reloaded === false ? "no" : "n/a"}`,
        `Reload verified: ${data.save_verification?.verified_from_reload === true ? "yes" : data.save_verification?.verified_from_reload === false ? "no" : "n/a"}`,
        `Review confirmation: ${settingsReviewDigestShort(data.review_confirmation?.preview_id)}`,
        `Active preset: ${byId("settings-handbrake-active-preset")?.textContent || "Saved settings"}`,
        "Preset scope: display/preset adapters only; backend save writes stable persisted keys.",
        `Changed keys: ${settingsPersistedKeyDisplayList(data.changed_keys || []) || "none"}`,
        `Removed keys: ${settingsPersistedKeyDisplayList(data.removed_keys || []) || "none"}`,
        "Save uses persisted keys. Friendly labels are display only and are not saved keys.",
      ];
      if (localHintLines.length) lines.push("", ...localHintLines);
      if (result.ok) {
        lines.push("", ...settingsRuntimeRestartNoticeLines(result));
      }
      if ((result.errors || []).length) {
        lines.push("", "Errors:", ...(result.errors || []).map((item) => `- ${item}`));
        lines.push("Backend validation errors are authoritative; this WebView did not save or bypass them.");
      }
      if ((result.warnings || []).length) {
        lines.push("", "Warnings:", ...(result.warnings || []).map((item) => `- ${item}`));
      }
      appendSettingsRiskSummaryLines(lines, data.risk_summary);
      if ((data.redacted_diff_lines || []).length) {
        lines.push("", "Redacted diff:", ...(data.redacted_diff_lines || []));
        if (data.diff_truncated) lines.push("...diff truncated...");
      }
      if (result.ok && Object.keys(snapshotBefore).length) {
        lines.push("", "Overwrite record (values replaced by this save):");
        Object.keys(snapshotBefore).sort().forEach((key) => {
          const reviewEntry = settingsSaveReviewBackendEntryForKey(saveReviewEntries, key);
          const afterValue = reviewEntry && reviewEntry.new_exists !== false ? reviewEntry.new_value : changes[key];
          lines.push(`  ${key}: ${JSON.stringify(snapshotBefore[key])} -> ${JSON.stringify(afterValue)}`);
        });
        if (data.backup_path) lines.push(`  Backup: ${data.backup_path}`);
      }
      if (result.ok) {
        clearSettingsPatchCandidate();
        resetSettingsBuilderSyncState();
      }
      setText("settings-patch-detail", lines.join("\n"));
      renderSettingsPatchSummary();
      maybeShowSettingsRuntimeRestartNotice(result);
      if (result.ok) {
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
      state.lastSettingsPatchSaveEvidence = {
        signature,
        command: "settings.save_patch",
        result,
        captured_at: new Date().toISOString(),
      };
      setText("settings-patch-status", "Save failed");
      setText("settings-patch-detail", message);
      renderSettingsPatchSummary();
    } finally {
      setSettingsCommandBusy(false);
    }
  }
  

    return {
      initSettingsRenameLogCaseEvents,
      openSettingsSaveReviewDialog,
      previewSettingsPatch,
      saveSettingsPatch,
      setSettingsRenameLogCaseBusy,
      settingsRenameLogCaseInput,
      settingsRenameLogCaseInteger,
      settingsRenameLogCasePayload,
      settingsRenameLogCaseRequiredIssues,
      settingsRenameLogCaseValue,
      submitSettingsRenameLogCase,
      syncSettingsRenameLogCaseButton,
    };
  }

  window.__settingsViewCommandsModule = { createSettingsViewCommandsModule };
})();
