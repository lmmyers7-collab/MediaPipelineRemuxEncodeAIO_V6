from __future__ import annotations

from collections.abc import Mapping
import json
import logging
import os
import tempfile
import threading
import time
from pathlib import Path
from typing import Any

from .command_journal_policy import (
    COMMAND_HISTORY_SCHEMA_VERSION,
    command_history_mapping,
    is_command_result_payload,
    scalar_text,
    summarize_command_payload,
    valid_journal_entries,
)


class CommandJournal:
    """Bounded command-result journal for local operator feedback.

    The journal intentionally stores command summaries, not full command data,
    because release dry runs and settings diffs can carry large payloads.
    """

    def __init__(
        self,
        *,
        path: Path | None = None,
        state_db_root: Path | None = None,
        max_entries: int = 50,
        logger: logging.Logger | None = None,
    ) -> None:
        self.path = path
        self.state_db_root = state_db_root
        self.max_entries = max(1, int(max_entries))
        self.logger = logger or logging.getLogger(__name__)
        self._lock = threading.Lock()
        self._last_json_save_ok: bool | None = None
        self._last_json_save_error = ""
        self._last_sqlite_mirror_ok: bool | None = None
        self._last_sqlite_mirror_error = ""
        self._entries: list[dict[str, Any]] = self._load()

    def record(
        self,
        payload: Mapping[str, Any],
        *,
        request: Mapping[str, Any] | None = None,
        strict: bool = False,
    ) -> None:
        if not is_command_result_payload(payload):
            return
        entry = summarize_command_payload(payload, request=request)
        with self._lock:
            previous_entries = list(self._entries)
            self._entries.insert(0, entry)
            del self._entries[self.max_entries :]
            try:
                self._save_locked(strict=strict)
                self._mirror_sqlite_locked(entry)
            except Exception:
                self._entries = previous_entries
                raise

    def to_mapping(self, *, limit: int = 20) -> dict[str, Any]:
        with self._lock:
            payload = command_history_mapping(self._entries, limit=limit, max_entries=self.max_entries)
            payload["journal_persistence"] = self._persistence_mapping_locked()
            return payload

    def _bounded_persistence_error(self, exc: Exception | str) -> str:
        return scalar_text(exc if isinstance(exc, str) else f"{type(exc).__name__}: {exc}", limit=500)

    def _persistence_mapping_locked(self) -> dict[str, Any]:
        json_configured = self.path is not None
        sqlite_configured = self.state_db_root is not None
        if not json_configured:
            json_status = "not_configured"
        elif self._last_json_save_error:
            json_status = "failed"
        elif self._last_json_save_ok is True:
            json_status = "ok"
        else:
            json_status = "not_attempted"
        if not sqlite_configured:
            sqlite_status = "not_configured"
        elif self._last_sqlite_mirror_error:
            sqlite_status = "failed"
        elif self._last_sqlite_mirror_ok is True:
            sqlite_status = "ok"
        else:
            sqlite_status = "not_attempted"

        warnings: list[str] = []
        if json_status == "not_configured":
            warnings.append("JSON command journal path is not configured; entries are memory-only.")
        elif json_status == "failed":
            warnings.append("JSON command journal persistence failed; entries may be memory-only.")
        if sqlite_status == "failed":
            warnings.append("SQLite command journal mirror failed.")

        return {
            "schema_version": "desktop_command_journal_persistence.v1",
            "degraded": bool(warnings),
            "json": {
                "configured": json_configured,
                "path": str(self.path) if self.path is not None else "",
                "status": json_status,
                "last_error": self._last_json_save_error,
            },
            "sqlite_mirror": {
                "configured": sqlite_configured,
                "state_db_root": str(self.state_db_root) if self.state_db_root is not None else "",
                "status": sqlite_status,
                "last_error": self._last_sqlite_mirror_error,
            },
            "warnings": warnings,
        }

    def _load(self) -> list[dict[str, Any]]:
        if self.path is None or not self.path.exists():
            return []
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            self.logger.warning("Could not load local API command journal %s: %s", self.path, exc)
            return []
        raw_entries = payload.get("entries") if isinstance(payload, dict) else None
        return valid_journal_entries(raw_entries, max_entries=self.max_entries)

    def _save_locked(self, *, strict: bool = False) -> None:
        if self.path is None:
            self._last_json_save_ok = False
            self._last_json_save_error = "Local API command journal path is not configured."
            if strict:
                raise RuntimeError("Local API command journal path is not configured.")
            return
        payload = {
            "schema_version": COMMAND_HISTORY_SCHEMA_VERSION,
            "entries": self._entries,
        }
        tmp_path: Path | None = None
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            fd, tmp_name = tempfile.mkstemp(
                prefix=f".{self.path.name}.",
                suffix=".tmp",
                dir=self.path.parent,
                text=True,
            )
            tmp_path = Path(tmp_name)
            with os.fdopen(fd, "w", encoding="utf-8", newline="") as handle:
                handle.write(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False))
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            delay_seconds = 0.05
            for attempt in range(7):
                try:
                    os.replace(tmp_path, self.path)
                    break
                except PermissionError:
                    if attempt >= 6:
                        raise
                    time.sleep(delay_seconds)
                    delay_seconds = min(delay_seconds * 2, 1.0)
            tmp_path = None
            self._last_json_save_ok = True
            self._last_json_save_error = ""
        except (OSError, TypeError, ValueError) as exc:
            if tmp_path is not None:
                try:
                    tmp_path.unlink(missing_ok=True)
                except OSError as cleanup_exc:
                    self.logger.warning("Could not remove temporary local API command journal %s: %s", tmp_path, cleanup_exc)
            self._last_json_save_ok = False
            self._last_json_save_error = self._bounded_persistence_error(exc)
            self.logger.warning("Could not save local API command journal %s: %s", self.path, exc)
            if strict:
                raise

    def _mirror_sqlite_locked(self, entry: Mapping[str, Any]) -> None:
        if self.state_db_root is None:
            self._last_sqlite_mirror_ok = None
            self._last_sqlite_mirror_error = ""
            return
        try:
            from mediapipeline.core.storage.db import maybe_maintain_state_db, open_state_db

            open_state_db(self.state_db_root).record_command(dict(entry))
            maybe_maintain_state_db(self.state_db_root)
            self._last_sqlite_mirror_ok = True
            self._last_sqlite_mirror_error = ""
        except Exception as exc:
            self._last_sqlite_mirror_ok = False
            self._last_sqlite_mirror_error = self._bounded_persistence_error(exc)
            self.logger.warning("Could not mirror local API command journal to SQLite: %s", exc)
