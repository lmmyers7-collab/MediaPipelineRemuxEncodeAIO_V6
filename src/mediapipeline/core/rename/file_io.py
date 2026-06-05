from __future__ import annotations

import contextlib
import os
import tempfile
import time
from pathlib import Path


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
