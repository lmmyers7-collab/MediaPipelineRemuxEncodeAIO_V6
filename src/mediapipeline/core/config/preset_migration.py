"""Stable config and PresetV2 display adapters."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from mediapipeline.core.config.encoding_capabilities import active_video_filter_names
from mediapipeline.core.config.preset_compatibility import (
    BLOCKED_FUTURE_PERSISTED_KEYS,
    FRIENDLY_LABEL_PERSISTED_KEY_ALIASES,
    LABEL_ONLY_RENAMES,
    LABEL_ONLY_RENAME_POLICIES,
    LEGACY_COMPATIBILITY_KEY_STATUSES,
    MIGRATION_STATUS_VALUES,
    PERSISTED_KEY_MIGRATION_STATUS,
    MigrationStatus,
)
from mediapipeline.core.config.preset_display_adapter import _encoder_backend, _video_codec_family
from mediapipeline.core.config.preset_migration_models import _legacy_config_and_extra, _legacy_number, _size_on_exceeded
from mediapipeline.core.config.preset_policy import (
    PRESET_POLICY_SCHEMA_VERSION,
    AdvancedPolicy,
    AudioPolicy,
    ContainerPolicy,
    DimensionsPolicy,
    DirectCopyMaxBitratePolicy,
    FiltersPolicy,
    GuardsPolicy,
    PresetV2,
    PublishPolicy,
    ResolutionAwareBitratePolicy,
    RoutingPolicy,
    SizeGuardsPolicy,
    SubtitlePolicy,
    VerificationPolicy,
    VideoPolicy,
)
from mediapipeline.contracts.config import Config
from mediapipeline.contracts.decision_policy import EffectiveDecisionPolicy

def legacy_config_patch_from_preset_v2(
    value: PresetV2 | Mapping[str, Any],
    *,
    validate: bool = True,
) -> dict[str, Any]:
    """Return a stable PSD1-key patch for a PresetV2 adapter/display model."""

    preset = value if isinstance(value, PresetV2) else PresetV2.model_validate(value)
    patch: dict[str, Any] = {
        "RoutingProfile": preset.processing_strategy,
        "RouteThresholdMode": preset.routing.enforcement_mode,
        "SizeGuardMode": preset.guards.size.mode,
        "EncodeTuningPreset": preset.video.encoder_quality_preset,
        "EncodeLadder": preset.video.target_selection,
        "MaxEncodeGrowthPercent": _legacy_number(preset.guards.size.quality_encode_growth_tolerance_pct),
        "CompatibilityEncodeGrowthPercent": _legacy_number(preset.guards.size.compatibility_encode_growth_tolerance_pct),
        "MovieRoute1080pTargetSizeGB": _legacy_number(preset.guards.size.movie_route_1080p_size_limit_gb),
        "MovieRoute1440pTargetSizeGB": _legacy_number(preset.guards.size.movie_route_1440p_size_limit_gb),
        "MovieRoute4KTargetSizeGB": _legacy_number(preset.guards.size.movie_route_4k_size_limit_gb),
        "TVRoute1080pTargetSizeGB": _legacy_number(preset.guards.size.tv_route_1080p_size_limit_gb),
        "TVRoute1440pTargetSizeGB": _legacy_number(preset.guards.size.tv_route_1440p_size_limit_gb),
        "TVRoute4KTargetSizeGB": _legacy_number(preset.guards.size.tv_route_4k_size_limit_gb),
        "Route1080pUpperHeightTolerancePercent": preset.routing.resolution_aware_bitrate.bucket_1080p_upper_height_tolerance_pct,
        "Route1080pMaxVideoBitrateMbps": _legacy_number(
            preset.routing.resolution_aware_bitrate.bucket_1080p_max_bitrate_mbps
        ),
        "Route1440pLowerHeightTolerancePercent": preset.routing.resolution_aware_bitrate.bucket_1440p_lower_height_tolerance_pct,
        "Route1440pUpperHeightTolerancePercent": preset.routing.resolution_aware_bitrate.bucket_1440p_upper_height_tolerance_pct,
        "Route1440pMaxVideoBitrateMbps": _legacy_number(
            preset.routing.resolution_aware_bitrate.bucket_1440p_max_bitrate_mbps
        ),
        "Route4KLowerHeightTolerancePercent": preset.routing.resolution_aware_bitrate.bucket_4k_lower_height_tolerance_pct,
        "Route4KMaxVideoBitrateMbps": _legacy_number(
            preset.routing.resolution_aware_bitrate.bucket_4k_max_bitrate_mbps
        ),
        "VideoCodec": preset.video.codec,
        "VideoPreset": preset.video.encoder_speed_preset,
        "VideoQuality": preset.video.quality_target,
        "OutputContainer": preset.container.format,
        "RemuxSafeVideoCodecs": list(preset.routing.direct_copy_video_codec_allowlist),
        "ExtraVideoFlags": list(preset.advanced.extra_video_flags),
    }
    if validate:
        Config.model_validate(patch)
    return patch

def preset_v2_from_legacy_config(
    value: Config | Mapping[str, Any] | None = None,
    *,
    name: str = "Migrated legacy policy",
) -> PresetV2:
    """Adapt current flat legacy config values into a read-only PresetV2 view."""

    config, extra = _legacy_config_and_extra(value)
    return PresetV2(
        name=name,
        processing_strategy=config.RoutingProfile,
        routing=RoutingPolicy(
            enforcement_mode=config.RouteThresholdMode,
            direct_copy_max_bitrate=DirectCopyMaxBitratePolicy(
                movie_mbps=config.Route1080pMaxVideoBitrateMbps,
                tv_mbps=config.Route1080pMaxVideoBitrateMbps,
            ),
            resolution_aware_bitrate=ResolutionAwareBitratePolicy(
                bucket_1080p_upper_height_tolerance_pct=config.Route1080pUpperHeightTolerancePercent,
                bucket_1080p_max_bitrate_mbps=config.Route1080pMaxVideoBitrateMbps,
                bucket_1440p_lower_height_tolerance_pct=config.Route1440pLowerHeightTolerancePercent,
                bucket_1440p_upper_height_tolerance_pct=config.Route1440pUpperHeightTolerancePercent,
                bucket_1440p_max_bitrate_mbps=config.Route1440pMaxVideoBitrateMbps,
                bucket_4k_lower_height_tolerance_pct=config.Route4KLowerHeightTolerancePercent,
                bucket_4k_max_bitrate_mbps=config.Route4KMaxVideoBitrateMbps,
            ),
            allow_h264_compatible_direct_copy=config.AllowH264RemuxIfPlexCompatible,
            h264_direct_copy_max_bitrate_mbps=config.H264RemuxMaxBitrateMbps,
            h264_direct_copy_max_height=config.H264RemuxMaxHeight,
            direct_copy_video_codec_allowlist=config.RemuxSafeVideoCodecs,
        ),
        dimensions=DimensionsPolicy(h264_direct_copy_max_height=config.H264RemuxMaxHeight),
        filters=FiltersPolicy(
            strip_ass_formatting=config.StripFormatting,
            remove_karaoke=config.RemoveKaraoke,
            merge_adjacent=config.MergeAdjacent,
            merge_threshold_ms=config.MergeThresholdMs,
        ),
        video=VideoPolicy(
            codec=config.VideoCodec,
            codec_family=_video_codec_family(config.VideoCodec),
            encoder_backend=_encoder_backend(config.VideoCodec),
            encoder_speed_preset=config.VideoPreset,
            quality_target=config.VideoQuality,
            encoder_quality_preset=config.EncodeTuningPreset,
            target_selection=config.EncodeLadder,
        ),
        audio=AudioPolicy(
            passthrough_default=True,
            passthrough_profile=config.AudioPassthroughProfile,
            compatible_codecs=config.CompatibleAudioCodecs,
            preferred_default_languages=config.PreferredDefaultAudioLanguages,
            transcode_codec=config.AudioTranscodeCodec,
            transcode_bitrate=config.AudioTranscodeBitrate,
            transcode_auto_bitrate_by_channels=config.AudioTranscodeAutoBitrateByChannels,
            downmix_mode=config.AudioDownmixMode,
            max_channels=config.AudioMaxChannels,
            force_transcode=False,
            allow_no_audio=config.AllowNoAudio,
        ),
        subtitles=SubtitlePolicy(
            keep_languages=config.SubKeepLanguages,
            generate_preferred_srt=config.ConvertTx3gToSrt or config.ConvertBdpgsToSrt or config.ConvertVobSubToSrt,
            burn_in_forced=False,
            convert_tx3g_to_srt=config.ConvertTx3gToSrt,
            drop_tx3g_after_conversion=config.DropTx3gAfterConversion,
            create_external_tx3g_srt_sidecars=config.CreateExternalTx3gSrtSidecars,
            tx3g_extract_languages=config.Tx3gExtractLanguages,
            tx3g_preserve_existing_srt=config.Tx3gPreserveExistingSrt,
            tx3g_treat_forced_as_separate=config.Tx3gTreatForcedAsSeparate,
            convert_bdpgs_to_srt=config.ConvertBdpgsToSrt,
            drop_bdpgs_after_conversion=config.DropBdpgsAfterConversion,
            bdpgs_extract_languages=config.BdpgsExtractLanguages,
            bdpgs_ocr_tool_path=config.BdpgsOcrToolPath,
            bdpgs_ocr_tessdata_path=config.BdpgsOcrTessdataPath,
            convert_vobsub_to_srt=config.ConvertVobSubToSrt,
            drop_vobsub_after_conversion=config.DropVobSubAfterConversion,
            vobsub_extract_languages=config.VobSubExtractLanguages,
            vobsub_ocr_tool_path=config.VobSubOcrToolPath,
            drop_ass_after_conversion=config.DropAssAfterConversion,
            keep_signs_and_songs=config.KeepSignsAndSongs,
            treat_ass_signs_songs_as_forced=config.TreatAssSignsSongsAsForced,
            treat_tx3g_signs_songs_as_forced=config.TreatTx3gSignsSongsAsForced,
            treat_bdpgs_signs_songs_as_forced=config.TreatBdpgsSignsSongsAsForced,
            treat_vobsub_signs_songs_as_forced=config.TreatVobSubSignsSongsAsForced,
            sdh_title_keywords=config.SubSDHTitleKeywords,
            supplemental_keywords=config.SubSupplementalKeywords,
            excluded_styles=config.ExcludeSubtitleStyles,
            included_styles=config.IncludeSubtitleStyles,
        ),
        container=ContainerPolicy(format=config.OutputContainer),
        guards=GuardsPolicy(
            size=SizeGuardsPolicy(
                mode=config.SizeGuardMode,
                on_exceeded=_size_on_exceeded(config.SizeGuardMode),
                compatibility_encode_growth_tolerance_pct=config.CompatibilityEncodeGrowthPercent,
                quality_encode_growth_tolerance_pct=config.MaxEncodeGrowthPercent,
                movie_route_size_limit_gb=config.MovieRoute1080pTargetSizeGB,
                tv_route_size_limit_gb=config.TVRoute1080pTargetSizeGB,
                movie_route_1080p_size_limit_gb=config.MovieRoute1080pTargetSizeGB,
                movie_route_1440p_size_limit_gb=config.MovieRoute1440pTargetSizeGB,
                movie_route_4k_size_limit_gb=config.MovieRoute4KTargetSizeGB,
                tv_route_1080p_size_limit_gb=config.TVRoute1080pTargetSizeGB,
                tv_route_1440p_size_limit_gb=config.TVRoute1440pTargetSizeGB,
                tv_route_4k_size_limit_gb=config.TVRoute4KTargetSizeGB,
                route_output_size_multiplier=config.OutputSizeMultiplier,
            )
        ),
        verification=VerificationPolicy(
            output_probe_timeout_seconds=config.OutputValidationProbeTimeoutSeconds,
            output_min_size_bytes=config.OutputValidationMinSizeBytes,
            output_duration_tolerance_seconds=config.OutputValidationDurationToleranceSeconds,
            source_integrity_preflight_enabled=config.EnableIntegrityCheck,
            source_stability_wait_seconds=config.FileStabilityWait,
            skip_source_stability_check=config.SkipStabilityCheck,
            source_media_extensions=config.ValidExtensions,
        ),
        publish=PublishPolicy(
            deferred_publish=config.DeferredPublish,
            output_free_space_reserve_gb=config.OutsourceMinFreeSpaceGB,
            final_library_promotion_enabled=config.FinalLibraryPromotionEnabled,
            final_library_promotion_rules=config.FinalLibraryPromotionRules,
            final_library_promotion_verification_mode=config.FinalLibraryPromotionVerificationMode,
            final_library_promotion_cleanup_after_verified=config.FinalLibraryPromotionCleanupAfterVerified,
            final_library_promotion_overwrite_existing=config.FinalLibraryPromotionOverwriteExisting,
        ),
        advanced=AdvancedPolicy(
            extra_video_flags=config.ExtraVideoFlags,
            fallback_cpu_quality=config.FallbackCpuQuality,
            cpu_encode_preset=config.CpuEncodePreset,
            cpu_encode_process_priority=config.CpuEncodeProcessPriority,
            cpu_encode_max_threads=config.CpuEncodeMaxThreads,
            ffmpeg_encode_timeout_seconds=config.FFmpegEncodeTimeoutSeconds,
            ffmpeg_cpu_encode_timeout_seconds=config.FFmpegCpuEncodeTimeoutSeconds,
            ffmpeg_remux_timeout_seconds=config.FFmpegRemuxTimeoutSeconds,
            mkvmerge_remux_timeout_seconds=config.MkvmergeRemuxTimeoutSeconds,
            subtitle_extract_timeout_seconds=config.SubtitleExtractTimeoutSeconds,
            subtitle_probe_timeout_seconds=config.SubtitleProbeTimeoutSeconds,
            bdpgs_ocr_timeout_seconds=config.BdpgsOcrTimeoutSeconds,
            vobsub_ocr_timeout_seconds=config.VobSubOcrTimeoutSeconds,
            copy_transfer_flags=config.RobocopyFlags,
            copy_transfer_timeout_seconds=config.RobocopyTimeoutSeconds,
            transient_failure_retry_limit=config.TransientFailureRetryLimit,
            scratch_free_space_reserve_gb=config.MinFreeSpaceGB,
            cleanup_remote_staging_enabled=config.CleanupRemoteStaging,
            cleanup_stale_age_hours=config.CleanupStaleAgeHours,
            legacy_passthrough=extra,
        ),
    )

def effective_decision_policy_from_preset_v2(value: PresetV2 | Mapping[str, Any]) -> EffectiveDecisionPolicy:
    """Project a PresetV2 document into the current decision-engine input."""

    preset = value if isinstance(value, PresetV2) else PresetV2.model_validate(value)
    return EffectiveDecisionPolicy(
        routing_profile=preset.processing_strategy,
        route_threshold_mode=preset.routing.enforcement_mode,
        size_guard_mode=preset.guards.size.mode,
        output_size_check_action=preset.guards.size.on_exceeded,
        quality_encode_growth_tolerance_percent=preset.guards.size.quality_encode_growth_tolerance_pct,
        compatibility_encode_growth_tolerance_percent=preset.guards.size.compatibility_encode_growth_tolerance_pct,
        movie_route_1080p_size_limit_gb=preset.guards.size.movie_route_1080p_size_limit_gb,
        movie_route_1440p_size_limit_gb=preset.guards.size.movie_route_1440p_size_limit_gb,
        movie_route_4k_size_limit_gb=preset.guards.size.movie_route_4k_size_limit_gb,
        tv_route_1080p_size_limit_gb=preset.guards.size.tv_route_1080p_size_limit_gb,
        tv_route_1440p_size_limit_gb=preset.guards.size.tv_route_1440p_size_limit_gb,
        tv_route_4k_size_limit_gb=preset.guards.size.tv_route_4k_size_limit_gb,
        route_1080p_upper_height_tolerance_percent=(
            preset.routing.resolution_aware_bitrate.bucket_1080p_upper_height_tolerance_pct
        ),
        route_1080p_max_video_bitrate_mbps=preset.routing.resolution_aware_bitrate.bucket_1080p_max_bitrate_mbps,
        route_1440p_lower_height_tolerance_percent=(
            preset.routing.resolution_aware_bitrate.bucket_1440p_lower_height_tolerance_pct
        ),
        route_1440p_upper_height_tolerance_percent=(
            preset.routing.resolution_aware_bitrate.bucket_1440p_upper_height_tolerance_pct
        ),
        route_1440p_max_video_bitrate_mbps=preset.routing.resolution_aware_bitrate.bucket_1440p_max_bitrate_mbps,
        route_4k_lower_height_tolerance_percent=(
            preset.routing.resolution_aware_bitrate.bucket_4k_lower_height_tolerance_pct
        ),
        route_4k_max_video_bitrate_mbps=preset.routing.resolution_aware_bitrate.bucket_4k_max_bitrate_mbps,
        allow_h264_compatible_direct_copy=preset.routing.allow_h264_compatible_direct_copy,
        h264_direct_copy_max_bitrate_mbps=preset.routing.h264_direct_copy_max_bitrate_mbps,
        h264_direct_copy_max_height=preset.routing.h264_direct_copy_max_height,
        max_direct_copy_height=preset.dimensions.max_direct_copy_height,
        output_container=preset.container.format,
        force_container_remux=preset.container.force_remux,
        direct_copy_video_codecs=preset.routing.direct_copy_video_codec_allowlist,
        mp4_audio_copy_codecs=preset.audio.mp4_copy_codecs,
        mp4_subtitle_copy_codecs=preset.subtitles.mp4_copy_codecs,
        resolution_limit=preset.dimensions.resolution_limit,
        custom_max_height=preset.dimensions.custom_max_height,
        scaling_policy=preset.dimensions.scaling_policy,
        crop_mode=preset.dimensions.crop_mode,
        video_filter_names=active_video_filter_names(preset.filters),
        video_output_codec=preset.video.codec,
        video_codec_family=preset.video.codec_family,
        video_encoder_backend=preset.video.encoder_backend,
        video_target_mode=preset.video.target_mode,
        video_quality_target=preset.video.quality_target,
        video_target_bitrate_mbps=preset.video.target_bitrate_mbps,
        video_max_bitrate_mbps=preset.video.max_bitrate_mbps,
        audio_passthrough_profile=preset.audio.passthrough_profile,
        audio_passthrough_codecs=preset.audio.compatible_codecs,
        audio_transcode_codec=preset.audio.transcode_codec,
        audio_max_channels=preset.audio.max_channels,
        audio_force_transcode=preset.audio.force_transcode,
        subtitle_mode=preset.subtitles.mode,
        subtitle_burn_in_forced=preset.subtitles.burn_in_forced or preset.subtitles.mode == "burn_forced",
    )

def effective_decision_policy_from_legacy_or_preset(
    value: Config | PresetV2 | Mapping[str, Any] | None,
) -> EffectiveDecisionPolicy:
    """Read either current legacy config or PresetV2 and return decision policy."""

    if isinstance(value, PresetV2):
        return effective_decision_policy_from_preset_v2(value)
    if isinstance(value, Mapping) and value.get("version") == PRESET_POLICY_SCHEMA_VERSION:
        return effective_decision_policy_from_preset_v2(value)
    return effective_decision_policy_from_preset_v2(preset_v2_from_legacy_config(value))

__all__ = [
    "BLOCKED_FUTURE_PERSISTED_KEYS",
    "FRIENDLY_LABEL_PERSISTED_KEY_ALIASES",
    "LABEL_ONLY_RENAMES",
    "LABEL_ONLY_RENAME_POLICIES",
    "LEGACY_COMPATIBILITY_KEY_STATUSES",
    "MIGRATION_STATUS_VALUES",
    "PERSISTED_KEY_MIGRATION_STATUS",
    "MigrationStatus",
    "effective_decision_policy_from_legacy_or_preset",
    "effective_decision_policy_from_preset_v2",
    "legacy_config_patch_from_preset_v2",
    "preset_v2_from_legacy_config",
]
