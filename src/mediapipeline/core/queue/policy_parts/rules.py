"""Queue policy constants and rule definitions."""

from __future__ import annotations

from mediapipeline.core.observability.runtime_outcomes import RUNTIME_OUTCOME_EVENT_LIMIT

NO_QUEUE_SNAPSHOT_WARNING = "No queue snapshot is available yet."
QUEUE_PREVIEW_SERVICE_WARNING = "Queue preview service is not available."
INVALID_QUEUE_SNAPSHOT_WARNING = "Queue snapshot is missing or invalid."
EMPTY_QUEUE_SNAPSHOT_WARNING = "Queue snapshot contains no runnable rows."
QUEUE_SNAPSHOT_STALE_AFTER_SECONDS = 3600
QUEUE_RUNTIME_OUTCOME_EVENT_LIMIT = RUNTIME_OUTCOME_EVENT_LIMIT
QUEUE_SOURCE_SCAN_PROGRESS_SCHEMA_VERSION = "desktop_queue_source_scan_progress.v1"
QUEUE_OPEN_COMMAND = "queue.open"
QUEUE_REFRESH_HINT = "queue"
QUEUE_OPEN_TARGETS = {
    "source_file": "queue source file",
    "source_folder": "queue source folder",
    "source_root": "queue source root",
}
QUEUE_OPEN_SCOPES = {
    "runnable": "runnable queue row",
    "excluded": "excluded source row",
}

__all__ = [
    "NO_QUEUE_SNAPSHOT_WARNING",
    "QUEUE_PREVIEW_SERVICE_WARNING",
    "INVALID_QUEUE_SNAPSHOT_WARNING",
    "EMPTY_QUEUE_SNAPSHOT_WARNING",
    "QUEUE_SNAPSHOT_STALE_AFTER_SECONDS",
    "QUEUE_RUNTIME_OUTCOME_EVENT_LIMIT",
    "QUEUE_SOURCE_SCAN_PROGRESS_SCHEMA_VERSION",
    "QUEUE_OPEN_COMMAND",
    "QUEUE_REFRESH_HINT",
    "QUEUE_OPEN_TARGETS",
    "QUEUE_OPEN_SCOPES",
]

