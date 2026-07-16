"""Canonical Pydantic contract for MediaPipeline configuration.

The runtime PSD1, the desktop settings schema, and generated JSON Schema
share this flat field shape. Field names intentionally match the PSD1 keys
instead of using snake_case aliases so round-trips do not need a key map.
"""

from __future__ import annotations

from typing import Any, ClassVar, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from mediapipeline.contracts.config_coercion import (
    _coerce_config_bool,
    _mapping_from_json_or_mapping,
    _normalize_config_term_list,
)
from mediapipeline.contracts.config_defaults import (
    _list_default,
    _normalize_legacy_packaged_rename_movie_remove_terms,
    _rename_movie_filter_options_default,
    _rename_movie_remove_terms_default,
    _rename_tv_filter_options_default,
    _rename_tv_remove_terms_default,
)
from mediapipeline.contracts.config_schema_extras import (
    _final_library_promotion_rules_schema_extra,
    _library_profiles_schema_extra,
    _subtitle_cross_field_schema_extra,
)
from mediapipeline.contracts.config_validators import (
    derive_missing_height_tolerance_fields,
    derive_missing_resolution_size_targets,
    reject_boolean_numeric_fields,
    validate_cross_field_config_policy,
)

from mediapipeline.contracts.height_tolerance import (
    DEFAULT_ROUTE_1080P_UPPER_HEIGHT_TOLERANCE_PERCENT,
    DEFAULT_ROUTE_1440P_LOWER_HEIGHT_TOLERANCE_PERCENT,
    DEFAULT_ROUTE_1440P_UPPER_HEIGHT_TOLERANCE_PERCENT,
    DEFAULT_ROUTE_4K_LOWER_HEIGHT_TOLERANCE_PERCENT,
)
from mediapipeline.core.rename.constants import RENAME_MOVIE_FILTER_OPTION_KEYS, RENAME_TV_FILTER_OPTION_KEYS
from mediapipeline.core.rename.movie import rename_movie_filter_default_terms
from mediapipeline.core.rename.tv import rename_tv_filter_default_terms
from mediapipeline.core.validation.strict_json import loads_strict_json


from mediapipeline.contracts.config_fields import *  # noqa: F403

class Config(BaseModel):
    """Flat config model matching PSD1 keys and WebView JSON payloads."""

    model_config: ClassVar[ConfigDict] = ConfigDict(
        extra="allow",
        json_schema_extra={
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "$id": "https://local.mediapipeline/src/mediapipeline/contracts/schemas/config.v1.schema.json",
            "x-config-schema-version": CONFIG_SCHEMA_VERSION,
            "required": list(REQUIRED_CONFIG_KEYS),
            **_subtitle_cross_field_schema_extra(),
        },
    )

    ConfigSchemaVersion: Literal[1] = CONFIG_SCHEMA_VERSION

    @model_validator(mode="before")
    @classmethod
    def _reject_boolean_numeric_fields(cls, value: Any) -> Any:
        return reject_boolean_numeric_fields(value, NUMERIC_CONFIG_KEYS)

    @model_validator(mode="before")
    @classmethod
    def _derive_missing_height_tolerance_fields(cls, value: Any) -> Any:
        return derive_missing_height_tolerance_fields(value)

    @model_validator(mode="before")
    @classmethod
    def _derive_missing_resolution_size_targets(cls, value: Any) -> Any:
        return derive_missing_resolution_size_targets(value)

    SourceMovies: str = Field(default=r"C:\MediaPipeline\Incoming\Movies", min_length=1)
    SourceTV: str = Field(default=r"C:\MediaPipeline\Incoming\TV", min_length=1)
    Outsource: str = Field(default=r"C:\MediaPipeline\Processed", min_length=1)
    LibraryProfiles: list[dict[str, Any]] = Field(
        default_factory=list,
        json_schema_extra=_library_profiles_schema_extra(LIBRARY_PROFILE_OVERRIDE_KEYS_BY_GROUP),
    )
    LocalBase: str = Field(default=r"C:\MediaPipeline\Scratch", min_length=1)

    MovieRoute1080pTargetSizeGB: int = Field(default=8, ge=1)
    MovieRoute1440pTargetSizeGB: int = Field(default=8, ge=1)
    MovieRoute4KTargetSizeGB: int = Field(default=8, ge=1)
    TVRoute1080pTargetSizeGB: int = Field(default=3, ge=1)
    TVRoute1440pTargetSizeGB: int = Field(default=3, ge=1)
    TVRoute4KTargetSizeGB: int = Field(default=3, ge=1)
    RoutingProfile: Literal[
        "plex_direct_stream",
        "plex_direct_play",
        "archive_shrink",
        "archive_quality",
        "manual",
    ] = "plex_direct_stream"
    RouteThresholdMode: Literal[
        "compatibility_advisory",
        "size",
        "bitrate",
        "size_or_bitrate",
    ] = "compatibility_advisory"
    Route1080pUpperHeightTolerancePercent: float = Field(
        default=DEFAULT_ROUTE_1080P_UPPER_HEIGHT_TOLERANCE_PERCENT,
        ge=0,
        le=100,
    )
    Route1080pMaxVideoBitrateMbps: int = Field(default=20, ge=1, le=500)
    Route1440pLowerHeightTolerancePercent: float = Field(
        default=DEFAULT_ROUTE_1440P_LOWER_HEIGHT_TOLERANCE_PERCENT,
        ge=0,
        le=100,
    )
    Route1440pUpperHeightTolerancePercent: float = Field(
        default=DEFAULT_ROUTE_1440P_UPPER_HEIGHT_TOLERANCE_PERCENT,
        ge=0,
        le=100,
    )
    Route1440pMaxVideoBitrateMbps: int = Field(default=35, ge=1, le=500)
    Route4KLowerHeightTolerancePercent: float = Field(
        default=DEFAULT_ROUTE_4K_LOWER_HEIGHT_TOLERANCE_PERCENT,
        ge=0,
        le=100,
    )
    Route4KMaxVideoBitrateMbps: int = Field(default=35, ge=1, le=500)
    AllowH264RemuxIfPlexCompatible: bool = True
    H264RemuxMaxBitrateMbps: int = Field(default=35, ge=1, le=500)
    H264RemuxMaxHeight: int = Field(default=1080, ge=1, le=4320)
    SizeGuardMode: Literal["advisory", "strict", "fallback_remux", "off"] = "advisory"
    MaxEncodeGrowthPercent: int = Field(default=5, ge=0, le=1000)
    CompatibilityEncodeGrowthPercent: int = Field(default=15, ge=0, le=1000)
    EncodeWasteGuardMode: Literal["off", "dry_run", "enforce"] = "off"
    EncodeWasteGuardPreflightEnabled: bool = False
    EncodeWasteGuardMinProgressPercent: int = Field(default=15, ge=0, le=95)
    EncodeWasteGuardMinElapsedSeconds: int = Field(default=120, ge=0, le=86400)
    EncodeWasteGuardOversizeMarginPercent: int = Field(default=20, ge=0, le=1000)
    EncodeWasteGuardConsecutiveSamples: int = Field(default=2, ge=1, le=10)
    EncodeWasteGuardPollSeconds: int = Field(default=10, ge=1, le=600)
    EncodeWasteGuardPreflightSampleSeconds: int = Field(default=30, ge=5, le=600)
    EncodeWasteGuardPreflightSampleCount: int = Field(default=3, ge=1, le=10)
    EncodeWasteGuardPreflightTimeoutSeconds: int = Field(default=900, ge=30, le=86400)

    MinFreeSpaceGB: int = Field(default=50, ge=0)
    OutsourceMinFreeSpaceGB: int = Field(default=50, ge=0)
    DeferredPublish: bool = False
    PendingPublishDrainMode: Literal["manual", "trusted"] = "manual"
    PendingPublishDrainBatchSize: int = Field(default=100, ge=1, le=1000000)
    FinalLibraryPromotionEnabled: bool = False
    FinalLibraryPromotionRules: list[dict[str, Any]] = Field(
        default_factory=list,
        json_schema_extra=_final_library_promotion_rules_schema_extra(),
    )
    FinalLibraryPromotionVerificationMode: Literal["fast", "cautious"] = "cautious"
    FinalLibraryPromotionCleanupAfterVerified: bool = False
    FinalLibraryPromotionOverwriteExisting: bool = False

    VideoCodec: Literal[
        "hevc_nvenc",
        "hevc_qsv",
        "hevc_amf",
        "libx265",
        "h264_nvenc",
        "h264_qsv",
        "h264_amf",
        "libx264",
        "av1_nvenc",
        "av1_qsv",
        "av1_amf",
        "libaom-av1",
    ] = "hevc_nvenc"
    EncoderBackend: Literal["auto", "nvenc", "qsv", "amf", "cpu"] = "auto"
    VideoPreset: Literal["p1", "p2", "p3", "p4", "p5", "p6", "p7"] = "p7"
    VideoQuality: int = Field(default=22, ge=1, le=51)
    OutputContainer: Literal["mkv", "mp4"] = "mkv"
    DynamicHdrPolicy: Literal["off", "warn", "preserve_or_remux", "preserve_or_review"] = "preserve_or_review"
    DoviToolPath: str = ""
    Hdr10PlusToolPath: str = ""
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
    AudioTranscodeBitrate: str = Field(default="640k", pattern=r"^[1-9]\d*k$")
    AudioTranscodeAutoBitrateByChannels: bool = False
    AudioDownmixMode: Literal["preserve", "max_channels", "stereo"] = "max_channels"
    AudioMaxChannels: int = Field(default=6, ge=1, le=16)
    AllowNoAudio: bool = False

    SubKeepLanguages: list[str] = Field(
        default_factory=lambda: _list_default(SUBTITLE_LANGUAGE_DEFAULT)
    )
    AllowSubtitleHelperFallback: bool = False
    ConvertTx3gToSrt: bool = True
    DropTx3gAfterConversion: bool = False
    CreateExternalTx3gSrtSidecars: bool = False
    Tx3gExtractLanguages: list[str] = Field(
        default_factory=lambda: _list_default(SUBTITLE_EXTRACT_LANGUAGE_DEFAULT)
    )
    Tx3gPreserveExistingSrt: bool = True
    Tx3gTreatForcedAsSeparate: bool = True
    ConvertBdpgsToSrt: bool = True
    DropBdpgsAfterConversion: bool = False
    BdpgsExtractLanguages: list[str] = Field(
        default_factory=lambda: _list_default(SUBTITLE_EXTRACT_LANGUAGE_DEFAULT)
    )
    BdpgsOcrToolPath: str = r"tools\PgsToSrt\PgsToSrt.exe"
    BdpgsOcrTessdataPath: str = r"tools\PgsToSrt\tessdata"
    ConvertVobSubToSrt: bool = False
    DropVobSubAfterConversion: bool = False
    VobSubExtractLanguages: list[str] = Field(
        default_factory=lambda: _list_default(SUBTITLE_EXTRACT_LANGUAGE_DEFAULT)
    )
    VobSubOcrToolPath: str = r"tools\SubtitleEditLegacy\SubtitleEdit.exe"
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
    MergeThresholdMs: int = Field(default=150, ge=0, le=5000)
    KeepSignsAndSongs: bool = True
    TreatAssSignsSongsAsForced: bool = False
    TreatTx3gSignsSongsAsForced: bool = False
    TreatBdpgsSignsSongsAsForced: bool = False
    TreatVobSubSignsSongsAsForced: bool = False
    ExcludeSubtitleStyles: list[str] = Field(
        default_factory=lambda: _list_default(EXCLUDE_SUBTITLE_STYLES_DEFAULT)
    )
    IncludeSubtitleStyles: list[str] = Field(default_factory=list)

    RemuxSafeVideoCodecs: list[str] = Field(
        default_factory=lambda: ["hevc", "h265", "h.265"]
    )
    RenameMovieFilterOptions: dict[str, bool] = Field(default_factory=_rename_movie_filter_options_default)
    RenameMovieFilterTerms: dict[str, list[str]] = Field(default_factory=rename_movie_filter_default_terms)
    RenameMovieRemoveTerms: list[str] = Field(default_factory=_rename_movie_remove_terms_default)
    RenameTVFilterOptions: dict[str, bool] = Field(default_factory=_rename_tv_filter_options_default)
    RenameTVFilterTerms: dict[str, list[str]] = Field(default_factory=rename_tv_filter_default_terms)
    RenameTVRemoveTerms: list[str] = Field(default_factory=_rename_tv_remove_terms_default)
    ValidExtensions: list[str] = Field(
        default_factory=lambda: [".mkv", ".mp4", ".avi", ".mov", ".m4v", ".ts", ".m2ts"]
    )
    FileStabilityWait: int = Field(default=15, ge=0)
    EnableWatchFolders: bool = False
    WatchFolderRoots: list[str] = Field(default_factory=list)
    WatchDebounceSeconds: int = Field(default=30, ge=5)
    WatchScanTimeoutSeconds: int = Field(default=300, ge=1, le=86400)
    WatchAction: Literal["enqueue_only", "enqueue_and_launch"] = "enqueue_only"
    WatchRespectScheduleWindow: bool = True
    SkipStabilityCheck: bool = False
    EnableIntegrityCheck: bool = True
    CreateTVSubfolder: bool = True
    AggressiveEpisodeParsing: bool = False
    RobocopyFlags: list[str] = Field(
        default_factory=lambda: ["/J", "/R:3", "/W:15", "/MT:2", "/NP", "/NDL", "/NFL"]
    )

    DebugMode: bool = True
    LogRetentionDays: int = Field(default=7, ge=0)
    InterruptedToolLogRetentionDays: int = Field(default=3, ge=1, le=365)
    PipelineDebugLogMaxBytes: int = Field(default=104857600, ge=1048576, le=2147483647)
    FailureArtifactWarningThresholdGB: int = Field(default=100, ge=0)
    FailureArtifactRetentionDays: int = Field(default=0, ge=0)
    FailureArtifactCleanupTargetGB: int = Field(default=0, ge=0)
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
    FallbackCpuQuality: int | None = Field(default=20, ge=1, le=51)
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
    OutputSizeMultiplier: float | None = Field(default=0.7, ge=0.1, le=2.0)

    FFmpegEncodeTimeoutSeconds: int = Field(default=21600, ge=1)
    FFmpegCpuEncodeTimeoutSeconds: int = Field(default=43200, ge=1)
    CpuEncodeMutexWaitSeconds: int = Field(default=1800, ge=0, le=86400)
    FFmpegRemuxTimeoutSeconds: int = Field(default=7200, ge=1)
    MkvmergeRemuxTimeoutSeconds: int = Field(default=7200, ge=60, le=86400)
    SubtitleExtractTimeoutSeconds: int = Field(default=180, ge=30, le=3600)
    SubtitleProbeTimeoutSeconds: int = Field(default=30, ge=5, le=600)
    BdpgsOcrTimeoutSeconds: int = Field(default=1800, ge=60, le=14400)
    VobSubOcrTimeoutSeconds: int = Field(default=1800, ge=60, le=14400)
    OutputValidationProbeTimeoutSeconds: int = Field(default=60, ge=1)
    OutputValidationMinSizeBytes: int = Field(default=1024, ge=0)
    OutputValidationDurationToleranceSeconds: int = Field(default=2, ge=0)
    EnableQualityVerification: bool = False
    QualityMetric: Literal["vmaf", "ssim", "psnr"] = "vmaf"
    QualitySampleMode: Literal["sampled", "full"] = "sampled"
    QualitySampleSeconds: int = Field(default=10, ge=2, le=60)
    QualitySampleCount: int = Field(default=3, ge=1, le=10)
    QualityWarnThreshold: float = Field(default=90, ge=0)
    QualityFailThreshold: float = Field(default=75, ge=0)
    QualityFailAction: Literal["warn_only", "block_review"] = "warn_only"
    QualityVerifyTimeoutSeconds: int = Field(default=1800, ge=60, le=21600)
    AllowSystemTools: bool = False
    RobocopyTimeoutSeconds: int = Field(default=14400, ge=60, le=172800)
    TransientFailureRetryLimit: int = Field(default=3, ge=1, le=100)
    ConsecutiveRoundFailureBlockLimit: int = Field(default=12, ge=1, le=1000)
    ConsecutiveRoundFailureProbeBackoffSeconds: int = Field(default=900, ge=30, le=86400)
    PendingPublishBacklogBlockThreshold: int = Field(default=100, ge=1, le=1000000)
    PendingPublishDeferredBlockThreshold: int = Field(default=25, ge=1, le=1000000)
    AutonomyPendingTotalReviewBytes: int = Field(default=100 * 1024**3, ge=1024**2, le=10 * 1024**4)
    AutonomyPendingTotalBlockBytes: int = Field(default=250 * 1024**3, ge=1024**2, le=10 * 1024**4)
    PauseFlagReviewSeconds: int = Field(default=1800, ge=60, le=86400)
    PauseFlagBlockSeconds: int = Field(default=21600, ge=300, le=604800)
    LocalWorkerHeartbeatGraceSeconds: int = Field(default=900, ge=60, le=86400)
    QueueExecutionMaxRunnablePerRound: int = Field(default=500, ge=1, le=1000000)
    StateDbMaintenanceIntervalSeconds: int = Field(default=21600, ge=60, le=604800)
    StateDbWalReviewBytes: int = Field(default=33554432, ge=1048576, le=2147483647)
    StateDbCompletedJobsMaxRows: int = Field(default=250000, ge=1000, le=10000000)
    IndexScanTimeoutSeconds: int = Field(default=1800, ge=30, le=86400)
    SourceScanTimeoutSeconds: int = Field(default=1800, ge=30, le=86400)
    CleanupScanTimeoutSeconds: int = Field(default=300, ge=30, le=7200)
    CleanupRemoteStaging: bool = False
    CleanupStaleAgeHours: int = Field(default=24, ge=1, le=720)
    SourceScanIntervalSeconds: int = Field(default=300, ge=0)
    ProcessedIndexRefreshSeconds: int = Field(default=900, ge=0)
    MinPipelineVersion: str = ""
    ReprocessAll: bool = False
    ShowOverrides: dict[str, Any] = Field(default_factory=dict)
    PlannerRolloutStage: Literal[
        "legacy",
        "shadow",
        "selected_jobs",
        "ui_old_backend",
        "new_planner_default",
        "deprecation_cleanup",
    ] = "legacy"
    UsePythonPlanner: bool = False
    EnableHandBrakeSettingsUi: bool = False
    PlannerComparisonLogging: bool = False
    NewPlannerCutoverApproved: bool = False

    NetworkRole: Literal["standalone", "coordinator", "worker"] = "standalone"
    CoordinatorPort: int = Field(default=7830, ge=1, le=65535)
    CoordinatorBindAddress: str = "0.0.0.0"
    CoordinatorAlsoEncodeLocally: bool = False
    CoordinatorHeartbeatTimeoutMins: int = Field(default=5, ge=1)
    CoordinatorMaxJobRetries: int = Field(default=3, ge=1, le=100)
    CoordinatorAuthToken: str = ""
    NetworkRerunHandoffRoot: str = ""
    WorkerCoordinatorUrl: str = ""
    WorkerName: str = ""
    WorkerAuthToken: str = ""
    WorkerPollIntervalSecs: int = Field(default=10, ge=1)
    WorkerSourcePathMap: str = ""
    WorkerEncoderMap: str = ""
    WorkerHonorCoordinatorPolicy: bool = False
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

    @field_validator("RenameMovieFilterOptions", mode="before")
    @classmethod
    def _normalize_rename_movie_filter_options(cls, value: Any) -> dict[str, bool]:
        raw_options = _mapping_from_json_or_mapping(value, label="RenameMovieFilterOptions")
        options = _rename_movie_filter_options_default()
        for key in RENAME_MOVIE_FILTER_OPTION_KEYS:
            if key in raw_options:
                options[key] = _coerce_config_bool(raw_options[key], default=True)
        return options

    @field_validator("RenameMovieFilterTerms", mode="before")
    @classmethod
    def _normalize_rename_movie_filter_terms(cls, value: Any) -> dict[str, list[str]]:
        raw_terms = _mapping_from_json_or_mapping(value, label="RenameMovieFilterTerms")
        terms = rename_movie_filter_default_terms()
        for key in RENAME_MOVIE_FILTER_OPTION_KEYS:
            if key in raw_terms:
                terms[key] = _normalize_config_term_list(raw_terms[key])
        return terms

    @field_validator("RenameMovieRemoveTerms")
    @classmethod
    def _normalize_rename_movie_remove_terms(cls, value: list[str]) -> list[str]:
        normalized = _normalize_config_term_list(value)
        return _normalize_legacy_packaged_rename_movie_remove_terms(normalized)

    @field_validator("RenameTVFilterOptions", mode="before")
    @classmethod
    def _normalize_rename_tv_filter_options(cls, value: Any) -> dict[str, bool]:
        raw_options = _mapping_from_json_or_mapping(value, label="RenameTVFilterOptions")
        options = _rename_tv_filter_options_default()
        for key in RENAME_TV_FILTER_OPTION_KEYS:
            if key in raw_options:
                options[key] = _coerce_config_bool(raw_options[key], default=True)
        return options

    @field_validator("RenameTVFilterTerms", mode="before")
    @classmethod
    def _normalize_rename_tv_filter_terms(cls, value: Any) -> dict[str, list[str]]:
        raw_terms = _mapping_from_json_or_mapping(value, label="RenameTVFilterTerms")
        terms = rename_tv_filter_default_terms()
        for key in RENAME_TV_FILTER_OPTION_KEYS:
            if key in raw_terms:
                terms[key] = _normalize_config_term_list(raw_terms[key])
        return terms

    @field_validator("RenameTVRemoveTerms")
    @classmethod
    def _normalize_rename_tv_remove_terms(cls, value: list[str]) -> list[str]:
        return _normalize_config_term_list(value)

    @field_validator("FinalLibraryPromotionRules", mode="before")
    @classmethod
    def _coerce_final_library_promotion_rules(cls, value: Any) -> list[dict[str, Any]]:
        if value in (None, "", False):
            return []
        if isinstance(value, str):
            raw = value.strip()
            if not raw:
                return []
            try:
                value = loads_strict_json(raw)
            except ValueError as exc:
                raise ValueError(f"FinalLibraryPromotionRules must be JSON object/array data: {exc}") from exc
        if isinstance(value, dict):
            value = [value]
        if not isinstance(value, (list, tuple)):
            raise TypeError("FinalLibraryPromotionRules must be a list of rule objects.")
        rules: list[dict[str, Any]] = []
        for item in value:
            if not isinstance(item, dict):
                raise TypeError("FinalLibraryPromotionRules entries must be objects.")
            rules.append(dict(item))
        return rules

    @field_validator("LibraryProfiles", mode="before")
    @classmethod
    def _coerce_library_profiles(cls, value: Any) -> list[dict[str, Any]]:
        if value in (None, "", False):
            return []
        if isinstance(value, str):
            raw = value.strip()
            if not raw:
                return []
            try:
                value = loads_strict_json(raw)
            except ValueError as exc:
                raise ValueError(f"LibraryProfiles must be JSON object/array data: {exc}") from exc
        if isinstance(value, dict):
            value = [value]
        if not isinstance(value, (list, tuple)):
            raise TypeError("LibraryProfiles must be a list of profile objects.")
        profiles: list[dict[str, Any]] = []
        for item in value:
            if not isinstance(item, dict):
                raise TypeError("LibraryProfiles entries must be objects.")
            profiles.append({str(key): item_value for key, item_value in item.items()})
        return profiles

    @field_validator(
        "RoutingProfile",
        "RouteThresholdMode",
        "SizeGuardMode",
        "EncodeWasteGuardMode",
        "QualityMetric",
        "QualitySampleMode",
        "QualityFailAction",
        "VideoCodec",
        "EncoderBackend",
        "VideoPreset",
        "OutputContainer",
        "DynamicHdrPolicy",
        "EncodeTuningPreset",
        "EncodeLadder",
        "FinalLibraryPromotionVerificationMode",
        "PendingPublishDrainMode",
        "AudioPassthroughProfile",
        "AudioTranscodeCodec",
        "AudioDownmixMode",
        "CpuEncodePreset",
        "CpuEncodeProcessPriority",
        "ParallelEncodeMode",
        "NetworkRole",
        "WatchAction",
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
        validate_cross_field_config_policy(self)
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
    "NUMERIC_CONFIG_KEYS",
    "LIBRARY_PROFILE_OVERRIDE_KEYS_BY_GROUP",
    "LIBRARY_PROFILE_TOP_LEVEL_KEYS",
    "FINAL_LIBRARY_PROMOTION_RULE_KEYS",
    "Config",
    "default_config",
]
