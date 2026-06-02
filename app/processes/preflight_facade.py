"""Read-only process launch preflight facade adapter."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from mediapipeline_desktop_app.application.dto_base import JsonMap, json_safe
from mediapipeline_desktop_app.models import ResolvedPaths

from app.processes.audit_policy import AUDIT_LIBRARY_ROOT_ERROR, resolve_audit_library_root
from app.processes.pipeline_policy import (
    PIPELINE_EXTRA_ARGS_ERROR,
    PIPELINE_SLEEP_SECONDS_ERROR,
    is_supported_pipeline_start_mode,
    normalize_pipeline_extra_args,
    normalize_pipeline_start_mode,
    parse_pipeline_sleep_seconds,
    pipeline_extra_args_error,
)
from app.processes.rerun_policy import (
    CSV_RERUN_MODE_ERROR,
    CSV_RERUN_PATH_ERROR,
    rerun_csv_path_from_request,
    rerun_modes_are_supported,
    rerun_modes_from_request,
)
from app.processes.schedule_policy import continuous_schedule_stop_watcher_preflight_check


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
    detail: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "key": key,
        "label": label,
        "status": status,
        "evidence": evidence,
        "action": action,
        "detail": detail or [],
    }


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
            }
            for check in non_ready
        ],
        "final_authority": final_authority,
    }


def _path_evidence(path: Path | None) -> tuple[str, list[str]]:
    if path is None:
        return "missing", []
    details = [f"path={path}"]
    try:
        if path.exists():
            details.append("exists=yes")
            return "exists", details
        details.append("exists=no")
        return "missing on disk", details
    except OSError as exc:
        details.append(f"exists check failed={exc}")
        return "existence unknown", details


def _service_callable(service: object, name: str) -> bool:
    return callable(getattr(service, name, None))


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

    def _pipeline_launch_preflight_checks(
        self,
        resolved: ResolvedPaths,
        request: dict[str, Any],
    ) -> tuple[list[dict[str, Any]], dict[str, Any], str]:
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
        }
        checks: list[dict[str, Any]] = [
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
        evidence, details = _path_evidence(path)
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
        evidence, details = _path_evidence(csv_path)
        modes_supported = rerun_modes_are_supported(stage_mode, original_mode, return_mode)
        normalized = {
            "target": "rerun",
            "csv_path": str(csv_path or ""),
            "dry_run": bool(request.get("dry_run", False)),
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
                f"stage={stage_mode}; original={original_mode}; return={return_mode}; dry_run={bool(request.get('dry_run', False))}",
                "V6 WebView rerun start is intentionally limited to copy / keep / park.",
                detail=[] if modes_supported else [CSV_RERUN_MODE_ERROR],
            ),
            self._process_launch_lock_preflight_check("CSV rerun preflight"),
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
