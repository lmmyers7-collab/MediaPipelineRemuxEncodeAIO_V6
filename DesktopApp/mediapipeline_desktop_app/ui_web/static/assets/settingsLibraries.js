(function () {
  const metadata = window.mediaPipelineSettingsMetadata || {};
  const choiceLabels = metadata.settingsChoiceLabels || {};
  const advancedFallbackKeys = new Set(metadata.settingsAdvancedFallbackKeys || []);
  const pathFields = ["source_path", "output_path", "promotion_destination"];
  const designationValues = ["movie", "tv", "auto"];

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
      { type: "grid", fields: ["RoutingProfile", "SizeGuardMode", "RouteThresholdMode", "EncodeTuningPreset", "EncodeLadder", "VideoCodec", "OutputContainer", "MaxEncodeGrowthPercent", "CompatibilityEncodeGrowthPercent", "EncodeThresholdGB", "TVEncodeThresholdGB", "MovieRouteMaxVideoBitrateMbps", "TVRouteMaxVideoBitrateMbps"] },
      { type: "note", text: "Library editor overrides affect only content routed through this library. Backend preview/save remains authoritative before future runs use these values." },
    ],
    video: [
      { type: "grid", fields: ["VideoPreset", "VideoQuality", "H264RemuxMaxBitrateMbps", "H264RemuxMaxHeight", "FallbackCpuQuality", "CpuEncodePreset", "CpuEncodeProcessPriority", "CpuEncodeMaxThreads"] },
      { type: "options", fields: ["AllowH264RemuxIfPlexCompatible"] },
      { type: "full", fields: ["RemuxSafeVideoCodecs", "ExtraVideoFlags"] },
      { type: "note", text: "Use this for direct-copy allowlists and fallback encode controls. Backend preview/save remains authoritative before any future run uses these values." },
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

  function config() {
    return (lastSettings && lastSettings.config) || {};
  }

  function fieldDefinitions() {
    return Array.isArray(lastSettings?.field_definitions) ? lastSettings.field_definitions : [];
  }

  function libraryProfileStates() {
    return Array.isArray(lastSettings?.library_profile_state) ? lastSettings.library_profile_state : [];
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

  function overrideStatus(groupKey, key) {
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

  const metadataBadgeLabels = {
    routing: "ROUTING",
    route: "ROUTING",
    compatibility: "COMPATIBILITY",
    quality: "QUALITY",
    size: "SIZE",
    bitrate: "BITRATE",
    output: "OUTPUT",
    verification: "VERIFY",
    verify: "VERIFY",
    publish: "PUBLISH",
    advisory: "ADVISORY",
    hard: "HARD",
    soft: "SOFT",
    advanced: "ADVANCED",
  };

  function metadataBadgeKind(value) {
    const normalized = String(value || "").trim().toLowerCase().replace(/_/g, "-");
    if (normalized === "route") return "routing";
    if (normalized === "verify") return "verification";
    return normalized;
  }

  function metadataBadgeText(value) {
    const kind = metadataBadgeKind(value);
    return metadataBadgeLabels[kind] || String(value || "").replace(/_/g, " ").toUpperCase();
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

  function renderMetadataBadges(fieldKey, field) {
    const badges = [
      ...metadataTags(field?.rule_taxonomy).map((value) => ["taxonomy", value]),
      ...metadataTags(field?.strictness).map((value) => ["strictness", value]),
    ];
    if (fieldIsAdvanced(fieldKey, field) && !badges.some(([, value]) => metadataBadgeKind(value) === "advanced")) {
      badges.push(["visibility", "advanced"]);
    }
    if (!badges.length) return "";
    return `
      <span class="settings-library-metadata-badges" data-metadata-source="backend">
        ${badges.map(([kind, value]) => `<span class="rule-badge settings-library-metadata-badge" data-metadata-kind="${escapeHtml(kind)}" data-rule-kind="${escapeHtml(metadataBadgeKind(value))}" title="Display-only backend metadata; not a saved config key.">${escapeHtml(metadataBadgeText(value))}</span>`).join("")}
      </span>
    `;
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
    const stepValue = field?.step || (field?.kind === "optional_float" ? "any" : "");
    const step = stepValue ? ` step="${escapeHtml(stepValue)}"` : "";
    const textAttrs = inputType === "text" ? ' autocomplete="off" spellcheck="false"' : "";
    return `<input type="${inputType}"${step}${textAttrs}${disabledAttr} data-library-override-control data-library-override-key="${escapeHtml(key)}" value="${escapeHtml(formatValue(value))}">`;
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

  function renderOverrideField(profile, groupKey, fieldKey, variant = "grid") {
    const status = overrideStatus(groupKey, fieldKey);
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
    const ruleTaxonomy = metadataTags(field?.rule_taxonomy).join(",");
    const strictness = String(field?.strictness || "");
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
    const rowAttrs = `class="${baseClass}" data-library-override-row data-library-override-group="${escapeHtml(groupKey)}" data-library-override-key="${escapeHtml(fieldKey)}" data-library-persisted-key="${escapeHtml(persistedKey)}" data-library-override="${isOverride ? "true" : "false"}" data-library-override-eligible="${editable ? "true" : "false"}" data-library-section="${escapeHtml(section)}" data-library-scope="${escapeHtml(scope)}" data-library-rule-taxonomy="${escapeHtml(ruleTaxonomy)}" data-library-strictness="${escapeHtml(strictness)}" data-library-advanced-visibility="${escapeHtml(advancedVisibility)}" data-library-unavailable-reason="${escapeHtml(unavailableReason)}"${advancedAttr}${title}`;
    const control = buildOverrideControl(fieldKey, value, !editable);
    const button = editable ? renderUseDefaultButton(groupKey, fieldKey, isOverride) : "";
    const badges = renderMetadataBadges(fieldKey, field);
    const unavailable = unavailableReason ? `<span class="note settings-library-override-unavailable">${escapeHtml(unavailableReason)}</span>` : "";
    if (field?.kind === "bool") {
      return `
        <label ${rowAttrs}>
          ${control}
          <span class="settings-library-override-label-text">${label}</span>
          ${badges}
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
          ${badges}
          ${state}
          ${button}
        </span>
        ${control}
        ${unavailable}
      </label>
    `;
  }

  function fieldsForGroup(groupKey, fields) {
    return fields.filter((fieldKey) => overrideStatus(groupKey, fieldKey).render);
  }

  function renderFieldGrid(profile, groupKey, fields) {
    const rows = fieldsForGroup(groupKey, fields).map((fieldKey) => {
      const field = fieldDefinition(fieldKey);
      return renderOverrideField(profile, groupKey, fieldKey, field?.kind === "bool" ? "check-grid" : "grid");
    });
    if (!rows.length) return "";
    return `<div class="form-grid launch-form-grid">${rows.join("")}</div>`;
  }

  function renderOptionGrid(profile, groupKey, fields) {
    const rows = fieldsForGroup(groupKey, fields).map((fieldKey) => renderOverrideField(profile, groupKey, fieldKey, "check"));
    if (!rows.length) return "";
    return `<div class="option-grid option-grid-compact">${rows.join("")}</div>`;
  }

  function renderFullFields(profile, groupKey, fields) {
    return fieldsForGroup(groupKey, fields).map((fieldKey) => renderOverrideField(profile, groupKey, fieldKey, "full")).join("");
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
      if (block.type === "grid") return renderFieldGrid(profile, groupKey, block.fields || []);
      if (block.type === "options") return renderOptionGrid(profile, groupKey, block.fields || []);
      if (block.type === "full") return renderFullFields(profile, groupKey, block.fields || []);
      if (block.type === "panel") return renderNestedOptionPanel(profile, groupKey, block);
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
    return card;
  }

  function renderSettingsLibraries(settings) {
    const incomingProfiles = currentProfilesFromSettings(settings);
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
      const stored = localStorage.getItem("mediapipeline-library-tab") || "";
      if (validIds.includes(stored)) return stored;
    } catch (_error) {}
    if (validIds.includes(activeLibraryTabId)) return activeLibraryTabId;
    if (validIds.includes("movies")) return "movies";
    return validIds[0] || "";
  }

  function activateLibraryTab(libraryId) {
    const tabBar = byId("settings-library-tab-bar");
    const list = byId("settings-library-profile-list");
    if (!tabBar || !list) return;
    const tabs = Array.from(tabBar.querySelectorAll("[data-library-profile-tab]"));
    const panes = Array.from(list.querySelectorAll("[data-library-profile-pane]"));
    const validIds = panes.map((pane) => pane.getAttribute("data-library-profile-pane") || "").filter(Boolean);
    const activeId = validIds.includes(libraryId) ? libraryId : storedLibraryTabId(validIds);
    const previousActiveId = activeLibraryTabId;
    activeLibraryTabId = activeId;
    tabs.forEach((tab) => {
      const active = tab.getAttribute("data-library-profile-tab") === activeId;
      tab.setAttribute("aria-selected", String(active));
      tab.setAttribute("tabindex", active ? "0" : "-1");
    });
    panes.forEach((pane) => {
      pane.classList.toggle("is-active", pane.getAttribute("data-library-profile-pane") === activeId);
    });
    if (activeId !== previousActiveId) closeOverrideSections(activeId);
    try { localStorage.setItem("mediapipeline-library-tab", activeId); } catch (_error) {}
    renderActiveLibraryCommandState();
    if (typeof window.updatePagePanelEmptyStates === "function") window.updatePagePanelEmptyStates();
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
      defaultsButton.title = "Clear all Editor, Video/Media, Subtitle, and Audio overrides for the selected library.";
    }
  }

  function renderProfileCards() {
    const list = byId("settings-library-profile-list");
    const tabBar = byId("settings-library-tab-bar");
    if (!list) return;
    captureOpenOverrideSections();
    if (tabBar) tabBar.replaceChildren();
    list.replaceChildren();
    profiles.forEach((profile) => {
      if (tabBar) {
        const tab = document.createElement("button");
        tab.type = "button";
        tab.className = "settings-tab-btn";
        tab.setAttribute("role", "tab");
        tab.setAttribute("aria-selected", "false");
        tab.setAttribute("aria-controls", libraryPaneId(profile.id));
        tab.setAttribute("data-library-profile-tab", profile.id);
        tab.textContent = profile.name;
        tab.addEventListener("click", () => activateLibraryTab(profile.id));
        tabBar.appendChild(tab);
      }
      const pane = document.createElement("div");
      pane.id = libraryPaneId(profile.id);
      pane.className = "settings-tab-pane settings-library-profile-pane";
      pane.setAttribute("role", "tabpanel");
      pane.setAttribute("data-library-profile-pane", profile.id);
      pane.appendChild(renderCard(profile));
      list.appendChild(pane);
    });
    setText("settings-libraries-status", `${profiles.length} library profile(s) loaded`);
    activateLibraryTab(storedLibraryTabId(profiles.map((profile) => profile.id)));
    renderLibraryWarningSummary();
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

  function generatedPromotionRules(libraryProfiles, existingRules) {
    const rules = [];
    libraryProfiles.forEach((profile) => {
      if (!profile.enabled || !profile.promotion_enabled || !profile.source_path || !profile.promotion_destination) return;
      rules.push({
        id: `library-profile-${profile.id}`,
        label: `${profile.name} promotion`,
        enabled: true,
        source_root: profile.source_path,
        output_root: profile.output_path,
        destination_root: profile.promotion_destination,
        library_id: profile.id,
        designation: profile.designation,
      });
    });
    const seen = new Set(rules.map((rule) => `${rule.source_root}|${rule.destination_root}`.toLowerCase()));
    (Array.isArray(existingRules) ? existingRules : []).forEach((rule) => {
      if (!rule || typeof rule !== "object") return;
      const key = `${rule.source_root || ""}|${rule.destination_root || ""}`.toLowerCase();
      if (seen.has(key)) return;
      rules.push(rule);
    });
    return rules;
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

  function libraryProfileResetRequest() {
    if (!currentPatchIncludesLibraryProfiles()) return [];
    lastLibraryProfileResetRequest = collectLibraryProfileResetsFromDom();
    return lastLibraryProfileResetRequest;
  }

  function buildPatchFromLibraries() {
    try {
      const libraryProfiles = collectProfilesFromDom();
      const movie = libraryProfiles.find((profile) => profile.designation === "movie" && profile.enabled) || libraryProfiles[0];
      const tv = libraryProfiles.find((profile) => profile.designation === "tv" && profile.enabled);
      const patch = {
        LibraryProfiles: libraryProfiles,
      };
      if (movie && movie.source_path) patch.SourceMovies = movie.source_path;
      if (tv && tv.source_path) patch.SourceTV = tv.source_path;
      if (movie && movie.output_path) patch.Outsource = movie.output_path;
      if (libraryProfiles.some((profile) => profile.enabled && profile.promotion_enabled)) {
        patch.FinalLibraryPromotionEnabled = true;
      }
      patch.FinalLibraryPromotionRules = generatedPromotionRules(libraryProfiles, config().FinalLibraryPromotionRules);
      lastLibraryProfileResetRequest = collectLibraryProfileResetsFromDom();
      if (typeof window.writeSettingsPatchJson === "function") {
        window.writeSettingsPatchJson(patch, "LibraryProfiles patch built. Preview/Save will validate paths, overrides, and mirrored Movie/TV compatibility keys.");
      }
      profiles = libraryProfiles;
      renderLibraryWarningSummary(patch);
      setText("settings-libraries-status", `${libraryProfiles.length} library profile(s) staged`);
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
    const patchStatus = byId("settings-patch-status")?.textContent || "No patch";
    const keys = currentSettingsPatchKeys();
    const lines = [
      message,
      `Shared settings patch status: ${patchStatus}`,
      `Staged keys: ${keys.length ? keys.join(", ") : "none"}`,
      "Save Library Profiles calls the backend settings save route, asks for confirmation, and creates the normal config backup before writing.",
      "Runtime boundary: these controls do not scan, launch, publish, promote, move, or delete media files.",
    ].filter(Boolean);
    setLibraryFeedback(lines.join("\n"));
  }

  async function previewLibraryProfiles() {
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
    await preview();
    setText("settings-libraries-status", "Library preview finished");
    renderLibraryPatchHandoff("Library profile preview command finished.");
  }

  async function saveLibraryProfiles() {
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
    await save();
    setText("settings-libraries-status", "Library save command finished");
    renderLibraryPatchHandoff("Library profile save command finished.");
  }

  function renderLibraryWarningSummary() {
    setLibraryFeedback("");
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
    renderProfileCards();
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
      ? window.confirm(`Delete the ${name} library profile from the staged settings patch? Saved settings do not change until Save Library Profile succeeds.`)
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
    renderProfileCards();
    setText("settings-libraries-status", `${name} library profile removed from staged editor`);
    renderLibraryWarningSummary();
  }

  function replaceActiveLibraryValuesWithDefaults() {
    const card = activeLibraryCard();
    if (!card) return;
    const name = activeLibraryName(card);
    card.querySelectorAll("[data-library-override-row]").forEach((row) => {
      const wasOverride = row.dataset.libraryOverride === "true";
      const key = row.getAttribute("data-library-override-key") || "";
      const control = row.querySelector("[data-library-override-control]");
      if (control) setOverrideControlValue(control, key, defaultSettingValue(key));
      updateOverrideRowState(row, false);
      if (wasOverride) row.dataset.libraryResetPending = "true";
    });
    try {
      profiles = profileCardsFromDom().map((profileCard, index) => profileFromCard(profileCard, index + 1));
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      setText("settings-libraries-status", "Defaults blocked");
      setLibraryFeedback(message);
      return;
    }
    markLibraryEditorDirty();
    setText("settings-libraries-status", `${name} settings overrides cleared`);
    renderLibraryWarningSummary();
  }

  function resetFromSaved() {
    closeOverrideSections(activeLibraryTabId);
    libraryEditorDirty = false;
    renderSettingsLibraries(lastSettings);
  }

  function initSettingsLibrariesEvents() {
    const list = byId("settings-library-profile-list");
    if (list) {
      list.addEventListener("click", (event) => {
        const target = event.target;
        if (!(target instanceof Element)) return;
        const card = target.closest?.(".settings-library-card");
        if (!card) return;
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
          const tab = Array.from(byId("settings-library-tab-bar")?.querySelectorAll("[data-library-profile-tab]") || [])
            .find((item) => item.getAttribute("data-library-profile-tab") === tabId);
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
        }
        if (field || target.matches?.("[data-library-override-control]")) markLibraryEditorDirty();
        renderLibraryWarningSummary();
      });
      list.addEventListener("change", (event) => {
        const target = event.target;
        if (target instanceof Element && target.matches?.("[data-library-override-control]")) {
          const row = target.closest("[data-library-override-row]");
          if (row) {
            delete row.dataset.libraryResetPending;
            updateOverrideRowState(row, true);
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
  }

  window.mediaPipelineSettingsLibraries = {
    renderSettingsLibraries,
    initSettingsLibrariesEvents,
    buildPatchFromLibraries,
    deleteActiveLibrary,
    replaceActiveLibraryValuesWithDefaults,
    libraryProfileResetRequest,
    previewLibraryProfiles,
    saveLibraryProfiles,
  };
})();
