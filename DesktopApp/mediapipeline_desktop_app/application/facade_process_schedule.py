from __future__ import annotations

from typing import Any

from .facade_process_schedule_policy import resolve_pipeline_start_schedule_gate


class ProcessScheduleFacadeMixin:
    """Schedule-gate policy for backend-owned pipeline starts."""

    def _pipeline_schedule_stop_watcher_available(self) -> bool:
        watcher = getattr(self, "_schedule_stop_watcher", None)
        available = getattr(watcher, "available", None)
        if not callable(available):
            return False
        try:
            return bool(available())
        except Exception:
            return False

    def _resolve_pipeline_start_schedule_gate(self, mode: str, request: dict[str, Any]) -> dict[str, Any]:
        workspace = self.get_schedule_workspace()
        evaluation = dict(workspace.evaluation or {})
        return resolve_pipeline_start_schedule_gate(
            mode=mode,
            request=request,
            enabled=bool(workspace.enabled),
            evaluation=evaluation,
            backend_stop_watcher_available=self._pipeline_schedule_stop_watcher_available(),
        )

__all__ = [
    "ProcessScheduleFacadeMixin",
]
