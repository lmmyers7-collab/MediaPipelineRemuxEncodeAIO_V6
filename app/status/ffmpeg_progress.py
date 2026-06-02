from __future__ import annotations

from datetime import datetime
import re
from typing import Any, Mapping

FFMPEG_PROGRESS_SCHEMA_VERSION = "desktop_ffmpeg_progress.v1"

_FFMPEG_KV_RE = re.compile(
    r"\b(?P<key>frame|fps|time|out_time_us|out_time_ms|out_time|bitrate|speed)\s*=\s*(?P<value>.*?)(?=\s+[A-Za-z_][A-Za-z0-9_]*\s*=|$)",
    re.IGNORECASE,
)
_LOG_TIMESTAMP_RE = re.compile(
    r"^(?P<timestamp>\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})?)\b"
)


def _text_from_mapping(mapping: Mapping[str, Any], *keys: str) -> str:
    for key in keys:
        value = mapping.get(key)
        if value not in (None, ""):
            return str(value).strip()
    return ""


def _joined_values(mapping: Mapping[str, Any], *keys: str) -> str:
    return " ".join(str(mapping.get(key) or "").strip() for key in keys if mapping.get(key) not in (None, ""))


def _bounded_text(value: object, *, max_chars: int = 280) -> str:
    text = str(value or "").strip()
    if len(text) <= max_chars:
        return text
    return f"{text[: max_chars - 3]}..."


def _coerce_int(value: str) -> int | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return int(float(text))
    except ValueError:
        return None


def _coerce_float(value: str) -> float | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def _speed_multiplier(value: str) -> float | None:
    text = str(value or "").strip().lower().removesuffix("x")
    return _coerce_float(text)


def _timestamp_from_line(line: str) -> str:
    match = _LOG_TIMESTAMP_RE.search(line)
    return str(match.group("timestamp")).strip() if match else ""


def _normalize_time_field(fields: Mapping[str, str]) -> str:
    text_time = str(fields.get("time") or fields.get("out_time") or "").strip()
    if text_time:
        return text_time
    for key in ("out_time_us", "out_time_ms"):
        raw = str(fields.get(key) or "").strip()
        if not raw:
            continue
        try:
            seconds = int(raw) / 1_000_000.0
        except ValueError:
            continue
        whole_seconds = int(seconds)
        microseconds = int(round((seconds - whole_seconds) * 1_000_000))
        hours, remainder = divmod(whole_seconds, 3600)
        minutes, secs = divmod(remainder, 60)
        return f"{hours:02d}:{minutes:02d}:{secs:02d}.{microseconds:06d}"
    return ""


def _ffmpeg_fields_from_log_tail(log_tail: str, *, max_lines: int = 160) -> tuple[dict[str, str], str, str]:
    fields: dict[str, str] = {}
    latest_line = ""
    latest_timestamp = ""
    lines = str(log_tail or "").splitlines()[-max_lines:]
    for raw_line in lines:
        line = raw_line.strip()
        if not line:
            continue
        pairs = list(_FFMPEG_KV_RE.finditer(line))
        if not pairs:
            continue
        latest_line = _bounded_text(line)
        timestamp = _timestamp_from_line(line)
        if timestamp:
            latest_timestamp = timestamp
        for pair in pairs:
            key = pair.group("key").strip().lower()
            value = pair.group("value").strip()
            if not value:
                continue
            if key == "out_time":
                key = "time"
            fields[key] = value
    return fields, latest_line, latest_timestamp


def _progress_active(progress: Mapping[str, Any]) -> bool:
    status = _text_from_mapping(progress, "Status", "status").casefold()
    stage = _text_from_mapping(progress, "CurrentStage", "current_stage").casefold()
    text = f"{status} {stage}".strip()
    if not text:
        return False
    if any(token in text for token in ("idle", "sleeping", "stopped", "completed")):
        return False
    return any(token in text for token in ("processing", "running", "active", "publishing", "copying", "encoding", "remuxing", "probing", "retry"))


def _ffmpeg_relevant(progress: Mapping[str, Any], worker_rows: list[Mapping[str, Any]], log_tail: str) -> bool:
    evidence = " ".join(
        [
            _joined_values(progress, "CurrentStage", "Status", "CurrentRoute", "RouteReason"),
            " ".join(_joined_values(row, "stage", "job_kind", "mode") for row in worker_rows),
            str(log_tail or "")[-4000:],
        ]
    ).casefold()
    return any(
        token in evidence
        for token in (
            "ffmpeg",
            "ffprobe",
            "mkvmerge",
            "encode",
            "encoding",
            "remux",
            "remuxing",
            "nvenc",
            "hevc",
            "h264",
            "x264",
            "x265",
        )
    )


def _worker_rows(worker_progress: Mapping[str, Any] | None) -> list[Mapping[str, Any]]:
    rows = worker_progress.get("rows") if isinstance(worker_progress, Mapping) else []
    if not isinstance(rows, list):
        return []
    return [row for row in rows if isinstance(row, Mapping)]


def _first_worker_value(worker_rows: list[Mapping[str, Any]], *keys: str) -> str:
    for row in worker_rows:
        value = _text_from_mapping(row, *keys)
        if value:
            return value
    return ""


def _job_id(progress: Mapping[str, Any], worker_rows: list[Mapping[str, Any]]) -> str:
    return (
        _first_worker_value(worker_rows, "job_id", "record_file")
        or _text_from_mapping(progress, "RunId", "SessionId", "SessionStartedAt")
        or ("pipeline_progress" if _progress_active(progress) else "")
    )


def _updated_at(progress: Mapping[str, Any], worker_rows: list[Mapping[str, Any]], latest_timestamp: str) -> str:
    return (
        latest_timestamp
        or _text_from_mapping(progress, "LastUpdate", "UpdatedAt", "updated_at")
        or _first_worker_value(worker_rows, "updated_at", "last_update", "launched_at")
    )


def _active_worker_running(worker_rows: list[Mapping[str, Any]]) -> bool:
    return any(str(row.get("status_state") or row.get("status") or "").casefold() in {"running", "active"} for row in worker_rows)


def _ffmpeg_progress_row(
    progress: Mapping[str, Any],
    worker_rows: list[Mapping[str, Any]],
    fields: Mapping[str, str],
    latest_line: str,
    latest_timestamp: str,
    *,
    parse_error: str = "",
) -> dict[str, Any]:
    speed = str(fields.get("speed") or "").strip()
    return {
        "job_id": _job_id(progress, worker_rows),
        "stage": _text_from_mapping(progress, "CurrentStage", "Status") or _first_worker_value(worker_rows, "stage"),
        "source": _text_from_mapping(progress, "CurrentFilePath", "CurrentFileDisplay", "CurrentFile") or _first_worker_value(worker_rows, "source"),
        "frame": _coerce_int(str(fields.get("frame") or "")),
        "fps": _coerce_float(str(fields.get("fps") or "")),
        "time": _normalize_time_field(fields),
        "speed": speed,
        "speed_multiplier": _speed_multiplier(speed),
        "bitrate": str(fields.get("bitrate") or "").strip(),
        "progress_source": "bounded pipeline log tail" if fields else "pipeline_progress.json + bounded pipeline log tail",
        "updated_at": _updated_at(progress, worker_rows, latest_timestamp),
        "last_log_line": latest_line,
        "parse_error": parse_error,
    }


def _latest_summary(row: Mapping[str, Any]) -> str:
    pieces = [
        f"job={row.get('job_id')}" if row.get("job_id") else "",
        f"frame={row.get('frame')}" if row.get("frame") is not None else "",
        f"fps={row.get('fps')}" if row.get("fps") is not None else "",
        f"time={row.get('time')}" if row.get("time") else "",
        f"speed={row.get('speed')}" if row.get("speed") else "",
        f"bitrate={row.get('bitrate')}" if row.get("bitrate") else "",
    ]
    return "; ".join(piece for piece in pieces if piece) or "No FFmpeg key/value fields parsed."


def ffmpeg_progress_payload(
    progress: Mapping[str, Any] | None,
    log_tail: str,
    *,
    worker_progress: Mapping[str, Any] | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Build read-only FFmpeg progress proof from existing progress/log evidence."""
    _ = now
    progress_mapping = progress if isinstance(progress, Mapping) else {}
    rows_from_workers = _worker_rows(worker_progress)
    fields, latest_line, latest_timestamp = _ffmpeg_fields_from_log_tail(log_tail)
    rows: list[dict[str, Any]] = []
    if fields:
        rows.append(_ffmpeg_progress_row(progress_mapping, rows_from_workers, fields, latest_line, latest_timestamp))
    elif (_progress_active(progress_mapping) or _active_worker_running(rows_from_workers)) and _ffmpeg_relevant(progress_mapping, rows_from_workers, log_tail):
        rows.append(
            _ffmpeg_progress_row(
                progress_mapping,
                rows_from_workers,
                {},
                "",
                latest_timestamp,
                parse_error="No FFmpeg key/value progress fields were found in the bounded log tail.",
            )
        )

    parsed_count = sum(1 for row in rows if not row.get("parse_error"))
    parse_error_count = sum(1 for row in rows if row.get("parse_error"))
    status = "loaded" if parsed_count else "unavailable" if parse_error_count else "idle"
    summary_lines = [
        f"FFmpeg progress proof: {status}",
        f"Rows: {len(rows)}; parsed={parsed_count}; parse_errors={parse_error_count}.",
    ]
    if rows:
        summary_lines.append(f"Latest: {_latest_summary(rows[0])}")
    else:
        summary_lines.append("No FFmpeg key/value progress rows are available from current runtime evidence.")
    summary_lines.extend(
        [
            "Data sources: pipeline_progress.json, worker progress, and bounded pipeline log tail.",
            "Mutation guardrail: FFmpeg progress proof is read-only telemetry; the WebView does not control processes, queue state, or media files.",
        ]
    )
    return {
        "schema_version": FFMPEG_PROGRESS_SCHEMA_VERSION,
        "mode": "ffmpeg_progress_proof",
        "status": status,
        "row_count": len(rows),
        "parsed_count": parsed_count,
        "parse_error_count": parse_error_count,
        "rows": rows,
        "summary_lines": summary_lines,
        "read_only": True,
    }


__all__ = [
    "FFMPEG_PROGRESS_SCHEMA_VERSION",
    "ffmpeg_progress_payload",
]
