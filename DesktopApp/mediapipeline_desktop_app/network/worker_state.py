from __future__ import annotations

import json
import logging
import os
from pathlib import Path
import tempfile
from typing import Any

from .json_policy import loads_strict_json


_log = logging.getLogger(__name__)


def atomic_write_text(path: Path, text: str) -> None:
    """Write text via a same-directory temp file and atomic replace."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(
        prefix=f".{path.name}.",
        suffix=".tmp",
        dir=path.parent,
        text=True,
    )
    tmp_path = Path(tmp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_path, path)
    except Exception:
        try:
            tmp_path.unlink(missing_ok=True)
        except OSError as cleanup_exc:
            _log.warning("Failed to remove temporary worker state file %s: %s", tmp_path, cleanup_exc)
        raise


def load_worker_state(path: Path) -> dict[str, Any]:
    payload = loads_strict_json(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("worker_state.json must contain an object")
    return payload


def save_worker_state(
    path: Path,
    *,
    job_id: str,
    source_path: str,
    pending_done_report: dict[str, Any] | None = None,
) -> None:
    payload: dict[str, Any] = {
        "job_id": job_id,
        "source_path": source_path,
    }
    if pending_done_report is not None:
        payload["pending_done_report"] = dict(pending_done_report)
    atomic_write_text(path, json.dumps(payload, indent=2, allow_nan=False) + "\n")


def clear_worker_state(path: Path) -> None:
    path.unlink(missing_ok=True)
