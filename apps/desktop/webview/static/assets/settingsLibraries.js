(function () {
  const metadata = window.mediaPipelineSettingsMetadata || {};
  const choiceLabels = metadata.settingsChoiceLabels || {};
  const routeModel = window.mediaPipelineRoutePolicyModel || {};
  const advancedFallbackKeys = new Set(metadata.settingsAdvancedFallbackKeys || []);
  const staticCompatibilityPresets = Array.isArray(metadata.settingsLibraryCompatibilityPresets)
    ? metadata.settingsLibraryCompatibilityPresets
    : [];
  const pathFields = ["source_path", "output_path", "promotion_destination"];
  const designationValues = ["movie", "tv", "auto"];
  const routeToleranceKeys = [
    "Route1080pUpperHeightTolerancePercent",
    "Route1440pLowerHeightTolerancePercent",
    "Route1440pUpperHeightTolerancePercent",
    "Route4KLowerHeightTolerancePercent",
  ];
  const routeSizeFields = [
    "RoutingProfile",
    "SizeGuardMode",
    "RouteThresholdMode",
    "MaxEncodeGrowthPercent",
    "CompatibilityEncodeGrowthPercent",
    "MovieRoute1080pTargetSizeGB",
    "MovieRoute1440pTargetSizeGB",
    "MovieRoute4KTargetSizeGB",
    "TVRoute1080pTargetSizeGB",
    "TVRoute1440pTargetSizeGB",
    "TVRoute4KTargetSizeGB",
    ...routeToleranceKeys,
    "Route1080pMaxVideoBitrateMbps",
    "Route1440pMaxVideoBitrateMbps",
    "Route4KMaxVideoBitrateMbps",
  ];
  const routeBucketDefinitions = [
    {
      key: "1080p",
      label: "1080p",
      targetLabel: "1080p",
      movieTargetKey: "MovieRoute1080pTargetSizeGB",
      tvTargetKey: "TVRoute1080pTargetSizeGB",
      bitrateKey: "Route1080pMaxVideoBitrateMbps",
      estimateMinutes: { tv: 30, movie: 120 },
    },
    {
      key: "1440p",
      label: "1440p",
      targetLabel: "1440p",
      movieTargetKey: "MovieRoute1440pTargetSizeGB",
      tvTargetKey: "TVRoute1440pTargetSizeGB",
      bitrateKey: "Route1440pMaxVideoBitrateMbps",
      estimateMinutes: { tv: 30, movie: 120 },
    },
    {
      key: "4k",
      label: "4K",
      targetLabel: "4K",
      movieTargetKey: "MovieRoute4KTargetSizeGB",
      tvTargetKey: "TVRoute4KTargetSizeGB",
      bitrateKey: "Route4KMaxVideoBitrateMbps",
      estimateMinutes: { tv: 30, movie: 120 },
    },
  ];

  const overrideGroupTitles = {
    editor: "Default Editor Overrides",
    video: "Default Video / Media Overrides",
    subtitles: "Default Subtitle Overrides",
    audio: "Default Audio Overrides",
  };
  const overrideGroupOrder = ["editor", "video", "subtitles", "audio"];
  const fallbackOverrideGroups = [
    { key: "editor", fields: metadata.settingsBuilderFields || [] },
    { key: "video", fields: metadata.videoDetailSettingsBuilderFields || [] },
    { key: "subtitles", fields: metadata.subtitleSettingsBuilderFields || [] },
    { key: "audio", fields: metadata.audioSettingsBuilderFields || [] },
  ].map((group) => ({
    ...group,
    title: overrideGroupTitles[group.key],
    fields: group.fields.map((field) => String(field?.[0] || "")).filter(Boolean),
  }));

  const overrideLayouts = {
    editor: [
      { type: "routeSize", fields: ["RoutingProfile", "SizeGuardMode", "RouteThresholdMode", "MaxEncodeGrowthPercent", "CompatibilityEncodeGrowthPercent", "MovieRoute1080pTargetSizeGB", "MovieRoute1440pTargetSizeGB", "MovieRoute4KTargetSizeGB", "TVRoute1080pTargetSizeGB", "TVRoute1440pTargetSizeGB", "TVRoute4KTargetSizeGB", "Route1080pUpperHeightTolerancePercent", "Route1440pLowerHeightTolerancePercent", "Route1440pUpperHeightTolerancePercent", "Route4KLowerHeightTolerancePercent", "Route1080pMaxVideoBitrateMbps", "Route1440pMaxVideoBitrateMbps", "Route4KMaxVideoBitrateMbps"] },
      { type: "grid", fields: ["EncodeTuningPreset", "EncodeLadder", "VideoCodec", "OutputContainer"] },
      { type: "compatibility" },
      { type: "note", text: "Library editor overrides affect only content routed through this library. Backend Save remains authoritative before future runs use these values." },
    ],
    video: [
      { type: "grid", fields: ["VideoPreset", "VideoQuality", "H264RemuxMaxBitrateMbps", "H264RemuxMaxHeight", "FallbackCpuQuality", "CpuEncodePreset", "CpuEncodeProcessPriority", "CpuEncodeMaxThreads"] },
      { type: "options", fields: ["AllowH264RemuxIfPlexCompatible"] },
      { type: "full", fields: ["RemuxSafeVideoCodecs", "ExtraVideoFlags"] },
      { type: "note", text: "Use this for direct-copy allowlists and fallback encode controls. Backend Save remains authoritative before any future run uses these values." },
    ],
    subtitles: [
      { type: "grid", fields: ["SubKeepLanguages", "Tx3gExtractLanguages", "BdpgsExtractLanguages", "VobSubExtractLanguages", "SubSDHTitleKeywords", "SubSupplementalKeywords", "MergeThresholdMs", "SubtitleExtractTimeoutSeconds", "SubtitleProbeTimeoutSeconds", "BdpgsOcrTimeoutSeconds", "VobSubOcrTimeoutSeconds", "ExcludeSubtitleStyles", "IncludeSubtitleStyles"] },
      { type: "panel", title: "TX3G", note: "MP4 timed text / mov_text policy", fields: ["ConvertTx3gToSrt", "DropTx3gAfterConversion", "CreateExternalTx3gSrtSidecars", "Tx3gPreserveExistingSrt", "Tx3gTreatForcedAsSeparate", "TreatTx3gSignsSongsAsForced"] },
      { type: "panel", title: "BDPGS", note: "Blu-ray image subtitle OCR policy", fields: ["ConvertBdpgsToSrt", "DropBdpgsAfterConversion", "TreatBdpgsSignsSongsAsForced"], gridFields: ["BdpgsOcrToolPath", "BdpgsOcrTessdataPath"] },
      { type: "panel", title: "VobSub", note: "DVD bitmap subtitle OCR policy", fields: ["ConvertVobSubToSrt", "DropVobSubAfterConversion", "TreatVobSubSignsSongsAsForced"], gridFields: ["VobSubOcrToolPath"] },
      { type: "panel", title: "ASS / SSA", note: "Styled subtitle conversion policy", fields: ["DropAssAfterConversion", "RemoveKaraoke", "StripFormatting", "MergeAdjacent", "KeepSignsAndSongs", "TreatAssSignsSongsAsForced"] },
      { type: "note", text: "Original subtitle tracks remain governed by the selected drop toggles." },
    ],
    audio: [
      { type: "grid", fields: ["AudioPassthroughProfile", "CompatibleAudioCodecs", "PreferredDefaultAudioLanguages", "AudioTranscodeCodec", "AudioTranscodeBitrate", "AudioTranscodeAutoBitrateByChannels", "AudioDownmixMode", "AudioMaxChannels", "AllowNoAudio"] },
      { type: "note", text: "Audio overrides are staged with the selected library. Leave no-audio output disabled for normal Plex libraries." },
    ],
  };

  const fallbackGroupByField = new Map();
  fallbackOverrideGroups.forEach((group) => {
    group.fields.forEach((field) => {
      if (!fallbackGroupByField.has(field)) fallbackGroupByField.set(field, group.key);
    });
  });

  let lastSettings = null;
  let profiles = [];
  let activeLibraryTabId = "movies";
  let libraryEditorDirty = false;
  let libraryProfilePatchCurrent = false;
  let libraryProfilePatchSaved = false;
  let libraryProfileCommandInFlight = false;
  let lastLibraryProfileResetRequest = [];
  const openOverrideSectionsByLibrary = new Map();

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
    libraryProfileCommandInFlight = Boolean(isBusy);
    [
      "settings-library-build-patch-button",
      "settings-library-preview-button",
      "settings-library-save-button",
    ].forEach((id) => {
      const button = byId(id);
      if (button) button.disabled = libraryProfileCommandInFlight;
    });
  }

  function rejectLibraryProfileCommandWhileBusy(command) {
    if (libraryProfileCommandInFlight) {
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
    return (lastSettings && lastSettings.config) || {};
  }

  function fieldDefinitions() {
    return Array.isArray(lastSettings?.field_definitions) ? lastSettings.field_definitions : [];
  }

  function libraryProfileStates() {
    return Array.isArray(lastSettings?.library_profile_state) ? lastSettings.library_profile_state : [];
  }

  function libraryCompatibilityPresets() {
    const dynamic = Array.isArray(lastSettings?.library_compatibility_presets)
      ? lastSettings.library_compatibility_presets
      : [];
    return dynamic.length ? dynamic : staticCompatibilityPresets;
  }

  function mp4CompatibilityPreset() {
    return libraryCompatibilityPresets().find((preset) => String(preset?.id || "") === "mp4_compatibility") || null;
  }

  function profileState(profile) {
    const profileId = String(profile?.id || "");
    return libraryProfileStates().find((state) => String(state?.library_id || "") === profileId) || null;
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
    let id = slug(rawId, `library-${index}`);
    if (id === "movie") id = "movies";
    if (id === "show" || id === "shows") id = "tv";
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
    libraryEditorDirty = true;
    libraryProfilePatchCurrent = false;
    libraryProfilePatchSaved = false;
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
    lastSettings = settings || lastSettings || (typeof window.getLastSettings === "function" ? window.getLastSettings() : null);
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
    const rootsLabel = watch.roots.length
      ? `${watch.roots.length} explicit root${watch.roots.length === 1 ? "" : "s"}`
      : "Library Profile source roots";
    return [
      `Auto-run: ${watch.autoRun ? "enabled" : "off"}`,
      `Watch folders: ${watch.enabled ? "enabled" : "off"}`,
      `Roots: ${rootsLabel}`,
      `Debounce: ${watch.debounce}s`,
      `Schedule gate: ${watch.respectSchedule ? "respected" : "ignored"}`,
      "Backend authority: detection stays in the local API watch-folder manager and launches use the existing gated Run Once path.",
    ];
  }

  function libraryWatchHasActiveControl() {
    const active = document.activeElement;
    const panel = byId("settings-library-watch-panel");
    return Boolean(active instanceof Element && panel?.contains(active));
  }

  function syncLibraryWatchControlsFromConfig(settings = lastSettings, options = {}) {
    if (settings) lastSettings = settings;
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
      pending.EnableWatchFolders
        ? "Roots: Library Profile source roots"
        : "Roots: existing saved roots are preserved while watch folders are disabled.",
      `Action: ${pending.WatchAction === "enqueue_and_launch" ? "gated Run Once" : "enqueue only"}`,
      `Schedule gate: ${pending.WatchRespectScheduleWindow ? "respected" : "ignored"}`,
      "Runtime boundary: this control only stages settings; it does not scan, launch, queue, publish, rename, move, or delete media files.",
    ];
    setText("settings-library-watch-summary", lines.join("\n"));
  }

  function stageLibraryWatchAutoRunPatch() {
    const patch = collectLibraryWatchAutoRunPatch();
    if (typeof window.writeSettingsPatchJson !== "function") {
      setText("settings-library-watch-status", "Settings unavailable");
      renderLibraryWatchPatchHandoff("Settings patch controls are not loaded.", patch);
      return null;
    }
    window.writeSettingsPatchJson(
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

  function choiceLabel(key) {
    const field = fieldDefinition(key);
    if (field?.label) return field.label;
    return choiceLabels[key] || key.replace(/_/g, " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
  }

  function fieldHelpText(field) {
    return String(field?.help_text || field?.help || "").trim();
  }

  function metadataTags(value) {
    if (Array.isArray(value)) return value.map((item) => String(item || "").trim()).filter(Boolean);
    const textValue = String(value || "").trim();
    return textValue ? [textValue] : [];
  }

  function fieldIsAdvanced(key, field) {
    const advancedVisibility = String(field?.advanced_visibility || "").trim().toLowerCase();
    const section = String(field?.section || "").trim().toLowerCase();
    const tags = [
      ...metadataTags(field?.rule_taxonomy),
      ...metadataTags(field?.strictness),
    ].map((value) => String(value || "").trim().toLowerCase());
    return advancedVisibility === "advanced"
      || section === "advanced"
      || tags.includes("advanced")
      || advancedFallbackKeys.has(String(key || field?.key || ""));
  }

  function choiceValueLabel(value) {
    const key = String(value ?? "");
    return choiceLabels[key] || key.replace(/_/g, " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
  }

  function inputTypeForField(field) {
    if (["integer", "number"].includes(field?.value_type)) return "number";
    if (field?.kind === "optional_float") return "number";
    if (["int", "optional_int", "combo_int"].includes(field?.kind)) return "number";
    return "text";
  }

  function fieldOwnValue(field, key) {
    if (!field || !Object.prototype.hasOwnProperty.call(field, key)) return undefined;
    const value = field[key];
    return value === null || value === undefined || value === "" ? undefined : value;
  }

  function buildOverrideControl(key, value, disabled = false) {
    const field = fieldDefinition(key);
    const kind = field?.kind || "";
    const disabledAttr = disabled ? " disabled" : "";
    if (kind === "bool") {
      return `<input type="checkbox"${disabledAttr} data-library-override-control data-library-override-key="${escapeHtml(key)}" ${boolValue(value) ? "checked" : ""}>`;
    }
    const allowedValues = Array.isArray(field?.allowed_values) && field.allowed_values.length ? field.allowed_values : field?.choices;
    if (Array.isArray(allowedValues) && allowedValues.length) {
      const choices = allowedValues.map((choice) => String(choice));
      const valueText = String(value ?? "");
      const hasCurrent = choices.includes(valueText);
      const options = allowedValues.map((choice) => {
        const optionValue = String(choice);
        const title = field.choice_help && field.choice_help[optionValue] ? ` title="${escapeHtml(field.choice_help[optionValue])}"` : "";
        return `<option value="${escapeHtml(optionValue)}"${optionValue === valueText ? " selected" : ""}${title}>${escapeHtml(choiceValueLabel(optionValue))}</option>`;
      });
      if (valueText && !hasCurrent) {
        options.unshift(`<option value="${escapeHtml(valueText)}" selected>${escapeHtml(valueText)}</option>`);
      }
      return `<select${disabledAttr} data-library-override-control data-library-override-key="${escapeHtml(key)}">${options.join("")}</select>`;
    }
    const inputType = inputTypeForField(field);
    const minValue = inputType === "number" ? fieldOwnValue(field, "min") : undefined;
    const maxValue = inputType === "number" ? fieldOwnValue(field, "max") : undefined;
    const stepValue = inputType === "number" ? (fieldOwnValue(field, "step") ?? (field?.kind === "optional_float" ? "any" : "")) : "";
    const unitValue = fieldOwnValue(field, "unit") ?? fieldOwnValue(field, "display_unit");
    const min = minValue !== undefined ? ` min="${escapeHtml(minValue)}"` : "";
    const max = maxValue !== undefined ? ` max="${escapeHtml(maxValue)}"` : "";
    const step = stepValue ? ` step="${escapeHtml(stepValue)}"` : "";
    const unit = unitValue !== undefined ? ` data-settings-unit="${escapeHtml(unitValue)}"` : "";
    const textAttrs = inputType === "text" ? ' autocomplete="off" spellcheck="false"' : "";
    return `<input type="${inputType}"${min}${max}${step}${unit}${textAttrs}${disabledAttr} data-library-override-control data-library-override-key="${escapeHtml(key)}" value="${escapeHtml(formatValue(value))}">`;
  }

  function effectiveOverrideValue(profile, groupKey, fieldKey) {
    const groupOverrides = profile.overrides?.[groupKey] || {};
    if (Object.prototype.hasOwnProperty.call(groupOverrides, fieldKey)) {
      return groupOverrides[fieldKey];
    }
    return defaultSettingValue(fieldKey);
  }

  function settingOverrideEvidence(profile, groupKey, fieldKey) {
    const evidence = profileState(profile)?.setting_overrides?.[groupKey]?.[fieldKey];
    return evidence && typeof evidence === "object" && !Array.isArray(evidence) ? evidence : null;
  }

  function overrideValuesEqual(left, right) {
    return JSON.stringify(stableComparable(left)) === JSON.stringify(stableComparable(right));
  }

  function overrideStateText(isOverride, value, inheritedValue) {
    if (!isOverride) return "Inherited from global";
    if (overrideValuesEqual(value, inheritedValue)) return "Library override — currently same as global";
    return "Library override";
  }

  function renderUseDefaultButton(groupKey, fieldKey, isOverride) {
    return `<button type="button" class="tertiary-button settings-library-override-use-default" data-library-use-default-override data-library-override-group="${escapeHtml(groupKey)}" data-library-override-key="${escapeHtml(fieldKey)}" title="Reset to inherited removes the persisted library override key; it does not write the global value into this library."${isOverride ? "" : " hidden disabled"}>Reset to inherited</button>`;
  }

  function routeNumberValue(value, fallback = 0) {
    if (typeof routeModel.numberValue === "function") return routeModel.numberValue(value, fallback);
    const number = Number(value);
    return Number.isFinite(number) ? number : fallback;
  }

  function routeFormatPercent(value) {
    if (typeof routeModel.formatPercent === "function") return routeModel.formatPercent(value);
    const number = Number(value);
    if (!Number.isFinite(number)) return "";
    return number.toFixed(6).replace(/\.?0+$/, "");
  }

  function routeFormatHeight(value) {
    if (typeof routeModel.formatHeight === "function") return routeModel.formatHeight(value);
    const number = Number(value);
    return Number.isFinite(number) ? String(Math.round(number)) : "";
  }

  function routeSafeIdPart(value) {
    return String(value || "library").replace(/[^A-Za-z0-9_-]+/g, "-").replace(/^-+|-+$/g, "") || "library";
  }

  function routeElementId(profile, suffix) {
    return `settings-library-route-${routeSafeIdPart(profile?.id)}-${suffix}`;
  }

  function routeValueAvailable(value) {
    return value !== undefined && value !== null && String(value).trim() !== "";
  }

  function routeValueFromBackendSource(values, key) {
    if (values && Object.prototype.hasOwnProperty.call(values, key) && routeValueAvailable(values[key])) {
      return values[key];
    }
    return defaultSettingValue(key);
  }

  function routeMetadataMissingKeys(values) {
    return routeSizeFields.filter((key) => {
      const field = fieldDefinition(key);
      const hasMetadata = Boolean(field && Object.keys(field).length);
      return !hasMetadata || !routeValueAvailable(routeValueFromBackendSource(values, key));
    });
  }

  function routeSourceSummary(values) {
    const missing = routeMetadataMissingKeys(values);
    if (missing.length) {
      const visibleKeys = missing.slice(0, 5).join(", ");
      const suffix = missing.length > 5 ? `, and ${missing.length - 5} more` : "";
      return `Advisory only: backend route metadata/current values are missing for ${visibleKeys}${suffix}. Preview or save with the backend before treating these readouts as evidence.`;
    }
    return "Readouts use backend field metadata and current config values. Library controls stage overrides only; backend Save remains authoritative.";
  }

  function routeValuesFromObject(values) {
    return routeSizeFields.reduce((accumulator, key) => {
      accumulator[key] = routeValueFromBackendSource(values, key);
      return accumulator;
    }, {});
  }

  function routeBoundariesFromValues(values) {
    if (typeof routeModel.boundariesFromValues === "function") return routeModel.boundariesFromValues(values);
    const withDefaults = routeValuesFromObject(values);
    return {
      route1080pMaxHeight: Math.round(1080 * (1 + (routeNumberValue(withDefaults.Route1080pUpperHeightTolerancePercent, 0) / 100))),
      route1440pMinHeight: Math.round(1440 * (1 - (routeNumberValue(withDefaults.Route1440pLowerHeightTolerancePercent, 0) / 100))),
      route1440pMaxHeight: Math.round(1440 * (1 + (routeNumberValue(withDefaults.Route1440pUpperHeightTolerancePercent, 0) / 100))),
      route4kMinHeight: Math.round(2160 * (1 - (routeNumberValue(withDefaults.Route4KLowerHeightTolerancePercent, 0) / 100))),
    };
  }

  function routeRailPercentages(boundaries) {
    if (typeof routeModel.railPercentages === "function") return routeModel.railPercentages(boundaries);
    const minHeight = 1080;
    const maxHeight = 2160;
    const span = maxHeight - minHeight;
    const clamp = (value) => Math.min(100, Math.max(0, Number(value)));
    return {
      firstPct: clamp(((routeNumberValue(boundaries?.route1080pMaxHeight, minHeight) - minHeight) / span) * 100),
      secondPct: clamp(((routeNumberValue(boundaries?.route4kMinHeight, maxHeight) - minHeight) / span) * 100),
    };
  }

  function routeValuesFromProfile(profile) {
    return routeSizeFields.reduce((accumulator, key) => {
      accumulator[key] = effectiveLibraryOverrideValue(profile, "editor", key);
      return accumulator;
    }, {});
  }

  function routeValuesFromCard(card) {
    return routeSizeFields.reduce((accumulator, key) => {
      const control = card.querySelector(`[data-library-override-key="${key}"] [data-library-override-control]`);
      accumulator[key] = control ? readOverrideControlValue(control, key) : defaultSettingValue(key);
      return accumulator;
    }, {});
  }

  function effectiveLibraryOverrideValue(profile, groupKey, fieldKey) {
    const groupOverrides = profile.overrides?.[groupKey] || {};
    const evidence = settingOverrideEvidence(profile, groupKey, fieldKey);
    if (Object.prototype.hasOwnProperty.call(groupOverrides, fieldKey)) return groupOverrides[fieldKey];
    if (evidence && Object.prototype.hasOwnProperty.call(evidence, "effective_value")) return evidence.effective_value;
    return defaultSettingValue(fieldKey);
  }

  function routeTriggerSummary(mode) {
    if (typeof routeModel.triggerSummary === "function") return routeModel.triggerSummary(mode);
    return "Routing trigger behavior follows the selected backend mode.";
  }

  function routeHeightPixelSummary(boundaries) {
    if (typeof routeModel.heightPixelSummary === "function") return routeModel.heightPixelSummary(boundaries);
    return `Derived direct-copy buckets: 1080p <=${routeFormatHeight(boundaries.route1080pMaxHeight)}p, 1440p ${routeFormatHeight(boundaries.route1440pMinHeight)}-${routeFormatHeight(boundaries.route1440pMaxHeight)}p, 4K >=${routeFormatHeight(boundaries.route4kMinHeight)}p. Boundary values route to the higher bucket.`;
  }

  function routeConsequenceSummary(boundaries, values) {
    if (typeof routeModel.consequenceSummary === "function") return routeModel.consequenceSummary(boundaries, values);
    const withDefaults = routeValuesFromObject(values);
    return `A ${routeFormatHeight(boundaries.route1440pMinHeight)}p source routes as 1440p: Movie ${withDefaults.MovieRoute1440pTargetSizeGB} GB / TV ${withDefaults.TVRoute1440pTargetSizeGB} GB, direct-copy cap ${withDefaults.Route1440pMaxVideoBitrateMbps} Mbps. A ${routeFormatHeight(boundaries.route4kMinHeight)}p source routes as 4K.`;
  }

  function routeUnknownHeightSummary(values) {
    if (typeof routeModel.unknownHeightSummary === "function") return routeModel.unknownHeightSummary(values);
    return "Unknown-height routing remains backend-owned until ffprobe dimensions or backend fallback evidence is available.";
  }

  function routeEstimatedGb(value, minutes) {
    if (typeof routeModel.estimatedSizeGb === "function") return routeModel.estimatedSizeGb(value, minutes);
    const mbps = routeNumberValue(value, 0);
    return mbps > 0 ? (mbps * routeNumberValue(minutes, 0) * 60) / 8 / 1024 : 0;
  }

  function routeFormatEstimatedGb(value) {
    if (typeof routeModel.formatEstimatedGb === "function") return routeModel.formatEstimatedGb(value);
    const number = Number(value);
    if (!Number.isFinite(number) || number <= 0) return "0 GB";
    return number < 10 ? `${number.toFixed(1).replace(/\.0$/, "")} GB` : `${Math.round(number)} GB`;
  }

  function renderLibraryRouteOverrideField(profile, groupKey, fieldKey, options = {}) {
    const status = overrideStatus(groupKey, fieldKey, profile);
    if (!status.render) return "";
    const field = status.field;
    const editable = status.editable;
    const groupOverrides = profile.overrides?.[groupKey] || {};
    const evidence = settingOverrideEvidence(profile, groupKey, fieldKey);
    const hasLocalOverride = Object.prototype.hasOwnProperty.call(groupOverrides, fieldKey);
    const isOverride = editable && (hasLocalOverride || evidence?.state === "explicit");
    const value = effectiveLibraryOverrideValue(profile, groupKey, fieldKey);
    const inheritedValue = evidence && Object.prototype.hasOwnProperty.call(evidence, "inherited_value")
      ? evidence.inherited_value
      : defaultSettingValue(fieldKey);
    const label = escapeHtml(options.label || choiceLabel(fieldKey));
    const unavailableReason = editable ? "" : status.reason || "not available for library overrides";
    const stateText = editable ? overrideStateText(isOverride, value, inheritedValue) : unavailableReason;
    const stateClass = editable ? (isOverride ? "is-custom" : "is-inherited") : "is-readonly";
    const state = `<span class="settings-library-state ${stateClass}" data-library-override-state-label>${escapeHtml(stateText)}</span>`;
    const titleText = [fieldHelpText(field), unavailableReason ? `Unavailable: ${unavailableReason}` : ""].filter(Boolean).join(" ");
    const title = titleText ? ` title="${escapeHtml(titleText)}"` : "";
    const advancedVisibility = field?.advanced_visibility || "standard";
    const persistedKey = String(field?.persisted_key || fieldKey);
    const section = String(field?.section || "");
    const scope = String(field?.scope || "");
    const baseClass = [
      "settings-library-override-row",
      "settings-library-route-override-row",
      options.hidden ? "settings-library-route-hidden-row" : "",
      options.inline ? "settings-library-route-inline-row" : "",
      fieldIsAdvanced(fieldKey, field) ? "is-advanced-field" : "",
      editable ? "" : "is-unavailable",
      isOverride ? "is-custom" : "is-inherited",
    ].filter(Boolean).join(" ");
    const advancedAttr = fieldIsAdvanced(fieldKey, field) ? " data-advanced" : "";
    const routeAttr = options.routeRole ? ` data-library-route-role="${escapeHtml(options.routeRole)}"` : "";
    const rowAttrs = `class="${baseClass}" data-library-override-row data-library-override-group="${escapeHtml(groupKey)}" data-library-override-key="${escapeHtml(fieldKey)}" data-library-persisted-key="${escapeHtml(persistedKey)}" data-library-override="${isOverride ? "true" : "false"}" data-library-override-eligible="${editable ? "true" : "false"}" data-library-section="${escapeHtml(section)}" data-library-scope="${escapeHtml(scope)}" data-library-advanced-visibility="${escapeHtml(advancedVisibility)}" data-library-unavailable-reason="${escapeHtml(unavailableReason)}"${routeAttr}${advancedAttr}${title}`;
    const control = buildOverrideControl(fieldKey, value, !editable);
    const controlMarkup = options.unit
      ? `<span class="settings-input-with-unit">${control}<span>${escapeHtml(options.unit)}</span></span>`
      : control;
    const button = editable ? renderUseDefaultButton(groupKey, fieldKey, isOverride) : "";
    const unavailable = unavailableReason ? `<span class="note settings-library-override-unavailable">${escapeHtml(unavailableReason)}</span>` : "";
    return `
      <label ${rowAttrs}>
        <span class="settings-library-override-field-heading">
          <span class="settings-library-override-label-text">${label}</span>
          ${state}
          ${button}
        </span>
        ${controlMarkup}
        ${unavailable}
      </label>
    `;
  }

  function renderLibraryRouteRail(boundaries) {
    const firstBoundary = routeFormatHeight(boundaries.route1080pMaxHeight);
    const secondBoundary = routeFormatHeight(boundaries.route4kMinHeight);
    const percentages = routeRailPercentages(boundaries);
    return `
      <div class="settings-route-range-rail settings-library-route-rail" data-library-route-rail style="--route-first-pct: ${routeFormatPercent(percentages.firstPct)}%; --route-second-pct: ${routeFormatPercent(percentages.secondPct)}%;">
        <div class="settings-route-slider-labels">
          <div class="settings-route-slider-bucket"><span>1080p</span><output data-library-route-readout="range-1080p">uses &lt;=${firstBoundary}p</output></div>
          <div class="settings-route-slider-bucket"><span>1440p</span><output data-library-route-readout="range-1440p">uses ${routeFormatHeight(boundaries.route1440pMinHeight)}-${routeFormatHeight(boundaries.route1440pMaxHeight)}p</output></div>
          <div class="settings-route-slider-bucket"><span>4K</span><output data-library-route-readout="range-4k">uses &gt;=${secondBoundary}p</output></div>
        </div>
        <div class="settings-route-slider settings-library-route-visual" data-library-route-visual aria-hidden="true">
          <div class="settings-route-slider-track">
            <span class="settings-route-slider-fill settings-route-slider-fill-1080p"></span>
            <span class="settings-route-slider-fill settings-route-slider-fill-1440p"></span>
            <span class="settings-route-slider-fill settings-route-slider-fill-4k"></span>
          </div>
          <span class="settings-library-route-marker settings-library-route-marker-first"></span>
          <span class="settings-library-route-marker settings-library-route-marker-second"></span>
        </div>
      </div>
    `;
  }

  function renderLibraryRouteBoundaryControls(boundaries, describedBy) {
    const firstBoundary = routeFormatHeight(boundaries.route1080pMaxHeight);
    const secondBoundary = routeFormatHeight(boundaries.route4kMinHeight);
    const describedByAttr = describedBy ? ` aria-describedby="${escapeHtml(describedBy)}"` : "";
    return `
      <div class="settings-library-route-boundary-grid" data-library-route-boundary-controls>
        <label class="settings-library-route-boundary-field">
          <span>1080p maximum height</span>
          <span class="settings-route-range-control">
            <input type="number" min="1080" max="1439" step="1" value="${firstBoundary}" data-library-route-boundary-input="first" aria-label="1080p maximum height"${describedByAttr}>
            <span>p</span>
          </span>
        </label>
        <label class="settings-library-route-boundary-field">
          <span>4K minimum height</span>
          <span class="settings-route-range-control">
            <input type="number" min="1441" max="2160" step="1" value="${secondBoundary}" data-library-route-boundary-input="second" aria-label="4K minimum height"${describedByAttr}>
            <span>p</span>
          </span>
        </label>
      </div>
      <div class="settings-library-route-boundary-actions">
        <button type="button" class="tertiary-button" data-library-route-boundary-reset="first">Reset 1080p/1440p boundary</button>
        <button type="button" class="tertiary-button" data-library-route-boundary-reset="second">Reset 1440p/4K boundary</button>
      </div>
    `;
  }

  function renderLibraryRouteBucket(profile, bucket, boundaries) {
    const movieTarget = renderLibraryRouteOverrideField(profile, "editor", bucket.movieTargetKey, {
      label: `Movie ${bucket.targetLabel} target output size`,
      routeRole: "target-size",
      unit: "GB",
    });
    const tvTarget = renderLibraryRouteOverrideField(profile, "editor", bucket.tvTargetKey, {
      label: `TV ${bucket.targetLabel} target output size`,
      routeRole: "target-size",
      unit: "GB",
    });
    const bitrate = renderLibraryRouteOverrideField(profile, "editor", bucket.bitrateKey, {
      label: `${bucket.label} max bitrate for direct copy`,
      routeRole: "direct-copy-bitrate",
      unit: "Mbps",
    });
    const targetRows = [movieTarget, tvTarget].filter(Boolean).join("");
    const values = routeValuesFromProfile(profile);
    const bitrateValue = routeNumberValue(values[bucket.bitrateKey], 0);
    const tvEstimate = routeFormatEstimatedGb(routeEstimatedGb(bitrateValue, bucket.estimateMinutes.tv));
    const movieEstimate = routeFormatEstimatedGb(routeEstimatedGb(bitrateValue, bucket.estimateMinutes.movie));
    const rangeText = bucket.key === "1080p"
      ? `uses <=${routeFormatHeight(boundaries.route1080pMaxHeight)}p`
      : bucket.key === "1440p"
        ? `uses ${routeFormatHeight(boundaries.route1440pMinHeight)}-${routeFormatHeight(boundaries.route1440pMaxHeight)}p`
        : `uses >=${routeFormatHeight(boundaries.route4kMinHeight)}p`;
    return `
      <section class="settings-route-bucket-card settings-library-route-bucket" data-library-route-bucket="${escapeHtml(bucket.key)}">
        <div class="settings-route-bucket-header">
          <div>
            <h4>${escapeHtml(bucket.label)}</h4>
            <p>Derived height range</p>
          </div>
          <span class="settings-route-range-ref" data-library-route-readout="bucket-${escapeHtml(bucket.key)}">${escapeHtml(rangeText)}</span>
        </div>
        <div class="settings-route-bucket-grid">
          ${targetRows ? `<div class="settings-route-bucket-group"><h5>Encoded output size (GB)</h5><div class="settings-route-target-stack">${targetRows}</div></div>` : ""}
          <div class="settings-route-bucket-group">
            <h5>Direct-copy limits</h5>
            <div class="settings-route-target-stack">${bitrate}</div>
            <p class="note" data-library-route-readout="estimate-${escapeHtml(bucket.key)}">If constant: 30m TV ~${escapeHtml(tvEstimate)}; 2h movie ~${escapeHtml(movieEstimate)}</p>
          </div>
        </div>
      </section>
    `;
  }

  function renderLibraryRouteSizeLayout(profile, groupKey, block) {
    const fields = new Set(block.fields || []);
    const values = routeValuesFromProfile(profile);
    const boundaries = routeBoundariesFromValues(values);
    const routeConsequenceId = routeElementId(profile, "bucket-consequences");
    const routeUnknownId = routeElementId(profile, "unknown-height");
    const routeSourceId = routeElementId(profile, "metadata-source");
    const routeBoundaryDescriptions = `${routeConsequenceId} ${routeUnknownId} ${routeSourceId}`;
    const hiddenToleranceRows = routeToleranceKeys
      .filter((key) => fields.has(key))
      .map((key) => renderLibraryRouteOverrideField(profile, groupKey, key, { hidden: true, routeRole: "height-tolerance" }))
      .join("");
    return `
      <div class="settings-library-route-editor" data-library-route-editor>
        <section class="settings-library-route-section">
          <h3>Library Goal</h3>
          ${renderLibraryRouteOverrideField(profile, groupKey, "RoutingProfile", { routeRole: "routing-profile" })}
        </section>
        <section class="settings-library-route-section">
          <h3>What Forces An Encode?</h3>
          ${renderLibraryRouteOverrideField(profile, groupKey, "RouteThresholdMode", { routeRole: "route-threshold" })}
          <p class="note settings-library-route-summary" data-library-route-summary="trigger">${escapeHtml(routeTriggerSummary(values.RouteThresholdMode))}</p>
        </section>
        <section class="settings-library-route-section">
          <h3>TV / Movie Targets By Height</h3>
          <p class="note">Target GB is the encoded output budget. Mbps is the source direct-copy/remux cap. Height chooses the bucket.</p>
          <p id="${escapeHtml(routeSourceId)}" class="note settings-library-route-summary" data-library-route-source-summary>${escapeHtml(routeSourceSummary(values))}</p>
          ${renderLibraryRouteRail(boundaries)}
          ${renderLibraryRouteBoundaryControls(boundaries, routeBoundaryDescriptions)}
          <div class="settings-route-target-editor settings-library-route-target-editor">
            ${routeBucketDefinitions.map((bucket) => renderLibraryRouteBucket(profile, bucket, boundaries)).join("")}
          </div>
          <p class="note settings-library-route-summary" data-library-route-summary="pixel">${escapeHtml(routeHeightPixelSummary(boundaries))}</p>
          <p id="${escapeHtml(routeConsequenceId)}" class="note settings-library-route-summary" data-library-route-summary="consequence">${escapeHtml(routeConsequenceSummary(boundaries, values))}</p>
          <p id="${escapeHtml(routeUnknownId)}" class="note settings-library-route-summary" data-library-route-summary="unknown">${escapeHtml(routeUnknownHeightSummary(values))}</p>
        </section>
        <section class="settings-library-route-section">
          <h3>If Encoded Output Is Too Large</h3>
          <div class="form-grid launch-form-grid settings-library-route-guard-grid">
            ${renderLibraryRouteOverrideField(profile, groupKey, "SizeGuardMode", { routeRole: "size-guard" })}
            ${renderLibraryRouteOverrideField(profile, groupKey, "MaxEncodeGrowthPercent", { routeRole: "size-guard", unit: "%" })}
            ${renderLibraryRouteOverrideField(profile, groupKey, "CompatibilityEncodeGrowthPercent", { routeRole: "size-guard", unit: "%" })}
          </div>
        </section>
        <div class="settings-library-route-hidden-fields" hidden>
          ${hiddenToleranceRows}
        </div>
      </div>
    `;
  }

  function renderOverrideField(profile, groupKey, fieldKey, variant = "grid") {
    const status = overrideStatus(groupKey, fieldKey, profile);
    if (!status.render) return "";
    const field = status.field;
    const editable = status.editable;
    const groupOverrides = profile.overrides?.[groupKey] || {};
    const evidence = settingOverrideEvidence(profile, groupKey, fieldKey);
    const hasLocalOverride = Object.prototype.hasOwnProperty.call(groupOverrides, fieldKey);
    const isOverride = editable && (hasLocalOverride || evidence?.state === "explicit");
    const value = hasLocalOverride
      ? groupOverrides[fieldKey]
      : evidence && Object.prototype.hasOwnProperty.call(evidence, "effective_value")
        ? evidence.effective_value
        : effectiveOverrideValue(profile, groupKey, fieldKey);
    const inheritedValue = evidence && Object.prototype.hasOwnProperty.call(evidence, "inherited_value")
      ? evidence.inherited_value
      : defaultSettingValue(fieldKey);
    const label = escapeHtml(choiceLabel(fieldKey));
    const unavailableReason = editable ? "" : status.reason || "not available for library overrides";
    const stateText = editable ? overrideStateText(isOverride, value, inheritedValue) : unavailableReason;
    const stateClass = editable ? (isOverride ? "is-custom" : "is-inherited") : "is-readonly";
    const state = `<span class="settings-library-state ${stateClass}" data-library-override-state-label>${escapeHtml(stateText)}</span>`;
    const titleText = [fieldHelpText(field), unavailableReason ? `Unavailable: ${unavailableReason}` : ""].filter(Boolean).join(" ");
    const title = titleText ? ` title="${escapeHtml(titleText)}"` : "";
    const advancedVisibility = field?.advanced_visibility || "standard";
    const persistedKey = String(field?.persisted_key || fieldKey);
    const section = String(field?.section || "");
    const scope = String(field?.scope || "");
    const baseClass = [
      variant === "check" ? "check-row" : "",
      variant === "check-grid" ? "check-row launch-check-row" : "",
      variant === "full" ? "full-field" : "",
      "settings-library-override-row",
      fieldIsAdvanced(fieldKey, field) ? "is-advanced-field" : "",
      editable ? "" : "is-unavailable",
      isOverride ? "is-custom" : "is-inherited",
    ].filter(Boolean).join(" ");
    const advancedAttr = fieldIsAdvanced(fieldKey, field) ? " data-advanced" : "";
    const rowAttrs = `class="${baseClass}" data-library-override-row data-library-override-group="${escapeHtml(groupKey)}" data-library-override-key="${escapeHtml(fieldKey)}" data-library-persisted-key="${escapeHtml(persistedKey)}" data-library-override="${isOverride ? "true" : "false"}" data-library-override-eligible="${editable ? "true" : "false"}" data-library-section="${escapeHtml(section)}" data-library-scope="${escapeHtml(scope)}" data-library-advanced-visibility="${escapeHtml(advancedVisibility)}" data-library-unavailable-reason="${escapeHtml(unavailableReason)}"${advancedAttr}${title}`;
    const control = buildOverrideControl(fieldKey, value, !editable);
    const button = editable ? renderUseDefaultButton(groupKey, fieldKey, isOverride) : "";
    const unavailable = unavailableReason ? `<span class="note settings-library-override-unavailable">${escapeHtml(unavailableReason)}</span>` : "";
    if (field?.kind === "bool") {
      return `
        <label ${rowAttrs}>
          ${control}
          <span class="settings-library-override-label-text">${label}</span>
          ${state}
          ${button}
          ${unavailable}
        </label>
      `;
    }
    return `
      <label ${rowAttrs}>
        <span class="settings-library-override-field-heading">
          <span class="settings-library-override-label-text">${label}</span>
          ${state}
          ${button}
        </span>
        ${control}
        ${unavailable}
      </label>
    `;
  }

  function fieldsForGroup(profile, groupKey, fields) {
    return fields.filter((fieldKey) => overrideStatus(groupKey, fieldKey, profile).render);
  }

  function renderFieldGrid(profile, groupKey, fields) {
    const rows = fieldsForGroup(profile, groupKey, fields).map((fieldKey) => {
      const field = fieldDefinition(fieldKey);
      return renderOverrideField(profile, groupKey, fieldKey, field?.kind === "bool" ? "check-grid" : "grid");
    });
    if (!rows.length) return "";
    return `<div class="form-grid launch-form-grid">${rows.join("")}</div>`;
  }

  function renderOptionGrid(profile, groupKey, fields) {
    const rows = fieldsForGroup(profile, groupKey, fields).map((fieldKey) => renderOverrideField(profile, groupKey, fieldKey, "check"));
    if (!rows.length) return "";
    return `<div class="option-grid option-grid-compact">${rows.join("")}</div>`;
  }

  function renderFullFields(profile, groupKey, fields) {
    return fieldsForGroup(profile, groupKey, fields).map((fieldKey) => renderOverrideField(profile, groupKey, fieldKey, "full")).join("");
  }

  function renderNestedOptionPanel(profile, groupKey, block) {
    const optionGrid = renderOptionGrid(profile, groupKey, block.fields || []);
    const formGrid = renderFieldGrid(profile, groupKey, block.gridFields || []);
    if (!optionGrid && !formGrid) return "";
    return `
      <section class="option-panel">
        <div class="option-panel-heading">
          <strong>${escapeHtml(block.title || "")}</strong>
          <span>${escapeHtml(block.note || "")}</span>
        </div>
        ${optionGrid}
        ${formGrid}
      </section>
    `;
  }

  function renderOverrideLayout(profile, groupKey) {
    const blocks = overrideLayouts[groupKey] || [{ type: "grid", fields: overrideFieldsForGroup(groupKey) }];
    return blocks.map((block) => {
      if (block.type === "routeSize") return renderLibraryRouteSizeLayout(profile, groupKey, block);
      if (block.type === "grid") return renderFieldGrid(profile, groupKey, block.fields || []);
      if (block.type === "options") return renderOptionGrid(profile, groupKey, block.fields || []);
      if (block.type === "full") return renderFullFields(profile, groupKey, block.fields || []);
      if (block.type === "panel") return renderNestedOptionPanel(profile, groupKey, block);
      if (block.type === "compatibility") return renderCompatibilityPresetEditorControl(profile);
      if (block.type === "note") return `<p class="note settings-library-panel-note">${escapeHtml(block.text || "")}</p>`;
      return "";
    }).join("");
  }

  function renderOverrideSection(profile, group) {
    const openSections = openOverrideSectionsByLibrary.get(profile.id);
    const isOpen = openSections instanceof Set && openSections.has(group.key);
    return `
      <details class="settings-library-override-section" data-library-override-section="${escapeHtml(group.key)}"${isOpen ? " open" : ""}>
        <summary class="settings-library-override-summary">
          <span>${escapeHtml(group.title)}</span>
        </summary>
        <div class="settings-library-override-body">
          ${renderOverrideLayout(profile, group.key)}
        </div>
      </details>
    `;
  }

  function profileMp4CompatibilityActive(profile) {
    const overrides = normalizeOverrides(profile || {});
    return String(overrides.editor?.OutputContainer || "").trim().toLowerCase() === "mp4";
  }

  function renderCompatibilityPresetEditorControl(profile) {
    const preset = mp4CompatibilityPreset();
    if (!preset) return "";
    const active = profileMp4CompatibilityActive(profile);
    return `
      <label class="settings-library-compatibility-field" data-library-compatibility-preset="${escapeHtml(preset.id)}" data-library-compatibility-active="${active ? "true" : "false"}">
        <span>Compatibility mode</span>
        <select data-library-compatibility-select>
          <option value=""${active ? "" : " selected"}>Standard library overrides</option>
          <option value="${escapeHtml(preset.id)}"${active ? " selected" : ""}>${escapeHtml(preset.label || "MP4 Compatibility")}</option>
        </select>
        <span class="note" data-library-compatibility-note>${escapeHtml(active ? (preset.warning || preset.summary || "") : "Optional lossy MP4 reset preset.")}</span>
      </label>
    `;
  }

  function captureOpenOverrideSections() {
    const list = byId("settings-library-profile-list");
    if (!list) return;
    list.querySelectorAll(".settings-library-card").forEach((card) => {
      const profileId = card.dataset.libraryId || "";
      if (!profileId) return;
      const openSections = new Set();
      card.querySelectorAll("details[data-library-override-section]").forEach((section) => {
        if (section.open) {
          const sectionKey = section.getAttribute("data-library-override-section") || "";
          if (sectionKey) openSections.add(sectionKey);
        }
      });
      openOverrideSectionsByLibrary.set(profileId, openSections);
    });
  }

  function renderCard(profile) {
    const nonDeletable = profile.id === "movies" || profile.id === "tv";
    const inherited = inheritedSet(profile);
    const card = document.createElement("article");
    card.className = "settings-library-card";
    card.dataset.libraryId = profile.id;
    card.dataset.localInheritedFields = JSON.stringify(Array.from(inherited));
    card.dataset.libraryPrunedOverrides = JSON.stringify(inapplicableOverrideKeys(profile));
    card.innerHTML = `
      <div class="settings-library-card-heading">
        <div>
          <h3>${escapeHtml(profile.name)}</h3>
          <p class="note">${escapeHtml(profile.id)} / ${escapeHtml(profile.designation)}</p>
        </div>
        <div class="settings-library-card-actions">
          <label class="settings-library-enabled"><input type="checkbox" data-library-field="enabled" ${profile.enabled ? "checked" : ""} ${nonDeletable ? "disabled" : ""}> Enabled</label>
        </div>
      </div>
      <div class="form-grid form-grid-dense settings-library-main-grid">
        <label>Name
          <input type="text" data-library-field="name" value="${escapeHtml(profile.name)}" ${nonDeletable ? "readonly" : ""}>
        </label>
        <label>Designation
          <select data-library-field="designation">
            ${designationValues.map((designation) => `<option value="${designation}" ${profile.designation === designation ? "selected" : ""}>${escapeHtml(choiceValueLabel(designation))}</option>`).join("")}
          </select>
        </label>
      </div>
      <div class="settings-library-path-grid"></div>
      <div class="settings-library-overrides">
        ${overrideGroupList().map((group) => renderOverrideSection(profile, group)).join("")}
      </div>
    `;
    const pathGrid = card.querySelector(".settings-library-path-grid");
    [
      ["source_path", "Source", profile.source_path],
      ["output_path", "Output destination", profile.output_path],
      ["promotion_destination", "Promotion destination", profile.promotion_destination],
    ].forEach(([field, label, value]) => {
      const row = document.createElement("label");
      const evidence = pathEvidence(profile, field);
      const state = pathState(profile, field);
      const sourceText = pathSourceText(evidence);
      const canReset = pathCanReset(profile, field, evidence);
      const isInherited = pathIsInherited(evidence);
      row.className = "settings-library-path-row";
      row.dataset.libraryPathStateKind = String(evidence?.state || "");
      row.dataset.libraryPathSourceKey = text(evidence?.source_key);
      row.innerHTML = `
        <span>${escapeHtml(label)} <span class="settings-library-state ${pathStateClass(state)}" data-library-path-state="${field}">${escapeHtml(state)}</span><span class="note settings-library-path-source" data-library-path-source="${field}">${escapeHtml(sourceText)}</span></span>
        <div class="settings-library-path-control">
          <input type="text" data-library-field="${field}" data-inherited="${isInherited ? "true" : "false"}" value="${escapeHtml(value || "")}">
          <button type="button" class="tertiary-button" data-library-use-default="${field}" data-library-can-reset="${canReset ? "true" : "false"}" title="${canReset ? "Reset to inherited removes explicit path state; it does not write the global path into this library." : "This field does not support inherited reset."}"${canReset && !isInherited ? "" : " hidden disabled"}>Use global default</button>
        </div>
      `;
      pathGrid.appendChild(row);
    });
    const promotionRow = document.createElement("label");
    promotionRow.className = "settings-library-promotion-toggle";
    promotionRow.innerHTML = `<input type="checkbox" data-library-field="promotion_enabled" ${profile.promotion_enabled ? "checked" : ""}> Enable promotion for this library`;
    pathGrid.appendChild(promotionRow);
    syncLibraryRouteReadouts(card);
    syncLibraryCompatibilityAvailability(card);
    return card;
  }

  function libraryEditorHasActiveControl() {
    const active = document.activeElement;
    if (!(active instanceof Element) || active === document.body) return false;
    const containers = [
      byId("settings-library-profile-list"),
      byId("settings-library-profile-nav"),
      byId("settings-library-active-title")?.closest?.(".settings-library-actions-panel"),
    ].filter(Boolean);
    if (!containers.some((container) => container.contains(active))) return false;
    return Boolean(active.closest?.("select, input, textarea"));
  }

  function shouldDeferAutomaticLibraryRender(options = {}) {
    return Boolean(options?.automatic === true && profileCardsFromDom().length && libraryEditorHasActiveControl());
  }

  function renderSettingsLibraries(settings, options = {}) {
    const incomingProfiles = currentProfilesFromSettings(settings);
    syncLibraryWatchControlsFromConfig(settings, options);
    if (shouldDeferAutomaticLibraryRender(options)) return;
    if (libraryEditorDirty && profileCardsFromDom().length) {
      try {
        const stagedProfiles = collectProfilesFromDom();
        if (!profilesEquivalent(stagedProfiles, incomingProfiles)) {
          profiles = stagedProfiles;
          setText("settings-libraries-status", `${profiles.length} library profile(s) staged`);
          renderActiveLibraryCommandState();
          return;
        }
        libraryEditorDirty = false;
      } catch (error) {
        const message = error instanceof Error ? error.message : String(error);
        setText("settings-libraries-status", "Unsaved libraries kept");
        setLibraryFeedback(`Unsaved library edits were kept through refresh. ${message}`);
        return;
      }
    }
    profiles = incomingProfiles;
    renderProfileCards();
  }

  function libraryPaneId(profileId) {
    return `settings-library-pane-${slug(profileId, "library")}`;
  }

  function storedLibraryTabId(validIds) {
    try {
      const stored = localStorage.getItem("mediapipeline-library-profile") || localStorage.getItem("mediapipeline-library-tab") || "";
      if (validIds.includes(stored)) return stored;
    } catch (_error) {}
    if (validIds.includes(activeLibraryTabId)) return activeLibraryTabId;
    if (validIds.includes("movies")) return "movies";
    return validIds[0] || "";
  }

  function activateLibraryTab(libraryId, options = {}) {
    const tabBar = byId("settings-library-profile-nav");
    const list = byId("settings-library-profile-list");
    if (!tabBar || !list) return;
    const tabs = Array.from(tabBar.querySelectorAll("[data-library-profile-nav]"));
    const panes = Array.from(list.querySelectorAll("[data-library-profile-pane]"));
    const validIds = panes.map((pane) => pane.getAttribute("data-library-profile-pane") || "").filter(Boolean);
    const activeId = validIds.includes(libraryId) ? libraryId : storedLibraryTabId(validIds);
    const previousActiveId = activeLibraryTabId;
    activeLibraryTabId = activeId;
    tabs.forEach((tab) => {
      const active = tab.getAttribute("data-library-profile-nav") === activeId;
      if (active) tab.setAttribute("aria-current", "location");
      else tab.removeAttribute("aria-current");
    });
    panes.forEach((pane) => {
      pane.classList.toggle("is-active", pane.getAttribute("data-library-profile-pane") === activeId);
    });
    if (activeId !== previousActiveId) closeOverrideSections(activeId);
    try { localStorage.setItem("mediapipeline-library-profile", activeId); } catch (_error) {}
    renderActiveLibraryCommandState();
    if (options.source !== "route-map") {
      window.mediaPipelineLibraryRouteMap?.selectProfile?.(activeId, { source: "library-editor" });
    }
    if (typeof window.updatePagePanelEmptyStates === "function") window.updatePagePanelEmptyStates();
  }

  function activateLibraryProfile(libraryId, options = {}) {
    activateLibraryTab(libraryId, options);
  }

  function closeOverrideSections(profileId) {
    if (profileId) openOverrideSectionsByLibrary.set(profileId, new Set());
    const pane = byId(libraryPaneId(profileId));
    if (!pane) return;
    pane.querySelectorAll("details[data-library-override-section]").forEach((section) => {
      section.open = false;
    });
  }

  function activeLibraryCard() {
    const activePane = byId("settings-library-profile-list")?.querySelector(".settings-library-profile-pane.is-active");
    return activePane?.querySelector(".settings-library-card") || null;
  }

  function activeLibraryProfileId(card = activeLibraryCard()) {
    return card?.dataset.libraryId || activeLibraryTabId || "";
  }

  function activeLibraryName(card = activeLibraryCard()) {
    const input = card?.querySelector('[data-library-field="name"]');
    const id = activeLibraryProfileId(card);
    return text(input?.value) || (id === "tv" ? "TV" : id === "movies" ? "Movies" : "Library");
  }

  function activeLibraryCanDelete(card = activeLibraryCard()) {
    const id = activeLibraryProfileId(card);
    return Boolean(id && id !== "movies" && id !== "tv");
  }

  function renderActiveLibraryCommandState() {
    const card = activeLibraryCard();
    const name = activeLibraryName(card);
    const canDelete = activeLibraryCanDelete(card);
    setText("settings-library-active-title", `Selected library: ${name}`);
    setText("settings-library-editor-status", `Editing ${name}`);
    setText(
      "settings-library-active-detail",
      canDelete
        ? "Delete removes this profile from the staged LibraryProfiles patch; Save Library Profile persists after backend validation."
        : "Movie and TV are default profiles. They can be edited and saved, but they cannot be deleted."
    );
    const deleteButton = byId("settings-library-delete-button");
    if (deleteButton) {
      deleteButton.disabled = !canDelete;
      deleteButton.title = canDelete
        ? `Delete ${name} from the staged library profiles.`
        : "Movie and TV default profiles cannot be deleted.";
    }
    const defaultsButton = byId("settings-library-defaults-button");
    if (defaultsButton) {
      defaultsButton.disabled = !activeLibraryProfileId(card);
      defaultsButton.title = "Reset all explicit library overrides to inherited/default values in the editor. Stage Patch, Preview, and Save are still required.";
    }
    renderLibraryStateStrip();
  }

  function renderProfileCards(options = {}) {
    const list = byId("settings-library-profile-list");
    const tabBar = byId("settings-library-profile-nav");
    if (!list) return;
    captureOpenOverrideSections();
    if (tabBar) tabBar.replaceChildren();
    list.replaceChildren();
    profiles.forEach((profile) => {
      if (tabBar) {
        const tab = document.createElement("button");
        tab.type = "button";
        tab.className = "profile-nav-btn";
        tab.setAttribute("aria-controls", libraryPaneId(profile.id));
        tab.setAttribute("data-library-profile-nav", profile.id);
        tab.textContent = profile.name;
        tab.addEventListener("click", () => activateLibraryTab(profile.id));
        tabBar.appendChild(tab);
      }
      const pane = document.createElement("div");
      pane.id = libraryPaneId(profile.id);
      pane.className = "settings-tab-pane settings-library-profile-pane";
      pane.setAttribute("role", "region");
      pane.setAttribute("aria-label", `${profile.name} library profile`);
      pane.setAttribute("data-library-profile-pane", profile.id);
      pane.appendChild(renderCard(profile));
      list.appendChild(pane);
    });
    setText("settings-libraries-status", `${profiles.length} library profile(s) loaded`);
    const profileIds = profiles.map((profile) => profile.id);
    const preferredActiveId = text(options.activeProfileId);
    activateLibraryTab(profileIds.includes(preferredActiveId) ? preferredActiveId : storedLibraryTabId(profileIds));
    renderLibraryWarningSummary();
  }

  function rerenderLibraryCard(card) {
    const pane = card?.closest?.("[data-library-profile-pane]");
    if (!pane) return;
    captureOpenOverrideSections();
    const profile = normalizeProfile(profileFromCard(card, 1), 1);
    pane.replaceChildren(renderCard(profile));
    profiles = collectProfilesFromDom();
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
    setOverrideControlValue(control, key, value);
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

  function syncLibraryCompatibilityAvailability(card) {
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
      row.classList.toggle("is-forced", forced);
      if (forced) {
        const reason = presetReasonForKey(preset, group, key);
        if (control) {
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
        delete row.dataset.libraryForcedByPreset;
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
        setLibraryOverrideValue(card, key, defaultSettingValue(key), { reset: true });
      });
    });
    syncLibraryRouteReadouts(card);
    syncLibraryCompatibilityAvailability(card);
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
      setLibraryRouteOverrideValue(card, key, defaultSettingValue(key), { reset: true });
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

  function updateOverrideRowState(row, isOverride) {
    row.dataset.libraryOverride = isOverride ? "true" : "false";
    row.classList.toggle("is-custom", isOverride);
    row.classList.toggle("is-inherited", !isOverride);
    const key = row.getAttribute("data-library-override-key") || "";
    const control = row.querySelector("[data-library-override-control]");
    const state = row.querySelector("[data-library-override-state-label]");
    if (state && control) {
      state.textContent = overrideStateText(isOverride, readOverrideControlValue(control, key), defaultSettingValue(key));
      state.classList.toggle("is-custom", isOverride);
      state.classList.toggle("is-inherited", !isOverride);
    }
    const button = row.querySelector("[data-library-use-default-override]");
    if (button) {
      button.hidden = !isOverride;
      button.disabled = !isOverride;
    }
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
    const id = currentId === "movies" || currentId === "tv"
      ? currentId
      : slug(fieldValue("name"), currentId || `library-${index}`);
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
    if (libraryProfilePatchSaved && !libraryEditorDirty) return "saved";
    if (!hasLibraryProfiles) return "none";
    if (libraryProfilePatchCurrent) return "staged";
    return "stale";
  }

  function renderLibraryStateStrip() {
    const patchState = libraryPatchStateKind();
    const activeId = activeLibraryProfileId();
    const editorState = libraryEditorDirty
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
    const routeState = libraryEditorDirty || patchState === "staged" || patchState === "stale"
      ? ["Route map: saved evidence, edits pending", "warning"]
      : ["Route map: saved backend evidence", "saved"];
    const patchStateText = patchTextByState[patchState] || patchTextByState.none;
    setStateBadge("settings-library-editor-state", editorState[0], editorState[1]);
    setStateBadge("settings-library-patch-state", patchStateText[0], patchStateText[1]);
    setStateBadge("settings-library-route-map-scope", routeState[0], routeState[1]);
    window.mediaPipelineLibraryRouteMap?.setEditorState?.({
      activeProfileId: activeId,
      dirty: libraryEditorDirty,
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
    lastLibraryProfileResetRequest = collectLibraryProfileResetsFromDom();
    return lastLibraryProfileResetRequest;
  }

  function buildPatchFromLibraries() {
    try {
      const libraryProfiles = collectProfilesFromDom();
      const patch = {
        LibraryProfiles: libraryProfiles,
      };
      lastLibraryProfileResetRequest = collectLibraryProfileResetsFromDom();
      libraryProfilePatchSaved = false;
      if (typeof window.writeSettingsPatchJson === "function") {
        window.writeSettingsPatchJson(patch, "LibraryProfiles patch built. Save Settings will validate paths, overrides, and mirrored compatibility keys.");
        libraryProfilePatchCurrent = true;
      } else {
        libraryProfilePatchCurrent = false;
      }
      profiles = libraryProfiles;
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
      "Save Library Profiles calls the backend settings save route, asks for confirmation, and creates the normal config backup before writing.",
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
        libraryEditorDirty = false;
        libraryProfilePatchCurrent = false;
        libraryProfilePatchSaved = true;
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

  function renderLibraryWarningSummary() {
    setLibraryFeedback([...mp4CompatibilityWarningLines(), ...prunedOverrideWarningLines()].join("\n"));
  }

  function addLibraryCard() {
    const next = profiles.length + 1;
    const profile = normalizeProfile({
      id: `library-${Date.now()}`,
      name: `Library ${next}`,
      enabled: true,
      designation: "auto",
      source_path: "",
      output_path: text(config().Outsource),
      promotion_enabled: false,
      promotion_destination: "",
      overrides: emptyOverrides(),
      default_tracking: {
        ...defaultTracking(`library-${next}`),
        inherited_fields: ["output_path"],
      },
    }, next);
    profiles.push(profile);
    activeLibraryTabId = profile.id;
    markLibraryEditorDirty();
    renderProfileCards({ activeProfileId: profile.id });
    setText("settings-libraries-status", `${profiles.length} library profile(s) staged`);
  }

  function deleteActiveLibrary() {
    const card = activeLibraryCard();
    if (!card) return;
    const name = activeLibraryName(card);
    if (!activeLibraryCanDelete(card)) {
      setText("settings-libraries-status", "Default library protected");
      renderLibraryPatchHandoff(`${name} cannot be deleted because Movie and TV are required default profiles.`);
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
      profiles = profileCardsFromDom()
        .filter((profileCard) => profileCard !== card)
        .map((profileCard, index) => profileFromCard(profileCard, index + 1));
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      setText("settings-libraries-status", "Delete blocked");
      setLibraryFeedback(message);
      return;
    }
    activeLibraryTabId = profiles[0]?.id || "movies";
    markLibraryEditorDirty();
    renderProfileCards({ activeProfileId: activeLibraryTabId });
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
      if (control) setOverrideControlValue(control, key, defaultSettingValue(key));
      updateOverrideRowState(row, false);
      if (wasOverride) {
        row.dataset.libraryResetPending = "true";
        resetCount += 1;
      }
    });
    syncLibraryRouteReadouts(card);
    try {
      profiles = profileCardsFromDom().map((profileCard, index) => profileFromCard(profileCard, index + 1));
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
    closeOverrideSections(activeLibraryTabId);
    libraryEditorDirty = false;
    libraryProfilePatchCurrent = false;
    libraryProfilePatchSaved = false;
    const cleared = clearLibraryProfilesPatchJson("Reset From Current removed LibraryProfiles from Changes JSON. Saved backend settings were not changed.");
    syncLibraryWatchControlsFromConfig(lastSettings);
    renderSettingsLibraries(lastSettings);
    setText("settings-libraries-status", cleared ? "Reset from current; staged LibraryProfiles cleared" : "Reset from current");
    renderLibraryPatchHandoff(cleared
      ? "Reset From Current restored the editor from loaded settings and cleared the staged LibraryProfiles patch."
      : "Reset From Current restored the editor from loaded settings. No LibraryProfiles patch was staged.");
    renderLibraryStateStrip();
  }

  function initSettingsLibrariesEvents() {
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
            setOverrideControlValue(control, key, defaultSettingValue(key));
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
          if (row) {
            delete row.dataset.libraryResetPending;
            updateOverrideRowState(row, true);
          }
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
              profiles = profileCardsFromDom().map((profileCard, index) => profileFromCard(profileCard, index + 1));
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
          if (row) {
            delete row.dataset.libraryResetPending;
            updateOverrideRowState(row, true);
          }
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
        const openSections = openOverrideSectionsByLibrary.get(profileId) || new Set();
        if (target.open) openSections.add(sectionKey);
        else openSections.delete(sectionKey);
        openOverrideSectionsByLibrary.set(profileId, openSections);
      }, true);
    }
    byId("settings-library-add-button")?.addEventListener("click", addLibraryCard);
    byId("settings-library-delete-button")?.addEventListener("click", deleteActiveLibrary);
    byId("settings-library-defaults-button")?.addEventListener("click", replaceActiveLibraryValuesWithDefaults);
    byId("settings-library-build-patch-button")?.addEventListener("click", buildPatchFromLibraries);
    byId("settings-library-reset-button")?.addEventListener("click", resetFromSaved);
    byId("settings-library-preview-button")?.addEventListener("click", previewLibraryProfiles);
    byId("settings-library-save-button")?.addEventListener("click", saveLibraryProfiles);
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
  window.mediaPipelineSettingsLibraries = {
    renderSettingsLibraries,
    initSettingsLibrariesEvents,
    activateLibraryProfile,
    buildPatchFromLibraries,
    stageLibraryWatchAutoRunPatch,
    previewLibraryWatchAutoRunPatch,
    saveLibraryWatchAutoRunPatch,
    deleteActiveLibrary,
    replaceActiveLibraryValuesWithDefaults,
    libraryProfileResetRequest,
    previewLibraryProfiles,
    saveLibraryProfiles,
  };
})();
