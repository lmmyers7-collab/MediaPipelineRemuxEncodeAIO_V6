"""Failure preview policy and result helpers."""

from __future__ import annotations

import os
from pathlib import Path
from typing import TYPE_CHECKING, Any

from mediapipeline.core.failures.retry_state import retry_state_for_failure_row, retry_state_payload
from mediapipeline.desktop.models import FailureRecord

if TYPE_CHECKING:
    from mediapipeline.desktop.application.dto import FailurePreviewDto


FAILURE_MARKER_SERVICE_UNAVAILABLE_MESSAGE = "Failure marker service is not available."
FAILURE_MARKERS_EMPTY_MESSAGE = "No failure markers are available from the state store."
FAILURE_REPORT_SERVICE_UNAVAILABLE_MESSAGE = "Failure report service is not available."
FAILURE_NO_JSON_REPORT_MESSAGE = "No failure JSON report is available yet."
FAILURE_LOADER_UNAVAILABLE_MESSAGE = "Failure report loader is not available."
FAILURE_JSON_EMPTY_MESSAGE = "Latest failure JSON contains no rows."


FAILURE_RESOLUTION_SCHEMA_VERSION = "desktop_failure_resolution.v1"
FAILURE_RESOLUTION_GROUP_SCHEMA_VERSION = "desktop_failure_resolution_group.v1"
FAILURE_EVIDENCE_DETAILS_SCHEMA_VERSION = "desktop_failure_evidence_details.v1"
FAILURE_EVIDENCE_MAX_LINES = 10
FAILURE_EVIDENCE_MAX_STREAM_ROWS = 16
FAILURE_EVIDENCE_MAX_PROOF_FIELDS = 16
FAILURE_RESOLUTION_OWNER_PAGES = {
    "Pending Publish": "pending",
    "Queue": "queue",
    "Settings": "settings",
    "Completed": "completed",
    "Diagnostics": "diagnostics",
    "Manual review": "diagnostics",
    "Backend retry": "",
}
FAILURE_LIFECYCLE_LABELS = {
    "new": "New",
    "acknowledged": "Acknowledged",
    "working": "Working",
    "waiting_backend": "Waiting retry",
    "ready_to_clear": "Ready to clear",
    "resolved": "Resolved",
    "reopened": "Reopened",
}
FAILURE_LIFECYCLE_TRANSITION_LABELS = {
    "acknowledge": "Acknowledge",
    "start_work": "Start work",
    "complete_step": "Complete step",
    "waive_step": "Waive step",
    "mark_resolved": "Mark resolved",
    "reopen": "Reopen",
}


def _failure_preview_dto(**kwargs: Any) -> "FailurePreviewDto":
    from mediapipeline.desktop.application.dto_inventory import FailurePreviewDto

    return FailurePreviewDto(**kwargs)


def normalize_failure_source_kind(value: Any) -> str:
    return str(value or "latest_json").strip().casefold()


def bounded_failure_limit(value: Any, *, default: int = 100, minimum: int = 1, maximum: int = 500) -> int:
    try:
        limit = int(value or default)
    except (TypeError, ValueError):
        limit = default
    return min(maximum, max(minimum, limit))


def _failure_text(value: Any) -> str:
    return str(value or "").strip()


def _failure_payload_value(payload: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        if key not in payload:
            continue
        value = payload.get(key)
        if value is None:
            continue
        if isinstance(value, str) and not value.strip():
            continue
        return value
    return None


def _failure_mapping(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _failure_payload_mapping(payload: dict[str, Any], *keys: str) -> dict[str, Any]:
    return _failure_mapping(_failure_payload_value(payload, *keys))


def _failure_list(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    if value is None:
        return []
    return [value]


def _failure_evidence_value(mapping: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in mapping and mapping.get(key) is not None:
            return mapping.get(key)
    return None


def _failure_evidence_int(value: Any, default: int = 0) -> int:
    try:
        fallback = int(default)
    except (TypeError, ValueError):
        fallback = 0
    if value is None:
        return fallback
    try:
        return int(value)
    except (TypeError, ValueError):
        return fallback


def _failure_evidence_bool(value: Any, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    text = _failure_text(value).casefold()
    if text in {"1", "true", "yes"}:
        return True
    if text in {"0", "false", "no"}:
        return False
    return default


def _failure_bounded_text(value: Any, limit: int = 240) -> str:
    text = _failure_text(value)
    if len(text) <= limit:
        return text
    return f"{text[: limit - 3].rstrip()}..."


def _failure_unique_lines(lines: list[str], *, limit: int = FAILURE_EVIDENCE_MAX_LINES) -> list[str]:
    unique: list[str] = []
    seen: set[str] = set()
    for line in lines:
        text = _failure_bounded_text(line)
        if not text:
            continue
        key = text.casefold()
        if key in seen:
            continue
        seen.add(key)
        unique.append(text)
        if len(unique) >= limit:
            break
    return unique


def _failure_stream_label(row: dict[str, object]) -> str:
    source = _failure_text(row.get("source")) or "source"
    index_value = row.get("index")
    index = "" if index_value is None else str(index_value).strip()
    codec = _failure_text(row.get("codec")) or "unknown"
    width = _failure_evidence_int(row.get("width"), 0)
    height = _failure_evidence_int(row.get("height"), 0)
    resolution = f" {width}x{height}" if width > 0 and height > 0 else ""
    prefix = f"{source} v:{index}" if index and index != "-1" else f"{source} video"
    suffix = " attached-picture" if row.get("attached_picture") is True else ""
    return _failure_bounded_text(f"{prefix} {codec}{resolution}{suffix}")


def _failure_stream_row(raw: Any, *, source: str, attached_default: bool = False) -> dict[str, object]:
    stream = _failure_mapping(raw)
    row: dict[str, object] = {
        "kind": _failure_text(_failure_evidence_value(stream, "kind")) or f"{source}_video",
        "source": _failure_text(_failure_evidence_value(stream, "source")) or source,
        "index": _failure_evidence_int(_failure_evidence_value(stream, "index", "Index"), -1),
        "ordinal": _failure_evidence_int(_failure_evidence_value(stream, "ordinal", "VideoOrdinal", "video_ordinal"), -1),
        "codec": _failure_bounded_text(_failure_evidence_value(stream, "codec", "Codec", "codec_name"), 64).casefold(),
        "width": _failure_evidence_int(_failure_evidence_value(stream, "width", "Width"), 0),
        "height": _failure_evidence_int(_failure_evidence_value(stream, "height", "Height"), 0),
        "attached_picture": _failure_evidence_bool(
            _failure_evidence_value(stream, "attached_picture", "AttachedPicture"),
            attached_default,
        ),
    }
    row["label"] = _failure_stream_label(row)
    return row


def _failure_stream_rows_from_inventory(inventory: dict[str, Any], *, source: str) -> list[dict[str, object]]:
    if not inventory:
        return []
    rows = [
        _failure_stream_row(stream, source=source, attached_default=False)
        for stream in _failure_list(_failure_evidence_value(inventory, "RealVideoStreams", "real_video_streams"))
    ]
    rows.extend(
        _failure_stream_row(stream, source=source, attached_default=True)
        for stream in _failure_list(
            _failure_evidence_value(inventory, "AttachedPicStreams", "attached_pic_streams", "attached_picture_streams")
        )
    )
    return rows[:FAILURE_EVIDENCE_MAX_STREAM_ROWS]


def _failure_stream_rows_from_evidence(evidence: dict[str, Any]) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for stream in _failure_list(_failure_evidence_value(evidence, "source_streams", "SourceStreams")):
        rows.append(_failure_stream_row(stream, source="source"))
    for stream in _failure_list(_failure_evidence_value(evidence, "output_streams", "OutputStreams")):
        rows.append(_failure_stream_row(stream, source="output"))
    if not rows:
        for stream in _failure_list(_failure_evidence_value(evidence, "stream_rows", "StreamRows")):
            source = _failure_text(_failure_mapping(stream).get("source")) or "source"
            rows.append(_failure_stream_row(stream, source=source))
    return rows[:FAILURE_EVIDENCE_MAX_STREAM_ROWS]


def _failure_inventory_counts(inventory: dict[str, Any]) -> tuple[int, int]:
    if not inventory:
        return 0, 0
    return (
        _failure_evidence_int(_failure_evidence_value(inventory, "RealVideoStreamCount", "real_video_stream_count"), 0),
        _failure_evidence_int(_failure_evidence_value(inventory, "AttachedPicCount", "attached_pic_count"), 0),
    )


def _failure_proof_field(label: str, value: Any) -> dict[str, str] | None:
    text = _failure_bounded_text(value)
    if not text:
        return None
    return {"label": label, "value": text}


def _failure_video_evidence(payload: dict[str, Any]) -> dict[str, object]:
    evidence = _failure_payload_mapping(payload, "video_stream_evidence", "VideoStreamEvidence")
    stream_rows: list[dict[str, object]] = []
    summary_lines: list[str] = []
    proof_fields: list[dict[str, str]] = []
    source_name = ""

    if evidence:
        source_name = "video_stream_evidence"
        summary_lines.extend(
            _failure_text(line)
            for line in _failure_list(_failure_evidence_value(evidence, "summary_lines", "SummaryLines"))
        )
        stream_rows.extend(_failure_stream_rows_from_evidence(evidence))
        source_real = _failure_evidence_int(_failure_evidence_value(evidence, "source_real_video_stream_count"), 0)
        source_attached = _failure_evidence_int(_failure_evidence_value(evidence, "source_attached_picture_stream_count"), 0)
        output_real = _failure_evidence_int(_failure_evidence_value(evidence, "output_real_video_stream_count"), 0)
        output_attached = _failure_evidence_int(_failure_evidence_value(evidence, "output_attached_picture_stream_count"), 0)
        if source_real or source_attached:
            summary_lines.append(f"Video streams: source real={source_real}, attached={source_attached}")
        if output_real or output_attached or _failure_list(_failure_evidence_value(evidence, "output_streams")):
            summary_lines.append(f"Video streams: output real={output_real}, attached={output_attached}")
        route = _failure_text(_failure_evidence_value(evidence, "route"))
        if route:
            field = _failure_proof_field("Route", route)
            if field:
                proof_fields.append(field)

    preservation = _failure_payload_mapping(payload, "video_stream_preservation", "VideoStreamPreservation")
    if preservation:
        source_name = source_name or "video_stream_preservation"
        source_inventory = _failure_mapping(_failure_evidence_value(preservation, "SourceInventory", "source_inventory"))
        output_inventory = _failure_mapping(_failure_evidence_value(preservation, "OutputInventory", "output_inventory"))
        source_real = _failure_evidence_int(
            _failure_evidence_value(preservation, "SourceCount", "source_count", "source_video_stream_count"),
            _failure_payload_value(payload, "source_video_stream_count", "SourceVideoStreamCount") or 0,
        )
        output_real = _failure_evidence_int(
            _failure_evidence_value(preservation, "OutputCount", "output_count", "output_video_stream_count"),
            _failure_payload_value(payload, "output_video_stream_count", "OutputVideoStreamCount") or 0,
        )
        _source_inventory_real, source_attached = _failure_inventory_counts(source_inventory)
        _output_inventory_real, output_attached = _failure_inventory_counts(output_inventory)
        summary_lines.append(f"Video streams: source real={source_real}, attached={source_attached}")
        summary_lines.append(f"Video streams: output real={output_real}, attached={output_attached}")
        stream_rows.extend(_failure_stream_rows_from_inventory(source_inventory, source="source"))
        stream_rows.extend(_failure_stream_rows_from_inventory(output_inventory, source="output"))

    inventory = _failure_payload_mapping(payload, "video_stream_inventory", "VideoStreamInventory")
    if inventory:
        source_name = source_name or "video_stream_inventory"
        source_real, source_attached = _failure_inventory_counts(inventory)
        summary_lines.append(f"Video streams: source real={source_real}, attached={source_attached}")
        stream_rows.extend(_failure_stream_rows_from_inventory(inventory, source="source"))

    source_count = _failure_payload_value(payload, "source_video_stream_count", "SourceVideoStreamCount")
    output_count = _failure_payload_value(payload, "output_video_stream_count", "OutputVideoStreamCount")
    attached_count = _failure_payload_value(payload, "attached_picture_stream_count", "AttachedPictureStreamCount")
    if source_count is not None and not any(line.startswith("Video streams: source") for line in summary_lines):
        source_name = source_name or "video_stream_counts"
        summary_lines.append(f"Video streams: source real={_failure_evidence_int(source_count)}, attached={_failure_evidence_int(attached_count)}")
    if output_count is not None and not any(line.startswith("Video streams: output") for line in summary_lines):
        source_name = source_name or "video_stream_counts"
        summary_lines.append(f"Video streams: output real={_failure_evidence_int(output_count)}, attached=0")

    burn_stream = _failure_payload_value(payload, "subtitle_burn_stream", "SubtitleBurnStream")
    field = _failure_proof_field("Subtitle burn stream", burn_stream)
    if field:
        proof_fields.append(field)

    if not summary_lines and not stream_rows and not proof_fields:
        return {}
    return {
        "source": source_name or "video_stream_payload",
        "summary_lines": _failure_unique_lines(summary_lines),
        "stream_rows": stream_rows[:FAILURE_EVIDENCE_MAX_STREAM_ROWS],
        "proof_fields": proof_fields[:FAILURE_EVIDENCE_MAX_PROOF_FIELDS],
    }


def _failure_subtitle_evidence(payload: dict[str, Any]) -> dict[str, object]:
    details = _failure_payload_mapping(payload, "subtitle_failure_details", "SubtitleFailureDetails")
    if not details:
        return {}
    family = _failure_text(_failure_evidence_value(details, "family"))
    count = _failure_evidence_int(_failure_evidence_value(details, "failure_count", "FailureCount"), 0)
    truncated = _failure_evidence_int(_failure_evidence_value(details, "truncated_count", "TruncatedCount"), 0)
    failures = _failure_list(_failure_evidence_value(details, "failures", "Failures"))
    summary = f"Subtitle failures: {count or len(failures)} recorded"
    if family:
        summary = f"{summary} ({family})"
    proof_fields: list[dict[str, str]] = []
    for failure in failures[:FAILURE_EVIDENCE_MAX_PROOF_FIELDS]:
        item = _failure_mapping(failure)
        stream_index = _failure_evidence_int(_failure_evidence_value(item, "stream_index", "StreamIndex"), -1)
        label = f"Subtitle stream {stream_index}" if stream_index >= 0 else "Subtitle stream"
        error_code = _failure_text(_failure_evidence_value(item, "error_code", "ErrorCode")) or "SUBTITLE_UNKNOWN_FAILURE"
        reason = _failure_text(_failure_evidence_value(item, "reason", "Reason")) or "failure record was malformed"
        field = _failure_proof_field(label, f"{error_code}: {reason}")
        if field:
            proof_fields.append(field)
        repro = _failure_proof_field("Subtitle repro", _failure_evidence_value(item, "repro_path", "ReproPath"))
        if repro:
            proof_fields.append(repro)
        tool = _failure_proof_field("Subtitle tool", _failure_evidence_value(item, "tool", "Tool"))
        if tool:
            proof_fields.append(tool)
    if truncated:
        field = _failure_proof_field("Subtitle evidence", f"{truncated} additional failure(s) omitted from preview")
        if field:
            proof_fields.append(field)
    return {
        "source": "subtitle_failure_details",
        "summary_lines": [summary],
        "stream_rows": [],
        "proof_fields": proof_fields[:FAILURE_EVIDENCE_MAX_PROOF_FIELDS],
    }


def _failure_generic_evidence(payload: dict[str, Any]) -> dict[str, object]:
    proof_fields: list[dict[str, str]] = []
    for key, label in (
        ("tool", "Tool"),
        ("operation", "Operation"),
        ("category", "Category"),
        ("config_key", "Config key"),
        ("config_path", "Config path"),
        ("tool_path", "Tool path"),
        ("expected_path", "Expected path"),
        ("actual_path", "Actual path"),
        ("missing_path", "Missing path"),
        ("encoder_backend", "Encoder backend"),
        ("video_codec", "Video codec"),
        ("dynamic_hdr_policy", "Dynamic HDR policy"),
        ("dynamic_hdr_action", "Dynamic HDR action"),
        ("dynamic_hdr_reason_code", "Dynamic HDR reason code"),
        ("dynamic_hdr_summary", "Dynamic HDR summary"),
    ):
        field = _failure_proof_field(label, _failure_payload_value(payload, key, "".join(part.title() for part in key.split("_"))))
        if field:
            proof_fields.append(field)

    encoder_activation = _failure_payload_mapping(payload, "encoder_activation", "EncoderActivation")
    if encoder_activation:
        for key, label in (("error_code", "Encoder activation code"), ("reason", "Encoder activation reason")):
            field = _failure_proof_field(label, _failure_evidence_value(encoder_activation, key, "".join(part.title() for part in key.split("_"))))
            if field:
                proof_fields.append(field)

    mux = _failure_payload_mapping(payload, "encode_attachment_mux", "EncodeAttachmentMux")
    if mux:
        for key, label in (("stage", "Attachment mux stage"), ("error_code", "Attachment mux code"), ("reason", "Attachment mux reason")):
            field = _failure_proof_field(label, _failure_evidence_value(mux, key, "".join(part.title() for part in key.split("_"))))
            if field:
                proof_fields.append(field)

    if not proof_fields:
        return {}
    return {
        "source": "known_failure_payload",
        "summary_lines": [],
        "stream_rows": [],
        "proof_fields": proof_fields[:FAILURE_EVIDENCE_MAX_PROOF_FIELDS],
    }


def _failure_evidence_display_lines(evidence: dict[str, object], *, include_fallback: bool = False) -> list[str]:
    if not isinstance(evidence, dict):
        return []
    if evidence.get("structured") is not True and not include_fallback:
        return []
    lines: list[str] = []
    lines.extend(_failure_text(line) for line in _failure_list(evidence.get("summary_lines")))
    for row in _failure_list(evidence.get("stream_rows"))[:FAILURE_EVIDENCE_MAX_STREAM_ROWS]:
        label = _failure_text(_failure_mapping(row).get("label")) or _failure_stream_label(_failure_mapping(row))
        lines.append(label)
    for field in _failure_list(evidence.get("proof_fields"))[:FAILURE_EVIDENCE_MAX_PROOF_FIELDS]:
        item = _failure_mapping(field)
        label = _failure_text(item.get("label"))
        value = _failure_text(item.get("value"))
        if label and value:
            lines.append(f"{label}: {value}")
    return _failure_unique_lines(lines)


def _failure_evidence_details(payload: dict[str, Any]) -> dict[str, object]:
    parts = [
        _failure_video_evidence(payload),
        _failure_subtitle_evidence(payload),
        _failure_generic_evidence(payload),
    ]
    summary_lines: list[str] = []
    stream_rows: list[dict[str, object]] = []
    proof_fields: list[dict[str, str]] = []
    sources: list[str] = []
    for part in parts:
        if not part:
            continue
        source = _failure_text(part.get("source"))
        if source and source not in sources:
            sources.append(source)
        summary_lines.extend(_failure_text(line) for line in _failure_list(part.get("summary_lines")))
        stream_rows.extend(row for row in _failure_list(part.get("stream_rows")) if isinstance(row, dict))
        proof_fields.extend(field for field in _failure_list(part.get("proof_fields")) if isinstance(field, dict))

    structured = bool(summary_lines or stream_rows or proof_fields)
    if not structured:
        return {
            "schema_version": FAILURE_EVIDENCE_DETAILS_SCHEMA_VERSION,
            "structured": False,
            "source": "fallback",
            "summary_lines": [
                "No structured proof was recorded for this failure row; inspect the record file and run logs."
            ],
            "stream_rows": [],
            "proof_fields": [],
        }

    return {
        "schema_version": FAILURE_EVIDENCE_DETAILS_SCHEMA_VERSION,
        "structured": True,
        "source": ", ".join(sources) or "failure_payload",
        "summary_lines": _failure_unique_lines(summary_lines),
        "stream_rows": stream_rows[:FAILURE_EVIDENCE_MAX_STREAM_ROWS],
        "proof_fields": proof_fields[:FAILURE_EVIDENCE_MAX_PROOF_FIELDS],
    }


def _normalized_failure_source_path(value: Any) -> str:
    text = _failure_text(value)
    if not text:
        return ""
    normalized = os.path.normcase(os.path.normpath(text))
    return normalized.replace("/", "\\").casefold()


def _failure_lookup_key(kind: str, *values: Any) -> str:
    parts = [_failure_text(value).casefold() for value in values]
    if not all(parts):
        return ""
    return "\u001f".join([kind, *parts])


def _failure_marker_lookup_keys_for_record(record: FailureRecord) -> list[str]:
    keys: list[str] = []
    source_key = _normalized_failure_source_path(record.source_path_text)
    if source_key:
        keys.append(source_key)
    job_key = _failure_lookup_key("job", record.job_id, record.stage, record.error_code)
    if job_key:
        keys.append(job_key)
    correlation_key = _failure_lookup_key(
        "correlation",
        record.correlation_id,
        record.source_path_text,
        record.stage,
        record.error_code,
    )
    if correlation_key:
        keys.append(correlation_key)
    return keys


def _failure_marker_lookup_keys_for_row(row: dict[str, object]) -> list[str]:
    keys: list[str] = []
    source_key = _normalized_failure_source_path(row.get("source_path"))
    if source_key:
        keys.append(source_key)
    job_key = _failure_lookup_key("job", row.get("job_id"), row.get("stage"), row.get("error_code"))
    if job_key:
        keys.append(job_key)
    correlation_key = _failure_lookup_key(
        "correlation",
        row.get("correlation_id"),
        row.get("source_path"),
        row.get("stage"),
        row.get("error_code"),
    )
    if correlation_key:
        keys.append(correlation_key)
    return keys


def _unique_failure_marker_paths(marker_paths: list[str]) -> list[str]:
    unique: list[str] = []
    seen: set[str] = set()
    for marker_path in marker_paths:
        text = _failure_text(marker_path)
        if not text:
            continue
        key = os.path.normcase(os.path.abspath(text)).casefold()
        if key in seen:
            continue
        seen.add(key)
        unique.append(text)
    return unique


def failure_marker_lookup(records: object) -> dict[str, list[str]]:
    lookup: dict[str, list[str]] = {}
    for record in records or []:
        if not isinstance(record, FailureRecord):
            continue
        marker_path = _failure_text(record.source_json)
        if not marker_path:
            continue
        for key in _failure_marker_lookup_keys_for_record(record):
            lookup[key] = _unique_failure_marker_paths([*lookup.get(key, []), marker_path])
    return lookup


def _failure_clear_error_available(marker_paths: list[str]) -> dict[str, object]:
    clean_paths = _unique_failure_marker_paths(marker_paths)
    return {
        "available": bool(clean_paths),
        "marker_path": clean_paths[0] if clean_paths else "",
        "marker_paths": clean_paths,
        "marker_count": len(clean_paths),
        "unavailable_reason": "",
    }


def _failure_clear_error_unavailable(reason: str) -> dict[str, object]:
    return {
        "available": False,
        "marker_path": "",
        "marker_paths": [],
        "marker_count": 0,
        "unavailable_reason": reason,
    }


def _failure_plain_summary(row: dict[str, object]) -> str:
    reason = _failure_text(row.get("reason"))
    if reason:
        return reason if len(reason) <= 180 else f"{reason[:177].rstrip()}..."
    code = _failure_text(row.get("error_code"))
    stage = _failure_text(row.get("stage"))
    if code and stage:
        return f"{code} during {stage}."
    if code:
        return code
    if stage:
        return f"Failure recorded during {stage}."
    return "Failure recorded. Review grouped evidence."


def _failure_row_key(row: dict[str, object]) -> str:
    return "\u001f".join(
        [
            _failure_text(row.get("source_json")),
            _failure_text(row.get("source_path")),
            _failure_text(row.get("stage")),
            _failure_text(row.get("error_code")),
            _failure_text(row.get("recorded_at")),
        ]
    ).casefold()


def _failure_suggested_fix(row: dict[str, object]) -> str:
    explicit = _failure_text(row.get("suggested_action"))
    if explicit:
        return explicit
    classification = _failure_text(row.get("classification")).casefold()
    if classification == "transient":
        return "Backend will retry this transient failure on the next backend queue pass. Compare logs first."
    if classification in {"operator_required", "permanent"}:
        return "Open diagnostics and review the source before retry."
    return "Review diagnostics before retry."


def _failure_resolution_search_text(row: dict[str, object]) -> str:
    evidence_lines = _failure_evidence_display_lines(
        row.get("evidence_details") if isinstance(row.get("evidence_details"), dict) else {},
        include_fallback=False,
    )
    values = [
        row.get("stage"),
        row.get("error_code"),
        row.get("classification"),
        row.get("reason"),
        row.get("suggested_action"),
        row.get("retry_safe_next_action"),
        row.get("lookup_title"),
        row.get("source_path"),
        row.get("media_type"),
        *evidence_lines,
    ]
    return " ".join(_failure_text(value) for value in values if _failure_text(value)).casefold()


def _failure_resolution_owner(row: dict[str, object]) -> str:
    text = _failure_resolution_search_text(row)
    classification = _failure_text(row.get("classification")).casefold()
    if "publish" in text or "pending" in text:
        return "Pending Publish"
    if "queue" in text:
        return "Queue"
    if any(token in text for token in ("subtitle", "bdpgs", "tx3g", "vobsub", "ocr")):
        return "Settings"
    if any(token in text for token in ("audio", "commentary", "language")):
        return "Settings"
    if any(token in text for token in ("setting", "policy", "config", "profile")):
        return "Settings"
    if any(token in text for token in ("completed", "output", "manifest")):
        return "Completed"
    if row.get("retry_allowed") is True or classification == "transient":
        return "Backend retry"
    if classification in {"operator_required", "permanent"}:
        return "Manual review"
    return "Diagnostics"


def _failure_resolution_diagnostic_targets(row: dict[str, object], owner: str) -> list[dict[str, str]]:
    targets = [
        {
            "kind": "tail",
            "target": "latest_failure_report",
            "label": "Read Latest Failure",
            "reason": "Read the bounded latest failure text before deciding on cleanup or retry.",
        },
        {
            "kind": "open",
            "target": "latest_failure_json",
            "label": "Open Failure JSON",
            "reason": "Inspect the structured failure payload behind the group.",
        },
        {
            "kind": "open",
            "target": "failed_reports",
            "label": "Open Failure Reports",
            "reason": "Open backend-selected failure report evidence.",
        },
        {
            "kind": "open",
            "target": "run_logs",
            "label": "Open Run Logs",
            "reason": "Compare the issue with recent runtime logs before retry.",
        },
    ]
    classification = _failure_text(row.get("classification")).casefold()
    stage = _failure_text(row.get("stage")).casefold()
    if classification in {"operator_required", "permanent"}:
        targets.append(
            {
                "kind": "open",
                "target": "failed_markers",
                "label": "Open Failure Markers",
                "reason": "Inspect active failure markers before clearing blockers.",
            }
        )
    if owner == "Pending Publish" or "publish" in stage:
        targets.append(
            {
                "kind": "open",
                "target": "pending_publish",
                "label": "Open Pending Publish",
                "reason": "Compare the failure with parked output state.",
            }
        )
    if owner in {"Queue", "Backend retry"} or "queue" in stage:
        targets.append(
            {
                "kind": "open",
                "target": "queue_snapshot",
                "label": "Open Queue Snapshot",
                "reason": "Compare the failure with current queue visibility.",
            }
        )
    unique: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for target in targets:
        key = (target["kind"], target["target"])
        if key in seen:
            continue
        seen.add(key)
        unique.append(target)
    return unique


def _failure_resolution_primary_action(
    *,
    owner: str,
    clearable: bool,
    retry_allowed: bool,
) -> dict[str, object]:
    if retry_allowed:
        return {
            "kind": "wait_for_backend_retry",
            "label": "Wait for backend retry",
            "safe": True,
            "page": "",
        }
    owner_page = FAILURE_RESOLUTION_OWNER_PAGES.get(owner, "")
    if owner_page:
        label = "Review in Diagnostics" if owner_page == "diagnostics" else f"Open {owner}"
        return {
            "kind": "open_owner_page",
            "label": label,
            "owner": owner,
            "page": owner_page,
            "safe": True,
        }
    if clearable:
        return {
            "kind": "preview_marker_clear",
            "label": "Preview marker clear",
            "safe": True,
            "page": "",
        }
    return {
        "kind": "review_details",
        "label": "Review details",
        "owner": owner or "Diagnostics",
        "page": "diagnostics",
        "safe": True,
    }


def _failure_resolution_action_step(owner: str, action: dict[str, object]) -> tuple[str, str]:
    label = _failure_text(action.get("label") if isinstance(action, dict) else "") or "Review details"
    if _failure_text(action.get("kind") if isinstance(action, dict) else "") == "wait_for_backend_retry":
        return "wait_backend_retry", "Backend will retry this transient failure; keep evidence visible and do not clear markers yet."
    if owner == "Pending Publish":
        return "open_owner", "Open Pending Publish and compare parked output, destination, and drain evidence."
    if owner == "Queue":
        return "open_owner", "Open Queue and compare current row, hold, retry, and queue snapshot evidence."
    if owner == "Settings":
        return "open_owner", "Open Settings and correct the profile, subtitle, audio, config, or policy input that caused the stop."
    if owner == "Completed":
        return "open_owner", "Open Completed and compare manifest/output evidence before accepting or rerunning."
    if owner in {"Diagnostics", "Manual review"}:
        return "open_owner", "Open Diagnostics and inspect failure JSON, reports, markers, and run logs."
    return "primary_action", label


def _failure_resolution_group_key(row: dict[str, object], owner: str, suggested_action: str) -> str:
    parts = [
        _failure_text(row.get("error_code")).casefold() or "no-code",
        _failure_text(row.get("stage")).casefold() or "unknown-stage",
        owner.casefold() or "unknown-owner",
        suggested_action.casefold() or "review",
    ]
    return "\u001f".join(parts)


def _failure_resolution_severity_priority(severity: str) -> int:
    value = str(severity or "").casefold()
    if value in {"blocked", "error", "failed", "critical", "danger", "fatal"}:
        return 0
    if value in {"warning", "warn", "retrying", "review", "stale"}:
        return 1
    if value in {"info", "unknown"}:
        return 2
    return 3


def _failure_resolution_status_label(severity: str) -> str:
    if _failure_resolution_severity_priority(severity) == 0:
        return "Needs operator"
    if _failure_resolution_severity_priority(severity) == 1:
        return "Review"
    return "Recorded"


def _failure_journal_events_for_group(group: dict[str, object], journal_state: dict[str, object] | None) -> list[dict[str, object]]:
    journal_key = _failure_text(group.get("journal_key")) or _failure_text(group.get("group_key"))
    if not journal_key or not isinstance(journal_state, dict):
        return []
    events = [event for event in journal_state.get("events") or [] if isinstance(event, dict)]
    return [
        event for event in events
        if _failure_text(event.get("journal_key")).casefold() == journal_key.casefold()
    ][-8:]


def _failure_lifecycle_state(group: dict[str, object], events: list[dict[str, object]]) -> str:
    clearable_count = int(group.get("clearable_count") or 0)
    retryable_count = int(group.get("retryable_count") or 0)
    blocking_count = int(group.get("blocking_count") or 0)
    last_state = _failure_text(events[-1].get("lifecycle_state") if events else "").casefold()
    if last_state == "resolved" and clearable_count > 0:
        return "reopened"
    if last_state in FAILURE_LIFECYCLE_LABELS:
        return last_state
    if retryable_count > 0 and blocking_count == 0:
        return "waiting_backend"
    if clearable_count > 0 and blocking_count == 0:
        return "ready_to_clear"
    return "new"


def _failure_available_transitions(state: str, verification: dict[str, object]) -> list[dict[str, object]]:
    transitions_by_state = {
        "new": ["acknowledge", "start_work"],
        "acknowledged": ["start_work", "mark_resolved"],
        "working": ["complete_step", "mark_resolved"],
        "waiting_backend": ["acknowledge", "start_work"],
        "ready_to_clear": ["mark_resolved"],
        "resolved": ["reopen"],
        "reopened": ["start_work", "mark_resolved"],
    }
    blockers = verification.get("blockers") if isinstance(verification, dict) else []
    safe_to_resolve = bool(verification.get("safe_to_resolve")) if isinstance(verification, dict) else False
    transitions: list[dict[str, object]] = []
    for transition in transitions_by_state.get(state, ["acknowledge"]):
        disabled = transition == "mark_resolved" and not safe_to_resolve
        reason = "; ".join(str(item) for item in blockers if str(item).strip()) if disabled else ""
        transitions.append(
            {
                "transition": transition,
                "label": FAILURE_LIFECYCLE_TRANSITION_LABELS.get(transition, transition.replace("_", " ").title()),
                "preview_required": transition in {"mark_resolved", "reopen", "waive_step"},
                "reason_required": transition in {"mark_resolved", "reopen", "waive_step"},
                "disabled": disabled,
                "disabled_reason": reason,
            }
        )
    return transitions


def _failure_verification(group: dict[str, object]) -> dict[str, object]:
    active_marker_count = int(group.get("clearable_count") or 0)
    retryable_count = int(group.get("retryable_count") or 0)
    active_rows = int(group.get("row_count") or 0)
    blockers: list[str] = []
    if active_marker_count:
        blockers.append("Active failure markers remain in the backend marker folder.")
    if retryable_count:
        blockers.append("At least one row is retryable; wait for backend retry unless operator review changes the cause.")
    return {
        "schema_version": "failure_resolution_verification.v1",
        "active_marker_count": active_marker_count,
        "active_failure_row_count": active_rows,
        "blocking_count": int(group.get("blocking_count") or 0),
        "retryable_count": retryable_count,
        "clearable": active_marker_count > 0,
        "safe_to_resolve": active_marker_count == 0,
        "blockers": blockers,
        "safe_next_action": (
            "Preview and clear markers only after the root cause is understood."
            if active_marker_count
            else "Markers are not active for this group; it can be marked resolved if evidence was reviewed."
        ),
    }


def _failure_playbook_steps(
    group: dict[str, object],
    *,
    lifecycle_state: str,
    verification: dict[str, object],
) -> list[dict[str, object]]:
    owner = _failure_text(group.get("owner")) or "Diagnostics"
    action = group.get("primary_action") if isinstance(group.get("primary_action"), dict) else {}
    action_step_id, action_detail = _failure_resolution_action_step(owner, action)
    resolved = lifecycle_state == "resolved"
    working_started = lifecycle_state in {"working", "ready_to_clear", "resolved"}
    acknowledged = lifecycle_state in {"acknowledged", "working", "ready_to_clear", "resolved"}
    markers_clear = int(verification.get("active_marker_count") or 0) == 0
    return [
        {
            "id": "review_evidence",
            "label": "Review evidence",
            "detail": "Read why it stopped and compare failure JSON, reports, markers, and run logs.",
            "status": "done" if acknowledged or working_started or resolved else "current",
        },
        {
            "id": action_step_id,
            "label": _failure_text(action.get("label") if isinstance(action, dict) else "") or "Open owner page",
            "detail": action_detail,
            "status": "done" if working_started or resolved else "current" if acknowledged else "not_started",
        },
        {
            "id": "verify_markers",
            "label": "Verify marker state",
            "detail": "Confirm whether active backend failure markers still block retry.",
            "status": "done" if markers_clear else "current" if working_started else "not_started",
        },
        {
            "id": "close_issue",
            "label": "Close issue",
            "detail": "Mark resolved only after verification passes; reopen if matching markers return.",
            "status": "done" if resolved else "current" if markers_clear else "blocked",
        },
    ]


def _failure_enrich_resolution_group(group: dict[str, object], journal_state: dict[str, object] | None) -> dict[str, object]:
    group["journal_key"] = _failure_text(group.get("journal_key")) or _failure_text(group.get("group_key"))
    events = _failure_journal_events_for_group(group, journal_state)
    group["timeline"] = [
        {
            "recorded_at": _failure_text(event.get("recorded_at")),
            "transition": _failure_text(event.get("transition")),
            "lifecycle_state": _failure_text(event.get("lifecycle_state")),
            "reason": _failure_text(event.get("reason")),
            "operator_note": _failure_text(event.get("operator_note")),
        }
        for event in events
    ]
    lifecycle_state = _failure_lifecycle_state(group, events)
    group["lifecycle_state"] = lifecycle_state
    group["lifecycle_label"] = FAILURE_LIFECYCLE_LABELS.get(lifecycle_state, lifecycle_state.replace("_", " ").title())
    last_event = events[-1] if events else {}
    group["last_transition_at"] = _failure_text(last_event.get("recorded_at") if isinstance(last_event, dict) else "")
    group["operator_note"] = _failure_text(last_event.get("operator_note") if isinstance(last_event, dict) else "")
    verification = _failure_verification(group)
    group["verification"] = verification
    group["playbook_steps"] = _failure_playbook_steps(
        group,
        lifecycle_state=lifecycle_state,
        verification=verification,
    )
    group["available_transitions"] = _failure_available_transitions(lifecycle_state, verification)
    group["resolution_journal_path"] = _failure_text(journal_state.get("path") if isinstance(journal_state, dict) else "")
    return group


def _failure_resolution_groups(rows: list[dict[str, object]], *, journal_state: dict[str, object] | None = None) -> list[dict[str, object]]:
    grouped: dict[str, dict[str, object]] = {}
    severity_rank: dict[str, int] = {}
    for row in rows:
        triage = row.get("triage") if isinstance(row.get("triage"), dict) else {}
        suggested_action = _failure_text(triage.get("suggested_fix") if isinstance(triage, dict) else "") or _failure_suggested_fix(row)
        owner = _failure_resolution_owner(row)
        group_key = _failure_resolution_group_key(row, owner, suggested_action)
        clear_error = row.get("clear_error") if isinstance(row.get("clear_error"), dict) else {}
        clearable_paths = _unique_failure_marker_paths(clear_error.get("marker_paths") if isinstance(clear_error, dict) else [])
        severity = _failure_text(triage.get("severity") if isinstance(triage, dict) else "") or "info"
        priority = _failure_resolution_severity_priority(severity)
        existing = grouped.get(group_key)
        if existing is None:
            existing = {
                "schema_version": FAILURE_RESOLUTION_GROUP_SCHEMA_VERSION,
                "group_key": group_key,
                "journal_key": group_key,
                "status_label": _failure_text(triage.get("status_label") if isinstance(triage, dict) else "")
                or _failure_resolution_status_label(severity),
                "severity": severity,
                "error_code": _failure_text(row.get("error_code")) or "NO_CODE",
                "stage": _failure_text(row.get("stage")) or "unknown-stage",
                "owner": owner,
                "owner_page": FAILURE_RESOLUTION_OWNER_PAGES.get(owner, ""),
                "suggested_action": suggested_action,
                "cause": _failure_text(triage.get("plain_summary") if isinstance(triage, dict) else "") or _failure_plain_summary(row),
                "safe_next_action": _failure_text(triage.get("safe_next_action") if isinstance(triage, dict) else "")
                or _failure_text(row.get("retry_safe_next_action"))
                or suggested_action,
                "row_count": 0,
                "affected_row_keys": [],
                "affected_sources": [],
                "sample_rows": [],
                "evidence_lines": [],
                "clearable_marker_paths": [],
                "clearable_count": 0,
                "marker_count": 0,
                "blocking_count": 0,
                "retryable_count": 0,
                "operator_required_count": 0,
                "permanent_count": 0,
                "transient_count": 0,
                "diagnostic_targets": _failure_resolution_diagnostic_targets(row, owner),
                "primary_action": {},
            }
            grouped[group_key] = existing
            severity_rank[group_key] = priority
        elif priority < severity_rank[group_key]:
            existing["severity"] = severity
            existing["status_label"] = _failure_text(triage.get("status_label") if isinstance(triage, dict) else "") or existing.get("status_label")
            severity_rank[group_key] = priority

        existing["row_count"] = int(existing.get("row_count") or 0) + 1
        classification = _failure_text(row.get("classification")).casefold()
        if classification == "operator_required":
            existing["operator_required_count"] = int(existing.get("operator_required_count") or 0) + 1
        if classification == "permanent":
            existing["permanent_count"] = int(existing.get("permanent_count") or 0) + 1
        if classification == "transient":
            existing["transient_count"] = int(existing.get("transient_count") or 0) + 1
        if classification in {"operator_required", "permanent"} or _failure_text(row.get("retry_status_state")).casefold() == "blocked":
            existing["blocking_count"] = int(existing.get("blocking_count") or 0) + 1
        if row.get("retry_allowed") is True:
            existing["retryable_count"] = int(existing.get("retryable_count") or 0) + 1

        row_key = _failure_text(row.get("row_key")) or _failure_row_key(row)
        if row_key and row_key not in existing["affected_row_keys"]:
            existing["affected_row_keys"].append(row_key)
        source = _failure_text(row.get("lookup_title")) or _failure_text(row.get("source_path")) or _failure_text(row.get("source_json"))
        if source and source not in existing["affected_sources"]:
            existing["affected_sources"].append(source)
        if len(existing["sample_rows"]) < 5:
            existing["sample_rows"].append(row)
        for line in _failure_evidence_display_lines(
            row.get("evidence_details") if isinstance(row.get("evidence_details"), dict) else {},
            include_fallback=False,
        ):
            if line not in existing["evidence_lines"] and len(existing["evidence_lines"]) < FAILURE_EVIDENCE_MAX_LINES:
                existing["evidence_lines"].append(line)
        marker_paths = _unique_failure_marker_paths([*existing["clearable_marker_paths"], *clearable_paths])
        existing["clearable_marker_paths"] = marker_paths
        existing["clearable_count"] = len(marker_paths)
        existing["marker_count"] = len(marker_paths)

    for group in grouped.values():
        retryable = int(group.get("retryable_count") or 0) > 0
        clearable = int(group.get("clearable_count") or 0) > 0
        group["primary_action"] = _failure_resolution_primary_action(
            owner=_failure_text(group.get("owner")),
            clearable=clearable,
            retry_allowed=retryable,
        )
        group["primary_action_label"] = _failure_text(group["primary_action"].get("label") if isinstance(group["primary_action"], dict) else "")
        group["safe_next_action"] = _failure_text(group.get("safe_next_action")) or group["primary_action_label"]
        _failure_enrich_resolution_group(group, journal_state)

    return sorted(
        grouped.values(),
        key=lambda item: (
            _failure_resolution_severity_priority(_failure_text(item.get("severity"))),
            -int(item.get("blocking_count") or 0),
            -int(item.get("clearable_count") or 0),
            -int(item.get("row_count") or 0),
            _failure_text(item.get("error_code")),
            _failure_text(item.get("stage")),
        ),
    )


def _failure_resolution_summary(
    *,
    rows: list[dict[str, object]],
    groups: list[dict[str, object]],
    source: str,
    source_kind: str,
    warnings: list[str],
) -> dict[str, object]:
    primary = groups[0] if groups else {}
    retryable_count = sum(int(group.get("retryable_count") or 0) for group in groups)
    blocking_count = sum(int(group.get("blocking_count") or 0) for group in groups)
    clearable_paths = _unique_failure_marker_paths(
        [path for group in groups for path in (group.get("clearable_marker_paths") or [])]
    )
    status = "empty"
    status_label = "No active failures"
    if rows:
        if blocking_count:
            status = "blocked"
            status_label = "Needs operator"
        elif retryable_count:
            status = "retrying"
            status_label = "Will retry"
        elif warnings:
            status = "warning"
            status_label = "Review"
        else:
            status = "review"
            status_label = "Review"
    elif warnings:
        status = "warning"
        status_label = "No rows"
    primary_action = primary.get("primary_action") if isinstance(primary, dict) else {}
    return {
        "schema_version": FAILURE_RESOLUTION_SCHEMA_VERSION,
        "status": status,
        "status_label": status_label,
        "source": source,
        "source_kind": source_kind,
        "source_mode_label": "Failure markers" if source_kind == "markers" else "Latest failure JSON",
        "refresh_state": "partial" if warnings and rows else "empty" if not rows else "loaded",
        "row_count": len(rows),
        "group_count": len(groups),
        "primary_group_key": _failure_text(primary.get("group_key") if isinstance(primary, dict) else ""),
        "primary_group_label": _failure_text(primary.get("cause") if isinstance(primary, dict) else ""),
        "primary_owner": _failure_text(primary.get("owner") if isinstance(primary, dict) else "") or "Reports",
        "primary_action": primary_action if isinstance(primary_action, dict) else {},
        "primary_action_label": _failure_text(primary_action.get("label") if isinstance(primary_action, dict) else "")
        or ("Refresh Reports" if not rows else "Review details"),
        "safe_next_action": _failure_text(primary.get("safe_next_action") if isinstance(primary, dict) else "")
        or ("Refresh Reports or open Diagnostics if a recent failure was expected." if not rows else "Review grouped failure evidence."),
        "blocking_count": blocking_count,
        "retryable_count": retryable_count,
        "clearable_count": len(clearable_paths),
        "clearable_marker_paths": clearable_paths,
        "warning_count": len(warnings),
        "lifecycle_counts": {
            state: sum(1 for group in groups if _failure_text(group.get("lifecycle_state")) == state)
            for state in FAILURE_LIFECYCLE_LABELS
        },
        "unacknowledged_count": sum(1 for group in groups if _failure_text(group.get("lifecycle_state")) == "new"),
        "working_count": sum(1 for group in groups if _failure_text(group.get("lifecycle_state")) == "working"),
        "waiting_backend_count": sum(1 for group in groups if _failure_text(group.get("lifecycle_state")) == "waiting_backend"),
        "ready_to_clear_count": sum(1 for group in groups if _failure_text(group.get("lifecycle_state")) == "ready_to_clear"),
        "resolved_recently_count": sum(1 for group in groups if _failure_text(group.get("lifecycle_state")) == "resolved"),
    }


def _failure_triage(row: dict[str, object], retry_state: dict[str, object]) -> dict[str, object]:
    classification = _failure_text(row.get("classification")).casefold()
    status_state = _failure_text(retry_state.get("status_state")).casefold()
    if status_state == "blocked" or classification in {"operator_required", "permanent"}:
        status_label = "Needs operator"
        severity = "blocked"
    elif retry_state.get("retry_allowed") is True:
        status_label = "Will retry"
        severity = "warning"
    elif _failure_text(row.get("reason")) or _failure_text(row.get("error_code")):
        status_label = "Review"
        severity = "warning"
    else:
        status_label = "Recorded"
        severity = "info"
    detail_available = any(
        _failure_text(row.get(key))
        for key in ("reason", "error_code", "stage", "artifact_path", "repro_path", "source_json")
    ) or bool(
        isinstance(row.get("evidence_details"), dict)
        and row.get("evidence_details", {}).get("structured") is True
    )
    return {
        "status_label": status_label,
        "severity": severity,
        "plain_summary": _failure_plain_summary(row),
        "suggested_fix": _failure_suggested_fix(row),
        "safe_next_action": _failure_text(retry_state.get("safe_next_action")) or _failure_suggested_fix(row),
        "detail_available": detail_available,
    }


def _failure_clear_error(
    row: dict[str, object],
    *,
    source_kind: str,
    marker_lookup: dict[str, list[str]] | None,
) -> dict[str, object]:
    if source_kind == "markers":
        marker_path = _failure_text(row.get("source_json"))
        if marker_path:
            return _failure_clear_error_available([marker_path])
        return _failure_clear_error_unavailable("This marker row did not include an active marker path.")

    if marker_lookup is None:
        return _failure_clear_error_unavailable("Active failure markers could not be loaded for this failure row.")
    lookup_keys = _failure_marker_lookup_keys_for_row(row)
    if not lookup_keys:
        return _failure_clear_error_unavailable(
            "This failure row did not include source or job evidence that can be matched to an active marker."
        )
    marker_paths = _unique_failure_marker_paths(
        [path for key in lookup_keys for path in marker_lookup.get(key, [])]
    )
    if marker_paths:
        return _failure_clear_error_available(marker_paths)
    return _failure_clear_error_unavailable(
        "No active failure marker matched this latest-report row. If markers were already cleared, switch to Use failure markers to view active retry blockers only."
    )


def failure_record_to_row(
    record: FailureRecord,
    *,
    source_kind: str = "latest_json",
    marker_lookup: dict[str, list[str]] | None = None,
) -> dict[str, object]:
    row: dict[str, object] = {
        "source_path": record.source_path_text,
        "job_id": record.job_id,
        "correlation_id": record.correlation_id,
        "stage": record.stage,
        "reason": record.reason,
        "classification": record.classification,
        "error_code": record.error_code,
        "media_type": record.media_type,
        "lookup_title": record.lookup_title,
        "recorded_at": record.recorded_at,
        "retry_count": record.retry_count,
        "retry_limit": record.retry_limit,
        "retryable": record.retryable,
        "escalated": record.escalated,
        "artifact_path": str(record.artifact_path or ""),
        "repro_path": str(record.repro_path or ""),
        "suggested_action": record.suggested_action,
        "suggested_rename": record.suggested_rename,
        "source_json": str(record.source_json),
    }
    row["evidence_details"] = _failure_evidence_details(record.payload)
    retry_state = retry_state_for_failure_row(row)
    row["retry_status_state"] = retry_state["status_state"]
    row["retry_allowed"] = retry_state["retry_allowed"]
    row["retry_route_or_command"] = retry_state["retry_route_or_command"]
    row["retry_safe_next_action"] = retry_state["safe_next_action"]
    row["row_key"] = _failure_row_key(row)
    normalized_source_kind = normalize_failure_source_kind(source_kind)
    row["triage"] = _failure_triage(row, retry_state)
    row["clear_error"] = _failure_clear_error(
        row,
        source_kind=normalized_source_kind,
        marker_lookup=marker_lookup,
    )
    return row


def failure_preview_fields(
    records: object,
    *,
    source: str,
    source_kind: str,
    limit: int,
    empty_warning: str,
    marker_lookup: dict[str, list[str]] | None = None,
    resolution_journal: dict[str, object] | None = None,
) -> dict[str, object]:
    valid_records = [record for record in records or [] if isinstance(record, FailureRecord)]
    rows = [
        failure_record_to_row(record, source_kind=source_kind, marker_lookup=marker_lookup)
        for record in valid_records[:limit]
    ]
    classifications = [str(row.get("classification") or "").casefold() for row in rows]
    warnings = [] if rows else [empty_warning]
    if len(valid_records) > len(rows):
        warnings.append(f"Showing {len(rows)} of {len(valid_records)} failure row(s).")
    resolution_groups = _failure_resolution_groups(rows, journal_state=resolution_journal)
    resolution_summary = _failure_resolution_summary(
        rows=rows,
        groups=resolution_groups,
        source=source,
        source_kind=source_kind,
        warnings=warnings,
    )
    return {
        "rows": rows,
        "source": source,
        "source_kind": source_kind,
        "count": len(valid_records),
        "operator_required_count": sum(1 for item in classifications if item == "operator_required"),
        "permanent_count": sum(1 for item in classifications if item == "permanent"),
        "transient_count": sum(1 for item in classifications if item == "transient"),
        "retry_state": retry_state_payload(rows, source=source, source_kind=source_kind),
        "resolution_summary": resolution_summary,
        "resolution_groups": resolution_groups,
        "warnings": warnings,
    }


def failure_marker_service_unavailable_result() -> FailurePreviewDto:
    return _failure_preview_dto(
        source_kind="markers",
        warnings=[FAILURE_MARKER_SERVICE_UNAVAILABLE_MESSAGE],
    )


def failure_markers_read_error_result(markers_path: Path | str | None, exc: Exception) -> FailurePreviewDto:
    return _failure_preview_dto(
        source=str(markers_path or ""),
        source_kind="markers",
        warnings=[f"Failure markers could not be read: {exc}"],
    )


def failure_report_service_unavailable_result() -> FailurePreviewDto:
    return _failure_preview_dto(warnings=[FAILURE_REPORT_SERVICE_UNAVAILABLE_MESSAGE])


def failure_latest_json_resolution_error_result(exc: Exception) -> FailurePreviewDto:
    return _failure_preview_dto(warnings=[f"Latest failure JSON could not be resolved: {exc}"])


def failure_no_json_report_result() -> FailurePreviewDto:
    return _failure_preview_dto(warnings=[FAILURE_NO_JSON_REPORT_MESSAGE])


def failure_loader_unavailable_result(report_path: Path | str) -> FailurePreviewDto:
    return _failure_preview_dto(
        source=str(report_path),
        warnings=[FAILURE_LOADER_UNAVAILABLE_MESSAGE],
    )


def failure_json_read_error_result(report_path: Path | str, exc: Exception) -> FailurePreviewDto:
    return _failure_preview_dto(
        source=str(report_path),
        warnings=[f"Failure JSON could not be read: {exc}"],
    )


def failure_preview_from_records(
    records: object,
    *,
    source: str,
    source_kind: str,
    limit: int,
    empty_warning: str,
    marker_lookup: dict[str, list[str]] | None = None,
    resolution_journal: dict[str, object] | None = None,
) -> FailurePreviewDto:
    return _failure_preview_dto(
        **failure_preview_fields(
            records,
            source=source,
            source_kind=source_kind,
            limit=limit,
            empty_warning=empty_warning,
            marker_lookup=marker_lookup,
            resolution_journal=resolution_journal,
        )
    )


__all__ = [
    "FAILURE_MARKER_SERVICE_UNAVAILABLE_MESSAGE",
    "FAILURE_MARKERS_EMPTY_MESSAGE",
    "FAILURE_REPORT_SERVICE_UNAVAILABLE_MESSAGE",
    "FAILURE_NO_JSON_REPORT_MESSAGE",
    "FAILURE_LOADER_UNAVAILABLE_MESSAGE",
    "FAILURE_JSON_EMPTY_MESSAGE",
    "normalize_failure_source_kind",
    "bounded_failure_limit",
    "failure_marker_lookup",
    "failure_record_to_row",
    "failure_preview_fields",
    "failure_marker_service_unavailable_result",
    "failure_markers_read_error_result",
    "failure_report_service_unavailable_result",
    "failure_latest_json_resolution_error_result",
    "failure_no_json_report_result",
    "failure_loader_unavailable_result",
    "failure_json_read_error_result",
    "failure_preview_from_records",
]
