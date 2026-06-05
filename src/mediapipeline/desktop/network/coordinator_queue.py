"""Queue claim/done/release helpers for :class:`CoordinatorDispatcher`."""
from __future__ import annotations

import logging
import uuid
from datetime import datetime

from .coordinator_policy import RETRY_AFTER_IDLE_SECONDS as _RETRY_AFTER_IDLE_SECONDS
from .coordinator_policy import compute_retry_after_seconds
from .dispatcher import ClaimedJob
from .encode_config_snapshot import snapshot_encode_config
from .failure_policy import source_has_prior_failure
from .protocol import coerce_finite_float
from .use_cases.done_outcome import CoordinatorDoneOutcomeService, DoneOutcome

_log = logging.getLogger("mediapipeline.desktop.network.coordinator")


def _coerce_record_estimated_size_gb(record: object, source_path: str) -> float:
    """Return a safe non-negative size estimate for a queue record."""
    try:
        return coerce_finite_float(
            getattr(record, "estimated_size_gb", 0.0),
            "estimated_size_gb",
            minimum=0.0,
        )
    except Exception as exc:
        _log.warning(
            "Invalid estimated_size_gb for queue record %s; using 0.0: %s",
            source_path,
            exc,
        )
        return 0.0


class CoordinatorQueueMixin:
    def claim_next(self) -> ClaimedJob | None:
        """Claim the next unclaimed queue record for local encode.

        Only executes when ``CoordinatorAlsoEncodeLocally`` is ``True``.
        Returns ``None`` when the setting is off, the queue is empty, or
        all records are already in-flight with remote workers.

        Uses the same ``_claim_lock`` as the HTTP claim handler so a local
        claim and a concurrent remote worker claim never race over the
        same file.
        """
        # Respect the CoordinatorAlsoEncodeLocally config flag.
        if not bool(self._config().get("CoordinatorAlsoEncodeLocally", False)):
            return None

        worker_id   = getattr(self._app, "_machine_id", "coordinator")
        worker_name = "coordinator"

        # Hold the same claim lock used by the HTTP handler so local and
        # remote claims are serialised and never race on the same record.
        with self._claim_lock:
            record, encode_config = self._scan_for_next_record(worker_name)
            if record is None:
                return None

            job_id      = str(uuid.uuid4())
            source_path = str(getattr(record, "source_path", ""))

            ok = self._registry.claim(
                job_id=job_id,
                worker_id=worker_id,
                worker_name=worker_name,
                source_path=source_path,
                encode_config=encode_config,
                priority=bool(getattr(record, "priority", False)),
                estimated_size_gb=_coerce_record_estimated_size_gb(record, source_path),
            )

        if not ok:
            # Another worker claimed it between scan and claim.
            return None

        try:
            self._registry.save(self._inflight_state_path())
        except Exception as exc:
            _log.warning("Failed to save inflight state after local claim %s: %s", job_id[:8], exc)
            self._safe_log_cluster_event(
                "inflight-save-failed",
                level="WARN",
                event="inflight_save_failed",
                message=f"Failed to save in-flight registry after local claim: {exc}",
                worker_id=worker_id,
                worker_name=worker_name,
                role="coordinator",
                job_id=job_id,
                source_path=source_path,
            )
        return ClaimedJob(
            job_id=job_id,
            record=record,
            encode_config=encode_config,
            claimed_at=datetime.now(),
            worker_id=worker_id,
        )

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
        # W1 — previously this method called registry.complete() and saved,
        # but discarded every other parameter. The local-encode path
        # therefore produced no cluster.log entry, no queue-record removal,
        # no retry-policy decision, and no per-worker stats — local jobs
        # silently vanished from the operator's audit trail. Now both the
        # HTTP /api/done handler and this local path funnel through the
        # shared _emit_done_outcome helper for consistent bookkeeping.
        completed = self._registry.complete(
            job.job_id,
            job.worker_id,
            success           = success,
            elapsed_seconds   = elapsed_seconds,
            output_size_bytes = output_size_bytes or 0,
        )
        if completed is None:
            # The job was reclaimed by the stale-reaper between heartbeat
            # and completion, or already finalised by a duplicate report.
            # Save and bail — no log/queue side-effects to apply.
            _log.warning(
                "Local mark_done for job %s found no matching registry "
                "entry (likely reclaimed); skipping post-completion logging.",
                job.job_id[:8],
            )
            try:
                self._registry.save(self._inflight_state_path())
            except Exception as exc:
                _log.warning("Failed to save inflight state after missing local completion: %s", exc)
                source_path = str(getattr(getattr(job, "record", None), "source_path", "") or "")
                self._safe_log_cluster_event(
                    "inflight-save-failed",
                    level="WARN",
                    event="inflight_save_failed",
                    message=f"Failed to save in-flight registry after missing local completion: {exc}",
                    worker_id=job.worker_id,
                    worker_name="coordinator",
                    role="coordinator",
                    job_id=job.job_id,
                    source_path=source_path,
                )
            return

        self._emit_done_outcome(
            job               = completed,
            success           = success,
            worker_id         = job.worker_id,
            elapsed_seconds   = elapsed_seconds,
            output_size_bytes = int(output_size_bytes or 0),
            completion_status = completion_status or "",
            publish_state     = publish_state or "",
            publish_mode      = publish_mode or "",
            error_message     = error or "",
            queue_terminal    = bool(queue_terminal),
            # Local encodes follow the same default retry policy the
            # HTTP handler uses (DoneRequest.retry_on_failure default).
            retry_on_failure  = True,
        )

    def release(self, job: ClaimedJob) -> None:
        # N3 — pass the local worker_id so the registry's ownership
        # check accepts the release. Local-encode jobs are owned by
        # the coordinator process, identified by job.worker_id.
        self._registry.unclaim(job.job_id, job.worker_id)
        try:
            self._registry.save(self._inflight_state_path())
        except Exception as exc:
            _log.warning("Failed to save inflight state after local release %s: %s", job.job_id[:8], exc)
            self._safe_log_cluster_event(
                "inflight-save-failed",
                level="WARN",
                event="inflight_save_failed",
                message=f"Failed to save in-flight registry after local release: {exc}",
                worker_id=job.worker_id,
                worker_name="coordinator",
                role="coordinator",
                job_id=job.job_id,
            )

    def _scan_for_next_record(self, worker_name: str = "") -> tuple:
        """Find the first queue record not currently in-flight.

        Returns ``(record, encode_config)`` or ``(None, {})``.
        Callers that need atomicity (the HTTP claim handler and the local
        ``claim_next`` path) must hold ``_claim_lock`` before calling here.

        Takes a shallow snapshot of ``queue_records`` before iterating so
        that concurrent mutations from the app callback scheduler (for
        example ``_remove_from_queue``) cannot cause iterator-invalidation bugs.
        """
        records = list(getattr(self._app, "queue_records", []))  # snapshot
        for r in records:
            source = str(getattr(r, "source_path", ""))
            if not self._registry.is_in_flight(source):
                return r, self._snapshot_encode_config(worker_name)
        return None, {}

    def _compute_retry_after_seconds(self) -> int:
        """Return the backoff hint to attach to an empty ClaimResponse.

        W4 — when this worker found no claimable record, the reason is
        either (a) other workers are still encoding and a job may free
        up soon, or (b) the cluster is genuinely idle. Distinguish the
        two so workers poll fast in case (a) (catch a freshly-released
        job within a few seconds) and slow in case (b) (avoid hammering
        an empty coordinator with a stampede of pollers every cycle).

        Heuristic: any active in-flight job means "busy somewhere" —
        even if all queue records are claimed, an encode failure could
        re-queue one and we want to be ready. With zero active jobs,
        nothing is going to change without operator action, so back off.
        """
        try:
            active_count = self._registry.active_count
        except Exception as exc:
            _log.warning("Could not read active in-flight job count; using idle retry hint: %s", exc)
            return _RETRY_AFTER_IDLE_SECONDS
        return compute_retry_after_seconds(active_count)

    def _source_has_prior_failure(self, source_path: str) -> bool:
        """Return ``True`` if *source_path* appears in the app's failure records."""
        return source_has_prior_failure(source_path, getattr(self._app, "failure_records", []))

    def _snapshot_encode_config(self, worker_name: str = "") -> dict:
        """Snapshot the encode-relevant config keys at claim time.

        If *worker_name* matches an entry in ``WorkerConfigOverrides`` (a
        JSON object mapping worker names to partial config dicts), those
        overrides are applied on top of the global config snapshot.  This
        allows BEAST-PC to use ``"VideoPreset": "p4"`` while LAPTOP uses
        ``"VideoPreset": "p2"`` without separate config files.
        """
        resolved = getattr(self._app, "resolved", None)
        if resolved is None or not hasattr(resolved, "config_data"):
            return {}
        return snapshot_encode_config(resolved.config_data, worker_name)

    def _remove_from_queue(self, source_path: str) -> None:
        """Remove a completed record from queue_records (UI-thread only)."""
        records = getattr(self._app, "queue_records", None)
        if not records:
            return
        to_remove = [
            r for r in records
            if str(getattr(r, "source_path", "")) == source_path
        ]
        for r in to_remove:
            records.remove(r)
        if to_remove and hasattr(self._app, "apply_queue_filters"):
            self._app.apply_queue_filters()

    def _emit_done_outcome(
        self,
        *,
        job,                            # InFlightJob returned by registry.complete
        success: bool,
        worker_id: str,
        elapsed_seconds: float,
        output_size_bytes: int,
        completion_status: str,
        publish_state: str,
        publish_mode: str,
        error_message: str,
        queue_terminal: bool,
        retry_on_failure: bool,
    ) -> None:
        """Shared post-``registry.complete()`` bookkeeping.

        Emits the operator-facing console + cluster.log entry, schedules
        queue-record removal through the app callback scheduler, and persists the inflight
        state.  Called by both the HTTP ``/api/done`` handler and the
        local-encode :meth:`mark_done` path so a job completed by the
        coordinator's own encode session leaves the same audit trail as
        one completed by a remote worker.

        Source-policy guardrail phrases remain visible here while the
        service owns the implementation: "Failed to schedule queue removal after done report",
        "queue record may remain claimable until manually removed", and
        "Retry policy: scheduled queue removal".
        """
        CoordinatorDoneOutcomeService(
            app=getattr(self, "_app", None),
            registry=self._registry,
            inflight_state_path=self._inflight_state_path,
            remove_from_queue=self._remove_from_queue,
            safe_log_cluster_event=self._safe_log_cluster_event,
            logger=_log,
        ).handle(
            DoneOutcome(
                job=job,
                success=success,
                worker_id=worker_id,
                elapsed_seconds=elapsed_seconds,
                output_size_bytes=output_size_bytes,
                completion_status=completion_status,
                publish_state=publish_state,
                publish_mode=publish_mode,
                error_message=error_message,
                queue_terminal=queue_terminal,
                retry_on_failure=retry_on_failure,
            )
        )
