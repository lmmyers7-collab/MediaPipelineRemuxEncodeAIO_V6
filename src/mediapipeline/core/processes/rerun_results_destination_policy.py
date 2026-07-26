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
from mediapipeline.core.processes.source_probe import (
    run_source_probe,
    source_content_hash_timeout_seconds,
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
from mediapipeline.core.processes.rerun_results_queue_projection import *  # noqa: F403

def _find_row(resolved: ResolvedPaths, row_key: str) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    for manifest in _manifest_entries(resolved, limit=100):
        for row in manifest.get("rows") or []:
            if str(row.get("row_key") or "") == row_key:
                return manifest, row
    return None, None


def _fingerprint(row_key: str, output_path: Path, final_output_path: str) -> str:
    stat = output_path.stat()
    sidecar = _pipeline_sidecar_path(output_path)
    sidecar_fingerprint = ""
    if sidecar.is_file():
        sidecar_stat = sidecar.stat()
        sidecar_fingerprint = f"|{sidecar}|{sidecar_stat.st_size}|{sidecar_stat.st_mtime_ns}"
    return _hash_text(f"{row_key}|{output_path}|{final_output_path}|{stat.st_size}|{stat.st_mtime_ns}{sidecar_fingerprint}", length=32)


def _source_overwrite_confirmed(row: Mapping[str, Any]) -> bool:
    if row.get("source_overwrite_confirmed") is True:
        return True
    attempt = row.get("attempt_evidence")
    return isinstance(attempt, Mapping) and attempt.get("source_overwrite_confirmed") is True


def _destination_error_code(message: str) -> str:
    if "unavailable" in message:
        return "rerun_final_output_root_unavailable"
    return "rerun_final_output_outside_configured_root"


def _promote_destination_violation(
    resolved: ResolvedPaths,
    row: Mapping[str, Any],
    *,
    final_output: str,
    server_out: Path | None = None,
) -> str:
    source_path = str(row.get("source_path") or "")
    violation = rerun_final_output_root_violation(
        resolved,
        row,
        source_path=source_path,
        final_output_path=final_output,
        final_output_field=str(row.get("final_output_source_field") or "final_output_path"),
        confirm_source_overwrite=_source_overwrite_confirmed(row),
    )
    if violation:
        return violation
    if server_out is None:
        return ""
    if _source_overwrite_confirmed(row) and source_path and rerun_paths_resolve_same(server_out, source_path):
        return ""
    root = rerun_effective_output_root_for_source(resolved, source_path)
    if root is None:
        return "configured output root is unavailable for Pending Publish server_out validation"
    if not rerun_path_resolves_under_root(server_out, root):
        return f"Pending Publish server_out resolves outside configured output root: {server_out}"
    return ""


def _batch_bool(batch: Mapping[str, Any], key: str) -> bool:
    if batch.get(key) is True:
        return True
    request = batch.get("request_summary")
    if isinstance(request, Mapping) and request.get(key) is True:
        return True
    lifecycle = batch.get("lifecycle")
    return isinstance(lifecycle, Mapping) and lifecycle.get(key) is True


def _network_destination_behavior(batch: Mapping[str, Any], row: Mapping[str, Any]) -> str:
    destination_mode = _clean_text(batch.get("destination_mode") or "auto_replace_clean_else_pending_review")
    policy = row.get("destination_policy")
    policy_behavior = ""
    if isinstance(policy, Mapping):
        policy_behavior = _clean_text(policy.get("destination_behavior"))
    behavior = _clean_text(row.get("rerun_rule_destination_behavior") or policy_behavior)
    if destination_mode and destination_mode != "auto_replace_clean_else_pending_review":
        return destination_mode
    if behavior == "blocked_manual_review":
        return "review_workspace"
    if behavior in {"review_workspace", "pending_publish", "publish_non_overlap", "publish_replace_final"}:
        return behavior
    replacement_eligible = row.get("rerun_rule_replacement_eligible") is True
    if isinstance(policy, Mapping):
        replacement_eligible = replacement_eligible or policy.get("replacement_eligible") is True
    return "publish_replace_final" if replacement_eligible else "pending_publish"


def _network_destination_result_base(
    *,
    batch: Mapping[str, Any],
    row: Mapping[str, Any],
    action: str,
    status: str,
) -> dict[str, Any]:
    return {
        "schema_version": NETWORK_RERUN_DESTINATION_POLICY_RESULT_SCHEMA_VERSION,
        "phase": "phase_6_destination_policy_integration",
        "batch_id": _clean_text(batch.get("batch_id")),
        "row_key": _clean_text(row.get("row_key")),
        "action": action,
        "status": status,
        "ok": False,
        "terminal": False,
        "started_at_utc": datetime.now(UTC).isoformat(),
        "source_path": _clean_text(row.get("source_path")),
        "verified_output_path": _clean_text(row.get("verified_output_path")),
        "final_output_path": _first_text(row, "final_output_path", "server_out", "published_path"),
        "errors": [],
        "warnings": [],
        "touches_source": False,
    }


def _network_terminal_destination_result(row: Mapping[str, Any]) -> dict[str, Any] | None:
    existing = row.get("destination_policy_result")
    if not isinstance(existing, Mapping) or existing.get("terminal") is not True:
        return None
    result = dict(existing)
    result["duplicate_apply"] = True
    result["duplicate_apply_at_utc"] = datetime.now(UTC).isoformat()
    return result


def _network_output_stat_evidence(path: Path) -> dict[str, Any]:
    evidence: dict[str, Any] = {
        "path": str(path),
        "exists": False,
        "probe_status": "missing",
        "stale": False,
    }
    try:
        stat_evidence = run_source_probe("stat", path, timeout_seconds=2.0)
    except FileNotFoundError:
        return evidence
    except (TimeoutError, PermissionError, OSError) as exc:
        evidence.update(
            {
                "probe_status": "access_failed",
                "stale": True,
                "error": str(exc),
            }
        )
        return evidence
    if stat_evidence.get("kind") != "file":
        evidence["probe_status"] = "not_file"
        return evidence
    size_bytes = max(0, int(stat_evidence.get("size") or 0))
    evidence.update({"exists": True, "size_bytes": size_bytes, "probe_status": "ok"})
    return evidence


def _network_output_hash_evidence(path: Path) -> dict[str, Any]:
    evidence = _network_output_stat_evidence(path)
    if evidence.get("probe_status") != "ok":
        return evidence
    size_bytes = max(0, int(evidence.get("size_bytes") or 0))
    try:
        hash_evidence = run_source_probe(
            "sha256",
            path,
            timeout_seconds=source_content_hash_timeout_seconds(size_bytes),
        )
        evidence["sha256"] = str(hash_evidence.get("digest") or "")
    except (TimeoutError, PermissionError, OSError) as exc:
        evidence.update(
            {
                "probe_status": "access_failed",
                "stale": True,
                "error": str(exc),
            }
        )
    return evidence


def _network_destination_root(resolved: ResolvedPaths, row: Mapping[str, Any]) -> Path | None:
    return rerun_effective_output_root_for_source(resolved, _clean_text(row.get("source_path")))


def _network_sidecar_targets(
    *,
    output: Path,
    final_output: Path,
    destination_root: Path,
) -> tuple[list[PromotionFileTarget], list[str]]:
    targets: list[PromotionFileTarget] = []
    errors: list[str] = []
    for sidecar in companion_sidecars(output):
        if not sidecar.is_file():
            continue
        server_out = _sidecar_server_path(sidecar, output, final_output)
        if not rerun_path_resolves_under_root(server_out, destination_root):
            errors.append(f"sidecar destination resolves outside configured output root: {server_out}")
            continue
        try:
            relative = server_out.resolve(strict=False).relative_to(destination_root.resolve(strict=False))
        except (OSError, ValueError):
            relative = Path(server_out.name)
        targets.append(PromotionFileTarget(source_path=sidecar, destination_path=server_out, relative_path=relative))
    return targets, errors


def _apply_network_review_workspace(
    result: dict[str, Any],
    *,
    output: Path,
) -> dict[str, Any]:
    result.update(
        {
            "ok": True,
            "terminal": True,
            "status": "review_workspace",
            "review_output_path": str(output),
            "message": "Network CSV rerun output left in the coordinator-owned handoff review workspace.",
            "completed_at_utc": datetime.now(UTC).isoformat(),
        }
    )
    return result


def _apply_network_pending_publish(
    result: dict[str, Any],
    *,
    resolved: ResolvedPaths,
    batch: Mapping[str, Any],
    row: Mapping[str, Any],
    output: Path,
    final_output: Path,
    product_version: str,
    pipeline_version: str,
) -> dict[str, Any]:
    pending_root = resolved.pending_push_path or (resolved.state_root / "PendingServerPush" if resolved.state_root else None)
    if pending_root is None:
        result["errors"].append("pending_publish_root_unavailable")
        result["message"] = "Pending Publish root is unavailable."
        result["completed_at_utc"] = datetime.now(UTC).isoformat()
        return result
    pending_root.mkdir(parents=True, exist_ok=True)
    row_key = _clean_text(row.get("row_key")) or _hash_text(str(output))
    server_out = _resolve_promote_server_out(final_output, pending_root, row_key)
    source_overwrite_row = dict(row)
    source_overwrite_row["source_overwrite_confirmed"] = _batch_bool(batch, "confirm_source_overwrite")
    violation = _promote_destination_violation(resolved, source_overwrite_row, final_output=str(final_output), server_out=server_out)
    if violation:
        result["errors"].append(_destination_error_code(violation))
        result["message"] = violation
        result["server_out"] = str(server_out)
        result["completed_at_utc"] = datetime.now(UTC).isoformat()
        return result

    destination = _non_overlapping_path(pending_root / output.name, f"network-rerun-{row_key}")
    manifest_path = pending_root / f"{destination.name}.manifest.json"
    now = datetime.now(UTC).isoformat()
    transaction_id = f"network-rerun-promote-{row_key}"
    pipeline_sidecar = _read_pipeline_sidecar(output)
    sidecar_entries: list[dict[str, Any]] = []
    pending_tx3g_records: list[dict[str, Any]] = []
    copied_sidecars: list[Path] = []
    final_output_root = _network_destination_root(resolved, row)
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
            result["errors"].append("pending_sidecar_copy_failed")
            result["message"] = f"Pending Publish sidecar copy failed before moving network rerun output: {exc}"
            result["completed_at_utc"] = datetime.now(UTC).isoformat()
            return result

    output_before = _network_output_hash_evidence(output)
    if output_before.get("probe_status") != "ok":
        result["errors"].append("verified_handoff_output_access_failed")
        result["message"] = "Network rerun handoff output could not be revalidated before Pending Publish mutation."
        result["completed_at_utc"] = datetime.now(UTC).isoformat()
        return result
    source_size_raw = row.get("source_size")
    try:
        source_size = int(str(source_size_raw or "0"))
    except (TypeError, ValueError):
        source_size = 0
    source_identity = _clean_text(row.get("source_identity_v2")) or row_key
    payload = {
        "schema_version": "pending_push_manifest.v1",
        "parked_at": now,
        "product_version": _clean_text(product_version),
        "pipeline_version": _clean_text(pipeline_version) or RERUN_PROMOTE_PIPELINE_VERSION,
        "publish_transaction_id": transaction_id,
        "manifest_state": "pending_move",
        "created_at": now,
        "route": "network_csv_rerun",
        "route_reason_code": "network_rerun_destination_policy",
        "route_reason": "Network CSV rerun handoff output promoted into Pending Publish by coordinator policy.",
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
        "source_identity_v2_algorithm": row.get("source_identity_v2_algorithm") or "network_rerun_destination_v1",
        "output_size": int(output_before.get("size_bytes") or 0),
        "output_sha256": output_before.get("sha256") or "",
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
        result["errors"].append("pending_manifest_contract_invalid")
        result["message"] = f"Pending Publish manifest contract validation failed before moving network rerun output: {exc}"
        result["pending_publish_manifest_path"] = str(manifest_path)
        result["completed_at_utc"] = datetime.now(UTC).isoformat()
        return result
    try:
        atomic_write_text(manifest_path, json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
        shutil.move(str(output), str(destination))
        payload["manifest_state"] = "parked"
        payload["parked_at"] = datetime.now(UTC).isoformat()
        PendingPushManifest.from_mapping(payload)
        atomic_write_text(manifest_path, json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    except Exception as exc:
        if _network_output_stat_evidence(output).get("exists") is True and not manifest_path.exists():
            for copied in copied_sidecars:
                copied.unlink(missing_ok=True)
        result["errors"].append("network_rerun_pending_publish_failed")
        result["message"] = f"Network rerun output promotion into Pending Publish failed: {exc}"
        result["pending_publish_manifest_path"] = str(manifest_path)
        result["pending_publish_payload_path"] = str(destination)
        result["completed_at_utc"] = datetime.now(UTC).isoformat()
        return result

    result.update(
        {
            "ok": True,
            "terminal": True,
            "status": "pending_publish",
            "message": "Network rerun output promoted into Pending Publish.",
            "pending_publish_payload_path": str(destination),
            "pending_publish_manifest_path": str(manifest_path),
            "server_out": str(server_out),
            "requested_server_out": str(final_output),
            "output_before": output_before,
            "output_after": _network_output_hash_evidence(destination),
            "sidecar_files": sidecar_entries,
            "completed_at_utc": datetime.now(UTC).isoformat(),
        }
    )
    return result


def _apply_network_final_publish(
    result: dict[str, Any],
    *,
    resolved: ResolvedPaths,
    batch: Mapping[str, Any],
    row: Mapping[str, Any],
    output: Path,
    final_output: Path,
    replace_final: bool,
) -> dict[str, Any]:
    destination_root = _network_destination_root(resolved, row)
    if destination_root is None:
        result["errors"].append("rerun_final_output_root_unavailable")
        result["message"] = "Configured output root is unavailable for final placement."
        result["completed_at_utc"] = datetime.now(UTC).isoformat()
        return result
    if replace_final and not _batch_bool(batch, "confirm_replace_final"):
        result["errors"].append("confirm_replace_final_required")
        result["message"] = "publish_replace_final requires confirm_replace_final=true from the network rerun start proof."
        result["completed_at_utc"] = datetime.now(UTC).isoformat()
        return result
    row_for_policy = dict(row)
    row_for_policy["source_overwrite_confirmed"] = _batch_bool(batch, "confirm_source_overwrite")
    target = final_output if replace_final else _non_overlapping_path(final_output, f"network-rerun-{_clean_text(row.get('row_key')) or 'row'}")
    violation = _promote_destination_violation(resolved, row_for_policy, final_output=str(final_output), server_out=target)
    if violation:
        result["errors"].append(_destination_error_code(violation))
        result["message"] = violation
        result["published_path"] = str(target)
        result["completed_at_utc"] = datetime.now(UTC).isoformat()
        return result

    try:
        relative = target.resolve(strict=False).relative_to(destination_root.resolve(strict=False))
    except (OSError, ValueError):
        relative = Path(target.name)
    targets: list[PromotionFileTarget] = [
        PromotionFileTarget(source_path=output, destination_path=target, relative_path=relative)
    ]
    sidecar_targets, sidecar_errors = _network_sidecar_targets(
        output=output,
        final_output=target,
        destination_root=destination_root,
    )
    if sidecar_errors:
        result["errors"].extend(sidecar_errors)
        result["message"] = "; ".join(sidecar_errors)
        result["completed_at_utc"] = datetime.now(UTC).isoformat()
        return result
    targets.extend(sidecar_targets)
    transaction = copy_files_transactionally(
        targets,
        destination_root=destination_root,
        verification_mode="cautious",
        overwrite_existing=replace_final,
    )
    result["transaction"] = transaction
    if not transaction.get("ok"):
        result["errors"].append("network_rerun_final_publish_failed")
        result["message"] = "Network rerun final placement failed."
        result["completed_at_utc"] = datetime.now(UTC).isoformat()
        return result
    result.update(
        {
            "ok": True,
            "terminal": True,
            "status": "published_replace_final" if replace_final else "published_non_overlap",
            "message": "Network rerun output copied into final placement with verification.",
            "published_path": str(target),
            "requested_final_output_path": str(final_output),
            "server_out_collision_policy": "none" if target == final_output else "suffix",
            "sidecar_target_count": len(sidecar_targets),
            "completed_at_utc": datetime.now(UTC).isoformat(),
        }
    )
    if transaction.get("overwritten_files"):
        result["overwritten_files"] = list(transaction.get("overwritten_files") or [])
    return result


def apply_network_rerun_destination_policy(
    resolved: ResolvedPaths,
    batch: Mapping[str, Any],
    row: Mapping[str, Any],
    *,
    product_version: str = "",
    pipeline_version: str = RERUN_PROMOTE_PIPELINE_VERSION,
) -> dict[str, Any]:
    """Apply coordinator-owned destination policy for one reduced Network CSV rerun row."""

    existing = _network_terminal_destination_result(row)
    if existing is not None:
        return existing
    action = _network_destination_behavior(batch, row)
    result = _network_destination_result_base(batch=batch, row=row, action=action, status="applying")
    reducer = row.get("reducer_result")
    if not isinstance(reducer, Mapping) or reducer.get("accepted") is not True:
        result["errors"].append("network_reducer_result_not_accepted")
        result["message"] = "Network row has no accepted Phase 5 reducer result."
        result["completed_at_utc"] = datetime.now(UTC).isoformat()
        return result
    output = Path(_clean_text(row.get("verified_output_path")))
    output_before = _network_output_hash_evidence(output)
    if output_before.get("exists") is not True or output_before.get("probe_status") != "ok":
        result["errors"].append("verified_handoff_output_missing")
        if output_before.get("probe_status") == "access_failed":
            result["errors"].append("verified_handoff_output_access_failed")
            result["message"] = "Verified handoff output could not be probed within the bounded deadline."
        else:
            result["message"] = "Verified handoff output is missing before destination policy."
        result["output_before"] = output_before
        result["completed_at_utc"] = datetime.now(UTC).isoformat()
        return result
    final_output_text = _first_text(row, "final_output_path", "server_out", "published_path")
    if action != "review_workspace" and not final_output_text:
        result["errors"].append("final_output_path_missing")
        result["message"] = "Network row is missing final output path evidence."
        result["completed_at_utc"] = datetime.now(UTC).isoformat()
        return result
    final_output = Path(final_output_text) if final_output_text else output
    result["output_before"] = output_before
    result["final_output_path"] = str(final_output)
    if action == "review_workspace":
        return _apply_network_review_workspace(result, output=output)
    if action == "pending_publish":
        return _apply_network_pending_publish(
            result,
            resolved=resolved,
            batch=batch,
            row=row,
            output=output,
            final_output=final_output,
            product_version=product_version,
            pipeline_version=pipeline_version,
        )
    if action == "publish_non_overlap":
        return _apply_network_final_publish(
            result,
            resolved=resolved,
            batch=batch,
            row=row,
            output=output,
            final_output=final_output,
            replace_final=False,
        )
    if action == "publish_replace_final":
        return _apply_network_final_publish(
            result,
            resolved=resolved,
            batch=batch,
            row=row,
            output=output,
            final_output=final_output,
            replace_final=True,
        )
    result["errors"].append("unsupported_destination_policy")
    result["message"] = f"Unsupported Network CSV rerun destination policy: {action}"
    result["completed_at_utc"] = datetime.now(UTC).isoformat()
    return result

__all__ = (
    "_find_row",
    "_fingerprint",
    "_source_overwrite_confirmed",
    "_destination_error_code",
    "_promote_destination_violation",
    "_batch_bool",
    "_network_destination_behavior",
    "_network_destination_result_base",
    "_network_terminal_destination_result",
    "_network_output_stat_evidence",
    "_network_output_hash_evidence",
    "_network_destination_root",
    "_network_sidecar_targets",
    "_apply_network_review_workspace",
    "_apply_network_pending_publish",
    "_apply_network_final_publish",
    "apply_network_rerun_destination_policy",
)
