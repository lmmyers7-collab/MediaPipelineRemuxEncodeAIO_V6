(function () {
  function createSettingsViewReviewModule(deps = {}) {
    const {
      appendCommandResult,
      appendSettingsRiskSummaryLines,
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
      audioSettingsBuilderState,
      byId,
      fileSafetySettingsBuilderState,
      finalLibraryPromotionSettingsBuilderState,
      formatConfigValue,
      markSettingsPatchTouched,
      networkSettingsBuilderState,
      parseSettingsListText,
      pendingPublishSettingsBuilderState,
      qualityDetailSettingsBuilderState,
      queueSettingsBuilderState,
      renderAllLaunchPreflights,
      renderSettingsPatchSummary,
      runtimeSettingsBuilderState,
      setText,
      settingsFieldDefinition,
      settingsFieldLabel,
      settingsPersistedKeyDisplayList,
      settingsValuesEqual,
      state,
      subtitleSettingsBuilderState,
      videoDetailSettingsBuilderState,
    } = deps;

    function settingsBuilderFlushFailureMessage(failedBuilders) {
      const names = Array.isArray(failedBuilders) && failedBuilders.length ? failedBuilders.join(", ") : "unknown builder";
      return `Fix invalid Settings builder input before Save Settings. Failed builder(s): ${names}.`;
    }

    function recordSettingsBuilderFlushFailure(command, flushResult) {
      const failedBuilders = Array.isArray(flushResult?.failedBuilders) ? flushResult.failedBuilders : [];
      const message = flushResult?.message || settingsBuilderFlushFailureMessage(failedBuilders);
      const existingDetail = byId("settings-patch-detail")?.textContent || "";
      appendCommandResult({
        command,
        ok: false,
        severity: "error",
        message,
        errors: failedBuilders,
      });
      setText("settings-patch-status", "Builder invalid");
      setText("settings-patch-detail", [message, existingDetail].filter(Boolean).join("\n"));
      renderSettingsPatchSummary();
      if (typeof renderAllLaunchPreflights === "function") renderAllLaunchPreflights();
    }

    function flushDirtySettingsBuilders() {
      // Merge any builder the operator edited (dirty) into the Changes JSON before
      // Save reads it. Without this, toggling a control only marks the builder
      // dirty and the change never reaches the patch that is actually sent to the backend.
      const flushTargets = [
        ["routing and size builder", state.settingsBuilderDirty, applySettingsBuilderToPatch],
        ["video detail builder", videoDetailSettingsBuilderState.dirty, applyVideoDetailSettingsBuilderToPatch],
        ["quality verification builder", qualityDetailSettingsBuilderState.dirty, applyQualityDetailSettingsBuilderToPatch],
        ["file safety builder", fileSafetySettingsBuilderState.dirty, applyFileSafetySettingsBuilderToPatch],
        ["network builder", networkSettingsBuilderState.dirty, applyNetworkSettingsBuilderToPatch],
        ["queue builder", queueSettingsBuilderState.dirty, applyQueueSettingsBuilderToPatch],
        ["runtime builder", runtimeSettingsBuilderState.dirty, applyRuntimeSettingsBuilderToPatch],
        ["pending publish builder", pendingPublishSettingsBuilderState.dirty, applyPendingPublishSettingsBuilderToPatch],
        ["subtitle builder", subtitleSettingsBuilderState.dirty, applySubtitleSettingsBuilderToPatch],
        ["audio builder", audioSettingsBuilderState.dirty, applyAudioSettingsBuilderToPatch],
      ];
      let flushed = 0;
      const failedBuilders = [];
      flushTargets.forEach(([label, dirty, applyFn]) => {
        if (!dirty || typeof applyFn !== "function") return;
        try {
          const result = applyFn();
          if (result === false) {
            failedBuilders.push(label);
            return;
          }
          flushed += 1;
        } catch (error) {
          const message = error instanceof Error ? error.message : String(error);
          failedBuilders.push(`${label}: ${message}`);
        }
      });
      if (failedBuilders.length) {
        return {
          ok: false,
          flushed,
          failedBuilders,
          message: settingsBuilderFlushFailureMessage(failedBuilders),
        };
      }
      return {
        ok: true,
        flushed,
        failedBuilders: [],
      };
    }

    function resetSettingsBuilderSyncState(options = {}) {
      state.settingsBuilderInitialized = false;
      state.settingsBuilderDirty = false;
      [
        videoDetailSettingsBuilderState,
        qualityDetailSettingsBuilderState,
        fileSafetySettingsBuilderState,
        networkSettingsBuilderState,
        queueSettingsBuilderState,
        runtimeSettingsBuilderState,
        pendingPublishSettingsBuilderState,
        subtitleSettingsBuilderState,
        audioSettingsBuilderState,
      ].forEach((state) => {
        state.initialized = false;
        state.dirty = false;
      });
      if (options.includeFinalLibraryPromotion) {
        finalLibraryPromotionSettingsBuilderState.initialized = false;
        finalLibraryPromotionSettingsBuilderState.dirty = false;
      }
    }

    function saveRenameCleaningFiltersFromSettingsSave(message = "Rename filter draft retained in this browser for local recovery.") {
      const releaseGroupsEditor = byId("settings-rename-filter-release-groups");
      const renameView = window.mediaPipelineRenameView || {};
      if (!releaseGroupsEditor || typeof renameView.saveRenameCleaningFilterDraft !== "function") return false;
      return renameView.saveRenameCleaningFilterDraft(message);
    }

    function mergeRenameCleaningFiltersForSave(changes) {
      const releaseGroupsEditor = byId("settings-rename-filter-release-groups");
      const renameView = window.mediaPipelineRenameView || {};
      if (!releaseGroupsEditor || typeof renameView.renameCleaningFilterConfigPatch !== "function") {
        return { changes, included: false, keys: [], draftSaved: false };
      }
      let filterPatch = {};
      try {
        filterPatch = renameView.renameCleaningFilterConfigPatch();
      } catch (error) {
        const message = error instanceof Error ? error.message : String(error);
        return { changes, included: false, keys: [], draftSaved: false, error: message };
      }
      const effectivePatch = {};
      Object.entries(filterPatch).forEach(([key, value]) => {
        const alreadyRequested = Object.prototype.hasOwnProperty.call(changes, key);
        const savedValue = state.lastSettingsValues ? state.lastSettingsValues[key] : undefined;
        const differsFromSaved = !Object.prototype.hasOwnProperty.call(state.lastSettingsValues || {}, key) || !settingsValuesEqual(savedValue, value);
        if (alreadyRequested || differsFromSaved) effectivePatch[key] = value;
      });
      const keys = Object.keys(effectivePatch);
      const draftSaved = keys.length
        ? saveRenameCleaningFiltersFromSettingsSave("Rename filters are included in the current Save Settings review.")
        : false;
      if (!keys.length) return { changes, included: false, keys, draftSaved };
      const nextChanges = { ...changes, ...effectivePatch };
      const patchNode = byId("settings-patch-json");
      if (patchNode) {
        patchNode.value = JSON.stringify(nextChanges, null, 2);
        patchNode.dispatchEvent(new Event("input", { bubbles: true }));
        patchNode.dispatchEvent(new Event("change", { bubbles: true }));
      } else {
        markSettingsPatchTouched();
      }
      renderSettingsPatchSummary();
      if (typeof renderAllLaunchPreflights === "function") renderAllLaunchPreflights();
      return { changes: nextChanges, included: true, keys, draftSaved };
    }

  function settingsSaveReviewValueText(value) {
      if (value === undefined) return "(not previously set)";
      if (Array.isArray(value) && value.some((item) => item && typeof item === "object")) {
        try {
          return JSON.stringify(value);
        } catch (_) {}
      }
      if (value && typeof value === "object") {
        try {
          return JSON.stringify(value);
        } catch (_) {}
      }
      try {
        return formatConfigValue(value) || JSON.stringify(value) || String(value);
      } catch (_) {
        try {
          return JSON.stringify(value);
        } catch {
          return String(value);
        }
      }
    }

    const renameFilterTermKeys = new Set([
      "RenameMovieFilterTerms",
      "RenameTVFilterTerms",
    ]);
    const renameFilterOptionKeys = new Set([
      "RenameMovieFilterOptions",
      "RenameTVFilterOptions",
    ]);
    const renameFilterRemoveTermKeys = new Set([
      "RenameMovieRemoveTerms",
      "RenameTVRemoveTerms",
    ]);

    function settingsSaveReviewObjectValue(value) {
      if (value && typeof value === "object" && !Array.isArray(value)) return value;
      if (typeof value !== "string") return null;
      const trimmed = value.trim();
      if (!trimmed.startsWith("{")) return null;
      try {
        const parsed = JSON.parse(trimmed);
        return parsed && typeof parsed === "object" && !Array.isArray(parsed) ? parsed : null;
      } catch (_error) {
        return null;
      }
    }

    function settingsSaveReviewTermList(value) {
      if (Array.isArray(value)) {
        return value.map((item) => String(item || "").trim()).filter(Boolean);
      }
      if (value === undefined || value === null) return [];
      if (typeof value === "string") {
        const trimmed = value.trim();
        if (!trimmed) return [];
        if (trimmed.startsWith("[")) {
          try {
            const parsed = JSON.parse(trimmed);
            if (Array.isArray(parsed)) return settingsSaveReviewTermList(parsed);
          } catch (_error) {}
        }
        return parseSettingsListText(trimmed);
      }
      return [String(value).trim()].filter(Boolean);
    }

    function settingsSaveReviewTermMap(value) {
      const map = new Map();
      settingsSaveReviewTermList(value).forEach((term) => {
        const normalized = term.toLowerCase();
        if (!map.has(normalized)) map.set(normalized, term);
      });
      return map;
    }

    function settingsSaveReviewTermDeltas(currentValue, newValue) {
      const currentMap = settingsSaveReviewTermMap(currentValue);
      const newMap = settingsSaveReviewTermMap(newValue);
      const added = [];
      const removed = [];
      newMap.forEach((term, normalized) => {
        if (!currentMap.has(normalized)) added.push(term);
      });
      currentMap.forEach((term, normalized) => {
        if (!newMap.has(normalized)) removed.push(term);
      });
      return { added, removed };
    }

    function settingsSaveReviewRenameFilterLabel(value) {
      return String(value || "").replace(/_/g, " ").replace(/\s+/g, " ").trim() || "default";
    }

    function settingsSaveReviewLimitedText(values, limit = 6) {
      const visible = values.slice(0, limit);
      const suffix = values.length > visible.length ? `, +${values.length - visible.length} more` : "";
      return `${visible.join(", ")}${suffix}`;
    }

    function settingsSaveReviewRenameTermDictionaryText(currentValue, newValue, side) {
      const currentTerms = settingsSaveReviewObjectValue(currentValue);
      const newTerms = settingsSaveReviewObjectValue(newValue);
      if (!currentTerms || !newTerms) return "";
      const keys = Array.from(new Set([...Object.keys(currentTerms), ...Object.keys(newTerms)]))
        .sort((a, b) => a.localeCompare(b));
      const addedLines = [];
      const removedLines = [];
      keys.forEach((key) => {
        const delta = settingsSaveReviewTermDeltas(currentTerms[key], newTerms[key]);
        if (delta.added.length) {
          addedLines.push(`${settingsSaveReviewRenameFilterLabel(key)}: ${settingsSaveReviewLimitedText(delta.added)}`);
        }
        if (delta.removed.length) {
          removedLines.push(`${settingsSaveReviewRenameFilterLabel(key)}: ${settingsSaveReviewLimitedText(delta.removed)}`);
        }
      });
      const lines = side === "current" ? removedLines : addedLines;
      const oppositeLines = side === "current" ? addedLines : removedLines;
      if (lines.length) {
        return `${side === "current" ? "Removed terms" : "Added terms"}: ${lines.join("; ")}. Unchanged terms hidden.`;
      }
      if (oppositeLines.length) {
        return `${side === "current" ? "No removed terms" : "No added terms"}. Unchanged terms hidden.`;
      }
      return "No added or removed terms after trim/case comparison; unchanged terms hidden.";
    }

    function settingsSaveReviewOptionState(value) {
      if (value === undefined) return "(not set)";
      if (value === true) return "on";
      if (value === false) return "off";
      const text = String(value).trim().toLowerCase();
      if (["true", "1", "yes", "on"].includes(text)) return "on";
      if (["false", "0", "no", "off"].includes(text)) return "off";
      return String(value);
    }

    function settingsSaveReviewRenameOptionDictionaryText(currentValue, newValue) {
      const currentOptions = settingsSaveReviewObjectValue(currentValue);
      const newOptions = settingsSaveReviewObjectValue(newValue);
      if (!currentOptions || !newOptions) return "";
      const keys = Array.from(new Set([...Object.keys(currentOptions), ...Object.keys(newOptions)]))
        .sort((a, b) => a.localeCompare(b));
      const changed = keys
        .filter((key) => settingsSaveReviewOptionState(currentOptions[key]) !== settingsSaveReviewOptionState(newOptions[key]))
        .map((key) => `${settingsSaveReviewRenameFilterLabel(key)}: ${settingsSaveReviewOptionState(currentOptions[key])} -> ${settingsSaveReviewOptionState(newOptions[key])}`);
      if (!changed.length) return "No option toggles changed; unchanged options hidden.";
      return `Changed toggles: ${changed.join("; ")}. Unchanged options hidden.`;
    }

    function settingsSaveReviewRenameRemoveTermsText(currentValue, newValue, side) {
      const delta = settingsSaveReviewTermDeltas(currentValue, newValue);
      const values = side === "current" ? delta.removed : delta.added;
      const oppositeValues = side === "current" ? delta.added : delta.removed;
      if (values.length) {
        return `${side === "current" ? "Removed terms" : "Added terms"}: ${settingsSaveReviewLimitedText(values)}. Unchanged terms hidden.`;
      }
      if (oppositeValues.length) {
        return `${side === "current" ? "No removed terms" : "No added terms"}. Unchanged terms hidden.`;
      }
      return "No added or removed terms after trim/case comparison; unchanged terms hidden.";
    }

    function settingsSaveReviewLibraryProfiles(value) {
      let candidate = value;
      if (typeof candidate === "string") {
        const trimmed = candidate.trim();
        if (!trimmed) return [];
        try {
          candidate = JSON.parse(trimmed);
        } catch (_error) {
          return [];
        }
      }
      if (!Array.isArray(candidate)) return [];
      return candidate.filter((profile) => profile && typeof profile === "object" && !Array.isArray(profile));
    }

    function settingsSaveReviewCanonicalProfileId(value, fallback) {
      const id = String(value || "").trim().toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "") || fallback;
      if (id === "movie" || id === "movies") return "movies";
      if (id === "show" || id === "shows" || id === "tv") return "tv";
      return id;
    }

    function settingsSaveReviewProfileId(profile, index = 0) {
      const raw = String(profile?.id || profile?.library_id || profile?.name || "").trim();
      return settingsSaveReviewCanonicalProfileId(raw, `profile-${index + 1}`);
    }

    function settingsSaveReviewProfileLabel(profile, index = 0) {
      const id = settingsSaveReviewProfileId(profile, index);
      const name = String(profile?.name || "").trim();
      return name && name !== id ? `${name} (${id})` : id;
    }

    function settingsSaveReviewPrimitiveText(value) {
      if (value === undefined) return "(not set)";
      if (value === null) return "null";
      if (Array.isArray(value) || (value && typeof value === "object")) {
        try {
          return JSON.stringify(value);
        } catch (_) {
          return String(value);
        }
      }
      return String(value);
    }

    function settingsSaveReviewProfileOverrideEntries(profile, index = 0) {
      const overrides = profile?.overrides && typeof profile.overrides === "object" && !Array.isArray(profile.overrides)
        ? profile.overrides
        : {};
      const profileId = settingsSaveReviewProfileId(profile, index);
      const profileLabel = settingsSaveReviewProfileLabel(profile, index);
      return Object.keys(overrides).sort((a, b) => a.localeCompare(b)).flatMap((group) => {
        const groupValues = overrides[group];
        if (!groupValues || typeof groupValues !== "object" || Array.isArray(groupValues)) return [];
        return Object.keys(groupValues).sort((a, b) => a.localeCompare(b)).map((key) => ({
          profileId,
          profileLabel,
          path: `${group}.${key}`,
          value: groupValues[key],
        }));
      });
    }

    function settingsSaveReviewLibraryProfileSummary(value) {
      const profiles = settingsSaveReviewLibraryProfiles(value);
      if (!profiles.length) return settingsSaveReviewValueText(value);
      const enabledCount = profiles.filter((profile) => profile.enabled !== false).length;
      const profileLabels = profiles
        .slice(0, 4)
        .map((profile, index) => settingsSaveReviewProfileLabel(profile, index));
      const profileSuffix = profiles.length > profileLabels.length ? `, +${profiles.length - profileLabels.length} more` : "";
      const overrideEntries = profiles.flatMap((profile, index) => settingsSaveReviewProfileOverrideEntries(profile, index));
      const overrideLabels = overrideEntries
        .slice(0, 5)
        .map((entry) => `${entry.profileId}.${entry.path}=${settingsSaveReviewPrimitiveText(entry.value)}`);
      const overrideSuffix = overrideEntries.length > overrideLabels.length ? `, +${overrideEntries.length - overrideLabels.length} more` : "";
      return [
        `${profiles.length} profile${profiles.length === 1 ? "" : "s"} (${enabledCount} enabled): ${profileLabels.join(", ")}${profileSuffix}`,
        overrideEntries.length ? `Overrides: ${overrideLabels.join("; ")}${overrideSuffix}` : "Overrides: none",
      ].join(". ");
    }

    function settingsSaveReviewProfileMap(profiles) {
      const map = new Map();
      profiles.forEach((profile, index) => {
        map.set(settingsSaveReviewProfileId(profile, index), { profile, index });
      });
      return map;
    }

    function settingsSaveReviewOverrideMap(profile, index = 0) {
      const map = new Map();
      settingsSaveReviewProfileOverrideEntries(profile, index).forEach((entry) => {
        map.set(entry.path, entry.value);
      });
      return map;
    }

    function settingsSaveReviewValuesDiffer(left, right) {
      try {
        return !settingsValuesEqual(left, right);
      } catch (_error) {
        return JSON.stringify(left) !== JSON.stringify(right);
      }
    }

    function settingsSaveReviewLibraryProfileDiffEntries(currentValue, newValue) {
      const currentProfiles = settingsSaveReviewLibraryProfiles(currentValue);
      const newProfiles = settingsSaveReviewLibraryProfiles(newValue);
      const currentMap = settingsSaveReviewProfileMap(currentProfiles);
      const newMap = settingsSaveReviewProfileMap(newProfiles);
      const ids = Array.from(new Set([...currentMap.keys(), ...newMap.keys()])).sort((a, b) => a.localeCompare(b));
      const topLevelKeys = ["name", "enabled", "designation", "source_path", "output_path", "promotion_enabled", "promotion_destination"];
      const entries = [];
      ids.forEach((id) => {
        const currentRecord = currentMap.get(id);
        const newRecord = newMap.get(id);
        if (!currentRecord && newRecord) {
          entries.push({
            profileLabel: settingsSaveReviewProfileLabel(newRecord.profile, newRecord.index),
            path: "profile",
            before: undefined,
            after: "added",
          });
          return;
        }
        if (currentRecord && !newRecord) {
          entries.push({
            profileLabel: settingsSaveReviewProfileLabel(currentRecord.profile, currentRecord.index),
            path: "profile",
            before: "present",
            after: undefined,
          });
          return;
        }
        if (!currentRecord || !newRecord) return;
        topLevelKeys.forEach((key) => {
          const before = currentRecord.profile[key];
          const after = newRecord.profile[key];
          if (settingsSaveReviewValuesDiffer(before, after)) {
            entries.push({
              profileLabel: settingsSaveReviewProfileLabel(newRecord.profile, newRecord.index),
              path: key,
              before,
              after,
            });
          }
        });
        const currentOverrides = settingsSaveReviewOverrideMap(currentRecord.profile, currentRecord.index);
        const newOverrides = settingsSaveReviewOverrideMap(newRecord.profile, newRecord.index);
        Array.from(new Set([...currentOverrides.keys(), ...newOverrides.keys()]))
          .sort((a, b) => a.localeCompare(b))
          .forEach((path) => {
            const before = currentOverrides.get(path);
            const after = newOverrides.get(path);
            if (settingsSaveReviewValuesDiffer(before, after)) {
              entries.push({
                profileLabel: settingsSaveReviewProfileLabel(newRecord.profile, newRecord.index),
                path,
                before,
                after,
              });
            }
          });
      });
      return entries;
    }

    function settingsSaveReviewLibraryProfileCellText(value, currentValue, newValue, side) {
      const summary = settingsSaveReviewLibraryProfileSummary(value);
      const deltas = settingsSaveReviewLibraryProfileDiffEntries(currentValue, newValue);
      if (!deltas.length) return summary;
      const valueKey = side === "current" ? "before" : "after";
      const labels = deltas
        .slice(0, 4)
        .map((entry) => `${entry.profileLabel}.${entry.path}=${settingsSaveReviewPrimitiveText(entry[valueKey])}`);
      const suffix = deltas.length > labels.length ? `, +${deltas.length - labels.length} more` : "";
      return `${summary}. ${side === "current" ? "Current" : "New"} changed values: ${labels.join("; ")}${suffix}`;
    }

    function settingsSaveReviewCellText(key, value, currentValue, newValue, side) {
      if (key === "LibraryProfiles") {
        return settingsSaveReviewLibraryProfileCellText(value, currentValue, newValue, side);
      }
      if (renameFilterTermKeys.has(key)) {
        return settingsSaveReviewRenameTermDictionaryText(currentValue, newValue, side) || "Changed; unchanged terms hidden.";
      }
      if (renameFilterOptionKeys.has(key)) {
        return settingsSaveReviewRenameOptionDictionaryText(currentValue, newValue) || "Changed; unchanged options hidden.";
      }
      if (renameFilterRemoveTermKeys.has(key)) {
        return settingsSaveReviewRenameRemoveTermsText(currentValue, newValue, side);
      }
      return settingsSaveReviewValueText(value);
    }

    function settingsSaveReviewBackendEntries(entries = []) {
      return (Array.isArray(entries) ? entries : [])
        .filter((entry) => entry && typeof entry === "object" && !Array.isArray(entry) && String(entry.key || "").trim());
    }

    function settingsSaveReviewBackendEntryForKey(entries = [], key) {
      return settingsSaveReviewBackendEntries(entries).find((entry) => String(entry.key || "") === key) || null;
    }

    function settingsReviewDigestShort(value) {
      const text = String(value || "").trim();
      return text ? `${text.slice(0, 12)}...` : "n/a";
    }

    function settingsSaveReviewSourceLabel(source) {
      const value = String(source || "").trim();
      if (value === "mirrored_from_library_profiles") return "mirrored from LibraryProfiles";
      if (value === "backend_normalized") return "backend normalized";
      if (value === "removed") return "remove request";
      if (value === "submitted") return "submitted";
      return value || "backend";
    }

    function settingsSaveReviewStatusLabel(entry) {
      const status = String(entry?.status || "").trim().toLowerCase();
      const statusLabel = status === "new" ? "New" : status === "removed" ? "Removed" : "Changed";
      const sourceLabel = settingsSaveReviewSourceLabel(entry?.source);
      return sourceLabel && sourceLabel !== "submitted" && sourceLabel !== "remove request"
        ? `${statusLabel} (${sourceLabel})`
        : statusLabel;
    }

    function settingsSaveReviewEntryCellText(entry, side) {
      const key = String(entry?.key || "");
      const currentExists = entry?.current_exists !== false;
      const newExists = entry?.new_exists !== false;
      const currentValue = currentExists ? entry.current_value : undefined;
      const newValue = newExists ? entry.new_value : undefined;
      if (side === "current") {
        return currentExists
          ? settingsSaveReviewCellText(key, currentValue, currentValue, newValue, "current")
          : "(not previously set)";
      }
      if (!newExists || String(entry?.status || "").toLowerCase() === "removed") return "(remove key)";
      return settingsSaveReviewCellText(key, newValue, currentValue, newValue, "new");
    }

    function settingsSaveReviewLibraryProfileDetailLines(currentValue, newValue) {
      const deltas = settingsSaveReviewLibraryProfileDiffEntries(currentValue, newValue);
      if (!deltas.length) {
        return ["LibraryProfiles changed, but no profile field or override delta was summarized. Use the backend redacted diff before saving."];
      }
      const lines = deltas.slice(0, 20).map((entry) => (
        `- ${entry.profileLabel}.${entry.path}: ${settingsSaveReviewPrimitiveText(entry.before)} -> ${settingsSaveReviewPrimitiveText(entry.after)}`
      ));
      if (deltas.length > lines.length) lines.push(`- +${deltas.length - lines.length} more LibraryProfiles change(s).`);
      return lines;
    }

    function settingsSaveReviewLabel(key) {
      const field = settingsFieldDefinition(key);
      return settingsFieldLabel(key, field?.label || field?.name || key);
    }

    function appendSettingsSaveReviewCell(row, value) {
      const cell = document.createElement("td");
      cell.textContent = value;
      row.appendChild(cell);
    }

    function settingsUniqueKeys(keys = []) {
      return Array.from(new Set((Array.isArray(keys) ? keys : [])
        .map((key) => String(key || "").trim())
        .filter(Boolean)));
    }

    function settingsSaveActualKeys(changedKeys = [], removedKeys = []) {
      return settingsUniqueKeys([...settingsUniqueKeys(changedKeys), ...settingsUniqueKeys(removedKeys)]);
    }

    function clearSettingsPatchCandidate() {
      const patchNode = byId("settings-patch-json");
      if (patchNode) patchNode.value = "{}";
      state.settingsPatchTouched = false;
    }

    function settingsSavePreviewDetailLines(result, localHintLines = [], options = {}) {
      const data = result?.data && typeof result.data === "object" ? result.data : {};
      const changedKeys = settingsUniqueKeys(data.changed_keys || []);
      const removedKeys = settingsUniqueKeys(data.removed_keys || []);
      const submittedCount = Number.isFinite(options.submittedCount) ? options.submittedCount : 0;
      const lines = [
        result?.message || "Backend settings save preview completed.",
        "",
        "Backend preview is authoritative for which submitted settings will actually change.",
        `Submitted keys: ${submittedCount}`,
        `Backend-confirmed changed keys: ${settingsPersistedKeyDisplayList(changedKeys) || "none"}`,
        `Backend-confirmed removed keys: ${settingsPersistedKeyDisplayList(removedKeys) || "none"}`,
        `Writes config during preview: ${data.writes_config === true ? "yes" : "no"}`,
        `Review contract: ${data.review_entries_schema_version || "legacy"}; confirmation ${settingsReviewDigestShort(data.review_confirmation?.preview_id)}`,
      ];
      if (localHintLines.length) lines.push("", ...localHintLines);
      if ((result?.errors || []).length) {
        lines.push("", "Errors:", ...(result.errors || []).map((item) => `- ${item}`));
        lines.push("Backend validation errors are authoritative; this WebView did not save or bypass them.");
      }
      if ((result?.warnings || []).length) {
        lines.push("", "Warnings:", ...(result.warnings || []).map((item) => `- ${item}`));
      }
      appendSettingsRiskSummaryLines(lines, data.risk_summary);
      if ((data.redacted_diff_lines || []).length) {
        lines.push("", "Redacted diff:", ...(data.redacted_diff_lines || []));
        if (data.diff_truncated) lines.push("...diff truncated...");
      }
      return lines;
    }

    function renderSettingsSaveReviewDialogRows({ changes, changedKeys, removedKeys, libraryProfileResetCount, reviewEntries = [] }) {
      const tbody = byId("settings-save-review-dialog-rows");
      if (!tbody) return;
      const backendEntries = settingsSaveReviewBackendEntries(reviewEntries);
      const effectiveChangedKeys = settingsUniqueKeys(changedKeys).sort((a, b) => a.localeCompare(b));
      const effectiveRemovedKeys = settingsUniqueKeys(removedKeys).sort((a, b) => a.localeCompare(b));
      tbody.replaceChildren();
      if (!backendEntries.length && !effectiveChangedKeys.length && !effectiveRemovedKeys.length && !libraryProfileResetCount) {
        const row = document.createElement("tr");
        const cell = document.createElement("td");
        cell.colSpan = 4;
        cell.textContent = "No settings changes to review.";
        row.appendChild(cell);
        tbody.appendChild(row);
        return;
      }
      if (backendEntries.length) {
        backendEntries
          .slice()
          .sort((a, b) => String(a.key || "").localeCompare(String(b.key || "")))
          .forEach((entry) => {
            const key = String(entry.key || "");
            const row = document.createElement("tr");
            appendSettingsSaveReviewCell(row, settingsSaveReviewLabel(key));
            appendSettingsSaveReviewCell(row, settingsSaveReviewEntryCellText(entry, "current"));
            appendSettingsSaveReviewCell(row, settingsSaveReviewEntryCellText(entry, "new"));
            appendSettingsSaveReviewCell(row, settingsSaveReviewStatusLabel(entry));
            tbody.appendChild(row);
          });
      }
      if (!backendEntries.length) effectiveChangedKeys.forEach((key) => {
        const row = document.createElement("tr");
        const currentExists = state.lastSettingsValues && Object.prototype.hasOwnProperty.call(state.lastSettingsValues, key);
        const currentValue = currentExists ? state.lastSettingsValues[key] : undefined;
        const newValue = changes[key];
        appendSettingsSaveReviewCell(row, settingsSaveReviewLabel(key));
        appendSettingsSaveReviewCell(row, currentExists ? settingsSaveReviewCellText(key, currentValue, currentValue, newValue, "current") : "(not previously set)");
        appendSettingsSaveReviewCell(row, settingsSaveReviewCellText(key, newValue, currentValue, newValue, "new"));
        appendSettingsSaveReviewCell(row, currentExists ? "Changed" : "New");
        tbody.appendChild(row);
      });
      if (!backendEntries.length) effectiveRemovedKeys.forEach((key) => {
        const row = document.createElement("tr");
        const currentExists = state.lastSettingsValues && Object.prototype.hasOwnProperty.call(state.lastSettingsValues, key);
        appendSettingsSaveReviewCell(row, settingsSaveReviewLabel(key));
        appendSettingsSaveReviewCell(row, currentExists ? settingsSaveReviewValueText(state.lastSettingsValues[key]) : "(not previously set)");
        appendSettingsSaveReviewCell(row, "(remove key)");
        appendSettingsSaveReviewCell(row, "Removed");
        tbody.appendChild(row);
      });
      if (!effectiveChangedKeys.length && !effectiveRemovedKeys.length && libraryProfileResetCount) {
        const row = document.createElement("tr");
        appendSettingsSaveReviewCell(row, "Library profile reset");
        appendSettingsSaveReviewCell(row, "Current profile overrides");
        appendSettingsSaveReviewCell(row, `${libraryProfileResetCount} reset request(s)`);
        appendSettingsSaveReviewCell(row, "Reset");
        tbody.appendChild(row);
      }
    }


    return {
      appendSettingsSaveReviewCell,
      clearSettingsPatchCandidate,
      flushDirtySettingsBuilders,
      mergeRenameCleaningFiltersForSave,
      recordSettingsBuilderFlushFailure,
      renderSettingsSaveReviewDialogRows,
      resetSettingsBuilderSyncState,
      saveRenameCleaningFiltersFromSettingsSave,
      settingsBuilderFlushFailureMessage,
      settingsReviewDigestShort,
      settingsSaveActualKeys,
      settingsSavePreviewDetailLines,
      settingsSaveReviewBackendEntries,
      settingsSaveReviewBackendEntryForKey,
      settingsSaveReviewCanonicalProfileId,
      settingsSaveReviewCellText,
      settingsSaveReviewEntryCellText,
      settingsSaveReviewLabel,
      settingsSaveReviewLibraryProfileCellText,
      settingsSaveReviewLibraryProfileDetailLines,
      settingsSaveReviewLibraryProfileDiffEntries,
      settingsSaveReviewLibraryProfiles,
      settingsSaveReviewLibraryProfileSummary,
      settingsSaveReviewLimitedText,
      settingsSaveReviewObjectValue,
      settingsSaveReviewOptionState,
      settingsSaveReviewOverrideMap,
      settingsSaveReviewPrimitiveText,
      settingsSaveReviewProfileId,
      settingsSaveReviewProfileLabel,
      settingsSaveReviewProfileMap,
      settingsSaveReviewProfileOverrideEntries,
      settingsSaveReviewRenameFilterLabel,
      settingsSaveReviewRenameOptionDictionaryText,
      settingsSaveReviewRenameRemoveTermsText,
      settingsSaveReviewRenameTermDictionaryText,
      settingsSaveReviewSourceLabel,
      settingsSaveReviewStatusLabel,
      settingsSaveReviewTermDeltas,
      settingsSaveReviewTermList,
      settingsSaveReviewTermMap,
      settingsSaveReviewValuesDiffer,
      settingsSaveReviewValueText,
      settingsUniqueKeys,
    };
  }

  window.__settingsViewReviewModule = { createSettingsViewReviewModule };
})();
