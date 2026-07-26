from __future__ import annotations

from pathlib import Path


def path_is_unc(path: Path) -> bool:
    text = str(path)
    return text.startswith("\\\\") or text.startswith("//")


def sorted_priority_markers(markers: list[str]) -> list[str]:
    return sorted((marker for marker in markers if marker), key=len, reverse=True)


def starts_with_priority_marker(text: str, markers: list[str]) -> bool:
    trimmed = (text or "").lstrip()
    if not trimmed:
        return False
    lowered = trimmed.lower()
    return any(lowered.startswith(marker.lower()) for marker in sorted_priority_markers(markers))


def remove_priority_markers_from_name(text: str, markers: list[str], *, max_passes: int = 6) -> str:
    result = text or ""
    for _ in range(max_passes):
        trimmed = result.lstrip()
        matched = False
        for marker in sorted_priority_markers(markers):
            if trimmed.lower().startswith(marker.lower()):
                result = trimmed[len(marker) :].lstrip(" -_.")
                matched = True
                break
        if not matched:
            break
    return result.strip()


def safe_mtime(path: Path, cache: dict[Path, float] | None = None) -> float:
    if cache is not None and path in cache:
        return cache[path]
    try:
        value = path.stat().st_mtime
    except OSError:
        value = 0.0
    if cache is not None:
        cache[path] = value
    return value


def get_source_priority_info(
    source_path: Path,
    markers: list[str],
    stat_cache: dict[Path, float] | None = None,
) -> tuple[bool, list[str], float]:
    reasons: list[str] = []
    priority_rank = 0.0
    if starts_with_priority_marker(source_path.name, markers):
        reasons.append("file")
        priority_rank = max(priority_rank, safe_mtime(source_path, stat_cache))

    current = source_path.parent
    source_mtime = stat_cache.get(source_path, 0.0) if stat_cache is not None else 0.0
    for _ in range(4):
        leaf = current.name
        if leaf and starts_with_priority_marker(leaf, markers):
            reasons.append(f"folder:{leaf}")
            if stat_cache is not None and path_is_unc(current) and current not in stat_cache:
                priority_rank = max(priority_rank, source_mtime)
            else:
                priority_rank = max(priority_rank, safe_mtime(current, stat_cache))
        if current.parent == current:
            break
        current = current.parent

    return (len(reasons) > 0, reasons, priority_rank)
