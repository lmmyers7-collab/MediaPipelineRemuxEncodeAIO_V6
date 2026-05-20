from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from .config_keys import KEY_VALID_EXTENSIONS


def first_existing(*paths: Path) -> Path:
    for path in paths:
        if path.exists():
            return path
    return paths[0]


def state_root_for_local_base(local_base: Path) -> Path:
    return local_base / "State"


def path_or_none(value: Any) -> Path | None:
    if value is None or str(value).strip() == "":
        return None
    return Path(str(value))


def valid_extensions_from_config(config_data: dict[str, Any]) -> list[str]:
    raw = config_data.get(KEY_VALID_EXTENSIONS)
    if isinstance(raw, list) and raw:
        cleaned = [str(item).lower() for item in raw if str(item).strip()]
        if cleaned:
            return cleaned
    return [".mkv", ".mp4", ".avi", ".mov", ".m4v", ".ts", ".m2ts"]


def normalized_path_key(path: Path) -> str:
    try:
        path_text = os.path.abspath(str(path.resolve(strict=False)))
    except OSError:
        path_text = os.path.abspath(str(path))
    if os.name == "nt":
        path_text = os.path.normcase(path_text)
    return path_text


def path_within_root(path: Path, root: Path) -> bool:
    try:
        path_text = os.path.abspath(str(path.resolve(strict=False)))
        root_text = os.path.abspath(str(root.resolve(strict=False)))
    except OSError:
        path_text = os.path.abspath(str(path))
        root_text = os.path.abspath(str(root))
    if os.name == "nt":
        path_text = os.path.normcase(path_text)
        root_text = os.path.normcase(root_text)
    try:
        return os.path.commonpath([path_text, root_text]) == root_text
    except ValueError:
        return False
