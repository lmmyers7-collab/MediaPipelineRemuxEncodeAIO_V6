from __future__ import annotations

from pathlib import Path
from typing import Any, Protocol

from mediapipeline.desktop.models_core import ResolvedPaths


class WarningLogger(Protocol):
    def warning(self, message: object, *args: object, **kwargs: object) -> None: ...


class StatusSnapshotServiceProtocol(Protocol):
    logger: WarningLogger

    def read_progress(self, resolved: ResolvedPaths) -> dict[str, Any] | None: ...
    def read_audit_progress(self, resolved: ResolvedPaths) -> dict[str, Any] | None: ...
    def latest_matching_file(self, folder: Path | None, pattern: str) -> Path | None: ...
    def latest_failure_json(self, resolved: ResolvedPaths) -> Path | None: ...
    def latest_audit_csv(self, resolved: ResolvedPaths, priority_only: bool) -> Path | None: ...
    def read_log_tail(self, resolved: ResolvedPaths) -> str: ...
    def read_pipeline_events_tail(self, resolved: ResolvedPaths) -> list[dict[str, Any]]: ...
    def _build_status_summary(
        self,
        *,
        resolved: ResolvedPaths,
        progress: dict[str, Any] | None,
        audit_progress: dict[str, Any] | None,
        pipeline_events: list[dict[str, Any]],
        audit_root: str,
        latest_failure_report: Path | None,
        latest_failure_json: Path | None,
        latest_audit_csv: Path | None,
        latest_priority_csv: Path | None,
    ) -> str: ...
    def is_progress_stale(self, progress: dict[str, Any] | None) -> bool: ...
    def _build_current_activity(
        self,
        resolved: ResolvedPaths,
        progress: dict[str, Any] | None,
        log_tail: str,
        pipeline_events: list[dict[str, Any]],
    ) -> str: ...
