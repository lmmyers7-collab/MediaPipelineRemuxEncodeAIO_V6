"""Backend-owned CSV rerun result scanning, open, and promote helpers."""

from __future__ import annotations

import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from mediapipeline.core.kernel.dto_commands import CommandResult
from mediapipeline.core.paths.contracts import ResolvedPaths
from mediapipeline.core.processes.file_io import atomic_write_text
from mediapipeline.core.processes.rerun_preview import recent_rerun_csv_candidates


RERUN_RESULTS_SCHEMA_VERSION = "desktop_rerun_results.v1"
RERUN_PROMOTE_DRY_RUN_SCHEMA_VERSION = "desktop_rerun_promote_dry_run.v1"


def _manifest_root(resolved: ResolvedPaths) -> Path | None:
    if resolved.local_base is None:
        return None
    return resolved.local_base / "RerunManifests"


def _hash_text(text: str, length: int = 20) -> str:
    return hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest()[:length]


def _read_json(path: Path) -> dict[str, Any] | None:
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception:
        return None


def _row_key(manifest_path: Path, batch_id: str, row_index: int, row: Mapping[str, Any]) -> str:
    basis = "|".join(
        [
            str(manifest_path),
            batch_id,
            str(row_index),
            str(row.get("source_path") or ""),
            str(row.get("planned_output_path") or ""),
            str(row.get("verified_output_path") or ""),
        ]
    )
    return _hash_text(basis)


def _path_exists(path_text: Any) -> bool:
    text = str(path_text or "").strip()
    return bool(text) and Path(text).exists()


def _manifest_entries(resolved: ResolvedPaths, *, limit: int = 24) -> list[dict[str, Any]]:
    root = _manifest_root(resolved)
    if root is None or not root.exists():
        return []
    try:
        paths = sorted(root.glob("*.json"), key=lambda item: item.stat().st_mtime, reverse=True)
    except OSError:
        return []
    manifests: list[dict[str, Any]] = []
    for path in paths[:limit]:
        data = _read_json(path)
        if not isinstance(data, dict):
            continue
        rows = []
        batch_id = str(data.get("batch_id") or path.stem)
        for index, raw_row in enumerate(data.get("rows") or []):
            if not isinstance(raw_row, Mapping):
                continue
            verified_output = str(raw_row.get("verified_output_path") or raw_row.get("planned_output_path") or "")
            final_output = str(raw_row.get("final_output_path") or raw_row.get("server_out") or "")
            status = str(raw_row.get("status") or "")
            key = _row_key(path, batch_id, index, raw_row)
            rows.append(
                {
                    "row_key": key,
                    "row_index": index,
                    "status": status,
                    "source_path": str(raw_row.get("source_path") or ""),
                    "verified_output_path": verified_output,
                    "review_output_path": verified_output,
                    "final_output_path": final_output,
                    "pending_publish_manifest_path": str(raw_row.get("pending_publish_manifest_path") or ""),
                    "pending_publish_payload_path": str(raw_row.get("pending_publish_payload_path") or ""),
                    "published_path": str(raw_row.get("published_path") or ""),
                    "source_size": raw_row.get("source_size"),
                    "source_mtime_utc": str(raw_row.get("source_mtime_utc") or ""),
                    "source_identity_v2": str(raw_row.get("source_identity_v2") or ""),
                    "source_identity_v2_algorithm": str(raw_row.get("source_identity_v2_algorithm") or ""),
                    "reason": str(raw_row.get("reason") or ""),
                    "audit_issue_codes": str(raw_row.get("audit_issue_codes") or ""),
                    "media_kind": str(raw_row.get("media_kind") or ""),
                    "can_open_output": _path_exists(verified_output),
                    "can_promote_to_pending_publish": status in {"complete", "review_workspace"} and _path_exists(verified_output),
                }
            )
        manifests.append(
            {
                "manifest_key": _hash_text(str(path)),
                "manifest_path": str(path),
                "batch_id": batch_id,
                "status": str(data.get("status") or ""),
                "created_at": str(data.get("created_at") or ""),
                "completed_at": str(data.get("completed_at") or ""),
                "execution_mode": str(data.get("execution_mode") or ""),
                "destination_mode": str(data.get("destination_mode") or ""),
                "original_policy": str(data.get("original_policy") or ""),
                "output_root": str(data.get("output_root") or ""),
                "pending_publish_root": str(data.get("pending_publish_root") or ""),
                "rows": rows,
                "row_count": len(rows),
            }
        )
    return manifests


def rerun_results_payload(resolved: ResolvedPaths, *, service: Any | None = None, limit: int = 24) -> dict[str, Any]:
    manifests = _manifest_entries(resolved, limit=limit)
    csvs = recent_rerun_csv_candidates(resolved, service, limit=limit)
    for item in csvs:
        item["csv_key"] = _hash_text(str(item.get("path") or ""))
    row_count = sum(len(item.get("rows") or []) for item in manifests)
    return {
        "schema_version": RERUN_RESULTS_SCHEMA_VERSION,
        "manifest_root": str(_manifest_root(resolved) or ""),
        "manifests": manifests,
        "rows": [row for manifest in manifests for row in manifest.get("rows", [])],
        "recent_csvs": csvs,
        "counts": {
            "manifest_count": len(manifests),
            "row_count": row_count,
            "promotable_rows": sum(1 for manifest in manifests for row in manifest.get("rows", []) if row.get("can_promote_to_pending_publish")),
            "csv_candidate_count": len(csvs),
        },
        "touches_media": False,
        "writes_queue": False,
        "writes_file_overrides": False,
    }


def _find_row(resolved: ResolvedPaths, row_key: str) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    for manifest in _manifest_entries(resolved, limit=100):
        for row in manifest.get("rows") or []:
            if str(row.get("row_key") or "") == row_key:
                return manifest, row
    return None, None


def _fingerprint(row_key: str, output_path: Path, final_output_path: str) -> str:
    stat = output_path.stat()
    return _hash_text(f"{row_key}|{output_path}|{final_output_path}|{stat.st_size}|{stat.st_mtime_ns}", length=32)


def rerun_promote_dry_run(resolved: ResolvedPaths, request: Mapping[str, Any]) -> CommandResult:
    row_key = str(request.get("row_key") or "").strip()
    _manifest, row = _find_row(resolved, row_key)
    if row is None:
        return CommandResult(command="rerun.promote_dry_run", ok=False, severity="error", message="Rerun row key was not found.", errors=["rerun_row_key_not_found"])
    output = Path(str(row.get("verified_output_path") or ""))
    final_output = str(row.get("final_output_path") or "")
    if not output.is_file() or not final_output:
        return CommandResult(command="rerun.promote_dry_run", ok=False, severity="error", message="Rerun output is not promotable.", errors=["rerun_output_not_promotable"], data={"row": row})
    pending_root = resolved.pending_push_path or (resolved.state_root / "PendingServerPush" if resolved.state_root else None)
    if pending_root is None:
        return CommandResult(command="rerun.promote_dry_run", ok=False, severity="error", message="Pending Publish root is unavailable.", errors=["pending_publish_root_unavailable"])
    fingerprint = _fingerprint(row_key, output, final_output)
    return CommandResult(
        command="rerun.promote_dry_run",
        ok=True,
        severity="info",
        message="Rerun output can be promoted into Pending Publish.",
        data={
            "schema_version": RERUN_PROMOTE_DRY_RUN_SCHEMA_VERSION,
            "row_key": row_key,
            "dry_run_fingerprint": fingerprint,
            "source_output_path": str(output),
            "pending_publish_root": str(pending_root),
            "server_out": final_output,
            "would_move_output": True,
            "would_write_manifest": True,
        },
    )


def rerun_promote_to_pending_publish(resolved: ResolvedPaths, request: Mapping[str, Any]) -> CommandResult:
    if request.get("confirm_promote") is not True:
        return CommandResult(command="rerun.promote", ok=False, severity="error", message="confirm_promote=true is required.", errors=["confirm_promote_required"])
    row_key = str(request.get("row_key") or "").strip()
    dry_run = rerun_promote_dry_run(resolved, request)
    if not dry_run.ok:
        return CommandResult(command="rerun.promote", ok=False, severity=dry_run.severity, message=dry_run.message, errors=list(dry_run.errors), data=dry_run.data)
    expected = str((dry_run.data or {}).get("dry_run_fingerprint") or "")
    supplied = str(request.get("dry_run_fingerprint") or "")
    if supplied != expected:
        return CommandResult(command="rerun.promote", ok=False, severity="error", message="dry_run_fingerprint does not match current rerun output evidence.", errors=["dry_run_fingerprint_mismatch"], data=dry_run.data)
    _manifest, row = _find_row(resolved, row_key)
    if row is None:
        return CommandResult(command="rerun.promote", ok=False, severity="error", message="Rerun row key was not found.", errors=["rerun_row_key_not_found"])
    output = Path(str(row.get("verified_output_path") or ""))
    pending_root = resolved.pending_push_path or (resolved.state_root / "PendingServerPush" if resolved.state_root else None)
    if pending_root is None:
        return CommandResult(command="rerun.promote", ok=False, severity="error", message="Pending Publish root is unavailable.", errors=["pending_publish_root_unavailable"])
    pending_root.mkdir(parents=True, exist_ok=True)
    destination = pending_root / output.name
    if destination.exists():
        destination = pending_root / f"{output.stem}.rerun-{row_key}{output.suffix}"
    shutil.move(str(output), str(destination))
    source_identity = str(row.get("source_identity_v2") or row_key)
    source_size_raw = row.get("source_size")
    try:
        source_size = int(source_size_raw)
    except (TypeError, ValueError):
        source_size = 0
    manifest_path = pending_root / f"{destination.stem}.manifest.json"
    payload = {
        "schema_version": "pending_push_manifest.v1",
        "manifest_state": "parked",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "route": "csv_rerun",
        "route_reason_code": "rerun_existing_promote",
        "route_reason": "Existing CSV rerun review output promoted into Pending Publish.",
        "media_type": row.get("media_kind") or "",
        "local_file": str(destination),
        "original_local_file": row.get("source_path") or "",
        "parked_file": str(destination),
        "server_out": row.get("final_output_path") or "",
        "source_path": row.get("source_path") or "",
        "source_size": source_size,
        "source_mtime_utc": row.get("source_mtime_utc") or "",
        "source_identity": source_identity,
        "source_identity_v2": source_identity,
        "source_identity_v2_algorithm": row.get("source_identity_v2_algorithm") or "rerun_results_v1",
        "output_size": destination.stat().st_size,
        "publish_mode": "pending_publish",
        "sidecars": [],
        "subtitle_tracks": [],
        "subtitle_failures": [],
        "embedded_subtitle_tracks": [],
        "original_subtitles_preserved": True,
        "drop_ass_after_conversion": False,
        "conversion_failed": False,
    }
    atomic_write_text(manifest_path, json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    return CommandResult(
        command="rerun.promote",
        ok=True,
        severity="ok",
        message="Rerun output promoted into Pending Publish.",
        refresh_hint="pending-publish",
        data={
            "row_key": row_key,
            "pending_publish_payload_path": str(destination),
            "pending_publish_manifest_path": str(manifest_path),
            "server_out": row.get("final_output_path") or "",
        },
    )


def rerun_open_backend_known_path(resolved: ResolvedPaths, service: Any, request: Mapping[str, Any]) -> CommandResult:
    target = str(request.get("target") or "").strip()
    row_key = str(request.get("row_key") or "").strip()
    csv_key = str(request.get("csv_key") or "").strip()
    path: Path | None = None
    opener_name = "open_path"
    if target in {"review_output", "review_folder", "manifest"}:
        manifest, row = _find_row(resolved, row_key)
        if row is None:
            return CommandResult(command="rerun.open", ok=False, severity="error", message="Rerun row key was not found.", errors=["rerun_row_key_not_found"])
        if target == "manifest" and manifest is not None:
            path = Path(str(manifest.get("manifest_path") or ""))
        elif target == "review_folder":
            raw = str(row.get("verified_output_path") or "")
            path = Path(raw).parent if raw else None
        else:
            raw = str(row.get("verified_output_path") or "")
            path = Path(raw) if raw else None
            opener_name = "open_path_with_default_app"
    elif target in {"import_csv", "scoped_csv", "csv_folder"}:
        candidates = recent_rerun_csv_candidates(resolved, service, limit=100)
        selected = next((item for item in candidates if _hash_text(str(item.get("path") or "")) == csv_key), None)
        if selected is None:
            return CommandResult(command="rerun.open", ok=False, severity="error", message="Rerun CSV key was not found.", errors=["rerun_csv_key_not_found"])
        raw = str(selected.get("path") or "")
        path = Path(raw).parent if target == "csv_folder" else Path(raw)
        opener_name = "open_path_with_default_app" if target != "csv_folder" else "open_path"
    else:
        return CommandResult(command="rerun.open", ok=False, severity="error", message="Unsupported rerun open target.", errors=["unsupported_rerun_open_target"])
    if path is None or not path.exists():
        return CommandResult(command="rerun.open", ok=False, severity="error", message="Rerun open target does not exist.", errors=["rerun_open_path_missing"], data={"target": target, "path": str(path or "")})
    opener = getattr(service, opener_name, None)
    if not callable(opener):
        return CommandResult(command="rerun.open", ok=False, severity="error", message="Backend path opener is unavailable.", errors=["path_opener_unavailable"], data={"target": target, "path": str(path)})
    try:
        opener(path)
    except Exception as exc:
        return CommandResult(command="rerun.open", ok=False, severity="error", message=f"Rerun open failed: {exc}", errors=[str(exc)], data={"target": target, "path": str(path)})
    return CommandResult(command="rerun.open", ok=True, severity="info", message=f"Opened rerun {target}.", data={"target": target, "path": str(path)})
