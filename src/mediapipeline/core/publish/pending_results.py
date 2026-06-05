from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from mediapipeline.desktop.application.dto_commands import CommandResult
    from mediapipeline.desktop.application.dto_inventory import PendingPublishPreviewDto

PENDING_PUBLISH_SERVICE_UNAVAILABLE_MESSAGE = "Pending publish service is not available."

PENDING_PUBLISH_INVALID_RESULT_MESSAGE = "Pending publish service returned an invalid result."

PENDING_PUBLISH_OPEN_COMMAND = "pending_publish.open"

PENDING_PUBLISH_RECOVERY_PLAN_COMMAND = "pending_publish.recovery_plan_dry_run"

PENDING_PUBLISH_RECOVERY_PLAN_SCHEMA_VERSION = "pending_publish_recovery_plan.v1"

PENDING_PUBLISH_INVENTORY_PROGRESS_SCHEMA_VERSION = "desktop_pending_publish_inventory_progress.v1"

PENDING_DRAIN_CONFIDENCE_SCHEMA_VERSION = "desktop_pending_drain_confidence.v1"

PENDING_FILE_INVENTORY_SCHEMA_VERSION = "desktop_pending_publish_file_inventory.v1"

PENDING_PUBLISH_OPEN_TARGETS = {
    "local_file": "parked local payload",
    "manifest": "pending manifest",
    "destination_folder": "destination folder",
    "source_folder": "source folder",
}

def _json_safe(value: Any) -> Any:
    from mediapipeline.desktop.application.dto_base import json_safe

    return json_safe(value)


def _command_result(**fields: Any) -> "CommandResult":
    from mediapipeline.desktop.application.dto_commands import CommandResult

    return CommandResult(**fields)


def _pending_publish_preview_dto(**fields: Any) -> "PendingPublishPreviewDto":
    from mediapipeline.desktop.application.dto_inventory import PendingPublishPreviewDto

    return PendingPublishPreviewDto(**fields)


def pending_publish_service_unavailable_result() -> PendingPublishPreviewDto:
    from .pending_rows import pending_publish_file_inventory_payload, pending_publish_inventory_progress_payload

    progress = pending_publish_inventory_progress_payload(
        rows_loaded=0,
        rows_scanned=0,
        status="blocked",
        detail=PENDING_PUBLISH_SERVICE_UNAVAILABLE_MESSAGE,
    )
    return _pending_publish_preview_dto(
        file_inventory=pending_publish_file_inventory_payload(
            None,
            status="unavailable",
            error=PENDING_PUBLISH_SERVICE_UNAVAILABLE_MESSAGE,
        ),
        inventory_progress=progress,
        progress_bars=progress["progress_bars"],
        warnings=[PENDING_PUBLISH_SERVICE_UNAVAILABLE_MESSAGE],
    )


def pending_publish_scan_exception_result(pending_root: Any, exists: bool, error: Exception) -> PendingPublishPreviewDto:
    from .pending_rows import pending_publish_scan_exception_fields

    return _pending_publish_preview_dto(
        **pending_publish_scan_exception_fields(pending_root, exists, error)
    )


def pending_publish_invalid_result() -> PendingPublishPreviewDto:
    from .pending_rows import pending_publish_file_inventory_payload, pending_publish_inventory_progress_payload

    progress = pending_publish_inventory_progress_payload(
        rows_loaded=0,
        rows_scanned=0,
        status="blocked",
        detail=PENDING_PUBLISH_INVALID_RESULT_MESSAGE,
    )
    return _pending_publish_preview_dto(
        file_inventory=pending_publish_file_inventory_payload(
            None,
            status="blocked",
            error=PENDING_PUBLISH_INVALID_RESULT_MESSAGE,
        ),
        inventory_progress=progress,
        progress_bars=progress["progress_bars"],
        warnings=[PENDING_PUBLISH_INVALID_RESULT_MESSAGE],
    )


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
    "pending_publish_service_unavailable_result",
    "pending_publish_scan_exception_result",
    "pending_publish_invalid_result",
]
