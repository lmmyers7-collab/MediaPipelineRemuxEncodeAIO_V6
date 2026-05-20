from __future__ import annotations

from pathlib import Path

from .service_constants import PROCESS_LAUNCH_ERROR_TAIL_LINES
from .service_utils import _tail_text_file


def spawn_log_tail(path: Path | None, *, line_count: int = PROCESS_LAUNCH_ERROR_TAIL_LINES) -> str:
    if path is None or not path.exists():
        return ""
    try:
        return _tail_text_file(path, line_count=line_count)
    except Exception:
        return ""


def launch_log_summary(stdout_log: Path | None, stderr_log: Path | None) -> str:
    pieces: list[str] = []
    if stdout_log:
        pieces.append(f"stdout: {stdout_log}")
    if stderr_log:
        pieces.append(f"stderr: {stderr_log}")
    return " | ".join(pieces)


def launch_log_tail_summary(stdout_log: Path | None, stderr_log: Path | None, *, line_count: int = 12) -> str:
    pieces: list[str] = []
    stderr_tail = spawn_log_tail(stderr_log)
    stdout_tail = spawn_log_tail(stdout_log)
    if stderr_tail:
        pieces.append("stderr tail:\n" + "\n".join(stderr_tail.splitlines()[-line_count:]))
    if stdout_tail:
        pieces.append("stdout tail:\n" + "\n".join(stdout_tail.splitlines()[-line_count:]))
    return "\n\n".join(pieces)
