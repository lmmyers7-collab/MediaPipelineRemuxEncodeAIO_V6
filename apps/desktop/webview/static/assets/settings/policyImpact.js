(function () {
  function createSettingsPolicyImpactModule(deps) {
    deps = deps || {};
    const byId = deps.byId || function () { return null; };
    const setText = deps.setText || function () {};
    const clearRows = deps.clearRows || function () {};
    const appendCells = deps.appendCells || function () {};
    const getCommandHistory = deps.getCommandHistory || function () { return []; };
    const isSettingsCommand = deps.isSettingsCommand || function () { return false; };
    const settingsCommandHistoryLine = deps.settingsCommandHistoryLine || function () { return ""; };
    const settingsPatchSaveReadinessIssues = deps.settingsPatchSaveReadinessIssues || function () { return []; };
    const settingsPatchSaveReadinessStatus = deps.settingsPatchSaveReadinessStatus || function () { return "No patch"; };
    const makeRowSelectable = deps.makeRowSelectable || function (row, handler) { if (row) row.addEventListener("click", handler); };
    const updateTableStatusLegend = deps.updateTableStatusLegend || function () {};
    const formatConfigValue = deps.formatConfigValue || function (value) { return String(value ?? ""); };
    const formatSettingsChoiceLabel = deps.formatSettingsChoiceLabel || function (value) { return String(value || ""); };
    const formatSettingsListValue = deps.formatSettingsListValue || function (value) { return Array.isArray(value) ? value.join(", ") : String(value ?? ""); };
    const parseSettingsListText = deps.parseSettingsListText || function (value) { return String(value || "").split(",").map((item) => item.trim()).filter(Boolean); };
    const settingsBuilderConfigValue = deps.settingsBuilderConfigValue || function (_key, fallback) { return fallback; };
    const settingsBuilderInputValue = deps.settingsBuilderInputValue || function () { return ""; };
    const settingsFieldDefinition = deps.settingsFieldDefinition || function () { return null; };
    const settingsRawConfigValue = deps.settingsRawConfigValue || function () { return undefined; };
    const parseSettingsPatchJson = deps.parseSettingsPatchJson || function () { return {}; };
    const settingsValuesEqual = deps.settingsValuesEqual || function (left, right) { return JSON.stringify(left) === JSON.stringify(right); };
    const settingsImpactGroups = Array.isArray(deps.settingsImpactGroups) ? deps.settingsImpactGroups : [];
    const settingsSpecificImpactHints = deps.settingsSpecificImpactHints || {};
    const getLastSettings = deps.getLastSettings || function () { return null; };
    const getLastSettingsValues = deps.getLastSettingsValues || function () { return {}; };
    const getLastSettingsPatchPreviewEvidence = deps.getLastSettingsPatchPreviewEvidence || function () { return null; };
    const getLastSettingsPatchSaveEvidence = deps.getLastSettingsPatchSaveEvidence || function () { return null; };
    const getSelectedSettingsEffectivePolicyKey = deps.getSelectedSettingsEffectivePolicyKey || function () { return ""; };
    const setSelectedSettingsEffectivePolicyKey = deps.setSelectedSettingsEffectivePolicyKey || function () {};

function settingsMediaPolicyList(id, key, fallback) {
  const element = byId(id);
  if (element) return parseSettingsListText(element.value || "");
  return parseSettingsListText(formatSettingsListValue(settingsBuilderConfigValue(key, fallback)));
}

function settingsMediaPolicyBool(id, key, fallback) {
  const element = byId(id);
  if (element) return element.checked === true;
  const value = settingsBuilderConfigValue(key, fallback);
  return value === true || String(value).toLowerCase() === "true";
}

function settingsMediaPolicyValue(id, key, fallback) {
  const element = byId(id);
  if (element) return settingsBuilderInputValue(id);
  return String(settingsBuilderConfigValue(key, fallback) ?? "");
}

function settingsMediaPolicyNumber(id, key, fallback) {
  const raw = settingsMediaPolicyValue(id, key, fallback);
  const value = Number(raw);
  return Number.isFinite(value) ? value : Number(fallback || 0);
}

function settingsRouteMaxHeightFromUpperTolerance(baseHeight, tolerancePercent) {
  return Math.round(Number(baseHeight) * (1 + (Number(tolerancePercent) / 100)));
}

function settingsRouteMinHeightFromLowerTolerance(baseHeight, tolerancePercent) {
  return Math.round(Number(baseHeight) * (1 - (Number(tolerancePercent) / 100)));
}

function settingsRouteHeightBoundariesFromValues(values) {
  return {
    route1080pMaxHeight: settingsRouteMaxHeightFromUpperTolerance(1080, values.route1080pUpperPercent ?? 11.111111),
    route1440pMinHeight: settingsRouteMinHeightFromLowerTolerance(1440, values.route1440pLowerPercent ?? 16.597222),
    route1440pMaxHeight: settingsRouteMaxHeightFromUpperTolerance(1440, values.route1440pUpperPercent ?? 24.930556),
    route4kMinHeight: settingsRouteMinHeightFromLowerTolerance(2160, values.route4kLowerPercent ?? 16.666667),
  };
}

function settingsActiveRouteHeightBoundaries() {
  return settingsRouteHeightBoundariesFromValues({
    route1080pUpperPercent: settingsMediaPolicyNumber("settings-builder-1080p-upper-tolerance", "Route1080pUpperHeightTolerancePercent", 11.111111),
    route1440pLowerPercent: settingsMediaPolicyNumber("settings-builder-1440p-lower-tolerance", "Route1440pLowerHeightTolerancePercent", 16.597222),
    route1440pUpperPercent: settingsMediaPolicyNumber("settings-builder-1440p-upper-tolerance", "Route1440pUpperHeightTolerancePercent", 24.930556),
    route4kLowerPercent: settingsMediaPolicyNumber("settings-builder-4k-lower-tolerance", "Route4KLowerHeightTolerancePercent", 16.666667),
  });
}

function settingsPatchHasCurrentPercentKeys() {
  return [
    "Route1080pUpperHeightTolerancePercent",
    "Route1440pLowerHeightTolerancePercent",
    "Route1440pUpperHeightTolerancePercent",
    "Route4KLowerHeightTolerancePercent",
  ].some((key) => {
    const value = settingsRawConfigValue(key);
    return value !== undefined && value !== null && String(value).trim() !== "";
  });
}

function settingsPatchHasCandidatePercentKeys(entries) {
  return settingsPatchHasCurrentPercentKeys() || entries.some((entry) => [
    "Route1080pUpperHeightTolerancePercent",
    "Route1440pLowerHeightTolerancePercent",
    "Route1440pUpperHeightTolerancePercent",
    "Route4KLowerHeightTolerancePercent",
  ].includes(entry.key));
}

function settingsPatchRouteHeightBoundaries(entries, mode) {
  const candidate = mode === "candidate";
  const numberValue = candidate ? settingsPatchCandidateNumber : ((_entries, key, fallback) => settingsPatchCurrentNumber(key, fallback));
  return settingsRouteHeightBoundariesFromValues({
    route1080pUpperPercent: numberValue(entries, "Route1080pUpperHeightTolerancePercent", 11.111111),
    route1440pLowerPercent: numberValue(entries, "Route1440pLowerHeightTolerancePercent", 16.597222),
    route1440pUpperPercent: numberValue(entries, "Route1440pUpperHeightTolerancePercent", 24.930556),
    route4kLowerPercent: numberValue(entries, "Route4KLowerHeightTolerancePercent", 16.666667),
  });
}

function settingsMediaPolicyLanguageGaps(base, candidate) {
  const normalizedBase = new Set((base || []).map((item) => String(item).toLowerCase()));
  return (candidate || []).filter((item) => !normalizedBase.has(String(item).toLowerCase()));
}

function settingsMediaPolicyRows() {
  const keepLanguages = settingsMediaPolicyList("settings-subtitle-languages", "SubKeepLanguages", ["eng", "und"]);
  const tx3gLanguages = settingsMediaPolicyList("settings-subtitle-tx3g-languages", "Tx3gExtractLanguages", ["eng", "und"]);
  const bdpgsLanguages = settingsMediaPolicyList("settings-subtitle-bdpgs-languages", "BdpgsExtractLanguages", ["eng", "und"]);
  const vobSubLanguages = settingsMediaPolicyList("settings-subtitle-vobsub-languages", "VobSubExtractLanguages", ["eng", "und"]);
  const convertTx3g = settingsMediaPolicyBool("settings-subtitle-convert-tx3g", "ConvertTx3gToSrt", true);
  const dropTx3g = settingsMediaPolicyBool("settings-subtitle-drop-tx3g", "DropTx3gAfterConversion", false);
  const sidecarTx3g = settingsMediaPolicyBool("settings-subtitle-sidecar-tx3g", "CreateExternalTx3gSrtSidecars", false);
  const preserveTx3gSrt = settingsMediaPolicyBool("settings-subtitle-preserve-tx3g-srt", "Tx3gPreserveExistingSrt", true);
  const convertBdpgs = settingsMediaPolicyBool("settings-subtitle-convert-bdpgs", "ConvertBdpgsToSrt", false);
  const dropBdpgs = settingsMediaPolicyBool("settings-subtitle-drop-bdpgs", "DropBdpgsAfterConversion", false);
  const convertVobSub = settingsMediaPolicyBool("settings-subtitle-convert-vobsub", "ConvertVobSubToSrt", false);
  const dropVobSub = settingsMediaPolicyBool("settings-subtitle-drop-vobsub", "DropVobSubAfterConversion", false);
  const dropAss = settingsMediaPolicyBool("settings-subtitle-drop-ass", "DropAssAfterConversion", false);
  const stripFormatting = settingsMediaPolicyBool("settings-subtitle-strip-formatting", "StripFormatting", true);
  const removeKaraoke = settingsMediaPolicyBool("settings-subtitle-remove-karaoke", "RemoveKaraoke", true);
  const keepSigns = settingsMediaPolicyBool("settings-subtitle-keep-signs", "KeepSignsAndSongs", true);
  const extractTimeout = settingsMediaPolicyNumber("settings-subtitle-extract-timeout", "SubtitleExtractTimeoutSeconds", 180);
  const probeTimeout = settingsMediaPolicyNumber("settings-subtitle-probe-timeout", "SubtitleProbeTimeoutSeconds", 30);
  const bdpgsTimeout = settingsMediaPolicyNumber("settings-subtitle-bdpgs-timeout", "BdpgsOcrTimeoutSeconds", 1800);
  const vobSubTimeout = settingsMediaPolicyNumber("settings-subtitle-vobsub-timeout", "VobSubOcrTimeoutSeconds", 1800);
  const passthroughProfile = settingsMediaPolicyValue("settings-audio-passthrough-profile", "AudioPassthroughProfile", "plex_balanced") || "plex_balanced";
  const compatibleCodecs = settingsMediaPolicyList("settings-audio-compatible-codecs", "CompatibleAudioCodecs", ["aac", "ac3", "eac3", "mp3", "opus", "vorbis"]);
  const defaultAudioLanguages = settingsMediaPolicyList("settings-audio-preferred-languages", "PreferredDefaultAudioLanguages", ["english"]);
  const transcodeCodec = settingsMediaPolicyValue("settings-audio-transcode-codec", "AudioTranscodeCodec", "eac3") || "eac3";
  const transcodeBitrate = settingsMediaPolicyValue("settings-audio-transcode-bitrate", "AudioTranscodeBitrate", "640k") || "640k";
  const autoBitrate = settingsMediaPolicyBool("settings-audio-auto-bitrate", "AudioTranscodeAutoBitrateByChannels", false);
  const downmixMode = settingsMediaPolicyValue("settings-audio-downmix-mode", "AudioDownmixMode", "max_channels") || "max_channels";
  const maxChannels = settingsMediaPolicyNumber("settings-audio-max-channels", "AudioMaxChannels", 6);
  const allowNoAudio = settingsMediaPolicyBool("settings-audio-allow-no-audio", "AllowNoAudio", false);
  const tx3gGaps = settingsMediaPolicyLanguageGaps(keepLanguages, tx3gLanguages);
  const bdpgsGaps = settingsMediaPolicyLanguageGaps(keepLanguages, bdpgsLanguages);
  const vobSubGaps = settingsMediaPolicyLanguageGaps(keepLanguages, vobSubLanguages);
  const rows = [
    {
      area: "Subtitle language routing",
      posture: !keepLanguages.length ? "warning" : (tx3gGaps.length || bdpgsGaps.length || vobSubGaps.length ? "review" : "coherent"),
      evidence: `keep=${keepLanguages.join(", ") || "(empty)"}; TX3G=${tx3gLanguages.join(", ") || "(empty)"}; BDPGS=${bdpgsLanguages.join(", ") || "(empty)"}; VobSub=${vobSubLanguages.join(", ") || "(empty)"}`,
      action: tx3gGaps.length || bdpgsGaps.length || vobSubGaps.length
        ? `Review extract-only language gaps: TX3G ${tx3gGaps.join(", ") || "none"}; BDPGS ${bdpgsGaps.join(", ") || "none"}; VobSub ${vobSubGaps.join(", ") || "none"}.`
        : "Preferred subtitle language policy is visible before backend preview/save.",
    },
    {
      area: "TX3G / mov_text SRT generation",
      posture: dropTx3g && !convertTx3g ? "blocked" : (!convertTx3g || dropTx3g ? "review" : "coherent"),
      evidence: `convert=${convertTx3g ? "on" : "off"}; drop original=${dropTx3g ? "on" : "off"}; sidecar=${sidecarTx3g ? "on" : "off"}; preserve existing SRT=${preserveTx3gSrt ? "on" : "off"}`,
      action: dropTx3g && !convertTx3g
        ? "Do not drop TX3G while conversion is disabled; that can remove subtitles without creating SRT."
        : "Default Plex posture is add SRT for preferred languages while preserving original TX3G unless drop is intentional.",
    },
    {
      area: "BDPGS OCR to SRT",
      posture: dropBdpgs && !convertBdpgs ? "blocked" : (!convertBdpgs || dropBdpgs ? "review" : "coherent"),
      evidence: `OCR=${convertBdpgs ? "on" : "off"}; drop original=${dropBdpgs ? "on" : "off"}; timeout=${bdpgsTimeout}s`,
      action: dropBdpgs && !convertBdpgs
        ? "Do not drop BDPGS while OCR is disabled; that can remove image subtitles without creating SRT."
        : "Preferred-language BDPGS should generate SRT for Plex while original image subtitles stay unless drop is intentional.",
    },
    {
      area: "VobSub OCR to SRT",
      posture: dropVobSub && !convertVobSub ? "blocked" : (!convertVobSub || dropVobSub ? "review" : "coherent"),
      evidence: `OCR=${convertVobSub ? "on" : "off"}; drop original=${dropVobSub ? "on" : "off"}; timeout=${vobSubTimeout}s`,
      action: dropVobSub && !convertVobSub
        ? "Do not drop embedded VobSub while OCR is disabled; that can remove image subtitles without creating SRT."
        : "Preferred-language VobSub should generate SRT for Plex while embedded originals stay unless drop is intentional.",
    },
    {
      area: "ASS / SSA preservation",
      posture: dropAss ? "review" : "coherent",
      evidence: `drop original=${dropAss ? "on" : "off"}; strip formatting=${stripFormatting ? "on" : "off"}; remove karaoke=${removeKaraoke ? "on" : "off"}; keep signs/songs=${keepSigns ? "on" : "off"}`,
      action: "SRT conversion can strip styling through filters, but ASS/SSA originals should remain available unless the drop toggle is intentional.",
    },
    {
      area: "Subtitle timeout posture",
      posture: extractTimeout <= 0 || probeTimeout <= 0 || bdpgsTimeout <= 0 || vobSubTimeout <= 0 ? "blocked" : (extractTimeout < 60 || probeTimeout < 10 || bdpgsTimeout < 600 || vobSubTimeout < 600 ? "review" : "coherent"),
      evidence: `extract=${extractTimeout}s; probe=${probeTimeout}s; BDPGS OCR=${bdpgsTimeout}s; VobSub OCR=${vobSubTimeout}s`,
      action: "Short timeout ceilings can turn slow disks, network shares, or OCR-heavy files into manual-review failures.",
    },
    {
      area: "Audio language/default routing",
      posture: defaultAudioLanguages.length ? "coherent" : "review",
      evidence: `preferred defaults=${defaultAudioLanguages.join(", ") || "(empty)"}`,
      action: "Preferred default audio languages make default-track behavior predictable when sources have mixed or missing metadata.",
    },
    {
      area: "Audio passthrough/transcode policy",
      posture: passthroughProfile === "custom_codec_list" && !compatibleCodecs.length ? "blocked" : (passthroughProfile === "lossless_passthrough" || passthroughProfile === "custom_codec_list" ? "review" : "coherent"),
      evidence: `profile=${formatSettingsChoiceLabel(passthroughProfile)}; codecs=${compatibleCodecs.join(", ") || "(empty)"}; transcode=${formatSettingsChoiceLabel(transcodeCodec)} ${autoBitrate ? "auto bitrate by channels" : transcodeBitrate}`,
      action: "Custom/lossless passthrough can be valid, but it should be intentional because it changes Plex Direct Play predictability.",
    },
    {
      area: "Audio channel / no-audio safety",
      posture: allowNoAudio ? "blocked" : (downmixMode === "stereo" || maxChannels < 6 ? "review" : "coherent"),
      evidence: `downmix=${formatSettingsChoiceLabel(downmixMode)}; max channels=${maxChannels}; allow no-audio=${allowNoAudio ? "on" : "off"}`,
      action: allowNoAudio
        ? "No-audio output is unsafe for normal Plex publishing and should stay disabled unless this is a deliberate manual-review case."
        : "Channel caps/downmix settings should match the operator's compatibility target before staging a patch.",
    },
  ];
  return rows;
}

function settingsMediaPolicyStatus(rows = settingsMediaPolicyRows()) {
  if (rows.some((row) => row.posture === "blocked")) return "Blocked review";
  if (rows.some((row) => row.posture === "warning" || row.posture === "review")) return "Review";
  return rows.length ? "Coherent" : "No policy";
}

function settingsActiveMediaPolicyRows() {
  const routingProfile = settingsMediaPolicyValue("settings-builder-routing-profile", "RoutingProfile", "plex_direct_stream") || "plex_direct_stream";
  const routeThresholdMode = settingsMediaPolicyValue("settings-builder-route-threshold-mode", "RouteThresholdMode", "compatibility_advisory") || "compatibility_advisory";
  const sizeGuard = settingsMediaPolicyValue("settings-builder-size-guard", "SizeGuardMode", "advisory") || "advisory";
  const encodeTuning = settingsMediaPolicyValue("settings-builder-encode-tuning", "EncodeTuningPreset", "balanced_nvenc") || "balanced_nvenc";
  const encodeLadder = settingsMediaPolicyValue("settings-builder-encode-ladder", "EncodeLadder", "auto") || "auto";
  const videoCodec = settingsMediaPolicyValue("settings-builder-video-codec", "VideoCodec", "hevc_nvenc") || "hevc_nvenc";
  const outputContainer = settingsMediaPolicyValue("settings-builder-output-container", "OutputContainer", "mkv") || "mkv";
  const maxGrowth = settingsMediaPolicyNumber("settings-builder-max-growth", "MaxEncodeGrowthPercent", 5);
  const compatGrowth = settingsMediaPolicyNumber("settings-builder-compat-growth", "CompatibilityEncodeGrowthPercent", 15);
  const movie1080pTarget = settingsMediaPolicyNumber("settings-builder-movie-1080p-target", "MovieRoute1080pTargetSizeGB", 8);
  const movie1440pTarget = settingsMediaPolicyNumber("settings-builder-movie-1440p-target", "MovieRoute1440pTargetSizeGB", 8);
  const movie4kTarget = settingsMediaPolicyNumber("settings-builder-movie-4k-target", "MovieRoute4KTargetSizeGB", 8);
  const tv1080pTarget = settingsMediaPolicyNumber("settings-builder-tv-1080p-target", "TVRoute1080pTargetSizeGB", 3);
  const tv1440pTarget = settingsMediaPolicyNumber("settings-builder-tv-1440p-target", "TVRoute1440pTargetSizeGB", 3);
  const tv4kTarget = settingsMediaPolicyNumber("settings-builder-tv-4k-target", "TVRoute4KTargetSizeGB", 3);
  const routeBoundaries = settingsActiveRouteHeightBoundaries();
  const route1080pMaxBitrate = settingsMediaPolicyNumber("settings-builder-1080p-route-bitrate", "Route1080pMaxVideoBitrateMbps", 20);
  const route1440pMaxBitrate = settingsMediaPolicyNumber("settings-builder-1440p-route-bitrate", "Route1440pMaxVideoBitrateMbps", 35);
  const route4kMaxBitrate = settingsMediaPolicyNumber("settings-builder-4k-route-bitrate", "Route4KMaxVideoBitrateMbps", 35);
  const allowH264Copy = settingsMediaPolicyBool("settings-video-h264-remux", "AllowH264RemuxIfPlexCompatible", true);
  const h264MaxBitrate = settingsMediaPolicyNumber("settings-video-h264-max-bitrate", "H264RemuxMaxBitrateMbps", 35);
  const h264MaxHeight = settingsMediaPolicyNumber("settings-video-h264-max-height", "H264RemuxMaxHeight", 1080);
  const remuxSafeCodecs = settingsMediaPolicyList("settings-video-remux-safe-codecs", "RemuxSafeVideoCodecs", ["hevc", "h265", "h264", "avc"]);
  const extraVideoFlags = settingsMediaPolicyList("settings-video-extra-flags", "ExtraVideoFlags", []);
  const convertTx3g = settingsMediaPolicyBool("settings-subtitle-convert-tx3g", "ConvertTx3gToSrt", true);
  const dropTx3g = settingsMediaPolicyBool("settings-subtitle-drop-tx3g", "DropTx3gAfterConversion", false);
  const convertBdpgs = settingsMediaPolicyBool("settings-subtitle-convert-bdpgs", "ConvertBdpgsToSrt", false);
  const dropBdpgs = settingsMediaPolicyBool("settings-subtitle-drop-bdpgs", "DropBdpgsAfterConversion", false);
  const convertVobSub = settingsMediaPolicyBool("settings-subtitle-convert-vobsub", "ConvertVobSubToSrt", false);
  const dropVobSub = settingsMediaPolicyBool("settings-subtitle-drop-vobsub", "DropVobSubAfterConversion", false);
  const dropAss = settingsMediaPolicyBool("settings-subtitle-drop-ass", "DropAssAfterConversion", false);
  const allowNoAudio = settingsMediaPolicyBool("settings-audio-allow-no-audio", "AllowNoAudio", false);
  const passthroughProfile = settingsMediaPolicyValue("settings-audio-passthrough-profile", "AudioPassthroughProfile", "plex_balanced") || "plex_balanced";
  const defaultAudioLanguages = settingsMediaPolicyList("settings-audio-preferred-languages", "PreferredDefaultAudioLanguages", ["english"]);
  const deferredPublish = settingsMediaPolicyBool("settings-pending-deferred-publish", "DeferredPublish", false);
  const cleanupRemote = settingsMediaPolicyBool("settings-pending-cleanup-remote", "CleanupRemoteStaging", false);
  const skipStability = settingsMediaPolicyBool("settings-pending-skip-stability", "SkipStabilityCheck", false);
  const integrity = settingsMediaPolicyBool("settings-pending-enable-integrity", "EnableIntegrityCheck", true);
  const rows = [
    {
      area: "Routing profile / output-size guard",
      posture: ["off", "disabled"].includes(String(sizeGuard).toLowerCase()) ? "review" : "coherent",
      evidence: `profile=${formatSettingsChoiceLabel(routingProfile)}; threshold=${formatSettingsChoiceLabel(routeThresholdMode)}; if encoded output is too large=${formatSettingsChoiceLabel(sizeGuard)}; normal growth=${maxGrowth}%; compatibility growth=${compatGrowth}%; targets 1080p movie/TV=${movie1080pTarget}/${tv1080pTarget}GB, 1440p movie/TV=${movie1440pTarget}/${tv1440pTarget}GB, 4K movie/TV=${movie4kTarget}/${tv4kTarget}GB; unknown height uses the 1080p targets and ${route1080pMaxBitrate}Mbps cap; bitrate caps 1080p <=${routeBoundaries.route1080pMaxHeight}p ${route1080pMaxBitrate}Mbps, 1440p ${routeBoundaries.route1440pMinHeight}-${routeBoundaries.route1440pMaxHeight}p ${route1440pMaxBitrate}Mbps, 4K >=${routeBoundaries.route4kMinHeight}p ${route4kMaxBitrate}Mbps`,
      handoff: "Launch should show these saved route/size values before Start. Source height selects both the target output size and direct-copy bitrate cap; final enforcement remains backend-owned.",
    },
    {
      area: "Video copy / encoder path",
      posture: !allowH264Copy || extraVideoFlags.length ? "review" : "coherent",
      evidence: `codec=${formatSettingsChoiceLabel(videoCodec)}; tuning=${formatSettingsChoiceLabel(encodeTuning)}; ladder=${formatSettingsChoiceLabel(encodeLadder)}; H.264 copy=${allowH264Copy ? "on" : "off"} <=${h264MaxBitrate}Mbps/${h264MaxHeight}p; remux-safe=${remuxSafeCodecs.join(", ") || "(empty)"}; legacy flags=${extraVideoFlags.length}`,
      handoff: allowH264Copy
        ? "Plex-compatible H.264 sources can remain copy/remux candidates; fallback encoder choices remain backend-owned."
        : "Compatible H.264 sources may encode instead of copy. Confirm this is intentional before large batches.",
    },
    {
      area: "Container / subtitle mux posture",
      posture: String(outputContainer).toLowerCase() === "mp4" && (!dropBdpgs || !dropVobSub || !dropAss) ? "review" : "coherent",
      evidence: `container=${formatSettingsChoiceLabel(outputContainer)}; TX3G convert/drop=${convertTx3g ? "on" : "off"}/${dropTx3g ? "on" : "off"}; BDPGS OCR/drop=${convertBdpgs ? "on" : "off"}/${dropBdpgs ? "on" : "off"}; VobSub OCR/drop=${convertVobSub ? "on" : "off"}/${dropVobSub ? "on" : "off"}; ASS drop=${dropAss ? "on" : "off"}`,
      handoff: String(outputContainer).toLowerCase() === "mp4"
        ? "MP4 cannot carry every original subtitle format. Backend routing must externalize or drop unsupported tracks deliberately."
        : "MKV remains the safer container for preserving original subtitle/audio streams while adding Plex-friendly SRT.",
    },
    {
      area: "SRT generation / original preservation",
      posture: (dropTx3g && !convertTx3g) || (dropBdpgs && !convertBdpgs) || (dropVobSub && !convertVobSub) ? "blocked" : (!convertTx3g || !convertBdpgs || !convertVobSub || dropTx3g || dropBdpgs || dropVobSub || dropAss ? "review" : "coherent"),
      evidence: `TX3G SRT=${convertTx3g ? "on" : "off"}; BDPGS OCR=${convertBdpgs ? "on" : "off"}; VobSub OCR=${convertVobSub ? "on" : "off"}; drop originals=${[dropTx3g ? "TX3G" : "", dropBdpgs ? "BDPGS" : "", dropVobSub ? "VobSub" : "", dropAss ? "ASS" : ""].filter(Boolean).join(", ") || "none"}`,
      handoff: "Default Plex posture is add SRT for preferred languages while preserving originals unless a drop toggle is explicitly enabled.",
    },
    {
      area: "Audio default / passthrough",
      posture: allowNoAudio ? "blocked" : (!defaultAudioLanguages.length || passthroughProfile === "lossless_passthrough" || passthroughProfile === "custom_codec_list" ? "review" : "coherent"),
      evidence: `passthrough=${formatSettingsChoiceLabel(passthroughProfile)}; default languages=${defaultAudioLanguages.join(", ") || "(empty)"}; allow no-audio=${allowNoAudio ? "on" : "off"}`,
      handoff: allowNoAudio
        ? "No-audio output should block normal Plex publishing until deliberately reviewed."
        : "Preferred default-language and passthrough policy should be visible in Launch before unattended runs.",
    },
    {
      area: "Publish / recovery posture",
      posture: cleanupRemote || skipStability || !integrity ? "review" : "coherent",
      evidence: `deferred publish=${deferredPublish ? "on" : "off"}; remote cleanup=${cleanupRemote ? "on" : "off"}; stability=${skipStability ? "skipped" : "enabled"}; integrity=${integrity ? "enabled" : "disabled"}`,
      handoff: deferredPublish
        ? "Completed files may park in Pending Publish; verify drain readiness and output proof after the sample run."
        : "Direct publish remains backend-owned; source files should still be copied to scratch and preserved.",
    },
  ];
  return rows;
}

function settingsActiveMediaPolicyStatus(rows = settingsActiveMediaPolicyRows()) {
  if (rows.some((row) => row.posture === "blocked")) return "Blocked review";
  if (rows.some((row) => row.posture === "review" || row.posture === "warning")) return "Review";
  return rows.length ? "Coherent" : "No policy";
}

function settingsActiveMediaPolicySummaryLines(rows = settingsActiveMediaPolicyRows()) {
  const counts = rows.reduce((acc, row) => {
    const key = row.posture || "review";
    acc[key] = (acc[key] || 0) + 1;
    return acc;
  }, {});
  const reviewRows = rows.filter((row) => row.posture !== "coherent");
  const lines = [
    "Active media-policy handoff:",
    `Rows: ${rows.length}; coherent=${counts.coherent || 0}; review=${counts.review || 0}; warning=${counts.warning || 0}; blocked=${counts.blocked || 0}.`,
    "This is the operator-facing bridge between Settings builders and Launch saved-settings checks.",
    "Builder edits are not launch-active until backend Preview/Save succeeds and settings reload/refresh completes.",
  ];
  if (reviewRows.length) {
    lines.push("", "Rows needing launch-time attention:");
    reviewRows.forEach((row) => lines.push(`- ${row.area}: ${row.handoff}`));
  } else {
    lines.push("", "No local route/size/subtitle/audio/publish contradictions detected in visible builder state.");
  }
  lines.push("Mutation guardrail: this table is read-only and cannot stage, save, launch, encode, remux, publish, or touch files.");
  return lines;
}

function renderSettingsActiveMediaPolicyHandoff() {
  const rows = settingsActiveMediaPolicyRows();
  setText("settings-active-media-policy-status", settingsActiveMediaPolicyStatus(rows));
  setText("settings-active-media-policy-summary", settingsActiveMediaPolicySummaryLines(rows).join("\n"));
  setText("settings-active-media-policy-legend", "Active media-policy handoff rows are read-only and do not stage, save, launch, encode, remux, publish, or touch files.");
  const tbody = byId("settings-active-media-policy-rows");
  if (!tbody) return;
  if (!rows.length) {
    clearRows(tbody, 4, "No active media-policy handoff rows loaded.");
    return;
  }
  tbody.replaceChildren();
  rows.forEach((item) => {
    const row = document.createElement("tr");
    row.dataset.status = item.posture === "blocked" ? "blocked" : (item.posture === "warning" || item.posture === "review" ? "warning" : "match");
    appendCells(row, [item.area, item.posture, item.evidence, item.handoff]);
    tbody.appendChild(row);
  });
}

function settingsEffectivePolicyRowKey(row) {
  return String(row?.checkpoint || "").toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "") || "policy-row";
}

function settingsEvidenceMatch(evidence, signature) {
  return Boolean(signature && evidence && evidence.signature === signature);
}

function settingsEvidenceResultLabel(evidence, signature) {
  if (!signature || signature === "{}") return "no staged patch";
  if (!evidence) return "missing";
  if (evidence.signature !== signature) return "stale";
  const result = evidence.result || {};
  if (result.ok === true) return Array.isArray(result.warnings) && result.warnings.length ? "fresh with warnings" : "fresh ok";
  if (result.ok === false) return "fresh failed";
  return "fresh unknown";
}

function settingsEffectivePolicyRows(entries) {
  const list = Array.isArray(entries) ? entries : [];
  const changedEntries = list.filter((entry) => entry.changed);
  const unknownEntries = changedEntries.filter((entry) => !entry.field);
  const changedLabels = changedEntries.slice(0, 8).map((entry) => entry.label || entry.key);
  const signature = settingsCurrentPatchSignature();
  const hasStagedPatch = Boolean(signature && signature !== "{}");
  const previewLabel = settingsEvidenceResultLabel(getLastSettingsPatchPreviewEvidence(), signature);
  const saveLabel = settingsEvidenceResultLabel(getLastSettingsPatchSaveEvidence(), signature);
  const previewMatches = settingsEvidenceMatch(getLastSettingsPatchPreviewEvidence(), signature);
  const saveMatches = settingsEvidenceMatch(getLastSettingsPatchSaveEvidence(), signature);
  const previewResult = getLastSettingsPatchPreviewEvidence()?.result || {};
  const saveResult = getLastSettingsPatchSaveEvidence()?.result || {};
  const readiness = settingsBackendMediaPolicyReadiness(getLastSettings());
  const readinessRows = Array.isArray(readiness.rows) ? readiness.rows : [];
  const readinessStatus = settingsBackendMediaPolicyStatus(readiness);
  const readinessBlocked = readinessRows.some((row) => String(row.posture || "").toLowerCase().includes("blocked"));
  const readinessReview = readinessRows.some((row) => {
    const posture = String(row.posture || "").toLowerCase();
    return posture.includes("review") || posture.includes("warning");
  });
  const deltaRows = settingsPolicyDeltaRows(list);
  const deltaStatus = settingsPolicyDeltaStatus(deltaRows);
  const deltaReviewRows = deltaRows.filter((row) => {
    const posture = String(row.posture || "").toLowerCase();
    return posture.includes("blocked") || posture.includes("critical") || posture.includes("review") || posture.includes("preview") || posture.includes("staged");
  });
  const savedKeyCount = Object.keys(getLastSettingsValues() || {}).length;
  const rows = [
    {
      checkpoint: "Launch-active source of truth",
      posture: savedKeyCount ? "saved backend active" : "blocked",
      saved: savedKeyCount ? `${savedKeyCount} loaded config key(s); Launch and pipeline use this saved backend config.` : "No saved config values are loaded in WebView.",
      staged: hasStagedPatch ? `${changedEntries.length} effective staged change(s) remain inactive until backend Save Patch succeeds and settings reload/refresh completes.` : "No staged Changes JSON is active.",
      action: savedKeyCount ? "Use saved backend settings as the operational source of truth. Do not treat visible builder or Changes JSON edits as launch-active." : "Reload settings from disk before launching or saving.",
      detail: [
        `Saved config key count: ${savedKeyCount}`,
        `Staged patch signature: ${signature || "(unavailable)"}`,
        "Launch-active rule: saved backend settings win until backend save and reload/refresh complete.",
      ],
    },
    {
      checkpoint: "Saved media-policy readiness",
      posture: readinessBlocked ? "blocked" : (readinessReview ? "review" : (readinessRows.length ? "coherent" : "not loaded")),
      saved: readinessRows.length ? `Backend readiness status=${readinessStatus}; rows=${readinessRows.length}.` : "No backend media-policy readiness payload is loaded.",
      staged: "Staged Changes JSON does not change saved readiness evidence.",
      action: readinessBlocked
        ? "Resolve blocked saved media-policy rows before unattended runs."
        : "Use this as saved-policy evidence, then verify any staged candidate with Preview Patch before saving.",
      detail: readinessRows.slice(0, 8).map((row) => `${row.area || "Policy"}: ${row.posture || "review"}; ${row.operator_check || row.evidence || ""}`),
    },
    {
      checkpoint: "Staged WebView patch activity",
      posture: unknownEntries.length ? "blocked" : (changedEntries.length ? "staged inactive" : "idle"),
      saved: changedEntries.length ? `${changedEntries.length} effective change(s) differ from saved config.` : "No effective staged change differs from saved config.",
      staged: changedLabels.length ? changedLabels.join(", ") : "No changed staged keys.",
      action: unknownEntries.length
        ? "Unknown keys are schema drift. Do not save until backend Preview Patch explains them."
        : (changedEntries.length ? "Run backend Preview Patch; Save Patch is required before any change can become active." : "No save action is needed for an unchanged patch."),
      detail: [
        `Staged keys: ${list.length}`,
        `Effective changes: ${changedEntries.length}`,
        `Unknown changed keys: ${unknownEntries.length}`,
        `Changed keys: ${changedEntries.map((entry) => entry.key).join(", ") || "(none)"}`,
      ],
    },
    {
      checkpoint: "Backend preview/save proof",
      posture: !hasStagedPatch || !changedEntries.length
        ? "idle"
        : (saveMatches && saveResult.ok === true ? "saved proof present" : (previewMatches && previewResult.ok === true ? "previewed" : "review")),
      saved: `Preview=${previewLabel}; Save=${saveLabel}.`,
      staged: hasStagedPatch ? "Current Changes JSON has a stable signature for evidence matching." : "No staged patch signature is active.",
      action: !changedEntries.length
        ? "No preview/save proof is needed for an unchanged patch."
        : (saveMatches && saveResult.ok === true
            ? "Reload/refresh settings before treating saved changes as launch-active."
            : (previewMatches && previewResult.ok === true
                ? "Preview matches current JSON. Save Patch still requires explicit confirmation and backend success."
                : "Run Preview Patch before Save Patch; stale or missing preview evidence is not enough.")),
      detail: [
        `Current patch signature: ${signature || "(unavailable)"}`,
        `Preview evidence: ${previewLabel}`,
        `Save evidence: ${saveLabel}`,
        `Preview command ok: ${previewResult.ok === true ? "yes" : previewResult.ok === false ? "no" : "unknown"}`,
        `Save command ok: ${saveResult.ok === true ? "yes" : saveResult.ok === false ? "no" : "unknown"}`,
      ],
    },
    {
      checkpoint: "Policy delta attention",
      posture: deltaStatus === "Blocked review" ? "blocked" : (deltaStatus === "No blocker" || deltaStatus === "No staged change" ? "coherent" : "review"),
      saved: `Delta status=${deltaStatus}; saved values remain active.`,
      staged: deltaReviewRows.length ? `${deltaReviewRows.length} staged policy row(s) need attention.` : "No staged media-policy contradictions detected locally.",
      action: deltaReviewRows.length
        ? "Review the first changed policy rows below and confirm backend Preview Patch before save."
        : "No local staged media-policy blocker is visible; backend preview remains authoritative.",
      detail: deltaReviewRows.slice(0, 8).map((row) => `${row.area}: ${row.posture}; ${row.check}`),
    },
    {
      checkpoint: "Mutation boundary",
      posture: "backend-owned",
      saved: "Settings display, builders, deltas, and trust rows are read-only until a backend command is sent.",
      staged: "Preview Patch is non-writing. Save Patch is the only persistence command and requires confirmation.",
      action: "This panel cannot save config, launch work, run FFmpeg, rename files, drain pending publish, or touch source media.",
      detail: [
        "Boundary: frontend may stage JSON and request backend commands only.",
        "Backend owns PSD1 serialization, backups, validation, risk classification, and settings reload evidence.",
      ],
    },
  ];
  return rows;
}

function settingsEffectivePolicyTrustStatus(rows = settingsEffectivePolicyRows(settingsPatchImpactEntries(parseSettingsPatchJson()))) {
  if (!rows.length) return "Not evaluated";
  if (rows.some((row) => String(row.posture || "").includes("blocked"))) return "Blocked review";
  if (rows.some((row) => ["review", "staged inactive", "previewed"].includes(String(row.posture || "")))) return "Review";
  return "Trusted saved policy";
}

function settingsEffectivePolicySummaryLines(rows = settingsEffectivePolicyRows(settingsPatchImpactEntries(parseSettingsPatchJson()))) {
  const counts = rows.reduce((acc, row) => {
    const key = String(row.posture || "unknown").toLowerCase();
    acc[key] = (acc[key] || 0) + 1;
    return acc;
  }, {});
  const reviewRows = rows.filter((row) => {
    const posture = String(row.posture || "").toLowerCase();
    return posture.includes("blocked") || posture.includes("review") || posture.includes("staged") || posture.includes("preview");
  });
  const lines = [
    "Effective policy trust summary:",
    `Status: ${settingsEffectivePolicyTrustStatus(rows)}`,
    `Rows: ${rows.length}; blocked=${counts.blocked || 0}; review=${counts.review || 0}; staged-inactive=${counts["staged inactive"] || 0}; previewed=${counts.previewed || 0}; saved-backend-active=${counts["saved backend active"] || 0}.`,
    "Launch-active policy is the saved backend config. WebView builder values and Changes JSON are candidates only.",
    "Backend Preview Patch is non-writing. Save Patch plus settings reload/refresh is required before staged policy can affect a run.",
  ];
  if (reviewRows.length) {
    lines.push("", "First operator checks:");
    reviewRows.slice(0, 6).forEach((row) => lines.push(`- ${row.checkpoint}: ${row.action}`));
  } else {
    lines.push("", "No local trust contradiction detected. Continue to backend preview/save only if you intend to change settings.");
  }
  lines.push("", "Mutation guardrail: this summary is read-only and cannot save settings, launch work, mutate queues, publish, rename, or touch media.");
  return lines;
}

function settingsEffectivePolicyDetailLines(row) {
  if (!row) {
    return [
      "No effective policy row selected.",
      "Select a row to inspect launch-active state, staged-state limitations, preview/save evidence, and backend ownership.",
      "Mutation guardrail: this detail view is read-only and cannot save settings or touch media.",
    ];
  }
  const lines = [
    `Checkpoint: ${row.checkpoint}`,
    `Posture: ${row.posture}`,
    `Saved backend state: ${row.saved}`,
    `Staged WebView state: ${row.staged}`,
    `Operator action: ${row.action}`,
  ];
  const detail = Array.isArray(row.detail) ? row.detail.filter(Boolean) : [];
  if (detail.length) {
    lines.push("", "Proof / detail:");
    detail.forEach((item) => lines.push(`- ${item}`));
  }
  lines.push("", "Mutation guardrail: effective-policy trust is display-only; backend Preview/Save owns validation and persistence.");
  return lines;
}

function selectedSettingsEffectivePolicyRow(rows) {
  const selectedKey = getSelectedSettingsEffectivePolicyKey();
  if (!selectedKey) return null;
  return (Array.isArray(rows) ? rows : []).find((row) => settingsEffectivePolicyRowKey(row) === selectedKey) || null;
}

function renderSettingsEffectivePolicyTrustFromEntries(entries) {
  const rows = settingsEffectivePolicyRows(entries);
  let selectedKey = getSelectedSettingsEffectivePolicyKey();
  if (selectedKey && !rows.some((row) => settingsEffectivePolicyRowKey(row) === selectedKey)) {
    setSelectedSettingsEffectivePolicyKey("");
    selectedKey = "";
  }
  if (!selectedKey && rows.length) {
    setSelectedSettingsEffectivePolicyKey(settingsEffectivePolicyRowKey(rows[0]));
    selectedKey = getSelectedSettingsEffectivePolicyKey();
  }
  setText("settings-effective-policy-status", settingsEffectivePolicyTrustStatus(rows));
  setText("settings-effective-policy-summary", settingsEffectivePolicySummaryLines(rows).join("\n"));
  setText("settings-effective-policy-legend", "Effective policy trust rows are read-only; backend Preview/Save remains the only settings persistence boundary.");
  setText("settings-effective-policy-detail", settingsEffectivePolicyDetailLines(selectedSettingsEffectivePolicyRow(rows)).join("\n"));
  const tbody = byId("settings-effective-policy-rows");
  if (!tbody) return;
  if (!rows.length) {
    clearRows(tbody, 5, "No effective policy trust rows loaded.");
    return;
  }
  tbody.replaceChildren();
  rows.forEach((item) => {
    const row = document.createElement("tr");
    const posture = String(item.posture || "").toLowerCase();
    row.dataset.status = posture.includes("blocked")
      ? "blocked"
      : posture.includes("review") || posture.includes("staged") || posture.includes("preview")
        ? "warning"
        : "match";
    const key = settingsEffectivePolicyRowKey(item);
    appendCells(row, [item.checkpoint, item.posture, item.saved, item.staged, item.action]);
    makeRowSelectable(row, () => {
      setSelectedSettingsEffectivePolicyKey(key);
      renderSettingsEffectivePolicyTrustFromEntries(entries);
    }, {
      selected: selectedKey === key,
      label: `Inspect effective policy checkpoint ${item.checkpoint}`,
    });
    tbody.appendChild(row);
  });
  updateTableStatusLegend("settings-effective-policy-legend", tbody, "Effective policy trust rows");
}

function renderSettingsEffectivePolicyTrustForError(message) {
  setText("settings-effective-policy-status", "Invalid JSON");
  setText(
    "settings-effective-policy-summary",
    [
      "Effective policy trust summary unavailable because Changes JSON is invalid.",
      message,
      "Saved backend settings remain launch-active; staged Changes JSON cannot be previewed or saved until it is valid JSON.",
      "Mutation guardrail: invalid JSON handling is local UI feedback only and does not write config.",
    ].join("\n")
  );
  clearRows(byId("settings-effective-policy-rows"), 5, "Effective policy trust unavailable because Changes JSON is invalid.");
  setText("settings-effective-policy-legend", "Effective policy trust rows are read-only; backend Preview/Save remains the only settings persistence boundary.");
  setText("settings-effective-policy-detail", [
    "Effective policy trust detail:",
    `Patch JSON is invalid: ${message}`,
    "Fix Changes JSON before Preview Patch or Save Patch can run.",
    "Launch-active rule: saved backend settings remain active.",
  ].join("\n"));
}

function settingsMediaPolicySummaryLines(rows = settingsMediaPolicyRows()) {
  const counts = rows.reduce((acc, row) => {
    const key = row.posture || "review";
    acc[key] = (acc[key] || 0) + 1;
    return acc;
  }, {});
  const reviewRows = rows.filter((row) => row.posture !== "coherent");
  const lines = [
    "Audio / subtitle policy cross-check:",
    `Rows: ${rows.length}; coherent=${counts.coherent || 0}; review=${counts.review || 0}; warning=${counts.warning || 0}; blocked=${counts.blocked || 0}.`,
    "SRT creation, original-track preservation, language routing, and audio predictability are checked from the visible builder state.",
    "Preview/Save remains backend-owned; this panel does not change FFmpeg, subtitle, audio, remux, encode, or publish behavior.",
  ];
  if (reviewRows.length) {
    lines.push("", "Rows needing review:");
    reviewRows.forEach((row) => lines.push(`- ${row.area}: ${row.action}`));
  } else {
    lines.push("", "No local audio/subtitle contradictions detected. Run backend Preview Patch before saving.");
  }
  return lines;
}

function renderSettingsMediaPolicyCrossCheck() {
  const rows = settingsMediaPolicyRows();
  setText("settings-media-policy-status", settingsMediaPolicyStatus(rows));
  setText("settings-media-policy-summary", settingsMediaPolicySummaryLines(rows).join("\n"));
  setText("settings-media-policy-legend", "Audio/subtitle policy rows are read-only and have no selectable actions.");
  const tbody = byId("settings-media-policy-rows");
  if (!rows.length) {
    clearRows(tbody, 4, "No audio/subtitle policy rows loaded.");
    return;
  }
  tbody.replaceChildren();
  rows.forEach((item) => {
    const row = document.createElement("tr");
    row.dataset.status = item.posture === "blocked" ? "blocked" : (item.posture === "warning" || item.posture === "review" ? "warning" : "match");
    appendCells(row, [item.area, item.posture, item.evidence, item.action]);
    tbody.appendChild(row);
  });
}

function settingsBackendPolicyImpact(settings = getLastSettings()) {
  const impact = settings?.policy_impact || {};
  if (!impact || impact.schema_version !== "settings_policy_impact.v1") {
    return { schema_version: "", media_policy_readiness: null, launch_risk_handoff: null };
  }
  return impact;
}

function settingsBackendMediaPolicyReadiness(settings = getLastSettings()) {
  const policyImpact = settingsBackendPolicyImpact(settings);
  const readiness = policyImpact.media_policy_readiness || settings?.media_policy_readiness || {};
  if (!readiness || readiness.schema_version !== "settings_media_policy_readiness.v1") {
    return { operator_status: "Not loaded", rows: [], counts: {}, summary_lines: [] };
  }
  return readiness;
}

function settingsBackendMediaPolicyStatus(readiness = settingsBackendMediaPolicyReadiness()) {
  return readiness.operator_status || "Not evaluated";
}

function settingsBackendMediaPolicySummaryLines(readiness = settingsBackendMediaPolicyReadiness()) {
  const rows = Array.isArray(readiness.rows) ? readiness.rows : [];
  const lines = Array.isArray(readiness.summary_lines) && readiness.summary_lines.length
    ? readiness.summary_lines.slice()
    : [
      "Backend media-policy readiness:",
      `Status: ${settingsBackendMediaPolicyStatus(readiness)}; rows=${rows.length}.`,
      "This is read-only evidence from saved backend settings.",
    ];
  lines.push("", "Mutation guardrail: this table cannot stage settings, save config, launch work, run FFmpeg, publish files, or touch source media.");
  return lines;
}

function renderSettingsBackendMediaPolicyReadiness(settings = getLastSettings()) {
  const readiness = settingsBackendMediaPolicyReadiness(settings);
  const rows = Array.isArray(readiness.rows) ? readiness.rows : [];
  setText("settings-backend-media-policy-status", settingsBackendMediaPolicyStatus(readiness));
  setText("settings-backend-media-policy-summary", settingsBackendMediaPolicySummaryLines(readiness).join("\n"));
  setText("settings-backend-media-policy-legend", "Backend media-policy readiness rows are read-only and have no selectable actions.");
  const tbody = byId("settings-backend-media-policy-rows");
  if (!tbody) return;
  if (!rows.length) {
    clearRows(tbody, 4, "No backend media-policy readiness rows loaded.");
    return;
  }
  tbody.replaceChildren();
  rows.forEach((item) => {
    const posture = String(item.posture || "review").toLowerCase();
    const row = document.createElement("tr");
    row.dataset.status = posture === "blocked" ? "blocked" : posture === "review" ? "warning" : "match";
    appendCells(row, [
      item.area || "Policy",
      item.posture || "review",
      item.evidence || "",
      item.operator_check || "Review saved media-policy setting.",
    ]);
    tbody.appendChild(row);
  });
}

function settingsImpactGroupForKey(key) {
  return settingsImpactGroups.find((group) => group.keys.includes(key)) || null;
}

function settingsPatchEntryStatus(key, staged) {
  const field = settingsFieldDefinition(key);
  const current = settingsRawConfigValue(key);
  if (!field) return { field, current, changed: true, status: "unknown key" };
  if (settingsValuesEqual(current, staged)) return { field, current, changed: false, status: "unchanged" };
  return { field, current, changed: true, status: current === undefined ? "new value" : "changed" };
}

function settingsPatchImpactSeverity(entries) {
  if (entries.some((entry) => entry.severity === "high")) return "high";
  if (entries.some((entry) => entry.severity === "medium")) return "medium";
  return entries.length ? "low" : "none";
}

function settingsPatchImpactEntries(patch) {
  return Object.keys(patch || {}).sort((a, b) => a.localeCompare(b)).map((key) => {
    const status = settingsPatchEntryStatus(key, patch[key]);
    const group = settingsImpactGroupForKey(key);
    return {
      key,
      staged: patch[key],
      group,
      severity: status.field ? (group?.severity || "low") : "high",
      label: status.field?.label || key,
      ...status,
    };
  });
}

function renderSettingsPatchImpactSummaryFromEntries(entries) {
  const changedEntries = entries.filter((entry) => entry.changed);
  const unknownEntries = entries.filter((entry) => !entry.field);
  const severity = settingsPatchImpactSeverity(changedEntries);
  const lines = [
    `Local impact: ${severity === "none" ? "none" : severity}`,
    `Changed/new keys: ${changedEntries.length}; unchanged keys: ${entries.length - changedEntries.length}; unknown keys: ${unknownEntries.length}`,
    "Backend preview remains the source of truth before saving.",
  ];
  if (!changedEntries.length) {
    lines.push("No effective staged changes detected.");
    setText("settings-patch-impact-summary", lines.join("\n"));
    return;
  }
  const grouped = new Map();
  changedEntries.forEach((entry) => {
    const groupName = entry.group?.name || "Unknown / custom";
    if (!grouped.has(groupName)) grouped.set(groupName, []);
    grouped.get(groupName).push(entry);
  });
  grouped.forEach((groupEntries, groupName) => {
    const group = groupEntries[0].group;
    lines.push("", `${groupName}: ${groupEntries.length} key${groupEntries.length === 1 ? "" : "s"}`);
    if (group?.note) lines.push(`  ${group.note}`);
    groupEntries.slice(0, 8).forEach((entry) => {
      const currentText = entry.current === undefined ? "(not set)" : formatConfigValue(entry.current);
      lines.push(`  - ${entry.label}: ${currentText} -> ${formatConfigValue(entry.staged)} (${entry.status})`);
      const hint = settingsSpecificImpactHints[entry.key];
      if (hint) lines.push(`    ${hint}`);
    });
    if (groupEntries.length > 8) lines.push(`  - ${groupEntries.length - 8} more key(s) in this group.`);
  });
  setText("settings-patch-impact-summary", lines.join("\n"));
}

function settingsBoolValue(value) {
  if (typeof value === "boolean") return value;
  if (value === undefined || value === null || value === "") return null;
  const normalized = String(value).trim().toLowerCase();
  if (["true", "1", "yes", "y", "on", "enabled"].includes(normalized)) return true;
  if (["false", "0", "no", "n", "off", "disabled"].includes(normalized)) return false;
  return null;
}

function settingsPatchCandidateValue(entries, key) {
  const entry = entries.find((item) => item.key === key);
  return entry ? entry.staged : settingsRawConfigValue(key);
}

function settingsStableJsonValue(value) {
  if (Array.isArray(value)) return value.map(settingsStableJsonValue);
  if (value && typeof value === "object") {
    const ordered = {};
    Object.keys(value).sort((left, right) => left.localeCompare(right)).forEach((key) => {
      ordered[key] = settingsStableJsonValue(value[key]);
    });
    return ordered;
  }
  return value;
}

function settingsPatchSignature(changes) {
  try {
    return JSON.stringify(settingsStableJsonValue(changes || {}));
  } catch (_error) {
    return "";
  }
}

function settingsCurrentPatchSignature() {
  try {
    return settingsPatchSignature(parseSettingsPatchJson());
  } catch (_error) {
    return "";
  }
}

function settingsPatchListValue(value) {
  if (Array.isArray(value)) return value.map((item) => String(item).trim()).filter(Boolean);
  if (typeof value === "string") return parseSettingsListText(value);
  return value === undefined || value === null || value === "" ? [] : [String(value)];
}

function settingsPatchCandidateText(entries, key, fallback = "") {
  const value = settingsPatchCandidateValue(entries, key);
  if (value === undefined || value === null || value === "") return String(fallback ?? "");
  return String(value).trim();
}

function settingsPatchCandidateNumber(entries, key, fallback = 0) {
  const value = Number(settingsPatchCandidateValue(entries, key));
  return Number.isFinite(value) ? value : Number(fallback || 0);
}

function settingsPatchCandidateBool(entries, key, fallback = false) {
  const value = settingsBoolValue(settingsPatchCandidateValue(entries, key));
  if (value === null) return Boolean(fallback);
  return value;
}

function settingsPatchCandidateList(entries, key, fallback = []) {
  const value = settingsPatchCandidateValue(entries, key);
  if (value === undefined) return Array.isArray(fallback) ? fallback.slice() : settingsPatchListValue(fallback);
  return settingsPatchListValue(value);
}

function settingsPatchCurrentText(key, fallback = "") {
  const value = settingsRawConfigValue(key);
  if (value === undefined || value === null || value === "") return String(fallback ?? "");
  return String(value).trim();
}

function settingsPatchCurrentNumber(key, fallback = 0) {
  const value = Number(settingsRawConfigValue(key));
  return Number.isFinite(value) ? value : Number(fallback || 0);
}

function settingsPatchCurrentBool(key, fallback = false) {
  const value = settingsBoolValue(settingsRawConfigValue(key));
  if (value === null) return Boolean(fallback);
  return value;
}

function settingsPatchCurrentList(key, fallback = []) {
  const value = settingsRawConfigValue(key);
  if (value === undefined) return Array.isArray(fallback) ? fallback.slice() : settingsPatchListValue(fallback);
  return settingsPatchListValue(value);
}

function settingsPolicyDeltaChangedLabels(entries, keys) {
  const wanted = new Set(keys);
  return entries
    .filter((entry) => entry.changed && wanted.has(entry.key))
    .map((entry) => entry.label || entry.key);
}

function settingsPolicyDeltaChangedText(entries, keys) {
  const labels = settingsPolicyDeltaChangedLabels(entries, keys);
  return labels.length ? `Changed: ${labels.join(", ")}.` : "No effective staged change in this area.";
}

function settingsPolicyDeltaBoolText(value) {
  return value ? "on" : "off";
}

function settingsPolicyDeltaStatus(rows) {
  if (!rows.length) return "No staged change";
  const postures = rows.map((row) => String(row.posture || "").toLowerCase());
  if (postures.some((posture) => posture.includes("blocked") || posture.includes("critical"))) return "Blocked review";
  if (postures.some((posture) => posture.includes("high"))) return "High review";
  if (postures.some((posture) => posture.includes("review") || posture.includes("staged") || posture.includes("preview"))) return "Preview required";
  return "No blocker";
}

// Frontend advisory only: backend Preview Patch and Save Patch remain
// authoritative for schema validation, source-deletion acceptance, and PSD1 writes.
function settingsPolicyDeltaRows(entries) {
  const changedEntries = entries.filter((entry) => entry.changed);
  const unknownEntries = changedEntries.filter((entry) => !entry.field);
  const rows = [];

  rows.push({
    area: "Patch scope",
    posture: !changedEntries.length ? "idle" : unknownEntries.length ? "blocked" : "staged",
    current: `${entries.length} staged key(s); ${changedEntries.length} effective change(s).`,
    candidate: unknownEntries.length
      ? `${unknownEntries.length} unknown key(s): ${unknownEntries.slice(0, 6).map((entry) => entry.key).join(", ")}${unknownEntries.length > 6 ? ", ..." : ""}`
      : `${changedEntries.length} known effective change(s).`,
    check: changedEntries.length
      ? "Run backend Preview Patch before Save Patch; Launch continues using saved settings until backend save/reload succeeds."
      : "No effective settings change is staged.",
  });

  const routingKeys = [
    "RoutingProfile",
    "RouteThresholdMode",
    "SizeGuardMode",
    "MovieRoute1080pTargetSizeGB",
    "MovieRoute1440pTargetSizeGB",
    "MovieRoute4KTargetSizeGB",
    "TVRoute1080pTargetSizeGB",
    "TVRoute1440pTargetSizeGB",
    "TVRoute4KTargetSizeGB",
    "Route1080pUpperHeightTolerancePercent",
    "Route1080pMaxVideoBitrateMbps",
    "Route1440pLowerHeightTolerancePercent",
    "Route1440pUpperHeightTolerancePercent",
    "Route1440pMaxVideoBitrateMbps",
    "Route4KLowerHeightTolerancePercent",
    "Route4KMaxVideoBitrateMbps",
    "MaxEncodeGrowthPercent",
    "CompatibilityEncodeGrowthPercent",
  ];
  const currentRouteThresholdMode = settingsPatchCurrentText("RouteThresholdMode", "compatibility_advisory").toLowerCase();
  const nextRouteThresholdMode = settingsPatchCandidateText(entries, "RouteThresholdMode", "compatibility_advisory").toLowerCase();
  const currentSizeGuard = settingsPatchCurrentText("SizeGuardMode", "advisory").toLowerCase();
  const nextSizeGuard = settingsPatchCandidateText(entries, "SizeGuardMode", "advisory").toLowerCase();
  const currentMaxGrowth = settingsPatchCurrentNumber("MaxEncodeGrowthPercent", 5);
  const nextMaxGrowth = settingsPatchCandidateNumber(entries, "MaxEncodeGrowthPercent", 5);
  const currentCompatGrowth = settingsPatchCurrentNumber("CompatibilityEncodeGrowthPercent", 15);
  const nextCompatGrowth = settingsPatchCandidateNumber(entries, "CompatibilityEncodeGrowthPercent", 15);
  const currentRouteBoundaries = settingsPatchRouteHeightBoundaries(entries, "current");
  const nextRouteBoundaries = settingsPatchRouteHeightBoundaries(entries, "candidate");
  rows.push({
    area: "Routing / output-size guard",
    posture: ["off", "disabled"].includes(nextSizeGuard) || nextMaxGrowth > 15 || nextCompatGrowth > 30 ? "review" : (settingsPolicyDeltaChangedLabels(entries, routingKeys).length ? "preview required" : "unchanged"),
    current: `profile=${formatSettingsChoiceLabel(settingsPatchCurrentText("RoutingProfile", "plex_direct_stream"))}; threshold=${formatSettingsChoiceLabel(currentRouteThresholdMode)}; guard=${formatSettingsChoiceLabel(currentSizeGuard)}; growth=${currentMaxGrowth}%/${currentCompatGrowth}%; size targets 1080p=${settingsPatchCurrentNumber("MovieRoute1080pTargetSizeGB", 8)}/${settingsPatchCurrentNumber("TVRoute1080pTargetSizeGB", 3)}GB, 1440p=${settingsPatchCurrentNumber("MovieRoute1440pTargetSizeGB", 8)}/${settingsPatchCurrentNumber("TVRoute1440pTargetSizeGB", 3)}GB, 4K=${settingsPatchCurrentNumber("MovieRoute4KTargetSizeGB", 8)}/${settingsPatchCurrentNumber("TVRoute4KTargetSizeGB", 3)}GB; unknown height uses 1080p targets and ${settingsPatchCurrentNumber("Route1080pMaxVideoBitrateMbps", 20)}Mbps cap; buckets 1080p<=${currentRouteBoundaries.route1080pMaxHeight}p ${settingsPatchCurrentNumber("Route1080pMaxVideoBitrateMbps", 20)}Mbps, 1440p ${currentRouteBoundaries.route1440pMinHeight}-${currentRouteBoundaries.route1440pMaxHeight}p ${settingsPatchCurrentNumber("Route1440pMaxVideoBitrateMbps", 35)}Mbps, 4K>=${currentRouteBoundaries.route4kMinHeight}p ${settingsPatchCurrentNumber("Route4KMaxVideoBitrateMbps", 35)}Mbps`,
    candidate: `profile=${formatSettingsChoiceLabel(settingsPatchCandidateText(entries, "RoutingProfile", "plex_direct_stream"))}; threshold=${formatSettingsChoiceLabel(nextRouteThresholdMode)}; guard=${formatSettingsChoiceLabel(nextSizeGuard)}; growth=${nextMaxGrowth}%/${nextCompatGrowth}%; size targets 1080p=${settingsPatchCandidateNumber(entries, "MovieRoute1080pTargetSizeGB", 8)}/${settingsPatchCandidateNumber(entries, "TVRoute1080pTargetSizeGB", 3)}GB, 1440p=${settingsPatchCandidateNumber(entries, "MovieRoute1440pTargetSizeGB", 8)}/${settingsPatchCandidateNumber(entries, "TVRoute1440pTargetSizeGB", 3)}GB, 4K=${settingsPatchCandidateNumber(entries, "MovieRoute4KTargetSizeGB", 8)}/${settingsPatchCandidateNumber(entries, "TVRoute4KTargetSizeGB", 3)}GB; unknown height uses 1080p targets and ${settingsPatchCandidateNumber(entries, "Route1080pMaxVideoBitrateMbps", 20)}Mbps cap; buckets 1080p<=${nextRouteBoundaries.route1080pMaxHeight}p ${settingsPatchCandidateNumber(entries, "Route1080pMaxVideoBitrateMbps", 20)}Mbps, 1440p ${nextRouteBoundaries.route1440pMinHeight}-${nextRouteBoundaries.route1440pMaxHeight}p ${settingsPatchCandidateNumber(entries, "Route1440pMaxVideoBitrateMbps", 35)}Mbps, 4K>=${nextRouteBoundaries.route4kMinHeight}p ${settingsPatchCandidateNumber(entries, "Route4KMaxVideoBitrateMbps", 35)}Mbps`,
    check: `${settingsPolicyDeltaChangedText(entries, routingKeys)} The output-size guard and growth limits affect remux-vs-encode trust and oversized-output review.`,
  });

  const videoKeys = [
    "VideoCodec",
    "EncodeTuningPreset",
    "EncodeLadder",
    "AllowH264RemuxIfPlexCompatible",
    "H264RemuxMaxBitrateMbps",
    "H264RemuxMaxHeight",
    "RemuxSafeVideoCodecs",
    "ExtraVideoFlags",
  ];
  const nextH264Copy = settingsPatchCandidateBool(entries, "AllowH264RemuxIfPlexCompatible", true);
  const nextExtraFlags = settingsPatchCandidateList(entries, "ExtraVideoFlags", []);
  rows.push({
    area: "Video route / encoder precision",
    posture: !nextH264Copy || nextExtraFlags.length ? "review" : (settingsPolicyDeltaChangedLabels(entries, videoKeys).length ? "preview required" : "unchanged"),
    current: `codec=${formatSettingsChoiceLabel(settingsPatchCurrentText("VideoCodec", "hevc_nvenc"))}; H.264 copy=${settingsPolicyDeltaBoolText(settingsPatchCurrentBool("AllowH264RemuxIfPlexCompatible", true))}; safe=${settingsPatchCurrentList("RemuxSafeVideoCodecs", ["hevc", "h265", "h264", "avc"]).join(", ") || "(empty)"}; raw flags=${settingsPatchCurrentList("ExtraVideoFlags", []).length}`,
    candidate: `codec=${formatSettingsChoiceLabel(settingsPatchCandidateText(entries, "VideoCodec", "hevc_nvenc"))}; H.264 copy=${settingsPolicyDeltaBoolText(nextH264Copy)} <=${settingsPatchCandidateNumber(entries, "H264RemuxMaxBitrateMbps", 35)}Mbps/${settingsPatchCandidateNumber(entries, "H264RemuxMaxHeight", 1080)}p; safe=${settingsPatchCandidateList(entries, "RemuxSafeVideoCodecs", ["hevc", "h265", "h264", "avc"]).join(", ") || "(empty)"}; raw flags=${nextExtraFlags.length}`,
    check: nextExtraFlags.length
      ? "Legacy FFmpeg flags are staged. Backend preview must review them before any route or size policy depends on this patch."
      : `${settingsPolicyDeltaChangedText(entries, videoKeys)} Compatible low-bitrate H.264 should normally remain copy/remux eligible.`,
  });

  const subtitleKeys = [
    "OutputContainer",
    "SubKeepLanguages",
    "Tx3gExtractLanguages",
    "BdpgsExtractLanguages",
    "VobSubExtractLanguages",
    "ConvertTx3gToSrt",
    "DropTx3gAfterConversion",
    "CreateExternalTx3gSrtSidecars",
    "ConvertBdpgsToSrt",
    "DropBdpgsAfterConversion",
    "ConvertVobSubToSrt",
    "DropVobSubAfterConversion",
    "DropAssAfterConversion",
    "StripFormatting",
    "RemoveKaraoke",
    "KeepSignsAndSongs",
  ];
  const nextContainer = settingsPatchCandidateText(entries, "OutputContainer", "mkv").toLowerCase();
  const nextConvertTx3g = settingsPatchCandidateBool(entries, "ConvertTx3gToSrt", true);
  const nextDropTx3g = settingsPatchCandidateBool(entries, "DropTx3gAfterConversion", false);
  const nextConvertBdpgs = settingsPatchCandidateBool(entries, "ConvertBdpgsToSrt", false);
  const nextDropBdpgs = settingsPatchCandidateBool(entries, "DropBdpgsAfterConversion", false);
  const nextConvertVobSub = settingsPatchCandidateBool(entries, "ConvertVobSubToSrt", false);
  const nextDropVobSub = settingsPatchCandidateBool(entries, "DropVobSubAfterConversion", false);
  const nextDropAss = settingsPatchCandidateBool(entries, "DropAssAfterConversion", false);
  const subtitleBlocked = (nextDropTx3g && !nextConvertTx3g) || (nextDropBdpgs && !nextConvertBdpgs) || (nextDropVobSub && !nextConvertVobSub);
  rows.push({
    area: "Container / subtitle preservation",
    posture: subtitleBlocked ? "blocked" : (nextContainer === "mp4" || nextDropTx3g || nextDropBdpgs || nextDropVobSub || nextDropAss || !nextConvertTx3g || !nextConvertBdpgs || !nextConvertVobSub ? "review" : (settingsPolicyDeltaChangedLabels(entries, subtitleKeys).length ? "preview required" : "unchanged")),
    current: `container=${formatSettingsChoiceLabel(settingsPatchCurrentText("OutputContainer", "mkv"))}; TX3G=${settingsPolicyDeltaBoolText(settingsPatchCurrentBool("ConvertTx3gToSrt", true))}/${settingsPolicyDeltaBoolText(settingsPatchCurrentBool("DropTx3gAfterConversion", false))}; BDPGS=${settingsPolicyDeltaBoolText(settingsPatchCurrentBool("ConvertBdpgsToSrt", false))}/${settingsPolicyDeltaBoolText(settingsPatchCurrentBool("DropBdpgsAfterConversion", false))}; VobSub=${settingsPolicyDeltaBoolText(settingsPatchCurrentBool("ConvertVobSubToSrt", false))}/${settingsPolicyDeltaBoolText(settingsPatchCurrentBool("DropVobSubAfterConversion", false))}; ASS drop=${settingsPolicyDeltaBoolText(settingsPatchCurrentBool("DropAssAfterConversion", false))}`,
    candidate: `container=${formatSettingsChoiceLabel(nextContainer)}; keep=${settingsPatchCandidateList(entries, "SubKeepLanguages", ["eng", "und"]).join(", ") || "(empty)"}; TX3G=${settingsPolicyDeltaBoolText(nextConvertTx3g)}/${settingsPolicyDeltaBoolText(nextDropTx3g)}; BDPGS=${settingsPolicyDeltaBoolText(nextConvertBdpgs)}/${settingsPolicyDeltaBoolText(nextDropBdpgs)}; VobSub=${settingsPolicyDeltaBoolText(nextConvertVobSub)}/${settingsPolicyDeltaBoolText(nextDropVobSub)}; ASS drop=${settingsPolicyDeltaBoolText(nextDropAss)}`,
    check: subtitleBlocked
      ? "Do not drop TX3G/BDPGS/VobSub originals when the matching SRT/OCR conversion is disabled."
      : `${settingsPolicyDeltaChangedText(entries, subtitleKeys)} Default Plex posture is add preferred-language SRT while preserving original subtitles unless a drop toggle is explicit.`,
  });

  const audioKeys = [
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
  const nextAudioProfile = settingsPatchCandidateText(entries, "AudioPassthroughProfile", "plex_balanced");
  const nextAudioCodecs = settingsPatchCandidateList(entries, "CompatibleAudioCodecs", ["aac", "ac3", "eac3", "mp3", "opus", "vorbis"]);
  const nextAudioLanguages = settingsPatchCandidateList(entries, "PreferredDefaultAudioLanguages", ["english"]);
  const nextAllowNoAudio = settingsPatchCandidateBool(entries, "AllowNoAudio", false);
  rows.push({
    area: "Audio direct-play predictability",
    posture: nextAllowNoAudio || (nextAudioProfile === "custom_codec_list" && !nextAudioCodecs.length) ? "blocked" : (!nextAudioLanguages.length || nextAudioProfile === "lossless_passthrough" || nextAudioProfile === "custom_codec_list" || settingsPatchCandidateNumber(entries, "AudioMaxChannels", 6) < 6 ? "review" : (settingsPolicyDeltaChangedLabels(entries, audioKeys).length ? "preview required" : "unchanged")),
    current: `profile=${formatSettingsChoiceLabel(settingsPatchCurrentText("AudioPassthroughProfile", "plex_balanced"))}; languages=${settingsPatchCurrentList("PreferredDefaultAudioLanguages", ["english"]).join(", ") || "(empty)"}; downmix=${formatSettingsChoiceLabel(settingsPatchCurrentText("AudioDownmixMode", "max_channels"))}; max=${settingsPatchCurrentNumber("AudioMaxChannels", 6)}; no-audio=${settingsPolicyDeltaBoolText(settingsPatchCurrentBool("AllowNoAudio", false))}`,
    candidate: `profile=${formatSettingsChoiceLabel(nextAudioProfile)}; codecs=${nextAudioCodecs.join(", ") || "(empty)"}; languages=${nextAudioLanguages.join(", ") || "(empty)"}; downmix=${formatSettingsChoiceLabel(settingsPatchCandidateText(entries, "AudioDownmixMode", "max_channels"))}; max=${settingsPatchCandidateNumber(entries, "AudioMaxChannels", 6)}; no-audio=${settingsPolicyDeltaBoolText(nextAllowNoAudio)}`,
    check: nextAllowNoAudio
      ? "No-audio outputs should stay disabled for normal Plex publishing."
      : `${settingsPolicyDeltaChangedText(entries, audioKeys)} Preferred-language defaults and passthrough policy should be intentional before unattended runs.`,
  });

  const publishKeys = [
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
  const nextDeleteSource = settingsPatchCandidateBool(entries, "DeleteSourceAfterProcessing", false);
  const nextSkipStability = settingsPatchCandidateBool(entries, "SkipStabilityCheck", false);
  const nextIntegrity = settingsPatchCandidateBool(entries, "EnableIntegrityCheck", true);
  const nextCleanupRemote = settingsPatchCandidateBool(entries, "CleanupRemoteStaging", false);
  rows.push({
    area: "Publish / source safety",
    posture: nextDeleteSource ? "critical blocked" : (nextSkipStability || !nextIntegrity || nextCleanupRemote ? "review" : (settingsPolicyDeltaChangedLabels(entries, publishKeys).length ? "preview required" : "unchanged")),
    current: `deferred=${settingsPolicyDeltaBoolText(settingsPatchCurrentBool("DeferredPublish", false))}; cleanup remote=${settingsPolicyDeltaBoolText(settingsPatchCurrentBool("CleanupRemoteStaging", false))}; stability=${settingsPatchCurrentBool("SkipStabilityCheck", false) ? "skipped" : "enabled"}; integrity=${settingsPatchCurrentBool("EnableIntegrityCheck", true) ? "enabled" : "disabled"}; delete source=${settingsPolicyDeltaBoolText(settingsPatchCurrentBool("DeleteSourceAfterProcessing", false))}`,
    candidate: `deferred=${settingsPolicyDeltaBoolText(settingsPatchCandidateBool(entries, "DeferredPublish", false))}; cleanup remote=${settingsPolicyDeltaBoolText(nextCleanupRemote)}; stability=${nextSkipStability ? "skipped" : "enabled"}; integrity=${nextIntegrity ? "enabled" : "disabled"}; delete source=${settingsPolicyDeltaBoolText(nextDeleteSource)}; copy timeout=${settingsPatchCandidateNumber(entries, "RobocopyTimeoutSeconds", 14400)}s`,
    check: nextDeleteSource
      ? "Source deletion must remain an explicit opt-in safety decision and should not be enabled from routine patch work."
      : `${settingsPolicyDeltaChangedText(entries, publishKeys)} Source files should still be copied to scratch and preserved during normal processing.`,
  });

  const runtimeKeys = [
    "DebugMode",
    "ConsoleLogLevel",
    "FileLogLevel",
    "LogRetentionDays",
    "FFmpegEncodeTimeoutSeconds",
    "FFmpegRemuxTimeoutSeconds",
    "FFmpegCpuEncodeTimeoutSeconds",
    "MkvmergeRemuxTimeoutSeconds",
    "SourceScanIntervalSeconds",
    "TransientFailureRetryLimit",
    "AllowSystemTools",
  ];
  const nextAllowSystemTools = settingsPatchCandidateBool(entries, "AllowSystemTools", false);
  const nextEncodeTimeout = settingsPatchCandidateNumber(entries, "FFmpegEncodeTimeoutSeconds", 21600);
  const nextRetention = settingsPatchCandidateNumber(entries, "LogRetentionDays", 7);
  rows.push({
    area: "Runtime / diagnostics guardrails",
    posture: nextAllowSystemTools || nextEncodeTimeout < 1800 || nextRetention === 0 ? "review" : (settingsPolicyDeltaChangedLabels(entries, runtimeKeys).length ? "preview required" : "unchanged"),
    current: `debug=${settingsPolicyDeltaBoolText(settingsPatchCurrentBool("DebugMode", false))}; encode timeout=${settingsPatchCurrentNumber("FFmpegEncodeTimeoutSeconds", 21600)}s; remux timeout=${settingsPatchCurrentNumber("FFmpegRemuxTimeoutSeconds", 7200)}s; retention=${settingsPatchCurrentNumber("LogRetentionDays", 7)}d; PATH tools=${settingsPolicyDeltaBoolText(settingsPatchCurrentBool("AllowSystemTools", false))}`,
    candidate: `debug=${settingsPolicyDeltaBoolText(settingsPatchCandidateBool(entries, "DebugMode", false))}; encode timeout=${nextEncodeTimeout}s; remux timeout=${settingsPatchCandidateNumber(entries, "FFmpegRemuxTimeoutSeconds", 7200)}s; retention=${nextRetention}d; PATH tools=${settingsPolicyDeltaBoolText(nextAllowSystemTools)}`,
    check: nextAllowSystemTools
      ? "Bundled tools should remain preferred; PATH fallback can hide FFmpeg/ffprobe version drift."
      : `${settingsPolicyDeltaChangedText(entries, runtimeKeys)} Timeout and log-retention changes affect long-running failure diagnosis.`,
  });

  const networkKeys = [
    "NetworkRole",
    "CoordinatorPort",
    "CoordinatorBindAddress",
    "CoordinatorAlsoEncodeLocally",
    "WorkerCoordinatorUrl",
    "WorkerName",
    "WorkerSourcePathMap",
    "WorkerConfigOverrides",
  ];
  const nextNetworkRole = settingsPatchCandidateText(entries, "NetworkRole", "standalone").toLowerCase();
  const nextWorkerOverrides = settingsPatchCandidateText(entries, "WorkerConfigOverrides", "");
  rows.push({
    area: "Network visibility / worker policy",
    posture: nextNetworkRole !== "standalone" || nextWorkerOverrides ? "review" : (settingsPolicyDeltaChangedLabels(entries, networkKeys).length ? "preview required" : "unchanged"),
    current: `role=${formatSettingsChoiceLabel(settingsPatchCurrentText("NetworkRole", "standalone"))}; worker=${settingsPatchCurrentText("WorkerName", "(not set)") || "(not set)"}; overrides=${settingsPatchCurrentText("WorkerConfigOverrides", "") ? "present" : "none"}`,
    candidate: `role=${formatSettingsChoiceLabel(nextNetworkRole)}; worker=${settingsPatchCandidateText(entries, "WorkerName", "(not set)") || "(not set)"}; coordinator=${settingsPatchCandidateText(entries, "WorkerCoordinatorUrl", "(not set)") || "(not set)"}; overrides=${nextWorkerOverrides ? "present" : "none"}`,
    check: `${settingsPolicyDeltaChangedText(entries, networkKeys)} WebView network lifecycle controls remain read-only/backend-owned during transition.`,
  });

  rows.push({
    area: "Mutation boundary",
    posture: "backend-owned",
    current: "Current config is read-only in this table.",
    candidate: "Changes JSON is still only staged text until backend Preview/Save succeeds.",
    check: "This delta cannot save settings, launch work, run FFmpeg, rename, drain, publish, or touch files.",
  });

  return rows;
}

function settingsPolicyDeltaSummaryLines(rows) {
  const counts = rows.reduce((acc, row) => {
    const key = String(row.posture || "unknown").toLowerCase();
    acc[key] = (acc[key] || 0) + 1;
    return acc;
  }, {});
  const reviewRows = rows.filter((row) => {
    const posture = String(row.posture || "").toLowerCase();
    return posture.includes("blocked") || posture.includes("critical") || posture.includes("review") || posture.includes("staged") || posture.includes("preview");
  });
  const lines = [
    "Staged media-policy delta:",
    `Status: ${settingsPolicyDeltaStatus(rows)}`,
    `Rows: ${rows.length}; blocked=${counts.blocked || 0}; critical-blocked=${counts["critical blocked"] || 0}; review=${counts.review || 0}; preview-required=${counts["preview required"] || 0}; staged=${counts.staged || 0}.`,
    "This compares current saved values against the local Changes JSON candidate before backend preview/save.",
    "Backend Preview Patch remains authoritative for schema validation, risk classification, PSD1 serialization, and redacted diff evidence.",
  ];
  if (reviewRows.length) {
    lines.push("", "Rows needing operator attention:");
    reviewRows.slice(0, 7).forEach((row) => lines.push(`- ${row.area}: ${row.posture}; ${row.check}`));
  } else {
    lines.push("", "No staged media-policy contradictions detected locally.");
  }
  lines.push("", "Mutation guardrail: this delta is read-only and cannot save settings, launch work, mutate queues, publish, rename, or touch media.");
  return lines;
}

function renderSettingsPolicyDeltaFromEntries(entries) {
  const rows = settingsPolicyDeltaRows(entries);
  const tbody = byId("settings-policy-delta-rows");
  setText("settings-policy-delta-status", settingsPolicyDeltaStatus(rows));
  setText("settings-policy-delta-summary", settingsPolicyDeltaSummaryLines(rows).join("\n"));
  setText("settings-policy-delta-legend", "Staged media-policy delta is read-only; backend preview/save remains authoritative.");
  if (!tbody) return;
  if (!rows.length) {
    clearRows(tbody, 5, "No staged media-policy delta loaded.");
    return;
  }
  tbody.replaceChildren();
  rows.forEach((item) => {
    const row = document.createElement("tr");
    const posture = String(item.posture || "").toLowerCase();
    row.dataset.status = posture.includes("blocked") || posture.includes("critical")
      ? "blocked"
      : posture.includes("review") || posture.includes("staged") || posture.includes("preview")
        ? "warning"
        : "match";
    appendCells(row, [item.area, item.posture, item.current, item.candidate, item.check]);
    tbody.appendChild(row);
  });
}

function renderSettingsPolicyDeltaForError(message) {
  setText("settings-policy-delta-status", "Invalid JSON");
  setText(
    "settings-policy-delta-summary",
    `Staged media-policy delta unavailable because Changes JSON is invalid.\n${message}\nBackend preview/save cannot run until this is valid JSON.`
  );
  clearRows(byId("settings-policy-delta-rows"), 5, "Staged media-policy delta unavailable because Changes JSON is invalid.");
  setText("settings-policy-delta-legend", "Staged media-policy delta is read-only; backend preview/save remains authoritative.");
}

    function settingsLaunchImpactGroupText(entry) {
      const groupName = String(entry?.group?.name || "Unknown / custom");
      const normalized = groupName.toLowerCase();
      if (normalized.includes("paths") || normalized.includes("file safety")) {
        return "May change source discovery, scratch/output roots, file stability checks, or source-preservation safeguards.";
      }
      if (normalized.includes("routing") || normalized.includes("size")) {
        return "May change remux-vs-encode routing, Plex compatibility posture, or output growth handling.";
      }
      if (normalized.includes("encoder") || normalized.includes("gpu")) {
        return "May change FFmpeg encoder selection, GPU/CPU fallback behavior, speed, or output size.";
      }
      if (normalized.includes("subtitle")) {
        return "May change SRT creation, original subtitle preservation, OCR/conversion routing, or language filtering.";
      }
      if (normalized.includes("audio")) {
        return "May change passthrough, default audio selection, downmixing, or no-audio output safeguards.";
      }
      if (normalized.includes("pending") || normalized.includes("publish") || normalized.includes("network")) {
        return "May change pending-publish behavior, copy retries, worker coordination, or slow-share recovery.";
      }
      if (normalized.includes("queue") || normalized.includes("reprocess")) {
        return "May change queue ordering, processed-output detection, or deliberate reprocess behavior.";
      }
      if (normalized.includes("runtime") || normalized.includes("diagnostics")) {
        return "May change scan cadence, subprocess timeout ceilings, retry escalation, or log volume.";
      }
      return "Backend preview must explain this setting before it is used for launch decisions.";
    }

    function settingsLaunchImpactLatestSettingsCommand() {
      const history = getCommandHistory();
      if (!Array.isArray(history)) return null;
      return history.find(isSettingsCommand) || null;
    }

    function settingsLaunchImpactRows(entries) {
      const changedEntries = entries.filter((entry) => entry.changed);
      const issues = settingsPatchSaveReadinessIssues(entries);
      const rows = [];
      rows.push({
        area: "Patch state",
        posture: changedEntries.length ? "staged" : entries.length ? "unchanged" : "idle",
        evidence: `${entries.length} staged key(s); ${changedEntries.length} effective change(s); ${entries.filter((entry) => !entry.field).length} unknown key(s).`,
        check: changedEntries.length
          ? "Launch continues to use saved backend settings until Save Patch succeeds and settings reload/refresh completes."
          : "No effective staged changes are waiting to affect Launch.",
      });

      const grouped = new Map();
      changedEntries.forEach((entry) => {
        const name = entry.group?.name || "Unknown / custom";
        if (!grouped.has(name)) grouped.set(name, []);
        grouped.get(name).push(entry);
      });
      grouped.forEach((groupEntries, groupName) => {
        const hasUnknown = groupEntries.some((entry) => !entry.field);
        const hasHigh = groupEntries.some((entry) => entry.severity === "high");
        const posture = hasUnknown ? "blocked" : hasHigh ? "high review" : "review";
        rows.push({
          area: groupName,
          posture,
          evidence: groupEntries.slice(0, 8).map((entry) => entry.key).join(", ") + (groupEntries.length > 8 ? `, +${groupEntries.length - 8} more` : ""),
          check: settingsLaunchImpactGroupText(groupEntries[0]),
        });
      });

      rows.push({
        area: "Save readiness",
        posture: settingsPatchSaveReadinessStatus(entries),
        evidence: issues.length ? issues.slice(0, 4).map((issue) => `[${issue.severity}] ${issue.message}`).join(" | ") : "No local save blocker detected.",
        check: "Run backend Preview Patch before Save Patch. Backend preview/save owns schema validation, PSD1 writes, backups, and reload.",
      });

      const latestCommand = settingsLaunchImpactLatestSettingsCommand();
      if (!latestCommand) {
        rows.push({
          area: "Last backend settings command",
          posture: "no history",
          evidence: "No settings validate/reload/preview/save command is available in recent command history.",
          check: "Use Preview Patch before Save Patch; use Reload From Disk after out-of-band config edits.",
        });
      } else {
        const command = String(latestCommand.command || latestCommand.raw?.command || "").toLowerCase();
        const ok = latestCommand.ok === true || latestCommand.result === "ok" || latestCommand.raw?.ok === true;
        const isSave = command === "settings.save_patch";
        const isPreview = command === "settings.preview_patch";
        rows.push({
          area: "Last backend settings command",
          posture: ok && isSave ? "saved evidence" : ok && isPreview ? "preview only" : ok ? "ok" : "review",
          evidence: settingsCommandHistoryLine(latestCommand) || command || "settings command",
          check: ok && isSave
            ? "A successful backend save is visible. Confirm Saved Settings Trust/Launch risk after refresh before starting long runs."
            : isPreview
              ? "Preview does not apply changes to Launch. Save Patch must succeed before Launch uses this config."
              : "Resolve command warnings/errors before relying on changed settings for Launch.",
        });
      }

      rows.push({
        area: "Launch authority",
        posture: "backend-owned",
        evidence: "This panel never starts work, bypasses schedule, rewrites config, or touches media files.",
        check: "Launch readiness, schedule gates, close-readiness, and pipeline locks remain backend-owned.",
      });
      return rows;
    }

    function settingsLaunchImpactStatus(rows) {
      if (!rows.length) return "Not evaluated";
      const postures = rows.map((row) => String(row.posture || "").toLowerCase());
      if (postures.some((posture) => posture.includes("blocked"))) return "Blocked review";
      if (postures.some((posture) => posture.includes("high"))) return "High review";
      if (postures.some((posture) => posture.includes("staged") || posture.includes("preview only") || posture.includes("review") || posture.includes("no history"))) return "Review";
      return "Ready";
    }

    function settingsLaunchImpactSummaryLines(rows) {
      const counts = rows.reduce((acc, row) => {
        const key = String(row.posture || "unknown");
        acc[key] = (acc[key] || 0) + 1;
        return acc;
      }, {});
      const reviewRows = rows.filter((row) => {
        const posture = String(row.posture || "").toLowerCase();
        return posture.includes("staged")
          || posture.includes("review")
          || posture.includes("blocked")
          || posture.includes("high")
          || posture.includes("preview only")
          || posture.includes("no history");
      });
      const lines = [
        "Settings-to-launch handoff:",
        `Status: ${settingsLaunchImpactStatus(rows)}`,
        `Rows: ${rows.length}; staged=${counts.staged || 0}; blocked=${counts.blocked || 0}; high-review=${counts["high review"] || 0}; preview-only=${counts["preview only"] || 0}.`,
        "Launch uses saved backend settings, not unsaved Changes JSON. Save Patch plus refresh/reload is required before a staged patch can affect Launch.",
        "Backend launch validation remains the source of truth for schedule gates, active-work locks, and pipeline start acceptance.",
      ];
      if (reviewRows.length) {
        lines.push("", "Rows needing operator review before launch:");
        reviewRows.slice(0, 6).forEach((row) => lines.push(`- ${row.area}: ${row.posture}; ${row.check}`));
      } else {
        lines.push("", "No local settings-to-launch review items detected.");
      }
      lines.push("", "Mutation guardrail: this handoff is read-only and cannot save settings, launch work, mutate queue state, or touch media files.");
      return lines;
    }

    function renderSettingsLaunchImpactHandoffFromEntries(entries) {
      const rows = settingsLaunchImpactRows(entries);
      setText("settings-launch-impact-status", settingsLaunchImpactStatus(rows));
      setText("settings-launch-impact-summary", settingsLaunchImpactSummaryLines(rows).join("\n"));
      setText("settings-launch-impact-legend", "Settings-to-launch handoff is read-only; backend launch validation remains authoritative.");
      const tbody = byId("settings-launch-impact-rows");
      if (!rows.length) {
        clearRows(tbody, 4, "No settings-to-launch impact rows loaded.");
        return;
      }
      tbody.replaceChildren();
      rows.forEach((item) => {
        const row = document.createElement("tr");
        const posture = String(item.posture || "").toLowerCase();
        row.dataset.status = posture.includes("blocked") ? "blocked" : (posture.includes("review") || posture.includes("staged") || posture.includes("preview only") || posture.includes("no history") ? "warning" : "match");
        appendCells(row, [item.area, item.posture, item.evidence, item.check]);
        tbody.appendChild(row);
      });
    }

    function renderSettingsLaunchImpactHandoffForError(message) {
      setText("settings-launch-impact-status", "Invalid JSON");
      setText(
        "settings-launch-impact-summary",
        `Settings-to-launch handoff unavailable because Changes JSON is invalid.\n${message}\nLaunch will continue using saved backend settings; backend preview/save cannot run until this is valid JSON.`
      );
      clearRows(byId("settings-launch-impact-rows"), 4, "Settings-to-launch handoff unavailable because Changes JSON is invalid.");
      setText("settings-launch-impact-legend", "Settings-to-launch handoff is read-only; backend launch validation remains authoritative.");
    }

    return {
      settingsMediaPolicyList,
      settingsMediaPolicyBool,
      settingsMediaPolicyValue,
      settingsMediaPolicyNumber,
      settingsMediaPolicyLanguageGaps,
      settingsMediaPolicyRows,
      settingsMediaPolicyStatus,
      settingsActiveMediaPolicyRows,
      settingsActiveMediaPolicyStatus,
      settingsActiveMediaPolicySummaryLines,
      renderSettingsActiveMediaPolicyHandoff,
      settingsEffectivePolicyRowKey,
      settingsEvidenceMatch,
      settingsEvidenceResultLabel,
      settingsEffectivePolicyRows,
      settingsEffectivePolicyTrustStatus,
      settingsEffectivePolicySummaryLines,
      settingsEffectivePolicyDetailLines,
      selectedSettingsEffectivePolicyRow,
      renderSettingsEffectivePolicyTrustFromEntries,
      renderSettingsEffectivePolicyTrustForError,
      settingsMediaPolicySummaryLines,
      renderSettingsMediaPolicyCrossCheck,
      settingsBackendPolicyImpact,
      settingsBackendMediaPolicyReadiness,
      settingsBackendMediaPolicyStatus,
      settingsBackendMediaPolicySummaryLines,
      renderSettingsBackendMediaPolicyReadiness,
      settingsImpactGroupForKey,
      settingsPatchEntryStatus,
      settingsPatchImpactSeverity,
      settingsPatchImpactEntries,
      renderSettingsPatchImpactSummaryFromEntries,
      settingsBoolValue,
      settingsPatchCandidateValue,
      settingsStableJsonValue,
      settingsPatchSignature,
      settingsCurrentPatchSignature,
      settingsPatchListValue,
      settingsPatchCandidateText,
      settingsPatchCandidateNumber,
      settingsPatchCandidateBool,
      settingsPatchCandidateList,
      settingsPatchCurrentText,
      settingsPatchCurrentNumber,
      settingsPatchCurrentBool,
      settingsPatchCurrentList,
      settingsPolicyDeltaChangedLabels,
      settingsPolicyDeltaChangedText,
      settingsPolicyDeltaBoolText,
      settingsPolicyDeltaStatus,
      settingsPolicyDeltaRows,
      settingsPolicyDeltaSummaryLines,
      renderSettingsPolicyDeltaFromEntries,
      renderSettingsPolicyDeltaForError,
      settingsLaunchImpactGroupText,
      settingsLaunchImpactLatestSettingsCommand,
      settingsLaunchImpactRows,
      settingsLaunchImpactStatus,
      settingsLaunchImpactSummaryLines,
      renderSettingsLaunchImpactHandoffFromEntries,
      renderSettingsLaunchImpactHandoffForError,
    };
  }

  window.__settingsPolicyImpactModule = {
    createSettingsPolicyImpactModule,
  };
})();
