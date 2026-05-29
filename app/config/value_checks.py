from __future__ import annotations

from typing import Any


def require_non_empty(values: dict[str, Any], errors: list[str], key: str, label: str) -> None:
    raw = str(values.get(key, "") or "").strip()
    if not raw:
        errors.append(f"{label} is required.")


def validate_int(
    values: dict[str, Any],
    errors: list[str],
    key: str,
    label: str,
    minimum: int | None = None,
    maximum: int | None = None,
) -> None:
    value = values.get(key)
    if not isinstance(value, int):
        errors.append(f"{label} must be an integer.")
        return
    if minimum is not None and value < minimum:
        errors.append(f"{label} must be >= {minimum}.")
    if maximum is not None and value > maximum:
        errors.append(f"{label} must be <= {maximum}.")


def validate_float(
    values: dict[str, Any],
    errors: list[str],
    key: str,
    label: str,
    minimum: float | None = None,
    maximum: float | None = None,
) -> None:
    value = values.get(key)
    if not isinstance(value, (int, float)):
        errors.append(f"{label} must be numeric.")
        return
    number = float(value)
    if minimum is not None and number < minimum:
        errors.append(f"{label} must be >= {minimum}.")
    if maximum is not None and number > maximum:
        errors.append(f"{label} must be <= {maximum}.")


def validate_optional_int(
    values: dict[str, Any],
    errors: list[str],
    key: str,
    label: str,
    minimum: int | None = None,
    maximum: int | None = None,
) -> None:
    value = values.get(key)
    if value in (None, ""):
        return
    validate_int(values, errors, key, label, minimum=minimum, maximum=maximum)


def validate_optional_float(
    values: dict[str, Any],
    errors: list[str],
    key: str,
    label: str,
    minimum: float | None = None,
    maximum: float | None = None,
) -> None:
    value = values.get(key)
    if value in (None, ""):
        return
    validate_float(values, errors, key, label, minimum=minimum, maximum=maximum)


def add_unique_warning(warnings: list[str], message: str) -> None:
    if message not in warnings:
        warnings.append(message)
