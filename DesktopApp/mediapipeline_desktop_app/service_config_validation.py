from __future__ import annotations

import re
from typing import Any

from .config_keys import (
    KEY_BDPGS_OCR_TOOL_PATH,
    KEY_CONVERT_BDPGS_TO_SRT,
    KEY_MIN_FREE_SPACE_GB,
    KEY_OUTSOURCE_MIN_FREE_SPACE_GB,
    KEY_PROCESSED_INDEX_REFRESH_SECONDS,
    KEY_SOURCE_SCAN_INTERVAL_SECONDS,
)
from .service_config_option_policy import validate_option_config
from .service_config_path_warnings import (
    PathKeyFunc,
    PathWithinRootFunc,
    config_path_overlap_warning as config_path_overlap_warning_helper,
    config_root_path_warnings,
)
from .service_config_numeric_policy import validate_required_and_numeric_config


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
    errors: list[str] = []
    warnings: list[str] = []

    validate_required_and_numeric_config(values, errors)
    validate_option_config(values, errors, warnings)

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
    if isinstance(values.get(KEY_OUTSOURCE_MIN_FREE_SPACE_GB), int) and isinstance(values.get(KEY_MIN_FREE_SPACE_GB), int):
        if int(values[KEY_OUTSOURCE_MIN_FREE_SPACE_GB]) < int(values[KEY_MIN_FREE_SPACE_GB]):
            warnings.append("OutsourceMinFreeSpaceGB is lower than MinFreeSpaceGB.")
    if isinstance(values.get(KEY_PROCESSED_INDEX_REFRESH_SECONDS), int) and isinstance(values.get(KEY_SOURCE_SCAN_INTERVAL_SECONDS), int):
        if int(values[KEY_PROCESSED_INDEX_REFRESH_SECONDS]) and int(values[KEY_SOURCE_SCAN_INTERVAL_SECONDS]) and int(values[KEY_PROCESSED_INDEX_REFRESH_SECONDS]) < int(values[KEY_SOURCE_SCAN_INTERVAL_SECONDS]):
            warnings.append("ProcessedIndexRefreshSeconds is shorter than SourceScanIntervalSeconds.")
    return errors, warnings
