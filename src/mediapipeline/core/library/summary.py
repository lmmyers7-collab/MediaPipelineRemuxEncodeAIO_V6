"""Read-only LibraryProfiles scan summary evidence."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from mediapipeline.core.config.library_profiles import effective_library_profiles_from_config
from mediapipeline.core.queue.source_inventory import utc_now_iso


LIBRARY_SUMMARY_SCHEMA_VERSION = "desktop_libraries_summary.v1"


def build_library_summary(
    config: Mapping[str, Any],
    queue_scan_status: Mapping[str, Any] | None = None,
    source_inventory: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    config_map = dict(config or {})
    scan_status = dict(queue_scan_status or {})
    inventory = dict(source_inventory or {})
    warnings: list[str] = []
    try:
        profiles = effective_library_profiles_from_config(config_map)
    except Exception as exc:
        profiles = []
        warnings.append(f"LibraryProfiles could not be normalized: {exc}")

    has_inventory = _has_inventory_counts(inventory)
    rows = [
        _library_summary_row(config_map, profile, scan_status, inventory, has_inventory)
        for profile in profiles
    ]
    warnings.extend(str(item) for item in inventory.get("warnings") or [] if str(item).strip())
    warnings.extend(str(item) for item in scan_status.get("warnings") or [] if str(item).strip())
    warnings.extend(str(item) for item in scan_status.get("errors") or [] if str(item).strip())

    enabled_rows = [row for row in rows if row.get("enabled")]
    media_total = sum(int(row.get("media_file_count") or 0) for row in rows if row.get("media_file_count") is not None)
    sidecar_total = sum(int(row.get("sidecar_file_count") or 0) for row in rows if row.get("sidecar_file_count") is not None)
    stale_or_unknown = sum(
        1
        for row in enabled_rows
        if str(row.get("scan_status") or "") in {"not_scanned", "partial", "error", "unavailable"}
    )
    counts_truncated = any(bool(row.get("counts_truncated")) for row in rows)
    if counts_truncated:
        warnings.append("One or more source inventory counts are partial because the scan hit its row limit.")

    return _base_payload(
        rows=rows,
        totals={
            "library_count": len(rows),
            "enabled_count": len(enabled_rows),
            "media_file_count": media_total,
            "sidecar_file_count": sidecar_total,
            "stale_or_unknown_scan_count": stale_or_unknown,
            "counts_truncated": counts_truncated,
        },
        library_count=len(rows),
        enabled_count=len(enabled_rows),
        media_file_count=media_total,
        sidecar_file_count=sidecar_total,
        stale_or_unknown_scan_count=stale_or_unknown,
        counts_truncated=counts_truncated,
        queue_scan_status=_bounded_status(scan_status),
        source_inventory_status=str(inventory.get("status") or "not_loaded"),
        source_inventory_schema=str(inventory.get("schema_version") or ""),
        produced_at_utc=utc_now_iso(),
        summary_lines=[
            f"Saved LibraryProfiles: {len(rows)}.",
            f"Enabled libraries: {len(enabled_rows)}.",
            "Media and sidecar counts come from backend queue source scan artifacts.",
            "The summary is read-only and does not scan, save settings, launch work, or touch media files.",
        ],
        warnings=_dedupe(warnings),
    )


def _base_payload(**fields: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "schema_version": LIBRARY_SUMMARY_SCHEMA_VERSION,
        "evidence_authority": "backend",
        "read_only": True,
        "mutation_enabled": False,
        "effects": [],
        "guardrail": (
            "Evidence only. No launch, scan, settings save, queue mutation, "
            "filesystem mutation, media processing, publish, drain, or delete is performed."
        ),
    }
    payload.update(fields)
    return payload


def _library_summary_row(
    config: Mapping[str, Any],
    profile: Mapping[str, Any],
    queue_scan_status: Mapping[str, Any],
    source_inventory: Mapping[str, Any],
    has_inventory: bool,
) -> dict[str, Any]:
    profile_id = _text(profile.get("library_id") or profile.get("id")) or "library"
    source_path = _text(profile.get("effective_source_root") or profile.get("source_path"))
    source_key = _inventory_source_key(config, profile_id, source_path, source_inventory)
    media_count = _source_count(source_inventory, "source_key_counts", source_key, has_inventory)
    sidecar_count = _source_count(source_inventory, "sidecar_source_key_counts", source_key, has_inventory)
    counts_truncated = bool(source_inventory.get("rows_truncated") or source_inventory.get("sidecar_counts_truncated"))
    scan_status = _row_scan_status(queue_scan_status, source_inventory, has_inventory, counts_truncated)
    return {
        "library_id": profile_id,
        "name": _text(profile.get("name")) or _default_name(profile_id),
        "designation": _text(profile.get("designation")) or "auto",
        "enabled": profile.get("enabled", True) is not False,
        "source_path": source_path,
        "media_file_count": media_count,
        "sidecar_file_count": sidecar_count,
        "last_scan_utc": _last_scan_utc(queue_scan_status, source_inventory, scan_status),
        "scan_status": scan_status,
        "source_key": source_key,
        "counts_truncated": counts_truncated,
        "warnings": _row_warnings(source_path, scan_status, counts_truncated),
    }


def _row_scan_status(
    queue_scan_status: Mapping[str, Any],
    source_inventory: Mapping[str, Any],
    has_inventory: bool,
    counts_truncated: bool,
) -> str:
    queue_status = _text(queue_scan_status.get("status")).casefold()
    inventory_status = _text(source_inventory.get("status")).casefold()
    if queue_scan_status.get("running") is True or queue_status == "running":
        return "scanning"
    if queue_status in {"failed", "error", "unavailable"} or inventory_status in {"failed", "error", "unavailable"}:
        return "error"
    if not has_inventory:
        return "not_scanned"
    if counts_truncated:
        return "partial"
    return "complete"


def _last_scan_utc(
    queue_scan_status: Mapping[str, Any],
    source_inventory: Mapping[str, Any],
    scan_status: str,
) -> str:
    if scan_status == "not_scanned":
        return ""
    if scan_status == "scanning":
        return _first_text(
            queue_scan_status.get("updated_at_utc"),
            queue_scan_status.get("started_at_utc"),
            source_inventory.get("produced_at_utc"),
        )
    return _first_text(
        queue_scan_status.get("completed_at_utc"),
        source_inventory.get("produced_at_utc"),
        queue_scan_status.get("updated_at_utc"),
    )


def _has_inventory_counts(source_inventory: Mapping[str, Any]) -> bool:
    status = _text(source_inventory.get("status")).casefold()
    if status in {"", "not_loaded", "unavailable", "failed", "error"}:
        return False
    if not source_inventory.get("schema_version"):
        return False
    return isinstance(source_inventory.get("source_key_counts"), Mapping) or isinstance(
        source_inventory.get("sidecar_source_key_counts"),
        Mapping,
    )


def _source_count(
    source_inventory: Mapping[str, Any],
    field: str,
    source_key: str,
    has_inventory: bool,
) -> int | None:
    if not has_inventory:
        return None
    counts = source_inventory.get(field)
    if not isinstance(counts, Mapping):
        return 0
    return _int_value(counts.get(source_key), default=0)


def _inventory_source_key(
    config: Mapping[str, Any],
    profile_id: str,
    source_path: str,
    source_inventory: Mapping[str, Any],
) -> str:
    canonical = f"LibraryProfiles:{profile_id}"
    count_keys = _count_keys(source_inventory)
    if canonical in count_keys:
        return canonical
    if profile_id == "movies" and _path_key(source_path) == _path_key(config.get("SourceMovies")):
        return "SourceMovies"
    if profile_id == "tv" and _path_key(source_path) == _path_key(config.get("SourceTV")):
        return "SourceTV"
    root_key = _inventory_root_key_for_path(source_inventory, source_path)
    return root_key or canonical


def _count_keys(source_inventory: Mapping[str, Any]) -> set[str]:
    keys: set[str] = set()
    for field in ("source_key_counts", "sidecar_source_key_counts"):
        counts = source_inventory.get(field)
        if isinstance(counts, Mapping):
            keys.update(str(key) for key in counts.keys())
    return keys


def _inventory_root_key_for_path(source_inventory: Mapping[str, Any], source_path: str) -> str:
    source_key = ""
    target_key = _path_key(source_path)
    if not target_key:
        return ""
    for root in source_inventory.get("roots") or []:
        if not isinstance(root, Mapping):
            continue
        if _path_key(root.get("path")) == target_key:
            source_key = _text(root.get("source_key"))
            break
    return source_key


def _row_warnings(source_path: str, scan_status: str, counts_truncated: bool) -> list[str]:
    warnings: list[str] = []
    if not source_path:
        warnings.append("Library profile has no source path.")
    if scan_status == "not_scanned":
        warnings.append("No queue source scan artifact is available for this library.")
    if scan_status == "error":
        warnings.append("Latest queue source scan evidence is unavailable or failed.")
    if counts_truncated:
        warnings.append("Counts are partial because the source inventory hit its row limit.")
    return warnings


def _bounded_status(queue_scan_status: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": _text(queue_scan_status.get("schema_version")),
        "scan_id": _text(queue_scan_status.get("scan_id")),
        "status": _text(queue_scan_status.get("status")) or "idle",
        "phase": _text(queue_scan_status.get("phase")),
        "running": bool(queue_scan_status.get("running")),
        "started_at_utc": _text(queue_scan_status.get("started_at_utc")),
        "updated_at_utc": _text(queue_scan_status.get("updated_at_utc")),
        "completed_at_utc": _text(queue_scan_status.get("completed_at_utc")),
        "message": _text(queue_scan_status.get("message")),
        "inventory_count": _int_value(queue_scan_status.get("inventory_count")),
        "curated_row_count": _int_value(queue_scan_status.get("curated_row_count")),
    }


def _path_key(value: Any) -> str:
    return str(value or "").replace("\\", "/").rstrip("/").casefold()


def _text(value: Any) -> str:
    return str(value or "").strip()


def _first_text(*values: Any) -> str:
    for value in values:
        text = _text(value)
        if text:
            return text
    return ""


def _int_value(value: Any, *, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _default_name(profile_id: str) -> str:
    if profile_id == "tv":
        return "TV"
    if profile_id == "movies":
        return "Movies"
    return "Library"


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        text = str(value or "").strip()
        key = text.casefold()
        if not text or key in seen:
            continue
        seen.add(key)
        result.append(text)
    return result


__all__ = [
    "LIBRARY_SUMMARY_SCHEMA_VERSION",
    "build_library_summary",
]
