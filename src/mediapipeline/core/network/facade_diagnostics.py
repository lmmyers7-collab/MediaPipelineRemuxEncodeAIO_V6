"""Network runtime-state facade adapter."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, UTC
import hashlib
import ipaddress
import logging
from pathlib import Path
import re
import socket
from typing import TYPE_CHECKING, Any
from urllib.parse import urlsplit

from mediapipeline.core.config.library_profiles import effective_library_profiles_from_config
from mediapipeline.core.kernel.config_keys import (
    KEY_WORKER_ENCODER_MAP,
    KEY_WORKER_HONOR_COORDINATOR_POLICY,
)
from mediapipeline.core.kernel.dto_commands import CommandResult
from mediapipeline.core.network.join import (
    NETWORK_JOIN_BLOB_RESULT_SCHEMA_VERSION,
    NETWORK_JOIN_IMPORT_RESULT_SCHEMA_VERSION,
    encode_network_join_blob,
    worker_join_patch_from_blob,
)
from mediapipeline.core.network.auth import generate_token
from mediapipeline.core.network.library_roots import library_roots_from_config
from mediapipeline.core.network.path_map import parse_source_path_map
from mediapipeline.core.network.registry import InFlightRegistry
from mediapipeline.core.network.url_policy import redact_network_secret_text, redact_url
from mediapipeline.core.network.url_policy import validate_coordinator_url
from mediapipeline.core.network.worker_state import load_worker_state
from mediapipeline.core.processes.pipeline_policy import configured_network_role
from mediapipeline.core.paths.contracts import ResolvedPaths

if TYPE_CHECKING:
    from mediapipeline.core.kernel.dto_workspaces import NetworkWorkersDto


_log = logging.getLogger(__name__)
from mediapipeline.core.network.facade_contract import (
    NETWORK_COORDINATOR_DISCOVERY_SCHEMA_VERSION,
    NETWORK_TEST_CONNECTION_SCHEMA_VERSION,
)
from mediapipeline.core.network.facade_connectivity import *  # noqa: F403
from mediapipeline.core.network.facade_policy import *  # noqa: F403

def _bounded_network_detail(value: Any, *, limit: int = 240) -> str:
    text = redact_network_secret_text(value).strip()
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 3)] + "..."


def _test_layer(key: str, label: str, ok: bool, detail: str, **extra: Any) -> dict[str, Any]:
    return {
        "key": key,
        "label": label,
        "status": "pass" if ok else "fail",
        "ok": bool(ok),
        "detail": detail,
        **extra,
    }


def _coordinator_endpoint_parts(value: Any) -> tuple[str, str, int, str]:
    try:
        normalized = validate_coordinator_url(str(value or ""))
    except ValueError as exc:
        return "", "", 0, _bounded_network_detail(exc)
    parsed = urlsplit(normalized)
    host = str(parsed.hostname or "")
    try:
        port = int(parsed.port or 0)
    except ValueError:
        return normalized, host, 0, "WorkerCoordinatorUrl port must be in 1..65535."
    return normalized, host, port, ""


def _network_tcp_probe(coordinator_url: Any, *, timeout_seconds: float) -> dict[str, Any]:
    normalized, host, port, error = _coordinator_endpoint_parts(coordinator_url)
    if error:
        return _test_layer(
            "l1_tcp",
            "L1 TCP coordinator reachability",
            False,
            error,
            coordinator_url=redact_url(coordinator_url),
            host=host,
            port=port,
        )
    try:
        with socket.create_connection((host, port), timeout=max(0.1, float(timeout_seconds))):
            pass
    except Exception as exc:
        return _test_layer(
            "l1_tcp",
            "L1 TCP coordinator reachability",
            False,
            f"Cannot reach {redact_url(normalized)}: {_bounded_network_detail(exc)}",
            coordinator_url=redact_url(normalized),
            host=host,
            port=port,
        )
    return _test_layer(
        "l1_tcp",
        "L1 TCP coordinator reachability",
        True,
        f"TCP connect succeeded for {redact_url(normalized)}.",
        coordinator_url=redact_url(normalized),
        host=host,
        port=port,
    )


def _network_auth_ping_probe(
    coordinator_url: Any,
    token: Any,
    *,
    timeout_seconds: float,
    probe_worker_auth_func: Any,
) -> dict[str, Any]:
    normalized, _host, _port, error = _coordinator_endpoint_parts(coordinator_url)
    if error:
        return _test_layer(
            "l2_auth",
            "L2 signed coordinator auth ping",
            False,
            error,
            coordinator_url=redact_url(coordinator_url),
            status_code=None,
        )
    try:
        result = probe_worker_auth_func(normalized, str(token or ""), timeout_seconds=max(1, int(timeout_seconds)))
    except Exception as exc:
        return _test_layer(
            "l2_auth",
            "L2 signed coordinator auth ping",
            False,
            _bounded_network_detail(exc),
            coordinator_url=redact_url(normalized),
            status_code=None,
        )
    return _test_layer(
        "l2_auth",
        "L2 signed coordinator auth ping",
        bool(result.ok),
        result.detail,
        coordinator_url=redact_url(normalized),
        status_code=result.status_code,
    )


def _add_test_path(rows: list[dict[str, Any]], seen: set[tuple[str, str]], *, library_id: str, path_kind: str, path: Any) -> None:
    text = str(path or "").strip()
    if not text:
        return
    key = (path_kind, text.rstrip("\\/").casefold())
    if key in seen:
        return
    seen.add(key)
    rows.append(
        {
            "library_id": library_id or "default",
            "path_kind": path_kind,
            "path": text,
        }
    )


def _configured_worker_library_paths(resolved: ResolvedPaths) -> tuple[list[dict[str, Any]], list[str]]:
    config = dict(resolved.config_data or {})
    rows: list[dict[str, Any]] = []
    warnings: list[str] = []
    seen: set[tuple[str, str]] = set()
    try:
        profiles = effective_library_profiles_from_config(config)
    except Exception as exc:
        profiles = []
        warnings.append(f"LibraryProfiles could not be normalized for path checks: {_bounded_network_detail(exc)}")

    for profile in profiles:
        if profile.get("enabled", True) is False:
            continue
        library_id = str(profile.get("library_id") or profile.get("id") or "").strip()
        _add_test_path(
            rows,
            seen,
            library_id=library_id,
            path_kind="source_root",
            path=profile.get("effective_source_root") or profile.get("source_path"),
        )
        _add_test_path(
            rows,
            seen,
            library_id=library_id,
            path_kind="output_root",
            path=profile.get("effective_output_root") or profile.get("output_path"),
        )

    if not rows:
        _add_test_path(rows, seen, library_id="movies", path_kind="source_root", path=config.get("SourceMovies"))
        _add_test_path(rows, seen, library_id="tv", path_kind="source_root", path=config.get("SourceTV"))
        _add_test_path(rows, seen, library_id="default", path_kind="output_root", path=config.get("Outsource"))
    return rows, warnings


def _path_access_row(row: dict[str, Any]) -> dict[str, Any]:
    path_text = str(row.get("path") or "").strip()
    result = {
        **row,
        "ok": False,
        "exists": False,
        "is_dir": False,
        "status": "fail",
        "detail": "",
    }
    if not path_text:
        result["detail"] = "Path is not configured."
        return result
    try:
        path = Path(path_text)
        is_dir = path.is_dir()
        exists = is_dir or path.exists()
    except Exception as exc:
        result["detail"] = _bounded_network_detail(exc)
        return result
    result["exists"] = bool(exists)
    result["is_dir"] = bool(is_dir)
    result["ok"] = bool(is_dir)
    result["status"] = "pass" if is_dir else "fail"
    result["detail"] = "Directory is reachable." if is_dir else "Directory is not reachable from this worker."
    return result


def _network_path_access_probe(resolved: ResolvedPaths) -> dict[str, Any]:
    path_rows, warnings = _configured_worker_library_paths(resolved)
    checked = [_path_access_row(row) for row in path_rows]
    if not checked:
        return _test_layer(
            "l3_paths",
            "L3 worker library path access",
            False,
            "No worker library source/output roots are configured.",
            paths=[],
            warnings=warnings,
        )
    failed = [row for row in checked if not row.get("ok")]
    detail = (
        f"{len(checked)} configured worker path(s) are reachable."
        if not failed
        else f"{len(failed)} of {len(checked)} configured worker path(s) are unreachable."
    )
    return _test_layer(
        "l3_paths",
        "L3 worker library path access",
        not failed,
        detail,
        paths=checked,
        warnings=warnings,
    )


def _diagnostic_layer(key: str, label: str, status: str, detail: str) -> dict[str, Any]:
    return {
        "key": key,
        "label": label,
        "status": status,
        "detail": detail,
        "read_only": True,
    }


def _network_diagnostic_layers(
    *,
    resolved: ResolvedPaths,
    role: str,
    rows: list[dict[str, Any]],
    worker_state: dict[str, Any],
    state_files: list[dict[str, Any]],
    coordinator_connectivity: dict[str, Any],
    token_posture: dict[str, Any],
    heartbeat_timeout_seconds: int | None,
) -> dict[str, Any]:
    """Build cheap read-only network layer evidence without live probes."""
    config = dict(resolved.config_data or {})
    layers: list[dict[str, Any]] = []

    if role == "worker":
        target = redact_url(config.get("WorkerCoordinatorUrl"))
        url_status = "ready" if target else "blocked"
        url_detail = f"WorkerCoordinatorUrl={target or 'not configured'}; run Test connection for live TCP reachability."
    elif role == "coordinator":
        candidates = coordinator_connectivity.get("candidate_urls")
        url_status = "ready" if isinstance(candidates, list) and candidates else "review"
        url_detail = f"candidate_urls={len(candidates) if isinstance(candidates, list) else 0}; worker-facing URL={coordinator_connectivity.get('worker_coordinator_url') or 'not available'}."
    else:
        url_status = "not_applicable"
        url_detail = "Standalone mode does not use a worker coordinator URL."
    layers.append(_diagnostic_layer("url_reachable", "URL reachability", url_status, url_detail))

    worker_token_status = str(((token_posture.get("worker") or {}) if isinstance(token_posture, dict) else {}).get("status") or "")
    coordinator_token_status = str(((token_posture.get("coordinator") or {}) if isinstance(token_posture, dict) else {}).get("status") or "")
    if role == "worker":
        auth_status = "ready" if worker_token_status == "present" else "blocked"
        auth_detail = f"Worker auth token posture={worker_token_status or 'unknown'}; token value hidden."
    elif role == "coordinator":
        auth_status = "ready" if coordinator_token_status == "present" else "review"
        auth_detail = f"Coordinator auth token posture={coordinator_token_status or 'unknown'}; token value hidden."
    else:
        auth_status = "not_applicable"
        auth_detail = "Standalone mode does not use network worker auth."
    layers.append(_diagnostic_layer("auth_ok", "Auth posture", auth_status, auth_detail))

    path_rows, path_warnings = _configured_worker_library_paths(resolved)
    path_map_entries = parse_source_path_map(str(config.get("WorkerSourcePathMap") or ""))
    if role == "worker":
        path_status = "ready" if path_rows else "blocked"
        path_detail = (
            f"configured roots={len(path_rows)}; path_map_entries={len(path_map_entries)}; "
            "run Test connection for live worker filesystem reachability."
        )
        if path_warnings:
            path_status = "review"
            path_detail += f" warnings={len(path_warnings)}."
    elif role == "coordinator":
        path_status = "ready" if path_rows else "review"
        path_detail = f"configured source/output roots={len(path_rows)}; worker path maps are validated on worker machines."
    else:
        path_status = "not_applicable"
        path_detail = "Standalone mode uses local paths through normal pipeline validation."
    layers.append(_diagnostic_layer("paths_ok", "Path access posture", path_status, path_detail))

    state_by_key = {str(item.get("key") or ""): item for item in state_files if isinstance(item, dict)}
    queue_file = state_by_key.get("coordinator_inflight") or {}
    queue_age = queue_file.get("age_seconds")
    queue_status = str(queue_file.get("status") or "")
    fresh_limit = max(300, int(heartbeat_timeout_seconds or 0) * 2)
    if queue_status == "present" and isinstance(queue_age, int):
        fresh = queue_age <= fresh_limit
        freshness_status = "ready" if fresh else "review"
        freshness_detail = f"coordinator_inflight age={queue_age}s; freshness limit={fresh_limit}s."
    elif role == "coordinator":
        freshness_status = "review"
        freshness_detail = f"coordinator_inflight status={queue_status or 'missing'}."
    else:
        freshness_status = "not_applicable"
        freshness_detail = "Coordinator in-flight registry freshness is only available on coordinator state."
    layers.append(_diagnostic_layer("queue_fresh", "Queue freshness", freshness_status, freshness_detail))

    if worker_state.get("pending_done_report"):
        claim_status = "blocked"
        claim_detail = f"pending_done_report=yes; job={worker_state.get('job_id') or 'unknown'}."
    elif worker_state.get("job_id"):
        claim_status = "ready"
        claim_detail = f"active local worker claim={worker_state.get('job_id')}."
    else:
        failed_rows = [row for row in rows if row.get("last_failure_reason_code")]
        active_rows = [row for row in rows if str(row.get("status") or "").lower() not in {"idle", "done", "complete", "ready"}]
        if failed_rows:
            claim_status = "review"
            codes = ", ".join(str(row.get("last_failure_reason_code")) for row in failed_rows[:3])
            claim_detail = f"last worker failure reason_code={codes}."
        elif active_rows:
            claim_status = "ready"
            claim_detail = f"active persisted worker rows={len(active_rows)}."
        elif rows:
            claim_status = "ready"
            claim_detail = f"idle persisted worker rows={len(rows)}."
        elif role in {"worker", "coordinator"}:
            claim_status = "review"
            claim_detail = "No current claim or persisted worker rows are visible."
        else:
            claim_status = "not_applicable"
            claim_detail = "Standalone mode does not claim network jobs."
    layers.append(_diagnostic_layer("last_claim_result", "Last claim result", claim_status, claim_detail))

    by_key = {str(layer["key"]): str(layer["status"]) for layer in layers}
    return {
        "schema_version": "desktop_network_diagnostic_layers.v1",
        "url_reachable": by_key.get("url_reachable", "unknown"),
        "auth_ok": by_key.get("auth_ok", "unknown"),
        "paths_ok": by_key.get("paths_ok", "unknown"),
        "queue_fresh": by_key.get("queue_fresh", "unknown"),
        "last_claim_result": by_key.get("last_claim_result", "unknown"),
        "layers": layers,
        "summary_lines": [f"{layer['key']}: {layer['status']} - {layer['detail']}" for layer in layers],
        "read_only": True,
    }


def _network_test_timeout(request: dict[str, Any]) -> float:
    try:
        value = float(request.get("timeout_seconds", 4))
    except (TypeError, ValueError):
        value = 4.0
    return max(1.0, min(30.0, value))


def _network_discovery_timeout(request: dict[str, Any]) -> float:
    try:
        value = float(request.get("timeout_seconds", 3))
    except (TypeError, ValueError):
        value = 3.0
    return max(0.1, min(10.0, value))


def _coordinator_discovery_row(value: Any) -> tuple[dict[str, Any] | None, str]:
    text = str(value or "").strip()
    if not text:
        return None, "mDNS discovery returned an empty coordinator URL."
    try:
        normalized = validate_coordinator_url(text)
        parsed = urlsplit(normalized)
        host = str(parsed.hostname or "").strip()
        port = int(parsed.port or 0)
    except Exception as exc:
        return None, f"Ignored invalid mDNS coordinator URL {redact_url(text) or text!r}: {_bounded_network_detail(exc)}"
    return (
        {
            "url": redact_url(normalized),
            "host": host,
            "port": port,
            "source": "mdns",
            "selectable": True,
        },
        "",
    )


def _operator_summary_lines(
    *,
    resolved: ResolvedPaths,
    mode: str,
    runtime_status_label: str,
    runtime_status_severity: str,
    lifecycle_state: dict[str, Any],
    coordinator_connectivity: dict[str, Any],
    worker_state: dict[str, Any],
    active_count: int,
    idle_count: int,
    warnings: list[str],
    token_posture: dict[str, Any],
    running_vs_saved: dict[str, Any],
) -> list[str]:
    target_role = "worker" if mode == "worker" else "coordinator" if mode in {"coordinator", "coordinator_local"} else ""
    role_state = lifecycle_state.get(target_role) if target_role else {}
    coordinator_url = redact_url(
        coordinator_connectivity.get("worker_coordinator_url")
        or _config_text(resolved, "WorkerCoordinatorUrl", "not configured")
    )
    launch_line = (
        "Normal Launch: available in Standalone mode."
        if mode == "standalone"
        else "Normal Launch: blocked in this network mode; use Network Lifecycle controls."
    )
    if mode not in {"standalone", "coordinator", "worker", "coordinator_local"}:
        launch_line = "Normal Launch: blocked because NetworkRole is unknown or malformed."
    lines = [
        f"Mode: {_visible_network_mode_label(mode)}.",
        f"Runtime: {runtime_status_label} ({runtime_status_severity}).",
        launch_line,
    ]
    if target_role:
        lines.append(f"Lifecycle state: {target_role} {str((role_state or {}).get('status') or 'unknown')}.")
    if mode == "worker":
        lines.extend(
            [
                f"Coordinator target: {coordinator_url or 'not configured'}.",
                f"Worker current claim: {worker_state.get('job_id') or 'none'}.",
                f"Pending done recovery: {'yes' if worker_state.get('pending_done_report') else 'no'}.",
            ]
        )
        lines.extend(str(line) for line in running_vs_saved.get("summary_lines", []) if str(line).strip())
    elif mode in {"coordinator", "coordinator_local"}:
        lines.extend(
            [
                f"Worker-facing coordinator URL: {coordinator_url or 'not available'}.",
                f"Workers: active={active_count}; idle={idle_count}.",
                f"Local worker enabled: {'yes' if mode == 'coordinator_local' else 'no'}.",
            ]
        )
    lines.extend(str(line) for line in token_posture.get("summary_lines", []) if str(line).strip())
    if warnings:
        lines.append(f"Warnings: {len(warnings)}; inspect worker rows, state files, and cluster log.")
    lines.append(
        "Restart note: if backend Python files were updated while this app/API was already running, restart the app/API before using lifecycle controls."
    )
    return lines



__all__ = [
    "_bounded_network_detail",
    "_test_layer",
    "_coordinator_endpoint_parts",
    "_network_tcp_probe",
    "_network_auth_ping_probe",
    "_add_test_path",
    "_configured_worker_library_paths",
    "_path_access_row",
    "_network_path_access_probe",
    "_diagnostic_layer",
    "_network_diagnostic_layers",
    "_network_test_timeout",
    "_network_discovery_timeout",
    "_coordinator_discovery_row",
    "_operator_summary_lines",
]
