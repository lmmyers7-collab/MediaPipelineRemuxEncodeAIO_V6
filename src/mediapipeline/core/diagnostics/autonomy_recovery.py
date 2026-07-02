"""Recovery action factories for autonomy diagnostics."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from mediapipeline.core.diagnostics.autonomy_types import recovery_action


def pending_publish_drain_action() -> dict[str, Any]:
    return recovery_action(
        kind="drain_pending_pushes",
        label="Drain Parked Outputs",
        method="POST",
        route="/api/pipeline/start",
        request={
            "mode": "drain_pending_pushes",
            "sleep_seconds": 30,
            "show_config": False,
            "show_console": False,
            "schedule_override": "",
        },
        requires_confirmation=True,
        frontend_should_autorun=False,
        mutates_media=True,
        mutates_runtime_state=True,
        safe_next_step="Open Pending Publish, review parked rows, then run the backend drain command only after operator confirmation.",
    )


def pending_publish_recovery_plan_action(*, row_key: str = "") -> dict[str, Any]:
    request: dict[str, Any] = {"scope": "all"}
    if row_key:
        request = {"scope": "selected", "row_key": row_key}
    return recovery_action(
        kind="pending_publish_recovery_plan",
        label="Open Pending Publish Recovery Plan",
        method="POST",
        route="/api/pending-publish/recovery-plan",
        request=request,
        requires_confirmation=False,
        frontend_should_autorun=False,
        mutates_media=False,
        mutates_runtime_state=False,
        safe_next_step="Review backend pending-publish recovery evidence before any drain, repair, rerun, or cleanup.",
    )


def journal_archive_action(path: Path | None) -> dict[str, Any]:
    return recovery_action(
        kind="archive_state_journals",
        label="Archive Event Journal",
        method="POST",
        route="/api/maintenance/archive-state-journals",
        request={
            "confirm_archive": True,
            "reason": "launch recovery",
        },
        requires_confirmation=True,
        frontend_should_autorun=False,
        mutates_media=False,
        mutates_runtime_state=True,
        evidence_path=str(path or ""),
        safe_next_step="Archive only the backend-resolved runtime event journal, then refresh launch preflight.",
    )


__all__ = [
    "journal_archive_action",
    "pending_publish_drain_action",
    "pending_publish_recovery_plan_action",
]
