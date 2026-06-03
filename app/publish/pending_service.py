from __future__ import annotations

from pathlib import Path
from typing import Any

from mediapipeline_desktop_app.models import ResolvedPaths
from app.publish.pending_format import (
    format_bytes_compact,
    format_pending_datetime_text,
    format_pending_timestamp,
    int_or_none,
    parse_pending_datetime,
    pending_age_text,
)
from app.publish.pending_paths import (
    build_pending_orphan_payload_row,
    path_from_manifest,
    path_from_texts,
    pending_item_mtime,
)
from app.publish.file_io import read_json_file
from app.publish.pending_manifest import pending_manifest_row


PENDING_DRAIN_SUMMARY_SCHEMA_VERSION = "pending_drain_summary.v1"
PENDING_FILE_INVENTORY_SCHEMA_VERSION = "desktop_pending_publish_file_inventory.v1"
PENDING_FILE_INVENTORY_LIMIT = 500


def pending_drain_summary_path(resolved: ResolvedPaths, pending_root: Path | None) -> Path | None:
    if resolved.state_root is not None:
        return resolved.state_root / "Progress" / "pending_drain_summary.json"
    if pending_root is not None:
        return pending_root.parent / "Progress" / "pending_drain_summary.json"
    return None


def read_pending_drain_summary(resolved: ResolvedPaths, pending_root: Path | None) -> dict[str, Any]:
    summary_path = pending_drain_summary_path(resolved, pending_root)
    if summary_path is None:
        return {
            "schema_version": PENDING_DRAIN_SUMMARY_SCHEMA_VERSION,
            "exists": False,
            "path": "",
            "items": [],
            "warnings": ["Pending drain summary path is not resolved."],
        }

    base: dict[str, Any] = {
        "schema_version": PENDING_DRAIN_SUMMARY_SCHEMA_VERSION,
        "exists": summary_path.exists(),
        "path": str(summary_path),
        "items": [],
    }
    if not summary_path.exists():
        return base

    try:
        payload = read_json_file(summary_path, retries=2)
    except Exception as exc:
        return {
            **base,
            "exists": True,
            "read_error": str(exc),
            "warnings": [f"Pending drain summary could not be read: {exc}"],
        }
    if not isinstance(payload, dict):
        return {
            **base,
            "exists": True,
            "read_error": "Pending drain summary JSON root is not an object.",
            "warnings": ["Pending drain summary JSON root is not an object."],
        }

    summary = dict(payload)
    summary["schema_version"] = str(summary.get("schema_version") or PENDING_DRAIN_SUMMARY_SCHEMA_VERSION)
    summary["exists"] = True
    summary["path"] = str(summary_path)
    if not isinstance(summary.get("items"), list):
        summary["items"] = []
        warnings = list(summary.get("warnings") or [])
        warnings.append("Pending drain summary items were not a list.")
        summary["warnings"] = warnings
    return summary


def _pending_file_inventory_empty(
    pending_root: Path | None,
    *,
    exists: bool,
    status: str,
    error: str = "",
) -> dict[str, Any]:
    return {
        "schema_version": PENDING_FILE_INVENTORY_SCHEMA_VERSION,
        "pending_root": str(pending_root or ""),
        "exists": bool(exists),
        "status": status,
        "rows": [],
        "row_limit": PENDING_FILE_INVENTORY_LIMIT,
        "total_count": 0,
        "shown_count": 0,
        "truncated": False,
        "total_bytes": 0,
        "total_size_text": "0 B",
        "manifest_count": 0,
        "payload_like_count": 0,
        "referenced_payload_count": 0,
        "orphan_payload_count": 0,
        "kind_counts": {},
        "role_counts": {},
        "summary_lines": [
            "Pending parked file inventory:",
            f"Pending root: {pending_root or 'not resolved'}",
            f"Status: {status}",
            "Rows shown: 0",
            "Evidence boundary: directory listing only; file bytes were not read and no files were changed.",
        ],
        "error": error,
    }


def _count_values(rows: list[dict[str, Any]], key: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        value = str(row.get(key) or "unknown").strip() or "unknown"
        counts[value] = counts.get(value, 0) + 1
    return dict(sorted(counts.items()))


def _pending_inventory_file_row(item: Path, referenced_payloads: set[str]) -> dict[str, Any]:
    size = 0
    stat_result = item.stat()
    size = int(stat_result.st_size)
    name = item.name
    lowered = name.casefold()
    is_manifest = name.endswith(".manifest.json")
    kind = "manifest" if is_manifest else "payload"
    role = "manifest" if is_manifest else "referenced_payload" if lowered in referenced_payloads else "orphan_payload"
    status = "manifest" if is_manifest else "referenced" if lowered in referenced_payloads else "unreferenced"
    return {
        "name": name,
        "path": str(item),
        "kind": kind,
        "role": role,
        "status": status,
        "size_bytes": size,
        "size_text": format_bytes_compact(size),
        "modified_at": format_pending_timestamp(pending_item_mtime(item)),
        "evidence": (
            "pending manifest"
            if is_manifest
            else "payload referenced by a pending manifest"
            if lowered in referenced_payloads
            else "file in PendingServerPush with no matching manifest reference"
        ),
    }


def pending_file_inventory(
    pending_root: Path | None,
    files: list[Path] | None,
    *,
    exists: bool,
    referenced_payloads: set[str] | None = None,
    status: str = "complete",
    error: str = "",
) -> dict[str, Any]:
    if not exists or files is None:
        return _pending_file_inventory_empty(pending_root, exists=exists, status=status, error=error)

    references = referenced_payloads or set()
    sorted_files = sorted(files, key=pending_item_mtime, reverse=True)
    rows: list[dict[str, Any]] = []
    for item in sorted_files[:PENDING_FILE_INVENTORY_LIMIT]:
        try:
            rows.append(_pending_inventory_file_row(item, references))
        except OSError as exc:
            rows.append({
                "name": item.name,
                "path": str(item),
                "kind": "unknown",
                "role": "scan_error",
                "status": "error",
                "size_bytes": 0,
                "size_text": "0 B",
                "modified_at": "",
                "evidence": f"Could not stat pending file: {exc}",
                "error": str(exc),
            })

    total_bytes = 0
    for item in sorted_files:
        try:
            total_bytes += int(item.stat().st_size)
        except OSError:
            continue
    manifest_count = sum(1 for item in sorted_files if item.name.endswith(".manifest.json"))
    payload_like_count = max(0, len(sorted_files) - manifest_count)
    referenced_payload_count = sum(
        1 for item in sorted_files
        if not item.name.endswith(".manifest.json") and item.name.casefold() in references
    )
    orphan_payload_count = max(0, payload_like_count - referenced_payload_count)
    truncated = len(sorted_files) > PENDING_FILE_INVENTORY_LIMIT
    summary_lines = [
        "Pending parked file inventory:",
        f"Pending root: {pending_root or 'not resolved'}",
        f"Files scanned: {len(sorted_files)}",
        f"Rows shown: {len(rows)}{' (truncated)' if truncated else ''}",
        f"Manifest files: {manifest_count}",
        f"Payload-like files: {payload_like_count}",
        f"Referenced payload files: {referenced_payload_count}",
        f"Unreferenced payload files: {orphan_payload_count}",
        f"Total size: {format_bytes_compact(total_bytes)}",
        "Evidence boundary: directory listing only; file bytes were not read and no files were changed.",
    ]
    if orphan_payload_count:
        summary_lines.append("Safe next action: inspect unreferenced payload rows with Pending Publish diagnostics before cleanup, rerun, manual move, or drain.")
    return {
        "schema_version": PENDING_FILE_INVENTORY_SCHEMA_VERSION,
        "pending_root": str(pending_root or ""),
        "exists": True,
        "status": status,
        "rows": rows,
        "row_limit": PENDING_FILE_INVENTORY_LIMIT,
        "total_count": len(sorted_files),
        "shown_count": len(rows),
        "truncated": truncated,
        "total_bytes": total_bytes,
        "total_size_text": format_bytes_compact(total_bytes),
        "manifest_count": manifest_count,
        "payload_like_count": payload_like_count,
        "referenced_payload_count": referenced_payload_count,
        "orphan_payload_count": orphan_payload_count,
        "kind_counts": _count_values(rows, "kind"),
        "role_counts": _count_values(rows, "role"),
        "summary_lines": summary_lines,
        "error": error,
    }


def _append_pending_row_error(row: dict[str, Any], message: str) -> None:
    current = str(row.get("error") or "").strip()
    row["error"] = f"{current}; {message}" if current else message


def mark_duplicate_pending_targets(rows: list[dict[str, Any]]) -> None:
    """Flag duplicate manifest targets without changing drain behavior."""
    for key, label in (("local_file", "local payload"), ("server_out", "server destination")):
        groups: dict[str, list[dict[str, Any]]] = {}
        for row in rows:
            if not row.get("manifest_path"):
                continue
            value = str(row.get(key) or "").strip()
            if not value:
                continue
            groups.setdefault(value.casefold(), []).append(row)
        for duplicates in groups.values():
            if len(duplicates) <= 1:
                continue
            message = f"Duplicate pending publish {label} referenced by {len(duplicates)} manifest rows."
            for row in duplicates:
                _append_pending_row_error(row, message)


class PendingPublishServiceMixin:
    def scan_pending_publish(self, resolved: ResolvedPaths) -> dict[str, Any]:
        pending_root = resolved.pending_push_path
        if pending_root is None:
            return {
                "pending_root": "",
                "exists": False,
                "error": "PendingServerPush path is not resolved.",
                "rows": [],
                "count": 0,
                "payload_count": 0,
                "total_bytes": 0,
                "total_size_text": "0 B",
                "missing_local_count": 0,
                "health_count": 0,
                "health_rows": [],
                "drain_summary": self._pending_drain_summary(resolved, pending_root),
                "file_inventory": pending_file_inventory(pending_root, None, exists=False, status="unavailable", error="PendingServerPush path is not resolved."),
            }
        if not pending_root.exists():
            return {
                "pending_root": str(pending_root),
                "exists": False,
                "error": "",
                "rows": [],
                "count": 0,
                "payload_count": 0,
                "total_bytes": 0,
                "total_size_text": "0 B",
                "missing_local_count": 0,
                "health_count": 0,
                "health_rows": [],
                "drain_summary": self._pending_drain_summary(resolved, pending_root),
                "file_inventory": pending_file_inventory(pending_root, None, exists=False, status="missing"),
            }

        try:
            files = [item for item in pending_root.iterdir() if item.is_file()]
        except Exception as exc:
            return {
                "pending_root": str(pending_root),
                "exists": True,
                "error": str(exc),
                "rows": [],
                "count": 0,
                "payload_count": 0,
                "total_bytes": 0,
                "total_size_text": "0 B",
                "missing_local_count": 0,
                "health_count": 1,
                "health_rows": [{"state": "scan_error", "error": str(exc)}],
                "drain_summary": self._pending_drain_summary(resolved, pending_root),
                "file_inventory": pending_file_inventory(pending_root, None, exists=True, status="blocked", error=str(exc)),
            }

        manifests = sorted(
            [item for item in files if item.name.endswith(".manifest.json")],
            key=self._pending_item_mtime,
            reverse=True,
        )
        rows: list[dict[str, Any]] = []
        referenced_payloads: set[str] = set()
        for manifest_path in manifests:
            row = self._pending_manifest_row(manifest_path)
            rows.append(row)
            for path_text in [row.get("local_file", ""), *row.get("sidecar_paths", [])]:
                if path_text:
                    referenced_payloads.add(Path(str(path_text)).name.casefold())

        for item in sorted(files, key=self._pending_item_mtime, reverse=True):
            if item.name.endswith(".manifest.json"):
                continue
            if item.name.casefold() in referenced_payloads:
                continue
            rows.append(self._pending_orphan_payload_row(item))

        mark_duplicate_pending_targets(rows)
        total_bytes = sum(int(row.get("output_size") or 0) for row in rows)
        missing_local_count = sum(1 for row in rows if row.get("local_file") and not row.get("local_exists", False))
        health_rows = [row for row in rows if row.get("error") or (row.get("local_file") and not row.get("local_exists", False))]
        return {
            "pending_root": str(pending_root),
            "exists": True,
            "error": "",
            "rows": rows,
            "count": len(manifests),
            "payload_count": len([item for item in files if not item.name.endswith(".manifest.json")]),
            "total_bytes": total_bytes,
            "total_size_text": self._format_bytes_compact(total_bytes),
            "missing_local_count": missing_local_count,
            "health_count": len(health_rows),
            "health_rows": health_rows,
            "drain_summary": self._pending_drain_summary(resolved, pending_root),
            "file_inventory": pending_file_inventory(
                pending_root,
                files,
                exists=True,
                referenced_payloads=referenced_payloads,
            ),
        }

    def _pending_manifest_row(self, manifest_path: Path) -> dict[str, Any]:
        return pending_manifest_row(manifest_path)

    def _pending_orphan_payload_row(self, payload_path: Path) -> dict[str, Any]:
        return build_pending_orphan_payload_row(payload_path)

    def _pending_drain_summary(self, resolved: ResolvedPaths, pending_root: Path | None) -> dict[str, Any]:
        return read_pending_drain_summary(resolved, pending_root)

    def _path_from_manifest(self, manifest: dict[str, Any], *keys: str) -> Path | None:
        return path_from_manifest(manifest, *keys)

    def _path_from_texts(self, *values: str) -> Path | None:
        return path_from_texts(*values)

    def _pending_item_mtime(self, item: Path) -> float:
        return pending_item_mtime(item)

    def _int_or_none(self, value: Any) -> int | None:
        return int_or_none(value)

    def _format_bytes_compact(self, raw_bytes: int) -> str:
        return format_bytes_compact(raw_bytes)

    def _format_pending_timestamp(self, timestamp: float) -> str:
        return format_pending_timestamp(timestamp)

    def _format_pending_datetime_text(self, value: str) -> str:
        return format_pending_datetime_text(value)

    def _pending_age_text(self, value: str) -> str:
        return pending_age_text(value)

    def _parse_pending_datetime(self, value: str) -> Any:
        return parse_pending_datetime(value)
