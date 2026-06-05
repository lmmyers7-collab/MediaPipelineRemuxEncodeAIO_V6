from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .readiness import SAMPLE_VALIDATION_ACCEPTANCE_CHECKS


SAMPLE_VALIDATION_EVIDENCE_KEYS = ("queue", "completed", "pending_publish", "diagnostics", "commands")
SAMPLE_VALIDATION_EVIDENCE_PACKET_SCHEMA = "desktop_sample_validation_evidence_packet.v1"
SAMPLE_VALIDATION_POST_RUN_CAPTURE_SCHEMA = "desktop_sample_validation_post_run_capture.v1"
SAMPLE_VALIDATION_TEXT_MAX_CHARS = 600


def sample_validation_evidence_packet_payload(
    record: Mapping[str, Any],
    current_evidence: Mapping[str, Any],
    append_readiness: Mapping[str, Any],
) -> dict[str, Any]:
    """Build an operator-facing proof packet for one proposed real-media sample.

    The packet is derived from the already-normalized record, current evidence,
    and append-readiness rows. It does not perform additional media probing or
    create acceptance state.
    """

    checks = record.get("checks") if isinstance(record.get("checks"), Mapping) else {}
    current_matches = current_evidence.get("matches") if isinstance(current_evidence.get("matches"), Mapping) else {}
    current_status = _clean_text(current_evidence.get("status")).casefold() or "unknown"
    current_severity = _clean_text(current_evidence.get("severity")).casefold() or "warning"
    append_status = _clean_text(append_readiness.get("operator_status")).casefold() or "unknown"
    append_allowed = bool(append_readiness.get("append_allowed"))
    accepted_ready = bool(append_readiness.get("accepted_ready"))
    decision = _clean_text(record.get("operator_decision")).casefold() or "unknown"
    required_checks = [item for item in SAMPLE_VALIDATION_ACCEPTANCE_CHECKS if item[2]]
    recommended_checks = [item for item in SAMPLE_VALIDATION_ACCEPTANCE_CHECKS if not item[2]]
    required_checked = sum(1 for key, _label, _required, _action in required_checks if bool(checks.get(key)))
    recommended_checked = sum(1 for key, _label, _required, _action in recommended_checks if bool(checks.get(key)))
    evidence_counts = {
        key: len(_record_evidence_list(record, key))
        for key in SAMPLE_VALIDATION_EVIDENCE_KEYS
    }
    rows = [
        _evidence_packet_row(
            "Sample identity",
            "ready" if (_clean_text(record.get("source_path")) or _clean_text(record.get("output_path"))) else "blocked",
            f"sample={_clean_text(record.get('sample_label')) or 'not labeled'}; source={_clean_text(record.get('source_path')) or '(empty)'}; output={_clean_text(record.get('output_path')) or '(empty)'}; proof={_clean_text(record.get('proof_strength')) or 'unknown'}",
            "Confirm this is the intended real-media sample before launch, playback, or evidence append.",
            owner_page="Home / Sample Validation",
        ),
        _evidence_packet_row(
            "Queue route proof",
            "ready" if bool(checks.get("queue_route_checked") and current_matches.get("queue_source")) else "review",
            f"checked={_yes_no(checks.get('queue_route_checked'))}; current_queue_match={_yes_no(current_matches.get('queue_source'))}; evidence_rows={evidence_counts.get('queue', 0)}",
            "Open Queue and verify source path, remux/encode route, route reason, blocked state, and duplicate-title posture for this sample.",
            owner_page="Queue",
        ),
        _evidence_packet_row(
            "Completed output and sidecar proof",
            "ready" if bool(checks.get("completed_output_checked") and checks.get("sidecar_manifest_checked") and current_matches.get("completed_output")) else "review",
            f"completed_checked={_yes_no(checks.get('completed_output_checked'))}; sidecar_checked={_yes_no(checks.get('sidecar_manifest_checked'))}; current_completed_output_match={_yes_no(current_matches.get('completed_output'))}; evidence_rows={evidence_counts.get('completed', 0)}",
            "After the run, verify Completed output path, sidecar/manifest fields, route reason, encoder, and file existence for this exact sample.",
            owner_page="Completed",
        ),
        _evidence_packet_row(
            "Diagnostics and run-log proof",
            "ready" if bool((checks.get("diagnostics_checked") or checks.get("ffmpeg_log_checked")) and current_matches.get("diagnostics_source_or_output")) else "review",
            f"diagnostics_checked={_yes_no(checks.get('diagnostics_checked') or checks.get('ffmpeg_log_checked'))}; current_log_match={_yes_no(current_matches.get('diagnostics_source_or_output'))}; evidence_rows={evidence_counts.get('diagnostics', 0)}",
            "Read bounded stderr/stdout/run-log evidence for the same source/output before accepting or rerunning the sample.",
            owner_page="Diagnostics",
        ),
        _evidence_packet_row(
            "Pending Publish posture",
            "review" if bool(current_matches.get("pending_source_or_output")) else ("ready" if bool(checks.get("pending_publish_checked")) else "manual"),
            f"pending_checked={_yes_no(checks.get('pending_publish_checked'))}; current_pending_match={_yes_no(current_matches.get('pending_source_or_output'))}; evidence_rows={evidence_counts.get('pending_publish', 0)}",
            "If deferred publish is involved, verify parked payload, destination, manifest, sidecars, recovery dry-run, and drain state.",
            owner_page="Pending Publish",
            required=False,
        ),
        _evidence_packet_row(
            "Playback, subtitle, audio, and size proof",
            "ready" if bool(checks.get("subtitle_checked") and checks.get("audio_checked") and checks.get("size_growth_checked")) else "review",
            f"subtitle={_yes_no(checks.get('subtitle_checked'))}; audio={_yes_no(checks.get('audio_checked'))}; size={_yes_no(checks.get('size_growth_checked'))}",
            "Manually verify Plex playback, preferred-language subtitles/SRT behavior, retained originals, audio/default track behavior, and size-growth policy.",
            owner_page="Player / Completed / Settings",
        ),
        _evidence_packet_row(
            "Evidence record readiness",
            "ready" if accepted_ready else ("blocked" if not append_allowed else "review"),
            f"decision={decision}; append_status={append_status}; append_allowed={_yes_no(append_allowed)}; accepted_ready={_yes_no(accepted_ready)}; current_status={current_status} ({current_severity})",
            _clean_text(append_readiness.get("safe_next_action")) or "Preview evidence and complete required checks before appending a note.",
            owner_page="Home / Sample Validation",
        ),
    ]
    blocked_count = sum(1 for row in rows if row.get("status") == "blocked")
    review_count = sum(1 for row in rows if row.get("status") == "review")
    ready_count = sum(1 for row in rows if row.get("status") == "ready")
    if blocked_count:
        operator_status = "blocked"
        safe_next_action = "Resolve blocked sample evidence rows before appending or trusting this pilot."
    elif accepted_ready:
        operator_status = "pilot-evidence-ready"
        safe_next_action = "Append only after manual playback/subtitle/audio/size review agrees; this packet is still not automatic acceptance."
    elif append_status == "review-before-append" or review_count:
        operator_status = "review-before-append"
        safe_next_action = _clean_text(append_readiness.get("safe_next_action")) or "Resolve review rows before appending an accepted evidence note."
    else:
        operator_status = append_status
        safe_next_action = _clean_text(append_readiness.get("safe_next_action")) or "Use this packet as operator evidence only."
    stop_conditions = [
        "Stop if Queue route proof and Completed output proof do not refer to the same source/output.",
        "Stop if Diagnostics/run logs do not contain the same source/output after the sample run.",
        "Stop if Pending Publish shows a parked/missing/do-not-drain state that is not understood.",
        "Stop if subtitle, audio, size, or playback behavior disagrees with saved policy expectations.",
    ]
    summary_lines = [
        f"Pilot evidence packet: {operator_status}",
        f"Rows: ready={ready_count}; review={review_count}; blocked={blocked_count}; required checks={required_checked}/{len(required_checks)}; recommended checks={recommended_checked}/{len(recommended_checks)}",
        f"Current backend matches: {_clean_text(current_evidence.get('evidence')) or 'not reported'}",
        f"Safe next action: {safe_next_action}",
        "Boundary: this packet is read-only operator evidence guidance and cannot accept output, mark jobs complete, launch work, publish/drain, save settings, rename, rewrite manifests, or touch media.",
    ]
    return {
        "schema_version": SAMPLE_VALIDATION_EVIDENCE_PACKET_SCHEMA,
        "operator_status": operator_status,
        "sample_label": _clean_text(record.get("sample_label")),
        "source_path": _clean_text(record.get("source_path")),
        "output_path": _clean_text(record.get("output_path")),
        "proof_strength": _clean_text(record.get("proof_strength")),
        "operator_decision": decision,
        "evidence_counts": evidence_counts,
        "required_checked_count": required_checked,
        "required_check_count": len(required_checks),
        "recommended_checked_count": recommended_checked,
        "recommended_check_count": len(recommended_checks),
        "ready_count": ready_count,
        "review_count": review_count,
        "blocked_count": blocked_count,
        "rows": rows,
        "stop_conditions": stop_conditions,
        "summary_lines": summary_lines,
        "safe_next_action": safe_next_action,
        "guardrail": (
            "Read-only pilot evidence packet. It does not mark jobs complete, accept outputs, clear failures, drain pending publish, "
            "rewrite manifests/sidecars, launch work, save settings, rename files, or mutate source/output/scratch media."
        ),
    }


def sample_validation_post_run_capture_payload(
    record: Mapping[str, Any],
    current_evidence: Mapping[str, Any],
    append_readiness: Mapping[str, Any],
    evidence_packet: Mapping[str, Any],
) -> dict[str, Any]:
    """Build a copyable post-run evidence capture sheet for Preview Record.

    This is generated from the proposed validation record and bounded current
    evidence. It does not create files or change whether append is allowed.
    """

    checks = record.get("checks") if isinstance(record.get("checks"), Mapping) else {}
    current_matches = current_evidence.get("matches") if isinstance(current_evidence.get("matches"), Mapping) else {}
    missing_current = [
        _clean_text(item, max_chars=160)
        for item in current_evidence.get("missing_current_evidence", []) or []
        if _clean_text(item)
    ]
    evidence_counts = evidence_packet.get("evidence_counts") if isinstance(evidence_packet.get("evidence_counts"), Mapping) else {}
    append_status = _clean_text(append_readiness.get("operator_status")).casefold() or "unknown"
    decision = _clean_text(record.get("operator_decision")).casefold() or "unknown"

    def row(
        checkpoint: str,
        owner_page: str,
        status: str,
        capture_prompt: str,
        captured_evidence: str,
        missing_capture: list[str],
        safe_next_action: str,
        *,
        required_for_acceptance: bool = True,
    ) -> dict[str, Any]:
        normalized = _clean_text(status).casefold() or "unknown"
        if normalized == "checked":
            normalized = "ready"
        if normalized in {"blocked", "error", "failed"}:
            severity = "error"
        elif normalized in {"review", "missing", "unknown", "manual"}:
            severity = "warning"
        else:
            severity = "info"
        return {
            "checkpoint": checkpoint,
            "owner_page": owner_page,
            "status": normalized,
            "severity": severity,
            "required_for_acceptance": required_for_acceptance,
            "capture_prompt": _clean_text(capture_prompt, max_chars=SAMPLE_VALIDATION_TEXT_MAX_CHARS),
            "captured_evidence": _clean_text(captured_evidence, max_chars=SAMPLE_VALIDATION_TEXT_MAX_CHARS),
            "missing_capture": [_clean_text(item, max_chars=180) for item in missing_capture if _clean_text(item)],
            "safe_next_action": _clean_text(safe_next_action, max_chars=SAMPLE_VALIDATION_TEXT_MAX_CHARS),
            "guardrail": "Read-only post-run capture row. It cannot launch, append, accept, publish, drain, repair, save settings, rename, rewrite manifests, or touch media.",
        }

    queue_ready = bool(checks.get("queue_route_checked") and current_matches.get("queue_source"))
    completed_ready = bool(checks.get("completed_output_checked") and checks.get("sidecar_manifest_checked") and current_matches.get("completed_output"))
    diagnostics_ready = bool((checks.get("diagnostics_checked") or checks.get("ffmpeg_log_checked")) and current_matches.get("diagnostics_source_or_output"))
    pending_current = bool(current_matches.get("pending_source_or_output"))
    pending_checked = bool(checks.get("pending_publish_checked"))
    subtitle_ready = bool(checks.get("subtitle_checked"))
    audio_ready = bool(checks.get("audio_checked"))
    size_ready = bool(checks.get("size_growth_checked"))
    append_ready = bool(append_readiness.get("accepted_ready"))

    rows = [
        row(
            "Sample identity and category",
            "Home / Sample Validation",
            "ready" if (_clean_text(record.get("source_path")) or _clean_text(record.get("output_path"))) else "blocked",
            "Record the exact source/output pair, proof strength, pilot category, and operator decision.",
            f"sample={_clean_text(record.get('sample_label')) or '(none)'}; category={_clean_text(record.get('sample_category')) or 'general'}; source={_clean_text(record.get('source_path')) or '(empty)'}; output={_clean_text(record.get('output_path')) or '(empty)'}; decision={decision}; proof={_clean_text(record.get('proof_strength')) or 'unknown'}",
            [] if (_clean_text(record.get("source_path")) or _clean_text(record.get("output_path"))) else ["source or output path"],
            "Confirm this preview is for the same file that was actually processed before appending evidence.",
        ),
        row(
            "Remux vs encode decision",
            "Queue / Completed",
            "ready" if queue_ready else "review",
            "Capture the route, route reason, blocked state, and whether the decision matched the intended Plex/media policy.",
            f"queue_checked={_yes_no(checks.get('queue_route_checked'))}; current_queue_match={_yes_no(current_matches.get('queue_source'))}; queue_evidence_rows={evidence_counts.get('queue', 0)}",
            [] if queue_ready else ["Queue source/route proof", "route reason"],
            "Compare Queue route intent and Completed route metadata before treating remux/encode behavior as proven.",
        ),
        row(
            "Completed output and sidecar",
            "Completed",
            "ready" if completed_ready else "review",
            "Capture final output path, output existence, sidecar/manifest agreement, route metadata, and output size posture.",
            f"completed_checked={_yes_no(checks.get('completed_output_checked'))}; sidecar_checked={_yes_no(checks.get('sidecar_manifest_checked'))}; current_completed_output_match={_yes_no(current_matches.get('completed_output'))}; completed_evidence_rows={evidence_counts.get('completed', 0)}",
            [] if completed_ready else ["Completed output proof", "sidecar/manifest proof"],
            "Inspect the selected Completed row and sidecar/manifest before appending an accepted validation note.",
        ),
        row(
            "Diagnostics and FFmpeg logs",
            "Diagnostics",
            "ready" if diagnostics_ready else "review",
            "Capture bounded stdout/stderr/run-log proof for the same source/output and any FFmpeg warnings that affect trust.",
            f"diagnostics_checked={_yes_no(checks.get('diagnostics_checked') or checks.get('ffmpeg_log_checked'))}; current_log_match={_yes_no(current_matches.get('diagnostics_source_or_output'))}; diagnostics_evidence_rows={evidence_counts.get('diagnostics', 0)}",
            [] if diagnostics_ready else ["Diagnostics or run-log proof"],
            "Read Diagnostics tail/open targets for the matching source/output before accepting or rerunning.",
        ),
        row(
            "Pending Publish or final placement",
            "Pending Publish / Completed",
            "review" if pending_current else ("ready" if pending_checked else "manual"),
            "Capture whether the output is final, parked, drained, or pending; include durable drain proof when publish was deferred.",
            f"pending_checked={_yes_no(pending_checked)}; current_pending_match={_yes_no(pending_current)}; pending_evidence_rows={evidence_counts.get('pending_publish', 0)}",
            ["pending/final-placement proof"] if pending_current or not pending_checked else [],
            "If this sample is parked or drained, inspect Pending Publish, drain summary, Completed proof, and logs before recording acceptance.",
            required_for_acceptance=False,
        ),
        row(
            "Subtitle behavior",
            "Completed / Settings / Player",
            "ready" if subtitle_ready else "review",
            "Capture preferred-language subtitle-to-SRT behavior, retained originals, dropped subtitle policy, and manual-review failures.",
            f"subtitle_checked={_yes_no(subtitle_ready)}",
            [] if subtitle_ready else ["preferred-language subtitle/SRT behavior"],
            "Manually verify subtitle tracks in Plex/player and compare against saved subtitle policy.",
            required_for_acceptance=False,
        ),
        row(
            "Audio behavior",
            "Completed / Settings / Player",
            "ready" if audio_ready else "review",
            "Capture passthrough/transcode decision, default-language behavior, track retention, and channel/downmix result.",
            f"audio_checked={_yes_no(audio_ready)}",
            [] if audio_ready else ["audio/default-language behavior"],
            "Manually verify audio tracks/default behavior in Plex/player and compare against saved audio policy.",
            required_for_acceptance=False,
        ),
        row(
            "Output size posture",
            "Completed / Settings",
            "ready" if size_ready else "review",
            "Capture source/output size ratio, backend size-policy mode, exceeded/advisory status, and whether output growth is acceptable.",
            f"size_growth_checked={_yes_no(size_ready)}",
            [] if size_ready else ["source/output size comparison", "size-policy result"],
            "Compare Completed size-policy evidence and real output size before treating the encode/remux decision as safe.",
        ),
        row(
            "Append decision",
            "Home / Sample Validation",
            "ready" if append_ready else ("blocked" if not bool(append_readiness.get("append_allowed")) else "review"),
            "Capture final operator decision and only append accepted evidence when required proof is current and manual checks agree.",
            f"append_status={append_status}; append_allowed={_yes_no(append_readiness.get('append_allowed'))}; accepted_ready={_yes_no(append_ready)}; current_evidence={_clean_text(current_evidence.get('status')) or 'unknown'}",
            [] if append_ready else list(append_readiness.get("required_acceptance_gaps") or missing_current or ["append readiness review"]),
            _clean_text(append_readiness.get("safe_next_action")) or "Preview first, then append only if current backend evidence and manual checks agree.",
        ),
    ]

    ready_count = sum(1 for item in rows if item["status"] == "ready")
    manual_count = sum(1 for item in rows if item["status"] == "manual")
    review_count = sum(1 for item in rows if item["status"] in {"review", "unknown"})
    blocked_count = sum(1 for item in rows if item["status"] == "blocked")
    required_gaps = [
        item["checkpoint"]
        for item in rows
        if item.get("required_for_acceptance") and item["status"] in {"blocked", "review", "unknown"}
    ]
    if blocked_count:
        operator_status = "blocked"
        safe_next_action = "Resolve blocked capture rows before appending sample-validation evidence."
    elif required_gaps:
        operator_status = "review-before-append"
        safe_next_action = f"Capture or verify required post-run evidence first: {', '.join(required_gaps)}."
    elif append_ready:
        operator_status = "ready-to-record"
        safe_next_action = "Append evidence only after manual playback/subtitle/audio/size review agrees with the preview."
    else:
        operator_status = append_status
        safe_next_action = _clean_text(append_readiness.get("safe_next_action")) or "Review capture rows before appending."

    summary_lines = [
        f"Post-run evidence capture: {operator_status}",
        f"Rows: ready={ready_count}; manual={manual_count}; review={review_count}; blocked={blocked_count}",
        f"Required capture gaps: {', '.join(required_gaps) if required_gaps else 'none'}",
        f"Current evidence: {_clean_text(current_evidence.get('evidence')) or 'not reported'}",
        f"Safe next action: {safe_next_action}",
        "Boundary: this capture packet is read-only/copyable guidance and cannot append, accept output, launch work, publish/drain, save settings, rename, rewrite manifests, or touch media.",
    ]
    markdown_lines = [
        "# Real-Media Post-Run Evidence Capture",
        "",
        f"Status: {operator_status}",
        f"Sample: {_clean_text(record.get('sample_label')) or '(none)'}",
        f"Source: {_clean_text(record.get('source_path')) or '(empty)'}",
        f"Output: {_clean_text(record.get('output_path')) or '(empty)'}",
        f"Pilot category: {_clean_text(record.get('sample_category')) or 'general'}",
        f"Decision: {decision}",
        "",
        "## Capture Checklist",
    ]
    for item in rows:
        checkbox = "[x]" if item["status"] == "ready" else "[ ]"
        required = "required" if item.get("required_for_acceptance") else "optional/manual"
        markdown_lines.append(f"{checkbox} {item['checkpoint']} ({required}; {item['status']}) - Owner: {item['owner_page']}")
        markdown_lines.append(f"   - Capture: {item['capture_prompt']}")
        markdown_lines.append(f"   - Evidence: {item['captured_evidence'] or 'not loaded'}")
        missing = "; ".join(item.get("missing_capture") or []) or "none"
        markdown_lines.append(f"   - Missing: {missing}")
        markdown_lines.append(f"   - Next: {item['safe_next_action']}")
    markdown_lines.extend(
        [
            "",
            "## Boundary",
            "- This packet is copied from Preview Record output only.",
            "- It does not append evidence, mark jobs complete, clear failures, publish/drain, save settings, rename files, rewrite manifests/sidecars, or mutate media.",
        ]
    )

    return {
        "schema_version": SAMPLE_VALIDATION_POST_RUN_CAPTURE_SCHEMA,
        "operator_status": operator_status,
        "sample_label": _clean_text(record.get("sample_label")),
        "sample_category": _clean_text(record.get("sample_category")),
        "source_path": _clean_text(record.get("source_path")),
        "output_path": _clean_text(record.get("output_path")),
        "ready_count": ready_count,
        "manual_count": manual_count,
        "review_count": review_count,
        "blocked_count": blocked_count,
        "required_gap_count": len(required_gaps),
        "required_gaps": required_gaps,
        "rows": rows,
        "summary_lines": summary_lines,
        "markdown_lines": markdown_lines,
        "markdown_text": "\n".join(markdown_lines),
        "safe_next_action": safe_next_action,
        "guardrail": (
            "Read-only post-run evidence capture packet. It does not append validation records, mark jobs complete, accept outputs, "
            "clear failures, drain pending publish, rewrite manifests/sidecars, launch work, save settings, rename files, or mutate source/output/scratch media."
        ),
    }


def _evidence_packet_row(
    checkpoint: str,
    status: str,
    evidence: str,
    operator_action: str,
    *,
    owner_page: str,
    required: bool = True,
) -> dict[str, Any]:
    severity = "error" if status == "blocked" else "warning" if status not in {"ready", "manual"} else "info"
    return {
        "checkpoint": checkpoint,
        "status": status,
        "severity": severity,
        "required": required,
        "owner_page": owner_page,
        "evidence": evidence,
        "operator_action": operator_action,
    }


def _record_evidence_list(record: Mapping[str, Any], key: str) -> list[Any]:
    evidence = record.get("evidence")
    if not isinstance(evidence, Mapping):
        return []
    value = evidence.get(key)
    return value if isinstance(value, list) else []


def _clean_text(value: Any, *, max_chars: int = SAMPLE_VALIDATION_TEXT_MAX_CHARS) -> str:
    text = "" if value is None else str(value)
    text = " ".join(text.replace("\r", " ").replace("\n", " ").split())
    return text[:max_chars]


def _yes_no(value: Any) -> str:
    return "yes" if bool(value) else "no"
