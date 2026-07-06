"""Backend-owned cooperative control helpers for CSV reruns."""

from __future__ import annotations

import csv
import hashlib
import io
import json
import uuid
from collections import Counter
from collections.abc import Mapping
from datetime import datetime, UTC
from pathlib import Path
from typing import Any

from mediapipeline.core.kernel.contracts import ActiveJobRecord
from mediapipeline.core.kernel.dto_commands import CommandResult
from mediapipeline.core.paths.contracts import ResolvedPaths
from mediapipeline.core.processes.active_jobs import ACTIVE_JOB_BLOCKING_STATUSES, active_jobs_dir_for_resolved
from mediapipeline.core.processes.file_io import atomic_write_text, read_json_file
from mediapipeline.core.processes.rerun_preview import read_rerun_csv_rows, scoped_rerun_csv_root


RERUN_CONTROL_SCHEMA_VERSION = "desktop_rerun_control.v1"
RERUN_CONTINUE_SCHEMA_VERSION = "desktop_rerun_continue.v1"
STOP_MARKER_NAME = "stop_after_current.json"
STOP_AFTER_CURRENT_ACTION = "stop_after_current"
PAUSE_ACTION = "pause"
STOPPED_AFTER_CURRENT_STATUS = "stopped_after_current"
RERUN_ACTIVE_JOB_KIND = "rerun_csv"


def _now_text() -> str:
    return datetime.now(UTC).astimezone().isoformat(timespec="seconds")


def _hash_text(text: str, length: int = 20) -> str:
    return hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest()[:length]


def _read_json(path: Path) -> dict[str, Any] | None:
    try:
        value = read_json_file(path, retries=1)
    except Exception:
        return None
    return value if isinstance(value, dict) else None


def rerun_control_root(resolved: ResolvedPaths) -> Path | None:
    if resolved.state_root is not None:
        return resolved.state_root / "Rerun" / "Control"
    if resolved.local_base is not None:
        return resolved.local_base / "State" / "Rerun" / "Control"
    return None


def rerun_stop_marker_path(resolved: ResolvedPaths) -> Path | None:
    root = rerun_control_root(resolved)
    return root / STOP_MARKER_NAME if root is not None else None


def _manifest_root(resolved: ResolvedPaths) -> Path | None:
    if resolved.local_base is None:
        return None
    return resolved.local_base / "RerunManifests"


def _manifest_key(path: Path) -> str:
    return _hash_text(str(path))


def _active_job_records(resolved: ResolvedPaths) -> list[tuple[Path, ActiveJobRecord]]:
    folder = active_jobs_dir_for_resolved(resolved)
    if folder is None or not folder.exists():
        return []
    try:
        paths = sorted(folder.glob("*.json"), key=lambda item: item.stat().st_mtime, reverse=True)
    except OSError:
        return []
    records: list[tuple[Path, ActiveJobRecord]] = []
    for path in paths:
        try:
            payload = read_json_file(path, retries=1)
            record = ActiveJobRecord.from_mapping(payload)
        except Exception:
            continue
        if record.status in ACTIVE_JOB_BLOCKING_STATUSES:
            records.append((path, record))
    return records


def _active_rerun_records(resolved: ResolvedPaths) -> list[tuple[Path, ActiveJobRecord]]:
    return [
        (path, record)
        for path, record in _active_job_records(resolved)
        if str(record.job_kind or "").casefold() == RERUN_ACTIVE_JOB_KIND
    ]


def _active_non_rerun_records(resolved: ResolvedPaths) -> list[tuple[Path, ActiveJobRecord]]:
    return [
        (path, record)
        for path, record in _active_job_records(resolved)
        if str(record.job_kind or "").casefold() != RERUN_ACTIVE_JOB_KIND
    ]


def _active_record_mapping(record_path: Path, record: ActiveJobRecord) -> dict[str, Any]:
    return {
        "record_path": str(record_path),
        "launch_id": record.launch_id,
        "job_kind": record.job_kind,
        "mode": record.mode,
        "status": record.status,
        "pid": record.pid,
        "metadata": dict(record.metadata),
    }


def _candidate_manifest_paths(resolved: ResolvedPaths) -> list[Path]:
    root = _manifest_root(resolved)
    if root is None or not root.exists():
        return []
    try:
        return sorted(root.glob("*.json"), key=lambda item: item.stat().st_mtime, reverse=True)
    except OSError:
        return []


def _normalize_path_text(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    try:
        return str(Path(text).resolve(strict=False)).rstrip("\\/").casefold()
    except OSError:
        return text.rstrip("\\/").casefold()


def _manifest_matches_record(manifest: Mapping[str, Any], record: ActiveJobRecord) -> bool:
    metadata = dict(record.metadata)
    csv_path = _normalize_path_text(metadata.get("csv_path"))
    manifest_csv = _normalize_path_text(manifest.get("csv_path") or manifest.get("source_csv_path"))
    if csv_path and manifest_csv and csv_path == manifest_csv:
        return True
    return False


def _latest_active_manifest(resolved: ResolvedPaths, record: ActiveJobRecord | None = None) -> tuple[Path | None, dict[str, Any] | None]:
    fallback: tuple[Path | None, dict[str, Any] | None] = (None, None)
    terminal = {"complete", "failed", "stopped_after_current"}
    for path in _candidate_manifest_paths(resolved):
        data = _read_json(path)
        if not isinstance(data, dict):
            continue
        status = str(data.get("status") or "").casefold()
        if status in terminal:
            continue
        if fallback == (None, None):
            fallback = (path, data)
        if record is not None and _manifest_matches_record(data, record):
            return path, data
    return fallback


def _control_command_name(action: str) -> str:
    return "rerun.control.pause" if action == PAUSE_ACTION else "rerun.control.stop_after_current"


def request_rerun_stop_after_current(resolved: ResolvedPaths, request: Mapping[str, Any]) -> CommandResult:
    requested_action = str(request.get("action") or "").strip().casefold()
    command_name = _control_command_name(requested_action)
    if requested_action not in {STOP_AFTER_CURRENT_ACTION, PAUSE_ACTION}:
        return CommandResult(
            command="rerun.control",
            ok=False,
            severity="error",
            message="Unsupported CSV rerun control action.",
            errors=["unsupported_rerun_control_action"],
        )
    if requested_action == STOP_AFTER_CURRENT_ACTION and request.get("confirm_stop") is not True:
        return CommandResult(
            command=command_name,
            ok=False,
            severity="error",
            message="confirm_stop=true is required.",
            errors=["confirm_stop_required"],
        )
    if requested_action == PAUSE_ACTION and request.get("confirm_pause") is not True:
        return CommandResult(
            command=command_name,
            ok=False,
            severity="error",
            message="confirm_pause=true is required.",
            errors=["confirm_pause_required"],
        )

    active_reruns = _active_rerun_records(resolved)
    active_non_reruns = _active_non_rerun_records(resolved)
    if not active_reruns:
        message = (
            "No active CSV rerun job is available for pause."
            if requested_action == PAUSE_ACTION
            else "No active CSV rerun job is available for stop-after-current."
        )
        severity = "warning" if not active_non_reruns else "error"
        return CommandResult(
            command=command_name,
            ok=False,
            severity=severity,
            message=message,
            errors=[] if severity == "warning" else ["active_work_is_not_rerun_csv"],
            warnings=[message] if severity == "warning" else [],
            refresh_hint="snapshot",
            data={
                "active_jobs": [_active_record_mapping(path, record) for path, record in active_non_reruns],
            },
        )
    if len(active_reruns) != 1:
        message = f"Expected exactly one active CSV rerun job; found {len(active_reruns)}."
        return CommandResult(
            command=command_name,
            ok=False,
            severity="error",
            message=message,
            errors=["ambiguous_active_rerun_csv_jobs"],
            refresh_hint="snapshot",
            data={"active_rerun_jobs": [_active_record_mapping(path, record) for path, record in active_reruns]},
        )

    record_path, record = active_reruns[0]
    marker_path = rerun_stop_marker_path(resolved)
    if marker_path is None:
        return CommandResult(
            command=command_name,
            ok=False,
            severity="error",
            message="State root is unavailable; cannot write CSV rerun control marker.",
            errors=["rerun_control_root_unavailable"],
    )

    manifest_path, manifest = _latest_active_manifest(resolved, record)
    request_id_prefix = "rerun-pause" if requested_action == PAUSE_ACTION else "rerun-stop"
    request_id = f"{request_id_prefix}-{uuid.uuid4().hex[:12]}"
    metadata = dict(record.metadata)
    payload = {
        "schema_version": RERUN_CONTROL_SCHEMA_VERSION,
        "request_id": request_id,
        "action": STOP_AFTER_CURRENT_ACTION,
        "requested_action": requested_action,
        "created_at": _now_text(),
        "active_job_record_path": str(record_path),
        "launch_id": record.launch_id,
        "job_kind": record.job_kind,
        "pid": record.pid,
        "batch_id": str((manifest or {}).get("batch_id") or ""),
        "manifest_path": str(manifest_path or ""),
        "manifest_key": _manifest_key(manifest_path) if manifest_path is not None else "",
        "csv_path": str(metadata.get("csv_path") or (manifest or {}).get("csv_path") or ""),
    }
    atomic_write_text(marker_path, json.dumps(payload, indent=2, sort_keys=True) + "\n")
    message = (
        "CSV rerun pause requested. The current row/window will finish; "
        "no next CSV row starts until Continue Pending Rows is used."
        if requested_action == PAUSE_ACTION
        else "CSV rerun stop-after-current requested. The current row/window will finish before the next row starts."
    )
    return CommandResult(
        command=command_name,
        ok=True,
        severity="info",
        message=message,
        refresh_hint="snapshot",
        data={
            "schema_version": RERUN_CONTROL_SCHEMA_VERSION,
            "request_id": request_id,
            "action": requested_action,
            "marker_action": STOP_AFTER_CURRENT_ACTION,
            "marker_path": str(marker_path),
            "batch_id": payload["batch_id"],
            "manifest_path": payload["manifest_path"],
            "manifest_key": payload["manifest_key"],
            "active_job": _active_record_mapping(record_path, record),
            "touches_media": False,
            "writes_manifest": False,
        },
    )


def _manifest_by_key(resolved: ResolvedPaths, manifest_key: str) -> tuple[Path | None, dict[str, Any] | None]:
    key = str(manifest_key or "").strip()
    if not key:
        return None, None
    for path in _candidate_manifest_paths(resolved):
        if _manifest_key(path) != key:
            continue
        data = _read_json(path)
        return (path, data) if isinstance(data, dict) else (path, None)
    return None, None


def _row_status_counts(rows: list[Mapping[str, Any]]) -> dict[str, int]:
    counts = Counter(str(row.get("status") or "unknown").strip() or "unknown" for row in rows)
    return dict(sorted(counts.items()))


def _source_path_from_row(row: Mapping[str, Any]) -> str:
    lowered = {str(key).casefold(): value for key, value in row.items()}
    for key in ("source_path", "path", "sourcepath"):
        text = str(lowered.get(key) or "").strip()
        if text:
            return text
    return ""


def _int_or_none(value: Any) -> int | None:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed >= 0 else None


def _pending_manifest_row_selectors(manifest: Mapping[str, Any]) -> tuple[set[tuple[int, str]], set[int], set[str]]:
    indexed_source_keys: set[tuple[int, str]] = set()
    indexes: set[int] = set()
    legacy_source_keys: set[str] = set()
    for row in manifest.get("rows") or []:
        if not isinstance(row, Mapping):
            continue
        if str(row.get("status") or "").strip().casefold() != "pending":
            continue
        row_index = _int_or_none(row.get("row_index"))
        source_path = _source_path_from_row(row)
        source_key = _normalize_path_text(source_path) if source_path else ""
        if row_index is not None:
            indexes.add(row_index)
            if source_key:
                indexed_source_keys.add((row_index, source_key))
        elif source_key:
            legacy_source_keys.add(source_key)
    return indexed_source_keys, indexes, legacy_source_keys


def _manifest_source_csv_path(manifest: Mapping[str, Any]) -> Path | None:
    for key in ("csv_path", "source_csv_path", "original_csv_path"):
        text = str(manifest.get(key) or "").strip()
        if text:
            return Path(text)
    return None


def _manifest_bool(manifest: Mapping[str, Any], key: str) -> bool:
    return manifest.get(key) is True


def _continue_request_from_manifest(manifest: Mapping[str, Any], scoped_csv_path: Path) -> dict[str, Any]:
    execution_mode = str(manifest.get("execution_mode") or "one_at_a_time")
    destination_mode = str(manifest.get("destination_mode") or "review_workspace")
    collision_policy = str(manifest.get("collision_policy") or "suffix")
    try:
        window_size = int(manifest.get("window_size") or 1)
    except (TypeError, ValueError):
        window_size = 1
    return {
        "csv_path": str(scoped_csv_path),
        "dry_run": False,
        "plan_only": False,
        "execution_mode": execution_mode,
        "destination_mode": destination_mode,
        "collision_policy": collision_policy,
        "window_size": max(1, window_size),
        "stage_mode": str(manifest.get("default_stage_mode") or manifest.get("stage_mode") or "copy"),
        "original_mode": str(manifest.get("default_original_mode") or manifest.get("original_mode") or "keep"),
        "return_mode": str(manifest.get("default_return_mode") or manifest.get("return_mode") or "park"),
        "confirm_replace_final": _manifest_bool(manifest, "confirm_replace_final"),
        "confirm_source_overwrite": _manifest_bool(manifest, "confirm_source_overwrite"),
    }


def _materialize_pending_only_csv(
    resolved: ResolvedPaths,
    *,
    manifest_path: Path,
    manifest: Mapping[str, Any],
    source_csv_path: Path,
    pending_indexed_source_keys: set[tuple[int, str]],
    pending_indexes: set[int],
    legacy_pending_source_keys: set[str],
) -> dict[str, Any]:
    fieldnames, original_rows = read_rerun_csv_rows(source_csv_path)
    selected_rows: list[dict[str, str]] = []
    paired_indexes = {row_index for row_index, _source_key in pending_indexed_source_keys}
    index_only_selectors = pending_indexes - paired_indexes
    for index, row in enumerate(original_rows):
        source_key = _normalize_path_text(_source_path_from_row(row))
        if pending_indexed_source_keys and (index, source_key) in pending_indexed_source_keys:
            selected_rows.append(row)
        elif index in index_only_selectors:
            selected_rows.append(row)
        elif not pending_indexes and source_key in legacy_pending_source_keys:
            selected_rows.append(row)
    if not selected_rows:
        raise RuntimeError("Original CSV does not contain any rows still marked pending in the stopped manifest.")

    output_root = scoped_rerun_csv_root(resolved)
    if output_root is None:
        raise RuntimeError("State root is unavailable; cannot materialize continuation CSV.")
    output_root.mkdir(parents=True, exist_ok=True)
    if not fieldnames:
        fieldnames = sorted({key for row in selected_rows for key in row})
    source_digest = _hash_text(str(manifest_path), length=12)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_path = output_root / f"rerun_continue_pending_{stamp}_{source_digest}.csv"
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=fieldnames, extrasaction="ignore")
    writer.writeheader()
    for row in selected_rows:
        writer.writerow({key: row.get(key, "") for key in fieldnames})
    atomic_write_text(output_path, buffer.getvalue(), encoding="utf-8")
    return {
        "schema_version": RERUN_CONTINUE_SCHEMA_VERSION,
        "source_csv_path": str(source_csv_path),
        "scoped_csv_path": str(output_path),
        "source_manifest_path": str(manifest_path),
        "source_manifest_key": _manifest_key(manifest_path),
        "row_count": len(selected_rows),
        "pending_source_count": len(pending_indexed_source_keys) + len(index_only_selectors) + len(legacy_pending_source_keys),
        "touches_media": False,
        "writes_queue": False,
        "writes_file_overrides": False,
    }


def build_rerun_continue_pending_request(
    resolved: ResolvedPaths,
    request: Mapping[str, Any],
) -> tuple[CommandResult | None, dict[str, Any] | None, dict[str, Any] | None]:
    if request.get("confirm_continue") is not True:
        return (
            CommandResult(
                command="rerun.continue",
                ok=False,
                severity="error",
                message="confirm_continue=true is required.",
                errors=["confirm_continue_required"],
            ),
            None,
            None,
        )
    manifest_key = str(request.get("manifest_key") or "").strip()
    manifest_path, manifest = _manifest_by_key(resolved, manifest_key)
    if manifest_path is None or manifest is None:
        return (
            CommandResult(
                command="rerun.continue",
                ok=False,
                severity="error",
                message="Rerun manifest was not found.",
                errors=["rerun_manifest_not_found"],
            ),
            None,
            None,
        )
    if str(manifest.get("status") or "").strip().casefold() != STOPPED_AFTER_CURRENT_STATUS:
        return (
            CommandResult(
                command="rerun.continue",
                ok=False,
                severity="error",
                message="Only stopped_after_current rerun manifests can continue pending rows.",
                errors=["rerun_manifest_not_stopped_after_current"],
                data={"manifest_path": str(manifest_path), "status": str(manifest.get("status") or "")},
            ),
            None,
            None,
        )
    rows = [row for row in manifest.get("rows") or [] if isinstance(row, Mapping)]
    pending_indexed_source_keys, pending_indexes, legacy_pending_source_keys = _pending_manifest_row_selectors(manifest)
    if not pending_indexed_source_keys and not pending_indexes and not legacy_pending_source_keys:
        return (
            CommandResult(
                command="rerun.continue",
                ok=False,
                severity="warning",
                message="Stopped rerun manifest has no pending rows to continue.",
                warnings=["no_pending_rerun_rows"],
                data={"manifest_path": str(manifest_path), "row_status_counts": _row_status_counts(rows)},
            ),
            None,
            None,
        )
    source_csv_path = _manifest_source_csv_path(manifest)
    if source_csv_path is None or not source_csv_path.is_file():
        return (
            CommandResult(
                command="rerun.continue",
                ok=False,
                severity="error",
                message="Stopped rerun source CSV is missing; continuation cannot materialize pending rows.",
                errors=["rerun_source_csv_missing"],
                data={"manifest_path": str(manifest_path), "source_csv_path": str(source_csv_path or "")},
            ),
            None,
            None,
        )
    try:
        scoped_info = _materialize_pending_only_csv(
            resolved,
            manifest_path=manifest_path,
            manifest=manifest,
            source_csv_path=source_csv_path,
            pending_indexed_source_keys=pending_indexed_source_keys,
            pending_indexes=pending_indexes,
            legacy_pending_source_keys=legacy_pending_source_keys,
        )
    except Exception as exc:
        return (
            CommandResult(
                command="rerun.continue",
                ok=False,
                severity="error",
                message=f"CSV rerun continuation CSV could not be written: {exc}",
                errors=[str(exc)],
                data={"manifest_path": str(manifest_path), "source_csv_path": str(source_csv_path)},
            ),
            None,
            None,
        )
    continue_request = _continue_request_from_manifest(manifest, Path(scoped_info["scoped_csv_path"]))
    return None, continue_request, scoped_info


__all__ = [
    "RERUN_CONTINUE_SCHEMA_VERSION",
    "RERUN_CONTROL_SCHEMA_VERSION",
    "STOPPED_AFTER_CURRENT_STATUS",
    "build_rerun_continue_pending_request",
    "request_rerun_stop_after_current",
    "rerun_control_root",
    "rerun_stop_marker_path",
]
