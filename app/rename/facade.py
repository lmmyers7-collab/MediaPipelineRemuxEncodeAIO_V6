"""Rename preview and guarded apply facade adapter."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from app.rename.policy import (
    rename_apply_blockers_result,
    rename_apply_busy_result,
    rename_apply_confirmation_required_result,
    rename_apply_exception_result,
    rename_apply_missing_selection_result,
    rename_apply_no_selection_result,
    rename_apply_outside_configured_roots_result,
    rename_apply_service_unavailable_result,
    rename_apply_success_result,
    annotate_rename_plan_path_authority,
    normalize_rename_template_preset,
    rename_configured_media_roots_from_request,
    rename_plan_kwargs_from_request,
    rename_plan_build_exception_result,
    rename_plan_outside_configured_roots,
    rename_preview_change_kind_counts,
    rename_preview_confidence_counts,
    rename_preview_counts,
    rename_preview_source_counts,
    rename_preview_warnings,
    rename_request_paths,
    rename_request_allows_outside_configured_roots,
    rename_template_catalog,
    rename_undo_manifest_root_from_request,
    select_rename_plan_rows,
    selected_rename_sources,
)

if TYPE_CHECKING:
    from mediapipeline_desktop_app.application.dto_commands import CommandResult
    from mediapipeline_desktop_app.application.dto_workspaces import RenamePreviewDto


def _rename_preview_dto(**fields: Any) -> "RenamePreviewDto":
    from mediapipeline_desktop_app.application.dto_workspaces import RenamePreviewDto

    return RenamePreviewDto(**fields)


def _json_safe(value: Any) -> Any:
    from mediapipeline_desktop_app.application.dto_base import json_safe

    return json_safe(value)


class RenameFacadeMixin:
    """Rename preview and guarded selected-apply adapters for the application facade."""

    def get_rename_preview(self, request: dict[str, Any]) -> RenamePreviewDto:
        rows = [_json_safe(dict(row)) for row in self._build_rename_plan_from_request(request)]
        counts = rename_preview_counts(rows)
        warnings = rename_preview_warnings(rows)
        mode = str(request.get("mode") or "tv")
        active_template = normalize_rename_template_preset(request.get("template_preset"), mode)
        return _rename_preview_dto(
            rows=rows,
            counts=counts,
            confidence_counts=rename_preview_confidence_counts(rows),
            preview_source_counts=rename_preview_source_counts(rows),
            change_kind_counts=rename_preview_change_kind_counts(rows),
            active_template=active_template,
            template_catalog=rename_template_catalog(mode),
            warnings=warnings,
        )

    def apply_rename_selection(self, request: dict[str, Any]) -> CommandResult:
        """Apply a selected rename plan rebuilt by the backend from the current request."""
        if not bool(request.get("confirm_apply", False)):
            return rename_apply_confirmation_required_result()
        selected_sources = selected_rename_sources(request)
        if not selected_sources:
            return rename_apply_no_selection_result()
        applier = getattr(self.service, "apply_rename_path_plan", None)
        if not callable(applier):
            return rename_apply_service_unavailable_result()
        lock, block_message = self._acquire_rename_apply_lock()
        if block_message:
            return rename_apply_busy_result(block_message)
        try:
            try:
                plan = self._build_rename_plan_from_request(request)
            except Exception as exc:
                return rename_plan_build_exception_result(exc)
            selected_plan, missing = select_rename_plan_rows(plan, selected_sources)
            if missing:
                return rename_apply_missing_selection_result(missing)
            blockers = [row for row in selected_plan if row.get("errors")]
            if blockers:
                return rename_apply_blockers_result(blockers)
            outside_roots = rename_plan_outside_configured_roots(selected_plan)
            if outside_roots and not rename_request_allows_outside_configured_roots(request):
                return rename_apply_outside_configured_roots_result(outside_roots)
            try:
                summary = applier(selected_plan, undo_manifest_root=rename_undo_manifest_root_from_request(request))
            except Exception as exc:
                return rename_apply_exception_result(exc)
        finally:
            self._release_rename_apply_lock(lock)
        renamed = self._int_value(summary.get("renamed"))
        return rename_apply_success_result(summary, renamed=renamed)

    def _build_rename_plan_from_request(self, request: dict[str, Any]) -> list[dict[str, Any]]:
        planner = getattr(self.service, "plan_rename_paths", None)
        if not callable(planner):
            raise RuntimeError("Rename preview service is not available.")
        parser = getattr(self.service, "parse_rename_remove_terms", None)
        rows = planner(
            rename_request_paths(request),
            **rename_plan_kwargs_from_request(request, parse_remove_terms=parser if callable(parser) else None),
        )
        configured_roots = rename_configured_media_roots_from_request(request)
        return annotate_rename_plan_path_authority(rows, configured_roots)

    def _acquire_rename_apply_lock(self) -> tuple[object | None, str]:
        lock = getattr(self, "_rename_apply_lock", None)
        if lock is None:
            return None, ""
        try:
            acquired = lock.acquire(blocking=False)
        except Exception as exc:
            self._log_rename_apply_exception("Rename apply lock acquisition failed", exc)
            return None, f"Rename apply blocked because the lock could not be verified: {exc}"
        if not acquired:
            return None, "Rename apply blocked because another rename apply command is already in progress."
        return lock, ""

    def _release_rename_apply_lock(self, lock: object | None) -> None:
        if lock is None:
            return
        try:
            lock.release()  # type: ignore[attr-defined]
        except Exception as exc:
            self._log_rename_apply_exception("Rename apply lock release failed", exc)

    def _log_rename_apply_exception(self, message: str, exc: Exception) -> None:
        logger = getattr(getattr(self, "service", None), "logger", None)
        if logger is None:
            return
        try:
            logger.warning("%s: %s", message, exc, exc_info=True)
        except Exception:
            return

__all__ = [
    "RenameFacadeMixin",
]
