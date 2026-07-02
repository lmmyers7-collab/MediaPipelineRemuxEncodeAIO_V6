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
from datetime import datetime, UTC
from pathlib import Path
from typing import Any

CURRENT_SCHEMA_VERSION = 2
STATE_DB_FILENAME = "mediapipeline_state.sqlite3"
STATE_DB_MAINTENANCE_MARKER_FILENAME = "state_db_maintenance.json"
DEFAULT_STATE_DB_MAINTENANCE_INTERVAL_SECONDS = 21600
DEFAULT_STATE_DB_WAL_REVIEW_BYTES = 33_554_432
DEFAULT_STATE_DB_COMPLETED_JOBS_MAX_ROWS = 250_000


class StateDbError(RuntimeError):
    """Base class for state DB failures."""


class StateDbIncompatibleVersion(StateDbError):
    """Raised when a DB was created by a newer schema version."""


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()


def _json_text(value: Mapping[str, Any] | list[Any] | None) -> str:
    return json.dumps(value or {}, ensure_ascii=False, sort_keys=True, allow_nan=False, default=str)


def _payload_hash(payload_json: str) -> str:
    return hashlib.sha256(payload_json.encode("utf-8")).hexdigest()


def _scalar_text(value: Any, *, limit: int = 500) -> str:
    text = "" if value is None else str(value)
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 3)] + "..."


def open_state_db(root: Path | str) -> StateDb:
    """Open the SQLite mirror under a runtime state root."""

    db = StateDb(Path(root) / STATE_DB_FILENAME)
    db.apply_migrations()
    return db


def maybe_maintain_state_db(
    root: Path | str,
    *,
    interval_seconds: int = DEFAULT_STATE_DB_MAINTENANCE_INTERVAL_SECONDS,
    wal_review_bytes: int = DEFAULT_STATE_DB_WAL_REVIEW_BYTES,
    completed_jobs_max_rows: int = DEFAULT_STATE_DB_COMPLETED_JOBS_MAX_ROWS,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Best-effort SQLite mirror maintenance.

    JSON state remains authoritative; failures here are bounded observability
    evidence and intentionally do not raise into callers that just finished a
    successful mirror write.
    """

    root_path = Path(root)
    db_path = root_path / STATE_DB_FILENAME
    wal_path = db_path.with_name(f"{db_path.name}-wal")
    shm_path = db_path.with_name(f"{db_path.name}-shm")
    marker_path = root_path / STATE_DB_MAINTENANCE_MARKER_FILENAME
    checked_at_dt = (now or datetime.now(UTC)).astimezone(UTC)
    checked_at = checked_at_dt.isoformat()
    interval = max(60, int(interval_seconds or DEFAULT_STATE_DB_MAINTENANCE_INTERVAL_SECONDS))
    wal_threshold = max(1_048_576, int(wal_review_bytes or DEFAULT_STATE_DB_WAL_REVIEW_BYTES))
    completed_jobs_limit = max(1_000, int(completed_jobs_max_rows or DEFAULT_STATE_DB_COMPLETED_JOBS_MAX_ROWS))
    marker = _read_json_mapping(marker_path)
    last_maintenance_at = str(marker.get("last_maintenance_at") or "")
    last_age_seconds = _timestamp_age_seconds(last_maintenance_at, checked_at_dt)
    db_size = _file_size(db_path)
    wal_size = _file_size(wal_path)
    shm_size = _file_size(shm_path)
    reason = ""
    if wal_size >= wal_threshold:
        reason = "wal_threshold"
    elif last_age_seconds is None or last_age_seconds >= interval:
        reason = "interval"

    payload: dict[str, Any] = {
        "schema_version": "state_db_maintenance_marker.v1",
        "checked_at": checked_at,
        "path": str(db_path),
        "db_size_bytes": db_size,
        "wal_size_bytes": wal_size,
        "shm_size_bytes": shm_size,
        "interval_seconds": interval,
        "wal_review_bytes": wal_threshold,
        "completed_jobs_max_rows": completed_jobs_limit,
        "last_maintenance_at": last_maintenance_at,
        "last_maintenance_age_seconds": last_age_seconds,
        "ran": False,
        "reason": reason,
        "ok": True,
        "error": "",
    }
    if not reason:
        _write_json_marker(marker_path, payload)
        return payload

    try:
        result = open_state_db(root_path).maintenance(max_completed_jobs=completed_jobs_limit)
        payload["ran"] = True
        payload["last_maintenance_at"] = checked_at
        payload["last_maintenance_age_seconds"] = 0
        payload["result"] = {
            "deleted_counts": result.get("deleted_counts", {}),
            "checkpoint": result.get("checkpoint", []),
            "health": result.get("health", {}),
        }
    except Exception as exc:
        payload["ok"] = False
        payload["error"] = _scalar_text(exc, limit=1000)
    _write_json_marker(marker_path, payload)
    return payload


def _read_json_mapping(path: Path) -> Mapping[str, Any]:
    try:
        with path.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
        return payload if isinstance(payload, Mapping) else {}
    except Exception:
        return {}


def _write_json_marker(path: Path, payload: Mapping[str, Any]) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = path.with_name(f"{path.name}.tmp")
        temp_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")
        temp_path.replace(path)
    except OSError:
        return


def _timestamp_age_seconds(value: str, now: datetime) -> int | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    age = (now - parsed.astimezone(UTC)).total_seconds()
    return max(0, int(age))


def _file_size(path: Path) -> int:
    try:
        return int(path.stat().st_size)
    except OSError:
        return 0


@dataclass
class StateDb:
    path: Path
    timeout_seconds: float = 5.0
    _lock: threading.Lock = field(default_factory=threading.Lock, init=False, repr=False)
    _write_failures: int = field(default=0, init=False, repr=False)

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
                    version = 1
                if version < 2:
                    self._apply_migration_2(conn)
                    conn.execute("PRAGMA user_version = 2")
                conn.commit()

    def _note_write_failure(self) -> None:
        self._write_failures += 1

    def _file_size(self, path: Path) -> int:
        try:
            return int(path.stat().st_size)
        except OSError:
            return 0

    def _table_counts(self, conn: sqlite3.Connection) -> dict[str, int]:
        counts: dict[str, int] = {}
        for table in ("commands", "events", "queue_snapshots", "completed_jobs"):
            counts[table] = int(conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
        return counts

    def health_counters(self) -> dict[str, Any]:
        with self._lock:
            with self.connection() as conn:
                counts = self._table_counts(conn)
        wal_path = self.path.with_name(f"{self.path.name}-wal")
        shm_path = self.path.with_name(f"{self.path.name}-shm")
        return {
            "path": str(self.path),
            "db_size_bytes": self._file_size(self.path),
            "wal_size_bytes": self._file_size(wal_path),
            "shm_size_bytes": self._file_size(shm_path),
            "write_failures": int(self._write_failures),
            "counts": counts,
        }

    def maintenance(
        self,
        *,
        max_commands: int = 5000,
        max_events: int = 50000,
        max_queue_snapshots: int = 1000,
        max_completed_jobs: int = DEFAULT_STATE_DB_COMPLETED_JOBS_MAX_ROWS,
        checkpoint_wal: bool = True,
    ) -> dict[str, Any]:
        limits = {
            "commands": max(0, int(max_commands)),
            "events": max(0, int(max_events)),
            "queue_snapshots": max(0, int(max_queue_snapshots)),
            "completed_jobs": max(0, int(max_completed_jobs)),
        }
        deleted: dict[str, int] = {}
        checkpoint_result: list[tuple[Any, ...]] = []
        with self._lock:
            with self.connection() as conn:
                before_counts = self._table_counts(conn)
                for table, keep_count in limits.items():
                    deleted_count = int(
                        conn.execute(
                            f"""
                            DELETE FROM {table}
                            WHERE id NOT IN (
                                SELECT id FROM {table}
                                ORDER BY id DESC
                                LIMIT ?
                            )
                            """,
                            (keep_count,),
                        ).rowcount
                    )
                    deleted[table] = max(0, deleted_count)
                conn.commit()
                if checkpoint_wal:
                    checkpoint_result = [tuple(row) for row in conn.execute("PRAGMA wal_checkpoint(TRUNCATE)").fetchall()]
                after_counts = self._table_counts(conn)
        health = self.health_counters()
        return {
            "schema_version": "state_db_maintenance.v1",
            "path": str(self.path),
            "before_counts": before_counts,
            "after_counts": after_counts,
            "deleted_counts": deleted,
            "checkpoint": checkpoint_result,
            "health": health,
        }

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

    def _apply_migration_2(self, conn: sqlite3.Connection) -> None:
        conn.executescript(
            """
            DROP TABLE IF EXISTS completed_jobs_append_rows;
            CREATE TABLE completed_jobs_append_rows (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                recorded_at TEXT NOT NULL,
                job_key TEXT NOT NULL,
                output_path TEXT NOT NULL,
                sidecar_path TEXT NOT NULL,
                completed_at TEXT NOT NULL,
                payload_hash TEXT NOT NULL,
                payload_json TEXT NOT NULL
            );
            INSERT INTO completed_jobs_append_rows(
                id, recorded_at, job_key, output_path, sidecar_path,
                completed_at, payload_hash, payload_json
            )
            SELECT
                id, recorded_at, job_key, output_path, sidecar_path,
                completed_at, payload_hash, payload_json
            FROM completed_jobs
            ORDER BY id;
            DROP TABLE completed_jobs;
            ALTER TABLE completed_jobs_append_rows RENAME TO completed_jobs;
            CREATE INDEX IF NOT EXISTS idx_completed_jobs_recorded_at ON completed_jobs(recorded_at DESC);
            CREATE INDEX IF NOT EXISTS idx_completed_jobs_output_path ON completed_jobs(output_path);
            CREATE INDEX IF NOT EXISTS idx_completed_jobs_job_key ON completed_jobs(job_key);
            """
        )
        conn.execute(
            "INSERT OR IGNORE INTO schema_migrations(version, name, applied_at) VALUES (?, ?, ?)",
            (2, "completed_jobs_append_rows", _utc_now()),
        )

    def record_command(self, command_event: Mapping[str, Any]) -> None:
        payload_json = _json_text(command_event)
        try:
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
        except Exception:
            self._note_write_failure()
            raise

    def record_stage_event(self, stage_event: Mapping[str, Any]) -> None:
        payload_json = _json_text(stage_event)
        try:
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
        except Exception:
            self._note_write_failure()
            raise

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
        try:
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
        except Exception:
            self._note_write_failure()
            raise

    def record_completed_job(self, completed_job: Mapping[str, Any]) -> None:
        payload_json = _json_text(completed_job)
        payload_hash = _payload_hash(payload_json)
        output_path = _scalar_text(completed_job.get("output_path"), limit=1000)
        sidecar_path = _scalar_text(completed_job.get("sidecar_path"), limit=1000)
        completed_at = _scalar_text(completed_job.get("completed_at") or completed_job.get("finished_at"), limit=120)
        # Manifest rows without a job_id still need append-only identity.
        # Output paths can repeat across retries or replacements.
        job_key = (
            _scalar_text(completed_job.get("job_id"), limit=300)
            or payload_hash
        )
        try:
            with self._lock:
                with self.connection() as conn:
                    conn.execute(
                        """
                        INSERT INTO completed_jobs(
                            recorded_at, job_key, output_path, sidecar_path,
                            completed_at, payload_hash, payload_json
                        )
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            _utc_now(),
                            job_key,
                            output_path,
                            sidecar_path,
                            completed_at,
                            payload_hash,
                            payload_json,
                        ),
                    )
                    conn.commit()
        except Exception:
            self._note_write_failure()
            raise

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
    "DEFAULT_STATE_DB_MAINTENANCE_INTERVAL_SECONDS",
    "DEFAULT_STATE_DB_WAL_REVIEW_BYTES",
    "DEFAULT_STATE_DB_COMPLETED_JOBS_MAX_ROWS",
    "STATE_DB_MAINTENANCE_MARKER_FILENAME",
    "STATE_DB_FILENAME",
    "StateDb",
    "StateDbError",
    "StateDbIncompatibleVersion",
    "maybe_maintain_state_db",
    "open_state_db",
]
