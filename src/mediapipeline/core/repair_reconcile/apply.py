from __future__ import annotations

import hashlib
import json
import os
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from mediapipeline.core.completed.manifest import completed_sidecar_path_from_payload
from mediapipeline.core.completed.policy import completed_record_key
from mediapipeline.core.kernel.dto_commands import CommandResult
from mediapipeline.core.completed.contracts import CompletedJobRecord
from mediapipeline.core.kernel.contracts.pending_publish import PendingPushManifest

from .dry_run import (
    COMPLETED_RECONCILE_MANIFEST_COMMAND,
    COMPLETED_REPAIR_SIDECAR_METADATA_COMMAND,
    PENDING_PUBLISH_RECONCILE_ORPHAN_PAYLOADS_COMMAND,
    PENDING_PUBLISH_REPAIR_MANIFEST_COMMAND,
)


REPAIR_RECONCILE_APPLY_SCHEMA_VERSION = "desktop_repair_reconcile_apply.v1"

_EFFECT_BY_COMMAND = {
    COMPLETED_RECONCILE_MANIFEST_COMMAND: "completed-manifest-write",
    COMPLETED_REPAIR_SIDECAR_METADATA_COMMAND: "completed-sidecar-json-write",
    PENDING_PUBLISH_REPAIR_MANIFEST_COMMAND: "pending-manifest-write",
    PENDING_PUBLISH_RECONCILE_ORPHAN_PAYLOADS_COMMAND: "pending-orphan-manifest-write",
}


def _transaction_id() -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"repair-reconcile-{stamp}-{uuid.uuid4().hex[:8]}"


def _json_dumps(value: Mapping[str, Any]) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n"


def _atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    try:
        with temp.open("w", encoding="utf-8", newline="\n") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp, path)
    finally:
        if temp.exists():
            temp.unlink()


def _read_json_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Expected JSON object in {path}")
    return value


def _file_state(path: Path) -> dict[str, Any]:
    if not path.exists() or not path.is_file():
        return {"exists": path.exists(), "is_file": path.is_file() if path.exists() else False}
    data = path.read_bytes()
    return {"exists": True, "is_file": True, "size": len(data), "sha256": hashlib.sha256(data).hexdigest()}


def _backup_path(backup_root: Path, path: Path) -> Path:
    return backup_root / path.name


def _path_identity(value: object) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    return str(Path(text)).casefold()


def _pending_orphan_expected_manifest_path(payload_path: Path) -> Path:
    return payload_path.with_name(f"{payload_path.name}.manifest.json")


def _pending_manifest_sidecar_paths(sidecar_files: Any) -> list[Path]:
    if not isinstance(sidecar_files, list):
        return []
    paths: list[Path] = []
    for sidecar in sidecar_files:
        if not isinstance(sidecar, Mapping):
            continue
        raw = str(sidecar.get("local_file") or sidecar.get("parked_file") or "").strip()
        if raw:
            paths.append(Path(raw))
    return paths


def _copy_backup(path: Path, backup_root: Path) -> Path:
    if not path.exists() or not path.is_file():
        raise FileNotFoundError(f"Cannot back up missing file: {path}")
    backup = _backup_path(backup_root, path)
    backup.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(path, backup)
    return backup


def _base_data(
    *,
    candidate_command: str,
    dry_run: Mapping[str, Any] | None,
    transaction_id: str,
    expected_fingerprint: str = "",
    requested_fingerprint: str = "",
) -> dict[str, Any]:
    selected = list((dry_run or {}).get("selected_row_keys") or [])
    return {
        "schema_version": REPAIR_RECONCILE_APPLY_SCHEMA_VERSION,
        "candidate_command": candidate_command,
        "effect": _EFFECT_BY_COMMAND.get(candidate_command, "repair-reconcile-write"),
        "selected_row_keys": selected,
        "applied": False,
        "blocked": True,
        "written_paths": [],
        "backup_paths": [],
        "transaction_id": transaction_id,
        "rollback_status": "not_started",
        "dry_run_fingerprint": requested_fingerprint,
        "expected_dry_run_fingerprint": expected_fingerprint,
        "source_payload_output_unchanged": True,
    }


def _blocked_result(
    *,
    candidate_command: str,
    message: str,
    errors: list[str],
    dry_run: Mapping[str, Any] | None = None,
    transaction_id: str | None = None,
    expected_fingerprint: str = "",
    requested_fingerprint: str = "",
) -> CommandResult:
    tx_id = transaction_id or _transaction_id()
    return CommandResult(
        command=candidate_command,
        ok=False,
        severity="warning",
        message=message,
        errors=errors,
        refresh_hint=_refresh_hint(candidate_command),
        data=_base_data(
            candidate_command=candidate_command,
            dry_run=dry_run,
            transaction_id=tx_id,
            expected_fingerprint=expected_fingerprint,
            requested_fingerprint=requested_fingerprint,
        ),
    )


def _refresh_hint(candidate_command: str) -> str:
    if candidate_command.startswith("completed."):
        return "completed"
    return "pending_publish"


def _state_root(resolved: Any) -> Path:
    raw = getattr(resolved, "state_root", None)
    if raw:
        return Path(raw)
    app_root = getattr(resolved, "app_root", None) or getattr(resolved, "workspace_root", None) or "."
    return Path(app_root) / "State"


def _candidate_rows(dry_run: Mapping[str, Any]) -> list[dict[str, Any]]:
    summary = dry_run.get("diff_summary")
    rows = summary.get("rows") if isinstance(summary, Mapping) else []
    return [
        dict(row)
        for row in rows or []
        if isinstance(row, Mapping) and str(row.get("status") or "").casefold() == "candidate"
    ]


def _paths_to_protect(rows: list[Mapping[str, Any]]) -> list[Path]:
    protected: list[Path] = []
    for row in rows:
        for key in ("source_path", "output_path", "local_file"):
            raw = str(row.get(key) or "").strip()
            if raw:
                protected.append(Path(raw))
        proposed = row.get("proposed")
        if isinstance(proposed, Mapping):
            for key in ("source_path", "output_path", "local_file"):
                raw = str(proposed.get(key) or "").strip()
                if raw:
                    protected.append(Path(raw))
        changed = row.get("changed_fields")
        if isinstance(changed, Mapping):
            for key in ("source_path", "output_path", "local_file"):
                value = changed.get(key)
                if isinstance(value, Mapping):
                    raw = str(value.get("proposed") or "").strip()
                    if raw:
                        protected.append(Path(raw))
    unique: dict[str, Path] = {}
    for path in protected:
        unique[str(path).casefold()] = path
    return list(unique.values())


def _unchanged(paths: list[Path], written: set[str], before: dict[str, dict[str, Any]]) -> bool:
    for path in paths:
        if str(path).casefold() in written:
            continue
        if before.get(str(path)) != _file_state(path):
            return False
    return True


def _apply_completed_sidecar_metadata_repair(
    rows: list[Mapping[str, Any]],
    *,
    backup_root: Path,
) -> tuple[list[Path], list[Path]]:
    written: list[Path] = []
    backups: list[Path] = []
    for row in rows:
        if str(row.get("status") or "").casefold() != "candidate":
            raise ValueError(f"Selected sidecar row is not a repair candidate: {row.get('row_key')}")
        path = Path(str(row.get("sidecar_path") or "").strip())
        changed = row.get("changed_fields")
        if not path or not isinstance(changed, Mapping):
            raise ValueError(f"Selected sidecar row lacks backend changed_fields: {row.get('row_key')}")
        current = _read_json_object(path)
        repaired = dict(current)
        for field, value in changed.items():
            if field not in {"source_path", "output_path", "output_file"}:
                continue
            if not isinstance(value, Mapping):
                raise ValueError(f"Invalid changed_fields entry for {field}")
            repaired[field] = str(value.get("proposed") or "")
        backups.append(_copy_backup(path, backup_root))
        _atomic_write_text(path, _json_dumps(repaired))
        written.append(path)
    return written, backups


def _manifest_line_key(manifest_path: Path, payload: dict[str, Any]) -> str:
    sidecar = completed_sidecar_path_from_payload(manifest_path, payload)
    return completed_record_key(CompletedJobRecord(sidecar_path=sidecar, payload=dict(payload)))


def _apply_completed_manifest_reconcile(
    rows: list[Mapping[str, Any]],
    *,
    manifest_path: Path,
    backup_root: Path,
) -> tuple[list[Path], list[Path]]:
    wanted = {str(row.get("row_key") or "").strip(): row for row in rows if str(row.get("status") or "").casefold() == "candidate"}
    if not wanted:
        raise ValueError("No completed manifest candidate rows were selected.")
    lines = manifest_path.read_text(encoding="utf-8").splitlines()
    updated: list[str] = []
    changed_keys: set[str] = set()
    for line in lines:
        if not line.strip():
            updated.append(line)
            continue
        payload = json.loads(line)
        if not isinstance(payload, dict):
            updated.append(line)
            continue
        key = _manifest_line_key(manifest_path, payload)
        row = wanted.get(key)
        if row is None:
            updated.append(line)
            continue
        proposed = row.get("proposed")
        if not isinstance(proposed, Mapping):
            raise ValueError(f"Completed manifest row lacks backend proposed fields: {key}")
        payload["output_path"] = str(proposed.get("output_path") or "")
        payload["output_file"] = str(proposed.get("output_file") or Path(str(payload.get("output_path") or "")).name)
        changed_keys.add(key)
        updated.append(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    missing = sorted(set(wanted) - changed_keys)
    if missing:
        raise ValueError(f"Selected completed manifest row(s) were not found: {', '.join(missing)}")
    backups = [_copy_backup(manifest_path, backup_root)]
    _atomic_write_text(manifest_path, "\n".join(updated) + "\n")
    return [manifest_path], backups


def _apply_pending_manifest_repair(
    rows: list[Mapping[str, Any]],
    *,
    backup_root: Path,
) -> tuple[list[Path], list[Path]]:
    written: list[Path] = []
    backups: list[Path] = []
    for row in rows:
        if str(row.get("status") or "").casefold() != "candidate":
            raise ValueError(f"Selected pending manifest row is not a repair candidate: {row.get('row_key')}")
        path = Path(str(row.get("manifest_path") or "").strip())
        proposed = row.get("proposed_manifest")
        if not path or not isinstance(proposed, Mapping):
            raise ValueError(f"Selected pending manifest row lacks backend proposed manifest fields: {row.get('row_key')}")
        PendingPushManifest.from_mapping(proposed)
        _read_json_object(path)
        repaired = dict(proposed)
        backups.append(_copy_backup(path, backup_root))
        _atomic_write_text(path, _json_dumps(repaired))
        written.append(path)
    return written, backups


def _apply_pending_orphan_manifest_reconcile(rows: list[Mapping[str, Any]]) -> tuple[list[Path], list[Path]]:
    written: list[Path] = []
    for row in rows:
        if str(row.get("status") or "").casefold() != "candidate":
            raise ValueError(f"Selected orphan payload row is not a manifest candidate: {row.get('row_key')}")
        path_text = str(row.get("manifest_path") or "").strip()
        proposed = row.get("proposed_manifest")
        if not path_text or not isinstance(proposed, Mapping):
            raise ValueError(f"Selected orphan payload row lacks backend proposed manifest fields: {row.get('row_key')}")
        path = Path(path_text)
        validated = PendingPushManifest.from_mapping(proposed)
        payload_path = Path(validated.local_file)
        expected_manifest = _pending_orphan_expected_manifest_path(payload_path)
        if _path_identity(path) != _path_identity(expected_manifest):
            raise ValueError("Orphan payload manifest path does not match the payload-adjacent pending manifest path.")
        if path.exists():
            raise ValueError(f"Orphan payload manifest already exists: {path}")
        if not payload_path.exists() or not payload_path.is_file():
            raise ValueError(f"Orphan payload manifest proposal points at a missing payload: {payload_path}")
        if int(validated.output_size) != int(payload_path.stat().st_size):
            raise ValueError("Orphan payload manifest proposal output_size no longer matches the pending payload.")
        missing_sidecars = [str(sidecar) for sidecar in _pending_manifest_sidecar_paths(validated.sidecar_files) if not sidecar.exists()]
        if missing_sidecars:
            raise ValueError(f"Orphan payload manifest proposal references missing pending sidecar payloads: {', '.join(missing_sidecars)}")
        _atomic_write_text(path, _json_dumps(dict(proposed)))
        written.append(path)
    return written, []


def apply_repair_reconcile_from_dry_run(
    *,
    resolved: Any,
    candidate_command: str,
    request: Mapping[str, Any],
    dry_run: Mapping[str, Any],
) -> CommandResult:
    requested_fingerprint = str(request.get("dry_run_fingerprint") or "").strip()
    expected_fingerprint = str(dry_run.get("dry_run_fingerprint") or "").strip()
    transaction_id = _transaction_id()
    if request.get("confirm_apply") is not True:
        return _blocked_result(
            candidate_command=candidate_command,
            message="Repair/reconcile apply requires explicit confirmation.",
            errors=["confirm_apply must be true."],
            dry_run=dry_run,
            transaction_id=transaction_id,
            expected_fingerprint=expected_fingerprint,
            requested_fingerprint=requested_fingerprint,
        )
    if not requested_fingerprint or requested_fingerprint != expected_fingerprint:
        return _blocked_result(
            candidate_command=candidate_command,
            message="Repair/reconcile apply blocked because the dry-run fingerprint no longer matches.",
            errors=["dry_run_fingerprint does not match the current backend dry-run."],
            dry_run=dry_run,
            transaction_id=transaction_id,
            expected_fingerprint=expected_fingerprint,
            requested_fingerprint=requested_fingerprint,
        )
    if dry_run.get("safe_to_apply") is not True:
        return _blocked_result(
            candidate_command=candidate_command,
            message="Repair/reconcile apply blocked because the current dry-run is not safe to apply.",
            errors=["safe_to_apply is false for the current backend dry-run."],
            dry_run=dry_run,
            transaction_id=transaction_id,
            expected_fingerprint=expected_fingerprint,
            requested_fingerprint=requested_fingerprint,
        )
    rows = _candidate_rows(dry_run)
    if not rows:
        return _blocked_result(
            candidate_command=candidate_command,
            message="Repair/reconcile apply blocked because no selected candidate rows were found.",
            errors=["No candidate rows were selected by the current backend dry-run."],
            dry_run=dry_run,
            transaction_id=transaction_id,
            expected_fingerprint=expected_fingerprint,
            requested_fingerprint=requested_fingerprint,
        )

    backup_root = _state_root(resolved) / "RepairReconcileBackups" / transaction_id
    protected_paths = _paths_to_protect(rows)
    protected_before = {str(path): _file_state(path) for path in protected_paths}
    written: list[Path] = []
    backups: list[Path] = []
    rollback_status = "not_needed"
    try:
        if candidate_command == COMPLETED_REPAIR_SIDECAR_METADATA_COMMAND:
            written, backups = _apply_completed_sidecar_metadata_repair(rows, backup_root=backup_root)
        elif candidate_command == COMPLETED_RECONCILE_MANIFEST_COMMAND:
            manifest_path = Path(str(getattr(resolved, "completed_manifest_path", "") or ""))
            written, backups = _apply_completed_manifest_reconcile(rows, manifest_path=manifest_path, backup_root=backup_root)
        elif candidate_command == PENDING_PUBLISH_REPAIR_MANIFEST_COMMAND:
            written, backups = _apply_pending_manifest_repair(rows, backup_root=backup_root)
        elif candidate_command == PENDING_PUBLISH_RECONCILE_ORPHAN_PAYLOADS_COMMAND:
            written, backups = _apply_pending_orphan_manifest_reconcile(rows)
        else:
            raise ValueError(f"Unsupported repair/reconcile apply command: {candidate_command}")
    except Exception as exc:
        rollback_status = "not_started"
        for original, backup in zip(written, backups, strict=False):
            try:
                shutil.copy2(backup, original)
                rollback_status = "restored"
            except Exception:
                rollback_status = "failed"
        data = _base_data(
            candidate_command=candidate_command,
            dry_run=dry_run,
            transaction_id=transaction_id,
            expected_fingerprint=expected_fingerprint,
            requested_fingerprint=requested_fingerprint,
        )
        data["backup_paths"] = [str(path) for path in backups]
        data["rollback_status"] = rollback_status
        data["source_payload_output_unchanged"] = _unchanged(
            protected_paths,
            {str(path).casefold() for path in written},
            protected_before,
        )
        return CommandResult(
            command=candidate_command,
            ok=False,
            severity="error",
            message=f"Repair/reconcile apply failed: {exc}",
            errors=[str(exc)],
            refresh_hint=_refresh_hint(candidate_command),
            data=data,
        )

    written_set = {str(path).casefold() for path in written}
    data = _base_data(
        candidate_command=candidate_command,
        dry_run=dry_run,
        transaction_id=transaction_id,
        expected_fingerprint=expected_fingerprint,
        requested_fingerprint=requested_fingerprint,
    )
    data.update(
        {
            "applied": True,
            "blocked": False,
            "written_paths": [str(path) for path in written],
            "backup_paths": [str(path) for path in backups],
            "rollback_status": rollback_status,
            "source_payload_output_unchanged": _unchanged(protected_paths, written_set, protected_before),
        }
    )
    return CommandResult(
        command=candidate_command,
        ok=True,
        severity="info",
        message=f"{candidate_command} applied to {len(written)} file(s).",
        refresh_hint=_refresh_hint(candidate_command),
        data=data,
    )


__all__ = [
    "REPAIR_RECONCILE_APPLY_SCHEMA_VERSION",
    "apply_repair_reconcile_from_dry_run",
]
