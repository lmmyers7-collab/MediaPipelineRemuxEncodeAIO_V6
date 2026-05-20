from __future__ import annotations

from pathlib import Path
from typing import Any

from ..models import Snapshot


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
        status = str(progress.get("Status") or "").strip().casefold()
        if status:
            if status in {"processing", "running", "active"}:
                return "processing"
            if status in {"paused", "pause"}:
                return "paused"
            if status in {"complete", "completed", "done"}:
                return "completed"
            if status in {"failed", "error"}:
                return "failed"
            return status.replace(" ", "_")
        audit_status = str(audit_progress.get("status") or audit_progress.get("Status") or "").strip().casefold()
        if audit_status and audit_status not in {"complete", "completed", "idle"}:
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
