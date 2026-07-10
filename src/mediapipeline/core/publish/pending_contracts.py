from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from mediapipeline.core.kernel.dto_commands import CommandResult
    from mediapipeline.core.kernel.dto_inventory import PendingPublishPreviewDto

PENDING_PUBLISH_SERVICE_UNAVAILABLE_MESSAGE = "Pending publish service is not available."

PENDING_PUBLISH_INVALID_RESULT_MESSAGE = "Pending publish service returned an invalid result."

PENDING_PUBLISH_OPEN_COMMAND = "pending_publish.open"

PENDING_PUBLISH_RECOVERY_PLAN_COMMAND = "pending_publish.recovery_plan_dry_run"

PENDING_PUBLISH_RECOVERY_PLAN_SCHEMA_VERSION = "pending_publish_recovery_plan.v1"

PENDING_PUBLISH_INVENTORY_PROGRESS_SCHEMA_VERSION = "desktop_pending_publish_inventory_progress.v1"

PENDING_DRAIN_CONFIDENCE_SCHEMA_VERSION = "desktop_pending_drain_confidence.v1"

PENDING_FILE_INVENTORY_SCHEMA_VERSION = "desktop_pending_publish_file_inventory.v1"

PENDING_PUBLISH_OPEN_TARGETS = {
    "play_local_file": "parked output playback",
    "local_file": "parked local payload",
    "manifest": "pending manifest",
    "destination_folder": "destination folder",
    "source_folder": "source folder",
}


def int_value(value: Any) -> int:
    try:
        if value not in (None, ""):
            return int(float(value))
    except (TypeError, ValueError):
        return 0
    return 0


def _json_safe(value: Any) -> Any:
    from mediapipeline.core.kernel.dto_base import json_safe

    return json_safe(value)


def _command_result(**fields: Any) -> CommandResult:
    from mediapipeline.core.kernel.dto_commands import CommandResult

    return CommandResult(**fields)


def _pending_publish_preview_dto(**fields: Any) -> PendingPublishPreviewDto:
    from mediapipeline.core.kernel.dto_inventory import PendingPublishPreviewDto

    return PendingPublishPreviewDto(**fields)


__all__ = [
    "PENDING_PUBLISH_SERVICE_UNAVAILABLE_MESSAGE",
    "PENDING_PUBLISH_INVALID_RESULT_MESSAGE",
    "PENDING_PUBLISH_OPEN_COMMAND",
    "PENDING_PUBLISH_RECOVERY_PLAN_COMMAND",
    "PENDING_PUBLISH_RECOVERY_PLAN_SCHEMA_VERSION",
    "PENDING_PUBLISH_INVENTORY_PROGRESS_SCHEMA_VERSION",
    "PENDING_DRAIN_CONFIDENCE_SCHEMA_VERSION",
    "PENDING_FILE_INVENTORY_SCHEMA_VERSION",
    "PENDING_PUBLISH_OPEN_TARGETS",
    "int_value",
    "_json_safe",
    "_command_result",
    "_pending_publish_preview_dto",
]
