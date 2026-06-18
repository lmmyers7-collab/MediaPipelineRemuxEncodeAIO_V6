from __future__ import annotations

import re
from typing import Any

from pydantic import ValidationError

from mediapipeline.core.kernel.config_key_aliases import CONFIG_KEY_ALIASES
from mediapipeline.core.kernel.config_key_order import ALL_CONFIG_KEYS
from mediapipeline.core.kernel.config_keys import (
    KEY_BDPGS_OCR_TOOL_PATH,
    KEY_CONVERT_BDPGS_TO_SRT,
    KEY_CONVERT_VOBSUB_TO_SRT,
    KEY_FINAL_LIBRARY_PROMOTION_CLEANUP_AFTER_VERIFIED,
    KEY_FINAL_LIBRARY_PROMOTION_ENABLED,
    KEY_FINAL_LIBRARY_PROMOTION_OVERWRITE_EXISTING,
    KEY_FINAL_LIBRARY_PROMOTION_RULES,
    KEY_FINAL_LIBRARY_PROMOTION_VERIFICATION_MODE,
    KEY_LIBRARY_PROFILES,
    KEY_LOCAL_BASE,
    KEY_MIN_FREE_SPACE_GB,
    KEY_OUTSOURCE,
    KEY_OUTSOURCE_MIN_FREE_SPACE_GB,
    KEY_PROCESSED_INDEX_REFRESH_SECONDS,
    KEY_SOURCE_MOVIES,
    KEY_SOURCE_SCAN_INTERVAL_SECONDS,
    KEY_SOURCE_TV,
    KEY_VOBSUB_OCR_TOOL_PATH,
)
from mediapipeline.core.config.library_profiles import (
    mirror_legacy_keys_from_library_profiles,
    normalize_library_profile_config_values,
    validate_library_profiles,
    validate_raw_library_profile_override_groups,
)
from mediapipeline.core.config.option_policy import validate_option_config
from mediapipeline.core.config.path_warnings import (
    PathKeyFunc,
    PathWithinRootFunc,
    config_path_overlap_warning as config_path_overlap_warning_helper,
    config_root_path_errors,
    config_root_path_warnings,
)
from mediapipeline.core.config.numeric_policy import validate_required_and_numeric_config
from mediapipeline.core.config.preset_migration import FRIENDLY_LABEL_PERSISTED_KEY_ALIASES
from mediapipeline.core.validation.strict_json import loads_strict_json

EVIDENCE_ONLY_CONFIG_KEYS = {
    "library_effective_settings",
    "runtime_effective_settings",
}
_STRICT_ROOT_PATH_ERROR_PAIRS = (
    (KEY_LOCAL_BASE, KEY_OUTSOURCE),
    (KEY_LOCAL_BASE, KEY_SOURCE_MOVIES),
    (KEY_LOCAL_BASE, KEY_SOURCE_TV),
    (KEY_OUTSOURCE, KEY_SOURCE_MOVIES),
    (KEY_OUTSOURCE, KEY_SOURCE_TV),
)
_CANONICAL_CONFIG_KEYS_BY_CASEFOLD = {str(key).casefold(): str(key) for key in ALL_CONFIG_KEYS}
_CONFIG_KEY_ALIASES_BY_CASEFOLD = {
    str(alias).casefold(): str(target) for alias, target in CONFIG_KEY_ALIASES.items()
}


def _canonical_config_key_for(key: str) -> str | None:
    normalized = str(key or "").strip().casefold()
    if not normalized:
        return None
    canonical = _CANONICAL_CONFIG_KEYS_BY_CASEFOLD.get(normalized)
    if canonical:
        return canonical
    alias_target = _CONFIG_KEY_ALIASES_BY_CASEFOLD.get(normalized)
    if alias_target:
        return _CANONICAL_CONFIG_KEYS_BY_CASEFOLD.get(alias_target.casefold(), alias_target)
    return None


def canonical_config_key_spelling_error(raw_key: object, *, context: str = "settings key") -> str | None:
    key = str(raw_key or "").strip()
    canonical = _canonical_config_key_for(key)
    if canonical and key != canonical:
        return f"Invalid {context}: {key!r}; use canonical key {canonical}."
    return None


def canonical_config_key_spelling_errors(values: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    seen: dict[str, str] = {}
    for raw_key in values:
        key = str(raw_key or "").strip()
        if not key:
            continue
        spelling_error = canonical_config_key_spelling_error(key)
        if spelling_error:
            errors.append(spelling_error)
        canonical = _canonical_config_key_for(key)
        if not canonical:
            continue
        previous = seen.get(canonical)
        if previous is not None and previous != key:
            errors.append(
                f"Config contains duplicate keys for {canonical}: {previous!r} and {key!r}; use only canonical key {canonical}."
            )
            continue
        seen[canonical] = key
    return errors


def _config_contract_error_messages(exc: ValidationError) -> list[str]:
    errors: list[str] = []
    for item in exc.errors():
        ctx = item.get("ctx") if isinstance(item, dict) else None
        ctx_error = ctx.get("error") if isinstance(ctx, dict) else None
        if ctx_error is not None:
            message = str(ctx_error)
        else:
            message = str(item.get("msg") or "Config contract validation failed.")
            if message.startswith("Value error, "):
                message = message.removeprefix("Value error, ")
        loc = item.get("loc") if isinstance(item, dict) else None
        if loc:
            errors.append(f"{'.'.join(str(part) for part in loc)}: {message}")
        else:
            errors.append(message)
    return errors


def _validated_config_contract_values(values: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
    from mediapipeline.contracts.config import Config

    try:
        config = Config.model_validate(values)
    except ValidationError as exc:
        return None, _config_contract_error_messages(exc)
    return config.model_dump(mode="python"), []


def _unique_strings(values: list[str]) -> list[str]:
    seen: set[str] = set()
    unique: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        unique.append(value)
    return unique


def _root_path_warning_promoted_to_error(warning: str) -> bool:
    for left_key, right_key in _STRICT_ROOT_PATH_ERROR_PAIRS:
        if warning in {
            f"{left_key} and {right_key} point to the same location.",
            f"{right_key} and {left_key} point to the same location.",
            f"{left_key} is inside {right_key}. Keep source, output, and scratch roots separated.",
            f"{right_key} is inside {left_key}. Keep source, output, and scratch roots separated.",
        }:
            return True
        if {left_key, right_key} == {KEY_LOCAL_BASE, KEY_OUTSOURCE} and warning == (
            "LocalBase and Outsource are identical. That defeats scratch-vs-library separation."
        ):
            return True
    return False


def split_list_input(raw: str) -> list[str]:
    values: list[str] = []
    for piece in re.split(r"[\r\n,]+", raw or ""):
        item = piece.strip()
        if item:
            values.append(item)
    return values


def truthy_config_value(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, int | float):
        return value != 0
    return str(value or "").strip().casefold() in {"1", "true", "yes", "on", "enabled", "enable"}


def bdpgs_ocr_path_error(values: dict[str, Any]) -> str | None:
    if not truthy_config_value(values.get(KEY_CONVERT_BDPGS_TO_SRT, False)):
        return None
    tool_path = str(values.get(KEY_BDPGS_OCR_TOOL_PATH, "") or "").strip()
    if tool_path:
        return None
    return "ConvertBdpgsToSrt requires BdpgsOcrToolPath."


def vobsub_ocr_path_error(values: dict[str, Any]) -> str | None:
    if not truthy_config_value(values.get(KEY_CONVERT_VOBSUB_TO_SRT, False)):
        return None
    tool_path = str(values.get(KEY_VOBSUB_OCR_TOOL_PATH, "") or "").strip()
    if tool_path:
        return None
    return "ConvertVobSubToSrt requires VobSubOcrToolPath."


def _coerce_promotion_rules(raw: Any) -> list[dict[str, Any]]:
    if raw in (None, "", False):
        return []
    if isinstance(raw, str):
        text = raw.strip()
        if not text:
            return []
        raw = loads_strict_json(text)
    if isinstance(raw, dict):
        raw = [raw]
    if not isinstance(raw, list):
        raise TypeError("FinalLibraryPromotionRules must be a JSON array or object.")
    rules: list[dict[str, Any]] = []
    for item in raw:
        if not isinstance(item, dict):
            raise TypeError("FinalLibraryPromotionRules entries must be objects.")
        rules.append(dict(item))
    return rules


def validate_final_library_promotion_config(values: dict[str, Any], errors: list[str], warnings: list[str]) -> None:
    mode = str(values.get(KEY_FINAL_LIBRARY_PROMOTION_VERIFICATION_MODE, "cautious") or "cautious").strip().casefold()
    if mode not in {"fast", "cautious"}:
        errors.append("FinalLibraryPromotionVerificationMode must be fast or cautious.")

    try:
        rules = _coerce_promotion_rules(values.get(KEY_FINAL_LIBRARY_PROMOTION_RULES))
    except Exception as exc:
        errors.append(f"FinalLibraryPromotionRules is invalid: {exc}")
        rules = []

    if truthy_config_value(values.get(KEY_FINAL_LIBRARY_PROMOTION_ENABLED, False)) and not rules:
        warnings.append("FinalLibraryPromotionEnabled is on, but no source-to-destination rules are configured.")

    for index, rule in enumerate(rules, start=1):
        label = str(rule.get("label") or rule.get("id") or f"rule {index}").strip()
        if rule.get("enabled", True) is False:
            continue
        if not str(rule.get("source_root") or "").strip():
            warnings.append(f"Final Library Promotion {label} is enabled without a source_root.")
        if not str(rule.get("destination_root") or "").strip():
            warnings.append(f"Final Library Promotion {label} is enabled without a destination_root.")

    if truthy_config_value(values.get(KEY_FINAL_LIBRARY_PROMOTION_OVERWRITE_EXISTING, False)):
        warnings.append("FinalLibraryPromotionOverwriteExisting is destructive: existing final files are deleted before replacement copy starts.")
    if truthy_config_value(values.get(KEY_FINAL_LIBRARY_PROMOTION_CLEANUP_AFTER_VERIFIED, False)):
        warnings.append("FinalLibraryPromotionCleanupAfterVerified deletes verified publish-output files below Outsource after promotion.")


def config_path_overlap_warning(
    left_key: str,
    right_key: str,
    path_values: dict[str, str],
    *,
    normalized_path_key: PathKeyFunc,
    path_within_root: PathWithinRootFunc,
) -> str | None:
    return config_path_overlap_warning_helper(
        left_key,
        right_key,
        path_values,
        normalized_path_key=normalized_path_key,
        path_within_root=path_within_root,
    )


def validate_config_values(
    values: dict[str, Any],
    *,
    normalized_path_key: PathKeyFunc,
    path_within_root: PathWithinRootFunc,
) -> tuple[list[str], list[str]]:
    raw_values = dict(values or {})
    had_library_profiles = KEY_LIBRARY_PROFILES in raw_values
    raw_errors: list[str] = []
    raw_errors.extend(canonical_config_key_spelling_errors(raw_values))
    validate_raw_library_profile_override_groups(raw_values, raw_errors)
    _raw_contract_values, raw_contract_errors = _validated_config_contract_values(raw_values)
    raw_errors.extend(raw_contract_errors)
    values = normalize_library_profile_config_values(raw_values)
    values = mirror_legacy_keys_from_library_profiles(values)
    errors: list[str] = list(raw_errors)
    warnings: list[str] = []
    contract_values, contract_errors = _validated_config_contract_values(values)
    errors.extend(contract_errors)
    if contract_values is not None:
        values = contract_values

    for key in sorted(set(raw_values) & set(FRIENDLY_LABEL_PERSISTED_KEY_ALIASES)):
        persisted_key = FRIENDLY_LABEL_PERSISTED_KEY_ALIASES[key]
        errors.append(f"{key} is a display label only; use persisted key {persisted_key}.")

    for key in sorted(set(raw_values) & EVIDENCE_ONLY_CONFIG_KEYS):
        errors.append(f"{key} is diagnostic evidence only; it is not a persisted config key.")

    validate_required_and_numeric_config(values, errors)
    validate_option_config(values, errors, warnings)
    validate_final_library_promotion_config(values, errors, warnings)
    validate_library_profiles(
        values,
        errors,
        warnings,
        normalized_path_key=normalized_path_key,
        path_within_root=path_within_root,
    )
    if had_library_profiles:
        warnings.append("LibraryProfiles mirrors its primary Movie/TV paths back to SourceMovies, SourceTV, and Outsource for compatibility during the transition.")

    root_path_errors = config_root_path_errors(
        values,
        normalized_path_key=normalized_path_key,
        path_within_root=path_within_root,
    )
    errors.extend(root_path_errors)
    warnings.extend(
        warning
        for warning in config_root_path_warnings(
            values,
            normalized_path_key=normalized_path_key,
            path_within_root=path_within_root,
        )
        if not _root_path_warning_promoted_to_error(warning)
    )
    bdpgs_error = bdpgs_ocr_path_error(values)
    if bdpgs_error and bdpgs_error not in errors:
        errors.append(bdpgs_error)
    vobsub_error = vobsub_ocr_path_error(values)
    if vobsub_error and vobsub_error not in errors:
        errors.append(vobsub_error)
    if isinstance(values.get(KEY_OUTSOURCE_MIN_FREE_SPACE_GB), int) and isinstance(values.get(KEY_MIN_FREE_SPACE_GB), int):
        if int(values[KEY_OUTSOURCE_MIN_FREE_SPACE_GB]) < int(values[KEY_MIN_FREE_SPACE_GB]):
            warnings.append("OutsourceMinFreeSpaceGB is lower than MinFreeSpaceGB.")
    if isinstance(values.get(KEY_PROCESSED_INDEX_REFRESH_SECONDS), int) and isinstance(values.get(KEY_SOURCE_SCAN_INTERVAL_SECONDS), int):
        if int(values[KEY_PROCESSED_INDEX_REFRESH_SECONDS]) and int(values[KEY_SOURCE_SCAN_INTERVAL_SECONDS]) and int(values[KEY_PROCESSED_INDEX_REFRESH_SECONDS]) < int(values[KEY_SOURCE_SCAN_INTERVAL_SECONDS]):
            warnings.append("ProcessedIndexRefreshSeconds is shorter than SourceScanIntervalSeconds.")
    return _unique_strings(errors), _unique_strings(warnings)
