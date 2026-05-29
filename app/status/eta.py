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
    now: datetime | None = None,
) -> dict[str, Any]:
    """Build read-only ETA estimates only when worker-progress evidence is sufficient."""
    active_rows = [row for row in _worker_rows(worker_progress) if _active_row(row)]
    rows = [_eta_row(row, now=now) for row in active_rows]
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
            "Data source: desktop_worker_progress.v1 percent and elapsed_seconds.",
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
