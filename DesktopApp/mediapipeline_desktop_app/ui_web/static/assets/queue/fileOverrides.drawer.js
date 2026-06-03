// queue/fileOverrides.drawer.js
// Split child of queueView.js. Loaded after queueView.js so it can
// register the drawer opener with the queue table slice.

/* =============================================================================
   S80 — Per-File Settings Drawer  (Phase 3)
   Manages the slide-in drawer for per-file audio/subtitle overrides.
   API: GET/POST /api/queue/file-overrides
   ============================================================================= */
(function initFileSettingsDrawerModule() {
  const FILE_OVERRIDES_ROUTE = "/api/queue/file-overrides";
  const FILE_OVERRIDES_EFFECTIVE_ROUTE = "/api/queue/file-overrides/effective";
  const FILE_OVERRIDES_TRACKS_ROUTE = "/api/queue/file-overrides/tracks";

  // Currently-open source path
  let foCurrentPath = "";
  let foCurrentItem = null;
  let fileSettingsDrawerTrigger = null;
  let foLastEffectivePayload = null;
  let foExactTrackOverrideEntry = null;
  let foExactTrackWarnings = [];
  let foUnmatchedExactSelectors = emptyExactSelectorState();

  const DRAWER_FIELD_HINT_IDS = {
    audioKeepLanguages: "fo-audio-keep-langs-inherited",
    audioDropLanguages: "fo-audio-drop-langs-inherited",
    audioMaxChannels: "fo-audio-max-channels-inherited",
    audioPreferDefaultLanguage: "fo-audio-prefer-default-language-inherited",
    subtitleKeepLanguages: "fo-sub-keep-langs-inherited",
    subtitleDropLanguages: "fo-sub-drop-langs-inherited",
    subtitleStripAll: "fo-sub-strip-all-inherited",
    routeProfile: "fo-route-profile-inherited",
    videoContainer: "fo-video-container-inherited",
    videoCodec: "fo-video-codec-inherited",
    videoEncodePreset: "fo-video-encode-preset-inherited",
    videoEncodeLadder: "fo-video-encode-ladder-inherited",
    routingRouteThresholdMode: "fo-route-threshold-mode-inherited",
  };
  const DRAWER_FIELD_PATHS = {
    audioKeepLanguages: "audio.keepTracks",
    audioDropLanguages: "audio.dropTracks",
    audioMaxChannels: "audio.maxChannels",
    audioPreferDefaultLanguage: "audio.preferDefaultLanguage",
    subtitleKeepLanguages: "subtitles.keepTracks",
    subtitleDropLanguages: "subtitles.dropTracks",
    subtitleStripAll: "subtitles.stripAll",
    routeProfile: "routing.profile",
    routingRouteThresholdMode: "routing.routeThresholdMode",
    videoCodec: "video.codec",
    videoContainer: "video.container",
    videoEncodePreset: "video.encodePreset",
    videoEncodeLadder: "video.encodeLadder",
  };
  const DRAWER_FIELD_CONFIG = {
    audioKeepLanguages: { settingKey: "PreferredDefaultAudioLanguages", groups: ["audio", "effective_audio"] },
    audioDropLanguages: {},
    audioMaxChannels: { settingKey: "AudioMaxChannels", groups: ["audio", "effective_audio"], unit: "channels" },
    audioPreferDefaultLanguage: { settingKey: "PreferredDefaultAudioLanguages", groups: ["audio", "effective_audio"], scalarLanguage: true },
    subtitleKeepLanguages: { settingKey: "SubKeepLanguages", groups: ["subtitles", "effective_subtitles"] },
    subtitleDropLanguages: {},
    subtitleStripAll: {},
    routeProfile: { settingKey: "RoutingProfile", groups: ["editor", "effective_editor"] },
    routingRouteThresholdMode: { settingKey: "RouteThresholdMode", groups: ["editor", "effective_editor"] },
    videoCodec: { settingKey: "VideoCodec", groups: ["video", "effective_video"] },
    videoContainer: { settingKey: "OutputContainer", groups: ["video", "effective_video"] },
    videoEncodePreset: { settingKey: "EncodeTuningPreset", groups: ["video", "effective_video"] },
    videoEncodeLadder: { settingKey: "EncodeLadder", groups: ["video", "effective_video"] },
  };
  const ROUTE_FIELD_CONFIG = {
    routeProfile: { controlId: "fo-route-profile", section: "routing", payloadKey: "profile" },
    routingRouteThresholdMode: { controlId: "fo-route-threshold-mode", section: "routing", payloadKey: "routeThresholdMode" },
    videoCodec: { controlId: "fo-video-codec", section: "video", payloadKey: "codec" },
    videoContainer: { controlId: "fo-video-container", section: "video", payloadKey: "container" },
    videoEncodePreset: { controlId: "fo-video-encode-preset", section: "video", payloadKey: "encodePreset" },
    videoEncodeLadder: { controlId: "fo-video-encode-ladder", section: "video", payloadKey: "encodeLadder" },
  };
  const ROUTE_FIELD_KEYS = Object.keys(ROUTE_FIELD_CONFIG);
  const ROUTE_FORCE_VALUES = new Set(["auto", "encode", "remux", "transcode"]);
  const TRACK_ACTION_FIELD_PATHS = {
    audio: { keep: "audio.keepTracks", drop: "audio.dropTracks" },
    subtitle: { keep: "subtitles.keepTracks", drop: "subtitles.dropTracks" },
  };
  const DRAWER_FOCUSABLE_SELECTOR = [
    "a[href]",
    "button",
    "input",
    "select",
    "textarea",
    "[tabindex]:not([tabindex=\"-1\"])",
  ].join(",");

  // ---------------------------------------------------------------------------
  // Helpers
  // ---------------------------------------------------------------------------

  /** Split "eng, jpn , " into ["eng","jpn"] */
  function parseLangList(text) {
    return (text || "")
      .split(",")
      .map((s) => s.trim().toLowerCase())
      .filter(Boolean);
  }

  /** Build a keepTracks/dropTracks rule array from a list of lang codes */
  function langCodesToRules(langs) {
    return langs.map((lang) => ({ language: lang }));
  }

  function selectorStreamIndex(rule) {
    if (!isPlainObject(rule)) return null;
    const raw = rule.streamIndex ?? rule.stream_index ?? rule.trackIndex ?? rule.track_index ?? rule.index;
    const value = Number(raw);
    return Number.isInteger(value) && value >= 0 ? value : null;
  }

  function isExactTrackSelector(rule) {
    return selectorStreamIndex(rule) !== null;
  }

  /** Populate a lang-list input from an array of rule objects */
  function rulesToLangInput(rules) {
    if (!Array.isArray(rules) || !rules.length) return "";
    return rules
      .filter((rule) => !isExactTrackSelector(rule))
      .map((r) => r.language || "")
      .filter(Boolean)
      .join(", ");
  }

  function byId(id) { return document.getElementById(id); }
  function setStatus(msg) {
    const el = byId("fo-drawer-status");
    if (el) el.textContent = msg;
  }

  function isPlainObject(value) {
    return value && typeof value === "object" && !Array.isArray(value);
  }

  function emptyExactSelectorState() {
    return {
      audioKeep: [],
      audioDrop: [],
      subtitleKeep: [],
      subtitleDrop: [],
    };
  }

  function hasOwnValue(source, key) {
    return isPlainObject(source) && Object.prototype.hasOwnProperty.call(source, key);
  }

  function backendErrorMessage(result, fallback = "Unknown error.") {
    const message = String(result?.message || fallback).trim();
    const errors = Array.isArray(result?.errors)
      ? result.errors.map((error) => String(error || "").trim()).filter(Boolean)
      : [];
    if (!errors.length) return message;
    return `${message} ${errors.join(" ")}`;
  }

  function currentFileOverridePathLooksFileLike() {
    const path = String(foCurrentPath || "").trim();
    if (!path || /[\\/]$/.test(path)) return false;
    const leaf = path.split(/[\\/]/).pop() || "";
    return /\.[A-Za-z0-9]{1,12}$/.test(leaf);
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
    inherit.textContent = "Inherit";
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

  const __fileOverridesRoutePreviewMod = window.__queueFileOverridesRoutePreviewModule || {};
  delete window.__queueFileOverridesRoutePreviewModule;
  const _fileOverridesRoutePreview = typeof __fileOverridesRoutePreviewMod.createFileOverridesRoutePreviewModule === "function"
    ? __fileOverridesRoutePreviewMod.createFileOverridesRoutePreviewModule({
      apiPost: typeof apiPost === "function" ? apiPost : window.apiPost,
      backendErrorMessage,
      buildOverridePayload: () => buildOverridePayload(),
      byId,
      documentRef: document,
      getCurrentPath: () => foCurrentPath,
      isPlainObject,
      normalizeRouteChoiceOptions,
      populateRouteSelectOptions,
      routeFieldConfig: ROUTE_FIELD_CONFIG,
      routeFieldKeys: ROUTE_FIELD_KEYS,
      routeForceValues: ROUTE_FORCE_VALUES,
      setStatus,
    })
    : {};
  const {
    clearProcessingRouteControls = function () {},
    clearRoutePreviewStatus = function () {},
    ensureRoutePreviewAllowsSave = async function () { return true; },
    loadRoutePreviewForPayload = async function () { return { ok: true }; },
    payloadHasRouteVideoOverride = function (payload) { return Boolean(payload && (isPlainObject(payload.routing) || isPlainObject(payload.video))); },
    refreshRoutePreviewFromCurrentForm = async function () {},
    renderProcessingRouteControls = function () {},
    renderRoutePreviewFromEffectivePayload = function () {},
    routeControlElement = function () { return null; },
    scheduleRoutePreviewFromCurrentForm = function () {},
  } = _fileOverridesRoutePreview;

  const __fileOverridesFolderPreviewMod = window.__queueFileOverridesFolderPreviewModule || {};
  delete window.__queueFileOverridesFolderPreviewModule;
  const _fileOverridesFolderPreview = typeof __fileOverridesFolderPreviewMod.createFileOverridesFolderPreviewModule === "function"
    ? __fileOverridesFolderPreviewMod.createFileOverridesFolderPreviewModule({
      apiGet: typeof apiGet === "function" ? apiGet : window.apiGet,
      apiPost: typeof apiPost === "function" ? apiPost : window.apiPost,
      appendCommandResult: typeof appendCommandResult === "function" ? appendCommandResult : window.appendCommandResult,
      backendErrorMessage,
      byId,
      clearElementChildren,
      closeFileSettingsDrawer: () => closeFileSettingsDrawer(),
      currentItem: () => foCurrentItem,
      currentPath: () => foCurrentPath,
      documentRef: document,
      exactSelectorForTrack,
      fileOverridesRoute: FILE_OVERRIDES_ROUTE,
      hasOwnValue,
      isPlainObject,
      langCodesToRules,
      loadFileOverrideEffectiveForPath: (path, item) => loadFileOverrideEffectiveForPath(path, item),
      parseLangList,
      refreshAll: typeof refreshAll === "function" ? refreshAll : window.refreshAll,
      setStatus,
      setTrackText,
    })
    : {};
  const {
    clearFolderRuleManagementPanel = function () {},
    clearFolderRulePreviewPanel = function () {},
    handleFolderPreviewScopeChange = function () {},
    handleFolderRuleManagementClick = function () {},
    invalidateFolderPreviewAfterRuleChange = function () {},
    loadFolderRulesForDrawer = async function () {},
    openFolderRulePreviewPanel = async function () {},
    openLibrarySettingsFromFolderHandoff = function () {},
    saveFolderRuleForPreview = async function () {},
    syncFolderPreviewSaveState = function () {},
  } = _fileOverridesFolderPreview;

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
    if (source === "unavailable") return "unavailable";
    return "";
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
    const inheritedPrefix = inheritedSourceLabel === "Global" ? "Global default" : "Library default";
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
      el.textContent = "Library default: unavailable";
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
      status.textContent = "Library defaults unavailable for this queue row.";
      return;
    }
    const fieldValues = Object.values(defaults.fields || {}).filter((field) => field?.available);
    if (fieldValues.length) {
      status.textContent = `Inherited defaults shown from ${defaults.sourceLabel}. Unavailable field hints were not reported on the queue row.`;
    } else {
      status.textContent = `Library defaults unavailable for these drawer fields; the row only reported ${defaults.sourceLabel}.`;
    }
  }

  function drawerEffectiveSourceLabel(payload, item) {
    const library = isPlainObject(payload?.library) ? payload.library : {};
    const name = String(library.name || library.id || "").trim();
    if (library.available) return name ? `Library ${name}` : "Library";
    const inherited = isPlainObject(payload?.inherited) ? Object.values(payload.inherited) : [];
    if (inherited.some((field) => field?.source === "global_default")) return "Global defaults";
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
    foLastEffectivePayload = payload;
    foExactTrackOverrideEntry = payload.file_override_scope === "file" && isPlainObject(payload.file_override)
      ? payload.file_override
      : null;
    renderProcessingRouteControls(payload);
    renderDrawerInheritedDefaults(drawerDefaultsFromEffectivePayload(payload, item));
    if (isPlainObject(payload.file_override)) {
      populateDrawerForm(payload.file_override);
    } else {
      clearDrawerForm({ resetRouteControls: false, resetTrackMetadata: false });
    }
    renderDrawerTrackMetadata(payload);
    renderDrawerUseInheritedButtons(payload);
    renderRoutePreviewFromEffectivePayload(payload);
    return true;
  }

  function clearDrawerUseInheritedButtons() {
    document.querySelectorAll("[data-fo-use-inherited]").forEach((button) => {
      button.hidden = true;
      button.disabled = true;
    });
  }

  function setDrawerUseInheritedAvailable(fieldKey, isAvailable) {
    const button = document.querySelector(`[data-fo-use-inherited="${fieldKey}"]`);
    if (!button) return;
    button.hidden = !isAvailable;
    button.disabled = !isAvailable;
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

  function isHTMLElement(value) {
    if (!value || typeof value !== "object") return false;
    if (typeof HTMLElement === "function") return value instanceof HTMLElement;
    return value.nodeType === 1;
  }

  function fileSettingsTriggerFromOptions(options) {
    if (isHTMLElement(options?.trigger)) return options.trigger;
    return isHTMLElement(document.activeElement) ? document.activeElement : null;
  }

  function isFileSettingsDrawerOpen() {
    const drawer = byId("fo-drawer");
    return Boolean(drawer && !drawer.hidden);
  }

  function fileSettingsElementIsHidden(element) {
    if (!element || element.hidden) return true;
    if (typeof element.closest === "function" && element.closest("[hidden]")) return true;
    if (typeof window.getComputedStyle === "function") {
      const style = window.getComputedStyle(element);
      if (style.display === "none" || style.visibility === "hidden") return true;
    }
    return false;
  }

  function getFileSettingsDrawerFocusableElements() {
    const drawer = byId("fo-drawer");
    if (!drawer || drawer.hidden || typeof drawer.querySelectorAll !== "function") return [];
    return Array.from(drawer.querySelectorAll(DRAWER_FOCUSABLE_SELECTOR)).filter((element) => {
      if (!isHTMLElement(element)) return false;
      if (element.disabled) return false;
      if (element.getAttribute("aria-hidden") === "true") return false;
      return !fileSettingsElementIsHidden(element);
    });
  }

  function focusInitialFileSettingsDrawerControl() {
    const drawer = byId("fo-drawer");
    if (!drawer || drawer.hidden) return;
    const focusable = getFileSettingsDrawerFocusableElements();
    const target = focusable[0] || drawer;
    if (target && typeof target.focus === "function") target.focus();
  }

  function restoreFileSettingsDrawerFocus() {
    const trigger = fileSettingsDrawerTrigger;
    fileSettingsDrawerTrigger = null;
    if (
      trigger &&
      trigger.isConnected &&
      typeof trigger.focus === "function" &&
      !trigger.disabled
    ) {
      trigger.focus();
    }
  }

  function handleFileSettingsDrawerKeydown(event) {
    if (!isFileSettingsDrawerOpen()) return;
    if (event.key === "Escape") {
      closeFileSettingsDrawer();
      return;
    }
    if (event.key !== "Tab") return;
    const drawer = byId("fo-drawer");
    const focusable = getFileSettingsDrawerFocusableElements();
    if (!focusable.length) {
      event.preventDefault();
      if (drawer && typeof drawer.focus === "function") drawer.focus();
      return;
    }
    const first = focusable[0];
    const last = focusable[focusable.length - 1];
    const active = document.activeElement;
    if (event.shiftKey && active === first) {
      event.preventDefault();
      last.focus();
    } else if (!event.shiftKey && active === last) {
      event.preventDefault();
      first.focus();
    }
  }

  try {
    if (typeof window.__queueSetFileDrawer === "function") {
      window.__queueSetFileDrawer(openFileSettingsDrawer);
    }
  } finally {
    delete window.__queueSetFileDrawer;
  }

  // ---------------------------------------------------------------------------
  // Drawer open / close
  // ---------------------------------------------------------------------------

  function openFileSettingsDrawer(item, options = {}) {
    const queueItem = item || {};
    fileSettingsDrawerTrigger = fileSettingsTriggerFromOptions(options);
    const path = queueItem.source_path || "";
    foCurrentPath = path;
    foCurrentItem = queueItem;
    foLastEffectivePayload = null;

    const titleEl = byId("fo-drawer-title");
    const pathEl  = byId("fo-drawer-path");
    const name    = queueItem.display_name || queueItem.relative_path || path || "Unknown";
    if (titleEl) titleEl.textContent = "File Settings — " + (name.length > 40 ? "…" + name.slice(-40) : name);
    if (pathEl) pathEl.textContent = path;

    clearDrawerForm();
    clearFolderRulePreviewPanel();
    clearFolderRuleManagementPanel();
    renderDrawerInheritedDefaults(getDrawerLibraryDefaults(queueItem));
    setStatus("Loading current override…");
    loadFileOverrideForPath(path);
    loadFileOverrideEffectiveForPath(path, queueItem);

    const overlay = byId("fo-overlay");
    const drawer  = byId("fo-drawer");
    if (overlay) { overlay.hidden = false; overlay.removeAttribute("aria-hidden"); }
    if (drawer)  { drawer.hidden  = false; }

    setTimeout(focusInitialFileSettingsDrawerControl, 50);
  }

  function closeFileSettingsDrawer() {
    const overlay = byId("fo-overlay");
    const drawer  = byId("fo-drawer");
    if (overlay) { overlay.hidden = true; overlay.setAttribute("aria-hidden", "true"); }
    if (drawer)  { drawer.hidden  = true; }
    clearDrawerOverrideMarkers();
    clearDrawerUseInheritedButtons();
    clearDrawerTrackMetadata();
    clearProcessingRouteControls();
    clearFolderRulePreviewPanel();
    clearFolderRuleManagementPanel();
    foLastEffectivePayload = null;
    foExactTrackOverrideEntry = null;
    foExactTrackWarnings = [];
    foUnmatchedExactSelectors = emptyExactSelectorState();
    foCurrentPath = "";
    foCurrentItem = null;
    restoreFileSettingsDrawerFocus();
  }

  // ---------------------------------------------------------------------------
  // Form helpers
  // ---------------------------------------------------------------------------

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
    foExactTrackOverrideEntry = null;
    resetExactTrackControls();
    foUnmatchedExactSelectors = emptyExactSelectorState();
    foExactTrackWarnings = [];
    if (resetTrackMetadata) clearDrawerTrackMetadata();
    if (resetRouteControls) clearProcessingRouteControls();
    else clearRoutePreviewStatus();
    syncSubFilterFields();
  }

  function syncSubFilterFields() {
    const stripAll = byId("fo-sub-strip-all");
    const fields   = byId("fo-sub-filter-fields");
    const stripAllChecked = Boolean(stripAll && stripAll.checked);
    if (!fields) return;
    if (stripAllChecked) {
      fields.style.opacity = "0.4";
      fields.style.pointerEvents = "none";
    } else {
      fields.style.opacity = "";
      fields.style.pointerEvents = "";
    }
    document.querySelectorAll('[data-fo-track-action][data-fo-track-kind="subtitle"]').forEach((control) => {
      const hasIndex = control.dataset.foTrackIndexAvailable !== "false";
      control.disabled = stripAllChecked || !hasIndex;
      if (stripAllChecked) control.value = "";
    });
  }

  function populateDrawerForm(entry) {
    // entry = { audio: {...}, subtitles: {...} } or null
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
    if (stripAll) subtitles.stripAll = true;
    if (!stripAll) {
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

    const payload = { path: foCurrentPath };
    if (hasAudio)  payload.audio     = audio;
    if (hasSubs)   payload.subtitles = subtitles;
    if (hasRouting) payload.routing  = routing;
    if (hasVideo)   payload.video    = video;
    return payload;
  }

  function trackActionBucket(kind, action) {
    if (kind === "audio" && action === "keep") return "audioKeep";
    if (kind === "audio" && action === "drop") return "audioDrop";
    if (kind === "subtitle" && action === "keep") return "subtitleKeep";
    if (kind === "subtitle" && action === "drop") return "subtitleDrop";
    return "";
  }

  function exactSelectorRules(entry, kind, action) {
    const sectionKey = kind === "audio" ? "audio" : "subtitles";
    const fieldKey = action === "keep" ? "keepTracks" : "dropTracks";
    const section = isPlainObject(entry?.[sectionKey]) ? entry[sectionKey] : {};
    const rules = Array.isArray(section[fieldKey]) ? section[fieldKey] : [];
    return rules.filter((rule) => isPlainObject(rule) && isExactTrackSelector(rule));
  }

  function normalizedTrackLanguage(value) {
    const text = String(value ?? "").trim().toLowerCase();
    return text || "und";
  }

  function normalizedTrackCodec(value) {
    return String(value ?? "").trim().toLowerCase();
  }

  function trackTitleValue(value) {
    return String(value ?? "").trim();
  }

  function globPatternMatches(value, pattern) {
    const text = String(value || "").toLowerCase();
    const rawPattern = String(pattern || "").toLowerCase();
    if (!rawPattern) return true;
    const escaped = rawPattern.replace(/[.+^${}()|[\]\\]/g, "\\$&").replace(/\*/g, ".*").replace(/\?/g, ".");
    return new RegExp(`^${escaped}$`).test(text);
  }

  function exactSelectorMatchesTrack(selector, track, kind) {
    if (!isPlainObject(selector) || !isPlainObject(track)) return false;
    const selectorIndex = selectorStreamIndex(selector);
    if (selectorIndex === null || selectorIndex !== trackStreamIndex(track)) return false;
    if (hasOwnValue(selector, "language") && normalizedTrackLanguage(selector.language) !== normalizedTrackLanguage(track.language)) return false;
    if (hasOwnValue(selector, "codec") && normalizedTrackCodec(selector.codec) !== normalizedTrackCodec(track.codec)) return false;
    if (hasOwnValue(selector, "title") && !globPatternMatches(trackTitleValue(track.title), selector.title)) return false;
    if (kind === "audio" && hasOwnValue(selector, "channels")) {
      const selectorChannels = Number(selector.channels);
      const trackChannels = Number(track.channels);
      if (!Number.isFinite(selectorChannels) || !Number.isFinite(trackChannels) || selectorChannels !== trackChannels) return false;
    }
    if (kind === "subtitle" && hasOwnValue(selector, "forced") && Boolean(selector.forced) !== Boolean(track.forced)) return false;
    return true;
  }

  function exactSelectorForTrack(track, kind) {
    const streamIndex = trackStreamIndex(track);
    if (streamIndex === null) return null;
    const selector = { streamIndex };
    const language = normalizedTrackLanguage(track.language);
    if (language) selector.language = language;
    const codec = normalizedTrackCodec(track.codec);
    if (codec) selector.codec = codec;
    const title = trackTitleValue(track.title);
    if (title) selector.title = title;
    if (kind === "audio") {
      const channels = Number(track.channels);
      if (Number.isInteger(channels) && channels > 0) selector.channels = channels;
    } else if (typeof track.forced === "boolean") {
      selector.forced = Boolean(track.forced);
    }
    return selector;
  }

  function trackExactActionForTrack(track, kind) {
    const entry = foExactTrackOverrideEntry;
    if (!isPlainObject(entry)) return "";
    const keepRules = exactSelectorRules(entry, kind, "keep");
    const dropRules = exactSelectorRules(entry, kind, "drop");
    const matchesKeep = keepRules.some((rule) => exactSelectorMatchesTrack(rule, track, kind));
    const matchesDrop = dropRules.some((rule) => exactSelectorMatchesTrack(rule, track, kind));
    if (matchesDrop) return "drop";
    if (matchesKeep) return "keep";
    return "";
  }

  function computeExactTrackWarningsForMetadata(metadata) {
    const entry = foExactTrackOverrideEntry;
    foUnmatchedExactSelectors = emptyExactSelectorState();
    if (!isPlainObject(entry)) return [];
    const available = Boolean(metadata?.available || metadata?.probe_available);
    if (!available) {
      return ["Saved exact-track override cannot be displayed because track metadata is unavailable."];
    }
    const warnings = [];
    const groups = [
      { kind: "audio", action: "keep", tracks: Array.isArray(metadata.audio_tracks) ? metadata.audio_tracks : [] },
      { kind: "audio", action: "drop", tracks: Array.isArray(metadata.audio_tracks) ? metadata.audio_tracks : [] },
      { kind: "subtitle", action: "keep", tracks: Array.isArray(metadata.subtitle_tracks) ? metadata.subtitle_tracks : [] },
      { kind: "subtitle", action: "drop", tracks: Array.isArray(metadata.subtitle_tracks) ? metadata.subtitle_tracks : [] },
    ];
    groups.forEach(({ kind, action, tracks }) => {
      exactSelectorRules(entry, kind, action).forEach((selector) => {
        const streamIndex = selectorStreamIndex(selector);
        const matched = tracks.some((track) => isPlainObject(track) && exactSelectorMatchesTrack(selector, track, kind));
        if (matched) return;
        const bucket = trackActionBucket(kind, action);
        if (bucket) foUnmatchedExactSelectors[bucket].push(selector);
        warnings.push(
          `Saved exact-track override no longer matches detected track metadata: ${TRACK_ACTION_FIELD_PATHS[kind][action]} stream ${streamIndex ?? "?"}.`
        );
      });
    });
    const seen = new Set();
    groups.forEach(({ kind, tracks }) => {
      tracks.forEach((track) => {
        if (!isPlainObject(track)) return;
        const streamIndex = trackStreamIndex(track);
        if (streamIndex === null) return;
        const key = `${kind}:${streamIndex}`;
        if (seen.has(key)) return;
        seen.add(key);
        const matchesKeep = exactSelectorRules(entry, kind, "keep").some((rule) => exactSelectorMatchesTrack(rule, track, kind));
        const matchesDrop = exactSelectorRules(entry, kind, "drop").some((rule) => exactSelectorMatchesTrack(rule, track, kind));
        if (matchesKeep && matchesDrop) {
          warnings.push(`Stream ${streamIndex} is saved as both Keep and Drop; Drop wins during processing.`);
        }
      });
    });
    return Array.from(new Set(warnings));
  }

  function resetExactTrackControls() {
    document.querySelectorAll("[data-fo-track-action]").forEach((control) => {
      control.value = "";
    });
  }

  function resetExactTrackActionsForField(fieldKey) {
    const targetPath = DRAWER_FIELD_PATHS[fieldKey];
    if (!targetPath) return;
    document.querySelectorAll("[data-fo-track-action]").forEach((control) => {
      const kind = control.dataset.foTrackKind || "";
      const action = control.dataset.foTrackActionKind || "";
      if (TRACK_ACTION_FIELD_PATHS[kind]?.[action] === targetPath) control.value = "";
    });
    const bucket = trackActionBucket(
      targetPath.startsWith("audio.") ? "audio" : "subtitle",
      targetPath.endsWith(".keepTracks") ? "keep" : "drop",
    );
    if (bucket) foUnmatchedExactSelectors[bucket] = [];
    foExactTrackWarnings = foExactTrackWarnings.filter((message) => !String(message || "").includes(targetPath));
  }

  function collectExactTrackSelectorsFromControls() {
    const selectors = emptyExactSelectorState();
    if (!currentFileOverridePathLooksFileLike()) return selectors;
    document.querySelectorAll("[data-fo-track-action]").forEach((control) => {
      if (control.disabled) return;
      const action = String(control.value || "");
      if (action !== "keep" && action !== "drop") return;
      const kind = control.dataset.foTrackKind || "";
      const trackData = control.dataset.foTrackJson || "";
      let track = null;
      try { track = JSON.parse(trackData); } catch (_err) { track = null; }
      const selector = exactSelectorForTrack(track, kind);
      const bucket = trackActionBucket(kind, action);
      if (bucket && selector) selectors[bucket].push(selector);
    });
    Object.keys(foUnmatchedExactSelectors).forEach((bucket) => {
      selectors[bucket].push(...foUnmatchedExactSelectors[bucket]);
    });
    return selectors;
  }

  function appendSelectorRules(target, key, rules) {
    if (!rules.length) return;
    target[key] = Array.isArray(target[key]) ? target[key].concat(rules) : rules.slice();
  }

  function validateExactTrackSelectionsBeforeSave() {
    const selectedExactControl = Array.from(document.querySelectorAll("[data-fo-track-action]"))
      .some((control) => ["keep", "drop"].includes(String(control.value || "")));
    if (selectedExactControl && !currentFileOverridePathLooksFileLike()) {
      setStatus("Exact stream selectors can only be saved for a file path, not a folder or library scope.");
      return false;
    }
    if (foExactTrackWarnings.some((message) => message.includes("Saved exact-track override"))) {
      setStatus("Saved exact-track override cannot be safely resaved. Use inherited for the affected field before saving.");
      return false;
    }
    const selected = new Map();
    let conflict = "";
    document.querySelectorAll("[data-fo-track-action]").forEach((control) => {
      const action = String(control.value || "");
      if (action !== "keep" && action !== "drop") return;
      const kind = control.dataset.foTrackKind || "";
      const streamIndex = Number(control.dataset.foTrackStreamIndex);
      if (!kind || !Number.isInteger(streamIndex)) return;
      const key = `${kind}:${streamIndex}`;
      const previous = selected.get(key);
      if (previous && previous !== action) conflict = `${kind} stream ${streamIndex}`;
      selected.set(key, action);
    });
    if (conflict) {
      setStatus(`Choose either Keep or Drop for ${conflict}, not both.`);
      return false;
    }
    return true;
  }

  function trackTextValue(value, fallback = "Not reported") {
    const text = String(value ?? "").trim();
    return text || fallback;
  }

  function trackStreamIndex(track) {
    const raw = track?.stream_index ?? track?.index;
    const value = Number(raw);
    return Number.isFinite(value) ? value : null;
  }

  function setTrackText(id, text) {
    const el = byId(id);
    if (el) el.textContent = text;
  }

  function clearElementChildren(id) {
    const el = byId(id);
    if (el) el.replaceChildren();
  }

  function clearDrawerTrackMetadata(message = "Track metadata unavailable for this file.") {
    ["fo-audio-track-list", "fo-subtitle-track-list", "fo-track-warning-list"].forEach(clearElementChildren);
    setTrackText("fo-audio-track-count", "Unavailable");
    setTrackText("fo-subtitle-track-count", "Unavailable");
    setTrackText("fo-audio-track-status", message);
    setTrackText("fo-subtitle-track-status", message);
    foExactTrackWarnings = [];
    foUnmatchedExactSelectors = emptyExactSelectorState();
  }

  function createTrackBadge(label, tone = "") {
    const badge = document.createElement("span");
    badge.className = "fo-track-badge";
    badge.textContent = label;
    if (tone) badge.dataset.tone = tone;
    return badge;
  }

  function appendTrackDetail(container, label, value) {
    const detail = document.createElement("span");
    detail.className = "fo-track-detail";
    detail.textContent = `${label}: ${trackTextValue(value)}`;
    container.appendChild(detail);
  }

  function trackSelectionMarkerLabel(marker) {
    if (!isPlainObject(marker)) return "";
    const sourceLabel = fileOverrideEffectiveSourceLabel(marker.source || "") || String(marker.source || "").trim();
    const field = String(marker.field || "").trim();
    if (sourceLabel && field) return `${sourceLabel} ${field}`;
    return sourceLabel || field;
  }

  function trackPreviewState(preview, streamIndex) {
    if (!isPlainObject(preview) || streamIndex === null) return null;
    const kept = Array.isArray(preview.kept_stream_indexes) ? preview.kept_stream_indexes.map(Number) : [];
    const dropped = Array.isArray(preview.dropped_stream_indexes) ? preview.dropped_stream_indexes.map(Number) : [];
    const indexKey = String(streamIndex);
    if (dropped.includes(streamIndex)) {
      return {
        label: "Dropped",
        tone: "warning",
        marker: isPlainObject(preview.dropped_stream_sources) ? preview.dropped_stream_sources[indexKey] : null,
      };
    }
    if (kept.includes(streamIndex)) {
      return {
        label: "Kept",
        tone: "",
        marker: isPlainObject(preview.kept_stream_sources) ? preview.kept_stream_sources[indexKey] : null,
      };
    }
    return null;
  }

  function appendTrackFlags(container, track, kind, previewState) {
    if (previewState) {
      const markerLabel = trackSelectionMarkerLabel(previewState.marker);
      const label = markerLabel ? `${previewState.label} by ${markerLabel}` : previewState.label;
      container.appendChild(createTrackBadge(label, previewState.tone));
    }
    if (track.default) container.appendChild(createTrackBadge("Default"));
    if (track.forced) container.appendChild(createTrackBadge("Forced", "warning"));
    if (kind === "audio" && track.commentary) container.appendChild(createTrackBadge("Commentary", "warning"));
    if (track.hearing_impaired) container.appendChild(createTrackBadge("SDH"));
    if (kind === "subtitle" && track.image_based) container.appendChild(createTrackBadge("Image subtitle", "warning"));
    if (kind === "subtitle" && track.text_based) container.appendChild(createTrackBadge("Text subtitle"));
  }

  function createTrackActionControl(track, kind) {
    const streamIndex = trackStreamIndex(track);
    const wrapper = document.createElement("label");
    wrapper.className = "fo-track-action";
    const label = document.createElement("span");
    label.textContent = "File override";
    wrapper.appendChild(label);

    const select = document.createElement("select");
    select.className = "fo-track-action-select";
    select.dataset.foTrackAction = "true";
    select.dataset.foTrackKind = kind;
    select.dataset.foTrackStreamIndex = streamIndex === null ? "" : String(streamIndex);
    select.dataset.foTrackIndexAvailable = streamIndex === null ? "false" : "true";
    select.dataset.foTrackJson = JSON.stringify(track);
    select.setAttribute("aria-label", `Override action for ${kind === "audio" ? "audio" : "subtitle"} stream ${streamIndex ?? "unknown"}`);
    [
      ["", "Inherit"],
      ["keep", kind === "audio" ? "Keep this audio track" : "Keep this subtitle track"],
      ["drop", kind === "audio" ? "Drop this audio track" : "Drop this subtitle track"],
    ].forEach(([value, text]) => {
      const option = document.createElement("option");
      option.value = value;
      option.textContent = text;
      select.appendChild(option);
    });
    select.value = trackExactActionForTrack(track, kind);
    if (streamIndex === null) {
      select.disabled = true;
      select.title = "Track stream index unavailable; exact-track override cannot be saved for this row.";
    }
    wrapper.appendChild(select);
    return wrapper;
  }

  function createTrackRow(track, kind, preview) {
    const row = document.createElement("div");
    row.className = "fo-track-row";
    row.dataset.trackKind = kind;

    const streamIndex = trackStreamIndex(track);
    const previewState = trackPreviewState(preview, streamIndex);

    const summary = document.createElement("div");
    summary.className = "fo-track-summary";
    const title = document.createElement("strong");
    title.textContent = streamIndex === null ? "Stream ?" : `Stream ${streamIndex}`;
    summary.appendChild(title);
    const display = document.createElement("span");
    display.textContent = trackTextValue(track.display, `${trackTextValue(track.language, "und")} track`);
    summary.appendChild(display);
    row.appendChild(summary);

    const details = document.createElement("div");
    details.className = "fo-track-details";
    appendTrackDetail(details, "Language", trackTextValue(track.language, "und"));
    appendTrackDetail(details, "Title", track.title);
    appendTrackDetail(details, "Codec", track.codec);
    if (kind === "audio") {
      appendTrackDetail(details, "Channels", track.channels);
      appendTrackDetail(details, "Layout", track.channel_layout);
    }
    row.appendChild(details);

    const badges = document.createElement("div");
    badges.className = "fo-track-badges";
    appendTrackFlags(badges, track, kind, previewState);
    row.appendChild(badges);
    row.appendChild(createTrackActionControl(track, kind));
    return row;
  }

  function renderTrackGroup({ kind, tracks, preview, listId, countId, statusId }) {
    const list = byId(listId);
    if (list) list.replaceChildren();
    const count = tracks.length;
    setTrackText(countId, `${count} ${count === 1 ? "track" : "tracks"}`);
    if (!count) {
      setTrackText(statusId, kind === "audio" ? "No detected audio tracks were reported." : "No detected subtitle tracks were reported.");
      return;
    }
    setTrackText(statusId, "");
    if (!list) return;
    tracks.forEach((track) => {
      if (isPlainObject(track)) list.appendChild(createTrackRow(track, kind, preview));
    });
  }

  function trackWarningMessage(warning) {
    if (!isPlainObject(warning)) return String(warning || "").trim();
    const message = String(warning.message || "").trim();
    const field = String(warning.field || "").trim();
    if (!message) return "";
    return field ? `${field}: ${message}` : message;
  }

  function collectTrackWarnings(metadata, preview) {
    const warnings = [];
    const addWarning = (warning) => {
      const message = trackWarningMessage(warning);
      if (message) warnings.push(message);
    };
    (Array.isArray(metadata?.warnings) ? metadata.warnings : []).forEach(addWarning);
    (Array.isArray(preview?.audio?.warnings) ? preview.audio.warnings : []).forEach(addWarning);
    (Array.isArray(preview?.subtitles?.warnings) ? preview.subtitles.warnings : []).forEach(addWarning);
    (Array.isArray(metadata?.audio_tracks) ? metadata.audio_tracks : []).forEach((track) => {
      const index = trackStreamIndex(track);
      if (track?.commentary) warnings.push(`Audio stream ${index ?? "?"} appears to be commentary.`);
    });
    (Array.isArray(metadata?.subtitle_tracks) ? metadata.subtitle_tracks : []).forEach((track) => {
      const index = trackStreamIndex(track);
      if (track?.forced) warnings.push(`Subtitle stream ${index ?? "?"} is marked forced.`);
      if (track?.image_based) warnings.push(`Subtitle stream ${index ?? "?"} is image-based and may require OCR or burn-in review.`);
    });
    foExactTrackWarnings.forEach((message) => {
      const text = String(message || "").trim();
      if (text) warnings.push(text);
    });
    return Array.from(new Set(warnings));
  }

  function renderTrackWarnings(metadata, preview) {
    const list = byId("fo-track-warning-list");
    if (!list) return;
    list.replaceChildren();
    const warnings = collectTrackWarnings(metadata, preview);
    if (!warnings.length) return;
    const heading = document.createElement("p");
    heading.className = "fo-track-warning-heading";
    heading.textContent = "Track warnings";
    list.appendChild(heading);
    const warningList = document.createElement("ul");
    warnings.forEach((message) => {
      const item = document.createElement("li");
      item.className = "fo-track-warning";
      item.textContent = message;
      warningList.appendChild(item);
    });
    list.appendChild(warningList);
  }

  function renderDrawerTrackMetadata(payload) {
    const metadata = isPlainObject(payload?.track_metadata) ? payload.track_metadata : {};
    const preview = isPlainObject(payload?.track_selection_preview) ? payload.track_selection_preview : {};
    const available = Boolean(metadata.available || metadata.probe_available);
    foExactTrackWarnings = computeExactTrackWarningsForMetadata(metadata);
    if (!available) {
      const message = trackWarningMessage((Array.isArray(metadata.warnings) ? metadata.warnings : [])[0])
        || "Track metadata unavailable for this file.";
      clearDrawerTrackMetadata(message);
      foExactTrackWarnings = computeExactTrackWarningsForMetadata(metadata);
      renderTrackWarnings(metadata, preview);
      return;
    }
    const audioTracks = Array.isArray(metadata.audio_tracks) ? metadata.audio_tracks : [];
    const subtitleTracks = Array.isArray(metadata.subtitle_tracks) ? metadata.subtitle_tracks : [];
    renderTrackGroup({
      kind: "audio",
      tracks: audioTracks,
      preview: isPlainObject(preview.audio) ? preview.audio : {},
      listId: "fo-audio-track-list",
      countId: "fo-audio-track-count",
      statusId: "fo-audio-track-status",
    });
    renderTrackGroup({
      kind: "subtitle",
      tracks: subtitleTracks,
      preview: isPlainObject(preview.subtitles) ? preview.subtitles : {},
      listId: "fo-subtitle-track-list",
      countId: "fo-subtitle-track-count",
      statusId: "fo-subtitle-track-status",
    });
    renderTrackWarnings(metadata, preview);
    syncSubFilterFields();
  }

  function trackMetadataFromTracksPayload(payload) {
    const available = Boolean(payload?.probe_available);
    return {
      available,
      probe_available: available,
      probe_source: String(payload?.probe_source || (available ? "tracks_endpoint" : "unavailable")),
      audio_tracks: available && Array.isArray(payload?.audio_tracks) ? payload.audio_tracks : [],
      subtitle_tracks: available && Array.isArray(payload?.subtitle_tracks) ? payload.subtitle_tracks : [],
      warnings: Array.isArray(payload?.warnings) ? payload.warnings : [],
    };
  }


  // ---------------------------------------------------------------------------
  // API calls
  // ---------------------------------------------------------------------------

  async function loadFileOverrideForPath(path) {
    if (!path) { setStatus("No source path — cannot load override."); return; }
    try {
      const url  = FILE_OVERRIDES_ROUTE + "?path=" + encodeURIComponent(path);
      const data = await apiGet(url);
      if (data && data.entry) {
        populateDrawerForm(data.entry);
        setStatus("Override loaded.");
      } else {
        clearDrawerForm({
          resetRouteControls: !foLastEffectivePayload,
          resetTrackMetadata: !foLastEffectivePayload,
        });
        setStatus("No override set for this file.");
      }
    } catch (err) {
      setStatus("Error loading override: " + (err.message || err));
    }
  }

  async function loadFileOverrideEffectiveForPath(path, item) {
    if (!path) return false;
    try {
      const url = FILE_OVERRIDES_EFFECTIVE_ROUTE + "?path=" + encodeURIComponent(path);
      const data = await apiGet(url);
      const applied = applyFileOverrideEffectivePayload(data, item);
      if (applied && !isPlainObject(data?.track_metadata)) await loadFileOverrideTracksForPath(path);
      return applied;
    } catch (_err) {
      await loadFileOverrideTracksForPath(path);
      return false;
    }
  }

  async function loadFileOverrideTracksForPath(path) {
    if (!path) return false;
    try {
      const url = FILE_OVERRIDES_TRACKS_ROUTE + "?path=" + encodeURIComponent(path);
      const data = await apiGet(url);
      renderDrawerTrackMetadata({
        track_metadata: trackMetadataFromTracksPayload(data),
        track_selection_preview: {},
      });
      return true;
    } catch (_err) {
      return false;
    }
  }

  async function saveFileOverrideForPath() {
    if (!foCurrentPath) { setStatus("No file selected."); return; }
    const payload = buildOverridePayload();
    if (!payload) { setStatus("No overrides specified — nothing to save."); return; }
    if (!validateExactTrackSelectionsBeforeSave()) return;
    const hasRouteVideoOverride = payloadHasRouteVideoOverride(payload);

    if (!(await ensureRoutePreviewAllowsSave(payload))) return;

    setStatus("Saving…");
    try {
      const result = await apiPost("/api/queue/file-overrides", payload);
      if (result && result.ok) {
        populateDrawerForm({
          audio: payload.audio || {},
          subtitles: payload.subtitles || {},
          routing: payload.routing || {},
          video: payload.video || {},
        });
        await loadFileOverrideEffectiveForPath(foCurrentPath, foCurrentItem);
        if (hasRouteVideoOverride) await loadRoutePreviewForPayload(payload);
        setStatus("Override saved. Takes effect on next pipeline round.");
        if (typeof appendCommandResult === "function") appendCommandResult(result);
        if (typeof refreshAll === "function") await refreshAll();
      } else {
        setStatus("Error: " + backendErrorMessage(result));
      }
    } catch (err) {
      setStatus("Error saving override: " + (err.message || err));
    }
  }

  async function clearFileOverrideField(fieldKey) {
    const fieldPath = DRAWER_FIELD_PATHS[fieldKey];
    if (!foCurrentPath) { setStatus("No file selected."); return; }
    if (!fieldPath) { setStatus("Cannot clear this override field."); return; }

    const button = document.querySelector(`[data-fo-use-inherited="${fieldKey}"]`);
    if (button) button.disabled = true;
    setStatus("Clearing field override…");
    try {
      const result = await apiPost("/api/queue/file-overrides", {
        path: foCurrentPath,
        clear_fields: [fieldPath],
      });
      if (result && result.ok) {
        resetExactTrackActionsForField(fieldKey);
        const reloaded = await loadFileOverrideEffectiveForPath(foCurrentPath, foCurrentItem);
        if (ROUTE_FIELD_KEYS.includes(fieldKey)) await refreshRoutePreviewFromCurrentForm();
        setStatus(reloaded ? "Override field cleared. Inherited value will be used." : "Override field cleared, but effective settings could not be reloaded.");
        if (typeof appendCommandResult === "function") appendCommandResult(result);
        if (typeof refreshAll === "function") await refreshAll();
      } else {
        if (button) button.disabled = false;
        setStatus("Error: " + backendErrorMessage(result));
      }
    } catch (err) {
      if (button) button.disabled = false;
      setStatus("Error clearing override field: " + (err.message || err));
    }
  }

  async function clearFileOverrideForPath() {
    if (!foCurrentPath) { setStatus("No file selected."); return; }
    setStatus("Clearing…");
    try {
      const result = await apiPost("/api/queue/file-overrides", { path: foCurrentPath, clear: true });
      if (result && result.ok) {
        clearDrawerForm();
        await loadFileOverrideEffectiveForPath(foCurrentPath, foCurrentItem);
        setStatus("Override cleared.");
        if (typeof appendCommandResult === "function") appendCommandResult(result);
        if (typeof refreshAll === "function") await refreshAll();
      } else {
        setStatus("Error: " + backendErrorMessage(result));
      }
    } catch (err) {
      setStatus("Error clearing override: " + (err.message || err));
    }
  }

  // ---------------------------------------------------------------------------
  // Wiring
  // ---------------------------------------------------------------------------

  function initFileSettingsDrawer() {
    const overlay  = byId("fo-overlay");
    const closeBtn = byId("fo-drawer-close");
    const saveBtn  = byId("fo-drawer-save");
    const clearBtn = byId("fo-drawer-clear");
    const folderPreviewBtn = byId("fo-folder-preview-open");
    const folderPreviewSaveBtn = byId("fo-folder-preview-save");
    const folderPreviewScopeSelect = byId("fo-folder-preview-scope-select");
    const folderPreviewLibraryBtn = byId("fo-folder-preview-library-settings");
    const folderRulesBtn = byId("fo-folder-rules-open");
    const folderRulesRefreshBtn = byId("fo-folder-rules-refresh");
    const folderRulesLibraryBtn = byId("fo-folder-rules-library-settings");
    const folderRulesList = byId("fo-folder-rules-list");
    const stripAll = byId("fo-sub-strip-all");

    if (overlay)  overlay.addEventListener("click", closeFileSettingsDrawer);
    if (closeBtn) closeBtn.addEventListener("click", closeFileSettingsDrawer);
    if (saveBtn)  saveBtn.addEventListener("click",  saveFileOverrideForPath);
    if (clearBtn) clearBtn.addEventListener("click", clearFileOverrideForPath);
    if (folderPreviewBtn) folderPreviewBtn.addEventListener("click", openFolderRulePreviewPanel);
    if (folderPreviewSaveBtn) folderPreviewSaveBtn.addEventListener("click", saveFolderRuleForPreview);
    if (folderPreviewScopeSelect) folderPreviewScopeSelect.addEventListener("change", handleFolderPreviewScopeChange);
    if (folderPreviewLibraryBtn) folderPreviewLibraryBtn.addEventListener("click", openLibrarySettingsFromFolderHandoff);
    if (folderRulesBtn) folderRulesBtn.addEventListener("click", loadFolderRulesForDrawer);
    if (folderRulesRefreshBtn) folderRulesRefreshBtn.addEventListener("click", loadFolderRulesForDrawer);
    if (folderRulesLibraryBtn) folderRulesLibraryBtn.addEventListener("click", openLibrarySettingsFromFolderHandoff);
    if (folderRulesList) folderRulesList.addEventListener("click", handleFolderRuleManagementClick);
    if (stripAll) stripAll.addEventListener("change", syncSubFilterFields);
    [
      "fo-folder-confirm-future-files",
      "fo-folder-confirm-file-overrides",
      "fo-folder-confirm-no-stream-index",
    ].forEach((id) => {
      const checkbox = byId(id);
      if (checkbox) checkbox.addEventListener("change", syncFolderPreviewSaveState);
    });
    [
      "fo-audio-keep-langs",
      "fo-audio-drop-langs",
      "fo-sub-keep-langs",
      "fo-sub-drop-langs",
      "fo-sub-strip-all",
    ].forEach((id) => {
      const control = byId(id);
      if (control) {
        control.addEventListener("change", invalidateFolderPreviewAfterRuleChange);
        control.addEventListener("input", invalidateFolderPreviewAfterRuleChange);
      }
    });
    document.querySelectorAll("[data-fo-use-inherited]").forEach((button) => {
      button.addEventListener("click", () => clearFileOverrideField(button.dataset.foUseInherited || ""));
    });
    document.querySelectorAll("[data-fo-route-control]").forEach((control) => {
      control.addEventListener("change", scheduleRoutePreviewFromCurrentForm);
    });
    document.addEventListener("change", (event) => {
      if (event.target?.matches?.("[data-fo-track-action]")) invalidateFolderPreviewAfterRuleChange();
    });

    document.addEventListener("keydown", handleFileSettingsDrawerKeydown);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initFileSettingsDrawer);
  } else {
    initFileSettingsDrawer();
  }

})();
