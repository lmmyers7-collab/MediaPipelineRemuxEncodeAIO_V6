"""Read-only state correlation for CSV rerun preview rows."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
import json
import logging
from pathlib import Path
from typing import Any

from mediapipeline.core.completed.manifest import PROOF_MODE_SUMMARY, read_completed_manifest_records
from mediapipeline.core.paths.contracts import ResolvedPaths


RERUN_STATE_CORRELATION_SCHEMA_VERSION = "desktop_rerun_state_correlation.v1"
RERUN_STATE_CORRELATION_COMPLETED_LIMIT = 1000
RERUN_STATE_CORRELATION_RERUN_MANIFEST_LIMIT = 100
RERUN_STATE_CORRELATION_ROW_EVIDENCE_LIMIT = 5


def rerun_state_path_key(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    return text.replace("/", "\\").rstrip("\\").casefold()


def _path_text(value: Any) -> str:
    return str(value or "").strip()


def _evidence(kind: str, **fields: Any) -> dict[str, str]:
    payload = {"kind": kind}
    for key, value in fields.items():
        text = _path_text(value)
        if text:
            payload[key] = text
    return payload


def _add_match(matches: dict[str, dict[str, Any]], raw_source_path: Any, kind: str, evidence: Mapping[str, Any]) -> None:
    key = rerun_state_path_key(raw_source_path)
    if not key:
        return
    bucket = matches.setdefault(key, {"flags": set(), "evidence": []})
    bucket["flags"].add(kind)
    if len(bucket["evidence"]) < RERUN_STATE_CORRELATION_ROW_EVIDENCE_LIMIT:
        bucket["evidence"].append({str(item_key): str(item_value) for item_key, item_value in evidence.items() if str(item_value or "").strip()})


def _completed_matches(resolved: ResolvedPaths, matches: dict[str, dict[str, Any]], warnings: list[str]) -> int:
    path = getattr(resolved, "completed_manifest_path", None)
    if path is None or not Path(path).exists():
        return 0
    try:
        records = read_completed_manifest_records(
            Path(path),
            limit=RERUN_STATE_CORRELATION_COMPLETED_LIMIT,
            logger=logging.getLogger(__name__),
            proof_mode=PROOF_MODE_SUMMARY,
        )
    except Exception as exc:
        warnings.append(f"Completed manifest correlation unavailable: {exc}")
        return 0

    count = 0
    for record in records:
        payload = getattr(record, "payload", {}) or {}
        source_path = payload.get("source_path")
        key = rerun_state_path_key(source_path)
        if not key:
            continue
        count += 1
        _add_match(
            matches,
            source_path,
            "completed",
            _evidence(
                "completed",
                output_path=payload.get("output_path"),
                route=payload.get("route"),
                job_id=payload.get("job_id"),
            ),
        )
    return count


def _pending_matches(
    resolved: ResolvedPaths,
    service: Any | None,
    matches: dict[str, dict[str, Any]],
    warnings: list[str],
) -> int:
    scanner = getattr(service, "scan_pending_publish", None) if service is not None else None
    if not callable(scanner):
        warnings.append("Pending publish correlation unavailable: scan service is not available.")
        return 0
    try:
        payload = scanner(resolved)
    except Exception as exc:
        warnings.append(f"Pending publish correlation unavailable: {exc}")
        return 0
    if not isinstance(payload, Mapping):
        warnings.append("Pending publish correlation unavailable: scan service returned an invalid payload.")
        return 0
    rows = [row for row in payload.get("rows") or [] if isinstance(row, Mapping)]
    count = 0
    for row in rows:
        source_path = row.get("source_path")
        key = rerun_state_path_key(source_path)
        if not key:
            continue
        count += 1
        _add_match(
            matches,
            source_path,
            "pending_publish",
            _evidence(
                "pending_publish",
                state=row.get("state"),
                manifest_path=row.get("manifest_path"),
                server_out=row.get("server_out"),
                local_file=row.get("local_file"),
            ),
        )
    return count


def _rerun_manifest_root(resolved: ResolvedPaths) -> Path | None:
    local_base = getattr(resolved, "local_base", None)
    if local_base is None:
        return None
    return Path(local_base) / "RerunManifests"


def _prior_rerun_matches(resolved: ResolvedPaths, matches: dict[str, dict[str, Any]], warnings: list[str]) -> int:
    root = _rerun_manifest_root(resolved)
    if root is None or not root.exists():
        return 0
    try:
        manifests = sorted(root.glob("*.json"), key=lambda item: item.stat().st_mtime, reverse=True)
    except OSError as exc:
        warnings.append(f"Prior rerun correlation unavailable: {exc}")
        return 0

    count = 0
    for manifest_path in manifests[:RERUN_STATE_CORRELATION_RERUN_MANIFEST_LIMIT]:
        try:
            payload = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            warnings.append(f"Prior rerun manifest unreadable: {manifest_path.name}: {exc}")
            continue
        if not isinstance(payload, Mapping):
            continue
        for row in payload.get("rows") or []:
            if not isinstance(row, Mapping):
                continue
            source_path = row.get("source_path")
            key = rerun_state_path_key(source_path)
            if not key:
                continue
            count += 1
            _add_match(
                matches,
                source_path,
                "prior_rerun",
                _evidence(
                    "prior_rerun",
                    status=row.get("status"),
                    batch_id=payload.get("batch_id"),
                    manifest_path=manifest_path,
                    destination_mode=payload.get("destination_mode"),
                ),
            )
    return count


def build_rerun_state_correlation(
    resolved: ResolvedPaths,
    source_paths: Iterable[Any],
    *,
    service: Any | None = None,
) -> tuple[dict[str, Any], dict[str, dict[str, Any]]]:
    requested_key_list = [key for key in (rerun_state_path_key(path) for path in source_paths) if key]
    requested_keys = set(requested_key_list)
    warnings: list[str] = []
    matches: dict[str, dict[str, Any]] = {}
    completed_count = _completed_matches(resolved, matches, warnings)
    pending_count = _pending_matches(resolved, service, matches, warnings)
    prior_rerun_count = _prior_rerun_matches(resolved, matches, warnings)

    filtered: dict[str, dict[str, Any]] = {}
    for key, match in matches.items():
        if key not in requested_keys:
            continue
        filtered[key] = {
            "flags": sorted(str(flag) for flag in match.get("flags", set())),
            "evidence": list(match.get("evidence") or []),
        }

    payload = {
        "schema_version": RERUN_STATE_CORRELATION_SCHEMA_VERSION,
        "status": "warning" if warnings else "complete",
        "warnings": warnings,
        "counts": {
            "requested_source_rows": len(requested_key_list),
            "requested_distinct_source_paths": len(requested_keys),
            "matched_source_rows": sum(1 for key in requested_key_list if key in filtered),
            "matched_distinct_source_paths": len(filtered),
            "completed_matches_scanned": completed_count,
            "pending_publish_matches_scanned": pending_count,
            "prior_rerun_matches_scanned": prior_rerun_count,
            "completed_source_rows": sum(1 for match in filtered.values() if "completed" in match.get("flags", [])),
            "pending_publish_source_rows": sum(1 for match in filtered.values() if "pending_publish" in match.get("flags", [])),
            "prior_rerun_source_rows": sum(1 for match in filtered.values() if "prior_rerun" in match.get("flags", [])),
        },
        "sources": {
            "completed_manifest_path": str(getattr(resolved, "completed_manifest_path", "") or ""),
            "pending_publish": "service.scan_pending_publish" if service is not None else "",
            "rerun_manifest_root": str(_rerun_manifest_root(resolved) or ""),
        },
        "touches_media": False,
        "writes_queue": False,
        "writes_file_overrides": False,
    }
    return payload, filtered


__all__ = [
    "RERUN_STATE_CORRELATION_SCHEMA_VERSION",
    "build_rerun_state_correlation",
    "rerun_state_path_key",
]
