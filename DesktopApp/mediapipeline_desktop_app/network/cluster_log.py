from __future__ import annotations

from datetime import datetime
from pathlib import Path

from .protocol import LogEntryRequest


def format_cluster_log_line(entry: LogEntryRequest) -> str:
    """Format one coordinator cluster-log line.

    The leading timestamp is the coordinator receive time. A worker-supplied
    timestamp, when different, is preserved as worker_ts for clock-drift
    investigations.
    """
    timestamp = entry.timestamp or datetime.now().astimezone().isoformat(timespec="seconds")
    level = (entry.level or "INFO").upper().ljust(5)
    role = (entry.role or "worker")[:11]
    name = (entry.worker_name or entry.worker_id[:8] or "?")[:20]
    event = (entry.event or "")[:24].ljust(24)
    parts = [f"{timestamp}  {level}  {role}/{name:<20}  {event}  {entry.message or ''}".rstrip()]
    if entry.job_id:
        parts.append(f"job={entry.job_id[:8]}")
    if entry.source_path:
        parts.append(f"src={Path(entry.source_path).name}")
    worker_timestamp = getattr(entry, "_worker_ts", "")
    if worker_timestamp and worker_timestamp != timestamp:
        parts.append(f"worker_ts={worker_timestamp}")
    return "  ".join(parts) + "\n"
