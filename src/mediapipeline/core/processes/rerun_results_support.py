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


def _display_path_key(path_text: str) -> str:
    """Normalize display-only destination evidence without touching the filesystem.

    Snapshot rendering can include stale or unavailable UNC destinations. Resolving
    those paths asks Windows to contact the share and can stall the whole Home
    snapshot, so destination summaries intentionally compare only textual paths.
    """

    return str(PureWindowsPath(path_text)).rstrip("\\/").casefold()


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
        destination_key = _display_path_key(destination)
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

__all__ = (
    "RERUN_RESULTS_SCHEMA_VERSION",
    "RERUN_QUEUE_STATE_SCHEMA_VERSION",
    "RERUN_QUEUE_STATE_ROW_SCHEMA_VERSION",
    "RERUN_PROMOTE_DRY_RUN_SCHEMA_VERSION",
    "RERUN_PROMOTE_PIPELINE_VERSION",
    "NETWORK_RERUN_DESTINATION_POLICY_RESULT_SCHEMA_VERSION",
    "PENDING_MANIFEST_ARRAY_FIELDS",
    "PENDING_MANIFEST_BOOL_FIELDS",
    "PENDING_MANIFEST_OPTIONAL_EVIDENCE_FIELDS",
    "_manifest_root",
    "_network_manifest_root",
    "_hash_text",
    "_read_json",
    "_pipeline_sidecar_path",
    "_read_pipeline_sidecar",
    "_list_from_mapping",
    "_bool_from_mapping",
    "_first_record_path",
    "_path_under",
    "_path_key",
    "_display_path_key",
    "_non_overlapping_path",
    "_pending_server_destination_keys",
    "_resolve_promote_server_out",
    "_sidecar_server_path",
    "_copy_sidecars_to_pending",
    "_pending_manifest_evidence_from_sidecar",
    "_row_key",
    "_clean_text",
    "_status_key",
    "_first_text",
    "_string_list",
    "_row_reason",
    "_review_issue_reason",
    "_queue_status_for_row",
    "_path_exists",
    "_row_status_counts",
    "_row_queue_status_counts",
    "_destination_summary",
    "_available_actions",
)
