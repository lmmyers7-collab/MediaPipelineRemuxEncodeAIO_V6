from __future__ import annotations

from typing import Any

from mediapipeline.core.ui_preferences import (
    UI_PREFERENCES_SCHEMA_VERSION,
    read_ui_preferences,
    ui_preferences_path,
    write_ui_preferences,
)


def _ui_preferences_unavailable(reason: str, *, source: str = "unavailable") -> dict[str, Any]:
    return {
        "schema_version": UI_PREFERENCES_SCHEMA_VERSION,
        "ok": False,
        "source": source,
        "message": f"UI preferences unavailable: {reason}",
        "storage": {},
    }


def _ui_preferences_os_error_summary(exc: OSError) -> str:
    detail = str(getattr(exc, "strerror", "") or "").strip() or exc.__class__.__name__
    code = getattr(exc, "winerror", None) or getattr(exc, "errno", None)
    code_suffix = f" ({code})" if code else ""
    return f"{exc.__class__.__name__}{code_suffix}: {detail}"


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
        try:
            payload = write_ui_preferences(
                ui_preferences_path(resolved.state_root),
                request.get("storage"),
                source_surface=str(request.get("source_surface") or ""),
            )
        except OSError as exc:
            return _ui_preferences_unavailable(
                f"could not write state file: {_ui_preferences_os_error_summary(exc)}",
                source="write_failed",
            )
        payload["ok"] = True
        return payload
