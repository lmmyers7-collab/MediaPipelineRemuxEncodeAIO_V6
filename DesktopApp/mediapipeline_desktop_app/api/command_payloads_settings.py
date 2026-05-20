from __future__ import annotations

from typing import Any

from .command_payloads_policy import (
    resolved_paths_unavailable_payload,
    settings_reload_exception_payload,
    settings_reload_missing_resolved_payload,
    settings_reload_success_payload,
    settings_reload_unavailable_payload,
    settings_save_reload_failure_payload,
    settings_save_reload_success_payload,
)


class LocalApiSettingsCommandPayloadMixin:
    def _settings_validate_payload(self, request: dict[str, Any]) -> dict[str, Any]:
        return self.facade.validate_settings_values(request).to_mapping()

    def _settings_preview_patch_payload(self, request: dict[str, Any]) -> dict[str, Any]:
        resolved = self._resolved()
        if resolved is None:
            return resolved_paths_unavailable_payload("settings.preview_patch", "settings")
        return self.facade.preview_settings_patch(resolved, request).to_mapping()

    def _settings_save_patch_payload(self, request: dict[str, Any]) -> dict[str, Any]:
        resolved = self._resolved()
        if resolved is None:
            return resolved_paths_unavailable_payload("settings.save_patch", "settings")
        payload = self.facade.save_settings_patch(resolved, request).to_mapping()
        if payload.get("ok") and self.resolved_reload is not None:
            try:
                reloaded = self.resolved_reload()
                payload = settings_save_reload_success_payload(payload, reloaded)
            except Exception as exc:
                self.logger.exception("local API settings reload after save failed")
                payload = settings_save_reload_failure_payload(payload, exc)
        return payload

    def _settings_reload_payload(self, request: dict[str, Any]) -> dict[str, Any]:
        _ = request
        if self.resolved_reload is None:
            return settings_reload_unavailable_payload()
        try:
            resolved = self.resolved_reload()
        except Exception as exc:
            self.logger.exception("local API settings reload failed")
            return settings_reload_exception_payload(exc)
        if resolved is None:
            return settings_reload_missing_resolved_payload()
        return settings_reload_success_payload(resolved)
