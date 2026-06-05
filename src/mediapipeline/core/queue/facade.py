"""Queue preview and source-open facade adapter."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from mediapipeline.core.queue.file_overrides import read_file_overrides
from mediapipeline.core.queue.priority_manifest import get_manifest_entry, get_manifest_level, read_priority_manifest
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
from mediapipeline.desktop.models import QueueRecord, ResolvedPaths

if TYPE_CHECKING:
    from mediapipeline.desktop.application.dto_commands import CommandResult
    from mediapipeline.desktop.application.dto_inventory import QueuePreviewDto


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


def _queue_phase_for_manifest_level(row: dict[str, object], level: str) -> str:
    media_kind = _queue_manifest_media_kind(row)
    if level == "hold":
        return "hold"
    if level == "low":
        return "low"
    if level == "high" or _queue_manifest_bool(row.get("is_priority")):
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
        entry = get_manifest_entry(priority_manifest, source_path) or {}
        row = dict(raw_row)
        row["manifest_priority_level"] = level
        if "position" in entry:
            row["manual_order_position"] = entry.get("position")
        row["phase"] = _queue_phase_for_manifest_level(row, level)
        rows.append(row)
    return rows


def _queue_priority_count_for_rows(rows: list[dict[str, object]]) -> int:
    count = 0
    for row in rows:
        level = str(row.get("manifest_priority_level") or "normal").strip().casefold()
        if level == "high" or (_queue_manifest_bool(row.get("is_priority")) and level == "normal"):
            count += 1
    return count


def _queue_preview_dto(**fields: object) -> "QueuePreviewDto":
    from mediapipeline.desktop.application.dto_inventory import QueuePreviewDto

    return QueuePreviewDto(**fields)


def _command_result(**fields: object) -> "CommandResult":
    from mediapipeline.desktop.application.dto_commands import CommandResult

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
        priority_manifest: dict[str, object] | None = None
        if resolved.priority_manifest_path is not None:
            priority_manifest = read_priority_manifest(resolved.priority_manifest_path)
        file_override_manifest = None
        if resolved.file_overrides_path is not None:
            file_override_manifest = read_file_overrides(resolved.file_overrides_path)
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
        warnings = queue_preview_warnings(rows)
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

    @staticmethod
    def _queue_record_to_row(record: QueueRecord) -> dict[str, object]:
        return queue_record_to_row(record)

    def open_queue_location(self, resolved: ResolvedPaths, request: dict[str, object]) -> CommandResult:
        """Open a path selected from the backend queue snapshot, not a raw frontend path."""
        row_key = str(request.get("row_key") or "").strip().casefold()
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
