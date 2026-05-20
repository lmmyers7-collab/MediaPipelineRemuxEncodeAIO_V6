from __future__ import annotations

import time
from pathlib import Path
from typing import Callable

from .models import ResolvedPaths


def queue_dry_run_temp_snapshot_path(snapshot_path: Path, request_id: str) -> Path:
    return snapshot_path.with_name(f"{snapshot_path.stem}.{request_id}.dryrun.json")


def build_queue_dry_run_command(
    resolved: ResolvedPaths,
    *,
    temp_snapshot_path: Path,
    powershell_host: str | None = None,
) -> list[str]:
    pwsh = powershell_host or resolved.powershell_host or "pwsh"
    return [
        pwsh,
        "-NoProfile",
        "-NonInteractive",
        "-File",
        str(resolved.pipeline_path),
        "-EmitQueuePlan",
        "-QueuePlanOutPath",
        str(temp_snapshot_path),
        "-ConfigPath",
        str(resolved.config_path),
    ]


def queue_snapshot_file_is_fresh(
    snapshot_path: Path,
    *,
    fresh_seconds: float,
    now: Callable[[], float] = time.time,
) -> bool:
    try:
        age = now() - snapshot_path.stat().st_mtime
    except OSError:
        return False
    return age <= fresh_seconds


def format_queue_plan_source_status(
    *,
    produced_at: object,
    request_id: str,
    used_dry_run: bool,
    fallback_status: str,
    record_count: int,
    completed_excluded: int,
) -> str:
    if used_dry_run and request_id:
        age_label = f"live (dry run {request_id[:8]})"
    elif used_dry_run:
        age_label = "live (dry run)"
    else:
        age_label = f"snapshot @ {produced_at}"
    prefix = f"{fallback_status} " if fallback_status else ""
    return (
        prefix
        + f"Queue plan source: {age_label}. "
        + f"{record_count} runnable, "
        + f"{completed_excluded} filtered (already-processed / blocked)."
    )
