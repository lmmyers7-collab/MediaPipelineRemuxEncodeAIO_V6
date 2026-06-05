"""Settings workspace and validation policy."""

from __future__ import annotations

from pathlib import Path
import shutil
from typing import TYPE_CHECKING, Any

from mediapipeline.desktop.config_keys import (
    KEY_ALLOW_SYSTEM_TOOLS,
    KEY_BDPGS_OCR_TESSDATA_PATH,
    KEY_BDPGS_OCR_TOOL_PATH,
    KEY_CONVERT_BDPGS_TO_SRT,
    KEY_CONVERT_VOBSUB_TO_SRT,
    KEY_OUTSOURCE,
    KEY_VOBSUB_OCR_TOOL_PATH,
)
from mediapipeline.desktop.models import ResolvedPaths

if TYPE_CHECKING:
    from mediapipeline.desktop.application.dto_commands import CommandResult


SETTINGS_VALIDATE_COMMAND = "settings.validate"
VOBSUB_TESSERACT_BUNDLED_CANDIDATES = (
    Path("Tools") / "SubtitleEditLegacy" / "Tesseract550" / "tesseract.exe",
    Path("Tools") / "SubtitleEditLegacy" / "Tesseract-OCR" / "tesseract.exe",
    Path("Tools") / "SubtitleEditLegacy" / "Tesseract" / "tesseract.exe",
    Path("Tools") / "SubtitleEdit" / "Tesseract550" / "tesseract.exe",
    Path("Tools") / "SubtitleEdit" / "Tesseract-OCR" / "tesseract.exe",
    Path("Tools") / "SubtitleEdit" / "Tesseract" / "tesseract.exe",
    Path("Tools") / "Tesseract-OCR" / "tesseract.exe",
    Path("Tools") / "Tesseract" / "tesseract.exe",
)


def _command_result(**fields: Any) -> "CommandResult":
    from mediapipeline.desktop.application.dto_commands import CommandResult

    return CommandResult(**fields)


def settings_path_text(path: object) -> str:
    return str(path) if path else ""


def settings_config_path_value(config: dict[str, Any], key: str) -> Path | None:
    raw = str(config.get(key) or "").strip()
    return Path(raw) if raw else None


def settings_workspace_paths(resolved: ResolvedPaths, config: dict[str, Any]) -> dict[str, str]:
    paths = {
        "app_root": settings_path_text(resolved.app_root),
        "workspace_root": settings_path_text(resolved.workspace_root),
        "config_path": settings_path_text(resolved.config_path),
        "local_base": settings_path_text(resolved.local_base),
        "state_root": settings_path_text(resolved.state_root),
        "source_movies": settings_path_text(resolved.source_movies),
        "source_tv": settings_path_text(resolved.source_tv),
        "outsource": settings_path_text(settings_config_path_value(config, KEY_OUTSOURCE)),
        "pending_push": settings_path_text(resolved.pending_push_path),
        "queue_snapshot": settings_path_text(resolved.queue_snapshot_path),
        "active_jobs": settings_path_text(resolved.active_jobs_path),
        "failed_reports": settings_path_text(resolved.failed_reports_path),
        "failed_markers": settings_path_text(resolved.failed_markers_path),
        "audit_reports": settings_path_text(resolved.audit_reports_path),
        "completed_manifest": settings_path_text(resolved.completed_manifest_path),
    }
    return {key: value for key, value in paths.items() if value}


def settings_bool(config: dict[str, Any], key: str, default: bool = False) -> bool:
    value = config.get(key)
    if isinstance(value, bool):
        return value
    text = str(value or "").strip().casefold()
    if text in {"true", "1", "yes", "y", "on"}:
        return True
    if text in {"false", "0", "no", "n", "off"}:
        return False
    return default


def settings_pipeline_base(resolved: ResolvedPaths) -> Path:
    try:
        if resolved.pipeline_path:
            return Path(resolved.pipeline_path).parent
    except (TypeError, ValueError):
        pass
    return Path(resolved.workspace_root)


def settings_resolve_configured_path(resolved: ResolvedPaths, raw_value: object, *, allow_command_lookup: bool = False) -> tuple[str, str, bool]:
    raw = str(raw_value or "").strip()
    if not raw:
        return "", "", False
    raw_path = Path(raw)
    if raw_path.is_absolute():
        candidate = raw_path
    else:
        candidate = settings_pipeline_base(resolved) / raw_path
    if candidate.exists():
        try:
            return raw, str(candidate.resolve()), False
        except OSError:
            return raw, str(candidate), False
    if allow_command_lookup:
        found = shutil.which(raw)
        if found:
            return raw, found, True
    try:
        return raw, str(candidate.resolve(strict=False)), False
    except OSError:
        return raw, str(candidate), False


def settings_resolve_vobsub_tesseract_path(resolved: ResolvedPaths, *, allow_command_lookup: bool = False) -> tuple[str, str, bool]:
    pipeline_base = settings_pipeline_base(resolved)
    for relative in VOBSUB_TESSERACT_BUNDLED_CANDIDATES:
        candidate = pipeline_base / relative
        if candidate.is_file():
            try:
                return str(relative), str(candidate.resolve()), False
            except OSError:
                return str(relative), str(candidate), False
    if allow_command_lookup:
        found = shutil.which("tesseract")
        if found:
            return "PATH", found, True
    first = pipeline_base / VOBSUB_TESSERACT_BUNDLED_CANDIDATES[0]
    try:
        return str(VOBSUB_TESSERACT_BUNDLED_CANDIDATES[0]), str(first.resolve(strict=False)), False
    except OSError:
        return str(VOBSUB_TESSERACT_BUNDLED_CANDIDATES[0]), str(first), False


def settings_path_evidence_row(
    *,
    key: str,
    label: str,
    raw_value: object,
    resolved_path: str,
    command_lookup: bool,
    required_kind: str,
    required_when_enabled: bool,
) -> dict[str, Any]:
    configured = str(raw_value or "").strip()
    if not configured:
        status = "blocked" if required_when_enabled else "inactive"
        message = f"{key} is not configured."
        exists = False
        path_type = "not_configured"
    else:
        path = Path(resolved_path) if resolved_path else None
        is_file = bool(path and path.is_file())
        is_dir = bool(path and path.is_dir())
        exists = bool(is_file or is_dir or command_lookup)
        path_type = "command" if command_lookup else "file" if is_file else "directory" if is_dir else "missing"
        matches_kind = (required_kind == "file" and (is_file or command_lookup)) or (required_kind == "directory" and is_dir)
        status = "ready" if matches_kind else "blocked" if required_when_enabled else "review"
        if matches_kind:
            message = f"{label} is accessible."
        elif exists:
            message = f"{label} resolved, but expected a {required_kind}."
        else:
            message = f"{label} was not found at the resolved path."
    return {
        "key": key,
        "label": label,
        "configured": configured,
        "resolved": resolved_path,
        "exists": exists,
        "path_type": path_type,
        "required_kind": required_kind,
        "status": status,
        "message": message,
        "command_lookup": command_lookup,
    }


def settings_bdpgs_ocr_path_evidence(resolved: ResolvedPaths, config: dict[str, Any]) -> dict[str, Any]:
    enabled = settings_bool(config, KEY_CONVERT_BDPGS_TO_SRT, True)
    allow_system_tools = settings_bool(config, KEY_ALLOW_SYSTEM_TOOLS, False)
    tool_configured, tool_resolved, tool_from_path = settings_resolve_configured_path(
        resolved,
        config.get(KEY_BDPGS_OCR_TOOL_PATH),
        allow_command_lookup=allow_system_tools,
    )
    tess_configured, tess_resolved, _ = settings_resolve_configured_path(
        resolved,
        config.get(KEY_BDPGS_OCR_TESSDATA_PATH),
        allow_command_lookup=False,
    )
    tool_row = settings_path_evidence_row(
        key=KEY_BDPGS_OCR_TOOL_PATH,
        label="BDPGS OCR tool",
        raw_value=tool_configured,
        resolved_path=tool_resolved,
        command_lookup=tool_from_path,
        required_kind="file",
        required_when_enabled=enabled,
    )
    if Path(tool_resolved).suffix.casefold() == ".dll" and tool_row["status"] == "ready":
        dotnet = shutil.which("dotnet")
        if dotnet:
            tool_row["message"] = f"BDPGS OCR .dll is accessible and dotnet was found at {dotnet}."
            tool_row["prefix_executable"] = dotnet
        else:
            tool_row["status"] = "blocked" if enabled else "review"
            tool_row["message"] = "BDPGS OCR tool is a .dll but dotnet was not found on PATH."
            tool_row["prefix_executable"] = ""
    tess_required = enabled and bool(tess_configured)
    tess_row = settings_path_evidence_row(
        key=KEY_BDPGS_OCR_TESSDATA_PATH,
        label="BDPGS OCR tessdata folder",
        raw_value=tess_configured,
        resolved_path=tess_resolved,
        command_lookup=False,
        required_kind="directory",
        required_when_enabled=tess_required,
    )
    if enabled and not tess_configured:
        tess_row["status"] = "ready"
        tess_row["message"] = "No tessdata path is configured; the OCR tool default search path will be used."
    rows = [tool_row, tess_row]
    blocked = [row for row in rows if row["status"] == "blocked"]
    review = [row for row in rows if row["status"] == "review"]
    operator_status = "Blocked" if blocked else "Review" if review else "Ready" if enabled else "Inactive"
    summary_lines = [
        f"BDPGS OCR path evidence: {operator_status}",
        f"OCR enabled in saved config: {'yes' if enabled else 'no'}",
        f"AllowSystemTools/PATH fallback: {'yes' if allow_system_tools else 'no'}",
        f"Tool: {tool_row['message']}",
        f"Tessdata: {tess_row['message']}",
        "Mutation guardrail: this evidence is read-only and comes from saved backend config; WebView does not resolve arbitrary paths or run OCR.",
    ]
    return {
        "schema_version": "settings_bdpgs_ocr_path_evidence.v1",
        "read_only": True,
        "operator_status": operator_status,
        "enabled": enabled,
        "allow_system_tools": allow_system_tools,
        "rows": rows,
        "blocked_count": len(blocked),
        "review_count": len(review),
        "summary_lines": summary_lines,
    }


def settings_vobsub_ocr_path_evidence(resolved: ResolvedPaths, config: dict[str, Any]) -> dict[str, Any]:
    enabled = settings_bool(config, KEY_CONVERT_VOBSUB_TO_SRT, False)
    allow_system_tools = settings_bool(config, KEY_ALLOW_SYSTEM_TOOLS, False)
    tool_configured, tool_resolved, tool_from_path = settings_resolve_configured_path(
        resolved,
        config.get(KEY_VOBSUB_OCR_TOOL_PATH),
        allow_command_lookup=allow_system_tools,
    )
    tool_row = settings_path_evidence_row(
        key=KEY_VOBSUB_OCR_TOOL_PATH,
        label="VobSub OCR tool",
        raw_value=tool_configured,
        resolved_path=tool_resolved,
        command_lookup=tool_from_path,
        required_kind="file",
        required_when_enabled=enabled,
    )
    if Path(tool_resolved).suffix.casefold() == ".dll" and tool_row["status"] == "ready":
        dotnet = shutil.which("dotnet")
        if dotnet:
            tool_row["message"] = f"VobSub OCR .dll is accessible and dotnet was found at {dotnet}."
            tool_row["prefix_executable"] = dotnet
        else:
            tool_row["status"] = "blocked" if enabled else "review"
            tool_row["message"] = "VobSub OCR tool is a .dll but dotnet was not found on PATH."
            tool_row["prefix_executable"] = ""
    if Path(tool_resolved).name.casefold() == "seconv.exe" and tool_row["status"] == "ready":
        tool_row["status"] = "blocked" if enabled else "review"
        tool_row["message"] = "VobSub OCR tool points to seconv.exe, but seconv currently skips VobSub OCR; use Subtitle Edit 4.x SubtitleEdit.exe."

    tesseract_configured, tesseract_path, tesseract_from_path = settings_resolve_vobsub_tesseract_path(
        resolved,
        allow_command_lookup=allow_system_tools,
    )
    tesseract_exists = bool(tesseract_path and (Path(tesseract_path).is_file() or tesseract_from_path))
    tesseract_status = "ready" if tesseract_exists else "blocked" if enabled else "inactive"
    tesseract_missing_message = (
        "Tesseract was not found in bundled VobSub OCR tool paths or PATH."
        if allow_system_tools
        else "Tesseract was not found in bundled VobSub OCR tool paths."
    )
    tesseract_row = {
        "key": "tesseract",
        "label": "Tesseract OCR",
        "configured": tesseract_configured,
        "resolved": tesseract_path,
        "exists": tesseract_exists,
        "path_type": "command" if tesseract_from_path else "file" if tesseract_exists else "missing",
        "required_kind": "file",
        "status": tesseract_status,
        "message": f"Tesseract was found at {tesseract_path}." if tesseract_exists else tesseract_missing_message,
        "command_lookup": tesseract_from_path,
    }
    rows = [tool_row, tesseract_row]
    blocked = [row for row in rows if row["status"] == "blocked"]
    review = [row for row in rows if row["status"] == "review"]
    operator_status = "Blocked" if blocked else "Review" if review else "Ready" if enabled else "Inactive"
    summary_lines = [
        f"VobSub OCR path evidence: {operator_status}",
        f"OCR enabled in saved config: {'yes' if enabled else 'no'}",
        f"AllowSystemTools/PATH fallback: {'yes' if allow_system_tools else 'no'}",
        f"Tool: {tool_row['message']}",
        f"Tesseract: {tesseract_row['message']}",
        "Mutation guardrail: this evidence is read-only and comes from saved backend config; WebView does not resolve arbitrary paths or run OCR.",
    ]
    return {
        "schema_version": "settings_vobsub_ocr_path_evidence.v1",
        "read_only": True,
        "operator_status": operator_status,
        "enabled": enabled,
        "allow_system_tools": allow_system_tools,
        "rows": rows,
        "blocked_count": len(blocked),
        "review_count": len(review),
        "summary_lines": summary_lines,
    }


def settings_worst_operator_status(*statuses: str) -> str:
    order = {"Blocked": 3, "Review": 2, "Ready": 1, "Inactive": 0}
    return max(statuses, key=lambda value: order.get(value, 0), default="Inactive")


def settings_tool_path_evidence(resolved: ResolvedPaths, config: dict[str, Any]) -> dict[str, Any]:
    bdpgs = settings_bdpgs_ocr_path_evidence(resolved, config)
    vobsub = settings_vobsub_ocr_path_evidence(resolved, config)
    return {
        "schema_version": "settings_tool_path_evidence.v1",
        "read_only": True,
        "bdpgs_ocr": bdpgs,
        "vobsub_ocr": vobsub,
        "operator_status": settings_worst_operator_status(bdpgs["operator_status"], vobsub["operator_status"]),
        "summary_lines": [
            "Settings tool-path evidence:",
            *bdpgs["summary_lines"],
            *vobsub["summary_lines"],
        ],
    }


def settings_validation_missing_values_result() -> CommandResult:
    return _command_result(
        command=SETTINGS_VALIDATE_COMMAND,
        ok=False,
        message="Settings validation requires a JSON object named values.",
        severity="error",
        errors=["Missing values object."],
    )


def settings_validation_unavailable_result() -> CommandResult:
    return _command_result(
        command=SETTINGS_VALIDATE_COMMAND,
        ok=False,
        message="Settings validation service is not available.",
        severity="error",
        errors=["Settings validation service is not available."],
    )


def settings_validation_exception_result(exc: Exception) -> CommandResult:
    return _command_result(
        command=SETTINGS_VALIDATE_COMMAND,
        ok=False,
        message=f"Settings validation failed: {exc}",
        severity="error",
        errors=[str(exc)],
    )


def settings_validation_result(values: dict[str, Any], raw_errors: object, raw_warnings: object) -> CommandResult:
    errors = [str(item) for item in raw_errors or []]  # type: ignore[union-attr]
    warnings = [str(item) for item in raw_warnings or []]  # type: ignore[union-attr]
    severity = "error" if errors else "warning" if warnings else "info"
    message = "Settings validation passed."
    if errors:
        message = f"Settings validation failed with {len(errors)} error(s)."
    elif warnings:
        message = f"Settings validation passed with {len(warnings)} warning(s)."
    return _command_result(
        command=SETTINGS_VALIDATE_COMMAND,
        ok=not errors,
        message=message,
        severity=severity,
        warnings=warnings,
        errors=errors,
        refresh_hint="settings",
        data={"key_count": len(values)},
    )

__all__ = [
    "SETTINGS_VALIDATE_COMMAND",
    "settings_path_text",
    "settings_config_path_value",
    "settings_workspace_paths",
    "settings_bool",
    "settings_pipeline_base",
    "settings_resolve_configured_path",
    "settings_path_evidence_row",
    "settings_bdpgs_ocr_path_evidence",
    "settings_vobsub_ocr_path_evidence",
    "settings_tool_path_evidence",
    "settings_validation_missing_values_result",
    "settings_validation_unavailable_result",
    "settings_validation_exception_result",
    "settings_validation_result",
]
