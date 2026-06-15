"""Network runtime-state facade adapter."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
import hashlib
import ipaddress
import logging
from pathlib import Path
import re
import socket
from typing import TYPE_CHECKING, Any
from urllib.parse import urlsplit

from mediapipeline.core.config.library_profiles import effective_library_profiles_from_config
from mediapipeline.core.kernel.dto_commands import CommandResult
from mediapipeline.core.network.join import (
    NETWORK_JOIN_BLOB_RESULT_SCHEMA_VERSION,
    NETWORK_JOIN_IMPORT_RESULT_SCHEMA_VERSION,
    encode_network_join_blob,
    worker_join_patch_from_blob,
)
from mediapipeline.core.network.url_policy import redact_network_secret_text, redact_url
from mediapipeline.core.network.url_policy import validate_coordinator_url
from mediapipeline.core.processes.pipeline_policy import configured_network_role
from mediapipeline.desktop.models import ResolvedPaths
from mediapipeline.desktop.network.auth import generate_token
from mediapipeline.desktop.network.library_roots import library_roots_from_config
from mediapipeline.desktop.network.mdns import ZeroconfUnavailable, discover_coordinators
from mediapipeline.desktop.network.path_map import parse_source_path_map
from mediapipeline.desktop.network.probe import probe_worker_auth
from mediapipeline.desktop.network.registry import InFlightRegistry
from mediapipeline.desktop.network.worker_state import load_worker_state

if TYPE_CHECKING:
    from mediapipeline.desktop.application.dto_workspaces import NetworkWorkersDto


_log = logging.getLogger(__name__)
NETWORK_TEST_CONNECTION_SCHEMA_VERSION = "desktop_network_worker_test_connection.v1"
NETWORK_COORDINATOR_DISCOVERY_SCHEMA_VERSION = "desktop_network_coordinator_discovery.v1"


def _network_workers_dto(**fields: Any) -> "NetworkWorkersDto":
    from mediapipeline.desktop.application.dto_workspaces import NetworkWorkersDto

    return NetworkWorkersDto(**fields)


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
            parsed = parsed.replace(tzinfo=timezone.utc)
        return max(0, int((datetime.now(timezone.utc) - parsed.astimezone(timezone.utc)).total_seconds()))
    except Exception:
        return None


def _clamped_percent(value: object) -> float | None:
    if value is None or value == "":
        return None
    try:
        numeric = float(value)
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
        minutes = float(raw)
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
            "label": "Network mode",
            "mode": "determinate",
            "percent": 100.0,
            "status": mode_status,
            "detail": f"role={role}; worker_rows={len(rows)}; warnings={len(warnings)}",
            "source": "desktop_network_workers.v1",
            "updated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
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
            "Mutation guardrail: Network progress is read-only persisted runtime evidence; WebView does not start/stop workers, reclaim jobs, release claims, send done reports, mutate queue state, or touch media files.",
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
        safe_exc = redact_network_secret_text(exc)
        warnings.append(f"Worker state could not be read: {safe_exc}")
        _log.warning("Network worker_state read failed for %s: %s", path, safe_exc)
        return {}
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

    modified = datetime.fromtimestamp(stat.st_mtime, timezone.utc)
    row.update(
        {
            "exists": True,
            "status": "present",
            "size_bytes": int(stat.st_size),
            "modified_at": modified.isoformat(),
            "age_seconds": max(0, int((datetime.now(timezone.utc) - modified).total_seconds())),
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
        return "Stopped", "warning" if warnings else "match"
    if status in {"starting", "stopping"}:
        return status.title(), "warning"
    if status in {"blocked", "failed", "error"}:
        return "Blocked", "blocked"
    if status in {"unknown", ""}:
        return "Unknown", "warning"
    return str((role_state or {}).get("status") or "Unknown").title(), "warning"


def _token_posture(resolved: ResolvedPaths) -> dict[str, Any]:
    config = resolved.config_data or {}

    def token_row(value: Any, *, allow_generate: bool) -> dict[str, Any]:
        present = bool(str(value or "").strip())
        if present:
            status = "present"
            display = "present, hidden"
        elif allow_generate:
            status = "blank"
            display = "blank; coordinator can generate one on start"
        else:
            status = "missing"
            display = "missing; must match the coordinator token"
        return {
            "status": status,
            "display": display,
            "hidden": True,
            "auto_generate_if_blank": allow_generate,
        }

    return {
        "schema_version": "desktop_network_token_posture.v1",
        "coordinator": token_row(config.get("CoordinatorAuthToken"), allow_generate=True),
        "worker": token_row(config.get("WorkerAuthToken"), allow_generate=False),
        "summary_lines": [
            f"Coordinator token: {token_row(config.get('CoordinatorAuthToken'), allow_generate=True)['display']}.",
            f"Worker token: {token_row(config.get('WorkerAuthToken'), allow_generate=False)['display']}.",
            "Token values are hidden; workers must use the same shared token as the coordinator.",
        ],
        "read_only": True,
    }


def _fingerprint_text(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:8]


def _path_map_fingerprint(mappings: list[tuple[str, str]]) -> str:
    if not mappings:
        return ""
    material = "\n".join(f"{source}\0{target}" for source, target in mappings)
    return _fingerprint_text(material)


def _path_map_descriptor(raw: Any) -> dict[str, Any]:
    mappings = parse_source_path_map(str(raw or "").strip())
    return {
        "path_map_entries": len(mappings),
        "path_map_fingerprint": _path_map_fingerprint(mappings),
    }


def _worker_url_compare_key(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    try:
        return f"valid:{validate_coordinator_url(text).casefold()}"
    except ValueError:
        return f"invalid:{redact_url(text).casefold()}"


def _worker_runtime_descriptor(owner: object) -> tuple[dict[str, Any] | None, str]:
    runtime = getattr(owner, "_network_dispatcher_runtime", None)
    if not isinstance(runtime, dict):
        return None, ""
    entry = runtime.get("worker")
    if not isinstance(entry, dict):
        return None, ""
    dispatcher = entry.get("dispatcher")
    if dispatcher is None:
        return None, ""
    try:
        descriptor_func = getattr(dispatcher, "runtime_descriptor", None)
        if callable(descriptor_func):
            raw_descriptor = dict(descriptor_func() or {})
        else:
            mappings = list(getattr(dispatcher, "_source_path_map", []) or [])
            raw_descriptor = {
                "coordinator_url": str(getattr(dispatcher, "coordinator_url", "") or ""),
                "token_fingerprint": _fingerprint_text(getattr(dispatcher, "_auth_token", "")),
                "path_map_entries": len(mappings),
                "path_map_fingerprint": _path_map_fingerprint(mappings),
            }
    except Exception as exc:
        return None, redact_network_secret_text(exc)

    try:
        path_map_entries = int(raw_descriptor.get("path_map_entries") or 0)
    except (TypeError, ValueError):
        path_map_entries = 0
    return {
        "coordinator_url": redact_url(raw_descriptor.get("coordinator_url")),
        "token_fingerprint": str(raw_descriptor.get("token_fingerprint") or ""),
        "path_map_entries": max(0, path_map_entries),
        "path_map_fingerprint": str(raw_descriptor.get("path_map_fingerprint") or ""),
    }, ""


def _field_label(field: str) -> str:
    return {
        "coordinator_url": "Coordinator URL",
        "worker_auth_token": "Worker auth token fingerprint",
        "source_path_map": "Worker source path map",
    }.get(field, field.replace("_", " "))


def _worker_running_vs_saved(owner: object, resolved: ResolvedPaths) -> dict[str, Any]:
    config = resolved.config_data or {}
    saved_map = _path_map_descriptor(config.get("WorkerSourcePathMap"))
    saved = {
        "coordinator_url": redact_url(config.get("WorkerCoordinatorUrl")),
        "token_fingerprint": _fingerprint_text(config.get("WorkerAuthToken")),
        **saved_map,
    }
    running, error = _worker_runtime_descriptor(owner)
    if error:
        return {
            "schema_version": "desktop_network_worker_running_vs_saved.v1",
            "status": "unknown",
            "running": {},
            "saved": saved,
            "drift_fields": [],
            "summary_lines": [
                "Worker settings drift: unavailable.",
                f"Reason: {error}",
            ],
            "read_only": True,
        }
    if running is None:
        return {
            "schema_version": "desktop_network_worker_running_vs_saved.v1",
            "status": "not_running",
            "running": {},
            "saved": saved,
            "drift_fields": [],
            "summary_lines": [
                "Worker settings drift: not running.",
                "Saved worker settings will be used the next time worker polling starts.",
            ],
            "read_only": True,
        }

    drift_fields: list[str] = []
    if _worker_url_compare_key(running.get("coordinator_url")) != _worker_url_compare_key(config.get("WorkerCoordinatorUrl")):
        drift_fields.append("coordinator_url")
    if str(running.get("token_fingerprint") or "") != str(saved.get("token_fingerprint") or ""):
        drift_fields.append("worker_auth_token")
    if (
        int(running.get("path_map_entries") or 0) != int(saved.get("path_map_entries") or 0)
        or str(running.get("path_map_fingerprint") or "") != str(saved.get("path_map_fingerprint") or "")
    ):
        drift_fields.append("source_path_map")

    if drift_fields:
        labels = ", ".join(_field_label(field) for field in drift_fields)
        summary_lines = [
            f"Worker settings drift: running worker differs from saved config ({labels}).",
            "Restart worker polling from Network Lifecycle to reconnect with saved settings.",
        ]
        status = "drift"
    else:
        summary_lines = [
            "Worker settings drift: none.",
            "Running worker URL, auth-token fingerprint, and source path map match saved config.",
        ]
        status = "match"
    return {
        "schema_version": "desktop_network_worker_running_vs_saved.v1",
        "status": status,
        "running": running,
        "saved": saved,
        "drift_fields": drift_fields,
        "drift_field_labels": [_field_label(field) for field in drift_fields],
        "summary_lines": summary_lines,
        "read_only": True,
    }


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


def _network_auth_ping_probe(coordinator_url: Any, token: Any, *, timeout_seconds: float) -> dict[str, Any]:
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
        result = probe_worker_auth(normalized, str(token or ""), timeout_seconds=max(1, int(timeout_seconds)))
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
    path_map_entries = parse_source_path_map(config.get("WorkerSourcePathMap"))
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


class NetworkFacadeMixin:
    """Read-only network runtime-state adapter for local WebView/Tauri shells."""

    service: object
    app_version: str

    def _network_dispatcher_for_role(self, role: str) -> Any:
        runtime = getattr(self, "_network_dispatcher_runtime", None)
        if not isinstance(runtime, dict):
            return None
        entry = runtime.get(role)
        if not isinstance(entry, dict):
            return None
        return entry.get("dispatcher")

    def _load_coordinator_app_state_token(self) -> str:
        loader = getattr(self.service, "load_app_state", None)
        if not callable(loader):
            return ""
        try:
            state = loader()
        except Exception:
            return ""
        if not isinstance(state, dict):
            return ""
        return str(state.get("coordinator_auth_token", "") or "").strip()

    def _save_coordinator_app_state_token(self, token: str) -> tuple[bool, str]:
        saver = getattr(self.service, "save_app_state", None)
        if not callable(saver):
            return False, "save_app_state is unavailable; coordinator token was not persisted."
        try:
            saver({"coordinator_auth_token": token})
        except Exception as exc:
            return False, f"coordinator token app-state save failed: {redact_network_secret_text(exc)}"
        return True, ""

    def _coordinator_join_token(
        self,
        resolved: ResolvedPaths,
        *,
        rotate: bool,
    ) -> tuple[str, str, list[str], dict[str, Any]]:
        warnings: list[str] = []
        write_evidence: dict[str, Any] = {
            "writes_config": False,
            "writes_app_state": False,
            "running_coordinator_updated": False,
        }
        dispatcher = self._network_dispatcher_for_role("coordinator")
        config_token = str((resolved.config_data or {}).get("CoordinatorAuthToken", "") or "").strip()

        if rotate:
            token = generate_token()
            if config_token:
                save_result = self.save_settings_patch(
                    resolved,
                    {"changes": {"CoordinatorAuthToken": token}, "confirm_save": True},
                )
                if not save_result.ok:
                    safe_errors = [
                        redact_network_secret_text(error)
                        for error in list(save_result.errors or [])
                    ]
                    detail = "; ".join(safe_errors) if safe_errors else save_result.message
                    raise RuntimeError(f"CoordinatorAuthToken rotation save failed: {detail}")
                write_evidence["writes_config"] = True

            updater = getattr(dispatcher, "update_auth_token", None)
            if callable(updater):
                updater(token)
                write_evidence["running_coordinator_updated"] = True
                write_evidence["writes_app_state"] = True
                return token, "rotated_running_coordinator", warnings, write_evidence

            if not config_token:
                saved, message = self._save_coordinator_app_state_token(token)
                if not saved:
                    raise RuntimeError(message)
                write_evidence["writes_app_state"] = True
                return token, "rotated_app_state", warnings, write_evidence

            return token, "rotated_config", warnings, write_evidence

        getter = getattr(dispatcher, "get_auth_token", None)
        if callable(getter):
            token = str(getter() or "").strip()
            if token:
                return token, "running_coordinator", warnings, write_evidence
        if config_token:
            return config_token, "CoordinatorAuthToken", warnings, write_evidence
        app_state_token = self._load_coordinator_app_state_token()
        if app_state_token:
            return app_state_token, "app_state", warnings, write_evidence

        token = generate_token()
        saved, message = self._save_coordinator_app_state_token(token)
        if not saved:
            raise RuntimeError(message)
        write_evidence["writes_app_state"] = True
        return token, "generated_app_state", warnings, write_evidence

    def request_network_coordinator_join_blob(
        self,
        resolved: ResolvedPaths,
        request: dict[str, Any] | None = None,
    ) -> CommandResult:
        request = dict(request or {})
        data_base = {
            "schema_version": NETWORK_JOIN_BLOB_RESULT_SCHEMA_VERSION,
            "effect": "secret-transfer",
            "suppress_command_journal": True,
            "read_only_media": True,
            "would_not_touch": {
                "source_media": "no write/delete/rename/move",
                "scratch_media": "no create/delete/cleanup",
                "output_media": "no create/delete/overwrite/publish",
                "queue_state": "no claim, enqueue, dequeue, reorder, or launch",
                "pending_publish": "no drain/repair/move/delete",
                "lifecycle_state": "no coordinator or worker start/stop",
            },
        }
        if request.get("confirm_create") is not True:
            return CommandResult(
                command="network.coordinator.join_blob",
                ok=False,
                severity="warning",
                message="Network coordinator join blob creation requires confirm_create=true.",
                warnings=["confirm_create must be true because the response contains a worker auth secret."],
                refresh_hint="network",
                data={**data_base, "join_blob": ""},
            )

        role = _network_role(resolved)
        coordinator_url = str(request.get("coordinator_url") or "").strip()
        connectivity = _coordinator_connectivity(resolved, "coordinator")
        if not coordinator_url:
            coordinator_url = str(connectivity.get("worker_coordinator_url") or "").strip()
        rotate = request.get("rotate_token") is True
        if rotate and request.get("confirm_rotate") is not True:
            return CommandResult(
                command="network.coordinator.join_blob",
                ok=False,
                severity="warning",
                message="Network coordinator token rotation requires confirm_rotate=true.",
                warnings=["confirm_rotate must be true when rotate_token is true."],
                refresh_hint="network",
                data={**data_base, "join_blob": "", "coordinator_url": redact_url(coordinator_url)},
            )

        try:
            token, token_source, warnings, write_evidence = self._coordinator_join_token(
                resolved,
                rotate=rotate,
            )
            blob, payload = encode_network_join_blob(
                coordinator_url=coordinator_url,
                token=token,
                libraries=library_roots_from_config(resolved.config_data or {}),
                created_at_utc=datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
            )
        except Exception as exc:
            return CommandResult(
                command="network.coordinator.join_blob",
                ok=False,
                severity="error",
                message="Network coordinator join blob could not be created.",
                errors=[redact_network_secret_text(exc)],
                refresh_hint="network",
                data={
                    **data_base,
                    "join_blob": "",
                    "coordinator_url": redact_url(coordinator_url),
                    "role": role,
                },
            )

        libraries = list(payload.get("libraries", []))
        return CommandResult(
            command="network.coordinator.join_blob",
            ok=True,
            severity="info",
            message="Network coordinator join blob created. Treat it as a secret.",
            warnings=warnings,
            refresh_hint="network",
            data={
                **data_base,
                **write_evidence,
                "join_blob": blob,
                "role": role,
                "coordinator_url": redact_url(coordinator_url),
                "token_fingerprint": _fingerprint_text(token),
                "token_source": token_source,
                "rotated": rotate,
                "library_count": len(libraries),
                "libraries": libraries,
                "candidate_urls": connectivity.get("candidate_urls", []),
                "secret_handling": "join_blob contains the worker auth token; do not paste it into logs or support notes.",
            },
        )

    def request_network_worker_join_cluster(
        self,
        resolved: ResolvedPaths,
        request: dict[str, Any] | None = None,
    ) -> CommandResult:
        request = dict(request or {})
        data_base = {
            "schema_version": NETWORK_JOIN_IMPORT_RESULT_SCHEMA_VERSION,
            "effect": "config-write-and-read-only-test",
            "suppress_command_journal": True,
            "would_not_touch": {
                "source_media": "no write/delete/rename/move",
                "scratch_media": "no create/delete/cleanup",
                "output_media": "stat/readability checks only during test; no create/delete/overwrite/publish",
                "queue_state": "no claim, enqueue, dequeue, reorder, or launch",
                "pending_publish": "no drain/repair/move/delete",
                "lifecycle_state": "no coordinator or worker start/stop",
                "media_policy": "no FFmpeg, subtitle, audio, remux, encode, publish, or cleanup policy changed",
            },
        }
        if request.get("confirm_import") is not True:
            return CommandResult(
                command="network.worker.join_cluster",
                ok=False,
                severity="warning",
                message="Network worker join import requires confirm_import=true.",
                warnings=["confirm_import must be true because this saves worker network settings."],
                refresh_hint="network",
                data=data_base,
            )

        try:
            payload, desired_changes, plan = worker_join_patch_from_blob(
                request.get("join_blob"),
                resolved.config_data or {},
            )
        except Exception as exc:
            return CommandResult(
                command="network.worker.join_cluster",
                ok=False,
                severity="error",
                message="Network worker join blob could not be imported.",
                errors=[redact_network_secret_text(exc)],
                refresh_hint="network",
                data=data_base,
            )

        current_config = dict(resolved.config_data or {})
        changes_to_save = {
            key: value
            for key, value in desired_changes.items()
            if str(current_config.get(key, "") or "") != str(value or "")
        }
        settings_save: dict[str, Any]
        hot_apply: list[dict[str, Any]] = []
        warnings: list[str] = []
        if changes_to_save:
            save_result = self.save_settings_patch(
                resolved,
                {"changes": changes_to_save, "confirm_save": True},
            )
            warnings.extend(redact_network_secret_text(item) for item in list(save_result.warnings or []))
            if not save_result.ok:
                return CommandResult(
                    command="network.worker.join_cluster",
                    ok=False,
                    severity=save_result.severity or "error",
                    message="Network worker join import was blocked by settings save validation.",
                    errors=[redact_network_secret_text(item) for item in list(save_result.errors or [])],
                    warnings=warnings,
                    refresh_hint="network",
                    data={
                        **data_base,
                        "coordinator_url": redact_url(payload["coordinator_url"]),
                        "token_fingerprint": _fingerprint_text(payload["token"]),
                        "join_plan": plan,
                        "settings_save": {
                            "ok": False,
                            "message": redact_network_secret_text(save_result.message),
                            "changed_keys": sorted(changes_to_save),
                        },
                    },
                )
            hot_apply = list(save_result.data.get("network_worker_hot_apply", []) or [])
            settings_save = {
                "ok": True,
                "status": "saved",
                "message": save_result.message,
                "changed_keys": list(save_result.data.get("changed_keys", sorted(changes_to_save))),
            }
        else:
            settings_save = {
                "ok": True,
                "status": "already_current",
                "message": "Worker network settings already matched the join blob.",
                "changed_keys": [],
            }

        test_config = dict(current_config)
        test_config.update(desired_changes)
        test_resolved = replace(resolved, config_data=test_config)
        test_request: dict[str, Any] = {}
        if "timeout_seconds" in request:
            test_request["timeout_seconds"] = request.get("timeout_seconds")
        test_result = self.request_network_test_connection(test_resolved, test_request)
        warnings.extend(redact_network_secret_text(item) for item in list(test_result.warnings or []))

        ok = bool(test_result.ok)
        message = (
            "Network worker joined the cluster and test-connection passed."
            if ok
            else "Network worker settings were imported, but test-connection found blockers."
        )
        return CommandResult(
            command="network.worker.join_cluster",
            ok=ok,
            severity="info" if ok else test_result.severity,
            message=message,
            errors=[redact_network_secret_text(item) for item in list(test_result.errors or [])],
            warnings=warnings,
            refresh_hint="network",
            data={
                **data_base,
                "coordinator_url": redact_url(payload["coordinator_url"]),
                "token_fingerprint": _fingerprint_text(payload["token"]),
                "library_count": int(payload["library_count"]),
                "join_plan": plan,
                "settings_save": settings_save,
                "network_worker_hot_apply": hot_apply,
                "test_connection": test_result.to_mapping(),
            },
        )

    def request_network_worker_discover_coordinators(
        self,
        resolved: ResolvedPaths,
        request: dict[str, Any] | None = None,
    ) -> CommandResult:
        request = dict(request or {})
        timeout_seconds = _network_discovery_timeout(request)
        data_base = {
            "schema_version": NETWORK_COORDINATOR_DISCOVERY_SCHEMA_VERSION,
            "read_only": True,
            "effect": "none",
            "suppress_command_journal": True,
            "timeout_seconds": timeout_seconds,
            "zeroconf_available": True,
            "coordinators": [],
            "count": 0,
            "would_not_touch": {
                "source_media": "no write/delete/rename/move",
                "scratch_media": "no create/delete/cleanup",
                "output_media": "no create/delete/overwrite/publish",
                "queue_state": "no claim, enqueue, dequeue, reorder, or launch",
                "pending_publish": "no drain/repair/move/delete",
                "lifecycle_state": "no coordinator or worker start/stop",
                "settings": "discovery does not save WorkerCoordinatorUrl; selection only fills the UI",
                "media_policy": "no FFmpeg, subtitle, audio, remux, encode, publish, or cleanup policy changed",
            },
        }
        try:
            discovered_urls = discover_coordinators(timeout_secs=timeout_seconds)
        except ZeroconfUnavailable as exc:
            warning = _bounded_network_detail(exc)
            return CommandResult(
                command="network.worker.discover_coordinators",
                ok=False,
                severity="warning",
                message="mDNS coordinator discovery is unavailable because zeroconf is not installed.",
                warnings=[warning],
                refresh_hint="network",
                data={
                    **data_base,
                    "zeroconf_available": False,
                    "summary_lines": [
                        "mDNS coordinator discovery unavailable.",
                        warning,
                        "Manual WorkerCoordinatorUrl entry and coordinator join blobs remain available.",
                    ],
                },
            )
        except Exception as exc:
            return CommandResult(
                command="network.worker.discover_coordinators",
                ok=False,
                severity="error",
                message="mDNS coordinator discovery failed.",
                errors=[_bounded_network_detail(exc)],
                refresh_hint="network",
                data={
                    **data_base,
                    "summary_lines": [
                        "mDNS coordinator discovery failed before returning coordinator rows.",
                        "Manual WorkerCoordinatorUrl entry and coordinator join blobs remain available.",
                    ],
                },
            )

        coordinators: list[dict[str, Any]] = []
        warnings: list[str] = []
        seen_urls: set[str] = set()
        for raw_url in discovered_urls:
            row, warning = _coordinator_discovery_row(raw_url)
            if warning:
                warnings.append(warning)
            if row is None:
                continue
            url_key = str(row.get("url") or "").casefold()
            if url_key in seen_urls:
                continue
            seen_urls.add(url_key)
            coordinators.append(row)

        count = len(coordinators)
        summary_lines = [
            f"mDNS coordinator discovery returned {count} selectable coordinator(s).",
            "Effect: none.",
            "No files, queue, scratch, output, pending publish, lifecycle state, settings, or media policy were changed.",
        ]
        if not count:
            summary_lines.append("No coordinators were discovered; verify the coordinator is running on the LAN and that firewall/mDNS traffic is allowed.")
        return CommandResult(
            command="network.worker.discover_coordinators",
            ok=True,
            severity="info" if count else "warning",
            message=(
                "mDNS coordinator discovery completed."
                if count
                else "mDNS coordinator discovery completed with no coordinators found."
            ),
            warnings=warnings,
            refresh_hint="network",
            data={
                **data_base,
                "coordinators": coordinators,
                "count": count,
                "summary_lines": summary_lines,
            },
        )

    def request_network_test_connection(self, resolved: ResolvedPaths, request: dict[str, Any] | None = None) -> CommandResult:
        request = dict(request or {})
        config = dict(resolved.config_data or {})
        timeout_seconds = _network_test_timeout(request)
        l1_tcp = _network_tcp_probe(config.get("WorkerCoordinatorUrl"), timeout_seconds=timeout_seconds)
        l2_auth = _network_auth_ping_probe(
            config.get("WorkerCoordinatorUrl"),
            config.get("WorkerAuthToken"),
            timeout_seconds=timeout_seconds,
        )
        l3_paths = _network_path_access_probe(resolved)
        layers = {
            "l1_tcp": l1_tcp,
            "l2_auth": l2_auth,
            "l3_paths": l3_paths,
        }
        failed_layers = [
            layer
            for layer in layers.values()
            if not layer.get("ok")
        ]
        ok = not failed_layers
        transport_blocked = not l1_tcp.get("ok") or not l2_auth.get("ok")
        severity = "info" if ok else "error" if transport_blocked else "warning"
        message = (
            "Network worker test-connection passed."
            if ok
            else "Network worker test-connection found one or more blocked layers."
        )
        errors = [f"{layer.get('label')}: {layer.get('detail')}" for layer in failed_layers]
        warnings = [
            str(warning)
            for warning in l3_paths.get("warnings", [])
            if str(warning or "").strip()
        ]
        data = {
            "schema_version": NETWORK_TEST_CONNECTION_SCHEMA_VERSION,
            "read_only": True,
            "effect": "none",
            "dry_run_writes": [],
            "suppress_command_journal": True,
            "timeout_seconds": timeout_seconds,
            "overall_status": "pass" if ok else "fail",
            "coordinator_url": redact_url(config.get("WorkerCoordinatorUrl")),
            "layers": layers,
            "summary_lines": [
                f"L1 TCP reachability: {l1_tcp.get('status')}",
                f"L2 signed auth ping: {l2_auth.get('status')}",
                f"L3 worker path access: {l3_paths.get('status')}",
                "No files, queue, scratch, output, pending publish, lifecycle state, or media policy were changed.",
            ],
            "would_not_touch": {
                "source_media": "no write/delete/rename/move",
                "scratch_media": "no create/delete/cleanup",
                "output_media": "stat/readability checks only; no create/delete/overwrite/publish",
                "queue_state": "no claim, enqueue, dequeue, reorder, or launch",
                "pending_publish": "no drain/repair/move/delete",
                "lifecycle_state": "no coordinator or worker start/stop",
                "secrets": "auth token used only for signed ping; token value is not returned",
            },
        }
        return CommandResult(
            command="network.worker.test_connection",
            ok=ok,
            message=message,
            severity=severity,
            errors=errors,
            warnings=warnings,
            refresh_hint="network",
            data=data,
        )

    def get_network_workers(self, resolved: ResolvedPaths) -> NetworkWorkersDto:
        role = _network_role(resolved)
        mode = _visible_network_mode(resolved)
        state_dir = _runtime_state_dir(resolved, self.service)
        inflight_path = state_dir / "coordinator_inflight.json"
        worker_state_path = state_dir / "worker_state.json"
        cluster_log_path = state_dir / "cluster.log"
        warnings: list[str] = []
        rows: list[dict[str, Any]] = []
        coordinator_state_error = ""
        session_completed = 0
        session_failed = 0
        active_count = 0
        idle_count = 0

        if inflight_path.exists():
            registry = InFlightRegistry()
            if registry.load(inflight_path):
                active_entries = registry.snapshot()
                idle_entries = registry.idle_workers_snapshot()
                rows.extend(_worker_row(entry, source="coordinator_inflight") for entry in active_entries)
                rows.extend(_worker_row(entry, source="coordinator_inflight_stats") for entry in idle_entries)
                active_count = len(active_entries)
                idle_count = len(idle_entries)
                session_completed = int(registry.session_completed)
                session_failed = int(registry.session_failed)
                if active_entries:
                    warnings.append("Coordinator worker rows come from persisted in-flight state; heartbeat progress may lag the live dispatcher.")
            else:
                coordinator_state_error = "Coordinator in-flight state could not be read; inspect or regenerate coordinator_inflight.json before trusting worker rows."
                warnings.append(coordinator_state_error)
        elif role == "coordinator":
            warnings.append("No coordinator in-flight state file exists yet.")

        worker_state = _safe_worker_state(worker_state_path, warnings)
        if worker_state.get("pending_done_report"):
            warnings.append("Worker state contains a pending done report; the coordinator may not have accepted the last completion yet.")
        if role == "coordinator" and not rows:
            warnings.append("Coordinator worker board is empty from persisted state; confirm workers are polling the displayed Worker Coordinator URL.")

        state_files = [
            _state_file_row(
                "coordinator_inflight",
                "Coordinator in-flight registry",
                inflight_path,
                "Tracks active and idle worker rows persisted by the coordinator dispatcher.",
            ),
            _state_file_row(
                "worker_state",
                "Local worker state",
                worker_state_path,
                "Tracks the current local worker claim and any pending done report.",
            ),
            _state_file_row(
                "cluster_log",
                "Cluster log",
                cluster_log_path,
                "Records coordinator/worker network lifecycle and claim events.",
            ),
        ]
        if coordinator_state_error:
            for item in state_files:
                if item.get("key") == "coordinator_inflight":
                    item["status"] = "unreadable"
                    item["error"] = coordinator_state_error
                    break
        unreadable = [item for item in state_files if item.get("status") == "unreadable"]
        for item in unreadable:
            warnings.append(f"{item.get('label') or item.get('key')} could not be inspected: {item.get('error')}")
        coordinator_connectivity = _coordinator_connectivity(resolved, role)
        warnings.extend(str(warning) for warning in coordinator_connectivity.get("warnings", []) if str(warning).strip())
        running_vs_saved = _worker_running_vs_saved(self, resolved)
        if running_vs_saved.get("status") == "drift":
            labels = ", ".join(str(label) for label in running_vs_saved.get("drift_field_labels", []) if str(label))
            warnings.append(
                "Worker running settings differ from saved config"
                + (f": {labels}" if labels else ".")
            )
        token_posture = _token_posture(resolved)
        heartbeat_timeout_seconds = _heartbeat_timeout_seconds(resolved)
        diagnostic_layers = _network_diagnostic_layers(
            resolved=resolved,
            role=role,
            rows=rows,
            worker_state=worker_state,
            state_files=state_files,
            coordinator_connectivity=coordinator_connectivity,
            token_posture=token_posture,
            heartbeat_timeout_seconds=heartbeat_timeout_seconds,
        )
        worker_progress = _network_worker_progress(
            role=role,
            rows=rows,
            worker_state=worker_state,
            warnings=warnings,
            heartbeat_timeout_seconds=heartbeat_timeout_seconds,
        )
        lifecycle_state = _lifecycle_state(self)
        runtime_status_label, runtime_status_severity = _runtime_status_from_lifecycle(
            mode=mode,
            lifecycle_state=lifecycle_state,
            worker_state=worker_state,
            state_files=state_files,
            warnings=warnings,
        )
        if running_vs_saved.get("status") == "drift" and runtime_status_severity == "match":
            runtime_status_severity = "warning"
            if runtime_status_label == "Running":
                runtime_status_label = "Running with drift"
        operator_summary_lines = _operator_summary_lines(
            resolved=resolved,
            mode=mode,
            runtime_status_label=runtime_status_label,
            runtime_status_severity=runtime_status_severity,
            lifecycle_state=lifecycle_state,
            coordinator_connectivity=coordinator_connectivity,
            worker_state=worker_state,
            active_count=active_count,
            idle_count=idle_count,
            warnings=warnings,
            token_posture=token_posture,
            running_vs_saved=running_vs_saved,
        )

        return _network_workers_dto(
            app_version=self.app_version,
            role=role,
            source="runtime_state_files",
            coordinator_inflight_path=str(inflight_path),
            worker_state_path=str(worker_state_path),
            cluster_log_path=str(cluster_log_path),
            state_files=state_files,
            rows=rows,
            active_count=active_count,
            idle_count=idle_count,
            total_count=len(rows),
            session_completed=session_completed,
            session_failed=session_failed,
            worker_state=worker_state,
            coordinator_connectivity=coordinator_connectivity,
            worker_progress=worker_progress,
            progress_bars=list(worker_progress.get("progress_bars") or []),
            lifecycle_state=lifecycle_state,
            runtime_status_label=runtime_status_label,
            runtime_status_severity=runtime_status_severity,
            operator_summary_lines=operator_summary_lines,
            token_posture=token_posture,
            running_vs_saved=running_vs_saved,
            diagnostic_layers=diagnostic_layers,
            warnings=warnings,
        )

__all__ = [
    "NetworkFacadeMixin",
]
