(function () {
  function configValue(config, key, fallback = "(not set)") {
    if (!config || typeof config !== "object") return fallback;
    if (Object.prototype.hasOwnProperty.call(config, key)) return formatConfigValue(config[key]) || fallback;
    const match = Object.keys(config).find((item) => item.toLowerCase() === String(key).toLowerCase());
    return match ? formatConfigValue(config[match]) || fallback : fallback;
  }

  function rawConfigValue(config, key, fallback = undefined) {
    if (!config || typeof config !== "object") return fallback;
    if (Object.prototype.hasOwnProperty.call(config, key)) return config[key];
    const match = Object.keys(config).find((item) => item.toLowerCase() === String(key).toLowerCase());
    return match ? config[match] : fallback;
  }

  function trustConfigValue(config, key, fallback = "(not set)") {
    const value = rawConfigValue(config, key, undefined);
    if (value === undefined || value === null || value === "") return fallback;
    return formatConfigValue(value) || fallback;
  }

  function settingsTrustBool(config, key, fallback = "unknown") {
    const value = rawConfigValue(config, key, undefined);
    if (value === undefined || value === null || value === "") return fallback;
    if (typeof value === "boolean") return value ? "enabled" : "disabled";
    const normalized = String(value).trim().toLowerCase();
    if (["true", "1", "yes", "y", "on", "enabled"].includes(normalized)) return "enabled";
    if (["false", "0", "no", "n", "off", "disabled"].includes(normalized)) return "disabled";
    return String(value);
  }

  function settingsRiskSummaryLine(riskSummary) {
    if (!riskSummary || typeof riskSummary !== "object") return "Backend risk summary: unavailable.";
    const counts = riskSummary.counts || {};
    const highest = riskSummary.highest_severity || "none";
    const total = Number(riskSummary.total_count || 0);
    return `Backend risk summary: ${total} item${total === 1 ? "" : "s"}; highest=${highest}; critical=${counts.critical || 0}, high=${counts.high || 0}, medium=${counts.medium || 0}, low=${counts.low || 0}.`;
  }

  function settingsRiskItems(settings, limit = 6) {
    const items = Array.isArray(settings?.risk_summary?.items) ? settings.risk_summary.items : [];
    return items.slice(0, limit).map((item) => {
      const severity = item?.severity || "risk";
      const key = item?.key || item?.code || "setting";
      const message = item?.message || item?.description || "Review saved setting.";
      return `- ${severity}: ${key}: ${message}`;
    });
  }

  function settingsMediaPolicyReadinessLine(settings) {
    const readiness = settings?.media_policy_readiness || {};
    if (!readiness || typeof readiness !== "object" || readiness.schema_version !== "settings_media_policy_readiness.v1") {
      return "Backend media-policy readiness: unavailable.";
    }
    const counts = readiness.counts || {};
    const status = readiness.operator_status || "Not evaluated";
    return `Backend media-policy readiness: ${status}; rows=${readiness.total_count || 0}; coherent=${counts.coherent || 0}, review=${counts.review || 0}, blocked=${counts.blocked || 0}.`;
  }

  function settingsOperatorTrustStatus(settings) {
    if (!settings || !settings.config || typeof settings.config !== "object") return "Not loaded";
    const errors = Array.isArray(settings.errors) ? settings.errors : [];
    if (settings.error || errors.length) return "Invalid";
    const highest = String(settings.risk_summary?.highest_severity || "none").toLowerCase();
    if (highest === "critical") return "Critical risk";
    if (highest === "high") return "High risk";
    const warnings = Array.isArray(settings.warnings) ? settings.warnings : [];
    const total = Number(settings.risk_summary?.total_count || 0);
    if (highest === "medium" || highest === "low" || warnings.length || total > 0) return "Review";
    return "Ready";
  }

  function settingsOperatorTrustLines(settings) {
    if (!settings || !settings.config || typeof settings.config !== "object") {
      return [
        "Saved settings trust checklist:",
        "Settings workspace: not loaded.",
        "Operator action: refresh the WebView or open Settings before starting pipeline work.",
        "Mutation guardrail: settings trust is read-only; backend settings workspace and launch validation remain the source of truth.",
      ];
    }
    const config = settings.config || {};
    const warnings = Array.isArray(settings.warnings) ? settings.warnings : [];
    const errors = Array.isArray(settings.errors) ? settings.errors : [];
    const skipStability = settingsTrustBool(config, "SkipStabilityCheck");
    const stabilityPosture = skipStability === "enabled" ? "disabled by SkipStabilityCheck" : skipStability === "disabled" ? "enabled" : "unknown";
    const lines = [
      "Saved settings trust checklist:",
      settingsRiskSummaryLine(settings.risk_summary),
      settingsMediaPolicyReadinessLine(settings),
      `Settings validation: ${settings.error || errors.length ? "review errors before launch" : warnings.length ? `${warnings.length} warning(s)` : "no blocking errors reported"}.`,
      "",
      "Source safety:",
      `- SourceMovies: ${trustConfigValue(config, "SourceMovies")}`,
      `- SourceTV: ${trustConfigValue(config, "SourceTV")}`,
      `- Output root: ${trustConfigValue(config, "Outsource")}`,
      `- Scratch root: ${trustConfigValue(config, "LocalBase")}`,
      `- Source mutation policy: copy-to-scratch; source delete is not exposed in the WebView shell.`,
      `- Stability check: ${stabilityPosture}; wait=${trustConfigValue(config, "FileStabilityWait", "default")}s; integrity=${settingsTrustBool(config, "EnableIntegrityCheck")}.`,
      `- Valid extensions: ${trustConfigValue(config, "ValidExtensions")}; disk estimate multiplier=${trustConfigValue(config, "OutputSizeMultiplier", "default")}.`,
      "",
      "Publish behavior:",
      `- Deferred publish: ${settingsTrustBool(config, "DeferredPublish")}; network role=${trustConfigValue(config, "NetworkRole", "local")}; cleanup remote staging=${settingsTrustBool(config, "CleanupRemoteStaging")}.`,
      `- Robocopy flags: ${trustConfigValue(config, "RobocopyFlags", "(default)")}`,
      "",
      "Remux/encode routing:",
      `- Routing profile: ${trustConfigValue(config, "RoutingProfile", "default")}; Output Size Check=${trustConfigValue(config, "SizeGuardMode", "default")}; output container=${trustConfigValue(config, "OutputContainer", "default")}.`,
      `- Remux/copy bitrate ceilings: movies=${trustConfigValue(config, "MovieRouteMaxVideoBitrateMbps", "35")} Mbps; TV=${trustConfigValue(config, "TVRouteMaxVideoBitrateMbps", "18")} Mbps.`,
      `- Encode growth limits: default=${trustConfigValue(config, "MaxEncodeGrowthPercent", "default")}; compatibility=${trustConfigValue(config, "CompatibilityEncodeGrowthPercent", "default")}.`,
      `- H.264 remux when Plex-compatible: ${settingsTrustBool(config, "AllowH264RemuxIfPlexCompatible")}; max bitrate=${trustConfigValue(config, "H264RemuxMaxBitrateMbps", "default")} Mbps; max height=${trustConfigValue(config, "H264RemuxMaxHeight", "default")}.`,
      "",
      "Encoder posture:",
      `- Video codec=${trustConfigValue(config, "VideoCodec", "default")}; preset=${trustConfigValue(config, "VideoPreset", "default")}; quality=${trustConfigValue(config, "VideoQuality", "default")}.`,
      `- Legacy extra flags: ${trustConfigValue(config, "ExtraVideoFlags", "(none)")}; PATH tool fallback=${settingsTrustBool(config, "AllowSystemTools")}.`,
      "",
      "Subtitle routing:",
      `- Preferred keep languages: ${trustConfigValue(config, "SubKeepLanguages", "default")}.`,
      `- TX3G: convert=${settingsTrustBool(config, "ConvertTx3gToSrt")}; drop original=${settingsTrustBool(config, "DropTx3gAfterConversion")}; extract languages=${trustConfigValue(config, "Tx3gExtractLanguages", "default")}.`,
      `- BDPGS: convert=${settingsTrustBool(config, "ConvertBdpgsToSrt")}; drop original=${settingsTrustBool(config, "DropBdpgsAfterConversion")}; extract languages=${trustConfigValue(config, "BdpgsExtractLanguages", "default")}.`,
      `- VobSub: convert=${settingsTrustBool(config, "ConvertVobSubToSrt")}; drop original=${settingsTrustBool(config, "DropVobSubAfterConversion")}; extract languages=${trustConfigValue(config, "VobSubExtractLanguages", "default")}.`,
      `- ASS/SSA: drop after conversion=${settingsTrustBool(config, "DropAssAfterConversion")}; strip formatting=${settingsTrustBool(config, "StripFormatting")}; remove karaoke=${settingsTrustBool(config, "RemoveKaraoke")}.`,
      "",
      "Audio routing:",
      `- Passthrough profile=${trustConfigValue(config, "AudioPassthroughProfile", "default")}; preferred defaults=${trustConfigValue(config, "PreferredDefaultAudioLanguages", "default")}.`,
      `- Compatible codecs=${trustConfigValue(config, "CompatibleAudioCodecs", "default")}; downmix=${trustConfigValue(config, "AudioDownmixMode", "default")}; max channels=${trustConfigValue(config, "AudioMaxChannels", "default")}; allow no audio=${settingsTrustBool(config, "AllowNoAudio")}.`,
      "",
      "Operator action:",
    ];
    if (settings.error || errors.length) {
      lines.push("- Settings are invalid or partially unavailable. Use Settings > Validate/Reload before launching.");
    } else if (settingsOperatorTrustStatus(settings).includes("risk") || settingsOperatorTrustStatus(settings) === "Review") {
      lines.push("- Review Settings risk items before launching long unattended runs.");
    } else {
      lines.push("- Saved settings look launch-ready; backend launch validation still has final authority.");
    }
    if (settingsTrustBool(config, "DeferredPublish") === "enabled") {
      lines.push("- Deferred publish is enabled. Monitor Pending Publish after encode/remux completion.");
    }
    if (settingsTrustBool(config, "SkipStabilityCheck") === "enabled") {
      lines.push("- Stability checks are disabled. Avoid active torrent/download folders unless this is intentional.");
    }
    const riskItems = settingsRiskItems(settings);
    if (riskItems.length) {
      lines.push("", "Top saved-setting risk item(s):", ...riskItems);
    }
    const mediaReadinessRows = Array.isArray(settings.media_policy_readiness?.rows) ? settings.media_policy_readiness.rows : [];
    const mediaReviewRows = mediaReadinessRows.filter((row) => row && row.posture !== "coherent").slice(0, 6);
    if (mediaReviewRows.length) {
      lines.push("", "Backend media-policy readiness item(s):");
      mediaReviewRows.forEach((row) => {
        lines.push(`- ${row.posture || "review"}: ${row.area || "policy"}: ${row.operator_check || "Review saved media-policy setting."}`);
      });
    }
    if (warnings.length) {
      lines.push("", "Validation warning(s):");
      warnings.slice(0, 6).forEach((warning) => lines.push(`- ${warning}`));
    }
    if (errors.length) {
      lines.push("", "Validation error(s):");
      errors.slice(0, 6).forEach((error) => lines.push(`- ${error}`));
    }
    lines.push("", "Mutation guardrail: settings trust is read-only; backend settings workspace and launch validation remain the source of truth.");
    return lines;
  }

  function renderSettingsOperatorTrust(settings) {
    const status = settingsOperatorTrustStatus(settings);
    const summary = settingsOperatorTrustLines(settings).join("\n");
    setText("home-settings-trust-status", status);
    setText("home-settings-trust-summary", summary);
    setText("launch-settings-trust-status", status);
    setText("launch-settings-trust-summary", summary);
    setText("settings-trust-status", status);
    setText("settings-trust-summary", summary);
  }

  function buildSettingsOverviewRows(config) {
    const rows = [];
    const add = (section, key, label = key) => {
      rows.push({ section, label, value: configValue(config, key), key });
    };
    const addValue = (section, label, value) => {
      rows.push({ section, label, value });
    };

    [
      ["RoutingProfile", "Routing profile"],
      ["RouteThresholdMode", "Route threshold mode"],
      ["SizeGuardMode", "Output Size Check"],
      ["AllowH264RemuxIfPlexCompatible", "H.264 remux when Plex-compatible"],
      ["H264RemuxMaxBitrateMbps", "H.264 remux max bitrate Mbps"],
      ["H264RemuxMaxHeight", "H.264 remux max height"],
      ["EncodeThresholdGB", "Movie encode threshold GB"],
      ["TVEncodeThresholdGB", "TV encode threshold GB"],
      ["MovieRouteMaxVideoBitrateMbps", "Movie copy max bitrate Mbps"],
      ["TVRouteMaxVideoBitrateMbps", "TV copy max bitrate Mbps"],
      ["MaxEncodeGrowthPercent", "Default encode growth limit %"],
      ["CompatibilityEncodeGrowthPercent", "Compatibility encode growth limit %"],
      ["OutputContainer", "Output container"],
    ].forEach(([key, label]) => add("Routing / Size", key, label));

    [
      ["SourceMovies", "Movie source root"],
      ["SourceTV", "TV source root"],
      ["Outsource", "Output root"],
      ["LocalBase", "Scratch root"],
      ["MinFreeSpaceGB", "Scratch min free GB"],
      ["OutsourceMinFreeSpaceGB", "Output min free GB"],
      ["FileStabilityWait", "File stability wait seconds"],
      ["SkipStabilityCheck", "Skip stability check"],
      ["EnableIntegrityCheck", "Enable integrity check"],
      ["CreateTVSubfolder", "Create TV subfolders"],
      ["ValidExtensions", "Valid media extensions"],
      ["OutputSizeMultiplier", "Disk estimate multiplier"],
      ["CleanupRemoteStaging", "Cleanup remote staging"],
    ].forEach(([key, label]) => add("Paths / Safety", key, label));
    addValue("Paths / Safety", "Source mutation policy", "copy-to-scratch; source delete not exposed in web shell");

    [
      ["VideoCodec", "Video codec"],
      ["VideoPreset", "Video preset"],
      ["VideoQuality", "Video quality"],
      ["EncodeTuningPreset", "Encode tuning preset"],
      ["EncodeLadder", "Encode ladder"],
      ["ExtraVideoFlags", "Extra video flags"],
      ["FallbackCpuQuality", "CPU fallback quality"],
      ["CpuEncodePreset", "CPU encode preset"],
      ["CpuEncodeProcessPriority", "CPU process priority"],
      ["FFmpegEncodeTimeoutSeconds", "FFmpeg encode timeout seconds"],
      ["FFmpegRemuxTimeoutSeconds", "FFmpeg remux timeout seconds"],
    ].forEach(([key, label]) => add("Encoder", key, label));

    [
      ["SubKeepLanguages", "Subtitle keep languages"],
      ["ConvertTx3gToSrt", "Convert TX3G to SRT"],
      ["DropTx3gAfterConversion", "Drop TX3G after conversion"],
      ["Tx3gExtractLanguages", "TX3G extract languages"],
      ["ConvertBdpgsToSrt", "Convert BDPGS to SRT"],
      ["DropBdpgsAfterConversion", "Drop BDPGS after conversion"],
      ["BdpgsExtractLanguages", "BDPGS extract languages"],
      ["ConvertVobSubToSrt", "Convert VobSub to SRT"],
      ["DropVobSubAfterConversion", "Drop VobSub after conversion"],
      ["VobSubExtractLanguages", "VobSub extract languages"],
      ["DropAssAfterConversion", "Drop ASS after conversion"],
      ["StripFormatting", "Strip formatting"],
      ["RemoveKaraoke", "Remove karaoke"],
      ["MergeAdjacent", "Merge adjacent subtitles"],
      ["KeepSignsAndSongs", "Keep signs/songs"],
      ["SubtitleExtractTimeoutSeconds", "Subtitle extract timeout seconds"],
      ["SubtitleProbeTimeoutSeconds", "Subtitle probe timeout seconds"],
      ["BdpgsOcrTimeoutSeconds", "BDPGS OCR timeout seconds"],
      ["VobSubOcrTimeoutSeconds", "VobSub OCR timeout seconds"],
    ].forEach(([key, label]) => add("Subtitles", key, label));

    [
      ["AudioPassthroughProfile", "Audio passthrough profile"],
      ["PreferredDefaultAudioLanguages", "Preferred default audio languages"],
      ["CompatibleAudioCodecs", "Compatible audio codecs"],
      ["AudioTranscodeCodec", "Audio transcode codec"],
      ["AudioTranscodeBitrate", "Audio transcode bitrate"],
      ["AudioDownmixMode", "Audio downmix mode"],
      ["AudioMaxChannels", "Audio max channels"],
      ["AllowNoAudio", "Allow no-audio outputs"],
    ].forEach(([key, label]) => add("Audio", key, label));

    [
      ["DeferredPublish", "Deferred publish"],
      ["NetworkRole", "Network role"],
      ["CoordinatorAlsoEncodeLocally", "Coordinator also encodes locally"],
      ["SourceScanIntervalSeconds", "Source scan interval seconds"],
      ["TransientFailureRetryLimit", "Transient failure retry limit"],
      ["RobocopyFlags", "Robocopy flags"],
      ["RobocopyTimeoutSeconds", "Robocopy timeout seconds"],
    ].forEach(([key, label]) => add("Publish / Network", key, label));

    [
      ["DebugMode", "Debug mode"],
      ["ConsoleLogLevel", "Console log level"],
      ["FileLogLevel", "File log level"],
      ["LogRetentionDays", "Log retention days"],
      ["PriorityMarkers", "Priority markers"],
      ["ReprocessAll", "Reprocess all"],
      ["AllowSystemTools", "Allow system tools"],
    ].forEach(([key, label]) => add("Diagnostics / Runtime", key, label));

    return rows;
  }

  function renderSettingsOverview(config) {
    const rows = buildSettingsOverviewRows(config || {});
    setText("settings-overview-status", `${rows.length} grouped setting${rows.length === 1 ? "" : "s"}`);
    const tbody = byId("settings-overview-rows");
    if (!tbody) return;
    if (!rows.length) {
      clearRows(tbody, 3, "No grouped settings loaded.");
      return;
    }
    tbody.replaceChildren();
    rows.forEach((item) => {
      const row = document.createElement("tr");
      appendCells(row, [item.section, item.label, item.value]);
      tbody.appendChild(row);
    });
  }

  /**
   * Public namespace for the settings overview module.
   * Prefer this namespace from new code; flat window.* exports are transitional compatibility aliases when present.
   */
  window.mediaPipelineSettingsOverview = {
    configValue,
    rawConfigValue,
    buildSettingsOverviewRows,
    renderSettingsOverview,
    settingsTrustBool,
    settingsOperatorTrustStatus,
    settingsOperatorTrustLines,
    settingsMediaPolicyReadinessLine,
    renderSettingsOperatorTrust,
  };
  window.configValue = configValue;
  window.buildSettingsOverviewRows = buildSettingsOverviewRows;
  window.renderSettingsOverview = renderSettingsOverview;
  window.settingsOperatorTrustStatus = settingsOperatorTrustStatus;
  window.renderSettingsOperatorTrust = renderSettingsOperatorTrust;
})();
