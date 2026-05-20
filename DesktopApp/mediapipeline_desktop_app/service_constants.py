from __future__ import annotations

import re

from .contracts.active_job import ACTIVE_JOB_SCHEMA_VERSION
from .contracts.control_flag import CONTROL_FLAG_SCHEMA_VERSION

APP_STATE_NAME = "MediaPipelineRemuxEncodeAIO_DesktopApp.state.json"
CONFIG_SCHEMA_VERSION = 1
CONTROL_FLAG_STALE_AFTER_SECONDS = 3600.0
MEDIA_FILE_SUFFIXES = frozenset({".mkv", ".mp4", ".m4v", ".mov", ".avi", ".ts", ".m2ts", ".webm"})
FOLDER_POLICY_SIDECAR_NAME = "mediapipeline.folder.json"
FOLDER_POLICY_SCHEMA_VERSION = "folder_policy.v1"
FAILURE_CLEAR_MANIFEST_SCHEMA_VERSION = "failure_workspace_clear_manifest.v1"
LOG_LEVEL_VALUES = ("", "ERROR", "WARN", "INFO", "DEBUG")
PROCESS_LAUNCH_ERROR_TAIL_LINES = 24
PROCESS_LAUNCH_READY_CHECK_SECONDS = 0.35
PIPELINE_PROGRESS_LAUNCH_CLEANUP_STALE_SECONDS = 120.0
AUDIT_PROGRESS_LAUNCH_CLEANUP_STALE_SECONDS = 120.0
PROFILE_NAME_PATTERN = re.compile(r"^[A-Za-z0-9_-]{1,80}$")
AUDIO_PASSTHROUGH_PROFILE_DEFAULT = "plex_balanced"
AUDIO_PASSTHROUGH_PROFILE_NAMES = (
    "plex_balanced",
    "compatibility",
    "lossless_passthrough",
    "custom_codec_list",
)
AUDIO_PASSTHROUGH_PROFILE_DESCRIPTIONS = {
    "plex_balanced": "Copy common Plex-friendly audio plus TrueHD/MLP; normalize DTS, FLAC, PCM, and unknown codecs.",
    "compatibility": "Copy only AAC/AC3/EAC3/MP3/Opus/Vorbis; normalize lossless and DTS-style tracks.",
    "lossless_passthrough": "Copy common lossy, lossless, DTS, and FLAC tracks; still normalize PCM-like tracks.",
    "custom_codec_list": "Use the custom Audio Passthrough codec list exactly as entered.",
}
AUDIO_PASSTHROUGH_PROFILE_CODECS = {
    "plex_balanced": ("aac", "ac3", "eac3", "mp3", "opus", "vorbis", "truehd", "mlp"),
    "compatibility": ("aac", "ac3", "eac3", "mp3", "opus", "vorbis"),
    "lossless_passthrough": ("aac", "ac3", "eac3", "mp3", "opus", "vorbis", "truehd", "mlp", "dts", "dts_hd_ma", "dts-hd", "flac", "alac"),
}
ROUTING_PROFILE_DEFAULT = "plex_direct_stream"
ROUTING_PROFILE_NAMES = (
    "plex_direct_stream",
    "plex_direct_play",
    "archive_shrink",
    "archive_quality",
    "manual",
)
ROUTING_PROFILE_DESCRIPTIONS = {
    "plex_direct_stream": "Default Plex-first routing. Copy compatible H.264/HEVC sources and encode only when bitrate, resolution, codec, or policy needs it.",
    "plex_direct_play": "Stricter Plex direct-play target. More willing to encode when compatibility scoring falls below the direct-play floor.",
    "archive_shrink": "Size-focused archive routing. Large files may encode even when already Plex-compatible.",
    "archive_quality": "Preserve quality first; keep compatible sources as copy/remux unless policy requires encode.",
    "manual": "Operator-driven routing. Folder force/prefer rules and explicit settings matter most.",
}
SIZE_GUARD_MODE_DEFAULT = "advisory"
SIZE_GUARD_MODE_NAMES = ("advisory", "strict", "off")
SIZE_GUARD_MODE_DESCRIPTIONS = {
    "advisory": "Warn and record when an encode grows past the configured size limit, but still publish if verification passes.",
    "strict": "Reject oversized encodes for manual review instead of publishing them.",
    "off": "Disable post-encode size growth checks.",
}
PLEX_RENAME_DEFAULT_REMOVE_TERMS = (
    "sample",
    "trailer",
    "extras",
    "featurette",
    "deleted scenes",
    "behind the scenes",
)
RENAME_MOVIE_FILTER_OPTIONS = (
    (
        "video_source",
        "Video / source tags",
        "Removes 1080p, 2160p, BluRay, WEBRip, HEVC, x264, HDR, UHD, and similar release/source markers.",
    ),
    (
        "audio_channels",
        "Audio / channels",
        "Removes AAC, AC3, EAC3, TrueHD, Atmos, DTS, DD5.1, 6CH, 5.1, 7.1, and similar audio markers.",
    ),
    (
        "editions",
        "Editions / cuts",
        "Removes EXTENDED, REMASTERED, PROPER, REPACK, UNRATED, IMAX, director's cut, final cut, and similar edition tags.",
    ),
    (
        "file_size",
        "File size tags",
        "Removes tags such as 1400MB, 2GB, and 4.7GB.",
    ),
    (
        "services_containers",
        "Services / containers",
        "Removes AMZN, NF, DSNP, HMAX, Hulu, iTunes, AppleTV, MKV, MP4, and M4V markers embedded in names.",
    ),
    (
        "release_groups",
        "Release groups",
        "Removes common leading/trailing groups such as RARBG, RBG, YIFY, YTS, GalaxyRG, BONE, PSA, Tigole, and Kris.",
    ),
)
RENAME_MOVIE_FILTER_OPTION_KEYS = tuple(option[0] for option in RENAME_MOVIE_FILTER_OPTIONS)
RENAME_TOOL_SIDECAR_SCHEMA_VERSION = "rename_tool.v1"
RERUN_CSV_COLUMNS = (
    "enabled",
    "source_path",
    "media_kind",
    "audit_issue_codes",
    "stage_mode",
    "post_success_original",
    "return_mode",
    "plex_planned_path",
    "source_size",
    "source_mtime_utc",
    "source_identity_v2",
    "priority_fix_level",
    "effective_bucket",
    "primary_issue_code",
    "lookup_title",
    "relative_path",
    "notes",
)
SCHEDULE_DAY_NAMES = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")
TOP_LEVEL_CONFIG_ORDER = (
    "ConfigSchemaVersion",
    "SourceMovies",
    "SourceTV",
    "Outsource",
    "LocalBase",
    "EncodeThresholdGB",
    "TVEncodeThresholdGB",
    "RoutingProfile",
    "AllowH264RemuxIfPlexCompatible",
    "H264RemuxMaxBitrateMbps",
    "H264RemuxMaxHeight",
    "SizeGuardMode",
    "MaxEncodeGrowthPercent",
    "CompatibilityEncodeGrowthPercent",
    "MinFreeSpaceGB",
    "OutsourceMinFreeSpaceGB",
    "VideoCodec",
    "VideoPreset",
    "VideoQuality",
    "OutputContainer",
    "EncodeTuningPreset",
    "EncodeLadder",
    "ExtraVideoFlags",
    "AudioPassthroughProfile",
    "CompatibleAudioCodecs",
    "PreferredDefaultAudioLanguages",
    "AudioTranscodeCodec",
    "AudioTranscodeBitrate",
    "AudioDownmixMode",
    "AudioMaxChannels",
    "AllowNoAudio",
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
    "ExcludeSubtitleStyles",
    "IncludeSubtitleStyles",
    "RemuxSafeVideoCodecs",
    "ValidExtensions",
    "FileStabilityWait",
    "SkipStabilityCheck",
    "EnableIntegrityCheck",
    "CreateTVSubfolder",
    "AggressiveEpisodeParsing",
    "RobocopyFlags",
    "DebugMode",
    "LogRetentionDays",
    "ConsoleLogLevel",
    "FileLogLevel",
    "PriorityMarkers",
    "MinPipelineVersion",
    "ReprocessAll",
    "OutputSizeMultiplier",
    "FallbackCpuQuality",
    "FFmpegEncodeTimeoutSeconds",
    "FFmpegRemuxTimeoutSeconds",
    "SubtitleExtractTimeoutSeconds",
    "SubtitleProbeTimeoutSeconds",
    "BdpgsOcrTimeoutSeconds",
    "AllowSystemTools",
    "RobocopyTimeoutSeconds",
    "TransientFailureRetryLimit",
    "SourceScanIntervalSeconds",
    "SourceScanTimeoutSeconds",
    "ProcessedIndexRefreshSeconds",
    "IndexScanTimeoutSeconds",
    "CleanupScanTimeoutSeconds",
    "CleanupRemoteStaging",
    "CleanupStaleAgeHours",
    "ShowOverrides",
)
VLC_LONG_PATH_THRESHOLD = 240
