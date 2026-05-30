from __future__ import annotations

from typing import Any

from app.ui.preferences import read_ui_preferences, ui_preferences_path, write_ui_preferences


def _ui_preferences_unavailable(reason: str) -> dict[str, Any]:
    return {
        "schema_version": "desktop_ui_preferences.v1",
        "ok": False,
        "source": "unavailable",
        "message": f"UI preferences unavailable: {reason}",
        "storage": {},
    }


class LocalApiUiPreferencesPayloadMixin:
    def _ui_preferences_payload(self) -> dict[str, Any]:
        """GET /api/ui-preferences - return shared browser/Tauri UI preferences."""
        resolved = self._resolved()
        if resolved is None or resolved.state_root is None:
            return _ui_preferences_unavailable("state_root is not configured")
        payload = read_ui_preferences(ui_preferences_path(resolved.state_root))
        payload["ok"] = True
        return payload

    def _ui_preferences_save_payload(self, request: dict[str, Any]) -> dict[str, Any]:
        """POST /api/ui-preferences - persist shared browser/Tauri UI preferences."""
        resolved = self._resolved()
        if resolved is None or resolved.state_root is None:
            return _ui_preferences_unavailable("state_root is not configured")
        payload = write_ui_preferences(
            ui_preferences_path(resolved.state_root),
            request.get("storage"),
            source_surface=str(request.get("source_surface") or ""),
        )
        payload["ok"] = True
        return payload
