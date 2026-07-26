from __future__ import annotations

import hmac
from collections.abc import Mapping
from datetime import datetime
from typing import Any

from mediapipeline.core.kernel.dto_commands import CommandResult


RESOLVED_PIPELINE_PATHS_UNAVAILABLE_MESSAGE = "Resolved pipeline paths are unavailable."
BACKEND_SHUTDOWN_UNAVAILABLE_MESSAGE = "Backend shutdown is not available for this server instance."
BACKEND_SHUTDOWN_BLOCKED_MESSAGE = "Backend shutdown blocked because active work may still be running."
BACKEND_SHUTDOWN_SCHEDULING_FAILED_MESSAGE = "Backend shutdown could not be scheduled; the backend remains available."
CLOSE_READINESS_UNAVAILABLE_REASON = "Close readiness is unknown because resolved paths are unavailable."
CLOSE_READINESS_UNAVAILABLE_WARNING = "Resolved paths were unavailable while evaluating close readiness."
SETTINGS_RELOAD_UNAVAILABLE_MESSAGE = "Settings reload is not available for this server instance."
SETTINGS_RELOAD_MISSING_RESOLVED_MESSAGE = "Settings reload did not return resolved paths."
SETTINGS_RELOAD_PROGRESS_SCHEMA_VERSION = "desktop_settings_reload_progress.v1"


def bounded_error_text(value: object, *, limit: int = 2000) -> str:
    text = str(value or "")
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 3)] + "..."


def command_result_payload(
    *,
    command: str,
    ok: bool,
    message: str,
    severity: str,
    errors: list[str] | None = None,
    warnings: list[str] | None = None,
    refresh_hint: str | None = None,
    data: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return CommandResult(
        command=command,
        ok=ok,
        message=message,
        severity=severity,
        errors=list(errors or []),
        warnings=list(warnings or []),
        refresh_hint=refresh_hint or "",
        data=dict(data or {}),
    ).to_mapping()


def resolved_paths_unavailable_payload(command: str, refresh_hint: str) -> dict[str, Any]:
    return command_result_payload(
        command=command,
        ok=False,
        message=RESOLVED_PIPELINE_PATHS_UNAVAILABLE_MESSAGE,
        severity="error",
        errors=[RESOLVED_PIPELINE_PATHS_UNAVAILABLE_MESSAGE],
        refresh_hint=refresh_hint,
    )


def close_readiness_unavailable_payload() -> dict[str, Any]:
    return {
        "schema_version": "desktop_close_readiness.v1",
        "safe_to_close": False,
        "state": "unknown",
        "active_work": True,
        "reason": CLOSE_READINESS_UNAVAILABLE_REASON,
        "warnings": [CLOSE_READINESS_UNAVAILABLE_WARNING],
    }


def settings_progress_bar_from_steps(
    *,
    bar_id: str,
    label: str,
    steps: list[dict[str, Any]],
    status: str,
    detail: str,
    source: str,
    updated_at: str,
) -> dict[str, Any]:
    total = len(steps)
    completed = sum(1 for step in steps if str(step.get("status") or "").lower() in {"complete", "skipped"})
    percent = 100.0 if total <= 0 else round((completed / total) * 100.0, 1)
    return {
        "id": bar_id,
        "label": label,
        "mode": "stepped",
        "percent": percent,
        "status": status,
        "detail": detail,
        "source": source,
        "updated_at": updated_at,
        "stale": False,
        "step_index": completed,
        "step_total": total,
        "completed_steps": [
            str(step.get("label") or step.get("key") or "")
            for step in steps
            if str(step.get("status") or "").lower() in {"complete", "skipped"}
        ],
    }


def settings_reload_progress_payload(
    *,
    ok: bool,
    key_count: int = 0,
    detail: str = "",
    source: str = "settings.reload",
) -> dict[str, Any]:
    status = "complete" if ok else "blocked"
    updated_at = datetime.now().isoformat(timespec="seconds")
    steps = [
        {
            "key": "reload",
            "label": "Reload settings",
            "status": "complete" if ok else "blocked",
            "detail": f"Reloaded {key_count} key(s)." if ok else detail,
        },
        {
            "key": "validate",
            "label": "Validate loaded config",
            "status": "complete" if ok else "blocked",
            "detail": "Resolved settings are available after reload." if ok else "Validation did not run because reload failed.",
        },
    ]
    progress_detail = detail or (f"Settings reloaded and validated with {key_count} key(s)." if ok else "Settings reload failed.")
    bar = settings_progress_bar_from_steps(
        bar_id="settings_reload",
        label="Settings reload",
        steps=steps,
        status=status,
        detail=progress_detail,
        source=source,
        updated_at=updated_at,
    )
    return {
        "schema_version": SETTINGS_RELOAD_PROGRESS_SCHEMA_VERSION,
        "status": status,
        "detail": progress_detail,
        "updated_at": updated_at,
        "steps": steps,
        "progress_bars": [bar],
    }


def settings_save_progress_with_reload(
    progress: Mapping[str, Any] | None,
    *,
    ok: bool,
    key_count: int = 0,
    detail: str = "",
) -> dict[str, Any] | None:
    if not isinstance(progress, Mapping):
        return None
    steps = [dict(step) for step in progress.get("steps") or [] if isinstance(step, Mapping)]
    if not steps:
        return dict(progress)
    for step in steps:
        key = str(step.get("key") or "")
        if key == "reload":
            step["status"] = "complete" if ok else "blocked"
            step["detail"] = f"Reloaded {key_count} key(s)." if ok else detail
        elif key == "validate":
            step["status"] = "complete" if ok else "blocked"
            step["detail"] = "Reloaded settings were validated by resolved-path construction." if ok else "Validation did not complete because reload failed."
    status = "complete" if ok else "blocked"
    progress_detail = detail or (f"Settings save/reload completed with {key_count} reloaded key(s)." if ok else "Settings save completed but reload failed.")
    updated_at = datetime.now().isoformat(timespec="seconds")
    updated = dict(progress)
    updated.update(
        {
            "status": status,
            "detail": progress_detail,
            "updated_at": updated_at,
            "steps": steps,
        }
    )
    updated["progress_bars"] = [
        settings_progress_bar_from_steps(
            bar_id="settings_save_reload",
            label="Settings save/reload",
            steps=steps,
            status=status,
            detail=progress_detail,
            source="settings.save_patch",
            updated_at=updated_at,
        )
    ]
    return updated


def backend_shutdown_unavailable_payload() -> dict[str, Any]:
    return command_result_payload(
        command="backend.shutdown",
        ok=False,
        message=BACKEND_SHUTDOWN_UNAVAILABLE_MESSAGE,
        severity="error",
        errors=[BACKEND_SHUTDOWN_UNAVAILABLE_MESSAGE],
        refresh_hint="none",
    )


def backend_shutdown_readiness_data(readiness: Mapping[str, Any] | None = None) -> dict[str, Any]:
    readiness_data = dict(readiness or {})
    reason = str(readiness_data.get("reason") or "Active work may still be running.")
    return {
        "safe_to_close": False,
        "state": str(readiness_data.get("state") or ""),
        "active_work": bool(readiness_data.get("active_work", True)),
        "reason": reason,
        "continuous_watcher": dict(readiness_data.get("continuous_watcher") or {}),
    }


def backend_shutdown_success_payload(
    readiness: Mapping[str, Any] | None = None,
    *,
    force_active_work_shutdown: bool = False,
    cleanup_messages: list[str] | None = None,
    post_cleanup_readiness: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    readiness_data = dict(readiness or {})
    cleanup = [str(item) for item in cleanup_messages or [] if str(item).strip()]
    safe_to_close = bool(readiness_data.get("safe_to_close", True))
    if not safe_to_close:
        data = backend_shutdown_readiness_data(readiness_data)
        reason = data["reason"]
        if not force_active_work_shutdown:
            return command_result_payload(
                command="backend.shutdown",
                ok=False,
                message=BACKEND_SHUTDOWN_BLOCKED_MESSAGE,
                severity="error",
                errors=[reason],
                refresh_hint="close-readiness",
                data=data,
            )
        if force_active_work_shutdown:
            data["forced_active_work_shutdown"] = True
            data["cleanup_messages"] = cleanup
            data["cleanup_verified"] = True
            data["shutdown_scheduled"] = True
            if post_cleanup_readiness is not None:
                data["post_cleanup_readiness"] = dict(post_cleanup_readiness)
        return command_result_payload(
            command="backend.shutdown",
            ok=True,
            message="Backend shutdown requested with forced active-work cleanup.",
            severity="warning",
            warnings=[reason, *cleanup],
            refresh_hint="shutdown",
            data=data,
        )
    return command_result_payload(
        command="backend.shutdown",
        ok=True,
        message="Backend shutdown requested.",
        severity="info",
        refresh_hint="shutdown",
        data={"shutdown_scheduled": True},
    )


def backend_shutdown_scheduling_failure_payload(
    readiness: Mapping[str, Any] | None,
    *,
    scheduling_error: object,
    force_active_work_shutdown: bool = False,
    cleanup_messages: list[str] | None = None,
    post_cleanup_readiness: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    error_detail = bounded_error_text(scheduling_error, limit=500)
    data: dict[str, Any] = {
        "shutdown_scheduled": False,
        "backend_ownership_retained": True,
        "shutdown_retry_allowed": True,
        "close_readiness": dict(readiness or {}),
    }
    cleanup = [bounded_error_text(item) for item in cleanup_messages or [] if str(item).strip()]
    if force_active_work_shutdown:
        data.update(
            {
                "forced_active_work_shutdown": True,
                "cleanup_messages": cleanup,
                "cleanup_verified": True,
            }
        )
        if post_cleanup_readiness is not None:
            data["post_cleanup_readiness"] = dict(post_cleanup_readiness)
    error = BACKEND_SHUTDOWN_SCHEDULING_FAILED_MESSAGE
    if error_detail:
        error = f"{error} Scheduling error: {error_detail}"
    return command_result_payload(
        command="backend.shutdown",
        ok=False,
        message=BACKEND_SHUTDOWN_SCHEDULING_FAILED_MESSAGE,
        severity="error",
        errors=[error],
        warnings=cleanup,
        refresh_hint="close-readiness",
        data=data,
    )


def backend_shutdown_cleanup_failure_payload(
    readiness: Mapping[str, Any] | None,
    *,
    cleanup_messages: list[str] | None = None,
    cleanup_errors: list[str] | None = None,
    post_cleanup_readiness: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    data = backend_shutdown_readiness_data(readiness)
    messages = [bounded_error_text(item) for item in cleanup_messages or [] if str(item).strip()]
    errors = [bounded_error_text(item) for item in cleanup_errors or [] if str(item).strip()]
    data.update(
        {
            "forced_active_work_shutdown": True,
            "cleanup_messages": messages,
            "cleanup_verified": False,
            "cleanup_uncertain": True,
            "reconciliation_required": True,
        }
    )
    if post_cleanup_readiness is not None:
        post_cleanup = dict(post_cleanup_readiness)
        data["post_cleanup_readiness"] = post_cleanup
        post_reason = str(post_cleanup.get("reason") or "").strip()
        if post_reason and post_reason not in errors:
            errors.insert(0, bounded_error_text(post_reason))
    if not errors:
        errors.append("Forced active-work cleanup did not produce verified safe close-readiness evidence.")
    return command_result_payload(
        command="backend.shutdown",
        ok=False,
        message="Backend shutdown blocked because forced active-work cleanup was not verified.",
        severity="error",
        errors=errors,
        warnings=messages,
        refresh_hint="close-readiness",
        data=data,
    )


def settings_reload_unavailable_payload() -> dict[str, Any]:
    progress = settings_reload_progress_payload(ok=False, detail=SETTINGS_RELOAD_UNAVAILABLE_MESSAGE)
    return command_result_payload(
        command="settings.reload",
        ok=False,
        message=SETTINGS_RELOAD_UNAVAILABLE_MESSAGE,
        severity="error",
        errors=[SETTINGS_RELOAD_UNAVAILABLE_MESSAGE],
        refresh_hint="settings",
        data={
            "settings_progress": progress,
            "progress_bars": progress["progress_bars"],
        },
    )


def settings_reload_exception_payload(exc: Exception) -> dict[str, Any]:
    error = bounded_error_text(exc)
    progress = settings_reload_progress_payload(ok=False, detail=error)
    return command_result_payload(
        command="settings.reload",
        ok=False,
        message=f"Settings reload failed: {error}",
        severity="error",
        errors=[error],
        refresh_hint="settings",
        data={
            "settings_progress": progress,
            "progress_bars": progress["progress_bars"],
        },
    )


def settings_reload_missing_resolved_payload() -> dict[str, Any]:
    progress = settings_reload_progress_payload(ok=False, detail=SETTINGS_RELOAD_MISSING_RESOLVED_MESSAGE)
    return command_result_payload(
        command="settings.reload",
        ok=False,
        message=SETTINGS_RELOAD_MISSING_RESOLVED_MESSAGE,
        severity="error",
        errors=[SETTINGS_RELOAD_MISSING_RESOLVED_MESSAGE],
        refresh_hint="settings",
        data={
            "settings_progress": progress,
            "progress_bars": progress["progress_bars"],
        },
    )


def settings_reload_success_payload(resolved: Any) -> dict[str, Any]:
    key_count = len(resolved.config_data or {})
    progress = settings_reload_progress_payload(ok=True, key_count=key_count)
    return command_result_payload(
        command="settings.reload",
        ok=True,
        message="Settings reloaded from disk.",
        severity="info",
        refresh_hint="settings",
        data={
            "config_path": str(resolved.config_path),
            "key_count": key_count,
            "local_base": str(resolved.local_base or ""),
            "settings_progress": progress,
            "progress_bars": progress["progress_bars"],
        },
    )


def settings_save_reload_success_payload(payload: dict[str, Any], reloaded: Any) -> dict[str, Any]:
    updated = dict(payload)
    data = dict(updated.get("data") or {})
    data["reloaded"] = reloaded is not None
    reloaded_key_count = 0
    verified_from_reload = False
    verified_at = datetime.now().isoformat(timespec="seconds")
    if reloaded is not None:
        from mediapipeline.core.config.settings_patch_policy import (
            settings_config_digest,
            settings_reload_verification_digest,
        )

        reloaded_key_count = len(reloaded.config_data or {})
        data["reloaded_key_count"] = reloaded_key_count
        reload_digest = settings_config_digest(reloaded.config_data or {})
        changed_keys = [str(item) for item in list(data.get("changed_keys") or [])]
        removed_keys = [str(item) for item in list(data.get("removed_keys") or [])]
        reload_verification_digest = settings_reload_verification_digest(
            dict(reloaded.config_data or {}),
            changed_keys,
            removed_keys,
        )
        expected_digest = str(
            data.get("reload_verification_digest_written")
            or dict(data.get("save_verification") or {}).get("reload_verification_digest_written")
            or ""
        )
        verified_from_reload = bool(expected_digest) and hmac.compare_digest(expected_digest, reload_verification_digest)
        data["reload_config_digest"] = reload_digest
        data["reload_verification_digest"] = reload_verification_digest
        data["reload_config_verified"] = verified_from_reload
        verification = dict(data.get("save_verification") or {})
        verification.update(
            {
                "reload_config_digest": reload_digest,
                "reload_verification_digest": reload_verification_digest,
                "verified_from_reload": verified_from_reload,
                "verified_at": verified_at,
            }
        )
        data["save_verification"] = verification
        if expected_digest and not verified_from_reload:
            warnings = list(updated.get("warnings") or [])
            warning = "Settings reload verification digest did not match the written changed-key candidate; reload evidence needs review."
            if warning not in warnings:
                warnings.append(warning)
            updated["warnings"] = warnings
            if str(updated.get("severity") or "") == "info":
                updated["severity"] = "warning"
    progress = settings_save_progress_with_reload(
        data.get("settings_progress") if isinstance(data.get("settings_progress"), Mapping) else None,
        ok=reloaded is not None,
        key_count=reloaded_key_count,
    )
    if progress is not None:
        data["settings_progress"] = progress
        data["progress_bars"] = progress["progress_bars"]
    updated["data"] = data
    return updated


def settings_save_reload_failure_payload(payload: dict[str, Any], exc: Exception) -> dict[str, Any]:
    updated = dict(payload)
    data = dict(updated.get("data") or {})
    error = bounded_error_text(exc)
    updated["ok"] = False
    updated["severity"] = "warning"
    updated["message"] = f"Settings saved, but backend reload failed: {error}"
    updated["errors"] = [error]
    data["reloaded"] = False
    verification = dict(data.get("save_verification") or {})
    verification.update(
        {
            "reload_config_digest": "",
            "verified_from_reload": False,
            "verified_at": datetime.now().isoformat(timespec="seconds"),
        }
    )
    data["save_verification"] = verification
    progress = settings_save_progress_with_reload(
        data.get("settings_progress") if isinstance(data.get("settings_progress"), Mapping) else None,
        ok=False,
        detail=error,
    )
    if progress is not None:
        data["settings_progress"] = progress
        data["progress_bars"] = progress["progress_bars"]
    updated["data"] = data
    return updated
