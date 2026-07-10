"""Worker claim parsing and ClaimedJob construction."""
from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from typing import Any

from ..dispatcher import ClaimedJob
from ..protocol import ClaimResponse


def parse_claim_response_payload(payload: dict[str, Any]) -> ClaimResponse:
    """Parse a coordinator claim response into the shared protocol object."""
    claim = ClaimResponse.from_dict(payload)
    if claim.job_kind not in {"pipeline_queue", "csv_rerun_row"}:
        raise ValueError(f"unsupported claim job_kind: {claim.job_kind}")
    if claim.status == "ok":
        if not claim.job_id.strip() or not claim.source_path.strip() or claim.source_path.strip() == ".":
            raise ValueError("ok claim response requires non-empty job_id and source_path")
        if claim.job_kind == "csv_rerun_row":
            if not claim.rerun_batch_id.strip() or not claim.rerun_row_key.strip():
                raise ValueError("csv_rerun_row claim requires rerun_batch_id and rerun_row_key")
            if not claim.planned_output_path.strip():
                raise ValueError("csv_rerun_row claim requires planned_output_path")
    return claim


def malformed_claim_identity(payload: object) -> tuple[str, str] | None:
    """Extract a trustworthy job/source identity from a malformed ok claim."""
    if not isinstance(payload, dict) or str(payload.get("status", "")).strip().lower() != "ok":
        return None
    job_id = str(payload.get("job_id", "") or "").strip()
    if not job_id:
        return None
    source_path = str(payload.get("source_path", "") or "").strip()
    if not source_path or source_path == ".":
        return None
    return job_id, source_path


def claim_with_source_path(claim: ClaimResponse, source_path: str) -> ClaimResponse:
    """Return a claim with the same metadata but a worker-local source path."""
    coordinator_source_path = claim.coordinator_source_path or claim.source_path
    return ClaimResponse(
        status=claim.status,
        job_id=claim.job_id,
        source_path=source_path,
        library_id=claim.library_id,
        relative_path=claim.relative_path,
        priority=claim.priority,
        estimated_size_gb=claim.estimated_size_gb,
        encode_config=claim.encode_config,
        retry_on_failure=claim.retry_on_failure,
        retry_after_seconds=claim.retry_after_seconds,
        job_kind=claim.job_kind,
        rerun_batch_id=claim.rerun_batch_id,
        rerun_row_key=claim.rerun_row_key,
        rerun_row_index=claim.rerun_row_index,
        planned_output_path=claim.planned_output_path,
        output_handoff=dict(claim.output_handoff),
        source_identity=dict(claim.source_identity),
        coordinator_source_path=coordinator_source_path,
        worker_source_path=source_path,
        handoff_probe=dict(claim.handoff_probe),
        destination_policy_applied=claim.destination_policy_applied,
    )


def claim_metadata_from_claim(claim: ClaimResponse) -> dict[str, Any]:
    """Return durable metadata for a claimed job."""
    return {
        "job_kind": claim.job_kind or "pipeline_queue",
        "rerun_batch_id": claim.rerun_batch_id,
        "rerun_row_key": claim.rerun_row_key,
        "rerun_row_index": claim.rerun_row_index,
        "planned_output_path": claim.planned_output_path,
        "output_handoff": dict(claim.output_handoff),
        "source_identity": dict(claim.source_identity),
        "coordinator_source_path": claim.coordinator_source_path or claim.source_path,
        "worker_source_path": claim.worker_source_path or claim.source_path,
        "handoff_probe": dict(claim.handoff_probe),
        "destination_policy_applied": bool(claim.destination_policy_applied),
    }


def build_claimed_job(
    claim: ClaimResponse,
    worker_id: str,
    *,
    record_builder: Callable[[ClaimResponse], Any],
) -> ClaimedJob:
    """Build the dispatcher job object that carries worker retry metadata."""
    record = record_builder(claim)
    encode_config = dict(claim.encode_config)
    claim_metadata = claim_metadata_from_claim(claim)
    encode_config["__retry_on_failure"] = claim.retry_on_failure
    encode_config["__job_kind"] = claim_metadata["job_kind"]
    encode_config["__claim_metadata"] = claim_metadata
    return ClaimedJob(
        job_id=claim.job_id,
        record=record,
        encode_config=encode_config,
        claimed_at=datetime.now(),
        worker_id=worker_id,
        claim_metadata=claim_metadata,
    )
