from __future__ import annotations

import contextlib
import os
import subprocess
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any


KillTreeCallback = Callable[[subprocess.Popen[Any], str], str]


@dataclass(frozen=True)
class CapturedCommandResult:
    args: Sequence[str]
    returncode: int | None
    stdout: str
    stderr: str
    timed_out: bool = False
    kill_message: str = ""

    @property
    def output_tail(self) -> str:
        text = (self.stderr.strip() or self.stdout.strip() or "").strip()
        return text if text else "<no output>"


def _cleanup_timed_out_process(
    proc: subprocess.Popen[Any],
    label: str,
    kill_tree: KillTreeCallback | None,
) -> str:
    messages: list[str] = []
    if kill_tree is not None:
        try:
            message = str(kill_tree(proc, label) or "").strip()
            if message:
                messages.append(message)
        except Exception as exc:
            messages.append(f"process tree kill failed: {exc}")

    if proc.poll() is None:
        try:
            proc.kill()
            messages.append("process killed")
        except Exception as exc:
            messages.append(f"process kill failed: {exc}")

    if proc.poll() is None:
        try:
            proc.terminate()
            messages.append("process terminated")
        except Exception as exc:
            messages.append(f"process terminate failed: {exc}")

    return "; ".join(messages) if messages else "process kill status unknown"


def run_capture(
    args: Sequence[str],
    *,
    timeout_seconds: float,
    cwd: str | Path | None = None,
    env: Mapping[str, str] | None = None,
    extra_popen_kwargs: Mapping[str, Any] | None = None,
    encoding: str | None = None,
    errors: str | None = None,
    hidden: bool = True,
    label: str = "process",
    kill_tree: KillTreeCallback | None = None,
) -> CapturedCommandResult:
    kwargs: dict[str, Any] = {
        "stdin": subprocess.DEVNULL,
        "stdout": subprocess.PIPE,
        "stderr": subprocess.PIPE,
        "text": True,
    }
    if encoding:
        kwargs["encoding"] = encoding
    if errors:
        kwargs["errors"] = errors
    if cwd is not None:
        kwargs["cwd"] = str(cwd)
    if env is not None:
        kwargs["env"] = dict(env)
    if os.name == "nt" and hidden:
        kwargs["creationflags"] = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    elif os.name != "nt":
        kwargs["start_new_session"] = True
    if extra_popen_kwargs:
        kwargs.update(dict(extra_popen_kwargs))

    proc: subprocess.Popen[Any] | None = None
    try:
        proc = subprocess.Popen(list(args), **kwargs)
        stdout, stderr = proc.communicate(timeout=timeout_seconds)
        return CapturedCommandResult(
            args=list(args),
            returncode=proc.returncode,
            stdout=stdout or "",
            stderr=stderr or "",
        )
    except subprocess.TimeoutExpired:
        kill_message = "process kill status unknown"
        if proc is not None:
            kill_message = _cleanup_timed_out_process(proc, label, kill_tree)
            with contextlib.suppress(Exception):
                stdout, stderr = proc.communicate(timeout=2)
                return CapturedCommandResult(
                    args=list(args),
                    returncode=proc.returncode,
                    stdout=stdout or "",
                    stderr=stderr or "",
                    timed_out=True,
                    kill_message=kill_message,
                )
        return CapturedCommandResult(
            args=list(args),
            returncode=None,
            stdout="",
            stderr="",
            timed_out=True,
            kill_message=kill_message,
        )
