"""Maintenance workspace DTO policy."""

from __future__ import annotations

from datetime import datetime, UTC
import re
from pathlib import Path
from typing import Any

from mediapipeline.core.paths.contracts import ResolvedPaths


def maintenance_row_key(name: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "_", str(name or "").casefold()).strip("_")
    return normalized or "maintenance_check"


def maintenance_row_guidance(name: str, status: str, optional: bool) -> dict[str, Any]:
    label = str(name or "maintenance check")
    if status == "ok":
        return {
            "severity": "info",
            "operator_status": "ready",
            "operator_guidance": f"{label} is available for maintenance dry-run planning.",
            "safe_next_action": "Continue to Release Dry Run or Completed Manifest Backfill Dry Run if other required checks are also ready.",
            "unsafe_if_ignored": "Low risk; this row is already healthy.",
            "dry_run_impact": "ready",
            "recommended_diagnostics_actions": [
                {"kind": "tail", "target": "last_stderr_log", "label": "Read Last Stderr"},
                {"kind": "open", "target": "run_logs", "label": "Open Run Logs"},
            ],
        }
    if status == "running":
        return {
            "severity": "info",
            "operator_status": "active",
            "operator_guidance": f"{label} detected active backend work. This is expected while a pipeline run is in progress.",
            "safe_next_action": "Let the active run finish, or inspect Home progress, Diagnostics ActiveJobs, and Run Logs before closing or starting maintenance dry-run work.",
            "unsafe_if_ignored": "Treating active backend work as a missing dependency can make a normal run look broken; treating it as ready can hide close-readiness risk.",
            "dry_run_impact": "active_run_in_progress",
            "recommended_diagnostics_actions": [
                {"kind": "open", "target": "active_jobs", "label": "Open ActiveJobs"},
                {"kind": "open", "target": "run_logs", "label": "Open Run Logs"},
                {"kind": "tail", "target": "last_stderr_log", "label": "Read Last Stderr"},
            ],
        }
    if optional:
        return {
            "severity": "warning",
            "operator_status": "review",
            "operator_guidance": f"{label} is optional but unavailable. Release/backfill dry runs can still be useful, but review the capability this check represents.",
            "safe_next_action": "Run dry-run commands only after deciding the missing optional capability is acceptable for this package/test pass.",
            "unsafe_if_ignored": "Optional tooling, telemetry, or documentation may be omitted from the maintenance plan without being noticed.",
            "dry_run_impact": "review_before_release",
            "recommended_diagnostics_actions": [
                {"kind": "tail", "target": "last_stderr_log", "label": "Read Last Stderr"},
                {"kind": "open", "target": "run_logs", "label": "Open Run Logs"},
                {"kind": "open", "target": "config", "label": "Open Config"},
            ],
        }
    return {
        "severity": "error",
        "operator_status": "blocked",
        "operator_guidance": f"{label} is required and unavailable. Maintenance dry-run output should not be trusted until this row is fixed.",
        "safe_next_action": "Fix the required tool/path/configuration, rerun Environment Health, then retry the dry-run command.",
        "unsafe_if_ignored": "Release packages or completed-manifest backfill plans can be incomplete, misleading, or fail after a long dry-run wait.",
        "dry_run_impact": "blocks_release_and_backfill",
        "recommended_diagnostics_actions": [
            {"kind": "tail", "target": "last_stderr_log", "label": "Read Last Stderr"},
            {"kind": "open", "target": "run_logs", "label": "Open Run Logs"},
            {"kind": "open", "target": "config", "label": "Open Config"},
            {"kind": "open", "target": "state", "label": "Open State Folder"},
        ],
    }


def maintenance_tool_kind(name: str) -> str:
    text = str(name or "").casefold()
    if "config schema" in text:
        return "config_schema"
    if "configured root" in text:
        return "configured_root"
    if "library output root" in text or "library promotion destination" in text or "final library destination" in text:
        return "library_output_root"
    if "runtime state" in text:
        return "runtime_state"
    if "sqlite mirror" in text:
        return "sqlite_mirror"
    if "api contract" in text:
        return "api_contract"
    if "process guard" in text:
        return "process_guard"
    if "bundle layout" in text:
        return "bundle_layout"
    if "powershell" in text or "pwsh" in text:
        return "powershell_host"
    if "ffmpeg" in text:
        return "ffmpeg"
    if "ffprobe" in text:
        return "ffprobe"
    if "mkvextract" in text:
        return "mkvextract"
    if "mkvmerge" in text or "mkvtool" in text:
        return "mkvtoolnix"
    if "nvidia" in text or "nvenc" in text:
        return "gpu_telemetry"
    if "mediapipeline.pipeline.ass_to_srt_cli" in text or "subtitle converter" in text:
        return "mediapipeline.pipeline.ass_to_srt_cli"
    if "tessdata" in text and "bdpgs" in text:
        return "bdpgs_tessdata"
    if "pgstosrt" in text or "bdpgs" in text:
        return "bdpgs_ocr"
    if "tesseract" in text and "vobsub" in text:
        return "vobsub_tesseract"
    if "subtitleedit" in text or "vobsub" in text:
        return "vobsub_ocr"
    return "tool"


def maintenance_tool_capability(tool_kind: str) -> str:
    return {
        "config_schema": "Active configuration file parse and canonical schema validation.",
        "configured_root": "Configured source, scratch, and output roots must exist before launch or package dry-run trust.",
        "library_output_root": "Enabled Library Profile and final-library destination roots used for output placement and promotion.",
        "runtime_state": "Runtime state files used by queue, diagnostics, launch guards, and operator trust surfaces.",
        "sqlite_mirror": "Optional read-only SQLite mirror of JSON state evidence.",
        "api_contract": "Backend route contract evidence for the WebView and Tauri shell.",
        "process_guard": "ActiveJobs and related-process visibility used by launch and close-readiness safety guards.",
        "bundle_layout": "Promoted launcher, bundled runtime, and WebView asset layout.",
        "powershell_host": "PowerShell host for pipeline, audit, rerun, config parsing, and release tooling.",
        "ffmpeg": "FFmpeg execution for remux, encode, subtitle/audio muxing, thumbnails, and media output generation.",
        "ffprobe": "Media probing for route decisions, stream inventory, audit, validation, and sidecar evidence.",
        "mkvtoolnix": "MKVToolNix support for MKV-oriented mux/metadata workflows and packaging expectations.",
        "mkvextract": "MKVToolNix extraction support for embedded VobSub IDX/SUB extraction before OCR.",
        "gpu_telemetry": "Optional GPU/NVENC telemetry visibility. Missing telemetry does not by itself block encoding.",
        "mediapipeline.pipeline.ass_to_srt_cli": "ASS/SSA subtitle text conversion helper used before SRT sidecar/output proof.",
        "bdpgs_ocr": "PgsToSrt command-line OCR helper for Blu-ray PGS/BDPGS subtitle conversion to SRT.",
        "bdpgs_tessdata": "Tesseract traineddata folder used by PgsToSrt for BDPGS subtitle OCR.",
        "vobsub_ocr": "Subtitle Edit 4.x command-line OCR helper for VobSub/DVD bitmap subtitle conversion to SRT.",
        "vobsub_tesseract": "Tesseract OCR executable and traineddata used by VobSub subtitle OCR.",
    }.get(tool_kind, "External tool or runtime dependency.")


def maintenance_tool_failure_scope(tool_kind: str, optional: bool) -> str:
    if optional:
        return "Optional visibility/capability may be reduced, but core media processing can still be evaluated if required tools are ready."
    return {
        "config_schema": "Settings, queue planning, launch preflight, media policy, and release tooling can read stale or invalid configuration.",
        "configured_root": "Launch, scan, scratch copy, publish, and state writes can fail or target the wrong place.",
        "library_output_root": "Library-specific output or final-library promotion can fail after media processing appears successful.",
        "runtime_state": "Queue, command history, diagnostics, close-readiness, and recovery surfaces can become misleading.",
        "sqlite_mirror": "SQLite mirror diagnostics are unavailable or stale; JSON state remains authoritative.",
        "api_contract": "WebView/Tauri route expectations can drift from backend route ownership.",
        "process_guard": "The operator can launch or close while backend work is still active or unverifiable.",
        "bundle_layout": "The promoted operator surface can fail to launch, package, or preserve removed legacy-boundary guarantees.",
        "powershell_host": "Pipeline, audit, rerun, settings/config load, release, and maintenance subprocesses may not start or may use the wrong host.",
        "ffmpeg": "Remux/encode/output generation cannot be trusted; media jobs may fail after queue decisions look valid.",
        "ffprobe": "Route decisions, stream mapping, subtitle/audio inspection, audit, and validation can become stale or impossible.",
        "mkvtoolnix": "MKV mux/metadata workflows and tool-bundle packaging may fail or silently fall back to less precise behavior.",
        "mkvextract": "Embedded VobSub tracks cannot be extracted to IDX/SUB for OCR, so VobSub conversion routes to review.",
        "mediapipeline.pipeline.ass_to_srt_cli": "ASS/SSA SRT generation may fail, leaving subtitle compatibility proof incomplete.",
        "bdpgs_ocr": "BDPGS image-subtitle OCR to SRT can fail or route to manual review.",
        "bdpgs_tessdata": "BDPGS OCR can produce failed or unusable text output when required language data is missing.",
        "vobsub_ocr": "VobSub OCR to SRT can fail or route to manual review.",
        "vobsub_tesseract": "VobSub OCR can fail when Tesseract or the required traineddata is missing.",
    }.get(tool_kind, "Required maintenance or pipeline capability may be missing.")


def maintenance_tool_source(detail: str, ok: bool) -> str:
    text = str(detail or "")
    normalized = text.replace("\\", "/").casefold()
    if not ok:
        return "missing"
    if any(token in normalized for token in ("config", "state", "route contract", "activejobs", "canonical", "webview")):
        return "backend_evidence"
    if "/pipeline/tools/" in normalized or "/pipeline/powershell-" in normalized:
        return "bundled"
    if "/pipeline/" in normalized and ("mediapipeline.pipeline.ass_to_srt_cli" in normalized or "pgstosrt" in normalized):
        return "pipeline_script"
    if re.search(r"(^|[/\\])pwsh(?:\.exe)?$", text, re.IGNORECASE):
        return "resolved_host"
    if text and "not found" not in normalized:
        return "system_or_absolute"
    return "unknown"


def maintenance_process_guard_is_running(detail: str) -> bool:
    normalized = str(detail or "").casefold()
    if "related mediapipeline process" in normalized and "still running" in normalized:
        return True
    if "activejobs record" not in normalized:
        return False
    active_record = " as active" in normalized or " as launching" in normalized
    active_pid = "is still running" in normalized or "identity could not be verified" in normalized or "with no pid" in normalized
    return active_record and active_pid


def maintenance_status_for_row(name: str, ok: bool, detail: str, optional: bool) -> str:
    if ok:
        return "ok"
    if optional:
        return "warning"
    if maintenance_tool_kind(name) == "process_guard" and maintenance_process_guard_is_running(detail):
        return "running"
    return "missing"


def maintenance_source_for_row(detail: str, ok: bool, status: str) -> str:
    if status == "running":
        return "backend_evidence"
    return maintenance_tool_source(detail, ok)


def maintenance_row_blocks_required(status: str) -> bool:
    return status not in {"ok", "running"}


def maintenance_toolchain_row(row: dict[str, Any]) -> dict[str, Any]:
    name = str(row.get("name") or "")
    ok = bool(row.get("ok"))
    optional = bool(row.get("optional"))
    tool_kind = maintenance_tool_kind(name)
    status = row.get("status") or maintenance_status_for_row(name, ok, str(row.get("detail") or ""), optional)
    operator_status = row.get("operator_status") or ("ready" if status == "ok" else "active" if status == "running" else "review" if optional else "blocked")
    return {
        "row_key": row.get("row_key") or maintenance_row_key(name),
        "name": name,
        "tool_kind": tool_kind,
        "required": not optional,
        "optional": optional,
        "status": status,
        "operator_status": operator_status,
        "detail": str(row.get("detail") or ""),
        "source": maintenance_source_for_row(str(row.get("detail") or ""), ok, str(status)),
        "capability": maintenance_tool_capability(tool_kind),
        "failure_scope": maintenance_tool_failure_scope(tool_kind, optional),
        "safe_next_action": row.get("safe_next_action") or "Rerun Environment Health before trusting dry-run output.",
        "recommended_diagnostics_actions": list(row.get("recommended_diagnostics_actions") or []),
    }


def maintenance_toolchain_evidence(rows: list[dict[str, Any]]) -> dict[str, Any]:
    tool_rows = [maintenance_toolchain_row(row) for row in rows]
    required_missing = [row for row in tool_rows if row["required"] and maintenance_row_blocks_required(str(row["status"]))]
    optional_review = [row for row in tool_rows if row["optional"] and row["status"] != "ok"]
    active_rows = [row for row in tool_rows if row["status"] == "running"]
    operator_status = "blocked" if required_missing else "active" if active_rows else "review" if optional_review else "ready" if tool_rows else "unknown"
    summary_lines = [
        f"Toolchain readiness: {operator_status}",
        f"Required missing/blocking: {len(required_missing)}",
        f"Active process guard rows: {len(active_rows)}",
        f"Optional warning/review: {len(optional_review)}",
        "Mutation guardrail: this evidence is read-only and comes from the backend maintenance health check; WebView does not resolve arbitrary tools, edit PATH, install dependencies, launch media jobs, or mutate files.",
    ]
    if required_missing:
        summary_lines.append("Blocking tools: " + ", ".join(row["name"] for row in required_missing[:6]))
    if active_rows:
        summary_lines.append("Active checks: " + ", ".join(row["name"] for row in active_rows[:6]))
    if optional_review:
        summary_lines.append("Optional review tools: " + ", ".join(row["name"] for row in optional_review[:6]))
    return {
        "schema_version": "desktop_maintenance_toolchain_evidence.v1",
        "read_only": True,
        "operator_status": operator_status,
        "required_missing_count": len(required_missing),
        "active_count": len(active_rows),
        "optional_review_count": len(optional_review),
        "tool_count": len(tool_rows),
        "rows": tool_rows,
        "summary_lines": summary_lines,
    }


def maintenance_health_row(raw_item: object) -> dict[str, Any] | None:
    try:
        name, ok, detail = raw_item  # type: ignore[misc]
    except Exception:
        return None
    optional = "optional" in str(name).casefold()
    status = maintenance_status_for_row(str(name), bool(ok), str(detail), optional)
    guidance = maintenance_row_guidance(str(name), status, optional)
    return {
        "row_key": maintenance_row_key(str(name)),
        "name": str(name),
        "ok": bool(ok),
        "tool_kind": maintenance_tool_kind(str(name)),
        "tool_source": maintenance_source_for_row(str(detail), bool(ok), status),
        "capability": maintenance_tool_capability(maintenance_tool_kind(str(name))),
        "failure_scope": maintenance_tool_failure_scope(maintenance_tool_kind(str(name)), optional),
        "optional": optional,
        "required": not optional,
        "status": status,
        "detail": str(detail),
        **guidance,
    }


def maintenance_health_rows(raw_rows: object) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for item in raw_rows or []:  # type: ignore[union-attr]
        row = maintenance_health_row(item)
        if row is not None:
            rows.append(row)
    return rows


def maintenance_workspace_counts(rows: list[dict[str, Any]]) -> dict[str, int]:
    return {
        "ok_count": sum(1 for row in rows if row.get("status") == "ok"),
        "missing_count": sum(1 for row in rows if row.get("status") == "missing"),
        "warning_count": sum(1 for row in rows if row.get("status") == "warning"),
    }


MAINTENANCE_HEALTH_STEP_ORDER: tuple[tuple[str, str, bool], ...] = (
    ("config_parse", "Config parse", True),
    ("path_reachability", "Path reachability", True),
    ("state_directory", "State directory", True),
    ("api_contract", "API contract", True),
    ("process_guard", "Process guard", True),
    ("bundle_layout", "Bundle layout", True),
    ("powershell", "PowerShell", True),
    ("ffmpeg", "FFmpeg", True),
    ("ffprobe", "ffprobe", True),
    ("mkvtoolnix", "MKVToolNix", True),
    ("mkvextract", "mkvextract", True),
    ("gpu_telemetry", "GPU telemetry", False),
    ("subtitle_helper", "ASS subtitle helper", True),
    ("subtitle_bdpgs_ocr", "BDPGS OCR tools", True),
    ("subtitle_vobsub_ocr", "VobSub OCR tools", True),
    ("pending_publish_path", "Pending-publish path", False),
)


def maintenance_progress_timestamp() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def maintenance_path_status(path: Path | None, *, required: bool) -> tuple[str, str]:
    if path is None:
        return ("blocked" if required else "warning", "Path is not configured.")
    try:
        exists = path.exists()
    except OSError as exc:
        return ("blocked" if required else "warning", f"{path} is not reachable: {exc}")
    if exists:
        return ("complete", str(path))
    return ("blocked" if required else "warning", f"{path} is not present.")


def maintenance_progress_path_steps(resolved: ResolvedPaths | None) -> dict[str, dict[str, Any]]:
    if resolved is None:
        return {
            "config_parse": {
                "status": "pending",
                "detail": "Resolved paths are not available yet.",
                "source": "resolved_paths",
            },
            "path_reachability": {
                "status": "pending",
                "detail": "Resolved paths are not available yet.",
                "source": "resolved_paths",
            },
            "state_directory": {
                "status": "pending",
                "detail": "Resolved paths are not available yet.",
                "source": "resolved_paths",
            },
            "pending_publish_path": {
                "status": "pending",
                "detail": "Resolved paths are not available yet.",
                "source": "resolved_paths",
            },
        }

    config_status, config_detail = maintenance_path_status(resolved.config_path, required=True)
    if config_status == "complete" and not isinstance(resolved.config_data, dict):
        config_status = "warning"
        config_detail = f"{resolved.config_path} exists, but parsed config data was not available."
    paths = [
        ("app root", resolved.app_root),
        ("workspace root", resolved.workspace_root),
        ("pipeline script", resolved.pipeline_path),
    ]
    missing_paths: list[str] = []
    for label, path in paths:
        status, detail = maintenance_path_status(path, required=True)
        if status != "complete":
            missing_paths.append(f"{label}: {detail}")
    path_status = "blocked" if missing_paths else "complete"
    path_detail = "; ".join(missing_paths) if missing_paths else "App root, workspace root, and pipeline script are reachable."
    state_path = resolved.state_root or resolved.local_base
    state_status, state_detail = maintenance_path_status(state_path, required=True)
    pending_status, pending_detail = maintenance_path_status(resolved.pending_push_path, required=False)
    return {
        "config_parse": {
            "status": config_status,
            "detail": config_detail,
            "source": str(resolved.config_path),
        },
        "path_reachability": {
            "status": path_status,
            "detail": path_detail,
            "source": "resolved_paths",
        },
        "state_directory": {
            "status": state_status,
            "detail": state_detail,
            "source": str(state_path or ""),
        },
        "pending_publish_path": {
            "status": pending_status,
            "detail": pending_detail,
            "source": str(resolved.pending_push_path or ""),
        },
    }


def maintenance_progress_tool_step_id(row: dict[str, Any]) -> str:
    tool_kind = str(row.get("tool_kind") or maintenance_tool_kind(str(row.get("name") or "")))
    if tool_kind == "config_schema":
        return "config_parse"
    if tool_kind in {"configured_root", "library_output_root"}:
        return "path_reachability"
    if tool_kind in {"runtime_state", "sqlite_mirror"}:
        return "state_directory"
    if tool_kind == "api_contract":
        return "api_contract"
    if tool_kind == "process_guard":
        return "process_guard"
    if tool_kind == "bundle_layout":
        return "bundle_layout"
    if tool_kind == "powershell_host":
        return "powershell"
    if tool_kind == "mkvtoolnix":
        return "mkvtoolnix"
    if tool_kind == "mkvextract":
        return "mkvextract"
    if tool_kind == "gpu_telemetry":
        return "gpu_telemetry"
    if tool_kind == "mediapipeline.pipeline.ass_to_srt_cli":
        return "subtitle_helper"
    if tool_kind in {"bdpgs_ocr", "bdpgs_tessdata"}:
        return "subtitle_bdpgs_ocr"
    if tool_kind in {"vobsub_ocr", "vobsub_tesseract"}:
        return "subtitle_vobsub_ocr"
    return tool_kind


def maintenance_progress_status_for_row(row: dict[str, Any]) -> str:
    if row.get("status") == "ok":
        return "complete"
    if row.get("status") == "running":
        return "active"
    if row.get("optional") is True:
        return "warning"
    return "blocked"


def maintenance_progress_worst_status(left: str, right: str) -> str:
    rank = {"pending": 0, "complete": 1, "warning": 2, "blocked": 3}
    return right if rank.get(right, 0) > rank.get(left, 0) else left


def maintenance_health_progress(
    resolved: ResolvedPaths | None,
    rows: list[dict[str, Any]] | None = None,
    *,
    status: str = "complete",
    active_step_id: str = "",
    active_detail: str = "",
    error: str = "",
) -> dict[str, Any]:
    row_list = list(rows or [])
    row_steps: dict[str, dict[str, Any]] = {}
    for row in row_list:
        step_id = maintenance_progress_tool_step_id(row)
        row_status = maintenance_progress_status_for_row(row)
        row_detail = f"{row.get('name') or step_id}: {row.get('detail') or ''}"
        existing = row_steps.get(step_id)
        if existing is None:
            row_steps[step_id] = {
                "status": row_status,
                "detail": row_detail,
                "source": row.get("tool_source") or row.get("source") or "check_environment_health",
                "row_key": row.get("row_key") or maintenance_row_key(str(row.get("name") or "")),
            }
        else:
            existing["status"] = maintenance_progress_worst_status(str(existing.get("status") or "pending"), row_status)
            existing["detail"] = "; ".join(part for part in (str(existing.get("detail") or ""), row_detail) if part)
            if not existing.get("row_key") and row.get("row_key"):
                existing["row_key"] = row.get("row_key")
    path_steps = maintenance_progress_path_steps(resolved)
    steps: list[dict[str, Any]] = []
    for step_id, label, required in MAINTENANCE_HEALTH_STEP_ORDER:
        data = row_steps.get(step_id) or path_steps.get(step_id) or {}
        step_status = str(data.get("status") or "pending")
        if step_id == active_step_id and step_status in {"pending", "unknown"}:
            step_status = "active"
        if error and step_id == active_step_id:
            step_status = "blocked" if required else "warning"
        steps.append(
            {
                "id": step_id,
                "label": label,
                "status": step_status,
                "detail": str(data.get("detail") or active_detail if step_id == active_step_id else data.get("detail") or ""),
                "source": str(data.get("source") or "maintenance_health"),
                "required": required,
                "optional": not required,
                "completed": step_status in {"complete", "warning", "blocked"},
                "row_key": data.get("row_key") or "",
            }
        )
    checked_count = sum(1 for step in steps if step["completed"])
    warning_count = sum(1 for step in steps if step["status"] == "warning")
    blocked_count = sum(1 for step in steps if step["status"] == "blocked" and step["required"])
    active_count = sum(1 for step in steps if step["status"] == "active")
    if error or blocked_count:
        operator_status = "blocked"
    elif status == "active" or active_count:
        operator_status = "active"
    elif warning_count:
        operator_status = "warning"
    elif checked_count == len(steps):
        operator_status = "complete"
    else:
        operator_status = "idle"
    percent = round((checked_count / len(steps)) * 100, 1) if steps else 0.0
    if operator_status in {"complete", "warning", "blocked"} and checked_count == len(steps):
        percent = 100.0
    detail = f"{checked_count}/{len(steps)} health step(s) checked"
    if active_step_id:
        active_label = next((step["label"] for step in steps if step["id"] == active_step_id), active_step_id)
        detail = f"{detail}; active: {active_label}"
    if error:
        detail = f"{detail}; error: {error}"
    updated_at = maintenance_progress_timestamp()
    progress_bar = {
        "id": "maintenance_health",
        "label": "Health check",
        "mode": "stepped",
        "percent": percent,
        "status": operator_status,
        "detail": detail,
        "source": "desktop_maintenance_workspace.v1",
        "updated_at": updated_at,
        "stale": False,
    }
    summary_lines = [
        f"Health progress: {operator_status}",
        f"Steps checked: {checked_count}/{len(steps)}",
        f"Required blocked: {blocked_count}",
        f"Warnings: {warning_count}",
        "Mutation guardrail: health progress is backend-authored probe evidence; WebView may render it but does not repair paths, install tools, launch media work, drain pending publish, or mutate files.",
    ]
    if error:
        summary_lines.insert(1, f"Error: {error}")
    return {
        "schema_version": "desktop_maintenance_health_progress.v1",
        "mode": "stepped",
        "status": operator_status,
        "percent": percent,
        "checked_count": checked_count,
        "total_steps": len(steps),
        "warning_count": warning_count,
        "blocked_count": blocked_count,
        "active_step_id": active_step_id,
        "steps": steps,
        "progress_bars": [progress_bar],
        "summary_lines": summary_lines,
        "updated_at": updated_at,
        "read_only": True,
    }


def maintenance_health_progress_with_error(current: dict[str, Any], error: str) -> dict[str, Any]:
    payload = dict(current or {})
    steps = [dict(step) for step in payload.get("steps") or [] if isinstance(step, dict)]
    active_step_id = str(payload.get("active_step_id") or "")
    for step in steps:
        if active_step_id and step.get("id") == active_step_id:
            step["status"] = "blocked" if step.get("required") else "warning"
            step["detail"] = f"{step.get('detail') or step.get('label') or active_step_id}: {error}"
            step["completed"] = True
    checked_count = sum(1 for step in steps if step.get("completed") is True)
    warning_count = sum(1 for step in steps if step.get("status") == "warning")
    blocked_count = sum(1 for step in steps if step.get("status") == "blocked" and step.get("required") is True)
    total_steps = len(steps)
    percent = round((checked_count / total_steps) * 100, 1) if total_steps else 0.0
    updated_at = maintenance_progress_timestamp()
    detail = f"{checked_count}/{total_steps} health step(s) checked; error: {error}"
    progress_bar = {
        "id": "maintenance_health",
        "label": "Health check",
        "mode": "stepped",
        "percent": percent,
        "status": "blocked",
        "detail": detail,
        "source": "desktop_maintenance_workspace.v1",
        "updated_at": updated_at,
        "stale": False,
    }
    return {
        **payload,
        "schema_version": "desktop_maintenance_health_progress.v1",
        "mode": "stepped",
        "status": "blocked",
        "percent": percent,
        "checked_count": checked_count,
        "total_steps": total_steps,
        "warning_count": warning_count,
        "blocked_count": blocked_count,
        "steps": steps,
        "progress_bars": [progress_bar],
        "summary_lines": [
            "Health progress: blocked",
            f"Error: {error}",
            f"Steps checked: {checked_count}/{total_steps}",
            f"Required blocked: {blocked_count}",
            f"Warnings: {warning_count}",
            "Mutation guardrail: health progress is backend-authored probe evidence; WebView may render it but does not repair paths, install tools, launch media work, drain pending publish, or mutate files.",
        ],
        "updated_at": updated_at,
        "read_only": True,
    }

__all__ = [
    "maintenance_row_key",
    "maintenance_row_guidance",
    "maintenance_tool_kind",
    "maintenance_tool_capability",
    "maintenance_tool_failure_scope",
    "maintenance_tool_source",
    "maintenance_process_guard_is_running",
    "maintenance_status_for_row",
    "maintenance_source_for_row",
    "maintenance_row_blocks_required",
    "maintenance_toolchain_row",
    "maintenance_toolchain_evidence",
    "maintenance_health_row",
    "maintenance_health_rows",
    "maintenance_workspace_counts",
    "MAINTENANCE_HEALTH_STEP_ORDER",
    "maintenance_progress_timestamp",
    "maintenance_path_status",
    "maintenance_progress_path_steps",
    "maintenance_progress_tool_step_id",
    "maintenance_progress_status_for_row",
    "maintenance_progress_worst_status",
    "maintenance_health_progress",
    "maintenance_health_progress_with_error",
]
