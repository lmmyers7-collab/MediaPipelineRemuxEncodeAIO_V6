from __future__ import annotations

from datetime import datetime
import json
from json import JSONDecodeError
from pathlib import Path
from typing import Any, Iterable, Mapping


DIAGNOSTICS_STATE_SUMMARY_SCHEMA_VERSION = "desktop_diagnostics_state_summary.v1"
DIAGNOSTICS_STATE_SUMMARY_TARGETS: tuple[str, ...] = (
    "active_jobs",
    "queue_snapshot",
    "completed_manifest",
    "pending_publish",
    "latest_failure_json",
    "failed_reports",
    "failed_markers",
    "run_logs",
    "last_stderr_log",
    "sample_validation_log",
    "state",
)
DIAGNOSTICS_STATE_SUMMARY_JSON_MAX_BYTES = 1_048_576
DIAGNOSTICS_STATE_SUMMARY_TEXT_MAX_BYTES = 262_144
DIAGNOSTICS_STATE_SUMMARY_DIR_SCAN_LIMIT = 500
DIAGNOSTICS_STATE_SUMMARY_RECENT_LIMIT = 10
DIAGNOSTICS_STATE_SUMMARY_FACT_LIMIT = 12
DIAGNOSTICS_STATE_SUMMARY_TAIL_TARGETS: tuple[str, ...] = (
    "queue_snapshot",
    "completed_manifest",
    "latest_failure_json",
    "last_stderr_log",
    "sample_validation_log",
)
DIAGNOSTICS_SETTINGS_TOOL_PATH_KEYS: tuple[str, ...] = (
    "ConvertBdpgsToSrt",
    "BdpgsOcrToolPath",
    "BdpgsOcrTessdataPath",
    "AllowSystemTools",
)
DIAGNOSTICS_RECOVERY_READY_STATUSES: tuple[str, ...] = (
    "ok",
    "resolved",
    "ignored",
    "complete",
    "completed",
    "closed",
    "done",
)

DIAGNOSTICS_STATE_TARGET_GUIDANCE: dict[str, str] = {
    "active_jobs": "ActiveJobs is the first stop when Close Readiness is blocked or a process looks orphaned.",
    "queue_snapshot": "Queue Snapshot explains what the next launch would process; stale or malformed data can make queue state look wrong.",
    "completed_manifest": "Completed Manifest explains processed outputs; malformed records can hide completed work or trigger false reruns.",
    "pending_publish": "Pending Publish holds parked outputs; review this before rerunning files that may already be waiting to drain.",
    "latest_failure_json": "Latest Failure JSON gives the newest structured failure classification for manual review.",
    "failed_reports": "Failed Reports keeps detailed failure artifacts for operator-required and transient failures.",
    "failed_markers": "Failure Markers can suppress or classify repeated source failures until reviewed.",
    "run_logs": "Run Logs contain stdout/stderr context for launch, FFmpeg, publish, and audit failures.",
    "last_stderr_log": "Last Stderr is usually the fastest place to confirm FFmpeg, PowerShell, copy, or validation errors.",
    "sample_validation_log": "Sample Validation Log keeps operator-written WebView/Tauri sample-run evidence; it never changes processing state.",
    "state": "State Folder contains runtime progress and control artifacts; inspect it before clearing stale runtime files.",
}

DIAGNOSTICS_STATE_TARGET_RECOVERY_STAGE: dict[str, str] = {
    "active_jobs": "process_lifecycle",
    "queue_snapshot": "queue_launch_readiness",
    "completed_manifest": "completed_output_proof",
    "pending_publish": "pending_publish_validation",
    "latest_failure_json": "failure_triage",
    "failed_reports": "failure_triage",
    "failed_markers": "failure_triage",
    "run_logs": "runtime_log_evidence",
    "last_stderr_log": "runtime_log_evidence",
    "sample_validation_log": "operator_validation_evidence",
    "state": "runtime_state_container",
}

DIAGNOSTICS_STATE_TARGET_IGNORE_RISK: dict[str, str] = {
    "active_jobs": "Ignoring stale or malformed ActiveJobs can make an active FFmpeg/PowerShell process look safe to close.",
    "queue_snapshot": "Ignoring queue snapshot issues can hide runnable work or cause an operator to rerun files that are already excluded.",
    "completed_manifest": "Ignoring completed-manifest issues can produce false reruns, duplicate outputs, or stale sidecar decisions.",
    "pending_publish": "Ignoring pending-publish issues can drain incomplete parked outputs or rerun files already waiting to publish.",
    "latest_failure_json": "Ignoring latest-failure issues can misclassify operator-required failures as transient noise.",
    "failed_reports": "Ignoring failed-report issues can hide the failure evidence needed for safe retry decisions.",
    "failed_markers": "Ignoring marker issues can keep bad files suppressed or repeatedly retry files that need manual review.",
    "run_logs": "Ignoring run-log issues can hide tool exits, file locks, copy failures, and publish errors.",
    "last_stderr_log": "Ignoring Last Stderr can miss the most recent FFmpeg, copy, PowerShell, or validation failure.",
    "sample_validation_log": "Ignoring stale sample validation evidence can make old operator notes look like current media proof.",
    "state": "Ignoring State folder issues can make runtime pages disagree about active work, progress, queue, and publish state.",
}


def diagnostics_should_include_settings_tool_path_evidence(config: Mapping[str, Any] | None) -> bool:
    if not isinstance(config, Mapping):
        return False
    return any(key in config for key in DIAGNOSTICS_SETTINGS_TOOL_PATH_KEYS)


def diagnostics_operator_status_state(operator_status: str, status: str = "") -> str:
    normalized = str(operator_status or "").strip().casefold().replace("_", " ")
    artifact_status = str(status or "").strip().casefold().replace("_", " ")
    if normalized in {"blocked", "error", "critical", "failed"}:
        return "blocked"
    if normalized in {"review", "not available", "unavailable"}:
        return "warning"
    if normalized == "ready":
        return "ready"
    if normalized == "active":
        return "running"
    if normalized == "empty":
        return "empty"
    if normalized == "unknown":
        return "unknown"
    if artifact_status == "error":
        return "blocked"
    if artifact_status in {"warning", "missing"}:
        return "warning"
    if artifact_status == "ok":
        return "ready"
    return "unknown"


def diagnostics_recovery_finding_status_state(severity: str = "", status: str = "") -> str:
    normalized_severity = str(severity or "").strip().casefold().replace("_", "-")
    normalized_status = str(status or "").strip().casefold().replace("_", "-")
    combined = f"{normalized_severity} {normalized_status}"
    if any(term in combined for term in ("critical", "fatal", "error", "blocked", "failed", "failure")):
        return "blocked"
    if normalized_status in DIAGNOSTICS_RECOVERY_READY_STATUSES:
        return "match"
    if any(term in combined for term in ("warn", "review", "open", "unresolved", "stale", "missing", "planned", "found", "retry")):
        return "warning"
    if normalized_severity in {"info", "notice", "debug"} and not normalized_status:
        return "match"
    if normalized_status:
        return "warning"
    return "unknown"


def diagnostics_state_summary_payload(
    items: Iterable[dict[str, Any]],
    *,
    settings_tool_path_evidence: Mapping[str, Any] | None = None,
    path_health: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    summaries = [diagnostics_state_summary_item(item) for item in items]
    settings_rows = diagnostics_settings_tool_path_summary_rows(settings_tool_path_evidence)
    path_health_rows = diagnostics_path_health_summary_rows(path_health)
    summaries.extend(settings_rows)
    summaries.extend(path_health_rows)
    counts: dict[str, int] = {}
    operator_counts: dict[str, int] = {}
    operator_state_counts: dict[str, int] = {}
    warnings: list[str] = []
    errors: list[str] = []
    for item in summaries:
        status = str(item.get("status") or "unknown")
        counts[status] = counts.get(status, 0) + 1
        operator_status = str(item.get("operator_status") or "unknown")
        operator_counts[operator_status] = operator_counts.get(operator_status, 0) + 1
        operator_state = str(
            item.get("operator_status_state")
            or diagnostics_operator_status_state(operator_status, status)
            or "unknown"
        )
        operator_state_counts[operator_state] = operator_state_counts.get(operator_state, 0) + 1
        warnings.extend(str(warning) for warning in item.get("warnings", []) if str(warning).strip())
        errors.extend(str(error) for error in item.get("errors", []) if str(error).strip())
    operator_status = _payload_operator_status(operator_counts, summaries)
    operator_status_state = diagnostics_operator_status_state(operator_status)
    triage = _diagnostics_state_triage(summaries)
    return {
        "schema_version": DIAGNOSTICS_STATE_SUMMARY_SCHEMA_VERSION,
        "ok": not errors,
        "operator_status": operator_status,
        "operator_status_state": operator_status_state,
        "guardrail": (
            "Read-only backend summary. Paths come from diagnostics allowlist targets; "
            "the WebView never sends arbitrary paths, and large files are summarized "
            "by metadata instead of being fully loaded."
        ),
        "targets": summaries,
        "counts": counts,
        "operator_counts": operator_counts,
        "operator_status_state_counts": operator_state_counts,
        "operator_summary": _payload_operator_summary(operator_status, operator_counts, triage),
        "triage": triage,
        "settings_tool_path_evidence": dict(settings_tool_path_evidence or {}),
        "settings_tool_path_issues": settings_rows,
        "path_health": dict(path_health or {}),
        "path_health_issues": path_health_rows,
        "warnings": warnings[:DIAGNOSTICS_STATE_SUMMARY_FACT_LIMIT],
        "errors": errors[:DIAGNOSTICS_STATE_SUMMARY_FACT_LIMIT],
    }


def diagnostics_settings_tool_path_summary_rows(evidence: Mapping[str, Any] | None) -> list[dict[str, Any]]:
    if not isinstance(evidence, Mapping):
        return []
    specs = [
        {
            "key": "bdpgs_ocr",
            "target": "settings_bdpgs_ocr_paths",
            "label": "Settings BDPGS OCR path evidence",
            "format_label": "BDPGS",
            "guidance": (
                "Settings says BDPGS OCR to SRT is enabled, but the saved OCR tool/tessdata path evidence is not ready. "
                "Open Settings > Subtitles, fix the saved OCR paths or disable OCR intentionally, save, then refresh Diagnostics before rerunning subtitle conversion."
            ),
            "unsafe": (
                "Ignoring blocked BDPGS OCR path evidence can make PGS subtitle conversion fail and leave files marked for manual review even though the media route itself looks healthy."
            ),
        },
        {
            "key": "vobsub_ocr",
            "target": "settings_vobsub_ocr_paths",
            "label": "Settings VobSub OCR path evidence",
            "format_label": "VobSub",
            "guidance": (
                "Settings says VobSub OCR to SRT is enabled, but the saved Subtitle Edit/Tesseract path evidence is not ready. "
                "Open Settings > Subtitles, fix the saved OCR tool path or disable OCR intentionally, save, then refresh Diagnostics before rerunning subtitle conversion."
            ),
            "unsafe": (
                "Ignoring blocked VobSub OCR path evidence can make VobSub subtitle conversion fail and leave files marked for manual review even though the media route itself looks healthy."
            ),
        },
    ]
    rows: list[dict[str, Any]] = []
    for spec in specs:
        ocr_evidence = evidence.get(spec["key"])
        if not isinstance(ocr_evidence, Mapping):
            continue
        enabled = bool(ocr_evidence.get("enabled"))
        operator_status = str(ocr_evidence.get("operator_status") or "").strip()
        normalized_status = operator_status.casefold()
        if not enabled or normalized_status not in {"blocked", "review"}:
            continue
        row_status = "error" if normalized_status == "blocked" else "warning"
        issue_rows = [
            row
            for row in ocr_evidence.get("rows", [])
            if isinstance(row, Mapping) and str(row.get("status") or "").strip().casefold() in {"blocked", "review"}
        ]
        messages = [str(row.get("message") or "").strip() for row in issue_rows if str(row.get("message") or "").strip()]
        summary_lines = [str(line).strip() for line in ocr_evidence.get("summary_lines", []) if str(line).strip()]
        facts = [
            f"OCR enabled in saved config: {'yes' if enabled else 'no'}",
            f"AllowSystemTools/PATH fallback: {'yes' if bool(ocr_evidence.get('allow_system_tools')) else 'no'}",
            f"Blocked settings path rows: {int(ocr_evidence.get('blocked_count') or 0)}",
            f"Review settings path rows: {int(ocr_evidence.get('review_count') or 0)}",
        ]
        for row in issue_rows:
            key = str(row.get("key") or "").strip()
            configured = str(row.get("configured") or "").strip() or "(not configured)"
            resolved = str(row.get("resolved") or "").strip() or "(not resolved)"
            status = str(row.get("status") or "").strip() or "unknown"
            facts.append(f"{key}: {status}; configured={configured}; resolved={resolved}")
        warnings: list[str] = []
        errors: list[str] = []
        format_label = str(spec["format_label"])
        if normalized_status == "blocked":
            errors.extend(messages or [f"{format_label} OCR is enabled, but saved OCR tool path evidence is blocked."])
        else:
            warnings.extend(messages or [f"{format_label} OCR saved path evidence needs review."])
        rows.append(
            {
                "target": spec["target"],
                "label": spec["label"],
                "path": "",
                "exists": False,
                "kind": "settings",
                "size_bytes": None,
                "modified_at": "",
                "status": row_status,
                "operator_status": normalized_status,
                "operator_status_state": diagnostics_operator_status_state(normalized_status, row_status),
                "operator_guidance": spec["guidance"],
                "recovery_stage": "settings_subtitle_ocr_readiness",
                "unsafe_if_ignored": spec["unsafe"],
                "recommended_open_target": "",
                "recommended_tail_target": "",
                "facts": facts[:DIAGNOSTICS_STATE_SUMMARY_FACT_LIMIT],
                "recent_entries": [],
                "warnings": warnings[:DIAGNOSTICS_STATE_SUMMARY_FACT_LIMIT],
                "errors": errors[:DIAGNOSTICS_STATE_SUMMARY_FACT_LIMIT],
                "summary_lines": summary_lines[:DIAGNOSTICS_STATE_SUMMARY_FACT_LIMIT],
            }
        )
    return rows


def diagnostics_path_health_summary_rows(path_health: Mapping[str, Any] | None) -> list[dict[str, Any]]:
    if not isinstance(path_health, Mapping):
        return []
    health_rows = path_health.get("rows")
    if not isinstance(health_rows, list):
        return []
    rows: list[dict[str, Any]] = []
    for health_row in health_rows:
        if not isinstance(health_row, Mapping):
            continue
        operator_status = str(health_row.get("operator_status") or health_row.get("status") or "unknown").strip().casefold()
        if operator_status == "ready":
            continue
        row_status = "error" if operator_status == "blocked" else "warning"
        label = str(health_row.get("label") or health_row.get("key") or "Configured path").strip()
        key = str(health_row.get("key") or "configured_path").strip()
        path = str(health_row.get("path") or "").strip()
        server = str(health_row.get("server") or "").strip()
        share = str(health_row.get("share") or "").strip()
        path_probe = health_row.get("path_probe") if isinstance(health_row.get("path_probe"), Mapping) else {}
        server_probe = health_row.get("server_probe") if isinstance(health_row.get("server_probe"), Mapping) else {}
        message = str(health_row.get("message") or "Configured path health needs review.").strip()
        safe_next_action = str(health_row.get("safe_next_action") or "Review Settings and Launch before starting work.").strip()
        facts = [
            f"Role: {health_row.get('role') or 'unknown'}",
            f"Configured key: {health_row.get('configured_key') or 'unknown'}",
            f"UNC path: {'yes' if bool(health_row.get('is_unc')) else 'no'}",
            f"Server/share: {server or '(local)'}/{share or '(none)'}",
            f"Path kind: {path_probe.get('path_kind') or health_row.get('path_kind') or 'unknown'}",
            f"Exists: {'yes' if bool(path_probe.get('exists') or health_row.get('exists')) else 'no'}",
            f"Can list root: {'yes' if bool(path_probe.get('can_list') or health_row.get('can_list')) else 'no'}",
            f"DNS: {server_probe.get('dns_status') or 'not_applicable'}; SMB TCP 445: {server_probe.get('tcp_445_status') or 'not_applicable'}",
            f"Elapsed: {int(health_row.get('elapsed_ms') or 0)} ms",
            "Write probe: not checked; this Diagnostics row is read-only.",
        ]
        issue_list = [message]
        row_errors = issue_list if operator_status == "blocked" else []
        row_warnings = issue_list if operator_status != "blocked" else []
        rows.append(
            {
                "target": f"configured_path_health_{key}",
                "label": f"Configured path health: {label}",
                "path": path,
                "exists": bool(path_probe.get("exists") or health_row.get("exists")),
                "kind": "path_health",
                "size_bytes": None,
                "modified_at": "",
                "status": row_status,
                "operator_status": operator_status,
                "operator_status_state": diagnostics_operator_status_state(operator_status, row_status),
                "operator_guidance": (
                    "Configured root health is checked by the backend before launch. "
                    "Reconnect the server/share or restore the folder, then refresh Settings or Launch before starting work."
                ),
                "recovery_stage": "configured_server_folder_health",
                "unsafe_if_ignored": (
                    "Ignoring unreachable configured roots can make a scan, copy, remux, encode, or publish attempt fail or stall before useful media evidence is produced."
                ),
                "recommended_open_target": "",
                "recommended_tail_target": "",
                "facts": facts[:DIAGNOSTICS_STATE_SUMMARY_FACT_LIMIT],
                "recent_entries": [],
                "warnings": row_warnings[:DIAGNOSTICS_STATE_SUMMARY_FACT_LIMIT],
                "errors": row_errors[:DIAGNOSTICS_STATE_SUMMARY_FACT_LIMIT],
                "summary_lines": [
                    message,
                    safe_next_action,
                    "Mutation guardrail: this row cannot save settings, start work, scan media, write test files, or clear state.",
                ][:DIAGNOSTICS_STATE_SUMMARY_FACT_LIMIT],
            }
        )
    return rows


def _payload_operator_status(operator_counts: dict[str, int], summaries: list[dict[str, Any]]) -> str:
    if not summaries:
        return "unknown"
    if operator_counts.get("blocked", 0) > 0:
        return "blocked"
    if operator_counts.get("review", 0) > 0:
        return "review"
    if operator_counts.get("unknown", 0) > 0:
        return "unknown"
    if operator_counts.get("not available", 0) > 0:
        return "review"
    return "ready"


def _payload_operator_summary(operator_status: str, operator_counts: dict[str, int], triage: list[dict[str, Any]]) -> list[str]:
    lines = [
        f"Backend state posture: {operator_status}.",
        (
            "Operator counts: "
            f"ready={operator_counts.get('ready', 0)}; "
            f"review={operator_counts.get('review', 0)}; "
            f"blocked={operator_counts.get('blocked', 0)}; "
            f"not_available={operator_counts.get('not available', 0)}; "
            f"unknown={operator_counts.get('unknown', 0)}."
        ),
    ]
    if triage:
        first = triage[0]
        lines.append(
            "Read order starts with "
            f"{first.get('label') or first.get('target') or 'the first diagnostics artifact'} "
            f"because {first.get('reason') or 'it needs operator review'}."
        )
        lines.append(
            "Use bounded tail targets before shell-open targets when both are available; "
            "this preserves the backend allowlist boundary and avoids arbitrary file reads."
        )
    else:
        lines.append("No backend state artifacts currently require triage. If pages disagree, compare Queue, Completed, Pending Publish, Run Logs, and ActiveJobs before rerunning media.")
    lines.append("Mutation guardrail: this summary cannot repair, delete, drain, rerun, clear state, or mark work complete.")
    return lines[:DIAGNOSTICS_STATE_SUMMARY_FACT_LIMIT]


def _diagnostics_state_triage(summaries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    issue_rows = [summary for summary in summaries if _triage_priority(summary) < 90]
    ordered = sorted(
        issue_rows,
        key=lambda summary: (
            _triage_priority(summary),
            str(summary.get("recovery_stage") or ""),
            str(summary.get("target") or ""),
        ),
    )
    return [_diagnostics_state_triage_row(summary, index + 1) for index, summary in enumerate(ordered[:DIAGNOSTICS_STATE_SUMMARY_RECENT_LIMIT])]


def _triage_priority(summary: dict[str, Any]) -> int:
    operator_status = str(summary.get("operator_status") or "").casefold()
    status = str(summary.get("status") or "").casefold()
    if operator_status == "blocked" or status == "error":
        return 0
    if status == "warning":
        return 10
    if operator_status == "unknown":
        return 20
    if status == "missing" or operator_status in {"review", "not available"}:
        return 30
    return 99


def _diagnostics_state_triage_row(summary: dict[str, Any], priority: int) -> dict[str, Any]:
    warnings = [str(item) for item in summary.get("warnings", []) if str(item).strip()]
    errors = [str(item) for item in summary.get("errors", []) if str(item).strip()]
    reason = errors[0] if errors else warnings[0] if warnings else str(summary.get("operator_guidance") or "Artifact needs operator review.")
    return {
        "priority": priority,
        "target": str(summary.get("target") or ""),
        "label": str(summary.get("label") or summary.get("target") or ""),
        "status": str(summary.get("status") or "unknown"),
        "operator_status": str(summary.get("operator_status") or "unknown"),
        "operator_status_state": str(
            summary.get("operator_status_state")
            or diagnostics_operator_status_state(
                str(summary.get("operator_status") or "unknown"),
                str(summary.get("status") or "unknown"),
            )
        ),
        "recovery_stage": str(summary.get("recovery_stage") or "diagnostics_artifact"),
        "reason": reason,
        "read_first_target": str(summary.get("recommended_tail_target") or ""),
        "open_next_target": str(summary.get("recommended_open_target") or ""),
        "safe_next_action": _triage_safe_next_action(summary),
        "unsafe_if_ignored": str(summary.get("unsafe_if_ignored") or ""),
    }


def _triage_safe_next_action(summary: dict[str, Any]) -> str:
    tail_target = str(summary.get("recommended_tail_target") or "")
    open_target = str(summary.get("recommended_open_target") or "")
    if tail_target:
        return f"Read bounded tail for {tail_target}, then compare with the owning page before changing workflow state."
    if open_target:
        return f"Open backend-allowlisted {open_target}, then compare with the owning page before changing workflow state."
    return "Review the artifact detail and owning page; do not clear state, rerun, drain, or close based on this summary alone."


def diagnostics_state_summary_item(item: dict[str, Any]) -> dict[str, Any]:
    target = str(item.get("target") or "").strip()
    label = str(item.get("label") or target).strip() or target
    path = _optional_path(item.get("path"))
    summary: dict[str, Any] = {
        "target": target,
        "label": label,
        "path": str(path) if path else "",
        "exists": False,
        "kind": "missing",
        "size_bytes": None,
        "modified_at": "",
        "status": "missing",
        "facts": [],
        "recent_entries": [],
        "warnings": [],
        "errors": [],
    }
    if path is None:
        summary["warnings"].append(f"No path is configured for {label}.")
        summary.update(_operator_summary(summary, target))
        return summary
    try:
        stat = path.stat()
    except FileNotFoundError:
        summary["warnings"].append(f"{label} does not exist yet.")
        summary.update(_operator_summary(summary, target))
        return summary
    except OSError as exc:
        summary["status"] = "error"
        summary["errors"].append(f"Could not stat {label}: {exc}")
        summary.update(_operator_summary(summary, target))
        return summary
    summary["exists"] = True
    summary["size_bytes"] = int(stat.st_size)
    summary["modified_at"] = _format_mtime(stat.st_mtime)
    if path.is_dir():
        summary.update(_directory_summary(path, label))
    elif path.is_file():
        summary.update(_file_summary(path, label, int(stat.st_size)))
    else:
        summary["kind"] = "other"
        summary["status"] = "warning"
        summary["warnings"].append(f"{label} is not a regular file or directory.")
    summary.update(_operator_summary(summary, target))
    return summary


def _operator_summary(summary: dict[str, Any], target: str) -> dict[str, Any]:
    status = str(summary.get("status") or "unknown").casefold()
    kind = str(summary.get("kind") or "").casefold()
    exists = bool(summary.get("exists"))
    errors = [str(item) for item in summary.get("errors", []) if str(item).strip()]
    warnings = [str(item) for item in summary.get("warnings", []) if str(item).strip()]
    if errors or status == "error":
        operator_status = "blocked"
    elif warnings or status in {"warning", "missing"}:
        operator_status = "review"
    elif exists:
        operator_status = "ready"
    else:
        operator_status = "not available"
    guidance = _operator_guidance(target, operator_status, status, kind, exists)
    return {
        "operator_status": operator_status,
        "operator_status_state": diagnostics_operator_status_state(operator_status, status),
        "operator_guidance": guidance,
        "recovery_stage": DIAGNOSTICS_STATE_TARGET_RECOVERY_STAGE.get(target, "diagnostics_artifact"),
        "unsafe_if_ignored": DIAGNOSTICS_STATE_TARGET_IGNORE_RISK.get(
            target,
            "Ignoring this diagnostics artifact can make the related WebView page look healthier than backend state actually is.",
        ),
        "recommended_open_target": target if exists else "",
        "recommended_tail_target": target if exists and kind == "file" and target in DIAGNOSTICS_STATE_SUMMARY_TAIL_TARGETS else "",
    }


def _operator_guidance(target: str, operator_status: str, status: str, kind: str, exists: bool) -> str:
    base = DIAGNOSTICS_STATE_TARGET_GUIDANCE.get(target, "Review this backend-selected diagnostics artifact when investigating runtime state.")
    if operator_status == "blocked":
        return f"{base} This artifact has parse/read errors; open the target and read an allowlisted tail when available before clearing state or rerunning work."
    if operator_status == "review":
        if status == "missing" or not exists:
            return f"{base} This artifact is missing or not configured; that can be normal before the first relevant run, but verify related pages if work is expected."
        return f"{base} This artifact has warnings; review its detail before trusting the related page."
    if kind == "directory":
        return f"{base} Directory summary is healthy; select recent entries when investigating fresh runtime activity."
    return f"{base} Artifact summary is healthy; use Open/Tail only when investigating a specific operator question."


def _directory_summary(path: Path, label: str) -> dict[str, Any]:
    facts: list[str] = []
    warnings: list[str] = []
    errors: list[str] = []
    entries: list[dict[str, Any]] = []
    file_count = 0
    directory_count = 0
    scanned = 0
    truncated = False
    try:
        iterator = path.iterdir()
        for child in iterator:
            scanned += 1
            if scanned > DIAGNOSTICS_STATE_SUMMARY_DIR_SCAN_LIMIT:
                truncated = True
                break
            try:
                child_stat = child.stat()
            except OSError as exc:
                warnings.append(f"Could not stat {child.name}: {exc}")
                continue
            is_dir = child.is_dir()
            if is_dir:
                directory_count += 1
            else:
                file_count += 1
            entries.append(
                {
                    "name": child.name,
                    "kind": "directory" if is_dir else "file",
                    "size_bytes": None if is_dir else int(child_stat.st_size),
                    "modified_at": _format_mtime(child_stat.st_mtime),
                }
            )
    except OSError as exc:
        return {
            "kind": "directory",
            "status": "error",
            "facts": [],
            "recent_entries": [],
            "warnings": [],
            "errors": [f"Could not list {label}: {exc}"],
        }
    entries.sort(key=lambda row: str(row.get("modified_at") or ""), reverse=True)
    facts.extend(
        [
            f"Files scanned: {file_count}",
            f"Directories scanned: {directory_count}",
        ]
    )
    if truncated:
        warnings.append(
            f"{label} contains more than {DIAGNOSTICS_STATE_SUMMARY_DIR_SCAN_LIMIT} entries; recent-entry list is truncated."
        )
    status = "warning" if warnings else "ok"
    return {
        "kind": "directory",
        "status": status,
        "facts": facts,
        "recent_entries": entries[:DIAGNOSTICS_STATE_SUMMARY_RECENT_LIMIT],
        "warnings": warnings[:DIAGNOSTICS_STATE_SUMMARY_FACT_LIMIT],
        "errors": errors,
    }


def _file_summary(path: Path, label: str, size_bytes: int) -> dict[str, Any]:
    suffix = path.suffix.casefold()
    facts = [f"File extension: {suffix or '(none)'}", f"Read limit: {DIAGNOSTICS_STATE_SUMMARY_JSON_MAX_BYTES} bytes"]
    warnings: list[str] = []
    errors: list[str] = []
    status = "ok"
    if suffix == ".jsonl" or path.name.casefold().endswith(".jsonl"):
        parsed = _jsonl_file_facts(path, label, size_bytes)
        facts.extend(parsed["facts"])
        warnings.extend(parsed["warnings"])
        errors.extend(parsed["errors"])
    elif suffix == ".json":
        parsed = _json_file_facts(path, label, size_bytes)
        facts.extend(parsed["facts"])
        warnings.extend(parsed["warnings"])
        errors.extend(parsed["errors"])
    elif suffix in {".log", ".txt", ".csv"}:
        parsed = _text_file_facts(path, label, size_bytes)
        facts.extend(parsed["facts"])
        warnings.extend(parsed["warnings"])
        errors.extend(parsed["errors"])
    else:
        facts.append("Metadata-only summary; use allowlisted tail/open controls for detailed inspection.")
    if errors:
        status = "error"
    elif warnings:
        status = "warning"
    return {
        "kind": "file",
        "status": status,
        "facts": facts[:DIAGNOSTICS_STATE_SUMMARY_FACT_LIMIT],
        "recent_entries": [],
        "warnings": warnings[:DIAGNOSTICS_STATE_SUMMARY_FACT_LIMIT],
        "errors": errors[:DIAGNOSTICS_STATE_SUMMARY_FACT_LIMIT],
    }


def _json_file_facts(path: Path, label: str, size_bytes: int) -> dict[str, list[str]]:
    if size_bytes > DIAGNOSTICS_STATE_SUMMARY_JSON_MAX_BYTES:
        return {
            "facts": ["JSON parse skipped because file exceeds diagnostics read limit."],
            "warnings": [f"{label} is too large for full JSON diagnostics parsing."],
            "errors": [],
        }
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except JSONDecodeError as exc:
        return {"facts": [], "warnings": [], "errors": [f"{label} is malformed JSON: {exc}"]}
    except UnicodeDecodeError as exc:
        return {"facts": [], "warnings": [], "errors": [f"{label} is not readable as UTF-8 JSON: {exc}"]}
    except OSError as exc:
        return {"facts": [], "warnings": [], "errors": [f"Could not read {label}: {exc}"]}
    return {"facts": _json_value_facts(payload), "warnings": [], "errors": []}


def _jsonl_file_facts(path: Path, label: str, size_bytes: int) -> dict[str, list[str]]:
    if size_bytes > DIAGNOSTICS_STATE_SUMMARY_JSON_MAX_BYTES:
        return {
            "facts": ["JSONL parse skipped because file exceeds diagnostics read limit."],
            "warnings": [f"{label} is too large for full JSONL diagnostics parsing."],
            "errors": [],
        }
    try:
        lines = path.read_text(encoding="utf-8-sig").splitlines()
    except UnicodeDecodeError as exc:
        return {"facts": [], "warnings": [], "errors": [f"{label} is not readable as UTF-8 JSONL: {exc}"]}
    except OSError as exc:
        return {"facts": [], "warnings": [], "errors": [f"Could not read {label}: {exc}"]}
    nonempty = [line for line in lines if line.strip()]
    valid = 0
    invalid = 0
    schemas: dict[str, int] = {}
    for line in nonempty:
        try:
            payload = json.loads(line)
        except JSONDecodeError:
            invalid += 1
            continue
        valid += 1
        if isinstance(payload, dict):
            schema = str(payload.get("schema_version") or payload.get("schema") or "(none)")
            schemas[schema] = schemas.get(schema, 0) + 1
    facts = [
        f"JSONL non-empty lines: {len(nonempty)}",
        f"JSONL valid records: {valid}",
        f"JSONL invalid records: {invalid}",
    ]
    if schemas:
        facts.append("Schemas: " + ", ".join(f"{key}={value}" for key, value in sorted(schemas.items())))
    warnings = [f"{label} contains {invalid} malformed JSONL record(s)."] if invalid else []
    return {"facts": facts, "warnings": warnings, "errors": []}


def _text_file_facts(path: Path, label: str, size_bytes: int) -> dict[str, list[str]]:
    if size_bytes > DIAGNOSTICS_STATE_SUMMARY_TEXT_MAX_BYTES:
        return {
            "facts": ["Text scan skipped because file exceeds diagnostics text read limit."],
            "warnings": [f"{label} is large; use the bounded tail control for recent lines."],
            "errors": [],
        }
    try:
        text = path.read_text(encoding="utf-8-sig", errors="replace")
    except OSError as exc:
        return {"facts": [], "warnings": [], "errors": [f"Could not read {label}: {exc}"]}
    lines = text.splitlines()
    error_like = sum(1 for line in lines if _is_error_like(line))
    warning_like = sum(1 for line in lines if _is_warning_like(line))
    return {
        "facts": [
            f"Text lines: {len(lines)}",
            f"Error-like lines: {error_like}",
            f"Warning-like lines: {warning_like}",
        ],
        "warnings": [f"{label} contains warning/error-like log lines."] if error_like or warning_like else [],
        "errors": [],
    }


def _json_value_facts(payload: Any) -> list[str]:
    if isinstance(payload, dict):
        keys = sorted(str(key) for key in payload.keys())
        facts = [f"JSON object keys: {len(keys)}", "Top keys: " + ", ".join(keys[:DIAGNOSTICS_STATE_SUMMARY_FACT_LIMIT])]
        collection_counts = []
        for key in keys:
            value = payload.get(key)
            if isinstance(value, (list, dict)):
                collection_counts.append(f"{key}={len(value)}")
        if collection_counts:
            facts.append("Collection sizes: " + ", ".join(collection_counts[:DIAGNOSTICS_STATE_SUMMARY_FACT_LIMIT]))
        return facts
    if isinstance(payload, list):
        return [f"JSON array items: {len(payload)}"]
    if payload is None:
        return ["JSON scalar: null"]
    return [f"JSON scalar: {type(payload).__name__}"]


def _optional_path(value: Any) -> Path | None:
    if value is None:
        return None
    try:
        path = Path(value)
    except TypeError:
        return None
    return path if str(path).strip() else None


def _format_mtime(raw: float) -> str:
    return datetime.fromtimestamp(raw).astimezone().isoformat(timespec="seconds")


def _is_error_like(line: str) -> bool:
    text = line.casefold()
    return any(term in text for term in ("error", "failed", "failure", "exception", "traceback", "fatal"))


def _is_warning_like(line: str) -> bool:
    text = line.casefold()
    return any(term in text for term in ("warn", "timeout", "retry", "stale", "missing", "locked", "skipped"))

__all__ = [
    "DIAGNOSTICS_STATE_SUMMARY_SCHEMA_VERSION",
    "DIAGNOSTICS_STATE_SUMMARY_TARGETS",
    "DIAGNOSTICS_STATE_SUMMARY_JSON_MAX_BYTES",
    "DIAGNOSTICS_STATE_SUMMARY_TEXT_MAX_BYTES",
    "DIAGNOSTICS_STATE_SUMMARY_DIR_SCAN_LIMIT",
    "DIAGNOSTICS_STATE_SUMMARY_RECENT_LIMIT",
    "DIAGNOSTICS_STATE_SUMMARY_FACT_LIMIT",
    "DIAGNOSTICS_STATE_SUMMARY_TAIL_TARGETS",
    "DIAGNOSTICS_SETTINGS_TOOL_PATH_KEYS",
    "DIAGNOSTICS_RECOVERY_READY_STATUSES",
    "DIAGNOSTICS_STATE_TARGET_GUIDANCE",
    "DIAGNOSTICS_STATE_TARGET_RECOVERY_STAGE",
    "DIAGNOSTICS_STATE_TARGET_IGNORE_RISK",
    "diagnostics_operator_status_state",
    "diagnostics_recovery_finding_status_state",
    "diagnostics_should_include_settings_tool_path_evidence",
    "diagnostics_state_summary_payload",
    "diagnostics_settings_tool_path_summary_rows",
    "diagnostics_path_health_summary_rows",
    "diagnostics_state_summary_item",
]
