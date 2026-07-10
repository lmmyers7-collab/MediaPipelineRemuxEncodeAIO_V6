"""Queue preview and source-open facade adapter."""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING

from mediapipeline.core.queue.file_overrides import FileOverrideManifestReadError, read_file_overrides
from mediapipeline.core.queue.priority_manifest import (
    PriorityManifestReadError,
    get_manifest_entry,
    get_manifest_level,
    has_manifest_priority_entry,
    read_priority_manifest,
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
from mediapipeline.core.status.active_jobs import active_job_detail_rows

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


def _active_csv_rerun_job_present(resolved: ResolvedPaths) -> bool:
    for row in active_job_detail_rows(resolved.active_jobs_path, max_items=20):
        text = " ".join(
            str(row.get(key) or "")
            for key in ("job_kind", "mode", "status", "command_line", "stdout_log", "stderr_log")
        ).casefold()
        if "rerun_csv" in text or "invoke-reruncsv.ps1" in text:
            status = str(row.get("status") or "").strip().casefold()
            if status not in {"completed", "exited", "failed", "killed", "stopped"}:
                return True
    return False


def _latest_rerun_manifest_path(resolved: ResolvedPaths) -> Path | None:
    if resolved.local_base is None:
        return None
    manifest_root = resolved.local_base / "RerunManifests"
    if not manifest_root.exists():
        return None
    try:
        manifests = sorted(
            manifest_root.glob("*.json"),
            key=lambda item: item.stat().st_mtime,
            reverse=True,
        )
    except OSError:
        return None
    return manifests[0] if manifests else None


def _read_latest_rerun_manifest(resolved: ResolvedPaths) -> tuple[Path, dict[str, object]] | None:
    manifest_path = _latest_rerun_manifest_path(resolved)
    if manifest_path is None:
        return None
    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict):
        return None
    return manifest_path, payload


def _rerun_manifest_text(value: object) -> str:
    return str(value or "").strip()


def _rerun_manifest_display_name(source_path: str, stage_path: str) -> str:
    display_path = stage_path or source_path
    if not display_path:
        return "CSV rerun item"
    return Path(display_path).name or display_path


def _rerun_manifest_row_reason(raw_row: dict[str, object], metadata: dict[str, object]) -> str:
    for key in ("reason", "status_reason", "blocked_reason", "failure_reason", "error", "error_message"):
        text = _rerun_manifest_text(raw_row.get(key) or metadata.get(key))
        if text:
            return text
    return ""


def _rerun_manifest_operator_fields(status: str, reason: str) -> dict[str, str]:
    status_key = _rerun_manifest_text(status).casefold()
    reason_key = _rerun_manifest_text(reason).casefold()
    if status_key in {"skipped", "skip", "disabled"}:
        return {
            "operator_status": "CSV rerun skipped",
            "operator_status_state": "skipped",
            "operator_severity": "muted",
            "operator_guidance": "This CSV rerun item was skipped by backend-owned scope or manifest evidence.",
            "queue_status": "skipped",
            "queue_status_label": "Skipped",
        }
    if status_key in {"failed", "error", "errored"}:
        return {
            "operator_status": "CSV rerun failed",
            "operator_status_state": "blocked",
            "operator_severity": "error",
            "operator_guidance": "Review the manifest reason and rerun logs before retrying this item.",
            "queue_status": "failed",
            "queue_status_label": "Failed",
        }
    if status_key in {"blocked", "invalid", "missing"} or "source file not found" in reason_key:
        return {
            "operator_status": "CSV rerun blocked",
            "operator_status_state": "blocked",
            "operator_severity": "error",
            "operator_guidance": "Fix the CSV row or source path before retrying this item.",
            "queue_status": "blocked",
            "queue_status_label": "Blocked",
        }
    if status_key in {"warning", "warn", "warnings"}:
        return {
            "operator_status": "CSV rerun warning",
            "operator_status_state": "warning",
            "operator_severity": "warning",
            "operator_guidance": "Review backend warning evidence before continuing this CSV rerun item.",
            "queue_status": "warning",
            "queue_status_label": "Warning",
        }
    if status_key in {"held", "hold"}:
        return {
            "operator_status": "CSV rerun held",
            "operator_status_state": "held",
            "operator_severity": "warning",
            "operator_guidance": "Release, reprioritize, or remove the held CSV rerun item before expecting progress.",
            "queue_status": "blocked",
            "queue_status_label": "Blocked",
        }
    if status_key in {"stopped", "stopped_after_current"}:
        return {
            "operator_status": "CSV rerun stopped",
            "operator_status_state": "stopped",
            "operator_severity": "warning",
            "operator_guidance": "This CSV rerun item is stopped until a backend-owned continuation starts pending rows.",
            "queue_status": "stopped",
            "queue_status_label": "Stopped",
        }
    if status_key in {"complete", "completed", "done", "succeeded", "success"}:
        return {
            "operator_status": "CSV rerun complete",
            "operator_status_state": "complete",
            "operator_severity": "ok",
            "operator_guidance": "This CSV rerun item has completed; use Completed or Pending Publish evidence for output details.",
            "queue_status": "completed",
            "queue_status_label": "Completed",
        }
    if status_key in {"published_replace_final", "published_non_overlap", "returned", "replaced"}:
        return {
            "operator_status": "CSV rerun returned",
            "operator_status_state": "returned",
            "operator_severity": "ok",
            "operator_guidance": "Backend evidence returned this CSV rerun output to final/library placement.",
            "queue_status": "replaced_returned",
            "queue_status_label": "Replaced / Returned",
        }
    if status_key in {"pending_publish", "parked"}:
        return {
            "operator_status": "CSV rerun Pending Publish",
            "operator_status_state": "parked",
            "operator_severity": "ok",
            "operator_guidance": "This CSV rerun output is parked in Pending Publish; final placement remains owned by Pending Publish drain evidence.",
            "queue_status": "pending_publish",
            "queue_status_label": "Pending Publish",
        }
    if status_key in {"review_workspace", "awaiting_review"}:
        return {
            "operator_status": "CSV rerun review workspace",
            "operator_status_state": "parked",
            "operator_severity": "ok",
            "operator_guidance": "This CSV rerun output is parked in the review workspace; promote it only after checking output evidence.",
            "queue_status": "review_workspace",
            "queue_status_label": "Review Workspace",
        }
    if status_key == "review":
        return {
            "operator_status": "CSV rerun review",
            "operator_status_state": "review",
            "operator_severity": "warning",
            "operator_guidance": "Review the CSV rerun manifest status and logs before taking action.",
            "queue_status": "warning",
            "queue_status_label": "Review",
        }
    if status_key in {"running", "active", "processing"}:
        return {
            "operator_status": "CSV rerun active",
            "operator_status_state": "running",
            "operator_severity": "warning",
            "operator_guidance": "This row is active in the CSV rerun queue; monitor Home progress and Close Readiness.",
            "queue_status": "active",
            "queue_status_label": "Active",
        }
    if status_key in {"priority", "priority_ready"}:
        return {
            "operator_status": "CSV rerun priority pending",
            "operator_status_state": "ready",
            "operator_severity": "ok",
            "operator_guidance": "This priority CSV rerun item is queued for processing.",
            "queue_status": "pending",
            "queue_status_label": "Pending",
        }
    if status_key in {"staged"}:
        return {
            "operator_status": "CSV rerun staged",
            "operator_status_state": "ready",
            "operator_severity": "ok",
            "operator_guidance": "This row is staged in the active CSV rerun queue. Monitor Home progress and Close Readiness.",
            "queue_status": "pending",
            "queue_status_label": "Pending",
        }
    if status_key in {"pending", "queued", ""}:
        return {
            "operator_status": "CSV rerun pending",
            "operator_status_state": "ready",
            "operator_severity": "ok",
            "operator_guidance": "This row is queued in the active CSV rerun manifest. Monitor Home progress and Close Readiness.",
            "queue_status": "pending",
            "queue_status_label": "Pending",
        }
    return {
        "operator_status": f"CSV rerun {status_key or 'status unknown'}",
        "operator_status_state": "review",
        "operator_severity": "warning",
        "operator_guidance": "Review the CSV rerun manifest status and logs before taking action.",
        "queue_status": "warning",
        "queue_status_label": "Warning",
    }


def _rerun_manifest_preview_rows(manifest: dict[str, object], manifest_path: Path) -> list[dict[str, object]]:
    raw_rows = manifest.get("rows")
    if not isinstance(raw_rows, list):
        return []
    total = len([row for row in raw_rows if isinstance(row, dict)])
    rows: list[dict[str, object]] = []
    for index, raw_row in enumerate((row for row in raw_rows if isinstance(row, dict)), start=1):
        queue_item = raw_row.get("queue_item") if isinstance(raw_row.get("queue_item"), dict) else {}
        metadata = queue_item.get("metadata") if isinstance(queue_item.get("metadata"), dict) else {}
        source_path = _rerun_manifest_text(raw_row.get("source_path") or queue_item.get("source_path"))
        stage_path = _rerun_manifest_text(raw_row.get("stage_path") or metadata.get("stage_path"))
        planned_output_path = _rerun_manifest_text(raw_row.get("planned_output_path") or metadata.get("planned_output_path"))
        media_kind = _rerun_manifest_text(raw_row.get("media_kind") or queue_item.get("media_kind") or "movie").casefold()
        media_type = "TV" if media_kind == "tv" else "Movie"
        status = _rerun_manifest_text(raw_row.get("status") or metadata.get("status") or "queued")
        reason = _rerun_manifest_row_reason(raw_row, metadata)
        operator_fields = _rerun_manifest_operator_fields(status, reason)
        route_reason = "Manifest-backed CSV rerun queue; processing route is decided by the nested pipeline per item."
        operator_guidance = operator_fields["operator_guidance"]
        if reason:
            route_reason = f"{route_reason} Manifest reason: {reason}"
            operator_guidance = f"{operator_guidance} Reason: {reason}"
        row = {
            "schema_version": "desktop_csv_rerun_queue_row.v1",
            "queue_source": "csv_rerun",
            "queue_phase": "csv_rerun",
            "rerun_batch_id": _rerun_manifest_text(manifest.get("batch_id")),
            "source_path": stage_path or source_path,
            "original_source_path": source_path,
            "stage_path": stage_path,
            "planned_output_path": planned_output_path,
            "destination_path": planned_output_path,
            "media_kind": media_kind or "movie",
            "media_type": media_type,
            "display_name": _rerun_manifest_display_name(source_path, stage_path),
            "relative_path": _rerun_manifest_text(queue_item.get("relative_path_sort") or stage_path or source_path),
            "root_path": _rerun_manifest_text(queue_item.get("root_path")),
            "source_root": _rerun_manifest_text(queue_item.get("root_path")),
            "route_name": "CSV rerun",
            "route_reason": route_reason,
            "operator_status": operator_fields["operator_status"],
            "operator_status_state": operator_fields["operator_status_state"],
            "operator_severity": operator_fields["operator_severity"],
            "operator_guidance": operator_guidance,
            "queue_status": operator_fields["queue_status"],
            "queue_status_label": operator_fields["queue_status_label"],
            "blocking_reason": reason if operator_fields["queue_status"] in {"blocked", "failed"} else "",
            "warning_reason": reason if operator_fields["queue_status"] in {"warning", "stopped", "awaiting_review", "pending_publish"} else "",
            "uses_pipeline_start": False,
            "queue_index": index,
            "queue_total": total,
            "queue_position": f"{index}/{total}",
            "global_order": index,
            "phase": "CSV RERUN",
            "status": status,
            "reason": reason,
            "stage_mode": _rerun_manifest_text(raw_row.get("stage_mode") or metadata.get("stage_mode")),
            "original_mode": _rerun_manifest_text(raw_row.get("original_mode") or metadata.get("original_mode")),
            "return_mode": _rerun_manifest_text(raw_row.get("return_mode") or metadata.get("return_mode")),
            "audit_issue_codes": _rerun_manifest_text(raw_row.get("audit_issue_codes") or metadata.get("audit_issue_codes")),
            "verified_output_path": _rerun_manifest_text(raw_row.get("verified_output_path") or metadata.get("verified_output_path")),
            "pending_publish_manifest_path": _rerun_manifest_text(raw_row.get("pending_publish_manifest_path") or metadata.get("pending_publish_manifest_path")),
            "pending_publish_payload_path": _rerun_manifest_text(raw_row.get("pending_publish_payload_path") or metadata.get("pending_publish_payload_path")),
            "published_path": _rerun_manifest_text(raw_row.get("published_path") or metadata.get("published_path")),
            "replaced_final_hold_path": _rerun_manifest_text(raw_row.get("replaced_final_hold_path") or metadata.get("replaced_final_hold_path")),
            "manifest_path": str(manifest_path),
            "available_open_targets": [],
            "row_key": f"csv_rerun\x1f{manifest.get('batch_id')}\x1f{index}\x1f{stage_path or source_path}".casefold(),
            "metadata": {
                "source": "rerun_manifest",
                "manifest_path": str(manifest_path),
                "csv_path": _rerun_manifest_text(manifest.get("csv_path")),
                "config_path": _rerun_manifest_text(manifest.get("config_path")),
                "stage_path": stage_path,
                "planned_output_path": planned_output_path,
                "status": status,
                "reason": reason,
                "destination_state": {
                    "destination_mode": _rerun_manifest_text(manifest.get("destination_mode")),
                    "collision_policy": _rerun_manifest_text(manifest.get("collision_policy")),
                    "auto_destination_policy": _rerun_manifest_text(raw_row.get("auto_destination_policy") or metadata.get("auto_destination_policy")),
                    "auto_destination_decision": _rerun_manifest_text(raw_row.get("auto_destination_decision") or metadata.get("auto_destination_decision")),
                    "auto_destination_issue_count": _rerun_manifest_text(raw_row.get("auto_destination_issue_count") or metadata.get("auto_destination_issue_count")),
                },
            },
        }
        rows.append(row)
    return rows


def _rerun_manifest_preview_snapshot(
    resolved: ResolvedPaths,
    manifest: dict[str, object],
    rows: list[dict[str, object]],
) -> dict[str, object]:
    movie_count = sum(1 for row in rows if str(row.get("media_type") or "").casefold() == "movie")
    tv_count = sum(1 for row in rows if str(row.get("media_type") or "").casefold() == "tv")
    return {
        "schema_version": "desktop_csv_rerun_queue_preview.v1",
        "produced_at": _rerun_manifest_text(manifest.get("created_at")),
        "config_path": _rerun_manifest_text(manifest.get("config_path") or resolved.config_path),
        "local_base": _rerun_manifest_text(manifest.get("pipeline_local_base") or resolved.local_base),
        "source_movies": "",
        "source_tv": "",
        "outsource": _rerun_manifest_text(manifest.get("output_root")),
        "movie_count_total": movie_count,
        "tv_count_total": tv_count,
        "runnable_count": len(rows),
        "total_row_count": len(rows),
        "shown_row_count": len(rows),
        "rows": rows,
    }


def _queue_preview_dto(**fields: object) -> QueuePreviewDto:
    from mediapipeline.core.kernel.dto_inventory import QueuePreviewDto

    return QueuePreviewDto(**fields)


def _command_result(**fields: object) -> CommandResult:
    from mediapipeline.core.kernel.dto_commands import CommandResult

    return CommandResult(**fields)


class QueueFacadeMixin:
    """Read-only queue snapshot adapter for the application facade."""

    def _csv_rerun_manifest_preview(
        self,
        resolved: ResolvedPaths,
        *,
        queue_scan_status: dict[str, object],
        source_inventory: dict[str, object],
        reason: str,
    ) -> QueuePreviewDto | None:
        if not _active_csv_rerun_job_present(resolved):
            return None
        manifest_info = _read_latest_rerun_manifest(resolved)
        if manifest_info is None:
            return None
        manifest_path, manifest = manifest_info
        rows = _rerun_manifest_preview_rows(manifest, manifest_path)
        if not rows:
            return None
        warnings = [
            reason,
            "Showing active CSV rerun manifest queue rows; this read-only view does not launch, stop, drain, publish, or mutate media.",
        ]
        metadata_snapshot = _rerun_manifest_preview_snapshot(resolved, manifest, rows)
        metadata = queue_preview_metadata(
            metadata_snapshot,
            rows,
            snapshot_path=manifest_path,
            runtime_event_count=0,
            runtime_outcome_source="",
            runtime_outcome_warning="",
        )
        queue_progress = queue_source_scan_progress_payload(
            source=str(manifest_path),
            row_count=len(rows),
            metadata=metadata,
            warnings=warnings,
            status="active",
            detail="Active CSV rerun manifest queue is driving the current run.",
        )
        return _queue_preview_dto(
            rows=rows,
            source=str(manifest_path),
            queue_scan_status=queue_scan_status,
            source_inventory=source_inventory,
            queue_progress=queue_progress,
            progress_bars=list(queue_progress["progress_bars"]),
            **metadata,
            warnings=warnings,
        )

    def get_queue_preview(self, resolved: ResolvedPaths) -> QueuePreviewDto:
        """Return the last queue snapshot without spawning a dry-run process."""
        queue_scan_status, source_inventory = self._queue_scan_artifacts(resolved)
        snapshot_path = resolved.queue_snapshot_path
        if not snapshot_path or not snapshot_path.exists():
            rerun_preview = self._csv_rerun_manifest_preview(
                resolved,
                queue_scan_status=queue_scan_status,
                source_inventory=source_inventory,
                reason=NO_QUEUE_SNAPSHOT_WARNING,
            )
            if rerun_preview is not None:
                return rerun_preview
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
        if resolved.file_overrides_path is not None:
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
        if not any(_queue_row_is_operator_runnable(row) for row in rows):
            rerun_preview = self._csv_rerun_manifest_preview(
                resolved,
                queue_scan_status=queue_scan_status,
                source_inventory=source_inventory,
                reason="Normal queue preview has no runnable rows while a CSV rerun is active.",
            )
            if rerun_preview is not None:
                return rerun_preview
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
