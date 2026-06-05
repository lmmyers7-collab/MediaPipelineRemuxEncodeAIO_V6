"""Versioned preset/policy schema."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any, ClassVar, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator

from mediapipeline.contracts.height_tolerance import (
    DEFAULT_ROUTE_1080P_UPPER_HEIGHT_TOLERANCE_PERCENT,
    DEFAULT_ROUTE_1440P_LOWER_HEIGHT_TOLERANCE_PERCENT,
    DEFAULT_ROUTE_1440P_UPPER_HEIGHT_TOLERANCE_PERCENT,
    DEFAULT_ROUTE_4K_LOWER_HEIGHT_TOLERANCE_PERCENT,
    height_tolerance_boundaries,
    legacy_height_tolerance_defaults,
    validate_height_tolerance_boundaries,
)
from mediapipeline.contracts.verification import OutputSizeCheckAction, output_size_check_action_from_settings
from mediapipeline.core.config.preset_encoding_sections import (
    AudioPolicy,
    ContainerPolicy,
    DimensionsPolicy,
    FiltersPolicy,
    SubtitlePolicy,
    VideoPolicy,
)

PRESET_POLICY_SCHEMA_VERSION: Literal[2] = 2
PRESET_POLICY_WRITE_FORMAT: Literal["legacy"] = "legacy"

RoutingProfile = Literal["plex_direct_stream", "plex_direct_play", "archive_shrink", "archive_quality", "manual"]
RouteThresholdMode = Literal["compatibility_advisory", "size", "bitrate", "size_or_bitrate"]
SizeGuardMode = Literal["advisory", "strict", "off"]

_SOURCE_FACT_KEYS = frozenset(
    {
        "source",
        "sourceFacts",
        "sourceMedia",
        "sourceMediaInfo",
        "source_facts",
        "source_media",
        "source_media_info",
    }
)


def _normalized_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _normalized_lower(value: Any) -> str:
    return _normalized_text(value).lower()


def _normalized_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        text = _normalized_text(value)
        return [text] if text else []
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [text for item in value if (text := _normalized_text(item))]
    text = _normalized_text(value)
    return [text] if text else []


class PresetPolicyModel(BaseModel):
    """Base model for the versioned preset schema.

    Unknown fields are allowed so a newer preset can be read and round-tripped
    by current tooling without destroying future data.
    """

    model_config: ClassVar[ConfigDict] = ConfigDict(extra="allow", populate_by_name=True)


class DirectCopyMaxBitratePolicy(PresetPolicyModel):
    movie_mbps: float = Field(default=35.0, ge=0, alias="movieMbps")
    tv_mbps: float = Field(default=18.0, ge=0, alias="tvMbps")


class ResolutionAwareBitratePolicy(PresetPolicyModel):
    bucket_1080p_max_height: int = Field(default=1200, ge=1, le=4320, alias="bucket1080pMaxHeight")
    bucket_1080p_upper_height_tolerance_pct: float = Field(
        default=DEFAULT_ROUTE_1080P_UPPER_HEIGHT_TOLERANCE_PERCENT,
        ge=0,
        le=100,
        alias="bucket1080pUpperHeightTolerancePct",
    )
    bucket_1080p_max_bitrate_mbps: float = Field(default=20.0, gt=0, le=500, alias="bucket1080pMaxBitrateMbps")
    bucket_1440p_lower_height_tolerance_pct: float = Field(
        default=DEFAULT_ROUTE_1440P_LOWER_HEIGHT_TOLERANCE_PERCENT,
        ge=0,
        le=100,
        alias="bucket1440pLowerHeightTolerancePct",
    )
    bucket_1440p_upper_height_tolerance_pct: float = Field(
        default=DEFAULT_ROUTE_1440P_UPPER_HEIGHT_TOLERANCE_PERCENT,
        ge=0,
        le=100,
        alias="bucket1440pUpperHeightTolerancePct",
    )
    bucket_1440p_max_bitrate_mbps: float = Field(default=35.0, gt=0, le=500, alias="bucket1440pMaxBitrateMbps")
    bucket_4k_lower_height_tolerance_pct: float = Field(
        default=DEFAULT_ROUTE_4K_LOWER_HEIGHT_TOLERANCE_PERCENT,
        ge=0,
        le=100,
        alias="bucket4kLowerHeightTolerancePct",
    )
    bucket_4k_min_height: int = Field(default=1800, ge=1, le=4320, alias="bucket4kMinHeight")
    bucket_4k_max_bitrate_mbps: float = Field(default=35.0, gt=0, le=500, alias="bucket4kMaxBitrateMbps")

    @model_validator(mode="before")
    @classmethod
    def _derive_percent_tolerances_from_legacy_heights(cls, value: Any) -> Any:
        if not isinstance(value, Mapping):
            return value
        next_value = dict(value)
        legacy_1080p_height = next_value.get(
            "bucket1080pMaxHeight",
            next_value.get("bucket_1080p_max_height", 1200),
        )
        legacy_4k_height = next_value.get(
            "bucket4kMinHeight",
            next_value.get("bucket_4k_min_height", 1800),
        )
        derived = legacy_height_tolerance_defaults(
            route_1080p_bucket_max_height=int(legacy_1080p_height),
            route_4k_bucket_min_height=int(legacy_4k_height),
        )
        alias_pairs = {
            "bucket1080pUpperHeightTolerancePct": (
                "bucket_1080p_upper_height_tolerance_pct",
                "Route1080pUpperHeightTolerancePercent",
            ),
            "bucket1440pLowerHeightTolerancePct": (
                "bucket_1440p_lower_height_tolerance_pct",
                "Route1440pLowerHeightTolerancePercent",
            ),
            "bucket1440pUpperHeightTolerancePct": (
                "bucket_1440p_upper_height_tolerance_pct",
                "Route1440pUpperHeightTolerancePercent",
            ),
            "bucket4kLowerHeightTolerancePct": (
                "bucket_4k_lower_height_tolerance_pct",
                "Route4KLowerHeightTolerancePercent",
            ),
        }
        for alias, (field_name, config_key) in alias_pairs.items():
            if alias not in next_value and field_name not in next_value:
                next_value[alias] = derived[config_key]
        return next_value

    @model_validator(mode="after")
    def _validate_bucket_order(self) -> "ResolutionAwareBitratePolicy":
        height_tolerances = {
            "Route1080pUpperHeightTolerancePercent": self.bucket_1080p_upper_height_tolerance_pct,
            "Route1440pLowerHeightTolerancePercent": self.bucket_1440p_lower_height_tolerance_pct,
            "Route1440pUpperHeightTolerancePercent": self.bucket_1440p_upper_height_tolerance_pct,
            "Route4KLowerHeightTolerancePercent": self.bucket_4k_lower_height_tolerance_pct,
        }
        height_errors = validate_height_tolerance_boundaries(height_tolerances)
        if height_errors:
            raise ValueError("; ".join(height_errors))
        boundaries = height_tolerance_boundaries(height_tolerances)
        self.bucket_1080p_max_height = boundaries.route_1080p_max_height
        self.bucket_4k_min_height = boundaries.route_4k_min_height
        return self


class RoutingPolicy(PresetPolicyModel):
    enforcement_mode: RouteThresholdMode = Field(default="compatibility_advisory", alias="enforcementMode")
    direct_copy_max_bitrate: DirectCopyMaxBitratePolicy = Field(
        default_factory=DirectCopyMaxBitratePolicy,
        alias="directCopyMaxBitrate",
    )
    resolution_aware_bitrate: ResolutionAwareBitratePolicy = Field(
        default_factory=ResolutionAwareBitratePolicy,
        alias="resolutionAwareBitrate",
    )
    allow_h264_compatible_direct_copy: bool = Field(default=True, alias="allowH264CompatibleDirectCopy")
    h264_direct_copy_max_bitrate_mbps: float = Field(default=35.0, ge=0, alias="h264DirectCopyMaxBitrateMbps")
    h264_direct_copy_max_height: int = Field(default=1080, ge=0, alias="h264DirectCopyMaxHeight")
    direct_copy_video_codec_allowlist: list[str] = Field(
        default_factory=lambda: ["hevc", "h265", "h.265"],
        alias="directCopyVideoCodecAllowlist",
    )

    @field_validator("enforcement_mode", mode="before")
    @classmethod
    def _normalize_enforcement_mode(cls, value: Any) -> str:
        return _normalized_lower(value)

    @field_validator("direct_copy_video_codec_allowlist", mode="before")
    @classmethod
    def _coerce_codec_list(cls, value: Any) -> list[str]:
        return [item.lower() for item in _normalized_list(value)]


class SizeGuardsPolicy(PresetPolicyModel):
    mode: SizeGuardMode = "advisory"
    on_exceeded: OutputSizeCheckAction = Field(default="warn_only", alias="onExceeded")
    compatibility_encode_growth_tolerance_pct: float = Field(
        default=15.0,
        ge=0,
        le=1000,
        alias="compatibilityEncodeGrowthTolerancePct",
    )
    quality_encode_growth_tolerance_pct: float = Field(
        default=5.0,
        ge=0,
        le=1000,
        alias="qualityEncodeGrowthTolerancePct",
    )
    movie_route_size_limit_gb: float = Field(default=8.0, ge=0, alias="movieRouteSizeLimitGb")
    tv_route_size_limit_gb: float = Field(default=3.0, ge=0, alias="tvRouteSizeLimitGb")
    movie_route_1080p_size_limit_gb: float = Field(default=8.0, ge=0, alias="movieRoute1080pSizeLimitGb")
    movie_route_1440p_size_limit_gb: float = Field(default=8.0, ge=0, alias="movieRoute1440pSizeLimitGb")
    movie_route_4k_size_limit_gb: float = Field(default=8.0, ge=0, alias="movieRoute4kSizeLimitGb")
    tv_route_1080p_size_limit_gb: float = Field(default=3.0, ge=0, alias="tvRoute1080pSizeLimitGb")
    tv_route_1440p_size_limit_gb: float = Field(default=3.0, ge=0, alias="tvRoute1440pSizeLimitGb")
    tv_route_4k_size_limit_gb: float = Field(default=3.0, ge=0, alias="tvRoute4kSizeLimitGb")
    route_output_size_multiplier: float | None = Field(default=0.7, gt=0, alias="routeOutputSizeMultiplier")

    @model_validator(mode="before")
    @classmethod
    def _derive_resolution_size_limits(cls, value: Any) -> Any:
        if not isinstance(value, Mapping):
            return value
        next_value = dict(value)
        movie_size = next_value.get("movie_route_size_limit_gb", next_value.get("movieRouteSizeLimitGb", 8.0))
        tv_size = next_value.get("tv_route_size_limit_gb", next_value.get("tvRouteSizeLimitGb", 3.0))
        for field, alias in (
            ("movie_route_1080p_size_limit_gb", "movieRoute1080pSizeLimitGb"),
            ("movie_route_1440p_size_limit_gb", "movieRoute1440pSizeLimitGb"),
            ("movie_route_4k_size_limit_gb", "movieRoute4kSizeLimitGb"),
        ):
            if field not in next_value and alias not in next_value:
                next_value[field] = movie_size
        for field, alias in (
            ("tv_route_1080p_size_limit_gb", "tvRoute1080pSizeLimitGb"),
            ("tv_route_1440p_size_limit_gb", "tvRoute1440pSizeLimitGb"),
            ("tv_route_4k_size_limit_gb", "tvRoute4kSizeLimitGb"),
        ):
            if field not in next_value and alias not in next_value:
                next_value[field] = tv_size
        return next_value

    @field_validator("mode", mode="before")
    @classmethod
    def _normalize_size_choice(cls, value: Any) -> str:
        return _normalized_lower(value)

    @field_validator("on_exceeded", mode="before")
    @classmethod
    def _normalize_size_action(cls, value: Any) -> OutputSizeCheckAction:
        return output_size_check_action_from_settings(None, _normalized_lower(value))


class GuardsPolicy(PresetPolicyModel):
    size: SizeGuardsPolicy = Field(default_factory=SizeGuardsPolicy)


class VerificationPolicy(PresetPolicyModel):
    output_probe_timeout_seconds: int = Field(default=60, ge=1, alias="outputProbeTimeoutSeconds")
    output_min_size_bytes: int = Field(default=1024, ge=0, alias="outputMinSizeBytes")
    output_duration_tolerance_seconds: int = Field(default=2, ge=0, alias="outputDurationToleranceSeconds")
    source_integrity_preflight_enabled: bool = Field(default=True, alias="sourceIntegrityPreflightEnabled")
    source_stability_wait_seconds: int = Field(default=15, ge=0, alias="sourceStabilityWaitSeconds")
    skip_source_stability_check: bool = Field(default=False, alias="skipSourceStabilityCheck")
    source_media_extensions: list[str] = Field(
        default_factory=lambda: [".mkv", ".mp4", ".avi", ".mov", ".m4v", ".ts", ".m2ts"],
        alias="sourceMediaExtensions",
    )

    @field_validator("source_media_extensions", mode="before")
    @classmethod
    def _coerce_extensions(cls, value: Any) -> list[str]:
        return _normalized_list(value)


class PublishPolicy(PresetPolicyModel):
    deferred_publish: bool = Field(default=False, alias="deferredPublish")
    output_free_space_reserve_gb: int = Field(default=50, ge=0, alias="outputFreeSpaceReserveGb")
    final_library_promotion_enabled: bool = Field(default=False, alias="finalLibraryPromotionEnabled")
    final_library_promotion_rules: list[dict[str, Any]] = Field(default_factory=list, alias="finalLibraryPromotionRules")
    final_library_promotion_verification_mode: Literal["fast", "cautious"] = Field(
        default="cautious",
        alias="finalLibraryPromotionVerificationMode",
    )
    final_library_promotion_cleanup_after_verified: bool = Field(
        default=False,
        alias="finalLibraryPromotionCleanupAfterVerified",
    )
    final_library_promotion_overwrite_existing: bool = Field(default=False, alias="finalLibraryPromotionOverwriteExisting")

    @field_validator("final_library_promotion_verification_mode", mode="before")
    @classmethod
    def _normalize_verification_mode(cls, value: Any) -> str:
        return _normalized_lower(value)


class AdvancedPolicy(PresetPolicyModel):
    extra_video_flags: list[str] = Field(default_factory=list, alias="extraVideoFlags")
    fallback_cpu_quality: int | None = Field(default=20, ge=0, alias="fallbackCpuQuality")
    cpu_encode_preset: str = Field(default="medium", alias="cpuEncodePreset")
    cpu_encode_process_priority: str = Field(default="belownormal", alias="cpuEncodeProcessPriority")
    cpu_encode_max_threads: int = Field(default=0, ge=0, le=256, alias="cpuEncodeMaxThreads")
    ffmpeg_encode_timeout_seconds: int = Field(default=21600, ge=1, alias="ffmpegEncodeTimeoutSeconds")
    ffmpeg_cpu_encode_timeout_seconds: int = Field(default=43200, ge=1, alias="ffmpegCpuEncodeTimeoutSeconds")
    ffmpeg_remux_timeout_seconds: int = Field(default=7200, ge=1, alias="ffmpegRemuxTimeoutSeconds")
    mkvmerge_remux_timeout_seconds: int = Field(default=7200, ge=60, le=86400, alias="mkvmergeRemuxTimeoutSeconds")
    subtitle_extract_timeout_seconds: int = Field(default=180, ge=1, alias="subtitleExtractTimeoutSeconds")
    subtitle_probe_timeout_seconds: int = Field(default=30, ge=1, alias="subtitleProbeTimeoutSeconds")
    bdpgs_ocr_timeout_seconds: int = Field(default=1800, ge=1, alias="bdpgsOcrTimeoutSeconds")
    vobsub_ocr_timeout_seconds: int = Field(default=1800, ge=60, le=14400, alias="vobSubOcrTimeoutSeconds")
    copy_transfer_flags: list[str] = Field(default_factory=list, alias="copyTransferFlags")
    copy_transfer_timeout_seconds: int = Field(default=14400, ge=1, alias="copyTransferTimeoutSeconds")
    transient_failure_retry_limit: int = Field(default=3, ge=1, alias="transientFailureRetryLimit")
    scratch_free_space_reserve_gb: int = Field(default=50, ge=0, alias="scratchFreeSpaceReserveGb")
    cleanup_remote_staging_enabled: bool = Field(default=False, alias="cleanupRemoteStagingEnabled")
    cleanup_stale_age_hours: int = Field(default=24, ge=0, alias="cleanupStaleAgeHours")
    legacy_passthrough: dict[str, Any] = Field(default_factory=dict, alias="legacyPassthrough")

    @field_validator("extra_video_flags", "copy_transfer_flags", mode="before")
    @classmethod
    def _coerce_advanced_list(cls, value: Any) -> list[str]:
        return _normalized_list(value)

    @field_validator("fallback_cpu_quality", mode="before")
    @classmethod
    def _blank_optional_quality(cls, value: Any) -> Any:
        if value is None:
            return None
        if isinstance(value, str) and not value.strip():
            return None
        return value


class PresetV2(PresetPolicyModel):
    version: Literal[2] = PRESET_POLICY_SCHEMA_VERSION
    name: str = Field(default="Migrated legacy policy", min_length=1)
    impact_level: Literal["safe", "moderate", "high", "custom"] = Field(default="custom", alias="impactLevel")
    preset_category: Literal["plex", "archive", "compatibility", "custom"] = Field(default="custom", alias="presetCategory")
    processing_strategy: RoutingProfile = Field(default="plex_direct_stream", alias="processingStrategy")
    compatibility_target: Literal["plex", "direct_play", "archive", "custom"] = Field(default="plex", alias="compatibilityTarget")
    routing: RoutingPolicy = Field(default_factory=RoutingPolicy)
    dimensions: DimensionsPolicy = Field(default_factory=DimensionsPolicy)
    filters: FiltersPolicy = Field(default_factory=FiltersPolicy)
    video: VideoPolicy = Field(default_factory=VideoPolicy)
    audio: AudioPolicy = Field(default_factory=AudioPolicy)
    subtitles: SubtitlePolicy = Field(default_factory=SubtitlePolicy)
    container: ContainerPolicy = Field(default_factory=ContainerPolicy)
    guards: GuardsPolicy = Field(default_factory=GuardsPolicy)
    verification: VerificationPolicy = Field(default_factory=VerificationPolicy)
    publish: PublishPolicy = Field(default_factory=PublishPolicy)
    advanced: AdvancedPolicy = Field(default_factory=AdvancedPolicy)

    @model_validator(mode="before")
    @classmethod
    def _reject_source_facts(cls, value: Any) -> Any:
        if isinstance(value, Mapping):
            present = sorted(str(key) for key in value if str(key) in _SOURCE_FACT_KEYS)
            if present:
                joined = ", ".join(present)
                raise ValueError(f"Preset: source facts are read-only and must not be stored in PresetV2 ({joined}).")
        return value

    @field_validator("impact_level", "preset_category", "processing_strategy", "compatibility_target", mode="before")
    @classmethod
    def _normalize_top_level_choice(cls, value: Any) -> str:
        return _normalized_lower(value)


class PresetValidationIssue(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid")

    section: str
    path: str
    message: str


_SECTION_LABELS: Mapping[str, str] = {
    "routing": "Routing",
    "dimensions": "Dimensions",
    "filters": "Filters",
    "video": "Video",
    "audio": "Audio",
    "subtitles": "Subtitles",
    "container": "Container",
    "guards": "Output Size Check",
    "verification": "Verification",
    "publish": "Publish",
    "advanced": "Advanced",
}


def preset_v2_validation_issues(value: Any) -> list[PresetValidationIssue]:
    """Return validation issues grouped by user-facing preset sections."""

    try:
        PresetV2.model_validate(value)
    except ValidationError as exc:
        issues: list[PresetValidationIssue] = []
        for error in exc.errors():
            loc = [str(part) for part in error.get("loc", ()) if str(part)]
            issues.append(
                PresetValidationIssue(
                    section=_section_label(loc),
                    path=".".join(loc) if loc else "preset",
                    message=str(error.get("msg", "")),
                )
            )
        return issues
    return []


def _section_label(loc: Sequence[str]) -> str:
    if not loc:
        return "Preset"
    first = loc[0]
    return _SECTION_LABELS.get(first, "Preset")


__all__ = [
    "PRESET_POLICY_SCHEMA_VERSION",
    "PRESET_POLICY_WRITE_FORMAT",
    "AdvancedPolicy",
    "AudioPolicy",
    "ContainerPolicy",
    "DimensionsPolicy",
    "DirectCopyMaxBitratePolicy",
    "FiltersPolicy",
    "GuardsPolicy",
    "PresetV2",
    "PresetValidationIssue",
    "PublishPolicy",
    "ResolutionAwareBitratePolicy",
    "RoutingPolicy",
    "SizeGuardsPolicy",
    "OutputSizeCheckAction",
    "SubtitlePolicy",
    "VerificationPolicy",
    "VideoPolicy",
    "preset_v2_validation_issues",
]
