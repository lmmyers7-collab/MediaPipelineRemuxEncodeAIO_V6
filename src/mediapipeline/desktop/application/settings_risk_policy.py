from __future__ import annotations

from typing import Any

from ..config_keys import (
    KEY_ALLOW_H264_REMUX_IF_PLEX_COMPATIBLE,
    KEY_ALLOW_NO_AUDIO,
    KEY_ALLOW_SYSTEM_TOOLS,
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
    KEY_CONVERT_VOBSUB_TO_SRT,
    KEY_CREATE_EXTERNAL_TX3G_SRT_SIDECARS,
    KEY_DEFERRED_PUBLISH,
    KEY_DROP_ASS_AFTER_CONVERSION,
    KEY_DROP_BDPGS_AFTER_CONVERSION,
    KEY_DROP_TX3G_AFTER_CONVERSION,
    KEY_DROP_VOBSUB_AFTER_CONVERSION,
    KEY_ENCODE_LADDER,
    KEY_ENCODE_THRESHOLD_GB,
    KEY_ENCODE_TUNING_PRESET,
    KEY_ENABLE_INTEGRITY_CHECK,
    KEY_EXTRA_VIDEO_FLAGS,
    KEY_H264_REMUX_MAX_BITRATE_MBPS,
    KEY_H264_REMUX_MAX_HEIGHT,
    KEY_KEEP_SIGNS_AND_SONGS,
    KEY_LOCAL_BASE,
    KEY_MAX_ENCODE_GROWTH_PERCENT,
    KEY_MOVIE_ROUTE_MAX_VIDEO_BITRATE_MBPS,
    KEY_OUTPUT_CONTAINER,
    KEY_OUTPUT_SIZE_MULTIPLIER,
    KEY_OUTSOURCE,
    KEY_OUTSOURCE_MIN_FREE_SPACE_GB,
    KEY_PREFERRED_DEFAULT_AUDIO_LANGUAGES,
    KEY_REMOVE_KARAOKE,
    KEY_REMUX_SAFE_VIDEO_CODECS,
    KEY_ROBOCOPY_TIMEOUT_SECONDS,
    KEY_ROUTING_PROFILE,
    KEY_SIZE_GUARD_MODE,
    KEY_SOURCE_MOVIES,
    KEY_SOURCE_TV,
    KEY_SKIP_STABILITY_CHECK,
    KEY_STRIP_FORMATTING,
    KEY_SUB_KEEP_LANGUAGES,
    KEY_TRANSIENT_FAILURE_RETRY_LIMIT,
    KEY_TV_ENCODE_THRESHOLD_GB,
    KEY_TV_ROUTE_MAX_VIDEO_BITRATE_MBPS,
    KEY_TX3G_EXTRACT_LANGUAGES,
    KEY_VOBSUB_EXTRACT_LANGUAGES,
    KEY_VOBSUB_OCR_TOOL_PATH,
    KEY_VIDEO_CODEC,
)
from mediapipeline.core.config.metadata import CONFIG_MANAGED_KEYS
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


def _display_text(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    if value is None:
        return ""
    return str(value)


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


def _row_key(area: str, fallback_index: int) -> str:
    key = "".join(ch.lower() if ch.isalnum() else "-" for ch in str(area or ""))
    key = "-".join(part for part in key.split("-") if part)
    return key or f"risk-{fallback_index}"


def _launch_risk_row(
    rows: list[dict[str, Any]],
    area: str,
    impact: str,
    evidence: str,
    action: str,
    detail: list[str] | None = None,
    **extra: Any,
) -> None:
    row: dict[str, Any] = {
        "key": _row_key(area, len(rows) + 1),
        "area": area,
        "impact": impact,
        "evidence": evidence,
        "action": action,
        "detail": list(detail or []),
        "source": "backend",
    }
    row.update(extra)
    rows.append(row)


def _launch_risk_counts(rows: list[dict[str, Any]]) -> dict[str, int]:
    counts = {"ready": 0, "review": 0, "high review": 0, "blocked": 0}
    for row in rows:
        impact = str(row.get("impact") or "review").casefold()
        if impact not in counts:
            impact = "review"
        counts[impact] += 1
    return counts


def _launch_risk_status(rows: list[dict[str, Any]]) -> str:
    counts = _launch_risk_counts(rows)
    if counts["blocked"]:
        return "Blocked review"
    if counts["high review"]:
        return "High review"
    if counts["review"]:
        return "Review"
    return "Ready" if rows else "No settings"


def _launch_risk_summary_lines(rows: list[dict[str, Any]]) -> list[str]:
    counts = _launch_risk_counts(rows)
    lines = [
        "Launch settings risk handoff:",
        f"Rows: {len(rows)}; ready={counts['ready']}; review={counts['review']}; high review={counts['high review']}; blocked={counts['blocked']}.",
        "This panel translates saved settings posture into launch-specific operator checks.",
        "Backend launch validation, process locks, and settings preview/save remain the source of truth.",
        "Real-media proof still requires a completed sample run with route, subtitle/audio, output, sidecar, size-growth, and pending-publish evidence.",
    ]
    review_rows = [row for row in rows if row.get("impact") != "ready"]
    if review_rows:
        lines.append("")
        lines.append("Rows needing attention:")
        lines.extend(f"- {row.get('area')}: {row.get('action')}" for row in review_rows[:8])
        if len(review_rows) > 8:
            lines.append(f"- {len(review_rows) - 8} more row(s) need review.")
    else:
        lines.append("")
        lines.append("No local saved-settings launch blockers detected.")
    return lines


def build_launch_settings_risk_handoff(
    config: dict[str, Any],
    *,
    risk_summary: dict[str, Any] | None = None,
    media_policy_readiness: dict[str, Any] | None = None,
    errors: list[str] | None = None,
    warnings: list[str] | None = None,
) -> dict[str, Any]:
    """Return backend-authored launch risk rows over saved settings.

    The WebView may still add request-only context such as the selected launch
    mode, but the saved-settings policy/risk rows originate here.
    """
    risk = risk_summary or build_current_settings_risk_summary(config)
    readiness = media_policy_readiness or build_media_policy_readiness(config)
    warnings = list(warnings or [])
    errors = list(errors or [])
    risk_items = risk.get("items") if isinstance(risk.get("items"), list) else []
    readiness_rows = readiness.get("rows") if isinstance(readiness.get("rows"), list) else []
    readiness_counts = readiness.get("counts") if isinstance(readiness.get("counts"), dict) else {}
    readiness_status = str(readiness.get("operator_status") or "not evaluated").casefold()
    highest = str(risk.get("highest_severity") or "none").casefold()
    total = int(risk.get("total_count") or 0)

    deferred = _bool_value(config, KEY_DEFERRED_PUBLISH, False)
    stability_skipped = _bool_value(config, KEY_SKIP_STABILITY_CHECK, False)
    integrity = _bool_value(config, KEY_ENABLE_INTEGRITY_CHECK, True)
    allow_no_audio = _bool_value(config, KEY_ALLOW_NO_AUDIO, False)
    allow_system_tools = _bool_value(config, KEY_ALLOW_SYSTEM_TOOLS, False)
    convert_tx3g = _bool_value(config, KEY_CONVERT_TX3G_TO_SRT, True)
    drop_tx3g = _bool_value(config, KEY_DROP_TX3G_AFTER_CONVERSION, False)
    convert_bdpgs = _bool_value(config, KEY_CONVERT_BDPGS_TO_SRT, True)
    drop_bdpgs = _bool_value(config, KEY_DROP_BDPGS_AFTER_CONVERSION, False)
    convert_vobsub = _bool_value(config, KEY_CONVERT_VOBSUB_TO_SRT, False)
    drop_vobsub = _bool_value(config, KEY_DROP_VOBSUB_AFTER_CONVERSION, False)
    drop_ass = _bool_value(config, KEY_DROP_ASS_AFTER_CONVERSION, False)
    size_guard = _text_value(config, KEY_SIZE_GUARD_MODE, "advisory").casefold() or "advisory"
    output_container = _text_value(config, KEY_OUTPUT_CONTAINER, "mkv").casefold() or "mkv"
    routing_profile = _text_value(config, KEY_ROUTING_PROFILE, "default") or "default"
    allow_h264_copy = _bool_value(config, KEY_ALLOW_H264_REMUX_IF_PLEX_COMPATIBLE, True)
    remux_safe_codecs = _list_value(config, KEY_REMUX_SAFE_VIDEO_CODECS, [])
    extra_video_flags = _list_value(config, KEY_EXTRA_VIDEO_FLAGS, [])
    source_movies = _text_value(config, KEY_SOURCE_MOVIES, "")
    source_tv = _text_value(config, KEY_SOURCE_TV, "")
    scratch = _text_value(config, KEY_LOCAL_BASE, "")
    output = _text_value(config, KEY_OUTSOURCE, "")

    max_growth = _display_text(_config_value(config, KEY_MAX_ENCODE_GROWTH_PERCENT, "default"))
    compat_growth = _display_text(_config_value(config, KEY_COMPATIBILITY_ENCODE_GROWTH_PERCENT, "default"))
    movie_threshold = _display_text(_config_value(config, KEY_ENCODE_THRESHOLD_GB, "default"))
    tv_threshold = _display_text(_config_value(config, KEY_TV_ENCODE_THRESHOLD_GB, "default"))
    movie_route_max_bitrate = _display_text(_config_value(config, KEY_MOVIE_ROUTE_MAX_VIDEO_BITRATE_MBPS, "35"))
    tv_route_max_bitrate = _display_text(_config_value(config, KEY_TV_ROUTE_MAX_VIDEO_BITRATE_MBPS, "18"))
    h264_max_bitrate = _display_text(_config_value(config, KEY_H264_REMUX_MAX_BITRATE_MBPS, "default"))
    h264_max_height = _display_text(_config_value(config, KEY_H264_REMUX_MAX_HEIGHT, "default"))
    encode_tuning = _display_text(_config_value(config, KEY_ENCODE_TUNING_PRESET, "default")) or "default"
    encode_ladder = _display_text(_config_value(config, KEY_ENCODE_LADDER, "default")) or "default"
    video_codec = _display_text(_config_value(config, KEY_VIDEO_CODEC, "default")) or "default"

    rows: list[dict[str, Any]] = []
    _launch_risk_row(
        rows,
        "Backend settings risk",
        "blocked" if errors or highest == "critical" else "high review" if highest == "high" else "review" if total or warnings else "ready",
        f"highest={risk.get('highest_severity') or 'none'}; risk items={total}; warnings={len(warnings)}; errors={len(errors)}",
        "Use Settings > Validate / Reload and resolve critical settings before launch."
        if errors or highest == "critical"
        else "Review backend risk preview before unattended starts; backend launch validation still has final authority."
        if total or warnings
        else "No saved-settings risk items currently reported.",
        [
            "Proof source: backend settings workspace and risk summary loaded into the WebView.",
            "Operator proof: Settings Validate/Preview responses should agree with this row before unattended starts.",
            "Boundary: this Launch page row cannot save settings or modify the active PSD1.",
        ],
    )
    _launch_risk_row(
        rows,
        "Backend media-policy readiness",
        "blocked" if "blocked" in readiness_status else "review" if "review" in readiness_status else "ready" if readiness_rows else "review",
        f"schema={readiness.get('schema_version') or 'missing'}; rows={len(readiness_rows)}; coherent={readiness_counts.get('coherent', 0)}; review={readiness_counts.get('review', 0)}; blocked={readiness_counts.get('blocked', 0)}",
        "Resolve blocked saved media-policy rows before launching unattended work."
        if "blocked" in readiness_status
        else "Review backend-authored media-policy readiness rows in Settings before long runs."
        if "review" in readiness_status
        else "Saved media-policy readiness is clean in the backend workspace.",
        [
            "Proof source: backend media_policy_readiness payload from the Settings workspace.",
            "Operator proof: compare Settings media-policy readiness with Launch Active Media Policy Boundary.",
            "Boundary: this is a pre-launch posture check, not proof of a specific media route.",
        ],
    )
    _launch_risk_row(
        rows,
        "Source / scratch / output roots",
        "review" if (not source_movies and not source_tv) or not scratch or not output else "ready",
        f"movies={source_movies or '(empty)'}; tv={source_tv or '(empty)'}; scratch={scratch or '(empty)'}; output={output or '(empty)'}",
        "Confirm nested source folders, scratch, and output roots are intentional. Launch never owns source mutation; pipeline should copy to scratch.",
        [
            "Proof source: saved path settings only.",
            "Operator proof: verify queue discovery and scratch-copy evidence during the first real-media sample run.",
            "Boundary: source/output/scratch validation and copy behavior remain backend-owned.",
        ],
    )
    _launch_risk_row(
        rows,
        "Stability / integrity gates",
        "high review" if stability_skipped or not integrity else "ready",
        f"stability={'skipped' if stability_skipped else 'enabled'}; integrity={'enabled' if integrity else 'disabled'}",
        "Avoid active torrent/download folders and network shares until this is intentional."
        if stability_skipped or not integrity
        else "Stability and integrity gates are visible as enabled for launch posture.",
        [
            "Proof source: saved stability and integrity settings.",
            "Operator proof: watch Diagnostics and Queue row evidence for locked, partial, or still-writing files.",
            "Boundary: this row does not probe files or override backend stability checks.",
        ],
    )
    _launch_risk_row(
        rows,
        "Publish / pending-drain posture",
        "review" if deferred else "ready",
        f"deferred publish={'enabled' if deferred else 'disabled'}; launch mode={{launch_mode}}",
        "Expect completed outputs to park for Pending Publish; monitor Pending Publish and drain evidence after processing."
        if deferred
        else "Completed outputs are not expected to park because deferred publish is disabled.",
        [
            "Proof source: saved DeferredPublish setting and selected launch mode.",
            "Operator proof: verify Pending Publish table and Completed row proof after a sample run.",
            "Boundary: this row cannot drain, publish, or clean pending-publish artifacts.",
        ],
        context_placeholders=["launch_mode"],
    )
    _launch_risk_row(
        rows,
        "Remux / encode size posture",
        "review" if size_guard in {"off", "disabled", "strict"} or extra_video_flags else "ready",
        f"routing={routing_profile}; output_size_check={size_guard}; normal growth={max_growth}%; compatibility growth={compat_growth}%; movie>{movie_threshold}GB/{movie_route_max_bitrate}Mbps; TV>{tv_threshold}GB/{tv_route_max_bitrate}Mbps; codec={video_codec}; tuning={encode_tuning}; ladder={encode_ladder}; legacy flags={len(extra_video_flags)}",
        "Output Size Check is not enforcing or warning normally; confirm this before testing low-bitrate sources that can balloon."
        if size_guard in {"off", "disabled"}
        else "Use Settings Preview before long runs if route, growth limits, encoder, or output container differs from the intended Plex direct/stream profile.",
        [
            "Proof source: saved routing profile, Output Size Check mode, thresholds, encoder choice, ladder, and legacy flags.",
            "Operator proof: compare Completed source/output size evidence after the first sample file.",
            "Boundary: this is not a media-policy change and does not force remux or encode.",
        ],
    )
    _launch_risk_row(
        rows,
        "H.264 copy / remux precision",
        "review" if not allow_h264_copy or not remux_safe_codecs else "ready",
        f"H.264 copy={'enabled' if allow_h264_copy else 'disabled'} <={h264_max_bitrate}Mbps/{h264_max_height}p; remux-safe codecs={', '.join(remux_safe_codecs) or '(empty)'}",
        "Plex-compatible H.264 sources should remain copy/remux candidates when bitrate, height, and codec policy allow it."
        if allow_h264_copy
        else "Compatible H.264 sources may encode instead of copy; review this before large batches or low-bitrate release groups.",
        [
            "Proof source: saved H.264 copy/remux limits and safe codec list.",
            "Operator proof: inspect Queue route evidence for low-bitrate H.264 samples before trusting a large batch.",
            "Boundary: route calculation remains backend/PowerShell-owned.",
        ],
    )
    _launch_risk_row(
        rows,
        "Container / original subtitle preservation",
        "review" if output_container == "mp4" and (not drop_bdpgs or not drop_vobsub or not drop_ass) else "ready",
        f"container={output_container}; TX3G drop={'on' if drop_tx3g else 'off'}; BDPGS drop={'on' if drop_bdpgs else 'off'}; VobSub drop={'on' if drop_vobsub else 'off'}; ASS drop={'on' if drop_ass else 'off'}",
        "MP4 cannot carry every original subtitle format. Confirm backend routing externalizes or drops unsupported tracks deliberately instead of misboxing them."
        if output_container == "mp4"
        else "MKV remains the safer container for preserving original subtitle/audio streams while adding Plex-friendly SRT.",
        [
            "Proof source: saved output container and original-subtitle drop toggles.",
            "Operator proof: validate output container, subtitle streams, and sidecar SRT evidence on a real sample.",
            "Boundary: this row cannot mux, externalize, or drop streams.",
        ],
    )
    subtitle_blocked = (
        (drop_tx3g and not convert_tx3g)
        or (drop_bdpgs and not convert_bdpgs)
        or (drop_vobsub and not convert_vobsub)
    )
    _launch_risk_row(
        rows,
        "Subtitle SRT routing",
        "blocked" if subtitle_blocked else "review" if (not convert_tx3g or not convert_bdpgs or not convert_vobsub or drop_tx3g or drop_bdpgs or drop_vobsub) else "ready",
        f"TX3G convert={'on' if convert_tx3g else 'off'} drop={'on' if drop_tx3g else 'off'}; BDPGS OCR={'on' if convert_bdpgs else 'off'} drop={'on' if drop_bdpgs else 'off'}; VobSub OCR={'on' if convert_vobsub else 'off'} drop={'on' if drop_vobsub else 'off'}",
        "Do not launch media work with drop-without-convert subtitle contradictions."
        if subtitle_blocked
        else "Preferred-language non-SRT subtitles should create SRT while originals stay unless drop toggles are intentional.",
        [
            "Proof source: saved TX3G/BDPGS/VobSub conversion and drop toggles.",
            "Operator proof: confirm SRT creation and original subtitle preservation on a known subtitle sample.",
            "Boundary: subtitle OCR/conversion failures still require backend manual-review classification.",
        ],
    )
    _launch_risk_row(
        rows,
        "Audio predictability",
        "blocked" if allow_no_audio else "ready",
        f"allow no-audio={'enabled' if allow_no_audio else 'disabled'}; passthrough={_display_text(_config_value(config, KEY_AUDIO_PASSTHROUGH_PROFILE, 'default')) or 'default'}; max channels={_display_text(_config_value(config, KEY_AUDIO_MAX_CHANNELS, 'default')) or 'default'}",
        "No-audio output is unsafe for normal Plex publishing; review Settings before launch."
        if allow_no_audio
        else "No-audio output is not allowed by saved settings.",
        [
            "Proof source: saved audio passthrough and no-audio settings.",
            "Operator proof: inspect Completed audio proof and Plex playback behavior for the first sample output.",
            "Boundary: this row cannot select, transcode, downmix, or publish audio tracks.",
        ],
    )
    _launch_risk_row(
        rows,
        "Tool resolution",
        "review" if allow_system_tools else "ready",
        f"PATH fallback={'enabled' if allow_system_tools else 'disabled'}",
        "PATH fallback can use non-bundled tools; confirm this before unattended runs."
        if allow_system_tools
        else "Bundled tool preference remains visible; backend launch validation still resolves executables.",
        [
            "Proof source: saved tool-resolution policy.",
            "Operator proof: backend launch validation and Diagnostics should show resolved tool paths if a tool issue occurs.",
            "Boundary: this row cannot change PATH or select executables.",
        ],
    )
    _launch_risk_row(
        rows,
        "Real-media validation boundary",
        "ready",
        "Preview/build/release gates do not prove FFmpeg, subtitle, audio, sidecar, size, or publish behavior on a specific media file.",
        "After start, confirm real output proof in Diagnostics, Completed, and Pending Publish before trusting unattended batches.",
        [
            "Proof source: selected launch mode and visible shell readiness only.",
            "Operator proof: complete a small known batch and compare route, subtitle, audio, sidecar, size, and publish evidence.",
            "Boundary: WebView preview/build/smoke success is not proof of media processing correctness.",
        ],
        launch_context={
            "validate": {
                "impact": "review",
                "action": "Validate mode is useful for config posture only; follow with a small real Run Once before treating WebView as daily-driver ready.",
            },
            "default": {
                "impact": "ready",
                "action": "After start, confirm real output proof in Diagnostics, Completed, and Pending Publish before trusting unattended batches.",
            },
        },
    )
    for item in risk_items[:3]:
        if not isinstance(item, dict):
            continue
        severity = str(item.get("severity") or "review").casefold()
        _launch_risk_row(
            rows,
            f"Risk item: {item.get('key') or item.get('code') or 'setting'}",
            "blocked" if severity == "critical" else "high review" if severity == "high" else "review",
            f"{item.get('code') or 'risk'}: {item.get('message') or 'Review saved setting.'}",
            "Use Settings Preview/Save or Diagnostics before launch if this risk is unexpected.",
            [
                f"Backend risk code: {item.get('code') or 'unknown'}",
                f"Setting key: {item.get('key') or 'unknown'}",
                "Proof source: backend settings risk item.",
                "Boundary: this row explains backend risk; it does not suppress or accept the risk.",
            ],
        )

    continuous_mode_row = {
        "key": "continuous-mode-sensitivity",
        "area": "Continuous-mode sensitivity",
        "impact": "high review",
        "evidence": "Launch mode is Continuous and at least one saved setting row needs review.",
        "action": "Prefer Validate or Run Once until saved settings risk is understood.",
        "detail": [
            "Proof source: selected Continuous mode plus at least one non-ready launch risk row.",
            "Operator proof: resolve or intentionally accept review rows before unattended continuous processing.",
            "Boundary: backend launch validation still has final authority over whether Continuous can start.",
        ],
        "source": "backend",
    }
    rows.sort(key=lambda row: {"blocked": 0, "high review": 1, "review": 2}.get(str(row.get("impact") or "").casefold(), 3))
    return {
        "schema_version": "settings_launch_risk_handoff.v1",
        "evidence_authority": "backend",
        "source_route": "/api/settings/workspace",
        "read_only": True,
        "status": _launch_risk_status(rows),
        "counts": _launch_risk_counts(rows),
        "total_count": len(rows),
        "rows": rows,
        "continuous_mode_row": continuous_mode_row,
        "summary_lines": _launch_risk_summary_lines(rows),
    }


def build_settings_policy_impact(
    config: dict[str, Any],
    *,
    risk_summary: dict[str, Any] | None = None,
    media_policy_readiness: dict[str, Any] | None = None,
    errors: list[str] | None = None,
    warnings: list[str] | None = None,
) -> dict[str, Any]:
    """Return backend-authored policy/risk display DTOs for WebView renderers."""
    readiness = media_policy_readiness or build_media_policy_readiness(config)
    launch_handoff = build_launch_settings_risk_handoff(
        config,
        risk_summary=risk_summary,
        media_policy_readiness=readiness,
        errors=errors,
        warnings=warnings,
    )
    return {
        "schema_version": "settings_policy_impact.v1",
        "evidence_authority": "backend",
        "source_route": "/api/settings/workspace",
        "read_only": True,
        "media_policy_readiness": readiness,
        "launch_risk_handoff": launch_handoff,
        "summary_lines": [
            "Settings policy impact:",
            "Backend-authored saved-policy readiness and launch risk rows are read-only DTOs for WebView rendering.",
            "Settings Preview Patch, Save Patch, backend launch validation, and PowerShell media policy remain authoritative.",
        ],
    }


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
    vobsub_languages = _list_value(config, KEY_VOBSUB_EXTRACT_LANGUAGES, ["eng", "und"])
    convert_tx3g = _bool_value(config, KEY_CONVERT_TX3G_TO_SRT, True)
    drop_tx3g = _bool_value(config, KEY_DROP_TX3G_AFTER_CONVERSION, False)
    tx3g_sidecars = _bool_value(config, KEY_CREATE_EXTERNAL_TX3G_SRT_SIDECARS, False)
    convert_bdpgs = _bool_value(config, KEY_CONVERT_BDPGS_TO_SRT, True)
    drop_bdpgs = _bool_value(config, KEY_DROP_BDPGS_AFTER_CONVERSION, False)
    convert_vobsub = _bool_value(config, KEY_CONVERT_VOBSUB_TO_SRT, False)
    drop_vobsub = _bool_value(config, KEY_DROP_VOBSUB_AFTER_CONVERSION, False)
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
            "Routing / Output Size Check",
            size_posture,
            f"profile={routing_profile}; output_size_check={size_guard}; normal_growth={_int_text(max_growth)}%; compatibility_growth={_int_text(compat_growth)}%",
            "Keep Output Size Check warn-only or fail-job for unattended Plex batches; off or non-positive growth caps can allow oversized encodes without a clear hold point.",
            [KEY_ROUTING_PROFILE, KEY_SIZE_GUARD_MODE, KEY_MAX_ENCODE_GROWTH_PERCENT, KEY_COMPATIBILITY_ENCODE_GROWTH_PERCENT],
        )
    )

    mp4_preserves_incompatible = output_container.casefold() == "mp4" and (not drop_bdpgs or not drop_vobsub or not drop_ass)
    rows.append(
        _readiness_row(
            "Container / subtitle preservation",
            "review" if mp4_preserves_incompatible else "coherent",
            f"container={output_container}; drop_ass={drop_ass}; drop_bdpgs={drop_bdpgs}; drop_vobsub={drop_vobsub}; drop_tx3g={drop_tx3g}; tx3g_sidecars={tx3g_sidecars}",
            "MKV is the safest preservation container. If MP4 is selected, verify unsupported original subtitle types are externalized or deliberately dropped instead of misboxed.",
            [KEY_OUTPUT_CONTAINER, KEY_DROP_ASS_AFTER_CONVERSION, KEY_DROP_BDPGS_AFTER_CONVERSION, KEY_DROP_VOBSUB_AFTER_CONVERSION, KEY_DROP_TX3G_AFTER_CONVERSION, KEY_CREATE_EXTERNAL_TX3G_SRT_SIDECARS],
        )
    )

    tx3g_gaps = _language_gaps(keep_languages, tx3g_languages)
    bdpgs_gaps = _language_gaps(keep_languages, bdpgs_languages)
    vobsub_gaps = _language_gaps(keep_languages, vobsub_languages)
    rows.append(
        _readiness_row(
            "Subtitle language routing",
            "review" if not keep_languages or tx3g_gaps or bdpgs_gaps or vobsub_gaps else "coherent",
            f"keep={', '.join(keep_languages) or '(empty)'}; tx3g={', '.join(tx3g_languages) or '(empty)'}; bdpgs={', '.join(bdpgs_languages) or '(empty)'}; vobsub={', '.join(vobsub_languages) or '(empty)'}",
            "Preferred subtitle language drives SRT generation; keep TX3G/BDPGS/VobSub extract languages aligned unless extract-only language gaps are intentional.",
            [KEY_SUB_KEEP_LANGUAGES, KEY_TX3G_EXTRACT_LANGUAGES, KEY_BDPGS_EXTRACT_LANGUAGES, KEY_VOBSUB_EXTRACT_LANGUAGES],
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
            "VobSub OCR to SRT",
            "blocked" if drop_vobsub and not convert_vobsub else "review" if (not convert_vobsub or drop_vobsub) else "coherent",
            f"ocr={convert_vobsub}; drop_original={drop_vobsub}",
            "Preferred-language VobSub should OCR to SRT for Plex clients, external .idx/.sub pairs should remain untouched, and OCR failures should remain visible for manual review.",
            [KEY_CONVERT_VOBSUB_TO_SRT, KEY_DROP_VOBSUB_AFTER_CONVERSION, KEY_VOBSUB_OCR_TOOL_PATH],
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
