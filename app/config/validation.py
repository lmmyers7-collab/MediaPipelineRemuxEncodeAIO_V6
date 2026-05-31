from __future__ import annotations

import json
import re
from typing import Any

from mediapipeline_desktop_app.config_keys import (
    KEY_BDPGS_OCR_TOOL_PATH,
    KEY_CONVERT_BDPGS_TO_SRT,
    KEY_CONVERT_VOBSUB_TO_SRT,
    KEY_FINAL_LIBRARY_PROMOTION_CLEANUP_AFTER_VERIFIED,
    KEY_FINAL_LIBRARY_PROMOTION_ENABLED,
    KEY_FINAL_LIBRARY_PROMOTION_OVERWRITE_EXISTING,
    KEY_FINAL_LIBRARY_PROMOTION_RULES,
    KEY_FINAL_LIBRARY_PROMOTION_VERIFICATION_MODE,
    KEY_LIBRARY_PROFILES,
    KEY_MIN_FREE_SPACE_GB,
    KEY_OUTSOURCE_MIN_FREE_SPACE_GB,
    KEY_PROCESSED_INDEX_REFRESH_SECONDS,
    KEY_SOURCE_SCAN_INTERVAL_SECONDS,
    KEY_VOBSUB_OCR_TOOL_PATH,
)
from app.config.library_profiles import (
    mirror_legacy_keys_from_library_profiles,
    normalize_library_profile_config_values,
    validate_library_profiles,
    validate_raw_library_profile_override_groups,
)
from app.config.option_policy import validate_option_config
from app.config.path_warnings import (
    PathKeyFunc,
    PathWithinRootFunc,
    config_path_overlap_warning as config_path_overlap_warning_helper,
    config_root_path_warnings,
)
from app.config.numeric_policy import validate_required_and_numeric_config
from app.config.preset_migration import FRIENDLY_LABEL_PERSISTED_KEY_ALIASES

EVIDENCE_ONLY_CONFIG_KEYS = {
    "library_effective_settings",
    "runtime_effective_settings",
}


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


def bdpgs_ocr_path_warning(values: dict[str, Any]) -> str | None:
    if not truthy_config_value(values.get(KEY_CONVERT_BDPGS_TO_SRT, False)):
        return None
    tool_path = str(values.get(KEY_BDPGS_OCR_TOOL_PATH, "") or "").strip()
    if tool_path:
        return None
    return "BdpgsOcrToolPath is blank while ConvertBdpgsToSrt is enabled; BDPGS OCR will be blocked until a bundled or configured OCR tool path is saved."


def vobsub_ocr_path_warning(values: dict[str, Any]) -> str | None:
    if not truthy_config_value(values.get(KEY_CONVERT_VOBSUB_TO_SRT, False)):
        return None
    tool_path = str(values.get(KEY_VOBSUB_OCR_TOOL_PATH, "") or "").strip()
    if tool_path:
        return None
    return "VobSubOcrToolPath is blank while ConvertVobSubToSrt is enabled; VobSub OCR will be blocked until Subtitle Edit seconv.exe is configured."


def _coerce_promotion_rules(raw: Any) -> list[dict[str, Any]]:
    if raw in (None, "", False):
        return []
    if isinstance(raw, str):
        text = raw.strip()
        if not text:
            return []
        raw = json.loads(text)
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
    validate_raw_library_profile_override_groups(raw_values, raw_errors)
    values = normalize_library_profile_config_values(raw_values)
    values = mirror_legacy_keys_from_library_profiles(values)
    errors: list[str] = list(raw_errors)
    warnings: list[str] = []

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

    warnings.extend(
        config_root_path_warnings(
            values,
            normalized_path_key=normalized_path_key,
            path_within_root=path_within_root,
        )
    )
    bdpgs_warning = bdpgs_ocr_path_warning(values)
    if bdpgs_warning:
        warnings.append(bdpgs_warning)
    vobsub_warning = vobsub_ocr_path_warning(values)
    if vobsub_warning:
        warnings.append(vobsub_warning)
    if isinstance(values.get(KEY_OUTSOURCE_MIN_FREE_SPACE_GB), int) and isinstance(values.get(KEY_MIN_FREE_SPACE_GB), int):
        if int(values[KEY_OUTSOURCE_MIN_FREE_SPACE_GB]) < int(values[KEY_MIN_FREE_SPACE_GB]):
            warnings.append("OutsourceMinFreeSpaceGB is lower than MinFreeSpaceGB.")
    if isinstance(values.get(KEY_PROCESSED_INDEX_REFRESH_SECONDS), int) and isinstance(values.get(KEY_SOURCE_SCAN_INTERVAL_SECONDS), int):
        if int(values[KEY_PROCESSED_INDEX_REFRESH_SECONDS]) and int(values[KEY_SOURCE_SCAN_INTERVAL_SECONDS]) and int(values[KEY_PROCESSED_INDEX_REFRESH_SECONDS]) < int(values[KEY_SOURCE_SCAN_INTERVAL_SECONDS]):
            warnings.append("ProcessedIndexRefreshSeconds is shorter than SourceScanIntervalSeconds.")
    return errors, warnings
