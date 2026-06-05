from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from ...config_keys import KEY_DEFERRED_PUBLISH
from ...models import ResolvedPaths
from ..settings_risk_policy import build_media_policy_readiness
from .pilot_plan import SAMPLE_VALIDATION_SAMPLE_SET_CATEGORIES


SAMPLE_VALIDATION_POLICY_ALIGNMENT_SCHEMA = "desktop_real_media_policy_alignment.v1"
SAMPLE_VALIDATION_EVIDENCE_GAP_SCHEMA = "desktop_real_media_evidence_gap.v1"
SAMPLE_VALIDATION_AUDIT_SCHEMA = "desktop_real_media_validation_audit.v1"
SAMPLE_VALIDATION_TEXT_MAX_CHARS = 600


def sample_validation_evidence_gap_payload(
    readiness: Mapping[str, Any],
    reconciliation: Mapping[str, Any],
    worksheet_runs: Mapping[str, Any],
    pilot_plan: Mapping[str, Any],
    cutover_gate: Mapping[str, Any],
    sample_set_guide: Mapping[str, Any],
) -> dict[str, Any]:
    """Summarize what proof is still missing for a trustworthy pilot run.

    This is a read-only checklist over existing sample-validation payloads. It
    deliberately does not probe media files, repair records, launch work,
    publish/drain, or promote evidence into acceptance state.
    """

    def normalize_status(value: Any) -> str:
        raw = _clean_text(value).casefold()
        if raw in {"ready", "current", "current-evidence", "sample-set-ready", "ready-for-operator-trial", "evidence-present", "ready-to-record"}:
            return "ready"
        if raw in {"blocked", "error", "failed"}:
            return "blocked"
        if raw in {"not-started", "not-ready", "needs-sample", "pilot-needed", "post-run-needed", "after-proof", "needs-settings", "coverage-needed"}:
            return "missing"
        if raw in {"review", "stale", "stale-history", "unknown", "planned", "optional-review"}:
            return "review"
        if raw == "manual":
            return "manual"
        return raw or "unknown"

    def row(
        checkpoint: str,
        owner_page: str,
        status: str,
        evidence: str,
        missing: list[str],
        safe_next_action: str,
        *,
        required: bool = True,
    ) -> dict[str, Any]:
        normalized = normalize_status(status)
        if normalized == "blocked":
            severity = "error"
        elif normalized in {"review", "missing", "unknown"}:
            severity = "warning"
        else:
            severity = "info"
        return {
            "checkpoint": checkpoint,
            "owner_page": owner_page,
            "status": normalized,
            "severity": severity,
            "required": required,
            "evidence": _clean_text(evidence, max_chars=SAMPLE_VALIDATION_TEXT_MAX_CHARS),
            "missing_evidence": [_clean_text(item, max_chars=160) for item in missing if _clean_text(item)],
            "safe_next_action": _clean_text(safe_next_action, max_chars=SAMPLE_VALIDATION_TEXT_MAX_CHARS),
            "guardrail": "Read-only evidence-gap row. It cannot launch, append, accept, publish, drain, repair, save settings, rename, rewrite manifests, or touch media.",
        }

    pilot_rows = {
        _clean_text(item.get("stage")): item
        for item in pilot_plan.get("rows", [])
        if isinstance(item, Mapping)
    }
    completed_stage = pilot_rows.get("Verify Completed output and sidecar", {})
    diagnostics_stage = pilot_rows.get("Read Diagnostics and run logs", {})
    pending_stage = pilot_rows.get("Review Pending Publish posture", {})
    settings_stage = pilot_rows.get("Confirm saved route/media policy", {})
    sample_stage = pilot_rows.get("Select a small known sample", {})

    required_ready = int(readiness.get("required_ready_count") or 0)
    required_count = int(readiness.get("required_count") or 0)
    readiness_missing = [
        _clean_text(item)
        for item in readiness.get("missing_required", []) or []
        if _clean_text(item)
    ]

    sample_rows = [
        item for item in sample_set_guide.get("rows", [])
        if isinstance(item, Mapping)
    ]
    missing_required_categories = [
        _clean_text(item.get("category") or item.get("category_key"))
        for item in sample_rows
        if item.get("required") is not False and normalize_status(item.get("status")) != "ready"
    ]

    reconciliation_status = normalize_status(reconciliation.get("operator_status"))
    reconciliation_missing: list[str] = []
    for item in reconciliation.get("rows", []) or []:
        if not isinstance(item, Mapping):
            continue
        for missing in item.get("missing_current_evidence", []) or []:
            text = _clean_text(missing, max_chars=160)
            if text and text not in reconciliation_missing:
                reconciliation_missing.append(text)
    if not reconciliation_missing and reconciliation_status in {"missing", "review", "unknown"}:
        reconciliation_missing.append("current backend record proof is incomplete or inconclusive")

    rows = [
        row(
            "Current backend evidence",
            "Queue / Completed / Pending Publish / Diagnostics",
            "blocked" if readiness.get("operator_status") == "blocked" else "ready" if required_count and required_ready >= required_count else "missing",
            f"readiness={readiness.get('operator_status') or 'not loaded'}; required={required_ready}/{required_count}; warnings={readiness.get('warning_count') or 0}; blockers={readiness.get('blocker_count') or 0}",
            readiness_missing,
            _clean_text(readiness.get("safe_next_action")) or "Load Queue, Completed, Pending Publish, Diagnostics, and Settings evidence.",
        ),
        row(
            "Selected sample and saved policy",
            "Queue / Settings / Launch",
            "ready" if normalize_status(sample_stage.get("status")) == "ready" and normalize_status(settings_stage.get("status")) == "ready" else "missing",
            f"sample={sample_stage.get('status') or 'not loaded'}; settings={settings_stage.get('status') or 'not loaded'}",
            [
                item
                for item, stage in (
                    ("selected Queue sample", sample_stage),
                    ("saved media policy posture", settings_stage),
                )
                if normalize_status(stage.get("status")) != "ready"
            ],
            "Select one known sample and confirm saved route, subtitle, audio, size, pending-publish, and source-safety policy before a pilot run.",
        ),
        row(
            "Post-run Completed and Diagnostics proof",
            "Completed / Diagnostics",
            "ready" if normalize_status(completed_stage.get("status")) == "ready" and normalize_status(diagnostics_stage.get("status")) == "ready" else "missing",
            f"completed={completed_stage.get('status') or 'not loaded'}; diagnostics={diagnostics_stage.get('status') or 'not loaded'}",
            [
                item
                for item, stage in (
                    ("Completed output/sidecar/size proof", completed_stage),
                    ("Diagnostics run-log proof", diagnostics_stage),
                )
                if normalize_status(stage.get("status")) != "ready"
            ],
            "After the sample run, compare Completed output/sidecar/route/size proof and bounded run-log evidence for the same source/output.",
        ),
        row(
            "Final placement / Pending Publish proof",
            "Pending Publish / Completed",
            "ready" if normalize_status(pending_stage.get("status")) in {"ready", "manual"} else normalize_status(pending_stage.get("status")),
            f"pending={pending_stage.get('status') or 'not loaded'}; pending rows are optional only when deferred publish is not involved",
            [] if normalize_status(pending_stage.get("status")) in {"ready", "manual"} else ["pending/final-placement proof"],
            "If the sample was parked or drained, compare Pending Publish, durable drain summary, Completed output proof, Run Logs, and Last Stderr before accepting final placement.",
            required=False,
        ),
        row(
            "Manual playback / subtitle / audio checks",
            "Plex client / Completed / Settings",
            "ready" if cutover_gate.get("current_recommended_checks_complete") else "review",
            f"recommended playback/subtitle/audio/publish checks complete={_yes_no(cutover_gate.get('current_recommended_checks_complete'))}",
            [] if cutover_gate.get("current_recommended_checks_complete") else ["Plex playback", "preferred-language subtitle/SRT behavior", "audio/default-language behavior", "pending-publish final-placement review"],
            "Manually confirm Plex playback, subtitle conversion/retention, audio/default track behavior, size posture, and final placement before expanding WebView use.",
            required=False,
        ),
        row(
            "Representative category coverage",
            "Home / Sample Validation",
            "ready" if sample_set_guide.get("sample_set_ready") else "missing",
            f"sample_set={sample_set_guide.get('operator_status') or 'not loaded'}; required={sample_set_guide.get('required_ready_count') or 0}/{sample_set_guide.get('required_count') or 0}; current accepted={sample_set_guide.get('current_accepted_record_count') or 0}",
            missing_required_categories,
            _clean_text(sample_set_guide.get("safe_next_action")) or "Add current accepted validation records for missing representative pilot categories.",
        ),
        row(
            "Current accepted record reconciliation",
            "Home / Sample Validation",
            reconciliation_status,
            f"reconciliation={reconciliation.get('operator_status') or 'not loaded'}; current={reconciliation.get('current_count') or 0}; review={reconciliation.get('review_count') or 0}; stale={reconciliation.get('stale_count') or 0}; errors={reconciliation.get('error_count') or 0}",
            reconciliation_missing,
            _clean_text(reconciliation.get("safe_next_action")) or "Compare validation records against current backend proof before trusting historical notes.",
        ),
        row(
            "Generated worksheet context",
            "Docs / Home",
            "ready" if int(worksheet_runs.get("run_count") or 0) > 0 else "review",
            f"worksheets={worksheet_runs.get('run_count') or 0}; samples={worksheet_runs.get('sample_count') or 0}; packet rows={worksheet_runs.get('packet_row_count') or 0}",
            [] if int(worksheet_runs.get("run_count") or 0) > 0 else ["optional generated worksheet context"],
            _clean_text(worksheet_runs.get("safe_next_action")) or "Generate a worksheet only if persistent Markdown pilot context is useful.",
            required=False,
        ),
    ]

    blocked_count = sum(1 for item in rows if item["status"] == "blocked")
    missing_count = sum(1 for item in rows if item["status"] == "missing")
    review_count = sum(1 for item in rows if item["status"] in {"review", "unknown"})
    ready_count = sum(1 for item in rows if item["status"] == "ready")
    manual_count = sum(1 for item in rows if item["status"] == "manual")
    required_missing = [
        item["checkpoint"]
        for item in rows
        if item.get("required") and item["status"] in {"missing", "blocked", "review", "unknown"}
    ]
    if blocked_count:
        operator_status = "blocked"
        safe_next_action = "Resolve blocked evidence before using WebView for another sample or unattended run."
    elif required_missing:
        operator_status = "missing-required-evidence"
        safe_next_action = f"Complete required evidence first: {', '.join(required_missing)}."
    elif review_count:
        operator_status = "review"
        safe_next_action = "Review optional/manual proof gaps before daily-driver trust."
    else:
        operator_status = "ready-looking"
        safe_next_action = "Required pilot proof is present. Keep the external rollback workspace and rerun representative samples after media-policy changes."
    summary_lines = [
        f"Real-media evidence gap summary: {operator_status}",
        f"Rows: ready={ready_count}; manual={manual_count}; review={review_count}; missing={missing_count}; blocked={blocked_count}",
        f"Required gaps: {', '.join(required_missing) if required_missing else 'none'}",
        f"Sample set required ready: {sample_set_guide.get('required_ready_count') or 0}/{sample_set_guide.get('required_count') or 0}; current accepted records={sample_set_guide.get('current_accepted_record_count') or 0}",
        f"Cutover gate: {cutover_gate.get('operator_status') or 'not loaded'}; pilot plan: {pilot_plan.get('operator_status') or 'not loaded'}; reconciliation: {reconciliation.get('operator_status') or 'not loaded'}",
        f"Safe next action: {safe_next_action}",
        "Boundary: this gap summary is read-only. It cannot launch, append records, accept outputs, publish/drain, repair, save settings, rename, rewrite manifests, or touch media.",
    ]
    return {
        "schema_version": SAMPLE_VALIDATION_EVIDENCE_GAP_SCHEMA,
        "operator_status": operator_status,
        "ready_count": ready_count,
        "manual_count": manual_count,
        "review_count": review_count,
        "missing_count": missing_count,
        "blocked_count": blocked_count,
        "required_gap_count": len(required_missing),
        "required_gaps": required_missing,
        "rows": rows,
        "summary_lines": summary_lines,
        "safe_next_action": safe_next_action,
        "guardrail": (
            "Read-only real-media evidence-gap summary. It does not launch work, append validation records, accept outputs, "
            "clear failures, drain pending publish, rewrite manifests/sidecars, save settings, rename files, or mutate source/output/scratch media."
        ),
    }


def sample_validation_validation_audit_payload(
    readiness: Mapping[str, Any],
    reconciliation: Mapping[str, Any],
    worksheet_runs: Mapping[str, Any],
    pilot_plan: Mapping[str, Any],
    cutover_gate: Mapping[str, Any],
    sample_set_guide: Mapping[str, Any],
    evidence_gap: Mapping[str, Any],
    pilot_runbook: Mapping[str, Any],
    policy_alignment: Mapping[str, Any],
) -> dict[str, Any]:
    """Return a conservative read-only roll-up over real-media validation evidence.

    This intentionally audits existing evidence payloads only. It never probes
    media, launches work, repairs records, promotes accepted state, or mutates
    queue/completed/pending-publish artifacts.
    """

    def number(payload: Mapping[str, Any], key: str) -> int:
        try:
            return max(0, int(payload.get(key) or 0))
        except (TypeError, ValueError):
            return 0

    def normalize_status(value: Any) -> str:
        raw = _clean_text(value).casefold()
        if raw in {
            "ready",
            "current",
            "current-evidence",
            "sample-set-ready",
            "ready-for-operator-trial",
            "ready-looking",
            "evidence-present",
            "ready-to-record",
            "worksheet-evidence-present",
        }:
            return "ready"
        if raw in {"blocked", "error", "failed", "unreadable"}:
            return "blocked"
        if raw in {
            "not-started",
            "not-ready",
            "needs-sample",
            "pilot-needed",
            "post-run-needed",
            "after-proof",
            "needs-settings",
            "coverage-needed",
            "missing-required-evidence",
        }:
            return "missing"
        if raw in {"review", "stale", "stale-history", "unknown", "planned", "optional-review", "manual"}:
            return "review"
        return raw or "unknown"

    def row(
        area: str,
        owner: str,
        status: str,
        evidence: str,
        safe_next_action: str,
        *,
        required: bool = True,
        source_payload: str = "",
    ) -> dict[str, Any]:
        normalized = normalize_status(status)
        if normalized == "blocked":
            severity = "error"
        elif normalized in {"missing", "review", "unknown"}:
            severity = "warning"
        else:
            severity = "info"
        return {
            "area": area,
            "owner": owner,
            "required": required,
            "status": normalized,
            "severity": severity,
            "source_payload": source_payload,
            "evidence": _clean_text(evidence, max_chars=SAMPLE_VALIDATION_TEXT_MAX_CHARS),
            "safe_next_action": _clean_text(safe_next_action, max_chars=SAMPLE_VALIDATION_TEXT_MAX_CHARS),
            "guardrail": "Read-only validation audit row. It cannot launch, accept, publish, drain, append records, repair state, save settings, rename, rewrite manifests, or touch media.",
        }

    readiness_required = number(readiness, "required_count")
    readiness_ready = number(readiness, "required_ready_count")
    readiness_blockers = number(readiness, "blocker_count")
    readiness_warnings = number(readiness, "warning_count")
    readiness_missing = [
        _clean_text(item, max_chars=140)
        for item in readiness.get("missing_required", []) or []
        if _clean_text(item)
    ]
    if readiness_blockers:
        readiness_audit_status = "blocked"
    elif readiness_required and readiness_ready >= readiness_required:
        readiness_audit_status = "review" if readiness_warnings else "ready"
    else:
        readiness_audit_status = "missing"

    reconciliation_current = number(reconciliation, "current_count")
    reconciliation_review = number(reconciliation, "review_count")
    reconciliation_stale = number(reconciliation, "stale_count")
    reconciliation_errors = number(reconciliation, "error_count")
    if reconciliation_errors or normalize_status(reconciliation.get("operator_status")) == "blocked":
        reconciliation_audit_status = "blocked"
    elif reconciliation_current:
        reconciliation_audit_status = "review" if reconciliation_review or reconciliation_stale else "ready"
    else:
        reconciliation_audit_status = "missing"

    worksheet_status = normalize_status(worksheet_runs.get("operator_status"))
    if number(worksheet_runs, "run_count") > 0 and worksheet_status != "blocked":
        worksheet_audit_status = "review" if worksheet_status == "review" else "ready"
    elif worksheet_status == "blocked":
        worksheet_audit_status = "blocked"
    else:
        worksheet_audit_status = "review"

    sample_required = number(sample_set_guide, "required_count")
    sample_ready = number(sample_set_guide, "required_ready_count")
    if normalize_status(sample_set_guide.get("operator_status")) == "blocked":
        sample_set_audit_status = "blocked"
    elif bool(sample_set_guide.get("sample_set_ready")):
        sample_set_audit_status = "ready"
    elif sample_required and sample_ready < sample_required:
        sample_set_audit_status = "missing"
    else:
        sample_set_audit_status = "review"

    evidence_gap_status = normalize_status(evidence_gap.get("operator_status"))
    if number(evidence_gap, "blocked_count"):
        evidence_gap_audit_status = "blocked"
    elif number(evidence_gap, "required_gap_count"):
        evidence_gap_audit_status = "missing"
    else:
        evidence_gap_audit_status = evidence_gap_status

    runbook_status = normalize_status(pilot_runbook.get("operator_status"))
    if number(pilot_runbook, "blocked_count"):
        runbook_audit_status = "blocked"
    elif number(pilot_runbook, "required_gap_count"):
        runbook_audit_status = "missing"
    else:
        runbook_audit_status = runbook_status

    policy_status = normalize_status(policy_alignment.get("operator_status"))
    if number(policy_alignment, "blocked_count"):
        policy_audit_status = "blocked"
    elif number(policy_alignment, "missing_count") and policy_status == "missing":
        policy_audit_status = "missing"
    elif number(policy_alignment, "review_count"):
        policy_audit_status = "review"
    elif policy_alignment.get("policy_ready") or policy_status == "ready":
        policy_audit_status = "ready"
    else:
        policy_audit_status = policy_status

    cutover_status = normalize_status(cutover_gate.get("operator_status"))
    if bool(cutover_gate.get("gate_ready")):
        cutover_audit_status = "ready"
    elif number(cutover_gate, "blocked_count") or cutover_status == "blocked":
        cutover_audit_status = "blocked"
    elif cutover_status == "missing":
        cutover_audit_status = "missing"
    else:
        cutover_audit_status = "review"

    rows = [
        row(
            "Current backend proof",
            "Queue / Completed / Pending Publish / Diagnostics / Settings",
            readiness_audit_status,
            f"readiness={readiness.get('operator_status') or 'not loaded'}; required={readiness_ready}/{readiness_required}; warnings={readiness_warnings}; blockers={readiness_blockers}; missing={', '.join(readiness_missing) if readiness_missing else 'none'}",
            _clean_text(readiness.get("safe_next_action")) or "Refresh backend evidence before recording a real-media sample.",
            source_payload="readiness",
        ),
        row(
            "Sample validation records",
            "Home / Sample Validation",
            reconciliation_audit_status,
            f"reconciliation={reconciliation.get('operator_status') or 'not loaded'}; checked={reconciliation.get('checked_count') or 0}; current={reconciliation_current}; review={reconciliation_review}; stale={reconciliation_stale}; errors={reconciliation_errors}",
            _clean_text(reconciliation.get("safe_next_action")) or "Append an evidence-only record after a supervised sample run.",
            source_payload="reconciliation",
        ),
        row(
            "Generated worksheet context",
            "Docs / Home",
            worksheet_audit_status,
            f"worksheets={worksheet_runs.get('run_count') or 0}; samples={worksheet_runs.get('sample_count') or 0}; packets={worksheet_runs.get('packet_row_count') or 0}; status={worksheet_runs.get('operator_status') or 'not loaded'}",
            _clean_text(worksheet_runs.get("safe_next_action")) or "Generate a worksheet only when persistent pilot context is useful.",
            required=False,
            source_payload="worksheet_runs",
        ),
        row(
            "Representative category coverage",
            "Home / Sample Validation",
            sample_set_audit_status,
            f"sample_set={sample_set_guide.get('operator_status') or 'not loaded'}; required={sample_ready}/{sample_required}; current accepted={sample_set_guide.get('current_accepted_record_count') or 0}; worksheet samples={sample_set_guide.get('worksheet_sample_count') or 0}",
            _clean_text(sample_set_guide.get("safe_next_action")) or "Gather accepted current evidence for each required representative sample category.",
            source_payload="sample_set_guide",
        ),
        row(
            "Saved media policy alignment",
            "Settings / Home / Sample Validation",
            policy_audit_status,
            f"policy={policy_alignment.get('operator_status') or 'not loaded'}; required={policy_alignment.get('required_ready_count') or 0}/{policy_alignment.get('required_count') or 0}; review={policy_alignment.get('review_count') or 0}; blocked={policy_alignment.get('blocked_count') or 0}; missing={policy_alignment.get('missing_count') or 0}",
            _clean_text(policy_alignment.get("safe_next_action")) or "Compare saved route, size, subtitle, audio, and pending-publish settings before the pilot.",
            source_payload="policy_alignment",
        ),
        row(
            "Evidence gap status",
            "Home / Queue / Completed / Diagnostics / Pending Publish",
            evidence_gap_audit_status,
            f"gap={evidence_gap.get('operator_status') or 'not loaded'}; required gaps={evidence_gap.get('required_gap_count') or 0}; ready={evidence_gap.get('ready_count') or 0}; review={evidence_gap.get('review_count') or 0}; missing={evidence_gap.get('missing_count') or 0}; blocked={evidence_gap.get('blocked_count') or 0}",
            _clean_text(evidence_gap.get("safe_next_action")) or "Close required proof gaps before treating WebView as daily-use ready.",
            source_payload="evidence_gap_summary",
        ),
        row(
            "Pilot runbook",
            "Home / Launch / Diagnostics / Completed",
            runbook_audit_status,
            f"runbook={pilot_runbook.get('operator_status') or 'not loaded'}; required gaps={pilot_runbook.get('required_gap_count') or 0}; ready={pilot_runbook.get('ready_count') or 0}; review={pilot_runbook.get('review_count') or 0}; missing={pilot_runbook.get('missing_count') or 0}; blocked={pilot_runbook.get('blocked_count') or 0}",
            _clean_text(pilot_runbook.get("safe_next_action")) or "Use the pilot runbook to complete a supervised real-media sample before daily use.",
            source_payload="pilot_runbook",
        ),
        row(
            "WebView cutover posture",
            "Home / external rollback / WebView",
            cutover_audit_status,
            f"cutover={cutover_gate.get('operator_status') or 'not loaded'}; gate_ready={bool(cutover_gate.get('gate_ready'))}; current accepted={cutover_gate.get('current_accepted_record_count') or 0}; required checks={_yes_no(cutover_gate.get('current_required_checks_complete'))}",
            _clean_text(cutover_gate.get("safe_next_action")) or "Keep external rollback available until cutover gate evidence is ready and current.",
            source_payload="cutover_gate",
        ),
    ]

    blocked_count = sum(1 for item in rows if item["status"] == "blocked")
    required_rows = [item for item in rows if item.get("required")]
    required_ready_count = sum(1 for item in required_rows if item["status"] == "ready")
    missing_required_rows = [
        item["area"]
        for item in required_rows
        if item["status"] in {"missing", "blocked", "unknown"}
    ]
    review_required_rows = [
        item["area"]
        for item in required_rows
        if item["status"] == "review"
    ]
    review_count = sum(1 for item in rows if item["status"] == "review")
    ready_count = sum(1 for item in rows if item["status"] == "ready")
    if blocked_count:
        operator_status = "blocked"
        safe_next_action = "Resolve blocked validation evidence before trusting WebView with real media."
    elif missing_required_rows:
        operator_status = "missing-required-evidence"
        safe_next_action = f"Complete required validation evidence first: {', '.join(missing_required_rows)}."
    elif review_required_rows:
        operator_status = "review-required-evidence"
        safe_next_action = f"Review required validation evidence first: {', '.join(review_required_rows)}."
    elif review_count:
        operator_status = "ready-with-operator-review"
        safe_next_action = "Required evidence is ready; review optional worksheet/manual context before expanding WebView use."
    else:
        operator_status = "ready-for-supervised-webview-trial"
        safe_next_action = "Run the next supervised representative sample through backend-owned Launch while keeping external rollback available."

    summary_lines = [
        f"Real-media validation audit: {operator_status}",
        f"Required rows ready: {required_ready_count}/{len(required_rows)}; blocked={blocked_count}; missing_required={len(missing_required_rows)}; review_required={len(review_required_rows)}; optional_review={max(0, review_count - len(review_required_rows))}",
        f"Current records: {reconciliation_current}; worksheet runs: {worksheet_runs.get('run_count') or 0}; required categories ready: {sample_ready}/{sample_required}; policy alignment: {policy_alignment.get('operator_status') or 'not loaded'}; cutover gate: {cutover_gate.get('operator_status') or 'not loaded'}",
        f"Required gaps: {', '.join(missing_required_rows + review_required_rows) if missing_required_rows or review_required_rows else 'none'}",
        f"Safe next action: {safe_next_action}",
        "Boundary: validation audit is read-only. It cannot launch, append records, accept outputs, publish/drain, repair, save settings, rename, rewrite manifests, or touch media.",
    ]
    return {
        "schema_version": SAMPLE_VALIDATION_AUDIT_SCHEMA,
        "operator_status": operator_status,
        "validation_ready": operator_status == "ready-for-supervised-webview-trial",
        "required_ready_count": required_ready_count,
        "required_count": len(required_rows),
        "ready_count": ready_count,
        "review_count": review_count,
        "blocked_count": blocked_count,
        "missing_required_count": len(missing_required_rows),
        "review_required_count": len(review_required_rows),
        "missing_required": missing_required_rows,
        "review_required": review_required_rows,
        "rows": rows,
        "summary_lines": summary_lines,
        "safe_next_action": safe_next_action,
        "guardrail": (
            "Read-only real-media validation audit. It does not launch work, append validation records, accept outputs, "
            "clear failures, drain pending publish, rewrite manifests/sidecars, save settings, rename files, or mutate source/output/scratch media."
        ),
    }


def sample_validation_policy_alignment_payload(resolved: ResolvedPaths) -> dict[str, Any]:
    """Compare saved media policy posture to real-media validation categories.

    This is a read-only bridge from Settings policy evidence into Sample
    Validation. It does not decide routes, rewrite config, launch work, run
    probes, or mutate any media/state artifacts.
    """

    config = dict(resolved.config_data or {}) if isinstance(resolved.config_data, Mapping) else {}
    if not config:
        rows = [
            _policy_alignment_row(
                str(category.get("category_key") or ""),
                str(category.get("category") or ""),
                bool(category.get("required", True)),
                "missing",
                "No saved config data is loaded.",
                "Open Settings and confirm route, size, subtitle, audio, pending-publish, and source-preservation policy before a real-media pilot.",
                (),
            )
            for category in SAMPLE_VALIDATION_SAMPLE_SET_CATEGORIES
        ]
        summary_lines = [
            "Real-media policy alignment: missing-saved-policy",
            "Required category settings ready: 0/4; review=0; blocked=0; missing=4",
            "Backend media-policy readiness: not loaded",
            "Safe next action: Open Settings and confirm saved policy before running or recording a real-media sample.",
            "Boundary: policy alignment is read-only. It cannot save settings, launch, append records, accept outputs, publish/drain, repair, rename, rewrite manifests, run FFmpeg, or touch media.",
        ]
        return {
            "schema_version": SAMPLE_VALIDATION_POLICY_ALIGNMENT_SCHEMA,
            "operator_status": "missing-saved-policy",
            "policy_ready": False,
            "required_ready_count": 0,
            "required_count": sum(1 for category in SAMPLE_VALIDATION_SAMPLE_SET_CATEGORIES if bool(category.get("required", True))),
            "ready_count": 0,
            "review_count": 0,
            "blocked_count": 0,
            "missing_count": len(rows),
            "rows": rows,
            "media_policy_readiness": {},
            "summary_lines": summary_lines,
            "safe_next_action": "Open Settings and confirm saved policy before running or recording a real-media sample.",
            "guardrail": _policy_alignment_guardrail(),
        }

    media_readiness = build_media_policy_readiness(config)
    readiness_rows = {
        _clean_text(row.get("area")): row
        for row in media_readiness.get("rows", [])
        if isinstance(row, Mapping)
    }

    def category_row(
        category_key: str,
        category: str,
        required: bool,
        areas: tuple[str, ...],
        safe_next_action: str,
    ) -> dict[str, Any]:
        related = [readiness_rows.get(area, {}) for area in areas]
        related = [row for row in related if row]
        if not related:
            return _policy_alignment_row(
                category_key,
                category,
                required,
                "missing",
                f"No backend media-policy readiness rows matched: {', '.join(areas)}.",
                safe_next_action,
                areas,
            )
        postures = [_clean_text(row.get("posture")).casefold() for row in related]
        if "blocked" in postures:
            status = "blocked"
        elif "review" in postures:
            status = "review"
        elif all(posture == "coherent" for posture in postures):
            status = "ready"
        else:
            status = "review"
        evidence = " | ".join(
            f"{row.get('area')}: {row.get('evidence') or row.get('posture') or 'not reported'}"
            for row in related
        )
        review_notes = [
            _clean_text(row.get("operator_check"), max_chars=180)
            for row in related
            if _clean_text(row.get("posture")).casefold() != "coherent"
        ]
        if review_notes:
            evidence = f"{evidence} | attention: {'; '.join(review_notes[:3])}"
        return _policy_alignment_row(
            category_key,
            category,
            required,
            status,
            evidence,
            safe_next_action,
            areas,
        )

    deferred_publish = _config_bool(config, KEY_DEFERRED_PUBLISH, False)
    rows = [
        category_row(
            "h264-remux-safe",
            "H.264 remux/direct-play copy",
            True,
            ("Routing / Output Size Check", "Container / subtitle preservation", "Source preservation"),
            "Before pilot launch, confirm the selected H.264 sample is expected to copy/remux and that any encode size growth remains advisory/strict according to saved policy.",
        ),
        category_row(
            "subtitle-srt-generation",
            "Preferred-language subtitle to SRT",
            True,
            (
                "Subtitle language routing",
                "TX3G / mov_text SRT",
                "BDPGS OCR to SRT",
                "ASS / SSA preservation",
                "Container / subtitle preservation",
            ),
            "Before pilot launch, confirm preferred-language SRT generation and original-subtitle retention/drop toggles match the sample's subtitle type.",
        ),
        category_row(
            "audio-routing",
            "Audio routing/default language",
            True,
            ("Audio language / default track", "Audio passthrough / channels"),
            "Before pilot launch, confirm preferred default audio language, passthrough profile, compatible codecs, and channel/downmix limits match the expected Plex playback path.",
        ),
        category_row(
            "encode-size-policy",
            "Encode and size policy",
            True,
            ("Routing / Output Size Check", "Publish / recovery safety"),
            "Before pilot launch, confirm the route profile and Output Size Check explain whether the sample may encode, copy, warn, reject, or require manual review.",
        ),
        category_row(
            "deferred-publish",
            "Deferred publish/final placement",
            False,
            ("Publish / recovery safety",),
            "If deferred publish is enabled for this pilot, compare Pending Publish parked/drain proof before recording accepted final-placement evidence.",
        ),
    ]
    if not deferred_publish:
        for row in rows:
            if row["category_key"] == "deferred-publish" and row["status"] == "ready":
                row["status"] = "manual"
                row["severity"] = "info"
                row["evidence"] = f"{row['evidence']} | DeferredPublish=False; category is optional unless the pilot intentionally tests parked/drained output."
                row["safe_next_action"] = "Deferred publish is disabled. Treat this category as optional unless you intentionally enable deferred publish for a final-placement pilot."
                break

    required_rows = [row for row in rows if row.get("required")]
    ready_count = sum(1 for row in rows if row.get("status") in {"ready", "manual"})
    review_count = sum(1 for row in rows if row.get("status") == "review")
    blocked_count = sum(1 for row in rows if row.get("status") == "blocked")
    missing_count = sum(1 for row in rows if row.get("status") == "missing")
    required_ready_count = sum(1 for row in required_rows if row.get("status") == "ready")
    blocked_required = [row["category"] for row in required_rows if row.get("status") == "blocked"]
    missing_required = [row["category"] for row in required_rows if row.get("status") == "missing"]
    review_required = [row["category"] for row in required_rows if row.get("status") == "review"]
    if blocked_required:
        operator_status = "blocked"
        safe_next_action = f"Resolve blocked saved-policy evidence first: {', '.join(blocked_required)}."
    elif missing_required:
        operator_status = "missing-policy-evidence"
        safe_next_action = f"Load or fix saved-policy evidence first: {', '.join(missing_required)}."
    elif review_required:
        operator_status = "review"
        safe_next_action = f"Review saved-policy tradeoffs before the pilot: {', '.join(review_required)}."
    else:
        operator_status = "ready-looking"
        safe_next_action = "Saved policy appears aligned with required pilot categories; still verify actual route/output/subtitle/audio/size behavior on real media."

    media_counts = media_readiness.get("counts") if isinstance(media_readiness.get("counts"), Mapping) else {}
    summary_lines = [
        f"Real-media policy alignment: {operator_status}",
        f"Required category settings ready: {required_ready_count}/{len(required_rows)}; review={len(review_required)}; blocked={len(blocked_required)}; missing={len(missing_required)}",
        f"Backend media-policy readiness: {media_readiness.get('operator_status') or 'unknown'}; coherent={media_counts.get('coherent') or 0}; review={media_counts.get('review') or 0}; blocked={media_counts.get('blocked') or 0}",
        f"Policy categories: ready={ready_count}; review={review_count}; missing={missing_count}; blocked={blocked_count}; deferred_publish={_yes_no(deferred_publish)}",
        f"Safe next action: {safe_next_action}",
        "Boundary: policy alignment is read-only. It cannot save settings, launch, append records, accept outputs, publish/drain, repair, rename, rewrite manifests, run FFmpeg, or touch media.",
    ]
    return {
        "schema_version": SAMPLE_VALIDATION_POLICY_ALIGNMENT_SCHEMA,
        "operator_status": operator_status,
        "policy_ready": operator_status == "ready-looking",
        "required_ready_count": required_ready_count,
        "required_count": len(required_rows),
        "ready_count": ready_count,
        "review_count": review_count,
        "blocked_count": blocked_count,
        "missing_count": missing_count,
        "missing_required": missing_required,
        "review_required": review_required,
        "blocked_required": blocked_required,
        "rows": rows,
        "media_policy_readiness": media_readiness,
        "summary_lines": summary_lines,
        "safe_next_action": safe_next_action,
        "guardrail": _policy_alignment_guardrail(),
    }


def _clean_text(value: Any, *, max_chars: int = SAMPLE_VALIDATION_TEXT_MAX_CHARS) -> str:
    text = str(value or "").replace("\x00", "").strip()
    return text[:max_chars]


def _config_bool(config: Mapping[str, Any], key: str, default: bool = False) -> bool:
    value = config.get(key, default)
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    text = _clean_text(value).casefold()
    if text in {"1", "true", "yes", "y", "on"}:
        return True
    if text in {"0", "false", "no", "n", "off"}:
        return False
    return default


def _policy_alignment_guardrail() -> str:
    return (
        "Read-only real-media policy alignment. It does not save settings, launch work, append validation records, "
        "accept outputs, clear failures, drain pending publish, rewrite manifests/sidecars, run FFmpeg, rename files, "
        "or mutate source/output/scratch media."
    )


def _policy_alignment_row(
    category_key: str,
    category: str,
    required: bool,
    status: str,
    evidence: str,
    safe_next_action: str,
    source_areas: tuple[str, ...],
) -> dict[str, Any]:
    normalized = _clean_text(status).casefold() or "unknown"
    if normalized == "blocked":
        severity = "error"
    elif normalized in {"review", "missing", "unknown"}:
        severity = "warning"
    else:
        severity = "info"
    return {
        "category_key": _clean_text(category_key, max_chars=120),
        "category": _clean_text(category, max_chars=180),
        "required": required,
        "status": normalized,
        "severity": severity,
        "source_areas": [_clean_text(area, max_chars=120) for area in source_areas],
        "evidence": _clean_text(evidence, max_chars=SAMPLE_VALIDATION_TEXT_MAX_CHARS),
        "safe_next_action": _clean_text(safe_next_action, max_chars=SAMPLE_VALIDATION_TEXT_MAX_CHARS),
        "guardrail": "Read-only policy-alignment row. It cannot save settings, launch, append, accept, publish, drain, repair, rename, rewrite manifests, run FFmpeg, or touch media.",
    }


def _yes_no(value: Any) -> str:
    return "yes" if bool(value) else "no"
