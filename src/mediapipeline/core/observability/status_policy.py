"""Application status, telemetry, and progress-bar policy helpers."""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
from typing import Any
from collections.abc import Mapping

from mediapipeline.core.telemetry.gpu_usage import gpu_encoder_usage_payload


_StatusSnapshot = Any
_TelemetrySnapshot = Any


APP_CAPABILITIES = (
    "snapshot",
    "telemetry",
    "diagnostics",
    "diagnostics-open",
    "queue-preview",
    "completed-preview",
    "completed-open",
    "close-readiness",
    "command-history",
    "failure-preview",
    "audit-preview",
    "pending-publish-preview",
    "pending-publish-open",
    "maintenance-workspace",
    "maintenance-release-dry-run",
    "maintenance-completed-backfill-dry-run",
    "maintenance-dependency-atlas",
    "rename-preview",
    "rename-apply",
    "schedule-workspace",
    "watch-folder-status",
    "settings-workspace",
    "settings-validate",
    "settings-preview-patch",
    "settings-save-patch",
    "settings-reload",
    "pipeline-control",
    "pipeline-start",
    "audit-start",
    "rerun-start",
    "backend-shutdown",
    "command-result-envelope",
)

ACTIVE_PROGRESS_STATES = (
    "processing",
    "running",
    "active",
    "publishing",
    "copying",
    "encoding",
    "remuxing",
    "probing",
    "auditing",
    "scanning",
    "retrying",
    "copied_pending_reveal",
    "revealing",
    "writing",
    "initializing",
)

COMPLETE_PROGRESS_STATES = ("complete", "completed", "published", "idle")

HELD_PROGRESS_STATES = ("stopped",)

REVIEW_PROGRESS_STATES = ("deferred", "parked", "pending publish", "review")

FAILED_PROGRESS_STATES = ("failed", "error", "blocked", "cancelled", "canceled", "orphaned")


def application_capabilities() -> list[str]:
    return list(APP_CAPABILITIES)


def int_from_mapping(mapping: Mapping[str, Any], *keys: str) -> int:
    for key in keys:
        raw: Any = mapping.get(key)
        try:
            if raw not in (None, ""):
                return int(float(raw))
        except (TypeError, ValueError):
            continue
    return 0


def nullable_int_from_mapping(mapping: Mapping[str, Any], *keys: str) -> int | None:
    for key in keys:
        raw: Any = mapping.get(key)
        try:
            if raw not in (None, ""):
                value = int(float(raw))
                return max(0, value)
        except (TypeError, ValueError):
            continue
    return None


def format_bytes(value: int | None) -> str:
    if value is None:
        return ""
    units = ("B", "KB", "MB", "GB", "TB")
    size = float(max(0, value))
    for unit in units:
        if size < 1024.0 or unit == units[-1]:
            if unit == "B":
                return f"{int(size)} {unit}"
            return f"{size:.1f} {unit}"
        size /= 1024.0
    return f"{value} B"


def snapshot_counts(progress: Mapping[str, Any]) -> dict[str, int]:
    return {
        "queue_index": int_from_mapping(progress, "CurrentQueueIndex"),
        "queue_total": int_from_mapping(progress, "CurrentQueueTotal"),
        "processed": int_from_mapping(progress, "TotalProcessed"),
        "encoded": int_from_mapping(progress, "Encoded"),
        "remuxed": int_from_mapping(progress, "Remuxed"),
        "failed": int_from_mapping(progress, "Failed", "TotalFailed"),
        "movies": int_from_mapping(progress, "Movies"),
        "tv_episodes": int_from_mapping(progress, "TVEpisodes"),
    }


def text_from_mapping(mapping: Mapping[str, Any], *keys: str) -> str:
    for key in keys:
        raw = mapping.get(key)
        if raw not in (None, ""):
            return str(raw).strip()
    return ""


def float_from_mapping(mapping: Mapping[str, Any], *keys: str) -> float | None:
    for key in keys:
        raw: Any = mapping.get(key)
        if raw in (None, ""):
            continue
        try:
            value = float(raw)
        except (TypeError, ValueError):
            continue
        return max(0.0, min(100.0, value))
    return None


def bool_from_mapping(mapping: Mapping[str, Any], *keys: str) -> bool:
    for key in keys:
        raw = mapping.get(key)
        if isinstance(raw, bool):
            return raw
        if raw in (None, ""):
            continue
        text = str(raw).strip().lower()
        if text in {"1", "true", "yes", "y"}:
            return True
        if text in {"0", "false", "no", "n"}:
            return False
    return False


def _parse_progress_datetime(raw: str) -> datetime | None:
    text = str(raw or "").strip()
    if not text:
        return None
    iso_text = text.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(iso_text)
    except ValueError:
        pass
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.strptime(text[:19], fmt)
        except ValueError:
            continue
    return None


def _datetime_is_stale(raw: str, stale_after_seconds: float) -> bool:
    parsed = _parse_progress_datetime(raw)
    if parsed is None:
        return False
    now = datetime.now(parsed.tzinfo) if parsed.tzinfo is not None else datetime.now()
    age = now - parsed
    if age < -timedelta(seconds=5):
        return True
    return age > timedelta(seconds=stale_after_seconds)


def _audit_progress_is_stale(audit_progress: Mapping[str, Any] | None, *, stale_after_seconds: float = 5.0) -> bool:
    if not audit_progress:
        return False
    if bool_from_mapping(audit_progress, "completed", "Completed") or bool_from_mapping(audit_progress, "failed", "Failed"):
        return False
    status = text_from_mapping(audit_progress, "status", "Status").lower()
    if status in {"", "idle", "completed", "failed", "stopped"}:
        return False
    raw = text_from_mapping(audit_progress, "last_update", "LastUpdate", "updated_at", "UpdatedAt")
    if _parse_progress_datetime(raw) is None:
        return True
    return _datetime_is_stale(raw, stale_after_seconds)


def progress_state_status(*values: str, stale: bool = False) -> str:
    text = " ".join(str(value or "").lower() for value in values)
    if any(token in text for token in FAILED_PROGRESS_STATES):
        return "blocked"
    if stale:
        return "warning"
    if any(token in text for token in REVIEW_PROGRESS_STATES):
        return "warning"
    if any(token in text for token in HELD_PROGRESS_STATES):
        return "warning"
    if any(token in text for token in ACTIVE_PROGRESS_STATES):
        return "active"
    if any(token in text for token in COMPLETE_PROGRESS_STATES):
        return "complete"
    if text.strip():
        return "unknown"
    return "idle"


def progress_mode(percent: float | None, status: str) -> str:
    if percent is not None:
        return "determinate"
    if status == "active":
        return "indeterminate"
    return "determinate"


def progress_bar(
    *,
    bar_id: str,
    label: str,
    status: str,
    source: str,
    detail: str = "",
    percent: float | None = None,
    mode: str | None = None,
    updated_at: str = "",
    stale: bool = False,
    steps: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "id": bar_id,
        "label": label,
        "mode": mode or progress_mode(percent, status),
        "percent": percent,
        "status": status,
        "detail": detail,
        "source": source,
        "updated_at": updated_at,
        "stale": bool(stale),
    }
    if steps is not None:
        payload["steps"] = steps
    return payload


def copy_bytes_detail(progress: Mapping[str, Any]) -> str:
    copied = nullable_int_from_mapping(progress, "CopyBytesCopied")
    total = nullable_int_from_mapping(progress, "CopyTotalBytes")
    if total is not None and total > 0:
        return f"{format_bytes(copied or 0)} / {format_bytes(total)}"
    if copied is not None and copied > 0:
        return f"{format_bytes(copied)} copied"
    return ""


def finalizing_progress_detail(stage: str, percent: float | None) -> str:
    if percent is None or percent < 95.0 or percent >= 100.0:
        return ""
    normalized = stage.strip().lower()
    if normalized in {"encode", "encode_cpu", "encode_verify"}:
        return "near complete; backend may still verify output, write sidecars, publish, or park"
    if normalized in {"remux", "remux_av", "remux_verify"}:
        return "near complete; backend may still verify remux, write sidecars, publish, or park"
    return ""


def publish_step_payloads(stage: str, push_state: str, sidecar_state: str) -> list[dict[str, Any]]:
    stage_lower = stage.strip().lower()
    push_lower = push_state.strip().lower()
    sidecar_lower = sidecar_state.strip().lower()

    copy_done = push_lower in {"copied_pending_reveal", "revealing", "complete", "deferred"} or bool(sidecar_lower)
    sidecar_done = sidecar_lower == "complete" or push_lower in {"revealing", "complete", "deferred"}
    reveal_done = push_lower in {"complete", "deferred"}
    finalize_done = push_lower == "complete"

    copy_status = "complete" if copy_done else "active" if push_lower in {"copying", "retrying"} else "pending"
    sidecar_status = "complete" if sidecar_done else "active" if stage_lower == "sidecar" or sidecar_lower == "writing" else "pending"
    reveal_status = "complete" if reveal_done else "active" if push_lower == "revealing" else "pending"
    finalize_status = "complete" if finalize_done else "review" if push_lower == "deferred" else "pending"

    if sidecar_lower == "failed":
        sidecar_status = "blocked"
    if push_lower == "failed":
        if stage_lower == "sidecar":
            sidecar_status = "blocked"
        elif stage_lower in {"push", "retry_pending_push"}:
            reveal_status = "blocked" if copy_done else copy_status
            if not copy_done:
                copy_status = "blocked"

    return [
        {"id": "copy", "label": "Copy completed output", "status": copy_status},
        {"id": "sidecars", "label": "Write sidecars", "status": sidecar_status},
        {"id": "reveal", "label": "Reveal output", "status": reveal_status},
        {"id": "finalize", "label": "Finalize", "status": finalize_status},
    ]


def publish_steps_percent(steps: list[dict[str, Any]]) -> float:
    if not steps:
        return 0.0
    completed = sum(1 for step in steps if step.get("status") == "complete")
    return max(0.0, min(100.0, round((completed / len(steps)) * 100.0, 1)))


def subtitle_progress_bars(progress: Mapping[str, Any], *, stale: bool) -> list[dict[str, Any]]:
    raw = progress.get("SubtitleProgress")
    if not isinstance(raw, Mapping):
        return []
    step_total = int_from_mapping(raw, "step_total", "StepTotal")
    if step_total <= 0:
        return []
    step_index = max(0, min(step_total, int_from_mapping(raw, "step_index", "StepIndex")))
    percent = float_from_mapping(raw, "percent", "Percent")
    if percent is None:
        percent = max(0.0, min(100.0, round((step_index / step_total) * 100.0, 1)))
    kind = text_from_mapping(raw, "kind", "Kind") or "subtitle"
    stream_index = text_from_mapping(raw, "stream_index", "StreamIndex")
    stage = text_from_mapping(raw, "stage", "Stage")
    detail = text_from_mapping(raw, "detail", "Detail")
    cue_count = text_from_mapping(raw, "cue_count", "CueCount")
    completed_steps = string_list_from_mapping(raw, "completed_steps", "CompletedSteps")
    completed_text = ", ".join(step.replace("_", " ") for step in completed_steps[-3:])
    detail_parts = [f"{step_index} / {step_total}", stage.replace("_", " ") if stage else "", detail]
    if cue_count:
        detail_parts.append(f"{cue_count} cue(s)")
    if completed_text:
        detail_parts.append(f"done: {completed_text}")
    if bool_from_mapping(raw, "failed", "Failed"):
        status = "blocked"
    elif bool_from_mapping(raw, "completed", "Completed") or step_index >= step_total:
        status = "complete"
    else:
        status = progress_state_status(text_from_mapping(raw, "status", "Status"), stage, stale=stale)
    label_parts = ["Subtitle", kind.upper()]
    if stream_index not in ("", "-1"):
        label_parts.append(f"stream {stream_index}")
    return [
        progress_bar(
            bar_id="subtitle_track",
            label=" ".join(label_parts),
            status=status,
            percent=percent,
            mode="stepped",
            detail=" | ".join(part for part in detail_parts if part),
            source="pipeline_progress.json",
            updated_at=text_from_mapping(raw, "updated_at", "UpdatedAt"),
            stale=stale,
        )
    ]


def audio_progress_bars(progress: Mapping[str, Any], *, stale: bool) -> list[dict[str, Any]]:
    raw = progress.get("AudioProgress")
    if not isinstance(raw, Mapping):
        return []
    stream_index = text_from_mapping(raw, "stream_index", "StreamIndex")
    action = text_from_mapping(raw, "action", "Action")
    stage = text_from_mapping(raw, "stage", "Stage")
    status_text = text_from_mapping(raw, "status", "Status")
    source_codec = text_from_mapping(raw, "source_codec", "SourceCodec")
    source_channels = text_from_mapping(raw, "source_channels", "SourceChannels")
    output_codec = text_from_mapping(raw, "output_codec", "OutputCodec")
    output_channels = text_from_mapping(raw, "output_channels", "OutputChannels")
    language = text_from_mapping(raw, "language", "Language")
    reason = text_from_mapping(raw, "reason", "Reason")
    detail = text_from_mapping(raw, "detail", "Detail")
    step_total = int_from_mapping(raw, "step_total", "StepTotal")
    step_index = max(0, min(step_total, int_from_mapping(raw, "step_index", "StepIndex"))) if step_total > 0 else 0
    percent = float_from_mapping(raw, "percent", "Percent")
    if percent is None and step_total > 0:
        percent = max(0.0, min(100.0, round((step_index / step_total) * 100.0, 1)))
    if bool_from_mapping(raw, "failed", "Failed"):
        status = "blocked"
    elif bool_from_mapping(raw, "completed", "Completed"):
        status = "complete"
    else:
        status = progress_state_status(status_text, action, stage, stale=stale)
        if status == "unknown":
            status = "active"
    codec_detail = " -> ".join(part for part in (source_codec, output_codec) if part)
    channel_detail = " -> ".join(
        f"{part}ch" for part in (source_channels, output_channels) if part not in ("", "-1")
    )
    detail_parts = [
        f"{step_index} / {step_total}" if step_total > 0 else "",
        stage.replace("_", " ") if stage else "",
        action.replace("_", " ") if action else "",
        codec_detail,
        channel_detail,
        language,
        reason,
        detail,
    ]
    label_parts = ["Audio"]
    if action:
        label_parts.append(action.replace("_", " ").title())
    if stream_index not in ("", "-1"):
        label_parts.append(f"stream {stream_index}")
    return [
        progress_bar(
            bar_id="audio_track",
            label=" ".join(label_parts),
            status=status,
            percent=percent,
            mode="stepped" if step_total > 0 else progress_mode(percent, status),
            detail=" | ".join(part for part in detail_parts if part),
            source="pipeline_progress.json",
            updated_at=text_from_mapping(raw, "updated_at", "UpdatedAt"),
            stale=stale,
        )
    ]


def pending_drain_progress_bars(progress: Mapping[str, Any], *, stale: bool) -> list[dict[str, Any]]:
    raw = progress.get("PendingDrainProgress")
    if not isinstance(raw, Mapping):
        return []
    total = int_from_mapping(raw, "manifest_count", "ManifestCount", "manifest_count_at_start", "ManifestCountAtStart")
    attempted = int_from_mapping(raw, "attempted_count", "AttemptedCount")
    succeeded = int_from_mapping(raw, "succeeded_count", "SucceededCount")
    already = int_from_mapping(raw, "already_published_count", "AlreadyPublishedCount")
    errors = int_from_mapping(raw, "error_count", "ErrorCount")
    skipped = int_from_mapping(raw, "skipped_count", "SkippedCount")
    remaining = int_from_mapping(raw, "remaining_count", "RemainingCount")
    status_text = text_from_mapping(raw, "status", "Status")
    current_manifest = text_from_mapping(raw, "current_manifest", "CurrentManifest")
    current_item = text_from_mapping(raw, "current_item", "CurrentItem")
    percent = max(0.0, min(100.0, round((attempted / total) * 100.0, 1))) if total > 0 else None
    if errors > 0:
        status = "blocked"
    elif total > 0 and attempted >= total and remaining == 0:
        status = "complete"
    elif bool_from_mapping(raw, "deferred", "Deferred"):
        status = "review"
    else:
        status = progress_state_status(status_text, "retrying", stale=stale)
    detail_parts = [
        f"{attempted} / {total} manifests" if total > 0 else "",
        f"succeeded {succeeded}" if succeeded else "",
        f"already published {already}" if already else "",
        f"errors {errors}" if errors else "",
        f"skipped {skipped}" if skipped else "",
        f"remaining {remaining}" if remaining else "",
        current_item,
        current_manifest,
    ]
    return [
        progress_bar(
            bar_id="pending_drain",
            label="Pending publish drain",
            status=status,
            percent=percent,
            detail=" | ".join(part for part in detail_parts if part),
            source="pipeline_progress.json",
            updated_at=text_from_mapping(raw, "updated_at", "UpdatedAt"),
            stale=stale,
        )
    ]


def pipeline_progress_bars(progress: Mapping[str, Any], *, pipeline_state: str, stale: bool) -> list[dict[str, Any]]:
    if not progress:
        return []
    bars: list[dict[str, Any]] = []
    stage = text_from_mapping(progress, "CurrentStage", "Status")
    route = text_from_mapping(progress, "CurrentRoute", "Route")
    file_display = text_from_mapping(progress, "CurrentFileDisplay", "CurrentFile")
    queue_phase = text_from_mapping(progress, "CurrentQueuePhase")
    percent = float_from_mapping(progress, "CurrentStagePercent")
    copy_state = text_from_mapping(progress, "CopyState")
    push_state = text_from_mapping(progress, "PushState")
    sidecar_state = text_from_mapping(progress, "SidecarState")
    status = progress_state_status(
        pipeline_state,
        text_from_mapping(progress, "Status"),
        stage,
        push_state,
        sidecar_state,
        stale=stale,
    )
    stage_lower = stage.lower()
    detail_parts = [part for part in (stage, route, file_display) if part]
    if copy_state:
        detail_parts.append(f"copy={copy_state}")
    if stage_lower in {"copy", "copy_to_scratch"}:
        byte_detail = copy_bytes_detail(progress)
        if byte_detail:
            detail_parts.append(byte_detail)
        detail_parts.append("source unchanged")
    finalizing_detail = finalizing_progress_detail(stage, percent)
    if finalizing_detail:
        detail_parts.append(finalizing_detail)
    if push_state:
        detail_parts.append(f"publish={push_state}")
    if sidecar_state:
        detail_parts.append(f"sidecar={sidecar_state}")
    bars.append(
        progress_bar(
            bar_id="current_stage",
            label="Current backend stage",
            status=status,
            percent=percent,
            detail=" | ".join(detail_parts),
            source="pipeline_progress.json",
            updated_at=text_from_mapping(progress, "LastUpdate", "UpdatedAt", "updated_at"),
            stale=stale,
        )
    )

    queue_total = int_from_mapping(progress, "CurrentQueueTotal")
    if queue_total > 0:
        queue_index = max(0, min(queue_total, int_from_mapping(progress, "CurrentQueueIndex")))
        queue_percent = max(0.0, min(100.0, round((queue_index / queue_total) * 100.0, 1)))
        queue_phase_lower = queue_phase.lower()
        total_label = "Pending publish total" if queue_phase_lower == "pending_push" else "Run total"
        total_detail = f"Pending item {queue_index} / {queue_total}" if queue_phase_lower == "pending_push" else f"Item {queue_index} / {queue_total}"
        bars.append(
            progress_bar(
                bar_id="run_total",
                label=total_label,
                status=status,
                percent=queue_percent,
                detail=total_detail,
                source="pipeline_progress.json",
                updated_at=text_from_mapping(progress, "LastUpdate", "UpdatedAt", "updated_at"),
                stale=stale,
            )
        )

    copy_percent = float_from_mapping(progress, "CopyPercent")
    if push_state or sidecar_state or stage_lower in {"push", "sidecar", "retry_pending_push"}:
        publish_steps = publish_step_payloads(stage, push_state, sidecar_state)
        publish_percent = publish_steps_percent(publish_steps)
        publish_status = progress_state_status(push_state, sidecar_state, stage, stale=stale)
        step_detail = f"{sum(1 for step in publish_steps if step.get('status') == 'complete')} / {len(publish_steps)} publish steps"
        bars.append(
            progress_bar(
                bar_id="publish_output",
                label="Publish steps",
                status=publish_status,
                percent=publish_percent,
                mode="stepped",
                detail=" | ".join(part for part in (step_detail, push_state, sidecar_state, route, file_display) if part),
                source="pipeline_progress.json",
                updated_at=text_from_mapping(progress, "LastUpdate", "UpdatedAt", "updated_at"),
                stale=stale,
                steps=publish_steps,
            )
        )
        if push_state.lower() == "copying" and copy_percent is not None:
            copied_bytes = nullable_int_from_mapping(progress, "CopyBytesCopied")
            total_bytes = nullable_int_from_mapping(progress, "CopyTotalBytes")
            byte_detail = ""
            if total_bytes is not None and total_bytes > 0:
                byte_detail = f"{format_bytes(copied_bytes or 0)} / {format_bytes(total_bytes)}"
            copy_detail = " | ".join(part for part in (byte_detail, route, file_display) if part)
            bars.append(
                progress_bar(
                    bar_id="publish_copy",
                    label="Publishing completed output",
                    status=progress_state_status(push_state, stage, stale=stale),
                    percent=copy_percent,
                    detail=copy_detail,
                    source="pipeline_progress.json",
                    updated_at=text_from_mapping(progress, "CopyUpdatedAt", "LastUpdate", "UpdatedAt", "updated_at"),
                    stale=stale,
                )
            )
    bars.extend(pending_drain_progress_bars(progress, stale=stale))
    bars.extend(audio_progress_bars(progress, stale=stale))
    bars.extend(subtitle_progress_bars(progress, stale=stale))
    return bars


def string_list_from_mapping(mapping: Mapping[str, Any], *keys: str) -> list[str]:
    for key in keys:
        raw = mapping.get(key)
        if isinstance(raw, (list, tuple)):
            return [str(item).strip() for item in raw if str(item).strip()]
        if raw not in (None, ""):
            return [part.strip() for part in str(raw).split(",") if part.strip()]
    return []


def audit_report_progress_bar(audit_progress: Mapping[str, Any], *, status_text: str, stale: bool = False) -> dict[str, Any] | None:
    step_total = int_from_mapping(audit_progress, "report_step_total", "ReportStepTotal")
    if step_total <= 0:
        return None
    step_index = int_from_mapping(audit_progress, "report_step_index", "ReportStepIndex")
    step_index = max(0, min(step_total, step_index))
    percent = max(0.0, min(100.0, round((step_index / step_total) * 100.0, 1)))
    stage = text_from_mapping(audit_progress, "report_stage", "ReportStage")
    stage_label = stage.replace("_", " ").strip() or "report generation"
    completed_steps = string_list_from_mapping(audit_progress, "report_completed_steps", "ReportCompletedSteps")
    completed_text = ", ".join(step.replace("_", " ") for step in completed_steps[-3:])
    path_parts = [
        "JSON" if text_from_mapping(audit_progress, "latest_json_path", "LatestJsonPath") else "",
        "CSV" if text_from_mapping(audit_progress, "latest_csv_path", "LatestCsvPath") else "",
        "Priority CSV" if text_from_mapping(audit_progress, "latest_priority_csv_path", "LatestPriorityCsvPath") else "",
        "Text" if text_from_mapping(audit_progress, "latest_text_path", "LatestTextPath") else "",
    ]
    detail_parts = [f"{step_index} / {step_total}", stage_label]
    if completed_text:
        detail_parts.append(f"done: {completed_text}")
    written_paths = ", ".join(part for part in path_parts if part)
    if written_paths:
        detail_parts.append(f"written: {written_paths}")
    if audit_progress.get("failed") is True:
        status = "blocked"
    elif step_index >= step_total and (audit_progress.get("completed") is True or stage.lower() == "complete"):
        status = "complete"
    else:
        status = progress_state_status(status_text, stage, stale=stale)
    return progress_bar(
        bar_id="audit_reports",
        label="Audit reports",
        status=status,
        percent=percent,
        mode="stepped",
        detail=" | ".join(detail_parts),
        source="audit_progress.json",
        updated_at=text_from_mapping(audit_progress, "last_update", "LastUpdate", "updated_at"),
        stale=stale,
    )


def audit_progress_bars(audit_progress: Mapping[str, Any], *, stale: bool = False) -> list[dict[str, Any]]:
    if not audit_progress:
        return []
    processed = int_from_mapping(audit_progress, "processed_files", "ProcessedFiles")
    total = int_from_mapping(audit_progress, "total_files", "TotalFiles")
    percent = float_from_mapping(audit_progress, "percent_complete", "PercentComplete")
    if percent is None and total > 0:
        percent = max(0.0, min(100.0, round((processed / total) * 100.0, 1)))
    status_text = text_from_mapping(audit_progress, "status", "Status")
    if audit_progress.get("failed") is True:
        status_text = "failed"
    elif audit_progress.get("completed") is True:
        status_text = "completed"
        percent = 100.0
    detail = text_from_mapping(audit_progress, "current_operation", "CurrentOperation", "current_file", "CurrentFile")
    if total > 0:
        count_detail = f"{processed} / {total}"
        detail = f"{count_detail} | {detail}" if detail else count_detail
    bars = [
        progress_bar(
            bar_id="audit_progress",
            label="Audit progress",
            status=progress_state_status(status_text, stale=stale),
            percent=percent,
            detail=detail,
            source="audit_progress.json",
            updated_at=text_from_mapping(audit_progress, "last_update", "LastUpdate", "updated_at"),
            stale=stale,
        )
    ]
    report_bar = audit_report_progress_bar(audit_progress, status_text=status_text, stale=stale)
    if report_bar is not None:
        bars.append(report_bar)
    return bars


def snapshot_progress_bars(snapshot: _StatusSnapshot, *, pipeline_state: str) -> list[dict[str, Any]]:
    progress = snapshot.progress or {}
    audit_progress = snapshot.audit_progress or {}
    stale = "stale progress" in str(snapshot.current_activity or "").lower()
    audit_stale = _audit_progress_is_stale(audit_progress)
    return [
        *pipeline_progress_bars(progress, pipeline_state=pipeline_state, stale=stale),
        *audit_progress_bars(audit_progress, stale=audit_stale),
    ]


def optional_path_text(path: Path | None) -> str:
    return str(path) if path else ""


def snapshot_latest_paths(snapshot: _StatusSnapshot) -> dict[str, str]:
    latest_paths = {
        "latest_failure_report": optional_path_text(snapshot.latest_failure_report),
        "latest_failure_json": optional_path_text(snapshot.latest_failure_json),
        "latest_audit_csv": optional_path_text(snapshot.latest_audit_csv),
        "latest_priority_csv": optional_path_text(snapshot.latest_priority_csv),
    }
    return {key: value for key, value in latest_paths.items() if value}


def snapshot_warnings(snapshot: _StatusSnapshot) -> list[str]:
    if snapshot.last_error:
        return [str(snapshot.last_error)]
    return []


def snapshot_recent_events(snapshot: _StatusSnapshot, *, limit: int = 25) -> list[dict[str, Any]]:
    return [dict(item) for item in snapshot.pipeline_events[-limit:]]


def telemetry_sampled_at(telemetry: _TelemetrySnapshot) -> str:
    if telemetry.collected_at is None:
        return ""
    if telemetry.collected_at.tzinfo:
        return telemetry.collected_at.astimezone().isoformat()
    return telemetry.collected_at.isoformat()


def telemetry_gpu_present(telemetry: _TelemetrySnapshot) -> bool:
    return (
        telemetry.gpu_count > 0
        or telemetry.gpu_encoder_percent is not None
        or bool(str(telemetry.gpu_name or "").strip())
        or bool(telemetry.gpu_rows)
    )


def telemetry_fields(telemetry: _TelemetrySnapshot) -> dict[str, Any]:
    return {
        "sampled_at": telemetry_sampled_at(telemetry),
        "cpu_percent": telemetry.cpu_percent,
        "cpu_utility_percent": telemetry.cpu_utility_percent,
        "memory_percent": telemetry.memory_percent,
        "memory_used_gb": telemetry.memory_used_gb,
        "memory_total_gb": telemetry.memory_total_gb,
        "gpu_present": telemetry_gpu_present(telemetry),
        "gpu_percent": telemetry.gpu_percent,
        "gpu_encoder_percent": telemetry.gpu_encoder_percent,
        "gpu_name": telemetry.gpu_name,
        "gpu_index": telemetry.gpu_index,
        "gpu_count": telemetry.gpu_count,
        "gpu_rows": [dict(row) for row in telemetry.gpu_rows],
        "gpu_temperature_c": telemetry.gpu_temperature_c,
        "gpu_memory_percent": telemetry.gpu_memory_percent,
        "gpu_memory_used_gb": telemetry.gpu_memory_used_gb,
        "gpu_memory_total_gb": telemetry.gpu_memory_total_gb,
        "gpu_encoder_usage": gpu_encoder_usage_payload(telemetry),
        "source": telemetry.source,
        "error": telemetry.error,
    }

__all__ = [
    "APP_CAPABILITIES",
    "ACTIVE_PROGRESS_STATES",
    "COMPLETE_PROGRESS_STATES",
    "HELD_PROGRESS_STATES",
    "FAILED_PROGRESS_STATES",
    "application_capabilities",
    "int_from_mapping",
    "nullable_int_from_mapping",
    "format_bytes",
    "snapshot_counts",
    "text_from_mapping",
    "float_from_mapping",
    "bool_from_mapping",
    "progress_state_status",
    "progress_mode",
    "progress_bar",
    "publish_step_payloads",
    "publish_steps_percent",
    "subtitle_progress_bars",
    "audio_progress_bars",
    "pending_drain_progress_bars",
    "pipeline_progress_bars",
    "string_list_from_mapping",
    "audit_report_progress_bar",
    "audit_progress_bars",
    "snapshot_progress_bars",
    "optional_path_text",
    "snapshot_latest_paths",
    "snapshot_warnings",
    "snapshot_recent_events",
    "telemetry_sampled_at",
    "telemetry_gpu_present",
    "telemetry_fields",
]
