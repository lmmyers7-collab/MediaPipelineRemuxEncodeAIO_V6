from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

from mediapipeline.core.files.constants import MEDIA_FILE_SUFFIXES


SIDECAR_SUFFIXES = (
    ".mediapipeline.rename.json",
    ".mediapipeline.json",
    ".pipeline.json",
)


@dataclass(frozen=True)
class RenameInputClassification:
    media_paths: list[Path] = field(default_factory=list)
    ignored_sidecar_paths: list[Path] = field(default_factory=list)
    ignored_non_media_paths: list[Path] = field(default_factory=list)
    ignored_duplicate_media_paths: list[Path] = field(default_factory=list)
    raw_count: int = 0

    @property
    def ignored_count(self) -> int:
        return (
            len(self.ignored_sidecar_paths)
            + len(self.ignored_non_media_paths)
            + len(self.ignored_duplicate_media_paths)
        )

    def counts(self) -> dict[str, int]:
        return {
            "raw": self.raw_count,
            "media": len(self.media_paths),
            "ignored": self.ignored_count,
            "ignored_sidecar": len(self.ignored_sidecar_paths),
            "ignored_non_media": len(self.ignored_non_media_paths),
            "ignored_duplicate": len(self.ignored_duplicate_media_paths),
        }

    def warnings(self) -> list[str]:
        warnings: list[str] = []
        sidecar_count = len(self.ignored_sidecar_paths)
        non_media_count = len(self.ignored_non_media_paths)
        duplicate_count = len(self.ignored_duplicate_media_paths)
        if sidecar_count:
            warnings.append(
                f"Ignored {sidecar_count} staged rename sidecar path(s); sidecars are attached to media rows automatically."
            )
        if non_media_count:
            warnings.append(
                f"Ignored {non_media_count} staged non-media path(s); rename preview/apply only plans known media extensions."
            )
        if duplicate_count:
            warnings.append(f"Ignored {duplicate_count} duplicate staged media path(s).")
        return warnings


def is_rename_sidecar_path(path: Path | str) -> bool:
    name = Path(str(path)).name.casefold()
    return any(name.endswith(suffix) for suffix in SIDECAR_SUFFIXES)


def classify_rename_input_paths(paths: Iterable[Path | str]) -> RenameInputClassification:
    media_paths: list[Path] = []
    ignored_sidecar_paths: list[Path] = []
    ignored_non_media_paths: list[Path] = []
    ignored_duplicate_media_paths: list[Path] = []
    seen_media: set[str] = set()
    raw_count = 0

    for raw_path in paths:
        text = str(raw_path or "").strip()
        if not text:
            continue
        raw_count += 1
        path = Path(text)
        if path.suffix.lower() in MEDIA_FILE_SUFFIXES:
            key = str(path).casefold()
            if key in seen_media:
                ignored_duplicate_media_paths.append(path)
                continue
            seen_media.add(key)
            media_paths.append(path)
        elif is_rename_sidecar_path(path):
            ignored_sidecar_paths.append(path)
        else:
            ignored_non_media_paths.append(path)

    return RenameInputClassification(
        media_paths=media_paths,
        ignored_sidecar_paths=ignored_sidecar_paths,
        ignored_non_media_paths=ignored_non_media_paths,
        ignored_duplicate_media_paths=ignored_duplicate_media_paths,
        raw_count=raw_count,
    )


__all__ = [
    "RenameInputClassification",
    "SIDECAR_SUFFIXES",
    "classify_rename_input_paths",
    "is_rename_sidecar_path",
]
