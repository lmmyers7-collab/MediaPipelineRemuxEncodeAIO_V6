"""Canonical Pydantic contract for MediaPipeline configuration.

The runtime PSD1, the desktop settings schema, and generated JSON Schema
share this flat field shape. Field names intentionally match the PSD1 keys
instead of using snake_case aliases so round-trips do not need a key map.
"""

from __future__ import annotations

from typing import Any, ClassVar, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

CONFIG_SCHEMA_VERSION: Literal[1] = 1

REQUIRED_CONFIG_KEYS: tuple[str, ...] = (
    "SourceMovies",
    "SourceTV",
    "Outsource",
    "LocalBase",
    "EncodeThresholdGB",
    "TVEncodeThresholdGB",
    "MinFreeSpaceGB",
    "VideoCodec",
    "VideoPreset",
    "VideoQuality",
    "OutputContainer",
    "CompatibleAudioCodecs",
    "SubKeepLanguages",
    "SubSDHTitleKeywords",
    "SubSupplementalKeywords",
    "DropAssAfterConversion",
    "RemuxSafeVideoCodecs",
    "ValidExtensions",
    "FileStabilityWait",
    "EnableIntegrityCheck",
    "CreateTVSubfolder",
    "RobocopyFlags",
    "DebugMode",
    "SkipStabilityCheck",
)

PS_CONFIG_KEY_ORDER: tuple[str, ...] = (
    "ConfigSchemaVersion",
    "SourceMovies",
    "SourceTV",
    "Outsource",
    "LocalBase",
    "EncodeThresholdGB",
    "TVEncodeThresholdGB",
    "RoutingProfile",
    "MovieRouteMaxVideoBitrateMbps",
    "TVRouteMaxVideoBitrateMbps",
    "AllowH264RemuxIfPlexCompatible",
    "H264RemuxMaxBitrateMbps",
    "H264RemuxMaxHeight",
    "SizeGuardMode",
    "MaxEncodeGrowthPercent",
    "CompatibilityEncodeGrowthPercent",
    "MinFreeSpaceGB",
    "OutsourceMinFreeSpaceGB",
    "DeferredPublish",
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
    "AudioTranscodeAutoBitrateByChannels",
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
    "PriorityMarkers",
    "MixPriorityPhase",
    "QueueOrderingStrategy",
    "ConsoleLogLevel",
    "FileLogLevel",
    "MaxParallelEncodes",
    "ParallelEncodeMode",
    "FallbackCpuQuality",
    "CpuEncodePreset",
    "CpuEncodeProcessPriority",
    "CpuEncodeMaxThreads",
    "OutputSizeMultiplier",
    "FFmpegEncodeTimeoutSeconds",
    "FFmpegCpuEncodeTimeoutSeconds",
    "FFmpegRemuxTimeoutSeconds",
    "MkvmergeRemuxTimeoutSeconds",
    "SubtitleExtractTimeoutSeconds",
    "SubtitleProbeTimeoutSeconds",
    "BdpgsOcrTimeoutSeconds",
    "OutputValidationProbeTimeoutSeconds",
    "OutputValidationMinSizeBytes",
    "OutputValidationDurationToleranceSeconds",
    "AllowSystemTools",
    "RobocopyTimeoutSeconds",
    "TransientFailureRetryLimit",
    "IndexScanTimeoutSeconds",
    "SourceScanTimeoutSeconds",
    "CleanupScanTimeoutSeconds",
    "CleanupRemoteStaging",
    "CleanupStaleAgeHours",
    "SourceScanIntervalSeconds",
    "ProcessedIndexRefreshSeconds",
    "MinPipelineVersion",
    "ReprocessAll",
    "ShowOverrides",
)

NETWORK_CONFIG_KEYS: tuple[str, ...] = (
    "NetworkRole",
    "CoordinatorPort",
    "CoordinatorBindAddress",
    "CoordinatorAlsoEncodeLocally",
    "CoordinatorHeartbeatTimeoutMins",
    "CoordinatorAuthToken",
    "WorkerCoordinatorUrl",
    "WorkerName",
    "WorkerAuthToken",
    "WorkerPollIntervalSecs",
    "WorkerSourcePathMap",
    "WorkerConfigOverrides",
)

CONFIG_KEY_ORDER: tuple[str, ...] = PS_CONFIG_KEY_ORDER + NETWORK_CONFIG_KEYS

DESKTOP_SCHEMA_CONFIG_KEYS: tuple[str, ...] = (
    "SourceMovies",
    "SourceTV",
    "Outsource",
    "LocalBase",
    "CreateTVSubfolder",
    "AudioPassthroughProfile",
    "CompatibleAudioCodecs",
    "PreferredDefaultAudioLanguages",
    "AudioTranscodeCodec",
    "AudioTranscodeBitrate",
    "AudioTranscodeAutoBitrateByChannels",
    "AudioDownmixMode",
    "AudioMaxChannels",
    "AllowNoAudio",
    "EncodeThresholdGB",
    "TVEncodeThresholdGB",
    "RoutingProfile",
    "MovieRouteMaxVideoBitrateMbps",
    "TVRouteMaxVideoBitrateMbps",
    "AllowH264RemuxIfPlexCompatible",
    "H264RemuxMaxBitrateMbps",
    "H264RemuxMaxHeight",
    "SizeGuardMode",
    "MaxEncodeGrowthPercent",
    "CompatibilityEncodeGrowthPercent",
    "DeferredPublish",
    "AggressiveEpisodeParsing",
    "VideoCodec",
    "VideoPreset",
    "VideoQuality",
    "OutputContainer",
    "EncodeTuningPreset",
    "EncodeLadder",
    "ExtraVideoFlags",
    "RemuxSafeVideoCodecs",
    "FallbackCpuQuality",
    "CpuEncodePreset",
    "CpuEncodeProcessPriority",
    "FFmpegCpuEncodeTimeoutSeconds",
    "MkvmergeRemuxTimeoutSeconds",
    "CpuEncodeMaxThreads",
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
    "DropAssAfterConversion",
    "RemoveKaraoke",
    "KeepSignsAndSongs",
    "TreatAssSignsSongsAsForced",
    "TreatTx3gSignsSongsAsForced",
    "TreatBdpgsSignsSongsAsForced",
    "StripFormatting",
    "MergeAdjacent",
    "MergeThresholdMs",
    "SubSDHTitleKeywords",
    "SubSupplementalKeywords",
    "ExcludeSubtitleStyles",
    "IncludeSubtitleStyles",
    "DebugMode",
    "ConsoleLogLevel",
    "FileLogLevel",
    "LogRetentionDays",
    "MinFreeSpaceGB",
    "OutsourceMinFreeSpaceGB",
    "FFmpegEncodeTimeoutSeconds",
    "FFmpegRemuxTimeoutSeconds",
    "SubtitleExtractTimeoutSeconds",
    "SubtitleProbeTimeoutSeconds",
    "BdpgsOcrTimeoutSeconds",
    "AllowSystemTools",
    "RobocopyTimeoutSeconds",
    "TransientFailureRetryLimit",
    "MinPipelineVersion",
    "OutputSizeMultiplier",
    "EnableIntegrityCheck",
    "RobocopyFlags",
    "PriorityMarkers",
    "SourceScanIntervalSeconds",
    "SourceScanTimeoutSeconds",
    "ProcessedIndexRefreshSeconds",
    "ReprocessAll",
    "IndexScanTimeoutSeconds",
    "CleanupScanTimeoutSeconds",
    "ValidExtensions",
    "CleanupRemoteStaging",
    "CleanupStaleAgeHours",
    *NETWORK_CONFIG_KEYS,
)

LIST_CONFIG_KEYS: tuple[str, ...] = (
    "ExtraVideoFlags",
    "CompatibleAudioCodecs",
    "PreferredDefaultAudioLanguages",
    "SubKeepLanguages",
    "Tx3gExtractLanguages",
    "BdpgsExtractLanguages",
    "SubSDHTitleKeywords",
    "SubSupplementalKeywords",
    "ExcludeSubtitleStyles",
    "IncludeSubtitleStyles",
    "RemuxSafeVideoCodecs",
    "ValidExtensions",
    "RobocopyFlags",
    "PriorityMarkers",
)

COMPATIBLE_AUDIO_CODECS_DEFAULT: tuple[str, ...] = (
    "aac",
    "ac3",
    "eac3",
    "mp3",
    "opus",
    "vorbis",
    "truehd",
    "mlp",
)
SUBTITLE_LANGUAGE_DEFAULT: tuple[str, ...] = ("eng", "en", "und", "")
SUBTITLE_EXTRACT_LANGUAGE_DEFAULT: tuple[str, ...] = ("eng", "en", "und")
SUB_SDH_KEYWORD_DEFAULT: tuple[str, ...] = (
    "sdh",
    "hearing impaired",
    "hearing-impaired",
    "cc",
    "closed caption",
    "closedcaption",
)
SUB_SUPPLEMENTAL_KEYWORD_DEFAULT: tuple[str, ...] = (
    "sign",
    "song",
    "karaoke",
    "chapter",
    "opening",
    "ending",
)
EXCLUDE_SUBTITLE_STYLES_DEFAULT: tuple[str, ...] = (
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
)


def _list_default(values: tuple[str, ...]) -> list[str]:
    return list(values)


class Config(BaseModel):
    """Flat config model matching PSD1 keys and WebView JSON payloads."""

    model_config: ClassVar[ConfigDict] = ConfigDict(
        extra="allow",
        json_schema_extra={
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "$id": "https://local.mediapipeline/schemas/config.v1.schema.json",
            "x-config-schema-version": CONFIG_SCHEMA_VERSION,
            "required": list(REQUIRED_CONFIG_KEYS),
        },
    )

    ConfigSchemaVersion: Literal[1] = CONFIG_SCHEMA_VERSION

    SourceMovies: str = Field(default=r"C:\MediaPipeline\Incoming\Movies", min_length=1)
    SourceTV: str = Field(default=r"C:\MediaPipeline\Incoming\TV", min_length=1)
    Outsource: str = Field(default=r"C:\MediaPipeline\Processed", min_length=1)
    LocalBase: str = Field(default=r"C:\MediaPipeline\Scratch", min_length=1)

    EncodeThresholdGB: int = Field(default=8, ge=1)
    TVEncodeThresholdGB: int = Field(default=3, ge=1)
    RoutingProfile: Literal[
        "plex_direct_stream",
        "plex_direct_play",
        "archive_shrink",
        "archive_quality",
        "manual",
    ] = "plex_direct_stream"
    MovieRouteMaxVideoBitrateMbps: float = Field(default=35, gt=0, le=500)
    TVRouteMaxVideoBitrateMbps: float = Field(default=18, gt=0, le=500)
    AllowH264RemuxIfPlexCompatible: bool = True
    H264RemuxMaxBitrateMbps: float = Field(default=35, gt=0, le=500)
    H264RemuxMaxHeight: int = Field(default=1080, ge=1, le=4320)
    SizeGuardMode: Literal["advisory", "strict", "off"] = "advisory"
    MaxEncodeGrowthPercent: float = Field(default=5, ge=0, le=1000)
    CompatibilityEncodeGrowthPercent: float = Field(default=15, ge=0, le=1000)

    MinFreeSpaceGB: int = Field(default=50, ge=0)
    OutsourceMinFreeSpaceGB: int = Field(default=50, ge=0)
    DeferredPublish: bool = False

    VideoCodec: str = Field(default="hevc_nvenc", min_length=1)
    VideoPreset: str = Field(default="p7", min_length=1)
    VideoQuality: int = Field(default=22, ge=0)
    OutputContainer: Literal["mkv", "mp4"] = "mkv"
    EncodeTuningPreset: Literal[
        "balanced_nvenc",
        "quality_nvenc",
        "fast_nvenc",
        "compatibility",
        "custom_legacy_flags",
    ] = "balanced_nvenc"
    EncodeLadder: Literal[
        "auto",
        "tv_balanced",
        "tv_space_saver",
        "movie_balanced",
        "movie_archive",
        "plex_compat",
    ] = "auto"
    ExtraVideoFlags: list[str] = Field(default_factory=list)

    AudioPassthroughProfile: Literal[
        "plex_balanced",
        "compatibility",
        "lossless_passthrough",
        "custom_codec_list",
    ] = "plex_balanced"
    CompatibleAudioCodecs: list[str] = Field(
        default_factory=lambda: _list_default(COMPATIBLE_AUDIO_CODECS_DEFAULT)
    )
    PreferredDefaultAudioLanguages: list[str] = Field(default_factory=lambda: ["english"])
    AudioTranscodeCodec: Literal["eac3", "ac3", "aac"] = "eac3"
    AudioTranscodeBitrate: str = Field(default="640k", pattern=r"^\d+k$")
    AudioTranscodeAutoBitrateByChannels: bool = False
    AudioDownmixMode: Literal["preserve", "max_channels", "stereo"] = "max_channels"
    AudioMaxChannels: int = Field(default=6, ge=1, le=16)
    AllowNoAudio: bool = False

    SubKeepLanguages: list[str] = Field(
        default_factory=lambda: _list_default(SUBTITLE_LANGUAGE_DEFAULT)
    )
    ConvertTx3gToSrt: bool = True
    DropTx3gAfterConversion: bool = False
    CreateExternalTx3gSrtSidecars: bool = False
    Tx3gExtractLanguages: list[str] = Field(
        default_factory=lambda: _list_default(SUBTITLE_EXTRACT_LANGUAGE_DEFAULT)
    )
    Tx3gPreserveExistingSrt: bool = True
    Tx3gTreatForcedAsSeparate: bool = True
    ConvertBdpgsToSrt: bool = False
    DropBdpgsAfterConversion: bool = False
    BdpgsExtractLanguages: list[str] = Field(
        default_factory=lambda: _list_default(SUBTITLE_EXTRACT_LANGUAGE_DEFAULT)
    )
    BdpgsOcrToolPath: str = r"Tools\PgsToSrt\PgsToSrt.exe"
    BdpgsOcrTessdataPath: str = r"Tools\PgsToSrt\tessdata"
    SubSDHTitleKeywords: list[str] = Field(
        default_factory=lambda: _list_default(SUB_SDH_KEYWORD_DEFAULT)
    )
    SubSupplementalKeywords: list[str] = Field(
        default_factory=lambda: _list_default(SUB_SUPPLEMENTAL_KEYWORD_DEFAULT)
    )
    DropAssAfterConversion: bool = False
    StripFormatting: bool = True
    RemoveKaraoke: bool = True
    MergeAdjacent: bool = True
    MergeThresholdMs: int = Field(default=150, ge=0)
    KeepSignsAndSongs: bool = True
    TreatAssSignsSongsAsForced: bool = False
    TreatTx3gSignsSongsAsForced: bool = False
    TreatBdpgsSignsSongsAsForced: bool = False
    ExcludeSubtitleStyles: list[str] = Field(
        default_factory=lambda: _list_default(EXCLUDE_SUBTITLE_STYLES_DEFAULT)
    )
    IncludeSubtitleStyles: list[str] = Field(default_factory=list)

    RemuxSafeVideoCodecs: list[str] = Field(
        default_factory=lambda: ["hevc", "h265", "h.265"]
    )
    ValidExtensions: list[str] = Field(
        default_factory=lambda: [".mkv", ".mp4", ".avi", ".mov", ".m4v", ".ts", ".m2ts"]
    )
    FileStabilityWait: int = Field(default=15, ge=0)
    SkipStabilityCheck: bool = False
    EnableIntegrityCheck: bool = True
    CreateTVSubfolder: bool = True
    AggressiveEpisodeParsing: bool = False
    RobocopyFlags: list[str] = Field(
        default_factory=lambda: ["/J", "/R:3", "/W:15", "/MT:2", "/NP", "/NDL", "/NFL"]
    )

    DebugMode: bool = True
    LogRetentionDays: int = Field(default=7, ge=0)
    PriorityMarkers: list[str] = Field(default_factory=lambda: ["!", "[NOW]"])
    MixPriorityPhase: bool = False
    QueueOrderingStrategy: Literal[
        "Standard",
        "FreshestFirst",
        "ShowComplete",
        "RoundRobin",
        "DeadlineAware",
        "SmallFirst",
        "LargeFirst",
        "ManualOrder",
    ] = "Standard"
    ConsoleLogLevel: Literal["", "ERROR", "WARN", "INFO", "DEBUG"] = ""
    FileLogLevel: Literal["", "ERROR", "WARN", "INFO", "DEBUG"] = ""

    MaxParallelEncodes: int = Field(default=1, ge=1, le=2)
    ParallelEncodeMode: Literal["single", "local_worker_slots"] = "single"
    FallbackCpuQuality: int | None = Field(default=20, ge=0)
    CpuEncodePreset: Literal[
        "ultrafast",
        "superfast",
        "veryfast",
        "faster",
        "fast",
        "medium",
        "slow",
        "slower",
        "veryslow",
        "placebo",
    ] = "medium"
    CpuEncodeProcessPriority: Literal[
        "inherit",
        "idle",
        "belownormal",
        "normal",
        "abovenormal",
        "high",
    ] = "belownormal"
    CpuEncodeMaxThreads: int = Field(default=0, ge=0, le=256)
    OutputSizeMultiplier: float | None = Field(default=0.7, gt=0)

    FFmpegEncodeTimeoutSeconds: int = Field(default=21600, ge=1)
    FFmpegCpuEncodeTimeoutSeconds: int = Field(default=43200, ge=1)
    FFmpegRemuxTimeoutSeconds: int = Field(default=7200, ge=1)
    MkvmergeRemuxTimeoutSeconds: int = Field(default=7200, ge=60, le=86400)
    SubtitleExtractTimeoutSeconds: int = Field(default=180, ge=1)
    SubtitleProbeTimeoutSeconds: int = Field(default=30, ge=1)
    BdpgsOcrTimeoutSeconds: int = Field(default=1800, ge=1)
    OutputValidationProbeTimeoutSeconds: int = Field(default=60, ge=1)
    OutputValidationMinSizeBytes: int = Field(default=1024, ge=0)
    OutputValidationDurationToleranceSeconds: int = Field(default=2, ge=0)
    AllowSystemTools: bool = False
    RobocopyTimeoutSeconds: int = Field(default=14400, ge=1)
    TransientFailureRetryLimit: int = Field(default=3, ge=1)
    IndexScanTimeoutSeconds: int = Field(default=1800, ge=1)
    SourceScanTimeoutSeconds: int = Field(default=1800, ge=1)
    CleanupScanTimeoutSeconds: int = Field(default=300, ge=1)
    CleanupRemoteStaging: bool = False
    CleanupStaleAgeHours: int = Field(default=24, ge=0)
    SourceScanIntervalSeconds: int = Field(default=300, ge=0)
    ProcessedIndexRefreshSeconds: int = Field(default=900, ge=0)
    MinPipelineVersion: str = ""
    ReprocessAll: bool = False
    ShowOverrides: dict[str, Any] = Field(default_factory=dict)

    NetworkRole: Literal["standalone", "coordinator", "worker"] = "standalone"
    CoordinatorPort: int = Field(default=7830, ge=1, le=65535)
    CoordinatorBindAddress: str = "0.0.0.0"
    CoordinatorAlsoEncodeLocally: bool = False
    CoordinatorHeartbeatTimeoutMins: int = Field(default=5, ge=1)
    CoordinatorAuthToken: str = ""
    WorkerCoordinatorUrl: str = ""
    WorkerName: str = ""
    WorkerAuthToken: str = ""
    WorkerPollIntervalSecs: int = Field(default=10, ge=1)
    WorkerSourcePathMap: str = ""
    WorkerConfigOverrides: str = ""

    @field_validator(*LIST_CONFIG_KEYS, mode="before")
    @classmethod
    def _coerce_list(cls, value: Any) -> list[str]:
        if value is None:
            return []
        if isinstance(value, str):
            return [value]
        if isinstance(value, (list, tuple, set)):
            return [str(item) for item in value]
        return [str(value)]

    @field_validator(
        "RoutingProfile",
        "SizeGuardMode",
        "OutputContainer",
        "EncodeTuningPreset",
        "EncodeLadder",
        "AudioPassthroughProfile",
        "AudioTranscodeCodec",
        "AudioDownmixMode",
        "CpuEncodePreset",
        "CpuEncodeProcessPriority",
        "ParallelEncodeMode",
        "NetworkRole",
        mode="before",
    )
    @classmethod
    def _lowercase_choice(cls, value: Any) -> Any:
        if value is None:
            return value
        return str(value).strip().lower()

    @field_validator("ConsoleLogLevel", "FileLogLevel", mode="before")
    @classmethod
    def _normalize_log_level(cls, value: Any) -> str:
        if value is None:
            return ""
        return str(value).strip().upper()

    @field_validator("MinPipelineVersion", mode="before")
    @classmethod
    def _normalize_optional_text(cls, value: Any) -> str:
        if value is None:
            return ""
        return str(value).strip()

    @field_validator("FallbackCpuQuality", "OutputSizeMultiplier", mode="before")
    @classmethod
    def _blank_optional_number(cls, value: Any) -> Any:
        if value is None:
            return None
        if isinstance(value, str) and not value.strip():
            return None
        return value

    @field_validator("QueueOrderingStrategy", mode="before")
    @classmethod
    def _normalize_queue_ordering_strategy(cls, value: Any) -> str:
        if value is None or not str(value).strip():
            return "Standard"
        candidates = (
            "Standard",
            "FreshestFirst",
            "ShowComplete",
            "RoundRobin",
            "DeadlineAware",
            "SmallFirst",
            "LargeFirst",
            "ManualOrder",
        )
        by_casefold = {candidate.casefold(): candidate for candidate in candidates}
        return by_casefold.get(str(value).strip().casefold(), str(value).strip())

    @field_validator("ShowOverrides", mode="before")
    @classmethod
    def _normalize_show_overrides(cls, value: Any) -> dict[str, Any]:
        if value in (None, False, ""):
            return {}
        if isinstance(value, dict):
            return value
        raise TypeError("ShowOverrides must be a mapping.")

    @model_validator(mode="after")
    def _validate_cross_field_policy(self) -> Config:
        if not self.ConvertTx3gToSrt and self.DropTx3gAfterConversion:
            raise ValueError("DropTx3gAfterConversion requires ConvertTx3gToSrt.")
        if not self.ConvertTx3gToSrt and self.CreateExternalTx3gSrtSidecars:
            raise ValueError("CreateExternalTx3gSrtSidecars requires ConvertTx3gToSrt.")
        if not self.ConvertBdpgsToSrt and self.DropBdpgsAfterConversion:
            raise ValueError("DropBdpgsAfterConversion requires ConvertBdpgsToSrt.")
        if self.ConvertBdpgsToSrt and not self.BdpgsOcrToolPath.strip():
            raise ValueError("ConvertBdpgsToSrt requires BdpgsOcrToolPath.")
        return self


def default_config() -> Config:
    """Return a fully defaulted config instance."""

    return Config()


__all__ = [
    "CONFIG_SCHEMA_VERSION",
    "REQUIRED_CONFIG_KEYS",
    "PS_CONFIG_KEY_ORDER",
    "NETWORK_CONFIG_KEYS",
    "CONFIG_KEY_ORDER",
    "DESKTOP_SCHEMA_CONFIG_KEYS",
    "LIST_CONFIG_KEYS",
    "Config",
    "default_config",
]
