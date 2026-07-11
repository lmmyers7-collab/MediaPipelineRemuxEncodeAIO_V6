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

def _network_workers_dto(**fields: Any) -> NetworkWorkersDto:
    from mediapipeline.core.kernel.dto_workspaces import NetworkWorkersDto

    return NetworkWorkersDto(**fields)


class NetworkDiscoveryUnavailable(RuntimeError):
    """Raised when the desktop-owned coordinator discovery adapter is unavailable."""


def _network_role(resolved: ResolvedPaths) -> str:
    return configured_network_role(resolved.config_data or {})


def _config_text(resolved: ResolvedPaths, key: str, default: str = "") -> str:
    value = (resolved.config_data or {}).get(key)
    text = str(value).strip() if value is not None else ""
    return text or default


def _coordinator_port(resolved: ResolvedPaths) -> str:
    raw = _config_text(resolved, "CoordinatorPort", "7830")
    try:
        port = int(raw)
    except (TypeError, ValueError):
        return "7830"
    if port < 1 or port > 65535:
        return "7830"
    return str(port)


def _url_host(host: str) -> str:
    value = str(host or "").strip().strip("[]")
    if ":" in value and not value.startswith("["):
        return f"[{value}]"
    return value


def _http_endpoint(host: str, port: str) -> str:
    return f"http://{_url_host(host)}:{port}"


def _add_connect_candidate(candidates: list[dict[str, str]], *, label: str, host: str, port: str, source: str) -> None:
    host_text = str(host or "").strip()
    if not host_text:
        return
    url = _http_endpoint(host_text, port)
    if any(item.get("url") == url for item in candidates):
        return
    candidates.append({"label": label, "url": url, "host": host_text, "source": source})


def _is_wildcard_bind(bind_address: str) -> bool:
    return str(bind_address or "").strip().lower() in {"", "*", "0.0.0.0", "::", "[::]"}


def _is_loopback_bind(bind_address: str) -> bool:
    value = str(bind_address or "").strip().strip("[]").lower()
    if value in {"localhost", "127.0.0.1", "::1"}:
        return True
    try:
        return ipaddress.ip_address(value).is_loopback
    except ValueError:
        return False


def _private_lan_ip_candidates() -> list[str]:
    candidates: list[str] = []

    def add_ip(value: object) -> None:
        text = str(value or "").strip()
        if not text or text in candidates:
            return
        try:
            parsed = ipaddress.ip_address(text)
        except ValueError:
            return
        if parsed.version != 4 or parsed.is_loopback or parsed.is_link_local:
            return
        candidates.append(text)

    try:
        hostname = socket.gethostname()
        for result in socket.getaddrinfo(hostname, None, family=socket.AF_INET, type=socket.SOCK_STREAM):
            add_ip(result[4][0])
    except OSError:
        pass

    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.connect(("8.8.8.8", 80))
            add_ip(sock.getsockname()[0])
    except OSError:
        pass

    private_first = [ip for ip in candidates if ipaddress.ip_address(ip).is_private]
    public_rest = [ip for ip in candidates if not ipaddress.ip_address(ip).is_private]
    return private_first + public_rest


def _coordinator_connectivity(resolved: ResolvedPaths, role: str) -> dict[str, Any]:
    bind_address = _config_text(resolved, "CoordinatorBindAddress", "0.0.0.0")
    port = _coordinator_port(resolved)
    bind_endpoint = f"{bind_address}:{port}"
    saved_worker_url = _config_text(resolved, "WorkerCoordinatorUrl", "")
    candidates: list[dict[str, str]] = []
    warnings: list[str] = []
    primary_url = ""

    if role == "coordinator":
        if _is_wildcard_bind(bind_address):
            hostname = str(socket.gethostname() or "").strip()
            if hostname and hostname.casefold() not in {"localhost", "0.0.0.0"}:
                _add_connect_candidate(candidates, label="Computer name", host=hostname, port=port, source="socket.gethostname")
            for ip in _private_lan_ip_candidates():
                _add_connect_candidate(candidates, label="LAN IP", host=ip, port=port, source="local_ipv4")
            if not candidates:
                _add_connect_candidate(candidates, label="Local machine only", host="127.0.0.1", port=port, source="fallback_loopback")
                warnings.append("Coordinator bind is wildcard, but no LAN hostname or IP was discovered; remote workers may need the machine's LAN IP.")
        else:
            label = "Loopback URL" if _is_loopback_bind(bind_address) else "Configured bind URL"
            _add_connect_candidate(candidates, label=label, host=bind_address, port=port, source="CoordinatorBindAddress")
            if _is_loopback_bind(bind_address):
                warnings.append("Coordinator bind address is loopback; workers on other machines cannot reach it.")
        primary_url = candidates[0]["url"] if candidates else ""
    elif role == "worker":
        primary_url = redact_url(saved_worker_url)
        if saved_worker_url:
            candidates.append(
                {
                    "label": "Saved worker target",
                    "url": redact_url(saved_worker_url),
                    "host": "",
                    "source": "WorkerCoordinatorUrl",
                }
            )

    summary_lines = [
        f"Worker coordinator URL: {primary_url or 'not available'}",
        f"Coordinator bind endpoint: {bind_endpoint}",
    ]
    if role == "coordinator":
        summary_lines.append("Use the worker coordinator URL in WorkerCoordinatorUrl on worker machines; do not use 0.0.0.0 as a worker target.")
    elif role == "worker":
        summary_lines.append("Worker mode uses the saved WorkerCoordinatorUrl value.")
    else:
        summary_lines.append("Standalone mode does not expose a worker coordinator URL.")

    return {
        "schema_version": "desktop_network_coordinator_connectivity.v1",
        "role": role,
        "bind_address": bind_address,
        "port": port,
        "bind_endpoint": bind_endpoint,
        "worker_coordinator_url": primary_url,
        "candidate_urls": candidates,
        "warnings": warnings,
        "summary_lines": summary_lines,
        "read_only": True,
    }


def _runtime_state_dir(resolved: ResolvedPaths, service: object) -> Path:
    app_state_path = getattr(resolved, "app_state_path", None) or getattr(service, "app_state_path", None)
    if app_state_path:
        return Path(app_state_path).parent
    if resolved.state_root is not None:
        return Path(resolved.state_root) / "App"
    return Path(resolved.app_root)


def _iso_age_seconds(value: object) -> int | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=UTC)
        return max(0, int((datetime.now(UTC) - parsed.astimezone(UTC)).total_seconds()))
    except Exception:
        return None


def _clamped_percent(value: object) -> float | None:
    if value is None or value == "":
        return None
    try:
        numeric = float(str(value))
    except (TypeError, ValueError):
        return None
    if not (numeric == numeric):
        return None
    return max(0.0, min(100.0, numeric))


def _progress_id(*parts: object) -> str:
    text = "_".join(str(part or "") for part in parts if str(part or "").strip())
    normalized = re.sub(r"[^a-z0-9]+", "_", text.casefold()).strip("_")
    return normalized or "network_worker"


def _heartbeat_timeout_seconds(resolved: ResolvedPaths) -> int | None:
    raw = (resolved.config_data or {}).get("CoordinatorHeartbeatTimeoutMins")
    try:
        minutes = float(str(raw))
    except (TypeError, ValueError):
        return None
    if minutes <= 0:
        return None
    return int(minutes * 60)


def _worker_bar_status(row: dict[str, Any], *, heartbeat_timeout_seconds: int | None) -> str:
    status = str(row.get("status") or "").casefold()
    stage = str(row.get("current_stage") or "").casefold()
    age = row.get("heartbeat_age_seconds")
    if any(token in status or token in stage for token in ("fail", "error", "offline", "reclaimed")):
        return "blocked"
    if heartbeat_timeout_seconds is not None and isinstance(age, int) and age > heartbeat_timeout_seconds:
        return "blocked"
    if any(token in status or token in stage for token in ("active", "running", "working", "claimed", "busy", "encoding", "remux")):
        return "active"
    if any(token in status or token in stage for token in ("idle", "done", "complete", "ready")):
        return "complete"
    if age is not None:
        return "warning"
    return "unknown"


def _worker_bar_detail(row: dict[str, Any]) -> str:
    bits = []
    if row.get("current_file_name") or row.get("current_file") or row.get("source_file"):
        bits.append(f"file={row.get('current_file_name') or row.get('current_file') or row.get('source_file')}")
    if row.get("current_stage"):
        bits.append(f"stage={row.get('current_stage')}")
    if row.get("heartbeat_age_seconds") is not None:
        bits.append(f"heartbeat_age={row.get('heartbeat_age_seconds')}s")
    if row.get("job_id"):
        bits.append(f"job={row.get('job_id')}")
    if row.get("error"):
        bits.append(f"error={redact_network_secret_text(row.get('error'))}")
    return "; ".join(str(bit) for bit in bits if bit) or "No worker detail reported."


def _network_worker_progress_bars(
    *,
    role: str,
    rows: list[dict[str, Any]],
    worker_state: dict[str, Any],
    warnings: list[str],
    heartbeat_timeout_seconds: int | None,
) -> list[dict[str, Any]]:
    bars: list[dict[str, Any]] = []
    if role == "coordinator":
        mode_status = "active" if rows else "warning"
    elif role == "worker":
        mode_status = "active" if worker_state.get("job_id") else "idle"
    else:
        mode_status = "idle"
    bars.append(
        {
            "id": "network_mode",
            "label": "Runtime evidence",
            "mode": "indeterminate",
            "percent": None,
            "status": mode_status,
            "detail": f"role={role}; worker_rows={len(rows)}; warnings={len(warnings)}",
            "source": "desktop_network_workers.v1",
            "updated_at": datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
            "stale": False,
        }
    )
    for row in rows:
        percent = _clamped_percent(row.get("progress_percent"))
        status = _worker_bar_status(row, heartbeat_timeout_seconds=heartbeat_timeout_seconds)
        mode = "determinate" if percent is not None else "indeterminate" if status == "active" else "determinate"
        if percent is None and status == "complete":
            percent = 100.0
        elif percent is None and status != "active":
            percent = 0.0
        bars.append(
            {
                "id": f"network_worker_{_progress_id(row.get('worker_id'), row.get('job_id'), row.get('worker_name'))}",
                "label": str(row.get("worker_name") or row.get("worker_id") or "Worker"),
                "mode": mode,
                "percent": percent if mode != "indeterminate" else None,
                "status": status,
                "detail": _worker_bar_detail(row),
                "source": str(row.get("source") or "coordinator_inflight"),
                "updated_at": str(row.get("last_heartbeat") or ""),
                "stale": status == "blocked",
            }
        )
    if worker_state.get("job_id") or worker_state.get("source_file") or worker_state.get("pending_done_report"):
        pending_done = bool(worker_state.get("pending_done_report"))
        bars.append(
            {
                "id": "network_local_worker",
                "label": "Local worker",
                "mode": "indeterminate" if worker_state.get("job_id") and not pending_done else "determinate",
                "percent": 0.0 if pending_done else None if worker_state.get("job_id") else 100.0,
                "status": "warning" if pending_done else "active" if worker_state.get("job_id") else "idle",
                "detail": f"job={worker_state.get('job_id') or 'none'}; file={worker_state.get('source_file') or 'none'}; pending_done_report={'yes' if pending_done else 'no'}",
                "source": "worker_state.json",
                "updated_at": "",
                "stale": pending_done,
            }
        )
    return bars


def _network_worker_progress(
    *,
    role: str,
    rows: list[dict[str, Any]],
    worker_state: dict[str, Any],
    warnings: list[str],
    heartbeat_timeout_seconds: int | None,
) -> dict[str, Any]:
    bars = _network_worker_progress_bars(
        role=role,
        rows=rows,
        worker_state=worker_state,
        warnings=warnings,
        heartbeat_timeout_seconds=heartbeat_timeout_seconds,
    )
    active_count = sum(1 for bar in bars if bar.get("status") == "active")
    blocked_count = sum(1 for bar in bars if bar.get("status") == "blocked")
    warning_count = sum(1 for bar in bars if bar.get("status") == "warning")
    status = "blocked" if blocked_count else "warning" if warning_count else "active" if active_count else "idle"
    return {
        "schema_version": "desktop_network_worker_progress.v1",
        "mode": "worker_progress",
        "status": status,
        "active_count": active_count,
        "blocked_count": blocked_count,
        "warning_count": warning_count,
        "bar_count": len(bars),
        "progress_bars": bars,
        "summary_lines": [
            f"Worker progress: {status}",
            f"Role: {role}",
            f"Progress bars: {len(bars)}",
            f"Active worker bars: {active_count}",
            f"Blocked/stale worker bars: {blocked_count}",
            f"Warning worker bars: {warning_count}",
            "Mutation guardrail: Network progress is read-only persisted runtime evidence; WebView lifecycle controls must use backend-owned Network lifecycle routes and must not reclaim jobs, release claims, send done reports, mutate queue state, or touch media files.",
        ],
        "read_only": True,
    }


def _worker_row(entry: object, *, source: str) -> dict[str, Any]:
    to_dict = getattr(entry, "to_dict", None)
    row = dict(to_dict() if callable(to_dict) else {})
    current_file = str(row.get("current_file") or "")
    row["current_file_name"] = Path(current_file).name if current_file else ""
    row["heartbeat_age_seconds"] = _iso_age_seconds(row.get("last_heartbeat"))
    row["source"] = source
    return row


def _safe_worker_state(path: Path, warnings: list[str]) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = load_worker_state(path)
    except Exception as exc:
        safe_exc = f"{path.name}: {redact_network_secret_text(exc)}".strip()
        if len(safe_exc) > 240:
            safe_exc = safe_exc[:237] + "..."
        warnings.append(f"Worker state could not be read: {safe_exc}")
        _log.warning("Network worker_state read failed for %s: %s", path, safe_exc)
        return {
            "read_failed": True,
            "read_error": safe_exc,
        }
    source_path = str(payload.get("source_path") or "")
    return {
        "job_id": str(payload.get("job_id") or ""),
        "source_path": source_path,
        "source_file": Path(source_path).name if source_path else "",
        "pending_done_report": isinstance(payload.get("pending_done_report"), dict),
    }


def _state_file_row(key: str, label: str, path: Path, purpose: str) -> dict[str, Any]:
    row: dict[str, Any] = {
        "key": key,
        "label": label,
        "path": str(path),
        "purpose": purpose,
        "exists": False,
        "status": "missing",
        "size_bytes": 0,
        "modified_at": "",
        "age_seconds": None,
        "error": "",
        "read_only": True,
    }
    try:
        stat = path.stat()
    except FileNotFoundError:
        return row
    except OSError as exc:
        row["status"] = "unreadable"
        row["error"] = redact_network_secret_text(exc)
        return row

    modified = datetime.fromtimestamp(stat.st_mtime, UTC)
    row.update(
        {
            "exists": True,
            "status": "present",
            "size_bytes": int(stat.st_size),
            "modified_at": modified.isoformat(),
            "age_seconds": max(0, int((datetime.now(UTC) - modified).total_seconds())),
        }
    )
    return row


def _visible_network_mode(resolved: ResolvedPaths) -> str:
    role = _network_role(resolved)
    if role == "coordinator" and (resolved.config_data or {}).get("CoordinatorAlsoEncodeLocally") is True:
        return "coordinator_local"
    return role


def _visible_network_mode_label(mode: str) -> str:
    if mode == "coordinator_local":
        return "Coordinator + local worker"
    if mode == "coordinator":
        return "Coordinator only"
    if mode == "worker":
        return "Worker only"
    if mode == "standalone":
        return "Standalone"
    return f"Unknown ({mode})"


def _safe_lifecycle_state(owner: object, role: str) -> dict[str, Any]:
    state_for = getattr(owner, "_network_lifecycle_state_for", None)
    if not callable(state_for):
        return {
            "role": role,
            "status": "unknown",
            "state_scope": "unavailable",
            "read_only": True,
        }
    try:
        state = dict(state_for(role) or {})
    except Exception as exc:
        return {
            "role": role,
            "status": "unknown",
            "state_scope": "unreadable",
            "error": redact_network_secret_text(exc),
            "read_only": True,
        }
    state["role"] = str(state.get("role") or role)
    state["status"] = str(state.get("status") or "unknown")
    state["read_only"] = True
    return state


def _lifecycle_state(owner: object) -> dict[str, Any]:
    return {
        "schema_version": "desktop_network_lifecycle_state.v1",
        "source": "session_memory_only",
        "coordinator": _safe_lifecycle_state(owner, "coordinator"),
        "worker": _safe_lifecycle_state(owner, "worker"),
        "read_only": True,
    }


def _runtime_status_from_lifecycle(
    *,
    mode: str,
    lifecycle_state: dict[str, Any],
    worker_state: dict[str, Any],
    state_files: list[dict[str, Any]],
    warnings: list[str],
) -> tuple[str, str]:
    if mode not in {"standalone", "coordinator", "worker", "coordinator_local"}:
        return "Blocked", "blocked"
    if any(item.get("status") == "unreadable" for item in state_files):
        return "Blocked", "blocked"
    if worker_state.get("pending_done_report"):
        return "Blocked", "blocked"
    if mode == "standalone":
        return "Standalone", "match"
    runtime_role = "worker" if mode == "worker" else "coordinator"
    role_state = lifecycle_state.get(runtime_role) if isinstance(lifecycle_state, dict) else {}
    status = str((role_state or {}).get("status") or "unknown").strip().lower()
    if status == "running":
        return "Running", "match"
    if status == "stopped":
        if worker_state.get("job_id"):
            return "Stopped with stale worker claim", "warning"
        return "Stopped", "warning" if warnings else "match"
    if status in {"starting", "stopping"}:
        return status.title(), "warning"
    if status in {"blocked", "failed", "error"}:
        return "Blocked", "blocked"
    if status in {"unknown", ""}:
        return "Unknown", "warning"
    return str((role_state or {}).get("status") or "Unknown").title(), "warning"


def _worker_state_stale_against_lifecycle(
    *,
    mode: str,
    lifecycle_state: dict[str, Any],
    worker_state: dict[str, Any],
) -> bool:
    if not worker_state.get("job_id"):
        return False
    if mode not in {"worker", "coordinator_local"}:
        return False
    runtime_role = "worker" if mode == "worker" else "coordinator"
    role_state = lifecycle_state.get(runtime_role) if isinstance(lifecycle_state, dict) else {}
    return str((role_state or {}).get("status") or "").strip().lower() == "stopped"



__all__ = [
    "_network_workers_dto",
    "_network_role",
    "_config_text",
    "_coordinator_port",
    "_url_host",
    "_http_endpoint",
    "_add_connect_candidate",
    "_is_wildcard_bind",
    "_is_loopback_bind",
    "_private_lan_ip_candidates",
    "_coordinator_connectivity",
    "_runtime_state_dir",
    "_iso_age_seconds",
    "_clamped_percent",
    "_progress_id",
    "_heartbeat_timeout_seconds",
    "_worker_bar_status",
    "_worker_bar_detail",
    "_network_worker_progress_bars",
    "_network_worker_progress",
    "_worker_row",
    "_safe_worker_state",
    "_state_file_row",
    "_visible_network_mode",
    "_visible_network_mode_label",
    "_safe_lifecycle_state",
    "_lifecycle_state",
    "_runtime_status_from_lifecycle",
    "_worker_state_stale_against_lifecycle",
]
