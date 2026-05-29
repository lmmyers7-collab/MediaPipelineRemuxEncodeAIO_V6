"""Network runtime-state facade adapter."""

from __future__ import annotations

from datetime import datetime, timezone
import logging
from pathlib import Path
import re
from typing import TYPE_CHECKING, Any

from mediapipeline_desktop_app.models import ResolvedPaths
from mediapipeline_desktop_app.network.registry import InFlightRegistry
from mediapipeline_desktop_app.network.worker_state import load_worker_state

if TYPE_CHECKING:
    from mediapipeline_desktop_app.application.dto_workspaces import NetworkWorkersDto


_log = logging.getLogger(__name__)


def _network_workers_dto(**fields: Any) -> "NetworkWorkersDto":
    from mediapipeline_desktop_app.application.dto_workspaces import NetworkWorkersDto

    return NetworkWorkersDto(**fields)


def _network_role(resolved: ResolvedPaths) -> str:
    return str((resolved.config_data or {}).get("NetworkRole") or "standalone").strip().lower() or "standalone"


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
        bits.append(f"error={row.get('error')}")
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
    mode_status = "idle" if role == "standalone" else "active" if rows or worker_state.get("job_id") else "warning"
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
        warnings.append(f"Worker state could not be read: {exc}")
        _log.warning("Network worker_state read failed for %s: %s", path, exc)
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
        row["error"] = str(exc)
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


class NetworkFacadeMixin:
    """Read-only network runtime-state adapter for local WebView/Tauri shells."""

    service: object
    app_version: str

    def get_network_workers(self, resolved: ResolvedPaths) -> NetworkWorkersDto:
        role = _network_role(resolved)
        state_dir = _runtime_state_dir(resolved, self.service)
        inflight_path = state_dir / "coordinator_inflight.json"
        worker_state_path = state_dir / "worker_state.json"
        cluster_log_path = state_dir / "cluster.log"
        warnings: list[str] = []
        rows: list[dict[str, Any]] = []
        session_completed = 0
        session_failed = 0
        active_count = 0
        idle_count = 0

        if inflight_path.exists():
            registry = InFlightRegistry()
            registry.load(inflight_path)
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
            warnings.append("No coordinator in-flight state file exists yet.")

        worker_state = _safe_worker_state(worker_state_path, warnings)
        if worker_state.get("pending_done_report"):
            warnings.append("Worker state contains a pending done report; the coordinator may not have accepted the last completion yet.")
        if role == "worker" and not worker_state:
            warnings.append("Worker runtime state is empty; this worker may be idle or has not claimed work in this state directory.")
        if role == "coordinator" and not rows:
            warnings.append("Coordinator worker board is empty from persisted state; use the backend Network diagnostics for live dispatcher rows.")

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
        unreadable = [item for item in state_files if item.get("status") == "unreadable"]
        for item in unreadable:
            warnings.append(f"{item.get('label') or item.get('key')} could not be inspected: {item.get('error')}")
        worker_progress = _network_worker_progress(
            role=role,
            rows=rows,
            worker_state=worker_state,
            warnings=warnings,
            heartbeat_timeout_seconds=_heartbeat_timeout_seconds(resolved),
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
            worker_progress=worker_progress,
            progress_bars=list(worker_progress.get("progress_bars") or []),
            warnings=warnings,
        )

__all__ = [
    "NetworkFacadeMixin",
]
