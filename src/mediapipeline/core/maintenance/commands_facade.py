"""Shared maintenance command facade helpers."""

from __future__ import annotations

from mediapipeline.core.maintenance.command_policy import release_stdout_value


class MaintenanceCommandFacadeMixin:
    """Shared maintenance command helpers for the application facade."""

    @staticmethod
    def _release_stdout_value(stdout: str, label: str) -> str:
        return release_stdout_value(stdout, label)

    def _acquire_maintenance_command_lock(self, action: str) -> tuple[object | None, str]:
        lock = getattr(self, "_maintenance_command_lock", None)
        if lock is None:
            return None, ""
        try:
            acquired = lock.acquire(blocking=False)
        except Exception as exc:
            self._log_maintenance_command_exception("Maintenance command lock acquisition failed", exc)
            return None, f"{action} blocked because the maintenance command lock could not be verified: {exc}"
        if not acquired:
            return None, f"{action} blocked because another maintenance command is already in progress."
        return lock, ""

    def _release_maintenance_command_lock(self, lock: object | None) -> None:
        if lock is None:
            return
        try:
            lock.release()  # type: ignore[attr-defined]
        except Exception as exc:
            self._log_maintenance_command_exception("Maintenance command lock release failed", exc)

    def _log_maintenance_command_exception(self, message: str, exc: Exception) -> None:
        logger = getattr(getattr(self, "service", None), "logger", None)
        if logger is None:
            return
        try:
            logger.warning("%s: %s", message, exc, exc_info=True)
        except Exception:
            return

__all__ = [
    "MaintenanceCommandFacadeMixin",
]
