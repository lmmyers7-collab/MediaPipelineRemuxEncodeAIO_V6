"""Strict, bounded JSON reads for persisted state and evidence files.

This boundary is intentionally separate from HTTP JSON handling. Persisted files
may be partially written, retained for operator evidence, or supplied by an older
runtime, so readers must fail without mutating or replacing the source artifact.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from mediapipeline.core.validation.strict_json import StrictJsonError, loads_strict_json


STATE_JSON_DEFAULT_MAX_BYTES = 256 * 1024
STATE_JSON_LARGE_MAX_BYTES = 16 * 1024 * 1024
STATE_JSON_DEFAULT_MAX_DEPTH = 32
STATE_JSONL_MAX_LINE_BYTES = 1024 * 1024
UTF8_BOM = b"\xef\xbb\xbf"


_PUBLIC_MESSAGES = {
    "empty": "State JSON is empty.",
    "too_large": "State JSON exceeds the configured byte limit.",
    "invalid_utf8": "State JSON is not valid UTF-8.",
    "invalid_bom": "State JSON contains an unsupported byte-order mark.",
    "too_deep": "State JSON exceeds the configured nesting limit.",
    "duplicate_key": "State JSON contains a duplicate object key.",
    "non_finite": "State JSON contains a non-finite number.",
    "invalid_json": "State JSON is malformed.",
    "unsupported_version": "State JSON uses an unsupported schema version.",
}


class StateJsonError(StrictJsonError):
    """Sanitized state-file parse failure with a stable machine-readable code."""

    def __init__(self, code: str) -> None:
        self.code = code if code in _PUBLIC_MESSAGES else "invalid_json"
        super().__init__(_PUBLIC_MESSAGES[self.code])


class StateSchemaVersionError(StateJsonError):
    """Raised when a parsed artifact declares an unsupported schema version."""

    def __init__(self) -> None:
        super().__init__("unsupported_version")


def _bounded_positive_int(value: object, default: int) -> int:
    if not isinstance(value, (str, bytes, bytearray, int, float)):
        return default
    try:
        normalized = int(value)
    except (TypeError, ValueError, OverflowError):
        return default
    return max(1, normalized)


def _decode_state_json(raw: str | bytes | bytearray, *, max_bytes: int, allow_bom: bool) -> str:
    byte_limit = _bounded_positive_int(max_bytes, STATE_JSON_DEFAULT_MAX_BYTES)
    if isinstance(raw, str):
        try:
            encoded = raw.encode("utf-8")
        except UnicodeEncodeError as exc:
            raise StateJsonError("invalid_utf8") from exc
    else:
        encoded = bytes(raw)
    if len(encoded) > byte_limit:
        raise StateJsonError("too_large")
    if not encoded:
        raise StateJsonError("empty")
    if encoded.startswith(UTF8_BOM):
        if not allow_bom:
            raise StateJsonError("invalid_bom")
        encoded = encoded[len(UTF8_BOM) :]
        if encoded.startswith(UTF8_BOM):
            raise StateJsonError("invalid_bom")
    try:
        text = encoded.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise StateJsonError("invalid_utf8") from exc
    if not text.strip():
        raise StateJsonError("empty")
    return text


def _enforce_nesting_limit(text: str, *, max_depth: int) -> None:
    depth_limit = _bounded_positive_int(max_depth, STATE_JSON_DEFAULT_MAX_DEPTH)
    depth = 0
    in_string = False
    escaped = False
    for character in text:
        if in_string:
            if escaped:
                escaped = False
            elif character == "\\":
                escaped = True
            elif character == '"':
                in_string = False
            continue
        if character == '"':
            in_string = True
        elif character in "[{":
            depth += 1
            if depth > depth_limit:
                raise StateJsonError("too_deep")
        elif character in "]}":
            depth -= 1
            if depth < 0:
                raise StateJsonError("invalid_json")


def loads_bounded_state_json(
    raw: str | bytes | bytearray,
    *,
    max_bytes: int = STATE_JSON_DEFAULT_MAX_BYTES,
    max_depth: int = STATE_JSON_DEFAULT_MAX_DEPTH,
    allow_bom: bool = True,
) -> Any:
    """Load one persisted JSON value with byte, depth, encoding, and syntax caps."""

    text = _decode_state_json(raw, max_bytes=max_bytes, allow_bom=allow_bom)
    _enforce_nesting_limit(text, max_depth=max_depth)
    try:
        return loads_strict_json(text)
    except StrictJsonError as exc:
        detail = str(exc)
        if detail.startswith("duplicate JSON object key"):
            raise StateJsonError("duplicate_key") from exc
        if detail.startswith("non-finite JSON value"):
            raise StateJsonError("non_finite") from exc
        raise StateJsonError("invalid_json") from exc
    except (RecursionError, ValueError) as exc:
        raise StateJsonError("invalid_json") from exc


def read_bounded_state_json(
    path: Path,
    *,
    max_bytes: int = STATE_JSON_DEFAULT_MAX_BYTES,
    max_depth: int = STATE_JSON_DEFAULT_MAX_DEPTH,
    allow_bom: bool = True,
) -> Any:
    """Read a state file without writes and reject content above ``max_bytes``."""

    byte_limit = _bounded_positive_int(max_bytes, STATE_JSON_DEFAULT_MAX_BYTES)
    with Path(path).open("rb") as handle:
        raw = handle.read(byte_limit + 1)
    return loads_bounded_state_json(
        raw,
        max_bytes=byte_limit,
        max_depth=max_depth,
        allow_bom=allow_bom,
    )


def require_supported_schema_version(
    payload: Any,
    supported: str | set[str] | frozenset[str] | tuple[str, ...],
    *,
    field: str = "schema_version",
) -> str:
    """Return an exact supported version or raise a sanitized version error."""

    if not isinstance(payload, dict):
        raise StateSchemaVersionError()
    actual = payload.get(field)
    versions = {supported} if isinstance(supported, str) else set(supported)
    if not isinstance(actual, str) or actual not in versions:
        raise StateSchemaVersionError()
    return actual


__all__ = [
    "STATE_JSON_DEFAULT_MAX_BYTES",
    "STATE_JSON_DEFAULT_MAX_DEPTH",
    "STATE_JSON_LARGE_MAX_BYTES",
    "STATE_JSONL_MAX_LINE_BYTES",
    "StateJsonError",
    "StateSchemaVersionError",
    "loads_bounded_state_json",
    "read_bounded_state_json",
    "require_supported_schema_version",
]
