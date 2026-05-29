from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
from typing import Any


def parse_progress_datetime(raw: str) -> datetime | None:
    text = str(raw or "").strip()
    if not text:
        return None
    iso_text = text.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(iso_text)
    except ValueError:
        pass
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.strptime(text[:19], fmt)
        except ValueError:
            continue
    return None


def datetime_is_stale(raw: str, stale_after_seconds: float) -> bool:
    parsed = parse_progress_datetime(raw)
    if parsed is None:
        return False
    now = datetime.now(parsed.tzinfo) if parsed.tzinfo is not None else datetime.now()
    return (now - parsed) > timedelta(seconds=stale_after_seconds)


def is_progress_stale(progress: dict[str, Any] | None, *, stale_after_seconds: float = 5.0) -> bool:
    if not progress:
        return False
    stage = str(progress.get("CurrentStage", "") or "").strip().lower()
    if stage in {"", "idle", "sleeping", "stopped", "completed"}:
        return False
    raw = str(progress.get("LastUpdate", "") or "").strip()
    return datetime_is_stale(raw, stale_after_seconds)


def is_audit_progress_stale(audit_progress: dict[str, Any] | None, *, stale_after_seconds: float = 5.0) -> bool:
    if not audit_progress:
        return False
    if bool(audit_progress.get("completed", False)) or bool(audit_progress.get("failed", False)):
        return False
    status = str(audit_progress.get("status", "") or "").strip().lower()
    if status in {"", "idle", "completed", "failed", "stopped"}:
        return False
    raw = str(audit_progress.get("last_update", "") or "").strip()
    return datetime_is_stale(raw, stale_after_seconds)


def format_audit_progress(audit_progress: dict[str, Any] | None) -> str:
    if not audit_progress:
        return "Audit progress: No audit progress file found."

    status = str(audit_progress.get("status", "")).strip() or "unknown"
    processed = int(audit_progress.get("processed_files", 0) or 0)
    total = int(audit_progress.get("total_files", 0) or 0)
    percent = int(audit_progress.get("percent_complete", 0) or 0)
    current_file = str(audit_progress.get("current_file", "")).strip()
    current_operation = str(audit_progress.get("current_operation", "")).strip()
    completed = bool(audit_progress.get("completed", False))
    failed = bool(audit_progress.get("failed", False))
    stale = is_audit_progress_stale(audit_progress)
    progress_healthy = bool(audit_progress.get("progress_persistence_healthy", True))
    progress_failures = int(audit_progress.get("progress_write_failures", 0) or 0)

    state = status
    if completed and failed:
        state = "failed"
    elif completed:
        state = "completed"
    elif stale:
        state = f"STALE {state}"

    pieces = [f"Audit progress: {state}"]
    if total > 0:
        pieces.append(f"{processed} / {total}")
        pieces.append(f"{percent}%")
    if current_file:
        pieces.append(Path(current_file).name)
    elif current_operation:
        pieces.append(current_operation)
    if not progress_healthy or progress_failures > 0:
        pieces.append(f"progress writes failing ({progress_failures})")
    return " | ".join(pieces)
