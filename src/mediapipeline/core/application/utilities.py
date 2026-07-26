"""Shared utility mixin for application facade adapters."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from mediapipeline.core.status.contracts import Snapshot
from mediapipeline.core.status.progress import is_audit_progress_stale

_COMPLETED_PROGRESS_STATUSES = frozenset({"complete", "completed", "done"})
_FAILED_PROGRESS_STATUSES = frozenset({"failed", "error"})
_IDLE_PROGRESS_STAGES = frozenset({"idle", "sleeping"})


class FacadeUtilityMixin:
    """Small shared helpers for facade mixins."""

    @staticmethod
    def _optional_path(value: object) -> Path | None:
        if value is None:
            return None
        try:
            return Path(value)
        except TypeError:
            return None

    @staticmethod
    def _path_text(path: Path | None) -> str:
        return str(path) if path else ""

    @staticmethod
    def _int_from(mapping: dict[str, Any], *keys: str) -> int:
        for key in keys:
            raw = mapping.get(key)
            try:
                if raw not in (None, ""):
                    return int(float(raw))
            except (TypeError, ValueError):
                continue
        return 0

    @staticmethod
    def _int_value(value: Any) -> int:
        try:
            if value not in (None, ""):
                return int(float(value))
        except (TypeError, ValueError):
            return 0
        return 0

    @staticmethod
    def _pipeline_state(snapshot: Snapshot) -> str:
        progress = snapshot.progress or {}
        audit_progress = snapshot.audit_progress or {}
        activity = str(snapshot.current_activity or "").strip().casefold()
        audit_status = str(audit_progress.get("status") or audit_progress.get("Status") or "").strip().casefold()
        audit_last_update = str(audit_progress.get("last_update") or "").strip()
        audit_is_current = (
            bool(audit_status)
            and audit_status not in {"complete", "completed", "failed", "idle", "stopped"}
            and (not audit_last_update or not is_audit_progress_stale(audit_progress))
        )
        if audit_is_current and "stale progress" in activity:
            return "audit"
        if "stale progress" in activity:
            return "stale"
        status = str(progress.get("Status") or "").strip().casefold()
        stage = str(progress.get("CurrentStage") or "").strip().casefold()
        if audit_is_current and (
            stage in {"", "completed", "stopped", *_IDLE_PROGRESS_STAGES}
            or status in {"", *_COMPLETED_PROGRESS_STATUSES, *_FAILED_PROGRESS_STATUSES}
        ):
            return "audit"
        if stage in _IDLE_PROGRESS_STAGES:
            if status in _COMPLETED_PROGRESS_STATUSES:
                return "completed"
            if status in _FAILED_PROGRESS_STATUSES:
                return "failed"
            return "idle"
        if stage == "completed":
            return "completed"
        if stage == "stopped":
            return "stopped"
        if status:
            if status in {"processing", "running", "active"}:
                return "processing"
            if status in {"paused", "pause"}:
                return "paused"
            if status in _COMPLETED_PROGRESS_STATUSES:
                return "completed"
            if status in _FAILED_PROGRESS_STATUSES:
                return "failed"
            return status.replace(" ", "_")
        if audit_is_current:
            return "audit"
        return "idle"

    @staticmethod
    def _bounded_timeout_seconds(value: Any, *, default: int, minimum: int, maximum: int) -> int:
        try:
            seconds = int(float(value))
        except (TypeError, ValueError):
            seconds = default
        return max(minimum, min(maximum, seconds))

__all__ = [
    "FacadeUtilityMixin",
]
