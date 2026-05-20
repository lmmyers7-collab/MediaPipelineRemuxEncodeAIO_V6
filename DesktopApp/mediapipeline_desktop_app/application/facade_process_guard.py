from __future__ import annotations

from ..models import ResolvedPaths, Snapshot
from .dto import CloseReadinessDto
from .facade_process_guard_policy import (
    audit_progress_indicates_active_work,
    close_readiness_fields,
    pipeline_progress_indicates_active_work,
)
from .schedule_stop_watcher import schedule_stop_watcher_state_mapping


class ProcessGuardFacadeMixin:
    """Active-work and close-readiness policy shared by process commands."""

    service: object

    def _acquire_process_launch_lock(self, action: str) -> tuple[object | None, str]:
        lock = getattr(self, "_process_launch_lock", None)
        if lock is None:
            return None, ""
        try:
            acquired = lock.acquire(blocking=False)
        except Exception as exc:
            self._log_close_guard_exception("Process launch lock acquisition failed", exc)
            return None, f"{action} blocked because the process launch lock could not be verified: {exc}"
        if not acquired:
            return None, f"{action} blocked because another process launch command is already in progress."
        return lock, ""

    def _release_process_launch_lock(self, lock: object | None) -> None:
        if lock is None:
            return
        try:
            lock.release()  # type: ignore[attr-defined]
        except Exception as exc:
            self._log_close_guard_exception("Process launch lock release failed", exc)

    def get_close_readiness(self, resolved: ResolvedPaths, snapshot: Snapshot | None = None) -> CloseReadinessDto:
        state = self._pipeline_state(snapshot) if snapshot is not None else "unknown"
        block_message = self._active_work_block_message(resolved, "Shell close")
        return CloseReadinessDto(
            **close_readiness_fields(
                state=state,
                snapshot_available=snapshot is not None,
                block_message=block_message,
                continuous_watcher=self._schedule_stop_watcher_state_mapping(),
            )
        )

    def _active_work_block_message(self, resolved: ResolvedPaths, action: str) -> str:
        related_method = getattr(self.service, "find_related_pipeline_processes", None)
        if callable(related_method):
            try:
                related_processes = related_method(resolved)
            except Exception as exc:
                self._log_close_guard_exception("Related process close-readiness verification failed", exc)
                return f"{action} blocked because related MediaPipeline processes could not be verified: {exc}"
            if related_processes:
                pids = sorted(str(getattr(proc, "pid", "?")) for proc in related_processes if str(getattr(proc, "pid", "?")).strip())
                pid_text = ", ".join(pids) if pids else "unknown"
                return f"{action} blocked because MediaPipeline process PID(s) {pid_text} are still running from this bundle."
        watcher_block = self._schedule_stop_watcher_close_block_message(action)
        if watcher_block:
            return watcher_block
        active_job_blocks = self._active_job_block_messages(resolved)
        if active_job_blocks:
            shown = "; ".join(active_job_blocks[:3])
            suffix = "" if len(active_job_blocks) <= 3 else f"; and {len(active_job_blocks) - 3} more"
            return f"{action} blocked because ActiveJobs still reports active work: {shown}{suffix}"
        progress_block = self._progress_block_message(resolved, action)
        if progress_block:
            return progress_block
        audit_block = self._audit_progress_block_message(resolved, action)
        if audit_block:
            return audit_block
        return ""

    def _active_job_block_messages(self, resolved: ResolvedPaths) -> list[str]:
        block_messages = getattr(self.service, "active_job_close_block_messages", None)
        if not callable(block_messages):
            return []
        try:
            return [str(message) for message in block_messages(resolved) if str(message).strip()]
        except Exception as exc:
            self._log_close_guard_exception("ActiveJobs close-readiness verification failed", exc)
            return ["ActiveJobs state could not be verified."]

    def _progress_block_message(self, resolved: ResolvedPaths, action: str) -> str:
        read_progress = getattr(self.service, "read_progress", None)
        is_stale = getattr(self.service, "is_progress_stale", None)
        if not callable(read_progress) or not callable(is_stale):
            return ""
        try:
            progress = read_progress(resolved)
            if not progress or is_stale(progress):
                return ""
        except Exception as exc:
            self._log_close_guard_exception("Pipeline progress close-readiness verification failed", exc)
            return f"{action} blocked because pipeline progress could not be verified: {exc}"
        if pipeline_progress_indicates_active_work(progress):
            return f"{action} blocked because fresh pipeline progress indicates active work."
        return ""

    def _audit_progress_block_message(self, resolved: ResolvedPaths, action: str) -> str:
        read_progress = getattr(self.service, "read_audit_progress", None)
        is_stale = getattr(self.service, "is_audit_progress_stale", None)
        if not callable(read_progress) or not callable(is_stale):
            return ""
        try:
            audit_progress = read_progress(resolved)
            if not audit_progress or is_stale(audit_progress):
                return ""
        except Exception as exc:
            self._log_close_guard_exception("Audit progress close-readiness verification failed", exc)
            return f"{action} blocked because audit progress could not be verified: {exc}"
        if audit_progress_indicates_active_work(audit_progress):
            return f"{action} blocked because fresh audit progress indicates active work."
        return ""

    def _schedule_stop_watcher_close_block_message(self, action: str) -> str:
        state = self._schedule_stop_watcher_state_mapping()
        status = str(state.get("status", "") or "").strip().casefold()
        if status == "error":
            error = str(state.get("error") or "unknown error")
            self._log_close_guard_exception("Schedule-stop watcher close-readiness verification failed", RuntimeError(error))
            return f"{action} blocked because backend schedule-stop watcher state could not be verified: {error}"
        if status != "armed":
            return ""
        pid = int(state.get("pid", 0) or 0)
        deadline = str(state.get("deadline", "") or "").strip()
        pid_text = f" PID {pid}" if pid > 0 else ""
        deadline_text = f" until {deadline}" if deadline else ""
        if pid_text:
            return f"{action} blocked because the backend schedule-stop watcher is armed for{pid_text}{deadline_text}."
        return f"{action} blocked because the backend schedule-stop watcher is armed{deadline_text}."

    def _schedule_stop_watcher_state_mapping(self) -> dict[str, object]:
        return schedule_stop_watcher_state_mapping(getattr(self, "_schedule_stop_watcher", None))

    def _log_close_guard_exception(self, message: str, exc: Exception) -> None:
        logger = getattr(self.service, "logger", None)
        if logger is None:
            return
        try:
            logger.warning("%s: %s", message, exc, exc_info=True)
        except Exception:
            return

__all__ = [
    "ProcessGuardFacadeMixin",
]
