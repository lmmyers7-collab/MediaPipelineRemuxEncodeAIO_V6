from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import os
from pathlib import Path
import shlex
import subprocess
from typing import Any


@dataclass(frozen=True)
class SpawnLogPaths:
    stdout_log: Path
    stderr_log: Path


def build_spawn_command_line(args: list[str]) -> str:
    if os.name == "nt":
        return subprocess.list2cmdline(args)
    return " ".join(shlex.quote(str(arg)) for arg in args)


def hidden_creationflags(show_console: bool) -> int:
    if os.name == "nt" and not show_console:
        return getattr(subprocess, "CREATE_NO_WINDOW", 0)
    return 0


def build_spawn_log_paths(app_root: Path, *, app_pid: int | None = None, now: datetime | None = None) -> SpawnLogPaths:
    run_log_dir = app_root / "RunLogs"
    run_log_dir.mkdir(parents=True, exist_ok=True)
    stamp = (now or datetime.now()).strftime("%Y%m%d_%H%M%S_%f")
    pid = os.getpid() if app_pid is None else app_pid
    base = f"run_{stamp}_{pid}"
    return SpawnLogPaths(
        stdout_log=run_log_dir / f"{base}.stdout.log",
        stderr_log=run_log_dir / f"{base}.stderr.log",
    )


def launch_cwd_for_roots(app_root: Path, workspace_root: Path) -> Path:
    return workspace_root if workspace_root.exists() else app_root


def build_spawn_kwargs(
    *,
    launch_cwd: Path,
    environment: dict[str, str],
    stdout_handle: Any,
    stderr_handle: Any,
    creationflags: int,
) -> dict[str, Any]:
    kwargs: dict[str, Any] = {
        "cwd": str(launch_cwd),
        "env": environment,
        "stdout": stdout_handle,
        "stderr": stderr_handle,
    }
    if os.name == "nt":
        kwargs["creationflags"] = creationflags
    else:
        kwargs["start_new_session"] = True
    return kwargs
