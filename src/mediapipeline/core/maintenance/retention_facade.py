"""Retention dry-run facade adapter."""

from __future__ import annotations

from typing import Any

from mediapipeline.core.maintenance.command_policy import (
    MAINTENANCE_REFRESH_HINT,
    maintenance_command_blocked_result,
)
from mediapipeline.core.maintenance.retention import (
    RETENTION_DRY_RUN_COMMAND,
    RETENTION_DRY_RUN_SCHEMA_VERSION,
    retention_dry_run_payload,
)
from mediapipeline.core.kernel.dto_commands import CommandResult


class MaintenanceRetentionFacadeMixin:
    """Read-only retention dry-run command adapter for the application facade."""

    def run_retention_dry_run(self, resolved: Any, request: dict[str, Any]) -> CommandResult:
        lock, block_message = self._acquire_maintenance_command_lock("Retention dry run")
        if block_message:
            return maintenance_command_blocked_result(RETENTION_DRY_RUN_COMMAND, block_message)
        try:
            data = retention_dry_run_payload(resolved, request)
        except Exception as exc:
            return CommandResult(
                command=RETENTION_DRY_RUN_COMMAND,
                ok=False,
                message=f"Retention dry run failed: {exc}",
                severity="error",
                errors=[str(exc)],
                refresh_hint=MAINTENANCE_REFRESH_HINT,
                data={
                    "schema_version": RETENTION_DRY_RUN_SCHEMA_VERSION,
                    "dry_run_only": True,
                    "effect": "none",
                    "suppress_command_journal": True,
                    "would_delete_paths": [],
                    "would_move_paths": [],
                    "would_write_paths": [],
                },
            )
        finally:
            self._release_maintenance_command_lock(lock)
        review = str(data.get("overall_status") or "").casefold() == "review"
        return CommandResult(
            command=RETENTION_DRY_RUN_COMMAND,
            ok=True,
            message=(
                "Retention dry run complete; "
                f"candidate_count={data.get('candidate_count', 0)}; "
                "mutation_route_available=no."
            ),
            severity="warning" if review else "info",
            warnings=[] if not review else ["Retention dry run found scan issues that require review."],
            refresh_hint=MAINTENANCE_REFRESH_HINT,
            data=data,
        )


__all__ = [
    "MaintenanceRetentionFacadeMixin",
]
