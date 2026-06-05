from __future__ import annotations

import json
from typing import Any


def reject_json_constant(value: str) -> None:
    raise ValueError(f"non-finite JSON value is not allowed: {value}")


def loads_strict_json(data: bytes | str) -> Any:
    text = data.decode("utf-8") if isinstance(data, bytes) else str(data)
    return json.loads(text, parse_constant=reject_json_constant)
