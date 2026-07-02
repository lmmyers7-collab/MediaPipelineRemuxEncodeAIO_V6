from __future__ import annotations

from collections.abc import Callable, Mapping
from copy import deepcopy
from datetime import datetime, UTC
import json
from pathlib import Path
import subprocess
import sys
import time
from typing import Any

from mediapipeline.core.kernel.config_keys import (
    KEY_LIBRARY_PROFILES,
    KEY_LOCAL_BASE,
    KEY_MIN_FREE_SPACE_GB,
    KEY_OUTSOURCE,
    KEY_OUTSOURCE_MIN_FREE_SPACE_GB,
    KEY_SOURCE_MOVIES,
    KEY_SOURCE_TV,
)


CONFIGURED_PATH_HEALTH_SCHEMA_VERSION = "desktop_configured_path_health.v1"
DEFAULT_PATH_HEALTH_TIMEOUT_SECONDS = 1.0
LAUNCH_PATH_HEALTH_TIMEOUT_SECONDS = 5.0
PATH_HEALTH_UNC_RETRY_TIMEOUT_SECONDS = 2.0
PATH_HEALTH_UNC_RETRY_DELAY_SECONDS = 0.2
DEFAULT_PATH_HEALTH_CACHE_TTL_SECONDS = 30.0

PathProbeRunner = Callable[[str, float], Mapping[str, Any]]
_PATH_HEALTH_CACHE: dict[tuple[str, float], tuple[float, dict[str, Any]]] = {}
_PATH_HEALTH_CAPACITY_CACHE: dict[str, dict[str, Any]] = {}
_PATH_HEALTH_PROBE_SCRIPT = r"""
import json
from pathlib import Path
import shutil
import socket
import sys
import time


def unc_parts(path_text):
    normalized = str(path_text or "").strip().replace("/", "\\")
    lowered = normalized.casefold()
    if lowered.startswith("\\\\?\\unc\\"):
        remainder = normalized[8:]
    elif normalized.startswith("\\\\") and not lowered.startswith("\\\\?\\"):
        remainder = normalized[2:]
    else:
        return "", ""
    parts = [part for part in remainder.split("\\") if part]
    server = parts[0] if len(parts) >= 1 else ""
    share = parts[1] if len(parts) >= 2 else ""
    return server, share


def unc_share_root(path_text):
    server, share = unc_parts(path_text)
    if not server or not share:
        return ""
    return "\\\\" + server + "\\" + share


def elapsed_ms(started):
    return int((time.monotonic() - started) * 1000)


def run_phase(result, name, func):
    phase_started = time.monotonic()
    try:
        return func()
    finally:
        result["phase_timings_ms"][name] = elapsed_ms(phase_started)


path_text = sys.argv[1] if len(sys.argv) > 1 else ""
try:
    timeout_seconds = max(0.2, float(sys.argv[2] if len(sys.argv) > 2 else "2.0"))
except ValueError:
    timeout_seconds = 2.0
started = time.monotonic()
server, share = unc_parts(path_text)
share_root = unc_share_root(path_text)
result = {
    "path": path_text,
    "server": server,
    "share": share,
    "dns_status": "not_applicable",
    "tcp_445_status": "not_applicable",
    "exists": False,
    "path_kind": "missing",
    "can_list": False,
    "path_error": "",
    "list_error": "",
    "disk_error": "",
    "capacity_error": "",
    "capacity_source": "not_checked",
    "capacity_path": "",
    "total_bytes": None,
    "used_bytes": None,
    "free_bytes": None,
    "phase_timings_ms": {},
    "elapsed_ms": 0,
}
if server:
    def check_dns():
        try:
            socket.setdefaulttimeout(min(1.0, timeout_seconds))
            socket.getaddrinfo(server, 445)
            result["dns_status"] = "ready"
        except OSError as exc:
            result["dns_status"] = "blocked"
            result["dns_error"] = str(exc)

    def check_tcp():
        try:
            with socket.create_connection((server, 445), timeout=min(1.0, timeout_seconds)):
                result["tcp_445_status"] = "ready"
        except OSError as exc:
            result["tcp_445_status"] = "blocked"
            result["tcp_445_error"] = str(exc)

    run_phase(result, "dns", check_dns)
    run_phase(result, "tcp_445", check_tcp)
try:
    path = Path(path_text)
    def check_path():
        if path.exists():
            result["exists"] = True
            if path.is_dir():
                result["path_kind"] = "directory"
            elif path.is_file():
                result["path_kind"] = "file"
            else:
                result["path_kind"] = "other"

    run_phase(result, "path", check_path)
    if result["exists"]:
        if result["path_kind"] == "directory":
            def check_list():
                try:
                    iterator = path.iterdir()
                    next(iterator, None)
                    result["can_list"] = True
                except OSError as exc:
                    result["list_error"] = str(exc)

            def check_disk_configured():
                result["capacity_source"] = "configured_path"
                result["capacity_path"] = path_text
                try:
                    usage = shutil.disk_usage(str(path))
                    result["total_bytes"] = int(usage.total)
                    result["used_bytes"] = int(usage.used)
                    result["free_bytes"] = int(usage.free)
                except OSError as exc:
                    message = str(exc)
                    result["disk_error"] = message
                    result["capacity_error"] = message

            run_phase(result, "list", check_list)
            if result["can_list"]:
                run_phase(result, "disk_usage", check_disk_configured)
                if result["free_bytes"] is None and share_root and share_root.rstrip("\\").casefold() != path_text.rstrip("\\").casefold():
                    def check_disk_share_root():
                        try:
                            usage = shutil.disk_usage(share_root)
                            result["total_bytes"] = int(usage.total)
                            result["used_bytes"] = int(usage.used)
                            result["free_bytes"] = int(usage.free)
                            result["capacity_source"] = "share_root_fallback"
                            result["capacity_path"] = share_root
                        except OSError as exc:
                            fallback_message = str(exc)
                            if result["capacity_error"]:
                                result["capacity_error"] = result["capacity_error"] + "; share root fallback failed: " + fallback_message
                            else:
                                result["capacity_error"] = fallback_message
                        if result["free_bytes"] is None and not result["capacity_path"]:
                            result["capacity_path"] = share_root

                    run_phase(result, "disk_usage_share_root", check_disk_share_root)
        elif result["path_kind"] == "file":
            result["can_list"] = True
        else:
            result["can_list"] = True
except OSError as exc:
    result["path_error"] = str(exc)
finally:
    result["elapsed_ms"] = elapsed_ms(started)
print(json.dumps(result, ensure_ascii=False))
"""


def is_unc_path(path: Path | str | None) -> bool:
    if path is None:
        return False
    path_text = str(path).strip().replace("/", "\\")
    lower_path_text = path_text.casefold()
    return lower_path_text.startswith("\\\\?\\unc\\") or (
        path_text.startswith("\\\\") and not lower_path_text.startswith("\\\\?\\")
    )


def path_evidence(path: Path | None) -> tuple[str, list[str]]:
    """Return read-only launch evidence without probing network roots.

    UNC reachability is intentionally left to bounded scan/copy phases. A
    read-only launch preflight must not hang the operator surface on an SMB
    share.
    """
    if path is None:
        return "missing", []
    details = [f"path={path}"]
    if is_unc_path(path):
        details.append("exists=not checked")
        details.append("reason=network path existence checks are intentionally skipped during read-only preflight")
        return "network path not checked", details
    try:
        if path.exists():
            details.append("exists=yes")
            return "exists", details
        details.append("exists=no")
        return "missing on disk", details
    except OSError as exc:
        details.append(f"exists check failed={exc}")
        return "existence unknown", details


def configured_path_health(
    resolved: Any,
    *,
    timeout_seconds: float = DEFAULT_PATH_HEALTH_TIMEOUT_SECONDS,
    cache_ttl_seconds: float = DEFAULT_PATH_HEALTH_CACHE_TTL_SECONDS,
    probe_runner: PathProbeRunner | None = None,
) -> dict[str, Any]:
    """Return bounded read-only health for configured media/storage roots."""
    specs = configured_path_specs(resolved)
    rows = [
        _path_health_row(
            spec,
            timeout_seconds=timeout_seconds,
            cache_ttl_seconds=cache_ttl_seconds,
            probe_runner=probe_runner,
        )
        for spec in specs
    ]
    counts: dict[str, int] = {}
    for row in rows:
        status = str(row.get("status") or "unknown")
        counts[status] = counts.get(status, 0) + 1
    blocked_count = counts.get("blocked", 0)
    review_count = counts.get("review", 0)
    unknown_count = counts.get("unknown", 0)
    if blocked_count:
        operator_status = "blocked"
    elif review_count:
        operator_status = "review"
    elif unknown_count:
        operator_status = "unknown"
    elif rows:
        operator_status = "ready"
    else:
        operator_status = "unknown"
    warnings = [
        str(row.get("message") or "")
        for row in rows
        if str(row.get("status") or "").casefold() in {"review", "unknown"} and str(row.get("message") or "").strip()
    ]
    errors = [
        str(row.get("message") or "")
        for row in rows
        if str(row.get("status") or "").casefold() == "blocked" and str(row.get("message") or "").strip()
    ]
    return {
        "schema_version": CONFIGURED_PATH_HEALTH_SCHEMA_VERSION,
        "read_only": True,
        "checked_at_utc": _utc_now_text(),
        "probe_timeout_seconds": float(timeout_seconds),
        "cache_ttl_seconds": float(cache_ttl_seconds),
        "operator_status": operator_status,
        "operator_status_state": _path_health_status_state(operator_status),
        "operator_summary": _path_health_operator_summary(operator_status, rows, counts),
        "rows": rows,
        "row_count": len(rows),
        "ready_count": counts.get("ready", 0),
        "review_count": review_count,
        "blocked_count": blocked_count,
        "unknown_count": unknown_count,
        "counts": counts,
        "warnings": warnings[:12],
        "errors": errors[:12],
        "summary_lines": _path_health_summary_lines(operator_status, rows, counts),
        "guardrail": (
            "Read-only bounded path health. The backend checks configured roots only; "
            "it does not scan media, write test files, save settings, or mutate queue state."
        ),
    }


def configured_path_specs(resolved: Any) -> list[dict[str, Any]]:
    config = dict(getattr(resolved, "config_data", {}) or {})
    specs: list[dict[str, Any]] = []
    seen: dict[tuple[str, str], dict[str, Any]] = {}
    scratch_reserve_gb = _reserve_gb(config.get(KEY_MIN_FREE_SPACE_GB))
    output_reserve_gb = _reserve_gb(config.get(KEY_OUTSOURCE_MIN_FREE_SPACE_GB), fallback=scratch_reserve_gb)

    def add_spec(
        *,
        key: str,
        label: str,
        role: str,
        value: Any,
        configured_key: str,
        source: str,
        library_id: str = "",
        reserve_key: str = "",
        reserve_gb: float | None = None,
    ) -> None:
        path_text = _path_text(value)
        if not path_text:
            return
        dedupe_key = (role, _dedupe_path_key(path_text))
        reference = {
            "key": key,
            "label": label,
            "configured_key": configured_key,
            "source": source,
            "library_id": library_id,
            "reserve_key": reserve_key,
            "reserve_gb": reserve_gb,
        }
        existing = seen.get(dedupe_key)
        if existing is not None:
            existing["references"].append(reference)
            return
        row = {
            "key": key,
            "label": label,
            "role": role,
            "path": path_text,
            "configured_key": configured_key,
            "source": source,
            "library_id": library_id,
            "reserve_key": reserve_key,
            "reserve_gb": reserve_gb,
            "references": [reference],
        }
        specs.append(row)
        seen[dedupe_key] = row

    add_spec(
        key="source_movies",
        label="SourceMovies root",
        role="source",
        value=config.get(KEY_SOURCE_MOVIES) or getattr(resolved, "source_movies", None),
        configured_key=KEY_SOURCE_MOVIES,
        source="config",
    )
    add_spec(
        key="source_tv",
        label="SourceTV root",
        role="source",
        value=config.get(KEY_SOURCE_TV) or getattr(resolved, "source_tv", None),
        configured_key=KEY_SOURCE_TV,
        source="config",
    )
    add_spec(
        key="outsource",
        label="Outsource output root",
        role="output",
        value=config.get(KEY_OUTSOURCE),
        configured_key=KEY_OUTSOURCE,
        source="config",
        reserve_key=KEY_OUTSOURCE_MIN_FREE_SPACE_GB,
        reserve_gb=output_reserve_gb,
    )
    add_spec(
        key="local_base",
        label="LocalBase scratch/state root",
        role="scratch",
        value=config.get(KEY_LOCAL_BASE) or getattr(resolved, "local_base", None),
        configured_key=KEY_LOCAL_BASE,
        source="config",
        reserve_key=KEY_MIN_FREE_SPACE_GB,
        reserve_gb=scratch_reserve_gb,
    )

    for profile in _effective_library_profiles(config):
        if not bool(profile.get("enabled", True)):
            continue
        library_id = str(profile.get("library_id") or profile.get("id") or "").strip()
        name = str(profile.get("name") or library_id or "Library").strip()
        source_path = profile.get("effective_source_root") or profile.get("source_path")
        output_path = profile.get("effective_output_root") or profile.get("output_path")
        add_spec(
            key=f"library_{_slug(library_id or name)}_source",
            label=f"Library {name} source root",
            role="source",
            value=source_path,
            configured_key=f"{KEY_LIBRARY_PROFILES}[*].source_path",
            source="library_profile",
            library_id=library_id,
        )
        add_spec(
            key=f"library_{_slug(library_id or name)}_output",
            label=f"Library {name} output root",
            role="output",
            value=output_path,
            configured_key=f"{KEY_LIBRARY_PROFILES}[*].output_path",
            source="library_profile",
            library_id=library_id,
            reserve_key=KEY_OUTSOURCE_MIN_FREE_SPACE_GB,
            reserve_gb=output_reserve_gb,
        )
    return specs


def path_health_warning_lines(payload: Mapping[str, Any] | None) -> list[str]:
    if not isinstance(payload, Mapping):
        return []
    rows = payload.get("rows")
    if not isinstance(rows, list):
        return []
    lines: list[str] = []
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        status = str(row.get("status") or "").casefold()
        storage_status = str(row.get("storage_status") or "").casefold()
        if status not in {"blocked", "review", "unknown"} and storage_status not in {"blocked", "low", "unknown"}:
            continue
        label = str(row.get("label") or row.get("key") or "Configured path").strip()
        path = str(row.get("path") or "").strip()
        storage_probe = row.get("storage_probe") if isinstance(row.get("storage_probe"), Mapping) else {}
        message = str(storage_probe.get("message") or row.get("message") or "needs review").strip()
        action = str(row.get("safe_next_action") or "").strip()
        suffix = f" {action}" if action else ""
        health_code = str(row.get("health_code") or "").strip()
        display_status = status if status != "ready" else f"storage {storage_status}"
        code_suffix = f"; code={health_code}" if health_code else ""
        lines.append(f"{label} path health {display_status}{code_suffix}: {message} ({path}).{suffix}")
    return lines[:8]


def _path_health_row(
    spec: Mapping[str, Any],
    *,
    timeout_seconds: float,
    cache_ttl_seconds: float,
    probe_runner: PathProbeRunner | None,
) -> dict[str, Any]:
    path_text = str(spec.get("path") or "").strip()
    server, share = _unc_server_share(path_text)
    try:
        probe = _cached_path_probe(
            path_text,
            timeout_seconds=timeout_seconds,
            cache_ttl_seconds=cache_ttl_seconds,
            probe_runner=probe_runner,
        )
    except Exception as exc:
        probe = {"path": path_text, "probe_error": str(exc), "elapsed_ms": 0}
    status = _probe_status(spec, probe)
    storage_probe = _storage_probe_fields(spec, probe, status)
    if _int_or_none(storage_probe.get("free_bytes")) is not None:
        _record_successful_capacity(path_text, storage_probe)
    last_successful_capacity = _last_successful_capacity(path_text)
    health_code = _health_code(spec, probe, status, storage_probe)
    message = _probe_message(spec, probe, status)
    safe_next_action = _safe_next_action(spec, probe, status)
    return {
        "key": str(spec.get("key") or ""),
        "label": str(spec.get("label") or ""),
        "role": str(spec.get("role") or ""),
        "path": path_text,
        "configured_key": str(spec.get("configured_key") or ""),
        "source": str(spec.get("source") or ""),
        "library_id": str(spec.get("library_id") or ""),
        "reserve_key": str(spec.get("reserve_key") or ""),
        "reserve_gb": storage_probe.get("reserve_gb"),
        "references": list(spec.get("references") or []),
        "is_unc": bool(server),
        "server": server,
        "share": share,
        "status": status,
        "health_code": health_code,
        "operator_status": status,
        "operator_status_state": _path_health_status_state(status),
        "exists": bool(probe.get("exists")),
        "path_kind": str(probe.get("path_kind") or "unknown"),
        "can_list": bool(probe.get("can_list")),
        "timed_out": bool(probe.get("timed_out")),
        "elapsed_ms": int(probe.get("elapsed_ms") or 0),
        "probe_attempts": _probe_attempts(probe),
        "phase_timings_ms": _phase_timings(probe),
        "server_probe": {
            "dns_status": str(probe.get("dns_status") or "not_applicable"),
            "dns_error": str(probe.get("dns_error") or ""),
            "tcp_445_status": str(probe.get("tcp_445_status") or "not_applicable"),
            "tcp_445_error": str(probe.get("tcp_445_error") or ""),
        },
        "path_probe": {
            "exists": bool(probe.get("exists")),
            "path_kind": str(probe.get("path_kind") or "unknown"),
            "can_list": bool(probe.get("can_list")),
            "path_error": str(probe.get("path_error") or probe.get("probe_error") or ""),
            "list_error": str(probe.get("list_error") or ""),
            "timed_out": bool(probe.get("timed_out")),
        },
        "storage_probe": storage_probe,
        "storage_status": storage_probe.get("status"),
        "storage_status_state": storage_probe.get("status_state"),
        "free_space_gb": storage_probe.get("free_gb"),
        "total_space_gb": storage_probe.get("total_gb"),
        "meets_space_reserve": storage_probe.get("meets_reserve"),
        "capacity_source": storage_probe.get("capacity_source"),
        "capacity_path": storage_probe.get("capacity_path"),
        "capacity_error": storage_probe.get("capacity_error"),
        "last_successful_capacity": last_successful_capacity,
        "write_probe": {
            "status": "not_checked",
            "reason": "Read-only health check; write capability is verified by backend copy/publish stages when work actually runs.",
        },
        "message": message,
        "safe_next_action": safe_next_action,
    }


def _cached_path_probe(
    path_text: str,
    *,
    timeout_seconds: float,
    cache_ttl_seconds: float,
    probe_runner: PathProbeRunner | None,
) -> dict[str, Any]:
    key = (path_text, float(timeout_seconds))
    now = time.monotonic()
    if cache_ttl_seconds > 0:
        cached = _PATH_HEALTH_CACHE.get(key)
        if cached is not None and now - cached[0] <= cache_ttl_seconds:
            return deepcopy(cached[1])
    result = _run_path_probe_with_retries(
        path_text,
        timeout_seconds=timeout_seconds,
        probe_runner=probe_runner,
    )
    if cache_ttl_seconds > 0:
        _PATH_HEALTH_CACHE[key] = (now, deepcopy(result))
    return result


def _run_path_probe_with_retries(
    path_text: str,
    *,
    timeout_seconds: float,
    probe_runner: PathProbeRunner | None,
) -> dict[str, Any]:
    attempts: list[dict[str, Any]] = []
    first = _single_path_probe_attempt(path_text, timeout_seconds=timeout_seconds, probe_runner=probe_runner)
    attempts.append(_probe_attempt_summary(first, attempt=1, timeout_seconds=timeout_seconds))
    result = first
    if _should_retry_path_probe(path_text, first):
        if PATH_HEALTH_UNC_RETRY_DELAY_SECONDS > 0:
            time.sleep(PATH_HEALTH_UNC_RETRY_DELAY_SECONDS)
        retry = _single_path_probe_attempt(
            path_text,
            timeout_seconds=PATH_HEALTH_UNC_RETRY_TIMEOUT_SECONDS,
            probe_runner=probe_runner,
        )
        attempts.append(
            _probe_attempt_summary(
                retry,
                attempt=2,
                timeout_seconds=PATH_HEALTH_UNC_RETRY_TIMEOUT_SECONDS,
            )
        )
        result = retry
    payload = dict(result)
    payload["probe_attempts"] = attempts
    payload["attempt_count"] = len(attempts)
    payload.setdefault("phase_timings_ms", {})
    return payload


def _single_path_probe_attempt(
    path_text: str,
    *,
    timeout_seconds: float,
    probe_runner: PathProbeRunner | None,
) -> dict[str, Any]:
    if probe_runner is not None:
        payload = dict(probe_runner(path_text, timeout_seconds))
    else:
        payload = _run_path_probe(path_text, timeout_seconds=timeout_seconds)
    payload.setdefault("path", path_text)
    payload.setdefault("elapsed_ms", 0)
    payload.setdefault("phase_timings_ms", {})
    return payload


def _should_retry_path_probe(path_text: str, probe: Mapping[str, Any]) -> bool:
    return bool(_unc_server_share(path_text)[0]) and _probe_timeout_like(probe)


def _probe_timeout_like(probe: Mapping[str, Any]) -> bool:
    if bool(probe.get("timed_out")):
        return True
    text = " ".join(
        str(probe.get(key) or "")
        for key in ("path_error", "probe_error", "list_error", "disk_error", "capacity_error")
    ).casefold()
    return "timed out" in text or "timeout" in text or "exceeded" in text


def _probe_attempt_summary(probe: Mapping[str, Any], *, attempt: int, timeout_seconds: float) -> dict[str, Any]:
    return {
        "attempt": attempt,
        "timeout_seconds": float(timeout_seconds),
        "timed_out": bool(probe.get("timed_out")),
        "elapsed_ms": int(probe.get("elapsed_ms") or 0),
        "status_hint": _probe_status_hint(probe),
        "path_error": str(probe.get("path_error") or probe.get("probe_error") or ""),
    }


def _probe_status_hint(probe: Mapping[str, Any]) -> str:
    if _probe_timeout_like(probe):
        return "timeout"
    if str(probe.get("probe_error") or probe.get("path_error") or "").strip():
        return "error"
    if not bool(probe.get("exists")):
        return "missing"
    if str(probe.get("path_kind") or "").casefold() != "directory":
        return "wrong_kind"
    if not bool(probe.get("can_list")) or str(probe.get("list_error") or "").strip():
        return "not_listable"
    if _int_or_none(probe.get("free_bytes")) is None:
        return "capacity_unknown"
    return "ready"


def _run_path_probe(path_text: str, *, timeout_seconds: float) -> dict[str, Any]:
    started = time.monotonic()
    command = [sys.executable, "-c", _PATH_HEALTH_PROBE_SCRIPT, path_text, str(float(timeout_seconds))]
    try:
        completed = subprocess.run(
            command,
            capture_output=True,
            check=False,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            encoding="utf-8",
            errors="replace",
            text=True,
            timeout=max(0.2, float(timeout_seconds)),
        )
    except subprocess.TimeoutExpired:
        return {
            "path": path_text,
            "timed_out": True,
            "elapsed_ms": int((time.monotonic() - started) * 1000),
            "path_error": f"Path health probe exceeded {timeout_seconds:g} seconds.",
            "phase_timings_ms": {},
        }
    stdout = (completed.stdout or "").strip()
    if stdout:
        try:
            payload = json.loads(stdout.splitlines()[-1])
        except json.JSONDecodeError:
            payload = {}
    else:
        payload = {}
    if not isinstance(payload, dict):
        payload = {}
    payload.setdefault("path", path_text)
    payload.setdefault("elapsed_ms", int((time.monotonic() - started) * 1000))
    payload.setdefault("phase_timings_ms", {})
    if completed.returncode != 0:
        payload["probe_error"] = (completed.stderr or "").strip() or f"Probe exited with code {completed.returncode}."
    return payload


def _probe_status(spec: Mapping[str, Any], probe: Mapping[str, Any]) -> str:
    if probe.get("timed_out"):
        return "blocked"
    if str(probe.get("probe_error") or probe.get("path_error") or "").strip():
        return "blocked"
    if not bool(probe.get("exists")):
        return "blocked"
    if str(probe.get("path_kind") or "").casefold() != "directory":
        return "blocked"
    if not bool(probe.get("can_list")):
        return "blocked"
    if str(probe.get("list_error") or "").strip():
        return "blocked"
    role = str(spec.get("role") or "").casefold()
    if role == "output" and _server_probe_has_issue(probe):
        return "review"
    return "ready"


def _probe_message(spec: Mapping[str, Any], probe: Mapping[str, Any], status: str) -> str:
    label = str(spec.get("label") or "Configured path")
    if status == "ready":
        return f"{label} exists and the backend can list the root."
    if probe.get("timed_out"):
        return f"{label} did not respond within the bounded path health timeout."
    error = str(probe.get("path_error") or probe.get("probe_error") or probe.get("list_error") or "").strip()
    if error:
        return f"{label} could not be reached: {error}"
    if not bool(probe.get("exists")):
        return f"{label} does not exist or is not reachable from this Windows session."
    kind = str(probe.get("path_kind") or "unknown")
    if kind != "directory":
        return f"{label} resolved as {kind}, but the pipeline expects a folder root."
    if not bool(probe.get("can_list")):
        return f"{label} exists but could not be listed by this Windows session."
    return f"{label} needs review before launch."


def _safe_next_action(spec: Mapping[str, Any], probe: Mapping[str, Any], status: str) -> str:
    if status == "ready":
        return "No action required."
    role = str(spec.get("role") or "").casefold()
    if _unc_server_share(str(spec.get("path") or ""))[0]:
        return "Log back into Windows/server share, reconnect VPN/network if needed, then refresh path health before starting the pipeline."
    if role in {"source", "output"}:
        return "Restore or choose the configured media root, then refresh Settings/Launch before starting work."
    if bool(probe.get("timed_out")):
        return "Check whether the folder is locked or slow to respond, then refresh path health."
    return "Restore the configured folder or update settings through the backend save flow before relying on this path."


def _server_probe_has_issue(probe: Mapping[str, Any]) -> bool:
    statuses = {
        str(probe.get("dns_status") or "").casefold(),
        str(probe.get("tcp_445_status") or "").casefold(),
    }
    return "blocked" in statuses


def _health_code(
    spec: Mapping[str, Any],
    probe: Mapping[str, Any],
    path_status: str,
    storage_probe: Mapping[str, Any],
) -> str:
    if _probe_timeout_like(probe):
        return "path_timeout"
    if str(probe.get("probe_error") or probe.get("path_error") or "").strip():
        return "path_error"
    if not bool(probe.get("exists")):
        return "path_missing_or_unreachable"
    if str(probe.get("path_kind") or "").casefold() != "directory":
        return "path_not_directory"
    if not bool(probe.get("can_list")) or str(probe.get("list_error") or "").strip():
        return "path_not_listable"
    storage_status = str(storage_probe.get("status") or "").casefold()
    if storage_status == "low":
        return "free_space_low"
    if storage_status == "unknown":
        return "free_space_unknown"
    if path_status == "review" and _server_probe_has_issue(probe):
        return "server_probe_review"
    role = str(spec.get("role") or "").casefold()
    if role in {"scratch", "output"} and storage_status == "ready":
        return "ready_with_capacity"
    if path_status == "ready":
        return "path_ready"
    return path_status or "unknown"


def _storage_probe_fields(spec: Mapping[str, Any], probe: Mapping[str, Any], path_status: str) -> dict[str, Any]:
    role = str(spec.get("role") or "").casefold()
    reserve_gb = _reserve_gb(spec.get("reserve_gb"))
    reserve_key = str(spec.get("reserve_key") or "")
    capacity_source = str(probe.get("capacity_source") or "").strip()
    capacity_path = str(probe.get("capacity_path") or "").strip()
    capacity_error = str(probe.get("capacity_error") or probe.get("disk_error") or "").strip()
    if role not in {"scratch", "output"}:
        return {
            "status": "not_checked",
            "status_state": "empty",
            "role": role,
            "reserve_key": reserve_key,
            "reserve_gb": None,
            "free_gb": None,
            "total_gb": None,
            "used_gb": None,
            "free_bytes": None,
            "total_bytes": None,
            "used_bytes": None,
            "meets_reserve": None,
            "capacity_source": "not_checked",
            "capacity_path": "",
            "capacity_error": "",
            "message": "Free-space reserve is not tracked for source roots.",
        }
    if path_status != "ready":
        status = "blocked"
        message = "Path must be reachable and listable before free space can be trusted."
        free_bytes = total_bytes = used_bytes = None
        capacity_source = capacity_source or "not_trusted"
        capacity_error = capacity_error or message
    else:
        free_bytes = _int_or_none(probe.get("free_bytes"))
        total_bytes = _int_or_none(probe.get("total_bytes"))
        used_bytes = _int_or_none(probe.get("used_bytes"))
        disk_error = str(probe.get("disk_error") or "").strip()
        if free_bytes is None:
            status = "unknown"
            capacity_source = capacity_source or "unavailable"
            capacity_error = capacity_error or disk_error
            message = capacity_error or "Free space could not be determined by the bounded read-only probe."
        else:
            capacity_source = capacity_source or "configured_path"
            capacity_path = capacity_path or str(probe.get("path") or "")
            free_gb = free_bytes / (1024**3)
            if free_gb < reserve_gb:
                status = "low"
                message = f"Free space is below the configured {reserve_key or 'reserve'} reserve."
            else:
                status = "ready"
                message = "Free space meets the configured reserve."
    free_gb_value = _bytes_to_gb(free_bytes)
    return {
        "status": status,
        "status_state": _storage_status_state(status),
        "role": role,
        "reserve_key": reserve_key,
        "reserve_gb": reserve_gb,
        "free_gb": free_gb_value,
        "total_gb": _bytes_to_gb(total_bytes),
        "used_gb": _bytes_to_gb(used_bytes),
        "free_bytes": free_bytes,
        "total_bytes": total_bytes,
        "used_bytes": used_bytes,
        "meets_reserve": None if free_gb_value is None else free_gb_value >= reserve_gb,
        "capacity_source": capacity_source,
        "capacity_path": capacity_path,
        "capacity_error": capacity_error,
        "message": message,
    }


def _probe_attempts(probe: Mapping[str, Any]) -> list[dict[str, Any]]:
    attempts = probe.get("probe_attempts")
    if not isinstance(attempts, list):
        return []
    return [dict(item) for item in attempts if isinstance(item, Mapping)]


def _phase_timings(probe: Mapping[str, Any]) -> dict[str, int]:
    timings = probe.get("phase_timings_ms")
    if not isinstance(timings, Mapping):
        return {}
    result: dict[str, int] = {}
    for key, value in timings.items():
        try:
            result[str(key)] = max(0, int(value))
        except (TypeError, ValueError):
            continue
    return result


def _record_successful_capacity(path_text: str, storage_probe: Mapping[str, Any]) -> None:
    key = _dedupe_path_key(path_text)
    if not key:
        return
    free_bytes = _int_or_none(storage_probe.get("free_bytes"))
    total_bytes = _int_or_none(storage_probe.get("total_bytes"))
    used_bytes = _int_or_none(storage_probe.get("used_bytes"))
    if free_bytes is None:
        return
    _PATH_HEALTH_CAPACITY_CACHE[key] = {
        "checked_at_utc": _utc_now_text(),
        "free_space_gb": _bytes_to_gb(free_bytes),
        "total_space_gb": _bytes_to_gb(total_bytes),
        "used_space_gb": _bytes_to_gb(used_bytes),
        "free_bytes": free_bytes,
        "total_bytes": total_bytes,
        "used_bytes": used_bytes,
        "reserve_gb": storage_probe.get("reserve_gb"),
        "capacity_source": storage_probe.get("capacity_source") or "",
        "capacity_path": storage_probe.get("capacity_path") or "",
        "evidence_only": True,
    }


def _last_successful_capacity(path_text: str) -> dict[str, Any] | None:
    cached = _PATH_HEALTH_CAPACITY_CACHE.get(_dedupe_path_key(path_text))
    return deepcopy(cached) if cached is not None else None


def _storage_status_state(status: str) -> str:
    normalized = str(status or "").casefold()
    if normalized == "ready":
        return "ready"
    if normalized in {"blocked", "low"}:
        return "blocked"
    if normalized == "unknown":
        return "warning"
    return "empty"


def _path_health_operator_summary(
    operator_status: str,
    rows: list[dict[str, Any]],
    counts: Mapping[str, int],
) -> str:
    if not rows:
        return "No configured media/storage roots were available for path health."
    if operator_status == "blocked":
        return f"{counts.get('blocked', 0)} configured root(s) are not reachable or listable."
    if operator_status == "review":
        return f"{counts.get('review', 0)} configured root(s) need review before launch."
    if operator_status == "ready":
        return "Configured media/storage roots are reachable and listable."
    return "Configured path health is incomplete."


def _path_health_summary_lines(
    operator_status: str,
    rows: list[dict[str, Any]],
    counts: Mapping[str, int],
) -> list[str]:
    lines = [
        f"Configured path health: {operator_status}.",
        (
            "Counts: "
            f"ready={counts.get('ready', 0)}; "
            f"review={counts.get('review', 0)}; "
            f"blocked={counts.get('blocked', 0)}; "
            f"unknown={counts.get('unknown', 0)}."
        ),
        "Probe scope: configured roots only; no recursive scan, no write probe, no media mutation.",
    ]
    issue_rows = [
        row
        for row in rows
        if str(row.get("status") or "").casefold() != "ready"
        or str(row.get("storage_status") or "").casefold() in {"blocked", "low", "unknown"}
    ]
    for row in issue_rows[:6]:
        storage_probe = row.get("storage_probe") if isinstance(row.get("storage_probe"), Mapping) else {}
        storage_status = str(row.get("storage_status") or storage_probe.get("status") or "not_checked")
        storage_message = str(storage_probe.get("message") or "").strip()
        capacity_source = str(row.get("capacity_source") or storage_probe.get("capacity_source") or "").strip()
        capacity_suffix = f"; capacity_source={capacity_source}" if capacity_source else ""
        storage_suffix = f"; storage={storage_status}" if storage_status and storage_status != "not_checked" else ""
        message = storage_message or str(row.get("message") or "").strip()
        lines.append(
            f"{row.get('label')}: path={row.get('status')}; code={row.get('health_code') or 'unknown'}"
            f"{storage_suffix}{capacity_suffix}; {message}"
        )
    if len(issue_rows) > 6:
        lines.append(f"{len(issue_rows) - 6} more configured path issue(s) are hidden from this summary.")
    return lines


def _effective_library_profiles(config: Mapping[str, Any]) -> list[dict[str, Any]]:
    try:
        from mediapipeline.core.config.library_profiles import effective_library_profiles_from_config

        return effective_library_profiles_from_config(config)
    except Exception:
        raw = config.get(KEY_LIBRARY_PROFILES)
        if isinstance(raw, list):
            return [dict(item) for item in raw if isinstance(item, Mapping)]
    return []


def _path_health_status_state(status: str) -> str:
    normalized = str(status or "").casefold()
    if normalized == "ready":
        return "ready"
    if normalized == "blocked":
        return "blocked"
    if normalized == "review":
        return "warning"
    return "unknown"


def _unc_server_share(path: str) -> tuple[str, str]:
    path_text = str(path or "").strip().replace("/", "\\")
    lower_path_text = path_text.casefold()
    if lower_path_text.startswith("\\\\?\\unc\\"):
        remainder = path_text[8:]
    elif path_text.startswith("\\\\") and not lower_path_text.startswith("\\\\?\\"):
        remainder = path_text[2:]
    else:
        return "", ""
    parts = [part for part in remainder.split("\\") if part]
    server = parts[0] if len(parts) >= 1 else ""
    share = parts[1] if len(parts) >= 2 else ""
    return server, share


def _path_text(value: Any) -> str:
    return str(value or "").strip()


def _dedupe_path_key(path_text: str) -> str:
    return str(path_text or "").replace("\\", "/").rstrip("/").casefold()


def _reserve_gb(value: Any, *, fallback: float = 0.0) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        parsed = float(fallback)
    if parsed <= 0 and fallback > 0:
        return float(fallback)
    if parsed < 0:
        return 0.0
    return float(parsed)


def _int_or_none(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _bytes_to_gb(value: int | None) -> float | None:
    if value is None:
        return None
    return round(float(value) / (1024**3), 2)


def _slug(value: str) -> str:
    text = "".join(ch if ch.isalnum() else "_" for ch in str(value or "").strip().casefold())
    return "_".join(part for part in text.split("_") if part) or "library"


def _utc_now_text() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


__all__ = [
    "CONFIGURED_PATH_HEALTH_SCHEMA_VERSION",
    "DEFAULT_PATH_HEALTH_CACHE_TTL_SECONDS",
    "DEFAULT_PATH_HEALTH_TIMEOUT_SECONDS",
    "LAUNCH_PATH_HEALTH_TIMEOUT_SECONDS",
    "PATH_HEALTH_UNC_RETRY_DELAY_SECONDS",
    "PATH_HEALTH_UNC_RETRY_TIMEOUT_SECONDS",
    "configured_path_health",
    "configured_path_specs",
    "is_unc_path",
    "path_evidence",
    "path_health_warning_lines",
]
