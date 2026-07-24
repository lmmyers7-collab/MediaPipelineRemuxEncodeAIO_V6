"""Worker status and app-callback reporting helpers."""
from __future__ import annotations

from collections.abc import Callable
from typing import Any


def is_unauthorized_http_error(error_text: str) -> bool:
    """Return True when an HTTP error string represents a coordinator 401."""
    return error_text.startswith("HTTP 401 ") or error_text.startswith("HTTP Error 401:")


def claim_failure_status_message(error_text: str, reason_preview: str, base_url: str) -> tuple[str, bool]:
    """Return the operator-facing status text and whether to log an auth event."""
    if is_unauthorized_http_error(error_text):
        if "clock_skew" in error_text:
            return "Auth error - coordinator/worker clock skew exceeds five minutes", True
        return "⚠ Auth error — token does not match coordinator", True
    if "timed out" in error_text.lower() or "refused" in error_text.lower():
        return f"⚠ Cannot reach coordinator ({base_url})", False
    return f"⚠ Poll error: {reason_preview[:80]}", False


def notify_status_callback(
    callback: Callable[[str], None] | None,
    msg: str,
    *,
    log: Any,
    diagnostic_preview: Callable[[object], str],
) -> None:
    """Invoke a worker status callback without letting callback failures escape."""
    if callback is None:
        return
    try:
        callback(msg)
    except Exception as exc:
        log.warning("Worker status callback failed: %s", diagnostic_preview(exc))


def post_app_callback(app: object, name: str, callback: Callable[[], None]) -> None:
    """Schedule a callback through the app's preferred UI callback mechanism."""
    poster = getattr(app, "post_ui", None)
    if callable(poster):
        poster(name, callback)
        return
    root = getattr(app, "root", None)
    if root is None or not hasattr(root, "after"):
        raise RuntimeError("app has no callback scheduler")
    root.after(1, callback)


def request_abort_reclaimed_job(
    app: object,
    job: object,
    *,
    post_callback: Callable[[str, Callable[[], None]], None],
    log: Any,
    diagnostic_preview: Callable[[object], str],
) -> bool:
    """Dispatch and verify abort containment for a reclaimed worker job."""
    job_id = str(getattr(job, "job_id", "") or "")
    scheduled = False
    try:
        scheduled_abort = getattr(app, "_worker_abort_current_job", None)
        if not callable(scheduled_abort):
            raise RuntimeError("app has no scheduled worker abort callback")
        post_callback(
            "worker-abort-current-job",
            scheduled_abort,
        )
        scheduled = True
    except Exception as exc:
        log.error(
            "Failed to schedule abort for reclaimed job %s: %s",
            job_id,
            diagnostic_preview(exc),
        )
        direct_abort = getattr(app, "abort_current_worker_job", None)
        if not callable(direct_abort):
            log.error("No backend-owned direct abort was available for reclaimed job %s.", job_id)
            return False
        try:
            direct_abort("network worker reclaimed fail-closed fallback")
        except Exception as direct_exc:
            log.error(
                "Backend-owned direct abort failed for reclaimed job %s: %s",
                job_id,
                diagnostic_preview(direct_exc),
            )
            return False

    wait_for_exit = getattr(app, "wait_for_active_process_exit", None)
    if not callable(wait_for_exit):
        return scheduled or callable(getattr(app, "abort_current_worker_job", None))
    try:
        contained = bool(wait_for_exit(timeout_seconds=5.0))
    except Exception as exc:
        log.error(
            "Could not verify process exit after abort for reclaimed job %s: %s",
            job_id,
            diagnostic_preview(exc),
        )
        return False
    if not contained:
        log.error("Process exit is not yet proven for reclaimed job %s; abort will be retried.", job_id)
    return contained
