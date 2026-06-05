from __future__ import annotations

import os
import stat
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from mediapipeline.desktop.config_keys import KEY_VALID_EXTENSIONS


@dataclass(frozen=True)
class PathBoundaryCheck:
    ok: bool
    reason_code: str
    reason: str
    path: str
    root: str
    reparse_path: str = ""


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


def _absolute_path_text(path: Path) -> str:
    text = os.path.abspath(str(path))
    return os.path.normcase(text) if os.name == "nt" else text


def _path_is_reparse(path: Path) -> bool:
    try:
        if path.is_symlink():
            return True
        stat_result = os.lstat(path)
        attrs = getattr(stat_result, "st_file_attributes", 0)
        reparse_flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x0400)
        return bool(attrs & reparse_flag)
    except OSError:
        return False


def _existing_path_chain(path: Path, root: Path) -> list[Path]:
    chain = [root]
    try:
        relative = os.path.relpath(str(path), str(root))
    except ValueError:
        return chain
    if relative in ("", "."):
        return chain
    current = root
    for part in Path(relative).parts:
        current = current / part
        if current.exists() or current.is_symlink():
            chain.append(current)
            continue
        break
    return chain


def path_boundary_check(
    path: Path,
    root: Path,
    *,
    allow_missing_leaf: bool = False,
    allow_root_target: bool = False,
) -> PathBoundaryCheck:
    raw_path = str(path)
    raw_root = str(root)
    if not raw_path.strip():
        return PathBoundaryCheck(False, "EMPTY_PATH", "path is empty", raw_path, raw_root)
    if not raw_root.strip():
        return PathBoundaryCheck(False, "EMPTY_ROOT", "root is empty", raw_path, raw_root)

    path_abs = Path(os.path.abspath(str(path)))
    root_abs = Path(os.path.abspath(str(root)))
    path_text = _absolute_path_text(path)
    root_text = _absolute_path_text(root)
    try:
        common = os.path.commonpath([path_text, root_text])
    except ValueError:
        return PathBoundaryCheck(False, "OUTSIDE_ALLOWED_ROOT", "path and root are on different volumes", path_text, root_text)
    if common != root_text:
        return PathBoundaryCheck(False, "OUTSIDE_ALLOWED_ROOT", "path is outside allowed root", path_text, root_text)
    if path_text == root_text and not allow_root_target:
        return PathBoundaryCheck(False, "ROOT_MUTATION_TARGET", "path is the allowed root itself", path_text, root_text)
    if not root_abs.exists():
        return PathBoundaryCheck(False, "ROOT_MISSING", "allowed root does not exist", path_text, root_text)
    if not allow_missing_leaf and not path_abs.exists() and not path_abs.is_symlink():
        return PathBoundaryCheck(False, "PATH_MISSING", "path does not exist", path_text, root_text)

    for candidate in _existing_path_chain(path_abs, root_abs):
        if _path_is_reparse(candidate):
            return PathBoundaryCheck(
                False,
                "REPARSE_POINT_COMPONENT",
                "path contains a symlink, junction, or reparse point component",
                path_text,
                root_text,
                str(candidate),
            )
    return PathBoundaryCheck(True, "OK", "path is within root and has no reparse components", path_text, root_text)


def ensure_path_boundary_safe_for_mutation(
    path: Path,
    root: Path,
    *,
    allow_missing_leaf: bool = False,
    allow_root_target: bool = False,
) -> None:
    result = path_boundary_check(
        path,
        root,
        allow_missing_leaf=allow_missing_leaf,
        allow_root_target=allow_root_target,
    )
    if not result.ok:
        raise RuntimeError(f"Unsafe filesystem mutation target ({result.reason_code}): {path}. {result.reason}")


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
