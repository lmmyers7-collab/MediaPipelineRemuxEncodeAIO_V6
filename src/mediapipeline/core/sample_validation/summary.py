from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .evidence import SAMPLE_VALIDATION_EVIDENCE_KEYS, _record_evidence_list


SAMPLE_VALIDATION_SUMMARY_SCHEMA = "desktop_sample_validation_summary.v1"
SAMPLE_VALIDATION_TEXT_MAX_CHARS = 600
SAMPLE_VALIDATION_CHECK_KEYS = (
    "queue_route_checked",
    "ffmpeg_log_checked",
    "subtitle_checked",
    "audio_checked",
    "completed_output_checked",
    "sidecar_manifest_checked",
    "size_growth_checked",
    "pending_publish_checked",
    "diagnostics_checked",
)


def sample_validation_log_summary(
    records: list[Mapping[str, Any]],
    *,
    warnings: list[str],
    errors: list[str],
    exists: bool,
    truncated: bool,
) -> dict[str, Any]:
    decision_counts = _count_values(records, "operator_decision")
    proof_counts = _count_values(records, "proof_strength")
    category_counts = _count_values(records, "sample_category")
    checked_counts = {
        key: sum(1 for record in records if bool((record.get("checks") if isinstance(record.get("checks"), Mapping) else {}).get(key)))
        for key in SAMPLE_VALIDATION_CHECK_KEYS
    }
    evidence_counts = {
        key: sum(len(value) for record in records for value in [_record_evidence_list(record, key)])
        for key in SAMPLE_VALIDATION_EVIDENCE_KEYS
    }
    latest = dict(records[0]) if records else {}
    latest_summary = {
        "record_id": _clean_text(latest.get("record_id")),
        "created_at": _clean_text(latest.get("created_at")),
        "operator_decision": _clean_text(latest.get("operator_decision")),
        "proof_strength": _clean_text(latest.get("proof_strength")),
        "sample_category": _clean_text(latest.get("sample_category")),
        "sample_label": _clean_text(latest.get("sample_label")),
        "source_path": _clean_text(latest.get("source_path")),
        "output_path": _clean_text(latest.get("output_path")),
    }

    if errors:
        operator_status = "blocked"
        safe_next_action = "Read the log error and Diagnostics State Artifact Summary before trusting sample-validation evidence."
    elif not exists:
        operator_status = "not-started"
        safe_next_action = "Run a small known sample, compare Queue/Completed/Pending/Diagnostics evidence, then preview an evidence record."
    elif warnings or truncated:
        operator_status = "review"
        safe_next_action = "Review skipped/truncated log evidence before using old sample records as current proof."
    elif not records:
        operator_status = "empty"
        safe_next_action = "No parsed sample records are loaded; preview a record only after real-media evidence is visible."
    elif (
        decision_counts.get("hold_review", 0)
        or decision_counts.get("manual_review", 0)
        or decision_counts.get("rerun_backend", 0)
    ):
        operator_status = "review"
        safe_next_action = "Recent sample history contains review or rerun decisions; compare latest record with current Queue, Completed, Pending Publish, and Diagnostics."
    else:
        operator_status = "evidence-present"
        safe_next_action = "Accepted sample evidence exists; still compare it with current route/output/pending/diagnostics state before daily-driver trust."

    return {
        "schema_version": SAMPLE_VALIDATION_SUMMARY_SCHEMA,
        "operator_status": operator_status,
        "record_count": len(records),
        "decision_counts": decision_counts,
        "proof_strength_counts": proof_counts,
        "sample_category_counts": category_counts,
        "checked_counts": checked_counts,
        "evidence_counts": evidence_counts,
        "latest": latest_summary,
        "safe_next_action": safe_next_action,
        "guardrail": _sample_validation_read_guardrail(),
    }


def _clean_text(value: Any, *, max_chars: int = SAMPLE_VALIDATION_TEXT_MAX_CHARS) -> str:
    text = str(value or "").replace("\x00", "").strip()
    return text[:max_chars]


def _count_values(records: list[Mapping[str, Any]], key: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for record in records:
        value = _clean_text(record.get(key)).casefold() or "unknown"
        counts[value] = counts.get(value, 0) + 1
    return counts


def _sample_validation_read_guardrail() -> str:
    return (
        "Read-only sample validation history. Records are operator evidence only and do not change queue, "
        "completed manifests, sidecars, pending publish, failures, launch readiness, or media files."
    )
