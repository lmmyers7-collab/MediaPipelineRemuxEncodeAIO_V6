from __future__ import annotations

from typing import Any

from mediapipeline.core.queue.contracts import QueuePreviewServiceProtocol
from mediapipeline.core.queue.dry_run import format_queue_plan_source_status, queue_snapshot_file_is_fresh
from mediapipeline.desktop.models import QueueRecord, ResolvedPaths


def build_queue_preview_for_service(
    service: QueuePreviewServiceProtocol,
    resolved: ResolvedPaths,
    *,
    force_refresh: bool = False,
) -> list[QueueRecord]:
    service._queue_completed_excluded = 0
    service._queue_source_candidates = 0
    service._queue_completed_size_mismatches = 0
    service._queue_completed_identity_mismatches = 0
    service._queue_completed_unverified = 0
    service._queue_scan_limited = False
    service._queue_completed_cache_status = ""

    snapshot_path = service._queue_snapshot_path(resolved)
    snapshot: dict[str, Any] | None = None
    used_dry_run = False
    fallback_status = ""

    if snapshot_path and snapshot_path.exists() and not force_refresh:
        if queue_snapshot_file_is_fresh(
            snapshot_path,
            fresh_seconds=service.QUEUE_SNAPSHOT_FRESH_SECONDS,
        ):
            snapshot = service._read_queue_snapshot(snapshot_path)

    if snapshot is None:
        snapshot = service._run_queue_dry_run(resolved, allow_cached_fallback=not force_refresh)
        used_dry_run = True
        if "Showing last cached snapshot" in service._queue_completed_cache_status:
            fallback_status = service._queue_completed_cache_status

    if not snapshot:
        if not service._queue_completed_cache_status:
            service._queue_completed_cache_status = "No queue snapshot available; run the pipeline once or refresh."
        return []

    rows = snapshot.get("rows") or []
    records = [service._queue_record_from_snapshot_row(row) for row in rows]

    service._queue_source_candidates = int(snapshot.get("movie_count_total", 0)) + int(snapshot.get("tv_count_total", 0))
    service._queue_completed_excluded = max(0, service._queue_source_candidates - len(records))

    produced = snapshot.get("produced_at", "?")
    request_id = str(snapshot.get("desktop_queue_preview_request_id", "") or "").strip()
    service._queue_completed_cache_status = format_queue_plan_source_status(
        produced_at=produced,
        request_id=request_id,
        used_dry_run=used_dry_run,
        fallback_status=fallback_status,
        record_count=len(records),
        completed_excluded=service._queue_completed_excluded,
    )
    return records
