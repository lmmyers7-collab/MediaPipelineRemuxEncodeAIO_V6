from __future__ import annotations

from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any, Protocol


class WarningLogger(Protocol):
    def warning(self, message: object, *args: object, **kwargs: object) -> None: ...


ControlFlagSpec = tuple[str, Path | None, bool]


def _related_process_pid_text(related_processes: Sequence[Any]) -> str:
    pids = sorted(
        str(getattr(proc, "pid", "?"))
        for proc in related_processes
        if str(getattr(proc, "pid", "?")).strip()
    )
    return ", ".join(pids) if pids else "unknown"


def prepare_stale_progress_cleanup(
    *,
    progress_label: str,
    is_stale: bool,
    find_related_processes: Callable[[], Sequence[Any]],
    clear_artifacts: Callable[[], list[str]],
    logger: WarningLogger,
) -> list[str]:
    if not is_stale:
        return []

    related_processes = list(find_related_processes())
    if related_processes:
        pid_text = _related_process_pid_text(related_processes)
        message = f"Stale {progress_label} progress was not cleared because related MediaPipeline process PID(s) {pid_text} are still running."
        logger.warning(message)
        return [message]

    removed = clear_artifacts()
    if not removed:
        return []
    message = f"Cleared stale {progress_label} progress before launch: {', '.join(removed)}."
    logger.warning(message)
    return [message]


def prepare_control_flags_for_launch(
    specs: Sequence[ControlFlagSpec],
    *,
    stale_after_seconds: float,
    read_payload: Callable[[Path], dict[str, Any] | None],
    age_seconds: Callable[[Path, dict[str, Any] | None], float | None],
    remove_flag: Callable[[Path, str], None],
    logger: WarningLogger,
) -> list[str]:
    messages: list[str] = []
    for label, flag_path, always_remove in specs:
        if flag_path is None or not flag_path.exists():
            continue
        payload = read_payload(flag_path)
        current_age_seconds = age_seconds(flag_path, payload)
        stale = current_age_seconds is not None and current_age_seconds > stale_after_seconds
        if always_remove or stale:
            reason = "pre-existing" if always_remove else "stale"
            remove_flag(flag_path, label)
            message = f"Removed {reason} {label.lower()} flag before launch."
            logger.warning(message)
            messages.append(message)
        else:
            message = f"Existing {label.lower()} flag remains active for launch."
            logger.warning(message)
            messages.append(message)
    return messages
