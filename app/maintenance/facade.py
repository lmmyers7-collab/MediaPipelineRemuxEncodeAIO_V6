"""Maintenance workspace facade adapter."""

from __future__ import annotations

import inspect
from typing import TYPE_CHECKING, Any

from app.maintenance.policy import (
    maintenance_health_progress,
    maintenance_health_progress_with_error,
    maintenance_health_rows,
    maintenance_toolchain_evidence,
    maintenance_workspace_counts,
)
from app.maintenance.change_ledger import change_ledger_payload
from mediapipeline_desktop_app.models import ResolvedPaths

if TYPE_CHECKING:
    from mediapipeline_desktop_app.application.dto_workspaces import MaintenanceWorkspaceDto


def _maintenance_workspace_dto(**fields: Any) -> "MaintenanceWorkspaceDto":
    from mediapipeline_desktop_app.application.dto_workspaces import MaintenanceWorkspaceDto

    return MaintenanceWorkspaceDto(**fields)


class MaintenanceFacadeMixin:
    """Read-only maintenance workspace adapter for the application facade."""

    def _set_maintenance_health_progress(self, progress: dict[str, Any]) -> None:
        lock = getattr(self, "_maintenance_health_progress_lock", None)
        if lock is None:
            self._maintenance_health_progress = dict(progress)
            return
        with lock:
            self._maintenance_health_progress = dict(progress)

    def get_maintenance_health_progress(self) -> dict[str, Any]:
        lock = getattr(self, "_maintenance_health_progress_lock", None)
        if lock is None:
            current = getattr(self, "_maintenance_health_progress", None)
            return dict(current) if isinstance(current, dict) else maintenance_health_progress(None, [], status="idle")
        with lock:
            current = getattr(self, "_maintenance_health_progress", None)
            return dict(current) if isinstance(current, dict) else maintenance_health_progress(None, [], status="idle")

    def _checker_accepts_progress_callback(self, checker: object) -> bool:
        try:
            parameters = inspect.signature(checker).parameters
        except (TypeError, ValueError):
            return False
        return "progress_callback" in parameters

    def get_maintenance_workspace(self, resolved: ResolvedPaths) -> MaintenanceWorkspaceDto:
        checker = getattr(self.service, "check_environment_health", None)
        if not callable(checker):
            health_progress = maintenance_health_progress(resolved, [], status="blocked", error="Environment health service is not available.")
            self._set_maintenance_health_progress(health_progress)
            return _maintenance_workspace_dto(
                app_version=self.app_version,
                health_progress=health_progress,
                progress_bars=list(health_progress.get("progress_bars") or []),
                warnings=["Environment health service is not available."],
            )
        self._set_maintenance_health_progress(
            maintenance_health_progress(
                resolved,
                [],
                status="active",
                active_step_id="powershell",
                active_detail="Starting backend environment health checks.",
            )
        )

        def progress_callback(event: dict[str, Any]) -> None:
            raw_rows = event.get("rows") if isinstance(event, dict) else []
            rows = maintenance_health_rows(raw_rows)
            progress = maintenance_health_progress(
                resolved,
                rows,
                status="active",
                active_step_id=str(event.get("active_step_id") or "") if isinstance(event, dict) else "",
                active_detail=str(event.get("active_detail") or "") if isinstance(event, dict) else "",
            )
            self._set_maintenance_health_progress(progress)

        try:
            if self._checker_accepts_progress_callback(checker):
                raw_rows = checker(resolved, progress_callback=progress_callback)
            else:
                raw_rows = checker(resolved)
        except Exception as exc:
            health_progress = maintenance_health_progress_with_error(
                self.get_maintenance_health_progress(),
                f"Environment health check failed: {exc}",
            )
            self._set_maintenance_health_progress(health_progress)
            return _maintenance_workspace_dto(
                app_version=self.app_version,
                health_progress=health_progress,
                progress_bars=list(health_progress.get("progress_bars") or []),
                warnings=[f"Environment health check failed: {exc}"],
            )
        rows = maintenance_health_rows(raw_rows)
        counts = maintenance_workspace_counts(rows)
        health_progress = maintenance_health_progress(resolved, rows, status="complete")
        self._set_maintenance_health_progress(health_progress)
        return _maintenance_workspace_dto(
            app_version=self.app_version,
            rows=rows,
            toolchain_evidence=maintenance_toolchain_evidence(rows),
            health_progress=health_progress,
            progress_bars=list(health_progress.get("progress_bars") or []),
            ok_count=counts["ok_count"],
            missing_count=counts["missing_count"],
            warning_count=counts["warning_count"],
        )

    def get_maintenance_change_ledger(self, resolved: ResolvedPaths) -> dict[str, Any]:
        return change_ledger_payload(resolved.workspace_root)

__all__ = [
    "MaintenanceFacadeMixin",
]
