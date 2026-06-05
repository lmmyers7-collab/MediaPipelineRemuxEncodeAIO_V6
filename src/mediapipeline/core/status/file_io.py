from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any


TAIL_READ_CHUNK_SIZE = 8192


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


def tail_text_file(path: Path, *, line_count: int, encoding: str = "utf-8") -> str:
    if line_count <= 0:
        return ""

    with path.open("rb") as handle:
        handle.seek(0, os.SEEK_END)
        file_size = handle.tell()
        buffer = b""
        newline_count = 0
        while file_size > 0 and newline_count <= line_count:
            read_size = min(TAIL_READ_CHUNK_SIZE, file_size)
            file_size -= read_size
            handle.seek(file_size)
            chunk = handle.read(read_size)
            buffer = chunk + buffer
            newline_count += chunk.count(b"\n")

    text = buffer.decode(encoding, errors="replace")
    lines = text.splitlines()[-line_count:]
    return "\n".join(lines)


def tail_jsonl_file(path: Path, *, line_count: int, encoding: str = "utf-8") -> list[dict[str, Any]]:
    text = tail_text_file(path, line_count=line_count, encoding=encoding)
    events: list[dict[str, Any]] = []
    for raw_line in text.splitlines():
        line = raw_line.strip().lstrip("\ufeff")
        if not line:
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            events.append(payload)
    return events
