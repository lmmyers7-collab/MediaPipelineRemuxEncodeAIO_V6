from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.config.library_profiles import effective_library_profiles_from_config
from app.files.constants import MEDIA_FILE_SUFFIXES
from app.queue.file_io import atomic_write_text
from mediapipeline_desktop_app.models import ResolvedPaths


QUEUE_SCAN_STATUS_SCHEMA_VERSION = "desktop_queue_scan_status.v1"
QUEUE_SOURCE_INVENTORY_SCHEMA_VERSION = "desktop_queue_source_inventory.v1"
QUEUE_SOURCE_INVENTORY_ROW_LIMIT = 5000
QUEUE_SOURCE_INVENTORY_PREVIEW_LIMIT = 250


@dataclass(frozen=True)
class QueueInventoryRoot:
    path: Path
    media_kind: str
    source_key: str
    label: str


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def queue_scan_status_path(resolved: ResolvedPaths) -> Path | None:
    if resolved.state_root is None:
        return None
    return resolved.state_root / "Progress" / "queue_scan_status.json"


def queue_source_inventory_path(resolved: ResolvedPaths) -> Path | None:
    if resolved.state_root is None:
        return None
    return resolved.state_root / "Progress" / "queue_source_inventory.json"


def write_json_artifact(path: Path, payload: dict[str, Any]) -> None:
    atomic_write_text(path, json.dumps(payload, indent=2, sort_keys=True, allow_nan=False) + "\n")


def read_json_artifact(path: Path | None) -> dict[str, Any] | None:
    if path is None or not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None


def _path_key(value: object) -> str:
    return str(value or "").replace("\\", "/").rstrip("/").casefold()


def _path_text(value: object) -> str:
    return str(value or "").strip()


def _media_kind(value: object, fallback: str = "auto") -> str:
    text = str(value or "").strip().casefold()
    if text in {"movie", "movies"}:
        return "movie"
    if text in {"tv", "television", "shows", "show"}:
        return "tv"
    return fallback


def queue_inventory_source_roots(resolved: ResolvedPaths) -> list[QueueInventoryRoot]:
    roots: list[QueueInventoryRoot] = []
    seen: set[str] = set()

    def add(path_value: object, media_kind: str, source_key: str, label: str) -> None:
        text = _path_text(path_value)
        if not text:
            return
        key = _path_key(text)
        if not key or key in seen:
            return
        seen.add(key)
        roots.append(QueueInventoryRoot(path=Path(text), media_kind=media_kind, source_key=source_key, label=label))

    add(resolved.source_movies, "movie", "SourceMovies", "Configured movie source")
    add(resolved.source_tv, "tv", "SourceTV", "Configured TV source")

    try:
        profiles = effective_library_profiles_from_config(resolved.config_data or {})
    except Exception:
        profiles = []
    for profile in profiles:
        if profile.get("enabled", True) is False:
            continue
        source_path = profile.get("effective_source_root") or profile.get("source_path")
        profile_id = str(profile.get("library_id") or profile.get("id") or "library").strip() or "library"
        kind = _media_kind(profile.get("designation"), fallback="auto")
        add(source_path, kind, f"LibraryProfiles:{profile_id}", f"Library profile {profile_id}")

    return roots


def _candidate_key(path: Path) -> str:
    normalized = _path_key(path)
    digest = hashlib.sha256(normalized.encode("utf-8", errors="replace")).hexdigest()
    return digest[:24]


def _relative_path(path: Path, root: Path) -> str:
    try:
        return os.path.relpath(str(path), str(root))
    except ValueError:
        return path.name


def _iso_from_timestamp(timestamp: float) -> str:
    return datetime.fromtimestamp(timestamp, timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _source_inventory_row(path: Path, root: QueueInventoryRoot) -> dict[str, Any] | None:
    try:
        stat = path.stat()
    except OSError:
        return None
    if not path.is_file():
        return None
    size_bytes = int(stat.st_size)
    relative = _relative_path(path, root.path)
    return {
        "candidate_key": _candidate_key(path),
        "source_path": str(path),
        "root_path": str(root.path),
        "relative_path": relative,
        "display_name": path.name,
        "media_kind": root.media_kind,
        "source_key": root.source_key,
        "source_label": root.label,
        "size_bytes": size_bytes,
        "size_gb": round(size_bytes / (1024.0 ** 3), 3),
        "last_write_utc": _iso_from_timestamp(stat.st_mtime),
        "curation_state": "uncurated",
        "launchable": False,
        "route": "pending_backend_curation",
        "inventory_reason": "media_file_suffix_match",
        "safe_next_action": "Wait for backend queue curation before launch decisions.",
    }


def build_queue_source_inventory(
    resolved: ResolvedPaths,
    *,
    scan_id: str,
    row_limit: int = QUEUE_SOURCE_INVENTORY_ROW_LIMIT,
) -> dict[str, Any]:
    produced_at = utc_now_iso()
    rows: list[dict[str, Any]] = []
    warnings: list[str] = []
    roots = queue_inventory_source_roots(resolved)
    visited_dirs = 0
    truncated = False

    for root in roots:
        if not root.path.exists():
            warnings.append(f"Source root missing or unavailable: {root.source_key} = {root.path}")
            continue
        if not root.path.is_dir():
            warnings.append(f"Source root is not a directory: {root.source_key} = {root.path}")
            continue
        try:
            walker = os.walk(root.path, topdown=True, followlinks=False)
            for dirpath, dirnames, filenames in walker:
                dirnames.sort(key=str.casefold)
                filenames.sort(key=str.casefold)
                visited_dirs += 1
                for filename in filenames:
                    if Path(filename).suffix.casefold() not in MEDIA_FILE_SUFFIXES:
                        continue
                    row = _source_inventory_row(Path(dirpath) / filename, root)
                    if row is None:
                        continue
                    rows.append(row)
                    if len(rows) >= row_limit:
                        truncated = True
                        break
                if truncated:
                    break
        except OSError as exc:
            warnings.append(f"Source root scan failed for {root.source_key}: {exc}")
        if truncated:
            warnings.append(f"Source inventory stopped at row limit {row_limit}.")
            break

    rows.sort(key=lambda row: (str(row.get("last_write_utc") or ""), str(row.get("source_path") or "")), reverse=True)
    for index, row in enumerate(rows, start=1):
        row["inventory_order"] = index

    media_kind_counts: dict[str, int] = {}
    source_key_counts: dict[str, int] = {}
    for row in rows:
        kind = str(row.get("media_kind") or "auto")
        source_key = str(row.get("source_key") or "unknown")
        media_kind_counts[kind] = media_kind_counts.get(kind, 0) + 1
        source_key_counts[source_key] = source_key_counts.get(source_key, 0) + 1

    summary_lines = [
        f"Source inventory candidates: {len(rows)}.",
        f"Source roots checked: {len(roots)}; directories visited: {visited_dirs}.",
        "Inventory rows are not launchable. Backend queue curation must produce authoritative queue rows first.",
    ]
    if warnings:
        summary_lines.extend(f"Warning: {warning}" for warning in warnings[:5])

    return {
        "schema_version": QUEUE_SOURCE_INVENTORY_SCHEMA_VERSION,
        "scan_id": scan_id,
        "status": "inventory_complete",
        "curation_state": "uncurated",
        "evidence_authority": "backend_source_inventory",
        "launchable": False,
        "produced_at_utc": produced_at,
        "row_count": len(rows),
        "row_limit": row_limit,
        "rows_truncated": truncated,
        "source_root_count": len(roots),
        "visited_dir_count": visited_dirs,
        "media_kind_counts": media_kind_counts,
        "source_key_counts": source_key_counts,
        "roots": [
            {
                "path": str(root.path),
                "media_kind": root.media_kind,
                "source_key": root.source_key,
                "label": root.label,
            }
            for root in roots
        ],
        "rows": rows,
        "summary_lines": summary_lines,
        "warnings": warnings,
    }


def preview_queue_source_inventory(payload: dict[str, Any] | None, *, row_limit: int = QUEUE_SOURCE_INVENTORY_PREVIEW_LIMIT) -> dict[str, Any]:
    if not isinstance(payload, dict):
        return {
            "schema_version": QUEUE_SOURCE_INVENTORY_SCHEMA_VERSION,
            "status": "not_loaded",
            "curation_state": "not_loaded",
            "launchable": False,
            "row_count": 0,
            "rows": [],
            "summary_lines": ["Source inventory has not been generated yet."],
            "warnings": [],
        }
    result = dict(payload)
    rows = [dict(row) for row in result.get("rows") or [] if isinstance(row, dict)]
    result["available_row_count"] = len(rows)
    result["rows"] = rows[: max(0, row_limit)]
    result["preview_row_limit"] = row_limit
    result["preview_truncated"] = len(rows) > row_limit
    result["launchable"] = False
    return result


def queue_scan_progress_bars(status: str, phase: str, detail: str, source: str, updated_at: str) -> list[dict[str, Any]]:
    normalized = status.strip().casefold()
    phase_key = phase.strip().casefold()
    if normalized == "completed":
        percent = 100.0
        bar_status = "complete"
    elif normalized == "failed":
        percent = 100.0
        bar_status = "blocked"
    elif phase_key == "inventory":
        percent = 35.0
        bar_status = "running"
    elif phase_key == "curating":
        percent = 70.0
        bar_status = "running"
    else:
        percent = 5.0 if normalized == "running" else 0.0
        bar_status = normalized or "idle"
    return [
        {
            "id": "queue_source_scan",
            "label": "Queue source scan",
            "mode": "determinate" if normalized in {"completed", "failed", "running"} else "indeterminate",
            "percent": percent,
            "status": bar_status,
            "detail": detail,
            "source": source,
            "updated_at": updated_at,
            "stale": False,
        }
    ]


def queue_scan_status_payload(
    *,
    scan_id: str = "",
    status: str = "idle",
    phase: str = "idle",
    mode: str = "",
    force: bool = True,
    scope: str = "all",
    requested_at_utc: str = "",
    started_at_utc: str = "",
    updated_at_utc: str = "",
    completed_at_utc: str = "",
    message: str = "",
    status_path: Path | None = None,
    inventory_path: Path | None = None,
    queue_snapshot_path: Path | None = None,
    inventory_count: int = 0,
    curated_row_count: int = 0,
    warnings: list[str] | None = None,
    errors: list[str] | None = None,
) -> dict[str, Any]:
    timestamp = updated_at_utc or utc_now_iso()
    detail = message or status
    source = str(status_path or "")
    return {
        "schema_version": QUEUE_SCAN_STATUS_SCHEMA_VERSION,
        "scan_id": scan_id,
        "status": status,
        "phase": phase,
        "mode": mode,
        "force": bool(force),
        "scope": scope,
        "requested_at_utc": requested_at_utc,
        "started_at_utc": started_at_utc,
        "updated_at_utc": timestamp,
        "completed_at_utc": completed_at_utc,
        "message": detail,
        "running": status == "running",
        "status_path": source,
        "inventory_path": str(inventory_path or ""),
        "queue_snapshot_path": str(queue_snapshot_path or ""),
        "inventory_count": int(inventory_count or 0),
        "curated_row_count": int(curated_row_count or 0),
        "warnings": list(warnings or []),
        "errors": list(errors or []),
        "evidence_authority": "backend_queue_scan_service",
        "mutation_guardrail": "Queue source scan reads source metadata and writes state artifacts only; it does not process, rename, delete, move, publish, drain, or mutate source media.",
        "progress_bars": queue_scan_progress_bars(status, phase, detail, source, timestamp),
    }


def read_queue_scan_status(resolved: ResolvedPaths) -> dict[str, Any]:
    path = queue_scan_status_path(resolved)
    payload = read_json_artifact(path)
    if isinstance(payload, dict) and payload.get("schema_version") == QUEUE_SCAN_STATUS_SCHEMA_VERSION:
        return payload
    return queue_scan_status_payload(
        status_path=path,
        inventory_path=queue_source_inventory_path(resolved),
        queue_snapshot_path=resolved.queue_snapshot_path,
    )


__all__ = [
    "QUEUE_SCAN_STATUS_SCHEMA_VERSION",
    "QUEUE_SOURCE_INVENTORY_PREVIEW_LIMIT",
    "QUEUE_SOURCE_INVENTORY_ROW_LIMIT",
    "QUEUE_SOURCE_INVENTORY_SCHEMA_VERSION",
    "build_queue_source_inventory",
    "preview_queue_source_inventory",
    "queue_scan_status_path",
    "queue_scan_status_payload",
    "queue_source_inventory_path",
    "read_json_artifact",
    "read_queue_scan_status",
    "utc_now_iso",
    "write_json_artifact",
]
