"""Queue claim/done/release helpers for :class:`CoordinatorDispatcher`."""
from __future__ import annotations

import contextlib
import logging
import uuid
from datetime import datetime

from mediapipeline.core.kernel.config_keys import KEY_COORDINATOR_MAX_JOB_RETRIES
from mediapipeline.core.network.url_policy import redact_network_secret_text
from mediapipeline.core.processes.pipeline_policy import coordinator_also_encode_locally_enabled

from .coordinator_policy import RETRY_AFTER_IDLE_SECONDS as _RETRY_AFTER_IDLE_SECONDS
from .coordinator_policy import compute_retry_after_seconds
from .dispatcher import ClaimedJob
from .encode_config_snapshot import snapshot_encode_config
from .failure_reasons import classify_failure_reason
from .failure_policy import source_has_prior_failure
from .protocol import coerce_finite_float, coerce_library_id_list
from .registry import normalize_source_identity
from .rerun_claims import (
    NETWORK_RERUN_ROW_JOB_KIND,
    claim_next_network_rerun_row,
    rollback_network_rerun_claim,
    update_network_rerun_row_done,
    update_network_rerun_row_released,
)
from .worker_parts.tasks import build_claimed_job
from .worker_record import make_queue_record as _make_queue_record
from .use_cases.done_outcome import CoordinatorDoneOutcomeService, DoneOutcome

_log = logging.getLogger("mediapipeline.desktop.network.coordinator")
COORDINATOR_MAX_JOB_RETRIES_DEFAULT = 3


def _coerce_record_estimated_size_gb(record: object, source_path: str) -> float:
    """Return a safe non-negative size estimate for a queue record.

    The live ``core.kernel.models.QueueRecord`` exposes ``size_gb``; older or
    synthetic records (and test doubles) use ``estimated_size_gb``. Prefer the
    real model field and fall back so both the live preview path and existing
    fixtures resolve a real value instead of silently defaulting to 0.0.
    """
    raw = getattr(record, "size_gb", None)
    if raw is None:
        raw = getattr(record, "estimated_size_gb", 0.0)
    try:
        return coerce_finite_float(
            raw,
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


def _coerce_record_priority(record: object) -> bool:
    """Return the priority flag for a queue record.

    The live ``QueueRecord`` exposes ``is_priority``; synthetic/legacy records
    (and test doubles) use ``priority``. Prefer the model field and fall back so
    priority is no longer silently dropped on real coordinator claims.
    """
    value = getattr(record, "is_priority", None)
    if value is None:
        value = getattr(record, "priority", False)
    return bool(value)


def _record_library_id(record: object) -> str:
    return str(getattr(record, "library_id", "") or "").strip()


def _worker_can_accept_record_library(
    record: object,
    accessible_library_ids: list[str] | None,
) -> bool:
    if accessible_library_ids is None:
        return True
    library_id = _record_library_id(record)
    if not library_id:
        return True
    accessible_keys = {item.casefold() for item in coerce_library_id_list(accessible_library_ids)}
    return library_id.casefold() in accessible_keys


def _app_queue_lock(app: object):
    """Return the app's queue mutation lock, or a null context for test doubles."""
    lock = getattr(app, "_queue_lock", None)
    if lock is None:
        return contextlib.nullcontext()
    return lock


def _coerce_coordinator_max_job_retries(config: dict) -> int:
    raw = config.get(KEY_COORDINATOR_MAX_JOB_RETRIES, COORDINATOR_MAX_JOB_RETRIES_DEFAULT)
    try:
        value = int(raw)
    except (TypeError, ValueError):
        _log.warning(
            "Invalid CoordinatorMaxJobRetries=%r; using default %d.",
            raw,
            COORDINATOR_MAX_JOB_RETRIES_DEFAULT,
        )
        return COORDINATOR_MAX_JOB_RETRIES_DEFAULT
    return max(1, min(100, value))


def _scan_for_next_record_for_claim(
    owner: object,
    worker_name: str,
    *,
    worker_id: str,
    max_job_retries: int,
    accessible_library_ids: list[str] | None = None,
) -> tuple:
    scanner = owner._scan_for_next_record
    try:
        return scanner(
            worker_name,
            worker_id=worker_id,
            max_job_retries=max_job_retries,
            accessible_library_ids=accessible_library_ids,
        )
    except TypeError as exc:
        # Some focused tests monkeypatch _scan_for_next_record with the old
        # single-argument shape. Preserve that compatibility while production
        # dispatchers use the worker-aware implementation.
        if "unexpected keyword argument" not in str(exc):
            raise
        return scanner(worker_name)


class CoordinatorQueueMixin:
    def _coordinator_max_job_retries(self) -> int:
        try:
            config = self._config()
        except Exception as exc:
            _log.warning(
                "Could not read CoordinatorMaxJobRetries config; using default %d: %s",
                COORDINATOR_MAX_JOB_RETRIES_DEFAULT,
                exc,
            )
            return COORDINATOR_MAX_JOB_RETRIES_DEFAULT
        return _coerce_coordinator_max_job_retries(dict(config or {}))

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
        if not coordinator_also_encode_locally_enabled(self._config()):
            return None

        worker_id   = getattr(self._app, "_machine_id", "coordinator")
        worker_name = "coordinator"

        # Hold the same claim lock used by the HTTP handler so local and
        # remote claims are serialised and never race on the same record.
        network_lease = None
        with self._claim_lock:
            network_lease = claim_next_network_rerun_row(
                app=self._app,
                registry=self._registry,
                worker_id=worker_id,
                worker_name=worker_name,
                accessible_library_ids=None,
                encode_config_for_row=lambda record: self._snapshot_encode_config(worker_name, record),
                allow_local_handoff=True,
            )
            if network_lease is not None:
                job_id = network_lease.response.job_id
                source_path = network_lease.response.source_path
                record = None
                encode_config = dict(network_lease.response.encode_config)
                ok = True
            else:
                record, encode_config = _scan_for_next_record_for_claim(
                    self,
                    worker_name,
                    worker_id=worker_id,
                    max_job_retries=self._coordinator_max_job_retries(),
                )
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
                    priority=_coerce_record_priority(record),
                    estimated_size_gb=_coerce_record_estimated_size_gb(record, source_path),
                )

        if not ok:
            # Another worker claimed it between scan and claim.
            return None

        try:
            self._registry.save(self._inflight_state_path())
        except Exception as exc:
            safe_exc = redact_network_secret_text(exc)
            _log.warning("Failed to save inflight state after local claim %s: %s", job_id[:8], safe_exc)
            try:
                rollback = getattr(self._registry, "rollback_claim", None)
                if network_lease is not None:
                    rollback_network_rerun_claim(network_lease, self._registry, reason=f"inflight save failed: {safe_exc}")
                elif callable(rollback):
                    rollback(job_id, worker_id)
                else:
                    self._registry.unclaim(job_id, worker_id)
            except Exception as release_exc:
                _log.warning(
                    "Failed to release local claim %s after inflight save failure: %s",
                    job_id[:8],
                    redact_network_secret_text(release_exc),
                )
            self._safe_log_cluster_event(
                "inflight-save-failed",
                level="WARN",
                event="inflight_save_failed",
                message=f"Local claim denied because in-flight registry could not be saved: {safe_exc}",
                worker_id=worker_id,
                worker_name=worker_name,
                role="coordinator",
                job_id=job_id,
                source_path=source_path,
            )
            return None
        if network_lease is not None:
            return build_claimed_job(
                network_lease.response,
                worker_id,
                record_builder=_make_queue_record,
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
        retry_on_failure: bool | None = None,
        reason_code: str | None = None,
        reason: str | None = None,
    ) -> None:
        # W1 — previously this method called registry.complete() and saved,
        # but discarded every other parameter. The local-encode path
        # therefore produced no cluster.log entry, no queue-record removal,
        # no retry-policy decision, and no per-worker stats — local jobs
        # silently vanished from the operator's audit trail. Now both the
        # HTTP /api/done handler and this local path funnel through the
        # shared _emit_done_outcome helper for consistent bookkeeping.
        source_path = str(getattr(getattr(job, "record", None), "source_path", "") or "")
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
        completed = self._registry.complete(
            job.job_id,
            job.worker_id,
            success           = success,
            elapsed_seconds   = elapsed_seconds,
            output_size_bytes = output_size_bytes or 0,
            reason_code       = final_reason_code,
            reason            = final_reason,
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
                safe_exc = redact_network_secret_text(exc)
                _log.warning("Failed to save inflight state after missing local completion: %s", safe_exc)
                source_path = str(getattr(getattr(job, "record", None), "source_path", "") or "")
                self._safe_log_cluster_event(
                    "inflight-save-failed",
                    level="WARN",
                    event="inflight_save_failed",
                    message=f"Failed to save in-flight registry after missing local completion: {safe_exc}",
                    worker_id=job.worker_id,
                    worker_name="coordinator",
                    role="coordinator",
                    job_id=job.job_id,
                    source_path=source_path,
            )
            return

        if getattr(completed, "job_kind", "") == NETWORK_RERUN_ROW_JOB_KIND:
            request = type(
                "NetworkRerunLocalDoneRequest",
                (),
                {
                    "job_id": job.job_id,
                    "worker_id": job.worker_id,
                    "success": bool(success),
                    "output_path": output_path or "",
                    "output_size_bytes": int(output_size_bytes or 0),
                    "completion_status": completion_status or "",
                    "publish_state": publish_state or "",
                    "publish_mode": publish_mode or "",
                    "route": route or "",
                    "reason_code": final_reason_code,
                    "reason": final_reason,
                    "error_message": error or "",
                },
            )()
            update_network_rerun_row_done(app=self._app, job=completed, request=request)
            try:
                self._registry.save(self._inflight_state_path())
            except Exception as exc:
                safe_exc = redact_network_secret_text(exc)
                _log.warning("Failed to save inflight state after local Network CSV rerun done %s: %s", job.job_id[:8], safe_exc)
                self._safe_log_cluster_event(
                    "inflight-save-failed",
                    level="WARN",
                    event="inflight_save_failed",
                    message=f"Failed to save in-flight registry after local Network CSV rerun done: {safe_exc}",
                    worker_id=job.worker_id,
                    worker_name="coordinator",
                    role="coordinator",
                    job_id=job.job_id,
                    source_path=source_path,
                )
                raise RuntimeError(f"registry save failed after local Network CSV rerun done: {safe_exc}") from exc
            self._safe_log_cluster_event(
                "network-rerun-row-pending-reduction",
                level="INFO" if success else "ERROR",
                event="network_rerun_row_pending_reduction",
                message="Network CSV rerun row completed by coordinator-local worker and is pending coordinator reduction.",
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
            retry_on_failure  = True if retry_on_failure is None else bool(retry_on_failure),
            output_path       = output_path or "",
            reason_code       = final_reason_code,
            reason            = final_reason,
        )

    def release(self, job: ClaimedJob) -> None:
        # N3 — pass the local worker_id so the registry's ownership
        # check accepts the release. Local-encode jobs are owned by
        # the coordinator process, identified by job.worker_id.
        released = self._registry.unclaim(job.job_id, job.worker_id)
        if getattr(released, "job_kind", "") == NETWORK_RERUN_ROW_JOB_KIND:
            update_network_rerun_row_released(
                app=self._app,
                job=released,
                worker_id=job.worker_id,
                reason="coordinator-local release",
            )
        try:
            self._registry.save(self._inflight_state_path())
        except Exception as exc:
            safe_exc = redact_network_secret_text(exc)
            _log.warning("Failed to save inflight state after local release %s: %s", job.job_id[:8], safe_exc)
            self._safe_log_cluster_event(
                "inflight-save-failed",
                level="WARN",
                event="inflight_save_failed",
                message=f"Failed to save in-flight registry after local release: {safe_exc}",
                worker_id=job.worker_id,
                worker_name="coordinator",
                role="coordinator",
                job_id=job.job_id,
            )

    def _scan_for_next_record(
        self,
        worker_name: str = "",
        *,
        worker_id: str = "",
        max_job_retries: int | None = None,
        accessible_library_ids: list[str] | None = None,
    ) -> tuple:
        """Find the first queue record not currently in-flight.

        Returns ``(record, encode_config)`` or ``(None, {})``.
        Callers that need atomicity (the HTTP claim handler and the local
        ``claim_next`` path) must hold ``_claim_lock`` before calling here.

        Takes a shallow snapshot of ``queue_records`` before iterating so
        that concurrent mutations from the app callback scheduler (for
        example ``_remove_from_queue``) or the coordinator queue refresher
        cannot cause iterator-invalidation bugs.
        """
        with _app_queue_lock(self._app):
            records = list(getattr(self._app, "queue_records", []))  # snapshot
        threshold = max(1, int(max_job_retries or self._coordinator_max_job_retries()))
        for r in records:
            source = str(getattr(r, "source_path", ""))
            if self._registry.is_in_flight(source):
                continue
            if not _worker_can_accept_record_library(r, accessible_library_ids):
                _log.debug(
                    "Skipping claim for worker %s on %s because library_id=%r is outside reported accessible libraries.",
                    worker_id[:32],
                    source,
                    _record_library_id(r),
                )
                continue
            if worker_id:
                blocked = getattr(self._registry, "claim_blocked_by_failure", None)
                if callable(blocked):
                    evidence = blocked(worker_id=worker_id, source_path=source, max_retries=threshold)
                    if evidence:
                        _log.debug(
                            "Skipping claim for worker %s on %s after %s consecutive %s failure(s).",
                            worker_id[:32],
                            source,
                            evidence.get("consecutive_count"),
                            evidence.get("reason_code"),
                        )
                        continue
            return r, self._snapshot_encode_config(worker_name, r)
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

    def _snapshot_encode_config(self, worker_name: str = "", record: object | None = None) -> dict:
        """Snapshot the encode-relevant config keys at claim time.

        ``WorkerConfigOverrides`` remains loadable for compatibility but is
        ignored by backend policy until worker lifecycle providers are real.
        """
        resolved = getattr(self._app, "resolved", None)
        if resolved is None or not hasattr(resolved, "config_data"):
            return {}
        return snapshot_encode_config(resolved.config_data, worker_name, record)

    def _remove_from_queue(self, source_path: str) -> None:
        """Remove a completed record from queue_records.

        Serialised against the coordinator queue refresher and the claim scan
        via the app queue lock so an in-place ``remove`` never races a
        reference swap from a periodic preview refresh.
        """
        with _app_queue_lock(self._app):
            records = getattr(self._app, "queue_records", None)
            if not records:
                return
            source_identity = normalize_source_identity(source_path)
            to_remove = [
                r for r in records
                if normalize_source_identity(getattr(r, "source_path", "")) == source_identity
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
        output_path: str = "",
        reason_code: str = "",
        reason: str = "",
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
                output_path=output_path,
                reason_code=reason_code,
                reason=reason,
                max_job_retries=self._coordinator_max_job_retries(),
            )
        )
