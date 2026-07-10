"""Dependency-safe close-readiness evidence for Tdarr Matrix background runs."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

try:
    import psutil  # type: ignore
except Exception:  # pragma: no cover - optional desktop dependency
    psutil = None  # type: ignore


def _runs_root(workspace_root: Path) -> Path:
    root = Path(workspace_root)
    if (root / "AGENTS.md").exists() and (root / "src" / "mediapipeline").exists():
        return Path("E:/Videos/TdarrMatrix/ProofPack/runs")
    return root / "LocalBase" / "Scratch" / "TestLibraries" / "TdarrProofPack" / "runs"


def _int_value(value: object) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _timestamp_matches(expected: object, actual: object, *, tolerance_seconds: float = 2.0) -> bool:
    try:
        expected_time = datetime.fromisoformat(str(expected).replace("Z", "+00:00")).astimezone(UTC)
        actual_time = datetime.fromisoformat(str(actual).replace("Z", "+00:00")).astimezone(UTC)
    except (TypeError, ValueError):
        return False
    return abs((expected_time - actual_time).total_seconds()) <= tolerance_seconds


def _process_state(metadata_path: Path, raw: dict[str, Any], *, psutil_module: Any) -> dict[str, Any]:
    pid = _int_value(raw.get("pid"))
    if pid <= 0:
        return {"live": False, "reason": "missing_background_pid", "pid": 0}
    expected_start = str(raw.get("process_start_time") or "")
    if not expected_start:
        return {"live": False, "reason": "missing_process_start_time", "pid": pid}
    if psutil_module is None:
        return {"live": False, "reason": "process_liveness_unavailable", "pid": pid}
    try:
        process = psutil_module.Process(pid)
        alive = bool(process.is_running()) and process.status() != psutil_module.STATUS_ZOMBIE
    except psutil_module.NoSuchProcess:
        return {"live": False, "reason": "process_not_found", "pid": pid}
    except Exception as exc:
        return {"live": False, "reason": f"process_liveness_check_failed: {exc}", "pid": pid}
    if not alive:
        return {"live": False, "reason": "process_not_running", "pid": pid}
    try:
        actual_start = datetime.fromtimestamp(float(process.create_time()), UTC).isoformat()
    except Exception:
        actual_start = ""
    if not actual_start or not _timestamp_matches(expected_start, actual_start):
        return {"live": False, "reason": "pid_identity_mismatch", "pid": pid}
    return {"live": True, "reason": "", "pid": pid, "metadata_path": str(metadata_path)}


def tdarr_matrix_background_close_evidence(
    workspace_root: Path,
    *,
    psutil_module: Any | None = None,
) -> dict[str, Any]:
    """Return fail-closed close evidence without importing the diagnostics package."""
    if psutil_module is None:
        psutil_module = psutil
    runs_root = _runs_root(Path(workspace_root))
    metadata_root = runs_root / "_background"
    if not metadata_root.exists():
        return {"status": "inactive", "active_work": False, "pid": 0, "run_id": "", "reason": ""}
    try:
        metadata_paths = sorted(metadata_root.glob("*.process.json"))
    except OSError as exc:
        return {"status": "unavailable", "active_work": True, "pid": 0, "run_id": "", "reason": str(exc)}
    for metadata_path in metadata_paths:
        try:
            raw = json.loads(metadata_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            return {
                "status": "unavailable", "active_work": True, "pid": 0,
                "run_id": metadata_path.name.removesuffix(".process.json"),
                "reason": f"background metadata is unreadable: {exc}", "metadata_path": str(metadata_path),
            }
        if not isinstance(raw, dict) or str(raw.get("schema_version") or "") != "tdarr_matrix_background_process.v1":
            return {
                "status": "unavailable", "active_work": True, "pid": 0, "run_id": "",
                "reason": "background metadata schema is invalid", "metadata_path": str(metadata_path),
            }
        run_id = str(raw.get("run_id") or "").strip()
        if not run_id or metadata_path != metadata_root / f"{run_id}.process.json":
            return {
                "status": "unavailable", "active_work": True, "pid": _int_value(raw.get("pid")),
                "run_id": run_id, "reason": "background metadata run identity is invalid",
                "metadata_path": str(metadata_path),
            }
        state = _process_state(metadata_path, raw, psutil_module=psutil_module)
        if state.get("live") is True:
            return {
                "status": "active", "active_work": True, "pid": _int_value(state.get("pid")),
                "run_id": run_id, "reason": "", "metadata_path": str(metadata_path),
            }
        reason = str(state.get("reason") or "")
        if reason not in {"process_not_found", "process_not_running", "pid_identity_mismatch"}:
            return {
                "status": "unavailable", "active_work": True, "pid": _int_value(state.get("pid")),
                "run_id": run_id, "reason": reason or "background process identity is unavailable",
                "metadata_path": str(metadata_path),
            }
    return {"status": "inactive", "active_work": False, "pid": 0, "run_id": "", "reason": ""}


__all__ = ["tdarr_matrix_background_close_evidence"]
