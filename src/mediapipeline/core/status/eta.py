from __future__ import annotations

from datetime import datetime
import math
from typing import Any, Mapping


ETA_SCHEMA_VERSION = "desktop_eta.v1"


def _worker_rows(worker_progress: Mapping[str, Any] | None) -> list[Mapping[str, Any]]:
    rows = worker_progress.get("rows") if isinstance(worker_progress, Mapping) else []
    if not isinstance(rows, list):
        return []
    return [row for row in rows if isinstance(row, Mapping)]


def _finite_float(value: object) -> float | None:
    if value in (None, ""):
        return None
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(result):
        return None
    return result


def _finite_int(value: object) -> int | None:
    result = _finite_float(value)
    if result is None:
        return None
    return int(result)


def _parse_datetime(value: object) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = f"{text[:-1]}+00:00"
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        return None


def _elapsed_seconds(start: object, end: object, *, now: datetime | None = None) -> int | None:
    start_time = _parse_datetime(start)
    if start_time is None:
        return None
    end_time = _parse_datetime(end) or now or datetime.now(tz=start_time.tzinfo)
    if start_time.tzinfo is None and end_time.tzinfo is not None:
        end_time = end_time.replace(tzinfo=None)
    elif start_time.tzinfo is not None and end_time.tzinfo is None:
        end_time = end_time.replace(tzinfo=start_time.tzinfo)
    elapsed = int(round((end_time - start_time).total_seconds()))
    return elapsed if elapsed >= 0 else None


def _active_row(row: Mapping[str, Any]) -> bool:
    status = str(row.get("status_state") or row.get("status") or "").strip().casefold()
    return status in {"running", "active", "processing"}


def _unavailable_reason(row: Mapping[str, Any], percent: float | None, elapsed_seconds: int | None) -> str:
    if bool(row.get("stale")):
        return "Worker progress is stale, so ETA is not reliable."
    if percent is None:
        return "Worker progress did not report a usable percent."
    if percent <= 0:
        return "Worker progress is at 0%, so a remaining-time estimate would be unstable."
    if percent >= 100:
        return "Worker progress is at or above 100%, so no remaining time is estimated."
    if elapsed_seconds is None:
        return "Worker progress did not report usable elapsed seconds."
    if elapsed_seconds <= 0:
        return "Elapsed time is not positive yet, so ETA is not stable."
    return ""


def _confidence(percent: float, elapsed_seconds: int) -> str:
    if percent >= 10 and elapsed_seconds >= 60:
        return "medium"
    return "low"


def _eta_row(row: Mapping[str, Any], *, now: datetime | None = None) -> dict[str, Any]:
    _ = now
    percent = _finite_float(row.get("percent"))
    elapsed_seconds = _finite_int(row.get("elapsed_seconds"))
    reason = _unavailable_reason(row, percent, elapsed_seconds)
    eta_seconds: int | None = None
    confidence = ""
    basis = "No ETA estimate was calculated."
    if not reason and percent is not None and elapsed_seconds is not None:
        eta_seconds = int(round(elapsed_seconds * ((100.0 - percent) / percent)))
        if eta_seconds < 0:
            eta_seconds = 0
        confidence = _confidence(percent, elapsed_seconds)
        basis = "Linear projection from desktop_worker_progress.v1 percent and elapsed_seconds for the current stage."

    return {
        "job_id": str(row.get("job_id") or ""),
        "worker_id": str(row.get("worker_id") or ""),
        "worker_label": str(row.get("worker_label") or row.get("worker_id") or "Local worker"),
        "stage": str(row.get("stage") or ""),
        "source": str(row.get("source") or ""),
        "eta_seconds": eta_seconds,
        "confidence": confidence,
        "basis": basis,
        "percent": percent,
        "elapsed_seconds": elapsed_seconds,
        "updated_at": str(row.get("updated_at") or ""),
        "unavailable_reason": reason,
        "progress_source": str(row.get("progress_source") or "desktop_worker_progress.v1"),
    }


def _progress_copy_candidate(progress: Mapping[str, Any]) -> bool:
    push_state = str(progress.get("PushState") or "").strip().casefold()
    copy_state = str(progress.get("CopyState") or "").strip().casefold()
    stage = str(progress.get("CurrentStage") or "").strip().casefold()
    if push_state in {"copying", "copied_pending_reveal", "revealing", "complete", "deferred"}:
        return True
    if copy_state == "copying":
        return True
    if stage in {"push", "sidecar", "retry_pending_push"} and progress.get("CopyTotalBytes") not in (None, ""):
        return True
    return False


def _copy_confidence(percent: float | None, elapsed_seconds: int | None) -> str:
    if percent is not None and percent >= 100:
        return "high"
    if percent is not None and elapsed_seconds is not None and percent >= 10 and elapsed_seconds >= 60:
        return "medium"
    return "low"


def _copy_eta_row(progress: Mapping[str, Any], *, now: datetime | None = None) -> dict[str, Any] | None:
    if not _progress_copy_candidate(progress):
        return None

    copied = _finite_int(progress.get("CopyBytesCopied"))
    total = _finite_int(progress.get("CopyTotalBytes"))
    percent = _finite_float(progress.get("CopyPercent"))
    elapsed_seconds = _elapsed_seconds(progress.get("CopyStartedAt"), progress.get("CopyUpdatedAt"), now=now)
    # Prefer this run's learned publish-push throughput (weighted average of
    # completed server pushes) once at least one file has finished. The first
    # file of a run has no learned rate yet and falls back to its own partial
    # bytes/elapsed measurement below.
    session_rate = _finite_float(progress.get("CopySessionBytesPerSecond"))
    session_files = _finite_int(progress.get("CopySessionFilesCompleted"))
    use_session_rate = (
        session_rate is not None
        and session_rate > 0
        and session_files is not None
        and session_files >= 1
    )
    eta_seconds: int | None = None
    bytes_per_second: int | None = None
    bytes_remaining: int | None = None
    unavailable_reason = ""
    basis = "No publish-copy ETA estimate was calculated."

    if total is None or total <= 0:
        unavailable_reason = "Publish copy telemetry did not report total bytes."
    elif copied is None:
        unavailable_reason = "Publish copy telemetry did not report copied bytes."
    else:
        safe_copied = max(0, min(copied, total))
        if percent is None:
            percent = round((safe_copied / total) * 100.0, 1)
        bytes_remaining = max(0, total - safe_copied)
        if bytes_remaining == 0 or (percent is not None and percent >= 100):
            eta_seconds = 0
            bytes_per_second = None
            basis = "Publish copy telemetry reports the file copy is complete."
        elif use_session_rate:
            bytes_per_second = int(round(session_rate))
            eta_seconds = int(round(bytes_remaining / session_rate))
            files_label = "file" if session_files == 1 else "files"
            basis = (
                "Projection from this run's average publish-copy throughput "
                f"({session_files} completed {files_label})."
            )
        elif safe_copied <= 0:
            unavailable_reason = "Publish copy has not written enough bytes for a stable ETA."
        elif elapsed_seconds is None:
            unavailable_reason = "Publish copy telemetry did not report usable start and update timestamps."
        elif elapsed_seconds <= 0:
            unavailable_reason = "Publish copy elapsed time is not positive yet, so ETA is not stable."
        else:
            rate = safe_copied / elapsed_seconds
            if rate <= 0:
                unavailable_reason = "Publish copy write rate is not positive yet."
            else:
                bytes_per_second = int(round(rate))
                eta_seconds = int(round(bytes_remaining / rate))
                basis = "Linear projection from pipeline_progress.json publish-copy bytes and elapsed time."

    return {
        "job_id": str(progress.get("CurrentFileDisplay") or progress.get("CurrentFile") or "publish_copy"),
        "worker_id": "publish_copy",
        "worker_label": "Push file",
        "stage": str(progress.get("CurrentStage") or progress.get("PushState") or "publish copy"),
        "source": str(progress.get("CurrentFileDisplay") or progress.get("CurrentFile") or ""),
        "eta_seconds": eta_seconds,
        "confidence": _copy_confidence(percent, elapsed_seconds),
        "basis": basis,
        "percent": percent,
        "elapsed_seconds": elapsed_seconds,
        "bytes_per_second": bytes_per_second,
        "bytes_remaining": bytes_remaining,
        "bytes_copied": copied,
        "bytes_total": total,
        "updated_at": str(progress.get("CopyUpdatedAt") or progress.get("LastUpdate") or ""),
        "unavailable_reason": unavailable_reason,
        "progress_source": "pipeline_progress.json",
    }


def _summary_eta(row: Mapping[str, Any]) -> str:
    pieces = [
        f"job={row.get('job_id')}" if row.get("job_id") else "",
        f"stage={row.get('stage')}" if row.get("stage") else "",
        f"eta_seconds={row.get('eta_seconds')}" if row.get("eta_seconds") is not None else "",
        f"confidence={row.get('confidence')}" if row.get("confidence") else "",
    ]
    return "; ".join(piece for piece in pieces if piece) or "No ETA estimate is currently available."


def eta_payload(
    worker_progress: Mapping[str, Any] | None,
    *,
    progress: Mapping[str, Any] | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Build read-only ETA estimates only when worker-progress evidence is sufficient."""
    active_rows = [row for row in _worker_rows(worker_progress) if _active_row(row)]
    rows: list[dict[str, Any]] = []
    progress_mapping = progress if isinstance(progress, Mapping) else {}
    copy_row = _copy_eta_row(progress_mapping, now=now)
    if copy_row is not None:
        rows.append(copy_row)
    rows.extend(_eta_row(row, now=now) for row in active_rows)
    estimated_count = sum(1 for row in rows if row.get("eta_seconds") is not None)
    unavailable_count = sum(1 for row in rows if row.get("eta_seconds") is None)
    status = "loaded" if estimated_count else "unavailable" if unavailable_count else "idle"
    summary_lines = [
        f"ETA: {status}",
        f"Rows: {len(rows)}; estimated={estimated_count}; unavailable={unavailable_count}.",
    ]
    if estimated_count:
        first_estimate = next(row for row in rows if row.get("eta_seconds") is not None)
        summary_lines.append(f"Latest: {_summary_eta(first_estimate)}")
    elif unavailable_count:
        first_unavailable = rows[0]
        summary_lines.append(f"ETA unavailable: {first_unavailable.get('unavailable_reason') or 'insufficient backend progress evidence.'}")
    else:
        summary_lines.append("No active worker rows are available for ETA calculation.")
    summary_lines.extend(
        [
            "Data sources: pipeline_progress.json publish-copy bytes and desktop_worker_progress.v1 percent/elapsed_seconds.",
            "Mutation guardrail: ETA is read-only telemetry; it does not control process, queue, retry, publish, validation, or media policy.",
        ]
    )
    return {
        "schema_version": ETA_SCHEMA_VERSION,
        "mode": "worker_progress_eta",
        "status": status,
        "row_count": len(rows),
        "estimated_count": estimated_count,
        "unavailable_count": unavailable_count,
        "rows": rows,
        "summary_lines": summary_lines,
        "read_only": True,
    }


__all__ = [
    "ETA_SCHEMA_VERSION",
    "eta_payload",
]
