from __future__ import annotations

import hashlib
import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from mediapipeline.core.paths.contracts import ResolvedPaths
from mediapipeline.core.queue.file_io import atomic_write_text


QUEUE_DISCOVERY_MANIFEST_SCHEMA_VERSION = "queue_discovery_manifest.v1"
QUEUE_DISCOVERY_KEEP_COMPLETED = 5


def queue_scans_root(resolved: ResolvedPaths) -> Path | None:
    return resolved.state_root / "Progress" / "QueueScans" if resolved.state_root is not None else None


def _path_key(value: object) -> str:
    return os.path.normcase(os.path.abspath(str(value or ""))).rstrip("\\/")


def _configured_root_keys(resolved: ResolvedPaths) -> list[str]:
    roots: list[str] = []
    for value in (resolved.source_movies, resolved.source_tv):
        if value:
            roots.append(_path_key(value))
    for profile in resolved.config_data.get("LibraryProfiles") or []:
        if not isinstance(profile, dict) or profile.get("enabled", True) is False:
            continue
        value = profile.get("effective_source_root") or profile.get("source_path")
        if value:
            roots.append(_path_key(value))
    return sorted(set(value for value in roots if value))


def configured_roots_fingerprint(resolved: ResolvedPaths) -> str:
    value = "\n".join(_configured_root_keys(resolved)).encode("utf-8", errors="replace")
    return hashlib.sha256(value).hexdigest()


def write_queue_discovery_artifact(
    resolved: ResolvedPaths,
    *,
    scan_id: str,
    inventory: dict[str, Any],
) -> Path | None:
    scans_root = queue_scans_root(resolved)
    if scans_root is None:
        return None
    scan_dir = scans_root / scan_id
    scan_dir.mkdir(parents=True, exist_ok=True)
    candidates_path = scan_dir / "source_candidates.jsonl"
    rows = [dict(row) for row in inventory.get("rows") or [] if isinstance(row, dict)]
    lines = [json.dumps(row, sort_keys=True, separators=(",", ":"), allow_nan=False) for row in rows]
    candidates_text = "\n".join(lines) + ("\n" if lines else "")
    atomic_write_text(candidates_path, candidates_text)
    checksum = hashlib.sha256(candidates_text.encode("utf-8")).hexdigest()
    manifest = {
        "schema_version": QUEUE_DISCOVERY_MANIFEST_SCHEMA_VERSION,
        "status": "complete",
        "scan_id": scan_id,
        "completed_at_utc": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "configured_roots_fingerprint": configured_roots_fingerprint(resolved),
        "candidate_count": len(rows),
        "directory_count": int(inventory.get("directory_count") or 0),
        "candidates_path": str(candidates_path),
        "candidates_sha256": checksum,
        "roots": list(inventory.get("roots") or []),
        "source_inventory_schema_version": str(inventory.get("schema_version") or ""),
    }
    manifest_path = scan_dir / "source_manifest.json"
    atomic_write_text(manifest_path, json.dumps(manifest, indent=2, sort_keys=True, allow_nan=False) + "\n")
    _retain_completed_scan_dirs(scans_root, active_scan_id=scan_id)
    return manifest_path


def validate_queue_discovery_artifact(resolved: ResolvedPaths, manifest_path: Path) -> tuple[bool, str, dict[str, Any] | None]:
    scans_root = queue_scans_root(resolved)
    if scans_root is None:
        return False, "state_root_unavailable", None
    try:
        manifest_resolved = manifest_path.resolve(strict=True)
        manifest_resolved.relative_to(scans_root.resolve(strict=False))
        manifest = json.loads(manifest_resolved.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError, json.JSONDecodeError):
        return False, "manifest_unreadable_or_out_of_scope", None
    if not isinstance(manifest, dict) or manifest.get("schema_version") != QUEUE_DISCOVERY_MANIFEST_SCHEMA_VERSION:
        return False, "manifest_schema_invalid", None
    if manifest.get("status") != "complete":
        return False, "manifest_incomplete", None
    if manifest.get("configured_roots_fingerprint") != configured_roots_fingerprint(resolved):
        return False, "configured_roots_mismatch", None
    candidates_path = Path(str(manifest.get("candidates_path") or ""))
    try:
        candidates_resolved = candidates_path.resolve(strict=True)
        candidates_resolved.relative_to(manifest_resolved.parent)
        content = candidates_resolved.read_bytes()
    except (OSError, ValueError):
        return False, "candidate_artifact_unreadable_or_out_of_scope", None
    if hashlib.sha256(content).hexdigest() != str(manifest.get("candidates_sha256") or ""):
        return False, "candidate_checksum_mismatch", None
    lines = [line for line in content.decode("utf-8-sig").splitlines() if line.strip()]
    if len(lines) != int(manifest.get("candidate_count") or 0):
        return False, "candidate_count_mismatch", None
    roots = _configured_root_keys(resolved)
    try:
        for line in lines:
            row = json.loads(line)
            source_key = _path_key(row.get("source_path"))
            root_key = _path_key(row.get("root_path"))
            if root_key not in roots or not (source_key == root_key or source_key.startswith(root_key + os.sep)):
                return False, "candidate_path_out_of_scope", None
    except (TypeError, ValueError, json.JSONDecodeError):
        return False, "candidate_record_invalid", None
    return True, "", manifest


def latest_valid_queue_discovery_artifact(resolved: ResolvedPaths) -> tuple[Path | None, str]:
    scans_root = queue_scans_root(resolved)
    if scans_root is None or not scans_root.is_dir():
        return None, "discovery_artifact_missing"
    manifests = sorted(
        scans_root.glob("*/source_manifest.json"),
        key=lambda path: path.stat().st_mtime if path.exists() else 0.0,
        reverse=True,
    )
    last_reason = "discovery_artifact_missing"
    for path in manifests:
        valid, reason, _manifest = validate_queue_discovery_artifact(resolved, path)
        if valid:
            return path, ""
        last_reason = reason
    return None, last_reason


def _retain_completed_scan_dirs(scans_root: Path, *, active_scan_id: str) -> None:
    protected_scan_dirs: set[str] = set()
    state_root = scans_root.parent.parent
    lease_root = state_root / "QueueLeases"
    if lease_root.is_dir():
        for lease_path in lease_root.glob("*.json"):
            try:
                lease = json.loads(lease_path.read_text(encoding="utf-8-sig"))
                referenced = Path(str(lease.get("discovery_manifest_path") or "")).resolve(strict=False).parent
                referenced.relative_to(scans_root.resolve(strict=False))
                protected_scan_dirs.add(str(referenced).casefold())
            except (OSError, ValueError, json.JSONDecodeError, AttributeError):
                continue
    completed: list[tuple[float, Path]] = []
    for manifest_path in scans_root.glob("*/source_manifest.json"):
        if manifest_path.parent.name == active_scan_id:
            continue
        if str(manifest_path.parent.resolve(strict=False)).casefold() in protected_scan_dirs:
            continue
        try:
            payload = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
            if payload.get("status") == "complete":
                completed.append((manifest_path.stat().st_mtime, manifest_path.parent))
        except (OSError, json.JSONDecodeError, AttributeError):
            continue
    for _mtime, directory in sorted(completed, reverse=True)[QUEUE_DISCOVERY_KEEP_COMPLETED - 1 :]:
        # Artifacts are derived and disposable. Refuse symlinks and only remove known files.
        if directory.is_symlink():
            continue
        for leaf in ("source_manifest.json", "source_candidates.jsonl", "output_paths.jsonl"):
            path = directory / leaf
            try:
                path.unlink(missing_ok=True)
            except OSError:
                pass
        try:
            directory.rmdir()
        except OSError:
            pass


__all__ = [
    "QUEUE_DISCOVERY_MANIFEST_SCHEMA_VERSION",
    "configured_roots_fingerprint",
    "latest_valid_queue_discovery_artifact",
    "queue_scans_root",
    "validate_queue_discovery_artifact",
    "write_queue_discovery_artifact",
]
