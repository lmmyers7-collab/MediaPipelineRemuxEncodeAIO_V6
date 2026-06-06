"""Metrics source registry and recursive sidecar backfill support."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
import hashlib
import json
import os
from pathlib import Path
from typing import Any

from mediapipeline.core.completed.manifest import OUTPUT_PROOF_DEFERRED
from mediapipeline.core.kernel.dto_base import json_safe
from mediapipeline.desktop.models import CompletedJobRecord, ResolvedPaths

from .policy import utc_now_text


METRICS_SOURCE_REGISTRY_SCHEMA_VERSION = "desktop_metrics_sources.v1"
METRICS_BACKFILL_SCHEMA_VERSION = "desktop_metrics_backfill.v1"
METRICS_BACKFILL_CACHE_SCHEMA_VERSION = "desktop_metrics_sidecar_backfill.v1"
METRICS_STATE_DIR_NAME = "Metrics"
METRICS_SIDECAR_SUFFIX = ".pipeline.json"


def _text(value: Any) -> str:
    return str(value or "").strip()


def _bool_value(value: Any, *, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if value in (None, ""):
        return default
    return str(value).strip().casefold() in {"1", "true", "yes", "y", "on"}


def _optional_positive_int(value: Any) -> int | None:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed > 0 else None


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


def _write_jsonl(path: Path, entries: Iterable[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    lines = [
        json.dumps(json_safe(dict(entry)), ensure_ascii=False, sort_keys=True, allow_nan=False)
        for entry in entries
    ]
    tmp.write_text(("\n".join(lines) + "\n") if lines else "", encoding="utf-8")
    tmp.replace(path)


def _metrics_state_root(resolved: ResolvedPaths) -> Path | None:
    if resolved.state_root is not None:
        return resolved.state_root
    if resolved.local_base is not None:
        return resolved.local_base / "State"
    return None


def metrics_state_paths(resolved: ResolvedPaths) -> dict[str, Path] | None:
    state_root = _metrics_state_root(resolved)
    if state_root is None:
        return None
    root = state_root / METRICS_STATE_DIR_NAME
    return {
        "state_root": state_root,
        "metrics_root": root,
        "registry": root / "metrics_sources.json",
        "cache": root / "metrics_sidecar_backfill.jsonl",
        "status": root / "metrics_backfill_status.json",
    }


def _source_key(raw_path: str) -> str:
    normalized = raw_path.strip().rstrip("\\/").casefold()
    digest = hashlib.sha256(normalized.encode("utf-8", errors="replace")).hexdigest()[:16]
    return f"src_{digest}"


def _path_from_request(raw_path: Any) -> tuple[Path | None, str | None]:
    path_text = _text(raw_path)
    if not path_text:
        return None, "A metrics source path is required."
    path = Path(path_text).expanduser()
    if not path.is_absolute():
        return None, "Metrics source paths must be absolute paths."
    try:
        if path.exists() and not path.is_dir():
            return None, "Metrics source path exists but is not a folder."
    except OSError as exc:
        return None, f"Metrics source path could not be inspected: {exc}"
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
        "schema_version": METRICS_SOURCE_REGISTRY_SCHEMA_VERSION,
        "updated_at": _text(payload.get("updated_at")),
        "roots": [dict(item) for item in roots],
    }


def _save_registry(registry_path: Path, registry: Mapping[str, Any]) -> None:
    roots = [dict(item) for item in registry.get("roots") or [] if isinstance(item, Mapping)]
    payload = {
        "schema_version": METRICS_SOURCE_REGISTRY_SCHEMA_VERSION,
        "updated_at": utc_now_text(),
        "roots": roots,
    }
    _json_dump(registry_path, payload)


def _read_cache_entries(cache_path: Path) -> list[dict[str, Any]]:
    if not cache_path.exists():
        return []
    entries: list[dict[str, Any]] = []
    try:
        raw = cache_path.read_text(encoding="utf-8-sig", errors="replace")
    except OSError:
        return []
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            parsed = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            entries.append(parsed)
    return entries


def _count_cache_entries(cache_path: Path) -> int:
    if not cache_path.exists():
        return 0
    count = 0
    try:
        with cache_path.open("r", encoding="utf-8-sig", errors="replace") as handle:
            for line in handle:
                if line.strip():
                    count += 1
    except OSError:
        return 0
    return count


def _source_state_from_registry(
    resolved: ResolvedPaths,
    *,
    registry: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    paths = metrics_state_paths(resolved)
    if paths is None:
        return {
            "schema_version": METRICS_SOURCE_REGISTRY_SCHEMA_VERSION,
            "available": False,
            "source": "unavailable",
            "state_root": "",
            "metrics_root": "",
            "registry_path": "",
            "cache_path": "",
            "status_path": "",
            "source_count": 0,
            "enabled_source_count": 0,
            "cache_record_count": 0,
            "enabled_cache_record_count": 0,
            "roots": [],
            "last_backfill": {},
            "warnings": ["Metrics source state is unavailable because state_root is not configured."],
        }
    loaded = dict(registry or _load_registry(paths["registry"]))
    now = utc_now_text()
    roots = [
        _refresh_source_entry(item, now=now)
        for item in loaded.get("roots") or []
        if isinstance(item, Mapping)
    ]
    enabled_ids = {str(item.get("source_id") or "") for item in roots if _bool_value(item.get("enabled"), default=True)}
    cache_entries = _read_cache_entries(paths["cache"])
    enabled_cache_count = sum(1 for item in cache_entries if str(item.get("source_id") or "") in enabled_ids)
    status_payload = _json_load(paths["status"])
    return {
        "schema_version": METRICS_SOURCE_REGISTRY_SCHEMA_VERSION,
        "available": True,
        "source": "metrics_state",
        "state_root": str(paths["state_root"]),
        "metrics_root": str(paths["metrics_root"]),
        "registry_path": str(paths["registry"]),
        "cache_path": str(paths["cache"]),
        "status_path": str(paths["status"]),
        "source_count": len(roots),
        "enabled_source_count": len(enabled_ids),
        "cache_record_count": len(cache_entries),
        "enabled_cache_record_count": enabled_cache_count,
        "roots": roots,
        "last_backfill": status_payload,
        "warnings": [],
    }


def metrics_source_state_payload(resolved: ResolvedPaths) -> dict[str, Any]:
    return _source_state_from_registry(resolved)


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
        "data": {"source_backfill": _source_state_from_registry(resolved, registry=registry)},
    }


def update_metrics_sources(resolved: ResolvedPaths, request: Mapping[str, Any]) -> dict[str, Any]:
    paths = metrics_state_paths(resolved)
    if paths is None:
        message = "Metrics source state is unavailable because state_root is not configured."
        return {
            "ok": False,
            "message": message,
            "severity": "error",
            "warnings": [],
            "errors": [message],
            "data": {"source_backfill": metrics_source_state_payload(resolved)},
        }
    registry = _load_registry(paths["registry"])
    roots = [dict(item) for item in registry.get("roots") or [] if isinstance(item, Mapping)]
    action = _text(request.get("action")).casefold() or "add"
    now = utc_now_text()
    warnings: list[str] = []

    if action == "add":
        path, error = _path_from_request(request.get("path"))
        if error or path is None:
            return _registry_command_result(
                ok=False,
                message=error or "Metrics source path is invalid.",
                severity="error",
                resolved=resolved,
                registry=registry,
                errors=[error or "Metrics source path is invalid."],
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
            "last_scan_at": "",
            "last_scan_status": "never",
            "last_scan_sidecar_count": 0,
            "last_scan_loaded_count": 0,
            "last_scan_error_count": 0,
        }
        if existing_index is not None:
            prior = dict(roots[existing_index])
            entry = {
                **prior,
                **entry,
                "added_at": prior.get("added_at") or now,
                "last_scan_at": prior.get("last_scan_at") or "",
                "last_scan_status": prior.get("last_scan_status") or "never",
                "last_scan_sidecar_count": prior.get("last_scan_sidecar_count") or 0,
                "last_scan_loaded_count": prior.get("last_scan_loaded_count") or 0,
                "last_scan_error_count": prior.get("last_scan_error_count") or 0,
            }
            roots[existing_index] = _refresh_source_entry(entry)
            message = "Metrics source updated."
        else:
            roots.append(_refresh_source_entry(entry))
            message = "Metrics source added."
        refreshed = roots[existing_index if existing_index is not None else -1]
        warnings.extend(str(item) for item in refreshed.get("warnings") or [])
        registry = {"schema_version": METRICS_SOURCE_REGISTRY_SCHEMA_VERSION, "updated_at": now, "roots": roots}
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
            message = "Metrics source was not found."
            return _registry_command_result(
                ok=False,
                message=message,
                severity="error",
                resolved=resolved,
                registry=registry,
                errors=[message],
            )
        roots = [item for item in roots if _source_lookup_key(item) != source_id]
        registry = {"schema_version": METRICS_SOURCE_REGISTRY_SCHEMA_VERSION, "updated_at": now, "roots": roots}
        _save_registry(paths["registry"], registry)
        kept_cache = [item for item in _read_cache_entries(paths["cache"]) if str(item.get("source_id") or "") != source_id]
        _write_jsonl(paths["cache"], kept_cache)
        return _registry_command_result(
            ok=True,
            message="Metrics source removed.",
            severity="info",
            resolved=resolved,
            registry=registry,
        )

    if action in {"enable", "disable"}:
        entry, source_id = _find_source_entry({"roots": roots}, request)
        if entry is None:
            message = "Metrics source was not found."
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
        registry = {"schema_version": METRICS_SOURCE_REGISTRY_SCHEMA_VERSION, "updated_at": now, "roots": roots}
        _save_registry(paths["registry"], registry)
        return _registry_command_result(
            ok=True,
            message=f"Metrics source {'enabled' if enabled else 'disabled'}.",
            severity="info",
            resolved=resolved,
            registry=registry,
        )

    message = f"Unsupported metrics source action: {action}"
    return _registry_command_result(
        ok=False,
        message=message,
        severity="error",
        resolved=resolved,
        registry=registry,
        errors=[message],
    )


def _scan_source_entry(entry: Mapping[str, Any], *, max_sidecars: int | None, scanned_at: str) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    source_id = _source_lookup_key(entry)
    path_text = _text(entry.get("path"))
    root_path = Path(path_text)
    stats: dict[str, Any] = {
        "source_id": source_id,
        "label": _text(entry.get("label")) or path_text,
        "path": path_text,
        "status": "complete",
        "sidecar_count": 0,
        "loaded_count": 0,
        "error_count": 0,
        "errors": [],
        "warnings": [],
        "scanned_at": scanned_at,
    }
    if not path_text:
        stats["status"] = "blocked"
        stats["error_count"] = 1
        stats["errors"].append("Source path is empty.")
        return stats, []
    try:
        if not root_path.exists():
            stats["status"] = "unreachable"
            stats["error_count"] = 1
            stats["warnings"].append("Source path is not currently reachable.")
            return stats, []
        if not root_path.is_dir():
            stats["status"] = "blocked"
            stats["error_count"] = 1
            stats["errors"].append("Source path is not a folder.")
            return stats, []
    except OSError as exc:
        stats["status"] = "blocked"
        stats["error_count"] = 1
        stats["errors"].append(f"Could not inspect source path: {exc}")
        return stats, []

    cache_entries: list[dict[str, Any]] = []

    def on_walk_error(exc: OSError) -> None:
        stats["error_count"] = int(stats["error_count"]) + 1
        stats["errors"].append(str(exc))

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
        dirnames[:] = kept_dirs
        for filename in filenames:
            if not filename.casefold().endswith(METRICS_SIDECAR_SUFFIX):
                continue
            if max_sidecars is not None and int(stats["sidecar_count"]) >= max_sidecars:
                stats["status"] = "partial"
                stats["warnings"].append(f"Stopped after max_sidecars={max_sidecars}.")
                return stats, cache_entries
            sidecar_path = current_path / filename
            stats["sidecar_count"] = int(stats["sidecar_count"]) + 1
            try:
                payload = json.loads(sidecar_path.read_text(encoding="utf-8-sig", errors="replace"))
            except (OSError, json.JSONDecodeError) as exc:
                stats["error_count"] = int(stats["error_count"]) + 1
                stats["errors"].append(f"{sidecar_path}: {exc}")
                continue
            if not isinstance(payload, dict):
                stats["error_count"] = int(stats["error_count"]) + 1
                stats["errors"].append(f"{sidecar_path}: sidecar payload is not an object")
                continue
            stats["loaded_count"] = int(stats["loaded_count"]) + 1
            cache_entries.append(
                {
                    "schema_version": METRICS_BACKFILL_CACHE_SCHEMA_VERSION,
                    "source_id": source_id,
                    "source_root": path_text,
                    "source_label": _text(entry.get("label")) or path_text,
                    "sidecar_path": str(sidecar_path),
                    "scanned_at": scanned_at,
                    "payload": json_safe(payload),
                }
            )
    if stats["error_count"]:
        stats["status"] = "warning"
    return stats, cache_entries


def _selected_source_entries(registry: Mapping[str, Any], request: Mapping[str, Any]) -> tuple[list[dict[str, Any]], list[str]]:
    roots = [dict(item) for item in registry.get("roots") or [] if isinstance(item, Mapping)]
    scope = _text(request.get("scope")).casefold() or "enabled"
    if _text(request.get("source_id")) or _text(request.get("path")):
        entry, _source_id = _find_source_entry({"roots": roots}, request)
        if entry is None:
            return [], ["Requested metrics source was not found. Add the source before scanning it."]
        return [entry], []
    if scope == "all":
        return roots, []
    if scope in {"enabled", ""}:
        return [item for item in roots if _bool_value(item.get("enabled"), default=True)], []
    return [], [f"Unsupported metrics backfill scope: {scope}"]


def run_metrics_sidecar_backfill(resolved: ResolvedPaths, request: Mapping[str, Any]) -> dict[str, Any]:
    paths = metrics_state_paths(resolved)
    if paths is None:
        message = "Metrics backfill is unavailable because state_root is not configured."
        return {
            "ok": False,
            "message": message,
            "severity": "error",
            "warnings": [],
            "errors": [message],
            "data": {"source_backfill": metrics_source_state_payload(resolved)},
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
            "data": {"source_backfill": _source_state_from_registry(resolved, registry=registry)},
        }
    if not entries:
        message = "No enabled Metrics sources are configured."
        return {
            "ok": False,
            "message": message,
            "severity": "warning",
            "warnings": [message],
            "errors": [],
            "data": {"source_backfill": _source_state_from_registry(resolved, registry=registry)},
        }

    scanned_at = utc_now_text()
    max_sidecars = _optional_positive_int(request.get("max_sidecars"))
    scanned_source_ids: set[str] = set()
    scanned_entries: list[dict[str, Any]] = []
    root_results: list[dict[str, Any]] = []
    for entry in entries:
        source_id = _source_lookup_key(entry)
        scanned_source_ids.add(source_id)
        stats, cache_entries = _scan_source_entry(entry, max_sidecars=max_sidecars, scanned_at=scanned_at)
        root_results.append(stats)
        scanned_entries.extend(cache_entries)

    prior_cache = _read_cache_entries(paths["cache"])
    kept_cache = [item for item in prior_cache if str(item.get("source_id") or "") not in scanned_source_ids]
    _write_jsonl(paths["cache"], [*kept_cache, *scanned_entries])

    roots = [dict(item) for item in registry.get("roots") or [] if isinstance(item, Mapping)]
    stats_by_id = {str(item.get("source_id") or ""): item for item in root_results}
    for index, item in enumerate(roots):
        source_id = _source_lookup_key(item)
        stats = stats_by_id.get(source_id)
        if not stats:
            continue
        updated = dict(item)
        updated["source_id"] = source_id
        updated["last_scan_at"] = scanned_at
        updated["last_scan_status"] = stats.get("status")
        updated["last_scan_sidecar_count"] = int(stats.get("sidecar_count") or 0)
        updated["last_scan_loaded_count"] = int(stats.get("loaded_count") or 0)
        updated["last_scan_error_count"] = int(stats.get("error_count") or 0)
        updated["updated_at"] = scanned_at
        roots[index] = _refresh_source_entry(updated)
    registry = {"schema_version": METRICS_SOURCE_REGISTRY_SCHEMA_VERSION, "updated_at": scanned_at, "roots": roots}
    _save_registry(paths["registry"], registry)

    total_sidecars = sum(int(item.get("sidecar_count") or 0) for item in root_results)
    total_loaded = sum(int(item.get("loaded_count") or 0) for item in root_results)
    total_errors = sum(int(item.get("error_count") or 0) for item in root_results)
    status_payload = {
        "schema_version": METRICS_BACKFILL_SCHEMA_VERSION,
        "status": "warning" if total_errors else "complete",
        "started_at": scanned_at,
        "completed_at": utc_now_text(),
        "source_count": len(root_results),
        "sidecar_count": total_sidecars,
        "loaded_count": total_loaded,
        "error_count": total_errors,
        "cache_path": str(paths["cache"]),
        "roots": root_results,
    }
    _json_dump(paths["status"], status_payload)
    state = _source_state_from_registry(resolved, registry=registry)
    message = f"Metrics sidecar backfill scanned {len(root_results)} source(s) and loaded {total_loaded} sidecar record(s)."
    return {
        "ok": True,
        "message": message,
        "severity": "warning" if total_errors else "info",
        "warnings": [
            warning
            for item in root_results
            for warning in [*list(item.get("warnings") or []), *list(item.get("errors") or [])]
            if _text(warning)
        ],
        "errors": [],
        "data": {
            "backfill": status_payload,
            "source_backfill": state,
        },
    }


def load_metrics_backfill_records(
    resolved: ResolvedPaths,
    warnings: list[str] | None = None,
) -> tuple[list[CompletedJobRecord], dict[str, Any]]:
    state = metrics_source_state_payload(resolved)
    paths = metrics_state_paths(resolved)
    if paths is None:
        return [], state
    enabled_ids = {
        str(item.get("source_id") or "")
        for item in state.get("roots") or []
        if isinstance(item, Mapping) and _bool_value(item.get("enabled"), default=True)
    }
    records: list[CompletedJobRecord] = []
    skipped = 0
    for entry in _read_cache_entries(paths["cache"]):
        source_id = _text(entry.get("source_id"))
        if source_id not in enabled_ids:
            skipped += 1
            continue
        payload = entry.get("payload")
        if not isinstance(payload, Mapping):
            skipped += 1
            continue
        sidecar_path_text = _text(entry.get("sidecar_path"))
        record_payload = dict(payload)
        record_payload["_diagnostics_output_proof"] = OUTPUT_PROOF_DEFERRED
        record_payload["_metrics_backfill_source_id"] = source_id
        record_payload["_metrics_backfill_source_root"] = _text(entry.get("source_root"))
        record_payload["_metrics_backfill_sidecar_path"] = sidecar_path_text
        record_payload["_metrics_backfill_loaded_at"] = utc_now_text()
        records.append(CompletedJobRecord(sidecar_path=Path(sidecar_path_text or "."), payload=record_payload))
    state["cache_record_count"] = _count_cache_entries(paths["cache"])
    state["enabled_cache_record_count"] = len(records)
    state["skipped_cache_record_count"] = skipped
    if skipped and warnings is not None:
        warnings.append(f"Metrics sidecar backfill skipped {skipped} cached record(s) from disabled or invalid sources.")
    return records, state


__all__ = [
    "METRICS_BACKFILL_CACHE_SCHEMA_VERSION",
    "METRICS_BACKFILL_SCHEMA_VERSION",
    "METRICS_SOURCE_REGISTRY_SCHEMA_VERSION",
    "load_metrics_backfill_records",
    "metrics_source_state_payload",
    "metrics_state_paths",
    "run_metrics_sidecar_backfill",
    "update_metrics_sources",
]
