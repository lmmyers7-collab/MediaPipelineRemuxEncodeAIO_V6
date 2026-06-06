// queue/fileOverrides.drawer.state.js
// Shared state/constants for the Queue file override drawer facade.

(function initFileOverridesDrawerStateModule() {
  function createFileOverridesDrawerState({ documentRef = document, windowRef = window } = {}) {
    const FILE_OVERRIDES_ROUTE = "/api/queue/file-overrides";
    const FILE_OVERRIDES_EFFECTIVE_ROUTE = "/api/queue/file-overrides/effective";
    const FILE_OVERRIDES_TRACKS_ROUTE = "/api/queue/file-overrides/tracks";
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
    subtitleBurnTrack: "subtitles.burnTrack",
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
    subtitleBurnTrack: {},
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
    subtitle: { keep: "subtitles.keepTracks", drop: "subtitles.dropTracks", burn: "subtitles.burnTrack" },
  };
    const SOURCE_INFO_BASIS_LABELS = Object.freeze({
    file_size_duration: "from size and duration",
    primary_video_reported: "reported video stream",
    container_reported: "reported container",
    unavailable: "",
  });
    const DRAWER_FOCUSABLE_SELECTOR = [
    "a[href]",
    "button",
    "input",
    "select",
    "textarea",
    "[tabindex]:not([tabindex=\"-1\"])",
  ].join(",");

    let state;

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

  function byId(id) { return documentRef.getElementById(id); }
  function statusToneForMessage(msg) {
    const text = String(msg || "").trim().toLowerCase();
    if (!text) return "info";
    if (text.startsWith("error") || text.includes(" cannot ") || text.includes("could not")) return "error";
    if (text.includes("saved") || text.includes("loaded") || text.includes("cleared")) return "success";
    if (text.includes("unsaved") || text.includes("cancelled") || text.includes("nothing to save")) return "warning";
    if (text.includes("saving") || text.includes("clearing") || text.includes("loading")) return "working";
    return "info";
  }

  function setStatus(msg, tone = "") {
    const el = byId("fo-drawer-status");
    if (!el) return;
    const text = String(msg || "");
    const resolvedTone = tone || statusToneForMessage(text);
    el.textContent = text;
    el.dataset.tone = resolvedTone;
    el.setAttribute("role", resolvedTone === "error" ? "alert" : "status");
    el.setAttribute("aria-live", resolvedTone === "error" ? "assertive" : "polite");
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
      subtitleBurn: [],
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
    const path = String(state.foCurrentPath || "").trim();
    if (!path || /[\\/]$/.test(path)) return false;
    const leaf = path.split(/[\\/]/).pop() || "";
    return /\.[A-Za-z0-9]{1,12}$/.test(leaf);
  }

    state = {
      foCurrentPath: "",
      foCurrentItem: null,
      fileSettingsDrawerTrigger: null,
      foLastEffectivePayload: null,
      foExactTrackOverrideEntry: null,
      foExactTrackWarnings: [],
      foUnmatchedExactSelectors: emptyExactSelectorState(),
      foCommandInFlight: false,
      foDrawerBaselineSignature: "",
      foDrawerDirty: false,
      foSeriesPreviewPayload: null,
      foSeriesFilter: "all",
      foSeriesModalTrigger: null,
      foDrawerHiddenForSeriesModal: false,
    };

    function resetClosedDrawerState() {
      state.foLastEffectivePayload = null;
      state.foExactTrackOverrideEntry = null;
      state.foExactTrackWarnings = [];
      state.foUnmatchedExactSelectors = emptyExactSelectorState();
      state.foDrawerBaselineSignature = "";
      state.foDrawerDirty = false;
      state.foCurrentPath = "";
      state.foCurrentItem = null;
    }

    return {
      documentRef,
      windowRef,
      state,
      FILE_OVERRIDES_ROUTE,
      FILE_OVERRIDES_EFFECTIVE_ROUTE,
      FILE_OVERRIDES_TRACKS_ROUTE,
      DRAWER_FIELD_HINT_IDS,
      DRAWER_FIELD_PATHS,
      DRAWER_FIELD_CONFIG,
      ROUTE_FIELD_CONFIG,
      ROUTE_FIELD_KEYS,
      ROUTE_FORCE_VALUES,
      TRACK_ACTION_FIELD_PATHS,
      SOURCE_INFO_BASIS_LABELS,
      DRAWER_FOCUSABLE_SELECTOR,
      parseLangList,
      langCodesToRules,
      selectorStreamIndex,
      isExactTrackSelector,
      rulesToLangInput,
      byId,
      statusToneForMessage,
      setStatus,
      isPlainObject,
      emptyExactSelectorState,
      hasOwnValue,
      backendErrorMessage,
      currentFileOverridePathLooksFileLike,
      resetClosedDrawerState,
    };
  }

  window.__queueFileOverridesDrawerStateModule = { createFileOverridesDrawerState };
})();
