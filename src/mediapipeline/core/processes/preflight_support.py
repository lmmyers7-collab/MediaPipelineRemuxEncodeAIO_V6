"""Process launch preflight facade adapter."""

from __future__ import annotations

from datetime import datetime, UTC
from pathlib import Path
from typing import Any

from mediapipeline.core.config.settings_policy import settings_encoder_capability_report
from mediapipeline.core.kernel.dto_commands import CommandResult
from mediapipeline.core.kernel.runtime.subprocess_runner import run_capture
from mediapipeline.core.kernel.dto_base import JsonMap, json_safe
from mediapipeline.core.paths.contracts import ResolvedPaths

from mediapipeline.core.config.identity import config_identity_block_reasons
from mediapipeline.core.processes.audit_policy import AUDIT_LIBRARY_ROOT_ERROR, resolve_audit_library_root
from mediapipeline.core.processes.pipeline_policy import (
    PIPELINE_EXTRA_ARGS_ERROR,
    PIPELINE_NETWORK_MODE_BLOCK_ERROR,
    PIPELINE_SLEEP_SECONDS_ERROR,
    configured_network_role,
    coordinator_also_encode_locally_enabled,
    is_supported_pipeline_start_mode,
    pipeline_start_network_mode_label,
    network_role_is_valid,
)
from mediapipeline.core.processes.launch_intent import normalize_pipeline_launch_intent
from mediapipeline.core.processes.rerun_policy import (
    CSV_RERUN_PATH_ERROR,
    rerun_lifecycle_errors,
    rerun_lifecycle_from_request,
    rerun_csv_path_from_request,
    rerun_dry_run_from_request,
    rerun_plan_only_from_request,
)
from mediapipeline.core.processes.rerun_preview import rerun_csv_preview_payload
from mediapipeline.core.processes.path_evidence import (
    LAUNCH_PATH_HEALTH_TIMEOUT_SECONDS,
    configured_path_health,
    path_evidence,
)
from mediapipeline.core.processes.schedule_policy import continuous_schedule_stop_watcher_preflight_check
from mediapipeline.core.processes.source_path_policy import SOURCE_ROOT_SCOPE_TEXT, queue_source_file_validation
from mediapipeline.core.processes.preflight_types import (
    preflight_check,
    preflight_counts,
    preflight_display_status,
    preflight_status,
)


LAUNCH_PREFLIGHT_SCHEMA_VERSION = "desktop_launch_preflight.v1"
LAUNCH_READINESS_SCHEMA_VERSION = "desktop_launch_readiness.v1"
LAUNCH_PREFLIGHT_TARGETS = frozenset({"pipeline", "audit", "rerun"})
LAUNCH_PREFLIGHT_PATH_HEALTH_TIMEOUT_SECONDS = LAUNCH_PATH_HEALTH_TIMEOUT_SECONDS
ENCODER_CAPABILITY_REFRESH_MAX_AGE_SECONDS = 7 * 24 * 60 * 60
ENCODER_CAPABILITY_REFRESH_TIMEOUT_SECONDS = 60.0


def _preflight_check(
    key: str,
    label: str,
    status: str,
    evidence: str,
    action: str,
    *,
    detail: list[Any] | None = None,
    recovery_actions: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    return preflight_check(
        key,
        label,
        status,
        evidence,
        action,
        detail=detail,
        recovery_actions=recovery_actions,
    )


def _preflight_status(checks: list[dict[str, Any]]) -> str:
    return preflight_status(checks)


def _preflight_counts(checks: list[dict[str, Any]]) -> dict[str, int]:
    return preflight_counts(checks)


def _preflight_display_status(status: str) -> str:
    return preflight_display_status(status)


def _preflight_readiness_summary_lines(
    *,
    target: str,
    start_route: str,
    status: str,
    can_request_start: bool,
    checks: list[dict[str, Any]],
    final_authority: str,
) -> list[str]:
    display_status = _preflight_display_status(status)
    counts = _preflight_counts(checks)
    non_ready = [check for check in checks if str(check.get("status") or "").casefold() != "ready"]
    lines = [
        "Launch readiness (backend-authored):",
        f"Backend snapshot: ok - source GET /api/launch/preflight for {target}.",
        f"Pipeline state: backend preflight status {display_status}.",
        "Close readiness: represented by the backend Active work guard check; start routes re-check at submission time.",
        "Saved settings: rendered from backend Settings workspace; backend validation remains authoritative at start.",
        "Schedule: represented by backend Schedule gate and Continuous schedule-stop watcher checks.",
        "Backend continuous watcher: inspect the Continuous schedule-stop watcher preflight row for PID/deadline evidence.",
        f"Target: {target}; start route: {start_route or '(none)'}; can request start: {'yes' if can_request_start else 'no'}.",
        f"Counts: ready={counts.get('ready', 0)}; review={counts.get('review', 0)}; high review={counts.get('high review', 0)}; blocked={counts.get('blocked', 0)}; unknown={counts.get('unknown', 0)}.",
        "Launch guidance:",
    ]
    if non_ready:
        lines.append("- Review backend-authored non-ready checks before pressing Start.")
        for check in non_ready[:8]:
            lines.append(
                f"- {check.get('label') or check.get('key') or 'Check'}: {check.get('status') or 'unknown'}; {check.get('action') or 'review before start'}"
            )
        if len(non_ready) > 8:
            lines.append(f"- {len(non_ready) - 8} more backend preflight check(s) need review.")
    else:
        lines.append("- Backend preflight reports no non-ready checks; the start route still re-checks current state.")
    lines.append(final_authority)
    lines.append("Backend launch locking and gating remain the source of truth.")
    return lines


def _preflight_operator_readiness(
    *,
    target: str,
    start_route: str,
    status: str,
    can_request_start: bool,
    checks: list[dict[str, Any]],
    final_authority: str,
) -> dict[str, Any]:
    counts = _preflight_counts(checks)
    non_ready = [check for check in checks if str(check.get("status") or "").casefold() != "ready"]
    return {
        "schema_version": LAUNCH_READINESS_SCHEMA_VERSION,
        "evidence_authority": "backend",
        "source_route": "/api/launch/preflight",
        "target": target,
        "start_route": start_route,
        "operator_status": status,
        "display_status": _preflight_display_status(status),
        "can_request_start": can_request_start,
        "non_ready_count": len(non_ready),
        "counts": counts,
        "summary_lines": _preflight_readiness_summary_lines(
            target=target,
            start_route=start_route,
            status=status,
            can_request_start=can_request_start,
            checks=checks,
            final_authority=final_authority,
        ),
        "non_ready_checks": [
            {
                "key": check.get("key") or "",
                "label": check.get("label") or "",
                "status": check.get("status") or "unknown",
                "evidence": check.get("evidence") or "",
                "action": check.get("action") or "",
                "recovery_actions": list(check.get("recovery_actions") or []),
            }
            for check in non_ready
        ],
        "final_authority": final_authority,
    }


def _service_callable(service: object, name: str) -> bool:
    return callable(getattr(service, name, None))


def _parse_report_timestamp(value: Any) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = f"{text[:-1]}+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _encoder_capability_report_age_seconds(report: dict[str, Any], now: datetime) -> int | None:
    generated_at = _parse_report_timestamp(report.get("generated_at"))
    if generated_at is None:
        return None
    return max(0, int((now - generated_at).total_seconds()))


def _encoder_capability_report_refresh_reason(report: dict[str, Any], now: datetime) -> tuple[bool, str, int | None]:
    state = str(report.get("operator_status_state") or "unknown").casefold()
    age_seconds = _encoder_capability_report_age_seconds(report, now)
    if state == "missing" or not report.get("exists"):
        return True, "missing", age_seconds
    if state == "unknown":
        return True, "unknown", age_seconds
    if state == "warning" and not str(report.get("report_schema") or "").strip():
        return True, "unreadable", age_seconds
    if age_seconds is None:
        return True, "generated_at_missing", age_seconds
    if age_seconds > ENCODER_CAPABILITY_REFRESH_MAX_AGE_SECONDS:
        return True, "stale", age_seconds
    return False, "fresh", age_seconds


def _path_command_is_available(raw: str) -> bool:
    candidate = Path(raw)
    if candidate.is_absolute() or candidate.parent != Path("."):
        return candidate.is_file()
    return True


def _encoder_capability_refresh_skip_reason(resolved: ResolvedPaths, report_path: Path | None) -> str:
    host = str(resolved.powershell_host or "").strip()
    if report_path is None:
        return "encoder capability report path is unavailable"
    if not host:
        return "PowerShell host is unavailable"
    if not _path_command_is_available(host):
        return f"PowerShell host does not exist: {host}"
    if resolved.pipeline_path is None or not Path(resolved.pipeline_path).is_file():
        return f"pipeline entrypoint does not exist: {resolved.pipeline_path or ''}"
    if resolved.config_path is None or not Path(resolved.config_path).is_file():
        return f"config file does not exist: {resolved.config_path or ''}"
    return ""


def _encoder_capability_refresh_command(resolved: ResolvedPaths, report_path: Path) -> list[str]:
    return [
        str(resolved.powershell_host),
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        str(resolved.pipeline_path),
        "-ConfigPath",
        str(resolved.config_path),
        "-DumpEncoderCapabilitiesPath",
        str(report_path),
    ]


def _encoder_capability_refresh_working_directory(resolved: ResolvedPaths) -> Path | None:
    for value in (resolved.workspace_root, resolved.app_root):
        if value is not None:
            path = Path(value)
            if path.exists() and path.is_dir():
                return path
    return None


def _encoder_capability_refresh_attempt(
    resolved: ResolvedPaths,
    report: dict[str, Any],
    *,
    refresh_requested: bool,
    force_refresh: bool = False,
) -> dict[str, Any]:
    now = datetime.now(UTC)
    needed, reason, age_seconds = _encoder_capability_report_refresh_reason(report, now)
    if force_refresh:
        needed = True
        reason = "explicit_refresh"
    refresh: dict[str, Any] = {
        "schema_version": "encoder_capability_auto_refresh.v1",
        "needed": needed,
        "reason": reason,
        "attempted": False,
        "ok": not needed,
        "age_seconds": age_seconds,
        "max_age_seconds": ENCODER_CAPABILITY_REFRESH_MAX_AGE_SECONDS,
        "timeout_seconds": ENCODER_CAPABILITY_REFRESH_TIMEOUT_SECONDS,
        "skipped_reason": "",
        "returncode": None,
        "timed_out": False,
        "message": "Encoder capability report is fresh." if not needed else "",
        "requested": bool(refresh_requested),
    }
    if not needed:
        return refresh
    if not refresh_requested:
        refresh["skipped_reason"] = "refresh not requested"
        refresh["message"] = "Auto-refresh skipped: refresh not requested."
        return refresh
    report_path_text = str(report.get("source_path") or "").strip()
    report_path = Path(report_path_text) if report_path_text else None
    skipped_reason = _encoder_capability_refresh_skip_reason(resolved, report_path)
    if skipped_reason:
        refresh["skipped_reason"] = skipped_reason
        refresh["message"] = f"Auto-refresh skipped: {skipped_reason}."
        return refresh
    if report_path is None:
        refresh["skipped_reason"] = "encoder capability report path is unavailable"
        refresh["message"] = "Auto-refresh skipped: encoder capability report path is unavailable."
        return refresh
    command = _encoder_capability_refresh_command(resolved, report_path)
    refresh["attempted"] = True
    refresh["command"] = command
    try:
        report_path.parent.mkdir(parents=True, exist_ok=True)
        result = run_capture(
            command,
            timeout_seconds=ENCODER_CAPABILITY_REFRESH_TIMEOUT_SECONDS,
            cwd=_encoder_capability_refresh_working_directory(resolved),
            hidden=True,
            label="encoder capability diagnostic refresh",
        )
    except Exception as exc:
        refresh["message"] = f"Auto-refresh failed to start: {exc}"
        return refresh
    refresh.update(
        {
            "returncode": result.returncode,
            "timed_out": bool(result.timed_out),
            "ok": result.returncode == 0 and not result.timed_out,
            "message": (
                "Auto-refresh completed."
                if result.returncode == 0 and not result.timed_out
                else f"Auto-refresh failed: {result.output_tail}"
            ),
        }
    )
    return refresh


def _encoder_capability_report_with_auto_refresh(
    resolved: ResolvedPaths,
    *,
    refresh_requested: bool = False,
    force_refresh: bool = False,
) -> dict[str, Any]:
    report = settings_encoder_capability_report(resolved)
    refresh = _encoder_capability_refresh_attempt(
        resolved,
        report,
        refresh_requested=refresh_requested,
        force_refresh=force_refresh,
    )
    if refresh.get("attempted") and refresh.get("ok"):
        report = settings_encoder_capability_report(resolved)
    now = datetime.now(UTC)
    final_needed, final_reason, final_age = _encoder_capability_report_refresh_reason(report, now)
    report["auto_refresh"] = refresh
    report["refresh_needed"] = final_needed
    report["refresh_reason"] = final_reason
    report["age_seconds"] = final_age
    report["stale_after_seconds"] = ENCODER_CAPABILITY_REFRESH_MAX_AGE_SECONDS
    report["stale"] = final_reason == "stale"
    if final_needed and str(report.get("operator_status_state") or "").casefold() == "ready":
        report["operator_status"] = "Stale" if final_reason == "stale" else "Review"
        report["operator_status_state"] = "warning"
        summary_lines = list(report.get("summary_lines") or [])
        summary_lines.append(str(refresh.get("message") or "Encoder capability report needs refresh."))
        report["summary_lines"] = summary_lines
    return report


def _network_role_preflight_check(config: dict[str, Any]) -> dict[str, Any]:
    role = configured_network_role(config)
    coordinator_also_encode_locally = coordinator_also_encode_locally_enabled(config)
    mode_label = pipeline_start_network_mode_label(
        role,
        coordinator_also_encode_locally=coordinator_also_encode_locally,
    )
    valid = network_role_is_valid(role)
    allowed = role == "standalone" and valid
    action = (
        "Use Network/Workers controls for distributed work, or save NetworkRole=standalone before using Launch."
        if valid
        else "Fix NetworkRole to standalone, coordinator, or worker before using Launch."
    )
    return _preflight_check(
        "network_role",
        "Network mode",
        "ready" if allowed else "blocked",
        f"mode={mode_label}; NetworkRole={role or '(missing/empty)'}; valid={'yes' if valid else 'no'}",
        action,
        detail=[] if allowed else [PIPELINE_NETWORK_MODE_BLOCK_ERROR],
    )


def _single_file_scope_preflight_check(resolved: ResolvedPaths, single_file: str) -> dict[str, Any]:
    if not single_file:
        return _preflight_check(
            "single_file_scope",
            "Single-file source scope",
            "ready",
            "single_file not requested; backend launch will use normal queue scope.",
            "Leave Single File blank for normal queue launches; Queue display filters and row selection are not submitted.",
        )
    validation = queue_source_file_validation(resolved, single_file, field_name="single_file")
    evidence = (
        f"single_file={validation.get('path') or '(empty)'}; "
        f"normalized={validation.get('normalized_path') or '(none)'}; "
        f"absolute={'yes' if validation.get('is_absolute') else 'no'}; "
        f"under_source_root={'yes' if validation.get('under_source_root') else 'no'}; "
        f"exists={'yes' if validation.get('exists') else 'no'}; "
        f"is_file={'yes' if validation.get('is_file') else 'no'}; "
        f"suffix={validation.get('media_suffix') or '(none)'}; "
        f"supported_suffix={'yes' if validation.get('media_suffix_supported') else 'no'}"
    )
    return _preflight_check(
        "single_file_scope",
        "Single-file source scope",
        "ready" if validation.get("ok") else "blocked",
        evidence,
        (
            "Start route will pass this normalized single-file path to the backend pipeline."
            if validation.get("ok")
            else f"Choose one existing supported media file under {SOURCE_ROOT_SCOPE_TEXT}."
        ),
        detail=[json_safe(validation)],
    )


def _encoder_capability_report_preflight_check(
    resolved: ResolvedPaths,
    *,
    refresh_requested: bool = False,
) -> dict[str, Any]:
    report = _encoder_capability_report_with_auto_refresh(resolved, refresh_requested=refresh_requested)
    state = str(report.get("operator_status_state") or "unknown").casefold()
    if state == "ready":
        status = "ready"
        action = "Launch still uses saved settings; start route will re-check launch guards without changing encoder choices."
    elif state in {"missing", "warning"}:
        status = "review"
        action = "Review or refresh backend-owned encoder capability diagnostic evidence before relying on hardware encoder choices."
    else:
        status = "unknown"
        action = "Refresh the backend Settings workspace or rerun the backend-owned encoder capability diagnostic."
    available = [str(item) for item in report.get("available_encoders", []) if str(item)]
    unavailable = [str(item) for item in report.get("unavailable_encoders", []) if str(item)]
    active = [str(item) for item in report.get("active_encoders", []) if str(item)]
    inactive_available = [str(item) for item in report.get("available_inactive_encoders", []) if str(item)]
    activation_unknown = [str(item) for item in report.get("activation_unknown_encoders", []) if str(item)]
    hardware_runtime_verified = [str(item) for item in report.get("hardware_runtime_verified_encoders", []) if str(item)]
    hardware_runtime_skipped = [str(item) for item in report.get("hardware_runtime_skipped_encoders", []) if str(item)]
    active_hardware_unverified = [
        str(item) for item in report.get("active_hardware_runtime_unverified_encoders", []) if str(item)
    ]
    auto_refresh = report.get("auto_refresh") if isinstance(report.get("auto_refresh"), dict) else {}
    if auto_refresh.get("attempted"):
        auto_refresh_status = "ok" if auto_refresh.get("ok") else "failed"
    elif auto_refresh.get("needed"):
        auto_refresh_status = "skipped"
    else:
        auto_refresh_status = "not_needed"
    evidence = (
        f"status={report.get('operator_status') or 'Unknown'}; "
        f"source_path={report.get('source_path') or '(unavailable)'}; "
        f"exists={'yes' if report.get('exists') else 'no'}; "
        f"VideoCodec={report.get('video_codec') or '(unknown)'}; "
        f"EncoderBackend={report.get('encoder_backend') or '(unknown)'}; "
        f"available_count={len(available)}; "
        f"unavailable_count={len(unavailable)}; "
        f"active_count={len(active)}; "
        f"inactive_available_count={len(inactive_available)}; "
        f"activation_unknown_count={len(activation_unknown)}; "
        f"hardware_runtime_verified_count={len(hardware_runtime_verified)}; "
        f"hardware_runtime_skipped_count={len(hardware_runtime_skipped)}; "
        f"active_hardware_unverified_count={len(active_hardware_unverified)}; "
        f"refresh={auto_refresh_status}; "
        f"refresh_reason={report.get('refresh_reason') or 'fresh'}; "
        f"read_only={'yes' if report.get('read_only') else 'no'}"
    )
    return _preflight_check(
        "encoder_capability_report",
        "Encoder capability evidence",
        status,
        evidence,
        action,
        detail=[
            json_safe(
                {
                    "schema_version": report.get("schema_version") or "",
                    "read_only": bool(report.get("read_only")),
                    "source": report.get("source") or "",
                    "source_path": report.get("source_path") or "",
                    "exists": bool(report.get("exists")),
                    "operator_status": report.get("operator_status") or "",
                    "operator_status_state": report.get("operator_status_state") or "",
                    "report_schema": report.get("report_schema") or "",
                    "generated_at": report.get("generated_at") or "",
                    "video_codec": report.get("video_codec") or "",
                    "encoder_backend": report.get("encoder_backend") or "",
                    "selection": report.get("selection") or {},
                    "available_encoders": available,
                    "unavailable_encoders": unavailable,
                    "active_encoders": active,
                    "available_inactive_encoders": inactive_available,
                    "activation_unknown_encoders": activation_unknown,
                    "hardware_runtime_verified_encoders": hardware_runtime_verified,
                    "hardware_runtime_skipped_encoders": hardware_runtime_skipped,
                    "active_hardware_runtime_unverified_encoders": active_hardware_unverified,
                    "refresh_needed": bool(report.get("refresh_needed")),
                    "refresh_reason": report.get("refresh_reason") or "",
                    "age_seconds": report.get("age_seconds"),
                    "stale_after_seconds": report.get("stale_after_seconds"),
                    "stale": bool(report.get("stale")),
                    "auto_refresh": json_safe(auto_refresh),
                    "backend_counts": report.get("backend_counts") or {},
                    "encoding_capability_facts": report.get("encoding_capability_facts") or {},
                    "evidence": report.get("evidence") or {},
                    "summary_lines": list(report.get("summary_lines") or []),
                    "errors": list(report.get("errors") or []),
                }
            )
        ],
    )



__all__ = (
    "LAUNCH_PREFLIGHT_SCHEMA_VERSION",
    "LAUNCH_READINESS_SCHEMA_VERSION",
    "LAUNCH_PREFLIGHT_TARGETS",
    "LAUNCH_PREFLIGHT_PATH_HEALTH_TIMEOUT_SECONDS",
    "ENCODER_CAPABILITY_REFRESH_MAX_AGE_SECONDS",
    "ENCODER_CAPABILITY_REFRESH_TIMEOUT_SECONDS",
    "_preflight_check",
    "_preflight_status",
    "_preflight_counts",
    "_preflight_display_status",
    "_preflight_readiness_summary_lines",
    "_preflight_operator_readiness",
    "_service_callable",
    "_parse_report_timestamp",
    "_encoder_capability_report_age_seconds",
    "_encoder_capability_report_refresh_reason",
    "_path_command_is_available",
    "_encoder_capability_refresh_skip_reason",
    "_encoder_capability_refresh_command",
    "_encoder_capability_refresh_working_directory",
    "_encoder_capability_refresh_attempt",
    "_encoder_capability_report_with_auto_refresh",
    "_network_role_preflight_check",
    "_single_file_scope_preflight_check",
    "_encoder_capability_report_preflight_check",
)
