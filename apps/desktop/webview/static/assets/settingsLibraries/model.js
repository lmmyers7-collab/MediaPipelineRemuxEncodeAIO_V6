(function () {
  function createSettingsLibrariesModelModule(deps = {}) {
    const {
      activeLibraryName,
      choiceLabel,
      choiceValueLabel,
      designationValues,
      fallbackGroupByField,
      fallbackOverrideGroups,
      overrideGroupOrder,
      overrideGroupTitles,
      pathFields,
      profileCardsFromDom,
      readOverrideControlValue,
      renderLibraryPatchHandoff,
      renderLibraryStateStrip,
      settingsView,
      state,
      staticCompatibilityPresets,
    } = deps;

    function byId(id) {
      return document.getElementById(id);
    }

    function setText(id, textValue) {
      const element = byId(id);
      if (element) element.textContent = textValue;
    }

    function setLibraryFeedback(message) {
      const element = byId("settings-library-warning-summary");
      if (!element) return;
      const value = String(message || "").trim();
      element.textContent = value;
      element.hidden = !value;
    }

    function setStateBadge(id, label, stateValue) {
      const element = byId(id);
      if (!element) return;
      element.textContent = label;
      element.dataset.state = stateValue;
    }

    function setLibraryProfileCommandBusy(isBusy) {
      state.libraryProfileCommandInFlight = Boolean(isBusy);
      [
        "settings-library-build-patch-button",
        "settings-library-preview-button",
        "settings-library-save-button",
      ].forEach((id) => {
        const button = byId(id);
        if (button) button.disabled = state.libraryProfileCommandInFlight;
      });
    }

    function rejectLibraryProfileCommandWhileBusy(command) {
      if (state.libraryProfileCommandInFlight) {
        setText("settings-libraries-status", "Busy");
        renderLibraryPatchHandoff("Another Library Profile backend Save command is already in progress.");
        renderLibraryStateStrip();
        return true;
      }
      const reject = window.mediaPipelineSettingsView?.rejectSettingsCommandWhileBusy;
      if (typeof reject === "function" && reject(command, "settings-libraries-status", "")) {
        renderLibraryPatchHandoff("Another settings command is already in progress; LibraryProfiles were not rebuilt.");
        renderLibraryStateStrip();
        return true;
      }
      return false;
    }

    function config() {
      return (state.lastSettings && state.lastSettings.config) || {};
    }

    function fieldDefinitions() {
      return Array.isArray(state.lastSettings?.field_definitions) ? state.lastSettings.field_definitions : [];
    }

    function libraryProfileStates() {
      return Array.isArray(state.lastSettings?.library_profile_state) ? state.lastSettings.library_profile_state : [];
    }

    function libraryCompatibilityPresets() {
      const dynamic = Array.isArray(state.lastSettings?.library_compatibility_presets)
        ? state.lastSettings.library_compatibility_presets
        : [];
      return dynamic.length ? dynamic : staticCompatibilityPresets;
    }

    function mp4CompatibilityPreset() {
      return libraryCompatibilityPresets().find((preset) => String(preset?.id || "") === "mp4_compatibility") || null;
    }

    function profileState(profile) {
      const profileId = canonicalLibraryProfileId(profile?.id, "");
      return libraryProfileStates().find((state) => (
        canonicalLibraryProfileId(state?.library_id, "") === profileId
      )) || null;
    }

    function fieldDefinition(key) {
      return fieldDefinitions().find((field) => String(field?.key || "") === key) || null;
    }

    function hasBackendFieldDefinitions() {
      return fieldDefinitions().length > 0;
    }

    function fallbackOverrideGroup(groupKey) {
      return fallbackOverrideGroups.find((group) => group.key === groupKey) || null;
    }

    function backendOverrideFieldsForGroup(groupKey) {
      return fieldDefinitions()
        .filter((field) => field?.library_override_allowed === true && String(field?.override_group || "") === groupKey)
        .map((field) => String(field?.key || ""))
        .filter(Boolean);
    }

    function overrideFieldsForGroup(groupKey) {
      if (hasBackendFieldDefinitions()) return backendOverrideFieldsForGroup(groupKey);
      return fallbackOverrideGroup(groupKey)?.fields || [];
    }

    function fieldLibraryDesignations(field) {
      const raw = field?.library_profile_designations;
      if (!Array.isArray(raw)) return [];
      return raw
        .map((value) => String(value || "").trim().toLowerCase())
        .filter((value) => designationValues.includes(value));
    }

    function fieldAppliesToProfile(profile, key) {
      const field = fieldDefinition(key);
      const designations = fieldLibraryDesignations(field);
      if (!designations.length) return true;
      const designation = normalizeDesignation(profile?.designation, "auto");
      return designations.includes(designation);
    }

    function designationScopeText(field) {
      const designations = fieldLibraryDesignations(field);
      if (!designations.length) return "";
      return designations.map((value) => choiceValueLabel(value)).join(" / ");
    }

    function overrideGroupList() {
      return overrideGroupOrder.map((groupKey) => ({
        key: groupKey,
        title: overrideGroupTitles[groupKey] || groupKey,
        fields: overrideFieldsForGroup(groupKey),
      }));
    }

    function groupForField(key, fallbackGroup) {
      const field = fieldDefinition(key);
      if (field?.library_override_allowed === true && field?.override_group) return String(field.override_group);
      return fallbackGroupByField.get(key) || fallbackGroup;
    }

    function overrideStatus(groupKey, key, profile = null) {
      const field = fieldDefinition(key);
      if (!hasBackendFieldDefinitions()) {
        const editable = Boolean(fallbackOverrideGroup(groupKey)?.fields.includes(key));
        return { field, render: editable, editable, reason: "" };
      }
      if (!field) {
        return { field: null, render: false, editable: false, reason: "backend-unknown" };
      }
      if (field.library_override_allowed !== true) {
        const scope = String(field.scope || "global_only");
        if (scope === "source_derived" || scope === "computed_only") {
          return { field, render: true, editable: false, reason: "Source/computed — read-only" };
        }
        return { field, render: true, editable: false, reason: "Global-only — unavailable" };
      }
      if (String(field.override_group || "") !== groupKey) {
        return { field, render: true, editable: false, reason: `belongs to ${field.override_group || "another"} overrides` };
      }
      if (profile && !fieldAppliesToProfile(profile, key)) {
        return { field, render: false, editable: false, reason: `Only shown for ${designationScopeText(field)} libraries` };
      }
      return { field, render: true, editable: true, reason: "" };
    }

    function text(value) {
      return String(value ?? "").trim();
    }

    function escapeHtml(value) {
      return String(value ?? "")
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#39;");
    }

    function boolValue(value, fallback = false) {
      if (typeof value === "boolean") return value;
      if (value === null || value === undefined || value === "") return fallback;
      if (typeof value === "number") return value !== 0;
      return ["1", "true", "yes", "on", "enabled"].includes(String(value).trim().toLowerCase());
    }

    function slug(value, fallback) {
      const slugged = String(value || "").trim().toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "");
      return slugged || fallback;
    }

    function canonicalLibraryProfileId(value, fallback) {
      const id = slug(value, fallback);
      if (id === "movie" || id === "movies") return "movies";
      if (id === "show" || id === "shows" || id === "tv") return "tv";
      return id;
    }

    function emptyOverrides() {
      return { editor: {}, video: {}, subtitles: {}, audio: {} };
    }

    function defaultTracking(id) {
      const fieldDefaultKeys = { output_path: "Outsource" };
      const inheritedFields = ["output_path"];
      if (id === "movies") {
        fieldDefaultKeys.source_path = "SourceMovies";
        inheritedFields.push("source_path");
      } else if (id === "tv") {
        fieldDefaultKeys.source_path = "SourceTV";
        inheritedFields.push("source_path");
      }
      const editorFields = overrideFieldsForGroup("editor");
      const videoFields = overrideFieldsForGroup("video");
      const subtitleFields = overrideFieldsForGroup("subtitles");
      const audioFields = overrideFieldsForGroup("audio");
      return {
        schema_version: "library_profile_default_tracking.v1",
        inherited_fields: inheritedFields,
        field_default_keys: fieldDefaultKeys,
        editor_default_keys: editorFields,
        video_default_keys: videoFields,
        subtitle_default_keys: subtitleFields,
        audio_default_keys: audioFields,
        media_default_keys: [...videoFields, ...subtitleFields, ...audioFields],
      };
    }

    function normalizeDesignation(value, fallback = "auto") {
      const candidate = text(value).toLowerCase();
      if (candidate === "mixed" || candidate === "custom") return "auto";
      if (designationValues.includes(candidate)) return candidate;
      return designationValues.includes(fallback) ? fallback : "auto";
    }

    function fieldDefaultKey(profile, field) {
      const tracking = profile.default_tracking || {};
      const key = tracking.field_default_keys && tracking.field_default_keys[field];
      if (key) return text(key);
      if (field === "output_path") return "Outsource";
      if (field === "source_path" && profile.id === "movies") return "SourceMovies";
      if (field === "source_path" && profile.id === "tv") return "SourceTV";
      return "";
    }

    function fieldDefaultValue(profile, field) {
      const key = fieldDefaultKey(profile, field);
      if (key) return text(config()[key]);
      return "";
    }

    function backendPathEvidence(profile, field) {
      const evidence = profileState(profile)?.path_fields?.[field];
      return evidence && typeof evidence === "object" && !Array.isArray(evidence) ? evidence : null;
    }

    function fallbackPathEvidence(profile, field) {
      const inherited = inheritedSet(profile).has(field);
      const value = inherited ? fieldDefaultValue(profile, field) : text(profile?.[field]);
      return {
        field,
        state: inherited ? "inherited" : value ? "explicit" : "not_configured",
        source_key: inherited ? fieldDefaultKey(profile, field) : "",
        effective_value: value,
        explicit_value: inherited ? null : value,
      };
    }

    function pathEvidence(profile, field) {
      return backendPathEvidence(profile, field) || fallbackPathEvidence(profile, field);
    }

    function pathIsInherited(evidence) {
      const state = String(evidence?.state || "");
      return state === "inherited" || state === "synthesized_builtin_default";
    }

    function pathCanReset(profile, field, evidence = pathEvidence(profile, field)) {
      if (field === "promotion_destination") return false;
      if (field === "source_path") return profile.id === "movies" || profile.id === "tv";
      if (field === "output_path") return Boolean(evidence);
      return false;
    }

    function pathState(profile, field) {
      const evidence = pathEvidence(profile, field);
      const state = String(evidence?.state || "");
      if (state === "invalid_unresolved") return "Invalid pending edit";
      if (state === "not_configured") return "Read-only source/effective value";
      if (pathIsInherited(evidence)) return "Inherited from global";
      return "Library-specific";
    }

    function pathSourceText(evidence) {
      const state = String(evidence?.state || "");
      const sourceKey = text(evidence?.source_key);
      if ((state === "inherited" || state === "synthesized_builtin_default") && sourceKey) {
        return `from ${sourceKey}`;
      }
      if (state === "invalid_unresolved") return "required path is unresolved";
      return "";
    }

    function pathPickerTargetForLibraryField(field) {
      if (field === "source_path") return "settings.library.source_path";
      if (field === "output_path") return "settings.library.output_path";
      return "settings.library.promotion_destination";
    }

    function pathStateClass(stateText) {
      if (stateText === "Library-specific") return "is-custom";
      if (stateText === "Invalid pending edit") return "is-invalid";
      if (stateText === "Read-only source/effective value") return "is-readonly";
      return "is-inherited";
    }

    function defaultSettingValue(key) {
      const cfg = config();
      if (Object.prototype.hasOwnProperty.call(cfg, key)) return cfg[key];
      const field = fieldDefinition(key);
      if (field && Object.prototype.hasOwnProperty.call(field, "default_value")) return field.default_value;
      if (field && Object.prototype.hasOwnProperty.call(field, "default")) return field.default;
      return "";
    }

    function inheritedSet(profile) {
      const fields = profile.default_tracking && Array.isArray(profile.default_tracking.inherited_fields)
        ? profile.default_tracking.inherited_fields
        : [];
      return new Set(fields.map(String));
    }

    function normalizeOverrideMap(values) {
      if (!values || Array.isArray(values) || typeof values !== "object") return {};
      return Object.entries(values).reduce((result, [key, value]) => {
        result[String(key)] = value;
        return result;
      }, {});
    }

    function mergeOverrideGroup(target, group, values) {
      const normalizedGroup = group === "subtitle" ? "subtitles" : group;
      if (!target[normalizedGroup]) return;
      Object.entries(normalizeOverrideMap(values)).forEach(([key, value]) => {
        target[normalizedGroup][key] = value;
      });
    }

    function mergeLegacyOverrides(target, values, fallbackGroup) {
      Object.entries(normalizeOverrideMap(values)).forEach(([key, value]) => {
        const group = groupForField(key, fallbackGroup);
        target[group][key] = value;
      });
    }

    function normalizeOverrides(raw) {
      const overrides = emptyOverrides();
      const nested = normalizeOverrideMap(raw?.overrides);
      overrideGroupList().forEach((group) => mergeOverrideGroup(overrides, group.key, nested[group.key]));
      mergeOverrideGroup(overrides, "subtitles", nested.subtitle);
      mergeLegacyOverrides(overrides, raw?.editor_overrides, "editor");
      mergeLegacyOverrides(overrides, raw?.media_overrides, "subtitles");
      return overrides;
    }

    function inapplicableOverrideKeys(profile) {
      const overrides = normalizeOverrides(profile || {});
      const rows = [];
      overrideGroupList().forEach((group) => {
        Object.keys(overrides[group.key] || {}).forEach((key) => {
          if (fieldAppliesToProfile(profile, key)) return;
          rows.push({
            group: group.key,
            key,
            label: choiceLabel(key),
          });
        });
      });
      return rows;
    }

    function prunedOverrideWarningLines() {
      return profileCardsFromDom().flatMap((card) => {
        let rows = [];
        try {
          rows = JSON.parse(card.dataset.libraryPrunedOverrides || "[]");
        } catch (_error) {
          rows = [];
        }
        if (!Array.isArray(rows) || !rows.length) return [];
        const name = activeLibraryName(card);
        const labels = rows.map((row) => row?.label || row?.key).filter(Boolean).join(", ");
        return labels ? [`${name}: omitted designation-specific override(s) from staged LibraryProfiles: ${labels}.`] : [];
      });
    }

    function mp4CompatibilityConsequences(preset = mp4CompatibilityPreset()) {
      const consequences = Array.isArray(preset?.consequences) ? preset.consequences : [];
      return consequences.map((item) => String(item?.message || "").trim()).filter(Boolean);
    }

    function libraryCardMp4CompatibilityActive(card) {
      const row = card?.querySelector?.('[data-library-override-row][data-library-override-key="OutputContainer"]');
      const control = row?.querySelector?.("[data-library-override-control]");
      if (!row || !control || row.dataset.libraryOverride !== "true") return false;
      return String(readOverrideControlValue(control, "OutputContainer") || "").trim().toLowerCase() === "mp4";
    }

    function mp4CompatibilityWarningLines() {
      return profileCardsFromDom().flatMap((card) => {
        if (!libraryCardMp4CompatibilityActive(card)) return [];
        const name = activeLibraryName(card);
        const lines = mp4CompatibilityConsequences();
        return lines.length
          ? lines.map((line) => `${name}: ${line}`)
          : [`${name}: MP4 compatibility is enabled and will drop or rewrite media features MKV can preserve.`];
      });
    }

    function normalizeProfile(raw, index) {
      const rawId = text(raw?.id || raw?.library_id || raw?.name);
      const id = canonicalLibraryProfileId(rawId, `library-${index}`);
      const fallbackDesignation = id === "tv" ? "tv" : id === "movies" ? "movie" : "auto";
      const designation = normalizeDesignation(raw?.designation, fallbackDesignation);
      const trackingWasMissing = !raw || !raw.default_tracking;
      const tracking = { ...defaultTracking(id), ...(raw?.default_tracking || {}) };
      if (!Array.isArray(tracking.inherited_fields)) tracking.inherited_fields = [];
      if (!tracking.field_default_keys || typeof tracking.field_default_keys !== "object") {
        tracking.field_default_keys = defaultTracking(id).field_default_keys;
      }
      const normalized = {
        id,
        name: text(raw?.name) || (id === "tv" ? "TV" : id === "movies" ? "Movies" : "Library"),
        enabled: boolValue(raw?.enabled, true),
        designation,
        source_path: text(raw?.source_path),
        output_path: text(raw?.output_path),
        promotion_enabled: boolValue(raw?.promotion_enabled, false),
        promotion_destination: text(raw?.promotion_destination),
        overrides: normalizeOverrides(raw || {}),
        default_tracking: tracking,
        _trackingWasMissing: trackingWasMissing,
      };
      const inherited = inheritedSet(normalized);
      pathFields.forEach((field) => {
        if (inherited.has(field)) normalized[field] = fieldDefaultValue(normalized, field);
      });
      if (id === "movies" && !normalized.source_path) normalized.source_path = text(config().SourceMovies);
      if (id === "tv" && !normalized.source_path) normalized.source_path = text(config().SourceTV);
      if (!normalized.output_path) normalized.output_path = text(config().Outsource);
      return normalized;
    }

    function markLibraryEditorDirty() {
      state.libraryEditorDirty = true;
      state.libraryProfilePatchCurrent = false;
      state.libraryProfilePatchSaved = false;
      renderLibraryStateStrip();
    }

    function stableComparable(value) {
      if (Array.isArray(value)) return value.map((item) => stableComparable(item));
      if (value && typeof value === "object") {
        return Object.keys(value).sort().reduce((result, key) => {
          if (key.startsWith("_")) return result;
          result[key] = stableComparable(value[key]);
          return result;
        }, {});
      }
      return value;
    }

    function comparableTracking(profile) {
      const tracking = profile?.default_tracking || {};
      const fieldDefaultKeys = tracking.field_default_keys && typeof tracking.field_default_keys === "object"
        ? Object.entries(tracking.field_default_keys).reduce((result, [key, value]) => {
          result[String(key)] = text(value);
          return result;
        }, {})
        : {};
      const inheritedFields = Array.isArray(tracking.inherited_fields)
        ? tracking.inherited_fields.map(String).filter(Boolean).sort()
        : [];
      return {
        field_default_keys: fieldDefaultKeys,
        inherited_fields: inheritedFields,
      };
    }

    function comparableProfile(profile) {
      return {
        id: text(profile?.id || profile?.library_id),
        name: text(profile?.name),
        enabled: boolValue(profile?.enabled, true),
        designation: normalizeDesignation(profile?.designation, "auto"),
        source_path: text(profile?.source_path),
        output_path: text(profile?.output_path),
        promotion_enabled: boolValue(profile?.promotion_enabled, false),
        promotion_destination: text(profile?.promotion_destination),
        overrides: normalizeOverrides(profile || {}),
        default_tracking: comparableTracking(profile),
      };
    }

    function profilesEquivalent(leftProfiles, rightProfiles) {
      const left = (Array.isArray(leftProfiles) ? leftProfiles : []).map(comparableProfile);
      const right = (Array.isArray(rightProfiles) ? rightProfiles : []).map(comparableProfile);
      return JSON.stringify(stableComparable(left)) === JSON.stringify(stableComparable(right));
    }

    function currentProfilesFromSettings(settings) {
      state.lastSettings = settings || state.lastSettings || (typeof window.mediaPipelineSettingsView?.getLastSettings === "function" ? window.mediaPipelineSettingsView.getLastSettings() : null);
      const cfg = config();
      const raw = Array.isArray(cfg.LibraryProfiles) ? cfg.LibraryProfiles : [];
      const normalized = raw.map((profile, index) => normalizeProfile(profile, index + 1));
      const byProfileId = new Map(normalized.map((profile) => [profile.id, profile]));
      if (!byProfileId.has("movies")) byProfileId.set("movies", normalizeProfile({ id: "movies", name: "Movies", designation: "movie", default_tracking: defaultTracking("movies") }, 1));
      if (!byProfileId.has("tv")) byProfileId.set("tv", normalizeProfile({ id: "tv", name: "TV", designation: "tv", default_tracking: defaultTracking("tv") }, 2));
      const ordered = [byProfileId.get("movies"), byProfileId.get("tv")];
      normalized.forEach((profile) => {
        if (profile.id !== "movies" && profile.id !== "tv") ordered.push(profile);
      });
      return ordered;
    }

    function formatValue(value) {
      if (Array.isArray(value)) return value.join(", ");
      if (value && typeof value === "object") return JSON.stringify(value);
      return String(value ?? "");
    }

    function parseListText(value) {
      return String(value || "")
        .split(/[\n,]/)
        .map((item) => item.trim())
        .filter(Boolean);
    }

    function libraryWatchConfig() {
      const cfg = config();
      const action = String(cfg.WatchAction || "enqueue_only").trim().toLowerCase();
      const roots = parseListText(cfg.WatchFolderRoots);
      const debounce = Number(cfg.WatchDebounceSeconds || cfg.FileStabilityWait || 30);
      return {
        enabled: boolValue(cfg.EnableWatchFolders, false),
        autoRun: boolValue(cfg.EnableWatchFolders, false) && action === "enqueue_and_launch",
        action: action === "enqueue_and_launch" ? "enqueue_and_launch" : "enqueue_only",
        roots,
        debounce: Number.isFinite(debounce) ? Math.max(5, Math.floor(debounce)) : 30,
        respectSchedule: boolValue(cfg.WatchRespectScheduleWindow, true),
      };
    }

    function libraryWatchStatusLabel(watch = libraryWatchConfig()) {
      if (watch.autoRun) return "Auto-run enabled";
      if (watch.enabled) return "Watch only";
      return "Off";
    }

    function libraryWatchSummaryLines(watch = libraryWatchConfig()) {
      return [
        `Auto-run: ${watch.autoRun ? "enabled" : "off"}`,
        `Watch folders: ${watch.enabled ? "enabled" : "off"}`,
        "Backend authority: detection stays in the local API watch-folder manager and launches use the existing gated Run Once path.",
      ];
    }

    function libraryWatchHasActiveControl() {
      const active = document.activeElement;
      const panel = byId("settings-library-watch-panel");
      return Boolean(active instanceof Element && panel?.contains(active));
    }

    function syncLibraryWatchControlsFromConfig(settings = state.lastSettings, options = {}) {
      if (settings) state.lastSettings = settings;
      if (options?.automatic === true && libraryWatchHasActiveControl()) return;
      const watch = libraryWatchConfig();
      const autoRun = byId("settings-library-watch-auto-run");
      const respectSchedule = byId("settings-library-watch-respect-schedule");
      if (autoRun) autoRun.checked = watch.autoRun;
      if (respectSchedule) respectSchedule.checked = watch.respectSchedule;
      setText("settings-library-watch-status", libraryWatchStatusLabel(watch));
      setText("settings-library-watch-summary", libraryWatchSummaryLines(watch).join("\n"));
    }

    function collectLibraryWatchAutoRunPatch() {
      const autoRun = Boolean(byId("settings-library-watch-auto-run")?.checked);
      const respectSchedule = Boolean(byId("settings-library-watch-respect-schedule")?.checked);
      const watch = libraryWatchConfig();
      const patch = {
        EnableWatchFolders: autoRun,
        WatchAction: autoRun ? "enqueue_and_launch" : "enqueue_only",
        WatchRespectScheduleWindow: respectSchedule,
      };
      if (autoRun) {
        patch.WatchFolderRoots = [];
        patch.WatchDebounceSeconds = watch.debounce;
      }
      return patch;
    }

    function renderLibraryWatchPatchHandoff(message, patch = null) {
      const pending = patch || collectLibraryWatchAutoRunPatch();
      const staged = Object.keys(pending);
      const lines = [
        message,
        `Staged keys: ${staged.join(", ")}`,
        `Action: ${pending.WatchAction === "enqueue_and_launch" ? "gated Run Once" : "enqueue only"}`,
        "Runtime boundary: this control only stages settings; it does not scan, launch, queue, publish, rename, move, or delete media files.",
      ];
      setText("settings-library-watch-summary", lines.join("\n"));
    }

    function stageLibraryWatchAutoRunPatch() {
      const patch = collectLibraryWatchAutoRunPatch();
      if (typeof settingsView.writeSettingsPatchJson !== "function") {
        setText("settings-library-watch-status", "Settings unavailable");
        renderLibraryWatchPatchHandoff("Settings patch controls are not loaded.", patch);
        return null;
      }
      settingsView.writeSettingsPatchJson(
        patch,
        "Library auto-run toggle merged watch-folder keys into Changes JSON. Preview or Save still uses backend validation."
      );
      setText("settings-library-watch-status", patch.EnableWatchFolders ? "Auto-run staged" : "Auto-run off staged");
      renderLibraryWatchPatchHandoff("Library auto-run toggle staged through the shared settings patch.", patch);
      return patch;
    }

    async function previewLibraryWatchAutoRunPatch() {
      const patch = stageLibraryWatchAutoRunPatch();
      if (!patch) return;
      const preview = window.mediaPipelineSettingsView?.previewSettingsPatch;
      if (typeof preview !== "function") {
        setText("settings-library-watch-status", "Settings unavailable");
        renderLibraryWatchPatchHandoff("Settings preview controls are not loaded.", patch);
        return;
      }
      setText("settings-library-watch-status", "Previewing...");
      await preview();
      setText("settings-library-watch-status", "Auto-run preview finished");
    }

    async function saveLibraryWatchAutoRunPatch() {
      const patch = stageLibraryWatchAutoRunPatch();
      if (!patch) return;
      const save = window.mediaPipelineSettingsView?.saveSettingsPatch;
      if (typeof save !== "function") {
        setText("settings-library-watch-status", "Settings unavailable");
        renderLibraryWatchPatchHandoff("Settings save controls are not loaded.", patch);
        return;
      }
      setText("settings-library-watch-status", "Saving...");
      await save();
      setText("settings-library-watch-status", "Auto-run save command finished");
    }


    return {
      byId,
      setText,
      setLibraryFeedback,
      setStateBadge,
      setLibraryProfileCommandBusy,
      rejectLibraryProfileCommandWhileBusy,
      config,
      fieldDefinitions,
      libraryProfileStates,
      libraryCompatibilityPresets,
      mp4CompatibilityPreset,
      profileState,
      fieldDefinition,
      hasBackendFieldDefinitions,
      fallbackOverrideGroup,
      backendOverrideFieldsForGroup,
      overrideFieldsForGroup,
      fieldLibraryDesignations,
      fieldAppliesToProfile,
      designationScopeText,
      overrideGroupList,
      groupForField,
      overrideStatus,
      text,
      escapeHtml,
      boolValue,
      slug,
      canonicalLibraryProfileId,
      emptyOverrides,
      defaultTracking,
      normalizeDesignation,
      fieldDefaultKey,
      fieldDefaultValue,
      backendPathEvidence,
      fallbackPathEvidence,
      pathEvidence,
      pathIsInherited,
      pathCanReset,
      pathState,
      pathSourceText,
      pathPickerTargetForLibraryField,
      pathStateClass,
      defaultSettingValue,
      inheritedSet,
      normalizeOverrideMap,
      mergeOverrideGroup,
      mergeLegacyOverrides,
      normalizeOverrides,
      inapplicableOverrideKeys,
      prunedOverrideWarningLines,
      mp4CompatibilityConsequences,
      libraryCardMp4CompatibilityActive,
      mp4CompatibilityWarningLines,
      normalizeProfile,
      markLibraryEditorDirty,
      stableComparable,
      comparableTracking,
      comparableProfile,
      profilesEquivalent,
      currentProfilesFromSettings,
      formatValue,
      parseListText,
      libraryWatchConfig,
      libraryWatchStatusLabel,
      libraryWatchSummaryLines,
      libraryWatchHasActiveControl,
      syncLibraryWatchControlsFromConfig,
      collectLibraryWatchAutoRunPatch,
      renderLibraryWatchPatchHandoff,
      stageLibraryWatchAutoRunPatch,
      previewLibraryWatchAutoRunPatch,
      saveLibraryWatchAutoRunPatch,
    };
  }

  window.__settingsLibrariesModelModule = { createSettingsLibrariesModelModule };
})();
