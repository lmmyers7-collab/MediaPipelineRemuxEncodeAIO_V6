from __future__ import annotations

from pathlib import Path
import subprocess
import threading
import time
from typing import Any, Protocol
from collections.abc import Mapping

from mediapipeline.core.paths.contracts import ResolvedPaths
from mediapipeline.core.processes.constants import ACTIVE_JOB_HEARTBEAT_SECONDS

from .spawn import (
    build_spawn_command_line,
    build_spawn_kwargs,
    build_spawn_log_paths,
    hidden_creationflags,
    launch_cwd_for_roots,
)


class InfoWarningLogger(Protocol):
    def info(self, message: object, *args: object, **kwargs: object) -> None: ...

    def warning(self, message: object, *args: object, **kwargs: object) -> None: ...


class ProcessSpawnService(Protocol):
    app_root: Path
    workspace_root: Path
    logger: InfoWarningLogger
    _last_spawn_stdout_log: Path | None
    _last_spawn_stderr_log: Path | None

    def _build_launch_environment(self) -> Mapping[str, str]: ...

    def _write_active_job_launch_record(
        self,
        proc: subprocess.Popen[Any],
        *,
        resolved: ResolvedPaths | None,
        job_kind: str,
        mode: str,
        command_line: str,
        args: list[str],
        launch_cwd: Path,
        show_console: bool,
        metadata: dict[str, Any],
    ) -> Path | None: ...

    def _verify_spawn_readiness(self, proc: subprocess.Popen[Any], command_line: str) -> None: ...


def _stop_started_process_after_launch_failure(
    service: ProcessSpawnService,
    proc: subprocess.Popen[Any],
    job_kind: str,
) -> None:
    if proc.poll() is not None:
        return
    label = f"{job_kind} launch failure"
    kill_tree = getattr(service, "kill_process_tree", None)
    try:
        if callable(kill_tree):
            kill_tree(proc, label)
            return
        proc.kill()
        proc.wait(timeout=5.0)
    except Exception as exc:
        service.logger.warning("Failed to stop %s process after launch failure: %s", job_kind, exc)


def _start_active_job_completion_watcher(
    service: ProcessSpawnService,
    proc: subprocess.Popen[Any],
    job_kind: str,
    *,
    resolved: ResolvedPaths | None = None,
    metadata: Mapping[str, Any] | None = None,
) -> bool:
    update_active_job = getattr(service, "update_active_job_record", None)
    wait_for_exit = getattr(proc, "wait", None)
    if not callable(update_active_job) or not callable(wait_for_exit):
        return False
    unregister_active_process = getattr(service, "_unregister_active_spawned_process", None)
    is_active_process_registered = getattr(service, "_active_spawned_process_is_registered", None)

    def _watch() -> None:
        return_code: int | None = None
        try:
            return_code = wait_for_exit()
            if callable(is_active_process_registered) and not is_active_process_registered(proc):
                return
            update_active_job(proc, return_code=return_code)
        except Exception as exc:
            service.logger.warning("Failed to update %s ActiveJobs record after process exit: %s", job_kind, exc)
        else:
            sync_after_exit = getattr(service, "sync_audit_sources_after_process_exit", None)
            if callable(sync_after_exit):
                try:
                    sync_after_exit(
                        proc,
                        resolved=resolved,
                        job_kind=job_kind,
                        return_code=return_code,
                        metadata=dict(metadata or {}),
                    )
                except Exception as exc:
                    service.logger.warning("Failed to sync %s post-exit state: %s", job_kind, exc)
        finally:
            if callable(unregister_active_process):
                unregister_active_process(proc)

    watcher = threading.Thread(
        target=_watch,
        name=f"mediapipeline-{job_kind}-active-job-completion",
        daemon=True,
    )
    watcher.start()
    return True


def _start_active_job_heartbeat_watcher(
    service: ProcessSpawnService,
    proc: subprocess.Popen[Any],
    job_kind: str,
    *,
    interval_seconds: float = ACTIVE_JOB_HEARTBEAT_SECONDS,
) -> bool:
    update_active_job = getattr(service, "update_active_job_record", None)
    poll = getattr(proc, "poll", None)
    if not callable(update_active_job) or not callable(poll):
        return False
    is_active_process_registered = getattr(service, "_active_spawned_process_is_registered", None)

    def _heartbeat() -> None:
        while True:
            time.sleep(max(1.0, float(interval_seconds)))
            if callable(is_active_process_registered) and not is_active_process_registered(proc):
                return
            try:
                if poll() is not None:
                    return
                update_active_job(proc, status="active", return_code=None)
            except Exception as exc:
                service.logger.warning("Failed to heartbeat %s ActiveJobs record: %s", job_kind, exc)

    watcher = threading.Thread(
        target=_heartbeat,
        name=f"mediapipeline-{job_kind}-active-job-heartbeat",
        daemon=True,
    )
    watcher.start()
    return True


def spawn_process_for_service(
    service: ProcessSpawnService,
    args: list[str],
    show_console: bool,
    *,
    resolved: ResolvedPaths | None = None,
    job_kind: str = "process",
    mode: str = "",
    metadata: dict[str, Any] | None = None,
) -> subprocess.Popen[Any]:
    creationflags = hidden_creationflags(show_console)
    command_line = build_spawn_command_line(args)
    service.logger.info("Launching: %s", command_line)
    log_paths = build_spawn_log_paths(service.app_root)
    stdout_log = log_paths.stdout_log
    stderr_log = log_paths.stderr_log
    stdout_handle = stdout_log.open("ab")
    stderr_handle = stderr_log.open("ab")
    service._last_spawn_stdout_log = stdout_log
    service._last_spawn_stderr_log = stderr_log
    launch_cwd = launch_cwd_for_roots(service.app_root, service.workspace_root)
    kwargs = build_spawn_kwargs(
        launch_cwd=launch_cwd,
        environment=dict(service._build_launch_environment()),
        stdout_handle=stdout_handle,
        stderr_handle=stderr_handle,
        creationflags=creationflags,
    )
    try:
        proc = subprocess.Popen(args, stdin=subprocess.DEVNULL, **kwargs)
        try:
            service._write_active_job_launch_record(
                proc,
                resolved=resolved,
                job_kind=job_kind,
                mode=mode,
                command_line=command_line,
                args=args,
                launch_cwd=launch_cwd,
                show_console=show_console,
                metadata=metadata or {},
            )
            service._verify_spawn_readiness(proc, command_line)
            register_active_process = getattr(service, "_register_active_spawned_process", None)
            if callable(register_active_process):
                register_active_process(proc, job_kind)
            _start_active_job_heartbeat_watcher(service, proc, job_kind)
            if not _start_active_job_completion_watcher(
                service,
                proc,
                job_kind,
                resolved=resolved,
                metadata=metadata or {},
            ):
                unregister_active_process = getattr(service, "_unregister_active_spawned_process", None)
                if callable(unregister_active_process):
                    unregister_active_process(proc)
        except Exception:
            _stop_started_process_after_launch_failure(service, proc, job_kind)
            raise
        return proc
    finally:
        stdout_handle.close()
        stderr_handle.close()
