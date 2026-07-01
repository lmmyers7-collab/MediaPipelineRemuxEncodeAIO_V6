"""Audit source registry and read-only source metric scanning."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
from typing import Any

from mediapipeline.core.files.constants import MEDIA_FILE_SUFFIXES, SIDECAR_FILE_SUFFIXES
from mediapipeline.core.kernel.dto_base import json_safe
from mediapipeline.core.paths.contracts import ResolvedPaths


AUDIT_SOURCE_REGISTRY_SCHEMA_VERSION = "desktop_audit_sources.v1"
AUDIT_SOURCE_SCAN_SCHEMA_VERSION = "desktop_audit_source_scan.v1"
AUDIT_SOURCE_STATE_DIR_NAME = "Audit"
AUDIT_SOURCE_SCAN_DEFAULT_MAX_ENTRIES = 750_000
AUDIT_SOURCE_PIPELINE_SIDECAR_SUFFIX = ".pipeline.json"


def _utc_now_text() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _text(value: Any) -> str:
    return str(value or "").strip()


def _bool_value(value: Any, *, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if value in (None, ""):
        return default
    return str(value).strip().casefold() in {"1", "true", "yes", "y", "on"}


def _optional_positive_int(value: Any, *, default: int = AUDIT_SOURCE_SCAN_DEFAULT_MAX_ENTRIES) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return parsed if parsed > 0 else default


def _json_load(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig", errors="replace"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _json_dump(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(
        json.dumps(json_safe(dict(payload)), ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    tmp.replace(path)


def _audit_state_root(resolved: ResolvedPaths) -> Path | None:
    if resolved.state_root is not None:
        return resolved.state_root
    if resolved.local_base is not None:
        return resolved.local_base / "State"
    return None


def audit_source_state_paths(resolved: ResolvedPaths) -> dict[str, Path] | None:
    state_root = _audit_state_root(resolved)
    if state_root is None:
        return None
    root = state_root / AUDIT_SOURCE_STATE_DIR_NAME
    return {
        "state_root": state_root,
        "audit_root": root,
        "registry": root / "audit_sources.json",
        "status": root / "audit_source_scan_status.json",
    }


def _source_key(raw_path: str) -> str:
    normalized = raw_path.strip().rstrip("\\/").replace("/", "\\").casefold()
    digest = hashlib.sha256(normalized.encode("utf-8", errors="replace")).hexdigest()[:16]
    return f"src_{digest}"


def _path_from_request(raw_path: Any) -> tuple[Path | None, str | None]:
    path_text = _text(raw_path)
    if not path_text:
        return None, "An audit source path is required."
    path = Path(path_text).expanduser()
    if not path.is_absolute():
        return None, "Audit source paths must be absolute paths."
    try:
        if path.exists() and not path.is_dir():
            return None, "Audit source path exists but is not a folder."
    except OSError as exc:
        return None, f"Audit source path could not be inspected: {exc}"
    return path, None


def _refresh_source_entry(entry: Mapping[str, Any], *, now: str | None = None) -> dict[str, Any]:
    refreshed = dict(entry)
    path_text = _text(refreshed.get("path"))
    warnings: list[str] = []
    exists = False
    is_directory = False
    if path_text:
        path = Path(path_text)
        try:
            exists = path.exists()
            is_directory = exists and path.is_dir()
        except OSError as exc:
            warnings.append(f"Could not inspect source path: {exc}")
    if path_text and not exists:
        warnings.append("Source path is not currently reachable.")
    elif exists and not is_directory:
        warnings.append("Source path is not a folder.")
    refreshed["exists"] = bool(exists)
    refreshed["is_directory"] = bool(is_directory)
    refreshed["warnings"] = warnings
    if now:
        refreshed["updated_at"] = now
    return refreshed


def _load_registry(registry_path: Path) -> dict[str, Any]:
    payload = _json_load(registry_path)
    roots = [item for item in payload.get("roots") or [] if isinstance(item, Mapping)]
    return {
        "schema_version": AUDIT_SOURCE_REGISTRY_SCHEMA_VERSION,
        "updated_at": _text(payload.get("updated_at")),
        "roots": [dict(item) for item in roots],
    }


def _save_registry(registry_path: Path, registry: Mapping[str, Any]) -> None:
    roots = [dict(item) for item in registry.get("roots") or [] if isinstance(item, Mapping)]
    payload = {
        "schema_version": AUDIT_SOURCE_REGISTRY_SCHEMA_VERSION,
        "updated_at": _utc_now_text(),
        "roots": roots,
    }
    _json_dump(registry_path, payload)


def _source_lookup_key(entry: Mapping[str, Any]) -> str:
    source_id = _text(entry.get("source_id"))
    if source_id:
        return source_id
    return _source_key(_text(entry.get("path")))


def _find_source_entry(registry: Mapping[str, Any], request: Mapping[str, Any]) -> tuple[dict[str, Any] | None, str]:
    source_id = _text(request.get("source_id"))
    path_text = _text(request.get("path"))
    if not source_id and path_text:
        source_id = _source_key(path_text)
    for item in registry.get("roots") or []:
        if not isinstance(item, Mapping):
            continue
        if _source_lookup_key(item) == source_id:
            return dict(item), source_id
    return None, source_id


def _matching_source_ids(request: Mapping[str, Any]) -> list[str]:
    raw_values: Iterable[Any]
    if isinstance(request.get("source_ids"), list):
        raw_values = request.get("source_ids") or []
    elif _text(request.get("source_id")):
        raw_values = [request.get("source_id")]
    else:
        raw_values = []
    result: list[str] = []
    seen: set[str] = set()
    for raw in raw_values:
        source_id = _text(raw)
        if not source_id or source_id in seen:
            continue
        seen.add(source_id)
        result.append(source_id)
    return result


def _source_state_from_registry(
    resolved: ResolvedPaths,
    *,
    registry: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    paths = audit_source_state_paths(resolved)
    if paths is None:
        return {
            "schema_version": AUDIT_SOURCE_REGISTRY_SCHEMA_VERSION,
            "available": False,
            "source": "unavailable",
            "state_root": "",
            "audit_root": "",
            "registry_path": "",
            "status_path": "",
            "source_count": 0,
            "enabled_source_count": 0,
            "selected_source_count": 0,
            "media_file_count": 0,
            "sidecar_file_count": 0,
            "folder_count": 0,
            "counts_truncated": False,
            "roots": [],
            "last_scan": {},
            "warnings": ["Audit source state is unavailable because state_root is not configured."],
        }
    loaded = dict(registry or _load_registry(paths["registry"]))
    now = _utc_now_text()
    roots = [
        _refresh_source_entry(item, now=now)
        for item in loaded.get("roots") or []
        if isinstance(item, Mapping)
    ]
    enabled_roots = [item for item in roots if _bool_value(item.get("enabled"), default=True)]
    status_payload = _json_load(paths["status"])
    return {
        "schema_version": AUDIT_SOURCE_REGISTRY_SCHEMA_VERSION,
        "available": True,
        "source": "audit_state",
        "state_root": str(paths["state_root"]),
        "audit_root": str(paths["audit_root"]),
        "registry_path": str(paths["registry"]),
        "status_path": str(paths["status"]),
        "source_count": len(roots),
        "enabled_source_count": len(enabled_roots),
        "selected_source_count": 0,
        "media_file_count": sum(int(item.get("media_file_count") or 0) for item in roots),
        "sidecar_file_count": sum(int(item.get("sidecar_file_count") or 0) for item in roots),
        "folder_count": sum(int(item.get("folder_count") or 0) for item in roots),
        "counts_truncated": any(bool(item.get("counts_truncated")) for item in roots),
        "roots": roots,
        "last_scan": status_payload,
        "warnings": [],
    }


def audit_source_state_payload(resolved: ResolvedPaths) -> dict[str, Any]:
    return _source_state_from_registry(resolved)


def _registry_command_result(
    *,
    ok: bool,
    message: str,
    severity: str,
    resolved: ResolvedPaths,
    registry: Mapping[str, Any] | None = None,
    warnings: list[str] | None = None,
    errors: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "ok": bool(ok),
        "message": message,
        "severity": severity,
        "warnings": list(warnings or []),
        "errors": list(errors or []),
        "data": {"audit_sources": _source_state_from_registry(resolved, registry=registry)},
    }


def update_audit_sources(resolved: ResolvedPaths, request: Mapping[str, Any]) -> dict[str, Any]:
    paths = audit_source_state_paths(resolved)
    if paths is None:
        message = "Audit source state is unavailable because state_root is not configured."
        return {
            "ok": False,
            "message": message,
            "severity": "error",
            "warnings": [],
            "errors": [message],
            "data": {"audit_sources": audit_source_state_payload(resolved)},
        }
    registry = _load_registry(paths["registry"])
    roots = [dict(item) for item in registry.get("roots") or [] if isinstance(item, Mapping)]
    action = _text(request.get("action")).casefold() or "add"
    now = _utc_now_text()
    warnings: list[str] = []

    if action == "add":
        path, error = _path_from_request(request.get("path"))
        if error or path is None:
            return _registry_command_result(
                ok=False,
                message=error or "Audit source path is invalid.",
                severity="error",
                resolved=resolved,
                registry=registry,
                errors=[error or "Audit source path is invalid."],
            )
        path_text = str(path)
        source_id = _source_key(path_text)
        existing_index = next((index for index, item in enumerate(roots) if _source_lookup_key(item) == source_id), None)
        label = _text(request.get("label")) or path.name or path_text
        entry = {
            "source_id": source_id,
            "label": label,
            "path": path_text,
            "enabled": _bool_value(request.get("enabled"), default=True),
            "added_at": now,
            "updated_at": now,
            "scan_status": "not_scanned",
            "last_scan_utc": "",
            "media_file_count": 0,
            "sidecar_file_count": 0,
            "folder_count": 0,
            "counts_truncated": False,
        }
        if existing_index is not None:
            prior = dict(roots[existing_index])
            entry = {
                **prior,
                **entry,
                "added_at": prior.get("added_at") or now,
                "scan_status": prior.get("scan_status") or "not_scanned",
                "last_scan_utc": prior.get("last_scan_utc") or "",
                "media_file_count": int(prior.get("media_file_count") or 0),
                "sidecar_file_count": int(prior.get("sidecar_file_count") or 0),
                "folder_count": int(prior.get("folder_count") or 0),
                "counts_truncated": bool(prior.get("counts_truncated")),
            }
            roots[existing_index] = _refresh_source_entry(entry)
            message = "Audit source updated."
        else:
            roots.append(_refresh_source_entry(entry))
            message = "Audit source added."
        refreshed = roots[existing_index if existing_index is not None else -1]
        warnings.extend(str(item) for item in refreshed.get("warnings") or [])
        registry = {"schema_version": AUDIT_SOURCE_REGISTRY_SCHEMA_VERSION, "updated_at": now, "roots": roots}
        _save_registry(paths["registry"], registry)
        return _registry_command_result(
            ok=True,
            message=message,
            severity="warning" if warnings else "info",
            resolved=resolved,
            registry=registry,
            warnings=warnings,
        )

    if action in {"remove", "delete"}:
        entry, source_id = _find_source_entry({"roots": roots}, request)
        if entry is None:
            message = "Audit source was not found."
            return _registry_command_result(
                ok=False,
                message=message,
                severity="error",
                resolved=resolved,
                registry=registry,
                errors=[message],
            )
        roots = [item for item in roots if _source_lookup_key(item) != source_id]
        registry = {"schema_version": AUDIT_SOURCE_REGISTRY_SCHEMA_VERSION, "updated_at": now, "roots": roots}
        _save_registry(paths["registry"], registry)
        return _registry_command_result(
            ok=True,
            message="Audit source removed.",
            severity="info",
            resolved=resolved,
            registry=registry,
        )

    if action in {"enable", "disable"}:
        entry, source_id = _find_source_entry({"roots": roots}, request)
        if entry is None:
            message = "Audit source was not found."
            return _registry_command_result(
                ok=False,
                message=message,
                severity="error",
                resolved=resolved,
                registry=registry,
                errors=[message],
            )
        enabled = action == "enable"
        for index, item in enumerate(roots):
            if _source_lookup_key(item) == source_id:
                updated = dict(item)
                updated["enabled"] = enabled
                updated["updated_at"] = now
                roots[index] = _refresh_source_entry(updated)
                break
        registry = {"schema_version": AUDIT_SOURCE_REGISTRY_SCHEMA_VERSION, "updated_at": now, "roots": roots}
        _save_registry(paths["registry"], registry)
        return _registry_command_result(
            ok=True,
            message=f"Audit source {'enabled' if enabled else 'disabled'}.",
            severity="info",
            resolved=resolved,
            registry=registry,
        )

    message = f"Unsupported audit source action: {action}"
    return _registry_command_result(
        ok=False,
        message=message,
        severity="error",
        resolved=resolved,
        registry=registry,
        errors=[message],
    )


def _scan_source_entry(entry: Mapping[str, Any], *, max_entries: int, scanned_at: str) -> dict[str, Any]:
    source_id = _source_lookup_key(entry)
    path_text = _text(entry.get("path"))
    root_path = Path(path_text)
    stats: dict[str, Any] = {
        "source_id": source_id,
        "label": _text(entry.get("label")) or path_text,
        "path": path_text,
        "status": "complete",
        "media_file_count": 0,
        "sidecar_file_count": 0,
        "folder_count": 0,
        "counts_truncated": False,
        "error_count": 0,
        "errors": [],
        "warnings": [],
        "scanned_at": scanned_at,
    }
    if not path_text:
        stats["status"] = "blocked"
        stats["error_count"] = 1
        stats["errors"].append("Source path is empty.")
        return stats
    try:
        if not root_path.exists():
            stats["status"] = "unreachable"
            stats["error_count"] = 1
            stats["warnings"].append("Source path is not currently reachable.")
            return stats
        if not root_path.is_dir():
            stats["status"] = "blocked"
            stats["error_count"] = 1
            stats["errors"].append("Source path is not a folder.")
            return stats
    except OSError as exc:
        stats["status"] = "blocked"
        stats["error_count"] = 1
        stats["errors"].append(f"Could not inspect source path: {exc}")
        return stats

    def on_walk_error(exc: OSError) -> None:
        stats["error_count"] = int(stats["error_count"]) + 1
        stats["errors"].append(str(exc))

    observed_entries = 0
    for current_root, dirnames, filenames in os.walk(root_path, topdown=True, onerror=on_walk_error, followlinks=False):
        current_path = Path(current_root)
        kept_dirs: list[str] = []
        for dirname in dirnames:
            candidate = current_path / dirname
            try:
                if candidate.is_symlink():
                    continue
            except OSError:
                continue
            kept_dirs.append(dirname)
        dirnames[:] = sorted(kept_dirs, key=str.casefold)
        filenames = sorted(filenames, key=str.casefold)
        stats["folder_count"] = int(stats["folder_count"]) + 1
        observed_entries += 1
        if observed_entries >= max_entries:
            stats["counts_truncated"] = True
            stats["status"] = "partial"
            stats["warnings"].append(f"Stopped after max_entries={max_entries}.")
            return stats
        for filename in filenames:
            filename_key = filename.casefold()
            suffix = Path(filename).suffix.casefold()
            if suffix in MEDIA_FILE_SUFFIXES:
                stats["media_file_count"] = int(stats["media_file_count"]) + 1
            elif suffix in SIDECAR_FILE_SUFFIXES or filename_key.endswith(AUDIT_SOURCE_PIPELINE_SIDECAR_SUFFIX):
                stats["sidecar_file_count"] = int(stats["sidecar_file_count"]) + 1
            else:
                continue
            observed_entries += 1
            if observed_entries >= max_entries:
                stats["counts_truncated"] = True
                stats["status"] = "partial"
                stats["warnings"].append(f"Stopped after max_entries={max_entries}.")
                return stats
    if stats["error_count"]:
        stats["status"] = "warning"
    return stats


def _selected_source_entries(registry: Mapping[str, Any], request: Mapping[str, Any]) -> tuple[list[dict[str, Any]], list[str]]:
    roots = [dict(item) for item in registry.get("roots") or [] if isinstance(item, Mapping)]
    source_ids = set(_matching_source_ids(request))
    path_text = _text(request.get("path"))
    if source_ids:
        selected = [item for item in roots if _source_lookup_key(item) in source_ids]
        missing = sorted(source_ids - {_source_lookup_key(item) for item in selected})
        if missing:
            return selected, [f"Audit source was not found: {', '.join(missing)}"]
        return selected, []
    if path_text:
        entry, _source_id = _find_source_entry({"roots": roots}, request)
        if entry is None:
            return [], ["Requested audit source was not found. Add the source before scanning it."]
        return [entry], []
    scope = _text(request.get("scope")).casefold() or "enabled"
    if scope == "all":
        return roots, []
    if scope in {"enabled", ""}:
        return [item for item in roots if _bool_value(item.get("enabled"), default=True)], []
    return [], [f"Unsupported audit source scan scope: {scope}"]


def scan_audit_sources(resolved: ResolvedPaths, request: Mapping[str, Any]) -> dict[str, Any]:
    paths = audit_source_state_paths(resolved)
    if paths is None:
        message = "Audit source scan is unavailable because state_root is not configured."
        return {
            "ok": False,
            "message": message,
            "severity": "error",
            "warnings": [],
            "errors": [message],
            "data": {"audit_sources": audit_source_state_payload(resolved)},
        }
    registry = _load_registry(paths["registry"])
    entries, selection_errors = _selected_source_entries(registry, request)
    if selection_errors:
        message = selection_errors[0]
        return {
            "ok": False,
            "message": message,
            "severity": "error",
            "warnings": [],
            "errors": selection_errors,
            "data": {"audit_sources": _source_state_from_registry(resolved, registry=registry)},
        }
    if not entries:
        message = "No enabled Audit sources are configured."
        return {
            "ok": False,
            "message": message,
            "severity": "warning",
            "warnings": [message],
            "errors": [],
            "data": {"audit_sources": _source_state_from_registry(resolved, registry=registry)},
        }

    scanned_at = _utc_now_text()
    max_entries = _optional_positive_int(request.get("max_entries"))
    root_results = [
        _scan_source_entry(entry, max_entries=max_entries, scanned_at=scanned_at)
        for entry in entries
    ]

    roots = [dict(item) for item in registry.get("roots") or [] if isinstance(item, Mapping)]
    stats_by_id = {str(item.get("source_id") or ""): item for item in root_results}
    for index, item in enumerate(roots):
        source_id = _source_lookup_key(item)
        stats = stats_by_id.get(source_id)
        if not stats:
            continue
        updated = dict(item)
        updated["source_id"] = source_id
        updated["scan_status"] = stats.get("status")
        updated["last_scan_utc"] = scanned_at
        updated["media_file_count"] = int(stats.get("media_file_count") or 0)
        updated["sidecar_file_count"] = int(stats.get("sidecar_file_count") or 0)
        updated["folder_count"] = int(stats.get("folder_count") or 0)
        updated["counts_truncated"] = bool(stats.get("counts_truncated"))
        updated["updated_at"] = scanned_at
        roots[index] = _refresh_source_entry(updated)
    registry = {"schema_version": AUDIT_SOURCE_REGISTRY_SCHEMA_VERSION, "updated_at": scanned_at, "roots": roots}
    _save_registry(paths["registry"], registry)

    total_media = sum(int(item.get("media_file_count") or 0) for item in root_results)
    total_sidecars = sum(int(item.get("sidecar_file_count") or 0) for item in root_results)
    total_folders = sum(int(item.get("folder_count") or 0) for item in root_results)
    total_errors = sum(int(item.get("error_count") or 0) for item in root_results)
    truncated = any(bool(item.get("counts_truncated")) for item in root_results)
    status_payload = {
        "schema_version": AUDIT_SOURCE_SCAN_SCHEMA_VERSION,
        "status": "partial" if truncated else "warning" if total_errors else "complete",
        "started_at": scanned_at,
        "completed_at": _utc_now_text(),
        "source_count": len(root_results),
        "media_file_count": total_media,
        "sidecar_file_count": total_sidecars,
        "folder_count": total_folders,
        "error_count": total_errors,
        "counts_truncated": truncated,
        "roots": root_results,
    }
    _json_dump(paths["status"], status_payload)
    state = _source_state_from_registry(resolved, registry=registry)
    message = f"Audit source scan counted {total_media} media file(s), {total_sidecars} sidecar file(s), and {total_folders} folder(s) across {len(root_results)} source(s)."
    return {
        "ok": True,
        "message": message,
        "severity": "warning" if total_errors or truncated else "info",
        "warnings": [
            warning
            for item in root_results
            for warning in [*list(item.get("warnings") or []), *list(item.get("errors") or [])]
            if _text(warning)
        ],
        "errors": [],
        "data": {
            "scan": status_payload,
            "audit_sources": state,
        },
    }


def _dedupe_text_values(values: Iterable[Any]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = _text(value)
        key = text.replace("/", "\\").rstrip("\\").casefold()
        if not text or key in seen:
            continue
        seen.add(key)
        result.append(text)
    return result


def _library_roots_from_metadata(metadata: Mapping[str, Any]) -> list[str]:
    raw_roots = metadata.get("library_roots")
    if isinstance(raw_roots, list):
        values: Iterable[Any] = raw_roots
    else:
        values = []
    roots = _dedupe_text_values(values)
    if roots:
        return roots
    return _dedupe_text_values([metadata.get("library_root")])


def _source_ids_for_library_roots(
    registry: Mapping[str, Any],
    library_roots: Iterable[Any],
) -> tuple[list[str], list[str]]:
    configured_ids = {
        _source_lookup_key(item)
        for item in registry.get("roots") or []
        if isinstance(item, Mapping)
    }
    source_ids: list[str] = []
    missing_paths: list[str] = []
    seen: set[str] = set()
    for library_root in _dedupe_text_values(library_roots):
        source_id = _source_key(library_root)
        if source_id not in configured_ids:
            missing_paths.append(library_root)
            continue
        if source_id in seen:
            continue
        seen.add(source_id)
        source_ids.append(source_id)
    return source_ids, missing_paths


def sync_audit_sources_from_completed_audit(
    resolved: ResolvedPaths,
    *,
    metadata: Mapping[str, Any] | None = None,
    library_roots: Iterable[Any] | None = None,
) -> dict[str, Any]:
    """Refresh configured audit-source metrics after a successful audit run.

    The audit process itself writes report files but the Locations table reads
    from the audit-source registry. Reuse the existing read-only source scan so
    media, sidecar, and folder counts stay consistent with the manual Scan
    buttons.
    """
    paths = audit_source_state_paths(resolved)
    if paths is None:
        message = "Audit source metrics sync is unavailable because state_root is not configured."
        return {
            "ok": False,
            "message": message,
            "severity": "error",
            "warnings": [],
            "errors": [message],
            "data": {"audit_sources": audit_source_state_payload(resolved)},
        }
    registry = _load_registry(paths["registry"])
    roots = _dedupe_text_values(library_roots or [])
    if not roots and metadata is not None:
        roots = _library_roots_from_metadata(metadata)
    source_ids: list[str] = []
    missing_paths: list[str] = []
    if roots:
        source_ids, missing_paths = _source_ids_for_library_roots(registry, roots)
        if not source_ids:
            message = "Completed audit did not match any configured Audit source rows."
            return {
                "ok": False,
                "message": message,
                "severity": "warning",
                "warnings": [*missing_paths, message],
                "errors": [],
                "data": {"audit_sources": _source_state_from_registry(resolved, registry=registry)},
            }
    request: dict[str, Any] = {"source_ids": source_ids} if source_ids else {"scope": "enabled"}
    result = scan_audit_sources(resolved, request)
    if missing_paths:
        warnings = list(result.get("warnings") or [])
        warnings.extend(f"Completed audit root is not configured as an Audit source row: {path}" for path in missing_paths)
        result = {**result, "warnings": warnings, "severity": "warning"}
    return result


class AuditSourceMetricsServiceMixin:
    def sync_audit_sources_after_process_exit(
        self,
        proc: Any,
        *,
        resolved: ResolvedPaths | None,
        job_kind: str,
        return_code: int | None,
        metadata: Mapping[str, Any] | None = None,
    ) -> None:
        if str(job_kind or "").strip().casefold() != "audit":
            return
        if return_code != 0 or resolved is None:
            return
        result = sync_audit_sources_from_completed_audit(resolved, metadata=metadata)
        logger = getattr(self, "logger", None)
        message = str(result.get("message") or "Audit source metrics sync finished.")
        if bool(result.get("ok")):
            if logger is not None and hasattr(logger, "info"):
                logger.info("Synced Audit source metrics after audit PID %s completed: %s", getattr(proc, "pid", ""), message)
        elif logger is not None and hasattr(logger, "warning"):
            logger.warning("Audit source metrics sync after audit PID %s did not complete: %s", getattr(proc, "pid", ""), message)


__all__ = [
    "AuditSourceMetricsServiceMixin",
    "AUDIT_SOURCE_REGISTRY_SCHEMA_VERSION",
    "AUDIT_SOURCE_SCAN_SCHEMA_VERSION",
    "audit_source_state_payload",
    "audit_source_state_paths",
    "scan_audit_sources",
    "sync_audit_sources_from_completed_audit",
    "update_audit_sources",
]
