from __future__ import annotations

from collections.abc import Callable
import contextlib
from dataclasses import dataclass, field
import os
from pathlib import Path
import signal
import subprocess
import threading
import time
from typing import Any, Protocol, cast

from mediapipeline.core.paths.contracts import ResolvedPaths


class WarningLogger(Protocol):
    def warning(self, message: object, *args: object, **kwargs: object) -> None: ...


UpdateActiveJobFunc = Callable[..., None]


_process_tree_cleanup_reconciliation_lock = threading.Lock()
_process_tree_cleanup_reconciliation_processes: dict[int, object] = {}
_PROCESS_TREE_CLEANUP_JOIN_TIMEOUT_SECONDS = 35.0


@dataclass
class _ProcessTreeCleanupAttempt:
    proc: object
    completed: threading.Event = field(default_factory=threading.Event)
    result: str | None = None
    error: BaseException | None = None


@dataclass(frozen=True)
class _ProcessTreeCleanupTerminalEvidence:
    status: str
    active_job_write_succeeded: bool


_process_tree_cleanup_attempts: dict[int, _ProcessTreeCleanupAttempt] = {}


def _mark_process_tree_cleanup_reconciliation_required(proc: object) -> None:
    """Retain identity-safe evidence that descendant exit remains unverified."""

    with _process_tree_cleanup_reconciliation_lock:
        _process_tree_cleanup_reconciliation_processes[id(proc)] = proc


def _process_tree_cleanup_reconciliation_required(proc: object) -> bool:
    with _process_tree_cleanup_reconciliation_lock:
        return _process_tree_cleanup_reconciliation_processes.get(id(proc)) is proc


def _clear_process_tree_cleanup_reconciliation_required(proc: object) -> bool:
    """Clear degraded evidence only for the exact process identity supplied."""

    with _process_tree_cleanup_reconciliation_lock:
        marked_proc = _process_tree_cleanup_reconciliation_processes.get(id(proc))
        if marked_proc is not proc:
            return False
        del _process_tree_cleanup_reconciliation_processes[id(proc)]
        return True


def _begin_process_tree_cleanup_attempt(proc: object) -> tuple[_ProcessTreeCleanupAttempt, bool]:
    with _process_tree_cleanup_reconciliation_lock:
        existing = _process_tree_cleanup_attempts.get(id(proc))
        if existing is not None and existing.proc is proc:
            return existing, False
        attempt = _ProcessTreeCleanupAttempt(proc=proc)
        _process_tree_cleanup_attempts[id(proc)] = attempt
    return attempt, True


def _finish_process_tree_cleanup_attempt(
    proc: object,
    attempt: _ProcessTreeCleanupAttempt,
    *,
    result: str | None,
    error: BaseException | None,
) -> None:
    with _process_tree_cleanup_reconciliation_lock:
        attempt.result = result
        attempt.error = error
        if _process_tree_cleanup_attempts.get(id(proc)) is attempt:
            del _process_tree_cleanup_attempts[id(proc)]
    attempt.completed.set()


def _wait_for_process_tree_cleanup_attempt(
    proc: object,
    *,
    timeout_seconds: float = _PROCESS_TREE_CLEANUP_JOIN_TIMEOUT_SECONDS,
) -> bool:
    """Wait for any exact-identity tree cleanup already deciding terminal evidence."""

    deadline = time.monotonic() + max(0.0, float(timeout_seconds))
    while True:
        with _process_tree_cleanup_reconciliation_lock:
            attempt = _process_tree_cleanup_attempts.get(id(proc))
            if attempt is None or attempt.proc is not proc:
                return True
            completed = attempt.completed
        remaining = deadline - time.monotonic()
        if remaining <= 0 or not completed.wait(timeout=remaining):
            _mark_process_tree_cleanup_reconciliation_required(proc)
            return False


def _process_tree_cleanup_attempt_in_progress(proc: object) -> bool:
    with _process_tree_cleanup_reconciliation_lock:
        attempt = _process_tree_cleanup_attempts.get(id(proc))
        return attempt is not None and attempt.proc is proc


def _set_process_tree_cleanup_terminal_evidence(
    proc: object,
    *,
    status: str,
    active_job_write_succeeded: bool,
) -> None:
    with contextlib.suppress(Exception):
        cast(Any, proc)._mediapipeline_tree_cleanup_terminal_evidence = (
            _ProcessTreeCleanupTerminalEvidence(
                status=status, active_job_write_succeeded=active_job_write_succeeded
            )
        )


def _process_tree_cleanup_terminal_evidence(
    proc: object,
) -> _ProcessTreeCleanupTerminalEvidence | None:
    evidence = getattr(proc, "_mediapipeline_tree_cleanup_terminal_evidence", None)
    return evidence if isinstance(evidence, _ProcessTreeCleanupTerminalEvidence) else None


def _record_process_tree_cleanup_active_job_status(
    proc: object,
    *,
    status: str,
    update_active_job_record: UpdateActiveJobFunc,
    logger: WarningLogger,
) -> bool:
    succeeded = False
    try:
        update_active_job_record(proc, status=status, return_code=getattr(proc, "returncode", None))
        succeeded = True
    except Exception as exc:
        logger.warning(
            "Process-tree cleanup was classified as %s for PID %s, but ActiveJobs evidence could not be updated: %s",
            status,
            getattr(proc, "pid", "?"),
            exc,
        )
    _set_process_tree_cleanup_terminal_evidence(
        proc,
        status=status,
        active_job_write_succeeded=succeeded,
    )
    return succeeded


def wait_for_process_exit(proc: subprocess.Popen[Any], timeout_seconds: float = 5.0) -> bool:
    try:
        proc.wait(timeout=timeout_seconds)
    except subprocess.TimeoutExpired:
        return proc.poll() is not None
    except Exception:
        return proc.poll() is not None
    return proc.poll() is not None


def fallback_kill_process_handle(
    proc: subprocess.Popen[Any],
    label: str,
    *,
    logger: WarningLogger,
    wait_for_exit: Callable[[subprocess.Popen[Any], float], bool] = wait_for_process_exit,
) -> None:
    if proc.poll() is not None:
        return
    logger.warning("Falling back to direct kill for %s process PID %s", label, proc.pid)
    with contextlib.suppress(Exception):
        proc.kill()
    wait_for_exit(proc, 3.0)
    if proc.poll() is None:
        with contextlib.suppress(Exception):
            proc.terminate()
    wait_for_exit(proc, 2.0)


def kill_psutil_process_tree(
    process: Any,
    label: str,
    *,
    psutil_module: Any,
    logger: WarningLogger,
    timeout_seconds: float = 5.0,
) -> None:
    if psutil_module is None:
        return
    try:
        children = process.children(recursive=True)
    except Exception:
        children = []
    targets = children + [process]
    for target in targets:
        with contextlib.suppress(Exception):
            if target.is_running():
                target.kill()
    gone, alive = psutil_module.wait_procs(targets, timeout=timeout_seconds) if targets else ([], [])
    _ = gone
    for target in alive:
        logger.warning("Process still alive after psutil kill for %s: PID %s", label, getattr(target, "pid", "?"))
        with contextlib.suppress(Exception):
            target.terminate()
    if alive:
        psutil_module.wait_procs(alive, timeout=2.0)


def process_text_contains_any(proc: Any, needles: list[str]) -> bool:
    try:
        pieces = [str(proc.exe() or "")]
    except Exception:
        pieces = []
    try:
        pieces.extend(str(part) for part in (proc.cmdline() or []))
    except Exception:
        pass
    text = " ".join(pieces).replace("/", "\\").casefold()
    return any(needle in text for needle in needles)


def _normalized_related_job_kinds(job_kinds: set[str] | None) -> set[str] | None:
    if job_kinds is None:
        return None
    normalized: set[str] = set()
    for item in job_kinds:
        key = str(item or "").strip().casefold()
        if key == "rerun":
            key = "rerun_csv"
        if key:
            normalized.add(key)
    return normalized


def related_pipeline_needles(resolved: ResolvedPaths, *, job_kinds: set[str] | None = None) -> list[str]:
    normalized_job_kinds = _normalized_related_job_kinds(job_kinds)
    script_paths: list[Path] = []
    if normalized_job_kinds is None or "pipeline" in normalized_job_kinds:
        script_paths.append(resolved.pipeline_path)
    if normalized_job_kinds is None or "audit" in normalized_job_kinds:
        script_paths.append(resolved.audit_script_path)
    if normalized_job_kinds is None or "rerun_csv" in normalized_job_kinds:
        script_paths.append(resolved.rerun_script_path)
    needles: list[str] = []
    for path in script_paths:
        try:
            resolved_path = path.resolve()
        except Exception:
            resolved_path = path
        for candidate in (path, resolved_path):
            text = str(candidate).replace("/", "\\").casefold()
            if text and text not in needles:
                needles.append(text)
    return needles


def find_related_pipeline_processes(
    resolved: ResolvedPaths,
    *,
    psutil_module: Any,
    current_pid: int | None = None,
    job_kinds: set[str] | None = None,
) -> list[Any]:
    """Find this bundle's pipeline/audit/rerun processes even if the app
    lost its original Popen handle after a restart.
    """
    if psutil_module is None:
        raise RuntimeError("psutil unavailable; related MediaPipeline process detection cannot be verified")
    needles = related_pipeline_needles(resolved, job_kinds=job_kinds)
    if not needles:
        return []

    own_pid = os.getpid() if current_pid is None else current_pid
    matches = []
    for proc in psutil_module.process_iter(["pid", "name"]):
        try:
            if int(proc.info.get("pid") or 0) == own_pid:
                continue
            name = str(proc.info.get("name") or "").casefold()
            if name not in {"pwsh.exe", "powershell.exe", "pwsh", "powershell"}:
                continue
            if process_text_contains_any(proc, needles):
                matches.append(proc)
        except Exception:
            continue
    return matches


def kill_related_pipeline_processes(
    resolved: ResolvedPaths,
    *,
    psutil_module: Any,
    logger: WarningLogger,
    job_kinds: set[str] | None = None,
) -> list[str]:
    messages: list[str] = []
    label = "related MediaPipeline"
    normalized_job_kinds = _normalized_related_job_kinds(job_kinds)
    if normalized_job_kinds is not None:
        label = f"related MediaPipeline {'/'.join(sorted(normalized_job_kinds))}"
    for proc in find_related_pipeline_processes(resolved, psutil_module=psutil_module, job_kinds=job_kinds):
        pid = getattr(proc, "pid", None)
        try:
            if not proc.is_running():
                continue
            logger.warning("Force-killing %s process tree for PID %s", label, pid)
            kill_psutil_process_tree(proc, label, psutil_module=psutil_module, logger=logger)
            if proc.is_running() and proc.status() != psutil_module.STATUS_ZOMBIE:
                raise RuntimeError(f"{label} process PID {pid} is still running after kill")
            messages.append(f"Force-killed {label} process tree (PID {pid}).")
        except Exception as exc:
            logger.warning("%s process kill did not complete cleanly for PID %s: %s", label, pid, exc)
            raise
    return messages


def _kill_running_process_tree(
    proc: subprocess.Popen[Any],
    label: str,
    *,
    psutil_module: Any,
    logger: WarningLogger,
    update_active_job_record: UpdateActiveJobFunc,
) -> str:
    pid = proc.pid
    logger.warning("Force-killing %s process tree for PID %s", label, pid)
    if os.name == "nt":
        taskkill_failure_reason = ""
        try:
            result = subprocess.run(
                ["taskkill", "/PID", str(pid), "/T", "/F"],
                capture_output=True,
                text=True,
                check=False,
                timeout=10,
            )
        except subprocess.TimeoutExpired as exc:
            result = None
            taskkill_detail = str(exc)
            taskkill_failure_reason = f"taskkill timed out: {taskkill_detail}"
            logger.warning("taskkill timed out for %s PID %s after 10s: %s", label, pid, taskkill_detail)
        if result is not None and result.returncode != 0:
            detail = (result.stderr or result.stdout or "").strip()
            taskkill_failure_reason = f"taskkill reported a failure with exit code {result.returncode}"
            if detail:
                taskkill_failure_reason = f"{taskkill_failure_reason}: {detail}"
            logger.warning("taskkill reported a failure for %s PID %s: %s", label, pid, detail)
        if taskkill_failure_reason:
            _mark_process_tree_cleanup_reconciliation_required(proc)
        if not wait_for_process_exit(proc, timeout_seconds=5.0):
            fallback_kill_process_handle(proc, label, logger=logger)
        if proc.poll() is None and psutil_module is not None:
            with contextlib.suppress(Exception):
                kill_psutil_process_tree(psutil_module.Process(pid), label, psutil_module=psutil_module, logger=logger)
        root_exit_verified = proc.poll() is not None
        if taskkill_failure_reason:
            _record_process_tree_cleanup_active_job_status(
                proc,
                status="kill_degraded",
                update_active_job_record=update_active_job_record,
                logger=logger,
            )
            root_detail = (
                "The root process exited, but descendant exit could not be verified."
                if root_exit_verified
                else "Root and descendant exit could not be verified."
            )
            return (
                f"Kill requested for {label} process tree (PID {pid}); {taskkill_failure_reason}. "
                f"{root_detail} Existing fallback attempts completed without blocking the control path."
            )
        if not root_exit_verified:
            raise RuntimeError(f"Unable to verify {label} process tree exited for PID {pid}.")
        _clear_process_tree_cleanup_reconciliation_required(proc)
        _record_process_tree_cleanup_active_job_status(
            proc,
            status="killed",
            update_active_job_record=update_active_job_record,
            logger=logger,
        )
        return f"Force-killed {label} process tree (PID {pid})."

    process_group_kill_issued = False
    process_group_absent = False
    process_group_id = os.getpgid(proc.pid)  # type: ignore[attr-defined]
    try:
        os.killpg(process_group_id, signal.SIGKILL)  # type: ignore[attr-defined]
        process_group_kill_issued = True
    except ProcessLookupError:
        process_group_absent = True
    root_exit_without_fallback = wait_for_process_exit(proc, timeout_seconds=5.0)
    if not root_exit_without_fallback:
        if not process_group_kill_issued:
            _mark_process_tree_cleanup_reconciliation_required(proc)
        fallback_kill_process_handle(proc, label, logger=logger)
    if proc.poll() is None:
        raise RuntimeError(f"Unable to verify {label} process exited for PID {pid}.")
    try:
        os.killpg(process_group_id, 0)  # type: ignore[attr-defined]
    except ProcessLookupError:
        process_group_absent = True
    except Exception as exc:
        process_group_absent = False
        logger.warning("Could not verify %s process group %s exited: %s", label, process_group_id, exc)
    else:
        process_group_absent = False
    process_tree_exit_verified = process_group_absent and (
        process_group_kill_issued or root_exit_without_fallback
    )
    if not process_tree_exit_verified:
        _mark_process_tree_cleanup_reconciliation_required(proc)
        _record_process_tree_cleanup_active_job_status(
            proc,
            status="kill_degraded",
            update_active_job_record=update_active_job_record,
            logger=logger,
        )
        return (
            f"Kill requested for {label} process tree (PID {pid}). The root process exited, but process group "
            "exit could not be verified."
        )
    _clear_process_tree_cleanup_reconciliation_required(proc)
    _record_process_tree_cleanup_active_job_status(
        proc,
        status="killed",
        update_active_job_record=update_active_job_record,
        logger=logger,
    )
    return f"Force-killed {label} process (PID {pid})."


def kill_process_tree(
    proc: subprocess.Popen[Any] | None,
    label: str,
    *,
    psutil_module: Any,
    logger: WarningLogger,
    update_active_job_record: UpdateActiveJobFunc,
) -> str:
    if proc is None:
        return f"No app-owned {label} process is running."
    attempt, owns_attempt = _begin_process_tree_cleanup_attempt(proc)
    if not owns_attempt:
        if not attempt.completed.wait(timeout=_PROCESS_TREE_CLEANUP_JOIN_TIMEOUT_SECONDS):
            _mark_process_tree_cleanup_reconciliation_required(proc)
            _record_process_tree_cleanup_active_job_status(
                proc,
                status="kill_degraded",
                update_active_job_record=update_active_job_record,
                logger=logger,
            )
            return (
                f"Kill requested for {label} process tree (PID {getattr(proc, 'pid', '?')}), but another exact-process "
                "cleanup attempt did not complete within the bounded reconciliation wait."
            )
        if attempt.error is not None:
            raise RuntimeError(
                f"The joined {label} process-tree cleanup attempt failed: {attempt.error}"
            ) from attempt.error
        if attempt.result is not None:
            return attempt.result
        _mark_process_tree_cleanup_reconciliation_required(proc)
        return (
            f"Kill requested for {label} process tree (PID {getattr(proc, 'pid', '?')}), but the joined cleanup "
            "attempt produced no conclusive result."
        )

    result: str | None = None
    error: BaseException | None = None
    try:
        if proc.poll() is not None:
            if _process_tree_cleanup_reconciliation_required(proc):
                result = (
                    f"App-owned {label} root process already exited, but descendant cleanup still requires "
                    "reconciliation."
                )
                return result
            terminal_evidence = _process_tree_cleanup_terminal_evidence(proc)
            if terminal_evidence is not None and terminal_evidence.status == "killed":
                result = f"App-owned {label} process-tree cleanup was already proven."
                return result
            try:
                update_active_job_record(proc, return_code=proc.returncode)
            except Exception as exc:
                logger.warning("Failed to record already-exited %s process PID %s: %s", label, proc.pid, exc)
            result = f"App-owned {label} process already exited."
            return result
        result = _kill_running_process_tree(
            proc,
            label,
            psutil_module=psutil_module,
            logger=logger,
            update_active_job_record=update_active_job_record,
        )
        return result
    except Exception as exc:
        error = exc
        _mark_process_tree_cleanup_reconciliation_required(proc)
        _record_process_tree_cleanup_active_job_status(
            proc,
            status="kill_degraded",
            update_active_job_record=update_active_job_record,
            logger=logger,
        )
        raise
    finally:
        _finish_process_tree_cleanup_attempt(proc, attempt, result=result, error=error)
