from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from collections.abc import Callable

from mediapipeline.core.kernel.contracts import ContractError, QueuePlanSnapshot
from mediapipeline.core.paths.contracts import ResolvedPaths
from mediapipeline.core.queue.contracts import QueueRecord

ProgressDateParser = Callable[[str], datetime | None]

_PHASE_LABELS = {
    "movie": "MOVIE",
    "tv": "TV",
    "priority": "PRIORITY",
    "priority_movie": "PRIORITY",
    "priority_tv": "PRIORITY",
    "low": "LOW",
    "hold": "HOLD",
}


def queue_snapshot_path(resolved: ResolvedPaths) -> Path | None:
    return resolved.queue_snapshot_path


def queue_snapshot_write_path(resolved: ResolvedPaths) -> Path | None:
    if resolved.state_root:
        return resolved.state_root / "Progress" / "queue_snapshot.json"
    return resolved.queue_snapshot_path


def read_queue_snapshot(path: Path) -> dict | None:
    try:
        text = path.read_text(encoding="utf-8-sig")
    except (OSError, UnicodeDecodeError):
        return None
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return None
    if not isinstance(data, dict):
        return None
    try:
        QueuePlanSnapshot.from_mapping(data)
    except ContractError:
        return None
    return data


def queue_snapshot_is_current_for_request(
    path: Path,
    snapshot: dict,
    started_at: float,
    *,
    parse_progress_datetime: ProgressDateParser,
) -> bool:
    try:
        if path.stat().st_mtime + 0.25 < started_at:
            return False
    except OSError:
        return False
    produced_raw = str(snapshot.get("produced_at", "") or "").strip()
    if not produced_raw:
        return False
    parsed = parse_progress_datetime(produced_raw)
    if parsed is None:
        return False
    produced_ts = parsed.timestamp()
    return produced_ts + 1.0 >= started_at


def queue_dry_run_tail(stdout: str | None, stderr: str | None, *, max_lines: int) -> str:
    text = (stderr or stdout or "").strip()
    if not text:
        return "no output"
    return " | ".join(text.splitlines()[-max_lines:])


def queue_record_from_snapshot_row(row: dict) -> QueueRecord:
    source_path = Path(str(row.get("source_path") or ""))
    source_root = Path(str(row.get("root_path") or ""))
    media_kind = str(row.get("media_kind") or "").lower()
    media_type = "TV" if media_kind == "tv" else "Movie"
    phase_raw = str(row.get("phase") or "").lower()
    phase_label = _PHASE_LABELS.get(phase_raw)
    if phase_label is None:
        phase_label = phase_raw.replace("_", " ").upper() if phase_raw else ("TV" if media_kind == "tv" else "MOVIE")
    last_write = 0.0
    iso = row.get("last_write_utc")
    if isinstance(iso, str) and iso:
        try:
            last_write = datetime.fromisoformat(iso.replace("Z", "+00:00")).timestamp()
        except ValueError:
            last_write = 0.0
    display_name = str(row.get("display_name") or source_path.stem)
    record = QueueRecord(
        source_path=source_path,
        source_root=source_root,
        media_type=media_type,
        is_priority=bool(row.get("is_priority", False)),
        priority_reasons=list(row.get("priority_reasons") or []),
        priority_rank=float(row.get("priority_rank") or 0.0),
        sort_name=display_name,
        display_name=display_name,
        relative_path=str(row.get("relative_path") or ""),
        show_folder=str(row.get("show_sort_key") or ""),
        season_folder=str(row.get("season_sort_key") or ""),
        season_number=int(row.get("season_number") or 0),
        episode_number=int(row.get("episode_number") or 0),
        source_mtime=last_write,
        size_gb=float(row.get("size_gb") or 0.0),
        route_name=str(row.get("route") or ""),
        route_reason=str(row.get("route_reason") or ""),
        matched_show_override="",
        queue_index=int(row.get("queue_index") or 0),
        queue_total=int(row.get("queue_total") or 0),
        phase=phase_label,
        global_order=int(row.get("global_order") or 0),
        manifest_priority_level=str(row.get("manifest_priority_level") or "normal").lower(),
    )
    record.library_id = str(row.get("library_id") or "").strip()
    return record
