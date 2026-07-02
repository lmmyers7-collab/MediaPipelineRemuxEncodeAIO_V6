from __future__ import annotations

from pathlib import Path
import subprocess
import time
from typing import Any, Protocol
from collections.abc import Callable


class InfoWarningLogger(Protocol):
    def info(self, message: object, *args: object, **kwargs: object) -> None: ...

    def warning(self, message: object, *args: object, **kwargs: object) -> None: ...


UpdateActiveJobFunc = Callable[..., None]
LaunchLogSummaryFunc = Callable[[], str]
SpawnLogTailFunc = Callable[[Path | None], str]


def _update_active_job_record_best_effort(
    update_active_job_record: UpdateActiveJobFunc,
    proc: subprocess.Popen[Any],
    *,
    status: str,
    return_code: int | None,
    logger: InfoWarningLogger,
) -> None:
    try:
        update_active_job_record(proc, status=status, return_code=return_code)
    except Exception as exc:
        logger.warning("Failed to update ActiveJobs record to %s: %s", status, exc)


def verify_spawn_readiness(
    proc: subprocess.Popen[Any],
    command_line: str,
    *,
    ready_check_seconds: float,
    update_active_job_record: UpdateActiveJobFunc,
    launch_log_summary: LaunchLogSummaryFunc,
    spawn_log_tail: SpawnLogTailFunc,
    stdout_log: Path | None,
    stderr_log: Path | None,
    logger: InfoWarningLogger,
) -> None:
    time.sleep(ready_check_seconds)
    return_code = proc.poll()
    if return_code is None:
        _update_active_job_record_best_effort(
            update_active_job_record,
            proc,
            status="active",
            return_code=None,
            logger=logger,
        )
        return

    logs = launch_log_summary()
    if return_code == 0:
        _update_active_job_record_best_effort(
            update_active_job_record,
            proc,
            status="completed_immediate",
            return_code=return_code,
            logger=logger,
        )
        logger.info("Launched process exited quickly with code 0. Logs: %s", logs)
        return

    stdout_tail = spawn_log_tail(stdout_log)
    stderr_tail = spawn_log_tail(stderr_log)
    tail_parts = []
    if stderr_tail:
        tail_parts.append(f"stderr tail:\n{stderr_tail}")
    if stdout_tail:
        tail_parts.append(f"stdout tail:\n{stdout_tail}")
    tail_text = "\n".join(tail_parts).strip()
    detail = f" Logs: {logs}." if logs else ""
    if tail_text:
        detail = f"{detail}\n{tail_text}"
    _update_active_job_record_best_effort(
        update_active_job_record,
        proc,
        status="failed_immediate",
        return_code=return_code,
        logger=logger,
    )
    raise RuntimeError(f"Launched process exited immediately with code {return_code}.{detail}\nCommand: {command_line}")
