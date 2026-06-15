"""Read-only validation-state contract for completed output rows."""

from __future__ import annotations

from pathlib import Path
from typing import Any

VALIDATION_STATE_SCHEMA_VERSION = "desktop_validation_state.v1"


def _text(value: Any) -> str:
    return str(value or "").strip()


def _row_text(row: dict[str, Any], *keys: str) -> str:
    for key in keys:
        value = _text(row.get(key))
        if value:
            return value
    return ""


def _row_bool_or_none(row: dict[str, Any], *keys: str) -> bool | None:
    found = False
    raw: Any = None
    for key in keys:
        if key in row:
            raw = row.get(key)
            found = True
            break
    if not found:
        return None
    if isinstance(raw, bool):
        return raw
    text = _text(raw).casefold()
    if text in {"true", "1", "yes", "ok", "passed", "pass"}:
        return True
    if text in {"false", "0", "no", "failed", "fail", "error"}:
        return False
    return None


def _row_int_or_none(row: dict[str, Any], *keys: str) -> int | None:
    for key in keys:
        if key not in row:
            continue
        raw = row.get(key)
        if raw in (None, ""):
            return None
        try:
            return max(0, int(raw))
        except (TypeError, ValueError):
            return None
    return None


def _path_name(path_text: str) -> str:
    if not path_text:
        return ""
    try:
        return Path(path_text).name
    except Exception:
        return path_text


def _validation_failure_reason(
    *,
    output_path: str,
    exists: bool | None,
    health: str,
    size: int | None,
    probe_ok: bool | None,
    hash_ok: bool | None,
    unavailable_reasons: list[str],
) -> str:
    health_text = health.casefold()
    if not output_path:
        return "Completed row does not report an output path."
    if exists is False:
        return "Completed row points at a missing output."
    if health_text and health_text not in {"ok", "healthy", "present"}:
        return f"Completed output health is {health}."
    if probe_ok is False:
        return "Output probe proof reports a failure."
    if hash_ok is False:
        return "Output hash proof reports a failure."
    if size is None:
        return "Output size is not reported."
    if size <= 0:
        return "Output size is zero bytes."
    if unavailable_reasons:
        return "Output validation proof is incomplete."
    return ""


def validation_state_for_completed_row(row: dict[str, Any]) -> dict[str, object]:
    output_path = _row_text(row, "output_path", "manifest_output_path")
    exists = _row_bool_or_none(row, "output_exists", "exists")
    size = _row_int_or_none(row, "output_size_bytes", "size", "output_size")
    health = _row_text(row, "output_health")
    probe_ok = _row_bool_or_none(row, "validation_probe_ok", "probe_ok", "output_probe_ok", "ffprobe_ok")
    hash_ok = _row_bool_or_none(row, "validation_hash_ok", "hash_ok", "output_hash_ok")
    playback_ok = _row_bool_or_none(row, "playback_ok", "validation_playback_ok")
    explicit_playback_required = _row_bool_or_none(row, "playback_required", "validation_playback_required")

    unavailable_reasons: list[str] = []
    if exists is None:
        unavailable_reasons.append("output existence proof not reported")
    if size is None:
        unavailable_reasons.append("output size proof not reported")
    if probe_ok is None:
        unavailable_reasons.append("ffprobe output proof not reported")
    if hash_ok is None:
        unavailable_reasons.append("output hash proof not reported")
    if playback_ok is None and explicit_playback_required is None:
        unavailable_reasons.append("manual playback acceptance not reported")

    output_exists = bool(exists) if exists is not None else False
    playback_required = (
        bool(explicit_playback_required)
        if explicit_playback_required is not None
        else output_exists and playback_ok is not True
    )
    failure_reason = _validation_failure_reason(
        output_path=output_path,
        exists=exists,
        health=health,
        size=size,
        probe_ok=probe_ok,
        hash_ok=hash_ok,
        unavailable_reasons=unavailable_reasons,
    )
    health_blocked = bool(health and health.casefold() not in {"ok", "healthy", "present"})
    if not output_path or exists is False or health_blocked or probe_ok is False or hash_ok is False:
        status_state = "blocked"
    elif size is None or size <= 0:
        status_state = "validation-needed"
    elif unavailable_reasons or playback_required:
        status_state = "validation-needed"
    else:
        status_state = "completed"

    if status_state == "blocked":
        safe_next_action = "Open the output folder, Completed Manifest, Run Logs, and Last Stderr before rerun, cleanup, or Sample Validation acceptance."
    elif status_state == "validation-needed":
        safe_next_action = "Treat this as output presence proof only; run or record probe/hash/playback validation before accepting the sample."
    else:
        safe_next_action = "Validation proof is reported as complete; still keep backend-owned publish, rerun, cleanup, and acceptance controls authoritative."

    return {
        "schema_version": VALIDATION_STATE_SCHEMA_VERSION,
        "row_key": _row_text(row, "row_key"),
        "source_path": _row_text(row, "source_path"),
        "output_path": output_path,
        "output_name": _path_name(output_path),
        "exists": exists,
        "size": size,
        "size_text": _row_text(row, "output_size_text"),
        "probe_ok": probe_ok,
        "hash_ok": hash_ok,
        "playback_required": playback_required,
        "validation_status_state": status_state,
        "failure_reason": failure_reason,
        "unavailable_reasons": unavailable_reasons,
        "safe_next_action": safe_next_action,
        "quality_score": row.get("quality_score"),
        "quality_metric": _row_text(row, "quality_metric"),
        "quality_outcome": _row_text(row, "quality_outcome"),
        "read_only": True,
    }


def validation_state_payload(rows: object, *, source: str = "", source_kind: str = "completed") -> dict[str, object]:
    valid_rows = [row for row in rows or [] if isinstance(row, dict)]
    validation_rows = [validation_state_for_completed_row(row) for row in valid_rows]
    blocked_count = sum(1 for row in validation_rows if row.get("validation_status_state") == "blocked")
    validation_needed_count = sum(1 for row in validation_rows if row.get("validation_status_state") == "validation-needed")
    completed_count = sum(1 for row in validation_rows if row.get("validation_status_state") == "completed")
    playback_required_count = sum(1 for row in validation_rows if row.get("playback_required") is True)
    unavailable_count = sum(1 for row in validation_rows if row.get("unavailable_reasons"))
    if blocked_count:
        status_state = "blocked"
    elif validation_needed_count:
        status_state = "validation-needed"
    elif completed_count:
        status_state = "completed"
    else:
        status_state = "idle"
    return {
        "schema_version": VALIDATION_STATE_SCHEMA_VERSION,
        "read_only": True,
        "source": source,
        "source_kind": source_kind,
        "status_state": status_state,
        "row_count": len(validation_rows),
        "blocked_count": blocked_count,
        "validation_needed_count": validation_needed_count,
        "completed_count": completed_count,
        "playback_required_count": playback_required_count,
        "unavailable_count": unavailable_count,
        "rows": validation_rows,
        "operator_guidance": (
            "Validation state is evidence-only. It reports output path/existence/size when available and explicitly marks probe, hash, or playback proof as unavailable until the backend reports it."
        ),
    }


__all__ = [
    "VALIDATION_STATE_SCHEMA_VERSION",
    "validation_state_for_completed_row",
    "validation_state_payload",
]
