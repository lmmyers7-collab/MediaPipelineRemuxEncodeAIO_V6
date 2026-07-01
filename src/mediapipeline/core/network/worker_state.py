from __future__ import annotations

import json
import logging
import os
from pathlib import Path
import tempfile
import time
from typing import Any

from .json_policy import loads_strict_json


_log = logging.getLogger(__name__)


def _utc_stamp() -> str:
    return time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())


def worker_state_backup_path(path: Path) -> Path:
    return path.with_name(f"{path.name}.bak")


def worker_state_review_dir(path: Path) -> Path:
    return path.parent / "worker_state_review"


def pending_done_reports_dir(path: Path) -> Path:
    return path.parent / "pending_done_reports"


def pending_done_reports_review_dir(path: Path) -> Path:
    return path.parent / "pending_done_reports_review"


def _safe_name(value: str) -> str:
    text = "".join(ch if ch.isalnum() or ch in {"-", "_"} else "_" for ch in str(value or "").strip())
    return text[:80] or "unknown"


def quarantine_worker_state(path: Path, reason: str) -> Path | None:
    if not path.exists():
        return None
    review_dir = worker_state_review_dir(path)
    review_dir.mkdir(parents=True, exist_ok=True)
    target = review_dir / f"{path.name}.{_utc_stamp()}.{_safe_name(reason)}.json"
    os.replace(path, target)
    return target


def _load_worker_state_payload(path: Path) -> dict[str, Any]:
    payload = loads_strict_json(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("worker_state.json must contain an object")
    return payload


def _write_backup(path: Path) -> None:
    if not path.exists():
        return
    backup_path = worker_state_backup_path(path)
    tmp_path = backup_path.with_name(f".{backup_path.name}.{os.getpid()}.{time.monotonic_ns()}.tmp")
    try:
        tmp_path.write_text(path.read_text(encoding="utf-8"), encoding="utf-8", newline="")
        os.replace(tmp_path, backup_path)
    except Exception as exc:
        _log.warning("Failed to refresh worker_state backup %s: %s", backup_path, exc)
        try:
            tmp_path.unlink(missing_ok=True)
        except OSError:
            pass


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
        _write_backup(path)
        delay_seconds = 0.05
        for attempt in range(7):
            try:
                os.replace(tmp_path, path)
                break
            except PermissionError:
                if attempt >= 6:
                    raise
                time.sleep(delay_seconds)
                delay_seconds = min(delay_seconds * 2, 1.0)
    except Exception:
        try:
            tmp_path.unlink(missing_ok=True)
        except OSError as cleanup_exc:
            _log.warning("Failed to remove temporary worker state file %s: %s", tmp_path, cleanup_exc)
        raise


def load_worker_state(path: Path) -> dict[str, Any]:
    try:
        return _load_worker_state_payload(path)
    except Exception:
        backup_path = worker_state_backup_path(path)
        if backup_path.exists():
            try:
                backup_state = _load_worker_state_payload(backup_path)
            except Exception as backup_exc:
                _log.warning("worker_state backup %s is not usable: %s", backup_path, backup_exc)
            else:
                quarantined = quarantine_worker_state(path, "corrupt")
                atomic_write_text(path, json.dumps(backup_state, indent=2, allow_nan=False) + "\n")
                _log.warning(
                    "Recovered worker_state.json from backup %s after quarantining corrupt state at %s.",
                    backup_path,
                    quarantined,
                )
                return backup_state
        quarantined = quarantine_worker_state(path, "corrupt")
        raise ValueError(f"worker_state.json was corrupt and quarantined at {quarantined}")


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


def queue_pending_done_report(
    path: Path,
    *,
    job_id: str,
    source_path: str,
    pending_done_report: dict[str, Any] | None = None,
) -> Path:
    payload = dict(pending_done_report or {})
    payload.setdefault("job_id", job_id)
    payload.setdefault("source_path", source_path)
    payload["queued_utc"] = _utc_stamp()
    payload["schema_version"] = "worker_pending_done_report.v1"
    queue_dir = pending_done_reports_dir(path)
    queue_dir.mkdir(parents=True, exist_ok=True)
    target = queue_dir / f"{_utc_stamp()}.{_safe_name(job_id)}.{time.monotonic_ns()}.json"
    atomic_write_text(target, json.dumps(payload, indent=2, allow_nan=False) + "\n")
    return target


def iter_pending_done_report_files(path: Path) -> list[Path]:
    queue_dir = pending_done_reports_dir(path)
    if not queue_dir.exists():
        return []
    return sorted(item for item in queue_dir.glob("*.json") if item.is_file())


def load_pending_done_report(path: Path) -> dict[str, Any]:
    payload = loads_strict_json(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("pending done report must contain an object")
    return payload


def quarantine_pending_done_report(report_path: Path, reason: str, payload: dict[str, Any] | None = None) -> Path:
    review_dir = pending_done_reports_review_dir(report_path.parent.parent / "worker_state.json")
    review_dir.mkdir(parents=True, exist_ok=True)
    target = review_dir / f"{report_path.stem}.{_safe_name(reason)}.json"
    if payload is not None:
        payload = dict(payload)
        payload["quarantine_reason"] = reason
        atomic_write_text(target, json.dumps(payload, indent=2, allow_nan=False) + "\n")
        report_path.unlink(missing_ok=True)
    else:
        os.replace(report_path, target)
    return target


__all__ = [
    "atomic_write_text",
    "clear_worker_state",
    "iter_pending_done_report_files",
    "load_worker_state",
    "load_pending_done_report",
    "pending_done_reports_dir",
    "pending_done_reports_review_dir",
    "queue_pending_done_report",
    "quarantine_pending_done_report",
    "quarantine_worker_state",
    "save_worker_state",
    "worker_state_backup_path",
    "worker_state_review_dir",
]
