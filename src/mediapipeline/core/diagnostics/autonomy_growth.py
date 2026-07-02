"""Autonomy health growth snapshot helpers."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from datetime import UTC, datetime
import os
from pathlib import Path
import time
from typing import Any

from mediapipeline.core.diagnostics.autonomy_policy import AutonomyPolicy


def growth_snapshot_write_result(
    *,
    snapshot_path: Path | None,
    snapshot: Mapping[str, Any],
    retained_snapshot_count: int,
    max_snapshots: int,
    wrote_snapshot: bool,
    error: str,
    lock_path: Path | None = None,
) -> dict[str, Any]:
    return {
        "schema_version": "desktop_autonomy_growth_snapshot_write.v1",
        "effect": "diagnostics_state_snapshot_write",
        "snapshot_path": str(snapshot_path or ""),
        "lock_path": str(lock_path or ""),
        "wrote_snapshot": wrote_snapshot,
        "retained_snapshot_count": retained_snapshot_count,
        "max_snapshot_count": max_snapshots,
        "snapshot": dict(snapshot),
        "error": error,
        "media_mutation_performed": False,
        "cleanup_performed": False,
        "pending_publish_mutation_performed": False,
        "queue_mutation_performed": False,
        "policy": (
            "Explicit diagnostics-state snapshot write only. This helper does not touch source media, "
            "pending publish files, queue state, cleanup targets, or final outputs."
        ),
    }


def acquire_growth_snapshot_lock(lock_path: Path, *, timeout_seconds: float) -> tuple[int | None, str]:
    try:
        lock_path.parent.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        return None, str(exc)
    deadline = time.monotonic() + timeout_seconds
    while True:
        try:
            fd = os.open(str(lock_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.write(fd, f"pid={os.getpid()}; acquired_at={datetime.now(UTC).isoformat()}\n".encode())
            return fd, ""
        except FileExistsError:
            if time.monotonic() >= deadline:
                return None, f"snapshot lock unavailable: {lock_path}"
            time.sleep(0.05)
        except OSError as exc:
            return None, str(exc)


def release_growth_snapshot_lock(fd: int | None, lock_path: Path) -> None:
    if fd is not None:
        try:
            os.close(fd)
        except OSError:
            pass
    try:
        lock_path.unlink()
    except OSError:
        pass


def bounded_snapshot_limit(max_snapshots: int | None, *, policy: AutonomyPolicy | None = None) -> int:
    requested = _safe_int(max_snapshots)
    active_policy = policy or AutonomyPolicy()
    if requested <= 0:
        return active_policy.growth_snapshot_max_count
    return min(requested, active_policy.growth_snapshot_max_count)


def minimum_present(values: Iterable[Any]) -> int | None:
    integers = [_safe_int(value) for value in values if value not in (None, "")]
    if not integers:
        return None
    return min(integers)


def _safe_int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


__all__ = [
    "acquire_growth_snapshot_lock",
    "bounded_snapshot_limit",
    "growth_snapshot_write_result",
    "minimum_present",
    "release_growth_snapshot_lock",
]
