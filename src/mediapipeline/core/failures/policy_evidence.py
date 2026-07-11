"""Failure preview policy and result helpers."""

from __future__ import annotations

import os
from pathlib import Path
from typing import TYPE_CHECKING, Any

from mediapipeline.core.failures.retry_state import retry_state_for_failure_row, retry_state_payload
from mediapipeline.core.failures.contracts import FailureRecord

if TYPE_CHECKING:
    from mediapipeline.core.kernel.dto_inventory import FailurePreviewDto


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
FAILURE_OPEN_TARGETS = {
    "artifact": "failure artifact",
    "repro": "reproduction file",
    "record_file": "failure record file",
    "record_folder": "failure record folder",
}
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



from mediapipeline.core.failures.policy_support import *  # noqa: F403

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

__all__ = (
    "_failure_stream_label",
    "_failure_stream_row",
    "_failure_stream_rows_from_inventory",
    "_failure_stream_rows_from_evidence",
    "_failure_inventory_counts",
    "_failure_proof_field",
    "_failure_video_evidence",
    "_failure_subtitle_evidence",
    "_failure_generic_evidence",
    "_failure_evidence_display_lines",
    "_failure_evidence_details",
)
