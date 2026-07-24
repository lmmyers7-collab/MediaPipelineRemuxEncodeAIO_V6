from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime
import json
import logging
import os
import tempfile
import threading
import time
from pathlib import Path
from typing import Any, Callable

from .command_journal_policy import (
    COMMAND_HISTORY_SCHEMA_VERSION,
    bounded_command_evidence,
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
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self.path = path
        self.state_db_root = state_db_root
        self.max_entries = max(1, int(max_entries))
        self.logger = logger or logging.getLogger(__name__)
        self._clock = clock or (lambda: datetime.now(UTC))
        self._lock = threading.Lock()
        self._last_json_save_ok: bool | None = None
        self._last_json_save_error = ""
        self._last_sqlite_mirror_ok: bool | None = None
        self._last_sqlite_mirror_error = ""
        self._load_error = ""
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
        entry = self._summarize_payload(payload, request=request)
        with self._lock:
            if self._load_error:
                message = (
                    "Local API command journal is unavailable because authoritative history could not be loaded: "
                    f"{self._load_error}"
                )
                if strict:
                    raise RuntimeError(message)
                self.logger.warning("%s New command evidence was not recorded.", message)
                return
            previous_entries = list(self._entries)
            self._entries.insert(0, entry)
            del self._entries[self.max_entries :]
            try:
                self._save_locked(strict=strict)
                self._mirror_sqlite_locked(entry)
            except Exception:
                self._entries = previous_entries
                raise

    def reserve_strict_command(
        self,
        *,
        command_id: str,
        route: str,
        request_fingerprint: str,
        accepted_payload: Mapping[str, Any],
        request: Mapping[str, Any],
    ) -> dict[str, Any]:
        """Atomically reserve a strict command identity before mutation."""

        with self._lock:
            if self._load_error:
                raise RuntimeError(
                    "Local API command journal is unavailable because authoritative history could not be loaded: "
                    f"{self._load_error}"
                )
            existing = self._strict_entry_locked(command_id)
            if existing is not None:
                data = existing.get("data")
                evidence = data if isinstance(data, dict) else {}
                existing_route = str(evidence.get("route") or "")
                existing_fingerprint = str(evidence.get("request_fingerprint") or "")
                if existing_route != route or existing_fingerprint != request_fingerprint:
                    return {
                        "action": "conflict",
                        "code": "command_id_payload_conflict",
                        "command_id": command_id,
                        "mutation_performed": False,
                    }
                response_payload = evidence.get("strict_response_payload")
                if isinstance(response_payload, dict):
                    return {
                        "action": "replay",
                        "command_id": command_id,
                        "response_status": self._response_status(evidence.get("response_status")),
                        "response_payload": dict(response_payload),
                        "mutation_performed": False,
                    }
                phase = str(evidence.get("evidence_phase") or "accepted")
                return {
                    "action": "blocked",
                    "code": "command_outcome_indeterminate" if phase == "indeterminate" else "command_in_progress",
                    "command_id": command_id,
                    "mutation_performed": False,
                }

            payload = dict(accepted_payload)
            data = dict(payload.get("data") or {})
            data.update(
                {
                    "command_id": command_id,
                    "route": route,
                    "request_fingerprint": request_fingerprint,
                    "evidence_phase": "accepted",
                }
            )
            payload["data"] = data
            entry = self._summarize_payload(payload, request=request)
            previous_entries = list(self._entries)
            self._entries.insert(0, entry)
            del self._entries[self.max_entries :]
            try:
                self._save_locked(strict=True)
                self._mirror_sqlite_locked(entry)
            except Exception:
                self._entries = previous_entries
                raise
            return {
                "action": "execute",
                "command_id": command_id,
                "mutation_performed": False,
            }

    def complete_strict_command(
        self,
        *,
        command_id: str,
        route: str,
        request_fingerprint: str,
        response_payload: Mapping[str, Any],
        response_status: int,
        request: Mapping[str, Any] | None = None,
    ) -> None:
        """Persist replayable terminal evidence linked to an existing reservation."""

        if not is_command_result_payload(response_payload):
            raise ValueError("strict command terminal response must use desktop_command_result.v1")
        with self._lock:
            if self._load_error:
                raise RuntimeError(
                    "Local API command journal is unavailable because authoritative history could not be loaded: "
                    f"{self._load_error}"
                )
            existing = self._strict_entry_locked(command_id)
            if existing is None:
                raise RuntimeError("strict command reservation is missing")
            existing_data = existing.get("data")
            evidence = existing_data if isinstance(existing_data, dict) else {}
            if (
                str(evidence.get("route") or "") != route
                or str(evidence.get("request_fingerprint") or "") != request_fingerprint
            ):
                raise RuntimeError("strict command reservation identity does not match terminal evidence")

            payload = dict(response_payload)
            data = dict(payload.get("data") or {})
            data.update(
                {
                    "command_id": command_id,
                    "route": route,
                    "request_fingerprint": request_fingerprint,
                    "response_status": self._response_status(response_status),
                    "strict_response_payload": bounded_command_evidence(response_payload),
                }
            )
            payload["data"] = data
            entry = self._summarize_payload(payload, request=request)
            previous_entries = list(self._entries)
            self._entries.insert(0, entry)
            del self._entries[self.max_entries :]
            try:
                self._save_locked(strict=True)
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

    def _summarize_payload(
        self,
        payload: Mapping[str, Any],
        *,
        request: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        entry = summarize_command_payload(payload, request=request)
        entry["at"] = self._clock().isoformat()
        return entry

    def _strict_entry_locked(self, command_id: str) -> dict[str, Any] | None:
        for entry in self._entries:
            data = entry.get("data")
            if isinstance(data, dict) and str(data.get("command_id") or "") == command_id:
                return entry
        return None

    @staticmethod
    def _response_status(value: Any) -> int:
        try:
            status = int(value)
        except (TypeError, ValueError):
            return 200
        return status if 100 <= status <= 599 else 200

    def _persistence_mapping_locked(self) -> dict[str, Any]:
        json_configured = self.path is not None
        sqlite_configured = self.state_db_root is not None
        if not json_configured:
            json_status = "not_configured"
        elif self._load_error or self._last_json_save_error:
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
            if self._load_error:
                warnings.append(
                    "Authoritative JSON command history could not be loaded; strict commands are blocked until explicit recovery and restart."
                )
            else:
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
                "last_error": self._load_error or self._last_json_save_error,
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
        if self.path is None:
            return []
        try:
            if not self.path.exists():
                return []
        except OSError as exc:
            self._load_error = self._bounded_persistence_error(exc)
            self.logger.warning("Could not inspect local API command journal %s: %s", self.path, exc)
            return []
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            self._load_error = self._bounded_persistence_error(exc)
            self.logger.warning("Could not load local API command journal %s: %s", self.path, exc)
            return []
        try:
            if not isinstance(payload, dict):
                raise ValueError("journal root must be an object")
            if payload.get("schema_version") != COMMAND_HISTORY_SCHEMA_VERSION:
                raise ValueError(f"schema_version must be {COMMAND_HISTORY_SCHEMA_VERSION}")
            raw_entries = payload.get("entries")
            if not isinstance(raw_entries, list):
                raise ValueError("entries must be an array")
            if any(not isinstance(entry, dict) for entry in raw_entries):
                raise ValueError("every journal entry must be an object")
        except ValueError as exc:
            self._load_error = self._bounded_persistence_error(exc)
            self.logger.warning("Could not validate local API command journal %s: %s", self.path, exc)
            return []
        return valid_journal_entries(raw_entries, max_entries=self.max_entries)

    def _save_locked(self, *, strict: bool = False) -> None:
        if self._load_error:
            self._last_json_save_ok = False
            if strict:
                raise RuntimeError(
                    "Local API command journal is unavailable because authoritative history could not be loaded: "
                    f"{self._load_error}"
                )
            return
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
