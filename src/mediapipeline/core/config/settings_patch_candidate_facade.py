"""Settings patch candidate construction facade adapter."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from mediapipeline.core.kernel.config_keys import (
    KEY_RENAME_MOVIE_FILTER_OPTIONS,
    KEY_RENAME_MOVIE_FILTER_TERMS,
    KEY_RENAME_MOVIE_REMOVE_TERMS,
)
from mediapipeline.core.rename.policy import rename_cleaning_policy_from_config
from mediapipeline.core.config.settings_patch_policy import (
    settings_patch_changes_from_request,
    settings_patch_remove_keys_from_request,
)
from mediapipeline.core.config.library_profiles import (
    apply_library_profile_resets,
    library_profile_state_from_config,
    normalize_library_profile_config_values,
)
from mediapipeline.desktop.models import ResolvedPaths

if TYPE_CHECKING:
    from mediapipeline.desktop.application.dto_base import JsonMap


def _json_safe(value: Any) -> "JsonMap":
    from mediapipeline.desktop.application.dto_base import json_safe

    return json_safe(value)


_RENAME_CLEANING_POLICY_KEYS = {
    KEY_RENAME_MOVIE_FILTER_OPTIONS,
    KEY_RENAME_MOVIE_FILTER_TERMS,
    KEY_RENAME_MOVIE_REMOVE_TERMS,
}


def _normalize_rename_cleaning_policy_values(values: dict[str, Any], changed_keys: list[str]) -> None:
    if not any(key in values for key in _RENAME_CLEANING_POLICY_KEYS):
        return
    policy = rename_cleaning_policy_from_config(values)
    normalized_values = {
        KEY_RENAME_MOVIE_FILTER_OPTIONS: policy["movie_filter_options"],
        KEY_RENAME_MOVIE_FILTER_TERMS: policy["movie_filter_terms"],
        KEY_RENAME_MOVIE_REMOVE_TERMS: policy["remove_terms"],
    }
    for key in _RENAME_CLEANING_POLICY_KEYS:
        if key not in values:
            continue
        safe_value = _json_safe(normalized_values[key])
        if _json_safe(values.get(key)) == safe_value:
            continue
        values[key] = safe_value
        if key not in changed_keys:
            changed_keys.append(key)


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
            safe_value = _json_safe(value)
            if key in merged and _json_safe(merged.get(key)) == safe_value:
                continue
            merged[key] = safe_value
            changed_keys.append(key)

        raw_library_profile_resets = request.get("library_profile_resets")
        if raw_library_profile_resets:
            before_resets = _json_safe(merged.get("LibraryProfiles"))
            merged, reset_errors = apply_library_profile_resets(merged, raw_library_profile_resets)
            errors.extend(reset_errors)
            after_resets = _json_safe(merged.get("LibraryProfiles"))
            if before_resets != after_resets and "LibraryProfiles" not in changed_keys:
                changed_keys.append("LibraryProfiles")

        normalized = normalize_library_profile_config_values(merged, require_profiles=True)
        for key, value in normalized.items():
            safe_value = _json_safe(value)
            if key in merged and _json_safe(merged.get(key)) == safe_value:
                continue
            merged[key] = safe_value
            if key not in changed_keys and _json_safe(base_config.get(key)) != safe_value:
                changed_keys.append(key)

        _normalize_rename_cleaning_policy_values(merged, changed_keys)

        library_profile_state: list[dict[str, Any]] = []
        if "LibraryProfiles" in merged:
            try:
                library_profile_state = library_profile_state_from_config(merged)
            except Exception as exc:
                warnings.append(f"Library profile inheritance evidence unavailable: {exc}")

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
            "library_profile_state": library_profile_state,
        }

__all__ = [
    "SettingsPatchCandidateFacadeMixin",
]
