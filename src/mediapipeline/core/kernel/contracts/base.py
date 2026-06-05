from __future__ import annotations

from collections.abc import Mapping
from typing import Any


class ContractError(ValueError):
    """Raised when a persisted pipeline contract has the wrong shape."""


def require_mapping(value: Any, name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ContractError(f"{name} must be a JSON object")
    return value


def require_schema_version(payload: Mapping[str, Any], expected: str | set[str], *, key: str = "schema_version") -> str:
    actual = str(payload.get(key) or "").strip()
    allowed = {expected} if isinstance(expected, str) else set(expected)
    if actual not in allowed:
        allowed_text = ", ".join(sorted(allowed))
        raise ContractError(f"{key} must be {allowed_text}; got {actual or '<missing>'}")
    return actual


def text_field(payload: Mapping[str, Any], key: str, default: str = "") -> str:
    value = payload.get(key)
    return default if value is None else str(value)


def bool_field(payload: Mapping[str, Any], key: str, default: bool = False) -> bool:
    value = payload.get(key)
    if isinstance(value, bool):
        return value
    if value is None or value == "":
        return default
    return str(value).strip().casefold() in {"1", "true", "yes", "y", "on"}


def int_field(payload: Mapping[str, Any], key: str, default: int = 0) -> int:
    value = payload.get(key)
    if value is None or value == "":
        return default
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise ContractError(f"{key} must be an integer") from exc


def float_field(payload: Mapping[str, Any], key: str, default: float = 0.0) -> float:
    value = payload.get(key)
    if value is None or value == "":
        return default
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise ContractError(f"{key} must be a number") from exc


def list_field(payload: Mapping[str, Any], key: str) -> list[Any]:
    value = payload.get(key)
    if value is None:
        return []
    if not isinstance(value, list):
        raise ContractError(f"{key} must be an array")
    return value


def dict_field(payload: Mapping[str, Any], key: str) -> dict[str, Any]:
    value = payload.get(key)
    if value is None:
        return {}
    if not isinstance(value, Mapping):
        raise ContractError(f"{key} must be an object")
    return dict(value)
