from __future__ import annotations

from typing import Any

from ..models import ResolvedPaths
from .dto import CommandResult
from .facade_maintenance_command_policy import (
    RELEASE_DRY_RUN_COMMAND,
    RELEASE_BUILD_COMMAND,
    maintenance_command_blocked_result,
    release_builder_unavailable_result,
    release_build_builder_kwargs,
    release_build_confirmation_required_result,
    release_build_exception_result,
    release_build_invalid_result,
    release_build_message,
    release_build_result,
    release_build_unavailable_result,
    release_dry_run_builder_kwargs,
    release_dry_run_exception_result,
    release_dry_run_invalid_result,
    release_dry_run_message,
    release_dry_run_result,
)


class MaintenanceReleaseFacadeMixin:
    """Release-package command adapter for the application facade."""

    def run_release_dry_run(self, request: dict[str, Any]) -> CommandResult:
        """Run the existing release builder in dry-run mode only."""
        builder = getattr(self.service, "build_release_package", None)
        if not callable(builder):
            return release_builder_unavailable_result()
        timeout_seconds = self._bounded_timeout_seconds(request.get("timeout_seconds"), default=900, minimum=30, maximum=1800)
        lock, block_message = self._acquire_maintenance_command_lock("Release dry run")
        if block_message:
            return maintenance_command_blocked_result(RELEASE_DRY_RUN_COMMAND, block_message)
        try:
            result = builder(**release_dry_run_builder_kwargs(request, timeout_seconds))
        except Exception as exc:
            return release_dry_run_exception_result(exc)
        finally:
            self._release_maintenance_command_lock(lock)
        if not isinstance(result, dict):
            return release_dry_run_invalid_result()
        return release_dry_run_result(result, request)

    def run_release_build(self, resolved: ResolvedPaths, request: dict[str, Any]) -> CommandResult:
        """Create a deployable release package through the existing backend builder."""
        if request.get("confirm_create") is not True:
            return release_build_confirmation_required_result()
        block_message = self._active_work_block_message(resolved, "Deployment build")
        if block_message:
            return maintenance_command_blocked_result(RELEASE_BUILD_COMMAND, block_message)
        builder = getattr(self.service, "build_release_package", None)
        if not callable(builder):
            return release_build_unavailable_result()
        timeout_seconds = self._bounded_timeout_seconds(request.get("timeout_seconds"), default=7200, minimum=30, maximum=14400)
        lock, lock_message = self._acquire_maintenance_command_lock("Deployment build")
        if lock_message:
            return maintenance_command_blocked_result(RELEASE_BUILD_COMMAND, lock_message)
        try:
            result = builder(**release_build_builder_kwargs(request, timeout_seconds))
        except Exception as exc:
            return release_build_exception_result(exc)
        finally:
            self._release_maintenance_command_lock(lock)
        if not isinstance(result, dict):
            return release_build_invalid_result()
        return release_build_result(result, request)

    def _release_dry_run_message(self, result: dict[str, Any]) -> str:
        return release_dry_run_message(result)

    def _release_build_message(self, result: dict[str, Any]) -> str:
        return release_build_message(result)

__all__ = [
    "MaintenanceReleaseFacadeMixin",
]
