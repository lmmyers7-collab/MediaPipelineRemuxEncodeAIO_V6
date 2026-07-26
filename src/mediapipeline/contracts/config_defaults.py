"""Default factories for the configuration contract."""

from __future__ import annotations

from mediapipeline.core.rename.constants import (
    PLEX_RENAME_DEFAULT_REMOVE_TERMS,
    RENAME_MOVIE_FILTER_OPTION_KEYS,
    RENAME_TV_FILTER_OPTION_KEYS,
)


LEGACY_PACKAGED_RENAME_MOVIE_REMOVE_TERMS = (
    *PLEX_RENAME_DEFAULT_REMOVE_TERMS,
    *(f"{value:02d}" for value in range(1, 13)),
)

def _list_default(values: tuple[str, ...]) -> list[str]:
    return list(values)

def _rename_movie_filter_options_default() -> dict[str, bool]:
    return dict.fromkeys(RENAME_MOVIE_FILTER_OPTION_KEYS, True)

def _rename_movie_remove_terms_default() -> list[str]:
    return _list_default(PLEX_RENAME_DEFAULT_REMOVE_TERMS)

def _is_exact_legacy_packaged_rename_movie_remove_terms(values: list[str]) -> bool:
    legacy_keys = {term.casefold() for term in LEGACY_PACKAGED_RENAME_MOVIE_REMOVE_TERMS}
    value_keys = {str(term).casefold() for term in values}
    return value_keys == legacy_keys

def _normalize_legacy_packaged_rename_movie_remove_terms(values: list[str]) -> list[str]:
    if _is_exact_legacy_packaged_rename_movie_remove_terms(values):
        return _rename_movie_remove_terms_default()
    return values

def _rename_tv_filter_options_default() -> dict[str, bool]:
    return dict.fromkeys(RENAME_TV_FILTER_OPTION_KEYS, True)

def _rename_tv_remove_terms_default() -> list[str]:
    return _list_default(PLEX_RENAME_DEFAULT_REMOVE_TERMS)
