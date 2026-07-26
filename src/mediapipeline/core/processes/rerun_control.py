"""Backend-owned cooperative control helpers for CSV reruns."""

from __future__ import annotations

import csv
import hashlib
import io
import json
import uuid
from collections import Counter
from collections.abc import Mapping, Sequence
from datetime import datetime, UTC
from pathlib import Path
from typing import Any

from mediapipeline.core.kernel.contracts import ActiveJobRecord
from mediapipeline.core.kernel.dto_commands import CommandResult
from mediapipeline.core.paths.contracts import ResolvedPaths
from mediapipeline.core.processes.active_jobs import ACTIVE_JOB_BLOCKING_STATUSES, active_jobs_dir_for_resolved
from mediapipeline.core.processes.file_io import atomic_write_text, read_json_file
from mediapipeline.core.processes.rerun_lifecycle import (
    rerun_enrollment_candidates,
    rerun_manifest_declared_path_matches_actual,
    rerun_manifest_matches_enrollment,
    rerun_manifest_path_matches_canonical_batch,
)
from mediapipeline.core.processes.rerun_preview import read_rerun_csv_rows, scoped_rerun_csv_root
from mediapipeline.core.rerun.evidence import exact_rerun_active_job_payload, normalized_rerun_path_text


RERUN_CONTROL_SCHEMA_VERSION = "desktop_rerun_control.v1"
RERUN_CONTINUE_SCHEMA_VERSION = "desktop_rerun_continue.v1"
STOP_MARKER_NAME = "stop_after_current.json"
STOP_AFTER_CURRENT_ACTION = "stop_after_current"
PAUSE_ACTION = "pause"
STOPPED_AFTER_CURRENT_STATUS = "stopped_after_current"
COMPLETED_WITH_FAILURES_STATUS = "completed_with_failures"
COMPLETED_WITH_FAILURES_STATUSES = frozenset(
    {COMPLETED_WITH_FAILURES_STATUS, "completed_with_failed_rows"}
)
RETRY_EXHAUSTED_STATUS = "retry_exhausted"
WAITING_RESTART_STATUSES = frozenset(
    {"waiting", "waiting_for_source", "retry_scheduled", "retrying"}
)
RERUN_ACTIVE_JOB_KIND = "rerun_csv"
_EXIT_PROVEN_ACTIVE_JOB_STATUSES = frozenset(
    {"completed", "failed", "completed_immediate", "failed_immediate", "killed", "orphaned"}
)
_TRUE_CSV_VALUES = frozenset({"1", "true", "yes", "y", "on", "enabled", "run"})
_FULL_CONTENT_SHA256_ALGORITHM = "sha256-full-file"
_RERUN_MANIFEST_V2_SCHEMA_VERSION = "rerun_batch_manifest.v2"
_RECOVERY_GENERATION_SEPARATOR = ":generation:"
_RETRY_IDENTITY_FIELDS = (
    "source_size",
    "source_mtime_utc",
    "source_identity_v2",
    "source_identity_v2_algorithm",
    "source_content_sha256",
    "source_content_sha256_algorithm",
)


def _now_text() -> str:
    return datetime.now(UTC).astimezone().isoformat(timespec="seconds")


def _hash_text(text: str, length: int = 20) -> str:
    return hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest()[:length]


def _normalized_source_content_sha256(row: Mapping[str, Any]) -> str:
    value = str(
        row.get("planned_source_content_sha256")
        or row.get("source_content_sha256")
        or ""
    ).strip().casefold()
    if len(value) != 64 or any(character not in "0123456789abcdef" for character in value):
        return ""
    return value


def _source_content_sha256_algorithm(row: Mapping[str, Any]) -> str:
    return str(
        row.get("planned_source_content_sha256_algorithm")
        or row.get("source_content_sha256_algorithm")
        or ""
    ).strip()


def _source_content_sha256(row: Mapping[str, Any]) -> str:
    if _source_content_sha256_algorithm(row) != _FULL_CONTENT_SHA256_ALGORITHM:
        return ""
    return _normalized_source_content_sha256(row)


def _recovery_row_selectors(
    rows: Sequence[Mapping[str, Any]],
    *,
    canonical_order: bool = True,
) -> list[dict[str, Any]]:
    selectors: list[dict[str, Any]] = []
    for row in rows:
        row_index = _int_or_none(row.get("row_index"))
        source_path = _source_path_from_row(row)
        selector: dict[str, Any] = {"source_path": _normalize_path_text(source_path)}
        if row_index is not None:
            selector["row_index"] = row_index
        source_identity = str(
            row.get("planned_source_identity_v2") or row.get("source_identity_v2") or ""
        ).strip()
        if source_identity:
            selector["source_identity_v2"] = source_identity
        source_content_sha256 = _source_content_sha256(row)
        if source_content_sha256:
            selector["source_content_sha256"] = source_content_sha256
            selector["source_content_sha256_algorithm"] = _FULL_CONTENT_SHA256_ALGORITHM
        selectors.append(selector)
    if not canonical_order:
        return selectors
    return sorted(
        selectors,
        key=lambda selector: json.dumps(selector, sort_keys=True, separators=(",", ":")),
    )


def _rerun_recovery_key(
    *,
    manifest_key: str,
    recovery_scope: str,
    row_selectors: list[dict[str, Any]],
) -> str:
    payload = {
        "manifest_key": manifest_key,
        "recovery_scope": recovery_scope,
        "row_selectors": row_selectors,
    }
    return _hash_text(json.dumps(payload, sort_keys=True, separators=(",", ":")), length=40)


def _logical_rerun_recovery_key(
    *,
    command_id: str,
    launch_id: str,
    batch_id: str,
    recovery_scope: str,
    row_selectors: list[dict[str, Any]],
) -> str:
    payload = {
        "source_correlation": {
            "command_id": str(command_id or "").strip(),
            "launch_id": str(launch_id or "").strip(),
            "batch_id": str(batch_id or "").strip(),
        },
        "recovery_scope": recovery_scope,
        "row_selectors": row_selectors,
    }
    return _hash_text(json.dumps(payload, sort_keys=True, separators=(",", ":")), length=40)


def _recovery_generation_from_key(recovery_key: str, recovery_root_key: str) -> int | None:
    if recovery_key == recovery_root_key:
        return 1
    prefix = f"{recovery_root_key}{_RECOVERY_GENERATION_SEPARATOR}"
    if not recovery_key.startswith(prefix):
        return None
    raw_generation = recovery_key[len(prefix) :]
    if not raw_generation.isdigit():
        return None
    generation = int(raw_generation)
    return generation if generation >= 2 else None


def _recovery_key_for_generation(recovery_root_key: str, generation: int) -> str:
    if generation <= 1:
        return recovery_root_key
    return f"{recovery_root_key}{_RECOVERY_GENERATION_SEPARATOR}{generation}"


def _existing_recovery_enrollments(
    resolved: ResolvedPaths,
    recovery_root_key: str,
) -> list[tuple[Path, dict[str, Any], int]]:
    matches: list[tuple[Path, dict[str, Any], int]] = []
    for path, payload in rerun_enrollment_candidates(resolved, limit=10_000):
        recovery_key = str(payload.get("recovery_key") or "").strip()
        generation = _recovery_generation_from_key(recovery_key, recovery_root_key)
        if generation is not None:
            matches.append((path, payload, generation))
    return matches


def _enrollment_recovery_root_and_generation(enrollment: Mapping[str, Any]) -> tuple[str, int]:
    recovery_key = str(enrollment.get("recovery_key") or "").strip()
    recovery_root_key = str(enrollment.get("recovery_root_key") or "").strip()
    try:
        recovery_generation = int(enrollment.get("recovery_generation") or 0)
    except (TypeError, ValueError):
        recovery_generation = 0
    if recovery_root_key:
        parsed_generation = _recovery_generation_from_key(recovery_key, recovery_root_key)
        if recovery_generation < 1 and parsed_generation is not None:
            recovery_generation = parsed_generation
    elif _RECOVERY_GENERATION_SEPARATOR in recovery_key:
        possible_root, possible_generation = recovery_key.rsplit(_RECOVERY_GENERATION_SEPARATOR, 1)
        if possible_root and possible_generation.isdigit() and int(possible_generation) >= 2:
            recovery_root_key = possible_root
            if recovery_generation < 1:
                recovery_generation = int(possible_generation)
    if not recovery_root_key:
        recovery_root_key = recovery_key
    return recovery_root_key, max(1, recovery_generation) if recovery_key else 0


def _canonical_stored_recovery_selectors(enrollment: Mapping[str, Any]) -> list[dict[str, Any]]:
    stored = [
        dict(selector)
        for selector in enrollment.get("recovery_row_selectors") or []
        if isinstance(selector, Mapping)
    ]
    return _recovery_row_selectors(stored) if stored else []


def _logical_recovery_enrollments(
    resolved: ResolvedPaths,
    *,
    source_command_id: str,
    source_launch_id: str,
    source_batch_id: str,
    recovery_scope: str,
    row_selectors: list[dict[str, Any]],
) -> list[tuple[str, tuple[Path, dict[str, Any], int]]]:
    matches: list[tuple[str, tuple[Path, dict[str, Any], int]]] = []
    for path, enrollment in rerun_enrollment_candidates(resolved, limit=10_000):
        if str(enrollment.get("recovery_scope") or "").strip() != recovery_scope:
            continue
        if str(enrollment.get("recovery_source_batch_id") or "").strip() != source_batch_id:
            continue
        stored_command_id = str(enrollment.get("recovery_source_command_id") or "").strip()
        stored_launch_id = str(enrollment.get("recovery_source_launch_id") or "").strip()
        if stored_command_id and stored_command_id != source_command_id:
            continue
        if stored_launch_id and stored_launch_id != source_launch_id:
            continue
        if _canonical_stored_recovery_selectors(enrollment) != row_selectors:
            continue
        recovery_root_key, recovery_generation = _enrollment_recovery_root_and_generation(enrollment)
        if not recovery_root_key or recovery_generation < 1:
            continue
        matches.append((recovery_root_key, (path, enrollment, recovery_generation)))
    return matches


def _recovery_enrollment_state(enrollment: Mapping[str, Any]) -> str:
    return str(enrollment.get("lifecycle_state") or enrollment.get("status") or "").strip().casefold()


def _recovery_enrollment_can_be_superseded(enrollment: Mapping[str, Any]) -> bool:
    if _recovery_enrollment_state(enrollment) != "failed_before_manifest":
        return False
    if enrollment.get("process_exit_verified") is not True:
        return False
    if enrollment.get("duplicate_launch_blocked") is not False:
        return False
    manifest_path = str(enrollment.get("manifest_path") or "").strip()
    if not manifest_path:
        return False
    try:
        Path(manifest_path).lstat()
    except FileNotFoundError:
        return True
    except (OSError, ValueError):
        return False
    return False


def _existing_recovery_result(
    *,
    enrollment_path: Path,
    enrollment: Mapping[str, Any],
    request_id: str,
    recovery_root_key: str,
    recovery_generation: int,
) -> CommandResult:
    same_request = str(enrollment.get("recovery_request_id") or "").strip() == request_id
    data = {
        "schema_version": RERUN_CONTINUE_SCHEMA_VERSION,
        "recovery_scope": str(enrollment.get("recovery_scope") or ""),
        "source_manifest_path": str(enrollment.get("recovery_source_manifest_path") or ""),
        "source_manifest_key": str(enrollment.get("recovery_source_manifest_key") or ""),
        "source_batch_id": str(enrollment.get("recovery_source_batch_id") or ""),
        "recovery_key": str(enrollment.get("recovery_key") or ""),
        "recovery_root_key": recovery_root_key,
        "recovery_generation": recovery_generation,
        "recovery_request_id": str(enrollment.get("recovery_request_id") or ""),
        "command_id": str(enrollment.get("command_id") or ""),
        "launch_id": str(enrollment.get("launch_id") or ""),
        "batch_id": str(enrollment.get("batch_id") or ""),
        "enrollment_path": str(enrollment_path),
        "manifest_path": str(enrollment.get("manifest_path") or ""),
        "lifecycle_state": str(enrollment.get("lifecycle_state") or enrollment.get("status") or ""),
        "durably_enrolled": True,
        "launches_work": False,
        "already_enrolled": True,
        "idempotent_replay": same_request,
    }
    if same_request:
        return CommandResult(
            command="rerun.continue",
            ok=True,
            severity="info",
            message="CSV rerun recovery was already durably enrolled for this request; no duplicate work was launched.",
            refresh_hint="snapshot",
            data=data,
        )
    return CommandResult(
        command="rerun.continue",
        ok=False,
        severity="error",
        message="CSV rerun recovery is already durably enrolled under a different request_id.",
        errors=["rerun_recovery_already_enrolled"],
        refresh_hint="snapshot",
        data=data,
    )


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


def _all_active_job_records(resolved: ResolvedPaths) -> list[tuple[Path, ActiveJobRecord]]:
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
        records.append((path, record))
    return records


def _active_job_records(resolved: ResolvedPaths) -> list[tuple[Path, ActiveJobRecord]]:
    return [
        (path, record)
        for path, record in _all_active_job_records(resolved)
        if record.status in ACTIVE_JOB_BLOCKING_STATUSES
    ]


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


def rerun_waiting_restart_posture(
    resolved: ResolvedPaths,
    manifest: Mapping[str, Any],
) -> dict[str, Any]:
    manifest_status = str(manifest.get("status") or manifest.get("lifecycle_state") or "").strip().casefold()
    waiting_rows = [
        row
        for row in manifest.get("rows") or []
        if isinstance(row, Mapping)
        and str(row.get("lifecycle_state") or row.get("status") or "").strip().casefold()
        in WAITING_RESTART_STATUSES
    ]
    source_recovery_posture = _selected_rows_recovery_posture(
        resolved,
        manifest,
        waiting_rows,
        scope="waiting_restart",
    )
    if manifest_status not in WAITING_RESTART_STATUSES:
        return {
            "state": "not_waiting",
            "manual_retry_available": False,
            "reason": "The manifest is not in a waiting/retry-scheduled lifecycle state.",
            "active_job": {},
            "source_recovery_posture": source_recovery_posture,
        }
    required_fields = ["command_id", "launch_id", "batch_id"]
    if str(manifest.get("schema_version") or "").strip() == _RERUN_MANIFEST_V2_SCHEMA_VERSION:
        required_fields.extend(("enrollment_path", "manifest_path"))
    correlation_complete = all(str(manifest.get(field) or "").strip() for field in required_fields)
    matches: list[tuple[Path, ActiveJobRecord]] = []
    if correlation_complete:
        record_path, raw_record = exact_rerun_active_job_payload(resolved, manifest)
        if record_path is not None and raw_record is not None:
            try:
                record = ActiveJobRecord.from_mapping(raw_record)
            except Exception:
                record = None
            if record is not None:
                matches.append((record_path, record))
    blocking = [item for item in matches if item[1].status in ACTIVE_JOB_BLOCKING_STATUSES]
    if blocking:
        record_path, record = blocking[0]
        return {
            "state": "child_active",
            "manual_retry_available": False,
            "reason": (
                "The correlated CSV rerun ActiveJobs record is still active; its child owns automatic retry. "
                "A second launch is blocked."
            ),
            "active_job": _active_record_mapping(record_path, record),
            "source_recovery_posture": source_recovery_posture,
        }
    terminal = [item for item in matches if item[1].status in _EXIT_PROVEN_ACTIVE_JOB_STATUSES]
    if terminal:
        record_path, record = terminal[0]
        recoverable_count = int(source_recovery_posture.get("recoverable_count") or 0)
        if recoverable_count == 0:
            return {
                "state": "source_identity_unqualified",
                "manual_retry_available": False,
                "reason": (
                    "The prior child exited, but one or more waiting rows lack durable row, identity, "
                    "or full-content SHA-256 evidence. Legacy rows remain in review and are not auto-recovered."
                ),
                "active_job": _active_record_mapping(record_path, record),
                "source_recovery_posture": source_recovery_posture,
            }
        return {
            "state": "child_exit_proven",
            "manual_retry_available": True,
            "reason": (
                f"The correlated CSV rerun child is no longer active; ActiveJobs status {record.status} "
                f"permits one explicit strong-identity recovery launch for {recoverable_count} qualified row(s). "
                "Unqualified legacy rows remain in review."
            ),
            "active_job": _active_record_mapping(record_path, record),
            "source_recovery_posture": source_recovery_posture,
        }
    return {
        "state": "child_exit_unproven",
        "manual_retry_available": False,
        "reason": (
            "No correlated terminal ActiveJobs record proves that the waiting CSV rerun child exited. "
            "Run backend lifecycle reconciliation before retrying."
        ),
        "active_job": {},
        "source_recovery_posture": source_recovery_posture,
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


def _required_row_index(row: Mapping[str, Any]) -> int:
    row_index = _int_or_none(row.get("row_index"))
    if row_index is None:
        raise ValueError("Recovery row is missing a valid non-negative row_index.")
    return row_index


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
    selected_row_selectors: list[dict[str, Any]] = []
    paired_indexes = {row_index for row_index, _source_key in pending_indexed_source_keys}
    index_only_selectors = pending_indexes - paired_indexes
    for index, row in enumerate(original_rows):
        source_key = _normalize_path_text(_source_path_from_row(row))
        if pending_indexed_source_keys and (index, source_key) in pending_indexed_source_keys:
            selected_rows.append(row)
            selected_row_selectors.append({"row_index": index, "source_path": _source_path_from_row(row)})
        elif index in index_only_selectors:
            selected_rows.append(row)
            selected_row_selectors.append({"row_index": index, "source_path": _source_path_from_row(row)})
        elif not pending_indexes and source_key in legacy_pending_source_keys:
            selected_rows.append(row)
            selected_row_selectors.append({"row_index": index, "source_path": _source_path_from_row(row)})
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
        "recovery_scope": "pending_only",
        "recovery_row_selectors": selected_row_selectors,
        "pending_source_count": len(pending_indexed_source_keys) + len(index_only_selectors) + len(legacy_pending_source_keys),
        "touches_media": False,
        "writes_queue": False,
        "writes_file_overrides": False,
    }


def _csv_row_enabled(row: Mapping[str, Any]) -> bool:
    lowered = {str(key).strip().casefold(): value for key, value in row.items()}
    raw = lowered.get("enabled", lowered.get("rerun_enabled", "true"))
    return str(raw or "").strip().casefold() in _TRUE_CSV_VALUES


def _retry_row_is_enabled_in_source_csv(
    row: Mapping[str, Any],
    source_rows: list[Mapping[str, Any]] | None,
) -> bool:
    if source_rows is None:
        return True
    row_index = _int_or_none(row.get("row_index"))
    source_path = _source_path_from_row(row)
    if row_index is None or row_index < 0 or row_index >= len(source_rows) or not source_path:
        return False
    source_row = source_rows[row_index]
    return (
        _normalize_path_text(_source_path_from_row(source_row)) == _normalize_path_text(source_path)
        and _csv_row_enabled(source_row)
    )


def rerun_retry_exhausted_recovery_posture(
    resolved: ResolvedPaths,
    manifest: Mapping[str, Any],
) -> dict[str, Any]:
    exhausted_rows = [
        row
        for row in manifest.get("rows") or []
        if isinstance(row, Mapping)
        and str(row.get("lifecycle_state") or row.get("status") or "").strip().casefold()
        == RETRY_EXHAUSTED_STATUS
    ]
    source_csv_path = _manifest_source_csv_path(manifest)
    original_rows: list[dict[str, str]] = []
    source_csv_error = ""
    if source_csv_path is None or not source_csv_path.is_file():
        source_csv_error = "source_csv_missing"
    else:
        try:
            _fieldnames, original_rows = read_rerun_csv_rows(source_csv_path)
        except Exception:
            source_csv_error = "source_csv_unreadable"
    durable_indexes = [_int_or_none(row.get("row_index")) for row in exhausted_rows]
    index_counts = Counter(index for index in durable_indexes if index is not None)
    recoverable_rows: list[Mapping[str, Any]] = []
    blocked_rows: list[dict[str, Any]] = []
    for row in exhausted_rows:
        row_index = _int_or_none(row.get("row_index"))
        source_path = _source_path_from_row(row)
        identity = str(row.get("planned_source_identity_v2") or row.get("source_identity_v2") or "").strip()
        raw_source_content_sha256 = _normalized_source_content_sha256(row)
        source_content_sha256_algorithm = _source_content_sha256_algorithm(row)
        source_content_sha256 = _source_content_sha256(row)
        reason_code = ""
        reason = ""
        if row_index is None:
            reason_code = "row_index_missing"
            reason = "The exhausted row has no durable nonnegative row_index selector."
        elif index_counts[row_index] > 1:
            reason_code = "row_index_duplicated"
            reason = f"The exhausted row_index {row_index} is duplicated in the source manifest."
        elif not source_path:
            reason_code = "source_path_missing"
            reason = "The exhausted row has no durable source_path selector."
        elif not identity:
            reason_code = "source_identity_missing"
            reason = "The exhausted row has no source_identity_v2 evidence."
        elif not raw_source_content_sha256:
            reason_code = "source_content_sha256_missing"
            reason = "The exhausted row has no durable full-content SHA-256 evidence for a safe retry."
        elif source_content_sha256_algorithm != _FULL_CONTENT_SHA256_ALGORITHM:
            reason_code = "source_content_sha256_algorithm_invalid"
            reason = (
                "The exhausted row's full-content SHA-256 algorithm is not sha256-full-file."
            )
        elif source_csv_error:
            reason_code = source_csv_error
            reason = "The source CSV is missing or unreadable, so the row selector cannot be verified."
        elif row_index >= len(original_rows):
            reason_code = "row_index_outside_source_csv"
            reason = f"The exhausted row_index {row_index} is outside the source CSV."
        else:
            original_row = original_rows[row_index]
            original_content_sha256 = _source_content_sha256(original_row)
            if _normalize_path_text(_source_path_from_row(original_row)) != _normalize_path_text(source_path):
                reason_code = "source_csv_path_changed"
                reason = f"The source CSV row {row_index} no longer matches the exhausted source path."
            elif not _csv_row_enabled(original_row):
                reason_code = "source_csv_row_disabled"
                reason = f"The source CSV row {row_index} is disabled and cannot be retried automatically."
            elif original_content_sha256 and original_content_sha256 != source_content_sha256:
                reason_code = "source_content_sha256_conflict"
                reason = f"The source CSV row {row_index} has conflicting full-content SHA-256 evidence."
        if reason_code:
            blocked_rows.append(
                {
                    "row_index": row_index,
                    "source_path": source_path,
                    "reason_code": reason_code,
                    "reason": reason,
                }
            )
        else:
            recoverable_rows.append(row)
    return {
        "schema_version": "desktop_rerun_retry_exhausted_recovery_posture.v1",
        "source_csv_path": str(source_csv_path or ""),
        "total_count": len(exhausted_rows),
        "recoverable_count": len(recoverable_rows),
        "unrecoverable_count": len(blocked_rows),
        "recoverable_row_indexes": [_required_row_index(row) for row in recoverable_rows],
        "recoverable_rows": recoverable_rows,
        "blocked_rows": blocked_rows,
    }


def _selected_rows_recovery_posture(
    resolved: ResolvedPaths,
    manifest: Mapping[str, Any],
    selected_rows: list[Mapping[str, Any]],
    *,
    scope: str,
) -> dict[str, Any]:
    proxy_rows: list[dict[str, Any]] = []
    original_by_selector: dict[tuple[int | None, str], Mapping[str, Any]] = {}
    for row in selected_rows:
        proxy = dict(row)
        proxy["status"] = RETRY_EXHAUSTED_STATUS
        proxy["lifecycle_state"] = RETRY_EXHAUSTED_STATUS
        proxy_rows.append(proxy)
        original_by_selector[
            (_int_or_none(row.get("row_index")), _normalize_path_text(_source_path_from_row(row)))
        ] = row
    posture = rerun_retry_exhausted_recovery_posture(
        resolved,
        {**dict(manifest), "rows": proxy_rows},
    )
    recoverable_rows = [
        original_by_selector[selector]
        for row in posture.get("recoverable_rows") or []
        if isinstance(row, Mapping)
        and (
            selector := (
                _int_or_none(row.get("row_index")),
                _normalize_path_text(_source_path_from_row(row)),
            )
        )
        in original_by_selector
    ]
    blocked_rows = [
        {
            **dict(row),
            "reason": str(row.get("reason") or "").replace("exhausted", scope.replace("_", " ")),
        }
        for row in posture.get("blocked_rows") or []
        if isinstance(row, Mapping)
    ]
    return {
        **posture,
        "schema_version": f"desktop_rerun_{scope}_recovery_posture.v1",
        "recoverable_count": len(recoverable_rows),
        "unrecoverable_count": len(blocked_rows),
        "recoverable_rows": recoverable_rows,
        "blocked_rows": blocked_rows,
    }


def rerun_pending_recovery_posture(
    resolved: ResolvedPaths,
    manifest: Mapping[str, Any],
) -> dict[str, Any]:
    pending_rows = [
        row
        for row in manifest.get("rows") or []
        if isinstance(row, Mapping)
        and str(row.get("lifecycle_state") or row.get("status") or "").strip().casefold() == "pending"
    ]
    return _selected_rows_recovery_posture(
        resolved,
        manifest,
        pending_rows,
        scope="pending_only",
    )


def _set_csv_value(row: dict[str, str], fieldnames: list[str], key: str, value: Any) -> None:
    existing = next((name for name in fieldnames if name.casefold() == key.casefold()), "")
    target = existing or key
    if not existing:
        fieldnames.append(key)
    row[target] = "" if value is None else str(value)


def _materialize_identity_recovery_csv(
    resolved: ResolvedPaths,
    *,
    manifest_path: Path,
    manifest: Mapping[str, Any],
    source_csv_path: Path,
    recovery_scope: str,
    recovery_rows: list[Mapping[str, Any]],
) -> dict[str, Any]:
    fieldnames, original_rows = read_rerun_csv_rows(source_csv_path)
    selected_rows: list[dict[str, str]] = []
    selected_indexes: set[int] = set()
    batch_id = str(manifest.get("batch_id") or manifest_path.stem)
    for retry_row in recovery_rows:
        row_index = _int_or_none(retry_row.get("row_index"))
        source_path = _source_path_from_row(retry_row)
        if row_index is None or not source_path:
            raise RuntimeError(f"{recovery_scope} row is missing its durable row_index/source_path selector.")
        if row_index in selected_indexes:
            raise RuntimeError(f"{recovery_scope} row_index {row_index} is duplicated in the source manifest.")
        if row_index >= len(original_rows):
            raise RuntimeError(f"{recovery_scope} row_index {row_index} is outside the source CSV.")
        original_row = dict(original_rows[row_index])
        if _normalize_path_text(_source_path_from_row(original_row)) != _normalize_path_text(source_path):
            raise RuntimeError(
                f"{recovery_scope} row_index {row_index} no longer matches its source CSV path."
            )
        if not _csv_row_enabled(original_row):
            raise RuntimeError(
                f"{recovery_scope} row_index {row_index} is disabled in the source CSV; create a reviewed CSV to retry it."
            )
        source_identity_v2 = str(
            retry_row.get("planned_source_identity_v2") or retry_row.get("source_identity_v2") or ""
        ).strip()
        if not source_identity_v2:
            raise RuntimeError(
                f"{recovery_scope} row_index {row_index} has no source_identity_v2 evidence; automatic retry is unsafe."
            )
        source_content_sha256 = _source_content_sha256(retry_row)
        if not source_content_sha256:
            raise RuntimeError(
                f"{recovery_scope} row_index {row_index} has no durable full-content SHA-256 evidence; "
                "automatic recovery is unsafe."
            )
        original_content_sha256 = _source_content_sha256(original_row)
        if original_content_sha256 and original_content_sha256 != source_content_sha256:
            raise RuntimeError(
                f"{recovery_scope} row_index {row_index} has conflicting source_content_sha256 evidence."
            )
        identity_values = {
            "source_size": retry_row.get("source_size"),
            "source_mtime_utc": retry_row.get("source_mtime_utc"),
            "source_identity_v2": source_identity_v2,
            "source_identity_v2_algorithm": retry_row.get("source_identity_v2_algorithm"),
            "source_content_sha256": source_content_sha256,
            "source_content_sha256_algorithm": _FULL_CONTENT_SHA256_ALGORITHM,
        }
        for field in _RETRY_IDENTITY_FIELDS:
            if identity_values[field] not in (None, ""):
                _set_csv_value(original_row, fieldnames, field, identity_values[field])
        _set_csv_value(original_row, fieldnames, "rerun_retry_of_batch_id", batch_id)
        _set_csv_value(original_row, fieldnames, "rerun_retry_of_row_index", row_index)
        _set_csv_value(original_row, fieldnames, "rerun_retry_reason_code", recovery_scope)
        selected_rows.append(original_row)
        selected_indexes.add(row_index)
    if not selected_rows:
        raise RuntimeError(f"Manifest has no {recovery_scope} rows to recover.")

    output_root = scoped_rerun_csv_root(resolved)
    if output_root is None:
        raise RuntimeError("State root is unavailable; cannot materialize recovery CSV.")
    output_root.mkdir(parents=True, exist_ok=True)
    if not fieldnames:
        fieldnames = sorted({key for row in selected_rows for key in row})
    source_digest = _hash_text(str(manifest_path), length=12)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_path = output_root / f"rerun_continue_{recovery_scope}_{stamp}_{source_digest}.csv"
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=fieldnames, extrasaction="ignore")
    writer.writeheader()
    for row in selected_rows:
        writer.writerow({key: row.get(key, "") for key in fieldnames})
    atomic_write_text(output_path, buffer.getvalue(), encoding="utf-8")
    return {
        "schema_version": RERUN_CONTINUE_SCHEMA_VERSION,
        "recovery_scope": recovery_scope,
        "source_csv_path": str(source_csv_path),
        "scoped_csv_path": str(output_path),
        "source_manifest_path": str(manifest_path),
        "source_manifest_key": _manifest_key(manifest_path),
        "source_batch_id": batch_id,
        "row_count": len(selected_rows),
        "recovery_source_count": len(selected_rows),
        "recovery_row_selectors": [
            {
                "row_index": _required_row_index(row),
                "source_path": _source_path_from_row(row),
                "source_identity_v2": str(
                    row.get("planned_source_identity_v2") or row.get("source_identity_v2") or ""
                ).strip(),
            }
            for row in recovery_rows
        ],
        "retry_exhausted_source_count": len(selected_rows) if recovery_scope == RETRY_EXHAUSTED_STATUS else 0,
        "preserved_source_identity_v2": True,
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
    request_id = str(request.get("request_id") or "").strip()
    if not request_id:
        return (
            CommandResult(
                command="rerun.continue",
                ok=False,
                severity="error",
                message="request_id is required for exactly-once CSV rerun recovery.",
                errors=["request_id_required"],
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
    if not rerun_manifest_declared_path_matches_actual(manifest, manifest_path):
        return (
            CommandResult(
                command="rerun.continue",
                ok=False,
                severity="error",
                message=(
                    "Rerun manifest recovery is blocked because this v2 manifest was selected from a path "
                    "different from the path declared by its writer."
                ),
                errors=["rerun_manifest_path_mismatch"],
                data={
                    "manifest_path": str(manifest_path),
                    "declared_manifest_path": str(manifest.get("manifest_path") or ""),
                    "schema_version": str(manifest.get("schema_version") or ""),
                },
            ),
            None,
            None,
        )
    if not rerun_manifest_path_matches_canonical_batch(resolved, manifest, manifest_path):
        return (
            CommandResult(
                command="rerun.continue",
                ok=False,
                severity="error",
                message=(
                    "Rerun manifest recovery is blocked because this v2 manifest is not stored at its "
                    "canonical batch path."
                ),
                errors=["rerun_manifest_path_mismatch"],
                data={
                    "manifest_path": str(manifest_path),
                    "declared_manifest_path": str(manifest.get("manifest_path") or ""),
                    "schema_version": str(manifest.get("schema_version") or ""),
                },
            ),
            None,
            None,
        )
    if str(manifest.get("schema_version") or "").strip() == _RERUN_MANIFEST_V2_SCHEMA_VERSION:
        manifest_batch_id = str(manifest.get("batch_id") or "").strip()
        declared_enrollment_path = normalized_rerun_path_text(manifest.get("enrollment_path"))
        available_enrollments = [
            (path, enrollment)
            for path, enrollment in rerun_enrollment_candidates(resolved, limit=10_000)
            if (
                manifest_batch_id
                and str(enrollment.get("batch_id") or "").strip() == manifest_batch_id
            )
            or (
                declared_enrollment_path
                and normalized_rerun_path_text(path) == declared_enrollment_path
            )
        ]
        enrollment_matches = any(
            rerun_manifest_matches_enrollment(
                manifest,
                enrollment,
                enrollment_path=enrollment_path,
                manifest_path=manifest_path,
            )
            for enrollment_path, enrollment in available_enrollments
        )
        if available_enrollments and not enrollment_matches:
            return (
                CommandResult(
                    command="rerun.continue",
                    ok=False,
                    severity="error",
                    message=(
                        "Rerun manifest recovery is blocked because its selected path does not match the "
                        "durable enrollment correlation."
                    ),
                    errors=["rerun_manifest_path_mismatch", "rerun_manifest_enrollment_mismatch"],
                    data={
                        "manifest_path": str(manifest_path),
                        "declared_manifest_path": str(manifest.get("manifest_path") or ""),
                        "declared_enrollment_path": str(manifest.get("enrollment_path") or ""),
                        "schema_version": str(manifest.get("schema_version") or ""),
                    },
                ),
                None,
                None,
            )
    manifest_status = str(manifest.get("status") or "").strip().casefold()
    retry_exhausted_manifest = manifest_status in COMPLETED_WITH_FAILURES_STATUSES
    waiting_restart_manifest = manifest_status in WAITING_RESTART_STATUSES
    if (
        manifest_status != STOPPED_AFTER_CURRENT_STATUS
        and not retry_exhausted_manifest
        and not waiting_restart_manifest
    ):
        return (
            CommandResult(
                command="rerun.continue",
                ok=False,
                severity="error",
                message=(
                    "Only stopped_after_current manifests with pending rows or completed_with_failures manifests "
                    "with retry_exhausted rows can continue. Waiting manifests require correlated child-exit proof."
                ),
                errors=["rerun_manifest_not_stopped_after_current", "rerun_manifest_not_recoverable"],
                data={"manifest_path": str(manifest_path), "status": str(manifest.get("status") or "")},
            ),
            None,
            None,
        )
    rows = [row for row in manifest.get("rows") or [] if isinstance(row, Mapping)]
    source_csv_path = _manifest_source_csv_path(manifest)
    all_retry_rows = [
        row
        for row in rows
        if str(row.get("lifecycle_state") or row.get("status") or "").strip().casefold()
        == RETRY_EXHAUSTED_STATUS
    ]
    retry_posture = (
        rerun_retry_exhausted_recovery_posture(resolved, manifest)
        if retry_exhausted_manifest
        else {}
    )
    retry_rows = [
        row
        for row in retry_posture.get("recoverable_rows") or []
        if isinstance(row, Mapping)
    ]
    waiting_rows = [
        row
        for row in rows
        if str(row.get("lifecycle_state") or row.get("status") or "").strip().casefold()
        in WAITING_RESTART_STATUSES
    ]
    pending_indexed_source_keys: set[tuple[int, str]] = set()
    pending_indexes: set[int] = set()
    legacy_pending_source_keys: set[str] = set()
    pending_recovery_posture: dict[str, Any] = {}
    if manifest_status == STOPPED_AFTER_CURRENT_STATUS:
        pending_indexed_source_keys, pending_indexes, legacy_pending_source_keys = _pending_manifest_row_selectors(manifest)
        pending_recovery_posture = rerun_pending_recovery_posture(resolved, manifest)
    if manifest_status == STOPPED_AFTER_CURRENT_STATUS and not (
        pending_indexed_source_keys or pending_indexes or legacy_pending_source_keys
    ):
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
    if retry_exhausted_manifest and not all_retry_rows:
        return (
            CommandResult(
                command="rerun.continue",
                ok=False,
                severity="warning",
                message="Completed-with-failures rerun manifest has no retry_exhausted rows to recover.",
                warnings=["no_retry_exhausted_rerun_rows"],
                data={"manifest_path": str(manifest_path), "row_status_counts": _row_status_counts(rows)},
            ),
            None,
            None,
        )
    if source_csv_path is None or not source_csv_path.is_file():
        return (
            CommandResult(
                command="rerun.continue",
                ok=False,
                severity="error",
                message="Rerun source CSV is missing; recovery rows cannot be verified.",
                errors=["rerun_source_csv_missing"],
                data={"manifest_path": str(manifest_path)},
            ),
            None,
            None,
        )
    if retry_exhausted_manifest and not retry_rows:
        blocked_reason_codes = {
            str(row.get("reason_code") or "")
            for row in retry_posture.get("blocked_rows") or []
            if isinstance(row, Mapping)
        }
        source_csv_missing = bool(
            blocked_reason_codes & {"source_csv_missing", "source_csv_unreadable"}
        )
        return (
            CommandResult(
                command="rerun.continue",
                ok=False,
                severity="error",
                message=(
                    "Rerun source CSV is missing or unreadable; exhausted rows cannot be verified."
                    if source_csv_missing
                    else (
                        "No retry_exhausted rows passed the backend's durable source-CSV row selector, "
                        "source_identity_v2, and strong-hash checks."
                    )
                ),
                errors=[
                    "rerun_source_csv_missing"
                    if source_csv_missing
                    else "retry_exhausted_source_identity_missing"
                ],
                data={
                    "manifest_path": str(manifest_path),
                    "row_status_counts": _row_status_counts(rows),
                    "retry_exhausted_recovery_posture": retry_posture,
                },
            ),
            None,
            None,
        )
    waiting_restart_evidence: dict[str, Any] = {}
    if waiting_restart_manifest:
        if not waiting_rows:
            return (
                CommandResult(
                    command="rerun.continue",
                    ok=False,
                    severity="warning",
                    message="Waiting rerun manifest has no waiting/retry-scheduled rows to recover.",
                    warnings=["no_waiting_rerun_rows"],
                    data={"manifest_path": str(manifest_path), "row_status_counts": _row_status_counts(rows)},
                ),
                None,
                None,
            )
        waiting_restart_evidence = rerun_waiting_restart_posture(resolved, manifest)
        if waiting_restart_evidence.get("manual_retry_available") is not True:
            child_active = waiting_restart_evidence.get("state") == "child_active"
            code = "rerun_waiting_child_still_active" if child_active else "rerun_waiting_exit_not_proven"
            message = str(waiting_restart_evidence.get("reason") or "Waiting rerun recovery is not safe.")
            return (
                CommandResult(
                    command="rerun.continue",
                    ok=False,
                    severity="warning" if child_active else "error",
                    message=message,
                    warnings=[code] if child_active else [],
                    errors=[] if child_active else [code],
                    data={
                        "manifest_path": str(manifest_path),
                        "row_status_counts": _row_status_counts(rows),
                        "waiting_restart_evidence": waiting_restart_evidence,
                    },
                ),
                None,
                None,
            )
        source_recovery_posture = waiting_restart_evidence.get("source_recovery_posture")
        waiting_rows = [
            row
            for row in (
                source_recovery_posture.get("recoverable_rows")
                if isinstance(source_recovery_posture, Mapping)
                else []
            )
            or []
            if isinstance(row, Mapping)
        ]
    if retry_exhausted_manifest:
        recovery_scope = RETRY_EXHAUSTED_STATUS
        recovery_rows = retry_rows
    elif waiting_restart_manifest:
        recovery_scope = "waiting_restart"
        recovery_rows = waiting_rows
    else:
        recovery_scope = "pending_only"
        recovery_rows = [
            row
            for row in pending_recovery_posture.get("recoverable_rows") or []
            if isinstance(row, Mapping)
        ]
        if not recovery_rows:
            blocked_reason_codes = {
                str(row.get("reason_code") or "")
                for row in pending_recovery_posture.get("blocked_rows") or []
                if isinstance(row, Mapping)
            }
            source_csv_missing = bool(
                blocked_reason_codes & {"source_csv_missing", "source_csv_unreadable"}
            )
            return (
                CommandResult(
                    command="rerun.continue",
                    ok=False,
                    severity="error",
                    message=(
                        "Rerun source CSV is missing or unreadable; pending rows cannot be verified."
                        if source_csv_missing
                        else (
                            "Pending rerun rows lack durable source-CSV row, source_identity_v2, or strong-hash "
                            "evidence; legacy rows remain in review."
                        )
                    ),
                    errors=[
                        "rerun_source_csv_missing"
                        if source_csv_missing
                        else "pending_rerun_recovery_unqualified"
                    ],
                    data={
                        "manifest_path": str(manifest_path),
                        "pending_recovery_posture": pending_recovery_posture,
                    },
                ),
                None,
                None,
            )
    recovery_row_selectors = _recovery_row_selectors(recovery_rows)
    source_manifest_key = _manifest_key(manifest_path)
    source_command_id = str(manifest.get("command_id") or "").strip()
    source_launch_id = str(manifest.get("launch_id") or "").strip()
    source_batch_id = str(manifest.get("batch_id") or "").strip()
    canonical_recovery_root_key = _logical_rerun_recovery_key(
        command_id=source_command_id,
        launch_id=source_launch_id,
        batch_id=source_batch_id,
        recovery_scope=recovery_scope,
        row_selectors=recovery_row_selectors,
    )
    enrollment_namespaces = _logical_recovery_enrollments(
        resolved,
        source_command_id=source_command_id,
        source_launch_id=source_launch_id,
        source_batch_id=source_batch_id,
        recovery_scope=recovery_scope,
        row_selectors=recovery_row_selectors,
    )
    matching_request = next(
        (
            item
            for item in sorted(enrollment_namespaces, key=lambda existing: existing[1][2], reverse=True)
            if str(item[1][1].get("recovery_request_id") or "").strip() == request_id
        ),
        None,
    )
    if matching_request is not None:
        existing_root_key, (existing_path, existing_enrollment, existing_generation) = matching_request
        return (
            _existing_recovery_result(
                enrollment_path=existing_path,
                enrollment=existing_enrollment,
                request_id=request_id,
                recovery_root_key=existing_root_key,
                recovery_generation=existing_generation,
            ),
            None,
            None,
        )
    blocking_enrollment = next(
        (
            item
            for item in sorted(enrollment_namespaces, key=lambda existing: existing[1][2], reverse=True)
            if not _recovery_enrollment_can_be_superseded(item[1][1])
        ),
        None,
    )
    if blocking_enrollment is not None:
        existing_root_key, (existing_path, existing_enrollment, existing_generation) = blocking_enrollment
        return (
            _existing_recovery_result(
                enrollment_path=existing_path,
                enrollment=existing_enrollment,
                request_id=request_id,
                recovery_root_key=existing_root_key,
                recovery_generation=existing_generation,
            ),
            None,
            None,
        )
    recovery_root_key = canonical_recovery_root_key
    existing_enrollments = [item for _root_key, item in enrollment_namespaces]
    recovery_generation = max(
        (generation for _path, _enrollment, generation in existing_enrollments),
        default=0,
    ) + 1
    recovery_key = _recovery_key_for_generation(recovery_root_key, recovery_generation)
    superseded = max(existing_enrollments, key=lambda existing: existing[2], default=None)
    if source_csv_path is None or not source_csv_path.is_file():
        return (
            CommandResult(
                command="rerun.continue",
                ok=False,
                severity="error",
                message="Rerun source CSV is missing; continuation cannot materialize the selected rows.",
                errors=["rerun_source_csv_missing"],
                data={"manifest_path": str(manifest_path), "source_csv_path": str(source_csv_path or "")},
            ),
            None,
            None,
        )
    try:
        if retry_exhausted_manifest:
            scoped_info = _materialize_identity_recovery_csv(
                resolved,
                manifest_path=manifest_path,
                manifest=manifest,
                source_csv_path=source_csv_path,
                recovery_scope=RETRY_EXHAUSTED_STATUS,
                recovery_rows=retry_rows,
            )
            scoped_info["retry_exhausted_total_count"] = len(all_retry_rows)
            scoped_info["retry_exhausted_unrecoverable_count"] = int(
                retry_posture.get("unrecoverable_count") or 0
            )
            scoped_info["retry_exhausted_recovery_posture"] = retry_posture
        elif waiting_restart_manifest:
            scoped_info = _materialize_identity_recovery_csv(
                resolved,
                manifest_path=manifest_path,
                manifest=manifest,
                source_csv_path=source_csv_path,
                recovery_scope="waiting_restart",
                recovery_rows=waiting_rows,
            )
            scoped_info["waiting_restart_evidence"] = waiting_restart_evidence
        else:
            scoped_info = _materialize_identity_recovery_csv(
                resolved,
                manifest_path=manifest_path,
                manifest=manifest,
                source_csv_path=source_csv_path,
                recovery_scope="pending_only",
                recovery_rows=recovery_rows,
            )
            scoped_info["pending_total_count"] = int(
                pending_recovery_posture.get("total_count") or 0
            )
            scoped_info["pending_unrecoverable_count"] = int(
                pending_recovery_posture.get("unrecoverable_count") or 0
            )
            scoped_info["pending_recovery_posture"] = pending_recovery_posture
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
    scoped_info.update(
        {
            "recovery_request_id": request_id,
            "recovery_key": recovery_key,
            "recovery_root_key": recovery_root_key,
            "recovery_generation": recovery_generation,
            "recovery_supersedes_enrollment_path": str(superseded[0]) if superseded is not None else "",
            "recovery_supersedes_recovery_key": (
                str(superseded[1].get("recovery_key") or "") if superseded is not None else ""
            ),
            "recovery_supersedes_batch_id": (
                str(superseded[1].get("batch_id") or "") if superseded is not None else ""
            ),
            "recovery_source_command_id": source_command_id,
            "recovery_source_launch_id": source_launch_id,
            "recovery_source_batch_id": source_batch_id,
            "recovery_source_manifest_path": str(manifest_path),
            "recovery_source_manifest_key": source_manifest_key,
            "recovery_scope": recovery_scope,
            "recovery_row_selectors": recovery_row_selectors,
        }
    )
    command_id = str(request.get("_command_id") or request.get("command_id") or "").strip()
    if command_id:
        continue_request["_command_id"] = command_id
    return None, continue_request, scoped_info


__all__ = [
    "RERUN_CONTINUE_SCHEMA_VERSION",
    "RERUN_CONTROL_SCHEMA_VERSION",
    "COMPLETED_WITH_FAILURES_STATUS",
    "COMPLETED_WITH_FAILURES_STATUSES",
    "RETRY_EXHAUSTED_STATUS",
    "WAITING_RESTART_STATUSES",
    "STOPPED_AFTER_CURRENT_STATUS",
    "build_rerun_continue_pending_request",
    "request_rerun_stop_after_current",
    "rerun_pending_recovery_posture",
    "rerun_retry_exhausted_recovery_posture",
    "rerun_waiting_restart_posture",
    "rerun_control_root",
    "rerun_stop_marker_path",
]
