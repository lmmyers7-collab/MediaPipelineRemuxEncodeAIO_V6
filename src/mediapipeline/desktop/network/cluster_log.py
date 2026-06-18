from __future__ import annotations

from datetime import datetime
from pathlib import Path

from mediapipeline.core.network.url_policy import redact_network_secret_text

from .identity import sanitize_log_display_text
from .protocol import LogEntryRequest


def _redacted_display_text(value: object, limit: int | None = None) -> str:
    return redact_network_secret_text(sanitize_log_display_text(value, limit))


def redact_cluster_log_entry_fields(entry: LogEntryRequest) -> None:
    """Redact every rendered cluster-log field in-place."""
    entry.timestamp = _redacted_display_text(entry.timestamp, 80)
    entry.level = _redacted_display_text(entry.level, 16)
    entry.role = _redacted_display_text(entry.role, 32)
    entry.worker_id = _redacted_display_text(entry.worker_id, 64)
    entry.worker_name = _redacted_display_text(entry.worker_name, 80)
    entry.event = _redacted_display_text(entry.event, 64)
    entry.message = _redacted_display_text(entry.message, 4096)
    entry.job_id = _redacted_display_text(entry.job_id, 64)
    entry.source_path = _redacted_display_text(entry.source_path, 4096)
    worker_timestamp = getattr(entry, "_worker_ts", "")
    if worker_timestamp:
        try:
            entry._worker_ts = _redacted_display_text(worker_timestamp, 80)  # type: ignore[attr-defined]
        except Exception:
            pass


def format_cluster_log_line(entry: LogEntryRequest) -> str:
    """Format one coordinator cluster-log line.

    The leading timestamp is the coordinator receive time. A worker-supplied
    timestamp, when different, is preserved as worker_ts for clock-drift
    investigations.
    """
    timestamp = _redacted_display_text(entry.timestamp, 80) or datetime.now().astimezone().isoformat(timespec="seconds")
    level = (_redacted_display_text(entry.level, 16) or "INFO").upper().ljust(5)
    role = (_redacted_display_text(entry.role, 32) or "worker")[:11]
    name = (_redacted_display_text(entry.worker_name, 80) or _redacted_display_text(entry.worker_id, 64)[:8] or "?")[:20]
    event = (_redacted_display_text(entry.event, 64) or "")[:24].ljust(24)
    message = _redacted_display_text(entry.message)
    parts = [f"{timestamp}  {level}  {role}/{name:<20}  {event}  {message}".rstrip()]
    if entry.job_id:
        parts.append(f"job={_redacted_display_text(entry.job_id, 64)[:8]}")
    if entry.source_path:
        source_path = _redacted_display_text(entry.source_path, 4096)
        parts.append(f"src={_redacted_display_text(Path(source_path).name)}")
    worker_timestamp = getattr(entry, "_worker_ts", "")
    worker_timestamp = _redacted_display_text(worker_timestamp, 80)
    if worker_timestamp and worker_timestamp != timestamp:
        parts.append(f"worker_ts={worker_timestamp}")
    return "  ".join(parts) + "\n"
