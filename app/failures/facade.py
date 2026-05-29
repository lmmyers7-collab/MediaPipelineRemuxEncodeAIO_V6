"""Failure report preview and marker-clear facade adapter."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app.failures.policy import (
    bounded_failure_limit,
    failure_json_read_error_result,
    failure_latest_json_resolution_error_result,
    failure_loader_unavailable_result,
    failure_marker_service_unavailable_result,
    failure_markers_read_error_result,
    failure_no_json_report_result,
    failure_preview_from_records,
    failure_report_service_unavailable_result,
    failure_record_to_row,
    normalize_failure_source_kind,
)

from mediapipeline_desktop_app.application.dto_commands import CommandResult
from mediapipeline_desktop_app.application.dto_inventory import FailurePreviewDto
from mediapipeline_desktop_app.models import FailureRecord, ResolvedPaths


class FailureFacadeMixin:
    """Read-only failure-report adapter for the application facade."""

    def get_failure_preview(self, resolved: ResolvedPaths, *, source_kind: str = "latest_json", limit: int = 100) -> FailurePreviewDto:
        """Return recent failure rows without mutating markers, reports, or priority state."""
        source_kind = normalize_failure_source_kind(source_kind)
        bounded_limit = bounded_failure_limit(limit)
        if source_kind == "markers":
            loader = getattr(self.service, "load_failure_marker_records", None)
            if not callable(loader):
                return failure_marker_service_unavailable_result()
            try:
                records = loader(resolved)
            except Exception as exc:
                return failure_markers_read_error_result(resolved.failed_markers_path, exc)
            return self._failure_preview_from_records(
                records,
                source=str(resolved.failed_markers_path or ""),
                source_kind="markers",
                limit=bounded_limit,
                empty_warning="No failure markers are available from the state store.",
            )

        path_getter = getattr(self.service, "latest_failure_json", None)
        if not callable(path_getter):
            path_getter = getattr(self.service, "newest_failure_json", None)
        if not callable(path_getter):
            return failure_report_service_unavailable_result()
        try:
            report_path = path_getter(resolved)
        except Exception as exc:
            return failure_latest_json_resolution_error_result(exc)
        if not report_path:
            return failure_no_json_report_result()
        loader = getattr(self.service, "load_failure_records", None)
        if not callable(loader):
            return failure_loader_unavailable_result(report_path)
        try:
            records = loader(Path(report_path))
        except Exception as exc:
            return failure_json_read_error_result(report_path, exc)
        return self._failure_preview_from_records(
            records,
            source=str(report_path),
            source_kind="latest_json",
            limit=bounded_limit,
            empty_warning="Latest failure JSON contains no rows.",
        )

    def _failure_preview_from_records(
        self,
        records: object,
        *,
        source: str,
        source_kind: str,
        limit: int,
        empty_warning: str,
    ) -> FailurePreviewDto:
        return failure_preview_from_records(
            records,
            source=source,
            source_kind=source_kind,
            limit=limit,
            empty_warning=empty_warning,
        )

    @staticmethod
    def _failure_record_to_row(record: FailureRecord) -> dict[str, object]:
        return failure_record_to_row(record)

    def clear_failure_markers(self, resolved: ResolvedPaths, request: dict[str, Any]) -> CommandResult:
        """Clear backend-owned failure marker files after explicit operator confirmation."""
        dry_run = bool(request.get("dry_run", False))
        confirm_clear = bool(request.get("confirm_clear", False))
        marker_paths = request.get("marker_paths")
        if marker_paths is None and request.get("marker_path"):
            marker_paths = [request.get("marker_path")]
        if marker_paths is None and request.get("source_json"):
            marker_paths = [request.get("source_json")]
        if marker_paths is not None and not isinstance(marker_paths, list):
            return CommandResult(
                command="failures.clear",
                ok=False,
                severity="error",
                message="'marker_paths' must be a list of backend failure marker paths.",
                errors=["'marker_paths' must be a list of backend failure marker paths."],
                refresh_hint="failures",
            )
        cleaned_paths = [str(item) for item in marker_paths or [] if str(item or "").strip()]
        scope = str(request.get("scope") or ("selected" if cleaned_paths else "all_markers"))
        if scope not in {"selected", "visible", "all_markers"}:
            return CommandResult(
                command="failures.clear",
                ok=False,
                severity="error",
                message="'scope' must be selected, visible, or all_markers.",
                errors=["'scope' must be selected, visible, or all_markers."],
                refresh_hint="failures",
            )
        if scope in {"selected", "visible"} and not cleaned_paths:
            return CommandResult(
                command="failures.clear",
                ok=False,
                severity="error",
                message=f"Failure marker clear scope '{scope}' requires marker_paths.",
                errors=[f"Failure marker clear scope '{scope}' requires marker_paths."],
                refresh_hint="failures",
                data={"scope": scope, "marker_count": 0, "dry_run": dry_run},
            )
        if not dry_run and not confirm_clear:
            return CommandResult(
                command="failures.clear",
                ok=False,
                severity="error",
                message="Failure marker clear requires confirm_clear: true.",
                errors=["Failure marker clear requires confirm_clear: true."],
                refresh_hint="failures",
                data={"scope": scope, "marker_count": len(cleaned_paths), "dry_run": dry_run},
            )
        clearer = getattr(self.service, "clear_failure_markers", None)
        if not callable(clearer):
            return CommandResult(
                command="failures.clear",
                ok=False,
                severity="error",
                message="Failure marker clear service is unavailable.",
                errors=["Failure marker clear service is unavailable."],
                refresh_hint="failures",
            )
        try:
            result = clearer(resolved, marker_paths=cleaned_paths or None, dry_run=dry_run)
        except Exception as exc:
            return CommandResult(
                command="failures.clear",
                ok=False,
                severity="error",
                message=f"Failure marker clear failed: {exc}",
                errors=[str(exc)],
                refresh_hint="failures",
            )
        errors = [str(item) for item in result.get("errors") or [] if str(item).strip()]
        planned_count = len(result.get("planned") or [])
        moved_count = int(result.get("markers") or 0)
        ok = not errors
        if dry_run:
            message = f"Failure marker clear preview found {planned_count} marker(s)."
        else:
            message = f"Failure marker clear moved {moved_count} marker(s) out of the active marker folder."
        if errors:
            message = "Failure marker clear blocked; review errors before retrying."
        data = dict(result)
        data["scope"] = scope
        data["writes_failure_markers"] = not dry_run
        data["touches_media"] = False
        data["safe_next_action"] = (
            "Refresh Queue/Reports. Cleared sources can be retried on the next backend queue build."
            if ok and not dry_run
            else "Review the dry-run plan, then confirm clear only after the failure root cause is understood."
        )
        return CommandResult(
            command="failures.clear",
            ok=ok,
            severity="info" if ok else "error",
            message=message,
            errors=errors,
            warnings=[str(item.get("reason")) for item in result.get("skipped") or [] if isinstance(item, dict) and item.get("reason")],
            refresh_hint="failures",
            data=data,
        )

__all__ = [
    "FailureFacadeMixin",
]
