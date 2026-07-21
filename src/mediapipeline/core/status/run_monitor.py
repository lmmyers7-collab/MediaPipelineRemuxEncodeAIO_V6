"""Single current-work freshness policy and WebView-facing Run Monitor projection."""

from __future__ import annotations

import ntpath
from collections.abc import Callable, Mapping, Sequence
from datetime import datetime, timezone
from pathlib import Path, PureWindowsPath
from typing import Any, Literal

from pydantic import ValidationError

from mediapipeline.contracts.run_monitor import (
    RUN_MONITOR_STAGE_IDS,
    RUN_MONITOR_PROJECTION_SCHEMA_VERSION,
    TERMINAL_RUN_LIFECYCLE_STATES,
    ProgressEvidence,
    RouteEvidence,
    RunMonitorItem,
    RunMonitorRecord,
)
from mediapipeline.core.kernel.contracts import PLANNED_DISPLAY_NAME_SOURCE, QueueAcceptedRunRow
from mediapipeline.core.status.run_monitor_storage import RunMonitorStore
from mediapipeline.core.status.active_jobs import active_job_detail_rows


BackendActivityState = Literal["confirmed_active", "confirmed_idle", "unknown", "unavailable"]
_ACTIVE_RUN_STATES = frozenset({"starting", "scanning", "running", "paused", "stop_requested", "stopping"})
_TERMINAL_ITEM_STATES = frozenset({"completed", "failed", "skipped", "blocked", "review", "parked", "stopped"})
_ACTIVE_JOB_STATES = frozenset({"launching", "active"})
_TERMINAL_ACTIVE_JOB_STATES = frozenset(
    {
        "completed",
        "failed",
        "completed_immediate",
        "failed_immediate",
        "kill_degraded",
        "killed",
        "orphaned",
    }
)


def backend_activity_state_for_run(
    active_jobs_path: Path | None,
    run_id: str,
    *,
    pid_alive: Callable[[int], bool | None] | None = None,
) -> BackendActivityState:
    """Resolve process activity only from an exact ActiveJobs run identity."""

    normalized_run_id = str(run_id or "").strip()
    if active_jobs_path is None or not normalized_run_id:
        return "unknown"
    rows = active_job_detail_rows(active_jobs_path, max_items=1000)
    if any(str(row.get("source") or "") in {"invalid", "unreadable"} for row in rows):
        return "unavailable"
    matching: list[Mapping[str, Any]] = []
    for row in rows:
        metadata = row.get("metadata")
        if not isinstance(metadata, Mapping):
            continue
        if str(metadata.get("run_id") or "").strip() != normalized_run_id:
            continue
        if str(row.get("job_kind") or "").strip() != "pipeline":
            continue
        if str(row.get("mode") or "").strip() != "once":
            continue
        matching.append(row)
    active = [row for row in matching if str(row.get("status") or "").strip() in _ACTIVE_JOB_STATES]
    if active:
        if pid_alive is None:
            return "confirmed_active"
        liveness: list[bool | None] = []
        for row in active:
            try:
                pid = int(row.get("pid") or 0)
            except (TypeError, ValueError):
                pid = 0
            if pid <= 0:
                return "unavailable"
            try:
                liveness.append(pid_alive(pid))
            except Exception:
                liveness.append(None)
        if any(value is True for value in liveness):
            return "confirmed_active"
        # An ActiveJobs row that no longer has a live process is contradictory,
        # not proof of idle. Suppress current claims until reconciliation.
        return "unavailable"
    if matching and all(
        str(row.get("status") or "").strip() in _TERMINAL_ACTIVE_JOB_STATES for row in matching
    ):
        return "confirmed_idle"
    return "unknown"


def _parse_timestamp(value: str) -> datetime:
    text = str(value or "").strip()
    if text.endswith("Z"):
        text = f"{text[:-1]}+00:00"
    parsed = datetime.fromisoformat(text)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _utc_now(now: datetime | None) -> datetime:
    value = now or datetime.now(timezone.utc)
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _iso_utc(now: datetime | None = None) -> str:
    return _utc_now(now).isoformat().replace("+00:00", "Z")


def _starting_seed_signature(record: RunMonitorRecord) -> tuple[Any, ...]:
    return (
        record.run.command_id,
        record.run.accepted_queue.schema_version,
        record.run.accepted_queue.fingerprint,
        record.run.accepted_queue.accepted_count,
        tuple(
            (
                item.job_id,
                item.source_identity.value,
                item.source_identity.algorithm,
                item.source_path.casefold(),
                item.display_name,
                item.display_name_evidence.source if item.display_name_evidence else "legacy_run_monitor",
                item.display_name_evidence.provenance if item.display_name_evidence else "unknown",
                item.parent_context,
                item.position,
                item.total,
                item.routes.planned.state,
                item.routes.planned.route,
                item.routes.planned.reason,
                item.routes.planned.reason_code,
                item.output.intended_final_path.casefold(),
            )
            for item in record.items
        ),
    )


def seed_starting_run_monitor(
    state_root: Path,
    *,
    run_id: str,
    command_id: str,
    accepted_queue_fingerprint: str,
    accepted_rows: Sequence[QueueAcceptedRunRow],
    now: datetime | None = None,
) -> RunMonitorRecord:
    """Durably accept an exact Backend Queue workload before process spawn.

    A recovery replay may adopt the same still-starting record. Any different
    command, fingerprint, membership, label, or planned-route evidence is
    rejected rather than overwriting the accepted workload.
    """

    normalized_run_id = str(run_id or "").strip()
    normalized_command_id = str(command_id or "").strip()
    normalized_fingerprint = str(accepted_queue_fingerprint or "").strip()
    if not normalized_run_id or not normalized_command_id or not normalized_fingerprint:
        raise ValueError("run_id, command_id, and accepted Queue fingerprint are required")
    rows = list(accepted_rows)
    if not rows:
        raise ValueError("accepted Run Once workload must contain at least one item")

    timestamp = _iso_utc(now)
    total = len(rows)

    def evidence(source: str, provenance: str = "backend_confirmed") -> dict[str, Any]:
        return {"source": source, "provenance": provenance, "recorded_at": timestamp}

    def route_evidence(
        state: str,
        *,
        route: str = "",
        reason: str = "",
        reason_code: str = "",
        source: str = "pipeline_engine",
        provenance: str = "backend_confirmed",
    ) -> dict[str, Any]:
        return {
            "state": state,
            "route": route,
            "reason": reason,
            "reason_code": reason_code,
            "evidence": evidence(source, provenance),
        }

    items: list[dict[str, Any]] = []
    for expected_position, row in enumerate(rows, start=1):
        if row.run_queue_index != expected_position or row.run_queue_total != total:
            raise ValueError("accepted rows must preserve contiguous run-wide positions and totals")
        stages: list[dict[str, Any]] = []
        for stage_id in RUN_MONITOR_STAGE_IDS:
            completed = stage_id == "accepted"
            stages.append(
                {
                    "stage_id": stage_id,
                    "state": "completed" if completed else "not_started",
                    "started_at": timestamp if completed else "",
                    "updated_at": timestamp if completed else "",
                    "completed_at": timestamp if completed else "",
                    "detail": (
                        "Accepted into the fingerprinted Backend Queue Run Once workload."
                        if completed
                        else (
                            "Accepted workload is durable; active source discovery has not started."
                            if stage_id == "source_discovery"
                            else ""
                        )
                    ),
                    "reason_code": "",
                    "progress": {"kind": "none", "numerator": None, "denominator": None},
                    "evidence": evidence(
                        "backend_launch_acceptance" if completed or stage_id == "source_discovery" else "pipeline_engine",
                        "queue_plan" if completed or stage_id == "source_discovery" else "backend_confirmed",
                    ),
                }
            )
        planned_route = str(row.route or "").strip()
        planned_state = "available" if planned_route else "unknown"
        planned_reason = str(row.route_reason or "") if planned_route else ""
        planned_reason_code = str(row.route_reason_code or "") if planned_route else ""
        display_name = str(row.planned_display_name or "").strip()
        if not row.has_verified_planned_display_name:
            raise ValueError(
                "accepted row requires verified planned display-name evidence; "
                "refresh Queue with the current backend before launching"
            )
        parent_context = str(row.parent_context or "").strip() or str(Path(row.source_path).parent)
        items.append(
            {
                "job_id": f"{normalized_run_id}-item-{expected_position:08d}",
                "source_identity": {
                    "value": row.source_identity,
                    "algorithm": row.source_identity_algorithm,
                },
                "source_path": row.source_path,
                "display_name": display_name,
                "display_name_evidence": evidence(PLANNED_DISPLAY_NAME_SOURCE, "queue_plan"),
                "parent_context": parent_context,
                "position": expected_position,
                "total": total,
                "lifecycle_state": "queued",
                "lifecycle_evidence": evidence("backend_launch_acceptance", "queue_plan"),
                "updated_at": timestamp,
                "routes": {
                    "planned": route_evidence(
                        planned_state,
                        route=planned_route,
                        reason=planned_reason,
                        reason_code=planned_reason_code,
                        source="queue_plan_acceptance",
                        provenance="queue_plan",
                    ),
                    "executed": route_evidence("awaiting_evidence"),
                    "final": route_evidence("awaiting_evidence"),
                },
                "stages": stages,
                "audio": {
                    "state": "awaiting_evidence",
                    "policy_final": False,
                    "tracks": [],
                    "evidence": evidence("audio_policy"),
                },
                "subtitles": {
                    "state": "awaiting_evidence",
                    "policy_final": False,
                    "tracks": [],
                    "evidence": evidence("subtitle_policy"),
                },
                "output": {
                    "state": "awaiting_evidence",
                    "scratch_path": "",
                    "working_output_path": "",
                    "published_path": "",
                    "parked_path": "",
                    "intended_final_path": str(row.intended_final_path or ""),
                    "size_bytes": None,
                    "verification_state": "not_started",
                    "sidecars": [],
                    "evidence": evidence("output_state"),
                },
                "terminal_references": [],
                "failure": {
                    "state": "none",
                    "reason_code": "",
                    "reason": "",
                    "retryable": None,
                    "reference": "",
                    "evidence": evidence("failure_state"),
                },
                "recovery": {
                    "owner": "pipeline",
                    "next_action": "Await backend-confirmed pipeline evidence.",
                    "retryable": None,
                    "evidence": evidence("recovery_state"),
                },
            }
        )

    candidate = RunMonitorRecord.model_validate(
        {
            "schema_version": "pipeline_run_monitor.v1",
            "write_sequence": 1,
            "run": {
                "run_id": normalized_run_id,
                "command_id": normalized_command_id,
                "mode": "once",
                "scope": "backend_queue",
                "accepted_queue": {
                    "schema_version": "queue_plan_fingerprint.v1",
                    "fingerprint": normalized_fingerprint,
                    "accepted_count": total,
                },
                "lifecycle_state": "starting",
                "started_at": timestamp,
                "updated_at": timestamp,
                "ended_at": "",
                "stop_after_current": {
                    "state": "not_requested",
                    "requested_at": "",
                    "evidence": evidence("stop_after_current_state"),
                },
                "outcome": {
                    "state": "pending",
                    "reason_code": "",
                    "reason": "",
                    "retryable": None,
                    "owner": "pipeline",
                    "next_action": "Monitor backend-confirmed source discovery.",
                    "evidence": evidence("backend_launch_acceptance"),
                },
                "counts": {
                    "accepted": total,
                    "queued": total,
                    "active": 0,
                    "completed": 0,
                    "failed": 0,
                    "skipped": 0,
                    "blocked": 0,
                    "review": 0,
                    "parked": 0,
                    "stopped": 0,
                },
                "evidence": evidence("backend_launch_acceptance", "queue_plan"),
            },
            "items": items,
            "current_workers": [],
        }
    )
    store = RunMonitorStore(Path(state_root))
    existing = store.read(normalized_run_id)
    if existing is not None:
        if (
            existing.run.lifecycle_state != "starting"
            or _starting_seed_signature(existing) != _starting_seed_signature(candidate)
        ):
            raise ValueError("run_id already identifies a different or non-starting exact starting monitor")
        store.repair_latest_pointer(existing)
        return existing
    return store.write(candidate)


def terminalize_launch_failed_run(
    state_root: Path,
    run_id: str,
    *,
    reason: str,
    now: datetime | None = None,
) -> bool:
    """Record a failed launch only while Python still owns the pre-spawn seed."""

    store = RunMonitorStore(Path(state_root))
    record = store.read(run_id)
    if record is None or record.run.lifecycle_state != "starting":
        return False
    timestamp = _iso_utc(now)
    payload = record.model_dump(mode="json")
    detail = str(reason or "Pipeline process launch failed before runtime evidence was available.")
    evidence = {
        "source": "pipeline_launch",
        "provenance": "terminal",
        "recorded_at": timestamp,
    }
    for item in payload["items"]:
        item["lifecycle_state"] = "failed"
        item["lifecycle_evidence"] = dict(evidence)
        item["updated_at"] = timestamp
        final_stage = next(stage for stage in item["stages"] if stage["stage_id"] == "final_evidence")
        final_stage.update(
            {
                "state": "failed",
                "updated_at": timestamp,
                "completed_at": timestamp,
                "detail": detail,
                "reason_code": "PIPELINE_LAUNCH_FAILED",
                "progress": {"kind": "none", "numerator": None, "denominator": None},
                "evidence": dict(evidence),
            }
        )
        if item["routes"]["final"]["state"] == "awaiting_evidence":
            item["routes"]["final"].update(
                {
                    "state": "unknown",
                    "route": "",
                    "reason": detail,
                    "reason_code": "PIPELINE_LAUNCH_FAILED",
                    "evidence": dict(evidence),
                }
            )
        item["audio"].update({"state": "unknown", "evidence": dict(evidence)})
        item["subtitles"].update({"state": "unknown", "evidence": dict(evidence)})
        item["output"].update(
            {
                "state": "unknown",
                "verification_state": "unknown",
                "evidence": dict(evidence),
            }
        )
        item["failure"] = {
            "state": "recoverable",
            "reason_code": "PIPELINE_LAUNCH_FAILED",
            "reason": detail,
            "retryable": True,
            "reference": "",
            "evidence": dict(evidence),
        }
        item["recovery"] = {
            "owner": "backend_process",
            "next_action": "Review command history and retry Run Once after resolving the launch failure.",
            "retryable": True,
            "evidence": dict(evidence),
        }
    counts = payload["run"]["counts"]
    counts.update({"queued": 0, "active": 0, "failed": len(payload["items"])})
    payload["write_sequence"] = int(payload["write_sequence"]) + 1
    payload["current_workers"] = []
    payload["run"].update(
        {
            "lifecycle_state": "failed",
            "updated_at": timestamp,
            "ended_at": timestamp,
            "outcome": {
                "state": "failed",
                "reason_code": "PIPELINE_LAUNCH_FAILED",
                "reason": detail,
                "retryable": True,
                "owner": "backend_process",
                "next_action": "Review command history and retry Run Once after resolving the launch failure.",
                "evidence": dict(evidence),
            },
            "evidence": dict(evidence),
        }
    )
    store.write(payload)
    return True


def terminalize_force_stopped_run(
    state_root: Path,
    run_id: str,
    *,
    now: datetime | None = None,
) -> bool:
    """Persist exact post-kill evidence after backend process termination.

    PowerShell remains the sole runtime writer. The backend uses this narrow
    takeover only after its force-stop service has terminated the process tree,
    so a killed run cannot linger as apparently active or be reconstructed from
    stale legacy progress.
    """

    store = RunMonitorStore(Path(state_root))
    record = store.read(run_id)
    if record is None or record.run.lifecycle_state in TERMINAL_RUN_LIFECYCLE_STATES:
        return False

    timestamp = _iso_utc(now)
    payload = record.model_dump(mode="json")
    evidence = {
        "source": "force_stop_control",
        "provenance": "terminal",
        "recorded_at": timestamp,
    }
    reason = "The operator force-stopped the backend-owned process tree."
    reason_code = "force_stopped_by_operator"
    for item in payload["items"]:
        if item["lifecycle_state"] in _TERMINAL_ITEM_STATES:
            continue
        item["lifecycle_state"] = "stopped"
        item["lifecycle_evidence"] = dict(evidence)
        item["updated_at"] = timestamp
        for stage in item["stages"]:
            if stage["state"] == "active":
                stage.update(
                    {
                        "state": "failed",
                        "updated_at": timestamp,
                        "completed_at": timestamp,
                        "detail": reason,
                        "reason_code": reason_code,
                        "progress": {"kind": "none", "numerator": None, "denominator": None},
                        "evidence": dict(evidence),
                    }
                )
        final_stage = next(stage for stage in item["stages"] if stage["stage_id"] == "final_evidence")
        final_stage.update(
            {
                "state": "failed",
                "updated_at": timestamp,
                "completed_at": timestamp,
                "detail": reason,
                "reason_code": reason_code,
                "progress": {"kind": "none", "numerator": None, "denominator": None},
                "evidence": dict(evidence),
            }
        )
        if item["routes"]["final"]["state"] == "awaiting_evidence":
            item["routes"]["final"].update(
                {
                    "state": "unknown",
                    "route": "",
                    "reason": reason,
                    "reason_code": reason_code,
                    "evidence": dict(evidence),
                }
            )
        for collection_name in ("audio", "subtitles"):
            collection = item[collection_name]
            for track in collection["tracks"]:
                if track["state"] == "active":
                    track["state"] = "failed"
                    track["updated_at"] = timestamp
                    track["completed_at"] = timestamp
                    track["result"] = reason
                    track["progress"] = {"kind": "none", "numerator": None, "denominator": None}
                    track["evidence"] = dict(evidence)
                elif track["state"] == "awaiting_evidence":
                    track["state"] = "unknown"
                    track["updated_at"] = timestamp
                    track["completed_at"] = ""
                    track["result"] = "Force stop occurred before terminal per-track evidence."
                    track["evidence"] = dict(evidence)
            if collection["state"] == "active":
                collection["state"] = "failed"
                collection["evidence"] = dict(evidence)
            elif collection["state"] == "awaiting_evidence":
                collection["state"] = "unknown"
                collection["evidence"] = dict(evidence)
        output_state_changed = False
        if item["output"]["state"] == "active":
            item["output"]["state"] = "failed"
            item["output"]["verification_state"] = "failed"
            output_state_changed = True
        elif item["output"]["state"] == "awaiting_evidence":
            item["output"]["state"] = "unknown"
            item["output"]["verification_state"] = "unknown"
            output_state_changed = True
        if output_state_changed:
            item["output"]["evidence"] = dict(evidence)
        item["failure"] = {
            "state": "force_stopped",
            "reason_code": reason_code,
            "reason": reason,
            "retryable": True,
            "reference": "",
            "evidence": dict(evidence),
        }
        item["recovery"] = {
            "owner": "operator",
            "next_action": "Review Reports and partial-output evidence before starting a new run.",
            "retryable": True,
            "evidence": dict(evidence),
        }

    counts = payload["run"]["counts"]
    for state in ("queued", "active", "completed", "failed", "skipped", "blocked", "review", "parked", "stopped"):
        counts[state] = sum(1 for item in payload["items"] if item["lifecycle_state"] == state)
    payload["write_sequence"] = int(payload["write_sequence"]) + 1
    payload["current_workers"] = []
    payload["run"].update(
        {
            "lifecycle_state": "force_stopped",
            "updated_at": timestamp,
            "ended_at": timestamp,
            "outcome": {
                "state": "force_stopped",
                "reason_code": reason_code,
                "reason": reason,
                "retryable": True,
                "owner": "operator",
                "next_action": "Review Reports and partial-output evidence before starting a new run.",
                "evidence": dict(evidence),
            },
            "evidence": dict(evidence),
        }
    )
    if payload["run"]["stop_after_current"]["state"] != "not_requested":
        payload["run"]["stop_after_current"]["state"] = "completed"
        payload["run"]["stop_after_current"]["evidence"] = dict(evidence)
    store.write(payload)
    return True


def _project_progress(progress: ProgressEvidence) -> dict[str, Any] | None:
    if progress.kind == "none":
        return None
    payload: dict[str, Any] = {"kind": progress.kind}
    if progress.kind == "determinate":
        payload.update(
            {
                "numerator": progress.numerator,
                "denominator": progress.denominator,
                "percent": round(float(progress.fraction or 0.0) * 100.0, 3),
            }
        )
    return payload


def _project_route(route: RouteEvidence, label: str, reason_label: str) -> dict[str, Any]:
    return {
        "label": label,
        "reason_label": reason_label,
        "state": route.state,
        "value": route.route,
        "reason": route.reason,
        "reason_code": route.reason_code,
        "evidence": route.evidence.model_dump(mode="json"),
    }


def _active_stage(item: RunMonitorItem) -> dict[str, Any] | None:
    active = next((stage for stage in item.stages if stage.state == "active"), None)
    if active is None:
        return None
    return {
        "stage_id": active.stage_id,
        "state": active.state,
        "detail": active.detail,
        "reason_code": active.reason_code,
        "started_at": active.started_at,
        "updated_at": active.updated_at,
        "progress": _project_progress(active.progress),
        "evidence": active.evidence.model_dump(mode="json"),
    }


def _terminal_path_leaf(value: str) -> str:
    normalized = str(value or "").strip().rstrip("\\/")
    if not normalized:
        return ""
    leaf = PureWindowsPath(normalized).name.strip()
    return "" if leaf in {"", ".", ".."} else leaf


def _normalized_terminal_path(value: str) -> str:
    normalized = str(value or "").strip().replace("/", "\\")
    if not normalized:
        return ""
    return ntpath.normcase(ntpath.normpath(normalized))


def _project_display_name(item: RunMonitorItem, *, allow_terminal: bool) -> tuple[str, str, dict[str, Any]]:
    if (
        item.display_name_evidence is not None
        and item.display_name_evidence.source == PLANNED_DISPLAY_NAME_SOURCE
        and item.display_name_evidence.provenance == "queue_plan"
    ):
        return (
            item.display_name,
            "verified_queue_plan",
            item.display_name_evidence.model_dump(mode="json"),
        )

    legacy_evidence = (
        item.display_name_evidence.model_dump(mode="json")
        if item.display_name_evidence is not None
        else {
            "source": "legacy_run_monitor",
            "provenance": "unknown",
            "recorded_at": item.updated_at,
        }
    )
    if not allow_terminal:
        return item.display_name, "legacy_accepted", legacy_evidence
    output = item.output
    if item.lifecycle_state == "completed" and output.state == "published" and output.evidence.provenance == "terminal":
        published_path = _normalized_terminal_path(output.published_path)
        completed_reference = next(
            (
                reference
                for reference in item.terminal_references
                if reference.kind == "completed"
                and reference.evidence.provenance == "terminal"
                and _normalized_terminal_path(reference.path or reference.reference) == published_path
            ),
            None,
        )
        if published_path and completed_reference is not None:
            display_name = _terminal_path_leaf(completed_reference.path or completed_reference.reference)
            if display_name:
                return (
                    display_name,
                    "terminal_output",
                    completed_reference.evidence.model_dump(mode="json"),
                )

    if item.lifecycle_state == "parked" and output.state == "parked" and output.evidence.provenance == "terminal":
        has_pending_reference = any(
            reference.kind in {"pending_publish", "manifest"} and reference.evidence.provenance == "terminal"
            for reference in item.terminal_references
        )
        display_name = _terminal_path_leaf(output.intended_final_path) if has_pending_reference else ""
        if display_name:
            return display_name, "terminal_output", output.evidence.model_dump(mode="json")

    return item.display_name, "legacy_accepted", legacy_evidence


def _project_item(
    item: RunMonitorItem,
    *,
    suppress_current: bool,
    suppress_terminal: bool = False,
    suppression_recorded_at: str = "",
) -> dict[str, Any]:
    active_stage = _active_stage(item)
    executed_route = _project_route(item.routes.executed, "Executed route", "Executed reason")
    final_route = _project_route(item.routes.final, "Final route", "Final reason")
    display_name, display_name_basis, display_name_evidence = _project_display_name(
        item,
        allow_terminal=not suppress_terminal,
    )

    payload: dict[str, Any] = {
        "job_id": item.job_id,
        "source_identity": item.source_identity.model_dump(mode="json"),
        "source_path": item.source_path,
        "display_name": display_name,
        "accepted_display_name": item.display_name,
        "display_name_basis": display_name_basis,
        "display_name_evidence": display_name_evidence,
        "parent_context": item.parent_context,
        "position": item.position,
        "total": item.total,
        "lifecycle_state": item.lifecycle_state,
        "lifecycle_evidence": item.lifecycle_evidence.model_dump(mode="json"),
        "updated_at": item.updated_at,
        "planned_route": _project_route(item.routes.planned, "Planned route", "Planned reason"),
        "executed_route": executed_route,
        "final_route": final_route,
        "current_stage": active_stage,
        "current_progress": active_stage.get("progress") if active_stage else None,
        "stages": [stage.model_dump(mode="json") for stage in item.stages],
        "audio": item.audio.model_dump(mode="json"),
        "subtitles": item.subtitles.model_dump(mode="json"),
        "output": item.output.model_dump(mode="json"),
        "terminal_references": [reference.model_dump(mode="json") for reference in item.terminal_references],
        "failure": item.failure.model_dump(mode="json"),
        "recovery": item.recovery.model_dump(mode="json"),
    }
    # Current-work freshness governs only live claims. A completed, failed,
    # skipped, blocked, review, parked, or stopped item is historical terminal
    # proof and must remain inspectable while a different active worker is
    # stale or unavailable.
    if suppress_current and (suppress_terminal or item.lifecycle_state not in _TERMINAL_ITEM_STATES):
        suppressed_at = suppression_recorded_at.strip() or item.updated_at
        suppressed_evidence = {
            "source": "run_monitor_freshness_policy",
            "provenance": "unknown",
            "recorded_at": suppressed_at,
        }
        payload.update(
            {
                "updated_at": suppressed_at,
                "lifecycle_state": "unknown",
                "lifecycle_evidence": dict(suppressed_evidence),
                "executed_route": {
                    "label": "Executed route",
                    "reason_label": "Executed reason",
                    "state": "unknown",
                    "value": "",
                    "reason": "",
                    "reason_code": "",
                    "evidence": dict(suppressed_evidence),
                },
                "final_route": {
                    "label": "Final route",
                    "reason_label": "Final reason",
                    "state": "unknown",
                    "value": "",
                    "reason": "",
                    "reason_code": "",
                    "evidence": dict(suppressed_evidence),
                },
                "current_stage": None,
                "current_progress": None,
                "stages": [],
                "audio": {
                    "state": "unknown",
                    "policy_final": item.audio.policy_final,
                    "tracks": [],
                    "evidence": dict(suppressed_evidence),
                },
                "subtitles": {
                    "state": "unknown",
                    "policy_final": item.subtitles.policy_final,
                    "tracks": [],
                    "evidence": dict(suppressed_evidence),
                },
                "output": {
                    "state": "unknown",
                    "scratch_path": "",
                    "working_output_path": "",
                    "published_path": "",
                    "parked_path": "",
                    "intended_final_path": item.output.intended_final_path,
                    "size_bytes": None,
                    "verification_state": "unknown",
                    "sidecars": [],
                    "evidence": dict(suppressed_evidence),
                },
                "terminal_references": [],
            }
        )
        if suppress_terminal:
            payload.update(
                {
                    "planned_route": {
                        "label": "Planned route",
                        "reason_label": "Planned reason",
                        "state": "unknown",
                        "value": "",
                        "reason": "",
                        "reason_code": "",
                        "evidence": dict(suppressed_evidence),
                    },
                    "output": {
                        **payload["output"],
                        "intended_final_path": "",
                    },
                    "failure": {
                        "state": "unknown",
                        "reason_code": "",
                        "reason": "",
                        "retryable": None,
                        "reference": "",
                        "evidence": dict(suppressed_evidence),
                    },
                    "recovery": {
                        "owner": "pipeline",
                        "next_action": "",
                        "retryable": None,
                        "evidence": dict(suppressed_evidence),
                    },
                }
            )
    return payload


def _project_workers(record: RunMonitorRecord) -> list[dict[str, Any]]:
    workers: list[dict[str, Any]] = []
    for worker in record.current_workers:
        workers.append(
            {
                "worker_id": worker.worker_id,
                "run_id": worker.run_id,
                "job_id": worker.job_id,
                "state": worker.state,
                "stage_id": worker.stage_id,
                "route": worker.route,
                "progress": _project_progress(worker.progress),
                "updated_at": worker.updated_at,
                "evidence": worker.evidence.model_dump(mode="json"),
            }
        )
    return workers


def _canonical_explicit_route(value: str) -> str | None:
    key = str(value or "").strip().casefold().replace("_", "-")
    aliases = {
        "encode-hardware": "encode_hardware",
        "hardware-encode": "encode_hardware",
        "encode-cpu-fallback": "encode_cpu_fallback",
        "cpu-encode-fallback": "encode_cpu_fallback",
        "encode-safe-retry": "encode_safe_retry",
        "safe-hardware-retry": "encode_safe_retry",
        "remux": "remux",
    }
    return aliases.get(key)


def _contradiction_reason(record: RunMonitorRecord, backend_activity_state: BackendActivityState) -> str:
    if record.run.lifecycle_state in TERMINAL_RUN_LIFECYCLE_STATES:
        return ""
    if backend_activity_state == "confirmed_idle" and (
        record.run.lifecycle_state in _ACTIVE_RUN_STATES
        or record.current_workers
        or any(item.lifecycle_state == "active" for item in record.items)
    ):
        return "contradictory_backend_idle"
    starting_job_ids = {
        worker.job_id
        for worker in record.current_workers
        if worker.state == "starting" and worker.stage_id == "accepted"
    }
    for item in record.items:
        if (
            item.lifecycle_state == "active"
            and item.job_id not in starting_job_ids
            and not any(stage.state == "active" for stage in item.stages)
        ):
            return "contradictory_item_stage"
    for worker in record.current_workers:
        item = next(item for item in record.items if item.job_id == worker.job_id)
        if worker.state == "starting":
            if item.lifecycle_state not in {"accepted", "queued", "active"}:
                return "contradictory_worker_lifecycle"
            if worker.stage_id != "accepted":
                return "contradictory_worker_stage"
            continue
        if item.lifecycle_state != "active":
            return "contradictory_worker_lifecycle"
        active = next((stage for stage in item.stages if stage.state == "active"), None)
        if active is None or active.stage_id != worker.stage_id:
            return "contradictory_worker_stage"
        if item.routes.executed.state == "available":
            executed_route = _canonical_explicit_route(item.routes.executed.route)
            worker_route = _canonical_explicit_route(worker.route)
            if executed_route is not None and worker_route is not None and executed_route != worker_route:
                return "contradictory_worker_route"
    return ""


def _active_item_claim_timestamps(item: RunMonitorItem) -> list[tuple[str, datetime]]:
    candidates: list[tuple[str, datetime]] = []
    active_stage = next((stage for stage in item.stages if stage.state == "active"), None)
    if active_stage is not None:
        candidates.extend(
            (
                (active_stage.updated_at, _parse_timestamp(active_stage.updated_at)),
                (
                    active_stage.evidence.recorded_at,
                    _parse_timestamp(active_stage.evidence.recorded_at),
                ),
            )
        )
    for collection in (item.audio, item.subtitles):
        if collection.state == "active":
            candidates.append(
                (
                    collection.evidence.recorded_at,
                    _parse_timestamp(collection.evidence.recorded_at),
                )
            )
        for track in collection.tracks:
            if track.state == "active":
                candidates.extend(
                    (
                        (track.updated_at, _parse_timestamp(track.updated_at)),
                        (
                            track.evidence.recorded_at,
                            _parse_timestamp(track.evidence.recorded_at),
                        ),
                    )
                )
    return candidates


def _current_claim_timestamp(record: RunMonitorRecord) -> tuple[str, datetime] | None:
    """Return the oldest exact liveness claim that still populates current UI.

    A monitor file write is not itself worker/stage/track liveness. Every active
    worker and every active stage/track remains visible, so the oldest required
    claim governs the shared freshness decision. A fresh worker heartbeat must
    never mask stale per-file or per-track evidence.
    """

    required_claims: list[tuple[str, datetime]] = []
    for worker in record.current_workers:
        required_claims.extend(
            (
                (worker.updated_at, _parse_timestamp(worker.updated_at)),
                (worker.evidence.recorded_at, _parse_timestamp(worker.evidence.recorded_at)),
            )
        )
    for item in record.items:
        if item.lifecycle_state != "active":
            continue
        required_claims.extend(_active_item_claim_timestamps(item))
    return min(required_claims, key=lambda candidate: candidate[1]) if required_claims else None


def _latest_current_claim_timestamp(record: RunMonitorRecord) -> tuple[str, datetime] | None:
    """Return the newest timestamp among every claim eligible for current UI.

    Staleness intentionally uses the oldest required liveness claim, while
    temporal trust must fail if *any* paired worker/stage/track timestamp is
    implausibly future-dated. Keeping these bounds separate prevents one valid
    timestamp from masking a contradictory future claim.
    """

    candidates: list[tuple[str, datetime]] = []
    for worker in record.current_workers:
        candidates.extend(
            (
                (worker.updated_at, _parse_timestamp(worker.updated_at)),
                (
                    worker.evidence.recorded_at,
                    _parse_timestamp(worker.evidence.recorded_at),
                ),
            )
        )
    for item in record.items:
        if item.lifecycle_state == "active":
            candidates.extend(_active_item_claim_timestamps(item))
    return max(candidates, key=lambda candidate: candidate[1]) if candidates else None


def _latest_visible_claim_timestamp(record: RunMonitorRecord) -> tuple[str, datetime] | None:
    """Return the newest timestamp in any claim the current projection can expose.

    Terminal proof is intentionally exempt from liveness staleness, but it is
    never exempt from temporal trust. Walking the strict contract makes final
    routes, output/sidecar artifacts, failures, recovery, terminal references,
    stages, and tracks obey the same impossible-future bound as current work.
    """

    timestamp_fields = {"started_at", "updated_at", "completed_at", "ended_at", "requested_at", "recorded_at"}
    candidates: list[tuple[str, datetime]] = []

    def collect(value: Any) -> None:
        if isinstance(value, Mapping):
            for key, nested in value.items():
                if key in timestamp_fields:
                    text = str(nested or "").strip()
                    if text:
                        candidates.append((text, _parse_timestamp(text)))
                else:
                    collect(nested)
        elif isinstance(value, list):
            for nested in value:
                collect(nested)

    collect(record.model_dump(mode="json"))
    return max(candidates, key=lambda candidate: candidate[1]) if candidates else None


def unavailable_run_monitor_projection(
    *,
    reason_code: str,
    backend_activity_state: BackendActivityState,
    detail: str = "",
) -> dict[str, Any]:
    return {
        "schema_version": RUN_MONITOR_PROJECTION_SCHEMA_VERSION,
        "run": None,
        "freshness": {
            "state": "unavailable",
            "reason_code": reason_code,
            "detail": detail,
            "updated_at": "",
            "age_seconds": None,
            "backend_state": backend_activity_state,
        },
        "items": [],
        "current_workers": [],
        "last_known": None,
        "compatibility": {"legacy_current_work_used": False},
    }


def project_run_monitor(
    payload: RunMonitorRecord | Mapping[str, Any],
    *,
    now: datetime | None = None,
    backend_activity_state: BackendActivityState = "unknown",
    stale_after_seconds: float = 45.0,
    future_tolerance_seconds: float = 5.0,
) -> dict[str, Any]:
    record = payload if isinstance(payload, RunMonitorRecord) else RunMonitorRecord.model_validate(payload)
    current_time = _utc_now(now)
    try:
        run_updated_at = _parse_timestamp(record.run.updated_at)
        current_claim = _current_claim_timestamp(record)
        latest_current_claim = _latest_current_claim_timestamp(record)
        latest_visible_claim = _latest_visible_claim_timestamp(record)
    except (TypeError, ValueError):
        return unavailable_run_monitor_projection(
            reason_code="invalid_current_evidence_timestamp",
            backend_activity_state=backend_activity_state,
            detail="A backend Run Monitor evidence timestamp could not be parsed.",
        )
    effective_updated_at_text = record.run.updated_at
    effective_updated_at = run_updated_at
    effective_source = "run"
    if current_claim is not None and current_claim[1] < effective_updated_at:
        effective_updated_at_text, effective_updated_at = current_claim
        effective_source = "current_claim"
    age_seconds = (current_time - effective_updated_at).total_seconds()
    run_age_seconds = (current_time - run_updated_at).total_seconds()
    latest_current_claim_age_seconds = (
        (current_time - latest_current_claim[1]).total_seconds() if latest_current_claim is not None else None
    )
    latest_visible_claim_age_seconds = (
        (current_time - latest_visible_claim[1]).total_seconds() if latest_visible_claim is not None else None
    )
    terminal = record.run.lifecycle_state in TERMINAL_RUN_LIFECYCLE_STATES
    contradiction = _contradiction_reason(record, backend_activity_state)
    temporal_untrusted = False
    if run_age_seconds < -abs(float(future_tolerance_seconds)):
        freshness_state = "unknown"
        reason_code = "future_timestamp"
        suppress_current = True
        temporal_untrusted = True
    elif (
        latest_current_claim_age_seconds is not None
        and latest_current_claim_age_seconds < -abs(float(future_tolerance_seconds))
    ):
        freshness_state = "unknown"
        reason_code = "current_evidence_future_timestamp"
        suppress_current = True
        temporal_untrusted = True
    elif (
        latest_visible_claim_age_seconds is not None
        and latest_visible_claim_age_seconds < -abs(float(future_tolerance_seconds))
    ):
        freshness_state = "unknown"
        reason_code = "future_timestamp"
        suppress_current = True
        temporal_untrusted = True
    elif terminal:
        freshness_state = "terminal"
        reason_code = "terminal_backend_evidence"
        suppress_current = False
    elif backend_activity_state == "unavailable":
        freshness_state = "unavailable"
        reason_code = "backend_activity_unavailable"
        suppress_current = True
    elif contradiction:
        freshness_state = "unknown"
        reason_code = contradiction
        suppress_current = True
    elif age_seconds > max(0.0, float(stale_after_seconds)):
        freshness_state = "stale"
        reason_code = "current_evidence_stale" if effective_source == "current_claim" else "evidence_stale"
        suppress_current = True
    elif backend_activity_state == "unknown":
        freshness_state = "unknown"
        reason_code = "backend_activity_unknown"
        suppress_current = True
    else:
        freshness_state = "current"
        reason_code = "backend_confirmed_current"
        suppress_current = False

    projection_timestamp = current_time.isoformat().replace("+00:00", "Z")
    projected_items = [
        _project_item(
            item,
            suppress_current=suppress_current,
            suppress_terminal=temporal_untrusted,
            suppression_recorded_at=projection_timestamp,
        )
        for item in record.items
    ]
    projected_workers = [] if suppress_current or terminal else _project_workers(record)
    last_known = None
    if suppress_current:
        last_known = {
            "label": "Last known — not current",
            "updated_at": effective_updated_at_text,
            "age_seconds": max(0.0, age_seconds),
            "items": [
                _project_item(
                    item,
                    suppress_current=False,
                    suppress_terminal=temporal_untrusted,
                    suppression_recorded_at=projection_timestamp,
                )
                for item in record.items
            ],
            "current_workers": _project_workers(record),
        }

    run_payload = record.run.model_dump(mode="json")
    run_payload["display_mode"] = "Run Once · Backend Queue"
    if temporal_untrusted:
        run_payload["lifecycle_state"] = "unknown"
        run_payload["evidence"] = {
            "source": "run_monitor_freshness_policy",
            "provenance": "unknown",
            "recorded_at": projection_timestamp,
        }
    return {
        "schema_version": RUN_MONITOR_PROJECTION_SCHEMA_VERSION,
        "run": run_payload,
        "freshness": {
            "state": freshness_state,
            "reason_code": reason_code,
            "detail": "",
            "updated_at": effective_updated_at_text,
            "age_seconds": max(0.0, age_seconds),
            "backend_state": backend_activity_state,
        },
        "items": projected_items,
        "current_workers": projected_workers,
        "last_known": last_known,
        "compatibility": {"legacy_current_work_used": False},
    }


def read_run_monitor_projection(
    state_root: Path,
    *,
    run_id: str | None = None,
    now: datetime | None = None,
    backend_activity_state: BackendActivityState = "unknown",
    stale_after_seconds: float = 45.0,
    future_tolerance_seconds: float = 5.0,
) -> dict[str, Any]:
    store = RunMonitorStore(Path(state_root))
    try:
        record = store.read(run_id)
    except (ValidationError, ValueError, TypeError, OSError) as exc:
        return unavailable_run_monitor_projection(
            reason_code="invalid_contract",
            backend_activity_state=backend_activity_state,
            detail=str(exc),
        )
    if record is None:
        return unavailable_run_monitor_projection(
            reason_code="monitor_not_found",
            backend_activity_state=backend_activity_state,
        )
    return project_run_monitor(
        record,
        now=now,
        backend_activity_state=backend_activity_state,
        stale_after_seconds=stale_after_seconds,
        future_tolerance_seconds=future_tolerance_seconds,
    )


def read_backend_correlated_run_monitor_projection(
    state_root: Path,
    active_jobs_path: Path | None,
    *,
    run_id: str | None = None,
    now: datetime | None = None,
    stale_after_seconds: float = 45.0,
    future_tolerance_seconds: float = 5.0,
    pid_alive: Callable[[int], bool | None] | None = None,
) -> dict[str, Any]:
    """Read one durable monitor and independently confirm its process activity."""

    store = RunMonitorStore(Path(state_root))
    try:
        record = store.read(run_id)
    except (ValidationError, ValueError, TypeError, OSError) as exc:
        return unavailable_run_monitor_projection(
            reason_code="invalid_contract",
            backend_activity_state="unavailable",
            detail=str(exc),
        )
    if record is None:
        return unavailable_run_monitor_projection(
            reason_code="monitor_not_found",
            backend_activity_state="unknown",
        )
    backend_activity_state = backend_activity_state_for_run(
        active_jobs_path,
        record.run.run_id,
        pid_alive=pid_alive,
    )
    return project_run_monitor(
        record,
        now=now,
        backend_activity_state=backend_activity_state,
        stale_after_seconds=stale_after_seconds,
        future_tolerance_seconds=future_tolerance_seconds,
    )


__all__ = [
    "BackendActivityState",
    "RunMonitorStore",
    "backend_activity_state_for_run",
    "project_run_monitor",
    "read_backend_correlated_run_monitor_projection",
    "read_run_monitor_projection",
    "seed_starting_run_monitor",
    "terminalize_launch_failed_run",
    "terminalize_force_stopped_run",
    "unavailable_run_monitor_projection",
]
