from __future__ import annotations

from typing import Any, Mapping

from .pending_results import PENDING_DRAIN_CONFIDENCE_SCHEMA_VERSION, _json_safe
from .pending_rows import (
    int_value,
    pending_publish_row_diagnostic_status,
    pending_publish_row_is_recovery_blocker,
    pending_publish_row_issue_summary,
    pending_publish_row_ready_to_drain,
)

def _pending_evidence_class(row: Mapping[str, Any]) -> str:
    recommendation = str(row.get("drain_recommendation") or "").casefold()
    severity = str(row.get("diagnostic_severity") or "").casefold()
    status = str(row.get("diagnostic_status") or "").casefold()
    state = str(row.get("state") or "").casefold()
    if recommendation == "do_not_drain":
        return "do-not-drain"
    if severity == "error":
        return "diagnostic-error"
    if row.get("local_exists") is False or status == "missing_payload":
        return "missing-payload"
    if status in {"invalid_manifest", "unreadable_manifest"} or state in {"invalid_manifest", "unreadable_manifest", "invalid_contract", "unreadable"}:
        return "manifest-invalid"
    if state == "orphan_payload" or status == "orphan_payload":
        return "orphan-payload"
    if int_value(row.get("missing_sidecar_count")) > 0 or status == "missing_sidecar":
        return "missing-sidecar"
    if severity == "warning" or recommendation == "review_before_drain" or row.get("ready_to_drain") is False:
        return "review"
    return "ready-evidence"


def _pending_evidence_rank(row: Mapping[str, Any]) -> int:
    ranks = {
        "do-not-drain": 0,
        "diagnostic-error": 1,
        "missing-payload": 2,
        "manifest-invalid": 3,
        "orphan-payload": 4,
        "missing-sidecar": 5,
        "review": 6,
        "ready-evidence": 7,
    }
    return ranks.get(_pending_evidence_class(row), 99)


def _pending_evidence_rows(rows: list[dict[str, Any]], *, include_ready: bool = False) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for index, row in enumerate(rows):
        evidence_class = _pending_evidence_class(row)
        if include_ready or evidence_class != "ready-evidence":
            entries.append({"row": row, "index": index, "evidenceClass": evidence_class})
    return sorted(entries, key=lambda entry: (_pending_evidence_rank(entry["row"]), entry["index"]))


def _pending_evidence_status(payload: Mapping[str, Any], rows: list[dict[str, Any]]) -> str:
    if payload.get("error"):
        return "Diagnostics first"
    if payload.get("exists") is False:
        return "No pending root"
    if not rows:
        return "No parked rows"
    evidence_rows = _pending_evidence_rows(rows)
    if any(entry["evidenceClass"] in {"do-not-drain", "diagnostic-error", "missing-payload", "manifest-invalid"} for entry in evidence_rows):
        return "Blocked evidence"
    if evidence_rows:
        return "Review evidence"
    return "No blockers"


def _pending_row_has_health_issue(row: Mapping[str, Any]) -> bool:
    return bool(
        row.get("error")
        or row.get("local_exists") is False
        or int_value(row.get("missing_sidecar_count")) > 0
        or str(row.get("diagnostic_severity") or "").casefold() in {"warning", "error", "critical"}
        or str(row.get("drain_recommendation") or "").casefold() in {"do_not_drain", "review_before_drain"}
    )


def _pending_validation_status(payload: Mapping[str, Any], rows: list[dict[str, Any]]) -> str:
    if payload.get("error"):
        return "Unavailable"
    if payload.get("exists") is False:
        return "No root"
    if not rows:
        return "Empty"
    do_not_drain = [row for row in rows if str(row.get("drain_recommendation") or "").casefold() == "do_not_drain"]
    severe = [row for row in rows if str(row.get("diagnostic_severity") or "").casefold() == "error"]
    invalid = [row for row in rows if str(row.get("state") or "").casefold() in {"invalid_manifest", "unreadable_manifest"}]
    missing_payload = [row for row in rows if row.get("local_exists") is False]
    missing_sidecar = [row for row in rows if int_value(row.get("missing_sidecar_count")) > 0]
    if (
        do_not_drain
        or severe
        or invalid
        or missing_payload
        or missing_sidecar
        or int_value(payload.get("health_count")) > 0
        or int_value(payload.get("missing_local_count")) > 0
    ):
        return "Do not drain"
    warnings = [item for item in payload.get("warnings") or [] if item]
    if warnings or int_value(payload.get("issue_count")) > 0 or any(_pending_row_has_health_issue(row) for row in rows):
        return "Review"
    return "Ready"


def _pending_drain_summary_payload(payload: Mapping[str, Any]) -> Mapping[str, Any]:
    summary = payload.get("drain_summary")
    return summary if isinstance(summary, Mapping) else {}


def _pending_drain_summary_status(payload: Mapping[str, Any]) -> str:
    summary = _pending_drain_summary_payload(payload)
    if summary.get("read_error"):
        return "Unreadable summary"
    if summary.get("exists") is False:
        return "No summary"
    if not summary.get("started_at") and not summary.get("completed_at"):
        return "No summary"
    if summary.get("deferred"):
        return "Deferred"
    if summary.get("stopped"):
        return "Stopped"
    if int_value(summary.get("error_count")) > 0:
        return "Review drain"
    if int_value(summary.get("succeeded_count")) > 0 or int_value(summary.get("already_published_count")) > 0:
        return "Last drain complete"
    if int_value(summary.get("attempted_count")) == 0:
        return "No attempts"
    return "Last drain recorded"


def _pending_drain_summary_issue_level(summary: Mapping[str, Any]) -> str:
    if summary.get("read_error"):
        return "blocked"
    if summary.get("exists") is False or (not summary.get("started_at") and not summary.get("completed_at")):
        return "none"
    if summary.get("stopped") or int_value(summary.get("error_count")) > 0:
        return "blocked"
    if summary.get("deferred") or int_value(summary.get("skipped_count")) > 0 or int_value(summary.get("remaining_count")) > 0:
        return "review"
    return "ok"


def _pending_drain_confidence_status(rows: list[dict[str, Any]]) -> str:
    if any(row.get("confidence") == "blocked" for row in rows):
        return "Do not drain"
    if any(row.get("confidence") == "review" for row in rows):
        return "Review first"
    if any(row.get("confidence") == "unknown" for row in rows):
        return "Evidence incomplete"
    return "Ready-looking" if rows else "Not evaluated"


def _pending_drain_confidence_counts(rows: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        key = str(row.get("confidence") or "unknown")
        counts[key] = counts.get(key, 0) + 1
    return dict(sorted(counts.items()))


def pending_publish_drain_confidence_payload(payload: Mapping[str, Any], rows: list[dict[str, Any]]) -> dict[str, Any]:
    evidence_rows = _pending_evidence_rows(rows)
    blocking_evidence = [entry for entry in evidence_rows if entry["evidenceClass"] in {"do-not-drain", "diagnostic-error", "missing-payload", "manifest-invalid"}]
    review_evidence = [entry for entry in evidence_rows if entry["evidenceClass"] not in {"do-not-drain", "diagnostic-error", "missing-payload", "manifest-invalid"}]
    summary = _pending_drain_summary_payload(payload)
    rows_out: list[dict[str, Any]] = []

    def add(check: str, confidence: str, evidence: str, action: str) -> None:
        rows_out.append({
            "check": check,
            "confidence": confidence,
            "evidence": evidence,
            "action": action,
            "evidence_authority": "backend",
        })

    if payload.get("error"):
        add(
            "Pending scan",
            "blocked",
            f"scan unavailable: {payload.get('error')}",
            "Open Diagnostics > Pending Publish, Run Logs, and Last Stderr before any drain attempt.",
        )
    else:
        exists = payload.get("exists")
        add(
            "Current parked rows",
            "unknown" if exists is False else "ready" if not rows else "blocked" if blocking_evidence else "review" if review_evidence else "ready",
            f"root={'missing' if exists is False else 'available'}; rows={payload.get('count') or len(rows) or 0}; ready={payload.get('ready_count') or 0}; issues={payload.get('issue_count') or 0}",
            "No pending root exists. Confirm Completed and Run Logs before rerun."
            if exists is False
            else "No parked outputs are waiting. Do not reprocess solely because Pending Publish is empty."
            if not rows
            else "Review row-level evidence below before pressing Publish Parked Outputs.",
        )
        add(
            "Blocker evidence",
            "blocked" if blocking_evidence else "review" if review_evidence else "ready",
            f"blocking={len(blocking_evidence)}; review={len(review_evidence)}; evidence status={_pending_evidence_status(payload, rows)}",
            "Do not drain. Select the highest-risk evidence row and inspect backend-selected targets or build a recovery dry-run plan."
            if blocking_evidence
            else "Review warning/orphan/sidecar rows before drain."
            if review_evidence
            else "No loaded row exposes drain-blocking evidence.",
        )
        validation = _pending_validation_status(payload, rows)
        add(
            "Validation checklist",
            "blocked" if validation == "Do not drain" else "review" if validation == "Review" else "ready",
            f"validation={validation}; health={payload.get('health_count') or 0}; missing payloads={payload.get('missing_local_count') or 0}; missing sidecars={payload.get('missing_sidecar_count') or 0}",
            "Use the Real-media Validation Checklist as the page-level pre-drain gate; backend drain validation remains authoritative.",
        )
        summary_level = _pending_drain_summary_issue_level(summary)
        add(
            "Durable drain summary",
            "blocked" if summary_level == "blocked" else "review" if summary_level == "review" else "ready" if summary_level == "ok" else "unknown",
            f"status={_pending_drain_summary_status(payload)}; attempted={summary.get('attempted_count') or 0}; errors={summary.get('error_count') or 0}; remaining={summary.get('remaining_count') or 0}",
            "Treat the durable summary as last-attempt evidence; the current pending rows remain the source of truth for what is still parked.",
        )

    counts = _pending_drain_confidence_counts(rows_out)
    return {
        "schema_version": PENDING_DRAIN_CONFIDENCE_SCHEMA_VERSION,
        "evidence_authority": "backend",
        "render_contract": "pendingPublishView.confidence.js",
        "render_complete": False,
        "status": _pending_drain_confidence_status(rows_out),
        "counts": counts,
        "rows": _json_safe(rows_out),
        "summary_lines": [
            "Pending Publish backend drain confidence:",
            f"Rows: {len(rows_out)}; ready={counts.get('ready', 0)}; review={counts.get('review', 0)}; blocked={counts.get('blocked', 0)}; unknown={counts.get('unknown', 0)}.",
            "Backend rows cover parked-row, blocker, validation, and durable-summary evidence; WebView still adds display-scope, command-history, recovery-plan, runtime-event, and selection context.",
            "Mutation guardrail: this DTO is read-only and cannot drain, repair, rewrite, move, delete, publish, or bypass backend validation.",
        ],
        "boundary": "read_only_no_media_mutation",
    }


__all__ = [
    "pending_publish_drain_confidence_payload",
]
