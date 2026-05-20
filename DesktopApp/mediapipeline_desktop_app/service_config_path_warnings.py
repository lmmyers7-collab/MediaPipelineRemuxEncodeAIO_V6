from __future__ import annotations

from pathlib import Path
from typing import Callable, Any

from .config_keys import KEY_LOCAL_BASE, KEY_OUTSOURCE, KEY_SOURCE_MOVIES, KEY_SOURCE_TV
from .service_config_value_checks import add_unique_warning

PathKeyFunc = Callable[[Path], str]
PathWithinRootFunc = Callable[[Path, Path], bool]


def config_path_overlap_warning(
    left_key: str,
    right_key: str,
    path_values: dict[str, str],
    *,
    normalized_path_key: PathKeyFunc,
    path_within_root: PathWithinRootFunc,
) -> str | None:
    left_raw = path_values.get(left_key, "")
    right_raw = path_values.get(right_key, "")
    if not left_raw or not right_raw:
        return None
    left_path = Path(left_raw).expanduser()
    right_path = Path(right_raw).expanduser()
    if not left_path.is_absolute() or not right_path.is_absolute():
        return None
    if normalized_path_key(left_path) == normalized_path_key(right_path):
        if {left_key, right_key} == {KEY_SOURCE_MOVIES, KEY_SOURCE_TV}:
            return "SourceMovies and SourceTV point to the same location."
        if {left_key, right_key} == {KEY_LOCAL_BASE, KEY_OUTSOURCE}:
            return "LocalBase and Outsource are identical. That defeats scratch-vs-library separation."
        return f"{left_key} and {right_key} point to the same location."
    if path_within_root(left_path, right_path):
        return f"{left_key} is inside {right_key}. Keep source, output, and scratch roots separated."
    if path_within_root(right_path, left_path):
        return f"{right_key} is inside {left_key}. Keep source, output, and scratch roots separated."
    return None


def config_root_path_warnings(
    values: dict[str, Any],
    *,
    normalized_path_key: PathKeyFunc,
    path_within_root: PathWithinRootFunc,
) -> list[str]:
    warnings: list[str] = []
    path_values = {
        key: str(values.get(key, "") or "").strip().rstrip("\\/")
        for key in (KEY_SOURCE_MOVIES, KEY_SOURCE_TV, KEY_OUTSOURCE, KEY_LOCAL_BASE)
    }
    for key, path_text in path_values.items():
        if path_text and not Path(path_text).expanduser().is_absolute():
            add_unique_warning(warnings, f"{key} should be an absolute path.")

    for left_key, right_key in (
        (KEY_SOURCE_MOVIES, KEY_SOURCE_TV),
        (KEY_SOURCE_MOVIES, KEY_OUTSOURCE),
        (KEY_SOURCE_TV, KEY_OUTSOURCE),
        (KEY_LOCAL_BASE, KEY_SOURCE_MOVIES),
        (KEY_LOCAL_BASE, KEY_SOURCE_TV),
        (KEY_LOCAL_BASE, KEY_OUTSOURCE),
    ):
        warning = config_path_overlap_warning(
            left_key,
            right_key,
            path_values,
            normalized_path_key=normalized_path_key,
            path_within_root=path_within_root,
        )
        if warning:
            add_unique_warning(warnings, warning)
    return warnings
