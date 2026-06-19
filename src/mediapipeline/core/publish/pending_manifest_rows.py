from __future__ import annotations

import contextlib
from pathlib import Path
from typing import Any

from mediapipeline.core.kernel.contracts.pending_publish import PENDING_PUSH_RETRY_LIMIT
from mediapipeline.core.publish.pending_format import (
    format_bytes_compact,
    format_pending_datetime_text,
    format_pending_timestamp,
    int_or_none,
    pending_age_text,
)
from mediapipeline.core.publish.pending_paths import path_from_manifest, pending_item_mtime


def unreadable_pending_manifest_row(manifest_path: Path, exc: Exception) -> dict[str, Any]:
    return {
        "manifest_path": str(manifest_path),
        "parked_at": "",
        "parked_at_display": format_pending_timestamp(pending_item_mtime(manifest_path)),
        "age_text": "",
        "publish_mode": "",
        "route": "",
        "state": "unreadable",
        "local_file": "",
        "local_exists": False,
        "server_out": "",
        "source_path": "",
        "output_size": 0,
        "size_text": "0 B",
        "sidecar_count": 0,
        "missing_sidecar_count": 0,
        "sidecar_paths": [],
        "error": str(exc),
    }


def invalid_contract_pending_manifest_row(
    manifest_path: Path,
    manifest: dict[str, Any],
    *,
    schema_version: str,
    exc: Exception,
) -> dict[str, Any]:
    return {
        "manifest_path": str(manifest_path),
        "parked_at": str(manifest.get("parked_at") or "").strip(),
        "parked_at_display": format_pending_timestamp(pending_item_mtime(manifest_path)),
        "age_text": "",
        "publish_mode": str(manifest.get("publish_mode") or "").strip(),
        "route": str(manifest.get("route") or "").strip(),
        "state": "invalid_contract",
        "local_file": str(manifest.get("local_file") or manifest.get("parked_file") or "").strip(),
        "local_exists": False,
        "server_out": str(manifest.get("server_out") or "").strip(),
        "source_path": str(manifest.get("source_path") or "").strip(),
        "output_size": 0,
        "size_text": "0 B",
        "sidecar_count": 0,
        "missing_sidecar_count": 0,
        "sidecar_paths": [],
        "schema_version": schema_version,
        "retry_count": int(int_or_none(manifest.get("retry_count")) or 0),
        "retry_limit": PENDING_PUSH_RETRY_LIMIT,
        "retry_exhausted": int(int_or_none(manifest.get("retry_count")) or 0) >= PENDING_PUSH_RETRY_LIMIT,
        "error": f"Current pending manifest contract invalid: {exc}",
    }


def pending_sidecar_status(sidecars: Any) -> tuple[list[str], int]:
    sidecar_paths: list[str] = []
    missing_sidecars = 0
    if isinstance(sidecars, list):
        for sidecar in sidecars:
            if not isinstance(sidecar, dict):
                continue
            sidecar_path = path_from_manifest(sidecar, "local_file", "parked_file")
            if sidecar_path:
                sidecar_paths.append(str(sidecar_path))
                if not sidecar_path.exists():
                    missing_sidecars += 1
    return sidecar_paths, missing_sidecars


def pending_output_size(manifest: dict[str, Any], local_path: Path | None) -> int:
    output_size = int_or_none(manifest.get("output_size"))
    if output_size is None and local_path and local_path.exists():
        with contextlib.suppress(OSError):
            output_size = local_path.stat().st_size
    return int(output_size or 0)


def pending_payload_error_text(
    local_path: Path | None,
    local_exists: bool,
    missing_sidecars: int,
    *,
    server_path: Path | None = None,
    state: str = "",
    known_states: set[str] | None = None,
    require_destination: bool = False,
    require_state: bool = False,
) -> str:
    issues: list[str] = []
    if local_path is None:
        issues.append("Manifest local_file payload path is missing; retry/drain will require manual recovery.")
    elif not local_exists:
        issues.append("Manifest local_file payload is missing; retry/drain will require manual recovery.")
    if require_destination and server_path is None:
        issues.append("Manifest server_out destination is missing; retry/drain will require manifest repair.")
    normalized_state = str(state or "").strip()
    if require_state and not normalized_state:
        issues.append("Manifest state is missing; retry/drain will require manifest repair.")
    elif known_states is not None and normalized_state not in known_states:
        issues.append(f"Manifest state '{normalized_state}' is not recognized; retry/drain will require manifest repair.")
    if missing_sidecars:
        issues.append(f"{missing_sidecars} pending sidecar payload(s) are missing.")
    return "; ".join(issues)


def readable_pending_manifest_row(
    *,
    manifest_path: Path,
    parked_at: str,
    publish_mode: str,
    route: str,
    state: str,
    local_path: Path | None,
    local_exists: bool,
    server_path: Path | None,
    source_path: Path | None,
    output_size: int,
    sidecar_paths: list[str],
    missing_sidecars: int,
    schema_version: str,
    error_text: str,
    retry_count: int = 0,
    retry_limit: int = PENDING_PUSH_RETRY_LIMIT,
) -> dict[str, Any]:
    safe_retry_count = max(0, int(retry_count or 0))
    safe_retry_limit = max(1, int(retry_limit or PENDING_PUSH_RETRY_LIMIT))
    return {
        "manifest_path": str(manifest_path),
        "parked_at": parked_at,
        "parked_at_display": format_pending_datetime_text(parked_at) or format_pending_timestamp(pending_item_mtime(manifest_path)),
        "age_text": pending_age_text(parked_at),
        "publish_mode": publish_mode,
        "route": route,
        "state": state or "unknown",
        "local_file": str(local_path) if local_path else "",
        "local_exists": local_exists,
        "server_out": str(server_path) if server_path else "",
        "source_path": str(source_path) if source_path else "",
        "output_size": int(output_size),
        "size_text": format_bytes_compact(int(output_size)),
        "sidecar_count": len(sidecar_paths),
        "missing_sidecar_count": missing_sidecars,
        "sidecar_paths": sidecar_paths,
        "schema_version": schema_version or "legacy",
        "retry_count": safe_retry_count,
        "retry_limit": safe_retry_limit,
        "retry_exhausted": safe_retry_count >= safe_retry_limit,
        "error": error_text,
    }
