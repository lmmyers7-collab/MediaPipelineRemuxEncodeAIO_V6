"""Durable storage for backend-owned Run Monitor artifacts.

Python writes before a pipeline process is spawned, when that spawn fails, or after
the backend force-stop service has terminated the correlated process tree. While
PowerShell is alive, the engine is the sole writer and uses a cross-process lock
around read/modify/replace. Ordinary readers never mutate files.
"""

from __future__ import annotations

import json
import os
import re
import time
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from mediapipeline.contracts.run_monitor import (
    RUN_MONITOR_POINTER_SCHEMA_VERSION,
    TERMINAL_RUN_LIFECYCLE_STATES,
    TERMINAL_ITEM_LIFECYCLE_STATES,
    RunMonitorPointer,
    RunMonitorRecord,
)


RUN_MONITOR_DIRECTORY_NAME = "RunMonitor"
RUN_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")


def _safe_run_id(run_id: str) -> str:
    normalized = str(run_id or "").strip()
    if not RUN_ID_PATTERN.fullmatch(normalized) or normalized.casefold() == "latest":
        raise ValueError("run_id contains unsafe path characters")
    return normalized


def _atomic_write_json(path: Path, payload: Mapping[str, Any], *, replace_retries: int = 7) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = path.with_name(f".{path.name}.{os.getpid()}.{time.time_ns()}.tmp")
    serialized = json.dumps(payload, ensure_ascii=False, allow_nan=False, indent=2, sort_keys=False) + "\n"
    try:
        with temporary_path.open("w", encoding="utf-8", newline="\n") as handle:
            handle.write(serialized)
            handle.flush()
            os.fsync(handle.fileno())
        for attempt in range(max(1, replace_retries)):
            try:
                os.replace(temporary_path, path)
                break
            except PermissionError:
                if attempt + 1 >= max(1, replace_retries):
                    raise
                time.sleep(min(1.0, 0.05 * (2**attempt)))
    finally:
        try:
            temporary_path.unlink(missing_ok=True)
        except OSError:
            pass


class RunMonitorStore:
    """Atomic per-run storage with a validated latest pointer and bounded history."""

    def __init__(self, state_root: Path, *, retention_count: int = 10) -> None:
        self.state_root = Path(state_root)
        self.root = self.state_root / RUN_MONITOR_DIRECTORY_NAME
        self.retention_count = max(1, int(retention_count))

    @property
    def latest_pointer_path(self) -> Path:
        return self.root / "latest.json"

    def path_for_run(self, run_id: str) -> Path:
        return self.root / f"{_safe_run_id(run_id)}.json"

    def write(self, payload: RunMonitorRecord | Mapping[str, Any]) -> RunMonitorRecord:
        record = payload if isinstance(payload, RunMonitorRecord) else RunMonitorRecord.model_validate(payload)
        run_id = _safe_run_id(record.run.run_id)
        run_path = self.path_for_run(run_id)
        existing_run = run_path.exists()
        latest_run_id = self._read_latest_run_id()
        if run_path.exists():
            current = RunMonitorRecord.model_validate(json.loads(run_path.read_text(encoding="utf-8")))
            if record.write_sequence <= current.write_sequence:
                raise ValueError("write_sequence must increase for an existing run monitor")
            if self._membership_signature(record) != self._membership_signature(current):
                raise ValueError("accepted run membership is immutable after the monitor is created")
            if current.run.lifecycle_state in TERMINAL_RUN_LIFECYCLE_STATES:
                if record.run.lifecycle_state != current.run.lifecycle_state:
                    raise ValueError("terminal run monitor state cannot change")
                if record.items != current.items or record.current_workers != current.current_workers:
                    raise ValueError("terminal run monitor evidence is immutable")
            current_items = {item.job_id: item for item in current.items}
            for item in record.items:
                previous = current_items[item.job_id]
                if (
                    previous.lifecycle_state in TERMINAL_ITEM_LIFECYCLE_STATES
                    and item.lifecycle_state != previous.lifecycle_state
                ):
                    raise ValueError(f"terminal item state cannot change for {item.job_id}")
        record_payload = record.model_dump(mode="json")
        pointer = RunMonitorPointer(
            schema_version=RUN_MONITOR_POINTER_SCHEMA_VERSION,
            run_id=run_id,
            updated_at=record.run.updated_at,
        )
        _atomic_write_json(run_path, record_payload)
        # A late event for an older run may update that run's durable history,
        # but it must never steal the discovery pointer from a newer run.
        update_latest_pointer = not existing_run or latest_run_id in {None, run_id}
        if update_latest_pointer:
            _atomic_write_json(self.latest_pointer_path, pointer.model_dump(mode="json"))
            latest_run_id = run_id
        self._prune_terminal_history(latest_run_id=latest_run_id or run_id)
        return record

    def repair_latest_pointer(self, record: RunMonitorRecord) -> None:
        """Repair discovery after a per-run write succeeded but pointer write failed."""

        run_id = _safe_run_id(record.run.run_id)
        persisted = self.read(run_id)
        if persisted is None or persisted != record:
            raise ValueError("latest pointer repair requires the exact persisted run monitor")
        latest_run_id = self._read_latest_run_id()
        if latest_run_id not in {None, run_id}:
            return
        pointer = RunMonitorPointer(
            schema_version=RUN_MONITOR_POINTER_SCHEMA_VERSION,
            run_id=run_id,
            updated_at=record.run.updated_at,
        )
        _atomic_write_json(self.latest_pointer_path, pointer.model_dump(mode="json"))

    @staticmethod
    def _membership_signature(record: RunMonitorRecord) -> tuple[tuple[Any, ...], ...]:
        header = (
            "__run__",
            record.run.command_id,
            record.run.accepted_queue.schema_version,
            record.run.accepted_queue.fingerprint,
            record.run.accepted_queue.accepted_count,
        )
        items = tuple(
            (
                item.job_id,
                item.source_identity.value,
                item.source_identity.algorithm,
                item.source_path.casefold(),
                item.display_name,
                item.parent_context,
                item.position,
                item.total,
                item.routes.planned.state,
                item.routes.planned.route,
                item.routes.planned.reason,
                item.routes.planned.reason_code,
            )
            for item in record.items
        )
        return (header, *items)

    def read(self, run_id: str | None = None) -> RunMonitorRecord | None:
        selected_run_id = _safe_run_id(run_id) if run_id else self._read_latest_run_id()
        if not selected_run_id:
            return None
        run_path = self.path_for_run(selected_run_id)
        if not run_path.exists():
            return None
        payload = json.loads(run_path.read_text(encoding="utf-8"))
        record = RunMonitorRecord.model_validate(payload)
        if record.run.run_id != selected_run_id:
            raise ValueError("run monitor filename and run_id do not match")
        return record

    def _read_latest_run_id(self) -> str | None:
        if not self.latest_pointer_path.exists():
            return None
        payload = json.loads(self.latest_pointer_path.read_text(encoding="utf-8"))
        return _safe_run_id(RunMonitorPointer.model_validate(payload).run_id)

    def _prune_terminal_history(self, *, latest_run_id: str) -> None:
        if not self.root.exists():
            return
        terminal_records: list[tuple[int, str, Path]] = []
        for path in self.root.glob("*.json"):
            if path.name == "latest.json":
                continue
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
                record = RunMonitorRecord.model_validate(payload)
            except Exception:
                continue
            if record.run.lifecycle_state not in TERMINAL_RUN_LIFECYCLE_STATES:
                continue
            try:
                modified_ns = path.stat().st_mtime_ns
            except OSError:
                continue
            terminal_records.append((modified_ns, record.run.run_id, path))
        terminal_records.sort(key=lambda value: (value[0], value[1]), reverse=True)
        retained_terminal_ids = {run_id for _, run_id, _ in terminal_records[: self.retention_count]}
        retained_terminal_ids.add(latest_run_id)
        for _, run_id, path in terminal_records:
            if run_id in retained_terminal_ids:
                continue
            try:
                path.unlink()
            except OSError:
                continue


__all__ = ["RUN_MONITOR_DIRECTORY_NAME", "RUN_ID_PATTERN", "RunMonitorStore"]
