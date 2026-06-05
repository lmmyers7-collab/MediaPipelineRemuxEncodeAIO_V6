from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from mediapipeline.core.rename.contracts import RenameApplyServiceProtocol
from mediapipeline.core.rename.file_io import atomic_write_text


def apply_rename_path_plan_for_service(
    service: RenameApplyServiceProtocol,
    plan: list[dict[str, Any]],
    *,
    undo_manifest_root: Path | None = None,
) -> dict[str, Any]:
    blockers = [row for row in plan if row.get("errors")]
    if blockers:
        raise RuntimeError(f"Rename plan has {len(blockers)} blocked row(s). Preview and fix them before applying.")

    applied: list[dict[str, Any]] = []
    completed_ops: list[dict[str, Path | str]] = []
    metadata_backups: dict[str, str | None] = {}
    operations = service._build_rename_operations(plan)
    undo_manifest = {
        "schema_version": "rename_undo.v1",
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "status": "planned",
        "operations": [
            {
                "kind": str(operation["kind"]),
                "source": str(operation["source"]),
                "destination": str(operation["destination"]),
            }
            for operation in operations
        ],
    }
    def write_undo_manifest() -> Path:
        if undo_manifest_root is None:
            return service._write_rename_undo_manifest(undo_manifest)
        return service._write_rename_undo_manifest(undo_manifest, root=undo_manifest_root)

    undo_path = write_undo_manifest()
    try:
        undo_manifest["status"] = "applying"
        write_undo_manifest()
        for operation in operations:
            service._rename_path_case_safe(Path(operation["source"]), Path(operation["destination"]))
            completed_ops.append(operation)

        for row in plan:
            source = Path(row["source"])
            destination = Path(row["destination"])

            if service._resolve_same_file(source, destination) and source.name == destination.name:
                media_status = "unchanged"
            else:
                media_status = "renamed"

            sidecar_count = sum(
                1
                for operation in operations
                if operation["kind"] == "sidecar"
                and any(str(operation["source"]) == str(move.get("source")) for move in (row.get("sidecar_moves") or []))
            )

            force_pipeline_name = bool(row.get("force_pipeline_name"))
            metadata_payload = {
                "AppliedAt": datetime.now().isoformat(timespec="seconds"),
                "OriginalPath": str(source),
                "RenamedPath": str(destination),
                "PipelineGuess": str(row.get("pipeline_guess") or ""),
                "FinalName": destination.name,
                "ForcePipelineName": force_pipeline_name,
                "Mode": str(row.get("mode") or ""),
            }
            for pipeline_sidecar in service._pipeline_sidecar_paths_for_destination(destination):
                if pipeline_sidecar.exists():
                    metadata_backups.setdefault(str(pipeline_sidecar), pipeline_sidecar.read_text(encoding="utf-8"))
                    service._update_pipeline_sidecar_after_rename(pipeline_sidecar, metadata_payload, destination)
            if force_pipeline_name:
                override_sidecar = service.rename_override_sidecar_path(destination)
                metadata_backups.setdefault(
                    str(override_sidecar),
                    override_sidecar.read_text(encoding="utf-8") if override_sidecar.exists() else None,
                )
                service._update_rename_sidecar_metadata(override_sidecar, metadata_payload)

            applied.append(
                {
                    "source": str(source),
                    "destination": str(destination),
                    "status": media_status,
                    "sidecars": str(sidecar_count),
                    "sidecar_count": sidecar_count,
                    "change_kind": "unchanged" if media_status == "unchanged" else str(row.get("change_kind") or "rename"),
                    "force_pipeline_name": force_pipeline_name,
                }
            )
        undo_manifest["status"] = "completed"
        undo_manifest["completed_at"] = datetime.now().isoformat(timespec="seconds")
        write_undo_manifest()
    except Exception:
        service.logger.exception("Standalone rename failed after %s applied row(s)", len(applied))
        undo_manifest["status"] = "rollback_started"
        undo_manifest["failed_at"] = datetime.now().isoformat(timespec="seconds")
        write_undo_manifest()
        for path_text, original_text in metadata_backups.items():
            path = Path(path_text)
            try:
                if original_text is None:
                    if path.exists():
                        path.unlink()
                else:
                    atomic_write_text(path, original_text, encoding="utf-8")
            except Exception as exc:
                service.logger.warning("Rename metadata restore failed for %s: %s", path, exc)
        rollback_errors = service._rollback_rename_operations(completed_ops)
        undo_manifest["status"] = "rollback_failed" if rollback_errors else "rolled_back"
        undo_manifest["rollback_errors"] = rollback_errors
        undo_manifest["rolled_back_at"] = datetime.now().isoformat(timespec="seconds")
        write_undo_manifest()
        if rollback_errors:
            raise RuntimeError(f"Rename failed and rollback had {len(rollback_errors)} error(s). Undo manifest: {undo_path}") from None
        raise
    media_operations = sum(1 for operation in operations if operation["kind"] == "media")
    sidecar_operations = sum(1 for operation in operations if operation["kind"] == "sidecar")
    return {
        "selected": len(plan),
        "renamed": sum(1 for row in applied if row["status"] == "renamed"),
        "unchanged": sum(1 for row in applied if row["status"] == "unchanged"),
        "sidecars": sum(int(row.get("sidecar_count") or 0) for row in applied),
        "media_operations": media_operations,
        "sidecar_operations": sidecar_operations,
        "rows": applied,
        "undo_manifest": str(undo_path),
    }
