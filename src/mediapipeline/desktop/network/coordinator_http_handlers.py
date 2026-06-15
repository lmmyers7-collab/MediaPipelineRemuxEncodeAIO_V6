"""Coordinator HTTP endpoint handlers."""
from __future__ import annotations

import logging
import uuid
from datetime import datetime
from pathlib import Path

from mediapipeline.core.network.url_policy import redact_network_secret_text

from .coordinator_policy import RETRY_AFTER_ACTIVE_SECONDS as _RETRY_AFTER_ACTIVE_SECONDS
from .coordinator_queue import _coerce_record_estimated_size_gb, _coerce_record_priority
from .coordinator_queue import _scan_for_next_record_for_claim
from .failure_reasons import classify_failure_reason
from .identity import coerce_worker_name, is_valid_worker_id, sanitize_log_entry_fields
from .json_policy import loads_strict_json
from .library_roots import claim_library_fields_for_record
from .library_roots import libraries_response_from_config
from .protocol import ClaimResponse, DoneRequest, HeartbeatRequest, PingResponse, coerce_library_id_list
from .protocol import HeartbeatResponse, LogEntryRequest, WorkersResponse

_log = logging.getLogger("mediapipeline.desktop.network.coordinator")


class CoordinatorHttpHandlersMixin:
    def _http_ping(self, handler: _CoordHandler) -> None:
        """Handle auth-required ``GET /api/ping`` for connection diagnostics."""
        handler._send_json(
            PingResponse(
                server_time=datetime.now().astimezone().isoformat(timespec="seconds")
            ).to_dict()
        )

    def _http_libraries(self, handler: _CoordHandler, params: dict[str, str]) -> None:
        """Handle auth-required ``GET /api/libraries`` for worker auto-mapping."""
        _ = params
        try:
            payload = libraries_response_from_config(self._config())
        except Exception as exc:
            _log.exception("Failed to build /api/libraries response: %s", exc)
            handler._send_json({"error": "library roots unavailable"}, 500)
            return
        handler._send_json(payload)

    def _record_worker_seen_for_board(
        self,
        worker_id: str,
        worker_name: str,
        *,
        accessible_library_ids: list[str] | None = None,
    ) -> None:
        registry = getattr(self, "_registry", None)
        recorder = getattr(registry, "note_worker_seen", None)
        if not callable(recorder):
            return
        try:
            recorder(
                worker_id=worker_id,
                worker_name=worker_name,
                accessible_library_ids=accessible_library_ids,
            )
            registry.save(self._inflight_state_path())
        except Exception as exc:
            safe_exc = redact_network_secret_text(exc)
            _log.warning("Failed to persist worker-board presence for %s: %s", worker_id, safe_exc)
            logger = getattr(self, "_safe_log_cluster_event", None)
            if callable(logger):
                logger(
                    "worker-presence-save-failed",
                    level="WARN",
                    event="worker_presence_save_failed",
                    message=f"Failed to persist worker-board presence: {safe_exc}",
                    worker_id=worker_id,
                    worker_name=worker_name,
                    role="coordinator",
                )

    def _http_claim(self, handler: _CoordHandler, params: dict[str, str]) -> None:
        """Handle ``GET /api/claim?worker_id=<id>&worker_name=<name>``."""
        worker_id   = str(params.get("worker_id", "") or "").strip()
        worker_name = coerce_worker_name(params.get("worker_name", ""), worker_id)

        if not worker_id:
            _log.warning("Rejected /api/claim with missing worker_id")
            handler._send_json({"error": "worker_id query parameter is required"}, 400)
            return

        # N13 — bound and validate the worker identity before it reaches
        # the registry, where it would otherwise be persisted into
        # coordinator_inflight.json, cluster.log, and the per-worker
        # stats table. Garbage values (e.g. a 1 MB worker_id from a
        # buggy client) used to bloat all three.
        if not is_valid_worker_id(worker_id):
            _log.warning("Rejected /api/claim with invalid worker_id=%r", worker_id[:80])
            handler._send_json({
                "error": "worker_id must be 1..64 chars of [A-Za-z0-9._-]",
                "received_length": len(worker_id),
            }, 400)
            return

        accessible_library_ids = (
            coerce_library_id_list(params.get("accessible_library_ids"))
            if "accessible_library_ids" in params
            else None
        )
        self._record_worker_seen_for_board(
            worker_id,
            worker_name,
            accessible_library_ids=accessible_library_ids,
        )

        if not self._accepting_claims:
            handler._send_json(
                ClaimResponse.empty(
                    retry_after_seconds=self._compute_retry_after_seconds()
                ).to_dict()
            )
            return

        # Scan-and-claim must be atomic — hold the claim lock for the whole
        # find-then-claim sequence so two concurrent workers don't race.
        try:
            with self._claim_lock:
                record, encode_config = _scan_for_next_record_for_claim(
                    self,
                    worker_name,
                    worker_id=worker_id,
                    max_job_retries=self._coordinator_max_job_retries(),
                    accessible_library_ids=accessible_library_ids,
                )

                if record is None:
                    # W4 — choose a backoff hint that reflects whether other
                    # workers are still encoding (a job may free up soon) or
                    # the cluster is genuinely idle (back off harder).
                    handler._send_json(
                        ClaimResponse.empty(
                            retry_after_seconds=self._compute_retry_after_seconds()
                        ).to_dict()
                    )
                    return

                job_id      = str(uuid.uuid4())
                source_path = str(getattr(record, "source_path", ""))
                try:
                    config = self._config()
                except Exception:
                    config = {}
                library_id, relative_path = claim_library_fields_for_record(record, config)
                priority    = _coerce_record_priority(record)
                size_gb     = _coerce_record_estimated_size_gb(record, source_path)

                ok = self._registry.claim(
                    job_id=job_id,
                    worker_id=worker_id,
                    worker_name=worker_name,
                    source_path=source_path,
                    encode_config=encode_config,
                    priority=priority,
                    estimated_size_gb=size_gb,
                    accessible_library_ids=accessible_library_ids,
                )
        except Exception as exc:
            _log.exception("Failed to process /api/claim for worker %s: %s", worker_id, exc)
            handler._send_json({"error": "claim unavailable"}, 500)
            return

        if not ok:
            # Another thread claimed the same path between scan and claim.
            # The cluster is provably busy (someone just claimed under us)
            # so always emit the active hint here.
            handler._send_json(
                ClaimResponse.empty(
                    retry_after_seconds=_RETRY_AFTER_ACTIVE_SECONDS,
                ).to_dict()
            )
            return

        # Retry policy: if this file already has a failure record, tell the
        # worker not to re-queue it if the encode fails again.
        try:
            retry_on_failure = not self._source_has_prior_failure(source_path)
        except Exception as exc:
            _log.exception(
                "Failed to evaluate retry policy after claim %s for worker %s: %s",
                job_id[:8],
                worker_id,
                exc,
            )
            try:
                self._registry.unclaim(job_id, worker_id)
            except Exception as release_exc:
                _log.warning(
                    "Failed to release claim %s after retry-policy failure: %s",
                    job_id[:8],
                    release_exc,
                )
            handler._send_json({"error": "claim unavailable"}, 500)
            return

        try:
            self._registry.save(self._inflight_state_path())
        except Exception as exc:
            safe_exc = redact_network_secret_text(exc)
            _log.warning("Failed to save registry after claim: %s", safe_exc)
            try:
                rollback = getattr(self._registry, "rollback_claim", None)
                if callable(rollback):
                    rollback(job_id, worker_id)
                else:
                    self._registry.unclaim(job_id, worker_id)
            except Exception as release_exc:
                _log.warning(
                    "Failed to release claim %s after inflight save failure: %s",
                    job_id[:8],
                    redact_network_secret_text(release_exc),
                )
            self._safe_log_cluster_event(
                "inflight-save-failed",
                level="WARN",
                event="inflight_save_failed",
                message=f"Claim denied because in-flight registry could not be saved: {safe_exc}",
                worker_id=worker_id,
                worker_name=worker_name,
                role="coordinator",
                job_id=job_id,
                source_path=source_path,
            )
            handler._send_json({"error": "claim state unavailable"}, 503)
            return

        _log.info(
            "Claimed job %s (%s) for worker '%s' (retry=%s, %.2f GB, priority=%s)",
            job_id[:8], Path(source_path).name, worker_name,
            retry_on_failure, size_gb, priority,
        )
        self._safe_log_cluster_event(
            "claim-handed",
            level="INFO",
            event="claim_handed",
            message=f"{Path(source_path).name} (retry={retry_on_failure}, {size_gb:.2f} GB)",
            worker_id=worker_id,
            worker_name=worker_name,
            role="coordinator",
            job_id=job_id,
            source_path=source_path,
        )
        response = ClaimResponse(
            status            = "ok",
            job_id            = job_id,
            source_path       = source_path,
            library_id         = library_id,
            relative_path      = relative_path,
            priority          = priority,
            estimated_size_gb = size_gb,
            encode_config     = encode_config,
            retry_on_failure  = retry_on_failure,
        )
        handler._send_json(response.to_dict())

    def _http_done(self, handler: _CoordHandler, body: bytes) -> None:
        """Handle ``POST /api/done``."""
        try:
            data = loads_strict_json(body) if body else {}
            req  = DoneRequest.from_dict(data)
        except Exception as exc:
            _log.warning("Rejected /api/done with invalid JSON body: %s", exc)
            handler._send_json({"error": "Invalid JSON body"}, 400)
            return
        # N13 — same identity validation as /api/claim. Empty worker_id
        # is allowed here because crash-recovery callers may not know
        # their previous worker_id; ownership is still enforced
        # downstream by the registry's worker_id check (N2/N3).
        if req.worker_id and not is_valid_worker_id(req.worker_id):
            _log.warning("Rejected /api/done with invalid worker_id=%r", req.worker_id[:80])
            handler._send_json({"error": "invalid worker_id"}, 400)
            return
        if req.job_id and not is_valid_worker_id(req.job_id):
            _log.warning("Rejected /api/done with invalid job_id=%r", req.job_id[:80])
            handler._send_json({"error": "invalid job_id"}, 400)
            return

        if req.released:
            # Worker is shutting down cleanly — release without failure count.
            # N3 — pass worker_id so a foreign worker can't release a job
            # it doesn't own. Distinguish "not found" from "wrong worker".
            try:
                with self._registry._lock:
                    _existing = self._registry._jobs.get(req.job_id)
                    _existing_owner = _existing.worker_id if _existing else None
                job = self._registry.unclaim(req.job_id, req.worker_id)
            except Exception as exc:
                _log.exception("Failed to process /api/done release for job %s from worker %s: %s", req.job_id, req.worker_id, exc)
                handler._send_json({"error": "done state unavailable"}, 500)
                return
            if job is None:
                if _existing is None:
                    _log.warning(
                        "Release report for unknown job %s from worker '%s' "
                        "(likely already reclaimed or completed).",
                        req.job_id[:8], req.worker_id[:32],
                    )
                    self._safe_log_cluster_event(
                        "release-not-found",
                        level="WARN",
                        event="release_not_found",
                        message="Worker released a job that is no longer in-flight.",
                        worker_id=req.worker_id,
                        role="coordinator",
                        job_id=req.job_id,
                    )
                    handler._send_json({"status": "not_found", "job_id": req.job_id}, 404)
                else:
                    _log.warning(
                        "Rejected /api/done released=True from worker '%s' for job %s "
                        "owned by '%s'.",
                        req.worker_id[:32], req.job_id[:8], (_existing_owner or "?")[:32],
                    )
                    handler._send_json({"status": "forbidden", "reason": "worker_id does not match job owner", "job_id": req.job_id}, 403)
                return
            _log.info(
                "Worker '%s' released job %s (%s).",
                req.worker_id[:8], req.job_id[:8], Path(job.source_path).name,
            )
            try:
                self._registry.save(self._inflight_state_path())
            except Exception as exc:
                safe_exc = redact_network_secret_text(exc)
                _log.warning("Failed to save inflight state after worker release: %s", safe_exc)
                self._safe_log_cluster_event(
                    "inflight-save-failed",
                    level="WARN",
                    event="inflight_save_failed",
                    message=f"Failed to save in-flight registry after worker release: {safe_exc}",
                    worker_id=req.worker_id,
                    worker_name=job.worker_name,
                    role="coordinator",
                    job_id=req.job_id,
                    source_path=job.source_path,
                )
            handler._send_json({"status": "ok"})
            return

        # N2 — peek the job before mutation so we can return a precise
        # 403 vs 404 to the worker.  Without this peek a worker can't
        # tell whether its job_id was stale or whether the coordinator
        # is rejecting it for ownership reasons.
        try:
            with self._registry._lock:
                _existing = self._registry._jobs.get(req.job_id)
                _existing_owner = _existing.worker_id if _existing else None

            final_reason_code, final_reason = classify_failure_reason(
                success=bool(req.success),
                reason_code=req.reason_code,
                reason=req.reason,
                error_message=req.error_message,
                completion_status=req.completion_status,
                source_path=str(getattr(_existing, "source_path", "") or ""),
                output_path=req.output_path,
                route=req.route,
            )
            job = self._registry.complete(
                req.job_id,
                req.worker_id,
                success           = req.success,
                elapsed_seconds   = req.elapsed_seconds,
                output_size_bytes = req.output_size_bytes,
                reason_code       = final_reason_code,
                reason            = final_reason,
            )
        except Exception as exc:
            _log.exception("Failed to process /api/done completion for job %s from worker %s: %s", req.job_id, req.worker_id, exc)
            handler._send_json({"error": "done state unavailable"}, 500)
            return

        if job is None:
            if _existing is None:
                _log.warning(
                    "Done report for unknown job %s from worker '%s' "
                    "(likely already reclaimed or completed).",
                    req.job_id[:8], req.worker_id[:32],
                )
                self._safe_log_cluster_event(
                    "done-not-found",
                    level="WARN",
                    event="done_not_found",
                    message="Worker reported completion for a job that is no longer in-flight.",
                    worker_id=req.worker_id,
                    role="coordinator",
                    job_id=req.job_id,
                )
                handler._send_json({"status": "not_found", "job_id": req.job_id}, 404)
            else:
                _log.warning(
                    "Rejected /api/done from worker '%s' for job %s owned by '%s'.",
                    req.worker_id[:32], req.job_id[:8], (_existing_owner or "?")[:32],
                )
                self._safe_log_cluster_event(
                    "done-owner-mismatch",
                    level="WARN",
                    event="done_owner_mismatch",
                    message=f"Worker '{req.worker_id[:16]}' tried to close job owned by '{(_existing_owner or '?')[:16]}'",
                    worker_id=req.worker_id,
                    role="coordinator",
                    job_id=req.job_id,
                )
                handler._send_json({"status": "forbidden", "reason": "worker_id does not match job owner", "job_id": req.job_id}, 403)
            return

        # W1 — both paths (HTTP and local mark_done) share this helper so
        # cluster.log, queue-record removal, and the inflight-state save
        # all happen consistently regardless of dispatch source.
        self._emit_done_outcome(
            job               = job,
            success           = req.success,
            worker_id         = req.worker_id,
            elapsed_seconds   = req.elapsed_seconds,
            output_size_bytes = req.output_size_bytes,
            completion_status = req.completion_status or "",
            publish_state     = req.publish_state or "",
            publish_mode      = req.publish_mode or "",
            error_message     = req.error_message or "",
            queue_terminal    = bool(req.queue_terminal),
            retry_on_failure  = bool(req.retry_on_failure),
            output_path       = req.output_path or "",
            reason_code       = final_reason_code,
            reason            = final_reason,
        )

        handler._send_json({"status": "ok"})

    def _http_heartbeat(self, handler: _CoordHandler, body: bytes) -> None:
        """Handle ``POST /api/heartbeat``."""
        try:
            data = loads_strict_json(body) if body else {}
            req  = HeartbeatRequest.from_dict(data)
        except Exception as exc:
            _log.warning("Rejected /api/heartbeat with invalid JSON body: %s", exc)
            handler._send_json({"error": "Invalid JSON body"}, 400)
            return
        # N13 — bound identifiers, same rules as /api/claim.
        if req.worker_id and not is_valid_worker_id(req.worker_id):
            _log.warning("Rejected /api/heartbeat with invalid worker_id=%r", req.worker_id[:80])
            handler._send_json({"error": "invalid worker_id"}, 400)
            return
        if req.job_id and not is_valid_worker_id(req.job_id):
            _log.warning("Rejected /api/heartbeat with invalid job_id=%r", req.job_id[:80])
            handler._send_json({"error": "invalid job_id"}, 400)
            return

        try:
            result = self._registry.heartbeat(
                req.job_id,
                req.worker_id,
                progress_percent=req.progress_percent,
                current_stage=req.current_stage,
                accessible_library_ids=req.accessible_library_ids,
            )
        except Exception as exc:
            _log.exception("Failed to process /api/heartbeat for job %s from worker %s: %s", req.job_id, req.worker_id, exc)
            handler._send_json({"error": "heartbeat unavailable"}, 500)
            return
        if result == "reclaimed":
            # Tell the cluster log when a worker discovers its job was
            # taken away — most useful diagnostic for "why did my encode
            # die mid-way" surprises.
            self._safe_log_cluster_event(
                "heartbeat-reclaimed",
                level="WARN",
                event="heartbeat_reclaimed",
                message=(
                    f"Worker reported progress on a job that's no longer "
                    f"theirs (stage={req.current_stage}, {req.progress_percent:.1f}%)"
                ),
                worker_id=req.worker_id,
                role="coordinator",
                job_id=req.job_id,
            )
        handler._send_json(HeartbeatResponse(status=result).to_dict())

    def _http_workers(self, handler: _CoordHandler, params: dict[str, str]) -> None:
        """Handle ``GET /api/workers``."""
        try:
            entries   = self._registry.snapshot()
            remaining = len(getattr(self._app, "queue_records", []))
        except Exception as exc:
            _log.exception("Failed to build /api/workers response: %s", exc)
            handler._send_json({"error": "worker snapshot unavailable"}, 500)
            return
        # W6 — stamp the coordinator's wall clock so the UI can compute
        # heartbeat ages relative to the coordinator rather than the
        # local coordinator host.  Eliminates false "stale" highlights when the
        # operator's laptop clock drifts away from the coordinator's.
        response  = WorkersResponse(
            workers=entries,
            queue_remaining=remaining,
            jobs_completed_session=self._registry.session_completed,
            jobs_failed_session=self._registry.session_failed,
            coordinator_now=datetime.now().astimezone().isoformat(timespec="seconds"),
        )
        handler._send_json(response.to_dict())

    def _http_log(self, handler: _CoordHandler, body: bytes) -> None:
        """Handle ``POST /api/log`` — append a worker-emitted entry to cluster.log.

        Workers fire-and-forget POST these for every interesting lifecycle
        event so an operator can see what every machine in the cluster is
        doing in one chronological view.  Auth is the same bearer token as
        every other endpoint, so untrusted boxes can't pollute the log.
        """
        try:
            data = loads_strict_json(body) if body else {}
            entry = LogEntryRequest.from_dict(data)
        except Exception as exc:
            _log.warning("Rejected /api/log with invalid JSON body: %s", exc)
            handler._send_json({"error": "Invalid JSON body"}, 400)
            return
        if not entry.event:
            _log.warning("Rejected /api/log without required event field from worker_id=%r", entry.worker_id[:80])
            handler._send_json({"error": "event field is required"}, 400)
            return
        # N13 — bound identifiers and clip the message so a misbehaving
        # worker can't burn cluster.log space with multi-MB lines. The
        # cluster log line formatter already truncates display fields;
        # this just rejects pathological inputs early. Clip rather than
        # reject the message body — operators want partial diagnostics
        # over silent drops.
        raw_worker_id = entry.worker_id or ""
        raw_job_id = entry.job_id or ""
        raw_event = entry.event or ""
        raw_message = entry.message or ""
        sanitize_log_entry_fields(entry)
        if raw_worker_id and not entry.worker_id:
            _log.warning("Sanitized /api/log invalid worker_id=%r before appending cluster log entry.", raw_worker_id[:80])
        if raw_job_id and not entry.job_id:
            _log.warning("Sanitized /api/log invalid job_id=%r before appending cluster log entry.", raw_job_id[:80])
        if raw_event and entry.event != raw_event:
            _log.warning("Truncated /api/log event field from %d to %d characters.", len(raw_event), len(entry.event))
        if raw_message and entry.message != raw_message:
            _log.warning("Truncated /api/log message field from %d to %d characters.", len(raw_message), len(entry.message))
        entry.message = redact_network_secret_text(entry.message)
        # W7 — preserve the worker-supplied timestamp on a side-channel
        # attribute and rewrite ``entry.timestamp`` to the coordinator
        # receive time. The cluster log is keyed off entry.timestamp, so
        # this guarantees the file is monotonically ordered by the time
        # we observed each event regardless of worker clock skew. The
        # original worker_ts is rendered as a trailing tag by
        # :meth:`_format_cluster_log_line` for forensic visibility.
        coord_now = datetime.now().astimezone().isoformat(timespec="seconds")
        try:
            entry._worker_ts = entry.timestamp or ""    # type: ignore[attr-defined]
        except Exception as exc:
            _log.warning(
                "Could not preserve worker timestamp for /api/log event %s; using coordinator receive time only: %s",
                entry.event,
                exc,
            )
        entry.timestamp = coord_now
        try:
            self._append_cluster_log(entry)
        except Exception as exc:
            _log.warning("Unexpected cluster log append failure for event %s: %s", entry.event, exc)
        handler._send_json({"status": "ok"})
