from __future__ import annotations

import json
import logging
import os
from pathlib import Path
import tempfile
from typing import Any

from .diagnostics import diagnostic_preview as _worker_diagnostic_preview
from .dispatcher import ClaimedJob
from .json_policy import loads_strict_json
from .worker_done import build_crash_recovery_done_request
from .worker_parts.state_reports import save_active_worker_state, save_pending_worker_report


_log = logging.getLogger(__name__)
_worker_log = logging.getLogger("mediapipeline_desktop_app.network.worker")


def atomic_write_text(path: Path, text: str) -> None:
    """Write text via a same-directory temp file and atomic replace."""
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
        os.replace(tmp_path, path)
    except Exception:
        try:
            tmp_path.unlink(missing_ok=True)
        except OSError as cleanup_exc:
            _log.warning("Failed to remove temporary worker state file %s: %s", tmp_path, cleanup_exc)
        raise


def load_worker_state(path: Path) -> dict[str, Any]:
    payload = loads_strict_json(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("worker_state.json must contain an object")
    return payload


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


class WorkerStateMixin:
    def _crash_recover(self) -> None:
        """If ``worker_state.json`` exists, report the interrupted job as failed."""
        if not self._state_path.exists():
            return
        try:
            state = load_worker_state(self._state_path)
        except Exception as exc:
            _worker_log.warning("worker_state.json unreadable (%s) — removing.", exc)
            self._clear_worker_state()
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
        return save_pending_worker_report(
            self._state_path,
            job,
            payload,
            save_state=save_worker_state,
            notify_status=self._notify_status,
            safe_log_cluster_event=self._safe_log_cluster_event,
            log=_worker_log,
        )

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
