from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import threading
from typing import Any
import uuid

from mediapipeline.core.queue.dry_run_runner import (
    queue_dry_run_failure_for_service,
    run_queue_dry_run_for_service,
)
from mediapipeline.core.queue.preview_builder import build_queue_preview_for_service
from mediapipeline.core.queue.priority_markers import (
    apply_priority_marker as apply_priority_marker_to_path,
    format_priority_leaf_name as format_priority_leaf_name_for_marker,
    get_source_priority_info as get_source_priority_info_for_path,
    path_is_unc,
    remove_priority_markers_from_name,
    safe_mtime,
    starts_with_priority_marker,
    touch_priority_target as touch_priority_target_path,
)
from mediapipeline.core.queue.snapshot import (
    queue_dry_run_tail,
    queue_record_from_snapshot_row,
    queue_snapshot_is_current_for_request,
    queue_snapshot_path,
    queue_snapshot_write_path,
    read_queue_snapshot,
)
from mediapipeline.core.queue.source_inventory import (
    QUEUE_SOURCE_INVENTORY_PREVIEW_LIMIT,
    build_queue_source_inventory,
    preview_queue_source_inventory,
    queue_scan_status_path,
    queue_scan_status_payload,
    queue_source_inventory_path,
    read_json_artifact,
    read_queue_scan_status as read_queue_scan_status_artifact,
    utc_now_iso,
    write_json_artifact,
)
from mediapipeline.core.paths.contracts import ResolvedPaths
from mediapipeline.core.queue.contracts import QueueRecord


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
    QUEUE_SCAN_MODES = {"inventory_then_curate", "inventory_only", "curate_only"}

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

    def _queue_scan_lock(self) -> threading.Lock:
        lock = getattr(self, "_queue_source_scan_lock", None)
        if lock is None:
            lock = threading.Lock()
            self._queue_source_scan_lock = lock
        return lock

    def _queue_scan_id(self) -> str:
        prefix = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        return f"{prefix}-{uuid.uuid4().hex[:10]}"

    def _write_queue_scan_status(self, resolved: ResolvedPaths, status: dict[str, Any]) -> None:
        path = queue_scan_status_path(resolved)
        if path is None:
            return
        write_json_artifact(path, status)

    def read_queue_scan_status(self, resolved: ResolvedPaths) -> dict[str, Any]:
        status = read_queue_scan_status_artifact(resolved)
        active = getattr(self, "_queue_source_scan_active", None)
        thread = active.get("thread") if isinstance(active, dict) else None
        if isinstance(thread, threading.Thread) and thread.is_alive():
            active_id = str(active.get("scan_id") or "")
            if active_id and str(status.get("scan_id") or "") == active_id:
                status = dict(status)
                status["running"] = True
                status["status"] = "running"
        if not status.get("queue_snapshot_path"):
            status = dict(status)
            status["queue_snapshot_path"] = str(self._queue_snapshot_write_path(resolved) or resolved.queue_snapshot_path or "")
        return status

    def read_queue_source_inventory(
        self,
        resolved: ResolvedPaths,
        *,
        row_limit: int = QUEUE_SOURCE_INVENTORY_PREVIEW_LIMIT,
    ) -> dict[str, Any]:
        return preview_queue_source_inventory(read_json_artifact(queue_source_inventory_path(resolved)), row_limit=row_limit)

    def queue_source_scan_active_block_message(self, action: str) -> str:
        active = getattr(self, "_queue_source_scan_active", None)
        if not isinstance(active, dict):
            return ""
        thread = active.get("thread")
        if not isinstance(thread, threading.Thread) or not thread.is_alive():
            return ""
        scan_id = str(active.get("scan_id") or "").strip()
        scan_text = f" {scan_id}" if scan_id else ""
        return f"{action} blocked because queue source scan{scan_text} is still running."

    def start_queue_source_scan(self, resolved: ResolvedPaths, request: dict[str, Any]) -> dict[str, Any]:
        status_path = queue_scan_status_path(resolved)
        inventory_path = queue_source_inventory_path(resolved)
        snapshot_path = self._queue_snapshot_write_path(resolved)
        if status_path is None or inventory_path is None or snapshot_path is None:
            return {
                "ok": False,
                "message": "Queue source scan requires LocalBase/State to be configured.",
                "status": queue_scan_status_payload(
                    status="failed",
                    phase="blocked",
                    message="Queue source scan requires LocalBase/State to be configured.",
                    errors=["state_root_unavailable"],
                ),
            }

        mode = str(request.get("mode") or "inventory_then_curate").strip().casefold()
        if mode not in self.QUEUE_SCAN_MODES:
            return {
                "ok": False,
                "message": f"Unsupported queue scan mode: {mode or '<blank>'}.",
                "status": self.read_queue_scan_status(resolved),
                "errors": ["unsupported_queue_scan_mode"],
            }
        scope = str(request.get("scope") or "all").strip().casefold()
        if scope not in {"all", ""}:
            return {
                "ok": False,
                "message": f"Unsupported queue scan scope: {scope}.",
                "status": self.read_queue_scan_status(resolved),
                "errors": ["unsupported_queue_scan_scope"],
            }
        scope = "all"
        force = request.get("force", True) is not False

        lock = self._queue_scan_lock()
        with lock:
            active = getattr(self, "_queue_source_scan_active", None)
            thread = active.get("thread") if isinstance(active, dict) else None
            if isinstance(thread, threading.Thread) and thread.is_alive():
                return {
                    "ok": True,
                    "duplicate": True,
                    "message": "Queue source scan is already running; observing the active scan.",
                    "status": self.read_queue_scan_status(resolved),
                }

            scan_id = self._queue_scan_id()
            requested_at = utc_now_iso()
            status = queue_scan_status_payload(
                scan_id=scan_id,
                status="running",
                phase="starting",
                mode=mode,
                force=force,
                scope=scope,
                requested_at_utc=requested_at,
                started_at_utc=requested_at,
                updated_at_utc=requested_at,
                message="Queue source scan starting.",
                status_path=status_path,
                inventory_path=inventory_path,
                queue_snapshot_path=snapshot_path,
            )
            self._write_queue_scan_status(resolved, status)

            thread = threading.Thread(
                target=self._run_queue_source_scan_worker,
                args=(resolved, scan_id, mode, force, scope, requested_at),
                name=f"queue-source-scan-{scan_id}",
                daemon=False,
            )
            self._queue_source_scan_active = {"scan_id": scan_id, "thread": thread}
            thread.start()

        return {
            "ok": True,
            "duplicate": False,
            "message": "Queue source scan started.",
            "status": status,
        }

    def _run_queue_source_scan_worker(
        self,
        resolved: ResolvedPaths,
        scan_id: str,
        mode: str,
        force: bool,
        scope: str,
        requested_at: str,
    ) -> None:
        status_path = queue_scan_status_path(resolved)
        inventory_path = queue_source_inventory_path(resolved)
        snapshot_path = self._queue_snapshot_write_path(resolved)
        inventory_count = 0
        curated_row_count = 0
        warnings: list[str] = []
        try:
            if mode != "curate_only":
                inventory_started = utc_now_iso()
                self._write_queue_scan_status(
                    resolved,
                    queue_scan_status_payload(
                        scan_id=scan_id,
                        status="running",
                        phase="inventory",
                        mode=mode,
                        force=force,
                        scope=scope,
                        requested_at_utc=requested_at,
                        started_at_utc=requested_at,
                        updated_at_utc=inventory_started,
                        message="Building fast source inventory.",
                        status_path=status_path,
                        inventory_path=inventory_path,
                        queue_snapshot_path=snapshot_path,
                    ),
                )
                inventory = build_queue_source_inventory(resolved, scan_id=scan_id)
                inventory_count = int(inventory.get("row_count") or 0)
                warnings.extend(str(item) for item in inventory.get("warnings") or [] if str(item).strip())
                if inventory_path is not None:
                    write_json_artifact(inventory_path, inventory)

            if mode == "inventory_only":
                completed_at = utc_now_iso()
                self._write_queue_scan_status(
                    resolved,
                    queue_scan_status_payload(
                        scan_id=scan_id,
                        status="completed",
                        phase="complete",
                        mode=mode,
                        force=force,
                        scope=scope,
                        requested_at_utc=requested_at,
                        started_at_utc=requested_at,
                        updated_at_utc=completed_at,
                        completed_at_utc=completed_at,
                        message=f"Source inventory completed with {inventory_count} candidate file(s).",
                        status_path=status_path,
                        inventory_path=inventory_path,
                        queue_snapshot_path=snapshot_path,
                        inventory_count=inventory_count,
                        curated_row_count=0,
                        warnings=warnings,
                    ),
                )
                return

            curation_started = utc_now_iso()
            self._write_queue_scan_status(
                resolved,
                queue_scan_status_payload(
                    scan_id=scan_id,
                    status="running",
                    phase="curating",
                    mode=mode,
                    force=force,
                    scope=scope,
                    requested_at_utc=requested_at,
                    started_at_utc=requested_at,
                    updated_at_utc=curation_started,
                    message="Curating authoritative queue snapshot through backend queue plan.",
                    status_path=status_path,
                    inventory_path=inventory_path,
                    queue_snapshot_path=snapshot_path,
                    inventory_count=inventory_count,
                    warnings=warnings,
                ),
            )
            curated_row_count = len(self.build_queue_preview(resolved, force_refresh=force))
            completed_at = utc_now_iso()
            self._write_queue_scan_status(
                resolved,
                queue_scan_status_payload(
                    scan_id=scan_id,
                    status="completed",
                    phase="complete",
                    mode=mode,
                    force=force,
                    scope=scope,
                    requested_at_utc=requested_at,
                    started_at_utc=requested_at,
                    updated_at_utc=completed_at,
                    completed_at_utc=completed_at,
                    message=f"Queue source scan completed: {inventory_count} inventory candidate(s), {curated_row_count} curated queue row(s).",
                    status_path=status_path,
                    inventory_path=inventory_path,
                    queue_snapshot_path=snapshot_path,
                    inventory_count=inventory_count,
                    curated_row_count=curated_row_count,
                    warnings=warnings,
                ),
            )
        except Exception as exc:
            logger = getattr(self, "logger", None)
            if logger is not None:
                logger.exception("queue source scan failed: %s", exc)
            failed_at = utc_now_iso()
            self._write_queue_scan_status(
                resolved,
                queue_scan_status_payload(
                    scan_id=scan_id,
                    status="failed",
                    phase="failed",
                    mode=mode,
                    force=force,
                    scope=scope,
                    requested_at_utc=requested_at,
                    started_at_utc=requested_at,
                    updated_at_utc=failed_at,
                    completed_at_utc=failed_at,
                    message=f"Queue source scan failed: {exc}",
                    status_path=status_path,
                    inventory_path=inventory_path,
                    queue_snapshot_path=snapshot_path,
                    inventory_count=inventory_count,
                    curated_row_count=curated_row_count,
                    warnings=warnings,
                    errors=[str(exc)],
                ),
            )
        finally:
            lock = self._queue_scan_lock()
            with lock:
                active = getattr(self, "_queue_source_scan_active", None)
                if isinstance(active, dict) and str(active.get("scan_id") or "") == scan_id:
                    self._queue_source_scan_active = None

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
