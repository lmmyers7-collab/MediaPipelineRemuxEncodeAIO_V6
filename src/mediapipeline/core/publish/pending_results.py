from __future__ import annotations

from typing import Any

from .pending_contracts import (
    PENDING_DRAIN_CONFIDENCE_SCHEMA_VERSION,
    PENDING_FILE_INVENTORY_SCHEMA_VERSION,
    PENDING_PUBLISH_INVALID_RESULT_MESSAGE,
    PENDING_PUBLISH_INVENTORY_PROGRESS_SCHEMA_VERSION,
    PENDING_PUBLISH_OPEN_COMMAND,
    PENDING_PUBLISH_OPEN_TARGETS,
    PENDING_PUBLISH_RECOVERY_PLAN_COMMAND,
    PENDING_PUBLISH_RECOVERY_PLAN_SCHEMA_VERSION,
    PENDING_PUBLISH_SERVICE_UNAVAILABLE_MESSAGE,
    _command_result,
    _json_safe,
    _pending_publish_preview_dto,
)


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
