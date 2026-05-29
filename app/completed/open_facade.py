"""Completed-job open command facade adapter."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app.completed.open_policy import (
    COMPLETED_OPEN_TARGETS,
    completed_open_disallowed_target_result,
    completed_open_exception_result,
    completed_open_path,
    completed_open_path_missing_result,
    completed_open_path_service_unavailable_result,
    completed_open_read_exception_result,
    completed_open_requires_row_result,
    completed_open_row_missing_result,
    completed_open_service_unavailable_result,
    completed_open_success_result,
    find_completed_record_by_key,
    normalize_completed_open_target,
)
from mediapipeline_desktop_app.application.dto_commands import CommandResult
from mediapipeline_desktop_app.models import CompletedJobRecord, ResolvedPaths


class CompletedOpenFacadeMixin:
    """Backend-allowlisted open command for completed manifest rows."""

    def open_completed_location(self, resolved: ResolvedPaths, request: dict[str, Any]) -> CommandResult:
        """Open a path selected from the completed-jobs manifest, not from a raw frontend path."""
        row_key = str(request.get("row_key") or "").strip()
        target = normalize_completed_open_target(request.get("target"))
        if not row_key:
            return completed_open_requires_row_result()
        if target not in COMPLETED_OPEN_TARGETS:
            return completed_open_disallowed_target_result()
        loader = getattr(self.service, "load_recent_completed_jobs", None)
        if not callable(loader):
            return completed_open_service_unavailable_result()
        try:
            records = loader(resolved, limit=500)
        except Exception as exc:
            return completed_open_read_exception_result(exc)
        record = find_completed_record_by_key(records, row_key, self._completed_record_key)
        if record is None:
            return completed_open_row_missing_result()
        path = self._completed_open_path(record, target)
        if path is None:
            return completed_open_path_missing_result(target, row_key)
        opener = getattr(self.service, "open_path", None)
        if not callable(opener):
            return completed_open_path_service_unavailable_result(target, row_key, path)
        try:
            opener(path)
        except Exception as exc:
            return completed_open_exception_result(target, row_key, path, exc)
        return completed_open_success_result(target, row_key, path)

    @staticmethod
    def _completed_open_path(record: CompletedJobRecord, target: str) -> Path | None:
        return completed_open_path(record, target)

__all__ = [
    "CompletedOpenFacadeMixin",
]
