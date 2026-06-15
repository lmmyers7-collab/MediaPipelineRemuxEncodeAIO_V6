"""Worker claim parsing and ClaimedJob construction."""
from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from typing import Any

from ..dispatcher import ClaimedJob
from ..protocol import ClaimResponse


def parse_claim_response_payload(payload: dict[str, Any]) -> ClaimResponse:
    """Parse a coordinator claim response into the shared protocol object."""
    return ClaimResponse.from_dict(payload)


def malformed_claim_identity(payload: object) -> tuple[str, str] | None:
    """Extract a trustworthy job/source identity from a malformed ok claim."""
    if not isinstance(payload, dict) or str(payload.get("status", "")).strip().lower() != "ok":
        return None
    job_id = str(payload.get("job_id", "") or "").strip()
    if not job_id:
        return None
    source_path = str(payload.get("source_path", "") or "")
    return job_id, source_path


def claim_with_source_path(claim: ClaimResponse, source_path: str) -> ClaimResponse:
    """Return a claim with the same metadata but a worker-local source path."""
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
    )


def build_claimed_job(
    claim: ClaimResponse,
    worker_id: str,
    *,
    record_builder: Callable[[ClaimResponse], Any],
) -> ClaimedJob:
    """Build the dispatcher job object that carries worker retry metadata."""
    record = record_builder(claim)
    encode_config = dict(claim.encode_config)
    encode_config["__retry_on_failure"] = claim.retry_on_failure
    return ClaimedJob(
        job_id=claim.job_id,
        record=record,
        encode_config=encode_config,
        claimed_at=datetime.now(),
        worker_id=worker_id,
    )
