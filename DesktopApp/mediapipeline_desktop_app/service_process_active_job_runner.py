from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Any

from .models import ResolvedPaths
from .service_process_active_jobs import (
    active_job_close_block_messages,
    active_job_pid_is_alive,
    active_job_record_path_for_proc,
    active_jobs_dir_for_resolved,
    reconcile_active_job_records,
    update_active_job_record,
    write_active_job_launch_record,
    write_active_job_payload,
)
from .service_runner_protocols import ActiveJobLaunchRecordServiceProtocol, ActiveJobLoggedServiceProtocol


def active_jobs_dir_for_service(_service: object, resolved: ResolvedPaths | None) -> Path | None:
    return active_jobs_dir_for_resolved(resolved)


def active_job_record_path_for_proc_for_service(_service: object, proc: subprocess.Popen[Any] | None) -> Path | None:
    return active_job_record_path_for_proc(proc)


def write_active_job_payload_for_service(_service: object, record_path: Path, payload: dict[str, Any]) -> None:
    write_active_job_payload(record_path, payload)


def write_active_job_launch_record_for_service(
    service: ActiveJobLaunchRecordServiceProtocol,
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
) -> Path | None:
    return write_active_job_launch_record(
        proc,
        resolved=resolved,
        job_kind=job_kind,
        mode=mode,
        command_line=command_line,
        args=args,
        launch_cwd=launch_cwd,
        show_console=show_console,
        metadata=metadata,
        stdout_log=service._last_spawn_stdout_log,
        stderr_log=service._last_spawn_stderr_log,
        app_pid=os.getpid(),
        logger=service.logger,
    )


def active_job_pid_is_alive_for_service(_service: object, pid: int, psutil_module: Any) -> bool | None:
    return active_job_pid_is_alive(pid, psutil_module)


def active_job_close_block_messages_for_service(
    _service: object,
    resolved: ResolvedPaths,
    *,
    max_items: int,
    psutil_module: Any,
) -> list[str]:
    return active_job_close_block_messages(resolved, max_items=max_items, psutil_module=psutil_module)


def reconcile_active_job_records_for_service(
    service: ActiveJobLoggedServiceProtocol,
    resolved: ResolvedPaths,
    *,
    max_items: int,
    psutil_module: Any,
) -> list[str]:
    return reconcile_active_job_records(
        resolved,
        max_items=max_items,
        psutil_module=psutil_module,
        logger=service.logger,
    )


def update_active_job_record_for_service(
    service: ActiveJobLoggedServiceProtocol,
    proc: subprocess.Popen[Any] | None,
    *,
    status: str | None,
    return_code: int | None,
) -> None:
    update_active_job_record(proc, status=status, return_code=return_code, app_pid=os.getpid(), logger=service.logger)
