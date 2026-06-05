(function () {
  function createLaunchRiskPolicyPatchModule(deps = {}) {
    const {
      launchPolicyBoolText = function (value) { return value ? "on" : "off"; },
      launchPolicyChoiceLabel = function (value) { return String(value || ""); },
      launchSettingsBool = function (value, fallback = false) { return fallback; },
      launchSettingsConfigValue = function () { return undefined; },
      launchSettingsList = function (value, fallback = []) { return Array.isArray(fallback) ? fallback : []; },
      launchSettingsNumber = function (value, fallback = 0) { return fallback; },
      settingsPatchEffectiveChangedEntries = null,
      settingsPatchIsTouched = null,
    } = deps;

  const launchPolicySubtitleKeys = [
    "OutputContainer",
    "SubKeepLanguages",
    "Tx3gExtractLanguages",
    "BdpgsExtractLanguages",
    "ConvertTx3gToSrt",
    "DropTx3gAfterConversion",
    "CreateExternalTx3gSrtSidecars",
    "ConvertBdpgsToSrt",
    "DropBdpgsAfterConversion",
    "DropAssAfterConversion",
    "StripFormatting",
    "RemoveKaraoke",
    "KeepSignsAndSongs",
  ];
  const launchPolicyAudioKeys = [
    "AudioPassthroughProfile",
    "CompatibleAudioCodecs",
    "PreferredDefaultAudioLanguages",
    "AudioTranscodeCodec",
    "AudioTranscodeBitrate",
    "AudioTranscodeAutoBitrateByChannels",
    "AudioDownmixMode",
    "AudioMaxChannels",
    "AllowNoAudio",
  ];
  const launchPolicyPublishKeys = [
    "DeferredPublish",
    "CleanupRemoteStaging",
    "SkipStabilityCheck",
    "EnableIntegrityCheck",
    "DeleteSourceAfterProcessing",
    "TransientFailureRetryLimit",
    "RobocopyTimeoutSeconds",
    "OutsourceMinFreeSpaceGB",
    "OutputSizeMultiplier",
  ];

  // Frontend advisory only: backend launch validation remains authoritative for
  // queue scope, route safety, publish/drain safety, and source-deletion policy.
  function launchPolicyPatchState() {
    if (typeof settingsPatchIsTouched !== "function" || settingsPatchIsTouched() !== true) {
      return { touched: false, entries: [], error: "" };
    }
    if (typeof settingsPatchEffectiveChangedEntries !== "function") {
      return { touched: true, entries: [], error: "Settings patch impact helper is unavailable." };
    }
    try {
      return { touched: true, entries: settingsPatchEffectiveChangedEntries(), error: "" };
    } catch (error) {
      return {
        touched: true,
        entries: [],
        error: error instanceof Error ? error.message : String(error),
      };
    }
  }

  function launchPolicyEntryMap(entries) {
    const map = new Map();
    (Array.isArray(entries) ? entries : []).forEach((entry) => {
      if (entry?.key) map.set(entry.key, entry);
    });
    return map;
  }

  function launchPolicyChangedKeys(entries, keys) {
    const allowed = new Set(keys);
    return (Array.isArray(entries) ? entries : []).filter((entry) => entry?.changed && allowed.has(entry.key)).map((entry) => entry.key);
  }

  function launchPolicyCurrentValue(config, key, fallback) {
    const value = launchSettingsConfigValue(config, key);
    return value === undefined ? fallback : value;
  }

  function launchPolicyCandidateValue(config, entryMap, key, fallback) {
    const entry = entryMap.get(key);
    return entry ? entry.staged : launchPolicyCurrentValue(config, key, fallback);
  }

  function launchPolicyFormatSubtitle(config, entryMap = new Map()) {
    const container = String(launchPolicyCandidateValue(config, entryMap, "OutputContainer", "mkv")).toLowerCase();
    const keep = launchSettingsList(launchPolicyCandidateValue(config, entryMap, "SubKeepLanguages", ["eng", "und"]), ["eng", "und"]);
    const tx3gLang = launchSettingsList(launchPolicyCandidateValue(config, entryMap, "Tx3gExtractLanguages", ["eng", "und"]), ["eng", "und"]);
    const bdpgsLang = launchSettingsList(launchPolicyCandidateValue(config, entryMap, "BdpgsExtractLanguages", ["eng", "und"]), ["eng", "und"]);
    const vobSubLang = launchSettingsList(launchPolicyCandidateValue(config, entryMap, "VobSubExtractLanguages", ["eng", "und"]), ["eng", "und"]);
    const convertTx3g = launchSettingsBool(launchPolicyCandidateValue(config, entryMap, "ConvertTx3gToSrt", true), true);
    const dropTx3g = launchSettingsBool(launchPolicyCandidateValue(config, entryMap, "DropTx3gAfterConversion", false), false);
    const convertBdpgs = launchSettingsBool(launchPolicyCandidateValue(config, entryMap, "ConvertBdpgsToSrt", true), true);
    const dropBdpgs = launchSettingsBool(launchPolicyCandidateValue(config, entryMap, "DropBdpgsAfterConversion", false), false);
    const convertVobSub = launchSettingsBool(launchPolicyCandidateValue(config, entryMap, "ConvertVobSubToSrt", false), false);
    const dropVobSub = launchSettingsBool(launchPolicyCandidateValue(config, entryMap, "DropVobSubAfterConversion", false), false);
    const dropAss = launchSettingsBool(launchPolicyCandidateValue(config, entryMap, "DropAssAfterConversion", false), false);
    const strip = launchSettingsBool(launchPolicyCandidateValue(config, entryMap, "StripFormatting", true), true);
    return {
      container,
      keep,
      tx3gLang,
      bdpgsLang,
      vobSubLang,
      convertTx3g,
      dropTx3g,
      convertBdpgs,
      dropBdpgs,
      convertVobSub,
      dropVobSub,
      dropAss,
      strip,
      evidence: `container=${launchPolicyChoiceLabel(container)}; keep=${keep.join(", ") || "(empty)"}; TX3G lang=${tx3gLang.join(", ") || "(empty)"} convert/drop=${launchPolicyBoolText(convertTx3g)}/${launchPolicyBoolText(dropTx3g)}; BDPGS lang=${bdpgsLang.join(", ") || "(empty)"} OCR/drop=${launchPolicyBoolText(convertBdpgs)}/${launchPolicyBoolText(dropBdpgs)}; VobSub lang=${vobSubLang.join(", ") || "(empty)"} OCR/drop=${launchPolicyBoolText(convertVobSub)}/${launchPolicyBoolText(dropVobSub)}; ASS drop=${launchPolicyBoolText(dropAss)}; strip ASS=${launchPolicyBoolText(strip)}`,
    };
  }

  function launchPolicyFormatAudio(config, entryMap = new Map()) {
    const profile = String(launchPolicyCandidateValue(config, entryMap, "AudioPassthroughProfile", "plex_balanced"));
    const codecs = launchSettingsList(launchPolicyCandidateValue(config, entryMap, "CompatibleAudioCodecs", ["aac", "ac3", "eac3", "mp3", "opus", "vorbis"]), ["aac", "ac3", "eac3", "mp3", "opus", "vorbis"]);
    const languages = launchSettingsList(launchPolicyCandidateValue(config, entryMap, "PreferredDefaultAudioLanguages", ["english"]), ["english"]);
    const transcodeCodec = String(launchPolicyCandidateValue(config, entryMap, "AudioTranscodeCodec", "eac3"));
    const transcodeBitrate = String(launchPolicyCandidateValue(config, entryMap, "AudioTranscodeBitrate", "640k"));
    const autoBitrate = launchSettingsBool(launchPolicyCandidateValue(config, entryMap, "AudioTranscodeAutoBitrateByChannels", false), false);
    const downmix = String(launchPolicyCandidateValue(config, entryMap, "AudioDownmixMode", "max_channels"));
    const maxChannels = launchSettingsNumber(launchPolicyCandidateValue(config, entryMap, "AudioMaxChannels", 6), 6);
    const allowNoAudio = launchSettingsBool(launchPolicyCandidateValue(config, entryMap, "AllowNoAudio", false), false);
    return {
      profile,
      codecs,
      languages,
      transcodeCodec,
      transcodeBitrate,
      autoBitrate,
      downmix,
      maxChannels,
      allowNoAudio,
      evidence: `profile=${launchPolicyChoiceLabel(profile)}; codecs=${codecs.join(", ") || "(empty)"}; default languages=${languages.join(", ") || "(empty)"}; transcode=${transcodeCodec}/${transcodeBitrate}${autoBitrate ? " auto-by-channel" : ""}; downmix=${launchPolicyChoiceLabel(downmix)}; max channels=${maxChannels}; no-audio=${launchPolicyBoolText(allowNoAudio)}`,
    };
  }

  function launchPolicyFormatPublish(config, entryMap = new Map()) {
    const deferred = launchSettingsBool(launchPolicyCandidateValue(config, entryMap, "DeferredPublish", false), false);
    const cleanupRemote = launchSettingsBool(launchPolicyCandidateValue(config, entryMap, "CleanupRemoteStaging", false), false);
    const skipStability = launchSettingsBool(launchPolicyCandidateValue(config, entryMap, "SkipStabilityCheck", false), false);
    const integrity = launchSettingsBool(launchPolicyCandidateValue(config, entryMap, "EnableIntegrityCheck", true), true);
    const deleteSource = launchSettingsBool(launchPolicyCandidateValue(config, entryMap, "DeleteSourceAfterProcessing", false), false);
    const retries = launchSettingsNumber(launchPolicyCandidateValue(config, entryMap, "TransientFailureRetryLimit", 3), 3);
    const robocopyTimeout = launchSettingsNumber(launchPolicyCandidateValue(config, entryMap, "RobocopyTimeoutSeconds", 14400), 14400);
    const minFree = launchSettingsNumber(launchPolicyCandidateValue(config, entryMap, "OutsourceMinFreeSpaceGB", 20), 20);
    return {
      deferred,
      cleanupRemote,
      skipStability,
      integrity,
      deleteSource,
      retries,
      robocopyTimeout,
      minFree,
      evidence: `deferred=${launchPolicyBoolText(deferred)}; cleanup remote=${launchPolicyBoolText(cleanupRemote)}; stability=${skipStability ? "skipped" : "enabled"}; integrity=${integrity ? "enabled" : "disabled"}; delete source=${launchPolicyBoolText(deleteSource)}; retries=${retries}; copy timeout=${robocopyTimeout}s; min free=${minFree}GB`,
    };
  }

  function launchPolicyCandidatePosture(area, candidate, changedCount) {
    if (!changedCount) return "same as saved";
    if (area === "subtitle") {
      if ((candidate.dropTx3g && !candidate.convertTx3g) || (candidate.dropBdpgs && !candidate.convertBdpgs) || (candidate.dropVobSub && !candidate.convertVobSub)) return "blocked";
      if (candidate.container === "mp4" || candidate.dropTx3g || candidate.dropBdpgs || candidate.dropVobSub || candidate.dropAss || !candidate.convertTx3g || !candidate.convertBdpgs || !candidate.convertVobSub) return "review";
      return "preview required";
    }
    if (area === "audio") {
      if (candidate.allowNoAudio || (candidate.profile === "custom_codec_list" && !candidate.codecs.length)) return "blocked";
      if (!candidate.languages.length || candidate.profile === "lossless_passthrough" || candidate.profile === "custom_codec_list" || candidate.maxChannels < 6 || String(candidate.downmix || "").toLowerCase() === "stereo") return "review";
      return "preview required";
    }
    if (area === "publish") {
      if (candidate.deleteSource) return "blocked";
      if (candidate.skipStability || !candidate.integrity || candidate.cleanupRemote || candidate.deferred || candidate.retries > 5 || candidate.robocopyTimeout < 1800) return "review";
      return "preview required";
    }
    return "preview required";
  }

    return {
      launchPolicySubtitleKeys,
      launchPolicyAudioKeys,
      launchPolicyPublishKeys,
      launchPolicyPatchState,
      launchPolicyEntryMap,
      launchPolicyChangedKeys,
      launchPolicyCurrentValue,
      launchPolicyCandidateValue,
      launchPolicyFormatSubtitle,
      launchPolicyFormatAudio,
      launchPolicyFormatPublish,
      launchPolicyCandidatePosture,
    };
  }

  window.__launchRiskPolicyPatchModule = {
    createLaunchRiskPolicyPatchModule,
  };
})();
