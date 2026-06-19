"""Default factories for the configuration contract."""

from __future__ import annotations

from mediapipeline.core.rename.constants import (
    PLEX_RENAME_DEFAULT_REMOVE_TERMS,
    RENAME_MOVIE_FILTER_OPTION_KEYS,
    RENAME_TV_FILTER_OPTION_KEYS,
)

def _list_default(values: tuple[str, ...]) -> list[str]:
    return list(values)

def _rename_movie_filter_options_default() -> dict[str, bool]:
    return {key: True for key in RENAME_MOVIE_FILTER_OPTION_KEYS}

def _rename_movie_remove_terms_default() -> list[str]:
    return _list_default(PLEX_RENAME_DEFAULT_REMOVE_TERMS)

def _rename_tv_filter_options_default() -> dict[str, bool]:
    return {key: True for key in RENAME_TV_FILTER_OPTION_KEYS}

def _rename_tv_remove_terms_default() -> list[str]:
    return _list_default(PLEX_RENAME_DEFAULT_REMOVE_TERMS)
