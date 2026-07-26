"""Durable backend-owned lifecycle evidence for local CSV rerun launches."""

from __future__ import annotations

import csv
import json
import threading
import uuid
from collections import Counter
from collections.abc import Callable, Iterator, Mapping, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

try:
    import psutil
except Exception:  # pragma: no cover - optional runtime dependency
    psutil = None

from mediapipeline.core.paths.contracts import ResolvedPaths
from mediapipeline.core.processes.active_jobs import active_job_pid_is_alive
from mediapipeline.core.processes.file_io import atomic_write_text, read_json_file
from mediapipeline.core.rerun.evidence import (
    exact_rerun_active_job_payload as _exact_active_job_payload,
    normalized_rerun_path_text as _normalized_path_text,
    read_rerun_enrollment,
    rerun_correlation_evidence,
    rerun_enrollment_candidates,
    rerun_enrollment_root,
    rerun_execution_manifest_has_durable_exit_state,
    semantic_rerun_lifecycle_state as _semantic_lifecycle_state,
)


RERUN_ENROLLMENT_SCHEMA_VERSION = "desktop_rerun_local_enrollment.v1"
RERUN_QUEUE_SOURCE = "csv_rerun"
_RERUN_ENROLLMENT_TRANSITION_LOCK = threading.RLock()
_PRESERVED_EXIT_STATES = frozenset(
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
        "failed",
        "pending_publish",
        "review_workspace",
        "review",
        "awaiting_review",
        "failed_before_manifest",
    }
)
_TERMINAL_ENROLLMENT_STATES = frozenset(
    {
        "failed",
        "failed_before_manifest",
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
_TERMINAL_ACTIVE_JOB_STATUSES = frozenset(
    {
        "completed",
        "failed",
        "completed_immediate",
        "failed_immediate",
        "exited",
        "killed",
        "orphaned",
        "stopped",
    }
)
_MUTABLE_ENROLLMENT_ROW_STATES = frozenset(
    {
        "accepted",
        "process_spawned",
        "starting",
        "processing",
        "waiting",
        "waiting_for_source",
        "retry_scheduled",
        "retrying",
    }
)
_TRUE_CSV_VALUES = frozenset({"1", "true", "yes", "y", "on", "enabled", "run"})
_LIFECYCLE_GUIDANCE: dict[str, dict[str, Any]] = {
    "requested": {
        "what": "The backend received the CSV rerun command.",
        "reason_code": "request_received",
        "reason": "The backend received this CSV rerun command and began durable enrollment.",
        "automatic_next_action": "Validate and durably accept the command before process launch.",
        "operator_action_required": False,
        "available_operator_action": "No operator action is required.",
    },
    "accepted": {
        "what": "The CSV rerun request is durably enrolled.",
        "reason_code": "request_accepted",
        "reason": "The backend durably enrolled this CSV rerun request before process launch.",
        "automatic_next_action": "Spawn the dedicated CSV rerun process and record its launch evidence.",
        "operator_action_required": False,
        "available_operator_action": "No operator action is required.",
    },
    "process_spawned": {
        "what": "The dedicated CSV rerun process has spawned.",
        "reason_code": "rerun_process_spawned",
        "reason": "The backend spawned the dedicated CSV rerun process after durable enrollment.",
        "automatic_next_action": "Wait for the rerun engine to record execution-manifest lifecycle evidence.",
        "operator_action_required": False,
        "available_operator_action": "Monitor Queue or Results for newer backend evidence.",
    },
    "spawn_transition_ambiguous": {
        "what": "The CSV rerun child may still be running, but its spawn transition is ambiguous.",
        "reason_code": "rerun_process_spawn_transition_exit_unverified",
        "reason": "The backend could not persist spawn proof or verify that the spawned child exited.",
        "automatic_next_action": "Preserve the enrollment and block duplicate launch until child identity is reconciled.",
        "operator_action_required": True,
        "available_operator_action": "Inspect ActiveJobs and process logs; do not submit a duplicate rerun.",
    },
    "failed": {
        "what": "The CSV rerun process ended without complete execution evidence.",
        "reason_code": "rerun_process_failed",
        "reason": "The rerun process ended without complete recoverable or terminal execution evidence.",
        "automatic_next_action": "Do not assume any row completed; preserve source media and inspect the durable evidence.",
        "operator_action_required": True,
        "available_operator_action": "Inspect ActiveJobs and process logs, correct the failure, then submit a new rerun request.",
    },
    "failed_before_manifest": {
        "what": "The CSV rerun process ended before row execution evidence was created.",
        "reason_code": "rerun_process_failed_before_manifest",
        "reason": "The rerun process ended before an execution manifest recorded row lifecycle evidence.",
        "automatic_next_action": "Do not assume the rerun ran; preserve source media and inspect the launch evidence.",
        "operator_action_required": True,
        "available_operator_action": "Inspect ActiveJobs and process logs, correct the failure, then submit a new rerun request.",
    },
    "disabled": {
        "what": "This CSV row is disabled.",
        "reason_code": "csv_row_disabled",
        "reason": "The CSV row is disabled by its enabled field.",
        "automatic_next_action": "Skip this row; no media processing will run for it.",
        "operator_action_required": False,
        "available_operator_action": "Enable the row in a new CSV only if it should run in a future rerun.",
    },
    "waiting_for_source": {
        "what": "The CSV rerun is waiting for its source location.",
        "reason_code": "source_location_unavailable",
        "reason": "The rerun is waiting for source availability evidence.",
        "automatic_next_action": "Wait for source availability and bounded retry evidence.",
        "operator_action_required": False,
        "available_operator_action": "Restore source access or request Retry now.",
    },
    "retry_scheduled": {
        "what": "A bounded CSV rerun retry is scheduled.",
        "reason_code": "retry_scheduled",
        "reason": "The backend scheduled a bounded retry.",
        "automatic_next_action": "Wait for the scheduled retry attempt.",
        "operator_action_required": False,
        "available_operator_action": "Wait or request Retry now.",
    },
    "retrying": {
        "what": "The CSV rerun is performing a bounded retry.",
        "reason_code": "retrying",
        "reason": "The backend is retrying the rerun operation.",
        "automatic_next_action": "Wait for the retry result.",
        "operator_action_required": False,
        "available_operator_action": "Monitor Queue or Results for newer backend evidence.",
    },
    "retry_exhausted": {
        "what": "The CSV rerun exhausted its automatic retry budget.",
        "reason_code": "retry_exhausted",
        "reason": "The bounded automatic retry budget is exhausted.",
        "automatic_next_action": "Wait for an explicit operator retry request.",
        "operator_action_required": True,
        "available_operator_action": "Request one explicit retry after correcting the source-access problem.",
    },
}


def _now_text() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


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


def rerun_execution_manifest_root(resolved: ResolvedPaths) -> Path:
    return _resolved_local_base(resolved) / "RerunManifests"


@dataclass(frozen=True)
class RerunCorrelation:
    command_id: str
    launch_id: str
    batch_id: str
    enrollment_path: Path
    manifest_path: Path


def new_rerun_correlation(resolved: ResolvedPaths, *, command_id: str = "") -> RerunCorrelation:
    now = datetime.now(UTC).strftime("%Y%m%d_%H%M%S_%f")
    nonce = uuid.uuid4().hex[:10]
    batch_id = f"rerun_{now}_{nonce}"
    normalized_command_id = str(command_id or "").strip() or uuid.uuid4().hex
    launch_id = f"{batch_id}_launch_{uuid.uuid4().hex[:8]}"
    return RerunCorrelation(
        command_id=normalized_command_id,
        launch_id=launch_id,
        batch_id=batch_id,
        enrollment_path=rerun_enrollment_root(resolved) / f"{batch_id}.json",
        manifest_path=rerun_execution_manifest_root(resolved) / f"{batch_id}.json",
    )


def _csv_rows(csv_path: Path) -> list[dict[str, Any]]:
    with csv_path.open("r", encoding="utf-8-sig", newline="") as handle:
        source_rows = [dict(row) for row in csv.DictReader(handle)]
    rows: list[dict[str, Any]] = []
    for index, source_row in enumerate(source_rows):
        row = dict(source_row)
        lowered = {str(key).strip().casefold(): value for key, value in source_row.items()}
        raw_enabled = lowered.get("enabled", lowered.get("rerun_enabled", "true"))
        enabled = str(raw_enabled or "").strip().casefold() in _TRUE_CSV_VALUES
        state = "accepted" if enabled else "disabled"
        row.update(
            {
                "row_index": index,
                "rerun_enabled": enabled,
                "status": state,
                "lifecycle_state": state,
                "last_transition_at": "",
                "timeline": [],
            }
        )
        rows.append(row)
    return rows


def _state_evidence(
    state: str,
    *,
    at: str,
    sequence: int,
    reason_code: str = "",
    reason: str = "",
    automatic_next_action: str = "",
    operator_action_required: bool | None = None,
    available_operator_action: str = "",
) -> dict[str, Any]:
    normalized_state = str(state or "").strip().casefold()
    defaults = _LIFECYCLE_GUIDANCE.get(normalized_state, {})
    why = str(reason or defaults.get("reason") or f"The backend recorded lifecycle state {normalized_state}.")
    next_action = str(
        automatic_next_action
        or defaults.get("automatic_next_action")
        or "Wait for newer backend lifecycle evidence."
    )
    required = (
        bool(defaults.get("operator_action_required", False))
        if operator_action_required is None
        else bool(operator_action_required)
    )
    operator_action = str(
        available_operator_action
        or defaults.get("available_operator_action")
        or "Review Queue or Results for durable backend evidence."
    )
    return {
        "sequence": max(1, int(sequence)),
        "state": normalized_state,
        "at": at,
        "reason_code": str(reason_code or defaults.get("reason_code") or f"rerun_{normalized_state}"),
        "what": str(
            defaults.get("what")
            or f"The backend recorded the {normalized_state.replace('_', ' ')} lifecycle state."
        ),
        "why": why,
        "when": at,
        "next": next_action,
        "automatic_next_action": next_action,
        "operator_action_required": required,
        "available_operator_action": operator_action,
    }


def _apply_current_evidence(target: dict[str, Any], evidence: Mapping[str, Any]) -> None:
    target["transition_sequence"] = int(evidence.get("sequence") or 0)
    target["lifecycle_what"] = str(evidence.get("what") or "")
    target["reason_code"] = str(evidence.get("reason_code") or "")
    target["reason"] = str(evidence.get("why") or "")
    target["automatic_next_action"] = str(evidence.get("automatic_next_action") or "")
    target["operator_action_required"] = evidence.get("operator_action_required") is True
    target["available_operator_action"] = str(evidence.get("available_operator_action") or "")


def _write_payload(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_text(path, json.dumps(dict(payload), indent=2, sort_keys=True) + "\n")


def create_rerun_enrollment(
    resolved: ResolvedPaths,
    *,
    correlation: RerunCorrelation,
    csv_path: Path,
    source_csv_path: Path,
    dry_run: bool,
    lifecycle: Mapping[str, Any],
) -> dict[str, Any]:
    created_at = _now_text()
    rows = _csv_rows(csv_path)
    for row in rows:
        row_state = str(row.get("lifecycle_state") or row.get("status") or "accepted")
        if row_state == "accepted":
            requested_evidence = _state_evidence("requested", at=created_at, sequence=1)
            evidence = _state_evidence(row_state, at=created_at, sequence=2)
            row["timeline"] = [requested_evidence, evidence]
        else:
            evidence = _state_evidence(row_state, at=created_at, sequence=1)
            row["timeline"] = [evidence]
        row["last_transition_at"] = created_at
        _apply_current_evidence(row, evidence)
    requested_evidence = _state_evidence("requested", at=created_at, sequence=1)
    accepted_evidence = _state_evidence("accepted", at=created_at, sequence=2)
    payload: dict[str, Any] = {
        "schema_version": RERUN_ENROLLMENT_SCHEMA_VERSION,
        "batch_id": correlation.batch_id,
        "command_id": correlation.command_id,
        "launch_id": correlation.launch_id,
        "enrollment_path": str(correlation.enrollment_path),
        "manifest_path": str(correlation.manifest_path),
        "csv_path": str(csv_path),
        "source_csv_path": str(source_csv_path),
        "queue_source": RERUN_QUEUE_SOURCE,
        "uses_pipeline_start": False,
        "inserted_into_normal_queue": False,
        "durably_enrolled": True,
        "dry_run": bool(dry_run),
        "status": "accepted",
        "lifecycle_state": "accepted",
        "current_phase": "accepted",
        "created_at": created_at,
        "requested_at": created_at,
        "accepted_at": created_at,
        "last_transition_at": created_at,
        "timeline": [requested_evidence, accepted_evidence],
        "rows": rows,
        **dict(lifecycle),
    }
    _apply_current_evidence(payload, accepted_evidence)
    payload["lifecycle_counts"] = rerun_lifecycle_counts(rows)
    _write_payload(correlation.enrollment_path, payload)
    return payload


@contextmanager
def rerun_recovery_enrollment_guard() -> Iterator[None]:
    """Serialize durable recovery lookup through enrollment creation/spawn."""

    with _RERUN_ENROLLMENT_TRANSITION_LOCK:
        yield


def find_rerun_recovery_enrollment(
    resolved: ResolvedPaths,
    recovery_key: str,
) -> tuple[Path, dict[str, Any]] | None:
    normalized_key = str(recovery_key or "").strip()
    if not normalized_key:
        return None
    with _RERUN_ENROLLMENT_TRANSITION_LOCK:
        for path, payload in rerun_enrollment_candidates(resolved, limit=1000):
            if str(payload.get("recovery_key") or "").strip() == normalized_key:
                return path, payload
    return None


def transition_rerun_enrollment(
    path: Path | None,
    state: str,
    *,
    expected_states: set[str] | frozenset[str] | None = None,
    reason_code: str = "",
    reason: str = "",
    pid: int | None = None,
    logs: str = "",
    return_code: int | None = None,
    evidence_links: Mapping[str, Any] | None = None,
    automatic_next_action: str = "",
    operator_action_required: bool | None = None,
    available_operator_action: str = "",
    extra_fields: Mapping[str, Any] | None = None,
) -> dict[str, Any] | None:
    if path is None:
        return None
    with _RERUN_ENROLLMENT_TRANSITION_LOCK:
        payload = read_rerun_enrollment(path)
        if payload is None:
            return None
        current = str(payload.get("lifecycle_state") or payload.get("status") or "").strip().casefold()
        if expected_states is not None and current not in expected_states:
            return payload
        transition_at = _now_text()
        normalized_state = str(state or "").strip().casefold()
        try:
            current_sequence = int(payload.get("transition_sequence") or 0)
        except (TypeError, ValueError):
            current_sequence = 0
        for entry in payload.get("timeline") or []:
            if not isinstance(entry, Mapping):
                continue
            try:
                current_sequence = max(current_sequence, int(entry.get("sequence") or 0))
            except (TypeError, ValueError):
                continue
        transition_sequence = current_sequence + 1
        transition_evidence = _state_evidence(
            normalized_state,
            at=transition_at,
            sequence=transition_sequence,
            reason_code=reason_code,
            reason=reason,
            automatic_next_action=automatic_next_action,
            operator_action_required=operator_action_required,
            available_operator_action=available_operator_action,
        )
        payload["status"] = normalized_state
        payload["lifecycle_state"] = normalized_state
        payload["current_phase"] = normalized_state
        payload["last_transition_at"] = transition_at
        if normalized_state == "process_spawned" and not str(payload.get("started_at") or "").strip():
            payload["started_at"] = transition_at
        if pid is not None:
            payload["pid"] = int(pid)
        if logs:
            payload["logs"] = str(logs)
        if return_code is not None:
            payload["return_code"] = int(return_code)
        if evidence_links:
            payload["evidence_links"] = {
                str(key): value
                for key, value in evidence_links.items()
                if str(key).strip() and value not in (None, "")
            }
        if extra_fields:
            payload.update(
                {str(key): value for key, value in extra_fields.items() if str(key).strip()}
            )
        _apply_current_evidence(payload, transition_evidence)
        if reason:
            payload["last_error"] = reason
        timeline = [dict(item) for item in payload.get("timeline") or [] if isinstance(item, Mapping)]
        timeline.append(transition_evidence)
        payload["timeline"] = timeline
        if normalized_state in {"failed", "failed_before_manifest"}:
            payload["completed_at"] = transition_at
        for raw_row in payload.get("rows") or []:
            if not isinstance(raw_row, dict):
                continue
            row_state = str(raw_row.get("lifecycle_state") or raw_row.get("status") or "").casefold()
            if row_state not in _MUTABLE_ENROLLMENT_ROW_STATES:
                continue
            raw_row["status"] = normalized_state
            raw_row["lifecycle_state"] = normalized_state
            raw_row["last_transition_at"] = transition_at
            if normalized_state == "process_spawned" and not str(raw_row.get("started_at") or "").strip():
                raw_row["started_at"] = transition_at
            _apply_current_evidence(raw_row, transition_evidence)
            if reason:
                raw_row["last_error"] = reason
            row_timeline = [dict(item) for item in raw_row.get("timeline") or [] if isinstance(item, Mapping)]
            row_timeline.append(dict(transition_evidence))
            raw_row["timeline"] = row_timeline
        payload["lifecycle_counts"] = rerun_lifecycle_counts(
            [row for row in payload.get("rows") or [] if isinstance(row, Mapping)]
        )
        _write_payload(path, payload)
        return payload


def force_terminalize_rerun_enrollment(
    path: Path | None,
    state: str,
    *,
    reason_code: str,
    reason: str,
    pid: int | None = None,
    logs: str = "",
    return_code: int | None = None,
    evidence_links: Mapping[str, Any] | None = None,
    process_exit_verified: bool,
    duplicate_launch_blocked: bool,
) -> dict[str, Any] | None:
    """Direct fail-closed terminal write independent of the transition seam."""

    if path is None:
        return None
    normalized_state = str(state or "").strip().casefold()
    if normalized_state not in {"failed", "failed_before_manifest"}:
        raise ValueError("forced rerun terminal state must be failed or failed_before_manifest")
    if process_exit_verified is not True or duplicate_launch_blocked is not False:
        raise ValueError("forced rerun terminalization requires conclusive child-exit proof")
    with _RERUN_ENROLLMENT_TRANSITION_LOCK:
        payload = read_rerun_enrollment(path)
        if payload is None:
            return None
        current = _semantic_lifecycle_state(payload)
        if current in _TERMINAL_ENROLLMENT_STATES:
            return payload
        transition_at = _now_text()
        sequences: list[int] = []
        for item in payload.get("timeline") or []:
            if not isinstance(item, Mapping):
                continue
            try:
                sequences.append(int(item.get("sequence") or 0))
            except (TypeError, ValueError):
                continue
        try:
            sequences.append(int(payload.get("transition_sequence") or 0))
        except (TypeError, ValueError):
            pass
        transition_evidence = _state_evidence(
            normalized_state,
            at=transition_at,
            sequence=max(sequences, default=0) + 1,
            reason_code=reason_code,
            reason=reason,
        )
        payload.update(
            {
                "status": normalized_state,
                "lifecycle_state": normalized_state,
                "current_phase": normalized_state,
                "last_transition_at": transition_at,
                "completed_at": transition_at,
                "last_error": reason,
                "process_exit_verified": True,
                "duplicate_launch_blocked": False,
            }
        )
        if pid is not None:
            payload["pid"] = int(pid)
        if logs:
            payload["logs"] = str(logs)
        if return_code is not None:
            payload["return_code"] = int(return_code)
        if evidence_links:
            payload["evidence_links"] = {
                str(key): value
                for key, value in evidence_links.items()
                if str(key).strip() and value not in (None, "")
            }
        _apply_current_evidence(payload, transition_evidence)
        timeline = [dict(item) for item in payload.get("timeline") or [] if isinstance(item, Mapping)]
        timeline.append(transition_evidence)
        payload["timeline"] = timeline
        for raw_row in payload.get("rows") or []:
            if not isinstance(raw_row, dict):
                continue
            if _semantic_lifecycle_state(raw_row) in _TERMINAL_ENROLLMENT_STATES:
                continue
            raw_row.update(
                {
                    "status": normalized_state,
                    "lifecycle_state": normalized_state,
                    "last_transition_at": transition_at,
                    "completed_at": transition_at,
                    "last_error": reason,
                }
            )
            _apply_current_evidence(raw_row, transition_evidence)
            row_timeline = [
                dict(item)
                for item in raw_row.get("timeline") or []
                if isinstance(item, Mapping)
            ]
            row_timeline.append(dict(transition_evidence))
            raw_row["timeline"] = row_timeline
        payload["lifecycle_counts"] = rerun_lifecycle_counts(
            [row for row in payload.get("rows") or [] if isinstance(row, Mapping)]
        )
        _write_payload(path, payload)
        return payload


def record_rerun_spawn_transition_failure(
    path: Path | None,
    *,
    reason: str,
) -> dict[str, Any] | None:
    """Persist the fail-closed state when a spawned child cannot be durably enrolled."""

    return transition_rerun_enrollment(
        path,
        "failed_before_manifest",
        expected_states={"accepted", "process_spawned"},
        reason_code="rerun_process_spawn_transition_unpersisted",
        reason=reason,
        extra_fields={"process_exit_verified": True, "duplicate_launch_blocked": False},
    )


def record_rerun_spawn_transition_ambiguity(
    path: Path | None,
    *,
    reason: str,
    pid: int | None,
) -> dict[str, Any] | None:
    """Persist a nonterminal duplicate-blocking state when child exit is unverified."""

    return transition_rerun_enrollment(
        path,
        "spawn_transition_ambiguous",
        expected_states={"accepted", "process_spawned"},
        reason_code="rerun_process_spawn_transition_exit_unverified",
        reason=reason,
        pid=pid,
        automatic_next_action=(
            "Keep this enrollment nonterminal and reconcile the correlated child before any retry."
        ),
        operator_action_required=True,
        available_operator_action=(
            "Inspect ActiveJobs and logs, verify PID exit, then restart the backend reconciliation; "
            "do not launch duplicate work."
        ),
        extra_fields={
            "process_exit_verified": False,
            "duplicate_launch_blocked": True,
        },
    )


def finalize_rerun_enrollment_after_exit(metadata: Mapping[str, Any], return_code: int | None) -> None:
    path_text = str(metadata.get("enrollment_path") or "").strip()
    if not path_text:
        return
    path = Path(path_text)
    payload = read_rerun_enrollment(path)
    if payload is None:
        return
    current = str(payload.get("lifecycle_state") or payload.get("status") or "").strip().casefold()
    if current in _PRESERVED_EXIT_STATES:
        return
    manifest_path_text = str(metadata.get("manifest_path") or payload.get("manifest_path") or "").strip()
    manifest_payload: dict[str, Any] | None = None
    manifest_observed = bool(manifest_path_text and Path(manifest_path_text).exists())
    if manifest_observed:
        try:
            raw_manifest = read_json_file(Path(manifest_path_text), retries=1)
        except Exception:
            raw_manifest = None
        if isinstance(raw_manifest, Mapping):
            manifest_payload = dict(raw_manifest)
            if rerun_execution_manifest_has_durable_exit_state(manifest_payload):
                return
    evidence_links = {
        "active_jobs": str(metadata.get("active_jobs_path") or ""),
        "stdout_log": str(metadata.get("stdout_log") or ""),
        "stderr_log": str(metadata.get("stderr_log") or ""),
        "manifest": manifest_path_text,
    }
    if return_code == 0:
        state = "failed" if manifest_observed else "failed_before_manifest"
        transition_rerun_enrollment(
            path,
            state,
            expected_states={
                "accepted",
                "process_spawned",
                "spawn_transition_ambiguous",
                "starting",
                "processing",
            },
            reason_code="rerun_terminal_manifest_incomplete" if manifest_observed else "rerun_terminal_manifest_missing",
            reason=(
                "The rerun process exited before its execution manifest recorded a recoverable or terminal state."
                if manifest_observed
                else "The rerun process exited without recording a terminal execution manifest state."
            ),
            return_code=return_code,
            evidence_links=evidence_links,
            extra_fields={"process_exit_verified": True, "duplicate_launch_blocked": False},
        )
        return
    state = "failed" if manifest_observed else "failed_before_manifest"
    transition_rerun_enrollment(
        path,
        state,
        expected_states={
            "accepted",
            "process_spawned",
            "spawn_transition_ambiguous",
            "starting",
            "processing",
        },
        reason_code="rerun_process_exit_before_terminal_manifest" if manifest_observed else "rerun_process_exit_nonzero",
        reason=(
            f"The rerun process exited with code {return_code} before its execution manifest recorded a recoverable or terminal state."
            if manifest_observed
            else f"The rerun process exited with code {return_code} before a newer recoverable or terminal state was recorded."
        ),
        return_code=return_code,
        evidence_links=evidence_links,
        extra_fields={"process_exit_verified": True, "duplicate_launch_blocked": False},
    )


def rerun_startup_reconciliation_path(resolved: ResolvedPaths) -> Path:
    if resolved.state_root is not None:
        state_root = resolved.state_root
    elif resolved.local_base is not None:
        state_root = resolved.local_base / "State"
    else:
        state_root = resolved.workspace_root / "LocalBase" / "State"
    return state_root / "Rerun" / "StartupReconciliation" / "latest.json"


def read_rerun_startup_reconciliation(resolved: ResolvedPaths) -> dict[str, Any]:
    path = rerun_startup_reconciliation_path(resolved)
    try:
        payload = read_json_file(path, retries=1)
    except Exception:
        return {}
    return dict(payload) if isinstance(payload, Mapping) else {}


def rerun_manifest_declared_path_matches_actual(
    manifest: Mapping[str, Any],
    manifest_path: Path | str | None,
) -> bool:
    """Bind v2 execution evidence to the file path declared by its writer."""

    if str(manifest.get("schema_version") or "").strip() != "rerun_batch_manifest.v2":
        return True
    declared_path = _normalized_path_text(manifest.get("manifest_path"))
    actual_path = _normalized_path_text(manifest_path)
    return bool(declared_path and actual_path and declared_path == actual_path)


def rerun_manifest_path_matches_canonical_batch(
    resolved: ResolvedPaths,
    manifest: Mapping[str, Any],
    manifest_path: Path | str | None,
) -> bool:
    """Require v2 manifests to remain at the backend-owned batch path."""

    if str(manifest.get("schema_version") or "").strip() != "rerun_batch_manifest.v2":
        return True
    batch_id = str(manifest.get("batch_id") or "").strip()
    actual_path = _normalized_path_text(manifest_path)
    if not batch_id or not actual_path:
        return False
    expected_path = _normalized_path_text(rerun_execution_manifest_root(resolved) / f"{batch_id}.json")
    return actual_path == expected_path


def rerun_manifest_matches_enrollment(
    manifest: Mapping[str, Any],
    enrollment: Mapping[str, Any],
    *,
    enrollment_path: Path | str | None = None,
    manifest_path: Path | str | None = None,
) -> bool:
    """Require every durable enrollment correlation value in an execution manifest."""

    if manifest_path is not None and not rerun_manifest_declared_path_matches_actual(manifest, manifest_path):
        return False
    expected_manifest_path = _normalized_path_text(enrollment.get("manifest_path"))
    actual_manifest_path = _normalized_path_text(manifest_path)
    if expected_manifest_path and actual_manifest_path != expected_manifest_path:
        return False
    for key in ("batch_id", "launch_id", "command_id"):
        expected = str(enrollment.get(key) or "").strip()
        actual = str(manifest.get(key) or "").strip()
        if expected and actual != expected:
            return False
    expected_path = _normalized_path_text(enrollment_path or enrollment.get("enrollment_path"))
    actual_path = _normalized_path_text(manifest.get("enrollment_path"))
    if expected_path and actual_path != expected_path:
        return False
    return bool(str(enrollment.get("batch_id") or "").strip())


def reconcile_local_rerun_enrollments(
    resolved: ResolvedPaths,
    *,
    pid_is_alive: Callable[[int], bool | None] | None = None,
    limit: int = 1000,
) -> dict[str, Any]:
    """Reconcile nonterminal local reruns once at backend startup; never replay media."""

    checker = pid_is_alive or (lambda pid: active_job_pid_is_alive(pid, psutil))
    summary: dict[str, Any] = {
        "schema_version": "desktop_rerun_startup_reconciliation.v1",
        "started_at": _now_text(),
        "checked_count": 0,
        "alive_count": 0,
        "durable_manifest_count": 0,
        "terminalized_count": 0,
        "ambiguous_count": 0,
        "replayed_count": 0,
        "items": [],
    }
    candidate_scan: dict[str, Any] = {}
    with _RERUN_ENROLLMENT_TRANSITION_LOCK:
        candidates = rerun_enrollment_candidates(resolved, limit=limit, scan_health=candidate_scan)
        summary["candidate_scan"] = candidate_scan
        for enrollment_path, enrollment in candidates:
            enrollment_state = _semantic_lifecycle_state(enrollment)
            if enrollment_state in _TERMINAL_ENROLLMENT_STATES:
                continue
            summary["checked_count"] += 1
            manifest_text = str(enrollment.get("manifest_path") or "").strip()
            manifest_path = Path(manifest_text) if manifest_text else None
            manifest: dict[str, Any] | None = None
            if manifest_path is not None and manifest_path.is_file():
                try:
                    raw_manifest = read_json_file(manifest_path, retries=1)
                except Exception:
                    raw_manifest = None
                if isinstance(raw_manifest, Mapping) and rerun_manifest_matches_enrollment(
                    raw_manifest,
                    enrollment,
                    enrollment_path=enrollment_path,
                    manifest_path=manifest_path,
                ):
                    manifest = dict(raw_manifest)
            if manifest is not None and rerun_execution_manifest_has_durable_exit_state(manifest):
                summary["durable_manifest_count"] += 1
                summary["items"].append(
                    {
                        "batch_id": str(enrollment.get("batch_id") or ""),
                        "outcome": "durable_manifest_preserved",
                        "manifest_path": str(manifest_path or ""),
                    }
                )
                continue

            active_job_path, active_job = _exact_active_job_payload(resolved, enrollment)
            active_job = dict(active_job or {})
            active_status = str(active_job.get("status") or "").strip().casefold()
            try:
                active_pid = int(active_job.get("pid") or enrollment.get("pid") or 0)
            except (TypeError, ValueError):
                active_pid = 0
            if active_pid > 0 and active_status not in _TERMINAL_ACTIVE_JOB_STATUSES:
                alive = checker(active_pid)
                if alive is True:
                    summary["alive_count"] += 1
                    summary["items"].append(
                        {
                            "batch_id": str(enrollment.get("batch_id") or ""),
                            "outcome": "child_alive_preserved",
                            "active_jobs_path": str(active_job_path or ""),
                            "pid": active_pid,
                        }
                    )
                    continue
                if alive is None:
                    summary["ambiguous_count"] += 1
                    summary["items"].append(
                        {
                            "batch_id": str(enrollment.get("batch_id") or ""),
                            "outcome": "child_identity_ambiguous_preserved",
                            "active_jobs_path": str(active_job_path or ""),
                            "pid": active_pid,
                        }
                    )
                    continue
                exit_reason = (
                    f"correlated ActiveJobs status {active_status or 'unknown'} PID {active_pid} "
                    "is no longer running"
                )
            elif active_status in _TERMINAL_ACTIVE_JOB_STATUSES:
                exit_reason = f"correlated ActiveJobs status is {active_status}"
            elif not active_job and active_pid > 0:
                alive = checker(active_pid)
                if alive is True or alive is None:
                    preserved = "child_alive_preserved" if alive is True else "child_identity_ambiguous_preserved"
                    summary["alive_count" if alive is True else "ambiguous_count"] += 1
                    summary["items"].append(
                        {
                            "batch_id": str(enrollment.get("batch_id") or ""),
                            "outcome": preserved,
                            "pid": active_pid,
                        }
                    )
                    continue
                exit_reason = f"enrollment PID {active_pid} is no longer running"
            elif not active_job and active_pid <= 0:
                record_rerun_spawn_transition_ambiguity(
                    enrollment_path,
                    reason=(
                        "Backend startup reconciliation found neither a correlated ActiveJobs record nor a PID. "
                        "That absence does not prove that no child was launched, so duplicate work remains blocked."
                    ),
                    pid=None,
                )
                summary["ambiguous_count"] += 1
                summary["items"].append(
                    {
                        "batch_id": str(enrollment.get("batch_id") or ""),
                        "outcome": "child_identity_ambiguous_preserved",
                        "pid": 0,
                    }
                )
                continue
            else:
                summary["ambiguous_count"] += 1
                summary["items"].append(
                    {
                        "batch_id": str(enrollment.get("batch_id") or ""),
                        "outcome": "active_jobs_state_ambiguous_preserved",
                        "active_jobs_path": str(active_job_path or ""),
                        "active_jobs_status": active_status,
                    }
                )
                continue

            manifest_observed = manifest_path is not None and manifest_path.is_file()
            terminal_state = "failed" if manifest_observed else "failed_before_manifest"
            reason_code = (
                "rerun_startup_child_exit_with_incomplete_manifest"
                if manifest_observed
                else "rerun_startup_child_exit_before_manifest"
            )
            reason = (
                "Backend startup reconciliation proved the prior CSV rerun child exited "
                f"without durable execution evidence: {exit_reason}. No media was replayed."
            )
            evidence_links = {
                "active_jobs": str(active_job_path or ""),
                "manifest": str(manifest_path or ""),
                "stdout_log": str(active_job.get("stdout_log") or ""),
                "stderr_log": str(active_job.get("stderr_log") or ""),
            }
            terminal = force_terminalize_rerun_enrollment(
                enrollment_path,
                terminal_state,
                reason_code=reason_code,
                reason=reason,
                pid=active_pid or None,
                return_code=active_job.get("return_code") if isinstance(active_job.get("return_code"), int) else None,
                evidence_links=evidence_links,
                process_exit_verified=True,
                duplicate_launch_blocked=False,
            )
            if terminal is not None and _semantic_lifecycle_state(terminal) == terminal_state:
                summary["terminalized_count"] += 1
                summary["items"].append(
                    {
                        "batch_id": str(enrollment.get("batch_id") or ""),
                        "outcome": terminal_state,
                        "active_jobs_path": str(active_job_path or ""),
                        "manifest_path": str(manifest_path or ""),
                    }
                )
            else:
                summary["ambiguous_count"] += 1
    summary_path = rerun_startup_reconciliation_path(resolved)
    summary["completed_at"] = _now_text()
    summary["summary_path"] = str(summary_path)
    summary["persisted"] = True
    try:
        _write_payload(summary_path, summary)
    except Exception as exc:
        summary["persisted"] = False
        summary["persistence_error"] = str(exc)
    return summary


def rerun_lifecycle_counts(rows: Sequence[Mapping[str, Any]]) -> dict[str, int]:
    states = [_semantic_lifecycle_state(row) for row in rows]
    counts = Counter(states)
    executable_states = {
        "requested",
        "accepted",
        "manifest_created",
        "pending",
        "queued",
        "planned",
        "ready",
        "retryable",
        "pending_claim",
    }
    blocked_states = {
        "blocked",
        "invalid",
        "missing",
        "source_missing",
        "source_access_failed",
        "source_identity_changed",
        "spawn_transition_ambiguous",
    }
    waiting_states = {"waiting", "waiting_for_source", "retry_scheduled"}
    retrying_states = {"retrying", "retry_scheduled"}
    staged_states = {"staged"}
    active_states = {
        "process_spawned",
        "starting",
        "staging",
        "processing",
        "running",
        "active",
        "claimed",
        "destination_policy",
        "destination_policy_applying",
        "worker_completed_pending_reduction",
        "reduced_ready_for_destination_policy",
        "spawn_transition_ambiguous",
    }
    completed_states = {
        "complete",
        "completed",
        "completed_with_failures",
        "completed_with_failed_rows",
        "done",
        "succeeded",
        "success",
        "published_replace_final",
        "published_non_overlap",
        "returned",
        "replaced",
    }
    failed_states = {
        "failed",
        "failed_before_manifest",
        "retry_exhausted",
        "error",
        "errored",
        "destination_policy_failed",
        "worker_failed_pending_reduction",
    }
    review_states = {
        "review",
        "review_workspace",
        "awaiting_review",
        "worker_review_pending_reduction",
        "warning",
        "warn",
        "warnings",
    }
    pending_publish_states = {"pending_publish", "parked"}
    terminal_states = {
        *completed_states,
        *failed_states,
        *review_states,
        *pending_publish_states,
        "cancelled",
        "skipped",
        "skip",
        "disabled",
    }
    return {
        "total": len(states),
        "executable": sum(counts[state] for state in executable_states),
        "blocked": sum(counts[state] for state in blocked_states),
        "waiting": sum(counts[state] for state in waiting_states),
        "retrying": sum(counts[state] for state in retrying_states),
        "staged": sum(counts[state] for state in staged_states),
        "active": sum(counts[state] for state in active_states),
        "completed": sum(counts[state] for state in completed_states),
        "failed": sum(counts[state] for state in failed_states),
        "review": sum(counts[state] for state in review_states),
        "pending_publish": sum(counts[state] for state in pending_publish_states),
        "terminal": sum(counts[state] for state in terminal_states),
    }


__all__ = [
    "RERUN_ENROLLMENT_SCHEMA_VERSION",
    "RERUN_QUEUE_SOURCE",
    "RerunCorrelation",
    "create_rerun_enrollment",
    "find_rerun_recovery_enrollment",
    "finalize_rerun_enrollment_after_exit",
    "force_terminalize_rerun_enrollment",
    "new_rerun_correlation",
    "read_rerun_enrollment",
    "record_rerun_spawn_transition_failure",
    "record_rerun_spawn_transition_ambiguity",
    "rerun_enrollment_candidates",
    "rerun_enrollment_root",
    "rerun_correlation_evidence",
    "rerun_execution_manifest_has_durable_exit_state",
    "rerun_execution_manifest_root",
    "rerun_lifecycle_counts",
    "rerun_manifest_declared_path_matches_actual",
    "rerun_manifest_path_matches_canonical_batch",
    "rerun_recovery_enrollment_guard",
    "reconcile_local_rerun_enrollments",
    "read_rerun_startup_reconciliation",
    "rerun_startup_reconciliation_path",
    "transition_rerun_enrollment",
]
