from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Callable

NormalizeComponentFunc = Callable[[str, list[str] | None], str]
CleanMovieNameFunc = Callable[[str, list[str] | None, dict[str, bool] | None, dict[str, list[str]] | None], str]

RENAME_TEMPLATE_PRESETS: tuple[dict[str, str], ...] = (
    {
        "key": "tv_standard",
        "mode": "tv",
        "label": "TV: Show - SxxEyy - Episode Title",
        "description": "Default TV Plex-style filename. Includes a cleaned episode title only when the backend is confident.",
    },
    {
        "key": "tv_no_episode_title",
        "mode": "tv",
        "label": "TV: Show - SxxEyy",
        "description": "TV filename without an episode title. Useful when release names contain noisy or misleading title text.",
    },
    {
        "key": "movie_standard",
        "mode": "movie",
        "label": "Movie: Title (Year)",
        "description": "Default movie Plex-style filename. Keeps the year when it is known or inferred by the movie scrubber.",
    },
)

_DEFAULT_RENAME_TEMPLATE_BY_MODE = {
    "tv": "tv_standard",
    "movie": "movie_standard",
}


def casefold_override_map(values: dict[str, Any] | None) -> dict[str, Any]:
    return {str(key).casefold(): value for key, value in (values or {}).items()}


def casefold_bool_override_map(values: dict[str, bool] | None) -> dict[str, bool]:
    return {str(key).casefold(): bool(value) for key, value in (values or {}).items()}


def rename_row_status(*, errors: list[str], warnings: list[str], matches_target: bool) -> str:
    if errors:
        return "blocked"
    if warnings:
        return "warning"
    if matches_target:
        return "match"
    return "ready"


def rename_template_catalog(mode: str | None = None) -> list[dict[str, str]]:
    media_mode = str(mode or "").strip().casefold()
    return [
        dict(item)
        for item in RENAME_TEMPLATE_PRESETS
        if not media_mode or item["mode"] == media_mode
    ]


def normalize_rename_template_preset(value: object, mode: str) -> str:
    media_mode = str(mode or "tv").strip().casefold()
    default = _DEFAULT_RENAME_TEMPLATE_BY_MODE.get(media_mode, "tv_standard")
    requested = str(value or "").strip().casefold()
    allowed = {item["key"] for item in RENAME_TEMPLATE_PRESETS if item["mode"] == media_mode}
    return requested if requested in allowed else default


def rename_template_includes_tv_episode_title(template_preset: str) -> bool:
    return template_preset != "tv_no_episode_title"


def normalise_manual_final_name(
    source: Path,
    value: str,
    *,
    normalize_component: NormalizeComponentFunc,
) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    if any(sep in text for sep in ("/", "\\")):
        raise ValueError("Final name overrides must be filenames, not paths.")
    candidate = normalize_component(text, [])
    suffix = source.suffix.lower()
    if not candidate:
        raise ValueError("Final name override is empty after invalid characters are filtered.")
    if not candidate.lower().endswith(suffix):
        candidate = f"{candidate}{suffix}"
    return candidate


def build_movie_rename_name(
    source: Path,
    *,
    movie_title: str,
    movie_year: str,
    remove_terms: list[str] | None,
    movie_filter_options: dict[str, bool] | None = None,
    movie_filter_terms: dict[str, list[str]] | None = None,
    normalize_component: NormalizeComponentFunc,
    clean_movie_name: CleanMovieNameFunc,
) -> str:
    cleaned_title = (
        normalize_component(movie_title, remove_terms)
        if movie_title
        else clean_movie_name(source.name, remove_terms, movie_filter_options, movie_filter_terms)
    )
    if not cleaned_title:
        raise ValueError("Movie title is required after invalid characters and remove terms are filtered.")
    year_text = str(movie_year or "").strip()
    if year_text:
        if not re.fullmatch(r"\d{4}", year_text):
            raise ValueError("Movie year must be blank or a four digit year.")
        if not re.search(rf"\({re.escape(year_text)}\)\s*$", cleaned_title):
            cleaned_title = re.sub(r"\s+\((?:19|20)\d{2}\)\s*$", "", cleaned_title).strip()
            cleaned_title = f"{cleaned_title} ({year_text})"
    return f"{cleaned_title}{source.suffix.lower()}"
