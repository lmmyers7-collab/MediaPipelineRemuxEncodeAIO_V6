from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

from .readiness import SAMPLE_VALIDATION_ACCEPTANCE_CHECKS
from .worksheet import _sample_set_worksheet_samples


SAMPLE_VALIDATION_SAMPLE_SET_GUIDE_SCHEMA = "desktop_real_media_sample_set_guide.v1"
SAMPLE_VALIDATION_PILOT_PLAN_SCHEMA = "desktop_real_media_pilot_plan.v1"
SAMPLE_VALIDATION_EXECUTION_CHECKLIST_SCHEMA = "desktop_real_media_execution_checklist.v1"
SAMPLE_VALIDATION_CUTOVER_GATE_SCHEMA = "desktop_webview_cutover_gate.v1"
SAMPLE_VALIDATION_PILOT_RUNBOOK_SCHEMA = "desktop_real_media_pilot_runbook.v1"
SAMPLE_VALIDATION_TEXT_MAX_CHARS = 600
SAMPLE_VALIDATION_SAMPLE_SET_CATEGORIES: tuple[dict[str, Any], ...] = (
    {
        "category_key": "h264-remux-safe",
        "category": "H.264 remux/direct-play copy",
        "required": True,
        "evidence_goal": "A small H.264/AVC source that should copy/remux without video encode and without output growth.",
        "operator_action": "Validate route reason, completed output, sidecar/manifest, size posture, and Plex direct-play playback.",
        "owner_pages": ("Home", "Queue", "Completed", "Diagnostics", "Settings"),
    },
    {
        "category_key": "subtitle-srt-generation",
        "category": "Preferred-language subtitle to SRT",
        "required": True,
        "evidence_goal": "A preferred-language ASS/TX3G/BDPGS subtitle case that should add SRT while preserving originals unless settings say otherwise.",
        "operator_action": "Validate subtitle conversion result, retained original subtitle tracks, diagnostics evidence, and manual-review behavior on failure.",
        "owner_pages": ("Home", "Completed", "Diagnostics", "Settings"),
    },
    {
        "category_key": "audio-routing",
        "category": "Audio routing/default language",
        "required": True,
        "evidence_goal": "A source with meaningful audio-selection risk, such as multiple languages, multichannel audio, or passthrough/downmix expectations.",
        "operator_action": "Validate default language, passthrough/transcode decision, channel layout, and Plex playback behavior.",
        "owner_pages": ("Home", "Completed", "Diagnostics", "Settings"),
    },
    {
        "category_key": "encode-size-policy",
        "category": "Encode and size policy",
        "required": True,
        "evidence_goal": "A source that must encode or is likely to trigger output-growth review, route policy, or size-limit guidance.",
        "operator_action": "Validate encode reason, output-size ratio, quality posture, sidecar route metadata, and any manual review threshold.",
        "owner_pages": ("Home", "Queue", "Completed", "Diagnostics", "Settings"),
    },
    {
        "category_key": "deferred-publish",
        "category": "Deferred publish/final placement",
        "required": False,
        "evidence_goal": "A sample that proves final output placement or Pending Publish parking/drain posture when upload-constrained publishing is enabled.",
        "operator_action": "Validate pending manifest, parked/final output, sidecar/manifest consistency, and drain visibility without starting network mutation from WebView.",
        "owner_pages": ("Home", "Completed", "Pending Publish", "Diagnostics"),
    },
)
SAMPLE_VALIDATION_SAMPLE_CATEGORY_KEYS = {
    str(category["category_key"]) for category in SAMPLE_VALIDATION_SAMPLE_SET_CATEGORIES
}


def sample_validation_pilot_plan_payload(readiness: Mapping[str, Any], reconciliation: Mapping[str, Any]) -> dict[str, Any]:
    """Return read-only operator guidance for the smallest safe real-media pilot.

    The plan intentionally stays separate from launch/acceptance behavior. It
    tells the operator what evidence must be gathered, but it never starts work
    or mutates any media, manifests, sidecars, queues, failures, or publish state.
    """

    readiness_rows = {str(row.get("area") or ""): row for row in readiness.get("rows", []) if isinstance(row, Mapping)}
    queue_row = readiness_rows.get("Queue route evidence", {})
    completed_row = readiness_rows.get("Completed output proof", {})
    diagnostics_row = readiness_rows.get("Diagnostics run log proof", {})
    pending_row = readiness_rows.get("Pending Publish posture", {})
    settings_row = readiness_rows.get("Saved media policy posture", {})
    history_row = readiness_rows.get("Validation history", {})

    readiness_status = _clean_text(readiness.get("operator_status")).casefold()
    reconciliation_status = _clean_text(reconciliation.get("operator_status")).casefold()
    blocked = bool(int(readiness.get("blocker_count") or 0)) or reconciliation_status == "blocked"
    stale = reconciliation_status == "stale"
    sample_run_required = readiness_status in {"not-ready", "blocked"} or not bool(readiness.get("ready_to_record"))

    if blocked:
        operator_status = "blocked"
        safe_next_action = "Resolve unreadable Queue, Completed, Diagnostics, or validation-log evidence before planning the pilot."
    elif stale:
        operator_status = "stale-history"
        safe_next_action = "Treat old validation records as historical only; rerun or re-check a small sample before daily-driver trust."
    elif sample_run_required:
        operator_status = "pilot-needed"
        safe_next_action = "Pick a small sample, refresh Queue route evidence, run only through backend-owned Launch, then compare Completed and Diagnostics proof."
    elif readiness_status == "review" or reconciliation_status in {"review", "unknown"}:
        operator_status = "review"
        safe_next_action = "Required evidence is present, but review warnings and current-evidence rows before recording or trusting the pilot."
    elif reconciliation_status == "current":
        operator_status = "current-evidence"
        safe_next_action = "Recent validation records still match current backend proof; keep validating new media-policy changes with a small pilot before daily use."
    else:
        operator_status = "ready-for-pilot-record"
        safe_next_action = "Preview and append the evidence-only record only after playback, route, subtitle, audio, size, and pending-publish checks are complete."

    rows = [
        _pilot_plan_row(
            "Select a small known sample",
            _pilot_status_from_row(queue_row, missing_status="needs-sample"),
            _clean_text(queue_row.get("evidence")) or "Queue evidence is not loaded.",
            "Use a low-risk file or small TV episode first. Refresh Queue and select the sample row before any Launch decision.",
        ),
        _pilot_plan_row(
            "Confirm saved route/media policy",
            _pilot_status_from_row(settings_row, missing_status="needs-settings"),
            _clean_text(settings_row.get("evidence")) or "Saved settings evidence is not loaded.",
            "Compare RoutingProfile, SizeGuardMode, subtitle conversion, audio passthrough/transcode, and pending-publish posture with the expected sample outcome.",
        ),
        _pilot_plan_row(
            "Run through backend-owned Launch only",
            "manual",
            "No pilot launch is started by this plan.",
            "Start the sample only from the existing backend Launch controls after schedule, close-readiness, Queue, and Settings evidence look correct.",
        ),
        _pilot_plan_row(
            "Verify Completed output and sidecar",
            _pilot_status_from_row(completed_row, missing_status="post-run-needed"),
            _clean_text(completed_row.get("evidence")) or "Completed proof is not loaded.",
            "After processing, compare output path, sidecar/manifest, route reason, encoder, size-growth fields, and file existence before trusting the sample.",
        ),
        _pilot_plan_row(
            "Read Diagnostics and run logs",
            _pilot_status_from_row(diagnostics_row, missing_status="post-run-needed"),
            _clean_text(diagnostics_row.get("evidence")) or "Run-log evidence is not loaded.",
            "Read bounded Last Stderr/Run Logs and ActiveJobs evidence for the same source/output before retrying or accepting the sample.",
        ),
        _pilot_plan_row(
            "Review Pending Publish posture",
            _pilot_status_from_row(pending_row, missing_status="optional-review"),
            _clean_text(pending_row.get("evidence")) or "Pending Publish evidence is not loaded.",
            "If deferred publish parks the sample, compare parked payload, manifest, recovery dry-run, and durable drain summary before final acceptance.",
            required=False,
        ),
        _pilot_plan_row(
            "Record evidence-only validation note",
            _pilot_status_from_row(history_row, missing_status="after-proof"),
            _clean_text(history_row.get("evidence")) or "Validation history is not started.",
            "Use Preview Record first. Append only after current backend evidence, playback, subtitles, audio, size, and pending-publish checks agree.",
            required=False,
        ),
    ]
    required_rows = [row for row in rows if bool(row.get("required"))]
    ready_stage_count = sum(1 for row in required_rows if row.get("status") == "ready")
    manual_stage_count = sum(1 for row in required_rows if row.get("status") == "manual")
    attention_rows = [
        row
        for row in rows
        if row.get("status") not in {"ready", "manual"} and (bool(row.get("required")) or row.get("severity") in {"error", "warning"})
    ]
    blocked_stages = [str(row.get("stage") or "") for row in rows if row.get("status") == "blocked"]
    review_stages = [str(row.get("stage") or "") for row in rows if row.get("status") == "review"]
    next_required_action = (
        _clean_text(attention_rows[0].get("operator_action"))
        if attention_rows
        else safe_next_action
    )
    pilot_attention = [
        {
            "stage": _clean_text(row.get("stage")),
            "status": _clean_text(row.get("status")),
            "severity": _clean_text(row.get("severity")),
            "operator_action": _clean_text(row.get("operator_action")),
        }
        for row in attention_rows[:5]
    ]
    stop_conditions = [
        "Stop and escalate to manual review if source files change unexpectedly.",
        "Stop if close-readiness claims safe while ActiveJobs/progress/logs still show active work.",
        "Stop if Completed output/sidecar proof is missing or points at the wrong final path.",
        "Stop if subtitle/audio/size behavior disagrees with saved Settings and route evidence.",
        "Stop if Pending Publish has do-not-drain, missing payload, invalid manifest, or unexplained drain evidence.",
    ]
    summary_lines = [
        f"Pilot posture: {operator_status}",
        f"Sample run required: {_yes_no(sample_run_required)}",
        f"Required checkpoints ready: {ready_stage_count}/{len(required_rows)}; manual: {manual_stage_count}; attention: {len(attention_rows)}; blocked: {len(blocked_stages)}",
        f"Readiness: {readiness_status or 'unknown'}; reconciliation: {reconciliation_status or 'unknown'}",
        f"Next required action: {next_required_action}",
        f"Safe next action: {safe_next_action}",
        "Boundary: this pilot plan is guidance only and cannot start work, accept output, repair state, publish, rename, rewrite manifests, or touch media.",
    ]
    stage_rows = {str(row.get("stage") or ""): row for row in rows}
    execution_checklist = [
        _pilot_execution_row(
            "Before Launch",
            "Select one known sample row",
            stage_rows.get("Select a small known sample", {}),
            "Queue",
            "Queue payload should identify the source path, route/remux-vs-encode decision, blocked state, and duplicate-title posture.",
            "Operator confirms this is a low-risk, fully copied media file and not a locked or partially downloading source.",
            "Launching an unintended or half-copied file can create misleading Completed/Pending/Diagnostics proof.",
        ),
        _pilot_execution_row(
            "Before Launch",
            "Confirm saved route/media policy",
            stage_rows.get("Confirm saved route/media policy", {}),
            "Settings / Launch",
            "Saved settings evidence should match the route, size guard, subtitle, audio, pending-publish, and source-safety behavior expected for the sample.",
            "Operator confirms staged JSON is either saved/reloaded or irrelevant; Launch will use saved backend settings only.",
            "Unsaved/stale media policy can make the pilot prove a different encode/remux path than the one the operator intended.",
        ),
        _pilot_execution_row(
            "Backend Launch Boundary",
            "Start only through backend-owned Launch",
            stage_rows.get("Run through backend-owned Launch only", {}),
            "Launch",
            "This checklist never starts work. The actual run must appear as a backend command/result with close-readiness and ActiveJobs evidence.",
            "Operator verifies schedule/override, close-readiness, active-work, command history, and Launch preflight before starting.",
            "Starting outside the backend Launch path bypasses the route, command, progress, and diagnostics proof chain this pilot relies on.",
        ),
        _pilot_execution_row(
            "Post-run Completed Proof",
            "Verify Completed output, sidecar, manifest, route, and size",
            stage_rows.get("Verify Completed output and sidecar", {}),
            "Completed",
            "Completed payload should show output path, sidecar/manifest, route reason, encoder, size-growth fields, and file-existence proof for the same sample.",
            "Operator confirms the output is playable and the sidecar/manifest still point at the expected source/output.",
            "A missing or mismatched Completed row can hide publish failures, wrong-folder output, stale sidecars, or unexpected encode growth.",
        ),
        _pilot_execution_row(
            "Post-run Diagnostics Proof",
            "Read Diagnostics and run logs for the same sample",
            stage_rows.get("Read Diagnostics and run logs", {}),
            "Diagnostics",
            "Diagnostics should expose bounded stderr/stdout/run-log/ActiveJobs evidence that matches the selected source or output.",
            "Operator checks errors, subtitle/OCR warnings, audio/route messages, FFmpeg exit status, and stale runtime-progress clues.",
            "Skipping logs can turn a partially successful encode, failed subtitle conversion, or orphan process into trusted sample evidence.",
        ),
        _pilot_execution_row(
            "Post-run Pending Publish Proof",
            "Verify parked or final-destination state",
            stage_rows.get("Review Pending Publish posture", {}),
            "Pending Publish",
            "Pending Publish evidence should explain whether the sample is parked, drained, do-not-drain, missing payload, or not applicable.",
            "Operator confirms parked payload, destination, manifest, sidecars, recovery dry-run, and durable drain summary before trusting final placement.",
            "Ignoring pending-publish posture can make a valid scratch output look completed while the final library path is still missing.",
            required=False,
        ),
        _pilot_execution_row(
            "Evidence Record",
            "Preview then append evidence-only validation note",
            stage_rows.get("Record evidence-only validation note", {}),
            "Home / Sample Validation",
            "Preview should show current backend evidence, append-readiness gaps, and manual acceptance checks before the JSONL record is written.",
            "Operator records playback, subtitle, audio, size, route, Completed, Pending Publish, and Diagnostics observations.",
            "Appending without proof creates false trust history; the record never accepts output or changes pipeline truth.",
            required=False,
        ),
    ]
    execution_required = [row for row in execution_checklist if bool(row.get("required"))]
    execution_attention = [
        row for row in execution_checklist if row.get("status") not in {"ready", "manual"} and (bool(row.get("required")) or row.get("severity") in {"error", "warning"})
    ]
    execution_ready_count = sum(1 for row in execution_required if row.get("status") == "ready")
    execution_manual_count = sum(1 for row in execution_required if row.get("status") == "manual")
    execution_summary_lines = [
        f"Operator-selected real-media sample execution: {operator_status}",
        f"Execution required ready: {execution_ready_count}/{len(execution_required)}; manual={execution_manual_count}; attention={len(execution_attention)}",
        f"Execution next action: {_clean_text(execution_attention[0].get('operator_proof')) if execution_attention else safe_next_action}",
        "Boundary: execution checklist is read-only guidance; only backend-owned Launch, Preview, Append, and page commands can mutate their scoped state.",
    ]
    return {
        "schema_version": SAMPLE_VALIDATION_PILOT_PLAN_SCHEMA,
        "operator_status": operator_status,
        "sample_run_required": sample_run_required,
        "recommended_sample_count": "Start with 1-3 small known files before unattended WebView use.",
        "required_stage_count": len(required_rows),
        "ready_stage_count": ready_stage_count,
        "manual_stage_count": manual_stage_count,
        "attention_stage_count": len(attention_rows),
        "blocked_stage_count": len(blocked_stages),
        "review_stage_count": len(review_stages),
        "blocked_stages": blocked_stages,
        "review_stages": review_stages,
        "pilot_attention": pilot_attention,
        "next_required_action": next_required_action,
        "rows": rows,
        "stop_conditions": stop_conditions,
        "summary_lines": summary_lines,
        "execution_checklist_schema": SAMPLE_VALIDATION_EXECUTION_CHECKLIST_SCHEMA,
        "execution_checklist": execution_checklist,
        "execution_required_count": len(execution_required),
        "execution_ready_count": execution_ready_count,
        "execution_manual_count": execution_manual_count,
        "execution_attention_count": len(execution_attention),
        "execution_summary_lines": execution_summary_lines,
        "safe_next_action": safe_next_action,
        "guardrail": (
            "Read-only real-media pilot plan. It does not launch work, accept outputs, clear failures, drain pending publish, "
            "rewrite manifests/sidecars, save settings, rename files, or mutate source/output/scratch media."
        ),
    }


def sample_validation_cutover_gate_payload(
    readiness: Mapping[str, Any],
    reconciliation: Mapping[str, Any],
    records: list[Mapping[str, Any]],
    worksheet_runs: Mapping[str, Any],
    pilot_plan: Mapping[str, Any],
) -> dict[str, Any]:
    """Summarize whether WebView has enough recent sample proof for operator trial.

    This is not a production cutover flag. It is deliberately conservative and
    read-only so it cannot turn historical evidence into media acceptance state.
    """

    reconciliation_rows = [
        row for row in reconciliation.get("rows", []) if isinstance(row, Mapping)
    ]
    current_record_ids = {
        _clean_text(row.get("record_id"))
        for row in reconciliation_rows
        if _clean_text(row.get("status")).casefold() == "current"
        and _clean_text(row.get("operator_decision")).casefold() == "accepted"
    }
    accepted_records = [
        record
        for record in records
        if _clean_text(record.get("operator_decision")).casefold() == "accepted"
    ]
    current_accepted_records = [
        record
        for record in accepted_records
        if _clean_text(record.get("record_id")) in current_record_ids
    ]
    required_keys = [key for key, _label, required, _action in SAMPLE_VALIDATION_ACCEPTANCE_CHECKS if required]
    recommended_keys = [key for key, _label, required, _action in SAMPLE_VALIDATION_ACCEPTANCE_CHECKS if not required]

    def checks_ready(record: Mapping[str, Any], keys: list[str]) -> bool:
        checks = record.get("checks") if isinstance(record.get("checks"), Mapping) else {}
        return bool(keys) and all(bool(checks.get(key)) for key in keys)

    current_required_ready = any(checks_ready(record, required_keys) for record in current_accepted_records)
    current_recommended_ready = any(checks_ready(record, recommended_keys) for record in current_accepted_records)
    readiness_status = _clean_text(readiness.get("operator_status")).casefold() or "not-loaded"
    reconciliation_status = _clean_text(reconciliation.get("operator_status")).casefold() or "not-loaded"
    worksheet_status = _clean_text(worksheet_runs.get("operator_status")).casefold() or "not-loaded"
    pilot_status = _clean_text(pilot_plan.get("operator_status")).casefold() or "not-loaded"
    readiness_blocked = bool(int(readiness.get("blocker_count") or 0)) or readiness_status == "blocked"
    reconciliation_blocked = bool(int(reconciliation.get("error_count") or 0)) or reconciliation_status == "blocked"
    stale_records = int(reconciliation.get("stale_count") or 0)
    review_records = int(reconciliation.get("review_count") or 0)
    worksheet_runs_count = int(worksheet_runs.get("run_count") or 0)

    rows = [
        _cutover_gate_row(
            "Backend evidence availability",
            "blocked" if readiness_blocked else "ready" if readiness.get("ready_to_record") else "review",
            f"readiness={readiness_status}; required={readiness.get('required_ready_count') or 0}/{readiness.get('required_count') or 0}; blockers={readiness.get('blocker_count') or 0}; warnings={readiness.get('warning_count') or 0}",
            _clean_text(readiness.get("safe_next_action")) or "Load Queue, Completed, Pending Publish, Diagnostics, and Settings evidence.",
        ),
        _cutover_gate_row(
            "Current accepted sample record",
            "ready" if current_accepted_records and current_required_ready else "review",
            f"accepted records={len(accepted_records)}; current accepted={len(current_accepted_records)}; required checks complete={_yes_no(current_required_ready)}",
            "Append one accepted sample record only after current Queue, Completed, Diagnostics, size, sidecar, and playback proof agree.",
        ),
        _cutover_gate_row(
            "Playback subtitle audio publish checks",
            "ready" if current_recommended_ready else "review",
            f"recommended checks complete={_yes_no(current_recommended_ready)}; required keys={len(required_keys)}; recommended keys={len(recommended_keys)}",
            "For Plex trust, manually confirm subtitles/SRT behavior, audio/default track behavior, size posture, and pending-publish final placement.",
        ),
        _cutover_gate_row(
            "Worksheet or run-note context",
            "blocked" if worksheet_status == "blocked" else "ready" if worksheet_runs_count else "review",
            f"worksheet status={worksheet_status}; runs={worksheet_runs_count}; samples={worksheet_runs.get('sample_count') or 0}; packet rows={worksheet_runs.get('packet_row_count') or 0}",
            _clean_text(worksheet_runs.get("safe_next_action")) or "Generate or update a worksheet if persistent pilot-run context is useful.",
            required=False,
        ),
        _cutover_gate_row(
            "Stale or review history",
            "blocked" if reconciliation_blocked else "review" if stale_records or review_records else "ready",
            f"reconciliation={reconciliation_status}; current={reconciliation.get('current_count') or 0}; review={review_records}; stale={stale_records}; errors={reconciliation.get('error_count') or 0}",
            _clean_text(reconciliation.get("safe_next_action")) or "Compare historical validation notes against current backend evidence.",
        ),
        _cutover_gate_row(
            "Pilot plan posture",
            "blocked" if pilot_status == "blocked" else "review" if pilot_status in {"pilot-needed", "stale-history", "review"} else "ready",
            f"pilot={pilot_status}; sample_run_required={_yes_no(pilot_plan.get('sample_run_required'))}; attention={pilot_plan.get('attention_stage_count') or 0}",
            _clean_text(pilot_plan.get("safe_next_action")) or "Run a small pilot and compare backend evidence before daily use.",
        ),
    ]
    blocked_count = sum(1 for row in rows if row.get("status") == "blocked")
    review_count = sum(1 for row in rows if row.get("status") == "review")
    ready_count = sum(1 for row in rows if row.get("status") == "ready")
    gate_ready = not blocked_count and not review_count and bool(current_accepted_records) and current_required_ready
    if blocked_count:
        operator_status = "blocked"
        safe_next_action = "Resolve blocked validation evidence before treating WebView as trustworthy for unattended work."
    elif not current_accepted_records:
        operator_status = "pilot-needed"
        safe_next_action = "Run one small known sample through backend-owned Launch, verify output/subtitle/audio/size/publish evidence, then append an accepted evidence record."
    elif review_count:
        operator_status = "review"
        safe_next_action = "Review incomplete playback/subtitle/audio/publish/worksheet/stale-history evidence before expanding WebView use."
    else:
        operator_status = "ready-for-operator-trial"
        safe_next_action = "WebView has current accepted sample evidence for a limited operator trial; keep V5 fallback and validate more media-policy changes before cutover."
    summary_lines = [
        f"WebView cutover gate: {operator_status}",
        f"Rows: ready={ready_count}; review={review_count}; blocked={blocked_count}; current accepted records={len(current_accepted_records)}",
        f"Accepted required checks complete: {_yes_no(current_required_ready)}; playback/subtitle/audio/publish checks complete: {_yes_no(current_recommended_ready)}",
        "Acceptance boundary: current accepted records are accepted sample_validation_record.v1 entries that still reconcile to current backend proof; generated worksheets are context only.",
        f"Safe next action: {safe_next_action}",
        "Boundary: this is not a production cutover switch. It is read-only evidence and cannot launch, accept, publish, drain, save settings, rename, rewrite manifests, or touch media.",
    ]
    return {
        "schema_version": SAMPLE_VALIDATION_CUTOVER_GATE_SCHEMA,
        "operator_status": operator_status,
        "gate_ready": gate_ready,
        "accepted_record_count": len(accepted_records),
        "current_accepted_record_count": len(current_accepted_records),
        "worksheet_run_count": worksheet_runs_count,
        "worksheet_sample_count": int(worksheet_runs.get("sample_count") or 0),
        "acceptance_evidence_boundary": (
            "Only accepted sample_validation_record.v1 entries that reconcile against current Queue/Completed/Pending/Diagnostics evidence count as current accepted records. "
            "Generated worksheet rows can plan or document a pilot run, but they do not satisfy cutover readiness by themselves."
        ),
        "current_required_checks_complete": current_required_ready,
        "current_recommended_checks_complete": current_recommended_ready,
        "ready_count": ready_count,
        "review_count": review_count,
        "blocked_count": blocked_count,
        "rows": rows,
        "summary_lines": summary_lines,
        "safe_next_action": safe_next_action,
        "guardrail": (
            "Read-only WebView cutover evidence. It does not approve production cutover, mark jobs complete, accept outputs, "
            "clear failures, drain pending publish, rewrite manifests/sidecars, launch work, save settings, rename files, "
            "or mutate source/output/scratch media."
        ),
    }


def sample_validation_pilot_runbook_payload(
    readiness: Mapping[str, Any],
    reconciliation: Mapping[str, Any],
    worksheet_runs: Mapping[str, Any],
    pilot_plan: Mapping[str, Any],
    cutover_gate: Mapping[str, Any],
    sample_set_guide: Mapping[str, Any],
    evidence_gap: Mapping[str, Any],
) -> dict[str, Any]:
    """Build a copyable, backend-authored runbook for the next real-media pilot.

    The packet is intentionally derived from already-loaded evidence. It gives
    the WebView shell a useful operator checklist without writing a worksheet,
    launching the pipeline, accepting records, or mutating media.
    """

    def normalize_status(value: Any) -> str:
        raw = _clean_text(value).casefold()
        if raw in {"ready", "current", "current-evidence", "sample-set-ready", "ready-for-operator-trial", "ready-looking", "evidence-present", "ready-to-record"}:
            return "ready"
        if raw in {"blocked", "error", "failed"}:
            return "blocked"
        if raw in {"not-started", "not-ready", "needs-sample", "pilot-needed", "post-run-needed", "after-proof", "needs-settings", "coverage-needed", "missing-required-evidence"}:
            return "missing"
        if raw in {"review", "stale", "stale-history", "unknown", "planned", "optional-review"}:
            return "review"
        if raw == "manual":
            return "manual"
        return raw or "unknown"

    gap_rows = {
        _clean_text(item.get("checkpoint")): item
        for item in evidence_gap.get("rows", [])
        if isinstance(item, Mapping)
    }
    execution_rows = {
        (_clean_text(item.get("phase")), _clean_text(item.get("check"))): item
        for item in pilot_plan.get("execution_checklist", [])
        if isinstance(item, Mapping)
    }

    def gap_status(checkpoint: str, fallback: Any = "") -> str:
        return normalize_status(gap_rows.get(checkpoint, {}).get("status") or fallback)

    def execution_status(phase: str, check: str, fallback: Any = "") -> str:
        return normalize_status(execution_rows.get((phase, check), {}).get("status") or fallback)

    def row(
        order: int,
        step: str,
        owner_page: str,
        status: str,
        evidence: str,
        required_evidence: list[str],
        safe_next_action: str,
        *,
        required: bool = True,
    ) -> dict[str, Any]:
        normalized = normalize_status(status)
        if normalized == "blocked":
            severity = "error"
        elif normalized in {"missing", "review", "unknown"}:
            severity = "warning"
        else:
            severity = "info"
        return {
            "order": order,
            "step": step,
            "owner_page": owner_page,
            "status": normalized,
            "severity": severity,
            "required": required,
            "evidence": _clean_text(evidence, max_chars=SAMPLE_VALIDATION_TEXT_MAX_CHARS),
            "required_evidence": [_clean_text(item, max_chars=180) for item in required_evidence if _clean_text(item)],
            "safe_next_action": _clean_text(safe_next_action, max_chars=SAMPLE_VALIDATION_TEXT_MAX_CHARS),
            "guardrail": "Read-only pilot runbook row. It cannot launch, append, accept, publish, drain, repair, save settings, rename, rewrite manifests, or touch media.",
        }

    rows = [
        row(
            1,
            "Choose one representative sample and category",
            "Home / Queue",
            gap_status("Selected sample and saved policy", pilot_plan.get("operator_status")),
            f"pilot={pilot_plan.get('operator_status') or 'not loaded'}; sample set={sample_set_guide.get('operator_status') or 'not loaded'}; selected sample stage={execution_status('Before Launch', 'Select one known sample row', 'unknown')}",
            ["selected Queue sample", "pilot category", "known expected route"],
            "Pick one small known file first, then select the matching sample category before previewing any evidence record.",
        ),
        row(
            2,
            "Confirm saved media policy before launch",
            "Settings / Launch",
            gap_status("Selected sample and saved policy", "missing"),
            f"readiness={readiness.get('operator_status') or 'not loaded'}; cutover={cutover_gate.get('operator_status') or 'not loaded'}",
            ["saved route policy", "subtitle policy", "audio policy", "size policy", "pending-publish posture"],
            "Confirm Settings are saved and Launch shows backend-owned policy evidence; do not rely on unsaved UI fields.",
        ),
        row(
            3,
            "Start the sample only through backend-owned Launch",
            "Launch",
            execution_status("Launch", "Run through backend-owned Launch only", "manual"),
            "WebView runbook has no launch command; Launch remains the explicit backend-owned start surface.",
            ["operator launch acknowledgement", "backend-owned command result", "ActiveJobs/run-log proof"],
            "Use the existing Launch start path only after steps 1-2 are satisfactory; stop if policy, route, or source safety evidence is unclear.",
            required=False,
        ),
        row(
            4,
            "Monitor running process and diagnostics",
            "Home / Diagnostics",
            gap_status("Post-run Completed and Diagnostics proof", "missing"),
            f"diagnostics/log stage={execution_status('During Run', 'Monitor ActiveJobs and run logs', 'unknown')}",
            ["ActiveJobs row while running", "bounded stdout/stderr/log evidence", "command result or failure record"],
            "While the sample runs, watch Activity, Diagnostics tail views, and command feedback for the same source/output.",
        ),
        row(
            5,
            "Verify Completed output, route, sidecar, and size",
            "Completed",
            gap_status("Post-run Completed and Diagnostics proof", "missing"),
            f"completed check={execution_status('Post-run Completed Proof', 'Verify Completed output, sidecar, manifest, route, and size', 'unknown')}",
            ["Completed output path", "route/remux-vs-encode reason", "sidecar/manifest consistency", "size-growth result"],
            "Compare source/output route metadata, sidecar/manifest, and size posture before trusting the sample.",
        ),
        row(
            6,
            "Verify final placement or Pending Publish handoff",
            "Completed / Pending Publish",
            gap_status("Final placement / Pending Publish proof", "manual"),
            "Deferred publish is optional, but final placement evidence is required whenever a sample parks or drains.",
            ["final output exists or parked payload exists", "pending/drain summary if applicable", "no silent scratch-only output"],
            "If publish is deferred, inspect Pending Publish and durable drain evidence; do not start network mutation from this runbook.",
            required=False,
        ),
        row(
            7,
            "Manually check Plex playback, subtitles, audio, and size posture",
            "Plex / Completed / Settings",
            gap_status("Manual playback / subtitle / audio checks", "review"),
            f"recommended manual checks complete={_yes_no(cutover_gate.get('current_recommended_checks_complete'))}",
            ["Plex playback result", "preferred-language SRT/retained subtitles", "audio/default-language behavior", "unexpected output growth review"],
            "Record manual playback/subtitle/audio/size observations before expanding WebView use beyond the sample.",
            required=False,
        ),
        row(
            8,
            "Preview and append evidence-only validation note",
            "Home / Sample Validation",
            gap_status("Current accepted record reconciliation", reconciliation.get("operator_status")),
            f"reconciliation={reconciliation.get('operator_status') or 'not loaded'}; current records={reconciliation.get('current_count') or 0}; worksheets={worksheet_runs.get('run_count') or 0}",
            ["current backend evidence", "operator notes", "proof strength", "decision", "sample category"],
            "Preview first, then append only if current backend evidence matches the completed sample; records never mark work complete.",
        ),
    ]

    ready_count = sum(1 for item in rows if item["status"] == "ready")
    manual_count = sum(1 for item in rows if item["status"] == "manual")
    review_count = sum(1 for item in rows if item["status"] in {"review", "unknown"})
    missing_count = sum(1 for item in rows if item["status"] == "missing")
    blocked_count = sum(1 for item in rows if item["status"] == "blocked")
    required_blockers = [
        item["step"]
        for item in rows
        if item.get("required") and item["status"] in {"blocked", "missing", "review", "unknown"}
    ]
    if blocked_count:
        operator_status = "blocked"
        safe_next_action = "Resolve blocked evidence before starting or accepting another WebView sample."
    elif required_blockers:
        operator_status = "missing-required-evidence"
        safe_next_action = f"Complete required pilot runbook evidence first: {', '.join(required_blockers)}."
    elif review_count:
        operator_status = "review"
        safe_next_action = "Required runbook evidence is mostly present; review manual/optional proof before treating WebView as daily-use ready."
    else:
        operator_status = "ready-looking"
        safe_next_action = "Run or record the next representative sample while keeping V5/manual review as fallback."

    summary_lines = [
        f"Real-media pilot runbook: {operator_status}",
        f"Steps: ready={ready_count}; manual={manual_count}; review={review_count}; missing={missing_count}; blocked={blocked_count}",
        f"Required runbook gaps: {', '.join(required_blockers) if required_blockers else 'none'}",
        f"Evidence gaps: {evidence_gap.get('operator_status') or 'not loaded'}; sample set={sample_set_guide.get('operator_status') or 'not loaded'}; cutover={cutover_gate.get('operator_status') or 'not loaded'}",
        f"Safe next action: {safe_next_action}",
        "Boundary: this runbook is read-only and copyable guidance. It cannot launch, append records, accept outputs, publish/drain, save settings, rename, rewrite manifests, or touch media.",
    ]

    markdown_lines = [
        "# Real-Media WebView Pilot Runbook",
        "",
        f"Status: {operator_status}",
        f"Safe next action: {safe_next_action}",
        "",
        "## Safety Boundary",
        "- Read-only guidance generated from loaded backend payloads.",
        "- Does not launch the pipeline, append validation records, accept outputs, publish, drain, save settings, rename files, rewrite manifests/sidecars, or mutate source/output/scratch media.",
        "- Use V5/manual review as fallback until representative real-media samples have current evidence.",
        "",
        "## Checklist",
    ]
    for item in rows:
        checkbox = "[x]" if item["status"] == "ready" else "[ ]"
        required = "required" if item.get("required") else "optional/manual"
        markdown_lines.append(
            f"{checkbox} {item['order']}. {item['step']} ({required}; {item['status']}) - Owner: {item['owner_page']}"
        )
        markdown_lines.append(f"   - Evidence: {item['evidence'] or 'not loaded'}")
        needed = "; ".join(item.get("required_evidence") or []) or "none reported"
        markdown_lines.append(f"   - Required evidence: {needed}")
        markdown_lines.append(f"   - Next: {item['safe_next_action']}")
    markdown_lines.extend(
        [
            "",
            "## Related Current Payloads",
            f"- Evidence gaps: {evidence_gap.get('operator_status') or 'not loaded'}",
            f"- Sample set guide: {sample_set_guide.get('operator_status') or 'not loaded'}",
            f"- Cutover gate: {cutover_gate.get('operator_status') or 'not loaded'}",
            f"- Reconciliation: {reconciliation.get('operator_status') or 'not loaded'}",
            f"- Generated worksheets: {worksheet_runs.get('run_count') or 0}",
        ]
    )

    return {
        "schema_version": SAMPLE_VALIDATION_PILOT_RUNBOOK_SCHEMA,
        "operator_status": operator_status,
        "ready_count": ready_count,
        "manual_count": manual_count,
        "review_count": review_count,
        "missing_count": missing_count,
        "blocked_count": blocked_count,
        "required_gap_count": len(required_blockers),
        "required_gaps": required_blockers,
        "rows": rows,
        "summary_lines": summary_lines,
        "markdown_lines": markdown_lines,
        "markdown_text": "\n".join(markdown_lines),
        "safe_next_action": safe_next_action,
        "guardrail": (
            "Read-only real-media pilot runbook. It does not launch work, append validation records, accept outputs, "
            "clear failures, drain pending publish, rewrite manifests/sidecars, save settings, rename files, or mutate source/output/scratch media."
        ),
    }


def sample_validation_sample_set_guide_payload(
    records: list[Mapping[str, Any]],
    worksheet_runs: Mapping[str, Any],
    cutover_gate: Mapping[str, Any],
    readiness: Mapping[str, Any],
    reconciliation: Mapping[str, Any],
    pilot_plan: Mapping[str, Any],
) -> dict[str, Any]:
    """Return read-only guidance for representative WebView real-media coverage.

    Validation records prove an operator checked a sample, but older records do
    not carry a required category field. This guide therefore separates
    worksheet coverage, current accepted record evidence, and category-specific
    proof instead of promoting a generic accepted record into a category pass.
    """

    worksheet_samples = _sample_set_worksheet_samples(worksheet_runs)
    accepted_records = [
        record
        for record in records
        if _clean_text(record.get("operator_decision")).casefold() == "accepted"
    ]
    current_accepted_records = _sample_set_current_accepted_records(records, reconciliation)
    reconciliation_by_id = {
        _clean_text(row.get("record_id")): row
        for row in reconciliation.get("rows", [])
        if isinstance(row, Mapping) and _clean_text(row.get("record_id"))
    }
    readiness_status = _clean_text(readiness.get("operator_status")).casefold() or "not-loaded"
    reconciliation_status = _clean_text(reconciliation.get("operator_status")).casefold() or "not-loaded"
    pilot_status = _clean_text(pilot_plan.get("operator_status")).casefold() or "not-loaded"
    cutover_status = _clean_text(cutover_gate.get("operator_status")).casefold() or "not-loaded"
    blocked = (
        readiness_status == "blocked"
        or reconciliation_status == "blocked"
        or cutover_status == "blocked"
        or bool(int(readiness.get("blocker_count") or 0))
        or bool(int(reconciliation.get("error_count") or 0))
    )
    rows = [
        _sample_set_guide_row(
            category,
            worksheet_samples,
            accepted_records,
            current_accepted_records,
            reconciliation_by_id,
            blocked=blocked,
            current_required_checks_complete=bool(cutover_gate.get("current_required_checks_complete")),
            current_recommended_checks_complete=bool(cutover_gate.get("current_recommended_checks_complete")),
        )
        for category in SAMPLE_VALIDATION_SAMPLE_SET_CATEGORIES
    ]
    required_rows = [row for row in rows if row.get("required")]
    ready_count = sum(1 for row in rows if row.get("status") == "ready")
    review_count = sum(1 for row in rows if row.get("status") == "review")
    planned_count = sum(1 for row in rows if row.get("status") == "planned")
    missing_count = sum(1 for row in rows if row.get("status") == "needs-sample")
    blocked_count = sum(1 for row in rows if row.get("status") == "blocked")
    required_ready_count = sum(1 for row in required_rows if row.get("status") == "ready")
    required_missing = [str(row.get("category") or "") for row in required_rows if row.get("status") in {"needs-sample", "planned"}]
    sample_set_ready = bool(required_rows) and required_ready_count == len(required_rows) and not blocked_count
    if blocked_count:
        operator_status = "blocked"
        safe_next_action = "Resolve blocked backend validation evidence before selecting a broader real-media pilot set."
    elif not current_accepted_records and missing_count:
        operator_status = "pilot-needed"
        safe_next_action = "Pick 3-5 representative samples, add them to a worksheet, run them through backend-owned Launch, then append accepted evidence notes."
    elif required_missing:
        operator_status = "coverage-needed"
        safe_next_action = f"Add or validate missing required pilot categories: {', '.join(required_missing)}."
    elif review_count or planned_count:
        operator_status = "review"
        safe_next_action = "Match each planned category to a current accepted validation record before treating WebView as daily-driver ready."
    else:
        operator_status = "sample-set-ready"
        safe_next_action = "Representative real-media sample categories have current evidence; keep V5 fallback and rerun samples after media-policy changes."
    summary_lines = [
        f"Recommended real-media sample set: {operator_status}",
        "Recommended samples: 3-5 small but representative files covering remux, subtitles, audio, encode/size, and publish posture.",
        f"Rows: ready={ready_count}; review={review_count}; planned={planned_count}; missing={missing_count}; blocked={blocked_count}",
        f"Required categories ready: {required_ready_count}/{len(required_rows)}; current accepted records={len(current_accepted_records)}; worksheet samples={len(worksheet_samples)}",
        f"Cutover={cutover_status}; readiness={readiness_status}; reconciliation={reconciliation_status}; pilot={pilot_status}",
        "Proof boundary: worksheet samples are planned/context rows only; ready sample categories require current accepted validation records.",
        f"Safe next action: {safe_next_action}",
        "Boundary: this guide is read-only. It cannot launch, accept outputs, rename, publish, drain pending publish, save settings, rewrite manifests/sidecars, or touch media.",
    ]
    return {
        "schema_version": SAMPLE_VALIDATION_SAMPLE_SET_GUIDE_SCHEMA,
        "operator_status": operator_status,
        "sample_set_ready": sample_set_ready,
        "recommended_sample_count": "3-5 representative files",
        "ready_count": ready_count,
        "review_count": review_count,
        "planned_count": planned_count,
        "missing_count": missing_count,
        "blocked_count": blocked_count,
        "required_ready_count": required_ready_count,
        "required_count": len(required_rows),
        "current_accepted_record_count": len(current_accepted_records),
        "worksheet_sample_count": len(worksheet_samples),
        "acceptance_evidence_boundary": (
            "Worksheet sample rows can make a category planned, but a category becomes ready only when an accepted validation record for that category remains current against backend evidence."
        ),
        "rows": rows,
        "summary_lines": summary_lines,
        "safe_next_action": safe_next_action,
        "guardrail": (
            "Read-only representative sample-set guidance. It does not prove production cutover, mark jobs complete, clear failures, "
            "drain pending publish, rewrite manifests/sidecars, launch work, save settings, rename files, or mutate source/output/scratch media."
        ),
    }


def _sample_set_current_accepted_records(
    records: list[Mapping[str, Any]],
    reconciliation: Mapping[str, Any],
) -> list[Mapping[str, Any]]:
    current_ids = {
        _clean_text(row.get("record_id"))
        for row in reconciliation.get("rows", [])
        if isinstance(row, Mapping)
        and _clean_text(row.get("status")).casefold() == "current"
        and _clean_text(row.get("operator_decision")).casefold() == "accepted"
    }
    return [
        record
        for record in records
        if _clean_text(record.get("operator_decision")).casefold() == "accepted"
        and _clean_text(record.get("record_id")) in current_ids
    ]


def _pilot_status_from_row(row: Mapping[str, Any], *, missing_status: str) -> str:
    severity = _clean_text(row.get("severity")).casefold()
    status = _clean_text(row.get("status")).casefold()
    if severity == "error" or status == "unreadable":
        return "blocked"
    if status == "ready":
        return "ready"
    if status in {"review", "empty"} or severity == "warning":
        return "review"
    if status in {"missing", "not-started"}:
        return missing_status
    return status or missing_status


def _pilot_plan_row(stage: str, status: str, evidence: str, operator_action: str, *, required: bool = True) -> dict[str, Any]:
    severity = "error" if status == "blocked" else "warning" if status not in {"ready", "manual"} else "info"
    return {
        "stage": stage,
        "status": status,
        "severity": severity,
        "required": required,
        "evidence": evidence,
        "operator_action": operator_action,
    }


def _pilot_execution_row(
    phase: str,
    check: str,
    stage_row: Mapping[str, Any],
    owner_page: str,
    backend_evidence: str,
    operator_proof: str,
    unsafe_if_ignored: str,
    *,
    required: bool = True,
) -> dict[str, Any]:
    status = _clean_text(stage_row.get("status")) or "unknown"
    severity = _clean_text(stage_row.get("severity")) or ("error" if status == "blocked" else "warning")
    evidence = _clean_text(stage_row.get("evidence")) or backend_evidence
    return {
        "phase": phase,
        "check": check,
        "status": status,
        "severity": severity,
        "required": required,
        "owner_page": owner_page,
        "backend_evidence": backend_evidence,
        "current_evidence": evidence,
        "operator_proof": operator_proof,
        "safe_next_action": _clean_text(stage_row.get("operator_action")) or operator_proof,
        "unsafe_if_ignored": unsafe_if_ignored,
        "guardrail": (
            "Read-only execution checklist. It cannot launch, accept, repair, publish, rename, rewrite manifests, save settings, "
            "or touch source/output/scratch media."
        ),
    }


def _cutover_gate_row(
    checkpoint: str,
    status: str,
    evidence: str,
    safe_next_action: str,
    *,
    required: bool = True,
) -> dict[str, Any]:
    severity = "error" if status == "blocked" else "warning" if status != "ready" else "info"
    return {
        "checkpoint": checkpoint,
        "status": status,
        "severity": severity,
        "required": required,
        "evidence": evidence,
        "safe_next_action": safe_next_action,
        "guardrail": "Read-only cutover-gate evidence; backend-owned workflow state remains authoritative.",
    }


def _sample_set_guide_row(
    category: Mapping[str, Any],
    worksheet_samples: list[Mapping[str, Any]],
    accepted_records: list[Mapping[str, Any]],
    current_accepted_records: list[Mapping[str, Any]],
    reconciliation_by_id: Mapping[str, Mapping[str, Any]],
    *,
    blocked: bool,
    current_required_checks_complete: bool,
    current_recommended_checks_complete: bool,
) -> dict[str, Any]:
    category_key = _clean_text(category.get("category_key"))
    matching_samples = [
        sample
        for sample in worksheet_samples
        if _sample_set_category_matches(category_key, _clean_text(sample.get("match_text"), max_chars=2000))
    ]
    accepted_matching_records = [
        record
        for record in accepted_records
        if _sample_record_matches_category(category_key, record)
    ]
    matching_records = [
        record
        for record in current_accepted_records
        if _sample_record_matches_category(category_key, record)
    ]
    stale_record_count = 0
    review_record_count = 0
    for record in accepted_matching_records:
        reconciliation = reconciliation_by_id.get(_clean_text(record.get("record_id")), {})
        status = _clean_text(reconciliation.get("status")).casefold()
        if status == "stale":
            stale_record_count += 1
        elif status and status != "current":
            review_record_count += 1
        elif not status:
            review_record_count += 1
    if blocked:
        status = "blocked"
        severity = "error"
        safe_next_action = "Resolve blocked backend evidence before using this sample category."
    elif matching_records and current_required_checks_complete and (current_recommended_checks_complete or category_key == "h264-remux-safe"):
        status = "ready"
        severity = "info"
        safe_next_action = "Keep this category in the regression set and rerun it after route, subtitle, audio, publish, or settings changes."
    elif accepted_matching_records:
        status = "review"
        severity = "warning"
        safe_next_action = "An accepted category record exists, but current backend reconciliation is not clean; re-check Queue, Completed, Pending Publish, and Diagnostics proof."
    elif matching_samples and current_accepted_records:
        status = "review"
        severity = "warning"
        safe_next_action = "Open the matching worksheet/sample and append or update an accepted validation record whose label or notes identify this category."
    elif matching_samples:
        status = "planned"
        severity = "warning"
        safe_next_action = "Run this planned worksheet sample through backend-owned Launch, then capture Queue, Completed, Diagnostics, playback, and size evidence."
    else:
        status = "needs-sample"
        severity = "warning" if category.get("required") else "info"
        safe_next_action = _clean_text(category.get("operator_action")) or "Add a representative sample for this category."
    sample_labels = _dedupe(
        [
            _clean_text(sample.get("source_leaf")) or _clean_text(sample.get("source_path"), max_chars=200)
            for sample in matching_samples
        ]
    )[:3]
    record_labels = _dedupe(
        [
            _clean_text(record.get("sample_label")) or _safe_leaf(_clean_text(record.get("source_path"), max_chars=2000))
            for record in accepted_matching_records
        ]
    )[:3]
    evidence = (
        f"worksheet matches={len(matching_samples)}; accepted category records={len(accepted_matching_records)}; current accepted category records={len(matching_records)}; stale category records={stale_record_count}; review category records={review_record_count}; "
        f"generic current accepted records={len(current_accepted_records)}; required checks complete={_yes_no(current_required_checks_complete)}; "
        f"recommended checks complete={_yes_no(current_recommended_checks_complete)}"
    )
    return {
        "category_key": category_key,
        "category": _clean_text(category.get("category")),
        "status": status,
        "severity": severity,
        "required": bool(category.get("required")),
        "worksheet_sample_count": len(matching_samples),
        "accepted_record_match_count": len(accepted_matching_records),
        "current_record_match_count": len(matching_records),
        "stale_record_match_count": stale_record_count,
        "review_record_match_count": review_record_count,
        "generic_current_accepted_record_count": len(current_accepted_records),
        "sample_examples": sample_labels,
        "record_examples": record_labels,
        "evidence_goal": _clean_text(category.get("evidence_goal"), max_chars=1000),
        "evidence": evidence,
        "operator_action": _clean_text(category.get("operator_action"), max_chars=1000),
        "owner_pages": list(category.get("owner_pages") or ()),
        "safe_next_action": safe_next_action,
        "proof_boundary": (
            "Category status prefers explicit sample_category records. Older validation records without a category are matched only from label, path, notes, or evidence text."
        ),
        "guardrail": "Read-only sample-set row. It cannot launch work, mutate media, accept outputs, publish, rename, or save settings.",
    }


def _sample_set_record_text(record: Mapping[str, Any]) -> str:
    parts = [
        _clean_text(record.get("sample_category")),
        _clean_text(record.get("sample_label")),
        _clean_text(record.get("source_path"), max_chars=2000),
        _clean_text(record.get("output_path"), max_chars=2000),
        _clean_text(record.get("operator_notes"), max_chars=2000),
    ]
    evidence = record.get("evidence")
    if isinstance(evidence, Mapping):
        for values in evidence.values():
            if isinstance(values, list):
                for item in values[:5]:
                    if isinstance(item, Mapping):
                        parts.extend([_clean_text(item.get("field")), _clean_text(item.get("value"), max_chars=1000)])
    return " ".join(parts)


def _sample_record_matches_category(category_key: str, record: Mapping[str, Any]) -> bool:
    explicit = _clean_text(record.get("sample_category")).casefold()
    if explicit:
        return explicit == category_key.casefold()
    return _sample_set_category_matches(category_key, _sample_set_record_text(record))


def _sample_set_category_matches(category_key: str, raw_text: str) -> bool:
    text = f" {raw_text.casefold().replace('_', ' ').replace('-', ' ').replace('.', ' ')} "
    compact = raw_text.casefold()
    if category_key and category_key.casefold() in compact:
        return True
    if category_key == "h264-remux-safe":
        return any(token in text for token in (" h264 ", " h 264 ", " avc ")) and any(
            token in text for token in (" remux ", " copy ", " direct play ", " direct stream ")
        )
    if category_key == "subtitle-srt-generation":
        return (" subtitle " in text or any(token in text for token in (" ass ", " ssa ", " tx3g ", " pgs ", " bdpgs "))) and " srt " in text
    if category_key == "audio-routing":
        return any(token in text for token in (" audio ", " channel ", " passthrough ", " downmix ", " language ", " aac ", " ac3 ", " eac3 ", " flac "))
    if category_key == "encode-size-policy":
        return any(token in text for token in (" encode ", " transcode ", " hevc ", " x265 ", " nvenc ", " size ", " growth ", " bitrate "))
    if category_key == "deferred-publish":
        return any(token in text for token in (" deferred ", " pending ", " publish ", " drain ", " final placement ", " parked "))
    return False


def _safe_leaf(raw_path: str) -> str:
    text = _clean_text(raw_path, max_chars=2000)
    if not text:
        return ""
    try:
        return Path(text).name
    except (OSError, ValueError):
        return text


def _clean_text(value: Any, *, max_chars: int = SAMPLE_VALIDATION_TEXT_MAX_CHARS) -> str:
    text = "" if value is None else str(value)
    text = " ".join(text.replace("\r", " ").replace("\n", " ").split())
    return text[:max_chars]


def _yes_no(value: Any) -> str:
    return "yes" if bool(value) else "no"


def _dedupe(items: list[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for item in items:
        text = str(item or "").strip()
        if text and text not in seen:
            result.append(text)
            seen.add(text)
    return result
