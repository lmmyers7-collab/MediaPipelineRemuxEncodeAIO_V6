from __future__ import annotations

import re
from typing import Any

from mediapipeline_desktop_app.config_keys import (
    KEY_AUDIO_DOWNMIX_MODE,
    KEY_AUDIO_PASSTHROUGH_PROFILE,
    KEY_AUDIO_TRANSCODE_BITRATE,
    KEY_AUDIO_TRANSCODE_CODEC,
    KEY_COMPATIBLE_AUDIO_CODECS,
    KEY_CONSOLE_LOG_LEVEL,
    KEY_CPU_ENCODE_PRESET,
    KEY_CPU_ENCODE_PROCESS_PRIORITY,
    KEY_ENCODE_LADDER,
    KEY_ENCODE_TUNING_PRESET,
    KEY_EXTRA_VIDEO_FLAGS,
    KEY_FILE_LOG_LEVEL,
    KEY_FINAL_LIBRARY_PROMOTION_VERIFICATION_MODE,
    KEY_OUTPUT_CONTAINER,
    KEY_PRIORITY_MARKERS,
    KEY_REMUX_SAFE_VIDEO_CODECS,
    KEY_ROBOCOPY_FLAGS,
    KEY_ROUTE_THRESHOLD_MODE,
    KEY_ROUTING_PROFILE,
    KEY_SIZE_GUARD_MODE,
    KEY_SUB_KEEP_LANGUAGES,
    KEY_VALID_EXTENSIONS,
    KEY_VIDEO_CODEC,
    KEY_VIDEO_PRESET,
)
from app.shared.constants import (
    AUDIO_PASSTHROUGH_PROFILE_CODECS,
    AUDIO_PASSTHROUGH_PROFILE_DEFAULT,
    AUDIO_PASSTHROUGH_PROFILE_NAMES,
    LOG_LEVEL_VALUES,
    ROUTE_THRESHOLD_MODE_NAMES,
    ROUTING_PROFILE_NAMES,
    SIZE_GUARD_MODE_NAMES,
)


def validate_option_config(values: dict[str, Any], errors: list[str], warnings: list[str]) -> None:
    if KEY_CPU_ENCODE_PRESET in values:
        cpu_preset = str(values.get(KEY_CPU_ENCODE_PRESET, "") or "").strip().lower()
        cpu_preset_choices = {
            "ultrafast", "superfast", "veryfast", "faster", "fast",
            "medium", "slow", "slower", "veryslow", "placebo",
        }
        if cpu_preset and cpu_preset not in cpu_preset_choices:
            errors.append(
                "CpuEncodePreset must be one of: " + ", ".join(sorted(cpu_preset_choices)) + "."
            )
    if KEY_CPU_ENCODE_PROCESS_PRIORITY in values:
        cpu_priority = str(values.get(KEY_CPU_ENCODE_PROCESS_PRIORITY, "") or "").strip().lower()
        cpu_priority_choices = {"inherit", "idle", "belownormal", "normal", "abovenormal", "high"}
        if cpu_priority and cpu_priority not in cpu_priority_choices:
            errors.append(
                "CpuEncodeProcessPriority must be one of: " + ", ".join(sorted(cpu_priority_choices)) + "."
            )

    output_container = str(values.get(KEY_OUTPUT_CONTAINER, "") or "").strip().lower()
    if output_container not in {"mkv", "mp4"}:
        errors.append("OutputContainer must be 'mkv' or 'mp4'.")

    encode_tuning = str(values.get(KEY_ENCODE_TUNING_PRESET, "balanced_nvenc") or "balanced_nvenc").strip().lower()
    if encode_tuning not in {"balanced_nvenc", "quality_nvenc", "fast_nvenc", "compatibility", "custom_legacy_flags"}:
        errors.append("EncodeTuningPreset must be one of: balanced_nvenc, quality_nvenc, fast_nvenc, compatibility, custom_legacy_flags.")
    if encode_tuning == "custom_legacy_flags" and not values.get(KEY_EXTRA_VIDEO_FLAGS):
        warnings.append("EncodeTuningPreset is custom_legacy_flags, but ExtraVideoFlags is empty.")
    if encode_tuning != "custom_legacy_flags" and values.get(KEY_EXTRA_VIDEO_FLAGS):
        warnings.append("ExtraVideoFlags are ignored unless EncodeTuningPreset is custom_legacy_flags; Save In Place will write an empty ExtraVideoFlags list.")
    encode_ladder = str(values.get(KEY_ENCODE_LADDER, "auto") or "auto").strip().lower()
    if encode_ladder not in {"auto", "tv_balanced", "tv_space_saver", "movie_balanced", "movie_archive", "plex_compat"}:
        errors.append("EncodeLadder must be one of: auto, tv_balanced, tv_space_saver, movie_balanced, movie_archive, plex_compat.")
    routing_profile = str(values.get(KEY_ROUTING_PROFILE, "plex_direct_stream") or "plex_direct_stream").strip().lower()
    if routing_profile not in ROUTING_PROFILE_NAMES:
        errors.append(f"RoutingProfile must be one of: {', '.join(ROUTING_PROFILE_NAMES)}.")
    route_threshold_mode = str(
        values.get(KEY_ROUTE_THRESHOLD_MODE, "compatibility_advisory") or "compatibility_advisory"
    ).strip().lower()
    if route_threshold_mode not in ROUTE_THRESHOLD_MODE_NAMES:
        errors.append(f"RouteThresholdMode must be one of: {', '.join(ROUTE_THRESHOLD_MODE_NAMES)}.")
    size_guard_mode = str(values.get(KEY_SIZE_GUARD_MODE, "advisory") or "advisory").strip().lower()
    if size_guard_mode not in SIZE_GUARD_MODE_NAMES:
        errors.append(f"SizeGuardMode must be one of: {', '.join(SIZE_GUARD_MODE_NAMES)}.")
    if size_guard_mode == "strict" and routing_profile == "archive_shrink":
        warnings.append("Archive Shrink with strict Output Size Check can reject outputs that do not shrink enough; use advisory while tuning.")

    video_codec = str(values.get(KEY_VIDEO_CODEC, "") or "").strip().lower()
    if video_codec and video_codec not in {"hevc_nvenc", "libx265", "h264_nvenc", "libx264", "av1_nvenc"}:
        errors.append("VideoCodec must be one of: av1_nvenc, h264_nvenc, hevc_nvenc, libx264, libx265.")
    video_preset = str(values.get(KEY_VIDEO_PRESET, "") or "").strip().lower()
    if video_preset and video_preset not in {"p1", "p2", "p3", "p4", "p5", "p6", "p7"}:
        errors.append("VideoPreset must be one of: p1, p2, p3, p4, p5, p6, p7.")

    promotion_verification = str(
        values.get(KEY_FINAL_LIBRARY_PROMOTION_VERIFICATION_MODE, "cautious") or "cautious"
    ).strip().lower()
    if promotion_verification not in {"fast", "cautious"}:
        errors.append("FinalLibraryPromotionVerificationMode must be fast or cautious.")

    audio_profile = str(values.get(KEY_AUDIO_PASSTHROUGH_PROFILE, AUDIO_PASSTHROUGH_PROFILE_DEFAULT) or AUDIO_PASSTHROUGH_PROFILE_DEFAULT).strip().lower()
    if audio_profile not in AUDIO_PASSTHROUGH_PROFILE_NAMES:
        errors.append(f"AudioPassthroughProfile must be one of: {', '.join(AUDIO_PASSTHROUGH_PROFILE_NAMES)}.")
    elif audio_profile in AUDIO_PASSTHROUGH_PROFILE_CODECS:
        configured_audio = values.get(KEY_COMPATIBLE_AUDIO_CODECS)
        normalized_configured = [
            str(item).strip().lower()
            for item in configured_audio
            if str(item).strip()
        ] if isinstance(configured_audio, list) else []
        profile_codecs = list(AUDIO_PASSTHROUGH_PROFILE_CODECS[audio_profile])
        if normalized_configured and normalized_configured != profile_codecs:
            warnings.append("CompatibleAudioCodecs are controlled by AudioPassthroughProfile unless it is custom_codec_list; Save In Place will write the selected profile codec list.")

    audio_codec = str(values.get(KEY_AUDIO_TRANSCODE_CODEC, "eac3") or "eac3").strip().lower()
    if audio_codec not in {"eac3", "ac3", "aac"}:
        errors.append("AudioTranscodeCodec must be one of: eac3, ac3, aac.")
    audio_bitrate = str(values.get(KEY_AUDIO_TRANSCODE_BITRATE, "640k") or "640k").strip().lower()
    if not re.fullmatch(r"\d+k", audio_bitrate):
        errors.append("AudioTranscodeBitrate must look like 640k.")
    audio_downmix = str(values.get(KEY_AUDIO_DOWNMIX_MODE, "max_channels") or "max_channels").strip().lower()
    if audio_downmix not in {"preserve", "max_channels", "stereo"}:
        errors.append("AudioDownmixMode must be one of: preserve, max_channels, stereo.")

    for key, label in (
        (KEY_COMPATIBLE_AUDIO_CODECS, "CompatibleAudioCodecs"),
        (KEY_PRIORITY_MARKERS, "PriorityMarkers"),
        (KEY_REMUX_SAFE_VIDEO_CODECS, "RemuxSafeVideoCodecs"),
        (KEY_SUB_KEEP_LANGUAGES, "SubKeepLanguages"),
        (KEY_VALID_EXTENSIONS, "ValidExtensions"),
        (KEY_ROBOCOPY_FLAGS, "RobocopyFlags"),
    ):
        raw = values.get(key)
        if not isinstance(raw, list) or not raw:
            errors.append(f"{label} must contain at least one value.")

    valid_extensions = values.get(KEY_VALID_EXTENSIONS)
    if isinstance(valid_extensions, list):
        for item in valid_extensions:
            extension = str(item or "").strip()
            if not re.fullmatch(r"\.[A-Za-z0-9][A-Za-z0-9_+-]{0,15}", extension):
                errors.append("ValidExtensions entries must start with a dot and contain only extension-safe characters.")
                break

    robocopy_flags = values.get(KEY_ROBOCOPY_FLAGS)
    if isinstance(robocopy_flags, list):
        for item in robocopy_flags:
            flag = str(item or "").strip()
            if not flag or not flag.startswith("/"):
                errors.append("RobocopyFlags entries must be non-empty robocopy switches beginning with '/'.")
                break

    for key in (KEY_CONSOLE_LOG_LEVEL, KEY_FILE_LOG_LEVEL):
        value = str(values.get(key, "") or "").strip().upper()
        if value and value not in LOG_LEVEL_VALUES:
            errors.append(f"{key} must be one of: ERROR, WARN, INFO, DEBUG, or blank.")
