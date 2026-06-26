"""Sample-validation preview and append policy helpers."""

from __future__ import annotations

from collections.abc import Mapping
import json
import os
from typing import TYPE_CHECKING, Any

from mediapipeline.desktop.models import ResolvedPaths
from mediapipeline.desktop.application.sample_validation.evidence import (
    sample_validation_evidence_packet_payload,
    sample_validation_post_run_capture_payload,
)
from mediapipeline.desktop.application.sample_validation.log_payload import (
    SAMPLE_VALIDATION_LOG_SCHEMA,
    SAMPLE_VALIDATION_RECENT_LIMIT,
    SAMPLE_VALIDATION_TAIL_BYTES,
    _dedupe,
    sample_validation_log_path,
    sample_validation_log_payload,
)
from mediapipeline.desktop.application.sample_validation.pilot_plan import (
    SAMPLE_VALIDATION_SAMPLE_CATEGORY_KEYS,
    sample_validation_cutover_gate_payload,
    sample_validation_pilot_plan_payload,
    sample_validation_pilot_runbook_payload,
    sample_validation_sample_set_guide_payload,
)
from mediapipeline.desktop.application.sample_validation.policy_alignment import (
    sample_validation_evidence_gap_payload,
    sample_validation_policy_alignment_payload,
    sample_validation_validation_audit_payload,
)
from mediapipeline.desktop.application.sample_validation.record import (
    SAMPLE_VALIDATION_RECORD_SCHEMA,
    SAMPLE_VALIDATION_REQUEST_MAX_BYTES,
    SAMPLE_VALIDATION_TEXT_MAX_CHARS,
    _clean_text,
    _json_size,
    _normalized_sample_validation_record,
)
from mediapipeline.desktop.application.sample_validation.readiness import sample_validation_append_readiness_payload, sample_validation_readiness_payload
from mediapipeline.desktop.application.sample_validation.reconciliation import (
    sample_validation_current_evidence_payload,
    sample_validation_reconciliation_payload,
)
from mediapipeline.desktop.application.sample_validation.summary import SAMPLE_VALIDATION_CHECK_KEYS, sample_validation_log_summary
from mediapipeline.desktop.application.sample_validation.worksheet import (
    SAMPLE_VALIDATION_WORKSHEET_READ_BYTES,
    SAMPLE_VALIDATION_WORKSHEET_RUN_LIMIT,
    SAMPLE_VALIDATION_WORKSHEET_RUNS_SCHEMA,
    SAMPLE_VALIDATION_WORKSHEET_SAMPLE_LIMIT,
    sample_validation_worksheet_runs_payload,
)

if TYPE_CHECKING:
    from mediapipeline.desktop.application.dto_commands import CommandResult

SAMPLE_VALIDATION_PREVIEW_SCHEMA = "desktop_sample_validation_preview.v1"
SAMPLE_VALIDATION_COMMAND = "sample_validation.append"
SAMPLE_VALIDATION_REFRESH_HINT = "sample_validation"
SAMPLE_VALIDATION_RECORD_MAX_BYTES = 32 * 1024


def _command_result(**kwargs: Any):
    from mediapipeline.desktop.application.dto_commands import CommandResult

    return CommandResult(**kwargs)


def sample_validation_preview(resolved: ResolvedPaths, request: Mapping[str, Any], *, app_version: str) -> dict[str, Any]:
    warnings: list[str] = []
    errors: list[str] = []
    request_size = _json_size(request, errors)
    if request_size > SAMPLE_VALIDATION_REQUEST_MAX_BYTES:
        errors.append(
            f"Sample validation request is too large: {request_size} bytes > {SAMPLE_VALIDATION_REQUEST_MAX_BYTES} bytes."
        )
    record = _normalized_sample_validation_record(resolved, request, app_version=app_version, warnings=warnings, errors=errors)
    record_size = _json_size(record, errors)
    if record_size > SAMPLE_VALIDATION_RECORD_MAX_BYTES:
        errors.append(
            f"Sample validation record is too large: {record_size} bytes > {SAMPLE_VALIDATION_RECORD_MAX_BYTES} bytes."
        )
    current_evidence = sample_validation_current_evidence_payload(resolved, record)
    for artifact_error in current_evidence.get("artifact_errors") or []:
        warnings.append(f"Current backend evidence read problem: {artifact_error}")
    decision = _clean_text(record.get("operator_decision")).casefold()
    current_status = _clean_text(current_evidence.get("status")).casefold()
    current_severity = _clean_text(current_evidence.get("severity")).casefold()
    if decision == "accepted" and (current_status in {"stale", "unknown"} or current_severity == "warning"):
        warnings.append(
            "Accepted sample record does not have fully current backend proof; inspect Queue, Completed, Pending Publish, and Diagnostics before appending."
        )
    append_readiness = sample_validation_append_readiness_payload(record, current_evidence, errors=errors)
    evidence_packet = sample_validation_evidence_packet_payload(record, current_evidence, append_readiness)
    post_run_capture = sample_validation_post_run_capture_payload(record, current_evidence, append_readiness, evidence_packet)
    return {
        "schema_version": SAMPLE_VALIDATION_PREVIEW_SCHEMA,
        "ok": not errors,
        "record_schema": SAMPLE_VALIDATION_RECORD_SCHEMA,
        "log_path": str(sample_validation_log_path(resolved)),
        "record_size_bytes": record_size,
        "request_size_bytes": request_size,
        "record": record,
        "current_evidence": current_evidence,
        "append_readiness": append_readiness,
        "pilot_evidence_packet": evidence_packet,
        "post_run_capture": post_run_capture,
        "warnings": _dedupe(warnings),
        "errors": _dedupe(errors),
        "guardrail": (
            "Preview only. Sample validation records are operator evidence and never mark jobs complete, "
            "clear failures, drain pending publish, rewrite manifests/sidecars, launch work, or mutate media files."
        ),
    }


def append_sample_validation_record(
    resolved: ResolvedPaths,
    request: Mapping[str, Any],
    *,
    app_version: str,
    lock: Any,
) -> CommandResult:
    preview = sample_validation_preview(resolved, request, app_version=app_version)
    if not bool(preview.get("ok")):
            return _command_result(
            command=SAMPLE_VALIDATION_COMMAND,
            ok=False,
            message="Sample validation record was not appended.",
            severity="error",
            errors=list(preview.get("errors") or []),
            warnings=list(preview.get("warnings") or []),
            refresh_hint=SAMPLE_VALIDATION_REFRESH_HINT,
            data={
                "schema_version": SAMPLE_VALIDATION_PREVIEW_SCHEMA,
                "preview": preview,
                "log_path": str(sample_validation_log_path(resolved)),
                "written": False,
            },
        )
    path = sample_validation_log_path(resolved)
    record = dict(preview.get("record") or {})
    line = json.dumps(record, ensure_ascii=False, sort_keys=True, allow_nan=False)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with lock:
            with path.open("a", encoding="utf-8", newline="\n") as handle:
                handle.write(line)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
    except OSError as exc:
        return _command_result(
            command=SAMPLE_VALIDATION_COMMAND,
            ok=False,
            message=f"Sample validation record append failed: {exc}",
            severity="error",
            errors=[str(exc)],
            warnings=list(preview.get("warnings") or []),
            refresh_hint=SAMPLE_VALIDATION_REFRESH_HINT,
            data={"log_path": str(path), "written": False},
        )
    warnings = list(preview.get("warnings") or [])
    return _command_result(
        command=SAMPLE_VALIDATION_COMMAND,
        ok=True,
        message="Sample validation record appended as operator evidence only.",
        severity="warning" if warnings else "info",
        warnings=warnings,
        refresh_hint=SAMPLE_VALIDATION_REFRESH_HINT,
        data={
            "schema_version": SAMPLE_VALIDATION_PREVIEW_SCHEMA,
            "record_id": str(record.get("record_id") or ""),
            "log_path": str(path),
            "record_size_bytes": int(preview.get("record_size_bytes") or 0),
            "current_evidence": preview.get("current_evidence") or {},
            "append_readiness": preview.get("append_readiness") or {},
            "pilot_evidence_packet": preview.get("pilot_evidence_packet") or {},
            "post_run_capture": preview.get("post_run_capture") or {},
            "written": True,
            "guardrail": preview.get("guardrail", ""),
        },
    )

__all__ = [
    "SAMPLE_VALIDATION_PREVIEW_SCHEMA",
    "SAMPLE_VALIDATION_COMMAND",
    "SAMPLE_VALIDATION_REFRESH_HINT",
    "SAMPLE_VALIDATION_RECORD_MAX_BYTES",
    "sample_validation_preview",
    "append_sample_validation_record",
]
