"""Failure report preview and marker-clear facade adapter."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from mediapipeline.core.failures.policy import (
    bounded_failure_limit,
    failure_json_read_error_result,
    failure_latest_json_resolution_error_result,
    failure_loader_unavailable_result,
    failure_marker_lookup,
    failure_marker_service_unavailable_result,
    failure_markers_read_error_result,
    failure_no_json_report_result,
    failure_preview_from_records,
    failure_report_service_unavailable_result,
    failure_record_to_row,
    normalize_failure_source_kind,
)
from mediapipeline.core.failures.resolution_journal import (
    FAILURE_LIFECYCLE_PREVIEW_REQUIRED,
    FAILURE_LIFECYCLE_REASON_REQUIRED,
    FAILURE_LIFECYCLE_TRANSITIONS,
    failure_lifecycle_fingerprint,
    failure_lifecycle_transition_preview,
    failure_resolution_append_event,
    failure_resolution_journal_path,
    failure_resolution_journal_state,
)

from mediapipeline.desktop.application.dto_commands import CommandResult
from mediapipeline.desktop.application.dto_inventory import FailurePreviewDto
from mediapipeline.desktop.models import FailureRecord, ResolvedPaths


class FailureFacadeMixin:
    """Read-only failure-report adapter for the application facade."""

    def get_failure_preview(self, resolved: ResolvedPaths, *, source_kind: str = "latest_json", limit: int = 100) -> FailurePreviewDto:
        """Return recent failure rows without mutating markers, reports, or priority state."""
        source_kind = normalize_failure_source_kind(source_kind)
        bounded_limit = bounded_failure_limit(limit)
        resolution_journal = self._failure_resolution_journal_state(resolved)
        if source_kind == "markers":
            loader = getattr(self.service, "load_failure_marker_records", None)
            if not callable(loader):
                return failure_marker_service_unavailable_result()
            try:
                records = loader(resolved)
            except Exception as exc:
                return failure_markers_read_error_result(resolved.failed_markers_path, exc)
            marker_lookup = failure_marker_lookup(records)
            return self._failure_preview_from_records(
                records,
                source=str(resolved.failed_markers_path or ""),
                source_kind="markers",
                limit=bounded_limit,
                empty_warning="No failure markers are available from the state store.",
                marker_lookup=marker_lookup,
                resolution_journal=resolution_journal,
            )

        path_getter = getattr(self.service, "latest_failure_json", None)
        if not callable(path_getter):
            path_getter = getattr(self.service, "newest_failure_json", None)
        if not callable(path_getter):
            return failure_report_service_unavailable_result()
        try:
            report_path = path_getter(resolved)
        except Exception as exc:
            return failure_latest_json_resolution_error_result(exc)
        if not report_path:
            return failure_no_json_report_result()
        loader = getattr(self.service, "load_failure_records", None)
        if not callable(loader):
            return failure_loader_unavailable_result(report_path)
        try:
            records = loader(Path(report_path))
        except Exception as exc:
            return failure_json_read_error_result(report_path, exc)
        marker_lookup = self._failure_marker_lookup_for_clear_errors(resolved)
        return self._failure_preview_from_records(
            records,
            source=str(report_path),
            source_kind="latest_json",
            limit=bounded_limit,
            empty_warning="Latest failure JSON contains no rows.",
            marker_lookup=marker_lookup,
            resolution_journal=resolution_journal,
        )

    def _failure_resolution_journal_state(self, resolved: ResolvedPaths) -> dict[str, object]:
        try:
            return failure_resolution_journal_state(resolved)
        except Exception as exc:
            return {
                "schema_version": "failure_resolution_journal.v1",
                "path": str(failure_resolution_journal_path(resolved)),
                "event_count": 0,
                "events": [],
                "by_journal_key": {},
                "warning": f"Failure resolution journal could not be read: {exc}",
            }

    def _failure_marker_lookup_for_clear_errors(self, resolved: ResolvedPaths) -> dict[str, list[str]] | None:
        loader = getattr(self.service, "load_failure_marker_records", None)
        if not callable(loader):
            return None
        try:
            records = loader(resolved)
        except Exception:
            return None
        return failure_marker_lookup(records)

    def _failure_preview_from_records(
        self,
        records: object,
        *,
        source: str,
        source_kind: str,
        limit: int,
        empty_warning: str,
        marker_lookup: dict[str, list[str]] | None = None,
        resolution_journal: dict[str, object] | None = None,
    ) -> FailurePreviewDto:
        return failure_preview_from_records(
            records,
            source=source,
            source_kind=source_kind,
            limit=limit,
            empty_warning=empty_warning,
            marker_lookup=marker_lookup,
            resolution_journal=resolution_journal,
        )

    @staticmethod
    def _failure_record_to_row(record: FailureRecord) -> dict[str, object]:
        return failure_record_to_row(record)

    def clear_failure_markers(self, resolved: ResolvedPaths, request: dict[str, Any]) -> CommandResult:
        """Clear backend-owned failure marker files after explicit operator confirmation."""
        dry_run = request.get("dry_run", False) is True
        confirm_clear = request.get("confirm_clear", False) is True
        marker_paths = request.get("marker_paths")
        if marker_paths is None and request.get("marker_path"):
            marker_paths = [request.get("marker_path")]
        if marker_paths is None and request.get("source_json"):
            marker_paths = [request.get("source_json")]
        if marker_paths is not None and not isinstance(marker_paths, list):
            return CommandResult(
                command="failures.clear",
                ok=False,
                severity="error",
                message="'marker_paths' must be a list of backend failure marker paths.",
                errors=["'marker_paths' must be a list of backend failure marker paths."],
                refresh_hint="failures",
            )
        cleaned_paths = [str(item) for item in marker_paths or [] if str(item or "").strip()]
        scope = str(request.get("scope") or ("selected" if cleaned_paths else "all_markers"))
        journal_key = str(request.get("journal_key") or "").strip()
        if scope not in {"selected", "visible", "all_markers"}:
            return CommandResult(
                command="failures.clear",
                ok=False,
                severity="error",
                message="'scope' must be selected, visible, or all_markers.",
                errors=["'scope' must be selected, visible, or all_markers."],
                refresh_hint="failures",
            )
        if scope in {"selected", "visible"} and not cleaned_paths:
            return CommandResult(
                command="failures.clear",
                ok=False,
                severity="error",
                message=f"Failure marker clear scope '{scope}' requires marker_paths.",
                errors=[f"Failure marker clear scope '{scope}' requires marker_paths."],
                refresh_hint="failures",
                data={"scope": scope, "marker_count": 0, "dry_run": dry_run},
            )
        if not dry_run and not confirm_clear:
            return CommandResult(
                command="failures.clear",
                ok=False,
                severity="error",
                message="Failure marker clear requires confirm_clear: true.",
                errors=["Failure marker clear requires confirm_clear: true."],
                refresh_hint="failures",
                data={"scope": scope, "marker_count": len(cleaned_paths), "dry_run": dry_run},
            )
        clearer = getattr(self.service, "clear_failure_markers", None)
        if not callable(clearer):
            return CommandResult(
                command="failures.clear",
                ok=False,
                severity="error",
                message="Failure marker clear service is unavailable.",
                errors=["Failure marker clear service is unavailable."],
                refresh_hint="failures",
            )
        lifecycle_group = self._active_failure_lifecycle_group(resolved, journal_key) if journal_key else None
        try:
            result = clearer(resolved, marker_paths=cleaned_paths or None, dry_run=dry_run)
        except Exception as exc:
            return CommandResult(
                command="failures.clear",
                ok=False,
                severity="error",
                message=f"Failure marker clear failed: {exc}",
                errors=[str(exc)],
                refresh_hint="failures",
            )
        errors = [str(item) for item in result.get("errors") or [] if str(item).strip()]
        planned_count = len(result.get("planned") or [])
        moved_count = int(result.get("markers") or 0)
        ok = not errors
        if dry_run:
            message = f"Failure marker clear preview found {planned_count} marker(s)."
        else:
            message = f"Failure marker clear moved {moved_count} marker(s) out of the active marker folder."
        if errors:
            message = "Failure marker clear blocked; review errors before retrying."
        data = dict(result)
        data["scope"] = scope
        data["writes_failure_markers"] = (not dry_run) and moved_count > 0
        data["touches_media"] = False
        data["safe_next_action"] = (
            "Refresh Queue/Reports. Cleared sources can be retried on the next backend queue build."
            if ok and not dry_run
            else "Review the dry-run plan, then confirm clear only after the failure root cause is understood."
        )
        warnings = [str(item.get("reason")) for item in result.get("skipped") or [] if isinstance(item, dict) and item.get("reason")]
        if ok and not dry_run and journal_key:
            try:
                event = failure_resolution_append_event(
                    resolved,
                    journal_key=journal_key,
                    transition="complete_step",
                    step_id="clear_markers",
                    reason="Failure markers cleared after operator confirmation.",
                    operator_note="",
                    group=lifecycle_group or {"journal_key": journal_key},
                )
                data["resolution_journal_event"] = event
            except Exception as exc:
                warnings.append(f"Failure resolution timeline event could not be recorded: {exc}")
        return CommandResult(
            command="failures.clear",
            ok=ok,
            severity="info" if ok else "error",
            message=message,
            errors=errors,
            warnings=warnings,
            refresh_hint="failures",
            data=data,
        )

    def archive_failure_evidence(self, resolved: ResolvedPaths, request: dict[str, Any]) -> CommandResult:
        """Move active failure evidence into a manifest-backed archive after preview confirmation."""
        command = "failures.archive_evidence"
        scope = str(request.get("scope") or "all_active")
        if scope != "all_active":
            return CommandResult(
                command=command,
                ok=False,
                severity="error",
                message="'scope' must be all_active.",
                errors=["'scope' must be all_active."],
                refresh_hint="failures",
            )
        for key in ("dry_run", "include_markers", "include_reports"):
            if not isinstance(request.get(key), bool):
                return CommandResult(
                    command=command,
                    ok=False,
                    severity="error",
                    message=f"'{key}' must be a JSON boolean.",
                    errors=[f"'{key}' must be a JSON boolean."],
                    refresh_hint="failures",
                )
        if "confirm_archive" in request and not isinstance(request.get("confirm_archive"), bool):
            return CommandResult(
                command=command,
                ok=False,
                severity="error",
                message="'confirm_archive' must be a JSON boolean.",
                errors=["'confirm_archive' must be a JSON boolean."],
                refresh_hint="failures",
            )
        dry_run = request.get("dry_run") is True
        include_markers = request.get("include_markers") is True
        include_reports = request.get("include_reports") is True
        if not include_markers and not include_reports:
            return CommandResult(
                command=command,
                ok=False,
                severity="error",
                message="Failure evidence archive requires include_markers or include_reports.",
                errors=["Failure evidence archive requires include_markers or include_reports."],
                refresh_hint="failures",
            )
        confirm_archive = request.get("confirm_archive") is True
        reason = str(request.get("reason") or "").strip()
        fingerprint = str(request.get("dry_run_fingerprint") or "").strip()
        journal_key = str(request.get("journal_key") or "").strip()
        if not dry_run and not confirm_archive:
            return CommandResult(
                command=command,
                ok=False,
                severity="error",
                message="Failure evidence archive requires confirm_archive: true.",
                errors=["Failure evidence archive requires confirm_archive: true."],
                refresh_hint="failures",
                data={"scope": scope, "dry_run": dry_run, "touches_media": False},
            )
        if not dry_run and not reason:
            return CommandResult(
                command=command,
                ok=False,
                severity="error",
                message="Failure evidence archive requires a non-empty reason.",
                errors=["Failure evidence archive requires a non-empty reason."],
                refresh_hint="failures",
                data={"scope": scope, "dry_run": dry_run, "touches_media": False},
            )
        if not dry_run and not fingerprint:
            return CommandResult(
                command=command,
                ok=False,
                severity="error",
                message="Failure evidence archive requires a matching dry_run_fingerprint.",
                errors=["Failure evidence archive requires a matching dry_run_fingerprint."],
                refresh_hint="failures",
                data={"scope": scope, "dry_run": dry_run, "touches_media": False},
            )
        archiver = getattr(self.service, "archive_failure_evidence", None)
        if not callable(archiver):
            return CommandResult(
                command=command,
                ok=False,
                severity="error",
                message="Failure evidence archive service is unavailable.",
                errors=["Failure evidence archive service is unavailable."],
                refresh_hint="failures",
            )
        lifecycle_group = self._active_failure_lifecycle_group(resolved, journal_key) if journal_key else None
        try:
            result = archiver(
                resolved,
                scope=scope,
                include_markers=include_markers,
                include_reports=include_reports,
                dry_run=dry_run,
                dry_run_fingerprint=fingerprint,
                reason=reason,
            )
        except Exception as exc:
            return CommandResult(
                command=command,
                ok=False,
                severity="error",
                message=f"Failure evidence archive failed: {exc}",
                errors=[str(exc)],
                refresh_hint="failures",
            )
        errors = [str(item) for item in result.get("errors") or [] if str(item).strip()]
        planned_count = len(result.get("planned") or [])
        moved_markers = int(result.get("markers") or 0)
        moved_reports = int(result.get("reports") or 0)
        ok = not errors
        if dry_run:
            message = f"Failure evidence archive preview found {planned_count} file(s)."
        else:
            message = f"Failure evidence archive moved {moved_markers} marker(s) and {moved_reports} report(s)."
        if errors:
            message = "Failure evidence archive blocked; review errors before retrying."
        data = dict(result)
        data["scope"] = scope
        data["writes_failure_evidence"] = (not dry_run) and (moved_markers + moved_reports > 0)
        data["touches_media"] = False
        data["safe_next_action"] = (
            "Refresh Reports. Archived evidence remains available from the clear manifest archive."
            if ok and not dry_run
            else "Review the preview fingerprint and reason before confirming archive."
        )
        warnings = [str(item.get("reason")) for item in result.get("skipped") or [] if isinstance(item, dict) and item.get("reason")]
        if ok and not dry_run and journal_key:
            try:
                event = failure_resolution_append_event(
                    resolved,
                    journal_key=journal_key,
                    transition="complete_step",
                    step_id="archive_evidence",
                    reason=reason or "Failure evidence archived after operator confirmation.",
                    operator_note="",
                    group=lifecycle_group or {"journal_key": journal_key},
                )
                data["resolution_journal_event"] = event
            except Exception as exc:
                warnings.append(f"Failure resolution timeline event could not be recorded: {exc}")
        return CommandResult(
            command=command,
            ok=ok,
            severity="info" if ok else "error",
            message=message,
            errors=errors,
            warnings=warnings,
            refresh_hint="failures",
            data=data,
        )

    def _active_failure_lifecycle_group(self, resolved: ResolvedPaths, journal_key: str) -> dict[str, Any] | None:
        normalized = str(journal_key or "").strip().casefold()
        if not normalized:
            return None
        seen: set[str] = set()
        for source_kind in ("markers", "latest_json"):
            try:
                payload = self.get_failure_preview(resolved, source_kind=source_kind, limit=500).to_mapping()
            except Exception:
                continue
            groups = payload.get("resolution_groups")
            for group in groups if isinstance(groups, list) else []:
                if not isinstance(group, dict):
                    continue
                key = str(group.get("journal_key") or group.get("group_key") or "").strip()
                if not key:
                    continue
                lower_key = key.casefold()
                if lower_key in seen:
                    continue
                seen.add(lower_key)
                if lower_key == normalized:
                    return group
        return None

    def transition_failure_lifecycle(self, resolved: ResolvedPaths, request: dict[str, Any]) -> CommandResult:
        """Record operator failure-resolution lifecycle state without touching evidence or media files."""
        command = "failures.lifecycle"
        for key in ("dry_run", "confirm_transition"):
            if key in request and not isinstance(request.get(key), bool):
                return CommandResult(
                    command=command,
                    ok=False,
                    severity="error",
                    message=f"'{key}' must be a JSON boolean.",
                    errors=[f"'{key}' must be a JSON boolean."],
                    refresh_hint="failures",
                )
        journal_key = str(request.get("journal_key") or "").strip()
        transition = str(request.get("transition") or "").strip()
        step_id = str(request.get("step_id") or "").strip()
        reason = str(request.get("reason") or "").strip()
        operator_note = str(request.get("operator_note") or "").strip()
        dry_run = request.get("dry_run") is True
        confirm_transition = request.get("confirm_transition") is True
        supplied_fingerprint = str(request.get("dry_run_fingerprint") or "").strip()
        if not journal_key:
            return CommandResult(
                command=command,
                ok=False,
                severity="error",
                message="Failure lifecycle transition requires journal_key.",
                errors=["Failure lifecycle transition requires journal_key."],
                refresh_hint="failures",
            )
        if transition not in FAILURE_LIFECYCLE_TRANSITIONS:
            return CommandResult(
                command=command,
                ok=False,
                severity="error",
                message=f"Unsupported failure lifecycle transition: {transition}",
                errors=[f"Unsupported failure lifecycle transition: {transition}"],
                refresh_hint="failures",
            )
        if transition in FAILURE_LIFECYCLE_REASON_REQUIRED and not reason:
            return CommandResult(
                command=command,
                ok=False,
                severity="error",
                message=f"Failure lifecycle transition '{transition}' requires a non-empty reason.",
                errors=[f"Failure lifecycle transition '{transition}' requires a non-empty reason."],
                refresh_hint="failures",
            )
        group = self._active_failure_lifecycle_group(resolved, journal_key)
        if group is None:
            return CommandResult(
                command=command,
                ok=False,
                severity="error",
                message="Failure lifecycle group is no longer active; refresh Reports before changing state.",
                errors=["Failure lifecycle group is no longer active; refresh Reports before changing state."],
                refresh_hint="failures",
                data={"journal_key": journal_key, "touches_media": False},
            )
        preview = failure_lifecycle_transition_preview(
            journal_key=journal_key,
            transition=transition,
            step_id=step_id,
            group=group,
            reason=reason,
        )
        blockers = [str(item) for item in preview.get("blockers") or [] if str(item).strip()]
        if dry_run:
            data = {
                **preview,
                "dry_run": True,
                "touches_media": False,
                "writes_failure_resolution_journal": False,
            }
            return CommandResult(
                command=command,
                ok=not blockers,
                severity="info" if not blockers else "warning",
                message=(
                    f"Failure lifecycle preview ready for {transition}."
                    if not blockers
                    else "Failure lifecycle transition is blocked; review verification before confirming."
                ),
                errors=blockers,
                refresh_hint="failures",
                data=data,
            )
        if not confirm_transition:
            return CommandResult(
                command=command,
                ok=False,
                severity="error",
                message="Failure lifecycle transition requires confirm_transition: true.",
                errors=["Failure lifecycle transition requires confirm_transition: true."],
                refresh_hint="failures",
                data={"journal_key": journal_key, "touches_media": False},
            )
        if transition in FAILURE_LIFECYCLE_PREVIEW_REQUIRED:
            expected_fingerprint = failure_lifecycle_fingerprint(
                journal_key=journal_key,
                transition=transition,
                step_id=step_id,
                group=group,
                reason=reason,
            )
            if not supplied_fingerprint:
                return CommandResult(
                    command=command,
                    ok=False,
                    severity="error",
                    message="Failure lifecycle transition requires a matching dry_run_fingerprint.",
                    errors=["Failure lifecycle transition requires a matching dry_run_fingerprint."],
                    refresh_hint="failures",
                    data={"journal_key": journal_key, "touches_media": False},
                )
            if supplied_fingerprint != expected_fingerprint:
                return CommandResult(
                    command=command,
                    ok=False,
                    severity="error",
                    message="Failure lifecycle transition fingerprint mismatch; preview again before confirming.",
                    errors=["Failure lifecycle transition fingerprint mismatch; preview again before confirming."],
                    refresh_hint="failures",
                    data={"journal_key": journal_key, "touches_media": False},
                )
        if blockers:
            return CommandResult(
                command=command,
                ok=False,
                severity="error",
                message="Failure lifecycle transition is blocked by current verification.",
                errors=blockers,
                refresh_hint="failures",
                data={**preview, "dry_run": False, "touches_media": False},
            )
        try:
            event = failure_resolution_append_event(
                resolved,
                journal_key=journal_key,
                transition=transition,
                step_id=step_id,
                reason=reason,
                operator_note=operator_note,
                group=group,
                dry_run_fingerprint=supplied_fingerprint,
            )
        except Exception as exc:
            return CommandResult(
                command=command,
                ok=False,
                severity="error",
                message=f"Failure lifecycle transition failed: {exc}",
                errors=[str(exc)],
                refresh_hint="failures",
            )
        data = {
            "schema_version": "failure_lifecycle_transition_result.v1",
            "dry_run": False,
            "journal_key": journal_key,
            "transition": transition,
            "lifecycle_state": event.get("lifecycle_state"),
            "event": event,
            "journal_path": str(failure_resolution_journal_path(resolved)),
            "touches_media": False,
            "writes_failure_resolution_journal": True,
            "safe_next_action": "Refresh Reports and continue from the selected issue playbook.",
        }
        return CommandResult(
            command=command,
            ok=True,
            severity="info",
            message=f"Failure lifecycle moved to {event.get('lifecycle_state')}.",
            refresh_hint="failures",
            data=data,
        )

__all__ = [
    "FailureFacadeMixin",
]
