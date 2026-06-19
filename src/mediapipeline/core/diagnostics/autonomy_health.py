from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any, Iterable, Mapping

from mediapipeline.core.kernel.contracts.pending_publish import PENDING_PUSH_RETRY_LIMIT

AUTONOMY_HEALTH_SCHEMA_VERSION = "desktop_autonomy_health.v1"

PENDING_REVIEW_SECONDS = 24 * 60 * 60
PENDING_BLOCK_SECONDS = 72 * 60 * 60
PENDING_RETRY_BLOCK_COUNT = PENDING_PUSH_RETRY_LIMIT
PENDING_TOTAL_REVIEW_BYTES = 100 * 1024**3
PENDING_TOTAL_BLOCK_BYTES = 250 * 1024**3

FAILURE_OPERATOR_REQUIRED_BLOCK_SECONDS = 72 * 60 * 60
FAILURE_OPERATOR_REQUIRED_BLOCK_COUNT = 10
FAILURE_INFRASTRUCTURE_BLOCK_COUNT = 3

ACTIVE_JOB_REVIEW_SECONDS = 30 * 60
ACTIVE_JOB_TIMEOUT_GRACE_SECONDS = 15 * 60
ACTIVE_JOB_NO_TIMEOUT_BLOCK_SECONDS = 30 * 60

DEFAULT_STORAGE_MIN_FREE_GB = 100.0
STATE_FILE_REVIEW_BYTES = 100 * 1024**2
STATE_FILE_BLOCK_BYTES = 500 * 1024**2
AUTONOMY_SCAN_LIMIT = 500
AUTONOMY_GROWTH_PILOT_DAYS = 7
AUTONOMY_GROWTH_PROJECTION_DAYS = 30
AUTONOMY_GROWTH_REQUIRED_SNAPSHOTS = 2
AUTONOMY_GROWTH_SNAPSHOT_MAX_COUNT = 64
AUTONOMY_GROWTH_SNAPSHOT_FILE_NAME = "autonomy_growth_snapshots.jsonl"
GIB_BYTES = 1024**3

AUTONOMY_CATEGORY_LABELS: dict[str, str] = {
    "pending_publish": "Pending publish",
    "failures": "Failure review",
    "workers": "Workers and ActiveJobs",
    "disk_state": "Disk and state growth",
    "path_health": "Configured path health",
    "journals": "Journals and manifests",
    "publish_recency": "Publish recency",
    "subtitles_ocr": "Subtitle and OCR review",
    "audio_policy_reviews": "Audio policy review",
}


def autonomy_health_payload(
    resolved: Any,
    *,
    pending_publish: Mapping[str, Any] | None = None,
    path_health: Mapping[str, Any] | None = None,
    now: datetime | None = None,
    psutil_module: Any = None,
    growth_history: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Return read-only health evidence for unattended launch gating."""
    checked_at = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    failure_findings = _failure_findings(resolved, checked_at)
    categories = {
        "pending_publish": _pending_publish_category(pending_publish, checked_at),
        "failures": _failures_category(failure_findings),
        "workers": _workers_category(resolved, checked_at, psutil_module=psutil_module),
        "disk_state": _disk_state_category(resolved, path_health),
        "path_health": _path_health_category(path_health),
        "journals": _journals_category(resolved),
        "publish_recency": _publish_recency_category(resolved, checked_at),
        "subtitles_ocr": _topic_failure_category(
            "subtitles_ocr",
            "Subtitle and OCR review",
            failure_findings,
            ("subtitle", "subtitles", "ocr", "tx3g", "bdpgs", "vobsub", "ass", "ssa"),
        ),
        "audio_policy_reviews": _topic_failure_category(
            "audio_policy_reviews",
            "Audio policy review",
            failure_findings,
            ("audio", "downmix", "passthrough", "transcode", "channel"),
        ),
    }
    blockers = _flatten_issue(categories.values(), "blockers")
    review_items = _flatten_issue(categories.values(), "review_items")
    overall_status = _overall_status(category["status"] for category in categories.values())
    summary_lines = _summary_lines(overall_status, categories, blockers, review_items)
    return {
        "schema_version": AUTONOMY_HEALTH_SCHEMA_VERSION,
        "checked_at_utc": checked_at.isoformat(timespec="seconds").replace("+00:00", "Z"),
        "overall_status": overall_status,
        "overall_status_state": _status_state(overall_status),
        "read_only": True,
        "guardrail": (
            "Backend-owned read-only autonomy health. This payload gates new launches when blocked; "
            "it does not stop active work, repair state, drain pending publish, delete files, or mutate media."
        ),
        "launch_gate": {
            "schema_version": "desktop_autonomy_launch_gate.v1",
            "can_start_new_work": overall_status != "blocked",
            "blocked_reason": str(blockers[0].get("message") or "") if blockers else "",
            "safe_next_action": _launch_gate_next_action(blockers, review_items),
            "recovery_action": _launch_gate_recovery_action(blockers, review_items),
            "policy": "Gate new work only; active workers/processes are left to existing timeout and lifecycle controls.",
        },
        "external_alert": _external_alert_payload(overall_status, blockers, review_items, summary_lines),
        "growth_projection": _growth_projection_payload(
            resolved,
            pending_publish,
            path_health,
            categories,
            blockers,
            review_items,
            checked_at,
            growth_history,
        ),
        "categories": categories,
        "blockers": blockers,
        "review_items": review_items,
        "blocked_count": len(blockers),
        "review_count": len(review_items),
        "summary_lines": summary_lines,
    }


def autonomy_health_is_blocked(payload: Mapping[str, Any] | None) -> bool:
    return str((payload or {}).get("overall_status") or "").casefold() == "blocked"


def load_autonomy_growth_history(
    resolved: Any,
    *,
    max_snapshots: int = AUTONOMY_GROWTH_SNAPSHOT_MAX_COUNT,
) -> dict[str, Any]:
    snapshot_path = _growth_snapshot_path(resolved)
    limit = _bounded_snapshot_limit(max_snapshots)
    snapshots: list[dict[str, Any]] = []
    invalid_line_count = 0
    read_error = ""
    if snapshot_path is not None and snapshot_path.exists() and snapshot_path.is_file():
        try:
            with snapshot_path.open("r", encoding="utf-8") as handle:
                for raw_line in handle:
                    line = raw_line.strip()
                    if not line:
                        continue
                    try:
                        item = json.loads(line)
                    except json.JSONDecodeError:
                        invalid_line_count += 1
                        continue
                    if isinstance(item, Mapping):
                        snapshots.append(dict(item))
                    else:
                        invalid_line_count += 1
        except OSError as exc:
            read_error = str(exc)
    retained = snapshots[-limit:]
    return {
        "schema_version": "desktop_autonomy_growth_history.v1",
        "effect": "none",
        "read_only": True,
        "snapshot_path": str(snapshot_path or ""),
        "snapshot_count": len(retained),
        "total_snapshot_count": len(snapshots),
        "invalid_line_count": invalid_line_count,
        "max_snapshot_count": limit,
        "read_error": read_error,
        "snapshots": retained,
    }


def record_autonomy_growth_snapshot(
    resolved: Any,
    health_payload: Mapping[str, Any],
    *,
    now: datetime | None = None,
    max_snapshots: int = AUTONOMY_GROWTH_SNAPSHOT_MAX_COUNT,
) -> dict[str, Any]:
    snapshot_path = _growth_snapshot_path(resolved)
    recorded_at = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    snapshot = _growth_snapshot_from_payload(health_payload, recorded_at)
    limit = _bounded_snapshot_limit(max_snapshots)
    if snapshot_path is None:
        return _growth_snapshot_write_result(
            snapshot_path=None,
            snapshot=snapshot,
            retained_snapshot_count=0,
            max_snapshots=limit,
            wrote_snapshot=False,
            error="state_root is unavailable",
        )
    history = load_autonomy_growth_history(resolved, max_snapshots=limit)
    snapshots = [item for item in history.get("snapshots", []) if isinstance(item, Mapping)]
    retained = [dict(item) for item in snapshots] + [snapshot]
    retained = retained[-limit:]
    try:
        snapshot_path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = snapshot_path.with_name(f"{snapshot_path.name}.tmp")
        with temp_path.open("w", encoding="utf-8", newline="\n") as handle:
            for item in retained:
                handle.write(json.dumps(item, sort_keys=True, separators=(",", ":")))
                handle.write("\n")
        temp_path.replace(snapshot_path)
    except OSError as exc:
        return _growth_snapshot_write_result(
            snapshot_path=snapshot_path,
            snapshot=snapshot,
            retained_snapshot_count=len(snapshots),
            max_snapshots=limit,
            wrote_snapshot=False,
            error=str(exc),
        )
    return _growth_snapshot_write_result(
        snapshot_path=snapshot_path,
        snapshot=snapshot,
        retained_snapshot_count=len(retained),
        max_snapshots=limit,
        wrote_snapshot=True,
        error="",
    )


def _pending_publish_category(pending_publish: Mapping[str, Any] | None, now: datetime) -> dict[str, Any]:
    if not isinstance(pending_publish, Mapping):
        return _category(
            "pending_publish",
            "review",
            summary_lines=["Pending publish scan was not available to autonomy health."],
            review_items=[
                _issue(
                    "autonomy_pending_scan_unavailable",
                    "pending_publish",
                    "medium",
                    "Pending publish scan was not available.",
                    next_action="Refresh Pending Publish diagnostics before starting unattended work.",
                    recovery_action=_pending_publish_recovery_plan_action(),
                )
            ],
        )
    rows = [row for row in pending_publish.get("rows", []) if isinstance(row, Mapping)]
    blockers: list[dict[str, Any]] = []
    review_items: list[dict[str, Any]] = []
    total_bytes = _safe_int(pending_publish.get("total_bytes"))
    error = str(pending_publish.get("error") or "").strip()
    if error:
        issue = _issue(
            "autonomy_pending_scan_error",
            "pending_publish",
            "critical",
            f"Pending publish could not be scanned: {error}",
            next_action="Fix PendingServerPush readability before launching new work.",
            recovery_action=_pending_publish_recovery_plan_action(),
        )
        if "not resolved" in error.casefold() and not rows:
            issue["severity"] = "medium"
            review_items.append(issue)
        else:
            blockers.append(
                issue
            )
    if total_bytes >= PENDING_TOTAL_BLOCK_BYTES:
        blockers.append(
            _issue(
                "autonomy_pending_bytes_over_budget",
                "pending_publish",
                "high",
                f"Pending publish parked bytes exceed the blocked budget ({total_bytes} bytes).",
                next_action="Drain or review parked outputs before launching new work.",
                recovery_action=_pending_publish_drain_action(),
            )
        )
    elif total_bytes >= PENDING_TOTAL_REVIEW_BYTES:
        review_items.append(
            _issue(
                "autonomy_pending_bytes_review",
                "pending_publish",
                "medium",
                f"Pending publish parked bytes exceed the review budget ({total_bytes} bytes).",
                next_action="Review parked output growth before a 7-day unattended run.",
                recovery_action=_pending_publish_recovery_plan_action(),
            )
        )
    oldest_age = 0
    for row in rows:
        row_error = str(row.get("error") or "").strip()
        evidence_path = str(row.get("manifest_path") or row.get("path") or "")
        age_seconds = _row_age_seconds(row, now)
        oldest_age = max(oldest_age, int(age_seconds or 0))
        retry_count = _pending_retry_count(row)
        if row_error:
            blockers.append(
                _issue(
                    "autonomy_pending_manifest_untrusted",
                    "pending_publish",
                    "critical",
                    f"Pending publish row needs manual recovery: {row_error}",
                    evidence_path=evidence_path,
                    age_seconds=age_seconds,
                    next_action="Keep the file parked and inspect Pending Publish diagnostics; do not rerun or drain blindly.",
                    recovery_action=_pending_publish_recovery_plan_action(row_key=str(row.get("row_key") or "")),
                )
            )
        if retry_count >= PENDING_RETRY_BLOCK_COUNT:
            blockers.append(
                _issue(
                    "autonomy_pending_retry_exhausted",
                    "pending_publish",
                    "high",
                    f"Pending publish retry count is {retry_count}, at or above the unattended gate.",
                    evidence_path=evidence_path,
                    age_seconds=age_seconds,
                    next_action="Dead-letter or manually review this parked output before starting more queue work.",
                    recovery_action=_pending_publish_recovery_plan_action(row_key=str(row.get("row_key") or "")),
                )
            )
        if age_seconds is not None and age_seconds >= PENDING_BLOCK_SECONDS:
            blockers.append(
                _issue(
                    "autonomy_pending_oldest_blocked",
                    "pending_publish",
                    "high",
                    "Pending publish item has been parked for at least 72 hours.",
                    evidence_path=evidence_path,
                    age_seconds=age_seconds,
                    next_action="Drain or review old parked output before launching new work.",
                    recovery_action=_pending_publish_drain_action(),
                )
            )
        elif age_seconds is not None and age_seconds >= PENDING_REVIEW_SECONDS:
            review_items.append(
                _issue(
                    "autonomy_pending_oldest_review",
                    "pending_publish",
                    "medium",
                    "Pending publish item has been parked for at least 24 hours.",
                    evidence_path=evidence_path,
                    age_seconds=age_seconds,
                    next_action="Review Pending Publish before the unattended pilot continues.",
                    recovery_action=_pending_publish_recovery_plan_action(row_key=str(row.get("row_key") or "")),
                )
            )
    inventory = pending_publish.get("file_inventory")
    if isinstance(inventory, Mapping) and _safe_int(inventory.get("orphan_payload_count")) > 0:
        review_items.append(
            _issue(
                "autonomy_pending_orphan_payloads",
                "pending_publish",
                "medium",
                "Pending publish contains unreferenced payload-like file(s).",
                evidence_path=str(inventory.get("pending_root") or ""),
                next_action="Inspect unreferenced payloads before cleanup, rerun, or drain.",
                recovery_action=_pending_publish_recovery_plan_action(),
            )
        )
    return _category(
        "pending_publish",
        _issue_status(blockers, review_items),
        metrics={
            "manifest_count": _safe_int(pending_publish.get("count")),
            "row_count": len(rows),
            "total_bytes": total_bytes,
            "oldest_age_seconds": oldest_age,
            "health_count": _safe_int(pending_publish.get("health_count")),
        },
        summary_lines=[
            f"Pending rows: {len(rows)}; bytes={total_bytes}; oldest_age_seconds={oldest_age}.",
            "Blocked rows keep files parked; this health check does not drain, delete, repair, or rerun.",
        ],
        blockers=blockers,
        review_items=review_items,
    )


def _failures_category(findings: list[dict[str, Any]]) -> dict[str, Any]:
    blockers: list[dict[str, Any]] = []
    review_items: list[dict[str, Any]] = []
    operator_required = [item for item in findings if item["operator_required"]]
    infrastructure = [item for item in findings if item["infrastructure"]]
    if len(operator_required) > FAILURE_OPERATOR_REQUIRED_BLOCK_COUNT:
        blockers.append(
            _issue(
                "autonomy_failure_operator_required_count",
                "failures",
                "high",
                f"{len(operator_required)} operator-required failure artifact(s) remain unresolved.",
                next_action="Clear, classify, or resolve old operator-required failures before unattended launch.",
            )
        )
    old_operator_required = [
        item for item in operator_required if item.get("age_seconds") is not None and item["age_seconds"] >= FAILURE_OPERATOR_REQUIRED_BLOCK_SECONDS
    ]
    for item in old_operator_required[:3]:
        blockers.append(
            _issue(
                "autonomy_failure_operator_required_old",
                "failures",
                "high",
                "Operator-required failure is older than 72 hours.",
                evidence_path=str(item.get("path") or ""),
                age_seconds=item.get("age_seconds"),
                next_action="Review the failure artifact and clear it only through backend-owned recovery.",
            )
        )
    if len(infrastructure) >= FAILURE_INFRASTRUCTURE_BLOCK_COUNT:
        blockers.append(
            _issue(
                "autonomy_failure_infrastructure_repeated",
                "failures",
                "high",
                f"{len(infrastructure)} infrastructure-like failure artifact(s) are present.",
                next_action="Resolve repeated network/share/disk/copy/publish failures before unattended launch.",
            )
        )
    if findings and not blockers:
        review_items.append(
            _issue(
                "autonomy_failure_artifacts_present",
                "failures",
                "medium",
                f"{len(findings)} failure artifact(s) are present.",
                next_action="Review failure artifacts before a 7-day unattended run.",
            )
        )
    return _category(
        "failures",
        _issue_status(blockers, review_items),
        metrics={
            "artifact_count": len(findings),
            "operator_required_count": len(operator_required),
            "infrastructure_count": len(infrastructure),
        },
        summary_lines=[
            f"Failure artifacts: {len(findings)}; operator_required={len(operator_required)}; infrastructure={len(infrastructure)}.",
            "Failure health is read-only; source markers and reports are not cleared here.",
        ],
        blockers=blockers,
        review_items=review_items,
    )


def _workers_category(resolved: ResolvedPaths, now: datetime, *, psutil_module: Any = None) -> dict[str, Any]:
    active_dir = resolved.active_jobs_path or (resolved.state_root / "ActiveJobs" if resolved.state_root else None)
    blockers: list[dict[str, Any]] = []
    review_items: list[dict[str, Any]] = []
    watchdog_records: list[dict[str, Any]] = []
    active_count = 0
    malformed_count = 0
    if not active_dir or not active_dir.exists():
        return _category(
            "workers",
            "ready",
            metrics={"active_count": 0, "malformed_count": 0, "active_liveness_watchdog": _active_liveness_watchdog([])},
            summary_lines=["No ActiveJobs folder is present yet, or it contains no active job evidence."],
        )
    for path in _iter_files(active_dir, "*.json"):
        try:
            payload = json.loads(path.read_text(encoding="utf-8-sig"))
        except Exception as exc:
            malformed_count += 1
            blockers.append(
                _issue(
                    "autonomy_active_job_unreadable",
                    "workers",
                    "high",
                    f"ActiveJobs record could not be read: {exc}",
                    evidence_path=str(path),
                    next_action="Repair or archive unreadable ActiveJobs evidence before launching new work.",
                )
            )
            continue
        if not isinstance(payload, Mapping):
            malformed_count += 1
            blockers.append(
                _issue(
                    "autonomy_active_job_invalid_shape",
                    "workers",
                    "high",
                    "ActiveJobs record JSON root is not an object.",
                    evidence_path=str(path),
                    next_action="Repair or archive invalid ActiveJobs evidence before launching new work.",
                )
            )
            continue
        status = str(payload.get("status") or "").casefold()
        if status not in {"launching", "active"}:
            continue
        if psutil_module is not None and _active_job_definitely_dead(payload, psutil_module):
            continue
        active_count += 1
        evidence = _active_liveness_evidence(resolved, payload, path, now)
        watchdog_records.append(evidence)
        age_seconds = evidence.get("latest_evidence_age_seconds")
        pid = payload.get("pid")
        label = f"{payload.get('job_kind') or 'process'} {payload.get('mode') or ''}".strip()
        if pid in (None, ""):
            blockers.append(
                _issue(
                    "autonomy_active_job_missing_pid",
                    "workers",
                    "high",
                    f"ActiveJobs record reports {label} as {status} with no PID.",
                    evidence_path=str(path),
                    age_seconds=age_seconds,
                    next_action="Reconcile ActiveJobs before launching new work.",
                )
            )
            evidence["status"] = "blocked"
        elif age_seconds is not None and age_seconds >= _safe_int(evidence.get("block_after_seconds")):
            blockers.append(
                _issue(
                    "autonomy_active_job_stale_blocked",
                    "workers",
                    "high",
                    f"ActiveJobs record reports {label} as {status} with stale liveness evidence.",
                    evidence_path=str(evidence.get("latest_evidence_path") or path),
                    age_seconds=age_seconds,
                    next_action="Use backend lifecycle controls or ActiveJobs reconciliation; this health gate will not kill the process.",
                )
            )
            evidence["status"] = "blocked"
        elif age_seconds is not None and age_seconds >= _safe_int(evidence.get("review_after_seconds")):
            review_items.append(
                _issue(
                    "autonomy_active_job_stale_review",
                    "workers",
                    "medium",
                    f"ActiveJobs record reports {label} as {status} with aging liveness evidence.",
                    evidence_path=str(evidence.get("latest_evidence_path") or path),
                    age_seconds=age_seconds,
                    next_action="Review Close Readiness and ActiveJobs before unattended launch.",
                )
            )
            evidence["status"] = "review"
    return _category(
        "workers",
        _issue_status(blockers, review_items),
        metrics={
            "active_count": active_count,
            "malformed_count": malformed_count,
            "active_liveness_watchdog": _active_liveness_watchdog(watchdog_records),
        },
        summary_lines=[
            f"Active worker records: {active_count}; malformed records: {malformed_count}.",
            "Worker health is detection-only in this pilot; active processes are not stopped or rewritten.",
        ],
        blockers=blockers,
        review_items=review_items,
    )


def _active_liveness_watchdog(records: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "schema_version": "desktop_active_liveness_watchdog.v1",
        "effect": "none",
        "read_only": True,
        "would_kill_active_processes": False,
        "would_rewrite_active_jobs": False,
        "policy": (
            "Detection-only liveness evidence for launch gating. Existing native process timeouts and "
            "lifecycle controls remain responsible for active work."
        ),
        "native_timeout_grace_seconds": ACTIVE_JOB_TIMEOUT_GRACE_SECONDS,
        "no_native_timeout_block_after_seconds": ACTIVE_JOB_NO_TIMEOUT_BLOCK_SECONDS,
        "record_count": len(records),
        "records": records,
    }


def _active_liveness_evidence(resolved: ResolvedPaths, payload: Mapping[str, Any], active_job_path: Path, now: datetime) -> dict[str, Any]:
    heartbeat_age = _age_seconds(_first_text(payload, "last_update", "launched_at"), active_job_path, now)
    evidence_candidates = [
        {
            "source": "active_job",
            "path": str(active_job_path),
            "age_seconds": heartbeat_age,
        }
    ]
    progress = _progress_liveness_evidence(resolved.progress_file, now)
    if progress is not None:
        evidence_candidates.append(progress)
    for source, path in (("event_file", resolved.event_file), ("log_file", resolved.log_file)):
        file_evidence = _file_mtime_liveness_evidence(source, path, now)
        if file_evidence is not None:
            evidence_candidates.append(file_evidence)
    latest = _latest_liveness_candidate(evidence_candidates)
    native_timeout_source, native_timeout_seconds = _native_timeout_for_active_job(payload, resolved.config_data)
    block_after = (
        native_timeout_seconds + ACTIVE_JOB_TIMEOUT_GRACE_SECONDS
        if native_timeout_seconds is not None
        else ACTIVE_JOB_NO_TIMEOUT_BLOCK_SECONDS
    )
    return {
        "status": "ready",
        "active_job_path": str(active_job_path),
        "pid": payload.get("pid"),
        "job_kind": str(payload.get("job_kind") or ""),
        "mode": str(payload.get("mode") or ""),
        "active_status": str(payload.get("status") or ""),
        "heartbeat_age_seconds": heartbeat_age,
        "latest_evidence_source": str(latest.get("source") or ""),
        "latest_evidence_path": str(latest.get("path") or ""),
        "latest_evidence_age_seconds": latest.get("age_seconds"),
        "native_timeout_source": native_timeout_source,
        "native_timeout_seconds": native_timeout_seconds,
        "native_timeout_grace_seconds": ACTIVE_JOB_TIMEOUT_GRACE_SECONDS,
        "review_after_seconds": min(ACTIVE_JOB_REVIEW_SECONDS, block_after),
        "block_after_seconds": block_after,
        "evidence_candidates": evidence_candidates,
    }


def _progress_liveness_evidence(path: Path | None, now: datetime) -> dict[str, Any] | None:
    if path is None or not path.exists() or not path.is_file():
        return None
    payload = _read_json_mapping(path)
    if "_read_error" in payload or "_json_root" in payload:
        return None
    status = _first_text(payload, "Status", "status", "CurrentStage", "current_stage").casefold()
    if status in {"completed", "complete", "failed", "idle", "stopped", "not_running", "not running"}:
        return None
    age_seconds = _age_seconds(
        _first_text(payload, "LastUpdate", "last_update", "updated_at", "timestamp", "Timestamp"),
        path,
        now,
    )
    return {
        "source": "progress_file",
        "path": str(path),
        "age_seconds": age_seconds,
    }


def _file_mtime_liveness_evidence(source: str, path: Path | None, now: datetime) -> dict[str, Any] | None:
    if path is None or not path.exists() or not path.is_file():
        return None
    return {
        "source": source,
        "path": str(path),
        "age_seconds": _age_seconds("", path, now),
    }


def _latest_liveness_candidate(candidates: list[dict[str, Any]]) -> dict[str, Any]:
    with_age = [item for item in candidates if item.get("age_seconds") is not None]
    if not with_age:
        return candidates[0] if candidates else {"source": "", "path": "", "age_seconds": None}
    return min(with_age, key=lambda item: int(item.get("age_seconds") or 0))


def _native_timeout_for_active_job(payload: Mapping[str, Any], config_data: Mapping[str, Any] | None) -> tuple[str, int | None]:
    if not isinstance(config_data, Mapping):
        return "", None
    text = " ".join(
        str(payload.get(key) or "")
        for key in ("job_kind", "mode", "stage", "current_stage", "operation", "label")
    ).casefold()
    candidate_keys: list[str] = []
    if "cpu" in text and "encode" in text:
        candidate_keys.append("FFmpegCpuEncodeTimeoutSeconds")
    if "encode" in text:
        candidate_keys.append("FFmpegEncodeTimeoutSeconds")
    if "remux" in text:
        if "mkvmerge" in text:
            candidate_keys.append("MkvmergeRemuxTimeoutSeconds")
        candidate_keys.extend(["FFmpegRemuxTimeoutSeconds", "MkvmergeRemuxTimeoutSeconds"])
    if "subtitle" in text or "tx3g" in text or "ass" in text or "ssa" in text:
        candidate_keys.append("SubtitleExtractTimeoutSeconds")
    if "bdpgs" in text:
        candidate_keys.append("BdpgsOcrTimeoutSeconds")
    if "vobsub" in text:
        candidate_keys.append("VobSubOcrTimeoutSeconds")
    if "copy" in text or "publish" in text or "robocopy" in text:
        candidate_keys.append("RobocopyTimeoutSeconds")
    if "scan" in text or "audit" in text:
        candidate_keys.extend(["SourceScanTimeoutSeconds", "IndexScanTimeoutSeconds"])
    for key in candidate_keys:
        value = _safe_int(config_data.get(key))
        if value > 0:
            return key, value
    return "", None


def _disk_state_category(resolved: ResolvedPaths, path_health: Mapping[str, Any] | None) -> dict[str, Any]:
    blockers: list[dict[str, Any]] = []
    review_items: list[dict[str, Any]] = []
    rows = path_health.get("rows") if isinstance(path_health, Mapping) else []
    if isinstance(rows, list):
        for row in rows:
            if not isinstance(row, Mapping):
                continue
            role = str(row.get("role") or "").casefold()
            if role not in {"scratch", "output"}:
                continue
            free_gb = _safe_float(row.get("free_space_gb"), row.get("free_gb"))
            reserve_gb = _safe_float(row.get("reserve_gb"))
            threshold_gb = reserve_gb if reserve_gb and reserve_gb > 0 else DEFAULT_STORAGE_MIN_FREE_GB
            storage_status = str(row.get("storage_status") or "").casefold()
            if storage_status in {"blocked", "low"} or (free_gb is not None and free_gb < threshold_gb):
                blockers.append(
                    _issue(
                        "autonomy_storage_free_space_low",
                        "disk_state",
                        "critical",
                        f"{row.get('label') or row.get('key') or 'Storage root'} has insufficient free space for unattended launch.",
                        evidence_path=str(row.get("path") or ""),
                        next_action="Free space or adjust backend storage reserve settings before launching new work.",
                    )
                )
            elif storage_status == "unknown":
                review_items.append(
                    _issue(
                        "autonomy_storage_free_space_unknown",
                        "disk_state",
                        "medium",
                        f"{row.get('label') or row.get('key') or 'Storage root'} free space could not be determined.",
                        evidence_path=str(row.get("path") or ""),
                        next_action="Refresh path health and verify free space before unattended launch.",
                    )
                )
    state_dir_size = _directory_size(resolved.state_root)
    local_base_size = _directory_size(resolved.local_base, limit=AUTONOMY_SCAN_LIMIT)
    return _category(
        "disk_state",
        _issue_status(blockers, review_items),
        metrics={
            "state_root_size_bytes": state_dir_size,
            "local_base_scanned_size_bytes": local_base_size,
        },
        summary_lines=[
            f"State root scanned bytes: {state_dir_size}.",
            f"LocalBase scanned bytes: {local_base_size}.",
            "No cleanup is performed by autonomy health.",
        ],
        blockers=blockers,
        review_items=review_items,
    )


def _path_health_category(path_health: Mapping[str, Any] | None) -> dict[str, Any]:
    if not isinstance(path_health, Mapping) or not path_health.get("rows"):
        return _category(
            "path_health",
            "ready",
            metrics={"row_count": 0},
            summary_lines=["No configured path health rows were available; launch-specific checks still run separately."],
        )
    operator_status = str(path_health.get("operator_status") or "unknown").casefold()
    rows = [row for row in path_health.get("rows", []) if isinstance(row, Mapping)]
    blockers: list[dict[str, Any]] = []
    review_items: list[dict[str, Any]] = []
    for row in rows:
        status = str(row.get("operator_status") or row.get("status") or "").casefold()
        if status == "blocked":
            blockers.append(
                _issue(
                    "autonomy_configured_path_blocked",
                    "path_health",
                    "critical",
                    str(row.get("message") or "Configured path health is blocked."),
                    evidence_path=str(row.get("path") or ""),
                    next_action=str(row.get("safe_next_action") or "Restore configured roots before launch."),
                )
            )
        elif status in {"review", "unknown"}:
            review_items.append(
                _issue(
                    "autonomy_configured_path_review",
                    "path_health",
                    "medium",
                    str(row.get("message") or "Configured path health needs review."),
                    evidence_path=str(row.get("path") or ""),
                    next_action=str(row.get("safe_next_action") or "Review configured path health before launch."),
                )
            )
    status = "blocked" if operator_status == "blocked" else _issue_status(blockers, review_items)
    return _category(
        "path_health",
        status,
        metrics={"row_count": len(rows), "operator_status": operator_status},
        summary_lines=[
            str(path_health.get("operator_summary") or f"Configured path health: {operator_status}."),
            "Path health is read-only; no settings, files, or shares are mutated.",
        ],
        blockers=blockers,
        review_items=review_items,
    )


def _journals_category(resolved: ResolvedPaths) -> dict[str, Any]:
    blockers: list[dict[str, Any]] = []
    review_items: list[dict[str, Any]] = []
    file_count = 0
    total_size = 0
    largest_file_size = 0
    for path in _journal_paths(resolved):
        if path is None or not path.exists() or not path.is_file():
            continue
        file_count += 1
        try:
            size = int(path.stat().st_size)
        except OSError as exc:
            review_items.append(
                _issue(
                    "autonomy_journal_stat_failed",
                    "journals",
                    "medium",
                    f"Could not stat journal/state file: {exc}",
                    evidence_path=str(path),
                    next_action="Inspect state file readability before unattended launch.",
                )
            )
            continue
        total_size += size
        largest_file_size = max(largest_file_size, size)
        if size > STATE_FILE_BLOCK_BYTES:
            blockers.append(
                _issue(
                    "autonomy_journal_file_blocked_size",
                    "journals",
                    "high",
                    f"Journal/state file is larger than the blocked budget ({size} bytes).",
                    evidence_path=str(path),
                    next_action="Archive or rotate state/log evidence with backend-approved tooling before launch.",
                    recovery_action=_journal_archive_action(path),
                )
            )
        elif size > STATE_FILE_REVIEW_BYTES:
            review_items.append(
                _issue(
                    "autonomy_journal_file_review_size",
                    "journals",
                    "medium",
                    f"Journal/state file is larger than the review budget ({size} bytes).",
                    evidence_path=str(path),
                    next_action="Review state/log growth before the unattended pilot.",
                    recovery_action=_journal_archive_action(path),
                )
            )
    return _category(
        "journals",
        _issue_status(blockers, review_items),
        metrics={
            "file_count": file_count,
            "total_size_bytes": total_size,
            "largest_file_size_bytes": largest_file_size,
        },
        summary_lines=[
            f"Journal/state files found: {file_count}.",
            f"Journal/state bytes found: {total_size}.",
            "This health payload is read-only; use backend-approved recovery actions to archive oversized runtime event evidence.",
        ],
        blockers=blockers,
        review_items=review_items,
    )


def _publish_recency_category(resolved: ResolvedPaths, now: datetime) -> dict[str, Any]:
    runnable_count = _queue_runnable_count(resolved.queue_snapshot_path)
    manifest = resolved.completed_manifest_path
    review_items: list[dict[str, Any]] = []
    if runnable_count > 0 and (manifest is None or not manifest.exists()):
        review_items.append(
            _issue(
                "autonomy_publish_recency_missing_manifest",
                "publish_recency",
                "medium",
                "Queue snapshot has runnable work but completed manifest is missing.",
                evidence_path=str(manifest or ""),
                next_action="Confirm whether this is a first run or a completed-manifest state issue.",
            )
        )
    elif runnable_count > 0 and manifest is not None and manifest.exists():
        age_seconds = _age_seconds("", manifest, now)
        if age_seconds is not None and age_seconds >= PENDING_REVIEW_SECONDS:
            review_items.append(
                _issue(
                    "autonomy_publish_recency_stale",
                    "publish_recency",
                    "medium",
                    "Queue snapshot has runnable work and no recent completed-manifest update.",
                    evidence_path=str(manifest),
                    age_seconds=age_seconds,
                    next_action="Confirm queue liveness before unattended operation.",
                )
            )
    return _category(
        "publish_recency",
        _issue_status([], review_items),
        metrics={"queue_runnable_count": runnable_count},
        summary_lines=[
            f"Queue runnable count from snapshot: {runnable_count}.",
            "Publish recency is advisory; it does not mutate queue or completed evidence.",
        ],
        review_items=review_items,
    )


def _topic_failure_category(
    key: str,
    label: str,
    findings: list[dict[str, Any]],
    needles: tuple[str, ...],
) -> dict[str, Any]:
    matched = [item for item in findings if any(needle in item["search_text"] for needle in needles)]
    review_items: list[dict[str, Any]] = []
    if matched:
        review_items.append(
            _issue(
                f"autonomy_{key}_failure_review",
                key,
                "medium",
                f"{len(matched)} related failure artifact(s) need review.",
                evidence_path=str(matched[0].get("path") or ""),
                age_seconds=matched[0].get("age_seconds"),
                next_action=f"Review {label.lower()} evidence before unattended launch.",
            )
        )
    return _category(
        key,
        _issue_status([], review_items),
        label=label,
        metrics={"failure_count": len(matched)},
        summary_lines=[f"Related failure artifacts: {len(matched)}."],
        review_items=review_items,
    )


def _failure_findings(resolved: ResolvedPaths, now: datetime) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    roots = [resolved.failed_reports_path, resolved.failed_markers_path]
    for root in roots:
        if root is None or not root.exists():
            continue
        for path in _iter_files(root, "*.json"):
            payload = _read_json_mapping(path)
            search_text = _failure_search_text(payload, path)
            age_seconds = _age_seconds(_first_text(payload, "recorded_at", "RecordedAt", "timestamp", "Timestamp"), path, now)
            findings.append(
                {
                    "path": str(path),
                    "payload": payload,
                    "search_text": search_text,
                    "age_seconds": age_seconds,
                    "operator_required": _is_operator_required_failure(payload, search_text),
                    "infrastructure": _is_infrastructure_failure(search_text),
                }
            )
    return findings[:AUTONOMY_SCAN_LIMIT]


def _read_json_mapping(path: Path) -> Mapping[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception:
        return {"_read_error": str(path)}
    return payload if isinstance(payload, Mapping) else {"_json_root": type(payload).__name__}


def _failure_search_text(payload: Mapping[str, Any], path: Path) -> str:
    values = [path.name]
    for key, value in payload.items():
        if isinstance(value, str | int | float | bool):
            values.append(f"{key}={value}")
    return " ".join(values).casefold()


def _is_operator_required_failure(payload: Mapping[str, Any], text: str) -> bool:
    if bool(payload.get("Escalated") or payload.get("escalated")):
        return True
    return any(term in text for term in ("operator_required", "operator required", "manual_review", "manual review"))


def _is_infrastructure_failure(text: str) -> bool:
    return any(term in text for term in ("network", "share", "smb", "disk", "space", "robocopy", "copy", "publish", "pending", "path"))


def _category(
    key: str,
    status: str,
    *,
    label: str | None = None,
    metrics: Mapping[str, Any] | None = None,
    summary_lines: list[str] | None = None,
    blockers: list[dict[str, Any]] | None = None,
    review_items: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    return {
        "key": key,
        "label": label or AUTONOMY_CATEGORY_LABELS.get(key, key.replace("_", " ").title()),
        "status": status,
        "status_state": _status_state(status),
        "metrics": dict(metrics or {}),
        "summary_lines": summary_lines or [],
        "blockers": blockers or [],
        "review_items": review_items or [],
    }


def _issue(
    code: str,
    category: str,
    severity: str,
    message: str,
    *,
    evidence_path: str = "",
    age_seconds: int | float | None = None,
    next_action: str,
    recovery_action: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    issue = {
        "code": code,
        "category": category,
        "severity": severity,
        "message": message,
        "evidence_path": evidence_path,
        "age_seconds": None if age_seconds is None else int(age_seconds),
        "next_action": next_action,
    }
    if isinstance(recovery_action, Mapping):
        issue["recovery_action"] = dict(recovery_action)
    return issue


def _issue_status(blockers: list[dict[str, Any]], review_items: list[dict[str, Any]]) -> str:
    if blockers:
        return "blocked"
    if review_items:
        return "review"
    return "ready"


def _overall_status(statuses: Iterable[str]) -> str:
    normalized = {str(status or "").casefold() for status in statuses}
    if "blocked" in normalized:
        return "blocked"
    if "review" in normalized or "unknown" in normalized:
        return "review"
    return "ready"


def _status_state(status: str) -> str:
    normalized = str(status or "").casefold()
    if normalized == "blocked":
        return "blocked"
    if normalized == "review":
        return "warning"
    if normalized == "ready":
        return "ready"
    return "unknown"


def _flatten_issue(categories: Iterable[Mapping[str, Any]], key: str) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    for category in categories:
        issues.extend(dict(item) for item in category.get(key, []) if isinstance(item, Mapping))
    return issues


def _summary_lines(
    overall_status: str,
    categories: Mapping[str, Mapping[str, Any]],
    blockers: list[Mapping[str, Any]],
    review_items: list[Mapping[str, Any]],
) -> list[str]:
    counts: dict[str, int] = {}
    for category in categories.values():
        status = str(category.get("status") or "unknown")
        counts[status] = counts.get(status, 0) + 1
    lines = [
        f"Autonomy health: {overall_status}.",
        f"Categories: ready={counts.get('ready', 0)}; review={counts.get('review', 0)}; blocked={counts.get('blocked', 0)}.",
        f"Blockers: {len(blockers)}; review items: {len(review_items)}.",
        "Policy: blocked health gates new work only; active work is not forcibly stopped by this pilot check.",
    ]
    if blockers:
        lines.append(f"First blocker: {blockers[0].get('message')}")
    return lines


def _external_alert_payload(
    overall_status: str,
    blockers: list[Mapping[str, Any]],
    review_items: list[Mapping[str, Any]],
    summary_lines: list[str],
) -> dict[str, Any]:
    blocker_codes = _issue_codes(blockers)
    review_codes = _issue_codes(review_items)
    level = _external_alert_level(overall_status)
    return {
        "schema_version": "desktop_autonomy_alert.v1",
        "effect": "none",
        "read_only": True,
        "operator_attention_required": overall_status != "ready",
        "alert_level": level,
        "subject": _external_alert_subject(overall_status),
        "dedupe_key": _external_alert_dedupe_key(overall_status, blocker_codes, review_codes),
        "recommended_poll_interval_seconds": _external_alert_poll_interval(overall_status),
        "would_send_notifications": False,
        "would_write_files": False,
        "polling_endpoint_hint": "/api/diagnostics/state-summary",
        "cli_hint": "mediapipeline.tools.autonomy_health_gate",
        "policy": (
            "External monitors may poll this metadata and send their own alerts. "
            "The backend payload does not send email, call webhooks, write export files, or mutate pipeline state."
        ),
        "blocker_codes": blocker_codes,
        "review_codes": review_codes,
        "first_blocker": _alert_issue_summary(blockers[0]) if blockers else {},
        "first_review": _alert_issue_summary(review_items[0]) if review_items else {},
        "next_action": _launch_gate_next_action(blockers, review_items),
        "summary_lines": list(summary_lines[:5]),
    }


def _growth_projection_payload(
    resolved: Any,
    pending_publish: Mapping[str, Any] | None,
    path_health: Mapping[str, Any] | None,
    categories: Mapping[str, Mapping[str, Any]],
    blockers: list[Mapping[str, Any]],
    review_items: list[Mapping[str, Any]],
    checked_at: datetime,
    growth_history: Mapping[str, Any] | None,
) -> dict[str, Any]:
    disk_metrics = _category_metrics(categories, "disk_state")
    journal_metrics = _category_metrics(categories, "journals")
    pending_bytes = _safe_int((pending_publish or {}).get("total_bytes")) if isinstance(pending_publish, Mapping) else 0
    state_root_bytes = _safe_int(disk_metrics.get("state_root_size_bytes"))
    local_base_bytes = _safe_int(disk_metrics.get("local_base_scanned_size_bytes"))
    journal_bytes = _safe_int(journal_metrics.get("total_size_bytes"))
    storage_roots = _growth_storage_roots(path_health)
    minimum_free_bytes = _minimum_present(row.get("free_bytes") for row in storage_roots)
    current_budget = {
        "state_root_size_bytes": state_root_bytes,
        "local_base_scanned_size_bytes": local_base_bytes,
        "journal_file_bytes": journal_bytes,
        "pending_publish_bytes": pending_bytes,
        "observed_bytes": state_root_bytes + local_base_bytes + pending_bytes,
        "minimum_free_bytes": minimum_free_bytes,
        "storage_row_count": len(storage_roots),
        "current_only_may_overlap_scanned_roots": True,
    }
    trend = _growth_projection_from_history(growth_history, current_budget, checked_at)
    blocker_codes = _issue_codes(blockers)
    review_codes = _issue_codes(review_items)
    return {
        "schema_version": "desktop_autonomy_growth_projection.v1",
        "effect": "none",
        "read_only": True,
        "operator_status": "blocked" if blocker_codes else "review" if review_codes else "ready",
        "confidence": trend["confidence"],
        "historical_samples_available": trend["historical_samples_available"],
        "required_snapshot_count": AUTONOMY_GROWTH_REQUIRED_SNAPSHOTS,
        "history_sample_count": trend["history_sample_count"],
        "snapshot_source": trend["snapshot_source"],
        "would_write_snapshots": False,
        "would_delete_or_cleanup": False,
        "pilot_window_days": AUTONOMY_GROWTH_PILOT_DAYS,
        "projection_window_days": AUTONOMY_GROWTH_PROJECTION_DAYS,
        "current_budget": current_budget,
        "storage_roots": storage_roots,
        "current_blocker_codes": blocker_codes,
        "current_review_codes": review_codes,
        "basis_snapshot_recorded_at_utc": trend["basis_snapshot_recorded_at_utc"],
        "observed_growth_bytes": trend["observed_growth_bytes"],
        "trend_window_seconds": trend["trend_window_seconds"],
        "growth_rate_bytes_per_day": trend["growth_rate_bytes_per_day"],
        "projected_7_day_growth_bytes": trend["projected_7_day_growth_bytes"],
        "projected_30_day_growth_bytes": trend["projected_30_day_growth_bytes"],
        "days_to_budget_exhaustion": trend["days_to_budget_exhaustion"],
        "next_action": _growth_projection_next_action(blocker_codes, review_codes),
        "policy": (
            "This payload reports current growth-budget evidence and optional history-based estimates. "
            "It does not persist trend snapshots, rotate logs, clean files, or change launch/publish behavior."
        ),
    }


def _category_metrics(categories: Mapping[str, Mapping[str, Any]], key: str) -> Mapping[str, Any]:
    category = categories.get(key)
    if not isinstance(category, Mapping):
        return {}
    metrics = category.get("metrics")
    if isinstance(metrics, Mapping):
        return metrics
    return {}


def _growth_storage_roots(path_health: Mapping[str, Any] | None) -> list[dict[str, Any]]:
    if not isinstance(path_health, Mapping):
        return []
    rows = path_health.get("rows")
    if not isinstance(rows, list):
        return []
    storage_rows: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        free_gb = _safe_float(row.get("free_space_gb"), row.get("free_gb"))
        if free_gb is None:
            continue
        reserve_gb = _safe_float(row.get("reserve_gb"))
        threshold_gb = reserve_gb if reserve_gb and reserve_gb > 0 else DEFAULT_STORAGE_MIN_FREE_GB
        storage_rows.append(
            {
                "key": str(row.get("key") or ""),
                "label": str(row.get("label") or row.get("key") or ""),
                "role": str(row.get("role") or ""),
                "path": str(row.get("path") or ""),
                "free_bytes": _gb_to_bytes(free_gb),
                "threshold_bytes": _gb_to_bytes(threshold_gb),
                "storage_status": str(row.get("storage_status") or ""),
                "operator_status": str(row.get("operator_status") or row.get("status") or ""),
            }
        )
    return storage_rows


def _growth_projection_from_history(
    growth_history: Mapping[str, Any] | None,
    current_budget: Mapping[str, Any],
    checked_at: datetime,
) -> dict[str, Any]:
    no_history = {
        "confidence": "current_evidence_only",
        "historical_samples_available": False,
        "history_sample_count": 0,
        "snapshot_source": "not_persisted_by_v1",
        "basis_snapshot_recorded_at_utc": "",
        "observed_growth_bytes": None,
        "trend_window_seconds": None,
        "growth_rate_bytes_per_day": None,
        "projected_7_day_growth_bytes": None,
        "projected_30_day_growth_bytes": None,
        "days_to_budget_exhaustion": None,
    }
    if not isinstance(growth_history, Mapping):
        return no_history
    snapshots = _valid_growth_snapshots(growth_history.get("snapshots"), checked_at)
    if not snapshots:
        result = dict(no_history)
        result["snapshot_source"] = str(growth_history.get("snapshot_path") or "provided_history")
        return result
    basis = snapshots[-1]
    basis_at = basis["recorded_at"]
    trend_window_seconds = max(0, int((checked_at - basis_at).total_seconds()))
    if trend_window_seconds <= 0:
        result = dict(no_history)
        result["history_sample_count"] = len(snapshots)
        result["snapshot_source"] = str(growth_history.get("snapshot_path") or "provided_history")
        return result
    current_observed = _safe_int(current_budget.get("observed_bytes"))
    observed_growth = current_observed - _safe_int(basis["snapshot"].get("current_budget", {}).get("observed_bytes"))
    growth_per_day = int(max(0.0, observed_growth / (trend_window_seconds / 86400.0)))
    minimum_free = current_budget.get("minimum_free_bytes")
    days_to_exhaustion = None
    if growth_per_day > 0 and minimum_free is not None:
        remaining_bytes = max(0, _safe_int(minimum_free) - current_observed)
        days_to_exhaustion = remaining_bytes / growth_per_day
    return {
        "confidence": "historical_projection",
        "historical_samples_available": True,
        "history_sample_count": len(snapshots),
        "snapshot_source": str(growth_history.get("snapshot_path") or "provided_history"),
        "basis_snapshot_recorded_at_utc": basis["snapshot"].get("recorded_at_utc", ""),
        "observed_growth_bytes": observed_growth,
        "trend_window_seconds": trend_window_seconds,
        "growth_rate_bytes_per_day": growth_per_day,
        "projected_7_day_growth_bytes": growth_per_day * AUTONOMY_GROWTH_PILOT_DAYS,
        "projected_30_day_growth_bytes": growth_per_day * AUTONOMY_GROWTH_PROJECTION_DAYS,
        "days_to_budget_exhaustion": days_to_exhaustion,
    }


def _valid_growth_snapshots(raw_snapshots: Any, checked_at: datetime) -> list[dict[str, Any]]:
    if not isinstance(raw_snapshots, list):
        return []
    snapshots: list[dict[str, Any]] = []
    for item in raw_snapshots:
        if not isinstance(item, Mapping):
            continue
        recorded_at = _parse_datetime(item.get("recorded_at_utc"))
        budget = item.get("current_budget")
        if recorded_at is None or not isinstance(budget, Mapping):
            continue
        if recorded_at >= checked_at:
            continue
        snapshots.append({"recorded_at": recorded_at, "snapshot": dict(item)})
    return sorted(snapshots, key=lambda item: item["recorded_at"])


def _growth_snapshot_path(resolved: Any) -> Path | None:
    state_root = getattr(resolved, "state_root", None)
    if state_root is None:
        return None
    return Path(state_root) / "Diagnostics" / AUTONOMY_GROWTH_SNAPSHOT_FILE_NAME


def _growth_snapshot_from_payload(health_payload: Mapping[str, Any], recorded_at: datetime) -> dict[str, Any]:
    projection = health_payload.get("growth_projection")
    current_budget = projection.get("current_budget") if isinstance(projection, Mapping) else {}
    blocker_codes = projection.get("current_blocker_codes") if isinstance(projection, Mapping) else []
    review_codes = projection.get("current_review_codes") if isinstance(projection, Mapping) else []
    return {
        "schema_version": "desktop_autonomy_growth_snapshot.v1",
        "recorded_at_utc": recorded_at.isoformat(timespec="seconds").replace("+00:00", "Z"),
        "health_checked_at_utc": str(health_payload.get("checked_at_utc") or ""),
        "overall_status": str(health_payload.get("overall_status") or "unknown"),
        "current_budget": dict(current_budget or {}),
        "current_blocker_codes": list(blocker_codes) if isinstance(blocker_codes, list) else [],
        "current_review_codes": list(review_codes) if isinstance(review_codes, list) else [],
    }


def _growth_snapshot_write_result(
    *,
    snapshot_path: Path | None,
    snapshot: Mapping[str, Any],
    retained_snapshot_count: int,
    max_snapshots: int,
    wrote_snapshot: bool,
    error: str,
) -> dict[str, Any]:
    return {
        "schema_version": "desktop_autonomy_growth_snapshot_write.v1",
        "effect": "diagnostics_state_snapshot_write",
        "snapshot_path": str(snapshot_path or ""),
        "wrote_snapshot": wrote_snapshot,
        "retained_snapshot_count": retained_snapshot_count,
        "max_snapshot_count": max_snapshots,
        "snapshot": dict(snapshot),
        "error": error,
        "media_mutation_performed": False,
        "cleanup_performed": False,
        "pending_publish_mutation_performed": False,
        "queue_mutation_performed": False,
        "policy": (
            "Explicit diagnostics-state snapshot write only. This helper does not touch source media, "
            "pending publish files, queue state, cleanup targets, or final outputs."
        ),
    }


def _bounded_snapshot_limit(max_snapshots: int) -> int:
    requested = _safe_int(max_snapshots)
    if requested <= 0:
        return AUTONOMY_GROWTH_SNAPSHOT_MAX_COUNT
    return min(requested, AUTONOMY_GROWTH_SNAPSHOT_MAX_COUNT)


def _minimum_present(values: Iterable[Any]) -> int | None:
    integers = [_safe_int(value) for value in values if value not in (None, "")]
    if not integers:
        return None
    return min(integers)


def _gb_to_bytes(value: float) -> int:
    return int(value * GIB_BYTES)


def _growth_projection_next_action(blocker_codes: list[str], review_codes: list[str]) -> str:
    if blocker_codes:
        return "Resolve current autonomy blockers before using growth projection for unattended work."
    if review_codes:
        return "Review current autonomy findings before relying on growth projection for an unattended pilot."
    return "Current budgets are ready; persist at least two future health snapshots before enabling rate-based alerts."


def _external_alert_level(overall_status: str) -> str:
    if overall_status == "blocked":
        return "critical"
    if overall_status == "review":
        return "warning"
    return "none"


def _external_alert_subject(overall_status: str) -> str:
    if overall_status == "blocked":
        return "MediaPipeline autonomy health blocked"
    if overall_status == "review":
        return "MediaPipeline autonomy health needs review"
    return "MediaPipeline autonomy health ready"


def _external_alert_poll_interval(overall_status: str) -> int:
    if overall_status == "blocked":
        return 300
    if overall_status == "review":
        return 900
    return 3600


def _external_alert_dedupe_key(overall_status: str, blocker_codes: list[str], review_codes: list[str]) -> str:
    codes = blocker_codes if blocker_codes else review_codes
    code_text = ",".join(codes[:5]) if codes else "none"
    return f"{overall_status}:{len(blocker_codes)}:{len(review_codes)}:{code_text}"


def _issue_codes(issues: list[Mapping[str, Any]]) -> list[str]:
    codes: list[str] = []
    for issue in issues:
        code = str(issue.get("code") or "").strip()
        if code:
            codes.append(code)
    return codes


def _alert_issue_summary(issue: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "code": str(issue.get("code") or ""),
        "category": str(issue.get("category") or ""),
        "severity": str(issue.get("severity") or ""),
        "message": str(issue.get("message") or ""),
        "age_seconds": issue.get("age_seconds"),
        "next_action": str(issue.get("next_action") or ""),
    }


def _launch_gate_next_action(blockers: list[Mapping[str, Any]], review_items: list[Mapping[str, Any]]) -> str:
    if blockers:
        return str(blockers[0].get("next_action") or "Resolve blocked autonomy health before launching new work.")
    if review_items:
        return "Review non-blocking autonomy health findings before a 7-day unattended run."
    return "Autonomy health is ready for new work under the 7-day pilot gate."


def _launch_gate_recovery_action(
    blockers: list[Mapping[str, Any]],
    review_items: list[Mapping[str, Any]],
) -> dict[str, Any]:
    for issue in [*blockers, *review_items]:
        action = issue.get("recovery_action")
        if isinstance(action, Mapping):
            return dict(action)
    return {}


def _pending_publish_drain_action() -> dict[str, Any]:
    return {
        "schema_version": "desktop_autonomy_recovery_action.v1",
        "kind": "drain_pending_pushes",
        "label": "Drain Parked Outputs",
        "method": "POST",
        "route": "/api/pipeline/start",
        "request": {
            "mode": "drain_pending_pushes",
            "sleep_seconds": 30,
            "show_config": False,
            "show_console": False,
            "schedule_override": "",
        },
        "requires_confirmation": True,
        "frontend_should_autorun": False,
        "mutates_media": True,
        "mutates_runtime_state": True,
        "safe_next_step": "Open Pending Publish, review parked rows, then run the backend drain command only after operator confirmation.",
    }


def _pending_publish_recovery_plan_action(*, row_key: str = "") -> dict[str, Any]:
    request: dict[str, Any] = {"scope": "all"}
    if row_key:
        request = {"scope": "selected", "row_key": row_key}
    return {
        "schema_version": "desktop_autonomy_recovery_action.v1",
        "kind": "pending_publish_recovery_plan",
        "label": "Open Pending Publish Recovery Plan",
        "method": "POST",
        "route": "/api/pending-publish/recovery-plan",
        "request": request,
        "requires_confirmation": False,
        "frontend_should_autorun": False,
        "mutates_media": False,
        "mutates_runtime_state": False,
        "safe_next_step": "Review backend pending-publish recovery evidence before any drain, repair, rerun, or cleanup.",
    }


def _journal_archive_action(path: Path | None) -> dict[str, Any]:
    return {
        "schema_version": "desktop_autonomy_recovery_action.v1",
        "kind": "archive_state_journals",
        "label": "Archive Event Journal",
        "method": "POST",
        "route": "/api/maintenance/archive-state-journals",
        "request": {
            "confirm_archive": True,
            "reason": "launch recovery",
        },
        "requires_confirmation": True,
        "frontend_should_autorun": False,
        "mutates_media": False,
        "mutates_runtime_state": True,
        "evidence_path": str(path or ""),
        "safe_next_step": "Archive only the backend-resolved runtime event journal, then refresh launch preflight.",
    }


def _pending_retry_count(row: Mapping[str, Any]) -> int:
    direct = _safe_int(row.get("retry_count"), row.get("RetryCount"))
    if direct:
        return direct
    manifest_path = _path_or_none(row.get("manifest_path"))
    if manifest_path is None or not manifest_path.exists():
        return 0
    payload = _read_json_mapping(manifest_path)
    return _safe_int(payload.get("retry_count"), payload.get("RetryCount"), payload.get("pending_retry_count"))


def _row_age_seconds(row: Mapping[str, Any], now: datetime) -> int | None:
    text = _first_text(row, "parked_at", "recorded_at", "last_update", "modified_at")
    path = _path_or_none(row.get("manifest_path") or row.get("path"))
    return _age_seconds(text, path, now)


def _age_seconds(text: str, path: Path | None, now: datetime) -> int | None:
    parsed = _parse_datetime(text)
    if parsed is None and path is not None:
        try:
            parsed = datetime.fromtimestamp(path.stat().st_mtime, timezone.utc)
        except OSError:
            return None
    if parsed is None:
        return None
    return max(0, int((now - parsed.astimezone(timezone.utc)).total_seconds()))


def _parse_datetime(value: Any) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _first_text(mapping: Mapping[str, Any], *keys: str) -> str:
    for key in keys:
        value = mapping.get(key)
        text = str(value or "").strip()
        if text:
            return text
    return ""


def _path_or_none(value: Any) -> Path | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return Path(text)
    except TypeError:
        return None


def _safe_int(*values: Any) -> int:
    for value in values:
        try:
            if value in (None, ""):
                continue
            return int(value)
        except (TypeError, ValueError):
            continue
    return 0


def _safe_float(*values: Any) -> float | None:
    for value in values:
        try:
            if value in (None, ""):
                continue
            return float(value)
        except (TypeError, ValueError):
            continue
    return None


def _iter_files(root: Path, pattern: str = "*") -> list[Path]:
    try:
        return sorted(root.glob(pattern), key=lambda item: item.stat().st_mtime, reverse=True)[:AUTONOMY_SCAN_LIMIT]
    except OSError:
        return []


def _directory_size(root: Path | None, *, limit: int = AUTONOMY_SCAN_LIMIT) -> int:
    if root is None or not root.exists() or not root.is_dir():
        return 0
    total = 0
    scanned = 0
    try:
        iterator = root.rglob("*")
        for path in iterator:
            if scanned >= limit:
                break
            if not path.is_file():
                continue
            scanned += 1
            try:
                total += int(path.stat().st_size)
            except OSError:
                continue
    except OSError:
        return total
    return total


def _journal_paths(resolved: ResolvedPaths) -> list[Path | None]:
    return [
        resolved.event_file,
        resolved.completed_manifest_path,
        resolved.queue_snapshot_path,
        resolved.progress_file,
        resolved.log_file,
    ]


def _queue_runnable_count(path: Path | None) -> int:
    if path is None or not path.exists() or not path.is_file():
        return 0
    payload = _read_json_mapping(path)
    for key in ("runnable_count", "RunnableCount"):
        if key in payload:
            return _safe_int(payload.get(key))
    items = payload.get("items")
    if isinstance(items, list):
        return len(items)
    rows = payload.get("rows")
    if isinstance(rows, list):
        return len(rows)
    return 0


def _active_job_definitely_dead(payload: Mapping[str, Any], psutil_module: Any) -> bool:
    pid = payload.get("pid")
    try:
        process = psutil_module.Process(int(pid))
        return not (bool(process.is_running()) and process.status() != psutil_module.STATUS_ZOMBIE)
    except psutil_module.NoSuchProcess:
        return True
    except Exception:
        return False


__all__ = [
    "AUTONOMY_HEALTH_SCHEMA_VERSION",
    "PENDING_REVIEW_SECONDS",
    "PENDING_BLOCK_SECONDS",
    "PENDING_RETRY_BLOCK_COUNT",
    "STATE_FILE_REVIEW_BYTES",
    "STATE_FILE_BLOCK_BYTES",
    "DEFAULT_STORAGE_MIN_FREE_GB",
    "autonomy_health_is_blocked",
    "autonomy_health_payload",
    "load_autonomy_growth_history",
    "record_autonomy_growth_snapshot",
]
