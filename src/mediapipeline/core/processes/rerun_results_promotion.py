"""Backend-owned CSV rerun result scanning, open, and promote helpers."""

from __future__ import annotations

import hashlib
import json
import shutil
from collections import Counter
from copy import deepcopy
from datetime import datetime, UTC
from pathlib import Path, PureWindowsPath
from typing import Any
from collections.abc import Mapping

from mediapipeline.core.final_library.promotion_parts.planning import PromotionFileTarget
from mediapipeline.core.final_library.promotion_parts.transfer import (
    companion_sidecars,
    copy_files_transactionally,
    sha256_file,
)
from mediapipeline.core.kernel.contracts.pending_publish import PendingPushManifest
from mediapipeline.core.kernel.dto_commands import CommandResult
from mediapipeline.core.paths.contracts import ResolvedPaths
from mediapipeline.core.processes.file_io import atomic_write_text
from mediapipeline.core.processes.rerun_preview import recent_rerun_csv_candidates
from mediapipeline.core.processes.rerun_policy import (
    rerun_effective_output_root_for_source,
    rerun_final_output_root_violation,
    rerun_path_resolves_under_root,
    rerun_paths_resolve_same,
)
from mediapipeline.core.processes.rerun_rules import (
    RERUN_RULE_DECISION_SCHEMA_VERSION,
    rerun_rule_decision_from_mapping,
)


RERUN_RESULTS_SCHEMA_VERSION = "desktop_rerun_results.v1"
RERUN_QUEUE_STATE_SCHEMA_VERSION = "desktop_rerun_queue_state.v1"
RERUN_QUEUE_STATE_ROW_SCHEMA_VERSION = "desktop_rerun_queue_state_row.v1"
RERUN_PROMOTE_DRY_RUN_SCHEMA_VERSION = "desktop_rerun_promote_dry_run.v1"
RERUN_PROMOTE_PIPELINE_VERSION = "1.0"
NETWORK_RERUN_DESTINATION_POLICY_RESULT_SCHEMA_VERSION = "desktop_rerun_network_destination_policy_result.v1"
PENDING_MANIFEST_ARRAY_FIELDS = (
    "tx3g_srt_tracks",
    "tx3g_srt_failures",
    "bdpgs_srt_failures",
    "vobsub_srt_failures",
    "converted_srt_sidecar_candidates",
    "subtitle_output_reduction",
    "tx3g_embedded_srt_tracks",
    "bdpgs_embedded_srt_tracks",
    "vobsub_embedded_srt_tracks",
)
PENDING_MANIFEST_BOOL_FIELDS = (
    "tx3g_srt_conversion_enabled",
    "tx3g_external_srt_sidecars_enabled",
    "drop_tx3g_after_conversion",
    "bdpgs_srt_conversion_enabled",
    "drop_bdpgs_after_conversion",
    "vobsub_srt_conversion_enabled",
    "drop_vobsub_after_conversion",
)
PENDING_MANIFEST_OPTIONAL_EVIDENCE_FIELDS = (
    "folder_policy",
    "route_plan",
    "route_explanation",
    "library_profile",
    "dynamic_hdr",
    "quality_verification",
    "audio_decisions",
    "subtitle_decisions",
    "encode_selected_attempt",
    "encode_selected_encoder",
    "encode_selected_encoder_kind",
    "encode_selected_gpu_device",
)



from mediapipeline.core.processes.rerun_results_support import *  # noqa: F403

from mediapipeline.core.processes.rerun_results_destination_policy import *  # noqa: F403

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
    server_out = _resolve_promote_server_out(Path(final_output), pending_root, row_key)
    destination_violation = _promote_destination_violation(resolved, row, final_output=final_output, server_out=server_out)
    if destination_violation:
        return CommandResult(
            command="rerun.promote_dry_run",
            ok=False,
            severity="error",
            message=destination_violation,
            errors=[_destination_error_code(destination_violation)],
            data={"row_key": row_key, "requested_server_out": final_output, "server_out": str(server_out)},
        )
    fingerprint = _fingerprint(row_key, output, str(server_out))
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
            "server_out": str(server_out),
            "requested_server_out": final_output,
            "server_out_collision_policy": "suffix" if str(server_out) != final_output else "none",
            "would_move_output": True,
            "would_write_manifest": True,
        },
    )


def rerun_promote_to_pending_publish(
    resolved: ResolvedPaths,
    request: Mapping[str, Any],
    *,
    product_version: str = "",
    pipeline_version: str = RERUN_PROMOTE_PIPELINE_VERSION,
) -> CommandResult:
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
    server_out = _resolve_promote_server_out(Path(str(row.get("final_output_path") or "")), pending_root, row_key)
    final_output_root = rerun_effective_output_root_for_source(resolved, row.get("source_path") or "")
    destination = pending_root / output.name
    if destination.exists():
        destination = pending_root / f"{output.stem}.rerun-{row_key}{output.suffix}"
    destination = _non_overlapping_path(destination, f"rerun-{row_key}")
    source_identity = str(row.get("source_identity_v2") or row_key)
    source_size_raw = row.get("source_size")
    try:
        source_size = int(source_size_raw)
    except (TypeError, ValueError):
        source_size = 0
    manifest_path = pending_root / f"{destination.name}.manifest.json"
    now = datetime.now(UTC).isoformat()
    transaction_id = f"rerun-promote-{row_key}"
    pipeline_sidecar = _read_pipeline_sidecar(output)
    sidecar_entries: list[dict[str, Any]] = []
    pending_tx3g_records: list[dict[str, Any]] = []
    copied_sidecars: list[Path] = []
    if pipeline_sidecar:
        try:
            sidecar_entries, pending_tx3g_records, copied_sidecars = _copy_sidecars_to_pending(
                pipeline_sidecar=pipeline_sidecar,
                output=output,
                final_output=server_out,
                pending_root=pending_root,
                transaction_id=transaction_id,
                final_output_root=final_output_root,
            )
        except Exception as exc:
            return CommandResult(
                command="rerun.promote",
                ok=False,
                severity="error",
                message=f"Pending Publish sidecar copy failed before moving rerun output: {exc}",
                errors=["pending_sidecar_copy_failed"],
                data={"row_key": row_key},
            )
    payload = {
        "schema_version": "pending_push_manifest.v1",
        "parked_at": now,
        "product_version": str(product_version or "").strip(),
        "pipeline_version": str(pipeline_version or RERUN_PROMOTE_PIPELINE_VERSION).strip() or RERUN_PROMOTE_PIPELINE_VERSION,
        "publish_transaction_id": transaction_id,
        "manifest_state": "pending_move",
        "created_at": now,
        "route": "csv_rerun",
        "route_reason_code": "rerun_existing_promote",
        "route_reason": "Existing CSV rerun review output promoted into Pending Publish.",
        "media_type": row.get("media_kind") or "",
        "local_file": str(destination),
        "original_local_file": str(output),
        "parked_file": str(destination),
        "server_out": str(server_out),
        "source_path": row.get("source_path") or "",
        "source_size": source_size,
        "source_mtime_utc": row.get("source_mtime_utc") or "",
        "source_identity": source_identity,
        "source_identity_v2": source_identity,
        "source_identity_v2_algorithm": row.get("source_identity_v2_algorithm") or "rerun_results_v1",
        "output_size": output.stat().st_size,
        "output_sha256": sha256_file(output),
        "output_hash_algorithm": "SHA256",
        "publish_mode": "pending_publish",
        "sidecar_files": sidecar_entries,
        "tx3g_srt_tracks": [],
        "tx3g_srt_failures": [],
        "bdpgs_srt_failures": [],
        "vobsub_srt_failures": [],
        "converted_srt_sidecar_candidates": [],
        "subtitle_output_reduction": [],
        "tx3g_embedded_srt_tracks": [],
        "bdpgs_embedded_srt_tracks": [],
        "vobsub_embedded_srt_tracks": [],
        "tx3g_srt_conversion_enabled": False,
        "tx3g_external_srt_sidecars_enabled": False,
        "drop_tx3g_after_conversion": False,
        "bdpgs_srt_conversion_enabled": False,
        "drop_bdpgs_after_conversion": False,
        "vobsub_srt_conversion_enabled": False,
        "drop_vobsub_after_conversion": False,
        "original_subtitles_preserved": True,
        "drop_ass_after_conversion": False,
        "conversion_failed": False,
    }
    if pipeline_sidecar:
        payload.update(_pending_manifest_evidence_from_sidecar(pipeline_sidecar))
        payload["sidecar_files"] = sidecar_entries
        if pending_tx3g_records:
            payload["tx3g_srt_tracks"] = pending_tx3g_records
    try:
        PendingPushManifest.from_mapping(payload)
    except Exception as exc:
        for copied in copied_sidecars:
            copied.unlink(missing_ok=True)
        return CommandResult(
            command="rerun.promote",
            ok=False,
            severity="error",
            message=f"Pending Publish manifest contract validation failed before moving rerun output: {exc}",
            errors=["pending_manifest_contract_invalid"],
            data={"row_key": row_key, "pending_publish_manifest_path": str(manifest_path)},
        )
    try:
        atomic_write_text(manifest_path, json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
        shutil.move(str(output), str(destination))
        payload["manifest_state"] = "parked"
        payload["parked_at"] = datetime.now(UTC).isoformat()
        PendingPushManifest.from_mapping(payload)
        atomic_write_text(manifest_path, json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    except Exception as exc:
        if output.exists() and not manifest_path.exists():
            for copied in copied_sidecars:
                copied.unlink(missing_ok=True)
        return CommandResult(
            command="rerun.promote",
            ok=False,
            severity="error",
            message=f"Rerun output promotion into Pending Publish failed: {exc}",
            errors=["rerun_promote_pending_publish_failed"],
            data={"row_key": row_key, "pending_publish_manifest_path": str(manifest_path), "pending_publish_payload_path": str(destination)},
        )
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
            "server_out": str(server_out),
            "requested_server_out": str(row.get("final_output_path") or ""),
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

__all__ = (
    "_destination_error_code",
    "_promote_destination_violation",
    "rerun_promote_dry_run",
    "rerun_promote_to_pending_publish",
    "rerun_open_backend_known_path",
)
