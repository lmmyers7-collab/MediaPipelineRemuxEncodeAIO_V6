from __future__ import annotations

from typing import Any

from mediapipeline_desktop_app.config_keys import (
    KEY_BDPGS_OCR_TIMEOUT_SECONDS,
    KEY_CLEANUP_SCAN_TIMEOUT_SECONDS,
    KEY_CLEANUP_STALE_AGE_HOURS,
    KEY_COMPATIBILITY_ENCODE_GROWTH_PERCENT,
    KEY_CPU_ENCODE_MAX_THREADS,
    KEY_AUDIO_MAX_CHANNELS,
    KEY_ENCODE_THRESHOLD_GB,
    KEY_FALLBACK_CPU_QUALITY,
    KEY_FFMPEG_CPU_ENCODE_TIMEOUT_SECONDS,
    KEY_FFMPEG_ENCODE_TIMEOUT_SECONDS,
    KEY_FFMPEG_REMUX_TIMEOUT_SECONDS,
    KEY_H264_REMUX_MAX_BITRATE_MBPS,
    KEY_H264_REMUX_MAX_HEIGHT,
    KEY_INDEX_SCAN_TIMEOUT_SECONDS,
    KEY_LOCAL_BASE,
    KEY_MAX_ENCODE_GROWTH_PERCENT,
    KEY_MERGE_THRESHOLD_MS,
    KEY_MIN_FREE_SPACE_GB,
    KEY_MOVIE_ROUTE_MAX_VIDEO_BITRATE_MBPS,
    KEY_MKVMERGE_REMUX_TIMEOUT_SECONDS,
    KEY_OUTSOURCE,
    KEY_OUTSOURCE_MIN_FREE_SPACE_GB,
    KEY_OUTPUT_CONTAINER,
    KEY_OUTPUT_SIZE_MULTIPLIER,
    KEY_PROCESSED_INDEX_REFRESH_SECONDS,
    KEY_ROBOCOPY_TIMEOUT_SECONDS,
    KEY_SOURCE_MOVIES,
    KEY_SOURCE_SCAN_INTERVAL_SECONDS,
    KEY_SOURCE_SCAN_TIMEOUT_SECONDS,
    KEY_SOURCE_TV,
    KEY_SUBTITLE_EXTRACT_TIMEOUT_SECONDS,
    KEY_SUBTITLE_PROBE_TIMEOUT_SECONDS,
    KEY_TRANSIENT_FAILURE_RETRY_LIMIT,
    KEY_TV_ENCODE_THRESHOLD_GB,
    KEY_TV_ROUTE_MAX_VIDEO_BITRATE_MBPS,
    KEY_VIDEO_CODEC,
    KEY_VIDEO_PRESET,
    KEY_VIDEO_QUALITY,
)
from app.config.value_checks import (
    require_non_empty,
    validate_int,
    validate_optional_float,
    validate_optional_int,
)


def validate_required_and_numeric_config(values: dict[str, Any], errors: list[str]) -> None:
    for key, label in (
        (KEY_SOURCE_MOVIES, "SourceMovies"),
        (KEY_SOURCE_TV, "SourceTV"),
        (KEY_OUTSOURCE, "Outsource"),
        (KEY_LOCAL_BASE, "LocalBase"),
        (KEY_VIDEO_CODEC, "VideoCodec"),
        (KEY_VIDEO_PRESET, "VideoPreset"),
        (KEY_OUTPUT_CONTAINER, "OutputContainer"),
    ):
        require_non_empty(values, errors, key, label)

    validate_int(values, errors, KEY_ENCODE_THRESHOLD_GB, "EncodeThresholdGB", minimum=1)
    validate_int(values, errors, KEY_TV_ENCODE_THRESHOLD_GB, "TVEncodeThresholdGB", minimum=1)
    if KEY_MOVIE_ROUTE_MAX_VIDEO_BITRATE_MBPS in values:
        validate_int(
            values,
            errors,
            KEY_MOVIE_ROUTE_MAX_VIDEO_BITRATE_MBPS,
            "MovieRouteMaxVideoBitrateMbps",
            minimum=1,
            maximum=500,
        )
    if KEY_TV_ROUTE_MAX_VIDEO_BITRATE_MBPS in values:
        validate_int(
            values,
            errors,
            KEY_TV_ROUTE_MAX_VIDEO_BITRATE_MBPS,
            "TVRouteMaxVideoBitrateMbps",
            minimum=1,
            maximum=500,
        )
    if KEY_H264_REMUX_MAX_BITRATE_MBPS in values:
        validate_int(values, errors, KEY_H264_REMUX_MAX_BITRATE_MBPS, "H264RemuxMaxBitrateMbps", minimum=1, maximum=500)
    if KEY_H264_REMUX_MAX_HEIGHT in values:
        validate_int(values, errors, KEY_H264_REMUX_MAX_HEIGHT, "H264RemuxMaxHeight", minimum=1, maximum=4320)
    if KEY_MAX_ENCODE_GROWTH_PERCENT in values:
        validate_int(values, errors, KEY_MAX_ENCODE_GROWTH_PERCENT, "MaxEncodeGrowthPercent", minimum=0, maximum=1000)
    if KEY_COMPATIBILITY_ENCODE_GROWTH_PERCENT in values:
        validate_int(
            values,
            errors,
            KEY_COMPATIBILITY_ENCODE_GROWTH_PERCENT,
            "CompatibilityEncodeGrowthPercent",
            minimum=0,
            maximum=1000,
        )
    validate_int(values, errors, KEY_MIN_FREE_SPACE_GB, "MinFreeSpaceGB", minimum=0)
    validate_int(values, errors, KEY_OUTSOURCE_MIN_FREE_SPACE_GB, "OutsourceMinFreeSpaceGB", minimum=0)
    validate_int(values, errors, KEY_VIDEO_QUALITY, "VideoQuality", minimum=1, maximum=51)
    if KEY_AUDIO_MAX_CHANNELS in values:
        validate_int(values, errors, KEY_AUDIO_MAX_CHANNELS, "AudioMaxChannels", minimum=1, maximum=16)
    validate_int(values, errors, KEY_MERGE_THRESHOLD_MS, "MergeThresholdMs", minimum=0, maximum=5000)
    validate_int(values, errors, KEY_FFMPEG_ENCODE_TIMEOUT_SECONDS, "FFmpegEncodeTimeoutSeconds", minimum=1)
    if KEY_FFMPEG_CPU_ENCODE_TIMEOUT_SECONDS in values:
        validate_int(values, errors, KEY_FFMPEG_CPU_ENCODE_TIMEOUT_SECONDS, "FFmpegCpuEncodeTimeoutSeconds", minimum=1)
    validate_int(values, errors, KEY_FFMPEG_REMUX_TIMEOUT_SECONDS, "FFmpegRemuxTimeoutSeconds", minimum=1)
    if KEY_MKVMERGE_REMUX_TIMEOUT_SECONDS in values:
        validate_int(values, errors, KEY_MKVMERGE_REMUX_TIMEOUT_SECONDS, "MkvmergeRemuxTimeoutSeconds", minimum=60, maximum=86400)
    validate_int(values, errors, KEY_SUBTITLE_EXTRACT_TIMEOUT_SECONDS, "SubtitleExtractTimeoutSeconds", minimum=30, maximum=3600)
    validate_int(values, errors, KEY_SUBTITLE_PROBE_TIMEOUT_SECONDS, "SubtitleProbeTimeoutSeconds", minimum=5, maximum=600)
    validate_int(values, errors, KEY_BDPGS_OCR_TIMEOUT_SECONDS, "BdpgsOcrTimeoutSeconds", minimum=60, maximum=14400)
    validate_int(values, errors, KEY_TRANSIENT_FAILURE_RETRY_LIMIT, "TransientFailureRetryLimit", minimum=1, maximum=100)
    validate_int(values, errors, KEY_SOURCE_SCAN_INTERVAL_SECONDS, "SourceScanIntervalSeconds", minimum=0)
    validate_int(values, errors, KEY_PROCESSED_INDEX_REFRESH_SECONDS, "ProcessedIndexRefreshSeconds", minimum=0)
    validate_int(values, errors, KEY_ROBOCOPY_TIMEOUT_SECONDS, "RobocopyTimeoutSeconds", minimum=60, maximum=172800)
    validate_int(values, errors, KEY_SOURCE_SCAN_TIMEOUT_SECONDS, "SourceScanTimeoutSeconds", minimum=30, maximum=86400)
    validate_int(values, errors, KEY_INDEX_SCAN_TIMEOUT_SECONDS, "IndexScanTimeoutSeconds", minimum=30, maximum=86400)
    validate_int(values, errors, KEY_CLEANUP_SCAN_TIMEOUT_SECONDS, "CleanupScanTimeoutSeconds", minimum=30, maximum=7200)
    validate_int(values, errors, KEY_CLEANUP_STALE_AGE_HOURS, "CleanupStaleAgeHours", minimum=1, maximum=720)
    validate_optional_int(values, errors, KEY_FALLBACK_CPU_QUALITY, "FallbackCpuQuality", minimum=1, maximum=51)
    validate_optional_float(values, errors, KEY_OUTPUT_SIZE_MULTIPLIER, "OutputSizeMultiplier", minimum=0.1, maximum=2.0)

    if KEY_CPU_ENCODE_MAX_THREADS in values:
        validate_int(values, errors, KEY_CPU_ENCODE_MAX_THREADS, "CpuEncodeMaxThreads", minimum=0, maximum=256)
