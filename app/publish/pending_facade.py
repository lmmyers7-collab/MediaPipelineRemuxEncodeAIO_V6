from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from mediapipeline_desktop_app.application.dto_commands import CommandResult
    from mediapipeline_desktop_app.application.dto_inventory import PendingPublishPreviewDto
    from mediapipeline_desktop_app.models import ResolvedPaths

from .pending_policy import (
    PENDING_PUBLISH_OPEN_TARGETS,
    normalize_pending_publish_open_target,
    normalize_pending_publish_row_key,
    pending_publish_invalid_result,
    pending_publish_open_disallowed_target_result,
    pending_publish_open_exception_result,
    pending_publish_open_missing_path_result,
    pending_publish_open_missing_row_result,
    pending_publish_open_path,
    pending_publish_open_scan_exception_result,
    pending_publish_open_scan_service_unavailable_result,
    pending_publish_open_service_unavailable_result,
    pending_publish_open_success_result,
    pending_publish_preview_result,
    pending_publish_recovery_plan_invalid_scan_result,
    pending_publish_recovery_plan_result,
    pending_publish_recovery_plan_scan_exception_result,
    pending_publish_recovery_plan_service_unavailable_result,
    pending_publish_row_key,
    pending_publish_rows,
    pending_publish_scan_exception_result,
    pending_publish_service_unavailable_result,
)


class PendingPublishFacadeMixin:
    """Read-only pending-publish adapter for the application facade."""

    def get_pending_publish_preview(self, resolved: ResolvedPaths) -> PendingPublishPreviewDto:
        scanner = getattr(self.service, "scan_pending_publish", None)
        if not callable(scanner):
            return pending_publish_service_unavailable_result()
        try:
            raw = scanner(resolved)
        except Exception as exc:
            exists = bool(resolved.pending_push_path and resolved.pending_push_path.exists())
            return pending_publish_scan_exception_result(resolved.pending_push_path, exists, exc)
        if not isinstance(raw, dict):
            return pending_publish_invalid_result()
        return pending_publish_preview_result(raw)

    def open_pending_publish_location(self, resolved: ResolvedPaths, request: dict[str, object]) -> CommandResult:
        """Open a backend-selected path from the current pending-publish scan."""
        target = normalize_pending_publish_open_target(request.get("target"))
        if not target:
            return pending_publish_open_disallowed_target_result()
        row_key = normalize_pending_publish_row_key(request.get("row_key"))
        if target not in PENDING_PUBLISH_OPEN_TARGETS:
            return pending_publish_open_disallowed_target_result()

        scanner = getattr(self.service, "scan_pending_publish", None)
        if not callable(scanner):
            return pending_publish_open_scan_service_unavailable_result(row_key)
        try:
            raw = scanner(resolved)
        except Exception as exc:
            return pending_publish_open_scan_exception_result(row_key, exc)
        rows = pending_publish_rows(raw.get("rows") if isinstance(raw, dict) else [])
        selected = next((row for row in rows if pending_publish_row_key(row) == row_key), None)
        if selected is None:
            return pending_publish_open_missing_row_result(row_key)
        path = pending_publish_open_path(selected, target)
        if path is None:
            return pending_publish_open_missing_path_result(target, row_key)
        opener = getattr(self.service, "open_path", None)
        if not callable(opener):
            return pending_publish_open_service_unavailable_result(target, row_key, path)
        try:
            opener(path)
        except Exception as exc:
            return pending_publish_open_exception_result(target, row_key, path, exc)
        return pending_publish_open_success_result(target, row_key, path)

    def plan_pending_publish_recovery(self, resolved: ResolvedPaths, request: dict[str, object]) -> CommandResult:
        """Build a backend-authored dry-run recovery plan from the current pending-publish scan."""
        scanner = getattr(self.service, "scan_pending_publish", None)
        if not callable(scanner):
            return pending_publish_recovery_plan_service_unavailable_result()
        try:
            raw = scanner(resolved)
        except Exception as exc:
            return pending_publish_recovery_plan_scan_exception_result(exc)
        if not isinstance(raw, dict):
            return pending_publish_recovery_plan_invalid_scan_result()
        rows = pending_publish_rows(raw.get("rows"))
        return pending_publish_recovery_plan_result(rows, request)

__all__ = [
    "PendingPublishFacadeMixin",
]
