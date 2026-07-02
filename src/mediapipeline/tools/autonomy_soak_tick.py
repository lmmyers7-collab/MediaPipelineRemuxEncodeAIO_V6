from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, UTC
from pathlib import Path
from typing import Any
from collections.abc import Mapping

from mediapipeline.core.diagnostics.autonomy_health import (
    autonomy_health_payload,
    load_autonomy_growth_history,
    record_autonomy_growth_snapshot,
)
from mediapipeline.core.processes.path_evidence import LAUNCH_PATH_HEALTH_TIMEOUT_SECONDS, configured_path_health
from mediapipeline.core.publish.pending_service import PendingPublishServiceMixin
from mediapipeline.tools.autonomy_health_gate import AUTONOMY_HEALTH_BLOCKED_EXIT_CODE, resolved_paths_from_payload


AUTONOMY_SOAK_BLOCKED_EXIT_CODE = AUTONOMY_HEALTH_BLOCKED_EXIT_CODE
AUTONOMY_SOAK_REVIEW_EXIT_CODE = 75
AUTONOMY_SOAK_TICK_HISTORY_FILE_NAME = "autonomy_soak_ticks.jsonl"
AUTONOMY_SOAK_TICK_HISTORY_MAX_COUNT = 256


class _PendingScanner(PendingPublishServiceMixin):
    pass


def _read_payload(args: argparse.Namespace) -> Mapping[str, Any]:
    if args.paths_json_file:
        raw = Path(args.paths_json_file).read_text(encoding="utf-8-sig")
    else:
        raw = str(args.paths_json or "").strip()
    if not raw:
        raise ValueError("paths JSON payload is required")
    payload = json.loads(raw)
    if not isinstance(payload, Mapping):
        raise ValueError("paths JSON root must be an object")
    return payload


def run_tick_from_payload(
    payload: Mapping[str, Any],
    *,
    record_snapshot: bool = False,
    max_snapshots: int = 64,
    record_tick_history: bool = False,
    max_tick_records: int = AUTONOMY_SOAK_TICK_HISTORY_MAX_COUNT,
    fail_on_review: bool = False,
) -> dict[str, Any]:
    resolved = resolved_paths_from_payload(payload)
    history_before = load_autonomy_growth_history(resolved, max_snapshots=max_snapshots)
    pending_publish = _PendingScanner().scan_pending_publish(resolved)
    path_health = configured_path_health(
        resolved,
        timeout_seconds=LAUNCH_PATH_HEALTH_TIMEOUT_SECONDS,
    )
    health = autonomy_health_payload(
        resolved,
        pending_publish=pending_publish,
        path_health=path_health,
        growth_history=history_before,
    )
    write_result: dict[str, Any] = {}
    snapshot_recorded = False
    history = history_before
    if record_snapshot:
        write_result = record_autonomy_growth_snapshot(resolved, health, max_snapshots=max_snapshots)
        snapshot_recorded = bool(write_result.get("wrote_snapshot"))
        history = load_autonomy_growth_history(resolved, max_snapshots=max_snapshots)
    exit_code = _tick_exit_code(str(health.get("overall_status") or ""), fail_on_review=fail_on_review)
    if record_snapshot and not snapshot_recorded:
        exit_code = 2
    result = {
        "schema_version": "desktop_autonomy_soak_tick.v1",
        "ok": exit_code == 0,
        "exit_code": exit_code,
        "health": health,
        "snapshot": {
            "requested": record_snapshot,
            "recorded": snapshot_recorded,
            "write_result": write_result,
        },
        "history": _history_summary(history),
        "would_kill_active_work": False,
        "media_mutation_performed": False,
        "pending_publish_mutation_performed": False,
        "queue_mutation_performed": False,
        "cleanup_performed": False,
        "policy": (
            "Scheduler-friendly autonomy soak tick. Health polling is read-only by default; "
            "snapshot and tick history writes require explicit flags and are confined to diagnostics state."
        ),
    }
    tick_history_write_result: dict[str, Any] = {}
    tick_history_recorded = False
    if record_tick_history:
        tick_history_write_result = record_soak_tick_history(
            resolved,
            result,
            max_records=max_tick_records,
        )
        tick_history_recorded = bool(tick_history_write_result.get("wrote_record"))
        if not tick_history_recorded:
            result["exit_code"] = 2
            result["ok"] = False
    tick_history = load_soak_tick_history(resolved, max_records=max_tick_records)
    result["tick_history"] = {
        "requested": record_tick_history,
        "recorded": tick_history_recorded,
        "write_result": tick_history_write_result,
        **_tick_history_summary(tick_history),
    }
    return result


def load_soak_tick_history(
    resolved: Any,
    *,
    max_records: int = AUTONOMY_SOAK_TICK_HISTORY_MAX_COUNT,
) -> dict[str, Any]:
    history_path = _tick_history_path(resolved)
    limit = _bounded_tick_record_limit(max_records)
    records: list[dict[str, Any]] = []
    invalid_line_count = 0
    read_error = ""
    if history_path is not None and history_path.exists() and history_path.is_file():
        try:
            with history_path.open("r", encoding="utf-8") as handle:
                for raw_line in handle:
                    line = raw_line.strip()
                    if not line:
                        continue
                    try:
                        item = json.loads(line)
                    except json.JSONDecodeError:
                        invalid_line_count += 1
                        continue
                    if isinstance(item, Mapping):
                        records.append(dict(item))
                    else:
                        invalid_line_count += 1
        except OSError as exc:
            read_error = str(exc)
    retained = records[-limit:]
    return {
        "schema_version": "desktop_autonomy_soak_tick_history.v1",
        "effect": "none",
        "read_only": True,
        "history_path": str(history_path or ""),
        "record_count": len(retained),
        "total_record_count": len(records),
        "invalid_line_count": invalid_line_count,
        "max_record_count": limit,
        "read_error": read_error,
        "records": retained,
    }


def record_soak_tick_history(
    resolved: Any,
    tick_payload: Mapping[str, Any],
    *,
    now: datetime | None = None,
    max_records: int = AUTONOMY_SOAK_TICK_HISTORY_MAX_COUNT,
) -> dict[str, Any]:
    history_path = _tick_history_path(resolved)
    limit = _bounded_tick_record_limit(max_records)
    recorded_at = (now or datetime.now(UTC)).astimezone(UTC)
    record = _tick_record_from_payload(tick_payload, recorded_at)
    if history_path is None:
        return _tick_history_write_result(
            history_path=None,
            record=record,
            retained_record_count=0,
            max_records=limit,
            wrote_record=False,
            error="state_root is unavailable",
        )
    history = load_soak_tick_history(resolved, max_records=limit)
    records = [item for item in history.get("records", []) if isinstance(item, Mapping)]
    retained = [dict(item) for item in records] + [record]
    retained = retained[-limit:]
    try:
        history_path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = history_path.with_name(f"{history_path.name}.tmp")
        with temp_path.open("w", encoding="utf-8", newline="\n") as handle:
            for item in retained:
                handle.write(json.dumps(item, sort_keys=True, separators=(",", ":")))
                handle.write("\n")
        temp_path.replace(history_path)
    except OSError as exc:
        return _tick_history_write_result(
            history_path=history_path,
            record=record,
            retained_record_count=len(records),
            max_records=limit,
            wrote_record=False,
            error=str(exc),
        )
    return _tick_history_write_result(
        history_path=history_path,
        record=record,
        retained_record_count=len(retained),
        max_records=limit,
        wrote_record=True,
        error="",
    )


def _history_summary(history: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": history.get("schema_version"),
        "snapshot_path": history.get("snapshot_path"),
        "snapshot_count": history.get("snapshot_count"),
        "total_snapshot_count": history.get("total_snapshot_count"),
        "invalid_line_count": history.get("invalid_line_count"),
        "max_snapshot_count": history.get("max_snapshot_count"),
        "read_error": history.get("read_error"),
    }


def _tick_history_path(resolved: Any) -> Path | None:
    state_root = getattr(resolved, "state_root", None)
    if state_root is None:
        return None
    return Path(state_root) / "Diagnostics" / AUTONOMY_SOAK_TICK_HISTORY_FILE_NAME


def _tick_history_summary(history: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": history.get("schema_version"),
        "history_path": history.get("history_path"),
        "record_count": history.get("record_count"),
        "total_record_count": history.get("total_record_count"),
        "invalid_line_count": history.get("invalid_line_count"),
        "max_record_count": history.get("max_record_count"),
        "read_error": history.get("read_error"),
    }


def _tick_record_from_payload(tick_payload: Mapping[str, Any], recorded_at: datetime) -> dict[str, Any]:
    health = tick_payload.get("health") if isinstance(tick_payload.get("health"), Mapping) else {}
    snapshot = tick_payload.get("snapshot") if isinstance(tick_payload.get("snapshot"), Mapping) else {}
    projection = health.get("growth_projection") if isinstance(health.get("growth_projection"), Mapping) else {}
    alert = health.get("external_alert") if isinstance(health.get("external_alert"), Mapping) else {}
    blockers = _issue_list(health.get("blockers"))
    review_items = _issue_list(health.get("review_items"))
    return {
        "schema_version": "desktop_autonomy_soak_tick_record.v1",
        "recorded_at_utc": recorded_at.isoformat(timespec="seconds").replace("+00:00", "Z"),
        "health_checked_at_utc": str(health.get("checked_at_utc") or ""),
        "overall_status": str(health.get("overall_status") or "unknown"),
        "exit_code": _safe_int(tick_payload.get("exit_code")),
        "blocked_count": _safe_int(health.get("blocked_count"), fallback=len(blockers)),
        "review_count": _safe_int(health.get("review_count"), fallback=len(review_items)),
        "blocker_codes": _issue_codes(blockers),
        "review_codes": _issue_codes(review_items),
        "snapshot_requested": bool(snapshot.get("requested")),
        "snapshot_recorded": bool(snapshot.get("recorded")),
        "growth_confidence": str(projection.get("confidence") or ""),
        "projected_7_day_growth_bytes": projection.get("projected_7_day_growth_bytes"),
        "days_to_budget_exhaustion": projection.get("days_to_budget_exhaustion"),
        "alert_level": str(alert.get("alert_level") or ""),
        "alert_dedupe_key": str(alert.get("dedupe_key") or ""),
    }


def _tick_history_write_result(
    *,
    history_path: Path | None,
    record: Mapping[str, Any],
    retained_record_count: int,
    max_records: int,
    wrote_record: bool,
    error: str,
) -> dict[str, Any]:
    return {
        "schema_version": "desktop_autonomy_soak_tick_history_write.v1",
        "effect": "diagnostics_state_tick_history_write",
        "history_path": str(history_path or ""),
        "wrote_record": wrote_record,
        "retained_record_count": retained_record_count,
        "max_record_count": max_records,
        "record": dict(record),
        "error": error,
        "media_mutation_performed": False,
        "cleanup_performed": False,
        "pending_publish_mutation_performed": False,
        "queue_mutation_performed": False,
        "policy": (
            "Explicit diagnostics-state tick history write only. This helper does not touch source media, "
            "pending publish files, queue state, cleanup targets, or final outputs."
        ),
    }


def _issue_list(raw_items: Any) -> list[Mapping[str, Any]]:
    if not isinstance(raw_items, list):
        return []
    return [item for item in raw_items if isinstance(item, Mapping)]


def _issue_codes(items: list[Mapping[str, Any]], *, limit: int = 20) -> list[str]:
    codes: list[str] = []
    for item in items:
        code = str(item.get("code") or "")
        if code:
            codes.append(code)
    return codes[:limit]


def _safe_int(value: Any, *, fallback: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return fallback


def _bounded_tick_record_limit(max_records: int) -> int:
    requested = _safe_int(max_records)
    if requested <= 0:
        return AUTONOMY_SOAK_TICK_HISTORY_MAX_COUNT
    return min(requested, AUTONOMY_SOAK_TICK_HISTORY_MAX_COUNT)


def _tick_exit_code(overall_status: str, *, fail_on_review: bool) -> int:
    normalized = str(overall_status or "").casefold()
    if normalized == "blocked":
        return AUTONOMY_SOAK_BLOCKED_EXIT_CODE
    if normalized == "review" and fail_on_review:
        return AUTONOMY_SOAK_REVIEW_EXIT_CODE
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run one MediaPipeline autonomy soak health tick.")
    parser.add_argument("--paths-json", default="", help="Resolved path payload JSON.")
    parser.add_argument("--paths-json-file", default="", help="File containing resolved path payload JSON.")
    parser.add_argument("--record-snapshot", action="store_true", help="Write one bounded diagnostics growth snapshot.")
    parser.add_argument("--max-snapshots", type=int, default=64, help="Maximum retained growth snapshots.")
    parser.add_argument("--record-tick-history", action="store_true", help="Write one bounded diagnostics tick record.")
    parser.add_argument("--max-tick-records", type=int, default=AUTONOMY_SOAK_TICK_HISTORY_MAX_COUNT)
    parser.add_argument("--fail-on-review", action="store_true", help="Return a nonzero exit code when health is review.")
    args = parser.parse_args(argv)
    try:
        payload = run_tick_from_payload(
            _read_payload(args),
            record_snapshot=args.record_snapshot,
            max_snapshots=args.max_snapshots,
            record_tick_history=args.record_tick_history,
            max_tick_records=args.max_tick_records,
            fail_on_review=args.fail_on_review,
        )
    except Exception as exc:
        payload = {
            "schema_version": "desktop_autonomy_soak_tick_error.v1",
            "ok": False,
            "exit_code": 2,
            "error": str(exc),
            "would_kill_active_work": False,
            "media_mutation_performed": False,
            "pending_publish_mutation_performed": False,
            "queue_mutation_performed": False,
            "cleanup_performed": False,
        }
        print(json.dumps(payload, ensure_ascii=False))
        return 2
    print(json.dumps(payload, ensure_ascii=False))
    return int(payload.get("exit_code") or 0)


if __name__ == "__main__":
    sys.exit(main())


__all__ = [
    "AUTONOMY_SOAK_BLOCKED_EXIT_CODE",
    "AUTONOMY_SOAK_REVIEW_EXIT_CODE",
    "AUTONOMY_SOAK_TICK_HISTORY_FILE_NAME",
    "AUTONOMY_SOAK_TICK_HISTORY_MAX_COUNT",
    "load_soak_tick_history",
    "main",
    "record_soak_tick_history",
    "run_tick_from_payload",
]
