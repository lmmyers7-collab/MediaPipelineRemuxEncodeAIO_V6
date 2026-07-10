from __future__ import annotations

import json
from datetime import datetime, UTC
from pathlib import Path
from typing import Any

from mediapipeline.core.audit.rerun_file_io import atomic_write_text


AUDIT_IGNORE_MANIFEST_VERSION = 1


class AuditIgnoreManifestError(ValueError):
    """Raised when an existing audit ignore manifest cannot be trusted."""


def normalize_audit_ignore_key(path: str | Path | None) -> str:
    text = str(path or "").strip().replace("\\", "/").rstrip("/")
    return text.casefold()


def empty_audit_ignore_manifest() -> dict[str, Any]:
    return {"version": AUDIT_IGNORE_MANIFEST_VERSION, "entries": {}}


def _invalid_audit_ignore_manifest(
    path: Path,
    message: str,
    *,
    strict: bool,
    cause: Exception | None = None,
) -> dict[str, Any]:
    if strict:
        error = AuditIgnoreManifestError(f"Audit ignore manifest is invalid at {path}: {message}")
        if cause is not None:
            raise error from cause
        raise error
    return empty_audit_ignore_manifest()


def read_audit_ignore_manifest(path: Path | None, *, strict: bool = False) -> dict[str, Any]:
    if path is None or not path.exists():
        return empty_audit_ignore_manifest()
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError, UnicodeDecodeError) as exc:
        return _invalid_audit_ignore_manifest(path, str(exc), strict=strict, cause=exc)
    if not isinstance(payload, dict):
        return _invalid_audit_ignore_manifest(path, "expected a JSON object", strict=strict)
    if payload.get("version") != AUDIT_IGNORE_MANIFEST_VERSION:
        return _invalid_audit_ignore_manifest(
            path,
            f"expected version {AUDIT_IGNORE_MANIFEST_VERSION}",
            strict=strict,
        )
    entries = payload.get("entries")
    if not isinstance(entries, dict):
        return _invalid_audit_ignore_manifest(path, "expected entries object", strict=strict)
    normalized_entries: dict[str, Any] = {}
    for key, value in entries.items():
        normalized_key = normalize_audit_ignore_key(key)
        if normalized_key and isinstance(value, dict):
            normalized_entries[normalized_key] = value
    return {"version": AUDIT_IGNORE_MANIFEST_VERSION, "entries": normalized_entries}


def write_audit_ignore_manifest(path: Path, manifest: dict[str, Any]) -> dict[str, Any]:
    entries = manifest.get("entries") if isinstance(manifest, dict) else {}
    payload = {
        "version": AUDIT_IGNORE_MANIFEST_VERSION,
        "entries": entries if isinstance(entries, dict) else {},
    }
    atomic_write_text(path, json.dumps(payload, indent=2, sort_keys=True) + "\n")
    return payload


def audit_ignore_entry_for_path(manifest: dict[str, Any] | None, path: str | Path | None) -> dict[str, Any] | None:
    key = normalize_audit_ignore_key(path)
    entries = manifest.get("entries", {}) if isinstance(manifest, dict) else {}
    entry = entries.get(key) if key and isinstance(entries, dict) else None
    return entry if isinstance(entry, dict) else None


def audit_ignore_manifest_payload(path: Path | None, manifest: dict[str, Any] | None = None) -> dict[str, Any]:
    valid = True
    error = ""
    if isinstance(manifest, dict):
        current = manifest
    elif path is None:
        current = empty_audit_ignore_manifest()
        valid = False
        error = "Audit ignore manifest path is unavailable."
    else:
        try:
            current = read_audit_ignore_manifest(path, strict=True)
        except AuditIgnoreManifestError as exc:
            current = empty_audit_ignore_manifest()
            valid = False
            error = str(exc)
    entries = current.get("entries", {}) if isinstance(current, dict) else {}
    return {
        "schema_version": "desktop_audit_ignore_manifest.v1",
        "path": str(path or ""),
        "valid": valid,
        "error": error,
        "entry_count": len(entries) if isinstance(entries, dict) else 0,
        "entries": entries if isinstance(entries, dict) else {},
    }


def set_audit_ignore_entries(
    path: Path,
    items: list[dict[str, Any]],
    *,
    reason: str = "",
) -> dict[str, Any]:
    manifest = read_audit_ignore_manifest(path, strict=True)
    entries = manifest.setdefault("entries", {})
    now = datetime.now(UTC).isoformat()
    for item in items:
        source_path = str(item.get("path") or "").strip()
        key = normalize_audit_ignore_key(source_path)
        if not key:
            continue
        entries[key] = {
            "path": source_path,
            "reason": str(item.get("reason") or reason or "").strip(),
            "source_csv": str(item.get("source_csv") or "").strip(),
            "issue_code": str(item.get("issue_code") or "").strip(),
            "title": str(item.get("title") or "").strip(),
            "set_at": now,
        }
    return write_audit_ignore_manifest(path, manifest)


def remove_audit_ignore_entries(path: Path, paths: list[str | Path]) -> dict[str, Any]:
    manifest = read_audit_ignore_manifest(path, strict=True)
    entries = manifest.setdefault("entries", {})
    for raw_path in paths:
        key = normalize_audit_ignore_key(raw_path)
        if key:
            entries.pop(key, None)
    return write_audit_ignore_manifest(path, manifest)


__all__ = [
    "AUDIT_IGNORE_MANIFEST_VERSION",
    "AuditIgnoreManifestError",
    "audit_ignore_entry_for_path",
    "audit_ignore_manifest_payload",
    "empty_audit_ignore_manifest",
    "normalize_audit_ignore_key",
    "read_audit_ignore_manifest",
    "remove_audit_ignore_entries",
    "set_audit_ignore_entries",
    "write_audit_ignore_manifest",
]
