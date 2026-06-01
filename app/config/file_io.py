from __future__ import annotations

import contextlib
import os
import re
import tempfile
import time
from pathlib import Path
from urllib.parse import unquote, urlsplit


WINDOWS_EXTENDED_PATH_PREFIX = "\\\\?\\"
WINDOWS_EXTENDED_UNC_PREFIX = "\\\\?\\UNC\\"


def strip_windows_extended_path_prefix(path_text: str) -> str:
    if path_text.startswith(WINDOWS_EXTENDED_UNC_PREFIX):
        return "\\\\" + path_text[len(WINDOWS_EXTENDED_UNC_PREFIX):]
    if path_text.startswith(WINDOWS_EXTENDED_PATH_PREFIX):
        return path_text[len(WINDOWS_EXTENDED_PATH_PREFIX):]
    return path_text


def path_from_file_uri(path_text: str) -> str:
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


def normalize_open_path_text(path_text: str) -> str:
    cleaned = path_text.strip().strip('"')
    if cleaned.lower().startswith("file:"):
        cleaned = path_from_file_uri(cleaned)
    return strip_windows_extended_path_prefix(cleaned)


def atomic_write_text(path: Path, text: str, *, encoding: str = "utf-8") -> None:
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


__all__ = [
    "atomic_write_text",
    "normalize_open_path_text",
    "path_from_file_uri",
    "strip_windows_extended_path_prefix",
]
