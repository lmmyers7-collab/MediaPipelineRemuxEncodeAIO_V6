from __future__ import annotations

from pathlib import Path
from typing import Any

from ..models import AuditRecord, ResolvedPaths
from .dto import AuditPreviewDto
from .facade_audit_policy import (
    audit_duplicate_group_count,
    audit_csv_read_error_result,
    audit_latest_csv_resolution_error_result,
    audit_loader_unavailable_result,
    audit_no_csv_report_result,
    audit_preview_from_records,
    audit_report_service_unavailable_result,
    audit_record_to_row,
    bounded_audit_limit,
)


class AuditFacadeMixin:
    """Read-only audit-report adapter for the application facade."""

    def get_audit_preview(self, resolved: ResolvedPaths, *, priority_only: bool = False, limit: int = 100) -> AuditPreviewDto:
        """Return recent audit rows without exporting, prioritizing, rerunning, or opening files."""
        bounded_limit = bounded_audit_limit(limit)
        path_getter = getattr(self.service, "latest_audit_csv", None)
        if not callable(path_getter):
            path_getter = getattr(self.service, "newest_audit_csv", None)
        if not callable(path_getter):
            return audit_report_service_unavailable_result(priority_only)
        try:
            csv_path = path_getter(resolved, priority_only=bool(priority_only))
        except Exception as exc:
            return audit_latest_csv_resolution_error_result(priority_only, exc)
        if not csv_path:
            return audit_no_csv_report_result(priority_only)
        loader = getattr(self.service, "load_audit_records", None)
        if not callable(loader):
            return audit_loader_unavailable_result(csv_path, priority_only)
        try:
            records = loader(Path(csv_path))
        except Exception as exc:
            return audit_csv_read_error_result(csv_path, priority_only, exc)
        return self._audit_preview_from_records(
            records,
            source=str(csv_path),
            priority_only=bool(priority_only),
            limit=bounded_limit,
            empty_warning="Latest audit CSV contains no rows.",
        )

    def _audit_preview_from_records(
        self,
        records: object,
        *,
        source: str,
        priority_only: bool,
        limit: int,
        empty_warning: str,
    ) -> AuditPreviewDto:
        return audit_preview_from_records(
            records,
            source=source,
            priority_only=priority_only,
            limit=limit,
            empty_warning=empty_warning,
        )

    @staticmethod
    def _audit_record_to_row(record: AuditRecord) -> dict[str, Any]:
        return audit_record_to_row(record)

    @staticmethod
    def _audit_duplicate_group_count(records: list[AuditRecord]) -> int:
        return audit_duplicate_group_count(records)

__all__ = [
    "AuditFacadeMixin",
]
