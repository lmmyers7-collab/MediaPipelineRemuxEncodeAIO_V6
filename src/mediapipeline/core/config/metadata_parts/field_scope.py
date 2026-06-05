"""Settings field scope and library-override metadata."""

from __future__ import annotations

from mediapipeline.core.config.preset_compatibility import MIGRATION_STATUS_VALUES

METADATA_SCOPE_VALUES = (
    "global_only",
    "library_overridable",
    "source_derived",
    "computed_only",
    "advanced",
)

METADATA_MIGRATION_STATUS_VALUES = (
    *MIGRATION_STATUS_VALUES,
)

METADATA_LIBRARY_OVERRIDE_KEYS_BY_GROUP = {
    "editor": (
        "RoutingProfile",
        "RouteThresholdMode",
        "SizeGuardMode",
        "EncodeTuningPreset",
        "EncodeLadder",
        "VideoCodec",
        "OutputContainer",
        "EncodeThresholdGB",
        "TVEncodeThresholdGB",
        "MovieRoute1080pTargetSizeGB",
        "MovieRoute1440pTargetSizeGB",
        "MovieRoute4KTargetSizeGB",
        "TVRoute1080pTargetSizeGB",
        "TVRoute1440pTargetSizeGB",
        "TVRoute4KTargetSizeGB",
        "MovieRouteMaxVideoBitrateMbps",
        "TVRouteMaxVideoBitrateMbps",
        "Route1080pBucketMaxHeight",
        "Route1080pUpperHeightTolerancePercent",
        "Route1080pMaxVideoBitrateMbps",
        "Route1440pLowerHeightTolerancePercent",
        "Route1440pUpperHeightTolerancePercent",
        "Route1440pMaxVideoBitrateMbps",
        "Route4KLowerHeightTolerancePercent",
        "Route4KBucketMinHeight",
        "Route4KMaxVideoBitrateMbps",
        "MaxEncodeGrowthPercent",
        "CompatibilityEncodeGrowthPercent",
    ),
    "video": (
        "VideoPreset",
        "VideoQuality",
        "AllowH264RemuxIfPlexCompatible",
        "H264RemuxMaxBitrateMbps",
        "H264RemuxMaxHeight",
        "RemuxSafeVideoCodecs",
        "FallbackCpuQuality",
        "CpuEncodePreset",
        "CpuEncodeProcessPriority",
        "CpuEncodeMaxThreads",
        "ExtraVideoFlags",
    ),
    "subtitles": (
        "SubKeepLanguages",
        "ConvertTx3gToSrt",
        "DropTx3gAfterConversion",
        "CreateExternalTx3gSrtSidecars",
        "Tx3gExtractLanguages",
        "Tx3gPreserveExistingSrt",
        "Tx3gTreatForcedAsSeparate",
        "ConvertBdpgsToSrt",
        "DropBdpgsAfterConversion",
        "BdpgsExtractLanguages",
        "BdpgsOcrToolPath",
        "BdpgsOcrTessdataPath",
        "ConvertVobSubToSrt",
        "DropVobSubAfterConversion",
        "VobSubExtractLanguages",
        "VobSubOcrToolPath",
        "SubtitleExtractTimeoutSeconds",
        "SubtitleProbeTimeoutSeconds",
        "BdpgsOcrTimeoutSeconds",
        "VobSubOcrTimeoutSeconds",
        "SubSDHTitleKeywords",
        "SubSupplementalKeywords",
        "DropAssAfterConversion",
        "StripFormatting",
        "RemoveKaraoke",
        "MergeAdjacent",
        "MergeThresholdMs",
        "KeepSignsAndSongs",
        "TreatAssSignsSongsAsForced",
        "TreatTx3gSignsSongsAsForced",
        "TreatBdpgsSignsSongsAsForced",
        "TreatVobSubSignsSongsAsForced",
        "ExcludeSubtitleStyles",
        "IncludeSubtitleStyles",
    ),
    "audio": (
        "AudioPassthroughProfile",
        "CompatibleAudioCodecs",
        "PreferredDefaultAudioLanguages",
        "AudioTranscodeCodec",
        "AudioTranscodeBitrate",
        "AudioTranscodeAutoBitrateByChannels",
        "AudioDownmixMode",
        "AudioMaxChannels",
        "AllowNoAudio",
    ),
}

METADATA_LIBRARY_OVERRIDE_GROUP_BY_KEY = {
    key: group
    for group, keys in METADATA_LIBRARY_OVERRIDE_KEYS_BY_GROUP.items()
    for key in keys
}

def _metadata_scope(field: dict[str, object], override_group: str | None) -> str:
    if override_group:
        return "library_overridable"
    if field.get("page") == "Advanced":
        return "advanced"
    return "global_only"
