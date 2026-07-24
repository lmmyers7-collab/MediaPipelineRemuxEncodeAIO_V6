from __future__ import annotations

import json
import os
from datetime import datetime
from hashlib import sha256
from pathlib import Path
from typing import Any

from mediapipeline.core.paths.layout import ensure_path_boundary_safe_for_mutation
from mediapipeline.core.rename.file_io import atomic_write_text

RENAME_UNDO_SCHEMA_VERSION = "rename_undo.v1"
RENAME_UNDO_PROGRESS_SCHEMA_VERSION = "rename_undo_progress.v1"


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _path_key(path: Path) -> str:
    try:
        text = os.path.abspath(str(path.resolve(strict=False)))
    except OSError:
        text = os.path.abspath(str(path))
    return os.path.normcase(text) if os.name == "nt" else text


def _load_manifest(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise RuntimeError(f"Rename undo manifest could not be read: {exc}") from exc
    if not isinstance(data, dict):
        raise RuntimeError("Rename undo manifest must contain a JSON object.")
    return data


def _write_manifest(path: Path, manifest: dict[str, Any]) -> None:
    atomic_write_text(path, json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _manifest_operations(manifest: dict[str, Any]) -> list[dict[str, Any]]:
    raw_operations = manifest.get("operations")
    if not isinstance(raw_operations, list) or not raw_operations:
        raise RuntimeError("Rename undo manifest has no operations to undo.")
    operations: list[dict[str, Any]] = []
    for index, raw_operation in enumerate(raw_operations, start=1):
        if not isinstance(raw_operation, dict):
            raise RuntimeError(f"Rename undo operation {index} is not an object.")
        kind = str(raw_operation.get("kind") or "").strip()
        source = str(raw_operation.get("source") or "").strip()
        destination = str(raw_operation.get("destination") or "").strip()
        boundary_root = str(raw_operation.get("boundary_root") or "").strip()
        if not kind or not source or not destination:
            raise RuntimeError(f"Rename undo operation {index} is missing kind, source, or destination.")
        operation: dict[str, Any] = {
            "kind": kind,
            "source": source,
            "destination": destination,
            "boundary_root": boundary_root,
        }
        parsed_identity = raw_operation.get("parsed_identity")
        if isinstance(parsed_identity, dict):
            operation["parsed_identity"] = dict(parsed_identity)
        tv_identity = raw_operation.get("tv_identity")
        if isinstance(tv_identity, dict):
            operation["tv_identity"] = dict(tv_identity)
        destination_identity_key = str(raw_operation.get("destination_identity_key") or "").strip()
        if destination_identity_key:
            operation["destination_identity_key"] = destination_identity_key
        operations.append(operation)
    return operations


def _manifest_metadata_backups(manifest: dict[str, Any]) -> list[dict[str, Any]]:
    raw_backups = manifest.get("metadata_backups")
    if isinstance(raw_backups, dict):
        return [
            {"path": str(path), "content": content, "existed": content is not None}
            for path, content in raw_backups.items()
        ]
    if not isinstance(raw_backups, list):
        return []
    return [item for item in raw_backups if isinstance(item, dict) and str(item.get("path") or "").strip()]


def _operation_id(operation: dict[str, Any]) -> str:
    payload = json.dumps(operation, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return sha256(payload.encode("utf-8")).hexdigest()


def _undo_progress_operations(
    manifest: dict[str, Any],
    operations: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], bool]:
    raw_progress = manifest.get("undo_progress")
    if raw_progress is None:
        entries = [
            {
                "operation_index": index,
                "operation_id": _operation_id(operation),
                "status": "prepared",
            }
            for index, operation in enumerate(operations)
        ]
        manifest["undo_progress"] = {
            "schema_version": RENAME_UNDO_PROGRESS_SCHEMA_VERSION,
            "operations": entries,
        }
        return entries, True
    if not isinstance(raw_progress, dict):
        raise RuntimeError("Rename undo progress must contain an object.")
    if str(raw_progress.get("schema_version") or "") != RENAME_UNDO_PROGRESS_SCHEMA_VERSION:
        raise RuntimeError("Rename undo progress schema is not rename_undo_progress.v1.")
    raw_entries = raw_progress.get("operations")
    if not isinstance(raw_entries, list) or len(raw_entries) != len(operations):
        raise RuntimeError("Rename undo progress operation count does not match the manifest.")
    validated_entries: list[dict[str, Any]] = []
    for index, (raw_entry, operation) in enumerate(zip(raw_entries, operations, strict=True)):
        if not isinstance(raw_entry, dict):
            raise RuntimeError(f"Rename undo progress operation {index + 1} is not an object.")
        if raw_entry.get("operation_index") != index or str(raw_entry.get("operation_id") or "") != _operation_id(
            operation
        ):
            raise RuntimeError(f"Rename undo progress identity mismatch for operation {index + 1}.")
        status = str(raw_entry.get("status") or "")
        if status not in {"prepared", "committed"}:
            raise RuntimeError(f"Rename undo progress operation {index + 1} has invalid status: {status or '<empty>'}.")
        validated_entries.append(dict(raw_entry))
    manifest["undo_progress"] = {
        "schema_version": RENAME_UNDO_PROGRESS_SCHEMA_VERSION,
        "operations": validated_entries,
    }
    return validated_entries, False


def _operation_layout_state(service: Any, operation: dict[str, Any]) -> str:
    original = Path(operation["source"])
    current = Path(operation["destination"])
    original_exists = original.exists()
    current_exists = current.exists()
    if original_exists and current_exists:
        if service._resolve_same_file(original, current):
            return "same_file"
        return "collision"
    if current_exists:
        return "forward"
    if original_exists:
        return "reversed"
    return "missing"


def _preflight_undo_operations(
    service: Any,
    operations: list[dict[str, Any]],
    progress: list[dict[str, Any]],
) -> tuple[list[str], bool]:
    errors: list[str] = []
    restore_targets: set[str] = set()
    progress_changed = False
    for index, operation in enumerate(operations):
        original = Path(operation["source"])
        current = Path(operation["destination"])
        boundary_root_text = str(operation.get("boundary_root") or "").strip()
        boundary_root = Path(boundary_root_text) if boundary_root_text else original.parent
        try:
            ensure_path_boundary_safe_for_mutation(current, boundary_root, allow_missing_leaf=True)
            ensure_path_boundary_safe_for_mutation(original, boundary_root, allow_missing_leaf=True)
        except Exception as exc:
            errors.append(f"{current} -> {original}: {exc}")
            continue
        target_key = _path_key(original)
        if target_key in restore_targets:
            errors.append(f"duplicate undo target: {original}")
        restore_targets.add(target_key)
        layout = _operation_layout_state(service, operation)
        status = str(progress[index]["status"])
        if layout == "collision":
            errors.append(f"cannot undo {current}; original path already exists: {original}")
        elif layout == "missing":
            errors.append(f"cannot undo {current}; renamed path is missing")
        elif status == "committed" and layout == "forward":
            errors.append(f"cannot resume undo {current}; committed original path is missing: {original}")
        elif status == "prepared" and layout in {"reversed", "same_file"}:
            progress[index]["status"] = "committed"
            progress[index]["reconciled_at"] = _now()
            progress[index]["reconciled_from_layout"] = True
            progress_changed = True
    return errors, progress_changed


def _metadata_backup_operation(
    backup: dict[str, Any],
    operations: list[dict[str, Any]],
) -> dict[str, Any] | None:
    paired_destination = str(backup.get("operation_destination") or "").strip()
    if paired_destination:
        paired_key = _path_key(Path(paired_destination))
        return next(
            (operation for operation in operations if _path_key(Path(operation["destination"])) == paired_key),
            None,
        )
    backup_path = Path(str(backup.get("path") or ""))
    backup_key = _path_key(backup_path)
    for operation in operations:
        destination = Path(operation["destination"])
        if backup_key == _path_key(destination):
            return operation
        if _path_key(backup_path.parent) == _path_key(destination.parent) and backup_path.name.casefold().startswith(
            destination.stem.casefold() + "."
        ):
            return operation
    return None


def _metadata_restore_path(backup: dict[str, Any], operation: dict[str, Any]) -> Path:
    backup_path = Path(str(backup.get("path") or ""))
    destination = Path(operation["destination"])
    source = Path(operation["source"])
    if _path_key(backup_path) == _path_key(destination):
        return source
    if _path_key(backup_path.parent) == _path_key(destination.parent):
        destination_prefix = destination.stem
        if backup_path.name.casefold().startswith(destination_prefix.casefold() + "."):
            suffix = backup_path.name[len(destination_prefix) :]
            return source.parent / f"{source.stem}{suffix}"
    return backup_path


def _preflight_metadata_backups(
    manifest: dict[str, Any],
    operations: list[dict[str, Any]],
) -> list[str]:
    errors: list[str] = []
    for backup in _manifest_metadata_backups(manifest):
        operation = _metadata_backup_operation(backup, operations)
        if operation is None:
            errors.append(f"metadata backup is not paired with an undo operation: {backup.get('path') or ''}")
            continue
        boundary_text = str(operation.get("boundary_root") or "").strip()
        boundary_root = Path(boundary_text) if boundary_text else Path(operation["source"]).parent
        backup_path = Path(str(backup.get("path") or ""))
        restore_path = _metadata_restore_path(backup, operation)
        try:
            ensure_path_boundary_safe_for_mutation(backup_path, boundary_root, allow_missing_leaf=True)
            ensure_path_boundary_safe_for_mutation(restore_path, boundary_root, allow_missing_leaf=True)
        except Exception as exc:
            errors.append(f"metadata backup boundary check failed for {backup_path}: {exc}")
    return errors


def _restore_metadata_backups(
    manifest: dict[str, Any],
    operations: list[dict[str, Any]],
) -> list[str]:
    warnings: list[str] = []
    for backup in _manifest_metadata_backups(manifest):
        backup_path = Path(str(backup.get("path") or ""))
        operation = _metadata_backup_operation(backup, operations)
        if operation is None:
            raise RuntimeError(f"Rename undo metadata backup is not paired with an operation: {backup_path}")
        boundary_text = str(operation.get("boundary_root") or "").strip()
        boundary_root = Path(boundary_text) if boundary_text else Path(operation["source"]).parent
        restore_path = _metadata_restore_path(backup, operation)
        content = backup.get("content")
        try:
            ensure_path_boundary_safe_for_mutation(backup_path, boundary_root, allow_missing_leaf=True)
            ensure_path_boundary_safe_for_mutation(restore_path, boundary_root, allow_missing_leaf=True)
            if content is None:
                if restore_path.exists():
                    restore_path.unlink()
            else:
                atomic_write_text(restore_path, str(content), encoding="utf-8")
        except Exception as exc:
            warnings.append(f"Metadata restore failed for {restore_path}: {exc}")
    return warnings


def undo_rename_manifest_for_service(
    service: Any,
    undo_manifest: Path,
    *,
    undo_manifest_root: Path | None,
) -> dict[str, Any]:
    if undo_manifest_root is None:
        raise RuntimeError("Rename undo root is not available.")
    root = Path(undo_manifest_root)
    manifest_path = Path(undo_manifest)
    ensure_path_boundary_safe_for_mutation(manifest_path, root)
    manifest = _load_manifest(manifest_path)
    if str(manifest.get("schema_version") or "") != RENAME_UNDO_SCHEMA_VERSION:
        raise RuntimeError("Rename undo manifest schema is not rename_undo.v1.")
    if str(manifest.get("status") or "") != "completed":
        raise RuntimeError("Only completed rename manifests can be undone.")
    if str(manifest.get("undo_status") or "") == "completed":
        raise RuntimeError("This rename manifest has already been undone.")
    operations = _manifest_operations(manifest)
    progress, progress_created = _undo_progress_operations(manifest, operations)
    preflight_errors, progress_reconciled = _preflight_undo_operations(service, operations, progress)
    preflight_errors.extend(_preflight_metadata_backups(manifest, operations))
    if preflight_errors:
        raise RuntimeError("Rename undo blocked: " + " | ".join(preflight_errors[:6]))

    previous_undo_status = str(manifest.get("undo_status") or "")
    manifest["undo_status"] = "undoing"
    if not str(manifest.get("undo_started_at") or ""):
        manifest["undo_started_at"] = _now()
    elif previous_undo_status in {"failed", "undoing"} or progress_reconciled:
        manifest["undo_resumed_at"] = _now()
    manifest["undo_errors"] = []
    if progress_created:
        manifest["undo_progress_created_at"] = _now()
    _write_manifest(manifest_path, manifest)

    rows: list[dict[str, Any]] = []
    warnings: list[str] = []
    try:
        for operation_index in reversed(range(len(operations))):
            operation = operations[operation_index]
            progress_entry = progress[operation_index]
            original = Path(operation["source"])
            current = Path(operation["destination"])
            boundary_root_text = str(operation.get("boundary_root") or "").strip()
            boundary_root = Path(boundary_root_text) if boundary_root_text else original.parent
            resume_state = ""
            if progress_entry["status"] == "committed":
                status = "skipped"
                resume_state = (
                    "reconciled_from_layout"
                    if progress_entry.get("reconciled_from_layout")
                    else "previously_committed"
                )
            else:
                service._rename_path_case_safe(current, original, boundary_root=boundary_root)
                status = "undone"
                progress_entry["status"] = "committed"
                progress_entry["committed_at"] = _now()
                _write_manifest(manifest_path, manifest)
            rows.append(
                {
                    "kind": operation["kind"],
                    "source": str(current),
                    "destination": str(original),
                    "status": status,
                    **({"resume_state": resume_state} if resume_state else {}),
                    **(
                        {"parsed_identity": dict(operation["parsed_identity"])}
                        if isinstance(operation.get("parsed_identity"), dict)
                        else {}
                    ),
                    **(
                        {"destination_identity_key": str(operation["destination_identity_key"])}
                        if operation.get("destination_identity_key")
                        else {}
                    ),
                }
            )
        warnings.extend(_restore_metadata_backups(manifest, operations))
        if not _manifest_metadata_backups(manifest) and any(operation["kind"] == "sidecar" for operation in operations):
            warnings.append("Undo manifest did not include metadata backups; verify sidecar metadata after undo.")
        manifest["undo_status"] = "completed"
        manifest["undo_completed_at"] = _now()
        manifest["undo_errors"] = []
        if warnings:
            manifest["undo_warnings"] = warnings
        _write_manifest(manifest_path, manifest)
    except Exception as exc:
        manifest["undo_status"] = "failed"
        manifest["undo_failed_at"] = _now()
        manifest["undo_errors"] = [str(exc)]
        _write_manifest(manifest_path, manifest)
        raise

    media_operations = sum(1 for operation in operations if operation["kind"] == "media")
    sidecar_operations = sum(1 for operation in operations if operation["kind"] == "sidecar")
    return {
        "schema_version": "desktop_rename_undo_result.v1",
        "undo_manifest": str(manifest_path),
        "media_operations": media_operations,
        "sidecar_operations": sidecar_operations,
        "undone": sum(1 for row in rows if row["status"] == "undone"),
        "skipped": sum(1 for row in rows if row["status"] == "skipped"),
        "failed": 0,
        "rows": rows,
        "warnings": warnings,
    }
