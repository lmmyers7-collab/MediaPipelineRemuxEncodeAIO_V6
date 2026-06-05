from __future__ import annotations

from collections.abc import Mapping
import json
import os
from pathlib import Path
from typing import Any

from ...config_keys import (
    KEY_AUDIO_PASSTHROUGH_PROFILE,
    KEY_DEFERRED_PUBLISH,
    KEY_OUTPUT_CONTAINER,
    KEY_ROUTE_THRESHOLD_MODE,
    KEY_ROUTING_PROFILE,
    KEY_SIZE_GUARD_MODE,
)
from ...models import ResolvedPaths


SAMPLE_VALIDATION_READINESS_SCHEMA = "desktop_sample_validation_readiness.v1"
SAMPLE_VALIDATION_APPEND_READINESS_SCHEMA = "desktop_sample_validation_append_readiness.v1"
SAMPLE_VALIDATION_TEXT_MAX_CHARS = 600
SAMPLE_VALIDATION_ACCEPTANCE_CHECKS = (
    ("queue_route_checked", "Queue route", True, "Compare the selected Queue row source, route, route reason, and blocked state."),
    ("completed_output_checked", "Completed output", True, "Verify the Completed row points at the expected final output file."),
    ("sidecar_manifest_checked", "Sidecar / manifest", True, "Verify sidecar and manifest fields still match the sample source/output."),
    ("size_growth_checked", "Size growth", True, "Compare source/output size and route size policy before trusting the sample."),
    ("diagnostics_checked", "Diagnostics / run logs", True, "Read bounded stdout/stderr/run-log evidence for the same source/output."),
    ("subtitle_checked", "Subtitle behavior", False, "Confirm preferred-language SRT behavior, retained originals, and any manual-review subtitle failures."),
    ("audio_checked", "Audio behavior", False, "Confirm passthrough/transcode/default-language behavior matches saved settings."),
    ("pending_publish_checked", "Pending Publish", False, "If deferred publish parked the output, verify payload, sidecar, manifest, and drain posture."),
)


def sample_validation_readiness_payload(
    resolved: ResolvedPaths,
    *,
    log_exists: bool | None = None,
    log_record_count: int | None = None,
    log_warnings: list[str] | None = None,
    log_errors: list[str] | None = None,
    log_truncated: bool = False,
) -> dict[str, Any]:
    """Summarize whether backend artifacts are present for an operator evidence note.

    This is intentionally read-only. It is not an acceptance rule and it never
    upgrades a job, output, manifest, pending publish row, or failure marker.
    """

    rows = [
        _queue_readiness_row(resolved),
        _completed_readiness_row(resolved),
        _diagnostics_log_readiness_row(resolved),
        _pending_publish_readiness_row(resolved),
        _settings_readiness_row(resolved),
        _validation_log_readiness_row(
            resolved,
            log_exists=log_exists,
            log_record_count=log_record_count,
            log_warnings=log_warnings or [],
            log_errors=log_errors or [],
            log_truncated=log_truncated,
        ),
    ]
    required = [row for row in rows if row.get("required")]
    ready_count = sum(1 for row in required if row.get("status") == "ready")
    review_count = sum(1 for row in rows if row.get("severity") == "warning")
    blocked_count = sum(1 for row in rows if row.get("severity") == "error")
    missing_required = [str(row.get("area") or "") for row in required if row.get("status") != "ready"]
    if blocked_count:
        operator_status = "blocked"
        safe_next_action = "Resolve unreadable validation evidence before recording sample proof."
    elif missing_required:
        operator_status = "not-ready"
        safe_next_action = f"Gather required evidence first: {', '.join(missing_required)}."
    elif review_count:
        operator_status = "review"
        safe_next_action = "Required evidence exists, but review warnings before appending a sample validation record."
    else:
        operator_status = "ready-to-record"
        safe_next_action = "Required evidence is present. Preview the record and confirm it matches the selected real-media sample before append."
    summary_lines = [
        f"Readiness posture: {operator_status}",
        f"Required evidence ready: {ready_count}/{len(required)}",
        f"Warnings: {review_count}; blockers: {blocked_count}",
        f"Safe next action: {safe_next_action}",
        "Boundary: readiness is advisory evidence only and cannot accept, rerun, drain, publish, rewrite manifests, or mutate media.",
    ]
    return {
        "schema_version": SAMPLE_VALIDATION_READINESS_SCHEMA,
        "operator_status": operator_status,
        "ready_to_record": operator_status in {"ready-to-record", "review"},
        "required_ready_count": ready_count,
        "required_count": len(required),
        "warning_count": review_count,
        "blocker_count": blocked_count,
        "missing_required": missing_required,
        "rows": rows,
        "summary_lines": summary_lines,
        "safe_next_action": safe_next_action,
        "guardrail": (
            "Read-only readiness evidence. This does not mark jobs complete, clear failures, drain pending publish, "
            "rewrite manifests/sidecars, launch work, save settings, rename files, or mutate source/output/scratch media."
        ),
    }


def sample_validation_append_readiness_payload(
    record: Mapping[str, Any],
    current_evidence: Mapping[str, Any],
    *,
    errors: list[str] | None = None,
) -> dict[str, Any]:
    """Explain whether the proposed evidence record is ready to append.

    This is advisory only. It does not change append behavior because hold,
    rerun, and fallback records are useful even when a sample is not accepted.
    """

    error_list = list(errors or [])
    decision = _clean_text(record.get("operator_decision")).casefold() or "unknown"
    checks = record.get("checks") if isinstance(record.get("checks"), Mapping) else {}
    rows: list[dict[str, Any]] = []
    required_missing: list[str] = []
    recommended_missing: list[str] = []
    checked_count = 0
    for key, label, required, action in SAMPLE_VALIDATION_ACCEPTANCE_CHECKS:
        checked = bool(checks.get(key))
        if checked:
            checked_count += 1
            status = "checked"
            severity = "info"
            evidence = "Operator marked this check complete."
        else:
            status = "missing-required" if required and decision == "accepted" else "not-checked"
            severity = "warning" if required and decision == "accepted" else "info"
            evidence = "Operator has not marked this check complete."
            if required:
                required_missing.append(label)
            else:
                recommended_missing.append(label)
        rows.append(
            {
                "check": key,
                "label": label,
                "required_for_acceptance": required,
                "status": status,
                "severity": severity,
                "evidence": evidence,
                "safe_next_action": action,
            }
        )

    current_status = _clean_text(current_evidence.get("status")).casefold() or "unknown"
    current_severity = _clean_text(current_evidence.get("severity")).casefold() or "warning"
    current_matches = current_evidence.get("matches") if isinstance(current_evidence.get("matches"), Mapping) else {}
    pending_match = bool(current_matches.get("pending_source_or_output"))
    current_proof_ready = current_status == "current" and current_severity != "warning" and not pending_match
    current_status_label = "checked" if current_proof_ready else "review-current-evidence"
    rows.append(
        {
            "check": "current_backend_evidence",
            "label": "Current backend proof",
            "required_for_acceptance": True,
            "status": current_status_label,
            "severity": "info" if current_proof_ready else "warning",
            "evidence": _clean_text(current_evidence.get("evidence")) or f"Current evidence status is {current_status}.",
            "safe_next_action": _clean_text(current_evidence.get("safe_next_action"))
            or "Compare Queue, Completed, Pending Publish, and Diagnostics before appending.",
        }
    )

    blocker_count = len(error_list)
    warning_count = sum(1 for row in rows if row.get("severity") == "warning")
    if blocker_count:
        operator_status = "blocked"
        safe_next_action = "Fix preview errors before appending any sample-validation evidence record."
    elif decision == "accepted" and required_missing:
        operator_status = "review-before-append"
        safe_next_action = f"Complete required acceptance checks first: {', '.join(required_missing)}."
    elif decision == "accepted" and not current_proof_ready:
        operator_status = "review-before-append"
        safe_next_action = "Current backend proof is not clean enough for an accepted evidence note; review the current-evidence row first."
    elif decision == "accepted":
        operator_status = "ready-to-append-evidence"
        safe_next_action = "Append only after manual Plex playback, subtitle, audio, size, and pending-publish review agrees with this preview."
    else:
        operator_status = "evidence-note"
        safe_next_action = "Append only if you intentionally want a hold/rerun/fallback note for this sample."

    summary_lines = [
        f"Append readiness: {operator_status}",
        f"Manual checks complete: {checked_count}/{len(SAMPLE_VALIDATION_ACCEPTANCE_CHECKS)}; warnings={warning_count}; blockers={blocker_count}",
        f"Required acceptance gaps: {', '.join(required_missing) if required_missing else 'none'}",
        f"Recommended review gaps: {', '.join(recommended_missing) if recommended_missing else 'none'}",
        f"Current backend proof clean: {_yes_no(current_proof_ready)}",
        f"Safe next action: {safe_next_action}",
        "Boundary: append readiness is advisory and cannot accept output, clear failures, drain publish state, launch work, or mutate media.",
    ]
    return {
        "schema_version": SAMPLE_VALIDATION_APPEND_READINESS_SCHEMA,
        "operator_status": operator_status,
        "append_allowed": not blocker_count,
        "accepted_ready": operator_status == "ready-to-append-evidence",
        "manual_checked_count": checked_count,
        "manual_check_count": len(SAMPLE_VALIDATION_ACCEPTANCE_CHECKS),
        "warning_count": warning_count,
        "blocker_count": blocker_count,
        "required_acceptance_gaps": required_missing,
        "recommended_review_gaps": recommended_missing,
        "current_backend_proof_clean": current_proof_ready,
        "rows": rows,
        "summary_lines": summary_lines,
        "safe_next_action": safe_next_action,
        "guardrail": (
            "Read-only append-readiness advice. It does not mark jobs complete, clear failures, drain pending publish, "
            "rewrite manifests/sidecars, launch work, save settings, rename files, or mutate source/output/scratch media."
        ),
    }


def _queue_readiness_row(resolved: ResolvedPaths) -> dict[str, Any]:
    path = resolved.queue_snapshot_path
    if not path:
        return _readiness_row("Queue route evidence", "missing", "Queue snapshot path is not configured.", "Refresh Queue before recording sample evidence.")
    if not Path(path).exists():
        return _readiness_row("Queue route evidence", "missing", f"Queue snapshot not found: {path}", "Refresh Queue and select the sample row before recording evidence.")
    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return _readiness_row("Queue route evidence", "unreadable", f"Queue snapshot could not be read: {exc}", "Repair or refresh Queue Snapshot before recording evidence.", severity="error")
    rows = _payload_rows(payload, "rows", "queue")
    if not rows:
        return _readiness_row("Queue route evidence", "empty", f"Queue snapshot is readable but has no rows: {path}", "Refresh Queue with the sample source visible before recording evidence.")
    route_count = sum(1 for row in rows if _clean_text(row.get("route") or row.get("route_name") or row.get("route_action")))
    evidence = f"{len(rows)} queue row(s); route evidence on {route_count} row(s)."
    status = "ready" if route_count else "review"
    severity = "info" if route_count else "warning"
    next_step = "Compare the selected Queue row source and route reason with Completed output proof."
    if not route_count:
        next_step = "Queue rows exist but route evidence is absent; refresh route planning before accepting the sample."
    return _readiness_row("Queue route evidence", status, evidence, next_step, severity=severity)


def _completed_readiness_row(resolved: ResolvedPaths) -> dict[str, Any]:
    path = resolved.completed_manifest_path
    if not path:
        return _readiness_row("Completed output proof", "missing", "Completed manifest path is not configured.", "Run a sample or inspect Completed after backend processing.")
    if not Path(path).exists():
        return _readiness_row("Completed output proof", "missing", f"Completed manifest not found: {path}", "Run a sample to completion before appending validation evidence.")
    try:
        records, invalid_count = _read_jsonl_records(Path(path), limit=200)
    except OSError as exc:
        return _readiness_row("Completed output proof", "unreadable", f"Completed manifest could not be read: {exc}", "Inspect Completed Manifest permissions/locking before recording evidence.", severity="error")
    if not records:
        severity = "warning" if invalid_count else "info"
        return _readiness_row("Completed output proof", "empty", f"Completed manifest has no parsed rows; invalid rows={invalid_count}.", "Process a sample and verify output/sidecar proof before recording evidence.", severity=severity)
    output_count = sum(1 for record in records if _clean_text(record.get("output_path") or record.get("output_file")))
    sidecar_count = sum(1 for record in records if _clean_text(record.get("sidecar_path") or record.get("sidecar_file")))
    route_count = sum(1 for record in records if _clean_text(record.get("route") or record.get("route_reason") or record.get("route_reason_code")))
    warnings: list[str] = []
    if invalid_count:
        warnings.append(f"{invalid_count} invalid completed row(s)")
    if not output_count:
        warnings.append("no output-path proof")
    evidence = f"{len(records)} completed row(s); outputs={output_count}; sidecars={sidecar_count}; route proof={route_count}."
    if warnings:
        evidence = f"{evidence} Warning(s): {', '.join(warnings)}."
    status = "ready" if output_count and not invalid_count else "review"
    severity = "info" if status == "ready" else "warning"
    return _readiness_row("Completed output proof", status, evidence, "Compare Completed output/sidecar/route/size evidence with the sample source.", severity=severity)


def _diagnostics_log_readiness_row(resolved: ResolvedPaths) -> dict[str, Any]:
    candidates = _run_log_candidates(resolved)
    existing = [path for path in candidates if path.exists()]
    if not existing:
        return _readiness_row("Diagnostics run log proof", "missing", "No run stdout/stderr log was found in known RunLogs locations.", "Run or inspect the sample, then read Last Stderr / Run Logs before recording evidence.")
    error_clues = 0
    warning_clues = 0
    unreadable: list[str] = []
    for path in existing[:4]:
        try:
            text = _read_tail_text(path, 64 * 1024).casefold()
        except OSError as exc:
            unreadable.append(f"{path.name}: {exc}")
            continue
        error_clues += sum(text.count(term) for term in ("error", "failed", "exception", "traceback"))
        warning_clues += text.count("warning")
    if unreadable and not (error_clues or warning_clues):
        return _readiness_row("Diagnostics run log proof", "unreadable", f"Run log read problem(s): {'; '.join(unreadable[:3])}", "Resolve run-log read errors before trusting diagnostics evidence.", severity="error")
    evidence = f"{len(existing)} run log file(s) found; error clues={error_clues}; warning clues={warning_clues}."
    if unreadable:
        evidence = f"{evidence} Unreadable: {'; '.join(unreadable[:3])}."
    severity = "warning" if error_clues or unreadable else "info"
    status = "review" if error_clues or unreadable else "ready"
    next_step = "Read Last Stderr and Run Logs for the selected sample before accepting validation evidence."
    return _readiness_row("Diagnostics run log proof", status, evidence, next_step, severity=severity)


def _pending_publish_readiness_row(resolved: ResolvedPaths) -> dict[str, Any]:
    path = resolved.pending_push_path
    if not path:
        return _readiness_row("Pending Publish posture", "missing", "Pending publish path is not configured.", "If deferred publish is enabled, confirm pending-publish state from Settings and Diagnostics.", required=False)
    pending_path = Path(path)
    if not pending_path.exists():
        return _readiness_row("Pending Publish posture", "ready", f"Pending publish folder not present: {pending_path}", "If the sample should be deferred, verify why no parked payload exists.", required=False)
    counts = _pending_publish_file_counts(pending_path)
    evidence = (
        f"Pending folder exists; manifests={counts['manifest_count']}; json sidecars={counts['json_count']}; "
        f"payload-like files={counts['payload_count']}."
    )
    if counts["truncated"]:
        evidence = f"{evidence} Scan capped after {counts['scanned_count']} file(s)."
    severity = "warning" if counts["manifest_count"] or counts["payload_count"] or counts["truncated"] else "info"
    status = "review" if severity == "warning" else "ready"
    next_step = "If sample output was parked, compare Pending Publish row, recovery dry-run, and drain summary before recording evidence."
    return _readiness_row("Pending Publish posture", status, evidence, next_step, severity=severity, required=False)


def _settings_readiness_row(resolved: ResolvedPaths) -> dict[str, Any]:
    config = resolved.config_data if isinstance(resolved.config_data, Mapping) else {}
    if not config:
        return _readiness_row("Saved media policy posture", "missing", "No saved config data is loaded.", "Open Settings and confirm routing, subtitle, audio, size, and pending-publish posture before recording evidence.")
    keys = (
        KEY_ROUTING_PROFILE,
        KEY_ROUTE_THRESHOLD_MODE,
        KEY_SIZE_GUARD_MODE,
        KEY_OUTPUT_CONTAINER,
        KEY_DEFERRED_PUBLISH,
        KEY_AUDIO_PASSTHROUGH_PROFILE,
    )
    present = {key: _clean_text(config.get(key)) for key in keys if _clean_text(config.get(key))}
    evidence = "; ".join(f"{key}={value}" for key, value in present.items()) or "Config loaded without common media policy keys."
    status = "ready" if len(present) >= 3 else "review"
    severity = "info" if status == "ready" else "warning"
    return _readiness_row("Saved media policy posture", status, evidence, "Compare Settings posture with the sample route/audio/subtitle/size result.", severity=severity, required=False)


def _validation_log_readiness_row(
    resolved: ResolvedPaths,
    *,
    log_exists: bool | None,
    log_record_count: int | None,
    log_warnings: list[str],
    log_errors: list[str],
    log_truncated: bool,
) -> dict[str, Any]:
    path = _sample_validation_log_path(resolved)
    exists = path.exists() if log_exists is None else log_exists
    count = 0 if log_record_count is None else int(log_record_count)
    if log_errors:
        return _readiness_row("Validation history", "unreadable", f"Validation log error(s): {'; '.join(log_errors[:3])}", "Fix validation-log read errors before trusting historical sample evidence.", severity="error", required=False)
    if not exists:
        return _readiness_row("Validation history", "not-started", f"No sample validation log exists yet: {path}", "Append evidence only after comparing current Queue/Completed/Pending/Diagnostics.", required=False)
    notes: list[str] = [f"{count} recent validation record(s) loaded."]
    if log_warnings:
        notes.append(f"Warnings: {'; '.join(log_warnings[:3])}.")
    if log_truncated:
        notes.append("Log is larger than read cap; only tail records were evaluated.")
    status = "review" if log_warnings or log_truncated else "ready"
    severity = "warning" if status == "review" else "info"
    return _readiness_row("Validation history", status, " ".join(notes), "Compare historical records with current evidence; old accepted records are not current proof.", severity=severity, required=False)


def _readiness_row(
    area: str,
    status: str,
    evidence: str,
    next_step: str,
    *,
    severity: str = "info",
    required: bool = True,
) -> dict[str, Any]:
    return {
        "area": area,
        "status": status,
        "severity": severity,
        "required": required,
        "evidence": evidence,
        "next_step": next_step,
    }


def _sample_validation_log_path(resolved: ResolvedPaths) -> Path:
    state_root = resolved.state_root or (Path(resolved.app_root) / "State")
    return Path(state_root) / "Validation" / "sample_validation_log.jsonl"


def _payload_rows(payload: Any, *keys: str) -> list[Mapping[str, Any]]:
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, Mapping)]
    if not isinstance(payload, Mapping):
        return []
    for key in keys:
        value = payload.get(key)
        if isinstance(value, list):
            return [item for item in value if isinstance(item, Mapping)]
    return []


def _read_jsonl_records(path: Path, *, limit: int) -> tuple[list[dict[str, Any]], int]:
    records: list[dict[str, Any]] = []
    invalid_count = 0
    with path.open("r", encoding="utf-8", errors="replace") as handle:
        for line in handle:
            text = line.strip()
            if not text:
                continue
            try:
                payload = json.loads(text)
            except json.JSONDecodeError:
                invalid_count += 1
                continue
            if isinstance(payload, dict):
                records.append(payload)
            else:
                invalid_count += 1
    return records[-limit:], invalid_count


def _run_log_candidates(resolved: ResolvedPaths) -> list[Path]:
    roots = [
        Path(resolved.local_base) if resolved.local_base else None,
        Path(resolved.app_root) if resolved.app_root else None,
        Path(resolved.workspace_root) if resolved.workspace_root else None,
        Path(resolved.state_root) if resolved.state_root else None,
    ]
    names = ("run.stderr.log", "run.stdout.log", "last_stderr.log", "last_stdout.log")
    candidates: list[Path] = []
    seen: set[str] = set()
    for root in roots:
        if root is None:
            continue
        for base in (root / "RunLogs", root / "apps" / "desktop" / "runlogs", root / "State" / "RunLogs"):
            for name in names:
                path = base / name
                key = os.path.normcase(os.path.abspath(path))
                if key not in seen:
                    candidates.append(path)
                    seen.add(key)
    return candidates


def _pending_publish_file_counts(root: Path, *, limit: int = 500) -> dict[str, Any]:
    manifest_count = 0
    json_count = 0
    payload_count = 0
    scanned_count = 0
    truncated = False
    try:
        iterator = root.rglob("*")
        for item in iterator:
            if not item.is_file():
                continue
            scanned_count += 1
            if scanned_count > limit:
                truncated = True
                break
            name = item.name.casefold()
            suffix = item.suffix.casefold()
            if name.endswith(".manifest.json") or name.endswith(".manifest.jsonl"):
                manifest_count += 1
            elif suffix in {".json", ".jsonl"}:
                json_count += 1
            else:
                payload_count += 1
    except OSError:
        truncated = True
    return {
        "manifest_count": manifest_count,
        "json_count": json_count,
        "payload_count": payload_count,
        "scanned_count": scanned_count,
        "truncated": truncated,
    }


def _read_tail_text(path: Path, max_bytes: int) -> str:
    with path.open("rb") as handle:
        handle.seek(0, 2)
        size = handle.tell()
        handle.seek(max(0, size - max_bytes))
        return handle.read(max_bytes).decode("utf-8", errors="replace")


def _clean_text(value: Any, *, max_chars: int = SAMPLE_VALIDATION_TEXT_MAX_CHARS) -> str:
    text = "" if value is None else str(value)
    text = " ".join(text.replace("\r", " ").replace("\n", " ").split())
    return text[:max_chars]


def _yes_no(value: Any) -> str:
    return "yes" if bool(value) else "no"
