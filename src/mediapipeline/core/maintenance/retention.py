"""Read-only retention dry-run evidence for runtime artifact cleanup."""

from __future__ import annotations

from pathlib import Path
import time
from typing import Any, Iterable, Mapping


RETENTION_DRY_RUN_COMMAND = "maintenance.retention_dry_run"
RETENTION_DRY_RUN_SCHEMA_VERSION = "desktop_retention_dry_run.v1"
RETENTION_EFFECT_NONE = "none"
RETENTION_DEFAULT_LIMIT = 200
RETENTION_MAX_LIMIT = 1000


def retention_dry_run_payload(resolved: Any, request: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """Build retention cleanup evidence without deleting, moving, or writing files."""
    request = request or {}
    limit = _bounded_limit(request.get("limit"))
    now = time.time()
    allowed_roots = _allowed_cleanup_roots(resolved)
    excluded_roots = _excluded_roots(resolved)
    categories: dict[str, dict[str, Any]] = {}
    seen: set[str] = set()
    remaining = {"value": limit}
    for key, label, roots, direct_files, patterns in _category_specs(resolved):
        category = _category_payload(
            key=key,
            label=label,
            roots=roots,
            direct_files=direct_files,
            patterns=patterns,
            now=now,
            allowed_roots=allowed_roots,
            excluded_roots=excluded_roots,
            seen=seen,
            remaining=remaining,
        )
        categories[key] = category
    candidates = [
        row
        for category in categories.values()
        for row in category["candidates"]
    ]
    guardrail_exclusions = _guardrail_exclusions(resolved)
    eligible = [row for row in candidates if bool(row.get("cleanup_eligible"))]
    scan_errors = [
        error
        for category in categories.values()
        for error in category.get("errors", [])
    ]
    overall_status = "review" if scan_errors else "ready"
    return {
        "schema_version": RETENTION_DRY_RUN_SCHEMA_VERSION,
        "dry_run_only": True,
        "effect": RETENTION_EFFECT_NONE,
        "overall_status": overall_status,
        "candidate_count": len(candidates),
        "eligible_count": len(eligible),
        "total_bytes": sum(_int_value(row.get("size_bytes")) for row in candidates),
        "eligible_bytes": sum(_int_value(row.get("size_bytes")) for row in eligible),
        "categories": categories,
        "candidates": candidates,
        "guardrail_exclusions": guardrail_exclusions,
        "allowlist_roots": [str(path) for path in allowed_roots],
        "excluded_roots": [str(path) for path in excluded_roots],
        "would_delete_paths": [],
        "would_move_paths": [],
        "would_write_paths": [],
        "would_not_touch": _would_not_touch(),
        "safe_to_apply": False,
        "mutation_route_available": False,
        "suppress_command_journal": True,
        "request_summary": {
            "limit": limit,
            "reason_present": bool(str(request.get("reason") or "").strip()),
        },
        "summary_lines": [
            f"Retention dry-run found {len(candidates)} runtime artifact candidate(s); {len(eligible)} are under allowlisted runtime roots.",
            "No files were deleted, moved, truncated, rewritten, archived, or marked for removal.",
            "Source roots, final output roots, and parked pending-publish payloads are guardrail exclusions in this v1 report.",
        ],
    }


def _bounded_limit(value: Any) -> int:
    try:
        parsed = int(value) if value not in (None, "") else RETENTION_DEFAULT_LIMIT
    except (TypeError, ValueError):
        parsed = RETENTION_DEFAULT_LIMIT
    return max(1, min(RETENTION_MAX_LIMIT, parsed))


def _int_value(value: Any) -> int:
    try:
        return int(value) if value not in (None, "") else 0
    except (TypeError, ValueError):
        return 0


def _path(value: Any) -> Path | None:
    if value in (None, ""):
        return None
    try:
        return Path(str(value))
    except (TypeError, ValueError):
        return None


def _resolved_path(path: Path) -> Path:
    try:
        return path.resolve(strict=False)
    except OSError:
        return path.absolute()


def _dedupe_paths(paths: Iterable[Path | None]) -> list[Path]:
    seen: set[str] = set()
    result: list[Path] = []
    for path in paths:
        if path is None:
            continue
        text = str(_resolved_path(path)).casefold()
        if text in seen:
            continue
        seen.add(text)
        result.append(path)
    return result


def _is_under(path: Path, roots: Iterable[Path]) -> bool:
    resolved = _resolved_path(path)
    for root in roots:
        root_resolved = _resolved_path(root)
        if resolved == root_resolved or resolved.is_relative_to(root_resolved):
            return True
    return False


def _config_path(resolved: Any, key: str) -> Path | None:
    config = getattr(resolved, "config_data", None)
    if not isinstance(config, Mapping):
        return None
    return _path(config.get(key))


def _library_profile_roots(resolved: Any, field_names: set[str]) -> list[Path]:
    config = getattr(resolved, "config_data", None)
    if not isinstance(config, Mapping):
        return []
    raw_profiles = config.get("LibraryProfiles")
    if isinstance(raw_profiles, Mapping):
        profiles = raw_profiles.values()
    elif isinstance(raw_profiles, list):
        profiles = raw_profiles
    else:
        profiles = []
    roots: list[Path] = []
    for profile in profiles:
        if not isinstance(profile, Mapping):
            continue
        for field in field_names:
            candidate = _path(profile.get(field))
            if candidate is not None:
                roots.append(candidate)
    return roots


def _allowed_cleanup_roots(resolved: Any) -> list[Path]:
    local_base = _path(getattr(resolved, "local_base", None))
    state_root = _path(getattr(resolved, "state_root", None))
    app_root = _path(getattr(resolved, "app_root", None))
    workspace_root = _path(getattr(resolved, "workspace_root", None))
    log_file = _path(getattr(resolved, "log_file", None))
    event_file = _path(getattr(resolved, "event_file", None))
    completed_manifest = _path(getattr(resolved, "completed_manifest_path", None))
    failed_reports = _path(getattr(resolved, "failed_reports_path", None))
    failed_markers = _path(getattr(resolved, "failed_markers_path", None))
    roots = [
        log_file.parent if log_file else None,
        event_file.parent if event_file else None,
        completed_manifest.parent if completed_manifest else None,
        failed_reports,
        failed_markers,
        local_base / "Logs" if local_base else None,
        local_base / "RunLogs" if local_base else None,
        local_base / "Temp" if local_base else None,
        local_base / "tmp" if local_base else None,
        local_base / "Scratch" if local_base else None,
        local_base / "Work" if local_base else None,
        local_base / "Working" if local_base else None,
        local_base / "Transcode" if local_base else None,
        local_base / "Cache" if local_base else None,
        local_base / "Caches" if local_base else None,
        state_root / "Logs" if state_root else None,
        state_root / "Temp" if state_root else None,
        state_root / "Cache" if state_root else None,
        app_root / "RunLogs" if app_root else None,
        workspace_root / "RunLogs" if workspace_root else None,
    ]
    return _dedupe_paths(roots)


def _excluded_roots(resolved: Any) -> list[Path]:
    roots = [
        _path(getattr(resolved, "source_movies", None)),
        _path(getattr(resolved, "source_tv", None)),
        _path(getattr(resolved, "pending_push_path", None)),
        _config_path(resolved, "Outsource"),
        *_library_profile_roots(resolved, {"source_path", "SourcePath", "SourceRoot"}),
        *_library_profile_roots(resolved, {"output_path", "OutputPath", "DestinationRoot"}),
    ]
    return _dedupe_paths(roots)


def _category_specs(resolved: Any) -> list[tuple[str, str, list[Path], list[Path], tuple[str, ...]]]:
    local_base = _path(getattr(resolved, "local_base", None))
    state_root = _path(getattr(resolved, "state_root", None))
    app_root = _path(getattr(resolved, "app_root", None))
    workspace_root = _path(getattr(resolved, "workspace_root", None))
    failed_reports = _path(getattr(resolved, "failed_reports_path", None))
    failed_markers = _path(getattr(resolved, "failed_markers_path", None))
    return [
        (
            "logs",
            "Logs",
            _dedupe_paths(
                [
                    local_base / "Logs" if local_base else None,
                    local_base / "RunLogs" if local_base else None,
                    state_root / "Logs" if state_root else None,
                    app_root / "RunLogs" if app_root else None,
                    workspace_root / "RunLogs" if workspace_root else None,
                ]
            ),
            _dedupe_paths([_path(getattr(resolved, "log_file", None))]),
            ("*.log", "*.txt", "*.jsonl"),
        ),
        (
            "jsonl_state",
            "JSONL/state files",
            _dedupe_paths([state_root / "Progress" if state_root else None, state_root / "Completed" if state_root else None]),
            _dedupe_paths([_path(getattr(resolved, "event_file", None)), _path(getattr(resolved, "completed_manifest_path", None))]),
            ("*.jsonl",),
        ),
        (
            "temp_scratch_orphans",
            "Temp/scratch orphans",
            _dedupe_paths(
                [
                    local_base / "Temp" if local_base else None,
                    local_base / "tmp" if local_base else None,
                    local_base / "Scratch" if local_base else None,
                    local_base / "Work" if local_base else None,
                    local_base / "Working" if local_base else None,
                    local_base / "Transcode" if local_base else None,
                    state_root / "Temp" if state_root else None,
                ]
            ),
            [],
            ("*",),
        ),
        (
            "failure_reports",
            "Failure reports",
            _dedupe_paths([failed_reports, failed_markers]),
            [],
            ("*.json", "*.jsonl", "*.txt", "*.log"),
        ),
        (
            "cache_artifacts",
            "Cache artifacts",
            _dedupe_paths(
                [
                    local_base / "Cache" if local_base else None,
                    local_base / "Caches" if local_base else None,
                    state_root / "Cache" if state_root else None,
                ]
            ),
            [],
            ("*",),
        ),
    ]


def _category_payload(
    *,
    key: str,
    label: str,
    roots: Iterable[Path],
    direct_files: Iterable[Path],
    patterns: Iterable[str],
    now: float,
    allowed_roots: list[Path],
    excluded_roots: list[Path],
    seen: set[str],
    remaining: dict[str, int],
) -> dict[str, Any]:
    errors: list[str] = []
    candidates: list[dict[str, Any]] = []
    roots_scanned: list[str] = []
    for path in direct_files:
        if remaining["value"] <= 0:
            break
        row = _candidate_row(key, path, now=now, allowed_roots=allowed_roots, excluded_roots=excluded_roots)
        if row is None:
            continue
        dedupe_key = str(_resolved_path(path)).casefold()
        if dedupe_key in seen:
            continue
        seen.add(dedupe_key)
        candidates.append(row)
        remaining["value"] -= 1
    for root in roots:
        if remaining["value"] <= 0:
            break
        roots_scanned.append(str(root))
        if not root.exists():
            continue
        if not root.is_dir():
            errors.append(f"{label} root is not a directory: {root}")
            continue
        for pattern in patterns:
            if remaining["value"] <= 0:
                break
            try:
                for path in root.rglob(pattern):
                    if remaining["value"] <= 0:
                        break
                    if not path.is_file():
                        continue
                    row = _candidate_row(key, path, now=now, allowed_roots=allowed_roots, excluded_roots=excluded_roots)
                    if row is None:
                        continue
                    dedupe_key = str(_resolved_path(path)).casefold()
                    if dedupe_key in seen:
                        continue
                    seen.add(dedupe_key)
                    candidates.append(row)
                    remaining["value"] -= 1
            except OSError as exc:
                errors.append(f"{label} root could not be scanned: {root}: {exc}")
                break
    eligible = [row for row in candidates if bool(row.get("cleanup_eligible"))]
    status = "review" if errors else "ready"
    return {
        "key": key,
        "label": label,
        "status": status,
        "candidate_count": len(candidates),
        "eligible_count": len(eligible),
        "total_bytes": sum(_int_value(row.get("size_bytes")) for row in candidates),
        "eligible_bytes": sum(_int_value(row.get("size_bytes")) for row in eligible),
        "roots_scanned": roots_scanned,
        "errors": errors,
        "candidates": candidates,
        "summary_lines": [
            f"{label}: {len(candidates)} candidate(s), {len(eligible)} eligible under retention allowlist.",
            "Dry-run only; no cleanup action was taken.",
        ],
    }


def _candidate_row(
    category: str,
    path: Path,
    *,
    now: float,
    allowed_roots: list[Path],
    excluded_roots: list[Path],
) -> dict[str, Any] | None:
    try:
        stat = path.stat()
    except OSError:
        return None
    excluded = _is_under(path, excluded_roots)
    allowed = _is_under(path, allowed_roots)
    cleanup_eligible = allowed and not excluded
    if excluded:
        blocked_reason = "path is inside a source, final output, or pending-publish guardrail root"
    elif not allowed:
        blocked_reason = "path is outside retention allowlist roots"
    else:
        blocked_reason = ""
    return {
        "category": category,
        "path": str(path),
        "kind": "file",
        "size_bytes": int(stat.st_size),
        "age_seconds": max(0, int(now - stat.st_mtime)),
        "cleanup_eligible": cleanup_eligible,
        "blocked_reason": blocked_reason,
        "would_delete": False,
        "safe_action": (
            "future allowlisted cleanup candidate; v1 report does not delete files"
            if cleanup_eligible
            else "review guardrail before any future cleanup command"
        ),
    }


def _guardrail_exclusions(resolved: Any) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    specs = [
        ("source_movies", _path(getattr(resolved, "source_movies", None)), "source media root"),
        ("source_tv", _path(getattr(resolved, "source_tv", None)), "source media root"),
        ("pending_publish", _path(getattr(resolved, "pending_push_path", None)), "parked pending-publish root"),
        ("final_output", _config_path(resolved, "Outsource"), "final output root"),
    ]
    for field, path, reason in specs:
        if path is None:
            continue
        rows.append(
            {
                "field": field,
                "path": str(path),
                "reason": reason,
                "cleanup_eligible": False,
                "would_delete": False,
                "safe_action": "excluded from retention cleanup candidates in this dry-run",
            }
        )
    return rows


def _would_not_touch() -> dict[str, str]:
    return {
        "source_media": "not scanned for cleanup candidates; never deleted, moved, renamed, or overwritten",
        "pending_publish": "parked payloads and manifests are excluded; not drained, moved, deleted, or rewritten",
        "final_output": "final output roots are excluded; completed outputs are not deleted or truncated",
        "scratch_media": "reported only when inside allowlisted runtime temp/scratch roots; not deleted by v1",
        "manifests": "completed and pending manifests are not rewritten",
        "command_journal": "suppressed for this read-only retention poll",
    }


__all__ = [
    "RETENTION_DRY_RUN_COMMAND",
    "RETENTION_DRY_RUN_SCHEMA_VERSION",
    "retention_dry_run_payload",
]
