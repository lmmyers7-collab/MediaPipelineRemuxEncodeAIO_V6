"""Settings patch preview/save facade adapter."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from app.config.settings_patch_policy import (
    settings_patch_preview_result,
    settings_save_busy_result,
    settings_save_confirmation_required_result,
    settings_save_exception_result,
    settings_save_no_changes_result,
    settings_save_service_unavailable_result,
    settings_save_success_result,
    settings_save_validation_error_result,
)
from mediapipeline_desktop_app.models import ResolvedPaths

if TYPE_CHECKING:
    from mediapipeline_desktop_app.application.dto_commands import CommandResult


class SettingsPatchFacadeMixin:
    """Settings patch preview and save command adapters."""

    def preview_settings_patch(self, resolved: ResolvedPaths, request: dict[str, Any]) -> CommandResult:
        """Preview explicit settings changes without writing PSD1 config."""
        patch = self._settings_patch_candidate(resolved, request, command="settings.preview_patch")
        if patch["fatal_result"] is not None:
            return patch["fatal_result"]
        return settings_patch_preview_result(resolved, patch)

    def save_settings_patch(self, resolved: ResolvedPaths, request: dict[str, Any]) -> CommandResult:
        """Validate and save explicit settings changes to the active PSD1 config."""
        if not bool(request.get("confirm_save", False)):
            return settings_save_confirmation_required_result()
        lock, block_message = self._acquire_settings_save_lock()
        if block_message:
            return settings_save_busy_result(block_message)
        warnings: list[str] = []
        try:
            patch = self._settings_patch_candidate(resolved, request, command="settings.save_patch")
            if patch["fatal_result"] is not None:
                return patch["fatal_result"]
            errors = patch["errors"]
            warnings = patch["warnings"]
            changed_keys = patch["changed_keys"]
            removed_keys = patch["removed_keys"]
            if errors:
                return settings_save_validation_error_result(errors, warnings)
            if not changed_keys and not removed_keys:
                return settings_save_no_changes_result(warnings)
            serializer = getattr(self.service, "serialize_psd1_document", None)
            saver = getattr(self.service, "save_config_document", None)
            if not callable(serializer) or not callable(saver):
                return settings_save_service_unavailable_result()
            document_text = str(serializer(patch["merged"]))
            result = saver(
                resolved.config_path,
                document_text,
                True,
                config_values=patch["merged"],
                powershell_host=resolved.powershell_host,
            )
        except Exception as exc:
            return settings_save_exception_result(exc, warnings)
        finally:
            self._release_settings_save_lock(lock)
        return settings_save_success_result(result, patch, warnings)

    def _acquire_settings_save_lock(self) -> tuple[object | None, str]:
        lock = getattr(self, "_settings_save_lock", None)
        if lock is None:
            return None, ""
        try:
            acquired = lock.acquire(blocking=False)
        except Exception as exc:
            self._log_settings_save_exception("Settings save lock acquisition failed", exc)
            return None, f"Settings patch save blocked because the lock could not be verified: {exc}"
        if not acquired:
            return None, "Settings patch save blocked because another settings save command is already in progress."
        return lock, ""

    def _release_settings_save_lock(self, lock: object | None) -> None:
        if lock is None:
            return
        try:
            lock.release()  # type: ignore[attr-defined]
        except Exception as exc:
            self._log_settings_save_exception("Settings save lock release failed", exc)

    def _log_settings_save_exception(self, message: str, exc: Exception) -> None:
        logger = getattr(getattr(self, "service", None), "logger", None)
        if logger is None:
            return
        try:
            logger.warning("%s: %s", message, exc, exc_info=True)
        except Exception:
            return

__all__ = [
    "SettingsPatchFacadeMixin",
]
