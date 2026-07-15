(function () {
  function createSettingsLibrariesInteractionModule(deps = {}) {
    const {
      activateLibraryProfile,
      activeLibraryCanDelete,
      activeLibraryCard,
      activeLibraryName,
      activeLibraryProfileId,
      boolValue,
      byId,
      canonicalLibraryProfileId,
      captureOpenOverrideSections,
      closeOverrideSections,
      config,
      defaultSettingValue,
      defaultTracking,
      emptyOverrides,
      fieldDefaultValue,
      fieldDefinition,
      formatValue,
      libraryCardMp4CompatibilityActive,
      libraryCompatibilityPresets,
      markLibraryEditorDirty,
      mp4CompatibilityPreset,
      mp4CompatibilityWarningLines,
      normalizeDesignation,
      normalizeProfile,
      overrideStateText,
      parseListText,
      pathFields,
      previewLibraryWatchAutoRunPatch,
      prunedOverrideWarningLines,
      rejectLibraryProfileCommandWhileBusy,
      renderActiveLibraryCommandState,
      renderCard,
      renderLibraryWatchPatchHandoff,
      renderProfileCards,
      renderSettingsLibraries,
      requestLibrarySummaryScan,
      routeBoundariesFromValues,
      routeBucketDefinitions,
      routeConsequenceSummary,
      routeEstimatedGb,
      routeFormatEstimatedGb,
      routeFormatHeight,
      routeFormatPercent,
      routeHeightPixelSummary,
      routeModel,
      routeNumberValue,
      routeRailPercentages,
      routeSourceSummary,
      routeTriggerSummary,
      routeUnknownHeightSummary,
      routeValuesFromCard,
      saveLibraryWatchAutoRunPatch,
      setLibraryFeedback,
      setLibraryProfileCommandBusy,
      setStateBadge,
      setText,
      settingsView,
      stageLibraryWatchAutoRunPatch,
      state,
      syncLibraryWatchControlsFromConfig,
      text,
    } = deps;

    function rerenderLibraryCard(card) {
      const pane = card?.closest?.("[data-library-profile-pane]");
      if (!pane) return;
      captureOpenOverrideSections();
      const profile = normalizeProfile(profileFromCard(card, 1), 1);
      pane.replaceChildren(renderCard(profile));
      state.profiles = collectProfilesFromDom();
      renderActiveLibraryCommandState();
      if (typeof window.updatePagePanelEmptyStates === "function") window.updatePagePanelEmptyStates();
    }

    function readOverrideControlValue(control, key) {
      const field = fieldDefinition(key);
      const kind = field?.kind || "";
      if (control.type === "checkbox") return Boolean(control.checked);
      if (kind === "list") return parseListText(control.value);
      if (kind === "int" || kind === "combo_int") {
        const value = Number.parseInt(control.value, 10);
        return Number.isFinite(value) ? value : control.value;
      }
      if (kind === "optional_int") {
        if (text(control.value) === "") return "";
        const value = Number.parseInt(control.value, 10);
        return Number.isFinite(value) ? value : control.value;
      }
      if (kind === "optional_float") {
        if (text(control.value) === "") return "";
        const value = Number.parseFloat(control.value);
        return Number.isFinite(value) ? value : control.value;
      }
      if (kind === "float" || field?.value_type === "number") {
        const value = Number.parseFloat(control.value);
        return Number.isFinite(value) ? value : control.value;
      }
      return control.value;
    }

    function setOverrideControlValue(control, key, value) {
      const field = fieldDefinition(key);
      if (control.type === "checkbox") {
        control.checked = boolValue(value);
        return;
      }
      if (control.tagName === "SELECT") {
        const valueText = String(value ?? "");
        if (!Array.from(control.options).some((option) => option.value === valueText) && valueText) {
          const option = document.createElement("option");
          option.value = valueText;
          option.textContent = valueText;
          control.insertBefore(option, control.firstChild);
        }
        control.value = valueText;
        return;
      }
      control.value = field?.kind === "list" ? formatValue(value) : String(value ?? "");
    }

    function libraryRouteRow(card, key) {
      return card.querySelector(`[data-library-override-row][data-library-override-key="${key}"]`);
    }

    function setLibraryOverrideValue(card, key, value, options = {}) {
      const row = libraryRouteRow(card, key);
      const control = row?.querySelector("[data-library-override-control]");
      if (!row || !control) return false;
      const wasOverride = row.dataset.libraryOverride === "true";
      const nextValue = options.reset === true ? overrideRowInheritedValue(row, key) : value;
      setOverrideControlValue(control, key, nextValue);
      if (options.reset === true) {
        updateOverrideRowState(row, false);
        if (wasOverride) row.dataset.libraryResetPending = "true";
        else delete row.dataset.libraryResetPending;
      } else {
        delete row.dataset.libraryResetPending;
        updateOverrideRowState(row, true);
      }
      return true;
    }

    function setLibraryRouteOverrideValue(card, key, value, options = {}) {
      return setLibraryOverrideValue(card, key, value, options);
    }

    function presetReasonForKey(preset, group, key) {
      const reasons = preset?.disabled_reasons?.[group];
      if (reasons && Object.prototype.hasOwnProperty.call(reasons, key)) return String(reasons[key] || "");
      return preset?.warning || "Managed by the selected library compatibility preset.";
    }

    function captureLibraryForcedRowState(row, control, key) {
      if (!row || !control || row.dataset.libraryForcedByPreset) return;
      row.dataset.libraryForcedPreviousValue = JSON.stringify(readOverrideControlValue(control, key));
      row.dataset.libraryForcedPreviousOverride = row.dataset.libraryOverride === "true" ? "true" : "false";
      row.dataset.libraryForcedPreviousResetPending = row.dataset.libraryResetPending === "true" ? "true" : "false";
    }

    function restoreLibraryForcedRowState(row, control, key) {
      if (!row || !control || !row.dataset.libraryForcedByPreset) return;
      try {
        setOverrideControlValue(control, key, JSON.parse(row.dataset.libraryForcedPreviousValue || "null"));
      } catch (_error) {
        setOverrideControlValue(control, key, overrideRowInheritedValue(row, key));
      }
      updateOverrideRowState(row, row.dataset.libraryForcedPreviousOverride === "true");
      if (row.dataset.libraryForcedPreviousResetPending === "true") row.dataset.libraryResetPending = "true";
      else delete row.dataset.libraryResetPending;
    }

    function clearLibraryForcedRowState(row) {
      delete row.dataset.libraryForcedPreviousValue;
      delete row.dataset.libraryForcedPreviousOverride;
      delete row.dataset.libraryForcedPreviousResetPending;
    }

    function syncLibraryCompatibilityAvailability(card, options = {}) {
      if (!card) return;
      const preset = mp4CompatibilityPreset();
      const active = libraryCardMp4CompatibilityActive(card);
      card.dataset.libraryCompatibilityMp4Active = active ? "true" : "false";
      const control = card.querySelector('[data-library-compatibility-preset="mp4_compatibility"]');
      if (control) {
        control.dataset.libraryCompatibilityActive = active ? "true" : "false";
        const select = control.querySelector("[data-library-compatibility-select]");
        if (select) select.value = active ? "mp4_compatibility" : "";
        const note = control.querySelector("[data-library-compatibility-note]");
        if (note) note.textContent = active
          ? (preset?.warning || preset?.summary || "MP4 compatibility is active.")
          : "Optional lossy MP4 reset preset.";
      }
      card.querySelectorAll("[data-library-override-row]").forEach((row) => {
        const group = row.getAttribute("data-library-override-group") || "";
        const key = row.getAttribute("data-library-override-key") || "";
        const control = row.querySelector("[data-library-override-control]");
        const forced = Boolean(active && preset?.overrides?.[group] && Object.prototype.hasOwnProperty.call(preset.overrides[group], key));
        const wasForced = row.dataset.libraryForcedByPreset === "mp4_compatibility";
        const drivesPreset = key === "OutputContainer";
        row.classList.toggle("is-forced", forced);
        if (forced) {
          const reason = presetReasonForKey(preset, group, key);
          if (control) {
            if (!drivesPreset) captureLibraryForcedRowState(row, control, key);
            setOverrideControlValue(control, key, preset.overrides[group][key]);
            updateOverrideRowState(row, true);
          }
          row.dataset.libraryForcedByPreset = "mp4_compatibility";
          row.dataset.libraryDisabledReason = reason;
          row.title = reason;
          if (control) {
            control.disabled = true;
            control.title = reason;
          }
        } else {
          if (wasForced && row.dataset.libraryForcedPreviousOverride !== undefined && options.preserveCurrentOnUnforce !== true) {
            restoreLibraryForcedRowState(row, control, key);
          }
          delete row.dataset.libraryForcedByPreset;
          clearLibraryForcedRowState(row);
          delete row.dataset.libraryDisabledReason;
          row.removeAttribute("title");
          if (control && row.getAttribute("data-library-override-eligible") === "true") {
            control.disabled = false;
            control.removeAttribute("title");
          }
        }
      });
    }

    function applyLibraryCompatibilityPreset(card, presetId) {
      const preset = libraryCompatibilityPresets().find((item) => String(item?.id || "") === presetId);
      if (!card || !preset?.overrides) return false;
      Object.entries(preset.overrides).forEach(([group, values]) => {
        Object.entries(values || {}).forEach(([key, value]) => {
          setLibraryOverrideValue(card, key, value);
        });
      });
      syncLibraryRouteReadouts(card);
      syncLibraryCompatibilityAvailability(card);
      return true;
    }

    function clearLibraryCompatibilityPreset(card, presetId) {
      const preset = libraryCompatibilityPresets().find((item) => String(item?.id || "") === presetId);
      if (!card || !preset?.overrides) return false;
      Object.values(preset.overrides).forEach((values) => {
        Object.keys(values || {}).forEach((key) => {
          setLibraryOverrideValue(card, key, undefined, { reset: true });
        });
      });
      syncLibraryRouteReadouts(card);
      syncLibraryCompatibilityAvailability(card, { preserveCurrentOnUnforce: true });
      return true;
    }

    function updateLibraryRouteText(card, selector, value) {
      const element = card.querySelector(selector);
      if (element) element.textContent = value;
    }

    function syncLibraryRouteReadouts(card) {
      if (!card) return;
      const editor = card.querySelector("[data-library-route-editor]");
      if (!editor) return;
      const values = routeValuesFromCard(card);
      const boundaries = routeBoundariesFromValues(values);
      const percentages = routeRailPercentages(boundaries);
      const rail = editor.querySelector("[data-library-route-rail]");
      if (rail) {
        rail.style.setProperty("--route-first-pct", `${routeFormatPercent(percentages.firstPct)}%`);
        rail.style.setProperty("--route-second-pct", `${routeFormatPercent(percentages.secondPct)}%`);
      }
      const firstBoundary = routeFormatHeight(boundaries.route1080pMaxHeight);
      const secondBoundary = routeFormatHeight(boundaries.route4kMinHeight);
      const firstInput = editor.querySelector('[data-library-route-boundary-input="first"]');
      const secondInput = editor.querySelector('[data-library-route-boundary-input="second"]');
      if (firstInput && document.activeElement !== firstInput) firstInput.value = firstBoundary;
      if (secondInput && document.activeElement !== secondInput) secondInput.value = secondBoundary;
      updateLibraryRouteText(card, '[data-library-route-readout="range-1080p"]', `uses <=${firstBoundary}p`);
      updateLibraryRouteText(card, '[data-library-route-readout="range-1440p"]', `uses ${routeFormatHeight(boundaries.route1440pMinHeight)}-${routeFormatHeight(boundaries.route1440pMaxHeight)}p`);
      updateLibraryRouteText(card, '[data-library-route-readout="range-4k"]', `uses >=${secondBoundary}p`);
      updateLibraryRouteText(card, '[data-library-route-readout="bucket-1080p"]', `uses <=${firstBoundary}p`);
      updateLibraryRouteText(card, '[data-library-route-readout="bucket-1440p"]', `uses ${routeFormatHeight(boundaries.route1440pMinHeight)}-${routeFormatHeight(boundaries.route1440pMaxHeight)}p`);
      updateLibraryRouteText(card, '[data-library-route-readout="bucket-4k"]', `uses >=${secondBoundary}p`);
      routeBucketDefinitions.forEach((bucket) => {
        const bitrate = routeNumberValue(values[bucket.bitrateKey], 0);
        const tvEstimate = routeFormatEstimatedGb(routeEstimatedGb(bitrate, bucket.estimateMinutes.tv));
        const movieEstimate = routeFormatEstimatedGb(routeEstimatedGb(bitrate, bucket.estimateMinutes.movie));
        updateLibraryRouteText(card, `[data-library-route-readout="estimate-${bucket.key}"]`, `If constant: 30m TV ~${tvEstimate}; 2h movie ~${movieEstimate}`);
      });
      updateLibraryRouteText(card, "[data-library-route-source-summary]", routeSourceSummary(values));
      updateLibraryRouteText(card, '[data-library-route-summary="trigger"]', routeTriggerSummary(values.RouteThresholdMode));
      updateLibraryRouteText(card, '[data-library-route-summary="pixel"]', routeHeightPixelSummary(boundaries));
      updateLibraryRouteText(card, '[data-library-route-summary="consequence"]', routeConsequenceSummary(boundaries, values));
      updateLibraryRouteText(card, '[data-library-route-summary="unknown"]', routeUnknownHeightSummary(values));
    }

    function applyLibraryRouteBoundary(card, boundary, rawHeight, options = {}) {
      const height = Number(rawHeight);
      if (!card || !Number.isFinite(height)) return false;
      const values = boundary === "first"
        ? typeof routeModel.valuesFromFirstBoundary === "function" ? routeModel.valuesFromFirstBoundary(height + (options.inputIsEnd === true ? 1 : 0)) : null
        : typeof routeModel.valuesFromSecondBoundary === "function" ? routeModel.valuesFromSecondBoundary(height) : null;
      if (!values) return false;
      Object.entries(values).forEach(([key, value]) => {
        setLibraryRouteOverrideValue(card, key, routeFormatPercent(value));
      });
      syncLibraryRouteReadouts(card);
      return true;
    }

    function resetLibraryRouteBoundary(card, boundary) {
      const keys = boundary === "first"
        ? ["Route1080pUpperHeightTolerancePercent", "Route1440pLowerHeightTolerancePercent"]
        : ["Route1440pUpperHeightTolerancePercent", "Route4KLowerHeightTolerancePercent"];
      keys.forEach((key) => {
        setLibraryRouteOverrideValue(card, key, undefined, { reset: true });
      });
      syncLibraryRouteReadouts(card);
    }

    function localInheritedFields(card) {
      try {
        return new Set(JSON.parse(card.dataset.localInheritedFields || "[]").map(String));
      } catch (_error) {
        return new Set();
      }
    }

    function setLocalInheritedFields(card, inherited) {
      card.dataset.localInheritedFields = JSON.stringify(Array.from(inherited));
    }

    function overrideRowInheritedValue(row, key) {
      try {
        return JSON.parse(row.dataset.libraryInheritedValue || "null");
      } catch (_error) {
        return defaultSettingValue(key);
      }
    }

    function overrideRowValuesEqual(left, right, key = "") {
      const kind = String(fieldDefinition(key)?.kind || "");
      if (kind.startsWith("optional_")) {
        const leftBlank = left === null || left === undefined || String(left).trim() === "";
        const rightBlank = right === null || right === undefined || String(right).trim() === "";
        if (leftBlank && rightBlank) return true;
      }
      return JSON.stringify(left) === JSON.stringify(right);
    }

    function updateOverrideRowState(row, isOverride) {
      row.dataset.libraryOverride = isOverride ? "true" : "false";
      row.classList.toggle("is-custom", isOverride);
      row.classList.toggle("is-inherited", !isOverride);
      const key = row.getAttribute("data-library-override-key") || "";
      const control = row.querySelector("[data-library-override-control]");
      const state = row.querySelector("[data-library-override-state-label]");
      if (state && control) {
        state.textContent = overrideStateText(isOverride, readOverrideControlValue(control, key), overrideRowInheritedValue(row, key));
        state.classList.toggle("is-custom", isOverride);
        state.classList.toggle("is-inherited", !isOverride);
      }
      const button = row.querySelector("[data-library-use-default-override]");
      if (button) {
        button.hidden = !isOverride;
        button.disabled = !isOverride;
      }
    }

    function updateEditedOverrideRowState(row) {
      const key = row.getAttribute("data-library-override-key") || "";
      const control = row.querySelector("[data-library-override-control]");
      if (!control) return;
      const persistedOverride = row.dataset.libraryPersistedOverride === "true";
      const matchesInherited = overrideRowValuesEqual(
        readOverrideControlValue(control, key),
        overrideRowInheritedValue(row, key),
        key
      );
      delete row.dataset.libraryResetPending;
      updateOverrideRowState(row, persistedOverride || !matchesInherited);
    }

    function setPathRowState(card, field, inherited) {
      const row = card.querySelector(`[data-library-field="${field}"]`)?.closest(".settings-library-path-row");
      const state = card.querySelector(`[data-library-path-state="${field}"]`);
      if (!state) return;
      const stateText = inherited ? "Inherited from global" : "Library-specific";
      state.textContent = stateText;
      state.classList.toggle("is-custom", !inherited);
      state.classList.toggle("is-inherited", inherited);
      state.classList.toggle("is-invalid", false);
      state.classList.toggle("is-readonly", false);
      const source = card.querySelector(`[data-library-path-source="${field}"]`);
      if (source) {
        const sourceKey = text(row?.dataset.libraryPathSourceKey);
        source.textContent = inherited && sourceKey ? `from ${sourceKey}` : "";
      }
      const button = card.querySelector(`[data-library-use-default="${field}"]`);
      if (button) {
        const canReset = button.getAttribute("data-library-can-reset") === "true";
        button.hidden = !canReset || inherited;
        button.disabled = !canReset || inherited;
      }
    }

    function profileFromCard(card, index) {
      const currentId = card.dataset.libraryId || `library-${index}`;
      const inherited = localInheritedFields(card);
      const fieldValue = (field) => {
        const input = card.querySelector(`[data-library-field="${field}"]`);
        if (!input) return "";
        if (input.type === "checkbox") return Boolean(input.checked);
        return input.value;
      };
      const id = canonicalLibraryProfileId(currentId || fieldValue("name"), `library-${index}`);
      const overrides = emptyOverrides();
      card.querySelectorAll("[data-library-override-row]").forEach((row) => {
        if (row.dataset.libraryOverride !== "true") return;
        const group = row.getAttribute("data-library-override-group") || "";
        const key = row.getAttribute("data-library-override-key") || "";
        const control = row.querySelector("[data-library-override-control]");
        if (!overrides[group] || !key || !control) return;
        overrides[group][key] = readOverrideControlValue(control, key);
      });
      return {
        id,
        name: text(fieldValue("name")) || (id === "tv" ? "TV" : id === "movies" ? "Movies" : "Library"),
        enabled: id === "movies" || id === "tv" ? true : Boolean(fieldValue("enabled")),
        designation: normalizeDesignation(fieldValue("designation"), "auto"),
        source_path: text(fieldValue("source_path")),
        output_path: text(fieldValue("output_path")),
        promotion_enabled: Boolean(fieldValue("promotion_enabled")),
        promotion_destination: text(fieldValue("promotion_destination")),
        overrides,
        default_tracking: {
          ...defaultTracking(id),
          inherited_fields: Array.from(inherited),
          field_default_keys: defaultTracking(id).field_default_keys,
        },
      };
    }

    function profileCardsFromDom() {
      return Array.from(document.querySelectorAll("#settings-library-profile-list .settings-library-card"));
    }

    function collectProfilesFromDom() {
      return profileCardsFromDom().map((card, index) => profileFromCard(card, index + 1));
    }

    function collectLibraryProfileResetsFromDom() {
      return profileCardsFromDom().map((card) => {
        const request = { library_id: card.dataset.libraryId || "" };
        const pathFieldsToReset = Array.from(card.querySelectorAll('[data-library-path-reset-pending="true"]'))
          .map((input) => input.getAttribute("data-library-field") || "")
          .filter(Boolean);
        if (pathFieldsToReset.length) request.path_fields = Array.from(new Set(pathFieldsToReset));
        const overrides = {};
        card.querySelectorAll('[data-library-override-row][data-library-reset-pending="true"]').forEach((row) => {
          const group = row.getAttribute("data-library-override-group") || "";
          const key = row.getAttribute("data-library-override-key") || "";
          if (!group || !key) return;
          if (!overrides[group]) overrides[group] = [];
          overrides[group].push(key);
        });
        Object.keys(overrides).forEach((group) => {
          overrides[group] = Array.from(new Set(overrides[group]));
        });
        if (Object.keys(overrides).length) request.overrides = overrides;
        return request;
      }).filter((request) => request.library_id && (Array.isArray(request.path_fields) || request.overrides));
    }

    function currentPatchIncludesLibraryProfiles() {
      const raw = byId("settings-patch-json")?.value || "{}";
      try {
        const parsed = JSON.parse(raw);
        return Boolean(parsed && typeof parsed === "object" && !Array.isArray(parsed) && Object.prototype.hasOwnProperty.call(parsed, "LibraryProfiles"));
      } catch (_error) {
        return false;
      }
    }

    function libraryPatchStateKind() {
      const hasLibraryProfiles = currentPatchIncludesLibraryProfiles();
      if (state.libraryProfilePatchSaved && !state.libraryEditorDirty) return "saved";
      if (!hasLibraryProfiles) return "none";
      if (state.libraryProfilePatchCurrent) return "staged";
      return "stale";
    }

    function renderLibraryStateStrip() {
      const patchState = libraryPatchStateKind();
      const activeId = activeLibraryProfileId();
      const editorState = state.libraryEditorDirty
        ? patchState === "staged"
          ? ["Editor: staged, unsaved", "changed"]
          : ["Editor: unstaged edits", "warning"]
        : ["Editor: saved settings", "saved"];
      const patchTextByState = {
        none: ["Patch: none staged", "empty"],
        staged: ["Patch: LibraryProfiles staged", "changed"],
        stale: ["Patch: stale LibraryProfiles", "warning"],
        saved: ["Patch: backend save returned", "saved"],
      };
      const routeState = state.libraryEditorDirty || patchState === "staged" || patchState === "stale"
        ? ["Route map: saved evidence, edits pending", "warning"]
        : ["Route map: saved backend evidence", "saved"];
      const patchStateText = patchTextByState[patchState] || patchTextByState.none;
      setStateBadge("settings-library-editor-state", editorState[0], editorState[1]);
      setStateBadge("settings-library-patch-state", patchStateText[0], patchStateText[1]);
      setStateBadge("settings-library-route-map-scope", routeState[0], routeState[1]);
      window.mediaPipelineLibraryRouteMap?.setEditorState?.({
        activeProfileId: activeId,
        dirty: state.libraryEditorDirty,
        patchState,
        patchCurrent: patchState === "staged",
      });
    }

    function clearLibraryProfilesPatchJson(reason) {
      const textarea = byId("settings-patch-json");
      if (!textarea) return false;
      let parsed;
      try {
        parsed = JSON.parse(textarea.value || "{}");
      } catch (_error) {
        return false;
      }
      if (!parsed || Array.isArray(parsed) || typeof parsed !== "object" || !Object.prototype.hasOwnProperty.call(parsed, "LibraryProfiles")) {
        return false;
      }
      delete parsed.LibraryProfiles;
      textarea.value = JSON.stringify(parsed, null, 2);
      window.mediaPipelineSettingsView?.markSettingsPatchTouched?.();
      window.mediaPipelineSettingsView?.renderSettingsPatchSummary?.();
      setText("settings-patch-status", "Library reset from current");
      setText(
        "settings-patch-detail",
        reason || "Removed LibraryProfiles from Changes JSON. Saved backend settings were not changed."
      );
      return true;
    }

    function libraryProfileResetRequest() {
      if (!currentPatchIncludesLibraryProfiles()) return [];
      state.lastLibraryProfileResetRequest = collectLibraryProfileResetsFromDom();
      return state.lastLibraryProfileResetRequest;
    }

    function buildPatchFromLibraries() {
      try {
        const libraryProfiles = collectProfilesFromDom();
        const patch = {
          LibraryProfiles: libraryProfiles,
        };
        state.lastLibraryProfileResetRequest = collectLibraryProfileResetsFromDom();
        state.libraryProfilePatchSaved = false;
        if (typeof settingsView.writeSettingsPatchJson === "function") {
          settingsView.writeSettingsPatchJson(patch, "LibraryProfiles patch built. Save Settings will validate paths, overrides, and mirrored compatibility keys.");
          state.libraryProfilePatchCurrent = true;
        } else {
          state.libraryProfilePatchCurrent = false;
        }
        state.profiles = libraryProfiles;
        renderLibraryWarningSummary();
        setText("settings-libraries-status", `${libraryProfiles.length} library profile(s) staged`);
        renderLibraryStateStrip();
        return patch;
      } catch (error) {
        const message = error instanceof Error ? error.message : String(error);
        setText("settings-libraries-status", "Library patch blocked");
        setLibraryFeedback(message);
        return null;
      }
    }

    function currentSettingsPatchKeys() {
      const raw = byId("settings-patch-json")?.value || "{}";
      try {
        const parsed = JSON.parse(raw);
        return parsed && typeof parsed === "object" && !Array.isArray(parsed) ? Object.keys(parsed) : [];
      } catch (_error) {
        return ["invalid JSON"];
      }
    }

    function renderLibraryPatchHandoff(message) {
      const patchStatus = byId("settings-patch-status")?.textContent || "No changes";
      const keys = currentSettingsPatchKeys();
      const prunedWarnings = prunedOverrideWarningLines();
      const mp4Warnings = mp4CompatibilityWarningLines();
      const lines = [
        message,
        ...mp4Warnings,
        ...prunedWarnings,
        `Shared settings patch status: ${patchStatus}`,
        `Staged keys: ${keys.length ? keys.join(", ") : "none"}`,
        "Save Library state.profiles calls the backend settings save route, asks for confirmation, and creates the normal config backup before writing.",
        "Runtime boundary: these controls do not scan, launch, publish, promote, move, or delete media files.",
      ].filter(Boolean);
      setLibraryFeedback(lines.join("\n"));
    }

    function sharedPatchStatus() {
      return text(byId("settings-patch-status")?.textContent || "");
    }

    async function previewLibraryProfiles() {
      if (rejectLibraryProfileCommandWhileBusy("settings.preview_patch")) return;
      const patch = buildPatchFromLibraries();
      if (!patch) return;
      const preview = window.mediaPipelineSettingsView?.previewSettingsPatch;
      if (typeof preview !== "function") {
        setText("settings-libraries-status", "Settings unavailable");
        renderLibraryPatchHandoff("Settings preview controls are not loaded.");
        return;
      }
      setText("settings-libraries-status", "Previewing...");
      renderLibraryPatchHandoff("Previewing staged LibraryProfiles through backend validation.");
      setLibraryProfileCommandBusy(true);
      try {
        await preview();
        const status = sharedPatchStatus();
        if (status === "Preview ready") {
          setText("settings-libraries-status", "Library preview ready");
          renderLibraryPatchHandoff("Library profile preview is ready.");
        } else {
          setText("settings-libraries-status", status ? `Library preview: ${status}` : "Library preview returned no status");
          renderLibraryPatchHandoff(`Library profile preview returned shared patch status: ${status || "not reported"}.`);
        }
      } catch (error) {
        const message = error instanceof Error ? error.message : String(error);
        setText("settings-libraries-status", "Library preview failed");
        renderLibraryPatchHandoff(`Library profile preview failed before backend success was reported: ${message}`);
      } finally {
        setLibraryProfileCommandBusy(false);
        renderLibraryStateStrip();
      }
    }

    async function saveLibraryProfiles() {
      if (rejectLibraryProfileCommandWhileBusy("settings.save_patch")) return;
      const patch = buildPatchFromLibraries();
      if (!patch) return;
      const save = window.mediaPipelineSettingsView?.saveSettingsPatch;
      if (typeof save !== "function") {
        setText("settings-libraries-status", "Settings unavailable");
        renderLibraryPatchHandoff("Settings save controls are not loaded.");
        return;
      }
      setText("settings-libraries-status", "Saving...");
      renderLibraryPatchHandoff("Saving staged LibraryProfiles through the backend settings route.");
      setLibraryProfileCommandBusy(true);
      try {
        await save();
        const status = sharedPatchStatus();
        if (status === "Saved") {
          state.libraryEditorDirty = false;
          state.libraryProfilePatchCurrent = false;
          state.libraryProfilePatchSaved = true;
          setText("settings-libraries-status", "Library profile saved");
          renderLibraryPatchHandoff("Library profile save succeeded through the backend settings route.");
        } else {
          setText("settings-libraries-status", status ? `Library save: ${status}` : "Library save returned no status");
          renderLibraryPatchHandoff(`Library profile save returned shared patch status: ${status || "not reported"}.`);
        }
      } catch (error) {
        const message = error instanceof Error ? error.message : String(error);
        setText("settings-libraries-status", "Library save failed");
        renderLibraryPatchHandoff(`Library profile save failed before backend success was reported: ${message}`);
      } finally {
        setLibraryProfileCommandBusy(false);
        renderLibraryStateStrip();
      }
    }

    function handleSettingsPostSaveRefreshFailure(message) {
      setText("settings-libraries-status", "Library save refresh failed");
      renderLibraryPatchHandoff([
        "Backend save returned success, but automatic settings refresh failed.",
        message || "Reload settings before launching to verify the saved LibraryProfiles state.",
      ].filter(Boolean).join(" "));
      renderLibraryStateStrip();
    }

    function renderLibraryWarningSummary() {
      setLibraryFeedback([...mp4CompatibilityWarningLines(), ...prunedOverrideWarningLines()].join("\n"));
    }

    function addLibraryCard() {
      const next = state.profiles.length + 1;
      const id = `library-${Date.now()}`;
      const profile = normalizeProfile({
        id,
        name: `Library ${next}`,
        enabled: true,
        designation: "auto",
        source_path: "",
        output_path: text(config().Outsource),
        promotion_enabled: false,
        promotion_destination: "",
        overrides: emptyOverrides(),
        default_tracking: {
          ...defaultTracking(id),
          inherited_fields: ["output_path"],
        },
      }, next);
      state.profiles.push(profile);
      state.activeLibraryTabId = profile.id;
      markLibraryEditorDirty();
      renderProfileCards({ activeProfileId: profile.id });
      setText("settings-libraries-status", `${state.profiles.length} library profile(s) staged`);
    }

    function deleteActiveLibrary() {
      const card = activeLibraryCard();
      if (!card) return;
      const name = activeLibraryName(card);
      if (!activeLibraryCanDelete(card)) {
        setText("settings-libraries-status", "Default library protected");
        renderLibraryPatchHandoff(`${name} cannot be deleted because Movie and TV are required default state.profiles.`);
        return;
      }
      const confirmed = typeof window.confirm === "function"
        ? window.confirm(`Delete the ${name} library profile from the unsaved Settings changes? Saved settings do not change until Save Library Profile succeeds.`)
        : true;
      if (!confirmed) {
        setText("settings-libraries-status", "Delete cancelled");
        return;
      }
      try {
        state.profiles = profileCardsFromDom()
          .filter((profileCard) => profileCard !== card)
          .map((profileCard, index) => profileFromCard(profileCard, index + 1));
      } catch (error) {
        const message = error instanceof Error ? error.message : String(error);
        setText("settings-libraries-status", "Delete blocked");
        setLibraryFeedback(message);
        return;
      }
      state.activeLibraryTabId = state.profiles[0]?.id || "movies";
      markLibraryEditorDirty();
      renderProfileCards({ activeProfileId: state.activeLibraryTabId });
      setText("settings-libraries-status", `${name} library profile removed from staged editor`);
      renderLibraryWarningSummary();
    }

    function replaceActiveLibraryValuesWithDefaults() {
      const card = activeLibraryCard();
      if (!card) return;
      const name = activeLibraryName(card);
      let resetCount = 0;
      card.querySelectorAll("[data-library-override-row]").forEach((row) => {
        const wasOverride = row.dataset.libraryOverride === "true";
        const key = row.getAttribute("data-library-override-key") || "";
        const control = row.querySelector("[data-library-override-control]");
        if (control) setOverrideControlValue(control, key, overrideRowInheritedValue(row, key));
        updateOverrideRowState(row, false);
        if (wasOverride) {
          row.dataset.libraryResetPending = "true";
          resetCount += 1;
        }
      });
      syncLibraryRouteReadouts(card);
      try {
        state.profiles = profileCardsFromDom().map((profileCard, index) => profileFromCard(profileCard, index + 1));
      } catch (error) {
        const message = error instanceof Error ? error.message : String(error);
        setText("settings-libraries-status", "Defaults blocked");
        setLibraryFeedback(message);
        return;
      }
      markLibraryEditorDirty();
      setText("settings-libraries-status", `${name} overrides reset to inherited defaults`);
      setLibraryFeedback([
        `${name}: ${resetCount} explicit override(s) marked to reset to inherited/default values in the staged editor.`,
        "Stage Patch writes the edited LibraryProfiles into Changes JSON; Preview and Save remain backend-owned.",
        ...mp4CompatibilityWarningLines(),
        ...prunedOverrideWarningLines(),
      ].filter(Boolean).join("\n"));
      renderLibraryStateStrip();
    }

    function resetFromSaved() {
      closeOverrideSections(state.activeLibraryTabId);
      state.libraryEditorDirty = false;
      state.libraryProfilePatchCurrent = false;
      state.libraryProfilePatchSaved = false;
      const cleared = clearLibraryProfilesPatchJson("Reset From Current removed LibraryProfiles from Changes JSON. Saved backend settings were not changed.");
      syncLibraryWatchControlsFromConfig(state.lastSettings);
      renderSettingsLibraries(state.lastSettings);
      setText("settings-libraries-status", cleared ? "Reset from current; staged LibraryProfiles cleared" : "Reset from current");
      renderLibraryPatchHandoff(cleared
        ? "Reset From Current restored the editor from loaded settings and cleared the staged LibraryProfiles patch."
        : "Reset From Current restored the editor from loaded settings. No LibraryProfiles patch was staged.");
      renderLibraryStateStrip();
    }

    function initSettingsLibrariesEvents() {
      const summaryRows = byId("settings-library-summary-rows");
      if (summaryRows) {
        summaryRows.addEventListener("click", (event) => {
          const target = event.target;
          if (!(target instanceof Element)) return;
          if (target.closest?.("[data-library-summary-inspect]")) return;
          const row = target.closest?.("[data-library-summary-row]");
          const libraryId = row?.getAttribute("data-library-summary-row") || "";
          if (libraryId) activateLibraryProfile(libraryId, { source: "summary-tiles" });
        });
        summaryRows.addEventListener("keydown", (event) => {
          if (event.key !== "Enter" && event.key !== " ") return;
          const target = event.target;
          if (!(target instanceof Element)) return;
          if (target.closest?.("[data-library-summary-inspect]")) return;
          const row = target.closest?.("[data-library-summary-row]");
          const libraryId = row?.getAttribute("data-library-summary-row") || "";
          if (!libraryId) return;
          event.preventDefault();
          activateLibraryProfile(libraryId, { source: "summary-tiles" });
        });
      }
      const list = byId("settings-library-profile-list");
      if (list) {
        list.addEventListener("click", (event) => {
          const target = event.target;
          if (!(target instanceof Element)) return;
          const card = target.closest?.(".settings-library-card");
          if (!card) return;
          const boundaryReset = target.getAttribute?.("data-library-route-boundary-reset");
          if (boundaryReset) {
            resetLibraryRouteBoundary(card, boundaryReset);
            markLibraryEditorDirty();
            renderLibraryWarningSummary();
            return;
          }
          const defaultField = target.getAttribute?.("data-library-use-default");
          if (defaultField) {
            const input = card.querySelector(`[data-library-field="${defaultField}"]`);
            const profile = normalizeProfile(profileFromCard(card, 1), 1);
            const button = target.closest?.("[data-library-use-default]");
            if (button && button.getAttribute("data-library-can-reset") !== "true") return;
            if (input) {
              input.value = fieldDefaultValue(profile, defaultField);
              input.dataset.inherited = "true";
              input.dataset.libraryPathResetPending = "true";
            }
            const inherited = localInheritedFields(card);
            inherited.add(defaultField);
            setLocalInheritedFields(card, inherited);
            setPathRowState(card, defaultField, true);
            markLibraryEditorDirty();
            renderLibraryWarningSummary();
            return;
          }
          if (target.matches?.("[data-library-use-default-override]")) {
            const row = target.closest("[data-library-override-row]");
            const key = row?.getAttribute("data-library-override-key") || "";
            const control = row?.querySelector("[data-library-override-control]");
            if (row && control) {
              setOverrideControlValue(control, key, overrideRowInheritedValue(row, key));
              updateOverrideRowState(row, false);
              row.dataset.libraryResetPending = "true";
            }
            syncLibraryRouteReadouts(card);
            syncLibraryCompatibilityAvailability(card);
            markLibraryEditorDirty();
            renderLibraryWarningSummary();
          }
        });
        list.addEventListener("input", (event) => {
          const target = event.target;
          if (!(target instanceof Element)) return;
          const card = target.closest?.(".settings-library-card");
          if (!card) return;
          const field = target.getAttribute?.("data-library-field");
          if (field === "name") {
            const pane = card.closest?.("[data-library-profile-pane]");
            const tabId = pane?.getAttribute("data-library-profile-pane") || card.dataset.libraryId || "";
            const tab = Array.from(byId("settings-library-profile-nav")?.querySelectorAll("[data-library-profile-nav]") || [])
              .find((item) => item.getAttribute("data-library-profile-nav") === tabId);
            if (tab) tab.textContent = text(target.value) || (tabId === "tv" ? "TV" : tabId === "movies" ? "Movies" : "Library");
            renderActiveLibraryCommandState();
          }
          if (pathFields.includes(field)) {
            const inherited = localInheritedFields(card);
            inherited.delete(field);
            setLocalInheritedFields(card, inherited);
            target.dataset.inherited = "false";
            delete target.dataset.libraryPathResetPending;
            setPathRowState(card, field, false);
          }
          if (target.matches?.("[data-library-override-control]")) {
            const row = target.closest("[data-library-override-row]");
            if (row) updateEditedOverrideRowState(row);
            syncLibraryRouteReadouts(card);
            syncLibraryCompatibilityAvailability(card);
          }
          if (field || target.matches?.("[data-library-override-control]")) markLibraryEditorDirty();
          renderLibraryWarningSummary();
        });
        list.addEventListener("change", (event) => {
          const target = event.target;
          const field = target instanceof Element ? target.getAttribute?.("data-library-field") : "";
          const compatibilitySelect = target instanceof Element ? target.getAttribute?.("data-library-compatibility-select") : null;
          const routeBoundary = target instanceof Element ? target.getAttribute?.("data-library-route-boundary-input") : "";
          if (compatibilitySelect !== null) {
            const card = target.closest?.(".settings-library-card");
            if (card) {
              const presetId = String(target.value || "");
              const changed = presetId
                ? applyLibraryCompatibilityPreset(card, presetId)
                : clearLibraryCompatibilityPreset(card, "mp4_compatibility");
              if (changed) {
                state.profiles = profileCardsFromDom().map((profileCard, index) => profileFromCard(profileCard, index + 1));
                markLibraryEditorDirty();
                setText("settings-libraries-status", presetId
                  ? `${activeLibraryName(card)} MP4 compatibility staged`
                  : `${activeLibraryName(card)} MP4 compatibility cleared`);
              }
            }
            renderLibraryWarningSummary();
            return;
          }
          if (routeBoundary) {
            const card = target.closest?.(".settings-library-card");
            if (card) {
              applyLibraryRouteBoundary(card, routeBoundary, target.value, { inputIsEnd: routeBoundary === "first" });
              markLibraryEditorDirty();
            }
            renderLibraryWarningSummary();
            return;
          }
          if (field === "designation") {
            const card = target.closest?.(".settings-library-card");
            if (card) {
              rerenderLibraryCard(card);
              syncLibraryRouteReadouts(card);
              syncLibraryCompatibilityAvailability(card);
              markLibraryEditorDirty();
            }
            renderLibraryWarningSummary();
            return;
          }
          if (target instanceof Element && target.matches?.("[data-library-override-control]")) {
            const row = target.closest("[data-library-override-row]");
            if (row) updateEditedOverrideRowState(row);
            const card = target.closest?.(".settings-library-card");
            if (card) {
              syncLibraryRouteReadouts(card);
              syncLibraryCompatibilityAvailability(card);
            }
          }
          if (target instanceof Element && (target.getAttribute?.("data-library-field") || target.matches?.("[data-library-override-control]"))) {
            markLibraryEditorDirty();
          }
          renderLibraryWarningSummary();
        });
        list.addEventListener("toggle", (event) => {
          const target = event.target;
          if (!(target instanceof Element) || !target.matches?.("details[data-library-override-section]")) return;
          const card = target.closest?.(".settings-library-card");
          const profileId = card?.dataset.libraryId || "";
          const sectionKey = target.getAttribute("data-library-override-section") || "";
          if (!profileId || !sectionKey) return;
          const openSections = state.openOverrideSectionsByLibrary.get(profileId) || new Set();
          if (target.open) openSections.add(sectionKey);
          else openSections.delete(sectionKey);
          state.openOverrideSectionsByLibrary.set(profileId, openSections);
        }, true);
      }
      byId("settings-library-add-button")?.addEventListener("click", addLibraryCard);
      byId("settings-library-delete-button")?.addEventListener("click", deleteActiveLibrary);
      byId("settings-library-defaults-button")?.addEventListener("click", replaceActiveLibraryValuesWithDefaults);
      byId("settings-library-build-patch-button")?.addEventListener("click", buildPatchFromLibraries);
      byId("settings-library-reset-button")?.addEventListener("click", resetFromSaved);
      byId("settings-library-preview-button")?.addEventListener("click", previewLibraryProfiles);
      byId("settings-library-save-button")?.addEventListener("click", saveLibraryProfiles);
      byId("settings-library-scan-sources-button")?.addEventListener("click", requestLibrarySummaryScan);
      byId("settings-library-watch-auto-run")?.addEventListener("change", () => {
        setText("settings-library-watch-status", "Auto-run toggle changed");
        renderLibraryWatchPatchHandoff("Stage the auto-run toggle to merge it into Changes JSON.");
      });
      byId("settings-library-watch-respect-schedule")?.addEventListener("change", () => {
        setText("settings-library-watch-status", "Schedule gate changed");
        renderLibraryWatchPatchHandoff("Stage the auto-run toggle to merge it into Changes JSON.");
      });
      byId("settings-library-watch-stage-button")?.addEventListener("click", stageLibraryWatchAutoRunPatch);
      byId("settings-library-watch-preview-button")?.addEventListener("click", previewLibraryWatchAutoRunPatch);
      byId("settings-library-watch-save-button")?.addEventListener("click", saveLibraryWatchAutoRunPatch);
    }

    /**
     * Public namespace for the settings libraries module.
     * Prefer this namespace from new code; flat window.* exports are transitional compatibility aliases when present.
     */

    return {
      rerenderLibraryCard,
      readOverrideControlValue,
      setOverrideControlValue,
      libraryRouteRow,
      setLibraryOverrideValue,
      setLibraryRouteOverrideValue,
      presetReasonForKey,
      syncLibraryCompatibilityAvailability,
      applyLibraryCompatibilityPreset,
      clearLibraryCompatibilityPreset,
      updateLibraryRouteText,
      syncLibraryRouteReadouts,
      applyLibraryRouteBoundary,
      resetLibraryRouteBoundary,
      localInheritedFields,
      setLocalInheritedFields,
      overrideRowInheritedValue,
      overrideRowValuesEqual,
      updateOverrideRowState,
      updateEditedOverrideRowState,
      setPathRowState,
      profileFromCard,
      profileCardsFromDom,
      collectProfilesFromDom,
      collectLibraryProfileResetsFromDom,
      currentPatchIncludesLibraryProfiles,
      libraryPatchStateKind,
      renderLibraryStateStrip,
      clearLibraryProfilesPatchJson,
      libraryProfileResetRequest,
      buildPatchFromLibraries,
      currentSettingsPatchKeys,
      renderLibraryPatchHandoff,
      sharedPatchStatus,
      previewLibraryProfiles,
      saveLibraryProfiles,
      handleSettingsPostSaveRefreshFailure,
      renderLibraryWarningSummary,
      addLibraryCard,
      deleteActiveLibrary,
      replaceActiveLibraryValuesWithDefaults,
      resetFromSaved,
      initSettingsLibrariesEvents,
    };
  }

  window.__settingsLibrariesInteractionModule = { createSettingsLibrariesInteractionModule };
})();
