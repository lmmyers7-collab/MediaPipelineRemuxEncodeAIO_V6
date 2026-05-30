"""Cluster-log event formatting for worker terminal reports."""
from __future__ import annotations

from pathlib import Path
from typing import Any


def completion_cluster_event(
    job: object,
    *,
    success: bool,
    elapsed_seconds: float,
    output_size_bytes: int | None = None,
    completion_status: str | None = None,
    error: str | None = None,
    publish_state: str | None = None,
    queue_terminal: bool = False,
) -> tuple[str, dict[str, Any]]:
    """Build the cluster-log context and payload for a done/failure report."""
    record = job.record
    source_path = str(getattr(record, "source_path", "")) if record else ""
    job_id = job.job_id
    if success:
        mb = (output_size_bytes / (1024 * 1024)) if output_size_bytes else 0.0
        state_suffix = f" publish={publish_state}" if publish_state else ""
        return (
            "encode-done",
            {
                "level": "INFO",
                "event": "encode_done",
                "message": (
                    f"Finished {Path(source_path).name} in {elapsed_seconds:.1f}s "
                    f"({mb:.1f} MB out){state_suffix}"
                ),
                "job_id": job_id,
                "source_path": source_path,
            },
        )

    event_name = "encode_terminal" if queue_terminal else "encode_failed"
    return (
        "encode-failed",
        {
            "level": "ERROR",
            "event": event_name,
            "message": (
                f"Pipeline failed for {Path(source_path).name} after "
                f"{elapsed_seconds:.1f}s: {(completion_status or error or '(no detail)')[:200]}"
            ),
            "job_id": job_id,
            "source_path": source_path,
        },
    )


def release_cluster_event(job: object) -> tuple[str, dict[str, Any]]:
    """Build the cluster-log context and payload for a clean worker release."""
    record = job.record
    source_path = str(getattr(record, "source_path", "")) if record else ""
    return (
        "job-released",
        {
            "level": "INFO",
            "event": "job_released",
            "message": f"Returned {Path(source_path).name} to the queue (clean release)",
            "job_id": job.job_id,
            "source_path": source_path,
        },
    )
