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
) -> None:
    """Schedule an app-side abort for a coordinator-reclaimed worker job."""
    try:
        post_callback(
            "worker-abort-current-job",
            getattr(app, "_worker_abort_current_job"),
        )
    except Exception as exc:
        log.error(
            "Failed to schedule abort for reclaimed job %s: %s",
            job.job_id,
            diagnostic_preview(exc),
        )
