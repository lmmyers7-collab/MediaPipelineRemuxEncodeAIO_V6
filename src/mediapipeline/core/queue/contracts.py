from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from mediapipeline.core.paths.contracts import ResolvedPaths


@dataclass
class QueueRecord:
    source_path: Path
    source_root: Path
    media_type: str
    is_priority: bool
    priority_reasons: list[str]
    priority_rank: float
    sort_name: str
    display_name: str
    relative_path: str
    show_folder: str
    season_folder: str
    season_number: int
    episode_number: int
    source_mtime: float
    size_gb: float
    route_name: str
    route_reason: str
    matched_show_override: str
    queue_index: int
    queue_total: int
    phase: str
    global_order: int
    # Manifest-based priority level: "high" | "normal" | "low" | "hold"
    # "normal" means no manifest entry (or entry explicitly set to normal).
    manifest_priority_level: str = "normal"

    @property
    def queue_position(self) -> str:
        return f"{self.queue_index}/{self.queue_total}"


class QueuePreviewServiceProtocol(Protocol):
    QUEUE_SNAPSHOT_FRESH_SECONDS: float
    _queue_completed_excluded: int
    _queue_source_candidates: int
    _queue_completed_size_mismatches: int
    _queue_completed_identity_mismatches: int
    _queue_completed_unverified: int
    _queue_scan_limited: bool
    _queue_completed_cache_status: str

    def _queue_snapshot_path(self, resolved: ResolvedPaths) -> Path | None: ...
    def _read_queue_snapshot(self, path: Path) -> dict[str, Any] | None: ...
    def _run_queue_dry_run(self, resolved: ResolvedPaths, *, allow_cached_fallback: bool = False) -> dict[str, Any] | None: ...
    def _queue_record_from_snapshot_row(self, row: dict[str, Any]) -> Any: ...


class QueueDryRunServiceProtocol(Protocol):
    app_root: Path
    workspace_root: Path
    QUEUE_DRY_RUN_TIMEOUT_SECONDS: float
    QUEUE_DRY_RUN_OUTPUT_TAIL_LINES: int
    _queue_completed_cache_status: str
    _queue_dry_run_cleanup_warnings: list[str]

    def _queue_snapshot_write_path(self, resolved: ResolvedPaths) -> Path | None: ...
    def _read_queue_snapshot(self, path: Path) -> dict[str, Any] | None: ...
    def _queue_snapshot_is_current_for_request(self, path: Path, snapshot: dict[str, Any], started_at: float) -> bool: ...
    def _build_launch_environment(self) -> Mapping[str, str]: ...
    def _subprocess_kwargs_hidden(self) -> Mapping[str, Any]: ...
