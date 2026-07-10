from __future__ import annotations

import json
import tempfile
import uuid
from pathlib import Path
from typing import Any
from collections.abc import Callable

from mediapipeline.core.paths.layout import ensure_path_boundary_safe_for_mutation
from mediapipeline.core.rename.constants import RENAME_TOOL_SIDECAR_SCHEMA_VERSION
from mediapipeline.core.rename.file_io import atomic_write_text

SameFileFunc = Callable[[Path, Path], bool]
PathKeyFunc = Callable[[Path], str]
RenamePathFunc = Callable[..., None]
PipelineSidecarPathFunc = Callable[[Path], Path]


def _operation_boundary_root(row: dict[str, Any], source: Path) -> Path:
    root = str(row.get("mutation_root") or "").strip()
    return Path(root) if root else source.parent


def rename_path_case_safe(
    source: Path,
    destination: Path,
    *,
    same_file: SameFileFunc,
    boundary_root: Path | None = None,
) -> None:
    root = Path(boundary_root) if boundary_root is not None else source.parent
    ensure_path_boundary_safe_for_mutation(source, root)
    ensure_path_boundary_safe_for_mutation(destination, root, allow_missing_leaf=True)
    ensure_path_boundary_safe_for_mutation(
        destination.parent,
        root,
        allow_missing_leaf=True,
        allow_root_target=True,
    )
    destination.parent.mkdir(parents=True, exist_ok=True)
    if same_file(source, destination) and source.name == destination.name:
        return
    if destination.exists() and not same_file(source, destination):
        raise FileExistsError(f"Destination already exists: {destination}")
    if source.name.casefold() == destination.name.casefold() and source.name != destination.name:
        temp = source.with_name(f".mediapipeline-rename-{uuid.uuid4().hex}{source.suffix}")
        source.rename(temp)
        try:
            temp.rename(destination)
        except Exception:
            if temp.exists() and not source.exists():
                temp.rename(source)
            raise
    else:
        source.rename(destination)


def read_json_dict_for_rename(path: Path) -> dict[str, Any]:
    existing: dict[str, Any] = {}
    if path.exists():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                existing = data
        except Exception:
            existing = {"PreviousSidecarDecodeError": True}
    return existing


def update_rename_sidecar_metadata(
    path: Path,
    payload: dict[str, Any],
    *,
    schema_default: str | None = RENAME_TOOL_SIDECAR_SCHEMA_VERSION,
) -> None:
    existing = read_json_dict_for_rename(path)
    if schema_default:
        existing.setdefault("SchemaVersion", schema_default)
    existing["RenameTool"] = payload
    atomic_write_text(path, json.dumps(existing, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def update_pipeline_sidecar_after_rename(path: Path, payload: dict[str, Any], destination: Path) -> None:
    existing = read_json_dict_for_rename(path)
    existing["output_path"] = str(destination)
    existing["output_file"] = destination.name
    history = existing.get("rename_history")
    if not isinstance(history, list):
        history = []
    history.append(
        {
            "applied_at": payload["AppliedAt"],
            "original_path": payload["OriginalPath"],
            "renamed_path": payload["RenamedPath"],
            "final_name": payload["FinalName"],
            "force_pipeline_name": payload["ForcePipelineName"],
        }
    )
    existing["rename_history"] = history[-25:]
    existing["RenameTool"] = payload
    atomic_write_text(path, json.dumps(existing, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def pipeline_sidecar_paths_for_destination(
    destination: Path,
    *,
    pipeline_sidecar_path: PipelineSidecarPathFunc,
    casefold_path: PathKeyFunc,
) -> list[Path]:
    candidates = [
        destination.with_suffix(".mediapipeline.json"),
        pipeline_sidecar_path(destination),
        Path(str(destination) + ".pipeline.json"),
    ]
    seen: set[str] = set()
    result: list[Path] = []
    for path in candidates:
        key = casefold_path(path)
        if key in seen:
            continue
        seen.add(key)
        result.append(path)
    return result


def write_rename_undo_manifest(manifest: dict[str, Any], *, root: Path | None = None) -> Path:
    manifest_root = root or (Path(tempfile.gettempdir()) / "MediaPipelineRemuxEncodeAIO" / "RenameUndo")
    manifest_root.mkdir(parents=True, exist_ok=True)
    path_text = str(manifest.get("path") or "")
    path = Path(path_text) if path_text else manifest_root / f"rename-undo-{uuid.uuid4().hex}.json"
    if root is not None:
        ensure_path_boundary_safe_for_mutation(path, manifest_root, allow_missing_leaf=True)
    manifest["path"] = str(path)
    atomic_write_text(path, json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def build_rename_operations(
    plan: list[dict[str, Any]],
    *,
    same_file: SameFileFunc,
    casefold_path: PathKeyFunc,
) -> list[dict[str, Path | str]]:
    operations: list[dict[str, Path | str]] = []
    destination_keys: set[str] = set()
    for row in plan:
        source = Path(row["source"])
        destination = Path(row["destination"])
        boundary_root = _operation_boundary_root(row, source)
        if not source.exists():
            raise FileNotFoundError(f"Source disappeared before rename: {source}")
        ensure_path_boundary_safe_for_mutation(source, boundary_root)
        ensure_path_boundary_safe_for_mutation(destination, boundary_root, allow_missing_leaf=True)
        if not same_file(source, destination) or source.name != destination.name:
            key = casefold_path(destination)
            if key in destination_keys:
                raise RuntimeError(f"Two rename operations target the same path: {destination}")
            destination_keys.add(key)
            if destination.exists() and not same_file(source, destination):
                raise FileExistsError(f"Destination already exists: {destination}")
            operations.append({"kind": "media", "source": source, "destination": destination, "boundary_root": boundary_root})
        if row.get("rename_sidecars"):
            for move in row.get("sidecar_moves") or []:
                sidecar_source = Path(str(move["source"]))
                sidecar_destination = Path(str(move["destination"]))
                if not sidecar_source.exists():
                    continue
                ensure_path_boundary_safe_for_mutation(sidecar_source, boundary_root)
                ensure_path_boundary_safe_for_mutation(sidecar_destination, boundary_root, allow_missing_leaf=True)
                key = casefold_path(sidecar_destination)
                if key in destination_keys:
                    raise RuntimeError(f"Two rename operations target the same sidecar path: {sidecar_destination}")
                destination_keys.add(key)
                if sidecar_destination.exists() and not same_file(sidecar_source, sidecar_destination):
                    raise FileExistsError(f"Sidecar destination already exists: {sidecar_destination}")
                operations.append({"kind": "sidecar", "source": sidecar_source, "destination": sidecar_destination, "boundary_root": boundary_root})
    return operations


def rollback_rename_operations(
    completed_ops: list[dict[str, Path | str]],
    *,
    rename_path: RenamePathFunc,
    same_file: SameFileFunc,
) -> list[str]:
    rollback_errors: list[str] = []
    for operation in reversed(completed_ops):
        source = Path(operation["source"])
        destination = Path(operation["destination"])
        boundary_root = Path(operation["boundary_root"]) if operation.get("boundary_root") else None
        try:
            if destination.exists() and not source.exists():
                rename_path(destination, source, boundary_root=boundary_root)
            elif destination.exists() and source.exists() and same_file(source, destination):
                continue
            else:
                rollback_errors.append(f"cannot roll back {destination}; destination is missing or source already exists")
        except Exception as exc:
            rollback_errors.append(f"{destination} -> {source}: {exc}")
    return rollback_errors
