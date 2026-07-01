from __future__ import annotations

from pathlib import Path
from typing import Any

from mediapipeline.core.rename.input_classification import classify_rename_input_paths


def _classify_folder_file_paths(paths: list[str], *, mode: str) -> tuple[list[str], dict[str, int]]:
    if mode != "folder_files":
        return paths, {"raw_path_count": len(paths), "ignored_path_count": 0, "ignored_sidecar_count": 0}
    classification = classify_rename_input_paths(paths)
    return [str(path) for path in classification.media_paths], {
        "raw_path_count": classification.raw_count,
        "ignored_path_count": classification.ignored_count,
        "ignored_sidecar_count": len(classification.ignored_sidecar_paths),
        "ignored_non_media_count": len(classification.ignored_non_media_paths),
        "ignored_duplicate_media_count": len(classification.ignored_duplicate_media_paths),
    }


def _direct_child_file_paths(folder: Path) -> list[str]:
    try:
        return [
            str(child)
            for child in sorted(folder.iterdir(), key=lambda item: item.name.casefold())
            if child.is_file()
        ]
    except OSError:
        return []


def select_rename_paths_from_known_paths(
    paths: list[str],
    *,
    selection_mode: str = "folder_files",
) -> dict[str, Any]:
    """Resolve already-known dropped paths without opening a native dialog."""
    raw_mode = str(selection_mode or "").strip().lower()
    mode = raw_mode if raw_mode in ("folder", "folder_files", "files") else "folder_files"
    normalized = [str(path).strip() for path in paths if str(path).strip()]
    if mode == "folder":
        return {
            "ok": True,
            "canceled": False,
            "selection_mode": mode,
            "paths": normalized,
            "raw_path_count": len(normalized),
            "ignored_path_count": 0,
            "ignored_sidecar_count": 0,
            "message": f"Resolved {len(normalized)} dropped folder path{'' if len(normalized) == 1 else 's'}.",
            "errors": [],
        }

    expanded: list[str] = []
    for raw_path in normalized:
        path = Path(raw_path)
        if path.is_dir():
            expanded.extend(_direct_child_file_paths(path))
        else:
            expanded.append(str(path))

    selected_paths, counts = _classify_folder_file_paths(
        expanded,
        mode="folder_files" if mode == "folder_files" else mode,
    )
    result: dict[str, Any] = {
        "ok": True,
        "canceled": False,
        "selection_mode": mode,
        "paths": selected_paths,
        "message": (
            f"Resolved dropped path(s) to {len(selected_paths)} media file"
            f"{'' if len(selected_paths) == 1 else 's'}."
        ),
        "errors": [],
    }
    result.update(counts)
    return result


__all__ = ["select_rename_paths_from_known_paths"]
