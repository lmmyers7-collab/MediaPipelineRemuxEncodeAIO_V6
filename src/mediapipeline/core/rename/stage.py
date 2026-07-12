"""Scratch-only Python executor for the guarded rename pipeline stage."""

from __future__ import annotations

import hashlib
import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from mediapipeline.contracts.stage_mutation import RenamePayload, RenameResult
from mediapipeline.core.paths.layout import ensure_path_boundary_safe_for_mutation, path_within_root
from mediapipeline.core.rename.apply import rename_path_case_safe
from mediapipeline.core.rename.file_io import atomic_write_text


class RenameStageBoundaryError(RuntimeError):
    """The requested rename is outside the scratch-only mutation boundary."""


class RenameStageFingerprintError(RuntimeError):
    """The execute request no longer matches its dry-run evidence."""


class RenameStageRecoveryError(RuntimeError):
    """The mutation failed after recovery evidence was created."""


def _path_key(path: Path) -> str:
    text = os.path.abspath(str(path.resolve(strict=False)))
    return os.path.normcase(text) if os.name == "nt" else text


def _same_file(left: Path, right: Path) -> bool:
    try:
        return left.samefile(right)
    except (FileNotFoundError, OSError):
        return _path_key(left) == _path_key(right)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_manifest(path: Path, payload: dict[str, Any]) -> None:
    atomic_write_text(path, json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _validated_plan(payload: RenamePayload) -> dict[str, Any]:
    target = Path(payload.target_path)
    scratch_root = Path(payload.scratch_root)
    source_roots = [Path(value) for value in payload.source_roots]
    destination = target.with_name(payload.proposed_name)

    if not scratch_root.exists() or not scratch_root.is_dir():
        raise RenameStageBoundaryError(f"scratch_root must be an existing directory: {scratch_root}")
    try:
        ensure_path_boundary_safe_for_mutation(target, scratch_root)
        ensure_path_boundary_safe_for_mutation(destination, scratch_root, allow_missing_leaf=True)
        ensure_path_boundary_safe_for_mutation(
            destination.parent,
            scratch_root,
            allow_root_target=True,
        )
    except RuntimeError as exc:
        raise RenameStageBoundaryError(str(exc)) from exc

    if not target.is_file():
        raise RenameStageBoundaryError(f"target_path must be one existing regular scratch file: {target}")
    if target.name == destination.name:
        raise RenameStageBoundaryError("rename stage proposed_name must change the scratch file name")
    if target.suffix.casefold() != destination.suffix.casefold():
        raise RenameStageBoundaryError("rename stage cannot change the target file extension")
    if _path_key(target) != _path_key(destination) and destination.exists():
        raise FileExistsError(f"Rename destination already exists: {destination}")

    for source_root in source_roots:
        if not source_root.is_absolute():
            raise RenameStageBoundaryError(f"source_roots entries must be absolute paths: {source_root}")
        if path_within_root(target, source_root):
            raise RenameStageBoundaryError(f"target_path overlaps a protected source root: {source_root}")
        if path_within_root(scratch_root, source_root) or path_within_root(source_root, scratch_root):
            raise RenameStageBoundaryError(
                f"scratch_root must be disjoint from every protected source root: {source_root}"
            )

    content_hash = _sha256(target)
    fingerprint_payload = {
        "schema_version": "pipeline_stage_rename_dry_run.v1",
        "operation": payload.operation,
        "target_path": _path_key(target),
        "destination_path": _path_key(destination),
        "scratch_root": _path_key(scratch_root),
        "source_roots": sorted(_path_key(root) for root in source_roots),
        "target_size_bytes": target.stat().st_size,
        "target_sha256": content_hash,
    }
    fingerprint = hashlib.sha256(
        json.dumps(fingerprint_payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return {
        "target": target,
        "destination": destination,
        "scratch_root": scratch_root,
        "content_hash": content_hash,
        "fingerprint": fingerprint,
        "boundary_checks": [
            "target and destination are children of scratch_root",
            "scratch_root is disjoint from every protected source root",
            "target is a regular non-reparse file and destination does not overwrite another file",
            "file extension is unchanged and no sidecars are selected",
        ],
    }


def execute_scratch_rename_stage(payload: RenamePayload) -> RenameResult:
    """Preview or execute one no-overwrite rename wholly inside scratch."""

    plan = _validated_plan(payload)
    target: Path = plan["target"]
    destination: Path = plan["destination"]
    scratch_root: Path = plan["scratch_root"]
    fingerprint = str(plan["fingerprint"])
    content_hash = str(plan["content_hash"])
    boundary_checks = list(plan["boundary_checks"])
    rollback_actions = [f"rename {destination} back to {target} if execute cannot commit evidence"]
    recovery_actions = ["use the scratch-local undo record to restore the original file name"]

    if payload.intent == "dry_run":
        return RenameResult(
            original_path=str(target),
            final_path=str(destination),
            dry_run_fingerprint=fingerprint,
            content_sha256_before=content_hash,
            content_sha256_after=content_hash,
            source_boundary_untouched=True,
            rollback_actions=rollback_actions,
            recovery_actions=recovery_actions,
            boundary_checks=boundary_checks,
        )

    if payload.dry_run_fingerprint != fingerprint:
        raise RenameStageFingerprintError(
            "Rename execute dry_run_fingerprint does not match the current scratch-only plan."
        )

    undo_root = scratch_root / ".mediapipeline-stage" / "rename"
    undo_path = undo_root / f"{payload.operation_id}.json"
    try:
        ensure_path_boundary_safe_for_mutation(undo_path, scratch_root, allow_missing_leaf=True)
    except RuntimeError as exc:
        raise RenameStageBoundaryError(str(exc)) from exc
    if undo_path.exists():
        raise FileExistsError(f"Rename operation undo record already exists: {undo_path}")
    undo_root.mkdir(parents=True, exist_ok=True)
    manifest: dict[str, Any] = {
        "schema_version": "pipeline_stage_rename_undo.v1",
        "operation_id": payload.operation_id,
        "status": "planned",
        "created_at": datetime.now(UTC).isoformat(),
        "scratch_root": str(scratch_root),
        "original_path": str(target),
        "renamed_path": str(destination),
        "content_sha256": content_hash,
        "dry_run_fingerprint": fingerprint,
        "source_media_mutation": "forbidden",
    }
    _write_manifest(undo_path, manifest)

    renamed = False
    try:
        rename_path_case_safe(target, destination, same_file=_same_file, boundary_root=scratch_root)
        renamed = True
        final_hash = _sha256(destination)
        if final_hash != content_hash:
            raise RenameStageRecoveryError("Renamed scratch file content hash changed unexpectedly.")
        manifest.update(
            {
                "status": "completed",
                "completed_at": datetime.now(UTC).isoformat(),
                "content_sha256_after": final_hash,
            }
        )
        _write_manifest(undo_path, manifest)
    except Exception as exc:
        rollback_error = ""
        if renamed and destination.exists() and not target.exists():
            try:
                rename_path_case_safe(destination, target, same_file=_same_file, boundary_root=scratch_root)
            except Exception as rollback_exc:  # pragma: no cover - platform/filesystem failure edge
                rollback_error = str(rollback_exc)
        manifest.update(
            {
                "status": "rollback_failed" if rollback_error else "rolled_back",
                "failed_at": datetime.now(UTC).isoformat(),
                "failure": str(exc),
                "rollback_error": rollback_error,
            }
        )
        try:
            _write_manifest(undo_path, manifest)
        except Exception:
            pass
        if rollback_error:
            raise RenameStageRecoveryError(
                f"Scratch rename failed and rollback also failed; recover from {undo_path}: {rollback_error}"
            ) from exc
        raise RenameStageRecoveryError(f"Scratch rename failed and was rolled back; evidence: {undo_path}") from exc

    return RenameResult(
        original_path=str(target),
        final_path=str(destination),
        undo_record_path=str(undo_path),
        dry_run_fingerprint=fingerprint,
        content_sha256_before=content_hash,
        content_sha256_after=content_hash,
        source_boundary_untouched=True,
        rollback_actions=rollback_actions,
        recovery_actions=recovery_actions,
        boundary_checks=boundary_checks,
        operation_id=payload.operation_id,
    )


__all__ = [
    "RenameStageBoundaryError",
    "RenameStageFingerprintError",
    "RenameStageRecoveryError",
    "execute_scratch_rename_stage",
]
