"""Coordinator-owned claim state for Network CSV rerun rows."""
from __future__ import annotations

import copy
import json
import os
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from collections.abc import Callable, Mapping

from mediapipeline.core.network.url_policy import redact_network_secret_text
from mediapipeline.core.processes.rerun_results import (
    NETWORK_RERUN_DESTINATION_POLICY_RESULT_SCHEMA_VERSION,
    apply_network_rerun_destination_policy,
)

from .protocol import ClaimResponse
from .registry import normalize_source_identity

NETWORK_RERUN_BATCH_SCHEMA_VERSION = "desktop_rerun_network_batch.v1"
NETWORK_RERUN_ROW_JOB_KIND = "csv_rerun_row"
NETWORK_RERUN_REDUCER_SCHEMA_VERSION = "desktop_rerun_network_result_reduction.v1"
NETWORK_RERUN_ACTIVE_STATUSES = {"active", "running", "stopping", "stopped_after_current", "paused"}


@dataclass(frozen=True)
class NetworkRerunClaimLease:
    response: ClaimResponse
    state_path: Path
    previous_payload: dict[str, Any]
    worker_id: str


def network_rerun_state_root_for_app(app: Any) -> Path | None:
    resolved = getattr(app, "resolved", None)
    if resolved is None:
        return None
    state_root = getattr(resolved, "state_root", None)
    if state_root is None and getattr(resolved, "local_base", None) is not None:
        state_root = Path(getattr(resolved, "local_base")) / "State"
    if state_root is None:
        return None
    return Path(state_root) / "Rerun" / "Network"


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _safe_int(value: Any) -> int:
    try:
        return max(0, int(value))
    except Exception:
        return 0


def _read_state(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(payload, dict):
        raise RuntimeError(f"Network CSV rerun state root must be a JSON object: {path}")
    if str(payload.get("schema_version") or "") != NETWORK_RERUN_BATCH_SCHEMA_VERSION:
        raise RuntimeError(f"Network CSV rerun state schema mismatch: {path}")
    return payload


def _write_state(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    try:
        temp.write_text(
            json.dumps(dict(payload), ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False) + "\n",
            encoding="utf-8",
            newline="",
        )
        os.replace(temp, path)
    finally:
        try:
            temp.unlink(missing_ok=True)
        except OSError:
            pass


def _row_source_path(row: Mapping[str, Any]) -> str:
    return str(row.get("source_path") or "").strip()


def _row_library_id(row: Mapping[str, Any]) -> str:
    mapping = row.get("source_mapping")
    if isinstance(mapping, Mapping):
        mapped = str(mapping.get("library_id") or "").strip()
        if mapped:
            return mapped
    return str(row.get("library_id") or "").strip()


def _row_relative_path(row: Mapping[str, Any]) -> str:
    mapping = row.get("source_mapping")
    if isinstance(mapping, Mapping):
        mapped = str(mapping.get("relative_path") or "").strip()
        if mapped:
            return mapped
    return ""


def _accessible_library_allowed(row: Mapping[str, Any], accessible_library_ids: list[str] | None) -> bool:
    if accessible_library_ids is None:
        return True
    library_id = _row_library_id(row)
    if not library_id:
        return True
    allowed = {str(item).casefold() for item in accessible_library_ids if str(item).strip()}
    return library_id.casefold() in allowed


def _row_output_handoff(row: Mapping[str, Any]) -> dict[str, Any]:
    raw = row.get("output_handoff")
    return dict(raw) if isinstance(raw, Mapping) else {}


def _row_claimable(row: Mapping[str, Any], *, allow_local_handoff: bool) -> bool:
    if row.get("claimable") is not True:
        return False
    if str(row.get("status") or "").strip() not in {"pending_claim", "retryable"}:
        return False
    if not _row_source_path(row):
        return False
    if not str(row.get("planned_output_path") or "").strip():
        return False
    handoff = _row_output_handoff(row)
    if handoff.get("ready") is not True:
        return False
    if not allow_local_handoff and handoff.get("remote_worker_compatible") is not True:
        return False
    return True


def _claimable_batch(payload: Mapping[str, Any]) -> bool:
    if payload.get("claim_provider_enabled") is not True:
        return False
    if payload.get("worker_execution_enabled") is not True:
        return False
    if payload.get("rows_claimable") is not True:
        return False
    return str(payload.get("status") or "").strip() in NETWORK_RERUN_ACTIVE_STATUSES


def _source_identity(row: Mapping[str, Any], source_path: str) -> dict[str, Any]:
    mapping = row.get("source_mapping")
    if isinstance(mapping, Mapping):
        method = str(mapping.get("method") or "")
    else:
        method = ""
    return {
        "schema_version": "desktop_rerun_network_source_identity.v1",
        "method": method or "coordinator_source_path",
        "source_path": source_path,
        "source_identity": normalize_source_identity(source_path),
        "library_id": _row_library_id(row),
        "relative_path": _row_relative_path(row),
    }


def _claim_metadata(
    *,
    payload: Mapping[str, Any],
    row: Mapping[str, Any],
    state_path: Path,
    source_path: str,
    worker_id: str,
    worker_name: str,
) -> dict[str, Any]:
    return {
        "job_kind": NETWORK_RERUN_ROW_JOB_KIND,
        "rerun_batch_id": str(payload.get("batch_id") or ""),
        "rerun_row_key": str(row.get("row_key") or ""),
        "rerun_row_index": _safe_int(row.get("row_index")),
        "planned_output_path": str(row.get("planned_output_path") or ""),
        "output_handoff": _row_output_handoff(row),
        "source_identity": _source_identity(row, source_path),
        "coordinator_source_path": source_path,
        "worker_source_path": "",
        "handoff_probe": {},
        "destination_policy_applied": False,
        "batch_state_path": str(state_path),
        "worker_id": worker_id,
        "worker_name": worker_name,
    }


def _row_record(row: Mapping[str, Any], source_path: str) -> SimpleNamespace:
    return SimpleNamespace(
        source_path=source_path,
        library_id=_row_library_id(row),
        relative_path=_row_relative_path(row),
        priority=False,
    )


def _update_counts(payload: dict[str, Any]) -> None:
    rows = [row for row in payload.get("rows") or [] if isinstance(row, dict)]
    payload["row_count"] = len(rows)
    payload["claimable_row_count"] = sum(1 for row in rows if row.get("claimable") is True)
    payload["claimed_row_count"] = sum(1 for row in rows if str(row.get("status") or "") == "claimed")
    payload["completed_pending_reduction_row_count"] = sum(
        1 for row in rows if str(row.get("status") or "") == "worker_completed_pending_reduction"
    )
    payload["failed_pending_reduction_row_count"] = sum(
        1 for row in rows if str(row.get("status") or "") == "worker_failed_pending_reduction"
    )
    payload["review_pending_reduction_row_count"] = sum(
        1 for row in rows if str(row.get("status") or "") == "worker_review_pending_reduction"
    )


def claim_next_network_rerun_row(
    *,
    app: Any,
    registry: Any,
    worker_id: str,
    worker_name: str,
    accessible_library_ids: list[str] | None,
    encode_config_for_row: Callable[[Any], dict[str, Any]],
    allow_local_handoff: bool,
    job_id: str | None = None,
) -> NetworkRerunClaimLease | None:
    root = network_rerun_state_root_for_app(app)
    if root is None or not root.exists():
        return None
    paths = sorted(root.glob("*.json"))
    for path in paths:
        payload = _read_state(path)
        if not _claimable_batch(payload):
            continue
        rows = payload.get("rows")
        if not isinstance(rows, list):
            continue
        for row in sorted((item for item in rows if isinstance(item, dict)), key=lambda item: _safe_int(item.get("row_index"))):
            if not _row_claimable(row, allow_local_handoff=allow_local_handoff):
                continue
            if not _accessible_library_allowed(row, accessible_library_ids):
                continue
            source_path = _row_source_path(row)
            if registry.is_in_flight(source_path):
                continue
            claim_id = str(job_id or uuid.uuid4())
            metadata = _claim_metadata(
                payload=payload,
                row=row,
                state_path=path,
                source_path=source_path,
                worker_id=worker_id,
                worker_name=worker_name,
            )
            metadata["job_id"] = claim_id
            record = _row_record(row, source_path)
            encode_config = dict(encode_config_for_row(record) or {})
            encode_config["__job_kind"] = NETWORK_RERUN_ROW_JOB_KIND
            encode_config["__claim_metadata"] = metadata
            ok = registry.claim(
                job_id=claim_id,
                worker_id=worker_id,
                worker_name=worker_name,
                source_path=source_path,
                encode_config=encode_config,
                priority=False,
                estimated_size_gb=0.0,
                accessible_library_ids=accessible_library_ids,
                job_kind=NETWORK_RERUN_ROW_JOB_KIND,
                claim_metadata=metadata,
            )
            if not ok:
                continue
            previous_payload = copy.deepcopy(payload)
            now = _now()
            row["status"] = "claimed"
            row["claim_status"] = "claimed"
            row["claimable"] = False
            row["active_claim"] = {
                "job_id": claim_id,
                "worker_id": worker_id,
                "worker_name": worker_name,
                "claimed_at_utc": now,
                "source_path": source_path,
                "source_identity": metadata["source_identity"],
            }
            payload["status"] = "active"
            payload["updated_at_utc"] = now
            _update_counts(payload)
            try:
                _write_state(path, payload)
            except Exception:
                registry.rollback_claim(claim_id, worker_id)
                raise
            response = ClaimResponse(
                status="ok",
                job_id=claim_id,
                source_path=source_path,
                library_id=metadata["source_identity"]["library_id"],
                relative_path=metadata["source_identity"]["relative_path"],
                priority=False,
                estimated_size_gb=0.0,
                encode_config=encode_config,
                retry_on_failure=True,
                job_kind=NETWORK_RERUN_ROW_JOB_KIND,
                rerun_batch_id=metadata["rerun_batch_id"],
                rerun_row_key=metadata["rerun_row_key"],
                rerun_row_index=metadata["rerun_row_index"],
                planned_output_path=metadata["planned_output_path"],
                output_handoff=metadata["output_handoff"],
                source_identity=metadata["source_identity"],
                coordinator_source_path=source_path,
                destination_policy_applied=False,
            )
            return NetworkRerunClaimLease(
                response=response,
                state_path=path,
                previous_payload=previous_payload,
                worker_id=worker_id,
            )
    return None


def rollback_network_rerun_claim(
    lease: NetworkRerunClaimLease,
    registry: Any,
    *,
    reason: str,
) -> None:
    try:
        registry.rollback_claim(lease.response.job_id, lease.worker_id)
    finally:
        payload = copy.deepcopy(lease.previous_payload)
        payload["updated_at_utc"] = _now()
        payload["last_claim_rollback"] = {
            "job_id": lease.response.job_id,
            "worker_id": lease.worker_id,
            "reason": redact_network_secret_text(reason),
            "rolled_back_at_utc": payload["updated_at_utc"],
        }
        _update_counts(payload)
        _write_state(lease.state_path, payload)


def _metadata_state_path(metadata: Mapping[str, Any], app: Any) -> Path | None:
    raw = str(metadata.get("batch_state_path") or "").strip()
    if raw:
        return Path(raw)
    batch_id = str(metadata.get("rerun_batch_id") or "").strip()
    root = network_rerun_state_root_for_app(app)
    if root is None or not batch_id:
        return None
    return root / f"{batch_id}.json"


def _request_text(request: Any, key: str) -> str:
    return str(getattr(request, key, "") or "").strip()


def _request_bool(request: Any, key: str, *, default: bool = False) -> bool:
    value = getattr(request, key, default)
    if isinstance(value, bool):
        return value
    return bool(value)


def _request_int(request: Any, key: str, *, default: int = 0) -> int:
    try:
        return max(0, int(getattr(request, key, default) or 0))
    except Exception:
        return default


def _request_mapping(request: Any, key: str) -> dict[str, Any]:
    value = getattr(request, key, None)
    return dict(value) if isinstance(value, Mapping) else {}


def _path_key_for_boundary(path: Path) -> str:
    try:
        text = str(path.resolve(strict=False))
    except OSError:
        text = str(path)
    return os.path.normcase(text.rstrip("\\/"))


def _path_under_or_equal(path_text: str, root_text: str) -> bool:
    path_raw = str(path_text or "").strip()
    root_raw = str(root_text or "").strip()
    if not path_raw or not root_raw:
        return False
    path_key = _path_key_for_boundary(Path(path_raw))
    root_key = _path_key_for_boundary(Path(root_raw))
    if path_key == root_key:
        return True
    return path_key.startswith(root_key + os.sep) or path_key.startswith(root_key + "/") or path_key.startswith(root_key + "\\")


def _artifact_text(payload: Mapping[str, Any], key: str) -> str:
    return str(payload.get(key) or "").strip()


def _read_worker_result_artifact(path_text: str) -> tuple[dict[str, Any], dict[str, Any] | None]:
    path_raw = str(path_text or "").strip()
    evidence: dict[str, Any] = {
        "path": path_raw,
        "supplied": bool(path_raw),
        "status": "not_supplied",
        "valid": None,
        "schema_version": "",
        "fields": {},
        "error": "",
    }
    if not path_raw:
        return evidence, None
    path = Path(path_raw)
    if not path.is_file():
        evidence.update({"status": "missing", "valid": False, "error": "worker result artifact path is missing"})
        return evidence, None
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception as exc:
        evidence.update({"status": "unreadable", "valid": False, "error": redact_network_secret_text(exc)})
        return evidence, None
    if not isinstance(payload, dict):
        evidence.update({"status": "invalid_root", "valid": False, "error": "worker result artifact root is not an object"})
        return evidence, None
    schema = _artifact_text(payload, "SchemaVersion")
    evidence["schema_version"] = schema
    evidence["fields"] = {
        "job_kind": _artifact_text(payload, "JobKind"),
        "rerun_batch_id": _artifact_text(payload, "RerunBatchId"),
        "rerun_row_key": _artifact_text(payload, "RerunRowKey"),
        "worker_claim_id": _artifact_text(payload, "WorkerClaimId"),
        "worker_run_id": _artifact_text(payload, "WorkerRunId"),
        "success": payload.get("Success") if isinstance(payload.get("Success"), bool) else None,
        "status": _artifact_text(payload, "Status"),
        "output_path": _artifact_text(payload, "OutputPath"),
        "output_size_bytes": _safe_int(payload.get("OutputSizeBytes")),
        "publish_state": _artifact_text(payload, "PublishState"),
        "publish_mode": _artifact_text(payload, "PublishMode"),
        "route": _artifact_text(payload, "Route"),
    }
    if schema != "local_worker_result.v1":
        evidence.update({"status": "invalid_schema", "valid": False, "error": "worker result artifact schema is not local_worker_result.v1"})
        return evidence, payload
    evidence.update({"status": "ok", "valid": True})
    return evidence, payload


def _source_identity_evidence(
    *,
    row: Mapping[str, Any],
    metadata: Mapping[str, Any],
    request: Any,
) -> tuple[dict[str, Any], list[str]]:
    expected_source_path = _row_source_path(row) or str(metadata.get("coordinator_source_path") or "")
    expected_identity = normalize_source_identity(expected_source_path)
    metadata_identity_raw = metadata.get("source_identity")
    metadata_identity = dict(metadata_identity_raw) if isinstance(metadata_identity_raw, Mapping) else {}
    expected_identity = str(metadata_identity.get("source_identity") or expected_identity)
    request_identity = _request_mapping(request, "source_identity")
    request_identity_value = str(request_identity.get("source_identity") or "").strip()
    request_coordinator_path = _request_text(request, "coordinator_source_path")
    worker_source_path = _request_text(request, "worker_source_path") or str(metadata.get("worker_source_path") or "")
    mismatches: list[str] = []
    if request_identity_value and expected_identity and request_identity_value != expected_identity:
        mismatches.append("source_identity_mismatch")
    if request_coordinator_path and expected_source_path:
        if normalize_source_identity(request_coordinator_path) != normalize_source_identity(expected_source_path):
            mismatches.append("coordinator_source_path_mismatch")
    return (
        {
            "schema_version": "desktop_rerun_network_reducer_source_identity.v1",
            "expected_source_path": expected_source_path,
            "expected_source_identity": expected_identity,
            "request_source_identity": request_identity_value,
            "request_coordinator_source_path": request_coordinator_path,
            "worker_source_path": worker_source_path,
            "library_id": _row_library_id(row),
            "relative_path": _row_relative_path(row),
            "matches": not mismatches,
            "mismatches": list(mismatches),
        },
        mismatches,
    )


def _output_evidence(request: Any, planned_output_path: str) -> dict[str, Any]:
    output_path = _request_text(request, "output_path")
    path = Path(output_path) if output_path else None
    exists = bool(path is not None and path.is_file())
    size_bytes = _request_int(request, "output_size_bytes", default=0)
    if exists and path is not None:
        try:
            size_bytes = max(size_bytes, path.stat().st_size)
        except OSError:
            pass
    under_handoff = _path_under_or_equal(output_path, planned_output_path)
    return {
        "schema_version": "desktop_rerun_network_reducer_output.v1",
        "path": output_path,
        "planned_output_path": planned_output_path,
        "exists": exists,
        "is_file": exists,
        "size_bytes": size_bytes,
        "under_planned_handoff": under_handoff,
    }


def _artifact_mismatches(
    artifact: Mapping[str, Any],
    *,
    request: Any,
    batch_id: str,
    row_key: str,
    job_id: str,
) -> list[str]:
    if artifact.get("valid") is not True:
        return ["worker_result_artifact_invalid"] if artifact.get("supplied") else []
    fields = artifact.get("fields")
    if not isinstance(fields, Mapping):
        return ["worker_result_artifact_invalid"]
    mismatches: list[str] = []
    artifact_job_kind = str(fields.get("job_kind") or "")
    if artifact_job_kind and artifact_job_kind != NETWORK_RERUN_ROW_JOB_KIND:
        mismatches.append("artifact_job_kind_mismatch")
    artifact_batch_id = str(fields.get("rerun_batch_id") or "")
    if artifact_batch_id and artifact_batch_id != batch_id:
        mismatches.append("artifact_batch_id_mismatch")
    artifact_row_key = str(fields.get("rerun_row_key") or "")
    if artifact_row_key and artifact_row_key != row_key:
        mismatches.append("artifact_row_key_mismatch")
    artifact_claim_id = str(fields.get("worker_claim_id") or "")
    if artifact_claim_id and job_id and artifact_claim_id != job_id:
        mismatches.append("artifact_claim_id_mismatch")
    artifact_success = fields.get("success")
    if isinstance(artifact_success, bool) and artifact_success != _request_bool(request, "success"):
        mismatches.append("artifact_success_mismatch")
    return mismatches


def _worker_result_snapshot(
    *,
    metadata: Mapping[str, Any],
    request: Any,
    now: str,
    artifact: Mapping[str, Any],
) -> dict[str, Any]:
    return {
        "schema_version": "desktop_rerun_network_worker_result_snapshot.v1",
        "job_id": _request_text(request, "job_id") or str(metadata.get("job_id") or ""),
        "worker_id": _request_text(request, "worker_id"),
        "success": _request_bool(request, "success"),
        "reported_at_utc": now,
        "output_path": _request_text(request, "output_path"),
        "output_size_bytes": _request_int(request, "output_size_bytes", default=0),
        "completion_status": _request_text(request, "completion_status"),
        "publish_state": _request_text(request, "publish_state"),
        "publish_mode": _request_text(request, "publish_mode"),
        "route": _request_text(request, "route"),
        "queue_terminal": _request_bool(request, "queue_terminal"),
        "retry_on_failure": _request_bool(request, "retry_on_failure", default=True),
        "reason_code": _request_text(request, "reason_code"),
        "reason": redact_network_secret_text(_request_text(request, "reason") or _request_text(request, "error_message")),
        "planned_output_path": str(metadata.get("planned_output_path") or _request_text(request, "planned_output_path")),
        "coordinator_source_path": str(metadata.get("coordinator_source_path") or _request_text(request, "coordinator_source_path")),
        "worker_source_path": str(metadata.get("worker_source_path") or _request_text(request, "worker_source_path")),
        "source_identity": dict(metadata.get("source_identity") or _request_mapping(request, "source_identity")),
        "handoff_probe": dict(metadata.get("handoff_probe") or _request_mapping(request, "handoff_probe")),
        "destination_policy_applied": _request_bool(request, "destination_policy_applied"),
        "pending_reduction": True,
        "worker_result_artifact_path": str(artifact.get("path") or ""),
        "worker_result_artifact_status": str(artifact.get("status") or ""),
    }


def _append_bounded(row: dict[str, Any], key: str, entry: Mapping[str, Any], *, limit: int = 20) -> None:
    existing = row.get(key)
    entries = [item for item in existing if isinstance(item, Mapping)] if isinstance(existing, list) else []
    entries.append(dict(entry))
    row[key] = entries[-limit:]


def _duplicate_reducer_result(row: dict[str, Any], *, request: Any, now: str) -> bool:
    existing = row.get("reducer_result")
    if not isinstance(existing, Mapping):
        return False
    job_id = _request_text(request, "job_id")
    if not job_id or str(existing.get("job_id") or "") != job_id:
        return False
    row["duplicate_done_count"] = _safe_int(row.get("duplicate_done_count")) + 1
    row["last_duplicate_done_at_utc"] = now
    _append_bounded(
        row,
        "reducer_events",
        {
            "schema_version": NETWORK_RERUN_REDUCER_SCHEMA_VERSION,
            "event": "duplicate_done_ignored",
            "job_id": job_id,
            "worker_id": _request_text(request, "worker_id"),
            "recorded_at_utc": now,
        },
    )
    return True


def _build_reducer_result(
    *,
    payload: Mapping[str, Any],
    row: Mapping[str, Any],
    metadata: Mapping[str, Any],
    request: Any,
    now: str,
    late: bool = False,
) -> dict[str, Any]:
    batch_id = str(payload.get("batch_id") or metadata.get("rerun_batch_id") or _request_text(request, "rerun_batch_id"))
    row_key = str(row.get("row_key") or metadata.get("rerun_row_key") or _request_text(request, "rerun_row_key"))
    job_id = _request_text(request, "job_id") or str(metadata.get("job_id") or "")
    planned_output_path = str(metadata.get("planned_output_path") or row.get("planned_output_path") or _request_text(request, "planned_output_path"))
    artifact, _artifact_payload = _read_worker_result_artifact(_request_text(request, "worker_result_artifact_path"))
    output = _output_evidence(request, planned_output_path)
    identity, identity_mismatches = _source_identity_evidence(row=row, metadata=metadata, request=request)
    mismatches: list[str] = list(identity_mismatches)
    req_batch = _request_text(request, "rerun_batch_id")
    req_row = _request_text(request, "rerun_row_key")
    if req_batch and req_batch != batch_id:
        mismatches.append("request_batch_id_mismatch")
    if req_row and req_row != row_key:
        mismatches.append("request_row_key_mismatch")
    active_claim = row.get("active_claim")
    if isinstance(active_claim, Mapping) and not late:
        if job_id and str(active_claim.get("job_id") or "") != job_id:
            mismatches.append("active_claim_job_id_mismatch")
        request_worker_id = _request_text(request, "worker_id")
        if request_worker_id and str(active_claim.get("worker_id") or "") != request_worker_id:
            mismatches.append("active_claim_worker_id_mismatch")
    mismatches.extend(_artifact_mismatches(artifact, request=request, batch_id=batch_id, row_key=row_key, job_id=job_id))

    success = _request_bool(request, "success")
    retry_on_failure = _request_bool(request, "retry_on_failure", default=True)
    queue_terminal = _request_bool(request, "queue_terminal")
    destination_policy_applied = _request_bool(request, "destination_policy_applied")
    publish_state = _request_text(request, "publish_state")
    reason = redact_network_secret_text(_request_text(request, "reason") or _request_text(request, "error_message"))
    classification = "success"
    accepted = False
    retryable = False
    terminal = False
    pending_destination_policy = False

    if late:
        classification = "late_done_report"
        reason = reason or "Done report arrived after the active claim was no longer current."
    elif mismatches:
        classification = "corrupt_result"
        retryable = True
        reason = reason or "; ".join(mismatches)
    elif success:
        if destination_policy_applied:
            classification = "review"
            reason = "Worker reported destination policy was applied before coordinator reduction."
        elif "pending" in publish_state.casefold():
            classification = "review"
            reason = "Worker reported worker-owned pending publish state before coordinator reduction."
        elif not output["exists"]:
            classification = "output_missing"
            retryable = True
            reason = reason or "Worker reported success but the handoff output is missing."
        elif not output["under_planned_handoff"]:
            classification = "review"
            reason = "Worker output path is outside the planned row handoff folder."
        else:
            accepted = True
            pending_destination_policy = True
            reason = reason or "Worker handoff output is ready for coordinator destination policy."
    else:
        terminal = bool(queue_terminal or not retry_on_failure)
        retryable = not terminal
        classification = "failed_terminal" if terminal else "failed_retryable"
        reason = reason or "Worker reported failure before coordinator destination policy."

    return {
        "schema_version": NETWORK_RERUN_REDUCER_SCHEMA_VERSION,
        "reducer_phase": "phase_5_coordinator_result_reducer",
        "reduced_at_utc": now,
        "job_id": job_id,
        "worker_id": _request_text(request, "worker_id"),
        "batch_id": batch_id,
        "row_key": row_key,
        "classification": classification,
        "accepted": accepted,
        "retryable": retryable,
        "terminal": terminal,
        "pending_destination_policy": pending_destination_policy,
        "destination_policy_applied": destination_policy_applied,
        "reason_code": _request_text(request, "reason_code"),
        "reason": reason,
        "mismatches": mismatches,
        "source_identity": identity,
        "output_artifact": output,
        "worker_result_artifact": artifact,
    }


def _apply_reducer_result(row: dict[str, Any], result: Mapping[str, Any]) -> None:
    classification = str(result.get("classification") or "")
    row["reducer_result"] = dict(result)
    row["claim_status"] = "done_reported"
    row["claimable"] = False
    row.pop("active_claim", None)
    if result.get("accepted") is True:
        row["status"] = "worker_completed_pending_reduction"
        output = result.get("output_artifact")
        if isinstance(output, Mapping):
            row["verified_output_path"] = str(output.get("path") or "")
    elif classification == "review":
        row["status"] = "worker_review_pending_reduction"
    else:
        row["status"] = "worker_failed_pending_reduction"


def _destination_policy_enabled(payload: Mapping[str, Any]) -> bool:
    return payload.get("destination_policy_application_enabled") is True


def _destination_policy_applying_result(payload: Mapping[str, Any], row: Mapping[str, Any], now: str) -> dict[str, Any]:
    return {
        "schema_version": NETWORK_RERUN_DESTINATION_POLICY_RESULT_SCHEMA_VERSION,
        "phase": "phase_6_destination_policy_integration",
        "batch_id": str(payload.get("batch_id") or ""),
        "row_key": str(row.get("row_key") or ""),
        "status": "applying",
        "ok": False,
        "terminal": False,
        "started_at_utc": now,
        "message": "Coordinator destination policy is applying.",
    }


def _destination_policy_unavailable_result(payload: Mapping[str, Any], row: Mapping[str, Any], now: str) -> dict[str, Any]:
    result = _destination_policy_applying_result(payload, row, now)
    result.update(
        {
            "status": "failed",
            "errors": ["resolved_paths_unavailable"],
            "message": "Resolved path context is unavailable for Network CSV rerun destination policy.",
            "completed_at_utc": now,
        }
    )
    return result


def _apply_destination_policy_result(row: dict[str, Any], result: Mapping[str, Any]) -> None:
    action = str(result.get("action") or "")
    status = str(result.get("status") or "")
    persisted_result = dict(result)
    if persisted_result.get("ok") is not True:
        persisted_result["terminal"] = True
        persisted_result.setdefault("completed_at_utc", _now())
    row["destination_policy_result"] = persisted_result
    row["claimable"] = False
    row["destination_policy_applied"] = result.get("ok") is True
    row["updated_at"] = str(result.get("completed_at_utc") or result.get("started_at_utc") or _now())
    if result.get("ok") is True:
        row["reducer_result"] = {
            **dict(row.get("reducer_result") or {}),
            "pending_destination_policy": False,
            "destination_policy_applied": True,
        }
        if action == "review_workspace" or status == "review_workspace":
            row["status"] = "review_workspace"
            row["review_output_path"] = str(result.get("review_output_path") or row.get("verified_output_path") or "")
            row["reason"] = str(result.get("message") or "Network CSV rerun output requires review.")
        elif action == "pending_publish" or status == "pending_publish":
            row["status"] = "pending_publish"
            row["pending_publish_manifest_path"] = str(result.get("pending_publish_manifest_path") or "")
            row["pending_publish_payload_path"] = str(result.get("pending_publish_payload_path") or "")
            row["server_out"] = str(result.get("server_out") or row.get("final_output_path") or "")
            row["reason"] = str(result.get("message") or "Network CSV rerun output parked in Pending Publish.")
        elif status in {"published_replace_final", "published_non_overlap"}:
            row["status"] = status
            row["published_path"] = str(result.get("published_path") or "")
            row["server_out"] = str(result.get("published_path") or row.get("final_output_path") or "")
            row["reason"] = str(result.get("message") or "Network CSV rerun output published by coordinator policy.")
        else:
            row["status"] = "destination_policy_applied"
            row["reason"] = str(result.get("message") or "Network CSV rerun destination policy applied.")
        return
    row["reducer_result"] = {
        **dict(row.get("reducer_result") or {}),
        "pending_destination_policy": False,
        "destination_policy_applied": False,
        "destination_policy_failed": True,
    }
    row["status"] = "destination_policy_failed"
    row["reason"] = str(result.get("message") or "Network CSV rerun destination policy failed.")


def _request_metadata(request: Any, app: Any) -> dict[str, Any]:
    metadata = {
        "job_kind": NETWORK_RERUN_ROW_JOB_KIND,
        "rerun_batch_id": _request_text(request, "rerun_batch_id"),
        "rerun_row_key": _request_text(request, "rerun_row_key"),
        "planned_output_path": _request_text(request, "planned_output_path"),
        "source_identity": _request_mapping(request, "source_identity"),
        "coordinator_source_path": _request_text(request, "coordinator_source_path"),
        "worker_source_path": _request_text(request, "worker_source_path"),
        "handoff_probe": _request_mapping(request, "handoff_probe"),
        "destination_policy_applied": _request_bool(request, "destination_policy_applied"),
    }
    path = _metadata_state_path(metadata, app)
    if path is not None:
        metadata["batch_state_path"] = str(path)
    return metadata


def _row_matches(row: Mapping[str, Any], metadata: Mapping[str, Any]) -> bool:
    return str(row.get("row_key") or "") == str(metadata.get("rerun_row_key") or "")


def update_network_rerun_row_released(*, app: Any, job: Any, worker_id: str, reason: str = "") -> bool:
    metadata = getattr(job, "claim_metadata", {}) if getattr(job, "claim_metadata", None) else {}
    if not isinstance(metadata, Mapping) or metadata.get("job_kind") != NETWORK_RERUN_ROW_JOB_KIND:
        return False
    path = _metadata_state_path(metadata, app)
    if path is None or not path.exists():
        return False
    payload = _read_state(path)
    now = _now()
    for row in payload.get("rows") or []:
        if not isinstance(row, dict) or not _row_matches(row, metadata):
            continue
        row["status"] = "pending_claim"
        row["claim_status"] = "released"
        row["claimable"] = True
        row.pop("active_claim", None)
        row["last_release"] = {
            "job_id": str(getattr(job, "job_id", "") or ""),
            "worker_id": worker_id,
            "released_at_utc": now,
            "reason": redact_network_secret_text(reason),
        }
        payload["updated_at_utc"] = _now()
        _update_counts(payload)
        _write_state(path, payload)
        return True
    return False


def update_network_rerun_row_done(
    *,
    app: Any,
    job: Any,
    request: Any,
) -> bool:
    metadata = getattr(job, "claim_metadata", {}) if getattr(job, "claim_metadata", None) else {}
    if not isinstance(metadata, Mapping) or metadata.get("job_kind") != NETWORK_RERUN_ROW_JOB_KIND:
        return False
    metadata = dict(metadata)
    metadata.setdefault("job_id", str(getattr(job, "job_id", "") or _request_text(request, "job_id")))
    path = _metadata_state_path(metadata, app)
    if path is None or not path.exists():
        return False
    payload = _read_state(path)
    now = _now()
    for row in payload.get("rows") or []:
        if not isinstance(row, dict) or not _row_matches(row, metadata):
            continue
        if _duplicate_reducer_result(row, request=request, now=now):
            payload["updated_at_utc"] = now
            _update_counts(payload)
            _write_state(path, payload)
            return True
        artifact, _payload = _read_worker_result_artifact(_request_text(request, "worker_result_artifact_path"))
        row["worker_result"] = _worker_result_snapshot(metadata=metadata, request=request, now=now, artifact=artifact)
        reducer_result = _build_reducer_result(
            payload=payload,
            row=row,
            metadata=metadata,
            request=request,
            now=now,
        )
        _apply_reducer_result(row, reducer_result)
        if reducer_result.get("accepted") is True and _destination_policy_enabled(payload):
            row["destination_policy_result"] = _destination_policy_applying_result(payload, row, now)
            row["status"] = "destination_policy_applying"
            payload["updated_at_utc"] = now
            _update_counts(payload)
            _write_state(path, payload)
            resolved = getattr(app, "resolved", None)
            if resolved is None:
                destination_result = _destination_policy_unavailable_result(payload, row, _now())
            else:
                destination_result = apply_network_rerun_destination_policy(
                    resolved,
                    payload,
                    row,
                    product_version=str(getattr(app, "product_version", "") or getattr(app, "_product_version", "") or ""),
                )
            _apply_destination_policy_result(row, destination_result)
        payload["updated_at_utc"] = now
        _update_counts(payload)
        _write_state(path, payload)
        return True
    return False


def record_late_network_rerun_row_done(
    *,
    app: Any,
    request: Any,
    late_report: Mapping[str, Any] | None = None,
    only_duplicate: bool = False,
) -> bool:
    metadata = _request_metadata(request, app)
    if metadata.get("job_kind") != NETWORK_RERUN_ROW_JOB_KIND:
        return False
    if not str(metadata.get("rerun_batch_id") or "") or not str(metadata.get("rerun_row_key") or ""):
        return False
    path = _metadata_state_path(metadata, app)
    if path is None or not path.exists():
        return False
    payload = _read_state(path)
    now = _now()
    for row in payload.get("rows") or []:
        if not isinstance(row, dict) or not _row_matches(row, metadata):
            continue
        if only_duplicate:
            if _duplicate_reducer_result(row, request=request, now=now):
                payload["updated_at_utc"] = now
                _update_counts(payload)
                _write_state(path, payload)
                return True
            return False
        artifact, _payload = _read_worker_result_artifact(_request_text(request, "worker_result_artifact_path"))
        late_result = _build_reducer_result(
            payload=payload,
            row=row,
            metadata=metadata,
            request=request,
            now=now,
            late=True,
        )
        if late_report is not None:
            late_result["registry_late_report"] = dict(late_report)
        row["last_late_worker_result"] = _worker_result_snapshot(metadata=metadata, request=request, now=now, artifact=artifact)
        row["last_late_reducer_result"] = late_result
        row["late_done_count"] = _safe_int(row.get("late_done_count")) + 1
        _append_bounded(row, "late_worker_results", late_result)
        payload["updated_at_utc"] = now
        _update_counts(payload)
        _write_state(path, payload)
        return True
    return False


__all__ = [
    "NETWORK_RERUN_ROW_JOB_KIND",
    "NetworkRerunClaimLease",
    "claim_next_network_rerun_row",
    "network_rerun_state_root_for_app",
    "record_late_network_rerun_row_done",
    "rollback_network_rerun_claim",
    "update_network_rerun_row_done",
    "update_network_rerun_row_released",
]
