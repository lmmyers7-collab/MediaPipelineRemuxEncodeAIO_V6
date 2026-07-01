from __future__ import annotations

from collections.abc import Callable
import contextlib
import os
from pathlib import Path
import signal
import subprocess
from typing import Any, Protocol

from mediapipeline.core.paths.contracts import ResolvedPaths


class WarningLogger(Protocol):
    def warning(self, message: object, *args: object, **kwargs: object) -> None: ...


UpdateActiveJobFunc = Callable[..., None]


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

    pid = proc.pid
    if proc.poll() is not None:
        update_active_job_record(proc, return_code=proc.returncode)
        return f"App-owned {label} process already exited."

    logger.warning("Force-killing %s process tree for PID %s", label, pid)
    if os.name == "nt":
        taskkill_timed_out = False
        taskkill_detail = ""
        try:
            result = subprocess.run(
                ["taskkill", "/PID", str(pid), "/T", "/F"],
                capture_output=True,
                text=True,
                check=False,
                timeout=10,
            )
            taskkill_detail = (result.stderr or result.stdout or "").strip()
        except subprocess.TimeoutExpired as exc:
            result = None
            taskkill_timed_out = True
            taskkill_detail = str(exc)
            logger.warning("taskkill timed out for %s PID %s after 10s: %s", label, pid, taskkill_detail)
        if result is not None and result.returncode != 0 and proc.poll() is None:
            detail = (result.stderr or result.stdout or "").strip()
            logger.warning("taskkill reported a failure for %s PID %s: %s", label, pid, detail)
        if not wait_for_process_exit(proc, timeout_seconds=5.0):
            fallback_kill_process_handle(proc, label, logger=logger)
        if proc.poll() is None and psutil_module is not None:
            with contextlib.suppress(Exception):
                kill_psutil_process_tree(psutil_module.Process(pid), label, psutil_module=psutil_module, logger=logger)
        if proc.poll() is None:
            if taskkill_timed_out:
                update_active_job_record(proc, status="kill_degraded", return_code=proc.returncode)
                return (
                    f"Kill requested for {label} process tree (PID {pid}), but taskkill timed out "
                    "and exit could not be verified. Existing fallback attempts completed without "
                    f"blocking the control path. Detail: {taskkill_detail}"
                )
            raise RuntimeError(f"Unable to verify {label} process tree exited for PID {pid}.")
        update_active_job_record(proc, status="killed", return_code=proc.returncode)
        return f"Force-killed {label} process tree (PID {pid})."

    try:
        os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
    except ProcessLookupError:
        pass
    if not wait_for_process_exit(proc, timeout_seconds=5.0):
        fallback_kill_process_handle(proc, label, logger=logger)
    if proc.poll() is None:
        raise RuntimeError(f"Unable to verify {label} process exited for PID {pid}.")
    update_active_job_record(proc, status="killed", return_code=proc.returncode)
    return f"Force-killed {label} process (PID {pid})."
