"""Read-only lifecycle evidence for local CSV rerun status surfaces."""

from __future__ import annotations

import json
import os
import time
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from mediapipeline.core.paths.contracts import ResolvedPaths


_PROVEN_EXECUTION_EXIT_STATES = frozenset(
    {
        "waiting",
        "waiting_for_source",
        "retry_scheduled",
        "retrying",
        "retry_exhausted",
        "stopped_after_current",
        "stopped",
        "cancelled",
        "complete",
        "completed",
        "completed_with_failures",
        "completed_with_failed_rows",
        "done",
        "succeeded",
        "success",
        "failed",
        "failed_before_manifest",
        "blocked",
        "invalid",
        "missing",
        "pending_publish",
        "parked",
        "review_workspace",
        "review",
        "awaiting_review",
        "published_replace_final",
        "published_non_overlap",
        "returned",
        "replaced",
        "skipped",
        "disabled",
    }
)


def _read_json_file(path: Path, *, retries: int = 1, delay_seconds: float = 0.05) -> Any | None:
    attempts = retries + 1
    last_exc: Exception | None = None
    for attempt in range(attempts):
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:
            last_exc = exc
            if attempt + 1 >= attempts:
                break
            time.sleep(delay_seconds)
    if last_exc:
        raise last_exc
    return None


def _resolved_local_base(resolved: ResolvedPaths) -> Path:
    if resolved.local_base is not None:
        return Path(resolved.local_base)
    config_data = dict(getattr(resolved, "config_data", {}) or {})
    configured = str(config_data.get("LocalBase") or "").strip()
    if configured:
        return Path(configured)
    if resolved.state_root is not None and Path(resolved.state_root).name.casefold() == "state":
        return Path(resolved.state_root).parent
    return Path(resolved.app_root) / "LocalBase"


def rerun_enrollment_root(resolved: ResolvedPaths) -> Path:
    if resolved.state_root is not None:
        state_root = Path(resolved.state_root)
    elif resolved.active_jobs_path is not None:
        state_root = Path(resolved.active_jobs_path).parent
    else:
        state_root = _resolved_local_base(resolved) / "State"
    return state_root / "Rerun" / "Local"


def read_rerun_enrollment(path: Path) -> dict[str, Any] | None:
    try:
        payload = _read_json_file(path, retries=1)
    except Exception:
        return None
    return dict(payload) if isinstance(payload, Mapping) else None


def normalized_rerun_path_text(value: object) -> str:
    text = str(value or "").strip()
    return os.path.normcase(os.path.normpath(text)) if text else ""


def _active_jobs_dir_for_resolved(resolved: ResolvedPaths) -> Path | None:
    if resolved.active_jobs_path:
        return Path(resolved.active_jobs_path)
    if resolved.state_root:
        return Path(resolved.state_root) / "ActiveJobs"
    return None


def _expected_active_job_path(resolved: ResolvedPaths, launch_id: str) -> Path | None:
    folder = _active_jobs_dir_for_resolved(resolved)
    normalized_launch_id = str(launch_id or "").strip()
    if folder is None or not normalized_launch_id:
        return None
    safe_launch_id = "".join(
        character if character.isalnum() or character in "-_." else "-"
        for character in normalized_launch_id
    )
    if safe_launch_id != normalized_launch_id:
        return None
    return folder / f"{safe_launch_id}.json"


def exact_rerun_active_job_payload(
    resolved: ResolvedPaths,
    payload: Mapping[str, Any],
) -> tuple[Path | None, dict[str, Any] | None]:
    launch_id = str(payload.get("launch_id") or "").strip()
    batch_id = str(payload.get("batch_id") or "").strip()
    expected_path = _expected_active_job_path(resolved, launch_id)
    if expected_path is None or not expected_path.is_file():
        return expected_path, None
    try:
        raw = _read_json_file(expected_path, retries=1)
    except Exception:
        return expected_path, None
    if not isinstance(raw, Mapping):
        return expected_path, None
    record = dict(raw)
    metadata = dict(record.get("metadata") or {}) if isinstance(record.get("metadata"), Mapping) else {}
    if str(record.get("launch_id") or "").strip() != launch_id:
        return expected_path, None
    if str(record.get("job_kind") or "").strip().casefold() != "rerun_csv":
        return expected_path, None
    record_batch_id = str(metadata.get("batch_id") or "").strip()
    if batch_id and record_batch_id != batch_id:
        return expected_path, None
    command_id = str(payload.get("command_id") or "").strip()
    recorded_command_id = str(metadata.get("command_id") or "").strip()
    if command_id and recorded_command_id != command_id:
        return expected_path, None
    for key in ("enrollment_path", "manifest_path"):
        expected = normalized_rerun_path_text(payload.get(key))
        recorded = normalized_rerun_path_text(metadata.get(key))
        if expected and recorded != expected:
            return expected_path, None
    return expected_path, record


def rerun_correlation_evidence(
    resolved: ResolvedPaths,
    payload: Mapping[str, Any],
    *,
    enrollment_path: Path | str | None = None,
    manifest_path: Path | str | None = None,
) -> dict[str, Any]:
    merged = dict(payload)
    if enrollment_path not in (None, ""):
        merged["enrollment_path"] = str(enrollment_path)
    if manifest_path not in (None, ""):
        merged["manifest_path"] = str(manifest_path)
    active_job_path, active_job = exact_rerun_active_job_payload(resolved, merged)
    evidence_links = dict(merged.get("evidence_links") or {}) if isinstance(merged.get("evidence_links"), Mapping) else {}
    active_job = dict(active_job or {})
    command_id = str(merged.get("command_id") or "").strip()
    launch_id = str(merged.get("launch_id") or "").strip()
    batch_id = str(merged.get("batch_id") or "").strip()
    return {
        "command_id": command_id,
        "launch_id": launch_id,
        "batch_id": batch_id,
        "manifest_path": str(merged.get("manifest_path") or ""),
        "enrollment_path": str(merged.get("enrollment_path") or ""),
        "active_jobs_key": launch_id,
        "active_jobs_path": str(active_job_path or ""),
        "active_jobs_correlated": bool(active_job),
        "active_jobs_correlation_status": "matched" if active_job else "missing_or_mismatched",
        "stdout_log": str(active_job.get("stdout_log") or evidence_links.get("stdout_log") or ""),
        "stderr_log": str(active_job.get("stderr_log") or evidence_links.get("stderr_log") or ""),
        "command_evidence_key": command_id,
    }


def semantic_rerun_lifecycle_state(payload: Mapping[str, Any]) -> str:
    lifecycle_state = str(payload.get("lifecycle_state") or "").strip().casefold()
    status = str(payload.get("status") or "").strip().casefold()
    if lifecycle_state == "terminal" and status:
        return status
    return lifecycle_state or status


def rerun_execution_manifest_has_durable_exit_state(payload: Mapping[str, Any]) -> bool:
    lifecycle_state = str(payload.get("lifecycle_state") or "").strip().casefold()
    status = semantic_rerun_lifecycle_state(payload)
    if lifecycle_state == "terminal" or status in _PROVEN_EXECUTION_EXIT_STATES:
        return True
    row_states = [
        (str(row.get("lifecycle_state") or "").strip().casefold(), semantic_rerun_lifecycle_state(row))
        for row in payload.get("rows") or []
        if isinstance(row, Mapping)
    ]
    return bool(row_states) and all(
        lifecycle == "terminal" or semantic in _PROVEN_EXECUTION_EXIT_STATES
        for lifecycle, semantic in row_states
    )


def rerun_enrollment_candidates(
    resolved: ResolvedPaths,
    *,
    limit: int = 100,
) -> list[tuple[Path, dict[str, Any]]]:
    root = rerun_enrollment_root(resolved)
    if not root.exists():
        return []
    try:
        paths = sorted(root.glob("*.json"), key=lambda item: item.stat().st_mtime, reverse=True)
    except OSError:
        return []
    result: list[tuple[Path, dict[str, Any]]] = []
    for path in paths[: max(1, int(limit))]:
        payload = read_rerun_enrollment(path)
        if payload is not None:
            result.append((path, payload))
    return result


__all__ = [
    "exact_rerun_active_job_payload",
    "normalized_rerun_path_text",
    "read_rerun_enrollment",
    "rerun_correlation_evidence",
    "rerun_enrollment_candidates",
    "rerun_enrollment_root",
    "rerun_execution_manifest_has_durable_exit_state",
    "semantic_rerun_lifecycle_state",
]
