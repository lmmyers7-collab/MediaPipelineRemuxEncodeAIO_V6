from __future__ import annotations

from datetime import datetime, UTC
from pathlib import Path
from typing import Any


BOOTSTRAP_SCHEMA_VERSION = "desktop_local_api_bootstrap.v1"
STARTUP_PROGRESS_SCHEMA_VERSION = "desktop_startup_progress.v1"


def startup_timestamp() -> str:
    return datetime.now(UTC).isoformat()


def startup_step(
    step_id: str,
    label: str,
    *,
    status: str = "complete",
    detail: str = "",
    source: str = "local_api_main",
    duration_ms: float | None = None,
    elapsed_ms: float | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "id": str(step_id),
        "label": str(label),
        "status": str(status or "unknown"),
        "detail": str(detail or ""),
        "source": str(source or "local_api_main"),
        "updated_at": startup_timestamp(),
    }
    if duration_ms is not None:
        payload["duration_ms"] = round(max(0.0, float(duration_ms)), 1)
    if elapsed_ms is not None:
        payload["elapsed_ms"] = round(max(0.0, float(elapsed_ms)), 1)
    return payload


def startup_progress_payload(steps: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    rows = list(steps or [])
    total = len(rows)
    completed = sum(1 for row in rows if str(row.get("status") or "").casefold() == "complete")
    blocked = sum(1 for row in rows if str(row.get("status") or "").casefold() in {"blocked", "failed", "error"})
    warnings = sum(1 for row in rows if str(row.get("status") or "").casefold() == "warning")
    status = "blocked" if blocked else "warning" if warnings else "complete" if total and completed == total else "active"
    percent = 100.0 if total == 0 else round((completed / total) * 100.0, 1)
    current = rows[-1] if rows else {}
    return {
        "schema_version": STARTUP_PROGRESS_SCHEMA_VERSION,
        "status": status,
        "mode": "stepped",
        "percent": percent,
        "completed_steps": completed,
        "total_steps": total,
        "current_step": current.get("id", ""),
        "steps": rows,
        "source": "local_api_main",
        "updated_at": startup_timestamp(),
    }


def backend_bootstrap_payload(
    *,
    url: str,
    token: str,
    host: str,
    port: int,
    config_path: Path,
    pipeline_path: Path,
    include_token: bool,
    shell_surface: str = "webview",
    startup_progress: dict[str, Any] | None = None,
) -> dict[str, object]:
    return {
        "schema_version": BOOTSTRAP_SCHEMA_VERSION,
        "url": str(url),
        "token": str(token) if include_token else "",
        "host": str(host),
        "port": int(port),
        "config_path": str(config_path),
        "pipeline_path": str(pipeline_path),
        "shell_surface": str(shell_surface or "webview"),
        "startup_progress": startup_progress or startup_progress_payload([]),
    }
