"""Completed-manifest backfill dry-run facade adapter."""

from __future__ import annotations

from pathlib import Path
import time
from typing import TYPE_CHECKING, Any

from app.maintenance.command_policy import (
    COMPLETED_BACKFILL_DRY_RUN_COMMAND,
    completed_backfill_dry_run_result,
    completed_backfill_exception_result,
    completed_backfill_unavailable_result,
    maintenance_command_blocked_result,
)
from mediapipeline_desktop_app.models import ResolvedPaths

if TYPE_CHECKING:
    from mediapipeline_desktop_app.application.dto_commands import CommandResult


class MaintenanceBackfillFacadeMixin:
    """Completed-manifest backfill dry-run command adapter for the application facade."""

    def run_completed_backfill_dry_run(self, resolved: ResolvedPaths, request: dict[str, Any]) -> CommandResult:
        """Run completed-manifest backfill in dry-run mode without rewriting the manifest."""
        backfill = getattr(self.service, "backfill_completed_manifest", None)
        if not callable(backfill):
            return completed_backfill_unavailable_result()
        timeout_seconds = self._bounded_timeout_seconds(request.get("timeout_seconds"), default=600, minimum=30, maximum=1800)
        lock, block_message = self._acquire_maintenance_command_lock("Completed manifest backfill dry run")
        if block_message:
            return maintenance_command_blocked_result(COMPLETED_BACKFILL_DRY_RUN_COMMAND, block_message)
        checkpoint_path = self._maintenance_checkpoint_path("completed_manifest_backfill_dry_run")
        try:
            ok, message = backfill(
                resolved,
                timeout_seconds=float(timeout_seconds),
                dry_run=True,
                checkpoint_path=checkpoint_path,
            )
        except TypeError:
            try:
                ok, message = backfill(
                    resolved,
                    timeout_seconds=float(timeout_seconds),
                    dry_run=True,
                )
                checkpoint_path = None
            except Exception as exc:
                return completed_backfill_exception_result(exc)
        except Exception as exc:
            return completed_backfill_exception_result(exc)
        finally:
            self._release_maintenance_command_lock(lock)
        return completed_backfill_dry_run_result(
            bool(ok),
            message,
            completed_manifest_path=resolved.completed_manifest_path,
            checkpoint_path=checkpoint_path,
            timeout_seconds=timeout_seconds,
        )

    def _maintenance_checkpoint_path(self, stem: str) -> Path:
        app_root = self._optional_path(getattr(self.service, "app_root", None)) or Path.cwd()
        run_logs = app_root / "RunLogs"
        try:
            run_logs.mkdir(parents=True, exist_ok=True)
            root = run_logs
        except OSError:
            root = Path.cwd()
        stamp = time.strftime("%Y%m%d_%H%M%S")
        return root / f"{stem}_{stamp}.json"

__all__ = [
    "MaintenanceBackfillFacadeMixin",
]
