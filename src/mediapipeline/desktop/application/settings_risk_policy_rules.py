from __future__ import annotations

from typing import Any

RiskItem = dict[str, str]

SEVERITY_ORDER = {"critical": 4, "high": 3, "medium": 2, "low": 1}


def truthy_setting(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, int | float):
        return value != 0
    return str(value or "").strip().casefold() in {"1", "true", "yes", "on", "enabled", "enable"}


def list_setting_values(value: Any) -> list[str]:
    if isinstance(value, list | tuple | set):
        return [str(item or "").strip() for item in value if str(item or "").strip()]
    if isinstance(value, str):
        return [item.strip() for item in value.split(",") if item.strip()]
    return []


def source_mutation_setting(key: str, value: Any) -> bool:
    normalized_key = str(key or "").casefold().replace("_", "").replace("-", "")
    mutation_keys = (
        "deletesource",
        "sourcedelete",
        "removesource",
        "sourceremove",
        "deleteoriginal",
        "removeoriginal",
        "postsuccessoriginal",
        "defaultoriginalmode",
        "originalmode",
    )
    if not any(token in normalized_key for token in mutation_keys):
        return False
    if isinstance(value, bool):
        return value
    normalized_value = str(value or "").strip().casefold()
    return normalized_value in {"1", "true", "yes", "on", "delete", "remove", "move", "trash", "recycle"}


def make_risk_item(severity: str, code: str, key: str, message: str) -> RiskItem:
    return {
        "severity": severity,
        "code": code,
        "key": key,
        "message": message,
    }


def unknown_schema_key_item(key: str) -> RiskItem:
    return make_risk_item(
        "medium",
        "unknown_key",
        key,
        f"{key} is not part of the desktop settings schema. It may be preserved but ignored by the pipeline.",
    )


def removed_key_item(key: str) -> RiskItem:
    return make_risk_item(
        "medium",
        "removed_key",
        key,
        f"{key} is staged for removal. Verify the backend has a default or the pipeline may fall back unexpectedly.",
    )


def changed_key_risk_item(key: str, value: Any) -> RiskItem | None:
    normalized_key = key.casefold()
    if normalized_key == "allowpsystemtools":
        # Kept for forward compatibility with misspelled local experiments.
        normalized_key = "allowsystemtools"
    if normalized_key == "allownoaudio" and truthy_setting(value):
        return make_risk_item(
            "high",
            "no_audio_allowed",
            key,
            "AllowNoAudio is enabled. Silent or failed-audio sources could publish without an audio track.",
        )
    if normalized_key == "preferreddefaultaudiolanguages" and not list_setting_values(value):
        return make_risk_item(
            "medium",
            "empty_default_audio_languages",
            key,
            "PreferredDefaultAudioLanguages is empty. Default audio selection will depend on source metadata.",
        )
    if normalized_key == "compatibleaudiocodecs" and not list_setting_values(value):
        return make_risk_item(
            "medium",
            "empty_audio_passthrough_codecs",
            key,
            "CompatibleAudioCodecs is empty. Custom audio passthrough policy can force unexpected transcodes.",
        )
    if normalized_key == "audiopassthroughprofile":
        audio_profile = str(value or "").strip().casefold()
        if audio_profile == "custom_codec_list":
            return make_risk_item(
                "medium",
                "custom_audio_passthrough_profile",
                key,
                "AudioPassthroughProfile is custom_codec_list. Manual codec choices now control copy-vs-transcode behavior.",
            )
        if audio_profile == "lossless_passthrough":
            return make_risk_item(
                "medium",
                "lossless_audio_passthrough_profile",
                key,
                "AudioPassthroughProfile is lossless_passthrough. Some Plex clients may transcode TrueHD/DTS-family audio.",
            )
    if normalized_key == "audiodownmixmode":
        audio_downmix = str(value or "").strip().casefold()
        if audio_downmix == "stereo":
            return make_risk_item(
                "medium",
                "forced_stereo_downmix",
                key,
                "AudioDownmixMode is stereo. Transcoded surround tracks will be collapsed to 2.0.",
            )
        if audio_downmix == "preserve":
            return make_risk_item(
                "low",
                "preserve_source_audio_channels",
                key,
                "AudioDownmixMode is preserve. Incompatible source channel layouts may carry forward when transcoding.",
            )
    if normalized_key == "audiomaxchannels":
        try:
            max_channels = int(value)
        except (TypeError, ValueError):
            max_channels = 0
        if 0 < max_channels < 6:
            return make_risk_item(
                "medium",
                "low_audio_channel_cap",
                key,
                "AudioMaxChannels is below 6. Surround tracks can be downmixed during audio normalization.",
            )
    if normalized_key == "subkeeplanguages" and not list_setting_values(value):
        return make_risk_item(
            "medium",
            "empty_subtitle_keep_languages",
            key,
            "SubKeepLanguages is empty. Preferred-language subtitle routing may become unpredictable.",
        )
    if normalized_key == "converttx3gtosrt" and not truthy_setting(value):
        return make_risk_item(
            "medium",
            "tx3g_srt_conversion_disabled",
            key,
            "ConvertTx3gToSrt is disabled. Preferred-language mov_text/TX3G subtitles will not generate Plex-friendly SRT.",
        )
    if normalized_key == "convertbdpgstosrt" and not truthy_setting(value):
        return make_risk_item(
            "medium",
            "bdpgs_srt_conversion_disabled",
            key,
            "ConvertBdpgsToSrt is disabled. Preferred-language PGS subtitles will not be OCRed to SRT for Plex clients.",
        )
    if normalized_key == "convertvobsubtosrt" and not truthy_setting(value):
        return make_risk_item(
            "medium",
            "vobsub_srt_conversion_disabled",
            key,
            "ConvertVobSubToSrt is disabled. Preferred-language VobSub subtitles will not be OCRed to SRT for Plex clients.",
        )
    if normalized_key == "allowsystemtools" and truthy_setting(value):
        return make_risk_item(
            "high",
            "system_tool_fallback",
            key,
            "AllowSystemTools is enabled. The pipeline may use PATH tools instead of the bundled FFmpeg/ffprobe/toolchain.",
        )
    if normalized_key == "skipstabilitycheck" and truthy_setting(value):
        return make_risk_item(
            "high",
            "file_stability_check_disabled",
            key,
            "SkipStabilityCheck is enabled. Torrents, interrupted SMB copies, and still-growing files can enter processing.",
        )
    if normalized_key == "enableintegritycheck" and not truthy_setting(value):
        return make_risk_item(
            "medium",
            "integrity_check_disabled",
            key,
            "EnableIntegrityCheck is disabled. Corrupt or partially readable media may not be held back before processing.",
        )
    if normalized_key == "deferredpublish" and truthy_setting(value):
        return make_risk_item(
            "low",
            "pending_publish_monitor_required",
            key,
            "DeferredPublish is enabled. Completed outputs may remain parked until the pending-publish drain succeeds.",
        )
    if normalized_key == "cleanupremotestaging" and truthy_setting(value):
        return make_risk_item(
            "medium",
            "remote_staging_cleanup_enabled",
            key,
            "CleanupRemoteStaging is enabled. Cleanup may touch slow or unreliable remote staging paths after publish.",
        )
    if normalized_key == "transientfailureretrylimit":
        try:
            retry_limit = int(value)
        except (TypeError, ValueError):
            retry_limit = 0
        if retry_limit > 8:
            return make_risk_item(
                "medium",
                "high_transient_retry_limit",
                key,
                "TransientFailureRetryLimit is high. Persistent network, disk, or media failures may wait too long for operator review.",
            )
    if normalized_key == "robocopytimeoutseconds":
        try:
            timeout = int(value)
        except (TypeError, ValueError):
            timeout = 0
        if 0 < timeout < 300:
            return make_risk_item(
                "medium",
                "short_copy_timeout",
                key,
                "RobocopyTimeoutSeconds is below five minutes. Large media copies on slow disks or SMB shares may fail prematurely.",
            )
    if normalized_key == "encodetuningpreset" and str(value or "").strip().casefold() == "custom_legacy_flags":
        return make_risk_item(
            "medium",
            "custom_video_flags_enabled",
            key,
            "EncodeTuningPreset is custom_legacy_flags. Raw ExtraVideoFlags may be passed to FFmpeg/NVENC unchanged.",
        )
    if normalized_key == "extravideoflags":
        has_flags = bool(value) if not isinstance(value, list | tuple | set) else any(str(item).strip() for item in value)
        if has_flags:
            return make_risk_item(
                "medium",
                "raw_video_flags_present",
                key,
                "ExtraVideoFlags is populated. Freeform FFmpeg flags can override structured encode policy.",
            )
    if normalized_key == "reprocessall" and truthy_setting(value):
        return make_risk_item(
            "medium",
            "full_reprocess_enabled",
            key,
            "ReprocessAll is enabled. Previously completed files may be reconsidered instead of skipped.",
        )
    if normalized_key == "sizeguardmode":
        mode = str(value or "").strip().casefold()
        if mode == "off":
            return make_risk_item(
                "high",
                "size_guard_disabled",
                key,
                "SizeGuardMode is off. Encodes that grow far beyond source size will not be blocked or warned by Output Size Check.",
            )
        if mode == "strict":
            return make_risk_item(
                "medium",
                "strict_size_guard",
                key,
                "SizeGuardMode is strict. Oversized encodes will fail before publishing.",
            )
        if mode == "fallback_remux":
            return make_risk_item(
                "medium",
                "fallback_remux_size_guard",
                key,
                "SizeGuardMode tries remux fallback for oversized override-forced encodes; validate with real media before unattended batches.",
            )
    if normalized_key in {"droptx3gafterconversion", "dropbdpgsafterconversion", "dropvobsubafterconversion", "dropassafterconversion"} and truthy_setting(value):
        return make_risk_item(
            "medium",
            "drops_original_subtitle",
            key,
            f"{key} is enabled. Original subtitle tracks of that type may be omitted after SRT conversion.",
        )
    if normalized_key == "outputcontainer" and str(value or "").strip().casefold() == "mp4":
        return make_risk_item(
            "medium",
            "mp4_container_limits",
            key,
            "OutputContainer is MP4. Incompatible subtitle types such as ASS/PGS/VobSub cannot be preserved in that container.",
        )
    if normalized_key == "validextensions":
        extensions = [str(item or "").strip().casefold() for item in value] if isinstance(value, list | tuple | set) else []
        risky = {".part", ".tmp", ".download", ".crdownload"} & set(extensions)
        if risky:
            return make_risk_item(
                "high",
                "partial_download_extension_allowed",
                key,
                f"ValidExtensions includes likely partial-download extensions: {', '.join(sorted(risky))}.",
            )
    if normalized_key == "robocopyflags":
        flags = [str(item or "").strip().casefold() for item in value] if isinstance(value, list | tuple | set) else []
        mt_flag = next((item for item in flags if item.startswith("/mt:")), "")
        try:
            mt_count = int(mt_flag.split(":", 1)[1]) if mt_flag else 0
        except ValueError:
            mt_count = 0
        if mt_count > 8:
            return make_risk_item(
                "medium",
                "high_robocopy_thread_count",
                key,
                f"RobocopyFlags uses {mt_flag.upper()}. High copy concurrency can saturate disks or network shares.",
            )
    if normalized_key == "outputsizemultiplier":
        try:
            multiplier = float(value)
        except (TypeError, ValueError):
            multiplier = 0.0
        if 0 < multiplier < 0.5:
            return make_risk_item(
                "medium",
                "low_output_size_estimate",
                key,
                "OutputSizeMultiplier is below 0.5. Pre-encode disk reservation may underestimate final output size.",
            )
    if source_mutation_setting(key, value):
        return make_risk_item(
            "high",
            "source_mutation_policy",
            key,
            f"{key} appears to enable source/original-file mutation. Verify this is intentional before saving.",
        )
    if normalized_key in {"sourcemovies", "sourcetv", "outsource", "localbase"}:
        return make_risk_item(
            "medium",
            "path_root_changed",
            key,
            f"{key} changes a pipeline root. Verify UNC access, nesting, free space, and scratch/output separation before saving.",
        )
    return None


def summarize_risk_items(items: list[RiskItem]) -> tuple[dict[str, int], str]:
    counts = {name: 0 for name in ("critical", "high", "medium", "low")}
    highest = "none"
    for item in items:
        severity = item["severity"]
        counts[severity] = counts.get(severity, 0) + 1
        if SEVERITY_ORDER.get(severity, 0) > SEVERITY_ORDER.get(highest, 0):
            highest = severity
    return counts, highest


def risk_warning_messages(items: list[RiskItem]) -> list[str]:
    return [
        f"Settings risk [{item['severity']}/{item['code']}/{item['key']}]: {item['message']}"
        for item in items
        if SEVERITY_ORDER.get(item["severity"], 0) >= SEVERITY_ORDER["medium"]
    ]
