"""Audit report preview facade adapter."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from app.audit.ignore_manifest import (
    audit_ignore_manifest_payload,
    read_audit_ignore_manifest,
    remove_audit_ignore_entries,
    set_audit_ignore_entries,
)
from app.audit.preview_policy import (
    audit_records_for_row_keys,
    audit_csv_read_error_result,
    audit_duplicate_group_count,
    audit_latest_csv_resolution_error_result,
    audit_loader_unavailable_result,
    audit_no_csv_report_result,
    audit_preview_from_records,
    audit_report_service_unavailable_result,
    audit_record_to_row,
    bounded_audit_limit,
)
from app.audit.score_policy import (
    audit_score_policy_payload,
    reset_audit_score_policy,
    write_audit_score_policy,
)

from mediapipeline_desktop_app.application.dto_commands import CommandResult
from mediapipeline_desktop_app.application.dto_inventory import AuditPreviewDto
from mediapipeline_desktop_app.models import AuditRecord, ResolvedPaths


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
        ignore_manifest = read_audit_ignore_manifest(getattr(resolved, "audit_ignore_manifest_path", None))
        return self._audit_preview_from_records(
            records,
            source=str(csv_path),
            priority_only=bool(priority_only),
            limit=bounded_limit,
            empty_warning="Latest audit CSV contains no rows.",
            ignore_manifest=ignore_manifest,
        )

    def _audit_preview_from_records(
        self,
        records: object,
        *,
        source: str,
        priority_only: bool,
        limit: int,
        empty_warning: str,
        ignore_manifest: dict[str, Any] | None = None,
    ) -> AuditPreviewDto:
        return audit_preview_from_records(
            records,
            source=source,
            priority_only=priority_only,
            limit=limit,
            empty_warning=empty_warning,
            ignore_manifest=ignore_manifest,
        )

    @staticmethod
    def _audit_record_to_row(record: AuditRecord, *, row_index: int = 0) -> dict[str, Any]:
        return audit_record_to_row(record, row_index=row_index)

    @staticmethod
    def _audit_duplicate_group_count(records: list[AuditRecord]) -> int:
        return audit_duplicate_group_count(records)

    def get_audit_controls(self, resolved: ResolvedPaths) -> dict[str, Any]:
        score_path = getattr(resolved, "audit_score_policy_path", None)
        ignore_path = getattr(resolved, "audit_ignore_manifest_path", None)
        ignore_manifest = read_audit_ignore_manifest(ignore_path)
        return {
            "schema_version": "desktop_audit_controls.v1",
            "score_policy": audit_score_policy_payload(score_path),
            "ignore_manifest": audit_ignore_manifest_payload(ignore_path, ignore_manifest),
            "boundaries": [
                "Audit score policy affects audit reporting and future priority CSV generation only.",
                "Audit ignore entries do not hold queue items, write file overrides, save settings, rename, publish, drain, delete, or touch media.",
                "Rerun CSV export uses backend-owned copy / keep / park defaults.",
            ],
        }

    def save_audit_score_policy(self, resolved: ResolvedPaths, request: dict[str, Any]) -> CommandResult:
        score_path = getattr(resolved, "audit_score_policy_path", None)
        if score_path is None:
            return CommandResult(
                command="audit.score_policy",
                ok=False,
                severity="error",
                message="Audit score policy path is unavailable because state_root is not configured.",
                errors=["audit_score_policy_path_unavailable"],
            )
        try:
            if request.get("reset") is True:
                policy = reset_audit_score_policy(score_path)
                message = "Audit score policy reset to defaults."
            else:
                policy = write_audit_score_policy(score_path, dict(request.get("policy") or {}))
                message = "Audit score policy saved."
        except Exception as exc:
            return CommandResult(
                command="audit.score_policy",
                ok=False,
                severity="error",
                message=f"Audit score policy save failed: {exc}",
                errors=[str(exc)],
            )
        return CommandResult(
            command="audit.score_policy",
            ok=True,
            severity="ok",
            message=message,
            refresh_hint="audit-controls",
            data={
                "schema_version": "desktop_audit_score_policy_result.v1",
                "path": str(score_path),
                "policy": policy,
                "touches_media": False,
                "writes_queue": False,
                "writes_file_overrides": False,
            },
        )

    def update_audit_ignore(self, resolved: ResolvedPaths, request: dict[str, Any]) -> CommandResult:
        ignore_path = getattr(resolved, "audit_ignore_manifest_path", None)
        if ignore_path is None:
            return CommandResult(
                command="audit.ignore",
                ok=False,
                severity="error",
                message="Audit ignore manifest path is unavailable because state_root is not configured.",
                errors=["audit_ignore_manifest_path_unavailable"],
            )
        action = str(request.get("action") or "add").strip().lower()
        if action not in {"add", "remove"}:
            return CommandResult(
                command="audit.ignore",
                ok=False,
                severity="error",
                message="audit.ignore action must be add or remove.",
                errors=["invalid_audit_ignore_action"],
            )
        priority_only = bool(request.get("priority_only", False))
        limit = bounded_audit_limit(request.get("limit", 100))
        row_keys = [str(key).strip() for key in request.get("row_keys") or [] if str(key).strip()]
        explicit_paths = [str(path).strip() for path in request.get("paths") or [] if str(path).strip()]
        reason = str(request.get("reason") or "Ignored from audit triage by operator.").strip()
        try:
            records = self._load_current_audit_records(resolved, priority_only=priority_only)
            ignore_manifest = read_audit_ignore_manifest(ignore_path)
            selected = audit_records_for_row_keys(
                records,
                row_keys,
                ignore_manifest=ignore_manifest if action == "add" else None,
                limit=limit,
            ) if row_keys else []
            paths = explicit_paths + [str(record.path or "") for record in selected if record.path]
            if not paths:
                return CommandResult(
                    command="audit.ignore",
                    ok=False,
                    severity="warning",
                    message="No audit rows or paths were available to update.",
                    errors=["no_audit_ignore_targets"],
                )
            if action == "remove":
                manifest = remove_audit_ignore_entries(ignore_path, paths)
                message = f"Audit ignore removed for {len(paths)} path(s)."
            else:
                selected_by_path = {str(record.path or ""): record for record in selected if record.path}
                source_csv = str(records[0].source_csv) if records else ""
                items = []
                for path in paths:
                    record = selected_by_path.get(path)
                    items.append({
                        "path": path,
                        "reason": reason,
                        "source_csv": str(record.source_csv) if record else source_csv,
                        "issue_code": record.primary_issue_code if record else "",
                        "title": record.lookup_title if record else "",
                    })
                manifest = set_audit_ignore_entries(ignore_path, items, reason=reason)
                message = f"Audit ignore saved for {len(items)} path(s)."
        except Exception as exc:
            return CommandResult(
                command="audit.ignore",
                ok=False,
                severity="error",
                message=f"Audit ignore update failed: {exc}",
                errors=[str(exc)],
            )
        return CommandResult(
            command="audit.ignore",
            ok=True,
            severity="ok",
            message=message,
            refresh_hint="audit-controls",
            data={
                "schema_version": "desktop_audit_ignore_result.v1",
                "manifest_path": str(ignore_path),
                "entry_count": len(manifest.get("entries", {})),
                "updated_count": len(paths),
                "action": action,
                "touches_media": False,
                "writes_queue": False,
                "writes_file_overrides": False,
            },
        )

    def export_audit_rerun_csv(self, resolved: ResolvedPaths, request: dict[str, Any]) -> CommandResult:
        report_root = getattr(resolved, "audit_reports_path", None)
        if report_root is None:
            return CommandResult(
                command="audit.export_rerun_csv",
                ok=False,
                severity="error",
                message="Audit report root is unavailable.",
                errors=["audit_report_root_unavailable"],
            )
        priority_only = bool(request.get("priority_only", False))
        limit = bounded_audit_limit(request.get("limit", 100))
        row_keys = [str(key).strip() for key in request.get("row_keys") or [] if str(key).strip()]
        ignore_manifest = read_audit_ignore_manifest(getattr(resolved, "audit_ignore_manifest_path", None))
        try:
            records = self._load_current_audit_records(resolved, priority_only=priority_only)
            selected_records = audit_records_for_row_keys(
                records,
                row_keys,
                ignore_manifest=ignore_manifest,
                limit=limit,
            )
            if not selected_records:
                return CommandResult(
                    command="audit.export_rerun_csv",
                    ok=False,
                    severity="warning",
                    message="No non-ignored audit rows were available for rerun CSV export.",
                    errors=["no_audit_rows_to_export"],
                )
            writer = getattr(self.service, "save_rerun_records_csv", None)
            if not callable(writer):
                raise RuntimeError("Audit rerun CSV writer is not available.")
            stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_path = Path(report_root) / f"audit_rerun_export_{stamp}.csv"
            written = int(writer(
                output_path,
                selected_records,
                resolved,
                stage_mode="copy",
                original_mode="keep",
                return_mode="park",
            ))
        except Exception as exc:
            return CommandResult(
                command="audit.export_rerun_csv",
                ok=False,
                severity="error",
                message=f"Audit rerun CSV export failed: {exc}",
                errors=[str(exc)],
            )
        return CommandResult(
            command="audit.export_rerun_csv",
            ok=True,
            severity="ok",
            message=f"Exported {written} audit row(s) to rerun CSV.",
            refresh_hint="audit-controls",
            data={
                "schema_version": "desktop_audit_rerun_export.v1",
                "output_path": str(output_path),
                "row_count": written,
                "selected_row_count": len(row_keys),
                "scope": "selected" if row_keys else "loaded",
                "stage_mode": "copy",
                "original_mode": "keep",
                "return_mode": "park",
                "touches_media": False,
                "writes_queue": False,
                "writes_file_overrides": False,
            },
        )

    def _load_current_audit_records(self, resolved: ResolvedPaths, *, priority_only: bool) -> list[AuditRecord]:
        path_getter = getattr(self.service, "latest_audit_csv", None)
        if not callable(path_getter):
            path_getter = getattr(self.service, "newest_audit_csv", None)
        if not callable(path_getter):
            raise RuntimeError("Audit CSV resolver is not available.")
        csv_path = path_getter(resolved, priority_only=bool(priority_only))
        if not csv_path:
            raise FileNotFoundError("No audit CSV report is available yet.")
        loader = getattr(self.service, "load_audit_records", None)
        if not callable(loader):
            raise RuntimeError("Audit CSV loader is not available.")
        return list(loader(Path(csv_path)))

__all__ = [
    "AuditFacadeMixin",
]
