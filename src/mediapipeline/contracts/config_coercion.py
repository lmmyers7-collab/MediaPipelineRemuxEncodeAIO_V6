"""Coercion helpers for the configuration contract."""

from __future__ import annotations

from typing import Any

from mediapipeline.core.validation.strict_json import loads_strict_json

def _mapping_from_json_or_mapping(value: Any, *, label: str) -> dict[str, Any]:
    if value in (None, "", False):
        return {}
    if isinstance(value, str):
        raw = value.strip()
        if not raw:
            return {}
        try:
            value = loads_strict_json(raw)
        except ValueError as exc:
            raise ValueError(f"{label} must be a JSON object when provided as text: {exc}") from exc
    if not isinstance(value, dict):
        raise TypeError(f"{label} must be a mapping.")
    return {str(key): item_value for key, item_value in value.items()}

def _coerce_config_bool(value: Any, *, default: bool = True) -> bool:
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

def _normalize_config_term_list(values: Any) -> list[str]:
    if values in (None, "", False):
        return []
    if isinstance(values, str):
        raw_values = values.replace(";", ",").replace("\n", ",").split(",")
    elif isinstance(values, (list, tuple, set)):
        raw_values = list(values)
    else:
        raw_values = [values]
    terms: list[str] = []
    seen: set[str] = set()
    for value in raw_values:
        term = str(value or "").strip()
        key = term.casefold()
        if not term or key in seen:
            continue
        seen.add(key)
        terms.append(term)
    return terms
