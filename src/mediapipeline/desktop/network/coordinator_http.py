from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import unquote_plus


MAX_COORDINATOR_BODY_BYTES = 1 * 1024 * 1024


@dataclass(frozen=True)
class BodyLengthDecision:
    ok: bool
    length: int
    status: int = 200
    payload: dict[str, object] | None = None
    close_connection: bool = False


def parse_query_params(path: str) -> dict[str, str]:
    query = path.split("?", 1)[1] if "?" in path else ""
    params: dict[str, str] = {}
    for pair in query.split("&"):
        if not pair:
            continue
        if "=" in pair:
            key, value = pair.split("=", 1)
            params[unquote_plus(key)] = unquote_plus(value)
        else:
            params[unquote_plus(pair)] = ""
    return params


def validate_content_length(raw_value: object, max_bytes: int = MAX_COORDINATOR_BODY_BYTES) -> BodyLengthDecision:
    raw_text = str(raw_value or "0")
    try:
        length = int(raw_text)
    except (TypeError, ValueError):
        return BodyLengthDecision(False, 0, 400, {"error": "Invalid Content-Length header"})
    if length < 0:
        return BodyLengthDecision(False, 0, 400, {"error": "Invalid Content-Length header"})
    if length > max_bytes:
        return BodyLengthDecision(
            False,
            length,
            413,
            {"error": "request body too large", "max_bytes": max_bytes},
            close_connection=True,
        )
    return BodyLengthDecision(True, length)
