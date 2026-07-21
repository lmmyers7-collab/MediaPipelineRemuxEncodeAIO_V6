"""Queue preview and source-open facade adapter."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from mediapipeline.core.queue.file_overrides import FileOverrideManifestReadError, read_file_overrides
from mediapipeline.core.paths.queue_input_fingerprint import (
    queue_input_consistency,
    queue_input_fingerprint,
)
from mediapipeline.core.queue.priority_manifest import (
    PriorityManifestReadError,
    get_manifest_entry,
    get_manifest_level,
    has_manifest_priority_entry,
    read_priority_manifest,
)
from mediapipeline.core.queue.priority_export import (
    PriorityQueueExportStore,
    priority_export_public_status,
)
from mediapipeline.core.queue.policy import (
    INVALID_QUEUE_SNAPSHOT_WARNING,
    NO_QUEUE_SNAPSHOT_WARNING,
    QUEUE_OPEN_SCOPES,
    QUEUE_OPEN_TARGETS,
    QUEUE_RUNTIME_OUTCOME_EVENT_LIMIT,
    QUEUE_PREVIEW_SERVICE_WARNING,
    normalize_queue_open_scope,
    normalize_queue_open_target,
    queue_apply_runtime_outcomes,
    queue_excluded_row_key,
    queue_open_disallowed_scope_result,
    queue_open_disallowed_target_result,
    queue_open_exception_result,
    queue_open_path,
    queue_open_path_missing_result,
    queue_open_path_service_unavailable_result,
    queue_open_requires_row_result,
    queue_open_row_missing_result,
    queue_open_success_result,
    queue_preview_metadata,
    queue_preview_rows,
    queue_preview_warnings,
    queue_record_to_row,
    queue_row_key,
    queue_source_scan_progress_payload,
)
from mediapipeline.core.paths.contracts import ResolvedPaths
from mediapipeline.core.queue.contracts import QueueRecord
if TYPE_CHECKING:
    from mediapipeline.core.kernel.dto_commands import CommandResult
    from mediapipeline.core.kernel.dto_inventory import QueuePreviewDto


def _queue_manifest_bool(value: object) -> bool:
    if isinstance(value, bool):
        return value
    if value in (None, ""):
        return False
    return str(value).strip().casefold() in {"1", "true", "yes", "y", "on"}


def _queue_manifest_media_kind(row: dict[str, object]) -> str:
    media_kind = str(row.get("media_kind") or "").strip().casefold()
    if media_kind in {"movie", "tv"}:
        return media_kind
    media_type = str(row.get("media_type") or "").strip().casefold()
    if media_type == "tv" or _queue_manifest_bool(row.get("is_tv")):
        return "tv"
    return "movie"


def _queue_phase_for_manifest_level(row: dict[str, object], level: str, *, manifest_explicit: bool = False) -> str:
    media_kind = _queue_manifest_media_kind(row)
    if level == "hold":
        return "hold"
    if level == "low":
        return "low"
    if level == "high" or (_queue_manifest_bool(row.get("is_priority")) and not manifest_explicit):
        return "priority_tv" if media_kind == "tv" else "priority_movie"
    return "tv" if media_kind == "tv" else "movie"


def _queue_rows_with_priority_manifest(
    raw_rows: object,
    priority_manifest: dict[str, object],
) -> list[object]:
    if not isinstance(raw_rows, list):
        return []
    if not priority_manifest.get("entries"):
        priority_manifest = {"version": 1, "entries": {}}

    rows: list[object] = []
    for raw_row in raw_rows:
        if not isinstance(raw_row, dict):
            rows.append(raw_row)
            continue
        source_path = str(raw_row.get("source_path") or "").strip()
        if not source_path:
            rows.append(raw_row)
            continue
        level = get_manifest_level(priority_manifest, source_path)
        manifest_explicit = has_manifest_priority_entry(priority_manifest, source_path)
        entry = get_manifest_entry(priority_manifest, source_path) or {}
        row = dict(raw_row)
        row["manifest_priority_level"] = level
        row["manifest_priority_explicit"] = manifest_explicit
        if "position" in entry:
            row["manual_order_position"] = entry.get("position")
        row["phase"] = _queue_phase_for_manifest_level(row, level, manifest_explicit=manifest_explicit)
        rows.append(row)
    return rows


def _queue_priority_count_for_rows(rows: list[dict[str, object]]) -> int:
    count = 0
    for row in rows:
        level = str(row.get("manifest_priority_level") or "normal").strip().casefold()
        manifest_explicit = _queue_manifest_bool(row.get("manifest_priority_explicit"))
        if level == "high" or (_queue_manifest_bool(row.get("is_priority")) and level == "normal" and not manifest_explicit):
            count += 1
    return count


def _queue_row_is_operator_runnable(row: dict[str, object]) -> bool:
    return str(row.get("operator_status") or "").strip().casefold() in {"ready", "priority ready"}


def _queue_preview_dto(**fields: object) -> QueuePreviewDto:
    from mediapipeline.core.kernel.dto_inventory import QueuePreviewDto

    return QueuePreviewDto(**fields)


def _command_result(**fields: object) -> CommandResult:
    from mediapipeline.core.kernel.dto_commands import CommandResult

    return CommandResult(**fields)


class QueueFacadeMixin:
    """Read-only queue snapshot adapter for the application facade."""

    def get_queue_preview(self, resolved: ResolvedPaths) -> QueuePreviewDto:
        """Return the last queue snapshot without spawning a dry-run process."""
        queue_scan_status, source_inventory = self._queue_scan_artifacts(resolved)
        snapshot_path = resolved.queue_snapshot_path
        if not snapshot_path or not snapshot_path.exists():
            return self._queue_preview_with_progress_warning(
                str(snapshot_path or ""),
                NO_QUEUE_SNAPSHOT_WARNING,
                queue_scan_status=queue_scan_status,
                source_inventory=source_inventory,
            )
        read_snapshot = getattr(self.service, "_read_queue_snapshot", None)
        row_factory = getattr(self.service, "_queue_record_from_snapshot_row", None)
        if not callable(read_snapshot) or not callable(row_factory):
            return self._queue_preview_with_progress_warning(
                str(snapshot_path),
                QUEUE_PREVIEW_SERVICE_WARNING,
                status="blocked",
                queue_scan_status=queue_scan_status,
                source_inventory=source_inventory,
            )
        try:
            snapshot = read_snapshot(snapshot_path)
        except Exception as exc:
            return self._queue_preview_with_progress_warning(
                str(snapshot_path),
                f"Queue snapshot could not be read: {exc}",
                queue_scan_status=queue_scan_status,
                source_inventory=source_inventory,
            )
        if not isinstance(snapshot, dict):
            return self._queue_preview_with_progress_warning(
                str(snapshot_path),
                INVALID_QUEUE_SNAPSHOT_WARNING,
                queue_scan_status=queue_scan_status,
                source_inventory=source_inventory,
            )
        input_consistency = queue_input_consistency(resolved, snapshot)
        snapshot_has_input_fingerprint = bool(str(snapshot.get("queue_input_fingerprint") or "").strip())
        inputs_current = input_consistency.get("status") == "current" or not snapshot_has_input_fingerprint
        priority_manifest: dict[str, object] | None = None
        if inputs_current and resolved.priority_manifest_path is not None:
            try:
                priority_manifest = read_priority_manifest(resolved.priority_manifest_path, fail_closed=True)
            except PriorityManifestReadError as exc:
                return self._queue_preview_with_progress_warning(
                    str(snapshot_path),
                    f"Queue priority manifest could not be read; queue preview is blocked until repaired: {exc}",
                    status="blocked",
                    queue_scan_status=queue_scan_status,
                    source_inventory=source_inventory,
                )
        file_override_manifest = None
        if inputs_current and resolved.file_overrides_path is not None:
            try:
                file_override_manifest = read_file_overrides(resolved.file_overrides_path)
            except FileOverrideManifestReadError as exc:
                return self._queue_preview_with_progress_warning(
                    str(snapshot_path),
                    f"Queue file overrides could not be read; queue preview is blocked until repaired: {exc}",
                    status="blocked",
                    queue_scan_status=queue_scan_status,
                    source_inventory=source_inventory,
                )
        raw_rows = (
            _queue_rows_with_priority_manifest(snapshot.get("rows") or [], priority_manifest)
            if priority_manifest is not None
            else snapshot.get("rows") or []
        )
        rows = queue_preview_rows(
            raw_rows,
            row_factory,
            file_override_manifest=file_override_manifest,
        )
        runtime_events: list[dict[str, object]] = []
        runtime_outcome_warning = ""
        read_events = getattr(self.service, "read_pipeline_events_tail", None)
        if callable(read_events):
            try:
                runtime_events = read_events(resolved, line_count=QUEUE_RUNTIME_OUTCOME_EVENT_LIMIT)
            except Exception as exc:
                runtime_outcome_warning = f"Runtime outcome history could not be read: {exc}"
        elif resolved.event_file:
            runtime_outcome_warning = "Runtime outcome history reader is not available."
        rows = queue_apply_runtime_outcomes(rows, runtime_events)
        normal_rows = rows
        warnings = queue_preview_warnings(normal_rows)
        if input_consistency.get("status") != "current":
            changed = ", ".join(str(item) for item in input_consistency.get("changed_inputs") or [])
            if snapshot_has_input_fingerprint:
                warnings.append(
                    "Queue inputs changed after this snapshot was produced; launch is blocked until Queue scan completes"
                    + (f" ({changed})." if changed else ".")
                )
            else:
                warnings.append(
                    "This legacy Queue snapshot has no input fingerprint; launch is blocked until Queue scan completes."
                )
        if runtime_outcome_warning:
            warnings.append(runtime_outcome_warning)
        metadata_snapshot = dict(snapshot)
        metadata_snapshot["rows"] = raw_rows
        if priority_manifest is not None:
            metadata_snapshot["priority_count"] = _queue_priority_count_for_rows(rows)
        metadata = queue_preview_metadata(
            metadata_snapshot,
            rows,
            snapshot_path=snapshot_path,
            runtime_event_count=len(runtime_events),
            runtime_outcome_source=str(resolved.event_file or ""),
            runtime_outcome_warning=runtime_outcome_warning,
        )
        metadata["shown_row_count"] = len(rows)
        metadata["total_row_count"] = int(metadata.get("total_row_count") or len(normal_rows))
        metadata["runnable_count"] = sum(1 for row in normal_rows if _queue_row_is_operator_runnable(row))
        metadata["normal_queue_visible_count"] = len(normal_rows)
        metadata["dedicated_rerun_visible_count"] = 0
        metadata["queue_sources"] = ["normal_queue"]
        metadata["rerun_correlation"] = {}
        request_id = str(snapshot.get("desktop_queue_preview_request_id") or "").strip()
        scan_failed = str(queue_scan_status.get("status") or "").casefold() == "failed"
        fallback_used = bool(snapshot.get("desktop_queue_snapshot_fallback_used")) or scan_failed
        fallback_reason = str(snapshot.get("desktop_queue_snapshot_fallback_reason") or "").strip()
        if scan_failed and not fallback_reason:
            fallback_reason = str(queue_scan_status.get("message") or "The latest Queue scan failed; showing cached evidence.")
        metadata["queue_preview_request_id"] = request_id
        metadata["queue_snapshot_origin"] = str(snapshot.get("queue_snapshot_origin") or "unknown")
        metadata["queue_snapshot_fallback"] = {
            "schema_version": "desktop_queue_snapshot_fallback.v1",
            "used": fallback_used,
            "reason": fallback_reason,
            "failed_scan_id": str(queue_scan_status.get("scan_id") or "") if scan_failed else "",
            "cached_request_id": request_id if fallback_used else "",
        }
        metadata["queue_input_consistency"] = input_consistency
        metadata["queue_plan_fingerprint"] = str(snapshot.get("queue_plan_fingerprint") or "")
        metadata["queue_plan_fingerprint_schema"] = str(snapshot.get("queue_plan_fingerprint_schema") or "")
        pending_health = snapshot.get("pending_publish_index_health")
        metadata["pending_publish_index_health"] = dict(pending_health) if isinstance(pending_health, dict) else {}
        pending_backpressure = snapshot.get("pending_publish_backpressure")
        metadata["pending_publish_backpressure"] = (
            dict(pending_backpressure) if isinstance(pending_backpressure, dict) else {}
        )
        queue_progress = queue_source_scan_progress_payload(
            source=str(snapshot_path),
            row_count=len(rows),
            metadata=metadata,
            warnings=warnings,
        )
        return _queue_preview_dto(
            rows=rows,
            source=str(snapshot_path),
            queue_scan_status=queue_scan_status,
            source_inventory=source_inventory,
            queue_progress=queue_progress,
            progress_bars=list(queue_progress["progress_bars"]),
            **metadata,
            warnings=warnings,
        )

    @staticmethod
    def _queue_preview_with_progress_warning(
        source: str,
        warning: str,
        *,
        status: str = "warning",
        queue_scan_status: dict[str, object] | None = None,
        source_inventory: dict[str, object] | None = None,
    ) -> QueuePreviewDto:
        progress = queue_source_scan_progress_payload(
            source=source,
            warnings=[warning],
            status=status,
            detail=warning,
        )
        return _queue_preview_dto(
            source=source,
            queue_scan_status=dict(queue_scan_status or {}),
            source_inventory=dict(source_inventory or {}),
            normal_queue_visible_count=0,
            dedicated_rerun_visible_count=0,
            queue_sources=["normal_queue"],
            rerun_correlation={},
            warnings=[warning],
            queue_progress=progress,
            progress_bars=list(progress["progress_bars"]),
        )

    def _queue_scan_artifacts(self, resolved: ResolvedPaths) -> tuple[dict[str, object], dict[str, object]]:
        status_reader = getattr(self.service, "read_queue_scan_status", None)
        inventory_reader = getattr(self.service, "read_queue_source_inventory", None)
        queue_scan_status: dict[str, object] = {}
        source_inventory: dict[str, object] = {}
        if callable(status_reader):
            try:
                status = status_reader(resolved)
                if isinstance(status, dict):
                    queue_scan_status = status
            except Exception as exc:
                queue_scan_status = {
                    "schema_version": "desktop_queue_scan_status.v1",
                    "status": "unavailable",
                    "phase": "unavailable",
                    "message": f"Queue scan status could not be read: {exc}",
                    "errors": [str(exc)],
                }
        if callable(inventory_reader):
            try:
                inventory = inventory_reader(resolved)
                if isinstance(inventory, dict):
                    source_inventory = inventory
            except Exception as exc:
                source_inventory = {
                    "schema_version": "desktop_queue_source_inventory.v1",
                    "status": "unavailable",
                    "curation_state": "unavailable",
                    "launchable": False,
                    "rows": [],
                    "summary_lines": [f"Source inventory could not be read: {exc}"],
                    "errors": [str(exc)],
                }
        return queue_scan_status, source_inventory

    def start_queue_scan(self, resolved: ResolvedPaths, request: dict[str, object]) -> CommandResult:
        scanner = getattr(self.service, "start_queue_source_scan", None)
        if not callable(scanner):
            return _command_result(
                command="queue.scan",
                ok=False,
                severity="error",
                message="Queue source scan service is not available.",
                errors=["queue_source_scan_service_unavailable"],
                refresh_hint="queue",
            )
        result = scanner(resolved, request)
        ok = bool(result.get("ok"))
        duplicate = bool(result.get("duplicate"))
        status = dict(result.get("status") or {}) if isinstance(result.get("status"), dict) else {}
        message = str(result.get("message") or ("Queue source scan started." if ok else "Queue source scan failed."))
        errors = [str(item) for item in result.get("errors") or [] if str(item).strip()]
        severity = "info" if ok else "error"
        if duplicate:
            severity = "warning"
        return _command_result(
            command="queue.scan",
            ok=ok,
            severity=severity,
            message=message,
            errors=errors,
            refresh_hint="queue",
            data={
                "schema_version": "desktop_queue_scan_command.v1",
                "duplicate": duplicate,
                "scan_id": str(status.get("scan_id") or ""),
                "status": status,
            },
        )

    def export_priority_queue(self, resolved: ResolvedPaths) -> CommandResult:
        exporter = getattr(self.service, "export_priority_queue_snapshot", None)
        if not callable(exporter):
            return _command_result(
                command="queue.priority_export",
                ok=False,
                severity="error",
                message="Priority queue export service is not available.",
                errors=["priority_export_service_unavailable"],
                refresh_hint="queue",
            )
        try:
            artifact = exporter(resolved)
        except Exception as exc:
            return _command_result(
                command="queue.priority_export",
                ok=False,
                severity="error",
                message=f"Priority queue export failed: {exc}",
                errors=["priority_export_failed"],
                refresh_hint="queue",
            )
        public = priority_export_public_status(artifact)
        ready = str(artifact.get("status") or "").casefold() == "ready"
        return _command_result(
            command="queue.priority_export",
            ok=ready,
            severity="ok" if ready else "warning",
            message=str(artifact.get("message") or "Priority queue export is not ready."),
            errors=[] if ready else [str(artifact.get("reason_code") or "priority_export_blocked")],
            refresh_hint="queue",
            data=public,
        )

    def get_priority_queue_export(self, resolved: ResolvedPaths) -> dict[str, object]:
        if resolved.state_root is None:
            payload = {
                "schema_version": "priority_queue_export.v1",
                "status": "missing",
                "ready": False,
                "reason_code": "priority_export_state_root_missing",
                "message": "Priority queue export requires LocalBase/State to be configured.",
                "count": 0,
                "queue_scope": "priority_export",
            }
        else:
            payload = PriorityQueueExportStore(resolved.state_root).latest_status()
            if str(payload.get("status") or "").casefold() == "ready":
                current_inputs = queue_input_fingerprint(resolved)
                if (
                    current_inputs.get("status") != "current"
                    or str(current_inputs.get("fingerprint") or "")
                    != str(payload.get("queue_input_fingerprint") or "")
                ):
                    payload = {
                        **payload,
                        "status": "stale",
                        "ready": False,
                        "reason_code": "priority_export_input_stale",
                        "message": "Queue inputs changed after this export. Prepare a new priority export.",
                    }
        return priority_export_public_status(payload)

    @staticmethod
    def _queue_record_to_row(record: QueueRecord) -> dict[str, object]:
        return queue_record_to_row(record)

    def open_queue_location(self, resolved: ResolvedPaths, request: dict[str, object]) -> CommandResult:
        """Open a path selected from the backend queue snapshot, not a raw frontend path."""
        # Queue row keys use the unit separator as a field delimiter.  A
        # route-less row legitimately ends with that delimiter, and Python's
        # whitespace-only ``strip()`` treats it as removable control space.
        # Trim only transport whitespace so the opaque backend-issued key
        # retains its complete identity.
        row_key = str(request.get("row_key") or "").strip(" \t\r\n").casefold()
        target = normalize_queue_open_target(request.get("target"))
        row_scope = normalize_queue_open_scope(request.get("row_scope"))
        if not row_key:
            return queue_open_requires_row_result()
        if row_scope not in QUEUE_OPEN_SCOPES:
            return queue_open_disallowed_scope_result(row_scope)
        if target not in QUEUE_OPEN_TARGETS:
            return queue_open_disallowed_target_result()

        preview = self.get_queue_preview(resolved)
        selected = self._queue_open_selected_row(preview, row_key, row_scope)
        if selected is None:
            return queue_open_row_missing_result(row_key)
        path = self._queue_open_path(selected, target)
        if path is None:
            return queue_open_path_missing_result(target, row_key, row_scope)
        opener = getattr(self.service, "open_path", None)
        if not callable(opener):
            return queue_open_path_service_unavailable_result(target, row_key, path, row_scope)
        try:
            opener(path)
        except Exception as exc:
            return queue_open_exception_result(target, row_key, path, exc, row_scope)
        return queue_open_success_result(target, row_key, path, row_scope)

    @staticmethod
    def _queue_open_path(row: dict[str, object], target: str) -> Path | None:
        return queue_open_path(row, target)

    @staticmethod
    def _queue_open_selected_row(preview: QueuePreviewDto, row_key: str, row_scope: str) -> dict[str, object] | None:
        if row_scope == "excluded":
            return next((row for row in preview.excluded_rows if queue_excluded_row_key(row) == row_key), None)
        return next((row for row in preview.rows if queue_row_key(row) == row_key), None)

__all__ = [
    "QueueFacadeMixin",
]
