"""Rename preview and guarded apply facade adapter."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from mediapipeline.core.rename.policy import (
    rename_apply_blockers_result,
    rename_apply_active_work_result,
    rename_apply_busy_result,
    rename_apply_confirmation_required_result,
    rename_apply_exception_result,
    rename_apply_missing_selection_result,
    rename_apply_no_selection_result,
    rename_apply_outside_configured_roots_result,
    rename_apply_service_unavailable_result,
    rename_apply_success_result,
    rename_apply_unscoped_operator_paths_result,
    rename_undo_confirmation_required_result,
    rename_undo_active_work_result,
    rename_undo_busy_result,
    rename_undo_exception_result,
    rename_undo_missing_manifest_result,
    rename_undo_service_unavailable_result,
    rename_undo_success_result,
    annotate_rename_plan_path_authority,
    normalize_rename_template_preset,
    rename_configured_media_roots_from_request,
    rename_cleaning_filter_catalog_payload,
    rename_movie_filter_catalog_payload,
    rename_plan_kwargs_from_request,
    rename_plan_build_exception_result,
    rename_plan_outside_configured_roots,
    rename_plan_unscoped_operator_paths,
    rename_clean_filename_preview_from_request,
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
from mediapipeline.core.rename.input_classification import classify_rename_input_paths

if TYPE_CHECKING:
    from mediapipeline.desktop.application.dto_commands import CommandResult
    from mediapipeline.desktop.application.dto_workspaces import RenamePreviewDto


def _rename_preview_dto(**fields: Any) -> "RenamePreviewDto":
    from mediapipeline.desktop.application.dto_workspaces import RenamePreviewDto

    return RenamePreviewDto(**fields)


def _json_safe(value: Any) -> Any:
    from mediapipeline.desktop.application.dto_base import json_safe

    return json_safe(value)


class RenameFacadeMixin:
    """Rename preview and guarded selected-apply adapters for the application facade."""

    def get_rename_preview(self, request: dict[str, Any]) -> RenamePreviewDto:
        rows = [_json_safe(dict(row)) for row in self._build_rename_plan_from_request(request)]
        counts = rename_preview_counts(rows)
        input_classification = classify_rename_input_paths(request.get("paths") or [])
        warnings = sorted(set(rename_preview_warnings(rows) + input_classification.warnings()))
        mode = str(request.get("mode") or "tv")
        active_template = normalize_rename_template_preset(request.get("template_preset"), mode)
        return _rename_preview_dto(
            rows=rows,
            counts=counts,
            input_counts=input_classification.counts(),
            confidence_counts=rename_preview_confidence_counts(rows),
            preview_source_counts=rename_preview_source_counts(rows),
            change_kind_counts=rename_preview_change_kind_counts(rows),
            active_template=active_template,
            template_catalog=rename_template_catalog(mode),
            warnings=warnings,
        )

    def get_rename_clean_filename_preview(self, request: dict[str, Any]) -> dict[str, Any]:
        cleaner = getattr(self.service, "_clean_pipeline_movie_name", None)
        if not callable(cleaner):
            return {
                "schema_version": "desktop_rename_clean_filename_preview.v1",
                "ok": False,
                "input": str(request.get("filename") or ""),
                "input_name": "",
                "cleaned_title": "",
                "target_name": "",
                "preview_source": "backend_movie_cleaner",
                "evidence_authority": "backend",
                "warnings": [],
                "errors": ["Rename movie cleaner is not available."],
                "mutation_boundary": "read-only filename preview; no filesystem paths are opened, renamed, moved, deleted, or written",
            }
        parser = getattr(self.service, "parse_rename_remove_terms", None)
        return rename_clean_filename_preview_from_request(
            request,
            parse_remove_terms=parser if callable(parser) else None,
            clean_movie_name=cleaner,
            build_auto_tv_name=getattr(self.service, "_build_auto_tv_rename_name", None),
        )

    def get_rename_cleaning_filter_catalog(self, config: dict[str, Any] | None = None) -> dict[str, Any]:
        return rename_cleaning_filter_catalog_payload(config)

    def get_rename_movie_filter_catalog(self, config: dict[str, Any] | None = None) -> dict[str, Any]:
        return rename_movie_filter_catalog_payload(config)

    def apply_rename_selection(self, request: dict[str, Any], resolved: Any | None = None) -> CommandResult:
        """Apply a selected rename plan rebuilt by the backend from the current request."""
        if request.get("confirm_apply") is not True:
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
            if resolved is not None:
                active_work_block = self._active_work_block_message(resolved, "Rename apply")
                if active_work_block:
                    return rename_apply_active_work_result(active_work_block)
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
            unscoped_paths = rename_plan_unscoped_operator_paths(selected_plan)
            if unscoped_paths:
                return rename_apply_unscoped_operator_paths_result(unscoped_paths)
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

    def undo_rename_selection(self, request: dict[str, Any], resolved: Any | None = None) -> CommandResult:
        """Undo the most recent backend rename apply from a backend-owned undo manifest."""
        if request.get("confirm_undo") is not True:
            return rename_undo_confirmation_required_result()
        undo_manifest = str(request.get("undo_manifest") or "").strip()
        if not undo_manifest:
            return rename_undo_missing_manifest_result()
        undoer = getattr(self.service, "undo_rename_manifest", None)
        if not callable(undoer):
            return rename_undo_service_unavailable_result()
        lock, block_message = self._acquire_rename_apply_lock()
        if block_message:
            return rename_undo_busy_result(block_message)
        try:
            if resolved is not None:
                active_work_block = self._active_work_block_message(resolved, "Rename undo")
                if active_work_block:
                    return rename_undo_active_work_result(active_work_block)
            try:
                summary = undoer(
                    undo_manifest,
                    undo_manifest_root=rename_undo_manifest_root_from_request(request),
                )
            except Exception as exc:
                return rename_undo_exception_result(exc)
        finally:
            self._release_rename_apply_lock(lock)
        return rename_undo_success_result(summary)

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
