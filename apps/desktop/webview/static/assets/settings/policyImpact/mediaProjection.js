(function () {
  /**
   * Projects the visible Settings builder into read-only media-policy evidence.
   * It has no command or persistence authority; the policy-impact facade injects all state access.
   */
  function createSettingsMediaProjection(deps) {
    deps = deps || {};
    const byId = deps.byId || function () { return null; };
    const setText = deps.setText || function () {};
    const clearRows = deps.clearRows || function () {};
    const appendCells = deps.appendCells || function () {};
    const formatSettingsChoiceLabel = deps.formatSettingsChoiceLabel || function (value) { return String(value || ""); };
    const formatSettingsListValue = deps.formatSettingsListValue || function (value) { return Array.isArray(value) ? value.join(", ") : String(value ?? ""); };
    const parseSettingsListText = deps.parseSettingsListText || function (value) { return String(value || "").split(",").map((item) => item.trim()).filter(Boolean); };
    const settingsBuilderConfigValue = deps.settingsBuilderConfigValue || function (_key, fallback) { return fallback; };
    const settingsBuilderInputValue = deps.settingsBuilderInputValue || function () { return ""; };
    const settingsActiveRouteHeightBoundaries = deps.settingsActiveRouteHeightBoundaries || function () { return {}; };

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
        : "Preferred subtitle language policy is visible before backend Save.",
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
    "Builder edits are not launch-active until backend Save succeeds and settings reload/refresh completes.",
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
    "Save Settings remains backend-owned; this panel does not change FFmpeg, subtitle, audio, remux, encode, or publish behavior.",
  ];
  if (reviewRows.length) {
    lines.push("", "Rows needing review:");
    reviewRows.forEach((row) => lines.push(`- ${row.area}: ${row.action}`));
  } else {
    lines.push("", "No local audio/subtitle contradictions detected. Save Settings will run backend validation before writing.");
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

    return {
      settingsMediaPolicyList, settingsMediaPolicyBool, settingsMediaPolicyValue, settingsMediaPolicyNumber,
      settingsMediaPolicyLanguageGaps, settingsMediaPolicyRows, settingsMediaPolicyStatus,
      settingsActiveMediaPolicyRows, settingsActiveMediaPolicyStatus, settingsActiveMediaPolicySummaryLines,
      renderSettingsActiveMediaPolicyHandoff, settingsMediaPolicySummaryLines, renderSettingsMediaPolicyCrossCheck,
    };
  }

  window.__settingsMediaProjectionModule = createSettingsMediaProjection;
})();
