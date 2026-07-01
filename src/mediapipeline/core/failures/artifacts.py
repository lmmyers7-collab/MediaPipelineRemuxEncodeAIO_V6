from __future__ import annotations

import os
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from mediapipeline.core.paths.contracts import ResolvedPaths


FAILURE_ARTIFACT_SUMMARY_SCHEMA_VERSION = "failure_artifact_summary.v1"
DEFAULT_FAILURE_ARTIFACT_WARNING_THRESHOLD_GB = 100
DEFAULT_FAILURE_ARTIFACT_RETENTION_DAYS = 0
DEFAULT_FAILURE_ARTIFACT_CLEANUP_TARGET_GB = 0
FAILURE_ARTIFACT_TOP_FILE_LIMIT = 25
_GIB = 1024**3
_SECONDS_PER_DAY = 24 * 60 * 60


def failure_artifact_roots(resolved: ResolvedPaths) -> list[dict[str, Any]]:
    roots: list[dict[str, Any]] = []
    if resolved.state_root:
        roots.append({"role": "current", "path": resolved.state_root / "Failures" / "Artifacts"})
    elif resolved.local_base:
        roots.append({"role": "current", "path": resolved.local_base / "State" / "Failures" / "Artifacts"})
    if resolved.local_base:
        roots.append({"role": "legacy", "path": resolved.local_base / "Failed" / "Artifacts"})

    unique: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in roots:
        path = Path(item["path"])
        key = os.path.normcase(os.path.abspath(str(path)))
        if key in seen:
            continue
        seen.add(key)
        unique.append({"role": str(item["role"]), "path": path})
    return unique


def failure_artifact_warning_threshold_gb(config: dict[str, Any] | None) -> tuple[float, list[str]]:
    warnings: list[str] = []
    raw = (config or {}).get("FailureArtifactWarningThresholdGB", DEFAULT_FAILURE_ARTIFACT_WARNING_THRESHOLD_GB)
    try:
        threshold = float(raw)
    except (TypeError, ValueError):
        warnings.append(
            "FailureArtifactWarningThresholdGB was not numeric; using the default 100 GB warning threshold."
        )
        return float(DEFAULT_FAILURE_ARTIFACT_WARNING_THRESHOLD_GB), warnings
    if threshold < 0:
        warnings.append(
            "FailureArtifactWarningThresholdGB was negative; using the default 100 GB warning threshold."
        )
        return float(DEFAULT_FAILURE_ARTIFACT_WARNING_THRESHOLD_GB), warnings
    return threshold, warnings


def failure_artifact_cleanup_policy(
    config: dict[str, Any] | None,
    *,
    retention_days: Any = None,
    target_gb: Any = None,
) -> tuple[dict[str, Any], list[str]]:
    warnings: list[str] = []
    explicit_target_override = target_gb is not None
    days = _non_negative_int(
        retention_days if retention_days is not None else (config or {}).get("FailureArtifactRetentionDays", DEFAULT_FAILURE_ARTIFACT_RETENTION_DAYS),
        default=DEFAULT_FAILURE_ARTIFACT_RETENTION_DAYS,
        label="FailureArtifactRetentionDays",
        warnings=warnings,
    )
    target = _non_negative_number(
        target_gb if target_gb is not None else (config or {}).get("FailureArtifactCleanupTargetGB", DEFAULT_FAILURE_ARTIFACT_CLEANUP_TARGET_GB),
        default=float(DEFAULT_FAILURE_ARTIFACT_CLEANUP_TARGET_GB),
        label="FailureArtifactCleanupTargetGB",
        warnings=warnings,
    )
    target_enabled = target > 0 or (explicit_target_override and target == 0)
    return {
        "schema_version": "failure_artifact_cleanup_policy.v1",
        "retention_days": days,
        "cleanup_target_gb": target,
        "retention_enabled": days > 0,
        "target_enabled": target_enabled,
        "enabled": days > 0 or target_enabled,
    }, warnings


def failure_artifact_summary_unavailable(reason: str) -> dict[str, Any]:
    return {
        "schema_version": FAILURE_ARTIFACT_SUMMARY_SCHEMA_VERSION,
        "evidence_authority": "backend",
        "status": "unavailable",
        "root_paths": [],
        "total_bytes": 0,
        "total_gb": 0.0,
        "total_size_text": "0 B",
        "file_count": 0,
        "oldest_modified_at": "",
        "newest_modified_at": "",
        "largest_files": [],
        "threshold_gb": float(DEFAULT_FAILURE_ARTIFACT_WARNING_THRESHOLD_GB),
        "retention_days": DEFAULT_FAILURE_ARTIFACT_RETENTION_DAYS,
        "cleanup_target_gb": float(DEFAULT_FAILURE_ARTIFACT_CLEANUP_TARGET_GB),
        "cleanup_policy_enabled": False,
        "warning": False,
        "warning_message": "",
        "scan_errors": [reason],
        "touches_media": False,
        "cleanup_route_available": True,
    }


def failure_artifact_summary(resolved: ResolvedPaths) -> dict[str, Any]:
    threshold_gb, threshold_warnings = failure_artifact_warning_threshold_gb(resolved.config_data)
    cleanup_policy, cleanup_warnings = failure_artifact_cleanup_policy(resolved.config_data)
    scan_errors = list(threshold_warnings)
    scan_errors.extend(cleanup_warnings)
    root_summaries: list[dict[str, Any]] = []
    largest_files: list[dict[str, Any]] = []
    total_bytes = 0
    file_count = 0
    oldest_mtime: float | None = None
    newest_mtime: float | None = None

    for root in failure_artifact_roots(resolved):
        role = str(root["role"])
        root_path = Path(root["path"])
        root_bytes = 0
        root_count = 0
        root_errors: list[str] = []
        try:
            exists = root_path.exists()
            is_dir = root_path.is_dir() if exists else False
        except OSError as exc:
            exists = False
            is_dir = False
            root_errors.append(f"{root_path}: {exc}")
        if exists and not is_dir:
            root_errors.append(f"{root_path} exists but is not a directory.")
        if is_dir:
            try:
                candidates = list(root_path.rglob("*"))
            except OSError as exc:
                candidates = []
                root_errors.append(f"{root_path}: {exc}")
            for path in candidates:
                try:
                    if path.is_symlink() or not path.is_file():
                        continue
                    stat = path.stat()
                except OSError as exc:
                    scan_errors.append(f"{path}: {exc}")
                    continue
                size = int(stat.st_size)
                modified = float(stat.st_mtime)
                root_bytes += size
                root_count += 1
                total_bytes += size
                file_count += 1
                oldest_mtime = modified if oldest_mtime is None else min(oldest_mtime, modified)
                newest_mtime = modified if newest_mtime is None else max(newest_mtime, modified)
                largest_files.append(
                    {
                        "role": role,
                        "root_path": str(root_path),
                        "path": str(path),
                        "relative_path": _relative_path(path, root_path),
                        "name": path.name,
                        "size_bytes": size,
                        "size_gb": _gb(size),
                        "modified_at": _timestamp(modified),
                    }
                )
        scan_errors.extend(root_errors)
        root_summaries.append(
            {
                "role": role,
                "path": str(root_path),
                "exists": bool(exists),
                "is_dir": bool(is_dir),
                "file_count": root_count,
                "total_bytes": root_bytes,
                "total_gb": _gb(root_bytes),
                "scan_errors": root_errors,
            }
        )

    largest_files = sorted(largest_files, key=lambda item: int(item.get("size_bytes") or 0), reverse=True)[
        :FAILURE_ARTIFACT_TOP_FILE_LIMIT
    ]
    warning = threshold_gb > 0 and total_bytes >= int(threshold_gb * _GIB)
    return {
        "schema_version": FAILURE_ARTIFACT_SUMMARY_SCHEMA_VERSION,
        "evidence_authority": "backend",
        "status": "warning" if warning else "ok",
        "root_paths": root_summaries,
        "total_bytes": total_bytes,
        "total_gb": _gb(total_bytes),
        "total_size_text": _size_text(total_bytes),
        "file_count": file_count,
        "oldest_modified_at": _timestamp(oldest_mtime),
        "newest_modified_at": _timestamp(newest_mtime),
        "largest_files": largest_files,
        "threshold_gb": threshold_gb,
        "retention_days": cleanup_policy["retention_days"],
        "cleanup_target_gb": cleanup_policy["cleanup_target_gb"],
        "cleanup_policy_enabled": cleanup_policy["enabled"],
        "warning": warning,
        "warning_message": _warning_message(total_bytes, threshold_gb) if warning else "",
        "scan_errors": scan_errors,
        "touches_media": False,
        "cleanup_route_available": True,
    }


def failure_artifact_cleanup_plan(
    resolved: ResolvedPaths,
    *,
    retention_days: Any = None,
    target_gb: Any = None,
    artifact_paths: list[str] | None = None,
    now: float | None = None,
) -> dict[str, Any]:
    policy, policy_warnings = failure_artifact_cleanup_policy(
        resolved.config_data,
        retention_days=retention_days,
        target_gb=target_gb,
    )
    scan = _scan_failure_artifact_files(resolved)
    files = list(scan["files"])
    total_bytes = sum(int(item.get("size_bytes") or 0) for item in files)
    planned_by_path: dict[str, dict[str, Any]] = {}
    skipped: list[dict[str, Any]] = []
    now_value = float(now if now is not None else datetime.now(tz=timezone.utc).timestamp())
    selected_paths = _selected_artifact_paths(artifact_paths)
    selected_path_keys = {_artifact_path_key(path) for path in selected_paths}
    selected_path_keys.discard("")
    selection_enabled = bool(selected_path_keys)

    if selection_enabled:
        policy = dict(policy)
        policy["selection_enabled"] = True
        policy["selected_count"] = len(selected_path_keys)
        policy["enabled"] = True

    if selection_enabled:
        matched: set[str] = set()
        for item in files:
            key = _artifact_path_key(str(item.get("path") or ""))
            if key in selected_path_keys:
                matched.add(key)
                _plan_artifact(planned_by_path, item, "selected")
        for path in selected_paths:
            key = _artifact_path_key(path)
            if key and key not in matched:
                skipped.append(
                    {
                        "path": path,
                        "reason": "selected artifact unavailable",
                        "detail": "The selected artifact was not found under a backend failure artifact root.",
                    }
                )
    elif policy["retention_enabled"]:
        cutoff = now_value - (float(policy["retention_days"]) * _SECONDS_PER_DAY)
        for item in files:
            modified = float(item.get("modified_timestamp") or 0)
            if modified <= cutoff:
                _plan_artifact(planned_by_path, item, "retention_days")

    if not selection_enabled and policy["target_enabled"] and total_bytes > int(float(policy["cleanup_target_gb"]) * _GIB):
        target_bytes = int(float(policy["cleanup_target_gb"]) * _GIB)
        current_bytes = total_bytes
        for item in sorted(files, key=lambda entry: (float(entry.get("modified_timestamp") or 0), str(entry.get("path") or ""))):
            if current_bytes <= target_bytes:
                break
            _plan_artifact(planned_by_path, item, "cleanup_target_gb")
            current_bytes -= int(item.get("size_bytes") or 0)

    if not policy["enabled"]:
        skipped.append(
            {
                "reason": "cleanup policy disabled",
                "detail": "Set FailureArtifactRetentionDays or FailureArtifactCleanupTargetGB above 0 to plan deletion.",
            }
        )

    planned = sorted(
        planned_by_path.values(),
        key=lambda entry: (float(entry.get("modified_timestamp") or 0), str(entry.get("path") or "")),
    )
    planned_bytes = sum(int(item.get("size_bytes") or 0) for item in planned)
    result = {
        "schema_version": "failure_artifact_cleanup_result.v1",
        "operation": "cleanup_failure_artifacts",
        "dry_run": True,
        "policy": policy,
        "root_paths": scan["root_paths"],
        "total_bytes": total_bytes,
        "total_gb": _gb(total_bytes),
        "planned_bytes": planned_bytes,
        "planned_gb": _gb(planned_bytes),
        "planned_count": len(planned),
        "planned": [_public_artifact_entry(item) for item in planned],
        "requested_artifact_paths": selected_paths,
        "skipped": skipped,
        "errors": [*policy_warnings, *scan["scan_errors"]],
        "deleted": [],
        "deleted_count": 0,
        "deleted_bytes": 0,
        "manifest_path": "",
        "dry_run_fingerprint": "",
        "fingerprint": "",
        "touches_media": False,
        "touches_failure_artifacts": False,
        "source_media_mutation": False,
        "cleanup_route_available": True,
    }
    fingerprint = failure_artifact_cleanup_fingerprint(result)
    result["dry_run_fingerprint"] = fingerprint
    result["fingerprint"] = fingerprint
    return result


def failure_artifact_cleanup_fingerprint(plan: dict[str, Any]) -> str:
    payload = {
        "schema_version": "failure_artifact_cleanup_fingerprint.v1",
        "policy": {
            "retention_days": int(dict(plan.get("policy") or {}).get("retention_days") or 0),
            "cleanup_target_gb": float(dict(plan.get("policy") or {}).get("cleanup_target_gb") or 0),
            "selection_enabled": bool(dict(plan.get("policy") or {}).get("selection_enabled")),
        },
        "requested_artifact_paths": sorted(str(path) for path in plan.get("requested_artifact_paths") or []),
        "planned": sorted(
            [
                {
                    "path": item.get("path"),
                    "size_bytes": item.get("size_bytes"),
                    "modified_at": item.get("modified_at"),
                    "reasons": sorted([str(reason) for reason in item.get("reasons") or []]),
                }
                for item in plan.get("planned") or []
            ],
            key=lambda item: str(item.get("path") or ""),
        ),
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _gb(bytes_value: int) -> float:
    return round(float(bytes_value) / _GIB, 3)


def _size_text(bytes_value: int) -> str:
    if bytes_value >= _GIB:
        return f"{_gb(bytes_value):.3f} GB"
    mib = 1024**2
    if bytes_value >= mib:
        return f"{bytes_value / mib:.1f} MB"
    kib = 1024
    if bytes_value >= kib:
        return f"{bytes_value / kib:.1f} KB"
    return f"{bytes_value} B"


def _timestamp(value: float | None) -> str:
    if value is None:
        return ""
    return datetime.fromtimestamp(value, tz=timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _relative_path(path: Path, root: Path) -> str:
    try:
        return str(path.relative_to(root))
    except ValueError:
        return path.name


def _warning_message(total_bytes: int, threshold_gb: float) -> str:
    return (
        f"Failure artifacts are using {_size_text(total_bytes)}, which is at or above "
        f"the configured {threshold_gb:g} GB warning threshold."
    )


def _non_negative_number(value: Any, *, default: float, label: str, warnings: list[str]) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        warnings.append(f"{label} was not numeric; using {default:g}.")
        return default
    if number < 0:
        warnings.append(f"{label} was negative; using {default:g}.")
        return default
    return number


def _non_negative_int(value: Any, *, default: int, label: str, warnings: list[str]) -> int:
    if isinstance(value, bool):
        warnings.append(f"{label} was not an integer; using {default}.")
        return default
    try:
        number = int(value)
    except (TypeError, ValueError):
        warnings.append(f"{label} was not an integer; using {default}.")
        return default
    if str(value).strip() not in (str(number), f"{number}.0"):
        warnings.append(f"{label} was not an integer; using {default}.")
        return default
    if number < 0:
        warnings.append(f"{label} was negative; using {default}.")
        return default
    return number


def _scan_failure_artifact_files(resolved: ResolvedPaths) -> dict[str, Any]:
    root_summaries: list[dict[str, Any]] = []
    files: list[dict[str, Any]] = []
    scan_errors: list[str] = []
    for root in failure_artifact_roots(resolved):
        role = str(root["role"])
        root_path = Path(root["path"])
        root_bytes = 0
        root_count = 0
        root_errors: list[str] = []
        try:
            exists = root_path.exists()
            is_dir = root_path.is_dir() if exists else False
        except OSError as exc:
            exists = False
            is_dir = False
            root_errors.append(f"{root_path}: {exc}")
        if exists and not is_dir:
            root_errors.append(f"{root_path} exists but is not a directory.")
        if is_dir:
            try:
                candidates = list(root_path.rglob("*"))
            except OSError as exc:
                candidates = []
                root_errors.append(f"{root_path}: {exc}")
            for path in candidates:
                try:
                    if path.is_symlink() or not path.is_file():
                        continue
                    stat = path.stat()
                except OSError as exc:
                    scan_errors.append(f"{path}: {exc}")
                    continue
                size = int(stat.st_size)
                modified = float(stat.st_mtime)
                root_bytes += size
                root_count += 1
                files.append(
                    {
                        "role": role,
                        "root_path": str(root_path),
                        "path": str(path),
                        "relative_path": _relative_path(path, root_path),
                        "name": path.name,
                        "size_bytes": size,
                        "size_gb": _gb(size),
                        "modified_at": _timestamp(modified),
                        "modified_timestamp": modified,
                    }
                )
        scan_errors.extend(root_errors)
        root_summaries.append(
            {
                "role": role,
                "path": str(root_path),
                "exists": bool(exists),
                "is_dir": bool(is_dir),
                "file_count": root_count,
                "total_bytes": root_bytes,
                "total_gb": _gb(root_bytes),
                "scan_errors": root_errors,
            }
        )
    return {"root_paths": root_summaries, "files": files, "scan_errors": scan_errors}


def _selected_artifact_paths(paths: list[str] | None) -> list[str]:
    selected: list[str] = []
    seen: set[str] = set()
    for path in paths or []:
        text = str(path or "").strip()
        key = _artifact_path_key(text)
        if not text or not key or key in seen:
            continue
        seen.add(key)
        selected.append(text)
    return selected


def _artifact_path_key(path: str) -> str:
    text = str(path or "").strip()
    if not text:
        return ""
    return os.path.normcase(os.path.abspath(text))


def _plan_artifact(planned_by_path: dict[str, dict[str, Any]], item: dict[str, Any], reason: str) -> None:
    key = _artifact_path_key(str(item.get("path") or ""))
    planned = planned_by_path.setdefault(key, dict(item))
    reasons = [str(value) for value in planned.get("reasons") or [] if str(value).strip()]
    if reason not in reasons:
        reasons.append(reason)
    planned["reasons"] = reasons


def _public_artifact_entry(item: dict[str, Any]) -> dict[str, Any]:
    public = dict(item)
    public.pop("modified_timestamp", None)
    return public
