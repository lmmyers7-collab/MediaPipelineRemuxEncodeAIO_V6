"""SQLite mirror storage for Phase 4 shadow writes.

The JSON files under the runtime state tree remain authoritative. This module
creates a durable SQLite mirror that can be populated opportunistically by new
paths without changing existing reads or operator-visible behavior.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
import threading
from collections.abc import Mapping
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

CURRENT_SCHEMA_VERSION = 1
STATE_DB_FILENAME = "mediapipeline_state.sqlite3"


class StateDbError(RuntimeError):
    """Base class for state DB failures."""


class StateDbIncompatibleVersion(StateDbError):
    """Raised when a DB was created by a newer schema version."""


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _json_text(value: Mapping[str, Any] | list[Any] | None) -> str:
    return json.dumps(value or {}, ensure_ascii=False, sort_keys=True, allow_nan=False, default=str)


def _payload_hash(payload_json: str) -> str:
    return hashlib.sha256(payload_json.encode("utf-8")).hexdigest()


def _scalar_text(value: Any, *, limit: int = 500) -> str:
    text = "" if value is None else str(value)
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 3)] + "..."


def open_state_db(root: Path | str) -> "StateDb":
    """Open the SQLite mirror under a runtime state root."""

    db = StateDb(Path(root) / STATE_DB_FILENAME)
    db.apply_migrations()
    return db


@dataclass
class StateDb:
    path: Path
    timeout_seconds: float = 5.0
    _lock: threading.Lock = field(default_factory=threading.Lock, init=False, repr=False)

    def connect(self) -> sqlite3.Connection:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(self.path), timeout=self.timeout_seconds)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA busy_timeout = 5000")
        conn.execute("PRAGMA journal_mode = WAL")
        return conn

    @contextmanager
    def connection(self) -> Any:
        conn = self.connect()
        try:
            yield conn
        finally:
            conn.close()

    def apply_migrations(self) -> None:
        with self._lock:
            with self.connection() as conn:
                version = int(conn.execute("PRAGMA user_version").fetchone()[0])
                if version > CURRENT_SCHEMA_VERSION:
                    raise StateDbIncompatibleVersion(
                        f"State DB schema version {version} is newer than supported version {CURRENT_SCHEMA_VERSION}."
                    )
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS schema_migrations (
                        version INTEGER PRIMARY KEY,
                        name TEXT NOT NULL,
                        applied_at TEXT NOT NULL
                    )
                    """
                )
                if version < 1:
                    self._apply_migration_1(conn)
                    conn.execute("PRAGMA user_version = 1")
                conn.commit()

    def _apply_migration_1(self, conn: sqlite3.Connection) -> None:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS commands (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                recorded_at TEXT NOT NULL,
                command TEXT NOT NULL,
                ok INTEGER NOT NULL,
                severity TEXT NOT NULL,
                message TEXT NOT NULL,
                job_id TEXT NOT NULL,
                refresh_hint TEXT NOT NULL,
                payload_hash TEXT NOT NULL,
                payload_json TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_commands_recorded_at ON commands(recorded_at DESC);
            CREATE INDEX IF NOT EXISTS idx_commands_command ON commands(command);

            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                recorded_at TEXT NOT NULL,
                event_type TEXT NOT NULL,
                run_id TEXT NOT NULL,
                command_id TEXT NOT NULL,
                stage TEXT NOT NULL,
                ok INTEGER,
                payload_hash TEXT NOT NULL,
                payload_json TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_events_recorded_at ON events(recorded_at DESC);
            CREATE INDEX IF NOT EXISTS idx_events_event_type ON events(event_type);
            CREATE INDEX IF NOT EXISTS idx_events_stage ON events(stage);
            CREATE INDEX IF NOT EXISTS idx_events_run_id ON events(run_id);

            CREATE TABLE IF NOT EXISTS queue_snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                recorded_at TEXT NOT NULL,
                request_id TEXT NOT NULL,
                produced_at TEXT NOT NULL,
                source_path TEXT NOT NULL,
                row_count INTEGER NOT NULL,
                payload_hash TEXT NOT NULL,
                payload_json TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_queue_snapshots_recorded_at ON queue_snapshots(recorded_at DESC);

            CREATE TABLE IF NOT EXISTS completed_jobs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                recorded_at TEXT NOT NULL,
                job_key TEXT NOT NULL UNIQUE,
                output_path TEXT NOT NULL,
                sidecar_path TEXT NOT NULL,
                completed_at TEXT NOT NULL,
                payload_hash TEXT NOT NULL,
                payload_json TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_completed_jobs_recorded_at ON completed_jobs(recorded_at DESC);
            CREATE INDEX IF NOT EXISTS idx_completed_jobs_output_path ON completed_jobs(output_path);
            """
        )
        conn.execute(
            "INSERT OR IGNORE INTO schema_migrations(version, name, applied_at) VALUES (?, ?, ?)",
            (1, "initial_state_mirror", _utc_now()),
        )

    def record_command(self, command_event: Mapping[str, Any]) -> None:
        payload_json = _json_text(command_event)
        with self._lock:
            with self.connection() as conn:
                conn.execute(
                    """
                    INSERT INTO commands(
                        recorded_at, command, ok, severity, message, job_id,
                        refresh_hint, payload_hash, payload_json
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        _utc_now(),
                        _scalar_text(command_event.get("command"), limit=160) or "unknown",
                        1 if bool(command_event.get("ok")) else 0,
                        _scalar_text(command_event.get("severity"), limit=40) or "info",
                        _scalar_text(command_event.get("message"), limit=2000),
                        _scalar_text(command_event.get("job_id"), limit=120),
                        _scalar_text(command_event.get("refresh_hint"), limit=80),
                        _payload_hash(payload_json),
                        payload_json,
                    ),
                )
                conn.commit()

    def record_stage_event(self, stage_event: Mapping[str, Any]) -> None:
        payload_json = _json_text(stage_event)
        with self._lock:
            with self.connection() as conn:
                conn.execute(
                    """
                    INSERT INTO events(
                        recorded_at, event_type, run_id, command_id, stage,
                        ok, payload_hash, payload_json
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        _utc_now(),
                        _scalar_text(stage_event.get("event_type") or stage_event.get("journal_event_type"), limit=160)
                        or "pipeline.stage.unknown",
                        _scalar_text(stage_event.get("run_id"), limit=120),
                        _scalar_text(stage_event.get("command_id"), limit=120),
                        _scalar_text(stage_event.get("stage"), limit=80),
                        None if stage_event.get("ok") is None else 1 if bool(stage_event.get("ok")) else 0,
                        _payload_hash(payload_json),
                        payload_json,
                    ),
                )
                conn.commit()

    def record_queue_snapshot(
        self,
        snapshot: Mapping[str, Any],
        *,
        source_path: Path | str | None = None,
        request_id: str = "",
    ) -> None:
        rows = snapshot.get("rows")
        row_count = len(rows) if isinstance(rows, list) else int(snapshot.get("row_count") or 0)
        payload_json = _json_text(snapshot)
        with self._lock:
            with self.connection() as conn:
                conn.execute(
                    """
                    INSERT INTO queue_snapshots(
                        recorded_at, request_id, produced_at, source_path,
                        row_count, payload_hash, payload_json
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        _utc_now(),
                        _scalar_text(request_id or snapshot.get("desktop_queue_preview_request_id"), limit=120),
                        _scalar_text(snapshot.get("produced_at"), limit=120),
                        _scalar_text(source_path, limit=1000),
                        int(row_count),
                        _payload_hash(payload_json),
                        payload_json,
                    ),
                )
                conn.commit()

    def record_completed_job(self, completed_job: Mapping[str, Any]) -> None:
        payload_json = _json_text(completed_job)
        output_path = _scalar_text(completed_job.get("output_path"), limit=1000)
        sidecar_path = _scalar_text(completed_job.get("sidecar_path"), limit=1000)
        completed_at = _scalar_text(completed_job.get("completed_at") or completed_job.get("finished_at"), limit=120)
        job_key = (
            _scalar_text(completed_job.get("job_id"), limit=300)
            or output_path.casefold()
            or sidecar_path.casefold()
            or _payload_hash(payload_json)
        )
        with self._lock:
            with self.connection() as conn:
                conn.execute(
                    """
                    INSERT INTO completed_jobs(
                        recorded_at, job_key, output_path, sidecar_path,
                        completed_at, payload_hash, payload_json
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(job_key) DO UPDATE SET
                        recorded_at = excluded.recorded_at,
                        output_path = excluded.output_path,
                        sidecar_path = excluded.sidecar_path,
                        completed_at = excluded.completed_at,
                        payload_hash = excluded.payload_hash,
                        payload_json = excluded.payload_json
                    """,
                    (
                        _utc_now(),
                        job_key,
                        output_path,
                        sidecar_path,
                        completed_at,
                        _payload_hash(payload_json),
                        payload_json,
                    ),
                )
                conn.commit()

    def list_recent_events(self, filters: Mapping[str, Any] | None = None) -> list[dict[str, Any]]:
        filters = dict(filters or {})
        limit = max(1, min(int(filters.get("limit") or 50), 500))
        where: list[str] = []
        params: list[Any] = []
        for column in ("event_type", "stage", "run_id"):
            value = filters.get(column)
            if value:
                where.append(f"{column} = ?")
                params.append(str(value))
        sql = "SELECT * FROM events"
        if where:
            sql += " WHERE " + " AND ".join(where)
        sql += " ORDER BY id DESC LIMIT ?"
        params.append(limit)
        return self._rows(sql, params)

    def list_recent_commands(self, *, limit: int = 50) -> list[dict[str, Any]]:
        return self._rows("SELECT * FROM commands ORDER BY id DESC LIMIT ?", [max(1, min(int(limit), 500))])

    def _rows(self, sql: str, params: list[Any]) -> list[dict[str, Any]]:
        with self._lock:
            with self.connection() as conn:
                rows = conn.execute(sql, params).fetchall()
        result: list[dict[str, Any]] = []
        for row in rows:
            item = dict(row)
            payload_text = item.pop("payload_json", "{}")
            try:
                item["payload"] = json.loads(payload_text)
            except json.JSONDecodeError:
                item["payload"] = {}
            result.append(item)
        return result


__all__ = [
    "CURRENT_SCHEMA_VERSION",
    "STATE_DB_FILENAME",
    "StateDb",
    "StateDbError",
    "StateDbIncompatibleVersion",
    "open_state_db",
]
