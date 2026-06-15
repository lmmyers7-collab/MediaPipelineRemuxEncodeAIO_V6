"""Coordinator done-outcome side effects for completed worker jobs."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from mediapipeline.core.network.url_policy import redact_network_secret_text

from mediapipeline.desktop.network.failure_reasons import classify_failure_reason


@dataclass(frozen=True)
class DoneOutcome:
    """Coordinator-owned post-completion outcome details."""

    job: Any
    success: bool
    worker_id: str
    elapsed_seconds: float
    output_size_bytes: int
    completion_status: str
    publish_state: str
    publish_mode: str
    error_message: str
    queue_terminal: bool
    retry_on_failure: bool
    output_path: str = ""
    reason_code: str = ""
    reason: str = ""
    max_job_retries: int = 3


class CoordinatorDoneOutcomeService:
    """Apply coordinator-owned side effects after a job is completed."""

    def __init__(
        self,
        *,
        app: Any,
        registry: Any,
        inflight_state_path: Callable[[], Path],
        remove_from_queue: Callable[[str], None],
        safe_log_cluster_event: Callable[..., None],
        logger: logging.Logger,
    ) -> None:
        self._app = app
        self._registry = registry
        self._inflight_state_path = inflight_state_path
        self._remove_from_queue = remove_from_queue
        self._safe_log_cluster_event = safe_log_cluster_event
        self._log = logger

    def handle(self, outcome: DoneOutcome) -> None:
        """Emit logs, queue-removal scheduling, and registry persistence."""
        if outcome.success:
            self._handle_success(outcome)
        else:
            self._handle_failure(outcome)

        self._save_registry_after_done(outcome)

    def _remove_queue_record_directly(self, source_path: str) -> bool:
        """Last-resort removal when the app scheduler cannot run callbacks.

        A failed ``root.after()`` means no UI loop is consuming
        ``queue_records``, so removing from this thread cannot race the
        scheduler path it replaces.
        """
        try:
            self._remove_from_queue(source_path)
        except Exception:
            self._log.exception("Direct queue-record removal failed for %s.", source_path)
            return False
        return True

    def _handle_success(self, outcome: DoneOutcome) -> None:
        job = outcome.job
        source_path = job.source_path
        try:
            self._app.root.after(
                0, lambda sp=source_path: self._remove_from_queue(sp)
            )
        except Exception as exc:
            if self._remove_queue_record_directly(source_path):
                self._log.info(
                    "App scheduler unavailable for completed job %s; queue record removed directly: %s",
                    job.job_id[:8],
                    exc,
                )
            else:
                self._log.warning(
                    "Failed to schedule queue removal for completed job %s; queue record may remain claimable until manually removed: %s",
                    job.job_id[:8],
                    exc,
                )
        out_mb = (outcome.output_size_bytes / (1024 * 1024)) if outcome.output_size_bytes else 0.0
        output_path_suffix = f" Output: {outcome.output_path}" if outcome.output_path else ""
        self._log.info(
            "Worker '%s' completed %s (%.1f s, %.1f MB out, status=%s, publish=%s/%s).%s",
            job.worker_name or outcome.worker_id[:8],
            Path(job.source_path).name,
            outcome.elapsed_seconds, out_mb,
            outcome.completion_status or "processed",
            outcome.publish_state or "unknown",
            outcome.publish_mode or "",
            output_path_suffix,
        )
        event_name = "job_completed"
        if outcome.publish_state and outcome.publish_state != "published":
            event_name = "job_completed_pending_publish"
        self._safe_log_cluster_event(
            event_name.replace("_", "-"),
            level="INFO",
            event=event_name,
            message=(
                f"{Path(job.source_path).name} ({outcome.elapsed_seconds:.1f}s, "
                f"{out_mb:.1f} MB out, status={outcome.completion_status or 'processed'}, "
                f"publish={outcome.publish_state or 'unknown'}/{outcome.publish_mode or ''})"
                f"{output_path_suffix}"
            ),
            worker_id=outcome.worker_id,
            worker_name=job.worker_name,
            role="coordinator",
            job_id=job.job_id,
            source_path=job.source_path,
        )

    def _handle_failure(self, outcome: DoneOutcome) -> None:
        job = outcome.job
        reason_code, reason = classify_failure_reason(
            success=False,
            reason_code=outcome.reason_code,
            reason=outcome.reason,
            error_message=outcome.error_message,
            completion_status=outcome.completion_status,
            source_path=getattr(job, "source_path", ""),
            output_path=outcome.output_path,
            route=outcome.publish_mode,
        )
        err_msg = redact_network_secret_text(reason or outcome.error_message or "(no detail)")
        self._log.warning(
            "Worker '%s' failed %s: %s (%s)",
            job.worker_name or outcome.worker_id[:8],
            Path(job.source_path).name,
            err_msg,
            reason_code,
        )
        event_name = "job_terminal_failed" if outcome.queue_terminal else "job_failed"
        self._safe_log_cluster_event(
            event_name.replace("_", "-"),
            level="ERROR",
            event=event_name,
            message=(
                f"{Path(job.source_path).name}: {err_msg[:200]}"
                f" status={outcome.completion_status or 'failed'} reason_code={reason_code}"
            ),
            worker_id=outcome.worker_id,
            worker_name=job.worker_name,
            role="coordinator",
            job_id=job.job_id,
            source_path=job.source_path,
            reason_code=reason_code,
            reason=err_msg,
        )
        alert = None
        marker = getattr(self._registry, "mark_failure_quarantine_alerted", None)
        if callable(marker):
            alert = marker(
                worker_id=outcome.worker_id,
                source_path=job.source_path,
                max_retries=outcome.max_job_retries,
            )
        if alert:
            count = int(alert.get("consecutive_count", 0) or 0)
            alert_reason_code = str(alert.get("reason_code") or reason_code)
            alert_reason = redact_network_secret_text(alert.get("reason") or err_msg)
            self._safe_log_cluster_event(
                "worker-quarantined",
                level="ERROR",
                event="worker_quarantined",
                message=(
                    f"Suppressed future claims for {Path(job.source_path).name} on "
                    f"{job.worker_name or outcome.worker_id[:8]} after {count} "
                    f"{alert_reason_code} failure(s): {alert_reason[:200]}"
                ),
                worker_id=outcome.worker_id,
                worker_name=job.worker_name,
                role="coordinator",
                job_id=job.job_id,
                source_path=job.source_path,
                reason_code=alert_reason_code,
                reason=alert_reason,
                consecutive_count=count,
                max_job_retries=outcome.max_job_retries,
            )
        # Retry policy: terminal worker outcomes have already produced
        # a durable skip/failure decision and should not be re-claimed.
        if outcome.queue_terminal or not outcome.retry_on_failure:
            source_path = job.source_path
            try:
                self._app.root.after(
                    0, lambda sp=source_path: self._remove_from_queue(sp)
                )
            except Exception as exc:
                if self._remove_queue_record_directly(source_path):
                    self._log.info(
                        "App scheduler unavailable after done report for %s; queue record removed directly: %s",
                        Path(job.source_path).name,
                        exc,
                    )
                else:
                    self._log.warning(
                        "Failed to schedule queue removal after done report for %s; queue record may remain claimable until manually removed: %s",
                        Path(job.source_path).name,
                        exc,
                    )
            else:
                self._log.info(
                    "Retry policy: scheduled queue removal for %s (queue_terminal=%s, retry_on_failure=%s).",
                    Path(job.source_path).name, outcome.queue_terminal, outcome.retry_on_failure,
                )

    def _save_registry_after_done(self, outcome: DoneOutcome) -> None:
        job = outcome.job
        try:
            self._registry.save(self._inflight_state_path())
        except Exception as exc:
            safe_exc = redact_network_secret_text(exc)
            self._log.error("Failed to save registry after done report: %s", safe_exc)
            self._safe_log_cluster_event(
                "inflight-save-failed",
                level="ERROR",
                event="inflight_save_failed",
                message=f"Failed to save in-flight registry after done report: {safe_exc}",
                worker_id=outcome.worker_id,
                worker_name=job.worker_name,
                role="coordinator",
                job_id=job.job_id,
                source_path=job.source_path,
            )
