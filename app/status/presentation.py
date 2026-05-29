from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from app.status.events import (
    format_pipeline_event_summary,
    pipeline_event_data,
    pipeline_event_stage_label,
    structured_status_from_pipeline_event,
)


def display_library_relative_path(path_text: str, media_type: str) -> str:
    parts = [segment for segment in re.split(r"[\\/]+", path_text or "") if segment]
    if not parts:
        return ""
    lower_parts = [part.casefold() for part in parts]
    marker = media_type if media_type in {"movie", "tv"} else ""
    if marker and marker in lower_parts:
        index = lower_parts.index(marker)
        remainder = parts[index + 1 :]
        if remainder:
            return "\\".join(remainder)
    if "movies" in lower_parts:
        index = lower_parts.index("movies")
        remainder = parts[index + 1 :]
        if remainder:
            return "\\".join(remainder)
    if "tv" in lower_parts:
        index = lower_parts.index("tv")
        remainder = parts[index + 1 :]
        if remainder:
            return "\\".join(remainder)
    return ""


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


def structured_status_from_progress(progress: dict[str, Any]) -> str:
    stage = str(progress.get("CurrentStage", "") or "").strip().lower()
    route = str(progress.get("CurrentRoute", "") or "").strip().lower()
    copy_state = str(progress.get("CopyState", "") or "").strip().lower()
    push_state = str(progress.get("PushState", "") or "").strip().lower()
    sidecar_state = str(progress.get("SidecarState", "") or "").strip().lower()
    percent_raw = progress.get("CurrentStagePercent")
    percent_text = ""
    try:
        if percent_raw not in ("", None):
            percent_text = f"{int(float(percent_raw))}%"
    except (TypeError, ValueError):
        percent_text = ""

    # encode_cpu gets its own label so the live status tile makes a
    # multi-hour libx265 fallback obvious instead of looking the same
    # as a fast NVENC encode.
    if stage == "encode_cpu":
        return f"encode (CPU) {percent_text}".strip()
    if stage == "encode":
        return f"encode {percent_text}".strip()
    if stage == "remux_av":
        return f"remux {percent_text}".strip()
    if stage == "copy_to_scratch":
        if copy_state == "complete":
            return "copy to scratch complete"
        return "copy to scratch"
    if stage == "remux_prepare":
        return "remux preparation"
    if stage == "remux_mux":
        return "remux mux"
    if stage == "remux_verify":
        return "remux verify"
    if stage == "encode_prepare":
        return "encode preparation"
    if stage == "encode_verify":
        return "encode verify"
    if stage == "push":
        if push_state == "failed":
            return "server push failed"
        if push_state == "deferred":
            return "parked until output space is available"
        if push_state == "complete":
            return "server push complete"
        return "server push"
    if stage == "sidecar":
        if sidecar_state == "failed":
            return "sidecar write failed"
        if sidecar_state == "complete":
            return "sidecar complete"
        return "sidecar write"
    if stage == "retry_pending_push":
        return "publishing parked outputs"
    if stage == "scanning":
        return "scanning sources"
    if stage == "sleeping":
        return "idle / sleeping until next scan"
    if stage == "paused":
        return "paused"
    if stage == "stopped":
        return "stopped"
    if stage == "idle":
        return "idle / waiting for next item"
    if stage == "startup":
        return "initializing"
    if stage == "completed":
        if route:
            return f"{route} complete"
        return "completed"
    return ""


def normalized_status(status: str) -> str:
    cleaned = (status or "").strip()
    if cleaned in ("", "Processing"):
        return ""
    return cleaned.lower()


def activity_from_pipeline_events(events: list[dict[str, Any]]) -> str:
    status_text = status_from_pipeline_events(events)
    file_text = display_current_file_from_pipeline_events(events)
    if file_text and status_text:
        return f"{file_text} | {status_text}"
    return file_text or status_text


def build_current_activity(
    progress: dict[str, Any] | None,
    pipeline_events: list[dict[str, Any]] | None = None,
) -> str:
    events = pipeline_events or []
    if progress:
        file_text = display_current_file_from_progress(progress)
        status_text = structured_status_from_progress(progress)
        if not status_text:
            status_text = normalized_status(str(progress.get("Status", "")))
        if not status_text:
            status_text = status_from_pipeline_events(events)

        if file_text and status_text:
            return f"{file_text} | {status_text}"
        if file_text:
            return file_text
        if status_text:
            return status_text

    event_activity = activity_from_pipeline_events(events)
    if event_activity:
        return event_activity

    return "No active work reported."


def status_from_pipeline_events(events: list[dict[str, Any]]) -> str:
    for event in reversed(events):
        status_text = structured_status_from_pipeline_event(event)
        if status_text:
            return status_text
    return ""


def display_current_file_from_pipeline_events(events: list[dict[str, Any]]) -> str:
    for event in reversed(events):
        data = pipeline_event_data(event)
        display = str(data.get("display_name", "") or "").strip()
        if display:
            return display_current_file(display)

        path_text = str(
            event.get("source_path", "")
            or data.get("source_path", "")
            or data.get("local_file", "")
            or data.get("server_out", "")
            or ""
        ).strip()
        if not path_text:
            continue

        media_type = str(data.get("media_type", "") or "").strip().lower()
        formatted_path = display_library_relative_path(path_text, media_type)
        if formatted_path:
            return formatted_path

        leaf = re.split(r"[\\/]+", path_text)[-1]
        return display_current_file(leaf)
    return ""
