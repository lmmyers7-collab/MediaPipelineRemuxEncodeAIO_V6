from __future__ import annotations

import os
from pathlib import Path
from typing import Callable, Any

from mediapipeline_desktop_app.config_keys import KEY_LOCAL_BASE, KEY_OUTSOURCE, KEY_SOURCE_MOVIES, KEY_SOURCE_TV
from app.config.value_checks import add_unique_warning

PathKeyFunc = Callable[[Path], str]
PathWithinRootFunc = Callable[[Path, Path], bool]


def normalized_config_warning_path_key(path: Any) -> str:
    """Return a lexical path key for read-only config warnings.

    Settings validation must not resolve paths because UNC roots can block the
    WebView while offline. Mutation safety checks use app.paths.layout instead.
    """
    text = str(path or "").strip()
    if not text:
        return ""
    try:
        expanded = str(Path(text).expanduser())
    except (OSError, RuntimeError, ValueError):
        expanded = text
    try:
        path_text = os.path.abspath(os.path.normpath(expanded))
    except (OSError, ValueError):
        path_text = os.path.normpath(expanded)
    return os.path.normcase(path_text) if os.name == "nt" else path_text


def config_warning_path_within_root(path: Any, root: Any) -> bool:
    path_text = normalized_config_warning_path_key(path)
    root_text = normalized_config_warning_path_key(root)
    if not path_text or not root_text:
        return False
    try:
        return os.path.commonpath([path_text, root_text]) == root_text
    except ValueError:
        return False


def _path_text_for_warning(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    stripped = text.rstrip("\\/")
    if not stripped:
        return text
    anchor = Path(text).expanduser().anchor
    anchor_text = anchor.rstrip("\\/")
    if anchor and anchor_text and stripped.casefold() == anchor_text.casefold():
        return anchor
    return stripped


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
        key: _path_text_for_warning(values.get(key, ""))
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
