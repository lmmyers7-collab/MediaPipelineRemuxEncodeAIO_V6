"""Queue snapshot freshness policy for backend-owned Run Once launches."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, UTC
import os
from pathlib import Path
import time
from typing import Any


QUEUE_SNAPSHOT_FRESHNESS_DEFAULT_SECONDS = 60
QUEUE_SNAPSHOT_FRESHNESS_MIN_SECONDS = 15
QUEUE_SNAPSHOT_FRESHNESS_MAX_SECONDS = 3600
QUEUE_SNAPSHOT_FRESHNESS_CLOCK_SKEW_SECONDS = 5.0
QUEUE_SNAPSHOT_FRESHNESS_HANDOFF_GRACE_SECONDS = 1.0


@dataclass(frozen=True)
class QueueSnapshotFreshnessAnchor:
    """Process-local correlation between a completed scan and monotonic time."""

    snapshot_path_key: str
    scan_id: str
    request_id: str
    produced_at: str
    queue_plan_fingerprint: str
    monotonic_at: float


@dataclass(frozen=True)
class QueueSnapshotFreshnessResult:
    fresh: bool
    reason_code: str
    message: str
    operator_action: str
    clock_model: str
    age_seconds: float | None
    detail: tuple[str, ...]


def normalize_queue_snapshot_freshness_seconds(value: object) -> int:
    try:
        freshness_seconds = int(value)
    except (TypeError, ValueError):
        return QUEUE_SNAPSHOT_FRESHNESS_DEFAULT_SECONDS
    if not (
        QUEUE_SNAPSHOT_FRESHNESS_MIN_SECONDS
        <= freshness_seconds
        <= QUEUE_SNAPSHOT_FRESHNESS_MAX_SECONDS
    ):
        return QUEUE_SNAPSHOT_FRESHNESS_DEFAULT_SECONDS
    return freshness_seconds


def _path_key(path: Path | str) -> str:
    return os.path.normcase(os.path.abspath(str(path)))


def _aware_utc_timestamp(value: object) -> tuple[datetime | None, str]:
    raw = str(value or "").strip()
    if not raw:
        return None, "queue_snapshot_timestamp_missing"
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None, "queue_snapshot_timestamp_invalid"
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        return None, "queue_snapshot_timezone_missing"
    return parsed.astimezone(UTC), ""


def build_queue_snapshot_freshness_anchor(
    snapshot_path: Path,
    snapshot: Mapping[str, Any],
    scan_status: Mapping[str, Any],
    *,
    monotonic_now: float | None = None,
) -> QueueSnapshotFreshnessAnchor:
    produced_at = str(snapshot.get("produced_at") or "").strip()
    _parsed, timestamp_error = _aware_utc_timestamp(produced_at)
    if timestamp_error:
        raise ValueError(timestamp_error)
    scan_id = str(scan_status.get("scan_id") or "").strip()
    request_id = str(scan_status.get("queue_preview_request_id") or "").strip()
    snapshot_request_id = str(snapshot.get("desktop_queue_preview_request_id") or "").strip()
    queue_plan_fingerprint = str(snapshot.get("queue_plan_fingerprint") or "").strip()
    if not scan_id or not request_id or request_id != snapshot_request_id or not queue_plan_fingerprint:
        raise ValueError("queue_snapshot_anchor_identity_invalid")
    return QueueSnapshotFreshnessAnchor(
        snapshot_path_key=_path_key(snapshot_path),
        scan_id=scan_id,
        request_id=request_id,
        produced_at=produced_at,
        queue_plan_fingerprint=queue_plan_fingerprint,
        monotonic_at=float(time.monotonic() if monotonic_now is None else monotonic_now),
    )


def _anchor_matches(
    anchor: QueueSnapshotFreshnessAnchor | None,
    snapshot_path: Path,
    snapshot: Mapping[str, Any],
    scan_status: Mapping[str, Any],
) -> bool:
    if anchor is None:
        return False
    return (
        anchor.snapshot_path_key == _path_key(snapshot_path)
        and anchor.scan_id == str(scan_status.get("scan_id") or "").strip()
        and anchor.request_id == str(scan_status.get("queue_preview_request_id") or "").strip()
        and anchor.request_id == str(snapshot.get("desktop_queue_preview_request_id") or "").strip()
        and anchor.produced_at == str(snapshot.get("produced_at") or "").strip()
        and anchor.queue_plan_fingerprint == str(snapshot.get("queue_plan_fingerprint") or "").strip()
    )


def _result(
    *,
    fresh: bool,
    reason_code: str,
    message: str,
    clock_model: str,
    age_seconds: float | None,
    detail: list[str],
) -> QueueSnapshotFreshnessResult:
    return QueueSnapshotFreshnessResult(
        fresh=fresh,
        reason_code=reason_code,
        message=message,
        operator_action=(
            "Queue evidence is fresh and correlated."
            if fresh
            else "Run Queue scan again and wait for it to complete before launching Run Once."
        ),
        clock_model=clock_model,
        age_seconds=age_seconds,
        detail=tuple(detail),
    )


def evaluate_queue_snapshot_freshness(
    snapshot_path: Path,
    snapshot: Mapping[str, Any],
    scan_status: Mapping[str, Any],
    *,
    freshness_seconds: float,
    wall_now: datetime | None = None,
    monotonic_now: float | None = None,
    anchor: QueueSnapshotFreshnessAnchor | None = None,
    clock_skew_seconds: float = QUEUE_SNAPSHOT_FRESHNESS_CLOCK_SKEW_SECONDS,
    handoff_grace_seconds: float = QUEUE_SNAPSHOT_FRESHNESS_HANDOFF_GRACE_SECONDS,
) -> QueueSnapshotFreshnessResult:
    """Evaluate one immutable snapshot using monotonic or restart-safe UTC time.

    A correlated scan completed in this process uses monotonic elapsed time, so
    wall-clock corrections cannot age or rejuvenate it. After a process restart,
    timezone-aware ``produced_at`` and filesystem mtime provide fail-closed UTC
    evidence. The small inclusive handoff grace prevents a preview rendered at
    the threshold from failing solely due to ordinary request latency.
    """

    limit_seconds = max(0.0, float(freshness_seconds))
    grace_seconds = max(0.0, float(handoff_grace_seconds))
    effective_limit = limit_seconds + grace_seconds
    base_detail = [
        "preview_age_policy=enforced",
        f"preview_age_limit_seconds={limit_seconds:g}",
        f"preview_handoff_grace_seconds={grace_seconds:g}",
    ]
    produced_at, timestamp_error = _aware_utc_timestamp(snapshot.get("produced_at"))
    if timestamp_error:
        return _result(
            fresh=False,
            reason_code=timestamp_error,
            message=f"Queue snapshot produced_at evidence is invalid ({timestamp_error}).",
            clock_model="invalid",
            age_seconds=None,
            detail=[timestamp_error, *base_detail],
        )
    assert produced_at is not None

    monotonic_value = float(time.monotonic() if monotonic_now is None else monotonic_now)
    if _anchor_matches(anchor, snapshot_path, snapshot, scan_status):
        assert anchor is not None
        age_seconds = monotonic_value - anchor.monotonic_at
        detail = [
            *base_detail,
            "preview_clock_model=process_monotonic",
            f"preview_age_seconds={age_seconds:.3f}",
        ]
        if age_seconds < 0:
            return _result(
                fresh=False,
                reason_code="queue_snapshot_monotonic_clock_invalid",
                message="Queue snapshot monotonic freshness evidence moved backward.",
                clock_model="process_monotonic",
                age_seconds=age_seconds,
                detail=["queue_snapshot_monotonic_clock_invalid", *detail],
            )
        if age_seconds > effective_limit:
            return _result(
                fresh=False,
                reason_code="queue_snapshot_monotonic_age_stale",
                message=(
                    f"Queue snapshot completed-scan age {age_seconds:.3f}s exceeds the "
                    f"{limit_seconds:g}s freshness window plus {grace_seconds:g}s launch handoff grace."
                ),
                clock_model="process_monotonic",
                age_seconds=age_seconds,
                detail=["queue_snapshot_monotonic_age_stale", *detail],
            )
        return _result(
            fresh=True,
            reason_code="queue_snapshot_fresh",
            message=f"Queue snapshot is fresh ({age_seconds:.3f}s, process monotonic clock).",
            clock_model="process_monotonic",
            age_seconds=age_seconds,
            detail=detail,
        )

    now = wall_now or datetime.now(UTC)
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("wall_now must include timezone data")
    now = now.astimezone(UTC)
    produced_age = (now - produced_at).total_seconds()
    detail = [
        *base_detail,
        "preview_clock_model=restart_wall_utc",
        f"produced_age_seconds={produced_age:.3f}",
    ]
    if produced_age < -abs(float(clock_skew_seconds)):
        return _result(
            fresh=False,
            reason_code="queue_snapshot_produced_at_in_future",
            message=f"Queue snapshot produced_at is {abs(produced_age):.3f}s in the future.",
            clock_model="restart_wall_utc",
            age_seconds=produced_age,
            detail=["queue_snapshot_produced_at_in_future", *detail],
        )
    if produced_age > effective_limit:
        return _result(
            fresh=False,
            reason_code="queue_snapshot_produced_at_stale",
            message=(
                f"Queue snapshot produced_at age {produced_age:.3f}s exceeds the "
                f"{limit_seconds:g}s freshness window plus {grace_seconds:g}s launch handoff grace."
            ),
            clock_model="restart_wall_utc",
            age_seconds=produced_age,
            detail=["queue_snapshot_produced_at_stale", *detail],
        )
    try:
        file_age = now.timestamp() - snapshot_path.stat().st_mtime
    except OSError as exc:
        return _result(
            fresh=False,
            reason_code="queue_snapshot_file_time_unavailable",
            message=f"Queue snapshot file timestamp could not be verified: {exc}",
            clock_model="restart_wall_utc",
            age_seconds=produced_age,
            detail=["queue_snapshot_file_time_unavailable", *detail],
        )
    detail.append(f"file_age_seconds={file_age:.3f}")
    if file_age < -abs(float(clock_skew_seconds)):
        return _result(
            fresh=False,
            reason_code="queue_snapshot_file_mtime_in_future",
            message=f"Queue snapshot file timestamp is {abs(file_age):.3f}s in the future.",
            clock_model="restart_wall_utc",
            age_seconds=produced_age,
            detail=["queue_snapshot_file_mtime_in_future", *detail],
        )
    if file_age > effective_limit:
        return _result(
            fresh=False,
            reason_code="queue_snapshot_file_mtime_stale",
            message=(
                f"Queue snapshot file age {file_age:.3f}s exceeds the "
                f"{limit_seconds:g}s freshness window plus {grace_seconds:g}s launch handoff grace."
            ),
            clock_model="restart_wall_utc",
            age_seconds=produced_age,
            detail=["queue_snapshot_file_mtime_stale", *detail],
        )
    return _result(
        fresh=True,
        reason_code="queue_snapshot_fresh",
        message=f"Queue snapshot is fresh ({max(0.0, produced_age):.3f}s, restart-safe UTC clock).",
        clock_model="restart_wall_utc",
        age_seconds=produced_age,
        detail=detail,
    )


__all__ = [
    "QUEUE_SNAPSHOT_FRESHNESS_CLOCK_SKEW_SECONDS",
    "QUEUE_SNAPSHOT_FRESHNESS_DEFAULT_SECONDS",
    "QUEUE_SNAPSHOT_FRESHNESS_HANDOFF_GRACE_SECONDS",
    "QUEUE_SNAPSHOT_FRESHNESS_MAX_SECONDS",
    "QUEUE_SNAPSHOT_FRESHNESS_MIN_SECONDS",
    "QueueSnapshotFreshnessAnchor",
    "QueueSnapshotFreshnessResult",
    "build_queue_snapshot_freshness_anchor",
    "evaluate_queue_snapshot_freshness",
    "normalize_queue_snapshot_freshness_seconds",
]
