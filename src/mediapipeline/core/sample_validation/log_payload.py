from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from mediapipeline.core.paths.contracts import ResolvedPaths
from .pilot_plan import (
    sample_validation_cutover_gate_payload,
    sample_validation_pilot_plan_payload,
    sample_validation_pilot_runbook_payload,
    sample_validation_sample_set_guide_payload,
)
from .policy_alignment import (
    sample_validation_evidence_gap_payload,
    sample_validation_policy_alignment_payload,
    sample_validation_validation_audit_payload,
)
from .readiness import sample_validation_readiness_payload
from .reconciliation import sample_validation_reconciliation_payload
from .record import SAMPLE_VALIDATION_RECORD_SCHEMA
from .summary import sample_validation_log_summary
from .worksheet import sample_validation_worksheet_runs_payload


SAMPLE_VALIDATION_LOG_SCHEMA = "desktop_sample_validation_log.v1"
SAMPLE_VALIDATION_RECENT_LIMIT = 50
SAMPLE_VALIDATION_TAIL_BYTES = 512 * 1024


def sample_validation_log_path(resolved: ResolvedPaths) -> Path:
    state_root = resolved.state_root or (Path(resolved.app_root) / "State")
    return Path(state_root) / "Validation" / "sample_validation_log.jsonl"


def sample_validation_log_payload(resolved: ResolvedPaths, *, limit: int = 20) -> dict[str, Any]:
    path = sample_validation_log_path(resolved)
    normalized_limit = max(1, min(SAMPLE_VALIDATION_RECENT_LIMIT, int(limit or 20)))
    worksheet_runs = sample_validation_worksheet_runs_payload(resolved)
    if not path.exists():
        warnings = ["No sample validation log exists yet."]
        readiness = sample_validation_readiness_payload(resolved, log_exists=False, log_record_count=0)
        reconciliation = sample_validation_reconciliation_payload(resolved, [])
        pilot_plan = sample_validation_pilot_plan_payload(readiness, reconciliation)
        cutover_gate = sample_validation_cutover_gate_payload(
            readiness,
            reconciliation,
            [],
            worksheet_runs,
            pilot_plan,
        )
        sample_set_guide = sample_validation_sample_set_guide_payload(
            [],
            worksheet_runs,
            cutover_gate,
            readiness,
            reconciliation,
            pilot_plan,
        )
        evidence_gap = sample_validation_evidence_gap_payload(
            readiness,
            reconciliation,
            worksheet_runs,
            pilot_plan,
            cutover_gate,
            sample_set_guide,
        )
        pilot_runbook = sample_validation_pilot_runbook_payload(
            readiness,
            reconciliation,
            worksheet_runs,
            pilot_plan,
            cutover_gate,
            sample_set_guide,
            evidence_gap,
        )
        policy_alignment = sample_validation_policy_alignment_payload(resolved)
        validation_audit = sample_validation_validation_audit_payload(
            readiness,
            reconciliation,
            worksheet_runs,
            pilot_plan,
            cutover_gate,
            sample_set_guide,
            evidence_gap,
            pilot_runbook,
            policy_alignment,
        )
        return {
            "schema_version": SAMPLE_VALIDATION_LOG_SCHEMA,
            "ok": True,
            "exists": False,
            "log_path": str(path),
            "limit": normalized_limit,
            "records": [],
            "record_count": 0,
            "warnings": warnings,
            "errors": [],
            "summary": sample_validation_log_summary([], warnings=warnings, errors=[], exists=False, truncated=False),
            "readiness": readiness,
            "reconciliation": reconciliation,
            "worksheet_runs": worksheet_runs,
            "pilot_plan": pilot_plan,
            "cutover_gate": cutover_gate,
            "sample_set_guide": sample_set_guide,
            "evidence_gap_summary": evidence_gap,
            "pilot_runbook": pilot_runbook,
            "policy_alignment": policy_alignment,
            "validation_audit": validation_audit,
            "guardrail": _sample_validation_read_guardrail(),
        }
    try:
        raw = _read_tail_text(path, SAMPLE_VALIDATION_TAIL_BYTES)
    except OSError as exc:
        errors = [f"Could not read sample validation log: {exc}"]
        readiness = sample_validation_readiness_payload(resolved, log_exists=True, log_record_count=0, log_errors=errors)
        reconciliation = sample_validation_reconciliation_payload(resolved, [], artifact_errors=errors)
        pilot_plan = sample_validation_pilot_plan_payload(readiness, reconciliation)
        cutover_gate = sample_validation_cutover_gate_payload(
            readiness,
            reconciliation,
            [],
            worksheet_runs,
            pilot_plan,
        )
        sample_set_guide = sample_validation_sample_set_guide_payload(
            [],
            worksheet_runs,
            cutover_gate,
            readiness,
            reconciliation,
            pilot_plan,
        )
        evidence_gap = sample_validation_evidence_gap_payload(
            readiness,
            reconciliation,
            worksheet_runs,
            pilot_plan,
            cutover_gate,
            sample_set_guide,
        )
        pilot_runbook = sample_validation_pilot_runbook_payload(
            readiness,
            reconciliation,
            worksheet_runs,
            pilot_plan,
            cutover_gate,
            sample_set_guide,
            evidence_gap,
        )
        policy_alignment = sample_validation_policy_alignment_payload(resolved)
        validation_audit = sample_validation_validation_audit_payload(
            readiness,
            reconciliation,
            worksheet_runs,
            pilot_plan,
            cutover_gate,
            sample_set_guide,
            evidence_gap,
            pilot_runbook,
            policy_alignment,
        )
        return {
            "schema_version": SAMPLE_VALIDATION_LOG_SCHEMA,
            "ok": False,
            "exists": True,
            "log_path": str(path),
            "limit": normalized_limit,
            "records": [],
            "warnings": [],
            "record_count": 0,
            "errors": errors,
            "summary": sample_validation_log_summary([], warnings=[], errors=errors, exists=True, truncated=False),
            "readiness": readiness,
            "reconciliation": reconciliation,
            "worksheet_runs": worksheet_runs,
            "pilot_plan": pilot_plan,
            "cutover_gate": cutover_gate,
            "sample_set_guide": sample_set_guide,
            "evidence_gap_summary": evidence_gap,
            "pilot_runbook": pilot_runbook,
            "policy_alignment": policy_alignment,
            "validation_audit": validation_audit,
            "guardrail": _sample_validation_read_guardrail(),
        }
    records: list[dict[str, Any]] = []
    invalid_count = 0
    for line in raw.splitlines():
        text = line.strip()
        if not text:
            continue
        try:
            payload = json.loads(text)
        except json.JSONDecodeError:
            invalid_count += 1
            continue
        if isinstance(payload, dict) and payload.get("schema") == SAMPLE_VALIDATION_RECORD_SCHEMA:
            records.append(payload)
        else:
            invalid_count += 1
    records = list(reversed(records[-normalized_limit:]))
    warnings = [f"Skipped {invalid_count} invalid sample validation record(s)."] if invalid_count else []
    try:
        size_bytes = int(path.stat().st_size)
    except OSError:
        size_bytes = 0
    truncated = size_bytes > SAMPLE_VALIDATION_TAIL_BYTES
    readiness = sample_validation_readiness_payload(
        resolved,
        log_exists=True,
        log_record_count=len(records),
        log_warnings=warnings,
        log_truncated=truncated,
    )
    reconciliation = sample_validation_reconciliation_payload(resolved, records)
    pilot_plan = sample_validation_pilot_plan_payload(readiness, reconciliation)
    cutover_gate = sample_validation_cutover_gate_payload(
        readiness,
        reconciliation,
        records,
        worksheet_runs,
        pilot_plan,
    )
    sample_set_guide = sample_validation_sample_set_guide_payload(
        records,
        worksheet_runs,
        cutover_gate,
        readiness,
        reconciliation,
        pilot_plan,
    )
    evidence_gap = sample_validation_evidence_gap_payload(
        readiness,
        reconciliation,
        worksheet_runs,
        pilot_plan,
        cutover_gate,
        sample_set_guide,
    )
    pilot_runbook = sample_validation_pilot_runbook_payload(
        readiness,
        reconciliation,
        worksheet_runs,
        pilot_plan,
        cutover_gate,
        sample_set_guide,
        evidence_gap,
    )
    policy_alignment = sample_validation_policy_alignment_payload(resolved)
    validation_audit = sample_validation_validation_audit_payload(
        readiness,
        reconciliation,
        worksheet_runs,
        pilot_plan,
        cutover_gate,
        sample_set_guide,
        evidence_gap,
        pilot_runbook,
        policy_alignment,
    )
    return {
        "schema_version": SAMPLE_VALIDATION_LOG_SCHEMA,
        "ok": True,
        "exists": True,
        "log_path": str(path),
        "size_bytes": size_bytes,
        "limit": normalized_limit,
        "records": records,
        "record_count": len(records),
        "tail_bytes": SAMPLE_VALIDATION_TAIL_BYTES,
        "truncated": truncated,
        "warnings": warnings,
        "errors": [],
        "summary": sample_validation_log_summary(records, warnings=warnings, errors=[], exists=True, truncated=truncated),
        "readiness": readiness,
        "reconciliation": reconciliation,
        "worksheet_runs": worksheet_runs,
        "pilot_plan": pilot_plan,
        "cutover_gate": cutover_gate,
        "sample_set_guide": sample_set_guide,
        "evidence_gap_summary": evidence_gap,
        "pilot_runbook": pilot_runbook,
        "policy_alignment": policy_alignment,
        "validation_audit": validation_audit,
        "guardrail": _sample_validation_read_guardrail(),
    }


def _read_tail_text(path: Path, max_bytes: int) -> str:
    size = path.stat().st_size
    with path.open("rb") as handle:
        if size > max_bytes:
            handle.seek(-max_bytes, os.SEEK_END)
        return handle.read(max_bytes).decode("utf-8", errors="replace")


def _sample_validation_read_guardrail() -> str:
    return (
        "Read-only sample validation history. Records are operator evidence only and do not change queue, "
        "completed manifests, sidecars, pending publish, failures, launch readiness, or media files."
    )


def _dedupe(items: list[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for item in items:
        text = str(item or "").strip()
        if text and text not in seen:
            result.append(text)
            seen.add(text)
    return result
