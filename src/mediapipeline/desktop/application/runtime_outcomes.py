"""Compatibility exports for runtime outcome helpers."""

from __future__ import annotations

from mediapipeline.core.observability.runtime_outcomes import (
    RUNTIME_OUTCOME_EVENT_LIMIT,
    runtime_bool,
    runtime_event_data,
    runtime_event_source_path,
    runtime_int,
    runtime_outcome_from_event,
    runtime_outcome_index,
    runtime_outcome_status,
    source_identity_key,
)

__all__ = [
    "RUNTIME_OUTCOME_EVENT_LIMIT",
    "runtime_bool",
    "runtime_event_data",
    "runtime_event_source_path",
    "runtime_int",
    "runtime_outcome_from_event",
    "runtime_outcome_index",
    "runtime_outcome_status",
    "source_identity_key",
]
