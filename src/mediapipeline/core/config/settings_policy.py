"""Settings workspace and validation policy."""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import TYPE_CHECKING, Any

from mediapipeline.core.config.encoding_capabilities import encoding_capability_facts_from_encoder_rows
from mediapipeline.core.kernel.config_keys import (
    KEY_ALLOW_SYSTEM_TOOLS,
    KEY_BDPGS_OCR_TESSDATA_PATH,
    KEY_BDPGS_OCR_TOOL_PATH,
    KEY_CONVERT_BDPGS_TO_SRT,
    KEY_CONVERT_VOBSUB_TO_SRT,
    KEY_OUTSOURCE,
    KEY_VOBSUB_OCR_TOOL_PATH,
)
from mediapipeline.core.paths.contracts import ResolvedPaths

if TYPE_CHECKING:
    from mediapipeline.core.kernel.dto_commands import CommandResult


SETTINGS_VALIDATE_COMMAND = "settings.validate"
VOBSUB_TESSERACT_BUNDLED_CANDIDATES = (
    Path("Tools") / "SubtitleEditLegacy" / "Tesseract550" / "tesseract.exe",
    Path("Tools") / "SubtitleEditLegacy" / "Tesseract-OCR" / "tesseract.exe",
    Path("Tools") / "SubtitleEditLegacy" / "Tesseract302" / "tesseract.exe",
    Path("Tools") / "SubtitleEditLegacy" / "Tesseract" / "tesseract.exe",
    Path("Tools") / "SubtitleEdit" / "Tesseract550" / "tesseract.exe",
    Path("Tools") / "SubtitleEdit" / "Tesseract-OCR" / "tesseract.exe",
    Path("Tools") / "SubtitleEdit" / "Tesseract302" / "tesseract.exe",
    Path("Tools") / "SubtitleEdit" / "Tesseract" / "tesseract.exe",
    Path("Tools") / "Tesseract-OCR" / "tesseract.exe",
    Path("Tools") / "Tesseract" / "tesseract.exe",
)
ENCODER_CAPABILITY_REPORT_SCHEMA = "settings_encoder_capability_report.v1"
ENCODER_CAPABILITY_REPORT_SOURCE_SCHEMA = "mediapipeline.encoder_capabilities.v2"
ENCODER_CAPABILITY_REPORT_LEGACY_SOURCE_SCHEMA = "mediapipeline.encoder_capabilities.v1"
ENCODER_CAPABILITY_REPORT_MAX_BYTES = 1024 * 1024
HARDWARE_ENCODER_BACKENDS = frozenset({"nvenc", "qsv", "amf"})


def _command_result(**fields: Any) -> CommandResult:
    from mediapipeline.core.kernel.dto_commands import CommandResult

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


def settings_encoder_capability_report(resolved: ResolvedPaths) -> dict[str, Any]:
    """Return read-only evidence from a previously generated encoder capability report."""

    path = _settings_encoder_capability_report_path(resolved)
    base = _settings_encoder_capability_report_base(path)
    if path is None:
        base.update(
            {
                "operator_status": "Unavailable",
                "operator_status_state": "unknown",
                "summary_lines": ["Encoder capability report path is unavailable."],
            }
        )
        return base
    if not path.is_file():
        base.update(
            {
                "operator_status": "Not generated",
                "operator_status_state": "missing",
                "summary_lines": [
                    "No encoder capability report has been generated yet.",
                    "Run the backend-owned encoder capability diagnostic to refresh this evidence.",
                ],
            }
        )
        return base
    try:
        size_bytes = path.stat().st_size
    except OSError as exc:
        base.update(
            {
                "exists": True,
                "operator_status": "Unreadable",
                "operator_status_state": "warning",
                "errors": [f"Encoder capability report stat failed: {exc}"],
                "summary_lines": ["Encoder capability report exists but could not be inspected."],
            }
        )
        return base
    if size_bytes > ENCODER_CAPABILITY_REPORT_MAX_BYTES:
        base.update(
            {
                "exists": True,
                "size_bytes": size_bytes,
                "operator_status": "Too large",
                "operator_status_state": "warning",
                "errors": [f"Encoder capability report exceeds {ENCODER_CAPABILITY_REPORT_MAX_BYTES} bytes."],
                "summary_lines": ["Encoder capability report exists but is too large for settings workspace display."],
            }
        )
        return base
    try:
        raw = path.read_text(encoding="utf-8")
        report = json.loads(raw) if raw.strip() else {}
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        base.update(
            {
                "exists": True,
                "size_bytes": size_bytes,
                "operator_status": "Unreadable",
                "operator_status_state": "warning",
                "errors": [f"Encoder capability report read failed: {exc}"],
                "summary_lines": ["Encoder capability report exists but could not be parsed."],
            }
        )
        return base
    if not isinstance(report, dict):
        base.update(
            {
                "exists": True,
                "size_bytes": size_bytes,
                "operator_status": "Unreadable",
                "operator_status_state": "warning",
                "errors": ["Encoder capability report root must be a JSON object."],
                "summary_lines": ["Encoder capability report exists but has an unexpected shape."],
            }
        )
        return base
    return _settings_encoder_capability_report_from_payload(base, report, size_bytes)


def _settings_encoder_capability_report_path(resolved: ResolvedPaths) -> Path | None:
    if resolved.progress_file:
        return Path(resolved.progress_file).with_name("encoder_capabilities.json")
    if resolved.state_root:
        return Path(resolved.state_root) / "Progress" / "encoder_capabilities.json"
    if resolved.local_base:
        return Path(resolved.local_base) / "State" / "Progress" / "encoder_capabilities.json"
    return None


def _settings_encoder_capability_report_base(path: Path | None) -> dict[str, Any]:
    return {
        "schema_version": ENCODER_CAPABILITY_REPORT_SCHEMA,
        "read_only": True,
        "source": "-DumpEncoderCapabilitiesPath",
        "source_path": settings_path_text(path),
        "exists": False,
        "size_bytes": 0,
        "operator_status": "Not generated",
        "operator_status_state": "missing",
        "report_schema": "",
        "generated_at": "",
        "video_codec": "",
        "encoder_backend": "",
        "selection": {},
        "encoders": [],
        "available_encoders": [],
        "unavailable_encoders": [],
        "active_encoders": [],
        "available_inactive_encoders": [],
        "activation_unknown_encoders": [],
        "hardware_runtime_verified_encoders": [],
        "hardware_runtime_skipped_encoders": [],
        "active_hardware_runtime_unverified_encoders": [],
        "backend_counts": {},
        "encoding_capability_facts": {},
        "evidence": {},
        "summary_lines": [],
        "errors": [],
    }


def _settings_encoder_capability_report_from_payload(
    base: dict[str, Any],
    report: dict[str, Any],
    size_bytes: int,
) -> dict[str, Any]:
    rows = [
        _settings_encoder_capability_row(row)
        for row in report.get("encoders", [])
        if isinstance(row, dict)
    ]
    available = [row["encoder_name"] for row in rows if row["available"]]
    unavailable = [row["encoder_name"] for row in rows if not row["available"]]
    active = [
        row["encoder_name"]
        for row in rows
        if row["available"] and row["descriptor_flags_active"]
    ]
    inactive_available = [
        row["encoder_name"]
        for row in rows
        if row["available"] and row["activation_known"] and not row["descriptor_flags_active"]
    ]
    activation_unknown = [
        row["encoder_name"]
        for row in rows
        if row["available"] and not row["activation_known"]
    ]
    hardware_runtime_verified = [
        row["encoder_name"]
        for row in rows
        if _settings_encoder_row_is_hardware(row) and row["runtime_ok"]
    ]
    hardware_runtime_skipped = [
        row["encoder_name"]
        for row in rows
        if _settings_encoder_row_is_hardware(row) and row["runtime_probe_skipped"]
    ]
    active_hardware_runtime_unverified = [
        row["encoder_name"]
        for row in rows
        if _settings_encoder_row_is_hardware(row) and row["descriptor_flags_active"] and not row["runtime_ok"]
    ]
    activation_known = any(row["activation_known"] for row in rows)
    capability_rows = [row for row in rows if row["available"] and row["descriptor_flags_active"]] if activation_known else rows
    capability_facts = encoding_capability_facts_from_encoder_rows(capability_rows).model_dump()
    report_schema = str(report.get("schema") or report.get("schema_version") or "")
    errors: list[str] = []
    if report_schema == ENCODER_CAPABILITY_REPORT_LEGACY_SOURCE_SCHEMA:
        errors.append("Legacy encoder capability report is review-only; refresh backend diagnostic evidence.")
    elif report_schema != ENCODER_CAPABILITY_REPORT_SOURCE_SCHEMA:
        errors.append(f"Unexpected encoder capability report schema: {report_schema or '(missing)'}")
    if not rows:
        errors.append("Encoder capability report did not include encoder rows.")
    if activation_unknown:
        errors.append(
            "Encoder capability report did not include descriptor activation readiness for: "
            f"{', '.join(activation_unknown)}"
        )
    if active_hardware_runtime_unverified:
        errors.append(
            "Active hardware descriptor rows lack runtime proof and remain review-only: "
            f"{', '.join(active_hardware_runtime_unverified)}"
        )
    state = "ready" if not errors and not unavailable and not inactive_available else "warning"
    status = "Ready" if state == "ready" else "Review"
    video_codec = str(report.get("video_codec") or "")
    encoder_backend = str(report.get("encoder_backend") or "")
    evidence = _settings_encoder_capability_evidence(report.get("evidence"))
    if report_schema == ENCODER_CAPABILITY_REPORT_SOURCE_SCHEMA:
        required_evidence = ("freshness", "resolved_config", "ffmpeg", "host", "selected_descriptor_chain")
        missing_evidence = [key for key in required_evidence if not evidence.get(key)]
        if missing_evidence:
            errors.append(f"Capability evidence is incomplete: {', '.join(missing_evidence)}")
    summary = [
        f"Report generated for VideoCodec={video_codec or '(unknown)'}, EncoderBackend={encoder_backend or '(unknown)'}.",
        f"Available encoders: {', '.join(available) if available else 'none'}.",
        f"Active descriptor-owned encoders: {', '.join(active) if active else 'none'}.",
    ]
    if unavailable:
        summary.append(f"Unavailable encoders: {', '.join(unavailable)}.")
    if inactive_available:
        summary.append(
            "Available but not active for descriptor-owned attempts: "
            f"{', '.join(inactive_available)}."
        )
    if hardware_runtime_verified:
        summary.append(f"Hardware runtime proof available for: {', '.join(hardware_runtime_verified)}.")
    if hardware_runtime_skipped:
        summary.append(f"Hardware runtime probe skipped for: {', '.join(hardware_runtime_skipped)}.")
    if active_hardware_runtime_unverified:
        summary.append(
            "Active hardware descriptors without runtime proof: "
            f"{', '.join(active_hardware_runtime_unverified)}."
        )
    if evidence:
        summary.append(
            "Evidence boundary: availability/activation/runtime probes are not metadata or playback certification."
        )
    if errors:
        summary.extend(errors)
    base.update(
        {
            "exists": True,
            "size_bytes": size_bytes,
            "operator_status": status,
            "operator_status_state": state,
            "report_schema": report_schema,
            "generated_at": str(report.get("generated_at") or ""),
            "video_codec": video_codec,
            "encoder_backend": encoder_backend,
            "selection": _settings_encoder_capability_selection(report.get("selection")),
            "encoders": rows,
            "available_encoders": available,
            "unavailable_encoders": unavailable,
            "active_encoders": active,
            "available_inactive_encoders": inactive_available,
            "activation_unknown_encoders": activation_unknown,
            "hardware_runtime_verified_encoders": hardware_runtime_verified,
            "hardware_runtime_skipped_encoders": hardware_runtime_skipped,
            "active_hardware_runtime_unverified_encoders": active_hardware_runtime_unverified,
            "backend_counts": _settings_encoder_backend_counts(rows),
            "encoding_capability_facts": capability_facts,
            "evidence": evidence,
            "summary_lines": summary,
            "errors": errors,
        }
    )
    return base


def _settings_encoder_capability_evidence(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    return {
        "evidence_schema": str(value.get("evidence_schema") or ""),
        "freshness": _settings_encoder_capability_evidence_object(value.get("freshness")),
        "resolved_config": _settings_encoder_capability_evidence_object(value.get("resolved_config")),
        "ffmpeg": _settings_encoder_capability_evidence_object(value.get("ffmpeg")),
        "host": _settings_encoder_capability_evidence_object(value.get("host")),
        "selected_descriptor_chain": _settings_encoder_capability_evidence_object(value.get("selected_descriptor_chain")),
        "activation_state": _settings_encoder_capability_evidence_object(value.get("activation_state")),
        "list_probe_state": str(value.get("list_probe_state") or ""),
        "runtime_probe_state": str(value.get("runtime_probe_state") or ""),
        "invalidation_state": _settings_encoder_capability_evidence_object(value.get("invalidation_state")),
        "metadata_proof_state": str(value.get("metadata_proof_state") or "not_collected"),
        "playback_proof_state": str(value.get("playback_proof_state") or "not_collected"),
    }


def _settings_encoder_capability_evidence_object(value: Any) -> dict[str, Any]:
    return {str(key): item for key, item in value.items()} if isinstance(value, dict) else {}


def _settings_encoder_capability_selection(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    return {
        "resolved": bool(value.get("resolved")),
        "reason": str(value.get("reason") or ""),
        "family": str(value.get("family") or ""),
    }


def _settings_encoder_capability_row(value: dict[str, Any]) -> dict[str, Any]:
    roles = value.get("roles")
    activation_rows = _settings_encoder_capability_row_activation(value.get("activation"))
    activation_known = "descriptor_flags_active" in value or bool(activation_rows)
    if "descriptor_flags_active" in value:
        descriptor_flags_active = bool(value.get("descriptor_flags_active"))
    elif activation_rows:
        descriptor_flags_active = any(row["active"] for row in activation_rows)
    else:
        descriptor_flags_active = bool(value.get("available"))
    return {
        "encoder_name": str(value.get("encoder_name") or ""),
        "probe_encoder_name": str(value.get("probe_encoder_name") or ""),
        "family": str(value.get("family") or ""),
        "backend": str(value.get("backend") or ""),
        "roles": [str(role) for role in roles if str(role).strip()] if isinstance(roles, list) else [],
        "descriptor_flags_active": descriptor_flags_active,
        "activation_known": activation_known,
        "activation": activation_rows,
        "available": bool(value.get("available")),
        "probed": bool(value.get("probed")),
        "runtime_probe_skipped": bool(value.get("runtime_probe_skipped")),
        "encoder_list_match": bool(value.get("encoder_list_match")),
        "runtime_ok": bool(value.get("runtime_ok")),
        "backend_invalidated": bool(value.get("backend_invalidated")),
        "reason": str(value.get("reason") or ""),
        "probed_at": str(value.get("probed_at") or ""),
    }


def _settings_encoder_capability_row_activation(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    rows: list[dict[str, Any]] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        rows.append(
            {
                "role": str(item.get("role") or ""),
                "active": bool(item.get("active")),
                "descriptor_encoder": str(item.get("descriptor_encoder") or ""),
                "active_descriptor_encoder": str(item.get("active_descriptor_encoder") or ""),
                "reason": str(item.get("reason") or ""),
            }
        )
    return rows


def _settings_encoder_row_is_hardware(row: dict[str, Any]) -> bool:
    backend = str(row.get("backend") or "").strip().casefold()
    return backend in HARDWARE_ENCODER_BACKENDS


def _settings_encoder_backend_counts(rows: list[dict[str, Any]]) -> dict[str, dict[str, int]]:
    counts: dict[str, dict[str, int]] = {}
    for row in rows:
        backend = str(row.get("backend") or "unknown")
        bucket = counts.setdefault(backend, {"available": 0, "unavailable": 0, "total": 0})
        bucket["total"] += 1
        if row.get("available"):
            bucket["available"] += 1
        else:
            bucket["unavailable"] += 1
    return counts


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


def _settings_add_unique_path(paths: list[Path], candidate: object) -> None:
    try:
        path = Path(candidate)
    except (TypeError, ValueError):
        return
    if not str(path):
        return
    key = str(path).casefold()
    if any(str(existing).casefold() == key for existing in paths):
        return
    paths.append(path)


def _settings_add_pipeline_base(paths: list[Path], candidate: object, *, include_tool_roots: bool) -> None:
    try:
        base = Path(candidate)
    except (TypeError, ValueError):
        return
    if not str(base):
        return
    if base.name.casefold() == "entrypoints":
        pipeline_base = base.parent
        _settings_add_unique_path(paths, pipeline_base)
        if include_tool_roots:
            _settings_add_unique_path(paths, pipeline_base / "tools")
        _settings_add_unique_path(paths, base)
        return
    _settings_add_unique_path(paths, base)
    if include_tool_roots and base.name.casefold() == "pipeline":
        _settings_add_unique_path(paths, base / "tools")


def settings_pipeline_bases(resolved: ResolvedPaths, *, include_tool_roots: bool = True) -> tuple[Path, ...]:
    paths: list[Path] = []
    try:
        if resolved.pipeline_path:
            _settings_add_pipeline_base(paths, Path(resolved.pipeline_path).parent, include_tool_roots=include_tool_roots)
    except (TypeError, ValueError):
        pass
    try:
        workspace_root = Path(resolved.workspace_root)
    except (TypeError, ValueError):
        workspace_root = None
    if workspace_root is not None:
        _settings_add_pipeline_base(paths, workspace_root / "ops" / "pipeline", include_tool_roots=include_tool_roots)
        _settings_add_pipeline_base(paths, workspace_root / "Pipeline", include_tool_roots=include_tool_roots)
        _settings_add_unique_path(paths, workspace_root)
    try:
        app_root = Path(resolved.app_root)
    except (TypeError, ValueError):
        app_root = None
    if app_root is not None:
        _settings_add_pipeline_base(paths, app_root / "pipeline", include_tool_roots=include_tool_roots)
        if include_tool_roots:
            _settings_add_unique_path(paths, app_root / "tools")
        _settings_add_unique_path(paths, app_root)
    return tuple(paths)


def settings_pipeline_base(resolved: ResolvedPaths) -> Path:
    bases = settings_pipeline_bases(resolved, include_tool_roots=False)
    if bases:
        return bases[0]
    return Path(resolved.workspace_root)


def _settings_existing_or_first_candidate(
    resolved: ResolvedPaths,
    raw_path: Path,
) -> tuple[Path, bool]:
    first_candidate: Path | None = None
    for base in settings_pipeline_bases(resolved):
        candidate = base / raw_path
        if first_candidate is None:
            first_candidate = candidate
        if candidate.exists():
            return candidate, True
    return first_candidate or raw_path, False


def settings_resolve_configured_path(resolved: ResolvedPaths, raw_value: object, *, allow_command_lookup: bool = False) -> tuple[str, str, bool]:
    raw = str(raw_value or "").strip()
    if not raw:
        return "", "", False
    raw_path = Path(raw)
    if raw_path.is_absolute():
        candidate = raw_path
        exists = candidate.exists()
    else:
        candidate, exists = _settings_existing_or_first_candidate(resolved, raw_path)
    if exists:
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
    first: Path | None = None
    first_relative = VOBSUB_TESSERACT_BUNDLED_CANDIDATES[0]
    for base in settings_pipeline_bases(resolved):
        for relative in VOBSUB_TESSERACT_BUNDLED_CANDIDATES:
            candidate = base / relative
            if first is None:
                first = candidate
                first_relative = relative
            if candidate.is_file():
                try:
                    return str(relative), str(candidate.resolve()), False
                except OSError:
                    return str(relative), str(candidate), False
    if allow_command_lookup:
        found = shutil.which("tesseract")
        if found:
            return "PATH", found, True
    if first is None:
        first = settings_pipeline_base(resolved) / first_relative
    try:
        return str(first_relative), str(first.resolve(strict=False)), False
    except OSError:
        return str(first_relative), str(first), False


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
    enabled = settings_bool(config, KEY_CONVERT_BDPGS_TO_SRT, False)
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
    "settings_encoder_capability_report",
    "settings_bool",
    "settings_pipeline_bases",
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
