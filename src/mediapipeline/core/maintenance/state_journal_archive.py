"""Confirmed archive action for oversized runtime event journals."""

from __future__ import annotations

from datetime import datetime, UTC
from pathlib import Path
import shutil
from typing import Any
from collections.abc import Mapping

from mediapipeline.core.diagnostics.autonomy_health import STATE_FILE_REVIEW_BYTES


STATE_JOURNAL_ARCHIVE_COMMAND = "maintenance.archive_state_journals"
STATE_JOURNAL_ARCHIVE_SCHEMA_VERSION = "desktop_state_journal_archive.v1"
PIPELINE_EVENT_JOURNAL_NAME = "pipeline_events.jsonl"
ARCHIVE_FOLDER_NAME = "ArchivedEvents"
ARCHIVE_MIN_BYTES = STATE_FILE_REVIEW_BYTES


def archive_state_journals_payload(
    resolved: Any,
    request: Mapping[str, Any] | None = None,
    *,
    close_readiness: Mapping[str, Any] | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Archive the configured pipeline event journal when it is oversized."""
    request = request or {}
    checked_at = (now or datetime.now(UTC)).astimezone(UTC)
    journal_path = _path(getattr(resolved, "event_file", None))
    state_root = _path(getattr(resolved, "state_root", None))
    moved: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    errors: list[str] = []
    row = _event_journal_candidate(journal_path, state_root)
    if row.get("eligible"):
        try:
            result = _archive_event_journal(journal_path, checked_at)
            moved.append(result)
        except Exception as exc:
            errors.append(str(exc))
            skipped.append({**row, "skipped_reason": f"archive failed: {exc}"})
    else:
        skipped.append(row)
    return {
        "schema_version": STATE_JOURNAL_ARCHIVE_SCHEMA_VERSION,
        "command": STATE_JOURNAL_ARCHIVE_COMMAND,
        "effect": "runtime-evidence-archive",
        "confirmed": request.get("confirm_archive") is True,
        "reason": str(request.get("reason") or "").strip(),
        "checked_at_utc": checked_at.isoformat(timespec="seconds").replace("+00:00", "Z"),
        "close_readiness": dict(close_readiness or {}),
        "safe_to_apply": not errors,
        "moved_count": len(moved),
        "skipped_count": len(skipped),
        "moved_journals": moved,
        "skipped_journals": skipped,
        "errors": errors,
        "warnings": [] if moved else ["No oversized event journal was eligible for archive."],
        "archive_min_bytes": ARCHIVE_MIN_BYTES,
        "allowed_file_name": PIPELINE_EVENT_JOURNAL_NAME,
        "would_not_touch": _would_not_touch(),
        "media_mutation_performed": False,
        "pending_publish_mutation_performed": False,
        "queue_mutation_performed": False,
        "source_media_mutation_performed": False,
        "command_journal": "recorded by the Local API command journal unless route handling fails before response",
        "summary_lines": _summary_lines(moved, skipped, errors),
    }


def unconfirmed_state_journal_archive_payload(
    resolved: Any,
    request: Mapping[str, Any] | None = None,
    *,
    close_readiness: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    journal_path = _path(getattr(resolved, "event_file", None))
    state_root = _path(getattr(resolved, "state_root", None))
    return {
        "schema_version": STATE_JOURNAL_ARCHIVE_SCHEMA_VERSION,
        "command": STATE_JOURNAL_ARCHIVE_COMMAND,
        "effect": "none",
        "confirmed": False,
        "reason": str((request or {}).get("reason") or "").strip(),
        "close_readiness": dict(close_readiness or {}),
        "safe_to_apply": False,
        "confirmation_required": True,
        "moved_count": 0,
        "skipped_count": 1,
        "moved_journals": [],
        "skipped_journals": [_event_journal_candidate(journal_path, state_root)],
        "errors": [],
        "warnings": ["confirm_archive must be true before archiving runtime event evidence."],
        "archive_min_bytes": ARCHIVE_MIN_BYTES,
        "allowed_file_name": PIPELINE_EVENT_JOURNAL_NAME,
        "would_not_touch": _would_not_touch(),
        "media_mutation_performed": False,
        "pending_publish_mutation_performed": False,
        "queue_mutation_performed": False,
        "source_media_mutation_performed": False,
    }


def close_readiness_blocked_archive_payload(
    resolved: Any,
    request: Mapping[str, Any] | None = None,
    *,
    close_readiness: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    payload = unconfirmed_state_journal_archive_payload(
        resolved,
        request,
        close_readiness=close_readiness,
    )
    confirmed = request.get("confirm_archive") is True if isinstance(request, Mapping) else False
    payload["confirmed"] = confirmed
    payload["confirmation_required"] = False
    payload["effect"] = "none"
    payload["warnings"] = ["Archive refused because close-readiness is not safe."]
    return payload


def _event_journal_candidate(path: Path | None, state_root: Path | None) -> dict[str, Any]:
    row: dict[str, Any] = {
        "path": str(path or ""),
        "kind": "pipeline_event_journal",
        "eligible": False,
        "size_bytes": 0,
        "skipped_reason": "",
    }
    if path is None:
        row["skipped_reason"] = "event journal path is not configured"
        return row
    if path.name.casefold() != PIPELINE_EVENT_JOURNAL_NAME:
        row["skipped_reason"] = f"event journal file name must be {PIPELINE_EVENT_JOURNAL_NAME}"
        return row
    if state_root is None:
        row["skipped_reason"] = "state_root is not configured"
        return row
    if not _is_under(path, state_root):
        row["skipped_reason"] = "event journal is outside the resolved state root"
        return row
    if not path.exists():
        row["skipped_reason"] = "event journal does not exist"
        return row
    if not path.is_file():
        row["skipped_reason"] = "event journal path is not a file"
        return row
    try:
        size = int(path.stat().st_size)
    except OSError as exc:
        row["skipped_reason"] = f"could not stat event journal: {exc}"
        return row
    row["size_bytes"] = size
    if size <= ARCHIVE_MIN_BYTES:
        row["skipped_reason"] = "event journal is below archive threshold"
        return row
    row["eligible"] = True
    return row


def _archive_event_journal(path: Path | None, checked_at: datetime) -> dict[str, Any]:
    if path is None:
        raise OSError("event journal path is not configured")
    original_size = int(path.stat().st_size)
    archive_dir = path.parent / ARCHIVE_FOLDER_NAME
    archive_dir.mkdir(parents=True, exist_ok=True)
    archive_path = _unique_archive_path(archive_dir, checked_at)
    shutil.move(str(path), str(archive_path))
    path.write_text("", encoding="utf-8")
    return {
        "path": str(path),
        "archive_path": str(archive_path),
        "size_bytes": original_size,
        "replacement_created": path.exists() and path.is_file(),
    }


def _unique_archive_path(archive_dir: Path, checked_at: datetime) -> Path:
    stamp = checked_at.strftime("%Y%m%d_%H%M%S")
    base = archive_dir / f"pipeline_events.{stamp}.archived.jsonl"
    if not base.exists():
        return base
    for index in range(1, 1000):
        candidate = archive_dir / f"pipeline_events.{stamp}.{index}.archived.jsonl"
        if not candidate.exists():
            return candidate
    raise OSError(f"could not allocate unique archive path under {archive_dir}")


def _path(value: Any) -> Path | None:
    if value in (None, ""):
        return None
    try:
        return Path(str(value))
    except (TypeError, ValueError):
        return None


def _resolved_path(path: Path) -> Path:
    try:
        return path.resolve(strict=False)
    except OSError:
        return path.absolute()


def _is_under(path: Path, root: Path) -> bool:
    resolved = _resolved_path(path)
    root_resolved = _resolved_path(root)
    return resolved == root_resolved or resolved.is_relative_to(root_resolved)


def _would_not_touch() -> dict[str, str]:
    return {
        "source_media": "not scanned, moved, renamed, overwritten, or deleted",
        "pending_publish": "parked payloads and manifests are not scanned, drained, moved, or rewritten",
        "completed_manifest": "completed manifest is not archived or rewritten",
        "queue_state": "queue snapshots and priority state are not archived or rewritten",
        "progress_state": "pipeline_progress.json is not archived or rewritten",
        "final_output": "final output roots are not scanned or changed",
    }


def _summary_lines(moved: list[dict[str, Any]], skipped: list[dict[str, Any]], errors: list[str]) -> list[str]:
    if errors:
        return [f"Event journal archive failed: {'; '.join(errors)}"]
    if moved:
        first = moved[0]
        return [
            f"Archived oversized event journal: {first.get('path')}",
            f"Archive path: {first.get('archive_path')}",
            "A fresh empty pipeline_events.jsonl replacement was created.",
        ]
    reason = str((skipped[0] if skipped else {}).get("skipped_reason") or "no eligible event journal")
    return [f"No event journal archived: {reason}."]


__all__ = [
    "STATE_JOURNAL_ARCHIVE_COMMAND",
    "STATE_JOURNAL_ARCHIVE_SCHEMA_VERSION",
    "PIPELINE_EVENT_JOURNAL_NAME",
    "ARCHIVE_FOLDER_NAME",
    "ARCHIVE_MIN_BYTES",
    "archive_state_journals_payload",
    "unconfirmed_state_journal_archive_payload",
    "close_readiness_blocked_archive_payload",
]
