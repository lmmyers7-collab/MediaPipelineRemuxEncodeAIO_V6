"""Maintenance command facade for archiving oversized state journals."""

from __future__ import annotations

from typing import Any, Mapping

from mediapipeline.core.kernel.dto_commands import CommandResult
from mediapipeline.core.maintenance.command_policy import (
    MAINTENANCE_REFRESH_HINT,
    maintenance_command_blocked_result,
)
from mediapipeline.core.maintenance.state_journal_archive import (
    STATE_JOURNAL_ARCHIVE_COMMAND,
    STATE_JOURNAL_ARCHIVE_SCHEMA_VERSION,
    archive_state_journals_payload,
    close_readiness_blocked_archive_payload,
    unconfirmed_state_journal_archive_payload,
)


class MaintenanceStateJournalArchiveFacadeMixin:
    """Confirmed archive action for oversized runtime event evidence."""

    def archive_state_journals(
        self,
        resolved: Any,
        request: dict[str, Any],
        *,
        close_readiness: Mapping[str, Any] | None = None,
    ) -> CommandResult:
        lock, block_message = self._acquire_maintenance_command_lock("State journal archive")
        if block_message:
            return maintenance_command_blocked_result(STATE_JOURNAL_ARCHIVE_COMMAND, block_message)
        try:
            if request.get("confirm_archive") is not True:
                return CommandResult(
                    command=STATE_JOURNAL_ARCHIVE_COMMAND,
                    ok=False,
                    message="State journal archive requires explicit confirmation.",
                    severity="warning",
                    warnings=["confirm_archive must be true."],
                    refresh_hint=MAINTENANCE_REFRESH_HINT,
                    data=unconfirmed_state_journal_archive_payload(
                        resolved,
                        request,
                        close_readiness=close_readiness,
                    ),
                )
            readiness = dict(close_readiness or {})
            if not bool(readiness.get("safe_to_close", False)):
                reason = str(readiness.get("reason") or "Close readiness is not safe.")
                return CommandResult(
                    command=STATE_JOURNAL_ARCHIVE_COMMAND,
                    ok=False,
                    message=f"State journal archive refused: {reason}",
                    severity="warning",
                    warnings=[reason],
                    refresh_hint="diagnostics",
                    data=close_readiness_blocked_archive_payload(
                        resolved,
                        request,
                        close_readiness=readiness,
                    ),
                )
            data = archive_state_journals_payload(
                resolved,
                request,
                close_readiness=readiness,
            )
        except Exception as exc:
            return CommandResult(
                command=STATE_JOURNAL_ARCHIVE_COMMAND,
                ok=False,
                message=f"State journal archive failed: {exc}",
                severity="error",
                errors=[str(exc)],
                refresh_hint="diagnostics",
                data={
                    "schema_version": STATE_JOURNAL_ARCHIVE_SCHEMA_VERSION,
                    "effect": "runtime-evidence-archive",
                    "moved_count": 0,
                    "skipped_count": 0,
                    "errors": [str(exc)],
                    "media_mutation_performed": False,
                    "pending_publish_mutation_performed": False,
                    "source_media_mutation_performed": False,
                },
            )
        finally:
            self._release_maintenance_command_lock(lock)
        ok = not data.get("errors")
        moved_count = int(data.get("moved_count") or 0)
        skipped_count = int(data.get("skipped_count") or 0)
        if moved_count:
            message = f"Archived {moved_count} oversized event journal(s)."
            severity = "info"
        elif ok:
            message = "No oversized event journal needed archiving."
            severity = "info"
        else:
            message = "State journal archive failed."
            severity = "error"
        return CommandResult(
            command=STATE_JOURNAL_ARCHIVE_COMMAND,
            ok=ok,
            message=message,
            severity=severity,
            warnings=[] if moved_count else [f"skipped_count={skipped_count}"],
            errors=[str(item) for item in data.get("errors", [])],
            refresh_hint="diagnostics",
            data=data,
        )


__all__ = [
    "MaintenanceStateJournalArchiveFacadeMixin",
]
