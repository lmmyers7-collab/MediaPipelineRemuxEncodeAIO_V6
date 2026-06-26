"""Status presentation compatibility facade."""

from __future__ import annotations

from mediapipeline.core.status.events import (
    format_pipeline_event_summary,
    pipeline_event_data,
    pipeline_event_stage_label,
    structured_status_from_pipeline_event,
)
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
from mediapipeline.core.status.presentation_lifecycle import (
    activity_from_pipeline_events,
    build_current_activity,
    display_current_file_from_pipeline_events,
    normalized_status,
    status_from_pipeline_events,
)
from mediapipeline.core.status.presentation_progress import (
    CURRENT_WORK_SCHEMA_VERSION,
    build_current_work,
    build_stale_current_work,
    display_current_file,
    display_current_file_from_progress,
)

__all__ = [
    "CURRENT_WORK_SCHEMA_VERSION",
    "activity_from_pipeline_events",
    "build_current_activity",
    "build_current_work",
    "build_stale_current_work",
    "current_work_item_label",
    "current_work_library_label",
    "current_work_percent_label",
    "current_work_phase_label",
    "current_work_queue_label",
    "current_work_queue_position_label",
    "current_work_route_label",
    "display_current_file",
    "display_current_file_from_pipeline_events",
    "display_current_file_from_progress",
    "display_library_relative_path",
    "format_pipeline_event_summary",
    "normalized_status",
    "pipeline_event_data",
    "pipeline_event_stage_label",
    "status_from_pipeline_events",
    "structured_status_from_pipeline_event",
    "structured_status_from_progress",
]
