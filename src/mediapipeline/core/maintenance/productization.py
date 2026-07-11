"""Productized desktop runtime and support-export helpers."""

from __future__ import annotations

import json
import os
import re
import shutil
import tempfile
from datetime import datetime, UTC
from pathlib import Path
from typing import Any

from mediapipeline.core.kernel.config_locations import PER_USER_APP_DIR_NAME, user_config_dir
from mediapipeline.core.network.url_policy import redact_network_secret_text
from mediapipeline.core.storage.constants import APP_STATE_NAME


PRODUCTIZATION_STATUS_SCHEMA_VERSION = "desktop_productization_status.v1"
SUPPORT_EXPORT_SCHEMA_VERSION = "desktop_support_export.v1"
MIGRATION_EVIDENCE_SCHEMA_VERSION = "desktop_appdata_migration.v1"
SUPPORT_EXPORT_COMMAND = "maintenance.support_export"
MAINTENANCE_REFRESH_HINT = "maintenance"
DEFAULT_RELEASE_CHANNEL = "beta"
MAX_SUPPORT_LOG_BYTES = 128 * 1024
MAX_SUPPORT_LOG_LINES = 120
MAX_IMPORT_FILE_BYTES = 8 * 1024 * 1024

_SENSITIVE_KEY_TERMS = (
    "api_key",
    "apikey",
    "authorization",
    "certificate",
    "credential",
    "password",
    "private_key",
    "secret",
    "signing",
    "token",
)
_PATH_KEY_TERMS = (
    "dir",
    "file",
    "folder",
    "manifest",
    "path",
    "root",
)
_WINDOWS_ABSOLUTE_PATH_RE = re.compile(r"(?i)\b[A-Z]:\\[^\s\"'<>|]+")
_UNC_PATH_RE = re.compile(r"\\\\[^\s\"'<>|]+")


def utc_timestamp() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def utc_file_stamp() -> str:
    return datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")


def productized_app_enabled() -> bool:
    return str(os.environ.get("MEDIAPIPELINE_PRODUCTIZED_APP") or "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def product_release_channel() -> str:
    raw = str(os.environ.get("MEDIAPIPELINE_RELEASE_CHANNEL") or DEFAULT_RELEASE_CHANNEL).strip().lower()
    return raw if raw in {"beta", "stable"} else DEFAULT_RELEASE_CHANNEL


def product_appdata_root() -> Path | None:
    override = str(os.environ.get("MEDIAPIPELINE_APPDATA_ROOT") or "").strip()
    if override:
        return Path(override).expanduser()
    return user_config_dir()


def product_runtime_roots(*, create: bool = False) -> dict[str, Path] | None:
    appdata_root = product_appdata_root()
    if appdata_root is None:
        return None
    roots = {
        "appdata_root": appdata_root,
        # Reserved service-owned home for productized configuration and
        # migration metadata. Legacy settings projections may remain at the
        # app-data root until their own migration completes.
        "config_root": appdata_root / "Config",
        "state_root": appdata_root / "State",
        "logs_root": appdata_root / "Logs",
        "run_logs_root": appdata_root / "RunLogs",
        "diagnostics_exports_root": appdata_root / "DiagnosticsExports",
        "update_state_root": appdata_root / "UpdateState",
        "backups_root": appdata_root / "Backups",
        "migration_root": appdata_root / "State" / "Migration",
    }
    if create:
        for path in roots.values():
            path.mkdir(parents=True, exist_ok=True)
    return roots


def known_redaction_roots(
    *,
    app_root: Path | None = None,
    workspace_root: Path | None = None,
    resolved: object | None = None,
) -> list[tuple[str, Path]]:
    roots: list[tuple[str, Path]] = []
    runtime_roots = product_runtime_roots(create=False) or {}
    for label, path in runtime_roots.items():
        roots.append((label, path))
    for label, path in (
        ("app_root", app_root),
        ("workspace_root", workspace_root),
        ("local_base", getattr(resolved, "local_base", None) if resolved is not None else None),
        ("state_root", getattr(resolved, "state_root", None) if resolved is not None else None),
        ("user_home", Path.home()),
    ):
        if path is not None:
            roots.append((label, Path(path)))
    deduped: dict[str, Path] = {}
    for label, path in roots:
        try:
            text = str(path.resolve())
        except OSError:
            text = str(path)
        if text:
            deduped[f"{label}:{text.casefold()}"] = path
    return sorted(
        ((key.split(":", 1)[0], path) for key, path in deduped.items()),
        key=lambda item: len(str(item[1])),
        reverse=True,
    )


def _is_sensitive_key(key: Any) -> bool:
    text = str(key or "").casefold()
    return any(term in text for term in _SENSITIVE_KEY_TERMS)


def _is_path_key(key: Any) -> bool:
    text = str(key or "").casefold()
    return any(term in text for term in _PATH_KEY_TERMS)


def _path_under(path: Path, root: Path) -> str | None:
    raw = str(path)
    raw_root = str(root)
    if not raw or not raw_root:
        return None
    raw_norm = raw.rstrip("\\/").casefold()
    root_norm = raw_root.rstrip("\\/").casefold()
    if raw_norm == root_norm:
        return ""
    prefix = root_norm + ("\\" if "\\" in raw_root else "/")
    if raw_norm.startswith(prefix):
        return raw[len(raw_root) :].lstrip("\\/")
    return None


def redact_path(value: Any, roots: list[tuple[str, Path]]) -> str:
    text = redact_network_secret_text(value).strip()
    if not text:
        return ""
    path = Path(text)
    for label, root in roots:
        relative = _path_under(path, root)
        if relative is not None:
            return f"<{label}>{'/' + relative.replace(chr(92), '/') if relative else ''}"
    if path.is_absolute() or text.startswith("\\\\"):
        name = path.name
        return f"<redacted-path>{'/' + name if name else ''}"
    return text


def _redact_absolute_path_match(match: re.Match[str]) -> str:
    raw = match.group(0)
    name = Path(raw.rstrip(".,);]")).name
    return f"<redacted-path>{'/' + name if name else ''}"


def redact_text(value: Any, roots: list[tuple[str, Path]]) -> str:
    text = redact_network_secret_text(value)
    for label, root in roots:
        raw_root = str(root)
        if raw_root:
            text = re.sub(re.escape(raw_root), f"<{label}>", text, flags=re.IGNORECASE)
    text = _WINDOWS_ABSOLUTE_PATH_RE.sub(_redact_absolute_path_match, text)
    text = _UNC_PATH_RE.sub(_redact_absolute_path_match, text)
    return text


def redact_value(value: Any, roots: list[tuple[str, Path]], *, key: Any = "") -> Any:
    if _is_sensitive_key(key):
        return "<redacted>"
    if value is None or isinstance(value, bool | int | float):
        return value
    if isinstance(value, Path):
        return redact_path(value, roots)
    if isinstance(value, str):
        return redact_path(value, roots) if _is_path_key(key) else redact_text(value, roots)
    if isinstance(value, dict):
        return {str(item_key): redact_value(item_value, roots, key=item_key) for item_key, item_value in value.items()}
    if isinstance(value, list | tuple):
        return [redact_value(item, roots, key=key) for item in value[:200]]
    return redact_text(value, roots)


def _write_json_atomically(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    tmp_path = Path(tmp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_path, path)
    except Exception:
        try:
            tmp_path.unlink(missing_ok=True)
        except OSError:
            pass
        raise


def _read_json(path: Path) -> dict[str, Any] | None:
    try:
        with path.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
        return payload if isinstance(payload, dict) else None
    except (OSError, json.JSONDecodeError):
        return None


def _copy_safe_import_file(source: Path, destination: Path) -> dict[str, Any]:
    if not source.exists() or not source.is_file():
        return {"source": source.name, "status": "missing"}
    size = source.stat().st_size
    if size > MAX_IMPORT_FILE_BYTES:
        return {
            "source": source.name,
            "status": "skipped",
            "reason": "too_large",
            "bytes": size,
        }
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)
    return {
        "source": source.name,
        "status": "copied",
        "bytes": size,
        "backup_name": destination.name,
    }


def prepare_product_runtime(app_root: Path, workspace_root: Path, *, logger: Any = None) -> dict[str, Any]:
    roots = product_runtime_roots(create=True)
    if roots is None:
        return {
            "schema_version": MIGRATION_EVIDENCE_SCHEMA_VERSION,
            "status": "appdata_unavailable",
            "appdata_available": False,
            "writes_media": False,
            "deletes_media": False,
            "updated_at": utc_timestamp(),
        }
    evidence_path = roots["migration_root"] / "localbase_import.json"
    existing = _read_json(evidence_path)
    if existing is not None:
        return existing

    stamp = utc_file_stamp()
    backup_root = roots["backups_root"] / "LocalBaseImport" / stamp
    candidates = [
        ("workspace_localbase", workspace_root / "LocalBase"),
        ("app_localbase", app_root / "LocalBase"),
    ]
    standalone_files = [
        ("legacy_app_state", app_root / APP_STATE_NAME),
        ("legacy_command_journal", app_root / "RunLogs" / "local_api_command_history.json"),
    ]
    imported: list[dict[str, Any]] = []
    for label, local_base in candidates:
        if not local_base.exists():
            continue
        for relative in (
            Path("State") / "App" / APP_STATE_NAME,
            Path("RunLogs") / "local_api_command_history.json",
        ):
            result = _copy_safe_import_file(local_base / relative, backup_root / label / relative)
            if result["status"] != "missing":
                result["candidate"] = label
                result["relative_path"] = str(relative).replace("\\", "/")
                imported.append(result)
    for label, source in standalone_files:
        result = _copy_safe_import_file(source, backup_root / label / source.name)
        if result["status"] != "missing":
            result["candidate"] = label
            result["relative_path"] = source.name
            imported.append(result)

    evidence = {
        "schema_version": MIGRATION_EVIDENCE_SCHEMA_VERSION,
        "status": "complete",
        "appdata_available": True,
        "updated_at": utc_timestamp(),
        "backup_name": stamp,
        "imported_count": sum(1 for item in imported if item.get("status") == "copied"),
        "skipped_count": sum(1 for item in imported if item.get("status") == "skipped"),
        "imported": imported,
        "protected_boundaries": {
            "moved_source_media": False,
            "deleted_source_media": False,
            "copied_scratch_payloads": False,
            "copied_output_payloads": False,
            "copied_pending_publish_payloads": False,
            "copied_completed_media": False,
        },
        "writes_media": False,
        "deletes_media": False,
    }
    try:
        _write_json_atomically(evidence_path, evidence)
    except OSError as exc:
        if logger is not None:
            try:
                logger.warning("Productized AppData migration evidence write failed: %s", exc)
            except Exception:
                pass
        evidence["status"] = "evidence_write_failed"
        evidence["error"] = str(exc)
    return evidence


def runtime_roots_payload(app_root: Path, workspace_root: Path, resolved: object | None = None) -> dict[str, Any]:
    roots = product_runtime_roots(create=False)
    redaction_roots = known_redaction_roots(app_root=app_root, workspace_root=workspace_root, resolved=resolved)
    if roots is None:
        return {
            "appdata_available": False,
            "appdata_dir_name": PER_USER_APP_DIR_NAME,
            "productized_app": productized_app_enabled(),
        }
    return {
        "appdata_available": True,
        "productized_app": productized_app_enabled(),
        "roots": {
            key: {
                "path": redact_path(path, redaction_roots),
                "exists": path.exists(),
            }
            for key, path in roots.items()
        },
    }


def _config_summary(config_data: dict[str, Any], roots: list[tuple[str, Path]]) -> dict[str, Any]:
    library_profiles = config_data.get("LibraryProfiles")
    if isinstance(library_profiles, dict):
        library_profile_count = len(library_profiles)
    elif isinstance(library_profiles, list):
        library_profile_count = len(library_profiles)
    else:
        library_profile_count = 0
    notable_keys = [
        "LocalBase",
        "SourceMovies",
        "SourceTV",
        "Outsource",
        "FinalLibraryRoot",
        "LibraryProfiles",
    ]
    return {
        "key_count": len(config_data),
        "notable_keys_present": {key: key in config_data for key in notable_keys},
        "library_profile_count": library_profile_count,
        "local_base": redact_path(config_data.get("LocalBase"), roots) if "LocalBase" in config_data else "",
        "source_movies_present": bool(config_data.get("SourceMovies")),
        "source_tv_present": bool(config_data.get("SourceTV")),
        "sensitive_values_included": False,
        "full_config_included": False,
    }


def _release_manifest_summary(app_root: Path, workspace_root: Path) -> dict[str, Any]:
    candidates = [
        app_root / "release_manifest.json",
        workspace_root / "release_manifest.json",
        workspace_root / "ops" / "release" / "metadata" / "release_manifest.json",
    ]
    for candidate in candidates:
        payload = _read_json(candidate)
        if payload is None:
            continue
        files = payload.get("files")
        if not isinstance(files, list):
            files = payload.get("entries")
        return {
            "found": True,
            "name": candidate.name,
            "schema_version": str(payload.get("schema_version") or ""),
            "version": str(payload.get("version") or payload.get("build_version") or ""),
            "channel": str(payload.get("channel") or ""),
            "file_count": len(files) if isinstance(files, list) else 0,
        }
    return {"found": False}


def _tool_evidence(resolved: object, roots: list[tuple[str, Path]]) -> list[dict[str, Any]]:
    pipeline_path = Path(getattr(resolved, "pipeline_path", ""))
    pipeline_root = pipeline_path.parent
    if pipeline_root.name.casefold() == "entrypoints":
        pipeline_root = pipeline_root.parent
    tools = {
        "ffmpeg": pipeline_root / "tools" / "ffmpeg" / "bin" / "ffmpeg.exe",
        "ffprobe": pipeline_root / "tools" / "ffmpeg" / "bin" / "ffprobe.exe",
        "mkvmerge": pipeline_root / "tools" / "MKVToolNix" / "mkvmerge.exe",
    }
    return [
        {
            "tool": name,
            "path": redact_path(path, roots),
            "exists": path.exists(),
            "version": "not_probed",
        }
        for name, path in tools.items()
    ]


def _tail_text_file(path: Path | None, roots: list[tuple[str, Path]], *, max_bytes: int) -> dict[str, Any]:
    if path is None:
        return {"available": False, "reason": "not_resolved"}
    path = Path(path)
    if not path.exists() or not path.is_file():
        return {"available": False, "path": redact_path(path, roots), "reason": "missing"}
    try:
        size = path.stat().st_size
        with path.open("rb") as handle:
            if size > max_bytes:
                handle.seek(-max_bytes, os.SEEK_END)
            raw = handle.read(max_bytes)
    except OSError as exc:
        return {"available": False, "path": redact_path(path, roots), "reason": str(exc)}
    text = raw.decode("utf-8", errors="replace")
    lines = redact_text(text, roots).splitlines()[-MAX_SUPPORT_LOG_LINES:]
    return {
        "available": True,
        "path": redact_path(path, roots),
        "bytes_read": len(raw),
        "truncated": size > len(raw),
        "lines": lines,
    }


def productization_status_payload(
    *,
    service: object,
    resolved: object,
    app_version: str,
    close_readiness: dict[str, Any] | None = None,
) -> dict[str, Any]:
    app_root = Path(getattr(resolved, "app_root", getattr(service, "app_root", "")))
    workspace_root = Path(getattr(resolved, "workspace_root", getattr(service, "workspace_root", "")))
    roots = known_redaction_roots(app_root=app_root, workspace_root=workspace_root, resolved=resolved)
    runtime_roots = runtime_roots_payload(app_root, workspace_root, resolved)
    config_data = getattr(resolved, "config_data", {}) or {}
    if not isinstance(config_data, dict):
        config_data = {}
    local_base = getattr(resolved, "local_base", None)
    state_root = getattr(resolved, "state_root", None)
    return {
        "schema_version": PRODUCTIZATION_STATUS_SCHEMA_VERSION,
        "app_version": app_version,
        "release_channel": product_release_channel(),
        "installer": {
            "target": "nsis",
            "msi_enabled": False,
            "windows_arch": "x64",
        },
        "updater": {
            "mode": "prompted",
            "channels": ["beta", "stable"],
            "active_channel": product_release_channel(),
            "close_readiness_required": True,
            "close_readiness": close_readiness or {},
        },
        "runtime_roots": runtime_roots,
        "migration": {
            "status": "active" if productized_app_enabled() else "not_started_dev_mode",
            "legacy_local_base": redact_path(local_base, roots) if local_base else "",
            "legacy_state_root": redact_path(state_root, roots) if state_root else "",
            "media_state_still_config_owned": bool(local_base),
            "guarded_import_runs_in_productized_mode": True,
            "writes_media": False,
            "deletes_media": False,
        },
        "config_summary": _config_summary(config_data, roots),
        "release_manifest": _release_manifest_summary(app_root, workspace_root),
    }


def support_export_payload(
    *,
    service: object,
    resolved: object,
    app_version: str,
    request: dict[str, Any],
    close_readiness: dict[str, Any] | None = None,
) -> dict[str, Any]:
    app_root = Path(getattr(resolved, "app_root", getattr(service, "app_root", "")))
    workspace_root = Path(getattr(resolved, "workspace_root", getattr(service, "workspace_root", "")))
    roots = known_redaction_roots(app_root=app_root, workspace_root=workspace_root, resolved=resolved)
    config_data = getattr(resolved, "config_data", {}) or {}
    if not isinstance(config_data, dict):
        config_data = {}
    max_log_bytes = request.get("max_log_bytes", MAX_SUPPORT_LOG_BYTES)
    try:
        max_log_bytes = max(16 * 1024, min(int(max_log_bytes), 512 * 1024))
    except (TypeError, ValueError):
        max_log_bytes = MAX_SUPPORT_LOG_BYTES
    include_recent_logs = request.get("include_recent_logs", True)
    if not isinstance(include_recent_logs, bool):
        include_recent_logs = True
    migration = prepare_product_runtime(app_root, workspace_root, logger=getattr(service, "logger", None))
    payload = {
        "schema_version": SUPPORT_EXPORT_SCHEMA_VERSION,
        "generated_at": utc_timestamp(),
        "app": {
            "version": app_version,
            "release_channel": product_release_channel(),
            "productized_app": productized_app_enabled(),
        },
        "redaction": {
            "personal_paths_redacted": True,
            "secrets_redacted": True,
            "full_config_included": False,
        },
        "close_readiness": redact_value(close_readiness or {}, roots),
        "runtime_roots": runtime_roots_payload(app_root, workspace_root, resolved),
        "migration": redact_value(migration, roots),
        "release_manifest": _release_manifest_summary(app_root, workspace_root),
        "config_summary": _config_summary(config_data, roots),
        "tool_evidence": _tool_evidence(resolved, roots),
        "resolved_paths": {
            "config_path": redact_path(getattr(resolved, "config_path", ""), roots),
            "pipeline_path": redact_path(getattr(resolved, "pipeline_path", ""), roots),
            "local_base": redact_path(getattr(resolved, "local_base", ""), roots),
            "state_root": redact_path(getattr(resolved, "state_root", ""), roots),
            "app_state_path": redact_path(getattr(resolved, "app_state_path", ""), roots),
            "log_file": redact_path(getattr(resolved, "log_file", ""), roots),
        },
        "update_history": _read_json((product_runtime_roots(create=True) or {})["update_state_root"] / "update_history.json")
        if product_runtime_roots(create=True) is not None
        else None,
        "request": redact_value(request, roots),
        "media_safety": {
            "source_mutation_default_forbidden": True,
            "backend_owns_media_policy": True,
            "support_export_writes_media": False,
            "support_export_deletes_media": False,
        },
    }
    if include_recent_logs:
        desktop_log_path = getattr(service, "desktop_log_path", None)
        payload["recent_logs"] = {
            "desktop": _tail_text_file(Path(desktop_log_path) if desktop_log_path else None, roots, max_bytes=max_log_bytes),
            "pipeline": _tail_text_file(getattr(resolved, "log_file", None), roots, max_bytes=max_log_bytes),
        }
    else:
        payload["recent_logs"] = {"included": False}
    return payload


def write_support_export(
    *,
    service: object,
    resolved: object,
    app_version: str,
    request: dict[str, Any],
    close_readiness: dict[str, Any] | None = None,
) -> Any:
    from mediapipeline.core.kernel.dto_commands import CommandResult

    roots = product_runtime_roots(create=True)
    if roots is None:
        return CommandResult(
            command=SUPPORT_EXPORT_COMMAND,
            ok=False,
            message="%LOCALAPPDATA% is unavailable; support export could not be written.",
            severity="error",
            errors=["LOCALAPPDATA is required for productized diagnostics exports."],
            refresh_hint=MAINTENANCE_REFRESH_HINT,
        )
    payload = support_export_payload(
        service=service,
        resolved=resolved,
        app_version=app_version,
        request=request,
        close_readiness=close_readiness,
    )
    export_path = roots["diagnostics_exports_root"] / f"support_export_{utc_file_stamp()}.json"
    try:
        _write_json_atomically(export_path, payload)
    except OSError as exc:
        return CommandResult(
            command=SUPPORT_EXPORT_COMMAND,
            ok=False,
            message=f"Support export failed: {exc}",
            severity="error",
            errors=[str(exc)],
            refresh_hint=MAINTENANCE_REFRESH_HINT,
        )
    redaction_roots = known_redaction_roots(
        app_root=Path(getattr(resolved, "app_root", "")),
        workspace_root=Path(getattr(resolved, "workspace_root", "")),
        resolved=resolved,
    )
    return CommandResult(
        command=SUPPORT_EXPORT_COMMAND,
        ok=True,
        message="Support export written.",
        severity="info",
        refresh_hint="diagnostics",
        log_paths={"support_export": str(export_path)},
        data={
            "schema_version": SUPPORT_EXPORT_SCHEMA_VERSION,
            "export_path": str(export_path),
            "export_path_redacted": redact_path(export_path, redaction_roots),
            "redaction": payload["redaction"],
            "writes_media": False,
            "deletes_media": False,
        },
    )


__all__ = [
    "PRODUCTIZATION_STATUS_SCHEMA_VERSION",
    "SUPPORT_EXPORT_SCHEMA_VERSION",
    "SUPPORT_EXPORT_COMMAND",
    "productized_app_enabled",
    "product_release_channel",
    "product_appdata_root",
    "product_runtime_roots",
    "prepare_product_runtime",
    "runtime_roots_payload",
    "productization_status_payload",
    "support_export_payload",
    "write_support_export",
    "redact_path",
    "redact_text",
    "redact_value",
]
