// queue/fileOverrides.drawer.form.js
// Form, inheritance, and dirty-state helpers for the Queue file override drawer.

(function initFileOverridesDrawerFormModule() {
  // eslint-disable-next-line max-lines-per-function
  function createFileOverridesDrawerFormModule(ctx) {
    const {
      documentRef: document,
      state,
      DRAWER_FIELD_HINT_IDS,
      DRAWER_FIELD_PATHS,
      DRAWER_FIELD_CONFIG,
      ROUTE_FIELD_CONFIG,
      ROUTE_FIELD_KEYS,
      parseLangList,
      langCodesToRules,
      rulesToLangInput,
      byId,
      isPlainObject,
      hasOwnValue,
      setStatus,
    } = ctx;

    function resetExactTrackControls() { return ctx.tracks.resetExactTrackControls(); }
    function collectExactTrackSelectorsFromControls() { return ctx.tracks.collectExactTrackSelectorsFromControls(); }
    function clearDrawerTrackMetadata(message) { return ctx.tracks.clearDrawerTrackMetadata(message); }
    function renderDrawerTrackMetadata(payload) { return ctx.tracks.renderDrawerTrackMetadata(payload); }
    function clearProcessingRouteControls() { return ctx.routePreview.clearProcessingRouteControls(); }
    function clearRoutePreviewStatus() { return ctx.routePreview.clearRoutePreviewStatus(); }
    function renderProcessingRouteControls(payload) { return ctx.routePreview.renderProcessingRouteControls(payload); }
    function renderRoutePreviewFromEffectivePayload(payload) { return ctx.routePreview.renderRoutePreviewFromEffectivePayload(payload); }
    function routeControlElement(fieldKey) { return ctx.routePreview.routeControlElement(fieldKey); }

  // Remembers an operator-initiated expand so value-driven syncs cannot
  // collapse the controls while the operator is still editing empty fields.
  let routeOverrideManualExpand = false;

  function routeOverrideDisclosureElements() {
    return {
      button: byId("fo-route-override-toggle"),
      controls: byId("fo-route-override-controls"),
      status: byId("fo-route-override-disclosure-status"),
      section: byId("fo-processing-route-section"),
    };
  }

  function routeOverrideHasValues() {
    return ROUTE_FIELD_KEYS.some((fieldKey) => {
      const control = routeControlElement(fieldKey);
      return String(control?.value || "").trim() !== "";
    });
  }

  function setRouteOverrideDisclosureExpanded(expanded) {
    const { button, controls, status, section } = routeOverrideDisclosureElements();
    const isExpanded = Boolean(expanded);
    if (controls) controls.hidden = !isExpanded;
    if (button) {
      button.setAttribute("aria-expanded", isExpanded ? "true" : "false");
      button.textContent = isExpanded ? "Hide processing route overrides" : "Override processing route";
    }
    if (status) {
      status.textContent = isExpanded
        ? "Route override controls are visible. Leave fields on saved policy to inherit backend settings."
        : "Using saved processing policy unless an override is expanded and saved.";
    }
    if (section) section.dataset.routeOverridesExpanded = isExpanded ? "true" : "false";
  }

  function syncRouteOverrideDisclosure(options = {}) {
    if (options.resetManualExpand) routeOverrideManualExpand = false;
    if (options.forceExpanded) {
      setRouteOverrideDisclosureExpanded(true);
      return;
    }
    setRouteOverrideDisclosureExpanded(routeOverrideHasValues() || routeOverrideManualExpand);
  }

  function toggleRouteOverrideDisclosure() {
    const button = byId("fo-route-override-toggle");
    const expanded = button?.getAttribute("aria-expanded") === "true";
    routeOverrideManualExpand = !expanded;
    setRouteOverrideDisclosureExpanded(!expanded);
  }

  function drawerChoiceLabel(value, explicitLabel = "") {
    const label = String(explicitLabel || "").trim();
    if (label) return label;
    const text = String(value || "").trim();
    const metadataLabels = window.mediaPipelineSettingsMetadata?.settingsChoiceLabels || {};
    if (metadataLabels[text]) return metadataLabels[text];
    return text.replace(/[_-]/g, " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
  }

  function normalizeRouteChoiceOptions(field) {
    const rawChoices = Array.isArray(field?.choices) ? field.choices : [];
    return rawChoices
      .map((choice) => {
        if (isPlainObject(choice)) {
          const value = String(choice.value || "").trim();
          if (!value) return null;
          return { value, label: drawerChoiceLabel(value, choice.label) };
        }
        const value = String(choice || "").trim();
        return value ? { value, label: drawerChoiceLabel(value) } : null;
      })
      .filter(Boolean);
  }

  function populateRouteSelectOptions(select, choices) {
    if (!select) return;
    const current = select.value;
    select.replaceChildren();
    const inherit = document.createElement("option");
    inherit.value = "";
    inherit.textContent = savedPolicyOptionText(select.dataset.foRouteControl || "");
    select.appendChild(inherit);
    choices.forEach((choice) => {
      const option = document.createElement("option");
      option.value = choice.value;
      option.textContent = choice.label;
      select.appendChild(option);
    });
    const values = choices.map((choice) => choice.value);
    select.value = values.includes(current) ? current : "";
  }

  function firstSettingValue(source, key, groups = []) {
    const candidates = [source];
    groups.forEach((group) => {
      if (isPlainObject(source?.[group])) candidates.push(source[group]);
    });
    for (const candidate of candidates) {
      if (hasOwnValue(candidate, key)) return { found: true, value: candidate[key] };
    }
    return { found: false, value: "" };
  }

  function normalizeLibraryDefaultValue(value, options = {}) {
    if (Array.isArray(value)) {
      const values = value
        .map((item) => isPlainObject(item) ? (item.language || item.value || item.id || "") : item)
        .map((item) => String(item || "").trim())
        .filter(Boolean);
      return options.firstValue ? (values[0] || "") : values.join(", ");
    }
    if (typeof value === "boolean") return value ? "enabled" : "disabled";
    if (value === null || value === undefined) return "";
    return String(value).trim();
  }

  function drawerLibrarySourceLabel(item, sourceName) {
    const libraryName = String(item?.library_name || item?.library_id || "").trim();
    const profileName = String(item?.profile_name || item?.profile || "").trim();
    const parts = [];
    parts.push(libraryName ? `Library ${libraryName}` : "Library");
    if (profileName) parts.push(`profile ${profileName}`);
    if (sourceName === "library_settings_overrides") parts.push("reported overrides");
    return parts.join(" / ");
  }

  function drawerLibrarySettingsSource(item) {
    const effective = isPlainObject(item?.library_effective_settings) ? item.library_effective_settings : {};
    if (Object.keys(effective).length) {
      return { source: effective, sourceName: "library_effective_settings" };
    }
    const overrides = isPlainObject(item?.library_settings_overrides) ? item.library_settings_overrides : {};
    if (Object.keys(overrides).length) {
      return { source: overrides, sourceName: "library_settings_overrides" };
    }
    return { source: {}, sourceName: "" };
  }

  function getDrawerLibraryDefaults(item) {
    const { source, sourceName } = drawerLibrarySettingsSource(item);
    const hasSource = Object.keys(source).length > 0;
    const defaults = {
      available: hasSource,
      sourceLabel: hasSource ? drawerLibrarySourceLabel(item, sourceName) : "Library",
      sourceName,
      fields: {},
    };
    Object.keys(DRAWER_FIELD_CONFIG).forEach((fieldKey) => {
      const config = DRAWER_FIELD_CONFIG[fieldKey] || {};
      if (!hasSource || !config.settingKey) {
        defaults.fields[fieldKey] = { available: false, value: "", unit: config.unit || "" };
        return;
      }
      const found = firstSettingValue(source, config.settingKey, config.groups || []);
      defaults.fields[fieldKey] = {
        available: found.found,
        value: found.found ? normalizeLibraryDefaultValue(found.value, { firstValue: Boolean(config.scalarLanguage) }) : "",
        unit: config.unit || "",
        settingKey: config.settingKey,
      };
    });
    return defaults;
  }

  function formatInheritedValue(inheritedValue) {
    const raw = String(inheritedValue?.value || "").trim();
    if (!raw) return "not set";
    if (inheritedValue?.unit === "channels") return `${raw} channels`;
    return raw;
  }

  function fileOverrideEffectiveSourceLabel(source) {
    if (source === "file_override") return "file override";
    if (source === "folder_override") return "folder override";
    if (source === "library") return "Library";
    if (source === "global_default") return "Global";
    if (source === "pipeline_policy" || source === "default") return "normal pipeline policy";
    if (source === "unavailable") return "unavailable";
    return "";
  }

  function savedPolicySourceLabel(source) {
    if (source === "library") return "library";
    if (source === "global_default") return "global";
    if (source === "pipeline_policy" || source === "default") return "pipeline policy";
    return "";
  }

  function savedPolicyFieldInfo(fieldKey, payload = state.foLastEffectivePayload) {
    const inherited = isPlainObject(payload?.inherited) ? payload.inherited : {};
    const expanded = {
      ...(isPlainObject(payload?.expanded_effective_fields) ? payload.expanded_effective_fields : {}),
      ...(isPlainObject(payload?.route_video_effective_fields) ? payload.route_video_effective_fields : {}),
    };
    const expandedField = isPlainObject(expanded[fieldKey]) ? expanded[fieldKey] : {};
    const inheritedField = isPlainObject(expandedField.inherited)
      ? expandedField.inherited
      : (isPlainObject(inherited[fieldKey]) ? inherited[fieldKey] : {});
    const effectiveField = isPlainObject(expandedField.effective) ? expandedField.effective : {};
    const field = inheritedField.available ? inheritedField : effectiveField;
    const source = String(field.source || "").trim();
    const display = String(field.display || effectiveInheritedHintValue(fieldKey, field) || "").trim();
    return {
      source,
      sourceLabel: savedPolicySourceLabel(source),
      display,
    };
  }

  function savedPolicyButtonText(fieldKey) {
    const info = savedPolicyFieldInfo(fieldKey);
    return info.sourceLabel ? `Use ${info.sourceLabel} setting` : "Use saved policy";
  }

  function savedPolicyOptionText(fieldKey) {
    const info = savedPolicyFieldInfo(fieldKey);
    if (info.sourceLabel && info.display) return `Use ${info.sourceLabel} setting: ${info.display}`;
    if (info.sourceLabel) return `Use ${info.sourceLabel} setting`;
    return "Use saved policy";
  }

  function updateRouteBlankOptions() {
    ROUTE_FIELD_KEYS.forEach((fieldKey) => {
      const control = routeControlElement(fieldKey);
      const option = control?.querySelector('option[value=""]');
      if (option) option.textContent = savedPolicyOptionText(fieldKey);
    });
  }

  function setInheritedHint(fieldKey, inheritedValue, defaultsAvailable) {
    const el = byId(DRAWER_FIELD_HINT_IDS[fieldKey]);
    if (!el) return;
    el.textContent = "";
    delete el.dataset.available;
    if (!defaultsAvailable) return;
    const effectiveSourceLabel = fileOverrideEffectiveSourceLabel(inheritedValue?.effectiveSource || "");
    const effectiveValue = String(inheritedValue?.effectiveValue || "").trim();
    const inheritedSourceLabel = fileOverrideEffectiveSourceLabel(inheritedValue?.source || "");
    const inheritedPrefix = inheritedSourceLabel === "Global" ? "Global setting" : "Library setting";
    if (inheritedValue?.effectiveAvailable && effectiveSourceLabel && effectiveValue) {
      const inheritedText = inheritedValue?.available ? formatInheritedValue(inheritedValue) : "unavailable";
      el.textContent = `Effective: ${formatInheritedValue({ value: effectiveValue, unit: inheritedValue?.unit || "" })} (${effectiveSourceLabel}). ${inheritedPrefix}: ${inheritedText}`;
      el.dataset.available = "true";
      return;
    }
    if (inheritedValue?.available) {
      el.textContent = `${inheritedPrefix}: ${formatInheritedValue(inheritedValue)}`;
      el.dataset.available = "true";
    } else {
      el.textContent = "Saved policy value: unavailable";
      el.dataset.available = "false";
    }
  }

  function renderDrawerInheritedDefaults(defaults) {
    const status = byId("fo-inherited-settings-status");
    const available = Boolean(defaults?.available);
    Object.keys(DRAWER_FIELD_HINT_IDS).forEach((fieldKey) => {
      setInheritedHint(fieldKey, defaults?.fields?.[fieldKey], available);
    });
    if (!status) return;
    status.dataset.available = available ? "true" : "false";
    if (!available) {
      status.textContent = "Saved policy values unavailable for this queue row.";
      return;
    }
    const fieldValues = Object.values(defaults.fields || {}).filter((field) => field?.available);
    if (fieldValues.length) {
      status.textContent = `Saved policy values shown from ${defaults.sourceLabel}. Unavailable field hints were not reported on the queue row.`;
    } else {
      status.textContent = `Saved policy values unavailable for these drawer fields; the row only reported ${defaults.sourceLabel}.`;
    }
  }

  function drawerEffectiveSourceLabel(payload, item) {
    const library = isPlainObject(payload?.library) ? payload.library : {};
    const name = String(library.name || library.id || "").trim();
    if (library.available) return name ? `Library ${name}` : "Library";
    const inherited = isPlainObject(payload?.inherited) ? Object.values(payload.inherited) : [];
    if (inherited.some((field) => field?.source === "global_default")) return "Global settings";
    return drawerLibrarySourceLabel(item, "");
  }

  function effectiveInheritedHintValue(fieldKey, field) {
    if (!field?.available) return "";
    const value = field.value;
    if (Array.isArray(value)) return value.map((item) => String(item || "").trim()).filter(Boolean).join(", ");
    if (value === null || value === undefined) return "";
    if (typeof value === "boolean") return value ? "enabled" : "disabled";
    return String(value).trim();
  }

  function drawerDefaultsFromEffectivePayload(payload, item) {
    const inherited = isPlainObject(payload?.inherited) ? payload.inherited : {};
    const expanded = {
      ...(isPlainObject(payload?.expanded_effective_fields) ? payload.expanded_effective_fields : {}),
      ...(isPlainObject(payload?.route_video_effective_fields) ? payload.route_video_effective_fields : {}),
    };
    const fields = {};
    Object.keys(DRAWER_FIELD_CONFIG).forEach((fieldKey) => {
      const expandedField = isPlainObject(expanded[fieldKey]) ? expanded[fieldKey] : {};
      const expandedInherited = isPlainObject(expanded[fieldKey]?.inherited) ? expanded[fieldKey].inherited : {};
      const expandedEffective = isPlainObject(expandedField.effective) ? expandedField.effective : {};
      const field = isPlainObject(inherited[fieldKey]) ? inherited[fieldKey] : expandedInherited;
      fields[fieldKey] = {
        available: Boolean(field.available),
        value: effectiveInheritedHintValue(fieldKey, field),
        source: String(field.source || ""),
        unit: DRAWER_FIELD_CONFIG[fieldKey]?.unit || "",
        settingKey: field.source_key || DRAWER_FIELD_CONFIG[fieldKey]?.settingKey || "",
        effectiveAvailable: Boolean(expandedEffective.available),
        effectiveValue: effectiveInheritedHintValue(fieldKey, expandedEffective),
        effectiveSource: String(expandedEffective.source || ""),
      };
    });
    const hasAvailableField = Object.values(fields).some((field) => field?.available);
    return {
      available: hasAvailableField || Boolean(payload?.library?.available),
      sourceLabel: drawerEffectiveSourceLabel(payload, item),
      sourceName: "file_overrides_effective",
      fields,
    };
  }

  function applyFileOverrideEffectivePayload(payload, item) {
    if (!payload || payload.ok === false) return false;
    state.foLastEffectivePayload = payload;
    state.foExactTrackOverrideEntry = payload.file_override_scope === "file" && isPlainObject(payload.file_override)
      ? payload.file_override
      : null;
    renderProcessingRouteControls(payload);
    updateRouteBlankOptions();
    renderDrawerInheritedDefaults(drawerDefaultsFromEffectivePayload(payload, item));
    if (isPlainObject(payload.file_override)) {
      populateDrawerForm(payload.file_override);
    } else {
      clearDrawerForm({ resetRouteControls: false, resetTrackMetadata: false });
    }
    renderDrawerTrackMetadata(payload);
    renderDrawerUseInheritedButtons(payload);
    renderRoutePreviewFromEffectivePayload(payload);
    markDrawerClean();
    return true;
  }

  function clearDrawerUseInheritedButtons() {
    document.querySelectorAll("[data-fo-use-inherited]").forEach((button) => {
      button.hidden = true;
      button.disabled = true;
      button.textContent = "Use saved policy";
      delete button.dataset.stagedClear;
    });
  }

  function setDrawerUseInheritedAvailable(fieldKey, isAvailable) {
    const button = document.querySelector(`[data-fo-use-inherited="${fieldKey}"]`);
    if (!button) return;
    const fieldPath = DRAWER_FIELD_PATHS[fieldKey];
    const staged = Boolean(fieldPath && state.foPendingClearFieldPaths?.has?.(fieldPath));
    const text = savedPolicyButtonText(fieldKey);
    button.textContent = staged ? "Saved policy staged" : text;
    button.setAttribute("aria-label", `${staged ? "Saved policy staged" : text} for ${fieldKey.replace(/([A-Z])/g, " $1").toLowerCase()}`);
    button.hidden = !isAvailable && !staged;
    button.disabled = !isAvailable || staged;
    if (staged) button.dataset.stagedClear = "true";
    else delete button.dataset.stagedClear;
  }

  function renderDrawerUseInheritedButtons(payload) {
    clearDrawerUseInheritedButtons();
    if (!payload || payload.file_override_scope !== "file" || !isPlainObject(payload.file_override)) return;
    const sources = isPlainObject(payload.sources) ? payload.sources : {};
    const state = drawerOverrideState(payload.file_override);
    Object.keys(DRAWER_FIELD_PATHS).forEach((fieldKey) => {
      const fieldPath = DRAWER_FIELD_PATHS[fieldKey];
      const isExactFileOverride = sources[fieldPath] === "file_override";
      setDrawerUseInheritedAvailable(fieldKey, Boolean(state[fieldKey] && isExactFileOverride));
    });
  }

  function setDrawerCommandButtonsDisabled(disabled) {
    const saveButton = byId("fo-drawer-save");
    const clearButton = byId("fo-drawer-clear");
    const seriesButton = byId("fo-series-preview-open");
    const seriesClearButton = byId("fo-series-clear-open");
    const seriesApplyButton = byId("fo-series-apply");
    const remuxPilotButton = byId("fo-remux-pilot-promote");
    const commandDisabled = Boolean(disabled || state.foDrawerLoading);
    if (saveButton) saveButton.disabled = commandDisabled || !state.foDrawerDirty;
    if (clearButton) clearButton.disabled = commandDisabled;
    if (seriesButton) seriesButton.disabled = commandDisabled || !state.foCurrentPath;
    if (seriesClearButton) seriesClearButton.disabled = commandDisabled || !state.foCurrentPath;
    if (seriesApplyButton && commandDisabled) seriesApplyButton.disabled = true;
    if (remuxPilotButton && commandDisabled) remuxPilotButton.disabled = true;
    document.querySelectorAll("[data-fo-use-inherited]").forEach((button) => {
      if (button.hidden) return;
      button.disabled = commandDisabled || button.dataset.stagedClear === "true";
    });
  }

  function normalizeForSignature(value) {
    if (Array.isArray(value)) return value.map(normalizeForSignature);
    if (isPlainObject(value)) {
      const normalized = {};
      Object.keys(value).sort().forEach((key) => {
        if (key === "path") return;
        normalized[key] = normalizeForSignature(value[key]);
      });
      return normalized;
    }
    return value === undefined ? null : value;
  }

  function drawerFormSignature() {
    const payload = buildOverridePayload();
    return JSON.stringify(normalizeForSignature({
      clear_fields: collectFileOverrideFieldsToClearOnSave(),
      payload: payload || {},
    }));
  }

  function syncDrawerDirtyState() {
    const signature = drawerFormSignature();
    state.foDrawerDirty = Boolean(state.foDrawerBaselineSignature && signature !== state.foDrawerBaselineSignature);
    const drawer = byId("fo-drawer");
    if (drawer) drawer.dataset.dirty = state.foDrawerDirty ? "true" : "false";
    setDrawerCommandButtonsDisabled(state.foCommandInFlight);
    return state.foDrawerDirty;
  }

  function markDrawerClean() {
    state.foPendingClearFieldPaths = new Set();
    state.foDrawerBaselineSignature = drawerFormSignature();
    state.foDrawerDirty = false;
    const drawer = byId("fo-drawer");
    if (drawer) drawer.dataset.dirty = "false";
    setDrawerCommandButtonsDisabled(state.foCommandInFlight);
  }

  function handleDrawerFormChanged() {
    const wasDirty = state.foDrawerDirty;
    const isDirty = syncDrawerDirtyState();
    if (!wasDirty && isDirty) {
      setStatus("Unsaved changes. Save Override to store them or close to discard.", "warning");
    }
  }

  function confirmDiscardDrawerChanges(actionLabel = "close this drawer") {
    if (!state.foDrawerDirty) return true;
    if (state.foCommandInFlight) {
      setStatus("Wait for the current file override command to finish before closing.", "warning");
      return false;
    }
    const ok = window.confirm(
      `Discard unsaved file override changes and ${actionLabel}?`
    );
    if (!ok) {
      setStatus("Unsaved changes kept.", "warning");
      return false;
    }
    return true;
  }

  function clearDrawerOverrideMarkers() {
    document.querySelectorAll("[data-fo-field]").forEach((field) => {
      delete field.dataset.overridden;
      field.querySelectorAll("[data-fo-overridden-badge]").forEach((badge) => {
        badge.hidden = true;
      });
    });
  }

  function setDrawerFieldOverridden(fieldKey, isOverridden) {
    const field = document.querySelector(`[data-fo-field="${fieldKey}"]`);
    if (!field) return;
    if (isOverridden) field.dataset.overridden = "true";
    else delete field.dataset.overridden;
    field.querySelectorAll("[data-fo-overridden-badge]").forEach((badge) => {
      badge.hidden = !isOverridden;
    });
  }

  function ruleListHasValues(rules) {
    return Array.isArray(rules) && rules.some((rule) => {
      if (isPlainObject(rule)) {
        return ["streamIndex", "stream_index", "trackIndex", "track_index", "index", "language", "value", "codec", "channels", "forced", "title"]
          .some((key) => hasOwnValue(rule, key) && String(rule[key] ?? "").trim() !== "");
      }
      return String(rule || "").trim();
    });
  }

  function drawerOverrideState(entry) {
    const audio = isPlainObject(entry?.audio) ? entry.audio : {};
    const subs = isPlainObject(entry?.subtitles) ? entry.subtitles : {};
    const routing = isPlainObject(entry?.routing) ? entry.routing : {};
    const video = isPlainObject(entry?.video) ? entry.video : {};
    return {
      audioKeepLanguages: ruleListHasValues(audio.keepTracks),
      audioDropLanguages: ruleListHasValues(audio.dropTracks),
      audioMaxChannels: hasOwnValue(audio, "maxChannels") && audio.maxChannels !== null && audio.maxChannels !== "",
      audioPreferDefaultLanguage: hasOwnValue(audio, "preferDefaultLanguage") && String(audio.preferDefaultLanguage || "").trim() !== "",
      subtitleKeepLanguages: ruleListHasValues(subs.keepTracks),
      subtitleDropLanguages: ruleListHasValues(subs.dropTracks),
      subtitleBurnTrack: isPlainObject(subs.burnTrack),
      subtitleStripAll: hasOwnValue(subs, "stripAll"),
      routeProfile: hasOwnValue(routing, "profile") && String(routing.profile || "").trim() !== "",
      routingRouteThresholdMode: hasOwnValue(routing, "routeThresholdMode") && String(routing.routeThresholdMode || "").trim() !== "",
      videoCodec: hasOwnValue(video, "codec") && String(video.codec || "").trim() !== "",
      videoContainer: hasOwnValue(video, "container") && String(video.container || "").trim() !== "",
      videoEncodePreset: hasOwnValue(video, "encodePreset") && String(video.encodePreset || "").trim() !== "",
      videoEncodeLadder: hasOwnValue(video, "encodeLadder") && String(video.encodeLadder || "").trim() !== "",
    };
  }

  function renderDrawerOverrideMarkers(entry) {
    clearDrawerOverrideMarkers();
    const state = drawerOverrideState(entry);
    Object.keys(state).forEach((fieldKey) => setDrawerFieldOverridden(fieldKey, state[fieldKey]));
  }

  function clearDrawerForm(options = {}) {
    const resetRouteControls = options.resetRouteControls !== false;
    const resetTrackMetadata = options.resetTrackMetadata !== false;
    const ids = [
      "fo-audio-keep-langs",
      "fo-audio-drop-langs",
      "fo-audio-prefer-default-language",
      "fo-sub-keep-langs",
      "fo-sub-drop-langs",
    ];
    ids.forEach((id) => { const el = byId(id); if (el) el.value = ""; });
    const maxCh = byId("fo-audio-max-channels");
    if (maxCh) maxCh.value = "";
    const stripAll = byId("fo-sub-strip-all");
    if (stripAll) stripAll.checked = false;
    ROUTE_FIELD_KEYS.forEach((fieldKey) => {
      const control = routeControlElement(fieldKey);
      if (control) control.value = "";
    });
    clearDrawerOverrideMarkers();
    clearDrawerUseInheritedButtons();
    state.foPendingClearFieldPaths = new Set();
    state.foExactTrackOverrideEntry = null;
    resetExactTrackControls();
    state.foUnmatchedExactSelectors = ctx.emptyExactSelectorState();
    state.foExactTrackWarnings = [];
    if (resetTrackMetadata) clearDrawerTrackMetadata();
    if (resetRouteControls) clearProcessingRouteControls();
    else clearRoutePreviewStatus();
    syncSubFilterFields();
    syncRouteOverrideDisclosure({ resetManualExpand: true });
    syncDrawerDirtyState();
  }

  function selectedSubtitleBurnControls() {
    return Array.from(document.querySelectorAll('[data-fo-track-action][data-fo-track-kind="subtitle"]'))
      .filter((control) => String(control.value || "") === "burn");
  }

  function setTrackActionDisabledReason(control, message) {
    if (!control) return;
    const reason = control.closest(".fo-track-action")?.querySelector(".fo-track-action-reason");
    const text = String(message || "").trim();
    if (reason) {
      reason.textContent = text;
      reason.hidden = !text;
      if (text && reason.id) control.setAttribute("aria-describedby", reason.id);
      else control.removeAttribute("aria-describedby");
    } else {
      control.removeAttribute("aria-describedby");
    }
    control.title = text;
  }

  function syncSubFilterFields() {
    const stripAll = byId("fo-sub-strip-all");
    const fields   = byId("fo-sub-filter-fields");
    const stripAllChecked = Boolean(stripAll && stripAll.checked);
    const burnControls = selectedSubtitleBurnControls();
    const burnSelected = burnControls.length > 0;
    const burnedControl = burnControls[0] || null;
    if (burnControls.length > 1) {
      burnControls.slice(1).forEach((control) => { control.value = ""; });
    }
    if (!fields) return;
    if (stripAllChecked || burnSelected) {
      fields.style.opacity = "0.4";
      fields.style.pointerEvents = "none";
    } else {
      fields.style.opacity = "";
      fields.style.pointerEvents = "";
    }
    if (stripAll) {
      stripAll.disabled = burnSelected;
      if (burnSelected) stripAll.checked = false;
    }
    document.querySelectorAll('[data-fo-track-action][data-fo-track-kind="subtitle"]').forEach((control) => {
      const hasIndex = control.dataset.foTrackIndexAvailable !== "false";
      control.disabled = stripAllChecked || !hasIndex || (burnSelected && control !== burnedControl);
      if (stripAllChecked) control.value = "";
      if (stripAllChecked) setTrackActionDisabledReason(control, "Subtitle track actions are disabled while Strip all subtitles is selected.");
      else if (burnSelected && control !== burnedControl) setTrackActionDisabledReason(control, "Only one subtitle stream can be burned; clear the burned row to edit other subtitle actions.");
      else if (!hasIndex) setTrackActionDisabledReason(control, "Track stream index unavailable; exact-track override cannot be saved for this row.");
      else setTrackActionDisabledReason(control, "");
    });
  }

  function populateDrawerForm(entry) {
    // entry = { audio: {...}, subtitles: {...} } or null
    state.foPendingClearFieldPaths = new Set();
    const audio = (entry && entry.audio)     || {};
    const subs  = (entry && entry.subtitles) || {};
    const routing = (entry && entry.routing) || {};
    const video = (entry && entry.video) || {};

    const keepLangs = byId("fo-audio-keep-langs");
    const dropLangs = byId("fo-audio-drop-langs");
    const maxCh     = byId("fo-audio-max-channels");
    const preferDefaultLanguage = byId("fo-audio-prefer-default-language");
    if (keepLangs) keepLangs.value = rulesToLangInput(audio.keepTracks);
    if (dropLangs) dropLangs.value = rulesToLangInput(audio.dropTracks);
    if (maxCh) {
      const v = audio.maxChannels != null ? String(audio.maxChannels) : "";
      maxCh.value = ["2","6","8"].includes(v) ? v : "";
    }
    if (preferDefaultLanguage) {
      preferDefaultLanguage.value = String(audio.preferDefaultLanguage || "").trim();
    }

    const stripAll   = byId("fo-sub-strip-all");
    const subKeep    = byId("fo-sub-keep-langs");
    const subDrop    = byId("fo-sub-drop-langs");
    if (stripAll) stripAll.checked = Boolean(subs.stripAll);
    if (subKeep) subKeep.value = rulesToLangInput(subs.keepTracks);
    if (subDrop) subDrop.value = rulesToLangInput(subs.dropTracks);
    const routeProfile = byId("fo-route-profile");
    const routeThresholdMode = byId("fo-route-threshold-mode");
    const videoCodec = byId("fo-video-codec");
    const videoContainer = byId("fo-video-container");
    const videoEncodePreset = byId("fo-video-encode-preset");
    const videoEncodeLadder = byId("fo-video-encode-ladder");
    if (routeProfile) routeProfile.value = String(routing.profile || "");
    if (routeThresholdMode) routeThresholdMode.value = String(routing.routeThresholdMode || "");
    if (videoCodec) videoCodec.value = String(video.codec || "");
    if (videoContainer) videoContainer.value = String(video.container || "");
    if (videoEncodePreset) videoEncodePreset.value = String(video.encodePreset || "");
    if (videoEncodeLadder) videoEncodeLadder.value = String(video.encodeLadder || "");
    renderDrawerOverrideMarkers(entry);
    syncSubFilterFields();
    syncRouteOverrideDisclosure({ resetManualExpand: true });
    syncDrawerDirtyState();
  }

  function buildOverridePayload() {
    const keepLangList = parseLangList(byId("fo-audio-keep-langs")?.value);
    const dropLangList = parseLangList(byId("fo-audio-drop-langs")?.value);
    const maxChVal     = byId("fo-audio-max-channels")?.value || "";
    const preferDefaultLanguage = String(byId("fo-audio-prefer-default-language")?.value || "").trim().toLowerCase();
    const stripAll     = Boolean(byId("fo-sub-strip-all")?.checked);
    const subKeepList  = parseLangList(byId("fo-sub-keep-langs")?.value);
    const subDropList  = parseLangList(byId("fo-sub-drop-langs")?.value);
    const routeProfile = String(byId("fo-route-profile")?.value || "").trim();
    const routeThresholdMode = String(byId("fo-route-threshold-mode")?.value || "").trim();
    const videoCodec = String(byId("fo-video-codec")?.value || "").trim();
    const videoContainer = String(byId("fo-video-container")?.value || "").trim();
    const videoEncodePreset = String(byId("fo-video-encode-preset")?.value || "").trim();
    const videoEncodeLadder = String(byId("fo-video-encode-ladder")?.value || "").trim();
    const exactTrackSelectors = collectExactTrackSelectorsFromControls();

    const audio = {};
    appendSelectorRules(audio, "keepTracks", langCodesToRules(keepLangList));
    appendSelectorRules(audio, "keepTracks", exactTrackSelectors.audioKeep);
    appendSelectorRules(audio, "dropTracks", langCodesToRules(dropLangList));
    appendSelectorRules(audio, "dropTracks", exactTrackSelectors.audioDrop);
    if (maxChVal) audio.maxChannels = parseInt(maxChVal, 10);
    if (preferDefaultLanguage) audio.preferDefaultLanguage = preferDefaultLanguage;

    const subtitles = {};
    if (exactTrackSelectors.subtitleBurn.length) {
      subtitles.burnTrack = exactTrackSelectors.subtitleBurn[0];
    } else if (stripAll) {
      subtitles.stripAll = true;
    } else {
      appendSelectorRules(subtitles, "keepTracks", langCodesToRules(subKeepList));
      appendSelectorRules(subtitles, "keepTracks", exactTrackSelectors.subtitleKeep);
      appendSelectorRules(subtitles, "dropTracks", langCodesToRules(subDropList));
      appendSelectorRules(subtitles, "dropTracks", exactTrackSelectors.subtitleDrop);
    }

    const routing = {};
    if (routeProfile) routing.profile = routeProfile;
    if (routeThresholdMode) routing.routeThresholdMode = routeThresholdMode;

    const video = {};
    if (videoCodec) video.codec = videoCodec;
    if (videoContainer) video.container = videoContainer;
    if (videoEncodePreset) video.encodePreset = videoEncodePreset;
    if (videoEncodeLadder) video.encodeLadder = videoEncodeLadder;

    const hasAudio    = Object.keys(audio).length > 0;
    const hasSubs     = Object.keys(subtitles).length > 0;
    const hasRouting  = Object.keys(routing).length > 0;
    const hasVideo    = Object.keys(video).length > 0;
    if (!hasAudio && !hasSubs && !hasRouting && !hasVideo) return null;  // nothing set

    const payload = { path: state.foCurrentPath };
    if (hasAudio)  payload.audio     = audio;
    if (hasSubs)   payload.subtitles = subtitles;
    if (hasRouting) payload.routing  = routing;
    if (hasVideo)   payload.video    = video;
    return payload;
  }

  function drawerFieldHasExactTrackSelectors(fieldKey, exactTrackSelectors) {
    if (fieldKey === "audioKeepLanguages") return exactTrackSelectors.audioKeep.length > 0;
    if (fieldKey === "audioDropLanguages") return exactTrackSelectors.audioDrop.length > 0;
    if (fieldKey === "subtitleKeepLanguages") return exactTrackSelectors.subtitleKeep.length > 0;
    if (fieldKey === "subtitleDropLanguages") return exactTrackSelectors.subtitleDrop.length > 0;
    if (fieldKey === "subtitleBurnTrack") return exactTrackSelectors.subtitleBurn.length > 0;
    return false;
  }

  function drawerFieldIsNeutral(fieldKey) {
    const exactTrackSelectors = collectExactTrackSelectorsFromControls();
    if (drawerFieldHasExactTrackSelectors(fieldKey, exactTrackSelectors)) return false;
    if (fieldKey === "audioKeepLanguages") return parseLangList(byId("fo-audio-keep-langs")?.value).length === 0;
    if (fieldKey === "audioDropLanguages") return parseLangList(byId("fo-audio-drop-langs")?.value).length === 0;
    if (fieldKey === "audioMaxChannels") return String(byId("fo-audio-max-channels")?.value || "").trim() === "";
    if (fieldKey === "audioPreferDefaultLanguage") return String(byId("fo-audio-prefer-default-language")?.value || "").trim() === "";
    if (fieldKey === "subtitleKeepLanguages") return parseLangList(byId("fo-sub-keep-langs")?.value).length === 0;
    if (fieldKey === "subtitleDropLanguages") return parseLangList(byId("fo-sub-drop-langs")?.value).length === 0;
    if (fieldKey === "subtitleBurnTrack") return exactTrackSelectors.subtitleBurn.length === 0;
    if (fieldKey === "subtitleStripAll") return !byId("fo-sub-strip-all")?.checked;
    if (ROUTE_FIELD_KEYS.includes(fieldKey)) {
      const controlId = ROUTE_FIELD_CONFIG[fieldKey]?.controlId;
      const control = controlId ? byId(controlId) : null;
      return String(control?.value || "").trim() === "";
    }
    return false;
  }

  function collectFileOverrideFieldsToClearOnSave() {
    const sources = isPlainObject(state.foLastEffectivePayload?.sources) ? state.foLastEffectivePayload.sources : {};
    const paths = Object.keys(DRAWER_FIELD_PATHS)
      .filter((fieldKey) => {
        const fieldPath = DRAWER_FIELD_PATHS[fieldKey];
        return (
          fieldPath
          && sources[fieldPath] === "file_override"
          && drawerFieldIsNeutral(fieldKey)
        );
      })
      .map((fieldKey) => DRAWER_FIELD_PATHS[fieldKey]);
    Object.keys(DRAWER_FIELD_PATHS).forEach((fieldKey) => {
      const fieldPath = DRAWER_FIELD_PATHS[fieldKey];
      if (!fieldPath || !state.foPendingClearFieldPaths?.has?.(fieldPath)) return;
      if (drawerFieldIsNeutral(fieldKey)) paths.push(fieldPath);
    });
    return Array.from(new Set(paths));
  }

  function neutralizeDrawerField(fieldKey) {
    const inputIds = {
      audioKeepLanguages: "fo-audio-keep-langs",
      audioDropLanguages: "fo-audio-drop-langs",
      audioMaxChannels: "fo-audio-max-channels",
      audioPreferDefaultLanguage: "fo-audio-prefer-default-language",
      subtitleKeepLanguages: "fo-sub-keep-langs",
      subtitleDropLanguages: "fo-sub-drop-langs",
    };
    const inputId = inputIds[fieldKey];
    if (inputId) {
      const control = byId(inputId);
      if (control) control.value = "";
    }
    if (fieldKey === "subtitleStripAll") {
      const control = byId("fo-sub-strip-all");
      if (control) control.checked = false;
    }
    if (ROUTE_FIELD_KEYS.includes(fieldKey)) {
      const control = routeControlElement(fieldKey);
      if (control) control.value = "";
    }
  }

  function stageUseSavedPolicyField(fieldKey) {
    const fieldPath = DRAWER_FIELD_PATHS[fieldKey];
    if (!fieldPath) {
      setStatus("Cannot stage saved policy for this override field.", "error");
      return false;
    }
    if (!state.foCurrentPath) {
      setStatus("No file selected.", "warning");
      return false;
    }
    neutralizeDrawerField(fieldKey);
    state.foPendingClearFieldPaths.add(fieldPath);
    if (fieldKey === "subtitleBurnTrack") ctx.tracks.resetExactTrackActionsForField(fieldKey);
    if (["audioKeepLanguages", "audioDropLanguages", "subtitleKeepLanguages", "subtitleDropLanguages"].includes(fieldKey)) {
      ctx.tracks.resetExactTrackActionsForField(fieldKey);
    }
    setDrawerFieldOverridden(fieldKey, false);
    syncSubFilterFields();
    syncRouteOverrideDisclosure();
    if (ROUTE_FIELD_KEYS.includes(fieldKey)) ctx.routePreview.scheduleRoutePreviewFromCurrentForm();
    syncDrawerDirtyState();
    setDrawerUseInheritedAvailable(fieldKey, true);
    setStatus("Saved policy staged locally. Use Save Override to persist this field clear, or close to discard.", "warning");
    return true;
  }

  function collectRouteVideoFieldsToClearOnSave() {
    return collectFileOverrideFieldsToClearOnSave().filter((fieldPath) => (
      String(fieldPath || "").startsWith("routing.")
      || String(fieldPath || "").startsWith("video.")
    ));
  }

  function fieldPathsIncludeRouteVideo(fieldPaths) {
    return Array.isArray(fieldPaths) && fieldPaths.some((fieldPath) => (
      String(fieldPath || "").startsWith("routing.")
      || String(fieldPath || "").startsWith("video.")
    ));
  }

  function appendSelectorRules(target, key, rules) {
    if (!rules.length) return;
    target[key] = Array.isArray(target[key]) ? target[key].concat(rules) : rules.slice();
  }

    return {
      drawerChoiceLabel,
      normalizeRouteChoiceOptions,
      populateRouteSelectOptions,
      getDrawerLibraryDefaults,
      fileOverrideEffectiveSourceLabel,
      savedPolicyButtonText,
      savedPolicyOptionText,
      updateRouteBlankOptions,
      renderDrawerInheritedDefaults,
      drawerDefaultsFromEffectivePayload,
      applyFileOverrideEffectivePayload,
      clearDrawerUseInheritedButtons,
      renderDrawerUseInheritedButtons,
      setDrawerCommandButtonsDisabled,
      drawerFormSignature,
      syncDrawerDirtyState,
      markDrawerClean,
      handleDrawerFormChanged,
      confirmDiscardDrawerChanges,
      toggleRouteOverrideDisclosure,
      syncRouteOverrideDisclosure,
      clearDrawerOverrideMarkers,
      renderDrawerOverrideMarkers,
      clearDrawerForm,
      selectedSubtitleBurnControls,
      syncSubFilterFields,
      populateDrawerForm,
      buildOverridePayload,
      drawerFieldIsNeutral,
      stageUseSavedPolicyField,
      collectFileOverrideFieldsToClearOnSave,
      collectRouteVideoFieldsToClearOnSave,
      fieldPathsIncludeRouteVideo,
    };
  }

  window.__queueFileOverridesDrawerFormModule = { createFileOverridesDrawerFormModule };
})();
