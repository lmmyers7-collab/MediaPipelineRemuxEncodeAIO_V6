from __future__ import annotations

from collections.abc import Mapping
import json
import logging
import os
import tempfile
import threading
from pathlib import Path
from typing import Any

from .command_journal_policy import (
    COMMAND_HISTORY_SCHEMA_VERSION,
    COMMAND_RESULT_SCHEMA_VERSION,
    command_history_mapping,
    is_command_result_payload,
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
        max_entries: int = 50,
        logger: logging.Logger | None = None,
    ) -> None:
        self.path = path
        self.max_entries = max(1, int(max_entries))
        self.logger = logger or logging.getLogger(__name__)
        self._lock = threading.Lock()
        self._entries: list[dict[str, Any]] = self._load()

    def record(self, payload: Mapping[str, Any]) -> None:
        if not is_command_result_payload(payload):
            return
        entry = summarize_command_payload(payload)
        with self._lock:
            self._entries.insert(0, entry)
            del self._entries[self.max_entries :]
            self._save_locked()

    def to_mapping(self, *, limit: int = 20) -> dict[str, Any]:
        with self._lock:
            return command_history_mapping(self._entries, limit=limit, max_entries=self.max_entries)

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

    def _save_locked(self) -> None:
        if self.path is None:
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
            os.replace(tmp_path, self.path)
            tmp_path = None
        except (OSError, TypeError, ValueError) as exc:
            if tmp_path is not None:
                try:
                    tmp_path.unlink(missing_ok=True)
                except OSError as cleanup_exc:
                    self.logger.warning("Could not remove temporary local API command journal %s: %s", tmp_path, cleanup_exc)
            self.logger.warning("Could not save local API command journal %s: %s", self.path, exc)
