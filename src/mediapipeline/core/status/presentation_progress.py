"""Current-work and progress display helpers."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Mapping

from mediapipeline.core.status.presentation_labels import (
    current_work_item_label,
    current_work_library_label,
    current_work_percent_label,
    current_work_phase_label,
    current_work_queue_label,
    current_work_queue_position_label,
    current_work_route_label,
    display_library_relative_path,
)

CURRENT_WORK_SCHEMA_VERSION = "desktop_current_work.v1"


def build_current_work(
    progress: dict[str, Any] | None,
    movie_cleaning_policy: Mapping[str, Any] | None = None,
) -> dict[str, str]:
    payload = progress if isinstance(progress, dict) else {}
    return {
        "schema_version": CURRENT_WORK_SCHEMA_VERSION,
        "item_label": current_work_item_label(payload, movie_cleaning_policy),
        "phase_label": current_work_phase_label(payload),
        "library_label": current_work_library_label(payload),
        "queue_label": current_work_queue_label(payload),
        "queue_position_label": current_work_queue_position_label(payload),
        "route_label": current_work_route_label(payload),
        "percent_label": current_work_percent_label(payload),
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
    "display_current_file",
    "display_current_file_from_progress",
]
