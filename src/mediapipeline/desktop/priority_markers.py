from __future__ import annotations


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
