from __future__ import annotations

import difflib
import json
from pathlib import Path
from typing import Any

from ..config_schema import CONFIG_FIELD_DEFINITIONS
from .dto import json_safe


class SettingsHelperFacadeMixin:
    """Shared settings schema, redaction, and diff helpers."""

    def _settings_field_definitions(self) -> list[dict[str, Any]]:
        keys_to_copy = ("page", "section", "key", "label", "kind", "choices", "default", "choice_help", "help")
        definitions: list[dict[str, Any]] = []
        for field in CONFIG_FIELD_DEFINITIONS:
            definition = {key: json_safe(field[key]) for key in keys_to_copy if key in field}
            definitions.append(definition)
        return definitions

    @classmethod
    def _redacted_config(cls, value: Any, key_name: str = "") -> Any:
        if cls._is_sensitive_key(key_name):
            return "<redacted>" if value not in (None, "") else ""
        if isinstance(value, dict):
            return {str(key): cls._redacted_config(item, str(key)) for key, item in value.items()}
        if isinstance(value, list):
            return [cls._redacted_config(item, key_name) for item in value]
        return json_safe(value)

    @staticmethod
    def _is_sensitive_key(key: str) -> bool:
        normalized = str(key or "").casefold()
        return any(token in normalized for token in ("token", "password", "secret", "credential", "api_key", "apikey"))

    @staticmethod
    def _config_path_value(config: dict[str, Any], key: str) -> Path | None:
        raw = str(config.get(key) or "").strip()
        return Path(raw) if raw else None

    @staticmethod
    def _settings_patch_key_allowed(key: str) -> bool:
        if not key or len(key) > 128:
            return False
        return not any(ord(char) < 32 for char in key)

    def _redacted_settings_diff(self, before: Any, after: Any) -> list[str]:
        before_text = self._redacted_settings_text(before)
        after_text = self._redacted_settings_text(after)
        return list(
            difflib.unified_diff(
                before_text.splitlines(),
                after_text.splitlines(),
                fromfile="saved-config",
                tofile="preview-config",
                lineterm="",
            )
        )

    def _redacted_settings_text(self, value: Any) -> str:
        serializer = getattr(self.service, "serialize_psd1_document", None)
        if callable(serializer):
            try:
                return str(serializer(value))
            except Exception as exc:
                logger = getattr(self.service, "logger", None)
                if logger is not None:
                    try:
                        logger.warning("Settings PSD1 serialization failed for redacted diff; falling back to JSON: %s", exc, exc_info=True)
                    except Exception:
                        pass
        return json.dumps(json_safe(value), ensure_ascii=False, indent=2, sort_keys=True)

__all__ = [
    "SettingsHelperFacadeMixin",
]
