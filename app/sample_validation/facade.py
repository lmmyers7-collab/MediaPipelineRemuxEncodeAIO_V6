from __future__ import annotations

from typing import Any

from mediapipeline_desktop_app.application.dto_commands import CommandResult
from app.sample_validation.policy import (
    append_sample_validation_record,
    sample_validation_log_payload,
    sample_validation_preview,
)
from mediapipeline_desktop_app.models import ResolvedPaths


class SampleValidationFacadeMixin:
    """Backend-owned sample validation evidence adapter."""

    app_version: str
    _sample_validation_lock: Any

    def preview_sample_validation_record(self, resolved: ResolvedPaths, request: dict[str, Any]) -> dict[str, Any]:
        return sample_validation_preview(resolved, request, app_version=self.app_version)

    def append_sample_validation_record(self, resolved: ResolvedPaths, request: dict[str, Any]) -> CommandResult:
        return append_sample_validation_record(
            resolved,
            request,
            app_version=self.app_version,
            lock=self._sample_validation_lock,
        )

    def get_sample_validation_records(self, resolved: ResolvedPaths, *, limit: int = 20) -> dict[str, Any]:
        return sample_validation_log_payload(resolved, limit=limit)


__all__ = [
    "SampleValidationFacadeMixin",
]
