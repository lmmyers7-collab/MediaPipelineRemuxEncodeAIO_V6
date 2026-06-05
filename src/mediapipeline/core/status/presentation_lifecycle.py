"""Lifecycle and current activity presentation helpers."""

from __future__ import annotations

import re
from typing import Any

from mediapipeline.core.status.events import (
    pipeline_event_data,
    structured_status_from_pipeline_event,
)
from mediapipeline.core.status.presentation_labels import display_library_relative_path, structured_status_from_progress
from mediapipeline.core.status.presentation_progress import display_current_file, display_current_file_from_progress


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


__all__ = [
    "normalized_status",
    "activity_from_pipeline_events",
    "build_current_activity",
    "status_from_pipeline_events",
    "display_current_file_from_pipeline_events",
]
