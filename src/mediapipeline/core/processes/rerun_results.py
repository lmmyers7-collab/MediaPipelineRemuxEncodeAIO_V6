"""Backend-owned CSV rerun result scanning, open, and promote helpers."""

from __future__ import annotations

import hashlib
import json
import shutil
from collections import Counter
from copy import deepcopy
from datetime import datetime, UTC
from pathlib import Path
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


def _manifest_root(resolved: ResolvedPaths) -> Path | None:
    if resolved.local_base is None:
        return None
    return resolved.local_base / "RerunManifests"


def _network_manifest_root(resolved: ResolvedPaths) -> Path | None:
    if resolved.state_root is not None:
        return resolved.state_root / "Rerun" / "Network"
    if resolved.local_base is not None:
        return resolved.local_base / "State" / "Rerun" / "Network"
    return None


def _hash_text(text: str, length: int = 20) -> str:
    return hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest()[:length]


def _read_json(path: Path) -> dict[str, Any] | None:
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception:
        return None


def _pipeline_sidecar_path(output_path: Path) -> Path:
    return output_path.with_name(f"{output_path.stem}.pipeline.json")


def _read_pipeline_sidecar(output_path: Path) -> dict[str, Any]:
    sidecar = _pipeline_sidecar_path(output_path)
    data = _read_json(sidecar) if sidecar.is_file() else None
    return data if isinstance(data, dict) else {}


def _list_from_mapping(data: Mapping[str, Any], key: str) -> list[Any]:
    value = data.get(key)
    return deepcopy(value) if isinstance(value, list) else []


def _bool_from_mapping(data: Mapping[str, Any], key: str) -> bool:
    return data.get(key) is True


def _first_record_path(record: Any) -> Path | None:
    if not isinstance(record, Mapping):
        return None
    for key in ("local_file", "path", "Path", "srt_path", "SrtPath", "LocalPath"):
        text = str(record.get(key) or "").strip()
        if text:
            return Path(text)
    return None


def _path_under(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except (OSError, ValueError):
        return False


def _path_key(path: Path) -> str:
    try:
        text = str(path.resolve(strict=False))
    except OSError:
        text = str(path)
    return text.rstrip("\\/").casefold()


def _non_overlapping_path(path: Path, suffix: str, occupied_keys: set[str] | None = None) -> Path:
    occupied = occupied_keys or set()
    if not path.exists() and _path_key(path) not in occupied:
        return path
    candidate = path.with_name(f"{path.stem}.{suffix}{path.suffix}")
    counter = 1
    while candidate.exists() or _path_key(candidate) in occupied:
        candidate = path.with_name(f"{path.stem}.{suffix}-{counter}{path.suffix}")
        counter += 1
    return candidate


def _pending_server_destination_keys(pending_root: Path) -> set[str]:
    keys: set[str] = set()
    if not pending_root.exists():
        return keys
    for manifest_path in pending_root.glob("*.manifest.json"):
        data = _read_json(manifest_path)
        if not isinstance(data, Mapping):
            continue
        server_out = str(data.get("server_out") or "").strip()
        if server_out:
            keys.add(_path_key(Path(server_out)))
    return keys


def _resolve_promote_server_out(final_output: Path, pending_root: Path, row_key: str) -> Path:
    occupied = _pending_server_destination_keys(pending_root)
    return _non_overlapping_path(final_output, f"rerun-{row_key}", occupied)


def _sidecar_server_path(source: Path, output: Path, final_output: Path) -> Path:
    output_dir = output.parent
    final_dir = final_output.parent
    try:
        relative = source.resolve().relative_to(output_dir.resolve())
    except (OSError, ValueError):
        relative = Path(source.name)
    source_stem = relative.stem
    output_stem = output.stem
    if output_stem and source_stem.casefold().startswith(output_stem.casefold()):
        leaf = f"{final_output.stem}{source_stem[len(output_stem):]}{relative.suffix}"
        relative = relative.with_name(leaf)
    return final_dir / relative


def _copy_sidecars_to_pending(
    *,
    pipeline_sidecar: Mapping[str, Any],
    output: Path,
    final_output: Path,
    pending_root: Path,
    transaction_id: str,
    final_output_root: Path | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[Path]]:
    entries: list[dict[str, Any]] = []
    pending_records: list[dict[str, Any]] = []
    copied: list[Path] = []
    output_dir = output.parent
    for index, record in enumerate(_list_from_mapping(pipeline_sidecar, "tx3g_srt_tracks")):
        source = _first_record_path(record)
        if source is None or source.suffix.casefold() != ".srt" or not source.is_file():
            continue
        if not _path_under(source, output_dir):
            continue
        server_out = _sidecar_server_path(source, output, final_output)
        if not _path_under(server_out, final_output.parent):
            raise ValueError(f"sidecar destination resolves outside final output folder: {server_out}")
        if final_output_root is not None and not rerun_path_resolves_under_root(server_out, final_output_root):
            raise ValueError(f"sidecar destination resolves outside configured output root: {server_out}")
        parked = _non_overlapping_path(
            pending_root / f"{transaction_id}.sidecar{index}{source.suffix}",
            "collision",
        )
        parked.parent.mkdir(parents=True, exist_ok=True)
        try:
            shutil.copy2(source, parked)
        except Exception:
            for copied_path in copied:
                copied_path.unlink(missing_ok=True)
            raise
        copied.append(parked)
        pending_record = deepcopy(record) if isinstance(record, Mapping) else {}
        pending_record["path"] = str(server_out)
        pending_record["file_name"] = server_out.name
        pending_record["status"] = "pending"
        pending_records.append(pending_record)
        entries.append(
            {
                "kind": "converted_srt",
                "local_file": str(parked),
                "original_local_file": str(source),
                "parked_file": str(parked),
                "server_out": str(server_out),
                "output_size": parked.stat().st_size,
                "preserve_existing": bool(record.get("preserved_existing") is True) if isinstance(record, Mapping) else False,
                "tx3g_record": pending_record,
            }
        )
    return entries, pending_records, copied


def _pending_manifest_evidence_from_sidecar(pipeline_sidecar: Mapping[str, Any]) -> dict[str, Any]:
    evidence: dict[str, Any] = {}
    for key in PENDING_MANIFEST_ARRAY_FIELDS:
        evidence[key] = _list_from_mapping(pipeline_sidecar, key)
    for key in PENDING_MANIFEST_BOOL_FIELDS:
        evidence[key] = _bool_from_mapping(pipeline_sidecar, key)
    for key in PENDING_MANIFEST_OPTIONAL_EVIDENCE_FIELDS:
        if key in pipeline_sidecar:
            evidence[key] = deepcopy(pipeline_sidecar[key])
    return evidence


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


def _clean_text(value: Any) -> str:
    return str(value or "").strip()


def _status_key(value: Any) -> str:
    return _clean_text(value).casefold().replace(" ", "_").replace("-", "_")


def _first_text(row: Mapping[str, Any], *keys: str) -> str:
    for key in keys:
        text = _clean_text(row.get(key))
        if text:
            return text
    return ""


def _string_list(value: Any) -> list[str]:
    if isinstance(value, Mapping):
        code = _first_text(value, "code", "issue_code", "reason_code", "type")
        reason = _first_text(value, "reason", "message", "detail", "description")
        text = ": ".join(item for item in (code, reason) if item)
        return [text] if text else [json.dumps(dict(value), sort_keys=True, default=str)]
    if isinstance(value, (list, tuple, set)):
        items: list[str] = []
        for item in value:
            items.extend(_string_list(item))
        return [item for item in items if item]
    raw = _clean_text(value)
    if not raw:
        return []
    return [item.strip() for item in raw.replace(";", ",").replace("|", ",").split(",") if item.strip()]


def _row_reason(row: Mapping[str, Any]) -> str:
    return _first_text(
        row,
        "reason",
        "status_reason",
        "blocked_reason",
        "warning_reason",
        "failure_reason",
        "error",
        "error_message",
    )


def _review_issue_reason(row: Mapping[str, Any]) -> str:
    issues = _string_list(row.get("auto_destination_issues"))
    if issues:
        return "; ".join(issues[:4])
    count = _clean_text(row.get("auto_destination_issue_count"))
    if count and count != "0":
        return f"{count} backend issue(s) require review"
    return ""


def _queue_status_for_row(row: Mapping[str, Any], *, manifest_status: str) -> dict[str, Any]:
    raw_status = _status_key(row.get("status"))
    manifest_key = _status_key(manifest_status)
    auto_decision = _status_key(row.get("auto_destination_decision"))
    reason = _row_reason(row)
    pending_manifest_path = _clean_text(row.get("pending_publish_manifest_path"))
    pending_payload_path = _clean_text(row.get("pending_publish_payload_path"))
    published_path = _clean_text(row.get("published_path"))
    replaced_hold_path = _clean_text(row.get("replaced_final_hold_path"))

    status_key = "pending"
    label = "Pending"
    severity = "ok"
    terminal = False

    if raw_status in {"skipped", "skip", "disabled"}:
        status_key, label, severity, terminal = "skipped", "Skipped", "muted", True
    elif raw_status in {"failed", "error", "errored", "destination_policy_failed"}:
        status_key, label, severity, terminal = "failed", "Failed", "error", True
    elif raw_status in {"blocked", "invalid", "missing"}:
        status_key, label, severity, terminal = "blocked", "Blocked", "error", False
    elif raw_status in {"warning", "warn", "warnings"}:
        status_key, label, severity, terminal = "warning", "Warning", "warning", False
    elif raw_status in {"stopped", "stopped_after_current"}:
        status_key, label, severity, terminal = "stopped", "Stopped", "warning", False
    elif raw_status in {"running", "active", "processing", "destination_policy_applying"}:
        status_key, label, severity, terminal = "active", "Active", "warning", False
    elif raw_status in {"pending_claim", "retryable"}:
        status_key, label, severity, terminal = "pending", "Pending", "ok", False
    elif raw_status in {"claimed"}:
        status_key, label, severity, terminal = "active", "Active", "warning", False
    elif raw_status in {"worker_completed_pending_reduction", "reduced_ready_for_destination_policy"}:
        status_key, label, severity, terminal = "pending_reduction", "Pending Reduction", "warning", False
    elif raw_status in {"worker_failed_pending_reduction"}:
        status_key, label, severity, terminal = "failed", "Failed", "error", False
    elif raw_status in {"worker_review_pending_reduction"}:
        status_key, label, severity, terminal = "awaiting_review", "Awaiting Review", "warning", False
    elif raw_status in {"pending_publish", "parked"} or pending_manifest_path or pending_payload_path or auto_decision == "pending_publish_review":
        status_key, label, severity, terminal = "pending_publish", "Pending Publish", "warning", True
    elif raw_status in {"review_workspace", "awaiting_review", "review"}:
        status_key, label, severity, terminal = "awaiting_review", "Awaiting Review", "warning", True
    elif (
        raw_status in {"published_replace_final", "published_non_overlap", "returned", "replaced"}
        or auto_decision in {"published_replace_final", "returned", "replaced"}
        or published_path
        or replaced_hold_path
    ):
        status_key, label, severity, terminal = "replaced_returned", "Replaced / Returned", "ok", True
    elif raw_status in {"complete", "completed", "done", "succeeded", "success"}:
        status_key, label, severity, terminal = "completed", "Completed", "ok", True
    elif manifest_key == "stopped_after_current" and raw_status in {"pending", "queued", "staged", ""}:
        status_key, label, severity, terminal = "stopped", "Stopped", "warning", False
    elif raw_status in {"pending", "queued", "staged", ""}:
        status_key, label, severity, terminal = "pending", "Pending", "ok", False

    blocking_reason = reason if status_key in {"blocked", "failed"} else ""
    warning_reason = reason if status_key in {"warning", "awaiting_review", "pending_publish", "stopped"} else ""
    if status_key in {"awaiting_review", "pending_publish"} and not warning_reason:
        warning_reason = _review_issue_reason(row)
    if status_key == "replaced_returned" and not reason:
        reason = "Backend returned the clean rerun output to final/library placement."

    return {
        "status_key": status_key,
        "label": label,
        "severity": severity,
        "terminal": terminal,
        "blocking_reason": blocking_reason,
        "warning_reason": warning_reason,
        "reason": reason,
    }


def _path_exists(path_text: Any) -> bool:
    text = str(path_text or "").strip()
    return bool(text) and Path(text).exists()


def _row_status_counts(rows: list[dict[str, Any]]) -> dict[str, int]:
    counts = Counter(str(row.get("status") or "unknown").strip() or "unknown" for row in rows)
    return dict(sorted(counts.items()))


def _row_queue_status_counts(rows: list[dict[str, Any]]) -> dict[str, int]:
    counts = Counter(str(row.get("queue_status") or "unknown").strip() or "unknown" for row in rows)
    return dict(sorted(counts.items()))


def _destination_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    counts: Counter[str] = Counter()
    final_destination_keys: set[str] = set()
    samples: list[dict[str, str]] = []
    sampled_keys: set[str] = set()
    for row in rows:
        status = str(row.get("queue_status") or "unknown").strip() or "unknown"
        counts[status] += 1
        if row.get("final_output_source") == "csv_completed_output":
            counts["csv_completed_output_rows"] += 1
        elif row.get("final_output_path"):
            counts["computed_destination_rows"] += 1
        destination = _clean_text(row.get("destination_path") or row.get("final_output_path") or row.get("published_path"))
        if not destination:
            continue
        try:
            destination_key = _path_key(Path(destination))
        except (OSError, ValueError):
            destination_key = destination.casefold()
        final_destination_keys.add(destination_key)
        if destination_key not in sampled_keys and len(samples) < 5:
            sampled_keys.add(destination_key)
            samples.append(
                {
                    "path": destination,
                    "source": _clean_text(row.get("final_output_source")) or "unknown",
                    "status": status,
                }
            )
    distinct_count = len(final_destination_keys)
    detail_parts = [f"{distinct_count} final target{'s' if distinct_count != 1 else ''}"]
    if counts.get("csv_completed_output_rows"):
        detail_parts.append(f"{counts['csv_completed_output_rows']} from CSV completed data")
    if counts.get("replaced_returned"):
        detail_parts.append(f"{counts['replaced_returned']} replaced")
    if counts.get("pending_publish"):
        detail_parts.append(f"{counts['pending_publish']} pending publish")
    if counts.get("awaiting_review"):
        detail_parts.append(f"{counts['awaiting_review']} review workspace")
    return {
        "schema_version": "desktop_rerun_destination_summary.v1",
        "distinct_final_destination_count": distinct_count,
        "counts": dict(sorted(counts.items())),
        "sample_destinations": samples,
        "detail": "; ".join(detail_parts) + ".",
    }


def _available_actions(row: Mapping[str, Any]) -> list[dict[str, Any]]:
    actions: list[dict[str, Any]] = []
    if row.get("can_open_output"):
        actions.append(
            {
                "action": "open_review_output",
                "label": "Open Output",
                "route": "/api/rerun/open",
                "target": "review_output",
                "requires_confirmation": False,
            }
        )
        actions.append(
            {
                "action": "open_review_folder",
                "label": "Open Folder",
                "route": "/api/rerun/open",
                "target": "review_folder",
                "requires_confirmation": False,
            }
        )
    actions.append(
        {
            "action": "open_manifest",
            "label": "Open Manifest",
            "route": "/api/rerun/open",
            "target": "manifest",
            "requires_confirmation": False,
        }
    )
    if row.get("can_promote_to_pending_publish"):
        actions.append(
            {
                "action": "promote_to_pending_publish",
                "label": "Promote to Pending Publish",
                "route": "/api/rerun/promote",
                "dry_run_route": "/api/rerun/promote-dry-run",
                "requires_confirmation": True,
            }
        )
    return actions


def rerun_manifest_queue_rows(manifest_path: Path, data: Mapping[str, Any]) -> list[dict[str, Any]]:
    batch_id = str(data.get("batch_id") or manifest_path.stem)
    manifest_status = _clean_text(data.get("status"))
    rows: list[dict[str, Any]] = []
    for index, raw_row in enumerate(data.get("rows") or []):
        if not isinstance(raw_row, Mapping):
            continue
        verified_output = _first_text(raw_row, "verified_output_path", "planned_output_path")
        final_output = _first_text(raw_row, "final_output_path", "server_out", "published_path")
        stage_path = _clean_text(raw_row.get("stage_path"))
        planned_output_path = _clean_text(raw_row.get("planned_output_path"))
        status = _clean_text(raw_row.get("status"))
        status_model = _queue_status_for_row(raw_row, manifest_status=manifest_status)
        try:
            row_index = int(raw_row.get("row_index"))
        except (TypeError, ValueError):
            row_index = index
        key = _row_key(manifest_path, batch_id, index, raw_row)
        issue_codes = _string_list(raw_row.get("audit_issue_codes"))
        auto_issues = _string_list(raw_row.get("auto_destination_issues"))
        rule_decision = rerun_rule_decision_from_mapping(raw_row)
        rule_mapping = rule_decision.to_mapping()
        can_promote = _status_key(status) in {
            "complete",
            "completed",
            "done",
            "succeeded",
            "success",
            "review_workspace",
            "awaiting_review",
            "review",
        } and _path_exists(verified_output)
        row = {
            "schema_version": RERUN_QUEUE_STATE_ROW_SCHEMA_VERSION,
            "row_key": key,
            "row_index": row_index,
            "queue_source": "csv_rerun",
            "queue_kind": "csv_rerun_row",
            "uses_pipeline_start": False,
            "status": status,
            "queue_status": status_model["status_key"],
            "queue_status_label": status_model["label"],
            "operator_status": f"CSV rerun {status_model['label']}",
            "operator_status_state": status_model["status_key"],
            "operator_severity": status_model["severity"],
            "operator_guidance": status_model["reason"] or status_model["warning_reason"] or status_model["blocking_reason"],
            "is_terminal": bool(status_model["terminal"]),
            "rule_schema_version": RERUN_RULE_DECISION_SCHEMA_VERSION,
            "rerun_rule_id": rule_decision.rule_id,
            "rerun_rule_label": rule_decision.label,
            "rerun_rule_status": rule_decision.status,
            "rerun_rule_reason": rule_decision.reason,
            "rerun_rule_destination_behavior": rule_decision.destination_behavior,
            "rerun_rule_replacement_eligible": rule_decision.replacement_eligible,
            "rerun_rule_required_confirmations": list(rule_decision.required_confirmations),
            "rerun_rule_runtime_options": dict(rule_decision.runtime_options),
            "rerun_rule_evidence": dict(rule_decision.evidence),
            "rule_decision": rule_mapping,
            "source_path": _clean_text(raw_row.get("source_path")),
            "original_source_path": _clean_text(raw_row.get("source_path")),
            "stage_path": stage_path,
            "planned_output_path": planned_output_path,
            "verified_output_path": verified_output,
            "review_output_path": verified_output,
            "output_path": _first_text(raw_row, "published_path", "pending_publish_payload_path", "verified_output_path", "planned_output_path"),
            "final_output_path": final_output,
            "final_output_source": _clean_text(raw_row.get("final_output_source")),
            "final_output_source_field": _clean_text(raw_row.get("final_output_source_field")),
            "destination_path": final_output,
            "pending_publish_manifest_path": _clean_text(raw_row.get("pending_publish_manifest_path")),
            "pending_publish_payload_path": _clean_text(raw_row.get("pending_publish_payload_path")),
            "published_path": _clean_text(raw_row.get("published_path")),
            "replaced_final_hold_path": _clean_text(raw_row.get("replaced_final_hold_path")),
            "pipeline_sidecar_path": _clean_text(raw_row.get("pipeline_sidecar_path")),
            "published_sidecar_paths": _string_list(raw_row.get("published_sidecar_paths")),
            "replaced_sidecar_hold_paths": _string_list(raw_row.get("replaced_sidecar_hold_paths")),
            "completed_manifest_path": _clean_text(raw_row.get("completed_manifest_path")),
            "completed_manifest_append": _clean_text(raw_row.get("completed_manifest_append")),
            "source_size": raw_row.get("source_size"),
            "source_mtime_utc": _clean_text(raw_row.get("source_mtime_utc")),
            "source_identity_v2": _clean_text(raw_row.get("source_identity_v2")),
            "source_identity_v2_algorithm": _clean_text(raw_row.get("source_identity_v2_algorithm")),
            "reason": status_model["reason"],
            "blocking_reason": status_model["blocking_reason"],
            "warning_reason": status_model["warning_reason"],
            "audit_issue_codes": ", ".join(issue_codes),
            "audit_issue_code_list": issue_codes,
            "media_kind": _clean_text(raw_row.get("media_kind")),
            "can_open_output": _path_exists(verified_output),
            "can_promote_to_pending_publish": can_promote,
            "manifest_key": _hash_text(str(manifest_path)),
            "manifest_path": str(manifest_path),
            "batch_id": batch_id,
            "manifest_status": manifest_status,
            "created_at": _clean_text(data.get("created_at")),
            "completed_at": _clean_text(data.get("completed_at") or raw_row.get("completed_at")),
            "stopped_at": _clean_text(data.get("stopped_at")),
            "destination_state": {
                "destination_mode": _clean_text(data.get("destination_mode")),
                "collision_policy": _clean_text(data.get("collision_policy")),
                "rerun_rule_id": rule_decision.rule_id,
                "rerun_rule_destination_behavior": rule_decision.destination_behavior,
                "rerun_rule_replacement_eligible": rule_decision.replacement_eligible,
                "auto_destination_policy": _clean_text(raw_row.get("auto_destination_policy")),
                "auto_destination_decision": _clean_text(raw_row.get("auto_destination_decision")),
                "auto_destination_issue_count": raw_row.get("auto_destination_issue_count", 0),
                "auto_destination_issues": auto_issues,
                "pending_publish_manifest_path": _clean_text(raw_row.get("pending_publish_manifest_path")),
                "pending_publish_payload_path": _clean_text(raw_row.get("pending_publish_payload_path")),
                "published_path": _clean_text(raw_row.get("published_path")),
                "replaced_final_hold_path": _clean_text(raw_row.get("replaced_final_hold_path")),
                "final_output_source": _clean_text(raw_row.get("final_output_source")),
                "final_output_source_field": _clean_text(raw_row.get("final_output_source_field")),
                "completed_manifest_path": _clean_text(raw_row.get("completed_manifest_path")),
                "completed_manifest_append": _clean_text(raw_row.get("completed_manifest_append")),
            },
            "attempt_evidence": {
                "row_index": row_index,
                "manifest_path": str(manifest_path),
                "rule_decision": rule_mapping,
                "current_chunk": data.get("current_chunk"),
                "stage_mode": _clean_text(raw_row.get("stage_mode")),
                "original_mode": _clean_text(raw_row.get("original_mode")),
                "return_mode": _clean_text(raw_row.get("return_mode")),
                "original_action": _clean_text(raw_row.get("original_action")),
                "source_overwrite_confirmed": raw_row.get("source_overwrite_confirmed") is True,
                "staged_input_cleanup": _clean_text(raw_row.get("staged_input_cleanup")),
                "pipeline_sidecar_publish": _clean_text(raw_row.get("pipeline_sidecar_publish")),
                "completed_manifest_append": _clean_text(raw_row.get("completed_manifest_append")),
            },
        }
        row["available_actions"] = _available_actions(row)
        rows.append(row)
    return rows


def _remaining_pending_count(data: Mapping[str, Any], row_counts: Mapping[str, int]) -> int:
    value = data.get("remaining_pending_count")
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = int(row_counts.get("pending", 0) or 0)
    return max(0, parsed)


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
        rows = rerun_manifest_queue_rows(path, data)
        batch_id = str(data.get("batch_id") or path.stem)
        row_counts = _row_status_counts(rows)
        queue_status_counts = _row_queue_status_counts(rows)
        destination_summary = _destination_summary(rows)
        remaining_pending_count = _remaining_pending_count(data, row_counts)
        status = str(data.get("status") or "")
        manifests.append(
            {
                "manifest_key": _hash_text(str(path)),
                "manifest_path": str(path),
                "batch_id": batch_id,
                "status": status,
                "created_at": str(data.get("created_at") or ""),
                "completed_at": str(data.get("completed_at") or ""),
                "stopped_at": str(data.get("stopped_at") or ""),
                "current_chunk": data.get("current_chunk"),
                "execution_mode": str(data.get("execution_mode") or ""),
                "destination_mode": str(data.get("destination_mode") or ""),
                "original_policy": str(data.get("original_policy") or ""),
                "collision_policy": str(data.get("collision_policy") or ""),
                "window_size": data.get("window_size"),
                "output_root": str(data.get("output_root") or ""),
                "pending_publish_root": str(data.get("pending_publish_root") or ""),
                "completed_jobs_manifest": str(data.get("completed_jobs_manifest") or ""),
                "row_status_counts": row_counts,
                "queue_status_counts": queue_status_counts,
                "destination_summary": destination_summary,
                "remaining_pending_count": remaining_pending_count,
                "can_continue_pending": status == "stopped_after_current" and remaining_pending_count > 0,
                "stop_request_id": str(data.get("stop_request_id") or ""),
                "stop_requested_at": str(data.get("stop_requested_at") or ""),
                "stop_request_marker_path": str(data.get("stop_request_marker_path") or ""),
                "safe_next_action": str(data.get("safe_next_action") or ""),
                "rows": rows,
                "row_count": len(rows),
            }
        )
    return manifests


def _network_row_key(batch_id: str, row_key: str, state_path: Path) -> str:
    raw = str(row_key or "").strip()
    if raw:
        return f"network:{batch_id}:{raw}"
    return f"network:{batch_id}:{_hash_text(str(state_path))}"


def _network_reducer_result(row: Mapping[str, Any]) -> dict[str, Any]:
    raw = row.get("reducer_result")
    return deepcopy(raw) if isinstance(raw, Mapping) else {}


def _network_worker_result(row: Mapping[str, Any]) -> dict[str, Any]:
    raw = row.get("worker_result")
    return deepcopy(raw) if isinstance(raw, Mapping) else {}


def _network_verified_output(row: Mapping[str, Any], worker_result: Mapping[str, Any], reducer_result: Mapping[str, Any]) -> str:
    text = _first_text(row, "verified_output_path", "review_output_path")
    if text:
        return text
    output = reducer_result.get("output_artifact") if isinstance(reducer_result, Mapping) else None
    if isinstance(output, Mapping):
        text = _clean_text(output.get("path"))
        if text:
            return text
    return _clean_text(worker_result.get("output_path"))


def _network_batch_queue_rows(state_path: Path, data: Mapping[str, Any]) -> list[dict[str, Any]]:
    batch_id = str(data.get("batch_id") or state_path.stem)
    manifest_status = _clean_text(data.get("status"))
    rows: list[dict[str, Any]] = []
    for index, raw_row in enumerate(data.get("rows") or []):
        if not isinstance(raw_row, Mapping):
            continue
        raw_row_key = _clean_text(raw_row.get("row_key"))
        status = _clean_text(raw_row.get("status"))
        status_model = _queue_status_for_row(raw_row, manifest_status=manifest_status)
        try:
            row_index = int(raw_row.get("row_index"))
        except (TypeError, ValueError):
            row_index = index
        reducer_result = _network_reducer_result(raw_row)
        worker_result = _network_worker_result(raw_row)
        raw_destination_result = raw_row.get("destination_policy_result")
        destination_result = deepcopy(raw_destination_result) if isinstance(raw_destination_result, Mapping) else {}
        destination_applied = raw_row.get("destination_policy_applied") is True or destination_result.get("ok") is True
        destination_terminal = destination_result.get("terminal") is True
        pending_destination_policy = (
            reducer_result.get("pending_destination_policy") is True
            and not destination_applied
            and not destination_terminal
        )
        verified_output = _network_verified_output(raw_row, worker_result, reducer_result)
        output_artifact = reducer_result.get("output_artifact") if isinstance(reducer_result, Mapping) else {}
        destination_policy = raw_row.get("destination_policy")
        pending_manifest_path = (
            _clean_text(raw_row.get("pending_publish_manifest_path"))
            or _clean_text(destination_result.get("pending_publish_manifest_path"))
        )
        pending_payload_path = (
            _clean_text(raw_row.get("pending_publish_payload_path"))
            or _clean_text(destination_result.get("pending_publish_payload_path"))
        )
        published_path = _clean_text(raw_row.get("published_path")) or _clean_text(destination_result.get("published_path"))
        row = {
            "schema_version": RERUN_QUEUE_STATE_ROW_SCHEMA_VERSION,
            "row_key": _network_row_key(batch_id, raw_row_key, state_path),
            "network_rerun_row_key": raw_row_key,
            "row_index": row_index,
            "queue_source": "network_csv_rerun",
            "queue_kind": "network_csv_rerun_row",
            "uses_pipeline_start": False,
            "status": status,
            "queue_status": status_model["status_key"],
            "queue_status_label": status_model["label"],
            "operator_status": f"Network CSV rerun {status_model['label']}",
            "operator_status_state": status_model["status_key"],
            "operator_severity": status_model["severity"],
            "operator_guidance": (
                status_model["reason"]
                or status_model["warning_reason"]
                or status_model["blocking_reason"]
                or _clean_text(reducer_result.get("reason"))
            ),
            "is_terminal": bool(status_model["terminal"]),
            "source_path": _clean_text(raw_row.get("source_path")),
            "original_source_path": _clean_text(raw_row.get("source_path")),
            "stage_path": "",
            "planned_output_path": _clean_text(raw_row.get("planned_output_path")),
            "verified_output_path": verified_output,
            "review_output_path": verified_output,
            "output_path": verified_output,
            "final_output_path": _first_text(raw_row, "final_output_path", "server_out", "published_path"),
            "destination_path": _first_text(raw_row, "final_output_path", "server_out", "published_path"),
            "pending_publish_manifest_path": pending_manifest_path,
            "pending_publish_payload_path": pending_payload_path,
            "published_path": published_path,
            "source_size": raw_row.get("source_size"),
            "source_mtime_utc": _clean_text(raw_row.get("source_mtime_utc")),
            "source_identity_v2": _clean_text(raw_row.get("source_identity_v2")),
            "source_identity_v2_algorithm": _clean_text(raw_row.get("source_identity_v2_algorithm")),
            "reason": status_model["reason"] or _clean_text(reducer_result.get("reason")),
            "blocking_reason": status_model["blocking_reason"],
            "warning_reason": status_model["warning_reason"] or _clean_text(reducer_result.get("reason")),
            "audit_issue_codes": _clean_text(raw_row.get("audit_issue_codes")),
            "audit_issue_code_list": _string_list(raw_row.get("audit_issue_codes")),
            "media_kind": _clean_text(raw_row.get("media_kind")),
            "can_open_output": _path_exists(verified_output),
            "can_promote_to_pending_publish": False,
            "manifest_key": _hash_text(str(state_path)),
            "manifest_path": str(state_path),
            "batch_id": batch_id,
            "manifest_status": manifest_status,
            "created_at": _clean_text(data.get("created_at_utc") or data.get("created_at")),
            "completed_at": _clean_text(raw_row.get("completed_at")),
            "stopped_at": _clean_text(data.get("stopped_at")),
            "claim_status": _clean_text(raw_row.get("claim_status")),
            "claimable": raw_row.get("claimable") is True,
            "active_claim": deepcopy(raw_row.get("active_claim")) if isinstance(raw_row.get("active_claim"), Mapping) else {},
            "network_reducer_result": reducer_result,
            "network_worker_result": worker_result,
            "network_output_artifact": deepcopy(output_artifact) if isinstance(output_artifact, Mapping) else {},
            "network_destination_policy": deepcopy(destination_policy) if isinstance(destination_policy, Mapping) else {},
            "network_destination_policy_result": destination_result,
            "destination_state": {
                "destination_mode": _clean_text(data.get("destination_mode")),
                "collision_policy": _clean_text(data.get("collision_policy")),
                "pending_destination_policy": pending_destination_policy,
                "destination_policy_applied": destination_applied,
                "destination_policy_terminal": destination_terminal,
                "destination_policy_status": _clean_text(destination_result.get("status")),
                "destination_policy_action": _clean_text(destination_result.get("action")),
                "destination_policy_result": destination_result,
                "pending_publish_manifest_path": pending_manifest_path,
                "pending_publish_payload_path": pending_payload_path,
                "published_path": published_path,
                "reducer_classification": _clean_text(reducer_result.get("classification")),
                "reducer_accepted": reducer_result.get("accepted") is True,
                "final_output_source": _clean_text(raw_row.get("final_output_source")),
                "final_output_source_field": _clean_text(raw_row.get("final_output_source_field")),
            },
            "attempt_evidence": {
                "row_index": row_index,
                "manifest_path": str(state_path),
                "network_batch_state": True,
                "claim_status": _clean_text(raw_row.get("claim_status")),
                "reducer_result": reducer_result,
                "worker_result": worker_result,
                "destination_policy_result": destination_result,
            },
            "available_actions": [],
        }
        rows.append(row)
    return rows


def _network_manifest_entries(resolved: ResolvedPaths, *, limit: int = 24) -> list[dict[str, Any]]:
    root = _network_manifest_root(resolved)
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
        if str(data.get("schema_version") or "") != "desktop_rerun_network_batch.v1":
            continue
        rows = _network_batch_queue_rows(path, data)
        batch_id = str(data.get("batch_id") or path.stem)
        manifests.append(
            {
                "manifest_key": _hash_text(str(path)),
                "manifest_path": str(path),
                "batch_id": batch_id,
                "status": str(data.get("status") or ""),
                "schema_version": str(data.get("schema_version") or ""),
                "phase": str(data.get("phase") or ""),
                "created_at": str(data.get("created_at_utc") or data.get("created_at") or ""),
                "updated_at": str(data.get("updated_at_utc") or ""),
                "queue_source": "network_csv_rerun",
                "uses_pipeline_start": False,
                "claim_provider_enabled": data.get("claim_provider_enabled") is True,
                "worker_execution_enabled": data.get("worker_execution_enabled") is True,
                "rows_claimable": data.get("rows_claimable") is True,
                "row_status_counts": _row_status_counts(rows),
                "queue_status_counts": _row_queue_status_counts(rows),
                "row_count": len(rows),
                "rows": rows,
            }
        )
    return manifests


def rerun_results_payload(resolved: ResolvedPaths, *, service: Any | None = None, limit: int = 24) -> dict[str, Any]:
    manifests = _manifest_entries(resolved, limit=limit)
    network_manifests = _network_manifest_entries(resolved, limit=limit)
    csvs = recent_rerun_csv_candidates(resolved, service, limit=limit)
    for item in csvs:
        item["csv_key"] = _hash_text(str(item.get("path") or ""))
    local_row_count = sum(len(item.get("rows") or []) for item in manifests)
    network_row_count = sum(len(item.get("rows") or []) for item in network_manifests)
    row_count = local_row_count + network_row_count
    rows = [row for manifest in manifests for row in manifest.get("rows", [])]
    rows.extend(row for manifest in network_manifests for row in manifest.get("rows", []))
    queue_status_counts = _row_queue_status_counts(rows)
    return {
        "schema_version": RERUN_RESULTS_SCHEMA_VERSION,
        "manifest_root": str(_manifest_root(resolved) or ""),
        "network_manifest_root": str(_network_manifest_root(resolved) or ""),
        "manifests": manifests,
        "network_manifests": network_manifests,
        "rows": rows,
        "queue_state": {
            "schema_version": RERUN_QUEUE_STATE_SCHEMA_VERSION,
            "row_schema_version": RERUN_QUEUE_STATE_ROW_SCHEMA_VERSION,
            "queue_source": "csv_rerun",
            "contains_network_csv_rerun": bool(network_manifests),
            "uses_pipeline_start": False,
            "rows": rows,
            "row_count": row_count,
            "status_counts": queue_status_counts,
            "available_statuses": [
                {"key": "pending", "label": "Pending"},
                {"key": "active", "label": "Active"},
                {"key": "blocked", "label": "Blocked"},
                {"key": "warning", "label": "Warning"},
                {"key": "failed", "label": "Failed"},
                {"key": "stopped", "label": "Stopped"},
                {"key": "pending_reduction", "label": "Pending Reduction"},
                {"key": "completed", "label": "Completed"},
                {"key": "awaiting_review", "label": "Awaiting Review"},
                {"key": "pending_publish", "label": "Pending Publish"},
                {"key": "replaced_returned", "label": "Replaced / Returned"},
                {"key": "skipped", "label": "Skipped"},
            ],
        },
        "recent_csvs": csvs,
        "counts": {
            "manifest_count": len(manifests),
            "network_manifest_count": len(network_manifests),
            "row_count": row_count,
            "local_row_count": local_row_count,
            "network_row_count": network_row_count,
            "promotable_rows": sum(1 for manifest in manifests for row in manifest.get("rows", []) if row.get("can_promote_to_pending_publish")),
            "csv_candidate_count": len(csvs),
            "queue_status_counts": queue_status_counts,
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


def _network_output_hash_evidence(path: Path) -> dict[str, Any]:
    evidence: dict[str, Any] = {"path": str(path), "exists": path.exists()}
    if not path.exists():
        return evidence
    try:
        evidence["size_bytes"] = path.stat().st_size
        evidence["sha256"] = sha256_file(path)
    except OSError as exc:
        evidence["error"] = str(exc)
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
    source_size_raw = row.get("source_size")
    try:
        source_size = int(source_size_raw)
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
        "output_size": output.stat().st_size,
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
        if output.exists() and not manifest_path.exists():
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
    if not output.is_file():
        result["errors"].append("verified_handoff_output_missing")
        result["message"] = "Verified handoff output is missing before destination policy."
        result["completed_at_utc"] = datetime.now(UTC).isoformat()
        return result
    final_output_text = _first_text(row, "final_output_path", "server_out", "published_path")
    if action != "review_workspace" and not final_output_text:
        result["errors"].append("final_output_path_missing")
        result["message"] = "Network row is missing final output path evidence."
        result["completed_at_utc"] = datetime.now(UTC).isoformat()
        return result
    final_output = Path(final_output_text) if final_output_text else output
    result["output_before"] = _network_output_hash_evidence(output)
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
