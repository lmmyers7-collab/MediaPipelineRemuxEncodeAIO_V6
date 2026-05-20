from __future__ import annotations

from typing import Any

from ..models import ResolvedPaths
from .dto import json_safe
from .facade_settings_patch_policy import (
    settings_patch_changes_from_request,
    settings_patch_remove_keys_from_request,
)


class SettingsPatchCandidateFacadeMixin:
    """Settings patch candidate construction shared by preview and save commands."""

    def _settings_patch_candidate(self, resolved: ResolvedPaths, request: dict[str, Any], *, command: str) -> dict[str, Any]:
        raw_changes, fatal_result = settings_patch_changes_from_request(request, command=command)
        if fatal_result is not None:
            return {"fatal_result": fatal_result}
        raw_remove_keys, fatal_result = settings_patch_remove_keys_from_request(request, command=command)
        if fatal_result is not None:
            return {"fatal_result": fatal_result}
        base_config = dict(resolved.config_data or {})
        merged = dict(base_config)
        errors: list[str] = []
        warnings: list[str] = []
        changed_keys: list[str] = []
        removed_keys: list[str] = []

        for raw_key in raw_remove_keys:
            key = str(raw_key or "").strip()
            if not self._settings_patch_key_allowed(key):
                errors.append(f"Invalid remove key: {key!r}")
                continue
            if key in merged:
                merged.pop(key, None)
                removed_keys.append(key)

        for raw_key, value in raw_changes.items():
            key = str(raw_key or "").strip()
            if not self._settings_patch_key_allowed(key):
                errors.append(f"Invalid settings key: {key!r}")
                continue
            if self._is_sensitive_key(key) and str(value or "").strip() == "<redacted>":
                errors.append(f"{key} is sensitive and cannot be set to the redacted display placeholder.")
                continue
            safe_value = json_safe(value)
            if key in merged and json_safe(merged.get(key)) == safe_value:
                continue
            merged[key] = safe_value
            changed_keys.append(key)

        if not changed_keys and not removed_keys and not errors:
            warnings.append("No settings changes were proposed.")

        risk_summary = self._settings_patch_risk_summary(base_config, merged, changed_keys, removed_keys)
        warnings.extend(risk_summary.get("warning_messages", []))

        validator = getattr(self.service, "validate_config_values", None)
        if callable(validator):
            try:
                raw_errors, raw_warnings = validator(merged)
                errors.extend(str(item) for item in raw_errors)
                warnings.extend(str(item) for item in raw_warnings)
            except Exception as exc:
                errors.append(f"Settings validation failed: {exc}")
        else:
            warnings.append("Settings validation service is not available.")

        redacted_before = self._redacted_config(base_config)
        redacted_after = self._redacted_config(merged)
        diff_lines = self._redacted_settings_diff(redacted_before, redacted_after)
        return {
            "fatal_result": None,
            "base_config": base_config,
            "merged": merged,
            "errors": errors,
            "warnings": warnings,
            "changed_keys": changed_keys,
            "removed_keys": removed_keys,
            "diff_lines": diff_lines,
            "risk_summary": risk_summary,
        }

__all__ = [
    "SettingsPatchCandidateFacadeMixin",
]
