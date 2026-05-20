from __future__ import annotations

from pathlib import Path
from typing import Any


def _path_key(value: str | Path) -> str:
    return str(Path(str(value))).replace("\\", "/").rstrip("/").lower()


def queue_source_roots(resolved: Any) -> list[Path]:
    roots: list[Path] = []
    for attr in ("source_movies", "source_tv"):
        value = getattr(resolved, attr, None)
        if value:
            roots.append(Path(value))
    return roots


def path_is_under_or_equal(path: str | Path, roots: list[Path]) -> bool:
    candidate = _path_key(path)
    if not candidate:
        return False
    for root in roots:
        root_key = _path_key(root)
        if candidate == root_key or candidate.startswith(root_key + "/"):
            return True
    return False


def validate_queue_source_path(resolved: Any, raw_path: Any) -> tuple[str | None, str | None]:
    path_text = str(raw_path or "").strip()
    if not path_text:
        return None, "'path' is required."
    candidate = Path(path_text)
    if not candidate.is_absolute():
        return None, "'path' must be an absolute source path selected from the backend queue snapshot."
    roots = queue_source_roots(resolved)
    if not roots:
        return None, "SourceMovies and SourceTV are not configured; queue source path updates are unavailable."
    if not path_is_under_or_equal(candidate, roots):
        return None, "Path is outside configured SourceMovies/SourceTV roots."
    return str(candidate), None
