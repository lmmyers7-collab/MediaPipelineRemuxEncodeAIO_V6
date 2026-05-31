from __future__ import annotations

import contextlib
import json
import os
import re
import tempfile
import time
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlsplit


WINDOWS_EXTENDED_PATH_PREFIX = "\\\\?\\"
WINDOWS_EXTENDED_UNC_PREFIX = "\\\\?\\UNC\\"
TAIL_READ_CHUNK_SIZE = 8192


def _strip_windows_extended_path_prefix(path_text: str) -> str:
    if path_text.startswith(WINDOWS_EXTENDED_UNC_PREFIX):
        return "\\\\" + path_text[len(WINDOWS_EXTENDED_UNC_PREFIX):]
    if path_text.startswith(WINDOWS_EXTENDED_PATH_PREFIX):
        return path_text[len(WINDOWS_EXTENDED_PATH_PREFIX):]
    return path_text


def _path_from_file_uri(path_text: str) -> str:
    if os.name == "nt" and path_text.lower().startswith("file://?/"):
        candidate = unquote(path_text[len("file://?/"):]).replace("/", "\\")
        if candidate.upper().startswith("UNC\\"):
            return "\\\\" + candidate[4:]
        return candidate
    if os.name == "nt" and path_text.lower().startswith("file:\\?\\"):
        candidate = unquote(path_text[len("file:\\?\\"):]).replace("/", "\\")
        if candidate.upper().startswith("UNC\\"):
            return "\\\\" + candidate[4:]
        return candidate

    parsed = urlsplit(path_text)
    if parsed.scheme.lower() != "file":
        return path_text

    netloc = unquote(parsed.netloc)
    uri_path = unquote(parsed.path)
    if os.name != "nt":
        return uri_path

    if netloc and netloc.lower() not in ("localhost", "?"):
        return "\\\\" + netloc + uri_path.replace("/", "\\")

    if netloc == "?":
        candidate = uri_path.lstrip("/").replace("/", "\\")
        if candidate.upper().startswith("UNC\\"):
            return "\\\\" + candidate[4:]
        return candidate

    if uri_path.startswith("/?/"):
        uri_path = uri_path[3:]
    elif re.match(r"^/[A-Za-z]:", uri_path):
        uri_path = uri_path[1:]
    return uri_path.replace("/", "\\")


def _normalize_open_path_text(path_text: str) -> str:
    cleaned = path_text.strip().strip('"')
    if cleaned.lower().startswith("file:"):
        cleaned = _path_from_file_uri(cleaned)
    return _strip_windows_extended_path_prefix(cleaned)


def _coerce_open_path(path: Path | str | None) -> Path:
    if not path:
        raise RuntimeError("No path is available for this action.")
    return Path(_normalize_open_path_text(str(path)))


def _windows_native_path(path: Path) -> str:
    return _normalize_open_path_text(str(path))


def _atomic_write_text(path: Path, text: str, *, encoding: str = "utf-8") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding=encoding, newline="") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        delay_seconds = 0.05
        for attempt in range(7):
            try:
                os.replace(tmp_name, path)
                break
            except PermissionError:
                if attempt >= 6:
                    raise
                time.sleep(delay_seconds)
                delay_seconds = min(delay_seconds * 2, 1.0)
    except Exception:
        with contextlib.suppress(OSError):
            os.remove(tmp_name)
        raise


def _read_json_file(path: Path, *, retries: int = 1, delay_seconds: float = 0.05) -> Any | None:
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


def _tail_text_file(path: Path, *, line_count: int, encoding: str = "utf-8") -> str:
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


def _tail_jsonl_file(path: Path, *, line_count: int, encoding: str = "utf-8") -> list[dict[str, Any]]:
    text = _tail_text_file(path, line_count=line_count, encoding=encoding)
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
