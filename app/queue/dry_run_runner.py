from __future__ import annotations

import contextlib
import json
import time
import uuid
from pathlib import Path
from typing import Any

from app.queue.dry_run import build_queue_dry_run_command, queue_dry_run_temp_snapshot_path
from app.queue.snapshot import queue_dry_run_tail
from mediapipeline_desktop_app.models import ResolvedPaths
from app.shared.protocols import QueueDryRunServiceProtocol
from app.shared.utils import _atomic_write_text
from mediapipeline_desktop_app.subprocess_runner import run_capture


def queue_dry_run_failure_for_service(
    service: QueueDryRunServiceProtocol,
    message: str,
    snap_path: Path,
    *,
    allow_cached_fallback: bool,
    temp_path: Path | None = None,
) -> dict[str, Any] | None:
    if temp_path is not None:
        with contextlib.suppress(OSError):
            temp_path.unlink()
    service._queue_completed_cache_status = message
    if allow_cached_fallback:
        cached = service._read_queue_snapshot(snap_path) if snap_path.exists() else None
        if cached:
            service._queue_completed_cache_status = f"{message} Showing last cached snapshot."
            return cached
        return None
    raise RuntimeError(message)


def run_queue_dry_run_for_service(
    service: QueueDryRunServiceProtocol,
    resolved: ResolvedPaths,
    *,
    allow_cached_fallback: bool = False,
) -> dict[str, Any] | None:
    snap_path = service._queue_snapshot_write_path(resolved)
    if not snap_path:
        service._queue_completed_cache_status = "LocalBase not configured; cannot run queue dry-run."
        return None
    snap_path.parent.mkdir(parents=True, exist_ok=True)
    request_id = uuid.uuid4().hex
    temp_snapshot_path = queue_dry_run_temp_snapshot_path(snap_path, request_id)
    cmd = build_queue_dry_run_command(resolved, temp_snapshot_path=temp_snapshot_path)
    launch_cwd = service.workspace_root if service.workspace_root.exists() else service.app_root
    started_at = time.time()
    try:
        result = run_capture(
            cmd,
            timeout_seconds=service.QUEUE_DRY_RUN_TIMEOUT_SECONDS,
            cwd=launch_cwd,
            env=service._build_launch_environment(),
            extra_popen_kwargs=service._subprocess_kwargs_hidden(),
            hidden=True,
            label="queue dry-run",
            kill_tree=getattr(service, "kill_process_tree", None),
        )
    except OSError as exc:
        return queue_dry_run_failure_for_service(
            service,
            f"Queue dry-run failed to launch: {exc}.",
            snap_path,
            allow_cached_fallback=allow_cached_fallback,
            temp_path=temp_snapshot_path,
        )

    if result.timed_out:
        kill_message = result.kill_message or "process kill status unknown"
        return queue_dry_run_failure_for_service(
            service,
            f"Queue dry-run timed out after {service.QUEUE_DRY_RUN_TIMEOUT_SECONDS:.0f}s; {kill_message}.",
            snap_path,
            allow_cached_fallback=allow_cached_fallback,
            temp_path=temp_snapshot_path,
        )

    if result.returncode != 0:
        tail = queue_dry_run_tail(result.stdout, result.stderr, max_lines=service.QUEUE_DRY_RUN_OUTPUT_TAIL_LINES)
        return queue_dry_run_failure_for_service(
            service,
            f"Queue dry-run exited {result.returncode}: {tail}",
            snap_path,
            allow_cached_fallback=allow_cached_fallback,
            temp_path=temp_snapshot_path,
        )

    snapshot = service._read_queue_snapshot(temp_snapshot_path)
    if not snapshot:
        return queue_dry_run_failure_for_service(
            service,
            "Queue dry-run did not produce a readable queue snapshot.",
            snap_path,
            allow_cached_fallback=allow_cached_fallback,
            temp_path=temp_snapshot_path,
        )
    if not service._queue_snapshot_is_current_for_request(temp_snapshot_path, snapshot, started_at):
        return queue_dry_run_failure_for_service(
            service,
            "Queue dry-run produced a stale queue snapshot; ignoring it.",
            snap_path,
            allow_cached_fallback=allow_cached_fallback,
            temp_path=temp_snapshot_path,
        )

    snapshot["desktop_queue_preview_request_id"] = request_id
    _atomic_write_text(snap_path, json.dumps(snapshot, indent=2, sort_keys=True) + "\n")
    if resolved.state_root is not None:
        try:
            from app.storage.db import open_state_db

            open_state_db(resolved.state_root).record_queue_snapshot(
                snapshot,
                source_path=snap_path,
                request_id=request_id,
            )
        except Exception as exc:
            logger = getattr(service, "logger", None)
            if logger is not None:
                logger.warning("Could not mirror queue snapshot to SQLite: %s", exc)
    with contextlib.suppress(OSError):
        temp_snapshot_path.unlink()
    return snapshot
