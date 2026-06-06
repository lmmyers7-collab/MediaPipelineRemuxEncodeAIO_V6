"""Rename cleaning policy parsing and request enrichment."""

from __future__ import annotations

from typing import Any, Callable, Mapping

from mediapipeline.core.rename.constants import PLEX_RENAME_DEFAULT_REMOVE_TERMS
from mediapipeline.core.rename.movie import normalize_movie_filter_options, normalize_movie_filter_terms, rename_movie_filter_default_terms
from mediapipeline.core.kernel.config_keys import (
    KEY_RENAME_MOVIE_FILTER_OPTIONS,
    KEY_RENAME_MOVIE_FILTER_TERMS,
    KEY_RENAME_MOVIE_REMOVE_TERMS,
)

RENAME_MOVIE_FILTER_PUBLIC_REQUEST_KEYS = {
    "remove_terms",
    "remove_terms_text",
    "movie_filter_options",
    "movie_filter_terms",
    "movie_filter_terms_enabled",
}
RENAME_MOVIE_FILTER_POLICY_SOURCE_KEY = "_rename_movie_filter_policy_source"


def dict_bool(value: object) -> dict[str, bool]:
    if not isinstance(value, dict):
        return {}
    return {str(key): _coerce_policy_bool(item, default=False) for key, item in value.items()}


def dict_str(value: object) -> dict[str, str]:
    if not isinstance(value, dict):
        return {}
    return {str(key): str(item) for key, item in value.items()}


def dict_terms(value: object, parser: Callable[[str], list[str]] | None = None) -> dict[str, list[str]]:
    if not isinstance(value, dict):
        return {}
    result: dict[str, list[str]] = {}
    for key, item in value.items():
        if isinstance(item, list):
            terms = [str(term).strip() for term in item if str(term or "").strip()]
        else:
            raw_terms = str(item or "")
            if callable(parser):
                terms = [str(term).strip() for term in parser(raw_terms) if str(term or "").strip()]
            else:
                terms = [term.strip() for term in raw_terms.replace(";", ",").replace("\n", ",").split(",") if term.strip()]
        seen: set[str] = set()
        deduped: list[str] = []
        for term in terms:
            term_key = term.casefold()
            if term_key in seen:
                continue
            seen.add(term_key)
            deduped.append(term)
        result[str(key)] = deduped
    return result


def _coerce_policy_bool(value: object, *, default: bool = True) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    if isinstance(value, (int, float)):
        return bool(value)
    text = str(value).strip().casefold()
    if text in {"true", "1", "yes", "y", "on"}:
        return True
    if text in {"false", "0", "no", "n", "off"}:
        return False
    return default


def _config_mapping_value(config: Mapping[str, Any] | object | None, key: str) -> Any:
    if isinstance(config, Mapping):
        return config.get(key)
    if config is not None and hasattr(config, key):
        return getattr(config, key)
    return None


def _rename_remove_terms_default() -> list[str]:
    return [str(term) for term in PLEX_RENAME_DEFAULT_REMOVE_TERMS]


def rename_cleaning_policy_from_config(config: Mapping[str, Any] | object | None = None) -> dict[str, Any]:
    raw_options = _config_mapping_value(config, KEY_RENAME_MOVIE_FILTER_OPTIONS)
    raw_terms = _config_mapping_value(config, KEY_RENAME_MOVIE_FILTER_TERMS)
    raw_remove_terms = _config_mapping_value(config, KEY_RENAME_MOVIE_REMOVE_TERMS)

    terms = rename_movie_filter_default_terms()
    terms.update(normalize_movie_filter_terms(dict_terms(raw_terms)))
    remove_terms = _rename_remove_terms_default()
    if raw_remove_terms not in (None, "", False):
        normalized_remove_terms: list[str] = []
        seen_remove_terms: set[str] = set()
        for item in remove_terms_from_request({"remove_terms": raw_remove_terms}):
            term = str(item or "").strip()
            key = term.casefold()
            if not term or key in seen_remove_terms:
                continue
            seen_remove_terms.add(key)
            normalized_remove_terms.append(term)
        remove_terms = normalized_remove_terms
    return {
        "movie_filter_options": normalize_movie_filter_options(dict_bool(raw_options)),
        "movie_filter_terms": terms,
        "remove_terms": remove_terms,
    }


def rename_cleaning_policy_from_resolved(resolved: object | None) -> dict[str, Any]:
    config_data = getattr(resolved, "config_data", None)
    return rename_cleaning_policy_from_config(config_data if isinstance(config_data, Mapping) else None)


def rename_request_with_cleaning_policy(
    request: Mapping[str, Any],
    policy: Mapping[str, Any],
    *,
    source: str,
    strip_existing: bool = False,
) -> dict[str, Any]:
    enriched = dict(request)
    if strip_existing:
        for key in RENAME_MOVIE_FILTER_PUBLIC_REQUEST_KEYS:
            enriched.pop(key, None)
    enriched["remove_terms"] = list(policy.get("remove_terms") or [])
    enriched["movie_filter_options"] = dict(policy.get("movie_filter_options") or {})
    enriched["movie_filter_terms"] = {
        str(key): [str(item) for item in values or [] if str(item or "").strip()]
        for key, values in dict(policy.get("movie_filter_terms") or {}).items()
    }
    enriched[RENAME_MOVIE_FILTER_POLICY_SOURCE_KEY] = source
    return enriched


def rename_request_uses_staged_cleaning_policy(request: Mapping[str, Any]) -> bool:
    return str(request.get(RENAME_MOVIE_FILTER_POLICY_SOURCE_KEY) or "").casefold() == "staged"


def remove_terms_from_request(
    request: Mapping[str, Any],
    parser: Callable[[str], list[str]] | None = None,
) -> list[str]:
    remove_terms = request.get("remove_terms")
    if isinstance(remove_terms, list):
        return [str(item) for item in remove_terms]
    raw_terms = str(request.get("remove_terms_text") or "")
    if callable(parser) and raw_terms:
        return [str(item) for item in parser(raw_terms)]
    return []


__all__ = [
    "RENAME_MOVIE_FILTER_PUBLIC_REQUEST_KEYS",
    "RENAME_MOVIE_FILTER_POLICY_SOURCE_KEY",
    "dict_bool",
    "dict_str",
    "dict_terms",
    "rename_cleaning_policy_from_config",
    "rename_cleaning_policy_from_resolved",
    "rename_request_with_cleaning_policy",
    "rename_request_uses_staged_cleaning_policy",
    "remove_terms_from_request",
]
