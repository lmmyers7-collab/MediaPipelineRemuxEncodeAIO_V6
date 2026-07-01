"""Compatibility shim for priority marker helpers.

New code should import from ``mediapipeline.core.queue.priority_markers``.
"""

from __future__ import annotations

from mediapipeline.core.queue.priority_markers import (
    remove_priority_markers_from_name,
    sorted_priority_markers,
    starts_with_priority_marker,
)

__all__ = [
    "remove_priority_markers_from_name",
    "sorted_priority_markers",
    "starts_with_priority_marker",
]
