"""Settings patch preview/save policy."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

from mediapipeline_desktop_app.models import ResolvedPaths

if TYPE_CHECKING:
    from mediapipeline_desktop_app.application.dto_commands import CommandResult


SETTINGS_PREVIEW_PATCH_COMMAND = "settings.preview_patch"
SETTINGS_SAVE_PATCH_COMMAND = "settings.save_patch"
SETTINGS_REFRESH_HINT = "settings"
SETTINGS_DIFF_LINE_LIMIT = 400
SETTINGS_PATCH_CHANGES_ERROR = "Missing changes object."
SETTINGS_PATCH_REMOVE_KEYS_ERROR = "remove_keys must be a JSON array."
SETTINGS_SAVE_BUSY_MESSAGE = "Settings patch save blocked because another settings save command is already in progress."
SETTINGS_SAVE_PROGRESS_SCHEMA_VERSION = "desktop_settings_save_reload_progress.v1"
SETTINGS_SAVE_PROGRESS_STEPS = [
    ("preview", "Preview patch"),
    ("write_backup", "Write backup"),
    ("write_config", "Write config"),
    ("reload", "Reload settings"),
    ("validate", "Validate loaded config"),
]


def _command_result(**fields: Any) -> "CommandResult":
    from mediapipeline_desktop_app.application.dto_commands import CommandResult

    return CommandResult(**fields)


def sorted_patch_keys(keys: list[str]) -> list[str]:
    return sorted(set(keys), key=str.casefold)


def truncated_diff_lines(diff_lines: list[str]) -> list[str]:
    return diff_lines[:SETTINGS_DIFF_LINE_LIMIT]


def settings_diff_truncated(diff_lines: list[str]) -> bool:
    return len(diff_lines) > SETTINGS_DIFF_LINE_LIMIT


def settings_save_progress_step_status_counts(steps: list[dict[str, Any]]) -> tuple[int, int]:
    total = len(steps)
    completed = sum(1 for step in steps if str(step.get("status") or "").lower() in {"complete", "skipped"})
    return completed, total


def settings_save_progress_bar(
    *,
    steps: list[dict[str, Any]],
    status: str,
    detail: str,
    source: str,
    updated_at: str,
) -> dict[str, Any]:
    completed, total = settings_save_progress_step_status_counts(steps)
    percent = 100.0 if total <= 0 else round((completed / total) * 100.0, 1)
    return {
        "id": "settings_save_reload",
        "label": "Settings save/reload",
        "mode": "stepped",
        "percent": percent,
        "status": status,
        "detail": detail,
        "source": source,
        "updated_at": updated_at,
        "stale": False,
        "step_index": completed,
        "step_total": total,
        "completed_steps": [str(step.get("label") or step.get("key") or "") for step in steps if str(step.get("status") or "").lower() in {"complete", "skipped"}],
    }


def settings_save_progress_payload(
    *,
    step_statuses: dict[str, str],
    step_details: dict[str, str] | None = None,
    status: str,
    detail: str,
    source: str,
) -> dict[str, Any]:
    details = step_details or {}
    updated_at = datetime.now().isoformat(timespec="seconds")
    steps = [
        {
            "key": key,
            "label": label,
            "status": step_statuses.get(key, "pending"),
            "detail": details.get(key, ""),
        }
        for key, label in SETTINGS_SAVE_PROGRESS_STEPS
    ]
    bar = settings_save_progress_bar(
        steps=steps,
        status=status,
        detail=detail,
        source=source,
        updated_at=updated_at,
    )
    return {
        "schema_version": SETTINGS_SAVE_PROGRESS_SCHEMA_VERSION,
        "status": status,
        "detail": detail,
        "updated_at": updated_at,
        "steps": steps,
        "progress_bars": [bar],
    }


def settings_patch_preview_progress_payload(patch: dict[str, Any]) -> dict[str, Any]:
    errors = patch["errors"]
    warnings = patch["warnings"]
    changed_keys = sorted_patch_keys(patch["changed_keys"])
    removed_keys = sorted_patch_keys(patch["removed_keys"])
    status = "blocked" if errors else "warning" if warnings else "review"
    detail = (
        f"Previewed {len(changed_keys)} changed key(s) and {len(removed_keys)} removed key(s); "
        "no config write requested."
    )
    return settings_save_progress_payload(
        step_statuses={
            "preview": "blocked" if errors else "complete",
            "write_backup": "pending",
            "write_config": "pending",
            "reload": "pending",
            "validate": "pending",
        },
        step_details={
            "preview": "Backend patch candidate and redacted diff were built without writing config.",
            "write_backup": "Save Patch has not been confirmed.",
            "write_config": "Save Patch has not been confirmed.",
            "reload": "No reload is needed until a save succeeds.",
            "validate": "Loaded config validation waits for save/reload.",
        },
        status=status,
        detail=detail,
        source=SETTINGS_PREVIEW_PATCH_COMMAND,
    )


def settings_save_written_progress_payload(result: object, patch: dict[str, Any]) -> dict[str, Any]:
    backup_path = getattr(result, "backup_path", None)
    changed_keys = sorted_patch_keys(patch["changed_keys"])
    removed_keys = sorted_patch_keys(patch["removed_keys"])
    backup_status = "complete" if backup_path else "skipped"
    return settings_save_progress_payload(
        step_statuses={
            "preview": "complete",
            "write_backup": backup_status,
            "write_config": "complete",
            "reload": "pending",
            "validate": "pending",
        },
        step_details={
            "preview": f"Patch candidate validated with {len(changed_keys)} changed key(s) and {len(removed_keys)} removed key(s).",
            "write_backup": f"Backup written to {backup_path}." if backup_path else "No prior config backup was created by the save service.",
            "write_config": f"Config document written to {getattr(result, 'output_path', '')}.",
            "reload": "Local API reload has not reported yet.",
            "validate": "Reloaded config validation waits for Local API reload.",
        },
        status="active",
        detail="Settings patch was written; waiting for backend reload/validation evidence.",
        source=SETTINGS_SAVE_PATCH_COMMAND,
    )


def settings_patch_severity(errors: list[str], warnings: list[str]) -> str:
    return "error" if errors else "warning" if warnings else "info"


def settings_patch_missing_changes_result(command: str) -> CommandResult:
    return _command_result(
        command=command,
        ok=False,
        message="Settings patch requires a JSON object named changes.",
        severity="error",
        errors=[SETTINGS_PATCH_CHANGES_ERROR],
        refresh_hint=SETTINGS_REFRESH_HINT,
    )


def settings_patch_remove_keys_type_error_result(command: str) -> CommandResult:
    return _command_result(
        command=command,
        ok=False,
        message="remove_keys must be a JSON array when supplied.",
        severity="error",
        errors=[SETTINGS_PATCH_REMOVE_KEYS_ERROR],
        refresh_hint=SETTINGS_REFRESH_HINT,
    )


def settings_patch_changes_from_request(
    request: dict[str, Any],
    *,
    command: str,
) -> tuple[dict[str, Any] | None, CommandResult | None]:
    raw_changes = request.get("changes")
    if not isinstance(raw_changes, dict):
        return None, settings_patch_missing_changes_result(command)
    return raw_changes, None


def settings_patch_remove_keys_from_request(
    request: dict[str, Any],
    *,
    command: str,
) -> tuple[list[Any] | None, CommandResult | None]:
    raw_remove_keys = request.get("remove_keys", [])
    if raw_remove_keys in (None, ""):
        raw_remove_keys = []
    if not isinstance(raw_remove_keys, list):
        return None, settings_patch_remove_keys_type_error_result(command)
    return raw_remove_keys, None


def settings_patch_preview_message(
    errors: list[str],
    changed_keys: list[str],
    removed_keys: list[str],
    diff_lines: list[str],
) -> str:
    if errors:
        return f"Settings patch preview failed with {len(errors)} error(s)."
    if changed_keys or removed_keys:
        return f"Settings patch preview produced {len(diff_lines)} redacted diff line(s)."
    return "Settings patch preview has no changes."


def settings_patch_preview_result(resolved: ResolvedPaths, patch: dict[str, Any]) -> CommandResult:
    errors = patch["errors"]
    warnings = patch["warnings"]
    changed_keys = patch["changed_keys"]
    removed_keys = patch["removed_keys"]
    diff_lines = patch["diff_lines"]
    progress = settings_patch_preview_progress_payload(patch)
    return _command_result(
        command=SETTINGS_PREVIEW_PATCH_COMMAND,
        ok=not errors,
        message=settings_patch_preview_message(errors, changed_keys, removed_keys, diff_lines),
        severity=settings_patch_severity(errors, warnings),
        warnings=warnings,
        errors=errors,
        refresh_hint=SETTINGS_REFRESH_HINT,
        data={
            "config_path": str(resolved.config_path),
            "changed_keys": sorted_patch_keys(changed_keys),
            "removed_keys": sorted_patch_keys(removed_keys),
            "base_key_count": len(patch["base_config"]),
            "preview_key_count": len(patch["merged"]),
            "redacted_diff_lines": truncated_diff_lines(diff_lines),
            "diff_truncated": settings_diff_truncated(diff_lines),
            "risk_summary": patch["risk_summary"],
            "library_profile_state": patch.get("library_profile_state", []),
            "writes_config": False,
            "settings_progress": progress,
            "progress_bars": progress["progress_bars"],
        },
    )


def settings_save_confirmation_required_result() -> CommandResult:
    return _command_result(
        command=SETTINGS_SAVE_PATCH_COMMAND,
        ok=False,
        message="Settings patch save requires explicit confirmation.",
        severity="warning",
        warnings=["confirm_save must be true."],
        refresh_hint=SETTINGS_REFRESH_HINT,
    )


def settings_save_busy_result(message: str = SETTINGS_SAVE_BUSY_MESSAGE) -> CommandResult:
    return _command_result(
        command=SETTINGS_SAVE_PATCH_COMMAND,
        ok=False,
        message=message,
        severity="warning",
        warnings=[message],
        refresh_hint=SETTINGS_REFRESH_HINT,
    )


def settings_save_validation_error_result(errors: list[str], warnings: list[str]) -> CommandResult:
    return _command_result(
        command=SETTINGS_SAVE_PATCH_COMMAND,
        ok=False,
        message=f"Settings patch save failed validation with {len(errors)} error(s).",
        severity="error",
        errors=errors,
        warnings=warnings,
        refresh_hint=SETTINGS_REFRESH_HINT,
    )


def settings_save_no_changes_result(warnings: list[str]) -> CommandResult:
    return _command_result(
        command=SETTINGS_SAVE_PATCH_COMMAND,
        ok=False,
        message="Settings patch save has no changes to write.",
        severity="warning",
        warnings=warnings or ["No settings changes were proposed."],
        refresh_hint=SETTINGS_REFRESH_HINT,
    )


def settings_save_service_unavailable_result() -> CommandResult:
    return _command_result(
        command=SETTINGS_SAVE_PATCH_COMMAND,
        ok=False,
        message="Settings save service is not available.",
        severity="error",
        errors=["serialize_psd1_document and save_config_document are required."],
        refresh_hint=SETTINGS_REFRESH_HINT,
    )


def settings_save_config_blocked_result(message: str, data: dict[str, Any]) -> CommandResult:
    return _command_result(
        command=SETTINGS_SAVE_PATCH_COMMAND,
        ok=False,
        message=message,
        severity="error",
        errors=[message],
        refresh_hint=SETTINGS_REFRESH_HINT,
        data=data,
    )


def settings_save_exception_result(exc: Exception, warnings: list[str]) -> CommandResult:
    return _command_result(
        command=SETTINGS_SAVE_PATCH_COMMAND,
        ok=False,
        message=f"Settings patch save failed: {exc}",
        severity="error",
        errors=[str(exc)],
        warnings=warnings,
        refresh_hint=SETTINGS_REFRESH_HINT,
    )


def settings_save_success_result(result: object, patch: dict[str, Any], warnings: list[str]) -> CommandResult:
    output_path = Path(getattr(result, "output_path"))
    backup_path = getattr(result, "backup_path", None)
    diff_lines = patch["diff_lines"]
    progress = settings_save_written_progress_payload(result, patch)
    return _command_result(
        command=SETTINGS_SAVE_PATCH_COMMAND,
        ok=True,
        message=f"Settings saved to {output_path.name}.",
        severity="info",
        warnings=warnings,
        refresh_hint=SETTINGS_REFRESH_HINT,
        data={
            "config_path": str(output_path),
            "backup_path": str(backup_path or ""),
            "changed_keys": sorted_patch_keys(patch["changed_keys"]),
            "removed_keys": sorted_patch_keys(patch["removed_keys"]),
            "key_count": len(patch["merged"]),
            "redacted_diff_lines": truncated_diff_lines(diff_lines),
            "diff_truncated": settings_diff_truncated(diff_lines),
            "risk_summary": patch["risk_summary"],
            "library_profile_state": patch.get("library_profile_state", []),
            "writes_config": True,
            "settings_progress": progress,
            "progress_bars": progress["progress_bars"],
        },
    )

__all__ = [
    "SETTINGS_PREVIEW_PATCH_COMMAND",
    "SETTINGS_SAVE_PATCH_COMMAND",
    "SETTINGS_REFRESH_HINT",
    "SETTINGS_DIFF_LINE_LIMIT",
    "SETTINGS_PATCH_CHANGES_ERROR",
    "SETTINGS_PATCH_REMOVE_KEYS_ERROR",
    "SETTINGS_SAVE_BUSY_MESSAGE",
    "SETTINGS_SAVE_PROGRESS_SCHEMA_VERSION",
    "SETTINGS_SAVE_PROGRESS_STEPS",
    "sorted_patch_keys",
    "truncated_diff_lines",
    "settings_diff_truncated",
    "settings_save_progress_step_status_counts",
    "settings_save_progress_bar",
    "settings_save_progress_payload",
    "settings_patch_preview_progress_payload",
    "settings_save_written_progress_payload",
    "settings_patch_severity",
    "settings_patch_missing_changes_result",
    "settings_patch_remove_keys_type_error_result",
    "settings_patch_changes_from_request",
    "settings_patch_remove_keys_from_request",
    "settings_patch_preview_message",
    "settings_patch_preview_result",
    "settings_save_confirmation_required_result",
    "settings_save_busy_result",
    "settings_save_validation_error_result",
    "settings_save_no_changes_result",
    "settings_save_service_unavailable_result",
    "settings_save_config_blocked_result",
    "settings_save_exception_result",
    "settings_save_success_result",
]
