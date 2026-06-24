from __future__ import annotations

import re
from collections.abc import Callable
from pathlib import Path

from mediapipeline.core.files.constants import MEDIA_FILE_SUFFIXES


def natural_sort_key(path: Path) -> tuple[object, ...]:
    parts: list[object] = []
    for chunk in re.split(r"(\d+)", str(path)):
        if chunk.isdigit():
            parts.append((0, int(chunk), len(chunk)))
        else:
            parts.append((1, chunk.casefold()))
    return tuple(parts)


def normalize_plex_filename_component(value: str, remove_terms: list[str] | None = None) -> str:
    text = str(value or "")
    for term in remove_terms or []:
        cleaned_term = str(term or "").strip()
        if not cleaned_term:
            continue
        text = re.sub(rf"\b{re.escape(cleaned_term)}\b", " ", text, flags=re.IGNORECASE)
    text = re.sub(r'[<>:"/\\|?*\x00-\x1f]', " ", text)
    text = re.sub(r"\s+", " ", text).strip(" .")
    return text


def parse_rename_remove_terms(raw: str) -> list[str]:
    terms = [item.strip() for item in re.split(r"[,;\n]+", str(raw or "")) if item.strip()]
    seen: set[str] = set()
    result: list[str] = []
    for term in terms:
        key = term.casefold()
        if key in seen:
            continue
        seen.add(key)
        result.append(term)
    return result


def parse_rename_number(raw: str | int, *, label: str, prefix_pattern: str, minimum: int, maximum: int) -> int:
    text = str(raw or "").strip()
    pattern = rf"(?i)^(?:{prefix_pattern})?\s*(\d{{1,4}})$"
    match = re.fullmatch(pattern, text)
    if not match:
        raise ValueError(f"{label} must be a number or a normal token such as S01/E22.")
    value = int(match.group(1))
    if value < minimum or value > maximum:
        raise ValueError(f"{label} must be between {minimum} and {maximum}.")
    return value


def pipeline_sidecar_path(media_path: Path) -> Path:
    return media_path.with_suffix(".pipeline.json")


def mediapipeline_sidecar_path(media_path: Path) -> Path:
    return media_path.with_suffix(".mediapipeline.json")


def rename_override_sidecar_path(media_path: Path) -> Path:
    return media_path.with_suffix(".mediapipeline.rename.json")


def associated_sidecar_candidates(media_path: Path) -> list[tuple[Path, Callable[[Path], Path]]]:
    destination_patterns: tuple[tuple[Path, Callable[[Path], Path]], ...] = (
        (mediapipeline_sidecar_path(media_path), lambda dest: mediapipeline_sidecar_path(dest)),
        (pipeline_sidecar_path(media_path), lambda dest: pipeline_sidecar_path(dest)),
        (Path(str(media_path) + ".pipeline.json"), lambda dest: Path(str(dest) + ".pipeline.json")),
        (rename_override_sidecar_path(media_path), lambda dest: rename_override_sidecar_path(dest)),
    )
    seen: set[str] = set()
    candidates: list[tuple[Path, Callable[[Path], Path]]] = []
    for source, mapper in destination_patterns:
        key = str(source).casefold()
        if key in seen:
            continue
        seen.add(key)
        candidates.append((source, mapper))
    return candidates


def casefold_path(path: Path) -> str:
    return str(path).casefold()


def resolve_same_file(left: Path, right: Path) -> bool:
    try:
        return left.resolve() == right.resolve()
    except OSError:
        return casefold_path(left) == casefold_path(right)


def strip_known_media_suffix(value: str) -> str:
    text = str(value or "")
    lower = text.casefold()
    for suffix in sorted(MEDIA_FILE_SUFFIXES, key=len, reverse=True):
        if lower.endswith(suffix.casefold()):
            return text[: -len(suffix)]
    return text


def remove_default_priority_markers(text: str) -> str:
    result = str(text or "")
    for _ in range(6):
        trimmed = result.lstrip()
        matched = False
        for marker in ("[NOW]", "!"):
            if trimmed.casefold().startswith(marker.casefold()):
                result = trimmed[len(marker):].lstrip(" -_.")
                matched = True
                break
        if not matched:
            break
    return result.strip()
