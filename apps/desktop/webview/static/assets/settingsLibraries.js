(function () {
  const metadata = window.mediaPipelineSettingsMetadata || {};
  const choiceLabels = metadata.settingsChoiceLabels || {};
  const routeModel = window.mediaPipelineRoutePolicyModel || {};
  const settingsView = window.mediaPipelineSettingsView || {};
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
      { type: "grid", fields: ["SubKeepLanguages", "Tx3gExtractLanguages", "BdpgsExtractLanguages", "VobSubExtractLanguages"] },
      { type: "advanced", title: "Advanced", note: "Keywords, timeouts, styles", fields: ["SubSDHTitleKeywords", "SubSupplementalKeywords", "MergeThresholdMs", "SubtitleExtractTimeoutSeconds", "SubtitleProbeTimeoutSeconds", "BdpgsOcrTimeoutSeconds", "VobSubOcrTimeoutSeconds", "ExcludeSubtitleStyles", "IncludeSubtitleStyles"] },
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

  const settingsLibrariesFacadeFactory = window.__settingsLibrariesFacade || {};
  delete window.__settingsLibrariesFacade;
  const settingsLibrariesFacade = settingsLibrariesFacadeFactory.createSettingsLibrariesFacade({
    advancedFallbackKeys, choiceLabels, designationValues, fallbackGroupByField, fallbackOverrideGroups,
    overrideGroupOrder, overrideGroupTitles, overrideLayouts, pathFields, routeBucketDefinitions,
    routeModel, routeSizeFields, routeToleranceKeys, settingsView, staticCompatibilityPresets,
  });

  /**
   * Public namespace for the settings libraries module.
   * Prefer this namespace from new code; flat window.* exports are transitional compatibility aliases when present.
   */
  window.mediaPipelineSettingsLibraries = {
    renderSettingsLibraries: settingsLibrariesFacade.renderSettingsLibraries,
    renderLibrarySummary: settingsLibrariesFacade.renderLibrarySummary,
    initSettingsLibrariesEvents: settingsLibrariesFacade.initSettingsLibrariesEvents,
    activateLibraryProfile: settingsLibrariesFacade.activateLibraryProfile,
    buildPatchFromLibraries: settingsLibrariesFacade.buildPatchFromLibraries,
    stageLibraryWatchAutoRunPatch: settingsLibrariesFacade.stageLibraryWatchAutoRunPatch,
    previewLibraryWatchAutoRunPatch: settingsLibrariesFacade.previewLibraryWatchAutoRunPatch,
    saveLibraryWatchAutoRunPatch: settingsLibrariesFacade.saveLibraryWatchAutoRunPatch,
    deleteActiveLibrary: settingsLibrariesFacade.deleteActiveLibrary,
    replaceActiveLibraryValuesWithDefaults: settingsLibrariesFacade.replaceActiveLibraryValuesWithDefaults,
    libraryProfileResetRequest: settingsLibrariesFacade.libraryProfileResetRequest,
    libraryPatchStateKind: settingsLibrariesFacade.libraryPatchStateKind,
    previewLibraryProfiles: settingsLibrariesFacade.previewLibraryProfiles,
    saveLibraryProfiles: settingsLibrariesFacade.saveLibraryProfiles,
    handleSettingsPostSaveRefreshFailure: settingsLibrariesFacade.handleSettingsPostSaveRefreshFailure,
  };
})();
