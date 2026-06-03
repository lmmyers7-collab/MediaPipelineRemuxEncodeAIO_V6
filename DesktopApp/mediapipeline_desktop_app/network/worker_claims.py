"""Claim, done, and release helpers for :class:`WorkerDispatcher`."""
from __future__ import annotations

import logging
import threading
from pathlib import Path

from .diagnostics import diagnostic_preview as _worker_diagnostic_preview
from .dispatcher import ClaimedJob
from .protocol import ClaimResponse
from .worker_done import build_completion_done_request, build_release_done_request
from .worker_parts.reporting import request_abort_reclaimed_job
from .worker_parts.results import completion_cluster_event, release_cluster_event
from .worker_parts.tasks import malformed_claim_identity

_log = logging.getLogger("mediapipeline_desktop_app.network.worker")


class WorkerClaimMixin:
    def _request_abort_reclaimed_job(self, job: ClaimedJob) -> None:
        """Ask the app callback scheduler to abort a job reclaimed by the coordinator."""
        request_abort_reclaimed_job(
            self.app,
            job,
            post_callback=self._post_app_callback,
            log=_log,
            diagnostic_preview=_worker_diagnostic_preview,
        )

    def _release_unstartable_claim(self, claim: ClaimResponse, reason: str) -> None:
        """Release a claimed job that cannot be converted into local work."""
        self._release_claim_identity(claim.job_id, claim.source_path, reason)

    def _release_claim_identity(self, job_id: str, source_path: str, reason: str) -> None:
        """Release a claimed job when only its wire identity is trustworthy."""
        reason_preview = _worker_diagnostic_preview(reason)
        try:
            self._http_post(
                "/api/done",
                build_release_done_request(job_id, self._worker_id).to_dict(),
            )
            self._notify_status(f"⚠ Released unstartable claim: {reason_preview[:80]}")
        except Exception as exc:
            failure_preview = _worker_diagnostic_preview(exc)
            _log.warning(
                "Failed to release unstartable claimed job %s after %s: %s",
                job_id[:8],
                reason_preview,
                failure_preview,
            )
            self._notify_status(f"⚠ Could not release unstartable claim: {failure_preview[:80]}")

    def _release_malformed_claim_response(self, resp: object, reason: str) -> bool:
        """Release an already-claimed job when the claim body cannot be parsed."""
        identity = malformed_claim_identity(resp)
        if identity is None:
            return False
        job_id, source_path = identity
        reason_preview = _worker_diagnostic_preview(reason)
        _log.warning(
            "Malformed claimed response for job %s; releasing claim: %s",
            job_id[:8],
            reason_preview,
        )
        self._safe_log_cluster_event(
            "malformed-claim",
            level="ERROR",
            event="claim_response_invalid",
            message=f"Worker could not parse claimed job response: {reason_preview}",
            job_id=job_id,
            source_path=source_path,
        )
        self._release_claim_identity(job_id, source_path, f"malformed claim response: {reason_preview}")
        return True

    def _on_job_claimed(self, job: ClaimedJob) -> None:
        """Called by the poll thread right after a job is claimed.

        Saves crash-recovery state, starts the heartbeat thread, and
        schedules the encode on the app callback thread.
        """
        self._save_worker_state(job)
        self._job_reclaimed  = False
        self._last_heartbeat_failure_text = ""
        self._heartbeat_stop = threading.Event()
        self._heartbeat_thread = threading.Thread(
            target=self._heartbeat_loop,
            args=(job,),
            name="worker-heartbeat",
            daemon=True,
        )
        try:
            self._heartbeat_thread.start()
        except Exception as exc:
            reason_preview = _worker_diagnostic_preview(exc)
            _log.error("Failed to start worker heartbeat thread for job %s: %s", job.job_id, reason_preview)
            self._notify_status(f"⚠ Could not start heartbeat for claimed job: {reason_preview[:80]}")
            self._safe_log_cluster_event(
                "heartbeat-start-failed",
                level="ERROR",
                event="heartbeat_start_failed",
                message=f"Worker could not start heartbeat thread for claimed job: {reason_preview}",
                job_id=job.job_id,
                source_path=str(job.record.source_path),
            )
            self._do_release(job)
            return
        _log.info(
            "Job claimed: job_id=%s path=%s",
            job.job_id, job.record.source_path,
        )
        self._safe_log_cluster_event(
            "claim-received",
            level="INFO",
            event="claim_received",
            message=f"Picked up {Path(str(job.record.source_path)).name}",
            job_id=job.job_id,
            source_path=str(job.record.source_path),
        )

        # Schedule the encode on the app callback thread.
        try:
            self._post_app_callback(
                "worker-start-single-file",
                lambda: self.app._worker_start_single_file(job),
            )
        except Exception as exc:
            reason_preview = _worker_diagnostic_preview(exc)
            _log.error("Failed to schedule _worker_start_single_file: %s", reason_preview)
            self._notify_status(f"⚠ Could not schedule claimed job: {reason_preview[:80]}")
            # Release the job immediately so the coordinator can re-queue it.
            self._do_release(job)

    def _do_release(self, job: ClaimedJob) -> None:
        """Internal: POST /api/done with released=True and clean up local state."""
        self._stop_heartbeat()
        with self._active_job_lock:
            self._active_job = None
        payload = build_release_done_request(job.job_id, self._worker_id).to_dict()
        report_accepted = False
        pending_report_saved = False
        try:
            self._http_post("/api/done", payload)
        except Exception as exc:
            reason_preview = _worker_diagnostic_preview(exc)
            _log.warning("POST /api/done (internal release) failed: %s", reason_preview)
            pending_report_saved = self._save_pending_done_report(job, payload)
            self._notify_status(f"⚠ Release report failed: {reason_preview[:80]}")
        else:
            report_accepted = True
            self._clear_worker_state_after_accepted_report(job.job_id, "internal release")
        if report_accepted:
            _log.info("Job %s internal release report accepted by coordinator.", job.job_id)
        elif pending_report_saved:
            _log.info("Job %s internal release report pending retry after coordinator POST failure.", job.job_id)
        else:
            _log.warning(
                "Job %s internal release report could not be saved for pending retry after coordinator POST failure.",
                job.job_id,
            )

    def claim_next(self) -> ClaimedJob | None:
        """In worker mode, claiming is driven by the background poll thread.

        This method always returns ``None``; the poll loop schedules work
        on the app callback thread through the app's UI callback queue.
        """
        return None

    def mark_done(
        self,
        job: ClaimedJob,
        *,
        success: bool,
        output_path: str | None = None,
        error: str | None = None,
        elapsed_seconds: float = 0.0,
        output_size_bytes: int | None = None,
        completion_status: str | None = None,
        publish_state: str | None = None,
        publish_mode: str | None = None,
        route: str | None = None,
        queue_terminal: bool = False,
    ) -> None:
        """Report job completion to the coordinator and clean up local state."""
        self._stop_heartbeat()
        with self._active_job_lock:
            self._active_job = None
        payload = build_completion_done_request(
            job,
            self._worker_id,
            success=success,
            output_path=output_path,
            elapsed_seconds=elapsed_seconds,
            output_size_bytes=output_size_bytes,
            error=error,
            completion_status=completion_status,
            publish_state=publish_state,
            publish_mode=publish_mode,
            route=route,
            queue_terminal=queue_terminal,
        ).to_dict()
        report_accepted = False
        pending_report_saved = False
        try:
            self._http_post("/api/done", payload)
        except Exception as exc:
            reason_preview = _worker_diagnostic_preview(exc)
            _log.warning("POST /api/done failed: %s", reason_preview)
            pending_report_saved = self._save_pending_done_report(job, payload)
            self._notify_status(f"⚠ Done report failed: {reason_preview[:80]}")
        else:
            report_accepted = True
            self._clear_worker_state_after_accepted_report(job.job_id, "done")
        if report_accepted:
            _log.info(
                "Job %s %s report accepted by coordinator.",
                job.job_id,
                "done" if success else "failed",
            )
        elif pending_report_saved:
            _log.info("Job %s completion report pending retry after coordinator POST failure.", job.job_id)
        else:
            _log.warning(
                "Job %s completion report could not be saved for pending retry after coordinator POST failure.",
                job.job_id,
            )
        event_context, event_kwargs = completion_cluster_event(
            job,
            success=success,
            elapsed_seconds=elapsed_seconds,
            output_size_bytes=output_size_bytes,
            completion_status=completion_status,
            error=error,
            publish_state=publish_state,
            queue_terminal=queue_terminal,
        )
        self._safe_log_cluster_event(event_context, **event_kwargs)

    def release(self, job: ClaimedJob) -> None:
        """Return the job to the coordinator queue without a failure record.

        Called on clean shutdown when the encode is still in flight.
        """
        self._stop_heartbeat()
        with self._active_job_lock:
            self._active_job = None
        payload = build_release_done_request(job.job_id, self._worker_id).to_dict()
        report_accepted = False
        pending_report_saved = False
        try:
            self._http_post("/api/done", payload)
        except Exception as exc:
            reason_preview = _worker_diagnostic_preview(exc)
            _log.warning("POST /api/done (release) failed: %s", reason_preview)
            pending_report_saved = self._save_pending_done_report(job, payload)
            self._notify_status(f"⚠ Release report failed: {reason_preview[:80]}")
        else:
            report_accepted = True
            self._clear_worker_state_after_accepted_report(job.job_id, "release")
        if report_accepted:
            _log.info("Job %s release report accepted by coordinator.", job.job_id)
        elif pending_report_saved:
            _log.info("Job %s release report pending retry after coordinator POST failure.", job.job_id)
        else:
            _log.warning(
                "Job %s release report could not be saved for pending retry after coordinator POST failure.",
                job.job_id,
            )
        event_context, event_kwargs = release_cluster_event(job)
        self._safe_log_cluster_event(event_context, **event_kwargs)
