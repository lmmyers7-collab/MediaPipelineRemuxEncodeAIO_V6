from __future__ import annotations

from typing import Any

from ..config_keys import (
    KEY_ALLOW_NO_AUDIO,
    KEY_AUDIO_DOWNMIX_MODE,
    KEY_AUDIO_MAX_CHANNELS,
    KEY_AUDIO_PASSTHROUGH_PROFILE,
    KEY_BDPGS_EXTRACT_LANGUAGES,
    KEY_BDPGS_OCR_TESSDATA_PATH,
    KEY_BDPGS_OCR_TOOL_PATH,
    KEY_CLEANUP_REMOTE_STAGING,
    KEY_COMPATIBILITY_ENCODE_GROWTH_PERCENT,
    KEY_COMPATIBLE_AUDIO_CODECS,
    KEY_CONVERT_BDPGS_TO_SRT,
    KEY_CONVERT_TX3G_TO_SRT,
    KEY_CREATE_EXTERNAL_TX3G_SRT_SIDECARS,
    KEY_DEFERRED_PUBLISH,
    KEY_DROP_ASS_AFTER_CONVERSION,
    KEY_DROP_BDPGS_AFTER_CONVERSION,
    KEY_DROP_TX3G_AFTER_CONVERSION,
    KEY_ENABLE_INTEGRITY_CHECK,
    KEY_KEEP_SIGNS_AND_SONGS,
    KEY_MAX_ENCODE_GROWTH_PERCENT,
    KEY_OUTPUT_CONTAINER,
    KEY_OUTPUT_SIZE_MULTIPLIER,
    KEY_OUTSOURCE_MIN_FREE_SPACE_GB,
    KEY_PREFERRED_DEFAULT_AUDIO_LANGUAGES,
    KEY_REMOVE_KARAOKE,
    KEY_ROBOCOPY_TIMEOUT_SECONDS,
    KEY_ROUTING_PROFILE,
    KEY_SIZE_GUARD_MODE,
    KEY_SKIP_STABILITY_CHECK,
    KEY_STRIP_FORMATTING,
    KEY_SUB_KEEP_LANGUAGES,
    KEY_TRANSIENT_FAILURE_RETRY_LIMIT,
    KEY_TX3G_EXTRACT_LANGUAGES,
)
from app.config.metadata import CONFIG_MANAGED_KEYS
from .settings_risk_policy_rules import (
    changed_key_risk_item,
    list_setting_values,
    removed_key_item,
    risk_warning_messages,
    source_mutation_setting,
    summarize_risk_items,
    truthy_setting,
    unknown_schema_key_item,
)


_MISSING = object()


def build_settings_patch_risk_summary(
    base_config: dict[str, Any],
    merged: dict[str, Any],
    changed_keys: list[str],
    removed_keys: list[str],
) -> dict[str, Any]:
    managed = {str(key).casefold() for key in CONFIG_MANAGED_KEYS}
    items: list[dict[str, str]] = []

    for key in sorted(set(changed_keys + removed_keys), key=str.casefold):
        if key.casefold() not in managed:
            items.append(unknown_schema_key_item(key))

    for key in sorted(set(removed_keys), key=str.casefold):
        items.append(removed_key_item(key))

    for key in sorted(set(changed_keys), key=str.casefold):
        item = changed_key_risk_item(key, merged.get(key))
        if item:
            items.append(item)

    counts, highest = summarize_risk_items(items)
    return {
        "schema_version": "settings_patch_risk_summary.v1",
        "highest_severity": highest,
        "counts": counts,
        "total_count": len(items),
        "items": items,
        "warning_messages": risk_warning_messages(items),
    }


def build_current_settings_risk_summary(config: dict[str, Any]) -> dict[str, Any]:
    """Summarize active saved-config risks without treating normal paths as changes."""
    items: list[dict[str, str]] = []
    for key in sorted(config, key=lambda item: str(item).casefold()):
        item = changed_key_risk_item(str(key), config.get(key))
        if not item:
            continue
        if item.get("code") == "path_root_changed":
            continue
        items.append(item)

    counts, highest = summarize_risk_items(items)
    return {
        "schema_version": "settings_current_risk_summary.v1",
        "highest_severity": highest,
        "counts": counts,
        "total_count": len(items),
        "items": items,
        "warning_messages": risk_warning_messages(items),
    }


def _config_value(config: dict[str, Any], key: str, default: Any = None) -> Any:
    if key in config:
        return config[key]
    normalized = key.casefold()
    for candidate, value in config.items():
        if str(candidate).casefold() == normalized:
            return value
    return default


def _text_value(config: dict[str, Any], key: str, default: str = "") -> str:
    value = _config_value(config, key, default)
    if value is None:
        return default
    return str(value).strip()


def _bool_value(config: dict[str, Any], key: str, default: bool = False) -> bool:
    value = _config_value(config, key, default)
    if value is None:
        return default
    return truthy_setting(value)


def _list_value(config: dict[str, Any], key: str, default: list[str] | None = None) -> list[str]:
    value = _config_value(config, key, _MISSING)
    if value is _MISSING:
        return list(default or [])
    values = list_setting_values(value)
    return values


def _number_value(config: dict[str, Any], key: str, default: float = 0.0) -> float:
    try:
        return float(_config_value(config, key, default))
    except (TypeError, ValueError):
        return default


def _int_text(value: float) -> str:
    return str(int(value)) if float(value).is_integer() else str(value)


def _readiness_row(
    area: str,
    posture: str,
    evidence: str,
    operator_check: str,
    keys: list[str],
) -> dict[str, Any]:
    return {
        "area": area,
        "posture": posture,
        "evidence": evidence,
        "operator_check": operator_check,
        "keys": keys,
    }


def _readiness_counts(rows: list[dict[str, Any]]) -> dict[str, int]:
    counts = {"coherent": 0, "review": 0, "blocked": 0}
    for row in rows:
        posture = str(row.get("posture") or "review").casefold()
        if posture not in counts:
            posture = "review"
        counts[posture] += 1
    return counts


def _readiness_status(counts: dict[str, int]) -> str:
    if counts.get("blocked", 0):
        return "Blocked review"
    if counts.get("review", 0):
        return "Review"
    return "Ready"


def _language_gaps(base: list[str], candidates: list[str]) -> list[str]:
    normalized = {item.casefold() for item in base}
    return [item for item in candidates if item.casefold() not in normalized]


def build_media_policy_readiness(config: dict[str, Any]) -> dict[str, Any]:
    """Return backend-authored, read-only readiness rows for saved media policy."""
    routing_profile = _text_value(config, KEY_ROUTING_PROFILE, "plex_direct_stream") or "plex_direct_stream"
    size_guard = _text_value(config, KEY_SIZE_GUARD_MODE, "advisory") or "advisory"
    output_container = _text_value(config, KEY_OUTPUT_CONTAINER, "mkv") or "mkv"
    max_growth = _number_value(config, KEY_MAX_ENCODE_GROWTH_PERCENT, 5.0)
    compat_growth = _number_value(config, KEY_COMPATIBILITY_ENCODE_GROWTH_PERCENT, 15.0)

    keep_languages = _list_value(config, KEY_SUB_KEEP_LANGUAGES, ["eng", "und"])
    tx3g_languages = _list_value(config, KEY_TX3G_EXTRACT_LANGUAGES, ["eng", "und"])
    bdpgs_languages = _list_value(config, KEY_BDPGS_EXTRACT_LANGUAGES, ["eng", "und"])
    convert_tx3g = _bool_value(config, KEY_CONVERT_TX3G_TO_SRT, True)
    drop_tx3g = _bool_value(config, KEY_DROP_TX3G_AFTER_CONVERSION, False)
    tx3g_sidecars = _bool_value(config, KEY_CREATE_EXTERNAL_TX3G_SRT_SIDECARS, False)
    convert_bdpgs = _bool_value(config, KEY_CONVERT_BDPGS_TO_SRT, True)
    drop_bdpgs = _bool_value(config, KEY_DROP_BDPGS_AFTER_CONVERSION, False)
    drop_ass = _bool_value(config, KEY_DROP_ASS_AFTER_CONVERSION, False)
    strip_formatting = _bool_value(config, KEY_STRIP_FORMATTING, True)
    remove_karaoke = _bool_value(config, KEY_REMOVE_KARAOKE, True)
    keep_signs = _bool_value(config, KEY_KEEP_SIGNS_AND_SONGS, True)

    audio_languages = _list_value(config, KEY_PREFERRED_DEFAULT_AUDIO_LANGUAGES, ["english"])
    audio_profile = _text_value(config, KEY_AUDIO_PASSTHROUGH_PROFILE, "plex_balanced") or "plex_balanced"
    audio_codecs = _list_value(config, KEY_COMPATIBLE_AUDIO_CODECS, ["aac", "ac3", "eac3"])
    downmix_mode = _text_value(config, KEY_AUDIO_DOWNMIX_MODE, "max_channels") or "max_channels"
    max_channels = _number_value(config, KEY_AUDIO_MAX_CHANNELS, 6.0)
    allow_no_audio = _bool_value(config, KEY_ALLOW_NO_AUDIO, False)

    deferred_publish = _bool_value(config, KEY_DEFERRED_PUBLISH, False)
    cleanup_remote = _bool_value(config, KEY_CLEANUP_REMOTE_STAGING, False)
    skip_stability = _bool_value(config, KEY_SKIP_STABILITY_CHECK, False)
    integrity_check = _bool_value(config, KEY_ENABLE_INTEGRITY_CHECK, True)
    retry_limit = _number_value(config, KEY_TRANSIENT_FAILURE_RETRY_LIMIT, 3.0)
    copy_timeout = _number_value(config, KEY_ROBOCOPY_TIMEOUT_SECONDS, 14400.0)
    min_free = _number_value(config, KEY_OUTSOURCE_MIN_FREE_SPACE_GB, 20.0)
    output_multiplier = _number_value(config, KEY_OUTPUT_SIZE_MULTIPLIER, 1.15)

    rows: list[dict[str, Any]] = []
    size_posture = "review" if size_guard.casefold() in {"off", "disabled"} or max_growth <= 0 or compat_growth <= 0 else "coherent"
    rows.append(
        _readiness_row(
            "Routing / size guard",
            size_posture,
            f"profile={routing_profile}; size_guard={size_guard}; normal_growth={_int_text(max_growth)}%; compatibility_growth={_int_text(compat_growth)}%",
            "Keep size guard advisory/strict for unattended Plex batches; off or non-positive growth caps can allow oversized encodes without a clear hold point.",
            [KEY_ROUTING_PROFILE, KEY_SIZE_GUARD_MODE, KEY_MAX_ENCODE_GROWTH_PERCENT, KEY_COMPATIBILITY_ENCODE_GROWTH_PERCENT],
        )
    )

    mp4_preserves_incompatible = output_container.casefold() == "mp4" and (not drop_bdpgs or not drop_ass)
    rows.append(
        _readiness_row(
            "Container / subtitle preservation",
            "review" if mp4_preserves_incompatible else "coherent",
            f"container={output_container}; drop_ass={drop_ass}; drop_bdpgs={drop_bdpgs}; drop_tx3g={drop_tx3g}; tx3g_sidecars={tx3g_sidecars}",
            "MKV is the safest preservation container. If MP4 is selected, verify unsupported original subtitle types are externalized or deliberately dropped instead of misboxed.",
            [KEY_OUTPUT_CONTAINER, KEY_DROP_ASS_AFTER_CONVERSION, KEY_DROP_BDPGS_AFTER_CONVERSION, KEY_DROP_TX3G_AFTER_CONVERSION, KEY_CREATE_EXTERNAL_TX3G_SRT_SIDECARS],
        )
    )

    tx3g_gaps = _language_gaps(keep_languages, tx3g_languages)
    bdpgs_gaps = _language_gaps(keep_languages, bdpgs_languages)
    rows.append(
        _readiness_row(
            "Subtitle language routing",
            "review" if not keep_languages or tx3g_gaps or bdpgs_gaps else "coherent",
            f"keep={', '.join(keep_languages) or '(empty)'}; tx3g={', '.join(tx3g_languages) or '(empty)'}; bdpgs={', '.join(bdpgs_languages) or '(empty)'}",
            "Preferred subtitle language drives SRT generation; keep TX3G/BDPGS extract languages aligned unless extract-only language gaps are intentional.",
            [KEY_SUB_KEEP_LANGUAGES, KEY_TX3G_EXTRACT_LANGUAGES, KEY_BDPGS_EXTRACT_LANGUAGES],
        )
    )

    rows.append(
        _readiness_row(
            "TX3G / mov_text SRT",
            "blocked" if drop_tx3g and not convert_tx3g else "review" if (not convert_tx3g or drop_tx3g) else "coherent",
            f"convert={convert_tx3g}; drop_original={drop_tx3g}; external_sidecar={tx3g_sidecars}",
            "Default Plex posture should add SRT for preferred-language TX3G while preserving original timed text unless the drop toggle is explicit.",
            [KEY_CONVERT_TX3G_TO_SRT, KEY_DROP_TX3G_AFTER_CONVERSION, KEY_CREATE_EXTERNAL_TX3G_SRT_SIDECARS],
        )
    )

    rows.append(
        _readiness_row(
            "BDPGS OCR to SRT",
            "blocked" if drop_bdpgs and not convert_bdpgs else "review" if (not convert_bdpgs or drop_bdpgs) else "coherent",
            f"ocr={convert_bdpgs}; drop_original={drop_bdpgs}",
            "Preferred-language PGS should OCR to SRT for Plex clients, and OCR failures should remain visible for manual review.",
            [KEY_CONVERT_BDPGS_TO_SRT, KEY_DROP_BDPGS_AFTER_CONVERSION, KEY_BDPGS_OCR_TOOL_PATH, KEY_BDPGS_OCR_TESSDATA_PATH],
        )
    )

    rows.append(
        _readiness_row(
            "ASS / SSA preservation",
            "review" if drop_ass else "coherent",
            f"drop_original={drop_ass}; strip_formatting={strip_formatting}; remove_karaoke={remove_karaoke}; keep_signs={keep_signs}",
            "Preserve ASS/SSA originals by default. SRT conversion can strip styling and apply negative filters without deleting the styled source track.",
            [KEY_DROP_ASS_AFTER_CONVERSION, KEY_STRIP_FORMATTING, KEY_REMOVE_KARAOKE, KEY_KEEP_SIGNS_AND_SONGS],
        )
    )

    rows.append(
        _readiness_row(
            "Audio language / default track",
            "review" if not audio_languages else "coherent",
            f"preferred_default_languages={', '.join(audio_languages) or '(empty)'}",
            "Preferred default audio languages make unattended default-track behavior more predictable when sources have mixed metadata.",
            [KEY_PREFERRED_DEFAULT_AUDIO_LANGUAGES],
        )
    )

    audio_posture = "blocked" if allow_no_audio else "review" if audio_profile.casefold() in {"lossless_passthrough", "custom_codec_list"} or (audio_profile.casefold() == "custom_codec_list" and not audio_codecs) or downmix_mode.casefold() in {"stereo", "preserve"} or (0 < max_channels < 6) else "coherent"
    rows.append(
        _readiness_row(
            "Audio passthrough / channels",
            audio_posture,
            f"profile={audio_profile}; codecs={', '.join(audio_codecs) or '(empty)'}; downmix={downmix_mode}; max_channels={_int_text(max_channels)}; allow_no_audio={allow_no_audio}",
            "Keep no-audio disabled for normal Plex output. Custom/lossless passthrough and stereo caps are valid only when direct-play tradeoffs are intentional.",
            [KEY_AUDIO_PASSTHROUGH_PROFILE, KEY_COMPATIBLE_AUDIO_CODECS, KEY_AUDIO_DOWNMIX_MODE, KEY_AUDIO_MAX_CHANNELS, KEY_ALLOW_NO_AUDIO],
        )
    )

    publish_posture = "review" if cleanup_remote or skip_stability or not integrity_check or retry_limit > 8 or (0 < copy_timeout < 300) or min_free < 5 or output_multiplier < 0.5 else "coherent"
    rows.append(
        _readiness_row(
            "Publish / recovery safety",
            publish_posture,
            f"deferred={deferred_publish}; cleanup_remote={cleanup_remote}; stability={'skipped' if skip_stability else 'enabled'}; integrity={integrity_check}; retries={_int_text(retry_limit)}; copy_timeout={_int_text(copy_timeout)}s; reserve={_int_text(min_free)}GB; size_multiplier={output_multiplier:g}",
            "Slow disks and SMB shares need stability checks, integrity checks, reasonable copy timeouts, and enough output reserve before unattended processing.",
            [KEY_DEFERRED_PUBLISH, KEY_CLEANUP_REMOTE_STAGING, KEY_SKIP_STABILITY_CHECK, KEY_ENABLE_INTEGRITY_CHECK, KEY_TRANSIENT_FAILURE_RETRY_LIMIT, KEY_ROBOCOPY_TIMEOUT_SECONDS, KEY_OUTSOURCE_MIN_FREE_SPACE_GB, KEY_OUTPUT_SIZE_MULTIPLIER],
        )
    )

    source_mutation_keys = sorted(str(key) for key, value in config.items() if source_mutation_setting(str(key), value))
    rows.append(
        _readiness_row(
            "Source preservation",
            "blocked" if source_mutation_keys else "coherent",
            f"source_mutation_keys={', '.join(source_mutation_keys) or 'none'}",
            "Normal processing must copy to scratch and preserve source files. Any source deletion/move policy needs explicit operator opt-in before unattended use.",
            source_mutation_keys or ["DeleteSourceAfterProcessing"],
        )
    )

    counts = _readiness_counts(rows)
    operator_status = _readiness_status(counts)
    review_rows = [row for row in rows if row["posture"] != "coherent"]
    summary_lines = [
        "Backend media-policy readiness:",
        f"Status: {operator_status}; rows={len(rows)}; coherent={counts['coherent']}; review={counts['review']}; blocked={counts['blocked']}.",
        "This is read-only evidence from saved backend settings. It does not stage changes, launch work, run FFmpeg, publish files, or touch source media.",
    ]
    if review_rows:
        summary_lines.append("")
        summary_lines.append("Rows needing operator attention:")
        summary_lines.extend(f"- {row['area']}: {row['operator_check']}" for row in review_rows[:8])
        if len(review_rows) > 8:
            summary_lines.append(f"- +{len(review_rows) - 8} more review row(s).")
    else:
        summary_lines.append("")
        summary_lines.append("No backend media-policy contradictions detected in saved settings.")

    return {
        "schema_version": "settings_media_policy_readiness.v1",
        "operator_status": operator_status,
        "counts": counts,
        "total_count": len(rows),
        "rows": rows,
        "summary_lines": summary_lines,
        "read_only": True,
    }
