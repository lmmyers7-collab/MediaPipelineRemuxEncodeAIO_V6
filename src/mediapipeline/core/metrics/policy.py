"""Read-only pipeline metrics aggregation policy."""

from __future__ import annotations

from collections import Counter
from datetime import datetime, UTC
from typing import Any
from collections.abc import Iterable, Mapping

from mediapipeline.core.completed.policy import completed_record_key, format_bytes_compact
from mediapipeline.core.completed.contracts import CompletedJobRecord


METRICS_SCHEMA_VERSION = "desktop_metrics.v1"
METRICS_ROUTE_MIX_SCHEMA_VERSION = "desktop_metrics_route_mix.v1"
METRICS_STORAGE_SCHEMA_VERSION = "desktop_metrics_storage.v1"
METRICS_PRODUCTION_SCHEMA_VERSION = "desktop_metrics_production.v1"
METRICS_WORKERS_SCHEMA_VERSION = "desktop_metrics_workers.v1"
METRICS_SOURCE_EVIDENCE_SCHEMA_VERSION = "desktop_metrics_source_evidence.v1"
RECENT_METRIC_ROW_LIMIT = 25
TOP_STORAGE_ROW_LIMIT = 10


def utc_now_text() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _int_or_none(value: Any) -> int | None:
    try:
        if value in (None, ""):
            return None
        return int(value)
    except (TypeError, ValueError):
        return None


def _int_value(value: Any) -> int:
    return max(0, _int_or_none(value) or 0)


def _float_value(value: Any) -> float:
    try:
        if value in (None, ""):
            return 0.0
        parsed = float(value)
    except (TypeError, ValueError):
        return 0.0
    return parsed if parsed == parsed else 0.0


def _signed_bytes_text(value: int | None) -> str:
    if value is None:
        return "unknown"
    sign = "+" if value > 0 else "-" if value < 0 else ""
    return f"{sign}{format_bytes_compact(abs(int(value)))}"


def _percent(numerator: int, denominator: int) -> float | None:
    if denominator <= 0:
        return None
    return round((float(numerator) / float(denominator)) * 100.0, 1)


def _text(value: Any) -> str:
    return str(value or "").strip()


def _route_group(route: str) -> str:
    normalized = route.casefold()
    if normalized == "remux":
        return "remux"
    if normalized.startswith("encode"):
        return "encode"
    return "other"


def _completed_date_key(record: CompletedJobRecord) -> str:
    completed_at = record.completed_at
    if completed_at is None:
        return "unknown"
    return completed_at.date().isoformat()


def _completed_at_text(record: CompletedJobRecord) -> str:
    completed_at = record.completed_at
    if completed_at is None:
        return ""
    return completed_at.isoformat(timespec="seconds")


def _counter_mapping(values: Iterable[str]) -> dict[str, int]:
    counter = Counter(value or "unknown" for value in values)
    return dict(sorted(counter.items()))


def _bounded_counter_mapping(values: Iterable[str], *, limit: int = 12) -> dict[str, int]:
    counter = Counter(value or "unknown" for value in values)
    return dict(sorted(counter.most_common(limit), key=lambda item: (-item[1], item[0])))


def _route_reason_group(reason_code: str, reason: str = "") -> tuple[str, str, str]:
    raw = _text(reason_code) or _text(reason) or "unknown"
    normalized = raw.casefold()
    if normalized in {"unknown", "none", "n/a", "na", "null"}:
        return ("unknown", "Unknown decision reason", "warning")
    if any(token in normalized for token in ("subtitle", "srt", "ocr", "caption")):
        return ("subtitle_policy", "Subtitle requirement", "info")
    if any(token in normalized for token in ("audio", "downmix", "track", "channel")):
        return ("audio_policy", "Audio requirement", "info")
    if any(token in normalized for token in ("force", "forced", "folder_policy", "profile_policy", "manual")):
        return ("configured_policy", "Configured route policy", "info")
    if any(token in normalized for token in ("remux_safe", "remux-compatible", "compatible", "passthrough")):
        return ("remux_safe", "Remux-safe media", "info")
    if any(token in normalized for token in ("codec", "encoder", "hevc", "h264", "h.264", "h.265", "video")):
        return ("codec_policy", "Codec or encoder requirement", "info")
    if any(token in normalized for token in ("size", "bitrate", "growth", "storage")):
        return ("size_policy", "Size or bitrate advisory", "info")
    if any(token in normalized for token in ("probe", "ffprobe", "metadata", "missing")):
        return ("metadata_review", "Metadata review", "warning")
    return ("other_policy", raw.replace("_", " ").replace("-", " ").title(), "info")


def _route_reason_groups(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    total = len(rows)
    groups: dict[str, dict[str, Any]] = {}
    for row in rows:
        code = str(row.get("route_reason_code") or "unknown")
        reason = str(row.get("route_reason") or "")
        key, label, severity = _route_reason_group(code, reason)
        bucket = groups.setdefault(
            key,
            {
                "key": key,
                "label": label,
                "severity": severity,
                "count": 0,
                "codes": set(),
            },
        )
        bucket["count"] += 1
        bucket["codes"].add(code or "unknown")
        if severity == "warning":
            bucket["severity"] = "warning"
    result: list[dict[str, Any]] = []
    for bucket in groups.values():
        codes = sorted(str(item) for item in bucket["codes"])
        result.append(
            {
                "key": bucket["key"],
                "label": bucket["label"],
                "severity": bucket["severity"],
                "count": int(bucket["count"]),
                "percent": _percent(int(bucket["count"]), total),
                "codes": codes[:8],
            }
        )
    return sorted(result, key=lambda item: (-int(item["count"]), str(item["label"])))


def _completed_metric_rows(records: Iterable[CompletedJobRecord]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for record in records:
        if not isinstance(record, CompletedJobRecord):
            continue
        source_size = _int_or_none(record.payload.get("source_size"))
        output_size = _int_or_none(record.payload.get("output_size"))
        route = record.route or "unknown"
        measured = bool(source_size and output_size and source_size > 0 and output_size > 0)
        delta_bytes = (output_size - source_size) if measured else None
        storage_saved_bytes = (source_size - output_size) if measured else None
        title = record.lookup_title or record.output_file or record.source_path_text
        rows.append(
            {
                "row_key": completed_record_key(record),
                "completed_date": _completed_date_key(record),
                "completed_at": _completed_at_text(record),
                "title": title,
                "media_type": record.media_type or "unknown",
                "route": route,
                "route_label": record.route_label,
                "route_group": _route_group(route),
                "route_reason": _text(record.payload.get("route_reason")),
                "route_reason_code": _text(record.payload.get("route_reason_code")),
                "encoder": _text(record.payload.get("encode_selected_encoder")),
                "publish_state": record.publish_state,
                "publish_mode": record.publish_mode,
                "source_size_bytes": source_size,
                "source_size_text": format_bytes_compact(source_size or 0),
                "output_size_bytes": output_size,
                "output_size_text": format_bytes_compact(output_size or 0),
                "measurement_available": measured,
                "size_delta_bytes": delta_bytes,
                "size_delta_text": _signed_bytes_text(delta_bytes),
                "storage_saved_bytes": storage_saved_bytes,
                "storage_saved_text": _signed_bytes_text(storage_saved_bytes),
            }
        )
    return rows


def _route_series(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_date: dict[str, dict[str, int]] = {}
    for row in rows:
        date_key = str(row.get("completed_date") or "unknown")
        group = str(row.get("route_group") or "other")
        bucket = by_date.setdefault(date_key, {"date": date_key, "remux": 0, "encode": 0, "other": 0, "total": 0})
        bucket[group if group in {"remux", "encode"} else "other"] += 1
        bucket["total"] += 1
    return [by_date[key] for key in sorted(by_date, key=lambda item: (item == "unknown", item))]


def _route_mix(rows: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(rows)
    route_counts = _counter_mapping(str(row.get("route") or "unknown") for row in rows)
    group_counts = {
        "remux": sum(1 for row in rows if row.get("route_group") == "remux"),
        "encode": sum(1 for row in rows if row.get("route_group") == "encode"),
        "other": sum(1 for row in rows if row.get("route_group") == "other"),
    }
    return {
        "schema_version": METRICS_ROUTE_MIX_SCHEMA_VERSION,
        "total_jobs": total,
        "remux_count": group_counts["remux"],
        "encode_count": group_counts["encode"],
        "other_route_count": group_counts["other"],
        "remux_percent": _percent(group_counts["remux"], total),
        "encode_percent": _percent(group_counts["encode"], total),
        "other_route_percent": _percent(group_counts["other"], total),
        "route_counts": route_counts,
        "route_group_counts": group_counts,
        "route_reason_code_counts": _bounded_counter_mapping(
            str(row.get("route_reason_code") or "unknown") for row in rows
        ),
        "route_reason_counts": _bounded_counter_mapping(str(row.get("route_reason") or "unknown") for row in rows),
        "encoder_counts": _bounded_counter_mapping(str(row.get("encoder") or "unknown") for row in rows),
        "reason_groups": _route_reason_groups(rows),
        "series": _route_series(rows),
    }


def _storage_breakdown(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[str, dict[str, Any]] = {
        "remux": {"route_group": "remux", "count": 0, "measured_count": 0, "output_bytes": 0, "source_bytes": 0, "net_storage_saved_bytes": 0},
        "encode": {"route_group": "encode", "count": 0, "measured_count": 0, "output_bytes": 0, "source_bytes": 0, "net_storage_saved_bytes": 0},
        "other": {"route_group": "other", "count": 0, "measured_count": 0, "output_bytes": 0, "source_bytes": 0, "net_storage_saved_bytes": 0},
    }
    for row in rows:
        group = str(row.get("route_group") or "other")
        bucket = groups[group if group in groups else "other"]
        bucket["count"] += 1
        bucket["output_bytes"] += _int_value(row.get("output_size_bytes"))
        if row.get("measurement_available"):
            bucket["measured_count"] += 1
            bucket["source_bytes"] += _int_value(row.get("source_size_bytes"))
            bucket["net_storage_saved_bytes"] += int(row.get("storage_saved_bytes") or 0)
    result: list[dict[str, Any]] = []
    for bucket in groups.values():
        source_bytes = int(bucket["source_bytes"])
        saved_bytes = int(bucket["net_storage_saved_bytes"])
        result.append(
            {
                **bucket,
                "output_size_text": format_bytes_compact(int(bucket["output_bytes"])),
                "source_size_text": format_bytes_compact(source_bytes),
                "net_storage_saved_text": _signed_bytes_text(saved_bytes),
                "net_storage_saved_percent": _percent(saved_bytes, source_bytes),
                "excluded_count": max(0, int(bucket["count"]) - int(bucket["measured_count"])),
            }
        )
    return result


def _storage(rows: list[dict[str, Any]]) -> dict[str, Any]:
    measured = [row for row in rows if row.get("measurement_available")]
    total_output_bytes = sum(_int_value(row.get("output_size_bytes")) for row in rows)
    measured_output_bytes = sum(_int_value(row.get("output_size_bytes")) for row in measured)
    measured_source_bytes = sum(_int_value(row.get("source_size_bytes")) for row in measured)
    gross_saved_bytes = sum(
        max(0, int(row.get("storage_saved_bytes") or 0))
        for row in measured
    )
    gross_growth_bytes = sum(
        max(0, -int(row.get("storage_saved_bytes") or 0))
        for row in measured
    )
    net_saved_bytes = measured_source_bytes - measured_output_bytes
    top_savings = sorted(
        (row for row in measured if int(row.get("storage_saved_bytes") or 0) > 0),
        key=lambda item: int(item.get("storage_saved_bytes") or 0),
        reverse=True,
    )[:TOP_STORAGE_ROW_LIMIT]
    top_growth = sorted(
        (row for row in measured if int(row.get("storage_saved_bytes") or 0) < 0),
        key=lambda item: abs(int(item.get("storage_saved_bytes") or 0)),
        reverse=True,
    )[:TOP_STORAGE_ROW_LIMIT]
    return {
        "schema_version": METRICS_STORAGE_SCHEMA_VERSION,
        "total_data_produced_bytes": total_output_bytes,
        "total_data_produced_text": format_bytes_compact(total_output_bytes),
        "measured_source_bytes": measured_source_bytes,
        "measured_source_text": format_bytes_compact(measured_source_bytes),
        "measured_output_bytes": measured_output_bytes,
        "measured_output_text": format_bytes_compact(measured_output_bytes),
        "gross_storage_saved_bytes": gross_saved_bytes,
        "gross_storage_saved_text": format_bytes_compact(gross_saved_bytes),
        "gross_storage_growth_bytes": gross_growth_bytes,
        "gross_storage_growth_text": format_bytes_compact(gross_growth_bytes),
        "output_growth_bytes": gross_growth_bytes,
        "output_growth_text": _signed_bytes_text(gross_growth_bytes),
        "net_storage_saved_bytes": net_saved_bytes,
        "net_storage_saved_text": _signed_bytes_text(net_saved_bytes),
        "net_storage_saved_percent": _percent(net_saved_bytes, measured_source_bytes),
        "net_storage_delta_bytes": measured_output_bytes - measured_source_bytes,
        "net_storage_delta_text": _signed_bytes_text(measured_output_bytes - measured_source_bytes),
        "output_written_bytes": total_output_bytes,
        "output_written_text": format_bytes_compact(total_output_bytes),
        "measurement_row_count": len(measured),
        "excluded_row_count": max(0, len(rows) - len(measured)),
        "breakdown": _storage_breakdown(rows),
        "top_savings": top_savings,
        "top_growth": top_growth,
    }


def _daily_completion_series(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_date: dict[str, dict[str, Any]] = {}
    for row in rows:
        date_key = str(row.get("completed_date") or "unknown")
        group = str(row.get("route_group") or "other")
        bucket = by_date.setdefault(
            date_key,
            {
                "date": date_key,
                "completed_count": 0,
                "output_bytes": 0,
                "output_text": "0 B",
                "remux": 0,
                "encode": 0,
                "other": 0,
            },
        )
        bucket["completed_count"] += 1
        bucket["output_bytes"] += _int_value(row.get("output_size_bytes"))
        bucket[group if group in {"remux", "encode"} else "other"] += 1
    result = [by_date[key] for key in sorted(by_date, key=lambda item: (item == "unknown", item))]
    for bucket in result:
        bucket["output_text"] = format_bytes_compact(_int_value(bucket.get("output_bytes")))
    return result


def _production_throughput(rows: list[dict[str, Any]]) -> dict[str, Any]:
    daily_series = _daily_completion_series(rows)
    dated_series = [item for item in daily_series if item.get("date") != "unknown"]
    recent_series = (dated_series or daily_series)[-7:]
    recent_completed_count = sum(_int_value(item.get("completed_count")) for item in recent_series)
    recent_output_bytes = sum(_int_value(item.get("output_bytes")) for item in recent_series)
    recent_day_count = len(recent_series)
    completed_at_values = [str(row.get("completed_at") or "") for row in rows if row.get("completed_at")]
    latest_completed_at = max(
        completed_at_values,
        key=datetime.fromisoformat,
        default="",
    )
    recent_output_per_day_bytes = int(recent_output_bytes / recent_day_count) if recent_day_count else 0
    return {
        "last_completed_at": latest_completed_at,
        "recent_day_count": recent_day_count,
        "recent_completed_count": recent_completed_count,
        "recent_output_bytes": recent_output_bytes,
        "recent_output_text": format_bytes_compact(recent_output_bytes),
        "recent_jobs_per_day": round(recent_completed_count / recent_day_count, 1) if recent_day_count else 0.0,
        "recent_output_per_day_bytes": recent_output_per_day_bytes,
        "recent_output_per_day_text": format_bytes_compact(recent_output_per_day_bytes),
        "recent_daily_completion_series": recent_series,
    }


def _production(
    rows: list[dict[str, Any]],
    *,
    pending_publish: Mapping[str, Any],
    final_library: Mapping[str, Any],
) -> dict[str, Any]:
    completed_output_bytes = sum(_int_value(row.get("output_size_bytes")) for row in rows)
    pending_bytes = _int_value(pending_publish.get("total_bytes"))
    final_counts = final_library.get("counts") if isinstance(final_library.get("counts"), Mapping) else {}
    return {
        "schema_version": METRICS_PRODUCTION_SCHEMA_VERSION,
        "completed_count": len(rows),
        "completed_output_bytes": completed_output_bytes,
        "completed_output_text": format_bytes_compact(completed_output_bytes),
        "pending_publish_count": _int_value(pending_publish.get("count")),
        "pending_publish_payload_count": _int_value(pending_publish.get("payload_count")),
        "pending_publish_bytes": pending_bytes,
        "pending_publish_text": _text(pending_publish.get("total_size_text")) or format_bytes_compact(pending_bytes),
        "known_output_plus_pending_bytes": completed_output_bytes + pending_bytes,
        "known_output_plus_pending_text": format_bytes_compact(completed_output_bytes + pending_bytes),
        "publish_state_counts": _counter_mapping(str(row.get("publish_state") or "unknown") for row in rows),
        "media_type_counts": _counter_mapping(str(row.get("media_type") or "unknown") for row in rows),
        "completion_series": _route_series(rows),
        "throughput": _production_throughput(rows),
        "pending_publish": {
            "exists": bool(pending_publish.get("exists")),
            "state_counts": dict(pending_publish.get("state_counts") or {}),
            "route_counts": dict(pending_publish.get("route_counts") or {}),
            "issue_count": _int_value(pending_publish.get("issue_count")),
            "ready_count": _int_value(pending_publish.get("ready_count")),
            "missing_local_count": _int_value(pending_publish.get("missing_local_count")),
        },
        "final_library": {
            "enabled": bool(final_library.get("enabled")),
            "pause_state": _text(final_library.get("pause_state")) or "unknown",
            "counts": dict(final_counts),
            "warnings": [str(item) for item in final_library.get("warnings") or []],
        },
        "recent_jobs": rows[:RECENT_METRIC_ROW_LIMIT],
    }


def _worker_rows(network_workers: Mapping[str, Any]) -> list[dict[str, Any]]:
    return [dict(row) for row in network_workers.get("rows") or [] if isinstance(row, Mapping)]


def _state_file_counts(network_workers: Mapping[str, Any]) -> dict[str, int]:
    state_files = [item for item in network_workers.get("state_files") or [] if isinstance(item, Mapping)]
    return _counter_mapping(str(item.get("status") or "unknown") for item in state_files)


def _worker_problem_row_count(rows: list[dict[str, Any]]) -> int:
    problem_tokens = ("fail", "error", "stale", "offline", "blocked", "missing")
    return sum(
        1
        for row in rows
        if any(token in str(row.get("status") or "").casefold() for token in problem_tokens)
    )


def _worker_posture(worker_summary: Mapping[str, Any]) -> dict[str, Any]:
    warnings = [str(item) for item in worker_summary.get("warnings") or [] if str(item).strip()]
    rows = [dict(row) for row in worker_summary.get("rows") or [] if isinstance(row, Mapping)]
    row_problem_count = _worker_problem_row_count(rows)
    failed_session_count = _int_value(worker_summary.get("session_failed"))
    warning_count = len(warnings)
    problem_count = failed_session_count + row_problem_count
    role = _text(worker_summary.get("role")) or "standalone"
    if problem_count:
        posture = "review"
        severity = "warning"
        detail = "Worker sessions or persisted worker rows need review."
    elif warning_count:
        posture = "warning"
        severity = "warning"
        detail = "Worker warnings are present in backend runtime state."
    elif role == "standalone":
        posture = "standalone"
        severity = "info"
        detail = "Standalone mode is active; distributed worker rows are optional."
    elif _int_value(worker_summary.get("active_count")):
        posture = "active"
        severity = "info"
        detail = "Workers are active with no failed sessions in the loaded summary."
    else:
        posture = "idle"
        severity = "info"
        detail = "Workers are idle with no failed sessions in the loaded summary."
    return {
        "posture": posture,
        "severity": severity,
        "role": role,
        "worker_count": _int_value(worker_summary.get("worker_count")),
        "active_count": _int_value(worker_summary.get("active_count")),
        "idle_count": _int_value(worker_summary.get("idle_count")),
        "problem_count": problem_count,
        "warning_count": warning_count,
        "failed_session_count": failed_session_count,
        "handoff_target": "network",
        "handoff_label": "Open Workers",
        "detail": detail,
    }


def _workers(network_workers: Mapping[str, Any]) -> dict[str, Any]:
    rows = _worker_rows(network_workers)
    speed_values = [_float_value(row.get("avg_speed_gbh")) for row in rows if _float_value(row.get("avg_speed_gbh")) > 0]
    worker_encoded_gb = round(sum(_float_value(row.get("total_gb_encoded")) for row in rows), 2)
    progress = network_workers.get("worker_progress") if isinstance(network_workers.get("worker_progress"), Mapping) else {}
    summary = {
        "schema_version": METRICS_WORKERS_SCHEMA_VERSION,
        "role": _text(network_workers.get("role")) or "standalone",
        "source": _text(network_workers.get("source")) or "runtime_state_files",
        "worker_count": _int_value(network_workers.get("total_count")) or len(rows),
        "active_count": _int_value(network_workers.get("active_count")),
        "idle_count": _int_value(network_workers.get("idle_count")),
        "session_completed": _int_value(network_workers.get("session_completed")),
        "session_failed": _int_value(network_workers.get("session_failed")),
        "worker_completed_files_total": sum(_int_value(row.get("files_completed")) for row in rows),
        "worker_encoded_gb_total": worker_encoded_gb,
        "average_speed_gbh": round(sum(speed_values) / len(speed_values), 2) if speed_values else 0.0,
        "progress_status": _text(progress.get("status")) or "unknown",
        "progress_bar_count": _int_value(progress.get("bar_count")),
        "state_file_status_counts": _state_file_counts(network_workers),
        "coordinator": {
            "inflight_path": _text(network_workers.get("coordinator_inflight_path")),
            "cluster_log_path": _text(network_workers.get("cluster_log_path")),
            "worker_state_path": _text(network_workers.get("worker_state_path")),
            "active_claims": _int_value(network_workers.get("active_count")),
            "idle_workers": _int_value(network_workers.get("idle_count")),
            "session_completed": _int_value(network_workers.get("session_completed")),
            "session_failed": _int_value(network_workers.get("session_failed")),
            "claim_count": None,
            "reclaim_count": None,
            "unavailable_counts": ["claim_count", "reclaim_count"],
        },
        "rows": rows[:RECENT_METRIC_ROW_LIMIT],
        "warnings": [str(item) for item in network_workers.get("warnings") or []],
    }
    summary["posture"] = _worker_posture(summary)
    return summary


def _source_evidence(
    *,
    completed_source: str,
    rows: list[dict[str, Any]],
    pending_publish: Mapping[str, Any],
    network_workers: Mapping[str, Any],
    final_library: Mapping[str, Any],
    source_backfill: Mapping[str, Any],
) -> dict[str, Any]:
    return {
        "schema_version": METRICS_SOURCE_EVIDENCE_SCHEMA_VERSION,
        "evidence_authority": "backend",
        "completed_manifest": {
            "source": completed_source,
            "record_count": len(rows),
            "proof_mode": "summary",
            "authority": "completed_jobs.jsonl",
        },
        "pending_publish": {
            "source": _text(pending_publish.get("pending_root")),
            "row_count": _int_value(pending_publish.get("count")),
            "payload_count": _int_value(pending_publish.get("payload_count")),
            "schema_version": _text(pending_publish.get("schema_version")),
        },
        "workers": {
            "source": _text(network_workers.get("source")),
            "row_count": len(_worker_rows(network_workers)),
            "schema_version": _text(network_workers.get("schema_version")),
        },
        "final_library": {
            "enabled": bool(final_library.get("enabled")),
            "schema_version": _text(final_library.get("schema_version")),
            "count_limit": 500,
        },
        "metrics_backfill": {
            "available": bool(source_backfill.get("available")),
            "schema_version": _text(source_backfill.get("schema_version")),
            "registry_path": _text(source_backfill.get("registry_path")),
            "cache_path": _text(source_backfill.get("cache_path")),
            "source_count": _int_value(source_backfill.get("source_count")),
            "enabled_source_count": _int_value(source_backfill.get("enabled_source_count")),
            "cache_record_count": _int_value(source_backfill.get("cache_record_count")),
            "enabled_cache_record_count": _int_value(source_backfill.get("enabled_cache_record_count")),
        },
    }


def _coverage(
    rows: list[dict[str, Any]],
    *,
    storage: Mapping[str, Any],
    source_backfill: Mapping[str, Any],
) -> dict[str, Any]:
    last_backfill = source_backfill.get("last_backfill") if isinstance(source_backfill.get("last_backfill"), Mapping) else {}
    completed_rows = len(rows)
    measured_rows = _int_value(storage.get("measurement_row_count"))
    excluded_rows = _int_value(storage.get("excluded_row_count"))
    source_count = _int_value(source_backfill.get("source_count"))
    enabled_source_count = _int_value(source_backfill.get("enabled_source_count"))
    cached_backfill_count = _int_value(
        source_backfill.get("enabled_cache_record_count") or source_backfill.get("cache_record_count")
    )
    return {
        "completed_rows": completed_rows,
        "measured_rows": measured_rows,
        "excluded_rows": excluded_rows,
        "measurement_percent": _percent(measured_rows, completed_rows),
        "source_count": source_count,
        "enabled_source_count": enabled_source_count,
        "cached_backfill_count": cached_backfill_count,
        "last_scan_status": _text(last_backfill.get("status")) or "not run",
        "last_backfill_status": _text(last_backfill.get("status")) or "not run",
        "last_backfill_loaded_count": _int_value(last_backfill.get("loaded_count")),
        "last_backfill_sidecar_count": _int_value(last_backfill.get("sidecar_count")),
        "last_backfill_error_count": _int_value(last_backfill.get("error_count")),
    }


def _attention_item(
    *,
    item_id: str,
    severity: str,
    label: str,
    value: str,
    detail: str,
    target_subtab: str,
) -> dict[str, str]:
    return {
        "id": item_id,
        "severity": severity,
        "label": label,
        "value": value,
        "detail": detail,
        "target_subtab": target_subtab,
    }


def _attention_items(
    *,
    coverage: Mapping[str, Any],
    route_mix: Mapping[str, Any],
    storage: Mapping[str, Any],
    production: Mapping[str, Any],
    workers: Mapping[str, Any],
    warnings: Iterable[str],
) -> list[dict[str, str]]:
    items: list[dict[str, str]] = []
    completed_rows = _int_value(coverage.get("completed_rows"))
    excluded_rows = _int_value(coverage.get("excluded_rows"))
    if excluded_rows:
        items.append(
            _attention_item(
                item_id="measurement-coverage",
                severity="warning",
                label="Missing size measurements",
                value=f"{excluded_rows} excluded",
                detail=f"{_int_value(coverage.get('measured_rows'))}/{completed_rows} completed rows have source and output sizes.",
                target_subtab="storage",
            )
        )
    unknown_reason = next(
        (item for item in route_mix.get("reason_groups") or [] if item.get("key") == "unknown"),
        None,
    )
    if unknown_reason and _int_value(unknown_reason.get("count")):
        items.append(
            _attention_item(
                item_id="unknown-route-reasons",
                severity="warning",
                label="Unknown route reasons",
                value=f"{_int_value(unknown_reason.get('count'))} job(s)",
                detail="Some completed rows do not explain why they remuxed or encoded.",
                target_subtab="routes",
            )
        )
    top_growth = storage.get("top_growth") if isinstance(storage.get("top_growth"), list) else []
    if top_growth:
        first = top_growth[0] if isinstance(top_growth[0], Mapping) else {}
        items.append(
            _attention_item(
                item_id="output-growth",
                severity="warning",
                label="Output growth outlier",
                value=str(first.get("size_delta_text") or storage.get("output_growth_text") or "growth"),
                detail=str(first.get("title") or first.get("row_key") or "Largest measured growth row needs review."),
                target_subtab="storage",
            )
        )
    pending_count = _int_value(production.get("pending_publish_count"))
    if pending_count:
        items.append(
            _attention_item(
                item_id="pending-publish-backlog",
                severity="warning",
                label="Pending publish backlog",
                value=f"{pending_count} row(s)",
                detail=f"Parked output totals {production.get('pending_publish_text') or '0 B'}.",
                target_subtab="production",
            )
        )
    final_library = production.get("final_library") if isinstance(production.get("final_library"), Mapping) else {}
    final_warnings = [str(item) for item in final_library.get("warnings") or [] if str(item).strip()]
    if final_warnings:
        items.append(
            _attention_item(
                item_id="final-library-warnings",
                severity="warning",
                label="Final-library warnings",
                value=f"{len(final_warnings)} warning(s)",
                detail=final_warnings[0],
                target_subtab="production",
            )
        )
    posture = workers.get("posture") if isinstance(workers.get("posture"), Mapping) else {}
    if _int_value(posture.get("problem_count")) or _int_value(posture.get("failed_session_count")):
        items.append(
            _attention_item(
                item_id="worker-failures",
                severity="warning",
                label="Worker failures",
                value=f"{_int_value(posture.get('failed_session_count'))} failed session(s)",
                detail=str(posture.get("detail") or "Open Workers for runtime detail."),
                target_subtab="workers",
            )
        )
    elif _int_value(posture.get("warning_count")):
        items.append(
            _attention_item(
                item_id="worker-warnings",
                severity="warning",
                label="Worker warnings",
                value=f"{_int_value(posture.get('warning_count'))} warning(s)",
                detail=str(posture.get("detail") or "Open Workers for runtime detail."),
                target_subtab="workers",
            )
        )
    enabled_sources = _int_value(coverage.get("enabled_source_count"))
    if enabled_sources and not _int_value(coverage.get("cached_backfill_count")):
        items.append(
            _attention_item(
                item_id="source-backfill-empty",
                severity="info",
                label="Backfill cache empty",
                value="0 cached",
                detail="Metrics source roots are enabled but no sidecar backfill rows are cached.",
                target_subtab="overview",
            )
        )
    for index, warning in enumerate(str(item) for item in warnings if str(item).strip()):
        items.append(
            _attention_item(
                item_id=f"metrics-warning-{index + 1}",
                severity="warning",
                label="Metrics warning",
                value="Review",
                detail=warning,
                target_subtab="overview",
            )
        )
    return items


def build_metrics_payload(
    records: Iterable[CompletedJobRecord],
    *,
    pending_publish: Mapping[str, Any] | None = None,
    network_workers: Mapping[str, Any] | None = None,
    final_library: Mapping[str, Any] | None = None,
    source_backfill: Mapping[str, Any] | None = None,
    completed_source: str = "",
    warnings: Iterable[str] = (),
    generated_at: str | None = None,
) -> dict[str, Any]:
    pending_payload = dict(pending_publish or {})
    worker_payload = dict(network_workers or {})
    final_library_payload = dict(final_library or {})
    source_backfill_payload = dict(source_backfill or {})
    rows = _completed_metric_rows(records)
    route_mix = _route_mix(rows)
    storage = _storage(rows)
    production = _production(rows, pending_publish=pending_payload, final_library=final_library_payload)
    storage["pending_parked_output_bytes"] = production["pending_publish_bytes"]
    storage["pending_parked_output_text"] = production["pending_publish_text"]
    workers = _workers(worker_payload)
    summary_warnings = [str(item) for item in warnings if str(item).strip()]
    if not rows:
        summary_warnings.append("No completed jobs are available from the completed manifest.")
    coverage = _coverage(rows, storage=storage, source_backfill=source_backfill_payload)
    attention_items = _attention_items(
        coverage=coverage,
        route_mix=route_mix,
        storage=storage,
        production=production,
        workers=workers,
        warnings=summary_warnings,
    )
    return {
        "schema_version": METRICS_SCHEMA_VERSION,
        "generated_at": generated_at or utc_now_text(),
        "read_only": True,
        "evidence_authority": "backend",
        "coverage": coverage,
        "attention_items": attention_items,
        "overview": {
            "total_jobs": len(rows),
            "remux_count": route_mix["remux_count"],
            "encode_count": route_mix["encode_count"],
            "other_route_count": route_mix["other_route_count"],
            "total_data_produced_bytes": storage["total_data_produced_bytes"],
            "total_data_produced_text": storage["total_data_produced_text"],
            "output_written_bytes": storage["output_written_bytes"],
            "output_written_text": storage["output_written_text"],
            "gross_storage_saved_bytes": storage["gross_storage_saved_bytes"],
            "gross_storage_saved_text": storage["gross_storage_saved_text"],
            "net_storage_saved_bytes": storage["net_storage_saved_bytes"],
            "net_storage_saved_text": storage["net_storage_saved_text"],
            "net_storage_saved_percent": storage["net_storage_saved_percent"],
            "pending_publish_bytes": production["pending_publish_bytes"],
            "pending_publish_text": production["pending_publish_text"],
            "worker_count": workers["worker_count"],
            "worker_session_completed": workers["session_completed"],
            "worker_session_failed": workers["session_failed"],
            "metrics_source_count": _int_value(source_backfill_payload.get("source_count")),
            "metrics_enabled_source_count": _int_value(source_backfill_payload.get("enabled_source_count")),
            "metrics_backfill_record_count": _int_value(source_backfill_payload.get("enabled_cache_record_count")),
        },
        "route_mix": route_mix,
        "storage": storage,
        "production": production,
        "workers": workers,
        "source_backfill": source_backfill_payload,
        "source_evidence": _source_evidence(
            completed_source=completed_source,
            rows=rows,
            pending_publish=pending_payload,
            network_workers=worker_payload,
            final_library=final_library_payload,
            source_backfill=source_backfill_payload,
        ),
        "summary_lines": [
            f"Jobs: {len(rows)} total; remux={route_mix['remux_count']}; encode={route_mix['encode_count']}; other={route_mix['other_route_count']}.",
            f"Data produced: {storage['total_data_produced_text']}; net storage saved: {storage['net_storage_saved_text']}.",
            f"Pending publish: {production['pending_publish_count']} manifest row(s), {production['pending_publish_text']}.",
            f"Workers: role={workers['role']}; active={workers['active_count']}; idle={workers['idle_count']}; completed session={workers['session_completed']}; failed session={workers['session_failed']}.",
            f"Metrics sidecar sources: {_int_value(source_backfill_payload.get('enabled_source_count'))}/{_int_value(source_backfill_payload.get('source_count'))} enabled; cached backfill records={_int_value(source_backfill_payload.get('enabled_cache_record_count'))}.",
            "Mutation guardrail: metrics are aggregated from backend read models only; this route does not launch work, drain pending publish, promote, repair, save settings, mutate queue state, or touch media files.",
        ],
        "warnings": summary_warnings,
    }


__all__ = [
    "METRICS_SCHEMA_VERSION",
    "build_metrics_payload",
    "utc_now_text",
]
