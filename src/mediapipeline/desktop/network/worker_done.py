from __future__ import annotations

from typing import Any

from .failure_reasons import (
    REASON_WORKER_CRASH,
    classify_failure_reason,
)
from .protocol import DoneRequest


def build_crash_recovery_done_request(job_id: str, worker_id: str) -> DoneRequest:
    return DoneRequest(
        job_id=str(job_id or ""),
        worker_id=str(worker_id or ""),
        success=False,
        error_message="Worker crashed or restarted",
        reason_code=REASON_WORKER_CRASH,
        reason="Worker crashed or restarted",
    )


def build_release_done_request(job_id: str, worker_id: str) -> DoneRequest:
    return DoneRequest(
        job_id=str(job_id or ""),
        worker_id=str(worker_id or ""),
        success=False,
        released=True,
    )


def build_completion_done_request(
    job: Any,
    worker_id: str,
    *,
    success: bool,
    output_path: str | None = None,
    elapsed_seconds: float = 0.0,
    output_size_bytes: int | None = None,
    error: str | None = None,
    completion_status: str | None = None,
    publish_state: str | None = None,
    publish_mode: str | None = None,
    route: str | None = None,
    queue_terminal: bool = False,
    retry_on_failure: bool | None = None,
    reason_code: str | None = None,
    reason: str | None = None,
) -> DoneRequest:
    if retry_on_failure is None:
        retry = bool(getattr(job, "encode_config", {}).get("__retry_on_failure", True))
    else:
        retry = bool(retry_on_failure)
    retry = retry and not bool(queue_terminal)
    record = getattr(job, "record", None)
    source_path = str(getattr(record, "source_path", "") or "")
    final_reason_code, final_reason = classify_failure_reason(
        success=bool(success),
        reason_code=reason_code or "",
        reason=reason or "",
        error_message=error or "",
        completion_status=completion_status or "",
        source_path=source_path,
        output_path=output_path or "",
        route=route or "",
    )
    return DoneRequest(
        job_id=str(getattr(job, "job_id", "") or ""),
        worker_id=str(worker_id or ""),
        success=bool(success),
        output_path=output_path or "",
        elapsed_seconds=elapsed_seconds,
        output_size_bytes=output_size_bytes or 0,
        error_message=error or "",
        completion_status=completion_status or "",
        reason_code=final_reason_code,
        reason=final_reason,
        publish_state=publish_state or "",
        publish_mode=publish_mode or "",
        route=route or "",
        queue_terminal=bool(queue_terminal),
        retry_on_failure=retry,
    )
