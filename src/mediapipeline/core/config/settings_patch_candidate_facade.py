"""Settings patch candidate construction facade adapter."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from mediapipeline.core.kernel.config_keys import (
    ALL_CONFIG_KEYS,
    KEY_BDPGS_OCR_TOOL_PATH,
    KEY_CONVERT_BDPGS_TO_SRT,
    KEY_CONVERT_VOBSUB_TO_SRT,
    KEY_FINAL_LIBRARY_PROMOTION_RULES,
    KEY_LIBRARY_PROFILES,
    KEY_OUTSOURCE,
    KEY_RENAME_MOVIE_FILTER_OPTIONS,
    KEY_RENAME_MOVIE_FILTER_TERMS,
    KEY_RENAME_MOVIE_REMOVE_TERMS,
    KEY_RENAME_TV_FILTER_OPTIONS,
    KEY_RENAME_TV_FILTER_TERMS,
    KEY_RENAME_TV_REMOVE_TERMS,
    KEY_SOURCE_MOVIES,
    KEY_SOURCE_TV,
    KEY_VOBSUB_OCR_TOOL_PATH,
)
from mediapipeline.core.config.metadata_network import (
    KEY_COORDINATOR_ALSO_ENCODE_LOCALLY,
    KEY_COORDINATOR_AUTH_TOKEN,
    KEY_WORKER_AUTH_TOKEN,
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
from mediapipeline.core.config.validation import (
    canonical_config_key_spelling_error,
    canonical_config_key_spelling_errors,
)
from mediapipeline.core.paths.contracts import ResolvedPaths

if TYPE_CHECKING:
    from mediapipeline.core.kernel.dto_base import JsonMap


REGISTERED_CONFIG_KEYS = frozenset(ALL_CONFIG_KEYS)
NETWORK_CREDENTIAL_CONFIG_KEYS = frozenset(
    {
        KEY_COORDINATOR_AUTH_TOKEN,
        KEY_WORKER_AUTH_TOKEN,
    }
)
LIBRARY_PROFILE_MIRRORED_KEYS = frozenset(
    {
        KEY_SOURCE_MOVIES,
        KEY_SOURCE_TV,
        KEY_OUTSOURCE,
        KEY_FINAL_LIBRARY_PROMOTION_RULES,
    }
)


def _values_differ(left: Any, right: Any) -> bool:
    return _json_safe(left) != _json_safe(right)


def _reconciled_patch_delta_keys(
    base_config: dict[str, Any],
    merged: dict[str, Any],
    changed_keys: list[str],
    removed_keys: list[str],
) -> tuple[list[str], list[str]]:
    actual_removed: list[str] = []
    for key in _unique_strings(removed_keys):
        if key in REGISTERED_CONFIG_KEYS and key in base_config and key not in merged:
            actual_removed.append(key)

    removed = set(actual_removed)
    ordered_candidates = _unique_strings(
        [
            *changed_keys,
            *[
                str(key)
                for key in ALL_CONFIG_KEYS
                if str(key) in base_config or str(key) in merged
            ],
        ]
    )
    actual_changed: list[str] = []
    for key in ordered_candidates:
        if key in removed or key not in REGISTERED_CONFIG_KEYS or key not in merged:
            continue
        if key not in base_config or _values_differ(base_config.get(key), merged.get(key)):
            actual_changed.append(key)
    return actual_changed, actual_removed


def _review_entry_source(key: str, raw_changes: dict[str, Any], raw_remove_keys: list[Any]) -> str:
    raw_change_keys = {str(item or "").strip() for item in raw_changes.keys()}
    if key in {str(item or "").strip() for item in raw_remove_keys}:
        return "removed"
    if key in raw_change_keys:
        return "submitted"
    if KEY_LIBRARY_PROFILES in raw_change_keys and key in LIBRARY_PROFILE_MIRRORED_KEYS:
        return "mirrored_from_library_profiles"
    return "backend_normalized"


def _raw_change_value(raw_changes: dict[str, Any], key: str) -> Any:
    for raw_key, value in raw_changes.items():
        if str(raw_key or "").strip() == key:
            return value
    return None



def _json_safe(value: Any) -> JsonMap:
    from mediapipeline.core.kernel.dto_base import json_safe

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

    def _settings_patch_review_entries(
        self,
        base_config: dict[str, Any],
        merged: dict[str, Any],
        raw_changes: dict[str, Any],
        raw_remove_keys: list[Any],
        changed_keys: list[str],
        removed_keys: list[str],
    ) -> list[dict[str, Any]]:
        entries: list[dict[str, Any]] = []
        actual_keys = _unique_strings([*changed_keys, *removed_keys])
        removed = set(removed_keys)
        raw_change_keys = {str(item or "").strip() for item in raw_changes.keys()}
        for key in actual_keys:
            current_exists = key in base_config
            new_exists = key in merged and key not in removed
            submitted_exists = key in raw_change_keys
            if key in removed:
                status = "removed"
            elif current_exists:
                status = "changed"
            else:
                status = "new"
            entries.append(
                {
                    "key": key,
                    "status": status,
                    "source": _review_entry_source(key, raw_changes, raw_remove_keys),
                    "current_exists": current_exists,
                    "new_exists": new_exists,
                    "submitted_exists": submitted_exists,
                    "current_value": self._redacted_config(base_config.get(key), key) if current_exists else None,
                    "submitted_value": self._redacted_config(_raw_change_value(raw_changes, key), key) if submitted_exists else None,
                    "new_value": self._redacted_config(merged.get(key), key) if new_exists else None,
                }
            )
        return entries

    def _settings_patch_candidate(
        self,
        resolved: ResolvedPaths,
        request: dict[str, Any],
        *,
        command: str,
        allow_network_credentials: bool = False,
    ) -> dict[str, Any]:
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
        raw_library_profile_resets = request.get("library_profile_resets")
        request_evidence = {
            "changes": self._redacted_config(raw_changes),
            "remove_keys": _json_safe(raw_remove_keys),
            "library_profile_resets": _json_safe(raw_library_profile_resets or []),
            "preserve_outsource_root": request.get("preserve_outsource_root") is True,
        }

        for raw_key in raw_remove_keys:
            key = str(raw_key or "").strip()
            if not self._settings_patch_key_allowed(key):
                errors.append(f"Invalid remove key: {key!r}")
                continue
            spelling_error = canonical_config_key_spelling_error(key, context="remove key")
            if spelling_error:
                errors.append(spelling_error)
                continue
            if key in NETWORK_CREDENTIAL_CONFIG_KEYS and not allow_network_credentials:
                errors.append(f"{key} cannot be changed through Settings Patch; use the backend network credential workflow.")
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
            if key in NETWORK_CREDENTIAL_CONFIG_KEYS and not allow_network_credentials:
                errors.append(f"{key} cannot be changed through Settings Patch; use the backend network credential workflow.")
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
        changed_keys, removed_keys = _reconciled_patch_delta_keys(
            base_config,
            merged,
            changed_keys,
            removed_keys,
        )

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
        review_entries = self._settings_patch_review_entries(
            base_config,
            merged,
            raw_changes,
            raw_remove_keys,
            changed_keys,
            removed_keys,
        )
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
            "review_entries": review_entries,
            "request_evidence": request_evidence,
        }


__all__ = [
    "SettingsPatchCandidateFacadeMixin",
]
