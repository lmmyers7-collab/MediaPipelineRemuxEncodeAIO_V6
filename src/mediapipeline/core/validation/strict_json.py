from __future__ import annotations

import json
from typing import Any


class StrictJsonError(ValueError):
    """Raised when JSON text violates the repository strict boundary."""


def _reject_json_constant(value: str) -> None:
    raise StrictJsonError(f"non-finite JSON value is not allowed: {value}")


def _reject_duplicate_object_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise StrictJsonError(f"duplicate JSON object key: {key}")
        result[key] = value
    return result


def loads_strict_json(raw: str | bytes | bytearray, *, default_text: str | None = None) -> Any:
    """Load JSON while rejecting non-finite values and duplicate object keys."""

    if isinstance(raw, (bytes, bytearray)):
        try:
            text = bytes(raw).decode("utf-8")
        except UnicodeDecodeError as exc:
            raise StrictJsonError(str(exc)) from exc
    else:
        text = str(raw)
    if default_text is not None and not text:
        text = default_text
    try:
        return json.loads(
            text,
            parse_constant=_reject_json_constant,
            object_pairs_hook=_reject_duplicate_object_pairs,
        )
    except StrictJsonError:
        raise
    except json.JSONDecodeError as exc:
        raise StrictJsonError(exc.msg) from exc


__all__ = [
    "StrictJsonError",
    "loads_strict_json",
]
