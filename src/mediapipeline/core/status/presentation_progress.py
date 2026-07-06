"""Current-work and progress display helpers."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any
from collections.abc import Mapping, Sequence

from mediapipeline.core.status.events import format_pipeline_event_summary
from mediapipeline.core.status.presentation_labels import (
    current_work_item_label,
    current_work_library_label,
    current_work_percent_label,
    current_work_phase_label,
    current_work_queue_label,
    current_work_queue_position_label,
    current_work_route_label,
    display_library_relative_path,
    structured_status_from_progress,
)

CURRENT_WORK_SCHEMA_VERSION = "desktop_current_work.v1"
NON_ACTIVE_PIPELINE_STATES = {"idle", "completed", "stopped"}
NON_ACTIVE_PROGRESS_STAGES = {"", "idle", "sleeping", "completed", "stopped"}


def _text_from_mapping(mapping: Mapping[str, Any], *keys: str) -> str:
    for key in keys:
        raw = mapping.get(key)
        if raw not in (None, ""):
            text = str(raw).strip()
            if text:
                return text
    return ""


def _int_from_mapping(mapping: Mapping[str, Any], *keys: str) -> int:
    for key in keys:
        raw = mapping.get(key)
        try:
            if raw not in (None, ""):
                return int(float(raw))
        except (TypeError, ValueError):
            continue
    return 0


def _bool_from_mapping(mapping: Mapping[str, Any], *keys: str) -> bool:
    for key in keys:
        raw = mapping.get(key)
        if isinstance(raw, bool):
            return raw
        if raw in (None, ""):
            continue
        text = str(raw).strip().casefold()
        if text in {"1", "true", "yes", "y"}:
            return True
        if text in {"0", "false", "no", "n"}:
            return False
    return False


def _display_words(value: str) -> str:
    text = str(value or "").replace("_", " ").replace("-", " ").strip()
    if not text:
        return ""
    known_upper = {"ASS", "AV", "CPU", "GPU", "HDR", "OCR", "PGS", "SRT", "TV"}
    tokens = []
    for token in text.split():
        upper = token.upper()
        if upper in known_upper:
            tokens.append(upper)
        elif upper == "VOBSUB":
            tokens.append("VobSub")
        elif upper in {"BDPGS", "BD-PGS"}:
            tokens.append("BDPGS")
        else:
            tokens.append(token[:1].upper() + token[1:].lower())
    return " ".join(tokens)


def _mapping_list(values: Sequence[Mapping[str, Any]] | None) -> list[dict[str, Any]]:
    if not isinstance(values, Sequence) or isinstance(values, (str, bytes)):
        return []
    return [dict(item) for item in values if isinstance(item, Mapping)]


def _progress_bar_status(bar: Mapping[str, Any]) -> str:
    if bar.get("stale") is True:
        return "stale"
    return str(bar.get("status") or "").strip().casefold()


def _bar_label(bar: Mapping[str, Any]) -> str:
    label = _text_from_mapping(bar, "label", "id")
    detail = _text_from_mapping(bar, "detail")
    return " | ".join(part for part in (label, detail) if part)


def _format_cues(count: int) -> str:
    if count <= 0:
        return ""
    return f"{count} {'cue' if count == 1 else 'cues'}"


def _subtitle_kind_label(kind: str) -> str:
    normalized = kind.strip().casefold()
    if normalized == "vobsub":
        return "VobSub"
    if normalized in {"bdpgs", "bd-pgs", "pgs"}:
        return "BDPGS"
    return _display_words(kind or "subtitle")


def _subtitle_evidence_label(progress: Mapping[str, Any]) -> str:
    raw = progress.get("SubtitleProgress")
    if not isinstance(raw, Mapping):
        return ""
    kind = _text_from_mapping(raw, "kind", "Kind") or "subtitle"
    kind_label = _subtitle_kind_label(kind)
    stream_index = _text_from_mapping(raw, "stream_index", "StreamIndex")
    stage = _text_from_mapping(raw, "stage", "Stage")
    status = _text_from_mapping(raw, "status", "Status")
    detail = _text_from_mapping(raw, "detail", "Detail")
    cue_count = _int_from_mapping(raw, "cue_count", "CueCount")
    evidence_text = " ".join(str(part or "").casefold() for part in (kind, stage, status, detail))
    action = "OCR" if "ocr" in evidence_text else kind_label
    target_parts = []
    if kind_label and action != kind_label:
        target_parts.append(kind_label)
    if stream_index not in {"", "-1"}:
        target_parts.append(f"stream {stream_index}")
    target = " ".join(target_parts) or "subtitle stream"
    detail_parts = [_format_cues(cue_count)]
    if not detail_parts[0] and detail and "cue" not in detail.casefold():
        detail_parts.append(detail)
    if not any(detail_parts) and status:
        detail_parts.append(status)
    suffix = ", ".join(part for part in detail_parts if part)
    return f"Subtitle {action}: {target}{', ' + suffix if suffix else ''}"


def _audio_evidence_label(progress: Mapping[str, Any]) -> str:
    raw = progress.get("AudioProgress")
    if not isinstance(raw, Mapping):
        return ""
    stream_index = _text_from_mapping(raw, "stream_index", "StreamIndex")
    action = _text_from_mapping(raw, "action", "Action")
    source_codec = _text_from_mapping(raw, "source_codec", "SourceCodec")
    output_codec = _text_from_mapping(raw, "output_codec", "OutputCodec")
    source_channels = _text_from_mapping(raw, "source_channels", "SourceChannels")
    output_channels = _text_from_mapping(raw, "output_channels", "OutputChannels")
    language = _text_from_mapping(raw, "language", "Language")
    reason = _text_from_mapping(raw, "reason", "Reason")
    status = _text_from_mapping(raw, "status", "Status")
    label = f"Audio {_display_words(action) if action else 'policy'}"
    target = f"stream {stream_index}" if stream_index not in {"", "-1"} else ""
    codec = " -> ".join(part for part in (source_codec, output_codec) if part)
    channels = " -> ".join(f"{part}ch" for part in (source_channels, output_channels) if part not in {"", "-1"})
    detail = ", ".join(part for part in (target, codec, channels, language, reason, status) if part)
    return f"{label}: {detail}" if detail else label


def _nested_progress_active(raw: Any) -> bool:
    if not isinstance(raw, Mapping):
        return False
    if _bool_from_mapping(raw, "failed", "Failed"):
        return False
    if _bool_from_mapping(raw, "completed", "Completed"):
        return False
    step_total = _int_from_mapping(raw, "step_total", "StepTotal")
    step_index = _int_from_mapping(raw, "step_index", "StepIndex")
    if step_total > 0 and step_index >= step_total:
        return False
    status = _text_from_mapping(raw, "status", "Status").casefold()
    return not any(token in status for token in ("complete", "completed", "failed", "error", "blocked"))


def _copy_evidence_label(progress: Mapping[str, Any]) -> str:
    copy_state = _text_from_mapping(progress, "CopyState")
    copy_percent = _text_from_mapping(progress, "CopyPercent")
    copied = _text_from_mapping(progress, "CopyBytesCopied")
    total = _text_from_mapping(progress, "CopyTotalBytes")
    parts = []
    if copy_state:
        parts.append(copy_state.replace("_", " "))
    if copy_percent:
        parts.append(f"{copy_percent}%")
    if copied and total:
        parts.append(f"{copied} / {total} bytes")
    if not parts:
        parts.append("waiting for backend evidence")
    return f"Copy to scratch: {' | '.join(parts)}"


def _stage_evidence_label(progress: Mapping[str, Any], *, phase_label: str, route_label: str, percent_label: str) -> str:
    stage = _text_from_mapping(progress, "CurrentStage", "Status").casefold()
    item = current_work_item_label(dict(progress))
    if stage in {"copy", "copy_to_scratch"}:
        return _copy_evidence_label(progress)
    if item and not route_label and stage not in {"idle", "sleeping", "completed", "stopped"}:
        return "Route decision pending: encode/remux decision not reported"
    structured = structured_status_from_progress(dict(progress))
    if structured:
        return structured
    parts = [phase_label if phase_label != "No active work" else "", percent_label, route_label]
    return " · ".join(part for part in parts if part)


def _latest_event_label(events: Sequence[Mapping[str, Any]] | None) -> str:
    rows = _mapping_list(events)
    if not rows:
        return ""
    summaries = format_pipeline_event_summary(rows[-1:], max_items=1)
    return summaries[0] if summaries else ""


def _blocked_label(progress: Mapping[str, Any], bars: Sequence[Mapping[str, Any]] | None) -> str:
    for bar in _mapping_list(bars):
        if _progress_bar_status(bar) == "blocked":
            return f"Blocked: {_bar_label(bar)}".strip()
    status_text = " ".join(
        _text_from_mapping(progress, key)
        for key in ("Status", "CurrentStage", "PushState", "SidecarState")
    ).casefold()
    if any(token in status_text for token in ("blocked", "failed", "error")):
        stage = _text_from_mapping(progress, "CurrentStage", "Status") or "backend work"
        return f"Blocked: {_display_words(stage)}"
    return ""


def _progress_is_non_active(progress: Mapping[str, Any], pipeline_state: str) -> bool:
    state = str(pipeline_state or "").strip().casefold()
    if state not in NON_ACTIVE_PIPELINE_STATES:
        return False
    stage = _text_from_mapping(progress, "CurrentStage").casefold()
    status = _text_from_mapping(progress, "Status").casefold()
    return stage in NON_ACTIVE_PROGRESS_STAGES or status.startswith(("idle", "completed", "stopped"))


def _latest_progress_evidence_label(
    progress: Mapping[str, Any],
    bars: Sequence[Mapping[str, Any]] | None,
    *,
    phase_label: str,
    route_label: str,
    percent_label: str,
) -> str:
    if _nested_progress_active(progress.get("SubtitleProgress")):
        return _subtitle_evidence_label(progress)
    if _nested_progress_active(progress.get("AudioProgress")):
        return _audio_evidence_label(progress)
    subtitle = _subtitle_evidence_label(progress)
    if subtitle:
        return subtitle
    audio = _audio_evidence_label(progress)
    if audio:
        return audio
    for bar in _mapping_list(bars):
        status = _progress_bar_status(bar)
        if status in {"active", "running", "processing", "warning", "review"}:
            label = _bar_label(bar)
            if label:
                return label
    return _stage_evidence_label(progress, phase_label=phase_label, route_label=route_label, percent_label=percent_label)


def _current_stage_label(
    progress: Mapping[str, Any],
    *,
    phase_label: str,
    percent_label: str,
) -> str:
    if _nested_progress_active(progress.get("SubtitleProgress")):
        return _subtitle_evidence_label(progress)
    if _nested_progress_active(progress.get("AudioProgress")):
        return _audio_evidence_label(progress)
    if phase_label and phase_label != "No active work":
        return " ".join(part for part in (phase_label, percent_label) if part)
    stage = _text_from_mapping(progress, "CurrentStage", "Status")
    return _display_words(stage)


def _next_stage_label(progress: Mapping[str, Any], *, route_label: str) -> str:
    if not progress:
        return "progress snapshot evidence"
    stage = _text_from_mapping(progress, "CurrentStage", "Status").casefold()
    if _nested_progress_active(progress.get("SubtitleProgress")):
        return "encode/remux output evidence"
    if _nested_progress_active(progress.get("AudioProgress")):
        return "subtitle or output evidence"
    if stage in {"copy", "copy_to_scratch"}:
        return "route decision evidence"
    if not route_label and stage not in {"idle", "sleeping", "completed", "stopped"}:
        return "encode/remux decision evidence"
    if stage in {"route", "remux_prepare", "encode_prepare"}:
        return "audio/subtitle policy evidence"
    if stage in {"encode", "encode_cpu", "encode_verify", "remux", "remux_av", "remux_mux", "remux_verify"}:
        return "publish or park evidence"
    if stage in {"push", "sidecar", "retry_pending_push"}:
        return "completion evidence"
    return ""


def _missing_evidence_label(
    progress: Mapping[str, Any],
    *,
    pipeline_state: str,
    item_label: str,
    route_label: str,
    latest_evidence_label: str,
) -> str:
    state = str(pipeline_state or "").casefold()
    if state in {"idle", "completed", "stopped"}:
        return ""
    if not progress:
        return "Waiting for backend evidence: progress snapshot"
    if not item_label:
        return "Waiting for backend evidence: current item"
    stage = _text_from_mapping(progress, "CurrentStage", "Status").casefold()
    if not route_label and stage not in {"copy", "copy_to_scratch"}:
        return "Waiting for backend evidence: encode/remux decision"
    if not latest_evidence_label:
        return "Waiting for backend evidence: stage detail"
    return ""


def build_current_work(
    progress: dict[str, Any] | None,
    movie_cleaning_policy: Mapping[str, Any] | None = None,
    *,
    pipeline_events: Sequence[Mapping[str, Any]] | None = None,
    progress_bars: Sequence[Mapping[str, Any]] | None = None,
    pipeline_state: str = "",
) -> dict[str, str]:
    payload = progress if isinstance(progress, dict) else {}
    item_label = current_work_item_label(payload, movie_cleaning_policy)
    phase_label = current_work_phase_label(payload)
    library_label = current_work_library_label(payload)
    queue_label = current_work_queue_label(payload)
    queue_position_label = current_work_queue_position_label(payload)
    route_label = current_work_route_label(payload)
    percent_label = current_work_percent_label(payload)
    latest_evidence_label = _latest_progress_evidence_label(
        payload,
        progress_bars,
        phase_label=phase_label,
        route_label=route_label,
        percent_label=percent_label,
    )
    latest_event_label = _latest_event_label(pipeline_events)
    current_stage_label = _current_stage_label(payload, phase_label=phase_label, percent_label=percent_label)
    next_stage_label = _next_stage_label(payload, route_label=route_label)
    blocked_label = _blocked_label(payload, progress_bars)
    non_active_progress = _progress_is_non_active(payload, pipeline_state)
    if non_active_progress and not blocked_label:
        latest_evidence_label = ""
        next_stage_label = ""
    missing_evidence_label = _missing_evidence_label(
        payload,
        pipeline_state=pipeline_state,
        item_label=item_label,
        route_label=route_label,
        latest_evidence_label=latest_evidence_label,
    )
    summary_label = (
        blocked_label
        or ("" if non_active_progress else latest_evidence_label)
        or (
            ""
            if non_active_progress
            else (f"{current_stage_label}: {item_label}" if current_stage_label and item_label else current_stage_label)
        )
        or missing_evidence_label
        or "No active work reported."
    )
    evidence_status = (
        "blocked"
        if blocked_label
        else "waiting"
        if missing_evidence_label
        else "active"
        if (latest_evidence_label or current_stage_label) and not non_active_progress
        else "idle"
    )
    return {
        "schema_version": CURRENT_WORK_SCHEMA_VERSION,
        "item_label": item_label,
        "phase_label": phase_label,
        "library_label": library_label,
        "queue_label": queue_label,
        "queue_position_label": queue_position_label,
        "route_label": route_label,
        "percent_label": percent_label,
        "summary_label": summary_label,
        "current_stage_label": current_stage_label,
        "next_stage_label": next_stage_label,
        "latest_evidence_label": latest_evidence_label,
        "latest_event_label": latest_event_label,
        "missing_evidence_label": missing_evidence_label,
        "blocked_label": blocked_label,
        "evidence_status": evidence_status,
    }


def build_stale_current_work() -> dict[str, str]:
    return {
        "schema_version": CURRENT_WORK_SCHEMA_VERSION,
        "item_label": "Stale progress from previous run",
        "phase_label": "Review stale progress",
        "library_label": "",
        "queue_label": "",
        "queue_position_label": "",
        "route_label": "",
        "percent_label": "",
        "summary_label": "Review stale progress from previous run",
        "current_stage_label": "Review stale progress",
        "next_stage_label": "fresh backend progress evidence",
        "latest_evidence_label": "",
        "latest_event_label": "",
        "missing_evidence_label": "Waiting for backend evidence: fresh progress snapshot",
        "blocked_label": "Stale progress from previous run",
        "evidence_status": "stale",
    }


def display_current_file(current_file: str) -> str:
    current_file = (current_file or "").strip()
    if not current_file:
        return ""

    queue_prefix = ""
    leaf = current_file
    match = re.match(r"^\[(?P<prefix>[^\]]+)\]\s*(?P<name>.+)$", leaf)
    if match:
        queue_prefix = match.group("prefix").strip()
        leaf = match.group("name").strip()

    leaf_name = Path(leaf).stem if leaf else leaf
    if queue_prefix:
        queue_match = re.match(r"^(Movie|TV)\s+(\d+)/(\d+)$", queue_prefix, re.IGNORECASE)
        if queue_match:
            kind, index, total = queue_match.groups()
            return f"{kind.title()} {index} of {total} | {leaf_name}"
        return f"[{queue_prefix}] {leaf_name}"
    return leaf_name


def display_current_file_from_progress(progress: dict[str, Any]) -> str:
    display = str(progress.get("CurrentFileDisplay", "") or progress.get("CurrentFile", "") or "").strip()
    path_text = str(progress.get("CurrentFilePath", "") or "").strip()
    if (not display or display.casefold() == "none") and not path_text:
        return ""

    queue_phase = str(progress.get("CurrentQueuePhase", "") or "").strip().lower()
    queue_index = int(progress.get("CurrentQueueIndex", 0) or 0)
    queue_total = int(progress.get("CurrentQueueTotal", 0) or 0)
    media_type = str(progress.get("CurrentMediaType", "") or "").strip().lower()

    formatted_path = display_library_relative_path(path_text, media_type)
    if formatted_path:
        leaf = formatted_path
    elif path_text:
        try:
            leaf = Path(path_text).name
        except Exception:
            leaf = display_current_file(display)
    else:
        leaf = display_current_file(display)
    if queue_index > 0 and queue_total > 0:
        media_label = "TV" if media_type == "tv" else "Movie" if media_type == "movie" else media_type.title()
        if queue_phase == "priority":
            if media_type in {"movie", "tv"}:
                return f"Priority {media_label} {queue_index} of {queue_total} | {leaf}"
            return f"Priority {queue_index} of {queue_total} | {leaf}"
        if media_type in {"movie", "tv"}:
            return f"{media_label} {queue_index} of {queue_total} | {leaf}"
    return leaf


__all__ = [
    "CURRENT_WORK_SCHEMA_VERSION",
    "build_current_work",
    "build_stale_current_work",
    "display_current_file",
    "display_current_file_from_progress",
]
