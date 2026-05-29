"""Schedule workspace facade adapter."""

from __future__ import annotations

from typing import Any

from app.schedule.policy import (
    schedule_day_summaries,
    schedule_grid_changed_days,
    schedule_grid_from_request,
    schedule_grid_rows,
    schedule_patch_warnings,
    schedule_preview_result,
    schedule_save_busy_result,
    schedule_save_confirmation_required_result,
    schedule_save_exception_result,
    schedule_save_no_changes_result,
    schedule_save_service_unavailable_result,
    schedule_save_success_result,
    schedule_save_validation_error_result,
)
from mediapipeline_desktop_app.application.dto_base import json_safe
from mediapipeline_desktop_app.application.dto_commands import CommandResult
from mediapipeline_desktop_app.application.dto_workspaces import ScheduleWorkspaceDto
from mediapipeline_desktop_app.application.schedule_stop_watcher import schedule_stop_watcher_state_mapping


class ScheduleFacadeMixin:
    """Schedule workspace query adapter for UI-neutral application facades."""

    service: object
    app_version: str

    def _schedule_state(self) -> tuple[dict[str, Any], dict[str, list[bool]], bool, list[str]]:
        warnings: list[str] = []
        loader = getattr(self.service, "load_app_state", None)
        state: dict[str, Any] = {}
        if callable(loader):
            try:
                raw_state = loader()
                state = raw_state if isinstance(raw_state, dict) else {}
            except Exception as exc:
                warnings.append(f"Schedule app state could not be read: {exc}")
        else:
            warnings.append("Schedule app state service is not available.")

        normalizer = getattr(self.service, "normalize_schedule_grid", None)
        default_grid = getattr(self.service, "default_schedule_grid", None)
        raw_grid = state.get("schedule_grid")
        if callable(normalizer):
            grid = normalizer(raw_grid)
        elif callable(default_grid):
            grid = default_grid()
        else:
            grid = {}
            warnings.append("Schedule grid normalization service is not available.")
        return state, grid, bool(state.get("schedule_enabled", False)), warnings

    def get_schedule_workspace(self) -> ScheduleWorkspaceDto:
        """Return the persisted schedule grid and current evaluation without changing it."""
        _state, grid, enabled, warnings = self._schedule_state()
        evaluator = getattr(self.service, "evaluate_schedule", None)
        evaluation: dict[str, Any] = {}
        if callable(evaluator):
            try:
                raw_evaluation = evaluator(enabled, grid)
                evaluation = dict(raw_evaluation) if isinstance(raw_evaluation, dict) else {}
            except Exception as exc:
                warnings.append(f"Schedule evaluation failed: {exc}")
        else:
            warnings.append("Schedule evaluation service is not available.")

        return ScheduleWorkspaceDto(
            app_version=self.app_version,
            enabled=enabled,
            evaluation=json_safe(evaluation),
            day_summaries=self._schedule_day_summaries(grid),
            grid=schedule_grid_rows(grid),
            app_state_path=str(getattr(self.service, "app_state_path", "") or ""),
            continuous_watcher=self._schedule_stop_watcher_state(),
            warnings=warnings,
        )

    def _schedule_day_summaries(self, grid: dict[str, list[bool]]) -> list[dict[str, Any]]:
        formatter = getattr(self.service, "block_label", None)
        return schedule_day_summaries(grid, formatter=formatter if callable(formatter) else None)

    def _schedule_stop_watcher_state(self) -> dict[str, Any]:
        return json_safe(schedule_stop_watcher_state_mapping(getattr(self, "_schedule_stop_watcher", None)))

    def preview_schedule_patch(self, request: dict[str, Any]) -> CommandResult:
        """Preview a schedule/app-state update without writing app state."""
        _state, current_grid, current_enabled, read_warnings = self._schedule_state()
        normalizer = getattr(self.service, "normalize_schedule_grid", None)
        proposed_grid, errors, source = schedule_grid_from_request(
            request,
            normalizer=normalizer if callable(normalizer) else None,
        )
        proposed_enabled = bool(request.get("enabled", current_enabled))
        warnings = read_warnings + schedule_patch_warnings(enabled=proposed_enabled, grid=proposed_grid)
        formatter = getattr(self.service, "block_label", None)
        return schedule_preview_result(
            enabled=proposed_enabled,
            current_enabled=current_enabled,
            grid=proposed_grid,
            current_grid=current_grid,
            source=source,
            errors=errors,
            warnings=warnings,
            app_state_path=str(getattr(self.service, "app_state_path", "") or ""),
            formatter=formatter if callable(formatter) else None,
        )

    def save_schedule_patch(self, request: dict[str, Any]) -> CommandResult:
        """Validate and save a schedule/app-state update through the service layer."""
        if not bool(request.get("confirm_save", False)):
            return schedule_save_confirmation_required_result()
        lock, block_message = self._acquire_schedule_save_lock()
        if block_message:
            return schedule_save_busy_result(block_message)
        warnings: list[str] = []
        try:
            _state, current_grid, current_enabled, read_warnings = self._schedule_state()
            normalizer = getattr(self.service, "normalize_schedule_grid", None)
            proposed_grid, errors, source = schedule_grid_from_request(
                request,
                normalizer=normalizer if callable(normalizer) else None,
            )
            proposed_enabled = bool(request.get("enabled", current_enabled))
            warnings = read_warnings + schedule_patch_warnings(enabled=proposed_enabled, grid=proposed_grid)
            if errors:
                return schedule_save_validation_error_result(errors, warnings)
            changed_days = schedule_grid_changed_days(current_grid, proposed_grid)
            changed_enabled = bool(proposed_enabled) != bool(current_enabled)
            if not changed_days and not changed_enabled:
                return schedule_save_no_changes_result(warnings)
            saver = getattr(self.service, "save_app_state", None)
            if not callable(saver):
                return schedule_save_service_unavailable_result()
            saver({"schedule_enabled": proposed_enabled, "schedule_grid": schedule_grid_rows(proposed_grid)})
        except Exception as exc:
            return schedule_save_exception_result(exc, warnings)
        finally:
            self._release_schedule_save_lock(lock)
        formatter = getattr(self.service, "block_label", None)
        return schedule_save_success_result(
            enabled=proposed_enabled,
            current_enabled=current_enabled,
            grid=proposed_grid,
            current_grid=current_grid,
            source=source,
            warnings=warnings,
            app_state_path=str(getattr(self.service, "app_state_path", "") or ""),
            formatter=formatter if callable(formatter) else None,
        )

    def _acquire_schedule_save_lock(self) -> tuple[object | None, str]:
        lock = getattr(self, "_schedule_save_lock", None)
        if lock is None:
            return None, ""
        try:
            acquired = lock.acquire(blocking=False)
        except Exception as exc:
            self._log_schedule_save_exception("Schedule save lock acquisition failed", exc)
            return None, f"Schedule save blocked because the lock could not be verified: {exc}"
        if not acquired:
            return None, "Schedule save blocked because another schedule save command is already in progress."
        return lock, ""

    def _release_schedule_save_lock(self, lock: object | None) -> None:
        if lock is None:
            return
        try:
            lock.release()  # type: ignore[attr-defined]
        except Exception as exc:
            self._log_schedule_save_exception("Schedule save lock release failed", exc)

    def _log_schedule_save_exception(self, message: str, exc: Exception) -> None:
        logger = getattr(getattr(self, "service", None), "logger", None)
        if logger is None:
            return
        try:
            logger.warning("%s: %s", message, exc, exc_info=True)
        except Exception:
            return

__all__ = [
    "ScheduleFacadeMixin",
]
