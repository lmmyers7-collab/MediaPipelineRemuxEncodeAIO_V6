from __future__ import annotations

from pathlib import Path

from .models import QueueRecord, ResolvedPaths
from .priority_markers import remove_priority_markers_from_name, starts_with_priority_marker
from .service_queue_priority import (
    apply_priority_marker as apply_priority_marker_to_path,
    format_priority_leaf_name as format_priority_leaf_name_for_marker,
    get_source_priority_info as get_source_priority_info_for_path,
    path_is_unc,
    safe_mtime,
    touch_priority_target as touch_priority_target_path,
)
from .service_queue_dry_run_runner import (
    queue_dry_run_failure_for_service,
    run_queue_dry_run_for_service,
)
from .service_queue_preview_builder import build_queue_preview_for_service
from .service_queue_snapshot import (
    queue_dry_run_tail,
    queue_record_from_snapshot_row,
    queue_snapshot_is_current_for_request,
    queue_snapshot_path,
    queue_snapshot_write_path,
    read_queue_snapshot,
)


class QueueServiceMixin:
    def starts_with_priority_marker(self, text: str, markers: list[str]) -> bool:
        return starts_with_priority_marker(text, markers)

    def remove_priority_markers_from_name(self, text: str, markers: list[str]) -> str:
        return remove_priority_markers_from_name(text, markers)

    def get_source_priority_info(
        self,
        source_path: Path,
        markers: list[str],
        stat_cache: dict[Path, float] | None = None,
    ) -> tuple[bool, list[str], float]:
        return get_source_priority_info_for_path(source_path, markers, stat_cache)

    def _path_is_unc(self, path: Path) -> bool:
        return path_is_unc(path)

    # Snapshot is considered fresh enough to skip a dry-run subprocess if
    # it was written within this many seconds. The running pipeline writes
    # one after every scan round.
    QUEUE_SNAPSHOT_FRESH_SECONDS = 60.0
    # Upper bound for the synchronous dry-run subprocess. The pipeline's own
    # SourceScanTimeoutSeconds / IndexScanTimeoutSeconds clamp internally;
    # this is an outer ceiling so a hung child can't pin the backend refresh path.
    QUEUE_DRY_RUN_TIMEOUT_SECONDS = 120.0
    QUEUE_DRY_RUN_OUTPUT_TAIL_LINES = 8

    def _queue_snapshot_path(self, resolved: ResolvedPaths) -> Path | None:
        return queue_snapshot_path(resolved)

    def _queue_snapshot_write_path(self, resolved: ResolvedPaths) -> Path | None:
        return queue_snapshot_write_path(resolved)

    def _read_queue_snapshot(self, path: Path) -> dict | None:
        return read_queue_snapshot(path)

    def _queue_snapshot_is_current_for_request(self, path: Path, snapshot: dict, started_at: float) -> bool:
        return queue_snapshot_is_current_for_request(
            path,
            snapshot,
            started_at,
            parse_progress_datetime=self._parse_progress_datetime,
        )

    def _queue_dry_run_failure(
        self,
        message: str,
        snap_path: Path,
        *,
        allow_cached_fallback: bool,
        temp_path: Path | None = None,
    ) -> dict | None:
        return queue_dry_run_failure_for_service(
            self,
            message,
            snap_path,
            allow_cached_fallback=allow_cached_fallback,
            temp_path=temp_path,
        )

    def _queue_dry_run_tail(self, stdout: str | None, stderr: str | None) -> str:
        return queue_dry_run_tail(stdout, stderr, max_lines=self.QUEUE_DRY_RUN_OUTPUT_TAIL_LINES)

    def _run_queue_dry_run(self, resolved: ResolvedPaths, *, allow_cached_fallback: bool = False) -> dict | None:
        """Spawn the pipeline in -EmitQueuePlan mode and load the resulting JSON."""
        return run_queue_dry_run_for_service(self, resolved, allow_cached_fallback=allow_cached_fallback)

    def _queue_record_from_snapshot_row(self, row: dict) -> QueueRecord:
        return queue_record_from_snapshot_row(row)

    def build_queue_preview(self, resolved: ResolvedPaths, force_refresh: bool = False) -> list[QueueRecord]:
        """Mirror the live pipeline's queue plan.

        Reads <LocalBase>/State/Progress/queue_snapshot.json when fresh (the running
        pipeline writes it after every scan), otherwise spawns the pipeline
        with -EmitQueuePlan to produce the same plan on demand. The returned
        rows are exactly what Invoke-MediaQueuePhasePlan would process, in the
        exact order, with Already-Processed / pending-publish / sidecar-version
        filtering already applied.
        """
        return build_queue_preview_for_service(self, resolved, force_refresh=force_refresh)

    def _safe_mtime(self, path: Path, cache: dict[Path, float] | None = None) -> float:
        return safe_mtime(path, cache)

    def format_priority_leaf_name(self, marker: str, leaf: str, markers: list[str]) -> str:
        return format_priority_leaf_name_for_marker(marker, leaf, markers)

    def apply_priority_marker(self, target_path: Path, markers: list[str], marker: str, remove_only: bool = False) -> Path:
        return apply_priority_marker_to_path(target_path, markers, marker, remove_only=remove_only)

    def touch_priority_target(self, target_path: Path) -> None:
        touch_priority_target_path(target_path)
