"""Read-only process launch preflight facade adapter."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from mediapipeline.core.config.settings_policy import settings_encoder_capability_report
from mediapipeline.desktop.application.dto_base import JsonMap, json_safe
from mediapipeline.desktop.models import ResolvedPaths

from mediapipeline.core.config.identity import config_identity_block_reasons
from mediapipeline.core.processes.audit_policy import AUDIT_LIBRARY_ROOT_ERROR, resolve_audit_library_root
from mediapipeline.core.processes.pipeline_policy import (
    PIPELINE_EXTRA_ARGS_ERROR,
    PIPELINE_NETWORK_MODE_BLOCK_ERROR,
    PIPELINE_SLEEP_SECONDS_ERROR,
    configured_network_role,
    coordinator_also_encode_locally_enabled,
    is_supported_pipeline_start_mode,
    normalize_network_role,
    normalize_pipeline_extra_args,
    normalize_pipeline_start_mode,
    parse_pipeline_sleep_seconds,
    pipeline_extra_args_error,
    pipeline_start_network_mode_label,
    network_role_is_valid,
)
from mediapipeline.core.processes.rerun_policy import (
    CSV_RERUN_MODE_ERROR,
    CSV_RERUN_PATH_ERROR,
    rerun_csv_path_from_request,
    rerun_dry_run_from_request,
    rerun_modes_are_supported,
    rerun_modes_from_request,
    rerun_plan_only_from_request,
)
from mediapipeline.core.processes.path_evidence import configured_path_health, path_evidence
from mediapipeline.core.processes.schedule_policy import continuous_schedule_stop_watcher_preflight_check
from mediapipeline.core.processes.source_path_policy import SOURCE_ROOT_SCOPE_TEXT, queue_source_file_validation


LAUNCH_PREFLIGHT_SCHEMA_VERSION = "desktop_launch_preflight.v1"
LAUNCH_READINESS_SCHEMA_VERSION = "desktop_launch_readiness.v1"
LAUNCH_PREFLIGHT_TARGETS = frozenset({"pipeline", "audit", "rerun"})


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
    row = {
        "key": key,
        "label": label,
        "status": status,
        "evidence": evidence,
        "action": action,
        "detail": detail or [],
    }
    if recovery_actions:
        row["recovery_actions"] = recovery_actions
    return row


def _preflight_status(checks: list[dict[str, Any]]) -> str:
    statuses = {str(check.get("status") or "").casefold() for check in checks}
    if "blocked" in statuses:
        return "blocked"
    if "high review" in statuses:
        return "high review"
    if "review" in statuses:
        return "review"
    if "unknown" in statuses:
        return "unknown"
    return "ready"


def _preflight_counts(checks: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for check in checks:
        status = str(check.get("status") or "unknown")
        counts[status] = counts.get(status, 0) + 1
    return counts


def _preflight_display_status(status: str) -> str:
    normalized = str(status or "").casefold()
    if normalized == "blocked":
        return "Blocked"
    if normalized == "high review":
        return "High review"
    if normalized == "review":
        return "Review"
    if normalized == "unknown":
        return "Evidence incomplete"
    if normalized == "ready":
        return "Ready"
    return "Evidence incomplete"


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


def _encoder_capability_report_preflight_check(resolved: ResolvedPaths) -> dict[str, Any]:
    report = settings_encoder_capability_report(resolved)
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
                    "backend_counts": report.get("backend_counts") or {},
                    "encoding_capability_facts": report.get("encoding_capability_facts") or {},
                    "summary_lines": list(report.get("summary_lines") or []),
                    "errors": list(report.get("errors") or []),
                }
            )
        ],
    )


class ProcessFacadeMixin:
    """Read-only process launch preflight helpers."""

    service: object

    def get_launch_preflight(self, resolved: ResolvedPaths, request: dict[str, Any]) -> JsonMap:
        target = str(request.get("target") or "pipeline").strip().casefold()
        if target == "csv":
            target = "rerun"
        if target not in LAUNCH_PREFLIGHT_TARGETS:
            checks = [
                _preflight_check(
                    "target",
                    "Launch target",
                    "blocked",
                    f"target={target or '(empty)'}",
                    "Use target pipeline, audit, or rerun.",
                    detail=[f"Allowed targets: {', '.join(sorted(LAUNCH_PREFLIGHT_TARGETS))}"],
                )
            ]
            return self._launch_preflight_payload(target or "unknown", request, checks, start_route="")
        if target == "pipeline":
            checks, normalized, start_route = self._pipeline_launch_preflight_checks(resolved, request)
        elif target == "audit":
            checks, normalized, start_route = self._audit_launch_preflight_checks(resolved, request)
        else:
            checks, normalized, start_route = self._rerun_launch_preflight_checks(resolved, request)
        return self._launch_preflight_payload(target, normalized, checks, start_route=start_route)

    def _launch_preflight_payload(
        self,
        target: str,
        request: dict[str, Any],
        checks: list[dict[str, Any]],
        *,
        start_route: str,
    ) -> JsonMap:
        status = _preflight_status(checks)
        blocked = sum(1 for check in checks if check.get("status") == "blocked")
        review = sum(1 for check in checks if check.get("status") in {"review", "high review", "unknown"})
        can_request_start = blocked == 0
        final_authority = "Backend start routes remain authoritative; this preflight does not reserve locks, launch processes, mutate config, write control flags, or touch media files."
        return json_safe(
            {
                "schema_version": LAUNCH_PREFLIGHT_SCHEMA_VERSION,
                "target": target,
                "start_route": start_route,
                "status": status,
                "can_request_start": can_request_start,
                "final_authority": final_authority,
                "blocked_count": blocked,
                "review_count": review,
                "counts": _preflight_counts(checks),
                "operator_readiness": _preflight_operator_readiness(
                    target=target,
                    start_route=start_route,
                    status=status,
                    can_request_start=can_request_start,
                    checks=checks,
                    final_authority=final_authority,
                ),
                "request": request,
                "checks": checks,
            }
        )

    def _process_launch_lock_preflight_check(self, label: str) -> dict[str, Any]:
        lock, lock_message = self._acquire_process_launch_lock(label)
        if lock_message:
            return _preflight_check(
                "process_launch_lock",
                "Process launch lock",
                "blocked",
                lock_message,
                "Wait for the current backend launch command to finish before submitting another start request.",
            )
        self._release_process_launch_lock(lock)
        return _preflight_check(
            "process_launch_lock",
            "Process launch lock",
            "ready",
            "Launch lock is currently available.",
            "Start route will re-check the lock at submission time.",
        )

    def _active_work_preflight_check(self, resolved: ResolvedPaths, action: str) -> dict[str, Any]:
        block_message = self._active_work_block_message(resolved, action)
        if block_message:
            return _preflight_check(
                "active_work",
                "Active work guard",
                "blocked",
                block_message,
                "Do not start additional work until active processing completes or backend-owned controls intentionally stop/pause it.",
            )
        return _preflight_check(
            "active_work",
            "Active work guard",
            "ready",
            "No active-work block is currently reported.",
            "Start route will re-check active work at submission time.",
        )

    def _config_identity_preflight_check(self, resolved: ResolvedPaths) -> dict[str, Any]:
        identity = dict(getattr(resolved, "config_identity", {}) or {})
        reasons = config_identity_block_reasons(identity)
        if reasons:
            return _preflight_check(
                "config_identity",
                "Active config identity",
                "blocked",
                str(identity.get("operator_status") or "Config is not ready."),
                "Restore a verified operator PSD1 before launching.",
                detail=reasons + [f"config_path={identity.get('config_path') or resolved.config_path}"],
            )
        if identity:
            return _preflight_check(
                "config_identity",
                "Active config identity",
                "ready",
                f"key_count={identity.get('key_count')}; sha256={str(identity.get('sha256') or '')[:16]}",
                "Start route will re-check the active config identity before launch.",
                detail=[f"config_path={identity.get('config_path') or resolved.config_path}"],
            )
        return _preflight_check(
            "config_identity",
            "Active config identity",
            "unknown",
            "Config identity evidence is not available in this resolved path snapshot.",
            "Refresh the backend Settings workspace before launch.",
        )

    def _configured_path_health_preflight_check(
        self,
        resolved: ResolvedPaths,
        *,
        path_health: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        health = path_health or configured_path_health(resolved)
        if not health.get("rows"):
            return None
        operator_status = str(health.get("operator_status") or "unknown").casefold()
        if operator_status == "ready":
            status = "ready"
        elif operator_status == "blocked":
            status = "high review"
        elif operator_status == "review":
            status = "review"
        else:
            status = "unknown"
        issue_lines = [
            str(line)
            for line in health.get("summary_lines", [])
            if str(line).strip()
        ]
        return _preflight_check(
            "configured_path_health",
            "Configured server/folder health",
            status,
            str(health.get("operator_summary") or "Configured path health is incomplete."),
            "Resolve unreachable configured source/output/scratch roots before pressing Start.",
            detail=issue_lines[:10],
        )

    def _autonomy_health_preflight_check(
        self,
        resolved: ResolvedPaths,
        *,
        path_health: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        health = self._autonomy_health_for_resolved(resolved, path_health=path_health)
        status = str(health.get("overall_status") or "unknown").casefold()
        if status == "ready":
            check_status = "ready"
        elif status == "blocked":
            check_status = "blocked"
        else:
            check_status = "review"
        blockers = [item for item in health.get("blockers", []) if isinstance(item, dict)]
        review_items = [item for item in health.get("review_items", []) if isinstance(item, dict)]
        detail = [
            f"overall_status={status}",
            f"blocked_count={len(blockers)}",
            f"review_count={len(review_items)}",
        ]
        recovery_actions: list[dict[str, Any]] = []
        for item in blockers[:5]:
            detail.append(f"{item.get('code')}: {item.get('message')}")
            recovery_action = item.get("recovery_action")
            if isinstance(recovery_action, dict):
                recovery_actions.append(json_safe(recovery_action))
                detail.append(f"recovery_action={recovery_action.get('kind')}: {recovery_action.get('label')}")
        if not recovery_actions:
            for item in review_items[:5]:
                recovery_action = item.get("recovery_action")
                if isinstance(recovery_action, dict):
                    recovery_actions.append(json_safe(recovery_action))
                    detail.append(f"recovery_action={recovery_action.get('kind')}: {recovery_action.get('label')}")
                    break
        return _preflight_check(
            "autonomy_health",
            "Autonomy health gate",
            check_status,
            f"overall_status={status}; can_start_new_work={'yes' if status != 'blocked' else 'no'}",
            str(
                (health.get("launch_gate") if isinstance(health.get("launch_gate"), dict) else {}).get("safe_next_action")
                or "Review autonomy health before unattended launch."
            ),
            detail=detail,
            recovery_actions=recovery_actions,
        )

    def _pipeline_launch_preflight_checks(
        self,
        resolved: ResolvedPaths,
        request: dict[str, Any],
    ) -> tuple[list[dict[str, Any]], dict[str, Any], str]:
        config = dict(resolved.config_data or {})
        network_role = configured_network_role(config)
        network_mode_label = pipeline_start_network_mode_label(
            network_role,
            coordinator_also_encode_locally=coordinator_also_encode_locally_enabled(config),
        )
        mode = normalize_pipeline_start_mode(request.get("mode"))
        sleep_seconds, sleep_error = parse_pipeline_sleep_seconds(request.get("sleep_seconds"))
        extra_args = normalize_pipeline_extra_args(request.get("extra_args"))
        extra_args_error = pipeline_extra_args_error(extra_args, False)
        normalized = {
            "target": "pipeline",
            "mode": mode,
            "sleep_seconds": sleep_seconds if sleep_seconds is not None else request.get("sleep_seconds"),
            "show_config": bool(request.get("show_config", False)),
            "show_console": bool(request.get("show_console", False)),
            "single_file": str(request.get("single_file") or "").strip(),
            "schedule_override": str(request.get("schedule_override") or "").strip(),
            "extra_args_present": bool(extra_args),
            "allow_extra_args": False,
            "network_role": network_role,
            "network_mode_label": network_mode_label,
        }
        single_file_check = _single_file_scope_preflight_check(resolved, normalized["single_file"])
        normalized["single_file_validation"] = single_file_check["detail"][0] if single_file_check["detail"] else {
            "ok": True,
            "status": "ready",
            "message": "single_file not requested; backend launch will use normal queue scope.",
        }
        checks: list[dict[str, Any]] = [
            _network_role_preflight_check(config),
            _preflight_check(
                "mode",
                "Pipeline mode",
                "ready" if is_supported_pipeline_start_mode(mode) else "blocked",
                f"mode={mode or '(empty)'}",
                "Use one of continuous, once, validate, or drain_pending_pushes.",
                detail=[] if is_supported_pipeline_start_mode(mode) else ["Invalid modes are rejected before schedule or active-work checks.", "Error: mode must be continuous, once, validate, or drain_pending_pushes."],
            ),
            _preflight_check(
                "sleep_seconds",
                "Sleep interval",
                "ready" if sleep_error is None else "blocked",
                f"sleep_seconds={normalized['sleep_seconds']}",
                "Use a whole number of seconds; backend start will clamp valid values to at least one second.",
                detail=[] if sleep_error is None else [PIPELINE_SLEEP_SECONDS_ERROR],
            ),
            _preflight_check(
                "extra_args",
                "Extra arguments",
                "ready" if extra_args_error is None else "blocked",
                f"extra_args_present={bool(extra_args)}; allow_extra_args=False",
                "Keep local API launches on structured fields; extra pipeline arguments are not accepted by the Local API.",
                detail=[] if extra_args_error is None else [PIPELINE_EXTRA_ARGS_ERROR],
            ),
            single_file_check,
        ]
        if is_supported_pipeline_start_mode(mode):
            schedule_gate = self._resolve_pipeline_start_schedule_gate(mode, request)
            normalized["actual_mode"] = str(schedule_gate.get("mode") or mode)
            normalized["schedule"] = schedule_gate.get("data") or {}
            checks.append(
                _preflight_check(
                    "schedule_gate",
                    "Schedule gate",
                    "ready" if bool(schedule_gate.get("ok")) else "blocked",
                    f"ok={bool(schedule_gate.get('ok'))}; actual_mode={normalized['actual_mode']}; override={normalized['schedule_override'] or 'none'}",
                    "Respect the schedule gate or choose an explicit override before start.",
                    detail=[str(schedule_gate.get("message") or "Schedule gate is currently allowing this request."), json_safe(schedule_gate.get("data") or {})],
                )
            )
            checks.append(
                continuous_schedule_stop_watcher_preflight_check(
                    requested_mode=mode,
                    actual_mode=normalized["actual_mode"],
                    request=request,
                    schedule_gate=schedule_gate,
                    backend_watcher_available=self._pipeline_schedule_stop_watcher_available(),
                )
            )
        else:
            normalized["actual_mode"] = mode
        checks.extend(
            [
                self._process_launch_lock_preflight_check("Pipeline preflight"),
                self._config_identity_preflight_check(resolved),
            ]
        )
        path_health = configured_path_health(resolved)
        path_health_check = self._configured_path_health_preflight_check(resolved, path_health=path_health)
        if path_health_check is not None:
            checks.append(path_health_check)
        checks.append(_encoder_capability_report_preflight_check(resolved))
        checks.append(self._autonomy_health_preflight_check(resolved, path_health=path_health))
        checks.extend(
            [
                self._active_work_preflight_check(resolved, "Pipeline preflight"),
                _preflight_check(
                    "service_start",
                    "Pipeline service",
                    "ready" if _service_callable(self.service, "start_pipeline") else "blocked",
                    f"start_pipeline callable={_service_callable(self.service, 'start_pipeline')}",
                    "Backend start requires the existing service pipeline launcher.",
                ),
                _preflight_check(
                    "runtime_prep_boundary",
                    "Runtime prep boundary",
                    "review",
                    "Preflight intentionally does not clear stale progress, remove flags, write launch state, or call runtime prep.",
                    "Start route will perform runtime/control prep immediately before launching.",
                ),
            ]
        )
        return checks, normalized, "/api/pipeline/start"

    def _audit_launch_preflight_checks(
        self,
        resolved: ResolvedPaths,
        request: dict[str, Any],
    ) -> tuple[list[dict[str, Any]], dict[str, Any], str]:
        library_root = resolve_audit_library_root(request, resolved.config_data)
        path = Path(library_root) if library_root else None
        evidence, details = path_evidence(path)
        normalized = {
            "target": "audit",
            "library_root": library_root,
            "include_sidecars": bool(request.get("include_sidecars", False)),
            "show_console": bool(request.get("show_console", False)),
        }
        checks = [
            _preflight_check(
                "library_root",
                "Audit library root",
                "blocked" if not library_root else "ready" if evidence == "exists" else "review",
                f"library_root={library_root or '(empty)'}; path={evidence}",
                "Provide a library root or configured Outsource path before audit start.",
                detail=details if library_root else [AUDIT_LIBRARY_ROOT_ERROR],
            ),
            self._process_launch_lock_preflight_check("Audit preflight"),
            self._config_identity_preflight_check(resolved),
            self._active_work_preflight_check(resolved, "Audit preflight"),
            _preflight_check(
                "service_start",
                "Audit service",
                "ready" if _service_callable(self.service, "start_audit") else "blocked",
                f"start_audit callable={_service_callable(self.service, 'start_audit')}",
                "Backend start requires the existing service audit launcher.",
            ),
            _preflight_check(
                "runtime_prep_boundary",
                "Runtime prep boundary",
                "review",
                "Preflight intentionally does not clear audit progress, write launch state, or call runtime prep.",
                "Start route will perform audit runtime prep immediately before launching.",
            ),
        ]
        return checks, normalized, "/api/audit/start"

    def _rerun_launch_preflight_checks(
        self,
        resolved: ResolvedPaths,
        request: dict[str, Any],
    ) -> tuple[list[dict[str, Any]], dict[str, Any], str]:
        _ = resolved
        csv_path = rerun_csv_path_from_request(request)
        stage_mode, original_mode, return_mode = rerun_modes_from_request(request)
        dry_run = rerun_dry_run_from_request(request)
        plan_only = rerun_plan_only_from_request(request)
        evidence, details = path_evidence(csv_path)
        modes_supported = rerun_modes_are_supported(stage_mode, original_mode, return_mode)
        normalized = {
            "target": "rerun",
            "csv_path": str(csv_path or ""),
            "dry_run": dry_run,
            "plan_only": plan_only,
            "stage_mode": stage_mode,
            "original_mode": original_mode,
            "return_mode": return_mode,
            "show_console": bool(request.get("show_console", False)),
        }
        checks = [
            _preflight_check(
                "csv_path",
                "CSV path",
                "blocked" if csv_path is None else "ready" if evidence == "exists" else "review",
                f"csv_path={csv_path or '(empty)'}; path={evidence}",
                "Provide an existing CSV path exported from audit/rerun tooling before start.",
                detail=details if csv_path is not None else [CSV_RERUN_PATH_ERROR],
            ),
            _preflight_check(
                "safe_modes",
                "CSV rerun safety modes",
                "ready" if modes_supported else "blocked",
                f"stage={stage_mode}; original={original_mode}; return={return_mode}; dry_run={dry_run}; plan_only={plan_only}",
                "WebView rerun start is intentionally limited to copy / keep / park.",
                detail=[] if modes_supported else [CSV_RERUN_MODE_ERROR],
            ),
            self._process_launch_lock_preflight_check("CSV rerun preflight"),
            self._config_identity_preflight_check(resolved),
            self._active_work_preflight_check(resolved, "CSV rerun preflight"),
            _preflight_check(
                "service_start",
                "CSV rerun service",
                "ready" if _service_callable(self.service, "start_rerun_csv") else "blocked",
                f"start_rerun_csv callable={_service_callable(self.service, 'start_rerun_csv')}",
                "Backend start requires the existing service CSV rerun launcher.",
            ),
            _preflight_check(
                "media_safety_policy",
                "Media safety policy",
                "ready",
                "copy to scratch; keep originals; park returned outputs.",
                "Rerun remains backend-owned and should not mutate source files.",
            ),
        ]
        return checks, normalized, "/api/rerun/start"

__all__ = [
    "LAUNCH_PREFLIGHT_SCHEMA_VERSION",
    "LAUNCH_READINESS_SCHEMA_VERSION",
    "LAUNCH_PREFLIGHT_TARGETS",
    "ProcessFacadeMixin",
]
