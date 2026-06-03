"""Coordinator persisted-state and cluster-log helpers."""
from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path
from typing import Any

from .cluster_log import format_cluster_log_line
from .protocol import LogEntryRequest

_log = logging.getLogger("mediapipeline_desktop_app.network.coordinator")


class CoordinatorStateMixin:
    def _restore_inflight_state(self) -> None:
        """Load crash-recovery state before accepting worker claims."""
        path = self._inflight_state_path()
        if self._registry.load(path):
            return
        _log.error(
            "Coordinator in-flight state restore failed for %s; refusing to start coordinator "
            "to avoid duplicate worker claims. Repair or remove the state file after confirming workers are idle.",
            path,
        )
        raise RuntimeError(
            f"Coordinator in-flight state restore failed for {path}; "
            "refusing to start until state is repaired or workers are confirmed idle."
        )

    def _inflight_state_path(self) -> Path:
        """JSON file that persists in-flight state across crashes."""
        state_file: Path = getattr(self._app.service, "app_state_path", None)
        if state_file is not None:
            return state_file.parent / "coordinator_inflight.json"
        return Path.home() / ".mediapipeline" / "coordinator_inflight.json"

    def cluster_log_path(self) -> Path:
        """Path to the aggregated cluster log (worker + coordinator events)."""
        state_file: Path = getattr(self._app.service, "app_state_path", None)
        if state_file is not None:
            return state_file.parent / "cluster.log"
        return Path.home() / ".mediapipeline" / "cluster.log"

    def _format_cluster_log_line(self, entry: LogEntryRequest) -> str:
        return format_cluster_log_line(entry)

    def _append_cluster_log(self, entry: LogEntryRequest) -> None:
        """Append one entry to ``cluster.log``, rotating when oversized."""
        path: Path | None = None
        try:
            path = self.cluster_log_path()
            line = self._format_cluster_log_line(entry)
            path.parent.mkdir(parents=True, exist_ok=True)
            with self._cluster_log_lock:
                # Cheap rotation: if the file is too big, move it to .1 and
                # start fresh.  Single backup — operators tail the live file.
                try:
                    size = path.stat().st_size if path.exists() else 0
                except OSError as exc:
                    _log.warning("Failed to inspect cluster log size for %s before rotation check: %s", path, exc)
                    size = 0
                if size >= self._cluster_log_max_bytes:
                    backup = path.with_suffix(path.suffix + ".1")
                    try:
                        if backup.exists():
                            backup.unlink()
                        path.rename(backup)
                    except OSError as exc:
                        # Rotation is best-effort; never block logging, but keep
                        # the failure visible because a stuck cluster.log can grow
                        # indefinitely during unattended network-mode runs.
                        _log.warning("Failed to rotate cluster log %s to %s: %s", path, backup, exc)
                with path.open("a", encoding="utf-8") as fh:
                    fh.write(line)
        except Exception:
            if path is None:
                _log.exception("Failed to resolve cluster log path.")
            else:
                _log.exception("Failed to prepare or append cluster log %s", path)

    def log_cluster_event(
        self,
        *,
        level: str = "INFO",
        event: str,
        message: str = "",
        worker_id: str = "",
        worker_name: str = "",
        role: str = "coordinator",
        job_id: str = "",
        source_path: str = "",
    ) -> None:
        """Convenience used by the coordinator itself for its own events.

        Workers post via ``/api/log``; the handler ultimately calls
        :meth:`_append_cluster_log` with the same machinery.
        """
        if not worker_name and role == "coordinator":
            worker_name = "coordinator"
        if not worker_id and role == "coordinator":
            worker_id = str(getattr(self._app, "_machine_id", "") or "coordinator")
        entry = LogEntryRequest(
            timestamp   = datetime.now().astimezone().isoformat(timespec="seconds"),
            worker_id   = worker_id,
            worker_name = worker_name,
            role        = role,
            level       = level,
            event       = event,
            message     = message,
            job_id      = job_id,
            source_path = source_path,
        )
        self._append_cluster_log(entry)

    def _safe_log_cluster_event(self, context: str, **kwargs: Any) -> None:
        """Emit a best-effort coordinator cluster event without changing control flow."""
        try:
            self.log_cluster_event(**kwargs)
        except Exception as exc:
            job_id = str(kwargs.get("job_id", "") or "")
            _log.warning(
                "Failed to emit %s cluster event for job %s: %s",
                context,
                job_id[:8],
                exc,
            )
