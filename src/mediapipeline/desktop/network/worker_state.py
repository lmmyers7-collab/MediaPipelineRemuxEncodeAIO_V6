from __future__ import annotations

import json
import logging
import os
from pathlib import Path
import tempfile
import time
from typing import Any

from .diagnostics import diagnostic_preview as _worker_diagnostic_preview
from .dispatcher import ClaimedJob
from .json_policy import loads_strict_json
from .worker_done import build_crash_recovery_done_request
from .worker_parts.state_reports import save_active_worker_state, save_pending_worker_report


_log = logging.getLogger(__name__)
_worker_log = logging.getLogger("mediapipeline.desktop.network.worker")


def _utc_stamp() -> str:
    return time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())


def worker_state_backup_path(path: Path) -> Path:
    return path.with_name(f"{path.name}.bak")


def worker_state_review_dir(path: Path) -> Path:
    return path.parent / "worker_state_review"


def pending_done_reports_dir(path: Path) -> Path:
    return path.parent / "pending_done_reports"


def pending_done_reports_review_dir(path: Path) -> Path:
    return path.parent / "pending_done_reports_review"


def _safe_name(value: str) -> str:
    text = "".join(ch if ch.isalnum() or ch in {"-", "_"} else "_" for ch in str(value or "").strip())
    return text[:80] or "unknown"


def quarantine_worker_state(path: Path, reason: str) -> Path | None:
    if not path.exists():
        return None
    review_dir = worker_state_review_dir(path)
    review_dir.mkdir(parents=True, exist_ok=True)
    target = review_dir / f"{path.name}.{_utc_stamp()}.{_safe_name(reason)}.json"
    os.replace(path, target)
    return target


def _load_worker_state_payload(path: Path) -> dict[str, Any]:
    payload = loads_strict_json(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("worker_state.json must contain an object")
    return payload


def _write_backup(path: Path) -> None:
    if not path.exists():
        return
    backup_path = worker_state_backup_path(path)
    tmp_path = backup_path.with_name(f".{backup_path.name}.{os.getpid()}.{time.monotonic_ns()}.tmp")
    try:
        tmp_path.write_text(path.read_text(encoding="utf-8"), encoding="utf-8", newline="")
        os.replace(tmp_path, backup_path)
    except Exception as exc:
        _log.warning("Failed to refresh worker_state backup %s: %s", backup_path, exc)
        try:
            tmp_path.unlink(missing_ok=True)
        except OSError:
            pass


def atomic_write_text(path: Path, text: str) -> None:
    """Write text via a same-directory temp file and atomic replace.

    The replace is retried with backoff on transient ``PermissionError``
    (antivirus/indexer briefly holding the destination on Windows),
    matching ``core.queue.file_io.atomic_write_text`` semantics.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(
        prefix=f".{path.name}.",
        suffix=".tmp",
        dir=path.parent,
        text=True,
    )
    tmp_path = Path(tmp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        _write_backup(path)
        delay_seconds = 0.05
        for attempt in range(7):
            try:
                os.replace(tmp_path, path)
                break
            except PermissionError:
                if attempt >= 6:
                    raise
                time.sleep(delay_seconds)
                delay_seconds = min(delay_seconds * 2, 1.0)
    except Exception:
        try:
            tmp_path.unlink(missing_ok=True)
        except OSError as cleanup_exc:
            _log.warning("Failed to remove temporary worker state file %s: %s", tmp_path, cleanup_exc)
        raise


def load_worker_state(path: Path) -> dict[str, Any]:
    try:
        return _load_worker_state_payload(path)
    except Exception:
        backup_path = worker_state_backup_path(path)
        if backup_path.exists():
            try:
                backup_state = _load_worker_state_payload(backup_path)
            except Exception as backup_exc:
                _log.warning("worker_state backup %s is not usable: %s", backup_path, backup_exc)
            else:
                quarantined = quarantine_worker_state(path, "corrupt")
                atomic_write_text(path, json.dumps(backup_state, indent=2, allow_nan=False) + "\n")
                _log.warning(
                    "Recovered worker_state.json from backup %s after quarantining corrupt state at %s.",
                    backup_path,
                    quarantined,
                )
                return backup_state
        quarantined = quarantine_worker_state(path, "corrupt")
        raise ValueError(f"worker_state.json was corrupt and quarantined at {quarantined}")


def save_worker_state(
    path: Path,
    *,
    job_id: str,
    source_path: str,
    pending_done_report: dict[str, Any] | None = None,
) -> None:
    payload: dict[str, Any] = {
        "job_id": job_id,
        "source_path": source_path,
    }
    if pending_done_report is not None:
        payload["pending_done_report"] = dict(pending_done_report)
    atomic_write_text(path, json.dumps(payload, indent=2, allow_nan=False) + "\n")


def clear_worker_state(path: Path) -> None:
    path.unlink(missing_ok=True)


def queue_pending_done_report(
    path: Path,
    *,
    job_id: str,
    source_path: str,
    pending_done_report: dict[str, Any] | None = None,
) -> Path:
    payload = dict(pending_done_report or {})
    payload.setdefault("job_id", job_id)
    payload.setdefault("source_path", source_path)
    payload["queued_utc"] = _utc_stamp()
    payload["schema_version"] = "worker_pending_done_report.v1"
    queue_dir = pending_done_reports_dir(path)
    queue_dir.mkdir(parents=True, exist_ok=True)
    target = queue_dir / f"{_utc_stamp()}.{_safe_name(job_id)}.{time.monotonic_ns()}.json"
    atomic_write_text(target, json.dumps(payload, indent=2, allow_nan=False) + "\n")
    return target


def iter_pending_done_report_files(path: Path) -> list[Path]:
    queue_dir = pending_done_reports_dir(path)
    if not queue_dir.exists():
        return []
    return sorted(item for item in queue_dir.glob("*.json") if item.is_file())


def load_pending_done_report(path: Path) -> dict[str, Any]:
    payload = loads_strict_json(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("pending done report must contain an object")
    return payload


def quarantine_pending_done_report(report_path: Path, reason: str, payload: dict[str, Any] | None = None) -> Path:
    review_dir = pending_done_reports_review_dir(report_path.parent.parent / "worker_state.json")
    review_dir.mkdir(parents=True, exist_ok=True)
    target = review_dir / f"{report_path.stem}.{_safe_name(reason)}.json"
    if payload is not None:
        payload = dict(payload)
        payload["quarantine_reason"] = reason
        atomic_write_text(target, json.dumps(payload, indent=2, allow_nan=False) + "\n")
        report_path.unlink(missing_ok=True)
    else:
        os.replace(report_path, target)
    return target


def _done_report_for_post(payload: dict[str, Any]) -> dict[str, Any]:
    report = dict(payload)
    for metadata_key in ("queued_utc", "schema_version", "quarantine_reason"):
        report.pop(metadata_key, None)
    return report


class WorkerStateMixin:
    def _quarantine_legacy_pending_report(self, payload: dict[str, Any], reason: str) -> None:
        queued_path = queue_pending_done_report(
            self._state_path,
            job_id=str(payload.get("job_id", "") or "unknown"),
            source_path=str(payload.get("source_path", "") or ""),
            pending_done_report=payload,
        )
        quarantine_pending_done_report(queued_path, reason, payload)

    def _drain_queued_pending_done_reports(self) -> bool:
        for report_path in iter_pending_done_report_files(self._state_path):
            try:
                payload = load_pending_done_report(report_path)
            except Exception as exc:
                quarantine_pending_done_report(report_path, f"unreadable_{_safe_name(str(exc))}")
                _worker_log.warning("Quarantined unreadable pending worker done report %s: %s", report_path, exc)
                continue
            payload.setdefault("worker_id", self._worker_id)
            job_id = str(payload.get("job_id", ""))
            post_payload = _done_report_for_post(payload)
            try:
                response = self._http_post("/api/done", post_payload)
            except Exception as exc:
                err_text = str(exc)
                if "HTTP 404 " in err_text or "HTTP Error 404:" in err_text:
                    quarantine_pending_done_report(report_path, "unknown_or_late_job", payload)
                    _worker_log.warning(
                        "Pending worker done report for job %s is unknown to coordinator; quarantined for review and continuing claims.",
                        job_id,
                    )
                    continue
                _worker_log.warning(
                    "Queued pending done-report delivery failed; holding new claims until retry: %s",
                    _worker_diagnostic_preview(exc),
                )
                return False
            status = str((response or {}).get("status", "ok") or "ok")
            if status not in {"ok", "late_recorded"}:
                quarantine_pending_done_report(report_path, f"unaccepted_{_safe_name(status)}", payload)
                _worker_log.warning(
                    "Pending worker done report for job %s returned status %r; quarantined for review and continuing claims.",
                    job_id,
                    status,
                )
                continue
            report_path.unlink(missing_ok=True)
            self._safe_log_cluster_event(
                "pending-done-recovered",
                level="WARN",
                event="pending_done_recovered",
                message=f"Delivered queued pending done report before claiming new work (job {job_id[:8]}).",
                job_id=job_id,
                source_path=str(payload.get("source_path", "")),
            )
        return True

    def _crash_recover(self) -> None:
        """If ``worker_state.json`` exists, report the interrupted job as failed."""
        if not self._state_path.exists():
            return
        try:
            state = load_worker_state(self._state_path)
        except Exception as exc:
            preview = _worker_diagnostic_preview(exc)
            if not self._state_path.exists():
                _worker_log.warning(
                    "worker_state.json unreadable (%s) and was quarantined; claims may resume because no recoverable active state remains.",
                    preview,
                )
                return
            self._worker_state_startup_error = preview
            _worker_log.warning(
                "worker_state.json unreadable (%s) - preserving and holding new claims.",
                preview,
            )
            return

        job_id = str(state.get("job_id", ""))
        if not job_id:
            _worker_log.warning("worker_state.json missing job_id — removing stale crash-recovery state.")
            self._clear_worker_state()
            return

        sp = str(state.get("source_path", ""))
        pending_done_report = state.get("pending_done_report")
        if isinstance(pending_done_report, dict) and str(pending_done_report.get("job_id", "") or "").strip():
            payload = dict(pending_done_report)
            payload.setdefault("worker_id", self._worker_id)
            _worker_log.warning(
                "Crash recovery: retrying pending done report for job_id=%s.",
                str(payload.get("job_id", "")),
            )
            try:
                self._http_post("/api/done", payload)
            except Exception as exc:
                _worker_log.warning("Crash recovery pending done-report failed: %s", _worker_diagnostic_preview(exc))
                return
            else:
                self._safe_log_cluster_event(
                    "pending-done-recovered",
                    level="WARN",
                    event="pending_done_recovered",
                    message=(
                        f"Retried pending done report after restart "
                        f"({Path(sp).name if sp else '(unknown source)'})"
                    ),
                    job_id=str(payload.get("job_id", "")),
                    source_path=sp,
                )
                self._clear_worker_state_after_accepted_report(
                    str(payload.get("job_id", "")),
                    "pending done recovery",
                )
                return

        if "pending_done_report" in state:
            _worker_log.warning(
                "Ignoring malformed pending done report in worker_state.json for job_id=%s; falling back to crash-failed recovery.",
                job_id,
            )

        _worker_log.warning(
            "Crash recovery: reporting job_id=%s as failed to coordinator.", job_id
        )
        try:
            self._http_post(
                "/api/done",
                build_crash_recovery_done_request(job_id, self._worker_id).to_dict(),
            )
        except Exception as exc:
            _worker_log.warning("Crash recovery done-report failed: %s", _worker_diagnostic_preview(exc))
            return
        else:
            # Only log success to the cluster — if the POST itself failed
            # the cluster log POST will fail too and we'll have nothing to
            # show.  The local Python log carries the failure.
            self._safe_log_cluster_event(
                "crash-recovered",
                level="WARN",
                event="crash_recovered",
                message=(
                    f"Reported orphaned job as failed after restart "
                    f"({Path(sp).name if sp else '(unknown source)'})"
                ),
                job_id=job_id,
                source_path=sp,
            )
            self._clear_worker_state_after_accepted_report(job_id, "crash recovery done")

    def _flush_pending_done_report(self) -> bool:
        """Deliver a persisted pending done report before claiming new work.

        Returns ``True`` when no pending report remains on disk (none
        existed, the coordinator accepted it, or the coordinator no
        longer knows the job).  Returns ``False`` while delivery keeps
        failing — the caller must not claim, because a new claim's state
        save would overwrite the single-slot report and lose the
        completed job's evidence.
        """
        state_path = getattr(self, "_state_path", None)
        if state_path is not None and not self._drain_queued_pending_done_reports():
            return False
        if state_path is None or not state_path.exists():
            return True
        try:
            state = load_worker_state(state_path)
        except Exception as exc:
            preview = _worker_diagnostic_preview(exc)
            if not state_path.exists():
                _worker_log.warning(
                    "worker_state.json is unreadable; holding new claims until quarantined state is reviewed: %s",
                    preview,
                )
            else:
                _worker_log.warning(
                    "worker_state.json is unreadable; holding new claims until the state file is recovered or cleared: %s",
                    preview,
                )
            notify_status = getattr(self, "_notify_status", None)
            if callable(notify_status):
                notify_status("⚠ Worker state unreadable; holding new claims until worker_state.json is repaired or cleared.")
            return False
        pending = state.get("pending_done_report")
        if not (isinstance(pending, dict) and str(pending.get("job_id", "") or "").strip()):
            active_job_id = str(state.get("job_id", "") or "").strip()
            if active_job_id:
                _worker_log.warning(
                    "worker_state.json still contains unresolved active job %s; holding new claims until crash recovery is accepted or the state is repaired.",
                    active_job_id,
                )
                notify_status = getattr(self, "_notify_status", None)
                if callable(notify_status):
                    notify_status("⚠ Worker crash recovery unresolved; holding new claims until worker_state.json is repaired or accepted.")
                return False
            return True
        payload = dict(pending)
        payload.setdefault("worker_id", self._worker_id)
        job_id = str(payload.get("job_id", ""))
        try:
            response = self._http_post("/api/done", payload)
        except Exception as exc:
            err_text = str(exc)
            if "HTTP 404 " in err_text or "HTTP Error 404:" in err_text:
                self._quarantine_legacy_pending_report(payload, "unknown_or_late_job")
                self._clear_worker_state()
                _worker_log.warning(
                    "Pending done report for job %s was not accepted by the coordinator; quarantined for review and continuing claims.",
                    job_id,
                )
                return True
            _worker_log.warning(
                "Pending done-report delivery failed; holding new claims until it lands: %s",
                _worker_diagnostic_preview(exc),
            )
            return False
        status = str((response or {}).get("status", "ok") or "ok")
        if status not in {"ok", "late_recorded"}:
            self._quarantine_legacy_pending_report(payload, f"unaccepted_{_safe_name(status)}")
            self._clear_worker_state()
            _worker_log.warning(
                "Pending done report for job %s returned unaccepted coordinator status %r; quarantined for review and continuing claims.",
                job_id,
                status,
            )
            return True
        self._safe_log_cluster_event(
            "pending-done-recovered",
            level="WARN",
            event="pending_done_recovered",
            message=f"Delivered pending done report before claiming new work (job {job_id[:8]}).",
            job_id=job_id,
            source_path=str(state.get("source_path", "")),
        )
        self._clear_worker_state_after_accepted_report(job_id, "pending done delivery")
        return True

    def _save_worker_state(self, job: ClaimedJob) -> None:
        """Write job identity to disk so crash recovery can report it on next start."""
        save_active_worker_state(
            self._state_path,
            job,
            save_state=save_worker_state,
            notify_status=self._notify_status,
            safe_log_cluster_event=self._safe_log_cluster_event,
            log=_worker_log,
        )

    def _save_pending_done_report(self, job: ClaimedJob, payload: dict[str, Any]) -> bool:
        """Persist an exact done/release payload for retry after restart."""
        saved = save_pending_worker_report(
            self._state_path,
            job,
            payload,
            save_state=queue_pending_done_report,
            notify_status=self._notify_status,
            safe_log_cluster_event=self._safe_log_cluster_event,
            log=_worker_log,
        )
        if saved:
            self._clear_worker_state()
        return saved

    def _clear_worker_state(self) -> bool:
        try:
            clear_worker_state(self._state_path)
        except Exception as exc:
            _worker_log.warning("Failed to clear worker_state.json after coordinator state transition: %s", exc)
            return False
        return True

    def _clear_worker_state_after_accepted_report(self, job_id: str, report_context: str) -> None:
        """Best-effort cleanup after the coordinator accepted a terminal report."""
        try:
            cleared = self._clear_worker_state()
        except Exception as exc:
            _worker_log.warning(
                "Coordinator accepted %s report for job %s, but worker_state cleanup failed; not saving a pending done report: %s",
                report_context,
                job_id,
                exc,
            )
            return
        if not cleared:
            _worker_log.warning(
                "Coordinator accepted %s report for job %s, but worker_state cleanup failed; not saving a pending done report.",
                report_context,
                job_id,
            )
