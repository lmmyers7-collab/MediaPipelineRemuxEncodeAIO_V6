"""Settings facade helper mixin for schema, redaction, and diffs."""

from __future__ import annotations

import difflib
import json
from collections.abc import Mapping
from datetime import datetime
from pathlib import Path
from typing import Any

from app.config.metadata import CONFIG_FIELD_DEFINITIONS


def _json_safe(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.astimezone().isoformat() if value.tzinfo else value.isoformat()
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, Mapping):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, tuple | list):
        return [_json_safe(item) for item in value]
    if isinstance(value, set):
        return [_json_safe(item) for item in sorted(value, key=str)]
    return value


class SettingsHelperFacadeMixin:
    """Shared settings schema, redaction, and diff helpers."""

    def _settings_field_definitions(self) -> list[dict[str, Any]]:
        keys_to_copy = (
            "page",
            "section",
            "key",
            "label",
            "short_label",
            "kind",
            "choices",
            "default",
            "choice_help",
            "help",
            "help_text",
            "rule_taxonomy",
            "strictness",
            "unavailable_reason",
            "persisted_key",
            "override_group",
            "scope",
            "value_type",
            "allowed_values",
            "min",
            "max",
            "step",
            "unit",
            "default_source",
            "default_value",
            "library_override_allowed",
            "advanced_visibility",
            "validation_owner",
            "runtime_consumer",
            "migration_status",
        )
        definitions: list[dict[str, Any]] = []
        for field in CONFIG_FIELD_DEFINITIONS:
            definition = {key: _json_safe(field[key]) for key in keys_to_copy if key in field}
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
        return _json_safe(value)

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
        return json.dumps(_json_safe(value), ensure_ascii=False, indent=2, sort_keys=True)

__all__ = [
    "SettingsHelperFacadeMixin",
]
