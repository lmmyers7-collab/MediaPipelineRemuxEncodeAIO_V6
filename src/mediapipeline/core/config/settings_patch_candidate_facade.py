"""Settings patch candidate construction facade adapter."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from mediapipeline.core.kernel.config_keys import (
    ALL_CONFIG_KEYS,
    KEY_BDPGS_OCR_TOOL_PATH,
    KEY_CONVERT_BDPGS_TO_SRT,
    KEY_CONVERT_VOBSUB_TO_SRT,
    KEY_OUTSOURCE,
    KEY_RENAME_MOVIE_FILTER_OPTIONS,
    KEY_RENAME_MOVIE_FILTER_TERMS,
    KEY_RENAME_MOVIE_REMOVE_TERMS,
    KEY_RENAME_TV_FILTER_OPTIONS,
    KEY_RENAME_TV_FILTER_TERMS,
    KEY_RENAME_TV_REMOVE_TERMS,
    KEY_VOBSUB_OCR_TOOL_PATH,
)
from mediapipeline.core.config.metadata_network import KEY_COORDINATOR_ALSO_ENCODE_LOCALLY
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
from mediapipeline.core.config.validation import (
    canonical_config_key_spelling_error,
    canonical_config_key_spelling_errors,
)
from mediapipeline.desktop.models import ResolvedPaths

if TYPE_CHECKING:
    from mediapipeline.desktop.application.dto_base import JsonMap


REGISTERED_CONFIG_KEYS = frozenset(ALL_CONFIG_KEYS)



def _json_safe(value: Any) -> "JsonMap":
    from mediapipeline.desktop.application.dto_base import json_safe

    return json_safe(value)


_RENAME_CLEANING_POLICY_KEYS = {
    KEY_RENAME_MOVIE_FILTER_OPTIONS,
    KEY_RENAME_MOVIE_FILTER_TERMS,
    KEY_RENAME_MOVIE_REMOVE_TERMS,
    KEY_RENAME_TV_FILTER_OPTIONS,
    KEY_RENAME_TV_FILTER_TERMS,
    KEY_RENAME_TV_REMOVE_TERMS,
}


def _normalize_rename_cleaning_policy_values(values: dict[str, Any], changed_keys: list[str]) -> None:
    if not any(key in values for key in _RENAME_CLEANING_POLICY_KEYS):
        return
    policy = rename_cleaning_policy_from_config(values)
    normalized_values = {
        KEY_RENAME_MOVIE_FILTER_OPTIONS: policy["movie_filter_options"],
        KEY_RENAME_MOVIE_FILTER_TERMS: policy["movie_filter_terms"],
        KEY_RENAME_MOVIE_REMOVE_TERMS: policy["remove_terms"],
        KEY_RENAME_TV_FILTER_OPTIONS: policy["tv_filter_options"],
        KEY_RENAME_TV_FILTER_TERMS: policy["tv_filter_terms"],
        KEY_RENAME_TV_REMOVE_TERMS: policy["tv_remove_terms"],
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


def _unique_strings(values: list[str]) -> list[str]:
    seen: set[str] = set()
    unique: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        unique.append(value)
    return unique


def _preserved_unknown_config_keys(values: dict[str, Any]) -> list[str]:
    keys: list[str] = []
    for raw_key in values:
        key = str(raw_key or "").strip()
        if not key or key in REGISTERED_CONFIG_KEYS:
            continue
        if canonical_config_key_spelling_error(key) is not None:
            continue
        keys.append(key)
    return sorted(set(keys))







def _truthy_patch_value(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, int | float):
        return value != 0
    return str(value or "").strip().casefold() in {"1", "true", "yes", "on", "enabled", "enable"}


def _coerce_network_patch_value(key: str, value: Any) -> Any:
    if key != KEY_COORDINATOR_ALSO_ENCODE_LOCALLY:
        return value
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().casefold()
        if normalized in {"true", "yes", "on"}:
            return True
        if normalized in {"false", "no", "off", ""}:
            return False
    return value


def _ocr_tool_path_errors(values: dict[str, Any], changed_keys: list[str]) -> list[str]:
    errors: list[str] = []
    changed = set(changed_keys)
    if (
        KEY_CONVERT_BDPGS_TO_SRT in changed or KEY_BDPGS_OCR_TOOL_PATH in changed
    ) and _truthy_patch_value(values.get(KEY_CONVERT_BDPGS_TO_SRT, False)):
        if not str(values.get(KEY_BDPGS_OCR_TOOL_PATH, "") or "").strip():
            errors.append("ConvertBdpgsToSrt requires BdpgsOcrToolPath.")
    if (
        KEY_CONVERT_VOBSUB_TO_SRT in changed or KEY_VOBSUB_OCR_TOOL_PATH in changed
    ) and _truthy_patch_value(values.get(KEY_CONVERT_VOBSUB_TO_SRT, False)):
        if not str(values.get(KEY_VOBSUB_OCR_TOOL_PATH, "") or "").strip():
            errors.append("ConvertVobSubToSrt requires VobSubOcrToolPath.")
    return errors


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
        preserved_unknown_keys = _preserved_unknown_config_keys(base_config)
        errors: list[str] = []
        warnings: list[str] = []
        changed_keys: list[str] = []
        removed_keys: list[str] = []

        for raw_key in raw_remove_keys:
            key = str(raw_key or "").strip()
            if not self._settings_patch_key_allowed(key):
                errors.append(f"Invalid remove key: {key!r}")
                continue
            spelling_error = canonical_config_key_spelling_error(key, context="remove key")
            if spelling_error:
                errors.append(spelling_error)
                continue
            if key not in REGISTERED_CONFIG_KEYS:
                errors.append(f"Unknown config key {key}. Use a registered backend config key.")
                continue
            if key in merged:
                merged.pop(key, None)
                removed_keys.append(key)

        for raw_key, value in raw_changes.items():
            key = str(raw_key or "").strip()
            if not self._settings_patch_key_allowed(key):
                errors.append(f"Invalid settings key: {key!r}")
                continue
            spelling_error = canonical_config_key_spelling_error(key)
            if spelling_error:
                errors.append(spelling_error)
                continue
            if self._is_sensitive_key(key) and str(value or "").strip() == "<redacted>":
                errors.append(f"{key} is sensitive and cannot be set to the redacted display placeholder.")
                continue
            safe_value = _json_safe(_coerce_network_patch_value(key, value))
            if self._source_mutation_setting(key, safe_value):
                errors.append(
                    f"{key} appears to enable source/original-file mutation and cannot be saved through Settings Patch."
                )
                continue
            if key not in REGISTERED_CONFIG_KEYS:
                errors.append(f"Unknown config key {key}. Use a registered backend config key.")
                continue
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
        if request.get("preserve_outsource_root") is True and KEY_OUTSOURCE in raw_changes:
            safe_outsource = _json_safe(raw_changes.get(KEY_OUTSOURCE))
            if _json_safe(merged.get(KEY_OUTSOURCE)) != safe_outsource:
                merged[KEY_OUTSOURCE] = safe_outsource
                if KEY_OUTSOURCE not in changed_keys and _json_safe(base_config.get(KEY_OUTSOURCE)) != safe_outsource:
                    changed_keys.append(KEY_OUTSOURCE)

        _normalize_rename_cleaning_policy_values(merged, changed_keys)

        errors.extend(canonical_config_key_spelling_errors(merged))
        errors.extend(_ocr_tool_path_errors(merged, changed_keys))

        library_profile_state: list[dict[str, Any]] = []
        if "LibraryProfiles" in merged:
            try:
                library_profile_state = library_profile_state_from_config(merged)
            except Exception as exc:
                warnings.append(f"Library profile inheritance evidence unavailable: {exc}")

        for key in preserved_unknown_keys:
            warnings.append(f"Existing unknown config key {key} is preserved but not validated.")

        if not changed_keys and not removed_keys and not errors:
            warnings.append("No settings changes were proposed.")

        risk_summary = self._settings_patch_risk_summary(base_config, merged, changed_keys, removed_keys)
        warnings.extend(risk_summary.get("warning_messages", []))

        validator = getattr(self.service, "validate_config_values", None)
        if callable(validator):
            try:
                validation_values = {key: value for key, value in merged.items() if key in REGISTERED_CONFIG_KEYS}
                raw_errors, raw_warnings = validator(validation_values)
                errors.extend(str(item) for item in raw_errors)
                warnings.extend(str(item) for item in raw_warnings)
            except Exception as exc:
                errors.append(f"Settings validation failed: {exc}")
        else:
            warnings.append("Settings validation service is not available.")
        errors = _unique_strings(errors)
        warnings = _unique_strings(warnings)

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
            "preserved_unknown_keys": preserved_unknown_keys,
        }


__all__ = [
    "SettingsPatchCandidateFacadeMixin",
]
