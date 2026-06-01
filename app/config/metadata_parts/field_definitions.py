"""Combined settings field definitions in public render order."""

from __future__ import annotations

from app.config.preset_migration import MIGRATION_STATUS_VALUES

from .advanced_fields import ADVANCED_CONFIG_FIELD_DEFINITIONS
from .basic_fields import BASIC_CONFIG_FIELD_DEFINITIONS
from .network_fields import NETWORK_CONFIG_FIELD_DEFINITIONS
from .queue_fields import QUEUE_CONFIG_FIELD_DEFINITIONS
from .subtitle_fields import SUBTITLE_CONFIG_FIELD_DEFINITIONS
from .video_fields import VIDEO_CONFIG_FIELD_DEFINITIONS


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

METADATA_ADVANCED_VISIBILITY_VALUES = (
    "standard",
    "advanced",
)

METADATA_RULE_TAXONOMY_VALUES = (
    "routing",
    "compatibility",
    "quality",
    "size",
    "bitrate",
    "output",
    "playback",
    "verification",
    "publish",
    "advisory",
    "source_fact",
    "computed_evidence",
    "advanced",
)

METADATA_STRICTNESS_VALUES = (
    "hard",
    "soft",
    "advisory",
    "computed",
    "read_only",
    "inherited",
    "explicit",
    "advanced",
)

_DISPLAY_SECTION_BY_LEGACY_SECTION = {
    "Paths": "Source / Compatibility",
    "Libraries": "Source / Compatibility",
    "Final Library Promotion": "Verification / Publish",
    "Audio": "Audio",
    "Routing": "Routing",
    "Video": "Video",
    "NVENC / Encode": "Video",
    "Remux / Safety": "Advanced",
    "Shared Subtitle Policy": "Subtitles",
    "TX3G Subtitles": "Subtitles",
    "BDPGS Subtitles": "Subtitles",
    "VobSub Subtitles": "Subtitles",
    "ASS / SSA Subtitles": "Filters",
    "Runtime": "Advanced",
    "Logging": "Advanced",
    "Safety": "Advanced",
    "Queue": "Advanced",
    "Role": "Advanced",
    "Coordinator": "Advanced",
    "Worker": "Advanced",
}

_DEFAULT_DISPLAY_RULE_BY_SECTION = {
    "Source / Compatibility": ("source_fact", "compatibility"),
    "Routing": ("routing",),
    "Dimensions": ("compatibility",),
    "Filters": ("playback",),
    "Video": ("quality", "output"),
    "Audio": ("playback", "compatibility"),
    "Subtitles": ("playback", "output"),
    "Container": ("output", "compatibility"),
    "Size / Bitrate Guards": ("size", "bitrate", "verification"),
    "Verification / Publish": ("verification", "publish"),
    "Presets": ("quality",),
    "Advanced": ("advanced",),
}

_PHASE3_DISPLAY_METADATA_BY_KEY: dict[str, dict[str, object]] = {
    "RoutingProfile": {
        "label": "Processing Strategy",
        "short_label": "Strategy",
        "section": "Routing",
        "rule_taxonomy": ("routing", "playback"),
        "strictness": "hard",
        "help_text": "Overall processing strategy. Controls the copy/remux-first policy before encoding is considered.",
    },
    "RouteThresholdMode": {
        "label": "Enforcement Mode",
        "short_label": "Enforcement",
        "section": "Routing",
        "rule_taxonomy": ("routing", "size", "bitrate"),
        "strictness": "hard",
        "help_text": "Used before processing to decide copy/remux versus encode. Selects which route gates are hard: target output size, max bitrate for direct copy, or either.",
    },
    "SizeGuardMode": {
        "label": "Output Size Check",
        "short_label": "Size Check",
        "section": "Size / Bitrate Guards",
        "rule_taxonomy": ("size", "verification"),
        "strictness": "hard",
        "help_text": "Checked after encode. Warns but does not block in warn-only mode. Blocks publish when configured to block if output exceeds the configured size budget.",
    },
    "EncodeTuningPreset": {
        "label": "Encoder Quality Preset",
        "short_label": "Quality Preset",
        "section": "Presets",
        "rule_taxonomy": ("quality", "output"),
        "strictness": "soft",
        "help_text": "Applies only when encoding is required. Chooses the encoder speed/compression tradeoff without changing copy/remux decisions by itself.",
    },
    "EncodeLadder": {
        "label": "Encode Target Mode",
        "short_label": "Target Mode",
        "section": "Presets",
        "rule_taxonomy": ("quality", "size", "bitrate"),
        "strictness": "soft",
        "help_text": "Applies only when encoding is required. Chooses target selection for one output; it does not produce multiple renditions.",
    },
    "VideoCodec": {
        "label": "Video Encoder",
        "short_label": "Encoder",
        "section": "Video",
        "rule_taxonomy": ("quality", "output"),
        "strictness": "soft",
        "help_text": "Applies only when encoding is required. Selects the video encoder used for encoded output.",
    },
    "OutputContainer": {
        "label": "Output Container",
        "short_label": "Container",
        "section": "Container",
        "rule_taxonomy": ("output", "compatibility"),
        "strictness": "hard",
        "help_text": "Output container format used when muxing or encoding creates the saved output; it does not decide whether video is re-encoded.",
    },
    "EncodeThresholdGB": {
        "label": "Movie target output size",
        "short_label": "Movie Target",
        "section": "Size / Bitrate Guards",
        "rule_taxonomy": ("size", "routing"),
        "strictness": "soft",
        "help_text": "GB target output size used as the movie size budget for route and size-policy checks; not the Mbps max bitrate for direct copy.",
    },
    "TVEncodeThresholdGB": {
        "label": "TV target output size",
        "short_label": "TV Target",
        "section": "Size / Bitrate Guards",
        "rule_taxonomy": ("size", "routing"),
        "strictness": "soft",
        "help_text": "GB target output size used as the TV episode size budget for route and size-policy checks; not the Mbps max bitrate for direct copy.",
    },
    "MovieRouteMaxVideoBitrateMbps": {
        "label": "Movie max bitrate for direct copy",
        "short_label": "Movie Copy Max",
        "section": "Size / Bitrate Guards",
        "rule_taxonomy": ("bitrate", "routing"),
        "strictness": "hard",
        "help_text": "Maximum movie video bitrate in Mbps used before processing to decide whether direct copy/remux remains eligible. Above this cap, routing may choose encode.",
    },
    "TVRouteMaxVideoBitrateMbps": {
        "label": "TV max bitrate for direct copy",
        "short_label": "TV Copy Max",
        "section": "Size / Bitrate Guards",
        "rule_taxonomy": ("bitrate", "routing"),
        "strictness": "hard",
        "help_text": "Maximum TV video bitrate in Mbps used before processing to decide whether direct copy/remux remains eligible. Above this cap, routing may choose encode.",
    },
    "MaxEncodeGrowthPercent": {
        "label": "Quality-encode size tolerance",
        "short_label": "Quality Tolerance",
        "section": "Size / Bitrate Guards",
        "rule_taxonomy": ("size", "verification"),
        "strictness": "soft",
        "help_text": "Checked after encode. Allowed output growth for quality encodes; Output Size Check warns or blocks publish when configured to block.",
    },
    "CompatibilityEncodeGrowthPercent": {
        "label": "Compatibility-encode size tolerance",
        "short_label": "Compat Tolerance",
        "section": "Size / Bitrate Guards",
        "rule_taxonomy": ("size", "verification"),
        "strictness": "soft",
        "help_text": "Checked after encode. Allowed output growth for compatibility encodes; Output Size Check warns or blocks publish when configured to block.",
    },
    "AllowH264RemuxIfPlexCompatible": {
        "label": "Copy Plex-Compatible H.264",
        "short_label": "H.264 Copy",
        "section": "Source / Compatibility",
        "rule_taxonomy": ("compatibility", "routing"),
        "strictness": "hard",
        "help_text": "Allows compatible H.264 sources to remain direct-copy/remux candidates when bitrate, dimensions, and routing policy allow it.",
    },
    "H264RemuxMaxBitrateMbps": {
        "label": "H.264 Direct Copy Max Bitrate",
        "short_label": "H.264 Max Mbps",
        "section": "Source / Compatibility",
        "rule_taxonomy": ("bitrate", "compatibility"),
        "strictness": "hard",
        "help_text": "Maximum H.264 video bitrate eligible for the Plex-compatible direct-copy shortcut.",
    },
    "H264RemuxMaxHeight": {
        "label": "H.264 Direct Copy Max Height",
        "short_label": "H.264 Max Height",
        "section": "Dimensions",
        "rule_taxonomy": ("compatibility",),
        "strictness": "hard",
        "help_text": "Maximum H.264 source height eligible for the Plex-compatible direct-copy shortcut.",
    },
    "VideoPreset": {
        "label": "Encoder Speed Preset",
        "short_label": "Speed Preset",
        "section": "Video",
        "rule_taxonomy": ("quality",),
        "strictness": "soft",
        "help_text": "Applies only when encoding is required. Selects the encoder speed/compression tradeoff.",
    },
    "VideoQuality": {
        "label": "Quality Target",
        "short_label": "Quality",
        "section": "Video",
        "rule_taxonomy": ("quality", "size"),
        "strictness": "soft",
        "help_text": "Applies only when encoding is required. Lower values target higher visual quality and larger files.",
    },
    "RemuxSafeVideoCodecs": {
        "label": "Direct Copy Video Codec Allowlist",
        "short_label": "Video Allowlist",
        "section": "Source / Compatibility",
        "rule_taxonomy": ("compatibility", "routing"),
        "strictness": "hard",
        "help_text": "Used before processing to decide whether source video codecs may remain direct-copy/remux candidates without re-encoding.",
    },
    "FallbackCpuQuality": {
        "label": "CPU Fallback Quality",
        "short_label": "CPU Quality",
        "section": "Advanced",
        "rule_taxonomy": ("quality", "advanced"),
        "strictness": "advanced",
        "help_text": "Advanced quality target. Applies only when CPU encoding is selected or required.",
    },
    "CpuEncodePreset": {
        "label": "CPU Encoder Speed Preset",
        "short_label": "CPU Speed",
        "section": "Advanced",
        "rule_taxonomy": ("quality", "advanced"),
        "strictness": "advanced",
        "help_text": "Advanced libx265 speed/compression preset. Applies only when CPU encoding is selected or required.",
    },
    "CpuEncodeProcessPriority": {
        "label": "CPU Encoder Process Priority",
        "short_label": "CPU Priority",
        "section": "Advanced",
        "rule_taxonomy": ("advanced",),
        "strictness": "advanced",
        "help_text": "Advanced Windows process priority used for CPU encode jobs.",
    },
    "CpuEncodeMaxThreads": {
        "label": "CPU Encoder Max Threads",
        "short_label": "CPU Threads",
        "section": "Advanced",
        "rule_taxonomy": ("advanced",),
        "strictness": "advanced",
        "help_text": "Advanced CPU encode thread cap. Zero keeps the encoder default behavior.",
    },
    "ExtraVideoFlags": {
        "label": "Advanced Encoder Flags",
        "short_label": "Extra Flags",
        "section": "Advanced",
        "rule_taxonomy": ("advanced", "output"),
        "strictness": "advanced",
        "help_text": "Advanced raw encoder flags. Applies only when encoding is required through explicit legacy/custom flag paths.",
    },
    "AudioPassthroughProfile": {
        "label": "Audio Passthrough Policy",
        "short_label": "Passthrough",
        "section": "Audio",
        "rule_taxonomy": ("playback", "compatibility"),
        "strictness": "hard",
        "help_text": "Audio copy policy. Controls which audio codecs may pass through instead of being transcoded.",
    },
    "CompatibleAudioCodecs": {
        "label": "Audio Direct Copy Codec Allowlist",
        "short_label": "Audio Allowlist",
        "section": "Audio",
        "rule_taxonomy": ("compatibility", "playback"),
        "strictness": "hard",
        "help_text": "Manual audio codec allowlist used when the passthrough policy selects custom codec control.",
    },
    "PreferredDefaultAudioLanguages": {
        "label": "Preferred Default Audio Languages",
        "short_label": "Audio Languages",
        "section": "Audio",
        "rule_taxonomy": ("playback",),
        "strictness": "soft",
        "help_text": "Ordered language preference for selecting the default audio track when matching tracks are present.",
    },
    "AudioTranscodeCodec": {
        "label": "Audio Transcode Codec",
        "short_label": "Transcode Codec",
        "section": "Audio",
        "rule_taxonomy": ("output", "playback"),
        "strictness": "soft",
        "help_text": "Codec used when an audio track is transcoded instead of copied.",
    },
    "AudioTranscodeBitrate": {
        "label": "Audio Transcode Bitrate",
        "short_label": "Audio Bitrate",
        "section": "Audio",
        "rule_taxonomy": ("bitrate", "quality"),
        "strictness": "soft",
        "help_text": "Target bitrate used when audio is transcoded and automatic channel-based bitrate is not active.",
    },
    "AudioTranscodeAutoBitrateByChannels": {
        "label": "Auto Audio Bitrate by Channels",
        "short_label": "Auto Bitrate",
        "section": "Audio",
        "rule_taxonomy": ("bitrate", "quality"),
        "strictness": "soft",
        "help_text": "Chooses audio transcode bitrate from codec and channel count instead of a fixed bitrate value.",
    },
    "AudioDownmixMode": {
        "label": "Audio Downmix Policy",
        "short_label": "Downmix",
        "section": "Audio",
        "rule_taxonomy": ("playback", "output"),
        "strictness": "soft",
        "help_text": "Controls channel count handling when an audio track is transcoded.",
    },
    "AudioMaxChannels": {
        "label": "Max Audio Channels",
        "short_label": "Max Channels",
        "section": "Audio",
        "rule_taxonomy": ("playback",),
        "strictness": "soft",
        "help_text": "Maximum channel count used when downmix policy caps transcoded audio.",
    },
    "AllowNoAudio": {
        "label": "Allow Outputs Without Audio",
        "short_label": "No Audio",
        "section": "Audio",
        "rule_taxonomy": ("verification", "playback"),
        "strictness": "hard",
        "help_text": "Allows source files with no audio tracks to produce outputs without audio.",
    },
    "SubKeepLanguages": {
        "label": "Subtitle Language Policy",
        "short_label": "Subtitle Langs",
        "section": "Subtitles",
        "rule_taxonomy": ("playback",),
        "strictness": "hard",
        "help_text": "Subtitle language tags kept during subtitle processing and output muxing.",
    },
    "ConvertTx3gToSrt": {
        "label": "Convert TX3G to SRT",
        "short_label": "TX3G to SRT",
        "section": "Subtitles",
        "rule_taxonomy": ("compatibility", "output"),
        "strictness": "hard",
        "help_text": "Subtitle processing option that converts embedded TX3G/mov_text subtitle tracks to SRT.",
    },
    "DropTx3gAfterConversion": {
        "label": "Drop TX3G After Conversion",
        "short_label": "Drop TX3G",
        "section": "Subtitles",
        "rule_taxonomy": ("output",),
        "strictness": "hard",
        "help_text": "Subtitle processing option that drops original TX3G tracks after successful conversion.",
    },
    "CreateExternalTx3gSrtSidecars": {
        "label": "Write TX3G SRT Sidecars",
        "short_label": "TX3G Sidecars",
        "section": "Subtitles",
        "rule_taxonomy": ("output",),
        "strictness": "soft",
        "help_text": "Also writes external SRT sidecars for converted TX3G subtitles.",
    },
    "Tx3gExtractLanguages": {
        "label": "TX3G Extraction Languages",
        "short_label": "TX3G Langs",
        "section": "Subtitles",
        "rule_taxonomy": ("playback", "output"),
        "strictness": "hard",
        "help_text": "Language tags eligible for TX3G subtitle extraction and conversion.",
    },
    "Tx3gPreserveExistingSrt": {
        "label": "Preserve Existing TX3G SRTs",
        "short_label": "Keep TX3G SRTs",
        "section": "Subtitles",
        "rule_taxonomy": ("output",),
        "strictness": "advisory",
        "help_text": "Leaves matching existing TX3G-derived SRT sidecars in place unless reprocessing is explicitly enabled.",
    },
    "Tx3gTreatForcedAsSeparate": {
        "label": "Separate Forced TX3G Subtitles",
        "short_label": "Forced TX3G",
        "section": "Subtitles",
        "rule_taxonomy": ("playback", "output"),
        "strictness": "soft",
        "help_text": "Keeps forced TX3G subtitle outputs separate from full subtitle outputs.",
    },
    "ConvertBdpgsToSrt": {
        "label": "OCR BDPGS to SRT",
        "short_label": "BDPGS OCR",
        "section": "Subtitles",
        "rule_taxonomy": ("compatibility", "output"),
        "strictness": "hard",
        "help_text": "Subtitle processing option that OCRs BDPGS image subtitles to SRT using the configured OCR tool.",
    },
    "DropBdpgsAfterConversion": {
        "label": "Drop BDPGS After OCR",
        "short_label": "Drop BDPGS",
        "section": "Subtitles",
        "rule_taxonomy": ("output",),
        "strictness": "hard",
        "help_text": "Subtitle processing option that drops original BDPGS image subtitles after successful OCR conversion.",
    },
    "BdpgsExtractLanguages": {
        "label": "BDPGS OCR Languages",
        "short_label": "BDPGS Langs",
        "section": "Subtitles",
        "rule_taxonomy": ("playback", "output"),
        "strictness": "hard",
        "help_text": "Language tags eligible for BDPGS OCR subtitle conversion.",
    },
    "BdpgsOcrToolPath": {
        "label": "BDPGS OCR Tool Path",
        "short_label": "BDPGS Tool",
        "section": "Advanced",
        "rule_taxonomy": ("advanced", "output"),
        "strictness": "advanced",
        "help_text": "Advanced path to the BDPGS OCR tool used when BDPGS OCR conversion is enabled.",
    },
    "BdpgsOcrTessdataPath": {
        "label": "BDPGS Tessdata Path",
        "short_label": "Tessdata",
        "section": "Advanced",
        "rule_taxonomy": ("advanced", "output"),
        "strictness": "advanced",
        "help_text": "Advanced optional tessdata path used by the BDPGS OCR tool.",
    },
    "ConvertVobSubToSrt": {
        "label": "OCR VobSub to SRT",
        "short_label": "VobSub OCR",
        "section": "Subtitles",
        "rule_taxonomy": ("compatibility", "output"),
        "strictness": "hard",
        "help_text": "Subtitle processing option that OCRs VobSub bitmap subtitles to SRT using the configured OCR tool.",
    },
    "DropVobSubAfterConversion": {
        "label": "Drop VobSub After OCR",
        "short_label": "Drop VobSub",
        "section": "Subtitles",
        "rule_taxonomy": ("output",),
        "strictness": "hard",
        "help_text": "Subtitle processing option that drops embedded VobSub tracks after successful OCR conversion. External source files are not deleted.",
    },
    "VobSubExtractLanguages": {
        "label": "VobSub OCR Languages",
        "short_label": "VobSub Langs",
        "section": "Subtitles",
        "rule_taxonomy": ("playback", "output"),
        "strictness": "hard",
        "help_text": "Language tags eligible for VobSub OCR subtitle conversion.",
    },
    "VobSubOcrToolPath": {
        "label": "VobSub OCR Tool Path",
        "short_label": "VobSub Tool",
        "section": "Advanced",
        "rule_taxonomy": ("advanced", "output"),
        "strictness": "advanced",
        "help_text": "Advanced path to the VobSub OCR tool used when VobSub OCR conversion is enabled.",
    },
    "VobSubOcrTimeoutSeconds": {
        "label": "VobSub OCR Timeout",
        "short_label": "VobSub Timeout",
        "section": "Advanced",
        "rule_taxonomy": ("advanced", "verification"),
        "strictness": "advanced",
        "help_text": "Advanced timeout for external VobSub OCR commands.",
    },
    "TreatVobSubSignsSongsAsForced": {
        "label": "Treat VobSub Signs/Songs as Forced",
        "short_label": "VobSub Forced",
        "section": "Subtitles",
        "rule_taxonomy": ("playback", "output"),
        "strictness": "soft",
        "help_text": "Marks kept or OCR-converted VobSub signs/songs subtitles as forced.",
    },
    "SubtitleExtractTimeoutSeconds": {
        "label": "Subtitle Extraction Timeout",
        "short_label": "Extract Timeout",
        "section": "Advanced",
        "rule_taxonomy": ("advanced", "verification"),
        "strictness": "advanced",
        "help_text": "Advanced timeout for subtitle extraction helper commands.",
    },
    "SubtitleProbeTimeoutSeconds": {
        "label": "Subtitle Probe Timeout",
        "short_label": "Probe Timeout",
        "section": "Advanced",
        "rule_taxonomy": ("advanced", "verification"),
        "strictness": "advanced",
        "help_text": "Advanced timeout for subtitle probing helper commands.",
    },
    "BdpgsOcrTimeoutSeconds": {
        "label": "BDPGS OCR Timeout",
        "short_label": "BDPGS Timeout",
        "section": "Advanced",
        "rule_taxonomy": ("advanced", "verification"),
        "strictness": "advanced",
        "help_text": "Advanced timeout for external BDPGS OCR commands.",
    },
}

_NUMERIC_LIMITS_BY_KEY = {
    "EncodeThresholdGB": {"min": 1, "step": 1, "unit": "GB"},
    "TVEncodeThresholdGB": {"min": 1, "step": 1, "unit": "GB"},
    "MovieRouteMaxVideoBitrateMbps": {"min": 1, "max": 500, "step": 1, "unit": "Mbps"},
    "TVRouteMaxVideoBitrateMbps": {"min": 1, "max": 500, "step": 1, "unit": "Mbps"},
    "H264RemuxMaxBitrateMbps": {"min": 1, "max": 500, "step": 1, "unit": "Mbps"},
    "H264RemuxMaxHeight": {"min": 1, "max": 4320, "step": 1, "unit": "pixels"},
    "MaxEncodeGrowthPercent": {"min": 0, "max": 1000, "step": 1, "unit": "percent"},
    "CompatibilityEncodeGrowthPercent": {"min": 0, "max": 1000, "step": 1, "unit": "percent"},
    "MinFreeSpaceGB": {"min": 0, "step": 1, "unit": "GB"},
    "OutsourceMinFreeSpaceGB": {"min": 0, "step": 1, "unit": "GB"},
    "VideoQuality": {"min": 1, "max": 51, "step": 1},
    "AudioMaxChannels": {"min": 1, "max": 16, "step": 1, "unit": "channels"},
    "MergeThresholdMs": {"min": 0, "max": 5000, "step": 1, "unit": "ms"},
    "FFmpegEncodeTimeoutSeconds": {"min": 1, "step": 1, "unit": "seconds"},
    "FFmpegCpuEncodeTimeoutSeconds": {"min": 1, "step": 1, "unit": "seconds"},
    "FFmpegRemuxTimeoutSeconds": {"min": 1, "step": 1, "unit": "seconds"},
    "MkvmergeRemuxTimeoutSeconds": {"min": 60, "max": 86400, "step": 1, "unit": "seconds"},
    "SubtitleExtractTimeoutSeconds": {"min": 30, "max": 3600, "step": 1, "unit": "seconds"},
    "SubtitleProbeTimeoutSeconds": {"min": 5, "max": 600, "step": 1, "unit": "seconds"},
    "BdpgsOcrTimeoutSeconds": {"min": 60, "max": 14400, "step": 1, "unit": "seconds"},
    "VobSubOcrTimeoutSeconds": {"min": 60, "max": 14400, "step": 1, "unit": "seconds"},
    "TransientFailureRetryLimit": {"min": 1, "max": 100, "step": 1},
    "SourceScanIntervalSeconds": {"min": 0, "step": 1, "unit": "seconds"},
    "ProcessedIndexRefreshSeconds": {"min": 0, "step": 1, "unit": "seconds"},
    "RobocopyTimeoutSeconds": {"min": 60, "max": 172800, "step": 1, "unit": "seconds"},
    "SourceScanTimeoutSeconds": {"min": 30, "max": 86400, "step": 1, "unit": "seconds"},
    "IndexScanTimeoutSeconds": {"min": 30, "max": 86400, "step": 1, "unit": "seconds"},
    "CleanupScanTimeoutSeconds": {"min": 30, "max": 7200, "step": 1, "unit": "seconds"},
    "CleanupStaleAgeHours": {"min": 1, "max": 720, "step": 1, "unit": "hours"},
    "FallbackCpuQuality": {"min": 1, "max": 51, "step": 1},
    "OutputSizeMultiplier": {"min": 0.1, "max": 2.0, "step": "any"},
    "CpuEncodeMaxThreads": {"min": 0, "max": 256, "step": 1, "unit": "threads"},
}

_KIND_VALUE_TYPES = {
    "bool": "boolean",
    "combo": "string",
    "combo_int": "integer",
    "int": "integer",
    "json": "json",
    "list": "list",
    "optional_float": "number",
    "optional_int": "integer",
    "path": "path",
    "string": "string",
}

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
        "MovieRouteMaxVideoBitrateMbps",
        "TVRouteMaxVideoBitrateMbps",
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

_RAW_CONFIG_FIELD_DEFINITIONS = (
    *BASIC_CONFIG_FIELD_DEFINITIONS,
    *VIDEO_CONFIG_FIELD_DEFINITIONS,
    *SUBTITLE_CONFIG_FIELD_DEFINITIONS,
    *ADVANCED_CONFIG_FIELD_DEFINITIONS,
    *QUEUE_CONFIG_FIELD_DEFINITIONS,
    *NETWORK_CONFIG_FIELD_DEFINITIONS,
)


def _metadata_scope(field: dict[str, object], override_group: str | None) -> str:
    if override_group:
        return "library_overridable"
    if field.get("page") == "Advanced":
        return "advanced"
    return "global_only"


def _value_type(field: dict[str, object]) -> str:
    kind = str(field.get("kind") or "")
    return _KIND_VALUE_TYPES.get(kind, "unknown")


def _advanced_visibility(field: dict[str, object]) -> str:
    return "advanced" if field.get("page") == "Advanced" else "standard"


def _display_section(field: dict[str, object], display_metadata: dict[str, object]) -> str:
    if "section" in display_metadata:
        return str(display_metadata["section"])
    legacy_section = str(field.get("section") or "")
    return _DISPLAY_SECTION_BY_LEGACY_SECTION.get(legacy_section, legacy_section)


def _rule_taxonomy(field: dict[str, object], display_metadata: dict[str, object], display_section: str) -> tuple[str, ...]:
    if "rule_taxonomy" in display_metadata:
        return tuple(str(value) for value in display_metadata["rule_taxonomy"])
    return _DEFAULT_DISPLAY_RULE_BY_SECTION.get(display_section, ("advisory",))


def _strictness(field: dict[str, object], display_metadata: dict[str, object], display_section: str) -> str:
    if "strictness" in display_metadata:
        return str(display_metadata["strictness"])
    if display_section == "Advanced" or field.get("page") in {"Advanced", "Network", "Queue"}:
        return "advanced"
    if display_section in {"Source / Compatibility", "Routing", "Container", "Verification / Publish"}:
        return "hard"
    return "soft"


def _enrich_field_definition(field: dict[str, object], override_groups: dict[str, str]) -> dict[str, object]:
    key = str(field["key"])
    override_group = override_groups.get(key)
    limits = _NUMERIC_LIMITS_BY_KEY.get(key, {})
    display_metadata = _PHASE3_DISPLAY_METADATA_BY_KEY.get(key, {})
    display_section = _display_section(field, display_metadata)
    enriched = dict(field)
    enriched.update(
        {
            "label": display_metadata.get("label", field.get("label")),
            "short_label": display_metadata.get("short_label", display_metadata.get("label", field.get("label"))),
            "help_text": display_metadata.get("help_text", field.get("help")),
            "section": display_section,
            "rule_taxonomy": _rule_taxonomy(field, display_metadata, display_section),
            "strictness": _strictness(field, display_metadata, display_section),
            "unavailable_reason": display_metadata.get("unavailable_reason"),
            "persisted_key": key,
            "override_group": override_group,
            "scope": _metadata_scope(field, override_group),
            "value_type": _value_type(field),
            "allowed_values": tuple(field["choices"]) if "choices" in field else None,
            "min": limits.get("min"),
            "max": limits.get("max"),
            "step": limits.get("step"),
            "unit": limits.get("unit"),
            "default_source": "field_definition" if "default" in field else "unknown",
            "default_value": field.get("default"),
            "library_override_allowed": override_group is not None,
            "advanced_visibility": _advanced_visibility(field),
            "validation_owner": "backend",
            "runtime_consumer": "deferred",
            "migration_status": "stable_persisted_key",
        }
    )
    return enriched


def _enrich_field_definitions(fields: tuple[dict[str, object], ...]) -> tuple[dict[str, object], ...]:
    return tuple(_enrich_field_definition(dict(field), METADATA_LIBRARY_OVERRIDE_GROUP_BY_KEY) for field in fields)


CONFIG_FIELD_DEFINITIONS = _enrich_field_definitions(_RAW_CONFIG_FIELD_DEFINITIONS)

CONFIG_MANAGED_KEYS = [field["key"] for field in CONFIG_FIELD_DEFINITIONS]
