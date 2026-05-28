"""Canonical configuration shape for the media pipeline.

Mirrors `Pipeline/MediaPipeline_config_template.psd1` field-for-field as of
2026-05-28. ADR-0004 will swap stdlib dataclasses for pydantic so JSON
Schema generation and runtime validation are automatic; until then these
dataclasses define intent and field names only.

When `Pipeline/MediaPipeline_config_template.psd1` changes, update this
file and bump `CONFIG_SCHEMA_VERSION`. The Phase 2 round-trip test
(`tests/python/contract/test_config_roundtrip.py`, planned) will assert
that `psd1 → Config → psd1` is a whitespace-only diff.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

CONFIG_SCHEMA_VERSION = 1

# ----------------------------------------------------------------------
# Sub-shapes grouped by concern. Keep field names verbatim with the PSD1.
# ----------------------------------------------------------------------


@dataclass
class Paths:
    """Source, output, and scratch roots."""

    SourceMovies: str = "C:\\MediaPipeline\\Incoming\\Movies"
    SourceTV: str = "C:\\MediaPipeline\\Incoming\\TV"
    Outsource: str = "C:\\MediaPipeline\\Processed"
    LocalBase: str = "C:\\MediaPipeline\\Scratch"
    MinFreeSpaceGB: int = 50
    OutsourceMinFreeSpaceGB: int = 50


@dataclass
class Routing:
    """Routing thresholds and remux-vs-encode policy."""

    EncodeThresholdGB: float = 8
    TVEncodeThresholdGB: float = 3
    RoutingProfile: Literal[
        "plex_direct_stream", "plex_balanced", "plex_archive"
    ] = "plex_direct_stream"
    AllowH264RemuxIfPlexCompatible: bool = True
    H264RemuxMaxBitrateMbps: int = 35
    H264RemuxMaxHeight: int = 1080
    RemuxSafeVideoCodecs: list[str] = field(
        default_factory=lambda: ["hevc", "h265", "h.265", "av1"]
    )


@dataclass
class SizeGuard:
    """Size-guard policy for remux and encode output."""

    SizeGuardMode: Literal["off", "advisory", "strict"] = "advisory"
    MaxEncodeGrowthPercent: float = 5
    CompatibilityEncodeGrowthPercent: float = 15
    RemuxSizeGuardMode: Literal["off", "advisory", "strict"] = "strict"
    MaxRemuxGrowthPercent: float = 20
    OutputSizeMultiplier: float = 0.7


@dataclass
class VideoEncode:
    """Hardware/CPU encode parameters."""

    VideoCodec: str = "hevc_nvenc"
    VideoPreset: str = "p7"
    VideoQuality: int = 22
    OutputContainer: Literal["mkv", "mp4"] = "mkv"
    EncodeTuningPreset: str = "balanced_nvenc"
    EncodeLadder: str = "auto"
    ExtraVideoFlags: list[str] = field(default_factory=list)
    FallbackCpuQuality: int = 20
    CpuEncodePreset: str = "medium"
    CpuEncodeProcessPriority: Literal[
        "low", "belownormal", "normal", "abovenormal", "high"
    ] = "belownormal"
    CpuEncodeMaxThreads: int = 0  # 0 = auto


@dataclass
class Audio:
    """Audio routing and passthrough policy."""

    AudioPassthroughProfile: str = "plex_balanced"
    CompatibleAudioCodecs: list[str] = field(
        default_factory=lambda: [
            "aac",
            "ac3",
            "eac3",
            "mp3",
            "opus",
            "vorbis",
            "truehd",
            "mlp",
        ]
    )
    PreferredDefaultAudioLanguages: list[str] = field(
        default_factory=lambda: ["english"]
    )


@dataclass
class Subtitles:
    """Subtitle keep/drop/convert policy across ASS, TX3G, BDPGS, SRT."""

    SubKeepLanguages: list[str] = field(
        default_factory=lambda: ["eng", "en", "english", "und", ""]
    )

    # TX3G
    ConvertTx3gToSrt: bool = True
    DropTx3gAfterConversion: bool = False
    CreateExternalTx3gSrtSidecars: bool = False
    Tx3gExtractLanguages: list[str] = field(
        default_factory=lambda: ["eng", "en", "english", "und", ""]
    )
    Tx3gPreserveExistingSrt: bool = True
    Tx3gTreatForcedAsSeparate: bool = True
    TreatTx3gSignsSongsAsForced: bool = False

    # BDPGS
    ConvertBdpgsToSrt: bool = False
    DropBdpgsAfterConversion: bool = False
    BdpgsExtractLanguages: list[str] = field(
        default_factory=lambda: ["eng", "en", "english", "und", ""]
    )
    BdpgsOcrToolPath: str = "Tools\\PgsToSrt\\PgsToSrt.exe"
    BdpgsOcrTessdataPath: str = "Tools\\PgsToSrt\\tessdata"
    TreatBdpgsSignsSongsAsForced: bool = False

    # ASS
    DropAssAfterConversion: bool = False
    StripFormatting: bool = True
    RemoveKaraoke: bool = True
    MergeAdjacent: bool = True
    MergeThresholdMs: int = 150
    KeepSignsAndSongs: bool = True
    TreatAssSignsSongsAsForced: bool = False

    # Cross-format
    SubSDHTitleKeywords: list[str] = field(
        default_factory=lambda: [
            "sdh",
            "hearing impaired",
            "hearing-impaired",
            "cc",
            "closed caption",
            "closedcaption",
        ]
    )
    SubSupplementalKeywords: list[str] = field(
        default_factory=lambda: [
            "sign",
            "song",
            "karaoke",
            "chapter",
            "opening",
            "ending",
        ]
    )
    ExcludeSubtitleStyles: list[str] = field(
        default_factory=lambda: [
            "Sign",
            "Sign *",
            "Sign-*",
            "Signs",
            "Signs *",
            "Signs-*",
            "OP",
            "OP *",
            "OP-*",
            "OP_*",
            "Opening*",
            "ED",
            "ED *",
            "ED-*",
            "ED_*",
            "Ending*",
            "*Lyrics*",
            "*Romaji*",
            "*Kanji*",
            "Song",
            "Song *",
            "Song-*",
            "Title",
            "Show Title",
            "Episode Title",
            "Next Episode",
            "Next *",
            "Credits",
            "Credit*",
            "Note",
            "Note*",
            "Caption",
            "Caption*",
            "fs",
        ]
    )
    IncludeSubtitleStyles: list[str] = field(default_factory=list)


@dataclass
class Publish:
    """Publish, scratch, and pending-publish behavior."""

    DeferredPublish: bool = False
    ValidExtensions: list[str] = field(
        default_factory=lambda: [".mkv", ".mp4", ".avi", ".mov", ".m4v", ".ts", ".m2ts"]
    )
    CreateTVSubfolder: bool = True
    RobocopyFlags: list[str] = field(
        default_factory=lambda: ["/J", "/R:3", "/W:15", "/MT:2", "/NP", "/NDL", "/NFL"]
    )


@dataclass
class Stability:
    """File stability and integrity checks."""

    FileStabilityWait: int = 15
    SkipStabilityCheck: bool = False
    EnableIntegrityCheck: bool = True


@dataclass
class Naming:
    """Filename parsing and TV-folder layout."""

    AggressiveEpisodeParsing: bool = False
    PriorityMarkers: list[str] = field(default_factory=lambda: ["!", "[NOW]"])


@dataclass
class Concurrency:
    """Parallelism and queue priority."""

    MaxParallelEncodes: int = 1
    ParallelEncodeMode: Literal["single", "multi"] = "single"


@dataclass
class Timeouts:
    """All subprocess and scan timeouts (seconds)."""

    FFmpegEncodeTimeoutSeconds: int = 21600
    FFmpegCpuEncodeTimeoutSeconds: int = 43200
    FFmpegRemuxTimeoutSeconds: int = 7200
    MkvmergeRemuxTimeoutSeconds: int = 7200
    SubtitleExtractTimeoutSeconds: int = 180
    SubtitleProbeTimeoutSeconds: int = 30
    BdpgsOcrTimeoutSeconds: int = 1800
    OutputValidationProbeTimeoutSeconds: int = 60
    RobocopyTimeoutSeconds: int = 14400
    SourceScanTimeoutSeconds: int = 1800
    IndexScanTimeoutSeconds: int = 1800
    CleanupScanTimeoutSeconds: int = 300


@dataclass
class Validation:
    """Output validation thresholds."""

    OutputValidationMinSizeBytes: int = 1024
    OutputValidationDurationToleranceSeconds: int = 2


@dataclass
class Cleanup:
    """Scratch cleanup and remote staging policy."""

    CleanupRemoteStaging: bool = False
    CleanupStaleAgeHours: int = 24


@dataclass
class Scheduling:
    """Background scan cadence."""

    SourceScanIntervalSeconds: int = 300
    ProcessedIndexRefreshSeconds: int = 900


@dataclass
class Retries:
    """Transient failure retry policy."""

    TransientFailureRetryLimit: int = 3


@dataclass
class Diagnostics:
    """Logging and debug behavior."""

    DebugMode: bool = True
    LogRetentionDays: int = 7
    AllowSystemTools: bool = False


@dataclass
class RunFlags:
    """Top-level operational flags."""

    ReprocessAll: bool = False


# ----------------------------------------------------------------------
# Top-level Config aggregates all groups. Group names are NOT part of the
# PSD1 shape — the PSD1 is a flat dict. The round-trip serializer flattens
# this back to the PSD1 layout.
# ----------------------------------------------------------------------


@dataclass
class Config:
    """Aggregate pipeline configuration.

    Field groups are organizational only. The on-disk PSD1 is a flat
    hashtable; `app/config/load.py` and `app/config/save.py` (Phase 2)
    flatten and unflatten across this boundary.
    """

    ConfigSchemaVersion: int = CONFIG_SCHEMA_VERSION
    paths: Paths = field(default_factory=Paths)
    routing: Routing = field(default_factory=Routing)
    size_guard: SizeGuard = field(default_factory=SizeGuard)
    video: VideoEncode = field(default_factory=VideoEncode)
    audio: Audio = field(default_factory=Audio)
    subtitles: Subtitles = field(default_factory=Subtitles)
    publish: Publish = field(default_factory=Publish)
    stability: Stability = field(default_factory=Stability)
    naming: Naming = field(default_factory=Naming)
    concurrency: Concurrency = field(default_factory=Concurrency)
    timeouts: Timeouts = field(default_factory=Timeouts)
    validation: Validation = field(default_factory=Validation)
    cleanup: Cleanup = field(default_factory=Cleanup)
    scheduling: Scheduling = field(default_factory=Scheduling)
    retries: Retries = field(default_factory=Retries)
    diagnostics: Diagnostics = field(default_factory=Diagnostics)
    run_flags: RunFlags = field(default_factory=RunFlags)


# Map every Config sub-group field back to a flat PSD1 key. Used by the
# Phase 2 round-trip serializer. Listed here so a single missed mapping
# fails loudly in one test rather than silently dropping a key.
FLAT_PSD1_KEYS: tuple[str, ...] = (
    "ConfigSchemaVersion",
    # paths
    "SourceMovies", "SourceTV", "Outsource", "LocalBase",
    "MinFreeSpaceGB", "OutsourceMinFreeSpaceGB",
    # routing
    "EncodeThresholdGB", "TVEncodeThresholdGB", "RoutingProfile",
    "AllowH264RemuxIfPlexCompatible", "H264RemuxMaxBitrateMbps",
    "H264RemuxMaxHeight", "RemuxSafeVideoCodecs",
    # size_guard
    "SizeGuardMode", "MaxEncodeGrowthPercent",
    "CompatibilityEncodeGrowthPercent", "RemuxSizeGuardMode",
    "MaxRemuxGrowthPercent", "OutputSizeMultiplier",
    # video
    "VideoCodec", "VideoPreset", "VideoQuality", "OutputContainer",
    "EncodeTuningPreset", "EncodeLadder", "ExtraVideoFlags",
    "FallbackCpuQuality", "CpuEncodePreset", "CpuEncodeProcessPriority",
    "CpuEncodeMaxThreads",
    # audio
    "AudioPassthroughProfile", "CompatibleAudioCodecs",
    "PreferredDefaultAudioLanguages",
    # subtitles
    "SubKeepLanguages",
    "ConvertTx3gToSrt", "DropTx3gAfterConversion",
    "CreateExternalTx3gSrtSidecars", "Tx3gExtractLanguages",
    "Tx3gPreserveExistingSrt", "Tx3gTreatForcedAsSeparate",
    "TreatTx3gSignsSongsAsForced",
    "ConvertBdpgsToSrt", "DropBdpgsAfterConversion",
    "BdpgsExtractLanguages", "BdpgsOcrToolPath", "BdpgsOcrTessdataPath",
    "TreatBdpgsSignsSongsAsForced",
    "DropAssAfterConversion", "StripFormatting", "RemoveKaraoke",
    "MergeAdjacent", "MergeThresholdMs", "KeepSignsAndSongs",
    "TreatAssSignsSongsAsForced",
    "SubSDHTitleKeywords", "SubSupplementalKeywords",
    "ExcludeSubtitleStyles", "IncludeSubtitleStyles",
    # publish
    "DeferredPublish", "ValidExtensions", "CreateTVSubfolder",
    "RobocopyFlags",
    # stability
    "FileStabilityWait", "SkipStabilityCheck", "EnableIntegrityCheck",
    # naming
    "AggressiveEpisodeParsing", "PriorityMarkers",
    # concurrency
    "MaxParallelEncodes", "ParallelEncodeMode",
    # timeouts
    "FFmpegEncodeTimeoutSeconds", "FFmpegCpuEncodeTimeoutSeconds",
    "FFmpegRemuxTimeoutSeconds", "MkvmergeRemuxTimeoutSeconds",
    "SubtitleExtractTimeoutSeconds", "SubtitleProbeTimeoutSeconds",
    "BdpgsOcrTimeoutSeconds", "OutputValidationProbeTimeoutSeconds",
    "RobocopyTimeoutSeconds", "SourceScanTimeoutSeconds",
    "IndexScanTimeoutSeconds", "CleanupScanTimeoutSeconds",
    # validation
    "OutputValidationMinSizeBytes",
    "OutputValidationDurationToleranceSeconds",
    # cleanup
    "CleanupRemoteStaging", "CleanupStaleAgeHours",
    # scheduling
    "SourceScanIntervalSeconds", "ProcessedIndexRefreshSeconds",
    # retries
    "TransientFailureRetryLimit",
    # diagnostics
    "DebugMode", "LogRetentionDays", "AllowSystemTools",
    # run_flags
    "ReprocessAll",
)


__all__ = [
    "CONFIG_SCHEMA_VERSION",
    "Config",
    "Paths",
    "Routing",
    "SizeGuard",
    "VideoEncode",
    "Audio",
    "Subtitles",
    "Publish",
    "Stability",
    "Naming",
    "Concurrency",
    "Timeouts",
    "Validation",
    "Cleanup",
    "Scheduling",
    "Retries",
    "Diagnostics",
    "RunFlags",
    "FLAT_PSD1_KEYS",
]
