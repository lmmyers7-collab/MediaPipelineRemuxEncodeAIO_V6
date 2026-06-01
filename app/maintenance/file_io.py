from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any


def read_json_file(path: Path, *, retries: int = 1, delay_seconds: float = 0.05) -> Any | None:
    attempts = retries + 1
    last_exc: Exception | None = None
    for attempt in range(attempts):
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:
            last_exc = exc
            if attempt + 1 >= attempts:
                break
            time.sleep(delay_seconds)
    if last_exc:
        raise last_exc
    return None


__all__ = [
    "read_json_file",
]
